import json
from decimal import Decimal

import pytest

from cadastral_validator.domain.rules import RulePackError, load_rulepack
from cadastral_validator.domain.textparse import (count_decimals, parse_area, round_half_up, split_fraction_label,
                                                  validate_land_code)
from cadastral_validator.infrastructure.config import CONFIG_DIR


def test_parse_area_dot_locale():
    assert parse_area("1342.3") == Decimal("1342.3")
    assert parse_area("1.234") == Decimal("1.234")          # không tự đảo nghĩa
    assert parse_area("1,234") is None                         # dấu phẩy không hợp lệ ở locale '.'
    assert parse_area("abc") is None and parse_area("") is None


def test_parse_area_comma_locale_with_thousands():
    assert parse_area("1.234,5", decimal_sep=",", thousands_sep=".") == Decimal("1234.5")
    assert parse_area("12.34,5", decimal_sep=",", thousands_sep=".") is None
    assert parse_area("874,6", decimal_sep=",") == Decimal("874.6")


def test_decimals_and_rounding():
    assert count_decimals("400.0") == 1 and count_decimals("400") == 0
    assert round_half_up(2.25, 1) == Decimal("2.3")
    assert round_half_up(399.95, 1) == Decimal("400.0")


def test_land_codes():
    codes = {"ONT", "CLN", "BHK"}
    assert validate_land_code("ONT+CLN", codes) == (True, [])
    assert validate_land_code("ONT+XYZ", codes) == (False, ["XYZ"])
    assert validate_land_code("ONT+CLN", codes, allow_combined=False)[0] is False


def test_fraction_label():
    assert split_fraction_label("125/874.6") == ("125", "874.6")
    assert split_fraction_label("ONT/1") is None


def test_vietnamese_unicode_normalization():
    from cadastral_validator.domain.textparse import normalize_text
    decomposed = "Đất ở tại nông thôn".encode("utf-8").decode("utf-8")
    import unicodedata
    nfd = unicodedata.normalize("NFD", decomposed)
    assert normalize_text(nfd) == unicodedata.normalize("NFC", decomposed)


def test_rulepack_loads_and_all_rules_pending():
    p = load_rulepack(CONFIG_DIR / "rulepacks" / "son_la_draft.json")
    assert p.approval_status == "DRAFT"
    assert all(r.verification_status == "PENDING_VERIFICATION" for c, r in p.rules.items() if c != "SAI_DIEN_TICH")
    assert p.rule("SAI_DIEN_TICH").verification_status == "VERIFIED_PARTIAL"
    assert p.rule("SAI_DIEN_TICH").legal_refs[0]["appendix"] == "Phụ lục số 04"
    assert not any(r.can_auto_fix for r in p.rules.values())
    assert p.params_for_scale("1:1000")["snap_tolerance_m"] == 0.01


def _write(tmp_path, mutate):
    d = json.loads((CONFIG_DIR / "rulepacks" / "son_la_draft.json").read_text(encoding="utf-8"))
    mutate(d)
    f = tmp_path / "rp.json"
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return f


def test_rulepack_rejects_legal_rule_without_basis(tmp_path):
    def m(d):
        d["rules"][0]["classification"] = "LEGAL_REQUIREMENT"
    with pytest.raises(RulePackError, match="LEGAL_REQUIREMENT"):
        load_rulepack(_write(tmp_path, m))


def test_rulepack_rejects_autofix_unverified(tmp_path):
    def m(d):
        d["rules"][0]["auto_fix_policy"] = "AUTO_SAFE_WITH_PREVIEW"
    with pytest.raises(RulePackError, match="auto-fix"):
        load_rulepack(_write(tmp_path, m))


def test_rulepack_reports_missing_field(tmp_path):
    def m(d):
        del d["rules"][2]["severity"]
    with pytest.raises(RulePackError, match=r"rules\[2\].*severity"):
        load_rulepack(_write(tmp_path, m))


def test_unknown_scale_is_error():
    p = load_rulepack(CONFIG_DIR / "rulepacks" / "son_la_draft.json")
    with pytest.raises(RulePackError):
        p.params_for_scale("1:750")
