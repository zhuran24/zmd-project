#!/usr/bin/env python3
"""Independently recheck the W0 ghost-front offline certificate.

This checker is intentionally standard-library-only and imports no solver,
routing, binding, Phase -1 harness, or project model code.  It recomputes the
certificate from the pinned canonical rules, candidate pool, fixed layout, and
fixed rectangle bytes.  Optional coverage checking reads a frozen prefix of the
observational journals only after the proof has succeeded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


class CheckError(RuntimeError):
    """Raised when a pinned identity or proof obligation does not hold."""


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


def _sha256_file(path: Path) -> tuple[str, int]:
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


def _canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_jsonl_prefix(path: Path, record_count: int) -> tuple[list[dict[str, Any]], bytes]:
    records: list[dict[str, Any]] = []
    raw = bytearray()
    try:
        with path.open("rb") as handle:
            for index in range(record_count):
                line = handle.readline()
                _require(bool(line), f"{path} ended before record {index + 1}")
                raw.extend(line)
                try:
                    record = json.loads(line)
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise CheckError(
                        f"invalid JSONL record {index + 1} in {path}: {exc}"
                    ) from exc
                _require(
                    isinstance(record, dict),
                    f"JSONL record {index + 1} is not an object: {path}",
                )
                records.append(record)
    except OSError as exc:
        raise CheckError(f"cannot read JSONL prefix {path}: {exc}") from exc
    return records, bytes(raw)


def _count_numbered_proof_steps(path: Path) -> int:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise CheckError(f"cannot read proof Markdown {path}: {exc}") from exc

    heading = "## 5. 反证"
    try:
        start = lines.index(heading)
    except ValueError as exc:
        raise CheckError(f"proof Markdown lacks exact heading {heading!r}: {path}") from exc

    section: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        section.append(line)

    numbered_steps: list[int] = []
    for line in section:
        match = re.match(r"^(\d+)\.\s+", line)
        if match is not None:
            numbered_steps.append(int(match.group(1)))

    _require(numbered_steps, "proof contradiction section has no numbered steps")
    expected = list(range(1, len(numbered_steps) + 1))
    _require(
        numbered_steps == expected,
        f"proof contradiction steps are not contiguous from 1: {numbered_steps}",
    )
    return len(numbered_steps)


def _cell(value: Any, *, label: str) -> tuple[int, int]:
    _require(
        isinstance(value, (list, tuple)) and len(value) == 2,
        f"{label} must be a two-element cell",
    )
    return int(value[0]), int(value[1])


def _inside(rect: dict[str, int], cell: tuple[int, int]) -> bool:
    x, y = cell
    return rect["x0"] <= x <= rect["x1"] and rect["y0"] <= y <= rect["y1"]


def _infer_repo_root(script_path: Path) -> Path:
    # script -> experiment dir -> review dossier -> docs/research -> docs -> repo
    return script_path.resolve().parents[4]


def _verify_problem_identity(
    repo_root: Path,
    judgment: dict[str, Any],
) -> tuple[dict[str, Path], str, dict[str, float]]:
    started = time.perf_counter()
    identity = judgment["problem_identity"]
    entries = identity["files"]
    _require(isinstance(entries, list) and entries, "problem identity has no files")

    paths: dict[str, Path] = {}
    material_parts: list[str] = []
    for entry in entries:
        role = str(entry["role"])
        relative = str(entry["path"])
        path = repo_root / relative
        _require(path.is_file(), f"missing pinned {role} file: {relative}")
        actual_sha, actual_size = _sha256_file(path)
        _require(
            actual_sha == entry["sha256"],
            f"SHA-256 mismatch for {relative}: {actual_sha}",
        )
        _require(
            actual_size == int(entry["size_bytes"]),
            f"size mismatch for {relative}: {actual_size}",
        )
        paths[role] = path
        material_parts.append(f"{relative}:{actual_sha}\n")

    problem_hash = hashlib.sha256("".join(material_parts).encode("utf-8")).hexdigest()
    _require(
        problem_hash == identity["problemHash"],
        f"problemHash mismatch: {problem_hash}",
    )
    return paths, problem_hash, {"identity_seconds": time.perf_counter() - started}


def _verify_semantic_proof(
    paths: dict[str, Path],
    problem_hash: str,
    judgment: dict[str, Any],
    proof_path: Path,
) -> tuple[dict[str, Any], dict[str, float]]:
    started = time.perf_counter()
    rules = _load_json(paths["canonical_rules"])
    pool_document = _load_json(paths["candidate_pool"])
    layout_document = _load_json(paths["fixed_layout"])
    ghost_document = _load_json(paths["fixed_ghost_rectangle"])

    _require(rules["metadata"]["version"] == "1.2.0", "unexpected rule version")
    empty_rule = rules["globals"]["empty_rectangle"]
    _require(
        empty_rule["emptiness"] == "no_occupant_of_any_kind",
        "strict empty-rectangle semantics are absent",
    )
    empty_statement = empty_rule["emptiness_adjudication"]["statement"]
    for required_phrase in ("facility bodies", "power poles", "belts", "bridge"):
        _require(
            required_phrase in empty_statement,
            f"empty-rectangle statement lacks {required_phrase!r}",
        )

    semantics = rules["semantics"]
    a5 = semantics["axiom_kernel"]["axioms"]["A5_interfaces"]
    _require(
        "stored port coordinate" in a5
        and "IS the front/belt cell itself" in a5,
        "canonical front identity is absent",
    )
    clearance_statement = semantics["machine_min_clearance"]["statement"]
    _require(
        "an in-use port requires THAT cell to accept a belt" in clearance_statement,
        "canonical in-use front requirement is absent",
    )
    connectivity_statement = semantics["connectivity_quantifier"]["statement"]
    _require(
        "every SOURCE front can reach SOME sink front" in connectivity_statement,
        "canonical source-connectivity requirement is absent",
    )

    raw_rect = ghost_document["max_admissible_empty_rect_minside_ge_6"]["rect"]
    rect = {
        key: int(raw_rect[key])
        for key in ("x0", "x1", "y0", "y1", "w", "h")
    }
    _require(rect["x1"] == rect["x0"] + rect["w"] - 1, "rect width mismatch")
    _require(rect["y1"] == rect["y0"] + rect["h"] - 1, "rect height mismatch")
    expected_rect = judgment["objective_context"]["fixed_rect"]
    _require(rect == expected_rect, f"fixed rectangle mismatch: {rect}")

    objective_value = {
        "fixed_rect": rect,
        "min_side_admissibility": int(empty_rule["min_side_admissibility"]),
        "objective": str(empty_rule["objective"]),
    }
    objective_hash = _canonical_json_sha256(objective_value)
    _require(
        objective_hash == judgment["objective_context"]["objectiveHash"],
        f"objectiveHash mismatch: {objective_hash}",
    )

    context = judgment["context"]
    context_value = {
        "binders": context["binders"],
        "fixed_layout_id": context["fixed_layout_id"],
        "objective_hash": objective_hash,
        "problem_hash": problem_hash,
        "quantified_component": context["quantified_component"],
        "routing_semantics": context["routing_semantics"],
        "trigger": context["trigger"],
    }
    context_hash = _canonical_json_sha256(context_value)
    _require(
        context_hash == context["contextHash"],
        f"contextHash mismatch: {context_hash}",
    )

    facility_pools = pool_document["facility_pools"]
    solution = layout_document["solution"]
    _require(isinstance(solution, dict) and solution, "fixed layout has no solution map")

    body_owner: dict[tuple[int, int], str] = {}
    for instance_id, selected in solution.items():
        facility_type = str(selected["facility_type"])
        _require(
            facility_type in facility_pools,
            f"unknown facility pool for {instance_id}: {facility_type}",
        )
        poses = facility_pools[facility_type]
        pose_idx = int(selected["pose_idx"])
        _require(0 <= pose_idx < len(poses), f"pose index out of range: {instance_id}")
        pose = poses[pose_idx]
        _require(
            pose["pose_id"] == selected["pose_id"],
            f"pose id mismatch for {instance_id}",
        )
        for raw_cell in pose["occupied_cells"]:
            occupied = _cell(raw_cell, label=f"occupied cell for {instance_id}")
            _require(
                occupied not in body_owner,
                f"fixed layout body overlap at {occupied}: "
                f"{body_owner.get(occupied)} and {instance_id}",
            )
            body_owner[occupied] = str(instance_id)

    body_cells_inside_rect = sorted(cell for cell in body_owner if _inside(rect, cell))
    _require(
        not body_cells_inside_rect,
        f"fixed rectangle intersects facility bodies: {body_cells_inside_rect[:8]}",
    )

    proof_object = judgment["proof_object"]
    proof_step_count = _count_numbered_proof_steps(proof_path)
    _require(
        proof_step_count == int(proof_object["proof_step_count"]),
        "Judgment proof_step_count does not match 02_PROOF.md section 5",
    )
    target_id = str(proof_object["target_instance_id"])
    _require(target_id in solution, f"target instance is absent: {target_id}")
    selected = solution[target_id]
    _require(
        selected["facility_type"] == proof_object["expected_facility_type"],
        "target facility type mismatch",
    )
    _require(
        int(selected["pose_idx"]) == int(proof_object["expected_pose_idx"]),
        "target pose index mismatch",
    )
    _require(
        selected["pose_id"] == proof_object["expected_pose_id"],
        "target pose id mismatch",
    )

    target_pose = facility_pools[selected["facility_type"]][int(selected["pose_idx"])]
    _require(target_pose["input_port_cells"] == [], "target unexpectedly has input ports")
    output_ports = target_pose["output_port_cells"]
    _require(len(output_ports) == 1, "target does not have exactly one output front")
    output = output_ports[0]
    front = int(output["x"]), int(output["y"])
    expected_front = _cell(
        proof_object["expected_unique_output_front_cell"],
        label="expected target front",
    )
    _require(front == expected_front, f"target front mismatch: {front}")
    _require(output["dir"] == proof_object["expected_direction"], "direction mismatch")
    _require(_inside(rect, front), f"target front is not inside fixed rectangle: {front}")

    sibling = judgment["redundant_sibling_witness"]
    sibling_id = str(sibling["instance_id"])
    _require(sibling_id in solution, f"sibling instance is absent: {sibling_id}")
    sibling_selected = solution[sibling_id]
    sibling_pose = facility_pools[sibling_selected["facility_type"]][
        int(sibling_selected["pose_idx"])
    ]
    sibling_outputs = sibling_pose["output_port_cells"]
    _require(len(sibling_outputs) == 1, "sibling does not have one output front")
    sibling_front = int(sibling_outputs[0]["x"]), int(sibling_outputs[0]["y"])
    _require(
        sibling_front
        == _cell(sibling["unique_output_front_cell"], label="expected sibling front"),
        "sibling front mismatch",
    )
    _require(_inside(rect, sibling_front), "sibling front is outside fixed rectangle")

    # The checked contradiction is deliberately tiny:
    # Active(target) -> belt terminal required at front;
    # front in strict-empty R -> every belt terminal forbidden there.
    proof_receipt = {
        "judgment_id": judgment["judgment_id"],
        "problemHash": problem_hash,
        "objectiveHash": objective_hash,
        "contextHash": context_hash,
        "fixed_layout_instance_count": len(solution),
        "fixed_layout_body_cell_count": len(body_owner),
        "fixed_rectangle": rect,
        "fixed_rectangle_body_intersection_count": 0,
        "trigger_atom": context["trigger"],
        "target_front_cell": list(front),
        "target_front_inside_strict_empty_rectangle": True,
        "active_front_requires_belt": True,
        "strict_empty_rectangle_forbids_belt": True,
        "conclusion": "TRIGGERED_BINDING_SELECTION_UNROUTABLE",
        "semantic_fact_count": int(proof_object["semantic_fact_count"]),
        "trigger_atom_count": int(proof_object["trigger_atom_count"]),
        "proof_step_count": proof_step_count,
        "proof_step_count_source": "02_PROOF.md section 5 numbered list",
        "experiment_data_used_as_proof_premise": False,
        "redundant_sibling_front_cell": list(sibling_front),
    }
    return proof_receipt, {"proof_seconds": time.perf_counter() - started}


def _verify_coverage_contract(
    judgment: dict[str, Any],
    snapshot: dict[str, Any],
) -> None:
    coverage = judgment["coverage"]
    _require(
        coverage["status"] == "POST_HOC_OBSERVATIONAL_ONLY",
        "Judgment coverage status is not post-hoc observational",
    )
    _require(
        coverage["identity"] == "非前提,仅事后覆盖数据源",
        "Judgment coverage identity drift",
    )
    _require(coverage["is_proof_premise"] is False, "coverage became a proof premise")
    _require(snapshot["proof_dependency"] is False, "coverage snapshot became a proof premise")
    _require(
        coverage["source_root"] == snapshot["source_run"]["root"],
        "coverage source-root path drift",
    )
    _require(
        coverage["event_journal_path"] == snapshot["event_prefix"]["path"],
        "coverage event-journal path drift",
    )
    _require(
        coverage["feedback_journal_path"] == snapshot["feedback_prefix"]["path"],
        "coverage feedback-journal path drift",
    )


def _matching_example(
    record: dict[str, Any],
    *,
    instance_id: str,
    front_cell: list[int],
    direction: str,
) -> list[dict[str, Any]]:
    return [
        example
        for example in record.get("examples", [])
        if example.get("instance_id") == instance_id
        and example.get("front_cell") == front_cell
        and example.get("direction") == direction
        and bool(example.get("commodity"))
    ]


def _verify_coverage(
    repo_root: Path,
    snapshot: dict[str, Any],
    *,
    proof_step_count: int,
    trigger_atom_count: int,
) -> tuple[dict[str, Any], dict[str, float]]:
    started = time.perf_counter()
    event_spec = snapshot["event_prefix"]
    event_path = repo_root / event_spec["path"]
    event_records, event_raw = _read_jsonl_prefix(
        event_path,
        int(event_spec["record_count"]),
    )
    _require(len(event_raw) == int(event_spec["prefix_size_bytes"]), "event prefix size drift")
    _require(
        hashlib.sha256(event_raw).hexdigest() == event_spec["prefix_sha256"],
        "event prefix SHA-256 drift",
    )

    event_indices = [int(record["event_index"]) for record in event_records]
    expected_indices = list(
        range(
            int(event_spec["first_event_index"]),
            int(event_spec["last_event_index"]) + 1,
        )
    )
    _require(event_indices == expected_indices, "event indices are not the frozen sequence")
    selection_digests = [str(record["selection_digest"]) for record in event_records]
    _require(
        len(set(selection_digests)) == int(event_spec["unique_selection_digest_count"]),
        "selection digest cardinality drift",
    )
    _require(
        all(record.get("record_type") == "routing_precheck_failure" for record in event_records),
        "event prefix includes a non-precheck-failure record",
    )
    _require(
        all(record.get("reason") == "routing_front_blocked" for record in event_records),
        "event prefix includes a non-front_blocked reason",
    )

    primary = snapshot["primary_trigger_measurement"]
    primary_matches = [
        _matching_example(
            record,
            instance_id=primary["instance_id"],
            front_cell=primary["expected_front_cell"],
            direction=primary["expected_direction"],
        )
        for record in event_records
    ]
    _require(
        all(len(matches) == 1 for matches in primary_matches),
        "primary trigger is not represented exactly once in every frozen event",
    )
    primary_count = sum(bool(matches) for matches in primary_matches)
    _require(
        primary_count == int(primary["matching_record_count"]),
        "primary trigger coverage drift",
    )
    primary_commodities = sorted(
        {str(matches[0]["commodity"]) for matches in primary_matches}
    )
    _require(
        primary_commodities == primary["commodity_values_seen"],
        "primary commodity observation drift",
    )
    primary_blockers = sorted(
        {
            str(blocker)
            for matches in primary_matches
            for blocker in matches[0].get("blocking_instance_ids", [])
        }
    )
    _require(
        primary_blockers == primary["blocking_instance_ids_seen"],
        "primary blocker observation drift",
    )

    sibling = snapshot["redundant_sibling_measurement"]
    sibling_matches = [
        _matching_example(
            record,
            instance_id=sibling["instance_id"],
            front_cell=sibling["expected_front_cell"],
            direction=sibling["expected_direction"],
        )
        for record in event_records
    ]
    _require(
        all(len(matches) == 1 for matches in sibling_matches),
        "sibling trigger is not represented exactly once in every frozen event",
    )
    sibling_count = sum(bool(matches) for matches in sibling_matches)
    _require(
        sibling_count == int(sibling["matching_record_count"]),
        "sibling trigger coverage drift",
    )

    signature_distribution = Counter(
        str(record["local_signature_digest"]) for record in event_records
    )
    _require(
        dict(signature_distribution) == snapshot["signature_distribution"],
        "local-signature distribution drift",
    )

    feedback_spec = snapshot["feedback_prefix"]
    feedback_path = repo_root / feedback_spec["path"]
    feedback_records, feedback_raw = _read_jsonl_prefix(
        feedback_path,
        int(feedback_spec["record_count"]),
    )
    _require(
        len(feedback_raw) == int(feedback_spec["prefix_size_bytes"]),
        "feedback prefix size drift",
    )
    _require(
        hashlib.sha256(feedback_raw).hexdigest() == feedback_spec["prefix_sha256"],
        "feedback prefix SHA-256 drift",
    )

    applied = [
        record for record in feedback_records if record.get("record_type") == "feedback_applied"
    ]
    outcomes = [
        record for record in feedback_records if record.get("record_type") == "feedback_outcome"
    ]
    _require(
        len(applied) == int(feedback_spec["feedback_applied_count"]),
        "feedback_applied count drift",
    )
    _require(
        len(outcomes) == int(feedback_spec["feedback_outcome_count"]),
        "feedback_outcome count drift",
    )
    expected_literal_count = int(feedback_spec["point_nogood_literal_count_each"])
    _require(
        all(int(record["literal_count"]) == expected_literal_count for record in applied),
        "point-nogood literal count drift",
    )
    _require(
        sum(int(record["literal_count"]) for record in applied)
        == int(feedback_spec["point_nogood_literal_count_total"]),
        "point-nogood total literal count drift",
    )
    _require(
        all(record.get("effect") is True for record in outcomes),
        "feedback effect observation drift",
    )
    _require(
        all(record.get("reachabilityFailureClass") == "EFFECT_NO_TERMINAL" for record in outcomes),
        "feedback outcome class drift",
    )

    applied_by_index = {int(record["event_index"]): record for record in applied}
    _require(len(applied_by_index) == len(applied), "duplicate applied event indices")
    for event in event_records:
        index = int(event["event_index"])
        _require(index in applied_by_index, f"missing feedback for event {index}")
        _require(
            applied_by_index[index]["selection_digest"] == event["selection_digest"],
            f"selection digest mismatch at event {index}",
        )

    ext_count = primary_count
    proof_steps = int(proof_step_count)
    trigger_atoms = int(trigger_atom_count)
    _require(proof_steps > 0, "proof-step count must be positive")
    _require(trigger_atoms > 0, "trigger-atom count must be positive")
    certificate_atoms = proof_steps + trigger_atoms
    point_literals = int(feedback_spec["point_nogood_literal_count_total"])
    coverage_receipt = {
        "snapshot_id": snapshot["snapshot_id"],
        "coverage_source_identity": "非前提,仅事后覆盖数据源",
        "event_journal_path": event_spec["path"],
        "feedback_journal_path": feedback_spec["path"],
        "event_prefix_sha256": event_spec["prefix_sha256"],
        "feedback_prefix_sha256": feedback_spec["prefix_sha256"],
        "observed_distinct_binding_selection_count": len(set(selection_digests)),
        "observed_Ext_J_count": ext_count,
        "observed_Ext_J_denominator": len(event_records),
        "observed_Ext_J_fraction": ext_count / len(event_records),
        "primary_trigger_instance_id": primary["instance_id"],
        "primary_trigger_front_cell": primary["expected_front_cell"],
        "redundant_sibling_coverage_count": sibling_count,
        "point_nogood_literal_count_total": point_literals,
        "certificate_atom_count": certificate_atoms,
        "coarse_point_literal_to_certificate_atom_ratio": point_literals
        / certificate_atoms,
        "ln_Ext_per_proof_step": math.log(ext_count) / proof_steps,
        "ln_Ext_per_certificate_atom": math.log(ext_count) / certificate_atoms,
        "coverage_is_a_proof_premise": False,
    }
    return coverage_receipt, {"coverage_seconds": time.perf_counter() - started}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument(
        "--coverage",
        choices=("auto", "required", "off"),
        default="auto",
        help="check the frozen observational prefix when available",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    total_started = time.perf_counter()
    script_path = Path(__file__).resolve()
    repo_root = (args.repo_root or _infer_repo_root(script_path)).resolve()
    experiment_dir = script_path.parent

    try:
        judgment = _load_json(experiment_dir / "01_JUDGMENT.json")
        _require(
            judgment["schema_version"] == "zmd_offline_semantic_judgment_v1",
            "unexpected Judgment schema",
        )
        paths, problem_hash, identity_timing = _verify_problem_identity(repo_root, judgment)
        proof_receipt, proof_timing = _verify_semantic_proof(
            paths,
            problem_hash,
            judgment,
            experiment_dir / "02_PROOF.md",
        )

        coverage_receipt: dict[str, Any] | None = None
        coverage_timing = {"coverage_seconds": 0.0}
        snapshot = _load_json(experiment_dir / "04_COVERAGE_SNAPSHOT.json")
        _verify_coverage_contract(judgment, snapshot)
        event_path = repo_root / snapshot["event_prefix"]["path"]
        feedback_path = repo_root / snapshot["feedback_prefix"]["path"]
        coverage_available = event_path.is_file() and feedback_path.is_file()
        if args.coverage == "required":
            _require(coverage_available, "frozen coverage journals are unavailable")
            coverage_receipt, coverage_timing = _verify_coverage(
                repo_root,
                snapshot,
                proof_step_count=int(proof_receipt["proof_step_count"]),
                trigger_atom_count=int(proof_receipt["trigger_atom_count"]),
            )
        elif args.coverage == "auto" and coverage_available:
            coverage_receipt, coverage_timing = _verify_coverage(
                repo_root,
                snapshot,
                proof_step_count=int(proof_receipt["proof_step_count"]),
                trigger_atom_count=int(proof_receipt["trigger_atom_count"]),
            )

        receipt = {
            "schema_version": "zmd_offline_semantic_certificate_check_receipt_v1",
            "status": "PASS",
            "checker_independence": {
                "standard_library_only": True,
                "project_module_imports": [],
                "phase_minus1_harness_imports": [],
                "solver_or_model_imports": [],
            },
            "proof": proof_receipt,
            "coverage_mode": args.coverage,
            "coverage_available": coverage_available,
            "coverage": coverage_receipt,
            "timing": {
                **identity_timing,
                **proof_timing,
                **coverage_timing,
                "total_seconds": time.perf_counter() - total_started,
            },
        }
        print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (CheckError, KeyError, TypeError, ValueError, IndexError) as exc:
        failure = {
            "schema_version": "zmd_offline_semantic_certificate_check_receipt_v1",
            "status": "FAIL",
            "error": str(exc),
            "timing": {"total_seconds": time.perf_counter() - total_started},
        }
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
