# 终末地 IndustrialPlanner 精确求解器 — P0-1 最终修复第一步:lazy connectivity cut(实现任务)

## 任务性质(新会话零历史,这是实现不是审查)

附件是完整项目快照 zip(zip 内 `project/` 为仓库根;ZIP_LZMA,用 `python -m zipfile -e <附件>.zip .` 解包)。依赖 wheels 在本 Project 文件区,沙盒 Python 3.13,离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。

owner 已拍板 P0-1 最终修复两步走:**第一步(本任务)= 在 routing guard 的拒绝循环里实现 lazy connectivity cut(source-side component cut),替代/强化现有的 selected-positive nogood**;第二步(不在本任务)= P1.3B 期把 per-commodity flow 一等编码进 CP-SAT。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器(目标 `max_lex(area, min_side)`,266 强制设施,OR-Tools CP-SAT 9.15 + Benders/LBBD 分解 master→binding→routing→flow)。宪法 `PROJECT_LOCK.md`;certified_exact 与 exploratory 严格分离;fail-closed 默认姿态。

## 背景(现状代码已含 P0 修复批次,两轮外审收口)

`src/models/routing_subproblem.py` 的现状:
- routing CP-SAT 只有局部 successor/predecessor 约束(`:864-937` 附近),FEASIBLE 不蕴含全局连通;
- P0-1 修复加了 **connectivity guard**:`solve()` 接受 incumbent 前按 commodity 重建选中 route-state 有向图、检查 source front → sink front 可达(`_validate_selected_route_connectivity()`);不可达 → 加 **selected-positive nogood**(`_add_selected_route_nogood()`,`BoolOr([v.Not() for v in selected])`,禁该选中集的超集)→ 重解;预算耗尽 → `_solver=None`、`_status=UNKNOWN`、返回 TIMEOUT;`extract_routes()` 要求 `_connectivity_guard_accepted`。
- **问题(完整性代价)**:70×70 大域里"局部闭合但不接 terminal"的环/孤岛组件可以海量存在,逐个 nogood 排除最坏指数级 → 候选大面积 UNKNOWN。第二轮外审的 Q3 评估认为高 UNKNOWN 率风险可信,推荐的折中正是本任务。

## 要实现什么:source-side component cut(有向 cutset 不等式)

在 guard 拒绝 commodity `c` 的 incumbent 时,生成一条**对该 commodity 无条件有效**的连通性割约束:

1. **W 集构造**:`W` = 从 `c` 的全部 source front 出发、**只沿 incumbent 已选中(selected)的 state 图**可达的节点闭包(= guard 已算出的 incumbent 可达区)。由"被拒"可知全部 sink front ∉ W。
2. **crossing 集 X**:`X` = 所有**候选**(不只是 selected)的 route-state,满足"它能把流从 W 内某 state 接出到 W 外"(沿 routing 模型的 arc 语义:state 的 `flow_out` 指向邻格、邻格 state 的 `flow_in == DIR_OPP[flow_out]`、同 commodity;以及 W 边界上能接 source front 输出的 state,语义必须与 `_validate_selected_route_connectivity()` 重建图的 arc 语义**严格同构**)。
3. **割约束**:`sum(r_var[s] for s in X) >= 1` 加进 model 后重解。
4. **为什么 valid(必须写进 FIXES 论证)**:任何物理可行的 routing 都必须把 `c` 从某个 source front 运到某个 sink front,即存在一条选中 state 路径从 W 内走到 W 外 → 该路径第一次跨出 W 的 state ∈ X 且被选中 → 任何可行解满足 `sum(X) >= 1`。这条不等式**不依赖 incumbent**、无条件有效,绝不误杀可行解。
5. **为什么强于 nogood**:incumbent 在 X 上选中数 = 0(W 是 selected-可达**闭包**,若有 selected state 跨出 W 则 W 会更大——矛盾),所以该割排除当前 incumbent **以及所有共享同一可达闭包的同类 incumbent**(一刀一族,nogood 一刀一个)。

## 硬性工程要求

1. **每条割加进 model 前必须过独立有效性自检(fail-closed)**,三项缺一不可:
   a. 全部 source front ∈ W,全部 sink front ∉ W(用独立重算确认,不信生成过程);
   b. **X 是完整 crossing 边界**:在"全候选 state 图"(potential graph)里把 X 移除后,从 source front 出发不可达任何 sink front(独立 BFS 重验——这是割确实分离的证书);
   c. incumbent 的 selected 集与 X 交集为空(确认这条割真的排除当前 incumbent,保证循环有进展)。
   **任何一项不过 → 该次拒绝退回现有 selected-positive nogood**(现行为保底),并在 telemetry 记 fallback 原因。
2. **guard 验收边界一字不动**:割只是加速收敛的手段,`_validate_selected_route_connectivity()` + `_connectivity_guard_accepted` 仍是最终 soundness 边界(纵深防御)。TIMEOUT/UNKNOWN 语义、`extract_routes()` 双门全保持。
3. **不引入新 env knob**,默认启用(与 P0-1 guard 本身一致;割是 sound-only 方向 + 每条都带自验 + 失败回退)。不改变 env-off / exploratory 行为。
4. **纯 Python 实现**(BFS/可达闭包足够,不需要真 max-flow 库;active domain 图很小),不加新依赖。
5. **telemetry**:`build_stats["last_solve"]["connectivity_guard"]` 里加计数:cuts_added、cut_sizes、fallback_nogoods(含原因)、rejected_incumbents 沿用。
6. **多 commodity**:一次拒绝可能多个 commodity 失败(guard 已会同时报)——对每个失败 commodity 各生成各自的割(各自自检,失败各自回退 nogood)。
7. **三件套同步**:`PROJECT_LOCK.md` 增补不变式一行;`specs/09_exact_grid_routing_subproblem.md` 加一节(如 §9.8 lazy connectivity cuts:割形状、有效性论证、自检义务、回退语义);regression 测试(见下)。
8. **代码质量**:ruff / mypy(core lifecycle 那套)零新增问题;LF 行尾;不要死变量(上一轮交付有 F841 前科)。

## Regression 要求(每条都要可判别)

1. **收敛性**:既有"窄走廊 3-commodity"INFEASIBLE probe(`src/tests/test_p0_certified_soundness_fixes.py` 里的场景)在割启用下仍正确 INFEASIBLE,且 telemetry 显示走了 cut 路径(cuts_added ≥ 1)而非纯 nogood 枚举。
2. **完整性保真(最关键)**:构造一个**物理可行**的 routing 场景(source→sink 有真路径),强制 CP-SAT 先产出一个 disconnected incumbent(参考既有测试的固定手法),验证:割加入后重解**仍能找到可行解并通过 guard 验收返回 FEASIBLE**——证明割没有误杀真解。
3. **自检回退**:构造让有效性自检失败的场景(可用 monkeypatch 破坏 X 完整性),验证回退到 nogood、telemetry 记录 fallback、行为等同现状。
4. **多 commodity**:双 commodity 同时 disconnected 时各自有割(或各自回退),沿用第二轮加的双 commodity 测试场景。
5. 既有 `src/tests/test_p0_certified_soundness_fixes.py` 全部 7 条必须保持通过。

## 自验环境与已知基线

- 先跑 `python scripts/check_p1_2_proof_obligations.py`(应 pass:8 obligations anchored)。
- `python -m pytest -q --randomly-dont-reset-seed src/tests/test_p0_certified_soundness_fixes.py` 基线 **7 passed**。
- `data/preprocessed/candidate_placements.json`(53.6MB)外置不在包内,**不准伪造**。已知环境性失败(非 finding):test_binding 10 ERROR / test_regression 5 / test_routing 3 / test_master 1 / test_preprocess_golden 1;其余约 2840 应过。
- 你沙盒跑不了全量,但必须:逐条 regression 实跑通过 + `py_compile` 改动文件 + 针对 `src/models/routing_subproblem.py` 跑 ruff。

## 交付物

- unified diff 补丁(基于包内原文件;**注意补丁路径前缀要能在仓库根 `git apply -p1` 直接落,测试文件在 `src/tests/` 下**)。
- `FIXES.md`:割的数学有效性完整论证(上面第 4/5 点展开)、自检三项的独立性论证、回退语义、对 env-off 零影响论证、三件套清单。
- 修前/修后 probe 输出(窄走廊场景:nogood-only 的 rejected 计数 vs cut 路径的收敛行为)。
- **关键论证写在回复正文**,不要只塞附件。

## 范围边界

- 不动 binding / master / benders_loop 的逻辑(它们消费 routing 的字符串状态,接口不变)。
- 不做第二步(flow 一等编码)——那是 P1.3B 的事,FIXES 里可以留一段"本割基础设施如何被第二步复用"的说明但不实现。
- P1.3B `step_8_apply_to_master` 仍是禁区。

包 sha256:`264e0583817801345f90dbf5dafa3155c292815c5e67e323d98145b07be10d35`
