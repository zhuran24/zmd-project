# M5 第一阶段 verdict（定稿，2026-07-08）

> 原始数据：`results_smoke/`、`results_scan/`、`probes/`；过程记录：`notes_phase1.md`。

## 一句话结论

本机（Windows 11 / 24 逻辑核 / 47.7GB RAM）在 ≤3600s 单 master 预算内，**任何配置组合都无法产出第一个 master 候选**——LBBD 卡在第 1 步，binding/routing 永不开审，attach 战场打不开；唯一有理论出路的组合（presolve 出头后 automatic portfolio）在本机 OR-Tools 上**原生段错误**（两发、`ortools.dll` 内 0xC0000005、不同偏移）。M5 收敛 A/B 实测在本机不可行，转生产机窗口或过夜多小时预算需 owner 拍板。

## 覆盖的配置空间（穷举证据）

| 维度 | 试过的值 |
|---|---|
| ghost 尺寸 | 6×6（历史战场）/ 8×8 / 12×12 / 16×16 / 20×20 / 26×26 / 32×32 / 40×40 |
| master 预算 | 90s / 600s / 1800s / 3600s |
| workers | 1 / 4 / 12 |
| presolve | 默认（probing/symmetry 强制≥3）/ diet（=1）/ 全关 |
| 分支策略 | fixed（生产默认）/ automatic |
| subsolver 过滤 | 生产过滤（砍 feasibility_pump/violation_ls）/ 无过滤（测量专用旁路）|
| warm-start | ghost-agnostic 266 hint（生产形态）/ ghost-aware 解锁（anchor 4096/验 32）|

全部 UNKNOWN，`coordinate_framework_cut_count` 恒 0（attach 零触发——不是 attach 的问题，是战场没开）。

## 四层性能税（诊断产出，对生产跑独立有价值）

1. **presolve 黑洞**：exact 模式 solve() 强制 `probing_level>=3`、`symmetry_level>=3`（`master_model.py:11527,11533`）——prod-scale 模型上 CP-SAT 单线程 presolve 吃掉 500s+ wall（`branches=0, booleans=0, deterministic≈18.76` 指纹），600s 预算全交税。压到 1 在 8×8 够用；6×6（interval 11596）又卡死 → 对模型规模强敏感。
2. **presolve 关闭的代价**：搜索立刻开跑，但 CP-SAT 多 worker portfolio 塌缩成单路顺序搜索（fixed 与 automatic+无过滤的 branches/conflicts 几乎一致：~7.15M/~3030，restarts=0）——presolve 与 portfolio 二选一。
3. **ghost-aware 修复机器的验证税**：`EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS=64` 使任何现实 ghost（2025-3969 anchor）整体跳过 ghost-aware 重建；解锁后重建真的产出完整布局（161 anchor 尝试 / 32 个 798 字段全钉死的候选），但每 anchor 2s 的验证 mini-solve 也卡 presolve（`branches=0`）→ 32 个全部假阴性 UNKNOWN → `none_compatible`。**「全钉死的模型验证不出结果」是 presolve 税最刺眼的形态。**
4. **首解主力被过滤**：`MASTER_IGNORE_SUBSOLVERS_FOR_MAX_LEX` 砍掉 `feasibility_pump`/`violation_ls`（feasibility-jump，CP-SAT 首解发现主力）——Phase 3C 为 max_lex 调参的决定，对「找第一个可行解」反向优化。无 env 开关（harness 加了测量专用旁路）。

结构性背景：266 设施占 4900 格的 72%（占用不变量 3544 格，空格恒 1356 → ghost 上限 ≈36×36）；warm-start 的 greedy hint 是「不管 ghost 的布局」，master 必须在 72% 满的盘上自行腾洞。

## 历史战场证据

`data/solutions/cuts_6x6.json`（tracked，历史 CutManager checkpoint）：5 条 whole-layout conflict_set（266 实例）——历史实跑在 **ghost 6×6** master 至少出过 5 个候选、全被 binding/routing 否决 = attach 触发点真实发生过。其余尺寸的 cuts 文件全空。历史机器/预算/master 表示版本未知（当前 `coordinate_exact_v2` 是 Phase 3C 重做的）。

## 终极 cell（两发）

`g6x6_presolve_then_portfolio_3600`（probing1/symmetry1 + automatic + **无过滤** + w12 + 3600s）：**solve ~28min 处 `ortools.dll` 原生段错误**（0xC0000005，独占跑、非 OOM）——头号嫌疑 = 旁路放回的 `violation_ls`/`feasibility_pump` 触发 OR-Tools 原生 bug。若坐实，Phase 3C 过滤清单意外有避崩价值（生产复核材料 +1）。

`g6x6_filtered_portfolio_3600`（同配置去掉旁路，隔离验证 + 继续测「presolve 出头后 portfolio」）：**同样 `ortools.dll` 内 0xC0000005**（solve ~11min 处，不同偏移 0x80e689 vs 0x7ae290）——旁路排除，崩因锁定为 **6×6 模型 + automatic 分支 + presolve 开** 的组合在本机 OR-Tools 上原生不稳定（对照：P4r 同参数在 8×8/600s 干净退出）。不同偏移 ⇒ 非单点确定性 bug，更像该组合下的内存压力/worker 竞态。

**推论**：本机逃逸路径全部封死——presolve 开 → 卡死或崩溃；presolve 关 → portfolio 塌缩单路搜索（1800s/7.2M branches 无解）。

## 资源方案选项（owner 拍板材料）

按「打开战场」的路径分：

1. **Linux 生产机跑 M5**（原设计轴）：生产 wrapper 是 Linux 导向；原历史候选大概率产自更长时间轴（campaign ≥24h、`EXACT_PARALLEL_PROCESSES` 多 ghost 并行）。M5 的 A/B 矩阵天然适合搬过去。成本 = 需要那台机器。
2. **本机过夜级单 solve**（4-8h/cell）：仅剩 fixed+presolve-diet 超长预算一条缝（automatic 会崩、presolve-off 已证 1800s 无解）——presolve 若在 1-2h 内出头、fixed 搜索还得靠 propagation 红利翻盘，胜率低。A/B 矩阵（≥8 cell）数天级。慢、胜率低、但零依赖。
3. **先收可收的**：M5 拆两半——「attach 机制开销测量」（M1 已给出：literal 复用后 50% 退化线 15-20K cut）与「收敛增益 A/B」（依赖战场）。前者已完成；后者标 BLOCKED_ON_COMPUTE，M5 以「可行性 verdict + 四层税诊断 + harness 交付」收口，A/B 等生产机窗口。
4. **性能税修复线**（独立于 M5，反哺生产）：presolve 强制 ≥3 的档位、subsolver 过滤清单、ghost-aware 验证 profile 无旋钮、anchor 限 64——四项都值得生产侧复核（改动碰 sealed 面，走正常 reseal 流程，属 P1.3/P1.21 性能债范畴）。**注意**：这些默认值可能是 Phase 3C 在「已有 incumbent 后的增量求解」场景下调优的，对「冷启动首解」不利不等于对生产错——复核时要分场景。

推荐：**3 + 4 组合**（M5 第一阶段按实测现实收口、诊断反哺生产），A/B 实测挂 1 的窗口。2 不推荐（终极两发已证 automatic 崩、唯一剩缝胜率低）。**4 的补充警示**：subsolver 过滤清单在本机意外有避崩价值存疑（两次崩溃偏移不同、且过滤版也崩）——生产复核时把「过滤清单」与「Windows OR-Tools 该版本在 prod-scale 模型上的稳定性」分开评估，勿混为一谈。

## attach 链自身状态

M4 四族全通电、telemetry（attached_by_family/预算闸/per-family last_cut）就位、四层关卡链全绿——**attach 链本身没有任何已知缺陷在等 M5**；M5 是它的效果计量，不是它的正确性验收（正确性由 M4 的测试与等价回归背书）。升格三前置仍是「只剩 owner 显式决定」。
