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

**证明（修正版）**：设 (w',h') 有可行解 (R',π\*,B\*,S\*)，取 R ⊆ R' 同锚 w×h 子矩形。逐谓词的 ghost 依赖盘点：

| 谓词 | 对 R 的依赖 | 缩小 R 的效果 |
|---|---|---|
| (1) ghost 空 | 唯一正向引用：`all_cells(π)∩R=∅` | R⊆R' ⇒ 约束放松 ✓ |
| (2)-(4)(6) | 不引用 R | 不变 ✓ |
| (5) routing | **独立于 R**（`routing_subproblem.py` 零 ghost 引用；belts 可穿过空矩形，ghost 只在 master 层排设施） | 不变 ✓（v1"routing 须避开 ghost"表述错误，但结论同向） |
| (P7 前瞻) | selected graph 与 R 无耦合或 R 缩小使可用格不减 | 不收紧 ✓ |

故 (R,π\*,B\*,S\*) 可行 ⇒ (w,h) 可行，矛盾。∎

**前提的机器化（CONCERN-1）**：引理依赖"无谓词对 ghost 做正向（存在性/接触性）引用"。这不能靠研究稿断言——实施时建 **ghost-use inventory**：登记源码中全部 ghost_rect 消费点及其方向性（排空/避障/无关 = 负向 ✓；存在性/接触性 = 正向 ✗），产出 `ghost_use_inventory_digest` 进证据 scope；发现正向或未分类引用 fail-closed。**覆盖范围警告（v2.1）**：inventory 不得只扫 no-overlap 与 routing——master 还有 ghost 条件化的 power/signature 收紧路径（`exact_coordinate_master.py` 约 3943-3988、4758-4761、4831-4834、5064-5067），初判为"缩小 R 不收紧"的负向派生约束，但它们必须逐个进 inventory 被显式分类，漏登记 = 引理前提无据。v1 的 O-5（PROJECT_LOCK F-* 条款）保留，inventory 是它的机器面。

### 2.2 最小覆盖证书（保留，加 oriented 纪律）

覆盖集 C = D 的逐维最小元反链的 replay-verified INFEASIBLE；标准域下 C = {(6,6)}，证书 O(1)。**oriented 纪律（CONCERN-2）**：支配规则命名 `dimwise_ge_oriented_v1`——同向逐维比较、禁止转置、禁止 (min,max) canonicalize、禁止面积/集合支配替代；key 严格 `^[1-9][0-9]*x[1-9][0-9]*$` 且与 tuple/record.ghost_rect 三方一致。反例警示：域含 6x7 与 7x6 时，{6x7} **不**覆盖 7x6。

### 2.3 触发条件、互斥、退化域

同 v1（potential_domain 空 ∧ 无 best_certified；任一 projected CERTIFIED 与 TNS 并存 = 矛盾态拒绝；空域 = `terminal_no_solution_domain_empty` 拒绝，空洞真不是无解证明）。

## 3. 证据 schema 与验证器（BLOCK-1/4、CONCERN-2/3 修订版）

```json
{
  "schema_version": 2,
  "source": "certified_terminal_no_solution_evidence_v2",
  "reason": "search_exhausted_all_candidates_infeasible",
  "domain_scope": "authoritative_full_domain_v1",
  "candidate_generation": { "…": "闭合合同，且必须等于 authoritative 生产参数" },
  "monotone_dominance_rule": "dimwise_ge_oriented_v1",
  "ghost_use_inventory_digest": "<机器化引理前提>",
  "candidate_domain_size": 4225,
  "candidate_status_counts": { "INFEASIBLE": 1, "MISSING": 4224 },
  "candidate_status_digest": "<全域审计，MISSING 合法>",
  "covering_infeasible_keys": ["6x6"],
  "covering_candidate_proof_digests": { "6x6": "<该 record 的 candidate_proof 规范摘要>" },
  "sink_replay_projection_digest": "<对覆盖集 sink projection 结果的摘要>"
}
```

**验证器流程（全部重算、不信 producer）**：
1. **域 authority 检查（BLOCK-1）**：`candidate_generation` 必须逐字段等于 authoritative 生产参数——`min_side` = canonical admissibility、`max_w/max_h` = grid、`area_upper_bound` = safe bound、`start_area`/`max_aspect_ratio` 必须为空。任何 sliced 形态直接拒（镜像正向 validator）。域非空。
2. 重算 `generate_candidate_sizes`；覆盖检查按 `dimwise_ge_oriented_v1` 全域逐候选验证「∃ c∈C: w≥c_w ∧ h≥c_h」。
3. **sink projection（BLOCK-4）**：对域内全部 present 强状态记录跑 `project_candidate_records_for_sink`，**只用投影后记录**——覆盖 key 必须投影后仍为 INFEASIBLE（即 isolated replay 实际发生且判 INFEASIBLE）；proof digest 与 `covering_candidate_proof_digests` 一致；任一投影后 CERTIFIED 在域内 ⇒ 拒绝。
4. counts/digest 一致性：**MISSING 是合法审计状态**（CONCERN-3）——非覆盖候选无须合成占位记录；counts/digest 只做审计，覆盖证明由第 2/3 步承担；present 记录仍须过 record schema。
5. ghost-use inventory digest 一致（§2.1）。

## 4. 三权分立接线（BLOCK-2/3、CONCERN-4 重做版）

### 4.1 producer：`NO_SOLUTION_PROPOSED` 生命周期（BLOCK-3）

- 终止分支产出 `final_status=NO_SOLUTION_PROPOSED` + `terminal_no_solution_evidence` + **专用 proposal marker**（镜像现有 marker：schema_version/authority=`certified_exact_no_solution_proposal_ready_v1`/run_id/exit_code/**checkpoint_sha256**/campaign_instance_id）。`final_result` 恒为 None。
- **resume 规则**（v1 空白，现有 sanitizer 会把强状态降级、证据清空）：`NO_SOLUTION_PROPOSED` checkpoint 载入时——**前置条件（v2.1 显式化）：必须先通过现有 resume validation 的 current source/artifact hash 校验**（`_validate_resume_state` 一族；hash 不符按现有语义直接拒，不进入任何保留分支）；通过后，若 marker 存在且 checkpoint_sha256 与磁盘一致、domain authority 校验通过，则证据与覆盖 proof 原样保留、**且保留态只能作为 supervisor seal 的输入，绝不进入 search/pruning/frontier 状态**（这是对"checkpoint 强状态必须 fresh replay"铁律的一个显式声明的例外：例外面窄——只延后到 seal 时的 L0 隔离重放，不是跳过重放）；任一绑定不符 ⇒ 整体降级 UNKNOWN + 证据清空 + 走正常 resume 卫生。resume validation 新分支：`NO_SOLUTION_PROPOSED` 要求证据存在、禁 final_result、禁任何 candidate solution 残留。

### 4.2 supervisor：负向复验硬门（BLOCK-2）

`supervisor_seal` 第二路径 `proposal_to_terminal_infeasible_v1`，L0 隔离内依次：
1. marker/checkpoint/域 authority 绑定复验；
2. §3 验证器全流程（含覆盖集 sink replay）；
3. **`candidate_wide_no_solution_reverifier_v1`（硬前置，不是选项）**：对覆盖集每个候选完整重解，结论枚举 `CONFIRMED_INFEASIBLE / FEASIBLE_FOUND / DIVERGED / UNKNOWN / PROFILE_UNSUPPORTED`——**只有 CONFIRMED_INFEASIBLE 可继续**，其余全部 fail-closed 不 seal。**独立性要求（v2.1 收紧）**：仅换 CP-SAT 参数族/种子/worker 拓扑**不够**——系统性 false-INFEASIBLE 的根在建模代码，同一模型构造器上跑一万个 profile 会一致地错。门的独立性必须落在编码路径层，二选一（或并用）：(a) 复验器走**独立重建的模型构造路径**（不 import 生产 master 的构造代码，从 canonical 规则独立重推约束——与 PR2 #5 B2 独立枚举同一哲学）；(b) 附带**编码忠实性定向审计产物**（针对覆盖集候选的 master/binding/routing 编码逐约束审计回执，作为门的输入之一，缺则不 seal）。定位说明：现有 I1 只复验单布局 nogood，不是候选级全 anchor 空间负向复验，不能顶替。此门的理由：负向结论无 witness 可独立几何检查，(6,6) 单点证书把全部信任压在一次求解上，同管线 replay 防不了编码级系统性 false-INFEASIBLE（`08_phase_1_2_plan.md:17-24` 裁定 false-INFEASIBLE 不低于 false-CERTIFIED）。
4. mint terminal `INFEASIBLE`。反绕过：`save()` 守卫扩展为同时挡「INFEASIBLE + TNS 证据」的 unsupervised claim；无证据的普通 INFEASIBLE 停机保持现状（合法、不可发布）。

### 4.3 publisher：manifest-only 面与互斥（CONCERN-4）

- manifest 新增 `no_solution_evidence` 节，与 `best_certified_result` **互斥**（后者必须为 null/absent）。
- **stale 正向产物清理**：发布事务必须删除同目录旧 `final_solution.json`/`optimal_blueprint.json`（同一 stage→commit→verify→rollback 事务内）；`validate_delivery_artifacts_match_campaign` 的无解分支发现任何正向产物残留 ⇒ 拒绝。防"final_status=INFEASIBLE 与旧 solution 文件并存"的自相矛盾交付面。
- P1.2 OPEN-GATE 对无解面同样生效。

## 5. 信任模型（v1 §5 修订）

1. 「同管线 replay 非异构复验」的坦白保留，处置从"增强选项"升为 §4.2 硬门（owner 若要降级此门，属显式改弱信任等级的拍板，默认不降）。
2. UNKNOWN 永不进覆盖；**TNS 落地前现状 fail-closed 到 UNPROVEN 是正确基线，不得先行放松**（审查 NOTE-2 采纳为红线）。

## 6. 实施义务与红测 O-1~O-12（CONCERN-5 扩充版）

- O-1 互斥/单调一致（v1）；O-2 覆盖洞（v1）；O-3 退化域（v1）；O-4 schema 升版连锁 + strong-status allowlist（v1）；O-5 ghost-use inventory + F-* 条款（v1 升级为机器面）；O-6 P7 前瞻兼容（v1）。
- **O-7 sliced domain**：min_side=7 / 带 start_area / 带 aspect 过滤的证据必拒。
- **O-8 oriented transpose**：域含 6x7、7x6，覆盖集 {6x7} 必拒；key canonicalize 成 (min,max) 的实现必被测出。
- **O-9 resume 生命周期**：marker/hash 不符的 NO_SOLUTION_PROPOSED 必降级清空；相符的必须原样可 seal。
- **O-10 sink replay 伪造**：raw INFEASIBLE record 无有效 proof / proof digest 漂移 / replay 实际返回 UNKNOWN → 覆盖必拒。
- **O-11 负向复验门**：reverifier 返回 FEASIBLE_FOUND/DIVERGED/UNKNOWN 时 seal 必拒；CONFIRMED 路径端到端可过。
- **O-12 stale 正向产物**：残留 final_solution.json 时无解发布必拒；发布事务清理可验证。
- **O-13 稀疏审计语义**（v2.1）：合法 sparse 证据（MISSING:4224）必须被接受；合成 UNKNOWN 占位 record（无时间戳/无 schema 的伪 record）必须被 record 校验拒绝。
- **O-14 并行路径一致性**（v2.1）：并行调度器（exact_parallel_scheduler）路径下 TNS 触发条件与串行路径逐字段一致；并行 worker 不得各自宣告 NO_SOLUTION_PROPOSED。
- **O-15 direct-writer guard**（v2.1）：「终局 INFEASIBLE + TNS 证据」的三处 unsupervised 写点（对称于 CERTIFIED 三处）逐个登记进 save() 守卫并出红测。

## 7. 开放问题（v1 三条的 v2 状态）

1. proposal 状态机形态（与 CANDIDATE_PROPOSED 分开）——v2 已按"分开"落稿（BLOCK-3 生命周期依赖专用 marker authority），不再开放。
2. ~~P-TNS-H 定级~~ → **已定为硬门**（§4.2）；残余：异构 profile 的具体族选择（P1.x 定）。
3. 无解面人类可读报告——维持押后。
4. **新增**：候选级 INFEASIBLE 的 `candidate_proof` 当前 replay 与生产同 profile——负向复验硬门是否应下沉到候选级 replay 层（所有 INFEASIBLE 强状态都异构复验，不只 TNS 覆盖集）——成本高，倾向只在 TNS 路径要求，P1.x 定。

---

*v2 完。v1 保留为历史快照；外审原件与加固参考版见 `p2_design_external_reviews_20260704/`（补丁未盲 apply，v2 为本方 triage 重写）。*
