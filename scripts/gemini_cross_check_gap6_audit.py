#!/usr/bin/env python3
"""Round 30 Gemini AUDIT mode — Gap 6 F1 demand_R 数学决策 + 找漏的 spec-data gap.

Per [[gemini-prompt-audit-mode]] memory 修法:
- 真数据 (rules + preprocessed + candidate_placements 含 ports) 进 DOC_PATHS
- 直接问 spec-data gap, 不问 "src 跟 spec 一致吗"
- Armor: 拒 vague hyperbole, GO 必先列 3 死法, critical 必 cite file:line
- 反 GO 章 ritual

Output: /home/zhuran24/linwin_share/gemini_round_30_gap6_audit_response.md
"""
from __future__ import annotations

import os
import collections
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


# 真数据 + spec + src — 直接对比
DOC_PATHS = [
    # 真数据 (canonical_rules + preprocessed + viewer candidate_placements aggregate)
    "rules/canonical_rules.json",
    "data/preprocessed/generic_io_requirements.json",
    # 不直接传 mandatory_exact_instances 3194 行 (太大), inline aggregate
    # 不直接传 candidate_placements viewer (size 大), inline aggregate
    # Spec layer
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md",
    "docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md",
    "docs/research/p3_b_design_v2_20260521/state_machine_v2.md",
    # src layer (问题源)
    "src/cuts/lifecycle.py",
    "src/cuts/families/region_capacity.py",
    "src/cuts/oracles/region_capacity_oracle.py",
    "src/cuts/families/port_exposure.py",
]


def _build_data_aggregate() -> str:
    """Inline aggregate of mandatory_exact_instances + candidate_placements
    (避 prompt 过大). 真数据关键聚合."""
    parts = []

    with (REPO / "data/preprocessed/mandatory_exact_instances.json").open() as f:
        mei = json.load(f)
    op_counts = collections.Counter(i["operation_type"] for i in mei)
    ft_counts = collections.Counter(i["facility_type"] for i in mei)
    op_to_ft = {}
    for i in mei:
        op_to_ft.setdefault(i["operation_type"], i["facility_type"])

    parts.append("### 真数据 aggregate: mandatory_exact_instances.json (266 instances)\n")
    parts.append("```\nInstance schema (sample):\n")
    parts.append(json.dumps(mei[0], indent=2, ensure_ascii=False))
    parts.append("\n```\n\n")
    parts.append("operation_type → count (group_id 真分布):\n")
    for op, c in sorted(op_counts.items(), key=lambda x: -x[1]):
        parts.append(f"- {op}: {c}  (facility_type={op_to_ft[op]})\n")
    parts.append("\nfacility_type → count:\n")
    for ft, c in sorted(ft_counts.items(), key=lambda x: -x[1]):
        parts.append(f"- {ft}: {c}\n")

    parts.append("\n### 真数据 aggregate: candidate_placements (viewer) 含 ports\n")
    cp_path = REPO / "data/examples/industrial_planner/current_delivery/viewer/candidate_placements.json"
    with cp_path.open() as f:
        cp = json.load(f)
    parts.append("```\n")
    parts.append(f"top-level keys: {list(cp.keys())}\n")
    parts.append(f"facility_pools sizes:\n")
    for ft, poses in cp["facility_pools"].items():
        parts.append(f"  {ft}: {len(poses)} poses\n")
    parts.append("\nSample pose per facility_type (含 input_port_cells / output_port_cells):\n")
    for ft, poses in cp["facility_pools"].items():
        if poses:
            parts.append(f"\n{ft} sample:\n")
            parts.append(json.dumps(poses[0], indent=2, ensure_ascii=False))
            parts.append("\n")
    parts.append("```\n")

    # boundary_storage_port pose spatial distribution
    bp_poses = cp["facility_pools"]["boundary_storage_port"]
    on_left = sum(1 for p in bp_poses if p["anchor"]["x"] == 0)
    on_bottom = sum(1 for p in bp_poses if p["anchor"]["y"] == 0)
    parts.append(
        f"\nboundary_storage_port 54 pose 空间分布:\n"
        f"- anchor.x=0 (left baseline): {on_left}\n"
        f"- anchor.y=0 (bottom baseline): {on_bottom}\n"
        f"- 其他: {54 - on_left - on_bottom}\n"
        f"- 每 pose 占 3 cells (w=1, h=3)\n"
    )

    return "".join(parts)


PROMPT = """\
# Round 30 Gemini AUDIT mode — Phase 1.1 F1 spec-data gap audit

## 工作模式声明 (跟 r27/r28/r29 不同)

**我不要 GO 章. 我要 audit.** 之前 3 round 全 "GO" 我已经怀疑 prompt 模式问题
(spec ↔ src 一致 ≠ 跟真数据接合 sound). 这次我把真数据 inline 进来, 你**直接对
比 src 假设 vs 真数据 schema**, 找会 crash / FN / FP 的 file:line.

## Audit 强制规则

1. **拒 vague hyperbole**: 不准 "完美 / 完全一致 / 绝佳 / 高光 / 极其精准 / 严
   密无误 / 极其坚固" 这种 ritual praise.
2. **每个 critical claim 必 cite file:line** — 比如 "src/cuts/oracles/
   region_capacity_oracle.py:117 假设 canonical_rules[gid]['cells_per_pose']
   字段, 实测 canonical_rules.json 此 key 不存在".
3. **GO verdict 必先列 3 种最可能死法** 加 反驳每一种. 找不到 3 个就 NOT GO.
4. **找不到 critical 也必须列 ≥ 5 个 high-risk hypothesis** (with reasoning,
   不是 "looks OK").
5. **找 1 critical bug 比写 100 surface comment 价值高 10×**. 优先深 dig.

## 核心问题: Gap 6 — F1 demand_R 数学

我列了 spec §2b (cut_family_specs/01_region_capacity.md line 100-105):

```
demand_R = ∑_{g : P(g) ⊆ R} g.demand × cells_per_pose(g)
```

P(g) 是 group 的 placement_rule 谓词 (允许 cells 集合).

套到 boundary_io (placement_rule="left_or_bottom_boundary", 真 group_id 是
operation_type="boundary_io", 真 demand=46 instance × 3 cells/pose = 138 cells):

**严格按 spec §2b**:
- R = left_baseline (70 cells): P(boundary_io) = "left ∪ bottom" ⊄ left_baseline
  → boundary_io 对 left_baseline 的 demand_R 贡献 = 0. F1 cut 永不 trigger.

**但 spec §9 F1 反例 fixture** (line 478-510) 反例:
```python
contributing_groups=(("boundary_storage_port", 69),),  # demand_R=69
```
直接给 single-side demand=69 (= 23 instance × 3 cells). 数学跟 §2b 公式不一致.

我列两个可能 fix + 第三个:

### a) Union region (我倾向)
- R = left_baseline ∪ bottom_baseline = 139 cells (含 (0,0) 重叠)
- demand_R = 全部 boundary_io demand = 138 cells (P(boundary_io) ⊆ union ✓)
- cap_R = 139 - |ghost ∩ union| - |exterior ∩ union|
- cert fully static (跟 v3.2.2 §2a cap_R static spirit 一致)
- 信号粗 (不区分 ghost 块 left 还是 bottom)
- 数学严格按 spec §2b sound

### b) Per-side region + state-snapshot demand (spec PoC 反例的形式)
- R = left_baseline (70 cells)
- demand_R = 23 × 3 = 69 (saturation invariant: bottom 70/3=23 max → left 至少 46-23=23 instance)
- cert demand_R 不 fully static (依赖 bottom_cap, ghost 也 block bottom 时 stale)
- 信号精

### c) 两个都生

## 你的任务

### 任务 A: Gap 6 数学决策 — a 还是 b 还是 c 还是别的?

不准答 "都 sound 看场景". **强制 single recommendation + 数学证明 sound 性**:
- 你 recommend 的选项, 在 ghost block 任意分布下 (left ghost / bottom ghost /
  union ghost / 单边 ≥ 2 / 跨边 1+1 等 5 种 case), F1 cut 是否 sound 且不 FN?
- 反方选项哪条 case 会 FN 或 FP? 给 specific case 数字.
- 若选 b 或 c, cert 半-static 怎么处理 replay? cut_lifecycle_v2 v3.2.2 GHOST_AGNOSTIC
  dispatch 还 sound 吗?

### 任务 B: 找漏的 spec-data gap (我没列出来的)

我已列 Gap 1-7. **找 ≥ 3 个我没列的 spec-data gap** 跟真数据接合时会 crash/FN/FP.
每个必 cite file:line + 真数据具体 key/value + 期望 vs 实际差异.

我提示几个方向 (不限于):
- F3 ports_by_pose 是不存在 — 真 ports 在 pose 层 (含 dir + commodity). F3
  src 当前怎么 fail?
- PoseId int vs str — lifecycle.py 假设 int, 真数据 string. CutLiteral schema
  跟真数据接 cut 时哪步 crash?
- placement_rule 字段 facility_template 层. F1 oracle src `_enumerate_contributing_groups`
  遍历 canonical_rules entries 找 placement_rule 字段, 真 canonical_rules 顶
  层 keys 是 ['metadata', 'globals', 'routing_rules', 'facility_templates',
  'recipes', 'production_targets', 'commodity_metadata'] — 这些 entry 都没
  placement_rule 字段. 这函数返什么?
- BState 假设 state 持哪些字段? cell_owner key 类型 Cell=(int, int) 真数据 pose
  occupied_cells 是 [[int, int]] list of list. 转换层哪里?
- canonical_rules.json 实际数据中 "boundary_storage_port" 是 facility_template
  名, 但 spec PoC + src test 把它当 group_id 用. 这种命名重叠是 spec 错还是
  实施错?

### 任务 C: 是否 NOT GO Phase 1.1?

按你 audit findings, Phase 1.1 (P1.5-P1.8) 实际跟真数据接合时能跑通哪个 family?
0 个? 1 个? 全部 crash? 不准答 "需进一步测试". 给 binary verdict:
- "Phase 1.1 NOT GO until Gap A+B+C 修" + 列具体 file:line 必修
- 或 "Phase 1.1 真 production OK, 跟真数据 接合时只有 X 处会 crash" + cite

### 输出格式

3 段 A / B / C. 每段强制 cite file:line + 真数据具体 key/value. 不要 vague
hyperbole. 长度 ≥ 1500 字, 没找到 critical 也必填 hypothesis.
"""


def fetch_doc(path: str) -> str:
    p = REPO / path
    if not p.exists():
        return f"[MISSING: {path}]"
    return p.read_text(encoding="utf-8")


def build_prompt() -> str:
    parts = [PROMPT, "\n\n## 真数据 inline aggregate\n\n"]
    parts.append(_build_data_aggregate())
    parts.append("\n\n## Reference Materials (spec + src)\n")
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
    out_path = SHARE / "gemini_round_30_gap6_audit_response.md"
    out_path.write_text(text, encoding="utf-8")
    print(f"Response written: {out_path} ({len(text):,} bytes)")
    print("\n---\n")
    print(text[:8000])
    if len(text) > 8000:
        print(f"\n... [{len(text)-8000} more bytes in file]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
