# Track B/B1：`22×54` sidewise marked-membrane 严格轮

| 项目 | 当前终态 |
|---|---|
| 文档性质 | 研究轮终态与证据索引 |
| 证据截止 | `2026-07-24` |
| 状态 | **FORMAL_AUTHORITY_INCOMPLETE** |
| 当前 authority run | `.artifacts/track_b_b1_sidewise_marked_membrane_strict_20260724/run-20260723T161302Z-SMM2/` |
| 上界账本 | `U=(1188,22)`，未更新 |
| 下界账本 | `L=absent` |
| claim 层级 | research-only；不是 production `CERTIFIED` |

## 终态

本轮严格证明了 `22×54` 与 `54×22` 两个 ceiling orientations 在既有几何
引理下不可行，并完成了对应 PB 翻译。唯一正式 attempt 的内部
RoundingSat→VeriPB 链返回 `VERIFIED UNSATISFIABLE`，但目标 systemd unit
卸载后，外层 terminal observer 已不能读取原 `MemoryHigh`、`MemoryMax`、
`MemorySwapMax` 与 `OOMPolicy`。因此最终资源 authority 没有闭合。

失败关闭结果是：

```text
attempt = a001_consumed_no_retry
status = FORMAL_AUTHORITY_INCOMPLETE
upper_bound_update_authorized = false
U = (1188,22)
L = absent
```

本轮不建立 `U=(1188,18)`。内部 proof 与 verifier 成功是已保存的研究事实，
不是绕过外层 authority gate 的理由。

## 已建立的几何条件

[01_necessity_proof.md](01_necessity_proof.md) 定义 `T_in` 为 628 个 active
terminal incidences 中进入 body-cell-empty `22×54` 矩形者，`M_in` 为
110 个 marked incidences 中进入该矩形者。strict entity-max census 为：

```text
r=3: 4 entities
r=2: 3 entities
r=1: 89 entities
r=0: 170 entities
top-eight = 3+3+3+3+2+2+2+1 = 19
```

由八个 directed rectangle endpoints、full/partial contact 分账和既有
ordinary membrane：

```text
2*M_in <= 2*(22+54)+19
M_in <= 85
T_in <= 124
T_in+M_in <= 209
```

矩形外 weighted incidences 至少 `529`，每个外部 access cell 至多承载
权重 `4`，故至少需要 `ceil(529/4)=133` 个外部 access cells，而：

```text
22*54 + 133 = 1321 > 1320.
```

这排除 oriented `(22,54)` 与 `(54,22)`。独立 band 枚举重建：

```text
old lex>(1188,22) band: 2084 orientations
candidate lex>(1188,18) band: 2086 orientations
exact delta: {(22,54), (54,22)}
```

`geometry-admission-a002/admission.json` 的决定是
`ADMITTED_FOR_PB_ENCODER`。该 admission 只允许进入本轮 PB 编码，不单独
更新全局上界。

## Authority 与历史

旧 SMM1 bootstrap 和 `PAUSE_FOR_USER_GAME_END.json` 保持不可变。恢复前发现
旧 authority root 中的 formal runner 是 untracked 文件，而旧 SMM1
`authority.json` 没有锁其字节。新 `resume-a001/authority.json` 绑定旧 pause，
并把 runner 固定为：

```text
size = 169658 B
mode = 0644
sha256 = 869f6bd6bcab88c73a989a68e288e8ac68eb026e7791e976e2289de7285dd24f
```

恢复器从同一 `O_NOFOLLOW` file descriptor 读取、哈希并
`compile`/`exec` 已校验字节，不再先读后按路径 import。任一 runner、旧 pause、
strict instance、HEAD 或上游 receipt 漂移都会失败关闭。

`geometry-authority-a001` 与 `recomputations-a001/primary.json` 是不可变执行
史料。a001 的 independent v1 因把 47 个 `generic_io` required instances
误当成 operation-group members 而拒绝输入；它没有形成 geometry admission。
v1 工具保留不变。a002 authority 固定 v1/v2 工具及输入，v2 独立实现只修正
该 strict schema 分区，随后 primary、independent、adversarial 与 admission
四层全部通过。

## PB 与正式 attempt

PB formula 是透明 exactly-one：

```text
* #variable= 2 #constraint= 3
+1 x1 +1 x2 = 1 ;
-1 x1 >= 0 ;
-1 x2 >= 0 ;
```

两个变量分别代表 `(22,54)` 与 `(54,22)`。translation gate 不 import
encoder，独立重推 strict census、`SMM-209`、ceil、tie-break、完整 2086
orientation band、OPB constraint multiset 与 build reseal。

关键字节身份：

| 工件 | SHA-256 |
|---|---|
| resume authority | `24a896999cdea34e3fcde84a1f14be8516f321bbbe3654dd856b1116994b3ca8` |
| geometry admission a002 | `abb67f2334756a22650457b3a066d32b48b7d5f8918406b53f4f4140ec3fbfdc` |
| PB authority | `8dd1d60e3412e84d73c190f726fa862082907cc0e7a64080cb8c7a218296d37e` |
| formula, 283 B | `d4b79cd76c80d23e509ad09b1d2e7fa02fa337049f40459ab803f0fc55a4d865` |
| translation gate | `e2146c2f1e4ded7bb080e7cb29c55d506a16ba778f69a64e492422ca99b8aa67` |
| proof, 137 B | `48dec7cbb9ee0aebd8bc6f1a34b1e2b4024f85c80159d5fb82207bc6bf0286aa` |
| internal formal receipt | `1a68ea4cd896e19787b4c2bcf73bf8e87a216c6c318065a4410e89b9c0eda5fc` |
| launch receipt | `3125e43943ed07aeb68f2b28344206679183fcf8a761540d47bf8f9c0831c98c` |
| terminal closeout | `35f87223990b72cf2d77581f2718603cc8f620b97ce044fc502fc368ecec47b9` |

正式 worker 内部在起止两次都观察到精确的
`35 GiB/39 GiB/16 GiB`、`OOMPolicy=continue`，`memory.events` 无
OOM/kill/limit drift，swap 为零。RoundingSat exit `0` 并给出唯一
`UNSATISFIABLE`；VeriPB 3.0.2 exit `0` 并给出唯一
`s VERIFIED UNSATISFIABLE`。

外层 launcher 也观察到 unit `Result=success`、`ExecMainStatus=0` 与空
cgroup，但此时 transient unit 已卸载，资源字段回退成
`infinity/infinity/infinity/""`。这些值不能证明终态仍绑定启动时的资源合同，
所以 `launch-a001` 为 `FAIL_CLOSED`，且没有生成 `final-a001`。

## Claim 边界

本轮建立：

- `SMM-209` 的纸面必要性、两份独立 strict 复算和对抗准入；
- 两个新增 orientations 与完整 lex band 的独立翻译；
- 指定 OPB 的内部 RoundingSat/VeriPB 机器验证结果；
- 唯一 formal attempt 的诚实 authority-incomplete 终态。

本轮不建立：

- `U=(1188,18)` 或任何更强全局上界；
- witness、attainability 或下界；
- optimality、全问题 infeasibility；
- production `CERTIFIED` 结论；
- 再次 formal attempt 的授权。

任何后续 attempt 都必须由新的独立任务授权，使用新的 no-overwrite run；
不得复用或覆盖 a001。
