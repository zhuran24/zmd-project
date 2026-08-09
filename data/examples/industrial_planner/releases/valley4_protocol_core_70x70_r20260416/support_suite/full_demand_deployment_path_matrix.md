# IndustrialPlanner Full-Demand Deployment Path Matrix

The current certified IndustrialPlanner support contract is intentionally narrowed to `valley4_protocol_core` (70×70) only. Other known bases are preserved as `future_scope` for later work and are excluded from the active audit / CI gate.

- Audited base count: 1
- Audited bases: `valley4_protocol_core`
- Preserved future-scope bases (not audited here): 5
- Future-scope groups: valley4 40×40 sub-bases (3), wuling 50×50 aid base (1), wuling 80×80 protocol core (1)
- Proven-equivalent bases under the strict 70×70 canonical contract: 1
- Additional bases unlocked by the adapter-side outer deployment path: 0
- Outer-path rows preserved as future-scope (not evaluated): 1
- Proven-equivalent bases under any active checked-in path: 1
- Smaller / equal / larger than the canonical 70×70 contract: 0 / 1 / 0

## Decision signals

- 1 audited base now reach `proven_equivalent` under active checked-in paths: 1 on the strict 70×70 canonical contract and 0 additional bases via evaluated outer deployment.
- The companion outer-path column is currently preserved as `future_scope` for 1 audited base; active checked-in status therefore stays canonical-only.
- 0 audited bases remain blocked by manufacturing-area shortfall before boundary representation is even considered.
- This deployment-path report stays postprocess-only: it preserves the companion outer-path column without widening canonical truth, campaign schema, or certified evidence.

## Active base matrix

| Base | Size | Relation | Canonical path | Outer path | Best path | Best throughput | Best import/layout | Best blocker |
|---|---:|---|---|---|---|---|---|---|
| `valley4_protocol_core` | 70 | equal_to_canonical_contract | `proven_equivalent` | `future_scope` | `canonical_contract` | `proven_equivalent` | True/True | - |

## Per-base details

### `valley4_protocol_core`

- Placeable size: 70
- Size relation: equal_to_canonical_contract
- Foundation bus edges: left, top
- Manufacturing headroom cells: 1575 (required 3325, lot 4900)
- Required boundary slots: outputs 52, inputs 2
- Best available path: `canonical_contract`
- Best available status: `proven_equivalent`
- Best available throughput: `proven_equivalent`
- Best available validator import/layout: True/True

#### Canonical 70×70 contract path

- Planner status: `proven_equivalent`
- Throughput status: `proven_equivalent`
- Validator import/layout: True/True
- Notes:
  - boundary slot selection is derived from the current generic I/O artifact plus exporter+validator feedback
  - the deterministic manufacturing row packing is still the checked-in 70x70 full-demand slice

#### Companion outer-path column

- Path status: `future_scope`
- Applicability reason: `outer_deployment_deactivated_from_active_contract`
- Notes:
  - outer deployment is preserved as future_scope and excluded from the active single-base contract / CI gate

## Preserved future-scope inventory

| Group | Bases | Size(s) | Note |
|---|---|---|---|
| valley4 40×40 sub-bases | `valley4_infra_outpost`, `valley4_rebuilt_command`, `valley4_refugee_shelter` | 40 | These three 40×40 valley4 sub-bases share the same current contract status, so the active reports collapse them into one preserved future-scope group. |
| wuling 50×50 aid base | `wuling_tianwangping_aid` | 50 | Smaller wuling aid base retained as future-scope only. |
| wuling 80×80 protocol core | `wuling_protocol_core` | 80 | Larger wuling protocol-core outer-deployment work is frozen as future-scope. |

The detailed future-scope base inventory remains available in the JSON sidecar so dormant bases stay preserved without re-expanding the active Markdown decision surface.
