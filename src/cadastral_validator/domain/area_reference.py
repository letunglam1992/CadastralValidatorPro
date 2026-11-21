"""Quy đổi diện tích hình học (mặt phẳng chiếu VN-2000) sang mặt so sánh của nhãn.

- "grid": diện tích trên mặt phẳng chiếu (shapely .area).
- "ellipsoid": diện tích trắc địa trên ellipsoid (pyproj.Geod) sau khi chuyển ngược phép chiếu TM.
- "ground": ellipsoid × (1 + h/R)², h = độ cao trung bình người dùng nhập. Thiếu h ⇒ không quy đổi được.

Phép chiếu ngược chỉ dùng tham số TM (lon_0, k, x_0, y_0, ellps) — không cần towgs84 vì diện tích
tính trên cùng ellipsoid của VN-2000 (kích thước WGS-84).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

R_EARTH = 6_371_000.0


@lru_cache(maxsize=8)
def _tools(lon0: float, k0: float, x0: float, y0: float):
    from pyproj import Geod, Transformer
    t = Transformer.from_crs(
        f"+proj=tmerc +lat_0=0 +lon_0={lon0} +k={k0} +x_0={x0} +y_0={y0} +ellps=WGS84 +units=m +no_defs",
        "+proj=longlat +ellps=WGS84 +no_defs", always_xy=True)
    return t, Geod(ellps="WGS84")


def ellipsoid_area(poly, crs: dict) -> float:
    t, g = _tools(float(crs["central_meridian_deg"]), float(crs["scale_factor"]),
                  float(crs["false_easting_m"]), float(crs["false_northing_m"]))
    polys = [poly] if poly.geom_type == "Polygon" else list(getattr(poly, "geoms", []))
    total = 0.0
    for p in polys:
        for i, ring in enumerate([p.exterior, *p.interiors]):
            xs, ys = zip(*ring.coords)
            lon, lat = t.transform(xs, ys)
            a = abs(g.polygon_area_perimeter(lon, lat)[0])
            total += a if i == 0 else -a
    return total


def compare_area(poly, mode: str, crs: Optional[dict], mean_height_m: Optional[float]) -> tuple[float, str]:
    """Trả (diện tích để so với nhãn, ghi chú). Không đủ điều kiện ⇒ trả diện tích lưới + lý do."""
    if mode == "grid" or crs is None:
        return poly.area, "mặt phẳng chiếu" if mode == "grid" else "mặt phẳng chiếu (thiếu CRS để quy đổi)"
    a = ellipsoid_area(poly, crs)
    if mode == "ellipsoid":
        return a, "ellipsoid"
    if mode == "ground":
        if mean_height_m is None:
            return a, "ellipsoid (thiếu độ cao trung bình để quy về mặt đất)"
        return a * (1 + mean_height_m / R_EARTH) ** 2, f"mặt đất, h={mean_height_m:g} m"
    raise ValueError(f"area_reference '{mode}' không hợp lệ (grid|ellipsoid|ground)")
