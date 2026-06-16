#!/usr/bin/env python3
"""AI cuts 训练数据 inspector — 168h 闲时 query 工具.

scan data/solutions/cuts_*.json (per-candidate cuts) + data/telemetry/binding_dumps.jsonl
统计 cuts 数量, 按 candidate 分布, cuts 类型, growth trajectory.

用途:
- 知道当前 168h `-p 1` 长跑攒到多少训练数据
- AI cuts model train 之前数据是否足够 (>1000 cuts/candidate 算够)
- 看哪些 candidate 数据多 / 少 (调 frontier policy 时参考)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _summarize_cuts() -> dict:
    cuts_dir = PROJECT_ROOT / "data" / "solutions"
    files = sorted(cuts_dir.glob("cuts_*.json"))
    by_candidate: dict[str, dict] = {}
    total_cuts = 0
    cut_types: Counter = Counter()
    conflict_set_sizes: list[int] = []

    for f in files:
        candidate = f.stem.removeprefix("cuts_")
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        cuts_list = data if isinstance(data, list) else data.get("cuts", [])
        if not isinstance(cuts_list, list):
            continue
        n = len(cuts_list)
        total_cuts += n
        for cut in cuts_list:
            if not isinstance(cut, dict):
                continue
            cut_types[str(cut.get("cut_type", "unknown"))] += 1
            cs = cut.get("conflict_set", {})
            if isinstance(cs, dict):
                conflict_set_sizes.append(len(cs))
        by_candidate[candidate] = {
            "cut_count": n,
            "file_size_kb": round(f.stat().st_size / 1024, 1),
        }

    return {
        "total_cuts": total_cuts,
        "candidates_with_cuts": len([c for c in by_candidate.values() if c["cut_count"] > 0]),
        "candidates_total": len(by_candidate),
        "by_candidate": by_candidate,
        "cut_types": dict(cut_types),
        "avg_conflict_set_size": (
            round(sum(conflict_set_sizes) / len(conflict_set_sizes), 1)
            if conflict_set_sizes else 0
        ),
        "max_conflict_set_size": max(conflict_set_sizes) if conflict_set_sizes else 0,
    }


def _summarize_binding_dumps() -> dict:
    path = PROJECT_ROOT / "data" / "telemetry" / "binding_dumps.jsonl"
    if not path.exists():
        return {"available": False}
    total = 0
    statuses: Counter = Counter()
    candidates: Counter = Counter()
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                total += 1
                statuses[str(rec.get("status", "unknown"))] += 1
                ck = rec.get("candidate_key") or rec.get("ghost_rect")
                if ck:
                    candidates[str(ck)] += 1
    except OSError:
        return {"available": False, "error": "read failed"}
    return {
        "available": True,
        "total_records": total,
        "statuses": dict(statuses),
        "candidates_with_dumps": len(candidates),
        "top_candidates": dict(candidates.most_common(5)),
    }


def _summarize_campaign_state() -> dict:
    path = PROJECT_ROOT / "data" / "checkpoints" / "exact_campaign_state.json"
    if not path.exists():
        return {"available": False}
    state = json.loads(path.read_text())
    candidates = state.get("candidates", {})
    by_status: Counter = Counter()
    for v in candidates.values():
        by_status[str(v.get("status", "unknown"))] += 1
    return {
        "available": True,
        "total_candidates": len(candidates),
        "by_status": dict(by_status),
        "declare_mode": state.get("declare_mode"),
        "last_stop_reason": (state.get("last_stop_reason") or {}).get("reason"),
        "updated_at": state.get("updated_at"),
    }


def main() -> int:
    cuts = _summarize_cuts()
    binding = _summarize_binding_dumps()
    state = _summarize_campaign_state()

    print("=" * 60)
    print("AI Cuts 训练数据 + 168h Campaign 进度")
    print("=" * 60)

    print("\n[Campaign 状态]")
    if state.get("available"):
        print(f"  total candidates: {state['total_candidates']}")
        for st, n in sorted(state["by_status"].items()):
            print(f"    {st}: {n}")
        print(f"  declare_mode: {state.get('declare_mode')}")
        print(f"  last_stop_reason: {state.get('last_stop_reason')}")
        print(f"  state updated_at: {state.get('updated_at')}")

    print("\n[AI Cuts 训练数据]")
    print(f"  total cuts: {cuts['total_cuts']}")
    print(f"  candidates with cuts: {cuts['candidates_with_cuts']} / {cuts['candidates_total']}")
    print(f"  cut types: {cuts['cut_types']}")
    print(f"  avg conflict-set size: {cuts['avg_conflict_set_size']}")
    print(f"  max conflict-set size: {cuts['max_conflict_set_size']}")
    print("  per candidate cut count (top 10):")
    top = sorted(cuts["by_candidate"].items(), key=lambda x: -x[1]["cut_count"])[:10]
    for cand, info in top:
        print(f"    {cand}: {info['cut_count']} cuts ({info['file_size_kb']} KB)")

    print("\n[Binding Subproblem Dumps]")
    if binding.get("available"):
        print(f"  total records: {binding['total_records']}")
        print(f"  statuses: {binding['statuses']}")
        print(f"  candidates with dumps: {binding['candidates_with_dumps']}")
        print(f"  top 5 candidates: {binding['top_candidates']}")
    else:
        print("  not available")

    print("\n[AI Train 数据足够性 estimate]")
    if cuts["total_cuts"] >= 5000:
        print(f"  ✓ 数据 ≥ 5000 cuts → AI sidecar 训练数据**足够**")
    elif cuts["total_cuts"] >= 1000:
        print(f"  ~ 数据 1000-5000 cuts → AI sidecar 训练**勉强**, 偏好继续攒")
    else:
        print(f"  ✗ 数据 < 1000 cuts → AI sidecar 训练**不够**, 需更多 168h round")

    return 0


if __name__ == "__main__":
    sys.exit(main())
