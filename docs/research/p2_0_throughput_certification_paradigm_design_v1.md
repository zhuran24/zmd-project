# P2.0 吞吐认证范式设计稿 v1

**Status:** HISTORICAL_OR_PLAN（研究层设计稿，不是生产实现，不改变任何锁边界）
**Authored:** 2026-07-04
**Scope authority:** 在本稿全部落地并走完 freeze-ritual 之前，`PROJECT_LOCK.md` §1A B 块（吞吐/带宽/离散容量流 OUT-OF-SCOPE）与 `rules/canonical_rules.json:415-417`（mixed_commodity_flow 的 out-of-scope 声明）**继续有效**。本稿存在 ≠ scope 已改。

---

## 0. 定位与决策背景

- Owner 2026-07-04 拍板：**吞吐认证是项目最终必做的 scope**（"不做的话这项目怎么实现"）——它从"明确 out-of-scope、零排期"转为 **planned P2.0**，但排期仍在 P1.2 close、PR2 深化、P1.3 cut 接入之后。
- 本稿的任务：把"怎么做"的**数学范式**想清楚并固化成可实现规格，使后续实现者（人或模型）可以照稿分期落地，不需要重做范式层的推理。
- 阅读前提：读者熟悉六谓词命题（`README.md:91-106`）与 producer→supervisor→publisher 三权分立（`docs/项目说明/01_overview.md` §1.3）。

## 1. 事实基线（全部经 2026-07-04 只读调查核验）

### 1.1 速率数据已在仓库且已被 hash 钉死——不需要新数据源

| 事实 | 值 | 证据 |
|---|---|---|
| tick 长度 | 2.0 秒 | `rules/canonical_rules.json:12-13`；`specs/02_global_notation_and_units.md:121-128` |
| belt 容量 | 1.0 item/tick（**跨商品聚合**） | `rules/canonical_rules.json:15-17` |
| 端口吞吐上限 | 1.0 item/tick | `rules/canonical_rules.json:15-18` |
| 配方周期 | `recipes.*.ticks_per_cycle`（整数 ≥1，如 packaging_battery=5） | `rules/canonical_rules.json:116-292` |
| 配方速率语义 | `input_rate(k)=inputs[k]/ticks_per_cycle`，output 同理 | `src/interchange/preprocess_context.py:33-44` |
| 生产目标 | `production_targets.*.mode ∈ {equivalent_full_speed_lines, rate_per_tick}`（当前 3.0 / 2.75 条满速线） | `rules/canonical_rules.json:293-304` |
| 需求反推 | `run_rate = demand_rate / output_rate`；输入需求 `+= run_rate*amount/ticks_per_cycle` | `src/preprocess/demand_solver.py:261-315` |
| 端口 slot 化 | `slots = ceil(rate / belt_capacity_per_tick)` | `src/preprocess/operation_profiles.py:65-74` |
| 派生需求速率 | `data/preprocessed/commodity_demands.json`（分数速率，如 buckwheat=5.5、qiaoyu_capsule=0.55） | `commodity_demands.json:2-18` |
| 上游数据佐证 | `third_party_snapshots/endfield_calc/`（craftingTime、amounts、facilities） | `SOURCE_METADATA.json:8-17` |

**推论**：P7 建模所需的全部速率参数已在 frozen artifacts 里；不需要解冻 preprocess additive-only 守卫（`recipes`/`production_targets` 本来就活在 `canonical_rules.json` 顶层，`src/interchange/preprocess_context.py:24-25` 的守卫只管 `preprocess_plan.json`）。

### 1.2 routing 模型的结构（P7 的建模底座）

- Route state = `(x, y, layer, flow_in, flow_out, commodity)`；physical state 去掉 commodity 换 `component_type`（`src/models/routing_subproblem.py:40-41, 1012-1019`）。组件类型：L0 belt（单入单出）、splitter（1 入 2-3 出）、merger（2-3 入 1 出）、L1 bridge（仅直行）（`routing_subproblem.py:915-953`）。
- 每 `(cell, layer)` 至多一个 physical state（`AddAtMostOne`，`routing_subproblem.py:1100-1104`）；**同一 physical 组件可被多商品共享**（use_vars per commodity + `AddMaxEquality`，`routing_subproblem.py:1056-1058`；语义裁定 `canonical_rules.json:415-417`）。共享商品**共用同一组 in/out 侧**（phys key 含 flow_in/flow_out，所以共格必同构）。
- CP-SAT FEASIBLE 后有 selected-graph 连通性复验（source front → sink front 可达 + orphan 检测，`routing_subproblem.py:1706-1802`）。
- 规模：266 实例、routing-visible 商品 17 类、port specs 620 个；selected graph 的 route states 上限 70×70×2 层但实际远小。

### 1.3 认证链的既有模式（P7 复验直接同构套用）

- 子问题 gate 模式：binding INFEASIBLE → proof_summary + whole-layout nogood；routing FEASIBLE → `RUN_STATUS_CERTIFIED`（`src/search/benders_loop.py:5937-6043, 6840-6990`）。
- 终端复验模式：`terminal_fixed_witness_verifier` 对 witness **重解** binding 和 routing 并比对 digest（`terminal_fixed_witness_verifier.py:189-393`）——P7 复验加第三段"重验吞吐证书"即可同构。
- schema 全部 fail-closed（unknown field 拒绝）：`candidate_proof` 12 个必需字段（`candidate_proof_replay.py:56-74`）、fixed-witness verdict stable fields（`terminal_fixed_witness_verifier.py:33-68`）、`final_result` 白名单（`exact_campaign.py:138-153`）——**加谓词 = 全链 schema_version 升版**，见 §6。

### 1.4 现状缺口（为什么不能改造现有 flow 诊断）

- `flow_subproblem.py` 是连续 LP 诊断器，specs 明禁升格（`specs/08_topological_flow_subproblem.md:57-59`）。
- 实测退化：生产调用把所有端口塞进 `port_dict["dummy_commodity"]`（`benders_loop.py:5713-5723`），而 demands 用真实商品名（`commodity_demands.json`）——每个有需求的商品都没有源边，诊断 LP 在当前生产路径上**结构性早退 INFEASIBLE**（`flow_subproblem.py:165-193` 的 `missing_source_edges` 分支）。它连诊断价值都存疑，P7 必须从头建。
- 它建在**全体 free cells**上（松弛）；P7 应建在 **selected route graph** 上（见 §2）——规模小两个量级且语义精确。

## 2. 命题扩展：第七谓词 P7 的形式定义

### 2.1 建模对象

给定一个已通过六谓词的候选终态：ghost rect `R*`、放置 `π*`、binding 选择 `B*`（每 port slot 的 commodity 赋值，`binding_subproblem.py:1360-1426`）、routing 选择 `S*`（selected route states 集合）。定义：

- **G(S\*)** = selected route graph：节点 = selected route states + port terminals，有向边 = guard 复验所用的邻接重建（`routing_subproblem.py:1413-1432`：state 的每个 flow_out 方向指向邻格中 flow_in 含对向的 state）。
- 商品集 K = routing-visible commodities（当前 17 类）；实例集 I = 266 mandatory instances；每实例经 operation_type → recipe 映射得到 `ticks_per_cycle` 与 inputs/outputs amounts。

### 2.2 变量（全有理数）

- `φ[e, k] ∈ Q≥0`：商品 k 在 G(S*) 有向边 e 上的稳态速率（item/tick）。
- `u[i] ∈ Q ∩ [0,1]`：实例 i 的利用率（占空比）。

### 2.3 约束组

| 编号 | 约束 | 语义 |
|---|---|---|
| T1 守恒 | 对每个 k、每个非终端节点 v：`Σ_in φ = Σ_out φ` | splitter/merger/belt/bridge 都只是守恒节点 |
| T2 组件容量 | 对每个 selected physical state s：`Σ_k through(φ, s) ≤ 1.0`（belt_capacity_per_tick，跨商品聚合） | 混商品共享组件时共享同一条 1.0 容量 |
| T3 端口容量 | 对每个 port p：`rate(p) ≤ 1.0`（port_max_throughput_per_tick） | |
| T4 机器耦合 | 对实例 i、商品 k：`Σ_{p∈in_ports(i,k)} rate(p) = u[i] · inputs_i[k]/tpc_i`；output 侧同理 | 消耗/产出与利用率线性耦合 |
| T5 目标满足 | 对每个 production target t：`Σ_{i∈producers(t)} u[i] · output_rate_i(k_t) ≥ target_rate(t)` | `rate_per_tick` 直取；`equivalent_full_speed_lines` 按 `value × recipe.output_rate` 换算（与 `demand_solver.py:261-272` 同语义） |
| T6 边界供给 | boundary_io 的 generic output ports 是外部源，每口 ≤1.0/tick；routing-free 的 generic inputs（wireless sink 终产品）不进 routing 图、只进 T4/T5 机器侧 | `binding_subproblem.py:524-528, 1371-1396` |

**P7(R\*, π\*, B\*, S\*) :≡ ∃ 有理 (φ, u) 满足 T1–T6。**

设计要点：

1. **只约束原始目标（production_targets），不约束派生需求**——`commodity_demands.json` 的 34/tick 等值是规划期反推产物，P7 让中间商品速率由守恒自然涌现。这避免把规划期的一种可行分解误当成必要条件（over-constraint 会造成 false-INFEASIBLE，破坏最优性）。
2. **P7 是对固定 (B\*, S\*) 的判定**。存在性量词在 witness 链上与现有模式一致：producer 给出一组可行 (B\*, S\*, φ, u)，复验器验证这一组。注意这意味着 routing/binding 不可行回退时，"该候选 P7-不可行"的全称结论（∀ B,S 都不行）**不能**只由单个 (B\*,S\*) 失败得出——见 §2.5。

### 2.4 新命题与最优性

**P′ := P（六谓词）∧ P7**；目标不变：`max_lex(area, min_side)`，admissibility（min_side ≥ 6）不变。CERTIFIED′ 的完整命题 = 发布的 `(R*, π*, B*, S*, φ*, u*)` 满足 P′，且 admissible frontier 中不存在 lex 更优的 P′-可行解。

**单调性引理（旧证据的继承规则）**：谓词添加是可行集收紧（P′-可行 ⇒ P-可行）。因此：

- 所有历史「候选 P-不可行」证明（binding/routing 穷尽 nogood、frontier 剪枝）在 P′ 下**保持 sound**（不可行只会更不可行）。
- 所有历史「候选 CERTIFIED（六谓词）」结论在 P′ 下**降级为未决**——P-可行不蕴含 P′-可行。
- 推论：campaign 可增量迁移：不可行侧剪枝全保留；只需对可行侧候选补 P7 判定，若旧最优候选 P7-fail 则从它向下继续搜索。**最优空矩形在 P′ 下可能严格变小**——这不是形式性检查，见 §8。

### 2.5 P7 失败时的回退语义（soundness 关键）

对固定候选 (w,h)，P7 对某组 (B\*,S\*) 失败 ≠ 候选不可行——可能换一组 binding/routing 就可行。正确的循环语义（与现有 routing connectivity guard 的 lazy-cut 模式同构，`routing_subproblem.py:1922-1973`）：

1. P7-INFEASIBLE（Farkas 证书在手）→ 对**这一组选择**落 selected-solution nogood，回到 CP-SAT 求下一组 (B,S)；
2. 穷尽所有 (B,S) 仍无 P7-可行 → 候选整体不可行，且此全称结论要走 whole-layout nogood 的独立复验通道（I1 同构）；
3. 时限/预算耗尽 → `UNKNOWN`，fail-closed，不落 cut。

工程警告：P7 加入后 CP-SAT（离散选择）与 LP（速率）形成真正的 LBBD 内环，收敛性没有免费午餐——Farkas 证书能否泛化成比 selected-solution nogood 更强的 cut（例如把不可行归因到"某组件集合的聚合容量不足"，即 F2 cutset 的速率版）是 P2.0b 的核心算法问题，与 F1/F2 的 LP-dual 欠账（`docs/项目说明/05_open_questions.md:111-149`）共用同一套有理对偶基建。

## 3. 离散语义鸿沟：稳态 LP ≠ 游戏内真实吞吐（本稿最重要的一节）

T1–T6 是**流体（fluid）稳态抽象**。物品是离散的、带是有限缓冲的 FIFO、机器是整周期的。以下逐条列出抽象与真实游戏语义可能脱节的机制，每条标注处置方式（可数学消解 / 必须公理化 / 必须游戏实测）：

| # | 机制 | 鸿沟 | 处置 |
|---|---|---|---|
| G1 | belt 迟延（item 移动 cells/tick 速度） | 只影响瞬态与在途库存（Little 定律 WIP=速率×迟延），**不影响稳态速率集**；canonical 里也没有 belt 速度字段（数据缺口 D1） | 数学消解（fluid 层无需该参数；tick 层需要） |
| G2 | merger 仲裁 | 若 merger 是优先级制（非公平轮询），低优先分支在回压下可被饿死：fluid 判 0.5+0.5 可行，实际一支归零 | **公理 A2（merger 公平性）**；游戏实测可裁定（D2） |
| G3 | splitter 分配 | ① 分配比例是否任意可控（游戏 splitter 多为轮询 ⇒ 1:1，但 blocked-skip 语义下回压会自适应出任意有效比例）；② **type-blind 混流可分性**：多商品共享一个 splitter 时，per-commodity 独立分流在无过滤器的游戏里可能不可实现 | **公理 A3（splitter 比例可实现 + 混流可分）**；②是当前 mixed_commodity_flow 裁定（`canonical_rules.json:415-417`）与吞吐语义的直接冲突点，游戏实测必裁（D3） |
| G4 | 有限缓冲 + 回压死锁 | 商品图**有环**（`preprocess_plan.json` 的 `cycle_groups`：种子循环）。稳态存在 ≠ 从空启动可达；环上缓冲配置不当可死锁 | 无环商品组可给定理消解（无环 + 公平服务 + 充分缓冲 ⇒ 稳态可达）；有环组需 **公理 A4（bootstrap 初始库存/引导可达性）** 或显式 bootstrap witness；游戏侧初始种子语义待实测（D4） |
| G5 | 机器整周期性 | `ticks_per_cycle` 整数周期 vs 连续 u[i] | 数学消解（时间平均论证：占空比调度可实现任意有理 u，输出阻塞时停机=标准 backpressure 语义；需 D5 确认游戏机器确实"输出满则停"而非丢弃） |
| G6 | 启动瞬态 | 有限确定性系统最终进入周期轨道，但需论证周期内平均速率=稳态速率 | fluid 层公理 A5（周期平均可达目标速率）；tick 层可数学消解 |

**结论**：P7-fluid 的 soundness 相对「游戏真实语义」必须携带**显式公理组 A = {A2, A3, A4, A5}**，写进 theorem scope 声明，地位等同现在的"candidate geometry 是 hash-pinned TCB"——命名信任，不是隐藏假设。每条公理有两条消解路径：(a) owner 游戏实测拍板后机器化进 canonical semantics 块（先例：2026-07-02 routing 四项游戏语义拍板）；(b) P2.0c 把 tick 语义形式化后数学消解或替换。

## 4. 范式三选一与推荐

| | A：纯 fluid LP 证书 | B：纯 tick 仿真证书 | C：分层（推荐） |
|---|---|---|---|
| 认证谓词 | P7-fluid + 公理组 A | 周期调度 witness，逐 tick 复验 | **P7-fluid 为认证谓词（公理显式入 scope）**，tick 语义为消解公理的后续研究线 |
| soundness 基础 | 相对公理组 | 相对形式化 tick 语义（语义本身仍需与游戏对齐） | 同 A，但公理有明确消解路线图 |
| 证书大小 | O(边×商品) 有理数 | O(周期长 × 状态) —— 周期受 lcm(ticks_per_cycle)×缓冲耦合影响，可能很大 | 同 A |
| 复验复杂度 | 纯算术代入，多项式 | 逐 tick 模拟，周期长度依赖 | 同 A |
| 双侧证书 | FEASIBLE=有理流；INFEASIBLE=**Farkas ray**（同为纯算术复验） | INFEASIBLE 侧极难（要证所有调度都不行） | 同 A |
| 实现成本 | 中（exact 有理 LP 基建） | 高（语义形式化 + 仿真器 + 对齐验证） | 分期摊开 |

**推荐 C**，理由：

1. **双侧皆可复验**是决定性优势：LP 对偶给了 INFEASIBLE 侧的有理 Farkas 证书，与本项目"不信 solver、信证书"的既有哲学（CP-SAT FEASIBLE 后 connectivity guard 复验）完全同构；范式 B 的不可行侧（"所有调度都不行"）没有已知的紧凑证书。
2. 有理对偶基建与 P1.3 的 F1 Farkas/F2 LP-dual witness 欠账**共用**，一次投资两处收益。
3. 公理组不是权宜——它把"游戏语义的不确定性"从隐藏风险变成显式、可逐条消解的清单，且消解机制（owner 实测拍板 → canonical semantics 机器化）已有成熟先例。

## 5. 证书格式与独立复验器设计

### 5.1 witness 格式（草案，全有理数，strict JSON）

```json
{
  "schema_version": 1,
  "authority": "certified_exact_throughput_fluid_witness_v1",
  "verdict": "FEASIBLE",
  "selected_graph_digest": "<sha256: 对 S* 的 canonical 序列化>",
  "binding_assignment_digest": "<沿用 fixed-witness 同名 digest>",
  "rate_inputs_digest": "<sha256: canonical_rules 中 tick/belt/port/recipes/targets 的规范化投影>",
  "flows": [
    {"edge": ["<state_key_from>", "<state_key_to>"], "commodity": "blue_iron_ore",
     "rate": {"num": 1, "den": 2}}
  ],
  "utilizations": [{"instance_id": "…", "u": {"num": 11, "den": 20}}]
}
```

- **禁 float**：全部 `{num, den}` 有理对；解析走 `src/io/strict_json.py` 家族（已有 exact-decimal 路径）。
- INFEASIBLE 侧：`"verdict": "INFEASIBLE"` + `"farkas": [{constraint_id, coeff: {num, den}}]`，复验器验证对偶不等式组合（`y ≥ 0, yᵀA ≤ 0, yᵀb > 0` 型）。
- digest 三元组把证书钉死到确切的 (S\*, B\*, 速率输入)——防 witness 与 layout 脱钩替换。

### 5.2 复验器（新独立模块，隔离子进程内跑）

1. 从 pose bytes + selected route states **独立重建** G(S\*)（不信 producer 给的边表——重建逻辑与 connectivity guard 的邻接重建同构）；
2. 从 canonical_rules 重算全部速率参数（不信 witness 自带数值）；
3. FEASIBLE：逐约束（T1–T6）有理算术代入验证；INFEASIBLE：验证 Farkas 组合。复杂度 O(|约束|·|商品|)，纯算术，无 solver 依赖。

### 5.3 求解器信任模型

- 生产求解：float LP（GLOP）先解 → 可行侧做**有理化+修复**（取顶点解的有理重构，代入验证，失败则换 exact 有理 LP 如 SoPlex-exact/QSopt_ex 重解）；不可行侧必须从 exact LP 或安全舍入的对偶取 Farkas。
- 原则不变：**solver 是不可信的候选生成器，证书是唯一信任对象**。

## 6. 管线接入与工程影响面（P2.0b 清单，本稿只列不做）

1. 新模块 `src/models/throughput_subproblem.py`（不改造 `flow_subproblem.py`——specs/08 明禁升格且其生产调用已退化，§1.4）。
2. gate 位置：benders_loop 中 routing FEASIBLE 之后、`RUN_STATUS_CERTIFIED` 之前；三态 FEASIBLE/INFEASIBLE/UNKNOWN，UNKNOWN fail-closed 不落 cut；回退循环语义按 §2.5。
3. 终端复验：`terminal_fixed_witness_verifier` 加第三段（binding 重解 → routing 重解 → **throughput witness 重验**）；verdict stable fields 增补 + schema_version 升版。
4. schema 升版全清单（全部 fail-closed 面）：`candidate_proof`（v1→v2）、fixed-witness verdict、capsule request/response、`final_result` 白名单（`exact_campaign.py:138-153`）、delivery manifest、proof_summary 字段。
5. 文档/锁面 freeze-ritual：`PROJECT_LOCK.md` §1A B 块改写（吞吐从 OUT-OF-SCOPE 移入谓词清单 + 公理组声明）、`canonical_rules.json` semantics 块更新 `mixed_commodity_flow` 措辞（frozen artifact，走完整 freeze-ritual + reseal 连锁）、六谓词→七谓词的全部文档同步（README、specs/01/08/09、01_overview 等）。
6. `EXACT_*` env allowlist 增补（新子问题的 worker/时限旋钮）+ close-kernel obligations/allowlist reseal。
7. 与 P1.3 的顺序建议：**P1.3 先行**——cut 基建（尤其有理对偶设施）先落地，P2.0b 复用；若 P2.0b 先做会重复造 LP-dual 轮子。

## 7. 复杂度与规模估计

- G(S\*)：selected states 实际规模 ~10³ 量级（上限 70×70×2=9800 格，高密度布局下 free 走廊远小）；17 商品；LP 变量 ~10⁴、约束同量级 → float LP 亚秒级，exact 有理 LP 慢 1–2 个量级仍在秒级。相对 routing CP-SAT（分钟级）：**每候选新增成本可忽略**。
- 复验：纯算术，毫秒级；隔离子进程开销与现有 capsule 同量级。
- 真正的复杂度风险不在单次 LP，在 §2.5 的 (B,S)×P7 交替循环收敛性——Farkas 泛化 cut 的强度决定内环轮数，列为 P2.0b 头号算法问题。

## 8. 对最优性结论的实质影响（为什么这不是形式性检查）

当前 production targets 反推出的需求速率大量处于**满带**（如 blue_iron 线 1.0/tick = 恰好一条带的全容量，`commodity_demands.json` + slot 化 `ceil(34/1.0)=34` 口）。在 P7 下：

- 满速线的带**不能**与任何其他流量共享组件（T2 聚合容量 1.0 已被占满）——现行"混商品共享"的空间节省手段在满速线上全部失效；
- 布局将被迫接近**逐线不相交**的路由结构，走廊需求大增 → 六谓词下 CERTIFIED 的高密度布局很可能 P7-不可行 → **最优空矩形预期收缩**。
- 这正是 owner"不做吞吐项目无法实现"判断的数学面印证：P7 改变的是答案本身，不是给旧答案盖章。

## 9. 数据/语义缺口清单（公理消解的输入）

| # | 缺口 | 需要谁补 | 不补的后果 |
|---|---|---|---|
| D1 | belt item 移动速度（cells/tick） | 游戏实测或上游数据 | 仅 tick 范式（P2.0c）受阻；fluid 不需要 |
| D2 | merger 仲裁语义（轮询/优先级/回压行为） | 游戏实测 | A2 保持公理（named TCB） |
| D3 | splitter 分配语义 + type-blind 混流可分性 | 游戏实测 | A3 保持公理；若实测否定混流可分 → P7 需加"共享组件商品流向绑定"约束（收紧，不破坏已证不可行侧） |
| D4 | 循环商品组 bootstrap 语义（初始种子/库存） | 游戏实测 + cycle_groups 语义对齐 | A4 保持公理 |
| D5 | 机器输出阻塞语义（输出满：停机 or 丢弃） | 游戏实测 | G5 消解论证缺前提，保守按"停机"公理化 |

先例路径：2026-07-02 四项 routing 游戏语义即由 owner 实测拍板后机器化进 `canonical_rules.json` semantics 块（`canonical_rules.json:402-441`）——公理组走同一条流水线。

## 10. 验收判据与分期

- **P2.0a（现在，纯研究层）**：本稿通过独立对抗审查；玩具实例（2–3 机器 + 1 splitter + 1 merger + 1 环）上手写 witness → 原型 checker 全约束验证通过；构造出至少一个「fluid-可行但离散语义下饿死/死锁」的反例并确认它被公理组 A 显式覆盖（而非被遗漏）。
- **P2.0b（P1.3 后）**：生产子问题 + 复验器 + §6 全清单落地；红测覆盖双侧证书伪造（篡改 rate、脱钩 digest、伪 Farkas）全被拒。
- **P2.0c（研究线）**：tick 语义形式化；公理 A2–A5 逐条消解或降格为已实测的 canonical semantics 条目。
- 本稿开放问题：①Farkas→泛化 cut 的形式（§2.5）；②混流可分性若被 D3 否定后的 P7 收紧形式；③循环组 bootstrap witness 的最小格式；④P7 与 frontier 增量迁移的 campaign 状态机改造。

---

*v1 完。本稿的对抗审查与独立对照设计（GPT Pro 双盲）另行打包，不进本文件。*
