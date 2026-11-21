"""Bộ trích xuất phần tử DGN qua MicroStation V8i COM (Windows + pywin32).

TRẠNG THÁI: NOT_TESTED — chưa chạy trên máy có MicroStation. Các tên đối tượng dùng
theo mô hình đối tượng MicroStation VBA (Application.OpenDesignFileForProgram,
ModelReference.Scan, ElementEnumerator, Element.Type/Level/AsVertexList, TextElement,
TextNodeElement, CellElement). Phải chạy `scripts/probe_microstation.py` để xác minh
ProgID, bitness (V8i thường 32-bit) và cách pywin32 trả kiểu Point3d trước khi tin dùng.

Mặc định mở CHỈ ĐỌC; không đóng/kill tiến trình ustation.exe của người dùng.
Nếu COM out-of-process từ Python 64-bit không hoạt động, dùng macro VBA
`scripts/microstation/XuatPhanTu_CVP.bas` (chạy trong MicroStation) để xuất cùng định dạng JSON.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from ..domain.models import CapabilityStatus, MapSheet, RawElement, SourceInfo
from .dgn_probe import probe_dgn

PROGID = "MicroStationDGN.Application"

# MsdElementType (giá trị theo tài liệu MicroStation VBA; cần xác minh trên máy thật)
T_CELL, T_LINE, T_LINESTRING, T_SHAPE, T_TEXTNODE = 2, 3, 4, 6, 7
T_COMPLEX_STRING, T_COMPLEX_SHAPE, T_ELLIPSE, T_ARC, T_TEXT = 12, 14, 15, 16, 17
TYPE_NAME = {T_CELL: "cell", T_LINE: "line", T_LINESTRING: "linestring", T_SHAPE: "shape",
             T_TEXTNODE: "textnode", T_COMPLEX_STRING: "complex_string", T_COMPLEX_SHAPE: "complex_shape",
             T_ELLIPSE: "ellipse", T_ARC: "arc", T_TEXT: "text"}


class MicroStationUnavailable(RuntimeError):
    pass


def com_capability() -> tuple[str, str]:
    """Kiểm tra nhanh khả năng COM (không khởi động MicroStation)."""
    if sys.platform != "win32":
        return CapabilityStatus.BLOCKED.value, "Không phải Windows — MicroStation COM không khả dụng."
    try:
        import win32com.client  # noqa: F401
        import pythoncom  # noqa: F401
    except ImportError:
        return CapabilityStatus.BLOCKED.value, "Thiếu pywin32 (pip install pywin32)."
    try:
        import winreg
        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, PROGID).Close()
    except OSError:
        return CapabilityStatus.BLOCKED.value, f"ProgID {PROGID} chưa được đăng ký."
    return CapabilityStatus.NOT_TESTED.value, f"ProgID {PROGID} có đăng ký; chưa thử đọc phần tử."


def _pt(p: Any) -> tuple[float, float]:
    return (float(p.X), float(p.Y))


def _id(app, el) -> str:
    try:
        return str(app.DLongToString(el.ID))
    except Exception:
        try:
            return f"{el.ID.High}_{el.ID.Low}"
        except Exception:
            return str(id(el))


def _convert(app, el, stats: dict) -> Optional[RawElement]:
    t = int(el.Type)
    name = TYPE_NAME.get(t)
    stats[name or f"type_{t}"] = stats.get(name or f"type_{t}", 0) + 1
    if name is None:
        return None
    level, lname = 0, None
    try:
        if el.Level is not None:
            level, lname = int(el.Level.Number), str(el.Level.Name)
    except Exception:
        pass
    r = RawElement(id=_id(app, el), type=name, level=level)
    if lname is not None:
        r.extra["level_name"] = lname
    if t in (T_LINE, T_LINESTRING, T_SHAPE):
        r.coords = [_pt(p) for p in el.AsVertexList.GetVertices()]
        r.closed = t == T_SHAPE
    elif t == T_TEXT:
        te = el.AsTextElement
        r.text = te.Text
        r.origin = _pt(te.Origin)
        try:
            r.font = te.TextStyle.Font.Name
        except Exception:
            pass
    elif t in (T_TEXTNODE, T_CELL, T_COMPLEX_STRING, T_COMPLEX_SHAPE):
        if t == T_TEXTNODE:
            en = el.AsTextNodeElement.GetSubElements()
        elif t == T_CELL:
            ce = el.AsCellElement
            r.cell_name = ce.Name
            try:
                r.origin = _pt(ce.Origin)
            except Exception:
                pass
            en = ce.GetSubElements()
        else:
            en = el.AsComplexElement.GetSubElements()
            r.closed = t == T_COMPLEX_SHAPE
        while en.MoveNext():
            ch = _convert(app, en.Current, stats)
            if ch is not None:
                r.children.append(ch)
        if t in (T_COMPLEX_STRING, T_COMPLEX_SHAPE):
            # nối đỉnh các phần tử con theo thứ tự (cung tròn con chưa được rời rạc hóa -> PARTIAL)
            for ch in r.children:
                r.coords.extend(ch.coords)
    else:
        stats["unsupported_geometry"] = stats.get("unsupported_geometry", 0) + 1
    return r


def extract_dgn(path: str | Path, scale: str = "1:1000", crs_profile_id: str | None = None,
                crs_confirmed: bool = False) -> tuple[MapSheet, dict]:
    """Đọc DGN qua COM -> MapSheet. Ném MicroStationUnavailable nếu không có COM."""
    status, msg = com_capability()
    if status == CapabilityStatus.BLOCKED.value:
        raise MicroStationUnavailable(msg)
    import pythoncom
    import win32com.client

    path = Path(path).resolve()
    prof = probe_dgn(path)
    pythoncom.CoInitialize()
    stats: dict[str, Any] = {}
    try:
        try:   # typed dispatch (makepy) để pywin32 hiểu kiểu Point3d của MicroStation
            app = win32com.client.gencache.EnsureDispatch(PROGID)
        except Exception:
            app = win32com.client.Dispatch(PROGID)
        dgn = app.OpenDesignFileForProgram(str(path), True)   # True = ReadOnly
        level_table = []
        try:
            for lv in dgn.Levels:
                level_table.append({"number": int(lv.Number), "name": str(lv.Name)})
        except Exception:
            pass
        try:
            model = dgn.DefaultModelReference
            en = model.Scan()
            elements = []
            while en.MoveNext():
                r = _convert(app, en.Current, stats)
                if r is not None:
                    elements.append(r)
        finally:
            dgn.Close()
    finally:
        pythoncom.CoUninitialize()
    sheet = MapSheet(sheet_id=path.stem, file_name=path.name, elements=elements, scale=scale,
                     source=SourceInfo(path=str(path), sha256=prof.sha256, fmt="dgn", dgn_version=prof.version,
                                       reader="microstation_com", reader_status=CapabilityStatus.NOT_TESTED.value),
                     crs_profile_id=crs_profile_id, crs_confirmed=crs_confirmed, level_table=level_table)
    return sheet, stats
