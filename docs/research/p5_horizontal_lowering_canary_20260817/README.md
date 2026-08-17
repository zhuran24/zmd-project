# P5 水平边界供电封锁 lowering 金丝雀（2026-08-17）

> **当前状态：** `FROZEN_PRE_IMPLEMENTATION`  
> **对象：** `HORIZONTAL-BOUNDARY-MIDDLE-TARGET-SHELL-V1`  
> **Judgment：** `J-P4-HORIZONTAL-BOUNDARY-MIDDLE-TARGET-SHELL-V1`  
> **权限：** research-only / pose-bool canary  
> **owner gate：** 本 canary 已授权；production、certified 与 canonical gate 仍关闭

## 研究问题

P4 已把水平边界供电封锁 family 定理化，并把编译技术义务关闭到只剩 owner attach gate。本批只检验该 family 的一个自然六事件实例能否：

1. 在 pose-bool backend 中解析为六个稳定的 `Presence(group_id, pose_idx)` 事件；
2. 只新增一条 `sum(six events)<=5` 约束；
3. 经 producer 外独立 proto replay 证明没有变量增量、子集误杀或其他模型漂移；
4. 在固定 body-generation 观察窗中消除自然命中，并完整记录 observer 成本、runtime censoring 与热点迁移。

自然实例来自 P1b 的 `33×35@(37,35)` body incumbent，在 `x=19` 处包含六个冻结 group-pose presence 事件。第二个 `x=24` occurrence 不进入本次 treatment cut，因此可以作为同一布局中的邻近未编译 family 观测。

## 冻结入口

授权、对账、预算、判词和非蕴含见：

```text
00_OWNER_AUTHORIZATION_AND_PROTOCOL_FREEZE.md
```

机器真源保存在：

```text
.artifacts/p5_horizontal_canary_20260817/OWNER_AUTHORIZATION.json
.artifacts/p5_horizontal_canary_20260817/LEDGER_RECONCILIATION_RECEIPT.json
.artifacts/p5_horizontal_canary_20260817/RUN_PROTOCOL.json
```

实现与运行不得原地修改这些冻结对象。需要修正装置时，只能新增 addendum 和新 run ID，历史 receipt 保持不可变。

## 预注册输出

本 dossier 完成时应给出：

- 三臂 arm receipts 与 ordered incumbent journals；
- B no-op 与 C treatment 的 binary CpModel proto；
- producer 外独立 proto replay receipt；
- endpoint／resource receipts；
- typed aggregate verdict；
- local-optional manifest 与 checksum list；
- 对 P3 编译义务逐条关闭的证据表。

## 效力边界

本批不修改：

```text
data/knowledge/claims.jsonl
data/solutions/exact_full_scale_status.json
production source
certified source
coordinate backend model
canonical L/U/M_t
```

即使 canary PASS，也只表示一个已核 family 实例在隔离 pose-bool research model 中得到精确消费；不产生 claim、cut registry、production default、certified effect 或通用 family compiler 权限。
