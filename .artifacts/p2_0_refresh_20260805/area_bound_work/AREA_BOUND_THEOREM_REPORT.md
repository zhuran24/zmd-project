# 流量面积上界定理报告（flowbound 线，2026-08-06，v4 = refute 席修正版）

> **语义标签（OB7，通篇有效）**：本文一切结论都在 **P2.0 第七谓词语义**下
> （钉死 `production_targets` + 严格空地 + 吞吐守恒 + 循环稳态）。与在案六谓词
> conditional 上界 U=(1188,18)（吞吐 OUT-OF-SCOPE）语义不同、并存不互斥，禁止混写。
> P2.0 落地采纳后本文口径才成为现役 U 语义。

> **修订记录**：v1-v3（提交 88c0911）含 front-state 下界 L≥308 与「第七谓词改变最优解」
> 结论，2026-08-06 经 codex refute 席对抗审查：**front-state 核心引理被 canonical
> splitter/merger 反例驳倒**（材料与本线亲手复跑记录在 `refute_20260806/`），
> 「改变最优解」为上界对上界的过推。v4 撤下两者，基座退回容量计数——
> 本版每一格都是站得住的，代价是结论更弱。

## 0. TL;DR

| 结论 | 数值 | 等级 | 收据 |
|---|---|---|---|
| 无条件面积上界 | **A ≤ 1167** | 【严格·模型内】（前提栏 §2 全列） | `ob5_theorem_bound_receipt.json` |
| 单层口径面积上界 | **A ≤ 1015** | 【条件·待 OB6】（需交叉密度上界 X ≤ 0） | 同上 |
| route state 下界 | **L ≥ 305**（容量计数；终品计入口径 306） | 【严格·模型内】 | 同上 |
| 电杆数下界 | **P ≥ 9**（旧 P≥6；SCIP 双档外部互证） | 【精确】 | `ob4_pole_lower_bound_receipt.json` |
| 流量口径 | **F_route = 9,135 整**（钉死目标，扣无线终品） | 【精确】 | `ob1_flow_caliber_receipt.json` |
| 机身预算 | 3,544（受电 3,325；棋盘余 1,356） | 【精确】 | `ob2_body_budget_receipt.json` |
| slot 普查（诊断用，不进上界） | 574/568/401/52 | 【精确】 | `ob5_slot_census_receipt.json` |
| front-state 下界 L≥308 | **REFUTED** | 负结果归档 §5.4 | `refute_20260806/` |

对 MEMO §3.3 粗算的净升级：三处粗算全部升格为脚本收据；**P_min 6→9**（A 收紧 12 格）；
面积上界从「粗算 ~1179（双层最宽松）」变为**严格链 1167**。
计划书预言「单层 ~950–1,100 档」：单层口径 1,015 接近预言档上沿，但它是条件结论
（依赖 OB6 交叉密度上界）；无条件档位是 1,167。

## 1. 与义务清单的对应

- **OB1 完成**：三口径并算（9,246 / 290691/32=9,084.09375 / 9,169.5→9,135），选定口径
  F_route=9,135 写单一 Fraction 收据；发现 flow_account.json 的 "9084" 是 `frac_str`
  4 位有效数字显示值（经 `F_balanced_over_C=302.803125` 无损互证）。
- **OB2 完成**：3,544 = 132×9+38×24+49×25+1×81+46×3 模板表驱动复算；受电机身 3,325。
- **OB3 引用**：每件 ≥1 route state 已闭（owner 08-05 附录二#1 零格交接「贴脸死、隔 1 格通」+
  模型 `src/models/routing_subproblem.py:1570-1572` missing_source_fronts/missing_sink_fronts、
  `:1710` `_validate_selected_route_connectivity`——本批回源核实仍在）。
- **OB4 完成**：单杆覆盖装填 IP（K=396 OPTIMAL；refute 席 SCIP 双档复算一致）⇒ P ≥ 9。
- **OB5 主体**：定理 1 严格链落地 + gap 结构台账（§5）+ 三条已证无效路线归档（§5.4，
  其中 front-state 引理由 refute 席驳倒）。
- **OB6 部分**：形式化 + 对抗例（§6），量化仍开放；新增一条未开发耦合杠杆（分/合流格不可交叉）。
- **OB7**：语义标签通篇执行。

## 2. 前提栏

继承 MEMO §0.3 前提 1–8（tick=2s、带容量 30 件/分钟/格/层跨商品聚合、slot=ceil(rate)、
每格位≤2 state、is_solid_z、front state 强制、production_targets 权威、严格空地）。
本文额外显式使用：

| # | 前提 | 出处 | 等级 |
|---|---|---|---|
| 前提 9 | 仓库桥排除：中间品必须带路由产口→耗口，仓库不是路由捷径 | `canonical_rules.json semantics.warehouse_bridge_exclusion`（owner 07-18 裁决） | 【owner 定谳】 |
| 前提 10 | 稳态无损耗：无丢弃/湮灭机制，循环稳态下内部商品 prod=cons | v3.1 循环态语义（A 档） | 【精确】（语义定义） |
| 前提 11 | belt 方向性 + 一切器件=具特殊功能的直带、无叠带 | owner 08-05 附录二#4 统一公理 | 【owner 定谳】 |
| 前提 12 | 门口排他（机器口无选择性⇒模型口 front 单商品是正确保守编码） | owner 08-06 定谳（机器入口无选择权·污染机制） | 【owner 定谳】 |
| 前提 13 | 垂直交叉双满速真实、平行双流物理不可能 | owner 08-05 附录二#3 | 【owner 定谳】 |
| 前提 14 | 电杆覆盖判据 = 12×12 覆盖矩形与受电设施 footprint bbox 相交（一格共享即算） | canonical `rules/canonical_rules.json:100-110` 与 `:460-471`（stencil 定义）；**运行时判据真身 = `src/models/exact_coordinate_master.py:6182-6197`（CP-SAT 四不等式矩形相交）**；exact 性由 `:5993-6028` 全矩形 footprint 守卫保证；C1 witness 路径 `:6679-` 以逐格 coverer OR 通道等价表达（Explore 座席回源 + 本线复核） | 【精确】 |

注意（refute 席点名后补的一条边界）：前提 11 的「直带」说的是器件的**机身形态**，
**不**蕴含 route state 是单向单进单出通道——splitter/merger state 有多入/多出边
（这正是 v1-v3 front-state 引理的翻车点，§5.4）。

任何一条前提被推翻，引用本文的结论必须重算（尤其前提 6/8/12/13）。

## 3. 定理与证明链

### 定理 1（P2.0 容量计数面积上界）

任何在 P2.0 语义下可行的布局满足 **A ≤ 1356 − 4P − R**，且 R ≥ ⌈L/2⌉、L ≥ 305、P ≥ 9，
故 **A ≤ 1167**；若单层口径成立（待 OB6，即交叉格数 X=0）则 R ≥ L ⇒ A ≤ 1015。

证明链（逐步等级）：

- **[A] 格位分账**【严格】：70×70=4,900 格划分为 mandatory 机身(3,544)、电杆(4P)、
  非强制机身(N≥0)、路由足迹(R)、空矩形(A)、空闲(S≥0)，六类两两不交
  （谓词 2 不重叠；前提 5 机身两层实心 ⇒ 无 route state 压机身；前提 8 严格空地 ⇒
  空矩形与其余五类全不交）。⇒ A ≤ 1,356 − 4P − R − N − S ≤ 1,356 − 4P − R。
- **[B] 聚合吞吐唯一**【严格】：17 个操作的聚合活动（机器当量）由 17 条商品平衡方程
  唯一确定（OB1 高斯消元非奇异；前提 7/9/10 排除仓库桥与损耗旁路）。
  **术语精确化（refute 席修正）**：canonical 配方图**不是 DAG**（buckwheat/sandleaf
  两个种子 SCC）；唯一的是**聚合活动向量与逐商品聚合吞吐**，不是逐条路径流。
  任何达标稳态的聚合吞吐 = 唯一解（超产只会更大）⇒ 进路由图流量 ≥ F_route = 9,135 件/分钟。
- **[C] 容量计数**【严格】：每件过 ≥1 个 route state（前提 6 + OB3）、每 state ≤ 30 件/分钟
  （前提 2）⇒ state 数 L ≥ ⌈9135/30⌉ = 305。
- **[D] 足迹**【严格（无条件口径）】：每格 ≤2 state（前提 4；且前提 13 坐实 2 state/格
  是真实机制而非建模伪影）⇒ R ≥ ⌈L/2⌉ = 153。**单层口径 R ≥ L 是【条件·待 OB6】**。
- **[E] 电杆**【精确】：P ≥ 9（定理 3，下）。

### 定理 2（front-state 下界）——已撤下（REFUTED）

v1-v3 曾以「一个 route state 至多充当 1 个产口 front 与 1 个耗口 front」为引理推出
L ≥ 308。该引理被 refute 席以 canonical 最小反例驳倒（一个 splitter state 同时服务
1 产口 + 2 耗口、一个 merger state 同时服务 2-3 个产口 + 1 耗口，绑定与路由模型均
FEASIBLE），本线已亲手复跑复现。全部材料、反例几何与前提错误剖析见 §5.4 第 3 条与
`refute_20260806/`。**本版上界不使用任何 front 计数。**

### 定理 3（电杆下界 P ≥ 9）

指派论证：每个受电设施（132×3×3 + 49×5×5 + 38×6×4，机身 3,325 格）指派给一根覆盖它的
电杆（前提 14 判据）⇒ 单杆名下设施两两不交、包围盒均与其 12×12 覆盖窗相交、均不压
2×2 杆身 ⇒ 单杆覆盖机身 ≤ K。K 由 CP-SAT 装填最优化精确求得 **K = 396**（OPTIMAL，
840 候选位姿；脚本内同进程逐格自检通过；**外部互证 = refute 席 SCIP 双档复算
K=396 一致**，收据 `refute_20260806/independent_power_ip_probe_receipt.json`）。
⇒ P ≥ ⌈3325/396⌉ = **9**。对照：MEMO 576 松窗口径 P≥6、22×22 膨胀计数 P≥7。
保守性：位姿允许悬空棋盘外、覆盖窗不裁剪、不计杆间互斥——全部只会高估 K，方向安全。

## 4. 紧性与对抗分析（为什么到此为止、强化必须从哪来）

**对抗例 1（全链贴放 + 分/合流压缩）**：产耗口正对共享中格（贴脸死、隔 1 格通 ⇒
1 格带合法）实现逐件路径长度 1；refute 反例进一步表明 splitter/merger state 可把
最多 4 个相邻口压进 1 个 state。⇒ [C] 的「每件 ≥1 state」在对抗意义下逐件紧，
且任何「按口数数 state」的下界都必须先过 splitter/merger 反例这一关。

**对抗例 2（网格城）**：全部干线直线化、垂直交叉自由堆叠 ⇒ 每格 2 state 大面积可达
（前提 13 坐实交叉双满速真实）。slot 结构又几乎无强制合流（扇形是 1:1 或
2:1-双slot）⇒ 纯计数不可能无条件排除 R = ⌈L/2⌉。
**结论：任何超越 1167 的无条件强化，必须使用口几何/普查结构/棋盘边界信息**，
纯流量计数已榨干。

## 5. Gap 结构台账（OB5 核心产出）

记号：ΔA = 对无条件上界 1167 的预期压降。

### G1 口几何强化（原「配对几何」，refute 后重述）
front 计数路线已死（§5.4 第 3 条），幸存的攻法必须换形式：
- **流量加权的口计数会塌回容量计数**（一个 state 服务多口时，其吞吐帽 30 件/分钟
  已在 [C] 里记账），所以「数口」本身没有免费增量；
- 任何复活的 front 型下界必须写成「口集合 − 共享超图上的最大匹配/覆盖亏损」的形式，
  且**逐个构造先过 refute 探针的模型验证**（探针 harness 就在 `refute_20260806/`，
  可直接改造成候选引理的自动验证器）；
- **未开发耦合杠杆【推断】**：`bridge_mechanics.can_overlap_splitter_merger=false` ⇒
  凡用 splitter/merger 压缩口的格**不能再当交叉格**——「口压缩」与「交叉堆叠」
  在同一格上互斥。这条把 G1 与 OB6 耦合：对抗方省 state 的每一步都在损失交叉容量。
  形式化后有望同时压两个口径，是 refute 后最值得先试的方向。

### G2 路径长度 ℓ̄
敏感度（精确值，`ob5_theorem_bound_receipt.json` sensitivity 表）：
L(ℓ̄) ≥ ⌈304.5·ℓ̄⌉；A_single ≤ 1320 − L；A_uncond ≤ 1320 − ⌈L/2⌉。

| ℓ̄ | L ≥ | A_single ≤ | A_uncond ≤ |
|---|---|---|---|
| 1 | 305 | 1015 | 1167 |
| 2 | 609 | 711 | 1015 |
| 3 | 914 | 406 | 863 |

逐 state 边际：单层恒 −1 格；无条件按奇偶交替 −1/0 格（R=⌈L/2⌉）。
band22 实测平均最近生产者距离 22.25 格，真实布局远离紧例，但布局无关的 ℓ̄>1
论证难度 = L 侧枚举墙同级。

### G3 交叉密度（= OB6，见 §6）
奖池：无条件 1167 → 单层 1015（ΔA −152）。

### G4 终品口径
扣无线终品是保守选择，代价已精确量化（receipt `finals_included_variant`）：
终品计入 ⇒ L ≥ 306，单层收紧 1 格（1015→1014）、无条件不变（1167）。
若 P2.0 谓词最终把终品交付计入路由，白拿回单层 1 格。

### G5 电杆-路由互动
电杆机身算 body、会堵口 front（07-18 定谳）；杆必须站在机群里（覆盖窗要交机身）⇒
杆周边格与路由预算冲突。预期 ΔA 小（个位数），排最后。

### G6 割集/Farkas 证书化（v2 B 档格式的落点）
**定理 1 链**是行族的非负组合：行族 = {17 条聚合守恒行（[B]）、每 state 容量行 ≤30（[C]）、
每格 ≤2 state 行（[D]）、格位分账行（[A]）、覆盖指派行（定理 3）}。把**这条链**写成
static-flow-with-lift + row-family manifest 是工程化（预期一个批次）——「无数学缺口」
的声明**仅限此链**；v1-v3 曾把 front 行族（614 行：产口 306 + 耗口 308）也算进去，
该行族已随引理撤下。真正的研究缺口在把 G1/G3 的几何论证也压进行族（割集行）。

### 5.4 已证无效的路线（防重踩，负结果归档）

1. **rate 类互斥配对排除**（曾推出 Pmax≤255、A≤~1100）：死于「机器级占空可集中
   （floor(x) 台满速 + 1 台残速）+ slot 可不均分」——两个自由度合谋能把绝大多数
   rate 类还原成可配对。
2. **slot×机器数当端口下界**（v1 的 L≥313）：同一对自由度，端口最小数只有 ⌈x·q⌉，
   多算 5 个 state；v2 修正为 308——但见第 3 条。
3. **front-state 引理本身**（v2/v3 的 L≥308，报告曾标【严格·模型内】）：
   **被 refute 席驳倒（2026-08-06）**。反例（canonical 位姿，绑定+路由模型 FEASIBLE）：
   planter_buckwheat(pose 7793) / crusher_buckwheat(8851) / seed_collector_buckwheat(9086)
   三机身不重叠、三口共 front (35,35)，一个 splitter state（in=[W], out=[N,S]）同时服务
   1 产口 + 2 耗口（残流 1/2+1/2 恰由满速 planter 分流）；另有 merger 2 产 1 耗、
   3 产 1 耗两个 gadget 同判。**前提错误**：把 route state 当成单向直通道——
   splitter/merger state 有多入/多出边；port_adherence 只要求每口 exact-one state，
   从未要求不同口选不同 state。后果：buckwheat 12→11、sandleaf 22→21，Σmax 推导整体失证。
   材料：`refute_20260806/`（探针、收据、本线复跑记录）。
   **任何未来 front 型论证先过该探针 harness 再上报告。**

## 6. OB6：双层口径修正（形式化 + 现状）

**已定谳事实**（前提 13）：同格双通道 = 单格垂直交叉件（无坡道），垂直双流各自满速
真实存在；平行双流物理不可能。⇒ 每格容量 2 件/tick 只在交叉格兑现。

**形式化**：令 X = 交叉格数（2 state 的格），则 R = L − X ≥ 305 − X，
A ≤ 1356 − 4P − L + X。单层口径 ⟺ X = 0；无条件口径 ⟺ X ≤ ⌊L/2⌋ = 152。
**OB6 的任务 = 布局无关地上界 X**。现状：开放。对抗例 2（网格城）表明纯计数不行；
可用杠杆：(i) 交叉格不能是弯道/分合流器/桥转弯（canonical `bridge_mechanics` 四禁令）
——**特别地，G1 的耦合杠杆：口压缩用的 splitter/merger 格天然非交叉格**；
(ii) 交叉的两条通道都要有来源与去处——46 个边界口全在左/下边界
（`placement_rule left_or_bottom_boundary`）给了方向结构。
**当前正确姿势：引用无条件口径 1167；单层 1015 必须带【条件·待 OB6】标签。**

## 7. 与在案六谓词 U 的关系（OB7 纪律，refute 席修正版）

U=(1188,18) conditional 是六谓词语义（吞吐 OUT-OF-SCOPE）的上界，本文不触碰它。
本文的正确定位：**收紧 P2.0 语义下的 research upper ledger 至 1167**。

**「第七谓词落地会改变最优解本身」是开放问题，本文不主张**（v1-v3 曾主张，
refute 席指出为过推：上界对上界推不出最优值变化——OPT_P2.0 ≤ 1167 与
OPT_六谓词 ≤ 1188 完全可以同时等于同一个值；当前 L=absent，两侧都没有下界）。
补证路径（任一即可闭合）：(a) 拿到六谓词最优 witness 且其 A > 1167，再证它
P2.0-不可行；(b) 六谓词侧建立 lower bound > 1167；(c) P2.0-complete 求解直接出最优。
min_side 维度本文未触碰。

## 8. 复跑索引（全部数字的唯一来源）

```
cd /home/zhuran24/zmd-pj
python  .artifacts/p2_0_refresh_20260805/area_bound_work/ob1_flow_caliber.py
python  .artifacts/p2_0_refresh_20260805/area_bound_work/ob2_body_budget.py
.venv/bin/python .artifacts/p2_0_refresh_20260805/area_bound_work/ob4_pole_lower_bound.py   # 需 ortools
python  .artifacts/p2_0_refresh_20260805/area_bound_work/ob5_slot_census.py
python  .artifacts/p2_0_refresh_20260805/area_bound_work/ob5_theorem_bound.py
```
依赖顺序：ob1 → ob2 → ob4 → ob5_slot_census → ob5_theorem_bound。
各脚本 stdout 存档于同名 `*_stdout.log`。
refute 席材料（反例探针、SCIP 互证、本线复跑记录）：`refute_20260806/`（含 README）。

## 9. 下一步排期建议

1. **G1×OB6 耦合杠杆**（splitter/merger 格不可交叉）：refute 后最值得先试的方向，
   同时攻两个口径；任何 front 型候选引理先过 `refute_20260806/` 探针 harness 验证；
2. **G6 证书工程化**（定理 1 链 → row-family manifest）：无数学缺口，一个批次；
3. **G2 路径长度**：与 1 合流（同一批几何论证双产出）；
4. 修订版过 refute 席复核后再入 docs/research/ 转正（本文当前状态：待复核）。
