# 终末地 IndustrialPlanner 精确求解器 — 算法 soundness 独立审查 · 角度 A:Benders/LBBD 分解

## 任务性质（新会话零历史，独立审查）

附件是完整项目最新快照 zip（zip 内 `project/` 为仓库根；**ZIP_LZMA 压缩，Linux `unzip` 不支持，用 `python -m zipfile -e <附件名>.zip .` 解包**）。Python 依赖 wheels 已在本 Project 文件区，沙盒 Python 3.13，`pip install --no-index --find-links <wheels目录> -r requirements.txt` 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器（目标 `max_lex(area, min_side)`：先最大化空矩形面积，再最大化最小边长；266 个强制设施实例必须全部放下；OR-Tools CP-SAT 9.15 + Benders/LBBD 分解 master→binding→routing→flow）。项目宪法在 `PROJECT_LOCK.md`；certified_exact 与 exploratory 严格分离；fail-closed 是默认姿态。

## 本轮方向（关键：与既往十九轮正交）

项目此前的 V80–V99 共十九轮外审，**全部**在审"公开面 / 交付工件能不能被伪造成看起来 CERTIFIED"（反伪造外壳），已逐字段穷举、收敛到极窄的壳层缝。**本轮请完全放下"伪造交付工件"这条线**：假定交付工件诚实、没有人篡改 evidence / env / state、求解器在认真求解。

你唯一要问的是——**求解器的算法、数学推导、模型编码本身对不对**。即：就算没有任何人作弊，这个求解器自己算出来的"CERTIFIED 最优解 / INFEASIBLE 剪枝"在数学上站得住脚吗？一个**诚实但算错**的求解器，会不会输出一个其实不是全局最优的解却标 CERTIFIED，或把一个其实可行的布局剪成 INFEASIBLE？

## 本轮焦点：Benders/LBBD 分解作为精确算法的 soundness 与完备性

关键文件：`src/search/benders_loop.py`（LBBD 主循环）、`src/search/outer_search.py`（外层候选循环 + frontier）、`src/models/master_model.py` 与 `src/models/exact_coordinate_master.py`（CP-SAT placement master + ghost rectangle 强制）、`src/cuts/lifecycle.py`（cut 生命周期，注意 `step_8_apply_to_master` 是**未集成**边界，不审它）。

把整个 master→subproblem→cut→重解 的循环当成一个**声称精确（exact）**的算法来审，逐一质疑：

1. **master 是真松弛吗**：master 放松了哪些约束？这个放松是否保证 master 最优 ≥ 真最优（对最大化目标）？有没有 master 把本应可行的布局判死、或把不可行布局当可行从而误导外层搜索的情形？
2. **Benders cut 是 valid 的吗（命脉）**：subproblem 返回 INFEASIBLE 时加给 master 的 nogood / cut，是否**只排除真不可行的 master 解、绝不误杀任何可行解**？cut 在 instance 内 lifting / 泛化之后，覆盖范围有没有超出它实际证明的不可行区域（over-cutting → certified false negative，即把可行更优解切掉）？
3. **子问题 INFEASIBLE ⇔ master 解物理不可行吗**：binding / routing / flow 任一报 INFEASIBLE，是否真等价于"这个 master 布局物理上无法实现"？会不会因子问题模型过紧而误报，导致可行布局被错误剪枝？
4. **收敛 / 最优终止判据对吗**：循环在什么条件下宣布"当前最优 = 全局最优"？master 下界与已找到最优解之间的 gap 闭合逻辑是否正确？会不会过早终止、漏掉更优候选？time-budget 用尽时的 partial 状态有没有被错当成完整证明？
5. **outer search + max_lex 驱动会漏候选吗**：ghost rectangle 强制 + 从大 area 往下扫的 frontier，如何保证不会跳过某个 `(area, min_side)` 字典序更优但未被枚举的候选？支配剪枝（dominance pruning）的判据是否严格正确？

## 已知背景：别重复报这 8 点，要挖更深一层

我们刚做过一轮内部系统调研，把 terminal validator（收尾验证器）"信求解器标签、没独立重算"的点列全了，共 8 处。**本轮你不要报"验证器没验 X"——那是已知的 proof-carrying certificate（future work）该补的事**；你要问的是更深一层：**求解器在 X 这件事上到底算得对不对**。8 点（与角度 A 最相关的是 1/2/6）：

1. 每候选的 CERTIFIED/INFEASIBLE 状态标签被原样信任，全 frontier"已穷尽更优候选"的论证完全建立在这些未独立重验的标签上（最大缺口）；
2. persisted cut 只做结构解析，不真重放铸造它的 CP-SAT；
3. 电力验证只查几何集合覆盖，无容量 / 连通 / 电网模型；
4. optional 设施只查数量下界，缺"够不够支撑路由"的证明；
5. 终端验证完全不碰 belt 路由；
6. 跨布局全局最优性 = 单布局最大性 + "搜索自报已穷尽"；
7. final_result / stop_reason 是反伪造形状门，不是证明；
8. 一切归约到"4 个 sha256 锁定的 JSON 工件是对的"这条公理。

**本轮重心**：在 Benders/LBBD 分解角度内，挖出这 8 点**之外**的算法 soundness 缝；或者深入第 1/2/6 点，论证求解器在那里**算错了**——给出会导致错误 CERTIFIED 或错误 INFEASIBLE 的具体机制与（哪怕是构造思路层面的）反例。

## 这类 finding 怎么坐实

**诚实预期**：这类"算法本身对不对"的缝，往往难用一个 5 分钟 probe 当场演示（要构造一个求解器真的误判的实例，本身可能和原问题一样难）。所以本轮**接受严谨的数学论证 + 反例构造思路**作为 finding 证据，不强求可运行 probe；但论证必须具体到 `file:line` 和确切的约束 / 推导步骤，指出"这一步在什么输入下会漏掉可行解 / 误判不可行 / 漏报更优解"。能给可运行 probe 更好。空泛的"可能不严谨 / 建议加强"不算 finding。

## 自验环境与已知基线

- 先跑 `python scripts/check_p1_2_proof_obligations.py`（应 pass）。
- `data/preprocessed/candidate_placements.json`（53.6MB）刻意外置不在包内，**不准伪造它**。它导致的已知环境性失败不是 finding：全量下 `test_binding` 10 ERROR、`test_regression` 5 FAILED、`test_routing` 3、`test_master` 1、`test_preprocess_golden` 1；其余约 2833 个测试应全过。

## 交付物

- `REVIEW.md`：逐条 finding——严重度分级（**algorithmic/soundness** vs 工程 vs 文档）、`file:line` 定位、数学论证或反例构造、建议修法；有把握的附 unified diff 补丁（基于包内原文件）+ 配套 regression 测试。
- **所有 finding 的完整论证直接写在回复正文里**（不要只塞进附件——附件通道可能抓不全）。
- 如果全审后认为 Benders/LBBD 分解在你审的范围内是 sound 的，明确写"**本轮零 soundness finding**" + 列出你实际审过的模块 / 约束 / 推导与论证依据（owner 在仓库外手动维护连续清零计数，这句是计数输入）。不要硬凑低价值 finding，也不要因"已审多轮"就默认干净——历史上 V82 的半域枚举洞、V83 的几何缺陷正是在已审多轮的核心模块里找到的。

## 范围边界

- P1.3B（`src/cuts/lifecycle.py::step_8_apply_to_master` 的真 master 集成）被 owner gate 阻塞未开，**不审未集成的未来工作**。
- exploratory 路径不审。
- proof-carrying certificate（让每个候选自带可独立重验证明）是已知 future work，**不要把"缺 proof-carrying / 缺独立重验"当 finding**——本轮问的是现有求解器**算得对不对**，不是"它有没有附带证明"。
