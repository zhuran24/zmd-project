# P2.0 特化设计稿 v1 —— refute 第一轮重判报告（2026-08-07）

**性质**：独立 refute 席对 `../P2_0_SPECIALIZED_DESIGN_V1.md`（下称「设计稿」）的对抗审查产物。研究层，不改生产代码、不改锁面、不改 canonical。
**触发**：owner 2026-08-07 指出设计稿的 split-free 探针把「每台机器占空」写死成均摊，这是未经辩护的约定。
**机器证据**：`split_free_probe_v2.py` + `split_free_probe_v2_receipt.json` + `split_free_probe_v2_stdout.log`（同目录，Fraction 精确、零浮点）。

**勘误二轮（20260807，外审份4 + 核签）**：本报告自身已过一道独立外部审查——GPT Pro 外审（`.artifacts/gpt_pro_review_batch_20260807/verdict/fen4/REPLY_VERBATIM.md` 的 R-01..R-10）+ 本地核签（同目录 `ADJUDICATION_fen4.md`）。R-01/R-04/R-07 判 OK，其余七条全部 ACCEPT（其中 **R-06 是 BLOCK 且我方见证自证**）。本报告按核签 §3.A4 就地订正，**订正涉及**：§0 后新增证据等级规则（R-10）、§1 逐商品独立判的表述（R-02）、§3 定理 1 补 4 条前件并**删掉多余的「任何最小车道路由」前件**（R-03 + 核签加强）、§3 定理 2 的措辞（外审 D-05）、§4 canonical 前件 (ii) 的定性与 616→622（外审 D-06，**按核签版、外审的 616 论据被驳回**）、§4 Part F 的格点标签与连续域证明来源（R-05）、§4 方向 b 的替换文本（D-05 + D-06）、**§5.2 整体替换**（R-06）、§6 三处越界措辞（R-08）、§9 欠账 2 与欠账 4（R-05 / R-09）、以及一处行号引错（核签 §1.4）。**被撤的旧文一律留痕，不静默覆盖。**
**外审自产的三个独立复核脚本已收编**（复跑逐字节相同）：`external_round2/`。其中 `independent_part_f_continuous_proof.py` 收作 **Part F 连续域证明的正式附录**；核签自产的 `aggregate_reading_check.py` 与 `true_min_lanes.py` 是 §4 那处反转的承重件。

---

## 0. 总判

设计稿有**三处独立缺陷**，全部在同一条论证链上（「网络级纯流不成立 ⇒ 甲案族空 ⇒ 推丙案」）：

（下表凡「设计稿 §N」指 `P2_0_SPECIALIZED_DESIGN_V1.md` 的节号，裸「§N」指本报告。全文同此约定。）

| # | 缺陷 | 性质 | 后果 |
|---|---|---|---|
| 缺陷一 | 命题 S2「每台机器占空 `duty = x_op/n_op` 唯一」是假的。唯一的只有聚合量 `x_op`；台间分配是 42 维自由度（§1） | 前提错，是**病根** | 设计稿 §2.4 的 6 例必然分流里 **4 例作废**；设计稿 §6 表 T3/T4/T5 三行判错（`u` 族不是「266 个全消失」而是「266 → 42 维」） |
| 缺陷二 | canonical `semantics.rate_lemma_scope` 的残道集合也是在同一均摊约定下算的，而引理**没把这条约定写进前件** | canonical 文本欠一条前件 | 引理结论在它自己声明的前件 (i)(ii) 下**不成立**（反例与措辞 diff 见 §4） |
| 缺陷三 | 设计稿 §4 甲案「P1 族对本实例是空的」是非蕴含：设计稿 §2.4 证的是「无中段稀释」不可满足，P1 说的是「每个物理状态只承载一种商品」，前者不蕴含后者 | 推理跳步 | 甲案的死刑判决与 Q2「P1 族已证为空」**双双不成立**，须撤回 |

**但设计稿的 headline 结论活下来了，而且被加固成无条件命题**。§3 把它写成两条可手算复核的定理：

- **定理 1（作物回流环必然分流）**：buckwheat 与 sandleaf 在任何合法占空分配下都必然分流，根因是种子回流环的奇偶性。
- **定理 2（速率分离不能推出物理纯度）**：在定理 1 的前件下，任何 rate-balance-admissible 占空分配都存在两条不同中间品的带段，速率之和 ≤ 带容量。**因此仅靠速率分离法无法推出 `P1`**——但这**不是**「`P1` 或网络纯流本身为假」（勘误二轮按外审 D-05 / 核签 ACCEPT 收缩；原标题「网络级纯流双体制**无条件失效**」与论述「均摊那一端破在中段细流，阶梯那一端破在端口残道，**没有第三条路**」已撤，理由见 §3）。

设计稿 §2.4 因此从「均摊约定内的实测结论」升格为无条件命题——这是本次重判最值钱的产出，丙案推荐理由的重写以它为地基。

**推荐路线（丙案双侧夹逼）不变**，理由改了：丙案胜出不再是因为「甲案族空」，而是因为丙案不欠支配引理；而甲案欠的支配引理义务在本轮之后**变大了**（多了一层「选定占空分配为约定」的支配义务，§5.2；**勘误二轮按外审 D-10 改成「视甲案冻结了什么，欠一到三条；只作见证启发式则零条」**）。

### 0.1 本报告的证据等级规则（勘误二轮新增，外审 R-10 / 核签 ACCEPT）

> 本报告中的「**legal allocation**」若只通过 `0 ≤ d ≤ 1, Σd = x_op` 检查，一律改称「**rate-balance-admissible allocation**」（速率平衡可容许分配）——它**不蕴含**该分配在游戏里可实现。
> 「**机器验证**」必须注明是**连续计数**、**固定 Fraction 复核**，还是 **1/660 格点 CP-SAT**。
> **几何可行、游戏稳态可达与模型可表达性，不得并入同一个【实测】标签。**

据此，本报告各结论的正确等级：

| 报告结论 | 正确等级 |
|---|---|
| v1 探针 `:97` 固定均摊 | 【实测·源码】 |
| 42 维 | 输入数值【实测】，维数【推导】 |
| 两条作物鸽巢（定理 1） | 【推导】 |
| Part C 的 17/19 lane assignment | 【实测·速率算术】 |
| staircase 是**游戏合法稳态** | 【假设】 |
| Part D | 【实测·1/660 格点】 |
| Part F 原脚本 | 【实测·1/660 格点】 |
| Part F **连续最优** | 【推导】，须附 exact interval proof（`external_round2/independent_part_f_continuous_proof.py`，已收编） |
| 定理 2 的「存在速率兼容对」 | 【推导】 |
| 「实际 shared-lane window」/「网络级 P1 失败」 | **未证；本轮已删，不得保留** |
| 「阶梯几何更容易」 | 【假设】；**本轮已删该断言** |
| §4 canonical 替换文本正确 | 【推导】，且已按核签版改写 |

---

## 1. 被修的缺陷与修法

设计稿的 `split_free_probe.py:97` 写 `duty[op] = x[op] / n_op[op]`，同一 operation 的每台机器占空相同。游戏里占空由供料决定，台间分配是布局能挑的自由度：6 台制瓶机总占空 11/2 既可以是「6 台各 11/12」，也可以是「5 台满速 + 1 台半速」。

**关于「逐商品独立判」**（勘误二轮按外审 R-02 / 核签 ACCEPT 改写）：**在 v1 已经把全网 duty 固定为统一均摊点的条件内，逐商品判定本身没有额外的耦合缺陷**——各商品之间没有待共同选择的 duty，因此不存在 duty 冲突。真正的耦合问题只在**放开 duty 之后**才出现：不同商品各自找到的**正见证**可能要求同一台机器取不同 duty，不能直接拼接。所以 v2 对**正结论**必须增加 Part C 的**统一 duty 联立验证**；而**全称的负证明**（某商品在所有分配下都必须分支）仍可逐商品独立进行。

> **原文（已撤）**：「v1 还有**第二个问题**：它**逐商品独立判**，而占空是机器级共享变量…判定必须整网联立。」撤销依据 = 外审 R-02 / 核签 ACCEPT：把它列成 v1 的**独立缺陷**不精确——在 v1 自己的固定均摊前件内它不是缺陷；它只是**放开 duty 后正见证必须联立**的理由。Part C 仍然必要，但理由要换。

v2 探针（`split_free_probe_v2.py`）放开占空为逐台变量（每台 `d_i ∈ [0,1]`，同 op 各台 `Σd_i = x_op`），并给出整网一致的判定。总量账（`x_op` / `n_op` / 266 实例普查断言）与 v1 同源、未改。

### 占空自由度的真实边界

| | |
|---|---|
| 17 个 operation 里 **10 个占空被钉死**为全满速 | `x_op = n_op` 时 `Σd_i = n`、`d_i ≤ 1` 唯一解全 1 |
| 剩下 **7 个有台间分摊自由度** | crusher_buckwheat / crusher_sandleaf / filling_capsule / grinder_fine_buckwheat / molding_bottle / seed_collector_buckwheat / seed_collector_sandleaf |
| **闲置（duty = 0）合法但无空间** | `n_op = ceil(x_op)`，少跑一台的话剩下 `n-1` 台全满速也只有 `n-1 < x_op`，够不到产量。所以每台都必须 `d_i > 0` |

「允许部分机器闲置」这条自由度在本实例里合法但用不上（详见 §7）；真正起作用的只有**台间不均摊**。

### 占空自由度的维数：42

219 台 recipe-backed 机器的占空 `u[i]` 构成一个多胞形：`u[i] ∈ [0,1]`，每个 operation 一条聚合等式 `Σ_i u[i] = x_op`。

| | 台数 | 说明 |
|---|---|---|
| 被钉死为 `u = 1` | **170** | 10 个 `x_op = n_op` 的 operation |
| 仍是变量 | **49** | 7 个自由 operation，受 7 条聚合等式约束 |
| **净自由度** | **42 维** | 5 + 10 + 2 + 5 + 5 + 5 + 10（各 op 的 `n_op − 1`） |

这 42 维是满维的（每个 `x_op` 都严格落在两个整数之间）。设计稿把这 49 台冻结在 11/12 与 21/22 两个值上（表 A 的「27 台 11/12、22 台 21/22」），等于在 42 维多胞形里挑了一个点当成唯一解。170 那个数字本身没错——它恰好就是被钉死的那部分。

---

## 2. 六例重判结果

| 商品 | v1 判据（均摊） | v2 判决（自由占空） |
|---|---|---|
| **buckwheat** | 鸽巢 11 产道 < 12 耗道 | **仍必然分流**，对任意占空成立（§3） |
| **sandleaf** | 鸽巢 21 < 22 | **仍必然分流**，对任意占空成立（§3） |
| buckwheat_seed | CP-SAT INFEASIBLE（12 产道 / 11 耗道） | **翻案**：split-free 存在 |
| sandleaf_seed | CP-SAT INFEASIBLE（22 / 21） | **翻案**：split-free 存在 |
| sandleaf_powder | CP-SAT INFEASIBLE（33 / 32） | **翻案**：split-free 存在 |
| steel_block | 鸽巢 17 < 18 | **翻案**：split-free 存在 |

必然分流的商品占路由流量从 **3,375 / 9,135 = 37%** 降到 **960 / 9,135 = 10.5%**（buckwheat 330 + sandleaf 630 件/分钟）。

判决建立在三条相互独立的证据上：

**(a) 车道计数定理（Part B，不依赖求解器）**。对每种商品，精确求出产道数在所有合法占空分配下的最大值与耗道数的最小值。`min(耗道) > max(产道)` 时鸽巢对任意分配成立。只有 buckwheat（11 vs 12）与 sandleaf（21 vs 22）触发；另外 4 种的 `min(耗道) ≤ max(产道)`，鸽巢论证失效。

**(b) 显式全局见证（Part C）**。一份整网一致的占空分配下，19 种商品里 **17 种同时 split-free**，车道表与整道指派表全部落在收据里，用 Fraction 独立复核（复核代码与 CP-SAT 无关）。

**(c) CP-SAT 交叉验证（Part D）**【实测·1/660 格点】。对 **v1 判死的那六种**商品在占空格点 1/660 上重跑可行性：buckwheat / sandleaf 得 INFEASIBLE，另 4 种得 OPTIMAL，与 (a)(b) 一致。**格点上的 INFEASIBLE 不构成连续域 INFEASIBLE**——负结论由 (a) 的连续计数承担，Part D 只是交叉验证（§9 欠账 2）。

(a) 给的是上确界、(b) 给的是达到该上确界的构造，两者吻合 ⇒ **17 就是能同时 split-free 的商品数上确界**。

### 见证：阶梯式占空

规则一句话：**能满速的满速，余数落在最后一台**。

| operation | 占空 |
|---|---|
| crusher_buckwheat / grinder_fine_buckwheat / molding_bottle / seed_collector_buckwheat | `[1, 1, 1, 1, 1, 1/2]` |
| crusher_sandleaf / seed_collector_sandleaf | `[1 ×10, 1/2]` |
| filling_capsule | `[1, 1, 3/4]` |
| 其余 10 个 operation | 全部 `1` |

合计 212 台满速 + 6 台半速 + 1 台 3/4（对比均摊的 170 台满速 + 27 台 11/12 + 22 台 21/22）。

这份分配下绝大多数车道速率恰好是 1，整道指派退化成排序双射，**可以手验**。三个代表性例子：

- **steel_block**（v1 的鸽巢）：refinery_steel 17 台全满速 ⇒ 17 条速率 1 的产道。耗侧 molding_bottle 5 台满速（每台吃 2 件/tick = 2 条满道）+ 1 台半速（吃 1 件/tick = 1 条满道）= 11 条，parts_maker 6 台满速 = 6 条，合计 **17 条速率 1 的耗道**。17 对 17 完美匹配。均摊下 molding_bottle 每台吃 11/6 需 2 条道 ⇒ 12 + 6 = 18 条，鸽巢正是均摊制造出来的。
- **buckwheat_seed**（v1 的 CP-SAT INFEASIBLE）：seed_collector_buckwheat 5 台满速（每台出 2 件/tick = 2 条满道）+ 1 台半速（出 1 件/tick = 1 条满道）= 11 条速率 1 的产道；耗侧 planter_buckwheat 11 台满速 = 11 条速率 1 的耗道。均摊下每台出 11/6 要 2 条道、每条 ≥ 5/6，12 条道塞 11 个格子必有一格收两条、和 ≥ 5/3 > 1——不可行的根源同样是均摊。
- **sandleaf_powder**：crusher_sandleaf 10 台满速（每台出 3 件/tick = 3 条满道）+ 1 台半速（出 3/2 = 1 条满道 + 1 条 1/2）= 32 条；耗侧 grinder_dense_blue_iron 17 + grinder_dense_source 9 + grinder_fine_buckwheat 5 台满速 = 31 条满道，加 grinder_fine_buckwheat 那台半速的 1 条 1/2 道 = 32 条。两侧多重集都是「31 条 1 + 1 条 1/2」。

---

## 3. 两条无条件定理

本节两条定理都不依赖占空约定、不依赖求解器，可以纯手算复核。它们是本次重判最值钱的产出：设计稿 §2.4 原本是「在均摊约定内实测出来的结论」，经此升格为**无条件命题**。

### 定理 1（作物回流必然分支——**对占空分配与车道约定均无关**，条件是当前实例与当前直连路由语义）

**前件**（勘误二轮按外审 R-03 / 核签 ACCEPT 补全）：

1. 使用**当前 frozen `production_targets`** 与**当前 mandatory operation counts**；
2. **每个正占空消费者必须经当前 route graph 获得正流量**；
3. **warehouse-bridge routing 继续被当前模型排除**；
4. 使用**当前端口容量与精确端口计数语义**。

> 在上述前件下，对**任意满足聚合占空等式的 duty 向量**，buckwheat 与 sandleaf 均必须出现**至少一次一对多分支**。

**本定理不要求先证明某个 70×70 几何布局存在**；它是对**所有可能几何实现**的必要条件（几何存在性不是负定理的前件——即使根本没有几何布局，该全称命题也只是空真，不会变成错误）。

> **标题与前件的两处改动（勘误二轮）**：
> - 原标题「作物回流环**必然分流**」+ 原陈述「**对任何满足 `production_targets` 的占空分配与任何最小车道路由**」。**「无条件」这个说法已撤**（外审 R-03 / 核签 ACCEPT）：warehouse bridge、mandatory counts、端口 / 直连语义**不是「几何摆不摆得下」，而是定理所量化的路由系统本身**；漏掉它们会把一条**实例定理**误写成**游戏的一般定理**。`GAME_RULE_IMPACT_AUDIT.md:96` 的 `warehouse_bridge_exclusion` 给出了反事实路径：若桥合法，商品可先入仓再从边界重发，11 个源与 12 个直接消费者之间的匹配关系会被绕开。本报告 §9 欠账 3 自己也承认结论依赖当前普查。
> - **「与任何最小车道路由」这个前件是多余的，已删**（核签加强，外审未发现）。理由：若某台 planter 的满速产出被铺到 2 条道上，**那本身就是一次一对多分支**，结论直接成立；若不铺开，则 11 条产道整条进入 12 个必须为正的耗口，鸽巢矛盾。**两种情况都得出分支**，所以定理对**任何**车道约定成立，不只是最小车道约定。删掉它是**净加强**。

**证明（buckwheat；sandleaf 同构）**。

1. 产侧：planter_buckwheat 的 `x_op = 11 = n_op`，故 11 台占空被 `Σd = 11`、`d ≤ 1` 唯一钉死为全 1；单机产出 1 件/tick，带容量 1 ⇒ 每台恰 1 条产道 ⇒ **恰 11 条产道**，每条速率恰 1。
2. 耗侧：crusher_buckwheat 与 seed_collector_buckwheat 各需 `Σd = 11/2`，每台 ≤ 1 ⇒ 各至少 `⌈11/2⌉ = 6` 台在跑；两者的 `n_op` 都恰是 6 ⇒ 各恰 6 台、每台进料速率 `d_i ∈ (0,1]` ⇒ 各恰 6 条耗道 ⇒ **合计 12 条耗道**，每条速率 > 0。
3. 「无分流」要求每条产道整条进入某条耗道、且每条耗道至少收到一条产道。11 条产道盖不住 12 条耗道。∎

**根因是种子回流环的奇偶性**：planter 的产量 N 被 1:1 劈给「粉碎」与「采种」两支（采种机 1 进 2 出、种植机 1 进 1 出 ⇒ 采种支恰占一半），奇数 N 劈半后两支各需 `⌈N/2⌉` 台，合计 `N+1 > N`。buckwheat 是 11，sandleaf 是 21，都是奇数。这条与占空分配无关、与布局无关，只跟配方比例和 mandatory 台数有关。

**被迫的细流段有多细（Part G）**：被劈开的那条产道速率恰为 1，劈出的两段（或更多段）总和恰为 1，故**最细一段 ≤ 1/2**——这是不依赖求解器的上界，对任意占空分配成立。阶梯占空恰好达到这个上界：

| 商品 | 均摊占空 | 阶梯占空 | 上界 |
|---|---|---|---|
| buckwheat 最厚的最细段 | 1/3（13 个分流点） | **1/2（1 个分流点）** | 1/2 |
| sandleaf 最厚的最细段 | 7/22（23 个分流点） | **1/2（1 个分流点）** | 1/2 |

全网分流点从 36 个降到 2 个。均摊占空下的 1/3 与 7/22 与设计稿 `maxmin_segment_probe.py` 的独立实现逐值吻合（本批对该探针的交叉验证通过）。承重的是阶梯与自由占空那两栏的 1/2，两者都以 OPTIMAL 收敛；均摊那一栏的 sandleaf 在本批 180 秒限时内只到 FEASIBLE（找到 7/22 未证最优），它的值由设计稿探针的独立计算佐证，且不承重——它只用来说明「均摊分配更差」。

### 定理 2（速率分离不能无条件推出物理纯度）

> 在定理 1 的四条前件下，对**任意满足聚合占空等式的 duty 向量**，都存在两条**不同中间品**的带段，其速率之和 ≤ 带容量。

**证明**。由定理 1，buckwheat 必然分支；被劈开的那条产道速率恰为 1（产侧占空被钉死为全 1），劈出的各段总和恰为 1，故其中最细一段 `≤ 1/2`。sandleaf 由定理 1 独立地同理，也有一段 `≤ 1/2`。buckwheat 与 sandleaf 都是 `sink_kind: none` 的中间品且互不相同，两段之和 `≤ 1` = 带容量。∎

**这条定理证明了什么、没证明什么**（勘误二轮按外审 D-05 / 核签 ACCEPT 钉死）。先把三个谓词分开：

| 谓词 | 含义 |
|---|---|
| `NS` | 一条源流在网络中**从不发生一对多分支** |
| `RC` | 存在两个**不同商品**的正速率段，且速率和不超过容量 |
| `P1` | 同一个**物理组件**不被两个商品共同使用 |

- 定理 1 证明的是 **`¬NS`**；守恒再推出 **`RC`**（即本定理）。
- 但 **`RC` 不构造两个段的几何共址**、**不构造汇流器 / 仲裁 / 共同下游**、**不推出某个布局违反 `P1`**。
- **`¬NS` 本身也不违反 `P1`**——同商品分支后的两条带仍可各自保持单商品。

所以本定理的算术核心成立，**可以下的唯一结论是**：

> **仅靠「所有不同商品段的速率和都大于容量」这一速率分离法，无法无条件推出 `P1`。**

**它不能被命名为「`P1` 或网络纯流本身无条件为假」。** 实际混流的存在还需要几何共址、汇流器语义与完整布局见证——本报告一条都没给。

> **原文（已撤，勘误二轮）**：标题「定理 2（**网络级纯流双体制无条件失效**）」+ 陈述「即：**网络级纯流强制**（「任两种中间品不得共用一条带道」）**在任何合法分配下都不成立**」+ 论述段「**这条定理的价值在于它堵死了两个方向**…**没有第三条路**…**恒破**」。
> 撤销依据 = 外审份4 D-05 / 核签 ACCEPT：传导链「被迫分支 → 各有一段 ≤ 1/2 → 两段和 ≤ 1 → **网络纯流恒假 / P1 不能用**」在最后一步越了级。**注意这与本报告 §5.3 撤销甲案死刑的理由（分流不违反 P1）是同一条一致性**——外审 R-07 判我方撤销死刑**正确**，正是因为「必须分支」不蕴含「违反 P1」；那么同一份报告就不能一边用它撤死刑、一边用它宣布「网络级纯流无条件为假」。

**两个端点的算术对比**（保留为数字对照，**不是**网络级断言）：

| 走哪一端 | 端口残道 | 被迫的细流段 | 「靠速率分离排除共道」 |
|---|---|---|---|
| 均摊（残道最优，Part F + `external_round2/independent_part_f_continuous_proof.py` 连续域证） | 最细 5/6 | 最细 7/22 | 在中段细流上失效 |
| 阶梯（车道最省，§4） | 最细 1/2 | 最细 1/2 | 在端口残道上失效 |
| 任何 rate-balance-admissible 分配 | — | 恒有 ≤ 1/2 的段（定理 2） | **恒失效** |

想把端口残道抬到 > 1/2 就得往均摊靠，那样中段细流更细；想把中段细流抬到最厚（1/2）就得往阶梯靠，那样端口残道掉到 1/2。全网最细段在所有分配上的可达最大值恰好是 `1/2`（上界由定理 2 给出，阶梯占空达到），而**靠速率分离排除共道需要它严格 `> 1/2`**。

---

## 4. canonical `rate_lemma_scope` 欠的那条前件是「占空约定」

`rules/canonical_rules.json` 的 `semantics.rate_lemma_scope` 声明两条前件：(i) 按 frozen `production_targets` 满产；(ii) 最小车道分配约定。在 (i)+(ii) 下断言：中间品的逐道残余速率两两之和 > 1 ⇒ 任两种中间品不得共用一条带道。

**前件 (ii) 的原文带一句消歧补充**（逐字回源 `rules/canonical_rules.json` 的 `semantics.rate_lemma_scope.statement`）：

> (ii) minimal-lane-allocation convention - each commodity occupies the fewest belt lanes its rate admits; **a layout that deliberately spreads one commodity over more lanes to dilute per-lane rates leaves this precondition family and the lemma asserts nothing about it.**

这半句把 (ii) 定性为**反稀释条款**，**不是**「全网车道总数最小化」的目标。

支撑该条目的机器复算是 `docs/research/canonical_batch_20260807/rate_lemma_recompute.py`，其中 `:34` 的 `util = runs / machines` 与 `:37` 的 `per_machine_runs = runs / machines` —— **同一个均摊约定**。
> **行号订正（勘误二轮，核签 §1.4）**：原文引「第 36 行 `per_machine_runs = runs / machines`」。回源实测 `:36` 是 `full_rate += 1`（与均摊无关），被引的字面在 **`:37`**；`:34` 是同一约定的另一处。兄弟线 `docs/research/rule_system_redesign_20260807/FINAL_DESIGN.md:186` 已经引对为「`:34/:37`」，本报告按兄弟线订正。（同批订正的还有 `../P2_0_SPECIALIZED_DESIGN_V1.md` §2.5 与 `split_free_probe_v2.py:25` 的同一处引用。）

### 反例

阶梯占空**在逐端口读法下**同样满足 (ii)，**在反稀释读法下与均摊同样都在族内**（读法辨析见下节，勘误二轮按外审 D-06 声明读法；原文只写「阶梯占空同样满足 (i) 与 (ii)」而未声明读法，是真缺陷）。在 canonical 自己的残道定义（`residual = rate − (ceil(rate) − 1)`，即最小车道数下可能出现的最细一条）下重算：

| 占空分配 | 中间品残道集合 | 最小残道 | 两两之和 ≤ 1 的反例 |
|---|---|---|---|
| 均摊（canonical 现行） | {5/6, 19/22, 10/11, 11/12, 21/22, 1} | 5/6 | **0 对** |
| 阶梯（本批见证） | {1/2, 1} | 1/2 | **40 对** |

例：grinder_fine_buckwheat 那台半速机器的 fine_buckwheat_powder 出口残道 = 1/2，molding_bottle 那台半速机器的 steel_bottle 出口残道 = 1/2，两者是不同中间品，和 = 1 ≤ 带容量 1 ⇒ 共道速率合法。引理结论不成立。

### 前件 (ii) 根本不约束占空分配——完备二分，两个分支都杀掉引理

**先把读法说清楚**（勘误二轮按外审 D-06 / 核签 ACCEPT 的诊断）。「each commodity occupies the fewest belt lanes its rate admits」至少有两种读法：

- **逐 active port 的局部最小**：每个端口速率 `r_p` 使用 `⌈r_p/C⌉` 条道。**均摊与阶梯都满足。**
- **逐商品聚合的全局最小**：每种商品两侧总道数达到 `⌈F_k/C⌉` 的聚合下界。

本报告原文在同一段论证里**切换了量化单位**——用第一种读法说「阶梯同样满足 (ii)」，又用第二种读法的聚合道数攻击均摊，两处都没声明读法。这条诊断成立，本轮订正。

**但结论不需要先定读法。** canonical 原文的反稀释补充句把车道侧堵住之后，剩下一个**完备二分，两个分支都杀掉引理**：

- **分支一：均摊在族内。** 均摊的每个端口都只用 `⌈r_p⌉` 条道、**没有为了稀释而刻意铺开**，阶梯同样如此 ⇒ **两份都在反稀释族内**。但残道集合是 `{5/6, 19/22, 10/11, 11/12, 21/22, 1}` vs `{1/2, 1}`（0 对 vs 40 对反例）⇒ **(ii) 不决定残道集合，(i)+(ii) 推不出结论**。
- **分支二：均摊出族。** 若把「均摊对 5 种商品用了 12 条道去装 11 的量」也算作 spreading，则均摊落在族外——而 canonical 记的那次机器复算（`rate_lemma_recompute.py:37`）**正是在均摊上做的** ⇒ **该条目的支撑证据是在它自己的前件族外算出来的**。

核心是：**前件 (ii) 根本不约束占空分配，而占空分配才是决定结论成不成立的东西。**

### 车道总数的真实数字：628 / 622 / **622**（不是 616）

逐商品比对总车道数：

| 商品 | 聚合下界 `⌈F_k/C⌉`（产/耗各） | 均摊（产,耗） | 阶梯（产,耗） |
|---|---|---|---|
| buckwheat_powder | 11 | 12, 12 | **11, 11** |
| buckwheat_seed | 11 | 12, 11 | **11**, 11 |
| sandleaf_powder | 32 | 33, 32 | **32**, 32 |
| sandleaf_seed | 21 | 22, 21 | **21**, 21 |
| steel_block | 17 | 17, 18 | 17, **17** |

全网车道总数：**均摊 628，阶梯 622**，而**在所有 rate-balance-admissible 占空分配上的可达最小值 = 622**——**阶梯正是它的一个最小化解**，均摊多用 6 条。

**逐 (op, port) 的车道数下界 = `max(n_op, ⌈c_p · x_op⌉)`**，两条独立理由：①`Σ⌈a_i⌉ ≥ ⌈Σa_i⌉`；②每台占空 > 0 ⇒ 每台至少 1 条道。验算件 `external_round2/true_min_lanes.py` 的输出：

```
制造端口车道数：逐项下界合计=568  均摊=574  阶梯=568
加 52 源口 + 2 终品汇口：下界=622  均摊=628  阶梯=622
阶梯是否处处达到逐项下界: True
```

超出下界的 6 个端口全部由均摊造成：`crusher_buckwheat out buckwheat_powder`(11/12)、`crusher_sandleaf out sandleaf_powder`(32/33)、`grinder_fine_buckwheat in buckwheat_powder`(11/12)、`molding_bottle in steel_block`(11/12)、`seed_collector_buckwheat out buckwheat_seed`(11/12)、`seed_collector_sandleaf out sandleaf_seed`(21/22)。

> **原文（已撤，勘误二轮）**：标题「**阶梯占空更满足前件 (ii)，不是更不满足**」+ 「全网车道总数：均摊 628，阶梯 622，**理论下确界 616**」+ 「**均摊占空对 5 种商品用了多于其速率所需的车道数，字面上并不满足前件 (ii)；把车道用到最少的那份分配，恰恰是打破引理结论的那份。**」
> **撤销依据（这一处是核签自产的增量，外审也判错了同一个数）**：
> **616 对任何合法占空分配都不可达。** `qiaoyu_capsule` 的聚合下界 `⌈F_k/C⌉ = ⌈11/20⌉ = 1`，但 `filling_capsule` 有 **3 台**机器、`n_op = ⌈x_op⌉ = 3` 使**任何一台都不能闲置** ⇒ 每台出口速率 > 0 ⇒ **产侧至少 3 条道**，聚合下界只给 1 条。`valley_battery` 同理（3 台）。验算件 `external_round2/aggregate_reading_check.py`。
> 所以：①「616」这个数不该出现在任何比较里；②「均摊字面上并不满足 (ii)」是拿一个**满足集为空**的读法当门槛，推不出这个结论；③「最满足前件的分配恰是破结论的分配」不成立——按反稀释读法两份都在族内。
> **外审份4 D-06 在同一个数上判错得更远**：它据 616 断言「均摊 628 与阶梯 622 都高于 616，因此**两者都不满足** (ii)」，核签判 **REFUTE**（`ADJUDICATION_fen4.md` §1.3 / §2 D-06 / §3.C 的 C1）。**本节按核签版改写，不采用外审的替换文本。**

### 均摊是残道最优约定，但最优 ≠ 前件蕴含

Part F 逐 operation 求「最大化最小中间品残道」：

- 【**实测·1/660 格点**】Part F 的现有 CP-SAT 输出在 **1/660 网格上**取得均摊最优（`split_free_probe_v2.py:499` 的 docstring 明写「格点 1/LATTICE」、`:518` 是 `NewIntVar(1, D, ...)`）。
- 【**推导·连续域**】`external_round2/independent_part_f_continuous_proof.py` 的 **exact interval proof** 对每个自由 operation 枚举 `residual > t` 的精确 duty 区间，证明不存在严格改进；均摊达到该界。**七个 operation 的连续最优值与本报告的格点数字全等**（`crusher_buckwheat 5/6`、`crusher_sandleaf 19/22`、`filling_capsule 5/6`、`grinder_fine_buckwheat 5/6`、`molding_bottle 5/6`、`seed_collector_buckwheat 5/6`、`seed_collector_sandleaf 10/11`）。
  例：`crusher_buckwheat` 若所有相关 residual 都严格大于 `5/6`，每台 duty 必须严格大于 `11/12`，六台之和便严格大于 `11/2`，矛盾。
- **因此连续域结论成立**，全局 max-min 残道 = 5/6，与 canonical 现行数字一致——**但证据来源是 exact interval proof，不是原 Part F 的 CP-SAT 日志**。

> **原文（已撤，勘误二轮）**：「Part F 逐 operation 求…**每个 operation 的最优点都落在均摊上**，全局 max-min 残道 = 5/6」——**无网格限定词**。撤销依据 = 外审 R-05 / 核签 ACCEPT（且**外审自带补丁，本条是净收入不是净损失**）：这与 Part D 的病同型，而 §9 欠账 2 原来**只登记了 Part D**，漏了 Part F 与 Part G。连续结论本身**成立**，只是原来那份证据（格点 CP-SAT）撑不起它。

所以均摊是**为纯流强制挑的最有利约定**——但它是一条约定，不是 (i)+(ii) 蕴含出来的结论。占空还能让残道任意薄：例如 crusher_buckwheat 取 `[1,1,1,1,0.99,0.51]`，其 buckwheat_powder 出口残道只有 0.02。

### 影响范围

该条目 `predicate_status: "non_predicate"`、`usage_rule` 明写「rate arithmetic never enters a certificate」，**不进认证链、不动六谓词、不是 soundness 缺陷**。它承重在叙述层：凡引用该引理论证「某某建模是 without-loss-of-generality 而不只是保守」的地方，都要补上「且占空按均摊分配」这条前件，或改成条件式表述。

### 处置与建议措辞 diff

**本批不动 canonical**（`fab718a` 刚封；该条目 non_predicate、不伤认证链）。处置 = 挂下一批 canonical freeze-ritual。下面两个方向的措辞都写出来，供 owner 与 freeze-ritual 批直接取用；二选一即可，**方向 b 更强**。

共同的理由段（两个方向都该带上，它解释了当初选均摊为什么不是错误、只是没声明）：

> 均摊分配（每 operation 各台等占空）是**最大化最小残道**的最优约定：逐 operation 的 exact interval proof（连续域，非格点）显示每个 operation 的最优点都落在均摊上，全局 max-min 中间品残道 = 5/6。所以原复算选它是选了对纯流强制最有利的那份分配；缺的只是把这个选择声明成前件。
>（勘误二轮：证据来源从「Part F 的 1/660 格点 CP-SAT」改为 `external_round2/independent_part_f_continuous_proof.py` 的连续域证明，R-05。）

---

**方向 a —— 补一条显式前件（改动最小）**

在 `statement` 的前件列表里，(ii) 之后插入 (iii)：

> `(iii) uniform per-machine duty convention - within each operation every machine runs at the same duty x_op / n_op. The production targets pin only the aggregate activity x_op; the per-machine split is a 42-dimensional free polytope (49 machines across 7 operations, 7 aggregate equalities), and the residual-rate set below is computed at the uniform point of that polytope. A layout that distributes duty unevenly leaves this precondition family; see docs/research/p2_0_specialized_20260807/refute_round1/ for a legal non-uniform allocation under which the residual set collapses to {1/2, 1} and pairwise-sum<=1 counterexamples number 40.`

并把 `statement` 里 `Under (i)+(ii):` 改成 `Under (i)+(ii)+(iii):`。

**代价**：(iii) 是一条**布局可违反**的前件——它比 (i)(ii) 弱，因为占空分配是布局自己挑的。任何引用该引理的叙述都要连带 discharge (iii)，而 (iii) 在 certified 语境下 discharge 不了（见 §5.4 下游①）。

---

**方向 b —— 改成分配无关版本（推荐）**

保留逐口纯流强制的**条件式**表述，另加一条**带前件的**否定结论。**主修 = 把「占空约定」声明成前件**（这才是缺的那条）；外审建议的「minimal lane allocation 是逐 active machine port 局部最小」作为**附加澄清条款**并入，但**不能替代**主修。`statement` 改为（勘误二轮按核签 D-06 重写）：

> `Scope declaration for the intermediate rate-separation calculation (rate lemma; non-predicate, rate-arithmetic only). Preconditions: (i) full production at the frozen production_targets; (ii) minimal-lane-allocation convention - each commodity occupies the fewest belt lanes its rate admits, quantified LOCAL TO EACH ACTIVE MACHINE PORT: a port of rate r_p is decomposed into exactly ceil(r_p / C) positive lanes whose rates sum to r_p; no claim of a globally minimum total lane count is made; a layout that deliberately spreads one commodity over more lanes to dilute per-lane rates leaves this precondition family. (iii) A STATED PER-MACHINE DUTY VECTOR. The frozen targets determine the aggregate activity x_op of each operation but DO NOT determine its per-machine duty vector: the per-machine split is a free 42-dimensional polytope (49 machines across 7 operations, 7 aggregate equalities). Any duty vector d used by this calculation must be stated explicitly and satisfy 0 <= d_i <= 1 and sum_{i in op} d_i = x_op. Preconditions (i)+(ii) do NOT constrain d, and d is what decides whether the conclusion below holds. At the uniform duty vector (every machine of an operation at x_op/n_op, which maximizes the minimum residual - established by exact interval proof over the continuous domain, not by a lattice search): intermediate residual-rate set {5/6, 19/22, 10/11, 11/12, 21/22, 1}; every pair of distinct intermediate residual lanes has rate sum greater than C, so no two intermediate commodities may share one belt lane. THIS IS A CONDITIONAL RESULT FOR THAT STATED DUTY VECTOR. At the staircase duty vector, the residual-rate set is {1/2, 1} and the archived calculation contains 40 distinct-commodity pairs whose rate sum is at most C; this establishes allocation dependence AT THE RATE-ARITHMETIC LEVEL only - it does not by itself establish geometric co-location, an actual shared lane, or a game-reachable steady state. Machine-verified recompute (2026-08-06) established the uniform-allocation numbers; the allocation dependence was established 2026-08-07 (docs/research/p2_0_specialized_20260807/refute_round1/). UNCONDITIONAL PART (subject only to the current instance and the current direct-transport routing semantics): under the current mandatory operation counts, with every positive-duty consumer required to receive positive flow through the current route graph, and with warehouse-bridge routing excluded, buckwheat has 11 full-rate producer machines and 12 positive consumer machines, and sandleaf has 21 and 22 respectively; hence each must branch at least once, and each has at least one branch segment of rate at most C/2. CONSEQUENTLY RATE ARITHMETIC ALONE CAN NEVER ESTABLISH PHYSICAL COMMODITY PURITY FOR ALL DUTY VECTORS. This is NOT a claim that any legal layout actually mixes those two segments, nor that physical-purity constraints are themselves invalid. Final-product terminal segments may share capacity only when the actual subrates carried by the shared segment sum to at most C; the full qiaoyu and valley terminal flows sum to 23/20 C and therefore do not fit in one lane.`

**为什么推荐 b**：a 把一条布局可违反的约定塞进前件，等于把引理的可用范围缩到一个没人能 discharge 的族里；b 把「均摊下成立」诚实地标成**占空相关**的条件结论，同时把**在当前实例与当前路由语义下无条件成立**的那半（定理 1 + 定理 2 的算术核心）写进去——后者才是能被下游安全引用的部分。b 也顺带修掉一处现存的措辞过强：现文 `the only lanes on which commodity mixing remains rate-legal are the final-product terminal segments` 在任何分配下都不成立（定理 2 给出终端段之外的速率兼容对）。

> **本方向的替换文本在勘误二轮被改过三处（原文已撤）**：
> ① 原文写 `NETWORK-LEVEL PURE FLOW IS UNCONDITIONALLY FALSE` —— **撤**。按外审 D-05 / 核签 ACCEPT，可写进 canonical 的只有「**rate arithmetic alone can never establish physical commodity purity for all duty vectors**」；`RC`（速率兼容对存在）不蕴含 `¬P1`。
> ② 原文写 `so a rate-legal shared-lane window always exists` —— **撤**。「window」这个词把速率兼容说成了实际共道；且必须显式声明**不主张任何合法布局真的混流**。
> ③ 原文把无条件部分写成完全无前件 —— **撤**。按外审 R-03 / 核签 ACCEPT，必须带上「当前 mandatory counts / 经当前 route graph / warehouse-bridge 排除 / 当前端口容量与精确计数语义」四条，否则会把一条**实例定理**误写成**游戏的一般定理**。
> 另外新增了 (iii) 占空前件与 (ii) 的逐端口量化声明——**前者是主修**（`ADJUDICATION_fen4.md` §3.B1：若只采外审原方案「声明逐端口读法」，占空前件仍未声明，洞还在）。
>
> **owner 决策项**：这条最终归 owner + 下一批 canonical freeze-ritual，本报告不替 owner 判。**本批 canonical 一个字未动。**

**两个方向都不需要动的**：`predicate_status`、`usage_rule`、`applies_to`、`axiom_derivation`。逐口纯流强制在均摊下的复算结论（反例 0 对）本身没错，本批独立复现一致。

---

## 5. 三层连锁结论重写

### 5.1 ①「靠速率分离推不出纯度」——成立，且证明比原来强

**（标题勘误二轮改写：原「①『网络级纯流被证伪』——成立，且升级为无条件命题」已撤，外审 D-05 / 核签 ACCEPT。被证伪的不是「网络级纯流」这个命题，而是「靠速率算术就能推出物理纯度」这条推理路径。）**

设计稿此结论**站得住，而且证明比原来强**：原证明依赖均摊约定下的 6 例，新证明是 §3 的定理 2，只用两条鸽巢，对任意 rate-balance-admissible 占空分配成立（前件 = 定理 1 的四条）。

由此产生的**速率兼容对**数随分配变化，但永不为零（勘误二轮：原称「混流窗口」，该词把速率兼容说成了实际共道，已按外审 D-05 / 核签 ACCEPT 统一改称「速率兼容对」）：

| 占空分配 | 全网最细段 | 不同中间品的速率兼容对 |
|---|---|---|
| 均摊 | 7/22 | 15 对（与设计稿 §2.4 的 15 对**逐对相同**，本批独立复现） |
| 阶梯 | 1/2 | 10 对（全部恰好等于带容量，即刚好合法） |

**给 mixflow / U-01 线的修正**：设计稿 §7.1 的「混流只可能发生在分流细流段，主干仍然逐口纯流」**只在均摊约定下成立**。阶梯分配下速率兼容对出现在**端口残道**上（半速机器的进出口），不在分流段。所以这条「收窄」不能无条件给 mixflow 线；无条件成立的收窄只剩一句（勘误二轮按外审 D-05 / 核签 ACCEPT 改写）：

> **速率算术恒能找到一对不同中间品的正速率段，其速率之和 ≤ 带容量。** 这句话**既不构造物理共道，也不把这对段限定在细流段**——涉及的商品集合与出现位置都随分配而变。
> 原文（已撤）：「**混流窗口的段速率永远 ≤ 1/2**」——「窗口」一词把 `RC` 说成了实际共道。

设计稿 §7.2 对 `item_admission_port_exclusion` 理由 (a) 的措辞补丁（Q7）方向不变，但措辞要从「中间品的最小车道之间没有东西可分拣」再放宽——因为最小车道本身在某些分配下就只有 1/2。裁决结论仍不受影响（它靠独立的 (b)(c) 两条，不依赖速率算术）。

### 5.2 ②「常数系数形态」——在「选定一份占空分配」的前件族内确实复活，但代价是新增一条支配义务

#### 死因换了一层，而且换到了更靠前的位置

设计稿给「常数系数形态不成立」的死因是**中段被切细**（前件 L 不可满足）。这个死因仍然有效（§5.1），但它不是第一死因——在它之前还有一层：

> **无条件地看，端口速率根本就不是常数。** 端口速率 = 满速速率 × `u[i]`，而 `u[i]` 是 42 维多胞形里的自由变量（§1）。不先固定占空分配，「格 c 上商品 k 的速率」连**在端口处**都没定义，谈不上被中段切细。

所以正确的死因是分层的：

| 层 | 死因 | 状态 |
|---|---|---|
| 第一层 | 占空分配 42 维自由 ⇒ 端口速率不是常数 | 无条件成立，设计稿完全没看到这一层 |
| 第二层（固定占空后才轮到） | buckwheat / sandleaf 必然分流 ⇒ 中段被切细 | 仍成立，但只剩 2 商品 × 1 分流点（设计稿说 6 商品） |

这一层错位直接反映在设计稿 §6 的 T 表上，**两行判错**：

- **T3「`r[p]` 由 S2 唯一确定，不再是待解变量而是已知常数」**——不成立。`r[p] = c_p · u[i]`，`u[i]` 是变量。真塌缩的只有「每 operation 的端口速率之和」。
- **T4「`u[i]` 变常数 = `duty(op)`，变量 u 整族（266 个）消失」**——不成立，而且基数也不对。`u[i]` 只对 recipe-backed 机器有定义，266 个 mandatory 实例里有 46 个 `boundary_io` 与 1 个 `protocol_core` 没有配方、没有占空变量，真实基数是 **219**。这 219 个里 **170 个**被 `Σu = n` 钉死为 1，**49 个仍是变量**（受 7 条聚合等式约束），**净剩 42 维自由度**。整族没有消失。
- **T5「由 T3/T4 常数化后自动满足，退化成一次性断言」**——结论对、机制错。T5 自动满足不是因为常数化，而是因为 T4 留下的 7 条聚合等式 `Σ_i u[i] = x_op` 本身就是它。它是**被吸收**，不是**消失**。
- **T6 不受影响**：两个外部源口的下游（refinery_blue_iron `x=n=34`、crusher_source `x=n=18`）占空都在被钉死那 170 台里，全部取等的结论照旧。

净收益随之改写：`u` 族从「266 个变量全消失」改成「**219 → 42 维**」，`r[p]` 族从「全部降为常数」改成「由这 42 维参数化」。仍是**大幅**塌缩（v2 一般形态下 `u` 与 `r` 都是完全自由的），但不是设计稿说的整族清零。

#### 固定 duty 后，端口速率固定，但内部段速率仍未固定

**（本小节在勘误二轮被整体替换，外审 R-06 判 BLOCK、核签 ACCEPT——而且是我方自己的 Part C 见证把原结论证伪的。原文见本节末的留痕框。）**

固定一份 duty 向量**只使机器端口总速率成为常数**。它**不决定**：

- 端口内如何分道（速率 11/6 的口需 2 条道，fill-first 给 `(1, 5/6)`，但 `(11/12, 11/12)` 同样合法）；
- 哪些同商品 lane 在何处合并；
- 合并后下游段速率；
- 分支与重并的拓扑。

**阶梯算术见证本身就已经出现多种非 `{1, 1/2}` 的速率**。按我方 Part C 的阶梯 duty（`split_free_probe_v2_stdout.log:54-60`）与我方自己的 fill-first 车道分解算出的真实速率集：

| 商品 | 阶梯下的速率集 | 与「只有两作物多一档 {1,1/2}」是否相容 |
|---|---|---|
| `fine_buckwheat_powder` | `1/2, 1` | **不在**「只有两作物多一档」的集合里 |
| `sandleaf_powder` | `1/2, 1` | 同上 |
| `steel_bottle` | `1/2, 1` | 同上 |
| `qiaoyu_capsule` | `3/20, 1/5, 11/20` | **三个值全不在 `{1, 1/2}` 里** |
| `valley_battery` | `1/5, 3/5` | **两个值全不在 `{1, 1/2}` 里** |

**全网并集 = `{3/20, 1/5, 1/2, 11/20, 3/5, 1}`，6 元不是 2 元。**（独立重建：`external_round2/independent_staircase_check.py`，与我方见证定义直接算出的结果一致。）

因此有**三种不同层级**，不能混为一谈：

1. **只固定 duty**：仍保留数值流变量 `f` / `φ`。
2. **固定 duty + 完整 lane/merge pattern**：**该单一见证**可用常数系数复核，但搜索域被进一步限制。
3. **固定 duty + 有限 rate-state 搜索**：必须**列全所有可达的分支、合并速率，并证明状态集对守恒与合并闭合**；否则不是完整模型。

**OB-D2 只处理 duty 冻结。**若还冻结 lane/merge pattern 或有限速率档，**必须另记编码完备性或支配义务**（对应设计稿 §4 的甲-A2）。**现有材料不能据此宣称「零有理变量」的常数系数 P7 已复活**——该说法是本节原文，已撤。

关于「甲案的族是否非空」：更准确的说法是——**Part C 表明当前速率算术没有给出 P1 的矛盾**；P1 本身含物理组件与 70×70 几何，**不能在无几何变量的 Part C 里判非空**（外审 R-08，见 §6）。设计稿原判的独立问题另见 §5.3。

> **原文（已撤，勘误二轮）**：
> 「#### 那么常数系数形态还能不能要 …… **选定阶梯占空后，17 种商品的全部段速率是单一常数**；buckwheat 与 sandleaf 各多出一个分流点、两段 1/2，即**系数取值集合从 {1} 扩到 {1, 1/2}**；…… 仍是**全常数系数、零有理变量**的线性行 …… 所以对「甲案的族是否非空」这个问题：**在速率算术层，族非空**。」
> **撤销依据**：外审份4 R-06 判 **BLOCK**、核签 ACCEPT。这不是外审的外部主张，**是我方自己的 Part C 见证直接算出来的**——阶梯下真实速率集 6 元，其中 `qiaoyu_capsule` 的三个值与 `valley_battery` 的两个值全都不在 `{1, 1/2}` 里，`fine_buckwheat_powder` / `sandleaf_powder` / `steel_bottle` 也各带一档 `1/2` 而它们不是那两种作物。
> **更实质的结构点也成立**：本报告 §2.2（`../P2_0_SPECIALIZED_DESIGN_V1.md` §2.2）证的是「fill-first 取到最小车道分配下**单条车道速率的下确界**」——这只管住「**最细那条**」，管不住「**每条是多少**」，**救不了本节**。
> 所以「零有理变量的常数系数 P7 已复活」**不成立**。

**代价是一条新的支配义务**。前件族现在包含「占空按某一份指定分配」，而这是在 42 维多胞形里挑一个点（§1）——布局自己挑的自由度，不是目标钉死的推论。要把族内最优升格为全局最优，除了原有的

> **OB-D（最小车道支配引理，未证）**：对任何满足六谓词 + 吞吐的布局，存在一个在受限族内、且 `lex(area, min_side)` 不更差的布局

之外，还要加一条：

> **OB-D2（占空分配支配，未证，本轮新增）**：对任何合法占空分配下的可行布局，存在一个采用指定分配（如阶梯）、且 `lex(area, min_side)` 不更差的布局。

OB-D2 不是 OB-D 的特例：OB-D 谈的是「不稀释」，OB-D2 谈的是「按哪份占空跑」，两者的反例构造方向不同。设计稿因为把命题 S2 当成了「占空唯一」，从来没有产生过这条义务。

> **记账方式已改（勘误二轮，外审 D-10 / 核签 ACCEPT）**：原文「**甲案的未闭合项因此从 1 条变成 2 条**」不准确。设计稿甲案的定义只是「加 P1 纯度行」，**没有固定 duty**，因此不自动欠 OB-D2；**OB-D2 的真实出处正是本节**（尝试复活「固定阶梯 duty + 常数系数」时才引入）。正确记账按三档分开：
> - **甲-A0（只加 P1，duty 与数值流仍自由）**：只欠一条「**不同商品不共用同一 hardware key 也不吃亏**」的支配引理（**OB-P1**）。注意 OB-D 原来的义务对象写偏了——它的直觉段讲的是「稀释 / 分流」，而 P1 禁的是**不同商品共用物理组件**，**分流不违反 P1**（这正是 §5.3 撤销甲案死刑的依据）。
> - **甲-A1（A0 + 固定一份 duty）**：才额外欠 **OB-D2**。
> - **甲-A2（A1 + 冻结速率档 / lane decomposition / merge pattern）**：再欠**有限编码完备性**（见本节上文三层级）。
> - **若 P1 / A1 / A2 只作丙案的找见证启发式、见证由不含这些限制的完整 P7 verifier 复核，则三条一条都不欠。**

### 5.3 ③ 丙案仍是推荐路线——但推荐理由要换，且甲案的死刑判决须撤回

**丙案本身不受任何影响**。它的上界半边（flowbound 线 `A ≤ 1167`）的五步链 [A] 几何分账 / [B] 聚合平衡 / [C] 聚合容量计数 / [D] 每格 ≤ 2 state / [E] 覆盖装填，**逐条与占空分配无关**：[B] 只用聚合活动 `x_op`（这一层确实唯一，命题 S1 成立）；[C] 用的是 `L ≥ ⌈F_route/C⌉`，`F_k` 是总量、与台间分摊无关。`L ≥ Σ_k ⌈F_k/C⌉ = 308` 那条陷阱也不变（`⌈F_k/C⌉` 是聚合量，不随占空动），仍然只能进「受限族内上界」台账。**给 flowbound 线的两条净输入（禁令 + `F_route = 9,135` 三次互证）原样有效。**

**但推荐理由必须重写**。设计稿的理由是「甲案便宜但族是空的；乙案会把命题声明在空集上」。这条理由现在两头都塌：

- **甲案的族不空**（§5.2，至少在速率算术层）；
- 而且设计稿判甲案族空的推理本身是**非蕴含**（缺陷三）：设计稿 §4 写「加 P1 纯度行，强制解落在网络级纯流族内 ⇒ 由 §2.4 该族是空的」。但设计稿 §3 定义的 P1 是 `对每个 phys_key: AddAtMostOne(_phys_uses[phys_key])`，即**每个物理状态只承载一种商品**（= 禁止混流）；设计稿 §2.4 证的是**中段稀释不可避免**（= 存在细流段）。分流器下游的两条带各自仍只跑 buckwheat 一种商品，每个物理状态仍只承载一种商品——**分流不违反 P1**。正确的蕴含方向是「网络级纯流 + 速率引理 ⇒ P1」，反过来不成立；所以「前件 L 不可满足」推不出「P1 族为空」。

  这一步已回源独立核实（`src/models/routing_subproblem.py` 主仓 main）：`phys_key = (x, y, layer, flow_in, flow_out, component_type)`（`:1031-1038`）确实**不含 commodity 维度**，`_phys_uses[phys_key]` 才是按商品分开的 use 变量列表（`:1060`）；`_add_capacity_constraints`（`:1119-1122`）是 `AddAtMostOne(self._phys_by_cell_layer.values())`，即每 (格, 层) 至多一个物理状态。所以 P1 作用在「同一个物理组件上的多个商品」这一维上。

  分流器本身是一个 `flow_in` 1 入、`flow_out` 2 出的物理状态，只被 buckwheat 一种商品使用 ⇒ 它的 `_phys_uses` 只有一个元素 ⇒ `AddAtMostOne` 平凡成立。**分流不违反 P1。**

  P1 族到底空不空，是一个**几何问题**（19 种商品能不能在 70×70×2 层上路由到从不共用同一个物理组件），本批与设计稿都没测过。注意跨越不受影响：两条带在同一格跨层交叉时 layer 不同 ⇒ `phys_key` 不同 ⇒ 不触发 P1；同层两条带共格本来就被现役的 `_add_capacity_constraints` 挡着，与 P1 无关。**P1 唯一禁的是「一条带上混载两种商品」。**

**重写后的推荐理由（勘误二轮再修）**：丙案胜出，因为它是唯一**零支配引理**的路线——上界半边对全部布局有效，下界半边选什么族都不损 soundness（**前提是见证由不含该族前件的完整 P7 verifier 复核**）。甲案不是死路，而是**视它冻结了什么欠一到三条**未证支配义务（OB-P1 / OB-D2 / 编码完备性）；它的族是否非空还没测，测法是几何而非算术。乙案的问题也要重述：它不再是「把命题声明在空集上」（那个理由建立在族空的错判上），而是「会把发布口径降级成族内最优，撞 owner 已定的无降级退路」——这条本来就是它的真问题。

> 原文（已撤）：「唯一**零前件**的路线」「甲案…欠**两条**未证支配引理（**OB-D**、OB-D2）」。前者过强——丙案本身仍带**语义一致性**前提，且要求上界侧是**完整 P7-S 模型**（外审 D-08 / D-11）；后者按 D-10 改成一到三条，OB-D 更名为 OB-P1 并改正义务对象。
> **丙案在第二轮新增两条工程欠账**（不是支配义务）：①上界侧必须补齐完整 P7-S 行族（守恒 / 终端 / 配方耦合 / duty 聚合），原设计稿 §3 只有容量片段、判不了 P7；②`max_lex` 的**第二坐标 `min_side` 从未开工**（我方面积上界报告 `AREA_BOUND_THEOREM_REPORT.md:296` 原文「`min_side 维度本文未触碰。`」），闭合判据必须改成两阶段。

**开放问题台账的连带修正**：

- **Q2「丙案下界半边用哪个受限族？P1 族已证为空，替代族未知」——前提撤回。** P1 族未经证明为空。下界半边可以**先直接试 P1 + P3**（这正是设计稿说的最便宜、最小割证书那条），跑不出来再换族。Q2 从「承重：替代族未知」降为「工程 spike：P1+P3 在生产规模上能否构造出见证」。
- **Q3「OB-D 是否成立」——范围扩大**，新增 OB-D2（§5.2）。仍只影响甲案，丙案不需要。
- **Q7（`item_admission_port_exclusion` 理由 (a) 措辞补丁）——措辞要求变了**，见 §5.1 末。
- 新增 **Q11：canonical `rate_lemma_scope` 措辞修正**（owner + freeze-ritual，措辞 diff 见 §4）。

### 5.4 稿外下游（本报告只登记，通知与注记由主线程负责）

1. **U-01 席的独立发现与本批叠加**。U-01 席已独立判定 `rate_lemma_scope` 的前件 (ii) 在 certified 语境下**不可 discharge**。与本批的发现叠加起来，该引理在 certified 模型里是**双重不可用**：一重是前件 (ii) 本身 discharge 不了，一重是结论还欠一条没写出来的前件（均摊占空）。这也是 §4 推荐措辞方向 b 而不是 a 的直接理由——方向 a 再加一条同样 discharge 不了的前件 (iii)，只会让不可用叠到三重。
2. **两处叙述是均摊条件下的账**：主线程的记忆卡与 `PORT_SEMANTICS_REVERDICT_A_REVISED` 附录里「中间产物纯流是皮带帽算术强制」的说法，都建立在均摊分配上。正确的替代表述是定理 2（§3）：**在定理 1 的四条前件下，恒存在一对不同中间品的段其速率和 ≤ 带容量，所以皮带帽算术强制不出纯流**——但这**不构造实际共道**（勘误二轮按外审 D-05 / 核签 ACCEPT 收缩；原文「纯流强制恒不成立，恒存在速率 ≤ 1/2 的**共道窗口**」已撤）。
3. **设计稿 §7.1 给 mixflow 线的净输入同染**（`maxmin_segment_probe.py` 复用 `solve_duty()`）。修正表述见 §5.1 末。

---

## 6. 判定的边界

**本报告的全部判定都在速率算术层。** split-free 存在**不等于**那份占空分配加那套道对应在 70×70 真实布局几何里可实现——拓扑（带子能不能拐到该拐的地方）、占地（车道要不要额外格位）、跨层交叉、供电覆盖，全部未验。反过来，§3 的两条必然分流是**否定性**结论，几何只会让情况更差，所以它对几何层无条件有效。

具体地：

- §2 的「17 种同时 split-free」= 存在一组满足速率守恒与带容量的整道指派；它是几何可行性的**必要条件被满足**，不是充分条件。
- §3 的「buckwheat / sandleaf 必然分流」= 对任何几何实现都成立。
- §4 的 canonical **allocation-dependence** = 在速率算术层成立。若 canonical 使用「**游戏合法 duty**」作为量化域，则还须证明 staircase 属于该域；几何共址不是 residual 集合计算的前件，但**游戏稳态可实现性仍是前件**。
- §5.2 的正确说法 = **Part C 表明当前速率算术没有给出 P1 的矛盾**；P1 本身含物理组件与 70×70 几何，**不能在无几何变量的 Part C 中判非空**。

> **上述两条的原文（已撤，勘误二轮）**：
> - 「…而且阶梯占空是**更省车道**的那一份（§4），**几何上更容易而非更难**。」**撤**（外审 R-08 / 核签 ACCEPT）：**「车道总数更少」不是几何可行性的单调充分统计量**——端口朝向、特定源宿配对、分流 / 合流位置、跨层冲突、供电都可能让车道更少的方案反而更难。阶梯布局**可能**确实更容易，但本报告没有证明。
>   注意这条与 §4 那处 616→622 的反转**不冲突**：核签坐实了阶梯**确实**是车道数最小化解（逐项下界处处达到），该撤的是从「车道少」跳到「几何更容易」的那一步。
> - 「§5.2 的『**甲案族在速率算术层非空**』」**撤**：「非空」是一个关于 P1 可行域的断言，而 P1 的可行域含几何；算术层没找到矛盾 ≠ 族非空。
> - 同条第三处（外审也点了）：§4 的 canonical 反例原写成「**若某个未被建模的几何约束能排除阶梯占空，反例才会失效**」，这把举证责任放反了——正确的量化域问题是「canonical 的『legal allocation』指的是速率平衡可容许，还是游戏合法稳态」，后者需要我方**正面证明** staircase 属于该域，不是等别人提出反对约束。

---

## 7. 闲置机器的语义

owner 提到「允许部分机器闲置（duty = 0）」——认证的六谓词确实没有任何「设施必须运转」的要求，`production_targets` 也只约束总产出，所以闲置在 P2.0 语义下合法。

但在本实例里**没有闲置空间**：mandatory 实例普查给出的 `n_op` 恰等于 `ceil(x_op)`，任何 operation 停掉一台，剩下 `n_op − 1` 台即使全满速也达不到 `x_op`。所以每台 recipe-backed 机器都必须 `duty > 0`（219 台全部在跑）。

这条有两个用处：一是它让 §3 的计数证明干净（耗侧台数没有下调余地）；二是若将来 `production_targets` 下调或 mandatory 实例集变化，闲置就会变成真实自由度，本报告的所有计数都要重算。

---

## 8. 设计稿 errata（可直接照改）

下表「位置」列全部指**设计稿**的节号。

| 位置 | 现文 | 应改为 |
|---|---|---|
| §1.1 命题 S2 | 「每台机器的占空 `duty(op) = x_op/n_op` 唯一」 | **病根，从这里动刀**。降级为：聚合占空 `x_op` 唯一（S1 无恙）；逐台分配是自由度（各台 ∈[0,1]、和 = `x_op`，含 0）；均摊是约定之一，且是残道最优的那一个。自由度维数 42（§1） |
| §1.1 占空三组 | 「170 台满速、27 台 11/12、22 台 21/22」 | 标注为「均摊约定下的分布」。170 那部分是真被钉死的；27+22 = 49 台是变量。并列阶梯分配（212 满速 + 6 台 1/2 + 1 台 3/4）作为另一份合法分配 |
| §6 表 T3 | 「`r[p]` 由 S2 唯一确定，不再是待解变量而是已知常数」 | 不成立。`r[p] = c_p · u[i]`，`u[i]` 是变量；真塌缩的只有每 operation 的端口速率之和 |
| §6 表 T4 | 「`u[i]` 变常数 = `duty(op)`；变量 u 整族（266 个）消失」 | 不成立，基数也错。`u` 族真实基数 **219**（266 减去 46 个 `boundary_io` 与 1 个 `protocol_core`，它们无配方无占空）。其中 170 个被钉死为 1，49 个仍是变量，净剩 **42 维**。改写为「219 → 42 维」 |
| §6 表 T5 | 「由 T3/T4 常数化后自动满足，退化成一次性断言」 | 结论对、机制错。它是被 T4 留下的 7 条聚合等式吸收，不是消失 |
| §6 净收益 1 | 「`u[i]` 全族（266 个）消失；`r[p]` 全族从变量降为常数」 | 「`u` 族 266 → 42 维；`r[p]` 族由这 42 维参数化」。仍是大幅塌缩，但不是整族清零 |
| §6 表 T6 | 源口全部取等 | **无恙**，下游两个 operation 的占空都在被钉死的 170 台里 |
| §0 结论 2 / §2.4 表 | 6 种商品必然分流，占路由流量 37% | 2 种（buckwheat / sandleaf），占 10.5%。另 4 种在自由占空下 split-free 存在 |
| §0 结论 2 / §2.4 | 最薄段 1/3、7/22、14/33、4/11 | 均摊下的值；自由占空下两种商品的最厚最细段都是 1/2，且只需 1 个分流点 |
| §0 结论 3 / §7.1 | 「混流窗口只存在于被迫切细的细流段上；主干仍然逐口纯流」 | 该判断依赖均摊约定。无条件成立的只有「最细段 ≤ 1/2 ⇒ 混流窗口恒存在」 |
| §2.4 末 | 「严格读法下前件族是空的」 | 仍空，但只差 2 种商品 × 1 个分流点 × 2 段 1/2，而非 6 种商品 |
| §4 甲案 | 「由 §2.4 该族对本实例是空的 ⇒ 加 P1 直接 INFEASIBLE」 | 撤回。P1（每物理状态单商品）不被分流违反；P1 族空不空未测，是几何问题 |
| §4 甲案 OB-D | 一条未闭合项 | 两条：OB-D + OB-D2（占空分配支配） |
| §4 丙案推荐理由 | 「甲案族空、乙案声明在空集上」 | 「丙案零前件；甲案欠两条支配引理且族的空性未测；乙案的真问题是发布口径降级」 |
| §10 Q2 | 「P1 族已证为空，替代族未知」（承重） | 前提撤回，降为工程 spike：先直接试 P1+P3 |
| §10 新增 Q11 | — | canonical `rate_lemma_scope` 措辞修正（owner + freeze-ritual，diff 见本报告 §4） |
| §9.3 攻击面 | 六条预判，第 1 条打「建模是否等价于无分流」 | 补录第三向量：**探针输入前提本身没被辩护**（`:97` 占空硬编码）。清单里没有一条打到它，实际命中的正是它 |
| §2.5 canonical 加固建议 | 「不建议把 §2.4 的否定结论写进 canonical」 | 方向反转。定理 2 是无条件命题，正是该写进去的那部分（§4 方向 b） |

`OWNER_DECISION_SUMMARY.md` 同步改动（该页是设计稿的一页摘要，措辞更口语，改动点一一对应）：

| 位置 | 现文 | 应改为 |
|---|---|---|
| 「你提的那个想法，对了一半」段 | 「机器占空、每个端口的分道全都是常数：170 台满速、27 台跑 11/12、22 台跑 21/22」 | 只有总量是常数；219 台里 170 台满速是定死的，另 49 台怎么分是布局自己挑的（42 维自由度） |
| 「后半段不成立」段 | 「有 6 种货……占总流量的 37%」 | 2 种（荞麦、沙叶），占 10.5%；另 4 种在不均摊分配下可以不切 |
| 同段 | 「被迫切出来的细流最粗……1/3、7/22、14/33、4/11……细到足以让 15 对不同的货合法地挤进同一格」 | 最粗 1/2（两种货各一个切点）；~~混流窗口~~**速率兼容对**随分配变（均摊 15 对、阶梯 10 对），但**永远不为零**〔本行「混流窗口」已被勘误二轮取代为「速率兼容对」，D-05〕 |
| 「这不推翻 canonical」段 | 「那条说的是『每个端口的道两两不能共用』，我独立复算确认它成立（反例 0 条）」 | 该复算只在均摊约定下成立；换一份合法分配反例 40 对。canonical 那条确实欠一条没写的前件（§4） |
| 「我推荐的路线」段末 | 「把前件写进模型最便宜，但那个族**是空的**，加了直接无解」 | 撤回。那个族空不空没测过，而且切细并不违反它（§5.3）。甲案的真问题是欠两条支配引理 |
| 「顺带两条小事」第 1 条 | canonical 可选加固两句 | 升级为必办项：措辞 diff 见本报告 §4 |
| 「已知欠账」段 | 「没过独立 refute 席」 | 已过（本报告）；改记为「refute 第一轮已过，结论见 refute_round1/」 |

> **本节两张表是勘误一轮的指令，其中五行已被勘误二轮取代**（外审份4 + 核签）。**以二轮为准**：
>
> | 本节原「应改为」 | 勘误二轮取代为 | 依据 |
> |---|---|---|
> | 「无条件成立的只有『最细段 ≤ 1/2 ⇒ **混流窗口恒存在**』」 | 「速率算术恒存在一对不同中间品的**速率兼容**段」——`RC` 不构造物理共道、不推出 `¬P1` | D-05 |
> | 「混流窗口随分配变（均摊 15 对、阶梯 10 对），但**永远不为零**」 | 同上，「窗口」统一改称「速率兼容对」 | D-05 |
> | 「甲案的真问题是欠**两条**支配引理」（两处） | 「视甲案冻结了什么，欠**一到三条**（OB-P1 / OB-D2 / 编码完备性）；只作见证启发式则**零条**」；OB-D 更名 OB-P1、义务对象从「稀释」改为「不同商品共用同一 hardware key」 | D-10 |
> | 「**丙案零前件**」 | 「丙案零**支配引理**」——它仍带语义一致性前提，且要求上界侧是完整 P7-S 模型 | D-08 / D-11 |
>
> 另外二轮**新增**了本节没有的四项设计稿改动：命题 S2 三层标签拆分（D-04）、§3 补齐 D1/D2/T1/T2/T3 行族（D-08）、§0 结论 3 加前件（D-09）、丙案闭合判据两阶段化（D-11）。完整清单见 `../ERRATA_ROUND2_CHECKLIST.md`。

设计稿中**不需改动**的部分：§1.1 命题 S1（聚合速率唯一）、`F_route = 9,135` / `F_target = 9,169.5` 的三次互证、§8 给 flowbound 线的两条净输入（`L ≥ 308` 禁令 + 互证）、§5 与六谓词的关系、§7.3 箱口。
> 勘误二轮从这份「不需改动」清单里**移出一项**：原列的「§3 的行族定义与回源行号」——行号回源仍然正确，但**行族定义本身不完整**（缺守恒 / 终端 / 配方耦合 / duty 聚合四族，外审 D-08 / 核签 ACCEPT），已在设计稿 §3 补齐。

---

## 9. 本批自身的欠账与攻击面

### 攻击面台账：这一枪是设计稿预判之外的第三向量

设计稿 §9.3 列了六条预判攻击面，第 1 条打的是「`split_free_probe.py` 的建模是否等价于『无分流』」——**没有一条打到 `:97` 的占空硬编码**。实际命中的向量是「探针的输入前提本身有没有被辩护」，它在预判清单之外。这一条值得单列进攻击面台账：**自审攻击面时容易只审建模等价性，不审喂给模型的前提是怎么来的**。

发起这一枪的是 owner 本人，而且给出的具体构造被机器证实：owner 举的 molding_bottle「6 台总 duty 5.5 可以摊成 5 台满速 + 1 台半速」**逐字出现在本批的阶梯见证里**（`[1, 1, 1, 1, 1, 1/2]`），正是它把 steel_block 的耗道从 18 压到 17、消掉那条鸽巢。

**第二轮（外部）又打进了三个新向量，本报告同样一条都没预判到**（勘误二轮补录）：

- **「同一论证里换量化单位」**（外审 D-06 的诊断半）——本报告 §4 用逐端口读法说「阶梯同样满足 (ii)」，又用逐商品聚合读法攻击均摊，两处都没声明读法。**教训：一个前件有多种读法时，先声明读法再用，不然同一段论证会自相矛盾。**
- **「我方自己的见证证伪我方自己的结论」**（外审 R-06，BLOCK）——§5.2 说「阶梯下只有 `{1, 1/2}` 两档」，而按我方 Part C 的阶梯 duty 与我方自己的 fill-first 分解算，真实速率集是 6 元。**教训：写「只有两档」这类穷举断言之前，先拿自己已有的见证跑一遍反查。**
- **「正向措辞越界」**（外审 R-08）——§6 已经诚实写了「几何全未验」，却在同一节里写了原文（已撤）「阶梯几何上更容易而非更难」。**教训：边界声明段里最容易夹带没论证的正向断言，因为上下文看起来已经很保守了。**

三轮加起来的模式很一致：**预判清单打的都是「建模对不对」，实际被打穿的全是「前提哪来的 / 读法定没定 / 断言穷举没穷举 / 声明可不可信」。**

另外一条**净收入**：外审自产的 `independent_part_f_continuous_proof.py` 补上了 Part F 的连续域证明（R-05 指出缺口的同时把补丁给了），复跑逐字节相同，已收编为正式附录。

### 本批的欠账

1. **几何层全未验**（§6）。本批的正面结论都是速率算术层的存在性。
2. **格点限制不止 Part D**（勘误二轮按外审 R-05 / 核签 ACCEPT 扩写；原文「Part D 的格点限制」**只登记了 Part D**，漏了 Part F 与 Part G）。
   **Part D、Part F 以及 Part G 的 free-duty CP-SAT 均使用 1/660 网格**，格点上的 `INFEASIBLE` 不构成一般 `INFEASIBLE`。三处的承担者分别是：
   - **六例负结论**由 **Part B 的连续计数**承担（不依赖求解器）；
   - **Part F 的连续最优**由 `external_round2/independent_part_f_continuous_proof.py` 的 **exact interval proof** 承担（已收编为正式附录，复跑逐字节相同）；
   - **Part G 的全局 1/2** 由**连续手算上界**与**固定 staircase 见证**夹闭。
3. **`n_op` 取自 mandatory 实例普查**。若该集合变化，§3 的计数论证与 §7 的「无闲置空间」都要重算。
4. **状态粒度与稳定硬件身份**（勘误二轮按外审 R-09 / 核签 ACCEPT 整体替换；原文只写「若把速率档并进 `phys_key` 则重判缺陷三」，**太窄**）。

   P7 实现前**必须定义稳定投影**

   `hardware_key = H(route_or_rate_state_key)`

   它**只表示实际占用的物理组件身份**，不含 commodity、rate class 或时间相位。**P1 纯度、P2 容量、`use ≤ phys`、`AddMaxEquality`、cell-layer 互斥，以及所有「同一物理组件」论证，都必须对同一 `hardware_key` 下的全部细化状态联合聚合。**

   若实现给不出该投影，则以下**全部**重判（不是只重判缺陷三）：
   ① 分流是否违反 P1（两个商品可借不同 rate key 绕过纯度行）；② P1 / P2 行数（每个 rate key 各占一份完整容量）；③ 共享容量语义；④ 逐商品分解的**商品归属单位**；⑤ min-cut 图、cut 复用与证书 digest；⑥ 「splitter 只被一种商品使用」的论证——须按**硬件身份**而非精细 route state 判断。

   另：**本报告同样是承重推理文书**，按仓库家规应过独立审查——**第二轮外部审查已于 2026-08-07 完成**（GPT Pro 份4 + 核签，见文首勘误二轮）。§5.3 的「分流不违反 P1」已回源核实到 `phys_key` 不含 commodity 维度，但它只覆盖**当前 main 的建模语义**。
5. **速率兼容对的口径**（勘误二轮：原称「混流窗口的口径」）。§5.1 表里两个数用的是同一算法（每商品取全网最细段，两两求和 ≤ 带容量），均摊那一栏复现出设计稿的 15 对，可作为算法一致性的交叉验证；但**「速率兼容对存在」始终只意味着「速率排除不了共道」，不意味着混流会发生**——这条设计稿 §9.3 第 3 点已经写对，本报告沿用，并已按外审 D-05 把全文的「混流窗口」统一改称「速率兼容对」。

---

## 附：复跑

```bash
cd /home/zhuran24/zmd-pj
.venv/bin/python docs/research/p2_0_specialized_20260807/refute_round1/split_free_probe_v2.py
```

实测约 3 分钟墙钟（24 核机器，Part D/G 各含若干 CP-SAT 可行性与最优化问题，求解器多线程）。脚本复用 `../split_free_probe.py` 的 `solve_duty()` 做总量账（含 266 实例普查断言），两文件须保持相对位置。全程 `Fraction` 精确、零浮点。输出 `split_free_probe_v2_receipt.json` 与 `split_free_probe_v2_stdout.log`。

`../split_free_probe.py`（v1）与其收据保留为历史，不修改。

**第二轮外部审查的独立复核件**（勘误二轮收编，见 `external_round2/README.md`）——六个脚本**零依赖**（纯 `fractions` + `math`，不用 OR-Tools、不读项目数据），任何 Python 3 环境直接可跑：

```bash
cd /home/zhuran24/zmd-pj/docs/research/p2_0_specialized_20260807/refute_round1/external_round2
python3 independent_handcheck.py                # §3 两条作物手算 + §4 的 660 反例
python3 independent_staircase_check.py          # §2 阶梯占空 19 商品独立重建（含 §5.2 的 6 元速率集与 622 车道数）
python3 independent_part_f_continuous_proof.py  # §4 Part F 连续域精确证明（正式附录）
python3 aggregate_reading_check.py              # §4 「616 不可达」（核签自产）
python3 true_min_lanes.py                       # §4 「622 是可达最小值、阶梯处处达到」（核签自产）
```
