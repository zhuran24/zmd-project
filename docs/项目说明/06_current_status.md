# 06 — 当前状态

**状态日期：2026-06-26**  
**发布结论：P1.2 OPEN / BLOCKED；P1.3 未开放。**

本页描述当前工作树，不以 Git HEAD 的提交时间替代工作树事实。未提交的 PR1 发布面 soundness 修复
属于当前实现状态。

## 已落地的边界

### 1. producer 只提案

`src/search/outer_search.py:855-954` 的 terminal path 只构造并持久化
`CANDIDATE_PROPOSED`，同时提交 terminal frontier evidence、sink replay request、fixed-witness
material 和 proposal marker。它不再直接铸造 durable terminal `CERTIFIED`。

### 2. supervisor 是唯一 durable terminal mint

`src/search/exact_campaign.py:3399-3593` 的 `ExactCampaign.supervisor_seal()`：

- 从磁盘读取已提交 proposal，而不是信调用者的内存对象；
- 复核 project/source/artifact/campaign/candidate bindings；
- 执行 candidate sink replay 与 fixed-witness capsule；
- 校验 terminal evidence 与发布 witness；
- 写前、写后重新验证 disk authority；
- 只有全部通过才写 terminal `CERTIFIED` seal。

其它路径调用 `mark_campaign_stopped(..., "CERTIFIED")` 会被拒绝。

**未接入项：**仓库没有生产 supervisor CLI/launcher，`main.py` 和 runtime wrappers 都不调用
`supervisor_seal()`；目前实际终点是 proposal-ready 的 `CANDIDATE_PROPOSED`。测试中的直接方法调用不能
替代生产调度面。

### 3. fixed-witness 与 connector/body 复验

`terminal_fixed_witness_capsule.py` 在隔离 Python 子进程中对提案的确切 `π*` 复跑验证，并用
nonce-bound response 返回裁决。`terminal_fixed_witness_verifier.py` 还独立拒绝 connector cell 被
facility body 占用，包括 own-body 和 other-body。自由重解出的“同尺寸另一个可行布局”不能替代发布
witness。

### 4. P1.2 OPEN-GATE 已机器化

`src/search/certified_surface.py:482-531` 从权威 review gate 解析 P1.2 发布状态。缺失、畸形、仍 open
或非显式 owner-closed 的 gate 一律使 public surface `publishable=false`。

### 5. public publisher 单入口

`src/search/certified_surface.py:563-680` 的
`publish_verified_certified_delivery_surface()` 是公开 solution、blueprint 和 delivery manifest 的
唯一 certified publisher。它要求 disk-current supervisor seal，三件输出同源，并在失败时清理部分写入。
外围 serializer、viewer、report、adapter 和 compatibility exporter 已被收拢为非权威派生面。

### 6. whole-layout false-INFEASIBLE 防线

`src/search/benders_loop.py:7538-7585` 在 whole-layout nogood 落 cut 前调用
`independent_infeasibility_reverifier.py`。独立 verifier 不确认、发现可行分歧、超时或异常时，路径返回
UNKNOWN 并拒绝落 proof-bearing cut。

### 7. close-kernel 结构闸

`data/proof_obligations/p1_2_proof_obligations.json` 当前含 14 个 active obligation；
`scripts/check_p1_2_proof_obligations.py` 绑定 proof-bearing sink inventory、source hashes、guard tokens、
allowlist 和关键 gate 文件。它是结构边界检查，不是“P1.2 已 sound/已发布”的证明。

## 仍未关闭的边界

1. 当前没有受支持的生产 supervisor seal 命令/launcher；普通 solver run 不会从 proposal 自动晋升。
2. `data/review_gates/phase_1_2_spike_close.json` 仍为 `blocked_manual_review_count`，兼容字段
   `p1_3b_entry_allowed=false`。内部 supervisor seal 不能自动翻转 owner gate。
3. PR2 的较小 verification TCB、controlled loader、read-once/one-snapshot 设计仍未实现完整。
4. `scripts/package_review_snapshot.py` 会先解析 treeish 得到 commit metadata，但物化时仍使用原 treeish；
   mutable ref 在两步之间变化时，包内容不一定等于记录的 commit。归档排除策略也仍有未覆盖面。
5. roadmap 中标为 OPEN/PARTIAL 的 canonical→geometry、boundary-placement 等项目仍需按各自验收条件处理。
6. flow/throughput 仍明确在命题 P 之外。不能把 diagnostic flow PASS 写成 certified throughput guarantee。

## 测试状态

2026-06-26 的 collect-only 结果是 **425 个测试文件、3450 个测试**。本轮已确认：

- `src/tests/test_delivery_manifest.py`: 26 passed
- `src/tests/test_delivery_manifest_compatibility_exports.py`: 3 passed

更大的组合运行曾超过本轮执行窗口，没有形成完整通过结论。因此任何文档都不得写“3450 passed”或
“full suite passed”。最终验证结果以本次修复包中的验证日志为准。

## 输入状态

`data/preprocessed/candidate_placements.json` 当前存在，45,774,305 字节，SHA256
`a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`。轻量分发可外置，但当前
工作树并不缺该文件。拐角修复前的 45,773,799 字节 / SHA256
`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` 版本已 superseded，且
hash-incompatible。

## 阶段命名

- P1.2：当前认证发布链 soundness 与 release gate 收口，仍未闭合。
- P1.3：后续真正的 master/cut integration。
- `p1_3b_*`：只作为既有 JSON/CLI 兼容字段保留，不代表人类路线图仍分 A/B。
