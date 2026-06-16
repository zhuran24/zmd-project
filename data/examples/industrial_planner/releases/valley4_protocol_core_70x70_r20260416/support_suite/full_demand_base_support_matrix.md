# IndustrialPlanner Full-Demand Base Support Matrix

The current certified IndustrialPlanner support contract is intentionally narrowed to `valley4_protocol_core` (70×70) only. Other known bases are preserved as `future_scope` for later work and are excluded from the active audit / CI gate.

- Audited base count: 1
- Audited bases: `valley4_protocol_core`
- Preserved future-scope bases (not audited here): 5
- Future-scope groups: valley4 40×40 sub-bases (3), wuling 50×50 aid base (1), wuling 80×80 protocol core (1)
- Proven-equivalent bases under the current contract: 1
- Infeasible bases: 0
- Unsupported-by-contract bases: 0
- Smaller / equal / larger than the canonical 70×70 contract: 0 / 1 / 0

## Decision signals

- 1 audited base already reach `proven_equivalent` under the current 70×70 canonical contract.
- The checked-in matrix is intentionally narrowed to the active 70×70 single-base contract; preserved future-scope bases are recorded separately below instead of expanding the active audit surface.

## Active base matrix

| Base | Size | Relation | Planner status | Throughput | Import/Layout | Manufacturing headroom | Boundary slots (out/in) | Blocker |
|---|---:|---|---|---|---|---:|---:|---|
| `valley4_protocol_core` | 70 | equal_to_canonical_contract | `proven_equivalent` | `proven_equivalent` | True/True | 1575 | 52/2 | - |

## Per-base details

### `valley4_protocol_core`

- Planner status: `proven_equivalent`
- Placeable size: 70
- Size relation: equal_to_canonical_contract
- Foundation bus edges: left, top
- Manufacturing headroom cells: 1575 (required 3325, lot 4900)
- Required boundary slots: outputs 52, inputs 2
- Selected input slots: 63, 66
- Selected output edge counts: top=18, left=20, bottom=12, right=2
- Final throughput status: `proven_equivalent`
- Final validator import/layout: True/True
- Notes:
  - boundary slot selection is derived from the current generic I/O artifact plus exporter+validator feedback
  - the deterministic manufacturing row packing is still the checked-in 70x70 full-demand slice

## Preserved future-scope inventory

| Group | Bases | Size(s) | Note |
|---|---|---|---|
| valley4 40×40 sub-bases | `valley4_infra_outpost`, `valley4_rebuilt_command`, `valley4_refugee_shelter` | 40 | These three 40×40 valley4 sub-bases share the same current contract status, so the active reports collapse them into one preserved future-scope group. |
| wuling 50×50 aid base | `wuling_tianwangping_aid` | 50 | Smaller wuling aid base retained as future-scope only. |
| wuling 80×80 protocol core | `wuling_protocol_core` | 80 | Larger wuling protocol-core outer-deployment work is frozen as future-scope. |

The detailed future-scope base inventory remains available in the JSON sidecar so dormant bases stay preserved without re-expanding the active Markdown decision surface.
