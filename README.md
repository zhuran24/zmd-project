# Endfield IndustrialPlanner — 70×70 certified-exact 求解器

《明日方舟：终末地》基地排布的**精确最大空矩形求解器**：在 70×70 网格、266 个强制设施实例约束下，求 `max_lex(area, min_side)`（先最大化面积、再最大化短边）的**可证明最优**空地矩形。OR-Tools CP-SAT + Benders/LBBD 分解（master → binding → routing → flow）。

## 当前主线（subject projection）

<!-- DOC-SUBJECT:current_project_state FIELD:frontdoor_snapshot START sha256:f8e20cb1970a03d8fa0b3b1a59ed4df09cf492d685bca0f20f631d625e5ead25 -->
Current working state: **Phase 1.2 spike close is not formally closed**. The V50 manual phase gate still applies: the **three clean full reviews** standard is owner-maintained outside the repo, and only an explicit owner manual decision may open P1.3B. After V57-V89, the current review anchor is `v89_ghost_pick_terminal_binding_sealing`: certified lifecycle evidence is now split into explicit proof obligations for exact-safe cut replay (persisted exact_safe_cuts are telemetry, never proof objects), certified master-domain and power-witness representation faithfulness (including time-budget-partial precheck groups never standing in for complete infeasibility proofs), replayable strict full-frontier terminal evidence over the fully oriented candidate domain with sealed candidate-domain axes, canonical project-level min-side admissibility, deny-unknown evidence keys, disk-authoritative delivery-manifest writing, canonical certified manifest publication, and certified export-surface consistency including the single-base release path rejecting self-claimed CERTIFIED run summaries. P1.3B remains blocked by default; review receipts are informational records only.
<!-- DOC-SUBJECT:current_project_state FIELD:frontdoor_snapshot END -->

## 精确性边界（subject projection）

<!-- DOC-SUBJECT:certified_exact_contract FIELD:frontdoor_contract START sha256:e8bdd52bb4ea38068e1e59d599ae362f8c66cb83423d851eee1748fd078ce8dd -->
Certified exact mode is separate from exploratory tooling. The exact objective is `max_lex(area, min_side)`, and exploratory caps or sidecar hints must never become certified feasibility bounds. The frozen source-of-truth inputs are `rules/canonical_rules.json`, required external artifact `data/preprocessed/candidate_placements.json`, checked-in `data/preprocessed/mandatory_exact_instances.json`, and checked-in `data/preprocessed/generic_io_requirements.json`.
<!-- DOC-SUBJECT:certified_exact_contract FIELD:frontdoor_contract END -->

## 文档树入口（subject projection）

<!-- DOC-SUBJECT:doc_tree_architecture FIELD:docs_readme_summary START sha256:e99ba762ef5fb654e50fe091103cde7cff8cee13657021cc04d593d5bb9d3954 -->
The documentation tree is organized around **subjects** and **projections**. Subjects live in `docs/subjects/` as context-independent sources; concrete docs and memory nodes carry registered projection blocks that are synchronized by `scripts/sync_doc_subjects.py`. This replaces copy-based current-status prose with a small transclusion graph.
<!-- DOC-SUBJECT:doc_tree_architecture FIELD:docs_readme_summary END -->

## GitHub checkout 导航

先读 [`START_HERE.md`](START_HERE.md)。当前 GitHub `main` 是 lightweight
checkout：源码、规格、文档和小型 certified inputs 留在树里，大型 review 包和
production `data/preprocessed/candidate_placements.json` 不放在当前工作区；需要跑
certified exact 前先按 `START_HERE.md` 恢复 artifact。

## 跑求解器

```powershell
# certified_exact 模式（默认）
python main.py --campaign-hours 168.0 --parallel-processes 4
# 测试
python -m pytest src/tests/ -q
# 可视化
python main.py --vis
```

（Linux 生产启动须用 wrapper，单跑 `python main.py` 会丢调优；见 `CLAUDE.md` 的 Commands / Maintenance scripts 段。）

## 精确性边界补充摘要（权威见 `PROJECT_LOCK.md`）

- `certified_exact` 与 `exploratory` 是**严格分离**的两条路径，绝不混用。
- exact 目标 = `max_lex(area, min_side)`；`min_side >= 6` 是候选 admissibility，不是 tie-break。
- exact 模式**无**硬 `50 供电桩 + 10 协议箱` cap —— 该数字仅 exploratory-only guidance（供电桩 residual-optional / 协议箱 demand 驱动）。
- 全 70×70 exact `CERTIFIED` 仍诚实标 `open`（spike close 阶段）。

## IndustrialPlanner 交付面（postprocess / adapter 线，release `r20260416` 冻结）

> **注**：本节是 **postprocess-only** 的产品化 / 交付线（把求解产物导出成 IndustrialPlanner 蓝图 + 消费面），**不是当前活动主线**，也**不重定义任何 solve schema**（见 `PROJECT_LOCK.md` 的 Source of Truth）。当前主线是上面的 cut-family LBBD。

当前唯一 active 的 IndustrialPlanner 线 = `valley4_protocol_core`（70×70）；其余 base 与 outer-deployment 均保留为 `future_scope`、不在默认 active gate。checked-in 入口与详细 artifact map / release pointers / 再生成命令见：

- `data/examples/industrial_planner/README.md` — 交付面 artifact map + release pointers + regeneration commands（交付面的权威索引）
- `data/examples/industrial_planner/index.html` — 交付面入口页（browse-first / download-first）
- `data/examples/industrial_planner/active_single_base_delivery_entrypoints.json` — 聚合 machine-readable entrypoints manifest（含 surface health 快照）

单基地端到端 / 交付面 promotion / no-drift audit / health snapshot 等脚本：

```bash
# 单基地 e2e
python scripts/run_industrial_planner_single_base_e2e.py \
  --run-dir .artifacts/industrial_planner_single_base_e2e
# 交付面 release promotion（刷新 release/viewer/landing/bundle/frontdoor + no-drift audit）
python scripts/build_industrial_planner_single_base_delivery_release.py --help
```

其余交付面脚本（standalone no-drift audit / health snapshot 等）见 `data/examples/industrial_planner/README.md` 与 `CLAUDE.md`。
