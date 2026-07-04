# Terminal 全域无解证书合同设计稿 v1

**Status:** HISTORICAL_OR_PLAN（研究层设计稿，不改生产代码/锁面）
**Authored:** 2026-07-04
**填的洞：** `src/search/outer_search.py:1982-1989`——候选域穷尽但无任何 certified 候选时，当前 terminal-frontier 证据 schema 只支持正向 CERTIFIED final result，系统只能 fail-closed 返回 `UNPROVEN`。「所有 admissible 候选均不可行」这一与 CERTIFIED 同等 proof-bearing 的终局结论（`exact_campaign.py:2548-2551` 自述）目前**说不出来**。若生产 campaign 的真实答案是"min_side≥6 无解"，这就是最终交付物的形状——本稿设计它的可重放证据合同。

---

## 1. 事实基线（2026-07-04 只读调查核验）

已存在的地基（本设计全部复用，不新造）：

1. **候选级 INFEASIBLE 已是一等强状态**：`STRONG_CANDIDATE_STATUSES = {"CERTIFIED","INFEASIBLE"}`、`PROOF_BEARING_TERMINAL_STATUSES` 同（`exact_campaign.py:103-115`）；`VALID_FINAL_STATUSES` 已含 `INFEASIBLE`（116-124）。
2. **候选级 INFEASIBLE 已可 sink replay**：`candidate_proof` 的 `claimed_status` 支持 CERTIFIED/INFEASIBLE 双侧；INFEASIBLE 侧禁带 solution、`solution_digest=None`；隔离子解释器重跑 `run_benders_for_ghost_rect`，replay_status 必须等于 claimed_status（`candidate_proof_replay.py:35, 240-250, 515-560, 875-928`）。
3. **支配剪枝已存在且方向正确**：显式 INFEASIBLE(w,h) 剪掉一切 `w'≥w ∧ h'≥h` 的候选（同向、不转置，`certified_frontier.py:218-220`；运行态同构 `outer_search.py:702-704`）。
4. **resume 卫生已覆盖 INFEASIBLE**：checkpoint 载入的强状态一律降级 UNKNOWN、需 fresh replay（`PROJECT_LOCK.md:276-284`；`exact_campaign.py:2184-2243`）。
5. **INFEASIBLE 已被当受保护面**：`has_certified_export_surface` 把 terminal INFEASIBLE 视为 proof-bearing、无证据时不可 export（`test_v101_terminal_infeasible_surface_soundness.py:70-95`）。

缺失的（本稿设计对象）：无解侧的 terminal 证据 schema、seal/publish 路径（`supervisor_seal()` 写死只 mint CERTIFIED，`exact_campaign.py:3571-3579`；manifest/publisher 硬要求 solution/blueprint，`delivery_manifest.py:127-135, 550-587`；`certified_surface.py:758-853`）、以及 resume validation 的对应分支（当前 `final_result` 只许伴随 CERTIFIED/CANDIDATE_PROPOSED，2442-2459）。

## 2. 数学骨架：单调性引理与最小覆盖证书

### 2.1 引理（候选可行性的逐维反单调）

**命题**：若候选 `(w,h)` 不可行（不存在满足全部谓词、含 w×h ghost 空矩形的解），则任意 `(w',h')`，`w'≥w ∧ h'≥h`，也不可行。

**证明**：反证。设 `(w',h')` 有可行解 `(R', π*)`，`R'` 为 w'×h' 空矩形。取 `R ⊆ R'` 为同锚点的 w×h 子矩形。则 `(R, π*)` 满足：谓词(1) `all_cells(π*) ∩ R ⊆ all_cells(π*) ∩ R' = ∅`；谓词(2)(3)(4)(6) 与 R 无关、由 π* 继承；谓词(5) routing 选择只须避开 ghost 区，避开 R' 者必避开 R ⊆ R'。故 `(w,h)` 可行，矛盾。∎

（注意方向盘点：ghost 只出现在谓词(1)的"排空"侧与 routing 的"不可用格"侧，缩小 ghost 是**约束放松**——这是引理成立的全部理由。若未来任何谓词把 ghost 用作"必须存在/必须接触"型约束，引理即破，见 §6 义务 O-5。）

这正是既有 derived-prune（事实 3）的 soundness 依据——但它目前只作为进程内剪枝存在，没有被形式陈述或红测钉住。本稿把它升格为 TNS 证书的承重引理。

### 2.2 最小覆盖证书（关键坍缩）

候选域 `D = {(w,h) : min_side ≤ w ≤ max_w, min_side ≤ h ≤ max_h, 过滤器}`（oriented 枚举，`certified_frontier.py:58-99`；过滤器 = area_upper_bound / start_area / max_aspect_ratio，均只**删除**候选）。

**定义**：TNS 覆盖集 C ⊆ D = 一组 replay-verified INFEASIBLE 候选，使 D 中每个候选都逐维 ≥ C 中某元素。由引理，C 存在 ⇒ D 全不可行。

**坍缩观察**：无过滤器时 D 的逐维最小元唯一——`(min_side, min_side)` = 生产项目的 `(6,6)`，它逐维 ≤ 一切候选。**故标准生产配置下，全域无解证书 = 单个候选 (6,6) 的 replay-verified INFEASIBLE + 域参数绑定**。过滤器只删候选、不产生新的下边界之外的最小元（被删候选无须覆盖），故 C = {(6,6)} 仍充分；一般形式（toy 项目、非常规域）取 D 的逐维最小元反链即可，验证器按一般形式实现。

工程含义：TNS 的验证成本 = 重放一个候选的不可行证明（与 CERTIFIED 侧重放一个候选的成本同阶）；证书体积 O(1)~O(反链)。**不需要**逐 4225 个候选存证——`candidate_status_digest` 仍全量记录状态用于审计，但承重的只有覆盖集。

### 2.3 触发条件与互斥

TNS 只在既有终止分支的空档触发：`potential_domain` 空 ∧ `best_certified_candidate is None`（`outer_search.py:1906-1918` 的 else 支）。此时投影不变量保证域中每个候选要么显式 INFEASIBLE、要么被显式 INFEASIBLE 支配剪掉（无 CERTIFIED、无残留 UNKNOWN——否则 potential_domain 非空）。互斥性红测义务：验证器必须拒绝「TNS 证据存在 ∧ 任一候选 replay-verified CERTIFIED」的状态（矛盾态,fail-closed）。

**退化域警告**：D 本身为空（过滤器删光）时**不得**输出 TNS——空域的"全不可行"是空洞真，语义是配置错误。验证器把 `candidate_domain_size == 0` 判为 `terminal_no_solution_domain_empty` 拒绝。

## 3. 证据 schema（草案）

```json
{
  "schema_version": 1,
  "source": "certified_terminal_no_solution_evidence_v1",
  "reason": "search_exhausted_all_candidates_infeasible",
  "candidate_generation": { "…": "与现有 terminal_frontier_evidence 同一闭合合同" },
  "candidate_domain_size": 4225,
  "candidate_status_counts": { "INFEASIBLE": 1, "UNKNOWN": 4224 },
  "candidate_status_digest": "<与现有 _candidate_status_digest 同构>",
  "covering_infeasible_keys": ["6x6"],
  "monotone_dominance_rule": "dimwise_ge_v1"
}
```

要点：①`candidate_generation` 沿用现有闭合合同（unknown key fail-closed，`PROJECT_LOCK.md:311`）；②`covering_infeasible_keys` 每个 key 对应的 candidate record 必须持 `status="INFEASIBLE"` + 合法 `candidate_proof`（claimed_status=INFEASIBLE）且通过 sink replay；③`monotone_dominance_rule` 显式命名支配规则版本——引理是证书的一部分，规则漂移必须撞 schema；④被支配候选**不需要**任何状态（表中可为 UNKNOWN/缺失）——覆盖由验证器重算，不信 producer 的剪枝记录。

**验证器**（镜像 `resolve_terminal_frontier_evidence_error` 的重算风格，`certified_frontier.py:456-514`）：从 params 重算 `generate_candidate_sizes` → 域非空 → 每个覆盖 key ∈ D 且 record 为 replay-verified INFEASIBLE → 全域逐维覆盖检查 → 无任何 CERTIFIED record → counts/digest 一致。全部纯重算 + 字典序检查，无 solver 依赖（除覆盖集的 INFEASIBLE replay 本身）。

## 4. 三权分立接线（对称于 CERTIFIED 侧，不走捷径）

1. **producer**：新终止分支产出 `NO_SOLUTION_PROPOSED`（镜像 `CANDIDATE_PROPOSED`：final_status 新值 + `terminal_no_solution_evidence` + proposal marker；`final_result` 保持 None）。resume validation 加对应分支（`NO_SOLUTION_PROPOSED` 要求证据存在、禁 final_result、禁 solution 类字段）。
2. **supervisor seal**：`supervisor_seal()` 增加第二 reason 路径（当前写死 `TERMINAL_FULL_FRONTIER_CERTIFIED_REASON`，3571-3579）：L0 隔离子进程重放覆盖集 INFEASIBLE 证明 + 重算覆盖验证，通过才 mint terminal `INFEASIBLE`。**mint 对称性原则**：terminal INFEASIBLE 一旦可发布，其 mint 权与 CERTIFIED 同级——`save()` 反绕过守卫从"只挡三处 CERTIFIED"（`exact_campaign.py:2569-2584`；README:899-900 记录的既知不对称）扩展为同时挡「终局 INFEASIBLE + TNS 证据」的 unsupervised claim；无证据的普通 `mark_campaign_stopped(status="INFEASIBLE")`（进程失败语义）保持合法且不可发布（维持 test_v101 行为）。
3. **publisher**：无解面的公开产物 = manifest-only（无 solution/blueprint——`validate_delivery_artifacts_match_campaign` 与 stage 写盘需要平行的 no-solution 分支）；manifest 新增 `no_solution_evidence` 节替代 `best_certified_result`（互斥，二选一）。P1.2 OPEN-GATE 对无解面同样生效——owner 手动门不因结论是负向而豁免。

## 5. 信任模型的诚实声明（设计稿必须自己戳破的两点）

1. **INFEASIBLE replay 是"同管线隔离重跑"，不是异构复验**：replay child 调的仍是 `run_benders_for_ghost_rect`（`candidate_proof_replay.py:907`）。它防的是记录篡改/字节漂移，不防"求解器系统性 false-INFEASIBLE"。这与 CERTIFIED 侧对称（CERTIFIED replay 也同管线），但方向不对称：false-CERTIFIED 还有 fixed-witness 独立几何复验兜底，false-INFEASIBLE 没有等价物——`08_phase_1_2_plan.md:17-24` 已把 false-INFEASIBLE 列为不低于 false-CERTIFIED 的 soundness 问题。**增强选项（P-TNS-H）**：对覆盖集（通常仅 (6,6)）额外跑 I1 风格异构 profile 复验 + master 编码忠实性定向审计；成本 O(覆盖集)，建议列为 seal 前置。这也与「CP-SAT 编码忠实性逐约束审计」待办直接勾连——TNS 把那项审计从"值得做"升格为"无解结论的直接依赖"。
2. **UNKNOWN 永不进入覆盖**：覆盖集只认 replay-verified INFEASIBLE；预算耗尽/UNKNOWN 仍走现有 `UNPROVEN` fail-closed 路径。TNS 不给"跑不完"提供任何新出口。

## 6. 实施义务清单（P1.x 排期时展开）

- O-1 引理红测：构造 (w,h) INFEASIBLE ∧ (w',h') 声称 CERTIFIED（w'≥w,h'≥h）的伪造状态 → 验证器必拒（互斥 + 单调一致性）。
- O-2 覆盖洞红测：覆盖集漏掉域最小元（伪造 covering_keys=[7x6] 而域含 6x6）→ 拒。
- O-3 退化域红测：params 过滤出空域 + TNS 证据 → 拒。
- O-4 schema 升版连锁：final_status 新值 / marker / seal / manifest / inspector / strong-status write allowlist（新的 INFEASIBLE 终局写点必须逐个登记）/ close-kernel obligations reseal。
- O-5 引理前提守护：任何给谓词引入"ghost 正向依赖"（存在性/接触性约束）的未来改动必须显式重审引理——在 PROJECT_LOCK 落一条 F-* 条款（TNS 落地批次内做）。
- O-6 与 P7 前瞻兼容：吞吐谓词（`p2_0_throughput_certification_paradigm_design_v1.md`）加入后引理仍成立（P7 约束与 ghost 尺寸的关系同为"缩小 ghost = 放松或不变"——routing 可用格变多，P7 的 selected graph 可行域不缩）；TNS 覆盖集的 INFEASIBLE replay 自动含 P7 gate，无需改证书结构。

## 7. 开放问题

1. `NO_SOLUTION_PROPOSED` 与 `CANDIDATE_PROPOSED` 是否合并为单一 proposal 状态 + 证据类型判别字段（schema 简洁性 vs 状态机显式性）——倾向分开（fail-closed 面更清晰），P1.x 定。
2. P-TNS-H（异构复验增强）是 seal 硬前置还是 owner 手动门审查项——涉及"无解结论的最终信任等级"，owner 拍板。
3. 无解面的公开产物形态（manifest-only 是否足够、要不要人类可读的 no-solution 报告）——交付需求问题，押后。

---

*v1 完。与前两稿（吞吐范式、F5 轨道提升）同为 Fable-5 下线前"先想后做"批次；三稿互相引用处均已显式标注。*
