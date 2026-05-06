# IndustrialPlanner Single-Base End-to-End Run Summary

Current active IndustrialPlanner contract: `valley4_protocol_core` (70×70) only. Other known bases and the larger-base outer-deployment path remain preserved as `future_scope` and do not re-enter the active checked-in CI surface through this workflow.

- Requested base: `valley4_protocol_core`
- Active contract base: `valley4_protocol_core`
- Requested base is active contract: True
- Overall status: `success`
- Delivery readiness: `ready_for_single_base_delivery`
- Full-scale exact `CERTIFIED` status: `open`
- Exact-status note: The full-scale 70×70 exact `CERTIFIED` end-state is still an open item. This workflow validates the current single-base delivery bundle and checked-in support surfaces only; it does not claim that the full exact terminal proof artifact has already been checked in.

## Step summary

| Step | Status | Key outcome |
|---|---|---|
| Canonical truth / planning | `proven_equivalent` | fixture `.artifacts/industrial_planner_single_base_e2e/canonical/full_demand_recipe_capacity_canonical_blueprint.json`; report `.artifacts/industrial_planner_single_base_e2e/canonical/full_demand_fixture_plan_report.md` |
| Export bundle | `written` | bundle `.artifacts/industrial_planner_single_base_e2e/bundle`; warnings `0` |
| Validator | `validator_acceptable_with_warnings` | import/layout `True`/`True`; port warnings `52` |
| Throughput audit | `proven_equivalent` | recipes proven `17` / required `17`; boundary proven `4` / required `4` |
| Fresh support reports | `written` | scope `default_contract_scope`; audited bases `valley4_protocol_core` |
| Checked-in support-suite inventory | `clean` | report sets `1`; drift entries `0` |
| Checked-artifact family gate | `clean` | families `1`; drift entries `0` |

## Validator interpretation

`validation_report.is_clean` is allowed to be `false` here when the only remaining issues are non-fatal `port_warnings`. Delivery readiness for this workflow is gated by `is_import_compatible=true` and `is_layout_healthy=true`, not by a warning-free export.

## Failure classes

- `planning_failed`: the deterministic fixture planner did not produce a canonical single-base source blueprint.
- `export_failed`: a canonical blueprint existed, but the IndustrialPlanner bundle could not be materialized.
- `validation_failed`: the exporter wrote a bundle, but import compatibility or layout health failed.
- `throughput_not_proven_equivalent`: the bundle exported, but the static recipe/capacity audit did not land at `proven_equivalent`.
- `support_generation_failed`: the single-base support report set could not be regenerated.
- `checked_in_support_drift_detected`: the checked-in support-suite inventory no longer matches current code/truth.
- `checked_artifact_drift_detected`: the repo-level checked-artifact family gate detected stale checked-in artifacts.

## Artifact roles

- `canonical_fixture` (required, planning) → `.artifacts/industrial_planner_single_base_e2e/canonical/full_demand_recipe_capacity_canonical_blueprint.json` — Regenerated canonical single-base source blueprint for this run.
- `fixture_plan_report_json` (required, planning) → `.artifacts/industrial_planner_single_base_e2e/canonical/full_demand_fixture_plan_report.json` — Machine-readable planning/generation report with slot choices and blocking classification.
- `fixture_plan_report_markdown` (required, planning) → `.artifacts/industrial_planner_single_base_e2e/canonical/full_demand_fixture_plan_report.md` — Operator-facing planning/generation report for the canonical fixture step.
- `industrial_planner_blueprint` (required, export) → `.artifacts/industrial_planner_single_base_e2e/bundle/industrial_planner.blueprint.json` — Actual IndustrialPlanner delivery blueprint for import.
- `industrial_planner_compatibility_manifest` (required, export) → `.artifacts/industrial_planner_single_base_e2e/bundle/industrial_planner.compatibility_manifest.json` — Translation / fallback / validation sidecar explaining the export boundary.
- `validation_report_json` (required, validator) → `.artifacts/industrial_planner_single_base_e2e/bundle/validation_report.json` — Machine-readable offline import/layout validation report.
- `validation_report_markdown` (required, validator) → `.artifacts/industrial_planner_single_base_e2e/bundle/validation_report.md` — Human-readable offline import/layout validation report.
- `throughput_report_json` (required, throughput) → `.artifacts/industrial_planner_single_base_e2e/bundle/throughput_report.json` — Machine-readable static recipe/capacity audit report.
- `throughput_report_markdown` (required, throughput) → `.artifacts/industrial_planner_single_base_e2e/bundle/throughput_report.md` — Human-readable static recipe/capacity audit report.
- `fresh_support_canonical_matrix_json` (required, support_reports) → `.artifacts/industrial_planner_single_base_e2e/support_suite/full_demand_base_support_matrix.json` — Freshly regenerated canonical single-base support matrix for this run.
- `fresh_support_canonical_matrix_markdown` (required, support_reports) → `.artifacts/industrial_planner_single_base_e2e/support_suite/full_demand_base_support_matrix.md` — Operator-facing canonical single-base support matrix for this run.
- `fresh_support_deployment_matrix_json` (required, support_reports) → `.artifacts/industrial_planner_single_base_e2e/support_suite/full_demand_deployment_path_matrix.json` — Freshly regenerated companion deployment-path support matrix for this run.
- `fresh_support_deployment_matrix_markdown` (required, support_reports) → `.artifacts/industrial_planner_single_base_e2e/support_suite/full_demand_deployment_path_matrix.md` — Operator-facing companion deployment-path support matrix for this run.
- `fresh_support_overview_json` (required, support_reports) → `.artifacts/industrial_planner_single_base_e2e/support_suite/full_demand_support_overview.json` — Freshly regenerated umbrella support summary for this run.
- `fresh_support_overview_markdown` (required, support_reports) → `.artifacts/industrial_planner_single_base_e2e/support_suite/full_demand_support_overview.md` — Operator-facing umbrella support summary for this run.
- `support_suite_inventory_summary_json` (required, checked_in_support_suite) → `.artifacts/industrial_planner_single_base_e2e/checks/support_suite_inventory_summary.json` — Machine-readable verdict for the checked-in support-suite inventory.
- `support_suite_inventory_summary_markdown` (required, checked_in_support_suite) → `.artifacts/industrial_planner_single_base_e2e/checks/support_suite_inventory_summary.md` — Human-readable verdict for the checked-in support-suite inventory.
- `support_suite_inventory_summary_console` (optional, checked_in_support_suite) → `.artifacts/industrial_planner_single_base_e2e/checks/support_suite_inventory_summary.txt` — Plain-text console verdict for the checked-in support-suite inventory.
- `checked_artifact_suite_summary_json` (required, checked_artifact_gate) → `.artifacts/industrial_planner_single_base_e2e/checks/checked_artifact_suite_summary.json` — Machine-readable repo-level checked-artifact gate verdict.
- `checked_artifact_suite_summary_markdown` (required, checked_artifact_gate) → `.artifacts/industrial_planner_single_base_e2e/checks/checked_artifact_suite_summary.md` — Human-readable repo-level checked-artifact gate verdict.
- `checked_artifact_suite_summary_console` (optional, checked_artifact_gate) → `.artifacts/industrial_planner_single_base_e2e/checks/checked_artifact_suite_summary.txt` — Plain-text console verdict for the repo-level checked-artifact gate.

## Interpretation boundary

- `industrial_planner.blueprint.json` is the actual target delivery blueprint for IndustrialPlanner import.
- `industrial_planner.compatibility_manifest.json` is a translation / fallback / validation sidecar; it explains the export, but it is not the blueprint itself.
- `throughput_report.*` is a static recipe/capacity audit only; it does not simulate steady-state runtime behavior or replace the exact proof chain.
- `full_demand_support_*` files are contract-surface reports that tell you whether the active single-base support surface and its future-scope metadata are still in sync.
- This workflow does not reactivate other bases. They remain `future_scope` until the single-base line is fully closed and a new base contract is explicitly defined.
