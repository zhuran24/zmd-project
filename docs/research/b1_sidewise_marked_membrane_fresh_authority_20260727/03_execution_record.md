# SMM4 fresh-authority 执行记录

| 字段 | 截止 `2026-07-27` 的记录 |
|---|---|
| 文档性质 | 追加式执行史料 |
| 状态 | `VERIFIED / FORMAL_A004_CONSUMED_NO_RETRY / RESEARCH_UPPER_RECOVERED` |
| 当前账本 | `U=(1188,18)`、`L=absent` |
| fresh authority root | `.artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727/run-20260726T211018Z-SMM4-14a491b/` |
| external authority package ID | `bed3a65a788655b95b445c944292b28fdf6a9f6fce74b27c4f0f8a2617a0622b` |
| synthetic gates | success 与 post-SEAL failure 均完成 detached `PASS`；均不授权账本更新 |
| full preflight | 固定 HEAD `14a491bdbfb9fa05d30b17731ed6e29abc1d2201` 上 exact `PASS` |
| formal selection | `formal-attempt-a004/selection.json` 已唯一创建 |
| `smm4-formal-a004` | 已消费，永久不得重试 |
| detached receipt | `VERIFIED`，SHA-256 `9a590d3e0ba6805dc2c1d6abebe60274e4cc5ced868126ab962b0b1a627ddafe` |
| immutable closeout | `VERIFIED`，SHA-256 `e839073a0f20942141147045db541050cc7aad58be91a1459d58835e081d863f` |
| authority 边界 | 仅 detached receipt 与 closeout 为 `upper_bound_update_authorized=true`；`production_certified=false` |

## 第三个 root 前已固定的设计与历史事实

- SMM4 初始侦察固定隔离 worktree 与基线
  `e03bc98dbb00fb38d941e471c61879c499b33213`；
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

## 2026-07-27 第一次 bootstrap：selection 前 fail-closed

第一次 bootstrap 固定在实现提交
`6c7e7a1d261466a36a9bd7244100d3a2cc6cdf5f`，使用全新 root
`.artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727/run-20260726T191750Z-SMM4-6c7e7a1d/`。
它在 `PRE_RUN_MANAGER_BOOT_AUTHORITY` 阶段写出唯一
`bootstrap-failure-a001.json` 后以 exit 2 停止，错误文本为
`manager epoch privileged attestor identity drifted`。该 root 保持原样冻结，
禁止复用、清理、覆盖或补写。

失败时 `authority-a001/` 为空，没有 sealed authority、external package ID、
synthetic unit、formal selection 或 solver 启动；receipt 明确记录
`formal_smm4_a004_consumed=false`、`upper_bound_update_authorized=false`，
账本仍为 `U=(1188,22)`、`L=absent`。

后续静态审计确认，attestor 的 path、size、SHA-256、mode、device 与 inode
并未漂移。根因是旧 manager helper 固定输出精确 legacy 8 字段
`requested_path/path/size_bytes/mode/mode_octal/sha256/device/inode`，首版 SMM4
却用 full7 字段集合直接比较，因 legacy 记录没有 `link_count` 而误判；同类
schema mismatch 也会阻断 observation busctl。

本实现修订增加共享的 exact legacy identity validator 与
legacy-to-full7 join：先拒绝 legacy 记录的缺字段、额外字段、非 canonical
path、mode 双表示不一致和内容/物理身份漂移，再对 `requested_path` 做前后
两次稳定解析，用 same-FD 读取产生 live full7，并连接 sealed authority
固定的 full7。bootstrap、attempt runner 与 detached verifier 均重算此桥，
而不是绕过或信任 writer 自报。修订后的七个 SMM4 聚焦测试文件共
`226 passed`；Ruff 与 `py_compile` 通过，三份改动核心模块的 mypy 通过。
`verify_smm4_two_stage_v1.py` 仍保留修订前已存在的 33 个动态 narrowing
mypy 报告，本修订没有新增该文件的 mypy 报告。

## 2026-07-27 第二次 bootstrap：synthetic success post-selection fail-closed

修复 manager identity bridge 后的第二个实现提交为
`04215f5be05d9f623faaacd3e015f117b5448d02`。它使用全新 root
`.artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727/run-20260726T193617Z-SMM4-04215f5b/`
成功完成 bootstrap。`authority-a001/` 恰好包含单链接 `authority.json` 与
`SHA256SUMS`，当时的 external package ID 为
`7be7aa80556753723940247622740b43b17e07c4d574b9d3f89701a342fcbb35`；
package self-verification、manager legacy-to-full7 join、旧完整 band replay 与
composition 均通过，但 authority 明确保持旧账本且不授权上界更新。

随后 `synthetic-success-a001` 创建 selection、实际启动 transient unit、写出
payload SEAL 并进入 keeper/preterminal。独立 resource verifier 以
`payload spec: pinned source loader argv mismatch` 写出 `FAIL_CLOSED`，runner
因此执行 post-selection failure 闭包。该 synthetic attempt 已消费且
`retry_authorized=false`，不得用同编号重试。

闭包已写出 `failure-terminal.json`、`failure-cleanup.json`、
`attempt-failure.json` 与 `detached-failure-verification.json`。最后一项为
`VERIFIED_FAIL_CLOSED`，明确
`upper_bound_update_authorized=false`、账本
`U=(1188,22)`/`L=absent`；live replay 证明 transient unit 为 `not-found`、
两个记录 PID 均消失、原 cgroup 消失。formal `smm4-formal-a004` 没有 selection，
仍未消费。第二 root 到此整体冻结；未在其中运行 post-SEAL synthetic gate、
formal admission 或 formal attempt。

根因是 runner 的 pinned source loader 已升级为接收并验证 exact full7 JSON，
而 detached verifier 的独立期望仍是旧 digest-only loader 字节，因而把更强的
正确 argv 错判为漂移。当前修订没有绕过 exact argv gate，而是把 verifier 的
独立常量升级为相同的 full7/stable-stat loader，并增加 runner/verifier loader
逐字节相等、full7 参数和 single-link 语义回归。

随后两轮独立对抗审计又在第三 root 创建前发现并关闭了四类 verifier 缺口：

- detached 先新鲜重算 resource validation，再对 resource receipt 的 exact
  顶层/inputs、manager tool full7、mode、授权位与 type-strict canonical JSON
  validation 做完全联结；生命周期 seed 不再取自 receipt 自报内容；
- verifier 从注册的 synthetic attempt/purpose 独立重建完整 worker CLI，并收紧
  selection schema 与 SMM4 unit namespace；
- launch/preterminal/terminal 三次 `systemctl show` retained stdout 与 raw
  mapping 做 exact field-set join，且 `systemd-run` 必须成功退出；
- success resource/detached 工件必须位于 canonical authority/preselection/
  attempt/state/formal 拓扑。普通 detached 与 formal admission 的两次 synthetic
  replay 使用三个 required、purpose-bound output context，后两者只允许固定
  `success.json` 与 `postseal_failure.json`。

这些修复都补有字段缺失/额外、path/hash/mode/physical identity、bool/int、
argv、stdout/raw、跨 attempt 路径、output context 与授权位漂移的 fail-closed
回归。修订后的七个 SMM4 聚焦测试文件共 `341 passed`；Ruff 与 `py_compile`
通过，runner mypy 通过，detached verifier 仍恰好保留修订前已有的 `33` 个
动态 narrowing 报告，没有新增。这些修复与本记录由同一个 tracked-clean
implementation commit 固定；第三个 fresh root 尚未建立。

## 第三个 root 建立前的挂起状态（历史快照）

以下两段保存第三个 root 建立前的决策边界，不是当前状态。当时没有可续的 fresh
sealed authority/external package ID，也没有 synthetic success、synthetic
post-SEAL failure、formal admission、formal proof、resource/terminal/cleanup
或 detached 成功证据；`(1188,18)` 仍是待采证候选，账本为
`U=(1188,22)`、`L=absent`。第二 root 中已存在的 synthetic selection 只证明
该 synthetic attempt 已消费并完成失败闭包，不是 formal selection 或候选上界证据。

当时固定的终态规则是：只有 formal detached receipt 明确写出
`upper_bound_update_authorized=true` 才能更新 `U=(1188,18)`；否则保持
`U=(1188,22)`。selection 已创建后的失败必须把 `smm4-formal-a004` 记录为
consumed/incomplete，禁止同编号重试；selection 前的精确空 canonical attempt
directory 不构成消费，也不产生 failure receipt。所有分支始终保持
`L=absent`，旧 SMM2/SMM3 失败记录不得改写。

## 2026-07-27 第三个 root：formal one-shot VERIFIED 与 immutable closeout

linked-worktree Git-root guard 修复由 tracked-clean HEAD
`14a491bdbfb9fa05d30b17731ed6e29abc1d2201` 固定。第三个 no-overwrite root 为
`.artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727/run-20260726T211018Z-SMM4-14a491b/`，
external authority package ID 为
`bed3a65a788655b95b445c944292b28fdf6a9f6fce74b27c4f0f8a2617a0622b`。
sealed package、自含 pin、synthetic success、synthetic post-SEAL failure、
两次 admission-time independent detached replay 与 fixed-HEAD full preflight
均通过。两项 synthetic detached receipt 与两份 admission replay 都保持
`upper_bound_update_authorized=false`、`U=(1188,22)`、`L=absent`。

canonical formal admission 以 `formal_attempt_selected=false` 发布。随后唯一一次
formal selection 创建 `formal-attempt-a004/selection.json`，并恰好启动一次
`b1-smm4-formal-a004.service`。`smm4-formal-a004` 自 selection 起永久消费，
不得重试、改号续跑或迁移到新 root。

内层 `formal-a004/internal_formal_receipt.json` 为 `VERIFIED`：RoundingSat
报告 UNSAT，第一轮 VeriPB 报告 `s VERIFIED UNSATISFIABLE`，同一 retained FD
链、old-upper replay 与 composition replay 均通过。该内部 receipt 明确保持
`upper_bound_update_authorized=false`，不是研究账本的授权源。

unit 清理后，独立 verifier 从 pinned formula/proof FD 执行第二轮 VeriPB，
并复核 terminal class `success`、payload exit `0`、unit/cgroup absence 与
`remaining_pids=[]`。最终
`formal-attempt-a004/detached-verification.json` 为 `VERIFIED`，SHA-256 为
`9a590d3e0ba6805dc2c1d6abebe60274e4cc5ced868126ab962b0b1a627ddafe`；
`closeout-a001.json` 同为 `VERIFIED`，SHA-256 为
`e839073a0f20942141147045db541050cc7aad58be91a1459d58835e081d863f`。
只有这两项明确给出 `upper_bound_update_authorized=true`，并把 research upper
ledger 更新为 `U=(1188,18)`；`L=absent`、`production_certified=false`。

该授权连接的范围恰为：旧 `U=(1188,22)` 的完整 `2084`-orientation band、
SMM-209 geometry admission、candidate-old delta 公式与变量映射、方向
`(22,54)`/`(54,22)` 的 2-selector UNSAT，共同覆盖候选
`U=(1188,18)` 的完整 `2086`-orientation band。它只完成 research upper
recovery，不证明 `(1188,18)` attainability、global optimality、
whole-instance infeasibility、任何 lower bound 或 production `CERTIFIED`。

前两个 SMM4 root 及 SMM2/SMM3 的失败记录继续按原字节和原判词保留。closeout
登记的下一项强制任务为 `AB16_GATE_B_AND_16_ORGANIC_ARMS`；本次 SMM4
收口没有执行该任务，也不构成 cut 已完成的证据。
