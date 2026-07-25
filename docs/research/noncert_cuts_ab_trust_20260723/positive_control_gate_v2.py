#!/usr/bin/env python3
"""Fail-closed Gate 1 closeout for the injected positive-control A/B pair.

This gate replays the immutable v1 history, binds the independent v2 arithmetic
receipts and their tool, and requires a separately verified paired-arm resource
receipt for *both* complete classifications.  Resource evidence missing or
drifting can therefore produce only ``CREDIBILITY_INCOMPLETE``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
EXPECTED_HISTORY_MANIFEST_SHA256 = "2da52051018de41bda5d1c12f92dc5e1b2dc5d52e7c7f360e0d752fd4ddf5924"
EXPECTED_HISTORY_SCHEMA = "noncert-cuts-positive-control-history-v1-manifest-v2"
EXPECTED_CONFIG = {
    "ghost_rect": [6, 6],
    "master_seconds": 900.0,
    "binding_seconds": 600.0,
    "routing_seconds": 600.0,
    "max_iterations": 30,
    "binding_alt_cap": 200,
    "post_attach_seconds": 120.0,
    "workers": 1,
    "seed": 2026072301,
    "master_branching": "fixed",
    "probing_level": 3,
    "symmetry_level": 3,
    "enabled_families": [
        "region_capacity",
        "shape_packing_hall",
        "power_hitting_set",
    ],
}
EXPECTED_EXACT_ENVIRONMENT = {
    "EXACT_B1_BINDING_ALT_CAP": "200",
    "EXACT_CP_SAT_WORKERS": "1",
    "EXACT_MASTER_CP_MODEL_PROBING_LEVEL": "3",
    "EXACT_MASTER_CP_SAT_WORKERS": "1",
    "EXACT_MASTER_RANDOM_SEED": "2026072301",
    "EXACT_MASTER_SEARCH_BRANCHING": "fixed",
    "EXACT_MASTER_SYMMETRY_LEVEL": "3",
}
EXPECTED_RESOURCE_CONTRACT = {
    "memory_high_bytes": 35 * 1024**3,
    "memory_max_bytes": 39 * 1024**3,
    "memory_swap_max_bytes": 16 * 1024**3,
    "oom_policy": "continue",
    "wall_timeout_seconds": 25 * 60,
}
EXPECTED_RESOURCE_VERIFIER_CHECKS = frozenset(
    {
        "schema_version",
        "schema",
        "repository_head",
        "contract_exact",
        "arm_result_identities",
        "source_identities_replay",
        "control.required_fields",
        "control.result_identity",
        "control.unit_name",
        "control.exit_code",
        "control.termination_reason",
        "control.wall_seconds",
        "control.memory_peak_below_high",
        "control.swap_zero_at_completion",
        "control.memory_events_zero",
        "control.kill_count",
        "control.timeout_count",
        "control.limit_violation_count",
        "treatment.required_fields",
        "treatment.result_identity",
        "treatment.unit_name",
        "treatment.exit_code",
        "treatment.termination_reason",
        "treatment.wall_seconds",
        "treatment.memory_peak_below_high",
        "treatment.swap_zero_at_completion",
        "treatment.memory_events_zero",
        "treatment.kill_count",
        "treatment.timeout_count",
        "treatment.limit_violation_count",
        "distinct_unit_names",
    }
)
V1_TOOL_PATHS = {
    "runner": "docs/research/noncert_cuts_ab_trust_20260723/positive_control_runner.py",
    "arithmetic_checker": "docs/research/noncert_cuts_ab_trust_20260723/independent_arithmetic_check.py",
    "gate": "docs/research/noncert_cuts_ab_trust_20260723/positive_control_gate.py",
}
CHECKER_INPUT_NAMES = frozenset(
    {
        "arm_result",
        "sample_corpus",
        "ledger_segment",
        "mandatory_instances",
        "candidate_placements",
        "history_manifest",
    }
)
EXPECTED_CHECKER_SEMANTIC_CHECKS = {
    "NO_APPLIED_CUT": [
        "strict_geometry_rebuilt",
        "ledger_chain_and_seal_replayed",
        "zero_applied_join_confirmed",
    ],
    "PASS_APPLIED_VIOLATION": [
        "strict_geometry_rebuilt",
        "typed_plan_and_compiled_digests_rebuilt",
        "ledger_chain_and_seal_replayed",
        "compiled_applied_assignment_join_replayed",
        "active_violated_inequality_reproduced",
    ],
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_sha256(value: object) -> bool:
    if type(value) is not str or len(value) != 64 or value != value.lower():
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _reject_symlink_chain(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"symlink path component rejected: {current}")


def _identity(path: Path) -> dict[str, object]:
    absolute = path.absolute()
    _reject_symlink_chain(absolute)
    if not absolute.is_file() or absolute.is_symlink():
        raise ValueError(f"input must be a regular non-symlink file: {path}")
    raw = absolute.read_bytes()
    return {
        "path": str(absolute),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _read_json(path: Path) -> tuple[dict[str, Any], dict[str, object]]:
    identity = _identity(path)
    try:
        payload = json.loads(Path(identity["path"]).read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON input {path}: {exc}") from exc
    if type(payload) is not dict:
        raise ValueError(f"input root must be an object: {path}")
    return payload, identity


def _write_exclusive(path: Path, payload: object) -> None:
    _reject_symlink_chain(path.parent)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite gate result: {path}")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("output parent must be an existing non-symlink directory")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(data)
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)


def _normal_path(value: object) -> str | None:
    if type(value) is not str or not value:
        return None
    return str(Path(value).absolute())


def _same_identity(recorded: object, actual: object) -> bool:
    if type(recorded) is not dict or type(actual) is not dict:
        return False
    return (
        _normal_path(recorded.get("path")) == _normal_path(actual.get("path"))
        and recorded.get("size") == actual.get("size")
        and recorded.get("sha256") == actual.get("sha256")
        and type(recorded.get("size")) is int
        and _is_sha256(recorded.get("sha256"))
    )


def _live_head(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _replay_manifest(
    manifest: dict[str, Any],
    manifest_identity: dict[str, object],
    *,
    expected_sha256: str,
) -> tuple[Path, dict[str, dict[str, object]], list[dict[str, object]]]:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"name": f"history.{name}", "passed": bool(passed), "detail": detail})

    check("manifest_sha256", manifest_identity["sha256"] == expected_sha256, manifest_identity)
    check("schema", manifest.get("schema") == EXPECTED_HISTORY_SCHEMA, manifest.get("schema"))
    check("repository_head", manifest.get("repository_head") == EXPECTED_HEAD, manifest.get("repository_head"))

    raw_root = manifest.get("repository_root")
    if type(raw_root) is not str or not raw_root:
        raise ValueError("history manifest repository_root must be a non-empty string")
    root = Path(raw_root).absolute()
    _reject_symlink_chain(root)
    check("repository_root", root.is_dir(), str(root))
    check("live_head", _live_head(root) == EXPECTED_HEAD, _live_head(root))

    scope = manifest.get("scope")
    excluded = scope.get("closeout_subtree_excluded") if type(scope) is dict else None
    declared_count = scope.get("allowlisted_history_member_count") if type(scope) is dict else None
    members = manifest.get("members")
    if type(members) is not list or not members:
        raise ValueError("history manifest members must be a non-empty list")
    check("member_count", declared_count == len(members) == 26, [declared_count, len(members)])
    check(
        "closeout_exclusion",
        type(excluded) is str and excluded.endswith("/positive-control/closeout-a001"),
        excluded,
    )

    replayed: dict[str, dict[str, object]] = {}
    for index, member in enumerate(members):
        if type(member) is not dict:
            raise ValueError(f"history manifest member {index} must be an object")
        relative_raw = member.get("path")
        if type(relative_raw) is not str or not relative_raw:
            raise ValueError(f"history manifest member {index} has invalid path")
        relative = Path(relative_raw)
        if relative.is_absolute() or ".." in relative.parts or relative_raw in replayed:
            raise ValueError(f"history manifest member {index} path is unsafe or duplicate")
        if type(excluded) is str and (relative_raw == excluded or relative_raw.startswith(f"{excluded}/")):
            raise ValueError("history manifest must not include the excluded closeout subtree")
        actual_path = (root / relative).absolute()
        if root != actual_path and root not in actual_path.parents:
            raise ValueError(f"history manifest member escapes repository root: {relative_raw}")
        actual = _identity(actual_path)
        passed = member.get("size") == actual["size"] and member.get("sha256") == actual["sha256"]
        check(f"member[{relative_raw}]", passed, actual)
        replayed[relative_raw] = actual

    for name, relative in V1_TOOL_PATHS.items():
        check(f"v1_tool_present[{name}]", relative in replayed, relative)
    return root, replayed, checks


def _member_identity(
    path_identity: dict[str, object],
    *,
    root: Path,
    members: dict[str, dict[str, object]],
) -> tuple[str | None, bool]:
    path = Path(str(path_identity["path"])).absolute()
    try:
        relative = str(path.relative_to(root))
    except ValueError:
        return None, False
    member = members.get(relative)
    return relative, _same_identity(path_identity, member)


def _arm_counts(result: dict[str, Any]) -> tuple[tuple[int, int, int], list[str]]:
    errors: list[str] = []
    ledger = result.get("ledger")
    injection = result.get("injection")
    if type(ledger) is not dict or type(injection) is not dict:
        return (-1, -1, -1), ["ledger_or_injection_missing"]

    generated = ledger.get("generated")
    compiled = injection.get("compiled_observed")
    applied = ledger.get("applied")
    values = (generated, compiled, applied)
    if any(type(value) is not int or value < 0 for value in values):
        return (-1, -1, -1), ["counts_not_nonnegative_exact_integers"]

    event_counts = ledger.get("event_counts")
    if type(event_counts) is not dict or any(type(value) is not int or value < 0 for value in event_counts.values()):
        errors.append("event_counts_invalid")
    else:
        if generated != event_counts.get("GENERATED", 0):
            errors.append("generated_count_disagrees_with_ledger")
        if applied != event_counts.get("APPLIED", 0):
            errors.append("applied_count_disagrees_with_ledger")
        if ledger.get("event_count") != sum(event_counts.values()):
            errors.append("event_count_disagrees_with_ledger")

    compiled_records = injection.get("compiled_records")
    if type(compiled_records) is not list or compiled != len(compiled_records):
        errors.append("compiled_count_disagrees_with_records")
    sample_count = injection.get("arithmetic_sample_count")
    if type(sample_count) is not int or sample_count < 0:
        errors.append("arithmetic_sample_count_invalid")
    return (generated, compiled, applied), errors


def _replay_checker_receipt(
    receipt: dict[str, Any],
    *,
    label: str,
    receipt_identity: dict[str, object],
    arm: dict[str, Any],
    arm_identity: dict[str, object],
    history_identity: dict[str, object],
    checker_identity: dict[str, object],
) -> tuple[bool, str | None, list[dict[str, object]]]:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"name": f"{label}_checker.{name}", "passed": bool(passed), "detail": detail})

    check("schema_version", receipt.get("schema_version") == 2, receipt.get("schema_version"))
    check(
        "checker_name",
        receipt.get("checker") == "independent_arithmetic_check_v2",
        receipt.get("checker"),
    )
    status = receipt.get("status")
    check(
        "status_domain",
        status in {"PASS_APPLIED_VIOLATION", "NO_APPLIED_CUT"},
        status,
    )
    semantic_checks = receipt.get("checks")
    check(
        "semantic_checks",
        semantic_checks == EXPECTED_CHECKER_SEMANTIC_CHECKS.get(status),
        semantic_checks,
    )
    check("arm", receipt.get("arm") == label, receipt.get("arm"))
    check("head", receipt.get("head") == EXPECTED_HEAD, receipt.get("head"))
    prestate = arm.get("prestate")
    expected_prestate_sha = prestate.get("incumbent_sha256") if type(prestate) is dict else None
    check("prestate_sha256", receipt.get("prestate_sha256") == expected_prestate_sha, receipt.get("prestate_sha256"))
    check(
        "checker_identity",
        _same_identity(receipt.get("checker_identity"), checker_identity),
        receipt.get("checker_identity"),
    )

    input_identities = receipt.get("input_identities")
    allowed_names = CHECKER_INPUT_NAMES | {"frozen_assignment"}
    input_schema_ok = (
        type(input_identities) is dict
        and CHECKER_INPUT_NAMES <= set(input_identities)
        and set(input_identities) <= allowed_names
    )
    check(
        "input_identity_schema", input_schema_ok, sorted(input_identities) if type(input_identities) is dict else None
    )
    if type(input_identities) is dict:
        check("arm_result_binding", _same_identity(input_identities.get("arm_result"), arm_identity), None)
        check("history_binding", _same_identity(input_identities.get("history_manifest"), history_identity), None)

        sample_recorded = arm.get("arithmetic_sample_corpus")
        sample_identity = input_identities.get("sample_corpus")
        check("sample_corpus_binding", _same_identity(sample_identity, sample_recorded), sample_identity)
        ledger = arm.get("ledger")
        ledger_path = ledger.get("path") if type(ledger) is dict else None
        if type(ledger_path) is str:
            try:
                live_ledger_identity = _identity(Path(ledger_path))
            except Exception as exc:  # noqa: BLE001 - convert drift to a failed gate check
                live_ledger_identity = {"error": f"{type(exc).__name__}: {exc}"}
        else:
            live_ledger_identity = {"error": "arm ledger path missing"}
        check(
            "ledger_segment_binding",
            _same_identity(input_identities.get("ledger_segment"), live_ledger_identity),
            live_ledger_identity,
        )

        expected_paths = {
            "mandatory_instances": PROJECT_ROOT / "data/preprocessed/mandatory_exact_instances.json",
            "candidate_placements": PROJECT_ROOT / "data/preprocessed/candidate_placements.json",
        }
        for name, expected_path in expected_paths.items():
            recorded = input_identities.get(name)
            try:
                live = _identity(expected_path)
            except Exception as exc:  # noqa: BLE001
                live = {"error": f"{type(exc).__name__}: {exc}"}
            check(f"{name}_binding", _same_identity(recorded, live), live)

        for name, recorded in input_identities.items():
            if name in {
                "arm_result",
                "history_manifest",
                "sample_corpus",
                "ledger_segment",
                "mandatory_instances",
                "candidate_placements",
            }:
                continue
            try:
                live = _identity(Path(str(recorded.get("path")))) if type(recorded) is dict else {}
            except Exception as exc:  # noqa: BLE001
                live = {"error": f"{type(exc).__name__}: {exc}"}
            check(f"{name}_binding", _same_identity(recorded, live), live)

    arm_ledger = arm.get("ledger")
    receipt_ledger = receipt.get("ledger")
    ledger_match = (
        type(arm_ledger) is dict
        and type(receipt_ledger) is dict
        and receipt_ledger.get("status") == arm_ledger.get("status") == "complete"
        and receipt_ledger.get("event_count") == arm_ledger.get("event_count")
        and receipt_ledger.get("event_counts") == arm_ledger.get("event_counts")
        and receipt_ledger.get("tail_hash") == arm_ledger.get("tail_hash")
        and receipt_ledger.get("event_counts", {}).get("APPLIED", 0) == arm_ledger.get("applied")
    )
    check("ledger_semantics", ledger_match, receipt_ledger)

    injection = arm.get("injection")
    sample_count = injection.get("arithmetic_sample_count") if type(injection) is dict else None
    applied_count = arm_ledger.get("applied") if type(arm_ledger) is dict else None
    check(
        "checked_sample_count", receipt.get("checked_sample_count") == sample_count, receipt.get("checked_sample_count")
    )
    check("applied_join_count", receipt.get("applied_join_count") == applied_count, receipt.get("applied_join_count"))

    if status == "PASS_APPLIED_VIOLATION":
        selected = receipt.get("selected")
        selected_ok = (
            type(selected) is dict
            and type(selected.get("cut_id")) is str
            and bool(selected.get("cut_id"))
            and type(selected.get("family")) is str
            and bool(selected.get("family"))
            and type(selected.get("lhs")) is int
            and type(selected.get("rhs")) is int
            and selected.get("lhs") > selected.get("rhs")
            and selected.get("active") is True
            and selected.get("violated") is True
            and _is_sha256(selected.get("plan_digest"))
            and _is_sha256(selected.get("compiled_digest"))
            and _is_sha256(selected.get("semantic_fingerprint"))
            and type(selected.get("ledger_seq")) is int
        )
        check("selected_applied_violation", selected_ok, selected)
    elif status == "NO_APPLIED_CUT":
        check("selected_absent", "selected" not in receipt or receipt.get("selected") is None, receipt.get("selected"))

    check(
        "receipt_identity",
        type(receipt_identity.get("size")) is int and _is_sha256(receipt_identity.get("sha256")),
        receipt_identity,
    )
    return all(bool(row["passed"]) for row in checks), status if type(status) is str else None, checks


def _resource_replay(
    *,
    authority_missing: bool,
    resource_receipt: dict[str, Any] | None,
    resource_identity: dict[str, object] | None,
    verifier_receipt: dict[str, Any] | None,
    verifier_receipt_identity: dict[str, object] | None,
    verifier_tool_identity: dict[str, object],
    control_identity: dict[str, object],
    treatment_identity: dict[str, object],
) -> tuple[bool, str | None, list[dict[str, object]]]:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"name": f"resource.{name}", "passed": bool(passed), "detail": detail})

    if authority_missing:
        check("authority_present", False, "resource_authority_missing")
        return False, "resource_authority_missing", checks
    if (
        resource_receipt is None
        or resource_identity is None
        or verifier_receipt is None
        or verifier_receipt_identity is None
    ):
        check("authority_present", False, "resource_input_pair_incomplete")
        return False, "resource_input_pair_incomplete", checks

    check("authority_present", True, resource_identity)
    check("receipt_schema_version", resource_receipt.get("schema_version") == 1, resource_receipt.get("schema_version"))
    check(
        "receipt_schema",
        resource_receipt.get("schema") == "noncert-cuts-positive-control-resource-receipt-v1",
        resource_receipt.get("schema"),
    )
    check(
        "receipt_head",
        resource_receipt.get("repository_head") == EXPECTED_HEAD,
        resource_receipt.get("repository_head"),
    )
    check(
        "receipt_contract",
        resource_receipt.get("contract") == EXPECTED_RESOURCE_CONTRACT,
        resource_receipt.get("contract"),
    )

    check(
        "verifier_schema_version", verifier_receipt.get("schema_version") == 1, verifier_receipt.get("schema_version")
    )
    check(
        "verifier_name",
        verifier_receipt.get("verifier") == "independent_resource_verifier_v1",
        verifier_receipt.get("verifier"),
    )
    check("verifier_status", verifier_receipt.get("status") == "PASS", verifier_receipt.get("status"))
    check(
        "verifier_head",
        verifier_receipt.get("repository_head") == EXPECTED_HEAD,
        verifier_receipt.get("repository_head"),
    )
    check(
        "verifier_contract",
        verifier_receipt.get("contract") == EXPECTED_RESOURCE_CONTRACT,
        verifier_receipt.get("contract"),
    )
    check(
        "verifier_tool_identity",
        _same_identity(verifier_receipt.get("verifier_identity"), verifier_tool_identity),
        verifier_receipt.get("verifier_identity"),
    )
    verifier_inputs = verifier_receipt.get("input_identities")
    verifier_inputs_ok = (
        type(verifier_inputs) is dict
        and set(verifier_inputs) == {"resource_receipt", "control", "treatment"}
        and _same_identity(verifier_inputs.get("resource_receipt"), resource_identity)
        and _same_identity(verifier_inputs.get("control"), control_identity)
        and _same_identity(verifier_inputs.get("treatment"), treatment_identity)
    )
    check("verifier_input_binding", verifier_inputs_ok, verifier_inputs)
    verifier_checks = verifier_receipt.get("checks")
    checks_pass = (
        type(verifier_checks) is list
        and len(verifier_checks) == len(EXPECTED_RESOURCE_VERIFIER_CHECKS)
        and {row.get("name") for row in verifier_checks if type(row) is dict} == EXPECTED_RESOURCE_VERIFIER_CHECKS
        and all(type(row) is dict and row.get("passed") is True for row in verifier_checks)
    )
    check("verifier_checks", checks_pass, verifier_checks)
    check(
        "verifier_receipt_identity",
        type(verifier_receipt_identity.get("size")) is int and _is_sha256(verifier_receipt_identity.get("sha256")),
        verifier_receipt_identity,
    )

    passed = all(bool(row["passed"]) for row in checks)
    return passed, None if passed else "resource_verification_failed", checks


def evaluate(
    *,
    control: dict[str, Any],
    control_identity: dict[str, object],
    treatment: dict[str, Any],
    treatment_identity: dict[str, object],
    control_checker: dict[str, Any],
    control_checker_identity: dict[str, object],
    treatment_checker: dict[str, Any],
    treatment_checker_identity: dict[str, object],
    history_manifest: dict[str, Any],
    history_identity: dict[str, object],
    old_receipt: dict[str, Any],
    old_receipt_identity: dict[str, object],
    old_gate: dict[str, Any],
    old_gate_identity: dict[str, object],
    checker_tool_identity: dict[str, object],
    verifier_tool_identity: dict[str, object],
    gate_tool_identity: dict[str, object],
    resource_authority_missing: bool,
    resource_receipt: dict[str, Any] | None,
    resource_identity: dict[str, object] | None,
    resource_verifier_receipt: dict[str, Any] | None,
    resource_verifier_receipt_identity: dict[str, object] | None,
    expected_history_sha256: str = EXPECTED_HISTORY_MANIFEST_SHA256,
) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    root, members, history_checks = _replay_manifest(
        history_manifest,
        history_identity,
        expected_sha256=expected_history_sha256,
    )
    checks.extend(history_checks)

    for label, identity in (
        ("control_history_member", control_identity),
        ("treatment_history_member", treatment_identity),
        ("old_receipt_history_member", old_receipt_identity),
        ("old_gate_history_member", old_gate_identity),
    ):
        relative, member_ok = _member_identity(identity, root=root, members=members)
        check(label, member_ok, relative)

    v1_runner = members.get(V1_TOOL_PATHS["runner"])
    v1_checker = members.get(V1_TOOL_PATHS["arithmetic_checker"])
    v1_gate = members.get(V1_TOOL_PATHS["gate"])
    check("v1_tools_bound", all(value is not None for value in (v1_runner, v1_checker, v1_gate)), V1_TOOL_PATHS)
    expected_tool_dir = root / "docs/research/noncert_cuts_ab_trust_20260723"
    check(
        "checker_v2_tool_path",
        _normal_path(checker_tool_identity["path"]) == str(expected_tool_dir / "independent_arithmetic_check_v2.py"),
        checker_tool_identity,
    )
    check(
        "resource_verifier_tool_path",
        _normal_path(verifier_tool_identity["path"]) == str(expected_tool_dir / "independent_resource_verifier_v1.py"),
        verifier_tool_identity,
    )
    check(
        "gate_v2_self_identity",
        _normal_path(gate_tool_identity["path"]) == str(Path(__file__).absolute()),
        gate_tool_identity,
    )

    check(
        "arm_labels",
        control.get("arm") == "control" and treatment.get("arm") == "treatment",
        [control.get("arm"), treatment.get("arm")],
    )
    check(
        "terminal_status",
        control.get("terminal_status") == "ARM_COMPLETE" and treatment.get("terminal_status") == "ARM_COMPLETE",
        [control.get("terminal_status"), treatment.get("terminal_status")],
    )
    control_authority = control.get("authority")
    treatment_authority = treatment.get("authority")
    authority_ok = (
        type(control_authority) is dict
        and control_authority == treatment_authority
        and control_authority.get("repository_head") == EXPECTED_HEAD
        and _normal_path(control_authority.get("project_root")) == str(root)
    )
    check("authority_identity", authority_ok, control_authority)
    runner_identity = (
        control_authority.get("identities", {}).get("runner")
        if type(control_authority) is dict and type(control_authority.get("identities")) is dict
        else None
    )
    check("runner_identity", _same_identity(runner_identity, v1_runner), runner_identity)

    config_ok = control.get("config") == treatment.get("config") == EXPECTED_CONFIG and control.get(
        "config_digest"
    ) == treatment.get("config_digest") == _digest(EXPECTED_CONFIG)
    check("config_exact", config_ok, [control.get("config_digest"), treatment.get("config_digest")])
    environment_ok = (
        control.get("exact_environment") == treatment.get("exact_environment") == EXPECTED_EXACT_ENVIRONMENT
    )
    check("exact_environment", environment_ok, [control.get("exact_environment"), treatment.get("exact_environment")])
    check(
        "fresh_replica_prestate",
        control.get("prestate") == treatment.get("prestate") and type(control.get("prestate")) is dict,
        None,
    )

    control_counts, control_count_errors = _arm_counts(control)
    treatment_counts, treatment_count_errors = _arm_counts(treatment)
    check("control_count_replay", not control_count_errors, {"counts": control_counts, "errors": control_count_errors})
    check(
        "treatment_count_replay",
        not treatment_count_errors,
        {"counts": treatment_counts, "errors": treatment_count_errors},
    )

    control_checker_ok, control_checker_status, control_checker_checks = _replay_checker_receipt(
        control_checker,
        label="control",
        receipt_identity=control_checker_identity,
        arm=control,
        arm_identity=control_identity,
        history_identity=history_identity,
        checker_identity=checker_tool_identity,
    )
    treatment_checker_ok, treatment_checker_status, treatment_checker_checks = _replay_checker_receipt(
        treatment_checker,
        label="treatment",
        receipt_identity=treatment_checker_identity,
        arm=treatment,
        arm_identity=treatment_identity,
        history_identity=history_identity,
        checker_identity=checker_tool_identity,
    )
    checks.extend(control_checker_checks)
    checks.extend(treatment_checker_checks)

    old_gate_inputs = old_gate.get("inputs")
    old_gate_binding = (
        old_gate.get("schema_version") == 1
        and old_gate.get("status") == "CREDIBILITY_INCOMPLETE"
        and old_gate.get("admitted") is False
        and type(old_gate_inputs) is dict
        and _same_identity(old_gate_inputs.get("control"), control_identity)
        and _same_identity(old_gate_inputs.get("treatment"), treatment_identity)
        and _same_identity(old_gate_inputs.get("arithmetic_receipt"), old_receipt_identity)
    )
    check("old_gate_semantics_and_binding", old_gate_binding, old_gate.get("status"))
    check("old_receipt_failure_preserved", old_receipt.get("status") == "FAIL", old_receipt.get("status"))

    resource_ok, resource_reason, resource_checks = _resource_replay(
        authority_missing=resource_authority_missing,
        resource_receipt=resource_receipt,
        resource_identity=resource_identity,
        verifier_receipt=resource_verifier_receipt,
        verifier_receipt_identity=resource_verifier_receipt_identity,
        verifier_tool_identity=verifier_tool_identity,
        control_identity=control_identity,
        treatment_identity=treatment_identity,
    )
    checks.extend(resource_checks)

    structural_ok = (
        all(bool(row["passed"]) for row in checks if not str(row["name"]).startswith("resource."))
        and control_checker_ok
        and treatment_checker_ok
    )
    control_zero = control_counts == (0, 0, 0)
    treatment_zero = treatment_counts == (0, 0, 0)
    treatment_positive = all(value > 0 for value in treatment_counts)
    check("control_generated_compiled_applied_zero", control_zero, control_counts)
    check(
        "observed_treatment_count_shape",
        treatment_zero or treatment_positive,
        treatment_counts,
    )

    positive = (
        structural_ok
        and resource_ok
        and control_zero
        and treatment_positive
        and control_checker_status == "NO_APPLIED_CUT"
        and treatment_checker_status == "PASS_APPLIED_VIOLATION"
    )
    negative = (
        structural_ok
        and resource_ok
        and control_zero
        and treatment_zero
        and control_checker_status == "NO_APPLIED_CUT"
        and treatment_checker_status == "NO_APPLIED_CUT"
    )
    if positive:
        status = "INJECTED_MECHANISM_POSITIVE_CONTROL"
        reason = None
    elif negative:
        status = "POSITIVE_CONTROL_NEGATIVE"
        reason = None
    else:
        status = "CREDIBILITY_INCOMPLETE"
        reason = resource_reason or "gate_requirements_failed"

    failed_checks = [str(row["name"]) for row in checks if not bool(row["passed"])]
    established: list[str]
    if positive:
        established = [
            "post_fix_typed_path_reachable",
            "audit_ledger_observed_applied",
            "one_applied_inequality_excludes_frozen_incumbent",
        ]
    elif negative:
        established = [
            "paired_gate1_run_completed_under_verified_resource_contract",
            "no_generated_compiled_or_applied_cut_observed_in_this_injected_attempt",
        ]
    else:
        established = []
    return {
        "schema_version": 2,
        "gate": "positive_control_gate_v2",
        "status": status,
        "classification_complete": positive or negative,
        "advance_authorized": positive,
        "reason": reason,
        "failed_checks": failed_checks,
        "observed_counts": {
            "control": {
                "generated": control_counts[0],
                "compiled": control_counts[1],
                "applied": control_counts[2],
            },
            "treatment": {
                "generated": treatment_counts[0],
                "compiled": treatment_counts[1],
                "applied": treatment_counts[2],
            },
        },
        "claim_boundary": {
            "established": established,
            "not_established": [
                "cut_global_soundness",
                "organic_runtime_usefulness",
                "single_family_usefulness",
                "pic4_or_pic5_closed",
                "b6_authorized",
                "unsat_or_infeasibility_proof",
                "witness_or_lower_bound",
            ],
        },
        "tool_identities": {
            "v1_runner": v1_runner,
            "v1_arithmetic_checker": v1_checker,
            "v1_gate": v1_gate,
            "v2_arithmetic_checker": checker_tool_identity,
            "resource_verifier": verifier_tool_identity,
            "gate_v2": gate_tool_identity,
        },
        "checks": checks,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--treatment", type=Path, required=True)
    parser.add_argument(
        "--control-checker-receipt",
        "--control-receipt",
        dest="control_checker_receipt",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--treatment-checker-receipt",
        "--treatment-receipt",
        dest="treatment_checker_receipt",
        type=Path,
        required=True,
    )
    parser.add_argument("--history-manifest", type=Path, required=True)
    parser.add_argument(
        "--v1-arithmetic-receipt",
        "--legacy-arithmetic-receipt",
        dest="v1_arithmetic_receipt",
        type=Path,
        required=True,
    )
    parser.add_argument("--v1-gate", "--legacy-gate", dest="v1_gate", type=Path, required=True)
    parser.add_argument("--checker-v2-tool", type=Path, required=True)
    parser.add_argument("--resource-verifier-tool", type=Path, required=True)
    resource_mode = parser.add_mutually_exclusive_group(required=True)
    resource_mode.add_argument("--resource-authority-missing", action="store_true")
    resource_mode.add_argument("--resource-receipt", type=Path)
    parser.add_argument("--resource-verifier-receipt", type=Path)
    parser.add_argument(
        "--expected-history-manifest-sha256",
        default=EXPECTED_HISTORY_MANIFEST_SHA256,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.resource_authority_missing and args.resource_verifier_receipt is not None:
        parser.error("--resource-authority-missing cannot be combined with --resource-verifier-receipt")
    if args.resource_receipt is not None and args.resource_verifier_receipt is None:
        parser.error("--resource-receipt requires --resource-verifier-receipt")
    return args


def main() -> int:
    args = _parse_args()
    inputs: dict[str, object] = {}
    try:
        control, control_identity = _read_json(args.control)
        inputs["control"] = control_identity
        treatment, treatment_identity = _read_json(args.treatment)
        inputs["treatment"] = treatment_identity
        control_checker, control_checker_identity = _read_json(args.control_checker_receipt)
        inputs["control_checker_receipt"] = control_checker_identity
        treatment_checker, treatment_checker_identity = _read_json(args.treatment_checker_receipt)
        inputs["treatment_checker_receipt"] = treatment_checker_identity
        history, history_identity = _read_json(args.history_manifest)
        inputs["history_manifest"] = history_identity
        old_receipt, old_receipt_identity = _read_json(args.v1_arithmetic_receipt)
        inputs["v1_arithmetic_receipt"] = old_receipt_identity
        old_gate, old_gate_identity = _read_json(args.v1_gate)
        inputs["v1_gate"] = old_gate_identity

        checker_tool_identity = _identity(args.checker_v2_tool)
        verifier_tool_identity = _identity(args.resource_verifier_tool)
        gate_tool_identity = _identity(Path(__file__).resolve())

        resource_receipt: dict[str, Any] | None = None
        resource_identity: dict[str, object] | None = None
        resource_verifier_receipt: dict[str, Any] | None = None
        resource_verifier_receipt_identity: dict[str, object] | None = None
        if args.resource_receipt is not None:
            resource_receipt, resource_identity = _read_json(args.resource_receipt)
            inputs["resource_receipt"] = resource_identity
            resource_verifier_receipt, resource_verifier_receipt_identity = _read_json(args.resource_verifier_receipt)
            inputs["resource_verifier_receipt"] = resource_verifier_receipt_identity

        result = evaluate(
            control=control,
            control_identity=control_identity,
            treatment=treatment,
            treatment_identity=treatment_identity,
            control_checker=control_checker,
            control_checker_identity=control_checker_identity,
            treatment_checker=treatment_checker,
            treatment_checker_identity=treatment_checker_identity,
            history_manifest=history,
            history_identity=history_identity,
            old_receipt=old_receipt,
            old_receipt_identity=old_receipt_identity,
            old_gate=old_gate,
            old_gate_identity=old_gate_identity,
            checker_tool_identity=checker_tool_identity,
            verifier_tool_identity=verifier_tool_identity,
            gate_tool_identity=gate_tool_identity,
            resource_authority_missing=args.resource_authority_missing,
            resource_receipt=resource_receipt,
            resource_identity=resource_identity,
            resource_verifier_receipt=resource_verifier_receipt,
            resource_verifier_receipt_identity=resource_verifier_receipt_identity,
            expected_history_sha256=args.expected_history_manifest_sha256,
        )
        result["inputs"] = inputs
        exit_code = 0 if result["classification_complete"] else 2
    except Exception as exc:  # noqa: BLE001 - fail-closed gate record
        result = {
            "schema_version": 2,
            "gate": "positive_control_gate_v2",
            "status": "CREDIBILITY_INCOMPLETE",
            "classification_complete": False,
            "advance_authorized": False,
            "reason": "gate_exception",
            "error": f"{type(exc).__name__}: {exc}",
            "inputs": inputs,
        }
        exit_code = 2
    _write_exclusive(args.output, result)
    print(json.dumps(result, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
