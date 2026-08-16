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
OWNER_AUTHORIZATION_PATH = HERE / "00_OWNER_AUTHORIZATION_20260816.md"
ACCEPTANCE_PATH = HERE / "00_ACCEPTANCE_CRITERIA_FROZEN.md"
CONTEXT_MANIFEST_PATH = HERE / "01_CONTEXT_MANIFEST.json"
THEOREM_TWO_RECEIPT_PATH = HERE / "05_THEOREM_RECEIPT.json"
CORRESPONDENCE_MANIFEST_PATH = HERE / "06_MODEL_CORRESPONDENCE_MANIFEST.json"
CORRESPONDENCE_DOC_PATH = HERE / "07_MODEL_CORRESPONDENCE.md"
TERMINAL_JUDGMENT_PATH = HERE / "08_TERMINAL_EXCLUSION_JUDGMENT.json"
TERMINAL_PROOF_PATH = HERE / "09_TERMINAL_EXCLUSION_PROOF.md"
RECEIPT_SCHEMA_PATH = HERE / "13_RECEIPT_ENVELOPE_SCHEMA_V1.json"
PROTOCOL_FREEZE_COMMIT = "a517fa7492a34f881f46b0a4cc9aae98bd6729ad"
THEOREM_COMMIT = "c8b69a03c8fae76a0b7b0864aa5bbea34e02fa0e"
TERMINAL_COMMIT = "da43392c18b725b007095ce31b8f9ba6461ea483"
OWNER_AUTHORIZATION_SHA256 = "e73af26bcb2a2184e3f83c93d79bdbac0563890c2a78bc506b914d844d2401b7"
ACCEPTANCE_SHA256 = "905e0b531c777c0b5216f306f77a0cacac57bd6b4a9b8d951d45fb31b574d5b2"
THEOREM_PASS_OUTCOME = "W0_SLOT_ARITHMETIC_PASS"
TERMINAL_PASS_OUTCOME = "W0_TERMINAL_EXCLUSION_PASS"
TERMINAL_FAIL_OUTCOME = "W0_TERMINAL_EXCLUSION_FAIL"
OBLIGATION_REQUIRED_EVIDENCE = (
    (
        "W0-LIFT-01-INPUT-IDENTITY",
        ("theorem-two input checker", "phase-minus1 harness source identity"),
    ),
    (
        "W0-LIFT-02-SLOT-COMPLETENESS",
        ("binding source audit", "A_BASELINE model snapshot"),
    ),
    (
        "W0-LIFT-03-PER-SLOT-EXACTLY-ONE",
        ("binding source audit", "A_BASELINE model snapshot"),
    ),
    (
        "W0-LIFT-04-GLOBAL-COUNTS",
        ("binding source audit", "A_BASELINE model snapshot"),
    ),
    ("W0-LIFT-05-ACTIVE-PORT-EXPORT", ("binding source audit",)),
    (
        "W0-LIFT-06-ROUTING-CONSUMPTION",
        ("phase-minus1 harness source audit", "routing source identity"),
    ),
    (
        "W0-LIFT-07-CONTEXT-TRANSPORT",
        (
            "theorem-one checker PASS",
            "theorem-two checker PASS",
            "structured context relation check",
        ),
    ),
    ("W0-LIFT-08-ENDPOINT-NONINTERFERENCE", ("protected surface hash check",)),
)
ARGUED_OBLIGATION_REASONS = {
    "W0-LIFT-01-INPUT-IDENTITY": (
        "The checker verifies pinned inputs and harness source identity but does not execute "
        "the runtime bridge from every frozen input into the binding model."
    ),
    "W0-LIFT-05-ACTIVE-PORT-EXPORT": (
        "The checker audits source markers for export behavior but does not execute the "
        "selection-to-port-spec semantic bridge."
    ),
    "W0-LIFT-06-ROUTING-CONSUMPTION": (
        "The checker verifies the pinned single-chain markers and call count but does not "
        "exhaustively prove that no alternate binding bypass exists."
    ),
}
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


def _schema_type_matches(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, Mapping)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected == "null":
        return instance is None
    raise TerminalCheckError(f"unsupported JSON Schema type: {expected}")


def _json_values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if (
        isinstance(left, (int, float))
        and not isinstance(left, bool)
        and isinstance(right, (int, float))
        and not isinstance(right, bool)
    ):
        return left == right
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _json_values_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(
            _json_values_equal(left[key], right[key]) for key in left
        )
    return type(left) is type(right) and left == right


def _schema_matches(instance: Any, schema: Any) -> bool:
    try:
        validate_json_schema_subset(instance, schema, path="<conditional>")
    except TerminalCheckError:
        return False
    return True


def validate_json_schema_subset(instance: Any, schema: Any, *, path: str = "$") -> None:
    """Validate the Draft 2020-12 subset used by the frozen receipt schema."""

    if isinstance(schema, bool):
        require(schema, f"receipt schema rejected {path}")
        return
    require(isinstance(schema, Mapping), f"receipt schema node is not an object at {path}")
    supported_keywords = {
        "$schema",
        "$id",
        "title",
        "description",
        "type",
        "required",
        "properties",
        "additionalProperties",
        "minProperties",
        "const",
        "enum",
        "minLength",
        "minItems",
        "maxItems",
        "uniqueItems",
        "items",
        "contains",
        "minContains",
        "maxContains",
        "allOf",
        "if",
        "then",
        "else",
    }
    unknown_keywords = set(schema) - supported_keywords
    require(not unknown_keywords, f"unsupported receipt schema keywords at {path}: {sorted(unknown_keywords)}")

    if "type" in schema:
        expected_type = schema["type"]
        require(isinstance(expected_type, str), f"schema type is not a string at {path}")
        require(_schema_type_matches(instance, expected_type), f"schema type mismatch at {path}: expected {expected_type}")
    if "const" in schema:
        require(_json_values_equal(instance, schema["const"]), f"schema const mismatch at {path}")
    if "enum" in schema:
        enum_values = schema["enum"]
        require(isinstance(enum_values, list), f"schema enum is not an array at {path}")
        require(instance in enum_values, f"schema enum mismatch at {path}")
    if isinstance(instance, str) and "minLength" in schema:
        require(len(instance) >= int(schema["minLength"]), f"schema minLength mismatch at {path}")

    if isinstance(instance, Mapping):
        required = schema.get("required", [])
        require(isinstance(required, list), f"schema required is not an array at {path}")
        for key in required:
            require(isinstance(key, str), f"schema required key is not a string at {path}")
            require(key in instance, f"schema required key missing at {path}/{key}")
        if "minProperties" in schema:
            require(len(instance) >= int(schema["minProperties"]), f"schema minProperties mismatch at {path}")
        properties = schema.get("properties", {})
        require(isinstance(properties, Mapping), f"schema properties is not an object at {path}")
        for key, child_schema in properties.items():
            if key in instance:
                validate_json_schema_subset(instance[key], child_schema, path=f"{path}/{key}")
        if schema.get("additionalProperties") is False:
            extras = set(instance) - set(properties)
            require(not extras, f"schema additional properties at {path}: {sorted(extras)}")

    if isinstance(instance, list):
        if "minItems" in schema:
            require(len(instance) >= int(schema["minItems"]), f"schema minItems mismatch at {path}")
        if "maxItems" in schema:
            require(len(instance) <= int(schema["maxItems"]), f"schema maxItems mismatch at {path}")
        if schema.get("uniqueItems") is True:
            for index, item in enumerate(instance):
                require(item not in instance[:index], f"schema uniqueItems mismatch at {path}/{index}")
        if "items" in schema:
            for index, item in enumerate(instance):
                validate_json_schema_subset(item, schema["items"], path=f"{path}/{index}")
        if "contains" in schema:
            match_count = sum(_schema_matches(item, schema["contains"]) for item in instance)
            min_contains = int(schema.get("minContains", 1))
            max_contains = int(schema.get("maxContains", len(instance)))
            require(min_contains <= match_count <= max_contains, f"schema contains mismatch at {path}")

    for index, child_schema in enumerate(schema.get("allOf", [])):
        validate_json_schema_subset(instance, child_schema, path=f"{path}/allOf/{index}")
    if "if" in schema:
        branch = "then" if _schema_matches(instance, schema["if"]) else "else"
        if branch in schema:
            validate_json_schema_subset(instance, schema[branch], path=f"{path}/{branch}")


def validate_receipt_against_schema(receipt: Mapping[str, Any]) -> None:
    schema = read_json(RECEIPT_SCHEMA_PATH, label="receipt envelope schema")
    require(isinstance(schema, Mapping), "receipt envelope schema root is not an object")
    validate_json_schema_subset(receipt, schema)


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


def base_contract_identity() -> dict[str, Any]:
    return {
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "theorem_commit": THEOREM_COMMIT,
        "terminal_commit": TERMINAL_COMMIT,
        "manifest_path": str(CONTEXT_MANIFEST_PATH.relative_to(DEFAULT_REPO_ROOT)),
        "receipt_schema_path": str(RECEIPT_SCHEMA_PATH.relative_to(DEFAULT_REPO_ROOT)),
    }


def authority_basis(*, defensive: bool = False) -> dict[str, Any]:
    owner_path = str(OWNER_AUTHORIZATION_PATH.relative_to(DEFAULT_REPO_ROOT))
    acceptance_path = str(ACCEPTANCE_PATH.relative_to(DEFAULT_REPO_ROOT))
    owner_sha = OWNER_AUTHORIZATION_SHA256 if defensive else sha256_file(OWNER_AUTHORIZATION_PATH)[0]
    acceptance_sha = ACCEPTANCE_SHA256 if defensive else sha256_file(ACCEPTANCE_PATH)[0]
    return {
        "authority_class": "research_only_non_authorizing",
        "source_paths": [
            owner_path,
            acceptance_path,
            str(CORRESPONDENCE_MANIFEST_PATH.relative_to(DEFAULT_REPO_ROOT)),
            str(CORRESPONDENCE_DOC_PATH.relative_to(DEFAULT_REPO_ROOT)),
            str(TERMINAL_JUDGMENT_PATH.relative_to(DEFAULT_REPO_ROOT)),
            str(TERMINAL_PROOF_PATH.relative_to(DEFAULT_REPO_ROOT)),
        ],
        "authority_sources": {
            "owner_authorization": {
                "path": owner_path,
                "sha256": owner_sha,
            },
            "acceptance_criteria": {
                "path": acceptance_path,
                "sha256": acceptance_sha,
            },
        },
    }


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
    observed_outcome = payload.get("outcome", payload.get("status"))
    require(
        observed_outcome in {"PASS", THEOREM_PASS_OUTCOME, TERMINAL_PASS_OUTCOME},
        f"{label} did not PASS: {observed_outcome}",
    )
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
    validate_receipt_against_schema(compact)
    require(
        compact.get("outcome") == THEOREM_PASS_OUTCOME,
        "theorem-two compact receipt did not emit the typed PASS outcome",
    )
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
        "slot_builder_markers_checked": True,
        "exactly_one_marker_checked": True,
        "global_requirement_marker_checked": True,
        "active_export_markers_checked": True,
        "routing_chain_markers_checked": True,
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


def audit_snapshot(
    data_root: Path,
    manifest: Mapping[str, Any],
    context_manifest: Mapping[str, Any],
    *,
    snapshot_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    spec = manifest["model_snapshot"]
    if snapshot_override is None:
        path = data_root / str(spec["path"])
        verify_file(path, str(spec["sha256"]), int(spec["size_bytes"]))
        snapshot = read_json(path, label="A_BASELINE model snapshot")
        require(isinstance(snapshot, Mapping), "model snapshot root is not an object")
    else:
        snapshot = snapshot_override
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


def verify_obligation_contract(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    records = manifest.get("path_obligations")
    require(isinstance(records, list), "correspondence manifest path_obligations is not an array")
    expected_ids = [item[0] for item in OBLIGATION_REQUIRED_EVIDENCE]
    require(len(records) == len(expected_ids), "correspondence manifest obligation count drift")
    record_by_id: dict[str, Mapping[str, Any]] = {}
    for record in records:
        require(isinstance(record, Mapping), "correspondence manifest obligation record malformed")
        obligation_id = str(record.get("id"))
        require(obligation_id not in record_by_id, f"duplicate manifest obligation ID: {obligation_id}")
        required_evidence = record.get("required_evidence")
        require(isinstance(required_evidence, list), f"manifest required_evidence malformed: {obligation_id}")
        require(
            all(isinstance(value, str) and value for value in required_evidence),
            f"manifest required_evidence item malformed: {obligation_id}",
        )
        record_by_id[obligation_id] = record
    require(set(record_by_id) == set(expected_ids), "correspondence manifest obligation ID set drift")
    for obligation_id, expected_evidence in OBLIGATION_REQUIRED_EVIDENCE:
        require(
            list(record_by_id[obligation_id]["required_evidence"]) == list(expected_evidence),
            f"correspondence manifest required_evidence drift: {obligation_id}",
        )
    return [record_by_id[obligation_id] for obligation_id in expected_ids]


def verify_obligation_receipts(obligations: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    expected_ids = [item[0] for item in OBLIGATION_REQUIRED_EVIDENCE]
    require(len(obligations) == len(expected_ids), "path obligation receipt count drift")
    receipt_by_id: dict[str, Mapping[str, Any]] = {}
    for item in obligations:
        require(isinstance(item, Mapping), "path obligation receipt malformed")
        obligation_id = str(item.get("id"))
        require(obligation_id not in receipt_by_id, f"duplicate path obligation receipt: {obligation_id}")
        receipt_by_id[obligation_id] = item
    require(set(receipt_by_id) == set(expected_ids), "path obligation receipt ID set drift")

    discharged = 0
    argued = 0
    open_count = 0
    for obligation_id, expected_evidence in OBLIGATION_REQUIRED_EVIDENCE:
        item = receipt_by_id[obligation_id]
        require(
            list(item.get("required_evidence", [])) == list(expected_evidence),
            f"path obligation required_evidence drift: {obligation_id}",
        )
        status = item.get("status")
        machine_checked = item.get("machine_checked")
        if obligation_id in ARGUED_OBLIGATION_REASONS:
            require(
                status == "ARGUED_NOT_MACHINE_CHECKED",
                f"argued obligation status drift: {obligation_id}: {status}",
            )
            require(machine_checked is False, f"argued obligation claimed machine coverage: {obligation_id}")
            argued += 1
        else:
            require(status == "DISCHARGED", f"machine obligation is not discharged: {obligation_id}: {status}")
            require(machine_checked is True, f"discharged obligation lacks machine result: {obligation_id}")
            discharged += 1
        if status == "OPEN":
            open_count += 1
    require(open_count == 0, "a path obligation remains OPEN")
    return {
        "path_obligation_count": len(obligations),
        "path_obligations_discharged": discharged,
        "path_obligations_argued_not_machine_checked": argued,
        "path_obligations_open": open_count,
    }


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
    verify_obligation_receipts(obligations)
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
    require(
        theorem_receipts["theorem_two"]["outcome"] == THEOREM_PASS_OUTCOME,
        "theorem two receipt did not emit the typed PASS outcome",
    )
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
    data_root: Path,
    terminal: Mapping[str, Any],
    proof_text: str,
    manifest: Mapping[str, Any],
    context_manifest: Mapping[str, Any],
    theorem_receipts: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def context_mismatch() -> None:
        mutated = copy.deepcopy(manifest)
        mutated["shared_identity"]["theorem_two_contextHash"] = "0" * 64
        verify_context_transport(theorem_receipts, mutated)

    def reopen_obligation() -> None:
        mutated = copy.deepcopy(list(obligations))
        machine_obligation = next(
            item for item in mutated if item["id"] == "W0-LIFT-02-SLOT-COMPLETENESS"
        )
        machine_obligation["status"] = "OPEN"
        machine_obligation["machine_checked"] = False
        verify_obligation_receipts(mutated)

    def remove_target_exactly_one() -> None:
        mutated = copy.deepcopy(snapshot)
        target_index = int(manifest["model_snapshot"]["expected"]["target_exactly_one_constraint_index"])
        mutated["constraints"][target_index]["kind"] = "synthetic_removed"
        audit_snapshot(
            data_root,
            manifest,
            context_manifest,
            snapshot_override=mutated,
        )

    def demand_33() -> None:
        mutated = copy.deepcopy(snapshot)
        index = int(manifest["model_snapshot"]["expected"]["blue_requirement_constraint_index"])
        mutated["constraints"][index]["linear"]["domain"] = [33, 33]
        audit_snapshot(
            data_root,
            manifest,
            context_manifest,
            snapshot_override=mutated,
        )

    def candidate_delta_zero() -> None:
        mutated = copy.deepcopy(terminal)
        mutated["endpoint_transaction"]["delta_M_bottom"] = 0
        verify_terminal_judgment(
            mutated,
            proof_text,
            manifest,
            theorem_receipts,
            obligations,
        )

    def rewrite_canary() -> None:
        mutated = copy.deepcopy(terminal)
        mutated["canary_relation"]["historical_verdict"] = "INFEASIBLE"
        verify_terminal_judgment(
            mutated,
            proof_text,
            manifest,
            theorem_receipts,
            obligations,
        )

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


def make_obligation_receipts(
    *,
    obligation_contract: Sequence[Mapping[str, Any]],
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
    machine_checks = {
        "W0-LIFT-02-SLOT-COMPLETENESS": (
            source_audit["slot_builder_markers_checked"] is True
            and int(snapshot_audit["generic_output_slot_count"]) == 52
        ),
        "W0-LIFT-03-PER-SLOT-EXACTLY-ONE": (
            source_audit["exactly_one_marker_checked"] is True
            and len(snapshot_audit["slot_exactly_one_constraint_indices"]) == 52
        ),
        "W0-LIFT-04-GLOBAL-COUNTS": (
            source_audit["global_requirement_marker_checked"] is True
            and snapshot_audit["blue_requirement"]["domain"] == [34, 34]
            and snapshot_audit["source_requirement"]["domain"] == [18, 18]
        ),
        "W0-LIFT-07-CONTEXT-TRANSPORT": (
            context_transport["problemHash_equal"] is True
            and context_transport["objectiveHash_equal"] is True
            and context_transport["theorem_two_base_equals_theorem_one_context"] is True
        ),
        "W0-LIFT-08-ENDPOINT-NONINTERFERENCE": protected["unchanged"] is True,
    }
    contract_by_id = {str(item["id"]): item for item in obligation_contract}
    receipts: list[dict[str, Any]] = []
    for obligation_id, _ in OBLIGATION_REQUIRED_EVIDENCE:
        if obligation_id in ARGUED_OBLIGATION_REASONS:
            machine_checked = False
            status = "ARGUED_NOT_MACHINE_CHECKED"
            status_reason = ARGUED_OBLIGATION_REASONS[obligation_id]
        else:
            machine_checked = bool(machine_checks[obligation_id])
            status = "DISCHARGED" if machine_checked else "OPEN"
            status_reason = (
                "All registered machine checks passed."
                if machine_checked
                else "At least one registered machine check failed."
            )
        receipts.append(
            {
                "id": obligation_id,
                "status": status,
                "machine_checked": machine_checked,
                "required_evidence": list(contract_by_id[obligation_id]["required_evidence"]),
                "evidence": evidence[obligation_id],
                "status_reason": status_reason,
            }
        )
    return receipts


def make_receipt(
    *,
    outcome: str,
    verified_scope: Mapping[str, Any],
    contract_identity: Mapping[str, Any],
    details: Mapping[str, Any],
    path_obligations: Sequence[Mapping[str, Any]] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    passed = outcome == TERMINAL_PASS_OUTCOME
    require(
        outcome in {TERMINAL_PASS_OUTCOME, TERMINAL_FAIL_OUTCOME},
        f"unsupported terminal receipt outcome: {outcome}",
    )
    details_payload = dict(details)
    terminal_summary = details_payload.pop("terminal_summary", None)
    receipt: dict[str, Any] = {
        "result_kind": "w0_terminal_exclusion_check",
        "outcome": outcome,
        "subject_identity": {
            "judgment_id": "J-W0-FIXED-RECT-BINDING-ROUTING-EXCLUDED-V1",
            "layout_id": "W0-ALIGNMENT",
            "rectangle": {"x0": 1, "y0": 51, "w": 6, "h": 7},
        },
        "verified_scope": dict(verified_scope),
        "authority_basis": authority_basis(defensive=not passed),
        "granted_effects": (
            [
                "records_the_fixed_W0_rectangle_as_PROVED_EXCLUDED_in_the_research_candidate_ledger",
                "records_delta_M_bottom_minus_one_with_global_M_t_still_N_A_NOT_READY",
            ]
            if passed
            else []
        ),
        "blocking_scope": [] if passed else ["research_candidate_exclusion"],
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
        "contract_identity": {**base_contract_identity(), **dict(contract_identity)},
        "details": details_payload,
    }
    if terminal_summary is not None:
        receipt["terminal_summary"] = dict(terminal_summary)
    if path_obligations is not None:
        receipt["path_obligations"] = [dict(item) for item in path_obligations]
    if error is not None:
        receipt["error"] = error
    try:
        validate_receipt_against_schema(receipt)
    except TerminalCheckError as exc:
        if passed:
            raise
        receipt["schema_validation"] = {
            "status": "UNAVAILABLE_OR_FAILED_DURING_FAILURE",
            "error": str(exc),
        }
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
        context_manifest = read_json(CONTEXT_MANIFEST_PATH, label="context manifest")
        terminal = read_json(TERMINAL_JUDGMENT_PATH, label="terminal Judgment")
        require(isinstance(manifest, Mapping), "correspondence manifest root is not an object")
        require(isinstance(context_manifest, Mapping), "context manifest root is not an object")
        require(isinstance(terminal, Mapping), "terminal Judgment root is not an object")
        proof_text = TERMINAL_PROOF_PATH.read_text(encoding="utf-8")
        obligation_contract = verify_obligation_contract(manifest)

        theorem_receipts = verify_theorems(repo_root=repo_root, data_root=data_root, manifest=manifest)
        source_audit = audit_sources(repo_root, manifest)
        snapshot_audit = audit_snapshot(data_root, manifest, context_manifest)
        context_transport = verify_context_transport(theorem_receipts, manifest)
        protected = verify_protected_surfaces(repo_root, manifest)
        canary_history = verify_canary_history(repo_root, manifest)
        obligations = make_obligation_receipts(
            obligation_contract=obligation_contract,
            source_audit=source_audit,
            snapshot_audit=snapshot_audit,
            context_transport=context_transport,
            protected=protected,
        )
        obligation_summary = verify_obligation_receipts(obligations)
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
            data_root=data_root,
            terminal=terminal,
            proof_text=proof_text,
            manifest=manifest,
            context_manifest=context_manifest,
            theorem_receipts=theorem_receipts,
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
            "path_obligation_count": obligation_summary["path_obligation_count"],
            "path_obligations_discharged": obligation_summary["path_obligations_discharged"],
            "path_obligations_argued_not_machine_checked": obligation_summary[
                "path_obligations_argued_not_machine_checked"
            ],
            "path_obligations_open": obligation_summary["path_obligations_open"],
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
            "terminal_summary": {**terminal_summary, **obligation_summary},
            "endpoint_transaction": terminal["endpoint_transaction"],
            "protected_surfaces": protected,
            "canary_history": canary_history,
            "negative_tests": negative_tests,
            "timing_seconds": time.perf_counter() - started,
        }
        receipt = make_receipt(
            outcome=TERMINAL_PASS_OUTCOME,
            verified_scope=verified_scope,
            contract_identity=contract_identity,
            details=details,
            path_obligations=obligations,
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
            outcome=TERMINAL_FAIL_OUTCOME,
            verified_scope={"completed": False},
            contract_identity={
                "correspondence_manifest_path": str(
                    CORRESPONDENCE_MANIFEST_PATH.relative_to(DEFAULT_REPO_ROOT)
                ),
                "terminal_judgment_path": str(TERMINAL_JUDGMENT_PATH.relative_to(DEFAULT_REPO_ROOT)),
                "checker_sha256": sha256_file(Path(__file__).resolve())[0],
            },
            details={
                "schema_version": "zmd_w0_terminal_exclusion_receipt_v1",
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
