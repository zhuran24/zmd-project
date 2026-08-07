# 混流表达手术设计（mixflow-surgery，2026-08-06；de-mix 禁令 + U-01 口类型分叉 + 混吃汇流区 2026-08-07）

> 状态：设计稿 v2。v1（2026-08-06）的手术本体经外审判 **BLOCK**（finding B-01：
> de-mix 解在内容盲物理件下纳伪，且存在无准入口槽位的 4 格反例）。owner
> 2026-08-07 拍板取三修复方案中的 **③保守禁止 de-mix**，本文 §9 是该批的落地
> 记录，并订正 §5 与 §6 中已被外审推翻或已过时的条款。§10 是 U-01（仓储系口混流
> 准入）守卫分叉的落地记录，§11 是其扩展「混吃汇流区」的落地记录。
> **冲突时以编号大的一节为准（§11 > §10 > §9 > 其余）。**
>
> 本线是残余 #7「模型混流表达」的施工线；上游依据 = `.artifacts/axiom_analysis_
> 20260806/` 的侦察文书（SOURCE_FRONT_UNLOCK_RECON）与 owner 终审公理系
> （AXIOM_KERNEL_PROPOSAL）。外审判决全文见
> `.artifacts/mixflow_review_pack_20260806/verdict_20260807/`。
>
> **接入边界**：本分支（mixflow-surgery）改动 `src/models/routing_subproblem.py`
> （V99 close-kernel floor 内文件）。分支上**不做 reseal**：pin 链测试红是预期内，
> 接入 main 时由主线程统一走 freeze-ritual + 外审。外审材料见同目录
> `EXTERNAL_REVIEW_BRIEF.md`。

## 0. 一句话结论

use 变量从「继承整个物理件图样」改为「商品自己的子图样」，物理层 48 态字典与
AtMostOne 容量一字不动，两层之间用「方向侧覆盖约束」缝合；sink front 地面纯流从
涌现排他改为**显式生成期排除**。U-02（合流后分流）由此从结构性 INFEASIBLE 变为
可表达，机器输入口门口纯流铁律保持，连通性谓词的复验器**零改动**且语义变得更忠实。

> **v2 订正（2026-08-07）**：上段是 v1 的结论。③ 落地后，「按商品分道」被显式
> 禁止——合流与共乘仍可表达，但分流点上所有在场商品必须共享全部出边。实测后果
> 是 U-02 这类「合流再分开」的实例整体 INFEASIBLE，且在当前 sink-front 排他范围
> 内**混流格在任何能送达的解里都不可达**（§9.5）。本手术因此当前是纯基建，
> 表达力红利要等 U-01 才兑现。

## 1. 现状与死因（一手确认，2026-08-06 本线实读）

### 1.1 当前变量结构

- `phys_vars[(x, y, layer, flow_in, flow_out, component_type)]`：物理件状态。
  图样字典（`_iter_state_patterns`）：L0 = belt（1进1出，进≠出，12 态）+
  splitter（1进2/3出，16 态）+ merger（2/3进1出，16 态）共 44 态；L1 = bridge
  直穿 4 态。合计 48 态（= R-03/R-04 的封闭字典）。
- `use_vars[(x, y, layer, flow_in, flow_out, commodity)]`：商品占用。**key 里的
  flow_in/flow_out 就是 phys 的完整图样**——`use ≤ phys[同 key 图样]`（:1066）、
  `phys = max(uses)`（:1075）。
- 每格每层 `AddAtMostOne(phys)`（:1122）；L0/L1 互斥、垂直直穿豁免（:1124-1143）。

### 1.2 U-02 的精确死因

同向共乘一条直带**今天就是合法的**（A、B 两个 use 挂同一条 belt phys，模型接受；
`extract_routes` 的 `uses` 列表天生支持多商品）。死的是合流点与分流点：

- **合流点**：phys 必须是 merger `{W,S}→E`，则 A 的 use key 也是 `{W,S}→E`——
  模型强迫 A 声明「我也从 S 进」。predecessor 约束（:1259）在 S 侧找不到 A 的
  发送者 → A 的 use 强制 0 → INFEASIBLE。
- **分流点**：phys 是 splitter `W→{N,E}`，A、B 都被迫声明双出口，A 被迫流进
  B 的支路，支路尽头没有 A 的去处，successor 链（:1221）逐级强制 0 → INFEASIBLE。

死因一句话：**use 的 key 语义是「物理件图样」而不是「商品自己的流向」**，分流点上
模型没有任何变量记「哪种货走哪条边」。这与侦察文书 §2 的判断一致，但更精确：不是
「缺机制」，是「use 变量的粒度选错了」。

### 1.3 排他的涌现机制（为什么手术必须显式补纯流约束）

现状下别家货完全上不了终端格地面：终端格 phys 被 adherence（:1297，sum==1）钉成
带端口方向的图样，别家货要用这格就得采纳同一完整图样，而它对端口方向的出/入边
过不了 successor/predecessor 的域检查（机身格不在活跃域）→ 强制 0。**手术把 use
从完整图样解耦后，这个涌现排他就消失了**——别家货可以用一个不含端口方向的子图样
搭上终端格的 splitter/merger。对 source front 这正是 owner 要的解锁；对 sink front
这是污染漏洞（内容盲物理件会把别家货轮进机器口），必须显式补回。见 §4。

## 2. 分流点商品去向：两个候选结构（成败点，单独成节）

> 主线程对齐点 1：分流点上「A 货走东、B 货走南」需要模型能对同一物理件的不同
> 出边按商品分流。两个候选结构与约束数量级如下。记号：C=商品数，N=单商品活跃格数
> （生产规模 ~10^3 量级/商品），P=每格每层图样数（L0 44 / L1 4）。

### 2.1 候选 A：商品子图样 use 变量（选定方案）

**变量**：use key 改为 `(x, y, layer, c_flow_in, c_flow_out, commodity)`，其中
`(c_flow_in, c_flow_out)` 是**该商品自己**经过这格的图样，取值域 = 同一张 48 态
字典（商品自己也可以 split/merge——多 sink 分发 / 多 source 汇集，今天已有）。
phys 变量、字典、容量、桥互斥全部不动。

**分流点语义**：A 在分流格的 use = `W→{N}`，B 的 use = `W→{E}`，phys = splitter
`W→{N,E}`。**「哪种货走哪条边」直接写在各自 use 的 key 里**——去向不是推断出来
的，是变量本身。

**缝合约束**（新增，替换 `use ≤ phys[key]` 与 `phys = max(uses)`）：

1. **覆盖**：对每个 use u、其每个进侧 d：`u ≤ Σ phys[P: d ∈ P.flow_in]`；出侧
   同理。配合 AtMostOne(phys)，被选中的唯一 phys 必须同时覆盖所有活跃 use 的
   全部侧 ⇒ phys 图样 ⊇ 商品子图样并集。并集不在字典里（如 2进2出）⇒ 自动
   不可满足 ⇒ **可表达域天然限于物理可实现域**，无需额外禁令。
2. **精确侧**（反方向）：对每个 phys P、其每个侧 d：`P ≤ Σ use[该侧被某商品
   使用]`。钉死 phys 图样 = 并集（不多不少）：抽取出的硬件最小化，且并集定图样
   在字典内**唯一**（1进1出=belt、1进多出=splitter、多进1出=merger），抽取器
   可确定性反查。
3. **商品态唯一**：每 (格, 层, 商品) `AddAtMostOne(use)`。消除同商品「两条 belt
   use」与「一个 merger use」的双重表示（边平衡本会排掉前者，显式唯一化把搜索
   空间也剪掉）。

**约束数量级**：use 变量数与今天同阶（同一字典、同一 per-commodity 局部支撑
剪枝）；phys 变量略增（并集支撑 ⊇ 单商品支撑，混流区多出跨商品拼合图样）。
新约束：覆盖 ≤ 4×|use|，精确侧 ≤ 4×|phys|，唯一化 = 格×层×商品 个 AtMostOne
——全部线性于变量数，替换掉的 `use≤phys`（1×|use|）与 MaxEquality（1×|phys|）
也是线性。**净变化 = 常数因子 ~3 的轻量线性约束增量，无新变量类**。

**下游机器零改动清单**：successor/predecessor（:1221/:1259）、有向边平衡
（:1169）、port adherence（:1297）、连通复验器（:1710）、source-side 割
（:1654）、nogood（:1821）——全部按 `(cell, dir, commodity)` 索引或按
RouteStateKey 遍历，key 结构不变、flow 语义从「物理图样」变「商品流向」后
**这些约束的语义反而首次变得逐字正确**（今天它们在混流态上是靠图样碰撞连带
杀掉的）。域构建 `analyze_exact_routing_domain` 是纯格集合几何，不碰图样，
零改动（侦察文书 §5 预警的「commodity_active_cells 语义会变」经实读排除：
共乘段本来就在同一自由连通分量里，每个商品的活跃域已覆盖）。

### 2.2 候选 B：per-commodity 出入边布尔（流量守恒式）

**变量**：`f[c, cell, layer, d]`（c 从 d 侧进）与 `g[c, cell, layer, d]`（c 从
d 侧出），每格每层每商品 8 个布尔；商品在格上的行为由度约束表达（出现 ⇒ |in|≥1
且 |out|≥1；|in|≥2 ⇒ |out|=1；|out|≥2 ⇒ |in|=1——后两条在候选 A 里由字典自动
保证，这里要显式 reify）。phys 层同样用覆盖约束缝合（或改成 per-side channel
变量 + 组件类型合法性约束）。

**数量级**：变量少 ~5 倍（8 vs 44/格/层/商品）；但度约束需要 reified 逻辑
（比线性覆盖贵），且**全部下游机器都要重写**——adherence/继承/边平衡/复验器/
割/抽取器全按图样态 key 工作，B 等于把 routing 子问题重写一遍。复验器重写 =
soundness 审计面翻倍（正是侦察文书警告的「_validate_selected_route_connectivity
混流下需重写」的那个世界线）。

### 2.3 判决

**选 A**。理由排序：①认证机器审计面最小（复验器/割/adherence 零改动是最强的
soundness 论据——见 brief §自攻1）；②48 态字典保持物理真相权威，模型-canonical
对账仍然逐态可查；③变量数同阶、约束线性增量，生产 build 40s 的预算里是常数
因子扰动（实测数字见 §7，落地后回填）。B 保留为**性能后备**：若生产规模实测
build/solve 爆预算，B 的变量瘦身值得再评（届时复验器重写的审计成本单独立项）。

## 3. 手术清单（候选 A 的落地改法）

`src/models/routing_subproblem.py` 内完成，无新模块（routing 是 certified gate
本体，平行新模块 = 分叉封印面 + 漂移风险，比原地手术更险）：

1. `_create_routing_variables` 重写为两遍生成：
   - Pass 1：算每 (格, 层, 侧) 的支撑商品集（复用 `_incoming_dir_supported` /
     `_outgoing_dir_supported` 逐商品判定）。
   - Pass 2a：phys 生成——字典图样的每个侧都有**某**商品支撑才建变量（今天
     phys 只在「某商品全图样支撑」时才建；新规则严格更宽，多出来的正是跨商品
     拼合态）。
   - Pass 2b：use 生成——per 商品，图样每个侧都被**该商品**支撑才建（与今天
     同规则），另加 sink-front 纯流排除（§4）。
2. 新增 `_add_phys_coverage_constraints`：§2.1 的覆盖 + 精确侧 + 商品态唯一，
   替换 `use ≤ phys` 与 `AddMaxEquality`。`_use_to_phys_key`/`_phys_uses` 退役。
3. `extract_routes` 改组队方式：selected use 按 (格, 层) 分组，反查该格唯一
   selected phys（AtMostOne 保证 ≤1）。输出 schema 不变：顶层 flow_in/flow_out
   仍是 phys 图样（生产 serializer 只读顶层），`uses` 列表里每条的 flow_in/
   flow_out 从「重复 phys 图样」变为「商品子图样」——语义更准，形状兼容。
4. 纯流约束（§4）：sink front 排除表在生成期应用 + 哨兵测试钉死。
5. 其余约束函数（capacity/bridge/continuity/edge-balance/adherence/hint/复验器/
   割/nogood）**逐字不动**。

## 4. 纯流与门口语义（owner 公理系的落点）

| 位置 | 手术后语义 | 依据 |
|---|---|---|
| sink front（机器输入口门口格）地面 | **对别家商品全排除**（生成期不建 use 变量，结构上不可能）。理由：adherence 钉死这格 phys 永远含通往端口的出边，物理件内容盲，任何共located 地面商品的货都会被轮进机器口 = 污染。涌现排他改显式排除，语义等价、强度不降。**多 owner 细则**：一格是多个 sink 端口的 front 时，owner 商品集为单元素（含同商品双端口对脸）→ 按上排除别家；owner 商品集 ≥2 个异商品 → **地面全排**（任何单商品在场都无法同时满足两家 adherence，且任何两家共存的子图样并集必含双端口出边=内容盲双向灌门）。设计期发现：只排非 owner 在异商品双 owner 格上有洞（a 的 `W→send_a` + b 的 `W→send_b` 会拼出 splitter 合法覆盖），必须全排。今天该几何也是 INFEASIBLE（successor 域检查杀），语义保持。 | A9/#1 污染链、#8(a)、owner「输入口门口纯流铁律」 |
| sink front 地面·同商品 | 不排除：A 自己的终端带、A 送达并继续（splitter `X→{port,N}`）照旧合法（今天已合法）。 | 同商品终端豁免（现状 :1233/:1271） |
| sink front L1 | 不排除：别家商品垂直借道照旧（P1 已实测 FEASIBLE，本手术不碰）。 | A5d、OWN-M23 |
| source front（输出口门口格）地面 | **解锁**：别家商品可共乘/汇入（如 merger `{port侧, W}→N` = 借输出道当干线的入口形态）。别家商品仍不可能声明「从端口收货」或「向端口送货」——predecessor/successor 的 per-commodity 端口豁免只对端口所属商品成立，别家的这类边在域检查即强制 0（现状代码，零改动）。 | owner 08-06 定谳 #8(c)「输出口门口过境安全」 |
| 地面垂直交叉 | 仍不可能（并集 2进2出不在字典）——这是物理，不是政策；交叉走 L1（现状）。 | A6a |
| 速率 | 不进模型。共乘段「各流之和 ≤1 件/tick、汇流 2s CD 最坏减半」是 owner 附注的游戏速率账，认证谓词不含吞吐（LOCK §1A B 块），归 P2.0。 | A7、W-CONN-01「非吞吐」 |

特殊几何自检（设计期推演，均得正确行为）：
- 两个**异商品** sink 共享同一 front 格（对脸机器）：互相排除 → 双 adherence
  失败 → INFEASIBLE。正确：两边门口互灌，无解法。今天也是 INFEASIBLE。
- **同商品** source front 即 sink front（A 机出口直喂 A' 机入口，中间一格）：
  belt `{port_in}→{port_out}` 一态满足双 adherence，合法（今天已合法）。
- 两个**异商品** source 共享 front 格（对脸输出）：merger `{recv_a, recv_b}→X`
  = 双输出汇成混流干线，手术后 FEASIBLE（今天 INFEASIBLE）——正是 owner 定谳
  安全的形态，差分测试 #4 的素材。

## 5. Soundness 论证草案（放宽方向为何不产生假 CERTIFIED）

> **⚠ 本节是 v1 的论证，已被外审部分推翻，保留作史料。** 第 1 条的「纯放宽」
> 是**假命题**（外审 F-02 逐字驳倒，见 §9.4 的带前提改写）；第 7 条的三层答辩
> 被外审 B-01 判为不足（4 格反例封死了「总能补准入口」这条腿）。当前有效的
> soundness 论证在 §9.3。

完整版（含自攻）在 `EXTERNAL_REVIEW_BRIEF.md`，此处存骨架：

1. **单调性**：旧可行解 ⊆ 新可行解（旧解里每个 use 的完整图样在新模型中是
   合法子图样，覆盖/精确侧/唯一化全满足）。放宽只发生在「新增可行解」上，
   下列 2-5 论证新增解仍满足谓词 (5) 的 canonical 语义。
2. **物理合法性不放宽**：phys 层约束逐字不动；精确侧约束保证被选 phys =
   子图样并集 ∈ 48 态字典。任何新可行解的硬件层都是今天也合法的硬件层。
3. **连通性谓词照证**：谓词 (5) 的 canonical 定义（W-CONN-01）按商品量词化
   （每 sink front 可达自某 source front、每 source front 达某 sink front、
   允许多岛、非吞吐）。复验器 `_validate_selected_route_connectivity` 按
   RouteStateKey 建 per-commodity 图——手术后 key 里的 flow 就是商品流向，
   复验器在混流解上第一次逐字正确（今天它「正确」是因为混流态根本到不了它
   面前）。CP-SAT FEASIBLE 后仍需全局复验通过才接受，双保险不变。
4. **污染语义不放宽**：sink front 地面排除从涌现变显式，强度不降（哨兵测试
   钉死）；端口边的商品归属检查零改动。
5. **真实放宽点只有两个**，均有 owner 定谳背书：(a) source front 地面共乘
   （08-06 定谳过境安全）；(b) 中段合流/分流（canonical `mixed_commodity_flow`
   本就写宽、模型此前过严——本手术是**向 canonical 对齐**，不是越过它）。
6. **残余严格面**（比 canonical 严、方向安全=只可能拒真不可能纳伪）：
   sink front 纯流显式排除先于 canonical 修正批（W-PENDING-01 终端条款）落地
   ——模型先行、canonical 待补，与 owner 公理一致；core 14 进的门口混流解锁
   （U-01，WarehouseSink 不拒收 ⇒ 游戏安全）**不在本手术范围**，保持保守。
7. **中心自攻点**（外审主攻方向，brief §自攻详述）：内容盲 splitter 不会按
   商品分拣——模型声明的「A 走北 B 走东」在裸 splitter 动力学下不成立。
   三层答辩：①谓词 (5) 从未证送达动力学（非吞吐、LOCK 明示 out-of-scope），
   静态连通性命题本身为真；②今天的纯车道模型「恰好」蕴含正确送达，手术后
   这个**隐含**性质消失——这是诚实披露的语义变化，不是谓词回归；③游戏 v1.1
   存在准入口（1×1 直行、按 itemId 筛，canonical 刻意不建模但玩家可放置），
   分拣结构 owner 已游戏实测（OWN-M08），declared split 的支路加准入口即可
   实现分拣，且 per-commodity 连通性恰好保证 #21 的吸收前提（每支路终点是
   该商品自己的 sink）。残余实现细节：准入口只直 ⇒ 支路上需存在直行格——
   原型不强制、列为外审开放问题。

## 6. 差分测试组（已落地全绿，2026-08-06 实测）

> **⚠ 本节记的是 ③ 落地前的判定。** 第 1、4 条（U-02 复活、source front 共乘）
> 已在 ③ 下重判为 INFEASIBLE，第 2 条的哨兵承重性已转移到 de-mix 禁令。当前
> 测试组（20 例）与逐条重判见 §9.7。

模块 `src/tests/test_routing_mixflow.py`，13 例全绿（0.2s）。手造小网格 spec
全部对齐 DIR_DELTA 数学系（N=y+1）；走廊场景把自由格钉成显式集合，逼出共乘段
（开阔网格会绕行、证不了任何事）。术前/术后完整对照表与坐标见
`EXTERNAL_REVIEW_BRIEF.md` §4，摘要：

1. **U-02 复活** ✅ INFEASIBLE→FEASIBLE，抽取证明分流去向记录在变量 key 里。
2. **污染哨兵** ✅ 三个几何全保持 INFEASIBLE：门口转弯（字典墙）、**门口分流**
   （并集字典合法、唯一防线=显式排除——真正的变异检测哨兵）、多 owner 门口格。
   **变异自证两层**：源码级双移除变体 → 3 哨兵齐红、还原复绿；常驻
   monkeypatch 中和测试（守卫失效时场景必须翻 FEASIBLE）钉死守卫承重性。
   设计教训：最初的转弯哨兵（2a）其实被字典挡住、测不出守卫承重——变异检测
   哨兵必须选「除守卫外全合法」的几何。
3. **语义不回归** ✅ 既有 9 文件 125 例绿。其中 2 个 fixture 需合法化（原几何
   把异商品双 sink 共located 同一 front 格同向 = placement 不可能的虚构，旧模型
   曾放行其混灌——潜伏接受面，详见 brief §4.1）；2 个 error 为 basetemp 环境
   噪声（预建目录即过，与手术无关）。
4. **source front 共乘** ✅ INFEASIBLE→FEASIBLE，a 输出门口格 merger 双商品
   共存（owner 定谳的解锁形态）。
5. **回归面** ✅ 垂直桥交叉、单商品分流结构不变；连通复验器接受混流解且
   failure_count=0；每个抽取件 phys 图样 == uses 侧并集（最小硬件不变量）。

## 7. 构建成本账（生产 build 40s 预算，proxy 实测）

**基准装置**：70×70、256 个 3×3 机体 pitch-4 点阵（宽1走廊）、19 商品、
一体一口（商品轮转、out/in 交替）——刻意构造的最坏形态：全部走廊被全部商品
共享、terminal-core 剥叶剥不掉任何格。老模型 = `git show 5af80d0` 平行模块，
同实例同进程对测。脚本 `bench_mixflow_prodscale.py`（scratchpad，报告存档）。

**第一轮（覆盖/精确侧按行展开求和的朴素实现）——不合格，已返工**：

| 指标 | 术前 5af80d0 | 术后朴素版 |
|---|---|---|
| use vars | 980,444 | 974,648（纯流排除净减）|
| phys vars | 53,444 | 53,444（本形态并集支撑=单商品支撑，零增）|
| constraints | 3,999,723 | 5,842,158（+46%，符合 §2.1 线性估计）|
| build | 19.6s | **46.7s（2.4×，超预算）** |
| solve（120s 帽）| INFEASIBLE @27.7s | TIMEOUT（可行域变大后不可行证明变难）|

教训：约束**行数**线性 ≠ proto **项数**线性——朴素版每条 use/phys 行各自展开
一遍 phys/use 求和，proto 里塞进数千万项。返工：按 (格,层,方向,进出) 聚合出
侧指示布尔（`phys_side == Σphys含该侧`（AtMostOne 下 Σ∈{0,1}，等式良型）、
`use_side == OR(use含该侧)`），覆盖/精确侧全部降为两文字蕴含。语义严格等价，
差分测试 13 例复绿。

**第二轮（聚合版，交付形态，2026-08-06 实测）**：

| 指标 | 术前 5af80d0 | 术后聚合版 |
|---|---|---|
| use vars | 980,444 | 974,648 |
| phys vars | 53,444 | 53,444 |
| constraints | 3,999,723 | 5,898,352（行多但大宗为两文字蕴含）|
| build | 19.5s | **20.6s（+5.6%，达标）** |
| solve（120s 帽）| INFEASIBLE @27.7s | TIMEOUT |

**解读注记**：
- build 成本账收口：聚合版把 2.4× 压回 +5.6%，40s 预算内是真扰动。
- solve 残余差距如实报告：在这个**不可行边界的对抗性最坏 proxy**（19 商品
  抢宽1走廊、剥叶失效）上，老模型 27.7s 穷尽证明 INFEASIBLE，新模型 120s
  内出不了结论——可行域放大后不可行证明必然变难，这是表达力扩展的固有
  代价，不是实现缺陷。6 商品变体同构复现（老 6.5s INFEASIBLE / 新 60s
  TIMEOUT；build 6.4s vs 7.0s 齐平），说明该差距随商品数缩放存在、非 19
  商品特有。真实生产候选的 solve 表现要在 benders 环境实测（**接入批
  必做项**，与 PIC 性能测同批）。
- 本 proxy 上 phys 零增/纯流排除净减 use——「变量同阶」的设计判断被实测
  坐实；成本全部来自约束项数（第一轮教训）与搜索难度（solve 残余）。

## 7b. 兼容面台账（侦察实测，2026-08-06）

- **认证链无 routing 独立重实现**：`candidate_proof_replay` 零 routing 引用；
  `independent_infeasibility_reverifier` 只重建 binding（routing 走保守 UNKNOWN
  策略）；`pr2_l0_fixed_witness_core` / `terminal_fixed_witness_verifier` 重新
  调用生产 `RoutingSubproblem`（`check_phase_review_gate.py:920` 源码扫描强制
  且有测试钉着）。**手术兼容义务 = 构造签名、solve 状态串、build_stats 既有
  字段名保持稳定**（本手术全部满足：新增字段只增不改）。
- **patch_routing_core**（唯一独立重实现，diagnostic-only、无 parity 测试）：
  其 docstring 自认未实现混流共享、预告需按 phys/use 拆层重构。本手术不碰
  （F-SND-001 同文件，按任务书不碰就不修，挂 promotion 前置清单）。
- **witness 线欠账（可执行粒度，挂接入批）**：
  `docs/research/witness_constructor_20260717/07_routing_aware/route_adapter.py:300-301`
  断言每条 use 的 flow 与 phys 图样**严格相等**——混流路由会 USES_MISMATCH
  fail-closed。本批不改（单商品见证 use==phys 仍成立不回归；混流见证拒真不
  纳伪方向安全）。**混流见证投产前必须**：把 :300 的逐条相等断言改为
  per-commodity 校验——use 集合按商品聚合去重后，(a) 每条 use 的 flow 侧 ⊆
  phys 侧，(b) 全体 use 的侧并集 == phys 侧，(c) 每商品至多一条 use；并同步
  更新 `src/tests/test_witness_route_adapter.py:351/:359` 的错位注入用例。
  owner/主线程 2026-08-06 批准挂接入批。
- **extract_routes 生产零调用**（benders_loop 只读 build_stats + 状态串），
  唯一真实调用方 = witness 线 `fixed_geometry_router.py:958`。输出 dict 形状
  不变（顶层 flow = phys 图样，`uses` 变商品子图样）。
- **sha pin（接入 reseal 用，本分支不动）**：obligation
  `PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS`
  （`data/proof_obligations/p1_2_proof_obligations.json:1445-1457`）与
  `scripts/check_p1_2_proof_obligations.py:13000` 双份
  `source_sha256=7554b0f2…`；reseal 按 LF 字节 `git show HEAD:<file>|sha256sum`。
  另 `test_topology_hint_isolation.py:81-93` 扫描本文件正文，禁出现 topology
  hint 模块名（手术注释避开该词面）。

## 7c. 开放问题（接入批设计题，主线程 2026-08-06 定调）

1. **门控开关形态**：混流表达是否做成开关——certified 求解路径**默认关**
   （保住不可行证明速度，§7 的 solve 残余差距即动机）、见证验收/研究路径开
   （吃表达力红利）。若走此形态：开关属 `EXACT_*` env 闭合白名单
   （deny-unknown），接入批必须连 allowlist/lock/tests 同批动。
2. **source-side 割在混流 incumbent 上的回退**（600s 探针发现）：6 商品
   proxy 上新模型 600s 内 guard rejected=4、cuts_added=0——四个局部闭合
   incumbent 全被全局连通复验拒掉，但 `_add_source_side_connectivity_cut`
   的自检全部回退成整解 nogood（弱割）。割机器是前混流时代写的；混流
   incumbent 下自检哪条失败、能否修出真割，接入批查 telemetry 定位。
   守卫环「拒-割-重解」在生产规模的收敛速度取决于此。
3. **600s 探针终态**：instance 在混流语义下 600s 无结论（非「慢不可行」
   实锤——CP-SAT 持续产出候选、复验持续拒，更像「慢可行+弱割」形态）。

## 8. 雷区处置记录

- `patch_routing_core.py:583-585`（F-SND-001 双重 front 偏移）：本手术不触碰
  PCR 面（改动仅 routing_subproblem.py），按任务书「不碰就不修」，留 promotion
  前置清单。
- `analyze_exact_routing_domain`：实读结论零改动（§2.1），D2/PCR 抑制义务不被
  本手术牵动。
- `_validate_selected_route_connectivity`：零改动（§2.1）；侦察文书的「需重写」
  预警对应的是候选 B 世界线。
- reseal/pin 链：本分支不动，接入时主线程统一 freeze-ritual。

## 9. ③ 保守禁 de-mix（外审 BLOCK 修复批，2026-08-07）

### 9.1 判决与选择

外审 2026-08-06 判 BLOCK，唯一 Blocker 是 **B-01**：内容盲 splitter 不按商品
分拣，模型却允许在同一物理件上声明「a 走一支、b 走另一支」；外审并构造了只有
4 个自由格的反例——两条分流支路都只剩一个转弯终端格，**根本没有直行格可放
v1 §5.7 所依赖的准入口**，该实例术前 INFEASIBLE、术后 FEASIBLE、术后的全局连通
复验器仍返回 `failure_count=0`。外审给的三条修复路（显式建模 filter / 独立
realization gate / 保守禁 de-mix）中，owner 2026-08-07 拍板取 **③保守禁止
de-mix**，依据是需求侧定谳：混流的收益场景只有「终品共道」「借道过境」两类、
全是共乘不分道型，de-mix 的收益场景为零。①（filter 建模）存档不排期，
②（realization gate）出局。

### 9.2 约束形态与不变量

`_add_demix_ban_constraints`（`src/models/routing_subproblem.py`），在
`_add_phys_coverage_constraints` 之后接线。逐条 use 变量发行两文字蕴含：

```
use[x, y, layer, *, flow_out, c]  ⟹  ¬phys_side_out[x, y, layer, d]
                                     对每个 d ∉ flow_out
```

即**被选中的商品子图样禁止该格物理件携带任何它没声明的出边**。复用 §7 返工
时建的聚合侧指示布尔，**零新变量类**。

- **行域剪枝**：只对「该 (格,层) 存在多出侧（splitter）状态且 d 属于其出侧」
  的方向发行。若携带出侧 d 的 phys 状态全是单出侧，则 `phys_side_out[d]=1`
  已把被选件的出侧集合钉成 `{d}`，覆盖约束又逼 use 的出侧落在其中——该行被
  既有约束蕴含，可略。L1 只有直行 1进1出 bridge，**零行**。
- **得到的不变量**：配合精确侧约束（phys 侧 = 全体 use 侧并集），每格每层
  **所有在场商品的出侧集合 ≡ phys 出侧集合**。进侧仍逐商品自由——物理件不
  决定货从哪来，合流点（多进一出）因此完好。

保留面（一格未误伤，测试逐条钉死）：同商品分流（单商品在场时每行皆恒真）、
混流共乘直带（唯一出侧、全体声明）、合流点汇入、L1 垂直借道。

### 9.3 soundness 论证（当前有效版，替代 §5.1/§5.7）

由 9.2 的不变量：商品 c 在场的每一格，它声明的出边 = 该格物理件的全部物理出边。
successor 约束又要求每条声明出边或者通向 c **自己**的 sink 端口（终端豁免按
商品键控），或者在邻格有 c 的接收态。于是 **c 的在场格集合对物理后继封闭**：
内容盲轮转推货沿物理边传播，永远走不出静态声明面。再叠加 sink front 地面排他
（别家商品在门口格不生成变量），错货抵达异商品机器输入口在结构上不可能。

这正是外审 B-01 要的性质，且论证不依赖准入口是否存在——外审 4 格反例的致命点
（支路上没有直行格）因此不再是缝隙：模型压根不产生需要准入口的解。

**已攻的最强缝隙：按层分道。** `_use_by_cell_dir_in_commodity` 是按**格**而非
(格,层) 索引的，所以地面件的出边可以被邻格的 L1 bridge 接收——两商品若能在邻格
一个走 L0 一个走 L1，就在没有任何 splitter 的情况下分了道，禁令看不见。答辩：
两商品从同一侧进入邻格，L1 bridge 只直行 ⇒ 其轴由进侧唯一确定；桥互斥
（`_add_bridge_constraints`）只在「L0 是直带且与 L1 轴**垂直**」时放行共存，而
同侧进入的 L0 直带必与该 L1 同轴，转弯带则根本不是直带 ⇒ 两种情况都被互斥掉。
**实测坐实**（探针 `.artifacts/mixflow_demix_ban_20260807/probe_layer_escape.py`，
几何 = a/b 在 (5,5) 合流、(6,5) 必须分开）：

| | 自由求解 | 追加「某格上 a 与 b 分处不同层」强制行 |
|---|---|---|
| 禁令开 | INFEASIBLE | INFEASIBLE |
| 禁令关 | FEASIBLE（(6,5) splitter 分道）| INFEASIBLE |

最后一格是关键读数：**按层分道即使在禁令关闭时也不可行**，说明堵住它的是桥互斥
（既有条款、本手术零改动），不是禁令——这条逃逸路径独立于本批就已封死。

**两道墙的分工（本批自查推翻过一次，范围必须说准）。** 在门口格剥离别家货本身
就是一次 de-mix（owner 朝端口出、搭车者朝别处出），而别家商品又不可能声明朝端口
的出边（端口背后是机身占用格，`_outgoing_dir_supported` 不成立、变量不生成）
——所以在两个**分道型**污染几何（门口分流、异向多 owner 门口格）上，禁令单独就
足以拒掉，只中和守卫它们仍 INFEASIBLE，守卫在这两处已不是唯一防线（对应的两条
承重哨兵因此改为同时中和两道墙）。

**但守卫没有被完全取代。** 本批一度写成「已被吞并」，自查时被自己的探针推翻：
BRIEF §4.1 登记的那个几何——两个异商品 sink 端口共 front 格且**同一终端方向**
（也是外审 F-02 的复现实例）——全程没有任何 splitter，**禁令发行零行**、完全
vacuous，守卫的多 owner 全排是唯一防线。注意
`_duplicate_terminal_front_keys`（`:190-242`）的重复键**含 commodity**，所以
「异商品同 front 同终端向」不会被它当重复口挡掉，确实会进模型。实测（探针
`.artifacts/mixflow_demix_ban_20260807/probe_guard_still_needed.py`，实例
`free={(1,0),(2,0),(3,0)}`、iron/copper 源同在 (1,0) dir E、汇同在 (3,0) dir W）：

| | 禁令开（`demix_ban.rows == 0`）| 禁令关 |
|---|---|---|
| 守卫开 | INFEASIBLE | INFEASIBLE |
| 守卫关 | **FEASIBLE**：三格全是 belt，每格 uses=[copper, iron] 双商品共乘，一条混流带同时灌两台机器 | FEASIBLE |

**结论：禁令管「分道」，守卫管「同向共 front 的混灌」，两堵墙谁也不能删。**
常驻台账拆成两条：`test_demix_ban_subsumes_purity_guard_on_split_geometries`
（分道型上只中和守卫仍 INFEASIBLE）与
`test_purity_guard_is_load_bearing_on_same_direction_multi_owner`（同向型上只
中和守卫即翻 FEASIBLE——守卫承重的真哨兵）。这也是 U-01 的直接前置：将来要解锁
仓储口/核心口混流准入，要拆的正是守卫这堵墙，拆之前必须先回答「同向共 front
混灌靠什么挡」。

### 9.4 M4 单调性订正（外审 F-02，BLOCK 解除条件 4）

v1 的「手术是纯放宽 ⇒ 新 INFEASIBLE 蕴含旧 INFEASIBLE」在 `RoutingSubproblem`
的**全 API 域上字面为假**，外审已复现最小反例（`free={(1,0),(2,0),(3,0)}`、
iron/copper 的 source 同在 (1,0) dir E、sink 同在 (3,0) dir W：BEFORE FEASIBLE /
AFTER INFEASIBLE，收紧来自多 owner 地面全排）。改写为带前提的命题：

> 对满足 placement/binding 可达性不变量的**生产输入**，旧可行解均可嵌入新模型；
> 额外的多 owner 收紧只拒绝游戏非法或上游不可达的输入。

③ 落地后还要再加一条：**de-mix 禁令是无条件的净收紧**。所以术后模型相对术前
既有放宽面（进侧自由 = 合流/共乘可表达）也有收紧面（多 owner 门口 + de-mix），
两个方向同时存在，**任何依赖「旧模型曾 INFEASIBLE」来论证 layout cut 安全的
代码或文档，都必须显式携带上述生产输入前提**，不得再引用全域单调性。

### 9.5 收益面实测：混流的送达面已清零（本批最重要的发现）

③ 的代价不是「少了 de-mix 这一种解法」，而是**在当前 sink-front 排他范围内，
混流格在任何能送达的可行解里都不可达**。链条（推导为主，走廊型实测佐证）：

1. 混流格上两商品的出侧集合相同（9.2 不变量）⇒ 后继格集合相同 ⇒ 由 successor
   约束，两商品的下游闭包完全共享，**从混流点起一路同行**；
2. 每个商品最终必须在自己的 sink front 经端口终端豁免收尾（port adherence 强制
   该 use 恰为 1）；
3. 在 a 的 sink front 上，b 要么被 `_mixflow_ground_banned` 挡掉，要么（守卫中和
   时）无法声明朝 a 机身的出边——而不变量逼它必须声明。矛盾。

**证据等级**：上面三步是**推导**（对模型条款的演绎），下表是**实测佐证**，不是
独立证明。探针方法可复述：给已建好的模型追加一行「至少存在一个 (格,层) 上有两
种商品同时在场」再求解——UNSAT 即表示该实例的任何可行解都不含混流格。

| 实例 | 强制混流格 + 禁令开 | 对照：禁令关 |
|---|---|---|
| U-02 宽1走廊（30s）| INFEASIBLE | FEASIBLE（merger + 共乘带 + splitter 三形态齐全）|
| source-front 共乘走廊（30s）| INFEASIBLE | FEASIBLE |
| 4×4 全自由空场（300s）| INFEASIBLE | — |
| 5×5 全自由空场（600s）| **TIMEOUT（无结论）** | — |

**如实报告**：空场越大，UNSAT 证明越难，5×5 就已经跑不出结论。所以「混流格不
可达」这条**以 1-3 步的推导为主证据**，实测只在走廊型（= 生产实际形态，pitch-4
点阵留下的就是宽1走廊）与最小空场上把它坐实。另有一个推导覆盖不到的退化角：
纯浮空环（两商品在一个与端口无关的闭环上互相支撑）在局部约束下不违反任何条款，
连通复验器也只查 sink 可达性——它可能作为无意义的附着物出现在某个可行解里，
但它不承载任何送达，不影响上面的结论。

所以本批的准确说法不是「零代价」，而是**零代价也零净收益**：手术留下的是基建
（per-commodity 子图样 key + 覆盖/精确侧缝合 + 侧指示布尔），表达面上合流与共乘
确实活着（禁令关闭的对照组逐条抽取证明），但送达面要等 **U-01**（仓储口/核心口
混流准入，DESIGN v1 §5.6 明示不在本手术范围）落地才可能兑现。接入批要不要为
它开门控开关，应当按这个账重算。

### 9.6 性能三点对照（生产规模 proxy，脚本进仓）

脚本 `docs/research/mixflow_surgery_20260806/bench_mixflow_prodscale.py`（外审
F-04 item 1 要的可复验件，**现在在仓库里**），同一 fixture、同一进程内三臂对测；
`pre` 臂从 `git show 5af80d0:src/models/routing_subproblem.py` 加载。复跑：

```
python docs/research/mixflow_surgery_20260806/bench_mixflow_prodscale.py --solve-seconds 120
```

fixture = §7 那套对抗性最坏 proxy（70×70、256 个 3×3 机体 pitch-4 点阵、宽1
走廊、19 商品、一体一口），`pre` 臂的四个数字与 §7 记录逐项对上（980,444 use /
53,444 phys / 3,999,723 约束 / build 19.5s、solve INFEASIBLE@27.7s），可确认是
同一装置。

| 指标 | 术前 5af80d0 | 术后（无禁令）| 术后 + ③ |
|---|---|---|---|
| use vars | 980,444 | 974,396 | 974,396 |
| phys vars | 53,444 | 53,444 | 53,444 |
| constraints | 3,999,723 | 5,897,344 | 7,888,989（禁令 1,991,645 行，全两文字）|
| **build** | **19.84s** | **20.67s（+4.2%）** | **23.88s（+20.4% / 较术后 +15.5%）** |
| solve（120s 帽）| INFEASIBLE @28.3s | **TIMEOUT** | **INFEASIBLE @113.9s** |

（2026-08-07 空载复跑，与首轮 19.9/20.73/24.26s、28.0/TIMEOUT/115.7s 一致；
原始 JSON 落盘 `.artifacts/mixflow_demix_ban_20260807/`。）

两条解读：

- **build 仍在 40s 预算内**：禁令加 199 万行，代价 ~3.2s。全部是两文字蕴含，
  走 CP-SAT 的二元蕴含图，单价极低（对比 §7 第一轮教训：同样量级的行数如果按
  朴素求和展开会把 build 顶到 2.4×）。
- **solve 反而修回来了**：§7 记的「术后 120s 内出不了结论」是可行域放大的固有
  代价，而 ③ 把可行域收回去，这个最坏 proxy 上重新在 120s 内证出 INFEASIBLE。
  也就是说 ③ 消掉的正是 §7c 开放问题 1（默认关开关）的主要动机。**但**这只是
  单实例单跑的对抗 proxy，不是启用门槛——外审 F-04 要的量化阈值、分层语料、多
  seed/worker 重复仍属接入批。

### 9.7 测试组重判与哨兵两层自证（BLOCK 解除条件 3）

`src/tests/test_routing_mixflow.py` 从 13 例扩到 **22 例全绿**；逐条重判：

| §6 原条目 | ③ 后 | 落点 |
|---|---|---|
| 1 U-02 复活（FEASIBLE）| **INFEASIBLE** | `test_u02_merge_then_split_now_infeasible`；中和对照 `test_u02_mutation_control_shows_merge_and_coride_expressible` 证明 merger / 共乘带 / splitter 三形态都还在，被拒的只是第三种 |
| 4 source front 共乘（FEASIBLE）| **INFEASIBLE** | `test_source_front_coride_now_infeasible` + 中和对照 |
| 2b 门口分流哨兵 | INFEASIBLE（不变）| 承重方从纯流守卫转到禁令，见 §9.3 与 `test_demix_ban_subsumes_purity_guard_on_split_geometries` |
| 2a/2c 门口转弯 / 异向多 owner | INFEASIBLE（不变）| 原样 |
| — 新增 | INFEASIBLE | 同向多 owner 门口格（BRIEF §4.1 / 外审 F-02 实例）进常驻负测，并配守卫的**真**承重哨兵——那处禁令零行，只中和守卫即翻 FEASIBLE |
| 回归组 | FEASIBLE（不变）| 垂直桥交叉、单商品分流、phys==uses 侧并集、连通复验器 |
| — 新增 | — | 4 格反例负测 + 中和对照；行域剪枝两条（宽1走廊零行、L1 无多出侧态）；`test_every_present_commodity_claims_all_outgoing_sides`（§9.2 不变量的解级读数）|

树内其余测试：`src/tests/test_routing.py` 31 例全绿，其中
`test_two_commodities_can_share_same_straight_belt_phys` 的端到端路线在 (4,2)
分道，已按新语义拆成「主张 INFEASIBLE」+「中和对照恢复原断言」两条——共乘直带
本身一格未被误伤（forcing helper 的成员断言即是子图样变量仍存在的白盒证据）。

**哨兵两层自证**：

- **常驻**：`test_demix_no_filter_slot_counterexample_is_infeasible` 把外审 4 格
  反例钉成负测；`test_demix_ban_is_load_bearing` 用 monkeypatch 中和禁令，断言
  它翻 FEASIBLE、抽取件正是外审报告的 (6,5) splitter（a:W→E / b:W→N）、且全局
  连通复验器仍 `failure_count=0`——即**逐字复现外审观察**，证明除禁令外无人拦得住。
- **源码级双移除**（2026-08-07 实测，两个独立变体）：①删 `build()` 里的调用点、
  ②保留调用点但掏空方法体。两次结果**逐条相同**：5 条 de-mix 哨兵齐红
  （`test_demix_no_filter_slot_counterexample_is_infeasible` /
  `test_u02_merge_then_split_now_infeasible` / `test_source_front_coride_now_infeasible` /
  `test_demix_ban_subsumes_purity_guard_on_split_geometries` /
  `test_two_commodities_sharing_a_belt_then_demixing_is_infeasible`），而
  `test_same_direction_multi_owner_front_stays_infeasible` **两次都保持绿**
  ——这条阴性对照正是 §9.3 分工的独立证据：那处几何靠的是守卫，禁令在场与否
  它都拦得住。还原后 sha256 逐字一致（`c1b8486…`）、6/6 复绿。日志
  `.artifacts/mixflow_demix_ban_20260807/mutation_verify.log`。

### 9.8 六条解除条件对照

| # | 外审条件 | 本批状态 |
|---|---|---|
| 1 | certified 路径默认关闭本手术，研究路径与认证状态严格分离 | **属接入批**。本分支不接 certified 开关；门控开关形态仍是 §7c 开放问题 1，且属 `EXACT_*` 闭合白名单，必须与 allowlist/lock/tests 同批动。**但开关的两条动机都被 ③ 抽掉了**：不可行证明速度已修回（§9.6），可行域放大的 soundness 风险已由禁令消除（§9.3），而混流红利在 U-01 前本来就是零（§9.5）——接入批应先决定「还要不要开关」，别默认照抄 v1 的设计。|
| 2 | 修复 de-mix 语义（三选一）| **本批已闭**：取 ③ 禁 de-mix，§9.2 约束 + §9.3 论证 + §9.7 双层哨兵。|
| 3 | 4 格无 filter 槽位反例进常驻负测；不再只复验静态标签图 | **本批已闭**（负测 + 中和对照）。「真实物品传播复验」在 ③ 下由 §9.3 的封闭性论证替代：模型不再产生需要物品级复验的解。|
| 4 | 修正 M4 单调性论证，明确生产输入前提与多 owner 收紧 | **本批已闭**：§9.4；并在 §5 顶部标注 v1 论证作废。|
| 5 | 性能脚本、原始日志、固定 corpus、量化阈值、timeout/fallback fail-closed 端到端测试 | **部分闭**：脚本进仓 + 三点数字可复跑（§9.6）。量化阈值、分层语料、多 seed/worker 重复、拒绝循环与模型增长上限、TIMEOUT 永不被解释为 INFEASIBLE 的端到端测试——**属接入批**（与 PIC 性能测同批）。|
| 6 | witness adapter 子图样兼容后，抽取结果须含/引用实现 de-mix 所需的物理构件证明 | **前提已消失**：③ 下不存在 de-mix 解，无物理构件需要证明。adapter 的子图样兼容欠账本身仍在（§7b 的 `route_adapter.py:300-301` 逐条相等断言），**属接入批**，方向仍是拒真不纳伪。|

## 10. U-01 仓储系口混流准入（2026-08-07）

### 10.1 语义依据与判决

owner 口岸三分法终审（`AXIOM_KERNEL_PROPOSAL.md` A4 参数表 + 推导 #1/#2/#3/#12）把
收货口分三类，混流准入面完全不同：

| 口 | 收货语义 | 混流准入 | 公理路 |
|---|---|---|---|
| 制造机输入口 | 收货不看配方、非配方货无消耗通道、A1 不回退 ⇒ 永久占位或按另一配方开工继续污染 | **禁**（地面门口纯流是唯一防线）| A9 + #1 |
| 有线仓储口（协议核心 14 进）| WarehouseSink 把落位改写进仓库的按类型槽（编译期预锁定、容量实践不可达）⇒ 对已注册开槽商品结构上不拒收 | **放开**——别家货被吞 = 合法入库 | A4 + #3/#12 |
| 协议储存箱（3 进）| 6 个独立单槽组的**有界**混吃：6 格占满即堵门，与类型数无关；堵门后的行为语义未定谳到可建模程度 | **第一期保守留在机器口规则** | #2、P2 |

边界仓储口 0 进 1 出、供电桩无口，都不产生 sink front，不入本节讨论。

于是模型此前「所有 sink front 一律地面排他」是一处**过严面**——它对仓储系口用了
制造机口的理由。U-01 把守卫按接收方口岸类别分叉，只保留有理由的那一半。

### 10.2 守卫分叉与分类通道

`_mixflow_ground_banned`（`src/models/routing_subproblem.py:1123-1170`）新增一条
前置分支：该格全部 sink 口都是仓储系口 ⇒ 不排他（连多 owner 全排也不要）；否则
逐字保留原规则（别家排他 + 多 owner 全排）。

分类判据**不是实例清单**，而是两段 hash-bound 数据接力：

1. **事实侧**：`BindingSubproblem.extract_port_specs`（`binding_subproblem.py:1478-1520`）
   给每条 spec 打 `operation_type`。它取自实例表，而 binding 在建域期已把
   `solution_facility_type` / `instance_facility_type` / `profile.facility_type`
   三者互校、不一致 fail-closed（`:745-790`）。
2. **策略侧**：`classify_sink_receiver`（`routing_subproblem.py:93-137`）把该
   operation 经 `OPERATION_PORT_PROFILES`（派生自冻结的
   `rules/preprocess_plan.json` 的 `utility_operations`）映射到 facility_type，再
   对 `WAREHOUSE_SYSTEM_SINK_FACILITY_TYPES = {"protocol_core"}`（`:85`）判定。

**一切缺口向保守方向塌**：字段缺失/为空/未知 operation/profile 表加载失败，全部
返回机器口。放宽不可能因遗漏发生——它需要一个冻结 plan 自己认识、且映射到仓储系
facility 的 operation 名。

**证据面零改动**：`_normalize_port_specs`（`pr2_l0_fixed_witness_core.py:1873-1896`）
是六字段白名单，`operation_type` 被剥掉 ⇒ `port_specs_digest` 与已发布的
`active_port_specs` 逐字不变，`serializer.py:396` 与
`pr2_l0_fixed_witness_core.py:2021` 那两处**键集全等**校验不受影响。见证链建
routing 用的是未 normalize 的 specs（`:1068-1073`），生产者与见证器看到同一份分类。

### 10.2b 本批是纯放宽（与 ③ 不同，单调性无前提）

③ 同时有放宽面与收紧面，所以 §9.4 必须把 M4 改写成带生产输入前提的命题。**U-01
是纯放宽**：它只删除生成期排除、不新增任何约束行，术前的任一可行解把新增变量
全取 0 即是术后可行解。于是 **routing 术后 INFEASIBLE ⇒ 术前 INFEASIBLE**，由
「routing 不可行」导出的 layout nogood 是在更弱的模型下导出的，只会更有据。

这一步有个不显然的环节，记下来免得将来被当成 bug：**分叉会顺带多生成 phys 变量**
（Pass 2a 的并集支撑变宽），而 `_add_demix_ban_constraints` 的 `multi_out_dirs`
是从已生成的 phys 键算的 ⇒ 同一个 use 变量可能**多收到几条禁令行**。看上去像收紧，
其实不改变旧解：新行形如 `use ⟹ ¬phys_side_out[d]`（d ∉ 该 use 的出侧），而旧解在
那格上满足「在场商品出侧集合 ≡ phys 出侧集合」——若该格旧模型零行，是因为全部
phys 单出侧，此时 `phys_side_out` 只有一侧为真且等于 use 的唯一出侧，故对一切
d ∉ flow_out 都有 `phys_side_out[d]=0`，新行平凡满足。两种情形都不淘汰旧解。

### 10.3 混合 owner 格与箱口

**混合 owner**（一格同时是仓储口与制造机口的 front）：**保守回机器口规则**。理由是
排他是格级的——喂同一个 front 格的物理件不可能只朝其中一个口送货，一格上只要有
一个可中毒的收货方，整格就得按最严的规则来。实现上就是 `receiver_classes <=
{WAREHOUSE_SYSTEM}` 这个**全称**判据（`:1163-1165`）。

**箱口**：有界混吃 ≠ 无限混吃。A4 直接把协议箱判在仓库系口之外（「不属仓库系口：
无连接、仅箱→仓库单向无线提交，本体走机器机制，且需电」），#2 又给出它会堵：
6 格占满即堵门、与占用它的类型数无关。放宽的判据是「结构上永不拒收」——核心口
满足（#3/#12），箱口不满足。而「堵门之后」的语义（拒收回退 vs 队头阻塞、能否与
A1 的「留在上游等待」区分、A8 断电时永不清空）没有定谳到可建模的程度，放开箱口
等于在模型里断言「箱永不拒收」，与 #2 直接冲突。所以第一期箱口留在机器口规则；
准入需要的语义前提列在 `OPEN_REVIEW_QUESTIONS.md` Q8 给 owner。

**速率注记**（不进模型）：终品共道汇入核心的形态，其汇流点有 2s CD、双输入竞争下
最坏各减半（A7 + owner 08-06 附注）。认证六谓词不含吞吐（`PROJECT_LOCK.md` §1A B
块），模型侧**无速率义务**；这笔账归 P2.0，不构成本节任何条款的前提或后果。

### 10.4 红利面：守卫分叉单独兑现不了（本批最重要的发现）

任务书委托 U-01 的目的是让「终品共道送进仓储系口」成为可行解。**实测：分叉后该
形态仍 INFEASIBLE**，挡住它的不是守卫而是 ③。

**四臂读数**（几何 = core 西面两个相邻输入口，a/b 共乘一条南北向带，b 在 (4,5)
下车、a 继续到 (4,6) 下车；探针 `.artifacts/mixflow_u01_20260807/probe_u01_guard_alone.py`）：

| | ③ 开 | ③ 关 |
|---|---|---|
| 守卫开 | INFEASIBLE | INFEASIBLE |
| 守卫关 | **INFEASIBLE**（demix rows=9）| FEASIBLE（(4,4) merger 共乘 + (4,5) splitter 下车）|

真实分叉复核（`probe_u01_fork_behaviour.py` §3）给出同一读数，且
`build_stats.mixflow` 显示 `warehouse_system_sink_fronts=[[4,5],[4,6]]`、
`purity_excluded_cell_layers=0`——守卫确实一格没挡。

**机制**：「共道下车」在几何上**就是分道**。b 在 (4,5) 拐进口、a 继续走，该格物理件
必然是 splitter S→{N,E}；③ 的行 `use_a(S→N) ⟹ ¬phys_side_out[E]` 与 b 的 port
adherence 逼出的 `phys_side_out[E]=1` 直接矛盾。

更一般地：**③ 在场时，守卫在单 owner front 格上已被完全吞并**。别家货要在 a 的
门口格出现，就得声明那条朝机身的终端出边（③ 逼在场商品声明全部出边），而终端豁免
按商品键控（`_outgoing_dir_supported` `:1091-1096`）——它声明不了。守卫真正单独
承重的只剩「同格同向双 owner」，而该几何在真实 placement 里造不出来（两个口共
front 格且同终端向 ⇒ 同一个机身边缘格 ⇒ 同一台设施上两个口重叠）。

所以 **③ 与 U-01 不正交**，「共道下车的终点是同一格、不需要分道」这个立项前提在
真实几何下不成立：终点同格意味着两个口共 front 格，正是那个不可达的形态。

**「不可达」是实测坐实的，不是推测**（探针 `probe_u01_fork_behaviour.py` 与冻结
输入全扫）：

- 冻结候选池：`protocol_core` 7,688 个 pose、`protocol_storage_box` 18,496 个
  pose，**没有一个 pose 的两个输入口共 front 格**（核心 14 口 = 14 个互异 front
  格）⇒ 同格双 sink 必来自两台不同设施；
- 冻结实例表：`protocol_core` 恰 1 个实例，且可 pose-optional 实例化的模板只有
  `protocol_storage_box` 与 `power_pole`（`binding_subproblem.py:59-62`）⇒ 不可能
  有第二个核心；
- 于是「两个仓储系口共 front 格」只能是核心口与箱口对脸，而箱口按机器口规则处理
  ⇒ 混合类别 ⇒ 回机器口规则。

**结论：本批在生产输入上的放宽面是空集。** 266 个实例里恰 1 个落 warehouse_system
类（14 个输入口），其余 265 个全落机器口；那 14 个 front 格的排他被解除，但按上面
的机制它们开不出任何新解。本批因此是**语义订正 + `wh_drain` 方案的前置**，不是
收益批——接入决策要按这个账算，别按立项时的红利预期算。

**为什么不能顺手放宽 ③**：「在仓储口终端侧免除禁令」不 sound——分道处物理件内容
盲，**两种货都会被轮到两条支路上**。别家的货也会被推向继续走的支路，只有当那条
支路下游的每个下车口都是混吃安全口时才无害；下游若有制造机口，就回到外审 B-01
原判。

**sound 形态草案（未实现）**：给每个 (格,层) 加布尔 `wh_drain`，语义 = 从该格沿
物理出边走、所有终点都是仓储系口；禁令行放宽为
`use ⟹ ¬phys_side_out[d] ∨ wh_drain[格,层]`，配递归蕴含
`wh_drain[c] ∧ phys_side_out[c,d] ∧ ¬(d 是该格仓储系终端侧) ⟹ wh_drain[邻格]`，
邻格不在域内或是制造机 front 则强制 0；闭环上可取真（货循环、不进任何机器口）。
代价 = 每格每层 1 布尔 + 三文字行。这是新约束类、soundness 敏感，**属新批**，
需重走外审（攻击面见 `OPEN_REVIEW_QUESTIONS.md` Q10）。

### 10.5 测试组与两层自证

`src/tests/test_routing_mixflow.py` 22 → 38 例。

- **分类溯源**：facility_type 从 `OPERATION_PORT_PROFILES` **读回**而非在测试里
  重述，冻结 plan 改标签会在这里暴露；伪造名/空/None/箱/边界口全部落机器口。
- **机器口分支承重**（既有哨兵按口类别参数化）：同向多 owner 几何在五种机器口
  形态（缺字段/空/未知名/真机器/箱）下各自 INFEASIBLE，只中和守卫则各自翻
  FEASIBLE ⇒ 每个分支独立承重，没有一个是靠邻居分支挡住的。
- **分叉承重**：仓储系口几何在无任何中和下 FEASIBLE；**策略集变异**——把箱加进
  `WAREHOUSE_SYSTEM_SINK_FACILITY_TYPES` 则同一实例翻 FEASIBLE，证明箱的保守决策
  由该集合承重、不是被别的约束顺手挡住的。
- **红利面负测**：相邻仓储系口共乘下车常驻 INFEASIBLE + 中和 ③ 的对照（抽取解
  含 (4,4) merger 与 (4,5) splitter、连通复验 `failure_count=0`）。

**源码级三变体自证**（`.artifacts/mixflow_u01_20260807/mutation_verify_fork.sh`，
日志同目录）：A 删分类分支 / B 停止打标 ⇒ 3 条 unlock 齐红、10 条机器口哨兵**全绿**
（阴性对照：分叉不是它们的墙）；C 分类器改 fail-open ⇒ 机器口哨兵红 1
（`unknown_operation` 参数）、unlock 绿。还原 sha256 逐字一致。

**首轮 C 全绿是本批自查抓到的哨兵缺口**：fail-closed 默认当时只有单元断言、没有
几何级哨兵，未知 operation 名从未出现在任何被求解的场景里。补 `_UNKNOWN_OPERATION`
场景参数后复验才红。教训与 §6 那条同源——哨兵必须选「除该条防线外全合法」的几何，
单元断言不能替代解级读数。

### 10.6 六条解除条件的增量

U-01 不改变 ③ 批对六条外审解除条件的判定（§9.8 逐条仍然有效），只增两条注记：

- **条件 1（certified 默认关本手术 / 门控开关）—— 2026-08-07 team-lead 拍板关闭：
  不做开关。** §9.8 曾判「③ 抽掉了开关的两条动机，接入批应先决定还要不要开关」，
  §11.10 曾判「wh_drain 落地后开关问题重开」。**现在关掉，理由是 soundness 的方向性，
  不是工程口味**：

  - **③ 单开（无汇流区）= 比游戏更严**——它杀掉合法的「仓储口共乘下车」。对 witness
    复验方向是保守的，**但对 nogood / 最优性链是假 INFEASIBLE 风险**：一个真最优的
    几何可能因此被错误排除，而 layout nogood 会把这个错误固化下去。
  - **汇流区单开（无 ③）= 回到 B-01 污染**，直接 unsound。
  - **两个都开才忠实。单独关任何一个，都在一个已知方向上不忠实。** 所以
    「③ + 汇流区」在 certified 下是**一个语义单元**，没有独立开关。

  性能动机已被真实口数臂杀死（§11.9：生产口数下代价在噪声内）。剩下的唯一开关动机是
  「万一外审打穿 §11.3 的归纳」的保险——**那个场景的正确工具是审查 + freeze-ritual
  回滚，不是运行时双态**：双态会让测试面翻倍、变异哨兵要覆盖两态，为的是一个假想收益。
- **条件 6（witness adapter 子图样兼容）**：新增一条同族欠账——从已发布 carrier
  **反建** routing 的消费者拿不到 `operation_type`，会全部落机器口、比生产者严。
  方向是拒真不纳伪（安全），但意味着 U-01 的红利过不了这类复验。当前树内没有这样
  的消费者（扫描结论见 `OPEN_REVIEW_QUESTIONS.md` Q11），接入批需复核该否定结论
  的范围。

### 10.7 全量 lane 的三条账（都有单变量对照）

完整红台账 `.artifacts/mixflow_u01_20260807/EXPECTED_REDS.md`。三条值得写进设计的：

**(1) port spec 形状是被三处测试钉着的契约。** 加 `operation_type` 打破了三处对
`extract_port_specs()` 输出的**逐字典全等**断言（`test_wireless_front_consumers_r4.py`
两处、`test_wireless_sink_binding_semantics.py` 一处）。正确处理是把断言更新到新
形状、继续守着漂移（提交 `5166fab`），不是把字段藏起来绕开。生产侧消费方逐个核过，
全部按键取值、无键集校验。

**(2) routing 的 `build_stats` 会被摘要进 candidate record。** 本批加的两个审计键
把 `test_golden_toy_supervisor_seal_semantic_digests` 的实际 digest 从 `3374bf0f…`
推到 `cf382458…`。两级单变量对照坐实了归因：还原 routing+binding 到 `fb76e15` ⇒
`3374bf0f…`（与 ③ 批记录逐字一致）；**只**去掉那两个键 ⇒ 也回到 `3374bf0f…`。
所以 `operation_type` 确实没进证据面（被 `_normalize_port_specs` 剥掉），推动
digest 的是 build_stats。

本批**保留**这两个键：U-01 是 soundness 敏感的放宽，把「本次求解放开了哪些 front
格」放进被摘要的证据，等于让一份 CERTIFIED 工件自己回答「有没有放开过什么」。
代价是 golden 常量随接入批 freeze-ritual 重钉（它本来就在重钉清单上）。这是可被
推翻的决策，已列为待审 Q12。

**(3) ③ 批 `open_yard_8x8` 探针装置的端口朝向不忠实（顺带发现）。** 机身在 front
格的 `DIR_OPP[dir]` 方向，而该装置的朝向把机身放在**院子内部的自由格**上。后果是
同一条终端出边既是端口又是通往自由格的格间边，别家商品可以合法声明它。U-01 之后
该场景「强制混流格」求解出 FEASIBLE、抽取解里 a 的 sink front 是双商品共乘 belt
——**看上去像红利兑现**。把四个口翻向、机身落到院子外的忠实变体重跑，读数回到
TIMEOUT（60s 无结论），与 ③ 批原装置同级。**那个 FEASIBLE 是装置产物，不是收益。**

③ 的结论不受动摇（该场景原读数是 INFEASIBLE/TIMEOUT，装置更宽只会让 INFEASIBLE
更强、TIMEOUT 仍是无结论；承重结论用的是走廊型与 4×4 空场的 UNSAT），但装置本身
要处置——已列为待审 Q13。教训与 §10.5 首轮变异 C 全绿同源：**装置的语义忠实性要
和结论一起被审，「解出来了」不等于「解的是那个问题」。**

### 10.8 性能四点对照（§9.6 三点表的续表）

脚本加了第四臂：`python docs/research/mixflow_surgery_20260806/bench_mixflow_prodscale.py
--solve-seconds 120`，同一 fixture、同一进程内四臂对测。u01 臂把**全部 128 个
sink 口**都声明成有线仓储口——这是**分叉代价的上界**，不是一个布局（真实基地只有
一台核心、14 个输入口）。原始 JSON `.artifacts/mixflow_u01_20260807/bench_u01.json`。

| 指标 | 术前 5af80d0 | 术后（无禁令）| 术后 + ③ | 术后 + ③ + U-01 |
|---|---|---|---|---|
| use vars | 980,444 | 974,396 | 974,396 | **980,444** |
| phys vars | 53,444 | 53,444 | 53,444 | 53,444 |
| constraints | 3,999,723 | 5,897,344 | 7,888,989 | 7,930,605（+0.5%）|
| de-mix 行 | — | — | 1,991,645 | 2,005,037 |
| 门口排除的(格,层) | — | 2,304 | 2,304 | **0** |
| 仓储系 front 格 | 0 | 0 | 0 | **128** |
| **build** | 19.78s | 20.47s | 23.83s | **23.54s** |
| solve（120s 帽）| INFEASIBLE @27.9s | TIMEOUT | INFEASIBLE @111.9s | **INFEASIBLE @110.7s** |

三条读数：

- **use 变量精确回到术前值**：980,444 − 974,396 = 6,048，正是手术当初被 sink-front
  纯流排除掉的那批变量，U-01 把它们一个不多一个不少地放了回来。这是分叉真的生效
  且只影响该面的独立佐证（`purity_excluded_cell_layers` 2,304 → 0 同向）。
- **build 与 solve 都没有代价**：build 23.54s vs 23.83s（同一装置空载复跑的抖动
  量级，甚至更快一点），solve 仍在 120s 内证出 INFEASIBLE（110.7s vs 111.9s）。
  ③ 修回来的不可行证明速度**没有**被 U-01 重新推坏——这一点本来是最需要担心的，
  因为放宽可行域正是 §7 里让 solve 从 27.7s 变 TIMEOUT 的原因。没有变坏的机制性
  解释见 §10.4：③ 在场时这些新变量组不出任何新解，可行域实际没变大。
- phys 变量零增：本形态下并集支撑 = 单商品支撑（与 §7 同一观察）。

**注意这是上界臂**：真实基地 266 个实例里恰 1 个落仓储系口类（核心，14 个输入口），
不是 128 个。真实代价比这张表更小。

## 11. 混吃汇流区（wh_drain，2026-08-07）

> §10 把守卫按口类型分叉，实测发现红利兑现不了（§10.4）——挡住终品共道下车的
> 是 ③ 而不是守卫。team-lead 2026-08-07 据此拍板把本批扩到「混吃汇流区」。
> 本节是该扩展的落地记录。**与 §10 冲突时以本节为准**（§10.4 的「红利为零」
> 是扩展前的实测，扩展后已兑现）。

### 11.1 要解决的问题，与「不能顺手放宽」的边界

③ 的不变量是「每格每层所有在场商品的出侧集合 ≡ phys 出侧集合」，它蕴含商品的
在场格集合对物理后继封闭，于是内容盲轮转推货永远走不出静态声明面——这是外审
B-01 要的性质。代价是它按**全局**陈述，顺带禁掉了 owner 口岸三分法说安全的形态：
终品共乘一条带、逐个下车进有线仓储口。

「共道下车」在几何上**就是分道**：b 拐进口、a 继续走，该格物理件必然是 splitter。
所以任何只放宽门口纯流守卫的做法都兑现不了它（§10.4 四臂实测）。

**为什么不能简单地「在仓储口终端侧免除禁令」**：分道处物理件内容盲，**两种货都
会被轮到两条支路上**。别家的货也会被推向继续走的那条支路，只有当那条支路下游的
每个下车口都是混吃安全口时才无害；下游若有制造机口，就回到 B-01 原判。所以豁免
的判据不能是「这一侧安全」，必须是「从这里出发的**全部**物理路径都安全」。

### 11.2 约束形态

`wh_drain[格]`（`_add_warehouse_drain_constraints`）语义 = **从该格出发的每条物理
出边路径都终于仓储系口**。禁令行在区内放宽为三文字：

```
use[x, y, layer, *, flow_out, c]  ⟹  ¬phys_side_out[x, y, layer, d] ∨ wh_drain[x, y]
                                     对每个 d ∉ flow_out
```

传播（对每个 (格,层) 的每条被携带出侧 d）：

```
wh_drain[c] ∧ phys_side_out[c, layer, d]  ⟹  d 是 c 的吸收性仓储出口 ∨ wh_drain[邻格]
```

邻格不在路由域内且该侧不是吸收性出口 ⇒ `¬wh_drain[c] ∨ ¬phys_side_out[d]`（强制假）。

**制造机口因此自动被封死**：其朝端口侧指向机身，机身 occupied ⇒ 不在域内，又不是
仓储出口 ⇒ 该格 wh_drain 强制假；falsity 再沿一切可能把货送到该机器的路径逐跳
回传。不需要为机器口写任何专门条款——它是同一条规则的落点。

三个设计决定，都不显然：

1. **变量按「格」而非「(格,层)」**。物理出边跨到邻**格**，而邻格的哪一层接收它
   本身是解的一部分（`_use_by_cell_dir_in_commodity` 正是按格索引，③ 批 Q1 的
   跨层逃逸讨论就源于此）。要求邻格**两层**都是 drain 是保守读法，且把跨层这个
   讨论面整个绕开。
2. **吸收性出口额外要求「邻格不在域内」**（`_is_warehouse_drain_exit`）。机身格
   本就 occupied，这条看似冗余——它是对**畸形输入**的防线：若调用方给出机身格
   可路由的口，同一条侧边既是「端口」又是「通往自由格的格间边」，当成吸收出口
   会让货无检查地离开闭包。③ 批的证据里正好有这种装置（§10.7 (3)），所以这不是
   假想威胁。有独立测试钉死两个方向（畸形 ⇒ 不算出口；机身在域外 ⇒ 算出口）。
3. **无任何仓储系 sink 口 ⇒ 不建变量、不发行**。只有机器口的实例与 U-01 前逐字
   相同，既有测试与生产的机器口世界零影响。

### 11.3 soundness 论证（正面写全）

**命题**：任何满足全部约束的解里，内容盲物理件都不可能把任何商品的货送进制造机
（或任何非仓储系）输入口。

**证明**（对物理传播路径归纳）。取任一被选中的物理件在格 c、其任一出侧 d，考虑
沿该边离开 c 的一件货。分两种情况：

- **c 不在汇流区**（`wh_drain[c]` 为假）：③ 的禁令行原样生效，c 上每个在场商品
  的出侧集合 ≡ phys 出侧集合，于是 c 的在场集合对物理后继封闭（§9.3 原论证逐字
  有效，本批一行未动）。货沿 d 到达的邻格上，该商品仍在场；归纳继续。终止于
  某商品自己的 sink front，由 port adherence 保证；而别家商品到不了那里，因为
  机器 front 格的地面排他（§10.2 分叉后仍对机器口全额生效）不生成它们的变量。
- **c 在汇流区**（`wh_drain[c]` 为真）：由传播行，d 要么是 c 的吸收性仓储出口，
  要么邻格也在汇流区。前者货被写进仓库按类型槽（A4 + #3/#12：对已注册开槽商品
  结构上不拒收）= 合法入库，路径终止；后者归纳继续，且**归纳假设保持**（邻格
  也在区内）。

于是从任一汇流区格出发的每条物理路径，只能停在仓储系口或永远留在区内。而**任何
喂制造机口的格都不可能在区内**：该格朝端口的侧邻格是机身、不在域内、也不是仓储
出口，传播行直接强制 `wh_drain` 为假。∎

**这条论证正对着 B-01 的攻击模式**。外审 B-01 说：模型声明「a 走北 b 走东」，而
内容盲 splitter 不认货，所以声明不可实现。本批的回答不是「声明可实现」——它**不**
可实现，本批也不假装它可实现——而是：**在汇流区内，声明与实际的差异不产生任何
可观察的违规**。b 的货被轮到 a 的支路上会怎样？沿归纳它只能进仓储口，被存起来。
a 的货被轮进 b 的下车口会怎样？同样被存起来。外审那个 4 格反例（两条支路都是
转弯终端、没有直行格放准入口）在本机制下**根本不需要准入口**：它的两条支路终点
若都是仓储口，混着走本来就无害；若有一条终点是机器口，闭包在那里强制假、整条
路径回传强制假，该 de-mix 仍被拒（`test_drain_closure_rejects_dropoff_whose_lane_ends_at_a_machine`
是这条的常驻实例——同一几何只把一个端口从核心换成制造机，判决翻转）。

**binding 计数的语义**（外审必问）：货被轮进别家仓储口后，谓词 (4) 的端口精确
计数还成立吗？成立，且不需要额外论证——谓词 (4) 计的是**端口绑定的多重度**
（哪个口绑哪个商品、口数是否精确），不是**通过量**。「a 的一件货进了 b 的核心
下车口」是一次运行期搬运，不改变任何端口的绑定。认证六谓词里没有任何一条对
「某商品实际到达其 sink 的件数」作断言——吞吐/带宽/离散容量流明确
out-of-scope（`PROJECT_LOCK.md` §1A B 块），连通性谓词 (5) 也只要求**静态可达**
（W-CONN-01：双向可达 + 允许多岛 + 非吞吐）。本批因此**不**改变六谓词中任何一条
的语义，只改变哪些布局能通过谓词 (5) 的模型编码。

**谓词 (5) 的忠实性没有被动摇，理由比上面更直接**：精确侧行让被选物理件的侧集合
**等于**全体 use 侧的并集，所以**每一条被声明的边都是真实存在的物理边**——声明从不
凭空多出边来。汇流区放宽的方向是单侧的：**物理件做的比声明的多**（内容盲轮转会用
上声明者没声明的那些侧），而 §11.3 的归纳恰恰就是证明「多出来的那部分」到不了任何
可中毒的收货方。于是连通性断言（每个 sink front 可达自某 source front 等）在物理
布局上逐字为真，复验器 `_validate_selected_route_connectivity` 一行未改也仍然在验
同一件事。

**静态连通 vs 动态送达**：本批把两者的差距**扩大**了，且这是诚实披露的。术前
（纯车道模型）「静态连通」恰好蕴含「声明的货真的按声明走」；③ 用封闭性把这个
蕴含保住；汇流区**放弃**这个蕴含，换来的是一个更弱但足够的性质——「货到不了可
中毒的收货方」。要的是后者：谓词 (5) 从来没有承诺过前者（§5.7 的三层答辩里第 ①
条已如实写过）。**任何未来想从 CERTIFIED 工件推出「某商品按某路线送达」的读法，
在汇流区存在时都不成立**；工件里 `build_stats.warehouse_drain` 记着本次求解是否
声明过汇流区，正是为了让这个问题可被审计地回答（§10.7 (2) 的保留决定即为此）。

### 11.4 闭环与无环化

闭包行是纯蕴含，一个无出口的 drain 环平凡满足它们，求解器可以取最大不动点把环
标成 drain。**这不 unsound**：货在闭环上循环，连收货方都到不了，更谈不上可中毒的
收货方；循环本身是吞吐/堵塞层的现象，out-of-scope（`PROJECT_LOCK.md` §1A B 块）。
论证的措辞因此写成「货到不了可中毒收货方」而非「货总会到某处」——后者对环为假，
前者对环为真。

但它仍是审查者必须被说服一遍的形态，所以按 team-lead 要求直接禁掉
（`_add_warehouse_drain_acyclicity`）：

```
wh_drain[c] ∧ phys_side_out[c, layer, d]  ⟹  rank[邻格] < rank[c]
```

对每条传播侧发行；吸收性出口不发行（货在那里离开网格），邻格不在域内的侧已被
闭包行强制假。**每条 rank 行都以 `wh_drain[c]` 为条件**，所以不声明汇流区时整个
机制消失——这保住了「U-01 相对 ③ 模型是纯放宽」（§10.2b）：把全部 drain 变量取假
即逐字回到术前模型，rank 行一并平凡满足。

差分实测（探针 `.artifacts/mixflow_u01_20260807/probe_drain_acyclicity.py`，几何 =
专门造的可载环实例）：

| | 无环化开 | 无环化关 |
|---|---|---|
| 强制环（四条环侧 + 四格 drain 全钉真）| **INFEASIBLE** | FEASIBLE |
| 自由求解 | FEASIBLE | FEASIBLE |

第二行是防误伤的对照：无环化没有悄悄拒掉普通解。

### 11.5 箱口：条件已论证，实现留二期

**参数（owner 2026-08-07 重申）**：协议箱在**通电**且默认开关打开时，每 **10s** 把
6 个缓存格的全部内容无线提交进仓库。**这条不是新增参数——它已经在 canonical 里**：
`semantics.protocol_storage_box_wireless`（main）原文「with power and its default-on
switch, the box flushes its 6 cache slots into the warehouse every 10s」。所以没有
「追加挂下批 freeze-ritual」这件事要做。

#### 11.5.1 「区内种类 ≤6」是错的条件——canonical 已点名退役该读法

本节初稿按「6 槽 ⇒ 每 10s 窗口至多 6 **种**」写过一版条件准入。**那是错的**，订正如下。

main 的 `protocol_storage_box_wireless.slot_count_clause`（2026-08-06 owner 裁决）原文：
6 槽是 **6 个独立单槽组**（组内排他真空、不跨组），一槽一商品，**同一商品可占多槽**，
箱阻塞当且仅当 6 槽全占，**「REGARDLESS of how many commodity types are involved」**，
并明确「the earlier **'six different commodities' phrasing was an example, not a
bound**」。**两种商品照样能占满 6 槽。** 所以种类计数既不充分也不必要，它是 canonical
点名作废的那个量。任何「≤6 种」的静态检查都是在检查一个已经不存在的条件。

#### 11.5.2 箱其实有一条更强的论证，但它是 owner 裁决面的动作

让机器口不安全的根本机制是**永久占用**：A9 的 intake recipe-blind + A1 的 no return
⇒ 非配方件落进缓存槽后没有消费通道，**永远**占死那个槽。箱没有这个机制——10s flush
无条件清空全部槽，而供电由**认证谓词 6** 保证（A8：不通电就不 flush，而谓词 6 要求
被供电设施落在电杆覆盖里）。**所以箱结构上不可能被毒死。** 剩下的「6 槽占满」是阻塞，
属吞吐层，`PROJECT_LOCK.md` §1A B 明列 out-of-scope；且阻塞的后果要么是上游原地等待
（A1），要么是内容盲分流器把货拨到另一条支路——**而汇流区闭包不变量保证每一条支路都
仍在闭包内**（§11.3），所以拨到哪都到不了可中毒的收货方。

**但这条论证需要一个我无权做的动作**：canonical 的 `mixed_commodity_flow.terminal_clause`
把箱放在 class (2)「BOUNDED mixed absorber」，与 class (1)「structurally non-rejecting」
**并列而非等同**，安全判据写成「terminates at class (1)，**or within the stated bound at
class (2)**」。把箱放进 drain 终点集 = 在模型里把 class (2) 提升成 class (1)。
**这是裁决面的 promotion，属 owner。**

#### 11.5.3 而且当前红利必然是零

266 个 mandatory 实例里**没有一个协议箱**（manufacturing_3x3 ×132、manufacturing_5x5
×49、boundary_storage_port ×46、manufacturing_6x4 ×38、protocol_core ×1）。箱是
pose-optional（`binding_subproblem.py` 的 `POSE_OPTIONAL_OPERATION_BY_TEMPLATE`），
下界 0，没有任何约束迫使实例化。**所以箱进 drain 终点集，和守卫分叉一样（§10.4），
当前生产几何下的放宽面是空集。**

#### 11.5.3b owner 已裁：箱是汇流区合法终点（2026-08-07）

**上面 §11.5.2 说「这条论证需要一个我无权做的动作」——那个动作 owner 已经做了。**

裁决大意（owner 08-07；**经记忆层转达，请主线确认转述无误**）：实际基建本来就拿箱当
收货口，限制加多了，能不能收货是**推出来的**不是规定出来的。推法：

- 3 个输入口 × 1 件/2s ⇒ 每个 10s 冲刷周期进货 **≤15 件**；
- 缓存 6 槽 × 50 件 = **300 件**，且每周期清零 ⇒ 件数维度 15 ≪ 300，不成立问题；
- 槽数维度：纯流喂养下 3 个口至多喂 **3 种** ⇒ 至多占 3 槽 < 6 ⇒ **阻塞判据（6 槽
  全占）结构上不可达，连暂时堵门都没有**；
- 混流带理论上要在 10s 内送来 **7 种以上**才会出现门口等待（且等待上限 10s），而
  **本实例的仓储系候选商品只有 2 个终品，凑不出 7 种**（与 §11.5.3、§11.12 前置 5 的
  绑定域构造事实一致）；
- **且永不中毒**——与 §11.5.2 独立推出的结论一致。

**结论：class (2) → drain 终点的 promotion 已获准。** canonical 的措辞改判挂**下一批
freeze-ritual**。于是 §11.5.5 听诊协议的第 3 步简化：**诊断臂翻案 ⇒ 直接走
freeze-ritual 实现，不必再排 owner 队列。**

**但这不改变本批仍不做箱口**：本批已封树、且 §11.5.3 的红利空集与 §11.5.5 的触发条件
都没变——箱零实例，诊断臂还没有任何布局可送。裁决在手只是把二期的**闸**打开了，没有
把二期的**触发条件**提前。

#### 11.5.4 一期结论

箱口维持机器口规则（`WAREHOUSE_SYSTEM_SINK_FACILITY_TYPES` 不含
`protocol_storage_box`），该保守决定由策略集变异哨兵承重（§10.5）。二期的任务不是
「实现种类计数」，而是**请 owner 裁决 class (2) → drain 终点的 promotion**（论证走
§11.5.2 的不可毒死，不走计数）。若 owner 拍了，实现确实顺手：终点白名单 + 污染孪生
箱口版 + 哨兵，**不需要新变量类**。两条前提与完整设计列在 `OPEN_REVIEW_QUESTIONS.md`
Q14。

#### 11.5.5 二期怎么触发：听诊协议（owner 追问「解不会说话」的答复）

owner 2026-08-07 追问：「等解想用箱」——**解不会说话，怎么知道它想用？** 所以二期的
触发不能写成「等将来需要时」这种被动措辞，下面是机械可执行的协议（team-lead 08-07
拍板，本节为正文）。

**第 1 步：多数结局里这个问题自动消解。** 箱口放开是**纯增解**的放宽。若双侧夹逼在
**无箱**的模型下就闭合（上界侧摸到与车道分配无关的松弛），那么箱从来没被需要过——
**沉默本身就是证明**，不需要任何检测动作。

**第 2 步：主动触发条件（唯一的那个信号）。** 任一**有价值候选**死于 routing
INFEASIBLE 时，把该布局送**箱口诊断臂**重跑。诊断臂在同一模型上放开**两个**自由度，
**必须同时开**：

- (a) 箱口进 drain 终点集（`WAREHOUSE_SYSTEM_SINK_FACILITY_TYPES` 加
  `protocol_storage_box`）；
- (b) 允许箱实例化（放开 pose-optional 的箱实例下界）。

**为什么必须同时开——这是本协议的关键，也是它区别于「等等看」的地方**：这是一对
**双重哑巴**。只开 (b)，模型不给箱口任何好处，它就没有理由放箱（箱口仍按机器口排他，
放箱只是多占格）；只开 (a)，箱口有了好处但一个箱实例都没有，规则作用在空集上。
**两个自由度各自单独都恒为零效果，只有同时开才可能观测到差别。** §11.5.3 说的
「箱当前零实例」正是 (b) 侧那个哑巴。

诊断臂 **diagnostic-only**：永不产出证据材料、永不进 certified 路径、其 FEASIBLE 不能
升格为任何结论——它只回答一个是非题「这个死因跟箱有没有关系」。

**第 3 步：分流（owner 08-07 裁决后已简化）。** 诊断臂**翻案**（同布局在双自由度下变
FEASIBLE）⇒ **直接走 freeze-ritual 实现**——class (2) → drain 终点的裁决 owner 已经拍了
（§11.5.3b），不必再排 owner 队列。**不翻案** ⇒ 死因与箱无关，实现继续挂起。

本步骤初稿写的是「翻案才去请 owner 拍裁决」，那是裁决到手之前的形态；留这句是为了让
读者知道协议的哪一环因为什么而缩短了。

**方法论出处**（这两条都是仓库已交过学费的）：

- 单开关差分 + 污染孪生对照的形态，与 §11.6 兑现红利时用的实证同构——**先证「放开确实
  是那个开关在起作用」，再谈要不要放开**；
- 「**结构上不可达的触发器永不有机触发**」：cut 框架跑了 7,187 轮零激活，就是因为触发
  分支在当时的口径下结构上到不了。双重哑巴正是这类结构，所以必须靠**主动构造的诊断臂**
  去问，等不来自发信号。

**与 §11.12 前置 2 的衔接**：那条把口数扫描臂的触发词写成「箱口实例数下界 > 0」。
实例化**不会自发发生**——它的上游就是本协议的第 2–3 步。两条因此闭合成一条链：
候选死于 routing INFEASIBLE → 诊断臂 → 翻案 → owner 裁决 → 实例下界 > 0 → 口数扫描臂
→ 接线。

### 11.6 测试与两层自证

`src/tests/test_routing_mixflow.py` 38 → 43 例。

- **红利正测** `test_warehouse_drain_unlocks_coride_dropoff`：抽取解含 (4,4)
  merger `{S,W}→{N}`（共乘）与 (4,5) splitter `S→{N,E}`（下车），连通复验
  `failure_count=0`；并断言 `warehouse_drain.cells > 0` 与
  `demix_ban.drain_excusable_rows > 0`，防止它靠别的机制侥幸变绿。
- **污染孪生** `test_drain_closure_rejects_dropoff_whose_lane_ends_at_a_machine`：
  **同一几何只把 a 自己那个口从核心换成制造机** ⇒ INFEASIBLE。一个端口的差别翻转
  判决，这对实例本身就是 §11.3 论证的可执行形式。
- **两个方向的承重哨兵**：中和传播行（变量留着浮空）⇒ 污染几何翻 FEASIBLE 且抽取
  出的正是外审反对的那个 splitter；中和整个闭包 ⇒ 红利几何回到 INFEASIBLE。
- **畸形装置防线** `test_drain_exit_requires_the_body_cell_to_be_off_domain`：机身
  格可路由时不算吸收出口，机身在域外时算——两个方向都钉。
- **无环化** 三读数差分 + 机器口世界零成本（`ranks=0 rows=0`）。

**源码级双变体自证**（`.artifacts/mixflow_u01_20260807/mutation_verify_drain.sh`，
日志同目录），两个变体的签名**互补**——这正是它的价值，它把「闭包是不是红利的
来源」与「传播是不是安全的来源」分开证：

| 变体 | 红利测试 | 污染哨兵（8 条）|
|---|---|---|
| D 删 `build()` 里的调用点 | **红** | 全绿（普通禁令接手）|
| E 保留变量、掏空传播行 | 绿 | **红 1**（B-01 形态被放行）|

还原 sha256 逐字一致。首轮 D 下污染组多红一条，查出来是污染测试里放了机制存在性
断言（`KeyError` 而非语义失败）在污染信号——移掉才干净。教训与 §10.5 首轮变异 C
全绿同源：**哨兵红得不是因为语义，就等于没有哨兵**。

### 11.7 性能六点对照（§10.8 四点表的续表）

同一装置、同一进程六臂（`bench_mixflow_prodscale.py --solve-seconds 120`，原始
JSON `.artifacts/mixflow_u01_20260807/bench_drain_clean.json`）。后两臂拆开，是为了
让**禁环的价钱单独成一个数字**、可被单独拍板。

| 指标 | 术前 | 术后 | +③ | +U-01 分叉 | +汇流区 | +无环化 |
|---|---|---|---|---|---|---|
| use vars | 980,444 | 974,396 | 974,396 | 980,444 | 980,444 | 980,444 |
| constraints | 3,999,723 | 5,897,344 | 7,888,989 | 7,930,605 | 7,944,533 | 7,958,461 |
| 闭包格 | — | — | — | 0 | 2,536 | 2,536 |
| 传播行 / 吸收出口 | — | — | — | — | 13,928 / 128 | 13,928 / 128 |
| rank 变量 / 行 | — | — | — | 0 / 0 | 0 / 0 | 2,536 / 13,928 |
| 可豁免禁令行 | — | — | 0 | 0 | 2,005,037 | 2,005,037 |
| **build** | 19.78s | 20.5s | 23.83s | 23.37s | **24.8s** | **23.74s** |
| solve（120s 帽）| INFEASIBLE @28.0s | TIMEOUT | INFEASIBLE @112.1s | INFEASIBLE @110.8s | **TIMEOUT** | **TIMEOUT** |

**build 全程在 40s 预算内**，且无环化实测**不要钱**（23.74s 比不带它的 24.8s 还
低一点，是同装置空载复跑的抖动量级）——2,536 个整数变量 + 13,928 条条件线性行在
这个规模上是噪声。禁环的价钱因此是「零」，team-lead 那条「便宜就禁掉」的取舍
成立。

**solve 是真代价，如实报告**：③ 曾把最坏 proxy 的不可行证明从 TIMEOUT 修回
INFEASIBLE（§9.6），汇流区把它又推了回去。机制清楚——200 万条禁令行变成可豁免，
可行域重新变大，不可行证明重新变难，正是 §7 记过的那个现象。

三条限定，别把这个数读过头：

- ③ 臂本来就贴着帽跑（112.1s / 120s），差距不是从「宽裕」掉到「超时」；
- 这是**刻意构造的对抗性最坏 proxy**（19 商品抢宽 1 走廊、剥叶失效），不是生产
  候选；真实基地只有 1 台核心 14 个口，本臂却把 128 个 sink 口全声明成仓储口；
- 单实例单跑，无多 seed / 多 worker 重复。

**它把「要不要门控开关」这个问题重新打开了**（§9.8 条件 1 的结论是「③ 抽掉了开关
的两条动机」，§10.6 已预告「若落 `wh_drain` 要重开」）。长帽复测见 §11.8。

### 11.8 长帽复测：128 口上界臂是真炸，不是慢一点（附一个塌掉的假说）

120s 帽下汇流区臂只报 TIMEOUT，那个词本身不区分「差一点」和「差很远」，所以做了
600s 帽的三臂复测（脚本 `.artifacts/mixflow_u01_20260807/bench_drain_longcap.py`，
日志同目录）：

| 臂（600s 帽，同装置同进程）| solve |
|---|---|
| ③ | INFEASIBLE @113.85s |
| +U-01 分叉 | INFEASIBLE @110.95s |
| **+汇流区+无环化** | **TIMEOUT @603s** |

**给到 5.3 倍时间仍无结论**。前两臂与 120s 帽的读数一致（113.85 vs 112.1、
110.95 vs 110.8），说明装置稳定、差别确实来自汇流区。

**我当时对成本机制的假说，以及它后来被证伪**：汇流区把 **2,005,037 条禁令行从
两文字变成三文字**。两文字子句进 CP-SAT 的二元蕴含图、传播极便宜；三文字的不进。
于是我写下：这不只是「可行域大了因而不可行证明变难」（§7 那个现象），而是两百万条
约束集体离开了最快的传播通道。

**这个假说是错的。** §11.9 那一臂把同样的 199 万条禁令行**全部**变成三文字、drain
变量数与传播行数与本臂逐字相同，却在 105.98s 拿到 INFEASIBLE 真证明。元数不是那个
成本轴。留着这段是因为它值得被看见是怎么塌的：一个听起来有机制、有数字、方向也对的
解释，可以完全不成立——把它写进 §11.9 的对照臂里去证伪，是本批做对的一件事。

**静态剪枝：评估后不做**。既然元数不是成本轴，「静态上不可能到达任何仓储出口的格不
建 drain 变量」这个优化就失去了它的动机。而它并非免费：**它只有在无环化开着时才
sound**——无环时 rank 严格下降必须终止于吸收出口，所以每个 drain 格都能到达仓储口；
无环化一关，纯环立刻让这个前提失效（环上的格永远到不了任何出口，却合法为真）。也就
是说它会在两个本来独立的开关之间造出一条单向 soundness 依赖。**为一个已被证伪的收益
换一条耦合，不划算，本批不做**。另外实测它剪得也很少：在连通走廊里被剪掉的基本只有
机器 front 格自己（其余格绕远路仍够得着仓储口）。将来若真需要它，先把这条耦合写死成
断言，别让两个开关能被分别关掉。

### 11.9 真实口数臂：生产口数下汇流区不要钱（本节是决策相关的那个数）

§11.7/§11.8 的汇流区臂把装置里**全部 128 个 sink 口**都声明成仓储系口。那是**代价
上界**，不是布局——真实基地 266 个 mandatory 实例里恰 **1** 台协议核心、**14** 个
输入口（§10.4 已在冻结池上点清）。所以补了一臂真实口数，脚本
`.artifacts/mixflow_u01_20260807/bench_realistic_mix.py`，日志 `bench_realistic.log`。

三臂同装置（256 体 / 19 商品 / 2536 可路由格）、同进程、同 120s 帽：

| 臂 | 禁令行 | 其中可豁免（三文字）| 吸收出口 | drain 变量 | solve |
|---|---|---|---|---|---|
| ③ | 1,991,645 | 0 | 0 | 0 | TIMEOUT @122.21s |
| **+U-01+汇流区+无环化（14 口）** | 1,992,653 | **1,992,653（全部）** | 14 | 2,536 | **INFEASIBLE @105.98s** |
| +U-01+汇流区+无环化（128 口）| 2,005,037 | 2,005,037（全部）| 128 | 2,536 | TIMEOUT @123.13s |

**读法一：性能反对意见在生产口数下基本消失。** 14 口臂拿到的是 INFEASIBLE——一个
**证明**，不是帽子截断，所以它不受帽子噪声影响。总约束数 792.0 万 vs ③ 的 788.9 万
（+0.4%），build 26.18s vs 25.17s（+4%）。

**读法二：§11.8 的成本机制假说被这一臂证伪。** 14 口臂与 128 口臂的 drain 变量
（2,536）、rank 变量（2,536）、传播行（13,928）逐字相同，禁令行也几乎相同且**两臂
都是 100% 三文字**。若成本真来自元数，两臂该一样炸。它们相差一个数量级以上。**真正
的成本轴是放宽有多大——吸收出口 14 个还是 128 个**，即模型真正多出了多少自由度。

**读法三：口数轴上生产落在哪一侧，是本批能不能接线的关键前提。** 14 vs 128 之间的
转折点没有测（本批只有两点），而生产是 14。若将来 canonical 把更多口判成仓储系口
（例如箱口二期放开，§11.5），这条曲线必须重测——不能拿 14 口的读数外推。

**证据等级与诚实边界**：
- 每臂**单次**运行，单个装置，没有重复采样；
- ③ 臂在本次跑里 TIMEOUT @122.21s，但在 600s 长帽里是 INFEASIBLE @113.85s
  （§11.8）——**它正卡在 120s 帽上**，所以「14 口臂比 ③ 快」这句话本表撑不住。
  本表撑得住的是：**14 口臂与 ③ 同量级（106–123s），128 口臂给到 5.3 倍时间仍无
  结论**；
- 这个装置在 ③ 下就是 INFEASIBLE，所以它只能量**代价**、量不出**红利**。红利的
  实证在 §11.6 的小几何上（几何 A 翻 FEASIBLE，机器口孪生仍 INFEASIBLE）。

### 11.10 六条解除条件的增量（汇流区部分，接 §10.6）

汇流区比守卫分叉动得多，对六条外审解除条件的影响也更实，逐条记：

- **条件 1（certified 默认关本手术 / 门控开关）—— 已关闭，不做开关**（team-lead
  2026-08-07 拍板；完整理由见 §10.6 条件 1）。本批一度建议「汇流区单独可关」，
  **该建议被否决且理由比我的更强**：③ 单开 = 比游戏更严 ⇒ 对 nogood / 最优性链是
  假 INFEASIBLE 风险；汇流区单开 = 回 B-01 污染。**「③ + 汇流区」是一个语义单元**，
  单独关任何一个都在已知方向上不忠实。性能动机已被 §11.9 杀死；「万一归纳被打穿」
  的保险走审查 + freeze-ritual 回滚，不走运行时双态（双态 = 测试面与变异哨兵翻倍，
  换一个假想收益）。
- **条件 2（soundness 论证完整性）**：新增一份**归纳**论证（§11.3），性质与前面几节
  不同——前面是「术前解仍可行」式的单调性论述，这条是对闭包结构做归纳。它是本批最
  该被攻的地方，已作最高优先外审题（Q15）。
- **条件 3（哨兵两层自证）**：汇流区的三个机制各自配了承重哨兵（闭包传播、无环化、
  出口判据），源码级移除 + 常驻 monkeypatch 中和两条签名互补（§11.6）。
- **条件 4（M4 单调性）**：汇流区**不是**纯放宽——它加了闭包行与 rank 行。但这些
  行只约束新变量（`wh_drain` / rank），术前解把 `wh_drain` 全取 0 即满足（闭包行退化
  为真，rank 行的 `OnlyEnforceIf` 不触发）。所以「术后 INFEASIBLE ⇒ 术前 INFEASIBLE」
  仍成立，nogood 安全方向不变。请与 §10.2b 一并复核。
- **条件 5（性能预算）**：**这条现在有前提了**。生产口数（14）下代价在测量噪声内
  （§11.9），但代价随吸收出口数增长，转折点未测，且箱口二期会让口数变成解的函数
  （§11.5）。接入前建议补口数扫描臂（Q19）。
- **条件 6（witness adapter 子图样兼容）—— 接入批硬项，处置方向已定死**：§10.6 那条
  欠账在汇流区下**变重**——反建 routing 的消费者拿不到 `operation_type` 时不只是
  「比生产者严」，而是整个汇流区不存在（`_add_warehouse_drain_constraints` 走
  `no_warehouse_system_sink_port` 早退），于是汇流区开出的解在这类复验下**必然**被判
  INFEASIBLE。

  **team-lead 2026-08-07 拍板：fail-loud + 哨兵，绝不允许静默退化成更严模型。** 理由
  写在这里因为它是一条可迁移的判据——**静默严格化是 silent-skip 的孪生病**：它同时藏
  两层账，「这条线没接上」和「接上了会发现的问题」，而且因为方向保守（拒真不纳伪），
  它连一条红都不会产生。保守不等于可以沉默。

  接入批两件事：

  1. **把分类数据从同一份 hash-bound 源头穿到所有反建面**（replay / 独立复验 /
     reverifier），不是各自重新推导；
  2. **加一条端到端哨兵**：一个用到汇流区的解，必须**原样**通过全局连通复验与 replay；
     **缺分类时必须红得响**，而不是安静地变成一个更严的模型然后判 INFEASIBLE。

### 11.11 P2.0 线转来的速率侧边界（**描述性收窄，不是放松模型防御的许可**）

P2.0 特化设计稿（`docs/research/p2_0_specialized_20260807/`，`86a2760`）给本线转来一条净输入。
先说**证据等级**：该稿是研究层设计稿，其自列欠账 #1 是「未过独立 refute 席」，所以下面
的数字按【设计稿自产、机器可复跑、未过对抗席】读。

**⚠ 口径警告（team-lead 2026-08-07 中期反哺）**：owner 对该稿的占空建模开了一枪——
`split_free_probe.py:97` 把每台设备的占空**硬编码成均摊**，而游戏允许每台自由分配
（含闲置），例如「5 台满 + 1 台半」就能让 steel_block 的 17 条产道盖住 17 条耗道、
鸽巢瓦解。`splitfree-refute` 席正在整网联立重判。**中期判决：六例翻案四例**（含
steel_block），**buckwheat 与 sandleaf 两例顶住**并升格为**任意分配下成立的纯计数
证明**（种子回流环奇数劈半）。所以下面凡引**具体数字**处一律按【v1 均摊口径】读，
**终值以 `refute_round1/REJUDGE_REPORT.md` 为准**。

**它说了什么**（该稿 §2.1/§2.4/§7.1，机器复算，`rate_table.py` + 两个 CP-SAT 探针）：

- 逐口车道分解下，574 个制造端口 slot 里 **464 条是满带宽车道**【v1 口径】，两两共道
  合法（速率和 ≤ 1 件/tick）的对**只有 3 对**，且两侧全是终品。**涉及中间品的合法
  共道对 = 0。**
- 但网络级纯流**不成立**：v1 报 6 种中间品在任何最小车道分配下必然分流【**该数字正在
  重判，中期为 2 种**】。被迫切细的细流段上，v1 报 **15 对**不同中间品的共道在速率上
  无法被排除【v1 口径，重判后会变小】。
- 合起来：**混流只可能出现在分流细流段，主干道全部逐口纯流**——而细流段恰恰是分流器
  下游，也正是 de-mix 与污染最危险的地方。**重判对本批的方向是收紧**（细流段变少甚至
  消失 ⇒ 需防的混流场景更少），所以它不会让本批的任何防御变得不足；会变的只是措辞。

**本节引用中唯一承重的那条，重判后不但活着还变强了**：「严格读法（车道条数处处最小）
的前件族**是空的**」原本是 v1 六例支撑的结论；中期判决里 buckwheat 与 sandleaf 两例
升格为**任意分配下成立的纯计数证明**，于是「两货在任意分配下必分流 ⇒ 全网 split-free
族恒空」变成一条**无条件命题**。§11.11 引它是安全的，且不再依赖被翻案的那四例。

**为什么这条**不能**用来放松本批任何防御**（这是本节存在的主要理由）：

1. **certified routing 模型里没有速率**。它不建流量变量、不知道产能目标，admissible
   的布局集合与「哪些商品对在速率上能共道」完全无关。所以上面那条收窄描述的是
   **哪些布局在速率上现实**，不是**模型接受哪些布局**。
2. **canonical 明文禁止这种升格**。`rate_lemma_scope.usage_rule`（main，`fab718a`）：
   任何倚靠该引理的叙事升格「must cite this entry AND **discharge both preconditions**」，
   而前件 (ii) 是最小车道约定，原文「a layout that deliberately spreads one commodity
   over more lanes to dilute per-lane rates **leaves this precondition family and the
   lemma asserts nothing about it**」。**certified 求解器搜的正是全部布局，包括故意摊开
   车道的**，模型不强制最小车道 ⇒ 前件 (ii) 在 certified 语境下不可 discharge。
3. P2.0 §2.2 证明了 fill-first 是最小车道分配下单条车道速率的**下确界**，所以**逐口**
   纯流强制与车道约定无关——这是一条加固，但它加固的是逐口层面；§2.4 同时证明严格读法
   （车道条数处处最小）的**前件族是空的**，引理在其上真空。两者合起来：**逐口层面稳，
   网络层面无。** 收窄止步于描述。
4. **该引理在 certified 模型里是双重不可用的**（team-lead 08-07 汇总）：本批发现前件
   (ii) 在 certified 语境不可 discharge（求解器搜全部布局、模型不强制最小车道），
   `splitfree-refute` 席同时发现 v1 的结论本身**欠一条均摊前件**（占空被硬编码）。
   两条是独立的失效，叠加后**任何想在 certified 模型里引用速率引理的人都要先过这两关**
   ——这条已作常设警告转出本线。

**它对本批的正确用法只有一个**：外审若问「wh_drain 放开的混流形态在真实基地里到底会不会
出现」，答案是**会，但只在细流段**（15 对中间品窗口）。这提高了本批红利的现实相关性，
**不降低**任何证明义务。

**一处顺带的精度修正，直接打到本批红利几何上**（该稿 §2.3）：canonical
`rate_lemma_scope` 写「the only lanes on which commodity mixing remains rate-legal are
the final-product terminal segments」，实测两条终品的**全流**车道之和 = 11/20 + 3/5 =
**23/20 > 1，一格装不下**。可混流的是**未完全汇聚**的子段（产口侧 3 条 11/60 + 3 条
1/5，任取和 ≤ 1 的子集，最多 5 条 = 57/60）。**所以 §11.6 那个「两终品共乘一格进相邻
仓储口」的红利几何，在满产速率下只对未完全汇聚的子段成立，不对汇聚后的终端段成立。**
这不改变红利的正确性（连通性谓词与速率无关），但引用红利时别说成「终品段随便混」。

**转来的第三条属别人的作业面，记在这里只为不丢**：canonical
`item_admission_port_exclusion` 的理由 (a) 建议从「中间道上没有东西可分拣」精确到
「中间品的**最小车道**之间没有东西可分拣」。裁决结论不受影响（另有独立的 (b)(c) 两条
支撑，都不依赖速率算术）。**这是 canonical 面的文档级精度补丁，属 P2.0 实现批的 Q7，
本批不改**——而且本工作树的 `rules/canonical_rules.json` 还是 `fab718a` 之前的版本
（§11.12），本来也没资格改它。

### 11.11b open_yard 装置缺陷已修（team-lead #3 拍板）

§10.7 记的那个不忠实探针装置（③ 批 `open_yard_8x8`，四个端口的设施机身格落在声明为
全自由的院子里）已按 team-lead 2026-08-07 拍板修好：原装置改名保留为
`open_yard_8x8_UNFAITHFUL_body_inside_yard` 并附缺陷说明，`open_yard_8x8` 换成机身落在
院子外的忠实版，原文件与原输出另存 `.orig_20260807`。两版同跑对照与完整记录在
`.artifacts/mixflow_demix_ban_20260807/CORRECTION_open_yard_fixture_20260807.md`。

**③ 批的结论没有被这个缺陷伤到**：承重对照「ban=ON 挡住混流 / ban=OFF 放行」两版同向。
差别只有一处，而且是往好的方向——忠实版在 ban=OFF 且**不强制**时就自发出混流格（缺陷版
要强制才出），所以忠实版是更强的探针。被这个缺陷真正误导过的只有 U-01 一度以为的「守卫
分叉红利」，那条在发现当场撤回、从未进入交付文档。

### 11.12 接入批 checklist（硬前置，逐条带出处）

本批**刻意不 reseal、不接线**。下面是接入批开工前必须逐条清掉的硬前置，写在这里免得
散在各节里被漏掉。

**前置 1（最容易被当成普通 merge 做掉的一条）：本工作树的 canonical 落后于 main，
接入必须当 freeze-ritual 处理。**

| | `rules/canonical_rules.json` |
|---|---|
| **main（唯一真身）** | `b675fb6a1cdae7920f90abf63e59aa76ea8df37ae8a8c5d5d15b10b94218c4ca`，**40,371 字节** |
| 本分支基线 `fb76e15` | `c3666d78d5dd1329514c7813be9f91f09cb3ce7b94907ef5b6ce746c9bcbbbd5`，18,137 字节 |

本分支基线**早于** canonical 公理 kernel 批 `fab718a`（`git merge-base --is-ancestor
fab718a HEAD` 判 **NO**），两版相差 **+67/−10 行**。**那是被字节级 hash 钉死的冻结
工件**，rebase 时以 **main 的 `b675fb6a`** 为唯一真身，本分支上**任何**对 canonical
的引用都要重新对表。§11.5、§11.11 里所有 canonical 引用**都是从 `main` 读的**，不是
从本工作树——写这句是为了让接手人知道那些引用不需要重查，但**代码与测试里若有对
canonical 的隐式依赖，必须重查**。

接入批的 rebase 因此**不是普通合并**，要走完整 freeze-ritual（pin sha 按 LF 字节算、
重跑两个 checker、提交 pathspec 覆盖全集）。落到本批的实际影响：新落地的
`mixed_commodity_flow.terminal_clause` 正是本批实现的口岸三分法的 canonical 版，接入时
要逐条对齐措辞，特别是 class (2) 的 bound 是**槽数**不是种类数（§11.5.1）。

**前置 2：口数-性能扫描臂，触发条件是「箱口被实际实例化」而不是「箱口被放开」。**
team-lead 2026-08-07 拍板把 14/28/56/128 的扫描臂定为箱口二期 / 接入批的硬前置
（§11.9 只有两点，转折点未测）。**触发条件要按 §11.5.3 收紧**：箱当前零实例、下界 0，
放开一个零实例的口**不改变吸收出口数**，性能曲线不动。真正让口数从 14 变大的是箱**被
实例化**（那要么 `production_targets` 上调、要么核心 14 口容量被占满）。所以 checklist
条目应写成「**箱口实例数下界 > 0 之前不需要扫描臂；一旦 > 0，扫描臂是接线前置**」。

**前置 3：门控粒度要显式判。** §11.10 条件 1 已展开；本批建议「汇流区单独可关」。

**前置 4：条件 6 的缝要处置 —— 已定死 fail-loud + 哨兵，不是自由发挥题。** 反建
routing 的消费者拿不到 `operation_type` 时汇流区整个不存在（早退
`no_warehouse_system_sink_port`），汇流区开出的解在这类复验下必然被判 INFEASIBLE。
**必须响亮报错，绝不允许静默退化成更严模型**——静默严格化是 silent-skip 的孪生病，
方向保守所以一条红都不会产生，却同时藏「没接线」与「接了会发现的问题」两层账。
两件事：①分类数据从同一份 hash-bound 源头穿到所有反建面；②端到端哨兵——用到汇流区的
解必须原样通过全局连通复验与 replay，缺分类时红得响。完整措辞见 §11.10 条件 6。

**前置 5：汇流区终品性论证的显式依赖声明（把「谁放开谁踩雷」翻转成「放开也不塌」）。**

> **承重结构 = binding 的 `generic_commodities` 域。no-orphan 全局门只是冗余防线。
> 若将来放开 no-orphan，本论证不受影响。**

展开：「drain 区内只可能是终品」有两条独立的推法。

- **承重的那条（构造性，唯一被本文件依赖的）**：`binding_subproblem.py:1175` 的
  `generic_commodities = sorted(self.required_generic_inputs.keys())` 把仓储系口的商品域
  **构造性地**钉死为 `required_generic_inputs` 的键集，加一个 `__unused__` 哨兵
  （`:1178`），而 `__unused__` 槽不导出 port spec（`:1510`、`:1527`）。当前该键集 =
  `{qiaoyu_capsule: 1, valley_battery: 1}`（`generic_io_requirements.json`，元数据原话
  「sink slots for **final products**」）。**中间品连候选资格都没有**——不需要论证它
  「到不了自己的 sink」，它压根不能被绑到仓储系口上。这条只依赖冻结工件 + 一行代码。
- **冗余的那条（不得作承重）**：中间品即使出现在 drain 区，也因为到不了自己的机器
  sink 而被 `_validate_selected_route_connectivity` 的 no-orphan 判失败。这条**成立
  但不得依赖**：canonical 的 `axiom_kernel.model_stricter_faces` 把「routing
  reverification's extra no-orphan / selected-source-reaches-sink conditions」**登记为
  模型比裁决过的游戏语义更严的面**，而 canonical 谓词 5（`connectivity_quantifier`）
  **不含** no-orphan。`model_stricter_faces` 按定义是待放开清单（同条目里 source-front
  那个面已被 owner 标成 confirmed over-strict、解锁另开批）。

**所以本文件（以及箱口二期、以及任何未来的 drain 扩展）一律锚在第一条上。** 这样写的
理由是它比一条脚注结实：脚注只能警告「别踩」，依赖声明直接让**放开 no-orphan 的那个
批次不需要知道本文件的存在**——它放开了，这里也不塌。
