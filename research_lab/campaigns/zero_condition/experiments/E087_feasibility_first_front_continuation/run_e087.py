#!/usr/bin/env python3
"""E087: continue E086 front closure from its 98-rule checkpoint."""

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
    "E087_feasibility_first_front_continuation/run-001"
)

DERIVED_PRODUCER = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E086_feasibility_first_front_proposer/run-001/DERIVED_PRODUCER.py"
)
SOURCE_CHECKPOINT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E086_feasibility_first_front_proposer/run-001/CHECKPOINT.json"
)
E086_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E086_feasibility_first_front_proposer/run-001/RESULT.json"
)
E086_CHECK = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E086_feasibility_first_front_proposer/run-001/ARTIFACT_CHECK.json"
)
E086_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E086_feasibility_first_front_proposer/RESULT.txt"
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
HINT_GEOMETRY = (
    ROOT / "research_lab/local/zero_condition/E084_power_integrated_probe_result.json"
)
CANDIDATES = HISTORY / "data/preprocessed/candidate_placements.json"
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"

EXPECTED_HASHES = {
    DERIVED_PRODUCER: "f78d6d6a1cffdb4d5f9e695c18ea60711befc3ad2129628845167ef2b3b8a8c7",
    SOURCE_CHECKPOINT: "06cadbed6f61cb04c8c5445b778378bca336ddc2fa1f2f0804962c1ceb70933d",
    E086_RESULT: "fdb6ad438a05802c24f3a21d7eee5fe05b5bf738f41614e7af99476c887f1351",
    E086_CHECK: "cfc7d91c728319cc3b30446761b39792c49b0c980be66b60dc0f30680e38b4b3",
    E086_DURABLE: "5f864ef100cb446b6683c79315cbc3a38dddc6276f78c331f852037b8db8c96a",
    E081_FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E079_MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    HINT_GEOMETRY: "b7628db5b8db5337eb43b1378f1d81e5a731fc4e102faa3cc5b342af4f575d1f",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
}

INITIAL_FRONT_RULE_COUNT = 98
INITIAL_OPERATION_NOGOOD_COUNT = 0
SEED_SHIFT = 4000


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def import_producer() -> ModuleType:
    name = "zmd_e087_frozen_e086_derived_producer"
    spec = importlib.util.spec_from_file_location(name, DERIVED_PRODUCER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import E086 derived producer: {DERIVED_PRODUCER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E087 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"tracked research worktree is not clean: {tracked_status}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E087 requires PYTHONHASHSEED=0")

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

    e086 = load_json(E086_RESULT)
    e086_check = load_json(E086_CHECK)
    checkpoint = load_json(SOURCE_CHECKPOINT)
    if e086.get("verdict") != "FEASIBILITY_FIRST_PROPOSER_LEARNED_NEW_FRONT_KNOWLEDGE":
        raise RuntimeError("E087 trigger E086 verdict drift")
    if e086_check.get("status") != "PASS_WITH_SEMANTIC_CORRECTION":
        raise RuntimeError("E087 trigger E086 check drift")
    if (
        e086_check.get("decision")
        != "CONTINUE_FROM_98_RULE_CHECKPOINT_WITH_CORRECTED_SCOPE"
    ):
        raise RuntimeError("E087 trigger E086 decision drift")
    if int(checkpoint.get("registered_front_candidate_count", -1)) != 98:
        raise RuntimeError("E087 source checkpoint does not carry 98 front rules")
    if int(checkpoint.get("operation_nogood_count", -1)) != 0:
        raise RuntimeError("E087 source checkpoint operation-nogood drift")
    if checkpoint.get("terminal") != "ITERATION_LIMIT":
        raise RuntimeError("E087 source checkpoint terminal drift")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked_status,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
        "source_checkpoint_front_rule_count": 98,
        "source_checkpoint_operation_nogood_count": 0,
        "corrected_scope": e086_check["corrected_scope"],
    }


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


def classify(
    producer_result: Mapping[str, Any],
    *,
    final_front_rules: int,
    final_operation_nogoods: int,
) -> tuple[str, str]:
    status = str(producer_result.get("status", "MISSING"))
    grew = (
        final_front_rules > INITIAL_FRONT_RULE_COUNT
        or final_operation_nogoods > INITIAL_OPERATION_NOGOOD_COUNT
    )
    if status == "FRONT_OPERATION_FEASIBLE":
        return (
            "FRONT_OPERATION_WITNESS_FOUND_AFTER_98_RULES",
            "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING",
        )
    if status == "MASTER_INFEASIBLE":
        return (
            "FULL_ONE_REPLACEMENT_FRONT_LANGUAGE_INFEASIBLE",
            "WIDEN_POLE_OR_GEOMETRY_LANGUAGE_WITHOUT_REFUTING_PARTITION",
        )
    if status == "ITERATION_LIMIT" and grew:
        return (
            "FRONT_CLOSURE_CONTINUES_TO_LEARN",
            "REASSESS_RULE_GROWTH_AND_CONTINUE_OR_DECOMPOSE",
        )
    if status == "ITERATION_LIMIT":
        return (
            "FRONT_CLOSURE_ITERATION_LIMIT_WITHOUT_NEW_KNOWLEDGE",
            "DECOMPOSE_BOUNDARY_OR_POLE_CHOICE",
        )
    return (
        "FRONT_CLOSURE_CENSORED",
        "DECOMPOSE_BOUNDARY_OR_POLE_CHOICE_OR_CHANGE_SOLVER_FAMILY",
    )


def run(*, run_dir: Path, master_seconds: float, max_iterations: int) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E087 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    checkpoint_path = run_dir / "CHECKPOINT.json"
    producer_result_path = run_dir / "PRODUCER_RESULT.json"
    checkpoint_path.write_bytes(SOURCE_CHECKPOINT.read_bytes())

    producer = import_producer()
    producer.CHECKPOINT = checkpoint_path
    producer.OUTPUT = producer_result_path
    producer.MAX_ITERATIONS = int(max_iterations)
    producer.MASTER_SECONDS = float(master_seconds)
    original_exact_solver = producer.exact_solver

    def shifted_exact_solver(seed: int, seconds: float) -> Any:
        return original_exact_solver(int(seed) + SEED_SHIFT, seconds)

    producer.exact_solver = shifted_exact_solver

    before_process = process_memory_snapshot()
    before_cgroup = cgroup_snapshot()
    started = time.monotonic()
    exit_code = int(producer.main())
    elapsed = time.monotonic() - started
    after_process = process_memory_snapshot()
    after_cgroup = cgroup_snapshot()

    if exit_code != 0:
        raise RuntimeError(f"E086 derived producer returned nonzero exit: {exit_code}")
    if not producer_result_path.is_file():
        raise RuntimeError("E087 producer did not write result")
    producer_result = load_json(producer_result_path)
    if producer_result.get("search_objective") != "MAXIMIZE_RETAINED_CURRENT_FOOTPRINTS":
        raise RuntimeError("E087 producer objective drift")
    if producer_result.get("fixed_retained_target") is not None:
        raise RuntimeError("E087 producer reintroduced a fixed retained rung")

    checkpoint = load_json(checkpoint_path)
    final_front_rules = int(checkpoint.get("registered_front_candidate_count", 0))
    final_operation_nogoods = int(checkpoint.get("operation_nogood_count", 0))
    verdict, decision = classify(
        producer_result,
        final_front_rules=final_front_rules,
        final_operation_nogoods=final_operation_nogoods,
    )

    selected = list(producer_result.get("selected_manufacturing", []))
    retained = sum(bool(row.get("is_current_footprint")) for row in selected)
    status = str(producer_result.get("status", "MISSING"))
    if status == "FRONT_OPERATION_FEASIBLE":
        if len(selected) != 219:
            raise RuntimeError("positive E087 result lacks 219 manufacturing rows")
        if not all("operation" in row and "pose_index" in row for row in selected):
            raise RuntimeError("positive E087 result lacks operation/mode assignment")

    records = list(producer_result.get("records", []))
    best_candidate_retained = max(
        (
            int(row["retained_current_footprints"])
            for row in records
            if row.get("retained_current_footprints") is not None
        ),
        default=None,
    )
    empty_counts = [
        int(row.get("operation_checker_empty_count", 0))
        for row in records
        if row.get("operation_checker_status") == "EMPTY_DOMAIN"
    ]

    return {
        "schema": "zmd_e087_feasibility_first_front_continuation_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "corrected_scope": identity["corrected_scope"],
            "search_objective": "MAXIMIZE_RETAINED_CURRENT_FOOTPRINTS",
            "fixed_retained_target": None,
            "master_seconds_per_iteration": float(master_seconds),
            "max_iterations": int(max_iterations),
            "initial_front_rule_count": INITIAL_FRONT_RULE_COUNT,
            "initial_operation_nogood_count": INITIAL_OPERATION_NOGOOD_COUNT,
            "seed_shift": SEED_SHIFT,
            "effective_master_seed_base": 91000,
            "effective_operation_checker_seed_base": 92000,
        },
        "producer": {
            "status": status,
            "exit_code": exit_code,
            "result_path": display(producer_result_path),
            "result_sha256": sha256_file(producer_result_path),
            "checkpoint_path": display(checkpoint_path),
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "iteration_count": int(producer_result.get("iteration_count", 0)),
            "records": json_safe(records),
            "best_candidate_retained_current_footprints": best_candidate_retained,
            "empty_domain_counts": empty_counts,
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
            "initial_front_rule_count": INITIAL_FRONT_RULE_COUNT,
            "final_front_rule_count": final_front_rules,
            "new_front_rule_count": final_front_rules - INITIAL_FRONT_RULE_COUNT,
            "initial_operation_nogood_count": INITIAL_OPERATION_NOGOOD_COUNT,
            "final_operation_nogood_count": final_operation_nogoods,
            "new_operation_nogood_count": (
                final_operation_nogoods - INITIAL_OPERATION_NOGOOD_COUNT
            ),
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
                "to the E087 Python process and in-process native solver."
            ),
        },
        "truth_boundary": (
            "E087 continues the corrected full bounded one-replacement language. "
            "Proposer rules are necessary front-capacity conditions; only the exact "
            "fixed-geometry checker enforces named operation counts. No terminal "
            "uniqueness, generic I/O, component binding, routing or throughput "
            "conclusion follows without an explicit positive and successor checks."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--master-seconds", type=float, default=100.0)
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
                    "empty_domain_counts": result["producer"][
                        "empty_domain_counts"
                    ],
                    "front_rule_count": result["checkpoint"][
                        "final_front_rule_count"
                    ],
                    "new_front_rules": result["checkpoint"][
                        "new_front_rule_count"
                    ],
                    "operation_nogood_count": result["checkpoint"][
                        "final_operation_nogood_count"
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
                {"status": "NO_OVERWRITE_REJECTION", "detail": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        return 2
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e087_feasibility_first_front_continuation_failure_v1",
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
