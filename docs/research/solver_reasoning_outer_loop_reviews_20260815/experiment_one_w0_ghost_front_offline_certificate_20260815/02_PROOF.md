# W0 固定空矩形阻断活动边界源口的离线证明

> **结论状态：** `PROVED_IN_PINNED_CONTEXT`
> **效力：** research-only、evidence-only；不接入求解器，不产生 lowering、cut、认证或发布效力。
> **机器陈述：** [`01_JUDGMENT.json`](01_JUDGMENT.json)
> **独立复算器：** [`03_check_w0_ghost_front_certificate.py`](03_check_w0_ghost_front_certificate.py)

## 1. Judgment 范围

本证明只讨论下列固定上下文：

- canonical 规则字节为 `rules/canonical_rules.json`，SHA-256 为 `c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0`；
- candidate pool 字节为 `data/preprocessed/candidate_placements.json`，SHA-256 为 `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`；
- 固定布局字节为 `.artifacts/w0_fixrerun_20260804/band22_alignment/registration_placement_solution.json`，SHA-256 为 `db85d3e18fd0fc12ba743e0fd86e38183262a24c90d28805634c952cf27103c7`；
- 固定矩形输入字节为 `.artifacts/w0_fixrerun_20260804/band22_alignment/max_empty_rect_for_this_placement.json`，SHA-256 为 `aeb3a046a23309db845c238372d3b0a8e442c2ac7c94eb9de18ab0f1d9420fc6`；
- 固定布局标识为 `W0-ALIGNMENT`；
- 固定矩形为

\[
R=[1,6]\times[51,57].
\]

只对绑定方案 \(b\) 量化，不对布局、矩形、规则版本或候选池量化。问题、目标和上下文的规范化 hash 见机器 Judgment。

本证明不引用 Phase -1 的失败计数、签名聚类、`front_blocked` 判词或任何观测事件。实验谱只用于发现候选命题，并在证明完成后测量覆盖。

## 2. 便宜触发器

定义：

\[
\operatorname{Active}_{041}(b)
\]

当且仅当绑定方案 \(b\) 把 `boundary_port_041` 的唯一输出 slot 作为 predicate 5 的活动 source terminal，并给它绑定某个 commodity。

这是一个单原子触发器。对显式 binding map，它只需一次键或 selected-literal membership 查询；不需要构造 routing grid，不需要连通性求解，也不需要读取其他绑定选择。

触发器与 commodity 身份无关。commodity 只决定该 source terminal 属于哪一种商品，不改变其唯一物理前格。

## 3. 结论

在上述固定上下文中：

\[
\forall b,
\operatorname{Active}_{041}(b)
\Longrightarrow
\neg\exists r\;
\operatorname{Routable}_{P5}(W0,R,b,r).
\]

也就是说，任何满足触发器的绑定方案都不可路由。

这里的 `Routable_P5` 同时服从 pinned canonical predicate 5 与 pinned strict-empty rectangle 语义。结论只是否定 routing witness，不宣称所有可能绑定都满足触发器。

## 4. 从字节独立重导的六个事实

### F1. 固定布局选中了指定 pose

固定布局字节给出：

```text
instance_id = boundary_port_041
facility_type = boundary_storage_port
pose_idx = 52
pose_id = p_x00_y52_o0_m_left_base
```

### F2. 该 pose 只有一个输出前格

在 pinned candidate pool 的 `facility_pools.boundary_storage_port[52]` 中：

```text
input_port_cells = []
output_port_cells = [{x: 1, y: 53, dir: E}]
```

因此其唯一输出前格为

\[
f_{041}=(1,53).
\]

checker 还逐个解析固定布局中的全部 pose，并从 candidate pool 重导其 occupied cells；固定矩形与所有设施 body 不相交。矩形是本 Judgment 的固定输入，不借用原始 artifact 对“最大”或“可认证”的叙述。

### F3. 唯一前格落在固定矩形内

由

\[
1\le 1\le 6,
\qquad
51\le 53\le 57,
\]

得

\[
f_{041}\in R.
\]

### F4. stored port coordinate 就是 front/belt cell

Pinned canonical `semantics.axiom_kernel.axioms.A5_interfaces` 明确规定，candidate placements 中保存的 port coordinate 本身就是 front/belt cell，不再向外偏移一格。

因此活动输出口的 belt terminal 所在格就是 \((1,53)\)，不是 \((2,53)\)。

### F5. 活动口要求该格接受 belt

Pinned canonical `semantics.machine_min_clearance.statement` 明确规定：一个 in-use port 要求其 stored front cell 接受 belt。

Pinned canonical `semantics.connectivity_quantifier.statement` 还要求每个 source front 能到达某个 sink front。因此 `Active_041(b)` 不能由一条完全不占用该 terminal front 的 routing witness 满足。

### F6. strict-empty 矩形禁止该 belt terminal

Pinned canonical `globals.empty_rectangle.emptiness` 为 `no_occupant_of_any_kind`。其 adjudication statement 明确禁止 facility body、power pole、belt、cross-junction、bridge component 以及其他 logistics part 与矩形相交。

因此任何 routing witness 都不得在 \(f_{041}\in R\) 放置 belt terminal 或其他 logistics occupant。

## 5. 反证

任取绑定方案 \(b\)，并假设 \(\operatorname{Active}_{041}(b)\)。

再假设存在 routing witness \(r\) 满足固定布局、固定矩形与 canonical predicate 5。

1. 由 F1 与 F2，活动 source terminal 的唯一前格是 \(f_{041}=(1,53)\)。
2. 由 F4 与 F5，\(r\) 必须让该格接受作为 terminal 的 belt。
3. 由 F3，\(f_{041}\in R\)。
4. 由 F6，\(R\) 内不得存在 belt 或任何 logistics occupant。
5. 同一 routing witness 因而同时要求并禁止 \(f_{041}\) 上的 belt terminal，矛盾。

所以不存在这样的 \(r\)。证毕。

## 6. 条件圈与缩圈记录

观测最初指向两个贯穿样本的局部签名：`boundary_port_041` 的前格 \((1,53)\) 与 `boundary_port_042` 的前格 \((1,56)\) 都落在固定矩形内。

证明构造没有把“两口同时活动”写进触发器。局部反证显示，只要 `boundary_port_041` 一个口活动就已经矛盾；第二个口只是冗余 sibling witness。于是条件圈从“两口同时活动”缩到一个单原子：

\[
\operatorname{Active}_{041}(b).
\]

随后又移除了观测中的具体 commodity `source_ore`，因为矛盾只依赖物理前格，和商品身份无关。

独立 checker 对 pinned 字节没有找到圈内可活对象：一旦触发器成立，矛盾由同一个格子的必占与禁占直接形成，不存在需要进一步枚举的局部选择。

这个缩圈动作的教训是：高覆盖签名适合指路，但证书应继续删除不承重的共同特征，直到只剩足以推出结论的最小语义核。

## 7. 冗余 sibling corollary

同一组 pinned 字节还独立给出：

```text
boundary_port_042
pose_idx = 55
unique output front = (1,56)
```

且 \((1,56)\in R\)。因此把主定理中的 `041` 替换为 `042`，可得到同型条件式不可路由结论。

该 corollary 不进入主证书大小；它只证明 W0 局部障碍存在两个独立的一格反证入口。

## 8. 明确不推出什么

本证明不推出：

- 每个合法 binding selection 都必然激活 `boundary_port_041`；
- W0 固定布局对所有可能 binding selection 都不可路由；
- 其他布局或其他空矩形具有同一障碍；
- 当前 lex 上界、下界或全局最优性发生变化；
- 一条 solver cut 或 lowering 已经 sound 地实现；
- Phase -1 的 1007 个观测能够替代定理前提；
- 推理外环已经达到真实系统闭环、家族 holdout 或全局面貌层级。

任何 pinned 文件字节变化都会使本 Judgment stale，必须重新复算和重新陈述范围。
