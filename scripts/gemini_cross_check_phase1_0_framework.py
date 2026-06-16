#!/usr/bin/env python3
"""Round 28 Gemini cross-check — Phase 1.0 framework 整 4 件 src 跟 spec 一致.

Per /goal v3: Phase 1.0 framework 4 件 (P1.1 lifecycle / P1.2 store / P1.3 replay /
P1.4 helpers + assumptions) 全 land. cross-check 整 framework src 是否跟
v3.2.2 spec + family_spec_06/08 严格一致.

任务:
1. CutStore 6 维 watcher + on_ghost_rect_changed dispatch 跟 cut_lifecycle_v2 §7-§8 一致?
2. replay_cut 6 步 verify + post-attach validation + store side-effect 对齐 §4 + §8?
3. ASSUMPTION_VERIFIERS dispatch 移到 assumptions module 后 lifecycle.assumption_holds
   delegate 通对吗 (lazy import 防循环)?
4. ghost_geometry Liang-Barsky AABB 实施 sound (Gemini round 16 B1 critical 修)?
   - corner-touch / axis-aligned-edge / 退化 segment 都 cover?
5. baseline_partition 仅依赖 ghost ∪ exterior (v1.1 finding #2 lock)?
6. power_network 用 segment_intersects_aabb sound (跟 ghost_geometry 一致)?

Output: /home/zhuran24/linwin_share/gemini_round_28_phase1_0_framework_response.md
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
    # Spec layer (post round 27 GO, 不重新 cross-check spec — 仅做参考)
    "docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/06_shape_packing_hall.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md",
    "docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md",
    # src 实施 Phase 1.0 framework 整 4 件
    "src/cuts/lifecycle.py",
    "src/cuts/store.py",
    "src/cuts/replay.py",
    "src/cuts/assumptions/verifiers.py",
    "src/cuts/helpers/ghost_geometry.py",
    "src/cuts/helpers/baseline_partition.py",
    "src/cuts/helpers/power_network.py",
    # round 27 verdict (上次 P1.1 verify, 给 B1/B2/B3 finding — 这次验是否修)
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_27_p1_1_src_verify.md",
]


PROMPT = """\
# Round 28 Gemini cross-check — Phase 1.0 framework 整 4 件 src

## 背景

Round 27 给 P1.1 (lifecycle.py) "GO + 3 个 Phase 1.2-1.7 实施盲区 (B1/B2/B3)".
之后:
- P1.2 (commit fe77a0c): src/cuts/store.py — CutStore + 6 维 watcher + on_ghost_rect_changed
- P1.3 (commit 224349e): src/cuts/replay.py — store-aware replay_cut + regression_sweep
- P1.4 (1/4) (commit a80a4d6): assumption verifier 真实施 — BState.canonical_rules
  field + assumptions/verifiers.py 独立 module + lookup_verifier/register_verifier.
  **修 Round 27 B1 finding** (ASSUMPTION_VERIFIERS 真读 canonical_rules).
- P1.4 (2-4/4) (commit cdb0531): helpers ghost_geometry + baseline_partition +
  power_network — Family 8 Liang-Barsky + Family 6 partition v1.1 fix.

Tests: src/tests/cuts/ 全 89/89 PASS:
- 17 lifecycle (schema + 9-step + v3.2.2 dispatch)
- 14 store (6 watcher + state machine + on_ghost_rect_changed)
- 8 replay (ATTACH/HOLD/QUARANTINE + post-attach validation + regression_sweep)
- 15 assumptions (verifier real impl + fail-closed)
- 12 ghost_geometry (Liang-Barsky + corner-touch + axis-aligned-edge)
- 11 baseline_partition (v1.1 不依赖 cell_owner)
- 12 power_network (jump graph + bfs_component)

ruff + mypy: all pass.

## 任务

任务 A: 验 P1.2 / P1.3 / P1.4 src 跟 v3.2.2 spec 严格一致

1. **P1.2 src/cuts/store.py CutStore** 跟 cut_lifecycle_v2 §7-§8 一致?
   - 6 维 watcher (by_cell/by_group/by_pose/by_commodity/by_region/by_ghost) 全有?
   - GHOST_AGNOSTIC cut 不入 by_ghost_watcher (§7 footnote)?
   - quarantine 是 terminal state, 不可再 hold (§8 state machine)?
   - on_ghost_rect_changed dispatch 4 个 branch (ATTACH/HOLD/QUARANTINE/skip-already-quarantined) 对吗?

2. **P1.3 src/cuts/replay.py replay_cut** 跟 §4 一致?
   - 6 步 verify (调 lifecycle.step_6_attach_scope_check) + 调 store API side-effect?
   - post-attach validation (Step 7) family-dispatched (Phase 1.0 仅 F1 wired)?
   - fail-closed: unsound/timeout/schema_err → QUARANTINE (PROJECT_LOCK §3A)?

3. **P1.4 (1/4) assumptions/verifiers.py** 修 Round 27 B1 finding 对吗?
   - BState.canonical_rules field added — readonly ref to parsed rules
   - assumption_holds delegate 到 lookup_verifier (lazy import 防循环)?
   - verify_placement_rule + verify_boundary_saturation fail-closed if rules None?

4. **P1.4 (2-4/4) helpers** 算法 sound 跟 spec 一致?
   - **ghost_geometry.py Liang-Barsky**: corner-touch / axis-aligned-edge / 退化
     segment / 端点 inside 等 edge case 都 cover? (Gemini round 16 B1 critical bug 修)
   - **baseline_partition.py v1.1**: 仅依赖 ghost ∪ exterior, **不**依赖 cell_owner
     (Gemini round 14 finding #2)?
   - **power_network.py**: edge canonical (no dup) + 调 segment_intersects_aabb
     sound, bfs_component correct?

## 任务 B: 找新 finding

Phase 1.0 framework 4 件全 land 后, 找 P1.5+ family validator 实施时的盲区
(non-critical 工程提示):

如:
- replay.py FAMILY_VALIDATORS dispatch 默认 None 跳过, Phase 1.5+ wired 漏 family 怎么 catch?
- store.py 6 watcher 的内存 fragmentation 风险 (Phase 1.4 ramp 168h)?
- assumptions/verifiers.py register_verifier 没 namespace, 不同 family 注册同名 key 怎么办?
- helpers 的 边界 grid 坐标 OFF-BY-ONE? (cell_aabb_from_rect 用 x+h 不是 x+h-1, 是否漏)

任务 C: Phase 1.0 framework verdict

如 4 件 src 全跟 spec 一致 + 89 test 覆盖够 + 没找到 P1.5+ 实施盲区 → 写
"Phase 1.0 GO, 继续 Phase 1.1 P1.5 (Family 1)". 如有 finding → 列详细.

## 输出格式

按 3 段 A/B/C 输出. 中文优先. 找不到 finding 写 "无 finding" 不要硬找凑数
(round 27 给的 B1/B2/B3 都 valid finding, 这次扫剩下的).
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
    out_path = SHARE / "gemini_round_28_phase1_0_framework_response.md"
    out_path.write_text(text, encoding="utf-8")
    print(f"Response written: {out_path} ({len(text):,} bytes)")
    print("\n---\n")
    print(text[:5000])
    if len(text) > 5000:
        print(f"\n... [{len(text)-5000} more bytes in file]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
