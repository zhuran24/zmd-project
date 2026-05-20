# IndustrialPlanner Full-Demand Fixture Planning Report

- Status: `proven_equivalent`
- Base id: `valley4_protocol_core`
- Selected base placeable size: 70
- Canonical grid size contract: 70×70
- Foundation bus edges: left, top
- Required manufacturing facilities: 219
- Required manufacturing area cells: 3325
- Required boundary output slots: 52
- Required boundary input slots: 2
- Validation probes used during planning: 78
- Selected top-edge input slots: 63, 66
- Selected output slots by edge:
  - top: 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 45, 48, 51, 54, 57, 60
  - left: 10, 13, 16, 19, 22, 25, 28, 31, 34, 37, 40, 43, 46, 49, 52, 55, 58, 61, 64, 67
  - bottom: 31, 34, 37, 40, 43, 46, 49, 52, 55, 58, 61, 64
  - right: 43, 46
- Final throughput status: `proven_equivalent`
- Final validator import-compatible: True
- Final validator layout-healthy: True

## Notes

- boundary slot selection is derived from the current generic I/O artifact plus exporter+validator feedback
- the deterministic manufacturing row packing is still the checked-in 70x70 full-demand slice
