#!/usr/bin/env python
"""审查树 L1.5 — Dynamic review smoke test.

抓静态 review (preflight gate / 多 agent 自主审查 / ultrareview) 抓不到的
runtime path bug. 触发场景:
- 改 src/search/outer_search.py / benders_loop.py / exact_campaign.py
- 改 src/models/{binding,routing,flow}_subproblem.py
- 任何 env-gate 影响 runtime control flow 的改动

教训: 2026-05-11 outer_search A+B 修订 (EXACT_OUTER_SKIP_UNKNOWN env-gate)
4 agent L2 复审 + 全量 pytest + readiness gate 全过, 但 168h 真跑发现 main
启动后没进 LBBD inner loop, dumper 100+ 条全是 boundary precheck. 静态 review
没人跑过 e2e short campaign 验证 candidate state 变化 → 漏 bug.

使用:
    .venv/bin/python scripts/dynamic_review_smoke.py [--minutes 5] [--env KEY=VAL]

退出码:
    0 = PASS (runtime 行为符合预期)
    1 = FAIL (assertion 不过, 详情见 stdout)
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def snapshot_state() -> dict:
    """Capture current campaign state + binding dump stats."""
    state_path = PROJECT_ROOT / "data" / "checkpoints" / "exact_campaign_state.json"
    dumps_path = PROJECT_ROOT / "data" / "telemetry" / "binding_dumps.jsonl"

    candidates: dict = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        cands = state.get("candidates", {})
        statuses = Counter(
            c.get("status") for c in cands.values() if isinstance(c, dict)
        )
        candidates = dict(statuses)

    dumps_count = 0
    dumps_lbbd_inner_count = 0
    if dumps_path.exists():
        with dumps_path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                dumps_count += 1
                # LBBD inner loop binding 实例: time_limit > 5s 或 instances > 2.
                # boundary precheck 是 5s / 2 instances, LBBD inner 是 30s+ / 100+ instances.
                if (
                    d.get("time_limit_seconds", 0) > 5.0
                    or len(d.get("instances", [])) > 2
                ):
                    dumps_lbbd_inner_count += 1

    return {
        "candidates": candidates,
        "dumps_count": dumps_count,
        "dumps_lbbd_inner_count": dumps_lbbd_inner_count,
    }


def run_short_campaign(minutes: float, env_overrides: dict) -> None:
    """Run main.py for `minutes`, then kill cleanly."""
    log_path = (
        PROJECT_ROOT
        / "data"
        / "telemetry"
        / f"dynamic_review_smoke_{int(time.time())}.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.setdefault("EXACT_BINDING_DUMP_STATE", "1")  # smoke 默认开 dumper
    env.update(env_overrides)

    cmd = [
        str(PROJECT_ROOT / ".venv" / "bin" / "python"),
        "main.py",
        "--campaign-hours",
        "168.0",
        "--parallel-processes",
        "4",
        "--master-seconds",
        "7200",
        "--binding-seconds",
        "7200",
        "--routing-seconds",
        "7200",
        "--resume-campaign",
    ]

    print(f"[smoke] launching: {' '.join(cmd)}")
    print(f"[smoke] env overrides: {env_overrides}")
    print(f"[smoke] log -> {log_path}")

    with log_path.open("w", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=logf,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )

    print(f"[smoke] main PID {proc.pid}, sleeping {minutes} min ...")
    time.sleep(minutes * 60)

    print("[smoke] killing main process group")
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        time.sleep(3)
    except ProcessLookupError:
        pass
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass

    # 兜底清残留 main + worker
    subprocess.run(["pkill", "-9", "-f", "main.py.*campaign-hours"], check=False)
    subprocess.run(["pkill", "-9", "-f", "multiprocessing.spawn"], check=False)
    time.sleep(2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=5.0, help="短跑分钟数")
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        help="额外 env vars, format KEY=VAL (可多次)",
    )
    parser.add_argument(
        "--skip-lbbd-assert",
        action="store_true",
        help="跳过 LBBD inner loop 断言 (用于早期 debug, 不推荐 production gate)",
    )
    args = parser.parse_args()

    env_overrides = {}
    for kv in args.env:
        k, _, v = kv.partition("=")
        env_overrides[k] = v

    print("=" * 60)
    print("Dynamic Review Smoke Test (审查树 L1.5)")
    print("=" * 60)
    print(f"Minutes: {args.minutes}")
    print(f"Env overrides: {env_overrides}")

    print("\n[snapshot before]")
    before = snapshot_state()
    print(json.dumps(before, indent=2, ensure_ascii=False))

    print(f"\n[run] {args.minutes} min short campaign")
    run_short_campaign(args.minutes, env_overrides)

    print("\n[snapshot after]")
    after = snapshot_state()
    print(json.dumps(after, indent=2, ensure_ascii=False))

    print("\n[asserts]")
    failures: list[str] = []

    delta_dumps = after["dumps_count"] - before["dumps_count"]
    print(f"  dumps grew by {delta_dumps}")
    if delta_dumps == 0 and env_overrides.get("EXACT_BINDING_DUMP_STATE") != "0":
        failures.append("dumps_count 没增长 — dumper 没工作 (binding_subproblem.solve() 没被调?)")

    delta_lbbd = (
        after["dumps_lbbd_inner_count"] - before["dumps_lbbd_inner_count"]
    )
    print(f"  LBBD-inner dumps grew by {delta_lbbd}")
    if not args.skip_lbbd_assert and delta_lbbd == 0:
        failures.append(
            "LBBD inner loop binding 实例 0 增长 — outer_search 没真进 LBBD! "
            "boundary precheck 之后被某个 path 卡住 return UNKNOWN."
        )

    if before["candidates"] != after["candidates"]:
        print(f"  candidate state 变化: {before['candidates']} → {after['candidates']}")
    else:
        print(f"  candidate state 不变: {before['candidates']}")
        # 不必然 fail (短跑可能不够时间 prove 新 candidate)

    if failures:
        print("\n" + "=" * 60)
        print("FAIL")
        print("=" * 60)
        for f in failures:
            print(f"  ❌ {f}")
        return 1

    print("\n" + "=" * 60)
    print("PASS — runtime 行为符合 L1.5 预期")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
