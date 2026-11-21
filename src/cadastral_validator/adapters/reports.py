"""Xuất báo cáo: Excel (tổng hợp + chi tiết), GeoJSON lỗi, CSV, JSON kết quả.

Số lượng trong mọi báo cáo lấy từ cùng một danh sách issue (issue store trong bộ nhớ)
để bảo đảm nhất quán (Master Prompt Tab 3 Tầng C).
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ..domain.models import SheetResult

SEV_VI = {"error": "Lỗi", "warning": "Cần xem", "info": "Thông tin"}
STATUS_VI = {"OK": "Đạt (theo bộ quy tắc nháp)", "CO_LOI": "Có lỗi", "CAN_XEM": "Cần xem lại",
             "DUNG_TIEN_KIEM": "Dừng ở tiền kiểm", "KHONG_DOC_DUOC": "Không đọc được"}
DISCLAIMER = ("Kết quả kiểm tra kỹ thuật offline theo bộ quy tắc cấu hình nháp (chưa xác minh pháp lý). "
              "Không phải kết quả kiểm định/chứng nhận của LANDINFO hay cơ quan nhà nước.")


def _atomic_write_text(path: Path, text: str):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def export_json(results: list[SheetResult], path: Path, meta: dict):
    data = {"meta": meta, "disclaimer": DISCLAIMER, "sheets": []}
    for r in results:
        data["sheets"].append({"sheet_id": r.sheet_id, "file_name": r.file_name, "status": r.status,
                               "message": r.message, "stats": r.stats,
                               "issues": [i.to_dict() for i in r.issues]})
    _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=1, default=str))


def export_csv(results: list[SheetResult], path: Path):
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["issue_id", "to", "ma_loi", "rule_id", "muc_do", "noi_dung", "X", "Y", "thua", "phan_tu",
                    "trang_thai_xac_minh"])
        for r in results:
            for i in r.issues:
                w.writerow([i.issue_id, r.file_name, i.code, i.rule_id, SEV_VI.get(i.severity, i.severity), i.message,
                            f"{i.x:.3f}" if i.x is not None else "", f"{i.y:.3f}" if i.y is not None else "",
                            ";".join(i.parcel_ids), ";".join(i.source_element_ids), i.verification_status])
    tmp.replace(path)


def export_geojson(results: list[SheetResult], path: Path, crs_note: str | None = None):
    feats = []
    for r in results:
        for i in r.issues:
            if i.x is None:
                continue
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [i.x, i.y]},
                          "properties": {"issue_id": i.issue_id, "sheet": r.file_name, "code": i.code,
                                         "severity": i.severity, "message": i.message}})
    data = {"type": "FeatureCollection", "features": feats,
            "cvp_crs_note": crs_note or "Tọa độ phẳng theo CRS của tờ (chưa chuyển đổi)."}
    _atomic_write_text(path, json.dumps(data, ensure_ascii=False))


def export_excel(results: list[SheetResult], path: Path, meta: dict):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "TongHop"
    hdr_fill = PatternFill("solid", fgColor="1F3864")
    hdr_font = Font(bold=True, color="FFFFFF")

    def header(sheet, row, cols):
        for c, v in enumerate(cols, 1):
            cell = sheet.cell(row=row, column=c, value=v)
            cell.fill, cell.font = hdr_fill, hdr_font
            cell.alignment = Alignment(wrap_text=True, vertical="center")

    ws["A1"] = "BÁO CÁO KIỂM TRA DGN OFFLINE — CadastralValidatorPro"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = DISCLAIMER
    ws["A2"].font = Font(italic=True, color="C00000")
    ws["A3"] = (f"Bộ quy tắc: {meta.get('rule_pack')} | config_hash: {meta.get('config_hash')} | "
                f"Thời điểm: {meta.get('run_at')}")
    cols = ["STT", "Tệp", "Kết quả", "Lỗi", "Cần xem", "Thông tin", "Số vùng", "Nhãn lớp 13", "Nhãn lớp 4",
            "Nhãn lớp 2", "Đầu mút treo", "CRS xác nhận", "Nguồn đọc", "Dữ liệu tổng hợp?", "SHA-256 nguồn",
            "Ghi chú"]
    header(ws, 5, cols)
    for k, r in enumerate(results, 1):
        s = r.stats
        ws.append([k, r.file_name, STATUS_VI.get(r.status, r.status), r.count("error"), r.count("warning"),
                   r.count("info"), s.get("so_vung"), s.get("nhan_lop13"), s.get("nhan_lop4"), s.get("nhan_lop2"),
                   s.get("dau_mut_treo"), "Có" if s.get("crs_confirmed") else "Chưa", s.get("reader"),
                   "Có (fixture)" if s.get("synthetic") else "Không", (s.get("source_sha256") or "")[:16],
                   r.message])
    tot = len(results) + 6
    ws.cell(row=tot, column=2, value="TỔNG").font = Font(bold=True)
    for col in (4, 5, 6):
        L = get_column_letter(col)
        ws.cell(row=tot, column=col, value=f"=SUM({L}6:{L}{tot - 1})").font = Font(bold=True)
    for i, w in enumerate([5, 22, 20, 7, 8, 9, 8, 10, 10, 10, 10, 10, 18, 12, 18, 60], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A6"

    wd = wb.create_sheet("ChiTietLoi")
    cols2 = ["Mã lỗi (ID)", "Tệp", "Mã", "Rule", "Mức độ", "Nội dung", "X", "Y", "Thửa liên quan",
             "Phần tử nguồn", "Đề xuất xử lý", "Trạng thái xác minh rule", "Phiên bản rule", "Trạng thái xử lý"]
    header(wd, 1, cols2)
    for r in results:
        for i in r.issues:
            wd.append([i.issue_id, r.file_name, i.code, i.rule_id, SEV_VI.get(i.severity, i.severity), i.message,
                       round(i.x, 3) if i.x is not None else None, round(i.y, 3) if i.y is not None else None,
                       "; ".join(i.parcel_ids), "; ".join(i.source_element_ids), i.suggested_fix or "",
                       i.verification_status, i.rule_version, i.status])
    for i, w in enumerate([14, 16, 24, 10, 10, 80, 14, 14, 20, 20, 40, 22, 10, 12], 1):
        wd.column_dimensions[get_column_letter(i)].width = w
    wd.auto_filter.ref = f"A1:{get_column_letter(len(cols2))}{max(1, wd.max_row)}"
    wd.freeze_panes = "A2"

    wc = wb.create_sheet("TheoMaLoi")
    header(wc, 1, ["Mã lỗi", "Mức độ", "Số lượng (công thức)"])
    codes = sorted({(i.code, i.severity) for r in results for i in r.issues})
    last = max(2, wd.max_row)
    for n, (code, sev) in enumerate(codes, 2):
        wc.cell(row=n, column=1, value=code)
        wc.cell(row=n, column=2, value=SEV_VI.get(sev, sev))
        wc.cell(row=n, column=3, value=f'=COUNTIF(ChiTietLoi!C2:C{last},A{n})')
    wc.column_dimensions["A"].width = 26
    wc.column_dimensions["C"].width = 20

    wm = wb.create_sheet("CauHinh")
    for k, v in meta.items():
        wm.append([k, json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v])
    wm.column_dimensions["A"].width = 24
    wm.column_dimensions["B"].width = 90
    tmp = path.with_name(path.name + ".tmp.xlsx")
    wb.save(tmp)
    tmp.replace(path)


def write_all(results: list[SheetResult], out_dir: Path, meta: dict, html: bool = True) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = {
        "json": out_dir / f"KetQua_KiemTra_{stamp}.json",
        "csv": out_dir / f"BaoCaoLoi_{stamp}.csv",
        "xlsx": out_dir / f"BaoCao_KiemTra_{stamp}.xlsx",
        "geojson": out_dir / f"Loi_{stamp}.geojson",
    }
    export_json(results, paths["json"], meta)
    export_csv(results, paths["csv"])
    export_excel(results, paths["xlsx"], meta)
    export_geojson(results, paths["geojson"])
    if html:
        from .html_map import export_html_map
        for r in results:
            if r.status == "KHONG_DOC_DUOC":
                continue  # không có hình học để vẽ
            p = out_dir / f"{Path(r.file_name).stem}_BanDo_{stamp}.html"
            export_html_map(r, p, meta)
            paths[f"html:{r.sheet_id}"] = p
    return paths


def iter_issue_counts(results: Iterable[SheetResult]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in results:
        for i in r.issues:
            out[i.code] = out.get(i.code, 0) + 1
    return out
