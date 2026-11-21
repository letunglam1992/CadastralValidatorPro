"""Đề xuất sửa đầu mút treo (Tab 2 — Master Prompt VII mức B: cần người dùng duyệt từng đối tượng).

Ba kiểu thao tác, chỉ dời MỘT đỉnh đầu mút của phần tử Line/LineString nguồn:
- TRIM   (thừa nét): đoạn cuối cắt qua nét ranh khác rồi thò ra → kéo đầu mút về giao điểm.
- EXTEND (hụt nét) : kéo dài đoạn cuối theo đúng hướng tới khi chạm nét ranh khác.
- JOIN   (hở đôi)  : hai đầu mút treo đối diện nhau → nối đầu này vào đúng đầu kia (bỏ đề xuất ngược lại).
- SNAP   (lệch)    : không kéo thẳng được → bắt vào điểm gần nhất trên nét ranh khác (rủi ro cao hơn).
Nếu điểm đích cách một đỉnh của nét đích ≤ vertex_snap thì bắt vào đỉnh đó (tránh tạo mảnh vụn).

Không xử lý: phần tử đóng (shape), phần tử con trong complex/cell, đầu mút không khớp phần tử nguồn.
Không sửa dữ liệu gốc: apply_fixes() trả BẢN SAO trong bộ nhớ.
"""
from __future__ import annotations

import copy
import hashlib
import math
from dataclasses import asdict, dataclass, field
from typing import Optional

from shapely import STRtree
from shapely.geometry import LineString, MultiPoint, Point
from shapely.ops import nearest_points

from .models import MapSheet, RawElement
from . import topology as topo

EDITABLE = {"line", "linestring"}


@dataclass
class FixProposal:
    fix_id: str
    sheet_id: str
    element_id: str
    element_type: str
    level: int
    vertex_index: int              # 0 = đầu, -1 = cuối (theo GetVertices)
    before: tuple[float, float]
    after: tuple[float, float]
    action: str                    # TRIM | EXTEND | SNAP
    gap_m: float
    target_element_id: Optional[str] = None
    risk: str = "B"
    note: str = ""
    approved: bool = False

    def to_dict(self):
        return asdict(self)


def _fid(sheet_id, el_id, idx, action, after) -> str:
    key = f"{sheet_id}|{el_id}|{idx}|{action}|{after[0]:.3f}|{after[1]:.3f}"
    return hashlib.sha1(key.encode()).hexdigest()[:10]


def _points(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == "Point":
        return [geom]
    if geom.geom_type in ("MultiPoint", "GeometryCollection"):
        out = []
        for g in geom.geoms:
            out += _points(g)
        return out
    if geom.geom_type in ("LineString", "MultiLineString"):   # chồng khít: lấy các đỉnh
        return [Point(c) for c in (geom.coords if geom.geom_type == "LineString"
                                   else [c for g in geom.geoms for c in g.coords])]
    return []


def propose_dangle_fixes(sheet: MapSheet, boundary_levels: set[int], dangles: list[tuple[Point, list[str]]],
                         max_gap: float = 1.0, vertex_snap: float = 0.05) -> tuple[list[FixProposal], list[dict]]:
    """Trả (đề xuất, danh sách đầu mút không đề xuất được + lý do)."""
    src = [e for e in sheet.elements if e.level in boundary_levels and e.type in EDITABLE and len(e.coords) >= 2]
    lines = topo.collect_lines(sheet.elements, boundary_levels)
    geoms = [l.geom for l in lines if l.geom.length > 0]
    gids = [l.element_id for l in lines if l.geom.length > 0]
    tree = STRtree(geoms) if geoms else None
    ends: dict[tuple[int, int], list[tuple[RawElement, int]]] = {}
    for e in src:
        for idx, c in ((0, e.coords[0]), (-1, e.coords[-1])):
            ends.setdefault((round(c[0] * 1000), round(c[1] * 1000)), []).append((e, idx))

    proposals: list[FixProposal] = []
    skipped: list[dict] = []
    dpts = [(round(p.x * 1000), round(p.y * 1000)) for p, _ in dangles]
    dtree = STRtree([p for p, _ in dangles]) if dangles else None
    consumed: set[tuple[int, int]] = set()
    dangle_keys = set(dpts)
    for p, _ids in dangles:
        key = (round(p.x * 1000), round(p.y * 1000))
        if key in consumed:
            continue
        hits = ends.get((round(p.x * 1000), round(p.y * 1000)), [])
        if len(hits) != 1:
            skipped.append({"x": p.x, "y": p.y, "reason": "không khớp đúng 1 đầu mút Line/LineString sửa được"
                            if not hits else "nhiều phần tử chung đầu mút"})
            continue
        el, idx = hits[0]
        end = el.coords[idx]
        other_end = el.coords[-1] if idx == 0 else el.coords[0]
        okey = (round(other_end[0] * 1000), round(other_end[1] * 1000))
        el_len = LineString(el.coords).length
        if okey in dangle_keys and el_len < 2 * max_gap:
            skipped.append({"x": p.x, "y": p.y, "element_id": el.id,
                            "reason": f"nét rời ngắn {el_len:.2f} m treo cả hai đầu — nghi ký hiệu/nét thừa, không tự nối"})
            continue
        prev = el.coords[1] if idx == 0 else el.coords[-2]
        others = [] if tree is None else [int(j) for j in tree.query(Point(end).buffer(max_gap + 1e-6))
                                          if gids[int(j)] != el.id]
        if not others:
            skipped.append({"x": p.x, "y": p.y, "reason": f"không có nét ranh khác trong {max_gap} m",
                            "element_id": el.id})
            continue
        cands = []   # (dist, action, point, target_id)
        # JOIN: đầu mút treo khác của phần tử khác trong ngưỡng -> nối hai đầu với nhau
        if dtree is not None:
            for j in dtree.query(Point(end).buffer(max_gap)):
                q, _ = dangles[int(j)]
                d = q.distance(Point(end))
                k2 = dpts[int(j)]
                owner = ends.get(k2, [])
                if 1e-6 < d < max_gap and k2 not in consumed and owner and owner[0][0].id != el.id:
                    cands.append((d, "JOIN", q, owner[0][0].id))
        # TRIM: đoạn cuối cắt nét khác, phần thò ra < max_gap
        seg = LineString([prev, end])
        for j in others:
            for q in _points(seg.intersection(geoms[j])):
                d = q.distance(Point(end))
                if 1e-6 < d < max_gap and q.distance(Point(prev)) > 1e-6:
                    cands.append((d, "TRIM", q, gids[j]))
        # EXTEND: kéo dài theo hướng đoạn cuối
        dx, dy = end[0] - prev[0], end[1] - prev[1]
        L = math.hypot(dx, dy)
        if L > 0:
            ray = LineString([end, (end[0] + dx / L * max_gap, end[1] + dy / L * max_gap)])
            for j in others:
                for q in _points(ray.intersection(geoms[j])):
                    d = q.distance(Point(end))
                    if 1e-6 < d <= max_gap:
                        cands.append((d, "EXTEND", q, gids[j]))
        if not cands:   # SNAP: điểm gần nhất
            best = None
            for j in others:
                q = nearest_points(Point(end), geoms[j])[1]
                d = q.distance(Point(end))
                if 1e-6 < d < max_gap and (best is None or d < best[0]):
                    best = (d, "SNAP", q, gids[j])
            if best:
                cands.append(best)
        if not cands:
            dmin = min(geoms[j].distance(Point(end)) for j in others)
            skipped.append({"x": p.x, "y": p.y, "element_id": el.id,
                            "reason": (f"khoảng hở {dmin:.2f} m ≥ ngưỡng {max_gap} m" if dmin >= max_gap
                                       else "không tìm được điểm nối hợp lệ")})
            continue
        joins = [c for c in cands if c[1] == "JOIN"]
        if joins:   # ưu tiên nối hai đầu treo đối diện
            cands = sorted(joins, key=lambda t: t[0])
        else:
            cands.sort(key=lambda t: (t[0], {"TRIM": 0, "EXTEND": 1, "SNAP": 2}[t[1]]))
        d, action, q, tgt = cands[0]
        note = ""
        if action == "JOIN":
            consumed.add((round(q.x * 1000), round(q.y * 1000)))
            note = "nối vào đầu mút treo của phần tử đích"
        else:
            # bắt vào đỉnh nét đích nếu rất gần
            tgeom = geoms[gids.index(tgt)]
            near_v = min((Point(c) for c in tgeom.coords), key=lambda v: v.distance(q))
            if near_v.distance(q) <= vertex_snap:
                q = near_v
                note = "bắt vào đỉnh nét đích"
        consumed.add(key)
        after = (round(q.x, 6), round(q.y, 6))
        proposals.append(FixProposal(
            fix_id=_fid(sheet.sheet_id, el.id, idx, action, after), sheet_id=sheet.sheet_id, element_id=el.id,
            element_type=el.type, level=el.level, vertex_index=idx, before=(end[0], end[1]), after=after,
            action=action, gap_m=round(d, 4), target_element_id=tgt,
            risk="B" if action != "SNAP" else "B+", note=note))
    return proposals, skipped


def apply_fixes(sheet: MapSheet, proposals: list[FixProposal]) -> MapSheet:
    """Áp dụng các đề xuất ĐÃ DUYỆT lên BẢN SAO trong bộ nhớ."""
    out = copy.deepcopy(sheet)
    byid = {e.id: e for e in out.elements}
    for fp in proposals:
        if not fp.approved:
            continue
        e = byid.get(fp.element_id)
        if e is None:
            continue
        i = 0 if fp.vertex_index == 0 else len(e.coords) - 1
        if abs(e.coords[i][0] - fp.before[0]) > 1e-3 or abs(e.coords[i][1] - fp.before[1]) > 1e-3:
            continue   # dữ liệu đã khác lúc đề xuất -> bỏ qua
        e.coords[i] = (fp.after[0], fp.after[1])
    return out


@dataclass
class ChangeSet:
    changeset_id: str
    created_at: str
    sheet_id: str
    source_file: str
    source_sha256: Optional[str]
    rule_pack: str
    level_profile: str
    max_gap_m: float
    approved_by: str
    fixes: list[FixProposal] = field(default_factory=list)
    impact: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    status: str = "PROPOSED"       # PROPOSED | EXPORTED | APPLIED_UNVERIFIED | VERIFIED | ROLLED_BACK

    def to_dict(self):
        d = asdict(self)
        d["fixes"] = [f.to_dict() for f in self.fixes]
        return d
