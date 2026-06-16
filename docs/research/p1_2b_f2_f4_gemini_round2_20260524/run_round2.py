#!/usr/bin/env python3
"""Phase 1.2 P1.2B-F2/F4 generator + helper Gemini round 1 cross-check.

Per memory [[gemini-review-algorithm-math]] v4:
- DOC_PATHS 必含真数据
- Task 直接问 spec-data gap
- Armor strict mode (3 死法 + 反 vague + cite file:line)
- 反 GO ritual

Run: KEY=<api_key> python3 run_round1.py
Output: prompt.txt + prompt.json + gemini_response.md + verdict.md
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
    "src/cuts/helpers/dinic_node_split.py",
    "src/cuts/oracles/cutset_oracle.py",
    "src/cuts/oracles/component_reach_oracle.py",
]

SPEC_FILES = [
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md",
]

# Validator side (reused helpers + validator entry)
VALIDATOR_REFERENCES = [
    ("src/cuts/families/cutset.py", "lines 1-260 (validator + helpers _free_cells / _parse_cell / _cross_partition_edges / _has_patch_escape — reused by generator)"),
    ("src/cuts/families/component_reach.py", "lines 1-200 (validator — independent BFS recompute + separator check)"),
]


PROMPT_HEADER = """你是 Dinic max-flow / LBBD / Menger min-cut / soundness 审查员。Endfield 工业规划求解器 Phase 1.2 P1.2B-F2/F4 (cutset + component_reach) **Round 2** cross-check (commit `01d368a`).

# Round 1 你给的 verdict: CONCERN. 3 finding:

1. BLOCKER: Dinic `_dfs_blocking_flow` 递归 → 70x70 serpentine `RecursionError`
   被 oracle except 静默吞 → false negative. **Fix landed**: 改 iterative
   (explicit stack of (node, pushed) + path_edges, dead-end pop+advance parent
   iter_ptr 匹配 recursive fall-through).
2. HIGH: Phase 1.5+ cell-capacity cut 切 internal edge → cross-partition recompute
   miss. **Deferred** (架构限制, edge-only by spec design).
3. LOW: bitset decoder padding `// 8 + 1` ≠ encoder `(+7) // 8` (70 巧合 OK).
   **Fix landed**: 解码端公式统一.

Gap A (float demand): CONFIRMED, Phase 1.5+ defer (preprocess scale).
Gap B (commodity_routes 无 prod fill): CONFIRMED, Phase 1.5+ defer (wiring).

# Round 2 任务 — 直接给答案不要 think-out-loud

**先输出 Verdict + 结构化 finding, 再展开 reasoning. 不要边想边写.**

1. R1#1 iterative DFS fix verify: 我的 fix 等价 recursive 吗? 找 corner case
   反例 (off-by-one / dead-end backtrack 漏 path / iter_ptr advance 错位)?
2. R1#3 bitset padding fix verify: 还有其他 file 用老公式吗?
3. F4 component_reach generator 单独 deep review (round 1 主要 verify F2).
4. **Round 2 new findings**: 至少 2-3 个 (BLOCKER/HIGH/MEDIUM 都行).

## 格式 (必须严格, 不要 think-out-loud)

```
## Round 2 Verdict
GO | GO_WITH_MINOR | CONCERN | NOT_GO  (一行)

## R1 Fix Verify
- R1#1 iterative DFS: CORRECT / PARTIAL / WRONG — 一段说明
- R1#3 bitset padding: CORRECT / PARTIAL / WRONG — 一段说明

## Round 2 New Findings

### Finding 1: [SEVERITY] file:line — title
问题 / reproduce / fix 建议. 每 finding ≤ 200 字.

### Finding 2: ...
### Finding 3: ...

## F4 component_reach Review
3-5 段 deep look. 重点: BFS / separator extraction / cert schema soundness.

## Sanity (3 disproved hypotheses)

1-3 段简短.

## 下一步建议
```

## Armor 规则

- 不接受 vague hyperbole (looks fine / ship-ready)
- GO verdict 必先列 3 种死法 + disprove
- critical claim 必 cite file:line

# 项目 1 句: 70x70 grid certified-exact LBBD, F2/F4 是 9 cut family 之二. 真数据 paths inline 在下方 (per v4 协议).



# 项目上下文 (3 句话)

- 70x70 grid Endfield 工业规划求解器, certified exact path, outer search candidate enumeration + 内层 LBBD (master → binding → routing → flow), 客观 max_lex(area, min_side)
- F2/F4 是 9 个 cut family 之二 (cutset / component_reach): routing infeasibility 子问题返不可行时, oracle 用 Menger min-cut (F2 边容量超 demand) 或 BFS 不连通 (F4 component disconnect) 提取 sound geometric cut 加到 master
- Phase 1.2 P1.2B-F5/F9 已经 GO (5 round Gemini); F2/F4 generator + helper 是这个 round 的新增 (commit `92224c4` master). Validator 已在 Phase 1.1 land, 这轮只 review generator + helper

# Round 1 你的任务 (v4 加严协议 — 不接受 GO ritual)

按重要性顺序:

1. **Spec-data gap focus** — 真数据 paths 我已 inline 在下方 DOC_PATHS. 实施 src 跟真数据接合时哪一步会 (a) crash, (b) FN (该发 cut 不发), (c) FP (发不该发的 cut)? 具体 file:line + 假设的字段名 / 类型 vs 真数据实际 schema.

2. **Soundness 数学**: Menger min-cut + BFS connectivity 算法实现是否 sound? Dinic 实现细节 (anti-parallel edge / 节点拆分 / 残差) 是否有 bug? min-cut 提取 (residual BFS 从 super_source) 是否漏算 cut edge?

3. **Fail-closed semantics**: 任何异常 / unknown / TIMEOUT / schema 错都必须返 []. 哪里可能 leak partial cut 或非 sound 路径?

4. **Cross-partition 不变量**: F2 `_has_patch_escape` 验 side_a ∪ side_b 完全 enclosed (没有 escape 到 free_cells 外其他 free cell). 这个 check 在 generator 跟 validator 一致吗? 如果 generator pass 但 validator reject 会怎样?

5. **Anonymity & multiset bound** (per state_machine_v2 §5): F2/F4 geometric mode 不绑 literal, 但 cert 含 commodity_id (F4) / contributing_commodities (F2) 是 active_assumption — assumption 跟 ghost binding 对吗?

## Armor strict mode (per memory [[gpt-review-prompt-armor]])

- **不接受** "looks fine / 完美 / 绝佳 / very solid / ship-ready" 等 vague hyperbole
- **不接受** GO 章 ritual ("All checks pass, ready to ship") — 如果真没大问题, 必至少给 3 个 high-risk hypothesis 你尝试 disprove 的过程 + 反驳每一个
- **critical claim 必 cite** file:line 或 spec §X 或 literature
- **GO verdict 必先列 3 种最可能死法** + 逐一 disprove
- 找 1 critical 比 100 surface comment 价值高 10× — 不堆 minor refactor 建议

## 提示我自己已经预察到的 2 个 spec-data gap (verify + push more)

Gap A (我推测 BLOCKER): `data/preprocessed/commodity_demands.json` 真数据 schema 是 `Dict[str, int|float]` (17 entries mix; e.g. `buckwheat: 5.5`, `oxalic_acid_solution: 0.55`), 但 BState.commodity_demands 类型签名 `Optional[Dict[str, int]]`. F2 generator `cutset_oracle.py:78` 的 `_is_strict_positive_int` gate (`isinstance(value, int) and not isinstance(value, bool) and value > 0`) **永远拒绝 float**, 17 commodities 中 5.5 / 0.55 等 float-demand 会被 generator silently skip — 永远不发 F2 cut. 这是真 BLOCKER 还是我误读? 请 verify + 给 fix 建议 (e.g. int(math.ceil(demand)) 还是改 BState schema 还是别的).

Gap B (我推测 BLOCKER): `state.commodity_routes` 字段在生产代码里完全没填充 site — `grep commodity_routes src/ -r` 显示**只在 cuts/ 内部读**, 没在 outside prod path 设. F4 generator `component_reach_oracle.py:68-69` 第一个 gate `if state.commodity_routes is None: return []`, 真接入 LBBD 时 100% 走 None 分支永远不发 cut. 这是 BLOCKER 还是 Phase 1.5+ 的 wiring 留到那时再做? 请 verify (grep 我做的可能漏 dynamic key set site).

Round 1 任务: verify Gap A/B + 找 round 1 第 3/4/5/... 个 finding. **不要重述** Gap A/B 当作新 finding (已在我提示里), focus 推进.

## Format

```
## Round 1 Overall Verdict
GO | GO_WITH_MINOR | CONCERN | NOT_GO

## Verify 我提示的 Gap A/B
- Gap A (float demand): CONFIRMED / PARTIAL / REJECTED — 详释 + fix 建议
- Gap B (commodity_routes 无 prod fill): CONFIRMED / PARTIAL / REJECTED — 详释 + fix 时机建议

## New findings (Round 1 catch — 不接受 0, 至少 3 个 high-risk hypothesis)

1. [SEVERITY: BLOCKER/HIGH/MEDIUM/LOW/INFO] file:line — 问题陈述 + reproduce + 建议 fix
2. ...
3. ...

## Sanity Arguments (如果真 GO, 至少 3 个 high-risk hypothesis disproved)

1. Hypothesis: <可能死法>. Disproof: <证明 src 已 cover>.
2. ...
3. ...

## 建议下一步 (Round 2 重点 / Phase 1.5+ defer)
```

# F2/F4 spec summary (来源 docs/research/p3_b_design_v2_20260521/cut_family_specs/)

"""


def build_doc_paths_section() -> str:
    sections = []
    sections.append("# DOC_PATHS: 真数据 schema inline (v4 协议硬要求 — Gemini 看不到本地文件)\n")

    # commodity_demands.json — F2 cut 的关键 input
    demands = json.loads((ROOT / "data/preprocessed/commodity_demands.json").read_text())
    sections.append(f"## data/preprocessed/commodity_demands.json\n")
    sections.append(f"Schema: Dict[commodity_id: str, demand: int|float]. {len(demands)} entries.\n\n")
    sections.append("Full content (verify mix of int + float):\n```json\n")
    sections.append(json.dumps(demands, indent=2, ensure_ascii=False))
    sections.append("\n```\n\n")

    # generic_io_requirements.json
    gen = json.loads((ROOT / "data/preprocessed/generic_io_requirements.json").read_text())
    sections.append("## data/preprocessed/generic_io_requirements.json\n")
    sections.append("Schema (top-level keys): metadata / required_generic_outputs / required_generic_inputs.\n\n")
    sections.append(
        "```json\n"
        + json.dumps({k: gen[k] for k in ("required_generic_outputs", "required_generic_inputs")},
                     indent=2, ensure_ascii=False)
        + "\n```\n\n"
    )

    # mandatory_exact_instances — F2/F4 用 mandatory placements 还是 candidate? 列 sample
    me = json.loads((ROOT / "data/preprocessed/mandatory_exact_instances.json").read_text())
    sections.append("## data/preprocessed/mandatory_exact_instances.json (preview)\n")
    sections.append(f"TYPE: {type(me).__name__}. ")
    if isinstance(me, list):
        sections.append(f"LEN={len(me)}. First entry sample:\n```json\n")
        sections.append(json.dumps(me[0] if me else {}, indent=2, ensure_ascii=False)[:1200])
        sections.append("\n```\n\n")
    elif isinstance(me, dict):
        sections.append(f"keys top={list(me.keys())[:6]}. Sample (first 1 commodity / instance group):\n```json\n")
        k0 = next(iter(me))
        sections.append(f"{k0!r}: " + json.dumps(me[k0], indent=2, ensure_ascii=False)[:800])
        sections.append("\n```\n\n")

    # candidate_placements
    cp = json.loads((ROOT / "data/preprocessed/candidate_placements.json").read_text())
    sections.append("## data/preprocessed/candidate_placements.json (preview)\n")
    sections.append(f"TYPE: {type(cp).__name__}. ")
    if isinstance(cp, list):
        sections.append(f"LEN={len(cp)}. First entry:\n```json\n")
        sections.append(json.dumps(cp[0] if cp else {}, indent=2, ensure_ascii=False)[:600])
        sections.append("\n```\n\n")
    elif isinstance(cp, dict):
        sections.append(f"keys top={list(cp.keys())[:6]}. ")

    # rules/canonical_rules.json (太大, 只放 schema 概述)
    sections.append("## rules/canonical_rules.json (太大, 只 cite path)\n")
    sections.append("Per PROJECT_LOCK, consolidated preprocess/recipe/target/commodity truth. Phase 1.2 F2/F4 不直接读此文件, 但若 commodity_routes 真数据来源是它的某个 sub-section, 请 flag.\n\n")

    # commodity_routes — 是 BState field 不是真数据文件
    sections.append("## BState.commodity_routes (字段)\n")
    sections.append("Schema (per src/cuts/lifecycle.py L390-L391): `Optional[Dict[str, JsonDict]]`, value 是 `{'src': (x,y), 'sink': (x,y)}`.\n\n")
    sections.append("**`grep commodity_routes src/ -r` 显示**: 只 cuts/ 内部 read, 没在 `src/preprocess/`, `src/search/benders_loop.py`, `src/models/` 任何 prod-side dataclass / loader 中 set. F4 generator gate `if state.commodity_routes is None: return []` 在 prod 100% 走 None.\n\n")

    return "".join(sections)


def build_src_section() -> str:
    s = ["# F2/F4 src (full content inline)\n\n"]
    for rel in SRC_FILES:
        s.append(f"### FILE: {rel}\n```python\n")
        s.append(read(rel))
        s.append("\n```\n\n")

    s.append("# Validator reference (Phase 1.1 已 land, 这轮不 review 主体, 但 cross-check generator 跟 validator schema 一致性时需 reference)\n\n")
    for rel, note in VALIDATOR_REFERENCES:
        s.append(f"### {rel} — {note}\n```python\n")
        content = read(rel)
        # truncate long files to first 280 lines
        lines = content.splitlines()
        if len(lines) > 280:
            s.append("\n".join(lines[:280]))
            s.append(f"\n# ... ({len(lines) - 280} more lines truncated)\n")
        else:
            s.append(content)
        s.append("\n```\n\n")
    return "".join(s)


def build_spec_section() -> str:
    s = []
    for rel in SPEC_FILES:
        s.append(f"## SPEC: {rel}\n")
        s.append(read(rel))
        s.append("\n\n")
    return "".join(s)


def main() -> int:
    key = os.environ.get("KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        print("ERROR: set KEY=<api_key> in env.", file=sys.stderr)
        return 2

    prompt_text = (
        PROMPT_HEADER
        + build_spec_section()
        + build_doc_paths_section()
        + build_src_section()
        + "\n\n# 完. 严格按 Format 输出, 不省任何 section. 提醒: 不 GO ritual, 真没 critical 也给 3 个 disproved hypothesis.\n"
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
    print("calling Gemini 3 pro ...")
    t0 = time.monotonic()

    # Per memory [[gemini-math-consultant]]: model name 可能浮动. 2026-05-24
    # API list 显示 stable: gemini-3.1-pro-preview, gemini-3-pro-preview.
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
        print("Failed to extract text from response:", parsed, file=sys.stderr)
        return 1
    (HERE / "gemini_response.md").write_text(verdict_text, encoding="utf-8")
    print(f"Response written ({len(verdict_text)} chars).")
    print("---")
    print(verdict_text[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
