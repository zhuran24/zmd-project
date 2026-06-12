# P1.2 闭合证据台账 (living, CC 维护)

> 目的: 给 owner 的手动闭合决策 (`phase_1_2_spike_close` gate, 计数权在 owner) 提供**系统性、可核查**的证据汇总。本文件只汇总与指路, 不重复论证细节 (逐项有归档指针)。闭合判据 = 连续独立全审零 finding (owner 计数) + 验证加固阶梯交叉确认。
> 最后更新: 2026-06-12 09:55。**当前诚实结论: P1.2 尚不可闭合** — preprocess 面 r5 确认轮**零 soundness finding** (wireless 修复链 F-01..F04-R4 收口, 面计第 1 个干净轮, 距饱和还差 1-2 连零); 面 6/7/8 未开; 面 4 latent 挂账。

## 一、按面滚动续审状态 (tier ③, 饱和判据 = 每面连续 2-3 轮独立零 finding)

| # | 面 | 轮次史 | 零 finding 连击 | 状态 |
|---|---|---|---|---|
| 1 | Benders/LBBD 主循环 | 算法审 1 轮 (A-1/A-2 → 已修) + 修复确认 2 轮零 | 2 | 接近饱和 |
| 2 | 几何 master | 算法审 1 轮 (B-01 → 已修) + 再审 1 轮 (2 finding → 已修) + 确认 1 轮零 | 1 | 续审中 |
| 3 | routing + guard/lazy cut | P0-1 双层修复 + lazy cut 双独立零 finding + guard 完整性 1 轮 (审出对偶条件类缺陷已修*) | 见注 | 审得最透 |
| 4 | cuts 机制 (F1-F9/PCR) | 算法审 1 轮 (C-3/C-4 latent, 非公开路径) | 0 (latent 待办挂账) | 待续审 |
| 5 | preprocess 链 | r1: F-01/F-02 → fbb0466; r2: F-03 → b7d2115; r3: F03-R3-01 (RAB build-time 侧门, env 潜伏) + H03-R3-02 (dual-role 语义守卫) → 51c5f90; **r4 (front 消费点全仓穷举轮, owner 手动发) 又出 4 组 residual 已修复落地**: F04-R4-01 (preprocess_context 直构路径绕过 dual-role 守卫 → 双层 fail-closed) + F04-R4-02 (deletion-core raw oracle, env `EXACT_B1_DELETION_CORE_CUT`) + F04-R4-03 (pose-bool master 四处 raw port/front: PORT_ACTIVE/CLEARANCE_HARD/blocking-cell/lazy-demand, env 门控) + F04-R4-04 (SAC/L2/dynamic separator 把 routing-free 终品当 routed source)。验收: 2 probe unpatched 复现 + patched 翻转, 行为级判别 (separator 分类 probe + pose-bool :303/:926 现场), 全量 **2908 绿** (+5 回归), preflight 20/20, lock/spec 消费点清单扩列; **r5 确认轮 (包 e676c94d, owner 手动发) 零 soundness finding** — 4 组修复逐处 file:line 复核 + r4 穷举清单独立复核同意 (port_exposure_oracle 零生产调用 / flow diagnostic 不作 proof, CC grep 抽查二者属实) + r2/r3/r4 交互复核 + 文档清单与代码一致; 归档 `algoaudit_preprocess_face_r5_REVIEW_20260612.md` | **1** | **wireless 修复链收口 ✅; 面续审至饱和 (还差 1-2 连零)** |
| 6 | binding 建模忠实度 | 未审 (C 轮只审了 cut 不是 binding 数学) | — | 排队 |
| 7 | campaign/resume 状态机 | 未审 | — | 排队 |
| 8 | parallel scheduler 合并 | 未审 | — | 排队 |

\* 面 3 注: 2026-06-12 凌晨的 guard 完整性/电力见证轮所发现项的处置与判读细节在 CC 工作区台账 (刻意不入仓库), 对应盲区回归已落仓 (`test_p0_certified_soundness_fixes.py`, commit c2e7394)。

横切: 路 A (伪造交付面) 已由 V81-V98 deny-unknown 19 轮横扫至封闭契约, 不在上表;「跨子系统交互缝」专项轮排在面 5-8 各自首轮干净之后。

## 二、差分对拍 fuzz (tier ②, 机械验证, 不受 reviewer 能力上限约束)

| 切片 | 覆盖 | 结果 | 工具 |
|---|---|---|---|
| 1 | routing 全局连通 + cell-layer capacity + port exact-one (A-1 类及端口履行/容量类) | 累计 750 随机实例 0 不一致 (强化 oracle 后 450; oracle 含 3 个 self-test 必抓案例: dead-end/容量超载/有效流) | `cc_context/verification/diff_fuzz/routing_connectivity_diff.py` |
| 2 | master no-overlap/bounds/电力 (B-01 类) 正向 + false-INFEASIBLE 反向 | seed 0-17 共 ~1400 实例 0 不一致 (反向经 master-pinned 二次裁决, 40 个 ghost 占满假阳性全过滤) | `cc_context/verification/diff_fuzz/master_geometry_diff.py` |
| 待做 | binding oracle / wireless 修复落地后按新几何重跑全部切片 | — | — |

方法论要点 (审计可复核): 独立验证器零共享被测代码路径; reverse 方向因 ghost 矩形可行性 oracle 不可独立重写, 用「嫌疑 witness pinned 重喂 master」自裁, 只有 pinned-FEASIBLE 才计真 over-cut。

## 三、审查能力校准 (tier ①)

已完成一轮, 结果支持「此前零 finding 轮可信」(对已校准的子系统与缺陷形态)。细节/台账在 CC 工作区与 harness memory, **刻意不入仓库不入包**。边界: 跨子系统多步交互形态未校准 (排期: 面 5-8 首轮干净后做交互专项)。

## 四、当前阻塞闭合的事项 (按序)

1. ~~wireless 修复链 (F-01/F-02 → F-03 → F03-R3 → F04-R4 → r5 零 finding 确认)~~ ✅ **收口** (fbb0466 / b7d2115 / 51c5f90 / c7f3bb5 + r5 干净轮)。r5 留 3 条 non-blocking 备注挂账 (非 soundness): ① 根目录裸 pytest 会误收集 `补丁包/` 归档重复测试 (日常用 `src/tests` 限定); ② PCR candidate scoring 仍用 raw front cluster + 未传 routing-free set 的 SAC pressure (仅影响候选排序效率, patch proof 走 filtered port_specs + replay); ③ flow_subproblem / heuristic_feasible_finder 内残留 raw port 逻辑 (diagnostic / 非 certified 主链)。
2. **当前在此: preprocess 面续审至饱和** (连零 1/2-3, 下一轮换非 wireless 角度审 preprocess 链其余面)。
3. 面 6/7/8 各自首轮 + 饱和。
4. 面 4 latent 待办 (C-3 F2 容量 / C-4 readiness gate blocker) 处置或显式划出 P1.2 范围 (owner 决策)。
5. 交互缝专项轮。
6. owner 按手动计数 gate 做闭合宣布。

## 五、已收口的大项 (证据指针)

- 3 真 P0 (A-1/B-01/A-2) 修复 + 两轮外审收口: commits 415c0c0/eb016ef/863f6d2, 归档 `cc_context/review/algofix_p0_*`。
- P0-1 lazy connectivity cut: commit 1876a6e, 双独立零 finding (`algofix_p0_1_lazycut_review_r1a/r1b_20260612.md`)。
- preprocess 面审查交付链: r1 `cc_context/review/algoaudit_preprocess_face_r1_*` (commit a716173); r2 `algoaudit_preprocess_face_r2_REVIEW_20260612.md` + `algofix_preprocess_F03_routing_free_leak.patch`; r3 `algoaudit_preprocess_face_r3_REVIEW_20260612.md` + `algofix_F03_r3_residual.patch`; r4 `algoaudit_preprocess_face_r4_REVIEW_20260612.md` + `algofix_F04_r4_residual.patch`。
- 单一 living 现状源: `_cc_live_memory/handoff_windows_ninth_review_pending.md` (stamp #4 为当前)。
