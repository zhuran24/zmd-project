# P1.2 闭合证据台账 (living, CC 维护)

> 目的: 给 owner 的手动闭合决策 (`phase_1_2_spike_close` gate, 计数权在 owner) 提供**系统性、可核查**的证据汇总。本文件只汇总与指路, 不重复论证细节 (逐项有归档指针)。闭合判据 = 连续独立全审零 finding (owner 计数) + 验证加固阶梯交叉确认。
> 最后更新: 2026-06-12 05:15 (自主夜班)。**当前诚实结论: P1.2 尚不可闭合** — preprocess 面刚爆出 2 个真 finding, 修复在途。

## 一、按面滚动续审状态 (tier ③, 饱和判据 = 每面连续 2-3 轮独立零 finding)

| # | 面 | 轮次史 | 零 finding 连击 | 状态 |
|---|---|---|---|---|
| 1 | Benders/LBBD 主循环 | 算法审 1 轮 (A-1/A-2 → 已修) + 修复确认 2 轮零 | 2 | 接近饱和 |
| 2 | 几何 master | 算法审 1 轮 (B-01 → 已修) + 再审 1 轮 (2 finding → 已修) + 确认 1 轮零 | 1 | 续审中 |
| 3 | routing + guard/lazy cut | P0-1 双层修复 + lazy cut 双独立零 finding + guard 完整性 1 轮 (审出对偶条件类缺陷已修*) | 见注 | 审得最透 |
| 4 | cuts 机制 (F1-F9/PCR) | 算法审 1 轮 (C-3/C-4 latent, 非公开路径) | 0 (latent 待办挂账) | 待续审 |
| 5 | preprocess 链 | 第 1 轮 (2026-06-12): F-01 P0 + F-02 P1 已验真; **完整修复已验收落地 (commit fbb0466, 全量 2900 passed 史上首次全绿)** | **0** | **确认轮在途 (round 2, 会话 6a2b34fc)** |
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

1. ~~preprocess F-01/F-02 完整修复落地~~ ✅ (commit fbb0466, 2026-06-12 清晨; 全量 2900 passed 首次全绿)。**当前在途 = 其零 finding 确认轮 (round 2)**, 通过才按安全修复完整性计完成。
2. preprocess 面修复后续审至饱和 (≥2 连零)。
3. 面 6/7/8 各自首轮 + 饱和。
4. 面 4 latent 待办 (C-3 F2 容量 / C-4 readiness gate blocker) 处置或显式划出 P1.2 范围 (owner 决策)。
5. 交互缝专项轮。
6. owner 按手动计数 gate 做闭合宣布。

## 五、已收口的大项 (证据指针)

- 3 真 P0 (A-1/B-01/A-2) 修复 + 两轮外审收口: commits 415c0c0/eb016ef/863f6d2, 归档 `cc_context/review/algofix_p0_*`。
- P0-1 lazy connectivity cut: commit 1876a6e, 双独立零 finding (`algofix_p0_1_lazycut_review_r1a/r1b_20260612.md`)。
- preprocess 面 round-1 审查交付: `cc_context/review/algoaudit_preprocess_face_r1_*` (commit a716173)。
- 单一 living 现状源: `_cc_live_memory/handoff_windows_ninth_review_pending.md` (stamp #4 为当前)。
