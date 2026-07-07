# P1.2 supervisor 设计与当前实现

**实现状态：PR1 已在当前工作树落地；P1.2 已于 2026-07-07 owner-closed；P1.3 已开放；PR2 发布时点硬化桶未完成。**

## 1. 目标

把“求解者声称成功”与“认证 authority 接受并公开”拆开，消除同一控制流既产 witness、又验证、又
发布的自证环。当前链分为 producer、supervisor mint、public publisher 三层。

## 2. Producer contract

`src/search/outer_search.py:855-954`：

- 内部 `RUN_STATUS_CERTIFIED` 只能作为候选求解 verdict；
- terminal frontier 满足后，构造 `search_status=CANDIDATE_PROPOSED`；
- 持久化 proposal、terminal frontier evidence、candidate replay request、fixed-witness material；
- 写 `proposal_ready` marker；
- 不写 durable terminal `CERTIFIED`，不直接生成 public delivery files。

proposal 是待审数据，不是证明 authority。

## 3. Supervisor contract

`ExactCampaign.supervisor_seal()` 位于 `src/search/exact_campaign.py:3399-3593`，是唯一 durable terminal
`CERTIFIED` mint。它必须：

1. 通过 authority path 从磁盘重读 proposal state；
2. 验证 schema、project/source/artifact/campaign/candidate bindings；
3. 重新执行 sink replay，拒绝 producer 进程内函数对象或 freshness marker 授权；
4. 调用 isolated fixed-witness capsule，验证提案中确切 `(R*, π*)` 的 binding/routing/geometry/power；
5. 验证 terminal frontier evidence；
6. 写入 supervisor seal 前后重新加载并验证 disk state；
7. 只在全部通过时写 terminal `CERTIFIED`。

`mark_campaign_stopped(..., "CERTIFIED")` 只有 supervisor 的私有 token 路径可用。普通调用必须报错。

生产调度面已于 2026-07-04 补上：`scripts/run_supervisor_seal.py`（`349c56c`）是 `supervisor_seal()`
的独立生产命令；`main.py`/campaign wrappers 仍不调用。入口存在只满足一条机器条件，不等于 P1.2 closed。

## 4. Fixed-witness capsule

capsule 在隔离 `python -I` 子进程运行，使用 `-B -X pycache_prefix=<fresh-dir>`，返回 nonce-bound
response。父进程只验证 response，不把可构造的 in-process verdict object 当 authority。

验证对象是提案内确切 witness，不允许按 ghost size 自由重解后替换。验证器还独立检查 connector/body、
occupied cells、ghost、binding、routing、power 等终端谓词。UNKNOWN、timeout、材料缺失和异常均 fail-close。

## 5. Public publisher

`src/search/certified_surface.py:563-680` 的
`publish_verified_certified_delivery_surface()`：

- 重读 disk-current campaign；
- 要求 supervisor seal；
- 调用 `resolve_p1_2_publish_open_gate()`；
- 从同一 sealed result 派生 solution、blueprint 和 manifest；
- 采用临时文件/replace，并在异常时清除部分公开输出。

compatibility export 函数可以生成非权威格式，但不能绕过该 publisher 获得 certified publication
语义。

## 6. PR1 已覆盖的外围面

当前未提交工作树还把 main、serializer、delivery manifest、render/viewer、IndustrialPlanner exporter、
report builder 等外围写入面收拢到 central publisher 或显式 non-authoritative 路径。相关 allowlist/obligation
必须按源文件 hash 重新封存。

## 7. PR2 未完成项

受支持的 production supervisor entrypoint 已落地（`scripts/run_supervisor_seal.py`：读取
proposal-ready marker、区分退出码、二次运行 fail-closed）。PR2 的目标仍包括：

- 更小的 supervisor/verifier import closure；
- controlled loader，拒绝不必要的 runtime import/mutable module state；
- read-once/one-snapshot input handling，进一步压缩 load↔hash 与两次读取分叉；
- 明确 verifier dependency manifest 与更窄 native/OS TCB；
- 对 immutable review package 的 resolved-commit materialization；
- 完整 archive policy regressions。

当前代码有 capsule、source digest 和若干 one-snapshot 防线，但不能把它们写成 PR2 已整体完成。

## 8. Gate 与状态

内部 supervisor seal 是发布的必要条件，不是 owner release approval；不能自动翻转 owner gate。
当前 `phase_1_2_spike_close.json` 已由 `owner_manual_decision` 关闭，P1.3 已开放；public
publisher 仍必须只接受完整 sealed campaign + gate 条件，不能因 seal/checker 绿灯旁路。
