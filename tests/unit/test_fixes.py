"""Tab 2 — đề xuất sửa đầu mút treo, mô phỏng tác động, xuất ChangeSet (dữ liệu TỔNG HỢP)."""
import copy
import hashlib

import pytest

from fixtures.builders import X0, Y0, W, grid_elements, sheet
from cadastral_validator.adapters.dgn_exchange import save_exchange
from cadastral_validator.application.check_service import CheckOptions
from cadastral_validator.application.fix_service import analyze, build_macro, export, simulate
from cadastral_validator.domain.models import RawElement


def _variant(kind):
    els = copy.deepcopy(grid_elements())
    for e in els:
        if e.id == "L1":   # đường dọc x = X0+W, từ Y0 đến Y0+2W
            if kind == "under":
                e.coords = [(X0 + W, Y0 + 0.4), e.coords[1]]         # hụt 0,4 m ở đáy
            elif kind == "over":
                e.coords = [(X0 + W, Y0 - 0.3), e.coords[1]]         # thò 0,3 m qua biên đáy
            elif kind == "far":
                e.coords = [(X0 + W, Y0 + 3.0), e.coords[1]]         # hở 3 m
    return els


def _session(tmp_path, kind, max_gap=1.0):
    p = tmp_path / f"{kind}.json"
    save_exchange(sheet(_variant(kind), f"DC_{kind}"), p)
    return analyze(p, CheckOptions(inputs=[p], out_dir=tmp_path / "o", crs_profile_id="VN2000_TM3_104",
                                   crs_confirmed=True), max_gap)


def test_undershoot_extend(tmp_path):
    s = _session(tmp_path, "under")
    assert len(s.proposals) == 1
    f = s.proposals[0]
    assert f.action == "EXTEND" and f.element_id == "L1" and f.vertex_index == 0
    assert f.after == pytest.approx((X0 + W, Y0)) and f.gap_m == pytest.approx(0.4)


def test_overshoot_trim(tmp_path):
    s = _session(tmp_path, "over")
    f = [p for p in s.proposals if p.element_id == "L1"][0]
    assert f.action == "TRIM" and f.after == pytest.approx((X0 + W, Y0)) and f.gap_m == pytest.approx(0.3)


def test_gap_beyond_threshold_not_proposed(tmp_path):
    s = _session(tmp_path, "far", max_gap=1.0)
    assert s.proposals == []
    assert s.skipped and "1.0 m" in s.skipped[0]["reason"]


def test_simulate_impact_closes_regions(tmp_path):
    s = _session(tmp_path, "under")
    assert s.before.stats["dau_mut_treo"] == 1
    for p in s.proposals:
        p.approved = True
    after, impact = simulate(s)
    assert after.stats["dau_mut_treo"] == 0 and after.stats["so_vung"] == 6
    assert impact["sau"]["loi"] == 0 and impact["loi_moi_phat_sinh"] == {}


def test_unapproved_not_applied(tmp_path):
    s = _session(tmp_path, "under")
    after, impact = simulate(s)
    assert after.stats["dau_mut_treo"] == 1 and impact["so_de_xuat_duyet"] == 0


def test_export_requires_approval(tmp_path):
    s = _session(tmp_path, "under")
    with pytest.raises(ValueError):
        export(s, tmp_path / "cs")


def test_export_copy_and_macros(tmp_path):
    # nguồn là .dgn (giả) + tệp xuất sẵn cạnh -> xuất bản sao DGN, gốc không đổi
    import os
    import time
    dgn = tmp_path / "DC7.dgn"
    dgn.write_bytes(bytes.fromhex("d0cf11e0a1b11ae1") + b"dulieu" * 50)
    old = time.time() - 100
    os.utime(dgn, (old, old))
    save_exchange(sheet(_variant("under"), "DC7"), tmp_path / "DC7.dgn.cvp.json")
    h0 = hashlib.sha256(dgn.read_bytes()).hexdigest()
    s = analyze(dgn, CheckOptions(inputs=[dgn], out_dir=tmp_path / "o", crs_profile_id="VN2000_TM3_104",
                                  crs_confirmed=True))
    for p in s.proposals:
        p.approved = True
    cs = export(s, tmp_path / "cs")
    assert hashlib.sha256(dgn.read_bytes()).hexdigest() == h0
    from pathlib import Path
    copy_path = Path(cs.outputs["ban_sao_dgn"])
    assert "_BANSAO_" in copy_path.name and copy_path.read_bytes() == dgn.read_bytes()
    ap = Path(cs.outputs["macro_ap_dung"]).read_bytes().decode("ascii")
    ht = Path(cs.outputs["macro_hoan_tac"]).read_bytes().decode("ascii")
    assert '"_BANSAO"' in ap and "\r\n" in ap and 'Sua "L1", 0' in ap
    # hoàn tác đảo trước/sau
    f = cs.fixes[0]
    assert f"{f.after[0]:.6f}, {f.after[1]:.6f}, {f.before[0]:.6f}, {f.before[1]:.6f}" in ht
    assert cs.impact["sau"]["dau_mut_treo"] == 0
    assert Path(cs.outputs["changeset_json"]).exists() and Path(cs.outputs["excel"]).exists()


def test_join_two_facing_dangles(tmp_path):
    """Hồi quy DC2: hai đầu treo đối diện -> 1 đề xuất JOIN (không đổi chỗ cho nhau)."""
    els = copy.deepcopy(grid_elements())
    for e in els:
        if e.id == "L1":    # tách đường dọc x=X0+W thành 2 đoạn hở 0,6 m ở giữa hàng dưới
            e.coords = [(X0 + W, Y0), (X0 + W, Y0 + 10.0)]
    els.append(RawElement(id="L1b", type="line", level=10, coords=[(X0 + W, Y0 + 10.6), (X0 + W, Y0 + 2 * W)]))
    p = tmp_path / "j.json"
    save_exchange(sheet(els, "DC_J"), p)
    s = analyze(p, CheckOptions(inputs=[p], out_dir=tmp_path / "o", crs_profile_id="VN2000_TM3_104",
                                crs_confirmed=True))
    assert s.before.stats["dau_mut_treo"] == 2
    assert len(s.proposals) == 1 and s.proposals[0].action == "JOIN"
    s.proposals[0].approved = True
    after, imp = simulate(s)
    assert after.stats["dau_mut_treo"] == 0 and after.stats["so_vung"] == 6


def test_evaluate_each(tmp_path):
    from cadastral_validator.application.fix_service import evaluate_each
    s = _session(tmp_path, "under")
    ev = evaluate_each(s)
    f = s.proposals[0]
    assert ev[f.fix_id]["giam_dau_mut_treo"] == 1 and ev[f.fix_id]["loi_moi"] == {}


def test_short_isolated_stroke_not_snapped(tmp_path):
    """Hồi quy DC2: nét rời ngắn (~0,7 m) treo cả hai đầu gần ranh -> không đề xuất nối."""
    els = copy.deepcopy(grid_elements())
    els.append(RawElement(id="TICK", type="line", level=10, coords=[(X0 + 5, Y0 + 0.3), (X0 + 5.5, Y0 + 0.8)]))
    p = tmp_path / "t.json"
    save_exchange(sheet(els, "DC_T"), p)
    s = analyze(p, CheckOptions(inputs=[p], out_dir=tmp_path / "o", crs_profile_id="VN2000_TM3_104",
                                crs_confirmed=True))
    assert s.proposals == []
    assert any("nét rời ngắn" in k["reason"] for k in s.skipped)
