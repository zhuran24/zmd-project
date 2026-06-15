"""记忆树同步/检查总闸 (memtree 重构 P1, 2026-06-15)。

单入口, 取代「改 X 类跑脚本 Y」的分流表。当前实现 --check (无副作用观测):
串起所有现有 --check 子脚本 + P0 的 repo<->harness 对账 (memory_harvest --check)。

铁律 (harvest-only): --check **绝不写任何文件、绝不碰 live harness**。
  日后 --harvest 从 live harness 只读收割进 repo; 写 harness 需显式重武器 (本工具不提供)。

子检查分两级:
- BLOCKING (任一失败 -> exit 1, 对应现有 CI gate): repo memory tree gate、doc subject projection。
- WARN (报告不阻断, 对应现有 warn-only / 本机观测语义): authoritative numbers、
  repo->harness sync、living-status slots、harness link health、repo<->harness drift。

用法:
    python cc_context/tools/sync_knowledge.py --check
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "cc_context" / "tools"
SCRIPTS = ROOT / "scripts"

# (label, [脚本路径 + 参数], blocking)
CHECKS: list[tuple[str, list[str], bool]] = [
    ("repo memory tree gate", [str(SCRIPTS / "check_memory_tree.py")], True),
    ("doc subject projection", [str(SCRIPTS / "sync_doc_subjects.py"), "--check"], True),
    ("authoritative numbers", [str(SCRIPTS / "gen_authoritative_numbers.py"), "--check"], False),
    ("repo->harness sync", [str(TOOLS / "sync_memory_to_harness.py"), "--check"], False),
    ("living-status slots", [str(TOOLS / "stamp_living_status.py"), "--check"], False),
    ("harness link health", [str(TOOLS / "check_harness_links.py")], False),
    ("repo<->harness drift", [str(TOOLS / "memory_harvest.py"), "--check"], False),
    # repo P3 gate: 必须 BLOCK (不是 warn) —— 否则工具 exit 1 被总闸吃成 WARN, 复刻原问题
    ("description freshness", [str(TOOLS / "check_description_freshness.py")], True),
    ("MEMORY.md == index_summary (lockfile)", [str(TOOLS / "gen_memory_index.py"), "--check"], True),
]


def run_check(label: str, args: list[str], blocking: bool) -> dict:
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    tail = "\n".join((proc.stdout or "").strip().splitlines()[-4:])
    return {
        "label": label, "blocking": blocking,
        "rc": proc.returncode, "ok": proc.returncode == 0, "tail": tail,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--check", action="store_true",
        help="无副作用观测: 串所有 --check 子检查 (当前唯一模式)",
    )
    ap.parse_args()

    print("=== 记忆树总闸 sync_knowledge --check (无副作用, 不写 harness) ===\n")
    results = [run_check(*c) for c in CHECKS]
    blocking_fail = []
    for r in results:
        tier = "BLOCK" if r["blocking"] else "warn "
        if r["ok"]:
            status = "OK  "
        else:
            status = "FAIL" if r["blocking"] else "WARN"
        print(f"[{tier}] {status}  {r['label']}  (rc={r['rc']})")
        for line in r["tail"].splitlines():
            print(f"        {line}")
        if r["blocking"] and not r["ok"]:
            blocking_fail.append(r["label"])

    print()
    if blocking_fail:
        print(f"BLOCKED: {', '.join(blocking_fail)}")
        return 1
    print("总闸通过 (blocking 全绿; warn 仅供观测, 不阻断)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
