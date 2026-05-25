"""Spike prod-scale runner helpers.

Per ``docs/research/prod_scale_spike_design_20260525/MERGER.md`` §5 shrink scope.
All modules under this package are spike-only, sandboxed under
``data/cuts/spike/`` output dir, and must not touch off-limits paths
(see :mod:`off_limits_check`).

Phase A scope (this branch):
- A1: branch setup + off-limits enforce
- A2: 50 inst failfast probe (G17 ≤ 15s)
- A3: real-oracle real-emit fixture (≥45 cert across 9 family)

Phase B (separate agent): toy translator + scale ramp + feasible smoke +
filter mock + telemetry + verdict.
"""
