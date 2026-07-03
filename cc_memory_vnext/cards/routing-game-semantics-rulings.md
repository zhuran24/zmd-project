---
id: routing-game-semantics-rulings
kind: decision
title: owner 2026-07-02 对算法核心的四项游戏语义拍板(拐角 pose / 十字传送格子 / 混流 / 连通量词)——已全部机器化落地并合入 main(3c99ed0),本卡为语义决策的历史权威
summary: 数学面外审(algo_core_audit baa2142,8 份报告)triage 后 owner 拍板四项游戏语义,全部是 canonical_rules.json 没写、代码硬编码在承担的语义。①拐角 pose:恢复 boundary_storage_port 两个 (0,0) pose(left_base 竖占 {(0,0),(0,1),(0,2)}、bottom_base 横占 {(0,0),(1,0),(2,0)}),互斥归 no-overlap 管,候选域预删是过紧 BLOCK;修复=生成器循环 1→0 + 重冻结 candidate_placements(freeze-ritual,预期 66,403→66,405 pose)。②"elevated bridge"真实语义=十字传送格子:单格部件、两条互相垂直的直通道(纵向占上/下口、横向占左/右口),两通道互不接触、可分属不同货;一格只有四个口→平行双流物理不可能(owner:显然)。当前 L0/L1 双层建模是其等价表示,layer-blind 邻接是**正确**的(不存在真实的"层",无坡道概念),单格使用合法;但当前编码(routing_subproblem.py:1063-1074)缺垂直性约束、允许同格平行 overlap=物理不可能状态,要补。③混流允许:一条 belt 可先后运多种货(A-B-A-B 排队);现编码 AddAtMostOne per (cell,layer) 跨 commodity 互斥=真·过紧 BLOCK(威胁 lex 最优性),修复=拆 phys(物理组件)/use(商品借道)两层变量;canonical 全部 17 配方单产物→binding"每口一货"不受冲击。④连通量词维持现判据:每 sink 从某 source 可达+每 source 能到某 sink,允许同商品多个独立岛;witness 孤岛后验检查(每个 selected state 须在 source→sink 闭包内)是卫生修复,直接做。(2026-07-04 注:四项已全部落地——批次1 freeze-ritual `d1845dc`,批次2+3 随 mixflow-routing 合入 main `3c99ed0`;语义权威已转到 canonical_rules.json+代码,本卡转历史记录,但修 routing/生成器前仍该读,防把刻意语义当 bug。)
scope:
  domains:
    - algorithm-core
    - routing
    - canonical-semantics
    - placement-generator
  paths:
    - src/models/routing_subproblem.py
    - src/placement/placement_generator.py
    - rules/canonical_rules.json
    - data/preprocessed/candidate_placements.json
  symbols:
    - _add_bridge_constraints
    - _add_capacity_constraints
    - gen_boundary_ports
    - _validate_selected_route_connectivity
status: active
priority: P1
triggers:
  intents:
    - modify-routing-model
    - modify-placement-generator
    - edit-canonical-rules
    - triage-algo-review
    - freeze-ritual
  keywords:
    - routing
    - 混流
    - 传送格子
    - 十字
    - bridge
    - 高架
    - 拐角
    - corner
    - boundary_storage_port
    - candidate_placements
    - canonical
    - 连通
    - 量词
    - 孤岛
    - witness
    - phys
    - layer-blind
    - 垂直
  negative_keywords: []
  paths:
    - src/models/routing_subproblem.py
    - src/placement/placement_generator.py
    - rules/canonical_rules.json
  symbols: []
  error_regex: []
  examples:
    - 实现 routing phys/use 拆层重构
    - 改 canonical 的 routing_rules / bridge_mechanics
    - 重冻结 candidate_placements
    - 为什么 layer-blind 邻接不算 bug
activation:
  layer_hint: L1
  must_know: false
  reason: 修 routing/生成器/canonical 时若不知道这四项拍板,会把"正确的 layer-blind"当 bug 修、或把"过紧的 commodity 互斥"当规则保留——方向直接反掉。canonical 已落地(3c99ed0)后本卡是语义决策的历史权威,改相关代码前仍先读。
provenance:
  op: record
  reason: 2026-07-02 数学面外审 triage,owner 逐条拍板;十字格子语义是 owner 纠正外审(GPT 把部件理解成了高架桥,owner 当时没纠正);混流用 A-B-A-B 生产场景确认;垂直性由"一格四口"直接推出。
  evidence:
    - "核实 workflow(5 路 codex 回源码):corner pose 预删 confirmed(canonical/schema 无拐角排除表达、LOCK:317 互斥归 no-overlap);layer-blind 邻接/AddAtMostOne 跨 commodity/witness 孤岛判据缺失 全部 confirmed(routing_subproblem.py:1058-1061,1063-1074,1636-1698);clearance 假阳性(PROJECT_LOCK.md:117-120 已裁非 P 谓词);I1 overload env 降级 guarded(env 在 certified forbidden 类)。"
    - "canonical_rules.json recipes 节 grep:全部 outputs 单商品。"
  updated_at: "2026-07-04"
---
数学面外审 triage 后 owner 的四项游戏语义拍板(2026-07-02),全部是 canonical 没写、代码硬编码承担的语义。修复排期:批次 1 = freeze-ritual 一次打包(拐角 pose 恢复 + candidate_placements 重冻结 + canonical 语义机器化四项;pinned hash 更新与 reseal 属发布面,走子代理);批次 2 = routing 拆层重构(phys/use + 垂直性 + 孤岛检查,认证核心改动必跑 --slow-tests);批次 3 = loader parity、I1 文档降格、anti-drift 测试;推迟 = I1 overload 参数化(动 benders_loop,等 pr2-5 merge 后做,避免撞 round-19 witness 门双倍 reseal)。**(2026-07-04 注:排期已全部执行完——批次1 `d1845dc`;批次2+3 随 mixflow-routing 合入 main `3c99ed0`,尾巴 `9aa4176`/`a8ea631`;推迟的 I1 overload 参数化由 `a731764` 落地(use_overload_separation 参数,I1 独立复验显式传 False);pr2-5 也已于 `6e06922` 合入。)**

== 四项拍板细节 ==

**① 拐角 pose(恢复,过紧 BLOCK)**:gen_boundary_ports() 左/下基线循环从 1 起跳过 (0,0),但两个拐角 pose 各自几何合法,canonical/schema/LOCK 均无拐角排除表达;"两者互撞"该由 no-overlap 管(PROJECT_LOCK.md:317),不该预删候选域。46 仓口×3 格=138 格 vs 两边共 139 格,近饱和,少 2 pose 有真实机会把可行紧布局误判 INFEASIBLE→连坐剪更大矩形→false-CERTIFIED 次优。

**② 十字传送格子(纠正外审的根本误读)**:部件不是"高架桥"而是单格十字交叉器——纵向通道(上进下出/下进上出)+横向通道(左进右出/右进左出),互不接触、可分属不同货、可只用一条。推论:(a) 双层建模只是表示技巧,layer-blind 邻接**正确**,"跳层/坡道"担忧整个消解;(b) 一格四口→同格平行双流物理不可能,当前编码却允许(只禁 L0 非直线、不查方向垂直)→补垂直性约束,只剪物理不可能状态、不伤真解;(c) 单格使用(=跨过一条地面带)合法;(d) canonical 的 layers/bridge_mechanics 表述要按十字格子语义改写,防 reviewer/维护者再被"高架桥"带偏(这轮外审就是被带偏的实例)。

**③ 混流允许(过紧 BLOCK 坐实,最大修复件)**:游戏允许一条带先后运多种货。现编码把所有 commodity 变量塞同一 (cell,layer) 桶 AddAtMostOne→强制商品间 cell-disjoint 路径=凭空多出的约束,空间紧张布局被误判摆不下,直接威胁 lex 最优性。修复:phys[cell,layer,pattern] 层管"放了什么部件"(AddAtMostOne 作用于此)+ use[commodity,...]≤phys 管"谁借道";连续性/edge balance/successor/predecessor/port adherence 移到 use 层。连锁:输出 schema route cell 单 commodity 字段要改、测试大面积适配、env-gated 消费者需编译通过。

**④ 连通量词(维持+固化)**:现判据"每 sink 有源可达+每 source 达某 sink"(允许同商品多独立岛)是有意选择(test_routing.py:261-297 固定),owner 确认维持,写进 canonical。独立小修:复验不查 selected state 是否都在送货路上→证明材料可含"孤立环"垃圾;补后验全覆盖检查,查不过重解,不剪真可行解。

== 相关 ==
外审 triage 全程与上下文卫生纪律见 [[guardrail-delegate-adversarial-reads]](发布面细节别进主线程);外审提示词纪律见 [[review-prompt-audience-purity]]。
