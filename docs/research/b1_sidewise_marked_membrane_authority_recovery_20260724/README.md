# SMM3 authority recovery 终态

| 项目 | 当前终态 |
|---|---|
| 截止日期 | `2026-07-24` |
| 文档性质 | 研究级 authority recovery 终态入口 |
| 状态 | `FORMAL_AUTHORITY_INCOMPLETE` |
| 权威 run | `run-20260723T192209Z-SMM3-a003` |
| 固定 HEAD | `398f8725c770f3c36408adebe9448a890ed886fe` |
| 当前上界 | `U=(1188,22)`，未更新 |
| witness 下界 | `L=absent` |
| 下一项强制任务 | `CUTS_GATE1_V4_AUTHORITY_COMPLETION` |

SMM3 已完成 privileged manager attestation、两阶段 synthetic 生命周期验证与
formal admission，但唯一 formal `a002` 在 payload 的 selection replay 处
失败关闭。该 attempt 已消费，不得重跑或补写。没有 RoundingSat、VeriPB 或
proof 工件由本轮产生，因此本目录不建立 `U=(1188,18)`。

## 1. 权威根

当前 recovery authority 位于：

```text
.artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/
  run-20260723T192209Z-SMM3-a003/
```

关键身份：

| 工件 | size | SHA-256 |
|---|---:|---|
| `authority-a001/authority.json` | 30,514 B | `4bfa5711c4f9214e7cb6ad1cd0dc5cb647667f5ced42ebf8d4ea786d3e4833e9` |
| `authority-a001/SHA256SUMS` | 81 B | `ba23501e7af6adb7dbc941065b872e6fcb8c0350ad49a01ef222bde22cf60cae` |
| q-success detached receipt | 29,377 B | `405f9c91ffa973144431999e1cc7df29673175ae7e7a99e3b48c30761a739196` |
| q-postseal-fail detached receipt | 29,497 B | `e7c5d4e64a90ca64766b699edbc1b562634f6792eec5d5a374981597a2628935` |
| `formal-admission-a001.json` | 31,893 B | `21b397aa25477da322a7feadd2353de0bfa557dda324d9ca41054727cdad77b6` |
| formal `selection.json` | 19,714 B | `9603bf3135f8173a9b3c15a59fb5bdf7d7b2d895fa63c839b21406556d33582f` |
| formal `payload-terminal.json` | 20,034 B | `fbd074edbc3e8b4213b0dd78a1074f0898a844724d5fe9a2232a2eae694f2277` |
| formal `attempt-failure.json` | 834 B | `5251e0f8c1f48fe910c8c29e09db2b1f954674dc0ca26b43659e457a1afafc5c` |

这里的 package ID 是 `sha256(SHA256SUMS bytes)`：

```text
ba23501e7af6adb7dbc941065b872e6fcb8c0350ad49a01ef222bde22cf60cae
```

authority 固定的 user manager epoch 为：

```text
boot_id              = 7af1ac9e-b552-412a-84e0-bf8bf2955835
DBus unique owner     = :1.1
manager PID/starttime = 2118 / 3154
manager Version       = 261.1-1-arch
manager executable    = /usr/lib/systemd/systemd
manager executable SHA-256
  = de79adab851d295b6a6d403d03552bf16f0f51642f4f7da07bf0e9c139719953
```

只有固定的 read-only attestor 经 `sudo -n` 读取 manager executable。SMM3
launcher、supervisor、observer、verifier 与 formal payload 均以普通用户运行。

## 2. 已通过的生命周期门

两个 synthetic 都使用真实 transient unit 和完整资源合同：

```text
MemoryHigh    = 37580963840
MemoryMax     = 41875931136
MemorySwapMax = 17179869184
OOMPolicy     = continue
KillMode      = control-group
SendSIGKILL   = yes
```

终态如下：

- `synthetic-success-a001`：resource、release、terminal、cleanup 与 detached
  replay 全部 `PASS`；
- `synthetic-postseal-fail-a001`：payload 在 SEAL 后 exit 7，keeper 与 unit
  terminal 保留该失败，resource、cleanup 与 detached replay 全部 `PASS`；
- `formal-admission-a001.json`：`FORMAL_ADMISSION_PASS`，但仍明确
  `formal_attempt_selected=false`、`upper_bound_update_authorized=false`。

这些结果建立本机 systemd 261.1 上的两阶段采证机制可行性。它们不建立 PB
结论，也不更新上界。

## 3. Formal `a002` 的失败边界

formal selection 已以 `SELECTED_CONSUMED` 创建，随后 payload exit 2，且未写
预注册的：

```text
formal-attempt-a002/formal-a002/internal_formal_receipt.json
```

事后只读 live journal 观察到 payload 输出：

```text
SMM3 selection semantics or argv mismatch
```

该 journal 文本没有进入 no-overwrite run，只作诊断，不能替代 immutable
receipt。不可变工件直接建立的是 payload exit 2、`seal_written=false`、completion
seal 缺失和 attempt failure。另对固定源码与工件的只读静态核对给出一个足以
触发该聚合错误的具体不一致：

- selection 中的 authority identity 含
  `device/inode/link_count/path/size/SHA/mode`；
- formal payload 的同 FD `load_json` identity 只重建
  `path/size/SHA/mode`；
- payload 对这两个对象执行整对象相等比较。

因此该比较为 false。失败发生在 solver 启动前；run 内没有 `formal-a002/`
目录、formula 副本、proof、RoundingSat output 或 VeriPB output。

外层保存了 payload 的双重 wait 终态：

```text
waitid.si_code   = CLD_EXITED
waitid.si_status = 2
waitpid.exit_code = 2
seal_written      = false
```

因为失败发生在 pre-terminal resource envelope 之前，本轮没有可接受的 formal
resource、terminal、cleanup 或 detached proof receipt。事后只读观察到 unit
为 `LoadState=not-found` 且没有相关进程，不能替代缺失的不可变 terminal
authority。

## 4. Claim 边界

本轮建立：

- privileged read-only manager executable attestation 在固定 epoch 可重放；
- q-success 与 q-postseal-fail 的 supervisor/keeper 两阶段协议通过；
- formal admission 前的 authority replay、磁盘门与资源配置/selection
  preflight 通过；
- formal `a002` 已消费且 authority 不完整。

本轮没有建立：

- `U=(1188,18)`；
- 新 witness 或任何 `L`；
- attainability、optimality 或 global infeasibility；
- production `CERTIFIED`；
- cuts 的可信度、效果或 Stage-B promotion。

研究账本保持：

```text
U = (1188,22)
L = absent
```

按照固定排期，SMM3 到此停止。下一项必须回到独立 cuts worktree 执行
[Gate 1 v4 authority completion](04_cuts_mandatory_schedule.md)，不得在本
SMM3 run 重试 formal 或扩展新候选。

## 5. 文件导航

- [Authority 合同](01_authority_contract.md)
- [Supervisor/keeper 两阶段协议](02_two_stage_protocol.md)
- [执行记录](03_execution_record.md)
- [Cuts 强制排期](04_cuts_mandatory_schedule.md)
