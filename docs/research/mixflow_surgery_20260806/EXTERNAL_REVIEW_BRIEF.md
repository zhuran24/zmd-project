# 外审材料：routing 混流表达扩展（mixflow-surgery）

> 状态：底稿 v1（随 DESIGN.md 同步生长；实现与差分测试数字落地后补全 §4）。
> 本方向是 soundness 敏感面（放宽 certified gate 的可行域），接入 main 前必须
> 通过外部对抗审查。审查对象 = 本分支对 `src/models/routing_subproblem.py` 的
> 改动 + 本文的论证链。

## 1. 审什么（一段话给外审席）

routing 子问题是 certified 链的谓词 (5)（路由连通性）gate。现状模型让每个商品的
use 变量继承整个物理件图样，导致「多商品共乘一段带再分开」结构性 INFEASIBLE
（模型比 canonical 严——已在案登记的保真缺口）。本手术把 use 改为商品子图样、
用方向侧覆盖约束缝合物理层，**扩大 routing 的可行域**。请对抗式回答：**这个扩大
会不会让一个不该 CERTIFIED 的布局拿到 CERTIFIED？** 附带审查：机器输入口门口
纯流（污染铁律）在新结构下是否仍然结构性成立。

## 2. 改动摘要（细节见 DESIGN.md §2-§4）

- use key：`(x,y,layer,phys 完整图样,commodity)` → `(x,y,layer,商品子图样,commodity)`。
- 新约束：覆盖（use 每侧 ≤ 含该侧 phys 之和）+ 精确侧（phys 每侧 ≤ 用该侧 use
  之和）+ 每格每层每商品至多一态。替换 `use≤phys`、`phys=max(uses)`。
- phys 层（48 态字典、AtMostOne 容量、桥互斥）逐字不动。
- sink front 地面对别家商品：涌现排他 → 生成期显式排除（结构上不可能）。
- source front 地面对别家商品：解锁（owner 08-06 定谳「输出口门口过境安全」）。
- 连通复验器、source-side 割、adherence、continuity、边平衡：零改动。

## 3. Soundness 主张与自攻

### 主张 M1：单调放宽 + 新增解物理合法

旧可行解全部保留（旧 use 图样 = 合法子图样特例）。新增解的物理层被精确侧约束
钉为「子图样并集 ∈ 48 态字典」，任何新增解的硬件都是现状模型同样接受的硬件。
**攻击面**：覆盖约束的每侧独立性——是否存在「侧侧都被覆盖但整体图样不被单一
phys 覆盖」的漏洞？答辩：AtMostOne(phys) 下每格每层至多一个 phys 为真，每条
覆盖约束的右侧求和只剩该 phys 一项，故所有侧的覆盖由**同一个** phys 同时满足，
并集覆盖是逐侧覆盖的合取。请外审验证这个论证在 CP-SAT 编码下无洞（特别是
phys 全 0 时 use 被迫全 0 的边界）。

### 主张 M2：谓词 (5) 在混流下照证（中心自攻点）

canonical 定义（W-CONN-01）：per 商品，每个 sink front 可达自某 source front、
每个 source front 能到某 sink front；允许多岛；**明文非吞吐保证**。

- 复验器 `_validate_selected_route_connectivity` 按 RouteStateKey 建 per-commodity
  有向图、CP-SAT FEASIBLE 后独立全局复验，代码零改动。手术后 key 的 flow 字段
  就是商品自身流向，复验器语义**更忠实**（现状下混流态从来到不了复验器面前，
  它的「按单商品分量走」从未被混流解检验过）。
- **自攻 2a（最强攻击）：内容盲分流器不会分拣。** 模型声明「A 走北、B 走东」，
  但游戏分流器按轮转推货不读类型：裸 splitter 下 A 的货也会被轮进东支路。
  静态连通性命题（存在按商品标注的路径图，其物理件序列合法且方向相容）为真，
  但「货真的只到声明的地方」不成立。

  **具体反例（坐标级，外审的靶）**：取 U-02 场景（`test_routing_mixflow.py`
  `_sc_u02_merge_then_split`，DIR_DELTA 数学系 N=y+1）。a 源 front (3,2)、
  b 源 front (3,4)，两流在 (4,3) merger 汇合，共乘 (5,3)→(6,3)，(6,3) 是
  splitter W→{N,S}：模型声明 b 走 N（经 (6,4) 到 b-sink front (7,4)）、a 走 S
  （经 (6,2) 到 a-sink front (7,2)）。**裸 splitter 动力学**：(6,3) 轮转不读
  类型，混流带上的 a 件会被轮进北支路 → 沿 (6,4)→(7,4) 抵达 b 的机器输入口
  → b 机缓存空窗吞入 a 件（A9 收货不看配方）→ 污染（能加工→错产物续污染
  下游；不能→槽位死锁）。模型的门口纯流约束在**静态标注**层被满足（(7,4)
  格上只有 b 的 use），但动力学送达不随静态标注走——这正是本次放宽让
  「静态连通 ⇒ 正确送达」失效的最小完整机理链。
  **物理兑现方案（答辩③的写实）**：在北支路的直行格 (6,4) 放准入口
  （itemId=b）、南支路 (6,2)……注意 (6,2) 是弯带（N→E），准入口只直、须放
  在其后的直行段如 (7,2) 前——本例 (7,2) 即终端格，恰为直行（W→E），可放。
  错入北支路的 a 件被 (6,4) 准入口拒收、留在 (6,3) 由轮转送回南支路
  （OWN-M08 实测机制）；per-commodity 连通性保证每型货都有自己的支路可去
  （#21 吸收前提）。本例同时示范了 Q3 的实体内容：每条 de-mix 支路需要
  一个直行格放准入口，a 支路的直行格恰好只剩终端格——若终端格也须保留为
  普通带，该布局的分拣兑现失败。这就是 Q3 要外审裁决的真实缝隙。

  三层答辩：
  1. 谓词 (5) 从未主张送达动力学——「非吞吐保证」是 canonical 逐字条款，
     LOCK §1A B 块把吞吐/离散容量流明示 OUT-OF-SCOPE。命题本身无假。
  2. **诚实披露的语义弱化**：现状纯车道模型下「静态连通 ⇒ 每件到货类型正确」
     恰好成立（车道有类型，到哪都是对的货）；手术后这个**隐含**性质在含
     de-mix 分流的解上消失。这不是谓词回归（谓词文本与复验器判定不变），但
     certified 布局的「可直接照建即工作」直觉弱化为「可照建即连通」。请外审
     裁决：这个弱化是否需要升级为谓词文本修订或 scope 声明（我们的建议：随
     W-PENDING-01 canonical 修正批加 scope 声明，不改谓词）。
  3. **游戏侧可实现性背书**（非证明义务，缓解 2 的实践担忧）：游戏 v1.1 存在
     准入口（1×1、直行、按 itemId 筛；canonical 刻意不建模但玩家可放）。
     declared split 支路加准入口 = owner 游戏实测过的分拣结构（OWN-M08）；
     per-commodity 连通性恰好满足 #21 分拣终端定理的吸收前提（每支路终点是
     该商品自己的 sink，错货被准入口挡回、由分流器轮到自己的支路）。残余
     缝隙：准入口只直 ⇒ 支路需有直行格可放，原型不强制——外审开放问题 Q3。
- **自攻 2b：复验器的邻接构造在子图样 key 下是否漏边/多边？** 邻接按「key 的
  flow_out 方向 × 邻格同商品 flow_in 反向」连边，与子图样语义严格一致。请
  外审重点核 `_terminal_nodes_by_front_for_keys`（终端节点识别，GROUND 限定）
  与 source-side 割自检 `_self_check_source_side_connectivity_cut` 在混流解上
  的正确性（割是 INFEASIBLE 方向的机器，割错 = 丢真解 = 影响最优性主张）。

### 主张 M3：污染铁律不放宽

sink front 地面别家 use 生成期即不存在（结构排除 > 约束排除）；端口边商品归属
由 per-commodity 端口豁免把守（零改动：别家商品对端口方向的边在域检查即强制 0）。
**攻击面**：涌现排他是否覆盖了显式排除表没覆盖的第三种到达方式？已推演的
边界几何（对脸异商品 sink、同商品 source→sink 直喂、对脸双 source）结论见
DESIGN.md §4 自检表。哨兵测试（§4 差分组 2）钉死回归。请外审构造我们没想到的
到达方式（如经 L1 下桥点、经 source front 解锁面迂回）。

### 主张 M4：INFEASIBLE 方向不受污染（cut 安全）

routing 的 INFEASIBLE 会经 independent reverifier 变成 layout 级 nogood cut。
手术是纯放宽：旧 INFEASIBLE ⊇ 新 INFEASIBLE，**新模型说 INFEASIBLE 的场景旧
模型也说 INFEASIBLE**……此蕴含只在「约束系确实单调放宽」时成立——请外审
核对唯一化约束（AddAtMostOne per 格层商品）不构成对旧解的收紧（答辩：旧解
每格层商品本就恰一个 use 态，唯一化在旧解域上恒真）。

## 4. 差分测试证据（2026-08-06 实测，`src/tests/test_routing_mixflow.py` 13 例全绿）

| # | 场景（坐标见测试模块 scenario builders）| 手术前实测 | 手术后实测 |
|---|---|---|---|
| 1 | U-02 合流后分流（双源汇入宽1走廊再分开）| INFEASIBLE | **FEASIBLE**；抽取证明分流去向记录在变量里：merger (4,3) uses=[b:N→E, a:S→E]，splitter (6,3) uses=[b:W→N, a:W→S] |
| 2a | 门口转弯过境（b 须在 a 的 sink front 转弯）| INFEASIBLE | INFEASIBLE（字典墙：并集 2进2出不存在 + L1 只直）|
| 2b | **门口分流过境**（b 共乘 a 车道、在 a 门口格剥离北去；并集= splitter W→{E,N} 字典合法，唯一防线=显式排除）| INFEASIBLE | INFEASIBLE（纯流守卫）|
| 2c | 多 owner 门口格（异商品双 sink 对脸共享 front）| INFEASIBLE | INFEASIBLE（多 owner 全排）|
| 3 | 既有测试面（9 文件 125 例：routing/p0 soundness/front identity/d2/rab-sep/wireless-sink/witness adapter/patch core/topology isolation）| 绿 | **绿**（2 个 fixture 需合法化，见 §4.1；2 个 error 为 basetemp 环境噪声与手术无关）|
| 4 | source front 共乘（b 在 a 输出门口格汇入干线）| INFEASIBLE | **FEASIBLE**；门口格 merger uses=[a:W→N, b:S→N] |
| 回归 | 垂直桥交叉 / 单商品分流 / 连通复验器接受混流解 / phys==uses 侧并集 | FEASIBLE | FEASIBLE（结构不变）|

**哨兵变异自证（两层）**：
- 源码级双移除（`_mixflow_ground_banned` 恒 False 变体）：3 个哨兵齐红
  （2b 翻 FEASIBLE、白盒 key 存在性、2c 翻 FEASIBLE），还原后 13/13 复绿——
  显式排除是唯一防线且哨兵承重，非摆设。
- 常驻自动化：`test_door_split_sentinel_is_load_bearing` /
  `test_multi_owner_sentinel_is_load_bearing` 用 monkeypatch 中和守卫断言场景
  翻 FEASIBLE——守卫将来被静默削弱时这两条会立即抓红。

### 4.1 附带发现：旧模型的潜伏混灌接受面（外审注意，方向有利）

既有 `test_two_commodities_can_share_same_straight_belt_phys` 与
`test_same_axis_l0_l1_crossing_is_infeasible` 的 fixture 把两种商品的 sink 端口
共located 在同一 front 格同一朝向（如 iron_sink 与 copper_sink 同在 (3,0) dir W）。
该几何 placement 不可能（两机体须重叠），但**旧模型接受它**——同图样 use 可共选，
两种商品经同一条终端带混灌进端口，旧的涌现排他对「同向同图样」终端不设防。
手术的多 owner 全排把这个潜伏接受面关掉（新模型 INFEASIBLE），两个 fixture 已
合法化重写（意图不变：共享直带/同轴叠层，测试内注释注明）。**对外审的意义**：
本手术在这一角上比旧模型更严，是污染语义的净收紧，与「放宽产生假 CERTIFIED」
的担忧方向相反。

## 5. 外审开放问题清单

- **Q1**：M1 的逐侧覆盖合取论证在 CP-SAT 布尔编码下是否有洞。
- **Q2**：M2 自攻 2a 的裁决——「静态连通不再蕴含正确送达」需不需要谓词文本/
  scope 动作，还是随 canonical 修正批的 scope 声明即可。
- **Q3**：准入口只直的实现细节要不要上升为模型约束（每个 de-mix 支路至少一个
  直行格）。我们的倾向：不上升（谓词不含送达），列 P2.0 设计守则。
- **Q4**：M3 请外审构造绕过显式排除表的到达路径。
- **Q5**：唯一化约束与边平衡的交互在 L0+L1 跨层边计数上是否仍然排除幻影
  splitter（DESIGN.md §2.1 下游零改动清单的边平衡行）。
- **Q6**：core 14 进保持保守排除（U-01 不在本手术范围）——外审确认这个范围
  切分不引入不一致。
