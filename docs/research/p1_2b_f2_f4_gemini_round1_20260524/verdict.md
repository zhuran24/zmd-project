# F2/F4 Gemini Round 1 verdict (2026-05-24)

Round 1 cross-check on commit `92224c4`. Per [[gemini-review-algorithm-math]] v4
protocol: prompt 含真数据 paths + armor strict + 反 GO ritual.

## Gemini verdict: CONCERN (borderline NOT_GO)

3 finding total (BLOCKER 1 + HIGH 1 + LOW 1) + 3 disproved hypothesis (legit
sanity arguments, not vague).

## Findings

### BLOCKER #1 — Dinic DFS recursion limit (FIXED this round)

`_dfs_blocking_flow` was recursive. On 70x70 grid serpentine layouts the level
graph depth can exceed Python's default `sys.getrecursionlimit() = 1000`,
raising `RecursionError`. The oracle's broad `except Exception` swallows it
silently — false negative (cut not emitted) instead of crash.

Reproducer (2026-05-24 verified):
- 1-cell-wide serpentine corridor through 70x70, 2485 free cells
- src=(0,0), sink=(69,69)
- Recursive version: `RecursionError: maximum recursion depth exceeded`
- Iterative version: `max_flow=1` correctly

Fix: `src/cuts/helpers/dinic_node_split.py:222-282` rewritten as iterative DFS
using explicit stack of `(node, pushed_budget)` frames + `path_edges` for
unwinding on sink-reached. Behavior matches recursive version (same edge
iteration order, same dead-end advance of parent's `iter_ptr`).

Regression test: `src/tests/cuts/test_helpers_dinic_node_split.py` (7 new
tests, including the serpentine reproducer).

### HIGH #2 — F2 schema cannot express Phase 1.5+ cell-capacity bottleneck (Phase 1.5+ defer, NOT this round)

When `cell_capacity` becomes finite (Phase 1.5+ true node-split mode), Dinic
may cut internal `v_in→v_out` edges. The generator's cross-partition recompute
(`_cross_partition_edges`) only counts adjacency edges between distinct cells,
so `frozenset(result.cut_cell_edges) != recomputed_edges` will always fail and
the cut gets dropped fail-closed.

Decision: defer to Phase 1.5+. The F2 cert schema is edge-only by design
(spec 02_cutset.md §1, `cut(A, B) = #{e ∈ E : e crosses}`). Cell-capacity
support would require a schema extension (mixed edge/vertex cut). Already
listed in `project_phase_1_2_progress.md` Phase 1.5+ defer.

### LOW #3 — bitset padding formula inconsistency (FIXED this round)

Generator encoded with `(grid_size² + 7) // 8`; validator decoded with
`grid_size² // 8 + 1`. At 70 (4900 bits) both equal 613, so the bug is
latent — but breaks for grid sizes that are exact multiples of 8.

Fix: `src/cuts/families/cutset.py:65` unified to encoder formula.

## Spec-data gaps (CONFIRMED, both Phase 1.5+ defer)

- **Gap A** (float demand): `commodity_demands.json` real data has
  `buckwheat: 5.5`, `oxalic_acid_solution: 0.55`. BState typed as
  `Dict[str, int]`. F2 generator strict-int gate skips float demands silently;
  F2 validator's `_parse_strict_int` would crash on float. Fix at preprocess
  layer (scale or ceil) when wiring real `commodity_routes` in Phase 1.5+.
- **Gap B** (`commodity_routes` never populated in prod): grep confirms only
  `cuts/` reads this field; no `src/preprocess/`, `src/search/benders_loop.py`,
  or `src/models/` site sets it. Phase 1.5+ wiring task.

## Sanity arguments Gemini disproved (legit, not vague ritual)

1. F2 `_has_patch_escape` is *not* dead — Phase 1.2 patch == free_cells so it
   trivially returns False, but enclosure check is meaningful when PCR-CUT
   feeds a strict subset patch in Phase 1.5+.
2. F4 `extract_frontier_separator` correctly excludes `exterior_blocks` per
   spec 04_component_reach.md §7 (separator ∈ cell_owner ∪ ghost_cells).
3. Bidirectional cell adjacency edges use `seen_pairs` dedup + two explicit
   directed edges — no residual double-count.

## Gate state (post-fix)

- pytest cuts: **361 passed** (+7 new dinic regression tests; 354→361)
- pytest cuts -O: 361 passed
- ruff: clean
- mypy --strict --explicit-package-bases src/cuts/: 28 source files, 0 errors
- bandit: clean
- radon: Average A (4.677)
- vulture: 1 known finding (Protocol method param `deadline_seconds` —
  preexisting from F5 land, not introduced this round)
- exit_criteria: 3 PASS / 8 PENDING_PHASE_1 / 0 FAIL

## Round 2 plan

Per v3 protocol (循环 until GO/minor only):
- Round 2 prompt 必须告诉 Gemini round 1 BLOCKER + LOW 修复细节, 让它 verify
- Round 2 重点: 验 iterative DFS 是否引入新 bug (off-by-one / dead-end backtrack
  错过 path / iter_ptr advance 漏掉合法 edge); 验 bitset padding fix 不破坏现有
  test
- 若 round 2 真 only minor / GO_WITH_MINOR → close F2/F4 cross-check 进 F6
