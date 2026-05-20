# Endfield exact refactor project

> **项目状态地图 (2026-05-16)**
>
> | Phase | 状态 | 说明 |
> |---|---|---|
> | **3A** delivery / productization | ✅ 完成 | release `r20260416` 已交付; viewer / landing / frontdoor / entrypoints 全打通 |
> | **3B** full-scale exact proof | ▶ 进行中 | 70×70 max_lex(area, min_side) 严格证明; 当前 0 FEASIBLE, 主线 lever 已 verify 9 条死路 (见 `docs/lever_verdicts.md`) |
> | **3C** 加速 / 路线优化 | 📋 规划 + 实测 | 4 lanes (safety / tuning / AI sidecar / runtime); 见 `docs/phase3c_optimization_roadmap_v1.md` |
>
> **进入项目的入口**:
> - 求解器架构 + Phase 状态 + commands: `CLAUDE.md` (操作手册)
> - 精确性宪法 + 禁条 + accepted invariants: `PROJECT_LOCK.md`
> - 每个文件运行时角色 + 信任状态: `FILE_STATUS.md`
> - 已试过的所有 master 加速 lever + 实测 verdict: `docs/lever_verdicts.md`
> - 所有 `EXACT_*` env 集中索引: `docs/env_variable_index.md`
> - Phase 3B 详细 endgame plan: `docs/phase3b_exact_endgame_execution_plan.md`
> - 操作脚本一览 (启 168h, 停, watchdog): `CLAUDE.md` 中 Commands / Maintenance scripts 段

---

This repository currently has one active user-facing IndustrialPlanner line:
`valley4_protocol_core` on the 70×70 base.

The quickest checked-in entry points are:

- `data/examples/industrial_planner/index.html` — repo-front current entry page with explicit browse-first/download-first paths and helper links that now point straight at the aggregate script-entry manifest
- `data/examples/industrial_planner/active_single_base_delivery_entrypoints.json` — one aggregate machine-readable manifest for the current release/viewer/landing/latest-bundle entry surface plus the surfaced current health snapshot
- `data/examples/industrial_planner/current_surface_health.json` — minimal zero-parse health snapshot for the active single-base consumer surface
- `.artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json` — the latest no-drift audit summary for the checked-in repo-front + aggregate-entrypoints surface
- `data/examples/industrial_planner/industrial_planner_latest_single_base_delivery_bundle.zip` — shorter top-level latest ZIP alias for download-first consumers
- `data/examples/industrial_planner/current_delivery/index.html` — stable
  current landing/download page
- `data/examples/industrial_planner/current_delivery/downloads/industrial_planner_current_single_base_delivery_bundle.zip` — source current-delivery ZIP alias mirrored by the top-level latest bundle
- `data/examples/industrial_planner/README.md` — checked-in artifact map,
  release pointers, and regeneration commands

Current boundary:

- other bases remain preserved as `future_scope`
- outer-deployment remains preserved but out of the default active gate
- full-scale 70×70 exact `CERTIFIED` is still honestly marked as `open`

For the active single-base execution flow, start with:

```bash
python scripts/run_industrial_planner_single_base_e2e.py \
  --run-dir .artifacts/industrial_planner_single_base_e2e
```

For the promotion flow that refreshes the checked-in release, viewer, current
landing, current bundle ZIP alias, repo-front entry page, and the top-level
latest bundle alias plus the aggregate active-entrypoints manifest — and now
runs a lightweight no-drift audit, writes a compact `current_surface_health.{json,md,txt}` snapshot for zero-parse consumers, then re-surfaces that clean/drift summary
back into the repo front door and aggregate manifest so reviewers/automation can
see the current entry-surface health directly, while also re-auditing the
surfaced `surface_alignment_summary.{json,md,txt}` refs themselves before the
final checked-in frontdoor/entrypoints pair is left behind — see:

```bash
python scripts/build_industrial_planner_single_base_delivery_release.py --help
```

For the standalone no-drift audit of the already-checked-in consumer surface —
including the surfaced audit-summary refs and metadata that now appear in both
the repo front door and the aggregate entrypoints manifest — run:

```bash
python scripts/audit_industrial_planner_single_base_delivery_surface_alignment.py
```

For the standalone compact health snapshot derived from the checked-in audit and re-surfaced into the frontdoor/aggregate manifests — run:

```bash
python scripts/build_industrial_planner_single_base_delivery_surface_health.py
```

For the remaining solver-side closeout after the single-base delivery/productization line, see:

- `docs/phase3b_exact_endgame_execution_plan.md` — detailed current-to-finish plan for Phase 3B, including startline freeze, exact-safe lower-bound / UNKNOWN triage loops, long-run campaign execution, terminal exact evidence freeze, and the final propagation of exact-close status back into the checked-in single-base release/frontdoor surface
