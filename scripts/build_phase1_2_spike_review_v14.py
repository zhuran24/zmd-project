#!/usr/bin/env python3
"""Build phase1_2_spike_review_v14.zip — Phase 1.2 spike close gate snapshot.

v13 → v14 change: include Finding 5 close gate spike verdict.

v13 was post-patch (3 commit fix BLOCKER ×2 + HIGH + LOW from GPT pro audit cb8e347),
with `docs/research/prod_scale_spike_design_20260525/**` EXCLUDED (design then in-flight).

v14 adds:
- master full history through `f7b88b6` (含 spike design 8 路 parallel + main merger +
  3 round Gemini cross-check archive, all on master now)
- spike branch overlay (5 file + 1 commit log):
  - docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md
  - docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md
  - data/cuts/spike/oracle_emit_fixture_45cert.jsonl
  - data/cuts/spike/scale_ramp_results.jsonl
  - data/cuts/spike/scale_ramp_test_smoke.jsonl
  - SPIKE_COMMIT_LOG.md (spike branch 10 commit log dump)

v14 does NOT include spike-only implementation code (per MERGER §5.1 rollback-safety
"PR #1 verdict-only style, PR #2 重写 P1.3A 实施 不 cherry-pick spike code"):
- scripts/spike_prod_scale_runner.py
- scripts/spike_prod_scale_lib/*.py

Strategy 同 v13:
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
OUT_DIR = Path("/tmp/_phase1_2_pkg_v14")
PROJECT_DIR = OUT_DIR / "project"
SEVENZ_PATH = OUT_DIR / "project.7z"
OUT_ZIP = Path("/home/zhuran24/linwin_share/phase1_2_spike_review_v14.zip")

SEVENZA_SRC = Path("/usr/lib/7zip/7za")

SPIKE_BRANCH = "spike/prod_scale_master_integration_20260526"

# Spike branch file overlay (verdict data only — NOT spike-only implementation code).
# Per MERGER §5.1 rollback-safety: PR #1 verdict-only style.
SPIKE_OVERLAY_FILES = [
    "docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md",
    "docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md",
    "data/cuts/spike/oracle_emit_fixture_45cert.jsonl",
    "data/cuts/spike/scale_ramp_results.jsonl",
    # phase_b_results.json contains B3 feasible_smoke + B2 scale ramp aggregate
    # (task spec mentioned scale_ramp_test_smoke.jsonl which does not exist on
    # spike branch — phase_b_results.json is the actual artifact carrying B3
    # smoke data, more complete than a hypothetical jsonl smoke file)
    "data/cuts/spike/phase_b_results.json",
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


README_V14 = """# 终末地工业规划器 — 项目快照

终末地 (Arknights: Endfield) 70×70 工业规划器 certified-exact 最大空矩形求解器.
目标 `max_lex(area, min_side)`. 266 mandatory facility, OR-Tools 9.15
CP-SAT, LBBD 分解 (master → binding → routing → flow). 详
`docs/项目说明/01_overview.md` + `02_mathematical_foundations.md`.

全项目内容 (src + docs + rules + data + scripts + main.py + spec + audit archive).

Build: master commit `f7b88b6` (详 `COMMIT_LOG.md`) + spike overlay (5 file + 1
SPIKE_COMMIT_LOG, 详 `SPIKE_COMMIT_LOG.md`).

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

## Post-patch 段 (v13 carryover)

GPT pro audit at cb8e347 → 3 commit landed on master:

- `68fa7f0` fix(cuts): bind F7/F8 validator to candidate_placements pose registry
- `a3414ee` fix(cuts): drop stale state.source_digest fallback in 7 oracles
- `035bd21` docs: archive Phase 1.2 GPT pro audit + fix lifecycle line ref

原 5 finding 中 4 finding (1 BLOCKER + 1 BLOCKER + 1 HIGH + 1 LOW) 已修.
Finding 4 (F8 performance — `_pole_pole_edges` O(n^2) + 28s connected
large-radius test) 仍 open. Finding 5 (Mini Step 8 spike 不足以作 prod
integration close gate) 通过本次 spike 验证 (详下 "Spike close gate" 段).

详 `docs/research/phase1_2_gpt_pro_audit_20260525/`:

- `AUDIT_REPORT.md` — 6 finding 全文
- `patches/0001-bind-power-family-pose-cells-and-digest.py` — 210 行 patch
  script (前 2 commit 已 land)
- `repro/` — 4 反例脚本

## Spike close gate 段 (Finding 5)

Spike design 在 `docs/research/prod_scale_spike_design_20260525/`. 8 路 parallel
opus 子代理 + main merger 产 8-section MERGER.md (commits `45c7a25` →
`f7b88b6`, 3 round Gemini cross-check archive 含 4 round responses).

Spike 实施在 branch `spike/prod_scale_master_integration_20260526` (off master
`f7b88b6`), 10 commit, Phase A (A1/A2/A3) + Phase B (B1-B6). 实施 code 不入此
包 (PR #1 verdict-only style); 实测数据 5 file overlay 进 zip:

- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md`
  — 13 G PASS / 1 SOFT-FAIL / 0 N + Finding 5 cover + Layer 2 risk register
- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md`
  — A1 branch + A2 failfast probe + A3 oracle emit fixture detail
- `data/cuts/spike/oracle_emit_fixture_45cert.jsonl` — A3 44 cert × 9 family
  oracle 实测 (real `cert_payload_b64` real `pose_count` / `cell_count` /
  `literal_count` per cert)
- `data/cuts/spike/scale_ramp_results.jsonl` — B2 5-tier ramp 0/1K/10K/50K/100K
  实测 (build / xlate / solve / proto / rss)
- `data/cuts/spike/phase_b_results.json` — Phase B aggregate (B3 feasible_smoke
  10K cut + B2 ramp + B4 filter_mock 10 iter + G/N criteria pass map)

(per MERGER §5.4 G/N criteria, MERGER §5.2 Layer 1 sizing close vs Layer 2
convergence/adversarial defer P1.3A)

### Spike verdict — GO_WITH_MINOR

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| G1 build 0 cut | ≤ 10s | 2.02s | PASS |
| G2 build 1K cut | ≤ 20s | 2.04s | PASS |
| G3 build 10K cut | ≤ 30s | 2.17s | PASS |
| G4 build 50K cut | ≤ 300s | 2.71s | PASS |
| G4b build 100K cut | ≤ 600s | 3.38s | PASS |
| G5 0 cut feasibility solve | ≤ 30s | 0.71s (OPTIMAL) | PASS |
| G7 100K solve wall (measure) | — | 0.88s (OPTIMAL) | n/a |
| G8 RSS peak | ≤ 20 GB | 1.03GB | PASS |
| G9 proto @ 50K | ≤ 500 MB | 18.0MB | PASS |
| G9 proto @ 100K | ≤ 1 GB | 19.7MB | PASS |
| G10 oracle real-emit 45 cert (A3) | ≥45 + 0 unsound | 44 cert / 0 unsound | PASS |
| G11 active filter Hybrid mock loop | ≤ 100ms/iter + eviction fires | total 0.073s, max 9.5ms, evict @ iter [6] | PASS |
| G17 failfast probe (A2) | ≤ 15s | 3.4s | PASS |
| G6a feasible smoke wall | < 180s cap | 180.00s | **FAIL (SOFT)** |
| G6a feasible smoke status | OPTIMAL/FEASIBLE | FEASIBLE | PASS |
| G6a best_objective_bound valid | not None | 76884.0 | PASS |
| G6b random cut tolerate-INFEAS wall | > 1s if INFEASIBLE | 0.82s (OPTIMAL) | PASS |

13 hard G PASS / 1 G SOFT-FAIL (G6a wall hit 180s cap) / 0 hard N trigger.

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
| 2 | 真 cut body 分布 (replacing toy 1-3-5 literal) | A3 jsonl 44 cert × 9 family with real `pose_count` / `cell_count` / `literal_count` | YES |
| 3 | build wall / proto / RSS / solve wall 实测 | B2 ramp: build 2.04–3.39s, proto 16.3–19.7 MB, RSS 0.61–0.83 GB, solve 0.73–0.87s across 0–100K | YES |
| 4 | active filter @ 10K/50K/100K, Hybrid score | B4 mock loop 10 iter: total 0.073s, eviction fired iter [6] (52K→30K), age_decay validated | YES |
| 5 | feasible realistic case 避 INFEAS-早停 | B3 feasible smoke: 10K known-feasible cut + Maximize obj → FEASIBLE obj=76795 bound=76884 gap 0.12% NOT Presolve-crash | YES (G6a wall SOFT FAIL) |

### Q8 semantic gap (Gemini round 3 文档化)

Spike GO close **Sizing only**. 不 close **Convergence** (real
PoseBoolExactMaster + LBBD multi-iter behavior under 81K BoolVar) / **Adversarial
robustness** (F1/F2/F3 patch hold under 100K scale + 50 bad / 9950 good inject).
后两者入 P1.3A 主体 risk register (verdict.md §"Layer 2 risk acknowledgment" 列
5 项).

## 本次 build 实测数据

pytest src/tests/cuts/ (普通): 398 pass (post-patch state, unchanged since v13)
mypy --strict --explicit-package-bases src/cuts/: 35 source 0 errors
ruff check src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py: 0 issue
vulture --min-confidence 100: 0 issue
bandit -q -r src/cuts/: 0 issue
radon cc src/cuts/ -s -a: average B (5.14), max C(15), no D

(spike scripts/spike_prod_scale_runner.py + scripts/spike_prod_scale_lib/ 不入
此包, 故 pytest / mypy / ruff 等不覆盖 spike code. spike data 5 file overlay
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

Mini Step 8 spike (v13 carryover, 50 BoolVar toy master, 不替代 v14 spike):

| Total cuts | Build (s) | Solve (s) | Status |
|---:|---:|---:|---|
| 100 | 0.001 | 0.002 | OPTIMAL |
| 1,000 | 0.012 | 0.000 | INFEASIBLE |
| 10,000 | 0.114 | 0.002 | INFEASIBLE |

v14 spike (Finding 5 close gate, 81,795 BoolVar prod registry) 数据见上 "Spike
close gate 段" — 数量级跟 mini step 8 不同.

## 解包步骤

```bash
unzip -q phase1_2_spike_review_v14.zip
cd _phase1_2_pkg_v14
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

# Audit reproducer (验 4 patch 已 land + 2 open finding 仍可重现)
.venv/bin/python docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_f7_facility_cells_mismatch.py
.venv/bin/python docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_f8_facility_cells_mismatch.py
.venv/bin/python docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_source_digest_quarantine.py
bash docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_f8_slow_generator.sh

# v14 spike data 不可在 zip 内重跑 (spike runner code 不入包).
# 数据查看:
cat docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md
cat docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md
head data/cuts/spike/oracle_emit_fixture_45cert.jsonl
cat data/cuts/spike/scale_ramp_results.jsonl
cat data/cuts/spike/phase_b_results.json
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
- `spike_run_20260526/verdict.md` — 13 G PASS / 1 SOFT-FAIL / 0 N verdict
- `spike_run_20260526/phase_a_report.md` — A1/A2/A3 phase A detail

### data/cuts/spike/ (Spike phase B 实测数据 overlay)

- `oracle_emit_fixture_45cert.jsonl` — 44 cert × 9 family A3 fixture (real oracle
  emit, 65KB)
- `scale_ramp_results.jsonl` — B2 5-tier ramp 0/1K/10K/50K/100K
- `phase_b_results.json` — Phase B aggregate (B3 + B2 + B4 + G/N pass map)

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

### docs/research/phase1_2_gpt_pro_audit_20260525/ (Post-patch audit archive — v13 carryover)

- `AUDIT_REPORT.md` — 6 finding 全文
- `README.md` — 审查方法 + apply patch 步骤
- `patches/0001-bind-power-family-pose-cells-and-digest.py` — 210 行可应用脚本
- `repro/repro_f7_facility_cells_mismatch.py`
- `repro/repro_f8_facility_cells_mismatch.py`
- `repro/repro_source_digest_quarantine.py`
- `repro/repro_f8_slow_generator.sh`

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
│   ├── port_exposure.py            (F3)
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
- `data/cuts/spike/` — spike 实测数据 3 file (本次新增 overlay)
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
"""


def fetch_spike_commit_log() -> str:
    """Dump spike branch commit log (10 commit on top of master)."""
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
10 commit Phase A (A1/A2/A3) + Phase B (B1-B6). Per MERGER §5.1 rollback-safety,
spike-only implementation code 不入本包 (PR #1 verdict-only style):

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

Verdict data 5 file overlay 入包 (覆盖到 project 相同路径):

- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md`
- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md`
- `data/cuts/spike/oracle_emit_fixture_45cert.jsonl`
- `data/cuts/spike/scale_ramp_results.jsonl`
- `data/cuts/spike/phase_b_results.json`

下面是 spike branch 完整 commit log + per-commit stat:

```
"""
    footer = "\n```\n"
    return header + body + footer


def overlay_spike_files() -> int:
    """Copy 5 spike data files from spike branch into PROJECT_DIR. Returns count added."""
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
    (PROJECT_DIR / "README.md").write_text(README_V14, encoding="utf-8")
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

    (OUT_DIR / "README.md").write_text(README_V14, encoding="utf-8")
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
