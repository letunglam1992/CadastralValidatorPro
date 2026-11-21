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
    area_reference: str = "grid"
    mean_height_m: Optional[float] = None


def expand_inputs(paths: list[Path]) -> list[Path]:
    out = []
    exts = {".json", ".dgn", ".shp", ".gml"}
    for p in paths:
        if p.is_dir():
            out += sorted(q for q in p.iterdir() if q.suffix.lower() in exts and not q.name.endswith(".tmp"))
        else:
            out.append(p)
    return out


def load_sheet(p: Path, o: CheckOptions):
    ext = p.suffix.lower()
    if ext == ".json":
        return dgn_exchange.load_exchange(p, o.scale, o.crs_profile_id, o.crs_confirmed), {}
    if ext == ".dgn":
        from ..adapters.microstation_com import extract_dgn
        return extract_dgn(p, o.scale, o.crs_profile_id, o.crs_confirmed)
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
        try:
            sheet, _rep = load_sheet(p, o)
            sheet.area_reference, sheet.mean_height_m = o.area_reference, o.mean_height_m
            res = validator.validate(sheet)
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
            "run_at": datetime.now().isoformat(timespec="seconds"), "scale": o.scale,
            "crs_profile": o.crs_profile_id, "crs_confirmed": o.crs_confirmed,
            "area_reference": o.area_reference, "mean_height_m": o.mean_height_m,
            "app_version": "0.1.0-g1"}
    paths = write_all(results, o.out_dir, meta, html=o.html)
    return results, {"meta": meta, "paths": {k: str(v) for k, v in paths.items()}}
