#!/usr/bin/env python3
"""Build phase1_1_gpt_pro_review_v3.zip for GPT pro Phase 1.1 Step A-H audit.

Diff vs v1 (commit 868bef7):
- src/cuts/ 全更 (Step A-H 8 commit 修后版)
- src/tests/cuts/ 全更 (156 PASS vs v1 139)
- 新增 cross_check archives: gemini_round_3{3,4,5}*.md
- 新增 external_review archives: gpt_pro_phase1_1_audit_round{1,2}_NOT_GO.md
- 新增 STEP_A_TO_H_CHANGELOG.md
- README 更新 (close status + 残余 defer items)

按 memory rules:
- prompt 不放包内 (chat 单独给)
- 包独立可跑, 不引用历史 ("跟 v1 不一样" 这类)
- 真数据 inline 给 + Gemini/GPT archive 让 audit 自查
- depends 通过 ~/linwin_share/zmd_deps_v3.zip (用户上传)
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO = Path("/home/zhuran24/claude-pj/zmd")
OUT_DIR = Path("/tmp/_phase1_1_pkg_v3")
OUT_ZIP = Path("/home/zhuran24/linwin_share/phase1_1_gpt_pro_review_v3.zip")


FILES = [
    # 真数据
    "rules/canonical_rules.json",
    "data/preprocessed/mandatory_exact_instances.json",
    "data/preprocessed/generic_io_requirements.json",
    # spec
    "PROJECT_LOCK.md",
    "docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md",
    "docs/research/p3_b_design_v2_20260521/state_machine_v2.md",
    "docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/05_pattern_nogood.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/06_shape_packing_hall.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/07_power_hitting_set.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md",
    "docs/research/p3_b_design_v2_20260521/cut_family_specs/09_density_envelope.md",
    # cross_check archives (Gemini)
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_14_cut_families.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_15_followup.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_16_day17.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_17_followup.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_18_phase0_go.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_19_f9_critical.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_20_all_clear.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_21_quarantine_fix.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_22_phase0_close.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_23_absolute_final.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_24_a_layer.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_25_phase1_ready.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_26_phase1_go.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_27_p1_1_src_verify.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_28_phase1_0_framework_go.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_29_phase1_1_families_go.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_30_gap6_audit_NOT_GO.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_31_gap_fix_verify_NOT_GO.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_32_gap_fix_verify_round2_partial_GO.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_33_gpt_pro_fix_verify_NOT_GO.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_34_step_f_verify_NOT_GO.md",
    "docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_35_step_g_verify_NOT_GO_phase13_defer.md",
    # external review archives (GPT pro)
    "docs/research/p3_b_design_v2_20260521/external_review/gpt_pro_phase1_1_audit_round1_NOT_GO.md",
    "docs/research/p3_b_design_v2_20260521/external_review/gpt_pro_phase1_1_audit_round2_NOT_GO.md",
    "docs/research/p3_b_design_v2_20260521/external_review/gpt_pro_phase1_1_v2_audit_round1_NOT_GO.md",
    "docs/research/p3_b_design_v2_20260521/external_review/gpt_pro_phase1_1_v2_audit_round2_NOT_GO.md",
    # config
    "requirements.txt",
]

# src/cuts/ 全包 (Step A-H 修后)
SRC_DIRS = [
    "src/cuts",
    "src/tests/cuts",
]


# 特殊文件 (rename / 不同源到不同 dst)
SPECIAL_COPIES = {
    # candidate_placements: 用 viewer sample (273 pose / BSP 54, 372KB), 跟所有
    # audit archive cite 的 "BSP 14/54 outside union" 反例数字一致. production
    # 全集 (data/preprocessed/, 81K pose, 53MB) 不适合 audit pkg, schema 一致.
    "data/examples/industrial_planner/current_delivery/viewer/candidate_placements.json":
        "data/preprocessed/candidate_placements.json",
}


CHANGELOG = """# Commit log (Phase 1.1 Step A-K)

10 commit (含 1 build-script infra commit). 每 commit message 在 git log (commit hash 列).

| Commit | Files touched | Subject |
|---|---|---|
| 3d35a62 | families/{region_capacity, cutset, port_exposure, component_reach}.py + lifecycle.py + test_family_port_exposure.py | validator schema assert 改 explicit if/return |
| 45c44d2 | families/port_exposure.py + test_family_port_exposure.py | F3 validator 加 cert ↔ literal multiset 绑定 |
| eaed85c | families/cutset.py + test_family_cutset.py | F2 validator 加 partition cells ⊆ free + patch enclosure + cut_edges 集合验 |
| 5c06dff | families/component_reach.py + test_family_component_reach.py | F4 validator 加 cert.src/sink_component == BFS + commodity_id schema_err |
| 8a38401 | helpers/candidate_placements.py + families/region_capacity.py + oracles/region_capacity_oracle.py + test 2 file + test_replay.py | F1 加 strict P(g)⊆R check |
| e0ec660 | families/region_capacity.py + families/component_reach.py + test 2 file | F1 evaluate 改 recompute cap_R; F4 加 separator_cells check |
| 3553efb | families/region_capacity.py + families/component_reach.py + test_family_component_reach.py | _decode_region_bitset 加 lru_cache(256); F4 移除 commodity_id schema_err |
| e5c41b9 | families/region_capacity.py + families/component_reach.py + store.py + archive + scripts | docstring 加 Phase 1.3 P1.21 TODO; archive Gemini round 33/34/35 |
| 2165285 | scripts/build_phase1_1_gpt_pro_review_v2.py | review-pkg v2 build script (删 README/CHANGELOG 主动性内容) |
| bdaa303 | lifecycle.py + families/{port_exposure, component_reach, cutset}.py + 3 test file | step_7 family dispatch; F3 blocking_slot→pose binding; F4 separator in-grid; F2 evaluator enclosure |
"""


README_V2 = """# Phase 1.1 audit pkg

终末地 (Arknights: Endfield) 70×70 工业规划器 certified exact solver 的
**B Design v2 cut framework** Phase 1.0 + Phase 1.1 实施.

## 怎么跑

依赖包 `zmd_deps_v3.zip` 单独上传.

```bash
# Setup
python3.10+ -m venv .venv && source .venv/bin/activate
unzip -q ../zmd_deps_v3.zip -d /tmp/deps
pip install --find-links /tmp/deps -r requirements.txt

# 单元测试
.venv/bin/python -m pytest src/tests/cuts/ -q

# python -O 模式
.venv/bin/python -O -m pytest src/tests/cuts/ -q

# 静态工具 (包内 deps 含)
.venv/bin/python -m ruff check src/cuts/ src/tests/cuts/
.venv/bin/python -m mypy --explicit-package-bases --strict src/cuts/
.venv/bin/python -m vulture src/cuts/
.venv/bin/python -m bandit -r src/cuts/
.venv/bin/python -m radon cc src/cuts/ -s -a

# Production smoke (真数据)
python -c "
import json
from src.cuts.lifecycle import BState, GroupState
from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts

with open('rules/canonical_rules.json') as f:
    rules = json.load(f)
with open('data/preprocessed/mandatory_exact_instances.json') as f:
    mei = json.load(f)
with open('data/preprocessed/candidate_placements.json') as f:
    cp = json.load(f)

import collections
ops = collections.Counter(i['operation_type'] for i in mei)
op_to_ft = {i['operation_type']: i['facility_type'] for i in mei}
pose_domain_by_ft = {
    ft: frozenset(p['pose_id'] for p in poses)
    for ft, poses in cp['facility_pools'].items()
}

state = BState(
    groups={
        op: GroupState(
            op, demand=count,
            pose_domain=pose_domain_by_ft.get(op_to_ft[op], frozenset()),
        )
        for op, count in ops.items()
    },
    facility_templates=rules['facility_templates'],
    instance_to_facility_type=op_to_ft,
    exterior_blocks=frozenset({(15, 0), (16, 0)}),
    canonical_rules=rules,
    candidate_placements=cp,
)
cuts = generate_region_capacity_cuts(state, rules)
print(f'F1 cuts emitted: {len(cuts)}')
"
```

## 文件清单

```
src/cuts/                            # production src
├── lifecycle.py                     # 9-step lifecycle + schema (Cut/CutScope/BState)
├── store.py                         # CutStore + 6-dim watcher
├── replay.py                        # store-aware replay + FAMILY_VALIDATORS
├── families/                        # F1-F4 validator + evaluator
├── oracles/                         # F1 combinatorial; F2/F3/F4 stub
├── helpers/                         # canonical_rules / candidate_placements / ghost_geometry / etc
└── assumptions/                     # ASSUMPTION_VERIFIERS dispatch

src/tests/cuts/                      # unit test
data/preprocessed/                   # 真数据 (266 instance + 273 pose)
rules/canonical_rules.json           # facility_templates + recipes + production_targets
docs/research/p3_b_design_v2_20260521/
├── cut_lifecycle_v2.md              # 9-step lifecycle spec
├── state_machine_v2.md              # BState schema + 5 invariants
├── PHASE_1_PLAN.md                  # Phase 1 plan
├── cut_family_specs/                # F1-F9 spec
├── cross_check/                     # 22 round Gemini archives (round 14-35)
└── external_review/                 # GPT pro audit archives
PROJECT_LOCK.md                      # 3A invariants
COMMIT_LOG.md                        # commit timeline
README.md (本文件)
requirements.txt
```

## 数据说明

`data/preprocessed/candidate_placements.json` (372 KB, 273 pose) 是 viewer
sample. 真生产 search 用全集 (BState.candidate_placements 字段 inject),
schema 一致.
"""


def main() -> int:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    # Copy individual files
    missing = []
    for rel in FILES:
        src = REPO / rel
        if not src.exists():
            missing.append(rel)
            continue
        dst = OUT_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Special copies (rename src → dst)
    for src_rel, dst_rel in SPECIAL_COPIES.items():
        src = REPO / src_rel
        if not src.exists():
            missing.append(src_rel)
            continue
        dst = OUT_DIR / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Copy src dirs (with __pycache__ filter)
    for rel in SRC_DIRS:
        src = REPO / rel
        dst = OUT_DIR / rel
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(
            src, dst,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    # Write COMMIT_LOG + README
    (OUT_DIR / "COMMIT_LOG.md").write_text(CHANGELOG, encoding="utf-8")
    (OUT_DIR / "README.md").write_text(README_V2, encoding="utf-8")

    # Build zip
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()
    subprocess.run(
        ["zip", "-rq", str(OUT_ZIP), OUT_DIR.name],
        cwd=str(OUT_DIR.parent),
        check=True,
    )

    size_mb = OUT_ZIP.stat().st_size / (1024 * 1024)
    print(f"Output: {OUT_ZIP}")
    print(f"Size: {size_mb:.2f} MB")
    if missing:
        print(f"\n⚠️  MISSING ({len(missing)} files):")
        for m in missing:
            print(f"  - {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
