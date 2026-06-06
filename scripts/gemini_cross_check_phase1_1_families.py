#!/usr/bin/env python3
"""Round 29 Gemini cross-check — Phase 1.1 整 4 family src 跟 spec 一致.

Phase 1.1 P1.5-P1.8 全 land:
- P1.5 F1 region_capacity production (combinatorial oracle + validator + evaluate)
- P1.6 F2 cutset (validator + oracle stub)
- P1.7 F3 port_exposure (literal-based + multiset eval, 修 round 27 B3)
- P1.8 F4 component_reach (validator + BFS + oracle stub)

任务:
1. 4 family validator 跟 spec v1.0/1.1/1.2 严格一致?
2. multiset eval (lifecycle.evaluate_literal_multiset) 跟 state_machine_v2 §5
   一致 (round 27 B3)?
3. literal cut + post_init schema enforce 没漏 (F3 cut.literals tuple ≥ 2)?
4. FAMILY_VALIDATORS dispatch 4 family register 对?
5. 3 个 oracle stub (F2/F3/F4) defer 措辞 + Phase 1.5+ TODO 清晰?

Output: /home/zhuran24/linwin_share/gemini_round_29_phase1_1_families_response.md
"""
from __future__ import annotations

import os
import json
import time
import urllib.request
from pathlib import Path

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
if not API_KEY:
    raise SystemExit("Set GEMINI_API_KEY to run this Gemini cross-check script.")
MODEL = "gemini-3.1-pro-preview"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

REPO = Path("/home/zhuran24/claude-pj/zmd")
SHARE = Path("/home/zhuran24/linwin_share")

DOC_PATHS = [
    # Spec layer
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md",
    "docs/research/p3_b_design_v2_20260521/state_machine_v2.md",
    "docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md",
    # src 实施 Phase 1.1 整 4 family
    "src/cuts/lifecycle.py",
    "src/cuts/families/region_capacity.py",
    "src/cuts/families/cutset.py",
    "src/cuts/families/port_exposure.py",
    "src/cuts/families/component_reach.py",
    "src/cuts/oracles/region_capacity_oracle.py",
    "src/cuts/oracles/cutset_oracle.py",
    "src/cuts/oracles/port_exposure_oracle.py",
    "src/cuts/oracles/component_reach_oracle.py",
    "src/cuts/replay.py",
    # 上一轮 verdict (round 28)
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_28_phase1_0_framework_go.md",
]


PROMPT = """\
# Round 29 Gemini cross-check — Phase 1.1 整 4 family src

## 背景

Round 28 给 Phase 1.0 framework "GO + 4 P1.5+ 盲区" (#1#2 hardened in src,
#3#4 defer P1.22/P1.14).

Phase 1.1 P1.5-P1.8 (4 family) 全 land single session:
- P1.5 (871b515): F1 region_capacity production (combinatorial oracle +
  validator with 4 region kind decode support, 但 generator 只 enumerate
  left/bottom baseline; interior_rect + ghost_complement defer Phase 1.5+).
- P1.6 (8f7cabb): F2 cutset (validator + stub oracle; patch_routing_core
  max-flow defer Phase 1.5+).
- P1.7 (1ed983b): F3 port_exposure (literal-based + ``evaluate_literal_multiset``
  generic helper in lifecycle.py + multiset 子集判 per state_machine_v2 §5 +
  round 27 finding B3 修).
- P1.8 (46a9b80): F4 component_reach (validator + BFS helper + stub oracle).

Tests: src/tests/cuts/ 137/137 PASS (+47 new from P1.5-P1.8).
ruff + mypy: all pass.

## 任务

任务 A: 验 4 family src 跟 spec 严格一致

1. **P1.5 F1 region_capacity**:
   - ``validate_region_capacity`` 5 步 check (cap_R / placement_rule / cells_per_pose
     source-of-truth / demand_R / witness) 跟 spec §7 v1.1 一致?
   - ``generate_region_capacity_cuts`` combinatorial path: 4 region kind 中只
     enumerate left/bottom baseline OK 吗? (interior_rect / ghost_complement
     defer Phase 1.5+ per spec §10 open question #2 — 合理?)
   - v1.2 GHOST_AGNOSTIC dispatch (ghost ∩ R == ∅ → AGNOSTIC) 正确?

2. **P1.6 F2 cutset**:
   - ``validate_cutset`` 3 步 check (partition disjoint / cut_size recompute /
     witness demand>cut) 跟 spec §7 一致?
   - ``_free_cells(state)`` = all - ghost - cell_owner.keys() 实施跟
     state_machine_v2 §3 I3 一致?
   - oracle stub defer 措辞 + Phase 1.5+ TODO 清晰?

3. **P1.7 F3 port_exposure + multiset eval**:
   - ``evaluate_literal_multiset`` (lifecycle.py) 跟 state_machine_v2 §5
     contract 严格一致? Counter (multiset) 子集判 + 跨 slot anonymity?
   - ``validate_port_exposure`` 4 步 check (front_cell math / blocking_facility
     at cell_owner / port spec / literals schema)?
   - **literal cut + post_init schema enforce**: cut.literals ≥ 2 (cut spec
     F3 期望 2 literals) — 当前 lifecycle.__post_init__ 只 enforce ≥ 1 (literal
     XOR geometric). F3 spec 期望 2 literals 但 schema 允许 1, 是否 spec gap?

4. **P1.8 F4 component_reach**:
   - ``validate_component_reach`` 3 步 check (disjoint / membership / recompute
     BFS still disconnect) 跟 spec §7 v1.1 一致?
   - Gemini round 16 A1 修 (geometric 不校验 blocking_facility pose ID) 正确实施?
   - BFS 4-conn helper 跟 d2_separator BFS 一致 (Phase 1.5+ wrap 时无 surprise)?

5. **FAMILY_VALIDATORS dispatch**:
   - 4 family register 全, register order 一致 (region_capacity / cutset /
     port_exposure / component_reach)?
   - replay_cut Step 7 dispatch 4 family 全 wire?

## 任务 B: 找 Phase 1.2 P1.11-P1.15 实施盲区

Phase 1.1 4 family land 后, 找 Phase 1.2 F5-F9 实施 (P1.11-P1.15) 时盲区:

如:
- F5 pattern_nogood (literal): 跟 F3 同 pattern, multiset eval helper 共用. 但
  L16 deletion minimizer + QuickXplain 还没 wire. 实施时 minimize_audit field
  跟 cert hash 怎么协调?
- F6 shape_packing_hall (geometric): 复用 baseline_partition helper (P1.4 已
  land). 但 Hall 条件 (set-packing necessary cond) 怎么 cert? cert schema 在
  spec §3 写明?
- F7 power_hitting_set (literal, causation split): 跟 F3 类似 但 multi-literal
  ghost cause + cell_owner cause sub-kind. multiset eval 还 sound?
- F8 power_grid_reach (geometric): 复用 power_network helper (P1.4) + bfs_component.
  Phase 1.4 P1.14 reminder #4 (bfs_component Set 序列化排序) 还 valid?
- F9 density_envelope (geometric, area-based v1.5): paradigm 降级版怎么 wire?

## 任务 C: Phase 1.1 verdict

如 4 family 全跟 spec 一致 + 137 test 覆盖够 + 没找到 P1.9+ 实施盲区 →
"Phase 1.1 GO, 继续 Phase 1.2 P1.11+". 如有 finding → 列详细.

## 输出格式

按 3 段 A/B/C. 中文优先. 找不到 finding 写 "无 finding" 不要硬找.
"""


def fetch_doc(path: str) -> str:
    p = REPO / path
    if not p.exists():
        return f"[MISSING: {path}]"
    return p.read_text(encoding="utf-8")


def build_prompt() -> str:
    parts = [PROMPT, "\n\n## Reference Materials\n"]
    for dp in DOC_PATHS:
        content = fetch_doc(dp)
        parts.append(f"\n\n### --- {dp} ---\n\n{content}\n")
    return "".join(parts)


def call_gemini(prompt: str) -> dict:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 16384},
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


def extract_text(resp: dict) -> str:
    try:
        return resp["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        return f"[parse error: {e}]\n\n{json.dumps(resp, ensure_ascii=False, indent=2)[:4000]}"


def main() -> int:
    SHARE.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt()
    print(f"Prompt size: {len(prompt):,} bytes, ~{len(prompt)//4:,} tokens (est)")

    t0 = time.monotonic()
    try:
        resp = call_gemini(prompt)
    except Exception as e:
        print(f"FAIL: {e}")
        return 1
    elapsed = time.monotonic() - t0
    print(f"Gemini response in {elapsed:.1f}s")

    text = extract_text(resp)
    out_path = SHARE / "gemini_round_29_phase1_1_families_response.md"
    out_path.write_text(text, encoding="utf-8")
    print(f"Response written: {out_path} ({len(text):,} bytes)")
    print("\n---\n")
    print(text[:6000])
    if len(text) > 6000:
        print(f"\n... [{len(text)-6000} more bytes in file]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
