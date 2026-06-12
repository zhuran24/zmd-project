# 终末地 IndustrialPlanner 几何 master round 5 审查记录

审查对象只使用 `zmd_snapshot_70457b5e.zip`。开工校验通过：

```text
70457b5e6cd759fd0fd75873b12b61f444ad3e569bb26216cea7aa383b22b15a  /mnt/data/zmd_snapshot_70457b5e.zip
45773799 data/preprocessed/candidate_placements.json
adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0  data/preprocessed/candidate_placements.json
```

结论：本轮发现 1 个 soundness/API false-INFEASIBLE finding，已给出 unified diff 与回归测试。其余 Q1 R4-A 主路径、Q2 slot 域到 candidate pool 对接、Q3 specs 独立对照未发现新的 soundness 问题。

## Finding 1: fixed required power_pole 在无 family 语义时被空 family table 强制判死

Severity: Medium。属于 R4-A 同族 API 缝的退化边界，主工程常规 266 强制设施有 powered demand，所以主线矩形搜索不容易踩到；但 `exact_required_pose_optional_counts={"power_pole": 1}` 的 API 语义下，固定杆即使没有待供电设施，仍应作为真实几何设施被放置，而不是因为 family 表不存在被判 infeasible。

位置：原始快照 `src/models/exact_coordinate_master.py:2070-2074`, `src/models/exact_coordinate_master.py:2984-3006`, `src/models/exact_coordinate_master.py:3176-3183`。

触发链：

1. `_prepare_power_pole_families()` 在 `skip_power_coverage` 或 `powered_template_demands` 为空时提前返回，未构造 `_power_pole_family_name_by_int` 与 `_power_pole_family_id_by_pose_idx`。这在 `src/models/exact_coordinate_master.py:2070-2074`。
2. 显式固定杆仍会作为 required optional slot 进入模型。slot 构建来自 `src/models/exact_coordinate_master.py:2271-2293`，几何变量在 `_create_required_optional_slot_vars()` 中按 mandatory-like slot 建立，见 `src/models/exact_coordinate_master.py:2811-2829`。
3. `_create_power_pole_slot_vars()` 只要存在 pole 域就无条件调用 `_attach_required_power_pole_family_channels()`，见 `src/models/exact_coordinate_master.py:3176-3183`。
4. 原始 `_attach_required_power_pole_family_channels()` 在 family 映射为空时得到 `tuple_rows=[]`，然后对每个 fixed pole slot 执行 `Add(0 == 1)`，见 `src/models/exact_coordinate_master.py:2984-3006`。这把一个几何上合法的固定杆退化配置误判为 INFEASIBLE。

最小复现 probe，原始快照返回 `INFEASIBLE`：

```python
from ortools.sat.python import cp_model
from src.models.master_model import MasterPlacementModel

pools = {
    "power_pole": [
        {
            "pose_id": "pole_0",
            "anchor": {"x": 0, "y": 0},
            "pose_params": {"orientation": 0, "port_mode": "none"},
            "occupied_cells": [[0, 0]],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": [[0, 0], [1, 0]],
        }
    ],
}
rules = {
    "globals": {"grid": {"width": 2, "height": 1}},
    "facility_templates": {
        "power_pole": {
            "dimensions": {"w": 1, "h": 1},
            "needs_power": False,
            "power_coverage_radius": 1,
        },
    },
}
model = MasterPlacementModel(
    instances=[],
    facility_pools=pools,
    rules=rules,
    solve_mode="certified_exact",
    exact_required_pose_optional_counts={"power_pole": 1},
)
status = model.solve(time_limit_seconds=1.0)
assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
```

修法：当 power family 映射为空时，fixed pole 不需要接入 capacity-family channel。它仍然保留 required optional 几何 slot，并通过 `_all_power_pole_slots()` 作为真实杆被其它存在的通道读取。正常有 powered demand 的 R4-A 路径不受影响，因为 family 映射非空，仍走原来的 table/membership/count 逻辑；若有 family 映射但 table 行异常为空，仍保留原 fail-closed 行为。

补丁位置：patched `src/models/exact_coordinate_master.py:2988-2995`。回归测试：patched `src/tests/test_exact_coordinate_protocol_bounds.py:180-216`。

## Unified diff

```diff
--- a/src/models/exact_coordinate_master.py
+++ b/src/models/exact_coordinate_master.py
@@ -2985,6 +2985,14 @@
         required_pole_slots = list(self.required_optional_slots.get("power_pole", []))
         if not required_pole_slots:
             return
+        if not self._power_pole_family_name_by_int:
+            # There is no capacity-family semantic channel to attach when power
+            # coverage is explicitly skipped or when the model has no powered
+            # demand at all.  Fixed required poles are still real geometry slots;
+            # forcing an empty family table here would reject those legal
+            # geometry-only configurations before the relevant witness/capacity
+            # constraints even exist.
+            return
         sentinel_family = int(len(self._power_pole_family_name_by_int))
         tuple_rows = self._power_pole_family_pose_tuple_rows_for_required_slots()
         for slot in required_pole_slots:
--- a/src/tests/test_exact_coordinate_protocol_bounds.py
+++ b/src/tests/test_exact_coordinate_protocol_bounds.py
@@ -175,3 +175,42 @@
     assert len(model._coordinate_delegate.required_optional_slots["power_pole"]) == 1
     assert len(model._coordinate_delegate.residual_optional_slots.get("power_pole", [])) == 0
     assert model.build_stats["power_coverage"]["pole_slots"] == 1
+
+
+def test_fixed_required_power_pole_without_powered_demand_keeps_geometry_semantics() -> None:
+    pools = {
+        "power_pole": [
+            {
+                "pose_id": "pole_0",
+                "anchor": {"x": 0, "y": 0},
+                "pose_params": {"orientation": 0, "port_mode": "none"},
+                "occupied_cells": [[0, 0]],
+                "input_port_cells": [],
+                "output_port_cells": [],
+                "power_coverage_cells": [[0, 0], [1, 0]],
+            }
+        ],
+    }
+    rules = {
+        "globals": {"grid": {"width": 2, "height": 1}},
+        "facility_templates": {
+            "power_pole": {
+                "dimensions": {"w": 1, "h": 1},
+                "needs_power": False,
+                "power_coverage_radius": 1,
+            },
+        },
+    }
+    model = MasterPlacementModel(
+        instances=[],
+        facility_pools=pools,
+        rules=rules,
+        solve_mode="certified_exact",
+        exact_required_pose_optional_counts={"power_pole": 1},
+    )
+
+    status = model.solve(time_limit_seconds=2.0)
+
+    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
+    assert len(model._coordinate_delegate.required_optional_slots["power_pole"]) == 1
+    assert len(model._coordinate_delegate._all_power_pole_slots()) == 1
```

## Q1: R4-A 修复确认记录

`_all_power_pole_slots()` 的全文件消费点已扫过。函数本身在 `src/models/exact_coordinate_master.py:2978-2982` 合并 fixed required pole 与 residual pole，主要读取点如下：family count upper bound `src/models/exact_coordinate_master.py:1662-1666`，lazy power stats `src/models/exact_coordinate_master.py:3329-3331`，table coverage witness `src/models/exact_coordinate_master.py:5026-5077`，geometric coverage witness `src/models/exact_coordinate_master.py:5676-5758`。这些读取点都走合并函数。残留的 `residual_optional_slots.get("power_pole")` 引用只用于 residual pole 创建、residual-only 对称破除、search guidance，以及 residual pole 激活数上界，见 `src/models/exact_coordinate_master.py:3185-3288`, `src/models/exact_coordinate_master.py:6111-6129`；它们不应把 fixed pole 纳入左侧 residual 决策池。

fixed pole 的 active 常量化经 CP-SAT 探针确认可用于 `AddElement`、`OnlyEnforceIf` 和线性约束：

```text
constant_active_probe OPTIMAL 0 0 1
```

实现上 `_slot_active_lookup_value()` 对 fixed slot 返回 `NewConstant(1)`，见 `src/models/exact_coordinate_master.py:2973-2976`；table witness 对 fixed pole 不加 `cover_lit <= active`，对 residual pole 加该约束，见 `src/models/exact_coordinate_master.py:5051-5065`；geometric witness 的 lookup 使用 `_all_power_pole_slots()` 与 active lookup，见 `src/models/exact_coordinate_master.py:5712-5728`。因此 fixed 与 residual 在覆盖 witness 中的差异正好是“fixed 恒激活”。

R3-A 与 R4-A 的交界也做了混合 probe：fixed pole 1 个、fixed protocol box 1 个、protocol lower bound 2 个，要求 residual protocol slot 继续存在，并由同一 fixed pole 覆盖 mandatory powered machine 与两个 protocol boxes。patched 结果：

```text
fixed_pole_fixed_residual_protocol_probe OPTIMAL all_poles 1 req_proto 1 res_proto 1 coverage_poles 1
```

这条路径对应 `_needs_residual_optional_slots_after_fixed_required()` 在 `src/models/exact_coordinate_master.py:1650-1660`，protocol shortfall 约束在 `src/models/exact_coordinate_master.py:6045-6079`，fixed+residual pole 合并覆盖在 `src/models/exact_coordinate_master.py:5028` 与 `src/models/exact_coordinate_master.py:5678`。未发现 protocol fixed 与 power pole fixed 的交叉污染。

family count upper bound 的推导在正常 powered demand 路径仍有效：`_power_pole_family_count_upper_bound()` 取 `min(family_size, len(_all_power_pole_slots()))`，见 `src/models/exact_coordinate_master.py:1662-1666`。这是每个 family 可出现数量的上界，fixed+residual 混合时不会低估；patched 只在 family 映射为空时跳过 fixed family channel，不会影响有 family 映射的正常路径。

## Q2: slot 域构建到 candidate pool 对接表

| 环节 | 判读 | 依据 |
| --- | --- | --- |
| mandatory slot 域为空 | 正确判 infeasible。mandatory 必须放置，空域没有可关闭的 active literal。 | slot 构造 `src/models/exact_coordinate_master.py:2239-2269`，empty-domain fast path `src/models/exact_coordinate_master.py:2515-2547`。 |
| required-optional fixed slot 域为空 | 正确判 infeasible。显式 required count 表示必须放置 N 个该模板姿态，不能静默降为 0。 | fixed slots 构造 `src/models/exact_coordinate_master.py:2271-2293`，required optional 建模 `src/models/exact_coordinate_master.py:2811-2829`。 |
| residual optional 域为空 | 生产路径不会把空域 residual optional 送入 fast path。上界小于等于 0 或 candidate count 为 0 时不 materialize；plain path 仍有 `if not all_domains: continue`；optional signature path没有可用 bucket 时约束 `active=0`，不是全局 infeasible。 | `src/models/exact_coordinate_master.py:2295-2341`, `src/models/exact_coordinate_master.py:2901-2903`, `src/models/exact_coordinate_master.py:2749-2753`。 |
| pose tuple 与 mode 域 | pool 顺序直接枚举为 pose_idx，`(x,y,mode)` 反查同一个 pose_idx；重复 tuple fail closed；缺 `occupied_cells` 或同 mode footprint 不稳定 fail closed。 | `src/models/exact_coordinate_master.py:1553-1616`, `src/models/exact_coordinate_master.py:1668-1699`。 |
| mandatory powered pose 过滤 | 对 certified power coverage 是必要条件。没有任何非重叠 pole coverer 的 powered pose 不可能满足 `needs_power`；disjoint 过滤也是必要条件，因为 pole body 与 powered body 还要通过 master no-overlap。 | coverer 与 disjoint 过滤 `src/models/master_model.py:3581-3607`，mandatory candidate filter `src/models/master_model.py:7491-7510`。 |
| ghost/signature bucket 过滤 | 不是从实现学习语义，而是 candidate bucket 的压缩表示。过滤后会检查 allowed pose 是否全部被 region 覆盖，不能表示则 fail closed，不会默默过强接受或拒绝。 | signature payload `src/models/exact_coordinate_master.py:1834-1894`，bucket payload `src/models/master_model.py:4359-4436`。 |
| family 瀑布激活与重标号 | power pole 瀑布只作用 residual poles，不把 fixed pole 混入可交换 residual 序列；protocol residual symmetry 只在同 template、同 slot 池上排序。bucket 大小不均匀由每个 bucket 的实际 upper bound 负责，不要求域均匀。 | residual pole symmetry `src/models/exact_coordinate_master.py:3266-3278`，protocol residual symmetry `src/models/exact_coordinate_master.py:2929-2937`，bucket upper bounds `src/models/exact_coordinate_master.py:2876-2899`。 |
| pose_idx 下游一致性 | master 读取 `candidate_placements.json` 后保持 `facility_pools[tpl]` list 顺序；coordinate delegate 用同一顺序枚举 pose_idx；extract_solution 通过 `(x,y,mode) -> pose_idx -> facility_pools[tpl][pose_idx]` 回读。 | `src/models/master_model.py:2161-2182`, `src/models/master_model.py:2256-2261`, `src/models/exact_coordinate_master.py:6577-6644`。 |

Q2 结论：除 Finding 1 的 fixed pole family 空表退化外，slot 域与 pool 的对接未见新的 false-INFEASIBLE 或 silent pose错位问题。

## Q3: specs 文本独立对照清单

本节先按 specs 和 canonical rules 建立应编码语义，再对照 master 实现。

| 规则语义 | 文本依据 | 实现对照 |
| --- | --- | --- |
| 网格为 70×70，候选坐标必须在闭区间内。 | `rules/canonical_rules.json:7-23`，`specs/02_global_notation_and_units.md:23-30`。 | exact master 从规则读取 `grid_w/grid_h` 并从候选 pool 建域；candidate pool 本身是 certified 输入，缺失或不稳定 footprint fail closed。 |
| 目标是 `max_lex(area, min_side)`，`min_side >= 6` 是 admissibility，不是 tie-break。 | `PROJECT_LOCK.md:10-16`，`specs/01_problem_statement.md:21-59`。 | `exact_coordinate_master.py` 是固定 `(w,h)` feasibility model，没有 `Maximize/Minimize` 主目标；ghost candidate 只接收外层给定尺寸。目标与 admissibility 分工干净。 |
| candidate pool 按 template 共享，pose 必须携带 anchor、pose_params、occupied_cells、power_coverage_cells。 | `specs/06_candidate_placement_enumeration.md:18-40`。 | `load_project_data()` 读 `candidate_placements.json` 与 rules，`MasterPlacementModel` 保持 pool list 顺序；coordinate delegate 按 pool 顺序建 tuple map。见 `src/models/master_model.py:2161-2182`, `src/models/master_model.py:2256-2261`, `src/models/exact_coordinate_master.py:1668-1699`。 |
| mandatory exactly-one，required/fixed optional 必须放置，residual optional 由 active 决策。 | `specs/07_master_placement_model.md:46-57`，`PROJECT_LOCK.md:115`。 | mandatory slots 按 group count 构造；required optional fixed count 构造 N 个 mandatory-like slot；residual optional 有 active literal，并用 protocol shortfall 承接 fixed 后剩余下界。见 `src/models/exact_coordinate_master.py:2239-2341`, `src/models/exact_coordinate_master.py:6045-6079`。 |
| no-overlap 只覆盖刚体 body 与 ghost 禁区；ordinary ports/belts/routing 不属于 master no-overlap。 | `specs/07_master_placement_model.md:13-16`, `specs/07_master_placement_model.md:59-62`, `specs/07_master_placement_model.md:100-104`。 | coordinate master 用 footprint interval 加 `AddNoOverlap2D`，ghost 也作为 interval 进入同一个 no-overlap；没有把 routing belts 加入 master no-overlap。见 `src/models/exact_coordinate_master.py:3313-3315`, `src/models/exact_coordinate_master.py:3497-3597`。 |
| ghost 矩形是全空地禁区，允许完全被包围；只要求存在、连续、与设施不重叠。 | `PROJECT_LOCK.md:105`，`specs/01_problem_statement.md:63-74`，`specs/06_candidate_placement_enumeration.md:84-91`。 | `_add_ghost_constraints()` 对所有合法 anchor 建 optional interval，`AddExactlyOne` 选一个，并和所有 core intervals 做 no-overlap。排除集是设施 body 与 pole body，不包括端口 connector、belt 或 coverage cells，口径与 specs 一致。 |
| power coverage：每个 `needs_power=true` 的 selected pose 必须由至少一个 active pole 的 coverage 与其 body 相交覆盖。 | `specs/07_master_placement_model.md:64-70`，`rules/canonical_rules.json:83-103`。 | table/geometric 两条 witness 都枚举 `_all_power_pole_slots()`，fixed pole active 为常量 1，residual pole 受 active literal 控制。见 `src/models/exact_coordinate_master.py:5026-5077`, `src/models/exact_coordinate_master.py:5676-5758`。 |
| candidate footprint 要从 `occupied_cells` 推导，不得只用模板默认尺寸 under-approximate。 | `PROJECT_LOCK.md:116`，`specs/07_master_placement_model.md:113-117`。 | mode token 包含 footprint key，mode 域要求 footprint bounds 稳定；NoOverlap、ghost、power selected geometry都读取同一 footprint channel。见 `src/models/exact_coordinate_master.py:1553-1616`, `src/models/exact_coordinate_master.py:2509-2588`。 |
| protocol storage lower bound 中 fixed required slots 要计入，只对 shortfall 要 residual literal。 | `PROJECT_LOCK.md:115`。 | `_needs_residual_optional_slots_after_fixed_required()` 与 lower-bound 约束一致：fixed ≥ lower 时不建 residual；0 < fixed < lower 时保留 residual 并约束 shortfall。见 `src/models/exact_coordinate_master.py:1650-1660`, `src/models/exact_coordinate_master.py:6045-6079`。 |

Q3 结论：除 Finding 1 的 fixed pole family 空表边界外，规则文本要求的 mandatory 计数、不重叠、在界、供电覆盖、ghost 空置、`min_side>=6` admissibility 与目标分工均未见实现更严、更松或缺失。

## 验证记录

环境：Python 3.13 venv，离线安装 `zmd_py313_linux_x86_64.zip` wheels，`ortools 9.15.6755`，`pytest 9.0.2`。全量 `src/tests` 曾启动但 300 秒超时，仅推进到约 16%，未观察到失败；以下专项与 gate 已跑完。

```text
python -m pytest -q -p no:randomly src/tests/test_exact_coordinate_protocol_bounds.py
4 passed in 1.03s

python -m pytest -q -p no:randomly src/tests/test_master.py -k "power_pole_family_count or exact_power_capacity_lower_bound or exact_optional_cardinality_bound or exact_geometric_power_coverage or coordinate_exact_power_family_lookup or coordinate_exact_power_coverage"
28 passed, 198 deselected in 1.20s

python -m pytest -q -p no:randomly src/tests/test_master.py -k "coordinate_symmetry_breaking_orders or ghost_signature_bucket or ghost_conditioned"
39 passed, 187 deselected in 1.15s

python -m pytest -q -p no:randomly src/tests/test_coordinate_benders_cut_presence_nogood.py src/tests/test_master_extract_bound_state.py src/tests/test_placements.py src/tests/test_power_witness_cut_dilution.py src/tests/test_power_placement_subproblem.py
38 passed in 4.65s

python scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 8 obligations anchored
```

补丁包：见 `zmd_r5_patch.diff`。没有修改 routing、binding、preprocess、campaign、scheduler 或 cuts 面。
