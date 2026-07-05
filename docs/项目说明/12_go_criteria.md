# 12 — 当前 GO / close 标准

> 基线：2026-06-26 工作树。本文不把历史测试数字、review receipt 或结构 checker 的 PASS
> 升格为 release certification。机器状态以 `data/review_gates/phase_1_2_spike_close.json` 为准。

## 12.1 状态词

- **IMPLEMENTED**：代码路径已存在，并有相应测试或结构义务。
- **VERIFIED IN THIS WORKTREE**：列明命令在当前 bytes 上实际完成且通过。
- **OWNER-CLOSED**：owner gate 显式记录关闭。
- **P1.2 CLOSED**：技术边界、要求的验证、包材边界与 owner gate 同时满足。
- **SUPERVISOR OPERABLE**：存在受支持、可审计的生产 supervisor invocation surface；当前不成立。
  （2026-07-05 注：本行"当前不成立"基于 2026-06-26 基线。生产入口
  `scripts/run_supervisor_seal.py` 已于 2026-07-04 落地——"invocation surface
  存在"这一机器条件已补；但 OPERABLE 与 P1.2 closed 的判定关系以
  `PROJECT_LOCK.md` 口径为准：入口存在只补机器条件、不打开 owner 门、
  不推导 P1.2 closed。）

这些词不能互换。当前状态是 **P1.2 OPEN/BLOCKED**。

## 12.2 技术 close 必要条件

P1.2 close 至少要求：

1. producer 只提交 `CANDIDATE_PROPOSED`，无旁路 durable/public `CERTIFIED` mint；
2. supervisor 从 canonical disk authority 重读并验证 proposal、sink replay、terminal frontier、
   fixed witness、current hashes 与 pre/post disk state；
3. whole-layout proof-bearing elimination 通过独立 reverify；
4. canonical public writer 只有 central verified publisher，且失败清理三件套；
5. public surface 绑定同一 sealed campaign、两份 payload、manifest 与 file hashes；
6. P1.2 publish-open gate 只有 owner 明确关闭时才通过；
7. proof-obligation/allowlist/checker 对当前工作树重新封存并通过；
8. owner 要求的 targeted/full/slow 验证在同一工作树实际完成，日志不混用历史结果；
9. review snapshot 从 resolved immutable commit 物化，并满足发布/归档策略；
10. PR2 规定的 controlled-loader/read-once/TCB 收缩完成，或 owner 明确修改 close scope。

当前 1–6 的主要 PR1 实现已在工作树落地；7 需在本次文本/source reseal 后重跑；8–10
尚不能写成满足。

## 12.3 Machine gate 的正确解释

`scripts/check_p1_2_proof_obligations.py` PASS 只表示当前登记的 obligation、sink、hash、guard
与 close-kernel contract 一致。它不是全程序 theorem prover，也不证明 full pytest、人工审查
或 owner close。

`check_strong_status_write_allowlist.py` PASS 表示扫描到的强状态/写入点均有登记理由；它不证明
扫描范围外绝无 writer，也不允许把“allowlisted”解释成“soundness 已证明”。

`check_phase_review_gate.py` 在 gate blocked 时仍应 PASS，因为它验证的是 fail-closed 状态
一致性。只有 `--require-ready` 且 owner-closed 才能作为下一阶段入口检查。

## 12.4 测试报告规则

当前 collect-only 盘点为 **425 个测试文件、3450 个测试**。这是收集结果，不是通过结果。
任何 pass 数必须附：命令、工作树标识、退出码与日志。历史 189、442、2211、3316 等数字
只属于各自时间点，不能描述当前全套状态。

本轮已知完成的局部结果应在最终变更报告中逐项列出；超时或未运行的组合必须明确写为
“未完成”，不能用已出现的绿点外推。

## 12.5 Review 与 owner gate

外部 reviewer 可发现技术 finding，但 review receipt、clean 计数与 package seal 不会自动修改
owner gate。反过来，owner gate 关闭也不能掩盖未修复的 false-CERTIFIED / false-INFEASIBLE
路径。

当前 gate：

```text
status = blocked_manual_review_count
p1_3b_entry_allowed = false
```

`p1_3b_*` 是机器兼容字段；面向人的后续阶段名称统一写 **P1.3**。

## 12.6 后续 P1.3 GO

P1.3 的 Step 8/cut-family production master integration 只有在 P1.2 close 后才能进入。它必须
单独证明 attach 语义、replay/currentness、性能与 rollback，不得把当前未接入的 F1–F9 写成
默认 certified path 已使用。
