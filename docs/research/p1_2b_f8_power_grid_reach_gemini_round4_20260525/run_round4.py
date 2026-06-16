#!/usr/bin/env python3
"""Phase 1.2 P1.2B-F8 power_grid_reach Gemini round 4 cross-check.

Round 1 (4be1b60): NOT_GO, 4 finding (3 CRITICAL + 1 HIGH).
Round 2 (b9ab24a): NOT_GO, 4 new finding (2 CRITICAL + 2 HIGH, #4 rejected).
Round 3 (fe7c239): NOT_GO, 3 finding (2 CRITICAL + 1 HIGH).
Round 4 base (29b64d0): R3 Finding #1/#2/#3 all landed via active_assumptions
+ verifier dispatch + any-pair-segment scan.

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


PROMPT = """你是 power network / connectivity cut / geometric soundness / Liang-Barsky / BFS reachability / assumption verifier dispatch 审查员。Endfield Phase 1.2 P1.2B-F8 **Round 4** cross-check (commit `29b64d0`).

# 任务背景 (最小)

70×70 LBBD certified-exact, F8 拦 "facility 的 CoverSet 非空但 pole-jump BFS 从 protocol_core 不可达 → INFEASIBLE". 跟 F7 互斥 (F7 = CoverSet 空).

# R3 → R4 diff (这次 review 的核心)

R1 (commit `4be1b60`) NOT_GO: 4 finding (3 CRITICAL + 1 HIGH) → R2 base `b9ab24a`.
R2 (commit `b9ab24a`) NOT_GO: 4 finding (2 CRITICAL + 2 HIGH, #4 rejected — Gemini misread JSON) → R3 base `fe7c239`.
R3 (commit `fe7c239`) NOT_GO: 3 finding (2 CRITICAL + 1 HIGH) → R4 base `29b64d0`.

R4 base 修法 (must verify):

| R3 Finding | 类型 | R3 漏洞 | R4 修法 |
|---|---|---|---|
| #1 | CRITICAL | `_can_jump_via_cells` 只检查 closest cell pair 的 segment, 若 closest 被 ghost 挡但其他 in-range pair 未挡, 仍 drop edge → FP disconnect | 改 any-pair scan: 遍历所有 cell pair (`c1∈cells1`, `c2∈cells2`), distance ≤ R AND segment 不过 ghost → True. 2×2 vs 1×1 footprint 至多 16 pair, 仍被外层 anchor-distance early-reject 限制 |
| #2 | CRITICAL | validator blindly trusts cert.pole_jump_radius + protocol_core_cell; 恶意 cert (R=0.001 / 错 anchor) 可伪造 disconnect | Wire via Finding #3 active_assumptions: attach-scope step 6 调 `assumption_holds` dispatch 到 verifiers.py; cert 不再 sole truth, 须 source-of-truth pass |
| #3 | HIGH | oracle `_build_cut` 没设 CutScope.active_assumptions (spec §4 mandate) | oracle 加 `active_assumptions=(Assumption("power_pole_jump_radius", f"R={r:g}"), Assumption("protocol_core_position", f"({x},{y})"))`. verifiers.py 加 `verify_power_pole_jump_radius` (读 `state.canonical_rules.facility_templates.power_pole.power_coverage_radius`) + `verify_protocol_core_position` (parse "(x,y)" + 9×9 bounds + cell_owner cross-check when 存在) |

R3 旧 fixture 改: `test_build_ghost_blocks_jump` + `test_ghost_segment_uses_cell_centers_not_anchors` 改 ghost rect h=2 (从 h=1) — 旧 fixture 在 closest-pair 语义下 pass, any-pair scan 下应让某些 pair (y=1.5) 不过 ghost AABB (y=[0,1]) → edge fires. 现 ghost AABB y=[0,2] 全 cell-pair segment 都过 → edge drop. 这是修 test 不是改 src.

验证状态 (commit 29b64d0):
- 43 F8 + power_network helper pytest (was 42, +1 regression test `test_jump_accepts_any_unblocked_cell_pair`)
- 10 new verifier pytest in `src/tests/cuts/test_assumptions_verifiers.py` (R=5 match / R=0.001 reject / no canonical rules / malformed value / bounds in/out of grid / cell_owner cross-check match/mismatch / malformed position)
- 2629 full pytest pass (was 2619, +10 verifier tests)
- mypy strict 5 module 0 error (新增 verifiers.py)
- radon avg A(4.45), max B(8) (verifiers helper `_protocol_core_footprint_owned` + `verify_protocol_core_position`); `_can_jump_via_cells` 从 closest-only → any-pair 后 B(6)

# Round 4 任务

**主线 (verify R3 fix)** — 全文 cite file:line:
1. `src/cuts/helpers/power_network.py:_can_jump_via_cells` — any-pair scan 严格性: 真的找到 ANY in-range unblocked segment 就 return True 吗? 短路 (early return) 正确吗? 退化 case (cells1 / cells2 之一是 empty, footprint overlap 同 cell, distance=0 算 jump 吗) 行为对?
2. `src/cuts/oracles/power_grid_reach_oracle.py:_build_cut` 加的 `active_assumptions` — 跟 spec §4 严格匹配吗? key/value format 跟 `verifiers.py` 验证逻辑一致? F8 cut 进 cut store 后, attach-scope step 6 真能调到 verifier?
3. `src/cuts/assumptions/verifiers.py:verify_power_pole_jump_radius`: 真的能 catch R=0.001 (malicious cert)? canonical_rules 缺 power_pole / 缺 power_coverage_radius 怎么 fail-closed? 这是不是真 source-of-truth 还是 placeholder?
4. `src/cuts/assumptions/verifiers.py:verify_protocol_core_position`: 9×9 bounds + cell_owner cross-check 真 enforce master_solution? 当 cell_owner 空 (fixture / Phase 1.2 single-case), accept bounds-only 是 sound choice 还是 leak?
5. `_VERIFIERS` dict 新加 2 key (`power_pole_jump_radius` + `protocol_core_position`) — `register_verifier` 不允许 silent overwrite (Gemini round 28 finding #2), 直接 dict 添加是否绕开 ducktest?

**R4 hidden bug hunt** — 真 hostile lookup (R3 没 catch 的):
- F8 cert active_assumption 跟 cert payload 字段冗余: cert 自己也有 `pole_jump_radius` 字段, scope 也有 assumption. 两者 conflict 时哪个胜? validator 用 cert (build_power_network with cert.pole_jump_radius), attach-scope 用 assumption — 攻击者 cert.pole_jump_radius=5 但 assumption R=5 (canonical 通过), 然后 validator 用真 R=5 验证 build graph (无 attack effect). 还有 attack 路径?
- F8 cut 跟 F1-F7 cut 在 cut_store 同 ghost 下的 watcher 冲突 / replay 顺序?
- `verify_protocol_core_position` 当 cell_owner 空 → bounds-only → 万一 production state 是 cell_owner 空 + 攻击者传 (0,0) 怎么办?
- Spec §1c 简化 ("pole-to-pole jump radius == pole-to-facility coverage radius") 是否真符合游戏? 游戏物理上 pole→pole 跟 pole→facility 用同一 R?

## Armor 规则

- 不接受 vague hyperbole ("looks fine / great")
- 不接受 GO ritual (必须 cite file:line)
- GO verdict 必先列 3 死法 + disprove (cite file:line)
- critical claim 必 cite file:line 或 spec §X 或 literature
- 找不到 critical 也必列 3 high-risk hypothesis disproved (file:line)

## R4 我预察到的 NEW gap

R4-Gap K (active_assumption 冗余 vs cert payload): cert 同时存 `pole_jump_radius` 字段 + scope 存 `power_pole_jump_radius` assumption. 验证两层: validator 重建 graph 用 cert 的 (假定 attach-scope 已 verified assumption ≡ source-of-truth)? 设计 sound? 攻击 path 漏?

R4-Gap L (Phase 1.2 bounds-only 漏洞): 当 `state.cell_owner` 空 (fixture / 早 phase), `verify_protocol_core_position` 接受 bounds-only check. 这意味着 Phase 1.2 production 若先 generate F8 cut 再 master place protocol_core (lifecycle 顺序), assumption 通过 bounds-only — 但实际后续 cell_owner 跟 cert anchor 不匹配. 是否需 phase guard?

R4-Gap M (verifier dict 直接添加绕过 register_verifier): R3 fix 直接修改 `_VERIFIERS = {...}` dict literal, 没用 `register_verifier(...)` API. 这是 module-level static initialization (合理), 还是绕开 Gemini round 28 finding #2 的 silent overwrite 防护?

## Format (严格不要 think-out-loud)

```
## Round 4 Verdict
GO | GO_WITH_MINOR | CONCERN | NOT_GO (一行)

## R3 fix verification (Finding #1/#2/#3)
- Finding #1 fix (any-pair segment scan): LANDED / PARTIAL / REGRESSION — cite file:line
- Finding #2 fix (validator trust via active_assumptions): LANDED / PARTIAL / REGRESSION — cite file:line
- Finding #3 fix (active_assumptions in CutScope + verifier dispatch): LANDED / PARTIAL / REGRESSION — cite file:line

## R4 NEW Gap K/L/M
- R4-Gap K (active_assumption ↔ cert payload 冗余): CONFIRMED / PARTIAL / REJECTED
- R4-Gap L (bounds-only when cell_owner empty): CONFIRMED / PARTIAL / REJECTED
- R4-Gap M (verifier dict literal vs register_verifier API): CONFIRMED / PARTIAL / REJECTED

## Round 4 New findings (≥3, 任何 severity, R1+R2+R3 没 catch 的)

### Finding 1: [SEVERITY] file:line — title
≤ 200 字.

### Finding 2: ...
### Finding 3: ...

## Sanity (GO verdict 必 ≥3 disproved hypothesis 含 file:line)

## 建议 (close at this round? or Round 5? Phase 1.5+ defer?)
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
