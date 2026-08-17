# P5 水平边界供电封锁 lowering 金丝雀（2026-08-17）

> **最终状态：** `INCONCLUSIVE / STATIC_LOWERING_PASS_RUNTIME_INCONCLUSIVE`
> **对象：** `HORIZONTAL-BOUNDARY-MIDDLE-TARGET-SHELL-V1`
> **Judgment：** `J-P4-HORIZONTAL-BOUNDARY-MIDDLE-TARGET-SHELL-V1`
> **权限：** research-only pose-bool canary
> **production / certified / canonical：** 全部未改动

## 总结

P5 在两个层面得到不同判词。

编译层已经闭合：冻结的六个 `Presence(group_id, pose_idx)` 事件被忠实翻译为 pose-bool 中的一条约束：

```text
sum(six existing BoolVars) <= 5
```

结果为：

```text
new variables       0
new constraints     1
truth-table reject  1
truth-table accept 63
natural P1b all-six assignment rejected     true
six one-event-absent mutations accepted     true
producer-independent pre/post replay         byte-identical
negative proto mutations killed              6 / 6
```

P3 遗留的五项编译义务均在本 canary 作用域内关闭：instance name 只作 group lookup、reject set 与 theorem trigger 精确等价、producer 外独立 replay、currency／invalidation 接入、owner 权限限制。

运行层保持删失：A、B、C 三臂均在单 worker、30 秒首 solve 窗口内返回 `UNKNOWN`，没有产出第一份 body incumbent。因此 baseline trigger、treatment avoidance 和 proposal-level pruning 都没有被观测到。

正确判词：

```text
static lowering        PASS
runtime pruning        INCONCLUSIVE_TRIGGER_NOT_REACHED
pruning observation    NOT_OBSERVED
reason                 CENSORED_BEFORE_TRIGGER_OBSERVATION
overall                INCONCLUSIVE
```

这不是 `NO_EFFECT`，也不是 runtime PASS。

## 授权与冻结

Owner 授权、消费点账本对账和冻结协议见：

```text
00_OWNER_AUTHORIZATION_AND_PROTOCOL_FREEZE.md
```

本 canary 的机器冻结对象位于 local-optional evidence root：

```text
.artifacts/p5_horizontal_canary_20260817/
```

其中：

```text
OWNER_AUTHORIZATION.json
LEDGER_RECONCILIATION_RECEIPT.json
RUN_PROTOCOL.json
RUN_PROTOCOL_ADDENDUM_V1_1.json
```

第一次 run 因 artifact process 未加入仓库根而在模型构建前失败，零 solve、零科学事件；原 receipt 保留。修复只涉及 `sys.path` 装置接线，第二个 run ID 从 A 臂重新完整执行。

## 三臂结果

| Arm | Incumbents | Terminal | Wall | Peak RSS | Branches | Conflicts |
|---|---:|---|---:|---:|---:|---:|
| `A_BASELINE` | 0 | `UNKNOWN/CENSORED` | 38.4754 s | 2.581 GB | 243,317 | 86 |
| `B_OBSERVER_NOOP` | 0 | `UNKNOWN/CENSORED` | 38.5127 s | 2.586 GB | 243,317 | 86 |
| `C_TREATMENT` | 0 | `UNKNOWN/CENSORED` | 38.5405 s | 2.583 GB | 243,317 | 86 |

Observer 解析六事件约 25 微秒；treatment attach 约 51 微秒。相对共同首-solve删失里程碑：

```text
B vs A wall delta  +0.0968%
C vs B wall delta  +0.0722%
```

三臂 coarse branches／conflicts 相同。该事实只说明 observer 与一条约束没有造成可见的 pre-incumbent 装置扰动，不说明更深搜索中的净收益。

## 编译义务

| 义务 | 终态 |
|---|---|
| `P3-LIFT-09-INSTANCE-NAME-NONIDENTITY` | `DISCHARGED` |
| `P3-LIFT-10-REJECT-SET-CORRESPONDENCE` | `DISCHARGED` |
| `P3-LIFT-11-INDEPENDENT-REPLAY` | `DISCHARGED` |
| `P3-LIFT-12-INVALIDATION` | `DISCHARGED_FOR_CANARY_RUN` |
| `P3-LIFT-13-AUTHORITY` | `DISCHARGED_WITHIN_RESEARCH_CANARY_ONLY` |

Producer 外 checker 不 import P5 producer 或 common module，而是自行重建模型、解析事件、添加约束并导出 proto。

## 识别边界

P4 小 corpus 中，当前唯一布局有两个自然 occurrence，历史八个布局零命中；该 corpus 不是随机样本。本轮单-worker body generator 又在首 incumbent 前删失，所以 runtime trigger 频率仍未被测量。

要识别 runtime pruning，后继实验必须预先提供以下之一：

1. 至少一个 all-six hit 和 matched one-event-absent controls 的冻结 incumbent replay corpus；或
2. 在冻结 event horizon 内稳定产出该水平边界壳的 body-generation 分布。

只有 baseline 先暴露 trigger，treatment 的 absence 才有因果含义。

## Endpoint 与非蕴含

最终保护面：

```text
data/knowledge/claims.jsonl
6c3608b09d56e4a76de8a605bf30c71812b4152a0eb00c077e5abccd391f7483

data/solutions/exact_full_scale_status.json
3e525b91e324e8e66abd52c5634fdb97c8957baef8dd49efd63b663f34d3e67e
```

Typed endpoint：

```text
ΔL                       ZERO_BY_SCOPE
ΔU                       ZERO_BY_SCOPE
global M_t               N_A_NOT_READY
canonical ledger write   false
production cut created   false
certified effect         false
```

本批不产生：

- production 或 certified attach；
- coordinate-backend attach；
- canonical claim、下界、上界或 exact-status 更新；
- 跨布局 prevalence 结论；
- full original witness 或 infeasibility 结论；
- generic family compiler promotion。

## 证据入口

完整报告：

```text
.artifacts/p5_horizontal_canary_20260817/REPORT.md
```

终局与义务：

```text
P5_TERMINAL_RECEIPT.json
COMPILATION_OBLIGATIONS_CLOSURE.json
ENDPOINT_RECEIPT.json
RUN_LINEAGE.json
```

科学 run：

```text
runs/p5-horizontal-canary-r2-20260817/SUITE_RECEIPT.json
runs/p5-horizontal-canary-r2-20260817/PROTO_REPLAY_RECEIPT.json
runs/p5-horizontal-canary-r2-20260817/CANARY_AGGREGATE.json
```

Evidence manifest：

```text
MANIFEST.json
SHA-256 344174c5be64ee0196f481a54249778ede4519779eae1edd6278b8f990c08ae4
```

Checksum list：

```text
SHA256SUMS.txt
SHA-256 565a4395151ac7aad8263b63dd9316b0b1140c5bd5cd4157b8255109d4a9cf2a
```

包规模：

```text
payload files       29
checksum entries    30
payload bytes       261,383,396
```

本机 payload 可在轻量 checkout 缺失；缺失时只能使用本 tracked 摘要和登记的 manifest identity，不得补造 runtime receipt。
