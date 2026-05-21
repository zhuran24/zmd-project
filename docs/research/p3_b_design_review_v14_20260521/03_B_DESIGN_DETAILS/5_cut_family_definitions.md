# B Component 3: 5 cut family 数学定义

5 类 cut + 1 个 symmetry-lifted variant. 每个 family 给:
- 数学定义
- soundness 论证
- generation 来源 (哪个 oracle 产)
- resolve 算法 (在 state machine 上 propagate 的方式)

## Family 1: Region Capacity cut

### 数学定义

```
对 region R ⊆ cells, 任意合法 layout 在 R 内 facility 占用 cell 总数 ≤ cap(R)
```

形式:

```
sum_{i : placement[i] is in R} |cells(placement[i]) ∩ R| ≤ cap_R
```

### Soundness

cap_R 通过 LP relaxation lower bound on infeasibility + Chvátal-Gomory
rounding 推. 比如:

- 给定 region R, region 内 free cells 总数 |R|
- 假设 R 内 facility footprint 总和 ≥ |R| + 1, 则任何 layout 在 R 内
  facility 占用 ≥ |R| + 1 > |R|, 矛盾
- → cap_R = |R|, cut 是 sound

`region_capacity` cut 推广覆盖了:
- 96% utilization 几何死结 (R = 全图)
- corridor capacity (R = corridor 切面)
- perimeter side capacity (R = 某边 perimeter)

### Generation

SAC-Hull paradigm (Path 13, lever 18) 的 corridor Menger min-cut 当 oracle.
PoC 在 Phase 2 v3 内 `boundary_constraints.py` 已实施 per-(cell, dir) net
flow equality.

### Resolve

```python
def resolve_region_capacity(cut, state):
    used = sum(|cells(state.placement[i]) ∩ cut.region| for i in placed)
    if used > cut.cap_R:
        return ResolveOutcome("infeasible")
    # filter pose_domain: 剩余 pose 选 cause used + new pose's R-cells > cap_R 的 → remove
    removed = {}
    for i, poses in state.pose_domain.items():
        for p in poses:
            if used + |cells(p) ∩ cut.region| > cut.cap_R:
                removed.setdefault(i, set()).add(p)
    return ResolveOutcome("domain_change", removed)
```

## Family 2: Cutset cut

### 数学定义

```
Routing graph G = (cells, belt_edges). 给定 partition (A, B) of cells,
任意 feasible routing 需要 edge_cut(A, B) ≥ k_AB
```

形式:

```
sum_{edges (u,v) : u in A, v in B, belt_usable(u,v) in layout} 1 ≥ k_AB
```

### Soundness

通过 Menger / max-flow min-cut theorem. 若 commodity c 必须从 source ∈ A
流到 sink ∈ B, 且 demand = k_AB, 则 partition (A, B) 上 belt-usable
edges ≥ k_AB 是 routing feasibility 的 necessary condition.

cut 不 sufficient (necessary ≠ sufficient — 见 Path 13 SAC-Hull verdict),
但 sound — 切掉的 layout 真的 routing infeasible.

### Generation

PCR-CUT (Path 14, lever 19) patch belt CP-SAT 当 oracle. 项目源码内
`docs/research/pcr_cut_patch_routing_conflict_20260519/` PoC infrastructure
可复用.

### Resolve

```python
def resolve_cutset(cut, state):
    # 算 layout 在 (A, B) partition 上的 belt-usable edges
    usable_edges = count_usable_edges(state, cut.side_a, cut.side_b)
    if usable_edges < cut.k_AB:
        return ResolveOutcome("infeasible")
    # filter: pose 加入会让 usable_edges 减到 < k_AB 的 → remove
    removed = {}
    for i, poses in state.pose_domain.items():
        for p in poses:
            edges_lost = count_lost_edges(state, p, cut.side_a, cut.side_b)
            if usable_edges - edges_lost < cut.k_AB:
                removed.setdefault(i, set()).add(p)
    return ResolveOutcome("domain_change", removed)
```

## Family 3: Port Exposure cut

### 数学定义

```
对 facility i 的 active port at cell c_port facing direction d, 
front cell c_front = c_port + offset(d) 必须 routing-clear (即不能被 facility 占).
```

形式:

```
forall i, p ∈ pose_domain[i]:
   forall (c_port, d) ∈ active_ports(p):
       cell_owner[c_front] is None or cell_owner[c_front] is i
```

### Soundness

来源: 项目 routing rule. port 前面必须空白 belt 才能接, 否则 routing
infeasibility. 这是 source-of-truth geometric rule (在
`routing_subproblem.py` 实施).

但 cut 不能 a priori 加 hard, 因为 active port 是 binding decision (master
不知). Phase 5 已验 a priori hard 全 INFEASIBLE.

→ B 设计的 port_exposure cut 是 **conditional on active port set**: 仅在
sub-problem 给出 cert "这个 port active" 后, cut 才 attach.

### Generation

B1 Phase 6 path-2 lazy demand cut + RAB-SEP binding-side owner+blocker
cert 当 oracle 推导哪些 port active. 也是 cand C `boundary_constraints.py`
覆盖范围.

### Resolve

```python
def resolve_port_exposure(cut, state):
    # 给定 cut 标的 (i, port_cell, direction)
    front_cell = port_cell + offset(direction)
    owner = state.cell_owner.get(front_cell)
    if owner is not None and owner != i:
        return ResolveOutcome("infeasible")
    # filter pose_domain: pose 占 front_cell 的 → remove (for j != i)
    removed = {}
    for j, poses in state.pose_domain.items():
        if j == i: continue
        for p in poses:
            if front_cell in p.cells:
                removed.setdefault(j, set()).add(p)
    return ResolveOutcome("domain_change", removed)
```

## Family 4: Component Reachability cut

### 数学定义

```
对 commodity c, source ∈ A, sink ∈ B, 必须存在 belt path 在 layout 中
从 A 到 B (component connectivity).
```

形式:

```
GhostRect ∪ Placement-occupied cells → free_cells (剩下的). 
free_cells 上 belt routing graph 必须有 path from src to sink.
```

### Soundness

来源: routing graph 拓扑. 若 component 不通, routing flow LP 必 infeasible.
D2 commodity flow (Path 17 / lever 22) PoC 即此 cert.

### Generation

D2 PoC infrastructure `src/models/d2_commodity_flow_core.py` + d2_separator
当 oracle. Phase 1 production class + LBBD wiring 已 land (commit 583c9dd).

### Resolve

```python
def resolve_component_reach(cut, state):
    # 算当前 state 下 free_cells 的 connected components
    components = compute_components(state.free_cells, cut.belt_edges)
    src_comp = components[cut.src_cell]
    sink_comp = components[cut.sink_cell]
    if src_comp != sink_comp:
        return ResolveOutcome("infeasible")
    # filter: pose 加入会切断 src→sink 路径的 → remove
    # (用 Tarjan biconnected component 找 cut vertices)
    ...
```

注: 这是 5 cut family 中 resolve 最贵的 — 需要 graph algorithm. PoC 优化点.

## Family 5: Pattern No-good cut

### 数学定义

```
不允许 (instance_1 = pose_1) ∧ (instance_2 = pose_2) ∧ ... ∧ (instance_k = pose_k)
同时为真.
```

形式:

```
not (forall t in [1, k]: placement[instance_t] = pose_t)
```

### Soundness

来源: sub-problem oracle 给出 cert "这 k 个 (instance, pose) 组合下
binding + routing 都不可行". no-good cut 不允许这个组合.

这是 LBBD 经典 cut form. Size = 1 的退化形式是 "不允许 (instance_i, pose_p)"
即 cell-cut. 6 paradigm 都退化到 size = 1 (lever 死法 B 共同根因).

→ B 设计想突破这个退化, 需要 sub-problem oracle 产 **size > 1 的 sound
no-good**. 这要求 oracle 能 minimal core 提取 (e.g. QuickXplain) 给出真
正 cluster-level cert.

### Generation

L16 Lazy Power Completion deletion-based core minimizer (lever 16) +
PCR-CUT QuickXplain (Path 14 lever 19 phase 2-3) 当 oracle. 已 PoC 实施.

### Resolve

```python
def resolve_pattern_nogood(cut, state):
    # 看 state 是否已 partially match cut
    matches = sum(1 for (i, p) in cut.forbidden_assignment.items()
                  if state.placement.get(i) == p)
    total = len(cut.forbidden_assignment)
    if matches == total:
        return ResolveOutcome("infeasible")
    if matches == total - 1:
        # 剩 1 个 (i, p) 配上就 violate, 必须 remove p from i's domain
        i, p = next((i, p) for (i, p) in cut.forbidden_assignment.items()
                    if state.placement.get(i) != p)
        return ResolveOutcome("domain_change", {i: {p}})
    return ResolveOutcome("no_change")
```

## Family 6 (variant): Symmetry-lifted cut

### 数学定义

```
对 symmetric orbit O = {i_1, ..., i_n} (132 manufacturing_3x3 同质),
单个 cut C 在 i_t 上有效, 则 lift 到所有 O 上.
```

### Soundness

来源: facility template 完全相同 (同 footprint, 同 IO spec, 同 power
coverage). 任何 permutation σ : O → O 是 problem 的 symmetry. cut C 在
i_t 上 sound, 则 σ(C) 在 σ(i_t) 上 sound.

### Generation

orbit detection: source-of-truth `mandatory_exact_instances.json` 内
`facility_type` + `operation_type` 同质 → 同 orbit. 132 个
`manufacturing_3x3` 至少 cluster 成几个 orbit (按 operation_type 分).

### Resolve

```python
def resolve_symmetry_lift(cut, state):
    # 对每个 σ : O → O, σ(cut) 都 attach
    # 实际不展开 (n! permutation 爆炸), 而是 lazy resolve
    for permutation σ in canonical_perms(cut.orbit):
        lifted_cut = apply_permutation(cut.rep_cut, σ)
        outcome = resolve_cut(lifted_cut, state)
        if outcome.kind == "infeasible":
            return outcome
        # accumulate domain_change
    ...
```

这是 5 cut family 之外的 cross-family **optimization**, 不是新 family.
适用于所有 family 1-5.

## 完备性 hypothesis (项目方判断, 待 stress test 验证)

项目方判断 5 cut family **可能完备** for 96% utilization layout 因为:

1. **Region capacity** cover 全图 / 子区域占用约束
2. **Cutset** cover routing graph 切面约束
3. **Port exposure** cover IO port direction × adjacency 约束
4. **Component reachability** cover routing connectivity 约束
5. **Pattern no-good** cover任何 sub-problem oracle 产的非几何 cert
6. **Symmetry-lifted** 不是新 family, 是 1-5 的 closure 优化

找出第 6 类 family 需求.

## Stress test 重点 prompt 数学构造方向

- **constraint interaction layout**: facility configuration 在单一 cut
  family 上 sound, 但 cut family 间相互作用产生新 infeasibility
- **boundary × cluster combination**: 46 boundary_storage_port × 132
  manufacturing_3x3 cluster 的某种 layout, 各 cut family 单独检查 OK 但
  组合 infeasible
- **power coverage trap**: facility 占 cell 后 power_pole 无 valid pose,
  master 没法识别 (因为 power_pole 是 residual_optional)
- **non-trivial routing topology**: layout 让 belt path 必须绕路, cutset
  + component reach 都过不滤
