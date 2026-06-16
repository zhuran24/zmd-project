#!/usr/bin/env python3
"""Phase 1.2 P1.2B-F8 power_grid_reach Gemini round 3 cross-check.

Round 1 (4be1b60): NOT_GO, 4 finding (3 CRITICAL #1/#2/#3 + 1 HIGH #4).
Round 2 (b9ab24a): NOT_GO, 4 new finding (2 CRITICAL + 2 HIGH).
Round 3 base (fe7c239): R2 Finding #1/#2/#3 fixed, #4 rejected (Gemini
misread JSON schema — verified `facility_pools` is top-level key).

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


PROMPT = """你是 power network / connectivity cut / geometric soundness / Liang-Barsky / BFS reachability 审查员。Endfield Phase 1.2 P1.2B-F8 **Round 3** cross-check (commit `fe7c239`).

# 任务背景 (最小)

70×70 LBBD certified-exact, F8 拦 "facility 的 CoverSet 非空但 pole-jump BFS 从 protocol_core 不可达 → INFEASIBLE". 跟 F7 互斥 (F7 = CoverSet 空).

# R2 → R3 diff (这次 review 的核心)

R1 (commit `4be1b60`) NOT_GO: 4 finding fix → R2 base `b9ab24a`.
R2 (commit `b9ab24a`) NOT_GO: 4 new finding (#1/#2/#3 fixed, #4 rejected) → R3 base `fe7c239`.

R3 base 修法 (must verify):

| R2 Finding | 类型 | R2 漏洞 | R3 修法 |
|---|---|---|---|
| #1 | CRITICAL | `_can_jump(p1, p2)` 用 `_euclidean(anchor, anchor)` overestimate cell-to-cell min by up to √8, drops legitimate edges | 新 `_can_jump_via_cells(cells1, cells2, ...)` + `_footprint_cells` + `_closest_cell_pair` helpers. distance = min cell-to-cell over both footprints. consistent with `compute_cover_set._min_cell_distance` |
| #2 | CRITICAL | `segment_intersects_aabb` 用 anchor coord (top-left corner), 不是 cell center | `_can_jump_via_cells` use closest cell pair centers `(c[0]+0.5, c[1]+0.5)` as segment endpoints |
| #3 | HIGH | `pc_set -= pole_set` direction reversed vs comment ("pc takes priority") | `pole_set -= pc_set` matches documented intent. 实际 free_cells 永远 exclude pc so overlap=0, but contract now self-consistent |
| #4 | HIGH | "facility_pools" schema 误判 generator silent fail | **REJECTED**: real `data/preprocessed/candidate_placements.json` 顶层 key 确是 `"facility_pools"` (verified `.venv/bin/python -c "json.load(...)['facility_pools'].keys()"` = manufacturing_3x3 / manufacturing_5x5 / manufacturing_6x4 / protocol_core / protocol_storage_box). Gemini misread JSON. No code fix. |

R3 还做了 R2-Gap E 优化 (anchor-distance early reject): `_pole_pole_edges` 加 `anchor_dist² > (R + 2√2)² ⇒ skip` 早过滤. Bound: `min cell-to-cell ≥ anchor_dist - 2√2`. R=5 + 70×70 grid, ~99% pole pair rejected, F8 test 180s → 60s. `_pole_pc_edges` 同 pattern (cutoff = R + √2).

验证状态 (commit fe7c239):
- 42 F8 + power_network helper test pass (was 39, +3 regression test: cell-to-cell distance / pole-pc cell distance / ghost segment center)
- 2619 full pytest pass (0 fail / 60 skip)
- mypy strict 4 module 0 error
- radon `build_power_network` A(3), avg A(4.09); _pole_pole_edges B(7) + _pole_pc_edges B(8) (含 early-reject branch)

# Round 3 任务

**主线 (verify R2 fix)** — 全文 cite file:line:
1. `src/cuts/helpers/power_network.py:_can_jump_via_cells` — 数学严格性: min cell-to-cell distance + closest-pair segment 算法是否 sound? 极端 (footprint overlap / 同 cell / 1×1 vs 2×2) 都 OK 吗?
2. `src/cuts/helpers/power_network.py:_pole_pole_edges` + `_pole_pc_edges` 早过滤 anchor-distance bound `(R + 2√2)² / (R + √2)²` 是 sound upper bound 还是 loose / tight? 漏过滤吗 (FN: 真应该 reject 但没过滤掉, 只是慢, 不影响 soundness) 还是漏 keep (FP: 真应该 keep 但 early-reject 掉, 这是 sound 灾难)?
3. R2-Gap E 真 fix 了吗? 当 pole_radius=50 (实测 fixture) 时 cutoff 52.83 > 70×√2 ≈ 99 grid diagonal, 等价 no early-reject. Production R≈5 是不是真的 cover 全 case?
4. `pole_set -= pc_set` (R2 Finding #3 fix): 现在 contract 是 "drop overlap from pole_set, keep in pc_set". 但 free_cells 永远 exclude pc, 所以 pole_set 永远不含 pc cells, 这个 dedup 永远 no-op. 这是 dead defense 还是必要 invariant guard?

**R3 hidden bug hunt** — 真 hostile lookup:
- 仍然 R2 没 catch 的 cert 攻击面 (R3/R4 加严层在 F8 验过了吗?)
- Watcher store key 与 F8 cert 在 cut_store rotation 下行为
- F7 ↔ F8 oracle 顺序在并发 / 部分 master_solution 下的 race?
- Liang-Barsky 在 cell center 坐标 (0.5, 0.5) 上的退化 case (segment 完全在 ghost 顶 / 底 edge, 数值精度)?

## Armor 规则

- 不接受 vague hyperbole ("looks correct / fixes the issue")
- 不接受 GO ritual ("R2 fixes are properly applied" 这种 — 必须 cite file:line)
- GO verdict 必先列 3 死法 + disprove (cite file:line)
- critical claim 必 cite file:line 或 spec §X 或 literature
- 找不到 critical 也必列 3 high-risk hypothesis disproved (file:line)

## R3 我预察到的 NEW gap

R3-Gap H (early-reject bound tightness): cutoff `R + 2√2 ≈ 7.83` for R=5. 但实际 worst case min cell-to-cell ≥ anchor_dist - 2√2 是 loose bound — 两 footprint 最远 cell 对最近 anchor (1, 0) 偏移. tight bound 应该跟具体方向有关. 现实施 sound (loose 永远 over-keep, sound 灾难是 over-reject), 但可优化?

R3-Gap I (closest-cell-pair segment): `_closest_cell_pair` 返回**任一**最近 pair (tie-breaking 不确定). 同 distance 的多 pair, segment 选哪 pair 影响 ghost intersection 结果. 是否需要"任一 unblocked segment 即可"语义 (e.g., 多 pair 都 ≤ R, 只要一个 segment 不过 ghost 就连接)?

R3-Gap J (`_validate_disconnect_witness` 跟 `_validate_ghost_only_disconnect` 的关系): 两都重建 graph (heavy). 现在 ghost_only 是 full_free 加 cell_owner. 若 cell_owner 跟 pole anchor 重合 (理论应该不会, 但 fixture 没 invariant guard), 行为如何?

## Format (严格不要 think-out-loud)

```
## Round 3 Verdict
GO | GO_WITH_MINOR | CONCERN | NOT_GO (一行)

## R2 fix verification (Finding #1/#2/#3 + Gap E)
- Finding #1 fix (_can_jump_via_cells cell-to-cell min): LANDED / PARTIAL / REGRESSION — cite file:line
- Finding #2 fix (cell-center segment endpoints): LANDED / PARTIAL / REGRESSION — cite file:line
- Finding #3 fix (pole_set -= pc_set 方向): LANDED / PARTIAL / REGRESSION — cite file:line
- Finding #4 rejection (facility_pools schema): ACCEPTED / DISPUTED — 详释
- R2-Gap E (anchor-distance early reject): LANDED / PARTIAL / NOT-ADDRESSED — cite file:line + 性能预估

## R3 NEW Gap H/I/J
- R3-Gap H (early-reject bound tightness): CONFIRMED / PARTIAL / REJECTED
- R3-Gap I (closest-pair segment ambiguity): CONFIRMED / PARTIAL / REJECTED
- R3-Gap J (full vs ghost-only path overlap): CONFIRMED / PARTIAL / REJECTED

## Round 3 New findings (≥3, 任何 severity, R1+R2 没 catch 的)

### Finding 1: [SEVERITY] file:line — title
≤ 200 字.

### Finding 2: ...
### Finding 3: ...

## Sanity (GO verdict 必 ≥3 disproved hypothesis 含 file:line)

## 建议 Round 4 重点 / Phase 1.5+ defer / 终结 (close at this round)
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
