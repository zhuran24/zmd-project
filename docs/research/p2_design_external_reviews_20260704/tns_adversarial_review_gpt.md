# TNS no-solution design v1 adversarial review

审阅范围严格限定为：

- `tns_prompt_adversarial_review.md`
- `tns_no_solution_design_v1.zip` 内文件

未读取其它上传包或外部资料。

## 总体判断

| 层级 | 判定 | 理由 |
|---|---|---|
| lemma layer | reliable after BLOCK fixes | 逐维反单调在「ghost 只作为排空/避障或无关」前提下成立；但设计稿对 routing 的表述与锁面事实不一致，且没有机器化 ghost-use inventory。 |
| contract layer | needs redesign | 现稿把同管线 replay 的候选级 INFEASIBLE 直接提升为 terminal no-solution，缺少 authoritative full-domain 校验、candidate-wide negative reverifier、proof digest/sink projection 绑定。 |
| wiring layer | needs redesign | `NO_SOLUTION_PROPOSED` 的 resume、seal、save guard、manifest-only publisher 都不是简单“对称加字段”；现有代码会清证据、要求 positive final_result，或只支持 CERTIFIED seal。 |

结论：原设计不能直接进入生产实现。若按本报告 BLOCK 修补并把 P-TNS-H 改为 seal 硬前置，设计可继续作为 P1.x research/implementation contract；否则 terminal INFEASIBLE 必须继续 fail-closed 到 `UNPROVEN`。

相关补丁：`tns_design_hardening.patch`，生成的加固版全文：`terminal_no_solution_evidence_contract_design_v1.hardened.md`。

---

## BLOCK-1：TNS 必须绑定 authoritative full domain，不能接受 sliced domain

**根因**：设计稿 §2.2 把候选域写成 `min_side/max/filter` 的一般 D，并说过滤器“只删除候选”；§3 又只说从 params 重算 `generate_candidate_sizes`。这会让验证器接受 producer 提供的缩小域，而不是生产 authoritative 全域。正向 terminal frontier validator 已明确拒绝 `start_area`、`max_aspect_ratio`、抬高 `min_side`、非 safe `area_upper_bound` 这类 sliced domain；无解侧如果更宽松，就会把“缩小域无解”发布成“全域无解”。参考：`src/search/certified_frontier.py:82-97`、`:421-454`，`src/search/outer_search.py:1831-1861`。

**最小反例**：真实 authoritative 域含 `min_side=6`。恶意/错误 evidence 使用 `min_side=7`，覆盖集 `C=[7x7]`，验证器只按证据 params 重算 D，则 `C` 覆盖 sliced D。但 authoritative 域里的 `6x6`、`6x70`、`70x6` 等候选根本未被覆盖；其中任一可行都会被误报为 terminal no-solution。

**影响**：false terminal INFEASIBLE。负向结论比普通 `UNPROVEN` 严重得多，会让交付面声称不存在解。

**修补补丁**：替换设计稿 §2.2 与 §3 的 domain 验证文字，要求 `domain_scope="authoritative_full_domain_v1"`，并硬拒 `start_area`、`max_aspect_ratio`、非 authoritative `min_side`、非 safe `area_upper_bound`、empty domain。完整替换文本见 `tns_design_hardening.patch` 中 §2.2 和 §3 hunks。

---

## BLOCK-2：同管线 INFEASIBLE replay 不足以 mint terminal no-solution，P-TNS-H 不能是“增强选项”

**根因**：候选 proof replay 的子进程仍调用同一 `run_benders_for_ghost_rect`。它能防 producer 篡改、proof 字节漂移、record/status 不匹配，但不能防建模/编码系统性 false-INFEASIBLE。设计稿 §5 明知 false-INFEASIBLE 没有 CERTIFIED 侧 fixed-witness 几何复验，却仍把 P-TNS-H 写成“建议列为 seal 前置”的增强选项。现有 `independent_infeasibility_reverifier.py` 也只是 whole-layout/nogood 局部复验，不是候选 `(w,h)` 全 anchor/layout 空间的 negative verifier。参考：`src/search/candidate_proof_replay.py:890-933`，`src/search/independent_infeasibility_reverifier.py:1-14`、`:69-90`、`:122-133`，`docs/项目说明/08_phase_1_2_plan.md:17-24`。

**最小反例**：生产和 replay 共用的 master 编码漏掉了某类合法 ghost anchor，或误把某个必须可选的设施约束写成必须满足。`6x6` 真实可行，但生产 run 与 replay child 都稳定返回 INFEASIBLE。设计稿当前合同会用单个 `6x6` INFEASIBLE 覆盖全域并发布 terminal no-solution。

**影响**：同管线 false negative 被 seal 成 public proof-bearing INFEASIBLE。该风险不低于 false-CERTIFIED，且没有 solution witness 可独立检查。

**修补补丁**：替换设计稿 §5：将 P-TNS-H 改为 hard gate，定义新的 `candidate_wide_no_solution_reverifier_v1`，明确现有 whole-layout I1 不足；只有 `CONFIRMED_INFEASIBLE` 可 seal，`UNKNOWN/DIVERGED/FEASIBLE_FOUND/PROFILE_UNSUPPORTED` 全部 fail-closed。完整替换文本见 patch §5 hunk。

---

## BLOCK-3：`NO_SOLUTION_PROPOSED` 的 resume/proposal 生命周期没有闭合

**根因**：当前 resume sanitizer 只对正向 `CANDIDATE_PROPOSED` 有特殊保留路径；其它 checkpoint-loaded strong evidence 会被降级或清空。若天真加入 `NO_SOLUTION_PROPOSED`，要么 resume 后覆盖 INFEASIBLE proof 被清掉导致无法 seal，要么为了保留它而绕过强状态降级，留下 stale/forged proposal。现有 validation 还要求 final_result 只伴随 CERTIFIED/CANDIDATE_PROPOSED，seal transition 也写死 CERTIFIED reason。参考：`src/search/exact_campaign.py:2135-2243`、`:2442-2459`、`:3433-3579`、`:3606-3667`。

**最小反例**：checkpoint 含 `final_status=NO_SOLUTION_PROPOSED`、`terminal_no_solution_evidence`、`6x6` INFEASIBLE proof、proposal marker。resume 载入时若沿用现有 sanitizer，INFEASIBLE record 被降级 UNKNOWN、terminal evidence 被清空，proposal 不可 seal；若粗暴把 NO_SOLUTION_PROPOSED 加入“保留”集合但没有 marker/checkpoint hash/domain authority 绑定，则旧证据可跨域或跨源码漂移后继续被 seal。

**影响**：轻则 TNS 永远无法稳定发布，重则 stale/伪造 evidence 被 supervisor 当成可信 proposal。

**修补补丁**：替换设计稿 §4：显式定义 `NO_SOLUTION_PROPOSED` 的 producer proposal、marker/hash/authority 绑定、resume 保留/降级规则、`proposal_to_terminal_infeasible_v1` supervisor transition、direct writer guard。完整替换文本见 patch §4 hunk。

---

## BLOCK-4：证据验证必须使用 sink-projected replay records，不能信 raw candidate record

**根因**：设计稿 §3 说覆盖 key 对应 record “必须持 INFEASIBLE + 合法 candidate_proof 且通过 sink replay”，但没有把验证器输入绑定为 `project_candidate_records_for_sink(...)` 的输出。当前代码明确把 candidate proof 当 request，不是 grant；sink replay 失败的强 record 会被降级。另一个细节是现有 positive `candidate_status_digest` 只摘要 key/w/h/area/status/solution_digest，对 INFEASIBLE proof digest 没有承重绑定。参考：`src/search/candidate_proof_replay.py:1-15`、`:304-426`、`:444-608`，`src/search/certified_frontier.py:486-495`。

**最小反例**：raw checkpoint 中放入 `status="INFEASIBLE"` 的 `6x6` record，但 `candidate_proof.claimed_status` 不匹配、proof request digest 漂移，或 isolated replay 实际返回 UNKNOWN。若 TNS verifier 只看 raw status 或只看 producer 填的 digest，就会错误接受覆盖集。

**影响**：伪造或漂移的候选级 negative proof 可被提升为 terminal no-solution。

**修补补丁**：替换设计稿 §3 的 verifier 流程：先对重算域内 present strong records 做 sink projection/replay，只使用 projected records；证据增加 `sink_replay_projection_digest` 与 `covering_candidate_proof_digests`；任一 projected CERTIFIED 在域内即拒绝。完整替换文本见 patch §3 hunk。

---

## CONCERN-1：lemma 的 ghost use inventory 不完整，且 routing 表述与锁面事实不一致

**根因**：设计稿证明写“routing 选择只须避开 ghost 区”。但 `PROJECT_LOCK.md` 明确记录默认 routing domain 不排除 ghost cells，cut families 把 ghost 当 blocked 是 env-gated 行为；即 routing 在当前锁面里更像“独立于 ghost”或条件性 obstacle，而不是必然避开。更重要的是 zip 中没有完整 master/routing 源文件，不能仅凭研究稿证明未来所有谓词都无 ghost-positive use。

**最小反例**：未来新增谓词“必须有一条 belts/boundary connector 接触 ghost 边界”或“ghost 区域必须被某 power coverage 证书引用”。此时缩小 ghost 可能收紧约束，`(w,h)` infeasible 不再推出 `(w',h')` infeasible。

**影响**：monotonic lemma 失效，覆盖证书不 sound。

**修补补丁**：替换 §2.1：把证明改成显式承重前提表；修正 routing 为“独立或 obstacle 均可”；新增 `ghost_use_inventory_digest` 与 positive/unknown use fail-closed。完整替换文本见 patch §2.1 hunk。

---

## CONCERN-2：oriented key 与 transpose/canonicalization 防线需要写进 schema

**根因**：代码事实显示候选是 oriented，`(w,h)` 与 `(h,w)` 分离；支配剪枝也是同向逐维。设计稿虽提到 oriented，但 schema 只列字符串 keys，未要求 strict parser、无前导零、tuple/key/record ghost_rect 三方一致，也没写 transpose 红测。

**最小反例**：域含 `6x7` 与 `7x6`。覆盖集只有 `6x7`。若实现把 key canonicalize 成 `(min,max)`，或把支配写成集合/面积支配，就会错误认为 `7x6` 已覆盖；但 `7≥6` 成立、`6≥7` 不成立，同向逐维覆盖失败。

**影响**：漏掉 oriented 候选，可能误报全域无解。

**修补补丁**：替换 §3 key 绑定段与 §6 红测，新增 `dimwise_ge_oriented_v1`、strict key regex、tuple/ghost_rect 一致、`6x7` 不覆盖 `7x6` 测试。完整替换文本见 patch §3 与 §6 hunks。

---

## CONCERN-3：`UNKNOWN` 与 `MISSING` 的审计语义混淆

**根因**：设计稿示例写 `candidate_status_counts={"INFEASIBLE":1,"UNKNOWN":4224}`，但非覆盖候选不需要 record；现有 digest 风格会把缺记录与 UNKNOWN record 区分。若 schema 强迫 UNKNOWN，producer 可能要合成 4224 条占位 record，反而触发 resume/validation 复杂度。

**最小反例**：标准域 4225 个候选，checkpoint 只保存 `6x6` replay-verified INFEASIBLE。正确审计应是 `INFEASIBLE:1, MISSING:4224` 或等价 sparse 表示。若 verifier 期待 UNKNOWN:4224，会把合法 sparse evidence 拒掉；若 producer 合成 UNKNOWN records，又可能引入无时间戳/无 schema 的 invalid records。

**影响**：证据 schema 脆弱，resume/inspector 解释不一致。

**修补补丁**：替换 §3 counts 描述：`MISSING` 是合法审计状态；counts/digest 只做 audit，不承担覆盖证明；present records 仍必须通过 record schema。完整替换文本见 patch §3 hunk。

---

## CONCERN-4：manifest-only public surface 未定义 stale artifact 清理与互斥

**根因**：当前 manifest/publisher 面是 positive CERTIFIED：要求 `final_result`、`final_solution.json`、`optimal_blueprint.json`。设计稿说无解面 manifest-only，但没有定义 manifest 字段、旧 positive artifacts 清理、consumer 互斥规则。参考：`src/io/delivery_manifest.py:127-135`、`:550-587`、`:812-860`，`src/search/certified_surface.py:49-100`、`:607-650`、`:758-855`。

**最小反例**：同一输出目录之前发布过 CERTIFIED，留下 `final_solution.json` 与 `optimal_blueprint.json`。随后 TNS 发布 manifest-only，但没有删除旧文件；下游 consumer 看到 final_status INFEASIBLE，却也看到旧 solution artifact。

**影响**：公开交付物自相矛盾；可能把 stale positive 方案当成当前结果。

**修补补丁**：替换 §4 publisher 段：manifest 新增 `no_solution_evidence`，positive artifacts 必须 absent/null，发布器事务性清除旧 solution/blueprint，validator 发现 stale positive artifacts 即拒绝。完整替换文本见 patch §4.4 hunk。

---

## CONCERN-5：O-1~O-6 红测覆盖不足

**根因**：原测试清单覆盖互斥、覆盖洞、空域、schema 升版、ghost-positive、P7 兼容，但缺少 sliced domain、resume marker、sink replay mismatch、negative reverifier UNKNOWN、oriented transpose、stale artifact、parallel/coordinator 与 direct writer guard。

**最小反例**：只实现原 O-1~O-6，仍可能让 `min_side=7` sliced evidence、`6x7` transpose coverage、raw forged proof、stale `final_solution.json` 逃过测试。

**影响**：最危险的 public negative path 缺乏回归网。

**修补补丁**：替换 §6 为 O-1~O-12，覆盖 domain、orientation、resume、sink replay、negative reverifier、manifest、ghost inventory、parallel、status transition。完整替换文本见 patch §6 hunk。

---

## NOTE-1：核心逐维覆盖思路本身值得保留

在当前可见事实下，`INFEASIBLE(w,h) ⇒ INFEASIBLE(w',h') for w'≥w,h'≥h` 的方向与现有剪枝实现一致；标准域若唯一最小元为 `6x6`，单候选覆盖确实能把证书体积降到 O(1)。问题不在数学直觉，而在 public terminal 证据合同必须把 domain authority、negative proof trust boundary 与 wiring lifecycle 锁死。

## NOTE-2：当前 fail-closed 行为是正确基线

`outer_search.py` 在“候选域穷尽但无 replayable terminal no-solution evidence”时返回 `UNPROVEN` 是正确的安全默认值。TNS 上线前，不应把该分支改成 terminal `INFEASIBLE`。
