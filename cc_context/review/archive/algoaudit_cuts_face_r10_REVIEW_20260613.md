# 终末地 IndustrialPlanner cuts 面 round 10 review

快照校验：`/mnt/data/zmd_snapshot_2cd169b4.zip` sha256 = `2cd169b46a12cc1e52e1915d89279be48fc0f6adbd02b1530d0994d18d1879eb`，与指定值一致后才解包审查。

结论：CUT-R9-H1 主修复在当前 production `benders_loop` 调用路径上确认 sound，未发现 HIGH/MEDIUM production-reachable soundness finding。自由攻击角发现 1 个 LOW 级 separator API fail-closed 合同缺口，已附 unified diff 与回归测试；该缺口未证明可经当前 `PortBindingModel.extract_port_specs()` + 实际 master delegate 形成 production over-cut，但它违反了 r9 补丁宣称的“无主 port spec fail-closed”边界，建议合入。

## Finding CUT-R10-L1: D2 port owner 校验把 `None` 字符串化，且不校验 owner 是否属于当前 placement

Severity: LOW，fail-closed contract hardening；当前 production 路径未证明可达 over-cut。

File: original `src/search/d2_separator.py:219`。

原代码只做：

```python
if any(not str(ps.get("instance_id", "")) for ps in port_specs):
    ... reason="unowned_port_spec_not_certified_for_d2_cut"
```

这会把 `instance_id=None` 变成字符串 `"None"`，视为有主端口；同时，非空但不属于 `placement_solution` 的 owner 也不会被拒绝。随后 `_build_pose_assumptions_for_owners_with_ports()` 会为该 synthetic owner 构造 `D2PoseAssumption(instance_id="None", pose_idx=-1, ...)`，support-augmented conflict set 也会把 `"None": -1` 纳入。若 delegate 是宽松的 `add_benders_cut`，separator 可在未认证端口 owner 的上下文下写 cut。

Repro probe，在原始快照上可复现：

```python
from src.tests.test_d2_separator_support_context import _toy_corridor_case, _RecordingMasterDelegate
from src.search.d2_separator import run_d2_separation

placement, pools, ports = _toy_corridor_case(blocked=True)
ports = [dict(p) for p in ports]
ports[0]["instance_id"] = None
m = _RecordingMasterDelegate()
r = run_d2_separation(
    master_delegate=m,
    placement_solution=placement,
    facility_pools=pools,
    port_specs=ports,
    time_limit=5.0,
)
print(r.cut_added, r.d2_status, r.cut_metadata.get("support_owners"), m.conflicts)
```

Observed before patch:

```text
True INFEASIBLE ['None', 'sink', 'src', 'wall'] [{'None': -1, 'sink': 0, 'src': 0, 'wall': 0}]
```

Impact analysis: 当前 benders production path 的 `PortBindingModel.extract_port_specs()` 从 placement/binding slots 生成 string owner，且实际 `PoseBoolExactMasterDelegate.add_benders_cut()` / coordinate delegate 对未知 owner 或 pose `-1` 会拒绝，因此我没有把它升级为 production-reachable soundness finding。但 D2 separator 自身合同应 fail-closed，不应依赖 master delegate 二次兜底。

Fix: 新增 `_d2_port_owner_validation_error()`，在 precheck 与 D2 model build 前拒绝 `None`、空白 owner、`ghost_pick` owner，以及不在当前 placement 的 owner。新增两个回归：`None` owner 和 missing owner 都返回 `ERROR`，且 delegate 不收到 conflict。

Patch: `/mnt/data/cut_r10_d2_owner_validation.patch`。

## Q1.1 precheck gate 语义对齐

production caller 在 `src/search/benders_loop.py:5282-5286` 首选同一个 `run_exact_routing_precheck()`，参数为 `placement_core=routing_placement_core`、`port_specs=port_specs`、`occupied_owner_by_cell=occupied_owner_by_cell`；fallback 路径在 `src/search/benders_loop.py:5291-5296` 用 `RoutingGrid` 形态。D2 separator 在 `src/search/d2_separator.py:220-223`，也调用同一个 `run_exact_routing_precheck()`，只是用简化的 `RoutingGrid(set(occupied), port_specs)`。

`run_exact_routing_precheck()` 是 `analyze_exact_routing_domain()` 的薄 wrapper，当前 precheck 可返回的 status 集合为：

- `front_blocked`: duplicate terminal front key fail-closed 分支，`src/models/routing_subproblem.py:398-417`；或 front cell out-of-grid / not free 分支，`src/models/routing_subproblem.py:424-494`。
- `relaxed_disconnected`: terminal-bearing component 缺少 counterpart，`src/models/routing_subproblem.py:531-612`。
- `feasible`: 所有 precheck 通过，`src/models/routing_subproblem.py:614-630`。

D2 gate 只放行 `front_blocked` / `relaxed_disconnected`，其余任何 status 都走 `MODEL_INVALID`，`src/search/d2_separator.py:278-293`。因此当前集合无遗漏；未来若 precheck 增加新 status，`not in {front_blocked, relaxed_disconnected}` 也会 deny-unknown。

我额外跑了 4 个小 probe，对比 separator 简化调用、production `placement_core` 调用、带 owner map 的 `RoutingGrid` 调用、`RoutingGrid.from_placement_core()` 调用，覆盖 `feasible`、front-cell blocked、duplicate-front-key blocked、`relaxed_disconnected`。四种调用形态 status 完全一致：

```text
feasible: ['feasible', 'feasible', 'feasible', 'feasible']
front_blocked: ['front_blocked', 'front_blocked', 'front_blocked', 'front_blocked']
duplicate_front_key: ['front_blocked', 'front_blocked', 'front_blocked', 'front_blocked']
relaxed_disconnected: ['relaxed_disconnected', 'relaxed_disconnected', 'relaxed_disconnected', 'relaxed_disconnected']
```

差异点：separator 不传 `occupied_owner_by_cell`，所以 `blocked_ports[*].blocking_instance_ids` / `placement_level_conflict_set` 的诊断 owner 可能更少；但 `status` 判定只依赖 front cell 是否在 `resolved_free_cells` 与 free-component 结构，owner map 不参与可达性。D2 cut 本身又并入全 occupancy support，因此该诊断差异不构成 proof 差异。

## Q1.2 口径单调性三问

(a) `front_blocked`：核心判定在 `src/models/routing_subproblem.py:433-435`，front cell 不在 grid 或不在 `resolved_free_cells` 即 blocked。若 separator occupied ⊆ production occupied，并且 separator 都判 front blocked，则 production 加更多障碍不可能把同一 front cell 变 free；duplicate-terminal-front-key 分支也与障碍无关，保持 blocked。若是 out-of-grid，同样与障碍无关。

(b) `relaxed_disconnected`：连通性只在 free-cell 图上求 component，见 `src/models/routing_subproblem.py:496-612`。增加 occupied cell 只会删除 free vertex / edge 并切分 component，不会把 source-only component 与 sink-only component 合并。因此 separator 在障碍更少时已经发现 terminal-bearing component 缺 counterpart，则 production 障碍更多时只会保持 disconnected 或升级成 `front_blocked`，不会变成 precheck-feasible。

(c) occupied 口径：production `_extract_occupied_cells()` / `_extract_occupied_owner_by_cell()` 在 `src/search/benders_loop.py:6025-6055` 显式跳过 `ghost_pick` 并从 `facility_pools[facility_type][pose_idx]["occupied_cells"]` 取格子。separator `_placement_to_occupied()` 在 `src/search/d2_separator.py:51-69` 同样跳过 `ghost_pick` 并读取同一 `occupied_cells` 字段。对 master 产生的合法 solution，二者相等；separator 对非法 pool/pose 更宽容时最多少算障碍，配合 (a)(b) 的单调方向仍安全。补丁又把端口 owner 缺失/不在 placement 的情况提前 fail-closed，避免 synthetic owner 进入 proof context。

## Q1.3 ladder 位置前提与 cut 弱化方向

`benders_loop.py` 的 precheck safe-reject ladder 在 `src/search/benders_loop.py:5328-5382`：当 `binding_selection_safe_reject=True`、status 是 `front_blocked` / `relaxed_disconnected` 且 binding 仍有 alternative 时，只添加 binding-level nogood 并重解 binding；`FEASIBLE` 则继续下一 binding，`INFEASIBLE` 才退出 alternatives 枚举。

D2 rung 位于后面的 `front_blocked` branch，`src/search/benders_loop.py:5384-5448`。也就是说，当前 production D2 只会在 safe-reject ladder 没有接管时到达；真实 precheck 对 `front_blocked`/`relaxed_disconnected` 都返回 `binding_selection_safe_reject=True`，所以这等价于没有 binding alternatives 的固定 binding 情况。当前代码并不在 `relaxed_disconnected` branch 调 D2；该 branch 仍只做 binding alternative 枚举，`src/search/benders_loop.py:5706-5744`。

弱化方向也正确：fallback front-blocked nogood 使用 blocked port 的 `placement_level_conflict_set`，`src/search/benders_loop.py:5610-5637`；D2 conflict set 则并入所有 port owners、所有 occupancy contributors 和 raw core，`src/search/d2_separator.py:126-152`。support tuple 是 fallback tuple 的超集，master no-good 需要更多 literals 同时成立才触发，因此只会更弱，不会更强。

## Q1.4 `MODEL_INVALID` 状态机消费

D2 separator 对非放行 precheck status 返回 `cut_added=False, d2_status="MODEL_INVALID"`，且不建 D2 模型、不写 cut，`src/search/d2_separator.py:278-293`。benders caller 只看 `d2_result.cut_added`：只有 true 才设置 `_b1_d2_skip_other_cuts=True` 并计数，`src/search/benders_loop.py:5438-5442`；否则继续进入 PCR/deletion/lazy/cell/fallback ladder，`src/search/benders_loop.py:5448-5681`。因此 `MODEL_INVALID` 没有被误读为证明性结论。

## 自由攻击角

选点 1：r9 新增的 unowned port 判定。原因是这是 gate 之前的 proof-context 入口，且 prompt 明确提到“无主 port spec fail-closed”。攻击发现 CUT-R10-L1，补丁已附。

选点 2：r8+r9 叠加后的 D2 support-augmented cut 链路。复查 `_build_d2_supported_conflict_set()`：它先纳入所有 port owner assumptions，再纳入 `_build_occupancy_support_pose_terms()` 返回的所有 selected footprint contributors，最后并入 raw core，`src/search/d2_separator.py:126-152`；`ghost_pick` 在 support 与 occupied 构造中均被排除，`src/search/d2_separator.py:56-68`、`src/search/d2_separator.py:107-123`。桥 crossing 与 splitter 两个 r9 回归仍表现为 production precheck=`feasible`、production routing=`FEASIBLE`、raw D2=`INFEASIBLE`、separator=`MODEL_INVALID`，未写 cut。

## Regression / validation

已运行：

```text
PYTHONPATH=. pytest -q -p no:randomly src/tests/test_d2_separator_support_context.py
# 6 passed in 1.65s

PYTHONPATH=. pytest -q -p no:randomly \
  src/tests/test_d2_separator_support_context.py \
  src/tests/test_exact_contract.py::test_relaxed_disconnected_only_rejects_binding_selection_without_persisted_cut \
  src/tests/test_exact_contract.py::test_routing_front_blocked_unencodable_optional_conflict_fails_closed \
  src/tests/test_patch_routing_core.py \
  src/tests/test_benders_cut_condition_lits.py \
  src/tests/test_master_cut_solution_invalidation.py
# 30 passed in 6.36s

ruff check src/search/d2_separator.py src/tests/test_d2_separator_support_context.py
# All checks passed!

PYTHONPATH=. python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

全量 `PYTHONPATH=. pytest -q -p no:randomly src/tests` 尝试过，但沙盒命令超时，停止在约 6% 进度，超时前未见 failure。因此全量绿未能在本轮环境内确认。
