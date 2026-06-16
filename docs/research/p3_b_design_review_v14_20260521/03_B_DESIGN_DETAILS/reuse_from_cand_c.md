# B Component: 复用清单 (cand C + 死路 paradigm)

Design B 不是 from scratch. 大量复用 cand C + 27 lever paradigm investigation
的 infrastructure 当 sub-problem oracle / data preprocessing / utility.

## 复用 from cand C Phase 2 v3

cand C ~3000 LOC, 复用 ~40-50%:

### 直接复用 (基本不改)

| File | LOC | 复用方式 |
|---|---|---|
| `pricing_cache.py` | ~180 | sub-problem pose pool query — B 的 master state machine 调它 enumerate 合法 pose / cell |
| `feasibility_bootstrap.py` | ~350 | Layer 1 (`solve_direct_mini_master`) 当 sub-problem oracle 验 candidate facility set 是否 layoutable |
| `routing_aware_pricing.py` | ~230 | pricing seed 当 B 的 candidate pose ordering heuristic (cut store 内 cut 触发 search restart 时用) |

### 部分复用 (重要逻辑保留, 接口适配)

| File | LOC | 复用方式 |
|---|---|---|
| `boundary_constraints.py` | ~190 | per-(cell, dir) net flow equality logic → B 的 port_exposure cut family resolve algorithm |
| `column_grammar.py` (Phase 1) | ~? | Pose ↔ column representation — adapter 层用 |
| `integer_validator.py` (Phase 1) | ~? | m10 `check_set_partitioning` strict validator — B 的 sub-problem cert validate logic |

### 弃用 (跟 B 设计冲突)

| File | LOC | 弃用原因 |
|---|---|---|
| `ryan_foster.py` | ~220 | RF branching on λ-space, B 不在 λ-space |
| `alternative_blueprint_generator.py` | ~? | A1 alternative bp 是 cand C 的 LP-level 加 column, B 不用 LP |
| RMP solving logic | (in `phase2_probe.py`) | set covering LP, B 完全替换 |

## 复用 from 27 lever 死路 paradigm

每个死路 paradigm 留下 infrastructure 可当 oracle. 关键复用:

### B1 paradigm (pose-bool master, lever 14 / B1 Phase 0-3 GO ✅)

- `src/models/pose_bool_exact_master.py` ~47K 行
- 复用方式: 在 B 的 sub-problem oracle 内当 fallback (小 candidate 直接
  call pose-bool master 验 layoutability, 不用 B 的 state machine)
- 注意: pose-bool master 是 B1 paradigm 的"真 GO 但下游死"产物 (B1 Phase
  4-6 path 1/2 verdict 死). master 端工作正常, 不能闭合 LBBD loop. B 设
  计借它当 oracle 不用它当 master.

### PCR-CUT (Path 14, lever 19)

- `docs/research/pcr_cut_patch_routing_conflict_20260519/` 内 PoC code
- `src/search/patch_routing_core.py` (~983 LOC)
- `src/search/d2_separator.py` (~469 LOC, 部分共用)
- signature lifting helpers
- 复用方式: cutset cut family generation. PCR-CUT 跑 patch belt CP-SAT 给
  min-cut cert, B 的 cutset cut 直接 wrap.

### D2 commodity flow (Path 17, lever 22)

- `src/models/d2_commodity_flow_core.py`
- `src/search/d2_separator.py`
- 复用方式: component reachability cut family generation. D2 PoC verified
  Phase 0b 7/7 INFEASIBLE 在 0.05-0.15s, oracle 端 work but cut 表达力被
  pose-bool master 锁. B 的 master state machine 不锁, oracle 应 work.

### SAC-Hull (Path 13, lever 18)

- `src/search/sac_hull_separator.py` (~? LOC)
- `docs/research/sac_hull_separator_capacity_20260518/` 内 Phase 2 dynamic
- 复用方式: region capacity cut family generation. Menger min-cut 算法
  + corridor capacity bound 直接复用.

### L16 Lazy Power Completion

- `docs/research/phase0_lazy_power_completion_20260517/` 内 deletion-based
  core minimizer PoC
- 复用方式: pattern no-good cut family generation. deletion-based 给 size
  > 1 的 minimal core cert.

### SMT-MT outer pruning (smt_mt research)

- `docs/research/smt_mt_outer_pruning_phase0_20260521/` 内 PoC
- 复用方式: candidate 枚举顺序 + outer-loop early pruning. 不直接进 B
  的 cut family, 而是 outer layer 优化.

## 复用 from project src/

| Path | 复用方式 |
|---|---|
| `src/models/binding_subproblem.py` | binding 当 black-box oracle, 给 master state machine 验"port → commodity 是否 layoutable" |
| `src/models/routing_subproblem.py` | routing 当 black-box oracle, 给端到端 cert |
| `src/models/flow_subproblem.py` | flow diagnostic oracle |
| `src/search/exact_campaign.py` | campaign persistence + resume infrastructure, B 直接复用 (cut store 加入 campaign state) |
| `data/preprocessed/*.json` | 全部 source-of-truth 数据, B 不改 |
| `rules/canonical_rules.json` | source-of-truth, B 不改 |
| `src/render/` (visualization) | postprocess only, B 直接复用 |

## 复用 ratio 估算

- 完全复用 (不改): ~30% LOC
- 部分复用 (adapter / interface 适配): ~10-15% LOC
- B 新写 (master state machine + cut store + 5 cut family core): ~50-60% LOC
- 弃用 (cand C RMP / RF / coordinate master 等): ~5-10% LOC

总体 ~40-50% 复用率. 这比 from-scratch 低很多 — paradigm 投资合理.

## 复用 risk

### Risk 1: 死路 paradigm oracle 在 B 设计下也 fail

死路 paradigm 验 cut framework 表达力被 master 锁. B 设计假设 master 状
态机解锁后 oracle work. 但**没实测**.

→ Phase 0 / 1 PoC 必须验 PCR-CUT / D2 / SAC-Hull oracle 在 B 的 master
state machine 下是否真 work, 不是直接信任 paradigm "GO 但下游死" 时的
oracle 数据.

### Risk 2: cand C oracle 在 96% utilization 下 0 iter infeasible

cand C v3 实测 RMP 0 iter infeasible at 160/266 inst. `feasibility_bootstrap.py`
Layer 1 `solve_direct_mini_master` 是 mini-master, 但 60s budget 可能不
够全 266 inst.

→ B 设计调 cand C oracle 时, 用小 candidate (e.g. 20-80 inst 等)验 oracle,
不要直接全 266.

### Risk 3: pose-bool master 在 B 的 state machine 下 inconsistency

pose-bool master 是 CP-SAT 模型, 内部 propagator 跟 B state machine 不同
步. 同一 layout, pose-bool master 可能 OPTIMAL 给一种 placement, B state
machine 可能 propagate 另一种. 这是 oracle 跟 master 的 contract 问题.

→ B 设计 oracle 调用必须 return "verdict + concrete layout", 不是 "feasibility
hint". B state machine 内 placement 是 truth, oracle 验那个 truth 是否
feasible.

## Stress test 视角

- 复用 ratio ~40-50% 是否合理? oracle 复用是否真 sound?
- 死路 paradigm 当 oracle 的 risk 是否被 underestimate?
- cand C `feasibility_bootstrap` Layer 1 是否能 cover 全 266 inst 还是只
  小规模?
- Phase 0 PoC 设计是否需要先单独 verify oracle 端 work?
