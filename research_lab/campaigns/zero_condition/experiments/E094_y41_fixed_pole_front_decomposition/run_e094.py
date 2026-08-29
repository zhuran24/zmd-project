#!/usr/bin/env python3
"""E094: nested fixed-pole decomposition of E090's y=41 front model."""

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
    "E094_y41_fixed_pole_front_decomposition/run-001"
)

SOURCE_PRODUCER = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E090_three_pole_front_discriminator/run-001/DERIVED_PRODUCER.py"
)
ANCHOR_GEOMETRY = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E092_pareto_three_pole_admission_atlas/run-001/"
    "state-00-partition_90abd29523f2a0dc/RESULT.json"
)
E093_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E093_e080_seed_admission_replay/run-001/RESULT.json"
)
E093_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E093_e080_seed_admission_replay/RESULT.txt"
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
MANDATORY = HISTORY / "data/preprocessed/mandatory_exact_instances.json"
STRICT = (
    ROOT
    / "docs/research/cleanroom_rederivation_20260718/strict/external/"
    "problem_instance.json"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"

EXPECTED_HASHES = {
    SOURCE_PRODUCER: "93471f93743d15dc2835c7e1c5a0637a219942e2aab6c4e77c4dcf4828cde0fb",
    ANCHOR_GEOMETRY: "7bc3cc6ccd48f919e08561c7b32262da56f9f3853d5fbca313413add4bd87a78",
    E093_RESULT: "0fe35a818735c79ebeffef1329e748b8c796b656a57d9f160a4cc72c200025ea",
    E093_DURABLE: "0bb21601c2acef31e4572348d523568996a97a8ea93057a654855ec8eae03184",
    E081_FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E079_MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    MANDATORY: "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
}

ARM_CONTROLS = (
    {
        "arm_id": "fixed_poles_fixed_boundary",
        "fix_boundary": True,
        "seconds": 120.0,
        "seed": 94001,
    },
    {
        "arm_id": "fixed_poles_all_boundaries",
        "fix_boundary": False,
        "seconds": 120.0,
        "seed": 94002,
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
        raise RuntimeError(f"E094 patch {label} matched {count} times")
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
        raise RuntimeError("E094 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E094 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E094 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    e093 = load_json(E093_RESULT)
    if e093.get("verdict") != "E080_SEED_THREE_POLE_BODY_POWER_INFEASIBLE":
        raise RuntimeError("E094 trigger E093 verdict drift")
    if e093.get("decision") != (
        "Y41_IS_SOLE_ADMITTED_SKELETON_CHOOSE_POLE_BUDGET_OR_FRONT_DECOMPOSITION"
    ):
        raise RuntimeError("E094 trigger E093 decision drift")

    anchor = load_json(ANCHOR_GEOMETRY)
    expected_anchor = {
        "status": "BODY_POWER_FEASIBLE",
        "partition_id": "partition_90abd29523f2a0dc",
        "corridor_axis": "y",
        "corridor_coordinate": 41,
        "module_low": "A",
        "module_high": "B",
        "stable_module": "B",
        "relocated_pole_count": 3,
        "selected_boundary_state_index": 8,
        "selected_boundary_state_id": "boundary_macro_09",
    }
    for key, value in expected_anchor.items():
        if anchor.get(key) != value:
            raise RuntimeError(f"E094 anchor drift: {key}")
    if len(anchor.get("selected_manufacturing", [])) != 219:
        raise RuntimeError("E094 anchor lacks 219 bodies")
    if len(anchor.get("selected_poles", [])) != 53:
        raise RuntimeError("E094 anchor lacks 53 poles")
    pole_pose_indices = sorted(int(row["pose_index"]) for row in anchor["selected_poles"])
    if len(set(pole_pose_indices)) != 53:
        raise RuntimeError("E094 anchor pole identity collision")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
        "anchor_boundary_state_index": 8,
        "anchor_boundary_state_id": "boundary_macro_09",
        "anchor_pole_pose_indices": pole_pose_indices,
        "anchor_pole_set_digest": sha256_bytes(
            json.dumps(pole_pose_indices, separators=(",", ":")).encode("utf-8")
        ),
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
        "runtime_controls",
        '''OUTPUT = Path(os.environ["E090_PRODUCER_OUTPUT"])
HINT_GEOMETRY = Path(os.environ["E090_HINT_GEOMETRY"])
MAX_RELOCATED_POLES = int(os.environ.get("E090_MAX_RELOCATED_POLES", "3"))
SOLVE_SECONDS = float(os.environ.get("E090_SOLVE_SECONDS", "240"))''',
        '''OUTPUT = Path(os.environ["E094_PRODUCER_OUTPUT"])
HINT_GEOMETRY = Path(os.environ["E094_HINT_GEOMETRY"])
MAX_RELOCATED_POLES = 3
SOLVE_SECONDS = float(os.environ.get("E094_SOLVE_SECONDS", "120"))
FIX_BOUNDARY = os.environ["E094_FIX_BOUNDARY"] == "1"
SOLVE_SEED = int(os.environ["E094_SOLVE_SEED"])''',
    )
    patch(
        "quick_restart_search",
        "    solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH",
        "    solver.parameters.search_branching = cp_model.PORTFOLIO_WITH_QUICK_RESTART_SEARCH",
    )
    patch(
        "explicit_seed",
        "    solver, status, elapsed = solve(model, seed=90001, seconds=SOLVE_SECONDS)",
        "    solver, status, elapsed = solve(model, seed=SOLVE_SEED, seconds=SOLVE_SECONDS)",
    )
    patch(
        "fixed_anchor_constraints",
        '''    for index, variable in enumerate(boundary_vars):
        model.AddHint(variable, int(index == hint_boundary))

    validation_error = model.Validate()''',
        '''    for index, variable in enumerate(boundary_vars):
        model.AddHint(variable, int(index == hint_boundary))

    fixed_pole_pose_indices = set(hint_poles)
    if len(fixed_pole_pose_indices) != EXPECTED_POLE_COUNT:
        raise RuntimeError("E094 fixed pole set cardinality drift")
    for index, row in enumerate(pole_rows):
        model.Add(
            pole_vars[index]
            == int(int(row["pose_index"]) in fixed_pole_pose_indices)
        )
    if FIX_BOUNDARY:
        for index, variable in enumerate(boundary_vars):
            model.Add(variable == int(index == hint_boundary))

    validation_error = model.Validate()''',
    )
    patch(
        "result_slice_fields",
        '''        "minimum_retained_current_poles": EXPECTED_POLE_COUNT - MAX_RELOCATED_POLES,
        "body_candidate_count": len(body_rows),''',
        '''        "minimum_retained_current_poles": EXPECTED_POLE_COUNT - MAX_RELOCATED_POLES,
        "fixed_pole_set": True,
        "fixed_pole_pose_indices": sorted(fixed_pole_pose_indices),
        "fixed_boundary": FIX_BOUNDARY,
        "anchor_boundary_state_index": hint_boundary,
        "anchor_boundary_state_id": str(macro["states"][hint_boundary]["state_id"]),
        "body_candidate_count": len(body_rows),''',
    )
    source = source.replace("E090", "E094").replace("e090", "e094")
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
        raise RuntimeError(f"cannot import E094 derived producer: {path}")
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
        "E094_PRODUCER_OUTPUT": str(output_path),
        "E094_HINT_GEOMETRY": str(ANCHOR_GEOMETRY),
        "E094_SOLVE_SECONDS": str(float(control["seconds"])),
        "E094_FIX_BOUNDARY": "1" if control["fix_boundary"] else "0",
        "E094_SOLVE_SEED": str(int(control["seed"])),
    }
    prior = {key: os.environ.get(key) for key in environment}
    os.environ.update(environment)
    process_before = process_memory_snapshot()
    cgroup_before = cgroup_snapshot()
    started = time.monotonic()
    try:
        module = import_module(
            derived_path,
            f"zmd_e094_arm_{arm_index + 1:02d}",
        )
        exit_code = int(module.main())
    finally:
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    wrapper_elapsed = time.monotonic() - started
    process_after = process_memory_snapshot()
    cgroup_after = cgroup_snapshot()
    if exit_code != 0 or not output_path.is_file():
        raise RuntimeError(f"E094 arm did not publish: {arm_id}")
    result = load_json(output_path)
    status = str(result.get("status", "MISSING"))
    if status not in {"FRONT_OPERATION_FEASIBLE", "MASTER_INFEASIBLE", "UNKNOWN"}:
        raise RuntimeError(f"E094 unexpected arm status {arm_id}: {status}")
    if result.get("fixed_pole_set") is not True:
        raise RuntimeError(f"E094 arm did not fix poles: {arm_id}")
    if bool(result.get("fixed_boundary")) != bool(control["fix_boundary"]):
        raise RuntimeError(f"E094 boundary control drift: {arm_id}")
    if int(result.get("anchor_boundary_state_index", -1)) != 8:
        raise RuntimeError(f"E094 anchor boundary index drift: {arm_id}")
    if result.get("anchor_boundary_state_id") != "boundary_macro_09":
        raise RuntimeError(f"E094 anchor boundary ID drift: {arm_id}")
    if len(result.get("fixed_pole_pose_indices", [])) != 53:
        raise RuntimeError(f"E094 fixed pole count drift: {arm_id}")
    selected_bodies = len(result.get("selected_manufacturing", []))
    selected_poles = len(result.get("selected_poles", []))
    if status == "FRONT_OPERATION_FEASIBLE":
        if selected_bodies != 219 or selected_poles != 53:
            raise RuntimeError(f"E094 positive witness cardinality drift: {arm_id}")
        if control["fix_boundary"] and result.get("selected_boundary_state_id") != "boundary_macro_09":
            raise RuntimeError("E094 fixed-boundary positive selected another state")
    elif selected_bodies or selected_poles:
        raise RuntimeError(f"E094 nonpositive arm carries witness: {arm_id}")
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
        "mode_class_variable_count": result.get("mode_class_variable_count"),
        "model_variable_count": result.get("model_variable_count"),
        "model_constraint_count": result.get("model_constraint_count"),
        "retained_manufacturing_count": result.get("retained_manufacturing_count"),
        "relocated_pole_count": result.get("relocated_pole_count"),
        "selected_boundary_state_id": result.get("selected_boundary_state_id"),
        "selected_manufacturing_count": selected_bodies,
        "selected_pole_count": selected_poles,
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
    first = arms[0]
    if first["status"] == "FRONT_OPERATION_FEASIBLE":
        return (
            "FIXED_POLE_BOUNDARY_FRONT_OPERATION_WITNESS_FOUND",
            "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING",
        )
    if first["status"] == "UNKNOWN":
        return (
            "FIXED_POLE_BOUNDARY_FRONT_SLICE_CENSORED",
            "DECOMPOSE_BODY_FRONT_ASSIGNMENT_BEFORE_RELEASING_BOUNDARY_OR_POLES",
        )
    if len(arms) != 2:
        raise RuntimeError("E094 missing all-boundary arm after fixed-boundary negative")
    second = arms[1]
    if second["status"] == "FRONT_OPERATION_FEASIBLE":
        return (
            "FIXED_POLE_ALL_BOUNDARY_FRONT_OPERATION_WITNESS_FOUND",
            "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING",
        )
    if second["status"] == "MASTER_INFEASIBLE":
        return (
            "KNOWN_THREE_POLE_SET_FRONT_INFEASIBLE_ACROSS_ALL_BOUNDARY_STATES",
            "SEARCH_ALTERNATIVE_THREE_POLE_SETS_WITH_DECOMPOSED_FRONT_CONSUMER",
        )
    return (
        "FIXED_POLE_ALL_BOUNDARY_FRONT_SLICE_CENSORED",
        "DECOMPOSE_BOUNDARY_BODY_FRONT_ASSIGNMENT_BEFORE_CHANGING_POLE_BUDGET",
    )


def run(*, run_dir: Path) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E094 run directory: {run_dir}")
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
            "schema": "zmd_e094_fixed_pole_front_derivation_v1",
            "source_path": display(SOURCE_PRODUCER),
            "source_sha256": EXPECTED_HASHES[SOURCE_PRODUCER],
            "derived_path": display(derived_path),
            "derived_sha256": sha256_file(derived_path),
            "patches": patches,
            "common_restriction": {
                "fixed_pole_set_source": display(ANCHOR_GEOMETRY),
                "fixed_pole_set_sha256": EXPECTED_HASHES[ANCHOR_GEOMETRY],
                "fixed_pole_count": 53,
                "relocated_pole_count": 3,
                "same_y41_partition": True,
                "same_complete_front_class_semantics": True,
                "same_power_and_nonoverlap": True,
                "same_219_body_and_stable_E078_requirements": True,
                "pure_feasibility": True,
                "stop_after_first_solution": True,
            },
            "arms": json_safe(ARM_CONTROLS),
        },
    )

    overall_started = time.monotonic()
    overall_before = process_memory_snapshot()
    arms: list[dict[str, Any]] = []
    first = run_arm(
        derived_path=derived_path,
        run_dir=run_dir,
        control=ARM_CONTROLS[0],
        arm_index=0,
    )
    arms.append(first)
    print(json.dumps({"arm_id": first["arm_id"], "status": first["status"], "elapsed_seconds": first["elapsed_seconds"], "branches": first["branches"], "conflicts": first["conflicts"]}, sort_keys=True), flush=True)
    if first["status"] == "MASTER_INFEASIBLE":
        second = run_arm(
            derived_path=derived_path,
            run_dir=run_dir,
            control=ARM_CONTROLS[1],
            arm_index=1,
        )
        arms.append(second)
        print(json.dumps({"arm_id": second["arm_id"], "status": second["status"], "elapsed_seconds": second["elapsed_seconds"], "branches": second["branches"], "conflicts": second["conflicts"]}, sort_keys=True), flush=True)
    overall_after = process_memory_snapshot()
    verdict, decision = classify(arms)
    return {
        "schema": "zmd_e094_y41_fixed_pole_front_decomposition_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "anchor": {
            "path": display(ANCHOR_GEOMETRY),
            "sha256": EXPECTED_HASHES[ANCHOR_GEOMETRY],
            "boundary_state_index": 8,
            "boundary_state_id": "boundary_macro_09",
            "fixed_pole_count": 53,
            "relocated_pole_count": 3,
            "pole_set_digest": identity["anchor_pole_set_digest"],
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
        "telemetry": {
            "wrapper_elapsed_seconds": time.monotonic() - overall_started,
            "process_before": overall_before,
            "process_after": overall_after,
        },
        "truth_boundary": (
            "Nested subsets of E090's y=41 three-pole complete-front language. "
            "Both arms fix one exact 53-pole set; Arm A also fixes boundary_macro_09. "
            "Negative arms do not close alternative pole sets. Positive arms do not "
            "establish terminal uniqueness, generic I/O, component binding or routing."
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
        print(json.dumps({"verdict": result["verdict"], "decision": result["decision"], "arm_statuses": [{"arm_id": arm["arm_id"], "status": arm["status"]} for arm in result["arms"]], "elapsed_seconds": result["telemetry"]["wrapper_elapsed_seconds"], "result_path": display(result_path), "result_sha256": sha256_file(result_path)}, ensure_ascii=False, sort_keys=True))
        return 0
    except FileExistsError as exc:
        print(json.dumps({"status": "NO_OVERWRITE_REJECTION", "detail": str(exc)}, sort_keys=True))
        return 2
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e094_y41_fixed_pole_front_decomposition_failure_v1",
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
