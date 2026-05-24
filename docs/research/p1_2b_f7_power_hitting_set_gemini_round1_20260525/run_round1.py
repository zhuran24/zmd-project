#!/usr/bin/env python3
"""Phase 1.2 P1.2B-F7 power_hitting_set Gemini round 1 cross-check.

Per memory [[gemini-review-algorithm-math]] v4 protocol.
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
    "src/cuts/families/power_hitting_set.py",
    "src/cuts/oracles/power_cover_oracle.py",
]

SPEC_FILES = [
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/07_power_hitting_set.md",
]


PROMPT = """你是 hitting set / combinatorial cut / power network / soundness 审查员。Endfield 工业规划求解器 Phase 1.2 P1.2B-F7 **Round 1** cross-check (commit `c30d681`).

# 任务背景

70x70 grid certified-exact LBBD, F7 是 9 cut family 之一: 拦 "facility 候选 pole 集合空 → INFEASIBLE". L16 lazy power completion (benders_loop.py:4179-4286) 在 v2 framework 内 typed cut 形式化.

# Design merger from 5 parallel opus subagents

- correctness-paranoid: **critical finding** — spec §1a/§3 写 "Pole 1×1" 但 canonical_rules.facility_templates.power_pole.dimensions = {w:2, h:2}. 实施 follow real data (pole 2×2, `pole_shape_canonical = "2x2_rigid"`).
- throughput: lazy per-candidate, O(grid) bucket-by-cell pole enum
- adversarial: 15+ attack matrix; needs_power=False check (spec 漏 catch); pose 不在 pose_domain catch
- integration: post-master plug (L16 paradigm); Phase 1.5+ wraps L16 via SubProblemOracleAdapter
- minimum viable: 7-phase validator + 3 file structure + cell_owner causation defer Phase 1.5+

# Phase 1.2 single-case scope (per minimum viable)

- cert_kind 单值: `"power_cover_emptyset_ghost"`
- cell_owner causation (multi-literal) defer Phase 1.5+
- Generator default-disabled (EXACT_F7_GENERATOR_ENABLED=0 default, 跟 F6 pattern)
- Validator phase 7 用 ghost-only CoverSet 重算 ∅ 验单 literal sound (确保 cell_owner 不是真 cause)
- 复用 lifecycle.evaluate_literal_multiset

# Round 1 任务 (v4 加严协议 — 不接受 GO ritual)

1. **Spec-data gap focus** — 真数据 inline 在下方. 实施 src 接合真数据时哪步 crash / FN / FP?
2. **Hall-style hitting set 数学严格性** (spec §2a empty CoverSet 单调保持): rigid 2×2 pole 占 4 连续 cells 假设有 hidden weak case?
3. **Fail-closed semantics**: 7 phase 是否真覆盖 15+ attack 路径?
4. **cell_owner causation phase 7 (ghost-only CoverSet 重算)**: validator phase 7 用 ghost-only CoverSet 验单 literal sound. 真 sound 吗? 边界 case (ghost 跟 cell_owner 重叠时)?
5. **canonical_rules ground truth ↔ spec drift**: spec 多处写 "1×1 pole" 但 canonical_rules 是 2×2. 实施跟真数据, spec 文本待修. 这种 design 决策正确吗?
6. **Generator default-disabled (Phase 1.5+ wiring 推迟)**: 跟 F6 同 pattern. Phase 1.2 fixture/test 路径如何 trigger?

## Armor 规则

- 不接受 "looks fine / 完美 / very solid" vague hyperbole
- GO verdict 必先列 3 死法 + disprove (cite file:line)
- critical claim 必 cite file:line 或 spec §X 或 literature
- 找不到 critical 也必列 3 high-risk hypothesis disproved (file:line)

## 关键 finding 我自己已经预察到

Gap A: spec §1a/§3 写 "1×1 pole" 矛盾 canonical_rules `power_pole.dimensions={w:2, h:2}` (实证). 实施跟真数据 (2×2 rigid). 是 sound 设计还是埋雷?

Gap B: `compute_cover_set` 使用 cell-to-cell min Euclidean distance (无 metric label, 项目共识 Euclidean). 真游戏 power coverage 真是 Euclidean R=5 圆形还是 Chebyshev 5×5 方形 / Manhattan diamond? canonical_rules 没标 metric.

Gap C: Phase 1.2 validator phase 7 用 ghost-only CoverSet 重算 ∅ 验单 literal sound. 但若 ghost 跟 cell_owner 重叠 cells (master pose 占了 ghost 内 cell, 不可能因 ghost prerequisite, 但 edge case)? 设计是否漏 catch?

## Format (严格不要 think-out-loud)

```
## Round 1 Verdict
GO | GO_WITH_MINOR | CONCERN | NOT_GO (一行)

## Verify Gap A/B/C
- Gap A (1×1 vs 2×2 spec drift): CONFIRMED / PARTIAL / REJECTED — 详释
- Gap B (metric label missing): CONFIRMED / PARTIAL / REJECTED — 详释 + 推荐
- Gap C (ghost ∩ cell_owner edge case): CONFIRMED / PARTIAL / REJECTED — 详释

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
    s = ["# DOC_PATHS: 真数据 schema inline (v4 协议硬要求)\n"]

    rules = json.loads((ROOT / "rules/canonical_rules.json").read_text())
    templates = rules.get("facility_templates", {})
    s.append("## rules/canonical_rules.json — facility_templates (full)\n")
    s.append("```json\n")
    s.append(json.dumps(templates, indent=2, ensure_ascii=False))
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
        s.append(f"Total {len(me)} instance entries. Powered: ")
        powered = []
        for ft, tpl in templates.items():
            if tpl.get("needs_power") is True:
                powered.append(f"{ft}={types_count.get(ft, 0)}")
        s.append(", ".join(powered))
        s.append("\n\n")

    s.append("## BState fields F7 reads\n")
    s.append("- state.ghost_rect / state.ghost_cells / state.exterior_blocks\n")
    s.append("- state.cell_owner: Dict[Cell, OwnerId]\n")
    s.append("- state.groups[gid]: GroupState (group_id, demand, pose_domain, selected_poses)\n")
    s.append("- state.instance_to_facility_type: Dict[GroupId, str]\n")
    s.append("- state.facility_templates: Dict[str, Dict] (alias canonical_rules.facility_templates)\n")
    s.append("- state.candidate_placements: Dict (mirrors data/preprocessed/candidate_placements.json)\n\n")

    return "".join(s)


def build_src_section() -> str:
    s = ["# F7 src (full content inline)\n\n"]
    for rel in SRC_FILES:
        s.append(f"### FILE: {rel}\n```python\n")
        s.append(read(rel))
        s.append("\n```\n\n")
    return "".join(s)


def build_spec_section() -> str:
    s = ["# F7 spec (cut_family_specs/07_power_hitting_set.md v1.1)\n\n"]
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
    print(verdict_text[:3500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
