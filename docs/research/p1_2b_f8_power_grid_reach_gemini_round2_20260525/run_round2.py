#!/usr/bin/env python3
"""Phase 1.2 P1.2B-F8 power_grid_reach Gemini round 2 cross-check.

Round 1 (commit 4be1b60) verdict: NOT_GO with 4 findings.
Round 2 base: commit b9ab24a (3 CRITICAL fixed + 1 HIGH deferred).

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


PROMPT = """你是 power network / connectivity cut / geometric soundness / Liang-Barsky / BFS reachability 审查员。Endfield Phase 1.2 P1.2B-F8 **Round 2** cross-check (commit `b9ab24a`).

# 任务背景 (最小)

70×70 LBBD certified-exact, F8 拦 "facility 的 CoverSet 非空但 pole-jump BFS 从 protocol_core 不可达 → INFEASIBLE". 跟 F7 互斥 (F7 = CoverSet 空).

# R1 → R2 diff (这次 review 的核心)

**R1 verdict: NOT_GO** (commit `4be1b60`), 4 finding (3 CRITICAL + 1 HIGH).

R2 base commit `b9ab24a` 修法摘要 (须 verify):

| Finding | 类型 | R1 漏洞 | R2 修法 |
|---|---|---|---|
| #1 | CRITICAL | validator + oracle 把 `list(cover_set)` 传 `build_power_network`, 漏 spanning intermediate, 100% FP | 新 public helper `enumerate_valid_pole_anchors(free_cells)` 取全 grid 合法 2×2 anchor; oracle + validator 改调它 |
| #2 | CRITICAL | pc_cell 当 single point, 9×9 protocol_core 远端 cell 距 anchor > R | API 改 `pc_cell` → `pc_cells: Iterable[Pole]`; pc 全 9 cells 加 vertices + 内部 auto pairwise edge + pole-pc edge 看 pole 到**任一** pc cell ≤ R |
| #3 | CRITICAL | evaluator 漏 spec §6 selected_poses check, `literals=None` cut 永久毒化 ghost AABB | evaluator 加 `state.groups[gid].selected_poses` 含 `cert.pose_id` check |
| #4 | HIGH | evaluator 宽 `except Exception: return False` 静默 fail | **defer Phase 1.5+**: hot-path fail-safe (return False = 不 prune = 保 soundness 只 lose prune), validator 已 enforce schema strict |

验证状态: 379 cuts pytest / 2616 full pytest / mypy strict 4 module 0 / radon `build_power_network` C(15)→A(3) refactor (子 helper: `_can_jump` / `_pole_pole_edges` / `_pc_internal_edges` / `_pole_pc_edges`).

# Round 2 任务

**主线 (verify R1 fix)** — 全文 cite file:line:
1. `src/cuts/helpers/power_cover.py:enumerate_valid_pole_anchors` — public contract 是否漏 (e.g. 默认 grid_size / pole_size) 让 caller 误传? 跟 R1 Finding #1 修法实际 fix 吗?
2. `src/cuts/helpers/power_network.py:build_power_network` 新 API + 4 子 helper — `pc_set -= pole_set` dedup 真无害吗? overlap cell 被划到 pc 而不在 pole_list, 那 cell ↔ 其他 pole 之间是否漏 edge?
3. `src/cuts/families/power_grid_reach.py:_validate_disconnect_witness` + `_validate_ghost_only_disconnect` — 调用点签名换了, BFS reach pc cell 仍是从 `pc_anchor` 单点 BFS, 是否漏 (e.g. pc_anchor 跟某 isolated 子 component 是同 vertex 但 graph 上 BFS 仅从 anchor 走?)
4. `src/cuts/families/power_grid_reach.py:evaluate_geometric_power_grid_reach` — selected_poses check (`pose_raw not in group_state.selected_poses`, O(n) linear scan) hot-path performance 是 concern? sound 上漏 case 没 (e.g. PoseId 类型怪异 / state.groups None / GroupState 缺 field)?
5. Regression test `test_generator_no_cut_via_spanning_intermediate_poles`: 只测 "连通后不发 cut", 没测 "F5 fixture (ghost wide vertical strip + R=5) 仍 fire". R1 fix 没破 R1 已 pass 的 disconnect case?

**hidden bug hunt (R1 没 catch)** — 真 hostile lookup, 不要重提 R1 的 Gap:
- Watcher / store integration (F8 cut 进 cut store, 哪些 key trigger replay?)
- Schema validation strict mode (R3/R4 加严层覆盖 F8 cert 没?)
- 跟现有 F1-F7 cut family 之间是否有 cert_kind 命名冲突 / scope 冲突?
- 真 hostile cert payload (huge facility_cells array / negative pole_jump_radius / cert claim 跟 source data inconsistent — `pole_shape_canonical = "1x1_rigid"` 在 canonical_rules pole 2×2 数据下) validator 拒掉?

## Armor 规则

- 不接受 "looks fine / 完美 / very solid" vague hyperbole
- 不接受 GO ritual ("R1 修法看起来都到位" 这种 — 必须 cite file:line 说哪行 verifies 哪行)
- GO verdict 必先列 3 死法 + disprove (cite file:line)
- critical claim 必 cite file:line 或 spec §X 或 literature
- 找不到 critical 也必列 3 high-risk hypothesis disproved (file:line)

## R2 我预察到的 NEW gap (不是 R1 Gap A/B/C/D, 那些已 verdict)

R2-Gap E (Finding #1 修法的副作用): `enumerate_valid_pole_anchors(free_cells)` 在 70×70 grid 上枚举 ~70×70=4900 anchor (排除 ghost+exterior+cell_owner+facility+pc 后剩 ~3000-4000). `build_power_network` 是 O(|V|²) edge enumeration → ~10M pairs. validator 跑 hot path, 单 cut validation ~1-3s. 实际 production wave 可能上千 cut, 总 validation 时间预估?

R2-Gap F (Finding #3 修法的写法): `pose_raw not in group_state.selected_poses` 是 `list.__contains__` (O(n)). demand=46 单 group 时, 单 evaluator call O(n=46). 若 cut store 触 1000 cut/iter, 总 46K op — 不大. 但若 spec §22 telemetry 跑 statistics 频繁 evaluator call (~10K cut * 10 iter), 6M op 可能可观. 是否需要 frozenset cache?

R2-Gap G (Finding #2 修法的 vertex dedup): `pc_set -= pole_set` 把 pc/pole overlap cell 从 pole_set 移除. 实际上 master_solution 应禁止 pole 占 pc cells (pc 是 facility footprint), 所以理论 overlap=0. 但 R1 验证 fixture 不一定遵守此 invariant. 若 fixture / 测试中 overlap 出现, edge 是否漏?

## Format (严格不要 think-out-loud)

```
## Round 2 Verdict
GO | GO_WITH_MINOR | CONCERN | NOT_GO (一行)

## R1 fix verification (Finding #1/#2/#3)
- Finding #1 fix (enumerate_valid_pole_anchors + 调用点): LANDED / PARTIAL / REGRESSION — cite file:line
- Finding #2 fix (pc_cells multi-cell + 4 子 helper): LANDED / PARTIAL / REGRESSION — cite file:line
- Finding #3 fix (evaluator selected_poses): LANDED / PARTIAL / REGRESSION — cite file:line
- Finding #4 defer (Phase 1.5+): ACCEPTED / REJECTED — 详释

## R2 NEW Gap E/F/G
- R2-Gap E (validator validation 时间): CONFIRMED / PARTIAL / REJECTED — 预估
- R2-Gap F (selected_poses O(n) hot-path): CONFIRMED / PARTIAL / REJECTED — 推荐
- R2-Gap G (pc/pole overlap edge dedup): CONFIRMED / PARTIAL / REJECTED — 详释

## Round 2 New findings (≥3, 任何 severity, R1 没 catch 的)

### Finding 1: [SEVERITY] file:line — title
≤ 200 字.

### Finding 2: ...
### Finding 3: ...

## Sanity (GO verdict 必 ≥3 disproved hypothesis 含 file:line)

## 建议 Round 3 重点 / Phase 1.5+ defer
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
