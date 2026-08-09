# P2.0 吞吐认证范式设计稿 v1 对抗性审查报告

审查范围仅限：`p2_0_throughput_with_design_v1.zip` 与 `p2_0_prompt_2_adversarial_review.md`。我把 `docs/research/p2_0_throughput_certification_paradigm_design_v1.md` 当作被审规格，以 zip 内源码与 frozen JSON 为准。

总体判定：**修复 BLOCK 后可继续作为 P2.0b 实现规格的底稿；按 v1 原文直接实现不可用**。最主要的问题不是“LP 思路错”，而是规格层有几处端口、证书、历史 frontier 语义的齿轮没咬上。若照稿实现，会出现 false-CERTIFIED、false-INFEASIBLE 或错误继承旧最优性证据。

---

## BLOCK-1：T6 把外部源口写成 boundary_io，漏掉 protocol_core，且 §2.1 把 utility 实例误说成都有 recipe

### 根因

设计稿 §2.1 写“实例集 I = 266 mandatory instances；每实例经 operation_type → recipe 映射”，§2.3 T6 写“boundary_io 的 generic output ports 是外部源”。这与源码事实不一致。

zip 内真实语义是：

- `rules/preprocess_plan.json` 中 `boundary_io.generic_output_slots = 1`，`protocol_core.generic_output_slots = 6`。
- `src/models/binding_subproblem.py:1047-1059` 在构造 generic output domain 时允许 `operation_type in {"boundary_io", "protocol_core"}`。
- `data/preprocessed/generic_io_requirements.json` 要求外部源 slots 总数为 `blue_iron_ore=34`、`source_ore=18`，合计 52。
- `data/preprocessed/mandatory_exact_instances.json` 中当前有 46 个 `boundary_io` 和 1 个 `protocol_core`。也就是说可用 generic output slots = `46×1 + 1×6 = 52`。若只承认 boundary_io，外部源容量只有 46 个 slot，当前实例族会被 P7 错判不可行。

这不是实现细节，而是范式层的源口集合定义错误。它会把所有需要 52 个外部源 slots 的真实候选误剪掉。

### 最小反例

当前 frozen 数据本身就是反例：

```text
required_generic_outputs = 34 + 18 = 52
boundary_io slots only = 46
boundary_io + protocol_core slots = 52
```

按 v1 的 T6 字面实现，当前问题没有足够外部源口，P7-INFEASIBLE；按源码 binding 语义，它正好有 52 个源口。

### 影响面

**false-INFEASIBLE**，会误剪真实可行布局，破坏 lex 最优性。并且 §2.1 对 utility 实例的 recipe 假设会让实现者给 `boundary_io`、`protocol_core` 之类没有 recipe 的实例构造无意义的 `u[i]` 与 T4 行。

### 修复补丁

替换 §2.1 的“实例集 I...”段落为：

```markdown
- 令 `M*` = 已放置且 `operation_type ∈ canonical_rules.recipes` 的 recipe-backed 机器实例集合。只有 `M*` 有 recipe、`ticks_per_cycle`、输入/输出速率和利用率变量 `u[i]`。
- 令 `U_src(B*)` = binding 选择出的 generic output source slots。它们来自 `preprocess_plan.utility_operations.*.generic_output_slots > 0` 且被 `PortBindingModel` 纳入 generic output domain 的 utility 实例；当前包括 `boundary_io` 与 `protocol_core`，不是只有 boundary_io。
- 令 `U_sink(B*)` = binding 选择出的 routing-free generic input sink slots。当前对应 `wireless_sink` 的 virtual generic input slots；它们不进入 routing graph，但仍有 per-slot capacity。
- 令 `P_recipe(B*)` = recipe-backed 机器的已绑定 input/output ports，包括因 routing-free sink commodity 而不进入 `port_specs` 的终品输出 ports。
- 商品集分为 `K_route` 与 `K_rf_sink`：`K_route` 是进入 routing graph 的商品；`K_rf_sink` 是 `canonical_rules.commodity_metadata[*].sink_kind == "generic_input"` 的 routing-free 终品。
```

替换 T4 与 T6 表格行的文字为：

```markdown
| T4 机器耦合 | 对每个 `i ∈ M*` 和 recipe 商品 k：`Σ_{p∈input_ports(i,k)} r[p] = u[i]·inputs_i[k]/tpc_i`；`Σ_{p∈output_ports(i,k)} r[p] = u[i]·outputs_i[k]/tpc_i`；`0≤u[i]≤1` | 只有 recipe-backed 机器有 `u[i]`。utility 实例不进 T4。 |
| T6 generic I/O | 对 `p∈U_src(B*)`：若其绑定商品 k 的 `source_kind == external_boundary`，则 `0≤r[p]≤port_max`，并作为 route-visible source terminal 或 routing-free source terminal；当前 source slots 可来自 `boundary_io` 与 `protocol_core`。对 `p∈U_sink(B*)`：若其绑定商品 k 的 `sink_kind == generic_input`，则 `0≤r[p]≤port_max`，且不进入 route graph。 | generic I/O 口集合以 binding/domain 源码语义为准，不以 facility 名硬编码。 |
```

---

## BLOCK-2：`rate(p)` 未定义且未与 route graph 流量相连，P7 允许“机器吞吐”和“路由流”脱钩

### 根因

§2.2 只定义了 `φ[e,k]` 与 `u[i]`，但 §2.3 的 T3、T4、T6 使用 `rate(p)`。设计稿没有定义 `rate(p)` 是变量、表达式，还是端口边上的 `φ`。同时 §2.1 说 G(S*) 的边来自 routing connectivity guard 的邻接重建；源码的 `_route_state_adjacency` 只把 route state 接到邻格 route state，source/sink front 在 guard 中是 reachability 起点/终点，并不是 LP 中的有向流边。

结果是：T4 可以给机器输入/输出声明速率，T1/T2 可以在 route graph 上另行有一套零流或无关流。规格没有约束二者相等。

### 最小反例

构造一个一输入一输出机器，目标要求该机器 `u=1`，但源口与机器输入没有路由连接。按 v1 文字：

```text
φ[e,k] = 0  对所有 route edge
u[m] = 1
rate(input_port) = recipe_input_rate
rate(output_port) = recipe_output_rate
```

T1 守恒成立，T2 容量成立，T3 端口容量只要 rate≤1 成立，T4/T5 成立。真实游戏中物品没有从源口到机器，候选应不可行。

### 影响面

**false-CERTIFIED**，直接是 soundness 缺陷。它比“离散语义鸿沟”更底层：即使接受 fluid 抽象和所有 A 公理，端口流量也仍然没有被绑定到选中的 route graph。

### 修复补丁

替换 §2.2 变量定义为：

```markdown
### 2.2 变量（全有理数）

- `φ[e,k] ∈ Q≥0`：商品 k 在扩展图 `G⁺(B*,S*)` 的有向边 e 上的稳态速率。`G⁺` 不仅包含 selected route state adjacency，还包含端口 terminal arcs。
- `r[p] ∈ Q≥0`：绑定端口或 generic slot p 的端口吞吐。`r[p]` 不是独立可信输入；对 route-visible ports，它必须等于唯一 incident terminal arc 上对应 commodity 的 `φ`；对 routing-free generic sink commodity，它参与 routing-free balance 约束。
- `u[i] ∈ Q ∩ [0,1]`：`i∈M*` 的 recipe-backed 机器利用率。

`G⁺(B*,S*)` 的端口边按 port type 定向：

- route-visible source/output port：`terminal(p) → first_route_state`；
- route-visible input/sink port：`last_route_state → terminal(p)`；
- routing-free generic sink commodity：不建 route edge，但保留 producer output port 与 virtual generic sink slot 的 `r[p]`，并按商品做总量平衡。

同一 front cell/direction 上若有多个 physical ports，必须保留多个 terminal 节点和多条 terminal arcs；connectivity guard 中的 front set 去重不能用于吞吐容量建模。
```

替换 §2.3 中 T1、T3、T4、T5、T6 的相关定义为：

```markdown
| T1 守恒 | 对每个 `k∈K_route`、每个非终端 route node v：`Σ_in φ = Σ_out φ`。对端口 terminal 不写守恒，而用 T3/T4/T6 定义其注入/吸收。 | route graph 与端口通过 terminal arcs 连接。 |
| T3 端口容量与端口绑定 | 对每个绑定端口或 generic slot p：`0≤r[p]≤port_max_throughput_per_tick`；若 p route-visible，则 `r[p]` 等于其 incident terminal arc 的 `φ`。未知端口、重复端口、无 incident selected route state 的正吞吐一律拒绝。 | `rate(p)` 改名为 `r[p]`，并成为可复验表达式。 |
| T4 机器耦合 | 对每个 `i∈M*`、商品 k：`Σ_{p∈in_ports(i,k)} r[p] = u[i]·inputs_i[k]/tpc_i`；output 侧同理。 | 机器速率必须通过实际绑定端口实现。 |
| T5 目标满足 | 对每个 production target t：`Σ_{p∈target_output_ports(k_t)} r[p] ≥ target_rate(t)`；等价地可写成 `Σ_i u[i]·output_rate_i(k_t)`，但 verifier 必须同时检查端口侧 T4。 | 目标由实际机器输出端口承载。 |
| T6 routing-free sink balance | 对 `k∈K_rf_sink`：`Σ_{recipe output ports for k} r[p] = Σ_{generic sink slots for k} r[p]`，且右侧每个 virtual generic input slot 满足 T3。该商品不进入 route graph。 | 防止终品无线 sink 被当作无限容量黑洞。 |
```

---

## BLOCK-3：§2.4 的“历史 frontier 剪枝全保留”量词不成立

### 根因

“谓词添加使可行集收紧”只能推出：若某个证据证明 `¬P(x)`，则它也证明 `¬P′(x)`。但旧 campaign 中的 frontier pruning / dominance skip 往往不是 `¬P(x)` 证明，而是“已有一个 lex 更优的 P-可行 incumbent，因此无需探索这个更差候选”的最优性侧证据。

P7 加入后，旧 incumbent 可能降级为未决或失败。此时被旧 incumbent 支配而跳过的较小候选，可能正是新的 P′ 最优解。把这些 skip 当成旧不可行剪枝继承，会直接丢掉 P′ 最优候选。

### 最小反例

```text
旧 P 下：area=100 的候选 A 被 CERTIFIED，因此 area=90 的候选 B 被 frontier dominance 跳过。
新 P′ 下：A 由于吞吐失败；B 满足 P7。
```

若继承“B 已被 frontier 剪枝”，系统会错误地认为没有必要检查 B，导致最优性证据失真。

### 影响面

**最优性缺陷**。这不会伪造单个候选的 P7-FEASIBLE，但会伪造“没有更优/候选空间已穷尽”的发布结论。

### 修复补丁

替换 §2.4 “单调性引理（旧证据的继承规则）”为：

```markdown
**单调性引理（旧证据的继承规则）**：谓词添加是可行集收紧（P′-可行 ⇒ P-可行）。因此只允许继承结论形式为 `¬P(x)` 的旧证据，包括：对同一候选 x 的 binding/routing/power 等结构性不可行证明、已复验的 whole-layout nogood、以及与旧可行 incumbent 无关的 exact-safe cut。

不得自动继承以下证据：

- 旧 CERTIFIED incumbent；
- 依赖旧 incumbent 的 frontier dominance skip、search stop、terminal frontier evidence；
- 只说明“无需探索，因为已有更优 P-可行解”的记录；
- 任何 proof_summary 中没有明确 `conclusion = candidate_structurally_infeasible` 的剪枝。

迁移规则：旧 P-CERTIFIED 全部降级为 `P7_PENDING`；所有由旧 incumbent 支配而未结构性证明不可行的候选恢复为 `UNRESOLVED_UNDER_P7`。新的 P′ 最优性必须在这些候选上重新建立 frontier evidence。若旧 campaign 没有保存足够粒度来区分 structural infeasible 与 dominance skip，则保守做法是只继承可独立复验的 exact-safe cut，其余 frontier 状态全部失效。
```

---

## BLOCK-4：§5 的 witness 不是自包含证书，digest 三元组不足以绑定 layout、port specs、generic I/O 与 selected graph

### 根因

§5.1 witness JSON 只有：`selected_graph_digest`、`binding_assignment_digest`、`rate_inputs_digest`、`flows`、`utilizations`。它缺少至少四类绑定：

1. **候选/layout 绑定**：现有 terminal verifier 已有 `candidate_key`、`solution_digest`、`ghost_rect_digest`、`ghost_cells_digest`、`port_specs_digest`、`routing_occupancy_digest`。P7 witness 若不携带并复验这些 digest，就可能被移植到另一个 layout 或另一次 replay 的不同 terminal surface。
2. **selected graph 实体**：witness 给了 `selected_graph_digest`，但没有给完整 `selected_route_states`，也没有引用一个独立发布的 routing witness。仅从 `flows` 推回 graph 会丢失零流 selected states、端口 terminal、多重 front terminal 等信息。
3. **输入数据绑定**：`rate_inputs_digest` 只覆盖 canonical_rules 中 tick/belt/port/recipes/targets，不覆盖 `preprocess_plan.utility_operations`、`data/preprocessed/generic_io_requirements.json`、`mandatory_exact_instances` 的 instance→operation map、以及 `commodity_metadata` 的 source/sink role。P7 实际用到了这些。
4. **closed-world 流量语义**：`flows` 是数组。若不规定 omitted edge = zero、重复 edge 如何处理、unknown edge 如何拒绝，恶意 producer 可以靠重复项、未知边或稀疏解释差异制造 verifier 分歧。

### 最小反例

两个候选 layout 恰好有相同的 selected route state 坐标片段，但端口绑定或 generic source slots 不同。v1 witness 没有 `port_specs_digest` 与完整 selected graph，只要 verifier 依据 producer 提供的 digest 或依据 `flows` 局部重建图，就可能把 A 的 throughput witness 套到 B 的 terminal record 上。

另一类反例：将 `generic_io_requirements.json` 中的 source slots 改成更宽松的版本生成 witness，但 `rate_inputs_digest` 不覆盖该文件。若 verifier 只比对 v1 的 rate digest，就无法发现 witness 使用了错误 I/O 容量输入。

### 影响面

**false-CERTIFIED 或 false-INFEASIBLE**。证书绑定不牢会破坏 producer/supervisor/publisher 的隔离假设。

### 修复补丁

替换 §5.1 witness 草案为：

~~~markdown
### 5.1 witness 格式（草案，全有理数，strict JSON）

FEASIBLE witness 必须是自包含、closed-world、layout-bound：

```json
{
  "schema_version": 2,
  "authority": "certified_exact_throughput_fluid_witness_v2",
  "verdict": "FEASIBLE",
  "candidate_key": "<w>x<h>",
  "solution_digest": "<same stable digest as terminal fixed witness>",
  "ghost_rect_digest": "<same stable digest as terminal fixed witness>",
  "ghost_cells_digest": "<same stable digest as terminal fixed witness>",
  "binding_assignment_digest": "<recomputed from B*>",
  "port_specs_digest": "<recomputed route-visible port specs>",
  "routing_occupancy_digest": "<recomputed occupied_owner_by_cell>",
  "selected_route_states": ["<canonical route-state key>", "..."],
  "selected_graph_digest": "<sha256 over selected_route_states + terminal arcs + graph grammar version>",
  "throughput_inputs_digest": "<sha256 over canonical_rules projection + commodity_metadata roles + preprocess_plan utility_operations + generic_io_requirements + mandatory instance operation map>",
  "flows": [
    {"edge": ["<node_from>", "<node_to>"], "commodity": "blue_iron_ore", "rate": {"num": 1, "den": 2}}
  ],
  "port_rates": [
    {"port_id": "<canonical bound port or generic slot id>", "rate": {"num": 1, "den": 1}}
  ],
  "utilizations": [
    {"instance_id": "packaging_battery_001", "u": {"num": 11, "den": 20}}
  ]
}
```

Verifier 规则：

- `selected_route_states` 是闭世界列表；verifier 从该列表、B* 和 port terminal rules 独立重建 `G⁺`，再重算 `selected_graph_digest`。不信 witness 给的 edge table。
- `flows` 中 omitted `(edge,commodity)` 解释为 0；重复项、unknown edge、unknown commodity、den≤0、非最简或符号异常一律拒绝。
- `port_rates` 必须覆盖所有正吞吐端口；omitted port rate = 0；route-visible port rate 必须等于 terminal arc flow。
- 所有 layout/routing/binding/input digests 都必须与同一 terminal fixed witness verdict 的 stable fields 一致。
~~~

同时替换 §5.2 第 1、2 步为：

```markdown
1. 从 terminal fixed witness 的 pose bytes、B*、port specs、routing occupancy 与 witness 中的 closed-world `selected_route_states` 独立重建 `G⁺(B*,S*)`。若 selected states 不等于 routing verifier 接受的 S* 或 digest 不匹配，拒绝。
2. 从 locked artifacts 重算 throughput inputs：canonical_rules 的 rate/recipe/target/commodity role 投影、preprocess_plan 的 utility slot 定义、generic_io_requirements 的 slot requirement、mandatory instance operation map。任一 digest 不匹配，拒绝。
```

---

## BLOCK-5：INFEASIBLE 侧 Farkas 证书规范过于含糊，足以让错误实现接受伪不可行证书

### 根因

§5.1 写 INFEASIBLE 证书验证 `y ≥ 0, yᵀA ≤ 0, yᵀb > 0 型`。这个描述没有固定 LP 标准形，也没有处理：

- T1/T4/T6 中的等式；
- T5 的 `≥`；
- 变量下界 `φ≥0, r≥0`；
- 变量上界 `u≤1`、端口容量、组件容量；
- 不同约束方向的 multiplier 符号；
- 证书中 constraint_id 到具体约束行的 canonical 顺序。

如果实现者按这句“型”去写 verifier，很容易忽略变量 bounds 或把等式 multiplier 当非负 multiplier，导致伪 Farkas ray 通过。错误的 INFEASIBLE 证书再进入 selected-solution nogood 或 whole-layout nogood，会把可行候选剪掉。

### 最小反例

系统 `u ≥ 1` 与 `u ≤ 0` 的不可行性必须依赖上下界/方向的正确规范化。若 verifier 没有把 `u≤0` 或 `u≤1` 这类 bound 纳入 A，或把 `u≥1` 的符号弄反，就可能接受一个数学上不成立的“不可行组合”。P7 的真实约束中大量存在同类 bound 与方向混合。

### 影响面

**false-INFEASIBLE**，轻则错误落 selected-solution nogood，重则错误发布 whole-layout 不可行证明，破坏最优性。

### 修复补丁

替换 §5.1 INFEASIBLE 侧段落为：

```markdown
INFEASIBLE 侧必须先把 P7-fluid 对固定 `(B*,S*)` 的所有约束规范化为同一个 closed-world inequality system：

`A x ≤ b`

其中：

- 每个等式 `aᵀx = β` 展开为 `aᵀx ≤ β` 与 `-aᵀx ≤ -β`；
- 每个 `aᵀx ≥ β` 展开为 `-aᵀx ≤ -β`；
- 每个变量下界 `x_j ≥ 0` 展开为 `-x_j ≤ 0`；
- 每个变量上界，例如 `u[i]≤1`、`r[p]≤port_max`、component capacity，均作为普通行进入 A；
- 每一行都有 canonical `constraint_id`，由 verifier 重建，不信 producer 自报。

Farkas certificate 为 `{constraint_id: λ_i}` 的非负有理 multiplier，verifier 用 exact rational arithmetic 检查：

`λ_i ≥ 0`，`Σ_i λ_i A_i = 0`，且 `Σ_i λ_i b_i < 0`。

只有这三个条件同时成立，才接受 INFEASIBLE。所有未知 constraint_id、重复 constraint_id、缺失 normal-form metadata、den≤0、非 finite rational 一律 fail-closed。
```

替换 §5.2 第 3 步中 INFEASIBLE 句子为：

```markdown
INFEASIBLE：verifier 先独立生成 normal form `A x ≤ b`，再按上述 Farkas 规则检查 exact-rational λ；不得接受 solver 原始 basis、float dual、未规范化不等式组合或只含自然语言 bottleneck 的证明。
```

---

## CONCERN-1：A2-A5 没覆盖若干会影响 fluid soundness 的离散机制

### 根因

§3 已经列出 merger、公平 splitter、环/bootstrap、整周期、启动瞬态，但仍漏了几类会让 fluid 可行、真实游戏不可行的机制：

1. **端口/connector handoff 语义**：port 到 front cell 是否每 tick 最多交接 1 件、是否有方向锁、是否会因下游回压阻塞、是否存在端口内缓冲。P7 用 `port_max_throughput_per_tick`，但 TCB 未声明端口交接模型。
2. **cross-junction 双通道独立性**：`canonical_rules.json` 说 L1/L0 是单格 cross-junction 建模，两个垂直通道可共格；若真实组件两个通道共享内部处理节拍，P7 按每 physical state 各 1.0 会高估容量。
3. **转弯、交叉、splitter/merger 的速率损失**：canonical 只有全局 `belt_capacity_per_tick=1.0`，没有 per-component rate table。若游戏里弯带或交接有吞吐折损，T2 不 sound。
4. **多输入机器的同步与输入 buffer**：T4 只匹配平均输入速率。多种输入需要同周期消费时，若机器输入 buffer 太小或不支持异步累积，平均可行不等于 tick-level 可调度。
5. **混流的全局可分性**：A3 局部说 splitter 比例可实现和 type-blind 混流可分，但真正需要的是“经过任意 merge/split 网络后，按 commodity 标签指定的分流矩阵可由无过滤器的 FIFO 组件实现”。这是全局调度公理，不只是单个 splitter 的局部公理。

### 最小反例

- cross-junction：同一格 L0 东西向 1.0/tick，L1 南北向 1.0/tick。P7 若按两个 physical states 各自限容，会认为总计 2.0/tick 可过该格。若真实 cross-junction 内部只有一个 service token/tick，则实际最多 1.0/tick。
- 多输入同步：机器配方每周期消耗 A 与 B。fluid 给 A、B 各 0.5/tick，但 A、B 到达相位长期错开；若机器没有足够输入 buffer 或不允许异步缓存，平均速率不能实现。

### 影响面

主要是**相对真实游戏语义的 soundness 风险**。如果这些机制被纳入命名 TCB，fluid theorem 可以保持“相对公理 sound”；如果隐藏不写，后续实现者会误以为 A2-A5 已经覆盖了全部离散鸿沟。

### 修复补丁

替换 §3 结论段为：

```markdown
**结论**：P7-fluid 的 soundness 相对「游戏真实语义」必须携带显式公理组 `A = {A2, A3, A4, A5, A6, A7, A8, A9}`，写进 theorem scope 声明。

新增公理：

- **A6（端口 handoff 与 buffer 公理）**：每个绑定 port / generic slot 的交接吞吐由 `port_max_throughput_per_tick` 严格刻画；端口不会丢弃物品；下游满时按 backpressure 停止；端口内部 buffer 或调度足以实现 verifier 接受的有理平均 `r[p]`。
- **A7（组件速率同质性公理）**：straight belt、turn belt、splitter、merger、bridge/cross-junction channel 的每通道稳态容量均由 `belt_capacity_per_tick` 刻画；不存在未建模的转弯、交叉、层/通道交接速率损失。若 cross-junction 两通道共格，则两通道是否独立必须由 canonical semantics 明确；未实测前作为 TCB。
- **A8（机器多输入同步与内部缓存公理）**：recipe-backed 机器可以按有理利用率 `u[i]` 实现时间平均输入/输出；多输入可异步缓存并在周期边界同步消费；输出阻塞导致停机而非丢弃。
- **A9（全局混流可分性公理）**：无过滤器的 mixed-commodity routing 网络可以实现 witness 指定的 commodity-wise flow decomposition，包括 merge 后再 split 的标签可分行为；若游戏实测否定该点，P7 必须禁止需要按标签分离的共享子图，或加入 explicit filtering/ordering witness。
```

并在 §9 数据/语义缺口清单追加：

```markdown
| D6 | port handoff、端口 buffer、输出阻塞/丢弃细节 | 游戏实测 | A6/A8 保持 TCB |
| D7 | cross-junction 两通道是否独立、转弯/交叉/组件交接是否有速率折损 | 游戏实测 | A7 保持 TCB；若有折损，T2 需改为 component-type capacity table |
| D8 | merge/split 混流后是否可按 commodity 标签全局分离 | 游戏实测或 tick-level constructive scheduler | A9 保持 TCB；若否定，P7 需收紧 mixed-flow 共享规则 |
```

---

## CONCERN-2：§8 “满速线不能与任何其他流共享组件”推理过强

### 根因

§8 把“34/tick 总需求 + `ceil(rate/1.0)=34` source slots”解释成“满速线的带不能与任何其他流量共享组件”。这里有两个层次需要分开：

- 当前 generic source slot 数确实是 exact requirement：binding 对 generic output commodity 使用 `sum(vars_for_commodity) == required`，当前 52 个 source slots 全部被 `34+18` 占满。若蓝铁矿总需求确为 34/tick，则每个蓝铁矿 source slot 平均必须 1.0/tick。
- 但“每个 source port 满”不推出“该 commodity 在内部每个组件上都满”。一个满载 source port 可以在 splitter 后分成两个 0.5 分支；每个 0.5 分支仍可与另一条 0.5 流共享组件并满足 T2。

因此严格数学结论应是：**某个具体组件 s 若在 witness 中已有 `Σ_k through(s,k)=1.0`，则它没有剩余容量，不能再共享额外正流。** 不能从 commodity 的总 port slot 数直接推出整条“线”逐组件不相交。

### 最小反例

```text
一个 source port 输出 A=1.0/tick。
第一个 splitter 后变成两条分支，各 A=0.5/tick。
其中一条分支与商品 B=0.5/tick 共享某组件。
该组件总流 = 1.0/tick，T2 成立。
```

此时 source port 是满的，但内部共享组件仍合法。

### 影响面

若 §8 只是直觉说明，影响较小；若后续实现把“满速线逐线不相交”当成 hard cut 或路由先验，会产生**false-INFEASIBLE**。

### 修复补丁

替换 §8 的三条 bullet 为：

```markdown
在 P7 下，真正严格的容量结论是局部的：对任意 selected physical state `s`，若 witness 中 `Σ_k through(s,k)=belt_capacity_per_tick`，则 `s` 没有剩余容量，不能再承载额外正流。这个结论适用于已被证明饱和的具体组件，而不是自动适用于某个 commodity 的整条“线”。

当前数据中，generic source slots 的需求数与可用数相等：`blue_iron_ore=34`、`source_ore=18`，合计 52，正好等于 46 个 boundary_io slots + 1 个 protocol_core 的 6 个 generic output slots。因此在当前 deterministic recipe decomposition 下，外部源 ports 很可能被打满；但端口饱和不推出内部 route components 全部饱和，因为 flow 可以分流、并流、再汇流。

所以 P7 对最优性的实质影响应表述为：吞吐约束会使许多局部 cut、走廊和 port-front 成为容量瓶颈，显著降低混商品共享带来的空间节省；但只有 verifier 或 Farkas cut 证明某个组件集合容量饱和/不足时，才能把“不共享”升格为 sound cut。不得把“满速 commodity 总需求”直接改写成“逐线不相交”硬约束。
```

---

## CONCERN-3：§2.5 的 selected-solution nogood 完备但可能不可收敛到实用结果，需要证明进展量和 whole-layout 复验证据

### 根因

§2.5 的语义方向是对的：单个 `(B*,S*)` P7-INFEASIBLE 只能 cut 这一组选项，不能推出候选整体不可行。但 v1 没有写清楚两个工程上会影响 completeness 的条件：

1. selected-solution nogood 必须覆盖完整的 B 和 S 决策，包括 recipe port binding、generic input/output slot assignment、以及每个 selected route use-var。否则 solver 可能原样返回同一个吞吐图。
2. whole-layout nogood 不能只说“很多 selected nogood 后 CP-SAT infeasible”。它需要一个可 replay 的穷尽 transcript：初始 CP-SAT model digest、每个 lazy cut/nogood digest、每个 P7-INFEASIBLE 证书 digest、最终 CP-SAT infeasible proof 或 deterministic replay 配置。

### 最小反例

如果 P7 nogood 只包含 route states，不包含 generic output assignment，那么 solver 可以返回同一条 route、同一吞吐不可行核心，但把两个等价 source slots 的 commodity assignment 交换一下。对于吞吐而言没有新信息，枚举却继续膨胀。

### 影响面

主要是**完备性与可复验性风险**，以及 `UNKNOWN` 爆炸。它不必然造成 false-CERTIFIED，但可能让系统在实际候选上无法到达“穷尽所有 B,S”的可发布结论。

### 修复补丁

替换 §2.5 的三步列表为：

```markdown
1. P7-INFEASIBLE（normal-form Farkas 证书在手）→ 对这一组完整离散选择落 selected-solution nogood。完整选择键必须包括：recipe port binding choice、generic input/output slot assignment、所有 selected route use-vars、以及 selected graph grammar version。该 nogood 的 replay 必须证明下一轮 CP-SAT 不可能返回同一 `(B,S)`。
2. 若尝试泛化 cut，则泛化 cut 必须有独立的 exact-rational 证明，例如 capacity cutset Farkas 证书；不能把 heuristic bottleneck 当 exact-safe cut。
3. 只有当 CP-SAT 在加入所有已复验 nogood/cut 后返回 INFEASIBLE，并且 whole-layout replay 能重建同一 model、同一 cut 序列、同一最终 infeasible 结论时，才能发布候选整体 P7-INFEASIBLE。否则是 UNKNOWN，fail-closed，不落 whole-layout cut。
```

并在 §7 复杂度段追加：

```markdown
收敛性声明只限“有限离散选择空间上的理论终止”。实际可发布终止还要求 cut transcript 可复验；selected-solution nogood 在最坏情况下可能枚举指数级 `(B,S)`，因此 P2.0b 不得承诺每候选新增成本可忽略。单次 LP 可忽略，不代表 LBBD 内环可忽略。
```

---

## NOTE-1：不约束派生需求是正确方向，但需要把“自然涌现”改成“由 T4 + network balance 唯一诱导或被 witness 选择”

设计稿 §2.3 的设计要点 1 避免把 `commodity_demands.json` 当硬约束，这是对的。当前 `commodity_demands.json` 的 17 个键并不等于 route-visible 商品集：它包含 routing-free 终品 `qiaoyu_capsule`、`valley_battery`，但不包含 route-visible cycle commodities `buckwheat_seed`、`sandleaf_seed`。若把该 JSON 当 P7 demand vector，会同时多约束终品、漏约束 seed 循环。

建议把该段最后一句微调为：

```markdown
P7 不读取 `commodity_demands.json` 作为 demand equality。中间商品速率由 recipe-backed 机器的 T4、route-visible network balance、routing-free sink balance 共同诱导；若某个中间/循环 commodity 存在多个可行循环流，witness 可选择其中一个有理稳态流，verifier 只检查 T1-T6 与目标。
```

---

## NOTE-2：`through(φ,s)` 需要给出可执行定义

T2 的 `through(φ,s)` 对 belt/bridge 是唯一入边或唯一出边速率；对 splitter/merger 应定义为 `Σ_in`，并由 T1 保证等于 `Σ_out`。对 co-located cross-junction，容量是 per physical state 还是 per cell aggregate 必须由 A7 或 component capacity table 决定。

建议在 T2 后追加：

```markdown
`through(φ,s)` 定义为该 selected physical state 上全部 incoming incident route/terminal arcs 的跨商品总和；由 T1 可等价改写为 outgoing 总和。若 component_type 有多个独立 channel，需把 channel 作为不同 physical state；若真实组件共享容量，需在 T2 增加 per-cell aggregate capacity row。
```
