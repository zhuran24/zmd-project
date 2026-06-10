# 终末地 IndustrialPlanner 精确求解器 — V80 实现任务(委托开发,非审查)

## 任务性质

这是一个**委托实现任务**:按下面的目标与硬约束,设计并实现三个相互关联的加固,产出可直接落地的补丁包。本消息附完整项目快照 `zmd_v80_impl_full_20260610_single.zip`(zip 内 `project/` 为仓库根镜像,含 `PACKAGE_BUILD_INFO.json` 构建元数据;**压缩方法是 ZIP_LZMA,Linux `unzip` 命令不支持,请用 `python -m zipfile -e zmd_v80_impl_full_20260610_single.zip .` 解包**);Python 依赖 wheels 此前已上传在本 Project 文件区(zmd_deps 包),沙盒 Python 3.13,`pip install --find-links <解包目录> -r requirements.txt` 离线安装即可。ortools 项目钉 9.15.6755;若 Project 依赖包里的版本不符,如实报告并继续——本任务核心改动(`certified_frontier.py` / `certified_surface.py` / `delivery_manifest.py` / env guard)大多是纯逻辑,多数自验测试不需要真 solver。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器(目标 `max_lex(area, min_side)`,266 个强制设施实例,OR-Tools CP-SAT + LBBD 分解)。certified 路径的纲领:**任何非权威路径都不得产出看起来 CERTIFIED 的工件**;fail-closed 是默认姿态。项目宪法在 `PROJECT_LOCK.md`。

## 背景:为什么是这三件事

V22→V79 几十轮外审的 finding 几乎全是同一母题的变体:"某条非权威路径能产出看起来 certified 的东西"(完整轮次史:`data/review_gates/phase_1_2_spike_close.json` 的 `informational_history` + `docs/research/p1_2_v*.md`)。防御一直是**枚举式**的——发现一个坏轴加一个 if、一条黑名单,于是每轮审查都能找到下一个没被枚举的轴。本任务把防御范式从"枚举已知坏"翻转为"封闭白名单",并修复 V79 文档披露的 residual。三个工作项共享同一设计原则:**未知即拒绝(deny-unknown),让"下一个未封轴"这类 finding 在结构上不可能存在**。

## 工作项 A:V80 发布期 admissibility 闸(V79 residual 修复)

现状(原文见 `docs/research/p1_2_v79_terminal_domain_axis_sealing.md` 的 Known residual 段):

- PROJECT_LOCK 规定 `min_side >= 6` 是 admissibility(可采纳性下限),不是 tie-break。
- V79 后 terminal evidence 契约拒绝 `min_side > 6` 的切片域;`min_side < 6` 是超集域,对穷尽 soundness 安全,被接受。
- 但这样的 run 可以把一个 sub-admissible 矩形(`min(w,h) < 6`)当 terminal CERTIFIED best 发布——发布面(`src/search/certified_surface.py` / `src/io/delivery_manifest.py`)目前没有任何 admissibility 概念(可在沙盒 grep 验证)。

要求:

1. 设计**项目级 admissibility 字段**。这是 canonical-schema 级决策:toy/测试 project 合法使用更小的 floor,所以不能在 validator 里硬编码 6。V79 已有常量 `TERMINAL_FRONTIER_MIN_SIDE_ADMISSIBILITY = 6`(`src/search/certified_frontier.py`),它将来如何与项目级字段对齐(谁是权威、谁是投影)由你设计并在 DESIGN_NOTES 说明。
2. **设计核心难点(必须给出 soundness 论证)**:当超集域 run 的 lex-best certified 结果是 sub-admissible 时,"best admissible certified" 对 admissible 目标域是否可证明最优?注意 `compute_terminal_frontier_projection` 的剪枝语义里有"missing 候选可被 CERTIFIED 结果几何支配而合法剪枝"——若支配者本身 sub-admissible,被剪掉的 admissible 候选的证明义务是什么?如果你的结论是"不能无条件回收,必须 fail-closed 拒绝发布",就这样设计,**不要为了发布而弱化证明**。
3. schema 改动必须 PROJECT_LOCK.md、相关 spec、相关测试三层同步(见 PROJECT_LOCK 的 Forbidden Changes)。

## 工作项 B:terminal evidence 域契约白名单封闭

现状:`src/search/certified_frontier.py` 的 `terminal_frontier_evidence_violation`(约 :258 起)是 if 链,逐轴枚举已知坏值(`start_area` / `area_upper_bound` / `max_aspect_ratio` / `min_side`)。candidate_generation 契约将来每加一个参数,默认都是"可信直到被审出来"。

要求:翻转为**封闭契约**——定义"权威全域参数全集"(键白名单 + 每个键的权威值/合法形态),evidence 的 `candidate_generation` 出现任何**未知键**、或白名单键取**非权威值**,一律 fail-closed 拒绝(给出明确的 violation reason)。同时检查:

- `normalize_terminal_frontier_domain_contract` / `normalize_candidate_generation_params` 这类规范化层不得留旁路(静默丢弃未知键 = 旁路)。
- 评估 evidence `schema_version`(V75 契约)是否需要 bump;旧 evidence 在新校验下的 resume 语义应是 fail-closed,而不是静默通过。

## 工作项 C:certified env guard 翻转为 allowlist

现状:`src/search/benders_loop.py` 约 :441-:552,`_CERTIFIED_MASTER_DOMAIN_UNSAFE_ENV_OVERRIDES` 黑名单枚举已知危险 knob,`_CERTIFIED_POWER_WITNESS_CANONICAL_ENV_DEFAULTS` 钉 canonical 默认。但全项目 `EXACT_*` env knob 共 **242 个**(沙盒里 `grep -rhoE 'EXACT_[A-Z0-9_]+' src | sort -u | wc -l` 可复核),V61-V66 一轮轮外审就是在这张黑名单上逐个补洞。

要求:certified_exact 模式下翻转为 **allowlist**:

1. 对 242 个 knob **逐个分类**(沙盒里有全部源码,读使用点判断):proof-semantics-affecting(影响 master 域/witness 表示/cut 语义/候选域/证据写出 → certified 模式禁止非 canonical 值)vs operational-only(CP-SAT 线程数/日志/心跳/遥测路径/进程优先级等 → 允许)。**拿不准的归 proof-affecting**——fail-closed 方向永远安全,误杀一个 operational knob 的代价只是生产时要把它显式加回白名单,而漏放一个 proof knob 的代价是下一轮审查 finding。
2. 未分类(未来新增)的 `EXACT_*` knob 在 certified 模式出现时一律 fail-closed——这是范式翻转的核心:新 knob 默认不可信。
3. 不得破坏默认生产路径:`main.py` 默认参数、production wrapper(`scripts/run_campaign_*.sh`)注入的 env(如 `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH`——hint 是 hint 不是约束,项目 AI Safety Contract 允许)必须仍可跑。给出生产路径所需的最小白名单并在测试里锁住。
4. exploratory 路径不受影响(exact/exploratory 严格分离是宪法)。

## 硬约束(PROJECT_LOCK 纲领)

- **只紧不松**:所有改动只能让 certified 面更难伪造,不得放宽任何既有拒绝路径。
- certified_exact 与 exploratory 严格分离;不得触碰 PROJECT_LOCK Forbidden Changes 列表中任何一项。
- 改 campaign/artifact/proof schema 必须同步 PROJECT_LOCK.md、相关 spec、相关测试。
- fail-closed 永远优先于可用性。
- **范围边界**:不碰 9 个 cut family 的数学、不碰 master/binding/routing 子问题模型、不开 P1.3B(`PoseBoolExactMaster` 集成被 owner gate 阻塞,`src/cuts/lifecycle.py` 的 `step_8_apply_to_master` 是显式未集成边界)。

## 锚定仪式(交付必须含,这是项目硬性 gate)

推进 review anchor 到 `v80` 需同步以下**全部**位置(漏一处 check 脚本或测试就红;前三个易漏点历史上都漏过):

1. `data/proof_obligations/p1_2_proof_obligations.json`:`review_anchor`、`summary`、`updated_at`、相关 obligation 的 `v_findings`/`required_tests`/`evidence_paths`、以及 **`phase_gate_required_anchor`(易漏点 1)**。
2. `data/review_gates/phase_1_2_spike_close.json`:`updated_at`、顶层 `current_review_anchor`、**`owner_manual_state.current_review_anchor`(易漏点 2)**、`summary`、`informational_history` 追加 v80 条目。
3. `src/tests/test_p1_2_proof_obligations.py`:**硬编码锚改 v80(易漏点 3)**。
4. `scripts/check_p1_2_proof_obligations.py`:`REQUIRED_TESTS_BY_OBLIGATION_ID` 加新测试名、源码 needle 加新 violation reason 字符串/新常量/新错误信息。
5. `docs/research/p1_2_v80_*.md` 轮次文档(沿用 V79 文档结构:Date / Review anchor / Result / Finding / Patch / Regression / Closure position;**诚实披露你留下的任何 residual**)。
6. `docs/PHASE_1_2_CLOSE_GATE.md`、`docs/subjects/current_project_state.md`(两个 FIELD)、`START_HERE.md`、`docs/项目说明/06_current_status.md` 的锚点行。

## 沙盒工作流

1. 解包项目 zip;按 Project 文件区已有依赖包离线安装(Python 3.13)。
2. **先跑基线**:`python scripts/check_p1_2_proof_obligations.py` 必须 pass;再跑下方目标测试集,记录基线结果。注意:`data/preprocessed/candidate_placements.json`(53.6MB)刻意外置不在包内——它在完整测试面造成约 20 个**已知环境性失败**(`test_binding` 10 个 ERROR、`test_regression` 的 artifacts 类、`test_routing` 3 个、`test_master`/`test_preprocess_golden` 的 FileNotFoundError)。这些是基线,不是你要修的,也**不准**为了让它们过而伪造该数据文件。
3. 开发三个工作项;每步保持 check 脚本 + 目标测试绿。
4. 自验命令(最低要求):

```bash
python scripts/check_p1_2_proof_obligations.py
python -m pytest -p no:randomly -q \
  src/tests/test_delivery_manifest.py \
  src/tests/test_p1_2_proof_obligations.py \
  src/tests/test_v62_candidate_frontier_contract.py \
  src/tests/test_v63_terminal_evidence_contract.py \
  src/tests/test_exact_campaign_inspector.py \
  src/tests/test_regression.py \
  src/tests/test_parallel_scheduler.py \
  src/tests/test_exact_contract.py
```

时间允许再尽力跑更大子集(排除上述环境性失败文件)。

5. 新增防御必须带**攻击性反例测试**:伪造 evidence(未知键/篡改值)、certified 模式注入未分类 env、sub-admissible 发布尝试——每类至少一个"必须被拒"的测试,不只 happy path。

## 交付物(最后打成一个 zip 给出)

- `patches/`:per-file unified diff(基于包内原文件;新文件给全文)。
- `docs/research/p1_2_v80_*.md` 轮次文档(可直接落进仓库的最终稿)。
- `DESIGN_NOTES.md`:三个工作项的设计决策与 soundness 论证(特别是工作项 A 的 admissible-optimality 论证)、**242 个 knob 的完整分类表**(每个一行理由)、每个工作项的把握度(高/中/低 + 哪里需要 owner 复核)。
- `SELF_TEST_LOG.md`:实际跑过的命令与输出摘要(基线 vs 改后对照);没跑成的如实标注,不要假装跑过。
- 本轮该做但没做的,写进轮次文档 residual 段——诚实披露优于表面完整。

## 硬性输出约束(两条)

1. **不可达必须形式化**:若你主张某个工作项"做不到 / 必须先 X / 不能在本轮做"(例如工作项 A 的 admissible-optimality 不可无条件回收),必须给出形式化论证:具体反例构造、或证明义务缺口的精确陈述。不接受 "I believe / intuitively / 通常如此";确实只有直觉就显式标 "intuition only"。
2. **范围自律**:发现本任务之外的问题(无论多严重)记录在 DESIGN_NOTES 的 out-of-scope findings 段,不要顺手修——certified 面的每处改动都要走锚定仪式,顺手修会破坏审计链。

项目包 sha256:`f127bbe79d1a721c4c1d7bb00ae637f7a72c8fdca0131e1bc136e9e8a7363bf4`
