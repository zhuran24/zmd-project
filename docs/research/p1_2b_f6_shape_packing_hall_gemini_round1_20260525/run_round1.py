#!/usr/bin/env python3
"""Phase 1.2 P1.2B-F6 shape_packing_hall Gemini round 1 cross-check.

Per memory [[gemini-review-algorithm-math]] v4:
- DOC_PATHS 必含真数据
- 任务直接问 spec-data gap
- Armor strict mode (3 死法 + 反 vague + cite file:line)
- 反 GO ritual
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
    "src/cuts/helpers/baseline_partition.py",
    "src/cuts/families/shape_packing_hall.py",
    "src/cuts/oracles/shape_packing_hall_oracle.py",
]

SPEC_FILES = [
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/06_shape_packing_hall.md",
]


PROMPT = """你是 Hall's marriage theorem / combinatorial cut / bin-packing / soundness 形式化方法 审查员。Endfield 工业规划求解器 Phase 1.2 P1.2B-F6 (shape_packing_hall) **Round 1** cross-check (commit `6adc5fd`).

# 任务背景

70x70 grid certified-exact LBBD 求解器, F6 是 9 个 cut family 之一: Hall 反例
拦 "ghost+exterior 切的 baseline 装不下 region_demand 个 rigid pose" →
INFEASIBLE cut. F2 反例: left baseline length 10, ghost+exterior 切 [4, 5],
pose_length=3, region_demand=3 → ⌊4/3⌋+⌊5/3⌋=2 < 3 → INFEASIBLE.

之前 land 的 F1-F4/F5/F9 都 GO. F6 是 first geometric-with-region_demand
family, 实现复用 baseline_partition.py helper (Phase 1.0 P1.4 已 land).

# Design merger 来源 — 5 parallel opus subagent slant

主对话从 5 个不同 slant 子代理收集 design 合并:
1. correctness-paranoid: 10 phase validator + 5 hidden weak case + 4 维 replay
2. throughput: by_cell watcher 不该用 (v1.1 cell_owner-independent), 3 层 cache
3. adversarial: 20+ attack matrix + 4 patches (含 partition_offsets recompute)
4. integration: F6 plug 在 benders_loop.py:~4341 + 3 path (a/b/c) for master attach
5. minimum viable: 8 phase + helper 复用 + 9 test

最终 land:
- Cert schema 含 `region_demand` (per region, Phase 1.5+ 真接 master.solution),
  `group_demand` (carry source-of-truth audit), `exterior_blocks_digest`
- 11-phase validator (合 5 agent 顶 + 4 patch)
- Strict `<` Hall witness (equality 不 cut)
- pose_length >= 2 (拒 退化 F1 case)
- partition_offsets 严等 recompute (不当 debug-only — adversarial agent patch)
- watcher: by_group + by_region + by_ghost auto (no by_cell)

# Round 1 任务 (v4 加严协议 — 不接受 GO ritual)

1. **Spec-data gap focus** — 真数据 inline 在下方. 实施 src 接合真数据时哪步
   crash / FN (该发 cut 不发) / FP (发不该发的 cut)?
2. **Hall theorem soundness**: spec §2a single-shape proof 是否 cover 所有
   corner? rigid 1×L pose 占 L 连续 cells 假设有 hidden weak case?
3. **Fail-closed semantics**: 11 phase 是否真覆盖 20 个 attack 路径? schema_err
   vs unsound 三分是否正确?
4. **Cross-state-of-truth**: canonical_rules / state.groups / source_digest /
   facility_templates 4 层 cross-check 哪里漏?
5. **region_demand 选 Phase 1.5+ 推迟决策**: 现 generator default
   `region_demand = min(group.demand, region_total_length // pose_length)`.
   合理 fallback 还是埋雷?

## Armor 规则

- 不接受 "looks fine / 完美 / very solid / ship-ready" 等 vague hyperbole
- GO verdict 必先列 3 种最可能死法 + disprove (cite file:line)
- critical claim 必 cite file:line 或 spec §X 或 literature
- 找不到 critical 也必列 3 个 high-risk hypothesis disproved (file:line 引用)

## 关键 finding我自己已经预察到 (verify + push more)

Gap A: spec §5b detect_shape_hall_infeasibility line 274
`demand = state.groups[contributing_group].remaining_count` 跟 §5a.bis
"demand 用 group.demand (source-of-truth)" 不一致. 实施已选 group.demand
+ region_demand 分离 schema, 跟 spec drift. 是吗?

Gap B: boundary_storage_port group.demand=46 全 group, 不是 per-region 23.
实施 generator 用 `min(group.demand, region_total_length // pose_length)` =
min(46, 23) = 23 作 default region_demand. 这是 sound 的 fallback (region 装满
上界 = 23 个 pose) 还是 over-trigger (永远发 cut)?

Round 1 任务: verify Gap A/B + push 找 round 1 第 3/4/... new finding.

## Format (严格不要 think-out-loud)

```
## Round 1 Verdict
GO | GO_WITH_MINOR | CONCERN | NOT_GO

## Verify Gap A/B
- Gap A (spec §5b drift): CONFIRMED / PARTIAL / REJECTED — 详释
- Gap B (region_demand default): CONFIRMED / PARTIAL / REJECTED — 详释 + 推荐

## Round 1 New findings (≥3, 任何 severity)

### Finding 1: [SEVERITY] file:line — title
≤ 200 字 (问题陈述 + reproduce + fix 建议)

### Finding 2: ...
### Finding 3: ...

## Sanity (如果 GO, 至少 3 disproved hypothesis 含 file:line)

## 建议 Round 2 重点 / Phase 1.5+ defer
```

"""


def build_doc_paths_section() -> str:
    s = ["# DOC_PATHS: 真数据 schema inline (v4 协议硬要求)\n"]

    # canonical_rules.json facility_templates.boundary_storage_port
    rules = json.loads((ROOT / "rules/canonical_rules.json").read_text())
    boundary_tpl = rules.get("facility_templates", {}).get("boundary_storage_port", {})
    s.append("## rules/canonical_rules.json — boundary_storage_port template\n")
    s.append("```json\n")
    s.append(json.dumps(boundary_tpl, indent=2, ensure_ascii=False))
    s.append("\n```\n\n")

    # mandatory_exact_instances counts
    me = json.loads((ROOT / "data/preprocessed/mandatory_exact_instances.json").read_text())
    from collections import Counter
    if isinstance(me, list):
        types_count: dict[str, int] = {}
        for entry in me:
            if isinstance(entry, dict):
                t = entry.get("facility_type") or entry.get("group_id")
                if t:
                    types_count[t] = types_count.get(t, 0) + 1
        s.append("## data/preprocessed/mandatory_exact_instances.json — group counts\n")
        s.append(f"Total {len(me)} instance entries. boundary_storage_port = {types_count.get('boundary_storage_port', 0)}.\n\n")
        s.append("Top 5 by count:\n")
        for k, v in sorted(types_count.items(), key=lambda x: -x[1])[:5]:
            s.append(f"- {k}: {v}\n")
        s.append("\n")

    # BState fields F6 used
    s.append("## BState fields F6 generator + validator reads\n")
    s.append("- `state.ghost_rect: Optional[Tuple[int, int, int, int]]` — (x, y, h, w)\n")
    s.append("- `state.ghost_cells: FrozenSet[Cell]` — set of (x, y) cells covered by ghost\n")
    s.append("- `state.exterior_blocks: FrozenSet[Cell]` — static map blocks\n")
    s.append("- `state.groups[gid]: GroupState (group_id, demand, pose_domain, selected_poses)`\n")
    s.append("- `state.instance_to_facility_type: Optional[Dict[GroupId, str]]`\n")
    s.append("- `state.facility_templates: Optional[Dict[str, Dict]]` — alias canonical_rules.facility_templates\n")
    s.append("\n")

    # left_baseline / bottom_baseline definitions
    s.append("## baseline cell convention (src/cuts/helpers/baseline_partition.py:28-38)\n")
    s.append("- left_baseline: `[(x, 0) for x in range(70)]` — 70 cells in column y=0\n")
    s.append("- bottom_baseline: `[(0, y) for y in range(70)]` — 70 cells in row x=0\n")
    s.append("- partition: scan along ordered cells, split on cells in ghost_cells ∪ exterior_blocks (NOT cell_owner per v1.1)\n\n")

    return "".join(s)


def build_src_section() -> str:
    s = ["# F6 src (full content inline)\n\n"]
    for rel in SRC_FILES:
        s.append(f"### FILE: {rel}\n```python\n")
        s.append(read(rel))
        s.append("\n```\n\n")
    return "".join(s)


def build_spec_section() -> str:
    s = ["# F6 spec (cut_family_specs/06_shape_packing_hall.md v1.1)\n\n"]
    for rel in SPEC_FILES:
        s.append(read(rel))
        s.append("\n\n")
    return "".join(s)


def main() -> int:
    key = os.environ.get("KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        print("ERROR: set KEY=<api_key> in env.", file=sys.stderr)
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
    print("calling Gemini 3.1 pro preview ...")
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
    elapsed = time.monotonic() - t0
    print(f"Gemini responded in {elapsed:.1f}s")

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
    print(verdict_text[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
