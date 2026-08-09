# 01 — 项目当前完整状态 (2026-05-20)

## Problem 定义

游戏《终末地》(Arknights: Endfield) 工业规划器精确求解.

- **Grid**: 70 × 70 (4900 cells)
- **Mandatory facility instances**: 266 (固定数量 + 类型组合, 跨多 facility template 含 mining / refinery / assembler / storage_box / power_pole 等)
- **Pose per facility**: orientation (4 方向) × port_mode (2-3) → per facility 平均 ~10 poses
- **Optimization objective**: `max_lex(area, min_side)` — 找最大空白 rectangle 同时安置所有 266 mandatory facility. Lex 优先 area, tie-break min_side.
- **Strictness**: certified_exact (无 ε 放松 / 无概率算法 / 无 heuristic 替代 / 不放 LOCK)
- **当前 stack**: OR-Tools CP-SAT 9.15.6755 (Python), Logic-based Benders Decomposition (LBBD) master+sub-problem framework

## Sub-problem 分解

LBBD 当前分层:
- **Master**: placement decision (placements + port_mode + power_pole coverage) pose-bool form
- **Binding sub-problem**: 选 port → commodity 映射 (每 facility 多种 port_specs 合法绑定)
- **Routing sub-problem**: belt 路径 (multi-commodity flow on grid)
- **Flow sub-problem**: diagnostic, 帮诊断 routing infeasibility

## 当前 master form (pose-bool)

由于 24 lever 调研后 user 提出 hypothesis "pose-bool master 是 fundamental 限制", 这里记录 master 内部结构:

```
x_{i, p}    BoolVar  per (mandatory_group_id, pose_idx)            ← 主要 vars
ro_{t, p}   BoolVar  per (required_optional_template, pose_idx)     ← protocol_storage_box etc.
pole_{p}    BoolVar  per (power_pole, pose_idx)                     ← residual_optional

每 27×15 anchor master.build 实测:
  vars 数 ≈ 285K  (主要来自 power_pole pose 数 + 16 mandatory groups × poses)
  constraints ≈ 280K
  master.solve(180s) 在 anchor (22,28) 单 anchor 实测 ~50-100s OPTIMAL (pose-bool form 比之前 coordinate-based 30 min UNKNOWN 跨数量级)

constraint 类型:
- pose exactly-one per mandatory group (demand 数)
- cell exclusivity (AddAtMostOne per cell)
- power coverage: x_{g,p} <= sum y_{coverer_pole}
- ghost rectangle 约束 (forbidden cells region)
- (env-gated) symmetry breaking / SAC-Hull / port_active 等增强
```

## 物理资源 constraint

- **Host machine**: i9-13900KS + 48 GB DDR5 单机. WAN 远端 1 台不可分布式 search.
- **Production wall budget**: 168 hours 大跑 (single campaign).
- **Per-anchor budget**: ~600-1000s master.solve + ~30s binding + ~60s routing + ~10s flow
- **RAM cap per process**: 12 GB (4-parallel campaign 模式下); 24 GB (single process); 48 GB 理论 max 但 OS reserve 占去 ~6 GB
- **CPU**: 8 P-core (5.6 GHz) + 16 E-core. P-core taskset pin 推荐. CP-SAT workers 8 默认.

## Lever 累积 (verdict 历史)

24 lever 全 verdict 死 — 详见 `02_LEVER_HISTORY_24_DEAD.md`. 简化分类:

| Group | Lever # | 共同 verdict | 死法 |
|---|---|---|---|
| L1-L10 (coordinate master era 早期 + paradigm + 工程优化) | 10 ❌ | 死 | coordinate master form 太弱, 30 min UNKNOWN |
| L11 牺牲严格性 | 用户拒绝 | 跳过 | not counted |
| L12 GPT v8 anchor slicing | 1 ❌ | 死 | 算法错估, build wall -92% 但 solve 不变 5 min UNKNOWN 5.5M branches |
| L13 GPT v10 witness preflight | 1 ❌ | 死 | 前提错估, blueprint 缺 41 mandatory + greedy 破坏空地, 大 candidate 0 compatible anchor |
| L14 weighted occupancy | 1 ❌ | 死 | 数学能力上限, interior anchor LP=1.000 永远不可 cert |
| L15 set-packing prover | 1 ❌ | 死 | paradigm 攻错层, minimum set-packing CP-SAT 几秒搞定 |
| L16 lazy power completion | 1 ❌ | 死 | master 端 OK (81s OPTIMAL) cut 端 instance-level Benders 振荡不收敛 |
| **B1 Phase 6 path-1** master 持 port-selection | 1 ❌ (lever 15) | 死 | 4 form 全 UNKNOWN, sound 最小 333K vars + 867K cstr 600s UNKNOWN |
| **B1 Phase 6 path-2** lazy demand cut | 1 ❌ (lever 16) | 死 | 778s 10 iter 不收敛, cut weak 不强制 port-selection consistency |
| Path 12 RAB-SEP | 1 ❌ (lever 17) | 死 | binding-side owner+blocker cert tight 8/8 UNPROVEN |
| Path 13 SAC-Hull | 1 ❌ (lever 18) | 死 | corridor capacity necessary 但 binding/routing reject |
| Path 14 PCR-CUT | 1 ❌ (lever 19) | 死 | patch belt Phase 0-4 全 GO 但 Phase 5 0/8 CERTIFIED |
| Path 14 PCR-CUT Phase 5 multi-anchor | 1 ❌ (lever 20) | 死 | 70 cuts master sustain OPTIMAL 但 routing reject |
| Path 15 PGW-UB | 1 ❌ (lever 21) | 死 | positive witness top5_cov 10x 差 target (0.046 vs 0.55) |
| Path 16 GOC-C2 | 1 ❌ (lever 22) | 死 | 全图 owner-optional RSS 25 GB build 30 min unfinished |
| Path 17 D2 sub-problem | 1 ❌ (lever 23) | 死 | Phase 0b 7/7 INFEASIBLE GO + Phase 2 0/8 CERTIFIED |
| Augmented master Candidate D | 1 ❌ (lever 24) | 死 | 603.9s UNKNOWN + RSS 32 GB + cstr 2.68M (今日 commit `5469885`) |

注: B1 Phase 0-3 是 paradigm 切换 (coordinate → pose-bool master, 53s OPTIMAL 跨数量级解锁, B1 paradigm 真 GO) 不算 lever 死. B1 Phase 4 routing convergence + Phase 5 cell cut findings 是 paradigm 内中间 cut form 实验, verdict 在 Phase 6 path-1/path-2 收尾.

## 当前对瓶颈的理解

详见 `03_BOTTLENECK_UNDERSTANDING_EVOLUTION.md`. 简化:

- root cause 不在 cut form 弱
- root cause 不在数学复杂度不够
- root cause **可能**在 pose-bool master form 自身 scale (280K x_vars × 8.4 ports/pose = 2.36M channel constraints)
- 实测两次直接撞墙:
  - Path 16 GOC-C2: vars 爆 (1.5M scale, RSS 25 GB, build 30 min unfinished)
  - Augmented master Lever 23: cstr 爆 (2.7M scale, RSS 32 GB, solve 603.9s UNKNOWN)

## 之前 GPT review 包历史

| 包 | 时间 | GPT 给的 paradigm | verdict |
|---|---|---|---|
| v3 | 2026-05-14 | (cross-anchor symmetry) | 早期未 land |
| v4 | 2026-05-14 | (proof object lifecycle) | follow-up 工作 land |
| v5 | 2026-05-14 | (port_active per pose) | Path 12 lever 衍生 |
| v6 | 2026-05-15 | hard no-go review (paradigm 收敛点论证) | 强 evidence |
| v7 | 2026-05-16 | Candidate D commodity cell-flow | Phase 0 ✅, Phase 2 0/8 CERTIFIED (L22) |
| v8 | 2026-05-16 | anchor slicing | L12 ❌ |
| v9 | 2026-05-16 | SHA 79b5d1d7 | 9 paradigm 三连死后状态 |
| v10 | 2026-05-16 | witness preflight | L13 ❌ |
| v11 | 2026-05-17 | Lazy Power Completion | L16 ❌ |
| **v12 (此包)** | **2026-05-20** | (current — paradigm research direction shift) | **待 GPT review** |

## Constitution 约束

`PROJECT_LOCK.md` 强制:
- `certified_exact` 和 `exploratory` 路径**严格分离**
- 不允许 master 内 pose 预筛 (破坏 exactness)
- 不允许 over-approximation cut (e.g. heuristic upper bound 当 sound cert)
- 不允许 column generation 退化为 set-packing 时丢失任何 mandatory facility constraint
- AI sidecar 只能 produce hint / candidate ordering, 不能 produce sound cut / proof source

## 当前活的候选 list (此包目的)

详见 `candidates/`:

1. **lever 25 candidate**: Implicit Hitting Set (IHS) paradigm
2. **lever 26 candidate**: Benders symmetry framework
3. **candidate A**: Hybrid CDCL + CP-SAT warm-start
4. **candidate C**: Column generation reformulation (远期备选)
