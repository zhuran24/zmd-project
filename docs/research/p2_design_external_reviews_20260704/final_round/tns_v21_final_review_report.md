# Terminal 全域无解证书合同稿 v2.1 终审报告

审查对象：`docs/research/terminal_no_solution_evidence_contract_design_v2.md`，含 v2.1 修订。附件源码只读复核，未修改仓库工作树；输出另附统一 diff 与 patched 全文。

## 0. 总体判定

**v2.1 不能直接无条件通过。** 它已经修掉 v1 的大部分合同层空洞，但终审仍发现两个“文字可实现、机械防绕过不足”的缺口：

1. **BLOCK-2 负向复验硬门仍需再收紧并写进 public schema。** v2.1 在 `docs/research/terminal_no_solution_evidence_contract_design_v2.md:85-89` 把 P-TNS-H 变成 seal 硬前置，并要求独立模型路径或编码忠实性审计。这是正确方向，但仍有绕过面：实现可共用 canonical 规则解析/normalization 层，只在模型构造层“独立”；或者提交 opaque/manual audit receipt，但 public evidence 不绑定该 receipt/verdict digest。候选 replay 当前确实仍调用生产 `run_benders_for_ghost_rect`，只能防篡改，不能防同源建模错误：`src/search/candidate_proof_replay.py:890-922`。现有 `independent_infeasibility_reverifier.py` 明确是 whole-layout/nogood 局部复验，不是候选级全 anchor 空间 verifier：`src/search/independent_infeasibility_reverifier.py:1-14`、`src/search/independent_infeasibility_reverifier.py:69-89`。

2. **BLOCK-3 resume 例外方向正确，但必须变成 seal-only 状态机硬约束。** v2.1 在 `docs/research/terminal_no_solution_evidence_contract_design_v2.md:81` 加了 current-hash 前置与“只作 supervisor seal 输入”的声明，这与铁律可以相容；但实现合同还需要明确：保留态绝不能进入 `_compute_exact_frontier_state` / pruning / search / parallel scheduler。因为当前 frontier 计算会把 sink projection 写回 campaign state，随后用 projected `INFEASIBLE` 做逐维剪枝：`src/search/outer_search.py:632-657`、`src/search/outer_search.py:660-704`。一旦保留证据绕进 frontier，例外就不再窄。当前 resume 铁律和 sanitizer 的基线是先校验 hash，再 demote checkpoint-loaded strong status：`src/search/exact_campaign.py:2408-2411`、`src/search/exact_campaign.py:2898-2918`、`src/search/exact_campaign.py:2160-2236`；`PROJECT_LOCK.md:276-284` 也明确 checkpoint-loaded strong status 必须 fresh replay。

分层结论：

| 层 | 判定 | 终审理由 |
|---|---|---|
| 引理层 | **可靠，但必须绑定 inventory 和 full_unfiltered anchor 前提** | visible master 代码中 ghost-conditioned power/signature tightening 都是“缩小 R 不收紧”；没有发现反向收紧点。但附件缺 `routing_subproblem.py` 与 `pr2_l0_frontier_core.py`，routing 零 ghost 与正向 validator 行号不能从本包复现，必须由 source-digest-bound inventory 兜底。 |
| 合同层 | **修后可靠** | v2.1 的 schema 还缺 sealed public negative reverification / supervisor seal / projection digest 的强绑定链。补丁把 `proposal_core` 与 `sealed_public` 分层，并升 schema。 |
| 接线层 | **修后可靠** | current-hash 前置已补，但 seal-only resume、TNS unsupervised writer guards、manifest-only no-solution publisher 仍需写成硬门。补丁覆盖 §4.1、§4.2、§4.3、§6。 |

## 1. v1 审查项逐项终验

### BLOCK-1：authoritative full domain

**终审判定：FIXED，补丁做显式 schema 加固。**

v1 要求 TNS 必须绑定 authoritative full domain，不能接受 sliced domain：`docs/research/p2_design_external_reviews_20260704/tns_adversarial_review_gpt.md:24-32`。v2.1 已在 schema 写入 `domain_scope="authoritative_full_domain_v1"` 与 authoritative 参数：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:56-57`，验证流程拒 `start_area`、`max_aspect_ratio`、抬高 `min_side`、非 safe `area_upper_bound`：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:69-71`。现有 outer search 的 candidate_generation snapshot 覆盖 grid、min_side、max_aspect_ratio、area_upper_bound、start_area、domain_authority、safe_area_upper_bound、min_side_admissibility：`src/search/outer_search.py:1831-1861`。

**剩余可加固点。** v2.1 用自然语言说“闭合合同”，但 public schema 未列 exact allowlist、`domain_contract_digest` 与 normalized authoritative domain 的绑定。补丁把 §3 的 `candidate_generation` 展开成 exact object，并增加 `domain_contract_digest`。

**修复补丁。** 见 `tns_v21_final_review_contract.patch` 对 §3 的替换：`schema_version=3`、`domain_contract_digest`、`candidate_generation` exact allowlist、strict validator step 1-3。

### BLOCK-2：candidate-wide negative reverifier hard gate

**终审判定：PARTIAL as-is，补丁后可靠。**

v2.1 把 P-TNS-H 升成 hard gate：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:85-89`。这修正了 v1 把异构复验当增强选项的问题，符合 v1 review 的 hard gate 要求：`docs/research/p2_design_external_reviews_20260704/tns_adversarial_review_gpt.md:36-44`。

**但强度仍差一枚铆钉。** v2.1 允许“独立模型构造路径 or 编码忠实性审计回执”。这个强度作为理念足够，但文字必须排除两个绕过面：

- 独立模型路径如果仍 import 生产 canonical 规则解析/normalization helper，就可能共享系统性误读。终审补丁要求复验器只能读 raw locked artifacts，由独立 strict parser 生成自己的 normalized fact set；共享项只能是 raw artifact bytes、hash 函数、CP-SAT kernel 等命名 TCB。
- 编码忠实性审计不能是人工自由文本或 opaque receipt。它必须机器可验证，绑定 raw artifact digest、独立 parser/fact digest、生产 source digest、覆盖候选、逐约束族 inventory、expected-vs-encoded 对照摘要、审计工具 digest 与签名/时间戳。

当前同管线 replay 的边界只承诺 fresh isolated interpreter 和当前 source/artifact hash，但仍调用同一个 production solve entry：`src/search/candidate_proof_replay.py:1-15`、`src/search/candidate_proof_replay.py:903-922`。`independent_infeasibility_reverifier.py` 只在 whole-layout nogood/binding 子问题上重建，并使用异构 CP-SAT profile：`src/search/independent_infeasibility_reverifier.py:69-89`、`src/search/independent_infeasibility_reverifier.py:146-180`、`src/search/independent_infeasibility_reverifier.py:220-246`。这不能替代候选 `(w,h)` 全 anchor/layout 空间的负向复验。P1.2 明确 proof-bearing false-INFEASIBLE 严重度不低于 false-CERTIFIED：`docs/项目说明/08_phase_1_2_plan.md:17-24`（附件中该目录名有编码漂移，但文件内容可读）。

**修复补丁。** 见 patch 对 §3 与 §4.2 的替换：新增 `negative_reverification`、`independence_kind`、`canonical_rule_input_digest`、`reverifier_source_digest`、`encoding_fidelity_audit_digest`、`verdict_digest`；§4.2 明确 `independent_model_path_v1` 不得 import 生产 master/binding/routing 构造器，也不得 import 生产 canonical parser/normalizer；`encoding_fidelity_audit_v1` 必须机器可验证。

### BLOCK-3：NO_SOLUTION_PROPOSED resume/proposal 生命周期

**终审判定：PARTIAL as-is，补丁后可靠。**

v2.1 已补 proposal marker、checkpoint hash、domain authority、current hash 前置与 seal-only 声明：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:78-82`。这比 local report 的 PARTIAL 状态更进一步，方向正确。

**严格相容性判断。** 这个例外可以与 checkpoint 强状态 fresh replay 铁律相容，但只有在例外面被压到“marker 绑定 bytes → L0 seal input”这一条缝里。当前基线是：`_validate_resume_state` 要求 artifact_hashes 等于 current_hashes，hash mismatch 直接拒绝：`src/search/exact_campaign.py:2356-2411`；loader 在 resume 时先算 current hashes 并校验：`src/search/exact_campaign.py:2898-2918`；sanitizer 对非 `CANDIDATE_PROPOSED` 的 checkpoint-loaded strong statuses 降为 UNKNOWN、删 solution/proof/cuts、清 terminal evidence：`src/search/exact_campaign.py:2160-2236`。`PROJECT_LOCK.md:276-284` 明确这是 proof authority 边界。

**保留态泄漏路径。** v2.1 说“绝不进入 search/pruning/frontier 状态”，但还没有把该声明变成可测试的状态机门。当前 `_compute_exact_frontier_state` 会先执行 sink projection，然后把 projection 写回 campaign state：`src/search/outer_search.py:632-657`；随后把 projected `INFEASIBLE` 收入 explicit_infeasible 并用 `ghost_w >= inf_w and ghost_h >= inf_h` 剪枝：`src/search/outer_search.py:660-704`。所以 `NO_SOLUTION_PROPOSED` resume 后若返回普通 campaign 对象，保留的覆盖 proof 仍有泄漏进 frontier 的路径。补丁要求 loader 返回 seal-only handle；若调用方要继续搜索，必须先正常卫生降级并持久化。

**修复补丁。** 见 patch 对 §4.1 的替换：`proposal_core` 只可作为 supervisor seal input；hash/marker/checkpoint/domain 全绑定；保留态不能进入 `_compute_exact_frontier_state`、search/pruning/frontier、parallel scheduler、`mark_candidate_result`、普通 `save()` 或 publisher；继续搜索前必须 demote/clear/persist。

### BLOCK-4：sink-projected records only

**终审判定：FIXED，补丁做 digest 承重加固。**

v1 要求验证只消费 sink-projected records：`docs/research/p2_design_external_reviews_20260704/tns_adversarial_review_gpt.md:60-68`。v2.1 在 schema 加了 `covering_candidate_proof_digests` 与 `sink_replay_projection_digest`：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:63-65`，验证流程明确对域内 present strong records 跑 `project_candidate_records_for_sink`，覆盖 key 必须 projected INFEASIBLE，projected CERTIFIED 必拒：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:72`。

源码支持这一边界：candidate record 只是 claim，sink replay 才是 authority：`src/search/candidate_proof_replay.py:1-15`；proof shape 绑定 key、record.ghost_rect、status、artifact/source/campaign context、solution digest/request digest：`src/search/candidate_proof_replay.py:304-426`；replay mismatch 会拒绝：`src/search/candidate_proof_replay.py:508-560`；projection 会把未被 sink 接受的 strong status 降为 `UNPROVEN` 并删 proof/solution：`src/search/candidate_proof_replay.py:564-608`。

**剩余可加固点。** v2.1 没明确 proof digest 必须来自“projected record”，也没明确 projection digest 要绑定 projected statuses、proof digests、empty replay violations。补丁补齐。

**修复补丁。** 见 patch 对 §3 validator step 4 与 `sink_replay_projection` object 的替换。

### CONCERN-1：ghost-use inventory 与 lemma 谓词方向

**终审判定：FIXED for visible master paths；但 routing/core 缺文件，必须 inventory-bound。**

v2.1 已把 ghost-use inventory 写进 §2.1：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:24-39`，并点名 master 中的 ghost-conditioned power/signature tightening：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:39`。我逐行复核了附件中的 `src/models/exact_coordinate_master.py`，没有发现“缩小 R 反而收紧”的路径。

关键源码判断如下：

- ghost anchor 枚举在 `_add_ghost_constraints` 中按 `range(grid_w - ghost_w + 1)` / `range(grid_h - ghost_h + 1)` 全枚举，且 campaign domain contract 要求 `ghost_anchor_domain="full_unfiltered"`、`ghost_anchor_filter=None`：`src/models/exact_coordinate_master.py:3693-3708`、`src/search/exact_campaign.py:229-262`。缩小矩形保留大矩形同锚，anchor 域不收紧。
- ghost optional intervals 进入 `AddNoOverlap2D`，并 `AddExactlyOne` 选一个 anchor：`src/models/exact_coordinate_master.py:3709-3724`、`src/models/exact_coordinate_master.py:3741-3748`。缩小 R 让 no-overlap 放松；选一不变。
- power capacity screen 用 `domain.cells` 统计被 ghost 挡住的 pose/family：`src/models/exact_coordinate_master.py:3882-3896`。`available_count = family_size - blocked_counts`，容量不足才禁用 anchor：`src/models/exact_coordinate_master.py:3934-3946`；条件上界取 `min(max(0, available_count), global_upper_bound)`：`src/models/exact_coordinate_master.py:3973-3988`。缩小 R 使 blocked_counts 不增、available_count 不降，所以禁用/上界不会更强。
- mandatory region helper 的 block 矩形由 ghost_x/y/w/h 推出：`src/models/exact_coordinate_master.py:1491-1548`。缩小 ghost 只会缩小被挡区域。
- signature tightening 的 mandatory bucket、required optional bucket、residual bucket 都按同一 `available_count` 模式加 upper bound：`src/models/exact_coordinate_master.py:4748-4762`、`src/models/exact_coordinate_master.py:4822-4835`、`src/models/exact_coordinate_master.py:5054-5068`。方向同样是缩小不收紧。
- ghost decision strategy 与 hint 只影响搜索顺序或 hint，不改变可行域：`src/models/exact_coordinate_master.py:6444-6489`、`src/models/exact_coordinate_master.py:6870-6879`。

**重要限制。** 附件包内不存在 `src/search/pr2_l0_frontier_core.py` 与 `src/search/routing_subproblem.py`，但 v2.1 和 local report 都引用它们；`certified_frontier.py` 也只是 import missing core：`src/search/certified_frontier.py:1-7`、`src/search/certified_frontier.py:14-34`。因此 routing “零 ghost 引用”与正向 frontier validator 的行号不能从本包独立复现。结论应写成：可见 master 路径可靠；routing/core 必须由 source-digest-bound ghost-use inventory 证明，缺文件/未分类时 fail-closed。

**修复补丁。** 见 patch 对 §2.1 的替换：新增 full_unfiltered/ghost_anchor_filter 前提、逐源码面表、inventory 分类 allowlist，以及“源码包缺 routing 时不得用研究稿断言替代 inventory”。

### CONCERN-2：oriented key / transpose / canonicalization

**终审判定：FIXED，补丁做 strict key 与 digest 绑定加固。**

v2.1 已写 `dimwise_ge_oriented_v1`，禁止 transpose、禁止 `(min,max)` canonicalize，key 与 tuple/record.ghost_rect 三方一致：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:41-43`。源码也以 oriented key 写出 `f"{w}x{h}"`：`src/search/exact_campaign.py:1555-1556`；frontier 对 INFEASIBLE 的支配剪枝是同向逐维 `ghost_w >= inf_w and ghost_h >= inf_h`：`src/search/outer_search.py:699-704`。

**一般域边角。** 在 standard domain 6..70 × 6..70 中最小元确实是 `(6,6)`；但非对称 floor、`start_area`、aspect filter 等一般域下，最小元反链可能有多个元素。终审随机检查 5000 个有限 oriented 域，正确 antichain 覆盖无洞；但 singleton floor collapse 会在如 `D={(6,7),(7,6)}` 且 `C={(6,7)}` 时漏掉 `(7,6)`。v2.1 的 standard-domain singleton 结论没问题，未来若开放 sliced/general domain，必须计算实际最小反链。

**修复补丁。** 见 patch 对 §3 validator step 3 与 O-8 的替换：strict regex、无前导零、三方一致、禁止转置/面积/集合支配。

### CONCERN-3：MISSING vs UNKNOWN audit semantics

**终审判定：FIXED，补丁补红测与 digest 语义。**

v1 的问题是把非覆盖候选写成 `UNKNOWN`，外审要求区分 sparse absence 与 real UNKNOWN record：`docs/research/p2_design_external_reviews_20260704/tns_adversarial_review_gpt.md:96-104`。v2.1 已改为 `MISSING:4224`：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:60-62`，并声明 counts/digest 只做 audit，不承担覆盖证明：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:73`。

**剩余可加固点。** v2.1 的 O-list 已加 O-13：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:111`，但标题仍写 O-1~O-12：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:102`。补丁把 O-13 展开成 “合法 sparse 接受；合成 UNKNOWN 占位 record 无 timestamp/schema 必拒”，并让 `candidate_status_digest` 绑定 domain order、projected statuses、cover/proof/projection digest。

**修复补丁。** 见 patch 对 §3 validator step 6 与 §6 O-13 的替换。

### CONCERN-4：manifest-only publisher / stale positive artifacts

**终审判定：FIXED conceptually，补丁后 public surface 闭合。**

v2.1 已要求 manifest 新增 `no_solution_evidence`，与 `best_certified_result` 互斥，并删除/拒绝旧 `final_solution.json`、`optimal_blueprint.json`：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:91-95`。

当前源码 public surface 仍是 positive-only：manifest builder 对 certified surface 要求 strict mode、final_result 与 terminal evidence：`src/io/delivery_manifest.py:123-142`；直接 manifest 写会拒绝 `best_certified_result` 非空：`src/io/delivery_manifest.py:228-274`；artifact validator 要 final_result、final_solution、optimal_blueprint 三者一致：`src/io/delivery_manifest.py:550-587`；best_certified_result payload 只构造 CERTIFIED 结果：`src/io/delivery_manifest.py:812-860`。publisher 也会写 final_solution、blueprint、manifest 三件套，并要求 terminal full frontier CERTIFIED 和 final_result：`src/search/certified_surface.py:607-649`、`src/search/certified_surface.py:758-853`。

**剩余可加固点。** manifest 必须只接受 `sealed_public` no_solution_evidence，而不是 producer 的 `proposal_core`。补丁加了 sealed evidence digest/currentness 复算要求。

**修复补丁。** 见 patch 对 §4.3 的替换：`no_solution_evidence` 只接受 sealed_public，positive artifacts 必须 absent/null，currentness 重算 checkpoint/source/artifact/projection/negative reverification digest。

### CONCERN-5：O-1~O-15 mapping and red tests

**终审判定：PARTIAL as-is，补丁后可靠。**

v2.1 已列出 O-13~O-15：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:111-113`，但标题仍是 O-1~O-12：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:102`。另外，schema/sealed binding chain 还没有独立红测：改 cover key、proof digest、projection digest、negative reverification digest、proposal checkpoint hash 中任一字段，manifest/inspector/L0 validator 都应拒绝。

现有 direct-writer guard 只挡 CERTIFIED，不挡 terminal `INFEASIBLE + TNS evidence`：`src/search/exact_campaign.py:2545-2560`、`src/search/exact_campaign.py:3583-3592`。`mark_campaign_stopped` 也只禁止直接 mint CERTIFIED，非 CERTIFIED 状态可普通写入：`src/search/exact_campaign.py:3532-3564`。这正是 O-15 需要落地的点。parallel/coordinator-only writer 是锁面要求：`PROJECT_LOCK.md:280-286`，outer search parallel wave 入口也存在独立路径：`src/search/outer_search.py:2153-2190`。

**修复补丁。** 见 patch 对 §6 的替换：标题升为 O-1~O-16，逐项映射 v1 NOTE/BLOCK/CONCERN，并新增 O-16 sealed-evidence binding chain。

## 2. v2.1 新缺陷狩猎

### 新缺陷 A：schema 里没有 sealed public negative reverification 绑定链

v2.1 schema 顶层只到 `sink_replay_projection_digest`：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:51-65`，而 §4.2 才在文字里说 negative reverifier 是 hard gate：`docs/research/terminal_no_solution_evidence_contract_design_v2.md:85-89`。这造成 public evidence 与 hard gate 之间没有可重放 digest 绑定。补丁新增 `proposal_core | sealed_public`、`negative_reverification` 与 `supervisor_seal` 对象。

### 新缺陷 B：独立性可能被共享 canonical parser 系统性误读绕过

v2.1 的“独立模型构造路径”未明确禁止 import 生产 canonical 规则解析/normalization。若 canonical parser 把规则字段误读为更严，生产与 verifier 即便构造器不同也会同错。补丁要求独立 strict parser 从 raw locked artifacts 生成 fact set；或机器可验证 encoding fidelity audit 绑定 raw artifact digest 与 expected-vs-encoded 对照。

### 新缺陷 C：resume 保留态存在 frontier 泄漏路径

v2.1 文字声明 seal-only，但没有把可调用面列成拒绝清单。当前 `_compute_exact_frontier_state` 会投影并持久化 candidate records，然后利用 projected INFEASIBLE 剪枝：`src/search/outer_search.py:632-704`。补丁要求 seal-only handle；继续搜索前必须卫生降级。

### 新缺陷 D：源码包 reviewability 漂移

`src/search/certified_frontier.py` 明确核心在 `pr2_l0_frontier_core`：`src/search/certified_frontier.py:1-7`，并 import 该文件：`src/search/certified_frontier.py:14-34`，但附件中该文件不存在；`routing_subproblem.py` 也不存在。local report 对这两份文件的行号不能在本包复核。补丁将这类事实改成 function/source-digest/inventory 锚，不允许靠研究稿断言。

### 新缺陷 E：一般域 minimal antichain 不是 singleton

我写了一个小覆盖检查器，对 5000 个随机 oriented 有限域做 minimal antichain 覆盖验证，没有发现 antichain 规则本身的洞；但多个随机域的最小元反链有 3~11 个元素。例：`min_w=6,min_h=6,start_area=49,max_w=max_h=12` 的最小元是 `(6,9),(7,7),(9,6)`。因此 standard authoritative domain 可以坍缩为 `(6,6)`；一旦未来放开 sliced/general domain，就必须计算 actual minimal antichain，不能沿用 floor-pair singleton。

## 3. 补丁产物

本终审生成了两份补丁产物：

- `tns_v21_final_review_contract.patch`：对 v2.1 文档的统一 diff。
- `terminal_no_solution_evidence_contract_design_v2_review_patched.md`：应用补丁后的完整合同稿。

补丁覆盖关系：

| 审查项 | 补丁落点 |
|---|---|
| BLOCK-1 | §3 schema / validator step 1-3 |
| BLOCK-2 | §3 `negative_reverification` + §4.2 independent model / audit hard gate + O-11/O-16 |
| BLOCK-3 | §4.1 seal-only resume lifecycle + O-9/O-15 |
| BLOCK-4 | §3 `sink_replay_projection` + validator step 4 + O-10 |
| CONCERN-1 | §2.1 ghost-use inventory table + O-5/O-6 |
| CONCERN-2 | §3 key rule + validator step 3 + O-8 |
| CONCERN-3 | §3 candidate_status_digest + validator step 6 + O-13 |
| CONCERN-4 | §4.3 sealed_public manifest-only publisher + O-12 |
| CONCERN-5 | §6 O-1~O-16 complete mapping |

## 4. 最终建议

可以把 v2.1 作为“修后可靠”的实现合同底稿，但不要按原文直接进实现。应先应用随附 patch，尤其是三处硬化：

1. public schema 必须区分 `proposal_core` 与 `sealed_public`，并绑定 negative reverification / supervisor seal digest。
2. candidate-wide negative verifier 的独立性必须落到 raw artifact 独立解析或机器可验 encoding audit，不允许共享生产 canonical parser 的系统性误读。
3. `NO_SOLUTION_PROPOSED` resume 例外必须是 seal-only handle，不能返还普通 search/pruning/frontier 可消费状态。
