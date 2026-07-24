"""Documentation contract for the rule/cut evolution shadow batch."""

from __future__ import annotations

import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DOC_ROOT = _PROJECT_ROOT / "docs/项目说明"
_PROTOCOL_PATH = _DOC_ROOT / "23_rule_cut_evolution_protocol.md"
_CROSS_REFERENCE_PATHS = (
    _DOC_ROOT / "00_master_roadmap.md",
    _DOC_ROOT / "06_current_status.md",
    _DOC_ROOT / "README.md",
    _DOC_ROOT / "21_glossary.md",
)
_ALLOWED_STATUSES = frozenset(
    {"candidate_pending_full_preflight", "full_preflight_passed"}
)
_STATUS_PATTERN = re.compile(
    r"(?m)^rule_cut_evolution_status\s*:\s*`?([a-z_]+)`?\s*$"
)
_NON_AUTHORIZING_METADATA = {
    "authority_effect": "non_authorizing",
    "authority_digest_change": "none",
    "p1_2_reseal": "not_performed",
}


def _read_required(path: Path) -> str:
    assert path.is_file(), f"required terminal documentation is missing: {path}"
    return path.read_text(encoding="utf-8")


def _metadata_values(text: str, key: str) -> list[str]:
    pattern = re.compile(rf"(?m)^{re.escape(key)}\s*:\s*`?([a-z0-9_]+)`?\s*$")
    return pattern.findall(text)


def _protocol_status(protocol_text: str) -> str:
    statuses = _STATUS_PATTERN.findall(protocol_text)
    assert len(statuses) == 1, "protocol must contain exactly one rule_cut_evolution_status marker"
    status = statuses[0]
    assert status in _ALLOWED_STATUSES
    return status


def test_protocol_has_bounded_status_and_non_authorizing_metadata() -> None:
    protocol_text = _read_required(_PROTOCOL_PATH)
    _protocol_status(protocol_text)

    for key, expected_value in _NON_AUTHORIZING_METADATA.items():
        assert _metadata_values(protocol_text, key) == [expected_value]


def test_protocol_and_project_status_documents_cross_reference_each_other() -> None:
    protocol_text = _read_required(_PROTOCOL_PATH)
    status = _protocol_status(protocol_text)

    for cross_reference_path in _CROSS_REFERENCE_PATHS:
        cross_reference_text = _read_required(cross_reference_path)
        assert f"]({_PROTOCOL_PATH.name})" in cross_reference_text
        assert f"]({cross_reference_path.name})" in protocol_text

    current_status_text = _read_required(_DOC_ROOT / "06_current_status.md")
    current_statuses = _STATUS_PATTERN.findall(current_status_text)
    assert current_statuses == [status]
