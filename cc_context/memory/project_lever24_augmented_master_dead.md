---
name: lever24-augmented-master-dead
description: "2026-05-20: augmented master Candidate D (lever 24) Phase 3 cheap gate NO-GO. 单 anchor (22,28) 27×15 single-commodity 实测: 603.9s UNKNOWN + RSS 32 GB (cap 12 GB 2.6x over) + cstr 2.68M (cap 650K 4x over). root cause: pose-bool master 280K pose vars × 8 ports/pose = 2.36M OnlyEnforceIf 约束. 进一步 confirm 用户 hypothesis: pose-bool master form 自身 scale 是 fundamental 限制"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

# Lever 24 Augmented master Candidate D 实测死路

## 实测核心数字

| 维度 | base | augment Δ | total | cap | verdict |
|---|---|---|---|---|---|
| build wall | 27.8s | +8.6s | 36.4s | n/a | ok |
| vars | 284,757 | +22,516 | 307,273 | ≤250K | 1.2x over |
| **constraints** | 279,233 | **+2,403,159** | **2,682,392** | ≤650K | **4x over** |
| solve wall | n/a | n/a | **603.9s UNKNOWN** | ≤600 | **超 budget** |
| **RSS peak** | 4.9 GB | +27.3 GB | **32.3 GB** | ≤12 GB | **2.6x over** |

augment 增的 2.36M 约束几乎全是 `u[front_cell] == 1 OnlyEnforceIf(x_var)` 形式
(u_force_constraints = 2,358,534).

## Root cause: pose-bool master scale × per-port channeling

pose-bool master 有 **280,444 pose vars** (mandatory x_vars 大头 + ro_vars). 每 pose 平均
8.4 ports (forced_port_count 2.36M / 280K pose).

augmented master 想让 master 同时考虑 placement + flow, 必须 channel: 当 pose x_{i,p_i}
选则 force port front_cell 上 u=1. 这是 N_pose × N_ports_per_pose 量级 OnlyEnforceIf.

CP-SAT 在 2.68M cstr scale 下 presolve + solve 不能 600s 收敛, UNKNOWN.

## 为啥 multi-commodity 必死

单 commodity aggregation 实测就 dead (2.36M cstr). 真 D2 paradigm 用 multi-commodity (~10
commodity), channel 数 × commodity = ~24M cstr — 显然不可能解.

## 不可减的 lever

1. **减 pose_data_count** (280K → 30K): 等于 master 内 pose 预筛, 破坏 exactness
   (PROJECT_LOCK 禁)
2. **减 ports_per_pose** (8.4 → 2): 改 source-of-truth facility 定义, 不可
3. **减 commodity_count** (10 → 1): 实测 single 也 dead

## 跟 Path 16 GOC-C2 同 paradigm 死法 (但不同 vars)

- Path 16 (lever 22): 全图 owner-optional + virtual terminal, **vars 大头** (~1.5M scale)
  Phase 0 build 30 min unfinished, RSS 25 GB.
- Lever 24: 全图 commodity flow 进 master, **cstr 大头** (~2.7M solve cstr)
  Phase 3 solve 600s UNKNOWN, RSS 32 GB.

两个 paradigm 不同 scale 维度爆 (vars vs cstr), 但都尝试"升 master form 跨 pose-bool 表达力
限制". GPT v7 Proposition 2 "全图建模 → 资源/wall dead end" 论证两次 confirm.

## 24 lever 累计 verdict

L1-L16 (前 session 14 lever) + Path 12 RAB-SEP + Path 13 SAC-Hull + Path 14 PCR-CUT +
Path 15 PGW-UB + Path 16 GOC-C2 + Path 17 D2 sub-problem + **augmented master Candidate D
(lever 24)** = **24 lever 全 verdict 死**.

## 进一步 confirm 用户 hypothesis

用户 hypothesis (2026-05-20): pose-bool master form 自身是 fundamental 限制. Lever 24
**实测 root cause 明确**:
- 不是 cut form 太弱 (sub-problem 路径死法)
- 不是数学复杂度不够 (D2 比 RAB-SEP 复杂)
- 是 **pose-bool master 自身 scale** (280K x_vars) 使任何 channel 都撞墙

要 break 必须 **换 master form**, 但 v7 Proposition 2 + Path 16 实测论证: 任何 routing-aware
master form 都撞 3 类资源 dead end.

## paradigm investigation 现状

paradigm investigation 在 **pose-bool master + 可计算 encoding 范畴内现穷尽**. 24 lever 全
verdict 死. 剩下候选:
- 算法 paradigm research 级方向 (未知压缩 proof system) — 数学领域研究
- 数据集变更 (改 problem 不是改 solver)
- 接受 paradigm investigation 完结, 项目 scope 转换

## 投资 vs 验证 ROI

- 1h Claude (probe 写 30 min + run 10 min wall + verdict 25 min)
- 验证 valor: pose-bool master 自身 scale 是 fundamental 限制, 给出**实测 root cause 证据**
  补强用户 hypothesis. 进一步 close paradigm investigation 范围.

## commit

未 commit. 待 commit files:
- `paths/17_candidate_d_commodity_flow/phase3_augmented_master_probe.py`
- `paths/17_candidate_d_commodity_flow/phase3_augmented_master_stats.json`
- `paths/17_candidate_d_commodity_flow/phase3_verdict.md`

## Related

- [[d2-path17-verdict]] — Path 17 D2 sub-problem (lever 23) 同 paradigm 子路径死法
- [[goc-phase0-verdict]] — Path 16 GOC-C2 (lever 22) 同 paradigm RAM 爆
- [[augmented-master-candidate-d-pickup]] — pre-execution pickup (上次 session 起跑点)
- [[subproblem-vs-augmented-master-default]] — 区分 sub vs augmented 教训
- [[2026-05-16-session-final-state]] — 23 lever 累计前 verdict
- v7 Proposition 2 — 资源 dead end 3 类论证
- MASTER_FORM_BASELINE.md — pose-bool 表达力 limits
