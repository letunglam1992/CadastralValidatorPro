"""Phân tích chuỗi nhãn: số thửa, diện tích, mã loại đất.

Nguyên tắc (Master Prompt V.7): số thửa là chuỗi, giữ số 0 đầu; diện tích đọc theo
locale cấu hình, KHÔNG tự đảo nghĩa '1.234'.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional


def normalize_text(s: str) -> str:
    """Chuẩn hóa Unicode NFC, gộp khoảng trắng; giữ nguyên ký tự gốc khác."""
    s = unicodedata.normalize("NFC", s or "")
    return re.sub(r"\s+", " ", s).strip()


def parse_area(text: str, decimal_sep: str = ".", thousands_sep: Optional[str] = None) -> Optional[Decimal]:
    """Trả về Decimal hoặc None nếu không hợp lệ. Không đoán locale."""
    t = normalize_text(text).replace(" ", "")
    if not t:
        return None
    if thousands_sep:
        parts = t.split(decimal_sep)
        if len(parts) > 2:
            return None
        intpart = parts[0]
        if thousands_sep in intpart:
            groups = intpart.split(thousands_sep)
            if not groups[0] or len(groups[0]) > 3 or any(len(g) != 3 for g in groups[1:]):
                return None
            intpart = "".join(groups)
        t = intpart + ("." + parts[1] if len(parts) == 2 else "")
    else:
        if decimal_sep != ".":
            if "." in t:
                return None
            t = t.replace(decimal_sep, ".")
    if not re.fullmatch(r"[0-9]+(\.[0-9]+)?", t):
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def count_decimals(text: str, decimal_sep: str = ".") -> int:
    t = normalize_text(text)
    if decimal_sep not in t:
        return 0
    return len(t.rsplit(decimal_sep, 1)[1])


def round_half_up(value: float, places: int) -> Decimal:
    q = Decimal(1).scaleb(-places)
    return Decimal(repr(value)).quantize(q, rounding=ROUND_HALF_UP)


def split_land_codes(text: str, sep: str = "+") -> list[str]:
    return [p.strip().upper() for p in normalize_text(text).split(sep) if p.strip()]


def validate_land_code(text: str, valid_codes: set[str], allow_combined: bool = True, sep: str = "+") -> tuple[bool, list[str]]:
    """Trả (hợp lệ, danh sách mã không thuộc danh mục)."""
    parts = split_land_codes(text, sep)
    if not parts:
        return False, [text]
    if len(parts) > 1 and not allow_combined:
        return False, parts
    bad = [p for p in parts if p not in valid_codes]
    return (not bad), bad


def split_fraction_label(text: str) -> Optional[tuple[str, str]]:
    """Nhãn dạng phân số 'số thửa/diện tích' hoặc 'số thửa\\ndiện tích' (Cell NHANTHUA).

    Chỉ tách khi đúng 2 phần và phần sau là số; ngược lại trả None (không đoán).
    """
    t = normalize_text(text)
    for sep in ("/", "\n"):
        if sep in text:
            a, *rest = [p.strip() for p in text.split(sep)]
            if len(rest) == 1 and re.fullmatch(r"[0-9]{1,5}[a-zA-Z]?", a) and re.fullmatch(r"[0-9.,]+", rest[0]):
                return a, rest[0]
    _ = t
    return None
