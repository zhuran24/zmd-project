---
name: paradigm-session-2026-05-18-19
description: "2026-05-18 → 19 整 session: B1 paradigm 验证终态. Path 12 RAB-SEP / Path 13 SAC-Hull paradigm 全死, Path 14 PCR-CUT Phase 0 ✅ GO 待 Phase 1. 累 19 lever 死 + 3 GPT review iteration"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

# 2026-05-18 → 19 整 session 终态

## 整体进度

- **19 lever 全 verdict 死** (L1-L16 + Path 12 RAB-SEP + Path 13 SAC-Hull)
- **Path 14 PCR-CUT Phase 0 GO ✅** — paradigm 前提 verified, Phase 1-6 待实施
- 累 ~20 commits today, 3 GPT review 包 (v1/v2/v3) 送 GPT 拿新 paradigm

## Path 12 — RAB-SEP (binding-side routing-aware filter + clear-deficit cert)

**Why**: Path 01-11 + L1-L16 全死, GPT v1 review 给 paradigm — binding 端前置过滤
(port front-free + component-consistent) + clear-deficit cert (owner_pose +
blocker_poses) 反馈 master.

**How to apply**: cert tight (median 3, p90 4-5 远 < 60 阈值) 但 8/8 anchor UNPROVEN.
master 加 200+ cert 后系统性给 routing-infeasible layouts — cert 切空间太局部.
binding-side 必要条件前移 paradigm dead.

文件: `src/models/routing_binding_context.py`, `src/models/binding_subproblem.py`
filter, `src/search/benders_loop.py` empty_domain branch cert.

## Path 13 — SAC-Hull (Separator-Aware Capacity Hull + L2)

**Why**: Path 12 死, GPT v2 review 给 Menger / max-flow min-cut paradigm. 全局
corridor capacity necessary condition.

**How to apply**: violations 减 80%+ (22→4-5 floor), L2 工作 (0.08-0.10s) 让
master OPTIMAL layout 通 SAC 2 次. 但 binding/routing 真 verifier 仍 reject
L2-FEASIBLE layouts — **SAC necessary ≠ sufficient**. 8 anchor uniform hardness,
0/8 CERTIFIED.

文件: `src/models/separator_capacity_hull.py`,
`src/search/separator_capacity_separator.py`, `src/models/abstract_routing_layer.py`,
`src/search/benders_loop.py` env-gated hooks.

env: EXACT_B1_SEPARATOR_HULL / EXACT_B1_SEPARATOR_HULL_DYNAMIC /
EXACT_B1_ABSTRACT_ROUTING_LAYER / 等.

## Path 14 — PCR-CUT (Patch-Certified Routing Conflict Core) — 进度

**Why**: GPT v3 review 给新 paradigm. 兼具 Path 12 local pose conjunction +
Path 13 global focus + belt-level actual conflict.

**核心 idea**: master 给 layout → 找最堵小区域 (10×10 - 20×20 patch) → patch
内**真用 belt routing CP-SAT 跑** (含 ground+elevated layer, capacity, bridge,
continuity, port adherence, binding pattern) → patch 外 boundary relaxation 保
sound → patch INFEASIBLE → assumption core + replay validate → lift 成 master
nogood cut (signature lifting 覆盖一族同构 pose).

**Phase 0 GO ✅** (commit 24ed7d8):
- 27×15 anchor (22,28): top-3 patches sac coverage 2.8x (overlap, 单 patch 已 cover ~98%)
- top-3 blocked coverage 53.4%, cells_max 770 (≤ 900 cap)
- oracle wall 0.17s ≤ 5s
- **horizontal sep H_56 是主 bottleneck** (top-3 patches 都围绕它)
- paradigm 有资源优势 — 770 cells << 4900 (70×70)

**Phase 1-6 待实施** (~15-25h Claude pace, 2-3 day):
- Phase 1 (~650 LOC, 4-6h): patch exact router PoC — 复用 routing_subproblem.py
  patterns 加 patch restriction + boundary relaxation
- Phase 2 (~300 LOC, 2-3h): assumption core + replay validate
- Phase 3 (~420 LOC, 3-4h): signature lifting + master cut
- Phase 4 (~260 LOC, 2-3h): LBBD orchestration
- Phase 5 (~220 LOC, 1-2h + trial): multi-anchor + ablation
- Phase 6 (~460 LOC, 2-3h): proof lifecycle

文件: `docs/research/pcr_cut_patch_routing_conflict_20260519/phase0_patch_oracle_probe.py`
(~280 LOC PoC + json output).

详细 GPT 计划书: `/home/zhuran24/下载/B1_paradigm_breakthrough_plan_v3.md`.

## key git commits today

- `24ed7d8` PCR-CUT Phase 0 GO
- `71fb897` SAC-Hull Phase 5 multi-anchor 0/8 CERTIFIED
- `c439efc` SAC-Hull Phase 3 L2
- `4ef256d` SAC-Hull fall-through
- `aace4f5` SAC-Hull cut encoding 优化
- `c00c3da` SAC-Hull Phase 2a v3 (violations 22→7→8)
- `b8a0e89` SAC-Hull Phase 2 dynamic land
- `374ccbf` SAC-Hull Phase 1 static land
- `a64e406` SAC-Hull Phase 0 PoC (22 violations)
- RAB-SEP: `7616eb2` + `0fc947d` + `559be9c`

## review 包路径

- `~/linwin_share/b1_phase6_review_package_v1.zip` (v1, RAB-SEP 前)
- `~/linwin_share/b1_phase6_review_package_v2.zip` (v2, 含 Path 12 RAB-SEP 数据)
- `~/linwin_share/b1_phase6_review_package_v3.zip` (v3, 含 Path 13 SAC-Hull 数据)
- prompts: `b1_phase6_review_prompt_v1/v2/v3.md` 单独

## Related

- [[pcr-cut-phase1-pickup]] — Phase 1 起跑点 + 实施细节
- [[paradigm-phase0-cheap-gate]] — paradigm 验证 workflow
- [[gpt-review-no-history]] — GPT review 新窗口零 memory
- [[no-role-priming-for-reasoning-models]] — 不催眠
- [[no-giveup-options]] — 不列放弃选项
