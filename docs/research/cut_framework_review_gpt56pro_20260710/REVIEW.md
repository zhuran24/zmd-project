# zmd cut framework 架构与实现评审

评审日期：2026-07-09  
评审对象：`toolchain_review_pkg.7z/40_implementation/src_cuts/` 及当前项目中的生产接线  
结论级别：**当前保持 production/certified NO-GO；shadow 与受控实验可继续。**

本文路径记号：

* `R/...` 指 `toolchain_review_pkg.7z` 解包根目录。
* `P/...` 指 `zmd_pr1_1c_88f65a55df3f_20260709_143517.7z` 解包根目录。
* `〔path:Lx-Ly〕` 是本次审阅使用的 committed tree 行号。

## 0. 先纠正评估包中的现状漂移

`00_READ_FIRST.md` 要求先读，本评审照做；但导读的两个关键现状已经落后于随包源码：

1. 导读称 2026-07-08 时 `step_8_apply_to_master` 仍是 `NotImplementedError`，并再次把 Step 8 列为 stub。〔R/00_READ_FIRST.md:L16-L17〕〔R/00_READ_FIRST.md:L29-L32〕实际源码已实现 F1、F7、F6、F5 四族翻译，其他族才 fail-closed。〔R/40_implementation/src_cuts/lifecycle.py:L1162-L1174〕〔R/40_implementation/src_cuts/lifecycle.py:L1207-L1250〕〔R/40_implementation/src_cuts/lifecycle.py:L1299-L1398〕当前状态文档和 M4 战报也明确四族已通电、F8 已删除。〔R/30_current_authority/project_spec_docs/06_current_status.md:L99-L110〕〔R/50_battle_record/m4_attach_ladder_landed_card.md:L69-L85〕
2. 导读称实现约 5.8K 行。〔R/00_READ_FIRST.md:L3-L3〕本次按物理 Python 行统计，`src_cuts` 为 33 文件、9,655 行，测试为 26 文件、9,941 行，见 `evidence/code_inventory.txt`。

评估时采用的实际权威优先级是：当前 committed source 与测试，高于 2026-07-08/09 战报和 `06_current_status.md`，再高于仍写着旧状态的规范段落。这个漂移不是纯文档瑕疵，它会直接误导上线门、威胁模型和评审范围，后文列为 CONCERN I-9。

评估包中的 `src_cuts/`、测试与项目包的 `src/cuts/`、`src/tests/cuts/` 文件集合及内容逐字节一致，见 `evidence/source_hash_equivalence.txt`。因此下述实现判断直接适用于当前项目。

## 1. 总判断

### 1.1 架构判断

**核心方向合理，而且比普通“从子问题抄一条 nogood 回 master”成熟得多。** 对一个要求 cut 可独立 replay、发布链 fail-closed、False Positive 必须为零的 LBBD 系统，把 cut 做成 proof-bearing 对象、显式绑定 source/ghost/artifact scope、区分 HOLD 与 QUARANTINE，并默认 generator/oracle 不可信，是正确的安全方向。规范的 sound deduction 目标也清楚：scope 匹配且 validator 通过，才允许 body 排除解。〔R/30_current_authority/project_spec_docs/02_mathematical_foundations.md:L24-L48〕HOLD 与 QUARANTINE 的区分能把“当前候选不适用”与“证明对象有问题”分开，这个语义值得保留。〔R/30_current_authority/project_spec_docs/04_design_invariants.md:L51-L58〕〔R/30_current_authority/PROJECT_LOCK.md:L403-L407〕

**但当前宣称的 trust model 不成立。** “validator 是唯一 trust point”与实现不符。真正可信计算基至少包含 state snapshot 构造、scope 依赖完备性、schema/canonicalization、family validator、proof 到约束的 compiler、master adapter、ghost condition 绑定和 solver API 语义。规范要求 validator 不调用 oracle。〔R/30_current_authority/project_spec_docs/02_mathematical_foundations.md:L138-L143〕当前 F5 validator 却从同一全局 registry 取回 generator 使用的 adapter，再调用同一 `query_liftable()`。〔R/40_implementation/src_cuts/families/pattern_nogood.py:L92-L130〕〔R/40_implementation/src_cuts/families/pattern_nogood.py:L360-L405〕这不是 Byzantine 隔离，而是共同失效。

**四元组本身可以保留概念，但不应保留两份可写真相。** 当前 geometric family 同时保存 `geometric_payload` 和 `cert.cert_payload`；F1 validator 解析前者，Step 8 解析后者。〔R/40_implementation/src_cuts/families/region_capacity.py:L365-L384〕〔R/40_implementation/src_cuts/lifecycle.py:L1207-L1230〕这让 body/cert 漂移成为结构性风险。本次已经构造出生产可达反例。正确形态应是“一个 typed proof，body 与 ConstraintPlan 都由它派生”，详见 RFC-001。

**ACTIVE/HOLD/QUARANTINE 状态机只完成了记录层，没有完成模型层。** CutStore 可以把记录改成 HOLD/QUARANTINE。〔R/40_implementation/src_cuts/store.py:L177-L208〕但 CP-SAT 约束一旦加入现有 model 就不能靠 store 状态撤回。项目自己也承认“满即停发”只是当前保险丝，真正 eviction 需要 master rebuild。〔R/50_battle_record/m4_attach_ladder_landed_card.md:L73-L78〕因此现在的状态机在最关键的物理层没有闭环。需要 model epoch、poison 与 rebuild 规则，详见 RFC-003。

### 1.2 实现质量判断

基础工程质量不差：基线 cut 测试 **441/441 通过**，Ruff 全绿；测试 LOC 甚至略高于实现 LOC。完整 source digest 使用全 SHA-256，且从实际注入 payload 重算，不信任调用者手写缓存值。〔R/40_implementation/src_cuts/lifecycle.py:L505-L538〕deserialize 会做完整性检查。〔R/40_implementation/src_cuts/lifecycle.py:L796-L851〕unknown family 的 Step 8 是 fail-closed；F7 master 端还会用自己的 coverer 表做第二次运行时核对。〔R/40_implementation/src_cuts/lifecycle.py:L1171-L1184〕〔P/src/models/exact_coordinate_master.py:L7347-L7369〕这些都是实打实的优点。

但生产入口恰好绕开了最重要的防护，且存在两个可复现 BLOCKER 和一个 scope CONCERN：

* 完整性错误返回值被忽略，能“验证正常 body，编译恶意 cert”。
* 非方形 ghost 的 width/height 在 BState 构造时反置。
* cut 能删除全部 `artifact_hashes` 后仍通过 Step 6。

三者在未改源码上均已复现，输出见 `evidence/repro_*.txt`。基线 441 个测试没有覆盖这些跨模块组合，说明测试丰富但仍偏 family 内部，生产 seam 的 adversarial coverage 不足。

### 1.3 GO/NO-GO

`EXACT_CUT_FRAMEWORK_ATTACH` 目前仍在 certified unsafe map，本评审支持继续保持。项目锁要求晋升前有 family ladder、helper/master 等价回归和 owner 决定。〔R/30_current_authority/PROJECT_LOCK.md:L479-L487〕我的意见是还应追加三个硬门：

1. attach 边界原子封口，至少合入本包补丁 0001 至 0003，并把生产入口收口为 typed validate-and-compile。
2. F5 改成真正独立 proof verifier；在此之前不允许 F5 mutate master。
3. 上线 append-only attach ledger、semantic dedup、model epoch/rebuild 与 rollback 演练。

没有这三项，当前架构的“可独立重验”和“fail-closed”只在 library 层成立，尚未在真实生产消费链成立。

## 2. 问题 1：架构判断

### A-1，肯定：proof-bearing cut + scope-aware replay 是对目标的正解

**判断：KEEP。** LBBD 本来就允许用 family-specific logical deduction 产生 cut；本项目进一步要求 proof 对象可序列化、可离线重验，并将 source、ghost、blocked cells、artifact、oracle version、assumption 分开检查。规范明确了六步 scope 和五层 proof binding。〔R/30_current_authority/project_spec_docs/02_mathematical_foundations.md:L77-L116〕〔R/30_current_authority/project_spec_docs/02_mathematical_foundations.md:L145-L170〕这比只记录一个约束表达式更适合 certified pipeline。

实现中也有扎实部分：`CutScope.__post_init__` 对 artifact map 做防别名快照。〔R/40_implementation/src_cuts/lifecycle.py:L175-L195〕source digest 覆盖 canonical rules、candidate placements、mandatory mapping、templates、commodity data 与 group static，并有字段漂移自检。〔R/40_implementation/src_cuts/lifecycle.py:L505-L521〕replay 首先检查完整性，再做 scope 与 validator。〔R/40_implementation/src_cuts/replay.py:L75-L116〕这些应保留。

### A-2，CONCERN：实际 TCB 大于 validator，当前口号会制造盲区

**问题。** 规范说 oracle Byzantine、validator 唯一可信且不调用 oracle。〔R/30_current_authority/project_spec_docs/02_mathematical_foundations.md:L138-L143〕但一个 cut 是否安全进入 master，还取决于：

* BState 是否正确反映 master，当前 ghost 轴错误证明 builder 会错。
* scope 是否完整，当前 artifact subset 证明 scope 会漏。
* validator 与 compiler 是否读同一语义对象，当前 F1 不是。
* compiler 是否忠实，Step 8 和四个 `add_*_cut` 都是 TCB。
* ghost condition 是否绑定正确，项目之前已经发生过无条件 attach 的 anchor 漏洞，M4 战报明确记录。〔R/50_battle_record/m4_attach_ladder_landed_card.md:L71-L78〕

**修改建议。** 用 RFC-001 的 `ValidatedStateSnapshot -> validate_and_compile_cut -> CompiledCut -> master.apply` 取代手工 gauntlet。文档把唯一 trust point 改为最小化、明确列举的 TCB。master 不再接受 raw `Cut`。迁移约 5 至 9 人日覆盖四个活跃 family。

### A-3，CONCERN：body 与 cert 双轨购买的是风险，不是价值

**问题。** Cut schema 强制 body XOR 模式，但 geometric body 与 cert 实际又是两份 bytes。〔R/40_implementation/src_cuts/lifecycle.py:L205-L233〕完整性函数知道二者必须相等。〔R/40_implementation/src_cuts/lifecycle.py:L545-L564〕然而 validator 和 compiler 分别解析两份，任何漏调完整性检查都会形成 split-brain。本次生产反例正是这样发生。

**修改建议。** 短期应用补丁 `0001-cuts-seal-integrity-at-irreversible-attach-boundary.patch`，在调用方和 Step 8 双重检查。长期按 RFC-001 schema v2 只保存 typed proof，body 和 ConstraintPlan 均由 proof 纯函数派生。v1 importer 可检查 body 等于 canonical projection 后再丢弃 body。预计 3 至 5 人日先迁 F1/F6/F7。

### A-4，CONCERN：F5 的“重问同一个 oracle”违反设计根基

**问题。** F5 generator 的合同允许 adapter 生成 INFEASIBLE。〔R/40_implementation/src_cuts/oracles/pattern_nogood_oracle.py:L111-L138〕validator 从同一 registry 找同一 adapter，并再次调用。〔R/40_implementation/src_cuts/families/pattern_nogood.py:L92-L130〕〔R/40_implementation/src_cuts/families/pattern_nogood.py:L360-L405〕若 adapter 对数学条件理解错、使用错误 group mapping、或被替换为永远返回 INFEASIBLE 的实现，两次调用会一致地错。

生产 adapter 的 `group_operation_types` 是构造时捕获的私有映射，不在 LiftableScope。〔P/src/search/f5_binding_empty_domain_adapter.py:L48-L65〕生产代码只按名称复用 registry 中已有实例。〔P/src/search/benders_loop.py:L7835-L7858〕这还引入跨 controller/session 陈旧映射风险。

**修改建议。** 在独立 proof 落地前禁用 F5 master mutation，只做 shadow。按 RFC-002 把当前唯一可 lift 结论收窄成 `binding_empty_domain_v1` proof，cert 明确绑定 group、operation type、pose/profile hashes；validator 用独立匹配/枚举器重算，不访问 registry。专用版本约 2 至 4 人日；通用 proof-kind 体系约 4 至 7 人日。

### A-5，CONCERN：scope 的依赖集合由 cut 自报，缺项不会被发现

**问题。** Step 6 当前只遍历 cut 携带的 `artifact_hashes`，所以空字典天然通过。〔R/40_implementation/src_cuts/lifecycle.py:L942-L985〕这相当于让不可信 proof 自己决定哪些前提需要核对。它违背“所有 proof premise 必须 current”的目标。

另外 ghost、blocked 和 exterior hash 截断到 SHA-256 前 16 个 hex，即 64 bit。〔R/40_implementation/src_cuts/lifecycle.py:L444-L462〕这对缓存键够用，但在显式 adversarial proof boundary 里没有必要承担可避免的碰撞风险。

**修改建议。** schema v1 先应用补丁 `0003-cuts-require-complete-artifact-scope-snapshots.patch`，要求 cut artifact map 与 state 全等。schema v2 改成 family registry 定义 required dependency names，cut 只携带值，集合严格相等；proof identity 一律使用完整 SHA-256。详见 RFC-001 §4。短期改动小于 1 人日，精确 family manifest 约 2 至 4 人日。

### A-6，CONCERN：状态机没有约束已经加入 CP-SAT 的约束

**问题。** Store 的 ACTIVE/HOLD/QUARANTINE 转换本身清楚。〔R/40_implementation/src_cuts/store.py:L114-L208〕但生产 attach 不经过 store，且 CP-SAT 约束不可删除。战报明确写了预算 2000 满即停发，真正 eviction 归 master rebuild。〔R/50_battle_record/m4_attach_ladder_landed_card.md:L73-L78〕原设计则把 source change、artifact change与 validator 失败视为 quarantine/replay 事件。〔R/20_original_design/cut_lifecycle_v2.md:L843-L881〕两者之间缺了一座桥。

**修改建议。** 实施 RFC-003：每次 build 建立 model epoch；APPLIED cut 后来失效则 poison 当前 epoch，禁止发布并 rebuild；ghost-bound cut 只有在 condition literal 本身经 replay 证明正确时可留在同一 epoch。预计 4 至 8 人日完成最小 ledger/rebuild 闭环。

### A-7，CONCERN：冻结“9 族数量”是过度设计，冻结 family 语义才有价值

**问题。** 规范仍说 9 族不可增删改 mode。〔R/30_current_authority/project_spec_docs/04_design_invariants.md:L9-L32〕〔R/30_current_authority/project_spec_docs/04_design_invariants.md:L60-L75〕但当前 source 已删除 F8，只剩 8 个 Literal 和 mode map。〔R/40_implementation/src_cuts/lifecycle.py:L65-L90〕当前状态也承认 F8 退役。〔R/30_current_authority/project_spec_docs/06_current_status.md:L99-L110〕这已用事实证明“数量冻结”不能作为可靠不变量。

九类数学 idea 可以是 roadmap，不应成为 closed-world schema。真正需要冻结的是：已发布 family 的 proof schema、mode、compiler 语义和兼容规则。

**修改建议。** 用 RFC-001 的 capability registry，状态包括 EXPERIMENTAL、VALIDATED、COMPILABLE、ENABLED、RETIRED。CI 从 registry 生成 family 表，并检查 verifier/compiler/tests 完整性。迁移约 1 至 2 人日，不影响已有 family 名称和序列化兼容。

### A-8，CONCERN：六维 watcher 在“无 ledger、无 rebuild、非生产路径”阶段过早

**问题。** 原设计为每个 family 建六维 watcher，希望把 O(全 cut) 降为 O(affected cut)。〔R/20_original_design/cut_lifecycle_v2.md:L767-L837〕实现也保留这些结构。〔R/40_implementation/src_cuts/store.py:L67-L110〕但当前生产 attach 直接生成并注入，不使用 CutStore；战报侦察也明确“CutStore 不在生产 attach 路径”。〔R/50_battle_record/m4_recon_index.md:L17-L18〕在首次生产消费前，投入大量 watcher/state 复杂度，却没有先完成最基本的 attach ledger、semantic dedup、model epoch 和持久化，这个优先级倒置。

**修改建议。** 不必删除 watcher，但把它降为后续性能优化，先实现 RFC-003 的 append-only ledger、strict replay、dedup 和 rebuild。只有生产 telemetry 证明全表 replay 成为瓶颈后再启用 watcher，并用同一 ledger 派生索引，避免第二权威源。

## 3. 问题 2：实现质量与设计契合度

### 正面评价

1. **schema/mode 防线具体。** `Cut.__post_init__` 强制 literal/geometric XOR、scope/cert 必填和 family mode。〔R/40_implementation/src_cuts/lifecycle.py:L205-L260〕
2. **source digest 设计正确。** 从真实 source payload 规范化并使用完整 SHA-256，调用方的 `state.source_digest` 不是 authority。〔R/40_implementation/src_cuts/lifecycle.py:L505-L538〕
3. **deserialize 与 replay 比 production seam 更严。** deserialize 检查 cert hash/body 一致性，replay 也先检查完整性并 quarantine。〔R/40_implementation/src_cuts/lifecycle.py:L796-L851〕〔R/40_implementation/src_cuts/replay.py:L103-L127〕
4. **master translator 多处有防御性重验。** F5 all-or-nothing，任何 literal 无法忠实表示就拒整条 cut；F7 用 master 自有 coverer 表核对。〔P/src/models/exact_coordinate_master.py:L7386-L7456〕〔P/src/models/exact_coordinate_master.py:L7347-L7384〕
5. **F5 liftable scope 的白名单思想值得肯定。** 它结构性排除了 selected poses、cell owner、ghost 等 incumbent 状态，避免口头约束。〔R/40_implementation/src_cuts/oracles/pattern_nogood_oracle.py:L63-L108〕只是独立验证仍未完成。
6. **测试投资充足。** 33 个 source 文件、26 个测试文件，基线 441 tests 全过，Ruff 全过；这为修复提供了良好地基。

### I-1，BLOCKER：生产入口忽略完整性错误，可错译成更强 cut

**代码。** `_maybe_attach_framework_cuts()` 调用了 `validate_cut_integrity(cut)`，但丢弃返回值，随后继续 validator 与 Step 8。〔P/src/search/benders_loop.py:L7862-L7883〕完整性函数本来能识别 cert hash、oracle hash和 geometric body/cert 漂移。〔R/40_implementation/src_cuts/lifecycle.py:L545-L564〕

**可复现影响。** 本次将一个正常 F1 cut 的 `cert.cert_payload.cap_R` 改成 0，重算 cert hash，保留正常 `geometric_payload`。`validate_cut_integrity()` 正确报告错误；F1 validator 因读取正常 body 而 OK；Step 8 因读取恶意 cert 而向 master 注入 `capacity=0`。未改源码输出：

```text
{'integrity_error_expected': True, 'attached': 1,
 'master_calls': [{'group_cell_weights': {'boundary_io': 3}, 'capacity': 0, ...}]}
```

见 `evidence/repro_cut_integrity_bypass.txt` 与脚本。该 bug 可把一个 sound proof 变成任意更强约束，属于 False Positive 风险。

**补丁。** `patches/0001-cuts-seal-integrity-at-irreversible-attach-boundary.patch`：生产入口检查返回值并记录拒绝原因；scope 在 expensive validator 前先 gate；Step 8 再做一次 defense-in-depth 完整性检查；新增恶意回归。长期替换见 RFC-001。

### I-2，BLOCKER：ghost width/height 反置

**代码。** master 的 `ghost_rect` 契约是 `(width, height)`，并按 width 遍历 dx、height 遍历 dy。〔P/src/models/master_model.py:L4769-L4792〕BState 契约是 `(x, y, x_span, y_span)`。〔R/40_implementation/src_cuts/lifecycle.py:L396-L412〕state builder 先正确取出 `ghost_w, ghost_h`，却构造成 `(anchor_x, anchor_y, ghost_h, ghost_w)`。〔P/src/search/benders_loop.py:L7581-L7587〕〔P/src/search/benders_loop.py:L7646-L7652〕

**可复现影响。** 对 master ghost `(w,h)=(2,1)`，BState 得到 `(x,y,1,2)`。见 `evidence/repro_ghost_axis_swap.txt`。square ghost 测试一直掩盖此错误。错误 ghost id/scope 会导致 cut 被错误 HOLD/ATTACH，并可影响 family 对 ghost geometry 的证明。

**补丁。** `patches/0002-cuts-preserve-ghost-width-and-height-in-BState.patch` 修正顺序，并新增非方形红测。长期应改用 `GhostRect(x,y,width,height)` 命名 dataclass，见 RFC-001 §7。

### I-3，CONCERN：artifact scope 可由 cut 删除依赖

**代码。** Step 6 只检查 cut 中存在的 key。〔R/40_implementation/src_cuts/lifecycle.py:L971-L978〕

**可复现影响。** state 有 `canonical_rules.json: h1`，将 cut 的 artifact map 改为空，仍返回 ATTACH。见 `evidence/repro_scope_artifact_omission.txt`。

**补丁。** `patches/0003-cuts-require-complete-artifact-scope-snapshots.patch` 对 schema v1 改为全 map 严格相等并加回归。长期用 RFC-001 的 per-family dependency manifest，避免无关 artifact 变动导致不必要 quarantine。

### I-4，CONCERN：F5 registry 既是全局可变状态，又承载 verifier

**代码。** registry 是模块级 dict；“同名幂等”实际无条件覆盖。〔R/40_implementation/src_cuts/oracles/pattern_nogood_oracle.py:L141-L162〕generator 先要求 adapter 在 registry，validator 再从相同 registry resolve。〔R/40_implementation/src_cuts/oracles/pattern_nogood_oracle.py:L175-L235〕〔R/40_implementation/src_cuts/families/pattern_nogood.py:L92-L130〕生产则在已存在时复用旧 adapter。〔P/src/search/benders_loop.py:L7846-L7858〕

**风险。** 跨 session stale mapping、测试顺序污染、同名实现替换、generator/validator common-mode。并且 adapter 的 operation mapping 未进入 scope/source digest。〔P/src/search/f5_binding_empty_domain_adapter.py:L48-L65〕

**修改建议。** 按 RFC-002 移除 validator 对 registry 的依赖，registry 只做 generator plugin factory；实例按 snapshot 创建，缓存 key 含完整 source/mapping digest；同名不同 fingerprint 抛错。F5 在此之前保持 shadow。

### I-5，CONCERN：生产链手工拼 gauntlet，绕过 serialize/replay/store

**代码。** library 的 replay 会做 integrity、scope、validator、store transition。〔R/40_implementation/src_cuts/replay.py:L75-L130〕生产却自己 import 四个函数并手工排序调用。〔P/src/search/benders_loop.py:L7734-L7775〕它不做 serialize/deserialize round-trip，不登记 CutStore，不留 rejection taxonomy，原代码只记录 generated/attached/family。〔P/src/search/benders_loop.py:L7887-L7897〕

**风险。** 防护在两个路径漂移。I-1 已证明这种漂移不是理论问题。

**修改建议。** RFC-001 提供单一 `validate_and_compile_cut()`；RFC-003 的 ledger 成为唯一生产记录。补丁 0001 先补 rejection reasons，但不把手工链当最终形态。

### I-6，CONCERN：Cut proof 与 lifecycle status 混在一起，状态权威重复

**代码。** frozen `Cut` 自带 `is_quarantined/quarantine_reason`。〔R/40_implementation/src_cuts/lifecycle.py:L205-L223〕CutStore 又维护独立的 `quarantined` 与 `held` 集合。〔R/40_implementation/src_cuts/store.py:L108-L110〕store transition 并不更新 Cut 内字段。〔R/40_implementation/src_cuts/store.py:L177-L208〕

**风险。** 序列化出去的 cut status 可能与 store 派生状态不一致；proof identity 被运行时状态污染。

**修改建议。** 按 RFC-003 将 proof envelope 与 append-only `CutLedgerEvent` 分开，status 仅由 ledger 派生。v1 deserialize 时忽略 Cut 内 status 或仅作为 legacy metadata，不作为权限判断。

### I-7，CONCERN：BState 可变且 geometry 使用裸 tuple，TOCTOU 与轴错误易发

**代码。** `GroupState`/`BState` 非 frozen，selected poses 是 list，多个映射是可变 dict；ghost 是未命名四元组。〔R/40_implementation/src_cuts/lifecycle.py:L378-L437〕虽然 CutScope 对 artifact map 做了局部 copy，但整个 state 在 validate 与 apply 之间仍可能变化。

**风险。** I-2 已经展示 tuple 契约易错；未来并发/多 worker 接线会放大 TOCTOU。P1.3 计划本身也把 thread safety 列为议题。〔R/30_current_authority/project_spec_docs/09_phase_1_3_plan.md:L78-L84〕

**修改建议。** RFC-001 的 immutable `ValidatedStateSnapshot`、`GhostRect`、tuple/frozenset/mapping proxy；snapshot digest 同时绑定 validator 与 compiler。预计 2 至 4 人日可先覆盖活跃四族输入。

### I-8，CONCERN：缺少语义去重与选择，2000 预算可能被重复 cut 吃完

**代码。** F1 cut_id 含毫秒时间戳。〔R/40_implementation/src_cuts/lifecycle.py:L703-L729〕生产每轮重新生成，按当前 attach count 到 2000 就停。〔P/src/search/benders_loop.py:L7777-L7791〕没有 semantic fingerprint、重复检测、dominance 或收益排序。原设计也把 dominance/expiry 延到 Phase 2。〔R/20_original_design/cut_lifecycle_v2.md:L944-L964〕

**风险。** 同一语义 cut 可因不同时间戳/iteration 多次占预算。对不可删除约束的 CP-SAT model，这会同时浪费 build memory 和传播成本。

**修改建议。** RFC-003 先做严格语义等价 fingerprint 与去重，再逐族加安全 dominance。CP-SAT 首版 selector 用 violation margin、plan arity、body/core 大小、重复率、apply cost 和 A/B propagation delta，不必照搬 LP efficacy。

### I-9，CONCERN：权威文档与代码发生互相否定

**证据。** 同一 `30_current_authority` 内，一边把 9 族不可删和 F8 mode 列为锁。〔R/30_current_authority/project_spec_docs/04_design_invariants.md:L60-L75〕〔R/30_current_authority/project_spec_docs/04_design_invariants.md:L92-L103〕另一边 `06_current_status` 说 F8 已删除。〔R/30_current_authority/project_spec_docs/06_current_status.md:L99-L110〕`PROJECT_LOCK` 仍有 Step 8 未实现、整个 subsystem 不可达的旧陈述。〔R/30_current_authority/PROJECT_LOCK.md:L121-L121〕〔R/30_current_authority/PROJECT_LOCK.md:L381-L381〕同时锁文件较后段又明确禁止 certified 开启已经接线的 Step 8。〔R/30_current_authority/PROJECT_LOCK.md:L479-L487〕

**风险。** reviewer 可能审错代码路径，release gate 可能检查错误 capability，历史 finding 的 reachability 结论失效。

**修改建议。** capability registry 生成机器可读 `cut_capability_manifest.json`，文档表从 manifest 生成；每个权威段落带 `as_of_commit`；CI 拒绝“ENABLED family 无 compiler”或“RETIRED family 仍被 frozen list 宣称 active”。导读和锁文件应在晋升前一次性校准。

### I-10，NOTE：静态类型门原基线有两个小缺口

基线 `mypy --strict --explicit-package-bases src/cuts` 报两个 bare generic：`set` 与 `dict`。这不构成 soundness concern，但说明当前“测试/ruff 全绿”不等于静态门全绿。补丁 0001 顺手修复 `set`，补丁 `0004-cuts-type-canonical-relabel-slot-counter.patch` 修复 `dict`，不改变运行语义。补丁后 33 个 source 文件 mypy strict 全绿。

## 4. 问题 3：与 LBBD/Benders 和成熟 cut 管理常规的比较

### 4.1 与领域常规一致、值得肯定的部分

1. **family-specific logical deduction 是标准 LBBD 思路。** Hooker 与 Ottosson 的 LBBD 本质就是把经典 Benders 的 LP dual 推广为 inference dual，由逻辑推导产生 cut。本项目的 F1/F5/F6/F7 各自用不同数学 witness，方向正确。
2. **proof replay 与 scope currentness 明显强于普通工程。** 常规实现常把 callback 生成的 cut 直接当可信；本项目要求可序列化 proof、source digest、artifact scope、validator、quarantine audit，这是高 assurance 场景的合理额外成本。
3. **master-side defense 值得保留。** F7 coverer 双算、F5 all-or-nothing translator、ghost condition fail-closed 都是在 compiler 边界防止 helper 与 master 语义漂移的好实践。
4. **最小 core 的方向合理。** F5 的 deletion minimizer、canonical relabel 与重新验证是 cut 强化思路，尽管 verifier 目前不独立。

### 4.2 相比成熟 cut management 明显缺失的部分

成熟 MIP cut manager 不只问“sound 吗”，还会做 pool 去重、cut selection、平行/冗余过滤、age/activity 和容量管理。Magnanti-Wong 经典工作强调选择 strong/Pareto-optimal Benders cuts；SCIP 的官方 hybrid selector综合 efficacy、directed cutoff distance、objective parallelism、integer support，并过滤平行 cut；SCIP cut pool 也有“若不存在才加入”、global pool、age limit 和删除机制。

本项目目前缺少：

* semantic fingerprint 与严格重复过滤；
* strength/violation/propagation 收益指标；
* family quota 与 diversity；
* dominance/subsumption；
* age/hit/activity 记录；
* model rebuild 后的安全 eviction；
* attach cost、solver time、RSS 的闭环反馈。

CP-SAT 没有 LP relaxation efficacy 的同一含义，不应机械照抄 SCIP。但可使用可测代理：当前 incumbent 的 violation margin、core/body 大小、presence term 数、变量固定/域削减、冲突和分支变化、build/solve/RSS 增量、duplicate rate、最近命中。RFC-003 给了最小 selector 形态。

### 4.3 本项目“多出来”的部分

多出来但值得保留：proof envelope、独立 replay、artifact/source scope、Byzantine generator 假设、HOLD/QUARANTINE audit。这些不是普通 cut pool 的常规配置，但与本项目 certified exact 目标匹配。

多出来且目前回报不足：冻结 family 数量、在生产 ledger/rebuild 之前先做六维 watcher、通用 Step 0 至 9 API 与 family 内实际流程不一致、Cut 内嵌状态加 Store 状态双轨。这些复杂度应收缩或后移。

### 4.4 非常规选择的最终评价

**“oracle Byzantine”值得肯定；“validator 唯一 trust point”必须撤回。** 前者促成了大量有价值的 adversarial checks，后者掩盖 compiler/state/master 也是安全边界。

**“每条 cut 可离线 replay”值得肯定；“replay 同一 adapter 就算独立”不可接受。** 能重现同一 bug 不等于验证 proof。

**“9 族预先封闭”不值得继续维护。** family taxonomy 可以指导研发，但算法发现、业务规则和 master 表达会变化，F8 已是现成反例。用 capability/version lock 代替数量 lock。

## 5. 问题 4：通电前最该做的三件事

### 第一件：封住不可逆 attach 边界

这是 P0。合入并审阅补丁 0001 至 0003：

* 完整性错误必须阻止 validator/Step 8/master mutation；Step 8 自身再守一次。
* 修复 ghost width/height，并永久保留非方形红测。
* scope artifact 依赖至少在 v1 做全等检查。
* rejection telemetry 必须按 integrity/scope/validator/evaluate/compiler/master 分类。

随后把生产调用收口为 RFC-001 的单一 typed API。晋升门必须包含恶意 body/cert 漂移、依赖删除、condition 错绑、compiler differential tests。仅靠 family 单测和“完整链 happy path”不够。

### 第二件：让 F5 proof 真正可独立验证，做不到就先关 F5

当前 F5 是最危险的 family，不是因为数学 idea 弱，而是因为 verifier 仍信同一 adapter。先把唯一生产 adapter 收窄为 `binding_empty_domain_v1` proof，用独立小匹配器验证；把 group operation mapping、operation profile、pose payload 全部纳入 proof/scope。删除 validator 的 registry lookup。

在此之前，F1/F6/F7 可以在完成第一件后进入受控 A/B；F5 只 shadow，不 attach。这样不会阻塞整个框架，同时诚实维持 Byzantine 模型。

### 第三件：把 lifecycle 从“内存记录”接到真实 model epoch

实现 RFC-003 最小版：append-only ledger、semantic dedup、model epoch、poison/rebuild、restart full replay、rollback drill。没有它，HOLD/QUARANTINE 对已经 Add 的约束只是标签。

使用刚打通的 batch0/C1 master 作为基线做 cut off/on A/B。batch0 已有完整 master OPTIMAL 和独立覆盖复验，可作为很好的等价基准。〔R/50_battle_record/batch0_power_encoding_result.md:L7-L17〕验收至少记录：objective/solution validity、generated/rejected/applied、family/reason、build time、solve time、branches、conflicts、peak RSS、rebuild time。任何 cut-on 结果都必须由 cut-off 独立验证器复验。

## 6. 是否应该推倒重建

**不建议把现有 9.6K 行全部推倒。** family validators、canonical helpers、source digest、master translators和大量 adversarial tests有可复用价值。真正需要替换的是 orchestration 与 trust boundary，而不是所有数学实现。

建议的目标形态：

```text
FailureEvidence
    -> untrusted family generator
    -> CutEnvelope(proof + exact scope)
    -> immutable ValidatedStateSnapshot
    -> independent family proof verifier
    -> typed ConstraintPlan
    -> master adapter + model epoch receipt
    -> append-only ledger + replay/rebuild
```

与当前相比，删掉的是 body/cert 双写、validator 回调 oracle、手工 gauntlet、proof/status 混装和 family 数量 lock；保留的是 family 数学、scope 思路、canonicalization、adversarial tests 和 master translation。

迁移量级估算：

* 本包四个补丁：评审和合入小于 1 人日，reseal/全门另计。
* typed gate + F1/F6/F7：3 至 5 人日。
* F5 专用独立 proof：2 至 4 人日；通用 proof-kind 4 至 7 人日。
* ledger/model epoch/dedup/rebuild：4 至 8 人日。
* capability manifest、schema v2、权威文档校准：2 至 4 人日。
* 完整替换 orchestration 的总量级：约 8 至 15 人日；若要求通用子求解器 formal proof，另加 1 至 3 周。

这些是代码规模与现有接口基础上的工程量级估算，不含 owner 审批、长跑 campaign 和 sealed artifact 全链时间。

## 7. Q1/Q2 CONCERN 到修改物的闭环表

| ID | 级别 | 发现 | 具体修改物 |
|---|---|---|---|
| A-2 | CONCERN | 实际 TCB 大于 validator | `design/RFC-001_trusted_cut_compiler_boundary.md` |
| A-3 | CONCERN | body/cert split-brain | patch 0001 + RFC-001 §3 |
| A-4 | CONCERN | F5 同一 adapter 重问 | `design/RFC-002_f5_independent_proof.md` |
| A-5 | CONCERN | scope 依赖可缺项、proof hash 截断 | patch 0003 + RFC-001 §4 |
| A-6 | CONCERN | 状态机不能撤回 model 约束 | `design/RFC-003_model_epoch_ledger_pool.md` |
| A-7 | CONCERN | 9-family 数量冻结 | RFC-001 §5 capability registry |
| A-8 | CONCERN | watcher 先于生产闭环 | RFC-003 §10 |
| I-1 | BLOCKER | 完整性错误被忽略 | patch 0001 + 恶意回归 |
| I-2 | BLOCKER | ghost 轴反置 | patch 0002 + 非方形回归 |
| I-3 | CONCERN | artifact omission 仍 ATTACH | patch 0003 |
| I-4 | CONCERN | F5 global registry/stale mapping | RFC-002 §§4-5 |
| I-5 | CONCERN | 生产手工 gauntlet 绕过 replay/store | RFC-001 §2/§6 + RFC-003 §7 |
| I-6 | CONCERN | proof 与 lifecycle status 双权威 | RFC-003 §4 |
| I-7 | CONCERN | mutable BState/raw tuple/TOCTOU | RFC-001 §7 |
| I-8 | CONCERN | 无 semantic dedup/selection | RFC-003 §§5-6 |
| I-9 | CONCERN | 文档和代码权威漂移 | RFC-001 §5 generated manifest |

每个 Q1/Q2 的 CONCERN 都有补丁或替换设计；本评审没有建议直接删除 family validator 数学实现。

## 8. 补丁验证结果

补丁序列在项目完整副本上逐个 `git apply --check` 通过，随后实际 apply。结果：

```text
cut + attach wiring tests: 452 passed
Ruff: All checks passed
mypy --strict --explicit-package-bases src/cuts:
  Success: no issues found in 33 source files
```

完整日志见：

* `evidence/patch_apply_and_test.txt`
* `evidence/patched_cut_and_wiring_tests.txt`
* `evidence/patched_ruff.txt`
* `evidence/patched_mypy.txt`

补丁 0004 仅修 bare generic 类型注解，属于工程卫生，不是前三个上线阻断项。

## 9. 文献与工程常规参考

1. J. N. Hooker, G. Ottosson, “Logic-based Benders decomposition,” Mathematical Programming, 2003. 核心是把 LP dual 推广为 inference dual，由逻辑推导产生 Benders cut。
2. T. L. Magnanti, R. T. Wong, “Accelerating Benders Decomposition: Algorithmic Enhancement and Model Selection Criteria,” Operations Research, 1981. 讨论 strong/Pareto-optimal cut 选择。
3. SCIP 官方文档，Hybrid Cut Selector。选择分数包含 efficacy、directed cutoff distance、objective parallelism、integer support，并做 parallelism filtering。
4. SCIP 官方文档，Cuts and Cutpools。global cut pool 支持 duplicate-aware add、删除与 age limit；官方默认参数也包含 cut age 和 pool frequency。

这些常规不是要求本项目照搬 LP cut manager，而是说明“soundness 验证”与“pool 质量管理”是两条不同轴。本项目第一轴投入很深，第二轴尚未开始形成生产闭环。
