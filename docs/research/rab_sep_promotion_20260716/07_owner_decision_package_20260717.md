# 07 — front-clear 上收批收官：owner 决策包（2026-07-17）

> 输入 = doc 06（阶梯 3-5 + 探针 2/3/4 + §4.7 round-4/5 互证）+ 过夜长跑
> `arm_on_overnight`（lift ON + presolve off + automatic，42G/40G 帽，无时限
> 24h 保险丝）。§1 待长跑终态回填；§2 起为决策菜单，不依赖终态方向。

## §1 过夜长跑终态（待回填）

## §2 已确立的事实（不随终态变化）

1. lift 语义正确性三面实证（哨兵 45 / 全池 286,636 pose / corpus 1,314 双向
   零 mismatch），OFF 路径零回归——**工程面无遗留**。
2. presolve off（`EXACT_MASTER_CP_MODEL_PRESOLVE=0`，已 allowlisted）=任何
   lift-ON 运行的必要操作配方（不开则 presolve 展开爆炸、solver 不搜索）。
3. 硬度证据（截至探针 4）：两套独立编码（本批 certified master + round-4/5
   研究原型）× 四个锚点（6×6/7×7/6×8/8×6）× fixed/automatic 两种 search，
   30 分钟单发全部无 incumbent 无 INFEASIBLE。
4. 迭代 cut 通道（RAB-SEP）工作正常但六轮无收敛迹象——皮带可用，不是证明
   引擎。

## §3 决策菜单（按投入从低到高；可并行项已标注）

| # | 牌 | 内容 | 前置/成本 | 赌注 |
|---|---|---|---|---|
| A | **witness 构造器**（下界侧，可并行，不受 solver 墙影响） | 构造 area-42 布局 + 多项式验证（construct-then-verify）；front-clear/demand SSOT 机械可直接当构造约束 | 研究脚本级，零 sealed | 拿下"3 负锚点+1 witness"里的 1；round-2 已把 front_blocked 582→138，方向通 |
| B | **两段式 master**（层数响应，判据 v2.1 直接产物） | 便宜松弛格（front-clear 计数+不重叠+面积）先解，解作 hint 喂完整 master | runner 级改造+一发单发验证 | ON 臂困境若是"单格合并过头"，此牌直接救 |
| C | **双线合流**（B6 flip 后） | F1/F6/F7 结构规则库对 lift 后 master 开火（区域容量/Hall/hitting set = 现成的健全必要条件库） | **B6 owner 手动门** + PIC-4/5 证据口径表态（台账 #9） | 工程线两个月的库第一次服务研究线主攻 |
| D | **证明日志求解器侦察** | lift 后模型仅 1-3 万变量，PB/SAT+VeriPB/DRAT 首次可行；与支线轴 B 同一笔投资 | 纸面评估+小实例试编码 | 负锚点 INFEASIBLE 出机器可查证书（比 CP-SAT 口头 UNKNOWN/INFEASIBLE 更硬） |
| E | **云算力** | portfolio×多 worker 需 128G+ 内存，本机装不下 | 租用决策+环境搬迁 | 把"可接受时间"扩一档 |
| F | **兜底姿态**（非降级） | witness 到手后最优解夹在 [42, 上界] 区间，3 负锚点=开放内核，RAB-SEP 皮带照转 | 无 | 阶段性可发布数学状态，目标不让寸 |

## §4 owner-only 决策项

- lift 默认值：维持 OFF（无翻转理由，按纪律确认现状）——台账 #10。
- 调参演习 go/no-go 与牌序拍板——台账 #11。
- 牌 C 的 B6 flip 与 PIC-4/5 证据口径——台账 #9。

## §5 执行建议（我的推荐，可否决）

A 与 B 并行开工（A 已于 07-17 凌晨离线时段起步，见
`witness_constructor_20260717/`）；D 做半日纸面侦察；C 等 owner 门；
E 视 B/C 结果再花钱；F 是 A 成功后的自然中间态。

## §6 牌 A 夜班中期战报（07-17 晨，详见 witness_constructor_20260717/01）

1. **几何三本账建立**（口格悬空于 body 外、整行带式布局被算术判死
   5,400>4,900、front-only 点状口径 ~4,100 装得下但余量踩着 3% 密铺）。
2. 贪心系五代构造器天花板 ~241/266（front-clear 审计全程 0 违规——
   构造语义与 binding 机械已证一致）；CP-SAT 装箱小模型（NoOverlap2D
   ~760 矩形）可行性形态三连 UNKNOWN（120s/300s+对称破除/600s+四朝向
   +241 件 warm hint）。
3. **中期判读——这个"难"本身是新证据**：witness 的纯装箱松弛（不带
   供电/binding/routing）已经塞不动 CP-SAT 十分钟级预算 ⇒ ①lift 后
   master 30 分钟干涸完全合理（它解严格更难的问题）；②area-42 witness
   的存在性不宜再当默认假设——**若装箱侧持续拿不下，负锚点侧
   （6×6 INFEASIBLE 上界证书）的相对价值上升**，过夜跑的赌注变大不变小；
   ③牌 D（证明日志求解器）动机增强。
4. 注意本模型的 UNKNOWN/将来若 UNSAT ≠ 原问题不可行：固定须点不共享是
   过约束（真松弛需允许 front 共格），且 CP-SAT 无证明日志——只作研究
   信号，不作数学结论。
