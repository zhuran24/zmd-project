# P1 受限 witness 构造与供电死因谱（2026-08-17）

> **证据截止：** 2026-08-17
>
> **dossier 状态：** `active`
>
> **P1 运行状态：** `COMPLETE_NO_VERIFIED_WITNESS`
> **权威边界：** research-only historical evidence。本文不修改 canonical claim ledger、上下界、exact status、认证面或发布面。

## 1. 问题与结论

P1 尝试为 production 单基地 70×70 原问题构造第一份完整可验证 witness，使 canonical 下界从 `L=absent` 变成数值。搜索范围是 P0 预注册的六级 ladder：

```text
31×38 -> 28×42 -> 30×39 -> 29×40 -> 34×34 -> 33×35
```

每级选择五个 P0 `UNKNOWN` 锚点。30 个目标全部完成有效 screen，但 54 次总尝试中没有产生 constructor candidate，完整原问题 verifier 因而没有被调用：

```text
verifier status    = VERIFIER_NOT_REACHED
reason             = NO_CONSTRUCTOR_CANDIDATE_EMITTED
canonical L before = ABSENT
canonical L after  = ABSENT
ΔL                 = 0
```

这不是 verifier 拒绝，也不是任何尺寸或锚点不可行的证明。

## 2. 证据总账

| 项目 | 数量 |
|---|---:|
| 全部 attempt receipt | 54 |
| 有效科学尝试 | 51 |
| 装置失败 | 3 |
| 六级 ladder 主筛查 | 30 / 30 |
| constructor `UNKNOWN` | 42 |
| 受限子域 `INFEASIBLE` | 9 |
| constructor candidate | 0 |
| full original verifier 调用 | 0 |

本机可选证据包：

```text
.artifacts/p1_witness_construction_20260817/
```

入口：

- `.artifacts/p1_witness_construction_20260817/REPORT.md`
- `.artifacts/p1_witness_construction_20260817/MANIFEST.json`
- `.artifacts/p1_witness_construction_20260817/SHA256SUMS.txt`
- `.artifacts/p1_witness_construction_20260817/attempt_aggregate.json`
- `.artifacts/p1_witness_construction_20260817/VERIFIER_NOT_REACHED_RECEIPT.json`

轻量 checkout 可以缺少该 payload。恢复时必须取得与 `MANIFEST.json` 和 `SHA256SUMS.txt` 匹配的完整目录；不能用空文件或重新生成的近似日志代替原始 attempt receipt。

## 3. 开工对账

`LEDGER_RECONCILIATION_RECEIPT.json` 的开工判词为：

```text
relation               = NO_CURRENT_MATCH
canonical_before_state = CANONICAL_EXISTENCE_OPEN_L_ABSENT
```

30 个主筛查锚点在 P0 投影中均为 `UNKNOWN`，且无 current claim ID 覆盖其可行性。该对账允许研究构造，不授权 witness 入账；只有完整原问题 verifier PASS 后，另开 before-state 入账批才可改变 canonical 下界。

## 4. 两个主死因家族

### 家族 A：机身可摆，供电后补不可扩展

`POSE_BOOL_GEOMETRY_THEN_POWER` 先搜索完整非电杆机身布局，再对固定机身运行 exact power-placement subproblem。共观察到 8 次家族 A，其中 7 次属于 30 个主筛查目标。

六个 rung 的 `top_right_boundary_preserving` 均进入该家族；31×38 的 `right_bottom_stratum` 也进入该家族。捕获到的 cut 摘要均为：

```text
cut_type              = power_subproblem_infeasible_nogood
conflict_size          = 266
support_conflict_scope = all_non_pole_selected_occupancy
```

这证明“先把全部机身塞下，再补电杆”对这些具体布局不可扩展，但不证明目标锚点不可行。后继工作的关键是把 266 实例 whole-layout nogood 收缩为局部供电冲突或区域级必要条件。

### 家族 B：机身 master 预算删失

其余 23 个主筛查尝试在完整非电杆机身布局产生前返回 master `UNKNOWN`。`centered`、`legal_lower_left`、`left_top_stratum` 六级全部落入家族 B；`right_bottom_stratum` 除 31×38 外也落入家族 B。

这与 top-right 的稳定家族 A 构成空间非对称。最窄结论是矩形位置显著改变当前构造表示的可搜索性和供电自由度；`UNKNOWN` 不能改写为几何不可行。

## 5. 表示层对撞

31×38 top-right 的 coordinate exact 尝试在约 132 秒 solver wall 内保持 0 branches、0 conflicts，峰值 RSS 约 11.54 GB；主要成本发生在模型构建与 presolve。

同一目标换成 integrated pose-bool 后产生约 4,360 branches，centered 产生约 4,472 branches。pose-bool 把零分支预处理墙改成了真实搜索，但 60–100 秒内仍没有候选。`automatic` branching 未改善状态，峰值 RSS 升至约 15.23 GB；固定九杆计数也仍为 `UNKNOWN`。

因此 P1b 不再给裸 coordinate master 或无结构 integrated pose-bool 增加预算。

## 6. Halo capacity 必要非充分反例

六个 boundary delta 的 halo-capacity 贪心都选择同一条竖线上的九根杆：

```text
(8,8), (8,10), ..., (8,24)
halo_lhs2 = 7128
halo_rhs2 = 6650
```

六个 restricted master 全部 `INFEASIBLE`。空间分散骨架 `L_GRID_A` 也满足 `6896 >= 6650`，但 restricted master 仍 `INFEASIBLE`。

合计 7 个固定九杆骨架满足 conditional-halo inequality，却没有与之兼容的完整机身布局。这否定了“满足或最大化 aggregate halo capacity 就足以构造 witness”，但不削弱该 inequality 作为必要条件的地位。

## 7. 九窗口模型

固定点骨架过硬后，九根杆被放宽为九个互不重叠的 radius-2 anchor window；每个窗口恰选一根杆，窗口外 pole anchors 禁用，供电覆盖与机身联合求解。五次尝试覆盖：

- 33×35 top-right 的 `L_WINDOW_A/B/C`；
- 34×34 top-right 的 `L_WINDOW_A`；
- 30×39 top-right 的 `L_WINDOW_A`。

五次均为 master `UNKNOWN`，没有被快速判死，也没有产生候选。其正确身份是：

```text
PROMISING_BUT_CENSORED_CONSTRUCTIVE_RESTRICTION
```

## 8. P1b successor

P1b 保留 top-right 锚点，以九窗口模型为起点，联合优化杆位与 body packing。两个停止目标并列：

1. 产生 master＋power candidate，立即停止扩模型并进入 binding、routing、完整原问题 verifier；
2. 从 incumbent、domain 与 power trace 中提取远小于 266 实例的供电冲突核，或区域级 Hall-halo 必要条件候选。

完整 verifier PASS 后只汇报 witness，不在 P1b 内自行写 canonical lower ledger。必要条件候选只作为 P3/P4 种子，不自动成为 claim 或 solver cut。

## 9. 非蕴含

本 dossier 不意味着：

- 任一 ladder 尺寸或锚点不可行；
- production 原问题无 witness；
- exactly nine poles 是必要或充分条件；
- top-right 在原问题中比其他位置更可行；
- conditional-halo inequality 无效；
- pose-bool 获得 certified production authority；
- restricted-subspace `INFEASIBLE` 可以写 upper ledger；
- budget `UNKNOWN` 可以改写为结构性墙。

## 10. 复算入口

所有 Python 命令使用 `.venv/bin/python`：

```bash
.venv/bin/python .artifacts/p1_witness_construction_20260817/p1_finalize_evidence.py
.venv/bin/python -m ruff check \
  .artifacts/p1_witness_construction_20260817/p1_construct_witness.py \
  .artifacts/p1_witness_construction_20260817/p1_finalize_evidence.py
```

`p1_finalize_evidence.py` 会 fail closed 地核对 54 份 receipt、30/30 主筛查覆盖、candidate 计数和 verifier 调用计数，然后重建 aggregate 与 typed-null 收据。它不运行 full verifier，也不写任何 canonical 状态。
