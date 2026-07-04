# Terminal 全域无解证书合同设计稿 v2

**Status:** HISTORICAL_OR_PLAN（研究层设计稿，不改生产代码/锁面）
**Authored:** 2026-07-04（v2，取代 `terminal_no_solution_evidence_contract_design_v1.md`；同日 v2.1 修订——本地独立核查回收：负向复验门的独立性收紧到编码路径层、resume 例外补 currentness 前置、红测补 O-13~O-15、引用改函数名锚定）
**v2 修订输入**：GPT Pro 对抗审查（4 BLOCK + 5 CONCERN + 2 NOTE，归档 `p2_design_external_reviews_20260704/tns_*`）。审查总判定：引理层修后可靠、合同层与接线层需重设计——v2 按此重做后两层。

**v1→v2 关键变更**：
- 【BLOCK-1】证据必须绑定 **authoritative full domain**：拒绝一切 sliced domain（start_area / max_aspect_ratio / 抬高 min_side / 非 safe area_upper_bound）——正向 terminal validator 本就这么做，负向侧更不能松。
- 【BLOCK-2】**P-TNS-H 从"增强选项"升为 seal 硬前置**：同管线 replay 防篡改不防系统性 false-INFEASIBLE；新增 `candidate_wide_no_solution_reverifier_v1`（异构 profile 负向复验），只有 `CONFIRMED_INFEASIBLE` 可 seal。
- 【BLOCK-3】补全 `NO_SOLUTION_PROPOSED` 的 **resume/marker/seal 生命周期**（v1 完全没写，现有 resume sanitizer 会把证据清掉）。
- 【BLOCK-4】验证器只消费 **sink-projected** 记录（raw record 是 claim 不是 grant）；证据增加 replay projection 与 proof digest 绑定。
- 【CONCERN-1】引理证明修正：routing 对 ghost **独立**（`routing_subproblem.py` 全文零 ghost 引用，belts 可穿过空矩形）——v1"routing 避开 ghost"表述错误；前提改为机器可查的 **ghost-use inventory**。
- 【CONCERN-2~5】oriented key 纪律入 schema、MISSING 审计语义、manifest-only 发布面的 stale 清理与互斥、红测扩为 O-1~O-12。

---

## 1. 事实基线（v1 §1 继承，补两条）

- 正向 terminal validator 已拒 sliced domain（函数 `resolve_terminal_frontier_evidence_error` 的域校验段：start_area/max_aspect_ratio/非 authoritative min_side/非 safe area_upper_bound 均拒；行号锚提示——2026-07-04 起 frontier 核心在重构中，该逻辑可能从 `certified_frontier.py` 迁至 `pr2_l0_frontier_core.py`，以函数名与语义为锚）——负向侧的 BLOCK-1 有现成镜像。
- 现有 `_candidate_status_digest` 对缺失记录用 `_MISSING_STATUS` 表示——稀疏证据是既有风格（CONCERN-3 的落点）。

## 2. 数学骨架（引理修正版 + 覆盖坍缩保留）

### 2.1 引理（逐维反单调）——证明前提表修正

**命题**不变：(w,h) 不可行 ⇒ 一切 (w'≥w, h'≥h) 不可行。

**证明（修正版）**：设 (w',h') 有可行解 (R',π\*,B\*,S\*)，取 R ⊆ R' 的同锚 w×h 子矩形。实施前提是 `master_domain_contract.ghost_anchor_domain="full_unfiltered"` 且 `ghost_anchor_filter=null`；否则同锚缩小不一定仍在 anchor 域内，TNS 必须 fail-closed。逐谓词的 ghost 依赖盘点如下。

| 谓词/源码面 | 对 R 的依赖 | 缩小 R 的效果 |
|---|---|---|
| ghost anchor 枚举 + 选一 | 全 anchor 枚举；`AddExactlyOne(u)` 只要求选一个 ghost anchor | 小 R 的 anchor 域包含大 R 同锚；选同锚即可，不收紧 ✓ |
| ghost 空/排设施 | ghost optional interval 进入 `AddNoOverlap2D`，等价于设施不得占用 R | R⊆R' ⇒ no-overlap 约束放松 ✓ |
| power capacity screen | 以 `domain.cells` 统计被 ghost 挡住的 pole pose/family；若容量不足则禁用该 anchor，或给 family count 加条件上界 | 缩小 R 只会减少 blocked_counts、增大 available_count；禁用和上界均不更强 ✓ |
| mandatory signature bucket | 以 `domain.cells` 或 region counting 统计被挡 mandatory pose，再加 `count_var <= conditioned_upper_bound + M(1-u)` | blocked_counts 不增、conditioned_upper_bound 不降；约束放松/消失 ✓ |
| required-optional signature bucket | 同上，统计 required optional pose bucket | 同上 ✓ |
| residual signature bucket | 同上，统计 residual optional pose bucket | 同上 ✓ |
| routing | 现行证明只能把 routing 作为「独立于 ghost」或「ghost 只作障碍/排空」的 inventory 条目接受；源码包缺 routing 文件时不得用本文断言替代 inventory | 不变或放松 ✓ |
| decision strategy / hint / telemetry | 只影响搜索顺序或统计 | 不改变可行域 ✓ |
| (P7 前瞻) | selected graph 与 R 无耦合，或 R 缩小使可用格不减 | 不收紧 ✓ |

故 (R,π\*,B\*,S\*) 可行 ⇒ (w,h) 可行，矛盾。∎

**前提的机器化（CONCERN-1）**：引理依赖「没有任何谓词对 ghost 做正向（存在性/接触性）引用」。实施时必须生成 **ghost-use inventory**，逐条登记 `ghost_rect` / `_ghost_domains` / `u_vars` / `domain.cells` / ghost anchor hint 的所有消费点、方向性、源码 digest、工具版本与分类理由。分类只允许：排空/避障/上界削弱/无关；存在性/接触性/unknown 一律 fail-closed。inventory 必须覆盖 master 中的 ghost 条件化 tightening，不得只 grep no-overlap/routing：`_add_ghost_constraints` 的 anchor 枚举、`AddExactlyOne`、`AddNoOverlap2D`；`_apply_ghost_anchor_power_capacity_screen` 的 anchor 禁用和 family 上界；`_apply_ghost_anchor_signature_bucket_tightening` 的 mandatory / required-optional 上界；`_apply_ghost_anchor_residual_signature_bucket_tightening` 的 residual 上界；以及 ghost decision strategy / hint。漏登记 = 引理前提无据。v1 的 O-5（PROJECT_LOCK F-* 条款）保留，inventory 是它的机器面。

### 2.2 最小覆盖证书（保留，加 oriented 纪律）

覆盖集 C = D 的逐维最小元反链的 replay-verified INFEASIBLE；标准域下 C = {(6,6)}，证书 O(1)。**oriented 纪律（CONCERN-2）**：支配规则命名 `dimwise_ge_oriented_v1`——同向逐维比较、禁止转置、禁止 (min,max) canonicalize、禁止面积/集合支配替代；key 严格 `^[1-9][0-9]*x[1-9][0-9]*$` 且与 tuple/record.ghost_rect 三方一致。反例警示：域含 6x7 与 7x6 时，{6x7} **不**覆盖 7x6。

### 2.3 触发条件、互斥、退化域

同 v1（potential_domain 空 ∧ 无 best_certified；任一 projected CERTIFIED 与 TNS 并存 = 矛盾态拒绝；空域 = `terminal_no_solution_domain_empty` 拒绝，空洞真不是无解证明）。

## 3. 证据 schema 与验证器（BLOCK-1/2/4、CONCERN-2/3 修订版）

TNS 必须分成两个对象：`proposal_core` 是 producer 提交给 supervisor 的 seal 输入，**不可公开发布**；`sealed_public` 是 supervisor 在 L0 隔离中完成 sink replay + negative reverification 后铸出的公开证据。新增强字段属于 schema 破坏性变化，实施时必须触发 O-4 的 schema 升版连锁；若继续沿用整数版本，建议升到 `schema_version=3`。

```json
{
  "schema_version": 3,
  "source": "certified_terminal_no_solution_evidence_v3",
  "evidence_kind": "proposal_core | sealed_public",
  "reason": "search_exhausted_all_candidates_infeasible",
  "domain_scope": "authoritative_full_domain_v1",
  "candidate_generation": {
    "domain_authority": "<authoritative terminal frontier domain authority>",
    "max_w": 70,
    "max_h": 70,
    "min_side": 6,
    "min_side_admissibility": 6,
    "area_upper_bound": "<safe_area_upper_bound>",
    "safe_area_upper_bound": "<safe_area_upper_bound>",
    "start_area": null,
    "max_aspect_ratio": null
  },
  "domain_contract_digest": "<canonical digest of the normalized authoritative domain contract>",
  "monotone_dominance_rule": "dimwise_ge_oriented_v1",
  "candidate_key_rule": "strict_w_x_h_no_leading_zero_v1",
  "ghost_use_inventory_digest": "<machine checked inventory digest bound to source_digest>",
  "candidate_domain_size": 4225,
  "candidate_status_counts": { "INFEASIBLE": 1, "MISSING": 4224 },
  "candidate_status_digest": {
    "algorithm": "terminal_no_solution_candidate_status_digest_v1",
    "digest": "<full-domain audit digest over canonical domain order and projected statuses>"
  },
  "covering_infeasible_keys": ["6x6"],
  "covering_candidate_proof_digests": { "6x6": "<digest of the projected record's candidate_proof>" },
  "sink_replay_projection": {
    "algorithm": "project_candidate_records_for_sink_v1",
    "projection_digest": "<digest over projected cover records, projected statuses, proof digests, and empty replay violations>",
    "projected_covering_statuses": { "6x6": "INFEASIBLE" },
    "replay_violations_digest": "<canonical digest of {}>"
  },
  "negative_reverification": null,
  "supervisor_seal": null
}
```

`sealed_public` 证据必须把 `negative_reverification` 与 `supervisor_seal` 填成非空对象；`proposal_core` 必须保持二者为 null，且任何 publisher/manifest/inspector 看到 `proposal_core` 都必须拒绝。

```json
{
  "negative_reverification": {
    "algorithm": "candidate_wide_no_solution_reverifier_v1",
    "independence_kind": "independent_model_path_v1 | encoding_fidelity_audit_v1",
    "canonical_rule_input_digest": "<raw canonical rules / generic I/O / locked artifact digest set>",
    "reverifier_source_digest": "<digest of the independent verifier or audit checker>",
    "encoding_fidelity_audit_digest": null,
    "verdicts": { "6x6": "CONFIRMED_INFEASIBLE" },
    "verdict_digest": "<canonical digest of verdicts + independence manifest>"
  },
  "supervisor_seal": {
    "transition": "proposal_to_terminal_infeasible_v1",
    "proposal_checkpoint_sha256": "<sha256 of exact proposal bytes>",
    "sealed_state_sha256": "<sha256 of sealed terminal INFEASIBLE checkpoint>",
    "sealed_public_evidence_digest": "<digest of this sealed_public evidence without this field>"
  }
}
```

**验证器流程（全部重算、不信 producer）**：
1. **strict schema**：evidence 顶层、`candidate_generation`、`sink_replay_projection`、`negative_reverification`、`supervisor_seal` 均使用 exact allowlist；未知字段、重复 key、非规范整数、key 前导零、覆盖 key 重复或 map key 集不等于 cover set ⇒ 拒绝。
2. **域 authority 检查（BLOCK-1）**：`candidate_generation` 必须逐字段等于 authoritative 生产参数：`min_side == min_side_admissibility == canonical admissibility`，`max_w/max_h == grid`，`area_upper_bound == safe_area_upper_bound == safe bound`，`start_area == null`，`max_aspect_ratio == null`，`domain_authority` 与当前锁面一致；域非空。任何 sliced 形态直接拒。
3. 重算 `generate_candidate_sizes`；覆盖检查按 `dimwise_ge_oriented_v1` 全域逐候选验证「∃ c∈C: w≥c_w ∧ h≥c_h」。覆盖 key 必须属于域，严格按 `^[1-9][0-9]*x[1-9][0-9]*$` 解析，且 key / tuple / projected record.ghost_rect 三方一致，禁止转置或 `(min,max)` canonicalize。
4. **sink projection（BLOCK-4）**：对域内全部 present strong records 运行 `project_candidate_records_for_sink`，只消费投影后记录。覆盖 key 必须投影后仍为 `INFEASIBLE`，且 `covering_candidate_proof_digests` 必须来自投影后 record 的 `candidate_proof`，不是 raw record。任一投影后 `CERTIFIED` 在域内 ⇒ 拒绝。重算 `sink_replay_projection.projection_digest`，并要求 replay violations 为空或仅包含非承重记录且不会改变覆盖/互斥结论；覆盖记录出现任何 violation ⇒ 拒绝。
5. **negative reverification（BLOCK-2）**：`sealed_public` 必须重算并匹配 `negative_reverification.verdict_digest`，每个覆盖 key 的 verdict 只能是 `CONFIRMED_INFEASIBLE`；`proposal_core` 必须没有该字段内容且不可发布。
6. counts/digest 一致性：`MISSING` 是合法审计状态；非覆盖候选无须合成占位 record。present record 仍须过 record schema；合成的无 timestamp / 无 schema `UNKNOWN` 占位不得通过。`candidate_status_digest` 必须绑定 authoritative domain order、projected statuses、cover set、proof digests 与 projection digest，不能只是 producer 填的状态字符串摘要。
7. ghost-use inventory digest 一致（§2.1），且 inventory 的 source/artifact digest 与 `candidate_proof` / reverifier 输入一致。

## 4. 三权分立接线（BLOCK-2/3、CONCERN-4 重做版）

### 4.1 producer：`NO_SOLUTION_PROPOSED` 生命周期（BLOCK-3）

- 终止分支产出 `final_status=NO_SOLUTION_PROPOSED` + `terminal_no_solution_proposal_evidence`（§3 的 `evidence_kind="proposal_core"`）+ **专用 proposal marker**（schema_version / authority=`certified_exact_no_solution_proposal_ready_v1` / run_id / exit_code / **checkpoint_sha256** / campaign_instance_id）。`final_result` 恒为 None，且不得写 positive `terminal_frontier_evidence`、candidate solution、`best_certified_result` 或 delivery artifacts。
- **resume 规则**：`NO_SOLUTION_PROPOSED` checkpoint 载入时，必须先通过现有 resume validation 的 current source/artifact hash 校验；hash 不符按现有语义直接拒，不进入保留分支。通过后，若 marker 存在且 checkpoint_sha256 与磁盘 bytes 一致、domain authority 校验通过、proposal evidence 为 `proposal_core` 且 schema/cover/proof digest 自洽，则证据与覆盖 proof 可原样保留，**但 loader 必须返回 seal-only 状态**：只能调用 supervisor seal，不能进入 `_compute_exact_frontier_state`、search/pruning/frontier、parallel scheduler、`mark_candidate_result`、普通 `save()` 或 publisher。若调用方要继续搜索，必须先执行正常 resume 卫生：覆盖 proof 降级为 UNKNOWN、TNS proposal/evidence/marker 清空并持久化。任一绑定不符 ⇒ 整体降级 UNKNOWN + 证据清空 + 走正常 resume 卫生。
- 该例外与「checkpoint-loaded strong status 必须 fresh replay」的相容边界是：保留态不是 proof authority，只是 L0 seal 的输入 bytes；L0 必须从 marker 绑定的 checkpoint bytes 重新做 sink replay 与 negative reverification，不能消费 caller-held in-memory mapping。resume validation 新分支必须要求 `NO_SOLUTION_PROPOSED` 有 proposal evidence、无 final_result、无 candidate solution 残留、无 stale positive artifacts。

### 4.2 supervisor：负向复验硬门（BLOCK-2）

`supervisor_seal` 第二路径 `proposal_to_terminal_infeasible_v1`，L0 隔离内依次：
1. 从 marker 绑定的 checkpoint bytes 载入 authority state，复验 checkpoint_sha256、campaign_instance_id、proposal authority、current source/artifact hash、domain authority；禁止使用 in-memory state 作为 authority。
2. 执行 §3 `proposal_core` 验证器全流程，含覆盖集 sink replay、proof digest、projection digest、candidate_status_digest 与 ghost-use inventory digest 重算。
3. **`candidate_wide_no_solution_reverifier_v1`（硬前置，不是选项）**：对覆盖集每个候选完整重解，结论枚举 `CONFIRMED_INFEASIBLE / FEASIBLE_FOUND / DIVERGED / UNKNOWN / PROFILE_UNSUPPORTED`；只有 `CONFIRMED_INFEASIBLE` 可继续，其余全部 fail-closed 不 seal。独立性必须落在编码路径层，不能只换 CP-SAT 参数族/种子/worker 拓扑。
   - `independent_model_path_v1`：复验器不得 import 生产 master / binding / routing 模型构造器，也不得 import 生产 canonical 规则解析/normalization helper；只能读取 raw locked artifacts，由独立 strict parser 生成自己的 normalized fact set，并从该 fact set 重建候选级全 anchor 空间模型。共享 OR-Tools/CP-SAT kernel、raw artifact bytes、artifact hash 函数可以作为命名 TCB，但必须在 independence manifest 中列明。
   - `encoding_fidelity_audit_v1`：若不用独立模型路径，审计回执必须是机器可验证的入门条件，不是人工自由文本。它必须绑定 raw canonical artifact digest、独立 parser/fact digest、生产 source digest、覆盖候选 key、逐约束族 inventory（master/binding/routing/ghost/power/signature）、每个约束族的 expected-vs-encoded 对照摘要、审计工具 digest 与签名/时间戳；缺项、过期、opaque receipt、与生产 parser 共享 rule AST 的 receipt 均不得 seal。
4. 生成 §3 `sealed_public` evidence：把 negative reverification verdict digest、independence manifest、projection digest 与 supervisor seal record 绑定进去；然后 mint terminal `INFEASIBLE`。sealed checkpoint 的 `final_result` 仍为 None，公开面只看 `no_solution_evidence`。
5. 反绕过：`save()`、`mark_campaign_stopped()`、manifest direct writer、publisher/inspector 入口都必须扩展为同时挡「终局 INFEASIBLE + TNS 证据」或「last_stop_reason 声称 terminal no-solution」的 unsupervised claim；无证据的普通 INFEASIBLE 停机保持现状（合法、不可发布）。

### 4.3 publisher：manifest-only 面与互斥（CONCERN-4）

- manifest 新增 `no_solution_evidence` 节，只接受 §3 的 `sealed_public` evidence；`best_certified_result`、`final_result`、`final_solution`、`optimal_blueprint` 必须为 null/absent。`proposal_core` 证据、缺 negative reverification digest 的证据、或无 supervisor seal 绑定的证据一律不可发布。
- **stale 正向产物清理**：发布事务必须删除同目录旧 `final_solution.json` / `optimal_blueprint.json`（同一 stage→commit→verify→rollback 事务内）；`validate_delivery_artifacts_match_campaign` 的无解分支发现任何正向产物残留 ⇒ 拒绝。防止 `final_status=INFEASIBLE` 与旧 solution 文件并存。
- manifest currentness 验证必须重算 sealed evidence digest、checkpoint digest、artifact/source hash、projection digest 与 negative reverification digest；不得只比较 `final_status` 或 producer-supplied JSON。
- P1.2 OPEN-GATE 对无解面同样生效。

## 5. 信任模型（v1 §5 修订）

1. 「同管线 replay 非异构复验」的坦白保留，处置从"增强选项"升为 §4.2 硬门（owner 若要降级此门，属显式改弱信任等级的拍板，默认不降）。
2. UNKNOWN 永不进覆盖；**TNS 落地前现状 fail-closed 到 UNPROVEN 是正确基线，不得先行放松**（审查 NOTE-2 采纳为红线）。

## 6. 实施义务与红测 O-1~O-16（CONCERN-5 扩充版）

- **O-1 互斥/单调一致**（NOTE-1）：构造 projected `CERTIFIED` 与覆盖 INFEASIBLE 支配冲突，验证器必拒。
- **O-2 覆盖洞**：覆盖集漏掉域最小元或任一域元素无 `dimwise_ge_oriented_v1` 见证，必拒。
- **O-3 退化域**：authoritative 重算域为空时 TNS 必拒。
- **O-4 schema 升版连锁 + strict allowlist**：final_status、marker、seal、manifest、inspector、strong-status write allowlist、close-kernel obligations 全部识别 `NO_SOLUTION_PROPOSED` / terminal no-solution；unknown field / duplicate key / 旧 schema 必 fail-closed。
- **O-5 ghost-use inventory + F-* 条款**（CONCERN-1）：master no-overlap、power capacity screen、mandatory/required/residual signature tightening、routing、hint/decision strategy 全消费点均登记；正向/unknown ghost use 必拒。
- **O-6 P7 前瞻兼容**：P7 加入后 inventory 必证明 R 缩小仍不收紧，否则 schema/version gate 拒绝旧 TNS。
- **O-7 sliced domain**（BLOCK-1）：min_side=7 / 带 start_area / 带 aspect 过滤 / 非 safe area_upper_bound / domain_authority 漂移的证据必拒。
- **O-8 oriented transpose**（CONCERN-2）：域含 6x7、7x6，覆盖集 {6x7} 必拒；key canonicalize 成 (min,max)、面积支配、集合支配的实现必被测出。
- **O-9 resume 生命周期**（BLOCK-3）：hash/marker/checkpoint/domain 任一不符的 `NO_SOLUTION_PROPOSED` 必降级清空；相符的只能以 seal-only handle 存活，调用 frontier/search/pruning 必拒或先卫生降级。
- **O-10 sink replay 伪造**（BLOCK-4）：raw INFEASIBLE record 无有效 proof / proof digest 漂移 / replay 实际返回 UNKNOWN 或 replay violation 落在覆盖 key → 覆盖必拒。
- **O-11 负向复验门**（BLOCK-2）：reverifier 返回 `FEASIBLE_FOUND` / `DIVERGED` / `UNKNOWN` / `PROFILE_UNSUPPORTED` 必拒；`CONFIRMED_INFEASIBLE` 还必须带合格 independence manifest 或 machine-verifiable encoding audit digest。
- **O-12 stale 正向产物**（CONCERN-4）：残留 `final_solution.json` / `optimal_blueprint.json` 时无解发布必拒；发布事务清理与 rollback 可验证。
- **O-13 稀疏审计语义**（CONCERN-3）：合法 sparse 证据（如 `MISSING:4224`）必须被接受；合成 UNKNOWN 占位 record（无 timestamp / 无 schema / 无 record 义务）必须被 record 校验拒绝。
- **O-14 并行路径一致性**：并行调度器路径下 TNS 触发条件与串行路径逐字段一致；并行 worker 不得各自宣告 `NO_SOLUTION_PROPOSED`，只有 coordinator 可写 proposal。
- **O-15 direct-writer guard**：`save()`、`mark_campaign_stopped()`、manifest direct writer / publisher 的终局 `INFEASIBLE + TNS` unsupervised 写点逐个登记并出红测。
- **O-16 sealed-evidence binding chain**（本终审新增）：修改 candidate_generation、cover key、cover proof digest、projection digest、negative reverification digest、ghost inventory digest、proposal checkpoint sha 或 sealed evidence digest 中任一字段，manifest/inspector/L0 validator 必拒；`proposal_core` 被放入 manifest 必拒。

## 7. 开放问题（v1 三条的 v2 状态）

1. proposal 状态机形态（与 CANDIDATE_PROPOSED 分开）——v2 已按"分开"落稿（BLOCK-3 生命周期依赖专用 marker authority），不再开放。
2. ~~P-TNS-H 定级~~ → **已定为硬门**（§4.2）；残余：异构 profile 的具体族选择（P1.x 定）。
3. 无解面人类可读报告——维持押后。
4. **新增**：候选级 INFEASIBLE 的 `candidate_proof` 当前 replay 与生产同 profile——负向复验硬门是否应下沉到候选级 replay 层（所有 INFEASIBLE 强状态都异构复验，不只 TNS 覆盖集）——成本高，倾向只在 TNS 路径要求，P1.x 定。

---

*v2 完。v1 保留为历史快照；外审原件与加固参考版见 `p2_design_external_reviews_20260704/`（补丁未盲 apply，v2 为本方 triage 重写）。*
