# Path 17 Phase 3 — Augmented master Candidate D cheap gate verdict (2026-05-20)

## 终态

❌ **NO-GO**. 单 anchor (22,28) 27×15 augmented master single-commodity probe:
- solve status **UNKNOWN** at 603.9s (超 600s budget)
- RSS peak **32.3 GB** (> 12 GB cap 2.6x)
- total_cstr **2.68M** (> 650K cap 4x)

augmented master Candidate D paradigm (lever 24) 撞 pose-bool master scale 墙.

## 实测数字

| 维度 | base (pose-bool 原) | augment Δ | total | cap | verdict |
|---|---|---|---|---|---|
| build wall | 27.8s | +8.6s | 36.4s | n/a | ok |
| vars | 284,757 | +22,516 (4900 u + 17616 e) | **307,273** | ≤250K | over 1.2x |
| constraints | 279,233 | **+2,403,159** | **2,682,392** | ≤650K | **over 4x** |
| - u_block | - | 4,493 | - | - | - |
| - u_force OnlyEnforceIf | - | **2,358,534** | - | - | **dead end** |
| - channeling implications | - | 35,232 | - | - | - |
| - flow conservation eq | - | 4,495 | - | - | - |
| solve wall | n/a | n/a | **603.9s UNKNOWN** | ≤600 | **超 budget** |
| RSS peak | 4,906 MB | +27,352 MB | **32,258 MB** | ≤12,288 | **2.6x over** |

## Root cause: pose-bool master scale × per-port channeling

**核心**: pose-bool master 有 **pose_data_count = 280,444** (mandatory x_vars + ro_vars 总和).
每 pose 平均 8.4 ports (forced_port_count 2,358,534 / pose 280,444 = 8.4). per-port channel
`u[front_cell] == 1 OnlyEnforceIf(x_var)` 展开为 2.36M OnlyEnforceIf 约束.

CP-SAT 在 2.68M cstr scale 下 presolve 后仍无法 600s 收敛, 退 UNKNOWN.

## 为啥这是 paradigm 级 dead end

augmented master Candidate D 的核心 propose:
- master 内置 D2 vars (u + e)
- 通过 pose vars (x_{i, p_i}) 跟 master placement 决策 channel
- master.solve 自己 search 时同时考虑 placement + flow feasibility

但 channel 的代价是 **pose_count × ports_per_pose × commodity_count** 量级 OnlyEnforceIf
约束:
- 单 commodity: 2.36M (实测)
- 真 multi-commodity (~10 commodity): ~24M (推算)

24M cstr 显然不可能在 master 时间 budget 内解.

**减 scale 的 lever 全 inactive**:
1. **减 pose_data_count** (280K → 30K): 等于在 master 里做 pose 预筛 — 但筛会破坏 exactness
   (PROJECT_LOCK 禁)
2. **减 ports_per_pose** (8.4 → 2): 每 facility 强行减 ports = 改 source-of-truth, 不可
3. **减 commodity_count** (10 → 1): single-commodity 已实测 still dead

## 跟之前 paradigm 的关系

Path 16 GOC-C2 (lever 22) 是 **全图 owner-optional + virtual terminal** form, Phase 0 cheap
gate 撞 RAM 爆 (~25 GB). Lever 24 是 **全图 commodity flow 进 master** form, Phase 3 cheap
gate 也撞 RAM 爆 (32 GB) + UNKNOWN.

两个 paradigm 不同 sub-problem 数学结构, 但都尝试**升 master form 跨 pose-bool 表达力限制**.
两个都撞 GPT v7 Proposition 2 论证的 "全图建模 → 资源爆/wall 爆" dead end.

**24 paradigm/lever 累计** (前 23 + augmented master Candidate D):
- L1-L16 (前 session): 14 lever
- Path 12 RAB-SEP / Path 13 SAC-Hull / Path 14 PCR-CUT / Path 15 PGW-UB / Path 16 GOC-C2 /
  Path 17 D2 sub-problem (前 5 paradigm)
- **Path 17 augmented master Candidate D** (lever 24)

## 进一步 confirm 用户 hypothesis

用户 hypothesis (2026-05-20 凌晨, Path 17 sub-problem verdict 后提出):

> 是不是 Path 01 突破时选的 pose-bool master form 把后续所有 paradigm 路堵了?

Lever 24 实测进一步 confirm:
- pose-bool master 自身 scale 大 (280K x_vars 全 enumeration)
- 任何想 channel routing/flow 进 master 的 paradigm 都被这个 scale × ports × commodity
  乘积爆掉
- 这是 **pose-bool master form 的 fundamental 限制**

要 break 必须**换 master form** (e.g. coordinate-based with on-the-fly pose generation,
或者 separated layer model), 但 v7 Proposition 2 论证 + Path 16 实测 + Path 08 历史: 任何
routing-aware master form 都撞 3 类资源 dead end.

## 留下的 infrastructure

- `paths/17_candidate_d_commodity_flow/phase3_augmented_master_probe.py` — probe script
- `paths/17_candidate_d_commodity_flow/phase3_augmented_master_stats.json` — 实测数据

不留 production code: 没有 src/ 改动, env-gated paradigm 全在 probe script local.

## 投资 vs 验证

- 总投资: ~1h Claude (probe 写 30 min, run 10 min wall, verdict 25 min)
- 验证 valor: confirm augmented master Candidate D 跟 sub-problem 同质死法, 而且 root cause
  在 master 自身 scale (不是 cut form), 给出**为啥 pose-bool master 形成 fundamental
  limit 的实测证据**

## paradigm investigation 现状

24 lever 全 verdict 死. paradigm framework 内已穷尽:
1. ✅ Cut framework 子路径 (Path 12-15, Path 17 sub-problem) — cut 表达力被 pose-bool 限制
2. ✅ 全图建模 (Path 16, augmented Path 17) — RAM/wall 爆
3. ❌ 换 master form (coordinate / separated layer / on-the-fly) — 全在 v7 Proposition 2
   3 类资源 dead end 范围
4. ❌ 放松严格性 (L11 / ε-certified / 分布式) — 用户拒绝

剩余 untested 候选 (按 ROI 排序):
- (低 ROI) 算法 paradigm research 级方向 ("未知压缩 proof system") — 数学领域研究
- (中 ROI) 放宽 paradigm 严格性, 重启 set-packing prover 等 paradigm investment — 用户拒绝
- (中 ROI) 数据集变更 (社区 blueprint 扩, 替换 mandatory facility 类型) — 改 problem 不是
  改 solver
- (高 ROI) 改方向: 接受 paradigm investigation 在 known encoding 范畴 完结, 项目转换 scope
  或 accept current state

## commit

待 commit. base files:
- `paths/17_candidate_d_commodity_flow/phase3_augmented_master_probe.py`
- `paths/17_candidate_d_commodity_flow/phase3_augmented_master_stats.json`
- `paths/17_candidate_d_commodity_flow/phase3_verdict.md`

## Related

- [[project-d2-path17-verdict]] — Path 17 D2 sub-problem 同 paradigm sub-problem 路径死法
- [[project-goc-phase0-verdict]] — Path 16 全图 owner-optional 同 RAM 爆 pattern
- [[project-augmented-master-candidate-d-pickup]] — Phase 3 pre-execution pickup notes
- [[feedback-subproblem-vs-augmented-master-default]] — 教训 (本次实施 cause)
- v7 Proposition 2 (`b1_phase6_review_package_v7.zip`) — 资源 dead end 3 类论证
- MASTER_FORM_BASELINE.md — pose-bool master 表达力 limits 论述
