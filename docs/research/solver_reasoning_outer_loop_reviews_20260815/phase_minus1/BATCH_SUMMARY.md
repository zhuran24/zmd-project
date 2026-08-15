# Phase -1 r3 批次摘要

> **冻结判词：** `INCONCLUSIVE`。
> **边界：** `research_only / non_authorizing`。本批不产生推理外环立项、认证结论或发布权限。

## 运行身份

- 协议冻结根：`2bd28a9848a1b247a96ca2c34b1f83782f2cda11`。
- 求解运行代码：`e781b5a714493ca34aa17869f01e50327571452c`。
- 聚合计数修正：`6e926e8be3602d40a6b7680263ecdce4f814bf1f`。
- 运行 ID：`phase-minus1-r3-20260815`。
- 时窗：`2026-08-15T15:42:27Z` 至 `2026-08-15T16:09:30Z`。
- 终态：`.DONE` 存在，`EXIT_CODE=0`。
- corpus：9/9 admitted；6 个旧 arm-off 布局因 optional storage box 无法唯一迁移，在开跑前按协议排除。

## 840 与 7578 是两个不同口径

九个布局的 layout receipt 都显示 `routing_prechecks=840`。这个数字来自父看门狗保存的最后一份原子 progress snapshot。r3 每完成 10 次 feedback round-trip 才写一次周期快照，因此 840 只表示子进程已经越过第 840 次快照点，但在写出第 850 次快照前被 180 秒看门狗终止。

D1/D2 的精确总计来自 append-only event/feedback JSONL 中所有以换行完整结束的记录。九份 event journal 的精确值为 840 至 845，总和为 **7578**。本轮 18 份 journal 均无截断末行、无畸形完整行。

因此：

```text
progress counters = 看门狗时最后周期快照的下界
journal counts     = 进程终止前已耐久落盘的精确真源
```

不得把九个均匀的 840 相加后当作 D1 总事件数。

## D1 结果

- 9/9 布局均为 `terminalStatus=UNKNOWN`。
- 9/9 布局均为 `censorStatus=WALL_TIMEOUT_END_TO_END`。
- uncensored terminal：`0/9`，冻结下限为 `6/9`。
- exact routing precheck：`7578`。
- 全部 7578 次均为 `routing_front_blocked`。
- `binding_selection_safe_reject=true`：7578/7578。
- 支持核状态：7578/7578 为 `AVAILABLE_REPLAYED`。
- 诊断重放：7578/7578 为 `REPLAYED_IDENTICAL`。
- routing solve：`0`。
- 实际反馈族只有一个：`routing_front_blocked|routing_precheck|point_nogood|UNCENSORED`。
- 发现 138 个跨 selection/layout 的局部诊断签名候选，但全部保持 `NOT_COMPILED`。

| 布局 | split | progress 下界 | journal 精确 precheck | 快照后追加 | 局部摘要种数 | 全程稳定签名数 | routing solve |
|---|---|---:|---:|---:|---:|---:|---:|
| `POSTMEM-00` | discovery | 840 | 841 | 1 | 213 | 45 | 0 |
| `POSTMEM-01` | discovery | 840 | 841 | 1 | 205 | 40 | 0 |
| `POSTMEM-02` | holdout | 840 | 841 | 1 | 268 | 42 | 0 |
| `POSTMEM-03` | discovery | 840 | 841 | 1 | 235 | 42 | 0 |
| `POSTMEM-04` | discovery | 840 | 842 | 2 | 324 | 35 | 0 |
| `POSTMEM-05` | holdout | 840 | 842 | 2 | 236 | 40 | 0 |
| `W0-ALIGNMENT` | discovery | 840 | 845 | 5 | 3 | 3 | 0 |
| `AB16-BASELINE` | discovery | 840 | 840 | 0 | 213 | 47 | 0 |
| `GREEDY-S0` | holdout | 840 | 845 | 5 | 74 | 5 | 0 |

最强局部候选 `manufacturing_3x3|power_pole|N|0,3` 出现在 8 个布局、6 个 discovery 布局和 2 个 source strata，共覆盖 6709 个事件。它是明确的接口压缩旁证，但当前 consumer 仍消费完整 selection point nogood，且 D3 无删失门未开启，所以不能把该签名升格为 sound family cut。

## D2 结果

Injected canary 与 organic 链都走通：

```text
producer → registry → resolver → PortBindingModel.add_nogood_cut → next solve
```

Injected canary：

- 285 literals；
- 第一次与第二次 selection digest 不同；
- 两次 binding status 均为 `FEASIBLE`；
- `effect=true`；
- 分类为 `EFFECT_NO_TERMINAL`。

Organic：

- feedback applied：7578；
- 已闭合 outcome：7569；
- effect=true：7569/7569；
- watchdog 时 pending：9；
- 所有已闭合 outcome 的下一状态仍为 `FEASIBLE`；
- 所有已闭合 outcome 分类为 `EFFECT_NO_TERMINAL`；
- 每次实际消费均为 285-literal `point_nogood`。

## D3/D4

冻结协议要求至少 `6/9` uncensored terminal observations 才允许打开 D3/D4。本轮为 `0/9`，所以：

- D3 没有打开；
- 没有选择或编译家族；
- holdout 不参与规则归纳；
- D4 paired A/B 没有执行；
- 不能把“D4 未执行”改写为“D4 失败”。

## D5a

源码级 canary 判定为：

```text
ADAPTER_REQUIRED / CURRENT_DIRECT_ENTRY_NO
```

当前 terminal fixed-witness 链要求已有 `CERTIFIED` candidate record 与 candidate-proof，不能诚实接收裸外部完整布局。即便伪装成现有 candidate，它仍会重新枚举 binding alternatives，并忽略外部 witness 自带的 active ports 与 route components，因此会原样重走同一 binding/routing 墙。

有限缺件已经定位为：

```text
ExternalWitnessAdapter
→ FixedExternalWitnessVerifier
→ research-only ExternalCandidateReceipt
```

该 vertical slice 当前不存在，D5a 不提供 GO 信号。

## 日终判词

本轮满足冻结协议的 `INCONCLUSIVE` 条件：uncensored terminal 少于 `6/9`，且尚未达到可判 NO-GO 的证据量。

- 不是 GO：D3/D4 未开放，D5a 直接入口不存在。
- 不是 NO-GO：冻结协议禁止在 `0/9` 无删失终态下用删失谱判死通用推理外环。
- 接口可压缩性：`SUPPORTING_SIGNAL_NOT_DISCHARGED`。
- 语义可压缩性：`NOT_DIRECTLY_TESTED`。
- 构造可分解性：`NOT_DIRECTLY_TESTED`。

完整 owner 判读见 [`GO_NO_GO.md`](GO_NO_GO.md)，结构化结果见 [`D1_DEATH_SPECTRUM.json`](D1_DEATH_SPECTRUM.json)、[`D2_REACHABILITY_MANIFEST.json`](D2_REACHABILITY_MANIFEST.json) 与 [`EVIDENCE_MANIFEST.json`](EVIDENCE_MANIFEST.json)。
