#!/usr/bin/env python3
"""Build phase1_2_entry_review_v11.zip — Phase 1.1 R4 recheck补强落地 (4 轮 deliverable 全 land).

v10 → v11 关键差异 (反映 R4 recheck补强, commit `7b0c3c8`):
- 188 cuts pytest pass (v10 时 181, +7 regression for base64/bitset/Cut schema/F1-F4 bool numeric)
- base64 改 strict decode (validate=True), 拒 junk char payload
- region bitset 加 grid 外高位 0 check (byte length=(70*70+7)//8 + 高位 0)
- Cut.scope / Cut.cert 强制真 CutScope/OracleCert 对象 (非只验 hasattr)
- Python bool 是 int 子类陷阱: F1-F4 所有 numeric 字段加 _parse_strict_int
  (cap_R/demand_R/gap/cells_per_pose/cut_size/commodity_demand/blocking_slot/cell 坐标)
- malformed cert evaluator fail-closed: F2/F4 evaluator try-except 返 False, 不抛异常
- 文档对齐 181 → 188 + docs/research/.../external_review/ 路径
- Cut.__post_init__ 拆 10 个 helper 保 radon A
- radon Average A (4.260869565217392) — 与 reviewer log byte-equal

v9 → v10 关键差异 (R3 final delivery, commit `db8d9cd`):
- 181 cuts pytest pass (v9 时 178, +3 regression for cut integrity / watcher copy / schema strict)
- validate_cut_integrity() 新加 (cert_payload hash + oracle_cert_hash + geo↔cert payload 一致)
- BState.source_digest 不信外部值, replay 按当前 source 重算
- CutStore 状态机补洞 / watcher 查询返副本
- F2 cutset free_cells 排除 exterior_blocks
- F1/F2 payload 解析加严 (R3 layer 1; R4 又加 strict 模式 + 高位 + bool!=int 三层)

v8 → v9 关键差异 (Phase 1.1 exit hardening + Gemini math review meta-audit, 见 archive):
- 178 cuts pytest pass / mypy strict 清零 / radon A 无 D / docs/项目说明/ 21 sub-doc / F8/F9 invariant

跟 v8/v9/v10 一样的 strategy:
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
OUT_DIR = Path("/tmp/_phase1_2_pkg_v11")
PROJECT_DIR = OUT_DIR / "project"
SEVENZ_PATH = OUT_DIR / "project.7z"
OUT_ZIP = Path("/home/zhuran24/linwin_share/phase1_2_entry_review_v11.zip")

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


README_V11 = """# Phase 1.2 Entry Review (v11) — Phase 1.1 R4 recheck补强落地

终末地 (Arknights: Endfield) 70×70 工业规划器 certified exact solver. 全项目
content (src + docs + rules + data + scripts + main.py + spec + audit archive).

## 当前状态

**Phase 1.1: GO blessed** (4 轮外部 deliverable 全 land):
- R1 exit hardening (`9e01a6e`) — 8 项入门 fix
- R2 docs/项目说明/ v1.1 (`ecc96c7`) — merge v2 plan + Gemini math review meta-audit
- R3 final delivery (`db8d9cd`) — 10 项 adversarial soundness 升级 (validate_cut_integrity / source_digest 不信外部值 / CutStore 状态机补洞 / watcher 返副本 / F2 free_cells 排除 exterior / F1/F2 payload 加严 / Cut runtime schema 加严 / optional HiGHS+SCIP skip)
- **R4 recheck补强 (`7b0c3c8`) — 6 类 schema fail-closed 边界**:
  - base64 改 strict decode (`validate=True`), 拒 junk char payload
  - region bitset 加 grid 外高位 0 check (`(70*70+7)//8` byte length + 高位置 1 拒绝)
  - `Cut.scope` / `Cut.cert` 强制真 `CutScope`/`OracleCert` 对象 (非只验 hasattr)
  - **Python `bool` 是 `int` 子类陷阱**: F1-F4 所有 numeric 字段加 `_parse_strict_int` (cap_R/demand_R/gap/cells_per_pose/cut_size/commodity_demand/blocking_slot/cell 坐标)
  - malformed cert evaluator fail-closed: F2/F4 evaluator try-except 返 False
  - 文档对齐 (181 → 188)
  - `Cut.__post_init__` 拆 10 个 helper 保 radon A

验收:
- **188 cuts pytest pass** (`python` 普通 + `python -O`, v10 时 181)
- mypy --strict --explicit-package-bases src/cuts/: 22 source 0 errors
- ruff: clean
- bandit: 0 issues
- radon: Average A (**4.260869565217392**), max C(15) — 与 reviewer log byte-equal
- vulture: pass
- exit_criteria: **3 PASS / 8 PENDING_PHASE_1 / 0 FAIL** (PENDING 是 F7/F8/F9 测试未建 + 80/160-inst ramp report 没跑 + cut_store rotation 测试未建, 全是 Phase 1.2/168h ramp 要做的事)

**进入 Phase 1.2**: P1.2A entry hardening ✅ done (4 轮 deliverable). 待 P1.2B-F5/F6/F7/F8/F9 实施 (按顺序: F5 fallback 优先 → F9 主力 lift → F2/F4 generator → F6 → F7 → F8).

详 `docs/项目说明/README.md` 总索引 + 受众分流 + 文档地图.

## 解包步骤

```bash
unzip -q phase1_2_entry_review_v11.zip
cd _phase1_2_pkg_v11
chmod +x tools/7za && ./tools/7za x project.7z
cd project
```

## 怎么跑 (cd project/)

依赖 `zmd_deps_v3.zip` 单独上传 (跟 v8 一致).

```bash
python3.10+ -m venv .venv && source .venv/bin/activate
unzip -q ../zmd_deps_v3.zip -d /tmp/deps
pip install --find-links /tmp/deps -r requirements.txt

# Cut framework 单元测试 (应 188 pass)
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
- `06_current_status.md` — Phase 1.1 GO blessed, 188 pytest, 4 轮 deliverable 全 land
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

### Audit archive (docs/research/p3_b_design_v2_20260521/external_review/)

含本次 review 的 deliverable + 历史:

- `phase1_1_exit_hardening_audit_report_20260523.md` — R1 Phase 1.1 GO verdict (8 项 fix)
- `phase1_1_exit_hardening_plan_v2_20260523.md` — R1 原 deliverable plan v2 (内容已 merge 进 docs/项目说明/)
- `gemini_math_review_action_plan_20260523.md` — R2 Gemini math review meta-audit (3 critical 降温修正 + 5 P0)
- `gemini_math_review_bundle_20260523/` — R2 checklist + 11 red fixture matrix + CP-SAT notes + F9 morphology caution
- `phase1_1_final_delivery_20260523/` — R3 final delivery (10 项 adversarial soundness 升级)
  - `phase1_1_final_acceptance_report.md` (verdict + 10 项 fix detail)
  - `phase1_1_final_gate_fixes.patch` (39 KB)
  - `verification_logs/` (pytest_cuts / mypy / ruff / bandit / vulture / radon / exit_criteria / patch dry-run)
- **`phase1_1_recheck_20260524/`** — R4 recheck补强 (6 类 schema fail-closed 边界)
  - `phase1_1_final_recheck_report.md` (verdict + 6 类 fix detail + 7 regression list + 全 8 门禁验证 cmd)
- `gpt_pro_phase1_1_v{1..6}_audit_*.md` (11 round v1-v6 audit history, 全 NOT GO → 现 GO)

### Cross-check archive (cross_check/)

- `gemini_round_{14..35}*.md` (22 Gemini per-commit cross-check)

### 主流程 src/

```
main.py                              # Campaign entry
src/cuts/                            # B Design v2 cut framework (本次 audit 主对象)
├── lifecycle.py (9 step, R3 加 validate_cut_integrity, R4 拆 10 helper)
├── store.py / replay.py
├── families/{region_capacity,cutset,port_exposure,component_reach}.py (F1-F4 ready, R4 加 _parse_strict_int)
├── oracles/ / helpers/ / assumptions/
src/search/ (outer search + benders loop) / src/models/ (master + binding + routing + flow)
src/tests/cuts/ (188 cuts test, R4 加 7 regression for base64/bitset/scope-cert/bool numeric)
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

## v8 → v11 diff summary

- v8 commit `744305d`: Phase 1.1 v6 audit 后 + plan/math doc 状态 (172 pytest)
- v9 commit `907dade`: Phase 1.1 GO blessed + docs/项目说明/ v1.1 (178 pytest)
- v10 commit `db8d9cd`: Phase 1.1 final hardening (R3 final delivery, 181 pytest)
- **v11 commit `7b0c3c8`**: Phase 1.1 R4 recheck补强 (188 pytest, bool/数字/base64/bitset schema fail-closed)

Commit chain (v8 → v11):
- `af83885` plan doc 高中 7 项 + math doc 新增
- `290bd32` plan §3/§4 收缩 cite math (SoT 政策)
- `b72bc22` 拆 21 sub-doc → docs/项目说明/
- `9e01a6e` R1 Phase 1.1 exit hardening patch (178 pytest)
- `ecc96c7` docs/项目说明/ v1.1 (R1 merge v2 plan + R2 Gemini math review meta-audit)
- `907dade` review-pkg v9 build script
- `db8d9cd` R3 Phase 1.1 final delivery overlay (181 pytest, 10 项 adversarial soundness)
- `7e8b803` review-pkg v10 build script
- `7b0c3c8` R4 Phase 1.1 recheck补强 (188 pytest, 6 类 schema fail-closed)
"""


CHANGELOG = """# Commit log (Phase 1.1 → Phase 1.2 entry, v6 audit → v11 build)

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
| **9e01a6e** | **R1 apply Phase 1.1 exit hardening patch (Phase 1.1 GO blessed)** — 178 pytest, mypy strict pass, radon A 无 D, 8 项 fix (strict gate ON / source_digest 真 hash / radon helper 拆 / F3 删 unused / ghost_rect lock / unsafe stub flag / mypy 清零 / spec drift) |
| **ecc96c7** | **R2 docs/项目说明/ v1.1 — merge v2 plan + Gemini math review meta-audit** — 11 sub-doc update (F9 area-only / F8 mode 锁 / CP-SAT no AddLazyConstraint Q10 verdict / Phase 1.2 P0 acceptance / 11 red fixture / dark matter telemetry) |
| 907dade | review-pkg v9 build script |
| **db8d9cd** | **R3 apply Phase 1.1 final delivery overlay (181 cuts pass, final hardening)** — 10 项 adversarial soundness 升级 (validate_cut_integrity / source_digest 不信外部值 / CutStore 状态机补洞 / watcher 返副本 / F2 free_cells 排除 exterior / F1/F2 payload 加严 base64+bitset+cell / Cut runtime schema 加严 / optional HiGHS+SCIP skip / exit_criteria 文件名 / 文档 178→181 对齐) |
| 7e8b803 | review-pkg v10 build script |
| **7b0c3c8** | **R4 apply Phase 1.1 recheck补强 patch (188 cuts pass, fail-closed schema)** — 6 类 schema fail-closed 边界 (strict base64 validate=True / bitset 高位 0 check / Cut.scope-cert 类型强制 / F1-F4 bool!=int strict / F2+F4 evaluator try-except 返 False / 文档 181→188 对齐). __post_init__ 拆 10 helper 保 radon A. 7 个新增 regression. radon Average A 4.260869565217392 byte-equal reviewer log |
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

    (PROJECT_DIR / "README.md").write_text(README_V11, encoding="utf-8")
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

    (OUT_DIR / "README.md").write_text(README_V11, encoding="utf-8")
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
