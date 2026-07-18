# 02 — 24 Lever 累积 verdict (全 dead)

> **历史失效标记（Batch 4，2026-07-18）**：本文中依赖旧 front 的
> Phase 4–6、RAB/FCL 与相关常数 benchmark 已撤销或待重验；“24 lever
> 全 dead/范式已穷尽”继续保持撤回（MAY-01/MAY-04/MAY-06）。纯 master、
> power、area 与渐近复杂度结论不受此标记整体否定；逐项边界见
> [历史重判附录](../front_offset_incident_20260718/01_historical_rejudgment_addendum.md)。

每个 lever 一段, 含 paradigm 描述 + verdict + 死因. 时间序排列.

## L1-L16: pose-bool framework 前 + 内 cut form (2025-12 ~ 2026-05-17)

### L1-L11 (pre-pose-bool master)

之前在 coordinate-based master + LBBD 框架下试的 11 个不同 cut form / search strategy 增强. 包括: warm start hint persistence, cross-wave hint patching, repair_hint, search branching profile (guided / ghost-first / ghost-after-counts), AI candidate ordering sidecar, parallel campaign tuning, search seed override, presolve config, LP subsolver filter, master CP-SAT subsolver filter, ghost-conditioned family bound formulation. 全 verdict 死 — coordinate-based master 在 70×70 + 266 facility scale 上 30 min UNKNOWN. 跟"cut form 表达力" 死法层级不同, 这层是 master form 自身 (coordinate-based) 太弱.

### L12 (anchor slicing — GPT v8)

GPT v8 plan 给的 ghost-anchor disjunctive decomposition env-gated 拆 N anchor. PROJECT_LOCK 允许 (anchor 独立 subproblems). 实测: clean apply + 2211 pytest pass + build wall -92% 真实, 但单 anchor 5 min UNKNOWN 5.5M branches 跟 trial7 1h UNKNOWN 同 quality. 关注 build 没量 solve, 实际 build 阶段不是瓶颈. **L12 ❌**.

### L13 (witness preflight — GPT v10)

GPT v10 plan 给的算法: greedy 填 mandatory facility 进 community blueprint 后 preflight 验空间. clean apply + 2212 pytest pass + 算法 sound. **前提错估**: 我们 community blueprint 缺 41 mandatory, greedy 填的位置破坏 blueprint 留 27×15 空地, merge 后 266 facility 占 3122 格, compatible anchor=0, preflight 0 秒 fail-closed 不 trigger. **L13 ❌**.

### L14 (weighted occupancy — GPT 加料 prompt)

GPT 给的 Farkas weighted-occupancy blocker oracle. PoC 70 min: 6 anchor LP datapoints + 数学推理验证 **interior anchor LP=1.000 exact 永远不可 cert** (boundary_storage_port 唯一 captive, 18 free group 对 LP 不贡献). **L14 ❌**. 12 paradigm 全 verdict 死, 严格性+算法层穷尽.

### L15 (set-packing prover — GPT L14 升级)

GPT L14 升级建议 1-2 月 paradigm investment. 3 小时 PoC 验底层假设: minimum set-packing 核心 CP-SAT 几秒搞定 (corner 2.3s INFEASIBLE, interior 7s feasible 8w). 真瓶颈在 master 多余约束 (port/power/connector), set-packing paradigm 攻错层. **L15 ❌**.

### L16 (Lazy Power Completion — GPT v11)

GPT v11 plan 给的 Phase 0 mini-PoC + Phase 3 deletion-based core minimizer. Master 端 PASS (81.8s OPTIMAL vs production 30 min UNKNOWN). 但 cut 端**两次都死**: loose cut (220 instance) 10 iter 134→133 stuck; tight cut (minimizer 缩到 6) 6 iter 134→123 振荡不收敛. Instance-level Benders cut 在 problem geometry 下 fundamental 不够. **L16 ❌**. 14 paradigm 全 verdict 死.

## B1 Phase 4-6 cut form 探索 (2026-05-17 ~ 2026-05-18, Pose-bool master 落地后)

User decision 走 B1 (pose-bool master rewrite) 后, 新 master form 实测 50-100s OPTIMAL 解锁了 master 端瓶颈. B1 paradigm 内 cut form 探索分 3 个 phase:

### B1 Phase 4: routing convergence finding

修 inferred counts (`infer_exact_required_pose_optional_counts` 用 build_exact_core 传给 master) → binding 通了 (ro_vars=15980). 但 routing precheck `front_blocked` ~500-610 ports 系统性 — pose-bool master 不知 port direction, 任何 OPTIMAL layout 都 ~500-600 ports front_blocked. 多 anchor / small candidate / warm start hint / max_iter=15 长 trial 全 UNPROVEN. `EXACT_B1_BYPASS_ROUTING_PRECHECK=1` bypass 后 binding enumerate > 42 min stuck.

PROJECT_LOCK 明禁 port_clearance hard constraint (`exact_coordinate_master.py` 内显式 if exact_mode return — "严格精确路径不允许把所有端口前方都必须畅通这种近似假设当成正式剪枝").

### B1 Phase 5: 3 种 cut 形式实测全 over-restrictive

3 个 cut form 实验都 over-restrictive:
1. **Cell-level reactive cut** (`add_routing_port_blocking_cell_cut`): mutual exclusion `sum(port_poses_at_C_d) + sum(front_poses) <= 1`. 5 iter 加 **1587 cuts, blocked_ports 仍 519-611 浮动不收敛**. 切掉合法解 (多个 facility 共享 port_cell).
2. **A priori hard mutual** (env `EXACT_B1_PORT_CLEARANCE_HARD`): 47666 个 `sum(port) + sum(front) <= 1`. 6 anchor + 4 small candidate **全 INFEASIBLE 47-56s**. over-restrictive.
3. **A priori hard implication (channeled-OR)**: `any_port = OR(port_poses)` + `any_port + sum(front) <= 1`. 47666 主约束 + ~K1 channeling. 同 INFEASIBLE 47s.

**Root cause**: master 不知 binding 选哪些 port active. binding 阶段每 facility 5-7 个 port 选其中**一部分**, 没接的 port 前面被堵不影响. a priori 把 "所有 port 必须 active" 当 hard 自然 INFEASIBLE.

### B1 Phase 6 audit + PoC finding

`port_binding._enumerate_side_binding_patterns` 让任何 facility (fixed op / boundary_io / protocol_core / wireless_sink) pose 都可能 inactive port_cell — total_slots < ordered_cell_count 时 enumerate 选子集. Phase 6 scope 放大: port_active BoolVar 给所有 facility 所有 port_cell, ~200K vars.

env flag `EXACT_B1_PORT_CLEARANCE_SKIP_STORAGE_BOX` PoC 验证否定 "storage box 唯一 over-restriction" 假设: 27×15 (22,28) INFEASIBLE 51.5s + 15×10 (28,30) INFEASIBLE 56.5s 跟 Phase 5b 几乎一样.

### B1 Phase 6 path-1: master 持有 port-selection 实测全死

user /goal "开始路线1, 改责任边界". 4 个 form 实测全 verdict 死:

| 配置 | vars | constraints | time | verdict |
|---|---|---|---|---|
| v1 per-pose port_active (~2.3M vars) | 2,588K | 3,106K | 134s | UNPROVEN |
| v2 grid-fc + anchor offset bug | (phantom) | | 52.5s | INFEASIBLE |
| v3 anchor-修 sound 最小 form 8w 300s | 333K | 867K | 346s | UNKNOWN |
| v3 1w 600s | 333K | 867K | 645s | UNKNOWN |

solver knob (workers/time) 不救. **sound 数学路径但 master.solve 架构层不可解** (累积 lever 15).

### B1 Phase 6 path-2: lazy demand cut 实测死

cut form `sum(blockers) <= K - demand`.OnlyEnforceIf(pose_var). 实测 UNPROVEN 778s (10 iter 不收敛). master 每 iter OPTIMAL (77.8s/iter) 但 cut weak — 不强制 binding 选的 port 跟 master cleared subset 对齐.

**根因**: master/binding port-selection 不匹配是 fundamental, 不论 prebuild (path-1) 还是 lazy cut (path-2) 都解不了. cut form 没强制 cross-component port-selection consistency. (累积 lever 16).

## Path 12-17: pose-bool master + 各 cut framework (2026-05-18 ~ 2026-05-20)

B1 内部 path-1/path-2 dead 后, GPT review v1/v2/v3/v4/v5 给 5 个 paradigm-level 新 cut framework. 6 paradigm 撞同墙.

### Path 12 / L17: RAB-SEP (Routing-Aware Binding Separator)

binding-side owner+blocker cert (binding 给 cert tight 后 master no-good cut). Phase 5 multi-anchor 8 anchor × max_iter=10: 0/8 CERTIFIED, 7/8 UNPROVEN. cert tight 但切空间 ≪ 1%, 不收敛. **L17 ❌**.

### Path 13 / L18: SAC-Hull (Separator Capacity Hull)

corridor capacity 用 Menger min-cut 给 hull capacity constraint. Phase 1 static 64 separator land OK + Phase 2 dynamic 22→17→10 violations 下降. **但 necessary ≠ sufficient**: L2 cuts 工作 (减 violations) 但 binding/routing 仍 reject 80% layout. **L18 ❌**.

### Path 14 / L19: PCR-CUT (Patch-Certified Routing Conflict Core)

patch belt CP-SAT 跑真 routing on patch (≤770 cells covers 98% SAC slack). Phase 0-4 全 GO ✅ 端到端 land (commits 24ed7d8/a56ab41/e71879e/f3a7382/2f9bee5). Phase 5 multi-anchor 8 anchor × 10 iter = 0/8 CERTIFIED + 7/8 UNPROVEN + 1/8 sound INFEASIBLE. **同 RAB-SEP / SAC-Hull pattern**. **L19 ❌**.

### Path 15 / L20: PGW-UB (Positive Witness + UB Closure)

正向 witness + LNS — positive witness paradigm 给 routing reachability hint. Phase 0 cheap gate 1h 实测 8 anchor: top5_cov 0.044-0.053 vs target ≥0.55 **10x off**, blocked_owners 276-327 vs ≤120, sac 12-80 vs ≤5. routing residual 全域均匀分散不 spatial-cluster, LNS neighborhood 失效. **L20 ❌**.

### Path 16 / L21: GOC-C2 (Global Owner-Conditional with C2 routing)

全图 owner-optional + virtual terminal + sufficient infeasibility core. Phase 0 cheap gate ~2h 实测: production scale (266 facility + 70×70 + 10 commodity, active_cells=全 free_cells) 下 CP-SAT model build **30 min 未完成**, RSS 25 GB > Pre2 cap 12 GB **2.1x over**, vars ~1.5M scale vs target 180K **8x off**. **撞 GPT 声称 "不撞" 的 (1) 全局耦合**. **L21 ❌**.

### Path 17 / L22: D2 (Commodity Cell-Flow + Conditional Terminal Balance)

GPT v7 Candidate D 完整版. Phase 0b 7/7 INFEASIBLE 0.05-0.15s **第一次 Phase 0 真 GO** + Phase 1 production class + LBBD wiring 5/5 iter cut_added. **但 Phase 2 multi-anchor max_iter=10 = 0/8 CERTIFIED 跟 Path 12-14 同质死法**. core 全 size = 1, cut form 退化 instance-pose no-good (跟 RAB-SEP 同). paradigm 数学最丰富 但 cut 表达力被 pose-bool master 卡死. **L22 ❌**.

### Augmented master Candidate D / L23 (2026-05-20)

User sharp 抓出 Path 17 D2 是 sub-problem 路线 (600s wall 完全没用上, master 仍 pose-bool 100s OK + D2 0.15s 完), 不是 augmented master. **真 untested**: 改 master 内置 D2 vars (u + e + flow conservation) 跟 master placement 决策 channel. Phase 0 cheap gate single-commodity 实测 (commit `5469885`):

- vars: 285K base + 22.5K augment = **307K** (over 250K cap 1.2x)
- cstr: 280K base + 2.4M augment = **2.68M** (over 650K cap **4x**)
- solve: **UNKNOWN at 603.9s** (超 600s budget)
- RSS: 32 GB (cap 12 GB **2.6x over**)

Root cause: pose-bool master 280K pose vars × 8.4 ports/pose channel = 2.36M OnlyEnforceIf 约束. CP-SAT 2.68M cstr scale 下 600s 不收敛. **multi-commodity 推算 24M cstr 必死**. **L23 ❌**.

减 scale 的 lever 全 inactive:
- 减 pose_data_count → 破坏 exactness (PROJECT_LOCK 禁)
- 减 ports_per_pose → 改 source-of-truth facility 定义 (不可)
- 减 commodity_count → single-commodity 已实测 dead

## 24 lever 累积 verdict 总结

| Lever group | 数量 | 共同 verdict |
|---|---|---|
| L1-L11 coordinate master + cut form | 11 | coordinate master form 太弱, 30 min UNKNOWN |
| L12-L16 pose-bool master + cut variations | 5 | cut form 表达力被 master 限制 / 算法层 paradigm shift 都 verdict 死 |
| Path 12-17 (L17-L22) pose-bool master + 6 paradigm | 6 | 6 paradigm 不同 sub-problem 抽象层, cut form 全退化 instance-pose, 同质死法 |
| Augmented master Candidate D (L23) | 1 | master 内置 vars 即 270K x_var × 8 ports × 1 commodity = 2.36M cstr, 600s UNKNOWN, RSS 32 GB |

24 lever 死法可归 2 大类:
1. **cut form / sub-problem framework 死法**: 6 paradigm 撞同墙, cut 表达力被 master pose-bool 维度锁死
2. **master form / augmented 死法**: pose-bool 自身 scale × per-port channel 让任何 channel-routing-into-master 撞资源 dead end

## 实测两次资源 dead end (跨 paradigm 撞同种类)

| Path | scale 爆维度 | 实测数字 | 备注 |
|---|---|---|---|
| Path 16 GOC-C2 (L21) | **vars 爆** | 1.5M vars, RSS 25 GB, build 30 min unfinished | 全图建模, owner-optional vars × commodity 维度 |
| Augmented master D (L23) | **cstr 爆** | 2.68M cstr, RSS 32 GB, solve 603.9s UNKNOWN | 全图建模, channel OnlyEnforceIf 维度 |

两次撞 GPT v7 plan Proposition 2 论证的"全图建模 → 3 类资源 dead end 之一"中的 2 种.

## 历史 GPT review paradigm 全 verdict 死

详 v3/v4/v5/v6/v7/v8/v9/v10/v11 review 包. GPT 给的 paradigm: anchor slicing / witness preflight / weighted occupancy / set-packing prover / Lazy Power Completion / Candidate D commodity flow / port_active per pose / pose_bool master rewrite (这个 actually GO) / 等. **GPT 出招 9 次, 1 个 GO (pose-bool master rewrite, 但 master OPTIMAL 后 cut framework 死) + 8 个 paradigm 死**.

## Master form rewrite 唯一一次真 GO (B1 pose-bool)

User decision 2026-05-17 走 B1 (pose-bool master rewrite, 代码重写 ~280 LOC PoseBoolExactMasterDelegate). master.solve 27×15 (22,28) 53.3s OPTIMAL — 跟 coordinate-based 30 min UNKNOWN 比跨数量级. 但 master OPTIMAL 解锁后, cut framework 6 paradigm 全死同质 → 现 24 lever 状态.

## 当前 paradigm investigation 状态评估

**项目自己的判断 (待 GPT review):**
- production CP-SAT + LBBD framework 内 paradigm investigation 现穷尽 (24 lever + 32 个调研方向 + GPT 9 次 review)
- root cause 推测在 pose-bool master form scale (待 GPT 反驳 / 确认)
- 真 break paradigm 需要 paradigm-research 级投资 (1-3 月 + ) 不是 production tooling 内调
