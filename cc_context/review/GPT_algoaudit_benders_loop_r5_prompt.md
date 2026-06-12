# 终末地 IndustrialPlanner 精确求解器 — Benders/LBBD 主循环 round 5 (F-BL-R4-01 修复攻击面 + 跨 candidate 会话隔离/proof summary 完整性角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_278e4d67.zip`, sha256 `278e4d67f97a88cab7bba697ec96df2f04d43ce1475bc65aef4a22519d1885a0`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + **Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断**)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面历史与本轮定位

本面 (`src/search/benders_loop.py` 主循环) 轮次史: 算法审 1 轮 (A-1/A-2 已修) + 修复确认 2 轮零; 涟漪轮抓 **F-BL-R3-01** (预算耗尽≠穷尽证明, cap 命中 → UNKNOWN 不铸 nogood) + **F-BL-R3-02** (routing status 显式契约, 非三态 → UNKNOWN 无 cut); **r4 抓同型残留 F-BL-R4-01 已修**: binding solve 的状态消费同型裂缝 — 初始 solve 只显式处理 TIMEOUT/INFEASIBLE, 非契约状态 (MODEL_INVALID/UNKNOWN/ABORT) 继续建 routing core、跳过 FEASIBLE 主循环、落到 `binding_status="EXHAUSTED"` whole-layout nogood 分支 (probe: MODEL_INVALID → `routing_exhausted_nogood` 被铸 = false-INFEASIBLE 方向); 同型共五处 (初始 solve / overload fallback retry / precheck safe-reject 重解 / relaxed_disconnected 重解 / routing INFEASIBLE 后重解)。修 (lock F-BL-R3 条款扩写 R4) = `_record_unexpected_binding_status()` 统一 fail-closed (`subproblem_status_contract_violation="unexpected_binding_status"` + 返回 UNKNOWN 无 cut) 五处全堵 + overload retry INFEASIBLE 时 proof source 切到 retry model。**本轮 r5 = F-BL-R4-01 修复确认 + 刻意换角度**。

注意: 包内带着其它面同期修复 (lock 末 F-GM-Q3-01-R3-A / F-CUT-R3 / F-RT-R3-01 系列), 各有线别重报。

## 审查重点 (按优先级)

### Q1 F-BL-R4-01 修复确认 (攻击面)

① 五消费点逐处核对 `_record_unexpected_binding_status` 接线: 有没有第六处 binding status 消费 (含 heuristic/diagnostic 路径里影响 proof 决策的) 仍走旧逻辑? 各处 return 后的控制流真的不再触达任何 cut 登记/exhaustion 分支? ② overload retry 的 proof source 切换 (`binding_model = retry_model`): 切换后 conflict summary/nogood 登记/exhaustion 证明引用的是否全部一致指向 retry model — 有没有半切换 (status 用 retry, summary 用第一轮) 残留? ③ `_record_unexpected_binding_status` 写的 proof summary 形状: `master_status: "FEASIBLE"` 硬编码 — 在哪些调用点 master 实际不是 FEASIBLE, 这个字段被下游消费成证据吗 (若只是 telemetry 则判读为 cosmetic)? ④ 与 F-BL-R3-01/02 的组合: cap 命中 + 非契约状态同时发生的路径序。

### Q2 跨 candidate 会话隔离 (新角度)

certified exact session 复用 static core, master overlay/controller/binding model 每 candidate 重建 (r4 已核)。本轮攻**共享态泄漏**: ① exact session 的 static core 在单个 candidate 求解期间有没有被加约束/改 domain (若有, 下一个 candidate 继承 = 跨 candidate 污染; 给出 core 对象生命周期内全部 mutation 点清单)? ② `CutManager`/`generated_exact_safe_cuts`/binding cache (`_update_binding_cache_from_summary`) 等 controller 外的累积容器: 哪些跨 candidate 存活, 存活的各自语义是 telemetry 还是会回流 proof 决策 (特别是 binding conflict cache 会不会让 candidate B 因 candidate A 的 conflict 被剪)? ③ 并行 worker (`exact_parallel_scheduler`) 的 per-worker session 与 serial 路径在共享态上的差异 — 有没有 serial 独有的跨 candidate 残留是 parallel 没有的 (或反向), 导致同一 campaign 两种执行方式可产生不同 proof 结论?

### Q3 proof summary 完整性 (新角度)

`last_proof_summary` 是单槽属性: ① 同一 candidate 求解内多次覆写的时序 — 最终被 outer/campaign 读走的是否总是「与返回 status 对应的那份」(构造一个中途覆写后异常路径返回的序, 看 summary 与 status 是否可能错配)? ② summary 里的 `subproblem_status_contract_violation` / `master_follow_up` 等键有没有下游消费者把它们当强证据 (应只是 telemetry/审计)? ③ heartbeat/telemetry 发射点 (`_emit_heartbeat`) 在异常路径上的 fail-open 检查 — 发射失败会不会改变控制流。

### Q4 抽查维持

F-BL-R3-01 cap→UNKNOWN 路径 / r4 Q2 重入清单 (reset metadata / persisted cuts 置空 / hint 非 proof) / Q3 终止保真 (UNKNOWN 不在 frontier skip 集) — 各抽 1-2 处对照 r4 已审结论。

## 明确不要报的

- A-1/A-2/F-BL-R3/F-BL-R4-01 已修本体复述 (但其修复的**新**缝算)。
- binding/master/routing/preprocess/campaign/scheduler 各面内部建模 (各有线; 本面只管主循环对它们的**消费**)。
- 设计决策 (canonical/266/52-Port); persisted `exact_safe_cuts` 是 telemetry 非 proof (V82, 已多轮确认, 但其边界的**新**绕过算)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2963 passed, 0 failed)**; 跑不完跑专项 (test_exact_contract / test_exact_campaign_state_soundness / test_p0_certified_soundness_fixes) + 如实声明 (`-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 跨 candidate 共享态清单 (容器×生命周期×telemetry/proof 判读) 与 Q1 五消费点核对表。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = F-BL-R4-01 修复确认 + 跨 candidate 隔离 + proof summary 完整性; 其余面不审。
