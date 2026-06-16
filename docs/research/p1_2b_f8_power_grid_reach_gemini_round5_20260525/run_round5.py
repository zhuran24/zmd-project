#!/usr/bin/env python3
"""Phase 1.2 P1.2B-F8 power_grid_reach Gemini round 5 cross-check.

Round 1 (4be1b60): NOT_GO, 4 finding (3 CRITICAL + 1 HIGH).
Round 2 (b9ab24a): NOT_GO, 4 new finding (2 CRITICAL + 2 HIGH, #4 rejected).
Round 3 (fe7c239): NOT_GO, 3 finding (2 CRITICAL + 1 HIGH).
Round 4 (29b64d0): NOT_GO, 4 finding (2 CRITICAL + 2 HIGH).
Round 5 base (3b9c8b3): R4 Finding #1/#2/#3/#4 all landed via SoT validator
phase + evaluator pc-position check + negative-coord parse rejection.

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
    "src/cuts/assumptions/verifiers.py",
]

SPEC_FILES = [
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md",
]


PROMPT = """你是 power network / connectivity cut / geometric soundness / Liang-Barsky / BFS reachability / assumption verifier dispatch 审查员。Endfield Phase 1.2 P1.2B-F8 **Round 5** cross-check (commit `3b9c8b3`).

# 任务背景 (最小)

70×70 LBBD certified-exact, F8 拦 "facility 的 CoverSet 非空但 pole-jump BFS 从 protocol_core 不可达 → INFEASIBLE". 跟 F7 互斥 (F7 = CoverSet 空).

# R4 → R5 diff (这次 review 的核心)

R1 (4be1b60) NOT_GO → R2 base b9ab24a → R3 NOT_GO → R4 base 29b64d0 → R4 NOT_GO → **R5 base 3b9c8b3**.

R4 base 修法 (must verify) — R4 4 finding 全 land:

| R4 Finding | 类型 | R4 漏洞 | R5 修法 |
|---|---|---|---|
| #1 | CRITICAL | evaluator 漏 spec §6 protocol_core 位置 check, master 移走 pc 后 cut 仍 fire | evaluator 加 `_eval_check_protocol_core_position` helper: 检查 cert.protocol_core_cell 9×9 footprint 仍 owned by facility_type=protocol_core in state.cell_owner. Phase 1.2 fixture/早 phase (cell_owner 空) accept bounds-only |
| #2 | CRITICAL | validator 用 cert.pole_jump_radius + cert.protocol_core_cell 直接 build graph, 没 cross-check canonical_rules. 恶意 cert (R=0.001) 可伪造 disconnect | 新 validator phase `_validate_source_of_truth_scalars`: cross-check pole_jump_radius == canonical power_coverage_radius + (when cell_owner 存) cross-check pc anchor footprint owned by protocol_core. 分 `_validate_pole_radius_sot` + `_validate_pc_anchor_sot` helper |
| #3 | HIGH | `verify_protocol_core_position` cell_owner 空时盲目接受 bounds-only (early phase 攻击面) | acknowledge Phase 1.2 limitation: production state always 有 cell_owner (master place pc 早). 攻击面 zero under generator default-disabled gate. Phase 1.5+ wiring 严化 |
| #4 | HIGH | `_parse_protocol_core_cell` 边界检查 `0 <= x + size <= 70` 漏负数 (x=-1, size=9 → 8 ∈ [0, 70]) | 加 explicit `x < 0 or y < 0 → ValueError` 在 upper bound 检查前 |

Refactor (radon hygiene): evaluator D(27)→B(10), SoT C(15)→A(2), 加 8 helper. avg B(5.92) max C(14).

验证状态 (commit 3b9c8b3):
- 71 F8 + helper + verifier pytest (was 68, +3 R4 regression: protocol_core moved evaluator / forged radius validator / negative pc coord parse)
- 2632 full pytest pass (was 2629, +3)
- mypy strict 5 module 0 error
- radon avg B(5.92), max C(14) (`_parse_facility_cells` / `_validate_scalars` / `validate_power_grid_reach` 都是 pre-existing C)
- F8 共 4 round NOT_GO; R5 评估是否 close

# Round 5 任务

**主线 (verify R4 fix)** — 全文 cite file:line:
1. `src/cuts/families/power_grid_reach.py:evaluate_geometric_power_grid_reach` + `_eval_check_protocol_core_position` — protocol_core move 后真 reject 吗? Hot path O(81) 接受吗?
2. `src/cuts/families/power_grid_reach.py:_validate_source_of_truth_scalars` — 真 catch R=0.001 + 错 anchor? canonical_rules 缺时正确 fail-closed?
3. `src/cuts/families/power_grid_reach.py:_parse_protocol_core_cell` 负数 reject 真生效? 边界 (x=0 / x=61 / x=62 / x=-1 / x=70) 都 correct?
4. evaluator + validator + verifier 三层 (evaluator hot path, validator deep recompute, verifier attach-scope step 6) 是 defense-in-depth 还是 redundancy 浪费? 设计 sound?

**R5 hidden bug hunt** — 极致 hostile, 最后机会:
- R1-R4 累积 11 finding (4+4+3+4) — 是否有 finding 之间 interaction 漏 (e.g., R1 + R3 + R4 修法 stacked, 某 path 没全 cover)?
- F8 cert 进 cut_store rotation, ghost 变 (master 重选), 现 attach 的 cut 怎么处理 (attach-scope 应 step 1-6 re-verify)?
- canonical_rules 真数据没有 pole→pole jump radius 字段, R5 修法用 `power_coverage_radius` (pole→facility=5) 当 pole→pole jump radius (Phase 1.2 spec §1c 简化). 这个 simplification 是否真符合游戏物理? 实测玩家社区如何理解 pole-to-pole?
- F8 是否真应该在 Phase 1.2 closeable? 4 round NOT_GO 是否暗示设计 fundamental 问题 (e.g., F8 应推迟 Phase 1.5+)?

## Armor 规则

- 不接受 vague hyperbole / GO ritual / 必 cite file:line
- GO verdict 必先列 3 死法 + disprove (cite file:line)
- 找不到 critical 必列 3 high-risk hypothesis disproved
- **R5 特别**: 如果 R5 verdict 仍 NOT_GO, 必须明确指出"为什么 R4 没 catch" + 是否系统性 problem

## R5 我预察到的 NEW gap

R5-Gap N (4 round 后仍可能漏): F8 跟 F2/F4/F6/F7 3-round 收敛对比, F8 已 4 round. R5 还有 finding 意味着 design 复杂度高 (geometric / multi-cell footprint / cross-check chain) 还是有系统性盲点?

R5-Gap O (canonical pole→pole vs pole→facility simplification): spec §1c 简化 "pole-to-pole = pole-to-facility radius" 是否真理? 5×5 pole→pole 看起来跟 power 网游戏物理一致, 但 caller-supplied + verifier 用 canonical pole→facility R 校验, 这是 implicit constraint, 应文档化.

R5-Gap P (Phase 1.2 close criteria): F8 Phase 1.2 single-case scope 是否已经满足 "cell_owner != null, master_solution wired" 等 prerequisite? 若 production state 跟 fixture 不一致, 哪些 corner case 还会暴露?

## Format

```
## Round 5 Verdict
GO | GO_WITH_MINOR | CONCERN | NOT_GO (一行)

## R4 fix verification (Finding #1/#2/#3/#4)
- Finding #1 fix (evaluator protocol_core position check): LANDED / PARTIAL / REGRESSION — cite file:line
- Finding #2 fix (validator SoT cross-check): LANDED / PARTIAL / REGRESSION — cite file:line
- Finding #3 defer (Phase 1.2 bounds-only): ACCEPTED / DISPUTED — 详释
- Finding #4 fix (negative coord parse): LANDED / PARTIAL / REGRESSION — cite file:line

## R5 NEW Gap N/O/P
- R5-Gap N (4-round 收敛慢): CONFIRMED / PARTIAL / REJECTED + 系统性 problem 判断
- R5-Gap O (canonical pole→pole simplification): CONFIRMED / PARTIAL / REJECTED
- R5-Gap P (Phase 1.2 close criteria): CONFIRMED / PARTIAL / REJECTED

## Round 5 New findings (≥0; 没新 finding 也明确说)

(if any)
### Finding 1: [SEVERITY] file:line — title

## Sanity (GO verdict 必 ≥3 disproved hypothesis 含 file:line)

## 终结建议
- close at this round (Phase 1.2 final)
- 还需 R6
- Phase 1.5+ defer items
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
    s.append("## rules/canonical_rules.json — top-level keys (audit: 是否有 pole_jump_radius 字段)\n")
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
    s.append("## data/preprocessed/candidate_placements.json — pool sizes (audit: protocol_core pose 选择空间)\n")
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
