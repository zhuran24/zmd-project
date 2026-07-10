# attach 通电线 production integration checklist（2026-07-11 凌晨立，GO 判决直接产物）

## §0 定位与终点

spike GO（`02_spike_evidence.md`）证明的是**工程开销可行**（10K attach 16.6s+solve +4.1%）；本清单是从「direct harness sanctioned 通路」到「生产 benders 循环正式通电」之间的全部工程就绪项。**终点 = owner promote 仪式**：把 `EXACT_CUT_FRAMEWORK_ATTACH` 从 `_CERTIFIED_MASTER_DOMAIN_UNSAFE_ENV_OVERRIDES` 移出（owner-only，含 PROJECT_LOCK 修订）——在那之前所有项完成也不等于通电（P1.2 手动门同款纪律）。

## §1 就绪项清单（编号即引用名，排序=建议执行序）

**PIC-0 宿主形态设计决策**（阻塞后续所有实测项）：通电宿主二选一——
- (a) certified campaign：需 owner promote+lock 修订，攻击面评估随 RFC-001；
- (b) exploratory campaign：当前 prod-scale 不可用（port clearance 启发式 build 爆炸+legacy master，见 memory 卡 exploratory-mode-prod-scale-unusable）——选此路需先修 exploratory（port clearance 开关+C1 delegate 解绑 exact_mode，均为生产代码改动）。
- 默认推荐 (a)：exploratory 修复工作量大且修完仍是非生产 master 形态,对「生产通电」的验证价值有限。

**PIC-1 三硬门（spike §3 拍板原文保留，不因 GO 消失）**：
1. RFC-001 原子封口：spike 级安全面=F3 step_8 入口 integrity 纵深+接线层 fail-closed（c7cd6a0）；通电前须正式评估「纵深是否足以替代原子封口」并成文（设计评审级,双审）。
2. RFC-002 F5 独立 verifier：通电族=F1/F6/F7,F5 保持 shadow/不 mutate master；F5 转正的前置=独立 verifier 落地。
3. RFC-003 ledger+dedup+epoch：spike 是单 epoch 单 master 豁免；生产 campaign 多 rect 多 epoch 场景必须落 ledger+dedup（跨 solve cut 池账本）。

**PIC-2 agnostic-F5 语义缝二选一**（spike TRIAGE 移交）：lifecycle:1393-1402 对 GHOST_AGNOSTIC F5 走无条件 attach 但 delegate:8050 拒空条件 → fail-closed。落地 F5 时二选一：delegate 支持空条件（改 sealed 文件）或 lifecycle 禁 agnostic F5 进 step_8。与 RFC-002 同批处理。

**PIC-3 E3 预算 env 化**（spike 规格原 §2 遗留）：`EXACT_CUT_FRAMEWORK_ATTACH_BUDGET=2000` 硬编码（benders_loop.py:946）→ env 可配。碰 benders_loop sealed 文件=reseal 链；新增 EXACT_* env=allowlist+lock+tests 三同步（CLAUDE.md §6 铁律）。小批次,可先行。

**PIC-4 跨 solve cut 池演化实测**（spike 效度边界 #5）：campaign 多 rect 序列下 cut 生成→scope 检查→attach→anchor 切换退役（M4-A ghost conditioning）的端到端行为从未在 prod-scale 实测。依赖 PIC-0 宿主。

**PIC-5 benders 循环编排路径验证**：spike 直调 step_8 绕过了 `_maybe_attach_framework_cuts` 的 step5→6→7→8 完整编排与 2000 预算路径;通电前须在宿主内验证门控编排本身（含 rejection taxonomy 计数落 telemetry）。依赖 PIC-0。

**PIC-6 replay 诊断 subset 残留清理**（cut 修复批 TRIAGE）：生产不可达,顺通电批一并清。

**PIC-7 M5 独立前置——产品默认 solve 参数病态归因**：默认 FIXED_SEARCH+probing3+symmetry3 在 C1 上持续吃内存不出解（M5 五刀+E1 系列双重实锤）,当前一切 prod-scale 实验靠原型参数 env 续命。通电的 wall 判断最终要在「生产可用参数形态」上重做一次轻量对照;归因与修法归 M5 线（A/B 实验已解锁）,此处为排期依赖登记。

## §2 批次划分建议

- **批 A（可立即,不依赖 PIC-0）**：PIC-3（E3 预算 env 化,小批全流程练 reseal）+ PIC-6（顺手）。
- **批 B（设计评审）**：PIC-0 宿主拍板 + PIC-1.1 原子封口评估成文——owner 参与度高,放 owner 在场时段。
- **批 C（实测,依赖 B）**：PIC-4+PIC-5。
- **批 D（F5 线,可与 C 并行）**：PIC-1.2+PIC-2。
- **批 E（账本）**：PIC-1.3。
- promote 仪式（owner-only）压轴。

## §3 明确不做（边界）

- 不在本线内做 cut 数学有效性升级（F 族语义归数学面/Fable5 负责人地盘）。
- 不做 F8（已退役）与 F2/F4/F9 未接线族的 step_8 接线（`NotImplementedError` fallback 保持,接线归各族落地批）。
- 不做吞吐/容量流(OUT-OF-SCOPE,PROJECT_LOCK §1A B)。
