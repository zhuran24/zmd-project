# IndustrialPlanner Single-Base Delivery Release

Current release scope is intentionally limited to the active IndustrialPlanner contract `valley4_protocol_core` (70×70). Other bases and the outer-deployment path remain preserved as `future_scope` and are not widened by this release builder.

- Release id: `valley4_protocol_core_70x70_r20260415`
- Base id: `valley4_protocol_core`
- Lot size: `70`
- Delivery status: `ready_for_single_base_delivery`
- Release dir: `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415`
- Source run dir: `.artifacts/industrial_planner_single_base_e2e`
- Manifest generated at: `2026-04-15T23:41:26Z`
- Full-scale exact `CERTIFIED` status: `open`
- Exact-status note: The full-scale 70×70 exact `CERTIFIED` end-state is still an open item. This workflow validates the current single-base delivery bundle and checked-in support surfaces only; it does not claim that the full exact terminal proof artifact has already been checked in.

## Delivery entrypoints

- Blueprint: `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/bundle/industrial_planner.blueprint.json`
- Compatibility manifest: `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/bundle/industrial_planner.compatibility_manifest.json`
- Validation report: `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/bundle/validation_report.json`
- Throughput report: `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/bundle/throughput_report.json`
- Source run summary: `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/run_summary.json`

## Source run gate summary

| Gate | Status |
|---|---|
| overall_status | `success` |
| deliverable_status | `ready_for_single_base_delivery` |
| planning | `proven_equivalent` |
| export | `written` |
| validator | `validator_acceptable_with_warnings` |
| throughput | `proven_equivalent` |
| fresh support reports | `written` |
| checked-in support inventory | `clean` |
| checked-artifact gate | `clean` |

## Reproducibility commands

```bash
python scripts/run_industrial_planner_single_base_e2e.py --run-dir .artifacts/industrial_planner_single_base_e2e
python scripts/build_industrial_planner_single_base_delivery_release.py --source-run-dir .artifacts/industrial_planner_single_base_e2e --release-root data/examples/industrial_planner/releases --release-id valley4_protocol_core_70x70_r20260415 --pointer-json data/examples/industrial_planner/active_single_base_delivery_release.json --pointer-markdown data/examples/industrial_planner/active_single_base_delivery_release.md --index-json data/examples/industrial_planner/releases/release_index.json --index-markdown data/examples/industrial_planner/releases/release_index.md
```

## Payload artifacts

| Artifact | Required | Stage | Path | SHA256 |
|---|---|---|---|---|
| `canonical_fixture` | yes | `planning` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/canonical/full_demand_recipe_capacity_canonical_blueprint.json` | `71bcd38f28f88c29a72b56aef5e6aee280d11c120645fd5b00a21e1bb4384efa` |
| `fixture_plan_report_json` | yes | `planning` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/canonical/full_demand_fixture_plan_report.json` | `1ef82a48be8ff76a1a431f913ca0f2856d9b628c6f00b3ab2c59af4187519da6` |
| `fixture_plan_report_markdown` | yes | `planning` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/canonical/full_demand_fixture_plan_report.md` | `85b64215ed83e8c64766bf5fc90030913d7727fa7744903f0bfd33046468f321` |
| `industrial_planner_blueprint` | yes | `export` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/bundle/industrial_planner.blueprint.json` | `ecf5b2c9c5dd586f57084dfeaa03661a7a57811b15c8f95535026f860aebaa5c` |
| `industrial_planner_compatibility_manifest` | yes | `export` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/bundle/industrial_planner.compatibility_manifest.json` | `fd54feba3348b7972ee440c3bdee4771846e0e9c1eb52d25c83165e8607dcc48` |
| `validation_report_json` | yes | `validator` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/bundle/validation_report.json` | `9a57bb6f3ee3a47ddce75e992b7d49dc8c332542e12727df948994d5a0f01592` |
| `validation_report_markdown` | yes | `validator` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/bundle/validation_report.md` | `f3415ff97dcf013ba1d754af14195503cd49a11d1fc5b6f9f59c3d4360060369` |
| `throughput_report_json` | yes | `throughput` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/bundle/throughput_report.json` | `5fc38fa1e7585741bc437b95dddb3a32ec9cf5e18dc52137527b2e21a0614fdc` |
| `throughput_report_markdown` | yes | `throughput` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/bundle/throughput_report.md` | `4430a7abf19d0719935518d87eba050741dcfffc9a3c186f8ee9856638a3660f` |
| `fresh_support_canonical_matrix_json` | yes | `support_reports` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/support_suite/full_demand_base_support_matrix.json` | `29901a590a67c51ef91ebf4a97dc3b3dc0f51b77772b377d9faca5cc9c4226a0` |
| `fresh_support_canonical_matrix_markdown` | yes | `support_reports` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/support_suite/full_demand_base_support_matrix.md` | `50e63b04e17ee39ad2c3bc1a0e67c86972ee96074f52b2d5ee235d7147cba2a6` |
| `fresh_support_deployment_matrix_json` | yes | `support_reports` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/support_suite/full_demand_deployment_path_matrix.json` | `cdc6d3bb5ef0fa80e2b786c3bb724dcef2f151adf4f25571adb587b1b085fc33` |
| `fresh_support_deployment_matrix_markdown` | yes | `support_reports` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/support_suite/full_demand_deployment_path_matrix.md` | `8224f4eba3b35348cd4b38037881b61b3c2fcc6428944cb04a3f6bca64fe8b26` |
| `fresh_support_overview_json` | yes | `support_reports` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/support_suite/full_demand_support_overview.json` | `c9dc0fc8d7165adadd560049317fed7a70da61eef0ddb804891d06db248e07fb` |
| `fresh_support_overview_markdown` | yes | `support_reports` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/support_suite/full_demand_support_overview.md` | `9eb0c4f3fe66ad73007fbf5d367d11fc6ce6fe451264e93aa486c28f487a6d1e` |
| `support_suite_inventory_summary_json` | yes | `checked_in_support_suite` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/checks/support_suite_inventory_summary.json` | `388d397ffa683d435ef001ae139405935d6b92496b74bc2926c7beec0ba48611` |
| `support_suite_inventory_summary_markdown` | yes | `checked_in_support_suite` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/checks/support_suite_inventory_summary.md` | `6210434611e69185394754cdde8a13a98be9893a9c1c3173f8124f1dd1b5e340` |
| `support_suite_inventory_summary_console` | no | `checked_in_support_suite` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/checks/support_suite_inventory_summary.txt` | `c2f23c91b7a0a3d3769e6fc20d9c5a5b84f392c5ceb919314b5756daaa7da7b6` |
| `checked_artifact_suite_summary_json` | yes | `checked_artifact_gate` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/checks/checked_artifact_suite_summary.json` | `bb49b8f9a84190d1fcc8ef18ee99966eb69d4e4d3500200c359f5aed38be54c1` |
| `checked_artifact_suite_summary_markdown` | yes | `checked_artifact_gate` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/checks/checked_artifact_suite_summary.md` | `e8c5a10c24ed29c86f7f92a1936c8cef4475ea4480a001d5b55b0dcb14d11ac0` |
| `checked_artifact_suite_summary_console` | no | `checked_artifact_gate` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/checks/checked_artifact_suite_summary.txt` | `ae5df713a37396c9a44f64349172e9b10c23d181be64c6a1e09edd68385c04a9` |
| `run_summary_json` | yes | `run_summary` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/run_summary.json` | `1ce24466384ee1d9b242a20cdfbb1ceda9a7d8e8e55f34a0f3f9bae3e75c48c1` |
| `run_summary_markdown` | yes | `run_summary` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/run_summary.md` | `32f9c2c132c006cfd9031b39189af171f194b0c43a9ce41b8d3944a5cbc9947b` |
| `run_summary_console` | no | `run_summary` | `data/examples/industrial_planner/releases/valley4_protocol_core_70x70_r20260415/run_summary.txt` | `525d5531d2fcb3494dcc7efa9ada0f7118986f7cd9aba8f9be2028237dd7ddc9` |

## Notes

- This release captures only the active `valley4_protocol_core` 70×70 delivery surface.
- Other bases remain preserved `future_scope` metadata and are not reactivated here.
- The full-scale 70×70 exact `CERTIFIED` end-state is still an open item. This workflow validates the current single-base delivery bundle and checked-in support surfaces only; it does not claim that the full exact terminal proof artifact has already been checked in.
