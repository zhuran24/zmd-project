#!/usr/bin/env python3
"""Standard-library checker for the W0 unary-lowering CpModel snapshot diff."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping


class CheckError(RuntimeError):
    """Raised when the compiled model is not exactly the authorized lowering."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CheckError(f"cannot read JSON {path}: {exc}") from exc
    _require(isinstance(value, dict), f"top-level JSON must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise CheckError(f"cannot hash {path}: {exc}") from exc


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _variable_by_index(snapshot: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for raw in snapshot["variables"]:
        index = int(raw["index"])
        _require(index not in result, f"duplicate variable index {index}")
        result[index] = raw
    return result


def _check(
    contract: Mapping[str, Any],
    baseline: Mapping[str, Any],
    treatment: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    _require(
        contract.get("schema_version") == "zmd_w0_unary_lowering_contract_v1",
        "unexpected lowering contract schema",
    )
    for label, snapshot in (("baseline", baseline), ("treatment", treatment)):
        _require(
            snapshot.get("schema_version") == "zmd_cp_model_snapshot_v1",
            f"unexpected {label} snapshot schema",
        )
    _require(
        metadata.get("schema_version") == "zmd_w0_lowering_metadata_v1",
        "unexpected lowering metadata schema",
    )

    _require(
        baseline["variables"] == treatment["variables"],
        "treatment changed the variable inventory or domains",
    )
    for key in (
        "model_name",
        "search_strategy",
        "has_objective",
        "objective_text",
        "assumptions",
        "solution_hint_text",
        "symmetry_text",
    ):
        _require(baseline[key] == treatment[key], f"treatment changed {key}")

    base_constraints = baseline["constraints"]
    treatment_constraints = treatment["constraints"]
    expected_added = int(contract["lowering"]["expected_added_constraint_count"])
    _require(
        len(treatment_constraints) == len(base_constraints) + expected_added,
        "unexpected treatment constraint-count delta",
    )
    _require(
        treatment_constraints[: len(base_constraints)] == base_constraints,
        "treatment changed or reordered a pre-existing constraint",
    )
    added = treatment_constraints[len(base_constraints) :]
    _require(len(added) == 1, "lowering must append exactly one constraint")
    unary = added[0]
    _require(unary["kind"] == "linear", "added constraint is not linear")
    _require(
        unary.get("name") == contract["lowering"]["constraint_name"],
        "added constraint name mismatch",
    )
    _require(unary.get("enforcement_literals") == [], "added constraint is conditionally enforced")

    target = contract["target"]
    target_meta = metadata["target"]
    _require(target_meta["slot_id"] == target["slot_id"], "target slot mismatch")
    _require(
        sorted(target_meta["domain_labels"]) == sorted(target["expected_domain_labels"]),
        "target domain-label set mismatch",
    )
    unused_index = int(target_meta["unused_variable_index"])
    variables = _variable_by_index(baseline)
    _require(unused_index in variables, "unused variable index is absent")
    _require(
        variables[unused_index]["name"] == target["expected_variable_name"],
        "unused variable name mismatch",
    )
    _require(variables[unused_index]["domain"] == [0, 1], "unused variable is not Boolean")

    linear = unary["linear"]
    _require(linear["vars"] == [unused_index], "unary constraint targets another variable")
    _require(
        linear["coeffs"] == [int(contract["lowering"]["coefficient"])],
        "unary coefficient mismatch",
    )
    _require(
        linear["domain"] == [int(value) for value in contract["lowering"]["domain"]],
        "unary equality domain mismatch",
    )

    target_indexes = sorted(int(value) for value in target_meta["domain_variable_indexes"])
    _require(unused_index in target_indexes, "unused variable is outside the target slot domain")
    exact_matches = [
        item
        for item in base_constraints
        if item["kind"] == "exactly_one"
        and sorted(int(value) for value in item["exactly_one"]["literals"])
        == target_indexes
    ]
    _require(len(exact_matches) == 1, "target slot lacks one unique pre-existing ExactlyOne")

    active_indexes = sorted(int(value) for value in target_meta["active_variable_indexes"])
    _require(
        active_indexes == sorted(index for index in target_indexes if index != unused_index),
        "active-variable partition is not target-domain minus unused",
    )
    _require(
        int(metadata["baseline_variable_count"]) == len(baseline["variables"]),
        "baseline variable-count receipt mismatch",
    )
    _require(
        int(metadata["treatment_variable_count"]) == len(treatment["variables"]),
        "treatment variable-count receipt mismatch",
    )
    _require(
        int(metadata["treatment_variable_count"])
        == int(metadata["baseline_variable_count"])
        + int(contract["lowering"]["expected_added_variable_count"]),
        "unexpected variable-count delta",
    )

    baseline_digest = _canonical_digest(baseline)
    treatment_digest = _canonical_digest(treatment)
    _require(
        metadata["baseline_snapshot_digest"] == baseline_digest,
        "baseline snapshot digest mismatch",
    )
    _require(
        metadata["treatment_snapshot_digest"] == treatment_digest,
        "treatment snapshot digest mismatch",
    )

    return {
        "status": "PASS",
        "judgment_id": contract["judgment_id"],
        "protocol_freeze_commit": contract["protocol_freeze_commit"],
        "baseline_variable_count": len(baseline["variables"]),
        "baseline_constraint_count": len(base_constraints),
        "treatment_variable_count": len(treatment["variables"]),
        "treatment_constraint_count": len(treatment_constraints),
        "added_constraint_count": 1,
        "target_slot_id": target["slot_id"],
        "target_domain_labels": sorted(target_meta["domain_labels"]),
        "unused_variable_index": unused_index,
        "active_variable_indexes": active_indexes,
        "preexisting_exactly_one_constraint_index": int(exact_matches[0]["index"]),
        "reject_set_relation": "EQUAL_TO_ACTIVE_041_TRIGGER_SET",
        "reason": "ExactlyOne(target domain) plus unused==1 is equivalent to every active target value being 0.",
        "baseline_snapshot_digest": baseline_digest,
        "treatment_snapshot_digest": treatment_digest,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--treatment", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    started = time.perf_counter()
    try:
        contract = _load_json(args.contract)
        baseline = _load_json(args.baseline)
        treatment = _load_json(args.treatment)
        metadata = _load_json(args.metadata)
        checked = _check(contract, baseline, treatment, metadata)
        receipt = {
            "schema_version": "zmd_w0_lowering_contract_receipt_v1",
            **checked,
            "contract_sha256": _sha256(args.contract),
            "checker_sha256": _sha256(Path(__file__)),
            "standard_library_only": True,
            "wall_seconds": time.perf_counter() - started,
        }
        encoded = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 0
    except (CheckError, KeyError, TypeError, ValueError) as exc:
        failure = {
            "schema_version": "zmd_w0_lowering_contract_receipt_v1",
            "status": "FAIL",
            "error": str(exc),
            "wall_seconds": time.perf_counter() - started,
        }
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
