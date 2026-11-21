"""Giới hạn sai diện tích thửa đất — Phụ lục số 04 Thông tư 26/2024/TT-BTNMT (căn cứ khoản 5 Điều 8).

Nguồn: tệp người dùng cung cấp "26_2024_TT-BTNMT_637676.docx" (21/11/2026). CHƯA đối chiếu
sửa đổi của TT 23/2025/TT-BNNMT đối với Phụ lục 04.

Cách tính: mỗi khoảng (S0, S1] có hạn sai = hạn sai tại S0 + (S − S0)/10 × mức tăng; hạn sai tại
cận dưới của khoảng sau = hạn sai tại cận trên khoảng trước. Chú thích (*): "nội suy đến 01 m²"
⇒ S được lấy đến 1 m² (làm tròn xuống) trước khi nội suy.

Lưu ý văn bản (đã báo người dùng): dòng "50 < S ≤ 300" của tỷ lệ 1:5.000 và 1:10.000 ghi
"so với hạn sai của thửa đất 40 m²" trong khi dòng trên là "S ≤ 50 ... ≤ 0,5 m²". Phần mềm
lấy mốc 50 m² (liên tục với dòng trên) — cần người dùng xác nhận.

Phạm vi theo văn bản: so sánh diện tích trên bản đồ số với diện tích đo trực tiếp tại thực địa.
Áp dụng cho so sánh "diện tích nhãn — diện tích hình học" là vận dụng theo yêu cầu người dùng.
"""
from __future__ import annotations

import math

# scale -> (S_base, tol_base, [(S_upper, rate_per_10m2), ...])  — S_upper None = không giới hạn
PL04: dict[str, tuple[float, float, list[tuple[float | None, float]]]] = {
    "1:200":   (30, 0.23, [(100, 0.07), (300, 0.05), (500, 0.04), (1000, 0.03), (2000, 0.02), (None, 0.01)]),
    "1:500":   (30, 0.25, [(100, 0.08), (300, 0.05), (500, 0.04), (1000, 0.03), (2000, 0.02), (None, 0.01)]),
    "1:1000":  (40, 0.35, [(300, 0.08), (1000, 0.05), (2000, 0.04), (5000, 0.03), (10000, 0.02), (None, 0.01)]),
    "1:2000":  (40, 0.40, [(300, 0.09), (1000, 0.05), (2000, 0.04), (5000, 0.03), (10000, 0.02), (None, 0.01)]),
    "1:5000":  (50, 0.50, [(300, 0.09), (1000, 0.05), (2000, 0.04), (5000, 0.03), (10000, 0.02), (None, 0.01)]),
    "1:10000": (50, 0.50, [(300, 0.09), (1000, 0.06), (2000, 0.05), (5000, 0.04), (10000, 0.03), (None, 0.02)]),
}
LEGAL_REF = {"document_id": "TT26_2024", "article": "Điều 8", "clause": "khoản 5", "appendix": "Phụ lục số 04"}


def area_tolerance_tt26(scale: str, area_m2: float) -> float:
    if scale not in PL04:
        raise KeyError(f"Phụ lục 04 TT 26/2024 không có tỷ lệ {scale}")
    s0, tol, bands = PL04[scale]
    s = math.floor(area_m2)          # nội suy đến 01 m²
    if s <= s0:
        return tol
    lo = s0
    for hi, rate in bands:
        top = s if hi is None else min(s, hi)
        tol += (top - lo) / 10.0 * rate
        if hi is None or s <= hi:
            break
        lo = hi
    return round(tol, 4)
