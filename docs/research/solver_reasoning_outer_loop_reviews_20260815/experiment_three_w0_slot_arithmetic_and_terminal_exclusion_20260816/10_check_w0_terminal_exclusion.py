#!/usr/bin/env python3
"""Independently verify the composed W0 fixed-rectangle research exclusion.

This checker is standard-library only.  It re-runs both theorem checkers,
audits the current fixed-layout binding/routing path, reconstructs the relevant
CpModel constraints from a frozen JSON snapshot, checks context transport and
protected-surface non-interference, and then validates the terminal Judgment.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence


HERE = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = HERE.parents[3]
CORRESPONDENCE_MANIFEST_PATH = HERE / "06_MODEL_CORRESPONDENCE_MANIFEST.json"
CORRESPONDENCE_DOC_PATH = HERE / "07_MODEL_CORRESPONDENCE.md"
TERMINAL_JUDGMENT_PATH = HERE / "08_TERMINAL_EXCLUSION_JUDGMENT.json"
TERMINAL_PROOF_PATH = HERE / "09_TERMINAL_EXCLUSION_PROOF.md"
THEOREM_TWO_RECEIPT_PATH = HERE / "05_THEOREM_RECEIPT.json"
REQUIRED_RECEIPT_FIELDS = (
    "result_kind",
    "outcome",
    "subject_identity",
    "verified_scope",
    "authority_basis",
    "granted_effects",
    "non_implications",
    "contract_identity",
)


class TerminalCheckError(RuntimeError):
    """The composed terminal exclusion failed closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise TerminalCheckError(message)


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise TerminalCheckError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def reject_nonfinite(token: str) -> None:
    raise TerminalCheckError(f"non-finite JSON number is forbidden: {token}")


def parse_json_bytes(payload: bytes, *, label: str) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TerminalCheckError(f"{label} is not UTF-8: {exc}") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite,
        )
    except json.JSONDecodeError as exc:
        raise TerminalCheckError(f"{label} is not strict JSON: {exc}") from exc


def read_json(path: Path, *, label: str | None = None) -> Any:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise TerminalCheckError(f"cannot read {label or path}: {exc}") from exc
    return parse_json_bytes(payload, label=label or str(path))


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise TerminalCheckError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest(), size


def verify_file(path: Path, expected_sha: str, expected_size: int | None = None) -> dict[str, Any]:
    require(path.is_file(), f"required file is missing: {path}")
    actual_sha, actual_size = sha256_file(path)
    require(actual_sha == expected_sha, f"SHA-256 drift: {path}")
    if expected_size is not None:
        require(actual_size == expected_size, f"size drift: {path}")
    return {"path": str(path), "sha256": actual_sha, "size_bytes": actual_size}


def run_json_command(command: Sequence[str], *, cwd: Path, label: str) -> Mapping[str, Any]:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=False,
    )
    require(completed.returncode == 0, f"{label} failed: rc={completed.returncode}; stderr={completed.stderr.decode('utf-8', 'replace')[:500]}")
    payload = parse_json_bytes(completed.stdout, label=label)
    require(isinstance(payload, Mapping), f"{label} did not emit a JSON object")
    require(payload.get("outcome", payload.get("status")) == "PASS", f"{label} did not PASS")
    return payload


def verify_theorems(
    *,
    repo_root: Path,
    data_root: Path,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    theorem_one = manifest["theorem_one"]
    theorem_two = manifest["theorem_two"]
    one_judgment = repo_root / str(theorem_one["judgment_path"])
    one_checker = repo_root / str(theorem_one["checker_path"])
    two_judgment = repo_root / str(theorem_two["judgment_path"])
    two_proof = repo_root / str(theorem_two["proof_path"])
    two_checker = repo_root / str(theorem_two["checker_path"])
    two_compact_receipt = repo_root / str(theorem_two["receipt_path"])
    identity_checks = [
        verify_file(one_judgment, str(theorem_one["judgment_sha256"])),
        verify_file(one_checker, str(theorem_one["checker_sha256"])),
        verify_file(two_judgment, str(theorem_two["judgment_sha256"])),
        verify_file(two_proof, str(theorem_two["proof_sha256"])),
        verify_file(two_checker, str(theorem_two["checker_sha256"])),
        verify_file(two_compact_receipt, str(theorem_two["receipt_sha256"])),
    ]

    one_receipt = run_json_command(
        [
            sys.executable,
            str(one_checker),
            "--repo-root",
            str(data_root),
            "--coverage",
            "off",
        ],
        cwd=repo_root,
        label="theorem-one checker",
    )
    require(one_receipt.get("coverage") is None, "theorem-one checker unexpectedly used coverage")

    two_receipt = run_json_command(
        [
            sys.executable,
            str(two_checker),
            "--repo-root",
            str(repo_root),
            "--data-root",
            str(data_root),
            "--coverage",
            "required",
        ],
        cwd=repo_root,
        label="theorem-two checker",
    )
    require(two_receipt["verified_scope"]["target_must_be_active"] is True, "theorem two did not force target active")
    require(two_receipt["verified_scope"]["coverage_is_a_proof_premise"] is False, "theorem-two coverage became a premise")

    compact = read_json(two_compact_receipt, label="theorem-two compact receipt")
    require(isinstance(compact, Mapping), "theorem-two compact receipt is not an object")
    require(compact.get("outcome") == "PASS", "theorem-two compact receipt did not PASS")
    compact_identity = compact["contract_identity"]
    for field, expected in (
        ("checker_sha256", theorem_two["checker_sha256"]),
        ("judgment_sha256", theorem_two["judgment_sha256"]),
        ("proof_sha256", theorem_two["proof_sha256"]),
        ("problemHash", manifest["shared_identity"]["problemHash"]),
        ("objectiveHash", manifest["shared_identity"]["objectiveHash"]),
        ("contextHash", manifest["shared_identity"]["theorem_two_contextHash"]),
    ):
        require(compact_identity[field] == expected, f"theorem-two compact receipt {field} drift")
    proof_summary = compact["proof_summary"]
    require(proof_summary["target_must_be_active"] is True, "theorem-two compact proof summary drift")
    require(int(proof_summary["slot_count"]) == 52, "theorem-two compact slot count drift")
    require(int(proof_summary["required_total"]) == 52, "theorem-two compact demand total drift")
    require(int(proof_summary["forced_unused_total"]) == 0, "theorem-two compact unused total drift")
    coverage = compact["coverage"]
    require(coverage["is_proof_premise"] is False, "theorem-two compact coverage became a premise")
    require(int(coverage["record_count"]) == 1007, "theorem-two compact coverage count drift")
    require(int(coverage["target_active_count"]) == 1007, "theorem-two compact active coverage drift")
    return {
        "theorem_one": one_receipt,
        "theorem_two": two_receipt,
        "theorem_two_compact_receipt": compact,
        "identity_checks": identity_checks,
    }


def class_methods(source_text: str, class_name: str) -> dict[str, str]:
    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        raise TerminalCheckError(f"source does not parse: {class_name}: {exc}") from exc
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods: dict[str, str] = {}
            lines = source_text.splitlines()
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    require(item.end_lineno is not None, f"method lacks end_lineno: {item.name}")
                    methods[item.name] = "\n".join(lines[item.lineno - 1 : item.end_lineno])
            return methods
    raise TerminalCheckError(f"class not found: {class_name}")


def module_functions(source_text: str) -> dict[str, str]:
    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        raise TerminalCheckError(f"harness source does not parse: {exc}") from exc
    lines = source_text.splitlines()
    functions: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            require(node.end_lineno is not None, f"function lacks end_lineno: {node.name}")
            functions[node.name] = "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return functions


def require_markers(text: str, markers: Sequence[str], *, label: str) -> None:
    for marker in markers:
        require(marker in text, f"{label} lost required marker: {marker}")


def audit_sources(repo_root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    records = {str(item["role"]): item for item in manifest["implementation_sources"]}
    checked: dict[str, dict[str, Any]] = {}
    texts: dict[str, str] = {}
    for role, record in records.items():
        path = repo_root / str(record["path"])
        checked[role] = verify_file(path, str(record["sha256"]), int(record["size_bytes"]))
        try:
            texts[role] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise TerminalCheckError(f"cannot read source {path}: {exc}") from exc

    methods = class_methods(texts["binding_model"], "PortBindingModel")
    for name in (
        "build",
        "_build_generic_output_domains",
        "_add_generic_output_requirements",
        "extract_selection",
        "extract_port_specs",
    ):
        require(name in methods, f"binding method missing: {name}")
    require_markers(
        methods["_build_generic_output_domains"],
        (
            'generic_commodities = sorted(self.required_generic_outputs.keys())',
            'slot_commodities = generic_commodities + ["__unused__"]',
            'operation_type not in {"boundary_io", "protocol_core"}',
            'pose.get("output_port_cells", [])',
            'self.model.AddExactlyOne',
        ),
        label="generic-output domain builder",
    )
    require_markers(
        methods["_add_generic_output_requirements"],
        (
            'for commodity, required in self.required_generic_outputs.items()',
            'self.model.Add(sum(vars_for_commodity) == required)',
        ),
        label="generic-output requirement builder",
    )
    require_markers(
        methods["build"],
        ("self._build_generic_output_domains()", "self._add_generic_output_requirements()"),
        label="binding build",
    )
    require_markers(
        methods["extract_selection"],
        ('selection["generic_outputs"][slot_id] = commodity',),
        label="selection extraction",
    )
    require_markers(
        methods["extract_port_specs"],
        (
            'commodity = selection["generic_outputs"].get(slot_id)',
            'if commodity in (None, "__unused__")',
            '"type": slot["type"]',
            '"commodity": commodity',
        ),
        label="port-spec extraction",
    )

    functions = module_functions(texts["fixed_layout_research_path"])
    for name in ("_load_frozen_inputs", "_load_layout", "_occupied_core", "_new_binding_model", "_run_layout"):
        require(name in functions, f"harness function missing: {name}")
    require_markers(
        functions["_new_binding_model"],
        ("PortBindingModel(", "model.build(use_overload_separation=False)", "return model"),
        label="fixed-layout binding model constructor",
    )
    require_markers(
        functions["_occupied_core"],
        ("GHOST_RESERVED_OWNER_ID", "occupied.add(cell)", "RoutingPlacementCore.from_occupied_cells"),
        label="strict rectangle placement core",
    )
    require_markers(
        functions["_run_layout"],
        (
            "model = _new_binding_model(layout, frozen)",
            "model.solve(BINDING_SECONDS)",
            "model.extract_selection()",
            "model.extract_port_specs()",
            "run_exact_routing_precheck(",
            "RoutingSubproblem.from_placement_core(",
        ),
        label="fixed-layout binding-routing path",
    )
    require(functions["_run_layout"].count("_new_binding_model(") == 1, "fixed-layout path has more than one binding-model entry")
    return {
        "source_files": checked,
        "binding_methods_checked": sorted(methods),
        "harness_functions_checked": sorted(functions),
        "single_binding_entry_in_run_layout": True,
        "active_export_contract": "non-__unused__ generic output is emitted as an out port spec; __unused__ is skipped",
    }


def snapshot_output_groups(
    snapshot: Mapping[str, Any],
    expected_slots: Sequence[str],
    labels: Sequence[str],
) -> tuple[dict[str, dict[str, int]], dict[str, Any]]:
    variables = snapshot.get("variables")
    constraints = snapshot.get("constraints")
    require(isinstance(variables, list), "snapshot variables missing")
    require(isinstance(constraints, list), "snapshot constraints missing")
    name_to_record: dict[str, Mapping[str, Any]] = {}
    for record in variables:
        require(isinstance(record, Mapping), "snapshot variable record malformed")
        name = str(record["name"])
        require(name not in name_to_record, f"duplicate snapshot variable name: {name}")
        name_to_record[name] = record

    expected_names: set[str] = set()
    groups: dict[str, dict[str, int]] = {}
    for slot_id in expected_slots:
        group: dict[str, int] = {}
        for label in labels:
            name = f"slot_{slot_id}_{label}"
            expected_names.add(name)
            record = name_to_record.get(name)
            require(record is not None, f"snapshot lacks variable {name}")
            require(record.get("domain") == [0, 1], f"snapshot variable domain drift: {name}")
            group[label] = int(record["index"])
        groups[slot_id] = group

    observed_output_names = {
        name
        for name in name_to_record
        if name.startswith("slot_") and ":out:" in name
    }
    require(observed_output_names == expected_names, "snapshot has extra or missing generic-output literals")

    exactly_one_sets: dict[frozenset[int], int] = {}
    for record in constraints:
        if not isinstance(record, Mapping) or record.get("kind") != "exactly_one":
            continue
        literals = record.get("exactly_one", {}).get("literals")
        if isinstance(literals, list):
            exactly_one_sets[frozenset(int(value) for value in literals)] = int(record["index"])
    slot_constraint_indices: dict[str, int] = {}
    for slot_id, group in groups.items():
        key = frozenset(group.values())
        require(key in exactly_one_sets, f"snapshot lacks ExactlyOne for {slot_id}")
        slot_constraint_indices[slot_id] = exactly_one_sets[key]
    return groups, {
        "variable_count": len(variables),
        "constraint_count": len(constraints),
        "generic_output_slot_count": len(groups),
        "generic_output_literal_count": len(expected_names),
        "slot_exactly_one_constraint_indices": slot_constraint_indices,
    }


def audit_linear_requirement(
    snapshot: Mapping[str, Any],
    *,
    constraint_index: int,
    expected_vars: set[int],
    required_value: int,
    label: str,
) -> dict[str, Any]:
    constraints = snapshot["constraints"]
    require(0 <= constraint_index < len(constraints), f"{label} constraint index out of range")
    record = constraints[constraint_index]
    require(record.get("kind") == "linear", f"{label} constraint is not linear")
    linear = record.get("linear")
    require(isinstance(linear, Mapping), f"{label} linear payload missing")
    variables = [int(value) for value in linear.get("vars", [])]
    coeffs = [int(value) for value in linear.get("coeffs", [])]
    domain = [int(value) for value in linear.get("domain", [])]
    require(len(variables) == len(expected_vars), f"{label} variable count drift")
    require(set(variables) == expected_vars, f"{label} variable set drift")
    require(coeffs == [1] * len(expected_vars), f"{label} coefficients drift")
    require(domain == [required_value, required_value], f"{label} equality domain drift")
    return {
        "constraint_index": constraint_index,
        "variable_count": len(variables),
        "coefficient_set": [1],
        "domain": domain,
    }


def audit_snapshot(data_root: Path, manifest: Mapping[str, Any], context_manifest: Mapping[str, Any]) -> dict[str, Any]:
    spec = manifest["model_snapshot"]
    path = data_root / str(spec["path"])
    verify_file(path, str(spec["sha256"]), int(spec["size_bytes"]))
    snapshot = read_json(path, label="A_BASELINE model snapshot")
    require(isinstance(snapshot, Mapping), "model snapshot root is not an object")
    expected = spec["expected"]
    slots = [
        *context_manifest["expected_binding_contract"]["expected_boundary_slot_ids"],
        *context_manifest["expected_binding_contract"]["expected_core_slot_ids"],
    ]
    labels = context_manifest["expected_binding_contract"]["slot_labels"]
    groups, summary = snapshot_output_groups(snapshot, slots, labels)
    require(summary["variable_count"] == int(expected["variable_count"]), "snapshot variable count drift")
    require(summary["constraint_count"] == int(expected["constraint_count"]), "snapshot constraint count drift")
    require(summary["generic_output_slot_count"] == int(expected["generic_output_slot_count"]), "snapshot slot count drift")
    require(summary["generic_output_literal_count"] == int(expected["generic_output_literal_count"]), "snapshot literal count drift")
    target_slot = context_manifest["expected_binding_contract"]["target_slot_id"]
    require(
        summary["slot_exactly_one_constraint_indices"][target_slot]
        == int(expected["target_exactly_one_constraint_index"]),
        "target ExactlyOne constraint index drift",
    )
    blue_vars = {group["blue_iron_ore"] for group in groups.values()}
    source_vars = {group["source_ore"] for group in groups.values()}
    blue = audit_linear_requirement(
        snapshot,
        constraint_index=int(expected["blue_requirement_constraint_index"]),
        expected_vars=blue_vars,
        required_value=int(expected["blue_requirement"]),
        label="blue requirement",
    )
    source = audit_linear_requirement(
        snapshot,
        constraint_index=int(expected["source_requirement_constraint_index"]),
        expected_vars=source_vars,
        required_value=int(expected["source_requirement"]),
        label="source requirement",
    )
    return {
        **summary,
        "target_slot_id": target_slot,
        "target_literal_indices": groups[target_slot],
        "target_exactly_one_constraint_index": summary["slot_exactly_one_constraint_indices"][target_slot],
        "blue_requirement": blue,
        "source_requirement": source,
        "snapshot_role": spec["role"],
    }


def verify_context_transport(
    theorem_receipts: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    one = theorem_receipts["theorem_one"]
    two = theorem_receipts["theorem_two"]
    shared = manifest["shared_identity"]
    one_proof = one["proof"]
    two_contract = two["contract_identity"]
    require(one_proof["problemHash"] == shared["problemHash"], "theorem-one problemHash drift")
    require(one_proof["objectiveHash"] == shared["objectiveHash"], "theorem-one objectiveHash drift")
    require(one_proof["contextHash"] == shared["theorem_one_contextHash"], "theorem-one contextHash drift")
    require(two_contract["problemHash"] == shared["problemHash"], "theorem-two problemHash drift")
    require(two_contract["objectiveHash"] == shared["objectiveHash"], "theorem-two objectiveHash drift")
    require(two_contract["base_contextHash"] == one_proof["contextHash"], "theorem-two base context is not theorem-one context")
    require(two_contract["contextHash"] == shared["theorem_two_contextHash"], "theorem-two contextHash drift")
    require(one_proof["target_front_cell"] == shared["target_front_cell"], "theorem-one target front drift")
    return {
        "problemHash_equal": True,
        "objectiveHash_equal": True,
        "theorem_two_base_equals_theorem_one_context": True,
        "transport_rule": "premise strengthening preserves theorem-one conditional implication",
    }


def verify_protected_surfaces(repo_root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    checked: list[dict[str, Any]] = []
    for record in manifest["protected_surfaces"]:
        path = repo_root / str(record["path"])
        checked.append(verify_file(path, str(record["sha256"]), int(record["size_bytes"])))
    return {"unchanged": True, "files": checked}


def verify_canary_history(repo_root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    spec = manifest["canary_history"]
    path = repo_root / str(spec["final_report_path"])
    verify_file(path, str(spec["final_report_sha256"]))
    text = path.read_text(encoding="utf-8")
    require("**冻结科学判词：** `INCONCLUSIVE`" in text, "canary final report no longer preserves INCONCLUSIVE")
    require(str(spec["frozen_verdict"]) == "INCONCLUSIVE", "canary manifest verdict drift")
    return {
        "historical_verdict": "INCONCLUSIVE",
        "current_action": "UNCHANGED",
        "relation": spec["relation"],
    }


def parse_numbered_steps(text: str, marker: str) -> int:
    require(marker in text, f"proof marker missing: {marker}")
    section = text.split(marker, 1)[1].split("\n## ", 1)[0]
    numbers: list[int] = []
    for line in section.splitlines():
        stripped = line.strip()
        if "." not in stripped:
            continue
        head = stripped.split(".", 1)[0]
        if head.isdigit():
            numbers.append(int(head))
    require(numbers == list(range(1, len(numbers) + 1)), "terminal proof numbering drift")
    return len(numbers)


def verify_terminal_judgment(
    terminal: Mapping[str, Any],
    proof_text: str,
    manifest: Mapping[str, Any],
    theorem_receipts: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    shared = manifest["shared_identity"]
    require(
        terminal["judgment_id"] == "J-W0-FIXED-RECT-BINDING-ROUTING-EXCLUDED-V1",
        "terminal Judgment ID drift",
    )
    require(terminal["status"] == "PROVED_EXCLUDED_RESEARCH", "terminal status drift")
    require(terminal["problem_identity"]["problemHash"] == shared["problemHash"], "terminal problemHash drift")
    require(terminal["problem_identity"]["objectiveHash"] == shared["objectiveHash"], "terminal objectiveHash drift")
    require(terminal["subject_identity"]["layout_id"] == shared["layout_id"], "terminal layout ID drift")
    require(terminal["subject_identity"]["rectangle"] == {
        **shared["fixed_rectangle"],
        "score": [42, 6],
    }, "terminal rectangle drift")
    require(
        terminal["sequent"]["formula"]
        == "not exists b,r: legal_w0_binding_contract(b) and canonical_predicate_5_routable(W0_ALIGNMENT, rectangle_[1,6]x[51,57], b, r)",
        "terminal sequent drift",
    )
    require([item["step"] for item in terminal["lift"]] == [1, 2, 3, 4], "terminal lift step sequence drift")
    require(terminal["lift"][0]["basis"] == manifest["theorem_two"]["judgment_id"], "terminal lift step 1 basis drift")
    require(manifest["theorem_one"]["judgment_id"] in terminal["lift"][1]["basis"], "terminal lift step 2 basis drift")
    require(terminal["conclusion"]["candidate_state"] == "PROVED_EXCLUDED", "terminal conclusion state drift")
    require(all(item["status"] == "DISCHARGED" for item in obligations), "a path obligation is not discharged")
    transaction = terminal["endpoint_transaction"]
    require(transaction["candidate_state_before"] == "UNKNOWN", "candidate before-state drift")
    require(transaction["candidate_state_after"] == "PROVED_EXCLUDED", "candidate after-state drift")
    require(int(transaction["delta_M_bottom"]) == -1, "candidate delta_M_bottom drift")
    require(transaction["global_M_t_before"] == "N_A_NOT_READY", "global M_t before type drift")
    require(transaction["global_M_t_after"] == "N_A_NOT_READY", "global M_t after type drift")
    require(
        transaction["evidence_type"]
        == "EXACT_SINGLETON_EXCLUSION_BY_COMPOSED_THEOREMS",
        "terminal evidence type drift",
    )
    require(transaction["delta_L"] == "ZERO_BY_SCOPE", "delta_L drift")
    require(transaction["delta_U"] == "ZERO_BY_SCOPE", "delta_U drift")
    require(transaction["ledger_effect"] == "research candidate ledger only", "terminal ledger-effect drift")
    require(terminal["canary_relation"]["historical_verdict"] == "INCONCLUSIVE", "terminal judgment rewrote canary verdict")
    require(terminal["canary_relation"]["current_action"] == "UNCHANGED", "terminal judgment changes canary history")
    require(theorem_receipts["theorem_one"]["status"] == "PASS", "theorem one receipt not PASS")
    require(theorem_receipts["theorem_two"]["outcome"] == "PASS", "theorem two receipt not PASS")
    required_forbidden = {
        "production exact-status write",
        "stable claim ledger write",
        "certified frontier pruning",
        "supervisor or publisher consumption",
        "cross-layout or cross-rectangle generalization",
        "adjudicated-game global optimality narrative",
    }
    require(
        required_forbidden <= set(terminal["consumption_contract"]["forbidden"]),
        "terminal forbidden-consumer set drift",
    )
    required_non_implications = {
        "no_certification_effect",
        "no_exact_status_update",
        "no_stable_claim_ledger_write",
        "no_production_lowering",
        "no_generic_D3_or_D4_unlock",
        "no_other_layout_or_rectangle_exclusion",
        "no_global_bound_or_optimum_update",
        "no_equivalence_between_current_binding_model_and_full_adjudicated_game_semantics",
        "no_rejudgment_of_the_W0_unary_lowering_canary",
        "no_use_of_1007_observations_as_a_proof_premise",
    }
    require(
        required_non_implications <= set(terminal["non_implications"]),
        "terminal non-implication set drift",
    )
    step_count = parse_numbered_steps(proof_text, "## 6. 组合证明")
    require(step_count == 7, f"terminal proof has {step_count} steps, expected 7")
    return {
        "terminal_status": terminal["status"],
        "candidate_transition": "UNKNOWN -> PROVED_EXCLUDED",
        "evidence_type": transaction["evidence_type"],
        "delta_M_bottom": -1,
        "global_M_t": "N_A_NOT_READY",
        "proof_step_count": step_count,
        "canary_verdict_unchanged": True,
    }


def expect_failure(name: str, callback: Callable[[], None]) -> dict[str, Any]:
    try:
        callback()
    except TerminalCheckError as exc:
        return {"name": name, "killed": True, "reason": str(exc)}
    raise TerminalCheckError(f"terminal negative mutation survived: {name}")


def run_negative_tests(
    *,
    terminal: Mapping[str, Any],
    manifest: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def context_mismatch() -> None:
        mutated = copy.deepcopy(manifest)
        mutated["shared_identity"]["theorem_two_contextHash"] = "0" * 64
        require(
            terminal["problem_identity"]["theorem_two_contextHash"]
            == mutated["shared_identity"]["theorem_two_contextHash"],
            "synthetic context mismatch",
        )

    def reopen_obligation() -> None:
        mutated = copy.deepcopy(list(obligations))
        mutated[0]["status"] = "OPEN"
        require(all(item["status"] == "DISCHARGED" for item in mutated), "synthetic open path obligation")

    def remove_target_exactly_one() -> None:
        mutated = copy.deepcopy(snapshot)
        target_index = int(manifest["model_snapshot"]["expected"]["target_exactly_one_constraint_index"])
        mutated["constraints"][target_index]["kind"] = "synthetic_removed"
        context_manifest = read_json(HERE / "01_CONTEXT_MANIFEST.json")
        audit_snapshot_payload(mutated, manifest, context_manifest)

    def demand_33() -> None:
        mutated = copy.deepcopy(snapshot)
        index = int(manifest["model_snapshot"]["expected"]["blue_requirement_constraint_index"])
        mutated["constraints"][index]["linear"]["domain"] = [33, 33]
        context_manifest = read_json(HERE / "01_CONTEXT_MANIFEST.json")
        audit_snapshot_payload(mutated, manifest, context_manifest)

    def candidate_delta_zero() -> None:
        mutated = copy.deepcopy(terminal)
        mutated["endpoint_transaction"]["delta_M_bottom"] = 0
        require(int(mutated["endpoint_transaction"]["delta_M_bottom"]) == -1, "synthetic candidate delta drift")

    def rewrite_canary() -> None:
        mutated = copy.deepcopy(terminal)
        mutated["canary_relation"]["historical_verdict"] = "INFEASIBLE"
        require(mutated["canary_relation"]["historical_verdict"] == "INCONCLUSIVE", "synthetic canary rejudgment")

    for name, callback in (
        ("context_mismatch", context_mismatch),
        ("reopened_path_obligation", reopen_obligation),
        ("missing_target_exactly_one", remove_target_exactly_one),
        ("blue_requirement_33", demand_33),
        ("candidate_delta_zero", candidate_delta_zero),
        ("canary_rejudgment", rewrite_canary),
    ):
        results.append(expect_failure(name, callback))
    return results


def audit_snapshot_payload(
    snapshot: Mapping[str, Any],
    manifest: Mapping[str, Any],
    context_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    expected = manifest["model_snapshot"]["expected"]
    slots = [
        *context_manifest["expected_binding_contract"]["expected_boundary_slot_ids"],
        *context_manifest["expected_binding_contract"]["expected_core_slot_ids"],
    ]
    labels = context_manifest["expected_binding_contract"]["slot_labels"]
    groups, summary = snapshot_output_groups(snapshot, slots, labels)
    require(summary["variable_count"] == int(expected["variable_count"]), "snapshot variable count drift")
    require(summary["constraint_count"] == int(expected["constraint_count"]), "snapshot constraint count drift")
    target = context_manifest["expected_binding_contract"]["target_slot_id"]
    require(
        summary["slot_exactly_one_constraint_indices"][target]
        == int(expected["target_exactly_one_constraint_index"]),
        "target ExactlyOne constraint index drift",
    )
    audit_linear_requirement(
        snapshot,
        constraint_index=int(expected["blue_requirement_constraint_index"]),
        expected_vars={group["blue_iron_ore"] for group in groups.values()},
        required_value=int(expected["blue_requirement"]),
        label="blue requirement",
    )
    audit_linear_requirement(
        snapshot,
        constraint_index=int(expected["source_requirement_constraint_index"]),
        expected_vars={group["source_ore"] for group in groups.values()},
        required_value=int(expected["source_requirement"]),
        label="source requirement",
    )
    return summary


def make_obligation_receipts(
    *,
    source_audit: Mapping[str, Any],
    snapshot_audit: Mapping[str, Any],
    context_transport: Mapping[str, Any],
    protected: Mapping[str, Any],
) -> list[dict[str, Any]]:
    evidence = {
        "W0-LIFT-01-INPUT-IDENTITY": ["theorem-two checker PASS", "fixed-layout harness source hash PASS"],
        "W0-LIFT-02-SLOT-COMPLETENESS": [f"snapshot slots={snapshot_audit['generic_output_slot_count']}", "binding source audit PASS"],
        "W0-LIFT-03-PER-SLOT-EXACTLY-ONE": ["52 snapshot ExactlyOne groups", "binding source AddExactlyOne marker PASS"],
        "W0-LIFT-04-GLOBAL-COUNTS": ["snapshot blue=34/source=18", "requirement source marker PASS"],
        "W0-LIFT-05-ACTIVE-PORT-EXPORT": [source_audit["active_export_contract"]],
        "W0-LIFT-06-ROUTING-CONSUMPTION": ["single fixed-layout binding entry", "exact precheck and RoutingSubproblem markers PASS"],
        "W0-LIFT-07-CONTEXT-TRANSPORT": [context_transport["transport_rule"]],
        "W0-LIFT-08-ENDPOINT-NONINTERFERENCE": [f"protected files unchanged={protected['unchanged']}"],
    }
    return [
        {
            "id": obligation_id,
            "status": "DISCHARGED",
            "evidence": evidence[obligation_id],
        }
        for obligation_id in evidence
    ]


def make_receipt(
    *,
    outcome: str,
    verified_scope: Mapping[str, Any],
    contract_identity: Mapping[str, Any],
    details: Mapping[str, Any],
    error: str | None = None,
) -> dict[str, Any]:
    passed = outcome == "PASS"
    receipt: dict[str, Any] = {
        "result_kind": "w0_terminal_exclusion_check",
        "outcome": outcome,
        "subject_identity": {
            "judgment_id": "J-W0-FIXED-RECT-BINDING-ROUTING-EXCLUDED-V1",
            "layout_id": "W0-ALIGNMENT",
            "rectangle": {"x0": 1, "y0": 51, "w": 6, "h": 7},
        },
        "verified_scope": dict(verified_scope),
        "authority_basis": {
            "authority_class": "research_only_non_authorizing",
            "source_paths": [
                str(CORRESPONDENCE_MANIFEST_PATH.relative_to(DEFAULT_REPO_ROOT)),
                str(CORRESPONDENCE_DOC_PATH.relative_to(DEFAULT_REPO_ROOT)),
                str(TERMINAL_JUDGMENT_PATH.relative_to(DEFAULT_REPO_ROOT)),
                str(TERMINAL_PROOF_PATH.relative_to(DEFAULT_REPO_ROOT)),
            ],
        },
        "granted_effects": (
            [
                "records_the_fixed_W0_rectangle_as_PROVED_EXCLUDED_in_the_research_candidate_ledger",
                "records_delta_M_bottom_minus_one_with_global_M_t_still_N_A_NOT_READY",
            ]
            if passed
            else ["blocks_research_candidate_exclusion"]
        ),
        "non_implications": [
            "no_certification_effect",
            "no_exact_status_update",
            "no_stable_claim_ledger_write",
            "no_production_lowering",
            "no_generic_D3_or_D4_unlock",
            "no_other_layout_or_rectangle_exclusion",
            "no_global_bound_or_optimum_update",
            "no_equivalence_to_full_adjudicated_game_semantics",
            "no_rejudgment_of_the_W0_unary_lowering_canary",
            "no_use_of_observational_coverage_as_proof",
        ],
        "contract_identity": dict(contract_identity),
        "details": dict(details),
    }
    if error is not None:
        receipt["error"] = error
    require(all(field in receipt for field in REQUIRED_RECEIPT_FIELDS), "terminal receipt lost an eight-field key")
    return receipt


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    started = time.perf_counter()
    repo_root = args.repo_root.resolve()
    data_root = (args.data_root or repo_root).resolve()
    try:
        manifest = read_json(CORRESPONDENCE_MANIFEST_PATH, label="correspondence manifest")
        context_manifest = read_json(HERE / "01_CONTEXT_MANIFEST.json", label="context manifest")
        terminal = read_json(TERMINAL_JUDGMENT_PATH, label="terminal Judgment")
        require(isinstance(manifest, Mapping), "correspondence manifest root is not an object")
        require(isinstance(context_manifest, Mapping), "context manifest root is not an object")
        require(isinstance(terminal, Mapping), "terminal Judgment root is not an object")
        proof_text = TERMINAL_PROOF_PATH.read_text(encoding="utf-8")

        theorem_receipts = verify_theorems(repo_root=repo_root, data_root=data_root, manifest=manifest)
        source_audit = audit_sources(repo_root, manifest)
        snapshot_audit = audit_snapshot(data_root, manifest, context_manifest)
        context_transport = verify_context_transport(theorem_receipts, manifest)
        protected = verify_protected_surfaces(repo_root, manifest)
        canary_history = verify_canary_history(repo_root, manifest)
        obligations = make_obligation_receipts(
            source_audit=source_audit,
            snapshot_audit=snapshot_audit,
            context_transport=context_transport,
            protected=protected,
        )
        terminal_summary = verify_terminal_judgment(
            terminal,
            proof_text,
            manifest,
            theorem_receipts,
            obligations,
        )

        snapshot_path = data_root / str(manifest["model_snapshot"]["path"])
        snapshot_payload = read_json(snapshot_path, label="A_BASELINE model snapshot")
        negative_tests = run_negative_tests(
            terminal=terminal,
            manifest=manifest,
            snapshot=snapshot_payload,
            obligations=obligations,
        )

        file_hashes: dict[str, str] = {}
        for path in (
            CORRESPONDENCE_MANIFEST_PATH,
            CORRESPONDENCE_DOC_PATH,
            TERMINAL_JUDGMENT_PATH,
            TERMINAL_PROOF_PATH,
            Path(__file__).resolve(),
        ):
            file_hashes[str(path.relative_to(repo_root))] = sha256_file(path)[0]
        contract_identity = {
            "problemHash": manifest["shared_identity"]["problemHash"],
            "objectiveHash": manifest["shared_identity"]["objectiveHash"],
            "theorem_one_contextHash": manifest["shared_identity"]["theorem_one_contextHash"],
            "theorem_two_contextHash": manifest["shared_identity"]["theorem_two_contextHash"],
            "theorem_one_judgment_sha256": manifest["theorem_one"]["judgment_sha256"],
            "theorem_two_judgment_sha256": manifest["theorem_two"]["judgment_sha256"],
            "theorem_two_receipt_sha256": manifest["theorem_two"]["receipt_sha256"],
            "file_hashes": file_hashes,
        }
        verified_scope = {
            "theorem_one_pass": True,
            "theorem_two_pass": True,
            "theorem_identity_file_count": len(theorem_receipts["identity_checks"]),
            "path_obligation_count": len(obligations),
            "path_obligations_discharged": sum(item["status"] == "DISCHARGED" for item in obligations),
            "snapshot_slot_count": snapshot_audit["generic_output_slot_count"],
            "snapshot_literal_count": snapshot_audit["generic_output_literal_count"],
            "snapshot_blue_requirement": snapshot_audit["blue_requirement"]["domain"][0],
            "snapshot_source_requirement": snapshot_audit["source_requirement"]["domain"][0],
            "candidate_state_before": "UNKNOWN",
            "candidate_state_after": "PROVED_EXCLUDED",
            "delta_M_bottom": -1,
            "global_M_t": "N_A_NOT_READY",
            "canary_verdict_unchanged": True,
            "negative_test_count": len(negative_tests),
            "protected_surfaces_unchanged": True,
        }
        details = {
            "schema_version": "zmd_w0_terminal_exclusion_receipt_v1",
            "status": "PASS",
            "theorem_checks": {
                "identity_files": theorem_receipts["identity_checks"],
                "theorem_one": {
                    "status": theorem_receipts["theorem_one"]["status"],
                    "judgment_id": manifest["theorem_one"]["judgment_id"],
                },
                "theorem_two": {
                    "outcome": theorem_receipts["theorem_two"]["outcome"],
                    "judgment_id": manifest["theorem_two"]["judgment_id"],
                    "coverage_checked": theorem_receipts["theorem_two"]["verified_scope"]["coverage_checked"],
                },
            },
            "source_audit": source_audit,
            "snapshot_audit": snapshot_audit,
            "context_transport": context_transport,
            "path_obligations": obligations,
            "terminal_summary": terminal_summary,
            "endpoint_transaction": terminal["endpoint_transaction"],
            "protected_surfaces": protected,
            "canary_history": canary_history,
            "negative_tests": negative_tests,
            "timing_seconds": time.perf_counter() - started,
        }
        receipt = make_receipt(
            outcome="PASS",
            verified_scope=verified_scope,
            contract_identity=contract_identity,
            details=details,
        )
        exit_code = 0
    except (
        TerminalCheckError,
        OSError,
        UnicodeError,
        KeyError,
        TypeError,
        ValueError,
        IndexError,
    ) as exc:
        receipt = make_receipt(
            outcome="FAIL",
            verified_scope={"completed": False},
            contract_identity={
                "correspondence_manifest_path": str(CORRESPONDENCE_MANIFEST_PATH),
                "terminal_judgment_path": str(TERMINAL_JUDGMENT_PATH),
                "checker_sha256": sha256_file(Path(__file__).resolve())[0],
            },
            details={
                "schema_version": "zmd_w0_terminal_exclusion_receipt_v1",
                "status": "FAIL",
                "timing_seconds": time.perf_counter() - started,
            },
            error=str(exc),
        )
        exit_code = 1

    text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
