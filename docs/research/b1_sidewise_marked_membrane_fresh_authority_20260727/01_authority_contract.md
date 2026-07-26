# SMM4 fresh-authority 合同

| 字段 | 当前值 |
|---|---|
| 日期 | `2026-07-27` |
| 状态 | `PRE_RUN_IMPLEMENTATION` |
| 固定基线 | `e03bc98dbb00fb38d941e471c61879c499b33213` |
| 研究账本 | `U=(1188,22)`、`L=absent` |
| 候选输入 | `(1188,18)` |
| 正式 attempt | `smm4-formal-a004`，尚未消费 |

## 权威范围

SMM4 只恢复已经通过内部数学验证的 `(1188,18)` 候选的外层采证链。它不新增
约束、encoder、band、候选或 B1/B2 武器，也不建立 attainability、optimality、
whole-instance infeasibility 或 production `CERTIFIED`。

2026-07-27 owner 指令采用“上界恢复先行”，只允许本轮对既有候选作有限
authority recovery。实存的
[SMM3 后续强制 cut 排期](../b1_sidewise_marked_membrane_authority_recovery_20260724/04_cuts_mandatory_schedule.md)
不作回溯修改。owner 本轮指定的
`../noncert_cuts_ab16_20260724/04_cuts_mandatory_schedule.md` 在固定 HEAD 中
缺失；这是 provenance/path gap，不改变本轮方向，也不能被解释为 cut 已完成。
最新 [AB16 状态](../noncert_cuts_ab16_20260724/README.md)为 Gate A 已 finalized、
Gate B 尚未建立、organic arms `0/16`；结合 owner 当前口径，Gate1 v4 已通过。
SMM4 无论成功或失败，cut 工作都保留为后续强制 backlog。

若实现审计要求改变候选、band、几何条件、变量映射或 OPB 约束，本例外立即失效，
不得创建正式 selection，必须返回 owner 重新判定方向。

## 隔离与不可变输入

实现只在独立 worktree
`/home/zhuran24/zmd-pj-codex-baselines/track-b-b1-smm4-fresh-authority-20260727`
进行。主检出的 dirty 工作树、旧 SMM2/SMM3 run、旧 receipt 和 v1 工具均为只读；
不得覆盖、清理、续号、重写或作为未钉死的 live path 输入。

fresh authority root 必须从已提交且 tracked-clean 的 `SMM4_IMPL_HEAD` 建立，并固定：

- 基线和实现 HEAD、完整工具字节集以及固定 Python、RoundingSat、VeriPB；
- manager executable、boot ID、user-manager DBus owner/PID/starttime 和 systemd epoch；
- resource/time 合同、三把重负载锁、run nonce 与 `smm4-formal-a004`；
- 旧 R4 receipt、toolchain record、raw manifest、formal manifest 的全部 `20`
  个成员、A004 admission、strict instance，以及 SMM-209 admission、SMM2
  formula 和 variable map 的 fresh `O_EXCL` 快照。

`authority-a001/` 是 sealed package，成员集合必须精确为 `authority.json` 与
`SHA256SUMS`。`SHA256SUMS` 必须逐字节封住 `authority.json`，其 SHA-256 作为
`authority_package_id` 从 package 外部传入。该外部 ID 必须在 selection、
payload、formal admission、resource/terminal/cleanup 验证与 detached replay
间保持一致。同步篡改 `authority.json` 和 `SHA256SUMS`、增加第三个成员、替换
目录项、硬链接或 reseal 后继续使用旧 package ID 都必须 fail-closed。历史输入
快照位于同一 fresh no-overwrite run root 的独立 snapshot 目录，由 sealed
authority 逐项引用；bootstrap 后不得再依赖旧 live path。

每项输入 pin 的对象必须精确为：

```json
{
  "identity": {
    "path": "/absolute/canonical/path",
    "size_bytes": 0,
    "sha256": "lowercase-64-hex",
    "mode_octal": "0644",
    "device": 0,
    "inode": 1,
    "link_count": 1
  },
  "content_projection": {
    "path": "/absolute/canonical/path",
    "size_bytes": 0,
    "sha256": "lowercase-64-hex",
    "mode_octal": "0644"
  }
}
```

缺失或额外字段、非规范绝对路径、path/size/hash/mode 漂移，或
device/inode/link-count 不一致都必须 fail-closed。读取与执行使用 `O_NOFOLLOW`
retained FD；selection writer、payload verifier 与 detached verifier 都调用同一
canonical content projection，不得再分别用 7-field 与 4-field 整对象比较。
校验后不得按路径重开，执行的字节必须来自完成 identity join 的同一个 FD。

## Attempt 消费与失败闭包

每个 payload spec 都是 selection 前的确定性输入，固定写入 fresh run 下的
`preselection-a001/<attempt>-payload-spec.json`，不属于 canonical attempt
directory。已存在的 spec 只有在字节完全相同时才可复用；任何差异都
fail-closed。

canonical attempt directory 在 selection 前只允许两种状态：不存在，或是 mode
`0755` 且精确为空的真实目录。进程若在建目录后、写 selection 前中断，这个精确
空目录仍未消费 attempt，可安全续至同一个 `O_EXCL` selection 写入；此阶段不得
在 canonical attempt directory 中落下 failure receipt。任意文件、symlink 或
子目录都会破坏该可续拓扑并 fail-closed。

`selection.json` 必须是 canonical attempt directory 中的首个不可变对象，也是
唯一 attempt 消费边界。它一经 `O_EXCL` 创建，attempt 即为
`SELECTED_CONSUMED`；随后的 epoch 漂移、launch、payload、resource、terminal、
cleanup、detached 或 closeout 异常都不能把 attempt 恢复为未消费，也不能授权
同编号重试。

selection 后的异常进入不可变失败链：

```text
failure-terminal.json
→ failure-cleanup.json
→ attempt-failure.json
→ detached-failure-verification.json（若独立验证完成）
```

前三项分别保留异常时的 unit/SEAL 观察、定向 stop/reset 与
unit/PID/cgroup absence、以及 `attempt_consumed=true`、
`retry_authorized=false` 的最终失败语义。independent verifier 的
`detached-failure` mode 必须重新验证 selection、payload spec、sealed package、
manager/boot epoch、retained-FD command provenance、cleanup absence 和失败账本。
它还必须用自己重新打开并钉死的 `systemctl` FD 复查 unit，并直接复查记录的
PID starttime 与 cgroup 路径；不能只信 runner 写入的 absence 布尔值。
若 detached failure receipt 未能生成或未通过，immutable closeout 必须记录
预期路径与缺失/未验证状态；缺失本身不能被补造为授权。

若 post-selection 故障本身导致 authority/package/tool/epoch 无法重放，runner
仍须对精确预注册 unit 执行 cleanup-only 的 last-resort stop/reset/LoadState：
该路径从固定的 root-owned `systemctl` retained FD 执行，但明确
`authority_bound=false`，只用于降低遗留进程风险，永远不能进入授权 receipt。

## 外部命令的执行 provenance

`systemd-run` 与 `systemctl` 都属于 sealed authority 中按 full7 identity 钉死的
binary。runner 对每次调用只打开一次 executable，校验 retained FD 上的内容与
元数据，并以继承的 `/proc/self/fd/<n>` 执行。receipt 同时保存：

- `logical_argv`：首项为 authority 中的规范绝对路径；
- `executed_argv`：首项为实际执行的 `/proc/self/fd/<n>`；
- executable full7 identity、`transport=retained_proc_self_fd`、
  `executed_from_retained_fd=true` 与执行前后同 FD 稳定性。

resource、terminal、cleanup 与 `detached-failure` verifier 必须验证这两套 argv
之间只有首项 transport 转换，其余参数逐项相同。路径只用于逻辑身份和审计展示，
不能在校验后重新打开并替代 retained FD。

## 旧 `(1188,22)` authority 的 snapshot-only recovery

旧 R4 receipt、proof 和 manifest 字节没有被 SMM4 改写。不能复用的是旧 R4
full replay 对历史 checkout 当前 HEAD 的绑定：原执行绑定的 HEAD 与该 checkout
现在的 HEAD 不同，live replay 会以 `repository_identity_drift` fail-closed。
SMM4 不伪造旧 checkout 状态，也不从历史 JSON 内嵌 path 取文件。

`verify_smm4_old_upper_v1.py` 只接收 fresh authority 中的 `25` 个 snapshot：
receipt、toolchain record、raw manifest、formal manifest 的 `20` 个成员、A004
admission 与 strict instance。adapter 必须：

1. 对全部 snapshot 做 full7/canonical4 join、内容锚定、单链接与 retained-FD
   稳定性检查；
2. 关闭 receipt → toolchain/build record → raw/build manifest → formula/proof
   的完整哈希图，并确认 resource/terminal/cleanup 历史证据；
3. 从 strict instance 独立重建旧完整 `2084`-selector、`2192`-constraint OPB
   及 variable map，并与 snapshot 字节精确比较；
4. 从 retained formula/proof/VeriPB FD 再次验证
   `VERIFIED UNSATISFIABLE`。

PASS 只恢复“在冻结 A004 admitted lemmas 条件下，旧 `U=(1188,22)` 的完整
lex-better band 为 UNSAT”这一局部前件。adapter 输出必须始终为
`upper_bound_update_authorized=false`；它既不重新授权旧 ledger update，也不替代
SMM4 的 composition、formal one-shot 或 detached receipt。

## 组合证明门

SMM4 的 composition/admission 链由两个独立输出组成：snapshot-only old-upper
adapter 提供旧完整 band 前件；`verify_smm4_composition_v1.py` 对 old receipt、
strict instance、SMM-209 admission、delta formula 与 variable map 五项组合输入
使用内置 size/SHA-256/mode 锚。formal admission 必须同时连接这两个输出，并在
detached replay 中重新得到相同结果。整条链必须显式证明：

1. snapshot-only old-upper adapter 已恢复旧 R4 完整 band 前件；历史 receipt
   为 `VERIFIED`、`VERIFIED UNSATISFIABLE`，语义限定为旧完整 lex-better
   band，且 SMM4 adapter 自身不携带新授权；
2. 从 strict instance 的 `70×70` grid 与
   `max_lex_area_min_side/minimum_side=6` 独立枚举旧 band `2084`、candidate band
   `2086`；
3. `candidate = old ⊔ {(22,54),(54,22)}`；
4. SMM-209 geometry admission 对两个方向都成立：`22+54=76`，
   marked/ordinary inside cap 为 `85+124=209`，outside incidence floor 为
   `529`，outside cell floor 为 `133`，故
   `1188+133=1321>1320`；
5. delta formula 的 selector 映射精确为 `x1↔(22,54)`、
   `x2↔(54,22)`，OPB 约束集合精确为
   `x1+x2=1`、`-x1>=0`、`-x2>=0`；RoundingSat proof 与 VeriPB 必须证明这个
   同时覆盖两种 orientation 的 2-selector delta UNSAT。

因此组合结论严格是：

```text
old complete 2084 band UNSAT
and exact delta {(22,54),(54,22)} UNSAT
and old ⊔ delta = candidate complete 2086 band
```

单个 delta OPB 的 UNSAT 不能被表述为 whole-instance infeasibility，也不能跳过
旧完整 band 前件直接推出更强结论。组合门只能输出
`formal_attempt_admitted=true` 与 `upper_bound_update_authorized=false`。最终上界
授权只能来自完成正式 proof、resource/terminal/cleanup 闭包和第二次 VeriPB 后的
detached receipt；`L` 始终为 `absent`。
