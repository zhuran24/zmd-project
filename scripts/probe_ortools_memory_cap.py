#!/usr/bin/env python3
"""Probe whether OR-Tools max_memory_in_mb actually caps OS RSS.

CP-SAT proto says default max_memory_in_mb=10000 (10 GB). But P1 #24
实测单 worker 飙到 28 GB anon-rss 没被这参数 cap. 这个 probe 跑一个
内存吃得起来的合成 problem, 显式设 cap, 实时监 RSS, 看 OR-Tools 是
graceful exit 还是 RSS 突破 cap.

策略: 加大量 boolean var + dense clauses 让 SAT presolve 加完 LP
relaxation 后 search tree 起飞.
"""

from __future__ import annotations

import os
import sys
import time

import psutil
from ortools.sat.python import cp_model


def make_memory_intensive_model() -> cp_model.CpModel:
    """Build a model that pushes CP-SAT to allocate big internal state."""
    model = cp_model.CpModel()
    n = 200
    bvars = [model.NewBoolVar(f"x_{i}") for i in range(n)]
    # Many random-looking pairwise constraints + cardinality bounds
    for i in range(n):
        for j in range(i + 1, n, 3):
            model.AddBoolOr([bvars[i], bvars[j]])
    for i in range(n):
        for j in range(i + 1, n, 7):
            model.AddBoolOr([bvars[i].Not(), bvars[j]])
    # Sum cardinality target
    model.Add(sum(bvars) >= n // 2)
    model.Add(sum(bvars) <= n - 5)
    # Objective: minimize sum  → search through cardinality levels
    model.Minimize(sum(bvars))
    return model


def main() -> int:
    cap_mb = int(os.environ.get("PROBE_MAX_MEMORY_MB", "2000"))
    time_limit = float(os.environ.get("PROBE_TIME_LIMIT_S", "60"))

    print(f"Probe: max_memory_in_mb={cap_mb}, time_limit_s={time_limit}")
    model = make_memory_intensive_model()
    solver = cp_model.CpSolver()
    solver.parameters.max_memory_in_mb = cap_mb
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 8
    solver.parameters.log_search_progress = False

    proc = psutil.Process(os.getpid())
    start_ts = time.time()
    peak_rss_mb = 0

    # Background sampler thread would be cleaner; here just sample
    # before/after — but solver call is blocking. Use ortools callback?
    class RssCallback(cp_model.CpSolverSolutionCallback):
        def __init__(self) -> None:
            super().__init__()
            self.peak_mb = 0
            self.calls = 0

        def OnSolutionCallback(self) -> None:
            self.calls += 1
            rss_mb = proc.memory_info().rss / 1024 / 1024
            if rss_mb > self.peak_mb:
                self.peak_mb = rss_mb
            elapsed = time.time() - start_ts
            print(
                f"  t={elapsed:.1f}s call#{self.calls} obj={self.ObjectiveValue():.0f} rss={rss_mb:.1f}MB"
            )

    cb = RssCallback()
    status = solver.Solve(model, cb)
    elapsed = time.time() - start_ts

    final_rss_mb = proc.memory_info().rss / 1024 / 1024
    peak_rss_mb = max(cb.peak_mb, final_rss_mb)

    status_name = solver.StatusName(status)
    print(f"\nFinal: status={status_name}, elapsed={elapsed:.1f}s")
    print(f"Cap requested: {cap_mb} MB")
    print(f"Final RSS: {final_rss_mb:.1f} MB")
    print(f"Peak RSS observed: {peak_rss_mb:.1f} MB")
    if peak_rss_mb > cap_mb:
        print(f"VERDICT: max_memory_in_mb 不严格限 OS RSS  (实测超 {peak_rss_mb - cap_mb:.0f} MB)")
        return 2
    print("VERDICT: max_memory_in_mb 限住了 OS RSS — 可用于 P1 #24 解锁")
    return 0


if __name__ == "__main__":
    sys.exit(main())
