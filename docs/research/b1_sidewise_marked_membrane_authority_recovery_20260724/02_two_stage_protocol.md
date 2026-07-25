# SMM3 supervisor/keeper 两阶段协议

| 项目 | 合同值 |
|---|---|
| 合同日期 | `2026-07-24` |
| 文档性质 | 生命周期、采证与验收合同，不是执行结果 |
| payload 类型 | synthetic success、synthetic post-SEAL failure、formal `a002` |
| unit main process | supervisor，payload 是其唯一工作子进程 |
| terminal authority | unit 外 observer 与 detached closer |

本协议与 [01_authority_contract.md](01_authority_contract.md) 共同构成 SMM3
authority。内部 solver receipt、unit terminal 状态和 cleanup 缺一不可。

## 1. 角色分离

### Supervisor

- 是 transient unit 的 main process；
- 创建唯一 payload 子进程；
- payload 在 start token 出现前保持阻塞；
- 是 payload 的唯一 reaper；
- 保存原始退出状态；
- payload 回收后转为唯一 keeper；
- 不判定资源合规，不发布最终 research claim。

### Payload

- synthetic 模式只执行指定 fixture；
- formal 模式只执行 translation replay、RoundingSat、VeriPB 和内层 SEAL；
- 不创建 terminal 或 cleanup authority；
- internal receipt 始终保持
  `upper_bound_update_authorized=false` 与
  `awaiting_terminal_envelope=true`。

### Unit 外 observer

- 固定 `unit_name + run_nonce + InvocationID + manager_epoch`；
- 验证 supervisor、payload 和 keeper 的 cgroup membership；
- 创建 start token；
- 在 keeper 存活时取得 pre-terminal 原始证据；
- 在 release 后取得 terminal 与 cleanup 原始证据；
- 不复用 payload 自报值作为独立资源结论。

### Independent resource verifier

- 不 import observer；
- 只从 authority package 与保存的 raw bytes 推导；
- 是创建 release token 的唯一授权门；
- 不判定 solver 的数学语义。

### Detached closer

- unit 生命周期结束后独立重放全部 receipt；
- 第二次运行 VeriPB；
- 只在所有 gate 通过后更新 research ledger。

## 2. 固定生命周期

每个 synthetic 或 formal unit 按以下顺序执行：

1. 外部 launcher 在 selection 已建立后启动 supervisor。
2. supervisor 创建 payload，payload 在 start token 前阻塞。
3. observer取得 unit `InvocationID`，重验 manager/boot epoch。
4. observer验证 supervisor 与 payload 同处目标受限 cgroup。
5. observer验证启动资源属性与 selection 完全一致。
6. observer以 `O_EXCL` 创建 start token。
7. payload开始执行并写入其 no-overwrite outputs。
8. payload写完内层 SEAL 后退出。
9. supervisor以 `waitid(..., WNOWAIT)` 保存原始 `siginfo`。
10. supervisor以 `waitpid` 回收 payload。
11. supervisor写入不可变 payload-exit receipt，并转为唯一 keeper。
12. observer在 cgroup 仍存在时取得 pre-terminal snapshot。
13. independent resource verifier重放 raw snapshot。
14. verifier PASS 后，observer才以 `O_EXCL` 创建 release token。
15. keeper从同一 fd 验证 release token。
16. keeper将 payload退出状态精确映射为自身退出状态。
17. observer取得 systemd terminal envelope。
18. observer执行限定于本 nonce/unit 的 stop/reset。
19. observer独立证明无残留 unit、PID 或 cgroup。
20. detached closer执行最终 replay。

start、SEAL、payload-exit、resource verdict 与 release token 都是单调、
no-overwrite 状态。任何 token 缺失、重复、symlink、identity drift 或时序倒置
都失败关闭。

## 3. 退出状态保持

supervisor不得把 payload failure 掩盖为成功。

固定映射：

- `CLD_EXITED`：keeper以相同 exit code退出；
- `CLD_KILLED`：keeper以相同 signal终止；
- `CLD_DUMPED`：keeper以相同 signal终止，并保留 dumped 分类；
- 任何无法无歧义映射的状态：fail-closed。

payload-exit receipt 至少保存：

- `waitid` 的 `si_code`、`si_status`、PID；
- `waitpid` 的 raw wait status；
- payload SEAL identity；
- supervisor/keeper PID 与 starttime；
- selection、InvocationID 和 manager epoch identity；
- payload output manifest。

keeper阶段不得生成新子进程，不得改写 payload receipt，不得把 post-SEAL
exit 7改成 exit 0。

## 4. Pre-terminal resource envelope

keeper存活时，observer必须在同一阶段保存一次完整 raw `systemctl show` 和
cgroup v2文件。该阶段必须证明：

- manager/boot epoch 与 launch 一致；
- unit为 `active/running`；
- `MainPID` 等于 keeper PID；
- `InvocationID` 与 launch 一致；
- payload已经退出且被 supervisor回收；
- `cgroup.procs` 精确只有 keeper PID；
- `cgroup.events populated=1`；
- `ControlGroup` 指向实际存在的目标 cgroup。

必须保存：

- `memory.high`
- `memory.max`
- `memory.swap.max`
- `memory.current`
- `memory.peak`
- `memory.swap.current`
- `memory.swap.peak`
- `memory.events`
- `memory.events.local`
- `cgroup.events`
- `cgroup.procs`

systemd属性必须为：

```text
MemoryHigh=37580963840
MemoryMax=41875931136
MemorySwapMax=17179869184
OOMPolicy=continue
KillMode=control-group
SendSIGKILL=yes
```

raw files必须以同 fd有界读取、前后 `fstat` 和 SHA-256固定。resource verifier
从 raw bytes独立推导 limits、peak、swap、OOM/kill、payload status、keeper
唯一性和时序。

以下任一情况关闭 release：

- 字段缺失或类型错误；
- limit或unit identity漂移；
- manager epoch或InvocationID漂移；
- OOM、oom_kill、oom_group_kill、非预期 max/high event；
- swap合同不闭合；
- payload未回收；
- keeper之外仍有PID；
- cgroup在snapshot前被prune；
- snapshot之后才补写字段。

## 5. Terminal envelope

release后，observer等待同一 unit、InvocationID和manager epoch到达终态。

synthetic success 与成功 formal 的终态合同：

```text
ActiveState=active
SubState=exited
Result=success
ExecMainCode=CLD_EXITED
ExecMainStatus=0
MainPID=0
```

该终态需要 transient unit 的 remain-after-exit语义，以便 observer在明确
cleanup前保存完整metadata。

synthetic post-SEAL failure：

```text
ActiveState=failed
Result=exit-code
ExecMainCode=CLD_EXITED
ExecMainStatus=7
```

terminal envelope必须保存同一次 raw query，禁止逐字段、跨时间查询后拼接。
terminal阶段重验manager/boot epoch。当前systemd 261.1可以在unit退出后立即
prune空cgroup，因此`ControlGroup=""`是允许的终态；它既不能证明资源合规，
也不能证明cgroup为空或cleanup完成。资源权威只来自keeper仍存活时的
pre-terminal snapshot。

## 6. Cleanup

cleanup是terminal之后的独立阶段：

1. 仅对当前 run nonce与unit执行stop/reset；
2. 保存命令argv、exit status与raw output；
3. 以unit name和InvocationID证明unit不再可运行；
4. 以已记录的supervisor、payload、keeper PID/starttime证明无残留进程；
5. 以pre-terminal记录的实际cgroup路径证明cgroup不存在；
6. 再次重验manager/boot epoch。

空 `ControlGroup`、`MainPID=0` 或 `cgroup.procs=[]` 中任何单一字段都不能替代
cleanup证据。不得搜索、停止或清理其他用户进程和共享服务。

在当前 C locale 的 systemd 261 上，`stop` 后成功 unit 可能已被卸载。
因此 `reset-failed` 的成功证据只接受两种规范结果：exit 0，或 exit 1
且 stderr 逐字等于该 unit 的 `Unit ... not loaded.` 消息；后一分支还必须
与随后独立取得的 `LoadState=not-found` 同时成立。其他非零结果一律关闭。

## 7. Synthetic 强制门

synthetic使用真实 transient unit和完整 `35/39/16 GiB` 合同，但不运行
solver。

### `q-success`

- payload写入内层SEAL；
- payload exit 0；
- supervisor/keeper状态保持正确；
- pre-terminal、terminal、cleanup和detached replay全部PASS。

### `q-postseal-fail`

- payload写入同样的内层SEAL；
- payload exit 7；
- pre-terminal资源采证可以PASS；
- keeper必须映射为exit 7；
- terminal必须记录`failed/exit-code/7`；
- detached closer必须拒绝success分类。

两个synthetic unit统一使用：

```text
RuntimeMaxSec = 120 s
payload wait  = 30 s
keeper wait   = 90 s
```

它们必须与formal处于同一manager/boot epoch。任一synthetic失败或跨epoch时，
formal selection不得创建。

## 8. Formal `a002`

synthetic全绿后，SMM3才允许：

1. 重验SMM2 resume、geometry admission、PB authority和strict instance；
2. 独立重放strict数学与translation gate；
3. 证明formula仍是固定的283 B字节；
4. 重验disk、single-worker和manager epoch；
5. 按[01_authority_contract.md](01_authority_contract.md)创建唯一`a002`
   selection；
6. 通过supervisor/keeper启动formal payload。

formal payload：

- 从authority固定字节建立本run input snapshots；
- 重跑translation verifier；
- 运行RoundingSat，内部limit 3600秒、outer monitor 3900秒、proof cap 5 GB；
- 只接受唯一`UNSATISFIABLE`；
- 运行VeriPB，limit 3600秒；
- 只接受唯一`s VERIFIED UNSATISFIABLE`；
- 写入formula、proof、原始stdout/stderr、manifest和internal receipt；
- 不更新ledger。

formal生命周期统一使用：

```text
RuntimeMaxSec = 9000 s
payload wait  = 8000 s
keeper wait   = 8700 s
```

三项均由pre-run authority的resource contract导出；observer不得自报或放宽。

## 9. Detached replay 与终态

detached closer必须独立验证：

- authority package与`a002` selection；
- manager/boot epoch全阶段一致；
- payload `waitid`/`waitpid`状态；
- pre-terminal resource envelope；
- release token；
- terminal envelope；
- cleanup；
- formula、proof、RoundingSat和VeriPB原始输出；
- unit外第二次VeriPB。

只有全部PASS才建立：

```text
status = VERIFIED
U = (1188,18)
L = absent
```

任何缺口都诚实收口：

```text
status = FORMAL_AUTHORITY_INCOMPLETE
U = (1188,22)
L = absent
```

两个终态的`NEXT_REQUIRED_TASK`都必须是：

```text
CUTS_GATE1_V4_AUTHORITY_COMPLETION
```

cuts不进入SMM3 run；后续严格排期见
[04_cuts_mandatory_schedule.md](04_cuts_mandatory_schedule.md)。
