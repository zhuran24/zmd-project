# 混流表达手术设计（mixflow-surgery，2026-08-06；de-mix 禁令 2026-08-07）

> 状态：设计稿 v2。v1（2026-08-06）的手术本体经外审判 **BLOCK**（finding B-01：
> de-mix 解在内容盲物理件下纳伪，且存在无准入口槽位的 4 格反例）。owner
> 2026-08-07 拍板取三修复方案中的 **③保守禁止 de-mix**，本文 §9 是该批的落地
> 记录，并订正 §5 与 §6 中已被外审推翻或已过时的条款。**§9 与本文其余部分冲突
> 时以 §9 为准。**
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
