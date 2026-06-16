# L23 — Augmented Master Candidate D (Today 2026-05-20)

## 当时项目情况

23 lever 累积全死. Path 17 D2 sub-problem 死后, user 上次 session 终态 sharp 抓出: **600s wall 完全没用上**, master 仍 pose-bool 100s OK + D2 0.15s 完. user 把"augmented master Candidate D" identified 为唯一 untested.

## 为什么走这条路

augmented master Candidate D: master **内置 D2 vars** (u + e + flow conservation), wall budget 放 10x (600s). paradigm 真**换 master form** (不只换 sub-problem).

理论上区别:
- Path 17 D2 sub-problem: master 不变 (pose-bool), D2 后台跑 INFEASIBLE → cut 反馈
- L23 augmented: D2 vars 进 master 同 model, master.solve 自己 search

之前 23 lever 全在 pose-bool master + cut framework, 这是**真 untested** paradigm path.

## 实验过程

Phase 0 cheap gate single-commodity simplified version (commit `5469885`):
- 写 `paths/17_candidate_d_commodity_flow/phase3_augmented_master_probe.py`
- 单 anchor (22,28) 27×15
- `EXACT_USE_POSE_BOOL_MASTER=1` + bolt-on D2 vars + 600s wall budget
- 实测

## 实验结果

| 维度 | base (pose-bool) | augment Δ | total | cap | verdict |
|---|---|---|---|---|---|
| build wall | 27.8s | +8.6s | 36.4s | n/a | ok |
| vars | 284,757 | +22,516 | 307,273 | ≤250K | over 1.2x |
| **constraints** | 279,233 | **+2,403,159** | **2,682,392** | ≤650K | **over 4x** |
| solve wall | n/a | n/a | **603.9s UNKNOWN** | ≤600 | **超 budget** |
| **RSS peak** | 4,906 MB | +27,352 MB | **32,258 MB** | ≤12,288 | **2.6x over** |

augment 增的 2.36M 约束几乎全是 `u[front_cell] == 1 OnlyEnforceIf(x_var)` (u_force_constraints = 2,358,534).

**multi-commodity 推算**: ~10 commodity × 2.36M = ~24M cstr — 物理不可能解.

## 经验跟教训 (含瓶颈理解更新)

- **Root cause 实测**: pose-bool master **280,444 pose vars × 平均 8.4 ports/pose = 2.36M OnlyEnforceIf channel 约束**. CP-SAT 2.68M cstr 600s 不收敛.
- **减 scale 全 inactive**:
  - 减 pose_data_count → 破坏 exactness (PROJECT_LOCK 禁)
  - 减 ports_per_pose → 改 source-of-truth (不可)
  - 减 commodity_count → single-commodity 实测已 dead
- **瓶颈理解更新 (今天关键 update)**: **pose-bool master 自身 scale 是 fundamental 限制**. 不是 cut form 弱, 不是数学复杂度不够, 是 master pose vars 数本身 (280K).
- **跟 Path 16 GOC-C2 同 paradigm 死法不同 scale 维度**:
  - Path 16 vars 爆 (1.5M, RSS 25 GB)
  - L23 cstr 爆 (2.7M, RSS 32 GB)
  - 两次实测 confirm GPT v7 Proposition 2 "全图建模 → 资源/wall dead end" 论证 (vars / cstr 2 类资源)

## code/

- `code/` 含 phase3_augmented_master_probe.py (实施 today) + phase3_augmented_master_stats.json + phase3_verdict.md
