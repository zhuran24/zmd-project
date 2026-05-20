# Frontier Probe Strategy

This note documents the exact-safe probe workflow for the certified outer search.

## 1. Why probes exist

The certified frontier starts from the largest remaining rectangles.
When the mandatory footprint already leaves very little free area, those top-layer
frontier candidates are often overwhelmingly infeasible. A single medium-area
`CERTIFIED` result can prune a much larger portion of the potential domain than a
long sequence of top-layer `INFEASIBLE` proofs.

A probe is therefore a **scheduling-only** hint:

- it evaluates one legitimate candidate from the current potential domain;
- it never changes the exact objective;
- it never removes candidates without the same exact proof rules;
- it cannot promote exploratory evidence into certified proof.

## 2. Manual workflow

When you want a fast first `CERTIFIED` anchor before launching a long campaign,
run a short bounded search around the medium-area region and then resume the
main campaign.

Example:

```bash
python main.py \
  --mode certified_exact \
  --start-area 610 \
  --max-attempts 3 \
  --master-seconds 120 \
  --binding-seconds 120 \
  --routing-seconds 120 \
  --benders-max-iter 15 \
  --campaign-hours 1

python main.py \
  --mode certified_exact \
  --resume-campaign \
  --parallel-processes 4 \
  --campaign-hours 168
```

The first run tries only medium-area candidates. If it lands a `CERTIFIED`
result, the resumed campaign prunes all objectively worse-or-equal candidates
through the normal exact frontier logic.

## 3. Automatic mode

`main.py` now exposes:

```text
--frontier-probe-mode off|auto
```

Current behavior:

- `off` keeps the historical frontier-only schedule.
- `auto` inserts at most one non-frontier medium-area probe when:
  - the campaign has no certified result yet;
  - the potential domain is still large;
  - no previous probe has already been executed for the campaign.

If the last probe candidate stopped with `UNKNOWN` or `UNPROVEN`, resume keeps
that same candidate as the pending probe instead of inventing a new one.

## 4. Telemetry

Campaign telemetry now records:

- `selection_reason = probe_head | objective_head | prune_head | anchor_head | prune_fill`
- per-wave `probe_round_active`
- per-wave `probe_candidate_keys`
- per-wave and aggregate `probe_prune_gain_*`
- aggregate `probe_round_count`, `probe_candidate_count`, and `probe_resume_pending_count`

These fields are additive runtime diagnostics only. They do not alter the proof
contract.
