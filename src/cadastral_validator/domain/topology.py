"""Hình học/topology: dựng vùng từ nét rời (noding + polygonize), đầu mút treo,
chồng lấn, khe hở trong vùng bao phủ, mảnh vụn.

Không sửa dữ liệu: snapping chỉ áp dụng trên BẢN SAO trong bộ nhớ để dựng vùng
kiểm tra; độ dịch chuyển cực đại được ghi lại làm bằng chứng (Master Prompt V.3).
Không dùng buffer(0)/make_valid để "sửa" (V.9).
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

import shapely
from shapely import STRtree
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.ops import polygonize_full, unary_union
from shapely.validation import explain_validity

from .models import RawElement

LINE_TYPES = {"line", "linestring", "shape", "complex_shape", "complex_string", "arc", "ellipse", "curve"}


@dataclass
class SourceLine:
    geom: LineString
    element_id: str
    level: int


@dataclass
class LineworkResult:
    regions: list[Polygon]
    dangles: list[tuple[Point, list[str]]]          # (điểm, element ids)
    zero_length: list[SourceLine]
    invalid_rings: list[LineString]
    max_snap_shift: float
    noded: list[LineString] = field(default_factory=list)


def collect_lines(elements: Iterable[RawElement], levels: set[int]) -> list[SourceLine]:
    out: list[SourceLine] = []

    def visit(el: RawElement, level_override: Optional[int] = None):
        lvl = el.level if level_override is None else level_override
        if el.type in LINE_TYPES and lvl in levels and len(el.coords) >= 2:
            coords = [(float(x), float(y)) for x, y in el.coords]
            if el.closed and coords[0] != coords[-1]:
                coords.append(coords[0])
            out.append(SourceLine(LineString(coords), el.id, lvl))
        elif el.type in LINE_TYPES and lvl in levels and len(el.coords) == 1:
            out.append(SourceLine(LineString([el.coords[0], el.coords[0]]), el.id, lvl))
        for ch in el.children:
            if el.type in ("complex_shape", "complex_string") and not el.coords:
                visit(ch, lvl)
            elif el.type == "cell":
                visit(ch)

    for e in elements:
        visit(e)
    return out


def _snap_lines(lines: list[SourceLine], tol: float) -> tuple[list[LineString], float]:
    """Snap đầu mút/đỉnh tới hình học lân cận trong ngưỡng tol. Trả hình học mới + độ dịch max."""
    if tol <= 0 or not lines:
        return [sl.geom for sl in lines], 0.0
    geoms = [sl.geom for sl in lines]
    tree = STRtree(geoms)
    out: list[LineString] = []
    max_shift = 0.0
    for i, g in enumerate(geoms):
        idx = tree.query(g.buffer(tol))
        neigh = [geoms[j] for j in idx if j != i]
        if not neigh:
            out.append(g)
            continue
        ref = unary_union(neigh)
        sg = shapely.snap(g, ref, tol)
        for (x0, y0), (x1, y1) in zip(g.coords, sg.coords):
            max_shift = max(max_shift, math.hypot(x1 - x0, y1 - y0))
        out.append(sg)
    return out, max_shift


def _key(pt: tuple[float, float], grid: float) -> tuple[int, int]:
    return (round(pt[0] / grid), round(pt[1] / grid))


def build_regions(lines: list[SourceLine], snap_tol: float, frame_boundary=None,
                  frame_tol: float = 0.1) -> LineworkResult:
    zero = [sl for sl in lines if sl.geom.length == 0]
    good = [sl for sl in lines if sl.geom.length > 0]
    snapped, max_shift = _snap_lines(good, snap_tol)
    if not snapped:
        return LineworkResult([], [], zero, [], 0.0)
    noded_union = unary_union(snapped)
    noded = list(noded_union.geoms) if isinstance(noded_union, MultiLineString) else [noded_union]
    noded = [g for g in noded if isinstance(g, LineString) and g.length > 0]

    # Bậc nút trên lưới làm tròn theo snap_tol (tối thiểu 1 mm)
    grid = max(snap_tol, 0.001)
    degree: dict[tuple[int, int], int] = defaultdict(int)
    node_xy: dict[tuple[int, int], tuple[float, float]] = {}
    for g in noded:
        for pt in (g.coords[0], g.coords[-1]):
            k = _key(pt, grid)
            degree[k] += 1
            node_xy.setdefault(k, pt)

    # ánh xạ điểm -> element gốc để truy vết
    src_tree = STRtree([sl.geom for sl in good]) if good else None
    dangles: list[tuple[Point, list[str]]] = []
    for k, d in degree.items():
        if d != 1:
            continue
        p = Point(node_xy[k])
        if frame_boundary is not None and frame_boundary.distance(p) <= frame_tol:
            continue
        ids: list[str] = []
        if src_tree is not None:
            for j in src_tree.query(p.buffer(max(snap_tol, 0.001) * 2)):
                ids.append(good[j].element_id)
        dangles.append((p, sorted(set(ids))))

    polys, _dangles_geom, _cuts, invalid = polygonize_full(noded)
    regions = [p for p in polys.geoms] if polys is not None else []
    invalid_rings = [g for g in invalid.geoms] if invalid is not None else []
    return LineworkResult(regions, dangles, zero, invalid_rings, max_shift, noded)


def compactness(poly: Polygon) -> float:
    """Chỉ số Polsby-Popper: 4πA/P² (gần 0 = rất mảnh/dài)."""
    if poly.length == 0:
        return 0.0
    return 4 * math.pi * poly.area / (poly.length ** 2)


def find_overlaps(polys: list[Polygon], threshold_m2: float) -> list[tuple[int, int, Polygon]]:
    out = []
    if not polys:
        return out
    tree = STRtree(polys)
    for i, a in enumerate(polys):
        for j in tree.query(a):
            j = int(j)
            if j <= i:
                continue
            b = polys[j]
            if not a.intersects(b):
                continue
            inter = a.intersection(b)
            area = inter.area
            if area > threshold_m2 and inter.geom_type in ("Polygon", "MultiPolygon", "GeometryCollection"):
                out.append((i, j, inter))
    return out


def find_gaps(polys: list[Polygon], coverage: Polygon) -> list[Polygon]:
    """Khe hở = vùng bao phủ hợp lệ trừ hợp các thửa. Chỉ gọi khi có coverage."""
    if coverage is None or coverage.is_empty:
        return []
    merged = unary_union(polys) if polys else Polygon()
    diff = coverage.difference(merged)
    if diff.is_empty:
        return []
    if diff.geom_type == "Polygon":
        return [diff]
    return [g for g in getattr(diff, "geoms", []) if g.geom_type == "Polygon"]


def validity_reason(poly) -> Optional[str]:
    if poly.is_valid:
        return None
    return explain_validity(poly)


def frame_polygon(lines: list[SourceLine]) -> Optional[Polygon]:
    """Khung tờ: vùng lớn nhất dựng được từ nét Level khung."""
    if not lines:
        return None
    polys, *_ = polygonize_full(unary_union([l.geom for l in lines if l.geom.length > 0]))
    cands = list(polys.geoms) if polys is not None else []
    if not cands:
        return None
    return max(cands, key=lambda p: p.area)
