#!/usr/bin/env python3
"""Build phase1_2_spike_review_v19.zip — GPT v18 五审 evidence + manifest fix.

v18 → v19 change: GPT pro v18 五审 verdict GO_WITH_MINOR — catch 1 new
evidence bug + 1 doclag MINOR. v19 fix 全部并 rebuild 求 clean GO:

- Evidence bug (BLOCKER for sizing claim): B2 scale ramp 100K tier
  `cut_count_applied=88,039` not 100,000 (12% skip) — because v18 spike
  snapshot `toy_translator.py` `nogood_families` set 缺 `port_exposure`,
  导致 F3 cert (50 中 6 = 12%) 在 oversample 时全部 skipped.
  v19 fix: spike branch `b0b8bef` apply patch 0001 toy_translator —
  `nogood_families` 增 `port_exposure`, family-shape comment 改 stub →
  AddBoolOr two-literal no-good (跟 F5/F7/F8 同 pattern).
  v19 rerun: spike branch `4e80405` Phase B rerun verify 5/5 tier
  cut_count_applied == cut_count_target. New 100K: build 2.44s, solve
  1.13s, proto 20.62 MB, RSS_after_solve 1.03 GB — 全 G threshold PASS.
  verdict.md auto-regenerate, doclag refresh spike branch `2b11147`.

- Doclag (3 spike snapshot file): oracle_emit_fixture.py + scale_ramp.py +
  toy_translator.py 顶部 docstring fix per patch 0001 (F3 stub → real-emit
  + 44/8 cert → 50/9 cert + "44 cert / oversample > 44" → "50 cert / >50").

- Manifest 命令 fix (2 README): `sha256sum -c code_context/SHA256SUMS...`
  失败 (file paths in manifest are relative to code_context/), 改为
  `(cd code_context && sha256sum -c SHA256SUMS.spike_code.txt)`.

v18 五审 patches/0001 union of 5 hunks:
- README.md (build script output): manifest command
- code_context/README.md (build script CODE_CONTEXT_README): manifest command
- code_context/spike/spike_prod_scale_lib/toy_translator.py: port_exposure fix
- code_context/spike/spike_prod_scale_lib/oracle_emit_fixture.py: doclag
- code_context/spike/spike_prod_scale_lib/scale_ramp.py: doclag

v19 also re-uses the v18 framework verbatim (all v17→v18 changes still
hold): code_context/spike/ overlay (MINOR #2), Gemini F3 archive
(MINOR #3), active_port_witness P1.5+ risk (MINOR #4), F3 self-blocker
guard (MINOR #5), and v18 doclag (MINOR #1).

Historical v17→v18 change set (still in v19):

- MINOR #1: doclag fix (Reviewer A/B patch 0001 union)
  - README "398 pytest pass" → "413 pytest pass" + python -O 行
  - README G8 行 + Finding 5 #3 行 v17 实测数 (raw 0.866→1.008 GB, after-
    solve max 0.983 GB, 不是 1.029 GB peak)
  - README radon "B 5.14, max C(15)" → "B 5.21, max C(17)"
  - README build header spike branch HEAD `6e6db10` → "spike branch HEAD
    `13a7079` (post-v18 doclag); data-producing Phase B rerun `6e6db10`"
  - spike verdict.md 同步 (G8 row + Finding 5 #3 + Raw artifacts + Unexpected #3)
  - spike phase_a_report.md 加 v17 addendum 标 historical pre-F3 superseded

- MINOR #2: spike-only code snapshot 入包 (Reviewer B patch 0002 spec)
  - 加 SPIKE_CODE_SNAPSHOT_FILES list 9 文件
  - 从 spike branch overlay 到 `code_context/spike/` 子目录
  - 加 `code_context/README.md` 说明 review-only snapshot 非 master merge target
  - 生成 SHA256SUMS.spike_code.txt manifest

- MINOR #3: Gemini archive 入包 (Reviewer A M3)
  - master commit `8cc6780` land `docs/research/p1_2b_f3_gemini_round{1,2}_20260526/`
  - prompt + response 跟其他 family (F5/F6/F7/F8/F9) 同 archive pattern
  - 自然进包 (master 上的文件, 不需额外 overlay)

- MINOR #4: active_port_witness=None 进 P1.5+ roadmap (Reviewer A M1 / B A3)
  - master commit `9d5d7fa` 改 docs/项目说明/10_phase_1_5_plan.md §13.4
  - 标 production-前置 risk + 二选一 hard gate
  - 自然进包 (master 上的文件)

- MINOR #5: F3 self-blocker defensive guard (Reviewer B F3 NIT, src 改动)
  - master commit `c639063` 改 src/cuts/oracles/port_exposure_oracle.py
  - blocking_group == facility_group + blocking_pose_id == facility_pose_id → skip
  - 1 new test (test_self_blocker_does_not_emit)
  - 414 pytest pass (413 + 1)
  - **注: src 数学层改动. Main 主对话接管 Gemini cross-check round 3 verify;
    sub-agent 本身不调 Gemini.**

Strategy 同 v14-v17:
- 全项目 root copy + 7z -mx=9 + zip 壳 + ship 7za binary
- 排除 .venv / .git / .artifacts / .codex_test_logs / .upstream_clones /
  .claude / _codex_archive
- 不放 prompt / 主动性内容 (per [[review-pkg-no-prompt-inside]])
- v18 新加 code_context/spike/ overlay 是事实层 source snapshot,
  不是 priming.
"""
from __future__ import annotations

import fnmatch
import hashlib
import shutil
import subprocess
from pathlib import Path

REPO = Path("/home/zhuran24/claude-pj/zmd")
OUT_DIR = Path("/tmp/_phase1_2_pkg_v19")
PROJECT_DIR = OUT_DIR / "project"
SEVENZ_PATH = OUT_DIR / "project.7z"
OUT_ZIP = Path("/home/zhuran24/linwin_share/phase1_2_spike_review_v19.zip")

SEVENZA_SRC = Path("/usr/lib/7zip/7za")

SPIKE_BRANCH = "spike/prod_scale_master_integration_20260526"

# Spike branch file overlay (verdict data only — NOT spike-only implementation code).
# v18 同 v17 范围, 加 v18 doclag commit on spike branch.
SPIKE_OVERLAY_FILES = [
    "docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md",
    "docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md",
    "data/cuts/spike/oracle_emit_fixture_45cert.jsonl",
    "data/cuts/spike/scale_ramp_results.jsonl",
    "data/cuts/spike/phase_b_results.json",
    # v17 telemetry kept for history (44→50 cert / pre-v19 numbers)
    "data/cuts/spike/telemetry_77754.jsonl",
    # v19 rerun telemetry (post toy_translator port_exposure fix) — primary
    "data/cuts/spike/telemetry_128896.jsonl",
]

# MINOR #2 per GPT v17 四审 Reviewer B patch 0002 spec:
# Spike-only code snapshot for review reproducibility. NOT a master merge target.
# Placed at `code_context/spike/` (not under `scripts/`) so reviewers cannot
# mistake it for live master code.
SPIKE_CODE_SNAPSHOT_FILES = [
    "scripts/spike_prod_scale_runner.py",
    "scripts/spike_prod_scale_lib/__init__.py",
    "scripts/spike_prod_scale_lib/failfast_probe.py",
    "scripts/spike_prod_scale_lib/feasible_smoke.py",
    "scripts/spike_prod_scale_lib/filter_mock.py",
    "scripts/spike_prod_scale_lib/off_limits_check.py",
    "scripts/spike_prod_scale_lib/oracle_emit_fixture.py",
    "scripts/spike_prod_scale_lib/scale_ramp.py",
    "scripts/spike_prod_scale_lib/telemetry.py",
    "scripts/spike_prod_scale_lib/toy_translator.py",
]

# Spike-only implementation code paths — these MUST NOT appear in project/scripts/.
# They live only on spike branch. v18 still excludes from canonical scripts/ tree;
# only mirrors them under code_context/spike/.
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
    # Spike-only implementation code: hard-block from canonical scripts/ tree.
    # (code_context/spike/ overlay is a separate review snapshot, not under scripts/.)
    for forbidden in SPIKE_FORBIDDEN_PATHS:
        if rel_str == forbidden or rel_str.startswith(forbidden + "/"):
            return True
    for pat in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel_str, pat):
            return True
    return False


CODE_CONTEXT_README = """# code_context/ — review-only source snapshots

This directory contains **read-only source code snapshots** for review
reproducibility per GPT pro v17 四审 Reviewer B patch 0002 spec.

**These files are NOT part of the master merge target.** They live only on
the spike branch (`spike/prod_scale_master_integration_20260526`). They are
included in this review package so reviewers can source-check call sites
that produced the data artifacts in this package.

## spike/

Spike-only Phase B implementation code (10 files):

- `spike_prod_scale_runner.py` — top-level Phase B runner orchestrating
  A2 failfast + A3 oracle emit + B1-B6 phase steps
- `spike_prod_scale_lib/telemetry.py` — `emit_rss_after_solve()` impl
  (relevant for v17 telemetry rss_sample_after_solve raw event class)
- `spike_prod_scale_lib/scale_ramp.py` — `run_one_tier()` impl with
  after-solve emit call site (relevant for telemetry event correctness)
- `spike_prod_scale_lib/oracle_emit_fixture.py` — `_emit_f3` driver +
  `_DRIVERS` registry (relevant for A3 50-cert/9-family fixture)
- `spike_prod_scale_lib/off_limits_check.py` — off-limits enforcement
  harness (no master src writes)
- `spike_prod_scale_lib/failfast_probe.py` — A2 probe impl
- `spike_prod_scale_lib/feasible_smoke.py` — B3 feasible smoke impl
- `spike_prod_scale_lib/filter_mock.py` — B4 active filter mock loop
- `spike_prod_scale_lib/toy_translator.py` — B1 toy translator
  (loose constraints, NOT real PoseBoolExactMaster)
- `spike_prod_scale_lib/__init__.py` — package marker

## SHA256SUMS.spike_code.txt

SHA256 manifest of all snapshot files for integrity verification.
The manifest paths are relative to this directory, so run from inside
``code_context/``:

```bash
(cd code_context && sha256sum -c SHA256SUMS.spike_code.txt)
```

## Why these are NOT merged to master

Per MERGER §5.1 (rollback-safety, PR #1 verdict-only style): spike
implementation code is intentionally not cherry-picked into master because
the toy translator constraints differ from production
`PoseBoolExactMaster` (ExactlyOne / port-linking / anti-overlap). Spike's
purpose was Sizing Layer-1 measurement (Finding 5 close gate), not
P1.3A 主体 implementation. Production P1.3A walks N=8 parallel design
fresh; cherry-picking spike code would anchor the design on toy
translator choices.

The data artifacts (telemetry / fixture / scale ramp / phase B
aggregate) ARE valid Layer-1 evidence and live in canonical paths
(`data/cuts/spike/`).
"""


README_V19 = """# 终末地工业规划器 — 项目快照 (v19)

终末地 (Arknights: Endfield) 70×70 工业规划器 certified-exact 最大空矩形求解器.
目标 `max_lex(area, min_side)`. 266 mandatory facility, OR-Tools 9.15
CP-SAT, LBBD 分解 (master → binding → routing → flow). 详
`docs/项目说明/01_overview.md` + `02_mathematical_foundations.md`.

全项目内容 (src + docs + rules + data + scripts + main.py + spec + audit archive)
+ v18 起 `code_context/spike/` review-only source snapshot
(v19 含 toy_translator port_exposure fix).

Build: master commit `9d5d7fa` (详 `COMMIT_LOG.md`) + spike overlay (6 file +
1 SPIKE_COMMIT_LOG, 详 `SPIKE_COMMIT_LOG.md`, spike branch HEAD `2b11147`;
data-producing Phase B rerun commit `4e80405` post-port_exposure fix).

## v18 → v19 状态变化

v18 (post-MINOR-全-fix + code_context/spike/ snapshot) 之后 GPT pro v18
五审 verdict GO_WITH_MINOR — catch 1 个新 evidence bug + 1 doclag MINOR.
v19 全 fix:

| Commit | Branch | Subject |
|---|---|---|
| `b0b8bef` | spike | [SPIKE-V19-PATCH-0001] toy_translator add port_exposure + 3 file doclag |
| `4e80405` | spike | [SPIKE-V19-RERUN-B2] Phase B rerun (toy_translator port_exposure fix verified) |
| `2b11147` | spike | [SPIKE-V19-VERDICT-UPDATE] refresh recommended-next-step + raw artifact telemetry counts |
| (v19 build) | master | review-pkg v19 build script — GPT v18 五审 evidence + manifest fix |

五审 finding fix 状态:

- **Evidence bug (B2 100K cut_count_applied 88,039 not 100,000) — CLOSED**:
  Root cause = v18 `toy_translator.translate_certs_to_constraints` 的
  `nogood_families` set 缺 `port_exposure`. F3 cert (50 中 6 = 12%) 在 100K
  oversample 时全部走 "Unknown family → skip" 分支, 真到 master 的 cut 数
  = 100K × 88% = 88,039. v19 fix (spike `b0b8bef`): patch 0001 union 5 hunks
  — `nogood_families` 增 `port_exposure` + 3 docstring doclag. v19 rerun
  (spike `4e80405`) Phase B (B3+B2+B4+B5) verify 5/5 tier
  cut_count_applied == cut_count_target:

  | Tier | Target | Applied | Match |
  |---|---|---|---|
  | 0 | 0 | 0 | YES |
  | 1K | 1,000 | 1,000 | YES |
  | 10K | 10,000 | 10,000 | YES |
  | 50K | 50,000 | 50,000 | YES |
  | 100K | 100,000 | 100,000 | YES |

  100K tier 新数: build_wall_s 2.44 (≤ 600s G4b), translation_wall_s 1.66,
  solve_wall_s 1.13 (OPTIMAL), proto_bytesize 20.62 MB (≤ 1 GB G9),
  rss_peak_gb_during_build 0.87, rss_peak_gb_after_solve 1.03 (≤ 20 GB G8).
  全 G threshold PASS.

- **Doclag (manifest 命令 2 处 + spike snapshot 3 file) — CLOSED**:
  本 README + code_context/README.md manifest 命令 `sha256sum -c
  code_context/SHA256SUMS.spike_code.txt` 改 `(cd code_context && sha256sum
  -c SHA256SUMS.spike_code.txt)` (manifest 内 path 是 code_context-relative);
  spike snapshot 3 file (oracle_emit_fixture / scale_ramp / toy_translator)
  顶部 docstring 跟 v18 F3 Stage 1 generator + 50 cert 现状对齐.

verdict.md auto-refresh (spike `2b11147`) 含 v19 patch + B2 rerun commit
SHA + recommended-next-step "v19 package + 五审 finding closed statement"
+ Raw artifacts telemetry rss_sample_after_solve count.

## v17 → v18 状态变化 (历史, 全部仍 in v19)

v17 (post-F3 special-case phase + telemetry rss_after_solve) 之后 GPT pro v17
四审 (两 reviewer 共识 GO_WITH_MINOR) 给 5 项 MINOR finding. v18 全 fix:

| Commit | Branch | Subject |
|---|---|---|
| `13a7079` | spike | [SPIKE-V18-DOCLAG] full doclag fix per GPT v17 四审 Reviewer A/B patch 0001 |
| `c639063` | master | fix(F3): self-blocker defensive guard per GPT v17 四审 Reviewer B NIT |
| `8cc6780` | master | docs(F3): archive Gemini cross-check round 1+2 transcript per GPT v17 四审 Reviewer A M3 |
| `9d5d7fa` | master | docs(P1.5+): document F3 active_port_witness production-前置 risk per GPT v17 四审 Reviewer A M1 |
| (v18 build) | master | review-pkg v18 build script — GPT v17 四审 MINOR 全 fix |

5 项 MINOR fix 状态:

- **MINOR #1 (LOW) doclag**: spike doclag commit `13a7079` 改 verdict.md
  (G8 row 拆 phase_b/raw/after-solve 三口径 + Finding 5 #3 RSS 旧 0.61-0.83 GB
  → v17 实测 + Raw artifacts 补 5 rss_sample_after_solve count + Unexpected #3
  RSS plateau 旧 0.83 GB → 1.008 / 0.983 GB) + phase_a_report.md 加 v17
  addendum (历史 pre-F3 superseded by 50-cert rerun). README_V18 同步全 doclag
  (398→413 pytest + radon B 5.14→5.21 max C 15→17 + raw max 0.866→1.008 GB
  + spike branch HEAD 写法).
- **MINOR #2 (LOW/MEDIUM review-pkg quality) spike code snapshot**: 加
  `code_context/spike/` 目录 (10 文件 + README + SHA256 manifest). 详见
  下面 "v18 新增" 段.
- **MINOR #3 (LOW evidence packaging) Gemini archive**: master `8cc6780` land
  `docs/research/p1_2b_f3_gemini_round{1,2}_20260526/` (prompt + response
  rounds 1, 2), 同其他 family (F5/F6/F7/F8/F9) archive pattern.
- **MINOR #4 (MINOR/production guard) active_port_witness risk**: master
  `9d5d7fa` 改 `docs/项目说明/10_phase_1_5_plan.md` §13.4. F3 active_port_
  witness production-前置 risk 标 hard gate 二选一: validator verify 或
  port-active 上收 master.
- **MINOR #5 (NIT) F3 self-blocker guard**: master `c639063` 改
  `src/cuts/oracles/port_exposure_oracle.py` 加 self-blocker guard
  (blocking == target same group+pose → skip) + 1 new test
  (`test_self_blocker_does_not_emit`). 414 pytest pass (413 + 1).

### v18 新增: code_context/spike/ overlay (MINOR #2)

按 GPT v17 四审 Reviewer B patch 0002 spec, v18 加 spike-only Phase B 实施
code 作 review-only snapshot:

```
code_context/
├── README.md                                      # 详细说明 (review-only / NOT merge target)
├── SHA256SUMS.spike_code.txt                      # SHA256 完整性 manifest
└── spike/
    ├── spike_prod_scale_runner.py                 # 顶层 Phase B runner
    └── spike_prod_scale_lib/
        ├── __init__.py
        ├── failfast_probe.py
        ├── feasible_smoke.py
        ├── filter_mock.py
        ├── off_limits_check.py
        ├── oracle_emit_fixture.py                 # _emit_f3 driver + _DRIVERS registry
        ├── scale_ramp.py                          # run_one_tier + emit_rss_after_solve callsite
        ├── telemetry.py                           # emit_rss_after_solve 实施
        └── toy_translator.py                      # B1 toy translator
```

- 路径 `code_context/spike/` 不是 `scripts/spike_prod_scale_lib/` (防 reviewer
  误以为 master 路径)
- 内容从 spike branch HEAD `13a7079` git show
- canonical `scripts/` 树**不含** spike code (off-limits enforce)

## v13-v17 状态变化 (历史)

详 `COMMIT_LOG.md` 跟下面 "Spike close gate 段". 主要 milestone:

- v13 (post-patch): GPT pro audit cb8e347 6 finding fix landed (3 commit)
- v14: Phase 1.2 spike close gate evidence (5 file overlay + spike commit log)
- v15: GPT pro v14 二审 fix (G10 SOFT-FAIL + telemetry overlay + repro
  sys.path + B2 RSS 口径)
- v16: GPT pro v15 三审 fix (F8 streaming reachability + repro walk-up to
  PROJECT_LOCK.md + RSS evidence boundary 拆)
- v17: F3 special-case phase Stage 1 generator + A3 rerun (44 → 50 cert /
  8 → 9 family) + telemetry rss_sample_after_solve raw event class + Phase B
  full rerun

## Spike close gate 段 (Finding 5)

Spike design 在 `docs/research/prod_scale_spike_design_20260525/`. 8 路 parallel
opus 子代理 + main merger 产 8-section MERGER.md (commits `45c7a25` →
`f7b88b6`, 3 round Gemini cross-check archive 含 4 round responses).

Spike 实施在 branch `spike/prod_scale_master_integration_20260526` (off master
`f7b88b6`), 16 commit (v18 加 doclag + v19 加 patch 0001 + B2 rerun +
verdict-update), Phase A (A1/A2/A3) + Phase B (B1-B6) + verdict-fix. 实施 code
不入 canonical scripts/ (PR #1 verdict-only style); v18 起 review-only
`code_context/spike/` 镜像; v19 实测数据 7 file overlay 进 zip:

- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md`
  — 13 hard G PASS / 1 G SOFT-FAIL (G6a) / 0 hard N + Finding 5 cover +
  Layer 2 risk register (v19 rerun 数字 + 五审 evidence bug close 段)
- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md`
  — A1 branch + A2 failfast probe + A3 oracle emit fixture detail (含 v17 addendum)
- `data/cuts/spike/oracle_emit_fixture_45cert.jsonl` — A3 50 cert × 9 family
  oracle 实测 (real `cert_payload_b64` real `pose_count` / `cell_count` /
  `literal_count` per cert; v17 F3 Stage 1 generator live)
- `data/cuts/spike/scale_ramp_results.jsonl` — B2 5-tier ramp 0/1K/10K/50K/100K
  实测 (v19 rerun, 5/5 tier `cut_count_applied` == `cut_count_target`)
- `data/cuts/spike/phase_b_results.json` — Phase B aggregate (B3 feasible_smoke
  10K cut + B2 ramp + B4 filter_mock 10 iter + G/N criteria pass map; v19 rerun)
- `data/cuts/spike/telemetry_77754.jsonl` — Phase B 原版 raw telemetry
  (历史保留 — pre-v19 toy_translator fix, 204 rss_sample + 14 proto_sample +
  5 rss_sample_after_solve + 1 dark_matter_emit)
- `data/cuts/spike/telemetry_128896.jsonl` — v19 rerun raw telemetry (208
  rss_sample + 14 proto_sample + 5 rss_sample_after_solve + 1 dark_matter_emit;
  pid 128896, primary verdict data source)

### Spike verdict — G6a SOFT-FAIL only

| Criterion | Threshold | Actual (v19 rerun) | Status |
|---|---|---|---|
| G1 build 0 cut | ≤ 10s | 2.22s | PASS |
| G2 build 1K cut | ≤ 20s | 2.42s | PASS |
| G3 build 10K cut | ≤ 30s | 2.53s | PASS |
| G4 build 50K cut | ≤ 300s | 3.28s | PASS |
| G4b build 100K cut | ≤ 600s | 4.10s | PASS |
| G5 0 cut feasibility solve | ≤ 30s | 0.82s (OPTIMAL) | PASS |
| G7 100K solve wall (measure) | — | 1.13s (OPTIMAL) | n/a |
| G8 RSS peak | ≤ 20 GB | rss_peak_gb_after_solve max 1.03 GB @ 100K; raw rss_sample max 1.03 GB | PASS |
| G9 proto @ 50K | ≤ 500 MB | 18.0 MB | PASS |
| G9 proto @ 100K | ≤ 1 GB | 19.7 MB | PASS |
| G10 oracle real-emit cert fixture (A3) | ≥45 + 9 families + 0 unsound | 50 cert / 9 families / 0 unsound | PASS |
| G11 active filter Hybrid mock loop | ≤ 100ms/iter + eviction fires | total 0.083s, max 11.0ms, evict @ iter [6] | PASS |
| G17 failfast probe (A2) | ≤ 15s | 3.4s | PASS (A2 phase_a_report) |
| G6a feasible smoke wall | < 180s cap | 180.01s | **FAIL (SOFT)** |
| G6a feasible smoke status | OPTIMAL/FEASIBLE | FEASIBLE | PASS |
| G6a best_objective_bound valid | not None | 76884.0 | PASS |
| G6b random cut tolerate-INFEAS wall | > 1s if INFEASIBLE | 0.83s (OPTIMAL) | PASS |

13 hard G PASS / 1 G SOFT-FAIL (G6a wall hit 180s cap) / 0 hard N trigger.
G10 SOFT-FAIL (v15/v16) closed by F3 special-case phase Stage 1 generator
(master `c768806`) + A3 rerun (spike `1d935f3`) — fixture grew 44 → 50 cert,
8 → 9 family coverage, 0 unsound unchanged.

v18 五审 evidence bug closed (v19 spike `b0b8bef` + `4e80405`): B2 100K
`cut_count_applied` from 88,039 (88%) to 100,000 (100%) after toy_translator
`nogood_families` 增 `port_exposure`. 5/5 tier `cut_count_applied ==
cut_count_target`. 100K tier numbers above are the v19 rerun data.

G6a SOFT-FAIL detail: solver 180s 后 status FEASIBLE + obj 76795 +
best_objective_bound 76884 (gap 0.12%) — 这是 toy master 在 wall 内未证 OPTIMAL
但 bound 有效, **不是 Presolve crash**. 真 PoseBoolExactMaster gap 可能更大,
列入 P1.3A LBBD outer-loop 不可假设 single-solve termination.

### Finding 5 (5 项) cover evidence

| # | Finding 5 item | Spike evidence | Cover? |
|---|---|---|---|
| 1 | 真 prod registry build master var | A3 oracle emit + B1 load_pose_registry: 81,795 BoolVar from real `data/preprocessed/candidate_placements.json` 7 facility pool | YES |
| 2 | 真 cut body 分布 (replacing toy 1-3-5 literal) | A3 jsonl 50 cert × 9 family (F3 special-case phase Stage 1 generator live) with real `pose_count` / `cell_count` / `literal_count` per cert | YES |
| 3 | build wall / proto / RSS / solve wall 实测 | B2 ramp (v19 rerun): build 2.22–2.45s + translation 0.00–1.66s, proto 16.3–19.7 MB, build RSS 0.834–0.865 GB; after-solve RSS 0.834–1.03 GB; solve 0.82–1.13s across 0–100K (5/5 tier `cut_count_applied` == `cut_count_target` post toy_translator port_exposure fix) | YES |
| 4 | active filter @ 10K/50K/100K, Hybrid score | B4 mock loop 10 iter: total 0.073s, eviction fired iter [6] (52K→30K), age_decay validated | YES |
| 5 | feasible realistic case 避 INFEAS-早停 | B3 feasible smoke: 10K known-feasible cut + Maximize obj → FEASIBLE obj=76795 bound=76884 gap 0.12% NOT Presolve-crash | YES (G6a wall SOFT FAIL) |

### Q8 semantic gap (Gemini round 3 文档化)

Spike close **Sizing only**. 不 close **Convergence** / **Adversarial robustness**.
后两者入 P1.3A 主体 risk register (verdict.md §"Layer 2 risk acknowledgment" 5 项 #1-#5).

## 本次 build 实测数据

pytest src/tests/cuts/: 413 pass (master before MINOR #5) → 414 pass (master
v18 含 MINOR #5 self-blocker guard + 1 new test)
python -O -m pytest src/tests/cuts/: 414 pass (1 warning)
mypy --strict --explicit-package-bases src/cuts/: 35 source 0 errors
ruff check src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py: 0 issue
vulture --min-confidence 100: 0 issue
bandit -q -r src/cuts/: 0 issue
radon cc src/cuts/ -s -a: average B (5.21), max C(17), no D

(canonical scripts/spike_prod_scale_runner.py + scripts/spike_prod_scale_lib/
不入此包; spike code 在 code_context/spike/ review-only snapshot; spike data
6 file overlay 在 canonical 路径.)

## 解包步骤

```bash
unzip -q phase1_2_spike_review_v19.zip
cd _phase1_2_pkg_v19
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

# Audit reproducer (v16 walk-up to PROJECT_LOCK.md)
.venv/bin/python docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_f7_facility_cells_mismatch.py
.venv/bin/python docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_f8_facility_cells_mismatch.py
.venv/bin/python docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_source_digest_quarantine.py
bash docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_f8_slow_generator.sh

# Spike data 不可在 zip 内重跑 (canonical scripts/ 不含 spike code; v18 加 review-only
# snapshot 在 code_context/spike/ 仅供 source-check, 不可直接 import / 跑).
# 数据查看:
cat docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md
cat docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md
head data/cuts/spike/oracle_emit_fixture_45cert.jsonl
cat data/cuts/spike/scale_ramp_results.jsonl
cat data/cuts/spike/phase_b_results.json
head -20 data/cuts/spike/telemetry_128896.jsonl   # v19 primary rerun
head -20 data/cuts/spike/telemetry_77754.jsonl    # pre-v19 historical
grep '"rss_sample_after_solve"' data/cuts/spike/telemetry_*.jsonl

# v18 起 review-only source snapshot (per MINOR #2):
cat code_context/README.md
ls code_context/spike/spike_prod_scale_lib/
(cd code_context && sha256sum -c SHA256SUMS.spike_code.txt)
```

## 文件地图

### docs/项目说明/ (21 sub-doc + README 索引)

- `README.md` — 总索引 + 受众分流
- `01_overview.md` — 数学问题陈述 + paradigm 选择
- `02_mathematical_foundations.md` — 9 family + sound deduction + scope/replay/multiset/adversarial
- `03_paradigm_death_baseline.md` — 27 lever 死路按数学根据分类
- `04_design_invariants.md` — PROJECT_LOCK §3A 镜像 (F8 mode 锁 / F9 area-only)
- `05_open_questions.md` — 33 + 6 open Q
- `06_current_status.md` — Phase 1.1 GO blessed + sound ≠ converge 警句 §6
- `07_historical_review.md`
- `08_phase_1_2_plan.md` — P1.2A + P1.2B-F5/F6/F7/F8/F9
- `09_phase_1_3_plan.md` — P1.3A CP-SAT attach spike (3 sub-route)
- `10_phase_1_5_plan.md` — Production integration + v18 §13.4 F3 active_port_witness production-前置 risk
- `11_dependency_graph.md` / `12_go_criteria.md` / `13_schedule_estimate.md`
- `14_risk_rollout.md` / `15_workflow_testing.md` / `16_workflow_review.md` /
  `17_workflow_telemetry.md` / `18_workflow_env_config.md` /
  `19_implementation_rhythm.md` / `20_skip_directions.md` / `21_glossary.md`

### docs/research/prod_scale_spike_design_20260525/ (Spike design + run data)

- `MERGER.md` (commit `f7b88b6` 终态) — 8-section main merger doc
- `agent_outputs/` — 8 路 parallel agent raw transcript
- `gemini_cross_check_round{1,2,3}_20260525/` — 3 round MERGER 数学审查
- `spike_run_20260526/verdict.md` — 13 G PASS / 1 SOFT-FAIL / 0 N verdict (post-v18 doclag)
- `spike_run_20260526/phase_a_report.md` — A1/A2/A3 phase A detail (含 v17 addendum)

### docs/research/p1_2b_f3_gemini_round{1,2}_20260526/ (v18 加 — MINOR #3)

- `round1/prompt.txt` + `round1/gemini_response.md` — F3 generator soundness review,
  verdict PASS with completeness warnings (silent skip 路径建议加 logging.debug)
- `round2/prompt.txt` + `round2/gemini_response.md` — Round 1 fix verify,
  verdict PASS — .debug level 选 optimal

### data/cuts/spike/ (Spike phase B 实测数据 overlay)

- `oracle_emit_fixture_45cert.jsonl` — 50 cert × 9 family A3 fixture (real
  oracle emit; v17 F3 Stage 1 generator live)
- `scale_ramp_results.jsonl` — B2 5-tier ramp 0/1K/10K/50K/100K (v19 rerun
  `cut_count_applied` == `cut_count_target` 全 5/5)
- `phase_b_results.json` — Phase B aggregate (v19 rerun)
- `telemetry_128896.jsonl` — v19 rerun raw telemetry (208 rss_sample + 14
  proto_sample + 5 rss_sample_after_solve + 1 dark_matter_emit; primary)
- `telemetry_77754.jsonl` — pre-v19 historical raw telemetry (204
  rss_sample + 14 proto_sample + 5 rss_sample_after_solve + 1 dark_matter_emit)

### code_context/spike/ (v18 加 — MINOR #2 spike-only review snapshot)

详 `code_context/README.md`. Source snapshot 10 文件 + SHA256 manifest.
review-only, NOT master merge target.

### docs/research/p3_b_design_v2_20260521/ (framework spec + family spec + audit archive)

详细同 v17.

### docs/research/p1_2b_*/ (Phase 1.2 family-level cross-check raw)

每目录含 `prompt.txt` + `gemini_response.md` (+ raw JSON 部分 family). 见上表
Family → 目录映射. v18 加 F3 round1/round2.

### docs/research/phase1_2_gpt_pro_audit_20260525/ (Post-patch audit archive)

详细同 v17.

### 主流程 src/

```
main.py                              # campaign entry
src/cuts/
├── lifecycle.py                     # 9 step (含 validate_cut_integrity)
├── store.py / replay.py
├── families/
│   ├── region_capacity.py          (F1)
│   ├── cutset.py                   (F2)
│   ├── port_exposure.py            (F3 validator; F3 oracle generator in src/cuts/oracles/port_exposure_oracle.py)
│   ├── component_reach.py          (F4)
│   ├── pattern_nogood.py           (F5)
│   ├── shape_packing_hall.py       (F6)
│   ├── power_hitting_set.py        (F7)
│   ├── power_grid_reach.py         (F8)
│   └── density_envelope.py         (F9)
├── oracles/                        # oracle protocol + stub/real per family (含 v18 F3 self-blocker guard)
├── helpers/                        # bounded_core_minimizer / baseline_partition / ...
└── assumptions/
src/search/                         # outer search + benders loop
src/models/                         # master + binding + routing + flow
src/tests/cuts/                     # 414 cuts test (v18: 413 + 1 self-blocker test)
```

### data/

详细同 v17.

### 其它

- `rules/canonical_rules.json`
- `specs/` — schema spec
- `scripts/` — 维护脚本 + build + entry-point + readiness gate
  (canonical scripts/ 不含 spike code; v18 加 code_context/spike/ review-only mirror)
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
| 3dbfa39 | review-pkg v17 build script — F3 special-case phase close |
| c639063 | fix(F3): self-blocker defensive guard per GPT v17 四审 Reviewer B NIT |
| 8cc6780 | docs(F3): archive Gemini cross-check round 1+2 transcript per GPT v17 四审 Reviewer A M3 |
| 9d5d7fa | docs(P1.5+): document F3 active_port_witness production-前置 risk per GPT v17 四审 Reviewer A M1 |
| 88735ad | review-pkg v18 build script — GPT v17 四审 MINOR 全 fix |
| (v19 build) | review-pkg v19 build script — GPT v18 五审 evidence + manifest fix |
"""


def fetch_spike_commit_log() -> str:
    """Dump spike branch commit log (16 commit on top of master)."""
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
master + telemetry rss_sample_after_solve raw event + A3 rerun (44 → 50 cert)
+ B6 rerun + v17 verdict doclag + v18 doclag (per GPT v17 四审) + v19 patch
0001 toy_translator port_exposure fix + B2 rerun + verdict-update (per GPT
v18 五审).

Per MERGER §5.1 rollback-safety, canonical `scripts/` 不含 spike code (PR #1
verdict-only style). v18 加 `code_context/spike/` review-only source snapshot
(per GPT v17 四审 Reviewer B patch 0002 spec; v19 含 toy_translator fix):

- `scripts/spike_prod_scale_runner.py`
- `scripts/spike_prod_scale_lib/__init__.py`
- `scripts/spike_prod_scale_lib/toy_translator.py` (v19: + port_exposure
  to nogood_families + Python 3.14 portability fix)
- `scripts/spike_prod_scale_lib/scale_ramp.py` (v19: doclag 50 cert)
- `scripts/spike_prod_scale_lib/filter_mock.py`
- `scripts/spike_prod_scale_lib/feasible_smoke.py`
- `scripts/spike_prod_scale_lib/oracle_emit_fixture.py` (v19: doclag F3 real-emit)
- `scripts/spike_prod_scale_lib/off_limits_check.py`
- `scripts/spike_prod_scale_lib/telemetry.py`
- `scripts/spike_prod_scale_lib/failfast_probe.py`

Verdict data overlay 入包 (覆盖到 project 相同路径, v19 7 files):

- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md`
  (v19: refresh G/raw artifact + recommended-next-step + 五审 finding close)
- `docs/research/prod_scale_spike_design_20260525/spike_run_20260526/phase_a_report.md`
- `data/cuts/spike/oracle_emit_fixture_45cert.jsonl` (50 cert × 9 family)
- `data/cuts/spike/scale_ramp_results.jsonl` (v19 rerun, 5/5 tier match)
- `data/cuts/spike/phase_b_results.json` (v19 rerun)
- `data/cuts/spike/telemetry_77754.jsonl` (pre-v19 historical: 204 rss + 14
  proto + 1 dark_matter + 5 rss_sample_after_solve)
- `data/cuts/spike/telemetry_128896.jsonl` (v19 rerun primary: 208 rss + 14
  proto + 1 dark_matter + 5 rss_sample_after_solve)

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


def overlay_spike_code_snapshot() -> int:
    """Copy spike-only source files into code_context/spike/. Returns count added.

    Per GPT v17 四审 Reviewer B patch 0002 spec (MINOR #2). The snapshot is
    placed at code_context/spike/ (not scripts/spike_prod_scale_lib/) so
    reviewers cannot mistake it for canonical master code.
    """
    code_context_dir = PROJECT_DIR / "code_context"
    spike_dir = code_context_dir / "spike"
    spike_dir.mkdir(parents=True, exist_ok=True)

    # Write code_context/README.md explaining review-only nature.
    (code_context_dir / "README.md").write_text(CODE_CONTEXT_README, encoding="utf-8")

    added = 0
    manifest_lines: list[str] = []
    for rel_str in SPIKE_CODE_SNAPSHOT_FILES:
        # rel_str is e.g. "scripts/spike_prod_scale_lib/telemetry.py".
        # We want to place at code_context/spike/spike_prod_scale_lib/telemetry.py
        # i.e. strip "scripts/" prefix.
        if rel_str.startswith("scripts/"):
            dst_rel = rel_str[len("scripts/"):]
        else:
            dst_rel = rel_str
        dst = spike_dir / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "show", f"{SPIKE_BRANCH}:{rel_str}"],
            cwd=str(REPO),
            check=True,
            capture_output=True,
        )
        dst.write_bytes(result.stdout)
        added += 1
        # Compute SHA256 for manifest. Path in manifest is relative to
        # code_context/ so reviewer can `cd code_context && sha256sum -c ...`.
        manifest_path = f"spike/{dst_rel}"
        h = hashlib.sha256(result.stdout).hexdigest()
        manifest_lines.append(f"{h}  {manifest_path}")
        print(f"  code_context overlay: {rel_str} → code_context/{manifest_path} ({len(result.stdout)} bytes)")

    # Write SHA256SUMS manifest (sorted for stable diff).
    manifest_lines.sort()
    (code_context_dir / "SHA256SUMS.spike_code.txt").write_text(
        "\n".join(manifest_lines) + "\n", encoding="utf-8"
    )
    print(f"  code_context: SHA256SUMS.spike_code.txt ({len(manifest_lines)} entries)")
    # README + manifest count as 2 extra files beyond snapshot files
    return added + 2


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
    print(f"Spike data overlay: {spike_added} files added")

    print("Overlaying spike code snapshot to code_context/spike/ (v18 MINOR #2)...")
    snapshot_added = overlay_spike_code_snapshot()
    file_count += snapshot_added
    print(f"Spike code snapshot: {snapshot_added} files added")

    spike_commit_log = fetch_spike_commit_log()
    (PROJECT_DIR / "SPIKE_COMMIT_LOG.md").write_text(spike_commit_log, encoding="utf-8")
    (PROJECT_DIR / "README.md").write_text(README_V19, encoding="utf-8")
    (PROJECT_DIR / "COMMIT_LOG.md").write_text(CHANGELOG, encoding="utf-8")
    file_count += 3

    # Sanity check: spike-only code MUST NOT be in canonical scripts/ tree
    # (it should ONLY live in code_context/spike/).
    forbidden_hits = []
    for forbidden in SPIKE_FORBIDDEN_PATHS:
        check_path = PROJECT_DIR / forbidden
        if check_path.exists():
            forbidden_hits.append(str(check_path.relative_to(PROJECT_DIR)))
    if forbidden_hits:
        print(f"FATAL: spike-only paths leaked into canonical scripts/: {forbidden_hits}")
        return 1
    print(f"Canonical scripts/ forbidden path check: 0 leak (all {len(SPIKE_FORBIDDEN_PATHS)} paths absent from scripts/)")

    # Sanity check: code_context/spike/ MUST have the snapshot files.
    snapshot_check_dir = PROJECT_DIR / "code_context" / "spike"
    for rel_str in SPIKE_CODE_SNAPSHOT_FILES:
        dst_rel = rel_str[len("scripts/"):] if rel_str.startswith("scripts/") else rel_str
        check_path = snapshot_check_dir / dst_rel
        if not check_path.exists():
            print(f"FATAL: spike snapshot missing in code_context/spike/: {dst_rel}")
            return 1
    print(f"code_context/spike/ snapshot present check: {len(SPIKE_CODE_SNAPSHOT_FILES)}/10 files OK")

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

    (OUT_DIR / "README.md").write_text(README_V19, encoding="utf-8")
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
    print(f"  ├─ project.7z: {sevenz_mb:.2f} MB ({file_count} files, {total_bytes/(1024*1024):.1f} MB unzipped + spike overlay + code_context)")
    print(f"  ├─ tools/7za: {(SEVENZA_SRC.stat().st_size)/(1024*1024):.2f} MB (Linux x64 ELF)")
    print(f"  ├─ README.md")
    print(f"  ├─ COMMIT_LOG.md")
    print(f"  └─ SPIKE_COMMIT_LOG.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
