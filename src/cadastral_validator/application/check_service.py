"""Điều phối Tab 3: đọc nguồn -> kiểm tra -> báo cáo. Dùng chung cho CLI và GUI."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from ..adapters import dgn_exchange
from ..adapters.dgn_probe import probe_dgn
from ..adapters.reports import write_all
from ..domain.models import SheetResult
from ..domain.rules import load_rulepack
from ..infrastructure.config import CONFIG_DIR, load_app_config
from .validate_service import Validator

log = logging.getLogger("cvp")


@dataclass
class CheckOptions:
    inputs: list[Path]
    out_dir: Path
    rulepack: Path = CONFIG_DIR / "rulepacks" / "son_la_draft.json"
    scale: str = "1:1000"
    crs_profile_id: Optional[str] = None
    crs_confirmed: bool = False
    html: bool = True
    field_map: dict[str, str] = field(default_factory=dict)
    dbf_encoding: Optional[str] = None
    gml_swap_xy: bool = False
    levels_path: Optional[Path] = None
    area_reference: Optional[str] = None   # None -> lấy theo hồ sơ Level/tờ, mặc định "grid"
    mean_height_m: Optional[float] = None
    scale_from_cli: bool = True


def expand_inputs(paths: list[Path]) -> list[Path]:
    out = []
    exts = {".json", ".dgn", ".shp", ".gml"}
    for p in paths:
        if p.is_dir():
            items = sorted(q for q in p.iterdir() if q.suffix.lower() in exts and not q.name.endswith(".tmp"))
            dgns = {q.name.lower() for q in items if q.suffix.lower() == ".dgn"}
            # X.dgn.cvp.json đi kèm X.dgn -> chỉ giữ X.dgn (tự dùng tệp xuất sẵn)
            out += [q for q in items if not (q.name.lower().endswith(".dgn.cvp.json")
                                             and q.name[:-len(".cvp.json")].lower() in dgns)]
        else:
            out.append(p)
    return out


def sidecar_for(dgn: Path) -> Path:
    return dgn.with_name(dgn.name + ".cvp.json")


def load_dgn(p: Path, o: CheckOptions):
    """Chọn thẳng tệp .dgn:
    1) dùng tệp xuất bằng macro <tên>.dgn.cvp.json nếu có và mới hơn DGN;
    2) nếu không, đọc qua MicroStation COM (chỉ đọc);
    3) nếu không được, báo hướng dẫn rõ ràng."""
    from ..adapters.dgn_probe import sha256_file
    side = sidecar_for(p)
    if side.exists() and side.stat().st_mtime >= p.stat().st_mtime:
        sheet = dgn_exchange.load_exchange(side, o.scale, o.crs_profile_id, o.crs_confirmed)
        sheet.source.reader = "microstation_vba (tệp xuất sẵn)"
        sheet.file_name, sheet.source.path = p.name, str(p)
        sheet.source.sha256 = sha256_file(p)
        return sheet, {"via": "sidecar", "sidecar": str(side)}
    stale = " (tệp .cvp.json cũ hơn DGN — bỏ qua)" if side.exists() else ""
    from ..adapters.microstation_com import MicroStationUnavailable, extract_dgn
    try:
        sheet, stats = extract_dgn(p, o.scale, o.crs_profile_id, o.crs_confirmed)
        return sheet, {"via": "com", "stats": stats}
    except MicroStationUnavailable as e:
        raise RuntimeError(
            f"Chưa đọc được {p.name}{stale}: {e} Cách xử lý: trong MicroStation chạy macro "
            f"XuatThuMucJSON (hoặc XuatPhanTuJSON) để tạo {side.name} cạnh tệp DGN, rồi chọn lại tệp .dgn.") from e
    except Exception as e:  # lỗi COM khi đọc
        raise RuntimeError(
            f"Đọc {p.name} qua MicroStation COM bị lỗi: {type(e).__name__}: {e}{stale}. "
            f"Tạm thời dùng macro XuatThuMucJSON để tạo {side.name}, rồi chọn lại tệp .dgn.") from e


def load_sheet(p: Path, o: CheckOptions):
    ext = p.suffix.lower()
    if ext == ".json":
        return dgn_exchange.load_exchange(p, o.scale, o.crs_profile_id, o.crs_confirmed), {}
    if ext == ".dgn":
        return load_dgn(p, o)
    if ext == ".shp":
        from ..adapters.polygon_sources import read_shp
        return read_shp(p, o.field_map, o.dbf_encoding, o.scale, o.crs_profile_id, o.crs_confirmed)
    if ext == ".gml":
        from ..adapters.polygon_sources import read_gml
        return read_gml(p, o.field_map, o.gml_swap_xy, o.scale, o.crs_profile_id, o.crs_confirmed)
    raise ValueError(f"Định dạng không hỗ trợ: {p.name}")


def run_check(o: CheckOptions, progress: Optional[Callable[[int, int, str], None]] = None,
              should_stop: Optional[Callable[[], bool]] = None) -> tuple[list[SheetResult], dict]:
    cfg = load_app_config(levels_path=o.levels_path)
    pack = load_rulepack(o.rulepack)
    validator = Validator(cfg, pack)
    files = expand_inputs(o.inputs)
    results: list[SheetResult] = []
    for k, p in enumerate(files, 1):
        if should_stop and should_stop():
            log.info("Người dùng dừng tại checkpoint trước tệp %s", p.name)
            break
        if progress:
            progress(k, len(files), p.name)
        mh_src = None
        try:
            sheet, _rep = load_sheet(p, o)
            lv = cfg.levels
            sheet.area_reference = o.area_reference or lv.area_reference or "grid"
            mh = o.mean_height_m if o.mean_height_m is not None else lv.mean_height_m
            mh_src = None
            if isinstance(mh, str) and mh.startswith("auto:"):
                from ..domain.level_resolve import auto_mean_height
                mh, n_h = auto_mean_height(sheet, {x.strip() for x in mh[5:].split(",")})
                mh_src = f"tự động: trung vị {n_h} nhãn độ cao" if mh is not None else "tự động: không có nhãn độ cao"
            sheet.mean_height_m = mh
            if not o.scale_from_cli and lv.scale:
                sheet.scale = lv.scale
            res = validator.validate(sheet)
            if mh_src:
                res.stats["mean_height_source"] = mh_src
        except Exception as e:  # một tệp hỏng không làm dừng cả lô
            res = SheetResult(sheet_id=p.stem, file_name=p.name, status="KHONG_DOC_DUOC", message=str(e))
            if p.suffix.lower() == ".dgn":
                try:
                    prof = probe_dgn(p)
                    res.stats.update({"dgn_version": prof.version, "source_sha256": prof.sha256,
                                      "reader": prof.element_reader})
                except Exception:
                    pass
            log.warning("Không kiểm tra được %s: %s", p.name, e)
        results.append(res)
        log.info("Đã kiểm tra %s: %s", p.name, res.status, extra={"data": {"file": p.name, "status": res.status,
                                                                         "stats": res.stats}})
    meta = {"rule_pack": f"{pack.rule_pack_id}@{pack.version}", "rule_pack_approval": pack.approval_status,
            "config_hash": pack.config_hash[:16], "level_profile": cfg.levels.profile_id,
            "run_at": datetime.now().isoformat(timespec="seconds"),
            "scale": o.scale if (o.scale_from_cli or not cfg.levels.scale) else cfg.levels.scale,
            "crs_profile": o.crs_profile_id, "crs_confirmed": o.crs_confirmed,
            "area_reference": o.area_reference or cfg.levels.area_reference or "grid",
            "mean_height_m": o.mean_height_m if o.mean_height_m is not None else cfg.levels.mean_height_m,
            "level_profile_file": str(o.levels_path) if o.levels_path else None,
            "app_version": "0.3.0"}
    paths = write_all(results, o.out_dir, meta, html=o.html)
    return results, {"meta": meta, "paths": {k: str(v) for k, v in paths.items()}}
