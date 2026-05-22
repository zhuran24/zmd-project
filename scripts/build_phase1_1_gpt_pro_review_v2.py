#!/usr/bin/env python3
"""Build phase1_1_gpt_pro_review_v2.zip for GPT pro Phase 1.1 Step A-H audit.

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
OUT_DIR = Path("/tmp/_phase1_1_pkg_v2")
OUT_ZIP = Path("/home/zhuran24/linwin_share/phase1_1_gpt_pro_review_v2.zip")


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


CHANGELOG = """# Phase 1.1 Step A-H Changelog

GPT pro round 1+2 audit verdict NOT GO 后 8 commit close 全 P0 + 5 必修.
Gemini round 33/34/35 follow-up 全 close (3 P0 defer Phase 1.3).

## Commit timeline

| Commit | Step | 修复内容 | Source |
|---|---|---|---|
| 3d35a62 | A | F1-F4 validator assert → fail-closed (`python -O` 防线) | GPT pro 必修 #4 |
| 45c44d2 | B | F3 validator cert ↔ literal multiset 绑定 | GPT pro P0-2 |
| eaed85c | C | F2 partition cells ⊆ free + patch enclosure + cut_edges 集合验 | GPT pro 必修 #4 |
| 5c06dff | D | F4 cert.src/sink_component == recomputed BFS + commodity_id fail-closed | GPT pro P0-4 |
| 8a38401 | E | F1 demand_R 真 P(g)⊆R strict (核心数学层) | GPT pro P0-1 |
| e0ec660 | F | F1 evaluate 重算 cap_R (sound 反 propagator 假 True) + F4 separator_cells | Gemini round 33 P0 + High |
| 3553efb | G | lru_cache(256) on _decode_region_bitset (500x perf) + F4 commodity_id spec align | Gemini round 34 P0 + High |
| e5c41b9 | H | Phase 1.3 perf opt TODO docstring (json.loads cache / by_exterior_watcher / F4 incremental BFS) | Gemini round 35 defer |

## Phase 1.1 状态

### Close (GPT pro 4 P0 + 5 必修):
- P0-1 F1 demand 真 P(g)⊆R: helpers/candidate_placements.all_poses_in_region
  strict check, oracle/validator 双层 enforce. boundary_io 14/54 pose 真数据反例
  现 fail-closed (Phase 1.1 v1.1 F1 cut 在 left∪bottom union region 不发 cut —
  sound first useful 后管).
- P0-2 F3 cert ↔ literal: multiset 严等 (slot anonymity per state_machine_v2 §5).
- P0-3 F2 cut_edges 集合验: partition cells ⊆ free + patch enclosure
  (_has_patch_escape) + cert.cut_edges canonical sorted byte-equal.
- P0-4 F4 commodity_id: spec-aligned 允许 carry (Gemini round 34 升级修).
  cert.src/sink_component bitset 严等 recomputed BFS + separator_cells ⊆ ghost ∪
  cell_owner.
- 必修 #3 (python -O 防线): 全 validator schema assert 改 explicit if/return.
- 必修 #5 (validator 补强): F2 + F4 cert 完整性全 land.

### Defer (Phase 1.2 P1.11 入门 + Phase 1.3 P1.21):
- 必修 #6 strict registration gate default ON: F5-F9 全注册后切换
- 必修 #7 spec docs align: state_machine_v2 PoseId / cut_lifecycle_v2 9 family /
  F2-F4 spec drift / source_digest 真实施 / mypy --strict 29 errors
- Phase 1.3 hot path perf opt: json.loads cache on Cut / by_exterior_watcher /
  F4 evaluate incremental connectivity (TODO docstring 已 inline 代码)

## 156 cuts test pass

```bash
.venv/bin/python -m pytest src/tests/cuts/ -q
# 156 passed

.venv/bin/python -O -m pytest src/tests/cuts/ -q
# 156 passed (Step A python -O 防线 regression 含)
```

## Audit archives

- `docs/research/.../external_review/gpt_pro_phase1_1_audit_round{1,2}_NOT_GO.md` —
  GPT pro 2 round audit verdict (input pkg 是 v1 commit 868bef7)
- `docs/research/.../cross_check/gemini_round_{14..35}*.md` — 22 round Gemini
  cross-check (round 14-32 是 Phase 0/1.0/1.1 base, 33-35 是 Step A-H 验真)

## verify reproducibility (key claims)

cite file:line 验证:
- Step A python -O 1-literal cut → schema_err: src/cuts/families/port_exposure.py:60
  + test: src/tests/cuts/test_family_port_exposure.py::test_validate_port_exposure_one_literal_schema_err_python_O_safe
- Step B F3 multiset: src/cuts/families/port_exposure.py:99-119
- Step C F2 partition enclosure: src/cuts/families/cutset.py:73-91 + validator:155-167
- Step D F4 BFS 严等: src/cuts/families/component_reach.py:104-138
- Step E F1 P(g)⊆R: src/cuts/helpers/candidate_placements.py:131-167 + validator:223-238
- Step F evaluate 重算: src/cuts/families/region_capacity.py:323-348
- Step G lru_cache: src/cuts/families/region_capacity.py:170-189

真数据 sample (Phase 1.1 P(g)⊆R 反例):
- boundary_storage_port 54 pose: 40 wholly inside left∪bottom union, 14 wholly outside
- outside 反例 pose: viewer::boundary_required_output_source_ore_005 占
  (31,69)/(32,69)/(33,69) — 不在 union
"""


README_V2 = """# Phase 1.1 Step A-H production-ready audit pkg (v2)

## 包目的

终末地 (Arknights: Endfield) 70×70 工业规划器 certified exact solver 的
**B Design v2 cut framework** Phase 1.0 + Phase 1.1 实施. v2 包是 GPT pro
round 1+2 audit NOT GO 后 Step A-H 8 commit 修复闭环的产物, 请整 phase audit
soundness + completeness + 任何 production-blocking findings.

## Step A-H 修复总览

详见 `STEP_A_TO_H_CHANGELOG.md`. 一句话: GPT pro 4 P0 + 5 必修 close,
2 必修 (#6 strict gate / #7 spec docs align) + Phase 1.3 hot path perf opt
defer (TODO docstring 已 inline 代码).

## 怎么跑

依赖包 (`zmd_deps_v3.zip` 120MB) 由用户单独上传.

```bash
# 1. Setup
python3.10+ -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # 或 unzip deps 包 + pip install --find-links wheels

# 2. Test (Phase 1.1 Step A-H 修后 src 单元 + spec-data 接合)
.venv/bin/python -m pytest src/tests/cuts/ -q
# 期望: 156 passed

# python -O 模式 (Step A python -O 防线 regression)
.venv/bin/python -O -m pytest src/tests/cuts/ -q
# 期望: 156 passed (1 warning re: assert in test, infrastructural)

# 3. Production oracle smoke (真数据 — F1 boundary_io P(g)⊆R 反例)
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

# 真 pose_domain (从 candidate_placements 提)
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
# 期望: 0 (boundary_io 14 pose 占 union 外 → P(g)⊄R → 不当 contributing → 不发 cut)
# 这是 Step E 修后 sound 结果. Phase 1.5+ group decomp 'P(g)⊆R subset' 解锁 useful.
"
```

## 文件清单

```
src/cuts/                            # Step A-H 修后 production src
├── lifecycle.py                     # 9-step lifecycle + schema (Cut/CutScope/BState)
├── store.py                         # CutStore + 6-dim watcher (by_exterior defer)
├── replay.py                        # store-aware replay + FAMILY_VALIDATORS
├── families/                        # F1-F4 validator + evaluator (Step A-G 修)
│   ├── region_capacity.py           # Step A/E/F/G (P(g)⊆R + evaluate 重算 + lru_cache)
│   ├── cutset.py                    # Step A/C (partition enclosure + cut_edges 严等)
│   ├── port_exposure.py             # Step A/B (python -O 防线 + cert↔literal multiset)
│   └── component_reach.py           # Step A/D/F/G (BFS 严等 + separator_cells + commodity 兼容)
├── oracles/                         # F1 production combinatorial; F2/F3/F4 stub (Phase 1.5+ wire)
├── helpers/                         # canonical_rules / candidate_placements / ghost_geometry / etc
└── assumptions/                     # ASSUMPTION_VERIFIERS dispatch

src/tests/cuts/                      # 156 unit test (Step A-H regression incl)
data/preprocessed/                   # 真数据 (266 instance + 273 pose)
rules/canonical_rules.json           # facility_templates + recipes + production_targets
docs/research/p3_b_design_v2_20260521/
├── cut_lifecycle_v2.md              # 9-step lifecycle spec
├── state_machine_v2.md              # BState schema + 5 invariants
├── PROJECT_LOCK.md                  # 3A invariants
├── cut_family_specs/                # F1-F9 spec
├── cross_check/                     # 22 round Gemini archives (14-35)
└── external_review/                 # GPT pro round 1+2 audit archives
STEP_A_TO_H_CHANGELOG.md             # 8 commit + 修复 source map
README.md (本文件)
requirements.txt
```

## 期望反馈 (两层)

### 层 1: 验 round 1+2 audit 的修复情况

逐 P0 + 必修 verify Step A-H 修是否真到位 + Sound + 没引新 critical bug:
- P0-1 F1 P(g)⊆R strict — 真数据 boundary_io 14/54 outside pose 反例修了?
- P0-2 F3 cert↔literal multiset 绑定 — slot anonymity 处理对?
- P0-3 F2 cut_edges 集合验 + partition enclosure — 数学 sound?
- P0-4 F4 cert.bitset == BFS — frozenset 严等 + commodity_id Phase 1.5+ 兼容?
- 必修 #3 python -O 防线 — 全 validator 入口都改?
- 必修 #5 validator 补强 — F2/F4 完整?

### 层 2: 继续找 Phase 1.1 任何**新**问题 (不限修复范围)

整 phase audit, 任何可能的 production-blocking finding:
- 全 src/cuts/{lifecycle, store, replay, families, oracles, helpers, assumptions}
  spec ↔ src ↔ 真数据 三层 align 任何 drift?
- adversarial soundness — 假 cert 还能 pass validator 吗 (任何 cert 完整性
  漏洞 Gemini round 33-35 没 catch 的)?
- Phase 1.3 P1.21 时 hot path perf (Gemini round 35 catch json.loads / BFS /
  by_exterior_watcher 是否真当 P0 处理, 或定 defer 合理?)
- 必修 #6 strict gate / #7 spec docs align — 在 Phase 1.2 P1.11 落地前合理 defer
  还是必须先做?
- 隐藏 P0 — 跟 PROJECT_LOCK §3A invariants 接合任何漂移?
- Phase 1.2 F5-F9 spec 实施前 阻断项?
- mypy --strict 29 errors / ruff / bandit / radon C 级 hotspot — 任何
  production hygiene 必修?

prompt 跟此 zip 单独通过 chat 给.

## 数据说明

`data/preprocessed/candidate_placements.json` (372 KB, 273 pose) 是 viewer
sample, 跟所有 audit archive 的 "BSP 14/54 outside union" 反例 cite 来源一致.
真生产 search 用全集 (BState.candidate_placements 字段 inject), schema 一致 — sample 够
verify Phase 1.1 所有 validator soundness claim.

## 包内 audit history (cross_check + external_review)

- `docs/research/.../external_review/gpt_pro_phase1_1_audit_round{1,2}_NOT_GO.md`
  — 2 round audit verdict (Step A-H 修复的 trigger source)
- `docs/research/.../cross_check/gemini_round_{14..35}*.md` — 22 round
  Gemini cross-check (含 r33/34/35 验 Step A-H 修复 + 升级 finding)
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

    # Write CHANGELOG + README
    (OUT_DIR / "STEP_A_TO_H_CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
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
