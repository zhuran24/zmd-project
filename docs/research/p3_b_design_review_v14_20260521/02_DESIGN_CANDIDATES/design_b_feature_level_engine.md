# Design B: Feature-level cut engine 自研

## 核心思路

**不在通用 CP-SAT solver 内加 cut**, 而是**自研一套 master state machine +
cut store + 5 cut family + proof object lifecycle**, 让 cut 表达力跟
master state machine 的 placement variable 直接对齐, 不被 solver-side cut
interface 表达力 ceiling 限制.

跟现有 27 lever 的关键区别:

- 27 lever 全 build on **通用 CP-SAT / SAT / LP solver**, cut 表达力受
  solver cut interface 限制 (e.g. OR-Tools 只支持 linear cut, 自研
  per-pose channel 撞 2.36M cstr scale)
- Design B 直接控制 master state machine, cut 可以是任意可计算的 prune
  predicate, 不必 linear

## B 设计核心 4 组件

### Component 1: Master state machine

```
state = {
    placement: Dict[instance_id, Optional[Pose]],   # 当前 placement (None = 未决定)
    cell_owner: Dict[(x, y), instance_id],          # 反向 index
    ghost_rect: Rect,                                # candidate ghost
    decision_trail: List[Decision],                  # 决策栈 (for backtrack)
    propagation_log: List[Inference],                # 单调 propagation
}
```

state 单调推进 (placement 只能 None → Pose, 不能 Pose → None 除非
backtrack 整段). 每次 placement 决定后跑 propagation: 移除 incompatible
pose, 移除 unreachable cell.

state machine **不是 CP-SAT**, 而是项目自管的数据结构. solver 角色: 只在
sub-problem oracle 里调通用 CP-SAT (binding / routing).

详 `03_B_DESIGN_DETAILS/master_state_machine.md`.

### Component 2: Cut store

cut 在 B 设计里是**独立 object**, 不是 solver 内部 lazy clause. cut object
有完整 6 步 lifecycle:

1. **Generate** — sub-problem oracle 返回 cert + cut spec
2. **Serialize** — 写入 disk (JSON, 跨 session 持久化)
3. **Deserialize** — load 后 reattach 到 master state machine
4. **Validate** — cut 数学论证检查 (i.e. cut 是否 sound)
5. **Resolve** — propagate cut 到当前 state 推 inference
6. **Replay** — 跨 candidate 回放, 验证 cut 在新 state 下正确

详 `03_B_DESIGN_DETAILS/cut_object_lifecycle.md`.

### Component 3: 5 cut family

5 类 cut 设计覆盖项目方识别的所有 prune dimension:

| Cut family | 数学描述 | 应对的 paradigm 死法 |
|---|---|---|
| **Region capacity cut** | sum_{i in region} cells_used(i) ≤ region_cap | 96% utilization 几何死结 |
| **Cutset cut** | edge-cut between component A / B ≥ k for flow | routing infeasibility |
| **Port exposure cut** | port at cell c facing dir d 必须 reachable | boundary_storage_port × perimeter trap |
| **Component reachability cut** | ghost rect + placement → connected routing graph | routing 不通的几何 cert |
| **Pattern no-good cut** | (i_1=p_1) ∧ ... ∧ (i_k=p_k) 不可同时为真 | sub-problem cert reduced to instance-pose conjunction |
| (额外) **Symmetry-lifted cut** | 132 manufacturing_3x3 同质 lifted no-good | 132 同质 facility 的 symmetry |

详 `03_B_DESIGN_DETAILS/5_cut_family_definitions.md`.

### Component 4: Bitset kernel

high-performance bitset 数据结构 for cell sets (70×70 = 4900 bit = 78
× 64-bit words). 用于:

- propagation 时 `placement.cells & free_mask` 等位运算
- cut storage `cut.cells_required` / `cut.cells_forbidden` 集合表达
- conflict detection
- 跨 candidate replay 的 invariant 校验

候选 implementation: Rust pyo3 / C++ pybind11 / numpy (uint64 array).

详 `03_B_DESIGN_DETAILS/bitset_kernel_options.md`.

## B 设计跟 cand C / 现有 paradigm 复用

复用范围:

- **Cand C Phase 2 v3 sub-problem oracle infra ~40-50%**:
  `feasibility_bootstrap.py` / `pricing_cache.py` / `boundary_constraints.py`
  当 sub-problem oracle 的 candidate generator + boundary feasibility check
- **死路 paradigm 的 oracle**:
  - B1 paradigm pose-bool master 当 fallback sub-problem oracle (small
    candidate 用)
  - PCR-CUT patch belt CP-SAT (Path 14) 当 cutset cut 的 cert oracle
  - D2 commodity flow (Path 17) 当 component reachability cut 的 cert oracle
  - SMT-MT outer pruning (smt_mt research) 当 region capacity cut 的 cert oracle

详 `03_B_DESIGN_DETAILS/reuse_from_cand_c.md`.

## B 设计的实施成本估算 (Claude pace)

按 10 day preparation + 3-5 month implementation:

- Preparation (work item 1.1-1.5 含此 stress test): 10 day
- Master state machine + decision/propagation core: ~3-4 weeks
- Cut store + 6-step lifecycle: ~2-3 weeks
- 5 cut family generator + oracle bridging: ~4-6 weeks
- Bitset kernel 选型 + integration: ~2-3 weeks
- Sub-problem oracle reuse + adapter: ~2 weeks
- 端到端 integration test + 27 anchor sweep: ~3-4 weeks
- **Total: ~3-5 month**

不是 "工程优化" 而是 paradigm-level investment. 项目方愿意投因为 27
lever 全死 + cand C 也 NO-GO 后**没有 cheaper 选项**.

## B 设计的优点

- **cut 表达力不受 solver 限制** — 任意可计算 predicate 都可以做 cut
- **proof object lifecycle 完整** — 跨 session / 跨 candidate replay,
  certified cert 可持久化
- **bitset kernel SIMD 加速** — 大 cell set 操作 native speed (cf. CP-SAT
  内部 2.36M OnlyEnforceIf 不能 vectorize)
- **5 cut family 直接编码 boundary_storage_port × perimeter trap 等几何
  invariant** — cand C LP 框架不能自然表达的 prune

## B 设计的缺点

- **重写 master form** — ~3-5 month investment, 风险高于 incremental
- **sub-problem oracle 仍依赖通用 CP-SAT / 现有 paradigm** — oracle 端
  不解锁的 trap (e.g. binding 端 over-restriction) 仍存在
- **第 6 类 cut family 风险** — 如果 5 类不够, 设计要补; stress test
  目的就是预判这个风险
- **bitset kernel 选型 trade-off** — Rust / C++ / numpy 各有 pro/con

## 跟 cand C 死法的解释

cand C v3 死在 set partition LP 的 cell exclusivity vs exactly-1 cover
contradiction. B 设计为什么能突破?

- B 不用 LP partition framework — placement 是 explicit decision, 不是 λ
  weighting
- 96% utilization 在 B 下不是 LP infeasibility, 而是 master state machine
  propagation 早期就识别 cell 冲突 (bitset & 操作)
- B 在 cell 冲突时直接产 sound cut (e.g. pattern no-good), 不会 LP 0 iter
  失败

## Stress test 视角

Design B 的 stress test 问题:

1. 5 cut family 在所有 96% utilization layout 上都能切吗?
3. 反例触发的 cut family 是哪类? 应加第 6 类还是改某个 cut 的范畴?
4. Master state machine 的 decision/propagation/backtrack schema 是否
   sound? (e.g. trail 是否正确表达 incremental state)
5. 6 步 lifecycle 是否完整? 缺哪步?
6. bitset kernel 选 Rust / C++ / numpy 哪个更适合 70×70 + 5000 instance
   PoC 阶段?

详细 prompt 在独立 prompt 文件.
