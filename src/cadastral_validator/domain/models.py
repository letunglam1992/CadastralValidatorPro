"""Mô hình trung gian chuẩn (canonical cadastral model).

Thiết kế theo Master Prompt mục IV. Chỉ chứa dữ liệu, không phụ thuộc UI/COM.
Mọi số tờ/số thửa là chuỗi (giữ số 0 đầu).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class LabelKind(str, Enum):
    PARCEL_NO = "parcel_no"
    AREA = "area"
    LAND_TYPE = "land_type"
    OTHER = "other"


class CapabilityStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    NOT_TESTED = "NOT_TESTED"


@dataclass
class RawElement:
    """Phần tử đọc từ nguồn (DGN qua COM, hoặc fixture). Tọa độ theo master unit (m)."""
    id: str
    type: str                      # line|linestring|shape|complex_shape|complex_string|arc|text|textnode|cell
    level: int
    coords: list[tuple[float, float]] = field(default_factory=list)
    closed: bool = False
    text: Optional[str] = None
    origin: Optional[tuple[float, float]] = None
    cell_name: Optional[str] = None
    children: list["RawElement"] = field(default_factory=list)
    font: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceInfo:
    path: str
    sha256: Optional[str] = None
    fmt: str = "dgn_exchange"
    dgn_version: Optional[str] = None
    reader: str = "unknown"
    reader_status: str = CapabilityStatus.NOT_TESTED.value
    is_synthetic: bool = False


@dataclass
class MapSheet:
    sheet_id: str
    file_name: str
    elements: list[RawElement]
    source: SourceInfo
    scale: str = "1:1000"
    crs_profile_id: Optional[str] = None
    crs_confirmed: bool = False
    so_to: Optional[str] = None
    # Dữ liệu dạng polygon (GML/SHP): list[PolygonFeature]; khi có, kiểm tra theo nhánh polygon
    features: list["PolygonFeature"] = field(default_factory=list)
    coverage: Any = None           # vùng bao phủ hợp lệ do người dùng cung cấp (shapely Polygon)


@dataclass
class PolygonFeature:
    feature_id: str
    geometry: Any                  # shapely Polygon/MultiPolygon
    parcel_no: Optional[str] = None
    area_label: Optional[str] = None
    land_type: Optional[str] = None
    so_to: Optional[str] = None
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Label:
    text_raw: str
    text_norm: str
    kind: LabelKind
    level: int
    anchor: tuple[float, float]
    source_element_id: str
    cell_id: Optional[str] = None
    confidence: float = 1.0


@dataclass
class Parcel:
    internal_id: str
    geometry: Any                  # shapely Polygon
    area_geom: float
    parcel_no: Optional[str] = None
    area_label: Optional[str] = None
    land_type: Optional[str] = None
    labels: list[Label] = field(default_factory=list)
    source_element_ids: list[str] = field(default_factory=list)


@dataclass
class Issue:
    code: str
    rule_id: str
    severity: str
    sheet_id: str
    message: str
    x: Optional[float] = None
    y: Optional[float] = None
    parcel_ids: list[str] = field(default_factory=list)
    source_element_ids: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_fix: Optional[str] = None
    rule_version: str = ""
    verification_status: str = "PENDING_VERIFICATION"
    status: str = "OPEN"
    geometry_wkt: Optional[str] = None
    issue_id: str = ""

    def compute_id(self) -> str:
        """ID ổn định giữa các lần chạy: mã lỗi + tờ + vị trí làm tròn cm + ID phần tử nguồn."""
        key = "|".join([
            self.code, self.sheet_id,
            f"{self.x:.2f}" if self.x is not None else "-",
            f"{self.y:.2f}" if self.y is not None else "-",
            ",".join(sorted(self.source_element_ids)),
        ])
        self.issue_id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        return self.issue_id

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SheetResult:
    sheet_id: str
    file_name: str
    status: str                    # OK | CO_LOI | DUNG_TIEN_KIEM | KHONG_DOC_DUOC
    issues: list[Issue] = field(default_factory=list)
    parcels: list[Parcel] = field(default_factory=list)
    labels: list[Label] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    linework: list[Any] = field(default_factory=list)   # shapely lines cho bản đồ
    frame: Any = None
    message: str = ""

    def count(self, severity: str) -> int:
        return sum(1 for i in self.issues if i.severity == severity)
