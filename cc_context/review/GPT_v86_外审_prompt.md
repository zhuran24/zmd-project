# 终末地 IndustrialPlanner 精确求解器 — certified 面独立全审(V86 轮)

## 任务性质

这是一轮**独立对抗审查**(新会话零历史)。附件 `zmd_v80_impl_full_20260611_single.zip` 是完整项目快照(zip 内 `project/` 为仓库根镜像;**压缩方法 ZIP_LZMA,Linux `unzip` 不支持,用 `python -m zipfile -e zmd_v80_impl_full_20260611_single.zip .` 解包**)。Python 依赖 wheels 已在本 Project 文件区(zmd_deps 包),沙盒 Python 3.13,`pip install --no-index --find-links <wheels目录> -r requirements.txt` 离线安装。

你的目标只有一个:**找出任何能让"非权威路径产出看起来 CERTIFIED 的工件"的路径,或任何 soundness 缺陷**。具体 finding 类别(与包内 `data/review_gates/phase_1_2_spike_close.json` 的 `finding_classes_that_break_manual_clean_review` 一致):unsound cut、certified false negative、proof obligation bypass、fake certified claim、reachable phase-gate false ready。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器(目标 `max_lex(area, min_side)`,266 个强制设施实例,OR-Tools CP-SAT + LBBD 分解)。项目宪法在 `PROJECT_LOCK.md`;certified_exact 与 exploratory 严格分离;fail-closed 是默认姿态。

## 审查起点与历史

当前 review anchor = **`v85_required_optional_terminal_sealing`**。V22→V82 完整 finding 史在包内:`data/review_gates/phase_1_2_spike_close.json` 的 `informational_history` + `docs/research/p1_2_v*.md` 逐轮文档。

近四轮概要:V80 deny-unknown 翻转(admissibility 闸/evidence 白名单/env allowlist);V81 封 partial-precheck 当完整证明 + release 自称 CERTIFIED;V82 封半域枚举(候选域全向化 + domain authority bump)+ persisted cuts 降级 telemetry;V83 封三缝(发布面几何重验/whole-layout nogood continue/mandatory loader deny-unknown);V84 封三缝(witness 最优性/symlink 拒绝/未知实例拒绝);V85(上一轮)封一缝:terminal validator 现在绑定 generic_io 推导的必选 pose-level optional 下界(省略必选 storage box 的伪 checkpoint 不再 publishable)。详见 `docs/research/p1_2_v81_*.md` / `p1_2_v82_*.md` / `p1_2_v83_*.md` / `p1_2_v84_*.md` / `p1_2_v85_*.md`。

## 前几轮已重点覆盖的面(供你换角度,不是禁区)

V81-V85 已逐面审过:V80 三件套、预算/anchor knob、release 下游、resume/checkpoint 校验、parallel wave merge、inspector、`EXACT_SUBPROBLEM_PARAMS`(watch 中)、cut replay 与 master 衔接、frontier/terminal projection、数据加载边界、safe bound 权威链、子问题 INFEASIBLE 证据接口。**优先换新鲜角度**,例如:V85 修复自身的对抗面(required optional 下界绑定的绕法?optional 占用与 witness 的交互?)、power witness 表示与 terminal 工件的衔接、blueprint/export 几何一致性、routing/binding 子问题接口残余、campaign telemetry 与 proof 混淆面、resume 旧字段兼容路径。已知 residual(连续披露,可挑战):proof_summary 仍是任意 Mapping(proof-carrying certificate 是 future work)、`EXACT_SUBPROBLEM_PARAMS` watch、v1 evidence fail-closed 不迁移。

## 自验环境与已知基线

- 先跑 `python scripts/check_p1_2_proof_obligations.py`(应 pass:8 obligations anchored)。
- `data/preprocessed/candidate_placements.json`(53.6MB)刻意外置不在包内。它导致的**已知环境性失败**(不是 finding,也不准伪造该文件):全量下 `test_binding` 10 个 ERROR、`test_regression` 5 个 FAILED、`test_routing` 3 个、`test_master` 1 个、`test_preprocess_golden` 1 个;其余约 2802 个测试应全过。
- **finding 尽量带可复现 probe**:构造伪 evidence / 注入 env / 篡改 state,实测验证器行为并附代码与输出。有实证的 finding 权重远高于纯阅读推断;实证推翻了你的怀疑就不要报。

## 交付物(最后打成 zip 附上)

- `REVIEW.md`:逐条 finding——严重度分级(**algorithmic/soundness** vs 工程/表面 vs 文档),`file:line` 定位,复现 probe(代码+输出),建议修法。
- 有把握的 finding 附可落地补丁(unified diff,基于包内原文件)与配套 regression 测试;没把握就只报不修。
- **如果全审后没有 algorithmic/soundness finding,明确写出"本轮零 soundness finding"并列出你实际审过的面与方法**(owner 在仓库外手动维护连续清零计数,这句结论是计数输入)。不要为了交差硬凑低价值 finding,也不要因为 V80-V85 连续修过就默认这轮干净——V82 的半域洞和 V83 的几何假发布正是在"已审多轮"的核心模块里找到的。

## 范围边界

- P1.3B(`src/cuts/lifecycle.py::step_8_apply_to_master` 的真 master 集成)被 owner gate 阻塞未开,不审未集成的未来工作。
- exploratory 路径只审"能否污染 certified 面",不审其自身质量。
- 9 个 cut family 的数学(F1-F9)经历过 v28 等多轮专项外审,可以审但不是本轮重心;它们的 validator 与 certified 面的衔接在重心内。

包 sha256:`deac3b84d98066fc463385e0ba123ad39bef8bf13580d8c3e28f5570bbd16566`
