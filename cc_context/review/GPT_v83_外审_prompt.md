# 终末地 IndustrialPlanner 精确求解器 — certified 面独立全审(V83 轮)

## 任务性质

这是一轮**独立对抗审查**(新会话零历史)。附件 `zmd_v80_impl_full_20260611_single.zip` 是完整项目快照(zip 内 `project/` 为仓库根镜像;**压缩方法 ZIP_LZMA,Linux `unzip` 不支持,用 `python -m zipfile -e zmd_v80_impl_full_20260611_single.zip .` 解包**)。Python 依赖 wheels 已在本 Project 文件区(zmd_deps 包),沙盒 Python 3.13,`pip install --no-index --find-links <wheels目录> -r requirements.txt` 离线安装。

你的目标只有一个:**找出任何能让"非权威路径产出看起来 CERTIFIED 的工件"的路径,或任何 soundness 缺陷**。具体 finding 类别(与包内 `data/review_gates/phase_1_2_spike_close.json` 的 `finding_classes_that_break_manual_clean_review` 一致):unsound cut、certified false negative、proof obligation bypass、fake certified claim、reachable phase-gate false ready。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器(目标 `max_lex(area, min_side)`,266 个强制设施实例,OR-Tools CP-SAT + LBBD 分解)。项目宪法在 `PROJECT_LOCK.md`;certified_exact 与 exploratory 严格分离;fail-closed 是默认姿态。

## 审查起点与历史

当前 review anchor = **`v82_oriented_domain_and_cut_replay_sealing`**。V22→V82 完整 finding 史在包内:`data/review_gates/phase_1_2_spike_close.json` 的 `informational_history` + `docs/research/p1_2_v*.md` 逐轮文档。

近三轮概要:V80 把 certified 面翻成 deny-unknown 封闭契约(admissibility 发布闸 / evidence 键白名单 schema v2 / env allowlist)。V81 封死时间预算打断的 partial precheck 被当完整 INFEASIBLE 证明、release 路径直通自称 CERTIFIED 两条缝。V82(上一轮)封死两个重磅:候选域曾只枚举 `h<=w` 而 master 可行性有向(全 frontier 证明只盖半域,已改全向枚举 + domain authority bump 到 `oriented_v2`);persisted `exact_safe_cuts` 曾经形状校验即 replay 进 master(已改为 telemetry-only,certified 不消费 checkpoint/IPC cut)。详见 `docs/research/p1_2_v81_*.md` / `p1_2_v82_*.md`。

## 前几轮已重点覆盖的面(供你换角度,不是禁区)

V81 审过:V80 三件套(normalize 层/schema v1 消费点/admissibility 出口/52 个 operational knob 逐个)、预算/anchor knob 的 skip 行为、release/viewer/landing 下游传播。V82 审过:resume/checkpoint 状态校验、parallel wave merge、inspector 字段信任边界、cut replay 与 master 衔接、`EXACT_SUBPROBLEM_PARAMS`(无可复现路径,保持 watch)、frontier/terminal projection。复查这些面有价值(前轮 reviewer 可能漏),但**优先把新鲜注意力放在还没被深挖的切面**,例如:

- **V82 修复自身的对抗审查**:全向域枚举后,支配/剪枝/digest/domain authority 的一致性有没有缝?persisted-cut 断电后,有没有别的通道还能把非新鲜 proof 对象送进 master(如 hint 路径、warm-start、condition 解析、worker 回传的 proof_summary 被信任的字段)?
- **binding / routing / power 子问题与 master 的"INFEASIBLE 证据"接口**:子问题的哪些返回会被消费成候选 INFEASIBLE / nogood?每条这种路径的证明义务是不是由当前进程的真实 solve 产生?有没有 V81 F-01(partial 当完整)的更多兄弟——比如迭代上限、内存上限、异常吞掉后的状态默认值?
- **数据加载边界**:`candidate_placements.json` / `mandatory_exact_instances.json` 等 preprocessed 输入的解析层——伪造/畸形输入会不会产生"静默缩小的实例集/pose 池"而不是 fail-closed(实例少了 = 约束少了 = 伪可行)?
- **`compute_exact_static_area_lower_bound` 与 safe_area_upper_bound 权威链**:这个静态下界喂进 evidence 的 safe bound;它的计算对输入畸形/缺失的行为?
- 任何你自己选的角度——V57-V82 的 finding 全是"非权威路径伪装 certified"母题的兄弟变体。

## 自验环境与已知基线

- 先跑 `python scripts/check_p1_2_proof_obligations.py`(应 pass:8 obligations anchored)。
- `data/preprocessed/candidate_placements.json`(53.6MB)刻意外置不在包内。它导致的**已知环境性失败**(不是 finding,也不准伪造该文件):全量下 `test_binding` 10 个 ERROR、`test_regression` 5 个 FAILED、`test_routing` 3 个、`test_master` 1 个、`test_preprocess_golden` 1 个;其余约 2795 个测试应全过。
- **finding 尽量带可复现 probe**:构造伪 evidence / 注入 env / 篡改 state,实测验证器行为并附代码与输出。有实证的 finding 权重远高于纯阅读推断;实证推翻了你的怀疑就不要报。

## 交付物(最后打成 zip 附上)

- `REVIEW.md`:逐条 finding——严重度分级(**algorithmic/soundness** vs 工程/表面 vs 文档),`file:line` 定位,复现 probe(代码+输出),建议修法。
- 有把握的 finding 附可落地补丁(unified diff,基于包内原文件)与配套 regression 测试;没把握就只报不修。
- **如果全审后没有 algorithmic/soundness finding,明确写出"本轮零 soundness finding"并列出你实际审过的面与方法**(owner 在仓库外手动维护连续清零计数,这句结论是计数输入)。不要为了交差硬凑低价值 finding,也不要因为 V80-V82 连续修过就默认这轮干净——V82 的半域洞正是在"已审多轮"的核心模块里找到的。

## 范围边界

- P1.3B(`src/cuts/lifecycle.py::step_8_apply_to_master` 的真 master 集成)被 owner gate 阻塞未开,不审未集成的未来工作。
- exploratory 路径只审"能否污染 certified 面",不审其自身质量。
- 9 个 cut family 的数学(F1-F9)经历过 v28 等多轮专项外审,可以审但不是本轮重心;它们的 validator 与 certified 面的衔接在重心内。

包 sha256:`cea834f77a45635ac3e08706fe6bbf138fe4aa69544707e48a1fb35f6a734338`
