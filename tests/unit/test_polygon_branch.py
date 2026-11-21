"""Nhánh polygon (GML/SHP): overlap, gap chỉ khi có coverage, polygon không hợp lệ."""
from shapely.geometry import Polygon, box

from conftest import codes
from fixtures.builders import X0, Y0
from cadastral_validator.domain.models import MapSheet, PolygonFeature, SourceInfo


def _sheet(feats, coverage=None):
    return MapSheet(sheet_id="GML1", file_name="GML1.gml", elements=[], features=feats, coverage=coverage,
                    source=SourceInfo(path="synthetic://gml", is_synthetic=True), crs_profile_id="VN2000_TM3_104",
                    crs_confirmed=True)


def f(i, geom, area=None):
    return PolygonFeature(str(i), geom, parcel_no=str(i), area_label=area or f"{geom.area:.1f}", land_type="CLN")


def test_clean_polygons(validator):
    a = box(X0, Y0, X0 + 20, Y0 + 20)
    b = box(X0 + 20, Y0, X0 + 40, Y0 + 20)
    res = validator.validate(_sheet([f(1, a), f(2, b)], coverage=box(X0, Y0, X0 + 40, Y0 + 20)))
    assert res.status == "OK", codes(res)


def test_overlap(validator):
    a = box(X0, Y0, X0 + 20, Y0 + 20)
    b = box(X0 + 19.5, Y0, X0 + 40, Y0 + 20)
    res = validator.validate(_sheet([f(1, a), f(2, b)]))
    ov = [i for i in res.issues if i.code == "CHONG_LAN"]
    assert len(ov) == 1 and abs(ov[0].evidence["area_m2"] - 10.0) < 1e-6
    assert "Không tự cắt" in ov[0].message


def test_gap_not_evaluated_without_coverage(validator):
    a = box(X0, Y0, X0 + 20, Y0 + 20)
    b = box(X0 + 20.2, Y0, X0 + 40, Y0 + 20)
    res = validator.validate(_sheet([f(1, a), f(2, b)]))
    assert "KHE_HO" not in codes(res)
    assert res.stats["gap_check"].startswith("NOT_EVALUATED")


def test_gap_with_coverage(validator):
    a = box(X0, Y0, X0 + 20, Y0 + 20)
    b = box(X0 + 20.2, Y0, X0 + 40, Y0 + 20)
    res = validator.validate(_sheet([f(1, a), f(2, b)], coverage=box(X0, Y0, X0 + 40, Y0 + 20)))
    g = [i for i in res.issues if i.code == "KHE_HO"]
    assert len(g) == 1 and abs(g[0].evidence["area_m2"] - 4.0) < 1e-6


def test_invalid_polygon(validator):
    bow = Polygon([(X0, Y0), (X0 + 10, Y0 + 10), (X0 + 10, Y0), (X0, Y0 + 10)])
    res = validator.validate(_sheet([f(1, bow, "50.0"), f(2, box(X0 + 30, Y0, X0 + 40, Y0 + 10))]))
    assert "HINH_HOC_KHONG_HOP_LE" in codes(res, "error")


def test_small_parcel(validator):
    res = validator.validate(_sheet([f(1, box(X0, Y0, X0 + 1, Y0 + 1))]))
    assert "THUA_NHO" in codes(res)
