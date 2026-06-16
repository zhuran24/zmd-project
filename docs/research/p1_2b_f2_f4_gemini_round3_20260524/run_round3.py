#!/usr/bin/env python3
"""Phase 1.2 P1.2B-F2/F4 Gemini round 3 cross-check (verify R2#3 fix + last catch).

Per memory [[gemini-review-algorithm-math]] v3 (循环 until GO/minor) + v4
(real data paths + armor + 反 GO ritual).
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

VALIDATOR_REFERENCES = [
    ("src/cuts/families/cutset.py", "lines 1-260 (validator + helpers)"),
    ("src/cuts/families/component_reach.py", "lines 1-200 (validator)"),
]


PROMPT_HEADER = """你是 Dinic max-flow / LBBD / soundness 审查员。Endfield 工业规划求解器 Phase 1.2 P1.2B-F2/F4 **Round 3** cross-check (commit `d5e653d`).

# Round 1+2 摘要

R1 (CONCERN) 3 finding:
- BLOCKER Dinic `_dfs_blocking_flow` recursive → iterative fix landed (commit 01d368a).
- HIGH Phase 1.5+ cell-cap cross-check drop → Phase 1.5+ defer.
- LOW bitset padding 公式 → 统一 fix landed.

R2 (GO_WITH_MINOR) verify R1 CORRECT + 3 finding:
- F1 HIGH Phase 1.5+ node-split cell-cap drop → Phase 1.5+ defer (R1#2 重复).
- F2 MEDIUM cert `cut_size` 命名 + edge_capacity=1 假设 → Phase 1.5+ defer.
- F3 LOW F4 cert 漏 `blocking_facilities` → **fix landed (commit d5e653d)**:
  `cert_payload_dict[..., "blocking_facilities": []]` + 注释 Phase 1.5+ causation
  split 时填真值.

# Round 3 任务

按 v3 循环规则, 停止条件: GO 或只剩 Phase 1.5+ defer / nice-to-have. Round 3
是收尾轮.

1. **Verify R2#3 fix soundness**: cert_payload 加 "blocking_facilities": []
   - cert_hash 变 (不同 cert 不同 hash) — Phase 1.5+ 填非空时再变. 这是 expected 行为,
     不是 false dedup risk (因 oracle_cert_hash 是 sound identity, 内容变 hash 应变).
     请 verify 这个推理.
   - JSON `sort_keys=True` 时 "blocking_facilities" 字母序排在 "commodity_id" 前.
     hash 计算正确? cross-worker reproducibility 保留?
   - v1.1 validator 不 check 此字段 — 加 carry 不破现有 test (验证: 292 cuts pytest pass).

2. **Round 3 New finding** — push 找最后 1 个. 任何 severity OK. 真没就给 3 个
   deep hypothesis + disproof (cite file:line).

3. **F2 generator 边界 case** (round 1/2 没专门 review):
   - `cutset_oracle.py:137` `src == sink` skip — 边界对吗?
   - `cutset_oracle.py:140` bfs_component 单源 — src/sink 不在 free_cells 时 generator
     skip, 但 validator 会 schema_err 不能信. 这个 fail-closed path 对吗?
   - `cutset_oracle.py:159` `result.cut_capacity >= demand` 等号 skip — Menger 要严
     格 cut < demand 才 INFEASIBLE, 等号 feasible, skip 正确?

## 格式 (严格, 不要 think-out-loud)

```
## Round 3 Verdict
GO | GO_WITH_MINOR | CONCERN | NOT_GO (一行)

## R2#3 Fix Verify
CORRECT / PARTIAL / WRONG — 一段 (含 cert_hash 影响分析)

## Round 3 New Finding (1 个 minimum)

### Finding 1: [SEVERITY] file:line — title
≤ 200 字.

## F2 generator 边界 case
3 段 deep look (src==sink / src ∉ free / equality boundary).

## Sanity (2-3 disproved, reference file:line)

## 下一步建议 (Round 4 还要 or close?)
```

## Armor 同 round 1/2 (不 vague, GO 必先 3 死法 disprove, cite file:line)

# 项目 1 句: 70x70 grid certified-exact LBBD, F2/F4 是 9 cut family 之二. 真数据 paths inline 在下方.

"""


def build_doc_paths_section() -> str:
    sections = []
    sections.append("# DOC_PATHS: 真数据 schema inline (v4 协议硬要求)\n")

    demands = json.loads((ROOT / "data/preprocessed/commodity_demands.json").read_text())
    sections.append(f"## data/preprocessed/commodity_demands.json\n")
    sections.append(f"Schema: Dict[commodity_id: str, demand: int|float]. {len(demands)} entries.\n\n")
    sections.append("Full content (verify mix of int + float):\n```json\n")
    sections.append(json.dumps(demands, indent=2, ensure_ascii=False))
    sections.append("\n```\n\n")

    gen = json.loads((ROOT / "data/preprocessed/generic_io_requirements.json").read_text())
    sections.append("## data/preprocessed/generic_io_requirements.json\n")
    sections.append(
        "```json\n"
        + json.dumps({k: gen[k] for k in ("required_generic_outputs", "required_generic_inputs")},
                     indent=2, ensure_ascii=False)
        + "\n```\n\n"
    )

    sections.append("## BState.commodity_routes (字段)\n")
    sections.append("Schema: `Optional[Dict[str, JsonDict]]` value `{'src': (x,y), 'sink': (x,y)}`. Prod 100% None (Phase 1.5+ wire).\n\n")
    return "".join(sections)


def build_src_section() -> str:
    s = ["# F2/F4 src (full content inline)\n\n"]
    for rel in SRC_FILES:
        s.append(f"### FILE: {rel}\n```python\n")
        s.append(read(rel))
        s.append("\n```\n\n")
    s.append("# Validator reference (round 3 不主 review, 仅辅 reference)\n\n")
    for rel, note in VALIDATOR_REFERENCES:
        s.append(f"### {rel} — {note}\n```python\n")
        content = read(rel)
        lines = content.splitlines()
        if len(lines) > 200:
            s.append("\n".join(lines[:200]))
            s.append(f"\n# ... ({len(lines) - 200} more lines truncated)\n")
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
        print("Failed to extract text from response:", parsed, file=sys.stderr)
        return 1
    (HERE / "gemini_response.md").write_text(verdict_text, encoding="utf-8")
    print(f"Response written ({len(verdict_text)} chars).")
    print("---")
    print(verdict_text[:2500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
