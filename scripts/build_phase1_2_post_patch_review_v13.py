#!/usr/bin/env python3
"""Build phase1_2_post_patch_review_v13.zip — Phase 1.2 post-patch state snapshot.

v12 → v13 change: reflect post-patch state after GPT pro audit at cb8e347.

3 commit landed (68fa7f0 F7/F8 validator binding, a3414ee 7 oracle digest,
035bd21 audit archive + plan doc fix). audit archive 进 git 在
`docs/research/phase1_2_gpt_pro_audit_20260525/`.

Strategy 同 v12:
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
OUT_DIR = Path("/tmp/_phase1_2_pkg_v13")
PROJECT_DIR = OUT_DIR / "project"
SEVENZ_PATH = OUT_DIR / "project.7z"
OUT_ZIP = Path("/home/zhuran24/linwin_share/phase1_2_post_patch_review_v13.zip")

SEVENZA_SRC = Path("/usr/lib/7zip/7za")


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
    for pat in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel_str, pat):
            return True
    return False


README_V13 = """# 终末地工业规划器 — 项目快照

终末地 (Arknights: Endfield) 70×70 工业规划器 certified-exact 最大空矩形求解器.
目标 `max_lex(area, min_side)`. 266 mandatory facility, OR-Tools 9.15
CP-SAT, LBBD 分解 (master → binding → routing → flow). 详
`docs/项目说明/01_overview.md` + `02_mathematical_foundations.md`.

全项目内容 (src + docs + rules + data + scripts + main.py + spec + audit archive).

Build: commit `035bd21` (详 `COMMIT_LOG.md`).

## Post-patch 段

GPT pro audit at cb8e347 → 3 commit landed:

- `68fa7f0` fix(cuts): bind F7/F8 validator to candidate_placements pose registry
- `a3414ee` fix(cuts): drop stale state.source_digest fallback in 7 oracles
- `035bd21` docs: archive Phase 1.2 GPT pro audit + fix lifecycle line ref

原 5 finding 中 4 finding (1 BLOCKER + 1 BLOCKER + 1 HIGH + 1 LOW) 已修.
Finding 4 (F8 performance — `_pole_pole_edges` O(n^2) + 28s connected
large-radius test) 仍 open. Finding 5 (Mini Step 8 spike 不足以作 prod
integration close gate) 仍 open.

详 `docs/research/phase1_2_gpt_pro_audit_20260525/`:

- `AUDIT_REPORT.md` — 6 finding 全文
- `patches/0001-bind-power-family-pose-cells-and-digest.py` — 210 行 patch
  script (前 2 commit 已 land)
- `repro/` — 4 反例脚本

## 本次 build 实测数据

pytest src/tests/cuts/ (普通): 398 pass
mypy --strict --explicit-package-bases src/cuts/: 35 source 0 errors
ruff check src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py: 0 issue
vulture --min-confidence 100: 0 issue
bandit -q -r src/cuts/: 0 issue
radon cc src/cuts/ -s -a: average B (5.14), max C(15), no D
exit_criteria 脚本: 3 PASS / 8 PENDING_PHASE_1 / 0 FAIL
  (8 PENDING 是 `scripts/b_design_v2_exit_criteria.py` 检查 artifact 名
   `test_family_8_*.py` 等, 实际命名 `test_family_power_grid_reach.py` 等;
   实际 test 文件存在并 pass 在 `src/tests/cuts/`. exit_criteria 脚本本身
   待 Phase 1.3 时 update.)

## Phase 1.2 cross-check 数据

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

Mini Step 8 spike 实测 (50 BoolVar toy master, fresh build 不 incremental):

| Total cuts | Build (s) | Solve (s) | Status |
|---:|---:|---:|---|
| 100 | 0.001 | 0.002 | OPTIMAL |
| 1,000 | 0.012 | 0.000 | INFEASIBLE |
| 10,000 | 0.114 | 0.002 | INFEASIBLE |

(spike 用 `Add` / `AddLinearConstraint`, 未使用 `AddLazyConstraint` —
OR-Tools 9.15 Python `cp_model.CpModel` 不提供该 API, 详
`docs/项目说明/05_open_questions.md` Q10.)

## 解包步骤

```bash
unzip -q phase1_2_post_patch_review_v13.zip
cd _phase1_2_pkg_v13
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

# Mini Step 8 spike 复现
.venv/bin/python docs/research/p1_2b_mini_step_8_spike_20260525/spike_translator.py

# Audit reproducer (验 4 patch 已 land + 2 open finding 仍可重现)
.venv/bin/python docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_f7_facility_cells_mismatch.py
.venv/bin/python docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_f8_facility_cells_mismatch.py
.venv/bin/python docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_source_digest_quarantine.py
bash docs/research/phase1_2_gpt_pro_audit_20260525/repro/repro_f8_slow_generator.sh
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

### docs/research/p3_b_design_v2_20260521/ (framework spec + family spec + audit archive)

- `cut_lifecycle_v2.md` / `state_machine_v2.md` / `schema_update_v3.md`
- `cut_family_specs/01-09_*.md` — 9 family spec (F1-F9)
- `red_fixtures/F1-F5*.md` — 5 known-infeasibility 反例 (+ P1.2B 加 11 fixture 详 `docs/项目说明/15`)
- `paradigm_death_timeline.md` — 27 lever chronological
- `external_review/` — Phase 1.1 audit archive:
  - `phase1_1_exit_hardening_audit_report_20260523.md`
  - `phase1_1_final_delivery_20260523/`
  - `phase1_1_recheck_20260524/`
  - `phase1_1_final_polish_20260524/`
  - `gemini_math_review_action_plan_20260523.md` / `_bundle_20260523/`
  - `gpt_pro_phase1_1_v{1..6}_audit_*.md`
- `cross_check/` — `gemini_round_{14..36}*.md` Phase 1.1 + 1.2 入门级 per-commit cross-check

### docs/research/p1_2b_*/ (Phase 1.2 family-level cross-check raw)

每目录含 `prompt.txt` + `gemini_response.md` + `gemini_response_raw.json` (raw JSON +
verdict). 见上表 Family → 目录映射.

### docs/research/phase1_2_gpt_pro_audit_20260525/ (Post-patch audit archive)

- `AUDIT_REPORT.md` — 6 finding 全文
- `README.md` — 审查方法 + apply patch 步骤
- `patches/0001-bind-power-family-pose-cells-and-digest.py` — 210 行可应用脚本
- `repro/repro_f7_facility_cells_mismatch.py`
- `repro/repro_f8_facility_cells_mismatch.py`
- `repro/repro_source_digest_quarantine.py`
- `repro/repro_f8_slow_generator.sh`

### docs/research/paradigm_search_review_v12_with_code_20260520/

24 dead lever + 3 alive candidate + 6 paradigm group + shared_infra. 跨 paradigm
search 历史包.

### docs/research/literature_review_papers_20260524/

4 路 agent 调研档案 (column generation / LBBD cuts / CP-SAT internals / paradigm shift)
+ DA reviewer checkpoint2 + overlap analysis.

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
- `data/examples/industrial_planner/current_delivery/viewer/` — viewer sample
  (BSP=54, 14 outside; production 全集 outside count 不同)

### 其它

- `rules/canonical_rules.json` — 消费冻结制品
- `specs/` — schema spec
- `scripts/` — 维护脚本 + build + entry-point + readiness gate
- `PROJECT_LOCK.md` — proof source / forbidden change 锁
- `CLAUDE.md` — repo-level instruction
"""


CHANGELOG = """# Commit log

本表列出本次 review pkg 涵盖的 commit 区间 (按时间序, 由远到近). 跟 zip 内
git-less 源对应.


| Commit | Subject |
|---|---|
| 7b0c3c8 | R4 apply Phase 1.1 recheck补强 patch (188 cuts pass, fail-closed schema) |
| e32c655 | review-pkg v11 build script (Phase 1.1 R4 recheck补强, 188 pytest) |
| 4278307 | R5 apply Phase 1.1 final polish (189 cuts pass, F3 grid-bound + 命名口径统一) |
| 11f5337 | feat(F5): land Phase 1.2 P1.2B-F5 pattern_nogood family (246 cuts pass) |
| 3d93b1d | fix(F5): Gemini round 1 fix (4 findings landed) |
| ca60a35 | fix(F5): Gemini round 2 fix (4 findings + 2 LOW landed) |
| 9cd676a | fix(F5): Gemini round 3 minor fix (close F5 cross-check loop, 2 minor 直接 land 不 defer) |
| f2d8f31 | feat(F9): land Phase 1.2 P1.2B-F9 density_envelope family (278 cuts pass) |
| 515aed4 | fix(F9): Gemini round 1 fix (1 BLOCKER + 2 HIGH landed) |
| e3aa3e9 | fix(F9): Gemini round 2 fix (1 BLOCKER + 1 HIGH landed) |
| 6153ce5 | fix(F9): Gemini round 3 BLOCKER #1 fix (cert_max=0 trivial cut prune) |
| 0bed978 | fix(F9): Gemini round 4 REVERT R3 cert_max=0 patch + positive test |
| 92224c4 | feat(F2/F4): land Phase 1.2 P1.2B-F2/F4 generator + Dinic node-split helper |
| 01d368a | fix(F2/F4): Gemini round 1 fix (1 BLOCKER + 1 LOW landed) |
| d5e653d | fix(F4): Gemini round 2 LOW #3 — carry blocking_facilities cert key |
| 180400b | docs(F2/F4): Gemini round 3 close — GO_WITH_MINOR |
| ec16f06 | docs(06_current_status): sound ≠ converge 警句 |
| 6adc5fd | feat(F6): land Phase 1.2 P1.2B-F6 shape_packing_hall (initial) |
| 9fac6d6 | fix(F6): Gemini round 1 fix (1 CRITICAL + 1 HIGH + 2 MEDIUM + Gap B landed) |
| 97388a0 | fix(F6): Gemini round 2 fix (1 CRITICAL + 2 HIGH landed) |
| 64cd15f | docs(F6): Gemini round 3 close |
| c30d681 | feat(F7): land Phase 1.2 P1.2B-F7 power_hitting_set (initial single-case) |
| 9f21901 | fix(F7): Gemini round 1 cross-check fixes (1 CRITICAL landed + 3 minor verdicts) |
| e5f0e18 | docs(F7): Gemini round 2 close — LOW dead code removed, 2 finding deferred |
| 4be1b60 | feat(F8): land Phase 1.2 P1.2B-F8 power_grid_reach (initial geometric) |
| b9ab24a | fix(F8): Gemini round 1 cross-check — 3 CRITICAL + 1 HIGH |
| fe7c239 | fix(F8): Gemini round 2 cross-check — 3 of 4 findings landed, 1 rejected |
| 29b64d0 | fix(F8): Gemini round 3 cross-check — 3 finding all CRITICAL/HIGH landed |
| 3b9c8b3 | fix(F8): Gemini round 4 cross-check — 4 finding all landed (2 CRITICAL + 2 HIGH) |
| 4721c04 | docs(F8): Gemini round 5 close — GO verdict |
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
"""


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

    (PROJECT_DIR / "README.md").write_text(README_V13, encoding="utf-8")
    (PROJECT_DIR / "COMMIT_LOG.md").write_text(CHANGELOG, encoding="utf-8")
    file_count += 2

    print(f"Project copy: {file_count} files / {total_bytes/(1024*1024):.1f} MB unzipped")
    print(f"Skipped: {skipped} files")

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

    (OUT_DIR / "README.md").write_text(README_V13, encoding="utf-8")
    (OUT_DIR / "COMMIT_LOG.md").write_text(CHANGELOG, encoding="utf-8")

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
    print(f"  ├─ project.7z: {sevenz_mb:.2f} MB ({file_count} files, {total_bytes/(1024*1024):.1f} MB unzipped)")
    print(f"  ├─ tools/7za: {(SEVENZA_SRC.stat().st_size)/(1024*1024):.2f} MB (Linux x64 ELF)")
    print(f"  ├─ README.md")
    print(f"  └─ COMMIT_LOG.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
