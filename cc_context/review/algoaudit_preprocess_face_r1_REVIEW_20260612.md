# IndustrialPlanner preprocess 链 certified 根基审查

审查对象：`src/placement/placement_generator.py`、`src/preprocess/demand_solver.py`、`src/preprocess/instance_builder.py`、`src/preprocess/operation_profiles.py`、`scripts/build_current_preprocess_context.py`、`src/interchange/preprocess_context.py`，以及 `rules/canonical_rules.json` / `rules/preprocess_plan.json` 与冻结 `data/preprocessed/*` artifact 的契约。

结论：**本轮非零 soundness finding**。我确认了 2 个候选摆位生成层缺陷，其中 1 个是 P0 级规则错编码，另 1 个是候选合法性过滤错误。需求数学、266 强制实例生成、冻结非候选 artifact 对账未发现新的 soundness finding。

## 实跑环境与基线

- 项目包 sha256：`324156a68d340c651c334f23220e9b6554f433b4fb5dec6bba3924c8a3d769a7`，已验证。
- 解包目录：`/mnt/data/zmd_review/project`。
- 依赖：使用 project wheels 离线安装到 Python 3.13 环境。
- `python scripts/build_current_preprocess_context.py --output ... --diff-json ... --diff-md ...`
  - `all_match: True`
  - `matched_count: 6/6`
  - `mandatory_exact_instance_count: 266`
  - `all_instance_count: 326`
  - `generic_output_slots: 52`
- `python scripts/check_p1_2_proof_obligations.py`：`P1.2 proof obligation check passed: 8 obligations anchored`。
- `python -m pytest -q -p no:randomly src/tests/test_p0_certified_soundness_fixes.py`：`12 passed`。
- 新增补丁回归：`python -m pytest -q -p no:randomly src/tests/test_preprocess_candidate_geometry_contract.py src/tests/test_p0_certified_soundness_fixes.py`：`16 passed`。
- `pytest-randomly` 在本沙盒会触发第三方 numpy/thinc seed 初始化错误；上述 pytest 结果均用 `-p no:randomly` 排除该环境性噪声。

## Finding F-01 — P0：`protocol_storage_box` 的 `omni_wireless` 被错误枚举成普通 3×3 实体端口机器

**位置**

- `src/placement/placement_generator.py:199-205`
- `src/placement/placement_generator.py:308-310` 调度分支注释写着“无线终端，不生成端口”，但实际调用的 `gen_protocol_storage_box()` 返回 `gen_square_manufacturing(3)`。
- `rules/canonical_rules.json` 中 `protocol_storage_box.port_rule == "omni_wireless"`。

**实证 probe**

现场对当前未补丁代码运行：

```text
protocol_storage_box 17952 first p_x00_y01_o0_m_TB ports 3 3
protocol_storage_box_physical_port_poses: 17952
  sample ('protocol_storage_box', 0, 'p_x00_y01_o0_m_TB', 3, 3)
```

更细的锚点检查：当前池中 `protocol_storage_box` 有 17,952 个 pose、4,620 个唯一 anchor；若按 `omni_wireless` 语义，它应是无物理端口的 3×3 占格，完整 anchor 域为 `68 * 68 = 4,624`。当前实现还因为错误继承端口面壁过滤，漏掉 4 个无线协议箱本应合法的角点 anchor：`(0,0)`, `(0,67)`, `(67,0)`, `(67,67)`。

当前生成出的 compact 候选 artifact hash 为：

```text
candidate_compact_sha256: d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f
candidate_compact_bytes: 53594995
```

这与 `PROJECT_LOCK.md` / `specs/06` 中记录的外置 `candidate_placements.json` hash 一致，说明冻结候选 artifact 若按该 hash 恢复，也带着这个错编码。

**影响**

这是 P0，因为 certified 证明吃到的是错误世界：

1. 错编码：`omni_wireless` 模板被赋予实体输入/输出端口，binding/routing 会把无线协议箱当作实体接驳点消费。
2. 漏枚举：无线箱不应受端口方向与边界死锁过滤；当前错误继承过滤导致合法 corner anchors 缺失。
3. 重复/伪模式：同一个无线占格 anchor 被扩展成 `TB/BT/RL/LR` 四类物理端口模式，这不是 canonical `omni_wireless` 的合法 pose 空间。

**修法**

补丁把 `gen_protocol_storage_box()` 改成：

- 固定 3×3 本体占格；
- 固定 `orientation=0`, `port_mode='omni'`；
- 全域 `x,y ∈ [0,67]`；
- `input_port_cells=[]`, `output_port_cells=[]`；
- 不影响 `needs_power`、占格、可选实例构建。

补丁后 probe：

```text
protocol_storage_box: 4624
generic geometry_errors: 0
protocol_storage_box_physical_port_poses: 0
candidate_compact_sha256: adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
candidate_compact_bytes: 45773799
```

**下游契约备注**

当前 `src/models/binding_subproblem.py:516-543` 对 `wireless_sink` 的 generic input slots 是从 `pose["input_port_cells"]` 生成的。上游修正为无端口后，带正 `required_generic_inputs` 的 exact 路径会 fail closed，而不是继续伪造物理 sink。要恢复完整生产可行性，后续必须明确建模无线 sink 的 routing-free 消费语义，或者在规范层撤销 `omni_wireless 不生成端口`。我没有在本补丁中用“合成假端口”绕过这个问题，因为那会把同一个 P0 以更隐蔽的形式搬到 binding/routing 侧。

## Finding F-02 — P1：面壁死锁过滤检查的是 port cell，而不是 routing 实际使用的 front cell

**位置**

- `src/placement/placement_generator.py:65-77`
- routing 消费语义在 `src/models/routing_subproblem.py:944-970` 与 `src/models/routing_binding_context.py:86-146`：`front = port + DIR_DELTA[dir]`，front 不在网格内则该端口不可用/路由直接失败。

**实证 probe**

当前未补丁生成池中，端口本身在网格内但 routing front 已经越界的 active ports 共有 11,424 个，涉及 2,608 个 pose：

```text
front_oog_ports: 11424
  manufacturing_3x3: 1632
  manufacturing_5x5: 2640
  manufacturing_6x4: 3120
  protocol_core: 2400
  protocol_storage_box: 1632
  sample ('manufacturing_3x3', 0, 'p_x00_y01_o0_m_TB', 'output_port_cells', (0, 0, 'S'), (0, -1))
  sample ('manufacturing_3x3', 130, 'p_x00_y66_o0_m_TB', 'input_port_cells', (0, 69, 'N'), (0, 70))
```

例子 `p_x00_y01_o0_m_TB` 的 bottom output port 是 `(0,0,S)`。旧 `is_edge_starved()` 只看 port cell `(0,0)`，判为可用；但 routing 真正铺带的 first cell 是 `(0,-1)`，必然越界。

**影响**

这不是“routing 侧二次偏移”问题；routing 侧已按 `front = port + dir` 消费，问题在 preprocess 侧把 port cell 当作可铺带 front 来过滤。当前 exact routing 会 fail closed，所以我没有把它判成当前可直接产生 false `CERTIFIED` 的 P0；但候选池“合法 pose”契约已经被污染，master/binding 会花时间选择下游必败的 pose，证据重放若只信候选池合法性也会被误导。

**修法**

补丁新增 `get_port_front_cell()`，并把 `is_edge_starved()` 改为检查所有 active ports 的 routing front 是否出界，而不是检查 port cell 本身。

补丁后的解析计数闭式为：

```text
manufacturing_3x3       4 * 68 * 64 = 17408
manufacturing_5x5       4 * 66 * 62 = 16368
manufacturing_6x4       4 * 65 * 63 = 16380
protocol_core           2 * 58 * 58 = 6728
protocol_storage_box    68 * 68     = 4624
power_pole              69 * 69     = 4761
boundary_storage_port   2 * 67      = 134
total                                  66403
```

补丁后不变量：

```text
geometry_errors: 0
front_oog_ports: 0
protocol_storage_box_physical_port_poses: 0
```

## 已审并未报 finding 的面

### `get_occupied_cells` 与旋转 footprint

`get_occupied_cells(x,y,w,h)` 使用闭区间语义 `x..x+w-1`, `y..y+h-1`，与 02 章“旋转后绝对包围盒左下角锚定法”一致。6×4 的 `o=0` 用 6×4，`o=1` 用 4×6；下游 master 也从真实 `occupied_cells` 推导 footprint，而不是只信模板默认尺寸。现场不变量确认所有 occupied cells 在 70×70 内、无重复、矩形 cell 数等于 bbox 面积。

### 四边端口坐标与外向法向

`get_edge_ports()` 的 top/bottom/left/right 坐标本身符合本轮约定：top `y+h,N`，bottom `y-1,S`，left `x-1,W`，right `x+w,E`。补丁后新增测试确认所有实体端口都位于本体 bbox 外一格，且方向背离本体。

### 供电覆盖

当前 canonical `power_pole.power_coverage_radius == 5`，生成器覆盖域为 `x-5..x+6`、`y-5..y+6` 并裁剪到 `[0,69]`，与 2×2 中心向外 5 格的 12×12 语义一致；覆盖域包含本体占格。这里没有当前 soundness finding。注意它仍是 hard-coded radius 5；若以后 canonical 改半径，需要把 `gen_power_pole()` 参数化，当前快照不构成缺陷。

### 边界口 `[1,66]` 文档差异

`specs/06` 的文字写 `[1,66]`，代码和冻结 artifact 生成 134 个边界口，即左边 `y=1..67`、底边 `x=1..67`。我没有把它作为 soundness finding：`y=67` 的 1×3 左边界口占格为 `(0,67..69)`，端口 `(1,68,E)`，front `(2,68)` 在网格内；底边 `x=67` 同理合法。该差异更像 specs/06 文字陈旧，且冻结 artifact/代码/几何不变量一致。

### 需求与实例构建

`solve_demands_exact()` 采用 `Fraction` 做需求回推和环组线性方程，`generate_ceil_machine_counts()` 对正的小数机数向上取整，没有发现少算。当前 fractional → integer 关键值：

```text
crusher_buckwheat 11/2 -> 6
crusher_sandleaf 21/2 -> 11
filling_capsule 11/4 -> 3
molding_bottle 11/2 -> 6
seed_collector_buckwheat 11/2 -> 6
seed_collector_sandleaf 21/2 -> 11
sum ceil machine_counts = 219
```

`mandatory_exact_instances.json` 对账：219 制造设施 + 1 protocol_core + 46 boundary_storage_port = 266；全部 `bound_type='exact'` 且 `solve_modes=['certified_exact','exploratory']`。`build_current_preprocess_context.py` 重新生成的 6 个非候选冻结 artifact 全部 MATCH。

`generate_generic_io_requirements()` 当前全局池化输出为：

```json
required_generic_outputs = {"blue_iron_ore": 34, "source_ore": 18}
required_generic_inputs = {"qiaoyu_capsule": 1, "valley_battery": 1}
```

这与 52 口预算和最终产品 sink 需求一致；未发现 per-line/全局池错位的新 finding。唯一的相关缺口是 F-01 的无线 sink 几何与 binding 物理端口消费语义冲突。

## 补丁内容

补丁文件：`preprocess_certified_review.patch`

变更摘要：

1. `src/placement/placement_generator.py`
   - 新增 `DIR_DELTA` 与 `get_port_front_cell()`。
   - `is_edge_starved()` 改为检查 routing front 是否出界。
   - `gen_protocol_storage_box()` 改为 `omni_wireless` 无端口全 anchor 枚举。
2. `src/tests/test_preprocess_candidate_geometry_contract.py`
   - 新增协议箱无物理端口/full anchor 域测试。
   - 新增所有实体端口 front 必在 grid 内测试。
   - 新增端口外一格且法向背离本体测试。
   - 新增池规模闭式计数测试。

## 补丁后关键输出

```text
pool_counts
  boundary_storage_port: 134
  manufacturing_3x3: 17408
  manufacturing_5x5: 16368
  manufacturing_6x4: 16380
  power_pole: 4761
  protocol_core: 6728
  protocol_storage_box: 4624
total: 66403
geometry_errors: 0
front_oog_ports: 0
protocol_storage_box_physical_port_poses: 0
candidate_compact_sha256: adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
candidate_compact_bytes: 45773799
```

## 复现命令

```bash
# 当前缺陷 probe，未补丁树
PYTHONPATH=. python /mnt/data/zmd_review/probe_current_preprocess_invariants.py

# 补丁后回归
python -m pytest -q -p no:randomly src/tests/test_preprocess_candidate_geometry_contract.py
python -m pytest -q -p no:randomly src/tests/test_preprocess_candidate_geometry_contract.py src/tests/test_p0_certified_soundness_fixes.py
python -m pytest -q -p no:randomly src/tests/test_operation_profiles.py
python scripts/check_p1_2_proof_obligations.py

# 非候选冻结 artifact 对账
python scripts/build_current_preprocess_context.py \
  --output /mnt/data/zmd_review/current_preprocess_context.json \
  --diff-json /mnt/data/zmd_review/current_preprocess_diff.json \
  --diff-md /mnt/data/zmd_review/current_preprocess_diff.md
```
