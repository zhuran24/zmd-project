---
id: cut-framework-stage-b-current-20260712
kind: status
title: cut framework 当前态(2026-07-12):Stage B B0-B5b+批D+修复批α/α2 全落地;F1/F6/F7=typed lowering 唯一写 master 通路;F5=shadow-only 无 lowering(真 adapter 在 verifier 前 fail-closed);F2/F3/F4/F9=LEGACY_DIAGNOSTIC registry 拒绝;gate 仍 unsafe/default-off 待 B6 owner
summary: 取代 M3/M4 时期三张旧卡的当前态。Stage B B0-B5b 已全部完成(typed 平台+三族纵切+B5a wiring cut-over+B5b AST lockdown),另加批D(RFC-002 F5 独立 verifier)、修复批 α/α2(pre-promotion 信任根硬化+master 写入面锁定)、B6 前置工程批(session-bundle session 级所有权+F-05 alias 一跳+sink 注册 owner won't-do)与批E RFC-003(编排层 semantic dedup+严格非消费 JSONL ledger+family 参数开关,owner 批准重生成 waiver)。F1/F6/F7=COMPILABLE,唯一写 master 通路=typed registry→resolver(ModelScopeBinding 唯一构造)→step_8_apply_to_master→typed_apply(调 master _lower_*);F5 只产 ShadowValidated、无 ConstraintPlan/lowering、结构上改不了 master(B5a 物理删除旧 apply 分支;独立 verifier 已落地但真实 adapter 因 frozen tuple/list 形态差异在 verifier 前 fail-closed,可达性哨兵钉死);F2/F3/F4/F9=LEGACY_DIAGNOSTIC 在 typed 单入口 registry 边界拒绝(旧「step_8 NotImplementedError fallback」机制已随 B5a 退役——别再按它规划);F8 retired。EXACT_CUT_FRAMEWORK_ATTACH 仍在 certified unsafe-map/default-off。开放项=批C(PIC-4+生产层 PIC-5+RFC-003 门6 prod A/B)、B6 owner 手动门、F5 转正批(非 flip 前置)。机器口径:sinks 67、cuts 833(07d04b3 快照)、slow 24 登记→31 实例。
scope:
  domains:
    - p1-3-master-cut-integration
    - cut-framework
    - close-kernel
  paths:
    - src/cuts/lifecycle.py
    - src/cuts/typed_platform.py
    - src/cuts/typed_apply.py
    - src/search/benders_loop.py
    - src/models/exact_coordinate_master.py
  symbols:
    - step_8_apply_to_master
    - _maybe_attach_framework_cuts
    - ShadowValidated
    - ModelScopeBinding
status: active
priority: P0
validity:
  until: "下一个改变 cut framework 架构态的批次落地(批C 实测结论 / B6 owner promotion / F5 转正批)之前本卡为当前态"
  invalidated_by: "B6 owner promotion、F5 转正或任何改动 typed 链拓扑的批次落地——届时按生命周期规程 supersede 本卡(07-12 深夜注:session-bundle/RFC-003/B6前置已落地,属开放项收窄,就地订正非 supersede)"
triggers:
  intents:
    - wire-cut-family
    - promote-cut-framework
    - modify-cut-framework
    - implement-m4-ladder
    - plan-b6-promotion
  keywords:
    - step_8
    - cut framework
    - EXACT_CUT_FRAMEWORK_ATTACH
    - typed_apply
    - ShadowValidated
    - Stage B
    - B5
    - B6
    - F5
    - pattern_nogood
    - region_capacity
    - 升格
    - 转正
    - lowering
  negative_keywords: []
  paths:
    - src/cuts
  symbols:
    - step_8_apply_to_master
    - _maybe_attach_framework_cuts
  error_regex: []
  examples:
    - F5 的 cut 现在是怎么进 master 的,step_8 接了哪些族?
    - 接下来给 cut framework 加一族/改 lowering,当前架构长什么样?
    - B6 转正前还差什么,attach 门现在什么状态?
activation:
  layer_hint: L0
  must_know: true
  reason: 旧 M3/M4 卡宣称的「F5 已接 step_8/其余族 NotImplementedError/B5 待办」与源码相反;按旧态规划会给不存在的 F5 master API 做加固、重复迁移、错估 reseal 面(07-12 文档实态外审 F10 定性为最危险的双文档系统分叉)。
provenance:
  op: supersede
  supersedes: [p1-3-m3-step8-landed, p1-3-m4-ladder-landed, p1-3-kickoff-recon-facts]
  reason: 2026-07-12 文档实态外审(zmd_doc_audit_20260712)F10:三张 P0 旧卡的「当前态」断言(F5 已接 step_8、其余族 step_8 NotImplementedError fallback、B5/M4 待办)已被 B5a/B5b/批D/α/α2 的落地推翻;修复批 β 按 vnext 生命周期规程 supersede 并立此 current 卡。旧卡的批次落地史实仍真,保留为历史证据。
  evidence:
    - "src/cuts/typed_platform.py:1397-1489(registry:F1/F6/F7=COMPILABLE/TYPED,F5=VALIDATED/TYPED compiler=None,F2/F3/F4/F9=LEGACY_DIAGNOSTIC,F8=RETIRED)"
    - "src/cuts/typed_apply.py:44-82(operation 表仅 region_capacity_le/shape_packing_hall_le/power_pose_exclusion)"
    - "src/tests/cuts/test_f5_independent_verifier.py(真 adapter 可达性哨兵:verifier 前 fail-closed)"
    - "docs/research/cut_framework_review_gpt56pro_20260710/03_stage_b_implementation_spec.md(B0-B6 批次序列+07-12 F02/F09 审计校准)"
    - "docs/research/cut_framework_review_gpt56pro_20260710/05_batch_alpha_prepromotion_hardening_spec.md(α/α2 执行记录+双审裁决)"
updated_at: "2026-07-12"
---
**cut framework 当前态(2026-07-12,批E 后 HEAD `1c2c1ab`;本卡取代 M3/M4 时期口径)**:

- **已落地**:Stage B **B0-B5b 全部完成**(契约壳→bundle/snapshot→typed 平台→F1/F6/F7 三族纵切→B5a wiring cut-over→B5b AST lockdown)+ **批D**(RFC-002 F5 独立 verifier,Kuhn 匹配,sink 66→67)+ **修复批 α/α2**(pre-promotion 信任根七道 fail-closed 门 + master 写入面锁定收尾)+ **修复批 β**(文档/记忆层同步)+ **B6 前置工程批**(`ef5e124`:session-bundle session 级所有权兑现——原 promotion 前 BLOCK 已消解、F-05 alias 一跳 dataflow 追踪、sink 注册 owner 改判 won't-do)+ **批E RFC-003**(`7875902`/`dd1a182`/`c10d317`/`1c2c1ab`:编排层 semantic dedup(applied-only pool,per master build)+严格非消费 JSONL 审计 ledger(`src/cuts/ledger.py`,restart 重取资格=重生成,owner 批准 waiver)+`enabled_cut_families` 参数开关+receipt v1;RFC 门6 保持 OPEN→批C)。
- **写 master 的唯一通路**(F1/F6/F7,COMPILABLE):typed registry → resolver(`_resolve_model_scope_binding`,`ModelScopeBinding` 唯一构造、AST 钉唯一 caller)→ `step_8_apply_to_master`(七道 α 门:内容绑定/exact-type/cache 一致性/fresh 投影重算/身份重验/master weakref)→ `typed_apply`(三行 operation 表调 master `_lower_*`——add_* 已私有化改名)。
- **F5 = shadow-only**:只产 `ShadowValidated`,无 `ConstraintPlan`、无 lowering,**结构上改不了 master**(B5a 把旧 apply 分支物理删除,agnostic-F5 语义缝=PIC-2 就此消灭)。独立 verifier 已落地,但**真实 `BindingEmptyDomainAdapter` 因 frozen tuple/list 形态差异在 verifier 前 fail-closed**(`isinstance(pool, list)` 对冻结 tuple 恒 FEASIBLE→前置 reverify 恒拒),verifier 真路径暂不可达、有哨兵测试钉死;`independently-verified` tag 当前仅测试 oracle 链可达,**不是生产背书**。
- **F2/F3/F4/F9 = LEGACY_DIAGNOSTIC**:在 typed 单入口的 registry execution_path 检查处 fail-closed 拒绝,只保留 replay/诊断(legacy 表 HELD、禁 reactivate)。**旧「step_8 `NotImplementedError` fallback」机制已随 B5a 退役**——别再在那一层加分支/异常处理/测试。F8 retired。
- **门**:`EXACT_CUT_FRAMEWORK_ATTACH` 仍在 certified unsafe-map、default-off,双入口红测在位。
- **开放项(到 promotion;07-13 晚批C 执行日+owner 四项拍板后口径)**:①**批C 收尾** = 矩阵零头(rollback 演练/多 rect 序列/oracle 开销测量/prod 层注入式演习点,~2-3h,07-14 白天清)——核心 A/B 矩阵 07-13 已收官(3 尺寸×on/off+复跑 7 点:证明面逐位等价×3 对+复现+跨尺寸一致,cap=1500 口径,cell.json 首批落地;判定口径 owner 已裁「两条腿」:无害性用 cap 矩阵、门6「触发>0」格用注入式演习、自然触发降观测项);②**B6 owner 手动门**(unsafe map 翻转+红测预期翻转+checker 登记+lock 授权改写;07 规格多跳 alias 张力已消解——owner 07-13 裁「一跳为界」、多跳归发布时点防内鬼桶,订正注在 07 号规格 §3.3);③**F5 转正批**(批D 规格 §5 五项;**非 flip 前置**,lock:492;排期 owner 已裁「B6 先走、F5 紧随不合批」)。批C 执行日工程沉淀:binding↔routing 枚举循环 F-6 定案+三 reseal 批(`cf76bed`/`34cb0aa`/`9deec8f`),`EXACT_B1_BINDING_ALT_CAP` 现为 certified 合法轮数预算(fail-closed UNKNOWN,F-BL-R3-01 背书)。
- **机器口径(07-12)**:checker 15 obligations/67 sinks;strong-status 65/83;cuts 833;slow 24 登记→31 实例。批次提交里的 cuts N 是当时快照。
