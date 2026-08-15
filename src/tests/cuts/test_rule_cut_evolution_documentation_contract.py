"""Documentation contract for the stable rule/cut evolution protocol."""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DOC_ROOT = _PROJECT_ROOT / "docs/项目说明"
_PROTOCOL_PATH = _DOC_ROOT / "23_rule_cut_evolution_protocol.md"
_METHOD_PATH = _DOC_ROOT / "REASONING_METHOD.md"
_PROJECT_README_PATH = _DOC_ROOT / "README.md"
_CURRENT_STATUS_PATH = _DOC_ROOT / "06_current_status.md"
_RETIRED_STATUS_MARKERS = (
    "rule_cut_evolution_status",
    "authority_effect",
    "authority_digest_change",
    "p1_2_reseal",
)


def _read_required(path: Path) -> str:
    assert path.is_file(), f"required terminal documentation is missing: {path}"
    return path.read_text(encoding="utf-8")


def test_protocol_is_stable_and_does_not_reintroduce_batch_status_metadata() -> None:
    protocol_text = _read_required(_PROTOCOL_PATH)

    for marker in _RETIRED_STATUS_MARKERS:
        assert marker not in protocol_text
    assert "不记录某一批次" in protocol_text
    assert "owner-authorized" in protocol_text


def test_protocol_links_the_split_current_method_and_navigation_surfaces() -> None:
    protocol_text = _read_required(_PROTOCOL_PATH)

    assert "](REASONING_METHOD.md)" in protocol_text
    assert "](../CURRENT.md)" in protocol_text
    assert "](README.md)" in protocol_text
    assert "](../TERMINOLOGY.md)" in protocol_text

    method_text = _read_required(_METHOD_PATH)
    project_readme_text = _read_required(_PROJECT_README_PATH)
    assert f"]({_PROTOCOL_PATH.name})" in method_text
    assert f"]({_PROTOCOL_PATH.name})" in project_readme_text

    current_status_text = _read_required(_CURRENT_STATUS_PATH)
    assert "../CURRENT.md" in current_status_text
    assert f"]({_PROTOCOL_PATH.name})" in current_status_text
    for marker in _RETIRED_STATUS_MARKERS:
        assert marker not in current_status_text
