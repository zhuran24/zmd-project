# Phase -1 v2：高预算死因谱与窗口饱和度冻结协议

> **状态：** `FROZEN_PRE_RUN_V2`。本文件与同目录 `corpus_manifest_v2.json` 所在的首个提交共同构成本轮协议冻结根；运行开始后不得修改 corpus、预算、窗口定义、阈值、停止条件或结论分类。
> **性质：** `non_authorizing / research_only`。本轮只产生推理外环立项前证据；实验达到任何预注册端点都不等于推理外环立项。
> **隔离边界：** 绕过 master，直接研究 fixed placement 的 binding/routing 接口；不修改或消费 proof-bearing 发布面，不调用 supervisor seal/publisher，不设置 certified 路径的 unsafe 环境变量，不改冻结工件。
> **D3/D4 状态：** `DEFERRED_BY_OWNER`。本协议只保留候选家族输出接口，不编译 family feedback、不运行 treatment、不做 holdout paired A/B。

## 1. 前代证据与本轮问题

本轮引用但不修改前代：

- v1 协议冻结根：`2bd28a9848a1b247a96ca2c34b1f83782f2cda11`；
- v1 证据包提交：`1914e2a3ec7bc07fec4ccbcbf428129247ed0eed`；
- v1 机械审计补登记：`21c0108e3ab91f66437bffe5e9ab6562f6e9338a`；
- v1 判词：`INCONCLUSIVE`。

v1 r3 在 9 个完整布局、每个 180 秒窗口中得到：

- 7578 条完整 event journal 记录；
- 7578 次 exact routing precheck，全部为 `front_blocked`；
- 7578 次 point-nogood feedback applied；
- 7569 个已闭合 outcome，全部改变下一 selection；
- 0 次 routing solve；
- 0/9 uncensored full-layout terminal。

观测速率约为：

```text
7578 / (9 × 180 s) = 4.678 binding-selection rounds / s
```

因此单纯把 180 秒改成数小时，仍不保证穷尽完整 binding 空间。v2 同时采用三种证据形态：

1. **少数完整布局的数小时级深窗口**；
2. **有限 binding-domain slice 的 exact terminal calibration**；
3. **把删失窗口内的死因家族饱和度升格为正式、预注册的经验端点**。

窗口饱和度只证明“在冻结抽样过程与预算内，接口返回的归一化死因分布已稳定”，不证明完整布局无解，也不替代 exact exhaustion。

## 2. 冻结 corpus

完整记录、输入 SHA 与机械 normalization 见 `corpus_manifest_v2.json`。本轮只消费 v1 已 admission 的三个布局：

| run id | layout | source stratum | role | v1 选择理由 |
|---|---|---|---|---|
| `DEEP-POSTMEM-00` | `POSTMEM-00` | `postmem_fcl_lift` | discovery | v1 有 213 种局部摘要，代表中等熵完整布局 |
| `DEEP-W0-ALIGNMENT` | `W0-ALIGNMENT` | `cross_line_fixed_layout` | discovery | v1 仅 3 种局部摘要，最接近可饱和/可穷尽形态 |
| `DEEP-GREEDY-S0` | `GREEDY-S0` | `cross_line_fixed_layout` | audit holdout | 不参与阈值设计；用于检验冻结饱和标准能否迁移到另一构造器 |

另设 6 个**有限域 calibration slices**，只使用 `POSTMEM-00` 与 `W0-ALIGNMENT`：

```text
POSTMEM-00 × target_product {1, 64, 4096}
W0-ALIGNMENT × target_product {1, 64, 4096}
```

slice 不是新游戏实例，也不是完整布局结论。它是在同一 fixed placement、当前 canonical rules 与当前 binding model 上，把除预注册 open groups 外的变量冻结到第一份 FEASIBLE selection，随后无 cap 地穷尽该有限子域。

`GREEDY-S0` 不参与 slice 设计或阈值调整，保持 audit-holdout 身份。

## 3. 冻结运行参数

### 3.1 公共求解参数

| 参数 | 冻结值 |
|---|---:|
| CP-SAT random seed | `1` |
| Python hash seed | `0` |
| binding workers | `1` |
| routing workers | `1` |
| 单次 binding solve | `20 s` |
| 单次 routing solve | `30 s` |
| binding alternative cap | **不存在；`EXACT_B1_BINDING_ALT_CAP` 必须为空** |
| deep full-layout max wall | `28800 s`（8 h） |
| slice max wall | `2700 s`（45 min） |
| deep 并发 | `3` |
| slice 并发 | `1` |
| 总并发上限 | `4` |

禁止非空：

```text
EXACT_B1_BINDING_ALT_CAP
EXACT_B1_BYPASS_ROUTING_PRECHECK
EXACT_B1_ROUTING_AWARE_BINDING
EXACT_BINDING_USE_OVERLOAD_SEPARATION
EXACT_BINDING_DUMP_STATE
EXACT_CUT_FRAMEWORK_ATTACH
EXACT_B1_DELETION_CORE_CUT
EXACT_B1_LAZY_DEMAND_CUT
```

### 3.2 调度

三个 deep arm 启动后并行运行；slice arm 以单工方式与 deep arm 并行。调度器不得因为看到中间结果改变顺序、预算或 slice target。

每个 arm 独立目录，必须拥有：

```text
full.log
progress.json
EXIT_CODE
.DONE
```

深窗口另有 append-only：

```text
events.jsonl
feedback.jsonl
saturation_windows.jsonl
```

顶层运行目录只在全部预注册 arm 结束后写 `EXIT_CODE` 与 `.DONE`。

## 4. 完整布局深窗口

执行顺序保持：

```text
fixed placement
→ PortBindingModel
→ FEASIBLE binding selection
→ exact routing precheck
→ routing model/solve（仅 precheck feasible 时）
→ point nogood
→ 下一 binding selection
```

完整布局 arm 的合法终态：

- `FULL_LAYOUT_FEASIBLE`：发现一份 routing FEASIBLE selection；
- `FULL_LAYOUT_BINDING_EXHAUSTED`：binding model 在无 cap、累计 point nogood 后返回 INFEASIBLE；
- `SOLVER_TIMEOUT_BINDING`；
- `SOLVER_TIMEOUT_ROUTING`；
- `WINDOW_SATURATED`；
- `WALL_TIMEOUT_END_TO_END`；
- `INVALID_INPUT`；
- `HARNESS_ERROR`；
- `EXTERNAL_INTERRUPT`；
- `PROTOCOL_VIOLATION`。

只有前两项是完整布局的 uncensored terminal。`WINDOW_SATURATED` 是正式经验端点，但不是可行性终态。

## 5. 正式窗口饱和度

### 5.1 计数单位

按事件数而非墙钟切窗：

```text
window_size = 5000 exact precheck/routing failure events
```

完整末窗不足 5000 时不参与连续饱和判定，但保留为尾部诊断。

每个事件同时产生三层身份：

1. `actual_feedback_family`：reason + gate side + 实际 feedback form；
2. `event_shape_digest`：局部 blocker type/direction/relative-offset 多重集的 canonical digest；
3. `atomic_local_signatures`：组成该多重集的原子签名集合。

当前 consumer 若仍使用完整 selection nogood，`actual_feedback_form` 必须写 `point_nogood`；不得把 diagnostic local shape 伪装成已编译 family feedback。

### 5.2 每窗指标

第 t 个完整窗记录：

- `event_count`；
- event-shape 唯一数；
- 相对此前累计的新 event-shape 数；
- `new_event_mass_fraction`：本窗中首次出现的 event-shape 所占事件比例；
- atomic signature 唯一数与新增数；
- 与上一窗 event-shape 集合的 Jaccard；
- 与上一窗 event-shape 频率分布的 total variation distance：

```text
TVD(P,Q) = 0.5 × Σ_i |P_i - Q_i|
```

- cumulative singleton count `f1`；
- Good–Turing unseen-mass proxy：`f1 / cumulative_event_count`；
- top-10 event-shape mass；
- actual feedback family 分布；
- routing solve 进入次数。

### 5.3 单窗饱和判据

一个完整窗只有同时满足以下条件才标为 `saturated=true`：

```text
new_atomic_signature_count == 0
new_event_shape_count <= 2
new_event_mass_fraction <= 0.005
event_shape_jaccard_vs_previous >= 0.95
event_shape_tvd_vs_previous <= 0.05
good_turing_unseen_mass <= 0.01
```

首窗没有 previous window，不能 saturated。

### 5.4 布局级饱和端点

允许提前结束 deep arm 的唯一经验停止条件：

```text
cumulative events >= 60000
complete windows >= 12
last 3 complete windows 均 saturated
```

满足后写：

```text
terminalStatus = UNKNOWN
censorStatus = WINDOW_SATURATED
```

这意味着至少 12 个 5000-event 窗、约为 v1 单布局观察量的 71 倍。若未满足，arm 必须继续到完整布局 terminal、solver timeout 或 8 小时 max wall；不得因“看起来稳定”人工提前停止。

### 5.5 跨布局证据端点

v2 正式证据量分级：

- `FULL_LAYOUT_TERMINAL_OBSERVED`：至少一个 deep arm 获得 `FULL_LAYOUT_FEASIBLE` 或 `FULL_LAYOUT_BINDING_EXHAUSTED`；
- `WINDOW_EVIDENCE_READY`：至少 2/3 deep arms 获得完整布局 terminal 或 `WINDOW_SATURATED`，且覆盖 `postmem_fcl_lift` 与 `cross_line_fixed_layout` 两个 strata；
- `WINDOW_EVIDENCE_INSUFFICIENT`：不满足以上两项。

`GREEDY-S0` 的结果只能按冻结标准评估，不能反向修改 discovery arm 的窗口定义或阈值。

## 6. 有限域 slice terminal calibration

### 6.1 deterministic slice 构造

每个 slice 先在未加限制的 binding model 上求第一份 FEASIBLE selection，并运行一次 exact precheck。随后构造变量组：

- `binding_choice::<instance_id>`；
- `generic_input::<slot_id>`；
- `generic_output::<slot_id>`。

每组 cardinality 等于其当前 exactly-one 变量数。open group 排序规则冻结为：

1. 当前 precheck `placement_level_conflict_set` 涉及的 binding instance 优先；
2. 其余 binding groups；
3. generic input groups；
4. generic output groups；
5. 同级按 `(cardinality, group_id)` 升序。

从空集合开始，按顺序加入 group；只有加入后 cardinality product 不超过 `target_product` 才保留。未打开的所有变量组固定到第一份 selection。

`target_product=1` 表示所有可变组均固定；一次 point nogood 后应形成最小 exact exhaustion canary。

### 6.2 slice 执行与终态

slice 内仍无 alternative cap：

```text
restricted binding solve
→ exact precheck/routing
→ point nogood
→ restricted binding solve
```

终态：

- `SLICE_FEASIBLE`；
- `SLICE_BINDING_EXHAUSTED`；
- `SLICE_SOLVER_TIMEOUT_BINDING`；
- `SLICE_SOLVER_TIMEOUT_ROUTING`；
- `SLICE_WALL_TIMEOUT`；
- `SLICE_HARNESS_ERROR`。

`SLICE_BINDING_EXHAUSTED` 只证明该 receipt 中钉死的固定变量、open groups 和 current inputs 下没有剩余 selection。不得提升成完整布局 INFEASIBLE。

slice calibration 成功阈值：

```text
至少 5/6 slice arms 获得 SLICE_FEASIBLE 或 SLICE_BINDING_EXHAUSTED
且 target_product=1 的两个 canary 都获得 exact terminal
且无 journal/identity/protocol corruption
```

此阈值只判断 harness 是否能在有限空间产生终局观测，不决定推理外环立项。

## 7. 死因谱与接口可压缩性输出

每个 deep arm 必须输出：

- actual feedback family 计数；
- event-shape discovery curve；
- atomic local signature discovery curve；
- 每窗饱和指标；
- point selection 数与 event-shape 数之比；
- support-core/replay 状态；
- routing solve 到达率；
- 完整终态或删失状态。

跨布局聚合必须分别报告：

- discovery-only；
- audit-holdout；
- combined；
- strata overlap。

任何候选局部家族均写：

```text
compilation_status = DEFERRED_BY_OWNER
consumer_status = NOT_RUN
D3_status = NOT_OPENED
D4_status = NOT_OPENED
```

不得生成可执行 cut、不得改 binding/master、不得在 holdout 上做 treatment。

## 8. 本轮结论分类

本轮不输出 v1 式 GO/NO-GO。只允许：

- `V2_FULL_LAYOUT_TERMINAL_OBSERVED`；
- `V2_WINDOW_EVIDENCE_READY`；
- `V2_WINDOW_EVIDENCE_INSUFFICIENT`；
- `V2_PROTOCOL_VIOLATION`。

同时独立报告：

- slice calibration：`PASS / FAIL / INCONCLUSIVE`；
- D3：`DEFERRED_BY_OWNER`；
- D4：`DEFERRED_BY_OWNER`；
- 推理外环立项：`NOT_DECIDED_BY_THIS_PROTOCOL`。

实验结果无论多强，都只进入 owner 的后续裁决材料。

## 9. 落盘与提交纪律

- 协议与 manifest 必须先提交，且提交为所有运行 commit 的祖先；
- harness 与 launcher 另行精确 pathspec 提交；
- 每笔本轮提交必须带：

```text
Co-Authored-By: GPT-5.6 Pro <noreply@openai.com>
```

- 运行由 tracked launcher 通过 `setsid nohup` 发射；
- 大 journals 与 logs 留在 `.artifacts/solver_reasoning_outer_loop_phase_minus1_v2_20260815/`；
- 小型结构化收据、最终摘要和 evidence manifest 才进入 Git；
- 不运行 preflight 或 slow lane；
- 不修改 v1 协议、v1 三份评审归档、既有 decisions 行或 proof-bearing 工件。
