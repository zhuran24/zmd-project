# `run-20260723T161302Z-SMM2` 执行记录

| 项目 | 记录值 |
|---|---|
| 文档性质 | 不可变工件的执行史料索引 |
| 证据截止 | `2026-07-24` |
| 最终分类 | `FORMAL_AUTHORITY_INCOMPLETE` |
| attempt | `a001_consumed_no_retry` |
| 最终账本 | `U=(1188,22)`，`L=absent` |

本页记录执行顺序；当前结论与 claim 边界以 [README.md](README.md) 为入口。

## 1. Authority 恢复

`resume-a001/authority.json` 以 no-overwrite 方式绑定旧 SMM1 pause、原
`(1188,22)` formal receipt、strict instance、HEAD/status identity 和旧
untracked formal runner。runner 固定为 169,658 B、mode `0644`、SHA-256
`869f6bd6bcab88c73a989a68e288e8ac68eb026e7791e976e2289de7285dd24f`，
并从同一已验证 file descriptor 的字节执行。状态为
`RESUME_AUTHORITY_PASS`。

## 2. 几何漏斗

执行史料分为两代：

- a001：primary `PASS`；independent v1 因 `generic_io` schema 分区错误退出
  `2`。该代没有 admission。
- a002：新 authority 固定历史与 v2 工具；primary、independent、adversarial
  全部 `PASS`；`geometry-admission-a002` 为
  `ADMITTED_FOR_PB_ENCODER`。

新条件把 top-eight entity-max budget 固定为 `19`，得到
`M_in<=85`、`T_in+M_in<=209`，排除 `(22,54)` 与 `(54,22)`。

## 3. PB 与 preflight

build-only 生成 2 variables、3 constraints、1 equality 的 OPB。独立
translation gate 重建全部数学、band 和 constraint multiset，决定
`FORMAL_RUN_AUTHORIZED`。正式 preflight 记录可用空间
`32,599,781,376 B`，高于
`10 GiB + 5,000,000,000 B = 15,737,418,240 B` 的门槛，并固定：

```text
MemoryHigh=37580963840
MemoryMax=41875931136
MemorySwapMax=17179869184
OOMPolicy=continue
KillMode=control-group
SendSIGKILL=yes
single_worker=true
formal_attempt_limit=1
```

## 4. 唯一正式 attempt

`formal_attempt_a001.reservation.json` 在启动前 O_EXCL 创建。launcher 保存的
完整 `systemd_argv` 位于 `launch-a001/launch_receipt.json`；该 argv 以
`systemd-run --user --wait` 启动
`b1-smm-1188-18-formal-a001-20260724.service`，并显式携带上述资源属性。

内部原始结果：

```text
RoundingSat exit_code=0, elapsed=50 ms, status=UNSATISFIABLE
VeriPB 3.0.2 exit_code=0, elapsed=1 ms
VeriPB status=s VERIFIED UNSATISFIABLE
proof size=137 B
proof sha256=48dec7cbb9ee0aebd8bc6f1a34b1e2b4024f85c80159d5fb82207bc6bf0286aa
```

worker 起止两次读取的 unit properties 都与合同一致；memory peak 为
`19,177,472 B`，swap 为 `0`，`memory.events` 的 high/max/oom/oom_kill/
oom_group_kill 均为 `0`。内部 receipt 保持
`upper_bound_update_authorized=false`，等待外层 terminal envelope。

## 5. 失败关闭

`systemd-run` exit `0`，外层看到 `Result=success`、`ExecMainStatus=0`、
`ActiveState=inactive`、`SubState=dead`，且终态 cgroup procs 为空。然而
transient unit 已在完整 terminal query 前卸载；外层得到：

```text
MemoryHigh=infinity
MemoryMax=infinity
MemorySwapMax=infinity
OOMPolicy=""
```

因此 launcher receipt 为 `FAIL_CLOSED`。`closeout-a001/closeout.json`
记录 primary reason
`terminal_resource_properties_unavailable_after_unit_unload`，没有创建
`final-a001`，也没有更新上界。按一次 attempt 合同，本轮未重试。

## 6. 不可变历史边界

本执行记录不授权覆盖或补写 a001。后续若有新任务，必须先建立新的
no-overwrite authority 与 attempt；本轮不自动进入下一候选、Track W、
witness 或其他项目线。
