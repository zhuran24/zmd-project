# SMM3 authority recovery 合同

| 项目 | 合同值 |
|---|---|
| 合同日期 | `2026-07-24` |
| 文档性质 | 实施与验收合同，不是执行结果 |
| 研究轮 | SMM3 sidewise marked-membrane authority recovery |
| 固定 HEAD | `398f8725c770f3c36408adebe9448a890ed886fe` |
| 当前账本入口 | `U=(1188,22)`，`L=absent` |
| SMM3 候选更新 | 仅在全部 authority 门通过后允许 `U=(1188,18)` |
| claim 层级 | research-only；不建立 production `CERTIFIED` |

## 1. 目的与不可变历史

SMM3 是一次有界的 formal authority recovery。它不重新论证已经通过的
SMM-209 几何与 PB authority 边界，也不覆盖 SMM2 工件。

SMM2 `run-20260723T161302Z-SMM2` 的唯一正式 attempt 已固定为：

```text
attempt = a001_consumed_no_retry
status = FORMAL_AUTHORITY_INCOMPLETE
upper_bound_update_authorized = false
U = (1188,22)
L = absent
```

`a001` 的 formula、proof、内部 receipt、launch receipt 和 incomplete closeout
都是不可变历史。旧 proof 和旧 terminal 字段不得成为 SMM3 formal claim 的
替代输入，也不得补写为新的 authority。

SMM3 只有一个正式 attempt：`a002`。创建 `a002` selection 即消费该 attempt；
selection 创建后的 launch failure、payload failure、timeout、OOM、proof cap、
manager epoch 漂移、UNKNOWN、SAT、VeriPB failure、terminal authority 缺口或
cleanup 缺口都不得重试。

## 2. No-overwrite authority root

每次 SMM3 实施必须建立新的 no-overwrite run：

```text
.artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/
  run-<UTC>-SMM3/
```

在任何 transient unit 出现前，以 `O_EXCL` 建立 pre-run authority package。
所有权威输入必须通过同一个 `O_NOFOLLOW` file descriptor 完成读取、哈希和
前后 `fstat`。普通文件至少固定：

- absolute path；
- size；
- mode；
- SHA-256；
- 读取前后的 device、inode、link count、mtime、ctime 稳定性。

禁止先按路径取 identity、再重新按路径读取 payload。需要执行的 Python 源码
必须从已验证的同一份字节执行，或先以 `O_EXCL` 固化到本 run 后按固定哈希
执行；不得在 identity 检查后重新 import 原路径。

authority package 至少固定：

- HEAD 与 dirty-status identity；
- SMM1 pause、SMM2 resume authority、SMM2 incomplete closeout；
- strict instance；
- geometry authority 与 `geometry-admission-a002`；
- PB authority；
- build-only 的 formula、variable map、metadata、build record、estimate 和
  `SHA256SUMS`；
- translation gate；
- fixed Python、RoundingSat、VeriPB；
- `systemd-run`、`systemctl` 和 `/usr/bin/busctl`；
- manager epoch probe、privileged manager executable attestor；
- supervisor/keeper、formal payload、observer、resource verifier、terminal
  closer 与 detached replay 工具；
- run nonce、purpose、unit naming rule、attempt ordinal；
- resource、proof、time 和 cleanup 合同。

Git snapshot只排除本轮`.artifacts`子树以及终态入口`README.md`和执行史料
`03_execution_record.md`。后两者必须在run结束后绑定实际工件，不能成为
pre-run执行输入；所有可执行研究工具仍逐文件进入authority的path/size/mode/
SHA/device/inode闭包。

历史 formula 的允许身份只有：

```text
size = 283 B
sha256 = d4b79cd76c80d23e509ad09b1d2e7fa02fa337049f40459ab803f0fc55a4d865
```

SMM3 可以在 synthetic gate 通过后复制这些已验收输入，但复制必须逐字一致且
进入新 run。旧 proof、旧 internal receipt 和旧 launch receipt不得复制成
`a002` 的证明结果。

## 3. Manager/boot epoch

`systemd-run` 与 `systemctl` 只是客户端。真正执行 transient-unit 和 cgroup
状态机的是当前 user manager，因此 manager/boot epoch 是 authority 的一部分。

规范 identity 为：

```text
boot_id
+ DBus unique owner
+ manager PID
+ PID starttime
+ manager executable path/size/mode/SHA-256
+ manager Version
+ manager Features
```

普通用户进程通过 user bus 对 `org.freedesktop.systemd1` 执行：

1. `GetNameOwner`，取得 DBus unique owner；
2. `GetConnectionUnixProcessID`，取得 manager PID；
3. 读取 `/proc/<pid>/stat` 的 starttime；
4. 从同一 DBus owner 读取 `Version` 和 `Features`；
5. 读取 `/proc/sys/kernel/random/boot_id`。

`/proc` scalar 可能报告 `st_size=0`。读取必须使用同一 fd、有界读和前后身份
复核，不得把 `st_size=0` 解释为空内容。

### 3.1 唯一 privileged 操作

普通用户现场不能可信读取 `/proc/<manager-pid>/exe` 时，只允许固定的
privileged attestor 经以下形态运行：

```text
sudo -n -- /usr/bin/python3.14 -I -c <fixed-read-only-loader> <read-only arguments>
```

loader 从 stdin 接收 pre-run authority 已钉住且通过 AST 职责审计的 attestor
原始字节；attestor 不以路径重新 import。`sudo`、`/usr/bin/python3.14`、
loader、attestor 与 `/usr/bin/busctl` 的 path/size/mode/SHA/device/inode 均在
调用前后重验。privileged attestor 的权限仅用于只读取得 manager executable
字节身份：

1. 接收普通用户已取得的 manager PID 与 expected starttime；
2. 读取 `/proc/<pid>/exe` 的原始 target，拒绝相对路径、`(deleted)` 和
   不稳定 target；
3. 以 `O_RDONLY|O_NOFOLLOW` 打开 target 对应的实际 executable；
4. 在同一 fd 上执行读取、SHA-256、前后 `fstat`；
5. 在取证前后重验 PID starttime；
6. 只向 stdout 输出 strict JSON receipt。

attestor 不得：

- 写文件或写 `/proc`；
- signal、ptrace、stop、restart 或 reconfigure manager；
- 创建、停止或 reset unit；
- 修改 cgroup；
- 运行 solver；
- 以 root 身份创建研究工件。

attestor 本身、固定解释器、`sudo` 客户端及完整 argv/stdin identity 必须由
pre-run authority package 固定。
`sudo -n` 不能立即取得既有非交互凭据时，epoch 取证失败关闭；不得提示输入
密码，也不得用 `/proc/<pid>/cmdline`、systemd 客户端字节或 package manager
记录代替 manager executable 字节。

除这一次只读 attestation 外，authority publisher、synthetic、formal payload、
observer、keeper、resource verifier、terminal closer、cleanup 和 detached
replay 全部以普通用户身份运行。

### 3.2 Epoch 贯穿规则

以下阶段都必须重建并逐字段匹配同一 manager/boot epoch：

- pre-run authority package；
- 每个 synthetic selection 前后及 launch；
- 每个 synthetic pre-terminal、terminal、cleanup 和 detached replay；
- formal `a002` selection 前后及 launch；
- formal pre-terminal、terminal、cleanup 和 detached replay。

每个 unit 的 `InvocationID` 只锚定该 unit，不能替代 manager epoch。

漂移语义：

- synthetic success、post-SEAL failure 和 formal 不在同一 epoch：
  synthetic 不得授权 formal；
- `a002` selection 创建前漂移：本 run fail-closed，不创建且不消费 `a002`；
- selection 创建后漂移：`a002` 已消费，终态只能是
  `FORMAL_AUTHORITY_INCOMPLETE`；
- detached replay 不能复现原 epoch：关闭 formal claim。

## 4. `a002` selection 合同

formal selection 必须是 authority package 之外的单独 `O_EXCL` 文件，schema
为 `b1_sidewise_smm3_attempt_selection_v1`，至少绑定：

- `attempt=a002`；
- authority package 的完整 identity；
- run nonce、purpose 与唯一 unit name；
- selection 前的 manager/boot epoch；
- exact worker argv；
- fixed Python、supervisor/keeper 和 payload identity；
- formula/build inputs；
-完整 resource 与 time contract；
- `upper_bound_update_authorized=false`。

selection 创建顺序固定为：

1. 重验全部 pre-run authority；
2. 重验 synthetic gates；
3. 重验 manager/boot epoch；
4. 重验 disk、single-worker 和无其他 prod-scale solver；
5. 证明 selection 尚不存在；
6. `O_EXCL` 创建 selection；
7. 立即重验同一 manager/boot epoch；
8. 才允许 launch。

selection 前的任何失败不消费 `a002`。第 6 步完成后的任何失败都消费 `a002`。

## 5. 固定资源与时间合同

formal transient unit 必须固定：

```text
MemoryHigh     = 37580963840
MemoryMax      = 41875931136
MemorySwapMax  = 17179869184
OOMPolicy      = continue
KillMode       = control-group
SendSIGKILL    = yes
single_worker  = true
```

磁盘与时间门：

```text
proof cap                         = 5000000000 B
artifact low-water                = 10 GiB
required free before formal       = 15737418240 B
RoundingSat internal limit        = 3600 s
RoundingSat outer monitor         = 3900 s
VeriPB limit                      = 3600 s
formal transient RuntimeMaxSec    = 9000 s
formal payload wait               = 8000 s
formal keeper release wait        = 8700 s
synthetic transient RuntimeMaxSec = 120 s
synthetic payload wait            = 30 s
synthetic keeper release wait     = 90 s
```

资源字段缺失、类型错误、limit drift、OOM、kill、额外 descendant、proof cap、
低水位或超时都失败关闭。

## 6. Claim 边界

SMM3 只有在以下事实同时成立时才允许 research ledger 更新：

- synthetic success 与 post-SEAL failure 全部通过；
- formal selection 是唯一 `a002`；
- RoundingSat 给出唯一 `UNSATISFIABLE`；
- unit 内 VeriPB 给出唯一 `s VERIFIED UNSATISFIABLE`；
- supervisor/keeper、pre-terminal resource、terminal 与 cleanup authority
  全部通过；
- detached closer 第二次运行 VeriPB 并得到相同验证语义；
- manager/boot epoch 从 authority package 到 detached replay 一致。

成功终态：

```text
status = VERIFIED
U = (1188,18)
L = absent
```

任一门失败：

```text
status = FORMAL_AUTHORITY_INCOMPLETE
U = (1188,22)
L = absent
```

两个终态都不建立 witness、attainability、optimality、global infeasibility 或
production `CERTIFIED`。

SMM3 terminal acceptance 后的下一项强制任务由
[04_cuts_mandatory_schedule.md](04_cuts_mandatory_schedule.md) 固定；该任务
不属于 SMM3 run。
