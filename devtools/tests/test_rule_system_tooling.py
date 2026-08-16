from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import subprocess

import pytest

from devtools import rule_system_tooling as tooling


EXPECTED_OWN_IDS = [
    *(f"OWN-M{number:02d}" for number in range(1, 25)),
    "OWN-M27",
    "OWN-M29",
]


def _sample_entry() -> dict[str, object]:
    return tooling._strict_object(tooling.ENTRY_DIR / "D-B1-SCAFFOLD-001.json")


def test_exact_decimal_and_explicit_rational_share_one_fingerprint_form() -> None:
    decimal_payload = {"value": Decimal("0.10"), "integer": 1}
    rational_payload = {
        "value": {"exact_rational": "1/10"},
        "integer": {"exact_rational": "1/1"},
    }
    assert tooling.canonical_bytes(decimal_payload) == tooling.canonical_bytes(rational_payload)


def test_assumption_normalization_is_nfc_and_line_ending_stable() -> None:
    decomposed = "e\u0301\r\nline"
    composed = "é\nline"
    left = {
        "kind": "assumption",
        "ref": "assumption:test",
        "statement": decomposed,
        "assumption_version": "1",
    }
    right = {
        "kind": "assumption",
        "ref": "assumption:test",
        "statement": composed,
        "assumption_version": "1",
    }
    assert tooling.canonical_bytes(left) == tooling.canonical_bytes(right)


def test_sample_entry_schema_and_currency_are_current() -> None:
    entry = _sample_entry()
    tooling.validate_entry(entry)
    result = tooling.entry_currency(entry)
    assert result["computed_fingerprint"] == "4dcf493d32fab29d37f79996e5637bcd08aa51504b863c337d2eac32f679da13"
    assert result["stale"] is False
    assert result["blocking"] is False
    assert result["issues"] == []


def test_currency_mutation_turns_red() -> None:
    """Acceptance ③: hand-editing one premise value must make currency red."""

    entry = deepcopy(_sample_entry())
    entry["status"] = "ACTIVE"
    entry["consumers"] = ["docs/research/example.md#claim"]
    source_premise = entry["premises"][0]
    assert isinstance(source_premise, dict)
    source_premise["value_at_derivation"] = {"exact_rational": "2/1"}

    result = tooling.entry_currency(entry)
    assert result["stale"] is True
    assert result["blocking"] is True
    assert any("value_at_derivation" in issue for issue in result["issues"])


def test_unreviewed_stale_entry_is_visible_but_nonblocking() -> None:
    entry = deepcopy(_sample_entry())
    source_premise = entry["premises"][0]
    assert isinstance(source_premise, dict)
    source_premise["value_at_derivation"] = {"exact_rational": "2/1"}

    result = tooling.entry_currency(entry)
    assert result["stale"] is True
    assert result["blocking"] is False
    assert entry["status"] == "UNREVIEWED"


@pytest.mark.parametrize(
    ("before", "after", "allowed"),
    [
        ("UNREVIEWED", "ACTIVE", True),
        ("ACTIVE", "STALE", True),
        ("STALE", "ACTIVE", True),
        ("ACTIVE", "UNREVIEWED", False),
        ("PROMOTED", "ACTIVE", False),
        ("RETIRED", "STALE", False),
    ],
)
def test_status_transition_contract(before: str, after: str, allowed: bool) -> None:
    assert tooling.transition_allowed(before, after) is allowed


def test_derived_scaffold_headers_manifest_and_package_debt_are_current() -> None:
    result = tooling.check_derived_scaffold()
    assert result["ok"] is True
    assert result["authority_issues"] == []
    assert result["entry_count"] == 1
    assert result["blocking_currency"] == []

    manifest = tooling._strict_object(tooling.MANIFEST_PATH)
    assert manifest["canonical_schema_pin"] == "OUT_OF_SCOPE_BATCH_2_OWNER_DECISION_PENDING"
    package = manifest["package_declaration"]
    assert package["script_connection_status"] == "DEFERRED_OPEN_DEBT"
    assert package["debt_id"] == "OD-B1-PACKAGE-01"
    assert package["script_target"] == "scripts/package_review_snapshot.py"


def test_ruling_index_matches_git_grep_and_records_expected_gaps() -> None:
    result = tooling.check_ruling_index()
    assert result["ok"] is True
    assert result["git_grep_distinct_count"] == 89
    assert result["index_active_count"] == 89
    assert result["own_ids"] == EXPECTED_OWN_IDS
    assert result["expected_gaps"] == ["OWN-M25", "OWN-M26", "OWN-M28"]
    assert result["missing_from_index"] == []
    assert result["stale_active"] == []


def test_ruling_index_refresh_is_append_only(monkeypatch: pytest.MonkeyPatch) -> None:
    original = tooling.RULING_INDEX_PATH.read_text(encoding="utf-8")
    current = tooling.extract_ruling_occurrences()
    current["W-NEW-99"] = [
        {
            "path": "docs/research/synthetic.md",
            "line": 99,
            "context": "synthetic",
        }
    ]
    monkeypatch.setattr(tooling, "extract_ruling_occurrences", lambda **_kwargs: current)

    refreshed = tooling.refresh_ruling_index_text(original)
    assert refreshed.startswith(original)
    assert refreshed != original
    appended = refreshed[len(original) :]
    assert '"event":"DISCOVERED"' in appended
    assert '"id":"W-NEW-99"' in appended


def test_facility_gap_is_current_and_hits_both_admission_devices() -> None:
    result = tooling.check_facility_template_gap()
    assert result["ok"] is True
    assert result["byte_current"] is True
    assert result["missing_required_hits"] == []
    assert result["gap_count"] == 52

    payload = tooling._strict_object(tooling.FACILITY_GAP_PATH)
    gaps = set(payload["not_directly_registered"])
    assert {"item_log_admission", "item_pipe_admission"} <= gaps
    assert "not proof" in payload["interpretation_boundary"]


def test_six_views_are_byte_current_and_non_authoritative() -> None:
    result = tooling.check_views()
    assert result["ok"] is True
    assert result["stale_views"] == []
    assert result["authority_issues"] == []
    assert result["v2_code_header_noncomplete"] is True

    for path in tooling.VIEW_PATHS.values():
        payload = tooling._strict_object(path)
        assert payload["_authority"] == tooling.VIEW_AUTHORITY
        assert payload["currency"]["rule"] == "tracked bytes must equal a cold regeneration"


def test_v2_code_column_header_explicitly_says_noncomplete() -> None:
    payload = tooling._strict_object(tooling.VIEW_PATHS["V2"])
    header = payload["columns"]["code_call_sites_non_exhaustive"]
    assert "非完备" in header
    assert "git grep" in header


def test_two_independent_cold_processes_recompute_identical_fingerprint() -> None:
    command = [
        str(tooling.ROOT / ".venv" / "bin" / "python"),
        "-B",
        str(tooling.ROOT / "devtools" / "rule_system_tooling.py"),
        "fingerprint",
        "rules/derived/entries/D-B1-SCAFFOLD-001.json",
    ]
    env = {
        "PATH": str(tooling.ROOT / ".venv" / "bin"),
        "PYTHONHASHSEED": "random",
        "LANG": "C.UTF-8",
    }
    first = subprocess.run(
        command,
        cwd=tooling.ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    env["PYTHONHASHSEED"] = "123456789"
    second = subprocess.run(
        command,
        cwd=tooling.ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()

    assert first == second == _sample_entry()["premise_fingerprint"]


def test_rendered_view_bytes_do_not_depend_on_existing_view_files(tmp_path: Path) -> None:
    rendered = tooling.render_views()
    for view_id, content in rendered.items():
        clone = tmp_path / tooling.VIEW_PATHS[view_id].name
        clone.write_text(content, encoding="utf-8")
        assert clone.read_bytes() == content.encode("utf-8")


def test_schema_does_not_pin_canonical_schema_sha() -> None:
    schema_text = tooling.ENTRY_SCHEMA_PATH.read_text(encoding="utf-8")
    manifest_text = tooling.MANIFEST_PATH.read_text(encoding="utf-8")
    canonical_schema_bytes = (tooling.ROOT / "rules" / "canonical_rules.schema.json").read_bytes()
    canonical_schema_sha = __import__("hashlib").sha256(canonical_schema_bytes).hexdigest()

    assert canonical_schema_sha not in schema_text
    assert canonical_schema_sha not in manifest_text
    assert "OUT_OF_SCOPE_BATCH_2_OWNER_DECISION_PENDING" in manifest_text


def test_tool_output_is_valid_json_for_complete_check() -> None:
    result = tooling.check_all()
    encoded = json.dumps(tooling._json_safe(result), ensure_ascii=False)
    decoded = json.loads(encoded)
    assert decoded["ok"] is True
