# Phase -1：给 owner 的 go/no-go 证据材料

> **协议判词：** `INCONCLUSIVE`。
> **建议动作：** 不依据本证据包批准通用推理外环立项；若继续追加实验，必须新开协议或显式补充协议，不得回头移动本轮冻结门槛。
> **边界：** `research_only / non_authorizing`。实验全绿不等于立项，本轮也没有全绿。

## 一句话结论

本轮第一次用无 ALT_CAP 的固定布局 binding/routing 循环，机械坐实了一个非常稳定的热点形状：

```text
binding FEASIBLE
→ exact routing precheck front_blocked
→ 285-literal full-selection point nogood
→ 下一份 binding 仍 FEASIBLE
```

这条循环在 9 个布局中精确发生 7578 次，routing solver 一次也没有进入。局部诊断形态高度重复，说明接口压缩值得继续看；但 9 个布局全部在 180 秒端到端预算下被删失，`0/9` 获得无删失终态，D3/D4 因冻结协议未获准打开，外部完整 witness 也不能直接进入现有终验链。因此证据不足以判 GO，也不足以按协议判 NO-GO。

## 判决矩阵

| 项目 | 冻结要求 | 本轮结果 | 判读 |
|---|---|---|---|
| D1 无删失死因谱 | 至少 `6/9` uncensored terminal 才能打开 D3 或判 NO-GO | `0/9`；9 个均为 `WALL_TIMEOUT_END_TO_END` | 证据量不足，必须 `INCONCLUSIVE` |
| D1 热点位置 | 记 proposal、precheck、routing solve 与删失 | 7578 次 precheck 全为 `front_blocked`，routing solve 为 0 | 热点明确位于 binding→routing precheck 接缝 |
| D2 injected effect | consumer 必须 reached 且改变域/下一 selection | 285-literal nogood 生效，下一 selection digest 改变 | 通过 |
| D2 organic effect | 至少一条真实 producer→consumer effect receipt | 7578 applied；7569 已闭合 outcome 全部 effect | 通过，但全部 `EFFECT_NO_TERMINAL` |
| D3 家族编译 | 先满足 `6/9` 无删失门，且反馈不能只是 point nogood | 无删失门未满足；实际反馈仍为 full-selection point nogood | 按协议不得打开 |
| D4 holdout A/B | D3 合法触发后才能执行，aggregate 昂贵提案下降至少 10% | 未执行 | 不得写成通过或失败 |
| D5a 外部布局终验 | 不伪造 authority，且不原样重走同一枚举墙 | 当前直接入口不存在；薄包装仍重枚举 binding/routing | 不提供 GO 信号 |

## D1：删失谱与真实墙位

### 1. 终态

- corpus admission：9/9 admitted；
- discovery/holdout：6/3；
- `terminalStatus=UNKNOWN`：9/9；
- `censorStatus=WALL_TIMEOUT_END_TO_END`：9/9；
- uncensored terminal：0/9；
- 冻结最低证据量：6/9。

所有 wall timeout 都保留为 `UNKNOWN`，没有静默改写成 `INFEASIBLE`。这部分删失纪律有效。

### 2. 840 不是终计数

九个 layout receipt 的 progress counters 都停在 840。r3 每完成 10 次 feedback round-trip 才写一次原子 progress snapshot。父进程在 watchdog 时只能保存最后完成的 snapshot，所以 840 的含义是：

> 九个子进程都到达过第 840 次快照点，但没有到达第 850 次快照点。

它不表示九个布局各自恰好执行了 840 次 precheck。

精确事件数来自 append-only JSONL。各布局 journal 为 840 至 845 条，合计 7578 条。本轮所有 journal 均无截断末行、无畸形完整行。

因此结构化 D1 明确分开：

```text
progress_counters_lower_bound = 周期快照下界
journal_derived_counts        = 精确耐久真源
```

### 3. 计数订正

此前会话阶段性回报中的 `7408 applied / 7400 outcomes / 8 pending` 是收口前的错误口述，不是最终工件真值。本文件及四个 tracked 小工件以全量 journal 复点后的下列值取代它：

```text
7578 feedback applied
7569 feedback outcomes
7569 outcomes with effect=true
9 feedbacks pending at watchdog censor
```

### 4. 7578 次事件的共同形态

全部 7578 条 event 都满足：

- `record_type=routing_precheck_failure`；
- `reason=routing_front_blocked`；
- `binding_selection_safe_reject=true`；
- `supportCoreStatus=AVAILABLE_REPLAYED`；
- `diagnosticReplayStatus=REPLAYED_IDENTICAL`；
- 实际 feedback form 为 `point_nogood`；
- routing solve 次数为 0。

这不是“routing 很慢”。更准确地说，routing solver 根本没有获得入场券。时间消耗在如下循环：每次 point nogood 后重新求一个 binding，再由 exact precheck 立即拒绝。

## D2：consumer 能到达，也确实改变下一 selection

### Injected canary

Injected canary 在 `POSTMEM-00` 上完成：

- registry：`REGISTERED`；
- resolver：`RESOLVED`；
- consumer：`APPLIED`；
- literal count：285；
- 第一次 binding：`FEASIBLE`；
- 第二次 binding：`FEASIBLE`；
- before/after selection digest 不同；
- `effect=true`；
- 三态分类：`EFFECT_NO_TERMINAL`。

### Organic 链

7578 条 organic feedback 全部满足：

- producer：`routing_precheck:front_blocked`；
- consumer：`PortBindingModel.add_nogood_cut`；
- registry/resolver/consumer 均成功；
- literal count 均为 285；
- feedback form 均为 `point_nogood`。

7569 条已闭合 outcome 中：

- 7569/7569 的下一 selection digest 发生变化；
- 7569/7569 的下一 binding status 仍为 `FEASIBLE`；
- 7569/7569 分类为 `EFFECT_NO_TERMINAL`。

另外 9 条是每个子进程在 watchdog 时最后一条刚应用、尚未来得及完成下一 solve 的 pending receipt。

D2 因而证明“consumer 不可达”并不是本项目当前问题。真正问题是：消费者只会排掉一个完整 selection，随后迅速找到另一个具有同型局部死因的 selection。

## 接口可压缩性的支持信号

本轮发现 138 个局部诊断签名候选。最强候选：

```text
manufacturing_3x3
→ blocker power_pole
→ north front
→ relative offset (0,3)
```

覆盖：

- 8 个布局；
- 6 个 discovery 布局；
- 2 个 source strata；
- 6709 条 event presence。

其他多组制造设施相邻签名也覆盖 5 个 discovery 布局、2 个 strata。`W0-ALIGNMENT` 的 845 个不同 selection 只形成 3 种局部摘要，且 3 个局部签名贯穿全部事件。

这说明 7578 个不同点不是 7578 种完全不同的数学原因。下游给出的局部结构比当前 point nogood consumer 实际使用的信息丰富得多。

但这些签名当前只能记为：

```text
NOT_COMPILED
```

原因有二：

1. 冻结协议要求 `6/9` 无删失终态后才允许打开 D3，本轮为 `0/9`；
2. 尚未建立“局部签名 → 上游 binding/port domain 收紧”的独立 sound lowering contract。

因此它们是很强的支持信号，不是已经成立的 family cut。

## D3/D4 为什么没有做

协议不是要求“看到重复就立即编译”，而是要求先有足够无删失终态，防止从被时间截断的循环里挑一个看起来漂亮的模式。

本轮 `0/9 < 6/9`。所以 D3/D4 没有合法入口：

- 没有选择最强家族；
- 没有冻结 family lowering；
- 没有看 holdout 后换规则；
- 没有做 3 个 holdout 的 paired A/B；
- 没有 10% 提案下降收据；
- 没有误杀检查或热点迁移检查。

这不是工程遗漏，而是遵守开跑前冻结的停止规则。

## D5a：外部完整布局 canary

`STRICT42-V51` 携带完整设施布局、active ports 和 route components，但当前 terminal fixed-witness 入口不是裸布局验证器。它先要求：

- authority state 中已有相应 candidate record；
- record 已是 `CERTIFIED`；
- candidate-proof 与 solution digest 闭合；
- final_result 与 candidate identity 闭合。

为了让外部 JSON 直接通过这些前置条件而自行铸造 `CERTIFIED` 或 candidate-proof，会伪造 authority，不能接受。

即使只做 schema 包装，现有 verifier 仍会重新建立 `PortBindingModel`，枚举 binding alternatives，运行 exact precheck 和 routing solve。外部 witness 已给出的 active ports 与 route components 不会被当作固定 witness 消费，因此同一 binding/routing 墙仍会重演。

最小缺件是三段式 vertical slice：

```text
ExternalWitnessAdapter
→ FixedExternalWitnessVerifier
→ ExternalCandidateReceipt
```

其中第二段必须直接核验固定 active ports 与固定 route，而不是重新寻找它们。receipt 只能是 research-only 弱状态，不得写 `CANDIDATE_PROPOSED`、`CERTIFIED`、seal 或 publisher surface。

所以 D5a 的当前判定是：

```text
ADAPTER_REQUIRED / CURRENT_DIRECT_ENTRY_NO
```

## 为什么不是 GO

冻结 GO 要求 D1、D2、D4、D5a 全部成立。本轮只有 D2 consumer effect 闭合：

- D1 无删失下限未达到；
- D3/D4 未获准打开；
- 没有 holdout 10% 收益证据；
- D5a direct admission vertical slice 不存在。

因此不能给 `GO_CANDIDATE_FOR_OWNER_REVIEW`。

## 为什么也不是 NO-GO

冻结 NO-GO 的前提是先达到至少 `6/9` uncensored terminal observations。本轮只有 `0/9`。即使当前实际 feedback 仍是 point nogood，协议也禁止用被 180 秒统一截断的谱直接判死通用推理外环。

因此不能给 `NO_GO_FOR_GENERIC_OUTER_LOOP`。

## 三条架构假设的本轮状态

| 假设 | 本轮状态 | 理由 |
|---|---|---|
| 语义可压缩性 | `NOT_DIRECTLY_TESTED` | Phase -1 协议不直接检验 theorem/normal-form 对整体语义的压缩 |
| 接口可压缩性 | `SUPPORTING_SIGNAL_NOT_DISCHARGED` | 大量不同 selection 映射到少量跨布局局部死因，但尚无 sound family lowering 与 holdout A/B |
| 构造可分解性 | `NOT_DIRECTLY_TESTED` | 未做充分模块拼装、残余自由或 exact checker 通过率实验 |

接口项的正向旁证不能外推成另两项同时成立。

## 给 owner 的建议

1. **本证据包不应触发推理外环立项。** 它只足以说明“接缝存在高度重复的可压缩候选”。
2. **也不应把通用推理外环判死。** 冻结的无删失证据下限未满足。
3. 任何后续动作都应被视为新投资闸，而不是补写本轮结果。最窄的候选方向有两个：
   - 为一个明确的 `front_blocked` 局部族建立独立 sound lowering，再按新协议做 holdout A/B；
   - 建立固定 active-port + fixed-route 的外部 witness verifier vertical slice。
4. 在 owner 显式拍板前，现行 solver、认证链和发布面保持不变。

## 证据入口

- [`D1_DEATH_SPECTRUM.json`](D1_DEATH_SPECTRUM.json)：紧凑 D1 真值投影，明确区分快照下界与 journal 精确计数。
- [`D2_REACHABILITY_MANIFEST.json`](D2_REACHABILITY_MANIFEST.json)：injected/organic consumer 触达与 effect。
- [`BATCH_SUMMARY.md`](BATCH_SUMMARY.md)：批次概览。
- [`D5A_EXTERNAL_WITNESS_CANARY.md`](D5A_EXTERNAL_WITNESS_CANARY.md)：外部 witness 管道分析。
- [`EVIDENCE_MANIFEST.json`](EVIDENCE_MANIFEST.json)：tracked 小工件和 `.artifacts` 大日志的 SHA-256 绑定。

最终 owner 决定仍是独立第二道闸。本文件不能替代该决定。
