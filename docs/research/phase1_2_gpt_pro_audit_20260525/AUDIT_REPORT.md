# 终末地工业规划器 Phase 1.2 close audit — cb8e347

审查范围：用户提供的 `phase1_2_close_review_v12.zip`，重点看 Phase 1.1 close → Phase 1.2 close 区间的 cut framework、F2/F4/F5/F6/F7/F8/F9、Mini Step 8 spike、Phase 1.3/1.5+ 计划。  
本报告的 finding 都来自包内源码/脚本可复现结果；没有使用“外部新算法/新文献”去推翻历史 lever verdict。没有发现需要 resurrect 27 lever 的证据；这次 push-back 主要是当前 Phase 1.2 cut validator / integration gate 内部的问题。

## Finding 1 — F7 `power_hitting_set` 可用假 `facility_cells` 通过 validator，形成 false-positive cut

**severity**: BLOCKER

**file:line**

- `/_phase1_2_pkg_v12/project/src/cuts/families/power_hitting_set.py:111-136`
- `/_phase1_2_pkg_v12/project/src/cuts/families/power_hitting_set.py:232-284`
- `/_phase1_2_pkg_v12/project/src/cuts/families/power_hitting_set.py:423-427`
- `/_phase1_2_pkg_v12/project/src/cuts/lifecycle.py:920-957`

**问题陈述**

F7 validator 只检查 cert 里的 `facility_cells` 形状合法、group/pose 存在、facility 需要 power，但没有检查 `facility_cells` 是否等于 `candidate_placements` 中该 `facility_pose_id` 的真实 footprint。  
因此可以构造一个 cert：literal 指向真实选中的 pose `(crusher_blue_iron, p_3x3_a)`，但 `facility_cells` 写成另一个位置；validator 用假 cells 证明 CoverSet 为空，generic literal evaluator 又只按 selected pose 触发，最终会 cut 掉一个实际可供电的 pose。  
这不是性能问题，是 soundness false-positive。

**reproduce 步骤**

```bash
cd _phase1_2_pkg_v12/project
. .venv/bin/activate
python - <<'PY'
from src.tests.cuts.test_family_power_hitting_set import _make_state, _make_cert, _make_cut
from src.cuts.families.power_hitting_set import validate_power_hitting_set
from src.cuts.lifecycle import evaluate_literal_multiset
from src.cuts.helpers.power_cover import compute_cover_set

state = _make_state(pose_anchor=(0,0), ghost_rect=(25,25,16,16))
state.groups["crusher_blue_iron"].selected_poses = ["p_3x3_a"]

actual = tuple(tuple(c) for c in state.candidate_placements["facility_pools"]["manufacturing_3x3"][0]["occupied_cells"])
free = frozenset((x,y) for x in range(70) for y in range(70)
               if (x,y) not in state.ghost_cells
               and (x,y) not in state.exterior_blocks
               and (x,y) not in state.cell_owner
               and (x,y) not in actual)
cover = compute_cover_set(actual, free, 5.0)

cert_payload = _make_cert(state)  # 默认 cert cells 是 (30,30)..(32,32)，不是真实 pose (0,0)..(2,2)
cut = _make_cut(cert_payload, state)
vr = validate_power_hitting_set(cut, state, canonical_rules={})

print("actual cover size:", len(cover), "sample:", sorted(cover)[:5])
print("validator:", vr.kind, vr.detail)
print("evaluator:", evaluate_literal_multiset(cut, state))
print("actual_pose_cells_first_last:", actual[0], actual[-1])
PY
```

观察到：

```text
actual cover size: 45 sample: [(0, 3), (0, 4), (0, 5), (0, 6), (0, 7)]
validator: ok None
evaluator: True
actual_pose_cells_first_last: (0, 0) (2, 2)
```

**建议 fix**

在 F7 validator 的 group/template check 后、CoverSet recompute 前，新增 `facility_cells ↔ candidate_placements[facility_type][pose_id].occupied_cells` 的 exact match 检查。缺 `candidate_placements`、找不到 pose、cells 不同都 fail-closed 为 `unsound`。补回归测试：真实 pose 在 `(0,0)`，cert 写 `(30,30)`，validator 必须拒绝。

**是否需 defer**

不应 defer。Phase 1.2 close 前立刻修；否则 cut framework 的 FP=0 不成立。


## Finding 2 — F8 `power_grid_reach` 同样没有绑定 cert cells 到真实 pose，可 false-positive 禁掉可连通 pose

**severity**: BLOCKER

**file:line**

- `/_phase1_2_pkg_v12/project/src/cuts/families/power_grid_reach.py:107-132`
- `/_phase1_2_pkg_v12/project/src/cuts/families/power_grid_reach.py:279-331`
- `/_phase1_2_pkg_v12/project/src/cuts/families/power_grid_reach.py:623-628`
- `/_phase1_2_pkg_v12/project/src/cuts/families/power_grid_reach.py:694-729`

**问题陈述**

F8 validator 也只验证 `facility_group`、`facility_pose_id`、needs_power 和 cert cells 的格式，没有把 cert cells 反查到真实 `candidate_placements`。  
可构造实际 pose 在左侧、protocol core 同侧且 power graph 可达；cert 却把同一个 `pose_id` 的 footprint 写到 ghost 另一侧，validator 会证明“假 footprint 到 protocol core 不连通”，evaluator 随后对真实选中 pose 返回 True。  
结果是 geometric F8 cut 会禁掉一个实际不该禁的 pose。

**reproduce 步骤**

```bash
cd _phase1_2_pkg_v12/project
. .venv/bin/activate
python - <<'PY'
from src.tests.cuts.test_family_power_grid_reach import _f5_fixture_state, _make_cert, _make_cut
from src.cuts.families.power_grid_reach import validate_power_grid_reach, evaluate_geometric_power_grid_reach, _build_full_free_mask, _protocol_core_cells
from src.cuts.helpers.power_cover import compute_cover_set, enumerate_valid_pole_anchors
from src.cuts.helpers.power_network import build_power_network, bfs_component

state = _f5_fixture_state(
    ghost_rect=(30,0,10,70),
    facility_anchor=(0,0),
    pc_anchor=(10,10),
    selected_poses=["p_3x3_a"],
)

actual_cells = tuple(tuple(c) for c in state.candidate_placements["facility_pools"]["manufacturing_3x3"][0]["occupied_cells"])
pc = (10,10)
free = _build_full_free_mask(state, actual_cells, pc)
cover = compute_cover_set(actual_cells, free, 5.0)
all_poles = enumerate_valid_pole_anchors(free)
graph = build_power_network(list(all_poles), 5.0, pc_cells=_protocol_core_cells(pc), ghost_rect=state.ghost_rect)
pc_comp = bfs_component(graph, pc)

print("actual cover size", len(cover), "reachable overlap", len(cover & pc_comp), "sample", sorted(cover & pc_comp)[:5])

cert_payload = _make_cert(state, facility_anchor=(60,60), protocol_core_cell=[10,10])  # fake cells
cut = _make_cut(cert_payload, state)
vr = validate_power_grid_reach(cut, state, {})
print("validator", vr.kind, vr.detail)
print("evaluator", evaluate_geometric_power_grid_reach(cut, state))
PY
```

观察到：

```text
actual cover size 45 reachable overlap 45 sample [(0, 3), (0, 4), (0, 5), (0, 6), (0, 7)]
validator ok None
evaluator True
```

**建议 fix**

同 Finding 1：在 F8 validator 中，`_validate_group_and_template` 后、`_validate_disconnect_witness` 前，强制 cert `facility_cells` 与 `candidate_placements` 的真实 `occupied_cells` exact match。补回归测试：真实 footprint `(0,0)..(2,2)`，cert forged footprint `(60,60)..(62,62)`，validator 必须 `unsound`。

**是否需 defer**

不应 defer。Phase 1.2 close 前立刻修。


## Finding 3 — 多个 oracle 写入可过期的 `state.source_digest`，新生成 cut 也可能 Step 6 直接 QUARANTINE

**severity**: HIGH

**file:line**

- `/_phase1_2_pkg_v12/project/src/cuts/lifecycle.py:438-444`
- `/_phase1_2_pkg_v12/project/src/cuts/lifecycle.py:863-874`
- `/_phase1_2_pkg_v12/project/src/cuts/oracles/component_reach_oracle.py:168`
- `/_phase1_2_pkg_v12/project/src/cuts/oracles/cutset_oracle.py:204`
- `/_phase1_2_pkg_v12/project/src/cuts/oracles/density_envelope_oracle.py:166`
- `/_phase1_2_pkg_v12/project/src/cuts/oracles/pattern_nogood_oracle.py:259`
- `/_phase1_2_pkg_v12/project/src/cuts/oracles/power_cover_oracle.py:273`
- `/_phase1_2_pkg_v12/project/src/cuts/oracles/power_grid_reach_oracle.py:285`
- `/_phase1_2_pkg_v12/project/src/cuts/oracles/shape_packing_hall_oracle.py:221`

**问题陈述**

`compute_source_digest()` 明确说 `BState.source_digest` 只是 caller-side note/cache，不是权威 source；Step 6 也会重新 `compute_source_digest(state)` 对比。  
但 7 个 oracle 都用 `state.source_digest or compute_source_digest(state)` 写 scope，导致只要 `state.source_digest` 是旧值/人写值，刚生成的 cut 也会在同一个 state 上被 Step 6 QUARANTINE。  
这会在 Phase 1.3 真接入时表现为“oracle 能产 cut，但 attach 全丢”，属于 integration high risk。

**reproduce 步骤**

```bash
cd _phase1_2_pkg_v12/project
. .venv/bin/activate
python - <<'PY'
import os
from src.tests.cuts.test_family_power_hitting_set import _make_state
from src.cuts.oracles.power_cover_oracle import generate_power_hitting_set_cuts
from src.cuts.lifecycle import compute_source_digest, step_6_attach_scope_check

os.environ["EXACT_F7_GENERATOR_ENABLED"] = "1"

state = _make_state()
state.source_digest = "stale-human-note-not-canonical-digest"

cuts = generate_power_hitting_set_cuts(
    state,
    target_poses=[("crusher_blue_iron", "p_3x3_a")],
    pole_radius=5.0,
    iter_index=0,
)
print("cuts", len(cuts))
cut = cuts[0]
print("cut_scope_digest", cut.scope.source_digest)
print("computed_digest_prefix", compute_source_digest(state)[:16])
print("scope_eq_computed", cut.scope.source_digest == compute_source_digest(state))
print("step6", step_6_attach_scope_check(cut, state))
PY
```

观察到：

```text
cuts 1
cut_scope_digest stale-human-note-not-canonical-digest
computed_digest_prefix f33bd659ff8c2778
scope_eq_computed False
step6 QUARANTINE
```

**建议 fix**

所有 oracle scope 里都改为 `source_digest = compute_source_digest(state)`。`state.source_digest` 可以保留作 debug/cache 字段，但不能写入 cut scope。补一个 oracle scope digest 回归测试：即使 `state.source_digest` 被设置为 stale 字符串，生成 cut 的 scope 也必须等于 `compute_source_digest(state)`。

**是否需 defer**

不应 defer。改动小，但会直接影响 Phase 1.3 generator → attach 真实链路。


## Finding 4 — F8 图构建存在 all-pairs 热点，单个“connected large radius”测试约 28s，full cuts suite 在本环境 300s 未结束

**severity**: MEDIUM

**file:line**

- `/_phase1_2_pkg_v12/project/src/cuts/helpers/power_network.py:112-140`
- `/_phase1_2_pkg_v12/project/src/tests/cuts/test_family_power_grid_reach.py:278-294`
- `/_phase1_2_pkg_v12/project/README.md:14`
- `/_phase1_2_pkg_v12/project/README.md:72-74`

**问题陈述**

`_pole_pole_edges()` 是所有 pole anchor 两两枚举，再用半径 cutoff 过滤；测试 `test_generator_no_cut_when_connected` 在 70×70 grid 上用 `pole_jump_radius=50.0`，cutoff 很大，基本把 all-pairs 路径打穿。  
在我复现环境中，这一个测试通过但耗时 28.17s；`python -m pytest src/tests/cuts -q` 在 300s 工具超时内未给出最终 summary，卡点在 F8 generator 测试附近。  
这不直接证明 soundness 错，但会让 “395 pass” close evidence 变得难复验，也提示 prod-scale graph path 需要更清晰的半径/规模约束。

**reproduce 步骤**

```bash
cd _phase1_2_pkg_v12/project
. .venv/bin/activate

python -m pytest src/tests/cuts/test_family_power_grid_reach.py::test_generator_no_cut_when_connected -q
# 观察：1 passed in 28.17s

timeout 300s python -m pytest src/tests/cuts -q
# 观察：本环境 300s 内无最终 summary；之前 verbose run 还在 F8 generator 附近
```

**建议 fix**

短期：把这个测试拆成“功能正确性”和“压力性能”两类；功能测试不要用 R=50 这种会打穿 all-pairs 的半径。  
中期：`build_power_network` 用 spatial bucket / grid-neighborhood / DSU，只枚举半径内候选，避免 `O(n^2)` 对大半径直接爆。  
门禁：按 PROJECT_LOCK 的 RSS 要求，加一个 psutil RSS + wall time 的 F8 microbench，不要只写“pass”。

**是否需 defer**

可 defer 到 Phase 1.3，但不要 defer 到 1.5+；F8 真接入 master 前需要处理。


## Finding 5 — Mini Step 8 spike 是 API sanity check，不足以支持 prod-scale “integration path clear” 结论

**severity**: HIGH

**file:line**

- `/_phase1_2_pkg_v12/project/docs/research/p1_2b_mini_step_8_spike_20260525/spike_translator.py:19-23`
- `/_phase1_2_pkg_v12/project/docs/research/p1_2b_mini_step_8_spike_20260525/spike_translator.py:39-65`
- `/_phase1_2_pkg_v12/project/docs/research/p1_2b_mini_step_8_spike_20260525/spike_translator.py:169-213`
- `/_phase1_2_pkg_v12/project/docs/research/p1_2b_mini_step_8_spike_20260525/verdict.md:5-7`
- `/_phase1_2_pkg_v12/project/docs/research/p1_2b_mini_step_8_spike_20260525/verdict.md:29-40`
- `/_phase1_2_pkg_v12/project/docs/research/p1_2b_mini_step_8_spike_20260525/verdict.md:50-55`
- `/_phase1_2_pkg_v12/project/docs/research/p1_2b_mini_step_8_spike_20260525/verdict.md:88-92`

**问题陈述**

这个 spike 只建了 10 groups × 5 poses = 50 BoolVar 的 toy master，synthetic cuts 也不是从真实 cert / validator / cut store replay 出来。  
verdict 里把 10K cuts 的 114ms build / 2ms solve 外推到 prod “约 50× = 5–6s”，但这里没有测 prod pose universe、constraint proto 大小、RSS、真实 cut body size、active cut filter、store rotation，也没有测 realistic feasible solve；而 1K/10K synthetic case 直接 INFEASIBLE，solve cost 更不能代表真实迭代。  
因此它可以作为 “CP-SAT API 形状没卡死” 的证据，但不能作为 Phase 1.3A 真 master integration path clear 的 close gate。

**reproduce 步骤**

```bash
cd _phase1_2_pkg_v12/project
. .venv/bin/activate
python docs/research/p1_2b_mini_step_8_spike_20260525/spike_translator.py
```

再对照源码常量：

```text
NUM_GROUPS = 10
POSES_PER_GROUP = 5
# 50 BoolVar toy master
```

以及 verdict：

```text
10,000 cuts: Build 0.114s, Solve 0.002s, Status INFEASIBLE
Toy master is 50 BoolVar, not production 266 instances × ~280K pose registry.
```

**建议 fix**

把当前 Mini Step 8 verdict 改名/改口径为 “API translator sanity check”。Phase 1.3A 前新增 prod-shaped spike：

1. 用真实或等价规模的 group/pose registry 建 master var。
2. 用每个 family 的真实 cut body size 分布生成约束，不只 1/3/5/6 literal toy cuts。
3. 测 build wall、`model.Proto().ByteSize()`、psutil RSS、solve/presolve wall。
4. 加 active cut filter / rotation 阈值，至少测 10K/50K/100K active cuts。
5. 另外测一组 feasible realistic case，避免 INFEASIBLE 早停掩盖 solve 成本。

**是否需 defer**

不要 defer 到 1.5+。应作为 Phase 1.3A 的进入/close gate。


## Finding 6 — Phase 1.3 plan 中 Step 8 行号已经 stale

**severity**: LOW

**file:line**

- `/_phase1_2_pkg_v12/project/docs/项目说明/09_phase_1_3_plan.md:35-36`
- `/_phase1_2_pkg_v12/project/src/cuts/lifecycle.py:1005-1010`

**问题陈述**

Phase 1.3 plan 写 “当前 `lifecycle.py:743-751` NotImplementedError”，但实际 `step_8_apply_to_master` 在 `lifecycle.py:1005-1010`。  
这不是 soundness 问题，但 Phase 1.3A 接入时会让 reviewer / implementer 跳错位置。  
顺手修掉即可。

**reproduce 步骤**

```bash
cd _phase1_2_pkg_v12/project
grep -n "step_8_apply_to_master\|NotImplementedError" docs/项目说明/09_phase_1_3_plan.md src/cuts/lifecycle.py
```

**建议 fix**

把 plan 中 `lifecycle.py:743-751` 改成 `lifecycle.py:1005-1010`，或更稳妥地写函数名 `src/cuts/lifecycle.py::step_8_apply_to_master`，避免之后行号再 drift。

**是否需 defer**

立刻修文档；不影响 Phase 1.2 close 的技术判断。


## 补丁说明

本包内 `patches/0001-bind-power-family-pose-cells-and-digest.py` 是一个可应用的最小修复脚本，覆盖：

- F7/F8 validator 增加 `facility_cells` 与真实 pose registry 的 exact match；
- 7 个 oracle 的 `source_digest` 改为强制 `compute_source_digest(state)`；
- 添加 3 个回归测试。

应用方式：

```bash
cd _phase1_2_pkg_v12/project
python /path/to/patches/0001-bind-power-family-pose-cells-and-digest.py
python -m pytest \
  src/tests/cuts/test_family_power_hitting_set.py::test_validator_unsound_when_facility_cells_do_not_match_pose_registry \
  src/tests/cuts/test_family_power_grid_reach.py::test_validator_unsound_when_facility_cells_do_not_match_pose_registry \
  src/tests/cuts/test_oracle_scope_digest.py -q
```

我在本地打补丁后跑过这 3 个 target test：`3 passed in 4.28s`。

## Phase 1.2 段 overall 看法

**不建议按当前包 close Phase 1.2。**  
一句话理由：F7/F8 两个 cut family 都能构造 false-positive validator 通过案例，已经破坏 FP=0；再加上 source_digest 生成/回放链路会让 Phase 1.3 真接入时出现“刚生成就 quarantine”的集成故障。
