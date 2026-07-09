# 诊断侦察·ablation_map（Fable，2026-07-09）

## Headline

6×6 coordinate master 的约束族已全量盘点：真正的模型只有 8 族（slot 几何/签名桶/对称链/核心 no_overlap_2d/ghost 族/供电 witness/供电容量族/全局有效不等式），其中「供电三层」和「ghost 4225-anchor 多重性」是仅有的两大可疑墙，且每族都找到了 harness 层合法关闭开关（构造 flag、create 后 unsafe env + 自建 core、from_exact_core kwarg、monkeypatch 四类）——另出土两个免费大发现：最终模型里存在两个语义嵌套的冗余 no_overlap_2d，且历史 5 条 6×6 cut 是 865-instance 的旧 pose 表示产物（不能证明当前 coordinate_exact_v2 表示曾解出过 6×6）。

## 硬事实

- exact 模式下 MasterPlacementModel.build() 全权委托 CoordinateExactMasterDelegate，master_model.py 里的 pose-bool 约束族（_add_assignment/_add_set_packing/_add_power_coverage 等，含 4664 行的 skip_power_coverage 分支）在 certified 路径根本不执行——盘点与消融对象必须是 delegate
  - 出处: src/models/master_model.py:4645-4657
- delegate 的完整约束族构建顺序：mandatory/required-optional/residual-optional/power-pole 四类 slot 变量 → 坐标对称破缺 → AddNoOverlap2D(核心 interval) → ghost 族 → 供电覆盖 witness（三分支：几何 witness / lazy_completion 跳过 / L4a fail-closed）→ 全局有效不等式 → 搜索引导
  - 出处: src/models/exact_coordinate_master.py:3444-3494
- harness 用的 from_exact_core 路径只做 proto 克隆 + bind_from_core + _add_ghost_constraints + 搜索引导重建——核心族（供电/对称/slot 域）全部烘焙在 core proto 里，消融它们必须重建 core，仅设 env 不重建 = 无效实验
  - 出处: src/models/master_model.py:2950-2991
- 最终模型含两个 no_overlap_2d：core-only 版（build 时加、烘焙进 core proto）+ ghost overlay 加的 core+ghost 组合版——前者被后者语义完全包含，是纯冗余的重复传播负担（最重 propagator ×2）
  - 出处: src/models/exact_coordinate_master.py:3467-3468 与 3769-3772
- ghost 族 = 6×6 时 4225 个 u_var + AddExactlyOne + 每 anchor 一对 OptionalIntervalVar 注入组合 no_overlap_2d；anchor 域可用 from_exact_core 的公开 kwarg ghost_anchor_filter 收缩（源码注释自述就是为 anchor slicing PoC 留的），env 版 EXACT_MASTER_GHOST_ANCHOR_FILTER 在 unsafe-map
  - 出处: src/models/exact_coordinate_master.py:3719-3772; src/models/master_model.py:2722,2321-2325; src/search/benders_loop.py:950-953
- ghost overlay 的三个 tightener（power capacity screen / signature bucket tightening / residual tightening）在 _add_ghost_constraints 里无条件调用、没有任何 off 开关（相关 env 全是 instrumentation 或 formulation 二选一 big_m/enforced）——单独消融只能 monkeypatch；no-op 安全因为三个 stats dict 在调用前已预初始化
  - 出处: src/models/exact_coordinate_master.py:3765-3767(调用),3677-3701(stats 预初始化),3793,4074,4916(三方法); 246-260(formulation 无 off 值)
- skip_power_coverage 构造参数（build_exact_core 可传）一刀关掉供电全家桶：几何 witness（3471-3476）、容量族下界（6308-6314）、pole 族系数准备（2114-2115，连带 ghost screen 因系数空在 3866-3871 自动短路），并且会放宽 powered 模板的 pose 候选域（1946-1955）——注意它是『最大刀』，消融判读时要知道它同时改了 4 处
  - 出处: src/models/exact_coordinate_master.py:3471-3476,6308-6314,2114-2115,3866-3871,1946-1955; src/models/master_model.py:2313,2626
- EXACT_LAZY_POWER_COMPLETION=1 是『中刀』：只跳过几何覆盖 witness，保留 pole slot 与容量族——与 skip_power_coverage 对照可分离『witness 编码代价』vs『容量约束紧度』；它在 certified unsafe-map（lazy_power_completion_not_certified），且 ExactSearchSession.create 构造前就 fail-closed 检查，所以必须 create 之后设 env 再手动 build_exact_core
  - 出处: src/models/exact_coordinate_master.py:2270-2281,3470-3486; src/search/benders_loop.py:962-965,2211-2220
- 残余 power_pole slot 上界 = 763（worst-case 每 powered slot 配 1 pole，源码注释自述这是『项目 30GB RAM 真凶』、实际估需 60-100）；EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE 可收窄（注明风险：设太小 → 假 INFEASIBLE）
  - 出处: src/models/exact_coordinate_master.py:2094-2113
- enable_symmetry_breaking=False（build_exact_core 构造参数）关闭 signature monotonic 对称链；这是除 skip_power_coverage 外唯一的核心族构造级开关
  - 出处: src/models/exact_coordinate_master.py:3595-3600; src/models/master_model.py:2314,2627
- EXACT_USE_POSE_BOOL_MASTER=1 切换整个表示层到 PoseBoolExactMasterDelegate，源码注释载 Phase 0 PoC 数据『27×15 anchor 53s OPTIMAL vs coordinate 30 min UNKNOWN』——现成的表示层对照组；同在 unsafe-map（954-957）
  - 出处: src/models/master_model.py:2595-2606; src/search/benders_loop.py:954-957
- 历史 cuts_6x6.json 的 5 条 whole-layout cut，conflict_set 是 865 个 instance_id→pose_idx 映射（如 boundary_port_001→0），不是当前 266 实例的坐标表示——历史 6×6 候选大概率产自旧 pose-bool 类表示，『当前 coordinate_exact_v2 模型曾在 6×6 出过解』并无证据
  - 出处: data/solutions/cuts_6x6.json（实测解析：5 条、每条 864-865 键、值为 pose 索引）
- 6×6 全约束模型规模：booleans 1,549,068 / integers 1,327,462 / lp_iterations 65,667（1800s automatic 真多核跑满仍 UNKNOWN、conflicts 仅 453）——布尔海洋主要来自签名桶 region literal（每 slot×bucket×region 一个）与供电 witness，精确分账待 P0 build 探针
  - 出处: docs/research/p1_3_m5_convergence_20260708/results_scan/cell_g6x6_linux_p4cfg_1800.json(last_solve.response_stats); src/models/exact_coordinate_master.py:2777-2822(region literal),5851-5933(witness)
- solve() 在 exact 模式强制 probing/symmetry>=3（env 可压）、硬调用 subsolver 过滤（砍 feasibility_pump/violation_ls 首解主力，无 env）、EXACT_SUBPROBLEM_PARAMS 是通用 solver.parameters setattr 注入口——solve 层旋钮已被前 14 个 cell 穷举为负，消融矩阵不必再扫这层
  - 出处: src/models/master_model.py:11523-11534,11480; src/models/cp_sat_worker_config.py:184-205,160-176
- m5_cell_runner 的直调路径（ExactSearchSession.create → from_exact_core → LBBDController.run_with_status）绕过 run_benders_for_ghost_rect 的 unsafe-map 门，但 create 自身也查一遍 unsafe env——所以消融开关的设置时序必须是『create 之后、build_exact_core 之前』（runner 已有同款先例：EXACT_CUT_FRAMEWORK_ATTACH 的 pop-then-export 与 --no-subsolver-filter monkeypatch）
  - 出处: docs/research/p1_3_m5_convergence_20260708/m5_cell_runner.py:117-149,196-199; src/search/benders_loop.py:2211-2220,8068-8071

## 实验设计

【消融实验矩阵：m5_ablation_runner.py（放 docs/research/p1_3_m5_convergence_20260708/，骨架抄 m5_cell_runner.py）】

=== 通用骨架（与 m5_cell_runner 差异点）===
```python
# 1) 洁净 env → session（guard 要求此刻无 unsafe env）
for k in ("EXACT_CUT_FRAMEWORK_ATTACH","EXACT_LAZY_POWER_COMPLETION","EXACT_USE_POSE_BOOL_MASTER","EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE"): os.environ.pop(k, None)
session = ExactSearchSession.create(PROJECT_ROOT, solve_mode="certified_exact")
# 2) 按 cell 设开关（此刻才允许出现 unsafe env / monkeypatch）
# 3) 需重建 core 的 cell：
core = MasterPlacementModel.build_exact_core(
    session.instances, session.facility_pools, session.rules,
    skip_power_coverage=..., enable_symmetry_breaking=...,
    generic_io_requirements=session.core.generic_io_requirements,
    wireless_sink_generic_input_slots=session.core.wireless_sink_generic_input_slots)
# 不需重建的 cell：core = session.core
master = MasterPlacementModel.from_exact_core(core, ghost_rect=(6,6) 或 None, ghost_anchor_filter=可选)
# 4) solve：no_ghost/single_anchor 走单轮 master.solve(args.master_seconds)（不进 LBBD）；其余走 LBBDController（binding/routing 600s、max_iterations 3）
# 5) 落盘：沿用 runner 的 last_solve 采集 + 新增 build_stats 子树
#    （power_coverage / global_valid_inequalities.ghost_aware_via_pole_feasibility /
#     coordinate_symmetry / ghost_rect / search_guidance）+ proto 直方图：
#    hist = Counter(c.WhichOneof("constraint") for c in master.model.Proto().constraints)
```
统一参数：w12、EXACT_SUBPROBLEM_MAX_MEMORY_MB=28000、systemd-run --user -p MemoryMax=42G 硬帽、每发前清 __pycache__、串行一次一个、日志放 ~/m5_runs/。solve 主档 --master-presolve 0（6×6 已证唯一能让搜索立刻开跑的档，notes L66），出解的 cell 再补 CP-SAT 默认档复验一发。

=== P0（本机现在就能做，零 solve、纯 build 探针，~5min/个）===
对 {baseline, no_ghost, skip_power, no_overlay} 各 build 一次、dump proto 直方图+build_stats 族计数，产出『每族编码体量表』（1.55M booleans 谁贡献的）。判读：某族占 booleans/constraints >40% = 编码代价头号嫌疑，直接给消融 cell 排优先级。

=== 第一波 solve cells（600s/w12/presolve-off，每 cell ≈15-20min，4 cell ≈1.5h；待换硅脂或转生产机）===
① C-NG（no_ghost）：from_exact_core(session.core, ghost_rect=None)，单轮 master.solve(600)。
   判读：出解 → ghost 族是墙（走②细分）；UNKNOWN → 72% 占用的纯打包+供电编码本身就是墙、ghost 无辜（跳③④）。
② C-1A（single_anchor ×3：(0,0)/(32,32)/(64,64)）：ghost_anchor_filter=[(x,y)]，单轮 solve。
   判读：出解 → 墙 = anchor 多重性（4225 选 1 的分支灾难），修复方向 = anchor 分片外置/EXACT_PARALLEL_PROCESSES 按 anchor 切；可加 64/256/1024 anchor 档量化衰减曲线。三个全 UNKNOWN → 墙 = 6×6 空间紧度或编码（走③）。INFEASIBLE = exact-safe 有效信号（该 anchor 真放不下），换 anchor 补测。
③ C-PW（skip_power_coverage=True，重建 core）：LBBD 全链。
   判读：出解 → 供电族是墙（走④细分）；UNKNOWN → 供电无辜，转 C-PB + no_overlap 去重。
④ C-PB（EXACT_USE_POSE_BOOL_MASTER=1，create 后设 env + 重建 core；先 build 探针验通 from_exact_core 兼容分支 master_model.py:2787-2798 再 solve）：
   判读：出解 → coordinate_exact_v2 表示本身是墙（历史 5 cut 本就是 pose 表示产物，闭环）→ M5 反哺方向变成表示层复核。

=== 第二波（按第一波结果走分支，每 cell 同预算）===
⑤ C-LZ（EXACT_LAZY_POWER_COMPLETION=1，create 后设 env + 重建 core）：仅当 C-PW 出解时跑。出解 → 墙 = witness 编码（容量族无辜），生产修复方向 = L4b lazy completion 通电；UNKNOWN → 墙 = 容量族/screen 紧度。
⑥ C-OV（monkeypatch 三 tightener 为 no-op：CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening/_apply_ghost_anchor_residual_signature_bucket_tightening/_apply_ghost_anchor_power_capacity_screen = lambda self: None；core 不用重建，overlay 在 from_exact_core 时加）：出解 → ghost-conditioned 大M strengthening 在帮倒忙（理论只该帮不该害），生产修复 = 旋钮化这三个 tightener。
⑦ C-SB（enable_symmetry_breaking=False，重建 core）：出解 → monotonic 链与首解搜索冲突。
⑧ C-PC（EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE=100，create 后设 env + 重建 core）：出解 → 763 pole slot 的规模才是墙（注意假 INFEASIBLE 风险：INFEASIBLE 时抬到 200 复测）。
⑨ C-NOD（proto 手术去重冗余 no_overlap_2d：from_exact_core 后扫 master.model.Proto().constraints，找到 interval 集合 = 纯 core interval 的那个 no_overlap_2d、Clear() 之；先在 build 探针里验证直方图 no_overlap_2d 数从 2→1）：出解或 branches 曲线剧变 → 冗余传播负担坐实，生产修复 = overlay 路径跳过 core-only 版。

=== 消融顺序合理性（依赖）===
先 C-NG/C-1A（结构定位 ghost vs 非 ghost，最便宜、区分度最大、不动任何约束语义）→ 再 C-PW（最大刀）→ 出解才有 C-LZ 细分的意义；C-OV/C-SB/C-PC/C-NOD 是独立正交刀随时可插队；C-PB 是表示层对照与①-③正交。全部 cell 保持默认 warm-start（与 14 个基线可比）；若某 cell 出解，立即补 attach-on 孪生 = M5 A/B 第一对。全矩阵 9-12 cell ≈ 3-6h 串行。

## 风险

- 全部消融开关（skip_power/lazy/pose_bool/anchor_filter/pole_cap）都在 certified unsafe-map（benders_loop.py:949-983），是 proof 语义级改动：结果只用于诊断，严禁任何形式回流 certified 路径；每个 cell 的 JSON 必须透明记录所用开关（照 --no-subsolver-filter 先例）
- 消融出的『解』不是全约束模型的解（skip_power 的解缺供电覆盖、single_anchor 的解只覆盖一个 anchor）——判读只回答『哪族是首解之墙』，绝不能读成『生产可以关这族』
- env 时序陷阱：unsafe env 在 ExactSearchSession.create 之前存在会直接 raise（benders_loop.py:2211-2220）；且 session.core 已烘焙默认约束，lazy_power/pose_bool/pole_cap 只设 env 不重建 core = 静默无效实验（假阴性）——runner 必须断言重建后的 build_stats 反映了开关（如 power_coverage.representation=="lazy_power_completion_v1"）
- monkeypatch no-op 依赖 _add_ghost_constraints:3677-3701 的 stats 预初始化才安全；若未来源码把初始化挪到 _apply_* 内部会变 KeyError——runner 里对 stats 键做防御性断言
- 本机硅脂期原生层点火不稳（notes L139 停机决定；ghost_first/after_counts 两档三跑三死）：所有 solve cell 必须等换硅脂或转生产机；P0 build 探针虽单线程低热，仍建议避开高温时段、一次一个
- single_anchor 的特定 anchor 可能真 INFEASIBLE（局部放不下 6×6），单点结果不能外推——至少 3 个分散 anchor，且 INFEASIBLE 与 UNKNOWN 判读严格分开
- pose_bool 的 from_exact_core 兼容分支（master_model.py:2787-2798）在本课题从未跑通过，可能有未知坑——先 build 探针验通再投 solve 预算
- no_ghost/single_anchor 单轮 master.solve 仍走 exact 模式强制 presolve/probing>=3（master_model.py:11527,11533）——presolve 旋钮必须照带，否则 600s 又全交 presolve 税、测了个寂寞
- 消融后模型变小，presolve 行为可能质变（8×8 probing1 够用、6×6 卡死的先例）：跨 cell 比较只在同 presolve 档内做；出解信号跨档复验
- w12 + 42G MemoryMax 硬帽是 q3z（w24 RSS 39.3GB 内核 OOM、CP-SAT 软帽拦不住峰值）换来的教训，不可省略；两个 master 并发 = OOM 双杀（Windows 侧实测）铁律继续有效