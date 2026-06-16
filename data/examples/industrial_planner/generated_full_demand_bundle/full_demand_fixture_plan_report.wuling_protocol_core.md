# IndustrialPlanner Full-Demand Fixture Planning Report

- Status: `unsupported_by_canonical_contract`
- Base id: `wuling_protocol_core`
- Selected base placeable size: 80
- Canonical grid size contract: 70×70
- Foundation bus edges: (none)
- Required manufacturing facilities: 219
- Required manufacturing area cells: 3325
- Required boundary output slots: 52
- Required boundary input slots: 2
- Validation probes used during planning: 0

## Error

selected base 'wuling_protocol_core' uses placeableSize=80, but the canonical blueprint contract is capped at 70×70; the planner refuses to fake boundary ports away from the true lot edge

## Notes

- this is an adapter-side fixture planner only; it does not widen the canonical blueprint schema
