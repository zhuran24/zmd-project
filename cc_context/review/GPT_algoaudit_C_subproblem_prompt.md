# 终末地 IndustrialPlanner 精确求解器 — 算法 soundness 独立审查 · 角度 C:子问题建模 + cut family oracle 数学

## 任务性质（新会话零历史，独立审查）

附件是完整项目最新快照 zip（zip 内 `project/` 为仓库根；**ZIP_LZMA 压缩，Linux `unzip` 不支持，用 `python -m zipfile -e <附件名>.zip .` 解包**）。Python 依赖 wheels 已在本 Project 文件区，沙盒 Python 3.13，`pip install --no-index --find-links <wheels目录> -r requirements.txt` 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器（目标 `max_lex(area, min_side)`：先最大化空矩形面积，再最大化最小边长；266 个强制设施实例必须全部放下；OR-Tools CP-SAT 9.15 + Benders/LBBD 分解 master→binding→routing→flow）。项目宪法在 `PROJECT_LOCK.md`；certified_exact 与 exploratory 严格分离；fail-closed 是默认姿态。

## 本轮方向（关键：与既往十九轮正交）

项目此前的 V80–V99 共十九轮外审，**全部**在审"公开面 / 交付工件能不能被伪造成看起来 CERTIFIED"（反伪造外壳），已逐字段穷举、收敛到极窄的壳层缝。**本轮请完全放下"伪造交付工件"这条线**：假定交付工件诚实、没有人篡改、求解器在认真求解。

你唯一要问的是——**子问题模型与 cut family oracle 的数学本身对不对**。即：binding / routing / flow 子问题，是否忠实编码了"货物能不能真运起来"的物理约束？F1–F9 cut family 的 oracle 声称"这个区域装不下"——这些数学命题成立吗？一个**过紧的子问题**或**错误的 oracle** 会把可行布局误判成不可行（certified false negative → 漏掉真正的最优解）。

## 本轮焦点：子问题物理忠实度 + cut family oracle 数学命题

关键文件：`src/models/binding_subproblem.py`（端口绑定）、`src/models/routing_subproblem.py`（网格 belt 路由）、`src/models/flow_subproblem.py`（多商品流诊断）、`src/cuts/`（F1–F9 families + oracles + `assumptions/verifiers.py`）、`src/cuts/lifecycle.py`（9 步管线，`step_8_apply_to_master` 是**未集成**边界）。

逐一质疑：

1. **子问题模型忠实度（过紧风险最危险）**：端口绑定、网格 belt 路由、多商品流分别编码了哪些物理约束？有没有把**本应可行的运输判死**（约束过紧 → 误报 INFEASIBLE → master 收到一个 valid 的 nogood 把可行布局剪掉 → certified false negative）？反过来有没有过松漏检的情形？
2. **flow diagnostic-only 边界**：flow subproblem 标为 diagnostic（不出 cut）。这个边界是否影响分解 soundness？是否存在"只有 flow 能发现的不可行"被漏掉、导致一个真不可行的布局被当可行接受？或反之，flow 的诊断结论有没有被别处误当作硬约束？
3. **cut family oracle 数学命题成立吗**：region capacity / density envelope / hall packing（set-packing / 区域容量 / Hall 条件）等 oracle 声称"这个区域装不下 X 个设施 / 这组实例无法共存"——这些数学命题在它们的前提下**严格成立**吗？有没有 oracle 在某些输入下给出错误的"装不下"（→ 误剪可行解）？特别审 Hall-type 与 capacity-type oracle 的计数 / 容量推导有没有 off-by-one 或前提疏漏。
4. **within-instance lifting soundness + 跨 instance 禁令**：cut 在 instance 内的 lifting / 泛化是否 sound（lifting 后排除的区域是否仍全部真不可行）？PROJECT_LOCK 禁止跨 instance lifting——审这个禁令在数学上是否**真的必要**（跨 instance lifting 确实会 unsound 吗，给出会出错的情形），还是过度保守？
5. **F9 tight-K quarantine 的判据**：F9（tight-K）被 quarantine，解封条件是 Phase 1.5+ 给 cert 加 area-capacity proof-carrying 字段。审：tight F9 当初被判 unsound 的论证（在 `PROJECT_LOCK.md` §3A / `docs/项目说明` / 相关 research 文档里）**成立吗**？它真的会误剪可行解，还是被误判而其实 sound？

## 已知背景：别重复报这 8 点，要挖更深一层

我们刚做过一轮内部系统调研，把 terminal validator「信求解器标签、没独立重算」的点列全了，共 8 处。**本轮你不要报「验证器没验 X」——那是已知的 proof-carrying certificate（future work）该补的事**；你要问的是更深一层：**子问题 / oracle 在 X 这件事上算得对不对**。8 点（与角度 C 最相关的是 2/3/4/5）：

1. 每候选状态标签被原样信任，frontier 穷尽论证建立在未重验标签上；
2. persisted cut 只结构解析不真重放；
3. 电力验证只查几何集合覆盖，无容量 / 连通 / 电网模型；
4. optional 设施只查数量下界，缺"够不够支撑路由"的证明；
5. 终端验证完全不碰 belt 路由；
6. 跨布局全局最优性 = 单布局最大性 + 自报穷尽；
7. final_result / stop_reason 是形状门；
8. 归约到 4 个冻结工件公理。

**本轮重心**：在子问题 / cut oracle 角度内，挖出这 8 点**之外**的数学 soundness 缝；或深入第 2/3/4/5 点，论证子问题或 oracle **算错了**——给出会把可行布局误判 INFEASIBLE、或把不可行布局误判可行的具体机制与构造思路。**子问题过紧（误杀可行解）是本角度最危险的 soundness 缺陷，优先找它。**

## 这类 finding 怎么坐实

**诚实预期**：子问题 / oracle 的缝有时能用小 probe 演示（构造一个手算可行的小布局，喂给子问题看它误报 INFEASIBLE；或构造一个 oracle 应判"装得下"的实例看它误判"装不下"），有时只能数学论证。本轮**接受严谨论证 + 反例构造思路**，但必须具体到 `file:line` 和确切约束 / 推导步骤。oracle 数学命题类**优先给反例构造**（一个该命题失效的具体实例）。空泛的「建议加强」不算 finding。

## 自验环境与已知基线

- 先跑 `python scripts/check_p1_2_proof_obligations.py`（应 pass）。
- `data/preprocessed/candidate_placements.json`（53.6MB）刻意外置不在包内，**不准伪造它**。它导致的已知环境性失败不是 finding：`test_binding` 10 ERROR、`test_regression` 5、`test_routing` 3、`test_master` 1、`test_preprocess_golden` 1；其余约 2833 测试应全过。binding/routing 测试因此受影响，审代码逻辑为主、不依赖这些测试通过。

## 交付物

- `REVIEW.md`：逐条 finding——严重度（**algorithmic/soundness** vs 工程 vs 文档）、`file:line`、论证 / 反例 / probe、建议修法；有把握的附 unified diff + regression。
- **所有 finding 完整论证直接写在回复正文里**（不要只塞附件）。
- 若审完认为子问题模型与 cut oracle 在你审范围内 sound，明确写"**本轮零 soundness finding**" + 列实际审过的模块 / oracle / 推导与论证依据。不硬凑、也不因"已审多轮"默认干净。

## 范围边界

- P1.3B（`step_8_apply_to_master` 真 master 集成）被 owner gate 阻塞未开，**不审**。9 个 cut family 数学曾经历 v28 等专项外审，可以审但请聚焦"oracle 命题是否成立 + 子问题是否过紧"这条 soundness 主线，不重复纯工程审查。
- exploratory 路径不审。
- proof-carrying certificate 是已知 future work，**不要把「缺独立重验 / 缺附带证明」当 finding**——本轮问的是现有子问题 / oracle **算得对不对**。
