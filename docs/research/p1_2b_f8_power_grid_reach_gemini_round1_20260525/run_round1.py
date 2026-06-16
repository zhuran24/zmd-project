#!/usr/bin/env python3
"""Phase 1.2 P1.2B-F8 power_grid_reach Gemini round 1 cross-check.

Per memory [[gemini-review-algorithm-math]] v4 protocol — real data paths
inline, armor strict, 反 GO ritual.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.request


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


SRC_FILES = [
    "src/cuts/helpers/power_cover.py",
    "src/cuts/helpers/power_network.py",
    "src/cuts/helpers/ghost_geometry.py",
    "src/cuts/families/power_grid_reach.py",
    "src/cuts/oracles/power_grid_reach_oracle.py",
]

SPEC_FILES = [
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md",
]


PROMPT = """你是 power network / connectivity cut / geometric soundness / Liang-Barsky line-clip / BFS reachability / soundness 审查员。Endfield 工业规划求解器 Phase 1.2 P1.2B-F8 **Round 1** cross-check (commit `4be1b60`).

# 任务背景

70x70 grid certified-exact LBBD, F8 是 9 cut family 之一: 拦 "facility 候选 pole 集合非空但 pole-jump BFS 从 protocol_core 不可达任何 candidate pole → INFEASIBLE". 跟 F7 互斥 trigger (F7=CoverSet 空, F8=CoverSet 非空但 disconnect).

# Design merger from 5 parallel opus subagents

- correctness-paranoid: **2 critical finding**
  1. `pole_to_pole_jump_radius` canonical 无 field (只有 `power_coverage_radius=5` 是 pole→facility, semantically 不同) — caller-supplied 通过 cert active_assumptions audit trail
  2. protocol_core anchor **state-dependent** (master 从 7200-pose pool 选), 不固定; caller (Phase 1.5+ wiring) 必须传; Phase 1.2 fixture 显式传
- throughput: `build_power_network` ~1.5s/call + cert.power_graph_b64 ~4MB/cut 警告 → 全删 graph snapshot, evaluator 走 scope-binding monotone-preserved invariant
- adversarial: pole 2×2 vs 1×1 spec drift (canonical_rules `power_pole.dimensions={w:2,h:2}` 实证), pole_shape_canonical = `"2x2_rigid"` lock + strict regex
- integration: post-master plug + F7 first → F8 only when F7 returns nothing (oracle generator 内 early-exit logic)
- minimum viable: O(1) evaluator + 7-phase validator + 3 file structure

# Phase 1.2 single-case scope (per minimum viable)

- cert_kind 单值: `"power_pole_bfs_disconnect_ghost"`
- cell_owner causation (multi-literal) + `"exterior_blocks_jump"` variant defer Phase 1.5+
- Generator default-disabled (`EXACT_F8_GENERATOR_ENABLED=0`, 跟 F6/F7 pattern)
- Validator phase 7 用 ghost-only power network 重算验单 cause sound (cell_owner 不是真 cause)
- Cert 不存 graph snapshot — validator independently rebuilds (跟 F2/F4 trust boundary pattern一致)
- Evaluator 走 O(1) scope drift guard (ghost_rect_id + exterior_blocks_hash); 单调保持 (free_cells 单调缩 → power connectivity 单调减弱)

# Round 1 任务 (v4 加严协议 — 不接受 GO ritual)

1. **Spec-data gap focus** — 真数据 inline 在下方. 实施 src 接合真数据时哪步 crash / FN / FP?
2. **Liang-Barsky AABB intersection 数学严格性** (`src/cuts/helpers/ghost_geometry.py`): 边角 case (parallel to axis / colinear with edge / endpoint exactly on edge) 是否 sound?
3. **F7 ↔ F8 mutual exclusion**: oracle 早退 logic 真的不漏吗? 边界 (CoverSet ghost-only 跟 full 不同时) 怎么走?
4. **scope-binding monotone preservation (O(1) evaluator)**: state.cell_owner 增多, power connectivity disconnect 真的单调保持吗? 边界 case 找一下 (free_cells 单调缩但 power_graph 拓扑非单调?)
5. **`pole_jump_radius` caller-supplied + cert active_assumptions audit**: caller 给错 radius 时, validator 怎么 catch? validator 是否独立 source-of-truth 校验?
6. **Generator default-disabled (Phase 1.5+ wiring 推迟)**: 跟 F6/F7 同 pattern. Phase 1.2 fixture/test 路径如何 trigger?
7. **Cell_owner phase 7 (ghost-only power network 重算)**: validator phase 7 用 ghost-only graph 验单 literal sound. 跟 F7 同 pattern. 真 sound 吗? 边界 (ghost 跟 cell_owner 重叠 cell)?

## Armor 规则

- 不接受 "looks fine / 完美 / very solid" vague hyperbole
- GO verdict 必先列 3 死法 + disprove (cite file:line)
- critical claim 必 cite file:line 或 spec §X 或 literature
- 找不到 critical 也必列 3 high-risk hypothesis disproved (file:line)

## 关键 finding 我自己已经预察到

Gap A: pole-jump radius **canonical_rules 无 field** (只有 `power_coverage_radius=5` 是 pole→facility cell, 跟 pole→pole jump 不是同概念). 实施 caller-supplied 通过 oracle `pole_jump_radius` 参数 + cert `pole_jump_radius` 字段. Phase 1.5+ 加 canonical 字段. 现在 design 是 sound 还是埋雷? (validator 怎么 catch 错 radius?)

Gap B: protocol_core **不固定** — canonical_rules.facility_templates.protocol_core 是 9×9 facility, 有 7200 candidate pose. master 选哪 pose 是 master_solution state. Phase 1.2 callers 必须传 anchor cell. 当 master 改 protocol_core pose 时, 现有 F8 cut 是否 stale (cut 是 ghost-bound 但隐含 protocol_core_cell)?

Gap C: O(1) evaluator 假设 "ghost + exterior 不变 (scope drift guard) → power disconnect 单调保持". 真的吗? state.cell_owner 增多 → free_cells 缩 → pole candidate set 缩 → 某些 jump edge 失效 (`build_power_network` 在 free_cells 减 cell 时不会 add edge)→ disconnect 单调保持. 但 `protocol_core_cell` 若不在 cell_owner 内 (master 已选), evaluator 不 rebuild graph 是否漏 catch protocol_core 移走的 case?

Gap D: Liang-Barsky `segment_intersects_aabb` 的 endpoint on AABB edge 算 intersect 吗? F8 spec §5a 写"含边" — 但 endpoint 本身就是 pole 中心, pole 占 2×2 区域; 若 pole 中心 exactly 在 ghost edge, 应视为 jump 不 block 还是 block?

## Format (严格不要 think-out-loud)

```
## Round 1 Verdict
GO | GO_WITH_MINOR | CONCERN | NOT_GO (一行)

## Verify Gap A/B/C/D
- Gap A (pole_jump_radius caller-supplied): CONFIRMED / PARTIAL / REJECTED — 详释
- Gap B (protocol_core state-dependent): CONFIRMED / PARTIAL / REJECTED — 详释
- Gap C (O(1) evaluator monotonicity): CONFIRMED / PARTIAL / REJECTED — 详释 + 边界 case
- Gap D (Liang-Barsky endpoint on edge): CONFIRMED / PARTIAL / REJECTED — 详释 + 推荐

## Round 1 New findings (≥3, 任何 severity)

### Finding 1: [SEVERITY] file:line — title
≤ 200 字.

### Finding 2: ...
### Finding 3: ...

## Sanity (如果 GO, 至少 3 disproved hypothesis 含 file:line)

## 建议 Round 2 重点 / Phase 1.5+ defer
```

"""


def build_doc_paths_section() -> str:
    s = ["# DOC_PATHS: 真数据 schema inline (v4 协议硬要求)\n\n"]

    rules = json.loads((ROOT / "rules/canonical_rules.json").read_text())
    templates = rules.get("facility_templates", {})
    s.append("## rules/canonical_rules.json — facility_templates (full)\n")
    s.append("```json\n")
    s.append(json.dumps(templates, indent=2, ensure_ascii=False))
    s.append("\n```\n\n")

    # Show that there's NO pole_to_pole jump radius field at top level
    s.append("## rules/canonical_rules.json — top-level keys (for Gap A audit)\n")
    s.append("```\n")
    s.append("\n".join(sorted(rules.keys())))
    s.append("\n```\n\n")

    me = json.loads((ROOT / "data/preprocessed/mandatory_exact_instances.json").read_text())
    s.append("## data/preprocessed/mandatory_exact_instances.json — group counts\n")
    if isinstance(me, list):
        types_count: dict[str, int] = {}
        for entry in me:
            if isinstance(entry, dict):
                t = entry.get("facility_type") or entry.get("group_id")
                if t:
                    types_count[t] = types_count.get(t, 0) + 1
        s.append(f"Total {len(me)} instance entries. Powered counts:\n")
        for ft, tpl in templates.items():
            if tpl.get("needs_power") is True:
                s.append(f"- {ft}: {types_count.get(ft, 0)} instances\n")
        s.append(f"- protocol_core: {types_count.get('protocol_core', 0)} instances (9×9)\n")
        s.append("\n")

    # Show candidate_placements structure for protocol_core pool size
    cp = json.loads((ROOT / "data/preprocessed/candidate_placements.json").read_text())
    s.append("## data/preprocessed/candidate_placements.json — pool sizes (for Gap B audit)\n")
    pools = cp.get("facility_pools", {}) if isinstance(cp, dict) else {}
    s.append("```\n")
    for ft in sorted(pools.keys()):
        pool = pools[ft]
        if isinstance(pool, list):
            s.append(f"{ft}: {len(pool)} poses\n")
    s.append("```\n\n")

    # Sample one pose entry from protocol_core (if exists)
    if isinstance(pools.get("protocol_core"), list) and pools["protocol_core"]:
        s.append("## protocol_core pool sample entry (first item)\n```json\n")
        s.append(json.dumps(pools["protocol_core"][0], indent=2, ensure_ascii=False))
        s.append("\n```\n\n")

    s.append("## BState fields F8 reads\n")
    s.append("- state.ghost_rect / state.ghost_cells / state.exterior_blocks\n")
    s.append("- state.cell_owner: Dict[Cell, OwnerId]\n")
    s.append("- state.groups[gid]: GroupState (group_id, demand, pose_domain, selected_poses)\n")
    s.append("- state.instance_to_facility_type: Dict[GroupId, str]\n")
    s.append("- state.facility_templates: Dict[str, Dict] (alias canonical_rules.facility_templates)\n")
    s.append("- state.candidate_placements: Dict (mirrors data/preprocessed/candidate_placements.json)\n\n")

    return "".join(s)


def build_src_section() -> str:
    s = ["# F8 src (full content inline)\n\n"]
    for rel in SRC_FILES:
        s.append(f"### FILE: {rel}\n```python\n")
        s.append(read(rel))
        s.append("\n```\n\n")
    return "".join(s)


def build_spec_section() -> str:
    s = ["# F8 spec (cut_family_specs/08_power_grid_reach.md v1.1)\n\n"]
    for rel in SPEC_FILES:
        s.append(read(rel))
        s.append("\n\n")
    return "".join(s)


def main() -> int:
    key = os.environ.get("KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        print("ERROR: set KEY=<api_key>.", file=sys.stderr)
        return 2

    prompt_text = (
        PROMPT
        + build_spec_section()
        + build_doc_paths_section()
        + build_src_section()
        + "\n\n# 完. 严格 format, 不 think-out-loud.\n"
    )
    (HERE / "prompt.txt").write_text(prompt_text, encoding="utf-8")
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "temperature": 0.3,
            "topP": 0.95,
            "maxOutputTokens": 32768,
        },
    }
    (HERE / "prompt.json").write_text(json.dumps(payload), encoding="utf-8")

    print(f"prompt length: {len(prompt_text)} chars")
    print("calling Gemini ...")
    t0 = time.monotonic()
    model = os.environ.get("GEMINI_MODEL", "gemini-3.1-pro-preview")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            body = r.read().decode("utf-8")
    except Exception as e:
        print(f"API call failed: {e!r}", file=sys.stderr)
        return 1
    print(f"Gemini responded in {time.monotonic() - t0:.1f}s")

    (HERE / "gemini_response_raw.json").write_text(body, encoding="utf-8")
    parsed = json.loads(body)
    try:
        verdict_text = parsed["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        print("Failed to extract text:", parsed, file=sys.stderr)
        return 1
    (HERE / "gemini_response.md").write_text(verdict_text, encoding="utf-8")
    print(f"Response written ({len(verdict_text)} chars).")
    print("---")
    print(verdict_text[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
