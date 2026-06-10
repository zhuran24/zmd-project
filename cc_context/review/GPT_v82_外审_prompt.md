# 终末地 IndustrialPlanner 精确求解器 — certified 面独立全审(V82 轮)

## 任务性质

这是一轮**独立对抗审查**(新会话零历史)。附件 `zmd_v80_impl_full_20260611_single.zip` 是完整项目快照(zip 内 `project/` 为仓库根镜像;**压缩方法 ZIP_LZMA,Linux `unzip` 不支持,用 `python -m zipfile -e zmd_v80_impl_full_20260611_single.zip .` 解包**)。Python 依赖 wheels 已在本 Project 文件区(zmd_deps 包),沙盒 Python 3.13,`pip install --no-index --find-links <wheels目录> -r requirements.txt` 离线安装。

你的目标只有一个:**找出任何能让"非权威路径产出看起来 CERTIFIED 的工件"的路径,或任何 soundness 缺陷**。具体 finding 类别(与包内 `data/review_gates/phase_1_2_spike_close.json` 的 `finding_classes_that_break_manual_clean_review` 一致):unsound cut、certified false negative、proof obligation bypass、fake certified claim、reachable phase-gate false ready。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器(目标 `max_lex(area, min_side)`,266 个强制设施实例,OR-Tools CP-SAT + LBBD 分解)。项目宪法在 `PROJECT_LOCK.md`;certified_exact 与 exploratory 严格分离;fail-closed 是默认姿态。

## 审查起点与历史

当前 review anchor = **`v81_partial_precheck_and_release_claim_sealing`**。V22→V81 完整 finding 史在包内:`data/review_gates/phase_1_2_spike_close.json` 的 `informational_history` + `docs/research/p1_2_v*.md` 逐轮文档。

近两轮概要:V80 把 certified 面的防御范式从"枚举已知坏轴"翻转为 deny-unknown 封闭契约(项目级 admissibility 发布闸 + terminal evidence 键白名单 schema v2 + certified env allowlist,未分类 `EXACT_*` 出现即拒)。V81(对 V80 的第一轮独立外审)找到并封死了两条缝:时间预算打断的 mandatory-rectangle precheck 部分 group 曾被当成完整 all-anchors-infeasible 证明消费(certified false negative);single-base release builder 曾把 run_summary 自称的 CERTIFIED 直通进 release/pointer 工件。两者详情见 `docs/research/p1_2_v81_partial_precheck_and_release_claim_sealing.md`。

## 前两轮已重点覆盖的面(供你换角度,不是禁区)

V81 reviewer 自述已逐面审过且除上述两条外无 finding:V80 terminal-evidence deny-unknown 契约(normalize 层/schema v1 消费点)、admissibility 发布闸的出口(certified_surface / delivery_manifest / blueprint export / inspector)、env allowlist 52 个 operational knob 逐个、boundary-port / mandatory-rectangle max-anchors / ghost-aware coordinate validation 的预算与 skip 行为、release/viewer/landing/frontdoor 下游状态传播。你可以复查这些面(独立验证有价值,上一轮 reviewer 也可能漏),但**优先把新鲜注意力放在还没被深挖的切面**,例如:

- **resume / checkpoint / parallel 状态一致性**:`exact_campaign.py` 状态机、checkpoint 原子写入、`exact_parallel_scheduler.py` 多进程 wave 下 candidate 状态合并、乱序完成时 best/frontier 的一致性,以及 resume 时旧 state 字段对新校验的绕过可能。
- **certified cut replay 与 master 的衔接**:`src/cuts/` lifecycle 与 `cut_manager.py` 的 replay/register 原子性、`src/models/master_model.py` 里其它 precheck 家族(coordinate validation、signature monotonic、ghost overlap、boundary-port)的"部分结果/预算耗尽/异常路径"是否存在 F-01 的兄弟(部分证据被当完整证明)。
- **`EXACT_SUBPROBLEM_PARAMS`**(V81 标记为 watched risk surface,未找到可复现实例):它能注入任意 CP-SAT 参数到子问题;深挖是否存在参数组合让 binding/routing 子问题的非 OPTIMAL 终态被当成 INFEASIBLE 证据消费。
- **inspector / 报告面**:`exact_campaign_inspector.py` 的字段信任边界。
- 任何你自己选的角度——V57-V81 的 finding 全是"非权威路径伪装 certified"这一母题的兄弟变体,下一个变体可能在还没人看过的缝里。

## 自验环境与已知基线

- 先跑 `python scripts/check_p1_2_proof_obligations.py`(应 pass:8 obligations anchored)。
- `data/preprocessed/candidate_placements.json`(53.6MB)刻意外置不在包内。它导致的**已知环境性失败**(不是 finding,也不准伪造该文件):全量下 `test_binding` 10 个 ERROR、`test_regression` 5 个 FAILED、`test_routing` 3 个、`test_master` 1 个、`test_preprocess_golden` 1 个;其余约 2793 个测试应全过。
- **finding 尽量带可复现 probe**:构造伪 evidence / 注入 env / 篡改 state,实测验证器行为并附代码与输出。有实证的 finding 权重远高于纯阅读推断;实证推翻了你的怀疑就不要报。

## 交付物(全部内容直接写在回复里,不要只放附件)

- 逐条 finding:严重度分级(**algorithmic/soundness** vs 工程/表面 vs 文档),`file:line` 定位,复现 probe(代码+输出),建议修法。**finding 全文与修法直接写在回复正文**;附件 zip 可以同时给(便于归档),但正文必须自包含——接收通道有时抓不到附件。
- 有把握的 finding 给出修法的精确描述(改哪个文件哪个函数、加什么条件);没把握就只报不修。
- **如果全审后没有 algorithmic/soundness finding,明确写出"本轮零 soundness finding"并列出你实际审过的面与方法**(owner 在仓库外手动维护连续清零计数,这句结论是计数输入)。不要为了交差硬凑低价值 finding,也不要因为 V80/V81 刚修过就默认这轮干净。

## 范围边界

- P1.3B(`src/cuts/lifecycle.py::step_8_apply_to_master` 的真 master 集成)被 owner gate 阻塞未开,不审未集成的未来工作。
- exploratory 路径只审"能否污染 certified 面",不审其自身质量。
- 9 个 cut family 的数学(F1-F9)经历过 v28 等多轮专项外审,可以审但不是本轮重心;它们的 validator 与 certified 面的衔接(replay/lifecycle)在重心内。

包 sha256:`4d90b200ff0a00ce8302c9bfe26a3e12656a405f95a6f525810c1cd8408f41c8`
