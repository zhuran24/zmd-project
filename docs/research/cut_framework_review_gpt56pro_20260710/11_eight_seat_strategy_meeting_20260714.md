# 11 — 八人战略会议纪要(2026-07-14):「慢=死」约束下如何拿到有界证明

> **历史失效标记（Batch 4，2026-07-18）**：本文对 routing FRONT
> precheck 的“真墙”定位及约 1,499 次拒绝/零 routing attempt 等数字已撤销
> （RND-01）。四实例条件式规约仍可保留；逐项边界见
> [历史重判附录](../front_offset_incident_20260718/01_historical_rejudgment_addendum.md)。

> owner 召集的八人会(4 claude + 4 codex,真·点对点第二轮)。命题:在本项目「任何只保证最终收敛的方法=死」的约束下,什么策略能产出**有界大小的全局最优证明**而非赌收敛?
> Chair(team-lead)在会中用批C 执行计划 §7 实测 + codegraph 把两个 load-bearing 事实定案后注入,八席在**正确的问题**上收口。
> 席位:claude-s1(§4夹逼)/s2(混合剪枝)/s3(怀疑者)/s4(认证优先);codex-s1(Farkas)/s2(OR理论)/s3(§2完备性)/s4(对抗现实)。
> 原始 r1/r2 逐席立场在 `scratchpad/meeting_r1|r2/*.md`;chair 已核实事实在 `scratchpad/meeting_chair_verified_facts.md`。

## 0. 一句话结论

整场「§4 全局夹逼 vs 混合 vs Farkas」之争,被 live+sealed 机制**精确规约成同一个 ~4-实例问题**;八席收敛到唯一逃出收敛赌注且认证契合的策略 = **对这几个固定小矩形做「双轨裁决」**(construct-then-verify 找可行 witness / binding-且-layout 不变的 Hall·min-cut 结构证书),两轨都 **recompute-check 不重解**;成败系于一个半天的 **go/no-go 便宜实验**,其唯一有效判据 = **不可行性核是否 binding-不变且 layout-不变**。

## 1. Chair 已核实的三个 load-bearing 事实(证据=批C §7 + codegraph,不是推演)

1. **§2(scout 钦点的"明确赢家")已经花掉**:sink 容量下界早已接进 certified master(`infer_certified_optional_lower_bounds` master_model.py:1964/2014 算 ceil(2/3)=1 → `_required_protocol_storage_box_lower_bound` :5396 + `exact_coordinate_master.py:6805-6839` 强制 fixed+residual;PROJECT_LOCK:317/345 钉死)。三席(claude-s3/codex-s3/codex-s4)独立指认 + codegraph 坐实。scout 的 spike-1 是在复现一件 HEAD 已做完的事(07-08 旧数据 cuts_6x6.json)。→ 「上收 sink 容量」不是候选。

2. **D1 真墙 = binding↔routing 枚举循环,不是 FIXED_SEARCH、不是慢 solve**:F-6(probe_7 CP-SAT 日志+py-spy)——binding 秒级出 selection(单次 0.01-1.6s **全 OPTIMAL**)→ routing FRONT precheck 拒(`routing_attempts=0`,full CP-SAT router 从未上场)→ `add_nogood_cut(selection)` 整点排除 → 重解。~1 轮/秒、数千轮、**无循环级预算帽**(F-1)。probe_8/11/13 三点全同款:`routing_precheck_rejections≈1499`、`routing_front_blocked_cut_count=0`(结构 cut 从未触发,纯 micro-nogood 震荡)。FIXED_SEARCH(F-5)真实但与段级时长无关(微 solve 无并行价值)——改 branching 救全链已证伪(cf76bed 撤销/f1eb29b)。

3. **D2 A* 是小矩形,不是大洞**:§1b scan——6×7、7×6(area 42)master 都 OPTIMAL 出解(search ~485s、峰 43G),但 binding 循环 ~4500 轮不收敛 TIMEOUT@7200s。"难点快速 INFEASIBLE 假设整体落空"。frontier 已被 `compute_terminal_frontier_projection` 压到 6×6/6×7/7×6 一小撮。**但这几个 UNDETERMINED(TIMEOUT≠INFEASIBLE),且零 incumbent(manifest best_certified_result:null)**——量级严格未判,只知落在小 regime。

## 2. 关键规约(claude-s2 提出,codex-s4 concurs,无人驳倒规约本身)

`compute_terminal_frontier_projection` 实测可复现:

| 状态 | potential_domain | frontier |
|---|---:|---:|
| 无 incumbent、空 records | 2361 | 36 |
| 只判掉首层 36 个极大点 | 2325 | 37(几乎不坍缩) |
| **area42 witness + 三个上侧极小锚点 (6,8)/(7,7)/(8,6) INFEASIBLE** | **0** | **0** |

→ **全局 certified 最优证明 = 3 份 INFEASIBLE(三锚点 up-closure 平铺所有 area>42)+ 1 份 area42 witness(objective 支配所有 ≤42)。** 证明规模固定(4 实例)、不依赖 Benders 何时"学够"。**"36" 只是瞬时波前宽度、不是总证明规模**(codex-s1/s3 纠正,claude-s2 认)。

**推论(全场最重要的收敛)**:全局/frontier 侧已经不是战场。真墙 = 让这 ~4 个固定小实例的 binding↔routing **终止**。谁能让它们终止谁就赢。

## 3. D1-D4 最终裁定(八席一致,除注明外)

- **D1**:真墙 = binding↔routing 枚举循环(见 §1.2)。FIXED_SEARCH 误诊。
- **D2**:A* 小(area~42),但 4 实例 UNDETERMINED、零 incumbent、量级未判。
- **D3 — Farkas 作主闭合路线死**:binding LP 是 TU/integral(codex-s1/s2 重放 cuts_6x6 实测,generic 槽运输矩阵),只得平凡 `3Σx_box≥2`(=已花掉的 sink 下界)。routing 是**连通性不是吞吐**,拒绝来自便宜的 FRONT precheck(组合可达性)不是 LP;连通性 LP 松弛在整数不可行时**仍分数可行** → 无非平凡对偶射线。flow_subproblem 是 diagnostic-only/吞吐向(PROJECT_LOCK §1A OUT-OF-SCOPE)→ 不能当 exact-safe Farkas 前提。**LP-dual 的内容只以组合 Menger min-cut / Hall 形态存活。** §3 至多做少数 LP-infeasible 容量/割集冲突的 separator。
- **D4 — 证书必须 shape-aware + 两重不变性**:标量面积界无用(frontier 已在 42)。证书必须 ①**binding-不变**(一次覆盖全 selection 空间,不是压缩已观测的 1500);②**layout-不变**(对该 ghost 下所有合法 placement 成立,不是只拒一份 occupied_cells)。**面积/计数证书给不出路由连通不可行性**(claude-s2 正面回应 Chair,答:不能)。

## 4. 单一推荐策略:~4 固定小矩形的「双轨非对称边界闭合」

两轨都必须 **recompute-check(重算)不 re-solve(重解)**——这是认证席(claude-s4)的北极星:producer 可贵/启发式(TCB 外),checker 只能重算。

### 正侧(最高优先)· construct-then-verify 找 witness
对最小未判 ghost(6×6→6×7/7×6),**启发式/手工显式构造**一份完整布局(设施 placement + ghost + port binding + 精确槽计数 + 电线杆覆盖 + **显式 belt/route 路径**),再**一次性多项式验证** 6 谓词(连通=BFS、计数=数、覆盖=扫)。
- 命中任一 area42 witness → **它就是 A*、直接收官**(I1 平凡重放 6 谓词,天然 recompute-checkable);构造失败只能记 UNKNOWN、**不得反推 INFEASIBLE**。
- **为什么逃出赌注**:它是**搜索问题**(找一份好布局)不是全称量词证明;显式构造路由**绕开 full router 32G(C 层)**、直接选 placement+binding **绕开 A/B 枚举**;把"提→拒→重提"循环塌成"验一个候选",循环消失、loop-free。这是唯一同时绕开三层墙的招。

### 负侧(仅当确 infeasible)· binding-且-layout 不变的结构证书
不产整点 nogood(只能重解检=死),而是提取一条 **O(1) 的 Hall / min-cut 全称不等式**:
1. 从冻结工件重建**所有可能 binding pattern 的 front 超集**;
2. 重算该 ghost 形状下**不可避免的强制占用** / free-front 容量 / 几何割容量;
3. 验 `capacity_all_bindings < required_ports / demand`;
4. 证该容量界**不依赖某个 selection、也不依赖某份具体 layout**。

- **两个 recompute-validator 已在代码里**:`validate_cutset`(cutset.py:276,零重解重算割边+验 Menger `demand>cut_size`)、component_reach 同构;类型可由 `analyze_exact_routing_domain`(routing_subproblem.py:400)读出:`front_blocked/blocked_ports`=port_exposure 型,`relaxed_disconnected/disconnected_commodities`=cutset/Menger 型。
- **坑(必须避)**:port_exposure 是 literal-based/per-binding——把 1500 nogood 压成 1500 条更小 clause = **只是更快的枚举**,master 提第 1501 个就漏、I1 检验成本随 clause 数涨=检验死。唯一有界的是 **binding-不变计数**(Hall:free-front 周长<所需端口;min-cut:跨割容量<需求)。
- 缺的两块:①这些族 certified 下仍禁用(待 B6 owner flip);②**没有 generator 从枚举循环的失败里抽出 Menger/Hall 割**——循环现在吐整层 micro-nogood、把冲突原因扔了。

## 5. GO/NO-GO 硬门(全场收敛的裁判)

**不可行性核是否 binding-不变 且 layout-不变?**
- **是** → 一条 recompute-checkable 计数不等式灭全族 → **有界证明存在 → 目标可达**。
- **否**(脆性:各绑不同 selection/layout 的 literal 冲突) → 唯一证书=整层 nogood → 唯一检验=重解 → 撞 D1 墙 → **certified 全局最优在当前算力下不可达**(不是工程不够努力,是正确的不可行性证明也检不动)。

## 6. 最便宜的决定性实验(1-2 天,zero-sealed,双门 kill-gate)

全部在 probe_14 冻结的批C 数据上,不重跑 60G master。

- **T-负(半天、纯算术、最便宜)**:对 probe_14 固定 layout 的 `occupied_cells`+ghost+`port_specs` 直接算 **layout 级 Hall 不等式**——强制 mandatory 占用是否把可作 boundary_port front 的自由周长 cell 数压到 < 所需 port 数;并测其 **binding-不变性 + layout-不变性**(不是看"1500 个共享哪些 cell"=症状级假阳性,而是从全 binding 域 + 冻结几何重算)。是=上界活;否=转正侧。
- **T-正(半天)**:手构一份 6×7-ghost 完整布局,跑一次性 6 谓词验证(loop-free),直接探 6×7 到底 feasible。命中=A* 收官。

判据(codex-s3/s4 的严格版):每锚点 O(1) 证书、分钟级复验、无需 joint solve、独立 checker 从全 binding 域+冻结几何重算(不得读 1500 历史 selection 当完整性依据)。任一条不满足 → 负向有界路线判死。

## 7. 无人正面驳倒的对抗锚点(claude-s3/codex-s3/codex-s4,必须随结论上交 owner)

**「个数有界 ≠ 单点终止;batch-C 至今 prod-scale 终止点 = 零。」** 所有"混合-有界 / frontier-36 / 3负+1正"machinery 界住的都是**不要命的量**(锚点个数),对**要命的量**(单个 prod-scale 锚点是否终止)集体沉默。manifest null、4 实例全 UNKNOWN/TIMEOUT。在有人真拿出**一个 prod-scale 终止点**之前,所有"有界"主张只在外层循环成立。诚实先验偏悲观(连通瓶颈常 placement-specific;唯一找到过的可泛化核=sink 已被 lift 走=选择偏差)——**但这是先验不是定理,必须量、不能判死**。上面的 T-负实验就是这个先验的可证伪兑现路径:front 上收后一个 6×6 若仍不终止,混合派已当场承诺改判 certified-unreachable。

## 8. 排期建议(Chair)

1. **立刻做 §6 双门实验**(zero-sealed、我的授权内、是 go/no-go)。先跑 T-负(最便宜)+ T-正(直接可能收官)。
2. 结果三出口:witness 命中→若在天花板即 DONE;核 binding+layout 不变→造 cutset/Hall 证书(需 B6 owner flip 才能进 certified attach);两者皆无→**诚实上交 owner:当前算力下 certified 全局最优不可达**,这是 owner 级战略决策(换算力/换目标口径/接受 exploratory 边界)。
3. 与既有排期的关系:这条**不依赖** B6 flip / F5 转正就能先做实验(纯只读 harness);只有负侧证书真要**进 certified attach** 才碰 B6。

---
*会议机制备注:codex 席(sonnet 转发层)实测持有 SendMessage(团队框架注入),八席真·点对点盘诘;codex.md 声明已订正。四个 claude 席全部在盘诘中改判(claude-s1 撤大洞、claude-s3 撤"结构已死"、claude-s2 撤"§2终止器"+"36坍缩"措辞、claude-s4 收窄证书形态),codex-s4 撤回 UB≤42——收敛是被证据逼出来的,不是附和。*
