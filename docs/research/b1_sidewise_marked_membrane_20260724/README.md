# Track B/B1：`22×54` 分边 marked-membrane 最小证明轮

| 项目 | 当前终态 |
|---|---|
| 文档性质 | 当前研究状态与恢复入口 |
| 证据截止 | `2026-07-24` |
| 状态 | **PAUSE_FOR_USER_GAME_END** |
| 上界账本 | `U=(1188,22)` |
| 下界账本 | `L=absent` |
| 当前 authority run | `.artifacts/track_b_b1_sidewise_marked_membrane_20260724/run-20260723T155052Z-SMM1/` |
| claim 层级 | research-only；不是 production `CERTIFIED` |

## 当前结论

本目录是 cuts Gate 1 支线终止后返回 Track B 的下一项最小工作。研究目标是
核心计划候选 3 的 ceiling 特化：对四条边容量 `22,22,54,54` 分开记账，并把
ordinary terminals、marked terminals、端点 partial contact 与 protocol core
的真实单实体 face 选择放进同一安全放松。

当前只建立了以下轻量执行面：

- 原 `(1188,22)` formal authority 的只读语义重放入口；
- 独立 successor worktree 的 byte-locked bootstrap；
- 闭合 JSON schema 的小型 side-contact 模型核；
- 两个互不 import 的合成 fixture 求解器与 mutation canary；
- 游戏结束前禁止进入真实 strict corpus、PB、solver、systemd 与 full preflight
  的 no-overwrite 暂停记录。

尚未运行 strict-instance contact 优化，尚未完成几何独立复算和数学对抗，
也没有生成 OPB 或正式 proof。因此 `U` 与 `L` 都没有变化。

## Authority 分层

### 只读上游

原 authority root 保持：

```text
/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721
HEAD 398f8725c770f3c36408adebe9448a890ed886fe
```

该 root 的 `(1188,22)` detached receipt 为 2,613 B，SHA-256
`0b3366a3e1640a13675a28d1408b9b96ede3a0e6403e71a8f9222f1f44e5b5c2`。
它完整重放后仍为 `VERIFIED UNSATISFIABLE` 且
`upper_bound_update_authorized=true`，同时明确
`production_certified=false`。

上游链还绑定：

- strict instance SHA-256
  `e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c`；
- R4 package ID
  `1a1288a705e699b406d6636c56170f39cb2aecfce18337943e6114035b53369f`；
- selected receipt 13,840 B / SHA-256
  `cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4`；
- response admission `a004` 10,273 B / SHA-256
  `2ebceb7bcdf93ad8cffa75e49eef89af679729f64a47a06ae27fa44682c206ff`。

旧 R4 handoff 文档中的 `AWAITING_EXTERNAL_ACTION` 是 package 生成时的历史状态。
外部回复此后已经完成逐字归档、独立复算、对抗判读和 `a004` 准入；旧 package
与 receipt 的字节仍保持不可变。

### 隔离 successor

本轮实现位于：

```text
/home/zhuran24/zmd-pj-codex-baselines/track-b-b1-sidewise-membrane-20260724
```

它是同一 HEAD 的 detached worktree。原 authority root 不接收本轮文件；
本轮源码、测试和 no-overwrite 工件只进入 successor。bootstrap 同时核对原
formal run 使用的 tracked diff 与 status identity，任一漂移都关闭本轮入口。

## 数学晋级目标

令 `T_in` 为进入 body-free 矩形的全部 active terminal incidences，`M_in`
为其中 110 个 marked incidences 的进入数。现有聚合 control 为：

```text
T_in <= 124
M_in <= 88
T_in + M_in <= 212
```

treatment 的预注册目标是从 strict instance 独立证明：

```text
T_in + M_in <= 209
```

若且仅若该目标通过必要性证明、两份独立复算和坐标级对抗审查，才能推出：

```text
T_out + M_out >= 628 + 110 - 209 = 529
N >= ceil(529 / 4) = 133
22*54 + 133 = 1321 > 1320
```

这将排除 normalized `22×54` 以及 oriented `22×54` / `54×22`。旧 formal
authority 已覆盖 `lex>(1188,22)`；独立 band-composition gate 还必须证明两者
并集恰好覆盖 `lex>(1188,18)`，之后才可进入新的 proof-bearing 上界更新。

## 恢复门

权威恢复点为 authority run 内的：

```text
PAUSE_FOR_USER_GAME_END.json
```

在用户明确确认游戏结束前，不得运行：

- 完整 strict-instance optimizer 或两份真实复算；
- PB encoder、build-only 或 translation gate；
- RoundingSat、VeriPB 或任何其他 solver；
- systemd worker、prod-scale resource run；
- `scripts/preflight_gate.py --full`。

恢复后也必须先完成几何三门。几何门失败、两份复算不一致、treatment 存在
`T_in+M_in>=210` 的有效赋值或对抗面未闭合，都以 `U=(1188,22)`、
`L=absent` 收尾，不进入 formal。

## Claim 边界

本目录当前不建立：

- `T_in+M_in<=209` 的 strict-instance 必要性；
- `(22,54)` 的全局不可行性；
- `U=(1188,18)`；
- 任意 witness 或 attainability；
- 全局 optimality、全问题 infeasibility 或 production `CERTIFIED`。

合成 fixture 只验证模型接口、单实体 face 互斥、端点/容量状态和独立实现
一致性，不能作为真实布局或上界证据。
