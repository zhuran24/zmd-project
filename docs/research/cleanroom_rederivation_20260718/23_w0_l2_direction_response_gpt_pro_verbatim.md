# 结论先行

我的裁决是 **Q1(c)：当前 A/B 二分并不是主要矛盾，应先修复 G1 与 G2 之间的语义接口，再做判定**【强论据】。主观置信度约 **82%**【猜测】。

当前存在两种相反偏差：

1. main/evaluator 口径偏松。它允许多个彼此断开的、各自含有 live stub 的自由空间分量同时通过检查，但 master 随后又丢掉了这些分量的划分信息。因此，“局部 pattern 被接纳”不能推出“全局可拼成一张网络”【强论据】。
2. strict 口径偏紧。它要求每个 region 内所有相关单元先成为一个分量，但全局网络本来可能在邻区绕行后把多个局部分量接起来。因此 strict 的显著面积下降也不能单独证明当前 region 限制必然过紧【已证明，图论意义下】。

在强制采用“每区单分量”这一额外充分条件后，我会暂时把 **B 排在 A 前，约 70% 对 30%**【猜测】；但材料中没有闭合的上界证书，所以不能把它写成“不可能”。

---

## 先校准四项证据口径

**第一，任务书与包内材料存在版本错配**【强论据】。`00_ASK.md` 说 strict 对照臂尚未收官、终值不在包内；但 `01_problem_statement.md §3.5`、`09_probe/results/result_*_strict.json` 以及对应 pattern 文件已经包含 strict 终值和坐标。后文以各个原始 `result_*.json` 为准，不采用聚合文件的旧状态。

strict 原始映射为：

* `BOTTOM_I1=118`
* `BOTTOM_I2=110`
* `BOTTOM_I3=117`
* `BOTTOM_I4=117`
* `LEFT_J1=117`
* `LEFT_J2=116`
* `LEFT_J3=110`
* `CLEAN=120`
* `CORNER=109`

七个边界 family 合计为 805；无洞总和为

[
16\times120+805+109=2834.
]

这是包内搜索找到的最好值，不是这些 family 的数学上界【强论据】。`01_problem_statement.md §3.5` 中边界数字的多重集合和总和正确，但按表格顺序理解时，family 对应关系不正确。

**第二，`09_probe/results/probe_results.json` 是中间态聚合文件**【强论据】。它只保留了部分 CLEAN/CORNER 状态和旧 hole-cost 假设。应使用各 `result_*.json`，不能用其中的 closure 字段做最终判断。

**第三，R-PAT-CONN 的文档语义与 evaluator 实现不一致**【强论据】。`01_problem_statement.md §2` 和 `03_charter.md §6` 要求 active fronts、live stubs、reserved fronts、hole 处于同一个四连通自由分量。可是在 `04_sources/g1_pattern_evaluator.py` 的 `portal_component(free, seeds)` 中，BFS 同时从所有 live stubs 初始化；`seen` 因而是多个 stub-bearing 分量的并集。后续检查只保证每个 anchor 落在“某个含 stub 的分量”，没有保证所有 stub 和 anchor 在同一分量。

包内审计记录显示，main 接纳的 2593 个 pattern 中有 855 个存在多个 stub-bearing 分量【强论据】。main 的高面积列因此不能直接作为 G2 可拼装证据。

**第四，CLEAN-with-hole 的 142 上界不成立**【已证明】。`g1_pattern_generator.py::enumerate_hole_poses` 允许 hole 与 reserved cells 重叠；strict objective 也只禁止 facility body 落入 hole，transport/front cell 可以在 hole 内。设 CLEAN 的 8 个 reserved stubs 为 (R)，洞为 (H)，一根 2×2 pole 占 4 格，则

[
|body|
\le 196-|R\cup H|-4
=196-(8+42-|R\cap H|)-4
=142+|R\cap H|.
]

按给定的 6×7、7×6 洞形与 CLEAN stub 坐标，最多可覆盖两个 stubs，所以

[
|body|\le144,
]

而不是 142。例子是 7×6 洞从 `(0,2)` 起放时覆盖 west edge 的两个 stub；包内 `(7,0)` 的洞样例也实际覆盖了一个 stub。

因此 `01_problem_statement.md §3.3` 中把 `usable` 已扣除的 reserved cells 再随 42 格洞完整扣一次，属于重复计数。边界洞分支的 `171−123−42−4=2` 也不能作为矛盾证书，除非先证明该 family 的洞与 reserved mask 完全不相交【已证明】。

---

# Q1：选择 C，以及最短的真判定路线

## 为什么不是 A 或 B

main 口径的已找到无洞总面积为

[
16\times138+7\times126+110=3200.
]

strict 口径则为 2834。两者相差 366 格，但这不是“生成器质量”的纯差值，其中混入了不同的连通语义【强论据】。

同时：

* main 的 138/126/110 是弱 evaluator 下找到的可行 witness，不是上界；
* strict 的 120/110～118/109 也是找到值，不是上界；
* relaxed packing ceilings 的 3392 是忽略关键连通与精确类别耦合的上界，仍高于 3325；
* 修正 CLEAN 洞重叠后，若洞在 CLEAN，纯 packing 上界最多只从 3392 降到 3390，仍不足以闭合；
* CORNER-hole 的 85 若确为该局部 packing 模型的精确值，则全局 relaxed 上界仍为
  [
  16\times146+7\times134+85=3359>3325.
  ]

所以材料既没有给出 B 所需的 `<3325` 上界，也没有给出 A 所需的完整可扩展构造【强论据】。

## 最短路线：类指派列生成，而不是继续堆固定 catalog

建议把当前固定 catalog master 改成一个小型 branch-and-price / column-generation 框架【强论据】。

每个局部列 (p) 不再只有“bucket 计数 + hole bool”，而应至少包含：

* 精确 class 指派计数 (n_{pc})；
* body、pole、hole 的局部几何 witness；
* active mode 和 active fronts；
* live stubs 与 active fronts 的自由分量划分 (\Pi_p)；
* 各共享 front cell 的可用 component-state；
* 若要直接面向 G2，再包含 portal 的方向状态。

先建立一个故意放松全局 G2 的 LP master：

[
\max U=\sum_{t,p,c} A_c n_{tpc}z_{tp}
]

约束为

[
\sum_p z_{tp}=1\quad\forall t,
]

[
\sum_{t,p}n_{tpc}z_{tp}\le d_c\quad\forall c,
]

[
\sum_{t,p}h_{tp}z_{tp}=1,
]

[
z_{tp}\ge0.
]

这里 (A_c) 是 class (c) 的 body area，(d_c) 是需求量。任何满足当前限制的完整 219-body 布局都映射为该 LP 的一个整数可行解，目标恰为 3325。因此：

> 若对所有 region family 的 pricing 都有“最大约化成本上界 (\le0)”的证书，且 master LP 最优值 (U<3325)，则当前限制下无解【已证明】。

这条证明甚至可以暂时省略全局路由约束，因为省略约束只会把上界抬高，不会制造错误的“不可能”。

若初始 LP 仍高于 3325，再加入 topology-aware 列信息。每列发布 portal/front 的分量划分，master 通过 seam matching 和 cut constraints 拼接分量。这样既不要求每区预先单分量，也不把多个分量无条件当成已经相连。

若 LP ≥3325，则仍不能判 A；下一步需要整数 master 或 branch-and-price 给出精确列组合，再通过 G2-safe expander 生成完整 witness【已证明】。

这条路线比继续增加 `MAX_VALID_PATTERNS_PER_TARGET` 更短，因为当前瓶颈不是“列太少”本身，而是列的接口丢失了决定可拼性的状态。

---

# Q2：建议的 CP-SAT 连通模型

即便继续走 A 侧、修生成器，也不应只在 evaluator 后置过滤。应把连通、mode/front 和共享 front component-state 放进同一个局部 CP-SAT 模型，并让 generator、packing/pricing、最终 checker 共用这套模型构造【强论据】。

## 变量族

在 14×14 region 中，记 (N=196)。

**几何与类别**

* (x_j)：body pose (j) 被选择。
* (u_{j,c,m})：pose (j) 作为 class (c)、mode (m) 被选择。
* 约束
  [
  \sum_{c,m}u_{j,c,m}=x_j.
  ]
* (g_a)：2×2 pole anchor (a) 被选择，最多 169 个候选。
* (h_r)：6×7 或 7×6 hole pose (r) 被选择，未加 mask 前最多 (72+72=144) 个。
* (o_v)：格点 (v) 被任一 facility body 或 pole 占据。

body pose 的规模可按

[
\sum_s(14-w_s+1)(14-h_s+1)|D_s||L_s|
]

计算。以当前三类尺寸为例：

* 3×3：(12^2\times4\times3=1728)；
* 5×5：(10^2\times4\times2=800)；
* 6×4/4×6：
  [
  2\times9\times11\times |D_{6\times4}|\times3.
  ]

若矩形只允许两类 front side，则该项为 1188；若四边都枚举，则为 2376。总 pose 量级约 3700 至 4900，family mask 和目标 level 会进一步减少。

**active fronts**

* (a_{j,c,m,f,k})：所选 body 在 cell (f) 激活类型为 (k) 的 terminal，其中 (k\in{\text{facility-output},\text{facility-input}})。
* 每个 class/mode 的输入、输出数量必须精确等于 frozen contract。
* active front 必须在板内且不被 facility body/pole 占据：
  [
  a_{\cdots f k}\le 1-o_f.
  ]
* 不应增加“每个 front cell 容量为 1”的约束，因为合法 splitter/merger/cross 可能服务多个 terminal。

**自由连通**

* (q_v)：cell (v) 被选入连接所需 terminals、hole 与 portals 的自由连通子图。
* [
  q_v+o_v\le1.
  ]
* 每个 live stub、selected active front、selected hole cell 都强制 (q_v=1)。
* 其他自由格可以作为可选 connector。

选择一个 canonical live stub 作为根 (r)。对每条有向邻接边 (u\to v) 建立 parent 变量 (y_{uv})，14×14 网格最多有 728 条有向邻接边。再设深度 (d_v\in[0,195])：

[
\sum_{u\in N(v)}y_{uv}=q_v\quad(v\ne r),
]

[
y_{uv}\le q_u,\qquad y_{uv}\le q_v,
]

[
y_{uv}=1\Rightarrow d_v=d_u+1.
]

根没有 parent。这样，每个被选中的 (q_v) 都沿 parent 铘追溯到根，正好刻画“所有 required cells 位于一个自由连通分量”【已证明】。

相比大容量单商品流，这个模型不依赖 196 倍流量的松弛。它是否在 OR-Tools CP-SAT 上给出更快的 best bound 仍是经验问题【猜测】，但整数语义是精确的。

## 共享 front 的 component-state

对每个自由 cell (f)，不要只记录“被几个 body 使用”，而应选择一个允许的 component state：

[
\sigma_f\in\Sigma,
]

其中 (\Sigma) 枚举 straight、turn、cross、splitter、merger 的输入/输出方向集合。每个方向只出现一次，并符合 strict contract 的方向唯一性。

实现上优先使用一个小域变量加 `AddAllowedAssignments`，而不是为每个 state 建一整排 one-hot。每个 cell 的四条边先编码为：

* 0：无连接；
* I：该方向必须是 component input；
* O：该方向必须是 component output。

facility output 的 outward direction 为 (d) 时，在 access cell 上要求 `opposite(d)` 为 component input；facility input 则要求 component output。

这种表约束同时解决 mode/front 选择和多 body 共用 front cell 的合法性。

## 与 generator/master 的接缝

建议在 `g1_pattern_generator.py::_solve_target()` 中，在已有 pose/occupancy 约束之后、目标函数之前插入上述模块。`measure_packing_ceiling` 和新的 pricing oracle 也应调用同一个 `_build_local_model()`，避免“生成器一套语义、evaluator 另一套语义”。

每个输出列必须附带可机器复核的证书：

* exact class/mode；
* active front cells；
* 每个 front cell 的 component-state；
* portal/front/hole 的分量 partition；
* pole anchors。

`g1_exact_cover_master.py` 不能再只按 `(bucket counts, hole)` 去重。该签名对纯 class 可服务性可能足够，但对 G2 拓扑与方向不封闭【强论据】。

## 仅有自由空间连通，仍不足以保证 G2

一个所有 terminal 都在同一无向自由分量的 pattern，仍可能无法形成强连通有向网络【已证明】。最简单的反例是两个子区域之间只有一条 width-1 bridge。跨越该 cut 只有一条物理邻接，方向唯一；它不能同时承担两个相反方向的通道，因此不能把两侧都放入同一个 SCC。

要让局部列真正 G2-safe，可再加入：

* (b_v)：SCC backbone cell；
* component-state 推导出的有向 arc (e_{uv})；
* 以同一根 (r) 为根的一棵 out-arborescence；
* 在反向图上的一棵 in-arborescence。

若每个 backbone cell 从 (r) 可达且能到达 (r)，则 backbone 强连通【已证明】。component-state 约束还会阻止同一物理 channel 被两个相反方向重复占用。

然后要求：

* 每个 manufacturing output 有有向路径进入 backbone；
* 每个最终 input 可由 backbone 有向到达。

这足以保证任一 output 可达任一 final input。terminal spur 可以是单向 width-1；但 SCC backbone 本身不能依赖单向桥。

## CEGAR 应加 separator cut，不应只禁整张 pattern

发现一个包含 required cell 但不含根的自由分量 (S) 时，加入条件式 cut：

[
\text{required}(S)
\Rightarrow
\sum_{v\in\delta(S)}(1-o_v)\ge1.
]

也就是至少打开一个当前 separator cell。若 required 身份由某些 mode/front/hole literal 决定，应把这些 literal 放进 antecedent。

方向检查失败时，对 route checker 找到的非根 SCC (S) 分别加入：

[
\sum_{e\in\delta^+(S)}e\ge1,\qquad
\sum_{e\in\delta^-(S)}e\ge1.
]

这类 cut 能排除整族同源失败布局；只加“当前完整 pattern 不得再次出现”的 no-good，通常会反复撞上相同 separator【强论据】。

---

# Q3：放松候选排序

以下是按“预期可回收 body area ÷ 新增 master 复杂度”的排序【猜测】。没有做新求解，所以数值收益不作伪精确承诺。

| 排名 | 改动                                     | 判断                                                                                                                                                                        |
| -- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | **新增候选 6：只解除 CORE 未激活 fronts 的预留**     | 最优先。当前固定 core 有 14 个候选 input fronts、6 个物理 output fronts，但 strict 只需激活 2 个 input 和全部 6 个 output。释放其余 12 个候选 input fronts，不新增 seam 耦合；CORE 当前找到值为 0，因此单位复杂度潜力最高【强论据，收益量猜测】。 |
| 2  | 候选 2a：取消 board-edge 的纯外向 stubs         | 不涉及邻区匹配，master 几乎不变。文书估计约 30 个此类保留格属于纯消耗；释放格数不等于 body area 收益，但这是最低风险的 mask 松绑【强论据】。                                                                                      |
| 3  | 候选 4：允许跨 region 共享 pole                | 当前 24 个非空制造 region 各至少放一根 2×2 pole，局部限制制造了至少 (24\times4=96) 个 pole 占用格【已证明】。真实全局仍需若干 pole，所以 96 不是可回收 body area。建议用 Benders pole subproblem，而不是把所有跨边 pole 状态塞进列签名。        |
| 4  | 候选 3：允许 hole 跨 seam                    | 全局只有一个 hole，耦合范围至多一对相邻 region；可用 hole-domino 列表达。它可能显著降低观测到的 hole penalty，但无法仅凭 42 格洞推出收益【猜测】。                                                                            |
| 5  | 候选 1：定向 domino merge                   | 可以同时捕获共享 pole、可移动 corridor 和 seam 邻近 packing，但会破坏 CLEAN 的 16 重对称压缩。只应先做少数高 dual-price seam 类型，不宜一次生成全部 domino family【猜测】。                                                 |
| 6  | 候选 2b：内部 portal 完全自由、2→1 或 edge cancel | portal 位置自由需要 edge signature；2→1 还可能削弱 G2 双向通行。应晚于 topology-aware master，再按 dual 选择性放开【强论据】。                                                                              |
| 7  | 候选 5：active front 跨 seam               | 引入跨区 terminal 占格、方向、component-state 和 class/mode 联动，master 接口最重。除非前六项仍无法接近 3325，否则不应先做【猜测】。                                                                               |

候选 4 中，“删除 inclusion-minimal pole 要求”本身没有面积收益【已证明】。在 R-POWER-LOCAL 仍保留时，任何覆盖所有 body cells 的非最小 pole 集都可以逐根删除冗余 pole，直到 inclusion-minimal；body/front/hole 不会因此变差。因此真正有价值的是 **跨区共享覆盖**，不是取消 minimality。

## 收益的可靠测量方法

对每项 relaxation (R)，用同一套精确 class/topology 模型分别求基线和放松模型的下界、上界：

* 基线：(L_0\le V_0\le U_0)
* 放松：(L_R\le V_R\le U_R)

则真实 area recovery 满足

[
\max(0,L_R-U_0)
\le V_R-V_0
\le U_R-L_0.
]

这比比较两个 incumbent 值可靠。只有上下界闭合时，才能把收益写成精确数字【已证明】。

## 首选改造：CORE-v2

保留固定 core body 和当前 orientation，只改 front reservation：

1. 6 个 output fronts 永远 active、永远保持 free。
2. 从 14 个候选 input fronts 中精确选择 2 个，共有
   [
   \binom{14}{2}=91
   ]
   种位置组合。
3. 仅所选 8 个 active fronts 强制 free；其余 12 个候选 input cells 恢复为普通可占格。
4. CORE 局部 CP-SAT 同时选择这两个 input fronts、其他 bodies、poles、component-states 和连通 backbone。
5. CORE 列发布所选 fronts 及 portal partition；由于 fronts 仍在 CORE region 内，master 不增加 seam 变量。

这是一项对 frozen strict contract 更忠实、同时比 R-FRONT-IN-REGION 小得多的松绑【已证明】。

---

# Q4：三个十分钟内的判别实验

以下均是计算预算估算，不是本次运行结果。调度假设为 24 个逻辑核，每个 CP-SAT 子任务使用 1 worker，避免嵌套超卖。

## 实验 1：存量列的 simultaneous-front 重编译

固定每个现有 pattern 的 body/pole/hole 几何，只重新求：

* exact class assignment；
* mode；
* active fronts；
* 每个共享 front cell 的 component-state；
* 必要的局部 directed continuation。

随后用新 class-count signature 重跑 master。

对 main 的 2593 个 pattern，每个给 1 秒硬上限，24 路并行的纯 cap 估算为

[
\lceil2593/24\rceil\times1\text{s}\approx109\text{s}.
]

加解析和 master，预计仍可控制在 4 分钟左右【猜测】。

判读：

* 若高面积列和 class supply 基本不变，则 Q5 不是主要损失，A 略获支持【猜测】。
* 若 138/126/110 附近的列大量失效，或关键 `5L/6I3/6I5` supply 下坠，则 main 证据被高估，支持 C 或 B【强论据方向】。
* 若同一几何通过另一种 class/mode assignment 可恢复，而当前 deterministic expander 失败，则直接定位为 C：接口和展开策略问题，不是几何 catalog 缺失【强论据】。

盲点：它只能审计已有几何，不能发现 generator 从未生成的 pattern。

## 实验 2：双语义 column-generation LP sprint

建立两条 pricing 臂：

* partition 臂：允许多个局部分量，但发布完整 portal partition；
* one-component 臂：所有 required cells 在一个局部分量。

10 个 region family 每轮各做两次 pricing，共 20 个任务，可在 24 核上一波完成。每个 45 秒，三轮理论 cap 为

[
3\times45\text{s}=135\text{s},
]

加 LP 与进程开销，预算控制在 6 分钟内【猜测】。

判读：

* one-component LP (<3325)，且每个 pricing 的约化成本上界都 (\le0)：证明 B，但只针对 one-component 限制【已证明】。
* partition 臂 (<3325)，且所有 pricing 闭合：证明更广义的当前 region restriction 也不足【已证明】。
* partition 臂 ≥3325、one-component 臂 <3325：强烈支持 C，说明“局部必须单分量”正是主差异【强论据】。
* 两臂均 ≥3325 且产生新的高价值整数列：支持 A，但仍需整数 master 和 G2 witness，LP 本身不证明 A【已证明】。
* pricing 未获得约化成本上界证书：结果只改变置信度，不能形成不可能证明。

盲点：LP ≥3325 可能是分数列拼接；全局方向路由若被放松，也可能仍有 integrality gap。

## 实验 3：同一组 dual 下的 restriction race

固定实验 2 的一组 class/hole dual，分别运行：

* baseline pricing；
* CORE-v2；
* board-edge stub cancel；
* 两区共享 pole 的定向 domino pricing。

至多约 32 个局部任务，24 核分两波，每个 60 秒；做两轮约为

[
2\times2\times60\text{s}=240\text{s},
]

加 master 开销预计低于 8 分钟【猜测】。

判读：

* baseline 自己持续产生正约化成本列，并把 LP 推过 3325：支持 A【强论据】。
* baseline 闭合，但某个单项 relaxation 立刻产生高正约化成本列：支持 B，并定位具体限制【强论据】。
* 只有共享 pole domino 有收益：候选 4 应前置。
* 只有 CORE-v2 有收益：优先修 R-CORE-FRONT-RESERVE。
* 所有 relaxation pricing 都闭合且 LP <3325：形成相应模型下的 B 证明【已证明】。

盲点：局部高收益列未必能在整数 master 中同时使用；代表性 domino seam 也不能覆盖所有相邻 family 组合。

这三个实验分别检查“存量列是否合法”“generator 是否漏列”“哪条限制最值钱”，不重复现有按 family 单独追最大面积的 probe。

---

# Q5：两个机器共用同一 free active-front cell

结论选择 **Q5(b)：条件合法，不应简单禁止；必须做 component-state 同时可实现性检查**【已证明】。

设两个 machine 的 active front 都是同一 cell (f)，outward directions 分别为 (d_1,d_2)。

若 (d_1=d_2)，两者对应的相邻 body port cell 都是 (f-d_1)，会造成 body 重叠。因此合法几何中必有

[
d_1\ne d_2.
]

令 (q_i=\operatorname{opposite}(d_i))。则 (q_1,q_2) 也是不同方向。

按 strict component contract：

* 两个都是 facility outputs：cell (f) 上需要两个不同方向的 component inputs，可由 merger 承载；还需在剩余方向中有一个可用 output。
* 两个都是 facility inputs：可由 splitter 承载；还需一个可用 input。
* 一个 output、一个 input：需要一个 component input 和一个 component output。方向相反时可用 straight，方向垂直时可用 turn；也可在需要继续接入网络时使用带额外方向的 splitter/merger。

因此，“两个 machine 共用一个 front cell”不是 strict rules 下的天然违法行为【已证明】。多 commodity 可共用一个 component，throughput/capacity 又明确不在模型范围内，所以也不存在隐含的容量 1 约束。

但局部存在某个 component 并不自动保证整条 route 合法。例如两个 outputs 共用 cell 时，若剩余两个方向都被 body 封住，就无法给 merger 提供继续进入网络的 output。一个 output 与一个 input 直接用 straight/turn 相连时，也仍需满足其余全局商品和目标可达性。

形式化同时判据应为：

[
\forall f,\quad
\exists \sigma_f\in\Sigma
]

使得：

1. 所有选中 body 的 mode 和 active-front 数量正确；
2. 对每个 incident terminal，(\sigma_f) 含有其要求的输入或输出方向；
3. 同一方向没有互相冲突的角色；
4. (\sigma_f) 的非 terminal 方向只连接可通行邻格；
5. 由全部 (\sigma_f) 诱导的有向图满足 G2 reachability/SCC 条件。

普通的 body-to-front 二分图 matching 不够精确。把每个 cell 容量设为 1 会错误拒绝合法 merger、splitter、cross；只做 Hall 条件也无法表达“两个 input 加一个 output”之类的 component 结构。这里需要 table/SAT 或 hypergraph-state 模型【已证明】。

对 §3.3 数字的影响方向是：

* 增加 simultaneous component-state 条件后，同一候选集合的可行面积只能不变或下降，不可能上升【已证明】。
* 但不能因为出现两个 body 共享 front 就一律扣除该 pattern；很多两 body 情况是合法的。
* 当前 `front_viability_audit.py` 主要逐 body 检查 front 数量与可用性，没有完成跨 body 的 cell-state 联合检查。因此 138/126/110 等 witness 对真实 G2 合法性存在弱乐观风险，具体降幅未知【强论据】。

---

# 仍需的数据

1. **R-PAT-CONN 的权威裁定**：究竟要求每区单分量，还是允许多个局部分量并由全局 portal stitch 连接。文档和 evaluator 目前冲突。
2. **`src.models.port_binding`、strict checker 的 component 验证源码及测试向量**：尤其是 OO、II、OI 共用 front、三至四 terminal 共用 cell、未连接 splitter/merger branch 的处理。
3. **任务书提及但未附的 `RESULT.md`**：需要旧 single-commodity-flow 模型的准确变量、约束和 best-bound 记录，才能判断它只是松弛弱，还是还含有错误耦合。
4. **重新生成的 probe manifest**：应包含 family 名称、规则口径、时间上限、随机种子、incumbent、solver best bound、`exact_ceiling_proved`，并替换当前陈旧的 `probe_results.json`。
5. **上述三个实验的证明性输出**：特别是 master LP dual、每个 pricing 的约化成本 incumbent 与上界、重编译后失效 pattern 的最小冲突证书。

以上判断仅针对咨询包中的 25-region 分区、固定 boundary/core、当前 R-* 限制与 strict contract；不推出任意 70×70 布局无解，也不推出该 benchmark 的更宽泛下界或上界。
