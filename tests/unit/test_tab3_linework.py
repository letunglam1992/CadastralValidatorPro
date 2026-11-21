"""Golden/regression tests Tab 3 trên dữ liệu TỔNG HỢP (synthetic fixture)."""
import copy

from conftest import codes
from fixtures.builders import X0, Y0, W, grid_elements, replace_text, sheet, without
from cadastral_validator.domain.models import RawElement


def test_valid_sheet(validator):
    res = validator.validate(sheet(grid_elements()))
    assert res.status == "OK", codes(res)
    assert res.stats["so_vung"] == 6
    assert res.count("error") == 0 and res.count("warning") == 0
    assert {p.parcel_no for p in res.parcels} == {"1", "2", "3", "4", "5", "6"}
    assert all(abs(p.area_geom - 400.0) < 1e-6 for p in res.parcels)


def test_precheck_missing_group(validator):
    els = [e for e in grid_elements() if e.level != 4]
    res = validator.validate(sheet(els, "DC99"))
    assert res.status == "DUNG_TIEN_KIEM"
    assert "lớp 2 = 6, lớp 4 = 0, lớp 13 = 6" in res.message
    assert 'Tập tin "DC99.dgn" chưa chuẩn hóa' in res.message
    assert codes(res) == ["THIEU_NHOM_NHAN"]


def test_missing_label(validator):
    res = validator.validate(sheet(without(grid_elements(), "T13_2", "T4_2", "T2_2")))
    assert codes(res, "error") == ["VUNG_KHONG_NHAN"]


def test_duplicate_label(validator):
    els = grid_elements()
    els.append(RawElement(id="DUP", type="text", level=13, text="77", origin=(X0 + 5, Y0 + 5)))
    res = validator.validate(sheet(els))
    assert "TRUNG_NHAN" in codes(res, "error")


def test_label_outside(validator):
    els = grid_elements()
    els.append(RawElement(id="OUT", type="text", level=13, text="99", origin=(X0 - 50, Y0 - 50)))
    res = validator.validate(sheet(els))
    assert codes(res, "error") == ["NHAN_NGOAI_VUNG"]


def test_label_on_boundary(validator):
    els = grid_elements()
    els.append(RawElement(id="EDGE", type="text", level=2, text="CLN", origin=(X0 + W, Y0 + 5)))
    res = validator.validate(sheet(els))
    assert "NHAN_SAT_RANH" in codes(res)


def test_dangle(validator):
    els = grid_elements()
    els.append(RawElement(id="SPUR", type="line", level=10, coords=[(X0 + 10, Y0 + 20), (X0 + 10, Y0 + 25)]))
    res = validator.validate(sheet(els))
    d = [i for i in res.issues if i.code == "DAU_MUT_TREO"]
    assert len(d) == 1
    assert abs(d[0].x - (X0 + 10)) < 1e-6 and abs(d[0].y - (Y0 + 25)) < 1e-6
    assert "SPUR" in d[0].source_element_ids


def test_open_boundary_undershoot_within_snap_is_closed(validator):
    """Đường ranh hụt 5 mm (< snap 10 mm ở 1:1000) vẫn khép vùng; độ dịch được ghi nhận."""
    els = grid_elements()
    for e in els:
        if e.id == "L1":  # đường dọc x = X0+W
            e.coords = [(X0 + W, Y0 + 0.005), e.coords[1]]
    res = validator.validate(sheet(els))
    assert "DAU_MUT_TREO" not in codes(res)
    assert res.stats["max_snap_shift_m"] > 0


def test_open_boundary_gap_beyond_snap(validator):
    els = grid_elements()
    for e in els:
        if e.id == "L1":
            e.coords = [(X0 + W, Y0 + 0.5), e.coords[1]]
    res = validator.validate(sheet(els))
    assert "DAU_MUT_TREO" in codes(res)
    # hai thửa hàng dưới hợp nhất -> một vùng chứa 2 bộ nhãn
    assert "TRUNG_NHAN" in codes(res)


def test_area_delta(validator):
    res = validator.validate(sheet(replace_text(grid_elements(), "T4_3", "412.5")))
    iss = [i for i in res.issues if i.code == "SAI_DIEN_TICH"]
    assert len(iss) == 1 and iss[0].evidence["lech"] == 12.5
    assert "Không tự sửa diện tích pháp lý" in iss[0].message


def test_area_not_number(validator):
    res = validator.validate(sheet(replace_text(grid_elements(), "T4_1", "4OO.0")))
    assert "DIEN_TICH_KHONG_PHAI_SO" in codes(res)


def test_area_decimals(validator):
    res = validator.validate(sheet(replace_text(grid_elements(), "T4_1", "400")))
    assert "SAI_QUY_CACH_LAM_TRON" in codes(res)
    assert "SAI_DIEN_TICH" not in codes(res)


def test_land_code(validator):
    res = validator.validate(sheet(replace_text(grid_elements(), "T2_1", "XYZ")))
    assert codes(res) == ["MA_DAT_KHONG_HOP_LE"]


def test_combined_land_code_ok(validator):
    res = validator.validate(sheet(replace_text(grid_elements(), "T2_1", "ONT+CLN")))
    assert "MA_DAT_KHONG_HOP_LE" not in codes(res)


def test_duplicate_parcel_no(validator):
    res = validator.validate(sheet(replace_text(grid_elements(), "T13_2", "1")))
    assert "TRUNG_SO_THUA" in codes(res, "error")


def test_leading_zero_parcel_no_kept(validator):
    res = validator.validate(sheet(replace_text(grid_elements(), "T13_1", "007")))
    assert "007" in {p.parcel_no for p in res.parcels}


def test_valid_hole(validator):
    """Thửa lọt bên trong thửa khác: polygon ngoài có lỗ, diện tích trừ lỗ."""
    els = grid_elements()
    cx, cy = X0 + W / 2, Y0 + W / 2
    els.append(RawElement(id="INNER", type="shape", level=10, closed=True,
                          coords=[(cx - 4, cy - 9), (cx + 4, cy - 9), (cx + 4, cy - 5), (cx - 4, cy - 5)]))
    els.append(RawElement(id="T13_IN", type="text", level=13, text="50", origin=(cx, cy - 7.5)))
    els.append(RawElement(id="T4_IN", type="text", level=4, text="32.0", origin=(cx - 2, cy - 6.5)))
    els.append(RawElement(id="T2_IN", type="text", level=2, text="ONT", origin=(cx + 2, cy - 6.5)))
    res = validator.validate(sheet(els))
    assert res.stats["so_vung"] == 7
    outer = [p for p in res.parcels if p.parcel_no == "1"][0]
    assert abs(outer.area_geom - 368.0) < 1e-6
    sai = [i for i in res.issues if i.code == "SAI_DIEN_TICH"]
    assert any("Thửa 1:" in i.message for i in sai)  # nhãn 400.0 vs 368 hình học


def test_sliver_unlabeled_small_region(validator):
    els = grid_elements()
    # tạo mảnh vụn 0.5 m x 2 m = 1 m² ở góc thửa 1, có ranh khép kín
    els.append(RawElement(id="SLV", type="linestring", level=10,
                          coords=[(X0, Y0 + 2), (X0 + 0.5, Y0 + 2), (X0 + 0.5, Y0)]))
    res = validator.validate(sheet(els))
    assert "KHE_HO" in codes(res, "error")


def test_road_region_without_parcel_no_is_not_error(validator):
    els = without(grid_elements(), "T13_6", "T4_6")
    els = replace_text(els, "T2_6", "DGT")
    res = validator.validate(sheet(els))
    assert res.count("error") == 0, codes(res)


def test_level_normalization_suggestion_preview_only(validator):
    els = grid_elements()
    els.append(RawElement(id="L11TXT", type="text", level=11, text="LUC", origin=(X0 + 5, Y0 + 35)))
    res = validator.validate(sheet(els))
    s = [i for i in res.issues if i.code == "DE_XUAT_CHUYEN_LEVEL"]
    assert len(s) == 1 and s[0].severity == "info" and s[0].evidence["suggested_level"] == 2


def test_cell_nhanthua_children_are_read(validator):
    els = [e for e in grid_elements() if not (e.id.startswith("T13_1") or e.id.startswith("T4_1"))]
    cx, cy = X0 + W / 2, Y0 + W / 2
    els.append(RawElement(id="C1", type="cell", level=0, cell_name="NHANTHUA", origin=(cx, cy), children=[
        RawElement(id="C1a", type="text", level=13, text="1", origin=(cx, cy + 3)),
        RawElement(id="C1b", type="text", level=4, text="400.0", origin=(cx, cy - 3))]))
    res = validator.validate(sheet(els))
    assert res.status == "OK", codes(res)
    assert any(lb.cell_id == "C1" for lb in res.labels)


def test_crs_unconfirmed_warns(validator):
    res = validator.validate(sheet(grid_elements(), crs_confirmed=False))
    assert "CRS_CHUA_XAC_NHAN" in codes(res, "warning")


def test_axis_swap(validator):
    els = grid_elements()
    for e in els:
        e.coords = [(y, x) for x, y in e.coords]
        if e.origin:
            e.origin = (e.origin[1], e.origin[0])
    res = validator.validate(sheet(els))
    assert "TOA_DO_NGOAI_KHOANG" in codes(res)


def test_outside_frame(validator):
    els = grid_elements()
    for e in els:
        if e.id == "FRAME":
            e.coords = [(X0, Y0), (X0 + 2 * W, Y0), (X0 + 2 * W, Y0 + 2 * W), (X0, Y0 + 2 * W), (X0, Y0)]
    validator_res = validator.validate(sheet(els))
    # cột 3 nằm ngoài khung mới -> vùng ngoài khung bị loại khỏi danh sách vùng, nhãn trở thành ngoài vùng
    assert "NHAN_NGOAI_VUNG" in codes(validator_res) or "THUA_NGOAI_KHUNG" in codes(validator_res)


def test_issue_ids_stable_between_runs(validator):
    els = replace_text(grid_elements(), "T4_3", "412.5")
    a = validator.validate(sheet(copy.deepcopy(els)))
    b = validator.validate(sheet(copy.deepcopy(els)))
    assert [i.issue_id for i in a.issues] == [i.issue_id for i in b.issues]
    assert all(len(i.issue_id) == 12 for i in a.issues)


def test_many_sheets_same_parcel_numbers_independent(validator):
    a = validator.validate(sheet(grid_elements(), "DC1"))
    b = validator.validate(sheet(grid_elements(), "DC2"))
    assert a.status == b.status == "OK"


def test_snap_shift_is_bounded_by_tolerance(validator):
    """Hồi quy DC8 thật: độ dịch snap từng báo 1.403 m do ghép cặp đỉnh sai."""
    els = grid_elements()
    for e in els:
        if e.id == "L1":
            e.coords = [(X0 + W, Y0 + 0.005), (X0 + W, Y0 + 10), (X0 + W, Y0 + 20.004), e.coords[1]]
    res = validator.validate(sheet(els))
    assert 0 < res.stats["max_snap_shift_m"] <= 0.01 + 1e-9


def test_windows_path_basename(tmp_path):
    import json
    from cadastral_validator.adapters.dgn_exchange import load_exchange
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"schema": "cvp.dgn_exchange/1", "source": {"path": "D:\\CVP\\DC8.dgn"},
                             "sheet": {"sheet_id": "DC8.dgn"}, "units": {"master": "m"}, "elements": []}),
                 encoding="utf-8")
    s = load_exchange(p)
    assert s.file_name == "DC8.dgn" and s.sheet_id == "DC8"
