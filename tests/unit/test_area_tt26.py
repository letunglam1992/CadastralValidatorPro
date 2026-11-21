"""Phụ lục 04 TT 26/2024 — giới hạn sai diện tích; quy đổi mặt so sánh diện tích."""
import pytest
from shapely.geometry import box

from cadastral_validator.domain.area_reference import compare_area
from cadastral_validator.domain.area_tolerance import area_tolerance_tt26


@pytest.mark.parametrize("scale,S,expected", [
    ("1:1000", 40, 0.35),
    ("1:1000", 30, 0.35),
    ("1:1000", 300, 0.35 + 26 * 0.08),                 # 2,43
    ("1:1000", 400, 0.35 + 26 * 0.08 + 10 * 0.05),     # 2,93
    ("1:1000", 400.9, 0.35 + 26 * 0.08 + 10 * 0.05),   # nội suy đến 01 m² (làm tròn xuống)
    ("1:5000", 50, 0.5),
    ("1:5000", 1537.8, 0.5 + 25 * 0.09 + 70 * 0.05 + 53.7 * 0.04),
    ("1:5000", 178612.0, 0.5 + 25*0.09 + 70*0.05 + 100*0.04 + 300*0.03 + 500*0.02 + 16861.2*0.01),
    ("1:200", 100, 0.23 + 7 * 0.07),
    ("1:10000", 1000, 0.5 + 25 * 0.09 + 70 * 0.06),
])
def test_pl04(scale, S, expected):
    assert area_tolerance_tt26(scale, S) == pytest.approx(expected, abs=1e-3)


def test_pl04_unknown_scale():
    with pytest.raises(KeyError):
        area_tolerance_tt26("1:750", 100)


CRS = {"central_meridian_deg": 104.0, "scale_factor": 0.9999, "false_easting_m": 500000.0, "false_northing_m": 0.0}


def test_area_reference_modes():
    p = box(568000, 2302000, 568100, 2302100)          # 10.000 m² trên mặt phẳng chiếu, cách KTT ~68 km
    g, _ = compare_area(p, "grid", CRS, None)
    e, _ = compare_area(p, "ellipsoid", CRS, None)
    gr, note = compare_area(p, "ground", CRS, 900)
    assert g == pytest.approx(10000)
    assert 1.00007 < e / g < 1.0001                     # 1/k² với k ≈ 0,99995683
    assert gr / e == pytest.approx((1 + 900 / 6371000) ** 2)
    assert "h=900" in note
    e2, note2 = compare_area(p, "ground", CRS, None)
    assert e2 == pytest.approx(e) and "thiếu độ cao" in note2
