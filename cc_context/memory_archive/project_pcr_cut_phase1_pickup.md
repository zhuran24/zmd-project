---
name: pcr-cut-phase1-pickup
description: "PCR-CUT Phase 1 起跑点 — Phase 0 ✅ GO 已 commit (24ed7d8), Phase 1 真 implement patch belt CP-SAT (~650 LOC, 4-6h Claude). 关键实施细节 + GPT 计划书路径"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

# PCR-CUT Phase 1 pickup

## 现状

- Phase 0 ✅ GO (commit `24ed7d8`)
- working tree clean
- GPT v3 计划书完整: `/home/zhuran24/下载/B1_paradigm_breakthrough_plan_v3.md`

## Phase 1 目标

证明 patch 内真实 belt-level CP-SAT 在资源上可运行, 能在部分 layout 上给出
sound local INFEASIBLE.

**新文件**: `src/models/patch_routing_core.py` (~650 LOC)

**关键数据结构** (从 GPT 计划书):

```python
@dataclass(frozen=True)
class PatchSpec:
    patch_id: str
    cells: frozenset[tuple[int, int]]
    boundary_cells: frozenset[tuple[int, int]]
    bbox: tuple[int, int, int, int]
    source_witness: dict[str, Any]

@dataclass(frozen=True)
class PoseAssumption:
    instance_id: str
    pose_idx: int
    local_signature: str
    assumption_name: str

@dataclass
class PatchRoutingCoreResult:
    status: Literal["FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
    patch_id: str
    wall_s: float
    var_count: int
    constraint_count: int
    core: list[PoseAssumption]
    stats: dict[str, Any]
```

**关键函数**:

- `build_local_pose_signature(solution, facility_pools, patch)` — patch 内
  footprint mask + port-front cells + port direction + commodity role +
  operation_type + facility_type
- `enumerate_patch_binding_patterns(owner, pose, patch, generic_io)` — 从
  binding_subproblem `_build_fixed_operation_domains` 抽取 pattern semantics
  (不复用 raw cache 避免 layout-local filter 污染)
- `build_patch_routing_model(patch, pose_assumptions, boundary_relaxation=True)`
  — 复用 `src/models/routing_subproblem.py` patterns (capacity, bridge,
  continuity, port adherence). patch 外邻居用 boundary interface vars 替.
- `solve_patch_routing_core(bundle, seconds=5)` — solve + return result

**patch router 必保留**:

- `AddAtMostOne` per `(cell, layer)`
- elevated bridge 与 ground non-straight mutual exclusion
- incoming/outgoing continuity
- source/sink port adherence
- per-owner binding pattern choice

**boundary relaxation**:
- routing edge 从 patch cell 指向 patch 外: `boundary_out[k,b,dir]` 满足 successor
- patch 外 edge 进入 patch cell: `boundary_in[k,b,dir]` 满足 predecessor
- boundary vars 不设总容量上限 — deliberate over-approximation, 保 INFEASIBLE sound

## Phase 1 GO 标准

- main anchor (22,28) top patch build+solve **p95 ≤ 5s**
- **route_state_vars p95 ≤ 160K, constraints p95 ≤ 500K**
- 8 anchor first-layout 中 **≥ 3 个返回 INFEASIBLE**
- corner negative 不出现 false FEASIBLE

## NO-GO (abort)

- p95 solve > 15s 或 vars > 300K
- 全 patch FEASIBLE/UNKNOWN (relaxation 过松)
- patch-INFEASIBLE 只来自 single front cell + core size 1-3 (退化 RAB-SEP)

## 复用 routing_subproblem.py 关键 reference

- `src/models/routing_subproblem.py` 1037 LOC
- `class RoutingSubproblem` (line 533+) — full belt CP-SAT model
- `class RoutingGrid` (line 475+) — grid + neighbor lookup
- `_create_routing_variables` (line 747) — vars per cell+layer+commodity
- `_add_obstacle_exclusion` (line 827) — obstacle constraints

**实施策略**: 不直接 reuse RoutingSubproblem (它是 full-grid). 写
`PatchRoutingCore` from scratch, 模仿 patterns 但 restrict to patch_cells +
boundary_in/out vars.

## env

- `EXACT_B1_PATCH_ROUTING_CORE=1`
- `EXACT_B1_PATCH_ROUTING_CORE_SECONDS=5`
- `EXACT_B1_PATCH_ROUTING_CORE_MAX_CELLS=900`

## 起跑工作

1. `mkdir paths/14_patch_routing_conflict/` (跟 PCR Phase 0 同 docs dir)
2. 写 `src/models/patch_routing_core.py` from scratch (~650 LOC)
3. 写 trial `phase1_patch_router_poc.py` 测 8 anchor first-layout
4. verify p95 metrics
5. commit + 进 Phase 2

## Related

- [[paradigm-session-2026-05-18-19]] — 整 session 上下文
- [[paradigm-phase0-cheap-gate]] — paradigm 验证 workflow
