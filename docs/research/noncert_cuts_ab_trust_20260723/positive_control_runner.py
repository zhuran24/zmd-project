#!/usr/bin/env python3
"""Run one no-overwrite arm of the post-fix injected cut positive control.

This is a direct, non-certified research harness.  It preserves the production
injection drill's construction discipline, but keeps the attach switch absent
until after the real LBBD run has produced a frozen incumbent.  The only
injected fact is the ``binding_infeasible`` trigger.  State construction,
oracles, typed compilation/application, and the audit ledger remain real.

The runner deliberately records only enough compiled-plan information to check
that an applied inequality excludes the frozen incumbent.  It is not a cut
soundness verifier or a proof ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
RUN_ROOT = PROJECT_ROOT / ".artifacts" / "noncert_cuts_ab_trust_20260723"
CORE_PLAN = Path("/home/zhuran24/zmd-pj-codex/核心计划书.md")
EXPECTED_IDENTITIES = {
    "core_plan": (
        CORE_PLAN,
        26_734,
        "0987d2d0a22da57b72ee94e3eb4d232a7389461f2ed031764d938a0789157422",
    ),
    "project_lock": (
        PROJECT_ROOT / "PROJECT_LOCK.md",
        147_405,
        "33632dfdb2297425e42066b2cf0749ca6b9ab1f8653e810b6f2e53ded1025410",
    ),
    "candidate_placements": (
        PROJECT_ROOT / "data" / "preprocessed" / "candidate_placements.json",
        54_467_709,
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    ),
}
ENABLED_FAMILIES = (
    "region_capacity",
    "shape_packing_hall",
    "power_hitting_set",
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_identity(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"identity path must be a regular non-symlink file: {path}")
    data = path.read_bytes()
    return {
        "path": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _git_head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.stdout.strip()


def _jsonable(value: object) -> object:
    if value is None or type(value) in {bool, int, float, str}:
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_jsonable(item) for item in value]
        return sorted(items, key=_canonical_bytes)
    raise TypeError(f"unsupported captured value: {type(value).__name__}")


def _reject_symlink_chain(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"symlink path component rejected: {current}")


def _prepare_attempt_dir(raw_path: Path) -> Path:
    attempt = raw_path.absolute()
    _reject_symlink_chain(attempt.parent)
    root = RUN_ROOT.absolute()
    if attempt == root or root not in attempt.parents:
        raise RuntimeError(f"attempt directory must be below {root}")
    if not attempt.parent.is_dir():
        raise RuntimeError(f"attempt parent must already exist: {attempt.parent}")
    if attempt.exists() or attempt.is_symlink():
        raise FileExistsError(f"attempt directory already exists: {attempt}")
    attempt.mkdir(mode=0o700)
    for name in ("checkpoint", "ledger", "progress", "tmp"):
        (attempt / name).mkdir(mode=0o700)
    return attempt


def _write_json_exclusive(path: Path, payload: object) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite output: {path}")
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


def _authority() -> dict[str, object]:
    head = _git_head()
    if head != EXPECTED_HEAD:
        raise RuntimeError(f"repository identity drift: {head} != {EXPECTED_HEAD}")
    identities: dict[str, object] = {}
    for name, (path, expected_size, expected_sha) in EXPECTED_IDENTITIES.items():
        actual = _file_identity(path)
        if actual["size"] != expected_size or actual["sha256"] != expected_sha:
            raise RuntimeError(f"authority identity mismatch for {name}: {actual}")
        identities[name] = actual
    interpreter = Path(sys.executable).resolve()
    identities["python"] = _file_identity(interpreter)
    identities["runner"] = _file_identity(Path(__file__).resolve())
    for name, relpath in {
        "legacy_injection_drill": ("docs/research/batch_ce_attach_host_20260712/injection_drill_runner.py"),
        "benders_loop": "src/search/benders_loop.py",
        "typed_platform": "src/cuts/typed_platform.py",
        "typed_apply": "src/cuts/typed_apply.py",
        "cut_ledger": "src/cuts/ledger.py",
    }.items():
        identities[name] = _file_identity(PROJECT_ROOT / relpath)
    return {
        "repository_head": head,
        "project_root": str(PROJECT_ROOT),
        "identities": identities,
    }


def _solution_group_entries(
    master: Any,
    solution: Mapping[str, Mapping[str, Any]],
    group_id: str,
) -> tuple[Mapping[str, Any], list[Mapping[str, Any]]]:
    group = next(
        (group for group in master._mandatory_groups if str(group.get("group_id")) == str(group_id)),
        None,
    )
    if not isinstance(group, Mapping):
        raise RuntimeError(f"compiled cut references unknown group: {group_id}")
    entries = [
        solution[str(instance_id)] for instance_id in group.get("instance_ids", ()) if str(instance_id) in solution
    ]
    return group, entries


def _literal_value(index: int, solver_values: Sequence[int]) -> int:
    variable_index = index if index >= 0 else -index - 1
    if variable_index < 0 or variable_index >= len(solver_values):
        raise RuntimeError(f"literal index outside frozen solver response: {index}")
    value = int(solver_values[variable_index])
    return value if index >= 0 else 1 - value


def _arithmetic_sample(
    compiled_cut: Any,
    master: Any,
    scope_binding: Any,
    solution: Mapping[str, Mapping[str, Any]],
    solver_values: Sequence[int],
) -> dict[str, object]:
    plan = compiled_cut.plan
    operation = str(plan.operation)
    parameters = plan.parameters
    contributions: list[dict[str, object]] = []

    if operation == "region_capacity_le":
        for group_id in sorted(parameters["group_cell_weights"]):
            weight = int(parameters["group_cell_weights"][group_id])
            _group, entries = _solution_group_entries(master, solution, str(group_id))
            contributions.append(
                {
                    "label": str(group_id),
                    "selected_count": len(entries),
                    "weight": weight,
                    "value": len(entries) * weight,
                }
            )
        rhs = int(parameters["capacity"])
    elif operation == "shape_packing_hall_le":
        group_id = str(parameters["group_id"])
        region_kind = str(parameters["region_kind"])
        group, entries = _solution_group_entries(master, solution, group_id)
        template = str(group["facility_type"])
        selected_on_baseline = 0
        for entry in entries:
            pose_idx = int(entry["pose_idx"])
            pose = master.facility_pools[template][pose_idx]
            cells = [(int(cell[0]), int(cell[1])) for cell in (pose.get("occupied_cells") or ())]
            if not cells:
                raise RuntimeError(f"selected pose lacks occupied_cells: {template}[{pose_idx}]")
            if region_kind == "left_baseline":
                on_baseline = all(y == 0 for _x, y in cells)
            elif region_kind == "bottom_baseline":
                on_baseline = all(x == 0 for x, _y in cells)
            else:
                raise RuntimeError(f"unknown baseline kind: {region_kind}")
            if on_baseline:
                selected_on_baseline += 1
        contributions.append(
            {
                "label": group_id,
                "selected_count": selected_on_baseline,
                "weight": 1,
                "value": selected_on_baseline,
            }
        )
        rhs = int(parameters["capacity"])
    elif operation == "power_pose_exclusion":
        group_id = str(parameters["group_id"])
        target_pose_id = str(parameters["pose_id"])
        _group, entries = _solution_group_entries(master, solution, group_id)
        selected = sum(1 for entry in entries if str(entry.get("pose_id")) == target_pose_id)
        contributions.append(
            {
                "label": f"{group_id}:{target_pose_id}",
                "selected_count": selected,
                "weight": 1,
                "value": selected,
            }
        )
        rhs = 0
    else:
        raise RuntimeError(f"unsupported arithmetic operation: {operation}")

    enforcement_values = []
    enforcement_literals = []
    for literal in scope_binding.condition_lits:
        index = int(literal.Index())
        value = _literal_value(index, solver_values)
        enforcement_values.append(value)
        enforcement_literals.append(
            {
                "index": index,
                "name": str(literal.Name()),
                "value": value,
            }
        )
    lhs = sum(int(item["value"]) for item in contributions)
    active = all(value == 1 for value in enforcement_values)
    violated = bool(active and lhs > rhs)
    return {
        "cut_id": str(compiled_cut.cut_id),
        "family": str(plan.family),
        "operation": operation,
        "plan_digest": str(plan.digest),
        "compiled_digest": str(compiled_cut.digest),
        "parameters": _jsonable(parameters),
        "enforcement_literals": enforcement_literals,
        "enforcement_values": enforcement_values,
        "contributions": contributions,
        "lhs": lhs,
        "rhs": rhs,
        "active": active,
        "violated": violated,
    }


def _compiled_record(compiled_cut: Any) -> dict[str, object]:
    plan = compiled_cut.plan
    scope = plan.model_scope
    return {
        "cut_id": str(compiled_cut.cut_id),
        "family": str(plan.family),
        "proof_digest": str(compiled_cut.proof_digest),
        "scope_digest": str(compiled_cut.scope_digest),
        "snapshot_digest": str(compiled_cut.snapshot_digest),
        "compiled_digest": str(compiled_cut.digest),
        "plan": {
            "family": str(plan.family),
            "schema_version": int(plan.schema_version),
            "semantic_fingerprint": str(plan.semantic_fingerprint),
            "operation": str(plan.operation),
            "parameters": _jsonable(plan.parameters),
            "digest": str(plan.digest),
            "model_scope": {
                "domain_fingerprint": str(scope.domain_fingerprint),
                "ghost_policy": str(scope.ghost_policy),
                "ghost_rect_digest": scope.ghost_rect_digest,
            },
        },
    }


def _event_counts(events: Iterable[Mapping[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        kind = str(event.get("event", ""))
        counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


def _progress(attempt: Path, index: int, stage: str, payload: object) -> None:
    _write_json_exclusive(
        attempt / "progress" / f"{index:03d}-{stage}.json",
        {"stage": stage, "payload": payload},
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("control", "treatment"), required=True)
    parser.add_argument("--attempt-dir", type=Path, required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--ghost-w", type=int, default=6)
    parser.add_argument("--ghost-h", type=int, default=6)
    parser.add_argument("--master-seconds", type=float, default=900.0)
    parser.add_argument("--binding-seconds", type=float, default=600.0)
    parser.add_argument("--routing-seconds", type=float, default=600.0)
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument("--binding-alt-cap", type=int, default=200)
    parser.add_argument("--post-attach-seconds", type=float, default=120.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=2026072301)
    args = parser.parse_args(argv)
    if args.workers != 1:
        parser.error("Gate 1 requires exactly one worker")
    if args.ghost_w <= 0 or args.ghost_h <= 0:
        parser.error("ghost dimensions must be positive")
    for name in (
        "master_seconds",
        "binding_seconds",
        "routing_seconds",
        "post_attach_seconds",
    ):
        if float(getattr(args, name)) <= 0:
            parser.error(f"{name.replace('_', '-')} must be positive")
    if args.max_iterations <= 0 or args.binding_alt_cap <= 0:
        parser.error("iteration and binding caps must be positive")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    attempt = _prepare_attempt_dir(args.attempt_dir)
    os.environ["TMPDIR"] = str(attempt / "tmp")
    os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
    os.environ["EXACT_CP_SAT_WORKERS"] = "1"
    os.environ["EXACT_MASTER_CP_SAT_WORKERS"] = "1"
    os.environ["EXACT_MASTER_RANDOM_SEED"] = str(args.seed)
    os.environ["EXACT_MASTER_SEARCH_BRANCHING"] = "fixed"
    os.environ["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = "3"
    os.environ["EXACT_MASTER_SYMMETRY_LEVEL"] = "3"
    os.environ["EXACT_B1_BINDING_ALT_CAP"] = str(args.binding_alt_cap)

    authority = _authority()
    config = {
        "ghost_rect": [args.ghost_w, args.ghost_h],
        "master_seconds": args.master_seconds,
        "binding_seconds": args.binding_seconds,
        "routing_seconds": args.routing_seconds,
        "max_iterations": args.max_iterations,
        "binding_alt_cap": args.binding_alt_cap,
        "post_attach_seconds": args.post_attach_seconds,
        "workers": args.workers,
        "seed": args.seed,
        "master_branching": "fixed",
        "probing_level": 3,
        "symmetry_level": 3,
        "enabled_families": list(ENABLED_FAMILIES),
    }
    result: dict[str, object] = {
        "schema_version": 1,
        "arm": args.arm,
        "run_tag": args.run_tag,
        "argv": list(sys.argv),
        "authority": authority,
        "config": config,
        "config_digest": _digest(config),
        "exact_environment": {key: value for key, value in sorted(os.environ.items()) if key.startswith("EXACT_")},
        "terminal_status": "IN_PROGRESS",
    }
    _progress(attempt, 1, "authority", result)

    sys.path.insert(0, str(PROJECT_ROOT))
    from src.cuts.ledger import CutLedgerWriter, read_segment
    from src.models.cut_manager import CutManager
    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import ExactSearchSession, LBBDController

    ledger = None
    failure: BaseException | None = None
    try:
        started = time.perf_counter()
        session = ExactSearchSession.create(PROJECT_ROOT, solve_mode="certified_exact")
        result["session_build_seconds"] = round(time.perf_counter() - started, 3)

        started = time.perf_counter()
        master = MasterPlacementModel.from_exact_core(
            session.core,
            ghost_rect=(args.ghost_w, args.ghost_h),
        )
        result["master_build_seconds"] = round(time.perf_counter() - started, 3)
        _progress(attempt, 2, "master-built", result)

        ledger = CutLedgerWriter(
            attempt / "ledger",
            scope_id=args.run_tag,
            genesis_context={
                "arm": args.arm,
                "authority_digest": _digest(authority),
                "config_digest": _digest(config),
                "attach_present_during_construction": False,
                "ghost_rect": [args.ghost_w, args.ghost_h],
                "recovery_reason": "fresh_start",
            },
        )
        controller = LBBDController(
            master=master,
            cut_manager=CutManager(
                checkpoint_dir=attempt / "checkpoint",
                solve_mode="certified_exact",
            ),
            project_root=PROJECT_ROOT,
            solve_mode="certified_exact",
            master_seconds=args.master_seconds,
            binding_seconds=args.binding_seconds,
            routing_seconds=args.routing_seconds,
            max_iterations=args.max_iterations,
            artifact_hashes=session.artifact_hashes,
            session=session,
            enabled_cut_families=ENABLED_FAMILIES,
            cut_ledger=ledger,
        )
        if os.environ.get("EXACT_CUT_FRAMEWORK_ATTACH") is not None:
            raise RuntimeError("attach env leaked into construction")

        started = time.perf_counter()
        lbbd_status, returned_solution = controller.run_with_status()
        result["lbbd"] = {
            "status": str(lbbd_status),
            "wall_seconds": round(time.perf_counter() - started, 3),
            "has_returned_solution": returned_solution is not None,
            "proof_summary": _jsonable(controller.last_proof_summary or {}),
            "organic_attach_last": _jsonable((master.build_stats or {}).get("cut_framework_attach_last")),
        }
        if returned_solution:
            frozen_solution = dict(returned_solution)
        else:
            frozen_solution = master.extract_solution()
        if not frozen_solution or "ghost_pick" not in frozen_solution:
            raise RuntimeError("LBBD run did not retain a non-empty incumbent with ghost_pick")
        if master._solver is None:
            raise RuntimeError("frozen incumbent lacks a retained CpSolver response")
        solver_values = tuple(int(value) for value in master._solver.ResponseProto().solution)
        if not solver_values:
            raise RuntimeError("frozen solver response has no assignment")
        # OR-Tools 9.15 exposes the pybind ``cp_model_helper.CpModelProto``
        # rather than a Python protobuf object.  Its deterministic text form is
        # the repository's established byte-comparison surface.
        proto_bytes = str(master.model.Proto()).encode("utf-8")
        frozen_solution_json = _jsonable(frozen_solution)
        prestate = {
            "incumbent": frozen_solution_json,
            "incumbent_sha256": _digest(frozen_solution_json),
            "model_proto_sha256": hashlib.sha256(proto_bytes).hexdigest(),
            "model_variable_count": len(master.model.Proto().variables),
            "model_constraint_count": len(master.model.Proto().constraints),
            "ghost_pick": _jsonable(frozen_solution["ghost_pick"]),
        }
        result["prestate"] = prestate
        _progress(attempt, 3, "prestate", prestate)

        import src.cuts.lifecycle as lifecycle
        import src.cuts.typed_platform as typed_platform

        real_validate = typed_platform.validate_and_compile_cut
        real_step_8 = lifecycle.step_8_apply_to_master
        compiled_records: list[dict[str, object]] = []
        samples: list[dict[str, object]] = []

        def capture_validate(envelope: Any, snapshot: Any, registry: Any) -> Any:
            compiled = real_validate(envelope, snapshot, registry)
            if type(compiled).__name__ == "CompiledCut":
                compiled_records.append(_compiled_record(compiled))
            return compiled

        def capture_step_8(
            compiled_cut: Any,
            live_master: Any,
            *,
            scope_binding: Any,
        ) -> Any:
            samples.append(
                _arithmetic_sample(
                    compiled_cut,
                    live_master,
                    scope_binding,
                    frozen_solution,
                    solver_values,
                )
            )
            return real_step_8(
                compiled_cut,
                live_master,
                scope_binding=scope_binding,
            )

        typed_platform.validate_and_compile_cut = capture_validate
        lifecycle.step_8_apply_to_master = capture_step_8
        attached = None
        try:
            if args.arm == "treatment":
                os.environ["EXACT_CUT_FRAMEWORK_ATTACH"] = "1"
            started = time.perf_counter()
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible",
                iteration=1001,
                solution=frozen_solution,
            )
            injection_wall = round(time.perf_counter() - started, 3)
        finally:
            os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
            typed_platform.validate_and_compile_cut = real_validate
            lifecycle.step_8_apply_to_master = real_step_8

        result["injection"] = {
            "attached_return": attached,
            "wall_seconds": injection_wall,
            "compiled_observed": len(compiled_records),
            "compiled_records": compiled_records,
            "arithmetic_sample_count": len(samples),
            "attach_telemetry": _jsonable((master.build_stats or {}).get("cut_framework_attach_last")),
        }
        sample_corpus = {
            "schema_version": 1,
            "authority": {"head": EXPECTED_HEAD},
            "arm": args.arm,
            "prestate_sha256": prestate["incumbent_sha256"],
            "samples": samples,
        }
        sample_path = attempt / "arithmetic_samples.json"
        _write_json_exclusive(sample_path, sample_corpus)
        sample_identity = _file_identity(sample_path)
        result["arithmetic_sample_corpus"] = {
            **sample_identity,
            "prestate_sha256": prestate["incumbent_sha256"],
        }
        _progress(attempt, 4, "injected", result["injection"])

        post_started = time.perf_counter()
        post_status = master.solve(time_limit_seconds=args.post_attach_seconds)
        post_solution: Mapping[str, Any] = {}
        if master._solver is not None:
            post_solution = master.extract_solution()
        post_solution_json = _jsonable(post_solution)
        result["post_attach_solve"] = {
            "status_code": int(post_status),
            "status": str((master.build_stats or {}).get("last_solve", {}).get("status", "UNKNOWN")),
            "wall_seconds": round(time.perf_counter() - post_started, 3),
            "has_solution": bool(post_solution),
            "solution_sha256": _digest(post_solution_json) if post_solution else None,
            "repeats_frozen_incumbent": bool(
                post_solution and _digest(post_solution_json) == prestate["incumbent_sha256"]
            ),
            "telemetry": _jsonable((master.build_stats or {}).get("last_solve", {})),
        }
    except BaseException as exc:  # noqa: BLE001 - fail-closed result capture
        failure = exc
        result["failure"] = f"{type(exc).__name__}: {exc}"
    finally:
        if ledger is not None:
            try:
                ledger.seal()
            except BaseException as exc:  # noqa: BLE001
                result["ledger_seal_error"] = f"{type(exc).__name__}: {exc}"
                failure = failure or exc

    if ledger is not None:
        segment = read_segment(ledger.path)
        counts = _event_counts(segment.events)
        result["ledger"] = {
            "path": str(ledger.path),
            "status": segment.status,
            "event_count": len(segment.events),
            "event_counts": counts,
            "generated": counts.get("GENERATED", 0),
            "applied": counts.get("APPLIED", 0),
            "tail_hash": segment.tail_hash,
        }
        if segment.status != "complete":
            failure = failure or RuntimeError(f"audit ledger is not complete: {segment.status}")

    if failure is None:
        result["terminal_status"] = "ARM_COMPLETE"
    else:
        result["terminal_status"] = "CREDIBILITY_INCOMPLETE"
    _write_json_exclusive(attempt / "result.json", result)
    print(
        json.dumps(
            {
                "arm": args.arm,
                "attempt": str(attempt),
                "terminal_status": result["terminal_status"],
                "ledger": result.get("ledger"),
                "injection": result.get("injection"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if failure is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
