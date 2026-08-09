# 否定性/上界类结论的 routing 依赖度逐证书盘点（2026-08-06）

fork: cert-scope-audit。背景：routing 模型判 (b) 比 canonical 严（终端 front 格对外商品
排他，「同形状按商品选边」表达力缺失）。凡证明**用到 routing 模型约束**的上界/不可行性
结论对 canonical 语义带作用域条件；只用几何/装箱/端口 front 计数/供电层必要条件的证明
不受影响。判定依据全部来自证明结构层（引文见各节）。

## 总表

| # | 结论 | 判定 | 一句话依据 |
|---|---|---|---|
| 1 | PB-03 VeriPB residual-band UNSAT (1326,34) | **不带条件** | 编码=机身面积+杆数下界P≥2+46 边界口 front 接驳格必需；无任何 per-commodity/routing 约束 |
| 2 | 干净房间 (1190,34) + P≥9 | **不带条件** | 端口膜=front 接驳格计数（每格≤4 口）+模板口几何+供电光环权重；无 routing 结构 |
| 3 | SMM4/R4 U=(1188,18)（含 (1188,22) PB） | **不带新条件**（原 A004 条件照旧） | A004 引理=模板口几何（marked=forced_mfg 58+raw 52）+access-cell t+m≤4+供电 halo+边界 packing；全部 canonical 级必要条件 |
| 4a | W0 3号死刑（129/219 seed 判死） | **不带条件**（且非全局 bound） | 文书自明「纯 body-front 几何计数，与 routing/class 分配方案无关」；scope=W0 seed 线 |
| 4b | H20 row-power oracle UNSAT | **不带条件**（且非全局 bound） | 纯供电层计数矛盾（halo 窗口 14 列→双杆≤10<22）；文书自限不外推 |
| 5 | round45 六臂 UNKNOWN | **无需处理** | 台账原文即「三锚点全 UNKNOWN=无上界证书」，从未被当上界引用 |
| 6a | W2b 六跑 UNKNOWN（负锚点未立） | **无需处理** | UNKNOWN 非证书；负锚点至今未立（钳口未合的 L 侧现状） |
| 6b | ab16 16 臂 BUDGET_CENSORED_UNKNOWN | **无需处理** | censored 合同=两个方向都不证明 |
| 6c | band22 旧 (42,6) 见证暂停/band14 割账 | **无需处理** | 见证内部记账，非仓库 bound 证书 |

**结论：现役全部上界/否定性证书（U=(1188,18) 链、(1190,34)+P≥9、PB-03 (1326,34)）
均不依赖 routing 模型约束——routing 保真缺口 (b) 不给任何在案证书追加作用域条件。**
「上界/不可行性类带条件」的风险敞口只对**未来**用 routing 子问题产出的否定结论生效
（如官方门对某见证的 INFEASIBLE 若被引作不可行证据——④路 censoring 合同已挡住这类误用）。

## 各证书依据细节

### 1. PB-03 (1326,34)

`front_offset_incident_20260718/07_pb03_r1_upper_bound_veripb_revalidation_20260720.md`：
- 带外段（1,763 尺寸）：`4900 − 3544(body) − 4×2(P≥2 杆体) = 1348` 自由格上限——几何+供电；
- 带内段（22 尺寸）：OPB 只编码「矩形与 46 个被迫 connector cell 共存 ⇒ |R∪Q_δ|≤1348」。
  connector cell = 边界口 front 常量格（encoder `r1_upper_bound_pb_encoder_v1.py:383-387`：
  `(1, anchor+1)`/`(anchor+1, 1)`，46 个），必要性=「46 口不许闲置+在用口 front 格必须能放带」
  ——canonical `machine_min_clearance` 原文级前提，与商品/路由结构无关。
- 混流表达力缺口不影响：front 格必须存在且非机身，在 canonical 混流语义下同样必要。

### 2. (1190,34) + P≥9

`cleanroom_rederivation_20260718/10_r3_judgment_20260720.md:19` 链条逐环：
- 「输入一侧/输出恰在对侧」「6×4 口恒在长边」「无同格同向双口」= strict 候选池模板几何（已逐条核实）；
- 「矩形外接驳容量每格≤4」= front 格方向容量（一格至多四向各一口）——几何上限，
  混流不改变一格能当几个口的 front（且该引理本就允许共享，比见证的 2 共享更宽）；
- P≥9 = 供电 halo 396 权重证书（840 放置不等式）——供电层。
- 对抗复核 `11_r3_adversarial_verdict_20260720.md` 14 攻击面 CONFIRMED，其攻击面中无 routing 前提。

### 3. SMM4/R4 U=(1188,18)

`b1_r4_1188_22_pb_20260723/README.md:40-90`：信任分层明示——A004 准入引理面=
ordinary membrane / conditional marked membrane / access-cell / power-halo / boundary
full-span「几何必要引理」；PB 只做引理后的有限尺寸算术。
marked 的构造（`cleanroom_rederivation_20260718/14_r4_next_certificate_python_gpt_pro_verbatim.md:44-82`）：
`marked = forced_mfg(58, 模板每侧口数超 2 的溢出) + raw_n(52 = 46 边界口+6 核心出口)`
——全部由模板口计数与 side 长度算术导出；access-cell 上限 `t(z)+m(z)≤4` 同 §2 的
front 方向容量。需求侧「52 raw 口恒活」来自 generic requirements 计数（端口精确计数
谓词层），非路由路径结构。SMM4 (1188,18) 用同一引理族（`verify_smm4_old_upper_v1.py:1159`
沿用 marked ceil 算术）。**原有条件（引用必须带 frozen A004 lemmas）不变，无新增。**

### 4a/4b. W0 3号死刑 与 H20

- 19 号文书第 4 步原文：「这是纯 body-front 几何计数，与 routing/class 分配方案无关」；
  判死口径=最弱要求（每台 ≥1 自由输入 front + ≥1 自由输出 front），canonical 级。
- 20 号：R2 行 22 台 M3 的杆触达计数矛盾（12 宽 halo ∩ 3 宽机身=14 列窗口→单杆≤5 台），
  放宽超域上枚举成立——纯供电层。
- 两者均 research-only、自限 scope，不构成全局 bound；即便层次归类也全部 routing-free。

### 5/6. UNKNOWN/censored 类

round45（roadmap 07-20 行原文「三锚点全 UNKNOWN=无上界证书」）、W2b 六跑、ab16 16 臂
——全部按 UNKNOWN/censored 记账，未见任何文书把它们引作上界或不可行证据。

## 需主线再深挖的残余

1. **无**——现役证书全部脱险。唯一提醒：若未来把「官方 routing 门对某布局判 INFEASIBLE」
   引作否定证据（目前无此用法，④路 censoring 合同明确挡住），该结论生来带 (b) 作用域条件，
   须在文书里显式标注。
2. A004 引理本身的既有条件（external-brain 准入、frozen receipt 引用纪律）与本次审计无关、
   维持原样；若未来 A004 家族出新引理涉及「膜上带道计数/逐商品穿越」类论证（routing 味），
   准入时要按 (b) 重审。

---

## 主线归档批注（非 fork 原文）

抽验两条承重引用属实：①SMM4 README（b1_r4_1188_22_pb_20260723）A004 准入段明文
「几何必要引理」（membrane/access-cell/power-halo/boundary full-span）；②PB-03 encoder
（r1_upper_bound_pb_encoder_v1.py:383-387）connector cells=`(1,anchor+1)`/`(anchor+1,1)`
front 常量格，无商品/路由结构。总判决采信：**(b) 保真缺口不触及任何在案证书，
双钳 U=(1188,18) conditional（原 A004 条件不变）/L=absent 原样成立。**
两条前瞻守则（官方 routing INFEASIBLE 作否定证据须标 (b) 条件；A004 家族 routing 味
新引理准入须按 (b) 重审）自本批注起生效。

## 批注二（(b)→(a)-修正翻案后的口径复核，2026-08-06 晚，矛盾清单 B 条）

1. **翻案记录**：本文书作于 (b) 判决当下；当晚 owner 语义定谳后翻案为 (a)-修正
   （模型 front 排他=正确保守编码），本盘点降级为「即使判 (b) 也零伤及」的双保险
   记录——这半句原批注已有，维持。
2. **新增复核（原「待深挖残余=无」节的修正）**：当晚新定谳的 binding 层残余缺口
   （模型单口单商品制 vs 游戏有线仓储口混吃）落在**端口计数谓词层**而非 routing 层，
   原审计口径未覆盖。补论证如下：A004 的 52=52 口计数（46 边界口 + 6 核心出口）
   全部是**输出/取货口**——游戏语义下边界口与核心出口本就是玩家逐槽单链配置的
   单商品口（warehouse-item-link，公理系 A11），「单口单商品」在这 52 口上是游戏
   事实而非模型保守。混吃缺口只存在于**输入口**（核心 14 进/箱 3 进），不参与
   52 计数。故 A004 与 (1190,34) 端口膜计数在新语义下**仍零伤及**；「双钳原样
   成立」结论经此复核后维持。残余：若未来引理把输入口计数引入证明，须按混吃
   语义重审（登记为前瞻守则第三条）。
