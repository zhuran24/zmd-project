"""A2 failfast probe — 50 inst subset toy master, G17 ≤ 15s.

Per MERGER §5.4 G17. Goal: verify the spike harness *itself* doesn't have
a stupid bug (e.g., O(N²) loop over 80K poses by accident). If a 50-inst
subset toy master takes > 15s to build + feasibility-solve, the harness is
the slow one — abort spike, fix harness, don't waste the full-scale run.

Subset sample: proportional by facility_type from
``data/preprocessed/mandatory_exact_instances.json``. Pose registry pulled
from ``data/preprocessed/candidate_placements.json``.

Toy master form (single coherent var structure, per MERGER §5.2):
- BoolVar ``x[(instance_id, pose_id)]`` for every pose in subset inst's
  facility_type pool.
- Demand constraint: ``sum_p x[(i, p)] == 1`` for each instance.
- No objective, no anti-overlap, no port linking — *toy*, not real master.
  (Per MERGER §5.2: "不接 PoseBoolExactMaster (P1.3A 主体的事, 这里只测
  BoolVar build 跟 constraint add cost).")

This file is spike-only. Off-limits paths untouched.
"""
from __future__ import annotations

import json
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from ortools.sat.python import cp_model


def _resolve_repo_root() -> Path:
    """Return the project root in production and review-mirror layouts.

    Production modules live under project/scripts/spike_prod_scale_lib/.
    Review-package mirrors live under project/code_context/spike/spike_prod_scale_lib/.
    """
    here = Path(__file__).resolve()
    candidates = (here.parent.parent.parent, here.parent.parent.parent.parent)
    for root in candidates:
        if (root / "data" / "preprocessed" / "candidate_placements.json").exists() and (root / "src").is_dir():
            return root
    return candidates[0]


REPO_ROOT = _resolve_repo_root()
MANDATORY_PATH = REPO_ROOT / "data" / "preprocessed" / "mandatory_exact_instances.json"
PLACEMENTS_PATH = REPO_ROOT / "data" / "preprocessed" / "candidate_placements.json"


@dataclass
class ProbeReport:
    instance_count: int
    bool_var_count: int
    constraint_count: int
    build_wall_s: float
    solve_wall_s: float
    total_wall_s: float
    timeout_s: float
    status: int
    status_label: str
    passed: bool
    notes: List[str] = field(default_factory=list)

    def format_human(self) -> str:
        verdict = "G17 PASS" if self.passed else "G17 FAIL"
        lines = [
            f"failfast probe — {verdict}",
            f"  instance_count = {self.instance_count}",
            f"  bool_var_count = {self.bool_var_count}",
            f"  constraint_count = {self.constraint_count}",
            f"  build_wall = {self.build_wall_s:.3f}s",
            f"  solve_wall = {self.solve_wall_s:.3f}s",
            f"  total_wall = {self.total_wall_s:.3f}s  (G17 limit = {self.timeout_s}s)",
            f"  status = {self.status_label}",
        ]
        for note in self.notes:
            lines.append(f"  note: {note}")
        return "\n".join(lines)


def _sample_subset(
    instances: List[dict], target_count: int, seed: int = 42
) -> List[dict]:
    """Proportional-by-facility-type sample without bias.

    For each facility_type, take ceil(count * frac) instances; truncate the
    overflow randomly to land exactly at ``target_count``.
    """
    by_type: Dict[str, List[dict]] = defaultdict(list)
    for inst in instances:
        by_type[inst["facility_type"]].append(inst)

    total = sum(len(v) for v in by_type.values())
    rng = random.Random(seed)

    picks: List[dict] = []
    for ft, lst in by_type.items():
        share = max(1, round(len(lst) * target_count / total))
        rng.shuffle(lst)
        picks.extend(lst[:share])

    # Trim or pad to land exactly at target_count.
    if len(picks) > target_count:
        rng.shuffle(picks)
        picks = picks[:target_count]
    elif len(picks) < target_count:
        # rare; pad with any remaining instances (across types) not yet picked
        picked_ids = {p["instance_id"] for p in picks}
        leftover = [inst for inst in instances if inst["instance_id"] not in picked_ids]
        rng.shuffle(leftover)
        picks.extend(leftover[: target_count - len(picks)])

    return picks


def _build_toy_master(
    subset: List[dict],
    facility_pools: Dict[str, List[dict]],
) -> Tuple[cp_model.CpModel, int, int]:
    """Build BoolVar x[(inst_id, pose_id)] + demand=1 per inst."""
    model = cp_model.CpModel()
    var_count = 0
    constraint_count = 0
    for inst in subset:
        inst_id = inst["instance_id"]
        ft = inst["facility_type"]
        pool = facility_pools.get(ft, [])
        if not pool:
            continue
        terms = []
        for pose in pool:
            pid = pose["pose_id"]
            v = model.NewBoolVar(f"x_{inst_id}__{pid}")
            terms.append(v)
            var_count += 1
        # demand=1: each instance must select exactly one pose.
        model.Add(sum(terms) == 1)
        constraint_count += 1
    return model, var_count, constraint_count


def run_probe(instance_count: int = 50, timeout_s: float = 15.0) -> ProbeReport:
    """Build + feasibility-solve toy master on subset; report wall + status."""
    t_overall = time.monotonic()
    notes: List[str] = []

    instances = json.loads(MANDATORY_PATH.read_text())
    # Observed in spike runner on Python 3.14.x: read_text() on this 53 MB
    # placements file feeds json.loads non-deterministic ValueError. Using
    # read_bytes().decode('utf-8') is a spike-local portability workaround;
    # no master src impact claimed (see toy_translator.load_pose_registry).
    placements = json.loads(PLACEMENTS_PATH.read_bytes().decode("utf-8"))
    facility_pools = placements.get("facility_pools", {})

    subset = _sample_subset(instances, instance_count)
    notes.append(
        "subset distribution: "
        + ", ".join(
            f"{k}={v}" for k, v in sorted(
                {inst["facility_type"]: 0 for inst in subset}.items()
            )
        )
        + " (counts below)"
    )
    type_counts: Dict[str, int] = defaultdict(int)
    for inst in subset:
        type_counts[inst["facility_type"]] += 1
    notes[-1] = "subset by type: " + ", ".join(
        f"{k}={v}" for k, v in sorted(type_counts.items())
    )

    t_build_start = time.monotonic()
    model, var_count, constraint_count = _build_toy_master(subset, facility_pools)
    t_build_end = time.monotonic()

    solver = cp_model.CpSolver()
    # Tight solve cap — probe is supposed to be near-instant. Anything > timeout
    # is a sign the harness itself is slow.
    solver.parameters.max_time_in_seconds = max(1.0, timeout_s - (t_build_end - t_build_start))
    t_solve_start = time.monotonic()
    status = solver.Solve(model)
    t_solve_end = time.monotonic()

    status_label = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN: "UNKNOWN",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
    }.get(status, f"status={status}")

    total = t_solve_end - t_overall
    passed = total <= timeout_s

    return ProbeReport(
        instance_count=len(subset),
        bool_var_count=var_count,
        constraint_count=constraint_count,
        build_wall_s=t_build_end - t_build_start,
        solve_wall_s=t_solve_end - t_solve_start,
        total_wall_s=total,
        timeout_s=timeout_s,
        status=status,
        status_label=status_label,
        passed=passed,
        notes=notes,
    )


if __name__ == "__main__":
    report = run_probe()
    print(report.format_human())
    raise SystemExit(0 if report.passed else 1)
