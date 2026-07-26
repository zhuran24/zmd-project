# SMM4 fresh-authority 执行记录

| 字段 | 截止 `2026-07-27` 的记录 |
|---|---|
| 文档性质 | 追加式执行史料 |
| 状态 | `PRE_RUN_IMPLEMENTATION` |
| 当前账本 | `U=(1188,22)`、`L=absent` |
| fresh authority root | 尚未建立 |
| external authority package ID | 不存在 |
| synthetic gates | 尚未运行 |
| full preflight | 尚未报备或运行 |
| formal selection | 尚未创建 |
| `smm4-formal-a004` | 未消费 |
| detached receipt | 不存在 |

## 截止日期前已固定的事实

- 固定隔离 worktree 与基线 `e03bc98dbb00fb38d941e471c61879c499b33213`；
- 确认 SMM3 失败发生在 solver 启动前的 7-field/4-field identity 整对象比较；
- 确认旧 R4 receipt 与 proof graph 的历史字节仍是只读输入，但旧 full replay
  绑定的 checkout 已发生 current-HEAD `repository_identity_drift`；SMM4 必须使用
  fresh snapshot-only adapter，不能依赖旧 live path，也不能改写旧记录；
- 固定共享 full7 identity 与 canonical4 content projection、sealed
  `authority.json`/`SHA256SUMS` 以及 external package ID 的实现合同；
- 固定 payload spec 位于 fresh run 的 `preselection-a001/`，canonical attempt
  directory 的 `selection.json` 是首个不可变对象和唯一消费边界；selection 前
  只有精确空目录可续，且不写 failure receipt；
- 固定 selection 后异常的 no-retry 闭包为 `failure-terminal.json`、
  `failure-cleanup.json`、`attempt-failure.json` 与 independent verifier
  `detached-failure-verification.json`；detached failure 未生成或未验证也必须由
  closeout 明确记录；
- 固定 `systemd-run`/`systemctl` 从 full7 钉死 executable 的 retained FD 经
  `/proc/self/fd/<n>` 执行，并同时记录和复核 logical/executed argv provenance；
- 固定组合链必须依次连接旧 `U=(1188,22)` 的完整 `2084` band、SMM-209
  admission、candidate-old delta 精确公式、`(22,54)` 与 `(54,22)` 两个方向和
  2-selector UNSAT；局部 delta UNSAT 不得替代旧完整 band 前件；
- 记录 2026-07-27 “上界恢复先行”的有限 owner 排期；实存的
  [SMM3 后续 cut 强制排期](../b1_sidewise_marked_membrane_authority_recovery_20260724/04_cuts_mandatory_schedule.md)
  不变；
- 记录 owner 指定的
  `../noncert_cuts_ab16_20260724/04_cuts_mandatory_schedule.md` 在固定 HEAD
  中缺失。该 provenance/path gap 不改变 SMM4 方向，也不构成 cut 已完成证据；
  最新 [AB16 状态](../noncert_cuts_ab16_20260724/README.md)为 Gate A 已
  finalized、Gate B 未建且 organic arms 为 `0/16`；结合 owner 当前口径，
  Gate1 v4 已过。

## 尚未发生

本记录没有 fresh sealed authority、external package ID、synthetic
success、synthetic post-SEAL failure、formal admission、selection、formal
proof、resource、terminal、cleanup 或 detached 成功证据，也没有监督线程的
重负载放行。因此 `(1188,18)` 仍是待采证候选；不得从当前记录更新账本或宣称
attainability、optimality、whole-instance infeasibility、production
`CERTIFIED`。

后续运行结果只在真实阶段完成后追加。只有 formal detached receipt 明确写出
`upper_bound_update_authorized=true` 才能追加成功收口并更新
`U=(1188,18)`；否则保持 `U=(1188,22)`。selection 已创建后的失败必须把
`smm4-formal-a004` 追加记录为 consumed/incomplete，禁止同编号重试；若
`detached-failure-verification.json` 缺失，执行记录还必须保留其预期路径与
未验证状态。selection 前的精确空 canonical attempt directory 不构成消费，也
不应产生失败记录。所有分支始终保持 `L=absent`，且旧 SMM2/SMM3 失败记录不得
在此处改写。
