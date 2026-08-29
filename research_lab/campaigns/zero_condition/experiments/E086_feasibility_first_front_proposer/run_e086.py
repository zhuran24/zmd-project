#!/usr/bin/env python3
"""E086: derive and run a feasibility-first front-aware proposer."""

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
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
HISTORY = Path("/home/zhuran24/zmd-pj")
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E086_feasibility_first_front_proposer/run-001"
)

SOURCE_PRODUCER = ROOT / "research_lab/local/zero_condition/E084_front_benders.py"
SOURCE_CHECKPOINT = (
    ROOT / "research_lab/local/zero_condition/E084_front_benders_checkpoint.json"
)
HINT_GEOMETRY = (
    ROOT / "research_lab/local/zero_condition/E084_power_integrated_probe_result.json"
)
E085_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E085_front_aware_r33_replay/run-001/RESULT.json"
)
E085_CHECK = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E085_front_aware_r33_replay/run-001/ARTIFACT_CHECK.json"
)
E085_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E085_front_aware_r33_replay/RESULT.txt"
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
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"

EXPECTED_HASHES = {
    SOURCE_PRODUCER: "1248029a1dc94a3e33a4b51836142a5e189210071ab0f5bb6b40917396766d37",
    SOURCE_CHECKPOINT: "0648bf057670c454d1c55a73417d127867c597063362407fe732c4a1b4c6ad9d",
    HINT_GEOMETRY: "b7628db5b8db5337eb43b1378f1d81e5a731fc4e102faa3cc5b342af4f575d1f",
    E085_RESULT: "8602a20c26dcb37742ec85a70cb619e402302807523b7a5006fa501cb1bb9a68",
    E085_CHECK: "f53d5151a6b09e86f40b2f951160f66604b4d7e2e0a6151518309994a880919c",
    E085_DURABLE: "3f1a9fd13ba36eb84f1871179369370e656c7f3833d8395fe2d5ffb3206ae048",
    E081_FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E079_MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
}


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
    encoded = (
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
        handle.write(encoded)
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


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E086 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"tracked research worktree is not clean: {tracked_status}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E086 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(
                f"frozen identity drift: {path}: {observed} != {expected}"
            )
        checked[display(path)] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }

    e085 = load_json(E085_RESULT)
    e085_check = load_json(E085_CHECK)
    if e085.get("verdict") != "R33_REPLAY_CENSORED":
        raise RuntimeError("E086 trigger E085 verdict drift")
    if e085_check.get("classification") != "CENSORED_UNKNOWN_NO_WITNESS":
        raise RuntimeError("E086 trigger E085 artifact classification drift")
    source_checkpoint = load_json(SOURCE_CHECKPOINT)
    if int(source_checkpoint.get("registered_front_candidate_count", -1)) != 34:
        raise RuntimeError("E086 source checkpoint front-rule count drift")
    if int(source_checkpoint.get("operation_nogood_count", -1)) != 0:
        raise RuntimeError("E086 source checkpoint operation-nogood drift")

    hint = load_json(HINT_GEOMETRY)
    if hint.get("status") != "OPTIMAL":
        raise RuntimeError("E086 hint geometry is not the expected OPTIMAL witness")
    if len(hint.get("selected_manufacturing", [])) != 219:
        raise RuntimeError("E086 hint geometry lacks 219 manufacturing rows")
    if int(hint.get("moved_manufacturing_count", -1)) != 31:
        raise RuntimeError("E086 hint geometry move-count drift")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked_status,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
        "source_checkpoint_registered_front_candidate_count": 34,
        "source_checkpoint_operation_nogood_count": 0,
        "hint_geometry_status": "OPTIMAL",
        "hint_geometry_retained_current_footprints": int(
            hint["objective_retained_current_footprints"]
        ),
    }


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"derived-source patch {label} matched {count} times")
    return source.replace(old, new, 1)


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
        "hint_geometry_constant",
        'CANDIDATES = HISTORY / "data/preprocessed/candidate_placements.json"\nCHECKPOINT = ROOT / "research_lab/local/zero_condition/E084_front_benders_checkpoint.json"',
        'CANDIDATES = HISTORY / "data/preprocessed/candidate_placements.json"\nHINT_GEOMETRY = ROOT / "research_lab/local/zero_condition/E084_power_integrated_probe_result.json"\nCHECKPOINT = ROOT / "research_lab/local/zero_condition/E084_front_benders_checkpoint.json"',
    )
    patch(
        "solver_diversity",
        "    solver.parameters.random_seed = int(seed)\n    solver.parameters.symmetry_level = 3\n    return solver",
        "    solver.parameters.random_seed = int(seed)\n    solver.parameters.symmetry_level = 3\n    solver.parameters.randomize_search = True\n    solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH\n    solver.parameters.repair_hint = True\n    solver.parameters.hint_conflict_limit = 1000\n    return solver",
    )
    patch(
        "feasibility_first_objective",
        "    model.Add(cp_model.LinearExpr.Sum(retained_terms) == TARGET_RETAINED)\n    for index, row in enumerate(manufacturing_rows):\n        if row[\"is_current_footprint\"]:\n            model.AddHint(body_vars[index], 1)\n    for index, row in enumerate(pole_rows):\n        if row[\"pose_id\"] == \"p_x59_y06_o0_m_omni\":\n            model.AddHint(pole_vars[index], 1)\n            break",
        "    retained_expr = cp_model.LinearExpr.Sum(retained_terms)\n    model.Maximize(retained_expr)\n\n    hint_geometry = load(HINT_GEOMETRY)\n    hint_bodies = {\n        tuple(sorted(cell(value) for value in row[\"body\"]))\n        for row in hint_geometry[\"selected_manufacturing\"]\n    }\n    if len(hint_bodies) != 219:\n        raise RuntimeError(f\"complete hint body count drift: {len(hint_bodies)}\")\n    matched_hint_bodies = 0\n    for index, row in enumerate(manufacturing_rows):\n        selected_hint = row[\"body\"] in hint_bodies\n        model.AddHint(body_vars[index], int(selected_hint))\n        matched_hint_bodies += int(selected_hint)\n    if matched_hint_bodies != 219:\n        raise RuntimeError(f\"hint body remap drift: {matched_hint_bodies}\")\n    hint_pole_pose_index = int(hint_geometry[\"selected_replacement_pole\"][\"pose_index\"])\n    hint_pole_matches = 0\n    for index, row in enumerate(pole_rows):\n        selected_hint = int(row[\"pose_index\"]) == hint_pole_pose_index\n        model.AddHint(pole_vars[index], int(selected_hint))\n        hint_pole_matches += int(selected_hint)\n    if hint_pole_matches != 1:\n        raise RuntimeError(f\"hint pole remap drift: {hint_pole_matches}\")\n    hint_boundary_state_index = int(hint_geometry[\"selected_boundary_state_index\"])",
    )
    patch(
        "boundary_hint",
        "    current_boundary_pose_set = {\n        int(row[\"pose_idx\"])\n        for row in parent.values()\n        if str(row[\"facility_type\"]) == \"boundary_storage_port\"\n    }\n    current_state_matches = [\n        index\n        for index, state in enumerate(macro[\"states\"])\n        if set(map(int, state[\"pose_indices\"])) == current_boundary_pose_set\n    ]",
        "    current_state_matches = [hint_boundary_state_index]",
    )
    patch(
        "master_seed_family",
        "        solver = exact_solver(85000 + iteration, MASTER_SECONDS)",
        "        solver = exact_solver(87000 + iteration, MASTER_SECONDS)",
    )
    patch(
        "checker_seed_family",
        "            seed=86000 + iteration,",
        "            seed=88000 + iteration,",
    )
    patch(
        "candidate_retention_telemetry",
        '            "master_status": solver.StatusName(status),\n            "elapsed_seconds": elapsed,',
        '            "master_status": solver.StatusName(status),\n            "elapsed_seconds": elapsed,\n            "retained_current_footprints": int(\n                sum(solver.Value(variable) for variable in retained_terms)\n            ),\n            "retained_best_bound": float(solver.BestObjectiveBound()),',
    )
    patch(
        "result_language_identity",
        '        "target_retained_current_footprints": TARGET_RETAINED,\n        "target_moved_manufacturing_count": 219 - TARGET_RETAINED,',
        '        "search_objective": "MAXIMIZE_RETAINED_CURRENT_FOOTPRINTS",\n        "fixed_retained_target": None,',
    )
    patch(
        "claim_boundary_wording",
        '"INFEASIBLE result is conclusive at the 31-move rung because unregistered "',
        '"INFEASIBLE result is conclusive only for the full feasibility-first "\n            "one-replacement language because unregistered "',
    )
    return source, patches


def import_derived(path: Path) -> ModuleType:
    name = "zmd_e086_derived_front_proposer"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import derived producer: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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
    result: dict[str, int] = {}
    for line in lines:
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            result[str(fields[0])] = int(fields[1])
        except ValueError:
            continue
    return result


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


def classify(producer_result: dict[str, Any]) -> tuple[str, str]:
    status = str(producer_result.get("status", "MISSING"))
    checkpoint_growth = (
        int(producer_result.get("registered_front_candidate_count", 0)) > 34
        or int(producer_result.get("operation_nogood_count", 0)) > 0
    )
    if status == "FRONT_OPERATION_FEASIBLE":
        return (
            "FEASIBILITY_FIRST_FRONT_OPERATION_WITNESS_FOUND",
            "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING",
        )
    if status == "MASTER_INFEASIBLE":
        return (
            "FEASIBILITY_FIRST_ONE_REPLACEMENT_LANGUAGE_INFEASIBLE",
            "WIDEN_POLE_OR_GEOMETRY_LANGUAGE_WITHOUT_REFUTING_PARTITION",
        )
    if status == "ITERATION_LIMIT" and checkpoint_growth:
        return (
            "FEASIBILITY_FIRST_PROPOSER_LEARNED_NEW_FRONT_KNOWLEDGE",
            "CONTINUE_FROM_E086_CHECKPOINT_IN_FRESH_SUCCESSOR",
        )
    return (
        "FEASIBILITY_FIRST_PROPOSER_CENSORED",
        "DECOMPOSE_BOUNDARY_OR_POLE_CHOICE_OR_CHANGE_SOLVER_FAMILY",
    )


def run(*, run_dir: Path, master_seconds: float, max_iterations: int) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E086 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    derived_path = run_dir / "DERIVED_PRODUCER.py"
    derivation_path = run_dir / "DERIVATION.json"
    checkpoint_path = run_dir / "CHECKPOINT.json"
    producer_result_path = run_dir / "PRODUCER_RESULT.json"

    derived_source, patches = derive_source()
    derived_bytes = derived_source.encode("utf-8")
    with derived_path.open("xb") as handle:
        handle.write(derived_bytes)
        handle.flush()
        os.fsync(handle.fileno())
    checkpoint_path.write_bytes(SOURCE_CHECKPOINT.read_bytes())
    dump_exclusive(
        derivation_path,
        {
            "schema": "zmd_e086_derived_producer_identity_v1",
            "source_path": display(SOURCE_PRODUCER),
            "source_sha256": EXPECTED_HASHES[SOURCE_PRODUCER],
            "derived_path": display(derived_path),
            "derived_sha256": sha256_file(derived_path),
            "patches": patches,
            "semantic_preservation": {
                "complete_boundary_disjunction": True,
                "fixed_52_plus_one_replacement_pole": True,
                "power": True,
                "stable_e078_bodies": True,
                "initial_front_rules": 34,
                "named_operation_checker": True,
                "changed_feasible_set": False,
                "changed_search_objective": True,
                "changed_hints_only": True,
            },
        },
    )

    producer = import_derived(derived_path)
    producer.CHECKPOINT = checkpoint_path
    producer.OUTPUT = producer_result_path
    producer.MAX_ITERATIONS = int(max_iterations)
    producer.MASTER_SECONDS = float(master_seconds)

    before_process = process_memory_snapshot()
    before_cgroup = cgroup_snapshot()
    started = time.monotonic()
    exit_code = int(producer.main())
    elapsed = time.monotonic() - started
    after_process = process_memory_snapshot()
    after_cgroup = cgroup_snapshot()

    if exit_code != 0:
        raise RuntimeError(f"derived producer returned nonzero exit code: {exit_code}")
    if not producer_result_path.is_file():
        raise RuntimeError("derived producer did not write PRODUCER_RESULT.json")
    producer_result = load_json(producer_result_path)
    if producer_result.get("search_objective") != "MAXIMIZE_RETAINED_CURRENT_FOOTPRINTS":
        raise RuntimeError("derived producer result lacks feasibility-first identity")
    if producer_result.get("fixed_retained_target") is not None:
        raise RuntimeError("derived producer unexpectedly retained a fixed rung")

    verdict, decision = classify(producer_result)
    selected = list(producer_result.get("selected_manufacturing", []))
    retained = sum(bool(row.get("is_current_footprint")) for row in selected)
    if producer_result.get("status") == "FRONT_OPERATION_FEASIBLE":
        if len(selected) != 219:
            raise RuntimeError("positive E086 result lacks 219 manufacturing rows")
        if not all("operation" in row and "pose_index" in row for row in selected):
            raise RuntimeError("positive E086 result lacks operation/mode assignment")

    checkpoint = load_json(checkpoint_path)
    records = list(producer_result.get("records", []))
    best_candidate_retained = max(
        (
            int(row["retained_current_footprints"])
            for row in records
            if row.get("retained_current_footprints") is not None
        ),
        default=None,
    )

    return {
        "schema": "zmd_e086_feasibility_first_front_proposer_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "search_objective": "MAXIMIZE_RETAINED_CURRENT_FOOTPRINTS",
            "fixed_retained_target": None,
            "master_seconds_per_iteration": float(master_seconds),
            "max_iterations": int(max_iterations),
            "initial_front_rule_count": 34,
            "initial_operation_nogood_count": 0,
            "master_seed_base": 87000,
            "operation_checker_seed_base": 88000,
            "hint_source": display(HINT_GEOMETRY),
            "hint_source_sha256": EXPECTED_HASHES[HINT_GEOMETRY],
        },
        "derivation": {
            "path": display(derivation_path),
            "sha256": sha256_file(derivation_path),
            "derived_source_path": display(derived_path),
            "derived_source_sha256": sha256_file(derived_path),
            "patch_count": len(patches),
        },
        "producer": {
            "status": str(producer_result.get("status", "MISSING")),
            "exit_code": exit_code,
            "result_path": display(producer_result_path),
            "result_sha256": sha256_file(producer_result_path),
            "checkpoint_path": display(checkpoint_path),
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "iteration_count": int(producer_result.get("iteration_count", 0)),
            "registered_front_candidate_count": int(
                producer_result.get("registered_front_candidate_count", 0)
            ),
            "operation_nogood_count": int(
                producer_result.get("operation_nogood_count", 0)
            ),
            "records": json_safe(records),
            "best_candidate_retained_current_footprints": best_candidate_retained,
            "selected_boundary_state_id": producer_result.get(
                "selected_boundary_state_id"
            ),
            "selected_replacement_pole": producer_result.get(
                "selected_replacement_pole"
            ),
            "selected_manufacturing_count": len(selected),
            "selected_retained_current_footprints": retained if selected else None,
            "selected_moved_manufacturing_count": 219 - retained if selected else None,
        },
        "checkpoint": {
            "registered_front_candidate_count": int(
                checkpoint.get("registered_front_candidate_count", 0)
            ),
            "operation_nogood_count": int(checkpoint.get("operation_nogood_count", 0)),
            "terminal": str(checkpoint.get("terminal", "")),
        },
        "telemetry": {
            "elapsed_seconds": elapsed,
            "process_before": before_process,
            "process_after": after_process,
            "cgroup_before": before_cgroup,
            "cgroup_after": after_cgroup,
            "cgroup_scope_note": (
                "cgroup counters may include sibling processes; ru_maxrss is local "
                "to the E086 Python process and its in-process native solver."
            ),
        },
        "truth_boundary": (
            "E086 changes search objective, hints and seed family but not the stated "
            "one-replacement feasible set. Proposer front rules are necessary count "
            "conditions; only the fixed-geometry checker enforces exact named "
            "operation counts. No terminal uniqueness, generic I/O, component "
            "binding, routing or throughput conclusion follows."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--master-seconds", type=float, default=110.0)
    parser.add_argument("--max-iterations", type=int, default=2)
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    result_path = run_dir / "RESULT.json"
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            master_seconds=float(args.master_seconds),
            max_iterations=int(args.max_iterations),
        )
        dump_exclusive(result_path, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "producer_status": result["producer"]["status"],
                    "best_candidate_retained": result["producer"][
                        "best_candidate_retained_current_footprints"
                    ],
                    "front_rule_count": result["checkpoint"][
                        "registered_front_candidate_count"
                    ],
                    "operation_nogood_count": result["checkpoint"][
                        "operation_nogood_count"
                    ],
                    "elapsed_seconds": result["telemetry"]["elapsed_seconds"],
                    "ru_maxrss_kib": result["telemetry"]["process_after"][
                        "ru_maxrss_kib"
                    ],
                    "result_path": display(result_path),
                    "result_sha256": sha256_file(result_path),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except FileExistsError as exc:
        print(
            json.dumps(
                {
                    "status": "NO_OVERWRITE_REJECTION",
                    "detail": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        return 2
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e086_feasibility_first_front_proposer_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not failure_path.exists():
            dump_exclusive(failure_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
