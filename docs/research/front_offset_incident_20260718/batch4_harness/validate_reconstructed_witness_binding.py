"""Validate a reconstructed Batch 4 witness with the current binding model.

This is a narrow research validator.  It verifies the witness against the
current candidate-pool bytes, constructs the current identity-front routing
context, and solves the current full port-binding model.  It does not place
power poles, solve routing, or produce certification evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.io.strict_json import loads_strict_json  # noqa: E402
from src.models.binding_subproblem import (  # noqa: E402
    PortBindingModel,
    load_generic_input_slots_by_operation_from_text,
)
from src.models.routing_binding_context import build_routing_binding_context  # noqa: E402


SCHEMA_VERSION = "batch4.reconstructed_witness_binding_validation.v1"
PROVENANCE_LABEL = "reconstructed_new_baseline"
EXPECTED_WITNESS_RUN_SCHEMA = "batch4.reconstructed_witness_run_record.v1"
WORKER_ENV = "EXACT_BINDING_CP_SAT_WORKERS"

INPUT_RELATIVE_PATHS = (
    Path("data/preprocessed/candidate_placements.json"),
    Path("data/preprocessed/mandatory_exact_instances.json"),
    Path("data/preprocessed/generic_io_requirements.json"),
    Path("rules/canonical_rules.json"),
    Path("rules/preprocess_plan.json"),
)
WITNESS_RECORDED_INPUT_PATHS = tuple(path.as_posix() for path in INPUT_RELATIVE_PATHS[:4])


class BindingValidationError(ValueError):
    """Raised when provenance or witness binding input fails closed."""


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _display_path(path: Path, *, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _file_record(path: Path, *, root: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": _display_path(path, root=root),
        "sha256": _sha256_bytes(raw),
        "size_bytes": len(raw),
    }


def _load_json_record(path: Path, *, root: Path) -> tuple[Any, dict[str, Any], str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    return (
        loads_strict_json(text),
        {
            "path": _display_path(path, root=root),
            "sha256": _sha256_bytes(raw),
            "size_bytes": len(raw),
        },
        text,
    )


def _normalize_sha256(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise BindingValidationError(f"{label}: expected 64 hexadecimal characters")
    return normalized


def _strict_pose_idx(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BindingValidationError(f"{label}: pose_idx must be an integer")
    if value < 0:
        raise BindingValidationError(f"{label}: pose_idx must be non-negative")
    return value


def _strict_anchor(value: Any, *, label: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise BindingValidationError(f"{label}: anchor must be an object with integer x/y")
    x = value.get("x")
    y = value.get("y")
    if type(x) is not int or type(y) is not int:
        raise BindingValidationError(f"{label}: anchor must define integer x/y")
    return {"x": x, "y": y}


def _extract_facility_pools(candidate_payload: Any) -> dict[str, list[Mapping[str, Any]]]:
    if not isinstance(candidate_payload, Mapping):
        raise BindingValidationError("candidate pool must be a JSON object")
    raw_pools = candidate_payload.get("facility_pools", candidate_payload)
    if not isinstance(raw_pools, Mapping):
        raise BindingValidationError("candidate pool has no facility_pools object")
    pools: dict[str, list[Mapping[str, Any]]] = {}
    for facility_type, raw_pool in raw_pools.items():
        if not isinstance(raw_pool, list) or not all(isinstance(pose, Mapping) for pose in raw_pool):
            raise BindingValidationError(f"candidate pool {facility_type!r} must be a list of objects")
        pools[str(facility_type)] = list(raw_pool)
    return pools


def _extract_instances(instances_payload: Any) -> list[Mapping[str, Any]]:
    raw_instances = (
        instances_payload.get("instances")
        if isinstance(instances_payload, Mapping)
        else instances_payload
    )
    if not isinstance(raw_instances, list) or not all(
        isinstance(instance, Mapping) for instance in raw_instances
    ):
        raise BindingValidationError("mandatory instances must be a list of objects")
    return list(raw_instances)


def _validate_placement_solution(
    witness_payload: Any,
    facility_pools: Mapping[str, list[Mapping[str, Any]]],
    instances: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if not isinstance(witness_payload, Mapping):
        raise BindingValidationError("witness result must be a JSON object")
    raw_solution = witness_payload.get("solution")
    if not isinstance(raw_solution, Mapping):
        raise BindingValidationError("witness result must contain a solution object")

    canonical_types: dict[str, str] = {}
    for index, instance in enumerate(instances):
        instance_id = instance.get("instance_id")
        facility_type = instance.get("facility_type")
        if not isinstance(instance_id, str) or not instance_id:
            raise BindingValidationError(f"mandatory instances[{index}] has invalid instance_id")
        if not isinstance(facility_type, str) or not facility_type:
            raise BindingValidationError(f"mandatory instances[{index}] has invalid facility_type")
        if instance_id in canonical_types:
            raise BindingValidationError(f"duplicate mandatory instance_id {instance_id!r}")
        canonical_types[instance_id] = facility_type

    solution_ids = {str(instance_id) for instance_id in raw_solution}
    missing_ids = sorted(set(canonical_types) - solution_ids)
    extra_ids = sorted(solution_ids - set(canonical_types))
    if missing_ids or extra_ids:
        raise BindingValidationError(
            "witness solution must select exactly the mandatory instances: "
            f"missing={missing_ids[:5]!r}, extra={extra_ids[:5]!r}"
        )

    normalized: dict[str, dict[str, Any]] = {}
    entries_with_pose_id = 0
    entries_with_anchor = 0
    for instance_id in sorted(canonical_types):
        raw_entry = raw_solution[instance_id]
        if not isinstance(raw_entry, Mapping):
            raise BindingValidationError(f"solution entry {instance_id!r} must be an object")
        facility_type = raw_entry.get("facility_type")
        if facility_type != canonical_types[instance_id]:
            raise BindingValidationError(
                f"solution entry {instance_id!r} facility_type {facility_type!r} does not match "
                f"mandatory metadata {canonical_types[instance_id]!r}"
            )
        pool = facility_pools.get(str(facility_type))
        if pool is None:
            raise BindingValidationError(
                f"solution entry {instance_id!r} names unknown pool {facility_type!r}"
            )
        pose_idx = _strict_pose_idx(raw_entry.get("pose_idx"), label=f"solution entry {instance_id!r}")
        if pose_idx >= len(pool):
            raise BindingValidationError(
                f"solution entry {instance_id!r} pose_idx {pose_idx} is outside "
                f"{facility_type!r} pool size {len(pool)}"
            )
        pose = pool[pose_idx]

        if "pose_id" in raw_entry:
            carried_pose_id = raw_entry["pose_id"]
            if not isinstance(carried_pose_id, str) or not carried_pose_id:
                raise BindingValidationError(
                    f"solution entry {instance_id!r} pose_id must be a non-empty string"
                )
            if pose.get("pose_id") != carried_pose_id:
                raise BindingValidationError(
                    f"solution entry {instance_id!r} carries pose_id {carried_pose_id!r}, "
                    f"but selected pose has {pose.get('pose_id')!r}"
                )
            entries_with_pose_id += 1
        if "anchor" in raw_entry:
            carried_anchor = _strict_anchor(
                raw_entry["anchor"], label=f"solution entry {instance_id!r}"
            )
            selected_anchor = _strict_anchor(
                pose.get("anchor"), label=f"candidate {facility_type}[{pose_idx}]"
            )
            if carried_anchor != selected_anchor:
                raise BindingValidationError(
                    f"solution entry {instance_id!r} carries anchor {carried_anchor!r}, "
                    f"but selected pose has {selected_anchor!r}"
                )
            entries_with_anchor += 1

        normalized[instance_id] = {
            "facility_type": str(facility_type),
            "pose_idx": pose_idx,
        }

    placed = witness_payload.get("placed")
    if placed is not None and placed != len(normalized):
        raise BindingValidationError(
            f"witness placed={placed!r} does not match solution count {len(normalized)}"
        )
    return normalized, {
        "candidate_index_mapping": "verified_against_expected_candidate_sha256",
        "entries_with_anchor": entries_with_anchor,
        "entries_with_pose_id": entries_with_pose_id,
        "mandatory_instance_count": len(canonical_types),
        "selected_pose_count": len(normalized),
    }


def _verify_witness_run_record(
    run_record: Any,
    *,
    witness_record: Mapping[str, Any],
    input_records: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(run_record, Mapping):
        raise BindingValidationError("companion run_record.json must be an object")
    if run_record.get("schema") != EXPECTED_WITNESS_RUN_SCHEMA:
        raise BindingValidationError("companion run_record.json has an unsupported schema")
    if run_record.get("source") != PROVENANCE_LABEL:
        raise BindingValidationError("companion run_record.json is not reconstructed_new_baseline")
    if run_record.get("hash_seed") != 0:
        raise BindingValidationError("reconstructed witness run_record hash_seed must be 0")

    outputs = run_record.get("outputs")
    result_record = outputs.get("result") if isinstance(outputs, Mapping) else None
    if not isinstance(result_record, Mapping) or result_record.get("sha256") != witness_record["sha256"]:
        raise BindingValidationError("companion run_record result SHA-256 does not match witness bytes")

    recorded_inputs = run_record.get("input_sha256s")
    if not isinstance(recorded_inputs, Mapping):
        raise BindingValidationError("companion run_record has no input_sha256s object")
    for relative_path in WITNESS_RECORDED_INPUT_PATHS:
        recorded = recorded_inputs.get(relative_path)
        current = input_records.get(relative_path)
        if not isinstance(recorded, Mapping) or current is None:
            raise BindingValidationError(
                f"companion run_record is missing input provenance for {relative_path}"
            )
        if recorded.get("sha256") != current.get("sha256"):
            raise BindingValidationError(
                f"companion run_record input SHA-256 drift for {relative_path}"
            )

    recorded_sources = run_record.get("source_sha256s")
    if not isinstance(recorded_sources, Mapping):
        raise BindingValidationError("companion run_record has no source_sha256s object")
    return {
        "binding_enabled_during_construction": bool(run_record.get("binding_enabled", False)),
        "construction_revision": dict(run_record.get("revision", {})),
        "recorded_constructor_source_sha256s": dict(recorded_sources),
        "run_schema": str(run_record["schema"]),
        "source": str(run_record["source"]),
    }


def _git_revision(*, root: Path) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    status_lines = status.splitlines()
    return {
        "commit": commit,
        "dirty": bool(status_lines),
        "dirty_snapshot_taken_before_output_creation": True,
        "status_porcelain_v1": status_lines,
        "status_porcelain_v1_sha256": _sha256_bytes(status.encode("utf-8")),
    }


def _loaded_repository_source_records(*, root: Path) -> dict[str, dict[str, Any]]:
    paths = {Path(__file__).resolve()}
    resolved_root = root.resolve()
    for module in tuple(sys.modules.values()):
        raw_path = getattr(module, "__file__", None)
        if not raw_path:
            continue
        path = Path(raw_path).resolve()
        if path.suffix in {".pyc", ".pyo"}:
            try:
                path = Path(importlib.util.source_from_cache(str(path))).resolve()
            except ValueError:
                continue
        if path.suffix != ".py" or not path.is_file():
            continue
        try:
            path.relative_to(resolved_root)
        except ValueError:
            continue
        paths.add(path)
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(paths):
        record = _file_record(path, root=root)
        records[str(record["path"])] = {
            "sha256": record["sha256"],
            "size_bytes": record["size_bytes"],
        }
    return records


def _summary_scalars(summary: Mapping[str, Any]) -> dict[str, Any]:
    scalar_types = (bool, int, float, str)
    return {
        str(key): value
        for key, value in sorted(summary.items(), key=lambda item: str(item[0]))
        if value is None or isinstance(value, scalar_types)
    }


def _selection_counts(selection: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    non_unused_total = 0
    total = 0
    for section in ("binding_choice", "generic_inputs", "generic_outputs"):
        values = selection.get(section, {})
        if not isinstance(values, Mapping):
            values = {}
        count = len(values)
        non_unused = sum(value != "__unused__" for value in values.values())
        counts[f"{section}_count"] = count
        counts[f"{section}_non_unused_count"] = non_unused
        total += count
        non_unused_total += non_unused
    counts["total"] = total
    counts["non_unused_total"] = non_unused_total
    return counts


def _canonical_slot_records(slots: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(slot) for slot in sorted(slots, key=lambda slot: str(slot.get("slot_id", "")))]


def validate_reconstructed_witness_binding(
    witness_path: Path,
    *,
    expected_candidate_sha256: str,
    time_limit: float = 30.0,
    workers: int = 1,
    project_root: Path = PROJECT_ROOT,
    process_argv: Sequence[str] | None = None,
    revision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise BindingValidationError("PYTHONHASHSEED=0 must be set before starting Python")
    if time_limit <= 0:
        raise BindingValidationError("--time-limit must be positive")
    if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
        raise BindingValidationError("--workers must be a positive integer")
    expected_sha = _normalize_sha256(
        expected_candidate_sha256,
        label="--expected-candidate-sha256",
    )

    root = project_root.resolve()
    input_payloads: dict[str, Any] = {}
    input_texts: dict[str, str] = {}
    input_records: dict[str, dict[str, Any]] = {}
    for relative_path in INPUT_RELATIVE_PATHS:
        payload, record, text = _load_json_record(root / relative_path, root=root)
        relative_name = relative_path.as_posix()
        input_payloads[relative_name] = payload
        input_texts[relative_name] = text
        input_records[relative_name] = {
            "sha256": record["sha256"],
            "size_bytes": record["size_bytes"],
        }

    candidate_name = INPUT_RELATIVE_PATHS[0].as_posix()
    actual_candidate_sha = str(input_records[candidate_name]["sha256"])
    if actual_candidate_sha != expected_sha:
        raise BindingValidationError(
            f"candidate pool SHA-256 mismatch: expected {expected_sha}, got {actual_candidate_sha}"
        )

    witness_payload, witness_record, _witness_text = _load_json_record(witness_path, root=root)
    run_record_path = witness_path.with_name("run_record.json")
    if not run_record_path.is_file():
        raise BindingValidationError(
            f"reconstructed witness companion run_record.json is missing: {run_record_path}"
        )
    run_record_payload, run_record_record, _run_record_text = _load_json_record(
        run_record_path,
        root=root,
    )
    witness_provenance = _verify_witness_run_record(
        run_record_payload,
        witness_record=witness_record,
        input_records=input_records,
    )

    facility_pools = _extract_facility_pools(input_payloads[candidate_name])
    instances = _extract_instances(input_payloads[INPUT_RELATIVE_PATHS[1].as_posix()])
    placement_solution, placement_stats = _validate_placement_solution(
        witness_payload,
        facility_pools,
        instances,
    )

    generic_payload = input_payloads[INPUT_RELATIVE_PATHS[2].as_posix()]
    rules_payload = input_payloads[INPUT_RELATIVE_PATHS[3].as_posix()]
    if not isinstance(generic_payload, Mapping):
        raise BindingValidationError("generic_io_requirements must be an object")
    if not isinstance(rules_payload, Mapping):
        raise BindingValidationError("canonical_rules must be an object")
    required_generic_outputs = generic_payload.get("required_generic_outputs")
    required_generic_inputs = generic_payload.get("required_generic_inputs")
    if not isinstance(required_generic_outputs, Mapping) or not isinstance(
        required_generic_inputs, Mapping
    ):
        raise BindingValidationError("generic_io_requirements sections must be objects")
    try:
        grid = rules_payload["globals"]["grid"]
        grid_width = int(grid["width"])
        grid_height = int(grid["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BindingValidationError("canonical_rules globals.grid width/height are invalid") from exc
    slot_map = load_generic_input_slots_by_operation_from_text(
        text=input_texts[INPUT_RELATIVE_PATHS[4].as_posix()]
    )

    routing_context = build_routing_binding_context(
        placement_solution,
        facility_pools,
        grid_w=grid_width,
        grid_h=grid_height,
    )
    previous_worker_env = os.environ.get(WORKER_ENV)
    os.environ[WORKER_ENV] = str(workers)
    try:
        build_started = time.perf_counter()
        binding_model = PortBindingModel(
            placement_solution,
            facility_pools,
            instances,
            required_generic_outputs=dict(required_generic_outputs),
            required_generic_inputs=dict(required_generic_inputs),
            project_root=root,
            generic_input_slots_by_operation=slot_map,
            routing_context=routing_context,
            canonical_rules_payload=rules_payload,
        )
        binding_model.build(use_overload_separation=False)
        build_seconds = time.perf_counter() - build_started

        build_summary = binding_model.extract_conflict_summary()
        empty_domains = binding_model.extract_empty_binding_domain_instances()
        proto = binding_model.model.Proto()
        solve_started = time.perf_counter()
        status = binding_model.solve(time_limit_seconds=float(time_limit))
        solve_seconds = time.perf_counter() - solve_started
        final_summary = binding_model.extract_conflict_summary()
        selection = binding_model.extract_selection()
    finally:
        if previous_worker_env is None:
            os.environ.pop(WORKER_ENV, None)
        else:
            os.environ[WORKER_ENV] = previous_worker_env

    argv_record = list(process_argv) if process_argv is not None else list(sys.argv)
    revision_record = dict(revision) if revision is not None else _git_revision(root=root)
    source_records = _loaded_repository_source_records(root=root)
    return {
        "binding": {
            "build_seconds": round(build_seconds, 6),
            "build_stats": {
                "conflict_summary_scalars": _summary_scalars(build_summary),
                "cp_model_constraint_count": len(proto.constraints),
                "cp_model_variable_count": len(proto.variables),
                "routing_aware_filter_stats": dict(binding_model.routing_aware_filter_stats),
            },
            "conflict_summary_scalars": _summary_scalars(final_summary),
            "empty_binding_domains": list(empty_domains),
            "generic_slots": {
                "inputs": _canonical_slot_records(binding_model.generic_input_slots),
                "outputs": _canonical_slot_records(binding_model.generic_output_slots),
            },
            "overload_separation": "forced_off_for_hard_binding_validation",
            "selection_count": _selection_counts(selection),
            "solve_seconds": round(solve_seconds, 6),
            "status": status,
        },
        "candidate_binding": {
            "actual_candidate_sha256": actual_candidate_sha,
            "expected_candidate_sha256": expected_sha,
            **placement_stats,
        },
        "execution": {
            "argv": argv_record,
            "cwd": str(Path.cwd()),
            "environment": {
                WORKER_ENV: str(workers),
                "PYTHONDONTWRITEBYTECODE": os.environ.get("PYTHONDONTWRITEBYTECODE"),
                "PYTHONHASHSEED": "0",
            },
            "environment_scope": "solver-relevant variables only; unrelated process environment omitted",
            "python_executable": str(Path(sys.executable).absolute()),
            "time_limit_seconds": float(time_limit),
        },
        "label": PROVENANCE_LABEL,
        "limitations": {
            "included": "mandatory placement selection plus current identity-front binding only",
            "not_included": [
                "power optional placement",
                "routing solve",
                "certification",
            ],
        },
        "provenance": {
            "input_sha256s": input_records,
            "loaded_repository_source_sha256s": source_records,
            "revision": revision_record,
            "witness": {
                "result": {
                    "path": witness_record["path"],
                    "sha256": witness_record["sha256"],
                    "size_bytes": witness_record["size_bytes"],
                },
                "run_record": {
                    "path": run_record_record["path"],
                    "sha256": run_record_record["sha256"],
                    "size_bytes": run_record_record["size_bytes"],
                },
                **witness_provenance,
            },
        },
        "routing_context": {
            "component_count": len(routing_context.cells_by_component),
            "grid": {"height": grid_height, "width": grid_width},
            "occupied_cell_count": len(routing_context.occupied_cells),
            "owned_occupied_cell_count": len(routing_context.occupied_owner_by_cell),
        },
        "schema_version": SCHEMA_VERSION,
        "solver_determinism": {
            "binding_workers": workers,
            "cp_sat_seed_api_exposed": False,
            "cp_sat_seed_requested": None,
            "cp_sat_seed_semantics": (
                "PortBindingModel.solve exposes time_limit_seconds but no binding seed and does not "
                "set CpSolver.random_seed; the installed OR-Tools default applies"
            ),
            "python_hash_seed": 0,
        },
    }


def deterministic_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("witness", type=Path, help="reconstructed witness result.json")
    parser.add_argument("--expected-candidate-sha256", required=True)
    parser.add_argument("--time-limit", type=float, default=30.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    output_path = args.output.expanduser().resolve()
    if output_path.exists():
        parser.error(f"refusing to overwrite existing output: {output_path}")
    if output_path in {args.witness.resolve(), args.witness.with_name("run_record.json").resolve()}:
        parser.error("--output must not overwrite witness inputs")

    revision = _git_revision(root=PROJECT_ROOT)
    process_argv = list(sys.argv) if argv is None else [str(Path(__file__)), *map(str, argv)]
    try:
        report = validate_reconstructed_witness_binding(
            args.witness,
            expected_candidate_sha256=args.expected_candidate_sha256,
            time_limit=args.time_limit,
            workers=args.workers,
            process_argv=process_argv,
            revision=revision,
        )
    except (
        BindingValidationError,
        FileNotFoundError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        parser.error(str(exc))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("x", encoding="utf-8") as output_file:
            output_file.write(deterministic_json(report))
    except FileExistsError:
        parser.error(f"refusing to overwrite existing output: {output_path}")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
