# F6 Gemini Round 3 verdict (2026-05-25)

Round 3 cross-check on commit `97388a0` (post R2 fix).

## Gemini header 错乱 (round 2/3 混)

Prompt header 的 "Round 2" vs "Round 3" Edit 未生效 (file was not yet read,
so all 3 Edit attempts failed). Gemini 收到的 prompt 写了 "Round 2" 标识,
但 verify section 列的 R1+R2 fix 都涵盖了. 实质 review 仍 covers R2 commit.
所以 verdict 内容 valid, 只是 label 看起来像 round 2.

## Gemini verdict: NOT_GO with 2 finding

但两个 finding 经 main 验证后, **F6 Phase 1.2 实际 OK** (一个 WRONG, 一个
Phase 1.5+ defer).

## R2 fix verify (Gemini)

- **R2#1 evaluator scope check**: CORRECT — O(1) ghost+exterior drift guard
- **R2#2 generator default-disabled**: CORRECT
- **R2#3 missing key skip**: CORRECT — Phase 1.5+ semantic match

## Round 3 finding analysis

### Finding 1 [CRITICAL claimed] — Phase 1.5+ defer, 非 Phase 1.2 src bug

Gemini 说: evaluator 读 stale `cert.region_demand`, Phase 1.5+ Benders 中
master 改 demand 后 cut 不再 violating 但 evaluator 还说 violating →
permanently kill valid state.

**Main analysis**:
- Phase 1.2 generator default-disabled: 没 region_demand_overrides 时不发 cut.
  cert.region_demand 永远来自 caller explicit override, Phase 1.2 fixture
  +Phase 1.5+ master.solution 直接控制.
- Phase 1.5+ wiring: master.solution 改 region_demand → 新 master_iteration →
  caller 应有显式 cut invalidate 或加 by_master_iter watcher. 这是 wiring 时
  设计议题, 不是当下 src bug. evaluator 读 stale cert.region_demand 是其
  hot-path 语义 (cert == "Hall witness 在 cert 时刻 hold"), Phase 1.5+ wiring
  必须保证 master 改 demand → cut invalidate, 否则任何 family 都同此问题.
- 跟 [[gpt-pro-p1-2-in-progress-review]] 项目层的 "dark matter telemetry +
  cut store 评分淘汰" + Phase 1.5+ mini Step 8 spike 一脉 — Phase 1.5+ wiring
  通用机制, F6 不单独负担.

**Action**: 加入 Phase 1.5+ defer list (跟 F6 Round 1 Finding 4 multi-region
union 一致). 不修 Phase 1.2 src.

### Finding 2 [HIGH claimed] — **WRONG**

Gemini 说: generator `scope.blocked_cells_hash = compute_blocked_cells_hash(state)`
含 cell_owner, cell_owner 改 → hash 改 → step_6 invalidate F6 cut → 破 v1.1
invariant.

**Main verify**: `src/cuts/lifecycle.py:406-410`:
```python
def compute_blocked_cells_hash(state: BState) -> Hash:
    """blocked_cells = ghost ∪ exterior (跨层 sound — 不含 cell_owner)."""
    blocked = sorted(state.ghost_cells | state.exterior_blocks)
    ...
```

`compute_blocked_cells_hash` **已 explicit 不含 cell_owner** (docstring + 实现
都 only `ghost_cells | exterior_blocks`). cell_owner 改不影响 hash, cut 跨层
sound. Gemini 错估了此 helper 的语义.

**Action**: 无需修. Round 3 sanity disproof 3 个 都 cite 正确 file:line.

## Sanity disproved (Gemini 3 个)

1. partition_offsets 切碎 attacker → disproved (validator phase 11 strict
   recompute byte-equal lines 380-401)
2. placement_rule 不验 — disproved (Hall 物理 cap globally valid 不需要)
3. blocked 越界 — disproved (loop bound to region_cells safe)

## Stop condition (v3 protocol)

R1+R2+R3 共 5 真 finding (R1#1/2/3 + R2#1/2/3 修, R3#1 Phase 1.5+ defer, R3#2
WRONG). 剩下:
- Phase 1.5+ defer (R1#4 multi-region union, R3#1 evaluator stale demand)

符合 stop "GO 或只剩 Phase 1.5+ defer" — **close F6 cross-check loop**.

## Gate state (post all 3 round)

- pytest cuts: 327 passed (+35 from F6)
- mypy --strict 30 src 0 errors
- ruff / bandit / radon A 4.836 clean
- exit_criteria 3 PASS / 0 FAIL

## Phase 1.5+ defer list (F6 specific)

- Multi-region union Hall (spec §10 #5, R1#4) — left+bottom (0,0) corner
- Cert.region_demand watcher / invalidation (R3#1) — master_iteration tracking
- LP dual / Farkas algebraic witness — spec §3 lp_dual_ray_b64 字段 Phase 1.5+ 加
- Multi-shape Hall ILP feasibility — spec §1c / open question #1
- Interior region shape_hall — spec §10 #2
- Cut store F1 vs F6 dominance dedup (per integration agent) — perf-level

## 下一步: F7 power_hitting_set 启 N=5 子代理 design
