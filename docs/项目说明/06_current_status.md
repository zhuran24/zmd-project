# 06 — 当前状态

**状态日期：2026-07-11（凌晨增量更新；正文边界事实 2026-07-07 版继续有效）**  
**发布结论：P1.2 CLOSED（owner 2026-07-07 显式 owner_manual_decision）；P1.3 已开放。**

## 2026-07-08 → 07-11 实现状态增量（细节见 roadmap §0 与各规格书）

- **C1 已是 certified 默认 master 表示**（批 1D，`a1ae1ed`+`fecb495`）：coordinate delegate 的 C1 pose-bool cov-channel 编码转正，S4 blocker 保证 certified 路径非 C1 即拒。批 1 全六子批（1A-1F）落地：cov 通道+witness cell（1B）、解级 power-pole dominance 剪杆进 sealed（1C，`3cc3cf4`）、第 15 条 proof obligation 入册（1E，`4d98314`）。
- **生产内存条款**（1F+M5 修订）：wrapper `systemd-run --scope` 42G 硬帽+`CAMPAIGN_SWAP_MAX` 默认 20G（C1 出解时刻有 ~60G 级固有尖峰，禁 swap 必死——M5 归因判决 `1148067`/`b25ba1d`）;readiness gate RSS 三档分层。「产品默认 solve 参数病态」经 07-11 A/B 四刀证伪（参数仅 wall 差异,`bd96549`）。
- **cut framework 通电前修复批**（`68b4557`）：F1 BState ghost 轴反置修复（soundness 级）+F2 scope 全 map 严格相等+F3 step_8 入口完整性纵深。**attach 通电 spike 判决 GO**（`e719e5d`：10K cut attach 16.6s+solve +4.1%,效度边界四条）;production integration checklist 立册（PIC-0~7,`4fceb9f`）,PIC-3 预算 env 化已落（`b9fcca9`,BUDGET fail-closed resolver+双注册）,PIC-7 已归因关闭。批 B（宿主形态+RFC-001 评估）已于 2026-07-11 完成；Stage B 规格定稿，B0 契约测试壳、B1 frozen artifact/snapshot/digest v1 与 B1.5 typed 平台层（三分支代数+单入口+F5 oracle 复验）已落地。当前待 B2-B5、PIC C/D/E、RFC-002/003 与 B6 owner promotion。
- **exploratory 模式在 prod-scale 上不可用**的坑已钉死（port clearance 启发式 build 爆炸+legacy master+all_facility 实例集,py-spy 实锤,memory 卡+spike 规格书）。

本页描述当前工作树，不以 Git HEAD 的提交时间替代工作树事实。未提交的 PR1 发布面 soundness 修复
属于当前实现状态。

## 已落地的边界

### 1. producer 只提案

`src/search/outer_search.py:855-954` 的 terminal path 只构造并持久化
`CANDIDATE_PROPOSED`，同时提交 terminal frontier evidence、sink replay request、fixed-witness
material 和 proposal marker。它不再直接铸造 durable terminal `CERTIFIED`。

### 2. supervisor 是唯一 durable terminal mint

`src/search/exact_campaign.py:3497` 的 `ExactCampaign.supervisor_seal()`：

- 从磁盘读取已提交 proposal，而不是信调用者的内存对象；
- 复核 project/source/artifact/campaign/candidate bindings；
- 执行 candidate sink replay 与 fixed-witness capsule；
- 校验 terminal evidence 与发布 witness；
- 写前、写后重新验证 disk authority；
- 只有全部通过才写 terminal `CERTIFIED` seal。

其它路径调用 `mark_campaign_stopped(..., "CERTIFIED")` 会被拒绝。

**生产入口（2026-07-04 已接入）：**`scripts/run_supervisor_seal.py`（`349c56c`）是 `supervisor_seal()`
的独立生产命令，从 proposal-ready marker 驱动；`main.py` 和 runtime wrappers 仍不调用
`supervisor_seal()`，普通 solve 的实际终点仍是 `CANDIDATE_PROPOSED`。入口存在只满足一条机器条件，
不等于 P1.2 closed。

### 3. fixed-witness 与 connector/body 复验

`terminal_fixed_witness_capsule.py` 在隔离 Python 子进程中对提案的确切 `π*` 复跑验证，并用
nonce-bound response 返回裁决。`terminal_fixed_witness_verifier.py` 还独立拒绝 connector cell 被
facility body 占用，包括 own-body 和 other-body。自由重解出的“同尺寸另一个可行布局”不能替代发布
witness。

### 4. P1.2 publish gate 已机器化且 owner-closed

`src/search/certified_surface.py:508` 从权威 review gate 解析 P1.2 发布状态。缺失、畸形、仍 open
或非显式 owner-closed 的 gate 一律使 public surface `publishable=false`。

### 5. public publisher 单入口

`src/search/certified_surface.py:800` 的
`publish_verified_certified_delivery_surface()` 是公开 solution、blueprint 和 delivery manifest 的
唯一 certified publisher。它要求 disk-current supervisor seal，三件输出同源，并在失败时清理部分写入。
外围 serializer、viewer、report、adapter 和 compatibility exporter 已被收拢为非权威派生面。

### 6. whole-layout false-INFEASIBLE 防线

`src/search/benders_loop.py::_reverify_whole_layout_infeasibility_before_cut`（当前调用点约 `:8279`） 在 whole-layout nogood 落 cut 前调用
`independent_infeasibility_reverifier.py`。独立 verifier 不确认、发现可行分歧、超时或异常时，路径返回
UNKNOWN 并拒绝落 proof-bearing cut。

### 7. close-kernel 结构闸

`data/proof_obligations/p1_2_proof_obligations.json` 当前含 15 个 active obligation；
`scripts/check_p1_2_proof_obligations.py` 绑定 proof-bearing sink inventory、source hashes、guard tokens、
allowlist 和关键 gate 文件。它是结构边界检查，不是“P1.2 已 sound/已发布”的证明。

## 已关闭后的剩余边界

1. 普通 solver run 不会从 proposal 自动晋升（生产 supervisor seal 命令已存在：`scripts/run_supervisor_seal.py`；但尚无真实生产 campaign→seal 实跑记录）。
2. `data/review_gates/phase_1_2_spike_close.json` 已为 `closed_manual_owner_decision`，兼容字段
   `p1_3b_entry_allowed=true`。这是 2026-07-07 owner 真实输入的 `owner_manual_decision`；
   内部 supervisor seal 不能自动翻转 owner gate，clean 计数仍保存在仓库外。
3. PR2 的较小 verification TCB、controlled loader、read-once/one-snapshot 设计仍未实现完整（其中「仅防能执行 reseal 仪式的蓄意内鬼」的硬化 owner 2026-07-06 已暂缓到发布时点、明确非 P1.2 闭合前提，见 PROJECT_LOCK §C5 close-scope 修改）。
4. `scripts/package_review_snapshot.py` 的 resolve-once 已把 treeish 一次解析为不可变 commit 并同时用于
   provenance 与物化（ref-move TOCTOU 已闭，回归 `test_package_review_snapshot_ref_move_after_resolve_keeps_packaged_commit`）；
   归档排除策略主缺口已堵（协作记忆 `cc_memory/`+`cc_memory_vnext/` 已排除，`28d9d2c`），残余仅策略细化（`paths/`/`.githooks` 去留、secret-scan 纵深、manifest 是否列出被排除路径名）。
5. roadmap 中标为 OPEN/PARTIAL 的 canonical→geometry、boundary-placement 等项目仍需按各自验收条件处理。
6. flow/throughput 仍明确在命题 P 之外。不能把 diagnostic flow PASS 写成 certified throughput guarantee。

## 测试状态

2026-07-11 collect-only 为 **450 个 `test*.py` 文件、4182 tests**；`src/tests/cuts` 单独为 **594 tests**。
这些都是收集数量，不是通过数量。本次文档审计没有运行并声称 full suite passed；任何 pass 数仍须附命令、工作树与退出码，最终以本次审计包的验证日志为准。

## 输入状态

`data/preprocessed/candidate_placements.json` 当前存在，45,774,305 字节，SHA256
`a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`。轻量分发可外置，但当前
工作树并不缺该文件。拐角修复前的 45,773,799 字节 / SHA256
`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` 版本已 superseded，且
hash-incompatible。

## 阶段命名

- P1.2：当前认证发布链 soundness 与 release gate 收口已于 2026-07-07 owner-closed。
- P1.3：已开放且实质推进（2026-07-08 M1-M4）：attach 链四族通电——F1
  region_capacity（含 ghost 条件化修复）、F7 power_hitting_set（运行时闸+
  等价回归）、F6 shape_packing_hall（SoT 下界 override）、F5 pattern_nogood
  （query_liftable 合同+binding_empty_domain_v1 真 adapter+P-HOM 结构门）；
  cut 总量预算（2000 满即停发）。F2/F3/F9/F4 保持 fail-closed（终态理由见
  记忆卡：F2 吞吐锁+桥语义、F3 缺 active_port_witness、F9 tight-K 绞死、
  F4 缺 route registry——均非遗漏）。总开关 `EXACT_CUT_FRAMEWORK_ATTACH`
  仍在 unsafe map（certified 下开启即 fail-closed）。旧 M4 阶梯与等价回归虽已齐，
  07-11 Stage B 规格又明确了 B1.5-B5、PIC C/D/E、RFC-002/003 与 B6 owner promotion（其中 B1.5 已于当日落地）；
  因此不能再概括为“仅剩 owner”。close-kernel 现 66 sinks（B1.5 后 typed_platform 入册）。
  F8 power_grid_reach 已整族退役删除（owner 游戏规则拍板：电杆不需连网）。
  详见记忆卡 `p1-3-m4-ladder-landed`/`p1-3-m3-step8-landed`/
  `p1-3-m2-coverage-stencil-ruling`。
- `p1_3b_*`：只作为既有 JSON/CLI 兼容字段保留，不代表人类路线图仍分 A/B。
