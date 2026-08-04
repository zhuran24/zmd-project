# Pricing-bound experiment deliverable

This directory is research-only. It does not write to a proof registry or claim a formal certificate.

## Validate

```bash
PY=/path/to/python3.13
$PY -m pytest -q test_deliverable.py
$PY make_tables.py
```

The scripts require OR-Tools 9.15.6755. The uploaded offline wheelhouse contains the compatible packages.

## Run one pricing branch

```bash
$PY pricing_probe.py \
  --bundle ../pricing_exp/11_runnable \
  --duals duals.json \
  --dual D1_SCARCITY_PRICES \
  --family CLEAN \
  --seconds 60 \
  --workers 4 \
  --max-poles none \
  --out one_run.json
```

Add `--hole` for the fixed hole branch, `--relaxed` for the legal no-connectivity packing relaxation, or `--loose` for the supplied multi-root connectivity semantics. Use `--cap-scaled N` to write a previously proved branch cap into the model.

## Run the 24-core staged protocol

```bash
$PY run_protocol.py \
  --out-root ./pricing_protocol_out \
  --python "$PY" \
  --bundle ../pricing_exp/11_runnable \
  --max-parallel 5 \
  --workers 4 \
  --hard-wall-seconds 1200

$PY analyze_protocol.py ./pricing_protocol_out/manifest.json \
  --out ./pricing_protocol_out/decision.json
```

The decision JSON reports both the no-fixed-pole-cap Lagrangian hybrid and a separately labeled supplied-`MAX_POLES_PER_REGION=3` exactly-one-hole branch bound. The bundled 129/85 hole bounds are used only in the latter scope.

A command-only preview is available with `--dry-run`.

## Core files

- `pricing_bound_decision_report.md`: mathematical derivation, thresholds, experiment design, risks, and fallback bounds.
- `pricing_probe.py`: bucket-weighted pricing harness with fixed hole branches and event-driven bound trajectories.
- `duals.json`: three complete synthetic dual vectors.
- `lagrangian_accounting.py`: exact rational bookkeeping.
- `run_protocol.py` and `analyze_protocol.py`: staged runner and numeric decision gates.
- `generated_tables.md/json`: recomputed anchor and threshold tables.
- `pilot_*.json`: local harness-validation runs. These are not target-machine GO/NO-GO evidence.
