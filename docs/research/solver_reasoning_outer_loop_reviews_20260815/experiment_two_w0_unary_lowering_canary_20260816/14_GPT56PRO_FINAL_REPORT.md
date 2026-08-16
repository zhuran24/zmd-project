# W0 一元 lowering 金丝雀最终报告（GPT-5.6 Pro lineage）

> **运行日期：** 2026-08-16
> **冻结科学判词：** `INCONCLUSIVE`
> **协议冻结提交：** `57a17a7672cf879fc39e0e67a044590a85cb47a2`
> **发射前增补提交：** `988d1b787778c211f5e8b930b7f6cf093581aed8`
> **实现与装置提交：** `edf13896a867ae14be8d5add3f08a41c0f4c5322`、`d3ad19d479eb5ea696ccda374fee655b81f6cfab`
> **删失判词修复：** `fe60db52b65eaa5c3664ad758a06b4427447b4a6`
> **局部效果表述收紧：** `4ce4e7ea7f8e44ab6a0f451d33ba61b4daf948bf`
> **科学运行 ID：** `w0-unary-canary-20260816T171013Z-d3ad19d479`
> **性质：** `research_only / non_authorizing`

## 1. 冻结判词

本实验取得了两个不同层级的结果，二者不能合并成 PASS：

1. **编译域效果成立。** 已证 Judgment 被精确编译为一个一元 CpModel 约束；W0 target slot 的有效域从 3 个值缩到 1 个值，活动 commodity 值从 2 个缩到 0 个。独立 proto checker 证明 treatment 除最后新增的一条单位约束外，与 baseline 完全一致。
2. **运行时 family 效果被删失。** treatment 的第一次 binding solve 在冻结的 20 秒单次预算内返回 `UNKNOWN`，没有产生任何 binding proposal，也没有得到 `FEASIBLE` 或 `INFEASIBLE` 终态。

因此，C 臂的零 event 是**零份 proposal 上的零**。它不能证明 baseline 中的 1007 个 `front_blocked` 循环已在可比较的真实执行轨迹上被一条 family constraint 因果替代，也不能证明 lowering 无效。

最终科学判词为：

```text
INCONCLUSIVE
```

它记录“编译域 3→1 已观测、运行时 family collapse 未观测、终态预算删失”，不授予下一条 theorem canary、通用 family compiler、D3/D4 解冻或 production promotion。

## 2. 三臂结果

| arm | 冻结角色 | arm receipt outcome | terminal | censor | proposals | point nogoods | routing solves | wall |
|---|---|---|---|---|---:|---:|---:|---:|
| `A_BASELINE` | 最小 baseline | `ARM_TRACE_COMPLETE` | `EVENT_CAP_REACHED` | `UNCENSORED` | 1007 | 1007 | 0 | 339.058 s |
| `B_OBSERVER_NOOP` | 完整观测 no-op | `ARM_TRACE_COMPLETE` | `EVENT_CAP_REACHED` | `UNCENSORED` | 1007 | 1007 | 0 | 338.543 s |
| `C_UNARY_LOWERING` | 唯一一元 lowering | 历史 raw=`NO_EFFECT`；重聚合 effective=`CENSORED` | `UNKNOWN` | `CENSORED` | 0 | 0 | 0 | 21.828 s |

A 与 B 各自完成 1007 个 append-only 事件。两臂按以下语义字段逐项完全一致：

- event index；
- selection digest；
- exact precheck status；
- replay identity；
- target instance、front cell 与 commodity；
- point-nogood literal count；
- routing-solve reachability。

ordered selection sequence SHA-256 均为：

```text
9cc4637b444bc66ac2def1151441bc703802f1433c99db456c2fa81225e94f64
```

两臂均复现：

```text
front_blocked events = 1007
point nogoods = 1007
point-nogood literals = 1007 × 285 = 286,995
routing solves = 0
```

B 相对 A 的墙钟差为 `-0.152%`，在冻结的 15% observer 容差内。B 对 1007 个 selection 计算 trigger 的累计时间为 `0.019072 s`，约 `18.94 µs/event`。因此完整观测没有改变 selection 顺序，也没有形成可见的正向开销回归。

## 3. Lowering 合同与灵敏度门

### 3.1 Lowering 合同

发射前独立 checker 重新验证：

```text
theorem currency = PASS
proto delta exact = true
truth table complete = true
mutation canaries killed = 4/4
```

唯一允许新增的约束为：

```text
slot = boundary_port_041:out:0
forced value = __unused__
coefficient = 1
domain = [1,1]
```

其拒绝集合精确等于 `Active_041` trigger set，不扩大到 theorem 未授权的 binding selection。错 slot、错 forced value、额外约束和 stale context 四个变体全部被拒绝。

### 3.2 Endpoint evaluator 灵敏度

11 个冻结控制全部 PASS：

- 6 个正控制；
- 4 个负控制；
- 1 个 stale 控制。

覆盖 lex 第二关键字、最高 band 单点删除与整层关闭、无关低分排除、幂等、stale context、`L=ABSENT`、热点迁移、`NOT_REACHED` 和一元域删除。只有通过这些控制后，真实运行中的 `ZERO_BY_SCOPE` 与 `NOT_REACHED` 才被允许进入报告。

## 4. 编译域效果与运行时删失

C 臂在 `S2` 的编译域变化为：

| 指标 | B observer | C lowering | 差分 |
|---|---:|---:|---:|
| target 有效域基数 | 3 | 1 | -2 |
| target 活动值数 | 2 | 0 | -2 |
| generic-output 边际域和 | 156 | 154 | -2 |
| generic-output box bits | 82.418050 | 80.833088 | -1.584963 |
| CpModel literal 数 | 156 | 156 | 0 |

这里的 `box bits` 是边际域乘积的 `BOX_DOMAIN` envelope，不是联合可行 binding 的精确计数。

C 只调用一次 binding solve：

```text
binding solve seconds = 20.088749
terminal = UNKNOWN
censor = CENSORED
binding proposals = 0
routing prechecks = 0
routing solves = 0
```

所以本轮没有看到：

- 第一份 `boundary_port_041=__unused__` 的 binding selection；
- 该残余 binding 域的 `FEASIBLE` 或 `INFEASIBLE` 终态；
- routing 是否接替成为新热点；
- 与 baseline 共同 proposal／terminal 里程碑上的运行时 family coverage。

A/B 与 C 的 raw event 差为 1007，raw point-nogood literal 差为 286,995；但报告明确：

```text
causal_avoidance_claimed = false
runtime_family_coverage_observed = false
```

因为 C 没有任何 proposal，这些差值不能解释为 1007 个循环已经被因果避免。

## 5. 资源账

| 资源 | A | B | C |
|---|---:|---:|---:|
| wall seconds | 339.058 | 338.543 | 21.828 |
| CPU seconds | 339.483 | 339.061 | 23.051 |
| peak RSS | 679,079,936 B | 679,174,144 B | 1,592,225,792 B |
| binding solve share of wall | 97.19% | 97.10% | 92.03% |

C 的 raw 墙钟只有 B 的 6.45%，但二者没有共同 terminal 或 proposal 里程碑，因此不得写成 93.55% 加速。冻结资源判词是：

```text
NOT_COMPARABLE_CENSORED
```

同时，C 的 peak RSS 约为 A/B 的 2.34 倍。这是明确的资源迁移观测，但单次删失运行不足以判定其稳定性或根因。

当前最有分量的现象是：

> baseline 能持续快速找到大量 doomed assignments；加入一条 sound unary constraint 后，solver 在更窄的残余域中，第一次存在性／不可行性判断反而在 20 秒内没有终态。

这与“删掉 cheap-to-refute family 后，证明成本可能迁移到残余域”完全同形，但本轮不能判定残余域究竟是可行而难找、不可行而难证，还是当前表示／搜索策略导致的困难。

## 6. 终点账

W0 Judgment 只量化固定布局中的 binding selection，不产生 witness，也不排除整个矩形。因此：

```text
ΔL = ZERO_BY_SCOPE
ΔU = ZERO_BY_SCOPE
L = ABSENT
M_t = N_A_NOT_READY
ΔM_bottom = ZERO_BY_SCOPE
ΔG = ZERO_BY_SCOPE
ΔB = ZERO_BY_SCOPE
```

三臂运行前后的 exact status、稳定 claim ledger、research upper-ledger evidence、`PROJECT_LOCK.md`、supervisor seal 源码、certified publisher 源码和 public output surfaces 身份保持不变。

这证明的是 scope non-interference，不是“终点收益经过真实测量恰好等于零”。

## 7. 装置事故与重聚合边界

### 7.1 第一次发射

run：

```text
w0-unary-canary-20260816T170830Z-edf13896a8
```

A 臂在第一次 binding solve 前因 research harness 环境检查函数名错误停止，没有形成 arm receipt 或科学事件。该 run 保留为 `PROTOCOL_VIOLATION` 装置史，不进入科学判词。

### 7.2 第二次 suite 的分类器缺陷

科学 run 收集完 A/B/C 三份 arm receipt 后，旧 suite 把 C 的合法数据面非通过 `rc=2` 当成 apparatus failure，写出 `PROTOCOL_VIOLATION`。后续修复只改变 orchestration／aggregate 的类型化判词：

- `UNKNOWN + CENSORED` 不再改写为 `NO_EFFECT`；
- 数据面 `rc=2` 允许进入 aggregate；
- C 的 raw receipt、A/B journals 与所有 arm receipt 均保持原字节。

最终 aggregate 由提交 `4ce4e7e` 的聚合器重读三份不可变 arm receipt得到。原 suite receipt不被覆盖，继续作为分类器事故史料存在。

纯标准库 post-run checker：

[`12_check_gpt56pro_canary_lineage.py`](12_check_gpt56pro_canary_lineage.py)

tracked compact receipt：

[`13_GPT56PRO_RUN_RECEIPT.json`](13_GPT56PRO_RUN_RECEIPT.json)

checker 重新读取 journals、arm receipts、preflight receipts、aggregate 和提交身份，判定：

```text
checker outcome = PASS
scientific verdict = INCONCLUSIVE
```

checker PASS 只说明证据包自洽与判词重算正确，不把科学判词升级为 PASS。

## 8. 决策边界

本轮允许登记：

- W0 Judgment 已有一个 proto-exact、truth-table-exact 的 research lowering；
- endpoint evaluator 已接线；
- observer no-op 未扰动 baseline 序列；
- 编译域 3→1 已观测；
- 运行时 family effect 与热点迁移因首个 solve 删失而未观测。

本轮不购买：

- 下一条 theorem 的真实 lowering；
- 跨布局 holdout；
- 通用 D3/D4；
- theorem registry 常态化；
- production default；
- certified-exact 上下界进展；
- compute gain 或 1007 family 已运行时塌缩的宣称。

若后续另获 owner 信号，下一问应另冻 v2：

> 在 `boundary_port_041=__unused__` 的残余 binding 域中，用有限且预注册的 solve-cap ladder、有限域 slice 或独立判定器，区分“存在可行 binding”“残余域不可行”与“当前表示下难判”，并建立共同里程碑。

不得回改本次 `INCONCLUSIVE`。

## 9. Lineage 与共享根边界

本报告只消费下列本席 run：

```text
w0-unary-canary-20260816T170830Z-edf13896a8
w0-unary-canary-20260816T171013Z-d3ad19d479
```

共享 artifact 根中存在其他并行 lineage 和另一份顶层 manifest。本报告不读取其 run 数据、不借用其判词，也不覆盖其 manifest。GPT-5.6 Pro lineage 使用独立 manifest：

```text
.artifacts/solver_reasoning_outer_loop_w0_unary_canary_20260816/
EVIDENCE_MANIFEST_GPT56PRO_LINEAGE.json
```

这样并行实验可以物理共址，但证据身份和判词不会被揉成同一来源。
