#!/usr/bin/env python3
"""Build phase1_2_entry_review_v9.zip — Phase 1.1 GO blessed + Phase 1.2 entry ready.

v8 → v9 关键差异 (反映 Phase 1.1 exit hardening 落地 + Gemini math review meta-audit):
- 178 cuts pytest pass (v8 时 172)
- mypy strict 全清 (v8 时 37 errors)
- radon A 无 D (v8 时 D(27/24/23))
- docs/项目说明/ 整 dir 21 sub-doc 新加 (项目顶层重组, 从原 plan + math doc 拆)
- external_review/ 加 exit hardening deliverable + Gemini math review bundle
- Phase 编号 P1.11 → P1.2A/P1.2B 修正
- F8 mode 锁 geometric / F9 area-only / CP-SAT no AddLazyConstraint verdict

跟 v8 一样的 strategy:
- 全项目 root copy + 7z -mx=9 + zip 壳 + ship 7za binary (per [[review-pkg-7z-strategy]])
- 排除 .venv / .git / .artifacts / .codex_test_logs / .upstream_clones / .claude / _codex_archive
- 不放 prompt / 主动性内容 (per [[review-pkg-no-prompt-inside]])
"""
from __future__ import annotations

import fnmatch
import shutil
import subprocess
from pathlib import Path

REPO = Path("/home/zhuran24/claude-pj/zmd")
OUT_DIR = Path("/tmp/_phase1_2_pkg_v9")
PROJECT_DIR = OUT_DIR / "project"
SEVENZ_PATH = OUT_DIR / "project.7z"
OUT_ZIP = Path("/home/zhuran24/linwin_share/phase1_2_entry_review_v9.zip")

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


README_V9 = """# Phase 1.2 Entry Review (v9) — Phase 1.1 GO blessed

终末地 (Arknights: Endfield) 70×70 工业规划器 certified exact solver. 全项目
content (src + docs + rules + data + scripts + main.py + spec + audit archive).

## 当前状态

**Phase 1.1: GO blessed** (commit `9e01a6e` Phase 1.1 exit hardening +
`ecc96c7` docs/项目说明/ v1.1)

- 178 cuts pytest pass (`python` 普通 + `python -O`)
- mypy --strict --explicit-package-bases src/cuts/: 0 errors
- ruff: clean (default + no per-file-ignores)
- bandit: 0 issues
- radon: average A, no D (max C(15))
- vulture: pass (scripts/vulture_cuts_whitelist.py)

**进入 Phase 1.2**: P1.2A entry hardening ✅ done (8 项 fix). 待 P1.2B-F5/F6/
F7/F8/F9 实施 (按顺序: F5 fallback 优先 → F9 主力 lift → F2/F4 generator →
F6 → F7 → F8).

详 `docs/项目说明/README.md` 总索引 + 受众分流 + 文档地图.

## 解包步骤

```bash
unzip -q phase1_2_entry_review_v9.zip
cd _phase1_2_pkg_v9
chmod +x tools/7za && ./tools/7za x project.7z
cd project
```

## 怎么跑 (cd project/)

依赖 `zmd_deps_v3.zip` 单独上传 (跟 v8 一致).

```bash
python3.10+ -m venv .venv && source .venv/bin/activate
unzip -q ../zmd_deps_v3.zip -d /tmp/deps
pip install --find-links /tmp/deps -r requirements.txt

# Cut framework 单元测试 (应 178 pass)
.venv/bin/python -m pytest src/tests/cuts/ -q
.venv/bin/python -O -m pytest src/tests/cuts/ -q

# 静态工具
.venv/bin/python -m ruff check src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py
.venv/bin/python -m mypy --strict --explicit-package-bases src/cuts/
.venv/bin/python -m vulture src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py
.venv/bin/python -m bandit -r src/cuts/
.venv/bin/python -m radon cc src/cuts/ -s -a
```

## 文档地图 (project/ 解包后)

### 项目说明 SoT (docs/项目说明/, 项目顶层)

21 sub-doc + README 总索引. 是项目说明 SoT (paradigm + 数学 + plan + workflow + 术语).

- `README.md` — 总索引 + 受众分流 + 21 sub-doc 文档地图
- `01_overview.md` — 战略 + 数学问题陈述 + paradigm 选择
- `02_mathematical_foundations.md` — 9 family + sound deduction + scope/replay/multiset/adversarial
- `03_paradigm_death_baseline.md` — 27 lever 死路按数学根据分类
- `04_design_invariants.md` — PROJECT_LOCK §3A 镜像 (F8 mode / F9 area-only)
- `05_open_questions.md` — 33 + 6 Q (Q10 CP-SAT AddLazyConstraint verdict)
- `06_current_status.md` — Phase 1.1 GO blessed, 178 pytest, exit hardening 8 项 fix
- `07_historical_review.md` — 含 §5.12 exit hardening + §5.13 Gemini math review
- `08_phase_1_2_plan.md` — P1.2A done + P1.2B-F5/F6/F7/F8/F9 详
- `09_phase_1_3_plan.md` — P1.3A CP-SAT attach spike (3 sub-route PoC)
- `10_phase_1_5_plan.md` — Production integration
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

### Audit archive (external_review/)

含本次 review 的 deliverable + 历史:

- `phase1_1_exit_hardening_audit_report_20260523.md` — Phase 1.1 GO verdict
- `phase1_1_exit_hardening_plan_v2_20260523.md` — 原 deliverable plan v2 (内容已 merge 进 docs/项目说明/)
- `gemini_math_review_action_plan_20260523.md` — Gemini math review meta-audit (3 critical 降温修正 + 5 P0)
- `gemini_math_review_bundle_20260523/` — checklist + 11 red fixture matrix + CP-SAT notes + F9 morphology caution
- `gpt_pro_phase1_1_v{1..6}_audit_*.md` (11 round v1-v6 audit history, 全 NOT GO → 现 GO)

### Cross-check archive (cross_check/)

- `gemini_round_{14..35}*.md` (22 Gemini per-commit cross-check)

### 主流程 src/

```
main.py                              # Campaign entry
src/cuts/                            # B Design v2 cut framework (本次 audit 主对象)
├── lifecycle.py (9 step)
├── store.py / replay.py
├── families/{region_capacity,cutset,port_exposure,component_reach}.py (F1-F4 ready)
├── oracles/ / helpers/ / assumptions/
src/search/ (outer search + benders loop) / src/models/ (master + binding + routing + flow)
src/tests/cuts/ (178 cuts test)
```

### Data 真集 (data/preprocessed/)

`candidate_placements.json` 53 MB production 全集 (81795 pose / 134 BSP).
Audit archive cite 反例 (BSP=54, 14 outside) 来自 viewer sample
(`data/examples/industrial_planner/current_delivery/viewer/`), production 全集
outside count 不同.

## 给 reviewer 的 audit 重点

主战场 (Phase 1.2 P0 acceptance, per Gemini math review):

1. **F5 bounded core minimizer** 合同 (last verified core, not unverified partial)
2. **F9 area-only invariant** (拒 routing/binding/pcr_cut overflow witness)
3. **CP-SAT 不依赖 `AddLazyConstraint`** (OR-Tools 9.15 不支持)
4. **F2/F4 generator 实施** (BFS 容量 0 是 F4 特例, F2 min-cut 主战场)
5. **dark matter telemetry** (unexplained infeasible jsonl)

详 `docs/项目说明/12_go_criteria.md §8.1.x` + `docs/项目说明/15_workflow_testing.md §21.7`.

## v8 → v9 diff summary

- v8 commit `744305d`: Phase 1.1 v6 audit 后 + plan/math doc 状态 (172 pytest)
- v9 commit `ecc96c7`: Phase 1.1 GO blessed + docs/项目说明/ v1.1 (178 pytest)

Commit chain (v8 → v9):
- `af83885` plan doc 高中 7 项 + math doc 新增
- `290bd32` plan §3/§4 收缩 cite math (SoT 政策)
- `b72bc22` 拆 21 sub-doc → docs/项目说明/
- `9e01a6e` Phase 1.1 exit hardening patch (178 pytest)
- `ecc96c7` docs/项目说明/ v1.1 (merge exit hardening v2 + Gemini math review)
"""


CHANGELOG = """# Commit log (Phase 1.1 → Phase 1.2 entry, v6 audit → v9 build)

| Commit | Subject |
|---|---|
| 3d35a62 | A: validator schema assert → fail-closed (`python -O` 防线) |
| 45c44d2 | B: F3 cert ↔ literal multiset 绑定 |
| eaed85c | C: F2 partition cells ⊆ free + patch enclosure + cut_edges 集合验 |
| 5c06dff | D: F4 cert.src/sink_component == BFS + commodity_id schema_err |
| 8a38401 | E: F1 strict P(g)⊆R check |
| e0ec660 | F: F1 evaluate 重算 cap_R + F4 separator_cells |
| 3553efb | G: lru_cache(256) + F4 commodity_id spec align |
| e5c41b9 | H: Phase 1.3 P1.21 TODO docstring + archive |
| bdaa303 | I/J/K: step_7 family dispatch + F3 slot binding + F4 separator in-grid + F2 evaluator enclosure |
| a38620c | L: F1 contributing_groups 去重 + tuple demand + gap consistency |
| 273fbff | M: replay canonical_rules=None HOLD; F2/F4 commodity registry require |
| afef8f1 | N: F2 contributing 去重 + cross-partition; CutStore.add_cut default held |
| c8fb7ef | O: F1 GHOST_AGNOSTIC ghost∩R=∅; F2/F4 reject GHOST_AGNOSTIC; on_ghost_rect_changed full replay gate |
| 46561c2 | plan rewrite + 6 段战略层 |
| d86d473 | plan §3 加 13 数学原理 subsection |
| af83885 | plan 补高中 7 项 gap + 新增 math doc |
| 290bd32 | plan §3 + §4 收缩为 overview cite math (SoT 政策) |
| b72bc22 | 拆 plan + math 为 docs/项目说明/ 21 sub-doc + 旧 file 改 redirect stub |
| **9e01a6e** | **apply Phase 1.1 exit hardening patch (Phase 1.1 GO blessed)** — 178 pytest, mypy strict pass, radon A 无 D, 8 项 fix (strict gate ON / source_digest 真 hash / radon helper 拆 / F3 删 unused / ghost_rect lock / unsafe stub flag / mypy 清零 / spec drift) |
| **ecc96c7** | **docs/项目说明/ v1.1 — merge exit hardening v2 plan + Gemini math review meta-audit** — 11 sub-doc update (F9 area-only / F8 mode 锁 / CP-SAT no AddLazyConstraint Q10 verdict / Phase 1.2 P0 acceptance / 11 red fixture / dark matter telemetry) |
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

    (PROJECT_DIR / "README.md").write_text(README_V9, encoding="utf-8")
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

    (OUT_DIR / "README.md").write_text(README_V9, encoding="utf-8")
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
