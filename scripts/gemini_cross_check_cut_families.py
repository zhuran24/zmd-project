#!/usr/bin/env python3
"""Gemini cross-check Phase 0 Family 1/6/7 spec.

Per [[feedback_gemini_review_algorithm_math]]: 算法/数学层 spec land 后必须
发 Gemini cross-check 或独立做一遍. Gemini 看不到本地文件 → prompt fat-context
全 paste relevant doc.

Output: /home/zhuran24/linwin_share/gemini_cut_family_review_response.md
"""
from __future__ import annotations

import os
import json
import sys
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

# Relevant docs (按 logical 顺序 paste)
# v3 (round 16): Day 17 全部 4 commit — 6 新 family spec + F5 fixture + watcher v3.2
DOC_PATHS = [
    # 27 lever 死路 timeline
    "docs/research/p3_b_design_v2_20260521/paradigm_death_timeline.md",
    # round 14-17 答复 (历史 context)
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_14_cut_families.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_15_followup.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_16_day17.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_17_followup.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_18_phase0_go.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_19_f9_critical.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_20_all_clear.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_21_quarantine_fix.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_22_phase0_close.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_23_absolute_final.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_24_a_layer.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_25_phase1_ready.md",
    # Phase 0 final close doc
    "docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md",
    # Day 18 A集成层
    "PROJECT_LOCK.md",
    "docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md",
    "scripts/b_design_v2_exit_criteria.py",
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

## 本次 cross-check 目的 (round 26) — round 25 fix 验

Round 26. round 25 给 GO verdict + 2 Phase 1 实施隐患 (B1 script #6 detail 漏
+ B2 RSS 测量碎片化陷阱). 我按 round 25 修了 commit fe807ed (Day 18c):

- script #6 detail keys 加 cut_store_peak_mb_per_worker / rss_peak_mb_per_worker
- PROJECT_LOCK §3A 加 RSS 测量 invariant (Phase 1 ramp report 必 emit
  rss_peak_mb_per_worker field, 禁用 sys.getsizeof / JSON string len)
- PHASE_1_PLAN R5 加 RSS mandate (psutil.Process.memory_info().rss)
- script #6 prefer rss_peak_mb_per_worker, fallback 逻辑大小

round 26 任务:

### 任务 A: 验 round 25 2 修对
- script #6 detail keys 加全了?
- PROJECT_LOCK §3A RSS invariant 措辞够严 — 防 Phase 1 实施静默退回 sys.getsizeof?
- script #6 dual-field check (rss preferred + fallback) 逻辑对吗?

### 任务 B: 找新 finding (最后一扫)
Phase 0 + A 集成层 + 25 round cross-check 后还有任何 sound bug / Phase 1
实施盲区吗?

### 任务 C: 进 Phase 1 ready final verdict

## 3 段 A/B/C. 找不到 bug 写"Phase 1 编码 GO, 不再 cross-check 此层".
## 中文优先.
"""

## OLD round 25 prompt:
_old_round_25 = """## 本次 cross-check 目的 (round 25) — A集成层 round 24 修验

Round 25. round 24 给 7 finding (1 致命 RAM + Lock 矛盾 + 目录脱节 + 漏测/
漏 risk). 我按 round 24 verdict 修了 commit 3e0a20b (Day 18b):

A1 fixes:
- A1.1 加 #28 F8 Liang-Barsky test + #38 F9 area-based test (CRITERIA dict ID-keyed)
- A1.2 致命 RAM: 12 GB/worker → 5 GB/worker (RAM budget 16+20+8=44 < 48 GB)
- A1.3 加 #9 cut store rotation/GC test
- A1 D1 修 cut file glob: data/cuts/{active,quarantine}/*.json 分子目录

A2 fixes:
- B1 §4 加 Capacity-based Eviction 豁免 (解 Lock vs Plan 冲突, 工程兜底不属 Step 10)
- B2 §3A 加 F9 area-based counting lock (焊死 round 20 finding 防退化)

A3 fixes:
- C1 P1.4 明确加 ghost_geometry.py
- C2 加 R6 F9 QuickXplain 耗时风险 + 缓解 (稳健: Phase 1 不 minimize)
- C3 smoke test 提前 P1.20 内存 only (解耦算法 bug vs IO bug)

state: 1 PASS / 10 PENDING_PHASE_1 / 0 FAIL.

round 25 任务:

### 任务 A: 验 round 24 7 finding 修对
- A1.2 RAM 计算修对吗 (16 master + 4×5 worker + 8 other = 44 GB)? 漏 OS/buffer?
- A1.1 #28 #38 criterion 设计合理吗?
- A1 D1 cut glob 兼容 flat + active/quarantine 分目录, edge case 漏没?
- B1 capacity-based eviction 豁免措辞够严吗 — 防 Phase 1 实施时 silent 滑回
  semantic expiry?
- B2 F9 area-based lock 措辞防退化够?
- C3 smoke test 解耦真的能区分算法 bug vs IO bug?

### 任务 B: 找新 finding (Phase 0 + A 集成层全图最后扫一次)

### 任务 C: Phase 0 + A 集成层 → Phase 1 ready verdict

## 3 段 A/B/C. 找不到 bug 写 "可启动 Phase 1 编码".
## 中文优先.
"""

## OLD round 24 prompt:
_old_round_24 = """## 本次 cross-check 目的 (round 24) — A集成层验证

Round 24. Phase 0 已 close (round 23 verdict). 现在跑 A 集成层 (Day 18-21
governance) 后 Gemini 验. 用户加严 rule v3: "决策按稳健方向选, 任何决策性
输出必 Gemini 审查" — 不只算法/数学层, governance/plan/lock 也走.

Day 18 A集成层 commit 33c18b4 land 3 件:

### A1 — scripts/b_design_v2_exit_criteria.py (168h 启动 8 硬条件 actionable
checklist):
- #1 boundary 语义冻结 (automated, Phase 0 done ✓ PASS)
- #2-#7 pending Phase 1 (test_family / ramp 数据)
- #8 persisted cuts replay 100% pass (pending data/cuts/)
CLI --strict/--json/--criterion. 现状 1 PASS / 7 PENDING_PHASE_1 / 0 FAIL.

### A2 — PROJECT_LOCK.md update (cut object 一等公民边界):
- §2B 新 source-of-truth: cut_lifecycle/family_specs/state_machine_v2 +
  data/cuts/*.json (Phase 1 启用后)
- §3A 6 新 invariant: Exactness FP=0 / group-orbit symmetry / family↔mode
  一致性 / Scope-aware HOLD vs Quarantine / F9 paradigm 降级 lock / 代数 vs
  几何分工
- §4 加 2 条 Forbidden: B Design v2 9 步 lifecycle 不可绕过 / silent recovery
  禁止 (validator fail-closed)

### A3 — PHASE_1_PLAN.md (Phase 1 实施计划):
- src/cuts/ 路径表 (lifecycle/store/replay/helpers/families/oracles/assumptions/
  monitor)
- 4 phase 实施顺序 (1.0 framework / 1.1 F1-4 / 1.2 F5-9 / 1.3 integration /
  1.4 ramp 5-266 inst)
- 工时 Claude pace ~22-28 day + wall clock 3-5 day = ~30-40 day
- 5 风险 + 缓解 + decision points

round 24 任务:

### 任务 A: 验 A1 8 exit criteria 设计 sound
- 8 条 criterion 真的覆盖 168h 启动前所有 sound 风险吗?
- pass_condition 量化是否合理 (e.g. #7 f5_ratio < 50% + core_size < 20 阈值
  是否准)?
- check_kind (automated / ramp_data / telemetry / code_inspection) 分类清楚?
- 漏什么 criterion? 例如 cut store disk rotation / GC / multi-thread race
  这些 Phase 1 工程 risk 是否该进 exit criteria?
- script CLI 设计 (--strict, --json, --criterion) 足够吗?

### 任务 B: 验 A2 PROJECT_LOCK update 完备性
- §2B Cut Object Boundary 列的 source-of-truth + postprocess boundary 完整吗?
- §3A 6 个新 invariant 真的 cover 23 round Gemini cross-check 共识吗? 漏哪条?
- §4 加的 2 条 Forbidden Change 措辞够严吗?
- 跟现有 §1-§5 兼容吗 (例如老 §4 已禁 6 步 lifecycle bypass, 新 §4 加 9 步,
  不会矛盾)?

### 任务 C: 验 A3 Phase 1 plan 工程可行性
- src/cuts/ 路径表合理吗? 哪个 sub-module 应合并 / 拆分?
- 4 phase 顺序 (1.0 framework → 1.1 F1-4 → 1.2 F5-9 → 1.3 integration → 1.4
  ramp) 依赖图正确吗? Family 7 依赖 Family 5/8 是否反映在顺序?
- 工时估稳健吗? Claude pace ~22-28 day 多了少了?
- 5 风险 + 缓解充分吗? 漏什么风险?
- decision points (Phase 1 中必 Gemini check) 清单合理吗?

### 任务 D: 跨 A1+A2+A3 一致性 + 找 sound bug
A1 8 criterion / A2 lock invariant / A3 plan 三者交叉对齐吗? 比如:
- A1 #7 f5_ratio < 50% 跟 A2 §3A "F9 paradigm 降级" + plan 1.2 P1.11 F5 monitor
  对齐吗?
- A1 #8 persisted cuts replay 跟 A2 §4 "9 步 lifecycle 不可绕过" + plan 1.0
  P1.3 replay.py 对齐吗?
- A3 plan §3 P1.21 cut store persist 跟 A2 §2B "data/cuts/*.json" source-of-
  truth 对齐吗?

## 回答格式
4 段 A/B/C/D. 找不到 bug 写"A 集成层无懈可击, 可启动 Phase 1".

## Reply 中文优先.
"""

## OLD round 23 prompt:
_old_round_23 = """## 本次 cross-check 目的 (round 23)

Round 23. round 22 给了 verdict "Phase 0 无懈可击, 进 Phase 1" + 1 行
watcher 漏注册 finding (F1 §8 漏加 by_ghost). 我按 round 22 finding 修了
commit 8ea6d00 (Day 17k FINAL CLOSE):

- F1 §8 add_watchers_region_capacity 加 `if ghost_rect_id != GHOST_AGNOSTIC:
  store.by_ghost_watcher[...].add(cut_id)` (1 行修复)
- 新 PHASE_0_CLOSE.md doc (总结 28 commit + 9 family + 22 round trace + 5
  invariant + Phase 1 起步 defer 清单)
- F16 反例 verdict (代数归 Master 不进 Cut framework, 1 行 master CP-SAT 约束)

round 23 是 Day 17k commit 本身的 cross-check (用户加严 rule "先 check 再
继续" — Day 17k 也得过).

### 任务 A: 验 Day 17k 改对

1. F1 §8 by_ghost watcher 1 行修法 sound 吗? 跟 v3.2 watcher 表 (F1 不显
   含 by_ghost 因为是 GHOST_AGNOSTIC default) 一致吗?
2. PHASE_0_CLOSE.md doc 内容 self-consistent 吗 (28 commit / 9 family / 22
   round / invariant)? 有没有错引/漏列/矛盾?
3. F16 反例 verdict ("代数归 Master 不进 Cut") 真的对吗? Master CP-SAT 加
   1 行线性约束 sound + complete 吗?

### 任务 B: Phase 0 真 ABSOLUTE final verdict
你 round 22 已给 GO verdict, round 23 是最后一次显微镜. **找不到新 bug 写
"Phase 0 已无懈可击, 进 Phase 1 编码"**.

### 任务 C: F11+ 反例 — 最后一次寻找

## 3 段 A/B/C. **找不到 bug 写 "Phase 0 已无懈可击, 进 Phase 1 编码"**.
## 中文优先.
"""

## OLD round 22 prompt:
_old_round_22 = """## 本次 cross-check 目的 (round 22)

Round 22. round 21 给了 2 False Quarantine bug (B1 cut_lifecycle GHOST_AGNOSTIC
vs blocked_cells_hash / B2 F9 Validator schema 错位). 我按 round 21 修了
commit 7f38842 (Day 17j):

- cut_lifecycle v3.2.2 CutScope 加 `exterior_blocks_hash` field + §4 Step 3
  dispatch (GHOST_AGNOSTIC 验 exterior, 绑 ghost 验全 blocked)
- F9 v1.5 Validator step 3 改 area-based `witness_area_in_W > max_allowed_area`
  跟 v1.4 evaluator 一致

round 22 是 Phase 0 close 前的 final final check. 任务:

### 任务 A: 验 round 21 2 修对
- v3.2.2 hash 拆分 + dispatch sound 吗? GHOST_AGNOSTIC cut 在 ghost 改时跨
  candidate attach 真 work?
- F9 v1.5 Validator area-based check `witness_area_in_W > max_allowed_area`
  跟 v1.4 evaluator 完全契合吗? round-trip (gen → serialize → deserialize →
  validate) 仍 sound?

### 任务 B: 找新 finding — 这次目标是**找不到**

Phase 0 已 21 round (14-21) cross-check 修了 11 个 finding. 现在状态是
否真的 sound + complete? 还能找到任何 sound bug / schema 漏 / watcher
issue / dispatch race 吗? **找不到就明说**, Phase 0 close.

### 任务 C: Phase 0 absolute final verdict

### 任务 D: F11+ 反例 — 最后一次

## 4 段 A/B/C/D. **找不到 bug 写 "Phase 0 已无懈可击, 进 Phase 1"**.
## 中文优先.
"""

## OLD round 21 prompt:
_old_round_21 = """## 本次 cross-check 目的 (round 21)

Round 21. round 20 给了 F9 v1.3 严重 FN (全包含计数对面积溢出漏剪). 我按
round 20 B2 修了 commit 4be39d0 (Day 17i):

- F9 v1.4 evaluator 改 `sum(|pose_cells ∩ W|)` 直接数占用格子, 不数 facility
  个数. 跟 F9 降级面积 paradigm 自然吻合.
- cert 加 `max_allowed_area` field 替代 `density_K` (deprecated).

F9 evaluator 完整演进 trace (你 review 完整):
- v1.0 over-count (any cell in W) → FP (round 18 B2 修)
- v1.2 origin-in-W → FP (round 19 B1 修, 修错)
- v1.3 all-in-W → FN (round 20 B2 修)
- v1.4 sum cells in W → sound (FP=0, FN=0) ✅

round 21 任务:

### 任务 A: 验 F9 v1.4 终于 sound 吗?
- `occupied_in_window = sum(...)` 计数对 FP/FN 严密吗?
- max_allowed_area cert field 是 oracle 给出, 验跟 Oracle area_capacity_overflow
  凭证 schema 一致吗?
- 还有 F9 边角 case (e.g. cell_owner 没 carry, ghost 占 W cells, etc) 没覆盖吗?

### 任务 B: 找新 finding (任何 family, 任何 schema, 任何 watcher)

### 任务 C: Phase 0 关停 verdict — 是否还有任何 sound 漏洞

### 任务 D: F11+ 反例

## 4 段 A/B/C/D. 找不到 bug 写"没找到 bug, Phase 0 已无懈可击 close".
## 中文优先.
"""

## OLD round 20 prompt:
_old_round_20 = """## 本次 cross-check 目的 (round 20)

这是 round 20. round 19 给了 F9 v1.2 修错 (Reference Cell unsound 引入新 False
Positive) + F9 paradigm 级 Unsound (拓扑死锁泛化几何密度 unsound). 我按
round 19 verdict 修了 commit 260f860 (Day 17h):

- F9 v1.3 计数严苛化: evaluate_geometric 改 `all(c in W for c in pose_cells)`
  全包含计数 (v1.0 over-count → v1.2 under-rigour → v1.3 严苛)
- F9 v1.3 paradigm 降级: 仅 area_capacity_overflow 触发, binding/routing/pcr
  INFEASIBLE 走 Family 5 fallback. witness_kind enum 仅留 area_capacity_overflow.

round 20 任务:

### 任务 A: 验 round 19 F9 v1.3 修对
- 全包含计数 `all(c in W for c in pose_cells)` sound 吗? 跟 v1.0 over-count /
  v1.2 under-rigour 比为什么这次严苛 sound 而不偏 False Negative 过多?
- paradigm 降级 (仅 area_capacity_overflow) 接受 Class C fallback Family 5
  代价 — 这个降级方向数学上合理吗? Class C 退化具体多严重 / Phase 1 telemetry
  能监控吗?

### 任务 B: 找新 finding

### 任务 C: Phase 0 final final verdict (final 决定进 Phase 1)

### 任务 D: F11+ 反例

## 回答格式 4 段 A/B/C/D.
## Reply 中文优先.
"""

## OLD round 19 prompt:
_old_round_19 = """## 本次 cross-check 目的 (round 19)

这是 round 19. round 18 给了 GO verdict + 2 致命 bug (B1 F1 GHOST_AGNOSTIC vs
cap_R 含 ghost / B2 F9 partial intersection). 我按 round 18 verdict 修了
commit fb2dcb4 (Day 17g):

- F1 v1.2: 加 condition — cap_R 含 ghost contribution 时 scope.ghost_rect_id
  必非 AGNOSTIC, 只 ghost_cells ∩ R == ∅ 允许 GHOST_AGNOSTIC
- F9 v1.2: evaluate_geometric 改 Reference Cell 计数, 只 facility reference
  cell 落 window 内才 +1, 防 partial intersection 误算

round 19 任务:

### 任务 A: 验 round 18 2 修对
- F1 v1.2 condition check: `ghost_cells ∩ R == ∅` 决定 AGNOSTIC vs 绑 ghost_rect_id
  sound 吗? F1 fixture 仍 AGNOSTIC 安全吗 (反例用 exterior_blocks 不是 ghost)?
- F9 v1.2 Reference Cell 计数: 用 left-top origin / cell_owner 反查 placed_ref
  对吗? edge case (slot 占 cell 不连续 / pose origin 在 ghost / 多 cell pose
  origin 顺序定义)?

### 任务 B: 找新 finding (sound / schema / watcher / dispatch)

### 任务 C: Phase 0 收尾 final verdict
round 14-18 已 7 finding + 2 round 18 致命 = 9 finding 修. 现在状态可不可以
进 Phase 1 编码? 还是有结构性漏洞?

### 任务 D: F11+ 反例

## 回答格式
4 段 A/B/C/D. 找不到 bug 写"没找到 bug, 已 cross-check 完毕".

## Reply 语言
中文优先.
"""

## OLD round 18 prompt:
_old_round_18 = """## 本次 cross-check 目的 (round 18)

这是 round 18. round 17 给了 2 新 bug (B1 F8 watcher / B2 F9 slot ID) + A4
sweep 推荐. 我按 round 17 verdict 修了 commit ab921b1 (Day 17f):

- F8 v1.1 watcher 改监听 PoolPole ∩ BoundingBox(facility, R_conn) 内全合法
  grid cell, 不只 candidate_pole_cells
- F9 v1.1 oracle_assignment_witness 去 slot ID 改 (group, pose) tuple
- F1-F4 fixture 顶部 changelog 段加 F8/F9 静默说明

round 18 任务:

### 任务 A: 验 round 17 2 新 bug 修对
- F8 v1.1 watcher BoundingBox 算法 sound 吗? `iter_cells_in_box` + `is_legal_pole_candidate_cell` 接口对吗?
- F9 v1.1 去 slot 后 validator 验只看 "K+1 pose 同时存在" 在 multi-slot pose
  case (same pose 出现多次 different slot) 怎么处理? Counter 比较 vs Set 比较?

### 任务 B: 新 finding (sound / schema / watcher / dispatch)

### 任务 C: 整体 Phase 0 收尾 verdict
我们 round 14-17 4 轮 cross-check 修了 7 个 finding (3 致命 sound bug + 2
schema 漏 + 2 新 watcher/state-dep bug + 1 watcher 误入 + 1 算法 unsound).
现在 9 family + cut_lifecycle v3.2.1 + watcher v3.2.1 状态如何? 还能不能在
Phase 0 找到 sound bug? 还是可以进 Phase 1 编码实施?

### 任务 D: F11+ 反例
9 family 修后, 还有什么 INFEASIBLE master assignment 现 9 family 全静默?

## 回答格式
分 4 段 A/B/C/D. 找不到 bug 写"没找到 bug, 已 cross-check 完毕".

## Reply 语言
中文优先. 输出长度不限.
"""

## OLD round 17 prompt:
_old_round_17 = """## 本次 cross-check 目的 (round 17)

这是 round 17. round 16 (已 paste) 给了 4 finding (A1 F4 ID 校验 / A2 F3
watcher / B1 F8 ghost_blocks_line / E1 F5 表 F9). 我按 round 16 verdict
修了, commit 1ece80a (Day 17e), 4 文件改:
- cut_family_specs/04_component_reach.md v1.1: 删 step 4 blocking_facilities
  ID 校验, geometric 哲学只认空间
- cut_lifecycle_v2.md v3.2.1: 表移除 F3 from by_ghost_watcher
- cut_family_specs/08_power_grid_reach.md v1.1: 改 ghost_blocks_line 严格
  Liang-Barsky AABB intersection
- red_fixtures/F5_power_grid_disconnect.md: 静默表加 Family 9

round 17 任务:

### 任务 A: 验 round 16 4 finding 修对
每条修法 sound 吗? 引入新 bug 吗?
- F4 v1.1 删 ID 校验后, separator_cell not in free_cells 单一校验充分吗?
- F3 v3.2.1 移除 by_ghost_watcher 后, ghost change 时 F3 不再 invalidate, 但
  ghost change 可能改 state.free_cells, F3 cert.front_cell 是否还在 free 没
  watcher 触发 evaluate? 漏不漏?
- F8 v1.1 Liang-Barsky algorithm — 算 ghost 是 axis-aligned rectangle 严格.
  ghost 是离散 cell grid 上 (60, 60)..(74, 74) 不是连续 float, 边界 inclusive
  / exclusive 怎么处理? 我现 line_segment_intersects_aabb 用 (x_min, y_min) =
  (rect[0], rect[1]), (x_max, y_max) = (rect[0]+h, rect[1]+w) — pole pose 在
  ghost cell (60, 60) 应被 block 吗? Edge case 问题
- F5 fixture E1 静默表加 F9 OK, 但其他 fixture (F1-F4) 静默表也应该 sweep
  加 F9 / F8 列么?

### 任务 B: 找新 Bug
基于 round 14/15/16 修后的 v3.2.1 + v1.1 spec 看现在状态:
- 还有什么 sound / soundness 漏洞?
- Schema 字段还有什么遗漏 (类比 round 14 finding #5 cells_per_pose)?
- watcher 还有 family 误入 / 漏入吗?
- evaluate_cut / evaluate_geometric / Validator dispatch 有没有 race / staleness?

### 任务 C: 验 F10 反例 (round 16 task F) 处理方向
round 16 给 F10 Kinematic Belt Knot 反例 (U-turn 空间不够), 推荐 Family 4 升级
Kinematic Reachability (Stateful BFS + port_directions field). 我 defer Phase 1.
问:
- defer Phase 1 合理吗? 还是 Phase 0 必加?
- 升级 Family 4 vs 加 Family 10 哪个好? round 16 你给 Family 4 升级建议, 现
  reconsider 仍是吗?
- belt routing 还有 类似 kinematic 反例吗? (e.g. 高速带速度限制 / 多带共享
  belt cell 限制 / 带方向锁死 case)

### 任务 D: 找 F11+ 反例
9 family + 修后 v3.2.1 watcher + Liang-Barsky 算法严格后, 还有什么 INFEASIBLE
master assignment 现 9 family 全静默?

## 回答格式
分 4 段 A/B/C/D. 每条具体 (file path + § + 行号). 找不到 bug 写"没找到 bug,
已 cross-check 完毕".

## Reply 语言
中文优先, 数学符号 ASCII / latex 都行. 输出长度不限 — 是 Phase 0 关键 gate.
"""

## OLD round 16 prompt (no longer used):
_old_round_16 = """## 本次 cross-check 目的 (round 16)

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
    prompt_path = SHARE / "gemini_cut_family_review_prompt_round_26.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    print(f"[gemini] prompt saved to {prompt_path}", file=sys.stderr)

    try:
        result = call_gemini(prompt)
    except Exception as e:
        print(f"[gemini] ERROR: {e}", file=sys.stderr)
        return 1

    text = extract_text(result)
    output_path = SHARE / "gemini_cut_family_review_response_round_26.md"
    output_path.write_text(text, encoding="utf-8")
    print(f"[gemini] response saved to {output_path}", file=sys.stderr)
    print(f"[gemini] response size: {len(text)} chars", file=sys.stderr)

    # Print head of response
    head = "\n".join(text.split("\n")[:50])
    print("\n=== Response head (50 lines) ===\n" + head, file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
