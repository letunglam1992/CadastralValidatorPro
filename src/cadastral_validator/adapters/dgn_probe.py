"""Khảo sát tệp DGN KHÔNG cần MicroStation: nhận diện V7/V8, metadata OLE, hash.

Kết quả Gate 0 (xem docs/api_probe_report.md): DGN V8 là OLE/CFB; luồng đồ họa
'Dgn-Md/#xxxxxx/Dgn^G/$n' nén zlib (header 16 byte). Định dạng phần tử bên trong là
độc quyền của Bentley — phần mềm KHÔNG tự giải mã phần tử (không bịa cấu trúc).
Đọc phần tử phải qua MicroStation COM (adapters/microstation_com.py) hoặc SDK được cấp phép.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

V8_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")


@dataclass
class DgnProfile:
    path: str
    size: int
    sha256: str
    version: str                     # V8 | V7 | UNKNOWN
    creating_application: Optional[str] = None
    models: int = 0
    graphic_streams: list[str] = field(default_factory=list)
    graphic_stream_bytes: int = 0
    zlib_ok: Optional[bool] = None
    element_reader: str = "MICROSTATION_COM_REQUIRED"
    notes: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def clean_ole_string(v) -> Optional[str]:
    """Chuỗi OLE SummaryInformation có thể chứa rác sau NUL (thấy trên DGN thật DC2/DC8/seed1000)."""
    if v is None:
        return None
    s = v.decode("latin-1", "replace") if isinstance(v, bytes) else str(v)
    s = s.split("\x00", 1)[0]
    return "".join(ch for ch in s if ch.isprintable()).strip() or None


def detect_version(head: bytes) -> str:
    if head.startswith(V8_MAGIC):
        return "V8"
    # DGN V7: phần tử đầu là TCB (type 9, level 8) -> 2 byte đầu 0x08 0x09
    if len(head) >= 2 and head[0] == 0x08 and head[1] == 0x09:
        return "V7"
    return "UNKNOWN"


def probe_dgn(path: str | Path) -> DgnProfile:
    path = Path(path)
    data_head = path.open("rb").read(8)
    prof = DgnProfile(path=str(path), size=path.stat().st_size, sha256=sha256_file(path),
                      version=detect_version(data_head))
    if prof.version == "V7":
        prof.element_reader = "V7_READER_NOT_IMPLEMENTED"
        prof.notes.append("DGN V7: có thể đọc bằng GDAL/OGR DGN driver nếu cài GDAL (chưa tích hợp ở G1).")
        return prof
    if prof.version != "V8":
        prof.notes.append("Không nhận diện được định dạng DGN.")
        return prof
    try:
        import olefile
        import zlib
    except ImportError:
        prof.notes.append("Thiếu olefile — bỏ qua phân tích cấu trúc OLE.")
        return prof
    with olefile.OleFileIO(str(path)) as ole:
        try:
            meta = ole.get_metadata()
            app = meta.creating_application
            prof.creating_application = clean_ole_string(app)
        except Exception as e:  # metadata hỏng không làm dừng khảo sát
            prof.notes.append(f"Không đọc được SummaryInformation: {e}")
        names = ["/".join(e) for e in ole.listdir()]
        prof.models = len({n.split("/")[1] for n in names if n.startswith("Dgn-Md/")})
        prof.graphic_streams = [n for n in names if "/Dgn^G/" in n]
        ok = True
        for n in prof.graphic_streams:
            raw = ole.openstream(n.split("/")).read()
            prof.graphic_stream_bytes += len(raw)
            try:
                zlib.decompressobj().decompress(raw[16:], 64)
            except Exception:
                ok = False
        prof.zlib_ok = ok if prof.graphic_streams else None
    prof.notes.append("Phần tử DGN V8 không được tự giải mã (định dạng độc quyền); cần MicroStation COM.")
    return prof
