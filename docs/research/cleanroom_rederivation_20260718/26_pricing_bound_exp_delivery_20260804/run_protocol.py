#!/usr/bin/env python3
"""Run the staged 24-core pricing-bound decision protocol.

The default plan uses five concurrent CP-SAT processes with four workers each,
leaving four logical cores for Python/model construction and the OS.  Research-only.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
PROBE = HERE / "pricing_probe.py"
DUALS_FILE = HERE / "duals.json"
DUAL_NAMES = ("D0_AREA", "D1_SCARCITY_PRICES", "D2_SLACK_EDGE_SELECTIVE")
PRIMARY_BRANCHES = (
    ("CLEAN", False),
    ("LEFT_J3", False),
    ("CLEAN", True),
    ("LEFT_J3", True),
    ("CORNER", True),
)
MULTIPLICITY = {"CLEAN": 16, "LEFT_J3": 1, "CORNER": 1}


@dataclass(frozen=True)
class Task:
    stage: str
    dual: str
    family: str
    hole: bool
    seconds: float
    workers: int
    seed: int
    relaxed: bool = False
    loose: bool = False
    max_poles: Optional[int] = None
    cap_scaled: Optional[int] = None

    @property
    def key(self) -> Tuple[str, str, bool]:
        return (self.dual, self.family, self.hole)

    @property
    def slug(self) -> str:
        suffix = "hole" if self.hole else "nohole"
        mode = "relaxed" if self.relaxed else ("loose" if self.loose else "strict")
        return f"{self.dual}__{self.family}__{suffix}__{mode}__seed{self.seed}"


def _load_json(path: Path) -> Mapping[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_one(task: Task, out_root: Path, python: Path, bundle: Path, dry_run: bool) -> Dict[str, object]:
    stage_dir = out_root / task.stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    out = stage_dir / f"{task.slug}.json"
    log = stage_dir / f"{task.slug}.log"
    command = [
        str(python), str(PROBE),
        "--bundle", str(bundle),
        "--duals", str(DUALS_FILE),
        "--dual", task.dual,
        "--family", task.family,
        "--seconds", str(task.seconds),
        "--workers", str(task.workers),
        "--seed", str(task.seed),
        "--max-poles", "none" if task.max_poles is None else str(task.max_poles),
        "--out", str(out),
    ]
    if task.hole:
        command.append("--hole")
    if task.relaxed:
        command.append("--relaxed")
    if task.loose:
        command.append("--loose")
    if task.cap_scaled is not None:
        command += ["--cap-scaled", str(task.cap_scaled)]
    if dry_run:
        return {"task": asdict(task), "command": command, "out": str(out), "dry_run": True}
    started = time.monotonic()
    with log.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
    result: Dict[str, object] = {
        "task": asdict(task), "command": command, "out": str(out),
        "returncode": completed.returncode,
        "runner_wall_seconds": round(time.monotonic() - started, 6),
    }
    if completed.returncode == 0 and out.exists():
        result["result"] = _load_json(out)
    return result


def run_batch(
    tasks: Sequence[Task], *, out_root: Path, python: Path, bundle: Path,
    max_parallel: int, dry_run: bool,
) -> List[Dict[str, object]]:
    if dry_run:
        return [_run_one(t, out_root, python, bundle, True) for t in tasks]
    rows: List[Dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {pool.submit(_run_one, t, out_root, python, bundle, False): t for t in tasks}
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            task = futures[future]
            status = row.get("result", {}).get("status") if isinstance(row.get("result"), dict) else "ERROR"
            print(f"[{task.stage}] {task.slug}: {status}", flush=True)
    return rows


def _result_map(rows: Sequence[Mapping[str, object]]) -> Dict[Tuple[str, str, bool], Mapping[str, object]]:
    result: Dict[Tuple[str, str, bool], Mapping[str, object]] = {}
    for row in rows:
        task = row.get("task")
        data = row.get("result")
        if not isinstance(task, Mapping) or not isinstance(data, Mapping):
            continue
        key = (str(task["dual"]), str(task["family"]), bool(task["hole"]))
        result[key] = data
    return result


def _score(data: Mapping[str, object], family: str) -> Tuple[float, float, float]:
    cap = data.get("objective_cap_scaled")
    bound = data.get("certified_objective_bound_scaled")
    incumbent = data.get("objective_value_scaled")
    if cap is None or bound is None:
        return (0.0, 0.0, 0.0)
    drop = max(0.0, float(cap) - float(bound))
    gap = max(1.0, float(cap) - float(incumbent if incumbent is not None else 0.0))
    closure = drop / gap
    leverage = MULTIPLICITY.get(family, 1) * drop
    return (leverage, closure, drop)


def _select_stage2(stage1: Mapping[Tuple[str, str, bool], Mapping[str, object]], limit: int = 8):
    mandatory = {
        ("D0_AREA", "CLEAN", False),
        ("D1_SCARCITY_PRICES", "CLEAN", False),
        ("D2_SLACK_EDGE_SELECTIVE", "CLEAN", True),
        ("D0_AREA", "LEFT_J3", False),
        ("D2_SLACK_EDGE_SELECTIVE", "LEFT_J3", True),
        ("D0_AREA", "CORNER", True),
    }
    ranked = sorted(
        stage1,
        key=lambda key: _score(stage1[key], key[1]),
        reverse=True,
    )
    chosen: List[Tuple[str, str, bool]] = []
    for key in ranked:
        leverage, closure, drop = _score(stage1[key], key[1])
        if key in mandatory or drop >= 1.0 or closure >= 0.10:
            chosen.append(key)
    for key in mandatory:
        if key in stage1 and key not in chosen:
            chosen.append(key)
    chosen = sorted(chosen, key=lambda key: _score(stage1[key], key[1]), reverse=True)
    # Preserve all mandatory entries even if this slightly exceeds the nominal limit.
    head = chosen[:limit]
    for key in mandatory:
        if key in stage1 and key not in head:
            if len(head) < limit:
                head.append(key)
            else:
                replace = next((i for i in range(len(head) - 1, -1, -1) if head[i] not in mandatory), None)
                if replace is not None:
                    head[replace] = key
    return list(dict.fromkeys(head))


def _select_stage3(stage2: Mapping[Tuple[str, str, bool], Mapping[str, object]], limit: int = 4):
    ranked = sorted(stage2, key=lambda key: _score(stage2[key], key[1]), reverse=True)
    mandatory = [
        ("D0_AREA", "CLEAN", False),
        ("D1_SCARCITY_PRICES", "CLEAN", False),
        ("D2_SLACK_EDGE_SELECTIVE", "CLEAN", True),
        ("D2_SLACK_EDGE_SELECTIVE", "LEFT_J3", True),
    ]
    chosen: List[Tuple[str, str, bool]] = []
    for key in mandatory + ranked:
        if key in stage2 and key not in chosen:
            chosen.append(key)
        if len(chosen) >= limit:
            break
    return chosen


def _tasks_for_keys(
    stage: str, keys: Iterable[Tuple[str, str, bool]], seconds: float, seed: int,
    caps: Mapping[Tuple[str, str, bool], int], workers: int,
) -> List[Task]:
    return [
        Task(
            stage=stage, dual=dual, family=family, hole=hole,
            seconds=seconds, workers=workers, seed=seed,
            cap_scaled=caps.get((dual, family, hole)),
        )
        for dual, family, hole in keys
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--bundle", type=Path, default=HERE.parent / "pricing_exp" / "11_runnable")
    parser.add_argument("--max-parallel", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--hard-wall-seconds", type=float, default=1200.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.max_parallel * args.workers > 24:
        raise SystemExit("max_parallel * workers must not exceed 24")

    args.out_root.mkdir(parents=True, exist_ok=True)
    overall = time.monotonic()
    manifest: Dict[str, object] = {
        "schema_version": 1,
        "started_unix": time.time(),
        "hard_wall_seconds": args.hard_wall_seconds,
        "max_parallel": args.max_parallel,
        "workers_per_task": args.workers,
        "stages": {},
    }

    keys = [(dual, family, hole) for dual in DUAL_NAMES for family, hole in PRIMARY_BRANCHES]
    relaxed_tasks = [
        Task("stage0_relaxed", dual, family, hole, 15.0, args.workers, 0, relaxed=True)
        for dual, family, hole in keys
    ]
    stage0 = run_batch(relaxed_tasks, out_root=args.out_root, python=args.python,
                       bundle=args.bundle, max_parallel=args.max_parallel, dry_run=args.dry_run)
    manifest["stages"]["stage0_relaxed"] = stage0
    if args.dry_run:
        # Dry-run cannot select later stages from measurements; emit the fixed upper plan.
        manifest["later_stage_policy"] = {
            "stage1": "all 15 primary tasks, strict, 15 s",
            "stage2": "up to 8 selected tasks, strict, 60 s",
            "stage3": "4 selected tasks, strict, 240 s, seed 0",
            "stage3_repeat": "same 4 tasks, strict, 240 s, seed 1",
            "calibration": "D0 CORNER+hole loose, 240 s",
        }
        (args.out_root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps(manifest, indent=2))
        return 0

    s0map = _result_map(stage0)
    caps: Dict[Tuple[str, str, bool], int] = {}
    for key in keys:
        data = s0map.get(key, {})
        bound = data.get("certified_objective_bound_scaled") if isinstance(data, Mapping) else None
        if bound is None:
            # Fall back to the dual pi already carried in the Stage-0 output.
            bound = data.get("pi_scaled") if isinstance(data, Mapping) else None
        if bound is None:
            raise RuntimeError(f"no legal cap for {key}")
        caps[key] = int(math.ceil(float(bound)))

    if time.monotonic() - overall >= args.hard_wall_seconds:
        manifest["stopped"] = "hard wall after stage0"
    else:
        stage1_tasks = _tasks_for_keys("stage1_15s", keys, 15.0, 0, caps, args.workers)
        stage1 = run_batch(stage1_tasks, out_root=args.out_root, python=args.python,
                           bundle=args.bundle, max_parallel=args.max_parallel, dry_run=False)
        manifest["stages"]["stage1_15s"] = stage1
        s1map = _result_map(stage1)
        selected2 = _select_stage2(s1map)
        manifest["stage2_selected"] = selected2

        if time.monotonic() - overall < args.hard_wall_seconds:
            stage2_tasks = _tasks_for_keys("stage2_60s", selected2, 60.0, 0, caps, args.workers)
            stage2 = run_batch(stage2_tasks, out_root=args.out_root, python=args.python,
                               bundle=args.bundle, max_parallel=args.max_parallel, dry_run=False)
            manifest["stages"]["stage2_60s"] = stage2
            s2map = _result_map(stage2)
            selected3 = _select_stage3(s2map)
            manifest["stage3_selected"] = selected3

            if time.monotonic() - overall < args.hard_wall_seconds:
                stage3_tasks = _tasks_for_keys("stage3_240s_seed0", selected3, 240.0, 0, caps, args.workers)
                # The loose CORNER-hole positive control fills the fifth process slot.
                cal_key = ("D0_AREA", "CORNER", True)
                stage3_tasks.append(Task(
                    "stage3_240s_seed0", *cal_key, 240.0, args.workers, 0,
                    loose=True, max_poles=3, cap_scaled=caps.get(cal_key),
                ))
                stage3 = run_batch(stage3_tasks, out_root=args.out_root, python=args.python,
                                   bundle=args.bundle, max_parallel=args.max_parallel, dry_run=False)
                manifest["stages"]["stage3_240s_seed0"] = stage3

                if time.monotonic() - overall < args.hard_wall_seconds:
                    repeats = _tasks_for_keys("stage4_240s_seed1", selected3, 240.0, 1, caps, args.workers)
                    stage4 = run_batch(repeats, out_root=args.out_root, python=args.python,
                                       bundle=args.bundle, max_parallel=args.max_parallel, dry_run=False)
                    manifest["stages"]["stage4_240s_seed1"] = stage4

    manifest["wall_seconds"] = round(time.monotonic() - overall, 6)
    (args.out_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"manifest": str(args.out_root / 'manifest.json'),
                      "wall_seconds": manifest["wall_seconds"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
