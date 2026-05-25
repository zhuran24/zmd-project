#!/usr/bin/env python3
"""Build phase1_2_close_review_v12.zip — Phase 1.2 ALL CLOSED 大节点 GPT pro review.

v11 → v12 关键差异 (反映 Phase 1.2 全部 family land + close gate spike):

- Phase 1.1 → Phase 1.2 状态切换: 7 family (F2/F4/F5/F6/F7/F8/F9) 全 Gemini
  cross-check GO + mini Step 8 spike GO (CP-SAT translator close gate).
- 测试 188 → 395 cuts pass (+207 新 family/regression).
- mypy --strict src 数量 22 → 35 source 0 errors.
- radon Average A(4.26) → B(5.07) (新 family validator/oracle/evaluator,
  仍 no D, 在 acceptable 范围).
- 累计 20 round Gemini per-commit cross-check + 14 finding 全 land (F8 最严
  4 round 12 finding).

跟 v8/v9/v10/v11 一样的 strategy:
- 全项目 root copy + 7z -mx=9 + zip 壳 + ship 7za binary (per [[review-pkg-7z-strategy]])
- 排除 .venv / .git / .artifacts / .codex_test_logs / .upstream_clones / .claude / _codex_archive
- 不放 prompt / 主动性内容 (per [[review-pkg-no-prompt-inside]]) — prompt 通过
  chat message 单独给 (per [[feedback_big_milestone_gpt_pro_review]])
"""
from __future__ import annotations

import fnmatch
import shutil
import subprocess
from pathlib import Path

REPO = Path("/home/zhuran24/claude-pj/zmd")
OUT_DIR = Path("/tmp/_phase1_2_pkg_v12")
PROJECT_DIR = OUT_DIR / "project"
SEVENZ_PATH = OUT_DIR / "project.7z"
OUT_ZIP = Path("/home/zhuran24/linwin_share/phase1_2_close_review_v12.zip")

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


README_V12 = """# Phase 1.2 Close Review (v12) — Phase 1.2 ALL CLOSED 大节点交付

终末地 (Arknights: Endfield) 70×70 工业规划器 certified exact solver. 全项目
content (src + docs + rules + data + scripts + main.py + spec + audit archive).

## 当前状态: Phase 1.2 ALL CLOSED ✅

**7 个 cut family 全 Gemini cross-check GO + mini Step 8 spike GO**:

| Family | Round | finding | verdict | Last commit |
|---|---|---|---|---|
| F5 pattern_nogood | 3 round | 10 finding (4+4+2) | GO (R3 minor 直接 land 不 defer) | `9cd676a` |
| F9 density_envelope | **4 round** | 3+2+1+revert | GO (paradigm defer 1.5+) | `0bed978` |
| F2/F4 cutset+component_reach | 3 round | 3 finding (2+1+0) | GO_WITH_MINOR | `180400b` |
| F6 shape_packing_hall | 3 round | 7 finding (4+3+0) | GO | `64cd15f` |
| F7 power_hitting_set | 2 round | 5 finding (4+1) | GO (2 defer 1.5+) | `e5f0e18` |
| **F8 power_grid_reach** | **5 round** | **14 finding (4+3+3+4+0) 全 land** | GO (R5 reviewer "极高质量") | `4721c04` |
| Mini Step 8 spike (close gate) | 1 round 内审 | — | GO (6 family CP-SAT translate, 10K cuts build 114ms) | `3f1c581` |

**累计**: 20 round Gemini per-commit cross-check + ~37 finding (绝大多数直接 land,
极少数明确 defer Phase 1.5+ 接真 adapter 时一并修).

### Phase 1.2 close quality gate (build 时实测)

| 指标 | 状态 |
|---|---|
| pytest src/tests/cuts/ | **395 pass** (普通模式 + `python -O`) |
| mypy --strict src count | **35 source 0 errors** |
| ruff | clean |
| bandit | 0 issues |
| vulture (--min-confidence 100) | pass |
| radon avg | **B (5.07)** (7 family validator 加入后, 最高 C(15), no D) |
| exit_criteria | 3 PASS / 8 PENDING_PHASE_1 / 0 FAIL |

注: exit_criteria 的 8 PENDING 是 `scripts/b_design_v2_exit_criteria.py` 检
查脚本 artifact 名跟实际 test 文件名 mismatch (脚本找 `test_family_8_*.py`,
实际叫 `test_family_power_grid_reach.py` 等). F8/F9/cut_store rotation 等
测试都在 `src/tests/cuts/` 实际存在且 pass, 不是真 PENDING. 待 P1.3 时
更新 exit_criteria 脚本.

### mini Step 8 spike (close gate) 数据

`docs/research/p1_2b_mini_step_8_spike_20260525/verdict.md`:

- 5 distinct CP-SAT constraint form covers 6 family (linear area / multiset
  nogood / edge-cut / region Hall / per-pose forbid)
- **不需要 `AddLazyConstraint`** (OR-Tools 9.15 Python `cp_model.CpModel` 不
  提供该 API, 详 `docs/项目说明/05_open_questions.md` Q10)
- Toy master 10 groups × 5 poses = 50 BoolVar, fresh build 不 incremental:
  - 100 cuts: 1ms build + 2ms solve
  - 1K cuts: 12ms build + 0ms solve (INFEASIBLE)
  - **10K cuts: 114ms build + 2ms solve** (~11.4µs/cut, 距 30s/iter GO 阈值 ~250x headroom)
- Prod-scale 估: 50× toy = ~5-6s build on 10K cuts, 仍 < 30s/iter master budget
  even before P1.3 active cut filter optimization.

### 进入 Phase 1.3 P1.3A spike

Mini Step 8 spike 是 close gate; 真 master integration (266 instance × ~280K
pose registry) 是 Phase 1.3 P1.3A spike 范围, plan 在 `docs/项目说明/09_phase_1_3_plan.md`.

## 解包步骤

```bash
unzip -q phase1_2_close_review_v12.zip
cd _phase1_2_pkg_v12
chmod +x tools/7za && ./tools/7za x project.7z
cd project
```

## 怎么跑 (cd project/)

依赖 `zmd_deps_v3.zip` 单独上传.

```bash
python3.10+ -m venv .venv && source .venv/bin/activate
unzip -q ../zmd_deps_v3.zip -d /tmp/deps
pip install --find-links /tmp/deps -r requirements.txt

# Cut framework 单元测试 (应 395 pass)
.venv/bin/python -m pytest src/tests/cuts/ -q
.venv/bin/python -O -m pytest src/tests/cuts/ -q

# 静态工具
.venv/bin/python -m ruff check src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py
.venv/bin/python -m mypy --strict --explicit-package-bases src/cuts/
.venv/bin/python -m vulture src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py --min-confidence 100
.venv/bin/python -m bandit -q -r src/cuts/
.venv/bin/python -m radon cc src/cuts/ -s -a

# Exit criteria
.venv/bin/python scripts/b_design_v2_exit_criteria.py

# Mini Step 8 spike (close gate) 复现
.venv/bin/python docs/research/p1_2b_mini_step_8_spike_20260525/spike_translator.py
```

## 文档地图 (project/ 解包后)

### 项目说明 SoT (docs/项目说明/, 项目顶层)

21 sub-doc + README 总索引. 是项目说明 SoT (paradigm + 数学 + plan + workflow + 术语).

- `README.md` — 总索引 + 受众分流 + 21 sub-doc 文档地图
- `01_overview.md` — 战略 + 数学问题陈述 + paradigm 选择
- `02_mathematical_foundations.md` — 9 family + sound deduction + scope/replay/multiset/adversarial
- `03_paradigm_death_baseline.md` — 27 lever 死路按数学根据分类
- `04_design_invariants.md` — PROJECT_LOCK §3A 镜像 (F8 mode 锁 / F9 area-only)
- `05_open_questions.md` — 33 + 6 Q (Q10 CP-SAT AddLazyConstraint verdict, mini Step 8 spike 验证)
- `06_current_status.md` — Phase 1.1 GO blessed + Phase 1.2 in-progress note
  (build 时该 doc 滞后于实际 P1.2 close 进度, 本 README 数字以 build 实测为准)
- `07_historical_review.md` — 含 §5.12 exit hardening + §5.13 Gemini math review
- `08_phase_1_2_plan.md` — P1.2A done + P1.2B-F5/F6/F7/F8/F9 详
- `09_phase_1_3_plan.md` — P1.3A CP-SAT attach spike (3 sub-route PoC)
- `10_phase_1_5_plan.md` — Production integration + F5/F7 defer items
- `11_dependency_graph.md` / `12_go_criteria.md` (含 §8.1.x Phase 1.2 P0 acceptance) / `13_schedule_estimate.md`
- `14_risk_rollout.md` / `15_workflow_testing.md` (含 §21.7 11 red fixture matrix)
- `16_workflow_review.md` / `17_workflow_telemetry.md` (含 dark matter telemetry + 报警阈值)
- `18_workflow_env_config.md` / `19_implementation_rhythm.md` / `20_skip_directions.md` / `21_glossary.md`

### B Design v2 framework spec (docs/research/p3_b_design_v2_20260521/)

framework spec SoT — cut object schema / lifecycle 9 step / validator contract.

- `cut_lifecycle_v2.md` / `state_machine_v2.md` / `schema_update_v3.md`
- `cut_family_specs/01-09_*.md` (9 family detailed spec)
- `red_fixtures/F1-F5*.md` (5 known-infeasibility 反例, P1.2B 加 11 fixture 详 docs/项目说明/15)
- `paradigm_death_timeline.md` (27 lever chronological)

### Audit archive (docs/research/, 本次 Phase 1.2 全 7 family cross-check)

含每 family 每 round 完整 prompt + raw response + verdict:

- `p1_2b_f5_pattern_nogood_gemini_round{1,2,3}_*` + `gemini_cross_check_phase1_2_f5_round3_20260524/`
- `p1_2b_f9_density_envelope_gemini_round{1,2,3}_20260524/` (F9 4 round, R4 在 commit `0bed978`)
- `p1_2b_f2_f4_gemini_round{1,2,3}_20260524/` (F2/F4 generator + Dinic node-split)
- `p1_2b_f6_shape_packing_hall_gemini_round{1,2,3}_20260525/` (F6 Hall theorem)
- `p1_2b_f7_power_hitting_set_gemini_round{1,2}_20260525/` (F7 power hitting set)
- `p1_2b_f8_power_grid_reach_gemini_round{1,2,3,4,5}_20260525/` (F8 5 round 12 finding)
- `p1_2b_mini_step_8_spike_20260525/` (close gate: spike_translator.py + verdict.md)

Phase 1.1 GO blessed (history) audit:

- `p3_b_design_v2_20260521/external_review/`:
  - `phase1_1_exit_hardening_audit_report_20260523.md` — R1 Phase 1.1 GO verdict (8 项 fix)
  - `phase1_1_final_delivery_20260523/` — R3 final delivery
  - `phase1_1_recheck_20260524/` — R4 recheck补强
  - `phase1_1_final_polish_20260524/` — R5 final polish (189 pass)
  - `gemini_math_review_action_plan_20260523.md` / `_bundle_20260523/`
  - `gpt_pro_phase1_1_v{1..6}_audit_*.md` (Phase 1.1 历次 audit 全档, 含 verdict 演进)

Paradigm v12 search archive (跨 24 lever dead history):

- `paradigm_search_review_v12_with_code_20260520/` — 24 dead lever + 3 alive
  candidate + 6 paradigm group + shared_infra. v12 GPT pro review 包.

### Cross-check archive (cross_check/)

- `gemini_round_{14..35}*.md` + `gemini_round_36_f5_round2_*` (23+ Gemini per-commit
  cross-check, Phase 1.1 + 1.2 入门级)

### 主流程 src/

```
main.py                              # Campaign entry
src/cuts/                            # B Design v2 cut framework (本次 audit 主对象)
├── lifecycle.py (9 step + validate_cut_integrity)
├── store.py / replay.py
├── families/{region_capacity,cutset,port_exposure,component_reach,
│              pattern_nogood,shape_packing_hall,power_hitting_set,
│              power_grid_reach,density_envelope}.py (F1-F9 全 ready)
├── oracles/ (F2/F3/F4/F5/F6/F7/F8/F9 oracle protocol + stub/real)
├── helpers/ (bounded_core_minimizer, baseline_partition, etc.)
├── assumptions/
src/search/ (outer search + benders loop) / src/models/ (master + binding + routing + flow)
src/tests/cuts/ (395 cuts test)
```

### Data 真集 (data/preprocessed/)

`candidate_placements.json` 53 MB production 全集 (81795 pose / 134 BSP).
Audit archive cite 反例 (BSP=54, 14 outside) 来自 viewer sample
(`data/examples/industrial_planner/current_delivery/viewer/`), production 全集
outside count 不同.

## 已知 trade-off 与 defer 项 (供 reviewer 参考)

以下是 Phase 1.2 close 期间团队**已识别但选择 defer / accept** 的设计取舍.
列出供 reviewer 自由判断是否要 push back; 完整 verdict + reproducer 在
对应 audit archive 里.

- **F9 R3→R4 反转**: R3 验证认为 "cert_max < safe_ub 是 trivially unsound",
  R4 反转: cert_max=0 在 W 被 static obstacle 完全覆盖时是合法 exclusion-zone
  cut. 团队接受 "validator 不能 NP-hard 验 oracle K", Phase 1.5+ 真 adapter
  时一并验证. 详 `docs/research/p1_2b_f9_density_envelope_gemini_round{1,2,3}_20260524/` +
  commit `0bed978`.
- **F5/F9 oracle trust 同 paradigm**: 两 family 都 defer "validator 重算
  verify oracle 的 NP-hard claim" 到 Phase 1.5+. P1.2 close gate 通过
  `docs/项目说明/06_current_status.md §6` "sound ≠ converge" 警句 cover.
- **mini Step 8 spike scale 外推**: 50 BoolVar toy 估 prod-scale rebuild
  ~5-6s on 10K cuts (~50× toy). 真 prod 266 instance × ~280K pose registry
  measure 是 Phase 1.3 P1.3A spike 范围, 当前未实测.
- **F8 5 round vs F2/F4 3 round**: F8 (global connectivity) 5 round 12
  finding, F2/F4 (cutset + component_reach) 3 round 0 new finding. 团队
  解读是 F2/F4 paradigm 真简单, 但 audit depth 是否相称留 reviewer 判断.
  详 commit `4721c04` (F8 R5) + `180400b` (F2/F4 R3).
- **F6 shape_packing_hall**: cut form
  `sum(x[g,p] for region_pose_set) <= region_capacity`. Multiset slot
  semantics 当前 collapse via Counter (Phase 1.5+ slot-indexed 改 schema 时
  revisit). 详 `cut_family_specs/06_shape_packing_hall.md`.
- **dark matter telemetry** (unexplained infeasible jsonl): 设计 land 但
  P1.3A ramp 才 trigger. 详 `docs/项目说明/17_workflow_telemetry.md`.

主战场源代码: `src/cuts/families/` (9 family) + `src/cuts/oracles/` +
`src/cuts/lifecycle.py`. P0 acceptance criteria 在
`docs/项目说明/12_go_criteria.md §8.1.x`. Red fixture matrix 在
`docs/项目说明/15_workflow_testing.md §21.7`.

## 本次 build state

Commit `cb8e347`, 395 cuts pass. 详 `COMMIT_LOG.md` 列出 Phase 1.1 close 到
本次 build 区间所有 commit (按时间序), 跟 zip 内 `.git`-less 源对应.
"""


CHANGELOG = """# Commit log (Phase 1.1 close → Phase 1.2 ALL CLOSED)

本表列出本次 review pkg 涵盖的 commit 区间 (按时间序), 跟 zip 内
git-less 源对应. 标黑体为 milestone commit.


| Commit | Subject |
|---|---|
| 7b0c3c8 | R4 apply Phase 1.1 recheck补强 patch (188 cuts pass, fail-closed schema) |
| e32c655 | review-pkg v11 build script (Phase 1.1 R4 recheck补强, 188 pytest) |
| **4278307** | **R5 apply Phase 1.1 final polish (189 cuts pass, F3 grid-bound + 命名口径统一)** — Phase 1.1 GO blessed final, 188 → 189 |
| **11f5337** | **feat(F5): land Phase 1.2 P1.2B-F5 pattern_nogood family (246 cuts pass)** |
| 3d93b1d | fix(F5): Gemini round 1 fix (4 findings landed) |
| ca60a35 | fix(F5): Gemini round 2 fix (4 findings + 2 LOW landed) |
| 9cd676a | fix(F5): Gemini round 3 minor fix (close F5 cross-check loop, 2 minor 直接 land 不 defer) |
| **f2d8f31** | **feat(F9): land Phase 1.2 P1.2B-F9 density_envelope family (278 cuts pass)** |
| 515aed4 | fix(F9): Gemini round 1 fix (1 BLOCKER + 2 HIGH landed) |
| e3aa3e9 | fix(F9): Gemini round 2 fix (1 BLOCKER + 1 HIGH landed) |
| 6153ce5 | fix(F9): Gemini round 3 BLOCKER #1 fix (cert_max=0 trivial cut prune) |
| **0bed978** | **fix(F9): Gemini round 4 REVERT R3 cert_max=0 patch + positive test** — R3 was WRONG, cert_max=0 实为合法 exclusion-zone cut, paradigm 接受 Phase 1.5+ defer |
| **92224c4** | **feat(F2/F4): land Phase 1.2 P1.2B-F2/F4 generator + Dinic node-split helper** |
| 01d368a | fix(F2/F4): Gemini round 1 fix (1 BLOCKER + 1 LOW landed) |
| d5e653d | fix(F4): Gemini round 2 LOW #3 — carry blocking_facilities cert key |
| 180400b | docs(F2/F4): Gemini round 3 close — GO_WITH_MINOR |
| **ec16f06** | **docs(06_current_status): sound ≠ converge 警句 (GPT pro P1.2 in-progress review)** |
| **6adc5fd** | **feat(F6): land Phase 1.2 P1.2B-F6 shape_packing_hall (initial)** |
| 9fac6d6 | fix(F6): Gemini round 1 fix (1 CRITICAL + 1 HIGH + 2 MEDIUM + Gap B landed) |
| 97388a0 | fix(F6): Gemini round 2 fix (1 CRITICAL + 2 HIGH landed) |
| 64cd15f | docs(F6): Gemini round 3 close — Phase 1.2 GO (剩 Phase 1.5+ defer) |
| **c30d681** | **feat(F7): land Phase 1.2 P1.2B-F7 power_hitting_set (initial single-case)** |
| 9f21901 | fix(F7): Gemini round 1 cross-check fixes (1 CRITICAL landed + 3 minor verdicts) |
| e5f0e18 | docs(F7): Gemini round 2 close — LOW dead code removed, 2 finding deferred |
| **4be1b60** | **feat(F8): land Phase 1.2 P1.2B-F8 power_grid_reach (initial geometric)** |
| b9ab24a | fix(F8): Gemini round 1 cross-check — 3 CRITICAL + 1 HIGH |
| fe7c239 | fix(F8): Gemini round 2 cross-check — 3 of 4 findings landed, 1 rejected |
| 29b64d0 | fix(F8): Gemini round 3 cross-check — 3 finding all CRITICAL/HIGH landed |
| 3b9c8b3 | fix(F8): Gemini round 4 cross-check — 4 finding all landed (2 CRITICAL + 2 HIGH) |
| **4721c04** | **docs(F8): Gemini round 5 close — GO verdict, Phase 1.2 F8 complete (5 round 12 finding)** |
| **3f1c581** | **feat(P1.2): mini Step 8 spike — 6 family CP-SAT translator + 10K cost = GO** (Phase 1.2 close gate, per GPT pro P1.2 in-progress review #6) |
| 5b49f04 | docs(F5/F9): archive Gemini cross-check round raw transcripts (补漏归档) |
| 9127c60 | docs(research): archive paradigm v12 review + literature review packages |
| 983ee65 | docs(research): backfill real-measure data for cand_c/smt_mt/sac_hull trials |
| **cb8e347** | **chore(F7 test): rename unused _kwargs param to clear vulture warning** (v12 build state) |
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

    (PROJECT_DIR / "README.md").write_text(README_V12, encoding="utf-8")
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

    (OUT_DIR / "README.md").write_text(README_V12, encoding="utf-8")
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
