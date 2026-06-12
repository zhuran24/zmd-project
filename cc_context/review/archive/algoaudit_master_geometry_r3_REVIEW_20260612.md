# IndustrialPlanner 几何 master round 3 审查报告

审查对象：`zmd_gm_r3_snapshot_b377a2a7.zip`  
SHA256：`b377a2a75e67697a38b2e46f8dc1407677a1f9936406b51695a7094487524531`  
校验结果：通过。只基于该快照解包后的 `project/` 审查。

审查范围按本轮定义收敛到几何 master：`src/models/exact_coordinate_master.py`、`src/models/master_model.py` 的几何侧，以及必要的专项测试。未重审 binding、routing、cuts、preprocess、campaign、scheduler 等其它面。

## 结论

本轮发现 1 个 soundness/completeness finding，已给出补丁和回归测试：

- **F-GM-Q3-01-R3-A，高危，false-INFEASIBLE**：r2 修复只覆盖了 `fixed_required_count >= lower_bound`，但当 `0 < fixed_required_count < lower_bound` 时，coordinate delegate 仍会因为“已有 fixed required optional 槽”而完全跳过 residual protocol storage 槽池，最终把合法配置编码成 `0 >= shortfall`。

修复后，Q1 的剩余攻击面、Q2 对称破除保真、Q3 ghost 锚点域完备性未发现额外 soundness finding。

## Finding F-GM-Q3-01-R3-A：fixed 槽不足下界时 residual protocol 池被跳过

**Severity**：High / soundness-completeness，false-INFEASIBLE。  
**位置**：

- 原快照 `src/models/exact_coordinate_master.py:1956-1961`：准备 residual protocol signature buckets 时，只要 `_exact_required_pose_optional_counts[tpl] > 0` 就跳过。
- 原快照 `src/models/exact_coordinate_master.py:2277-2282`：创建 residual optional slots 时同样跳过。
- 原快照 `src/models/exact_coordinate_master.py:5967-6001`：下界编码已按 `protocol_shortfall = lower - fixed` 写，但 residual 池为空时仍落到 `Add(0 >= shortfall)`。
- 原快照 `src/models/master_model.py:5222-5229`：powered residual upper-bound 统计也把任何带 fixed required count 的非 pole optional 模板整体排除，导致修复后若只补 delegate 槽池，旁路统计仍会和实际 residual 池分裂。

**问题描述**：

F-GM-Q3-01 的 r2 修复把 lower-bound 变成“fixed required 槽作为常量贡献，residual 只负责 shortfall”。这对 `fixed_required_count >= lower_bound` 是正确的。但 residual 池构造仍沿用旧逻辑：只要该模板存在 exact required optional count，就完全不建立 residual optional 槽。于是当 `fixed_required_count` 是严格正数但小于 protocol 下界时，模型没有 residual literal 可以补足 shortfall，合法实例被硬编码为不可行。

最小反例：3×3 网格，两个合法 `protocol_storage_box` pose；generic input demand = 4，wireless slots = 3，因此 lower bound = `ceil(4/3)=2`；同时固定 required optional count = 1。语义上应选择 1 个 fixed + 1 个 residual，模型应可行。原快照输出：

```text
status INFEASIBLE
lower 2
bounds {'mode': 'required_lower_bound', 'required_generic_input_slots': 4, 'slots_per_pose': 3, 'lower': 2, 'upper': None, 'candidate_pose_count': 2, 'slot_pool_upper_bound': 0}
required_slots {'protocol_storage_box': 1}
residual_slots {}
```

**修复**：

补丁做了三件事：

1. `src/models/exact_coordinate_master.py` 新增 `_needs_residual_optional_slots_after_fixed_required(tpl)`。对 `protocol_storage_box`，只有当 `lower_bound > fixed_required_count` 时才在 fixed 槽之后继续保留 residual 槽池；其它 required optional 模板仍保持原先“fixed 槽已完全代表该模板”的语义。
2. `_residual_optional_slot_upper_bound()` 对非 power residual 池返回 `certified_optional_upper_bound - fixed_required_count`，避免 fixed 槽和 residual 槽双花同一个 upper-bound 容量。
3. `src/models/master_model.py:_residual_optional_powered_slot_upper_bounds()` 同步 residual upper-bound 口径：当 protocol fixed 槽不足 lower bound 时，powered residual 统计保留 `upper - fixed`；当 fixed 已满足 lower bound 时仍不创建 residual powered 需求。

修复后同一 probe 输出：

```text
status OPTIMAL
lower 2
bounds {'mode': 'required_lower_bound', 'required_generic_input_slots': 4, 'slots_per_pose': 3, 'lower': 2, 'upper': None, 'candidate_pose_count': 2, 'slot_pool_upper_bound': 1}
required_slots {'protocol_storage_box': 1}
residual_slots {'protocol_storage_box': 1}
powered_residual_bounds {'protocol_storage_box': 1}
```

新增回归：`src/tests/test_exact_coordinate_protocol_bounds.py:56-114`，覆盖 `fixed_required_count=1 < lower=2` 的 shortfall 场景，并断言 solver 可行、`slot_pool_upper_bound == 1`、powered residual upper-bound 为 1。

## Q1 F-GM-Q3-01 修复确认攻击面

修复后的关键口径如下：

- fixed required 槽的计数口径仍来自实际创建的 required optional slots：`len(self.required_optional_slots["protocol_storage_box"])`，下界 shortfall 编码在 `src/models/exact_coordinate_master.py:5985-6019`。槽创建源头与 master 的 `_exact_required_pose_optional_counts` 一致，修复没有引入第二套 fixed 计数来源。
- residual 槽池是否存在由同一 helper 判断：`src/models/exact_coordinate_master.py:1650-1660`。signature bucket 准备点和 slot 创建点都调用该 helper，分别在 `src/models/exact_coordinate_master.py:1974-1980` 与 `src/models/exact_coordinate_master.py:2295-2300`，避免“只修一侧”的分裂。
- lower bound 来源仍是 `ceil(required_generic_inputs / wireless_sink_generic_input_slots)`：`src/models/master_model.py:2030-2055`。generic input count 被规范化为非负整数，负数 fail-closed：`src/models/master_model.py:1961-1984`；wireless slots 也被规范化为非负整数：`src/models/master_model.py:2016-2027`。因此 lower 为负的边界不可由合法输入进入；lower 为 0 时不会添加 required lower-bound 约束。
- exact core / overlay 传递的是同一份 in-memory snapshot 数据：`generic_io_requirements`、`wireless_sink_generic_input_slots`、`exact_required_pose_optional_counts` 在 core 打包处保留，见 `src/models/master_model.py:2590-2597`；overlay 重建处直接传回构造器，见 `src/models/master_model.py:2680-2689`。
- 同型 lower-bound 编码扫描结果：coordinate delegate 内使用“required optional 数量下界 + fixed optional 常量抵扣”的点只落在 protocol storage 下界。其它 optional 计数多为 upper-bound 或 power-pole family bound，不存在同型 lower shortfall 未修兄弟。

## Q2 对称性破除与解空间保真

本轮没有发现对称破除切真解问题。

核验重点：

- 规范 `specs/07_master_placement_model.md:74-85` 要求只对“同一种类模板、且担任同种配方任务”的实例做字典序裁剪，并对 optional power pole 做瀑布式激活。
- mandatory instance 分组粒度是 `(facility_type, operation_type)`，不是仅按模板尺寸或模板名：`src/models/master_model.py:2969-2990`。因此同为 3×3 但 operation_type 不同的 crusher / packer 不会被错误互换。
- 组内成员排序按 `instance_id` 字符串排序，group key 也排序，重建时稳定：`src/models/master_model.py:2978-2980`。exact core 打包/overlay 保留 mandatory groups 与 group_id mapping：`src/models/master_model.py:2590-2602`、`src/models/master_model.py:2680-2689`。
- coordinate slot 的顺序约束落在同一 group 或同一 optional template 的匿名槽上：mandatory order-key 约束在 `src/models/exact_coordinate_master.py:2768-2794`；required optional order-key 在 `src/models/exact_coordinate_master.py:2811-2837`；residual optional 激活前缀与 order-key 在 `src/models/exact_coordinate_master.py:2929-2936`；power-pole prefix/family/order 在 `src/models/exact_coordinate_master.py:3211-3221`。
- residual optional 的“先激活低编号槽”不切掉“只有高编号杆有合法 pose”的配置：这些槽共享相同 domain；若某个高编号槽可取某 pose，可以通过交换槽标签把它放到更低编号槽。power pole family/order 也是 family 内排序，同样只裁匿名标签对称。

一个非 soundness 观察：部分 order-key / active-prefix canonicalization 在 slot 创建阶段无条件加入，而 signature 单调约束受 `enable_symmetry_breaking` 控制，见 `src/models/exact_coordinate_master.py:3386-3440`。因为这些约束仍只作用于匿名可交换槽，本轮不作为 soundness finding 报告；若 owner 期望关闭 flag 后完全无 canonicalization，可另开性能/配置语义议题。

## Q3 ghost rectangle 锚点域完备性

本轮没有发现 ghost 锚点域或 no-overlap 坐标约定问题。

核验范围与结果：

- coordinate delegate ghost 枚举使用半开坐标域：`range(self.grid_w - ghost_w + 1)` 与 `range(self.grid_h - ghost_h + 1)`，见 `src/models/exact_coordinate_master.py:3487-3502`；cells 使用 `anchor + dx/dy`，interval end 使用 `anchor + w/h`，见 `src/models/exact_coordinate_master.py:3495-3515`。这覆盖 `0 <= x <= 70-w`、`0 <= y <= 70-h`，包含贴边 anchor。
- legacy/master_model ghost 枚举也使用相同 half-open 约定：`src/models/master_model.py:4624-4649`。
- 未发现 `(w,h)` 被排序成 `w<=h` 的 master 侧假设；oriented `(2,3)` 与 `(3,2)` 被分别枚举。
- ghost no-overlap 使用 ghost interval 与 core footprint interval 一起 `AddNoOverlap2D`：`src/models/exact_coordinate_master.py:3538-3542`。core footprint interval 来自候选 pose 的 `occupied_cells`：relative occupied cells 在 `src/models/exact_coordinate_master.py:962-976`，bbox 在 `src/models/exact_coordinate_master.py:978-987`，mode token 包含 footprint key 在 `src/models/exact_coordinate_master.py:998-1004`，interval start/end 使用 selected footprint width/height 在 `src/models/exact_coordinate_master.py:2353-2476`。这保持了 r1 B-01 的 footprint-bbox 派生修复；非矩形 footprint 仍按 lock 允许的 bbox 保守 over-approx，不 under-approx。

ghost anchor probe：

```text
(2, 3) 4692 4692 (0, 0) (68, 67) True True
(3, 2) 4692 4692 (0, 0) (67, 68) True True
(70, 1) 70 70 (0, 0) (0, 69) True True
(1, 70) 70 70 (0, 0) (69, 0) True True
(70, 70) 1 1 (0, 0) (0, 0) True True
```

每行字段为：`rect, actual_anchor_count, expected_anchor_count, min_anchor, max_anchor, contains_(0,0), contains_(70-w,70-h)`。

## Q4 抽查维持

抽查 3 个 r1/r2 已修结论仍在场：

1. B-01 footprint bbox 派生仍从 `occupied_cells` 出发，而不是模板默认尺寸：`src/models/exact_coordinate_master.py:962-987`。
2. mode-channel 包含 footprint key，避免同 orientation/port_mode 但 footprint 不同的姿态被并入同一模式：`src/models/exact_coordinate_master.py:989-1004`。
3. F-GM-Q3-01 fixed 槽已满足下界的旧回归仍通过；新增 shortfall 回归也通过。

## 自验命令与结果

依赖安装：使用文件区 `zmd_py313_linux_x86_64.zip` 离线 wheels 安装到 Python 3.13 环境。

已执行：

```bash
sha256sum /mnt/data/zmd_gm_r3_snapshot_b377a2a7.zip
# b377a2a75e67697a38b2e46f8dc1407677a1f9936406b51695a7094487524531

python -m py_compile \
  src/models/exact_coordinate_master.py \
  src/models/master_model.py \
  src/tests/test_exact_coordinate_protocol_bounds.py

python -m pytest -q -p no:randomly src/tests/test_exact_coordinate_protocol_bounds.py
# 2 passed in 0.46s

python -m pytest -q -p no:randomly \
  src/tests/test_exact_coordinate_protocol_bounds.py \
  src/tests/test_master.py::test_coordinate_symmetry_breaking_orders_mandatory_signature_slots \
  src/tests/test_master.py::test_coordinate_symmetry_breaking_orders_required_optional_signature_slots \
  src/tests/test_master.py::test_coordinate_symmetry_breaking_orders_residual_optional_signature_slots \
  src/tests/test_master.py::test_ghost_signature_bucket_mandatory_region_counting_counts_pose_footprint_overlap \
  src/tests/test_master.py::test_ghost_signature_bucket_template_footprint_support_enables_rectangular_pose_footprints \
  src/tests/test_master.py::test_ghost_signature_bucket_payload_footprint_stability_cohorts_rectangular_bounds
# 8 passed in 0.61s

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

全量 `python -m pytest -q -p no:randomly src/tests` 已尝试；在沙盒 300 秒限制内跑到约 14% 后超时，因此本报告不声称全量 2955 项已完成。

## 补丁说明

补丁文件：`zmd_gm_r3_review.patch`，可在仓库根目录用以下方式应用：

```bash
patch -p1 < zmd_gm_r3_review.patch
```

已 dry-run 验证补丁可应用到原始快照。
