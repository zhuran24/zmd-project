# Provenance and Isolation Record

The benchmark facts were transcribed from the authoritative rule and preprocessing artifacts, then frozen as standalone constants in `scripts/cleanroom_strict/generate_bundle.py`. The external generator imports only the Python standard library and does not read production artifacts at generation time.

Internal source cross-checks used:

- `rules/canonical_rules.json` for the grid, objective, templates, commodities, routing, and power geometry;
- `data/preprocessed/mandatory_exact_instances.json` for required identifiers and facility types;
- `data/preprocessed/material_connection_skeleton.json` for the 17 operation groups and exact discrete terminal needs;
- `data/preprocessed/generic_io_requirements.json` for raw-source and final-sink counts.

The external bundle intentionally excludes repository paths, implementation vocabulary, absolute placement lists, candidate-domain counts, prior answers, and project version labels. Its SHA manifest covers every external file other than the manifest itself. The generator's token-aware leakage gate also requires external text to be ASCII English.

The benchmark is version-neutral with respect to the production solver. Its own `schema_version: 1` identifies only the exchange format.
