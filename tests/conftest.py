import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import pytest  # noqa: E402

from cadastral_validator.application.validate_service import Validator  # noqa: E402
from cadastral_validator.domain.rules import load_rulepack  # noqa: E402
from cadastral_validator.infrastructure.config import CONFIG_DIR, load_app_config  # noqa: E402


@pytest.fixture(scope="session")
def validator():
    return Validator(load_app_config(), load_rulepack(CONFIG_DIR / "rulepacks" / "son_la_draft.json"))


def codes(res, severity=None):
    return sorted(i.code for i in res.issues if severity is None or i.severity == severity)
