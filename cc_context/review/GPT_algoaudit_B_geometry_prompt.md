# 终末地 IndustrialPlanner 精确求解器 — 算法 soundness 独立审查 · 角度 B:几何 / master CP-SAT 建模忠实度

## 任务性质（新会话零历史，独立审查）

附件是完整项目最新快照 zip（zip 内 `project/` 为仓库根；**ZIP_LZMA 压缩，Linux `unzip` 不支持，用 `python -m zipfile -e <附件名>.zip .` 解包**）。Python 依赖 wheels 已在本 Project 文件区，沙盒 Python 3.13，`pip install --no-index --find-links <wheels目录> -r requirements.txt` 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器（目标 `max_lex(area, min_side)`：先最大化空矩形面积，再最大化最小边长；266 个强制设施实例必须全部放下；OR-Tools CP-SAT 9.15 + Benders/LBBD 分解 master→binding→routing→flow）。项目宪法在 `PROJECT_LOCK.md`；certified_exact 与 exploratory 严格分离；fail-closed 是默认姿态。

## 本轮方向（关键：与既往十九轮正交）

项目此前的 V80–V99 共十九轮外审，**全部**在审"公开面 / 交付工件能不能被伪造成看起来 CERTIFIED"（反伪造外壳），已逐字段穷举、收敛到极窄的壳层缝。**本轮请完全放下"伪造交付工件"这条线**：假定交付工件诚实、没有人篡改、求解器在认真求解。

你唯一要问的是——**CP-SAT 模型有没有正确、完整地把真实物理问题编码进去**。即：就算求解器把模型解到了最优，那个模型本身是不是真实问题的忠实表达？一个**编码错了的模型**会让求解器输出一个对错误问题最优、但对真实问题并非最优（或并非可行）的解，却照样标 CERTIFIED。

## 本轮焦点：几何与 master CP-SAT 模型是否忠实、完整地编码了物理问题

关键文件：`src/models/master_model.py`、`src/models/exact_coordinate_master.py`、`src/models/pose_bool_exact_master.py`、候选域生成相关代码与 `data/preprocessed/candidate_placements.json` 的契约、`src/search/certified_frontier.py`（候选域重生成 + 防切片）、`src/search/exact_campaign.py` 中的几何重算（empty-rectangle witness scan、occupancy 重铺）。

逐一质疑 CP-SAT 模型与真实物理的对应：

1. **max empty rectangle 编码**：「空矩形」在模型里怎么表达？它和「266 个设施都放下后剩余的连续空白区域里的轴对齐矩形」是否精确对应？有没有把被设施占用的格当空、或把空格当占用？ghost rectangle 的强制方式会不会引入或排除掉某些合法空矩形？
2. **no-overlap 与设施 footprint**：每个设施的占格形状、朝向、锚点偏移是否完整正确？266 个强制实例之间的 no-overlap 约束有没有遗漏的重叠情形（例如非矩形 footprint、跨格边界、端口外伸格）？
3. **pose 域有向性完备**：每个设施的朝向域（orientation / port_mode）是否两个方向 `(w,h)` 和 `(h,w)` 都覆盖？历史上 V81–V82 修过半域枚举 bug（只枚举了一半朝向）。现在候选域是否**真完备、无遗漏 pose**？请实际从域生成代码 / candidate_placements 契约核对，而不是看注释。
4. **min_side admissibility 与 max_lex 目标编码**：`min_side ≥ 6` 是 admissibility（准入条件）不是 tie-break；`max_lex(area, min_side)` 的「area 优先、min_side 次级」在 CP-SAT 里怎么编码？字典序是否**精确**实现（用加权和 / 大 M 近似会不会在边界情形选错？area 与 min_side 的取值范围是否保证加权不串位）？
5. **empty-rect witness 的「最大性」范围与正确性**：终端验证暴力扫所有 `(w,h)` 证明「这个布局下没有更大空矩形」——它只证**单布局**最大、不证全局（这是已知边界）。请审：单布局最大性的几何重算本身有没有 off-by-one、边界条件、前缀和 / 扫描覆盖的漏洞？会不会因为重算逻辑的 bug 而漏判一个其实更大的空矩形（→ 错误地确认一个非最优解为最优）？

## 已知背景：别重复报这 8 点，要挖更深一层

我们刚做过一轮内部系统调研，把 terminal validator「信求解器标签、没独立重算」的点列全了，共 8 处。**本轮你不要报「验证器没验 X」——那是已知的 proof-carrying certificate（future work）该补的事**；你要问的是更深一层：**模型 / 几何重算在 X 这件事上编码 / 计算得对不对**。8 点（与角度 B 最相关的是 1/6）：

1. 每候选状态标签被原样信任，frontier 穷尽论证建立在未重验标签上（最大缺口）；
2. persisted cut 只结构解析不真重放；
3. 电力验证只查几何覆盖；
4. optional 只查数量下界；
5. 终端不碰 belt 路由；
6. 跨布局全局最优性 = 单布局最大性 + 自报穷尽；
7. final_result / stop_reason 是形状门；
8. 归约到 4 个冻结工件公理。

**本轮重心**：在几何 / master 建模角度内，挖出这 8 点**之外**的编码 / 几何 soundness 缝；或深入第 1/6 点，论证模型或几何重算**编码错了 / 算错了**，给出会让一个非最优或不可行布局被标 CERTIFIED 的具体机制与构造思路。

## 这类 finding 怎么坐实

**诚实预期**：建模 / 几何缝有时能用小 probe 演示（构造一个布局，让模型的约束与手算物理结果不符），有时只能数学论证。本轮**接受严谨论证 + 反例构造思路**作为证据，但必须具体到 `file:line` 和确切的约束 / 几何步骤。几何类缝**优先尝试给可运行 probe**（构造小输入跑模型 / 跑 witness scan，对比手算）。空泛的「建议加强」不算 finding。

## 自验环境与已知基线

- 先跑 `python scripts/check_p1_2_proof_obligations.py`（应 pass）。
- `data/preprocessed/candidate_placements.json`（53.6MB）刻意外置不在包内，**不准伪造它**。它导致的已知环境性失败不是 finding：`test_binding` 10 ERROR、`test_regression` 5、`test_routing` 3、`test_master` 1、`test_preprocess_golden` 1；其余约 2833 测试应全过。

## 交付物

- `REVIEW.md`：逐条 finding——严重度（**algorithmic/soundness** vs 工程 vs 文档）、`file:line`、论证 / probe、建议修法；有把握的附 unified diff + regression。
- **所有 finding 完整论证直接写在回复正文里**（不要只塞附件）。
- 若审完认为几何 / master 建模在你审范围内忠实正确，明确写"**本轮零 soundness finding**" + 列实际审过的模块 / 约束与论证依据。不硬凑、也不因"已审多轮"默认干净（V82 半域洞、V83 几何缺陷都在已审核心里）。

## 范围边界

- P1.3B（`step_8_apply_to_master` 真 master 集成）被 owner gate 阻塞未开，**不审**。
- exploratory 路径不审。
- proof-carrying certificate 是已知 future work，**不要把「缺独立重验 / 缺附带证明」当 finding**——本轮问的是现有模型**编码得对不对**。
