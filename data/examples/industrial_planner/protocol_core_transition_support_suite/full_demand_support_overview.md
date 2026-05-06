# IndustrialPlanner Full-Demand Support Overview

This overview is an umbrella decision-support report. It regenerates the strict canonical 70×70 support matrix and the additive deployment-path matrix together, then highlights the cross-view status deltas without widening canonical truth or certified evidence.

- Total bases audited: 2
- Audited bases: `valley4_protocol_core`, `wuling_protocol_core`
- Proven-equivalent bases on the strict canonical path: 1
- Proven-equivalent bases on the best available checked-in path: 2
- Additional bases unlocked by the adapter-side outer path: 1
- Bases whose checked-in status changes across the two reports: 1
- Canonical-contract ceiling count, strict vs best available: 1 -> 0
- Manufacturing-area shortfall bases (unchanged upstream blocker): 0

## Companion reports

- `full_demand_base_support_matrix.json` / `full_demand_base_support_matrix.md` — strict 70×70 canonical-only matrix.
- `full_demand_deployment_path_matrix.json` / `full_demand_deployment_path_matrix.md` — additive best-available matrix after the outer path is considered.

## Decision signals

- The strict canonical matrix still records 1 `proven_equivalent` base, while the best available checked-in path records 2.
- Current checked-in status transitions: `wuling_protocol_core` (unsupported_by_canonical_contract -> proven_equivalent via `outer_deployment`).
- The additive outer path currently unlocks 1 additional base without changing the upstream manufacturing-area shortfall on 0 bases.
- This umbrella workflow stays postprocess-only: it writes companion reports for the strict canonical and additive deployment views together, but it does not widen canonical truth, campaign schema, or certified evidence.

## Cross-view status table

| Base | Size | Relation | Canonical status | Outer path | Best path | Best status | Transition | Best blocker |
|---|---:|---|---|---|---|---|---|---|
| `valley4_protocol_core` | 70 | equal_to_canonical_contract | `proven_equivalent` | `proven_equivalent` | `canonical_contract` | `proven_equivalent` | `unchanged` | - |
| `wuling_protocol_core` | 80 | larger_than_canonical_contract | `unsupported_by_canonical_contract` | `proven_equivalent` | `outer_deployment` | `proven_equivalent` | `unsupported_by_canonical_contract -> proven_equivalent` | - |

## Status transitions

### `wuling_protocol_core`

- Canonical status: `unsupported_by_canonical_contract`
- Outer path status: `proven_equivalent`
- Best available path: `outer_deployment`
- Transition: `unsupported_by_canonical_contract -> proven_equivalent`
- Best available throughput: `proven_equivalent`
- Best available validator import/layout: True/True
- Outer-path unlock: yes
