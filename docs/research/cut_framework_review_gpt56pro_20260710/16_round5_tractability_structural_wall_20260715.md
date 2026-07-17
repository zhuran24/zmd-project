# 16 — round-5(2026-07-15):sound 的 UBC 紧凑 master 在真锚点上撞结构性终止墙,solver-tractability 工程用尽

> 承 doc 15。工作流 `wf_4bdd7cb5-8df`(2 Attack[claude+codex 诊断+加合法割/对称/分解] + 2 Verify[faithful claude / numbers codex]),zero-sealed 只读。harness 在 `scratchpad/spike_round6/`、`spike_round7_verify/`。

## 0. 一句话结论
round-4 证明 UBC 上界证书 **sound + 紧凑**;round-5 双模型 + 两席对抗一致证明:**拿这张证书撞的是结构性墙,不是时间/调参**——CP-SAT 对这个 sound 紧凑 master 在真锚点(7×7/6×8/8×6)上既证不出 INFEASIBLE(无廉价证书 + 无 LP bound)也证不出 FEASIBLE(对称装箱太大)。**solver-tractability 这条自己能做的攻法到此用尽。剩下是 owner 级岔口。**

## 1. 双模型诊断:两堵独立的结构墙(不是时间不够)
**墙1 — 无廉价 INFEASIBLE 证书**:模型是纯 satisfaction(objective/best_bound=NA,root LP 实跑 723 iters **无 root contradiction**=root 松弛可行)。唯一天然"装不下"杠杆=面积,但彻底死:面积余量 1298 格(body 3553 + ghost 49 vs 4900);最强 sound 计数割(area-cut Σarea+4·pole+ghost≤4900 等价 Σpole≤324 而池仅 220 根=恒真;再叠 front 密度界 620/4=155 互异空格仍剩 >1100/418 余量)全部 vacuous。→ **若锚点真不可行,其不可行是纯几何/邻接现象,除穷举 266 设施对称几何搜索外无多项式证书。** 任何 sound 面积/密度冗余割都证不出。
**墙2 — 编码+对称炸搜索,且逼 solver 进"无 LP 单席"**:front_clear 用 620 条 per-witness NoOverlap2D × 487 body(303K rect refs)。→ ≥2 worker 起 LP 线性化 RSS 炸 18–20 GiB(self_rss_stop)→ 被迫 1 worker + linearization=0 = 无任何全局 bound 推理;即便 sound 严格序破对称仍残留 ~9722 个 size-2 轨道。合起来=无 bound + 巨型对称装箱,既穷举不完(证不可行)也撞不上解(证可行)。
**分支热点**:600s 跑 117K–368K 分支只 278–351 conflicts——几乎不学 nogood,是"枚举摆放"非"学习矛盾"。codex 另建 aggregated pose-occupancy 必要条件模型(181K vars/448K constraints)把分支速率抬 50–120×(1200s 跑 33.6M 分支)仍 UNKNOWN=更便宜编码也不收敛。

## 2. 试过的合法-sound 杠杆(全 zero-sealed 亲手实跑,无一产出 INFEASIBLE)
area-cut(sound,vacuous)/ 严格序破对称(sound,从 presolve 卡死变真搜索但不终止)/ ghost 位置分解(sound,钉 ghost 无用=难点 100% 在 front_clear)/ pole 松弛(合法超集,668K 分支 UNKNOWN)/ CP-SAT 参数(lin 0 vs 2、worker 1 vs 2/4、presolve/probing)/ boundary-fence+direction-uniqueness / cumulative 投影(负效果) / 全新 pose-occupancy 重构。诚实:红队自查抓到一版 pose-occupancy 把 ghost cell 当 front blocker=对 INFEASIBLE 过严,已弃为 performance-only、**从未产出 INFEASIBLE 假证书**(所有受影响 run raw_status=UNKNOWN/KILLED)。

## 3. 对抗验证结论
- verify:faithful(claude)=`refuted=False/none`:全 UNKNOWN、无 INFEASIBLE 铸出=**无假证书可攻**;诊断数字(面积 1298、area-cut vacuous)算术正确、正确留锚点未定而非假闭。
- verify:numbers(codex)=`refuted=True/moderate` 但**确认两席 still_unknown 基本可信**(refuted 针对假想的"已终止"论断,无人真声称);抓到小数值 nuance(area-cut 后 constraints 16,287→16,288;"LP 杠杆普遍为零"略过泛化——有个 root-only profile 跑了 723 LP iters 但**无 contradiction**,反而坐实墙1)。

## 4. 逼出的更根本问题 + owner 级岔口
- **关键歧义**:CP-SAT 分不清"不可行但无廉价证明"与"可行但 witness 太难找"。**⟹ 我们其实不知道 7×7 锚点到底可不可行。** 整个 UBC 上界路线假设它 INFEASIBLE,但这一点从未被独立确立;area-42 witness(下界)也从未构造出。目标在上下界两侧都未确认。
- **自己能做的攻法链已走完**:front 计数 Hall(R1 死)、连通 min-cut(R2 死)、UBC lift(R3-4 sound 但 R5 证不动)、solver-tractability(R5 结构性墙)。
- **剩下全是 owner 级**:①针对这批实例的具体几何/组合不可行引理(重数学,且诊断说无多项式证书=需全新结构论证,高不确定);②回到 binding↔routing 枚举墙正面解决(原始死循环硬核);③换算力/换求解技术(CP-SAT proof-log、SAT、基地分解、并行);④接受 exploratory 边界、不追 certified。

## 5. 质量与诚实边界
4 席 claude+codex 双模型 + 2 席对抗,0 fatal。全 zero-sealed 只读、未跑 master/main.py、未铸强状态。诊断数字全亲手实跑复算(build 10,719 vars、面积余量、root LP 723 iters 无 contradiction、对称 orbit、分支/conflict 比、多 worker RSS 18–20G)。结论是研究判读。**这是 owner 级战略决策的输入,不是又一轮我该自己往下打的技术活。**
