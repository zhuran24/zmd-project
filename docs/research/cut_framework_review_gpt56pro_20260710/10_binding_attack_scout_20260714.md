# 10 — binding 主攻 scout(2026-07-14,owner 授权提前 scout)

> 定位:owner 07-14「提前 scout binding 主攻」授权下的 Phase-0 cheap-gate scout(不等 B6/F5,zero sealed 面,只读为主)。基于 09 号五路线盘点 + 真实工作树/历史数据实测,给**数据落地的路线重排**。09 号的优先级(§1 最先)是纸面推演;本文用实测数据修正之。

## §1 真瓶颈 = 两个叠加问题(不是单一"binding 慢")

**问题 A — prod 规模 binding 不出结论**:`src/models/binding_subproblem.py:1273` `solve` 默认 30s 帽 + `search_branching=cp_model.FIXED_SEARCH`(1297)。批C F-5 实测:FIXED_SEARCH 下 CP-SAT `num_workers` 退化单 worker。266 设施规模,单 worker 定序搜索在时限内跑不完 → UNKNOWN(既非 FEASIBLE 也非 INFEASIBLE)→ 无 binding_infeasible 信号 → 无 cut 生成 → Benders 停滞(批C「组织性触发从未到手」的根因)。

**问题 B — 即便出结论,反馈是逐点 nogood(实测坐实)**:`data/solutions/cuts_6x6.json` 5 个历史 binding-INFEASIBLE cut(6×6 ghost、865 设施全量布局)**全是 `cut_type=micro`**——整层 nogood,`conflict_set` = 整份布局解(instance→pose_idx)。而且 5 个 cut **彼此几乎相同**:

| cut | 相对 cut[0] |
|---|---|
| cut[1] | 键集相同,**1/865** 绑定值不同 |
| cut[2] | 键集 ±1,864 绑定 |
| cut[3] | 键集相同,**2/865** 绑定值不同 |
| cut[4] | 键集 ±1,864 绑定 |

= 教科书式**逐点 nogood 死亡震荡**:master 提布局 → binding 拒 → micro-nogood 禁掉这整个 865 元组 → master 只翻 1-2 个绑定再提 → 再拒……组合空间里近乎相同的布局天文数字多,每次只消一个点,永不收敛。

**关键**:`conflict_set` 是**整层**(power_pole 599/boundary_port 46/crusher 34/…共 865,分布只反映布局构成、power_pole 最多),**micro-cut 完全不捕获"为什么被拒"的结构性冲突核**。这是问题 B 的病根:cut 机制扔掉了冲突原因,只留"禁掉整个"。

## §2 对 09 号五路线的数据落地重排

09 号优先级 §1→§3→§2→§4→§5 是纸面推演。用实测数据修正:

- **§1(旧 cut 死刑 C1 重审)——payoff 对 micro-cut 近零,降级**:§1 的 cheap gate 是"重放 cuts_6x6 的 binding-INFEASIBLE cut,量 C1 下 branch/conflict 缩减率"。但历史 cut **全是整层 micro-nogood**——一个整层 nogood 恰好消掉组合空间**一个点**,这个反馈力**与 master 表示无关**(C1 也好旧 pose-bool 也好,一个点就是一个点)。预期缩减率 ≈1 = §1 cheap gate 对这批数据大概率**失败**。§1 的真实价值只在**结构性 cut**(F2/F4)上,而那些不在历史数据里、要先造出来。→ §1 不该第一个投。

- **缺失前置 = 冲突核提取(IIS)**:§2(上收哪个结构)和 §3(对哪个 INFEASIBLE 建 LP)都要先知道**结构性冲突原因**,而现机制(micro-cut)把它扔了。所以**任何结构化路线的真前置 = 从一个 6×6 binding-INFEASIBLE 实例提取最小不可行子集(IIS)/冲突核**——回答"865 绑定里到底哪一小撮互相冲突"。09 号没识别出这个前置。

- **§3(Farkas)——数据支持,但需先过 LP 松弛关**:逐点震荡正是 Farkas 要治的(一条不等式覆盖一个连续族而非一个点)。但 §3 gate①=binding 子问题的 LP 松弛必须也 INFEASIBLE(整数结构不能松掉底)。端口绑定是离散选择,LP 松弛很可能 FEASIBLE → Farkas 无从谈起。**这一关是 §3 的生死关,且可在 6×6 小实例上只读验证**。

- **§2(部分上收)——数据支持方向,工程重**:文档假设"boundary port 饱和/方向冲突"是高频结构;需 IIS 坐实后才知道上收什么。

- **§4(夹逼)/§5(并行)**:§4 纯数学、绕开 Benders(最高 payoff),不依赖上述数据,可独立 attempt;§5 需多机,暂缓(且不解决单点慢)。

## §3 本 scout 的建议(数据落地)

**新的 spike 顺序建议**:
1. **冲突核/IIS 提取**(新前置,09 号漏了):对一个 6×6 binding-INFEASIBLE 实例(cuts_6x6 的 conflict_set 即布局输入)跑 binding 子问题,用 CP-SAT assumptions/`SufficientAssumptionsForInfeasibility` 或逐绑定 drop 提最小冲突核。产出="865 绑定里真正互斥的那一小撮"。**这是 §2/§3 共同前置,单机分钟级(6×6 小实例),zero sealed 面。**
2. **§3 Farkas gate①**(承 1):对该冲突核建 LP 松弛(GLOP,借 flow_subproblem 基建),验 LP 是否也 INFEASIBLE。INFEASIBLE=Farkas 有戏;FEASIBLE=端口离散结构松掉底、§3 对该形态死。
3. 视 1/2 结果:冲突核指向可紧凑编码的结构 → §2 最小上收原型;或 §4 纯数学夹逼独立并行 attempt。

**注意问题 A(prod 不出结论)与问题 B(反馈弱)要分开治**:即便 §2/§3 把反馈变强,prod 规模 binding 仍可能因 FIXED_SEARCH 单 worker 不出结论(F-5,提速须 reseal 批改 search 策略,soundness 敏感——cf76bed 撤销教训:search_branching 乱改可铸假 OPTIMAL)。两条都得走通,第一个 CERTIFIED 才到手。

## §4 spike-1 结果(冲突核/IIS 提取,2026-07-14 已执行,决定性)

从 `cuts_6x6.json` cut[0].conflict_set 忠实重建 binding 实例(865 = 266 mandatory ∩ 完美 + 599 power_pole;candidate_placements 与 cuts_6x6 同为 07-08 同期,pose_idx 对齐),**binding-only** 跑(不跑 master、无机器风险):

**结果 = 瞬间(0.0s、presolve)复现 INFEASIBLE**,且冲突核是**全局容量非对称缺口**,不是局部端口打包、也不是搜索超时:
- `empty_binding_domain_instances=[]`、`invalid_binding_input_reasons=[]`(非局部空域);
- **输出侧匹配**:`required_generic_outputs=52`(blue_iron_ore 34+source_ore 18)vs `generic_output_slot_count=52`——boundary_port 是 **mandatory 恒被放**,输出槽够;
- **输入侧缺口**:`required_generic_inputs=2`(qiaoyu_capsule 1+valley_battery 1)vs `generic_input_slot_count=0`——输入槽唯一提供者 protocol_storage_box(wireless_sink)是 **pose-optional,master 省了不放**;
- 机制:`_add_generic_input_requirements`(binding_subproblem.py:1145)对每个需求加 `sum(slot_vars)==required`,0 槽下 = `0==1` → presolve 立判 INFEASIBLE;
- **5 个被拒布局全部 0 个 protocol_storage_box**——震荡确实围着同一结构缺口:master 无 sink-provisioning 约束 → 反复提 sink-deficient 布局 → binding 秒拒 → micro-nogood 只禁整层不教 master 放 sink → 翻 1 绑定再提。

**根因定性**:非对称=**源设施 mandatory(恒供给)、汇设施 pose-optional(master 可省)**,而 master 目标是几何面积、无放 sink 的动机 → 系统性欠配。

## §5 结论:§2(部分上收)是明确赢家 + 分层结构

- **§2 具体化(cheap、高杠杆、soundness-safe)**:把一条紧凑约束上收进 master——「已放 wireless_sink 输入槽容量 ≥ required_generic_inputs(=2)」(必要时对称加输出侧,但输出侧已由 mandatory boundary_port 天然满足)。这是**必要条件**(任何可行布局都满足它)→ 加进 certified master **不割任何可行解 = soundness 中性**,一条约束消灭整个 sink-absence infeasible 类。比 §3(Farkas)/§4(夹逼)便宜得多、直击当前主导冲突。代价=master 语义面小幅扩(§2 风险:proof 义务连锁),但这条约束是简单容量下界、非最坏情形。
- **分层洞察(关键)**:此冲突 presolve 秒判、binding 并不慢——它是 Benders **早期**主导的**平凡** infeasible。批C 的「prod binding 从不出结论」(问题 A、FIXED_SEARCH 超时)是**这层平凡冲突被 §2 消除后、sink provisioned 之下才暴露的真·端口打包难题**。即 §2 是**到达真问题的必经第一步**:不上收 sink 容量,master 永远卡在平凡欠配震荡、根本走不到硬 binding。
- **09 号路线再校准**:§1(重审 micro-cut)确认无价值(冲突是平凡容量缺口,C1 表示无关);§2 升为首选(数据直指);§3/§4 留给 §2 之后暴露的真端口打包层。

## §6 状态

zero sealed 面、zero commit(纯只读 scout + binding-only 复现 + 本报告)。下一步候选 = §2 最小上收原型(exploratory master harness:加 sink 容量下界约束,量 build 内存增量 + 是否消除 sink-deficient 震荡 + 暴露的下一层冲突形态)——那是碰 master 的完整 spike(需 owner 定投)。
