# 终末地 IndustrialPlanner 精确求解器 — wireless 修复链 round 5 (F04-R4 residual 修复审查, 零 finding 确认轮)

## 任务性质 (新会话零历史, 独立对抗审查)

完整项目快照 zip 已上传在本 Project **文件区 (来源)**: `zmd_v80_impl_full_20260612_single.zip` (zip 内 `project/` 为仓库根; ZIP_LZMA, `python -m zipfile -e <该zip> .` 解包)。依赖 wheels 同在 Project 文件区, 沙盒 Python 3.13, 离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。本会话不带消息附件, 一切从 Project 文件区取; 开工前先校验包 sha256 与文末一致。

修复链背景 (归档全在包内 `cc_context/review/algoaudit_preprocess_face_r{1,2,3,4}_REVIEW_20260612.md`): r1 = F-01/F-02 (协议箱 omni_wireless 几何) → r2 = F-03 (无线终品生产端输出口经 `extract_port_specs` 泄入 routing) → r3 = F03-R3-01 (RAB build-time 侧门) + H03-R3-02 (dual-role 语义守卫) → **r4 = 全仓穷举确认轮又出 4 组 residual, 本包刚落地其修复** (commit c7f3bb5):

- **F04-R4-01**: `validate_preprocess_context()` 镜像 canonical dual-role 守卫 (直接 rules+plan / overlay 装载路径曾绕过仅 canonical 一层的守卫) — 双层 fail-closed;
- **F04-R4-02**: deletion-core minimizer 的 `_oracle_front_blocked` 接收可选 routing-visible port key 集 (`build_routing_visible_port_keys_by_instance(port_specs)`), benders 调用点传当轮 binding port specs; 不传参时保留 legacy raw 行为;
- **F04-R4-03**: pose-bool exact master 四处 raw port/front 消费 (PORT_ACTIVE 输出需求 / CLEARANCE_HARD cache / blocking-cell cut / lazy-demand cut, 全 env 门控) 改 routing-visible demand helper + `_routing_visible_poses_by_port_at_cell_dir` cache; visible 与 routing-free 混合输出侧不按 raw 输出口做 hard 泛化, 只让 demand-count cut 保守处理;
- **F04-R4-04**: `classify_pose_commodity_side()` / SAC hull / L2 abstract routing / dynamic separator 增加 `routing_free_sink_commodities` 参数过滤 output commodities (input 全保留), benders 与 pose-bool delegate 从 `generic_io_requirements.required_generic_inputs` 构造后传入。

PROJECT_LOCK line-95 与 specs/05 §5.4.3 的消费点清单已扩列到上述全部位置 + 守卫双装载路径条款。

你的任务: 对抗式审查 r4 修复——确认正确且没引入新缝。**若审完无残留, 明确报零** (owner 判 preprocess/wireless 修复链收口的输入)。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 审查重点 (按优先级)

### Q1 r4 修复四处本身 (最重要)
对每一处修复判定: 修对了吗、修全了吗、有没有引入新错误?

- R4-02: `build_routing_visible_port_keys_by_instance` 的 key 规范化 `(x,y,dir,type)` 会不会在任何 pose/binding 形态下撞 key 或漏 key (同 cell 多 port? dir 归一化?)? benders 调用点构造时机 (当轮 port_specs) 与 oracle 消费时机之间, binding 是否可能已变化? 不传参的 legacy 调用点还剩哪些、是否都不在 certified 路径?
- R4-03: routing-visible demand helper 的 input 全保留 + output 排除 `required_generic_inputs` 商品, 对「同一 operation 既有 visible output 又有 routing-free output」的混合侧处理是否真保守 (会不会反向放过该 hard-clear 的 visible 口)? `_routing_visible_poses_by_port_at_cell_dir` cache 与原 raw cache 的使用点有没有漏切换/错切换?
- R4-04: separator 分类过滤后, SAC/L2/dynamic 的容量数学是否仍 sound (少算 source 只会让 cut 更弱=安全, 还是某处会让 hull 约束反向收紧)? `routing_free_sink_commodities` 构造点 (benders 与 pose-bool delegate) 是否一致、有没有第三个调用点没传?
- R4-01: `validate_preprocess_context` 镜像守卫三条 (generic_input 必有 target / 不得作 recipe input / target 必须 generic_input) 与 canonical 守卫是否语义等价; 有没有第三条装载路径两层都不经过 (序列化/缓存/checkpoint resume 反序列化)?

### Q2 穷举的再穷举
r4 报告自己的穷举清单 (见包内 r4 REVIEW「Q1 端口 front 消费点穷举清单」) 判了若干「无新增 finding」与两个「非 blocking 备注」——请独立复核这些判定, 特别是:
- `src/cuts/oracles/port_exposure_oracle.py` (raw front oracle, r4 判「未接入 certified wireless 链」——真的吗? cut-family 框架哪些入口能到它?)
- `src/models/flow_subproblem.py` (r4 判「diagnostic 不作 proof」——certified 路径有没有任何分支把 flow 结果当 acceptance/cut 依据?)
- heuristic_feasible_finder 的 `_verify_flow`; master_model boundary-storage 筛; PCR/D2 路径。
还有没有 r4 也漏掉的第五处 raw port/front 消费?

### Q3 交互与回归
4 处修复相互之间 + 与 r2/r3 修复的交互 (例: deletion-core 拿 routing-visible keys 后, 其 minimal core 语义与 placement nogood 强度是否仍正确——少看端口会不会把真 blocker 从 core 里漏掉, 产生**过弱但仍错误归因**的 cut?)。env 全关 (默认 certified 路径) 行为零变化?

### Q4 文档一致性
PROJECT_LOCK line-95 / specs/05 §5.4.3 扩列后的清单与代码实际消费点集合是否一致 (列多/列少都报)。

## 明确不要报的

- 设计决策 (canonical omni_wireless / routing-free, owner 已定); r1/r2/r3 主体 (已收口, 除非与 r4 交互出新缝)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); data/hints stale (已档); 已 refuted 误判。

## 自验环境与已知基线

- 再生工件后全量应 **全绿 (≈2908 passed, 0 failed)**; 任何 failed 都值得查。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression; 关键论证写正文。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列实际复核过的消费点/交互面清单。

## 范围边界

- 重点 = r4 改动面 (上述 4 组) + Q2 的穷举复核; P1.3B `step_8_apply_to_master` 禁区; exploratory 不审。

包 sha256: `e676c94dcc8477d087c916299486bea08c0d5a23dfd31d20b2c4c5842684fa52`
