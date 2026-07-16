# 06 — front-clear lift 阶梯4/5：OFF/ON A/B 判读（2026-07-16）

> 数据 = `.artifacts/fc_lift_ab_20260716/{arm_on,arm_off,arm_on_probe2,arm_on_probe3,arm_on_probe4}/`；
> harness = `fc_lift_ab_runner.py`（本目录）。两臂同 revision `7b9cbae`、独立
> 进程、systemd-run MemoryMax=36G/SwapMax=16G（审查 F-06/R16 纪律）；单锚点
> 6×6、配方镜像批C drill_arm1（fixed/probing3/symmetry3/全局单 worker/
> alt_cap200/RAB=1），唯一变量 = `EXACT_MASTER_FRONT_CLEAR_LIFT`。

## §1 A/B 原始结果

| 指标 | arm_off（lift OFF） | arm_on（lift ON） |
|---|---|---|
| 终态 | UNKNOWN（6 迭代帽） | UNKNOWN（**master 无 incumbent**） |
| wall | 3004.6s | 2183.1s |
| master incumbent | **6/6 迭代产出**（~500s/个） | **0 个**（单次 solve ~2130s 无解产出） |
| binding 是否上场 | 是 ×6（RAB 每轮点火） | **从未**（layouts=0、raw 遥测零条） |
| EMPTY_DOMAIN cut | 1293 | 0（无 binding 无 cut） |
| 逐轮 cert | 216/218/214/217/216/213 | — |
| raw=0 验收判据 | n/a（OFF 臂不计） | **NOT_EVALUATED**（未到 binding，判据正确拒绝判绿） |
| 内存峰值（cgroup） | 22.00 GiB | 采样失误（PID 匹配错，作废；build 期 RSS 5.9G 见冒烟） |
| master build | 14.84s / 19,592 intervals | 15.11s / 29,392 intervals |

**OFF 臂 = ③段的逐字复刻**（六轮 cert 数与 arm_rab 完全相同、wall 3005 vs
3089）——本批代码对 lift OFF 路径零行为回归，A/B 对照有效。且 OFF 臂产出
**6 张带 sha 的 incumbent 布局快照**（阶梯 3 corpus 首批素材：这些布局全部
被 binding 判死 ~215 owner，是「lift 应当排除」的正例集）。

## §2 判读

1. **难度按设计位置转移，但未被解决**：lift OFF 时 master 每 ~500s 产出一个
   "front 被堵"的廉价 incumbent、binding 再花一轮证明它不行（每轮 ~215 个
   owner 空域）；lift ON 后这些廉价解在 master 内直接不可行——master 被迫
   在自己的搜索里找"219 个实例每侧 front 同时真自由 + 6×6 ghost"的布局，
   在 fixed branching/单 worker/900s cap 下**一个都没找到**（2183s 墙钟里
   连 FEASIBLE 都没有，也没证出 INFEASIBLE）。
2. **两臂都不收敛，但失败形态完全不同**：OFF = 无信息的踏车替代品（每轮学
   一批 cut、空域 owner 数不降）；ON = 全部预算沉入一次 master 搜索。ON 的
   形态里藏着一个潜在大奖：若 master 能证出 INFEASIBLE，那就是**该锚点的
   合法上界证书**（front-clear 是必要条件 ⟹ 其下 INFEASIBLE = 原问题该锚
   点 INFEASIBLE）——这正是 round-3 翻案后追的东西。
3. **两个未解事实**：①arm_on 墙钟 2183s vs master cap 900s 的差额来源未定
   （runner 已补 last_solve 遥测，探针2 会带回数据）；②fixed branching 配
   方是给旧模型形态调的（批C 门6 的产物），对 lift 后的新结构可能严重不利。

## §3 探针 2（判别配方绑定 vs 结构性；已完成，结果见 §4）

`arm_on_probe2`：default branching（撤 fixed）+ master 专属 4 workers
（全局仍 1）+ master_seconds=3600 + 迭代帽 2，MemoryMax=40G。三种可能结局：

- **出 incumbent** → ON 臂困境是配方绑定，调参可救，lift 进入可用形态评估；
- **证出 INFEASIBLE** → 6×6 锚点合法上界证书（研究线重大结果）；
- **仍 UNKNOWN** → 结构墙证据增强，lift 保持 default-OFF、RAB 迭代通道继续
  当运行时皮带，结果与调参杠杆一并交 owner 拍板。

（结果回填：见 §4。）

## §3.5 阶梯 3：corpus 无 solve 结构检查（已完成，全绿）

harness = `fc_lift_corpus_checker.py`（本目录）；输入 = OFF 臂 6 张布局快照。
对每张 × 每个范围内实例双向核对「RAB filter 后域空 ⟺ 某侧自由 front 计数 <
demand」——左侧真实 binding+filter 重建（ground truth）、右侧独立重算
（pose 原始端口 + _DIR_DELTA + SSOT demand = lift 约束的数学语义）：

- **1,314 次实例级核对（6×219）零 mismatch**；
- 1,294 空域 owner 全部被计数谓词精确预测（⟹ 方向）；
- **20 个非空 owner 全部计数达标（⟸ 负控——超杀方向零违规）**；
- 每张布局 empty 数 = 该轮 [rab-sep] cert 数（216/218/214/217/216/213），
  与 ③段/OFF 臂遥测三方自洽。

结论：lift 约束语义在 prod 布局上双向正确；这 6 张 OFF incumbent 在 lift ON
的 master 内必然不可行（吞并判据的镜像面成立）。ON 臂"无 incumbent"不是
超杀征兆——是廉价解被正确排除后残余问题的真实硬度。

## §4 探针 2 结果：病灶定位 = presolve 展开爆炸（不是结构墙）

`arm_on_probe2`（master 4 workers + 3600s 预算）：UNKNOWN、wall 2153s——
与 arm_on 的 2183s 在**不同 cap 下停同一点**。last_solve 遥测揭底：

```
branches=0 conflicts=0 propagations=0  ← solver 从未开始搜索
deterministic_time=5.5  wall=2152.6    ← 全部时间沉在 presolve
cgroup peak=29.9 GiB（build 期仅 ~6G）
search_branching=FIXED_SEARCH（requested="fixed"）
usertime==walltime ← 单线程
```

四个结论：
1. **病灶 = 1,702 个全网格宽域 AddElement 的 presolve 展开**（f 域 [0,5183]
   ≈ 5M 展开单位、~30G、35+ 分钟）。C1 先例可行是因为 witness 被 footprint
   钉窄（≤36 值）；lift 的 f 是锚点全域派生。审查席 encoding F1 的"继续给
   f 紧域"警告命中——但**域收紧救不了它**：宽域 slot 的可达带 ≈ 全网格
   （锚点全域平移），элement 天然是 ~5k 路 2D 查表。
2. **探针 2 的两个杠杆都没真拉动**：exact 模式下 branching env 缺省即 fixed
   （`master_model.py:11553`），"default" = 不设 env = 仍 fixed；presolve
   单线程，master workers 无关。探针 2 实为 arm_on 的复跑（复现性 ✓）。
3. 终止点 ~2150s 与两种 wall cap 都不符——presolve 巨型单步迟检 time limit
   （arm_on）解释不了 probe2（3600s 未到）；最可能 = CP-SAT 内部 memory
   guard（默认 max_memory_in_mb=10000）在 presolve 中触发致 UNKNOWN。机制
   未终证，但两次同点停 = 确定性终止、与搜索无关。
4. **"结构墙"判断撤回待定**：master 从未搜索过，ON 臂数据对"lift 后真问题
   硬度"零信息量。先修 presolve 病灶再谈硬度。

**修复菜单**：
- A（探针 3，env-only）：`EXACT_MASTER_CP_MODEL_PRESOLVE=0`（allowlisted）
  ——element 有原生传播器，不展开；fixed search 逐槽赋值时 element 传播
  是平凡的。代价 = 失去 presolve 对整个模型的其它化简。
- B（小批）：`expand_element_constraints=false` 外科手术参数——但 certified
  的 EXACT_SUBPROBLEM_PARAMS 守卫只放行 4 个键，扩键 = sealed 小批 +
  soundness 注记（该参数只改内部表示、complete-solve-preserving）。
- C（编码重构）：分析过的方向都不省——域收紧对宽域 slot 无效、witness 数
  减半仍 ~2.5M、front-marker interval 会跨实例互斥（共享 front cell 超杀）。
  除非有新形态，暂不押注。

## §4.5 探针 3 结果：修复 A 生效——搜索真正启动，30min fixed 无果

`arm_on_probe3`（`EXACT_MASTER_CP_MODEL_PRESOLVE=0`，其余镜像 arm_on：
fixed/单 worker；master 1800s、迭代帽 1）：**UNKNOWN，但性质完全不同**——

```
branches=66,698,954  conflicts=181,244        ← vs 探针2 的 0/0：搜索真启动
deterministic_time=2303.9                     ← vs 探针2 的 5.5
walltime=1805.04 ≈ cap 1800s                  ← 第一次真被 time limit 停
booleans=25,148,832  integers=38,585          ← presolve off 的加载形态
内存峰值 33.7 GiB RAM + 11.4 GiB swap（journal 权威；40G/16G 帽内、余量不大）
```

判读：
1. **presolve 展开病灶确认为先前唯一拦路虎**（修复菜单 A 生效）：element 走
   原生传播器后 solver 全预算真搜索。探针 2 的"~2150s 确定性终止"机制随病灶
   移除不再复现，正式归档为 presolve 路径专属现象。
2. **第一份有信息量的硬度数据点**：30 分钟 × fixed search × 单 worker 真搜索，
   无 incumbent、无 INFEASIBLE。此前所有 ON 臂 UNKNOWN 对硬度零信息（solver
   没搜过）；这一份是真的"搜了没搜出来"。
3. 覆盖面仍窄：fixed search 的 guided branching profile
   （`exact_coordinate_guided_branching_v4`）是给旧形态（廉价 incumbent 快速
   产出）调的，对 lift 后结构可能系统性不利；且 25.1M 布尔的加载形态吃掉
   33.7G+11.4G swap，内存余量薄。
4. **探针 4（最后一根 env-only 杠杆）**：`EXACT_MASTER_SEARCH_BRANCHING`
   合法值域含 `automatic`/`portfolio`（master_model.py:11553 起；探针 2 的
   "default"=unset=仍 fixed，不是有效杠杆）——presolve off + automatic
   一发判别"fixed 是不是残余瓶颈"。结果见 §4.6。

## §4.6 探针 4 结果（presolve off + automatic branching；待回填）

## §5 诚实边界

- 单锚点（6×6）×单配方族；外推到其它 anchor 属推断。
- arm_on 的 raw=0 吞并判据一次都没被评估过——lift 的语义正确性由 build 期
  哨兵/全池黄金对照/**阶梯 3 corpus 检查（1,314 次双向核对零 mismatch，含
  20 个非空负控）**三面背书，但 raw=0 判据本身仍无 prod solve 级评估记录
  （需要 master 在 lift ON 下产出 incumbent 才可能评估）。
- 硬度结论的覆盖面：探针 3/4 各 30 分钟单发；"解不动"只在测过的
  branching×预算格子内成立，不是普适结构墙证明。
