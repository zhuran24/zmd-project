#!/usr/bin/env python3
"""Independently verify the pinned W0 generic-output slot arithmetic theorem.

The checker uses only the Python standard library.  It does not import project
modules, solver code, Phase -1 harnesses, OR-Tools, or the experiment-one
checker.  Experimental journals are optional post-hoc coverage data and are
never consumed by the mathematical proof path.
"""

from __future__ import annotations

import argparse
from collections import Counter
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
MANIFEST_PATH = HERE / "01_CONTEXT_MANIFEST.json"
JUDGMENT_PATH = HERE / "02_JUDGMENT.json"
PROOF_PATH = HERE / "03_PROOF.md"
ACCEPTANCE_PATH = HERE / "00_ACCEPTANCE_CRITERIA_FROZEN.md"
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


class CheckError(RuntimeError):
    """The theorem or one of its pinned premises failed closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise CheckError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_nonfinite(token: str) -> None:
    raise CheckError(f"non-finite JSON number is forbidden: {token}")


def parse_json_bytes(payload: bytes, *, label: str) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckError(f"{label} is not UTF-8: {exc}") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except json.JSONDecodeError as exc:
        raise CheckError(f"{label} is not strict JSON: {exc}") from exc


def read_json(path: Path, *, label: str | None = None) -> Any:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise CheckError(f"cannot read {label or path}: {exc}") from exc
    return parse_json_bytes(payload, label=label or str(path))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise CheckError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest(), size


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


def resolve_input_path(repo_root: Path, relative: str) -> Path:
    path = repo_root / relative
    require(path.is_file(), f"pinned input is missing: {relative}")
    return path


def verify_pinned_inputs(
    repo_root: Path,
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    resolved: dict[str, Path] = {}
    receipts: list[dict[str, Any]] = []
    records = manifest.get("pinned_inputs")
    require(isinstance(records, list) and records, "manifest pinned_inputs is empty")
    for record in records:
        require(isinstance(record, Mapping), "pinned input record is not an object")
        role = str(record["role"])
        relative = str(record["path"])
        path = resolve_input_path(repo_root, relative)
        actual_sha, actual_size = sha256_file(path)
        require(actual_sha == str(record["sha256"]), f"SHA-256 drift: {relative}")
        require(actual_size == int(record["size_bytes"]), f"size drift: {relative}")
        require(role not in resolved, f"duplicate pinned input role: {role}")
        resolved[role] = path
        receipts.append(
            {
                "role": role,
                "path": relative,
                "sha256": actual_sha,
                "size_bytes": actual_size,
            }
        )
    expected_roles = {
        "canonical_rules",
        "candidate_pool",
        "mandatory_instances",
        "generic_io",
        "fixed_layout",
        "fixed_rectangle",
    }
    require(set(resolved) == expected_roles, "pinned input role set drift")
    return resolved, receipts


def recompute_binding_contract_hash(manifest: Mapping[str, Any]) -> str:
    records = {str(item["role"]): item for item in manifest["pinned_inputs"]}
    spec = manifest["binding_contract_hash_material"]
    roles = [str(value) for value in spec["ordered_roles"]]
    material = "".join(
        f"{role}:{records[role]['path']}:{records[role]['sha256']}\n"
        for role in roles
    )
    observed = hashlib.sha256(material.encode("utf-8")).hexdigest()
    require(
        observed == manifest["judgment_two"]["binding_contractHash"],
        "binding_contractHash drift",
    )
    return observed


def recompute_context_hash(manifest: Mapping[str, Any]) -> str:
    identity = manifest["judgment_two"]
    context_material = {
        "base_contextHash": identity["base_contextHash"],
        "binding_contractHash": identity["binding_contractHash"],
        "quantified_component": "binding_selection_only",
        "target_slot_id": manifest["expected_binding_contract"]["target_slot_id"],
        "contract": "52 slots; labels blue_iron_ore/source_ore/__unused__; exactly-one; sums 34/18",
    }
    observed = canonical_json_sha256(context_material)
    require(observed == identity["contextHash"], "contextHash drift")
    return observed


def derive_slot_universe(
    *,
    layout_payload: Mapping[str, Any],
    candidate_payload: Mapping[str, Any],
    mandatory_instances: Sequence[Mapping[str, Any]],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    solution = layout_payload.get("solution")
    require(isinstance(solution, Mapping), "fixed layout lacks solution mapping")
    require(int(layout_payload.get("facility_count", -1)) == len(solution), "layout facility_count drift")
    by_id: dict[str, Mapping[str, Any]] = {}
    for record in mandatory_instances:
        require(isinstance(record, Mapping), "mandatory instance record is not an object")
        instance_id = str(record["instance_id"])
        require(instance_id not in by_id, f"duplicate mandatory instance id: {instance_id}")
        by_id[instance_id] = record
    require(len(by_id) == 266, f"mandatory instance count is {len(by_id)}, expected 266")

    pools = candidate_payload.get("facility_pools")
    require(isinstance(pools, Mapping), "candidate pool lacks facility_pools")
    source_rows: list[dict[str, Any]] = []
    slots: list[str] = []
    for raw_id, raw_entry in solution.items():
        instance_id = str(raw_id)
        require(isinstance(raw_entry, Mapping), f"layout entry {instance_id} is malformed")
        instance = by_id.get(instance_id)
        entry_operation = str(raw_entry.get("operation_type", ""))
        if instance is None:
            if entry_operation in {"boundary_io", "protocol_core"}:
                raise CheckError(f"unregistered generic-output source instance: {instance_id}")
            continue
        operation_type = str(instance.get("operation_type", ""))
        if entry_operation:
            require(
                entry_operation == operation_type,
                f"layout/mandatory operation mismatch for {instance_id}",
            )
        if operation_type not in {"boundary_io", "protocol_core"}:
            continue
        require(instance.get("is_mandatory") is True, f"source instance is not mandatory: {instance_id}")
        facility_type = str(raw_entry["facility_type"])
        pool = pools.get(facility_type)
        require(isinstance(pool, list), f"missing facility pool: {facility_type}")
        pose_idx = raw_entry.get("pose_idx")
        require(isinstance(pose_idx, int) and not isinstance(pose_idx, bool), f"invalid pose_idx: {instance_id}")
        require(0 <= pose_idx < len(pool), f"pose_idx out of range: {instance_id}")
        pose = pool[pose_idx]
        require(isinstance(pose, Mapping), f"candidate pose is malformed: {instance_id}")
        output_ports = pose.get("output_port_cells", [])
        require(isinstance(output_ports, list), f"output_port_cells is not a list: {instance_id}")
        expected_count = 1 if operation_type == "boundary_io" else 6
        require(
            len(output_ports) == expected_count,
            f"{instance_id} contributes {len(output_ports)} outputs, expected {expected_count}",
        )
        for local_index, port in enumerate(output_ports):
            require(isinstance(port, Mapping), f"malformed output port: {instance_id}:{local_index}")
            for field in ("x", "y", "dir"):
                require(field in port, f"output port lacks {field}: {instance_id}:{local_index}")
            slot_id = f"{instance_id}:out:{local_index}"
            slots.append(slot_id)
        source_rows.append(
            {
                "instance_id": instance_id,
                "operation_type": operation_type,
                "facility_type": facility_type,
                "pose_idx": pose_idx,
                "output_slot_count": len(output_ports),
            }
        )

    require(len(slots) == len(set(slots)), "derived slot IDs are not unique")
    boundary_rows = [row for row in source_rows if row["operation_type"] == "boundary_io"]
    core_rows = [row for row in source_rows if row["operation_type"] == "protocol_core"]
    boundary_slots = sorted(slot for slot in slots if slot.startswith("boundary_port_"))
    core_slots = sorted(slot for slot in slots if slot.startswith("protocol_core_001:out:"))
    require(len(boundary_rows) == int(expected["boundary_source_instance_count"]), "boundary source instance count drift")
    require(len(core_rows) == int(expected["protocol_core_source_instance_count"]), "core source instance count drift")
    require(len(boundary_slots) == int(expected["boundary_slot_count"]), "boundary slot count drift")
    require(len(core_slots) == int(expected["protocol_core_slot_count"]), "core slot count drift")
    require(len(slots) == int(expected["total_slot_count"]), "total slot count drift")
    require(boundary_slots == sorted(expected["expected_boundary_slot_ids"]), "boundary slot identity drift")
    require(core_slots == sorted(expected["expected_core_slot_ids"]), "core slot identity drift")
    require(str(expected["target_slot_id"]) in slots, "target slot is absent")
    return {
        "source_instance_count": len(source_rows),
        "boundary_source_instance_count": len(boundary_rows),
        "protocol_core_source_instance_count": len(core_rows),
        "boundary_slot_count": len(boundary_slots),
        "protocol_core_slot_count": len(core_slots),
        "total_slot_count": len(slots),
        "slot_ids": sorted(slots),
        "target_slot_id": str(expected["target_slot_id"]),
        "source_rows": sorted(source_rows, key=lambda item: item["instance_id"]),
    }


def derive_external_demands(
    *,
    canonical: Mapping[str, Any],
    mandatory_instances: Sequence[Mapping[str, Any]],
    generic_io: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    commodity_metadata = canonical.get("commodity_metadata")
    recipes = canonical.get("recipes")
    require(isinstance(commodity_metadata, Mapping), "canonical commodity_metadata missing")
    require(isinstance(recipes, Mapping), "canonical recipes missing")
    external = sorted(
        str(commodity)
        for commodity, metadata in commodity_metadata.items()
        if isinstance(metadata, Mapping) and metadata.get("source_kind") == "external_boundary"
    )
    require(external == ["blue_iron_ore", "source_ore"], "external-boundary commodity set drift")

    semantics = canonical.get("semantics")
    require(isinstance(semantics, Mapping), "canonical semantics missing")
    axioms = semantics.get("axiom_kernel", {}).get("axioms", {})
    require(isinstance(axioms, Mapping), "canonical axiom kernel missing")
    a4 = str(axioms.get("A4_device_composition", ""))
    a11 = str(axioms.get("A11_commodity_identity", ""))
    require("0-in/1-out" in a4, "canonical A4 no longer states boundary 0-in/1-out")
    require("one commodity per boundary-port generic_output slot" in a11, "canonical A11 generic-output mirror drift")
    core_limits = canonical.get("facility_templates", {}).get("protocol_core", {}).get("core_limits", {})
    require(int(core_limits.get("max_outputs", -1)) == 6, "protocol-core max_outputs drift")

    operation_counts: Counter[str] = Counter()
    derived: Counter[str] = Counter()
    for record in mandatory_instances:
        require(record.get("is_mandatory") is True, f"non-mandatory record in mandatory file: {record.get('instance_id')}")
        require(str(record.get("bound_type")) == "exact", f"non-exact mandatory record: {record.get('instance_id')}")
        operation = str(record.get("operation_type", ""))
        operation_counts[operation] += 1
        recipe = recipes.get(operation)
        if not isinstance(recipe, Mapping):
            continue
        inputs = recipe.get("inputs", {})
        require(isinstance(inputs, Mapping), f"recipe inputs malformed: {operation}")
        for commodity, raw_count in inputs.items():
            if str(commodity) in external:
                require(isinstance(raw_count, int) and not isinstance(raw_count, bool), f"non-integer recipe input: {operation}.{commodity}")
                require(raw_count >= 0, f"negative recipe input: {operation}.{commodity}")
                derived[str(commodity)] += raw_count

    expected_op_counts = expected["mandatory_operation_counts"]
    for operation, count in expected_op_counts.items():
        require(operation_counts[str(operation)] == int(count), f"mandatory operation count drift: {operation}")
    required_outputs = generic_io.get("required_generic_outputs")
    require(isinstance(required_outputs, Mapping), "generic I/O required_generic_outputs missing")
    normalized_required: dict[str, int] = {}
    for commodity, raw_count in required_outputs.items():
        require(isinstance(raw_count, int) and not isinstance(raw_count, bool), f"generic output requirement is not integer: {commodity}")
        require(raw_count >= 0, f"negative generic output requirement: {commodity}")
        normalized_required[str(commodity)] = raw_count
    expected_required = {str(key): int(value) for key, value in expected["required_generic_outputs"].items()}
    require(normalized_required == expected_required, "pinned generic-output requirement drift")
    require(dict(sorted(derived.items())) == expected_required, "canonical/mandatory demand re-derivation disagrees with generic I/O")
    return {
        "external_boundary_commodities": external,
        "mandatory_operation_counts": {
            operation: operation_counts[operation]
            for operation in sorted(expected_op_counts)
        },
        "derived_required_generic_outputs": dict(sorted(derived.items())),
        "generic_io_required_generic_outputs": dict(sorted(normalized_required.items())),
        "required_generic_output_total": sum(normalized_required.values()),
    }


def validate_declared_labels(expected: Mapping[str, Any]) -> list[str]:
    labels = [str(value) for value in expected["slot_labels"]]
    require(len(labels) == len(set(labels)), "slot labels are not unique")
    require(set(labels) == {"blue_iron_ore", "source_ore", "__unused__"}, "slot label domain drift")
    return labels


def prove_saturation(
    *,
    slot_ids: Sequence[str],
    demands: Mapping[str, int],
    target_slot_id: str,
    expected_slot_count: int = 52,
) -> dict[str, Any]:
    require(len(slot_ids) == len(set(slot_ids)), "slot universe contains duplicates")
    require(len(slot_ids) == expected_slot_count, f"slot universe has {len(slot_ids)}, expected {expected_slot_count}")
    require(target_slot_id in slot_ids, "target slot is absent from theorem universe")
    blue = int(demands.get("blue_iron_ore", -1))
    source = int(demands.get("source_ore", -1))
    require(blue >= 0 and source >= 0, "demand count is negative or missing")
    demand_total = blue + source
    forced_unused_total = len(slot_ids) - demand_total
    require(demand_total == len(slot_ids), "demand total does not saturate the slot universe")
    require(forced_unused_total == 0, "unused total is not forced to zero")
    return {
        "slot_count": len(slot_ids),
        "blue_iron_ore_count": blue,
        "source_ore_count": source,
        "required_total": demand_total,
        "forced_unused_total": forced_unused_total,
        "all_unused_indicators_forced_zero": True,
        "target_slot_id": target_slot_id,
        "target_must_be_active": True,
    }


def parse_numbered_proof_steps(proof_text: str) -> int:
    marker = "## 5. 证明"
    require(marker in proof_text, "proof section 5 is missing")
    tail = proof_text.split(marker, 1)[1]
    section = tail.split("\n## ", 1)[0]
    numbers: list[int] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or "." not in stripped:
            continue
        head = stripped.split(".", 1)[0]
        if head.isdigit():
            numbers.append(int(head))
    require(numbers == list(range(1, len(numbers) + 1)), "proof-step numbering is not consecutive")
    require(numbers, "proof contains no numbered steps")
    return len(numbers)


def verify_judgment(
    manifest: Mapping[str, Any],
    judgment: Mapping[str, Any],
    proof_text: str,
    arithmetic: Mapping[str, Any],
) -> dict[str, Any]:
    identity = manifest["judgment_two"]
    require(judgment["judgment_id"] == identity["judgment_id"], "Judgment ID drift")
    require(judgment["problem_identity"]["problemHash"] == identity["problemHash"], "problemHash drift")
    require(judgment["objective_context"]["objectiveHash"] == identity["objectiveHash"], "objectiveHash drift")
    context = judgment["context"]
    for field in ("base_contextHash", "binding_contractHash", "contextHash"):
        require(context[field] == identity[field], f"Judgment {field} drift")
    scope = judgment["scope"]
    require(scope["target_slot_id"] == arithmetic["target_slot_id"], "Judgment target slot drift")
    require(int(scope["slot_count"]) == int(arithmetic["slot_count"]), "Judgment slot count drift")
    require(
        set(scope["labels_per_slot"])
        == {"blue_iron_ore", "source_ore", "__unused__"},
        "Judgment slot-label domain drift",
    )
    require(scope["per_slot_constraint"] == "exactly one label", "Judgment per-slot contract drift")
    require(scope["global_counts"] == {
        "blue_iron_ore": arithmetic["blue_iron_ore_count"],
        "source_ore": arithmetic["source_ore_count"],
    }, "Judgment demand count drift")
    condition = judgment["condition"]
    require(condition["name"] == "LEGAL_W0_BINDING_CONTRACT", "Judgment condition identity drift")
    conclusion = judgment["conclusion"]
    require(conclusion["name"] == "W0_BOUNDARY_041_MUST_BE_ACTIVE", "Judgment conclusion identity drift")
    require(
        conclusion["formula"]
        == "forall b: W0LegalBindingSelection, active_output_slot(b, boundary_port_041, 0)",
        "Judgment conclusion formula drift",
    )
    require(
        judgment["sequent"]["formula"]
        == "forall b: W0LegalBindingSelection, legal_w0_binding_contract(b) -> active_output_slot(b, boundary_port_041, 0)",
        "Judgment sequent drift",
    )
    require(judgment["proof_object"]["experiment_data_is_a_premise"] is False, "experiment data became a premise")
    proof_steps = parse_numbered_proof_steps(proof_text)
    require(proof_steps == int(judgment["proof_object"]["proof_step_count"]), "proof-step count drift")
    coverage = judgment["coverage"]
    require(coverage["status"] == "POST_HOC_OBSERVATIONAL_ONLY", "coverage status drift")
    require(coverage["is_proof_premise"] is False, "coverage became a proof premise")
    consumption = judgment["consumption_contract"]
    require(
        consumption["polarity"]
        == "necessary_property_of_every_binding_accepted_by_the_pinned_current_model_contract",
        "Judgment consumption polarity drift",
    )
    required_non_implications = {
        "no_certification_effect",
        "no_exact_status_update",
        "no_stable_claim_ledger_write",
        "no_production_lowering",
        "no_generic_D3_or_D4_unlock",
        "no_claim_about_other_layouts_or_rectangles",
        "no_claim_that_the_current_binding restriction equals full adjudicated game semantics",
        "no_use_of_1007_observations_as_a_proof_premise",
    }
    require(
        required_non_implications <= set(judgment["non_implications"]),
        "Judgment non-implication set drift",
    )
    return {
        "proof_step_count": proof_steps,
        "experiment_data_is_a_premise": False,
        "context_relation": context["context_relation"],
    }


def expect_failure(name: str, callback: Callable[[], None]) -> dict[str, Any]:
    try:
        callback()
    except CheckError as exc:
        return {"name": name, "killed": True, "reason": str(exc)}
    raise CheckError(f"negative mutation survived: {name}")


def run_negative_tests(
    *,
    slots: Sequence[str],
    demands: Mapping[str, int],
    target_slot: str,
    canonical: Mapping[str, Any],
    mandatory_instances: Sequence[Mapping[str, Any]],
    generic_io: Mapping[str, Any],
    expected: Mapping[str, Any],
    data_root: Path,
    manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def missing_slot() -> None:
        prove_saturation(
            slot_ids=list(slots[:-1]),
            demands=demands,
            target_slot_id=target_slot,
        )

    def extra_slot() -> None:
        prove_saturation(
            slot_ids=[*slots, "synthetic_extra:out:0"],
            demands=demands,
            target_slot_id=target_slot,
            expected_slot_count=53,
        )

    def demand_total_51() -> None:
        mutated = dict(demands)
        mutated["source_ore"] = int(mutated["source_ore"]) - 1
        prove_saturation(slot_ids=slots, demands=mutated, target_slot_id=target_slot)

    def target_missing() -> None:
        prove_saturation(
            slot_ids=[slot for slot in slots if slot != target_slot],
            demands=demands,
            target_slot_id=target_slot,
            expected_slot_count=51,
        )

    def duplicate_slot() -> None:
        prove_saturation(
            slot_ids=[*slots[:-1], slots[0]],
            demands=demands,
            target_slot_id=target_slot,
        )

    def recipe_coefficient_drift() -> None:
        mutated = copy.deepcopy(canonical)
        mutated["recipes"]["refinery_blue_iron"]["inputs"]["blue_iron_ore"] = 2
        derive_external_demands(
            canonical=mutated,
            mandatory_instances=mandatory_instances,
            generic_io=generic_io,
            expected=expected,
        )

    def stale_hash() -> None:
        mutated = copy.deepcopy(manifest)
        canonical_record = next(
            record
            for record in mutated["pinned_inputs"]
            if record["role"] == "canonical_rules"
        )
        canonical_record["sha256"] = "0" * 64
        verify_pinned_inputs(data_root, mutated)

    def extra_domain_label() -> None:
        mutated = dict(expected)
        mutated["slot_labels"] = [*expected["slot_labels"], "synthetic_commodity"]
        validate_declared_labels(mutated)

    for name, callback in (
        ("missing_slot", missing_slot),
        ("extra_slot", extra_slot),
        ("demand_total_51", demand_total_51),
        ("target_missing", target_missing),
        ("duplicate_slot", duplicate_slot),
        ("recipe_coefficient_drift", recipe_coefficient_drift),
        ("stale_input_hash", stale_hash),
        ("extra_domain_label", extra_domain_label),
    ):
        results.append(expect_failure(name, callback))
    return results


def read_jsonl_prefix(path: Path, count: int) -> tuple[list[Mapping[str, Any]], bytes]:
    records: list[Mapping[str, Any]] = []
    chunks: list[bytes] = []
    try:
        with path.open("rb") as handle:
            for index in range(count):
                raw = handle.readline()
                require(raw != b"", f"coverage journal ended at record {index}")
                chunks.append(raw)
                record = parse_json_bytes(raw, label=f"coverage record {index + 1}")
                require(isinstance(record, Mapping), f"coverage record {index + 1} is not an object")
                records.append(record)
    except OSError as exc:
        raise CheckError(f"cannot read coverage journal {path}: {exc}") from exc
    return records, b"".join(chunks)


def verify_coverage(repo_root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    spec = manifest["coverage"]
    require(spec["status"] == "POST_HOC_OBSERVATIONAL_ONLY", "coverage status drift")
    require(spec["is_proof_premise"] is False, "coverage became a proof premise")
    path = resolve_input_path(repo_root, str(spec["event_journal_path"]))
    records, raw = read_jsonl_prefix(path, int(spec["event_prefix_record_count"]))
    require(len(raw) == int(spec["event_prefix_size_bytes"]), "coverage prefix size drift")
    require(sha256_bytes(raw) == str(spec["event_prefix_sha256"]), "coverage prefix SHA drift")
    expected_indices = list(range(1, len(records) + 1))
    observed_indices = [int(record["event_index"]) for record in records]
    require(observed_indices == expected_indices, "coverage event index sequence drift")
    digests = [str(record["selection_digest"]) for record in records]
    require(len(set(digests)) == int(spec["expected_unique_selection_digest_count"]), "coverage selection digest count drift")

    active_count = 0
    commodities: Counter[str] = Counter()
    for record in records:
        require(record.get("layout_id") == "W0-ALIGNMENT", "coverage includes another layout")
        examples = record.get("examples")
        require(isinstance(examples, list), "coverage event examples missing")
        matches = [
            example
            for example in examples
            if isinstance(example, Mapping)
            and example.get("instance_id") == "boundary_port_041"
            and example.get("front_cell") == [1, 53]
            and example.get("direction") == "E"
            and bool(example.get("commodity"))
        ]
        require(len(matches) == 1, "041 is not represented exactly once in a coverage event")
        active_count += 1
        commodities[str(matches[0]["commodity"])] += 1
    require(active_count == int(spec["expected_target_active_count"]), "coverage active count drift")
    return {
        "status": "PASS",
        "identity": spec["identity"],
        "is_proof_premise": False,
        "event_journal_path": spec["event_journal_path"],
        "record_count": len(records),
        "unique_selection_digest_count": len(set(digests)),
        "target_active_count": active_count,
        "coverage_fraction": active_count / len(records),
        "commodity_counts": dict(sorted(commodities.items())),
        "prefix_sha256": spec["event_prefix_sha256"],
    }


def git_output(repo_root: Path, *args: str) -> str | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def git_chronology(repo_root: Path) -> dict[str, Any]:
    acceptance_rel = str(ACCEPTANCE_PATH.relative_to(DEFAULT_REPO_ROOT))
    judgment_rel = str(JUDGMENT_PATH.relative_to(DEFAULT_REPO_ROOT))
    freeze_commit = git_output(repo_root, "log", "--diff-filter=A", "-1", "--format=%H", "--", acceptance_rel)
    theorem_commit = git_output(repo_root, "log", "--diff-filter=A", "-1", "--format=%H", "--", judgment_rel)
    relation = "UNCOMMITTED_THEOREM"
    if freeze_commit and theorem_commit:
        relation_result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", freeze_commit, theorem_commit],
            cwd=repo_root,
            check=False,
        )
        require(freeze_commit != theorem_commit, "acceptance criteria and theorem were introduced in one commit")
        require(relation_result.returncode == 0, "acceptance freeze commit is not an ancestor of theorem commit")
        relation = "FREEZE_PRECEDES_THEOREM"
    return {
        "acceptance_freeze_commit": freeze_commit,
        "theorem_introduction_commit": theorem_commit,
        "relation": relation,
    }


def make_receipt(
    *,
    outcome: str,
    verified_scope: Mapping[str, Any],
    contract_identity: Mapping[str, Any],
    details: Mapping[str, Any],
    error: str | None = None,
) -> dict[str, Any]:
    pass_outcome = outcome == "PASS"
    receipt: dict[str, Any] = {
        "result_kind": "w0_slot_arithmetic_theorem_check",
        "outcome": outcome,
        "subject_identity": {
            "judgment_id": "J-W0-GENERIC-OUTPUT-SLOT-SATURATION-041-V1",
            "layout_id": "W0-ALIGNMENT",
            "target_slot_id": "boundary_port_041:out:0",
        },
        "verified_scope": dict(verified_scope),
        "authority_basis": {
            "authority_class": "research_only_non_authorizing",
            "source_paths": [
                str(ACCEPTANCE_PATH.relative_to(DEFAULT_REPO_ROOT)),
                str(MANIFEST_PATH.relative_to(DEFAULT_REPO_ROOT)),
                str(JUDGMENT_PATH.relative_to(DEFAULT_REPO_ROOT)),
                str(PROOF_PATH.relative_to(DEFAULT_REPO_ROOT)),
            ],
        },
        "granted_effects": (
            [
                "permits_offline_composition_with_J-W0-GHOST-FRONT-BOUNDARY-041-V1",
                "permits_research_candidate_exclusion_review_for_the_fixed_W0_rectangle",
            ]
            if pass_outcome
            else ["blocks_terminal_exclusion_composition"]
        ),
        "non_implications": [
            "no_certification_effect",
            "no_exact_status_update",
            "no_stable_claim_ledger_write",
            "no_production_lowering",
            "no_generic_D3_or_D4_unlock",
            "no_cross_layout_or_cross_rectangle_generality",
            "no_equivalence_to_full_adjudicated_game_semantics",
            "no_use_of_observational_coverage_as_proof",
        ],
        "contract_identity": dict(contract_identity),
        "details": dict(details),
    }
    if error is not None:
        receipt["error"] = error
    require(all(field in receipt for field in REQUIRED_RECEIPT_FIELDS), "receipt lost an eight-field key")
    return receipt


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="root containing pinned workspace inputs and optional coverage journals",
    )
    parser.add_argument("--coverage", choices=("off", "auto", "required"), default="auto")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    started = time.perf_counter()
    repo_root = args.repo_root.resolve()
    data_root = (args.data_root or repo_root).resolve()
    try:
        manifest = read_json(MANIFEST_PATH, label="context manifest")
        judgment = read_json(JUDGMENT_PATH, label="Judgment")
        require(isinstance(manifest, Mapping), "context manifest root is not an object")
        require(isinstance(judgment, Mapping), "Judgment root is not an object")
        proof_text = PROOF_PATH.read_text(encoding="utf-8")
        resolved, file_receipts = verify_pinned_inputs(data_root, manifest)
        binding_hash = recompute_binding_contract_hash(manifest)
        context_hash = recompute_context_hash(manifest)

        canonical = read_json(resolved["canonical_rules"], label="canonical rules")
        candidate = read_json(resolved["candidate_pool"], label="candidate pool")
        mandatory = read_json(resolved["mandatory_instances"], label="mandatory instances")
        generic_io = read_json(resolved["generic_io"], label="generic I/O")
        layout = read_json(resolved["fixed_layout"], label="fixed W0 layout")
        require(isinstance(canonical, Mapping), "canonical root is not an object")
        require(isinstance(candidate, Mapping), "candidate-pool root is not an object")
        require(isinstance(mandatory, list), "mandatory-instance root is not a list")
        require(isinstance(generic_io, Mapping), "generic-I/O root is not an object")
        require(isinstance(layout, Mapping), "fixed-layout root is not an object")

        expected = manifest["expected_binding_contract"]
        labels = validate_declared_labels(expected)
        slot_summary = derive_slot_universe(
            layout_payload=layout,
            candidate_payload=candidate,
            mandatory_instances=mandatory,
            expected=expected,
        )
        demand_summary = derive_external_demands(
            canonical=canonical,
            mandatory_instances=mandatory,
            generic_io=generic_io,
            expected=expected,
        )
        arithmetic = prove_saturation(
            slot_ids=slot_summary["slot_ids"],
            demands=demand_summary["derived_required_generic_outputs"],
            target_slot_id=slot_summary["target_slot_id"],
        )
        judgment_summary = verify_judgment(manifest, judgment, proof_text, arithmetic)
        negative_tests = run_negative_tests(
            slots=slot_summary["slot_ids"],
            demands=demand_summary["derived_required_generic_outputs"],
            target_slot=slot_summary["target_slot_id"],
            canonical=canonical,
            mandatory_instances=mandatory,
            generic_io=generic_io,
            expected=expected,
            data_root=data_root,
            manifest=manifest,
        )

        coverage_available = (data_root / manifest["coverage"]["event_journal_path"]).is_file()
        coverage_receipt: dict[str, Any] | None = None
        if args.coverage == "required":
            require(coverage_available, "required coverage journal is unavailable")
            coverage_receipt = verify_coverage(data_root, manifest)
        elif args.coverage == "auto" and coverage_available:
            coverage_receipt = verify_coverage(data_root, manifest)

        manifest_sha, _ = sha256_file(MANIFEST_PATH)
        judgment_sha, _ = sha256_file(JUDGMENT_PATH)
        proof_sha, _ = sha256_file(PROOF_PATH)
        checker_sha, _ = sha256_file(Path(__file__).resolve())
        chronology = git_chronology(repo_root)
        contract_identity = {
            "problemHash": manifest["judgment_two"]["problemHash"],
            "objectiveHash": manifest["judgment_two"]["objectiveHash"],
            "base_contextHash": manifest["judgment_two"]["base_contextHash"],
            "binding_contractHash": binding_hash,
            "contextHash": context_hash,
            "manifest_sha256": manifest_sha,
            "judgment_sha256": judgment_sha,
            "proof_sha256": proof_sha,
            "checker_sha256": checker_sha,
            **chronology,
        }
        verified_scope = {
            "pinned_file_count": len(file_receipts),
            "slot_count": arithmetic["slot_count"],
            "boundary_slot_count": slot_summary["boundary_slot_count"],
            "protocol_core_slot_count": slot_summary["protocol_core_slot_count"],
            "slot_labels": labels,
            "blue_iron_ore_count": arithmetic["blue_iron_ore_count"],
            "source_ore_count": arithmetic["source_ore_count"],
            "required_total": arithmetic["required_total"],
            "forced_unused_total": arithmetic["forced_unused_total"],
            "target_must_be_active": arithmetic["target_must_be_active"],
            "proof_step_count": judgment_summary["proof_step_count"],
            "negative_test_count": len(negative_tests),
            "coverage_mode": args.coverage,
            "coverage_available": coverage_available,
            "coverage_checked": coverage_receipt is not None,
            "coverage_is_a_proof_premise": False,
        }
        details = {
            "schema_version": "zmd_w0_slot_arithmetic_theorem_receipt_v1",
            "status": "PASS",
            "pinned_files": file_receipts,
            "slot_derivation": slot_summary,
            "demand_derivation": demand_summary,
            "arithmetic_proof": arithmetic,
            "judgment_check": judgment_summary,
            "negative_tests": negative_tests,
            "coverage": coverage_receipt,
            "timing_seconds": time.perf_counter() - started,
        }
        receipt = make_receipt(
            outcome="PASS",
            verified_scope=verified_scope,
            contract_identity=contract_identity,
            details=details,
        )
        exit_code = 0
    except (CheckError, OSError, UnicodeError, KeyError, TypeError, ValueError, IndexError) as exc:
        contract_identity = {
            "manifest_path": str(MANIFEST_PATH),
            "judgment_path": str(JUDGMENT_PATH),
            "checker_sha256": sha256_file(Path(__file__).resolve())[0],
        }
        receipt = make_receipt(
            outcome="FAIL",
            verified_scope={"completed": False, "coverage_mode": args.coverage},
            contract_identity=contract_identity,
            details={
                "schema_version": "zmd_w0_slot_arithmetic_theorem_receipt_v1",
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
