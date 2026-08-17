# P1b 九窗口联合修复与区域供电封锁候选（2026-08-17）

> **状态：** `CHECKED_REGION_HALL_HALO_CANDIDATE`
> **作用域：** research-only / evidence-only
> **完整 witness：** 未取得
> **完整原问题 verifier：** `VERIFIER_NOT_REACHED`
> **canonical 下界：** `L=ABSENT → ABSENT`
> **候选谓词身份：** P3/P4 candidate；不是 claim、不是 cut、不是 certified 证据。

## 1. 本 dossier 记录什么

P1b 是 P1 受限 witness 构造线的后继。它保留 top-right 目标锚点，用九个局部电杆窗口与 body packing 做联合局部修复，同时把 P1 的 family A“机身已摆好但供电后补不可扩展”收缩为更小的可检查原因。

P1b 没有产生可提交给完整 verifier 的 master+power candidate，因此没有下界进展。它先达成了另一项预冻结胜利条件：

```text
266-instance whole-layout nogood
    → 6-pose exact minimum local core
    → 56-translation regional Hall predicate candidate
```

完整本地证据包位于：

```text
.artifacts/p1b_joint_power_repair_20260817/
```

恢复入口：

- `REPORT.md`：完整叙事、方法、结果与边界；
- `P1B_TERMINAL_RECEIPT.json`：typed 终局；
- `MANIFEST.json` 与 `SHA256SUMS.txt`：本机 payload 身份；
- `CANDIDATE_PREDICATE.md`：候选谓词的正式研究陈述；
- `BOTTOM_EDGE_TILE_BLOCKADE_CHECKER_RECEIPT.json`：56 平移复算收据。

## 2. 开工对账与停止纪律

P1b 按 `LEDGER_RECONCILIATION_PROTOCOL_V1` 对账，结果为：

```text
relation                NO_CURRENT_MATCH
canonical before state  CANONICAL_EXISTENCE_OPEN_L_ABSENT
```

冻结双目标：

1. 取得 master+power candidate 后立即进入 binding/routing/full verifier；
2. 或提出并独立复算一个远小于 266 实例的区域级供电必要条件候选。

第二项目标先到，故按协议停止继续扩九窗口臂，不把“还有预算”当成继续跑的理由。

## 3. Body incumbent 与供电机制反转

首个目标：

```text
33×35@(37,35)
score = (1155,33)
```

得到一份完整 266 机身 incumbent：

```text
master status      OPTIMAL
solver wall        16.499 s
branches           6,115,422
boundary delta     39
Q-cell violators   37
```

它不是 witness，因为供电、binding、routing 尚未闭合。

对固定 incumbent 运行 exact power-placement subproblem：

```text
powered instances           219
candidate pole poses          72
uncovered powered instances 184
status                        INFEASIBLE
```

这说明 family A 的主机制不是九根杆之间的复杂组合配对，而是固定机身布局已经让约 84% 的需电设施连一个合法电杆落点都没有。

## 4. 266 → 6 的最小局部核

对 184 个 uncovered 目标逐个建立 exact blocker hitting-set。最小核为：

```text
target     planter_sandleaf_006, pose 6113 @ (24,1)
blockers   5
full coverers 140
ghost-blocked 0
unblocked after all blockers 0
minimum blocker cardinality 5
conflict facilities 6
region bbox [18,34] × [0,11]
```

五个 blocker：

| 实例 | pose | anchor |
|---|---:|---:|
| `planter_buckwheat_004` | 4813 | `(19,1)` |
| `planter_buckwheat_005` | 4833 | `(19,6)` |
| `planter_sandleaf_007` | 6133 | `(24,6)` |
| `planter_sandleaf_019` | 7413 | `(29,1)` |
| `planter_sandleaf_020` | 7433 | `(29,6)` |

独立纯标准库 checker 从冻结 placement bytes 重建 target、4,761 个电杆姿态、2×2 pole bodies、coverage cells 与 blocker bodies，并验证：

```text
global minimum cardinality 5
inclusion-minimal          true
negative mutations         5 / 5 rejected
```

该核只证明这六个精确姿态与固定 ghost 条件不能共同拥有供电 completion，不外推整个锚点或尺寸。

## 5. 候选谓词完整身份

候选 ID：

```text
P1B-BOTTOM-EDGE-5X5-3X2-TILE-BLOCKADE-V1
```

### 5.1 陈述

对任意整数 `a∈[0,55]`，六个实心 5×5 body 无缝铺满：

```text
[a,a+14] × [1,10]
```

形成 3 列 × 2 行拼块。下排中间 5×5 为需电目标，其余五块为 blocker。冻结的 2×2 电杆 body 和 coverage 语义下，其他五块与网格底边共同封死目标全部合法 coverer pole poses。

Hall 形式：

```text
demand(T) = 1
available_coverer_capacity(T | five blockers) = 0
1 > 0
```

候选 pose-literal no-good：

```text
x_下左 + x_目标 + x_下右 + x_上左 + x_上中 + x_上右 <= 5
```

### 5.2 当前证据

独立标准库 checker 对全部 56 个水平平移复算：

```text
translation count    56
coverer count range  129..140
unblocked coverers   0 for every translation
negative mutations   5 / 5 rejected at a=19
status                PASS
```

收据 SHA-256：

```text
1b21ff7d684c6cf2d2c24eb46b272cc3a3c3b278f3d7b0ef2c8c75f07f4d9dc2
```

### 5.3 权限与表示身份

该对象当前严格属于：

```text
representation class  P3/P4_CANDIDATE
research status       CHECKED_REGION_HALL_HALO_CANDIDATE
authority             evidence_only
```

它明确不是：

```text
canonical current claim
production cut
certified theorem
proof-relevant artifact
exact-status update
lower-bound update
solver consumption authority
```

后续若要升格，必须另行验证近失配边界、内部纵向平移、目标 tile 换位、混合模板、production incumbent 命中频率，以及 pose-bool / coordinate 两种表示的 source-to-literal 翻译义务；编译与消费仍需 owner 闸。

## 6. 九窗口联合修复结果

同一 incumbent 上运行：

```text
boundary delta          39
window method           L_WINDOW_A
pole window radius       2
local body radius        4
power-core instances     6
Q violators             37
movable union           40
fixed bodies           226
```

结果：

```text
restricted master status INFEASIBLE
branches                  0
presolve wall              2.949 s
candidate                  none
full verifier              NOT_REACHED
```

该结果只判死这一精确受限构造子域，不排除其他窗口、半径、incumbent、锚点或原问题。

## 7. Typed 终局与非蕴含

P1b typed 终局：

```text
status                         CHECKED_REGION_HALL_HALO_CANDIDATE
winning condition              checked regional predicate
master-plus-power candidate    ABSENT
full original verifier         VERIFIER_NOT_REACHED
canonical L                    ABSENT → ABSENT
canonical write                false
```

本 dossier 不意味着：

- `33×35@(37,35)` 不可行；
- 其他九窗口子域不可行；
- 六块整体上移后仍封死；
- 目标换到其他 tile 后仍封死；
- 任意六个 5×5 body 都形成同型矛盾；
- 6×4/4×6 混合拼块自动继承该结论；
- candidate predicate 已可编译或可默认启用；
- binding、routing 或完整原问题 verifier 已通过；
- canonical claim、exact-status 或下界已经变化。

## 8. 本地证据身份

本地 manifest：

```text
.artifacts/p1b_joint_power_repair_20260817/MANIFEST.json
SHA-256 30245c53c4e3fb7bd83c6f4ac85141d302752249fa7690dfe9a01ec1dbc3110e
```

SHA 清单：

```text
.artifacts/p1b_joint_power_repair_20260817/SHA256SUMS.txt
SHA-256 783e889f92fe094e95e2a8e44a1c3629d2201f2b32354032d0e56d14d8d2164c
```

本地 payload 可以在轻量 checkout 缺失；恢复后必须按 manifest 与 SHA 清单复核，不能用空占位或重生成近似物冒充原证据。
