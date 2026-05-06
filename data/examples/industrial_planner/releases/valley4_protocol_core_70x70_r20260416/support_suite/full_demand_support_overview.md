# IndustrialPlanner Full-Demand Support Overview

The current certified IndustrialPlanner support contract is intentionally narrowed to `valley4_protocol_core` (70×70) only. Other known bases are preserved as `future_scope` for later work and are excluded from the active audit / CI gate.

This overview regenerates the strict canonical base matrix and the companion deployment-path matrix together while keeping the active checked-in decision surface aligned to the single 70×70 `valley4_protocol_core` contract.

- Total bases audited: 1
- Audited bases: `valley4_protocol_core`
- Preserved future-scope bases (not audited here): 5
- Future-scope groups: valley4 40×40 sub-bases (3), wuling 50×50 aid base (1), wuling 80×80 protocol core (1)
- Proven-equivalent bases on the strict canonical path: 1
- Proven-equivalent bases on the best available active checked-in path: 1
- Additional bases unlocked by the active checked-in path: 0
- Bases whose active checked-in status changes across the two reports: 0
- Outer-path rows preserved as future-scope (not evaluated): 1
- Canonical-contract ceiling count, strict vs best available active path: 0 -> 0
- Manufacturing-area shortfall bases (unchanged upstream blocker): 0

## Companion reports

- `full_demand_base_support_matrix.json` / `full_demand_base_support_matrix.md` — strict 70×70 canonical-only matrix for the active contract.
- `full_demand_deployment_path_matrix.json` / `full_demand_deployment_path_matrix.md` — companion deployment matrix that preserves future-scope outer-path metadata without activating it by default.

## Decision signals

- The active checked-in support suite is intentionally narrowed to 1 audited base under the single 70×70 contract, while 5 preserved bases remain outside the active audit / CI surface.
- The strict canonical matrix records 1 active `proven_equivalent` base, and the best available active checked-in path records 1.
- No active checked-in status transitions remain after the out-of-scope outer deployment path is frozen as future_scope.
- The companion deployment column is currently preserved as `future_scope` for 1 audited base, so the active checked-in best-path view stays canonical-only.
- 0 active audited bases remain blocked by manufacturing-area shortfall before boundary representation is even considered.
- This umbrella workflow stays postprocess-only: it writes companion strict/deployment summaries together without widening canonical truth, campaign schema, or certified evidence.

## Active cross-view status table

| Base | Size | Relation | Canonical status | Outer path | Best path | Best status | Transition | Best blocker |
|---|---:|---|---|---|---|---|---|---|
| `valley4_protocol_core` | 70 | equal_to_canonical_contract | `proven_equivalent` | `future_scope` | `canonical_contract` | `proven_equivalent` | `unchanged` | - |
## Preserved future-scope inventory

| Group | Bases | Size(s) | Note |
|---|---|---|---|
| valley4 40×40 sub-bases | `valley4_infra_outpost`, `valley4_rebuilt_command`, `valley4_refugee_shelter` | 40 | These three 40×40 valley4 sub-bases share the same current contract status, so the active reports collapse them into one preserved future-scope group. |
| wuling 50×50 aid base | `wuling_tianwangping_aid` | 50 | Smaller wuling aid base retained as future-scope only. |
| wuling 80×80 protocol core | `wuling_protocol_core` | 80 | Larger wuling protocol-core outer-deployment work is frozen as future-scope. |

The detailed future-scope base inventory remains available in the JSON sidecar so dormant bases stay preserved without re-expanding the active Markdown decision surface.
