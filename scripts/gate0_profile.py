"""Gate 0 — lập data_profile.xlsx từ thư mục DGN (không cần MicroStation).

python scripts/gate0_profile.py "<thư mục DGN>" docs/gate0/data_profile.xlsx
Chỉ ghi metadata (tên tệp, kích thước, SHA-256, phiên bản, ứng dụng tạo) — không ghi nội dung bản đồ.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Font  # noqa: E402

from cadastral_validator.adapters.dgn_probe import probe_dgn  # noqa: E402


def main(src: str, out: str):
    files = sorted(Path(src).rglob("*.dgn"))
    wb = Workbook()
    ws = wb.active
    ws.title = "DGN"
    cols = ["Tệp", "Kích thước (byte)", "SHA-256", "Phiên bản", "Ứng dụng tạo", "Số model", "Luồng đồ họa",
            "Byte luồng đồ họa", "zlib giải nén thử", "Bộ đọc phần tử", "Ghi chú"]
    ws.append(cols)
    for c in ws[1]:
        c.font = Font(bold=True)
    for f in files:
        p = probe_dgn(f)
        ws.append([f.name, p.size, p.sha256, p.version, p.creating_application, p.models,
                   "; ".join(p.graphic_streams), p.graphic_stream_bytes, p.zlib_ok, p.element_reader,
                   " | ".join(p.notes)])
        print(f.name, p.version, p.creating_application, p.zlib_ok)
    for col, w in zip("ABCDEFGHIJK", [16, 14, 66, 9, 26, 9, 44, 14, 12, 28, 80]):
        ws.column_dimensions[col].width = w
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
