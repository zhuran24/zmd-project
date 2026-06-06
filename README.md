# Endfield IndustrialPlanner — 70×70 certified-exact 求解器

《明日方舟：终末地》基地排布的**精确最大空矩形求解器**：在 70×70 网格、266 个强制设施实例约束下，求 `max_lex(area, min_side)`（先最大化面积、再最大化短边）的**可证明最优**空地矩形。OR-Tools CP-SAT + Benders/LBBD 分解（master → binding → routing → flow）。

## 当前主线（subject projection）

<!-- DOC-SUBJECT:current_project_state FIELD:frontdoor_snapshot START sha256:ff8fdd45a63dc5ca9c06870d2daf0bda3e91db5c29387c7436143e43824b9d9e -->
Current working state: **Phase 1.2 spike close** for cut-family validator soundness. The next major implementation body is the true `PoseBoolExactMaster` LBBD master integration, named `P1.3B` in the project-book docs and historically called `P1.3A 主体` in CC memory. Treat this as a living projection of `docs/subjects/current_project_state.md`; do not hand-copy a separate current-phase story elsewhere.
<!-- DOC-SUBJECT:current_project_state FIELD:frontdoor_snapshot END -->

## 精确性边界（subject projection）

<!-- DOC-SUBJECT:certified_exact_contract FIELD:frontdoor_contract START sha256:3b43b968c1dd26cfe824ead3065a56a7c9947bc5b1c0eef8f12c8bcf21a3ae17 -->
Certified exact mode is separate from exploratory tooling. The exact objective is `max_lex(area, min_side)`, and exploratory caps or sidecar hints must never become certified feasibility bounds. The frozen source-of-truth artifacts are `rules/canonical_rules.json`, `data/preprocessed/candidate_placements.json`, `data/preprocessed/mandatory_exact_instances.json`, and `data/preprocessed/generic_io_requirements.json`.
<!-- DOC-SUBJECT:certified_exact_contract FIELD:frontdoor_contract END -->

## 文档树入口（subject projection）

<!-- DOC-SUBJECT:doc_tree_architecture FIELD:docs_readme_summary START sha256:ca8444165fd1c2128cfdc08a6ad8da370a426d6727028353da593ea29d1768f2 -->
The documentation tree is organized around **subjects** and **projections**. Subjects live in `docs/subjects/` as context-independent sources; concrete docs carry registered projection blocks that are synchronized by `scripts/sync_doc_subjects.py`. This replaces copy-based current-status prose with a small transclusion graph.
<!-- DOC-SUBJECT:doc_tree_architecture FIELD:docs_readme_summary END -->

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
