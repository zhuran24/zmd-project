# zmd witness preflight delivery v10

This package replaces the ineffective v8 ghost-anchor slicing path with a witness-only preflight reducer for the v9 bottleneck.

Core result: v9 evidence shows the hard part is no longer ghost anchor selection. After a single anchor slice, mandatory placement still has 3,853,132 pose literals. v10 therefore collapses mandatory placement only when a complete mandatory witness hint is available, by solving a cloned CP-SAT model with mandatory x/y/mode equalities plus one compatible ghost anchor.

Safety contract:

- FEASIBLE or OPTIMAL forced clone plus successful solution extraction is accepted as a normal master FEASIBLE incumbent.
- INFEASIBLE, UNKNOWN, timeout, incomplete hint, or extraction failure never proves the parent candidate infeasible.
- The controller falls back to the normal master solve with the remaining original master budget.
- If the preflight uses the whole master budget without a witness, the parent result is UNKNOWN, not INFEASIBLE.

Recommended env:

```bash
EXACT_COMMUNITY_BLUEPRINT_HINT_PATH=data/hints/blueprint_2026_05_13_master_hint.json \
EXACT_MASTER_WITNESS_PREFLIGHT=1 \
EXACT_MASTER_WITNESS_PREFLIGHT_SECONDS=30 \
EXACT_MASTER_WITNESS_PREFLIGHT_MAX_ANCHORS=32 \
python -m src.search.outer_search ...
```

Files:

- `code.tar.xz`: full modified source tree, without virtualenv/cache files.
- `patches/zmd_witness_preflight_v10.patch`: patch against zmd_code_v9.
- `validation/validation.log`: compile, ruff, targeted pytest results.
- `checksums/`: inner source and archive SHA256 manifests.
