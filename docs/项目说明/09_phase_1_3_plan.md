# 09 — Phase 1.3 plan（attach spike + master integration）

> **未来计划**：面向人的阶段名统一为 **P1.3**。本文旧的 P1.3A/P1.3B 子标签仅用于追溯，不表示 owner gate 已打开，也不表示 Step 8 已接入当前 default certified path。


F5-F9 落地后, evaluator 才进真 hot path (10K calls/sec). 这阶段 perf opt
必要. GO 标准见 §8.3.

## P1.3A — CP-SAT attach spike (NEW, 必先验)

**为啥加 spike**: 外部 reviewer (Gemini math review meta-audit, 2026-05-23)
catch — 当前 OR-Tools 9.15 CP-SAT Python 模型 **不支持** `model.AddLazyConstraint`.
旧 plan 把 lazy constraint 写得像确定可行, 实际项目当前依赖路径必须改 LBBD 外循环.

**P1.3A 唯一问题**: 当前 Python OR-Tools CP-SAT 路径到底能不能在预期时机把 cut 变成有效 master 约束?

**Spike 3 个方向 PoC, ≤ 3 day 答完**:

1. **Solve-rebuild 路径** (推荐, 跟现 benders_loop 一致): 每轮 master.solve 前
   把 active cut 转 `Add` / `OnlyEnforceIf` / `AddBoolOr` / `AddLinearConstraint`
   注入新 model, 然后 solve. 每轮 rebuild model 不是 incremental.
2. **C++ propagator hook** (实施成本高): OR-Tools C++ 层有 `SearchObserver` /
   custom propagator API. Python 绑定不完整, 投资 ≥ 1 周.
3. **Hard-constraint rebuild** (蛮力): cut 全 hard, 每加新 cut rebuild model.
   兼容性最好但 build cost 大.

**Spike GO 标准**: 至少一条路径在 prod-scale (266 instance + ~10K cut) 跑通端到端
master cycle, wall-clock 退化 < 50%. **GO 后才进入 production master integration**.

**Spike NOT GO 路径**:
- 如果 1+3 都不工作 → paradigm 走回头 (e.g. solver 替换, 但 [03 paradigm death](03_paradigm_death_baseline.md) 已 verdict 死)
- 这种情况是项目层风险, 不只 Phase 1.3

cite: `docs/research/p3_b_design_v2_20260521/external_review/gemini_math_review_bundle_20260523/notes/CP_SAT_INTEGRATION_NOTES.md`

## P1.3 production master integration（旧子标签 P1.3B；原 P1.21）

### 12.1 step_8_apply_to_master 实施

<!-- DOC-SUBJECT:certified_exact_contract FIELD:cut_lifecycle_contract START sha256:4787489db07f2d910aa3066abf723b63e692046e047f7ae31e1c4109ba7cf8c6 -->
Cut-family LBBD work must respect the cut object lifecycle: generation, validation, replay, quarantine, storage, and master application are separate trust steps. `step_8_apply_to_master` is intentionally the unresolved integration boundary until the true master-integration phase starts.
<!-- DOC-SUBJECT:certified_exact_contract FIELD:cut_lifecycle_contract END -->

- 当前 `lifecycle.py::step_8_apply_to_master` NotImplementedError
- 接 `benders_loop` hook (env flag `EXACT_B_DESIGN_V2=1` 切新框架)
- Lazy → hard constraint 转化, 跟 master CP-SAT model 真集成
- **风险**: master 加 lazy constraint 可能影响 master.solve 收敛 (constraint
  push 太多导致 propagator overhead). mitigation: 阶梯式启用, 先 F1 single
  family 跑通后逐步 F2-F9 wire

### 12.2 evaluate hot path perf opt
GPT v3 Gemini r35 已识别, Step H 加 TODO docstring 留好:

- **cache parsed cert_dict on Cut**: 避 hot path `json.loads` 每次 ~2µs,
  10K calls 累 20-50ms/sec. 修法: attach 阶段 eager parse 挂内存
- **F4 evaluate 改 incremental connectivity**: 当前 `_bfs_component`
  O(|Grid|) per call. Phase 1.3 propagator 10K/sec 数量级退化. 修法 union-find
  with rollback / cache last-known component bitset + dirty flag
- **lru_cache(256) on _decode_region_bitset**: Step G land OK, 但 Phase 1.3
  跨 cut 反复调时 cache miss risk. 修法 attach-time eager decode 持 FrozenSet
  于 Cut.scope
- **风险**: cache invalidation bug. mitigation: 每 cache key 必 content-addressed
  (cert hash / source_digest), 不依赖 mtime / mutable state

### 12.3 by_exterior_watcher 实施
- GPT v3 Gemini r35 P0, Step H 暂 defer (sound 不需要, evaluate 重算保 — Step F)
- Phase 1.3 lazy → hard constraint 后, evaluator 不再被自动调, watcher 必必
- 实施: `CutStore` 加 `by_exterior_watcher: Dict[Cell, Set[CutId]]`, 跟
  exterior_blocks 变化时 trigger affected cut re-replay
- F1 GHOST_AGNOSTIC cut 注册到此 watcher
- **风险**: watcher 跟 ghost_watcher 重复 invalidate 浪费. mitigation: cut 只
  入一个 watcher (GHOST_AGNOSTIC → exterior_watcher, else → ghost_watcher)

### 12.4 propagator thread-safe 评估
- 当前 `lru_cache(256)` multiprocess.spawn 各 worker 一份, 不共享
- Phase 1.3 propagator 如果 master CP-SAT 内部多线程 callback, lru_cache 是
  thread-safe (GIL + functools 实施) 但 cache pollution 跨决策回溯仍要 verify
- HR1 thread-safe 是 Phase 1.3 评估项
- **风险**: multi-thread propagator callback 跨 worker 共享 store. mitigation:
  现 CP-SAT propagator 是单线程 callback, Phase 1.3 直接验; 多线程时再加 lock

---

