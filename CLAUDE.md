# CLAUDE.md — Endfield IndustrialPlanner Exact Solver

## Project Overview

70x70 grid exact maximum empty rectangle solver for Arknights: Endfield IndustrialPlanner.
Objective: `max_lex(area, min_side)` — maximize area first, then min-side.
266 mandatory facility instances, OR-Tools CP-SAT, Benders decomposition (master -> binding -> routing -> flow).

## Exactness Constitution (from PROJECT_LOCK.md)

- `certified_exact` and `exploratory` are **strictly separate paths**. Never mix them.
- Exact objective is `max_lex(area, min_side)`. `min_side >= 6` is admissibility, not tie-break.
- No hard `50 power poles + 10 storage boxes` cap in exact mode — that's exploratory-only.

## Forbidden Changes

- Reintroducing exploratory caps as exact-mode bounds
- Treating exploratory artifacts as certified proof
- Changing campaign/artifact/proof schemas without updating lock/spec/test together
- Rebinding globally pooled resources into per-line hard bindings without new proof basis
- Adding exterior-path requirement for the ghost rectangle

## Source of Truth

Certified path is grounded in:
- `rules/canonical_rules.json` (consolidated preprocess/recipe/target/commodity truth)
- `data/preprocessed/candidate_placements.json`
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

Everything under `src/adapters/`, `src/render/`, `data/exports/`, `data/examples/` is **postprocess-only** — never redefines solve schemas.

## Architecture

```
main.py                          # Entry point
src/search/outer_search.py       # Outer candidate loop + frontier
src/search/benders_loop.py       # Benders decomposition (LBBD)
src/models/master_model.py       # CP-SAT placement master
src/models/exact_coordinate_master.py  # Ghost rectangle enforcement
src/models/binding_subproblem.py # Port binding
src/models/routing_subproblem.py # Grid routing
src/models/flow_subproblem.py    # Multi-commodity flow diagnostic
src/search/exact_campaign.py     # Campaign persistence + resume
src/search/exact_parallel_scheduler.py  # Multi-process parallel waves
```

## Active Scope

- Single base: `valley4_protocol_core` 70x70 only
- Other bases (`valley4_infra_outpost`, `wuling_protocol_core`, etc.) are `future_scope`
- Outer-deployment subsystem is adapter-side `future_scope`

## Current Phase: 3B Optimization / Acceleration

- Phase 3A (delivery/productization): Complete, release `r20260416`
- Phase 3B (full-scale exact proof): In progress
- Acceleration plan: `docs/phase3b_repair5_acceleration_tuning_ai_plan.md`
- 4 lanes: A=safety/observability, B=deterministic tuning, C=AI sidecar, D=runtime diagnostics
- AI is shadow-only sidecar: no proof source, no formal pruning, no checkpoint writes

## AI Safety Contract

AI modules may ONLY:
- Suggest candidate ordering (order_only)
- Classify UNKNOWN/UNPROVEN results
- Explain tuning experiments
- Suggest CP-SAT hints (as hints, not constraints)

AI modules must NEVER:
- Delete candidates or declare infeasibility
- Write to `data/checkpoints/`, `data/solutions/`, `data/blueprints/`
- Modify certified proof source or campaign hash
- Change final preflight semantics
- Authorize final 168h production run

## Commands

```powershell
# Run solver (default certified_exact mode)
python main.py --campaign-hours 168.0 --parallel-processes 4

# Run tests
python -m pytest src/tests/ -q

# Single-base e2e workflow
python scripts/run_industrial_planner_single_base_e2e.py --run-dir .artifacts/industrial_planner_single_base_e2e

# Visualization only
python main.py --vis
```

## Maintenance scripts (runbook)

> **重要**：用户可能会问"上游更新了怎么办"——答案是这两条命令，不是手动复制文件。

```powershell
# Refresh JamboChen/endfield-calc vendored snapshot (recipes + items + facilities)
python scripts/refresh_endfield_calc_snapshot.py
# Optional: --dry-run / --commit <SHA>

# Refresh hsyhhssyy/IndustrialPlanner vendored BASES (7 base definitions)
python scripts/refresh_industrial_planner_bases.py
# Optional: --dry-run / --branch v2 / --commit <SHA>
```

Both scripts are mechanical sync only:
- Update `third_party_snapshots/.../SOURCE_METADATA.json` (version, commit, observed_counts, previous_*)
- Print a diff report (counts changed, new entities)
- **Do NOT touch** `canonical_rules.json` — extending the 17-recipe canonical projection is a PROJECT_LOCK gate, separate manual decision
- **Do NOT auto-edit** `BORROWED_COMPONENTS.md` / `CHANGELOG.md` / `FILE_STATUS.md` / specs — release-note phrasing stays editorial

Tests `src/tests/test_endfield_calc_typescript_snapshot.py` and `src/tests/test_industrial_planner_bases_snapshot.py` read `SOURCE_METADATA.json` for expected counts, so refresh runs do not require test edits.

### Linux migration setup (CachyOS target — switched from Fedora 2026-05-08)

```bash
# Phase 3C P2 #19 bring-up checklist after CachyOS install
bash scripts/cachyos_setup.sh             # dry-run, prints commands
bash scripts/cachyos_setup.sh --apply     # actually install/configure
```

Covers Python 3.13 + venv + requirements + jemalloc/tcmalloc/mimalloc
allocators + THP madvise check + cgroups v2 + zram check + ortools
sanity + cachyos-bore kernel verify + IgnorePkg recommendation for
168h campaign stability. Default mode is dry-run so user can review
each step before applying.

Why CachyOS not Fedora: Fedora 41-44 all fail to boot on user's ASUS
Z790 (BIOS memory fragmentation + GRUB 2.06 can't coalesce). CachyOS
ships **Limine** as default EFI bootloader (verified via repo config
`src/modules/bootloader/bootloader.conf` `efiBootLoader: "limine"`)
which bypasses the GRUB 2.06 issue at root with no user action
needed during install. Plus cachyos-bore kernel default brings
BORE/EEVDF scheduler +5-10% on top of base Linux migration's +15-35%.
Earlier `scripts/fedora_setup.sh` removed (recoverable from git
history if needed).

### 168h campaign 关键包冻结 (CachyOS 滚动稳定性)

```bash
# 168h campaign 启动前 freeze 关键包不被 pacman -Syu 升级
bash scripts/pacman_campaign_freeze.sh --enable

# 当前状态查询
bash scripts/pacman_campaign_freeze.sh --status

# campaign 结束后解冻让系统跟最新
bash scripts/pacman_campaign_freeze.sh --disable
```

锁的包：linux-cachyos*, glibc, python, jemalloc, gperftools。平时（非
campaign 期间）应保持 unfreeze。脚本通过在 `/etc/pacman.conf` 里加带
markers 的 `IgnorePkg` 行实现，可可逆 toggle。

### Local upstream reference clones (offline, not vendored)

`.upstream_clones/` is **gitignored** and holds full clones for offline browsing/diffing. Currently contains:

- `.upstream_clones/industrial_planner_v2/` — full `hsyhhssyy/IndustrialPlanner` v2 branch (~50 MB shallow clone). Use for reading `src/domain/registry.ts`, `src/sim/engine.ts`, etc. without network. Refresh: `cd .upstream_clones/industrial_planner_v2 && git pull`.

These clones are **NOT** part of the build, are NOT scanned by tests, and do NOT count as vendored data. Vendored slices live under `third_party_snapshots/`.

## Dependencies

- Python 3.13
- ortools (9.15.6755), pydantic (>=2), numpy, matplotlib, psutil, pandas, jsonschema, Pillow

## Conventions

- All changes touching exact boundaries must update: PROJECT_LOCK.md, FILE_STATUS.md, relevant spec, relevant tests
- Postprocess/adapter changes don't need lock updates but must not widen proof semantics
- Test with `python -m pytest src/tests/ -q` before any commit
- `_codex_archive/` contains historical Codex (GPT) workspace artifacts — read-only reference, not active code
