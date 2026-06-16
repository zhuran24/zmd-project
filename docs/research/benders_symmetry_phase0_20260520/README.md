# Phase 0 cheap gate — Benders symmetry / cut-orbit lifting

**Date**: 2026-05-20
**Scope**: Phase 0 only (cheap gate, no src changes)
**Verdict so far**: TBD (probe written, not yet executed)

## Direction

Benders decomposition + **typed automorphism graph** over (poses × grid cells × directed cells), with **cut orbit lifting**: one rejected core (typically a single pose no-good in our 24-lever pattern) is mapped through the graph's automorphism orbit to an *orbit family* of equivalent infeasible cores. One cut excludes the whole family in sound mode.

This is paradigm-level different from prior 24 levers because:
- Prior levers all kept `cut_size = 1` after translation back to master (instance-pose no-good). Master never had the language to represent the orbit.
- Symmetry detection runs **offline** on the typed graph once per outer-search candidate; lifting then amortizes across all iterations.
- The graph encodes constraint structure (cells + port directions + boundary + commodity role) as graph colors, so automorphisms preserve the constraints they were colored by.

## Phase 0 hypothesis

A **typed symmetry detection graph** containing:

| Node type | Count (est.) | Color = |
|---|---|---|
| pose | ~280K | (facility_type, footprint_hash, port_signature) |
| cell | 4,900 | ("cell", boundary_flag) |
| dir-cell | 19,600 | ("dir", direction, dst_in_grid, dst_boundary) |

with edges:
- pose ↔ cell for each occupied cell of the pose
- pose ↔ dir-cell for each input/output port of the pose

**will** have:
- nontrivial orbit count ≥ 10 (operation_type groups + translation symmetries)
- effective multiplier ≥ 5 on synthetic rejected cores (i.e., the average orbit reachable from a typed pose is ≥ 5)
- 100% sound orbit-image replay (stub: orbit members are translation-equivalent, no occupancy overlap)

If those hold under wall ≤ 60s + RSS ≤ 8GB on a single 70×70 build, Phase 1 (real cut-lift + benders_loop hook) is justified.

## Metrics (gate spec)

| ID | Metric | Cap / Threshold |
|---|---|---|
| m1 | graph_build_seconds | ≤ 60s |
| m2 | automorphism_seconds | ≤ 60s (m1+m2 ≤ 60s combined) |
| m3 | graph_rss_gb | ≤ 8 GB |
| m4 | nontrivial_orbit_count | ≥ 10 |
| m5 | effective_multiplier (avg over 5 synthetic cores) | min ≥ 2, avg ≥ 5 |
| m6 | orbit_image_replay_soundness | = 100% |

**GO**: all pass. **NO-GO**: any fail.

## How to run

```bash
# Dry-run (validates pynauty import + data files + pose schema; no graph build)
.venv/bin/python docs/research/benders_symmetry_phase0_20260520/phase0_probe.py --dry-run

# Live (builds full graph, runs automorphism, ~1h budget)
.venv/bin/python docs/research/benders_symmetry_phase0_20260520/phase0_probe.py
```

Outputs `phase0_stats.json` next to the probe.

## Dependencies

- `pynauty 2.8.8.1` — installed clean via `pip install pynauty` (built local C wheel against system nauty; no version-conflict warnings, no `--no-deps` needed). Smoke-tested with a 4-cycle: 2 generators, group size 4, orbits `[0,1,1,0]` — correct.
- No other new deps; project's existing Python 3.13 venv used.

Why pynauty over alternatives:
- **networkx GraphMatcher**: Python-only, O(n!) worst-case isomorphism — wholly inadequate for 280K + 24K nodes.
- **pybliss / sage**: pybliss not packaged on PyPI; SAGE pulls 1+ GB of math stack.
- **pynauty**: Direct binding to nauty, the field's reference automorphism backend; built locally in 8 seconds; supports vertex coloring natively via `set_vertex_coloring([{cls0}, {cls1}, ...])`.

## Graph schema decisions

1. **Footprint hash** translates occupied-cells to anchor-relative `(0,0)` before hashing → poses that differ only by translation share the same color, enabling translation orbits without exploding the color space.
2. **Port signature** is anchor-relative + includes direction + role (in/out) → distinguishes `port_mode=TB` from `LR` etc., but treats two translation-equivalent same-mode poses as same color.
3. **Cell node color** includes a `boundary_flag` because boundary cells are special in the project (boundary_storage_port instances live only on boundary). Non-boundary cells stay uniform.
4. **Directed cell node color** includes `(direction, dst_in_grid, dst_boundary)` — direction matters for port routing; `dst_in_grid` separates ports pointing outward (off-grid) from inward; `dst_boundary` lets the graph distinguish ports adjacent to boundary even when the directed-cell itself isn't on boundary.
5. **No edges between cells** — only pose ↔ {cell, dir-cell}. The grid's geometric adjacency is **intentionally not** encoded as a graph edge, because pose nodes carry the geometry implicitly through which cells they connect to. Adding cell-adjacency edges would crush the symmetry (the grid has only the identity + 8-fold dihedral). This is the central design choice.

## Failure modes (5 documented for Phase 0)

1. **Symmetry shattered by ghost/boundary/port-direction colors** — too-fine typing collapses all orbits to singletons; m4 < 10. Mitigation: probe reports nontrivial orbit count, sizes, and color summary; if shattered, we can relax (drop boundary_flag from cells) in Phase 1.
2. **Graph automorphism unsound vs LBBD oracle** — even with rich typing, two pose vertices might be graph-isomorphic yet differ in routing-feasibility. Phase 0 stub-replay (occupancy-overlap proxy) can miss this; Phase 1 must replay through the real binding/routing oracles before declaring soundness.
3. **Orbit image replay actually FEASIBLE** — if a rejected core's orbit-mate happens to be solvable by binding/routing, lifting is unsound. Phase 0 m6 measures this as a 0/1 flag per orbit; if any orbit produces a feasible image, lift is invalid as-is and Phase 1 needs constraint-aware orbit pruning.
4. **Graph build resource cliff** — 280K poses × 9-15 edges each = ~3M edges; if pynauty's adjacency representation pushes RSS past 8 GB, the gate fails. Mitigation: probe has `cap_poses_per_template` knob (unused by default) to bisect.
5. **Aggregate cut degenerates to L23-lite** — if all orbits happen to be tiny (size 2-3) AND only on power_pole / cell symmetries, the orbit cut adds nothing beyond what cell-cut levers (L23 Phase 5) already tried. Phase 0 reports `top_orbit_sizes` so we can eyeball whether orbits are meaningfully large (operation_type-level, ≥ 30) vs trivial (template-level, ≤ 5).

## What Phase 1 would look like (only if Phase 0 = GO)

1. Wire `benders_loop._run_certified_exact` cut-emission path: after a no-good cut is emitted, look up the rejected pose's orbit and emit one master constraint per orbit member (or aggregate via a single `sum_orbit_members <= |orbit| - 1`).
2. Replace stub-replay with real `binding_subproblem.solve` + `routing.precheck` on a sampled orbit image (sample size = √|orbit|).
3. Env-flag gated: `EXACT_BENDERS_SYMMETRY_ORBIT_CUT=1`. fail-closed if any sampled orbit image is FEASIBLE.
4. Phase 5-equivalent multi-anchor trial (8 anchors × 10 iter) on top of existing infrastructure.

## Hard constraints (compliance with task spec)

- No `src/` changes.
- No reads of `paradigm_search_review_v12_*` or `~/linwin_share/paradigm_search_review_v12_*`.
- Probe + README total ≈ 700 LOC (probe ~570, README ~130).
- Dry-run supported and exercised.
