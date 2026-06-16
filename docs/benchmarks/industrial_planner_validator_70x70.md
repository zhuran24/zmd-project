# IndustrialPlanner Validator Benchmark (70×70)

## Fixture
- Path: `data/examples/industrial_planner/benchmark.full70x70.blueprint.json`
- Base: `valley4_protocol_core`
- User devices: 3508
- Import compatible: yes
- Layout healthy: yes
- Clean export: yes
- Port warnings: 0
- Port mismatches: 0

## Command
```bash
python scripts/benchmark_industrial_planner_validator.py data/examples/industrial_planner/benchmark.full70x70.blueprint.json \
  --warmup 2 \
  --iterations 7 \
  --json-output data/examples/industrial_planner/benchmark.full70x70.benchmark.json \
  --markdown-output docs/benchmarks/industrial_planner_validator_70x70.md
```

## Environment
- Generated at (UTC): 2026-03-29T00:32:18.643701+00:00
- Python: CPython 3.13.5
- Platform: Linux-4.4.0-x86_64-with-glibc2.41
- Warmup iterations: 2
- Measured iterations: 7

## Results
| Metric | Seconds |
|---|---:|
| Min | 0.115455 |
| Mean | 0.124747 |
| Median | 0.122513 |
| P95 | 0.138501 |
| Max | 0.139601 |

## Conclusion
The reference run is comfortably within the 2-second class (mean 0.125s).

This benchmark is a deterministic synthetic 70×70 fixture meant to exercise import/layout-health validation at lot scale. It is not a throughput proof and does not simulate factory ticks.
