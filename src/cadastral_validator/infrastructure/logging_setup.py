"""Log JSONL (máy đọc) + log tiếng Việt (người đọc). Không ghi thông tin cá nhân mặc định."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path


class JsonlHandler(logging.Handler):
    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    def emit(self, record):
        rec = {"ts": datetime.now().isoformat(timespec="seconds"), "level": record.levelname,
               "msg": record.getMessage(), **getattr(record, "data", {})}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime("%Y%m%d")
    log = logging.getLogger("cvp")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(log_dir / f"cvp_{day}.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    log.addHandler(fh)
    log.addHandler(JsonlHandler(log_dir / f"cvp_{day}.jsonl"))
    return log
