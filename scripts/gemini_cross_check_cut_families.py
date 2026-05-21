#!/usr/bin/env python3
"""Gemini cross-check Phase 0 Family 1/6/7 spec.

Per [[feedback_gemini_review_algorithm_math]]: 算法/数学层 spec land 后必须
发 Gemini cross-check 或独立做一遍. Gemini 看不到本地文件 → prompt fat-context
全 paste relevant doc.

Output: /home/zhuran24/linwin_share/gemini_cut_family_review_response.md
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

API_KEY = "[REDACTED_GCP_API_KEY]"
MODEL = "gemini-3.1-pro-preview"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

REPO = Path("/home/zhuran24/claude-pj/zmd")
SHARE = Path("/home/zhuran24/linwin_share")

# Relevant docs (按 logical 顺序 paste)
# v3 (round 16): Day 17 全部 4 commit — 6 新 family spec + F5 fixture + watcher v3.2
DOC_PATHS = [
    # 27 lever 死路 timeline
    "docs/research/p3_b_design_v2_20260521/paradigm_death_timeline.md",
    # round 14/15 答复 (历史 context)
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_14_cut_families.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_15_followup.md",
    # B Design v2 framework (含 v3.2 by_ghost_watcher)
    "docs/research/p3_b_design_v2_20260521/state_machine_v2.md",
    "docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md",
    "docs/research/p3_b_design_v2_20260521/schema_update_v3.md",
    # Red fixtures (5 反例, F1-F4 sweep + F5 新)
    "docs/research/p3_b_design_v2_20260521/red_fixtures/README.md",
    "docs/research/p3_b_design_v2_20260521/red_fixtures/F1_boundary_saturation.md",
    "docs/research/p3_b_design_v2_20260521/red_fixtures/F2_shape_packing_hall.md",
    "docs/research/p3_b_design_v2_20260521/red_fixtures/F3_power_no_cover.md",
    "docs/research/p3_b_design_v2_20260521/red_fixtures/F4_ghost_scoped_replay.md",
    "docs/research/p3_b_design_v2_20260521/red_fixtures/F5_power_grid_disconnect.md",
    # 9 family spec (round 16 review target — 6 新 + 3 round 14/15 修过)
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/05_pattern_nogood.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/06_shape_packing_hall.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/07_power_hitting_set.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/09_density_envelope.md",
    # PoC (runtime 验证 reference)
    "docs/research/p3_b_design_v2_20260521/poc/README.md",
]


PROJECT_BACKGROUND = """\
# 项目背景 — 终末地 (Arknights: Endfield) 70×70 工业规划器 certified exact solver

## 求解目标
- 70×70 grid + 266 mandatory facility (132 manufacturing_3x3 + 49 manufacturing_5x5 +
  46 boundary_storage_port + 38 manufacturing_6x4 + 1 protocol_core)
- 目标: max_lex(area, min_side) — 最大化空 ghost rectangle 面积优先, min-side 次之
- 约束: 必精确 (certified exact, PROJECT_LOCK 不接 UNKNOWN / heuristic)

## 两层架构
- Outer: outer_search.py 枚举 candidate (ghost_rect area, min_side 降序)
- Inner: 每 candidate 跑 LBBD (master placement + binding port + routing belt + flow)
- Single base valley4_protocol_core 70×70, 单机 48 GB RAM, 168h campaign budget

## 27 lever 全死
之前 27 个 algorithmic lever 全 verdict 死路 (B1 pose-bool master / PCR-CUT /
SAC-Hull / D2 commodity flow / lever 24 augmented master / 等). master.solve
inherent 解不动. 路径已穷尽 cut 层 + master 层 + paradigm 层.

## B Design v2 (当前 paradigm)
重新设计 master + cut 框架, 走 cut object 一等公民路线:
- Master 不直接 solve, 通过 cut 累积学习 infeasibility
- Cut 是 first-class object (持久化, 跨 session, scope-aware replay)
- 5 cut family + 2 新 family (shape_packing_hall + power_hitting_set, v3 加)

## 之前 review 路径
- v14 review: GPT pro + Gemini round 12 + round 13 cross-check 找出 4 必修事
- 现 Phase 0 在 v14 review verdict 之后, 按 plan v3 推进
- 用户偏好 (memory feedback): 算法/数学层 spec land 后必须 Gemini cross-check

## 当前进度
Phase 0 Day 1-16b 已 land:
- Day 1-2 (commit 976bc10): boundary source-of-truth 冻结 + double-count bug 修
- Day 3-9 (commit 64c5317): 双线 design doc — state_machine_v2 (445 LOC) +
  cut_lifecycle_v2 (678 LOC, group/orbit-count + 10 步 scope-aware lifecycle)
- Day 10-12 (commit 4da7e30): F1-F4 red fixtures doc-only spec (反例几何 +
  hardcode cut 验表达力)
- Day 13 (commit 3dd3d63): schema_update_v3 propose 解 5 schema gap
- Day 14 (commit f861ba7): cut_lifecycle_v2 v3 land 5 gap
- Day 15 (commit 925157e): Family 1 region_capacity 完整 spec (489 LOC)
- Day 16a (commit 30b0a2d): Family 6 shape_packing_hall 完整 spec (523 LOC, v3 新)
- Day 16b (commit 824c9b6): Family 7 power_hitting_set 完整 spec (512 LOC, v3 新)

剩 Day 17-21: Family 2/3/4/5 (复用现有 L16/PCR-CUT/D2/boundary_constraints 实现) +
F1-F4 fixture sweep update + 集成 + 168h campaign 8 exit criteria.

## 本次 cross-check 目的 (round 16)

这是 round 16. round 14/15 历史 (已 paste cross_check/round_14 + round_15) —
3 致命 sound bug + 2 schema 漏 + F5 全局电力孤岛反例 + Class B/C 风险预警 +
Family 9 density_envelope 推荐你给的. 现在 round 16 验 Day 17 全部 4 commit:

- 17a (83d3242): Family 2 cutset (PCR-CUT 复用) + Family 3 port_exposure
  (boundary_constraints 复用) + Family 4 component_reach (D2 复用) + Family 5
  pattern_nogood (L16 deletion minimizer 复用)
- 17b (1c757ff): Family 8 power_grid_reach (F5 反例 owner, 独立 family per
  你 round 15 verdict)
- 17c (98daa07): Family 9 density_envelope (你 round 15 推 Class C mitigation)
- 17d (b1ff909): F1-F4 fixture sweep v3.1 + F5 fixture + cut_lifecycle §7 加
  6 维 by_ghost_watcher v3.2

### 任务 A: 6 新 family spec sound check (Family 2/3/4/5/8/9)

每 family 完整 spec 在 cut_family_specs/ 下. 验:
- 数学定义完整 (Family 2 Menger / Family 4 BFS / Family 8 pole jump graph /
  Family 9 oracle witness lift)
- Soundness proof 严密 (无 monotone 假设漏洞)
- Cert payload schema 跟 cut_lifecycle_v2 v3.2 一致, 没漏 cells_per_pose 类
  field
- Generator 复用 src/ helper 是 sound 包装 (e.g. Family 2 patch_routing_core
  复用 / Family 4 d2_separator 复用 / Family 5 L16 deletion_minimize)
- Validator 独立重算 — **不**走外部 state (跟 Family 1 v1.0 finding #5 同
  pattern 防 source rotated 时全 quarantine)
- evaluate_geometric vs evaluate_cut_literal_based dispatch 正确

### 任务 B: Family 8 power_grid_reach 验

我按你 round 15 verdict 写独立 family. 验:
- ghost_blocks_line 算法 (08 spec §5a 简化版): "ghost 中心点 ∩ line(p1, p2)" —
  sound 吗? 应该用 line-segment 真 intersect ghost rectangle, simplified 版有
  没漏 case?
- F7/F8 互斥 trigger 协议 (07/08 spec §9): CoverSet 空 → F7; 非空 disconnect →
  F8. dedup 政策对吗?
- v1.0 单 cause = ghost. cell_owner 挤压 power network (相邻 pole 被 facility
  占) 也可 disconnect — 现 v1.0 不拦. 多严重?

### 任务 C: Family 9 density_envelope 验

我按你 round 15 推荐写. 验:
- K bound 推导: "oracle 在 W 内放 m facility INFEASIBLE → K = m - 1 sound" —
  K binary search 紧化是必要的吗 (v1.0 直接用 m-1)?
- Window 选择: bounding rect of K+1 witness — sound 但可能太大. Phase 1
  shrink window 算法应该长啥样?
- 跟 Family 5 fallback dispatch: oracle generate 优先 lift F9, 失败回退 F5.
  fallback 决策什么时候应该走 F9 什么时候 F5?
- multi-group window: 现 v1.0 单 group. multi-group 是 NP-hard generalize 还
  是 trivial extension?

### 任务 D: cut_lifecycle v3.2 by_ghost_watcher 验

§7 加 6 维 by_ghost_watcher + on_ghost_rect_changed 工作流:
- v3.2 watcher 表 (Family 2/4/5/6/7/8/9 都加 by_ghost): 漏什么 family 吗?
- Performance: 168h 内 ghost change rate 估几次? worker 每次 sweep
  by_ghost_watcher 漏多大?
- by_blocked_cells 7 维 watcher 我 defer Phase 1 — 应该提前到 Phase 0 加吗?
- GHOST_AGNOSTIC cut 不入 by_ghost_watcher 但仍受 blocked_cells_hash 校验 —
  on_blocked_cells_changed event 缺没缺?

### 任务 E: F5 fixture + Family 8 spec 配合验

F5 fixture 反例: ghost width=15 > R_conn=10 power 不可跨. Family 8 应拦.
验:
- F5 反例 7 family 全静默原因表完整吗 (现 8 family 写 4/6 etc 静默, 9 没列)?
- Family 9 在 F5 是否静默 / trigger? F5 单 facility 不是 cluster — 应该静默
- Family 8 hardcode cut object (F5 fixture §4) 跟 spec §3 Cert schema 一致吗?

### 任务 F: 新轮反例 (基于全 9 family + 6 fixture 全 context)

你看完全 9 family + 5 fixture, 想新一轮反例: 哪个 INFEASIBLE master assignment
9 family 全静默? 写清反例几何 + 哪些 family 静默 why + 推荐第 10 family 还是
现有 family generalize.

## 回答格式
分 6 段 A/B/C/D/E/F. 每条具体 (file path + § + 行号). 找不到 bug 写"没找到 bug,
已 cross-check 完毕".

## Reply 语言
中文优先, 数学符号 ASCII / latex 都行. 输出长度不限 — 是 Phase 0 关键 gate.
"""


def load_doc(rel_path: str) -> str:
    abs_path = REPO / rel_path
    if not abs_path.exists():
        return f"# [MISSING] {rel_path}\n\n(file not found, skipping)"
    return f"# ============= START FILE: {rel_path} =============\n\n" + abs_path.read_text(encoding="utf-8") + f"\n\n# ============= END FILE: {rel_path} =============\n"


def build_prompt() -> str:
    parts = [PROJECT_BACKGROUND, "\n\n---\n\n# 接下来 paste 所有相关 doc (按 logical 顺序)\n\n---\n\n"]
    for rel in DOC_PATHS:
        parts.append(load_doc(rel))
        parts.append("\n\n")
    parts.append('\n\n---\n\n# 现在请按上面"回答格式"产出 cross-check 报告.\n')
    return "".join(parts)


def call_gemini(prompt: str) -> dict:
    body = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}],
        }],
        "generationConfig": {
            "temperature": 0.4,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": 65536,
        },
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    print(f"[gemini] POST {ENDPOINT[:80]}... payload {len(data) / 1024:.1f} KB", file=sys.stderr)
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    print(f"[gemini] {time.monotonic() - t0:.1f}s elapsed", file=sys.stderr)
    return result


def extract_text(result: dict) -> str:
    if "candidates" not in result:
        return f"# [API ERROR]\n\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
    parts = []
    for cand in result["candidates"]:
        for part in cand.get("content", {}).get("parts", []):
            if "text" in part:
                parts.append(part["text"])
    return "\n".join(parts)


def main() -> int:
    prompt = build_prompt()
    print(f"[gemini] prompt {len(prompt) / 1024:.1f} KB / {len(prompt) / 4:.0f} ~ tokens", file=sys.stderr)

    SHARE.mkdir(parents=True, exist_ok=True)
    prompt_path = SHARE / "gemini_cut_family_review_prompt_round_16.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    print(f"[gemini] prompt saved to {prompt_path}", file=sys.stderr)

    try:
        result = call_gemini(prompt)
    except Exception as e:
        print(f"[gemini] ERROR: {e}", file=sys.stderr)
        return 1

    text = extract_text(result)
    output_path = SHARE / "gemini_cut_family_review_response_round_16.md"
    output_path.write_text(text, encoding="utf-8")
    print(f"[gemini] response saved to {output_path}", file=sys.stderr)
    print(f"[gemini] response size: {len(text)} chars", file=sys.stderr)

    # Print head of response
    head = "\n".join(text.split("\n")[:50])
    print("\n=== Response head (50 lines) ===\n" + head, file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
