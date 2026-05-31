# 终末地 exact solver — Phase 1.2 spike close gate 审查

我有一个项目想请你独立审一个具体的 gate。先把背景和我真正想知道的讲清楚，你别被我带偏，也别因为客气就给我盖章。

## 项目是什么

70×70 网格上 266 个固定设施的 certified-exact 最大空矩形求解器（游戏《明日方舟：终末地》的工业规划器）。目标 `max_lex(area, min_side)`，用 OR-Tools 9.15 CP-SAT + LBBD（Benders）分解。附件 zip 是项目快照（`project/` 是主线代码+数据，`code_context/` 是 review-only 的旁支代码镜像）。

## 我要你审的 gate

项目里有一道工序叫 "prod-scale spike"，目的是在真正动手做下一阶段（P1.3A，真 master 集成 + 多轮 LBBD 收敛）之前，先验证 cut 在生产规模下的 **sizing**（build/translate/solve 耗时、proto 大小、RSS）扛不扛得住。这个 spike 自己的结论是 **GO_WITH_MINOR**，而且明确只认 sizing 这一层，把收敛性和对抗鲁棒性 defer 到下一阶段。

包里 README 记录了这个 spike 此前已经过 8 轮独立审查、逐轮修 finding 修到现在这个状态。**你不用、也别假设你看过前面几轮——就当第一次看，独立判断现在。** 前几轮的 finding 和修复都在 git 历史和 README 里，是给你 source-check 的事实素材，不是要你接谁的话往下说。

我想知道的就一件事：**以现在的状态，这道 spike close gate 还有没有未闭的 soundness / 完整性 / scoping finding？** 有就指出来、给可复现的反例；没有就直说没有。欢迎你挑战，包括挑战 "GO_WITH_MINOR 这个结论本身是不是 scope 划得过宽或过窄"。别因为前面 8 轮都在收尾就觉得这轮必须给 GO。

## 真正的瓶颈（免得你往错方向使劲）

项目的根本难点不是这个 spike，是：master CP-SAT 在 prod 规模 single-solve 解不动——这是 latency-bound 工作负载（~280K pose registry，two-watched-literal 随机指针追逐，working set 溢出 L3）。项目试过 27 条求解 paradigm，绝大多数 NOT_GO，死因分类在 `project/docs/项目说明/03_paradigm_death_baseline.md` 和 `project/docs/research/` 下。当前主线是 cut-family LBBD 重设计：9 个 cut family（F1–F9）当 Benders cut 喂回 master 收紧搜索。这个 spike 就是在验这些 cut 的工程可行性。

## 已经死掉的方向（别重新推荐）

这些都实测/推理穷尽过，verdict 死。除非你能指出之前的 NOT_GO 论证里有**具体技术漏洞**（见最后一节的形式化要求），否则别 resurrect：

- 单机扩 RAM 路径：augmented master / GOC / PGW 全在 25–32 GB 上界，机器 48 GB，撑不住。
- 重写求解器：HiGHS 等 LP-MIP 对这种 dense linear constraint 不适合（实测 42 GB > 现 OR-Tools 30 GB）。
- 让 pose-bool master 自己持有 port direction / pole selection / belt routing 的决策：6 条 paradigm 撞同一面墙（master 表达力 fundamental 不够），全死。

## 重点看这几层（不限于此）

1. **假证据 / soundness（最高价值）**：spike 的 sizing 数字能不能被伪造或误导？具体说——旁支的 `toy_translator` 在 cert malformed（坏 base64 / 非 dict root / 缺字段）时，是不是真的 fail-closed（返回空、跳过），而不是 fallback 合成几条 literal 把数蒙混过去？A3 oracle-emit fixture 报的 "0 unsound" 立不立得住？
2. **主线 src 的 soundness 守卫**：F7/F8 这两个 cut family 的 validator，是不是真的把 cert 里的 `facility_cells` 绑回了真实 pose registry？（不绑的话，可以伪造一个坐标骗过 validator → 生成 false-positive cut → 把本该可行的 pose 剪掉，破坏 FP=0。这是前几轮的 BLOCKER 修复点，我想确认它真补上了、且锁住了。）
3. **完整性**：spike 是否真覆盖了它声称覆盖的那几项 sizing（真 prod registry 建 master var / 真 cut body 分布 / build·proto·RSS·solve 实测 / active-cut filter / 一个 feasible case 避免 INFEASIBLE 早停掩盖成本）？
4. **scoping 诚实度**：GO_WITH_MINOR 把收敛性和对抗鲁棒性 defer 到下一阶段——这个 defer 是诚实的，还是把本该 block 这道 gate 的东西藏进了 "下一阶段"？（前几轮最大的争议就是 "某个 cut family 的 fixture gap 能不能用 'convergence later' 豁免"，结论是不能，所以单独做了一个 special-case phase 补齐。我想知道还有没有同类被偷偷豁免的。）

## 我面前的选择

spike close 之后下一步是 P1.3A 主体。我卡在：能不能拿这个 GO_WITH_MINOR 当进入 P1.3A 的依据。

- A：v22 状态干净，spike close 成立，进 P1.3A。
- B：还有未闭 finding（请指出 + 反例），修完再进。
- C：GO_WITH_MINOR 的 scope 本身划错了（过宽/过窄），这道 gate 要重定义。

我不预设你选哪个。

## 唯一的硬性输出约束：不可达断言要形式化

如果你的结论里出现任何 "X 不可达 / 必然失败 / 这道 gate 该 NOT_GO 因为 P1.3A 根本走不通" 这类断言，请把它**形式化**：给 complexity reduction、proof-system lower bound、resource inequality，或者 cite 文献。不接受 "我觉得 / 直觉 / 大概率"。

除此之外，finding 怎么报、报几条、什么格式，你自便——我不规定 verdict label，也不规定字数。

## 包里怎么核 / 怎么复现

> 解包后得到 `_phase1_2_pkg_v22/` 目录，主线代码在它下面的 `project/`，以下路径都相对 `_phase1_2_pkg_v22/`（即 `cd _phase1_2_pkg_v22` 后用）。

- spike 自我结论 + G 标准表 + 5 项 Layer-2 defer：`project/docs/research/prod_scale_spike_design_20260525/spike_run_20260526/verdict.md`
- spike 实现代码镜像（review-only，**不是** master 合并目标）：`project/code_context/spike/`（含 `toy_translator.py` 和它的 9-case fail-closed 自测 `test_toy_translator_f3_malformed.py`、runner、各 lib；说明文档在 `project/code_context/README.md`）
- 主线 soundness 守卫：`project/src/cuts/families/power_hitting_set.py` 和 `power_grid_reach.py` 里的 `_validate_facility_cells_match_pose_registry`
- 对应回归测试：`project/src/tests/cuts/`（含两个 `test_validator_unsound_when_facility_cells_do_not_match_pose_registry` 和 `test_oracle_scope_digest.py`）
- 原始 telemetry：`project/data/cuts/spike/*.jsonl`
- 每个 cut family 的 per-commit 数学 cross-check 存档：`project/docs/research/` 下各 `*_gemini_round*` / `cross_check/`
- 跑测试：`cd project && python -m pytest src/tests/cuts/ -q`（实测数见包内 README）；spike 自测跑法见 `project/code_context/README.md`
