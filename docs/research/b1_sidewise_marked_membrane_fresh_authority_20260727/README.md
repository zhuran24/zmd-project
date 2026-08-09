# SMM4 fresh-authority recovery

| 字段 | 当前值 |
|---|---|
| SMM4 终态日期 | `2026-07-27` |
| 当前状态日期 | `2026-07-30` |
| 状态 | `VERIFIED / FORMAL_A004_CONSUMED_NO_RETRY` |
| 研究账本 | `U=(1188,18)`、`L=absent` |
| authority | detached receipt 与 immutable closeout 已授权 research upper recovery |
| production | `production_certified=false` |
| 下一项强制任务 | `AB16_GATE_B_AND_16_ORGANIC_ARMS`（A031–A038 frozen；A038 `FAIL_CLOSED`；fresh successor 尚未创建；arms `0/16`） |

SMM4 是对同一候选 `(1188,18)` 的有限 authority recovery，不是新 B1/B2
武器。固定实现 HEAD、fresh sealed authority、全新 no-overwrite root 和唯一一次
`smm4-formal-a004` 已建立外层证据闭包。该 formal attempt 已消费且永久不得重试。
旧 SMM2/SMM3 与前两个 SMM4 root 的失败工件继续只读保留；SMM4 没有修改 v1
历史面，也没有续跑或重写旧 attempt。

## 文件

- [01_authority_contract.md](01_authority_contract.md)：authority、identity、
  组合证明和声明边界；
- [02_execution_protocol.md](02_execution_protocol.md)：synthetic、资源放行、
  one-shot formal、detached 和收口顺序；
- [03_execution_record.md](03_execution_record.md)：追加式执行史料；
- `identity_contract_v1.py`：full7 与 canonical4 的共享 fail-closed 合同；
- `authority_package_v1.py`：sealed authority 与 external package ID verifier；
- `verify_smm4_old_upper_v1.py`：旧 R4 snapshot-only authority adapter；
- `verify_smm4_composition_v1.py`：完整 local composition gate；
- `run_smm4_*_v1.py`、`verify_smm4_two_stage_v1.py`：fresh authority 和 two-stage
  lifecycle。

## 当前判读

前两个 fresh root 已分别在 selection 前 manager identity bridge 和
post-selection synthetic loader join 处 fail-closed，并完整冻结。当前成功 root
为
`.artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727/run-20260726T211018Z-SMM4-14a491b/`，
external authority package ID 为
`bed3a65a788655b95b445c944292b28fdf6a9f6fce74b27c4f0f8a2617a0622b`。
完整追加式史料见 [03_execution_record.md](03_execution_record.md)。

`formal-attempt-a004/formal-a004/internal_formal_receipt.json` 虽为
`VERIFIED`/UNSAT，仍明确保持 `upper_bound_update_authorized=false`。最终
`formal-attempt-a004/detached-verification.json` 为 `VERIFIED`，SHA-256
`9a590d3e0ba6805dc2c1d6abebe60274e4cc5ced868126ab962b0b1a627ddafe`；
`closeout-a001.json` 同为 `VERIFIED`，SHA-256
`e839073a0f20942141147045db541050cc7aad58be91a1459d58835e081d863f`。
只有 detached receipt 与 closeout 明确给出
`upper_bound_update_authorized=true`，授权把 research upper ledger 更新为
`U=(1188,18)`；`L=absent`、`production_certified=false`。

旧 R4 receipt 的历史字节与 proof graph 仍是 SMM4 的只读输入，但旧 R4 的
full replay 绑定原 checkout HEAD；当前该 checkout 已发生 repository identity
drift。因此 SMM4 不从旧 live path 运行旧 replay，而是把 receipt、manifest、
完整 formal 成员、A004 admission 和 strict instance 快照到 fresh root，再由
snapshot-only adapter 关闭哈希图、独立重建旧 `2084`-selector/`2192`-constraint
模型，并从 retained FD 重放 VeriPB。adapter 自身始终
`upper_bound_update_authorized=false`。

组合门通过时只表示下面这条有限连接成立：

```text
old U=(1188,22) 的完整 2084-orientation lex-better band 为 UNSAT
⊔ SMM-209 admitted delta {(22,54),(54,22)} 的 2-selector OPB 为 UNSAT
= 候选 U=(1188,18) 的完整 2086-orientation lex-better band 被覆盖
```

这不是 attainability、global optimality、whole-instance infeasibility、lower
bound 或 production `CERTIFIED`。composition、old-upper adapter、formal
admission、selection、内层 proof receipt、resource 与 terminal/cleanup 记录均为
`upper_bound_update_authorized=false`。unit 清理后的独立 detached verifier
完成第二轮 VeriPB 及 absence replay，最终 detached receipt 与 immutable closeout
才给出 `upper_bound_update_authorized=true`。`smm4-formal-a004` 已消费且不得
同编号重试。

## Attempt lifecycle

每个 attempt 的 payload spec 位于 fresh run 的 `preselection-a001/`，与
canonical attempt directory 分离。canonical directory 在 selection 前必须精确
为空；这种状态可续且不消费 attempt，也不落 failure receipt。`selection.json`
是该目录的首个不可变对象和唯一消费边界。

selection 后任何异常都冻结该编号为 no-retry，并尽可能依次固定
`failure-terminal.json`、`failure-cleanup.json`、`attempt-failure.json`，再由
independent verifier 的 `detached-failure` mode 生成
`detached-failure-verification.json`。若 detached failure 未能生成或未验证，
immutable closeout 明确保留预期路径和缺失状态；该缺失不能产生上界授权。

`systemd-run` 与 `systemctl` 均从 authority 钉死的 executable retained FD 经
`/proc/self/fd/<n>` 执行。每次调用同时记录规范绝对路径形式的
`logical_argv`、实际 proc-FD 形式的 `executed_argv`、full7 executable identity
和同 FD 稳定性，并由 resource/terminal/cleanup/detached verifier 复核。

SMM4 没有修改实存的
[SMM3 后续 cut 强制排期](../b1_sidewise_marked_membrane_authority_recovery_20260724/04_cuts_mandatory_schedule.md)。
既有归档路径
`../noncert_cuts_ab16_20260724/04_cuts_mandatory_schedule.md` 在固定 HEAD 中缺失；
这只是 provenance/path gap，也不是 cut 已完成的证据。SMM4 closeout 登记的
下一项强制任务仅为 `AB16_GATE_B_AND_16_ORGANIC_ARMS`。该任务现已进入执行链，
但 A031–A038 均已冻结；A035–A037 只发布 input authority，A038 的 pinned
Gate-A full preflight 以 `FAIL_CLOSED` 结束，尚无 fresh successor、trusted
terminal 或 organic arm。其
当前背景见 [AB16 状态](../noncert_cuts_ab16_20260724/README.md)。SMM4 收口本身
没有执行该任务，也不为任何 AB16 attempt 授权。
