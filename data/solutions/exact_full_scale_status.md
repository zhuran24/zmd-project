# Exact Full-Scale Status

- Status: `open`
- Note: The full-scale 70×70 exact `CERTIFIED` end-state is still an open item. Current checked-in solver evidence does not yet satisfy the full terminal evidence bundle contract. missing artifact `/mnt/data/workrepo/data/checkpoints/exact_campaign_state.json`; campaign state unavailable; campaign state unavailable; +12 more blocker(s)
- Campaign state: `data/checkpoints/exact_campaign_state.json`
- Campaign telemetry: `data/checkpoints/exact_campaign_telemetry.json`
- Delivery manifest: `data/solutions/certified_delivery_manifest.json`
- Final solution: `data/solutions/final_solution.json`
- Optimal blueprint: `data/blueprints/optimal_blueprint.json`
- Campaign final status: ``
- Last stop reason: ``
- Best certified ghost rect: `(none)`
- Resume compatible with current hashes: `False`
- Proof-summary schema version: ``

## Required evidence checks

| Check | Status | Detail |
|---|---|---|
| `campaign_state_present` | `fail` | missing artifact `/mnt/data/workrepo/data/checkpoints/exact_campaign_state.json` |
| `campaign_solve_mode_certified_exact` | `skipped` | campaign state unavailable |
| `campaign_artifact_hashes_match_current` | `skipped` | campaign state unavailable |
| `campaign_final_status_certified` | `skipped` | campaign state unavailable |
| `campaign_terminal_stop_reason_search_exhausted` | `skipped` | campaign state unavailable |
| `campaign_final_result_present` | `skipped` | campaign state unavailable |
| `campaign_telemetry_present` | `fail` | missing artifact `/mnt/data/workrepo/data/checkpoints/exact_campaign_telemetry.json` |
| `campaign_telemetry_solve_mode_certified_exact` | `skipped` | campaign telemetry unavailable |
| `campaign_telemetry_references_campaign_state` | `skipped` | campaign telemetry unavailable |
| `final_solution_present` | `fail` | missing artifact `/mnt/data/workrepo/data/solutions/final_solution.json` |
| `final_solution_matches_campaign_final_result` | `skipped` | final solution unavailable |
| `optimal_blueprint_present` | `fail` | missing artifact `/mnt/data/workrepo/data/blueprints/optimal_blueprint.json` |
| `optimal_blueprint_matches_campaign_final_result` | `skipped` | optimal blueprint unavailable |
| `delivery_manifest_present` | `fail` | missing artifact `/mnt/data/workrepo/data/solutions/certified_delivery_manifest.json` |
| `delivery_manifest_matches_campaign_final_result` | `skipped` | delivery manifest unavailable |

## Current exact source-of-truth hashes

| Artifact | SHA256 |
|---|---|
| `candidate_placements` | `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f` |
| `canonical_rules` | `8ac667a1bce67ff9084701d18892f370e19d68cc9b5ace44bd63c68b20d3d6ea` |
| `generic_io_requirements` | `ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e` |
| `mandatory_exact_instances` | `545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6` |
