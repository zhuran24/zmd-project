# attach 通电线 production integration checklist（2026-07-11 凌晨立，GO 判决直接产物）

## §0 定位与终点

spike GO（`02_spike_evidence.md`）证明的是**工程开销可行**（10K attach 16.6s+solve +4.1%）；本清单是从「direct harness sanctioned 通路」到「生产 benders 循环正式通电」之间的全部工程就绪项。**终点 = owner promote 仪式**：把 `EXACT_CUT_FRAMEWORK_ATTACH` 从 `_CERTIFIED_MASTER_DOMAIN_UNSAFE_ENV_OVERRIDES` 移出（owner-only，含 PROJECT_LOCK 修订）——在那之前所有项完成也不等于通电（P1.2 手动门同款纪律）。

## §1 就绪项清单（编号即引用名，排序=建议执行序）

**PIC-0 宿主形态设计决策**（阻塞后续所有实测项）：通电宿主二选一——
- (a) certified campaign：需 owner promote+lock 修订，攻击面评估随 RFC-001；
- (b) exploratory campaign：当前 prod-scale 不可用（port clearance 启发式 build 爆炸+legacy master，见 memory 卡 exploratory-mode-prod-scale-unusable）——选此路需先修 exploratory（port clearance 开关+C1 delegate 解绑 exact_mode，均为生产代码改动）。
- 默认推荐 (a)：exploratory 修复工作量大且修完仍是非生产 master 形态,对「生产通电」的验证价值有限。

**PIC-1 三硬门（spike §3 拍板原文保留，不因 GO 消失）**：
1. RFC-001 原子封口 ✅评估已成文并过双审(2026-07-11,`02_rfc_adoption_assessment.md` 正式判定节,opus+codex 双 AGREE_WITH_AMENDMENTS 修正后定稿)：判定=纵深不替代原子封口;通电第一批=RFC-001 阶段 B(封 state 侧 validate/compile 漂移——cut 侧已 frozen 结构性关闭);叠加 lock:487 三前置之上;spike 级活动不受阻。
2. RFC-002 F5 独立 verifier：通电族=F1/F6/F7,F5 保持 shadow/不 mutate master；F5 转正的前置=独立 verifier 落地。
3. RFC-003 ledger+dedup+epoch：spike 是单 epoch 单 master 豁免；生产 campaign 多 rect 多 epoch 场景必须落 ledger+dedup（跨 solve cut 池账本）。

**PIC-2 agnostic-F5 语义缝二选一**（spike TRIAGE 移交）：lifecycle:1393-1402 对 GHOST_AGNOSTIC F5 走无条件 attach 但 delegate:8050 拒空条件 → fail-closed。落地 F5 时二选一：delegate 支持空条件（改 sealed 文件）或 lifecycle 禁 agnostic F5 进 step_8。与 RFC-002 同批处理。

**PIC-3 E3 预算 env 化 ✅已落地(2026-07-11 凌晨,`b9fcca9`)**（spike 规格原 §2 遗留）：`EXACT_CUT_FRAMEWORK_ATTACH_BUDGET=2000` 硬编码（benders_loop.py:946）→ env 可配。碰 benders_loop sealed 文件=reseal 链；新增 EXACT_* env=allowlist+lock+tests 三同步（CLAUDE.md §6 铁律）。小批次,可先行。

**PIC-4 跨 solve cut 池演化实测**（spike 效度边界 #5）：campaign 多 rect 序列下 cut 生成→scope 检查→attach→anchor 切换退役（M4-A ghost conditioning）的端到端行为从未在 prod-scale 实测。依赖 PIC-0 宿主。

**PIC-5 benders 循环编排路径验证**：spike 直调 step_8 绕过了 `_maybe_attach_framework_cuts` 的 step5→6→7→8 完整编排与 2000 预算路径;通电前须在宿主内验证门控编排本身（含 rejection taxonomy 计数落 telemetry）。依赖 PIC-0。

**PIC-6 replay 诊断 subset 残留清理**（cut 修复批 TRIAGE）：生产不可达,顺通电批一并清。

**PIC-7 M5 独立前置 ✅已归因关闭(2026-07-11 凌晨,M5 A/B 四刀)**：「默认参数病态」证伪——smoke#4 死于当时的 42G+禁 swap 条款(<60G 尖峰),双变量混杂误读;修订条款(62G)下完整默认组合 fixed+p3+s3 OPTIMAL@649s(+26.4% wall)。通电对照可直接用生产默认参数,残余仅为 +26% 性能注记(优化机会,非阻塞)。证据 `../p1_3_m5_convergence_20260708/m5_ab_param_bisect_20260711.md`。

## §2 批次划分建议

- **批 A（可立即,不依赖 PIC-0）**：PIC-3 ✅（`b9fcca9`）；PIC-6 明确改为搭车项——单独为纯卫生残留做 reseal 轮不值,留给下一个碰 lifecycle.py 的批（C/D）顺带。
- **批 B（设计评审）✅完成(2026-07-11)**：PIC-0 owner 拍板=(a) certified promote 路线；PIC-1.1 评估成文+双审定稿。
- **阶段 B 工程批（通电线主线,规格书✅定稿 2026-07-11)**：`../cut_framework_review_gpt56pro_20260710/03_stage_b_implementation_spec.md`（v3,codex 三条侦察供料+两轮 opus/codex 双审 53 条全采纳）。批次序列 **B0 ✅落地(`de2df50`,AST 守卫立即生效+12 condition 哨兵)** → **B1 ✅落地(2026-07-11,bundle+snapshot 层+digest v1,双审 codex 主动攻击实证 8 项修复全落,两新 TCB 文件 floor 注册+checker 自钉)** → **B1.5 ✅落地(2026-07-11,typed 平台层:三分支代数+FamilyPlugin/registry+纯函数单入口+F5 全通路 oracle 复验+v1 adapter;双审 opus 4 LOW/codex 18 条含 10 BLOCK,8 组修复全落——F5 语义等价锚/SemanticCutRejection 异常边界/16-hex rehash 删除/quarantine 拒绝/registry 跨表钉;reseal 三层连锁:typed_platform 进 sink 台账 65→66+语义投影 floor 双写+runtime anchor(certified_artifact_contract)同步+checker 自钉;全 cuts 589;遗留:CutScope 无 raw preimage→v1 adapter scope identity fail-closed,B2 开工时 producer 侧补 raw preimage)** → **B2 ✅落地(2026-07-11,F1 纵切:ScopeIdentityPreimageV1 carrier 进 CutScope(方案 A,oracle 同读取捕获+adapter 16-hex 防伪核对全量先行)+assumptions snapshot-native 复验前移(无条件,版本 seam 不得绕过)+MasterDomainProjectionV1 snapshot 侧投影含 slot 身份+F1→COMPILABLE+四层 differential 含双拒 tamper matrix;codex 侦察三缝拍板先行+双审 opus 2 LOW/codex 6 条全落(含三项 accept-set 收窄追认);实现中途 codex 连接中断由主会话接管修复;五 pinned 文件 reseal+新 plugin region_capacity_typed.py 进 floor+mypy gate;全 cuts 638;B3 前置:semantic fingerprint 编码提案随 B3 双审把关)** → **B3 ✅落地(2026-07-11 午后,F6 纵切:shape_packing_hall_typed plugin(14 字段+legacy 12-phase snapshot-native 复验+fingerprint 照 F1 编码定格)+oracle preimage 单次捕获(恒 ghost-bound,无 agnostic 政策)+独立 F6 MasterDomainProjectionV1+registry 翻 COMPILABLE+借名机制测试统一迁 cutset(F2 永久 diagnostic,B4 不再撞);codex 主会话 fan-out 三路侦察(codex 通道中断期)+九项拍板先行,codex 新 thread 实现+双审 opus 2(计划内 reseal)/codex 7 条全落——literals=() 放宽洞(真 BLOCK,adapter framing 前拦截)+requires_ghost_bound 声明式字段(VALIDATED 出口跳检封死)+accept-set 差异表补齐立完备性义务+两处测试锁错攻击点修正;修复中新收窄 stale-exterior currentness 追认;全 cuts 707;reseal:v99 floor 三重钉+新 plugin 入 floor+sink 双更新+自钉)** → **B4 ✅落地(2026-07-11 傍晚,F7 纵切:power_hitting_set_typed plugin(八段复验 snapshot-native 平价+pole_radius int/float 归一)+oracle preimage 捕获+requires_ghost_bound=True+独立 F7 projection 含 canonical coverer rows+blocked digest 公共原语 blocked_cells_digest_v1(三消费者统一)+13 行 accept-set audit 表;侦察 codex 八问+九项拍板先行(两个条件拍板:slot 恒 0 保留+bundle raw 补检查);实现 codex 中断由主会话接管;双审 opus 1 BLOCK(计划内 reseal)+2 LOW/codex BLOCK 1+HIGH 1+MEDIUM 1——JSON-native TOCTOU+冻结层宽容真放宽洞(list→tuple 漂移 legacy 拒 typed 过,双复现)修复=单次原子冻结遍历+source-capture 读取点收严;修复由主会话执行;全 cuts 777;reseal:v99 floor 四重钉+新 plugin 入 floor+sink 双更新+自钉)** → B5(wiring cut-over,≈16 pinned 文件 reseal,PIC-6 搭车)→B6(promotion=owner)。
- **批 C（实测,依赖 B）**：PIC-4+PIC-5。
- **批 D（F5 线,可与 C 并行）**：PIC-1.2+PIC-2。
- **批 E（账本）**：PIC-1.3。
- promote 仪式（owner-only）压轴。

## §3 明确不做（边界）

- 不在本线内做 cut 数学有效性升级（F 族语义归数学面/Fable5 负责人地盘）。
- 不做 F8（已退役）与 F2/F4/F9 未接线族的 step_8 接线（`NotImplementedError` fallback 保持,接线归各族落地批）。
- 不做吞吐/容量流(OUT-OF-SCOPE,PROJECT_LOCK §1A B)。
