# P4 区域供电封锁 family 抽象与定理化（2026-08-17）

> **状态：** `active / P4_COMPLETE_HORIZONTAL_READY_FOR_OWNER_GATE_OTHER_FAMILIES_HELD`  
> **权限：** research-only / evidence-only  
> **owner lowering gate：** `CLOSED`  
> **canonical claim、cut、certified 与下界效力：** 无

## 问题与作用域

P3 已确认，P1b 出土的 5×5 六块供电核不是一般内部拼块定理；真正承重的是网格边界、目标位置与局部机身壳。P4 将该机制拆成三类 group-pose family，并分别冻结精确语句、独立穷举 checker、系统反例、九布局 corpus 投影和编译义务：

1. `HORIZONTAL-BOUNDARY-MIDDLE-TARGET-SHELL-V1`：水平网格边界相邻行的中间 powered target，允许三条 seam 各为 0 或 1；
2. `CORNER-TARGET-SHELL-V1`：互相垂直的两条网格边界与角 powered target；
3. `MIXED-RECTANGULAR-BODY-SHELL-V1`：5×5、6×4、4×6 target／blocker 的有限混合证书族。

三类的可执行原子统一为：

```text
Presence(group_id, pose_idx)
```

mandatory instance name 只负责查找 symmetric group，不是稳定的 executable literal identity。

本批没有把任何约束接入 pose-bool 或 coordinate master，没有写 `data/knowledge/claims.jsonl`、exact-status、上下界或认证发布面。

## 方法与证据

全部 checker 使用 Python 标准库，直接从冻结 candidate pool 重建：

- 4,761 个 power-pole poses；
- 每个电杆的精确 2×2 body；
- `power_coverage_cells`；
- 5×5、6×4、4×6 的实际 frozen group-pose geometry。

机械结果：

| Family | 正域 | 反例域 | Corpus |
|---|---:|---:|---|
| Horizontal | 1,728 个可表示 case 全部 `BLOCKED`；32 个 frozen geometry `N/A` | 6,708 个系统 near-miss 全部 `EXPOSED` | current 1/1 命中，2 occurrences；historical 0/8 |
| Corner | 48 个可表示 case 全部 `BLOCKED`；16 个 frozen geometry `N/A` | 136 个系统 near-miss 全部 `EXPOSED` | 0/9 |
| Mixed | 28 个镜像闭合模板，93,660 个平移；664 `BLOCKED`、90,732 `EXPOSED`、2,264 `N/A` | 142 个 seed 邻域 case | 0/9 |

Corner family 在 checker 驱动的 scope refinement 中由六事件 3×2 seed 收缩为四事件 2×2 角壳：远端第三列不是承重条件。最终候选 no-good 为：

```text
sum(four group-pose presence events) <= 3
```

Horizontal family 的六事件参考 lowering 经 64-assignment truth table 证明，只拒绝 all-six-present，接受另外 63 个赋值。

## 结果与边界

### Horizontal：达到 owner-gated canary 完备度

精确承重条件：

- target 是上／下网格边界相邻行的中间 5×5 tile；
- target 到对应水平边界距离为 0 或 1；
- left seam、right seam、row seam 各为 0 或 1；
- 六个 group-pose 事件均实际可表示；
- target group canonical `needs_power=true`。

边界距离升至 2、任一 seam 升至 2、target 改为没有垂直边界支撑的边 tile，或删除任一 blocker，都会显式暴露合法电杆姿态。

独立 readiness checker 的终态为：

```text
READY_TO_PRESENT_FOR_OWNER_GATED_LOWERING_CANARY
technical_open_obligation_count = 0
owner_gate_count = 1
owner_gate = CLOSED
```

这只允许把冻结 canary 草案呈 owner 裁决，不授权 attach。

### Corner：定理闭合，无自然 canary target

最终最小形态为 target 加三个内向邻块，共四个 group-pose 事件。两条边界距离和两条承重 seam 均不得超过 1。离开任一边界、seam=2、删除任一 essential blocker 或 target 换位，136 个 case 全部暴露。

九布局 corpus 零命中，因此保留为已证候选，等待自然 incumbent 或单独授权的 synthetic canary。

### Mixed：有限证书族，尚未抽象完

7 个 P3 seed 经三种镜像变换闭合为 28 个模板。664 个 `BLOCKED` case 的 target y 只落在 `0,1,63,64,65`，再次表明机制主要依赖水平网格边界。

该类当前仍是 664 条有限证书，不是紧凑 symbolic family；还缺自然 corpus target、边界子族分解和统一 mandatory multiplicity 合同，不应请求 lowering canary。

## 编译义务与 owner 闸门

水平类已经关闭：

- group-pose identity；
- instance-name nonidentity；
- reject-set correspondence；
- cross-backend event equality；
- fail-closed representability；
- currency / invalidation；
- 独立 proto replay 规格与 checker 装置。

唯一未执行事项是 owner 是否允许 research-only attach canary。`OWNER_GATE_CLOSED` 是 authority 状态，不是被遗漏的技术工作。

Corner 额外缺自然 canary target；Mixed 额外缺 symbolic family、自然 target、边界分类与 multiplicity 合同。

## 本机证据包与恢复

Local-optional evidence root：

```text
.artifacts/p4_blockade_family_abstraction_20260817/
```

读者入口：

```text
REPORT.md
P4_TERMINAL_RECEIPT.json
```

三类 Judgment：

```text
HORIZONTAL_BOUNDARY_MIDDLE_TARGET_SHELL_JUDGMENT.json
CORNER_TARGET_SHELL_JUDGMENT.json
MIXED_RECTANGULAR_BODY_SHELL_JUDGMENT.json
```

Horizontal canary 包：

```text
HORIZONTAL_LOWERING_CANARY_DRAFT.json
HORIZONTAL_CANARY_READINESS_RECEIPT.json
```

Manifest：

```text
MANIFEST.json
SHA-256 773fcc59ec4ba7e88100ad18a25a7961acb5059cd65fe84a47053886874c51a3
```

Checksum list：

```text
SHA256SUMS.txt
SHA-256 18628904da011fbf4d490f9433cf100339aa3131dc8f00e2d98538e3c18c9b27
```

本机 payload 可在轻量 checkout 缺失；缺失时只能保留 tracked 摘要，不能推测或补造 receipt 字节。

## 后继触发器

优先触发器是 owner 对 Horizontal research-only lowering canary 的明确信号。信号到来后，应另冻 canary 协议并保持：

- pose-bool treatment 只新增一条六 literal 线性约束；
- coordinate backend 只做 shadow replay；
- 独立 checker 对 attach 前后 proto 做精确差分；
- 不改变 canonical、production 或 certified 权限。

Corner 在出现自然 corpus hit 时重开；Mixed 在 664 个正 case 被压成更小的符号边界 family 时重开。
