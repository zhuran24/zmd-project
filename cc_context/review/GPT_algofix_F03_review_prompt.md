# 终末地 IndustrialPlanner 精确求解器 — F-03 修复实现审查 (preprocess 面 round 3, 零 finding 确认轮)

## 任务性质 (新会话零历史, 独立对抗审查)

附件是完整项目快照 zip (zip 内 `project/` 为仓库根; ZIP_LZMA, `python -m zipfile -e <附件>.zip .` 解包)。依赖 wheels 在本 Project 文件区, 沙盒 Python 3.13, 离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。

背景链 (归档全在包内): round 1 审出 F-01/F-02 (协议箱 omni_wireless 错编码 + front 过滤) → 修复落地; round 2 确认轮审出 **F-03 P0** (`cc_context/review/algoaudit_preprocess_face_r2_REVIEW_20260612.md`): wireless 修复只堵了消费端, 无线终品 (qiaoyu_capsule / valley_battery) 的**生产端实体输出口**仍被 `extract_port_specs()` 导出成 routing terminal → routing 孤立 source 无 sink → 虚假 `front_blocked` → false-INFEASIBLE。本包刚落地 F-03 修复:
- `src/models/binding_subproblem.py`: 新增 `routing_free_sink_commodities` (= positive `required_generic_inputs` 商品集, 构造期算好), `extract_port_specs()` 跳过这些商品的实体 **output** 口与 generic-output 口; 生产设施的原料 **input** 口保持 routing。
- 前提已实证: 这俩商品在 canonical 里 `sink_kind="generic_input"`、只作 recipe output 从不作 input、是 production_targets——纯终品, 排除其输出不会断任何真实 routing 消费者。
- 三件套: PROJECT_LOCK 生产端对偶条款 / specs/05 §5.4.3 生产端对偶段 / specs/08 $\mathcal{V}_{\text{port}}$ 无线例外。
- 回归: `test_wireless_sink_commodity_does_not_reenter_routing_from_producer_output` (unpatched 判别翻红)。

你的任务: 对抗式审查 F-03 修复——**确认修复正确且没引入新缝**。若审完无残留, 明确报零——owner 判 preprocess 面本批收口的输入。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 审查重点 (按优先级)

### Q1 排除集合的两个方向都别错 (最重要)
`routing_free_sink_commodities = {c : required_generic_inputs[c] > 0}`:
- **过宽方向 (新 false-CERTIFIED 风险)**: 有没有可能某商品 positive required_generic_inputs 却**同时**是某设施的 routing 中间输入 (canonical 里 recipe input)? 若存在, 跳过其生产输出口会让真实消费者断料而 binding/routing 却各自 FEASIBLE → 没人发现料没送到。请独立从 `rules/canonical_rules.json` 的 recipes/commodity_metadata 穷举核对当前 17-recipe 投影下该集合恰为 {qiaoyu_capsule, valley_battery} 且二者零 recipe-input 出现; 并评估: 若未来 canonical 扩展加入"既是 generic_input 又是中间品"的商品, 这套实现会静默错 (值得 fail-closed 守卫/测试钉死吗) 还是会显式报错?
- **过窄方向 (F-03 复发风险)**: 排除只看 `required_generic_inputs`——有没有别的 routing-free 消费形态没被覆盖 (如 required==0 时商品仍可能出现在某 selection? `__unused__` 路径)?
- 排除作用在 `extract_port_specs()` 的 binding_choice 端口循环与 generic_output 槽循环两处——**fixed_binding_choice** 路径、`extract_routing_aware_certificates()`、`extract_empty_binding_domain_instances()` 等其他读端口的出口有没有同类泄漏残留 (上轮逐通道清单在 r2 REVIEW 里, 请独立重走)?

### Q2 binding 数学与下游交互
- 跳过输出口只影响 port_specs 导出, **不**影响 binding 内部的端口绑定数学 (producer 的输出口仍参与 binding 选择)——这个不变性是否成立? 若 binding 选了一个"输出口被堵死"的 producer pose (实体上 front 被占), 现在 routing 不再看到该口, 是否引入"本应 front_blocked 却放行"的反向漏洞? **请仔细论证**: 按无线语义这恰是 desired (终品不需要可达 front), 还是存在某个物理一致性约束 (如游戏里满载输出口会 back-pressure 停机) 被丢了? 以 canonical/specs 文本为准, 不臆测游戏机制。
- precheck `front_blocked` / `binding_selection_safe_reject` / benders nogood 在新 port_specs 形状下的行为一致性。

### Q3 回归与文档
- 新回归是否真判别、覆盖双向 (qiaoyu 不在 port_specs / 原料口仍在)?
- PROJECT_LOCK / specs/05 / specs/08 新条款与代码是否严格一致, 措辞有没有把"排除输出口"误写成"排除全部口"之类错位。

## 明确不要报的

- 设计决策 (canonical omni_wireless + routing-free, owner 已定)。
- `candidate_placements.json` 外置 (可 `python src/placement/placement_generator.py` 再生, 期望 sha `adcc2a6e…`, **不准伪造**)。
- preflight 的 `phase_1_2_spike_close` BLOCKED (owner 手动计数 gate)。
- data/hints stale (已文档化) / 上几轮已 refuted 误判。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q -p no:randomly src/tests/` 应 **全绿 (≈2901 passed, 0 failed)**; 任何 failed 都值得查。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression; **关键论证写在回复正文**。
- **若审完确认修复 sound, 明确写「本轮零 soundness finding」** + 列实际审过的通道与构造的攻击。

## 范围边界

- 重点 = F-03 改动面 (`binding_subproblem.py` 排除逻辑 + 三件套) 及其与 routing/precheck/benders 交互; F-01/F-02 主体已上轮收口非重点 (但若发现其与 F-03 交互的新缝, 报)。
- P1.3B `step_8_apply_to_master` 禁区; exploratory 不审。

包 sha256: `764ef038b5df45a196ff597fb02a1b6e803fb4d2b8cd802113bb5446d8177614`
