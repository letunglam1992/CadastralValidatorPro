"""Rule Registry: nạp rule pack, kiểm soát trạng thái xác minh.

Quy tắc (Phụ lục V2.1 mục B, V2.2 mục B):
- Rule PENDING_VERIFICATION chỉ được phát hiện/cảnh báo, không được auto-fix.
- Không gọi ngưỡng gợi ý của phần mềm là tiêu chuẩn pháp luật.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_CLASSIFICATIONS = {"LEGAL_REQUIREMENT", "APPROVED_PROJECT_SPEC", "LOCAL_CONFIG", "SOFTWARE_HEURISTIC"}
VALID_VERIFICATION = {"VERIFIED_CURRENT", "VERIFIED_PARTIAL", "PENDING_VERIFICATION", "SUPERSEDED", "REPEALED"}
VALID_AUTOFIX = {"NONE", "SUGGEST_ONLY", "PREVIEW_ONLY", "AUTO_SAFE_WITH_PREVIEW"}
VALID_SEVERITY = {"error", "warning", "info"}


class RulePackError(ValueError):
    """Lỗi cấu hình rule pack — báo rõ trường sai, không fallback âm thầm."""


@dataclass
class Rule:
    rule_id: str
    code: str
    title: str
    severity: str
    scope: str
    classification: str
    verification_status: str
    legal_refs: list[dict[str, Any]]
    auto_fix_policy: str
    test_case_id: str
    enabled: bool = True

    @property
    def can_auto_fix(self) -> bool:
        return (self.auto_fix_policy == "AUTO_SAFE_WITH_PREVIEW"
                and self.verification_status == "VERIFIED_CURRENT")


@dataclass
class RulePack:
    rule_pack_id: str
    version: str
    approval_status: str
    scale_params: dict[str, dict[str, Any]]
    general_params: dict[str, Any]
    rules: dict[str, Rule] = field(default_factory=dict)   # theo code
    config_hash: str = ""
    path: str = ""

    def rule(self, code: str) -> Rule:
        if code not in self.rules:
            raise KeyError(f"Không có rule với code '{code}' trong rule pack {self.rule_pack_id}")
        return self.rules[code]

    def enabled(self, code: str) -> bool:
        return code in self.rules and self.rules[code].enabled

    def params_for_scale(self, scale: str) -> dict[str, Any]:
        if scale not in self.scale_params:
            raise RulePackError(f"Tỷ lệ '{scale}' không có trong scale_params của rule pack {self.rule_pack_id}")
        p = dict(self.scale_params[scale])
        p.update(self.general_params)
        return p


def _require(d: dict, key: str, where: str):
    if key not in d:
        raise RulePackError(f"{where}: thiếu trường bắt buộc '{key}'")
    return d[key]


def load_rulepack(path: str | Path) -> RulePack:
    path = Path(path)
    raw_bytes = path.read_bytes()
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise RulePackError(f"{path.name}: JSON không hợp lệ dòng {e.lineno} cột {e.colno}: {e.msg}") from e

    pack = RulePack(
        rule_pack_id=_require(data, "rule_pack_id", path.name),
        version=_require(data, "rule_pack_version", path.name),
        approval_status=_require(data, "approval_status", path.name),
        scale_params=_require(data, "scale_params", path.name),
        general_params=data.get("general_params", {}),
        config_hash=hashlib.sha256(raw_bytes).hexdigest(),
        path=str(path),
    )
    for i, r in enumerate(_require(data, "rules", path.name)):
        where = f"{path.name}: rules[{i}]"
        rule = Rule(
            rule_id=_require(r, "rule_id", where), code=_require(r, "code", where),
            title=_require(r, "title", where), severity=_require(r, "severity", where),
            scope=_require(r, "scope", where), classification=_require(r, "classification", where),
            verification_status=_require(r, "verification_status", where),
            legal_refs=r.get("legal_refs", []), auto_fix_policy=_require(r, "auto_fix_policy", where),
            test_case_id=r.get("test_case_id", ""), enabled=bool(r.get("enabled", True)),
        )
        if rule.severity not in VALID_SEVERITY:
            raise RulePackError(f"{where} ({rule.rule_id}): severity '{rule.severity}' không hợp lệ")
        if rule.classification not in VALID_CLASSIFICATIONS:
            raise RulePackError(f"{where} ({rule.rule_id}): classification '{rule.classification}' không hợp lệ")
        if rule.verification_status not in VALID_VERIFICATION:
            raise RulePackError(f"{where} ({rule.rule_id}): verification_status '{rule.verification_status}' không hợp lệ")
        if rule.auto_fix_policy not in VALID_AUTOFIX:
            raise RulePackError(f"{where} ({rule.rule_id}): auto_fix_policy '{rule.auto_fix_policy}' không hợp lệ")
        if rule.classification == "LEGAL_REQUIREMENT" and (
                rule.verification_status != "VERIFIED_CURRENT" or not rule.legal_refs):
            raise RulePackError(
                f"{where} ({rule.rule_id}): rule LEGAL_REQUIREMENT phải có legal_refs và VERIFIED_CURRENT")
        if rule.auto_fix_policy == "AUTO_SAFE_WITH_PREVIEW" and rule.verification_status != "VERIFIED_CURRENT":
            raise RulePackError(f"{where} ({rule.rule_id}): không được bật auto-fix khi rule chưa xác minh")
        if rule.code in pack.rules:
            raise RulePackError(f"{where}: trùng code '{rule.code}'")
        pack.rules[rule.code] = rule
    return pack
