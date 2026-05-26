#!/usr/bin/env python3
"""Build phase1_2_spike_review_v17.zip — Phase 1.2 spike close gate snapshot (post-F3 special-case phase).

v13 → v14 change: include Finding 5 close gate spike verdict.
v14 → v15 change: downgrade G10 → SOFT-FAIL per GPT pro v14 二审.
v15 → v16 change: per GPT pro v15 三审 — F8 audit 大半径 case (R=50) src 改动
(streaming reachability replaces full power graph materialization) + repro project
root walk-up (PROJECT_LOCK.md + src/cuts marker) + RSS evidence boundary 拆 (build
vs after-solve snapshot).
v16 → v17 change: F3 special-case phase Stage 1 generator (master `c768806` +
Gemini round 1 logging fix `b5860bc`) + spike A3 rerun (44 → 50 cert / 8 → 9
family / 0 unsound) + spike telemetry `rss_sample_after_solve` raw event
(GPT pro v15 三审 finding 4 后续 fix) + Phase B full rerun.

v13 was post-patch (3 commit fix BLOCKER ×2 + HIGH + LOW from GPT pro audit cb8e347),
with `docs/research/prod_scale_spike_design_20260525/**` EXCLUDED (design then in-flight).

v14 added Phase 1.2 spike close gate evidence (5 file overlay + spike branch log).

v15 reflects GPT pro v14 二审 finding fix (G10 SOFT-FAIL doc + telemetry overlay
+ repro sys.path bootstrap + B2 RSS 数字口径修正).

v16 reflects GPT pro v15 三审 finding fix:
- F8 streaming reachability src 改动 (commit `f17f13e`):
  any_target_reachable_from_pc() 加 streaming BFS to target set (same exact edge
  predicate _can_jump_via_cells + ghost AABB). 解锁 R=50 大半径 case 11M pair
  O(n^2) 卡住 (defer P1.3 的同一 root cause as v14 finding 4 F8 perf 28s).
  build_power_network() 公开 API 不变.
- Repro project root walk-up (commit `b3c370e`): 原 `parents[4]` 硬编码 4 层
  改 _find_project_root() 找 PROJECT_LOCK.md + src/cuts 双标记 (Python + shell).
- RSS evidence boundary 拆 (commit `f54f4f8` on spike branch + v16 README sync):
  G8 行 + Finding 5 #3 行 + tail RSS 段标 build RSS 0.834–0.866 GB (telemetry
  raw) vs phase_b_results after-solve RSS 1.029 GB (aggregate snapshot only).

v17 后续:
- F3 special-case phase Stage 1 generator landed on master (commit `c768806`):
  generate_port_exposure_cuts() 不再 stub return [], 按 cell_owner derive +
  ghost-occluded skip + pose_ports lookup 实施 spec §5 + §6 + §9 OQ#2; env
  gate `EXACT_F3_GENERATOR_ENABLED=1` default-disabled (mirrors F7 / F8). 接口
  跟 validator port_exposure.py frozen API 一致. Gemini round 1 cross-check
  fix (`b5860bc`): silent skip path 加 logging.debug 让 generator skip 可追踪.
- A3 oracle emit fixture rerun on spike branch (commit `1d935f3`):
  F3 driver 用 explicit `target_poses` path 跑 generator 真 emit;
  redistributed_per_family lifted to min 6 让 F6 (state-design cap ~4) 不足
  由其它 8 family 补齐. 结果 50 cert × 9 family × 0 unsound (v16 时 44 / 8 / 0).
- Spike telemetry rss_sample_after_solve raw event (spike commit `b1bab5c`):
  GPT pro v15 三审 finding 4 follow-up. telemetry.emit_rss_after_solve(tier,
  rss_bytes) 新 event type. scale_ramp.run_one_tier 在 solver.Solve(model)
  返回后立刻 emit, per tier 1 个 event. N11 audit 不动 (新 event 是补充而非
  替代 rss_sample 1Hz background).
- Phase B full rerun (spike commit `6e6db10`) 用新 fixture + 新 telemetry +
  refresh verdict.md (G10 row "44 cert" → "50 cert / 9 family / 0 unsound",
  Finding 5 #2 evidence count refresh, raw artifact 段 count refresh).

v17 does NOT include spike-only implementation code (per MERGER §5.1 rollback-safety
"PR #1 verdict-only style, PR #2 重写 P1.3A 实施 不 cherry-pick spike code"):
- scripts/spike_prod_scale_runner.py
- scripts/spike_prod_scale_lib/*.py
F3 generator src code (src/cuts/oracles/port_exposure_oracle.py) **入包** —
那是 master commit `c768806`/`b5860bc`, 不是 spike-only code.

Strategy 同 v14/v15:
- 全项目 root copy + 7z -mx=9 + zip 壳 + ship 7za binary (per [[review-pkg-7z-strategy]])
- 排除 .venv / .git / .artifacts / .codex_test_logs / .upstream_clones / .claude / _codex_archive
- 不放 prompt / 主动性内容 (per [[review-pkg-no-prompt-inside]]) — prompt 通过
  chat message 单独给
"""
from __future__ import annotations

import fnmatch
import shutil
import subprocess
from pathlib import Path

REPO = Path("/home/zhuran24/claude-pj/zmd")
OUT_DIR = Path("/tmp/_phase1_2_pkg_v17")
PROJECT_DIR = OUT_DIR / "project"
SEVENZ_PATH = OUT_DIR / "project.7z"
OUT_ZIP = Path("/home/zhuran24/linwin_share/phase1_2_spike_review_v17.zip")

SEVENZA_SRC = Path("/usr/lib/7zip/7za")

SPIKE_BRANCH = "spike/prod_scale_master_integration_20260526"

# Spike branch file overlay (verdict data only — NOT spike-only implementation code).
# Per MERGER §5.1 rollback-safety: PR #1 verdict-only style.
SPIKE_OVERLAY_FILES = [
    "docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md",
    "docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md",
    "data/cuts/spike/oracle_emit_fixture_45cert.jsonl",
    "data/cuts/spike/scale_ramp_results.jsonl",
    "data/cuts/spike/phase_b_results.json",
    # v17 telemetry pid renamed (Phase B rerun: pid 21050 → pid 77754) per
    # F3 special-case phase Stage 1 + rss_sample_after_solve event class
    # introduction. Phase B was rerun after master merged onto spike branch
    # so the new fixture (50 cert / 9 family) + new telemetry event drive
    # the artifacts in this overlay.
    "data/cuts/spike/telemetry_77754.jsonl",
]

# Spike-only implementation code paths — these must NOT appear in the project tree.
# They live only on the spike branch and would anchor reviewer on toy translator
# design choices when P1.3A 主体 should walk N=8 parallel design instead.
SPIKE_FORBIDDEN_PATHS = [
    "scripts/spike_prod_scale_runner.py",
    "scripts/spike_prod_scale_lib",
]


EXCLUDE_TOPLEVEL = {
    ".venv", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".artifacts", ".codex_test_logs", ".upstream_clones", ".claude",
    "_codex_archive", "node_modules",
}

EXCLUDE_NAMES = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}

EXCLUDE_PATTERNS = [
    "**/telemetry_samples.jsonl",
    "**/exact_campaign_state.json.*",
    "**/exact_campaign_telemetry.json.*",
    "**/cache.*.db",
    "**/tree.txt",
    "**/*.tar.xz",
    "**/.DS_Store",
    "**/Thumbs.db",
]

EXCLUDE_FILES: set[str] = set()
EXCLUDE_REVIEW_BUILD = "scripts/build_phase1_"


def should_skip(rel: Path) -> bool:
    parts = rel.parts
    if not parts:
        return True
    if parts[0] in EXCLUDE_TOPLEVEL:
        return True
    if any(p in EXCLUDE_NAMES for p in parts):
        return True
    rel_str = str(rel)
    if rel_str in EXCLUDE_FILES:
        return True
    if rel_str.startswith(EXCLUDE_REVIEW_BUILD):
        return True
    # Spike-only implementation code: hard-block even if present locally
    # (would only happen if user accidentally cherry-picks; sanity guard).
    for forbidden in SPIKE_FORBIDDEN_PATHS:
        if rel_str == forbidden or rel_str.startswith(forbidden + "/"):
            return True
    for pat in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel_str, pat):
            return True
    return False


README_V17 = """# 终末地工业规划器 — 项目快照

终末地 (Arknights: Endfield) 70×70 工业规划器 certified-exact 最大空矩形求解器.
目标 `max_lex(area, min_side)`. 266 mandatory facility, OR-Tools 9.15
CP-SAT, LBBD 分解 (master → binding → routing → flow). 详
`docs/项目说明/01_overview.md` + `02_mathematical_foundations.md`.

全项目内容 (src + docs + rules + data + scripts + main.py + spec + audit archive).

Build: master commit `b5860bc` (详 `COMMIT_LOG.md`) + spike overlay (6 file + 1
SPIKE_COMMIT_LOG, 详 `SPIKE_COMMIT_LOG.md`, spike branch HEAD `6e6db10`).

## v13 → v14 状态变化

v13 (post-patch) 之后 master 上 land 5 commit:

| Commit | Subject |
|---|---|
| `45c7a25` | research(spike): prod-scale spike design 8 路 parallel + main merger |
| `52cd014` | research(spike): MERGER round 1 fix per Gemini cross-check |
| `3523526` | research(spike): MERGER round 2 fix per Gemini cross-check |
| `b44d0c6` | research(spike): MERGER shrink §5 scope per user scope creep audit |
| `f7b88b6` | research(spike): MERGER round 3 fix (G6 + G11 + Q8 文档化 → 直接 spike 实施) |

外加 spike branch `spike/prod_scale_master_integration_20260526` 10 commit (off
master `f7b88b6`) 含 spike A/B 实施 + verdict. spike code 本身不入此包 (per
MERGER §5.1 rollback-safety PR #1 verdict-only style), 只入 verdict / report /
实测数据 5 file.

## v14 → v15 状态变化

| Commit | Branch | Subject |
|---|---|---|
| `d575a87` | master | fix(review-pkg v14): replace non-existent scale_ramp_test_smoke.jsonl with phase_b_results.json |
| `0691175` | spike | [SPIKE-VERDICT-FIX] downgrade G10 PASS → SOFT-FAIL per GPT pro v14 二审 |
| `832f157` | master | fix(audit-repro): add sys.path bootstrap + correct shell repro path per GPT pro v14 二审 |

v15 改动来源 GPT pro v14 二审 4 finding:
- Finding 1 HIGH: A3 fixture observed 44 cert across 8 families, F3 `port_exposure`
  缺失 (generator 是 Phase 1.1 stub `return []`). G10 阈值原写 ≥45 + 9 families.
  Verdict G10 PASS → SOFT-FAIL; Finding 5 #2 YES → PARTIAL; spike Overall
  GO_WITH_MINOR → NOT_GO until G10 is repaired.
- Finding 2 MEDIUM: 3 个 Python repro file + 1 个 shell repro 入口失败. 加 sys.path
  bootstrap 跟 BASH_SOURCE 路径计算.
- Finding 3 LOW: B2 ramp RSS 文档口径 `0.61-0.83 GB` 跟 raw jsonl `0.84-1.03 GB`
  不一致. 改成 `0.84-1.03 GB`.
- Finding 4 LOW: `data/cuts/spike/telemetry_21050.jsonl` 在 spike branch tracked
  但 v14 build script 漏 overlay. v15 加入 SPIKE_OVERLAY_FILES.

## v15 → v16 状态变化

| Commit | Branch | Subject |
|---|---|---|
| `5e05ef6` | master | fix(review-pkg v15): strip verdict-claim priming from README per review-pkg-no-prompt-inside |
| `b3c370e` | master | fix(audit-repro): harden project root discovery via PROJECT_LOCK.md walk-up |
| `f17f13e` | master | fix(F8): streaming reachability replaces full power graph materialization |
| `f54f4f8` | spike | [SPIKE-VERDICT-FIX-2] RSS evidence boundary per GPT pro v15 三审 finding 3 |

v16 改动来源 GPT pro v15 三审 finding:
- Finding 1 (MED/HIGH) NEW: F8 audit 大半径 case (R=50) build_power_network 物化
  完整图 — 70×70 grid 上 2×2 pole anchor 最多 4761 个, R=50 pair 数
  4761×4760/2 = 11,331,180. 跟 v14 二审 Finding 4 F8 perf 28s 同一 root cause.
  Fix: 加 any_target_reachable_from_pc() streaming BFS 按需生成邻居, 找 target
  提前返回; 用 same exact edge predicate (_can_jump_via_cells + ghost AABB).
  公开 API build_power_network() 不动 (其它 caller 不受影响). 数学等价性
  (full graph BFS reachability ≡ streaming BFS to target set under same exact
  predicate). 验证: 398 pytest pass + mypy strict 0 error + ruff clean.
- Finding 2 (follow-up): 二审 fix `parents[4]` 硬编码 4 层目录, file 移动 silently
  找错根. 改成 _find_project_root() 向上 walk 找 PROJECT_LOCK.md + src/cuts
  双标记; shell 同理用 find_project_root function + PYTHON env override.
- Finding 3 (LOW): 0.84-1.03GB 是 aggregate summary, 证据需拆开 —
  scale_ramp_results.jsonl rss_peak_gb_during_build max 0.866 GB (telemetry raw)
  vs phase_b_results.json 100K rss_peak_gb_after_solve 1.029 GB (aggregate
  snapshot only). README G8 行 + Finding 5 #3 行 + spike branch verdict.md 同步.

## v16 → v17 状态变化

| Commit | Branch | Subject |
|---|---|---|
| `c768806` | master | feat(F3): implement port_exposure generator per spec §5 (special-case phase stage 1) |
| `b5860bc` | master | fix(F3): Gemini round 1 — add logging.debug to silent skip paths |
| `d92ed77` | spike (merge) | [SPIKE-MERGE-MASTER] incorporate F3 generator stage 1 + round 1 fix |
| `b1bab5c` | spike | [SPIKE-TELEMETRY] emit rss_sample_after_solve event at solve completion |
| `1d935f3` | spike | [SPIKE-A3-RERUN] F3 generator emit added — 50 cert / 9 family / 0 unsound |
| `6e6db10` | spike | [SPIKE-B6-RERUN] Phase B full rerun with F3 generator + rss_sample_after_solve |

v17 改动来源 F3 special-case phase Stage 1 实施 + GPT pro v15 三审 finding 4 follow-up:
- F3 generator stage 1 (`c768806` + Gemini round 1 fix `b5860bc`): `src/cuts/
  oracles/port_exposure_oracle.py` 从 stub (return [] line 34-55) 升级到完整
  generator. cell_owner-derived targets (Phase 1.5+ master_solution wiring
  defer) + target_poses explicit override (F7 same API) + ghost-occluded skip
  per spec §6 + §9 OQ#2 + pose_ports lookup miss fail-closed + multi-port
  per facility emit. cert_kind="port_exposure_blocked" 2-literal mode (facility
  A + blocking facility B); active_port_witness_b64=None (Phase 1.5+ defer
  cand C LP wrap). Tests `src/tests/cuts/test_family_port_exposure_generator.py`
  462 line covers env gate / happy path / multi-port / ghost / exterior /
  out-of-grid / free front / dedup / fail-closed schema.
- A3 oracle emit fixture rerun (spike `1d935f3`): scripts/spike_prod_scale_lib/
  oracle_emit_fixture.py 的 _emit_f3 driver 从 stub-skip 升级到 explicit
  target_poses-driven 真 emit. _DRIVERS dict 注册 port_exposure (was skipped).
  run_emit 用 redistributed_per_family=max(6, ...) 让 F6 / F7 state-design
  cap shortfall 由其它 family 补齐 (F6 emit 4 / F7 emit 4 due to state
  design; 其它 7 family emit 6 each → 50 total). 结果: 50 cert × 9 family ×
  0 unsound, G10 SOFT-FAIL → PASS unlocked.
- Spike telemetry rss_sample_after_solve raw event (spike `b1bab5c`): GPT pro
  v15 三审 finding 4 后续 — raw telemetry max 0.866 GB 来自 1Hz background
  rss_sample, after-solve peak 1.03 GB 只在 phase_b_results.json aggregate.
  Reviewer 要求 raw event 在 solve completion 时刻直接 emit. Fix: telemetry.
  emit_rss_after_solve(buf, tier, rss_bytes, vms_bytes) 新 event type
  "rss_sample_after_solve" 含 tier tag + rss_bytes / rss_gb / vms_bytes.
  scale_ramp.run_one_tier 在 solver.Solve(model) 返回后立刻 emit; per tier
  1 event (5 per Phase B run). 1Hz background sampler 不动 (新 event 是
  补充). N11 audit 阈值不变 (3 必 event class 不含此).
- Phase B full rerun (spike `6e6db10`): 用新 fixture (50 cert) + 新 telemetry
  event. 验证: 9 G PASS + 0 N trigger + G6a SOFT-FAIL remains (toy master
  inherent, 180s wall cap at FEASIBLE + 0.12% bound gap, documented Layer-2
  risk #2). Overall verdict: GO_WITH_MINOR (G6a SOFT 仍, G10 closed).

## Post-patch 段 (v13 carryover)

GPT pro audit at cb8e347 → 3 commit landed on master:

- `68fa7f0` fix(cuts): bind F7/F8 validator to candidate_placements pose registry
- `a3414ee` fix(cuts): drop stale state.source_digest fallback in 7 oracles
- `035bd21` docs: archive Phase 1.2 GPT pro audit + fix lifecycle line ref

cb8e347 时 6 finding 状态 + 3 commit 改动范围在
`docs/research/phase1_2_gpt_pro_audit_20260525/AUDIT_REPORT.md`. Finding 4
(F8 performance — `_pole_pole_edges` O(n^2) + 28s connected large-radius
test) 在 v15 master 状态: 见 git log 查 `_pole_pole_edges` 范围. Finding 5
(Mini Step 8 spike) 对应 spike 数据见下 "Spike close gate" 段.

详 `docs/research/phase1_2_gpt_pro_audit_20260525/`:

- `AUDIT_REPORT.md` — 6 finding 全文
- `patches/0001-bind-power-family-pose-cells-and-digest.py` — 210 行 patch
  script
- `repro/` — 4 反例脚本 (跑法见 § "怎么跑")

## Spike close gate 段 (Finding 5)

Spike design 在 `docs/research/prod_scale_spike_design_20260525/`. 8 路 parallel
opus 子代理 + main merger 产 8-section MERGER.md (commits `45c7a25` →
`f7b88b6`, 3 round Gemini cross-check archive 含 4 round responses).

Spike 实施在 branch `spike/prod_scale_master_integration_20260526` (off master
`f7b88b6`), 11 commit, Phase A (A1/A2/A3) + Phase B (B1-B6) + verdict-fix.
实施 code 不入此包 (PR #1 verdict-only style); 实测数据 6 file overlay 进 zip:

- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md`
  — 12 G PASS / 2 SOFT-FAIL / 0 N + Finding 5 cover + Layer 2 risk register
- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md`
  — A1 branch + A2 failfast probe + A3 oracle emit fixture detail
- `data/cuts/spike/oracle_emit_fixture_45cert.jsonl` — A3 50 cert × 9 family
  oracle 实测 (real `cert_payload_b64` real `pose_count` / `cell_count` /
  `literal_count` per cert; v17 F3 Stage 1 generator live)
- `data/cuts/spike/scale_ramp_results.jsonl` — B2 5-tier ramp 0/1K/10K/50K/100K
  实测 (build / xlate / solve / proto / rss)
- `data/cuts/spike/phase_b_results.json` — Phase B aggregate (B3 feasible_smoke
  10K cut + B2 ramp + B4 filter_mock 10 iter + G/N criteria pass map)
- `data/cuts/spike/telemetry_77754.jsonl` — Phase B raw telemetry (204
  rss_sample + 14 proto_sample + 1 dark_matter_emit + 5 rss_sample_after_solve).
  v17 加 rss_sample_after_solve raw event 一条 per tier (5 tier).

(per MERGER §5.4 G/N criteria, MERGER §5.2 Layer 1 sizing close vs Layer 2
convergence/adversarial defer P1.3A)

### Spike verdict — G6a SOFT-FAIL only

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| G1 build 0 cut | ≤ 10s | 1.95s | PASS |
| G2 build 1K cut | ≤ 20s | 2.02s | PASS |
| G3 build 10K cut | ≤ 30s | 2.13s | PASS |
| G4 build 50K cut | ≤ 300s | 2.66s | PASS |
| G4b build 100K cut | ≤ 600s | 3.31s | PASS |
| G5 0 cut feasibility solve | ≤ 30s | 0.70s (OPTIMAL) | PASS |
| G7 100K solve wall (measure) | — | 0.91s (OPTIMAL) | n/a |
| G8 RSS peak | ≤ 20 GB | 0.98GB in phase_b_results after-solve snapshot; telemetry rss_sample raw max 0.866GB; new rss_sample_after_solve event records per-tier after-solve RSS | PASS, evidence split |
| G9 proto @ 50K | ≤ 500 MB | 17.8MB | PASS |
| G9 proto @ 100K | ≤ 1 GB | 19.3MB | PASS |
| G10 oracle real-emit cert fixture (A3) | ≥45 + 9 families + 0 unsound | 50 cert / 9 families / 0 unsound | PASS |
| G11 active filter Hybrid mock loop | ≤ 100ms/iter + eviction fires | total 0.071s, max 9.3ms, evict @ iter [6] | PASS |
| G17 failfast probe (A2) | ≤ 15s | 3.4s | PASS |
| G6a feasible smoke wall | < 180s cap | 180.01s | **FAIL (SOFT)** |
| G6a feasible smoke status | OPTIMAL/FEASIBLE | FEASIBLE | PASS |
| G6a best_objective_bound valid | not None | 76884.0 | PASS |
| G6b random cut tolerate-INFEAS wall | > 1s if INFEASIBLE | 0.76s (OPTIMAL) | PASS |

13 hard G PASS / 1 G SOFT-FAIL (G6a wall hit 180s cap) / 0 hard N trigger.
G10 SOFT-FAIL (v15/v16) closed by F3 special-case phase Stage 1 generator
(master `c768806`) + A3 rerun (spike `1d935f3`) — fixture grew 44 → 50 cert,
8 → 9 family coverage, 0 unsound unchanged.

G6a SOFT-FAIL detail: solver 180s 后 status FEASIBLE + obj 76795 +
best_objective_bound 76884 (gap 0.12%) — 这是 toy master 在 wall 内未证 OPTIMAL
但 bound 有效, **不是 Presolve crash** (Presolve crash 是 N2 anti-pattern, 这里
G6a 三项 status / bound 都 PASS, 只 wall 项 FAIL). 真 PoseBoolExactMaster
(port-linking + ExactlyOne per instance + anti-overlap) gap 可能更大, 列入
P1.3A LBBD outer-loop 不可假设 single-solve termination.

### Finding 5 (5 项) cover evidence

| # | Finding 5 item | Spike evidence | Cover? |
|---|---|---|---|
| 1 | 真 prod registry build master var | A3 oracle emit + B1 load_pose_registry: 81,795 BoolVar from real `data/preprocessed/candidate_placements.json` 7 facility pool | YES |
| 2 | 真 cut body 分布 (replacing toy 1-3-5 literal) | A3 jsonl 50 cert × 9 family (F3 special-case phase Stage 1 generator live) with real `pose_count` / `cell_count` / `literal_count` per cert | YES |
| 3 | build wall / proto / RSS / solve wall 实测 | B2 ramp: build 2.04–3.39s, proto 16.3–19.7 MB, build RSS 0.834–0.866 GB; phase_b_results after-solve RSS peak 1.029 GB; solve 0.73–0.87s across 0–100K | YES, but 1.029GB peak needs raw telemetry event |
| 4 | active filter @ 10K/50K/100K, Hybrid score | B4 mock loop 10 iter: total 0.073s, eviction fired iter [6] (52K→30K), age_decay validated | YES |
| 5 | feasible realistic case 避 INFEAS-早停 | B3 feasible smoke: 10K known-feasible cut + Maximize obj → FEASIBLE obj=76795 bound=76884 gap 0.12% NOT Presolve-crash | YES (G6a wall SOFT FAIL) |

### Q8 semantic gap (Gemini round 3 文档化)

Spike GO close **Sizing only**. 不 close **Convergence** (real
PoseBoolExactMaster + LBBD multi-iter behavior under 81K BoolVar) / **Adversarial
robustness** (F1/F2/F3 patch hold under 100K scale + 50 bad / 9950 good inject).
后两者入 P1.3A 主体 risk register (verdict.md §"Layer 2 risk acknowledgment" 列
5 项 — v15 时 6 项含 #0 G10 fixture coverage; v17 #0 项 closed by F3 Stage 1
generator + A3 rerun, 余下 5 项 #1-#5 仍 open).

## 本次 build 实测数据

pytest src/tests/cuts/ (普通): 398 pass (post-patch state, unchanged since v13)
mypy --strict --explicit-package-bases src/cuts/: 35 source 0 errors
ruff check src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py: 0 issue
vulture --min-confidence 100: 0 issue
bandit -q -r src/cuts/: 0 issue
radon cc src/cuts/ -s -a: average B (5.14), max C(15), no D

(spike scripts/spike_prod_scale_runner.py + scripts/spike_prod_scale_lib/ 不入
此包, 故 pytest / mypy / ruff 等不覆盖 spike code. spike data 6 file overlay
只是数据 artifacts.)

## Phase 1.2 cross-check 数据 (v13 carryover)

每 family 的 round / finding count / Gemini raw response 完整在
`docs/research/p1_2b_*/` 各 round 目录:

| Family | Cross-check round 目录 | round 数 | finding 数 | last commit |
|---|---|---|---|---|
| F5 pattern_nogood | `p1_2b_*f5*` / `gemini_cross_check_phase1_2_f5_round3_20260524/` | 3 | 10 (4+4+2) | `9cd676a` |
| F9 density_envelope | `p1_2b_f9_density_envelope_gemini_round{1,2,3}_20260524/` + commit `0bed978` (R4 revert R3) | 4 | 3+2+1+revert | `0bed978` |
| F2 cutset / F4 component_reach | `p1_2b_f2_f4_gemini_round{1,2,3}_20260524/` | 3 | 3 (2+1+0) | `180400b` |
| F6 shape_packing_hall | `p1_2b_f6_shape_packing_hall_gemini_round{1,2,3}_20260525/` | 3 | 7 (4+3+0) | `64cd15f` |
| F7 power_hitting_set | `p1_2b_f7_power_hitting_set_gemini_round{1,2}_20260525/` | 2 | 5 (4+1) | `e5f0e18` |
| F8 power_grid_reach | `p1_2b_f8_power_grid_reach_gemini_round{1,2,3,4,5}_20260525/` | 5 | 14 (4+3+3+4+0) | `4721c04` |
| Mini Step 8 spike | `p1_2b_mini_step_8_spike_20260525/spike_translator.py + verdict.md` | — | — | `3f1c581` |

Mini Step 8 spike (v13 carryover, 50 BoolVar toy master, 不替代 v14/v15 spike):

| Total cuts | Build (s) | Solve (s) | Status |
|---:|---:|---:|---|
| 100 | 0.001 | 0.002 | OPTIMAL |
| 1,000 | 0.012 | 0.000 | INFEASIBLE |
| 10,000 | 0.114 | 0.002 | INFEASIBLE |

v14/v15 spike (Finding 5 close gate, 81,795 BoolVar prod registry) 数据见上
"Spike close gate 段" — 数量级跟 mini step 8 不同.

## 解包步骤

```bash
unzip -q phase1_2_spike_review_v17.zip
cd _phase1_2_pkg_v17
chmod +x tools/7za && ./tools/7za x project.7z
cd project
```

## 怎么跑 (cd project/)

依赖 `zmd_deps_v3.zip` 单独上传.

```bash
python3.10+ -m venv .venv && source .venv/bin/activate
unzip -q ../zmd_deps_v3.zip -d /tmp/deps
pip install --find-links /tmp/deps -r requirements.txt

# Cut framework 单元测试
.venv/bin/python -m pytest src/tests/cuts/ -q
.venv/bin/python -O -m pytest src/tests/cuts/ -q

# 静态工具
.venv/bin/python -m ruff check src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py
.venv/bin/python -m mypy --strict --explicit-package-bases src/cuts/
.venv/bin/python -m vulture src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py --min-confidence 100
.venv/bin/python -m bandit -q -r src/cuts/
.venv/bin/python -m radon cc src/cuts/ -s -a

# Exit criteria 脚本
.venv/bin/python scripts/b_design_v2_exit_criteria.py

# Mini Step 8 spike 复现 (v13 carryover, 50 BoolVar toy)
.venv/bin/python docs/research/p1_2b_mini_step_8_spike_20260525/spike_translator.py

# Audit reproducer (v16 walk-up 入口 fix 后, 直接 cd project 跑即可, 无需手设 PYTHONPATH)
.venv/bin/python docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_f7_facility_cells_mismatch.py
.venv/bin/python docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_f8_facility_cells_mismatch.py
.venv/bin/python docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_source_digest_quarantine.py
bash docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_f8_slow_generator.sh

# Spike data 不可在 zip 内重跑 (spike runner code 不入包).
# 数据查看:
cat docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md
cat docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md
head data/cuts/spike/oracle_emit_fixture_45cert.jsonl
cat data/cuts/spike/scale_ramp_results.jsonl
cat data/cuts/spike/phase_b_results.json
cat data/cuts/spike/telemetry_77754.jsonl | head -20
grep '"rss_sample_after_solve"' data/cuts/spike/telemetry_*.jsonl
```

## 文件地图

### docs/项目说明/ (21 sub-doc + README 索引)

- `README.md` — 总索引 + 受众分流
- `01_overview.md` — 数学问题陈述 + paradigm 选择
- `02_mathematical_foundations.md` — 9 family + sound deduction + scope/replay/multiset/adversarial
- `03_paradigm_death_baseline.md` — 27 lever 死路按数学根据分类
- `04_design_invariants.md` — PROJECT_LOCK §3A 镜像 (F8 mode 锁 / F9 area-only)
- `05_open_questions.md` — 33 + 6 open Q (含 Q10 CP-SAT AddLazyConstraint)
- `06_current_status.md` — Phase 1.1 GO blessed + sound ≠ converge 警句 §6
- `07_historical_review.md`
- `08_phase_1_2_plan.md` — P1.2A + P1.2B-F5/F6/F7/F8/F9
- `09_phase_1_3_plan.md` — P1.3A CP-SAT attach spike (3 sub-route)
- `10_phase_1_5_plan.md` — Production integration + F5/F7 defer items
- `11_dependency_graph.md` / `12_go_criteria.md` (含 §8.1.x P1.2 P0 acceptance) / `13_schedule_estimate.md`
- `14_risk_rollout.md` / `15_workflow_testing.md` (含 §21.7 11 red fixture matrix)
- `16_workflow_review.md` / `17_workflow_telemetry.md` (含 dark matter telemetry)
- `18_workflow_env_config.md` / `19_implementation_rhythm.md` / `20_skip_directions.md` / `21_glossary.md`

### docs/research/prod_scale_spike_design_20260525/ (Spike design + run data)

- `MERGER.md` (commit `f7b88b6` 终态) — 8-section main merger doc (8 路 parallel
  opus 子代理 投 + main 收 + 3 round Gemini cross-check 修)
- `agent_outputs/` — 8 路 parallel agent raw transcript (correctness / throughput /
  adversarial / integration / simplicity / rollback / observability / historical)
- `gemini_cross_check_round{1,2,3}_20260525/` — 3 round MERGER 数学审查 raw
  response + verdict + fix patch
- `spike_run_20260526/verdict.md` — 12 G PASS / 2 SOFT-FAIL / 0 N verdict (post-二审)
- `spike_run_20260526/phase_a_report.md` — A1/A2/A3 phase A detail

### data/cuts/spike/ (Spike phase B 实测数据 overlay)

- `oracle_emit_fixture_45cert.jsonl` — 50 cert × 9 family A3 fixture (real oracle
  emit, ~71 KB; v17 F3 Stage 1 generator live)
- `scale_ramp_results.jsonl` — B2 5-tier ramp 0/1K/10K/50K/100K
- `phase_b_results.json` — Phase B aggregate (B3 + B2 + B4 + G/N pass map)
- `telemetry_77754.jsonl` — Phase B raw telemetry (204 rss_sample + 14
  proto_sample + 1 dark_matter_emit + 5 rss_sample_after_solve). v17 加
  rss_sample_after_solve raw event class.

(注: spike-only implementation code `scripts/spike_prod_scale_runner.py` +
`scripts/spike_prod_scale_lib/*.py` **不入此包** — 详 `SPIKE_COMMIT_LOG.md`)

### docs/research/p3_b_design_v2_20260521/ (framework spec + family spec + audit archive)

- `cut_lifecycle_v2.md` / `state_machine_v2.md` / `schema_update_v3.md`
- `cut_family_specs/01-09_*.md` — 9 family spec (F1-F9)
- `red_fixtures/F1-F5*.md` — 5 known-infeasibility 反例 (+ P1.2B 加 11 fixture 详 `docs/项目说明/15`)
- `paradigm_death_timeline.md` — 27 lever chronological
- `external_review/` — Phase 1.1 audit archive
- `cross_check/` — `gemini_round_{14..36}*.md` Phase 1.1 + 1.2 per-commit cross-check

### docs/research/p1_2b_*/ (Phase 1.2 family-level cross-check raw)

每目录含 `prompt.txt` + `gemini_response.md` + `gemini_response_raw.json` (raw JSON +
verdict). 见上表 Family → 目录映射.

### docs/research/phase1_2_gpt_pro_audit_20260525/ (Post-patch audit archive)

- `AUDIT_REPORT.md` — 6 finding 全文
- `README.md` — 审查方法 + apply patch 步骤
- `patches/0001-bind-power-family-pose-cells-and-digest.py` — 210 行可应用脚本
- `repro/repro_f7_facility_cells_mismatch.py` (v16 walk-up to PROJECT_LOCK.md)
- `repro/repro_f8_facility_cells_mismatch.py` (v16 walk-up to PROJECT_LOCK.md)
- `repro/repro_source_digest_quarantine.py` (v16 walk-up to PROJECT_LOCK.md)
- `repro/repro_f8_slow_generator.sh` (v16 walk-up + PYTHON env override)

### docs/research/paradigm_search_review_v12_with_code_20260520/

24 dead lever + 3 alive candidate + 6 paradigm group + shared_infra.

### docs/research/literature_review_papers_20260524/

4 路 agent 调研档案 + DA reviewer checkpoint2 + overlap analysis.

### 主流程 src/

```
main.py                              # campaign entry
src/cuts/
├── lifecycle.py                     # 9 step (含 validate_cut_integrity)
├── store.py / replay.py
├── families/
│   ├── region_capacity.py          (F1)
│   ├── cutset.py                   (F2)
│   ├── port_exposure.py            (F3 validator; F3 oracle generator landed v17 in src/cuts/oracles/port_exposure_oracle.py)
│   ├── component_reach.py          (F4)
│   ├── pattern_nogood.py           (F5)
│   ├── shape_packing_hall.py       (F6)
│   ├── power_hitting_set.py        (F7)
│   ├── power_grid_reach.py         (F8)
│   └── density_envelope.py         (F9)
├── oracles/                        # oracle protocol + stub/real per family
├── helpers/                        # bounded_core_minimizer / baseline_partition / ...
└── assumptions/
src/search/                         # outer search + benders loop
src/models/                         # master + binding + routing + flow
src/tests/cuts/                     # 398 cuts test
```

### data/

- `data/preprocessed/candidate_placements.json` — 53 MB production 全集
  (81795 pose / 134 BSP)
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`
- `data/cuts/spike/` — spike 实测数据 4 file (v17: telemetry_21050.jsonl → telemetry_77754.jsonl; new rss_sample_after_solve event class)
- `data/examples/industrial_planner/current_delivery/viewer/` — viewer sample

### 其它

- `rules/canonical_rules.json`
- `specs/` — schema spec
- `scripts/` — 维护脚本 + build + entry-point + readiness gate
  (注: spike runner / spike lib 不在此包)
- `PROJECT_LOCK.md` — proof source / forbidden change 锁
- `CLAUDE.md` — repo-level instruction
"""


CHANGELOG = """# Commit log (master line)

本表列出本次 review pkg master 涵盖的 commit 区间 (按时间序). spike branch
commit 列在 `SPIKE_COMMIT_LOG.md`.


| Commit | Subject |
|---|---|
| 7b0c3c8 | R4 apply Phase 1.1 recheck补强 patch (188 cuts pass, fail-closed schema) |
| e32c655 | review-pkg v11 build script (Phase 1.1 R4 recheck补强, 188 pytest) |
| 4278307 | R5 apply Phase 1.1 final polish (189 cuts pass, F3 grid-bound + 命名口径统一) |
| 11f5337 | feat(F5): land Phase 1.2 P1.2B-F5 pattern_nogood family (246 cuts pass) |
| 3d93b1d | fix(F5): Gemini round 1 fix (4 findings landed) |
| ca60a35 | fix(F5): Gemini round 2 fix (4 findings + 2 LOW landed) |
| 9cd676a | fix(F5): Gemini round 3 minor fix |
| f2d8f31 | feat(F9): land Phase 1.2 P1.2B-F9 density_envelope family (278 cuts pass) |
| 515aed4 | fix(F9): Gemini round 1 fix (1 BLOCKER + 2 HIGH landed) |
| e3aa3e9 | fix(F9): Gemini round 2 fix (1 BLOCKER + 1 HIGH landed) |
| 6153ce5 | fix(F9): Gemini round 3 BLOCKER #1 fix |
| 0bed978 | fix(F9): Gemini round 4 REVERT R3 cert_max=0 patch + positive test |
| 92224c4 | feat(F2/F4): land Phase 1.2 P1.2B-F2/F4 generator + Dinic node-split helper |
| 01d368a | fix(F2/F4): Gemini round 1 fix (1 BLOCKER + 1 LOW landed) |
| d5e653d | fix(F4): Gemini round 2 LOW #3 — carry blocking_facilities cert key |
| 180400b | docs(F2/F4): Gemini round 3 close — GO_WITH_MINOR |
| ec16f06 | docs(06_current_status): sound ≠ converge 警句 |
| 6adc5fd | feat(F6): land Phase 1.2 P1.2B-F6 shape_packing_hall (initial) |
| 9fac6d6 | fix(F6): Gemini round 1 fix |
| 97388a0 | fix(F6): Gemini round 2 fix |
| 64cd15f | docs(F6): Gemini round 3 close |
| c30d681 | feat(F7): land Phase 1.2 P1.2B-F7 power_hitting_set (initial) |
| 9f21901 | fix(F7): Gemini round 1 cross-check fixes |
| e5f0e18 | docs(F7): Gemini round 2 close |
| 4be1b60 | feat(F8): land Phase 1.2 P1.2B-F8 power_grid_reach (initial) |
| b9ab24a | fix(F8): Gemini round 1 cross-check |
| fe7c239 | fix(F8): Gemini round 2 cross-check |
| 29b64d0 | fix(F8): Gemini round 3 cross-check |
| 3b9c8b3 | fix(F8): Gemini round 4 cross-check |
| 4721c04 | docs(F8): Gemini round 5 close |
| 3f1c581 | feat(P1.2): mini Step 8 spike — 6 family CP-SAT translator + 10K cost |
| 5b49f04 | docs(F5/F9): archive Gemini cross-check round raw transcripts |
| 9127c60 | docs(research): archive paradigm v12 review + literature review packages |
| 983ee65 | docs(research): backfill real-measure data for cand_c/smt_mt/sac_hull trials |
| cb8e347 | chore(F7 test): rename unused _kwargs param to clear vulture warning |
| ca10fb0 | review-pkg v12 build script |
| 438f1c9 | review-pkg v12: 重写 README + COMMIT_LOG 清主动性内容 |
| 68fa7f0 | fix(cuts): bind F7/F8 validator to candidate_placements pose registry (audit BLOCKER ×2) |
| a3414ee | fix(cuts): drop stale state.source_digest fallback in 7 oracles (audit HIGH) |
| 035bd21 | docs: archive Phase 1.2 GPT pro audit + fix lifecycle line ref (audit LOW) — v13 build state |
| 45c7a25 | research(spike): prod-scale spike design 8 路 parallel + main merger |
| 52cd014 | research(spike): MERGER round 1 fix per Gemini cross-check |
| 3523526 | research(spike): MERGER round 2 fix per Gemini cross-check |
| b44d0c6 | research(spike): MERGER shrink §5 scope per user scope creep audit |
| f7b88b6 | research(spike): MERGER round 3 fix (G6 + G11 + Q8 文档化) — v14 build state |
| d575a87 | fix(review-pkg v14): replace non-existent scale_ramp_test_smoke.jsonl with phase_b_results.json |
| 832f157 | fix(audit-repro): add sys.path bootstrap + correct shell repro path per GPT pro v14 二审 |
| 3ad3de5 | review-pkg v14 build script — spike close gate snapshot |
| 6abe992 | review-pkg v15 build script — GPT pro v14 二审 fix |
| 5e05ef6 | fix(review-pkg v15): strip verdict-claim priming from README per review-pkg-no-prompt-inside |
| b3c370e | fix(audit-repro): harden project root discovery via PROJECT_LOCK.md walk-up |
| f17f13e | fix(F8): streaming reachability replaces full power graph materialization |
| 3b0cc76 | review-pkg v16 build script — GPT pro v15 三审 fix |
| c768806 | feat(F3): implement port_exposure generator per spec §5 (special-case phase stage 1) |
| b5860bc | fix(F3): Gemini round 1 — add logging.debug to silent skip paths |
| (v17 build) | review-pkg v17 build script — F3 special-case phase Stage 1 + A3 rerun + telemetry rss_sample_after_solve event |
"""


def fetch_spike_commit_log() -> str:
    """Dump spike branch commit log (11 commit on top of master)."""
    result = subprocess.run(
        ["git", "log", "--stat", f"master..{SPIKE_BRANCH}"],
        cwd=str(REPO),
        check=True,
        capture_output=True,
        text=True,
    )
    body = result.stdout
    header = """# Spike branch commit log

Branch `spike/prod_scale_master_integration_20260526` off master `f7b88b6`,
Phase A (A1/A2/A3) + Phase B (B1-B6) + verdict-fix + verdict-fix-2 + merge-
master (v17 incorporate master F3 generator stage 1) + telemetry rss_sample_
after_solve raw event + A3 rerun (44→50 cert) + B6 rerun. Per MERGER §5.1
rollback-safety, spike-only implementation code 不入本包 (PR #1 verdict-only
style):

- `scripts/spike_prod_scale_runner.py`
- `scripts/spike_prod_scale_lib/__init__.py`
- `scripts/spike_prod_scale_lib/toy_translator.py`
- `scripts/spike_prod_scale_lib/scale_ramp.py`
- `scripts/spike_prod_scale_lib/filter_mock.py`
- `scripts/spike_prod_scale_lib/feasible_smoke.py`
- `scripts/spike_prod_scale_lib/oracle_emit_fixture.py`
- `scripts/spike_prod_scale_lib/off_limits_check.py`
- `scripts/spike_prod_scale_lib/telemetry.py`
- `scripts/spike_prod_scale_lib/failfast_probe.py`

Verdict data overlay 入包 (覆盖到 project 相同路径):

- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md`
- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md`
- `data/cuts/spike/oracle_emit_fixture_45cert.jsonl` (v17: 50 cert × 9 family)
- `data/cuts/spike/scale_ramp_results.jsonl`
- `data/cuts/spike/phase_b_results.json`
- `data/cuts/spike/telemetry_77754.jsonl` (v17: 204 rss + 14 proto +
  1 dark_matter + 5 rss_sample_after_solve; v15/v16 = telemetry_21050.jsonl)

下面是 spike branch 完整 commit log + per-commit stat:

```
"""
    footer = "\n```\n"
    return header + body + footer


def overlay_spike_files() -> int:
    """Copy spike data files from spike branch into PROJECT_DIR. Returns count added."""
    added = 0
    for rel_str in SPIKE_OVERLAY_FILES:
        dst = PROJECT_DIR / rel_str
        dst.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "show", f"{SPIKE_BRANCH}:{rel_str}"],
            cwd=str(REPO),
            check=True,
            capture_output=True,
        )
        dst.write_bytes(result.stdout)
        added += 1
        print(f"  overlay: {rel_str} ({len(result.stdout)} bytes)")
    return added


def main() -> int:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    PROJECT_DIR.mkdir(parents=True)

    file_count = 0
    skipped = 0
    total_bytes = 0
    for src in REPO.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(REPO)
        if should_skip(rel):
            skipped += 1
            continue
        dst = PROJECT_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        file_count += 1
        total_bytes += src.stat().st_size

    print(f"Project copy: {file_count} files / {total_bytes/(1024*1024):.1f} MB unzipped")
    print(f"Skipped: {skipped} files")

    print("Overlaying spike data files from spike branch...")
    spike_added = overlay_spike_files()
    file_count += spike_added
    print(f"Spike overlay: {spike_added} files added")

    spike_commit_log = fetch_spike_commit_log()
    (PROJECT_DIR / "SPIKE_COMMIT_LOG.md").write_text(spike_commit_log, encoding="utf-8")
    (PROJECT_DIR / "README.md").write_text(README_V17, encoding="utf-8")
    (PROJECT_DIR / "COMMIT_LOG.md").write_text(CHANGELOG, encoding="utf-8")
    file_count += 3

    # Sanity check: spike-only code MUST NOT be in PROJECT_DIR
    forbidden_hits = []
    for forbidden in SPIKE_FORBIDDEN_PATHS:
        check_path = PROJECT_DIR / forbidden
        if check_path.exists():
            forbidden_hits.append(str(check_path.relative_to(PROJECT_DIR)))
    if forbidden_hits:
        print(f"FATAL: spike-only paths leaked into project/: {forbidden_hits}")
        return 1
    print(f"Spike forbidden path check: 0 leak (all {len(SPIKE_FORBIDDEN_PATHS)} paths absent)")

    print("Compressing project/ → project.7z (-mx=9 ultra)...")
    subprocess.run(
        ["7z", "a", "-mx=9", "-bd", "-y", str(SEVENZ_PATH), "project"],
        cwd=str(OUT_DIR),
        check=True,
        capture_output=True,
    )
    sevenz_mb = SEVENZ_PATH.stat().st_size / (1024 * 1024)
    print(f"7z size: {sevenz_mb:.2f} MB")

    shutil.rmtree(PROJECT_DIR)

    tools_dir = OUT_DIR / "tools"
    tools_dir.mkdir()
    shutil.copy2(SEVENZA_SRC, tools_dir / "7za")
    (tools_dir / "7za").chmod(0o755)

    (OUT_DIR / "README.md").write_text(README_V17, encoding="utf-8")
    (OUT_DIR / "COMMIT_LOG.md").write_text(CHANGELOG, encoding="utf-8")
    (OUT_DIR / "SPIKE_COMMIT_LOG.md").write_text(spike_commit_log, encoding="utf-8")

    if OUT_ZIP.exists():
        OUT_ZIP.unlink()
    subprocess.run(
        ["zip", "-rq", str(OUT_ZIP), OUT_DIR.name],
        cwd=str(OUT_DIR.parent),
        check=True,
    )
    zip_mb = OUT_ZIP.stat().st_size / (1024 * 1024)
    print(f"Output: {OUT_ZIP}")
    print(f"Zip 壳 size: {zip_mb:.2f} MB")
    print(f"  ├─ project.7z: {sevenz_mb:.2f} MB ({file_count} files, {total_bytes/(1024*1024):.1f} MB unzipped + spike overlay)")
    print(f"  ├─ tools/7za: {(SEVENZA_SRC.stat().st_size)/(1024*1024):.2f} MB (Linux x64 ELF)")
    print(f"  ├─ README.md")
    print(f"  ├─ COMMIT_LOG.md")
    print(f"  └─ SPIKE_COMMIT_LOG.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
