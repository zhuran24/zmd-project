---
id: p2-0-throughput-scope-and-design-doc
kind: decision
title: 吞吐认证是项目必做 scope(owner 2026-07-04)——范式设计稿 v1 已落 docs/research,锁边界暂不动
summary: owner 2026-07-04 拍板:离散吞吐/带宽认证从「out-of-scope 零排期」转为**必做的 planned P2.0**(原话意:不做吞吐这项目怎么实现)。但排期仍在 P1.2 close → PR2 深化 → P1.3 之后;PROJECT_LOCK §1A B 块与 canonical_rules semantics.mixed_commodity_flow 的 out-of-scope 声明**在 P2.0b 落地走完 freeze-ritual 前继续有效**——设计稿存在 ≠ scope 已改。范式设计稿 v1 = docs/research/p2_0_throughput_certification_paradigm_design_v1.md(commit 35791c3):fluid P7(T1-T6,建于 selected route graph)+ 显式公理组 A2-A5 + 双侧有理证书(FEASIBLE=有理流/INFEASIBLE=Farkas)+ 单调性引理(旧不可行剪枝保留、旧 CERTIFIED 降级未决)。动机:Fable-5 模型 2026-07-07 前后下线,把「难想的」提前做成设计稿,实现留给后续模型照稿做。
scope:
  domains:
    - certification-scope
    - throughput
    - roadmap
  paths:
    - docs/research/p2_0_throughput_certification_paradigm_design_v1.md
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - plan-next-work
    - throughput-scope-question
  keywords:
    - 吞吐
    - 带宽
    - throughput
    - bandwidth
    - P2.0
    - flow
    - 离散容量
    - fluid
    - Farkas
    - 第七谓词
    - P7
  negative_keywords: []
  paths:
    - src/models/flow_subproblem.py
  symbols: []
  error_regex: []
  examples:
    - 吞吐认证要不要做/什么时候做
    - P2.0 是什么状态
    - flow_subproblem 能不能升格
activation:
  layer_hint: L1
  must_know: false
  reason: 谈 roadmap/scope/吞吐时该想起:①吞吐已改判「必做」,别再引旧口径「研究级 future 零排期」;②但锁面未动,别把设计稿当 scope 已开。
provenance:
  op: record
  reason: owner 2026-07-04 明示「带宽肯定要做的呀,如果不做的话,这项目怎么实现呢」,并授权在 Fable-5 下线前把范式设计做掉。
  evidence:
    - "设计稿 commit 35791c3(docs/research/p2_0_throughput_certification_paradigm_design_v1.md,217 行)"
    - "GPT Pro 三工作包已 staged:C:\\Users\\22957\\pr2_pkg\\p2_0_throughput\\(盲设计对照/对抗审查/沙箱反例狩猎)"
updated_at: "2026-07-04"
---
owner 2026-07-04 两项相关拍板:

== ① scope 改判:吞吐认证必做 ==
离散吞吐/带宽认证从「OUT-OF-SCOPE BY DESIGN、Phase2+ 研究级、零排期」改判为**项目最终必做的 planned P2.0**。理由(owner 原话意):不证吞吐,项目的最终目的就没实现。
但注意两条边界:
- **排期不变**:仍在 P1.2 close → PR2 深化四阶段 → P1.3 cut 接入之后;不是现在实现。
- **锁面未动**:PROJECT_LOCK §1A B 块、canonical_rules.json:415-417(mixed_commodity_flow 的 out-of-scope 声明)在 P2.0b 走完 freeze-ritual 前继续有效。引用口径:「已定为必做、范式已设计、scope 待正式解冻」。

== ② 范式设计稿 v1(照稿实现,别重推范式)==
`docs/research/p2_0_throughput_certification_paradigm_design_v1.md`(35791c3)。核心结论:
- 第七谓词 **P7-fluid**:在 selected route graph 上存在满足 守恒/组件聚合容量(belt 1.0/tick 跨商品)/端口容量/机器 u∈[0,1] 耦合/production_targets 的**有理**稳态流。只约束原始 targets,不约束派生 commodity_demands(防 over-constraint 伤最优性)。
- **公理组 A2-A5** 显式承担离散语义鸿沟(merger 公平/splitter 可分/环 bootstrap/周期平均),消解走 owner 游戏实测 → canonical semantics 机器化(先例:2026-07-02 routing 四裁定,见 [[routing-game-semantics-rulings]])。
- **双侧证书**:FEASIBLE=有理流 witness、INFEASIBLE=Farkas ray,复验器纯算术、不信 solver;有理对偶基建与 P1.3 F1/F2 LP-dual 欠账共用——**P1.3 先行,P2.0b 复用**。
- 单调性引理:加谓词=收紧 ⇒ 历史不可行剪枝全保留 sound、历史 CERTIFIED 降级未决、最优空矩形预期收缩(P7 是改答案,不是盖章)。
- 关键事实:速率数据全在 canonical_rules 且已 hash 钉死,不需新数据;现有 flow_subproblem.py 生产调用已退化(port_dict 用 dummy_commodity 对不上真实 demands,benders_loop.py:5713-5723),P7 须新建模块,禁改造。

== 背景:Fable-5 下线前的「先想后做」策略(三稿已全部落地 2026-07-04)==
Fable-5 约 2026-07-07 下线。owner 授权把 backlog 里最吃推理的部分提前做成设计稿(纯 docs/research 产出,零 reseal 成本)。三稿全部完成:
1. 带宽范式 v1(`p2_0_throughput_certification_paradigm_design_v1.md`,35791c3);
2. F5 orbit lifting v1(`p1_3_f5_orbit_lift_soundness_design_v1.md`,c2644a4)——修正"132!"叙事(真实轨道=8个 operation_type 组)、定理1谓词不变性+P-HOM 机器化前提、定理2轨道提升 soundness、与 master 序复合引理;发现提升机械已存在一半(AnonymousSlotRef/multiset evaluator/master presence nogood 标签擦除),缺的是定理与前提守门;
3. terminal 全域无解证书 v1(`terminal_no_solution_evidence_contract_design_v1.md`,f5a95be)——逐维反单调引理+最小覆盖坍缩(标准域下证书=单个 (6,6) 的 replay-verified INFEASIBLE);地基盘点:候选级 INFEASIBLE 已是可 sink-replay 强状态;诚实声明 false-INFEASIBLE 无 fixed-witness 等价兜底(P-TNS-H 增强选项待 owner 定级)。
GPT Pro(无限额度+沙箱)当三角色用:盲设计对照/对抗审查/反例实验(共 4 zip 5 prompt,owner 手机通道收发)。**五会话结果已回收、triage 完成、三稿 v2 已落 main(2026-07-04)**:
- 外审原件归档 `docs/research/p2_design_external_reviews_20260704/`(84ca691);
- **v2 = 实现基准**(68cdccc;v1 已标 superseded):吞吐 v2 主结构换两层范式(TP7-S 平均层 Farkas 不可行证书 + TP7-D 离散周期 path-phase 为发布级可行证书)+修 5 BLOCK(源口=boundary_io+protocol_core=52 等);F5 v2 定理前提收紧(liftable-reject、禁重复 (group,pose))+P-HOM 已全量机器验证(266条0违例);TNS v2 合同/接线层重做(authoritative 域、负向异构复验硬门、resume 生命周期、sink projection)。
- 沙箱 CE1-CE4 反例集校准公理组(CE4 多输入队首阻塞=新机制,归 A8+FIFO trace)。
- 注意:同内容提交 e7e0425 存在于 pr2-1-min-tcb-closure 分支(提交时共享工作区被并发会话切了分支,已 cherry-pick 到 main 68cdccc,分支上的留待合并自动消解,勿重复处理)。
