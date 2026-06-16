# Patch summary

This patch set is a fail-closed soundness hardening overlay for the Phase 1.2 spike package.

## Applied changes

1. F5 `pattern_nogood`: validates every certificate slot is in-range and unique for its group; rejects per-group literal counts exceeding demand.
2. F9 `density_envelope`: rejects `max_allowed_area < static_safe_ub` until a replayable tight-area proof is added; oracle no longer emits those nontrivial cuts.
3. F6 `shape_packing_hall`: validates per-side `region_demand` against `max(0, group_demand - opposite_capacity)`; generator applies the same guard to overrides.
4. F7 `power_hitting_set`: checks canonical `power_pole` dimensions are `2x2` in `state.canonical_rules`.
5. F8 `power_grid_reach`: checks canonical `power_pole` dimensions are `2x2` and `protocol_core` dimensions are `9x9`.
6. Tests: seven adversarial coverage tests added; existing F9 tests adjusted to the fail-closed quarantine behavior.

## Regression result

```text
Original v28: 418 passed in 4.97s
Patched overlay: 425 passed in 5.46s
```

## Notes

The F9 patch is intentionally conservative. It preserves soundness by suppressing nontrivial F9 cuts until the certificate schema includes enough proof data to validate a tight area cap. This is preferable to accepting an oracle-supplied scalar that can be forged into a false-positive cut.
