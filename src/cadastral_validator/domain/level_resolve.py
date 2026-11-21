"""Phân giải Level theo TÊN (ưu tiên) hoặc SỐ cho từng tờ.

Thực tế DC8: Level không mang số 2/4/13 mà có tên 'L', 'TCT', 'DIENTICH3', 'C', 'KG-5000'.
Khi hồ sơ Level khai báo `level_names`, số Level cấu hình cho vai trò đó bị bỏ qua và
số được suy ra từ: (1) tên Level gắn trên phần tử (macro mới xuất `level_name`),
(2) bảng `levels` trong tệp trao đổi, (3) `name_to_number_fallback` (ghi rõ nguồn).
"""
from __future__ import annotations

import copy

from ..infrastructure.config import LevelProfile
from .models import MapSheet

ROLES = ("boundary", "frame", "parcel_no", "area", "land_type")


def _attr(role: str) -> str:
    return {"boundary": "boundary_levels", "frame": "frame_levels", "parcel_no": "parcel_no_levels",
            "area": "area_levels", "land_type": "land_type_levels"}[role]


def resolve_levels(lv: LevelProfile, sheet: MapSheet) -> tuple[LevelProfile, dict]:
    if not lv.role_names:
        return lv, {"mode": "number"}
    name_to_num: dict[str, set[int]] = {}
    source = {}

    def add(name, num, src):
        name_to_num.setdefault(name, set()).add(int(num))
        source.setdefault(name, src)

    def walk(els):
        for e in els:
            n = e.extra.get("level_name")
            if n is not None:
                add(str(n), e.level, "element.level_name")
            walk(e.children)
    walk(sheet.elements)
    for row in sheet.level_table:
        if "name" in row and "number" in row:
            add(str(row["name"]), row["number"], "exchange.levels")
    for n, num in lv.name_to_number_fallback.items():
        if n not in name_to_num:
            add(n, num, "profile.name_to_number_fallback")
    out = copy.deepcopy(lv)
    info = {"mode": "name", "resolved": {}, "missing": []}
    for role, names in lv.role_names.items():
        nums = set()
        for n in names:
            if n in name_to_num:
                nums |= name_to_num[n]
                info["resolved"][n] = {"role": role, "numbers": sorted(name_to_num[n]), "source": source[n]}
        if not nums:   # chỉ báo thiếu khi CẢ vai trò không tìm được tên nào (vd ranh khai báo "L" hoặc "THUA")
            info["missing"].append(f"{role}: {' / '.join(sorted(names))}")
        setattr(out, _attr(role), nums)
    return out, info


def auto_mean_height(sheet: MapSheet, level_names: set[str]) -> tuple[float | None, int]:
    """Trung vị nhãn độ cao (số) trên các Level có tên trong level_names (vd DO-CAO)."""
    import statistics
    vals = []

    def walk(els):
        for e in els:
            if e.type == "text" and e.extra.get("level_name") in level_names and e.text:
                t = e.text.strip().replace(",", ".")
                try:
                    v = float(t)
                    if -500 < v < 9000:
                        vals.append(v)
                except ValueError:
                    pass
            walk(e.children)
    walk(sheet.elements)
    return (statistics.median(vals) if vals else None), len(vals)
