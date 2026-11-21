"""Đọc GML/SHP dạng polygon -> MapSheet.features (nhánh kiểm tra polygon).

- SHP: pyshp; bắt buộc .shp/.shx/.dbf; .prj/.cpg được báo nếu thiếu. Mã trang DBF lấy từ .cpg,
  không có thì phải truyền `encoding` (không đoán).
- GML: lxml; hỗ trợ gml:Polygon, gml:MultiSurface/MultiPolygon với posList/pos/coordinates.
  Thứ tự trục: ghi nhận srsName; KHÔNG tự đảo trục — người dùng xác nhận qua `swap_xy`.
- Ánh xạ trường (field_map) do người dùng cấu hình: {"parcel_no": "...", "area_label": "...",
  "land_type": "...", "so_to": "..."}. Thiếu ánh xạ -> báo, không đoán tên trường.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from shapely.geometry import MultiPolygon, Polygon

from ..domain.models import MapSheet, PolygonFeature, SourceInfo
from .dgn_probe import sha256_file


def _attrs_to_feature(fid: str, geom, attrs: dict[str, Any], field_map: dict[str, str]) -> PolygonFeature:
    def g(key):
        f = field_map.get(key)
        if not f or f not in attrs or attrs[f] in (None, ""):
            return None
        v = attrs[f]
        return str(v).strip() if not isinstance(v, float) else repr(v)
    return PolygonFeature(feature_id=fid, geometry=geom, parcel_no=g("parcel_no"), area_label=g("area_label"),
                          land_type=g("land_type"), so_to=g("so_to"), attrs=attrs)


def read_shp(path: str | Path, field_map: dict[str, str], encoding: Optional[str] = None,
             scale: str = "1:1000", crs_profile_id: str | None = None, crs_confirmed: bool = False
             ) -> tuple[MapSheet, dict]:
    import shapefile  # pyshp
    path = Path(path)
    report: dict[str, Any] = {"missing_sidecars": [], "warnings": []}
    for ext in (".shx", ".dbf"):
        if not path.with_suffix(ext).exists():
            raise FileNotFoundError(f"Thiếu tệp bắt buộc {path.with_suffix(ext).name}")
    for ext in (".prj", ".cpg"):
        if not path.with_suffix(ext).exists():
            report["missing_sidecars"].append(ext)
    if encoding is None:
        cpg = path.with_suffix(".cpg")
        if cpg.exists():
            encoding = cpg.read_text(errors="replace").strip() or None
    if encoding is None:
        raise ValueError(f"{path.name}: không có .cpg — phải chỉ định mã trang DBF (ví dụ 'utf-8' hoặc 'cp1258').")
    feats = []
    with shapefile.Reader(str(path), encoding=encoding) as r:
        fields = [f[0] for f in r.fields[1:]]
        report["fields"] = fields
        for k, f in field_map.items():
            if f and f not in fields:
                report["warnings"].append(f"Trường '{f}' ({k}) không có trong DBF")
        for i, sr in enumerate(r.iterShapeRecords()):
            geo = sr.shape.__geo_interface__
            geom = _from_geojson(geo)
            if geom is None:
                report["warnings"].append(f"Bản ghi {i}: kiểu hình học {geo.get('type')} không phải polygon — bỏ qua")
                continue
            feats.append(_attrs_to_feature(f"{path.stem}:{i}", geom, dict(zip(fields, sr.record)), field_map))
    sheet = MapSheet(sheet_id=path.stem, file_name=path.name, elements=[], features=feats, scale=scale,
                     source=SourceInfo(path=str(path), sha256=sha256_file(path), fmt="shp", reader="pyshp"),
                     crs_profile_id=crs_profile_id, crs_confirmed=crs_confirmed)
    report["features"] = len(feats)
    return sheet, report


def _from_geojson(geo: dict) -> Optional[Polygon | MultiPolygon]:
    t = geo.get("type")
    if t == "Polygon":
        rings = geo["coordinates"]
        return Polygon(rings[0], rings[1:])
    if t == "MultiPolygon":
        return MultiPolygon([Polygon(p[0], p[1:]) for p in geo["coordinates"]])
    return None


GML_NS = ["http://www.opengis.net/gml", "http://www.opengis.net/gml/3.2"]


def _coords_from(el, swap_xy: bool) -> list[tuple[float, float]]:
    from lxml import etree  # noqa: F401
    txt, dim = None, 2
    for ns in GML_NS:
        pl = el.find(f"{{{ns}}}posList")
        if pl is not None:
            txt = pl.text
            dim = int(pl.get("srsDimension") or pl.get("dimension") or el.get("srsDimension") or 2)
            break
        pos = el.findall(f"{{{ns}}}pos")
        if pos:
            pts = [tuple(map(float, p.text.split()[:2])) for p in pos]
            return [(b, a) for a, b in pts] if swap_xy else pts
        co = el.find(f"{{{ns}}}coordinates")
        if co is not None:
            pts = [tuple(map(float, t.split(",")[:2])) for t in co.text.split()]
            return [(b, a) for a, b in pts] if swap_xy else pts
    if txt is None:
        return []
    vals = list(map(float, txt.split()))
    pts = [(vals[i], vals[i + 1]) for i in range(0, len(vals) - dim + 1, dim)]
    return [(b, a) for a, b in pts] if swap_xy else pts


def read_gml(path: str | Path, field_map: dict[str, str], swap_xy: bool = False, scale: str = "1:1000",
             crs_profile_id: str | None = None, crs_confirmed: bool = False) -> tuple[MapSheet, dict]:
    from lxml import etree
    path = Path(path)
    tree = etree.parse(str(path))
    root = tree.getroot()
    report: dict[str, Any] = {"srsName": set(), "warnings": [], "swap_xy": swap_xy}
    feats = []
    members = []
    for ns in GML_NS:
        members += root.findall(f".//{{{ns}}}featureMember") + root.findall(f".//{{{ns}}}featureMembers/*")
    for i, m in enumerate(members):
        feat = m[0] if m.tag.endswith("featureMember") and len(m) else m
        polys = []
        for ns in GML_NS:
            for pg in feat.iter(f"{{{ns}}}Polygon"):
                if pg.get("srsName"):
                    report["srsName"].add(pg.get("srsName"))
                ext = None
                ints = []
                for tag in ("exterior", "outerBoundaryIs"):
                    e = pg.find(f"{{{ns}}}{tag}")
                    if e is not None:
                        ext = _coords_from(e[0], swap_xy)
                for tag in ("interior", "innerBoundaryIs"):
                    for e in pg.findall(f"{{{ns}}}{tag}"):
                        ints.append(_coords_from(e[0], swap_xy))
                if ext:
                    polys.append(Polygon(ext, ints))
        if not polys:
            report["warnings"].append(f"Đối tượng {i}: không có polygon")
            continue
        geom = polys[0] if len(polys) == 1 else MultiPolygon(polys)
        attrs = {}
        for ch in feat:
            if len(ch) == 0 and ch.text is not None:
                attrs[etree.QName(ch).localname] = ch.text.strip()
        fid = feat.get("{http://www.opengis.net/gml}id") or feat.get("{http://www.opengis.net/gml/3.2}id") or str(i)
        feats.append(_attrs_to_feature(fid, geom, attrs, field_map))
    report["srsName"] = sorted(report["srsName"])
    report["features"] = len(feats)
    sheet = MapSheet(sheet_id=path.stem, file_name=path.name, elements=[], features=feats, scale=scale,
                     source=SourceInfo(path=str(path), sha256=sha256_file(path), fmt="gml", reader="lxml"),
                     crs_profile_id=crs_profile_id, crs_confirmed=crs_confirmed)
    return sheet, report
