# 终末地 IndustrialPlanner 精确求解器 — preprocess F-01/F-02 修复实现审查 (零 finding 确认轮)

## 任务性质 (新会话零历史, 独立对抗审查)

附件是完整项目快照 zip (zip 内 `project/` 为仓库根; ZIP_LZMA, `python -m zipfile -e <附件>.zip .` 解包)。依赖 wheels 在本 Project 文件区, 沙盒 Python 3.13, 离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。

本包刚落地了 preprocess F-01/F-02 完整修复 (实现自述 `cc_context/review/algofix_preprocess_wireless_FIXES_20260612.md`, 上轮审查原文 `cc_context/review/algoaudit_preprocess_face_r1_REVIEW_20260612.md`):
- 生成器: `protocol_storage_box` 按 canonical `omni_wireless` 改为 3×3 无端口全 anchor 枚举 (68×68=4624); `is_edge_starved()` 改查 routing front 格; 候选池总量 66,403, 新冻结工件 `adcc2a6e…`/45,773,799B (旧 `d5e3911f…` 标记 superseded, resume 撞旧 hash 必须 fail-closed)。
- binding: `wireless_sink` 实例的 generic input 槽**虚拟化** (每实例 3 槽来自 `rules/preprocess_plan.json`, 无坐标无端口, `routing_free=True`), `extract_port_specs()` 跳过虚拟槽 → routing/flow 收不到无线商品需求 (routing-free 消费语义)。
- 三件套: PROJECT_LOCK/specs05+06/docs/preflight 外置契约全部换登记。

你的任务: 对抗式审查这套修复的 soundness——**确认修复正确且没引入新缝**。若审完无残留缺陷, 明确报零——这是 owner 按「安全修复完整性」原则判该批完成的输入。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 审查重点 (按优先级)

### Q1 routing-free 声明的完备性 (最重要)
「无线商品零 routing 需求」依赖 `extract_port_specs()` 跳过虚拟槽这**一个**闸门。请穷举所有从 binding 流向 routing/flow/precheck/master-cut 的信息通道 (`extract_selection` / `extract_port_specs` / `extract_routing_aware_certificates` / conflict summary / `add_nogood_cut` / benders_loop 消费侧), 确认:
- 没有第二条通道把 wireless 商品或虚拟槽坐标泄进 routing/flow (虚拟槽 dict 无 x/y/dir——有没有下游代码对槽 dict 做 `slot["x"]` 直接下标而在某条路径上炸/或更糟地默默用错值?);
- `run_exact_routing_precheck` 与 flow 诊断对无线商品的处理一致 (不会把"零需求"误读成"断连"或反之);
- binding nogood / 重解循环在含虚拟槽的 selection 上形状正确 (不会因虚拟槽让 nogood 失效或过强)。

### Q2 binding 容量数学不变性
虚拟槽替换实体槽后: `AddExactlyOne(commodities+__unused__)` + `sum(commodity vars)==required` 的可满足集与"槽数承载力"语义是否严格保持? 攻击点: required > 总虚拟槽数应 INFEASIBLE; required==0 时全 `__unused__`; 多 wireless 实例槽数叠加; `load_wireless_sink_generic_input_slots()` 的 fail-closed (缺文件/缺键/负数)。

### Q3 生成器与池契约
- `is_edge_starved()` 新语义 (整边全部 front 越界才剪) 的 exactness: 被剪 pose 是否**必然**下游不可行 (该 port_mode 声明边必须至少绑一口)? 有没有被误剪的合法 pose (漏枚举复发)?
- 协议箱全 anchor 域 68×68 的边界正确性; 旧 TB/BT/RL/LR 伪模式清干净; 池闭式计数与实际生成一致。
- 工件 supersession: campaign resume 撞旧 hash `d5e3911f…` 是否真 fail-closed (`test_campaign_resume_rejects_stale_candidate_placement_hash` 是否真判别)?

### Q4 回归测试判别力与文档一致性
新增/改写测试 (geometry contract 4 条 / wireless semantics 5 条 / test_placements 重写 / binding+exact_contract 更新) 是否真判别 (不是恒真)? PROJECT_LOCK/specs05+06 的陈述与代码是否还有错位残留 (上轮 F-01 的教训正是 docstring 与 canonical 矛盾——请全文搜协议箱/端口相关陈述)?

## 明确不要报的

- 设计决策本身 (服从 canonical omni_wireless = 无端口 + routing-free, owner 已定, 不重开辩论)。
- `data/hints/blueprint_*.json` stale (已知已文档化, advisory 不伤 soundness)。
- `candidate_placements.json` 不在包内 (外置, 你可用 `python src/placement/placement_generator.py` 现场再生, **不准伪造**; 期望 sha `adcc2a6e…`)。
- preflight 的 `phase_1_2_spike_close` BLOCKED (owner 手动计数 gate, by-design)。
- 上几轮已 refuted 的误判 (52-port 满占 / front 单次偏移 / pose-bool guard)。

## 自验环境与已知基线

- 再生工件后: `python -m pytest -q -p no:randomly src/tests/` 应 **全绿 (≈2900 passed, 0 failed)** — 旧「环境性失败」族已随工件回树清零; 任何 failed 都值得查。
- `python scripts/check_p1_2_proof_obligations.py` pass; `python scripts/check_external_artifacts.py --require candidate_placements` pass (再生后)。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression; **关键论证写在回复正文**。
- **若审完确认修复 sound, 明确写「本轮零 soundness finding」** + 列实际审过的通道清单、构造过的攻击、论证依据。

## 范围边界

- 重点 = 本批修复改动面 (placement_generator / binding_subproblem / 三件套文档 / 新测试) 及其与 routing/flow/campaign 的交互; 其余内核已多轮收口。
- P1.3B `step_8_apply_to_master` 禁区; exploratory 不审。

包 sha256: `7f0433fa4258cb91970b9f266bbbc8f36f793c004687b64c09e2ad7625d8063a`
