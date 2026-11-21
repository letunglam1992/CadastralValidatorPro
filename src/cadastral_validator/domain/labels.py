"""Trích và phân loại nhãn từ phần tử DGN (Text, TextNode, Cell NHANTHUA).

- Phân loại chính: theo Level cấu hình (2 loại đất, 4 diện tích, 13 số thửa).
- Nhãn ở Level không chuẩn: chỉ ĐỀ XUẤT chuyển Level theo pattern (preview), không tự ghi.
- Cell: không phân rã khi chưa có children (đặc tính Cell chưa xác minh) -> đánh dấu.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from ..infrastructure.config import LevelProfile, LabelPatterns
from .models import Label, LabelKind, RawElement
from .textparse import normalize_text

TEXT_TYPES = {"text", "textnode"}


@dataclass
class LevelSuggestion:
    element_id: str
    text: str
    current_level: int
    suggested_kind: str
    suggested_level: int
    confidence: float
    anchor: tuple[float, float]


def _anchor(el: RawElement) -> Optional[tuple[float, float]]:
    if el.origin is not None:
        return (float(el.origin[0]), float(el.origin[1]))
    if el.coords:
        xs = [c[0] for c in el.coords]
        ys = [c[1] for c in el.coords]
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    return None


def iter_text_elements(elements: Iterable[RawElement], cell_names: set[str]):
    """Sinh (element, cell_id) cho mọi Text/TextNode, kể cả nằm trong Cell nhãn."""
    for el in elements:
        if el.type in TEXT_TYPES:
            if el.type == "textnode" and el.children:
                # TextNode nhiều dòng: mỗi dòng con là một text; nếu không có children dùng text gộp
                for ch in el.children:
                    if ch.type == "text":
                        if ch.origin is None:
                            ch.origin = el.origin
                        if not ch.level:
                            ch.level = el.level
                        yield ch, None
            else:
                yield el, None
        elif el.type == "cell":
            for ch in el.children:
                if ch.type in TEXT_TYPES:
                    yield ch, el.id
                elif ch.type == "cell":
                    for sub, _ in iter_text_elements([ch], cell_names):
                        yield sub, el.id


def classify_by_pattern(text: str, patterns: LabelPatterns) -> tuple[str, float]:
    t = normalize_text(text)
    if patterns.land_type.fullmatch(t):
        return LabelKind.LAND_TYPE.value, 0.9
    if patterns.parcel_no.fullmatch(t) and "." not in t and "," not in t:
        # Số nguyên ngắn: có thể là số thửa hoặc diện tích tròn -> độ tin cậy thấp
        return LabelKind.PARCEL_NO.value, 0.6 if len(t) <= 4 else 0.4
    if patterns.area.fullmatch(t):
        return LabelKind.AREA.value, 0.85
    return LabelKind.OTHER.value, 0.0


def extract_labels(elements: list[RawElement], lv: LevelProfile, patterns: LabelPatterns
                   ) -> tuple[list[Label], list[LevelSuggestion], list[RawElement]]:
    """Trả (nhãn hợp lệ theo level, đề xuất chuyển level, cell chưa phân rã được)."""
    labels: list[Label] = []
    suggestions: list[LevelSuggestion] = []
    opaque_cells = [e for e in elements if e.type == "cell" and not e.children
                    and (e.cell_name or "").upper() in lv.label_cell_names]
    level_kind = {}
    for L in lv.parcel_no_levels:
        level_kind[L] = LabelKind.PARCEL_NO
    for L in lv.area_levels:
        level_kind[L] = LabelKind.AREA
    for L in lv.land_type_levels:
        level_kind[L] = LabelKind.LAND_TYPE
    target_level = {LabelKind.PARCEL_NO.value: min(lv.parcel_no_levels),
                    LabelKind.AREA.value: min(lv.area_levels),
                    LabelKind.LAND_TYPE.value: min(lv.land_type_levels)}

    for el, cell_id in iter_text_elements(elements, lv.label_cell_names):
        raw = el.text or ""
        norm = normalize_text(raw)
        if not norm:
            continue
        anc = _anchor(el)
        if anc is None:
            continue
        kind = level_kind.get(el.level)
        if kind is not None:
            labels.append(Label(text_raw=raw, text_norm=norm, kind=kind, level=el.level, anchor=anc,
                                source_element_id=el.id, cell_id=cell_id))
        elif el.level in lv.normalization_source_levels:
            k, conf = classify_by_pattern(norm, patterns)
            if k != LabelKind.OTHER.value:
                suggestions.append(LevelSuggestion(el.id, norm, el.level, k, target_level[k], conf, anc))
    return labels, suggestions, opaque_cells


def count_by_kind(labels: list[Label]) -> dict[str, int]:
    out = {k.value: 0 for k in (LabelKind.LAND_TYPE, LabelKind.AREA, LabelKind.PARCEL_NO)}
    for lb in labels:
        if lb.kind.value in out:
            out[lb.kind.value] += 1
    return out
