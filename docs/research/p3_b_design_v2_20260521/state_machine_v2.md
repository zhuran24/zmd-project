# B Design v2 — Master State Machine (v2)

> **Status**: Phase 0 Day 3-9 Dev A deliverable (parallel with `cut_lifecycle_v2.md`)
> **Supersedes**: `docs/research/p3_b_design_review_v14_20260521/03_B_DESIGN_DETAILS/master_state_machine.md`
> **Cross-check verdict on v14**: B direction GO; v14 state schema NO-GO as written (per GPT pro v14 + Gemini round 12 + Gemini round 13)
> **Scope**: state schema / invariants / trail+backtrack / cut-resolve contract / ghost-conditioned domain. **Does not** define cut lifecycle / cut family taxonomy / search heuristic — those live in `cut_lifecycle_v2.md` and §5 cut family docs.

---

## 1. TL;DR

State machine v2 changes the **basis of the state**: from per-instance pose
assignment (v14, re-introduces 10^134 label symmetry) to **group/orbit-count
state** (anonymous within facility group).

Five core decisions:

1. **Group basis**: state stores `GroupState` per facility group, not per
   instance. `selected_pose_set` is a multiset over group's pose domain —
   no instance ID inside.
2. **Four derived domain projections**: `binding_domain_summary`,
   `forced_terminal_resources`, `front_resource_load`,
   `power_cover_domain` — pre-projected per `(group, pose)` so cut resolve
   doesn't rebuild from raw geometry per call.
3. **Reversible delta trail**: 8 `TrailEvent` variants, decision-level
   stack only — no `cause_decision_id` guessing.
4. **Anonymous slot ref cut contract**: cuts reference `(group_id, slot_idx)`
   not `instance_id`. Resolve maps slot → group's currently selected
   anonymous instance in enumeration order.
5. **Ghost-conditioned `power_cover_domain`**: `ghost_rect` changes
   invalidate the projection; trail records `GhostConditionChange` events.

---

## 2. State schema

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Literal, Optional, Set, Tuple, Counter

# Type aliases (consistent with cand C Phase 1 + src/models/)
GroupId   = str                                  # e.g. "crusher_blue_iron"
PoseId    = Tuple[str, int]                      # (facility_type, pose_idx) — cand C convention
Cell      = Tuple[int, int]                      # (x, y), 0 <= x,y < 70
Resource  = Tuple[Cell, str]                     # (cell, layer)  layer ∈ {"port", "power", "belt", ...}
SlotIdx   = int                                  # 0-based anonymous slot inside group

# Anonymous instance reference — used by cut literals (see §5)
AnonymousSlotRef = Tuple[GroupId, SlotIdx]


@dataclass
class GroupState:
    """One facility group (e.g. all 34 crusher_blue_iron instances)."""
    group_id: GroupId
    demand: int                                  # how many instances must be placed
    pose_domain: FrozenSet[PoseId]               # group-shared candidate poses (single-pose origin)
    selected_poses: List[PoseId] = field(default_factory=list)
                                                 # selected count = len(selected_poses)
                                                 # ordering = anonymous slot index (0..demand-1)
                                                 # NOT instance-bound — slot i is interchangeable
                                                 # with slot j for i,j < len(selected_poses)
    remaining_count: int = -1                    # = demand - len(selected_poses)

    def __post_init__(self) -> None:
        if self.remaining_count == -1:
            self.remaining_count = self.demand - len(self.selected_poses)


@dataclass
class BindingDomain:
    """Per (group, pose) projection: which ports of the facility are
    'active' in any binding feasible for this pose.  Reused from
    src/models/port_binding.py pose_binding_domain output."""
    active_port_set: FrozenSet[Tuple[Cell, str]]    # (cell, direction) tuples
    # 'optional' ports: enumerator may or may not bind them
    optional_port_set: FrozenSet[Tuple[Cell, str]] = frozenset()


@dataclass
class DerivedDomain:
    """All cell-/resource-level projections, recomputed on placement delta.
    Lightweight ONLY — no CP-SAT vars (avoid L23 32GB blow-up)."""

    # (group, pose) -> binding-feasible port set (see BindingDomain)
    binding_domain_summary: Dict[Tuple[GroupId, PoseId], BindingDomain] \
        = field(default_factory=dict)

    # (group, pose) -> set of (cell, layer) resources that MUST be active
    # if this pose is placed (forced terminal cells)
    forced_terminal_resources: Dict[Tuple[GroupId, PoseId], FrozenSet[Resource]] \
        = field(default_factory=dict)

    # Aggregated load on each (cell, layer) — Counter so undo is a -1 delta
    front_resource_load: Counter[Resource] = field(default_factory=Counter)

    # (group, pose) -> bitset over (PowerPolePose_id) — which power poles
    # could cover this facility pose under current ghost_rect
    # Bitset (numpy uint64 array) keyed by global pole-pose index
    power_cover_domain: Dict[Tuple[GroupId, PoseId], "Bitset"] \
        = field(default_factory=dict)

    # Invalidation flag — set True when ghost_rect changes; resolver
    # rebuilds power_cover_domain lazily on next access
    power_cover_invalid: bool = False


@dataclass
class MasterStateV2:
    # --- Group-orbit state (replaces v14's per-instance placement) ---
    groups: Dict[GroupId, GroupState]

    # --- Cell ownership (forward index) ---
    # cell_owner[cell] = (group_id, slot_idx) if owned, else absent
    # Note: stored as (group, slot) not instance_id — invariant I2 below
    cell_owner: Dict[Cell, AnonymousSlotRef] = field(default_factory=dict)

    # 4900-bit mask (numpy uint8 array of len 4900 / 8)
    free_cells: "Bitset" = field(default_factory=lambda: bitset_all_set(4900))

    # --- Ghost rectangle (fixed per inner LBBD pass) ---
    ghost_rect: Optional["Rect"] = None
    ghost_cells: "Bitset" = field(default_factory=lambda: bitset_empty(4900))

    # --- Derived domain (recomputed on placement delta) ---
    derived: DerivedDomain = field(default_factory=DerivedDomain)

    # --- Trail (reversible) ---
    trail: List["TrailEvent"] = field(default_factory=list)
    decision_level: int = 0                          # current depth (0 = root)
    decision_marks: List[int] = field(default_factory=list)
                                                     # trail index at each
                                                     # decision_level boundary

    # --- Active cuts (resolution state, see §5) ---
    active_cuts: List["CutRef"] = field(default_factory=list)

    # --- Conflict (if propagation reached infeasibility) ---
    conflict: Optional["ConflictSet"] = None
```

### TrailEvent — 8 reversible variants

```python
TrailEvent = (
    GroupSelectAdd      # group.selected_poses.append(pose) at slot_idx
  | GroupSelectRemove   # (currently unused — only undo path)
  | DomainShrink        # GroupState.pose_domain -= removed
  | CellOwnerSet        # cell_owner[cell] = (group, slot)
  | ForcedTerminalAdd   # forced_terminal_resources[(g,p)] insert
  | FrontResourceDelta  # Counter[(cell, layer)] += sign
  | PowerCoverShrink    # power_cover_domain[(g,p)] &= mask
  | GhostConditionChange # ghost_rect updated → set power_cover_invalid
  | CutAttach           # active_cuts.append(cut)
  | CutActivate         # cut.state = ACTIVE  (see cut_lifecycle_v2.md)
)
```

(8 reversible-data events + 2 cut-lifecycle events = 10 total. Cut events
share decision_level book-keeping but their semantic state lives in
`CutRef` — see `cut_lifecycle_v2.md`.)

Each event is a `@dataclass(frozen=True)` carrying:
- `decision_level: int` — at which level it was emitted
- `reason: Literal[...]` — for debug / cert; **not** used by backtrack logic
- payload (e.g. `(group_id, pose_id)` for `GroupSelectAdd`)

---

## 3. State invariants

Six invariants enforced by `validate_state(state) -> None` (raises on
violation in debug mode, no-op in production).

| # | Invariant | Complexity |
|---|---|---|
| I1 | For all `g`: `len(g.selected_poses) == g.demand - g.remaining_count` and `0 <= remaining_count <= demand` | O(\|groups\|) ≈ O(50) |
| I2 | Every selected pose's cells are in `cell_owner`, and `cell_owner[c] == (g, slot)` matches the slot index of the pose in `g.selected_poses` | O(Σ placed_cells) ≈ O(2500) |
| I3 | `free_cells == all_cells \ ghost_cells \ {c : c ∈ cell_owner}` (bitset XOR check) | O(4900/64) ≈ O(77) bitset words |
| I4 | For every `(g, p) ∈ derived.binding_domain_summary`: `p ∈ g.pose_domain` ∨ `p ∈ g.selected_poses` (no orphan projection) | O(\|derived.binding\|) |
| I5 | `front_resource_load[r] == #{(g, slot) : r ∈ forced_terminal_resources[(g, p_slot)] }` (consistency between aggregate and per-pose) | O(Σ forced terminals) |
| I6 | If `derived.power_cover_invalid == False`: every entry in `power_cover_domain` was computed under current `ghost_rect`; else: entries are stale and must be rebuilt on next read | O(1) flag check |

**Total validator complexity**: O(\|groups\| + \|placed cells\| + 4900/64 + \|forced terminals\|).
Empirically bounded by **O(266 instances + 4900 cells) ≈ O(5K) operations**
— well below per-propagation cost. Safe to enable in debug mode after
every propagation fixpoint.

**Crucial NOT-checks** (skipped on purpose):
- We do NOT check `placement[i] ∈ pose_domain[i]` per instance (no instance-level state).
- We do NOT enumerate all 280K poses' compatibility per call (only delta'd ones).
- We do NOT recompute `power_cover_domain` unless `power_cover_invalid` is true.

`resolve_region_capacity` double-count bug fix (commit `976bc10`,
`if i in placed: continue`) is enforced by **I2**: a placed pose's cells
are in `cell_owner`, so any resource counting that iterates `cell_owner`
naturally skips already-placed; only iteration over `pose_domain` candidates
needs explicit "placed exclusion", and we centralize that in
`iter_placeable(group)`.

---

## 4. Trail + backtrack algorithm

### Decision level discipline

```
decision_level 0 = root
push_decision()  → decision_level += 1; decision_marks.append(len(trail))
pop_decision()   → undo all trail events with event.decision_level == decision_level;
                   decision_level -= 1; decision_marks.pop()
```

Trail is **append-only during forward propagation**, **rewound LIFO on
backtrack**. No event ever moves between levels.

### Undo order

```python
def backtrack_to_level(state: MasterStateV2, target_level: int) -> None:
    """Pop events strictly above target_level, in reverse trail order."""
    assert target_level < state.decision_level
    while state.decision_level > target_level:
        mark = state.decision_marks[-1]
        # All trail[mark:] belong to current decision_level (strict invariant)
        while len(state.trail) > mark:
            event = state.trail.pop()
            _undo(state, event)
        state.decision_marks.pop()
        state.decision_level -= 1
```

`_undo` dispatch table (one per `TrailEvent` variant):

| Event | Undo action |
|---|---|
| `GroupSelectAdd(g, pose, slot)` | `g.selected_poses.pop(slot)`; `g.remaining_count += 1`; assert slot == len after pop |
| `DomainShrink(g, removed_set)` | `g.pose_domain = g.pose_domain ∪ removed_set` (frozenset re-bind) |
| `CellOwnerSet(c, prev)` | `cell_owner[c] = prev` if prev else `del cell_owner[c]`; flip `free_cells` bit |
| `ForcedTerminalAdd((g,p), resource)` | `forced_terminal_resources[(g,p)].discard(resource)` |
| `FrontResourceDelta(r, sign)` | `front_resource_load[r] -= sign` (drop key if reaches 0) |
| `PowerCoverShrink((g,p), removed_bits)` | `power_cover_domain[(g,p)] \|= removed_bits` |
| `GhostConditionChange(old_rect, old_cells)` | `ghost_rect = old_rect`; `ghost_cells = old_cells`; set `power_cover_invalid = True` |
| `CutAttach(cut)` / `CutActivate(cut)` | see `cut_lifecycle_v2.md` §undo |

**Why no `cause_decision_id` (v14 design rejected)**: v14 tied each
inference to a single decision via `cause_decision_id`, but in practice
one inference may be a consequence of `D1 ∧ D2 ∧ C5` (decisions + cuts).
We instead tag every event with the **decision_level at emission time**
and roll back **strictly by level**, not by causal graph traversal. This
guarantees soundness — if you backtrack to level k, **all** events
emitted at level > k are undone in LIFO order, regardless of cause.

---

## 5. Group state ↔ Port-binding Cut interface contract

### The conflict (Gemini round 13 cross-check finding)

- State is group-based: "group `crusher_blue_iron` has 3 slots filled with
  poses [p1, p1, p2]".
- A Port-binding Cut (GPT cut family #6) needs to express:
  "NOT(some specific 3-instance combination of crusher pose at certain
  cells AND refinery pose at certain cells)".

Naive solution (cut carries `instance_id`) **re-introduces the 10^134
label symmetry** we just removed.

### Anonymous slot ref contract

A cut's literal pattern uses `AnonymousSlotRef = (GroupId, SlotIdx)`:

```python
@dataclass(frozen=True)
class CutLiteral:
    slot_ref: AnonymousSlotRef           # ("crusher_blue_iron", 2)
    pose: PoseId                         # ("crusher_blue_iron", 17)
    polarity: bool                       # True = literal positive ("== pose"), False = negative

@dataclass(frozen=True)
class CutPattern:
    literals: Tuple[CutLiteral, ...]
    # Cut active iff ∀ literal: group[slot].pose == literal.pose ⇔ polarity
```

### Resolve mapping (group → anonymous slots)

When `resolve_cut(cut, state)` checks if the cut applies:

```python
def resolve_cut(cut: CutPattern, state: MasterStateV2) -> CutOutcome:
    """Check cut against ALL anonymous slot permutations within each
    group that the cut references."""
    referenced_groups = {lit.slot_ref[0] for lit in cut.literals}
    # For each referenced group, the cut indexes specific slot positions.
    # Since slots inside a group are INTERCHANGEABLE (group-orbit basis),
    # the cut must be checked against EVERY assignment of the cut's slot
    # positions to currently-selected slots — i.e., a subset enumeration.
    return _check_anonymous_subset_match(cut, state, referenced_groups)
```

**Key property — soundness across group permutation**: because slot
indices inside a group are anonymous (any permutation is the same state),
a cut that uses `slot_ref=("crusher", 2)` is equivalent to one using
`slot_ref=("crusher", 5)` after slot relabeling. Resolution must
**enumerate all subset matches**, not just the named slot.

**Practical implementation**: cut carries `referenced_group_sizes`
(`{group: required_slot_count}`) so resolver pre-checks
`len(g.selected_poses) >= required_slot_count` and skips otherwise.

### Cut generation contract

A subproblem (binding / routing / patch core) returns a conflict over
**named instance IDs**. The cut-construction step translates:

```
(crusher_blue_iron_007 → p1, refinery_steel_002 → p3) is INFEASIBLE
  ↓  group-canonicalization
(group=crusher_blue_iron, ANY slot → p1) ∧ (group=refinery_steel, ANY slot → p3) is INFEASIBLE
```

This canonicalization is **lossless under group symmetry**: every
permutation of instance IDs within a group yields the same group-anonymous
cut. The cut therefore prunes the **full orbit**, not just one instance
assignment — directly addressing v14's label-symmetry blow-up.

---

## 6. Ghost-conditioned `power_cover_domain`

`benders_loop.py:4219-4268` already implements ghost-conditioned power
no-good logic. State machine v2 enforces the same invariant at
projection layer.

### Trigger

`ghost_rect` changes through one path only: outer LBBD candidate switch
or a `ghost_anchor` decision. On change:

```python
def set_ghost_rect(state: MasterStateV2, new_rect: Rect) -> None:
    state.trail.append(GhostConditionChange(
        decision_level=state.decision_level,
        old_rect=state.ghost_rect,
        old_cells=state.ghost_cells,
        new_rect=new_rect,
        new_cells=compute_ghost_cells(new_rect),
    ))
    state.ghost_rect = new_rect
    state.ghost_cells = compute_ghost_cells(new_rect)
    state.derived.power_cover_invalid = True
    # power_cover_domain entries NOT cleared eagerly; lazy rebuild
```

### Lazy rebuild

```python
def get_power_cover(state, group, pose) -> Bitset:
    if state.derived.power_cover_invalid:
        # Rebuild all entries against current ghost_rect
        _rebuild_power_cover_domain(state)
        state.derived.power_cover_invalid = False
    return state.derived.power_cover_domain[(group, pose)]
```

`_rebuild_power_cover_domain` iterates only `(group, pose) ∈ active
candidate pool` (intersect with `g.pose_domain ∪ g.selected_poses`),
applying ghost-cell mask. Cost is O(\|pose pool\| × \|pole poses\| / 64)
bitset ops; precomputed pole-coverage tables from cand C share-cache
make this seconds-level per rebuild on full 280K pool (verified by
Phase 2 v3 cache build_seconds < 5s).

### Undo

`GhostConditionChange` undo restores `ghost_rect` and `ghost_cells` and
sets `power_cover_invalid = True` again (forces lazy rebuild on next
read against the restored rect). No need to undo individual
`PowerCoverShrink` events emitted between two `GhostConditionChange`s —
they were rebuilt against the now-restored ghost, and lazy rebuild
overwrites them.

---

## 7. Reuse from cand C Phase 2 v3

### Direct reuse (no schema change)

| Source | What we take | Adapter needed? |
|---|---|---|
| `cand_c_column_generation_phase1_20260521/column_grammar.py: BoundarySignature` | Used **as-is** as a tag on derived projections that cache "boundary effect" of a pose group. Same `(perimeter_ports, perimeter_cells)` schema; `canonical_bytes()` for hash-keying cache entries. | No |
| `cand_c_column_generation_phase2_20260521/pricing_cache.py: PricingShareCache.cell_index` | Used as the **pose-domain index** backing `iter_placeable(group, region)`. Same `(x,y) -> List[(tpl, pose_idx)]` schema. Build once per outer candidate, query during propagation. | No |
| `pricing_cache.py: instance_pose_index` | **Adapter only**: cand C's iid-keyed index → B's group-keyed index. Mapping `iid → group` is 1-to-1 via canonical_rules; group-level dedup makes B's index smaller (one entry per group, not per iid). | Yes — thin wrap `build_group_pose_index(cache, instances)` |

### Partial reuse (logic, new wrapping)

| Source | What we take |
|---|---|
| `phase1/column_grammar.py: compute_boundary_signature` | Reused unchanged as pure function for building the cache key in `DerivedDomain.binding_domain_summary`. |
| `phase1/integer_validator.py: check_set_partitioning` (referenced in `reuse_from_cand_c.md`) | Hooks into our `validate_state` extension when sub-problem oracle returns a candidate full assignment, to verify covering=demand exactly. |
| `phase2/pricing_cache.build_share_cache` ghost-filter step | We refactor the `ghost_filter_fn` signature to accept a `state` so it can use `state.ghost_cells` directly instead of a closure. |

### Dropped from cand C (explicitly NOT reused)

- `ryan_foster.py` — RF branching on λ-space, B is not in λ-space.
- `alternative_blueprint_generator.py` — A1 LP-level column gen, B uses no LP.
- RMP solving in `phase2_probe.py` — set-covering LP, B is pure feasibility.

### Cross-check against `cut_lifecycle_v2.md` (Dev B parallel)

This doc and Dev B's doc share two contract surfaces — **NOT read here per
hard constraint**, but the schemas committed must match:

1. `CutRef` / `CutPattern` / `CutLiteral` — defined here in §5; Dev B
   document defines lifecycle states (PROPOSED → ACTIVE → REVOKED).
2. `TrailEvent.CutAttach` / `.CutActivate` — defined here; semantics
   (when emitted, who emits) belong to Dev B.

Integration test (Phase 0 Day 10+) must verify both definitions agree.

---

## 8. Open questions / risks

| # | Question | Severity | Defer to |
|---|---|---|---|
| O1 | **Cut subset-match performance**: §5 anonymous slot resolve enumerates subsets; if a group has 34 selected slots and a cut references 3 of them, that's C(34,3)=5984 matches per cut per propagation. With ~10^3 cuts active, naïve resolve = 6M ops / fixpoint. Need incremental match index (e.g. by literal pose). | High | Implementation Phase 1: build inverted index `pose → list[CutLiteral]` |
| O2 | **`power_cover_domain` rebuild cost on ghost change**: lazy rebuild OK for single ghost change, but if outer search switches candidates rapidly (e.g. SMT-MT outer pruning iteration), rebuild dominates. Cache rebuilt versions keyed by `ghost_rect`? | Medium | Phase 1 PoC: measure rebuild rate; decide LRU cache vs eager invalidate |
| O3 | **`forced_terminal_resources` granularity**: do we need (cell, layer) tuples, or is (cell, port_dir) sufficient? Depends on cut family #6 (Port Exposure) and Dev B's `cut_lifecycle_v2.md` resource model. | Medium | Cross-sync with Dev B before Phase 1 |
| O4 | **Invariant I5 in production**: consistency check between aggregate `front_resource_load` and per-pose `forced_terminal_resources` is O(Σ forced terminals) — may be hot path. Production mode disables I5; debug mode runs it. Need a 'fast path' invariant that's O(1)? | Low | Tracked; production toggle is sufficient |
| O5 | **Group orbit vs ghost-rect symmetry interaction**: when ghost_rect breaks a group's geometric symmetry (e.g. some poses now overlap ghost), the group's effective pose_domain shrinks. We handle this via `DomainShrink` event, but the **shrink itself is decision_level=0 if ghost is fixed at outer LBBD level**, vs decision_level>0 if ghost moved during inner search. Backtrack semantics depend on which. Document explicit rule. | Medium | Implementation: `set_ghost_rect` at level 0 only OR always at current level |

---

## Cross-references

- `cut_lifecycle_v2.md` (Dev B parallel, NOT read during authoring) — cut state machine
- `docs/research/p3_b_design_review_v14_20260521/03_B_DESIGN_DETAILS/master_state_machine.md` — v14 baseline (superseded by this doc)
- `docs/research/p3_b_design_review_v14_20260521/03_B_DESIGN_DETAILS/reuse_from_cand_c.md` — cand C reuse map
- `docs/research/cand_c_column_generation_phase1_20260521/column_grammar.py` — `BoundarySignature` source
- `docs/research/cand_c_column_generation_phase2_20260521/pricing_cache.py` — `PricingShareCache` source
- `src/models/pose_bool_exact_master.py` — group-anonymous pose-bool reference impl
- `src/search/benders_loop.py:4219-4268` — ghost-conditioned power no-good reference impl
- commit `976bc10` — `resolve_region_capacity` double-count bug fix (enforced here by invariant I2)
