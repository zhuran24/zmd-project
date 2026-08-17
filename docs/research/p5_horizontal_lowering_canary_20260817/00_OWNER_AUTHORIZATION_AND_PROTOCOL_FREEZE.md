# P5 水平边界供电封锁 lowering 金丝雀：授权与协议冻结

> **状态：** `FROZEN_PRE_IMPLEMENTATION`  
> **日期：** 2026-08-17  
> **权限：** research-only pose-bool lowering canary  
> **production / certified / canonical：** 未授权

## Owner 授权

当前分支会话中的 owner 原话：

> 「owner 已批:HORIZONTAL-BOUNDARY-MIDDLE-TARGET-SHELL-V1 的 research-only pose-bool lowering canary,开工。」

该信号只打开一条隔离的 pose-bool canary：允许在 treatment arm 中附加一条冻结的六 literal no-good，允许三臂测量和独立 proto replay；不允许 production、certified、coordinate attach、claim ledger、exact-status 或 endpoint 写入。

本地授权收据：

```text
.artifacts/p5_horizontal_canary_20260817/OWNER_AUTHORIZATION.json
SHA-256 14b4941b6dbf44f2fce49c2f9b8822d56760ecd0bf56ed489701a9a1a941a21d
```

## 开工对账

本批是 `LEDGER_RECONCILIATION_PROTOCOL_V1` §3 的 solver-consumption point。对账结果：

```text
relation                NO_CURRENT_MATCH
canonical subject       no current horizontal group-pose blockade claim or cut
local lineage           P4 checked theorem candidate, canary-ready
intended role           consumption_test
owner gate              authorized research-only on 2026-08-17
canonical endpoint      unchanged by contract
```

相关但不等价的 current claims 包括全局九杆下界、conditional halo、W0 历史供电 scope boundary 和 attach 工程／科学效力分离。它们都不授权或替代本次局部 family lowering。

对账收据：

```text
.artifacts/p5_horizontal_canary_20260817/LEDGER_RECONCILIATION_RECEIPT.json
SHA-256 d3ff83775891458c014d927c16db7767a47817f4bf0e5db10358a70caf10ef26
```

## 冻结协议

协议问题：

> 冻结的六事件水平边界定理能否被编译成且只编译成一条 pose-bool no-good，经 producer 外独立 proto replay 证明无越权，并在固定 body-generation 观察窗中因果性地消除其自然首 incumbent 命中？

三臂：

```text
A_BASELINE       不求值 trigger，不附加 family constraint
B_OBSERVER_NOOP  只解析六个 group-pose 事件并观测，不改 proto
C_TREATMENT      在第一次 solve 前附加唯一 sum(six BoolVars)<=5
```

冻结运行形态：

```text
rectangle          33x35@(37,35)
representation     pose_bool_exact_v1
power coverage     skipped in body generator
pole count         0
search             fixed, seed 0, one worker
event cap          3 incumbents per arm
per solve cap      30 s
arm watchdog       90 s
budget extension   forbidden after seeing data
```

静态 proto 合同：

```text
B delta  variables 0, constraints 0
C delta  variables 0, constraints 1
new constraint exactly six expected group-pose indices, coefficient 1, upper bound 5
reject exactly all-six-present; accept other 63 Boolean assignments
coordinate backend shadow-only
```

Runtime 结果三分：

```text
PRUNING_EFFECT_OBSERVED
PRUNING_EFFECT_CENSORED
PRUNING_EFFECT_NOT_OBSERVED
```

另外保留 `NO_LOCAL_EFFECT`、`OBSERVER_EFFECT`、`LOWERING_OVERREACH`、`LOWERING_UNDERREACH`、`REPRESENTATION_MISMATCH` 与 `APPARATUS_FAILURE`。静态 lowering 缺陷优先于任何 runtime 性能数字；runtime 删失不撤销已经独立成立的 proto 合同。

完整机器协议：

```text
.artifacts/p5_horizontal_canary_20260817/RUN_PROTOCOL.json
SHA-256 0ed0628a7ea6987367eb7d362b999b548d29cbb8c984e3362ca82b152ac1b55d
```

## 不变量

本批预注册：

```text
ΔL = ZERO_BY_SCOPE
ΔU = ZERO_BY_SCOPE
global M_t = N_A_NOT_READY
canonical ledger write = false
production cut = false
certified effect = false
```

任何 PASS 都只购买一个窄能力结论：该 checked family 的一个自然六事件实例可以在 research pose-bool model 中被精确消费。它不购买 production 默认、跨布局普遍性、净生产加速或通用 compiler。
