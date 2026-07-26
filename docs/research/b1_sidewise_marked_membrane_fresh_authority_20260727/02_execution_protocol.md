# SMM4 执行协议

| 字段 | 当前值 |
|---|---|
| 日期 | `2026-07-27` |
| 状态 | `PRE_RUN_IMPLEMENTATION` |
| 当前账本 | `U=(1188,22)`、`L=absent` |
| 正式选择 | 尚未创建 |

## 1. 实现冻结

1. 在 SMM4 独立 worktree 完成 identity contract、组合门、two-stage runner、
   snapshot-only old-upper adapter、formal payload、独立 verifier 和聚焦回归。
2. 运行聚焦 pytest、目标 Ruff/mypy/语法检查。此阶段不得启动 formal。
3. 提交实现并记录 tracked-clean `SMM4_IMPL_HEAD`；未提交或 dirty 实现不得进入
   authority。

## 2. Fresh authority 与 synthetic gates

1. 在全新 no-overwrite root 中，以 retained FD 从旧只读根校验历史哈希，并
   `O_EXCL` 快照旧 R4 的 `25` 项闭包和 SMM2 composition 输入。其后所有阶段
   只读 fresh snapshot；禁止跟随历史 JSON 中的 path 或访问旧 live run。
2. 固定实现、工具、binary、manager/boot/systemd epoch、资源合同、锁和 nonce；
   建立成员集合仅为 `authority.json` 与 `SHA256SUMS` 的 `authority-a001/`。
   将 SHA-256(`SHA256SUMS`) 作为 package 外保存的
   `authority_package_id`，并在每个后续阶段校验 sealed package。
3. 从 snapshot-only adapter 重放旧 R4 完整 band，独立重建旧 OPB/map，并通过
   retained-FD VeriPB；该阶段保持 `upper_bound_update_authorized=false`。
4. 在 fresh run 的 `preselection-a001/` 写入每个 attempt 的 immutable payload
   spec。spec 在 canonical attempt directory 之外；已存在时只能复用完全相同的
   字节。随后创建或复用精确为空、mode `0755` 且非 symlink 的 canonical
   attempt directory。
5. 以 `O_EXCL` 写入 canonical attempt directory 的 `selection.json`。它必须是
   该目录的首个不可变对象，也是唯一消费点；selection 之前的精确空目录可续，
   且不得产生 failure receipt。
6. 完成 synthetic success：selection、SEAL、keeper、preterminal resource、
   release、terminal、cleanup 与 detached replay 全部通过。
7. 完成 synthetic post-SEAL exit-7：失败必须被 terminal/cleanup 与 detached
   replay 保留，且不得误分类为成功。
8. composition gate 在 fresh authority、formal admission 和 detached 阶段都
   重放旧 `2084` band、SMM-209、delta formula 和两个 orientations 的同一证据
   闭包。
9. formal admission 只有在两项 synthetic detached replay、composition、epoch、
   disk/process/lock gate 全部通过后发布；发布时
   `formal_attempt_selected=false`、`upper_bound_update_authorized=false`。

任一 synthetic receipt 都不得授权上界更新。post-SEAL gate 的目的不是制造一个
可忽略错误，而是证明 payload 已写 SEAL 后仍能由 keeper、terminal、cleanup 与
detached replay 准确分类失败。

所有 `systemd-run` launch，以及 launch/resource/terminal/cleanup/absence 使用的
`systemctl` 调用，都从 authority 钉死的 executable retained FD 经
`/proc/self/fd/<n>` 执行。记录必须同时保留规范路径开头的 `logical_argv` 和
实际 proc-FD 开头的 `executed_argv`，并固定 executable identity、transport 与
同 FD 执行前后稳定性；独立 verifier 对这些 provenance 字段逐项复核。

## 3. 资源报备与正式 one-shot

full preflight 启动前报告当前 load、MemAvailable、SwapFree、磁盘空间与重负载锁，
以及以下预计资源，等待监督线程明确放行：

- 最多约 24 logical cores；
- RAM 约 12–24 GiB；
- I/O 约 2–6 GiB；
- 时长约 5–20 分钟。

正式 attempt 启动前必须重新报备并另行获批：

- 单 worker，RoundingSat 与 VeriPB 顺序执行；
- `MemoryHigh=35 GiB`、`MemoryMax=39 GiB`、`MemorySwapMax=16 GiB`；
- proof cap 5 GB，启动前可用空间至少 `15,737,418,240` bytes；
- 预计 5–30 分钟；formal 硬上限 9000 秒，detached VeriPB 最多另 3600 秒。

获批后且 selection 前，以 nonblocking flock 同时取得：

```text
/tmp/zmd-pj-codex-heavy-validation.lock
/run/user/$UID/zmd_pj_prod_scale_solver.lock
/run/user/$UID/zmd-pj-prod-scale-solve.lock
```

任一锁忙、发现游戏或其他重负载、epoch 漂移或资源条件不足时，不创建 selection。
放行依据变化后必须重新报备。

formal payload spec 固定在
`<fresh-run>/preselection-a001/formal-attempt-a004-payload-spec.json`。canonical
attempt directory 是 `<fresh-run>/formal-attempt-a004/`；在
`selection.json` 出现前，该目录只有精确为空时才可续。selection 前 gate、epoch
或资源检查失败不写 canonical failure 对象，不消费 attempt，也不得伪称 attempt
已启动。

`O_EXCL` 创建 `formal-attempt-a004/selection.json` 是唯一的正式消费点和该目录
中的首个不可变对象。正式流程只允许一次 selection 创建和一次 solver 启动；
selection 后任何失败都冻结该编号为 incomplete，不得同编号重试、改号续跑或
重写历史。

## 4. Formal、detached 与收口

formal payload 从 retained FD 执行钉死的工具，重放 composition，运行
RoundingSat 和第一次 VeriPB。loader、formula、proof 与 executable 的 identity
校验和实际读取/执行必须使用同一 retained FD；禁止校验路径 A 后从路径 B 或同一路径
重新打开。内层 receipt 即使成功也保持 `upper_bound_update_authorized=false`。

keeper 在 transient unit 仍存在时保留并采集资源字段；独立 resource verifier
通过后才 release。随后固定 terminal 与 cleanup/absence。

detached verifier 在 unit 清理后重新检查完整 epoch、identity、composition、
sealed authority/package ID、resource、terminal 和 cleanup，并从 pinned FD 第二次
运行 VeriPB。只有 formal detached receipt 可以写
`upper_bound_update_authorized=true`；synthetic、内部 formal、失败或 incomplete
receipt 均不得授权。

### 成功收口

```text
formal detached receipt 明确 upper_bound_update_authorized=true
→ immutable closeout
→ SMM4 execution record/README
→ docs/项目说明/06_current_status.md（U=(1188,18)，L=absent）
→ docs/项目说明/00_master_roadmap.md 的新增日期记录
```

这一路径也不得写 attainability、optimality、whole-instance infeasibility 或
production `CERTIFIED`，不得触碰 production cut wiring、P1.2 seal、B6、witness
或 AB16 工件。

### 失败收口

selection 后任意异常都进入同一 no-retry 路径。runner 追加或只读复用精确字节的
`failure-terminal.json`、`failure-cleanup.json` 与 `attempt-failure.json`：

- `failure-terminal.json` 保留异常类型、SEAL 是否已经出现、已知
  PID/cgroup 和 cleanup 前的 systemd 状态；
- `failure-cleanup.json` 保留仅针对预注册 unit 的 stop/reset、LoadState、
  PID starttime、remaining PID 与 cgroup absence；
- `attempt-failure.json` 固定 `selection_created=true`、
  `attempt_consumed=true`、`retry_authorized=false`，并命名预期的
  `detached-failure-verification.json` 路径。

随后 independent verifier 以 `detached-failure` mode 重验 selection、payload
spec、sealed package/package ID、epoch、上述 retained-FD `systemctl`
logical/executed argv provenance、cleanup absence 和失败账本；并以独立
retained-FD `systemctl` 调用及直接 PID/cgroup 检查重做 live absence replay，
而非接受记录中的布尔值。通过时生成
`detached-failure-verification.json`，状态为 `VERIFIED_FAIL_CLOSED`，仍明确
`upper_bound_update_authorized=false`。若该 receipt 未能生成或未通过，closeout
必须明确记录预期路径和缺失/未验证状态，不得补造授权。

如果 authority/package/tool/epoch 重放本身失败，普通证据链可能无法继续；
此时只允许对精确预注册 unit 运行 retained-FD、root-owned `systemctl` 的
last-resort stop/reset/LoadState。该记录必须标为 `authority_bound=false`、
cleanup-only，不能充当 detached authority。

写入顺序为：

```text
failure-terminal/failure-cleanup/attempt-failure
→ 真实 detached-failure，或其明确缺失/未验证状态
→ immutable incomplete closeout
→ SMM4 execution record/README
→ docs/项目说明/06_current_status.md（仍为 U=(1188,22)，L=absent）
→ docs/项目说明/00_master_roadmap.md 的新增日期记录
```

失败分支把 `smm4-formal-a004` 冻结为 consumed/incomplete，禁止同编号重试。成功
和失败分支都只追加 SMM4 新记录，不改写 SMM2/SMM3、旧 R4 或实存的
[SMM3 后续 cut 强制排期](../b1_sidewise_marked_membrane_authority_recovery_20260724/04_cuts_mandatory_schedule.md)。
owner 指定的
`../noncert_cuts_ab16_20260724/04_cuts_mandatory_schedule.md` 在固定 HEAD 中
缺失；该 provenance/path gap 不改变 SMM4 方向，也不表示 cut 已完成。最新
[AB16 状态](../noncert_cuts_ab16_20260724/README.md)为 Gate A 已 finalized、
Gate B 未建、organic arms `0/16`；结合 owner 当前口径，Gate1 v4 已过，cut
仍是后续强制 backlog。
