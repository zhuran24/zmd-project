# PROJECT_LOCK 硬约束 (审稿不可绕的边界)

`PROJECT_LOCK.md` 是项目的宪法层文件. 包内 `shared_infra/PROJECT_LOCK.md` 有
完整 7K 原文. 这里抽出 audit 必须知道的硬约束.

## 1. Certified exact 跟 exploratory 严格分离

```
certified_exact 跟 exploratory 是两个独立 mode, 路径完全隔离.
exact 路径的任何 cut / pruning / objective bound 都必须 sound
(也就是不能误剪合法解, 不能高估上界, 不能低估下界).
```

具体不可做:
- master 内 pose 预筛 (筛掉某些 pose 因为 "看起来不可行") — 破坏 exactness
- over-approximation cut 当 sound cut (e.g. heuristic upper bound 当
  certified upper bound)
- ε-relaxation / probabilistic algorithm / Las Vegas algorithm
- column generation 在 master 收敛时 column pool 内丢失任何 mandatory
  facility (集合 cover ≠ 集合 partition)

## 2. Strict objective

`max_lex(ghost.area, ghost.min_side)`. min_side ≥ 6 是 admissibility (低于此
不算合法), **不是 tie-break**. tie-break 只在 area 相等且 min_side 相等才发
生 (然后按 anchor pos 字典序选 1 个 representative).

不可绕:
- 不允许 area-only objective (丢 min_side)
- 不允许 area + small-perimeter (改变 lex 顺序)
- 不允许 weighted scalarization (e.g. area + α × min_side) — 破坏 lex

## 3. 资源 + wall budget

- 物理 host: i9-13900KS + 48 GB DDR5, 单机 + 1 远端 (WAN, 不能高频 sync)
- per-process RAM cap: **12 GB** (4-parallel campaign 模式); 24 GB (single
  process); OS reserve ~6 GB 后 实际可用 ~42 GB
- single campaign wall: **168 hours**
- per-anchor budget:
  - master.solve: ~600-1000s (依 anchor 大小)
  - binding sub-problem: ~30s
  - routing sub-problem: ~60s
  - flow diagnostic: ~10s
- CPU: 8 P-core (5.6 GHz, taskset pin 推荐) + 16 E-core
- Solver workers 默认 8 (可调到 1 减 RAM peak 至 12 GB plateau)

## 4. 不可重写 source-of-truth

下列文件是 source-of-truth, 任何 design 决策必须读这些不是 cache / vendored
版本:

- `rules/canonical_rules.json` — facility template + recipe + commodity 真相
- `data/preprocessed/candidate_placements.json` — 预计算 pose pool
- `data/preprocessed/mandatory_exact_instances.json` — 266 mandatory list
- `data/preprocessed/generic_io_requirements.json` — IO/port spec

修改这些需要 PROJECT_LOCK gate (人工审稿).

## 5. AI sidecar 限制 (含此 stress test)

PROJECT_LOCK 明确:
- AI 模块 (含 GPT review / Claude / Gemini) 可以:
  - 建议 candidate ordering
  - 给 master CP-SAT hint
  - 解释 tuning experiment 结果
  - 分类 UNKNOWN / UNPROVEN result
  - **审查 design proposal** (本 stress test 在此范畴)
- AI 模块**不可以**:
  - 直接删除 candidate / 宣告 infeasibility (除非 oracle 完整 cert)
  - 写入 `data/checkpoints/` / `data/solutions/` / `data/blueprints/`
  - 修改 certified proof source 或 campaign hash
  - 改变 final preflight semantics
  - authorize final 168h production run

→ 此 stress test **可以**给 design B 提出 critique + suggest 第 6 cut family,
但不能直接 "代为执行" 改 src.

## 6. Forbidden architecture changes

PROJECT_LOCK 明禁:
- Reintroducing exploratory caps as exact-mode bounds (e.g. "50 power poles
  + 10 storage boxes" 是 exploratory 限制, exact 模式不可加)
- Treating exploratory artifacts as certified proof
- Changing campaign / artifact / proof schemas without lock + spec + test 同
  时更新
- Rebinding globally pooled resources into per-line hard bindings without
  new proof basis
- Adding exterior-path requirement for the ghost rectangle (ghost 不需要
  从外界 reachable)

## 7. Phase 3B 当前 phase 范畴

- Phase 3A (delivery / productization): 已完成, release `r20260416`
- Phase 3B (full-scale exact proof): **当前 phase** — 目标拿到 certified
  feasible solution 给 valley4_protocol_core 70×70 base
- Phase 3B optimization plan: 4 lanes (A=safety/obs / B=det tuning /
  C=AI sidecar / D=runtime diag)
- AI 是 shadow-only sidecar: no proof source, no formal pruning, no
  checkpoint writes

## 8. 单 base scope

- 仅 `valley4_protocol_core` 70×70
- 其他 base (`valley4_infra_outpost`, `wuling_protocol_core` 等) 是
  `future_scope`
- Outer-deployment subsystem (跨 base 路径) 是 adapter-side `future_scope`

→ Design B stress test 只针对 valley4_protocol_core base 的几何 + 266
mandatory 分布.

