作为 P2 #14 AlphaEvolve 的 LLM proposer，我已严格阅读并确认 AI Safety Contract。本次提交的所有变体均**仅使用 `model.AddHint()`** 进行软偏好引导，绝不注入破坏 certified proof 的硬约束，不修改求解器内部逻辑。

以下为针对 Binding Subproblem 提出的 6 个 NEW hint 变体，旨在探索“空间几何关联”、“玩家习惯（工厂模式）”及“基数启发式”对 CP-SAT 分支选择的加速潜力。

---

## 变体 1: hint_adjacent_direct_insertion (相邻直塞优先)
```python
def hint_adjacent_direct_insertion(model, slot_vars, instances, adj_port_pairs):
    """几何启发: 若 Master placement 中两设施的输出/输入端口紧贴且相对，优先 bind 相同 commodity 形成直塞。"""
    for (port_out, port_in) in adj_port_pairs: # adj_port_pairs 需从 master 几何信息提取
        f_out, s_out = port_out
        f_in, s_in = port_in
        # 寻找既是 f_out 产出又是 f_in 需求的 commodity
        common_commodities = get_common_commodities(instances[f_out], instances[f_in])
        for c in common_commodities:
            # 软偏好：如果它们紧邻，强烈建议用这个商品直接对接
            model.AddHint(slot_vars[f_out][s_out][c], 1)
            model.AddHint(slot_vars[f_in][s_in][c], 1)
```
- **跟 hint 1/2 区别**: Hint 1 是 Routing 的跳数限制，Hint 2 是非空间相关的 Storage 限制。此变体首次将 Master 的几何特征（直接相邻）映射为 Binding 的变量偏好。
- **预期效果**: 极大降低 Routing 压力。在密集布局中，预期 binding 求解时间下降 15-20%，因为顺应了“流水线直塞”的最优解结构。
- **风险**: 安全（软偏好）。不会破坏 cert。若 Master 布局并非为了直塞，可能导致 CP-SAT 早期探索错误分支。

## 变体 2: hint_single_commodity_output_homogeneity (同源纯净输出)
```python
def hint_single_commodity_output_homogeneity(model, slot_vars, instances):
    """玩家习惯启发: 对于多输出端口的制造设施，倾向于所有激活的输出端口都绑定同一种（最高产量的）commodity。"""
    for f_id, inst in instances.items():
        if inst.type == 'MANUFACTURING':
            out_slots = inst.get_output_slots()
            if not out_slots: continue
            # 找出该设施配方中产出率最高的商品
            main_c = get_highest_yield_commodity(inst)
            for s in out_slots:
                # 引导所有输出端口优先处理主打产品，避免“杂交”输出增加分拣器负担
                model.AddHint(slot_vars[f_id][s][main_c], 1)
```
- **跟 hint 1/2 区别**: 属于设施维度的基数/一致性启发，不涉及物流桥或 overload。
- **预期效果**: 缩小 CP-SAT 分支搜索树，预期提升首个可行解发现速度 10%+，符合玩家“单一产线单一产品”的强迫症习惯。
- **风险**: 极其安全。部分复杂配方（如副产物）可能会在此 hint 下稍晚被搜到。

## 变体 3: hint_index_based_port_packing (端口紧凑分配)
```python
def hint_index_based_port_packing(model, slot_vars, instances):
    """基数启发: 倾向于优先使用 index 较小的端口，高 index 端口默认不绑定(绑定到 dummy/None)。"""
    for f_id, inst in instances.items():
        for s_idx, slot in enumerate(inst.all_slots):
            # 假设 index > 1 的端口为边缘端口或备用端口
            if s_idx >= 2:
                for c in inst.possible_commodities:
                    # 强烈建议高位端口闲置 (0 = false)
                    model.AddHint(slot_vars[f_id][slot.id][c], 0)
```
- **跟 hint 1/2 区别**: 纯粹的对称性打破/搜索空间压缩手段，不依赖业务逻辑复杂特征。
- **预期效果**: 减少冗余的 active ports 组合验证，理论上能让 Binding 求解器时间稳定下降 5-8%。
- **风险**: 安全。如果设施必须用满 4 个端口才能满足吞吐率，求解器仍能推翻此 hint，但可能会在回溯时消耗少量额外时间。

## 变体 4: hint_recipe_proportional_input (按配方比例预分配)
```python
def hint_recipe_proportional_input(model, slot_vars, instances):
    """领域知识: 若设施需 A 和 B，且 A 的消耗速率是 B 的两倍，优先将更多端口绑定给 A。"""
    for f_id, inst in instances.items():
        if inst.type == 'MANUFACTURING':
            in_slots = inst.get_input_slots()
            sorted_reqs = sort_commodities_by_req_rate(inst) # 按需求率降序
            if not sorted_reqs or not in_slots: continue
            
            # 最高需求的商品占用第一个输入槽
            model.AddHint(slot_vars[f_id][in_slots[0].id][sorted_reqs[0].c_id], 1)
            # 如果有第二个槽和第二个商品，分配给老二
            if len(in_slots) > 1 and len(sorted_reqs) > 1:
                model.AddHint(slot_vars[f_id][in_slots[1].id][sorted_reqs[1].c_id], 1)
```
- **跟 hint 1/2 区别**: 利用了 throughput (吞吐量) 和配方比例信息来指导具体端口。
- **预期效果**: 防止 CP-SAT 将所有端口盲目绑定给低耗商品导致 Infeasible，提高 LBBD 单次迭代质量。
- **风险**: 安全。纯启发式指派。

## 变体 5: hint_pure_storage_box (纯净仓储模式)
```python
def hint_pure_storage_box(model, slot_vars, instances):
    """扩展 Hint2: 玩家习惯一个 Storage Box 只存一种 commodity。对所有端口软提示绑定同一最高权重商品。"""
    for f_id, inst in instances.items():
        if inst.type == 'STORAGE':
            # 找到网络中流量需求最大的商品作为仓储首选
            top_c = get_highest_network_traffic_commodity() 
            for s in inst.all_slots:
                # 提示这个箱子的所有可用槽位都绑同一个商品
                model.AddHint(slot_vars[f_id][s.id][top_c], 1)
```
- **跟 hint 1/2 区别**: Hint 2 是基于冲突图的硬/软*分离* (Separation) 逻辑；这里是更激进的 *聚合* (Clustering) 逻辑，追求极致纯净。
- **预期效果**: 形成“物流集散中心”模式，大幅简化 Routing 的商品分流逻辑。
- **风险**: 安全。在资源极端紧张、必须用一个箱子混装两样东西的边缘测试例中，可能会略微拖慢求解。

## 变体 6: hint_central_port_high_volume (高通量居中/对齐)
```python
def hint_central_port_high_volume(model, slot_vars, instances):
    """几何与通量结合: 吞吐量最大的 commodity 优先绑定到设施几何中心的端口，便于传送带直走。"""
    for f_id, inst in instances.items():
        highest_c = get_highest_throughput_commodity(inst)
        if not highest_c: continue
        # 假设 central_slot 是设施正中间的端口
        central_slot = get_geometrically_central_slot(inst)
        if central_slot:
            model.AddHint(slot_vars[f_id][central_slot.id][highest_c], 1)
```
- **跟 hint 1/2 区别**: 将“内部微观几何（中心槽位）”与“宏观吞吐量”结合。
- **预期效果**: 减少传送带在设施周边的绕线/转弯，直接提升解的视觉美观度和 Routing 的成功率。
- **风险**: 安全。需要依赖 `get_geometrically_central_slot` 的准确性。

---

## 总结

- **最看好哪 1-2 个？为什么？**
  1. **变体 1 (`hint_adjacent_direct_insertion`)**: 最具潜力。因为 Factorio/Endfield 类规划的最优解极度依赖**直接插入（直塞）**。它直接利用了 Master 提供的信息，能极大地将 Binding 解空间导向对 Routing 最友好的方向。
  2. **变体 3 (`hint_index_based_port_packing`)**: 最具普适性。它无需复杂的领域知识即可生效，能有效破除 CP-SAT 在相同功能端口间排列组合造成的对称性爆炸（Symmetry Breaking）。

- **哪些可能 over-constrain 不安全？**
  - 由于我们严格遵循了 AI Safety Contract，全部使用 `model.AddHint`，因此从数学证明 (Certified Proof) 层面来说，**没有任何一个变体是不安全的 (不会引发假 Infeasible)**。
  - 但从“性能 over-constrain”角度来看，**变体 5 (`pure_storage_box`)** 风险最高。如果当前布局确实需要用一个箱子中转两种少量物资（如早期紧凑型工厂），过度偏好纯净箱子会导致 CP-SAT 浪费大量节点在寻找不存在的单商品分配方案上，直到触发冲突返回。