# P1.2 闭合证据台账 (living, CC 维护)

> 目的: 给 owner 的手动闭合决策 (`phase_1_2_spike_close` gate, 计数权在 owner) 提供**系统性、可核查**的证据汇总。本文件只汇总与指路, 不重复论证细节 (逐项有归档指针)。闭合判据 = 连续独立全审零 finding (owner 计数) + 验证加固阶梯交叉确认。
> 最后更新: 2026-06-12 16:20。**当前诚实结论: P1.2 尚不可闭合** — 面 6 首轮爆 2 HIGH (F-BIND-R1-01 latent 满额结构假设 / F-BIND-R1-02 loader fail-open, 修复已验收落地, 需确认轮); face 7/8 连零 1/2-3; preprocess 面连零 1/2-3; 面 4 latent 挂账; 交互缝专项轮未做。

## 一、按面滚动续审状态 (tier ③, 饱和判据 = 每面连续 2-3 轮独立零 finding)

| # | 面 | 轮次史 | 零 finding 连击 | 状态 |
|---|---|---|---|---|
| 1 | Benders/LBBD 主循环 | 算法审 1 轮 (A-1/A-2 → 已修) + 修复确认 2 轮零 | 2 | 接近饱和 |
| 2 | 几何 master | 算法审 1 轮 (B-01 → 已修) + 再审 1 轮 (2 finding → 已修) + 确认 1 轮零 | 1 | 续审中 |
| 3 | routing + guard/lazy cut | P0-1 双层修复 + lazy cut 双独立零 finding + guard 完整性 1 轮 (审出对偶条件类缺陷已修*) | 见注 | 审得最透 |
| 4 | cuts 机制 (F1-F9/PCR) | 算法审 1 轮 (C-3/C-4 latent, 非公开路径) | 0 (latent 待办挂账) | 待续审 |
| 5 | preprocess 链 | r1: F-01/F-02 → fbb0466; r2: F-03 → b7d2115; r3: F03-R3-01 (RAB build-time 侧门, env 潜伏) + H03-R3-02 (dual-role 语义守卫) → 51c5f90; **r4 (front 消费点全仓穷举轮, owner 手动发) 又出 4 组 residual 已修复落地**: F04-R4-01 (preprocess_context 直构路径绕过 dual-role 守卫 → 双层 fail-closed) + F04-R4-02 (deletion-core raw oracle, env `EXACT_B1_DELETION_CORE_CUT`) + F04-R4-03 (pose-bool master 四处 raw port/front: PORT_ACTIVE/CLEARANCE_HARD/blocking-cell/lazy-demand, env 门控) + F04-R4-04 (SAC/L2/dynamic separator 把 routing-free 终品当 routed source)。验收: 2 probe unpatched 复现 + patched 翻转, 行为级判别 (separator 分类 probe + pose-bool :303/:926 现场), 全量 **2908 绿** (+5 回归), preflight 20/20, lock/spec 消费点清单扩列; **r5 确认轮 (包 e676c94d, owner 手动发) 零 soundness finding** — 4 组修复逐处 file:line 复核 + r4 穷举清单独立复核同意 (port_exposure_oracle 零生产调用 / flow diagnostic 不作 proof, CC grep 抽查二者属实) + r2/r3/r4 交互复核 + 文档清单与代码一致; 归档 `algoaudit_preprocess_face_r5_REVIEW_20260612.md`; **r6 (非 wireless 角度, 包复用 e676c94d) 又出 1 HIGH — R6-F-01**: `preprocess_plan.json` 可静默同名覆盖 canonical recipe/target/commodity (probe: packaging_battery input_slots 3→1 静默接受 = 欠约束/false-CERTIFIED 方向) 且 plan 完全不在 exact campaign hash 闭包与 preflight 冻结登记 (同一 campaign hash 两种运行时端口语义)。**修复已验收落地**: builder 对三键 fail-closed (additive-only) + schema 收紧 + `OPTIONAL_EXACT_HASH_FILES` 纳 hash 闭包 (missing sentinel 保 synthetic) + CC 补 FROZEN_ARTIFACTS 登记与 lock/specs04/18/19/20 同步 (含纠正 specs18 "regeneration-only" 过时论断); probe 双向翻转, 全量 **2912 绿** (+4), preflight **21/21**; r6 其余 Q1-Q5 零 finding (demand 数学/池计数 66403 闭式吻合/profile 投影/确定性/三件一致性, 复核详尽)。归档 `algoaudit_preprocess_face_r6_REVIEW_20260612.md` + `algofix_R6_plan_hash_overlay.patch`; **r7 确认轮 (包 e8c7dac3, 干净 worktree 唯一名包) 零 soundness finding**: R6-F-01 修复逐项确认 (builder gate 全装载路径覆盖 / sentinel 形状不撞 sha256 / resume dict 全等 probe 验证 / binding 直读 plan 不消费三键且 bytes 已 hash 绑定) + **Q2 泛化穷举 16 类 runtime 输入面对照 hash 闭包无同类缝** (commodity_demands=diagnostic-only 留再审触发条件: 若未来 certified 分支在它上面; CC grep 抽查属实) + r6 数字抽查 (266/52 槽/池 hash) 全验证 + 2 条 DOC-LOW (01=plan metadata 措辞 stale, 动冻结工件不值挂账; 02=specs19 措辞, CC 已落地 spec-only 修复); 归档 `algoaudit_preprocess_face_r7_REVIEW_20260612.md` | **1** | **续审至饱和 (差 1-2 连零); 下一单建议 face 7/8 首轮** |
| 6 | binding 建模忠实度 | **首轮 (2026-06-12, 包复用 13dc4e59, 脚本全自动外发) 爆 2 HIGH 已修**: **F-BIND-R1-01** = generic output 槽 domain 无 `__unused__` 哨兵, 把 specs/04 §4.5「52=52 满额」数值巧合硬编码成结构假设 → 需求<槽数时合法空置被判 INFEASIBLE (false-INFEASIBLE → objective 级 false-CERTIFIED 方向)。**定性诚实**: 当前 active scope (R=S=52 满额) 下 latent, 不是 active bug; 与 C-1 refute **不冲突** (C-1 补丁改坏精确计数被禁是对的; 本修保留精确计数只加哨兵, 52=52 下计数逼满哨兵恒 0 行为零变化) — specs/03 多处「多余端口允许空置」证实规则层面空置合法。**F-BIND-R1-02** = generic IO/wireless 槽数 loader fail-open: 缺 section 静默空需求 (真实需求消失=false-FEASIBLE 方向) + int() 接受 bool/float 截断/字符串 + 不校验 canonical 商品角色 (中间品可冒充无线终品被吞, routing 不兜底)。修复: loader fail-closed (双 section 必须在场+严格非负整数+哨兵保留名+默认装载路径校验 source_kind/sink_kind) — 生产三调用点 (benders 主链:4909/retry:5813/heuristic finder) 全走 loader 路径实证受保护, 显式传参为 test-fixture-only。验收: 3 probe unpatched 复现 (F-01 INFEASIBLE / 缺 key 静默 / steel_block 被吞) → patched 翻转 2 个 + F-02-B 经 loader 路径篡改工件 probe 补证 ValueError → ruff 清 → 全量 **2923 绿** (+6 回归) → preflight 21/21 → lock 新增 F-BIND-R1-01/02 两条款 + specs/04 §4.5 实现注记 + specs/05 §5.4.3 generic output 对称段。挂账非 soundness: master_model.py 自有宽松 loader (`load_generic_io_requirements_artifact`) 未收紧 (binding 不靠它, 后续数据契约面统一); RAB 证书 union 非最小 (保守方向, 非缝)。归档 `algoaudit_binding_face_r1_REVIEW_20260612.md` + `algofix_FBIND_r1.patch` | 0 | r2 确认轮待发 |
| 7 | campaign/resume 状态机 | **首轮 (2026-06-12, 包 1ebcc03b) 爆 F78-F-01 HIGH**: 陈旧 candidate `solution` 穿越状态改写存活 (started 拷入 RUNNING + CERTIFIED(None) 继承旧 witness + 弱状态带 solution 不被校验拒) → 陈旧 witness 可过 resume 边界撑起 terminal 证据 = false-CERTIFIED 方向。**修复落地**: solution 仅 CERTIFIED 可携 + CERTIFIED 必须带新 witness + 强状态单调 (rerun 不降 RUNNING / 弱覆盖审计阻断 / 强冲突 raise) + resume 校验拒弱状态带 solution。probe 复现+四轴翻转, lock 新增 F78-F-01 条款; **r2 确认轮 (包 13dc4e59, 脚本全自动外发) 零 soundness finding**: F-01 修复逐处 file:line 复核 (入口/resume 栅栏 + started 强状态 no-op + result 单调语义) + 强→弱阻断跳过 cut/counter 更新判读为 completeness-only (counters 非证据判据, CC 同意) + **Q2 泛化穷举 campaign 全 writer 清单** (`exact_campaign.py` 7 writer + `outer_search.py` 6 直写点, 逐个判读无弱证据穿强缝) + 字段族 deny-unknown 边界复核; 非 finding 备注: 同 hash 旧版坏强记录无法自证 provenance 属固有限制 (新 writer 已不能生成)。归档 `algoaudit_campaign_scheduler_r2_REVIEW_20260612.md` | **1** | 续审中 (差 1-2 连零) |
| 8 | parallel scheduler 合并 | **首轮同包爆 F78-F-02 HIGH**: `results_by_seq` 只认 dispatch_seq 不校验候选身份 (setdefault 先到先得), outer_search 对未匹配结果走 prune_fill 兜底照写 campaign → 队列边界可注入"从未派发的候选"的结果。**修复落地**: 调度/消费双侧身份校验 (seq/attempt/candidate/key 全匹配), 重复/错配/errored 结果全弃, 畸形波次 → worker_process_failed/UNKNOWN 停机。probe 复现+翻转 (修后比 REVIEW 描述更保守: 错配波次同伴结果一并丢弃, 只伤完整性), lock 新增 F78-F-02 条款。验收: CC 修 1 个连带 (test_exact_contract 的 SimpleNamespace mock 缺 error 字段), 全量 **2917 绿** (+5), preflight 21/21; **r2 确认轮 (同包同轮) 零 soundness finding**: F-02 修复双侧复核 (scheduler `_worker_result_identity_violation` 四元组 + consumer `_parallel_wave_result_identity_failure` 独立二审, 普通收割/crash drain/尾部 drain 三路径无旁路) + **Q3 队列/序列化边界穷举 8 类** (task queue/READY/heartbeat/result queue/drain/wave 对象/telemetry/pickle round-trip, 逐个判读) + r1 抽查 (resume hash fail-closed / terminal export 守卫 / partial failure fail-closed 三声明复验成立); 非 finding 挂账: **task_fingerprint 纵深防御建议** (WorkerResult 身份四元组不含 epsilon/solve_mode/profile, 当前 queue 生命周期下无漂移路径, 属可选加固非缝)。CC 验收: 行号抽查 4 处精确命中 + 基线 e5e6d49→HEAD 源码零漂移 + 无降级 (21min 生成); 本轮无代码改动, 全量基线维持 2917 绿 | **1** | 续审中 (差 1-2 连零, 与面 7 同步) |

\* 面 3 注: 2026-06-12 凌晨的 guard 完整性/电力见证轮所发现项的处置与判读细节在 CC 工作区台账 (刻意不入仓库), 对应盲区回归已落仓 (`test_p0_certified_soundness_fixes.py`, commit c2e7394)。

横切: 路 A (伪造交付面) 已由 V81-V98 deny-unknown 19 轮横扫至封闭契约, 不在上表;「跨子系统交互缝」专项轮排在面 5-8 各自首轮干净之后。

## 二、差分对拍 fuzz (tier ②, 机械验证, 不受 reviewer 能力上限约束)

| 切片 | 覆盖 | 结果 | 工具 |
|---|---|---|---|
| 1 | routing 全局连通 + cell-layer capacity + port exact-one (A-1 类及端口履行/容量类) | 累计 **900** 随机实例 0 不一致 (含 F04-R4 落地后复跑 150, seeds 50-52) | `cc_context/verification/diff_fuzz/routing_connectivity_diff.py` |
| 2 | master no-overlap/bounds/电力 (B-01 类) 正向 + false-INFEASIBLE 反向; **生成器已加无线箱形态** (方形无端口单朝向, 镜像 post-F-01 协议箱几何) | 累计 **~1760** 实例 0 不一致 (反向 pinned 二次裁决累计滤 28 假阳性; 无线箱形态 168 实例, seeds 100-105) | `cc_context/verification/diff_fuzz/master_geometry_diff.py` |
| 待做 | binding oracle (难) | — | — |

方法论要点 (审计可复核): 独立验证器零共享被测代码路径; reverse 方向因 ghost 矩形可行性 oracle 不可独立重写, 用「嫌疑 witness pinned 重喂 master」自裁, 只有 pinned-FEASIBLE 才计真 over-cut。

## 三、审查能力校准 (tier ①)

已完成一轮, 结果支持「此前零 finding 轮可信」(对已校准的子系统与缺陷形态)。细节/台账在 CC 工作区与 harness memory, **刻意不入仓库不入包**。边界: 跨子系统多步交互形态未校准 (排期: 面 5-8 首轮干净后做交互专项)。

## 四、当前阻塞闭合的事项 (按序)

1. ~~wireless 修复链 (F-01/F-02 → F-03 → F03-R3 → F04-R4 → r5 零 finding 确认)~~ ✅ **收口** (fbb0466 / b7d2115 / 51c5f90 / c7f3bb5 + r5 干净轮)。r5 留 3 条 non-blocking 备注挂账 (非 soundness): ① 根目录裸 pytest 会误收集 `补丁包/` 归档重复测试 (日常用 `src/tests` 限定); ② PCR candidate scoring 仍用 raw front cluster + 未传 routing-free set 的 SAC pressure (仅影响候选排序效率, patch proof 走 filtered port_specs + replay); ③ flow_subproblem / heuristic_feasible_finder 内残留 raw port 逻辑 (diagnostic / 非 certified 主链)。
2. **当前在此: preprocess 面续审至饱和** — r7 确认轮零 finding ✅ (连零 1/2-3)。挂账非 soundness: DOC-LOW-01 (plan metadata 描述仍写 "optional future overrides", 修复需动冻结工件 hash 完整仪式, 为措辞不值——下次真有理由动 plan 时顺路改); commodity_demands.json 不在 hash 闭包 (当前 diagnostic-only 无需; **再审触发条件 = 未来任何 certified 分支依赖它**)。下一单建议 face 7/8 首轮 (brief 已预写, 包 e8c7dac3 复用), preprocess r8 之后再排。
3. ~~面 7/8 首轮~~ ✅ (2 HIGH 已修) → ~~面 7/8 r2 确认轮~~ ✅ **零 finding** (各计连零 1) → ~~面 6 首轮~~ ✅ (2 HIGH 已修, 见面 6 行) → **当前在此: 面 6 r2 确认轮** (点名 F-BIND 两修复为攻击面 + 泛化问「binding 还有哪些把当前 base 数值巧合硬编码成结构假设的位置」+ master_model loader 挂账复核); 之后 preprocess r8 / face 7/8 r3 轮换。
4. 面 4 latent 待办 (C-3 F2 容量 / C-4 readiness gate blocker) 处置或显式划出 P1.2 范围 (owner 决策)。
5. 交互缝专项轮。
6. owner 按手动计数 gate 做闭合宣布。

## 五、已收口的大项 (证据指针)

- 3 真 P0 (A-1/B-01/A-2) 修复 + 两轮外审收口: commits 415c0c0/eb016ef/863f6d2, 归档 `cc_context/review/algofix_p0_*`。
- P0-1 lazy connectivity cut: commit 1876a6e, 双独立零 finding (`algofix_p0_1_lazycut_review_r1a/r1b_20260612.md`)。
- preprocess 面审查交付链: r1 `cc_context/review/algoaudit_preprocess_face_r1_*` (commit a716173); r2 `algoaudit_preprocess_face_r2_REVIEW_20260612.md` + `algofix_preprocess_F03_routing_free_leak.patch`; r3 `algoaudit_preprocess_face_r3_REVIEW_20260612.md` + `algofix_F03_r3_residual.patch`; r4 `algoaudit_preprocess_face_r4_REVIEW_20260612.md` + `algofix_F04_r4_residual.patch`; r5 (零 finding 确认轮) `algoaudit_preprocess_face_r5_REVIEW_20260612.md`。
- wireless 修复链 (F-01..F04-R4) 全弧线收口: 5 轮收敛 (2 finding → 1 → 2 → 4 → 0), 每轮 brief 点名上轮修复为攻击面; 终轮独立穷举复核全部 raw port/front 消费点 + 交互 + 文档一致。
- face 7/8 审查交付链: r1 `algoaudit_campaign_scheduler_r1_REVIEW_20260612.md` + `algofix_F78_campaign_scheduler.patch` (2 HIGH); r2 (零 finding 确认轮) `algoaudit_campaign_scheduler_r2_REVIEW_20260612.md`。
- face 6 审查交付链: r1 `algoaudit_binding_face_r1_REVIEW_20260612.md` + `algofix_FBIND_r1.patch` (2 HIGH: 哨兵缺失 latent + loader fail-open)。
- 单一 living 现状源: `_cc_live_memory/handoff_windows_ninth_review_pending.md` (stamp #4 为当前)。
