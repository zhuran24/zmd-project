# P2.0 离散吞吐/带宽认证证明范式设计

## 0. 设计立场

本文把“吞吐”作为第七个 certified 谓词接入，而不是把现有 `flow_subproblem.py` 升格。当前包内事实很明确：现有 certified 命题只证明六个谓词和 `max_lex(area, min_side)` 最优性，且明文不证明 belt 离散吞吐、单位时间产率等机制，见 `docs/项目说明/01_overview.md:27-41`。`PROJECT_LOCK.md` 也把物料离散吞吐列为 out-of-scope，并指出当前 routing 只到“belt 路径存在、port 对连通”，不是带宽达标，见 `PROJECT_LOCK.md:100-116`。

我的核心判断是：新谓词必须以“被 routing 选中的物理 route graph”为主要证明对象，而不是在全 70×70 网格上重新证明任意潜在路由。理由是三点。第一，现有 terminal fixed-witness verifier 已经按固定 candidate 独立重解 binding 与 routing，并记录 binding / port / occupancy digest，见 `src/search/terminal_fixed_witness_verifier.py:239-271` 与 `src/search/terminal_fixed_witness_verifier.py:324-375`。吞吐证书天然应绑定到同一次 terminal 复验得到的 route graph。第二，routing 模型当前有“physical component”和“commodity use”两层，物理组件可由多商品共享，这正是带宽容量应限制的对象，见 `src/models/routing_subproblem.py:990-1058` 与 `rules/canonical_rules.json:415-418`。第三，全网格吞吐不可行不等于当前 candidate 不可行，因为还可能存在另一组 binding 或另一张 route graph。

因此本文定义两个层级：

1. **TP7-S，静态平均带宽层**：在已选 route graph 上，用有理数平均流证明所有生产、端口、组件容量都有平均可行解。它有简单、可纯算术复验的可行证书和 Farkas 不可行证书。它是任何离散周期运行的必要条件。
2. **TP7-D，离散周期运行层**：在同一 route graph 上，给出一个周期为 `P` tick 的路径相位调度或更完整 FIFO trace，逐 tick 证明没有任何 belt / port / splitter / merger / bridge 超容量，并且周期边界状态闭合。它是第七谓词的发布级可行证书。

发布级 `CERTIFIED` 应要求 TP7-D 可行。TP7-S 不可行证书可安全地否定某个固定 route graph 的吞吐可行性；TP7-S 可行但没有 TP7-D 时，结论只能是 `UNKNOWN`，不是 `CERTIFIED`。

---

## 1. 包内事实锚点

当前网格为 `70 x 70`，mandatory facility instance 为 266，旧谓词包括 ghost 内无设施、设施不重叠、placement_rule、端口 exact-count、routing 连通、power coverage，见 `docs/项目说明/01_overview.md:7-21`。目标是 `max_lex(area, min_side)`，`min_side >= 6` 是 candidate admissibility floor，不是目标替代品，见 `docs/项目说明/01_overview.md:23-25` 与 `specs/01_problem_statement.md:19-59`。

吞吐相关的规则数据已经存在：`tick_interval_seconds=2.0`，`belt_capacity_per_tick=1.0`，`port_max_throughput_per_tick=1.0`，见 `rules/canonical_rules.json:12-18`。生产目标在 `production_targets` 中声明，当前 `valley_battery` 为 `equivalent_full_speed_lines=3.0` 且 final recipe 为 `packaging_battery`，`qiaoyu_capsule` 为 `2.75` 且 final recipe 为 `filling_capsule`，见 `rules/canonical_rules.json:293-303`。配方满速输入/输出率的代码语义是 `amount / ticks_per_cycle`，见 `src/interchange/preprocess_context.py:32-44`；`equivalent_full_speed_lines` 会乘 final recipe 的输出率得到 target rate，见 `src/preprocess/demand_solver.py:261-272`。因此当前目标率为：

- `valley_battery`: `3 * (1/5) = 3/5` items/tick，依据 `rules/canonical_rules.json:117-127` 与 `rules/canonical_rules.json:293-298`。
- `qiaoyu_capsule`: `11/4 * (1/5) = 11/20` items/tick，依据 `rules/canonical_rules.json:128-137` 与 `rules/canonical_rules.json:299-303`。

预处理的 demand solver 会从 targets 反推非循环需求、机器运行率、循环组需求，并对 cycle group 解有理线性系统，见 `src/preprocess/demand_solver.py:102-129`、`src/preprocess/demand_solver.py:275-315` 与 `src/interchange/preprocess_context.py:656-732`。当前 `commodity_demands.json` 声明外部源需求为 `blue_iron_ore=34`、`source_ore=18`，最终品需求为 `valley_battery=0.6`、`qiaoyu_capsule=0.55`，见 `data/preprocessed/commodity_demands.json:2-18`。generic I/O 工件声明 `required_generic_outputs.blue_iron_ore=34`、`source_ore=18`，`required_generic_inputs.qiaoyu_capsule=1`、`valley_battery=1`，见 `data/preprocessed/generic_io_requirements.json:11-18`。

现有 binding 只证明端口槽数量与 commodity 绑定，不证明每口速率：generic output slot 与 input slot 都 `AddExactlyOne`，每个 required commodity 的 slot 总数等于 required，见 `src/models/binding_subproblem.py:1047-1086`、`src/models/binding_subproblem.py:1095-1132`、`src/models/binding_subproblem.py:1134-1158`。最终产品是 routing-free wireless sink：wireless sink 的 generic input slots 是 virtual 且 routing-free，binding 提取 `port_specs` 时会跳过 routing-free final output 和 virtual generic input，见 `src/models/binding_subproblem.py:1109-1113` 与 `src/models/binding_subproblem.py:1360-1396`。

现有 routing 子问题是布尔 route-state 模型。route state key 是 `(x,y,layer,flow_in,flow_out,commodity)`，见 `src/models/routing_subproblem.py:40`；组件类型包括 ground belt、splitter、merger 和 elevated bridge，见 `src/models/routing_subproblem.py:915-953`。物理组件变量和 commodity use 变量分离，同一 physical state 可被多个 commodity use 触发，见 `src/models/routing_subproblem.py:1012-1058`；每个 cell/layer 的 physical states 有 `AddAtMostOne`，见 `src/models/routing_subproblem.py:1100-1103`。routing acceptance 还会对选中 route-state 图做 source-to-sink reachability guard，见 `src/models/routing_subproblem.py:1693-1802`，并且 `solve()` 只有 guard 接受后才返回 `FEASIBLE`，见 `src/models/routing_subproblem.py:1904-1920`。

现有 flow LP 不能直接复用为认证。它是 GLOP 连续 LP，变量为 `NumVar(0.0, infinity)`，见 `src/models/flow_subproblem.py:148-160`；规格也声明它只是诊断器，`INFEASIBLE` 或 `UNKNOWN` 不能单独淘汰 certified candidate，见 `specs/08_topological_flow_subproblem.md:10-24`。

---

## 2. 新谓词形式定义

### 2.1 第七谓词名称

新增 certified 谓词记为：

```text
TP7_THROUGHPUT_DISCRETE_STEADY_STATE(R, π, b, G_route, Θ)
```

其中：

- `R` 是候选空矩形。
- `π` 是每个 instance 的 pose 选择。
- `b` 是 binding assignment，包含机器端口 commodity 绑定、generic output slot 绑定、wireless sink virtual slot 绑定。
- `G_route` 是 routing guard 接受后的 selected physical route graph。
- `Θ` 是吞吐证书，包含生产活动、周期调度或不可行证明。

发布级可行谓词的量词为：

```text
exists b, exists G_route, exists Θ_feas:
    Predicate1..6(R,π,b,G_route) and
    VerifyThroughputDiscrete(R,π,b,G_route,Θ_feas) = ACCEPT
```

注意：旧命题中 routing 只需要连通，现在第七谓词要求同一 `b` 与 `G_route` 也能承载目标速率。一个 binding/routing 组合吞吐失败，只能否定这一个组合，不能直接否定 `(R,π)`。

### 2.2 速率域

所有速率、容量、周期和计数都在有理数域 `Q` 与整数域 `Z` 上定义。JSON 证书中禁止 float，所有有理数编码为：

```json
{"num": 3, "den": 5}
```

规范要求：`num` 为 JSON integer，`den` 为正 JSON integer，`gcd(abs(num), den)=1`，零必须写作 `{"num":0,"den":1}`。证书 schema 对未知字段 fail-closed，沿用 terminal verifier 已有的“缺字段或未知 durable field 直接拒绝”风格，见 `src/search/terminal_fixed_witness_verifier.py:136-157`。

### 2.3 生产活动变量

对每个 recipe instance `i`，令其 operation type 对应 recipe `q(i)`，配方周期为 `τ_q` tick，输入量 `a_{q,k}`，输出量 `o_{q,k}`。这些值来自 `rules/canonical_rules.json::recipes.*`，代码语义为每 tick 满速率 `a/τ` 与 `o/τ`，见 `src/interchange/preprocess_context.py:40-44`。

证书给出每个 recipe instance 的活动率：

```text
ρ_i ∈ Q, 0 <= ρ_i <= 1
```

解释：`ρ_i=1` 表示该实例满速运行，`ρ_i=0` 表示停机。对周期证书，活动率也可由整数 cycle count 给出：

```text
cycles_i_per_period = n_i ∈ Z_{>=0}
ρ_i = n_i * τ_q / P
```

其中 `P` 是证书周期 tick 数，并要求 `0 <= n_i * τ_q <= P`。如果后续游戏规则允许机器流水线重叠，应在 `throughput_semantics` 中显式声明并改变该约束。

生产平衡约束为：

```text
Produce_i,k = ρ_i * o_{q(i),k} / τ_{q(i)}
Consume_i,k = ρ_i * a_{q(i),k} / τ_{q(i)}
```

最终产品 `k` 的无线接收量必须精确达到 target rate：

```text
Σ_i Produce_i,k = D_k          for k in production_targets
```

中间商品和循环商品满足全局守恒：

```text
external_injection_k + Σ_i Produce_i,k = Σ_i Consume_i,k + wireless_sink_k
```

其中 `wireless_sink_k` 仅允许 `sink_kind=generic_input` 的最终商品。外部源 commodity 必须来自 `source_kind=external_boundary` 的 generic output slots；binding 对该角色的校验见 `src/models/binding_subproblem.py:332-399`。

### 2.4 选中 route graph

从 terminal routing 复验得到 `selected_routes`，规范化为物理组件集合 `P` 和 commodity use 集合 `U`。每个物理组件：

```text
p = (x, y, layer, component_type, flow_in_set, flow_out_set)
```

每个 commodity use：

```text
u = (p, commodity)
```

要求：

1. `p` 必须来自 routing guard 接受的 selected graph。
2. `commodity` 必须在 `p.uses` 中。
3. `component_type` 必须是 `belt`、`splitter`、`merger`、`bridge` 中之一，与 routing 当前 state patterns 对齐，见 `src/models/routing_subproblem.py:915-953`。
4. 同一 `(x,y,layer)` 至多一个物理组件，这是现有 routing 的静态互斥，见 `src/models/routing_subproblem.py:1100-1103`。
5. ground straight belt 与 elevated bridge 的同格交叉只在 canonical bridge/cross-junction 语义允许时成立，见 `rules/canonical_rules.json:410-413` 与 `src/models/routing_subproblem.py:1105-1124`。

把 `G_route` 展开为有向端口侧图：节点是 `(p, side, commodity)`，边是相邻组件的方向匹配，方向匹配规则与 routing guard 的 adjacency 相同：沿 `flow_out` 指向相邻格，目标 use 的 `flow_in` 包含反向方向，见 `src/models/routing_subproblem.py:1413-1432`。

### 2.5 TP7-S 静态平均带宽层

TP7-S 是一个有理多商品流模型。变量包括：

```text
r_i                         recipe instance activity rate
x_{a,k}                     commodity k 在 route arc a 上的平均 items/tick
s_{port,k}                  source port injection rate
t_{port,k}                  sink port extraction rate
```

约束：

1. `0 <= r_i <= 1`。
2. route graph 内部每个 use 的流守恒：除 source/sink 端口外，进入该 use 的 rate 等于离开该 use 的 rate。
3. splitter 不复制物品：`Σ output rates = input rate`；merger 不丢物品：`output rate = Σ input rates`。
4. 每个 physical component 的跨 commodity 聚合使用率不超过 `belt_capacity_per_tick`。当前 canonical 为 `1.0`，见 `rules/canonical_rules.json:15-18`。cross-junction 的 ground channel 和 elevated channel 是两个 physical component，因此各自独立限容，但仍受 routing 的同格合法性约束。
5. 每个 physical port 的通过率不超过 `port_max_throughput_per_tick`，当前为 `1.0`，见 `rules/canonical_rules.json:15-18`。
6. source/sink port rates 与生产活动变量匹配：机器输出端口总注入等于该机器对应 commodity 的 `Produce_i,k`，机器输入端口总抽取等于 `Consume_i,k`；external generic output port 总注入等于 `external_injection_k`；wireless sink final product 不走 route graph，按 virtual slot 容量计。
7. production target 精确等式按 §2.3。

TP7-S 的意义：任何 TP7-D 离散周期运行按周期平均后，都会给出一个 TP7-S 可行解。因此，TP7-S 不可行是固定 selected graph 吞吐不可行的 sound 证据。

### 2.6 TP7-D 离散周期运行层

TP7-D 以周期 `P ∈ Z_{>0}` 的离散事件表证明稳态。本文给出首选的紧凑证书：**periodic path-phase schedule**。

证书列出若干条有限路径：

```text
path_j = (commodity k, source endpoint, component sequence p_1..p_L, sink endpoint)
```

并给出该路径在一个周期内的注入相位集合：

```text
Φ_j ⊆ {0,1,...,P-1}
```

当 `φ ∈ Φ_j` 时，一个 commodity `k` item 在 tick `φ` 从 source endpoint 注入，tick `φ+h` 占用路径上的第 `h+1` 个物理组件，tick `φ+L` 到达 sink endpoint，所有 tick 按 `mod P` 计算。由此得到一个周期闭合的 in-flight item 集合，不需要 verifier 信任求解器的模拟。

Verifier 逐项检查：

1. 路径合法：首尾端口与 binding `port_specs` 匹配，中间组件相邻方向匹配，每个组件允许该 commodity use。
2. 容量日历：对每个 tick、每个 physical component，跨所有 commodity 和 path-phase 的占用数不超过 `belt_capacity_per_tick`。当前容量为 1，所以就是整数 `<=1`。
3. 端口日历：对每个 tick、每个 physical port，注入或抽取数不超过 `port_max_throughput_per_tick`。
4. 生产日历或聚合生产：v1 必须至少验证每个 instance 在一个周期内的输入/输出 item count 与 recipe balance 完全相等；若 `throughput_semantics.machine_timing = cycle_trace`，还要验证 cycle start phases、输入消费 tick、输出完成 tick 与配方 `ticks_per_cycle` 一致。
5. 目标达成：每个 `production_targets` commodity 在一个周期内的 wireless sink 接收数等于 `P * D_k`，且该值必须为整数。
6. 周期闭合：由 path-phase 构造的 in-flight 集合在 tick `0` 与 tick `P` 完全相同；如果证书选择显式 FIFO trace 模式，则直接比较所有 queue 的初末状态。

这种证书比逐格逐 tick FIFO trace 小得多，同时仍是离散整数证书。它对 splitter/merger 的处理是保守的：同一 tick 每个 physical component 最多运一个 item，因此不需要依赖“公平仲裁”来避免多输入争抢。若未来确认 splitter/merger 有更高并行度，可通过 `throughput_semantics` 升版。

---

## 3. 证书格式

### 3.1 公共 envelope

所有吞吐证书共享 envelope：

```json
{
  "schema_version": 1,
  "authority": "throughput_certificate_v1",
  "scope": "selected_route_graph",
  "kind": "feasible_periodic_path_phase_v1",
  "candidate_key": "...",
  "digests": {
    "canonical_rules_sha256": "...",
    "preprocess_plan_sha256": "...",
    "mandatory_instances_sha256": "...",
    "generic_io_requirements_sha256": "...",
    "placement_solution_digest": "...",
    "binding_assignment_digest": "...",
    "port_specs_digest": "...",
    "selected_route_graph_digest": "...",
    "throughput_semantics_digest": "..."
  },
  "payload": {}
}
```

`scope` 的允许值：

- `selected_route_graph`: 只针对一个固定 binding + selected routing。
- `binding`: 证明某个 binding 下所有 selected routing 选择都吞吐不可行，需要额外 all-routings cover 证书。v1 不建议启用。
- `placement`: 证明固定 `(R,π)` 下所有 binding/routing 都吞吐不可行，需要 binding/routing/throughput 联合不可行证明。v1 只作为未来扩展。
- `candidate_frontier`: 证明 lex 更优候选均不可行，用于 campaign-level 最优性。该 scope 必须由 supervisor 独立复验，v1 不直接生成。

### 3.2 可行侧证书 A：`feasible_periodic_path_phase_v1`

payload 结构：

```json
{
  "period_ticks": 20,
  "rate_plan": {
    "targets_per_period": {
      "valley_battery":  {"num": 12, "den": 1},
      "qiaoyu_capsule":  {"num": 11, "den": 1}
    },
    "machine_cycles": {
      "packaging_battery_001": {"recipe_id": "packaging_battery", "cycle_start_ticks": [0,5,10,15]},
      "...": {"recipe_id": "...", "cycle_start_ticks": []}
    },
    "external_injection_counts": {
      "blue_iron_ore": 680,
      "source_ore": 360
    }
  },
  "paths": [
    {
      "path_id": "p000001",
      "commodity": "source_ore",
      "source": {"port_id": "boundary_io_001:out:0"},
      "components": [
        {"component_id": "c:10:3:0", "enter": "W", "leave": "E"}
      ],
      "sink": {"port_id": "crusher_source_001:in:0"},
      "phases": [0, 1, 2]
    }
  ],
  "wireless_sink_events": {
    "valley_battery": [0, 1, 3, 5, 6, 8, 10, 11, 13, 15, 16, 18],
    "qiaoyu_capsule": [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 19]
  }
}
```

说明：上面的数字只是格式示意，不是当前项目候选的证书。实际 verifier 必须从 canonical rules 重新计算 `targets_per_period`，不能信任 payload 中的目标值。当前目标在 `P=20` 时确实是 `12` 个 `valley_battery` 与 `11` 个 `qiaoyu_capsule`，依据 `rules/canonical_rules.json:117-137`、`rules/canonical_rules.json:293-303` 与 `src/preprocess/demand_solver.py:261-272`。

复验器不需要解优化问题，只做确定性重算：重建 `selected_route_graph_digest`，重建端口、组件、capacity resource，展开 path phases，检查每个资源每 tick 的整数占用和每个 commodity 的周期计数。

### 3.3 可行侧证书 B：`feasible_fifo_trace_v1`

当 path-phase 不足以表达游戏机制，例如需要证明有限 FIFO queue 的具体队列顺序、merger 仲裁或启动 warm-up，可使用显式 trace：

```json
{
  "period_ticks": 20,
  "buffer_model": "component_fifo_v1",
  "initial_buffers": {
    "c:10:3:0": ["source_ore", "source_ore"]
  },
  "ticks": [
    {
      "t": 0,
      "actions": [
        {"type": "move", "commodity": "source_ore", "from": "port:boundary_io_001:out:0", "to": "c:10:3:0"},
        {"type": "move", "commodity": "source_ore", "from": "c:10:3:0", "to": "port:crusher_source_001:in:0"}
      ]
    }
  ],
  "final_buffers_digest": "..."
}
```

复验器按 `throughput_semantics` 声明的 tick update order 做纯整数模拟，检查 FIFO head、容量、队列长度、初末队列一致。此格式更大，但最接近游戏离散语义。

### 3.4 可行侧证书 C：`feasible_static_flow_with_lift_v1`

该格式先给 TP7-S 的有理 primal flow，再给一个可复验的 lift 证明，把平均流提升为周期 path-phase schedule。payload 包含：

```json
{
  "static_flow": {
    "variables": {
      "x:arc001:source_ore": {"num": 1, "den": 1}
    }
  },
  "decomposition": {
    "paths": [
      {"path_id": "p000001", "rate": {"num": 3, "den": 20}, "components": []}
    ],
    "cycles": []
  },
  "edge_coloring": {
    "period_ticks": 20,
    "path_phases": {"p000001": [0, 7, 14]}
  }
}
```

Verifier 检查：static flow 满足 TP7-S；decomposition 的 path/cycle rate 重构 static flow；edge coloring 等价于 §3.2 的 path-phase 容量日历。这个格式用于让求解器输出更接近优化模型的对象，但最终可行性仍落到离散相位表。

### 3.5 不可行侧证书 A：`infeasible_static_farkas_v1`

这是 v1 的主力不可行证书。它证明 TP7-S 的线性约束系统不可行。由于任何 TP7-D 周期运行的平均都满足 TP7-S，所以该证书也否定 TP7-D。

复验器先把 TP7-S 全部约束规范化为 `M x <= q`。等式拆成两行，变量非负约束写成 `-x <= 0`，上界写成 `x <= upper`。证书给出非负有理乘子 `λ_row`：

```json
{
  "lp_digest": "...",
  "row_multipliers": {
    "cap:component:c:10:3:0": {"num": 1, "den": 1},
    "balance:node:n123:source_ore:+": {"num": 2, "den": 1}
  },
  "strict_negative_rhs": {"num": -1, "den": 20}
}
```

Verifier 只做纯算术：

```text
for every variable col:
    Σ_row λ_row * M[row,col] == 0
Σ_row λ_row * q[row] < 0
λ_row >= 0
```

若成立，则所有满足 `M x <= q` 的 `x` 会推出 `0 <= negative`，矛盾。该证书不依赖 LP 求解器可信度，也不使用 float。

### 3.6 不可行侧证书 B：`infeasible_periodic_branch_farkas_v1`

当 TP7-S 可行但离散 FIFO 语义不可行时，可选用 bounded-period 整数不可行证明。该证书针对指定 `period_ticks=P`、指定 buffer model、指定 selected graph 的 time-expanded pseudo-Boolean/ILP 模型。

证书是一棵 branch tree：

- 内部节点指定某个整数变量 `z` 的 split，例如 `z <= 0` 与 `z >= 1`。
- 叶子节点给出该分支附加约束下 LP relaxation 的 Farkas 证书。
- Verifier 检查分支覆盖整数域，并检查每个叶子的 Farkas 证书。

这能证明“不存在周期 P 的离散 schedule”。它不是“不存在任意周期 schedule”的证明，除非同时给出一个已复验的 period bound theorem。v1 发布 gate 不应依赖它来剪掉 candidate，只能用于解释和局部 route nogood。

### 3.7 不可行侧证书 C：all-alternatives cover

若要把吞吐不可行提升到 binding 或 placement scope，证书必须显式覆盖量词：

```text
∀ binding choices b accepted by binding model,
∀ routing selected graphs G accepted by routing model,
TP7-S/D infeasible
```

v1 不建议直接实现该 scope。工程上应先在 selected graph scope 失败后回退到 routing search，让 solver 找另一张 route graph；若所有尝试耗尽但没有 all-alternatives cover，返回 `UNKNOWN`。

---

## 4. 独立复验器算法

### 4.1 输入加载与 fail-closed

`throughput_verifier.py` 接收 terminal fixed-witness state、candidate record、吞吐证书和 project root。它必须：

1. strict JSON 读取证书，拒绝 NaN/Inf、float、有未知字段、重复 key、非规范 rational。
2. 重新读取 canonical artifacts，并检查 digests。
3. 重新运行或消费 terminal verifier 已重算的 binding/routing 结果。现有 terminal verifier 已在固定 solver 环境下重解 binding 与 routing，见 `src/search/terminal_fixed_witness_verifier.py:75-90`、`src/search/terminal_fixed_witness_verifier.py:239-258`、`src/search/terminal_fixed_witness_verifier.py:374-375`。
4. 新增一步：routing `FEASIBLE` 后必须提取并规范化 `selected_routes`，计算 `selected_route_graph_digest`。当前 `extract_routes()` 会输出 physical route 及 `uses`，见 `src/models/routing_subproblem.py:1975-2024`，但 terminal verifier 还没有把该 digest 纳入 verdict，这是接入点。
5. 证书中的 `binding_assignment_digest`、`port_specs_digest`、`selected_route_graph_digest` 必须全部与 terminal 重算值一致。

### 4.2 速率重算

复验器从 `canonical_rules.json` 和 `preprocess_plan.json` 重新构建 recipe、target、commodity role、cycle group：

- target rate 按 `src/preprocess/demand_solver.py:261-272`。
- recipe input/output rate 按 `src/interchange/preprocess_context.py:40-44`。
- cycle group 如需重算，可复用 `src/interchange/preprocess_context.py:656-732` 的有理线性系统语义。

但证书不需要信任预处理的 float JSON。`commodity_demands.json` 可作为 cross-check，不能作为唯一证明源，因为其当前保存了 `0.6`、`0.55` 这类 JSON number，见 `data/preprocessed/commodity_demands.json:10-18`。复验器应从 canonical decimal lexeme 转成 exact rational。

### 4.3 selected route graph 规范化

规范化排序键：

```text
component_id = (x, y, layer, component_type, sorted(flow_in), sorted(flow_out))
use_id       = (component_id, commodity)
port_id      = (instance_id, type, local_idx, x, y, dir, commodity)
```

所有 digest 使用 canonical JSON：排序 key、无空白差异、rational 规范化。terminal 现有 `canonical_digest` 已用于 binding/port digest，见 `src/search/terminal_fixed_witness_verifier.py:268-271`。

### 4.4 可行 path-phase 验证

设 `P=period_ticks`，`C` 为 components 数，`L_total` 为所有 path 的 component 长度乘 phase 数之和。

算法：

1. 初始化 `component_calendar[(component_id,t)] = 0`，`port_calendar[(port_id,t)] = 0`。
2. 对每条 path：
   - 检查 source port commodity、direction 与首组件 `enter` 匹配。
   - 检查每个 component 存在于 selected graph，commodity use 被 routing 选中。
   - 检查相邻 component 的坐标与方向符合 `DIR_DELTA` 和 `DIR_OPP`。
   - 检查 sink port 与末组件 `leave` 匹配。
3. 对每个 phase `φ`：
   - source port 在 tick `φ mod P` 加 1。
   - 第 `h` 个 component 在 tick `(φ+h) mod P` 加 1。
   - sink port 在 tick `(φ+L) mod P` 加 1。
4. 每次加 1 后检查不超过容量。容量来自 `throughput_semantics`，默认必须等于 canonical `belt_capacity_per_tick` / `port_max_throughput_per_tick`。
5. 汇总每个 machine/commodity 的输入输出 count，除以 `P` 得到有理 rate，检查 recipe balance、target exactness、external source count、wireless sink count。

复杂度：`O(L_total log L_total)` 若用 hash map 日历，内存 `O(min(L_total, P*(C+ports)))`。当前规则的目标分母 lcm 为 20，但 verifier 不应硬编码；证书可使用任意正整数 `P`。

### 4.5 FIFO trace 验证

算法按 tick 顺序模拟：

1. 将 `initial_buffers` 规范化为 queue。
2. 对 tick `t`，先读取旧状态，检查每个 action 的 source queue head、destination capacity、component compatibility、port/machine legality。
3. 同一 tick 同一 capacity resource 不得被多个 action 占用，除非 `throughput_semantics` 明确允许。
4. 同步提交 pop/push。
5. P tick 后，完整 queue 状态必须等于初态，或者 digest 相等且 verifier 可重算 digest。
6. 统计周期产量。

复杂度：`O(P + action_count + total_buffer_items)`。

### 4.6 Farkas 不可行验证

算法：

1. 从固定 selected graph 和生产模型重建 TP7-S 矩阵 `M x <= q`，生成 canonical `lp_digest`。
2. 检查证书 `lp_digest` 一致。
3. 对所有 row multiplier 检查 rational 非负。
4. 累加每个变量列的系数，要求全为 0。
5. 累加 RHS，要求 `<0`。

复杂度：`O(nnz(M_referenced))`，若 verifier 只遍历证书引用行，需额外检查未引用行乘子默认为 0；若为了防漏，可遍历全矩阵，复杂度 `O(nnz(M))`。

---

## 5. 稳态抽象与游戏离散语义的鸿沟

本文把所有不确定游戏机制显式列为公理。没有对应公理或证书 trace 时，verifier 必须返回 `UNKNOWN`。

| 机制 | 本范式如何处理 | soundness 公理 |
| --- | --- | --- |
| tick 时间 | 所有事件发生在整数 tick，目标 rate 按 items/tick 有理数计算。canonical tick 为 2 秒，见 `rules/canonical_rules.json:12-14`。 | **A1 Tick 公理**：游戏物流更新与 recipe 时间可抽象为统一 tick，且 tick 内事件顺序由 `throughput_semantics.update_order` 完整描述。 |
| 物品离散性 | TP7-D 使用整数 phase/action 计数；`P * rate` 必须为整数。 | **A2 离散计数公理**：一个 item 不可拆分，周期内整数事件能代表稳态平均产率。 |
| belt 容量 | 每个 physical component 每 tick 聚合最多 1 item，跨 commodity 聚合。canonical 只给 `belt_capacity_per_tick=1.0`，见 `rules/canonical_rules.json:15-18`。 | **A3 belt 聚合容量公理**：物理 belt/splitter/merger/bridge 的瓶颈容量与 canonical capacity 一致，且同一组件上不同商品共享此容量。 |
| port 容量 | 每个 physical port 每 tick 最多 1 item。 | **A4 port 容量公理**：`port_max_throughput_per_tick` 是每个已绑定 port slot 的真实上限。 |
| mixed commodity | 允许多商品共享同一 physical component，但日历容量聚合。canonical semantics 明说单个 physical belt/routing component 可被多商品共享，见 `rules/canonical_rules.json:415-418`。 | **A5 混货公理**：多商品共享组件不会引入额外污染、排序禁忌或过滤机制，唯一额外约束是聚合容量与 FIFO 顺序。 |
| FIFO buffer | path-phase 证书默认每组件每 tick 至多一个 in-flight item，可视为容量 1 的保守 schedule；FIFO trace 可显式验证 queue。 | **A6 FIFO 公理**：若使用 FIFO trace，`throughput_semantics` 的 queue 容量和同步更新顺序等同于游戏；若使用 path-phase，游戏允许每组件至少一个 in-flight item。 |
| splitter | path-phase 把 splitter 当作“不复制，一进多出择一路”的组件，且每 tick 最多一个 item。routing state patterns 的 splitter 是一组 `flow_out`，见 `src/models/routing_subproblem.py:935-943`。 | **A7 splitter 公理**：splitter 不复制物品；证书指定的输出选择是游戏可实现的仲裁选择。若游戏强制轮转比例，必须在 `throughput_semantics.splitter_policy` 中加入比例约束。 |
| merger | path-phase 每 tick 最多选择一个输入进入 merger。routing state patterns 的 merger 是多输入一输出，见 `src/models/routing_subproblem.py:945-953`。 | **A8 merger 公理**：证书指定的输入选择是游戏可实现的仲裁选择；若游戏有固定优先级导致某些输入长期饥饿，必须用 FIFO trace 或 priority 规则验证。 |
| bridge / cross-junction | ground straight channel 与 elevated bridge 可在同 cell 垂直相交，各自独立容量。canonical cross-junction 描述见 `rules/canonical_rules.json:410-413`。 | **A9 cross-junction 公理**：两条垂直 channel 同格不会互相阻塞或共享吞吐容量；非垂直或非 straight 组合按 routing 已拒绝。 |
| 机器生产周期 | v1 至少做 aggregate recipe balance；若声明 `cycle_trace`，验证 cycle start/output phases。 | **A10 machine 公理**：aggregate 模式下，机器可在稳态中实现给定平均 input/output rate；cycle_trace 模式下，`throughput_semantics.machine_timing` 必须等同于游戏。 |
| final wireless sink | final product 不走 belt，binding 已把 final sink virtual 化，见 `src/models/binding_subproblem.py:1109-1113` 与 `src/models/binding_subproblem.py:1375-1396`。 | **A11 wireless sink 公理**：protocol storage box 的 wireless sink 对 final product 的接收容量由 generic input slots 给出，且不占用 route graph。 |
| commodity graph 有环 | 周期证书允许非空初始 in-flight / buffer 状态，能表示 buckwheat/sandleaf cycle 的稳态。cycle_groups 见 `rules/preprocess_plan.json:7-33`。 | **A12 warm-up 公理**：发布命题若只声明稳态，可接受周期初态；若要求从空网启动，必须另给 finite startup trace，把空状态引到周期初态。 |

最重要的边界：TP7-S 可行不是游戏可行。只有 TP7-D path-phase / FIFO trace 被接受，或者有一个已复验的 lift theorem，才能进入发布级 `CERTIFIED`。

---

## 6. 与最优性的相互作用

### 6.1 旧不可行剪枝的效力

把第七谓词加入后，新可行集合是旧六谓词可行集合的子集：

```text
Feasible_new = Feasible_old ∩ TP7
```

因此，任何已经 sound 证明“旧六谓词不可行”的剪枝仍然 sound，因为 `not Feasible_old` 推出 `not Feasible_new`。这包括 geometry、binding exact-count、routing connectivity、power coverage 方向的旧 exact-safe cut。旧 `flow_subproblem.py` 仍然不能因此升级；它的诊断边界见 `specs/08_topological_flow_subproblem.md:10-24`。

### 6.2 旧已认证候选的效力

若旧 campaign 已证明候选 `(R*,π*)` 在旧六谓词下 lex 最优，则：

- 若能为同一 `(R*,π*)` 找到 TP7-D 可行证书，则旧的“无 lex 更优旧可行候选”自动推出“无 lex 更优新可行候选”，因为新可行候选必然也是旧可行候选。此时无需重跑整个 frontier，只需重新 seal 一个 schema 升版的 terminal evidence。
- 若 `(R*,π*)` 的吞吐为 `INFEASIBLE` 或 `UNKNOWN`，旧最优性不能证明新问题。需要在旧 frontier 中寻找 lex 次优但 TP7 可行的候选，或者运行增量 campaign。

### 6.3 吞吐失败不能直接剪候选

固定 selected graph 的吞吐不可行只推出：

```text
not exists schedule for this exact (b, G_route)
```

它不推出：

```text
not exists other binding b' or other route graph G'_route for same placement
```

因此 pipeline 的失败回退语义必须是：

1. TP7-D schedule 找不到，先尝试 TP7-S。若 TP7-S 不可行，记录 selected graph throughput nogood。
2. routing 层尝试另一张 selected route graph。
3. 若同一 binding 下 routing alternatives 被一个 all-routings cover 证书穷尽，才可回到 binding。
4. 若所有 binding alternatives 被 cover，才可把 `(R,π)` 判为 throughput-infeasible。
5. 任一 cover 缺失、超时、证书不完整、schema 不匹配，结论为 `UNKNOWN`。

---

## 7. 接入现有认证链

### 7.1 管线位置

推荐新阶段位置：

```text
placement master
  -> binding subproblem
  -> routing subproblem with selected-graph reachability guard
  -> throughput subproblem TP7-S / TP7-D
  -> terminal fixed-witness verifier replays binding+routing+throughput
  -> supervisor seal
  -> public publisher
```

理由：吞吐需要 binding 的 port commodity 和 routing 的 selected physical graph；在 routing 前做只能得到粗诊断，不是证明。当前 routing `FEASIBLE` 的 acceptance 依赖 selected graph reachability guard，见 `src/models/routing_subproblem.py:1693-1802` 与 `src/models/routing_subproblem.py:1904-1920`，吞吐应建立在 guard 接受的 graph 上。

### 7.2 新模块接口

新增模块建议：

```text
src/models/throughput_static_subproblem.py
src/models/throughput_periodic_certificate.py
src/search/terminal_throughput_witness_verifier.py
schemas/throughput_certificate_v1.schema.json
rules/throughput_semantics.json 或 canonical_rules.semantics.throughput
```

核心 API：

```python
verify_throughput_certificate(
    *,
    placement_solution,
    binding_selection,
    port_specs,
    selected_routes,
    canonical_rules_payload,
    preprocess_plan_payload,
    generic_io_requirements_payload,
    certificate_payload,
) -> ThroughputVerdict
```

返回 tri-state：`FEASIBLE`、`INFEASIBLE_SELECTED_GRAPH`、`UNKNOWN`。只有 `FEASIBLE` 可进入 publishable terminal verdict。`INFEASIBLE_SELECTED_GRAPH` 是局部否定，不可直接变成 candidate-level `INFEASIBLE`。

### 7.3 terminal verifier 升版

当前 `TerminalFixedWitnessVerdict` 稳定字段含 `binding_assignment_digest`、`port_specs_digest`、`routing_occupancy_digest`、`binding_status`、`routing_status`，见 `src/search/terminal_fixed_witness_verifier.py:45-62`。建议 schema v2 新增：

```text
selected_route_graph_digest
throughput_semantics_digest
throughput_certificate_digest
throughput_status
throughput_kind
throughput_scope
```

`authority` 从：

```text
terminal_fixed_witness_binding_routing_v1
```

升为：

```text
terminal_fixed_witness_binding_routing_throughput_v2
```

publishable 判定新增：

```text
binding_status == FEASIBLE
routing_status == FEASIBLE
throughput_status == FEASIBLE
throughput_scope == selected_route_graph
```

如果吞吐证书不可复验，projected status 必须是 `UNPROVEN`。这与当前 verifier 对 binding/routing 非 FEASIBLE 的拒绝逻辑一致，见 `src/search/terminal_fixed_witness_verifier.py:260-266` 与 `src/search/terminal_fixed_witness_verifier.py:376-383`。

### 7.4 schema 升版清单

需要升版或新增的 schema/artifact：

1. `terminal_fixed_witness_verdict` v2：新增吞吐 digest/status 字段。
2. `candidate_proof` v2：包含 selected route graph digest 与 throughput certificate digest。
3. `delivery_manifest` v2：公开声明 certified theorem 已含 TP7，且列出 `throughput_semantics_digest`。
4. `throughput_certificate_v1.schema.json`：feasible/infeasible 双侧证书，`additionalProperties:false`。
5. `canonical_rules.schema.json` 或新增 `rules/throughput_semantics.schema.json`：锁定 buffer、splitter、merger、machine timing、wireless sink 等机制。

---

## 8. 复杂度与规模估计

### 8.1 现有数据规模

当前 mandatory exact instances 为 266，`data/preprocessed/mandatory_exact_instances.json::$` 数组长度为 266；文档也在形式问题中声明 266 个 mandatory facility instance，见 `docs/项目说明/01_overview.md:7-10`。当前 generic external output slot 总量是 `34 + 18 = 52`，见 `data/preprocessed/generic_io_requirements.json:11-14`。最终 wireless sink commodity 有两个，每个 required generic input slot 为 1，见 `data/preprocessed/generic_io_requirements.json:15-18`。cycle groups 有 `buckwheat_cycle` 和 `sandleaf_cycle`，见 `rules/preprocess_plan.json:7-33`。

### 8.2 TP7-S 规模

令：

```text
C = selected physical components
U = selected commodity uses
A = directed adjacency arcs between uses
I = active recipe instances
K = commodities
```

TP7-S 变量数约为：

```text
O(A + ports + I)
```

约束数约为：

```text
O(U + C + ports + I + K)
```

由于构建在 selected graph 上，`C` 不会超过 `70*70*2=9800`，通常远小于全候选 route-state 空间。现有 routing 的 candidate state patterns 在每个 active cell 上可膨胀为 belt/splitter/merger/bridge 多种状态，见 `src/models/routing_subproblem.py:915-953`；吞吐 verifier 避开候选状态，只看已选状态。

### 8.3 TP7-D path-phase 规模

令 `P` 为周期，`L_total` 为所有 path-phase 展开后的组件占用数。复验复杂度：

```text
time  = O(L_total)
memory = O(min(L_total, P*(C+ports)))
```

当前目标分母 lcm 为 20：`valley_battery=3/5`，`qiaoyu_capsule=11/20`。但中间路径冲突可能需要更大 `P` 进行相位着色，不能硬编码 20。

### 8.4 证书体积

- Farkas 不可行证书体积约为被引用约束行数乘稀疏度，通常小于完整 trace。
- path-phase 可行证书体积约为 path 数、组件序列总长、phase 总数。对高吞吐主干，phase 可用 run-length 或 bitset 压缩，但 schema v1 应先允许普通数组，优化作为 v1.1。
- FIFO trace 是最大格式，体积约为 `O(P * moves_per_tick)`，用于机制争议和调试，不作为默认生产格式。

---

## 9. 被否决的替代方案

### 9.1 直接把 `flow_subproblem.py` 升格

否决。它是连续 GLOP 诊断器，规格明确禁止把它当 certified gate，见 `specs/08_topological_flow_subproblem.md:10-24`；代码也使用 float capacity 和连续变量，见 `src/models/flow_subproblem.py:38-44` 与 `src/models/flow_subproblem.py:148-160`。即使修补成 rational LP，它也不是 selected physical graph 上的离散周期证书。

### 9.2 在全网格上做吞吐证明

否决作为 v1 主路径。全网格模型可以用于未来“联合 routing+throughput search”，但证书复验会重复 routing 的巨大选择空间。v1 应绑定 terminal 已接受的 selected route graph，符合现有 fixed-witness replay 模式。

### 9.3 只证明端口 slot 数够

否决。当前 port slot exact-count 已经 certified，但 `PROJECT_LOCK.md` 明确区分端口数量、电力覆盖、物料吞吐三种“资源数量够”，物料离散吞吐仍未 certified，见 `PROJECT_LOCK.md:113-116`。一个 commodity 有足够 slot 不代表 route graph 中共享 belt 不拥塞。

### 9.4 只给平均多商品流，不给离散 schedule

否决作为发布级可行证书。平均流可作为 TP7-S 和 Farkas 不可行层，但不能覆盖有限 FIFO、splitter/merger 仲裁、启动状态和离散相位冲突。

### 9.5 对每个 failed graph 直接落 placement nogood

否决。固定 route graph 吞吐不可行不等于固定 placement 不可行，更不等于 candidate 不可行。必须有 all-alternatives cover 才能提升 scope。

---

## 10. 开放问题清单

1. **游戏机制实测**：belt buffer 容量、item 间距、tick update order、splitter 分配、merger 仲裁、bridge/cross-junction 是否共享时钟，必须进入 `throughput_semantics` 并 hash-pin。
2. **机器 cycle timing**：配方是周期末统一输出、周期初统一消耗，还是持续消耗/产出。当前代码只给 rates，见 `src/interchange/preprocess_context.py:40-44`，没有游戏内 tick-level machine semantics。
3. **wireless sink 容量**：binding 把 final products 设为 routing-free virtual sink，但 wireless sink 每 tick 是否有容量上限、是否跨商品共享，需要规则化。当前 utility operation 给 `wireless_sink.generic_input_slots=3`，见 `rules/preprocess_plan.json:51-55`。
4. **周期上界**：何时能从 TP7-S 可行推出存在某个 bounded `P` 的 TP7-D schedule。没有该 theorem 时，TP7-S 可行只能辅助求解。
5. **证书压缩**：大规模 path-phase arrays 需要 bitset、arithmetic progression 或 run-length 编码，同时保持 canonical JSON 和 fail-closed schema。
6. **route search 集成**：routing 目前目标是连通。吞吐失败后如何引导 routing 找低拥塞替代图，需要新 cut，但 cut scope 必须保守。
7. **all-alternatives proof**：若要把吞吐不可行提升到 candidate prune，需要 binding+routing+throughput 联合不可行证书。v1 不应假装已有。
8. **启动 warm-up**：发布命题究竟证明“存在稳态”还是“从空带启动后进入稳态”。若是后者，必须新增 startup trace。
9. **过产处理**：本文要求 final target 精确达成，避免未声明 void sink。若游戏允许溢出、丢弃或缓冲满停机，需要另立公理。
10. **人工可读审计**：最终 delivery 应输出每种 commodity 的 path utilization、component bottleneck 和周期日历摘要，便于 reviewer 找到“吞吐在证书里”的证据。

---

## 11. 最小可落地路线

1. **先落 TP7-S verifier 和 Farkas 证书**：它不需要游戏 FIFO 细节，就能安全否定一批明显拥塞的 selected route graph。
2. **让 routing terminal verifier 输出 `selected_route_graph_digest`**：不改变 routing 求解，只增加复验输出。
3. **实现 path-phase verifier**：以 capacity=1 的保守模型支持可行证书，先不做 FIFO trace。
4. **新增 `throughput_semantics` hash**：先声明 v1 的保守组件语义：每 physical component 每 tick 聚合 1 item，splitter/merger 每 tick只转发 1 item，不复制、不丢弃，cross-junction 两层独立。
5. **terminal schema v2**：只有 binding/routing/throughput 三者都 FEASIBLE 才 publishable。
6. **campaign 迁移**：对旧最佳 candidate 尝试补 TP7-D；若成功，旧 optimality proof 可沿用；若失败或 UNKNOWN，启动增量 search。

这条路线避免把诊断 LP“粉刷成证明”，也避免一口吞下全网格联合 ILP。它把第七谓词拆成可复验的算术对象：平均层负责必要条件和不可行证书，周期层负责离散可行证书，所有跨越游戏机制的部分都由显式公理或 trace 承担。
