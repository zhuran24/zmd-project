# 27 Lever 死法分类 (高层 timeline)

每个 lever = 一次 paradigm-level 实施尝试 (从修 cut form / sub-problem 设
计到 master rewrite). 全部 verdict 死. 这里按死因归类, 不是按时间排.

## 5 大死法分类

### 死法 A: master form 自身太弱 (11 个 lever, L1-L11)

时间: 2025-12 ~ 2026-02 (项目最早期)

paradigm: coordinate-based master form (每 facility 用 (x, y, orientation,
mode) 自变量 + 各种工程优化: warm start hint persistence, cross-wave hint
patching, repair_hint, search branching profile, AI candidate ordering
sidecar, parallel campaign tuning, search seed override, presolve config,
LP subsolver filter, master CP-SAT subsolver filter, ghost-conditioned
family bound formulation).

verdict: 全 30 min UNKNOWN. coordinate master 在 70×70 + 266 facility scale
上自身不可解, cut form 调多花哨都没用.

实测信号: master.solve 30 min wall budget 内 master_status = UNKNOWN, branch
count > 10M 但没 verdict.

### 死法 B: cut form / sub-problem 表达力被 master 维度限制 (6 个 lever, Path 12-17 / L17-L22)

时间: 2026-05-18 ~ 2026-05-20 (B1 pose-bool master 解锁后)

B1 pose-bool master rewrite 解锁 master 端 — 27×15 anchor 53s OPTIMAL 跨数
量级好于 30 min UNKNOWN. **但** 6 个不同 sub-problem 抽象层全 verdict 死同
质:

| Path / Lever | sub-problem paradigm | Phase 进展 | verdict |
|---|---|---|---|
| Path 12 / L17 RAB-SEP | binding-side owner+blocker cert | 全 phase land | 0/8 CERTIFIED + 7/8 UNPROVEN |
| Path 13 / L18 SAC-Hull | corridor capacity hull (Menger min-cut) | Phase 1-2 land | 减 80% violations 但 necessary ≠ sufficient |
| Path 14 / L19 PCR-CUT | patch belt CP-SAT cert (≤770 cells) | Phase 0-4 GO ✅ | Phase 5: 0/8 CERTIFIED + 7/8 UNPROVEN + 1/8 sound INFEASIBLE |
| Path 15 / L20 PGW-UB | positive witness + LNS upper bound closure | Phase 0 cheap gate | top5_cov 0.046 vs target 0.55 (10x off) |
| Path 16 / L21 GOC-C2 | 全图 owner-optional + virtual terminal | Phase 0 cheap gate | RSS 25 GB > 12 GB cap, build 30 min unfinished |
| Path 17 / L22 D2 | commodity cell-flow + conditional terminal balance | Phase 2 multi-anchor | 0/8 CERTIFIED + same Path 12-14 pattern |

共同根因: cut 翻译回 master 时只能写

```
sum_{(i, p_i) in core} x_{i, p_i} <= |core| - 1
```

跟 master pose-bool 维度对齐. master 只认识 `x_{i, p_i}`, cut 不能表达
"connectivity / flow / Menger min-cut" 这些 sub-problem 内部结构. **6
paradigm 不同 sub-problem 但 cut form 全退化 instance-pose conjunction
(size 1)**. 10 iter cut 累加但切空间 < 1% per cut, 多 iter 不收敛.

### 死法 C: cut form 表达力跟 algorithm 错估 / 前提错估 (5 个 lever, L12-L16)

时间: 2026-05-16 ~ 2026-05-17 (paradigm exploration era)

| Lever | paradigm | 死因 |
|---|---|---|
| L12 (GPT v8) | anchor slicing 拆 N anchor | 算法错估 — build wall -92% 但 solve 5 min UNKNOWN 不变 |
| L13 (GPT v10) | greedy witness preflight | 前提错估 — blueprint 缺 41 mandatory, greedy 破坏空地 |
| L14 (加料 GPT) | Farkas weighted-occupancy blocker oracle | 数学能力上限 — interior LP=1.000 永远不可 cert |
| L15 (GPT L14 升级) | set-packing prover paradigm | paradigm 攻错层 — minimum set-packing CP-SAT 几秒就出 verdict, 真瓶颈在 master |
| L16 (GPT v11) | Lazy Power Completion (deletion-based core minimizer) | master 端 OK (81s) 但 instance-level cut 振荡不收敛 |

### 死法 D: master form rewrite 真 GO 但下游死 (B1 Phase 4-6, 累积 L15-L16 实际是 Phase 6 子项)

时间: 2026-05-17 (B1 paradigm) ~ 2026-05-18 (Phase 6 path 1+2 verdict)

- **B1 phase 0-3**: pose-bool master rewrite, 53s OPTIMAL 跨数量级解锁 ✅
  这是 **27 lever 中唯一一次真 GO**
- **B1 phase 4**: routing convergence 卡 — front_blocked ~500-610 ports
  系统性. PROJECT_LOCK 禁 port_clearance hard constraint
- **B1 phase 5**: 3 种 cell-cut form 全 over-restrictive (Phase 5a/5b/5c)
- **B1 phase 6 path-1** (master 持 port-selection): 4 form 全 UNKNOWN, 累积 lever 15
- **B1 phase 6 path-2** (lazy demand cut): 778s UNPROVEN 10 iter 不收敛, 累积 lever 16

### 死法 E: Augmented master 资源 dead end (Lever 23-24, 2026-05-20)

| Lever | paradigm | 实测撞墙 |
|---|---|---|
| L23 augmented master Candidate D | master 内置 D2 vars (u + e + flow conservation) channel master placement | 307K vars + 2.68M cstr (cap 4x over), solve 603.9s UNKNOWN, RSS 32 GB (cap 2.6x over) |
| L24 augmented master single-commodity | (类似 L23 但单 commodity) | 同 cstr 爆 dead end |

Root cause 实测: pose-bool master 280K pose vars × 8.4 ports/pose = 2.36M
OnlyEnforceIf channel constraint. CP-SAT 2.68M cstr scale 下不可解.
multi-commodity (~10) 推算 ~24M cstr, 物理不可能.

## 死法分布跟 cand C 关系

cand C (column generation) 不在上面 5 大死法分类内. cand C 是 fundamentally
不同 master form (不再是 CP-SAT pose-bool, 而是 LP-based RMP + pricing CP-SAT
+ B&P), 它是 **27 lever 之外的方向**.

cand C verdict 数据见 `cand_c_phase_0_1_2_v3_verdicts.md`. Phase 0/1 (5/20/40/80
inst ramp) GO, Phase 2 v3 (160/266 inst) NO-GO with RMP infeasibility at iter 0.

→ cand C 跟 27 lever 死法不同, 撞的是不同的墙 (cell exclusivity vs exactly-1
partition contradiction 在 96% 利用率下).

## 共同 root cause (项目方判断)

按 lever 死法 + cand C 实测后, 项目方对 root cause 的判断:

1. **pose-bool master form scale 是 fundamental scale 限制** (B1 paradigm
   解锁后 cut framework 在此 scale 下不能升表达力)
2. **96% effective utilization 是 fundamental geometric stress** (cand C
   verdict 撞的根因)
3. 通用 CP-SAT solver 内 cut framework 表达力受 solver 自身 cut interface
   限制 — 自研 feature-level cut engine 是项目方 P3 决策选 Design B 的理由

→ Stress test 任务是验证或反驳这些 root cause 判断.

## "27 lever" 准确计数

- L1-L11 (coordinate master era): 11 个
- L12-L16 (paradigm exploration): 5 个
- L17-L22 (Path 12-17, sub-problem paradigm): 6 个
- L23-L24 (augmented master): 2 个
- B1 Phase 6 path-1, path-2 (实际算 sub-paradigm): 各 1 个, 但 verdict 跟 L15 / L16 同时累积, 没单独编号. 加 2 = **25**
- 调研 32 paradigm 内验过 NO-GO 没 land: 32 - 已 land lever = 不算 lever
- 上面 25 + L25 IHS (Implicit Hitting Set, alive 候选未实施) + L26 (Benders symmetry, alive 候选未实施) = **27**

主对话历史里 "27 lever" 数字偶有 24/25/26/27 不同记法 (跟 L25/L26 是否算 +
B1 path-1/path-2 是否单算 sub-lever 有关). 项目 paradigm investigation 列 **24 lever 全 dead** +
3 alive candidate (L25 IHS, L26 Benders symmetry, candidate A CDCL warmstart)
+ candidate C column generation. cand C 后续 Phase 0/1/2 land + NO-GO 后, 加
B1 path-1/path-2 单独算 = **27 lever** 在主对话当前记法.
