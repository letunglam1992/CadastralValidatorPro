"""Nạp cấu hình (levels, land types, label patterns, CRS). Báo lỗi rõ trường sai."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "config"


class ConfigError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ConfigError(f"Không tìm thấy tệp cấu hình: {path}") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path.name}: JSON lỗi dòng {e.lineno}: {e.msg}") from e


@dataclass
class LevelProfile:
    boundary_levels: set[int]
    frame_levels: set[int]
    parcel_no_levels: set[int]
    area_levels: set[int]
    land_type_levels: set[int]
    label_cell_names: set[str]
    normalization_source_levels: set[int]
    error_overlay_level: int
    profile_id: str = ""
    # Khai báo theo TÊN Level (ưu tiên khi có): role -> {tên}; role ∈ boundary, frame, parcel_no, area, land_type
    role_names: dict = field(default_factory=dict)
    # Số Level dự phòng khi tệp trao đổi chưa có tên Level (phải ghi rõ nguồn)
    name_to_number_fallback: dict = field(default_factory=dict)
    exclusion_boxes: list = field(default_factory=list)   # [[x0,y0,x1,y1], ...] vùng bỏ qua nhãn (bảng, chú dẫn)
    verification_status: str = "PENDING_VERIFICATION"


@dataclass
class LandCatalog:
    codes: set[str]
    allow_combined: bool
    separator: str
    mappings: list[dict[str, str]] = field(default_factory=list)
    mappings_approved: bool = False


@dataclass
class LabelPatterns:
    parcel_no: re.Pattern
    area: re.Pattern
    land_type: re.Pattern
    decimal_sep: str = "."
    thousands_sep: Optional[str] = None


@dataclass
class AppConfig:
    levels: LevelProfile
    land: LandCatalog
    patterns: LabelPatterns
    crs_profiles: dict[str, dict[str, Any]]


def load_levels(path: Path | None = None) -> LevelProfile:
    path = path or CONFIG_DIR / "levels.json"
    d = _load(path)
    d.setdefault("boundary_levels", [])
    d.setdefault("label_levels", {"parcel_no": [], "area": [], "land_type": []})
    try:
        ll = d["label_levels"]
        return LevelProfile(
            boundary_levels=set(map(int, d["boundary_levels"])),
            frame_levels=set(map(int, d.get("frame_levels", []))),
            parcel_no_levels=set(map(int, ll["parcel_no"])),
            area_levels=set(map(int, ll["area"])),
            land_type_levels=set(map(int, ll["land_type"])),
            label_cell_names={s.upper() for s in d.get("label_cell_names", [])},
            normalization_source_levels=set(map(int, d.get("normalization_candidates", {}).get("source_levels", []))),
            error_overlay_level=int(d.get("error_overlay_level", 63)),
            profile_id=d.get("profile_id", ""),
            role_names={k: {str(n) for n in v} for k, v in d.get("level_names", {}).items()},
            name_to_number_fallback={str(k): int(v) for k, v in d.get("name_to_number_fallback", {}).items()
                                     if not str(k).startswith("_")},
            exclusion_boxes=[list(map(float, b)) for b in d.get("exclusion_boxes", [])],
            verification_status=d.get("verification_status", "PENDING_VERIFICATION"),
        )
    except KeyError as e:
        raise ConfigError(f"{path.name}: thiếu trường {e}") from e


def load_land_catalog(path: Path | None = None) -> LandCatalog:
    path = path or CONFIG_DIR / "land_types.json"
    d = _load(path)
    if "groups" not in d:
        raise ConfigError(f"{path.name}: thiếu trường 'groups'")
    codes = {c.upper() for g in d["groups"].values() for c in g}
    m = d.get("mappings", {})
    return LandCatalog(codes=codes, allow_combined=bool(d.get("allow_combined_codes", True)),
                       separator=d.get("combined_code_separator", "+"),
                       mappings=m.get("items", []), mappings_approved=m.get("approval_status") == "APPROVED")


def load_patterns(path: Path | None = None) -> LabelPatterns:
    path = path or CONFIG_DIR / "label_patterns.json"
    d = _load(path)
    try:
        loc = d.get("area_locale", {})
        return LabelPatterns(parcel_no=re.compile(d["parcel_no"]), area=re.compile(d["area"]),
                             land_type=re.compile(d["land_type"]),
                             decimal_sep=loc.get("decimal_separator", "."),
                             thousands_sep=loc.get("thousands_separator"))
    except KeyError as e:
        raise ConfigError(f"{path.name}: thiếu trường {e}") from e
    except re.error as e:
        raise ConfigError(f"{path.name}: regex không hợp lệ: {e}") from e


def load_crs_profiles(path: Path | None = None) -> dict[str, dict[str, Any]]:
    path = path or CONFIG_DIR / "crs_profiles.json"
    d = _load(path)
    return {p["id"]: p for p in d.get("profiles", [])}


def load_app_config(config_dir: Path | None = None, levels_path: Path | None = None) -> AppConfig:
    cd = config_dir or CONFIG_DIR
    return AppConfig(levels=load_levels(levels_path or cd / "levels.json"), land=load_land_catalog(cd / "land_types.json"),
                     patterns=load_patterns(cd / "label_patterns.json"),
                     crs_profiles=load_crs_profiles(cd / "crs_profiles.json"))
