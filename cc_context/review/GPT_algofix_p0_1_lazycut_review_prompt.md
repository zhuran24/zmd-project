# 终末地 IndustrialPlanner 精确求解器 — P0-1 lazy connectivity cut 实现审查(零 finding 确认轮)

## 任务性质(新会话零历史,独立对抗审查)

附件是完整项目快照 zip(zip 内 `project/` 为仓库根;ZIP_LZMA,用 `python -m zipfile -e <附件>.zip .` 解包)。依赖 wheels 在本 Project 文件区,沙盒 Python 3.13,离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。

本包刚落地了 P0-1 最终修复第一步:**routing guard 拒绝循环里的 lazy source-side connectivity cut**。你的任务:对抗式审查这个实现的 soundness——重点是**割的有效性**(任何一条 invalid 割都会静默剪掉真可行解 = false INFEASIBLE = 漏掉真最优,这是本实现唯一的致命失败模式)。若审完确认无残留缺陷,明确报零——这是 owner 判定该步"完成"的输入。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器(目标 `max_lex(area, min_side)`,266 强制设施,OR-Tools CP-SAT 9.15 + Benders/LBBD 分解 master→binding→routing→flow)。宪法 `PROJECT_LOCK.md`;fail-closed 默认姿态。

## 实现概要(实现方自述在包内 `cc_context/review/algofix_p0_1_lazycut_FIXES_20260612.md`,规格在 `specs/09_exact_grid_routing_subproblem.md` §9.8)

背景:routing CP-SAT 只有局部 successor/predecessor 约束,FEASIBLE 不蕴含全局连通;P0-1 修复加了 connectivity guard(接受 incumbent 前重建 selected 图验 source→sink 可达,不可达加 selected-positive nogood 重解,预算尽 TIMEOUT)。nogood 一刀一个,大域下有指数级枚举 → 高 UNKNOWN 风险。

本步改动(全部在 `src/models/routing_subproblem.py`):guard 拒绝 commodity k 时,先尝试生成割:
- `W` = 从 k 的 selected source-front states 出发、只沿 incumbent selected 图可达的闭包;
- `X` = 「W 外第一节点」候选集:能直接接收 k 的 source front 输出但 ∉ W 的候选 state,∪ 存在 guard 同构 arc `u→v`(u∈W, v∉W)的候选 state v;
- 加 `sum(r_var[s] for s in X) >= 1` 重解。
- **三项 fail-closed 自检**(独立重算,不信生成过程):① 全部 source front 在 W 有 selected source-state 且无 sink-front 候选 state 落入 W;② 在全候选图里删除 X 后 source-front 候选出发 BFS 不可达任何 sink-front 候选(X 是完整分离边界的证书);③ incumbent selected ∩ X = ∅(割真排除当前 incumbent)。任一失败 → 回退原 selected-positive nogood + telemetry 记录原因。
- guard 最终验收边界 / TIMEOUT 语义 / `extract_routes()` 双门未动;无新 env;telemetry 加 cuts_added / cut_sizes / fallback_nogoods。

有效性论证(声称):任何真实可行 routing 必须把 k 从 source front 运到 sink front;路径第一颗 source-接收 state 若 ∉ W 则它 ∈ X(定义 1);若 ∈ W,因 sink 候选不在 W,路径必有首次离开 W 的跨越 u→v,v ∈ X(定义 2)。故 `sum(X)≥1` 无条件有效。

## 审查重点(按优先级)

### Q1 割的有效性——能否构造 invalid 割(最重要)
- **X 的两条定义是否真覆盖"所有可能的第一颗 W 外 state"**?着重攻:
  - source front 的接收语义(output port 外侧格 + DIR_OPP 方向)与 `_add_port_adherence()` / guard 重建是否严格同构——有没有一种合法的"路径起点"形态没被定义 1 捕获(比如 incumbent 的 W 含部分 selected source-state、而真解用了**另一个** source front 的不同接收 state)?
  - 定义 2 的 arc 语义(flow_out → 邻格 flow_in=DIR_OPP,同 commodity)与 routing 模型真实约束是否同构——双层(ground/elevated bridge)、splitter/merger 多入多出、sink-front terminal 不外扩,这些点位上 potential 图会不会比模型可行集**窄**(窄 = X 不完整但自检 BFS 也用同一窄图 → 自检过但割 invalid 的**同构盲区**)?这是最隐蔽的攻击面:**自检②与生成用同一套 arc 语义,若该语义共同遗漏了模型里实际可行的某种跨越方式,自检不会兜住**。请独立从 CP-SAT 约束(`_add_continuity_constraints`/`_add_successor_constraints`/`_add_predecessor_constraints`/`_add_port_adherence`)出发核对 arc 语义的完备性。
  - W 的构造:「selected source-front states 出发」——若某 source front 在 incumbent 里**没有** selected 接收 state(端口约束 exact-one 应该保证有,但请核对),W 构造和自检①的行为是否仍 sound?
- 多 commodity:每个失败 commodity 各自生成割——commodity 间共享 cell 容量(AddAtMostOne per cell-layer),割只看本 commodity 的 state 子图是否引入跨 commodity 的有效性问题?(应该不会——割是纯本 commodity 必要条件——但请确认 X 的 state 集没混入他 commodity 的 var。)

### Q2 自检的独立性与 fail-closed 完备性
- 三项自检是否真"独立重算"(不复用生成过程的中间数据结构,否则生成 bug 会自我豁免)?
- 自检失败路径是否全部正确回退 nogood(没有静默吞掉拒绝、没有既不加割也不加 nogood 就重解的死循环)?
- 重解循环的预算/终止:加割后重解仍在同一 time budget 内?INFEASIBLE/TIMEOUT 语义与改动前一致?

### Q3 回归测试判别力
新增的 lazy cut 测试(收敛/完整性保真/自检回退/多 commodity)是否真判别?完整性保真测试(先拒不连通 incumbent、加割后仍找到真可行解)的场景是否足够代表性,有没有"割恰好不碰真解路径"的侥幸?

### Q4 工程面
ruff/mypy 雷、死代码、telemetry 字段准确性、对 benders_loop 消费接口零影响、env-off 行为不变。

## 明确不要报的

- proof-carrying certificate(future work)、P1.3B flow 一等编码(已排期的第二步)、guard 本身的完整性代价(已知,本步正是缓解它)。
- 上几轮已 refuted 的误判(52-port 满占 / port 单次偏移 / pose-bool guard 拦截)。
- nogood 是 selected-positive subset 形状(已知已文档化)。

## 自验环境与已知基线

- `python scripts/check_p1_2_proof_obligations.py` 应 pass(8 obligations anchored)。
- `python -m pytest -q --randomly-dont-reset-seed src/tests/test_p0_certified_soundness_fixes.py` 基线 **10 passed**。
- `data/preprocessed/candidate_placements.json`(53.6MB)外置不在包内,**不准伪造**。已知环境性失败(非 finding):test_binding 10 ERROR / test_regression 5 / test_routing 3 / test_master 1 / test_preprocess_golden 1;其余约 2843 应过。
- finding 必须带可复现 probe(构造让割误杀真可行解的实例 = 金标准)或严谨数学论证(具体到 file:line);实证推翻了你的怀疑就不要报。

## 交付物

- `REVIEW.md`:逐条 finding(severity / file:line / probe 或论证 / 修法),有把握附 unified diff + regression;**关键论证写在回复正文**。
- **若审完确认实现 sound,明确写"本轮零 soundness finding"** + 列实际审过的面、构造过的攻击实例、论证依据。

## 范围边界

- 只审本步改动面(routing_subproblem.py 的割相关代码 + 其与 guard/solve 循环的交互)与其测试;P0 修复批次其余部分已经两轮外审收口,非重点。
- P1.3B `step_8_apply_to_master` 禁区;exploratory 不审。

包 sha256:`9e21ca319186e64786627a1a9ed77a507959d6113bbd38c136aa8162a7ee96ac`
