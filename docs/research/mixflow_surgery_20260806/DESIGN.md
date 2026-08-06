# 混流表达手术设计（mixflow-surgery，2026-08-06）

> 状态：设计稿 v1（骨架已对齐主线程 / 实现进行中）。本线是残余 #7「模型混流表达」的
> 施工线；上游依据 = `.artifacts/axiom_analysis_20260806/` 的侦察文书（SOURCE_FRONT_
> UNLOCK_RECON）与 owner 终审公理系（AXIOM_KERNEL_PROPOSAL）。
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

## 7. 构建成本账（生产 build 40s 预算）

设计期估计见 §2.1/§2.2；落地后在此回填实测（同一 fixture 手术前后 build 时间、
use/phys 变量数、约束数、solve 时间）。

| 指标 | 手术前 | 手术后 | 备注 |
|---|---|---|---|
| use vars |（待测）|（待测）| 预期同阶 |
| phys vars |（待测）|（待测）| 预期略增（跨商品拼合态） |
| build 时间 |（待测）|（待测）| 预算：常数因子扰动 |
| solve 时间（差分场景）|（待测）|（待测）| |

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

## 8. 雷区处置记录

- `patch_routing_core.py:583-585`（F-SND-001 双重 front 偏移）：本手术不触碰
  PCR 面（改动仅 routing_subproblem.py），按任务书「不碰就不修」，留 promotion
  前置清单。
- `analyze_exact_routing_domain`：实读结论零改动（§2.1），D2/PCR 抑制义务不被
  本手术牵动。
- `_validate_selected_route_connectivity`：零改动（§2.1）；侦察文书的「需重写」
  预警对应的是候选 B 世界线。
- reseal/pin 链：本分支不动，接入时主线程统一 freeze-ritual。
