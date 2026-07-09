# C1 patch codex 独立审查（2026-07-09，b0_3/b0_4 发射前拦截）

> codex CLI（gpt-5.x）对 `c1_encoding_patch.py` v0 的只读语义审查。审查对象是 v0；
> 修复后版本 = v1（见 patch 头注释）。BUG 1 经主会话机制层复核实锤：clone+overlay 后
> 组合 no_overlap 杆 interval=0（v0）→ 2（v1），玩具行为对照被 ghost anchor 容量 screen
> 遮蔽（INFEASIBLE 来自 screen 非 no_overlap），机制层 proto 计数才是判据。
> 四修复 + runner 杆落盘全部落地，玩具等价 4 场景（含 ghost clone 全链）PASS。

**结论：C1 patch 目前不忠实实现设计语义。**  
最严重问题会造成假 FEASIBLE，足以污染 batch0 结果；不建议把 C1 实验数据用于生产编码选型，除非先修正并重跑。

**主要 Findings**

1. **BUG：exact-core + ghost overlay 路径丢失 C1 杆 interval，导致杆可与 ghost/设施/其他杆重叠。**  
   C1 只在 core build 时把 p_k interval 追加进临时 `_core_x/y_intervals`（[c1_encoding_patch.py](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:55), [line 61](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:61)）。但 core binding 导出不包含这些 C1 interval（[exact_coordinate_master.py](/home/zhuran24/zmd-pj/src/models/exact_coordinate_master.py:3565)），clone 时 `_core_x/y_intervals` 只从 slot specs 重建（[exact_coordinate_master.py](/home/zhuran24/zmd-pj/src/models/exact_coordinate_master.py:3557)）。由于 residual power_pole spec 已被 pop（[c1_encoding_patch.py](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:30)），p_k interval 不会回来。

   `from_exact_core(..., ghost_rect=...)` 随后加 ghost no_overlap（[master_model.py](/home/zhuran24/zmd-pj/src/models/master_model.py:2954), [exact_coordinate_master.py](/home/zhuran24/zmd-pj/src/models/exact_coordinate_master.py:3769)），并会清掉原 core-only no_overlap（[exact_coordinate_master.py](/home/zhuran24/zmd-pj/src/models/exact_coordinate_master.py:3825)）。结果：C1 p_k 杆不再参与任何 no_overlap。  
   失败场景：ghost 覆盖唯一可用杆位，生产应 INFEASIBLE；C1 clone 可选 ghost 内 p_k 覆盖 powered slot，返回假 FEASIBLE。batch0 runner 正走 `build_exact_core` 后 `from_exact_core(core, ghost_rect=(6, 6))`（[batch0_prod_runner.py](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/batch0_prod_runner.py:53), [line 62](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/batch0_prod_runner.py:62)）。

2. **BUG：pose 池完整性 fail-closed 断言不检查“完整格阵”，只检查数量。**  
   [c1_encoding_patch.py](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:41) 到 line 48 只做 `len(pool) == expected`。缺一个 anchor、重复另一个 anchor 仍会通过。  
   失败场景：缺少 `(68,68)`，重复 `(0,0)`，长度仍为 4761；生产坐标域允许 `(68,68)`，C1 不允许，可能假 INFEASIBLE。应检查 anchor 集合与 domain 笛卡尔积一一相等，且最好校验 pose tuple/occupied bbox 与 anchor/domain 一致。

3. **BUG：required_optional power_pole 路径未被 C1 等价处理。**  
   C1 只 pop `residual_optional_slots["power_pole"]`（[c1_encoding_patch.py](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:30)），但生产 `_all_power_pole_slots()` 包含 required + residual（[exact_coordinate_master.py](/home/zhuran24/zmd-pj/src/models/exact_coordinate_master.py:3124)）。仓内测试明确覆盖 `exact_required_pose_optional_counts={"power_pole": 1}`（[test_exact_coordinate_protocol_bounds.py](/home/zhuran24/zmd-pj/src/tests/test_exact_coordinate_protocol_bounds.py:117)）。  
   C1 coverage 只看 `_c1_pole_bools`（[c1_encoding_patch.py](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:77)），不是生产 required pole slot。该分支下会出现“required 坐标杆仍存在 + 全池 p_k 又可选”的混合语义，不是等价重编码。

4. **OK：witness cell 的 footprint 边界和 flat 展平顺序本身是对的。**  
   `wx >= fx`, `wx <= fx + fw - 1`, y 同理（[c1_encoding_patch.py](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:125)）匹配生产 footprint end = start + width 的半开区间定义（[exact_coordinate_master.py](/home/zhuran24/zmd-pj/src/models/exact_coordinate_master.py:2486)）。`cov` 按 `cy` 外层、`cx` 内层 append（[c1_encoding_patch.py](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:105)），`flat == wx + wy * grid_w`（[c1_encoding_patch.py](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:132)），一致。

5. **OK：`cov[c] <= Σp` 只有 ≤ 方向不会虚报覆盖，active/mandatory 挂接正确。**  
   `target == 1` 对 active slot 挂 `OnlyEnforceIf(active)`，mandatory `active=None` 时是硬约束（[c1_encoding_patch.py](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:135)）。`AddElement(flat, cov, target)` 加上 `target==1` 会强制选中的 `cov[cell]=1`，再由 `cov <= sum(coverers)` 推出至少一个覆盖该 cell 的 p_k 为真。

6. **存疑/不等价：杆数上界只保留静态 cap，没有保留生产的变量 dominance bound。**  
   C1 只加 `Σp <= _power_pole_slot_upper_bound`（[c1_encoding_patch.py](/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709/c1_encoding_patch.py:68)）。生产还在 residual power_pole 存在时加 `active poles <= mandatory powered + required optional powered + selected residual powered`（[exact_coordinate_master.py](/home/zhuran24/zmd-pj/src/models/exact_coordinate_master.py:6321), [line 6334](/home/zhuran24/zmd-pj/src/models/exact_coordinate_master.py:6334)）。  
   这通常是 dominance 弱化，不一定单独造成假 FEASIBLE，但不等于“Σp ≤ selected powered 数”的生产语义。

**其它观察**

- `_prepare_slot_specs_c1` 对 residual power_pole 的 pop 与 clone binding 的 KeyError 修复方向是干净的；其它设施 spec 列表没有被重排或改索引。问题是 C1 p_k 没有进入 binding/export，进而触发上面的 no_overlap 丢失。
- C1 也没有把选中的 p_k 接到 `extract_solution()`；free 模式若 FEASIBLE，runner 保存的 solution 会缺 power_pole entries。这不影响 solver status，但会影响后续覆盖复验材料。

我没有修改文件，没有跑 solve，也没有跑测试。