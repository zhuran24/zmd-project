# 12 — go/no-go 前障碍 spike 结果(2026-07-14):双模型独立算 + 四席对抗验证

> 承 doc 11 八人会议的 §6 决定性实验。工作流 `wf_6d213858-32f`(12 席:4 Map + 4 Compute[claude/codex 各半 T-负/T-正] + 4 对抗 Verify[claude/codex 混]),zero-sealed 只读,~46min。
> harness 在 `scratchpad/spike_gonogo/`;journal 在 `subagents/workflows/wf_6d213858-32f/journal.jsonl`。

## 0. 一句话结果

**偏悲观的未决(UNKNOWN,leaning pessimistic),不是"目标不可达",也不是"一条不等式收官"。** 负轨(有界不可行证书)对 front-exposure 类**基本死**;正轨(可行 witness)机制**验证成功但需要还没人造的 routing-aware 构造器**;而且 spike 订正了会议的一个 load-bearing 模型错误。

## 1. 重大模型订正(三路独立坐实,无 fatal 驳倒)

**会议(及此前给 owner 的)"输出侧精确饱和 52/52 是强 lead"= 模型不完整。** certified routing 谓词要连通的是**整条基地内部制造配方流 + 原料 sourcing**,不只是对外的 52 输出+2 无线。
- **真实 belt 路由端口 = 620**(310 in + 310 out;out = 258 配方输出 + 52 generic 输出),17 个商品。52 只占 **8.4%**、且只在边界。其余 568 在基地内部、front 自由性随布局变。
- 三路独立推导一致:opus 硬编码 620;codex 从 `OPERATION_PORT_PROFILES` 按 `_rate_to_slots`(rate=qty/ticks,slots=ceil(rate/belt_cap),operation_profiles.py:65-74)逐设施求和得 620/17 并 assert;T-正 对真实 witness b0_4r 跑 binding solve 独立吐 620/310/310/17。分子可信。
- footprint=3544、free=1356(layout 不变量,4 路核实)。
- 出处:port_specs 由 `binding_subproblem.extract_port_specs()`(:1360-1426)三路合并生成,只有 2 个终品(qiaoyu_capsule/valley_battery)走 `omni_wireless` 无线、连其生产者输出口也从路由剔除(routing_free_sink,:524-528/:1374-1378)。

## 2. T-负(binding+layout 不变的有界不可行证书):基本死

**结论:front-exposure 类拿不出 binding+layout 不变的干净 Hall/min-cut 不等式。** 认识论正确的标签是 **undetermined**(codex 版),不是 claude 版的 `no_obstruction`(对抗验证判其**过强**——把"计数证不出障碍"偷换成"障碍不存在")。
- 模型**允许 connector/front 共享**(routing_subproblem.py:135-148/:359/:445-449 核实:每端口 1 connector[body 外邻、移出可路由集] + 1 distinct front,二者强制不相交),所以没有"强制下界 > 预算"的可证地板 → obstruction 计数上**不可证**。
- 但**预算真紧**:connector+front 最坏需 2×620=1240 格,vs 扣 ghost/电线杆后预算 ~1202-1339 → 最坏差 **-38**,只靠"假设可达的共享"(~0.45 connector 共享 + 生产者→消费者 front 塌缩 + 双层路由)救回。**这精确解释了 batch-C 的经验脆性/枚举震荡**(routing_precheck_rejections≈1499、routing_attempts=0):大多数布局/绑定挤不下 connector+front,不是因为存在全称障碍。
- 对抗验证纠错:claude 的 H3 边界打包("46 互异 off-body front、0 碰撞、余量 ~300 格")**技术错**——(2,1) 处 front 撞 connector;codex 穷举 47 种合法打包证实**边界子族近乎刚性**:凡 46 互异 front 必 ≥1 front-connector 重叠(front_blocked),唯一 precheck-feasible 打包只有 45 互异 front(两端口共享)。即会议的"边界 L 周长 Hall"假说被证伪、但方向(边界极紧)是对的。
- **未碰的口子**:连通性 min-cut(relaxed_disconnected)类超出计数范围、形式上 undetermined(会议 D3 判其 LP 松弛分数可行、干净 min-cut 也不太可能);belt-**路径**格(连 310↔310)未计入,是额外需求。

## 3. T-正(construct-then-verify 可行 witness):机制成功,witness 本轮失败

- **管线验证成功(重要正信号)**:construct-verify 对单份固定布局 = 一次 binding solve(OPTIMAL@0.033s)+ 一次多项式 precheck,**loop-free、便宜、可重算验证**(不碰 master、不上 32G full router)。插桩确认真跑(17157 vars、582 现场算出,非照抄)。会议 §4 "把提→拒→重提循环塌成验一个候选"在代码接口上坐实成立。
- **但拿 packing witness 直接验必死**:复用仓库唯一现成完整 6×6 witness `b0_4r_free_c1_w6.json.solution.json`(C1 按 packing+供电优化、路由无感知),谓词 4 binding OPTIMAL,谓词 5 precheck = **front_blocked 582/620(94% front 埋进 body)**;该布局上 routing-aware 过滤剪 16987/16992 pattern、216/266 设施绑定域空 → binding-不变(layout-fatal)。**但这只证"packing/供电 witness 直接验路由必死",不证 6×6 不可行**(设施贴死没留走线廊道)。
- **缺口**:需要一个 **routing-aware 布局构造器**(266 设施+ghost 摆出 belt 廊道使 front 暴露 + 17 商品连通),仓库没有、本质是求解器要干的硬活。codex 那席 T-正 被中断、无实质产出。

## 4. 对"第一个 CERTIFIED 可达性"的诚实判读

- **下界(证 6×7 feasible)= 造一个 routing-aware witness**:难,但定义清楚、有便宜的 recompute 验证器(terminal fixed-witness verifier,pr2_l0_fixed_witness_core.py:183)。是"找一份好布局"的构造/搜索题,不是死循环、不是 32G solve。
- **上界(证更大的都 infeasible = 最优性)**:没有便宜的 front-exposure 证书。**但 spike 挖出一条新线索**:connector+front+路径的**面积驱动计数界会随 ghost 变大而收紧**——存在某个 ghost 面积阈值,超过它连最优共享打包都挤不下 = 一条 layout-不变的**上界**证书(H2/H5 harness 已是雏形,需推到"哪个 ghost 面积下最优打包也 FAIL")。若阈值接近 A*,上界就有救。
- **残余风险(怀疑席锚点仍成立)**:下界 witness 与上界阈值之间若有 gap,那段仍无 certified 手段;且"routing-aware 构造器"本身难度未知。但已从"死循环/不可达"收窄成两个定义清楚、有便宜验证器的子问题。

## 5. 下一步(排期建议)

1. **上界线索(纯计数、最便宜)**:把 T-负 的 connector+front+路径计数界推成"ghost 面积阈值函数"——最优共享打包下,ghost 面积 ≥ X ⟹ 挤不下 ⟹ INFEASIBLE。量 X 离 A*(~42)多远。zero-sealed。
2. **下界(routing-aware 构造器可行性)**:评估能否用启发式/局部搜索在 ~1300 自由格里为 6×6/6×7 摆出带 belt 廊道、17 商品连通的布局(construct-verify 管线已验证可用)。
3. 两者夹逼:上界阈值 vs 下界 witness,收窄残余。若上界阈值远大于最大 witness → 残余大 → 上交 owner 战略决策。

## 6. 质量与诚实边界

双模型独立算(claude+codex)+ 4 席对抗验证(claude/codex 混),无 fatal 驳倒;对抗验证抓出 claude no_obstruction 过强(改判 undetermined)、H3 边界打包技术错(codex 穷举纠正)、blocker 分类误标(548 碰 body 而非 582,总数 582 不变)、电线杆 28 桩是估计(唯一可证下界 2 桩)。全程 zero-sealed 只读、未跑 master/main.py。结论是研究判读、非 certified 结果。
