"""Tích hợp: exchange JSON -> kiểm tra -> Excel/CSV/GeoJSON/HTML; số lượng nhất quán."""
import json
import os
from pathlib import Path

import pytest
from openpyxl import load_workbook

from fixtures.builders import grid_elements, replace_text, sheet
from cadastral_validator.adapters.dgn_exchange import load_exchange, save_exchange
from cadastral_validator.adapters.dgn_probe import detect_version, probe_dgn
from cadastral_validator.application.check_service import CheckOptions, run_check

REAL_DGN_DIR = Path(os.environ.get("CVP_REAL_DGN_DIR", "/mnt/user-data/uploads/Liem/file DGN"))


@pytest.fixture()
def exchange_dir(tmp_path):
    d = tmp_path / "in"
    d.mkdir()
    save_exchange(sheet(grid_elements(), "DC1"), d / "DC1.json")
    save_exchange(sheet(replace_text(grid_elements(), "T4_3", "412.5"), "DC2"), d / "DC2.json")
    save_exchange(sheet([e for e in grid_elements() if e.level != 13], "DC3"), d / "DC3.json")
    (d / "HONG.json").write_text("{not json", encoding="utf-8")
    return d


def test_exchange_roundtrip(tmp_path):
    s = sheet(grid_elements(), "RT")
    save_exchange(s, tmp_path / "rt.json")
    s2 = load_exchange(tmp_path / "rt.json")
    assert len(s2.elements) == len(s.elements)
    assert s2.source.is_synthetic is True
    assert [e.text for e in s2.elements] == [e.text for e in s.elements]


def test_full_pipeline(exchange_dir, tmp_path):
    out = tmp_path / "out"
    before = {p.name: p.read_bytes() for p in exchange_dir.iterdir()}
    results, info = run_check(CheckOptions(inputs=[exchange_dir], out_dir=out, crs_profile_id="VN2000_TM3_104",
                                           crs_confirmed=True))
    st = {r.sheet_id: r.status for r in results}
    assert st == {"DC1": "OK", "DC2": "CAN_XEM", "DC3": "DUNG_TIEN_KIEM", "HONG": "KHONG_DOC_DUOC"}
    # nguồn không bị thay đổi
    assert {p.name: p.read_bytes() for p in exchange_dir.iterdir()} == before

    total = sum(len(r.issues) for r in results)
    wb = load_workbook(info["paths"]["xlsx"])
    assert wb["ChiTietLoi"].max_row - 1 == total
    with open(info["paths"]["csv"], encoding="utf-8-sig") as f:
        assert sum(1 for _ in f) - 1 == total
    data = json.loads(Path(info["paths"]["json"]).read_text(encoding="utf-8"))
    assert sum(len(s["issues"]) for s in data["sheets"]) == total
    assert "LANDINFO" in data["disclaimer"]
    gj = json.loads(Path(info["paths"]["geojson"]).read_text(encoding="utf-8"))
    assert len(gj["features"]) == sum(1 for r in results for i in r.issues if i.x is not None)

    html = Path(info["paths"]["html:DC2"]).read_text(encoding="utf-8")
    assert "SAI_DIEN_TICH" in html
    assert "http://" not in html.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in html


def test_clean_ole_string_regression():
    """Hồi quy: metadata DGN thật chứa rác sau NUL làm openpyxl báo IllegalCharacterError."""
    from cadastral_validator.adapters.dgn_probe import clean_ole_string
    assert clean_ole_string(b"MicroStation v8.11.9.832\x00\x00\x1f\x00Admin") == "MicroStation v8.11.9.832"
    assert clean_ole_string("MicroStation v8.11.9.357   ") == "MicroStation v8.11.9.357"
    assert clean_ole_string(None) is None


def test_detect_version_magic():
    assert detect_version(bytes.fromhex("d0cf11e0a1b11ae1")) == "V8"
    assert detect_version(b"\x08\x09\xfe\x02") == "V7"
    assert detect_version(b"PK\x03\x04") == "UNKNOWN"


@pytest.mark.skipif(not REAL_DGN_DIR.exists(), reason="Không có DGN thật trên máy này (dữ liệu không đưa lên repo)")
def test_real_dgn_probe_is_v8_and_reader_blocked_without_com(tmp_path):
    files = sorted(REAL_DGN_DIR.glob("*.dgn"))
    assert files
    for p in files:
        before = probe_dgn(p).sha256
        prof = probe_dgn(p)
        assert prof.version == "V8"
        assert prof.zlib_ok is True
        assert prof.sha256 == before
    results, _ = run_check(CheckOptions(inputs=files[:1], out_dir=tmp_path, html=False))
    assert results[0].status == "KHONG_DOC_DUOC"
    assert "Windows" in results[0].message or "pywin32" in results[0].message or "ProgID" in results[0].message
