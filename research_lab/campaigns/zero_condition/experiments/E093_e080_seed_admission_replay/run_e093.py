#!/usr/bin/env python3
"""E093: solver-diverse replay of E092's sole unresolved Pareto admission state."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback
from types import ModuleType
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HISTORY = Path("/home/zhuran24/zmd-pj")
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E093_e080_seed_admission_replay/run-001"
)

SOURCE_PRODUCER = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E092_pareto_three_pole_admission_atlas/run-001/DERIVED_PRODUCER.py"
)
SOURCE_UNKNOWN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E092_pareto_three_pole_admission_atlas/run-001/"
    "state-02-partition_5a72220e0268a3c1/RESULT.json"
)
E092_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E092_pareto_three_pole_admission_atlas/run-001/RESULT.json"
)
E092_CHECK = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E092_pareto_three_pole_admission_atlas/run-001/ARTIFACT_CHECK.json"
)
E092_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E092_pareto_three_pole_admission_atlas/RESULT.txt"
)
E081_FRONTIER = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E081_axis_seam_recolor_frontier/run-001/AXIS_SEAM_FRONTIER.json"
)
E069_PARENT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001/PARENT_SOLUTION.json"
)
E079_MACRO = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E079_k47_boundary_macro/run-001/BOUNDARY_MACRO_V1.json"
)
CANDIDATES = HISTORY / "data/preprocessed/candidate_placements.json"
STRICT = (
    ROOT
    / "docs/research/cleanroom_rederivation_20260718/strict/external/"
    "problem_instance.json"
)

EXPECTED_HASHES = {
    SOURCE_PRODUCER: "306ccf5da973b97710ee6cf13c3190cc32c4c0ce3236fd581a75a756020b2e1c",
    SOURCE_UNKNOWN: "b87d4f7a5d00349b4daebf37bb2b0504223ef7d98011723cca6e3e13fa538c3f",
    E092_RESULT: "e60aaf29ff4b2db9e965c1d7c1932797099b3bd9a91759067821f49b8063e909",
    E092_CHECK: "eb26f090c01d803203c5f78806ec562e85319de60f9b59ced3496e60ab158a99",
    E092_DURABLE: "956427c8c3f1929c74b54c78d08ae0d33b32f4f336f165dbd92b7f78608d2bae",
    E081_FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E079_MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}

TARGET_PARTITION_ID = "partition_5a72220e0268a3c1"
TARGET_RANK = 2
CORRIDOR_AXIS = "y"
CORRIDOR_COORDINATE = 21
MODULE_LOW = "B"
MODULE_HIGH = "A"
STABLE_MODULE = "A"
MAX_RELOCATED_POLES = 3

ARM_CONTROLS = (
    {
        "arm_id": "pseudo_cost_single_worker",
        "seconds": 110.0,
        "workers": 1,
        "search_branching": "PSEUDO_COST_SEARCH",
        "symmetry_level": 0,
        "probing_level": 0,
        "randomize_search": False,
        "seed": 93001,
    },
    {
        "arm_id": "quick_restart_portfolio",
        "seconds": 110.0,
        "workers": 8,
        "search_branching": "PORTFOLIO_WITH_QUICK_RESTART_SEARCH",
        "symmetry_level": 3,
        "probing_level": 3,
        "randomize_search": True,
        "seed": 93002,
    },
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_safe(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            default=str,
        )
    )


def dump_exclusive(path: Path, payload: Any) -> None:
    raw = (
        json.dumps(
            json_safe(payload),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"E093 patch {label} matched {count} times")
    return source.replace(old, new, 1)


def _read_scalar(path: Path) -> int | str | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if raw.isdigit():
        return int(raw)
    return raw


def _read_events(path: Path) -> dict[str, int] | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    output: dict[str, int] = {}
    for line in lines:
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            output[str(fields[0])] = int(fields[1])
        except ValueError:
            continue
    return output


def cgroup_snapshot() -> dict[str, Any]:
    relative: str | None = None
    try:
        for line in Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines():
            fields = line.split(":", 2)
            if len(fields) == 3 and fields[0] == "0":
                relative = fields[2]
                break
    except OSError:
        pass
    if relative is None:
        return {"available": False}
    directory = Path("/sys/fs/cgroup") / relative.lstrip("/")
    return {
        "available": directory.is_dir(),
        "relative_path": relative,
        "memory_current_bytes": _read_scalar(directory / "memory.current"),
        "memory_peak_bytes": _read_scalar(directory / "memory.peak"),
        "memory_max": _read_scalar(directory / "memory.max"),
        "memory_swap_current_bytes": _read_scalar(directory / "memory.swap.current"),
        "memory_swap_peak_bytes": _read_scalar(directory / "memory.swap.peak"),
        "memory_events": _read_events(directory / "memory.events"),
    }


def process_memory_snapshot() -> dict[str, Any]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "ru_maxrss_kib": int(usage.ru_maxrss),
        "minor_page_faults": int(usage.ru_minflt),
        "major_page_faults": int(usage.ru_majflt),
        "voluntary_context_switches": int(usage.ru_nvcsw),
        "involuntary_context_switches": int(usage.ru_nivcsw),
    }


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E093 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E093 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E093 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    e092 = load_json(E092_RESULT)
    if e092.get("verdict") != (
        "Y41_ONLY_OBSERVED_SURVIVOR_WITH_CENSORED_ADMISSION_STATES"
    ):
        raise RuntimeError("E093 trigger E092 verdict drift")
    if e092.get("decision") != (
        "RESOLVE_UNKNOWN_ADMISSION_STATES_BEFORE_SELECTING_CARRIER"
    ):
        raise RuntimeError("E093 trigger E092 decision drift")
    if e092.get("unknown_partition_ids") != [TARGET_PARTITION_ID]:
        raise RuntimeError("E093 unresolved partition identity drift")

    unknown = load_json(SOURCE_UNKNOWN)
    expected_context = {
        "partition_id": TARGET_PARTITION_ID,
        "corridor_axis": CORRIDOR_AXIS,
        "corridor_coordinate": CORRIDOR_COORDINATE,
        "module_low": MODULE_LOW,
        "module_high": MODULE_HIGH,
        "stable_module": STABLE_MODULE,
    }
    if unknown.get("status") != "UNKNOWN":
        raise RuntimeError("E093 source state is not UNKNOWN")
    for key, value in expected_context.items():
        if unknown.get(key) != value:
            raise RuntimeError(f"E093 source state identity drift: {key}")
    if int(unknown.get("max_relocated_poles", -1)) != MAX_RELOCATED_POLES:
        raise RuntimeError("E093 source pole cap drift")
    if int(unknown.get("minimum_retained_current_poles", -1)) != 50:
        raise RuntimeError("E093 source retained-pole floor drift")
    if unknown.get("selected_manufacturing") or unknown.get("selected_poles"):
        raise RuntimeError("E093 source UNKNOWN unexpectedly carries a witness")

    frontier = load_json(E081_FRONTIER)
    rows = [
        row
        for row in frontier["detailed_candidates"]
        if row["partition"]["partition_id"] == TARGET_PARTITION_ID
    ]
    if len(rows) != 1:
        raise RuntimeError("E093 target partition multiplicity drift")
    evaluation = rows[0]["best_reference_preserving"]
    corridor = evaluation["corridor"]
    expected_corridor = {
        "axis": CORRIDOR_AXIS,
        "start": CORRIDOR_COORDINATE,
        "end": CORRIDOR_COORDINATE,
        "width": 1,
        "module_low": MODULE_LOW,
        "module_high": MODULE_HIGH,
        "interior_cell_count": 68,
        "interior_cells_digest": corridor["interior_cells_digest"],
    }
    if corridor != expected_corridor:
        raise RuntimeError(f"E093 corridor drift: {corridor}")
    stable_modules = {
        str(row["target_module"])
        for row in evaluation["reference_rewrite_rows"]
    }
    if stable_modules != {STABLE_MODULE}:
        raise RuntimeError(f"E093 stable-module drift: {stable_modules}")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
        "target_partition_id": TARGET_PARTITION_ID,
        "target_rank": TARGET_RANK,
        "target_corridor": json_safe(corridor),
        "source_status": "UNKNOWN",
    }


def derive_source() -> tuple[str, list[dict[str, Any]]]:
    source = SOURCE_PRODUCER.read_text(encoding="utf-8")
    patches: list[dict[str, Any]] = []

    def patch(label: str, old: str, new: str) -> None:
        nonlocal source
        source = replace_once(source, old, new, label)
        patches.append(
            {
                "label": label,
                "old_sha256": sha256_bytes(old.encode("utf-8")),
                "new_sha256": sha256_bytes(new.encode("utf-8")),
            }
        )

    patch(
        "search_controls",
        '''def solve(model: cp_model.CpModel, *, seed: int, seconds: float) -> tuple[cp_model.CpSolver, int, float]:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = seed
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.randomize_search = True
    solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
    solver.parameters.repair_hint = True
    solver.parameters.hint_conflict_limit = 2000
    solver.parameters.stop_after_first_solution = True
    started = time.monotonic()
    status = solver.Solve(model)
    return solver, status, time.monotonic() - started''',
        '''def solve(model: cp_model.CpModel, *, seed: int, seconds: float) -> tuple[cp_model.CpSolver, int, float]:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = int(os.environ["E093_WORKERS"])
    solver.parameters.random_seed = seed
    solver.parameters.symmetry_level = int(os.environ["E093_SYMMETRY_LEVEL"])
    solver.parameters.cp_model_probing_level = int(os.environ["E093_PROBING_LEVEL"])
    solver.parameters.randomize_search = os.environ["E093_RANDOMIZE_SEARCH"] == "1"
    branching_name = os.environ["E093_SEARCH_BRANCHING"]
    try:
        solver.parameters.search_branching = getattr(cp_model, branching_name)
    except AttributeError as exc:
        raise RuntimeError(f"unsupported E093 search branching: {branching_name}") from exc
    solver.parameters.repair_hint = True
    solver.parameters.hint_conflict_limit = 2000
    solver.parameters.stop_after_first_solution = True
    started = time.monotonic()
    status = solver.Solve(model)
    return solver, status, time.monotonic() - started''',
    )
    patch(
        "explicit_seed",
        '    seed = 92000 + int(os.environ.get("E092_STATE_RANK", "0"))',
        '    seed = int(os.environ["E093_SEED"])',
    )
    source = source.replace("E092", "E093").replace("e092", "e093")
    patches.append(
        {
            "label": "experiment_namespace",
            "old_sha256": EXPECTED_HASHES[SOURCE_PRODUCER],
            "new_sha256": sha256_bytes(source.encode("utf-8")),
        }
    )
    return source, patches


def import_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import E093 derived producer: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _event_delta(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
    key: str,
) -> int | None:
    if before is None or after is None:
        return None
    if key not in before or key not in after:
        return None
    return int(after[key]) - int(before[key])


def run_arm(
    *,
    derived_path: Path,
    run_dir: Path,
    control: Mapping[str, Any],
    arm_index: int,
) -> dict[str, Any]:
    arm_id = str(control["arm_id"])
    arm_dir = run_dir / f"arm-{arm_index + 1:02d}-{arm_id}"
    arm_dir.mkdir(parents=False, exist_ok=False)
    output_path = arm_dir / "RESULT.json"

    environment = {
        "E093_STATE_OUTPUT": str(output_path),
        "E093_STATE_SECONDS": str(float(control["seconds"])),
        "E093_STATE_RANK": str(TARGET_RANK),
        "E093_PARTITION_ID": TARGET_PARTITION_ID,
        "E093_CORRIDOR_AXIS": CORRIDOR_AXIS,
        "E093_CORRIDOR_COORDINATE": str(CORRIDOR_COORDINATE),
        "E093_MODULE_LOW": MODULE_LOW,
        "E093_MODULE_HIGH": MODULE_HIGH,
        "E093_STABLE_MODULE": STABLE_MODULE,
        "E093_HINT_GEOMETRY": "",
        "E093_WORKERS": str(int(control["workers"])),
        "E093_SEARCH_BRANCHING": str(control["search_branching"]),
        "E093_SYMMETRY_LEVEL": str(int(control["symmetry_level"])),
        "E093_PROBING_LEVEL": str(int(control["probing_level"])),
        "E093_RANDOMIZE_SEARCH": "1" if control["randomize_search"] else "0",
        "E093_SEED": str(int(control["seed"])),
    }
    previous = {key: os.environ.get(key) for key in environment}
    os.environ.update(environment)
    process_before = process_memory_snapshot()
    cgroup_before = cgroup_snapshot()
    started = time.monotonic()
    try:
        module = import_module(
            derived_path,
            f"zmd_e093_arm_{arm_index + 1:02d}",
        )
        exit_code = int(module.main())
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    wrapper_elapsed = time.monotonic() - started
    process_after = process_memory_snapshot()
    cgroup_after = cgroup_snapshot()

    if exit_code != 0 or not output_path.is_file():
        raise RuntimeError(f"E093 arm did not publish: {arm_id}")
    result = load_json(output_path)
    allowed_statuses = {"BODY_POWER_FEASIBLE", "MASTER_INFEASIBLE", "UNKNOWN"}
    status = str(result.get("status", "MISSING"))
    if status not in allowed_statuses:
        raise RuntimeError(f"E093 unexpected arm status {arm_id}: {status}")
    expected_context = {
        "partition_id": TARGET_PARTITION_ID,
        "corridor_axis": CORRIDOR_AXIS,
        "corridor_coordinate": CORRIDOR_COORDINATE,
        "module_low": MODULE_LOW,
        "module_high": MODULE_HIGH,
        "stable_module": STABLE_MODULE,
    }
    for key, value in expected_context.items():
        if result.get(key) != value:
            raise RuntimeError(f"E093 arm identity drift {arm_id}:{key}")
    if int(result.get("max_relocated_poles", -1)) != MAX_RELOCATED_POLES:
        raise RuntimeError(f"E093 arm pole cap drift: {arm_id}")
    if int(result.get("minimum_retained_current_poles", -1)) != 50:
        raise RuntimeError(f"E093 arm pole floor drift: {arm_id}")
    selected_body_count = len(result.get("selected_manufacturing", []))
    selected_pole_count = len(result.get("selected_poles", []))
    if status == "BODY_POWER_FEASIBLE":
        if selected_body_count != 219 or selected_pole_count != 53:
            raise RuntimeError(f"E093 positive witness cardinality drift: {arm_id}")
        if int(result.get("relocated_pole_count", 99)) > MAX_RELOCATED_POLES:
            raise RuntimeError(f"E093 positive exceeds pole cap: {arm_id}")
    elif selected_body_count or selected_pole_count:
        raise RuntimeError(f"E093 nonpositive arm carries a witness: {arm_id}")

    before_events = cgroup_before.get("memory_events")
    after_events = cgroup_after.get("memory_events")
    return {
        "arm_id": arm_id,
        "controls": json_safe(dict(control)),
        "status": status,
        "solver_status": str(result.get("solver_status", "MISSING")),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "wrapper_elapsed_seconds": wrapper_elapsed,
        "branches": result.get("branches"),
        "conflicts": result.get("conflicts"),
        "body_candidate_count": result.get("body_candidate_count"),
        "pole_candidate_count": result.get("pole_candidate_count"),
        "model_variable_count": result.get("model_variable_count"),
        "model_constraint_count": result.get("model_constraint_count"),
        "retained_manufacturing_count": result.get("retained_manufacturing_count"),
        "moved_manufacturing_count": result.get("moved_manufacturing_count"),
        "retained_current_pole_count": result.get("retained_current_pole_count"),
        "relocated_pole_count": result.get("relocated_pole_count"),
        "selected_boundary_state_id": result.get("selected_boundary_state_id"),
        "selected_manufacturing_count": selected_body_count,
        "selected_pole_count": selected_pole_count,
        "result_path": display(output_path),
        "result_sha256": sha256_file(output_path),
        "telemetry": {
            "process_before": process_before,
            "process_after": process_after,
            "cgroup_before": cgroup_before,
            "cgroup_after": cgroup_after,
            "oom_delta": _event_delta(before_events, after_events, "oom"),
            "oom_kill_delta": _event_delta(before_events, after_events, "oom_kill"),
        },
    }


def classify(arms: list[Mapping[str, Any]]) -> tuple[str, str]:
    for arm in arms:
        if arm["status"] == "BODY_POWER_FEASIBLE":
            return (
                "E080_SEED_THREE_POLE_BODY_POWER_FEASIBLE",
                "RUN_COMPLETE_THREE_POLE_FRONT_CONSUMER_ON_E080_SEED",
            )
        if arm["status"] == "MASTER_INFEASIBLE":
            return (
                "E080_SEED_THREE_POLE_BODY_POWER_INFEASIBLE",
                "Y41_IS_SOLE_ADMITTED_SKELETON_CHOOSE_POLE_BUDGET_OR_FRONT_DECOMPOSITION",
            )
    return (
        "E080_SEED_ADMISSION_REPLAY_CENSORED",
        "DECOMPOSE_BODY_POWER_ADMISSION_INSTRUMENT_BEFORE_CARRIER_SELECTION",
    )


def run(*, run_dir: Path) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E093 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)
    derived_path = run_dir / "DERIVED_PRODUCER.py"
    derivation_path = run_dir / "DERIVATION.json"

    source, patches = derive_source()
    with derived_path.open("xb") as handle:
        handle.write(source.encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    dump_exclusive(
        derivation_path,
        {
            "schema": "zmd_e093_solver_diverse_derivation_v1",
            "source_path": display(SOURCE_PRODUCER),
            "source_sha256": EXPECTED_HASHES[SOURCE_PRODUCER],
            "derived_path": display(derived_path),
            "derived_sha256": sha256_file(derived_path),
            "patches": patches,
            "feasible_set_changes": [],
            "search_only_changes": {
                "two_conditional_arms": True,
                "arm_controls": json_safe(ARM_CONTROLS),
                "same_current_geometry_hint_surface": True,
                "same_pure_feasibility": True,
                "same_stop_after_first_solution": True,
            },
            "frozen_context": {
                "partition_id": TARGET_PARTITION_ID,
                "corridor_axis": CORRIDOR_AXIS,
                "corridor_coordinate": CORRIDOR_COORDINATE,
                "module_low": MODULE_LOW,
                "module_high": MODULE_HIGH,
                "stable_module": STABLE_MODULE,
                "exact_manufacturing_count": 219,
                "exact_pole_count": 53,
                "maximum_relocated_poles": MAX_RELOCATED_POLES,
                "complete_boundary_disjunction": True,
                "power_and_nonoverlap": True,
            },
        },
    )

    overall_started = time.monotonic()
    overall_before = process_memory_snapshot()
    arms: list[dict[str, Any]] = []
    for arm_index, control in enumerate(ARM_CONTROLS):
        if arms and arms[-1]["status"] != "UNKNOWN":
            break
        arm = run_arm(
            derived_path=derived_path,
            run_dir=run_dir,
            control=control,
            arm_index=arm_index,
        )
        arms.append(arm)
        print(
            json.dumps(
                {
                    "arm_id": arm["arm_id"],
                    "status": arm["status"],
                    "elapsed_seconds": arm["elapsed_seconds"],
                    "branches": arm["branches"],
                    "conflicts": arm["conflicts"],
                    "result_sha256": arm["result_sha256"],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
    overall_after = process_memory_snapshot()
    verdict, decision = classify(arms)
    return {
        "schema": "zmd_e093_e080_seed_admission_replay_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "context": {
            "partition_id": TARGET_PARTITION_ID,
            "pareto_rank_zero_based": TARGET_RANK,
            "corridor_axis": CORRIDOR_AXIS,
            "corridor_coordinate": CORRIDOR_COORDINATE,
            "module_low": MODULE_LOW,
            "module_high": MODULE_HIGH,
            "stable_module": STABLE_MODULE,
            "maximum_relocated_poles": MAX_RELOCATED_POLES,
            "minimum_retained_current_poles": 50,
        },
        "derivation": {
            "path": display(derivation_path),
            "sha256": sha256_file(derivation_path),
            "derived_source_path": display(derived_path),
            "derived_source_sha256": sha256_file(derived_path),
            "patch_count": len(patches),
        },
        "arms": arms,
        "arm_count": len(arms),
        "terminal_arm_id": (
            next(
                (
                    str(arm["arm_id"])
                    for arm in arms
                    if arm["status"] in {"BODY_POWER_FEASIBLE", "MASTER_INFEASIBLE"}
                ),
                None,
            )
        ),
        "telemetry": {
            "wrapper_elapsed_seconds": time.monotonic() - overall_started,
            "process_before": overall_before,
            "process_after": overall_after,
        },
        "truth_boundary": (
            "Two search-diverse replays of one frozen three-pole body/pole/power "
            "feasible set. A positive is a skeleton only; a negative is contextual; "
            "UNKNOWN remains censored. No native-front or downstream claim."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    result_path = run_dir / "RESULT.json"
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(run_dir=run_dir)
        dump_exclusive(result_path, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "arm_statuses": [
                        {"arm_id": arm["arm_id"], "status": arm["status"]}
                        for arm in result["arms"]
                    ],
                    "elapsed_seconds": result["telemetry"]["wrapper_elapsed_seconds"],
                    "terminal_arm_id": result["terminal_arm_id"],
                    "result_path": display(result_path),
                    "result_sha256": sha256_file(result_path),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except FileExistsError as exc:
        print(
            json.dumps(
                {"status": "NO_OVERWRITE_REJECTION", "detail": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e093_e080_seed_admission_replay_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not failure_path.exists():
            dump_exclusive(failure_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
