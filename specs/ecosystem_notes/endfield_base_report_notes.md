# endfield-base-planner report notes

Borrowed concepts:

- report/export boundary separated from core simulation
- JSON input/output discipline
- stable-state throughput, power, and logistics summaries
- optional viewer/editor split from core

Local interpretation:

- `src/adapters/base_planner/report_shapes.py` builds summary-only view models
- `src/render/report_builder.py` assembles a viewer-side sidecar JSON
