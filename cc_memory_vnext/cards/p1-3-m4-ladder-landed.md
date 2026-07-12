---
id: p1-3-m4-ladder-landed
kind: decision
title: P1.3 M4 阶梯落地(2026-07-08,七批):F7/F6/F5 通电+F1 anchor 条件化洞修复+pose 映射层+cut 预算闸+等价回归+query_liftable 合同+P-HOM 门;F2/F3/F9/F4 终态登记;升格只剩 owner 显式决定
summary: M4 七 commit 全落地慢 lane 全绿:M4-A(aad0a7a) F7 全链+pose_id→pose_idx 映射层+F1 ghost 条件化修复(M3 遗留 anchor 条件性洞:cap 含 ghost 扣除+master anchor 是 u_vars 决策变量+无条件 Add 三件坐实,生产零暴露)+cut 预算闸(EXACT_CUT_FRAMEWORK_ATTACH_BUDGET=2000 满即停发=唯一 sound 最简 eviction)+等价回归层1/2(升格前置);M4-B(c4a0130) F6 baseline 计数容量+SoT 鸽笼下界 override 来源;M4-D1(73fa1cf) F5 BLOCK-2 多重集封口+canonical_relabel 幂等;M4-D2(d9ceb15) query_liftable 合同(LiftableScope 投影结构性剔除黑名单)+首个真 adapter binding_empty_domain_v1(登记为第 65 close-kernel sink,触发语义投影 hash 双钉+certified_artifact_contract runtime 锚三重钉的最深 reseal 链);M4-D3(38195e0) F5 named 版 attach 全链(presence nogood,all-or-nothing 比容量族更严);M4-D4(dadee58) P-HOM 结构门(orbit_homogeneity_digest 三件合并,fail-closed+artifact_hashes 漂移隔离);M4-D5(951b4f2) R10 两状态红测+per-family telemetry。**attach 链四族通电(F1/F5/F6/F7),F5 是 PROJECT_LOCK 钦定的 binding/routing 失败兜底族——生产 attach 点语义闭环完成。**
scope:
  domains:
    - p1-3-master-cut-integration
    - cut-framework
    - close-kernel
  paths:
    - src/cuts/lifecycle.py
    - src/search/benders_loop.py
    - src/models/exact_coordinate_master.py
    - src/search/f5_binding_empty_domain_adapter.py
    - src/search/orbit_homogeneity.py
  symbols:
    - step_8_apply_to_master
    - add_pattern_nogood_cut
    - add_power_pose_exclusion_cut
    - add_baseline_packing_cut
    - query_liftable
    - compute_orbit_homogeneity_digest
status: superseded
priority: P0
triggers:
  intents:
    - promote-cut-framework
    - implement-m5
    - wire-cut-family
    - modify-cut-framework
  keywords:
    - M4
    - M5
    - EXACT_CUT_FRAMEWORK_ATTACH
    - 升格
    - F5
    - F2
    - F3
    - F9
    - query_liftable
    - P-HOM
    - orbit lift
  negative_keywords: []
  paths:
    - src/cuts/lifecycle.py
  symbols:
    - step_8_apply_to_master
  error_regex:
    - "cut_framework_attach_not_certified"
  examples:
    - M5 从哪开始
    - cut framework 升格条件齐了吗
    - F2/F3 为什么没接
activation:
  layer_hint: L1
  must_know: false
  reason: M5 排程、升格裁定、任何 cut framework/adapter 改动(65 sinks!)都要以本卡为基线;不知道 F2/F3/F9/F4 的终态理由会重蹈「把不可 lift 判决接进 F5」类错误。
provenance:
  op: record
  reason: 2026-07-08 M4 七批收口,按 P1.3 大计划留档。
  evidence:
    - "commits: aad0a7a(A)/c4a0130(B)/73fa1cf(D1)/d9ceb15(D2)/38195e0(D3)/dadee58(D4)/951b4f2(D5);每批慢 lane 绿;双 checker 绿(14 obligations/65 sinks)。"
    - "F5 全链端到端: test_cut_framework_attach_wiring.py::test_full_chain_f5_binding_empty_domain_end_to_end(死端口 incumbent→adapter 判死→minimizer 收敛单字面→关卡链→真 master 落约束)。"
    - "M4 侦察材料(九份行号级报告,含 F2/F3/F9/F4 的 owner 拍板材料): docs/research/p1_3_m4_recon_20260708/——七路 Fable+一路 codex;D2 核心发现=binding demand 型 INFEASIBLE 反单调不可 lift。"
  updated_at: "2026-07-08"
---
> **Superseded 2026-07-12(修复批 β/文档实态外审 F10/F11)**:当前态见 `cut-framework-stage-b-current-20260712`。本卡仅作批次/历史证据保留,不再参与 active recall;正文中的「当前状态/待办/OPEN」段落均为当时快照,勿再据此行动。


P1.3 M4(F2-F7+F9 逐族阶梯)2026-07-08 收口。七 commit 与内容见 summary。

== 通电族与关键机制 ==

- **F1(修复)**: ghost-bound cut 必须挂选中 anchor 文字(OnlyEnforceIf);GHOST_AGNOSTIC(ghost∩R=∅)仍无条件恒真。M3 落的无条件 attach 是真 anchor 条件性洞(生产零暴露——总开关 unsafe map)。
- **F7**: add_power_pose_exclusion_cut=presence==0 under ghost literal+运行时闸(master 自查 coverers 表,有活 coverer 即拒——helper 漂移从静默错杀降级为当场拒绝)。等价回归层1(4761 anchor 三方全量对拍)+层2(真 master coverers 表 vs helper CoverSet)= PROJECT_LOCK 升格前置之一落地。
- **F6**: add_baseline_packing_cut=数「body 完全落在该 baseline」的 pose ≤ validator 重算过的 total_packable;cert 的 region_demand/group_demand 推理值刻意不进 master。generator 解锁=把 SoT 鸽笼下界 max(0,demand−对侧容量) 直接当 override 传(compute_sot_region_demand_overrides,纯几何零增量证明义务)。
- **F5(主菜)**: 四批(D1-D4)。BLOCK-2 多重集封口(validator 禁重复 (group,pose)+generator 拒发多重集 core)→布尔 presence 忠实;canonical_relabel 幂等+重标后重过 oracle 复验;query_liftable(core, LiftableScope, deadline) 投影结构性剔除 selected_poses/cell_owner;首个真 adapter=binding_empty_domain_v1(唯一 liftable 的 binding 失败型);master add_pattern_nogood_cut all-or-nothing 最严(nogood 少一成员=更强 cut=错杀,literal 建不出/alias 撞车整条拒)。
- **P-HOM 门(D4)**: F5 presence 翻译天然 orbit 级(组级 literal)——匿名提升在 master 侧隐式发生。orbit_homogeneity_digest(组同质+池无实例维度+profiles 快照)fail-closed 进 state builder+搭 artifact_hashes 漂移隔离的车。当前 empty-domain adapter 判决天然 orbit 级,P-HOM 门是防未来实例敏感 adapter 的结构前提。
- **cut 预算(M1 硬前置②,并入 A)**: attach 入口读统一计数器 coordinate_framework_cut_count(三个 API 都自增),BUDGET=2000 满即停发。CP-SAT 约束不可删→停发是唯一 sound 最简 eviction;真 eviction=master rebuild 归 M5。放宽到 10K+ 须生产 before/after 复测(verdict.md「不取消预算」)。

== 未接族的终态理由(M4 保持 fail-closed NotImplementedError) ==

- **F2(cutset)**: 三重死结——demand=吞吐量纲(PROJECT_LOCK B-1/B-2 明锁 out-of-scope,接=违锁);单层 4-邻接图 vs certified routing 双层桥语义未 reconcile(过切);route schema=P1.5+ owner 拍板项。出路=P2.0 吞吐轴或 owner 拍板连通弱化语义。
- **F3(port_exposure)**: v1.0 cert 无 active_port_witness(恒 None 不校验),master binding 语义=「端口够用就行」——堵一个门不必然死→直译过切。出路=Phase 1.5+ witness 机制,或 master 侧可算的窄化版(可用端口数==需求数时堵一必死)。
- **F9(density_envelope)**: Phase 1.2 决策数学绞死(K 必须==static safe_ub→只能发恒真冗余 cut)。解封需与 F5 同类的 replayable proof 升级(PROJECT_LOCK:461)。
- **F4(component_reach)**: commodity route registry 生产不存在且 schema=P1.5+ owner 拍板项;ghost-cause 弱形态触发率≈0。跟 P1.5+ registry 拍板走。

== D2 侦察的 soundness 关键发现(防复犯) ==

binding 子问题两种 INFEASIBLE 提升语义相反:empty-domain 型(纯 (op,pose) 白名单属性)可 lift;demand 等式型**反单调**(加设施=加 slot=放松等式,子集 INFEASIBLE 不蕴含超集)——生产 binding_infeasible 分支碰到的全是后者,天真把生产失败直接喂 F5=每条 cut 都错杀。query_liftable 合同+adapter 的 generic-hub 拒 lift 就是防这个。

== 升格三前置状态(EXACT_CUT_FRAMEWORK_ATTACH 出 unsafe map) ==

1. M4 阶梯: ✅(可 sound 接的四族全通电;F2/F3/F9/F4 有终态理由非遗漏)
2. helper-vs-master 等价回归: ✅(F7 层1/2+运行时闸;F1/F5/F6 各自的行为端到端)
3. owner 显式决定: **待**(PROJECT_LOCK Forbidden Change 条款,升格后继承 F-*/PCR-*/CUT-* 全部义务)

== M5 待办 ==

- 收敛实测(全项目唯一无理论保证处;L11 退路挂 owner)+ telemetry 验收阈值(>10^5 撞墙/<10^3 工作,attached_by_family 数据源已就位)
- evaluate 热路径优化(F4 的 O(|Grid|) BFS P1.21 债在案——若 F4 解封)
- 生产 worker model 生命周期核查(M1 内存滞留暴露面)
- CutStore campaign 持久化(V82 边界=fresh revalidated attach;预算不能靠存盘复用绕)
- Q1a recognizer 体系(R1/R4/R5/R6/R7+C6 telemetry 三拆完整版)归属评估——呈 owner
- cut 预算放宽复测(千级→万级需生产数据背书)

== 纪律(后续会话必知) ==

- **65 sinks**(D2 新增 f5_binding_empty_domain_adapter);orbit_homogeneity.py 在 V99 floor(import 闭包)。改 adapter/orbit 文件=reseal。
- 新 sink 登记的完整连锁=sink_files entry+classification map+V99 floor+语义投影 hash 双钉(checker 常量+manifest declared)+runtime 锚(certified_artifact_contract.py 的 LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256)三重钉+checker 自钉。
- adapter 放 src/search 不放 src/cuts(需 import src/models 的 port_binding;src/cuts 保持 import 隔离)。
- F5 scope.oracle_abstraction_version=adapter 名(binding_empty_domain_v1)非族名——available_oracle_versions 忘加 adapter 名=F5 全 HOLD 假通电。
