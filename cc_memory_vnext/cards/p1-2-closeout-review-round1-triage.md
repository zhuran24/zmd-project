---
id: p1-2-closeout-review-round1-triage
kind: decision
title: P1.2 收口外审第 1 轮 triage 结果——8 份 GPT Pro 报告去重成 11 簇,0 条真·上-TCB 必修洞;4 已裁定延期 / 3 线下·维护 / 3 假阳 / 1 治理门 split-brain 待 owner 拍板(cluster-6)
summary: 2026-07-06 收口外审(冻结树 c9b41b3、包 SHA 1296f981…)8 份报告回传,workflow wf_db1502d5-103 抽取 15 条原始发现→去重 11 簇→对抗验真(codex verify 阶段大量占位/失败不可信,故按 [[guardrail-delegate-adversarial-reads]] 由 Opus leader 亲读源码 triage)。**结论:认证 soundness 骨架未破——0 条能盖假章的上-TCB 洞**,与 [[review-convergence-tcb-line-not-zero-findings]] 预测一致(reviewer 剥出的全在 TCB 线下/已裁定/假阳)。分桶:**已裁定延期(reseal-adversary 内鬼桶,改 sealed 文件+reseal 才能碰)4 条**——cluster-1(父门不独立 pin checker hash→空心 checker=#8 深化)、cluster-5(dependency floor provenance=deploy-pending 部署时点重钉=#9a 类)、cluster-8(entrypoint 只 AST 语法形状校验、未封 __name__/SystemExit 运行时绑定=结构 AST 锚深化;codex 误判 MUST_FIX 是占位输出、不可信)、cluster-9(import-time rebind denylist 漏 getattr/__getattribute__/update=import-time 完整性深水)。**真但 TCB 线下/维护 3 条**——cluster-2(required_tests floor 手工维护不自动吸收新测=冻结时 obligation-anchor 的已知实践、reviewer 自认未 false-green)、cluster-4(嵌套 replay 子进程无 -S:因需 import ortools〔系统 site-packages、TCB 线上〕,-I 已排 user site+env,残余=系统装包信任=OS/环境 TCB 线下;一致性硬化可加)、cluster-7(L0 checkpoint replace/marker unlink 缺父目录 fsync=崩溃一致性运维、reviewer 自认不造成 false-CERTIFIED、失败方向=crash 后 SEALED 丢失需重 reseal 非 mint 假章)。**假阳性 3 条**——cluster-3(×3 最高共识:非监督 false-INFEASIBLE 可持久化;实证 has_certified_export_surface 明确把 INFEASIBLE 当 proof-bearing、certified_terminal_evidence_violation 里"有 export surface 但无 terminal CERTIFIED evidence"→fail-closed、V101 测试钉住;reviewer 漏看)、cluster-10(strict JSON 局部 loader 收 1e999999=inf:进不了 `is True` 布尔门、门本 blocked、双重复验;可选给局部 loader 加 parse_float 对齐全局作廉价纵深)、cluster-11(public projection identity failure 返回未 scrub 的 proof-bearing records:publishable=false 已 gate 下游不当 CERTIFIED 消费)。**唯一待 owner 拍板 cluster-6**:public publisher 的 resolve_p1_2_publish_open_gate(4 字段精确匹配)弱于 authoritative check_phase_review_gate.py(还要 counting authority/decision id)=split-brain;路径硬绑无伪造路径,但 gate 文件不冻(owner 可变决策面);风险=有人把 gate 写成 4 字段 closed 形状〔没走 counting authority〕则弱 resolver 放行 publish——但**不 mint 假 CERTIFIED**(publish 仍要真 supervisor-sealed CERTIFIED),只是可能"手动门真关前就 publish 一个真 CERTIFIED"=治理门强度/时序,非 soundness 假章。推荐:冻结 gate 文件、或 publish 路径也调 authoritative checker 消除 split-brain。
scope:
  domains:
    - external-review
    - certified-exact
    - p1-2-closeout
  paths:
    - src/search/exact_campaign.py
    - src/search/certified_surface.py
    - src/search/pr2_l0_replay_core.py
    - data/review_gates/phase_1_2_spike_close.json
  symbols:
    - has_certified_export_surface
    - certified_terminal_evidence_violation
    - resolve_p1_2_publish_open_gate
    - _invoke_isolated_replay
status: active
priority: P1
triggers:
  intents:
    - consume-review-report
    - triage-closeout-review
    - decide-whether-review-converged
    - assess-gate-split-brain
  keywords:
    - 收口外审
    - triage
    - 8 份报告
    - cluster
    - 上-TCB 洞
    - split-brain
    - gate resolver
    - false-INFEASIBLE
    - 已裁定延期
    - 假阳性
    - c9b41b3
  negative_keywords: []
  paths:
    - data/review_gates/phase_1_2_spike_close.json
  symbols: []
  error_regex: []
  examples:
    - 收口外审回来了怎么 triage
    - 那批外审发现哪些是真的
    - cluster-6 gate split-brain 要不要修
    - 这轮外审收敛了吗
activation:
  layer_hint: L1
  must_know: false
  reason: 问"收口外审结果/哪些发现真假/cluster-N 怎么判/这轮收敛没"时该读——记了第 1 轮 triage 全 11 簇分桶与判定依据,尤其 0 上-TCB 洞 + cluster-6 治理门待 owner 拍板。不读易把已裁定延期/假阳当新 blocker、或漏掉 cluster-6。
provenance:
  op: record
  reason: 2026-07-06 收口外审第 1 轮 8 报告回传,Opus leader 亲读源码 triage(codex verify 阶段占位/失败不可信),固化全 11 簇分桶结果 + cluster-6 待拍板项。
  evidence:
    - "workflow wf_db1502d5-103:extract 8 报告→15 原始发现,dedup→11 簇,verify 阶段 3 硬失败+多条占位(test/测试短文本),故 Opus 亲验 cluster-3/4/6。"
    - "cluster-3 实证:exact_campaign.py:2521-2542 has_certified_export_surface 含 INFEASIBLE;2863-2879 certified_terminal_evidence_violation has_export_surface∧¬terminal_certified_evidence→fail-closed;test_v101_terminal_infeasible_surface_soundness.py。"
    - "cluster-4 实证:pr2_l0_replay_core.py:644-662 _invoke_isolated_replay 用 -I -B -X pycache_prefix、无 -S(需 import ortools)、env 极简。"
    - "cluster-6 实证:certified_surface.py:497-546 resolve_p1_2_publish_open_gate 路径硬绑+4 字段精确匹配;弱于 scripts/check_phase_review_gate.py。"
  updated_at: "2026-07-06"
---
2026-07-06 P1.2 收口外审第 1 轮 triage(冻结树 `c9b41b3`、包 SHA `1296f981…`)。8 份 GPT Pro 报告 → 去重 11 簇 → Opus leader 亲读源码验真(codex verify 占位/失败不可信,按 [[guardrail-delegate-adversarial-reads]] leader=Opus 亲做)。

== 头号结论:认证 soundness 骨架未破 ==
**0 条能盖假章的上-TCB soundness 洞。** 与 [[review-convergence-tcb-line-not-zero-findings]] 预测同构:reviewer 剥出的全部落在 TCB 线下 / 已裁定延期 / 假阳。是否据此收敛收口 = owner 画线拍板(不是我)。

== 全 11 簇分桶 ==
**A. 已裁定延期(reseal-adversary 内鬼桶,[[deliberate-insider-hardening-deferred-to-release]])——改 sealed 文件+reseal 才能碰**
- cluster-1 父门不独立 pin checker 源码 hash → 空心 checker(=#8 父级独立验 checker 深化)。
- cluster-5 canonical dependency floor provenance=deploy-pending placeholder,部署时点重钉(#9a 类)。
- cluster-8 canonical entrypoint 只 AST 语法形状校验、未封 __name__/SystemExit 运行时绑定(=结构 AST 锚深化)。**codex 误判 REAL_MUST_FIX/BLOCK,是占位输出 justification="test-short"、不可信。**
- cluster-9 import-time rebind denylist 漏 getattr/__getattribute__/update 反射写路径(=import-time 完整性深水)。

**B. 真但 TCB 线下 / 维护性,非上-TCB 洞**
- cluster-2 required_tests hard-coded floor 不自动吸收新测(subset floor+reseal 时手工加=冻结时 obligation-anchor 已知实践;reviewer 自认未 false-green)。
- cluster-4(×3)嵌套 candidate replay 子进程无 -S:因需 import ortools(系统 site-packages、TCB 线上);-I 已排 user site+env;残余=系统装包信任=OS/环境 TCB 线下。一致性硬化(给内层带 dependency floor)可加、非上-TCB。
- cluster-7 L0 durable mint 的 checkpoint replace/marker unlink 缺父目录 fsync=崩溃一致性运维健壮性;reviewer 自认不造成 false-CERTIFIED;失败方向=crash 后 SEALED 丢失需重 reseal,非 mint 假章。

**C. 假阳性(源码其实挡住了)**
- cluster-3(×3 最高共识)非监督 false-INFEASIBLE 可持久化:`has_certified_export_surface` 明确含 INFEASIBLE;`certified_terminal_evidence_violation` 里"有 export surface∧无 terminal CERTIFIED evidence"→fail-closed `terminal_certified_frontier_evidence_invalid`;INFEASIBLE 无可 replay 的 terminal 证据 schema 故必 fail-closed;`test_v101_terminal_infeasible_surface_soundness.py` 钉住。reviewer 漏看这道。
- cluster-10 owner gate 局部 strict JSON loader 收 1e999999=float('inf'):进不了 `is True` 布尔门判定、只能混旁路字段;门本 blocked;发布链双重复验。非可利用。**可选廉价纵深**:给 `_load_strict_json_mapping` 加 parse_float 对齐全局 `loads_strict_json`(非 soundness 洞、动 certified_surface.py 要 reseal,留冻结那轮)。
- cluster-11 terminal fixed-witness public projection identity 失败时返回未 scrub 的 proof-bearing records:但 publishable=false 已 gate,下游不当 CERTIFIED 消费。

**D. 待 owner 拍板(唯一)——cluster-6 治理门 split-brain**
public publisher 的 `resolve_p1_2_publish_open_gate()`(certified_surface.py:497-546,4 字段精确匹配:gate_id/status/next_phase_entry.allowed/p1_3b_entry_allowed)**弱于** authoritative `scripts/check_phase_review_gate.py`(还要 counting authority/decision id 等)。路径硬绑(无伪造路径攻击),但 gate 文件 `data/review_gates/phase_1_2_spike_close.json` **不冻**(owner 可变决策面)。风险:有人把 gate 写成 4 字段 closed 形状〔没走 counting authority〕,弱 resolver 会放行 publish。**关键定性**:这**不** mint 假 CERTIFIED(publish 仍要真 supervisor-sealed 的 CERTIFIED),只是可能"你手动门真正关闭前就 publish 一个真 CERTIFIED"=治理门强度/时序问题,非 soundness 假章。**我的推荐**:①冻结 gate 文件(纳入 frozen,篡改被字节 floor 抓)或 ②publish 路径也调 authoritative checker,消除 split-brain。gate 语义归 owner,故上交。

关联:收敛判据 [[review-convergence-tcb-line-not-zero-findings]];延期桶 [[deliberate-insider-hardening-deferred-to-release]];对抗语料上下文卫生 [[guardrail-delegate-adversarial-reads]];外审前未闭项(乙冻结仪式已执行)[[p1-2-pre-external-review-open-items]]。
