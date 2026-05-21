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
# v2 (round 15): 补 timeline + cross_check round 14 答复 + src 实现
DOC_PATHS = [
    # 27 lever 死路 timeline (round 15 新加)
    "docs/research/p3_b_design_v2_20260521/paradigm_death_timeline.md",
    # round 14 答复 (你的)
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_14_cut_families.md",
    # B Design v2 framework (v1.1 修过)
    "docs/research/p3_b_design_v2_20260521/state_machine_v2.md",
    "docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md",
    "docs/research/p3_b_design_v2_20260521/schema_update_v3.md",
    # Red fixtures (4 反例)
    "docs/research/p3_b_design_v2_20260521/red_fixtures/README.md",
    "docs/research/p3_b_design_v2_20260521/red_fixtures/F1_boundary_saturation.md",
    "docs/research/p3_b_design_v2_20260521/red_fixtures/F2_shape_packing_hall.md",
    "docs/research/p3_b_design_v2_20260521/red_fixtures/F3_power_no_cover.md",
    "docs/research/p3_b_design_v2_20260521/red_fixtures/F4_ghost_scoped_replay.md",
    # 3 个 family spec (round 15 review target — v1.1 修后)
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/06_shape_packing_hall.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/07_power_hitting_set.md",
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

## 本次 cross-check 目的 (round 15)

这是 round 15. round 14 (你之前给的) 已发现 3 致命 bug + 2 schema 漏 + F5
全局电力孤岛反例. 我们按你的 round 14 verdict 修了 5 个 finding (commit
75e5f18), 然后补了 27 lever 死路 consolidated timeline (commit 1f1e051,
paradigm_death_timeline.md), 现在 round 15 跟你 follow-up:

### 任务 A: 验 round 14 5 finding 修对了
v1.1 改 (具体看 cut_family_specs 顶部 changelog):
- F7 v1.1: causation split (ghost-empty 单 literal / cell_owner-empty 多 literal
  含 blocking_facility_literals); cert 加 witness_kind enum + blocking field
- F6 v1.1: partition 改 static (只看 ghost+exterior, 不看 cell_owner); demand
  用 group.demand 不用 remaining_count
- F1 v1.1: cap_R 改 static (ghost+exterior only); cert 加 cells_per_pose
- cut_lifecycle v3.1: replay 加 step 3 blocked_cells_hash 校验 → 6 步
- F1 cert cells_per_pose field 已加

**验**: 修法 sound 吗? 有没有引入新 bug / 矛盾? F7 causation split 的多 literal
cut 跟 Family 5 pattern_nogood 重复吗? F6 demand 用 group.demand 跨层 sound 吗?

### 任务 B: 验 F5 反例评估 (paradigm_death_timeline.md §4)
我评估 F5 不撞 Path 14 PCR-CUT / Path 13 SAC-Hull / Lever 23 D2 (3 个最近似的
死路). 推荐 Day 17 加 Family 8 power_grid_reach 独立 family (不 generalize
Family 4 防 schema 字段冲突).

**验**: 这个评估对吗? F5 真不撞已死? Family 8 vs Family 4 generalize 哪个更
好? 你 round 14 推荐的 "Family 4 语义泛化跑 power-跃迁 BFS" 跟我的"加 Family 8"
有冲突, 请重新选定方向并给 reason.

### 任务 C: 看完 27 lever timeline 想第 2 轮反例
现在你能看到 27 lever 死路 + 4 共同 root cause + B 5 unsolved issue 完整 context
(paradigm_death_timeline.md). 重新想:
- Class B (cut accumulation 不够) — B Design v2 cut framework 有没有这个风险?
- Class C (cut family abstraction 不够, full no-good 退化) — Family 5
  pattern_nogood 在 132 个 manufacturing_3x3 cluster 时会不会退化 full no-good?
  permutation 撞 132! 墙?
- F6/F7/F8 跟之前 paradigm 撞同墙的 sub-pattern 有没有? (e.g. m1 cut lift 不
  跨数量级 / m5 trivial orbit)

### 任务 D: B 5 unsolved issue 现 spec 充分性评估
paradigm_death_timeline.md §3 列了 5 件 unsolved issue 当前 spec 状态. issue 3
(manufacturing cluster trap) 我标 ⚠️ "现 spec 不足". 你看 Family 5 pattern_nogood
在 132 个最大类 cluster 时:
- 拦 132! permutation 几何 trap 够吗?
- 走 full no-good 退化 (v14 review Pattern >50% stop-ship signal) 风险有多大?
- Day 18-21 怎么加 dedicated orbit-aware lift?

## 回答格式
分 4 段, A 验修法 / B 验 F5 评估 / C 新反例 / D unsolved issue. 每条具体 (file
+ § + 行号). 找不到 bug 写"没找到 bug, 已 cross-check 完毕".

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
    prompt_path = SHARE / "gemini_cut_family_review_prompt_round_15.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    print(f"[gemini] prompt saved to {prompt_path}", file=sys.stderr)

    try:
        result = call_gemini(prompt)
    except Exception as e:
        print(f"[gemini] ERROR: {e}", file=sys.stderr)
        return 1

    text = extract_text(result)
    output_path = SHARE / "gemini_cut_family_review_response_round_15.md"
    output_path.write_text(text, encoding="utf-8")
    print(f"[gemini] response saved to {output_path}", file=sys.stderr)
    print(f"[gemini] response size: {len(text)} chars", file=sys.stderr)

    # Print head of response
    head = "\n".join(text.split("\n")[:50])
    print("\n=== Response head (50 lines) ===\n" + head, file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
