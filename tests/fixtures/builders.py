"""Bộ dựng dữ liệu TỔNG HỢP (synthetic fixture) — KHÔNG phải dữ liệu thực.

Lưới 3 cột x 2 hàng thửa 20 m x 20 m (400 m²) tại vùng tọa độ VN-2000 giả định.
"""
from __future__ import annotations

import copy

from cadastral_validator.domain.models import MapSheet, RawElement, SourceInfo

X0, Y0 = 520000.0, 2350000.0
W = 20.0


def _seg(i, a, b, level=10):
    return RawElement(id=f"L{i}", type="line", level=level, coords=[a, b])


def grid_elements(cols=3, rows=2, with_labels=True, area_text="400.0", land="ONT"):
    els = []
    n = 0
    for c in range(cols + 1):
        x = X0 + c * W
        els.append(_seg(n, (x, Y0), (x, Y0 + rows * W))); n += 1
    for r in range(rows + 1):
        y = Y0 + r * W
        els.append(_seg(n, (X0, y), (X0 + cols * W, y))); n += 1
    # khung tờ level 54 trùng biên ngoài
    els.append(RawElement(id="FRAME", type="shape", level=54, closed=True,
                          coords=[(X0, Y0), (X0 + cols * W, Y0), (X0 + cols * W, Y0 + rows * W), (X0, Y0 + rows * W),
                                  (X0, Y0)]))
    if with_labels:
        k = 1
        for r in range(rows):
            for c in range(cols):
                cx, cy = X0 + c * W + W / 2, Y0 + r * W + W / 2
                els.append(RawElement(id=f"T13_{k}", type="text", level=13, text=str(k), origin=(cx, cy + 3)))
                els.append(RawElement(id=f"T4_{k}", type="text", level=4, text=area_text, origin=(cx, cy - 3)))
                els.append(RawElement(id=f"T2_{k}", type="text", level=2, text=land, origin=(cx, cy)))
                k += 1
    return els


def sheet(elements, sheet_id="DC_TEST", scale="1:1000", crs_confirmed=True):
    return MapSheet(sheet_id=sheet_id, file_name=f"{sheet_id}.dgn", elements=elements, scale=scale,
                    source=SourceInfo(path=f"synthetic://{sheet_id}", reader="synthetic_fixture", is_synthetic=True),
                    crs_profile_id="VN2000_TM3_104", crs_confirmed=crs_confirmed)


def without(elements, *ids):
    return [copy.deepcopy(e) for e in elements if e.id not in ids]


def replace_text(elements, el_id, text):
    out = copy.deepcopy(elements)
    for e in out:
        if e.id == el_id:
            e.text = text
    return out
