"""Định dạng trao đổi phần tử DGN (cvp.dgn_exchange/1).

Bộ trích xuất MicroStation COM ghi phần tử ra JSON này; engine kiểm tra đọc JSON,
nên phần lõi kiểm thử được trên mọi máy không có MicroStation.

Cấu trúc:
{
  "schema": "cvp.dgn_exchange/1",
  "source": {"path": ..., "sha256": ..., "dgn_version": "V8", "reader": "microstation_com", "is_synthetic": false},
  "sheet": {"sheet_id": "DC8", "so_to": "8", "scale": "1:1000"},
  "units": {"master": "m"},
  "elements": [ {"id": "1234", "type": "linestring", "level": 10, "coords": [[x,y],...], "closed": false},
                {"id": "5678", "type": "text", "level": 13, "text": "125", "origin": [x,y]},
                {"id": "9", "type": "cell", "level": 0, "cell_name": "NHANTHUA", "children": [...]} ]
}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..domain.models import MapSheet, RawElement, SourceInfo

SCHEMA = "cvp.dgn_exchange/1"


class ExchangeError(ValueError):
    pass


def _el_from(d: dict[str, Any], path: str) -> RawElement:
    for k in ("id", "type", "level"):
        if k not in d:
            raise ExchangeError(f"{path}: phần tử thiếu trường '{k}'")
    return RawElement(
        id=str(d["id"]), type=str(d["type"]).lower(), level=int(d["level"]),
        coords=[(float(c[0]), float(c[1])) for c in d.get("coords", [])],
        closed=bool(d.get("closed", False)), text=d.get("text"),
        origin=tuple(d["origin"][:2]) if d.get("origin") else None,
        cell_name=d.get("cell_name"), font=d.get("font"),
        children=[_el_from(c, path) for c in d.get("children", [])],
        extra={k: v for k, v in d.items() if k not in {"id", "type", "level", "coords", "closed", "text", "origin",
                                                       "cell_name", "children", "font"}},
    )


def _el_to(e: RawElement) -> dict[str, Any]:
    d: dict[str, Any] = {"id": e.id, "type": e.type, "level": e.level}
    if e.coords:
        d["coords"] = [list(c) for c in e.coords]
    if e.closed:
        d["closed"] = True
    if e.text is not None:
        d["text"] = e.text
    if e.origin is not None:
        d["origin"] = list(e.origin)
    if e.cell_name:
        d["cell_name"] = e.cell_name
    if e.font:
        d["font"] = e.font
    if e.children:
        d["children"] = [_el_to(c) for c in e.children]
    d.update(e.extra)
    return d


def load_exchange(path: str | Path, scale: str | None = None, crs_profile_id: str | None = None,
                  crs_confirmed: bool = False) -> MapSheet:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ExchangeError(f"{path.name}: JSON lỗi dòng {e.lineno}: {e.msg}") from e
    if data.get("schema") != SCHEMA:
        raise ExchangeError(f"{path.name}: schema '{data.get('schema')}' không phải {SCHEMA}")
    src = data.get("source", {})
    sh = data.get("sheet", {})
    units = data.get("units", {}).get("master", "m")
    if units != "m":
        raise ExchangeError(f"{path.name}: master unit '{units}' — chỉ hỗ trợ m ở G1 (cần xác nhận UOR/working units)")
    return MapSheet(
        sheet_id=str(sh.get("sheet_id") or path.stem), file_name=Path(src.get("path") or path.name).name,
        elements=[_el_from(e, path.name) for e in data.get("elements", [])],
        source=SourceInfo(path=str(src.get("path") or path), sha256=src.get("sha256"), fmt="dgn_exchange",
                          dgn_version=src.get("dgn_version"), reader=src.get("reader", "unknown"),
                          is_synthetic=bool(src.get("is_synthetic", False))),
        scale=scale or sh.get("scale") or "1:1000", so_to=sh.get("so_to"),
        crs_profile_id=crs_profile_id or sh.get("crs_profile_id"), crs_confirmed=crs_confirmed,
    )


def save_exchange(sheet: MapSheet, path: str | Path) -> None:
    data = {
        "schema": SCHEMA,
        "source": {"path": sheet.source.path, "sha256": sheet.source.sha256, "dgn_version": sheet.source.dgn_version,
                   "reader": sheet.source.reader, "is_synthetic": sheet.source.is_synthetic},
        "sheet": {"sheet_id": sheet.sheet_id, "so_to": sheet.so_to, "scale": sheet.scale,
                  "crs_profile_id": sheet.crs_profile_id},
        "units": {"master": "m"},
        "elements": [_el_to(e) for e in sheet.elements],
    }
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
