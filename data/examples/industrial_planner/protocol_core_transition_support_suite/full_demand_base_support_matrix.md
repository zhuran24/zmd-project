# IndustrialPlanner Full-Demand Base Support Matrix

- Total bases audited: 2
- Audited bases: `valley4_protocol_core`, `wuling_protocol_core`
- Proven-equivalent bases under the current contract: 1
- Infeasible bases: 0
- Unsupported-by-contract bases: 1
- Smaller / equal / larger than the canonical 70×70 contract: 0 / 1 / 1

## Decision signals

- 1 known base already reaches `proven_equivalent` under the current 70×70 canonical contract.
- `wuling_protocol_core` is currently the only known base blocked purely by the canonical 70×70 edge contract on this strict matrix; additive outer-deployment status is tracked separately in `full_demand_deployment_path_matrix`.

## Base matrix

| Base | Size | Relation | Planner status | Throughput | Import/Layout | Manufacturing headroom | Boundary slots (out/in) | Blocker |
|---|---:|---|---|---|---|---:|---:|---|
| `valley4_protocol_core` | 70 | equal_to_canonical_contract | `proven_equivalent` | `proven_equivalent` | True/True | 1575 | 52/2 | - |
| `wuling_protocol_core` | 80 | larger_than_canonical_contract | `unsupported_by_canonical_contract` | `-` | - | 3075 | 52/2 | canonical_contract_ceiling |

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

### `wuling_protocol_core`

- Planner status: `unsupported_by_canonical_contract`
- Placeable size: 80
- Size relation: larger_than_canonical_contract
- Foundation bus edges: (none)
- Manufacturing headroom cells: 3075 (required 3325, lot 6400)
- Required boundary slots: outputs 52, inputs 2
- Blocking classification: `canonical_contract_ceiling`
- Error: selected base 'wuling_protocol_core' uses placeableSize=80, but the canonical blueprint contract is capped at 70×70; the planner refuses to fake boundary ports away from the true lot edge
- Notes:
  - this is an adapter-side fixture planner only; it does not widen the canonical blueprint schema
