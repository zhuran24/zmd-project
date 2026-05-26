# Spike Phase A — branch + probe + oracle fixture report

**Date**: 2026-05-26
**Branch**: `spike/prod_scale_master_integration_20260526` (off master `f7b88b6`)
**Phase A commits**: 4 (含 1 cross_check archive)
**Phase A wall-clock**: ~1.5h (主对话 + agent spawn, 重启一次)
**Phase A Claude 工时**: ~3-4h (estimate)
**Status**: ✅ Phase A done, Phase B ready

> **v17 addendum**: This file is a **historical pre-F3 Phase A report**. The A3 section
> below records the original 44-cert / 8-family run. Current v17 G10 status is
> **superseded** by spike commit `1d935f3` and
> `data/cuts/spike/oracle_emit_fixture_45cert.jsonl`: 50 cert / 9 family / 0 unsound,
> including 6 F3 `port_exposure` certs.

## Commit chain

| Commit | Subject | A-step |
|---|---|---|
| `09da356` | `[SPIKE-A1] branch setup + off-limits enforce harness` | A1 |
| `6679f34` | `[SPIKE-A2] failfast probe — G17 PASS (3.4s ≤ 15s)` | A2 |
| `a32a796` | `docs(spike): Gemini round 3 cross-check archive` | A0 (round 3 archive 补 commit, 在 spike branch) |
| `7922676` | `[SPIKE-A3] real oracle real emit fixture — 44/45 cert all sound` | A3 |

## A1 — Branch setup + off-limits enforce (commit `09da356`)

- Branch `spike/prod_scale_master_integration_20260526` 创建 off master `f7b88b6`
- State sandbox: `data/cuts/spike/` 创建 (gitignored 通过 spike-specific path)
- Spike harness 框架 land:
  - `scripts/spike_prod_scale_runner.py` (101 行, 主入口)
  - `scripts/spike_prod_scale_lib/__init__.py` (15 行)
  - `scripts/spike_prod_scale_lib/off_limits_check.py` (99 行, 8 项 off-limits enforce)
- 215 行 total

8 项 off-limits 实施 enforce (per MERGER §5.1 rollback-safety):
- ✅ `PROJECT_LOCK.md`
- ✅ `rules/canonical_rules.json`
- ✅ `data/preprocessed/*`
- ✅ `src/cuts/families/*` (9 family validator entry)
- ✅ `docs/项目说明/*` (spec)
- ✅ `CLAUDE.md`
- ✅ `src/cuts/lifecycle.py` 主 step 函数
- ✅ `src/cuts/replay.py`

## A2 — Failfast probe (commit `6679f34`) — G17 PASS ✅

- 50-inst subset toy master (proportional-by-facility-type sample, seed=42)
- BoolVar `x[(inst, pose)]` × full facility_type pool + demand=1 per inst
- 不加 anti-overlap / objective — 仅 harness sanity check, 不测 prod 行为
- 实测:
  - build wall: 1.3s
  - solve wall: 1.6s
  - **total wall: 3.4s** (G17 阈值 15s, **4× margin**)
  - status: OPTIMAL
  - 709,618 BoolVar / 50 constraints

注: 709K BoolVar 是 probe slack (subset 给每 inst 全 type pool, ~14K pose/inst
× 50 = 710K). 不是 prod group-anonymized 81K registry — A3 + Phase B 用真
81K 数字.

**G17 PASS** = harness 自身够快, 进 A3 / Phase B.

## A3 — Real oracle real emit fixture (commit `7922676`) — G10 SOFT-FAIL ⚠️

Observed fixture = **44 cert across 8 families**. Original target was ≥45 cert across 9 families; F3 `port_exposure` is missing because `generate_port_exposure_cuts()` is still a Phase 1.1 stub returning `[]`. This is not a soundness failure in the 44 certs, but it is **not a full G10 pass** for Finding 5 #2.

Family count:
| Family | Cert 数 |
|---|---|
| F1 region_capacity | 6 |
| F2 cutset | 6 |
| F4 component_reach | 6 |
| F3 port_exposure | 0 |
| F5 pattern_nogood | 6 |
| F6 shape_packing_hall | 4 |
| F7 power_hitting_set | 4 |
| F8 power_grid_reach | 6 |
| F9 density_envelope | 6 |
| **Total** | **44** |

Validator verdict on all 44 observed cert: 全 `kind="ok"` (0 unsound / 0 schema_err / 0 timeout). **N6 remains PASS** (no unsound cert), but **G10 is SOFT-FAIL / evidence incomplete** because the fixture misses F3 and does not meet the ≥45 target.

每 cert jsonl 记录 (`data/cuts/spike/oracle_emit_fixture_45cert.jsonl`,
67 KB / 44 line):
- family
- cert payload (base64)
- cert_kind
- 真 oracle wall (per cert)
- pose 数 / cell 数 / literal 数
- validator_kind

真 cut body size 分布数据已收集供 Phase B toy translator + active filter Hybrid sizing 用, but coverage is **partial**: F3 `port_exposure` contributes no cert body sample. Treat Finding 5 #2 as PARTIAL until an F3 validated fixture is added or the gate is explicitly re-scoped to 8 active families.

### Ruff lint fix (A3 commit 含)

oracle_emit_fixture.py 初版 agent 留 4 ruff error (lint-only, 不影响 logic):
- F401 `hashlib` imported but unused → 删
- F401 `LiteralAssignment` imported but unused → 删
- F401 `OracleVerdict` imported but unused → 删
- E402 `from dataclasses import dataclass as _dc` not at top → 改用 top-of-file `dataclass`
- E741 ambiguous variable `l` → 改 `lit`

ruff clean after fix.

## Phase A 工时实际 vs estimate

| 段 | Estimate (Claude) | Actual |
|---|---|---|
| A1 Branch + sandbox | 0.5-1h | ~1h |
| A2 Failfast probe | 1h | ~1-1.5h |
| A3 Oracle fixture 45 cert | 2-3h | ~2-3h (含 ruff fix +0.5h) |
| **Phase A total** | **3.5-5h Claude** | **~4-5.5h Claude** |
| Wall-clock | 0.5-1.5h | ~1-2h (含重启 + agent crash + 主对话接手) |

整体在 estimate 范围内. 重启一次 + agent 撞 socket error 后留 2 个 stale
worktree (主对话清理后接手 A3 commit + 写 report).

## Phase B 准备状态

- Fixture jsonl ready: `data/cuts/spike/oracle_emit_fixture_45cert.jsonl`
  (44 真 cert, 全 sound, family 分布 + cut body size 分布数据)
- Off-limits enforce harness ready: `scripts/spike_prod_scale_lib/off_limits_check.py`
- Branch state clean, ready 接 Phase B commits

## 偏离 MERGER spec

1. **44 cert vs ≥45 target + missing F3**: fixture has 44 cert across 8 families, not 9. This is a gate-accounting soft fail, not merely a one-cert rounding issue. Fix by adding ≥1 validated F3 `port_exposure` cert sample, preferably 4-5 to match the family distribution, or by formally changing G10 to "8 active families".
2. **709K BoolVar in probe**: probe 给每 inst 全 pool 不是 anonymized 81K,
   是 probe sanity (harness 自身够快) 不是 sizing 数据. Phase B 用真 81K.
3. **重启一次 + worktree cleanup**: 主对话接手 cleanup 2 stale worktree
   (pid 278918 等 stale), 再 commit A3. 流程顺利 recover, 无 data loss.

## Phase B scope (per MERGER §5)

待 spawn agent:
- B1 Toy translator (验 build cost, simple Add()/AddLinearConstraint, 不接
  PoseBoolExactMaster) — 1-2h Claude
- B2 Scale ramp (1K/10K/50K/100K cut, single build/solve, no LBBD loop) —
  1-2h Claude + 2-3h wall
- B3 Feasible smoke (IP v2 blueprint hint, 验 G6a 不 INFEASIBLE 早停 +
  G6b random cut tolerate-INFEASIBLE wall > 1s) — 1h Claude + <5min wall
- B4 Active filter Hybrid mock loop (10 iter age 累积, eviction trigger) —
  0.5-1h Claude
- B5 3 必 telemetry hook (RSS / proto / dark_matter) + post-mortem —
  1-2h Claude
- B6 Run + verify + write spike `verdict.md` — 1-2h Claude + 1-2h wall

**Phase B estimate**: ~6-9h Claude / 3-5h wall. 跟 spike total 8-12h / 4-7h
对齐 (Phase A 用了 ~4-5h Claude / 1-2h wall, 余 ~3-7h Claude / 2-5h wall
留 Phase B, 估算 tight 但可 hold).
