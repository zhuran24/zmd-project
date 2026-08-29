#!/usr/bin/env python3
"""E085: fresh no-overwrite replay of E084's first unresolved r33 rung."""

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
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
HISTORY = Path("/home/zhuran24/zmd-pj")
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E085_front_aware_r33_replay/run-001"
)

PRODUCER = ROOT / "research_lab/local/zero_condition/E084_front_benders.py"
SOURCE_CHECKPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E084_front_benders_checkpoint.json"
)
E084_SNAPSHOT = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E084_current_geometry_power_front_repair/MACHINE_SNAPSHOT.json"
)
E084_RESULT = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E084_current_geometry_power_front_repair/RESULT.txt"
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
    PRODUCER: "1248029a1dc94a3e33a4b51836142a5e189210071ab0f5bb6b40917396766d37",
    SOURCE_CHECKPOINT: "0648bf057670c454d1c55a73417d127867c597063362407fe732c4a1b4c6ad9d",
    E084_SNAPSHOT: "5f177b3877c8890bcbc00066aaf1917e980d5c3851409af9f28dd510fe0faf9e",
    E084_RESULT: "b9d2f82ca48974be07fdfc39a5a11399a1eae32cc485df958a9d76ac71e4a91a",
    E081_FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E079_MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
}

TARGET_RETAINED = 186
TARGET_MOVED = 33


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def import_producer() -> Any:
    name = "zmd_e085_frozen_e084_front_benders"
    spec = importlib.util.spec_from_file_location(name, PRODUCER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen producer: {PRODUCER}")
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
    events: dict[str, int] = {}
    for line in lines:
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            events[str(fields[0])] = int(fields[1])
        except ValueError:
            continue
    return events


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
        raise RuntimeError("E085 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"tracked research worktree is not clean: {tracked_status}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E085 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(
                f"frozen identity drift: {path}: {observed} != {expected}"
            )
        try:
            display = str(path.relative_to(ROOT))
        except ValueError:
            display = str(path)
        checked[display] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }

    checkpoint = load_json(SOURCE_CHECKPOINT)
    if int(checkpoint.get("registered_front_candidate_count", -1)) != 34:
        raise RuntimeError("E085 source checkpoint does not carry 34 front rules")
    if int(checkpoint.get("operation_nogood_count", -1)) != 0:
        raise RuntimeError("E085 source checkpoint unexpectedly carries an operation nogood")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked_status,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
        "source_checkpoint_terminal": str(checkpoint.get("terminal", "")),
        "source_checkpoint_registered_front_candidate_count": 34,
    }


def verdict_for_status(status: str) -> tuple[str, str]:
    if status == "FRONT_OPERATION_FEASIBLE":
        return (
            "R33_FRONT_OPERATION_FEASIBLE",
            "RUN_TERMINAL_UNIQUENESS_AND_COMPONENT_AWARE_BINDING",
        )
    if status == "MASTER_INFEASIBLE":
        return (
            "R33_ONE_REPLACEMENT_FRONT_MODEL_INFEASIBLE",
            "SELECT_A_DELIBERATELY_WIDER_POLE_OR_REPAIR_LANGUAGE",
        )
    return (
        "R33_REPLAY_CENSORED",
        "DO_NOT_ADVANCE_RUNG_SELECT_SOLVER_DIVERSE_REPLAY_OR_EXPLICIT_BUDGET_CHANGE",
    )


def run(
    *,
    run_dir: Path,
    master_seconds: float,
    max_iterations: int,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E085 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    checkpoint_path = run_dir / "CHECKPOINT.json"
    producer_result_path = run_dir / "PRODUCER_RESULT.json"
    checkpoint_path.write_bytes(SOURCE_CHECKPOINT.read_bytes())

    producer = import_producer()
    producer.CHECKPOINT = checkpoint_path
    producer.OUTPUT = producer_result_path
    producer.TARGET_RETAINED = TARGET_RETAINED
    producer.TARGET_MOVED = TARGET_MOVED
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
        raise RuntimeError(f"frozen producer returned nonzero exit code: {exit_code}")
    if not producer_result_path.is_file():
        raise RuntimeError("frozen producer did not write PRODUCER_RESULT.json")
    producer_result = load_json(producer_result_path)
    status = str(producer_result.get("status", "MISSING"))
    verdict, decision = verdict_for_status(status)

    if int(producer_result.get("target_retained_current_footprints", -1)) != TARGET_RETAINED:
        raise RuntimeError("producer target retained count drift")
    if int(producer_result.get("target_moved_manufacturing_count", -1)) != TARGET_MOVED:
        raise RuntimeError("producer target moved count drift")
    if status == "FRONT_OPERATION_FEASIBLE":
        selected = list(producer_result.get("selected_manufacturing", []))
        if len(selected) != 219:
            raise RuntimeError("positive producer result lacks 219 manufacturing rows")

    return {
        "schema": "zmd_e085_front_aware_r33_replay_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "target_retained_current_footprints": TARGET_RETAINED,
            "target_moved_manufacturing_count": TARGET_MOVED,
            "master_seconds": float(master_seconds),
            "max_iterations": int(max_iterations),
            "producer_random_seed_base": 85000,
            "operation_checker_random_seed_base": 86000,
        },
        "producer": {
            "status": status,
            "exit_code": exit_code,
            "result_path": str(producer_result_path.relative_to(ROOT)),
            "result_sha256": sha256_file(producer_result_path),
            "checkpoint_path": str(checkpoint_path.relative_to(ROOT)),
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "iteration_count": int(producer_result.get("iteration_count", 0)),
            "registered_front_candidate_count": int(
                producer_result.get("registered_front_candidate_count", 0)
            ),
            "operation_nogood_count": int(
                producer_result.get("operation_nogood_count", 0)
            ),
            "records": json_safe(producer_result.get("records", [])),
            "selected_boundary_state_id": producer_result.get(
                "selected_boundary_state_id"
            ),
            "selected_replacement_pole": producer_result.get(
                "selected_replacement_pole"
            ),
            "selected_manufacturing_count": len(
                producer_result.get("selected_manufacturing", [])
            ),
        },
        "telemetry": {
            "elapsed_seconds": elapsed,
            "process_before": before_process,
            "process_after": after_process,
            "cgroup_before": before_cgroup,
            "cgroup_after": after_cgroup,
            "cgroup_scope_note": (
                "cgroup counters may include sibling processes; ru_maxrss is for "
                "the E085 Python process and its in-process native solver."
            ),
        },
        "truth_boundary": (
            "Fresh replay of the frozen E084 one-replacement front producer at "
            "retained=186 only. UNKNOWN/ITERATION_LIMIT remain censored. A positive "
            "contains body-local front capacity plus exact named operation counts, "
            "not terminal uniqueness, generic I/O, component binding, routing, or "
            "throughput."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--master-seconds", type=float, default=250.0)
    parser.add_argument("--max-iterations", type=int, default=1)
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
                    "elapsed_seconds": result["telemetry"]["elapsed_seconds"],
                    "ru_maxrss_kib": result["telemetry"]["process_after"][
                        "ru_maxrss_kib"
                    ],
                    "result_path": str(result_path.relative_to(ROOT)),
                    "result_sha256": sha256_file(result_path),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e085_front_aware_r33_replay_failure_v1",
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
