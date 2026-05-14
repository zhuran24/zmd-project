#!/usr/bin/env python3
"""A 方案 anchor slicing PoC: 量单 (或少量) anchor master 的 RAM curve.

跑法:
    ANCHOR_FILTER="0,0" DURATION_S=420 .venv/bin/python scripts/anchor_slicing_ram_poc.py

输出:
    .artifacts/anchor_slicing_poc/rss_curve_filter_<slug>.csv
    每 5s 1 行: ts_s, main_rss_gb, all_python_rss_gb, available_gb

跟谁比 (memory project_p1_24_oom_blocked):
    baseline fresh -p 1 (filter=None) trajectory:
        0:57 → 8.87 GB, 1:57 → 10.76 GB, 2:57 → 30.01 GB (CP-SAT solve 阶段一次性飙)
    任务 #67 目标: 单 worker peak RSS ≤ ~15 GB (50% 减) → 解锁 -p 2 production
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _slug(anchor_filter: str) -> str:
    if not anchor_filter.strip() or anchor_filter.strip().lower() in {"none", "baseline"}:
        return "baseline"
    return anchor_filter.replace(";", "_").replace(",", "-").replace(" ", "")


def main() -> int:
    anchor_filter = os.environ.get("ANCHOR_FILTER", "0,0")
    duration_s = int(os.environ.get("DURATION_S", "420"))
    sample_s = int(os.environ.get("SAMPLE_S", "5"))

    outdir = PROJECT_ROOT / ".artifacts" / "anchor_slicing_poc"
    outdir.mkdir(parents=True, exist_ok=True)
    slug = _slug(anchor_filter)
    csv_path = outdir / f"rss_curve_filter_{slug}.csv"
    log_path = outdir / f"main_filter_{slug}.log"

    env = os.environ.copy()
    if slug == "baseline":
        env.pop("EXACT_MASTER_GHOST_ANCHOR_FILTER", None)
    else:
        env["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = anchor_filter

    cmd = [
        str(PROJECT_ROOT / ".venv" / "bin" / "python"),
        "main.py",
        "--campaign-hours",
        "0.1",
        "--parallel-processes",
        "1",
        "--skip-readiness-gate",
    ]

    print(f"PoC anchor_filter={anchor_filter!r} duration={duration_s}s sample={sample_s}s")
    print(f"CSV: {csv_path}")
    print(f"LOG: {log_path}")
    print(f"CMD: {' '.join(cmd)}")

    with open(log_path, "w") as logf:
        proc = subprocess.Popen(
            cmd, cwd=PROJECT_ROOT, env=env, stdout=logf, stderr=subprocess.STDOUT
        )

    rows = [("ts_s", "main_rss_gb", "all_python_rss_gb", "available_gb")]
    start = time.time()
    print(f"main PID={proc.pid}")

    try:
        while True:
            elapsed = time.time() - start
            if elapsed > duration_s:
                print(f"reached duration cap t={elapsed:.0f}s")
                break
            if proc.poll() is not None:
                print(f"main exited t={elapsed:.0f}s code={proc.returncode}")
                break
            try:
                p = psutil.Process(proc.pid)
                main_rss = p.memory_info().rss / 1024 ** 3
                all_rss = main_rss
                for c in p.children(recursive=True):
                    try:
                        all_rss += c.memory_info().rss / 1024 ** 3
                    except psutil.NoSuchProcess:
                        continue
                vm = psutil.virtual_memory()
                avail = vm.available / 1024 ** 3
                rows.append(
                    (
                        round(elapsed, 1),
                        round(main_rss, 2),
                        round(all_rss, 2),
                        round(avail, 2),
                    )
                )
                print(
                    f"  t={elapsed:5.0f}s main={main_rss:5.2f}GB all={all_rss:5.2f}GB avail={avail:5.2f}GB"
                )
                if all_rss > 35.0:
                    print(f"  ABORT: rss={all_rss:.2f}GB > 35 GB OOM headroom")
                    break
            except psutil.NoSuchProcess:
                break
            time.sleep(sample_s)
    finally:
        if proc.poll() is None:
            print("terminating main + children")
            try:
                parent = psutil.Process(proc.pid)
                for c in parent.children(recursive=True):
                    try:
                        c.terminate()
                    except psutil.NoSuchProcess:
                        continue
            except psutil.NoSuchProcess:
                pass
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    parent = psutil.Process(proc.pid)
                    for c in parent.children(recursive=True):
                        try:
                            c.kill()
                        except psutil.NoSuchProcess:
                            continue
                except psutil.NoSuchProcess:
                    pass

    with open(csv_path, "w", newline="") as f:
        csv.writer(f).writerows(rows)

    if len(rows) > 1:
        peaks_all = [r[2] for r in rows[1:]]
        peak = max(peaks_all)
        baseline_peak = 30.01
        delta = baseline_peak - peak
        pct = delta / baseline_peak * 100.0
        print()
        print(f"SUMMARY: peak_all_rss = {peak:.2f} GB")
        print(f"vs baseline {baseline_peak:.2f} GB (memory p1_24_oom_blocked): "
              f"delta -{delta:.2f} GB ({pct:.0f}% less)")
        if peak < 15.0:
            print("VERDICT: <15 GB → A 方案 viable, 可继续做 production slicing loop")
        elif peak < 22.0:
            print("VERDICT: 15-22 GB → 解锁 -p 2 marginal, A 方案值得继续打磨")
        else:
            print("VERDICT: >22 GB → A 方案 RAM 减不够 50%, 软方向再死一个")
    else:
        print("SUMMARY: no samples (main died too fast?)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
