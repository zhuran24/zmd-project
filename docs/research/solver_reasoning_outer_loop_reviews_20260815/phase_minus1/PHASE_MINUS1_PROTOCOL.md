# Phase -1：推理外环立项前实验闸冻结协议

> **状态：** `FROZEN_PRE_RUN`。本文件与同目录 `corpus_manifest.json` 所在的 Git 提交就是本轮协议冻结根；提交后不得根据观察结果修改 corpus、分类、指标或阈值。
> **性质：** `non_authorizing / research_only`。本协议只规定证据可采纳性；owner 已授权开展 Phase -1，但实验全绿不等于推理外环立项，最终第二道闸仍是 owner 立项裁决。
> **隔离边界：** 本轮绕过 master，直接研究 fixed placement 的 binding/routing 接口；不修改或消费 proof-bearing 发布面，不调用 supervisor seal/publisher，不设置 certified 路径的 unsafe 环境变量，不改冻结工件。
> **直接检验的架构假设：** 接口可压缩性。语义可压缩性与构造可分解性本轮只记旁证，不因 Phase -1 结果获得通过状态。

## 1. 问题与交付物

本轮回答四个问题：

1. 固定布局在无 alternative-count cap 的 binding/routing 链上，死亡原因是否以可复用家族而非布局身份为主？
2. 下游失败能否经显式 producer→registry→resolver→consumer→receipt 链到达上游，并造成可测域变化？
3. 若发现清晰重复家族，它能否在 discovery 集上形成 sound 的最小 feedback，并在冻结 holdout 上减少昂贵提案而不误杀？
4. 一个外部构造的完整布局能否进入现有 terminal/fixed-witness 验证链；若不能，缺少什么 adapter，是否仍被迫重走同一 binding↔routing 循环？

日终证据包至少包含：

- `D1_DEATH_SPECTRUM.json` 与人读摘要；
- `D2_REACHABILITY_MANIFEST.json`；
- `D5A_EXTERNAL_WITNESS_CANARY.md`；
- 若满足 D3 触发条件，增加一族 feedback 规格与 D4 paired A/B 收据；
- `GO_NO_GO.md`，结论只能是 `GO_CANDIDATE_FOR_OWNER_REVIEW`、`NO_GO_FOR_GENERIC_OUTER_LOOP` 或 `INCONCLUSIVE`。

## 2. 冻结 corpus 与抽样框

机器清单为 [`corpus_manifest.json`](corpus_manifest.json)。抽样框先枚举 15 个本机固定布局候选，静态 admission 后保留 9 个互异布局：

- 6 个 post-membrane / front-clear-lift 固定布局；
- 1 个 W0 alignment 固定布局；
- 1 个 AB16 baseline incumbent；
- 1 个 whole-layout greedy fixed placement。

另有 6 个早期 arm-off 布局在冻结前被排除：其中 optional protocol storage box 仍使用旧 `omni / wireless_sink` 语义，而当前 candidate pool 对同一 anchor 有多个端口模式，无法唯一迁移。不得为了凑样本猜选一个现代端口模式。

### 2.1 Admission 必须全部满足

- raw 文件 SHA-256 与 manifest 一致；
- 当前四份输入工件 SHA-256 与 manifest 一致；
- 266 个 mandatory instance 全部存在且 facility type 一致；
- pose 只允许按 manifest 的 normalization contract 机械解析；
- canonical normalized placement digest 与 manifest 一致；
- normalized layout 之间不得重号；
- 未识别 extra record、缺 mandatory、歧义 pose、坐标推测或 hash mismatch 一律记 `INELIGIBLE_INPUT`，不得进入 D1 分母。

### 2.2 Discovery / holdout

- discovery：6 个；
- holdout：3 个；
- 具体 ID 已写死在 manifest；
- holdout 不得参与死因家族发现、规则形态选择、阈值调整或支持核提炼。

本轮样本小于早期文书建议的 30–50，是预先作出的工期裁量：优先获得一轮可终结、无 cap 污染的首份谱；结论的外延严格限于该冻结 corpus，不伪装成总体频率估计。

## 3. 冻结运行参数

| 参数 | 冻结值 |
|---|---:|
| corpus sampling seed | `20260815` |
| CP-SAT random seed | `1`（当前 solver 默认；禁止运行期改动） |
| harness 并发 layout 数 | `1` |
| binding workers | `1` |
| routing workers | `1` |
| 单次 binding solve limit | `20 s` |
| 单次 routing solve limit | `30 s` |
| 单布局 end-to-end watchdog | `180 s` |
| binding alternative-count cap | **无；`EXACT_B1_BINDING_ALT_CAP` 必须未设置/为空** |
| overload-separation heuristic | `False` |
| cut-framework production attach | **禁止** |
| routing-precheck bypass | **禁止** |

每个 layout 独立子进程运行。父 harness 达到 180 秒必须终止该子进程并记录删失；不能把 watchdog、solver timeout 或外部中断重写成 `INFEASIBLE`。

## 4. D1：无 cap 死因谱

### 4.1 固定执行顺序

对每个 admitted layout：

1. 从当前冻结 pool 构造 normalized fixed placement；
2. 构造并 `build(use_overload_separation=False)` binding model；
3. binding solve；若 FEASIBLE，提取 selection 与 port specs；
4. 运行 exact routing precheck；
5. 若 precheck 给出 exact-safe binding-selection reject，则记录原因，向同一 binding model 加当前 selection nogood，再解下一 selection；
6. 若 precheck 可行，则 build/solve routing；routing INFEASIBLE 时向 binding 加当前 selection nogood，再解下一 selection；
7. binding 最终 INFEASIBLE 才表示在本固定 placement 和已逐个拒绝 selection 的模型内穷尽；任何 TIMEOUT/UNKNOWN/进程终止都只记删失。

不得使用 master，不得使用 alternative-count cap，不得用历史 cut replay 代替本轮观察。

### 4.2 `censorStatus` 冻结枚举

- `UNCENSORED`
- `INELIGIBLE_INPUT`
- `SOLVER_TIMEOUT_BINDING`
- `SOLVER_TIMEOUT_ROUTING`
- `WALL_TIMEOUT_END_TO_END`
- `INVALID_INPUT`
- `HARNESS_ERROR`
- `EXTERNAL_INTERRUPT`
- `ALT_CAP_PROTOCOL_VIOLATION`

`terminalStatus` 与 `censorStatus` 分开记录。`UNKNOWN` 不是死因家族。

### 4.3 死因四维键

每个观察按以下键登记：

```text
reason × gateSide × feedbackForm × censorStatus
```

冻结词表：

- `reason`：`binding_empty_domain`、`binding_invalid_input`、`binding_exhausted`、`routing_front_blocked`、`routing_relaxed_disconnected`、`routing_duplicate_terminal_front`、`routing_model_infeasible`、`routing_connectivity_guard_timeout`、`routing_solver_timeout`、`layout_feasible`、`unknown_other`；
- `gateSide`：`input_admission`、`binding_build`、`binding_solve`、`routing_precheck`、`routing_build`、`routing_solve`、`terminal`；
- `feedbackForm`：`placement_family`、`binding_selection_family`、`point_nogood`、`none`；
- `supportCoreStatus`：`AVAILABLE_REPLAYED`、`AVAILABLE_NOT_REPLAYED`、`UNAVAILABLE`。没有生产诊断支持时必须写 `UNAVAILABLE`，不得凭直觉补一个“最小核”。

逐例至少记录：layout ID、stratum、split、normalized digest、binding proposal 次数、routing precheck 次数、routing solve 次数、binding↔routing 往返数、各阶段 wall time、终态、删失状态、原始诊断与归一化家族键。

## 5. D2：producer→consumer 三态触达

D2 使用研究侧 typed feedback envelope，不接 production cut attach。链条固定为：

```text
routing failure producer
→ research feedback registry
→ scope resolver
→ PortBindingModel.add_nogood_cut consumer
→ before/after receipt
```

必须同时做：

- **organic**：由 D1 中真实 routing precheck/routing failure 产生 feedback；
- **injected**：在冻结 discovery fixture 的第一份 FEASIBLE binding selection 上，构造同型、可独立核对的 selection nogood，验证 consumer 与 receipt。

对未成功闭合的边使用以下 `reachabilityFailureClass` 三态；成功闭合时该字段为 `null`，另记 `terminalOutcome`：

- `NOT_REACHED`：producer 或下游边未被执行；
- `REACHED_NO_EFFECT`：consumer 已调用且有 receipt，但 binding 域/下一 selection 无可测变化；
- `EFFECT_NO_TERMINAL`：域发生变化，但在冻结预算内没有终态。

“代码路径存在”不算 reached。effect 至少需要 before/after selection digest、nogood literal count 和下一次 solve 结果中的一个可重放差异。

## 6. D3/D4 触发条件与 paired A/B

只有 discovery 集同时满足以下条件才允许开 D3/D4：

1. 至少 `6/9` admitted layouts 给出 `UNCENSORED` terminal observation；
2. 同一归一化家族在至少 `3` 个 discovery layouts 复现；
3. 复现跨至少 `2` 个 source strata；
4. feedback 不只是 full-assignment point nogood；
5. 支持核为 `AVAILABLE_REPLAYED`，或该家族直接来自 production exact precheck 的可重放结构诊断；
6. 没有依赖未证 WLOG、流量语义、探针忠实性或布局间独立性的承重跳步。

若触发，选择 discovery 覆盖数最多、再按家族键字典序最小的一族，冻结一份最小编译规格；不得看 holdout 后换族。

### 6.1 D4 成功阈值

在 3 个冻结 holdout 上做 baseline/treatment paired A/B。必须全部满足：

- treatment 不错误排除任何 baseline FEASIBLE 结果；
- aggregate 昂贵提案数（binding proposal + routing solve）下降至少 `10%`；
- 至少 `2/3` holdout 的昂贵提案数不增加；
- routing + checker wall time 不增加超过 `10%`，且热点没有原样从 binding 搬到 routing/checker；
- 所有差异均有 receipt，可从同一 normalized input 重放。

样本过小，因此只报告原始数与配对差，不声称统计显著性。

## 7. D5a：外部布局终验 canary

冻结 canary 是 manifest 中的 `STRICT42-V51`。它只用于接口分析/适配实验，历史自述、route 数据和旧 source hash 不获得当前认证权威。

最低交付是源码级管道分析，必须回答：

- terminal fixed-witness verifier 的输入对象是什么；
- 外部布局能否在不伪造 campaign/proposal authority 的前提下进入独立几何、binding、routing、power 复验；
- 当前 binding/routing 是否存在“固定完整 witness 直接验证”接口，还是会重新枚举同一无 cap 循环；
- 最小 adapter 的输入、输出、信任边界与工程量；
- 哪些历史字段与当前 canonical/pool 不兼容。

若能在 research-only 路径安全做动态 canary，可以追加；不得为了让 canary 通过修改 supervisor/publisher 或生成强状态。

## 8. 冻结判决规则

### 8.1 `GO_CANDIDATE_FOR_OWNER_REVIEW`

仅当以下全部成立：

- D1 达到无删失下限并发现满足 D3 条件的重复家族；
- D2 injected 与 organic 至少各有一条 consumer effect receipt；
- D4 全部成功阈值通过；
- D5a 给出不依赖伪造 authority、且不会原样重走同一 binding↔routing 枚举墙的有限 adapter 路径。

这只表示“值得提交 owner 考虑立项”，不是立项。

### 8.2 `NO_GO_FOR_GENERIC_OUTER_LOOP`

达到至少 `6/9` uncensored terminal observations 后，任一成立即 NO-GO：

- 没有家族达到 `3 layouts / 2 strata`；
- 最强反馈仍只能是点状 full-assignment nogood；
- D2 producer 到不了 consumer，或到达后域始终不变；
- D4 未达到 10% 提案下降、产生误杀或只是迁移热点；
- D5a 只能通过伪造 authority 或重走同一无 cap binding↔routing 循环。

### 8.3 `INCONCLUSIVE`

以下任一成立且未达到可判 NO-GO 的证据量：

- 少于 `6/9` uncensored terminal observations；
- corpus admission 被当前输入漂移破坏；
- harness/环境故障污染主要样本；
- 关键 source artifact 在开跑前消失或 hash 不符。

## 9. 运行与落盘纪律

- harness 与小型结构化结果进入本 dossier，完成后以精确 pathspec 提交；
- 全量日志与大中间产物写入 `.artifacts/solver_reasoning_outer_loop_phase_minus1_20260815/`；
- 长运行必须由 tracked launcher 用 `setsid nohup` 发射，日志末尾写退出码并 touch `.DONE`；
- 只以 `.DONE` 与结构化 receipt 判断终态，不以 `pgrep` 或日志尾句猜测；
- 任何运行期协议偏差都写 `PROTOCOL_VIOLATION`，不得现场修改本文件补救。
