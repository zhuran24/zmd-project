# B Component 1: Master state machine

## 状态 schema

```python
@dataclass
class MasterState:
    # Core placement
    placement: Dict[InstanceId, Optional[Pose]]
    cell_owner: Dict[Cell, InstanceId]               # 反向 index for O(1) cell→inst
    free_cells: Bitset                               # 4900-bit mask, free = 1
    
    # Ghost rectangle
    ghost_rect: Rect                                 # candidate ghost (fixed per inner LBBD pass)
    ghost_cells: Bitset                              # ghost 占用的 cell mask
    
    # Domain (per instance, 可用 pose 集合, 单调缩)
    pose_domain: Dict[InstanceId, FrozenSet[PoseId]]
    
    # Trail (for backtracking)
    decision_trail: List[Decision]                   # 决策 stack
    propagation_log: List[Inference]                 # 每次推理记录
    
    # Cut store linkage
    active_cuts: List[CutRef]                        # 当前已 attached cuts
    
    # Conflict tracking
    conflict_set: Optional[ConflictSet]              # 当前 conflict (if any)
```

## Decision 类型

```python
@dataclass(frozen=True)
class Decision:
    kind: Literal["assign", "exclude", "split"]
    instance: InstanceId
    pose: Optional[PoseId]                           # 若 kind = "assign" or "exclude"
    subset: Optional[FrozenSet[PoseId]]              # 若 kind = "split"
    depth: int                                       # 决策栈深度
    cause: DecisionCause                              # 谁触发 (search heuristic / cut / propagation)
```

3 种 decision:
- **assign**: 强制 instance i 选 pose p (placement[i] = p)
- **exclude**: 排除 pose p (pose_domain[i] -= {p})
- **split**: 跟 RAB-SEP / B&P 类似的 disjunctive split, pose_domain[i] 拆
  两个互斥 subset

## Inference 类型 (propagation 产物)

```python
@dataclass(frozen=True)
class Inference:
    kind: Literal["unit_pose", "domain_filter", "cell_conflict", "cut_conflict"]
    instance: Optional[InstanceId]
    pose: Optional[PoseId]
    cause: List[Tuple[DecisionId, CutId]]            # explanation
```

4 种 inference:
- **unit_pose**: domain 缩到 1 个 pose → 强制 assign
- **domain_filter**: cell 被别 instance 占了 → 缩 pose domain
- **cell_conflict**: 没法找到 cell 不冲突的 pose → backtrack
- **cut_conflict**: cut store 检查 placement 跟某 cut 冲突 → backtrack

## Propagation 算法

```python
def propagate(state: MasterState) -> Optional[ConflictSet]:
    """单调推理直到 fixpoint 或冲突. 不修改外部 trail."""
    while True:
        changed = False
        
        # Step 1: cell-level filter
        for i, poses in state.pose_domain.items():
            new_poses = {p for p in poses if compatible(state.cell_owner, i, p)}
            if new_poses != poses:
                state.pose_domain[i] = frozenset(new_poses)
                state.propagation_log.append(Inference("domain_filter", i, ...))
                changed = True
        
        # Step 2: unit pose detect
        for i, poses in state.pose_domain.items():
            if len(poses) == 1 and state.placement[i] is None:
                p = next(iter(poses))
                state.placement[i] = p
                state.cell_owner.update({c: i for c in p.cells})
                state.free_cells &= ~p.cells_bitset
                state.propagation_log.append(Inference("unit_pose", i, p, ...))
                changed = True
        
        # Step 3: cut-level filter
        for cut in state.active_cuts:
            outcome = cut.resolve(state)
            if outcome.kind == "infeasible":
                return outcome.conflict_set
            if outcome.kind == "domain_change":
                # cut shrink domain
                for (i, removed) in outcome.removed_poses:
                    state.pose_domain[i] -= removed
                    state.propagation_log.append(Inference("cut_conflict", i, ..., cut.id))
                    changed = True
        
        # Step 4: empty domain check
        for i, poses in state.pose_domain.items():
            if state.placement[i] is None and not poses:
                return ConflictSet.from_empty_domain(i, state.propagation_log)
        
        if not changed:
            return None  # fixpoint, no conflict
```

## Backtrack 算法

```python
def backtrack(state: MasterState, depth: int) -> None:
    """回溯到 depth, 撤销所有 depth 之后的 decision + inference."""
    while state.decision_trail and state.decision_trail[-1].depth >= depth:
        decision = state.decision_trail.pop()
        # 撤销 decision 引起的所有 inference
        while state.propagation_log and state.propagation_log[-1].cause_decision_id == decision.id:
            inf = state.propagation_log.pop()
            undo_inference(state, inf)
        undo_decision(state, decision)
```

注: `undo_decision` 需要 invariant — decision 只记 reversible 操作, e.g.
"pose_domain -= {p}" 而不是 "pose_domain = {p}". split decision 需要 record
原 subset.

## Search loop

```python
def b_search(state: MasterState) -> Optional[Layout]:
    """DFS + branch and bound + cut propagation."""
    while True:
        # Propagate to fixpoint
        conflict = propagate(state)
        if conflict is not None:
            # Generate cut from conflict
            new_cut = derive_cut(conflict, state.cut_store_oracle)
            cut_store.add(new_cut)
            
            # Backtrack
            if state.decision_trail.empty():
                return None  # infeasible from root
            state.backtrack(state.decision_trail[-1].depth - 1)
            continue
        
        # Check all placed
        if all(p is not None for p in state.placement.values()):
            # Sub-problem oracle: binding + routing
            verdict = sub_problem_oracle(state)
            if verdict.feasible:
                return Layout(state.placement)
            else:
                # Sub-problem returned cert + cut
                new_cut = verdict.cut
                cut_store.add(new_cut)
                state.backtrack(verdict.cut.causal_depth)
                continue
        
        # Choose decision
        decision = branching_heuristic(state)
        state.decision_trail.append(decision)
        apply_decision(state, decision)
```

## Trail / undo 关键 invariant

1. **decision_trail 严格栈** — push/pop only, no random access
2. **propagation_log 跟 decision_trail 绑定** — 每个 inference 记
   `cause_decision_id`, undo 时按栈 unwind
3. **pose_domain 单调缩** — 同一 (state, instance) 上 domain 只能缩, decision
   提供 "expand" 通过 backtrack 整段
4. **cell_owner 单调加** — 同一 (state, cell) 上 owner 只能 None → set,
   undo 通过 backtrack
5. **cut_store 跨 candidate 持久化** — 但 cut.active 状态跟 state machine
   绑定, 跨 candidate 时 cut 需要 reattach

## 实施 reuse 考量

state machine 自管, 不是通用 CP-SAT 内部 trail. 优势:
- 可以序列化整个 state + decision_trail 到 disk (debug + 跨 session resume)
- propagation rule 自定义, 不受 CP-SAT propagator 限制
- cut store reference state 内部 var, 不需要 lift 到 solver var

劣势:
- 性能调优要自己做 (CP-SAT propagator 是高度优化的 C++)
- 算法 bug 风险 (没有 CP-SAT 的 test coverage 当 baseline)

PoC 阶段: 用 Python state machine + numpy bitset 验算法正确. 性能优化 phase
换 Rust pyo3 / C++ pybind11. 详 `bitset_kernel_options.md`.

## 跟 27 lever 死法的关系

state machine + cut store 直接对应 lever 死法 B (cut 表达力被 master 维度
锁) 的解锁方向. cut 不再翻译回 CP-SAT linear cstr, 而是直接 propagate 到
state machine 的 pose_domain.

跟 lever 死法 E (augmented master 资源 dead end) 的关系: state machine 不
build CP-SAT model, 没有 2.36M cstr scale 风险. 但 cut store 大小要看 cut
数量 + 每 cut size, 待 PoC 实测.

## Stress test 视角

- state schema 是否完整? (e.g. 是否缺 port-binding 状态? 缺 ghost
  rectangle 跟 placement 的 mutual constraint state?)
- propagation 算法是否 sound? (cell-level filter + unit pose + cut filter
  顺序是否会漏 prune)
- backtrack invariant 是否 sufficient for soundness? (e.g. 是否会 leak
  cell_owner 不 undo)
- trail design 是否 efficient? (replay 时复用 trail 还是重跑 propagation)
