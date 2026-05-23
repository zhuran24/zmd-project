# 11 — 依赖图 (family / step / phase 之间 chain)

各段不是平行做的. 错顺序就走死路.

### 9.1 Family 内部 dependency

```
F1 region_capacity
   └─ Phase 1.1 闭环 ✓

F2 cutset
   └─ commodity_demands + commodity_routes registry (Step M+N)
   └─ patch_routing_core (Phase 1.5+ 复用 PCR-CUT 单 anchor 部分)

F3 port_exposure
   └─ candidate_placements pose ports lookup (Step E candidate_placements helper)
   └─ active_port_witness (Phase 1.5+ boundary_constraints LP)

F4 component_reach
   └─ commodity_routes registry (Step M+N)
   └─ d2_separator BFS helper (Phase 1.5+ 复用 D2 单 anchor 部分)

F5 pattern_nogood
   └─ F1-F4 任一 INFEASIBLE 后 fallback (literal pattern catch geometric 漏掉的)
   └─ lifecycle step 2 minimize (F5 driver)
   └─ L16 core_minimizer 复用 (deletion + QuickXplain)

F6 shape_packing_hall
   └─ F1 region helper 复用 (region_cells / capacity)
   └─ Hall theorem 实施 (greedy match 后 LP)

F7 power_hitting_set
   └─ F3 port_exposure 跟 power 版本同 dispatch
   └─ power_network helper (现 src/cuts/helpers/power_network.py stub)

F8 power_grid_reach
   └─ F4 BFS helper 复用 (component reach)
   └─ Liang-Barsky helper (现 src/cuts/helpers/ghost_geometry.py)
   └─ ghost_rect tuple 语义 lock (§8.1 Phase 1.2 入门必先)

F9 density_envelope
   └─ F6 跟 F9 都 region-density 约束, F6 land 后 F9 复用 region helper
```

### 9.2 Phase 间 dependency

```
Phase 1.2 P1.11 入门 (7 factual fix)
   ↓
Phase 1.2 P1.11-P1.15 (F5-F9 实施)
   依赖: 入门 strict gate default ON / spec drift 清 / source_digest 真 hash
   ↓
Phase 1.3 P1.21 (CP-SAT propagator 集成)
   依赖: F5-F9 全 register (lifecycle step 8 接 9 family dispatch)
   ↓
Phase 1.5+ (production integration)
   依赖: Phase 1.3 propagator 集成验 lifecycle 闭环
   依赖: BState production builder (Phase 1.2 入门 +/或 Phase 1.5 起做)
```

### 9.3 关键 ordering decision

- **source_digest 真 hash 必先** (Phase 1.2 §8.1 §3) — 不然 Phase 1.3 production
  data 轮换识别不出, cross-session cert replay 不可信
- **ghost_rect tuple 语义 lock 必先 F8** — F8 实施前不 lock 会让 Liang-Barsky
  跟 ghost_rect 横竖反
- **strict gate default ON 必先 F5-F9** — 新 family 漏 register 时 silent
  attach
- **BState production builder 必先 Phase 1.5+** — 真生产 inject 各 family
  validator 需要的字段, 不统一 builder 会让一处漏 inject 拖崩全 framework

### 9.4 跨 phase invariant

Phase 1.2 / 1.3 / 1.5+ 全 share 这些 invariant (PROJECT_LOCK §3A):
- 9 family list 不变 (不加 / 不删 / 不改 mode)
- cut schema 字段 invariant (cut.scope + cert + literals XOR geometric_payload)
- multiset eval slot anonymity (state_machine §5)
- adversarial soundness (validator trust boundary, oracle 不可信)

任一 phase 想改 invariant 必先 PROJECT_LOCK 更新 + spec/src/test 跨同步.

---

