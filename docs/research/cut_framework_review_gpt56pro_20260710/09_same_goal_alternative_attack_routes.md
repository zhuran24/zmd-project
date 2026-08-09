# 09 — 同目标替代进攻路线盘点(cut 反馈力若全火力仍不足时)

> **定位(先读)**:owner 2026-07-13 口径——本项目目标(70×70+266 mandatory 全局
> `max_lex(area, min_side)` certified-exact)**不设降级退路**;L11 命题降级=另开新线
> 候选、非本目标 Plan B(roadmap 台账 #2 已订正,memory 卡
> `zmd-goal-no-degradation-fallback`)。本文回答的问题是:**若 cut framework 全火力
> 实测后反馈力仍不足,同一个目标还有哪些没打过的进攻路线**。
> **启用条件**:F2/F4 接线+F5 转正+F3 硬门解决+binding 提速全部落地实测后,组织性
> cut 反馈仍不能推动 Benders 收敛——在那之前本文只是储备,不是排期。
> **纪律**:每条路线投入前必过 Phase 0 cheap gate(03 号 §4.5 教训:L15 三小时 PoC
> 抓「攻错层」,L25 十轮 cheap gate 抓「core 全 trivial」);本文的 spike 草案即为此设计。
> 作者:Fable 5(数学面),2026-07-13 凌晨;基于 03 号范式墓地+现工作树状态推演,
> **非已登记路线**,立项需 owner 拍板。

## §0 前置认知:为什么「还有活路」不是安慰话

27 lever 墓地的死亡结论,按项目归因纪律(「死亡结论绑完整条款上下文」,memory 卡
experiment-single-variable-discipline)全部绑定在**旧 pose-bool master** 的条款环境。
C1(批 1,2026-07-09 破供电墙、07-10 转正 certified 默认)已经替换了这个环境——
**这意味着 Root cause 1(master 表达力墙)的既有死刑对 C1 世界不自动生效**,需要
逐条重审而非默认沿用。本文五条路线中,前两条直接吃这个红利。

同时三条**假退路维持禁提**(墓碑完整、不受 C1 影响):
- master 整体重写(6 路径同墙,Root cause 1 的「重写」侧不因 C1 复活——C1 本身
  就是那条线的幸存者,不支持「再来一次全量重写」);
- solver 替换(HiGHS 实测 42G>CP-SAT 30G;L23 路径穷尽 hard verdict);
- 跨 instance lifting(对称性被 cell-front/ghost/边界/端口方向打碎,LIC m1=2、
  orbit 全 trivial;PROJECT_LOCK §3A 明令)。

## §1 路线一:旧 cut 死刑的 C1 环境重审

- **主张**:Path 12(RAB-SEP)/Path 13(SAC-Hull)/B1 lazy demand 等「cut 表达力被
  master 卡死」类死刑,死因的一半在 master 听不懂(旧 pose-bool 无端口/覆盖语义)。
  C1 master 带 pose-bool+cov 通道,能锚定的语义面显著变宽——同款 cut 形式在 C1
  basis 下的反馈力需要重测,不能沿用旧判决。
- **与墓地关系**:不推翻墓碑,只主张「换了被告」。F2/F4 接线实测(批C 后续)本质
  上就是重审第一庭——此路线的一半已在主线排程内。
- **cheap gate spike**:取历史 cuts_6x6.json 的 5 次 binding-INFEASIBLE 场景(旧表示
  下的真实拒绝),在 C1 harness 里重放对应 cut 的 lowered 形式,量 master 重解的
  branch/conflict 缩减率。缩减率≥一个数量级=重审有戏;≈1=旧死刑维持。
  规模:单机数小时,zero sealed 面。
- **风险**:C1 的 cov 通道只覆盖 power 语义,port 语义仍在 master 外——重审可能
  得出「部分死刑维持」的中间结果,需按 family 拆分判决。

## §2 路线二:binding 部分上收(C1 手法推广)

- **主张**:C1 破供电墙的手法=挑子问题里最易违反的知识、选紧凑编码收进 master。
  binding 的对应物:把 boundary port 饱和/端口方向冲突等**高频拒绝结构的子集**
  编进 master(例如按 03 号 Root cause 2 的 138-cell perimeter trap 做专用容量通道),
  其余仍留子问题。介于「纯 cut 反馈」与「全量上收」(augmented master,224 万约束
  32G 死)之间的连续谱,墓地里没有中间地带的尸体。
- **cheap gate spike**:统计历史+批C 实测中 binding 拒绝的结构分布(哪类冲突占大头);
  对 top-1 结构做最小编码原型(exploratory 侧 harness,直建),量 master build 内存
  增量与 solve wall 变化。内存增量>5G 或 wall 恶化>30%=此结构不宜上收,换下一个。
- **风险**:每上收一类结构=master 语义面扩大=proof 义务扩大(S4/witness 类防御
  断言与 15 条 obligation 的连锁),工程成本高;必须一次一类、带完整 reseal 预算。

## §3 路线三:Farkas/对偶证书驱动的 cut

- **主张**:现役 cut 是组合式(nogood/capacity/Hall),反馈力受构造形式限制。给
  binding/routing 子问题建 LP 松弛,从 INFEASIBLE 的 Farkas 对偶射线**推导**线性
  不等式 cut——一条覆盖一个连续族,反馈力量级高于逐点 nogood。05 号 F1 Farkas
  自动触发是同方向的既有口子(当时结论:先定义证书/独立 verifier/replay 义务)。
- **与证明链关系**:Farkas 证书天然 proof-carrying(对偶乘子即证书),与独立复验
  (I1 形态)和证书侧(P3.0c VeriPB)同构衔接——不引入「不可复验的 cut 来源」。
- **cheap gate spike**:对 binding 子问题的一个真实 INFEASIBLE 实例手工建 LP 松弛
  (GLOP,flow_subproblem 已有基建可借形),验证:①LP 也 INFEASIBLE(松弛不掉底)
  ②Farkas 射线导出的不等式在 C1 变量上可表达 ③该不等式确实割掉原拒绝点的一个
  邻域。三关任一失败=此路线对该子问题形态不可用。
- **风险**:LP 松弛可能太松(整数结构丢失后 FEASIBLE),Farkas 无从谈起——这是
  第①关先验的原因;以及 lowering 的 soundness 证明义务全新,TCB 面扩大。

## §4 路线四:夹逼证明结构(绕开 Benders 收敛)

- **主张**:命题 `max_lex(area, min_side)=(A*,s*)` 的证明不必依赖迭代收敛:
  **上界侧**用 F 族数学(Hall/鸽笼/割集)做全局组合论证「任何可行布局的 ghost
  面积 ≤A*」;**下界侧**出示 area=A* 的可行解见证(已有 OPTIMAL 解即候选)。
  两侧夹逼,全局最优闭合,Benders 收敛性整个退出命题。当年上界论证不紧;
  F1/F6 一年的族数学积累+证书侧(2b 线)可机器验证的证明载体是新变量。
- **cheap gate spike**:对 7×6(比当前最优大一档的 ghost)手工构造组合上界论证——
  用 F1 region capacity+F6 Hall 的全局版推「266 实例塞不进剩余区域」。能写出人类
  可检的证明=路线活;写不出(论证依赖枚举深度)=退化回逐点 INFEASIBLE 证明,
  与现 frontier 无异,路线死。
- **风险**:组合上界的紧度天花板未知——可能证得出 8×8 不行但证不出 7×6 不行
  (差一档就没用);且这类证明的 checker 化(进 close-kernel)是全新证明面。

## §5 路线五:frontier 点级并行(工程活口)

- **主张**:Root cause 4 排除的是**单 solve 内部**的分布式(WAN ≥100ms 杀传播);
  outer_search frontier 的候选 ghost 点是数千个**互相独立**的 INFEASIBLE 证明任务,
  点间零通信——纯任务级并行,租 N 台云机撒出去,全局扫完 wall 除以 N。墓地无此
  路线的尸体。
- **前置**:certified 链的跨机器工件纪律(frozen artifacts 分发+seal 材料回传+
  supervisor 单点 mint 不变——多机只产 proposal 材料,seal 仍单机 owner 侧);
  成本模型(每点 1-2h×单价)与 owner 预算拍板。
- **cheap gate spike**:两台机器(本机+Windows 侧即可)各跑 frontier 不相交子集,
  验证 proposal 材料合并进单一 campaign 的 currentness/hash 链是否天然成立,或需要
  多 producer 协议(那是新工程面,成本另计)。
- **风险**:不解决单点慢(binding 枚举仍是每点的税);若单点 >2h,N 台的经济性
  要认真算。

## §6 优先级建议(非排期)

若启用条件成立,建议的 spike 顺序:**§1(重审,最便宜且一半已在主线)→ §3
(Farkas,与 F1 既有口子协同)→ §2(部分上收,工程重)→ §4(夹逼,回报最大
不确定性也最大)→ §5(工程扩容,随时可并行于上述任一)**。全部 spike 均
exploratory/harness 侧,zero sealed 面,单条预算 ≤1 天。
