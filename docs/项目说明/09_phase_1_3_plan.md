# 09 — Phase 1.3 plan (P1.21 CP-SAT propagator 集成)

F5-F9 落地后, evaluator 才进真 hot path (10K calls/sec). 这阶段 perf opt
必要. GO 标准见 §8.3.

### 12.1 step_8_apply_to_master 实施
- 当前 `lifecycle.py:743-751` NotImplementedError
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

