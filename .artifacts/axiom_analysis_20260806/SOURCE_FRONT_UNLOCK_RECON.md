# source front 模型解锁·技术侦察（2026-08-06，纯只读侦察）

> 背景：owner 08-06 公理终审定谳「输出口门口混流过境安全」（附汇流 2s CD 速率注记），
> 模型对 source front 与 sink front 同等排他被确认为过严面。本文回答「解锁怎么做、
> 代价多大」——侦察结论**修正了「删一行豁免就行」的直觉**。

## 1. 排他的真实编码（不是一张表）

`routing_subproblem.py` 里没有显式的「front 格排他约束」。排他是三层结构的涌现：

1. **`_add_port_adherence`（:1297）**：每个口在自家 front 格上要求
   `sum(终端边 vars) == 1`——恰一条地面终端边对准口方向；
2. **`_add_capacity_constraints`（:1119）**：每格每层 AtMostOne(物理件)——物理层
   （belt/cross 形态）**无商品维度**，一格一件；
3. **同商品终端豁免（:1233/:1271，layer==GROUND 守卫）**：successor/predecessor
   链在自家终端格跳过——这是 wf 反例席实读的「sink/source 对称」的真身，
   它是**同商品**终端语义，不是跨商品排他。

跨商品的「别家货不能过我门口」= 别家货的流变量要用这格，就得共享同一个物理件
（capacity 一格一件）+ 终端 adherence 已把这件的地面形态钉死为终端带 ⇒ 别家货
只能「共乘同一条带」——而这撞上 §2 的真墙。

## 2. 真墙 = 模型的混流表达能力（残余 5.2#7 / U-02）

一手 probe（U-02）显示：两商品「合流后再分流」在当前 use/phys 结构下**结构性
INFEASIBLE**——分流点上没有按商品区分去向的机制。所以即便把终端格对别家货
「放开」，别家货也上不了那条带。**解锁 source front 地面共乘的前置是先解决 #7
（混流表达扩展）**，那是 use-var 结构手术（sealed 面、freeze-ritual、soundness
敏感方向须外审），不是删一个守卫。

## 3. 已经免费拿到的部分（本日双探针实证）

**L1 垂直借道在两种口的 front 上都已可用**：
- 输入口：`probe_p1_l1_transit.py` → FEASIBLE（08-06 上午）；
- 输出口：`probe_source_front_l1_transit.py` → FEASIBLE（08-06 下午，本侦察）。

机制：`_add_bridge_constraints`（:1124）对 L0 直带 + L1 垂直轴向直通豁免互斥
（`l0_is_crossable && 轴不同`）——终端带是直带即满足。**垂直过境增益无需任何
代码改动**，r4 任务书已把该自由度扩为双向口。

## 4. 结论与排期建议

| 增益 | 状态 |
|---|---|
| 垂直过境（L1 借道，双向口） | ✅ 已有，零改动，r4 已教 |
| 输出口门口地面**同向共乘**（借输出道当干线） | ❌ 挂 #7 混流表达扩展——大手术，远期 |

**建议**：「source front 解锁」从独立候选降级为 **#7（混流表达）的子项**。速率
账（owner：借道段各流之和 ≤1 件/tick、残余 >1/2 不可被满速借道）在 #7 落地时
一并写进设计文档——认证谓词不含吞吐，模型侧无速率义务。

## 5. 若未来做 #7 的雷区清单（本侦察顺手记）

- `patch_routing_core.py:583-585` 双重 front 偏移（F-SND-001）在 V99 floor 内，
  promotion/结构改动前必修；
- 域构建（`analyze_exact_routing_domain`）按商品建活跃域，混流扩展会改
  `commodity_active_cells` 语义——D2/PCR 抑制义务同批重审；
- `_validate_selected_route_connectivity` 全局复验按单商品分量走，混流下需重写。
