## Round 3 Verdict
NOT_GO

## R2 fix verification (Finding #1/#2/#3 + Gap E)
- Finding #1 fix (_can_jump_via_cells cell-to-cell min): LANDED — `src/cuts/helpers/power_network.py:64` (`_closest_cell_pair` correctly computes min cell-to-cell distance).
- Finding #2 fix (cell-center segment endpoints): LANDED — `src/cuts/helpers/power_network.py:84` (uses `c[0] + 0.5` for segment endpoints).
- Finding #3 fix (pole_set -= pc_set 方向): LANDED — `src/cuts/helpers/power_network.py:175` (matches documented intent, acts as invariant guard).
- Finding #4 rejection (facility_pools schema): ACCEPTED — Verified `data/preprocessed/candidate_placements.json` schema uses `facility_pools`.
- R2-Gap E (anchor-distance early reject): LANDED — `src/cuts/helpers/power_network.py:101` (mathematically sound upper bound `R + 2√2`, safely rejects ~99% pairs).

## R3 NEW Gap H/I/J
- R3-Gap H (early-reject bound tightness): REJECTED — The bound is loose but 100% sound (never over-rejects). Tightening it would require complex directional math that negates the hot-path speedup.
- R3-Gap I (closest-pair segment ambiguity): CONFIRMED — `_can_jump_via_cells` only checks the single closest pair for ghost intersection. If blocked, it drops the edge even if another pair within `pole_radius` has unblocked line-of-sight (CRITICAL False Positive).
- R3-Gap J (full vs ghost-only path overlap): REJECTED — `ghost_only_free` intentionally excludes `cell_owner` to simulate their removal. If the graph reconnects, `cell_owner` was the true cause, which correctly invalidates the single-cause ghost cert.

## Round 3 New findings (≥3, 任何 severity, R1+R2 没 catch 的)

### Finding 1: [CRITICAL] src/cuts/helpers/power_network.py:83 — `_can_jump_via_cells` drops valid edges by only checking one closest pair
When determining if power can jump, `_closest_cell_pair` returns a single pair. If this pair's segment is blocked by the ghost, `_can_jump_via_cells` returns `False`. However, if multiple cell pairs between the footprints are within `pole_radius`, power can physically jump if *any* of them has an unblocked line-of-sight. Restricting the check to an arbitrarily chosen closest pair falsely drops legitimate edges, leading to false disconnects and unsound cuts.

### Finding 2: [CRITICAL] src/cuts/families/power_grid_reach.py:150 — Validator blindly trusts `pole_jump_radius` and `protocol_core_cell` from cert
The validator reads `pole_jump_radius` and `protocol_core_cell` directly from the unverified cert payload and uses them to rebuild the power graph. It never validates these values against `canonical_rules` or `state`. A malicious prover can forge a cert with `pole_jump_radius = 0.001` or a bogus `protocol_core_cell` (e.g., `[69, 69]`) to artificially guarantee a BFS disconnect, causing the validator to accept an invalid cut that bans legitimate placements.

### Finding 3: [HIGH] src/cuts/oracles/power_grid_reach_oracle.py:236 — Generator omits `active_assumptions` from `CutScope`
The spec §4 explicitly requires `active_assumptions` for `power_pole_radius` and `protocol_core_position` to bind these parameters to the cut's scope. However, `_build_cut` completely omits `active_assumptions` when constructing the `CutScope`. This breaks the audit trail and prevents the cut store from invalidating the cut if the canonical rules or protocol core position change in future states.

## Sanity (GO verdict 必 ≥3 disproved hypothesis 含 file:line)
1. **Watcher is too narrow (False Positive on cell_owner removal)**: Disproved. `_validate_ghost_only_disconnect` (`src/cuts/families/power_grid_reach.py:330`) ensures the disconnect holds on the `ghost_only_free` mask (which assumes ALL `cell_owner` facilities are removed). Thus, the disconnect is invariant to `cell_owner` removals, making the O(1) evaluator and tight watcher 100% sound.
2. **`pole_set -= pc_set` is a dead defense**: Disproved. While `free_cells` already excludes `pc_cells` making it a no-op in practice, it acts as a harmless and correct invariant guard matching the API contract (`src/cuts/helpers/power_network.py:175`).
3. **Evaluator placement check fails on rotation**: Disproved. If a facility is rotated, its `pose_id` changes. The cut was generated for a specific `pose_id`. The evaluator correctly returns `False` if the facility is no longer at that exact pose (`src/cuts/families/power_grid_reach.py:423`).

## 建议 Round 4 重点 / Phase 1.5+ defer / 终结 (close at this round)
- **Round 4 必须修**: 
  1. `_can_jump_via_cells` 必须遍历所有 `dist <= pole_radius` 的 cell pair，只要有一个 segment 不跟 ghost 相交就返回 `True` (修复 Finding 1)。
  2. Validator 必须从 source-of-truth (或通过严格的 `active_assumptions` 校验) 获取 `pole_jump_radius` 和 `protocol_core_cell`，不能盲信 cert payload (修复 Finding 2)。
  3. Generator 必须在 `CutScope` 中补齐 `active_assumptions` (修复 Finding 3)。
- **Phase 1.5+ defer**: 多原因 (cell_owner + ghost 共同导致) 的 disconnect cut 生成与验证。