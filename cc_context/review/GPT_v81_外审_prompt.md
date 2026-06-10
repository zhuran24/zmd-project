# 终末地 IndustrialPlanner 精确求解器 — certified 面独立全审(V81 轮)

## 任务性质

这是一轮**独立对抗审查**。附件 `zmd_v80_impl_full_20260611_single.zip` 是完整项目快照(zip 内 `project/` 为仓库根镜像;**压缩方法 ZIP_LZMA,Linux `unzip` 不支持,用 `python -m zipfile -e zmd_v80_impl_full_20260611_single.zip .` 解包**)。Python 依赖 wheels 已在本 Project 文件区(zmd_deps 包),沙盒 Python 3.13,`pip install --no-index --find-links <wheels目录> -r requirements.txt` 离线安装。

你的目标只有一个:**找出任何能让"非权威路径产出看起来 CERTIFIED 的工件"的路径,或任何 soundness 缺陷**。具体 finding 类别(与包内 `data/review_gates/phase_1_2_spike_close.json` 的 `finding_classes_that_break_manual_clean_review` 一致):unsound cut、certified false negative、proof obligation bypass、fake certified claim、reachable phase-gate false ready。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器(目标 `max_lex(area, min_side)`,266 个强制设施实例,OR-Tools CP-SAT + LBBD 分解)。项目宪法在 `PROJECT_LOCK.md`;certified_exact 与 exploratory 严格分离;fail-closed 是默认姿态。

## 审查起点与历史

当前 review anchor = **`v80_deny_unknown_certified_surface`**。V22→V80 完整 finding 史在包内:`data/review_gates/phase_1_2_spike_close.json` 的 `informational_history` + `docs/research/p1_2_v*.md` 逐轮文档。

V80(最近一轮,刚落地)把 certified 面的防御范式从"枚举已知坏轴"翻转为 **deny-unknown 封闭契约**,三件套:

1. **项目级 admissibility 发布闸**:`rules/canonical_rules.json::globals.empty_rectangle.min_side_admissibility` 成为权威(生产=6);terminal evidence schema v2 绑定该值;超集域跑出的 lex-best 若 sub-admissible,发布面 fail-closed 拒绝(不做"best admissible 回收",论证见 `docs/research/p1_2_v80_deny_unknown_certified_surface.md`)。
2. **terminal evidence 域契约白名单**:`src/search/certified_frontier.py` 的 `candidate_generation` 键全集封闭,未知键/非权威值即拒;v1 evidence 在 resume/import 下 fail-closed。
3. **certified env guard allowlist**:`src/search/benders_loop.py` 的 `_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST`(52 个 operational knob)+ 其余已知 `EXACT_*` 非 canonical 默认值即拒 + **未分类 `EXACT_*` 出现即拒**(`unclassified_exact_env_not_certified`)。

## 建议的审查重点(不限于此,任何威胁 certified 正确性的角度都欢迎)

**A. V80 三件套的对抗审查**(它们是新代码,没经历过独立外审):
- evidence 白名单真的封闭吗?`normalize_candidate_generation_params` / `normalize_terminal_frontier_domain_contract` 等规范化层有没有静默丢键/类型强转旁路?schema v1→v2 的所有消费点都升级了吗(resume、import、inspector、manifest、export)?
- admissibility 闸有没有绕过路径?发布面(`certified_surface.py` / `delivery_manifest.py` / blueprint export / inspector)是否存在不经过该闸的出口?canonical_rules 的 `empty_rectangle` 字段被篡改、缺失、或与 evidence 记录值不一致时,每条路径的行为是什么?
- env allowlist 里 52 个被归 operational 的 knob(`benders_loop.py` 的 frozenset),有没有其实能改变 proof 语义的?判定标准:它能否影响候选域、master 约束、witness 表示、cut 语义、子问题"INFEASIBLE"判定、或 evidence 写出内容——能则是误归类。特别留意 `EXACT_SUBPROBLEM_PARAMS`(可注入任意 CP-SAT 参数)和各类 `*_SECONDS` / `*_MAX_ANCHORS` 预算 knob(预算耗尽路径必须是"不确定→继续/UNKNOWN",绝不能是"当通过/当 INFEASIBLE")。

**B. 已知残留(上轮诚实披露,可作为切入点)**:
- 旧 v1 terminal evidence 一律 fail-closed 不迁移——确认没有任何代码路径还能消费 v1 evidence。
- allowlist 里 `EXACT_GATE_WORKER_PEAK_RSS_GIB` 用字符串拼接写法(`"EX" "ACT_" "…"`)避开源码 grep 口径——确认这只是口径维护,不构成审计盲点。
- 个别被 blocked 的 knob 可能其实 operational(误杀方向,soundness 安全,不算 finding;但若你发现反向案例——operational 名单里混进了 proof knob——那是真 finding)。

**C. 整个 certified lifecycle 的任意切面**:cut replay 忠实性、master-domain 契约、power witness 表示、frontier terminal evidence、export/manifest 边界、resume/parallel 调度下的状态一致性。V57-V80 的 finding 全部是"同一母题的兄弟变体"——非权威路径伪装 certified;下一个变体可能在还没人看过的缝里。

## 自验环境与已知基线

- 先跑 `python scripts/check_p1_2_proof_obligations.py`(应 pass:8 obligations anchored)。
- `data/preprocessed/candidate_placements.json`(53.6MB)刻意外置不在包内。它导致的**已知环境性失败**(不是 finding,也不准伪造该文件):全量下 `test_binding` 10 个 ERROR、`test_regression` 5 个 FAILED、`test_routing` 3 个、`test_master` 1 个、`test_preprocess_golden` 1 个;其余约 2788 个测试应全过。
- **finding 尽量带可复现 probe**:构造伪 evidence / 注入 env / 篡改 manifest,实测验证器行为并附代码与输出。有实证的 finding 权重远高于纯阅读推断;实证推翻了你的怀疑就不要报。

## 交付物(最后打成一个 zip 给出)

- `REVIEW.md`:逐条 finding——严重度分级(**algorithmic/soundness** vs 工程/表面 vs 文档),`file:line` 定位,复现 probe(代码+输出),建议修法。
- 有把握的 finding 可附可落地补丁(unified diff,基于包内原文件);没把握就只报不修。
- **如果全审后没有 algorithmic/soundness finding,明确写出"本轮零 soundness finding"并列出你实际审过的面与方法**(owner 在仓库外手动维护连续清零计数,这句结论是计数输入)。不要为了交差硬凑低价值 finding,也不要因为 V80 刚修过就默认这轮干净——上一个洞(V79 切片域轴)正是在"看起来收口完成"的架构里找到的。

## 范围边界

- P1.3B(`src/cuts/lifecycle.py::step_8_apply_to_master` 的真 master 集成)被 owner gate 阻塞未开,不审未集成的未来工作。
- exploratory 路径只审"能否污染 certified 面",不审其自身质量。
- 9 个 cut family 的数学(F1-F9)经历过 v28 等多轮专项外审,可以审但不是本轮重心;它们的 validator 与 certified 面的衔接(replay/lifecycle)在重心内。

包 sha256:`66778633e2b5df898d531d670b6cb01300c28920dcf6a6f1e82bcd0a73323a81`
