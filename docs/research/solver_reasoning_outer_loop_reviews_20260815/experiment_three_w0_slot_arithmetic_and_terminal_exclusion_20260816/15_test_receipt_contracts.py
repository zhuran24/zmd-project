"""Persistent negative tests for experiment-three receipt and lift contracts."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from jsonschema import Draft202012Validator


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
SCHEMA_PATH = HERE / "13_RECEIPT_ENVELOPE_SCHEMA_V1.json"
THEOREM_RECEIPT_PATH = HERE / "05_THEOREM_RECEIPT.json"
TERMINAL_RECEIPT_PATH = HERE / "11_TERMINAL_RECEIPT.json"
CORRESPONDENCE_MANIFEST_PATH = HERE / "06_MODEL_CORRESPONDENCE_MANIFEST.json"
OWNER_AUTHORIZATION_PATH = HERE / "00_OWNER_AUTHORIZATION_20260816.md"
ACCEPTANCE_PATH = HERE / "00_ACCEPTANCE_CRITERIA_FROZEN.md"


def load_checker(filename: str, module_name: str) -> ModuleType:
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


THEOREM_CHECKER = load_checker("04_check_w0_slot_arithmetic.py", "experiment_three_theorem_checker")
TERMINAL_CHECKER = load_checker("10_check_w0_terminal_exclusion.py", "experiment_three_terminal_checker")


def receipt_schema_mutations() -> list[tuple[str, dict[str, Any]]]:
    theorem = read_json(THEOREM_RECEIPT_PATH)
    terminal = read_json(TERMINAL_RECEIPT_PATH)
    cases: list[tuple[str, dict[str, Any]]] = []

    mutated = copy.deepcopy(theorem)
    del mutated["contract_identity"]["protocol_freeze_commit"]
    cases.append(("missing_contract_identity_field", mutated))

    mutated = copy.deepcopy(theorem)
    mutated["outcome"] = "PASS"
    cases.append(("bare_pass_outcome", mutated))

    mutated = copy.deepcopy(theorem)
    mutated["status"] = "PASS"
    cases.append(("top_level_status", mutated))

    mutated = copy.deepcopy(theorem)
    mutated["authority_basis"]["authority_sources"]["owner_authorization"]["sha256"] = "0" * 64
    cases.append(("authority_digest_drift", mutated))

    mutated = copy.deepcopy(theorem)
    mutated["authority_basis"]["authority_class"] = "production_authorizing"
    cases.append(("authority_class_escalation", mutated))

    mutated = copy.deepcopy(theorem)
    mutated["granted_effects"][0] = "permits_production_exact_status_write"
    cases.append(("forged_granted_effect", mutated))

    mutated = copy.deepcopy(theorem)
    mutated["outcome"] = "W0_SLOT_ARITHMETIC_FAIL"
    cases.append(("fail_with_granted_effects", mutated))

    mutated = copy.deepcopy(terminal)
    del mutated["path_obligations"][0]["required_evidence"]
    cases.append(("obligation_missing_field", mutated))

    mutated = copy.deepcopy(terminal)
    mutated["path_obligations"][1]["machine_checked"] = False
    cases.append(("obligation_status_machine_mismatch", mutated))

    mutated = copy.deepcopy(terminal)
    mutated["path_obligations"][1]["id"] = mutated["path_obligations"][0]["id"]
    cases.append(("duplicate_obligation_id", mutated))

    mutated = copy.deepcopy(terminal)
    mutated["terminal_summary"]["terminal_status"] = "UNKNOWN"
    cases.append(("terminal_status_drift", mutated))

    mutated = copy.deepcopy(terminal)
    mutated["verified_scope"]["candidate_state_after"] = "UNKNOWN"
    cases.append(("candidate_state_after_drift", mutated))

    mutated = copy.deepcopy(terminal)
    mutated["terminal_summary"]["path_obligations_open"] = 1
    cases.append(("terminal_open_nonzero", mutated))

    mutated = copy.deepcopy(terminal)
    mutated["verified_scope"]["path_obligations_open"] = False
    cases.append(("bool_masquerades_as_zero", mutated))

    mutated = copy.deepcopy(terminal)
    mutated["path_obligations"].pop()
    cases.append(("obligation_count_seven", mutated))

    return cases


@pytest.mark.parametrize(
    ("_name", "receipt"),
    receipt_schema_mutations(),
    ids=[name for name, _ in receipt_schema_mutations()],
)
def test_receipt_schema_mutations_are_rejected(_name: str, receipt: dict[str, Any]) -> None:
    schema = read_json(SCHEMA_PATH)
    assert not Draft202012Validator(schema).is_valid(receipt)
    with pytest.raises(THEOREM_CHECKER.CheckError):
        THEOREM_CHECKER.validate_json_schema_subset(receipt, schema)
    with pytest.raises(TERMINAL_CHECKER.TerminalCheckError):
        TERMINAL_CHECKER.validate_json_schema_subset(receipt, schema)


def test_receipt_schema_digest_identity_drift_is_rejected() -> None:
    theorem = read_json(THEOREM_RECEIPT_PATH)
    theorem["contract_identity"]["receipt_schema_sha256"] = "0" * 64
    with pytest.raises(THEOREM_CHECKER.CheckError, match="digest identity drift"):
        THEOREM_CHECKER.validate_receipt_against_schema(theorem)
    with pytest.raises(TERMINAL_CHECKER.TerminalCheckError, match="digest identity drift"):
        TERMINAL_CHECKER.validate_receipt_against_schema(theorem)


def test_both_checkers_reject_tampered_schema_bytes(tmp_path: Path) -> None:
    tampered = tmp_path / SCHEMA_PATH.name
    tampered.write_text('{"type":"object"}\n', encoding="utf-8")
    with pytest.raises(THEOREM_CHECKER.CheckError, match="schema SHA-256 drift"):
        THEOREM_CHECKER.verify_receipt_schema_digest(tampered)
    with pytest.raises(TERMINAL_CHECKER.TerminalCheckError, match="schema SHA-256 drift"):
        TERMINAL_CHECKER.verify_receipt_schema_digest(tampered)


def test_manifest_obligation_contract_mutations_are_rejected() -> None:
    manifest = read_json(CORRESPONDENCE_MANIFEST_PATH)
    mutations: list[dict[str, Any]] = []

    mutated = copy.deepcopy(manifest)
    mutated["path_obligations"].pop()
    mutations.append(mutated)

    mutated = copy.deepcopy(manifest)
    mutated["path_obligations"][0]["id"] = "W0-LIFT-SYNTHETIC"
    mutations.append(mutated)

    mutated = copy.deepcopy(manifest)
    mutated["path_obligations"][0]["required_evidence"][0] = "synthetic evidence"
    mutations.append(mutated)

    for mutation in mutations:
        with pytest.raises(TERMINAL_CHECKER.TerminalCheckError):
            TERMINAL_CHECKER.verify_obligation_contract(mutation)


def test_authority_currency_and_receipt_chain() -> None:
    owner_sha = sha256(OWNER_AUTHORIZATION_PATH)
    acceptance_sha = sha256(ACCEPTANCE_PATH)
    assert owner_sha == THEOREM_CHECKER.OWNER_AUTHORIZATION_SHA256
    assert owner_sha == TERMINAL_CHECKER.OWNER_AUTHORIZATION_SHA256
    assert acceptance_sha == THEOREM_CHECKER.ACCEPTANCE_SHA256
    assert acceptance_sha == TERMINAL_CHECKER.ACCEPTANCE_SHA256

    for receipt_path in (THEOREM_RECEIPT_PATH, TERMINAL_RECEIPT_PATH):
        authority = read_json(receipt_path)["authority_basis"]
        sources = authority["authority_sources"]
        assert sources["owner_authorization"]["sha256"] == owner_sha
        assert sources["acceptance_criteria"]["sha256"] == acceptance_sha
        assert str(OWNER_AUTHORIZATION_PATH.relative_to(REPO_ROOT)) in authority["source_paths"]


def test_correspondence_manifest_double_pins_receipt_schema() -> None:
    manifest = read_json(CORRESPONDENCE_MANIFEST_PATH)
    schema_rel = str(SCHEMA_PATH.relative_to(REPO_ROOT))
    expected = {
        "path": schema_rel,
        "sha256": sha256(SCHEMA_PATH),
        "size_bytes": SCHEMA_PATH.stat().st_size,
    }
    implementation = next(
        item for item in manifest["implementation_sources"] if item["role"] == "receipt_schema"
    )
    protected = next(item for item in manifest["protected_surfaces"] if item["path"] == schema_rel)
    assert {key: implementation[key] for key in expected} == expected
    assert {key: protected[key] for key in expected} == expected


def test_unknown_schema_keyword_fails_closed() -> None:
    unsupported = {"type": "object", "patternProperties": {}}
    with pytest.raises(THEOREM_CHECKER.CheckError):
        THEOREM_CHECKER.validate_json_schema_subset({}, unsupported)
    with pytest.raises(TERMINAL_CHECKER.TerminalCheckError):
        TERMINAL_CHECKER.validate_json_schema_subset({}, unsupported)
