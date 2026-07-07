---
id: p1-2-closeout-review-round1-triage
kind: decision
title: P1.2 收口外审第 1 轮 triage 结果——8 份 GPT Pro 报告去重成 11 簇,0 条真·上-TCB 必修洞;4 已裁定延期 / 3 线下·维护 / 3 假阳 / 1 治理门 split-brain 已修(cluster-6→owner 选方案b→6b41ebf;cluster-10 同次带走)
summary: 2026-07-06 收口外审(冻结树 c9b41b3、包 SHA 1296f981…)8 份报告回传,workflow wf_db1502d5-103 抽取 15 条原始发现→去重 11 簇→对抗验真(codex verify 阶段大量占位/失败不可信,故按 [[guardrail-delegate-adversarial-reads]] 由 Opus leader 亲读源码 triage)。**结论:认证 soundness 骨架未破——0 条能盖假章的上-TCB 洞**,与 [[review-convergence-tcb-line-not-zero-findings]] 预测一致(reviewer 剥出的全在 TCB 线下/已裁定/假阳)。分桶:**已裁定延期(reseal-adversary 内鬼桶,改 sealed 文件+reseal 才能碰)4 条**——cluster-1(父门不独立 pin checker hash→空心 checker=#8 深化)、cluster-5(dependency floor provenance=deploy-pending 部署时点重钉=#9a 类)、cluster-8(entrypoint 只 AST 语法形状校验、未封 __name__/SystemExit 运行时绑定=结构 AST 锚深化;codex 误判 MUST_FIX 是占位输出、不可信)、cluster-9(import-time rebind denylist 漏 getattr/__getattribute__/update=import-time 完整性深水)。**真但 TCB 线下/维护 3 条**——cluster-2(required_tests floor 手工维护不自动吸收新测=冻结时 obligation-anchor 的已知实践、reviewer 自认未 false-green)、cluster-4(嵌套 replay 子进程无 -S:因需 import ortools〔系统 site-packages、TCB 线上〕,-I 已排 user site+env,残余=系统装包信任=OS/环境 TCB 线下;一致性硬化可加)、cluster-7(L0 checkpoint replace/marker unlink 缺父目录 fsync=崩溃一致性运维、reviewer 自认不造成 false-CERTIFIED、失败方向=crash 后 SEALED 丢失需重 reseal 非 mint 假章)。**假阳性 3 条**——cluster-3(×3 最高共识:非监督 false-INFEASIBLE 可持久化;实证 has_certified_export_surface 明确把 INFEASIBLE 当 proof-bearing、certified_terminal_evidence_violation 里"有 export surface 但无 terminal CERTIFIED evidence"→fail-closed、V101 测试钉住;reviewer 漏看)、cluster-10(strict JSON 局部 loader 收 1e999999=inf:进不了 `is True` 布尔门、门本 blocked、双重复验;可选给局部 loader 加 parse_float 对齐全局作廉价纵深)、cluster-11(public projection identity failure 返回未 scrub 的 proof-bearing records:publishable=false 已 gate 下游不当 CERTIFIED 消费)。**唯一待 owner 拍板 cluster-6**:public publisher 的 resolve_p1_2_publish_open_gate(4 字段精确匹配)弱于 authoritative check_phase_review_gate.py(还要 counting authority/decision id)=split-brain;路径硬绑无伪造路径,但 gate 文件不冻(owner 可变决策面);风险=有人把 gate 写成 4 字段 closed 形状〔没走 counting authority〕则弱 resolver 放行 publish——但**不 mint 假 CERTIFIED**(publish 仍要真 supervisor-sealed CERTIFIED),只是可能"手动门真关前就 publish 一个真 CERTIFIED"=治理门强度/时序,非 soundness 假章。**owner 2026-07-06 选方案 b、已修 `6b41ebf`**:把全套权威 owner-closed 条件复制进 sealed resolver 成超集(不 import 非 sealed 权威 checker=保 sound)+ 常量 drift-guard 测试;完整 reseal、双 checker 绿/--full 3836/--slow 30。cluster-10 同次带走。
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
    - 供电覆盖 intersection
    - power coverage 相交 vs 包含
    - 游戏语义裁定
    - round-2 语义轴
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
    - "2026-07-07 round-2:换轴到数学语义(Fable 写提示词),9 报告→7 簇(wf_afe548cd-05d),Opus 亲验;仍 0 真洞。C2/C3 供电覆盖 intersection vs containment=文档自相矛盾,owner 裁定=相交,改 PROJECT_LOCK:65-67 + overview §1.1 措辞;C1/C4/C5/C6/C7 假阳(codex 行为验证 reachable=不能)。"
  updated_at: "2026-07-07"
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
- cluster-10 owner gate 局部 strict JSON loader 收 1e999999=float('inf'):进不了 `is True` 布尔门判定、只能混旁路字段;门本 blocked;发布链双重复验。非可利用。**已修**(`6b41ebf`,搭 cluster-6 同文件同次 reseal 免费带走):`_load_strict_json_mapping` 加 `parse_float=_reject_non_finite_json_float`,拒非有限数值 token。
- cluster-11 terminal fixed-witness public projection identity 失败时返回未 scrub 的 proof-bearing records:但 publishable=false 已 gate,下游不当 CERTIFIED 消费。

**D. cluster-6 治理门 split-brain —— owner 选方案 b、已修(`6b41ebf`)**
public publisher 的 `resolve_p1_2_publish_open_gate()`(certified_surface.py)原只查 4 字段(gate_id/status/next_phase_entry.allowed/p1_3b_entry_allowed)**弱于** authoritative `scripts/check_phase_review_gate.py`(还要 counting_authority/approved anchor/owner_manual_state/decision 元数据+两个 ack)。路径硬绑(无伪造路径),但 gate 文件不冻(owner 可变决策面)→ 4 字段假 closed gate 会被弱 resolver 放行 publish、被权威 checker 拒(split-brain)。**关键定性**:不 mint 假 CERTIFIED(publish 仍要真 supervisor-sealed CERTIFIED),是"手动门真关前就 publish 真 CERTIFIED"=治理门强度/时序,非假章。**owner 2026-07-06 选方案 b、已实做 `6b41ebf`**:sound 设计=runtime 发布 authority 自包含在 sealed 模块(不 import 非 sealed 权威 checker,否则可不 reseal 绕过),故把全套权威 owner-closed 条件**复制进 resolver**成超集消除 split-brain,+ `test_publish_open_gate_matches_authoritative_gate_constants` 常量 drift-guard 防再漂移;完整 reseal(certified_surface sha 三处+allowlist 7 行号+checker 自钉),双 checker 绿、--full 3836 passed、--slow 30 passed。(未采方案①冻结 gate 文件:gate 是 owner 可变决策面、不宜 frozen;方案 b 治本。)

== round-2:换轴到"验证语义等价性"(Fable 2026-07-06,应 owner"线上零发现存疑、换人写提示词"之令)==
- **为什么换轴**:round-1 的 7 切面全是发布链**权限结构**轴(REVIEW_PLAN 自述"不是数学"),且 entry 把守卫锚点连 file:line 带正确行为喂给了 reviewer(考生沿地图验完守卫都在→只剩线下可挖)。所以"0 条上-TCB 发现"是**切面盲区**,不能当"线上已闭合"的证据——历史真洞(v79-v99)几乎全是数学语义洞(v82 半域/v85 漏箱/v86 不复验电力/v94 过剩箱)。
- **round-2 提示词 = 4 份**(初稿单份 8 靶区,owner 问"多几条会不会更好"后按注意力预算/审查手法从零重推拆 4——语义深审费注意力,8 靶区塞一会话必摊薄;按所需心智模型分组):`pr2_pkg\p1_2_closeout_20260706\entry_8a_predicates.md`(谓词语义等价:几何/计数/供电/退化,双向对照法)、`entry_8b_routing.md`(routing 图构造等价+存在性 vs 所选路径语义差+两层判定严格序)、`entry_8c_optimality.md`(lex 穷尽性推理链逐环+UNKNOWN 记账+resume/wave 合并+false-INFEASIBLE 侧,v79/81/82/83/84 同族区)、`entry_8d_crosscut.md`(精确算术/字节↔语义解释层/状态时间一致性+不设边界自由狩猎兜三份切缝)。共同设计:审"判定者的数学"非"谁能绕过判定者"、不给守卫地图、历史真洞校准(读包内 v79-v99 找同族下一个)、**覆盖矩阵硬性要求**(零发现须交"审了什么凭什么判闭合")、排除 round-1 全部 11 簇同族噪声。同一送审包(冻结树未变)。已按 relay 规程 staged 剪贴板(顶→底=包路径,8a,8b,8c,8d,逐条回读核验),剩 owner 手动上传、四份各开独立会话。

== round-2 triage 结果(Opus leader 亲验 + codex 行为验证,2026-07-07)==
9 报告回传(含多份 reviewer 补丁)。workflow wf_afe548cd-05d:12 发现→7 簇→codex 行为验证(这轮 verdict 是真分析、非占位)。**最终仍 0 个真·上-TCB 洞**——但换轴有价值:翻出一个真实语义歧义(供电覆盖措辞),经 owner 裁定消除。
- **C2+C3 供电覆盖 intersection vs containment(reviewer ×4 最高共识 + 补丁 + codex 在冻结 candidate_placements 找到真实 partial-cover pair)**:代码全链路统一 **intersection**——master `exact_coordinate_master.py:5330-5344`(双轴区间重叠 facility_left≤cov_right ∧ cov_left≤facility_right)+ terminal `pr2_l0_artifact_core.py:1023-1030`(`any(cell in coverage_cells)`);但 `PROJECT_LOCK:65-67` 误写 containment("覆盖矩形几何包含 slot footprint")、`:86` 又写"覆盖相交"、`overview §1.1`"被覆盖"偏 containment = **权威文档自相矛盾**。→ **owner 2026-07-07 裁定:供电覆盖谓词 = 相交(intersection,footprint 与塔覆盖区 ≥1 格重叠即算覆盖,非全包含)**,故代码正确、**非 soundness 洞**;已改 PROJECT_LOCK:65-67 + overview §1.1 措辞对齐(纯文档,不动代码/reseal)。属 [[routing-game-semantics-rulings]] 同类(canonical 没写死、代码硬编码承担的游戏语义)。
- **C1 routing-free 终品 output connector 漏终端 connector/body 复验**:假阳。谓词(5)只管 **routed** commodity 的 front(overview §1.1 + PROJECT_LOCK B-4"端口 front 格由 routing 强制");qiaoyu_capsule 等是 wireless/routing-free 终品、非 routed→其 output connector 本不需空;`extract_port_specs` 跳过它+终端 `_connector_body_exclusion_violation` 吃该投影,行为属实但语义正确(Opus 亲验)。
- **C4 局部 strict loader 收 1e999→inf**:假阳/已修(=round-1 cluster-10,`6b41ebf` 已给 `_load_strict_json_mapping` 加 parse_float;codex reachable=不能)。
- **C5 非监督 terminal INFEASIBLE 可持久化**:假阳(=round-1 cluster-3;`has_certified_export_surface`+`certified_terminal_evidence_violation` fail-close;reachable=不能)。
- **C6 routing in-loop 只查 port front cell、未同层拒 connector 被 body 占**:假阳(求解层候选过宽,但所有走 public CERTIFIED 的路径〔outer_search 提交前/capsule/supervisor seal child/publish〕都重跑终端 `_connector_body_exclusion_violation` 拦下;codex 实证不穿透)。
- **C7 terminal 接受 superdomain evidence(min_side 可低于 admissibility)**:假阳(超集穷尽不漏 admissible 子域更优解 + 独立 final-result-below-admissibility 检查 `pr2_l0_frontier_core.py:375-380`/`exact_campaign.py:2626-2629` 拦;真松点、非可利用)。

**round-1 vs round-2 合论**:两轮换轴(权限结构轴 / 数学语义轴)共 18 簇,**0 个真·上-TCB soundness 洞**;唯二实做=cluster-6 治理门 split-brain(`6b41ebf`)+ 供电覆盖措辞对齐(纯文档);其余全假阳/已裁定延期/线下。是否据此判收敛收口 = owner 画线拍板。

== round-3 triage 结果(换轴 TCB 线诚实性,codex 抽取+Opus 判,2026-07-07)==
2 会话+1 patch(dependency_floor_root)。codex 子代理抽取+行为验证、Opus 定判。**仍 0 个新真·上-TCB 洞**。6 条:①dependency_floor parent/`-S` child root 分叉=**已裁定 #9a 部署时点**(child 重验 manifest digest/root/每文件 size+sha fail-closed;manifest 已标 `deploy_pending_placeholder`;reachable=不能);②public "thin gate"=**已修**(=cluster-6 `6b41ebf`;codex 实测 4 字段 gate 返 `review_anchor_mismatch` 阻塞——reviewer 报告是修复前旧态);③送审包 manifest 列出被排除路径名=**归档策略小信息披露**(泄的是排除项名字非内容、非 soundness 洞;留 owner 定是否 redact);④TCB 线文档口径漂移=**doc drift、已扫**(specs/11「无生产 CLI」→已有 run_supervisor_seal;11_dependency_graph immutable-materialization OPEN→IMPLEMENTED;06_current_status resolve TOCTOU→已闭、归档主缺口→已堵、PR2 TCB 加延期交叉引用);⑤run_supervisor_seal 不在 critical_gate_files=非洞(seal 权威在 supervisor_seal/L0,改 CLI 伪造不了 CERTIFIED、certified source digest 已绑 scripts/**/*.py);⑥非监督 INFEASIBLE=假阳(=round-1 cluster-3 重报,sink projection 缺 proof 降 UNPROVEN)。

**三轮合论(2026-07-06~07)**:三个正交轴(权限结构 / 数学语义 / TCB 线诚实性)全剥完,**0 个真·上-TCB soundness 洞**。实做=cluster-6 split-brain(`6b41ebf`)+ 供电覆盖措辞裁定(`f2ee48b`)+ round-3 doc drift 扫;唯一留 owner 定的小策略点=送审包 manifest 是否 redact 被排除路径名(非洞)。收敛信号极强(三轴皆剥不出线上洞);是否据此收口归 owner 画线 + 手动门。

关联:收敛判据 [[review-convergence-tcb-line-not-zero-findings]];延期桶 [[deliberate-insider-hardening-deferred-to-release]];对抗语料上下文卫生 [[guardrail-delegate-adversarial-reads]];外审前未闭项(乙冻结仪式已执行)[[p1-2-pre-external-review-open-items]]。
