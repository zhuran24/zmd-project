# Phase3B GPT-5.4 Pro Help Request

> ⚠️ **HISTORICAL（状态校准至 2026-07-11）**：本文只记录 2026-04-22 的 Phase 3B 求助快照（coordinate-master 时代瓶颈、candidate UNKNOWN 等），不能描述现行阶段。现行状态见 `PROJECT_LOCK.md`、`CLAUDE.md` 与 `docs/项目说明/06_current_status.md`；下方内容按历史读。

Date: 2026-04-22  
Project: Endfield / 70x70 exact refactor Phase3B  
Audience: GPT-5.4 Pro reviewer with the repository attached

## Short Version

We are blocked before the final 168h exact campaign. The release/product surface must remain `open`; we do not yet have a certified anchor. The immediate bottleneck is not documentation, packaging, or release promotion. It is that the current exact campaign candidate `67x13` still ends in `UNKNOWN` with a zero-branch master solve even after multiple proof-preserving/default-off diagnostic improvements.

The most recent bounded B5A retry used:

- selected-block / block64 / all-template formulation
- ghost-overlap no-solve precheck enabled
- signature-monotonic forced-label precheck enabled
- ghost-aware coordinate validation cap 128
- pose-order validation budget increased to 30s
- one bounded sprint attempt, not the 168h final run

Result:

- `anchor_found=false`
- campaign final status `UNKNOWN`
- master solve still `0 branches / 0 conflicts`
- pose-order portfolio `UNKNOWN` count was reduced to `0`
- final start attribution still rejected all 112 anchor attempts

So increasing pose-order validation time fixed the portfolio observability/timeout artifact, but did not find a compatible start or unlock the master. The current best pivot appears to be the deeper power/protocol/family lookup global blocker, not another pose-order budget increase.

I want your help deciding the next proof-preserving/default-off path. I especially want an independent review of whether the current evidence really points back to the power/protocol/family lookup global blocker, or whether there is a more exact-safe start/encoding change we should test first.

## Hard Boundaries

Please keep these boundaries strict:

- Do not suggest launching the final 168h production long run yet.
- Do not suggest promoting release/viewer/frontdoor/surface-health exact status.
- Do not treat diagnostic forced-anchor, proto-deletion, semantic-weakening, or workspace checkpoints as proof.
- Do not modify the four exact hash truth sources unless you explicitly identify a proof-source change and a reset strategy.
- Prefer proof-preserving, default-off, report-only, or no-solve diagnostics before runtime changes.
- Any runtime precheck must be guarded/default-off until it has a proof-safe contract and focused regression coverage.
- Workspace checkpoints are not to be copied back into repo main proof paths.

## Repository State You Will Receive

The repository has already accumulated many B1-B5A support layers:

- B1 inspector / recovery / telemetry surfaces.
- B2 pre-master lookahead and observability.
- B3 unknown triage and blocker inventory.
- B4 operating profile.
- B5A workspace preparation, bounded sprint runner, summarizer, and long-run preflight gate.
- Many Phase3B diagnostic modules under `src/search/phase3b_*`.

The main repo intentionally does not contain a valid production `data/checkpoints/exact_campaign_state.json`. Campaign checkpoints are generated in E: workspaces and should stay there unless frozen evidence is explicitly accepted later.

Important recent repo files:

- `src/models/master_model.py`
- `src/search/campaign_triage.py`
- `src/search/phase3b_start_repair_evidence_surface.py`
- `src/search/phase3b_start_repair_portfolio_audit.py`
- `src/search/phase3b_start_repair_portfolio_sample_comparison.py`
- `src/search/phase3b_pose_order_unknown_resolution.py`
- `src/search/phase3b_b5a_blocker_pivot.py`
- `src/search/phase3b_signature_monotonic_forced_label_audit.py`
- `src/search/phase3b_signature_monotonic_precheck_candidate.py`
- `src/search/phase3b_signature_monotonic_precheck_promotion_spec.py`
- `src/search/phase3b_coordinate_validation_global_family_delta.py`
- `src/search/phase3b_signature_region_equivalence_audit.py`
- `scripts/run_phase3b_b5_anchor_sprint.ps1`
- `scripts/build_phase3b_long_run_preflight.py`

## Current Preflight Status

The long-run preflight remains blocked:

```text
ready=False
failed checks:
- b5a_anchor_found
- production_acceptance_present
- production_acceptance_prod_4x4_valid
```

This is expected and correct. Production acceptance should not be run until B5A finds a certified anchor, or until we have a stronger reason to run it.

The latest preflight recommendation still points to the power/protocol/family lookup global blocker:

```text
Blocked before final long run: B5A did not find a certified anchor;
zero-branch UNKNOWN triage for 67x13 points to presolve/model-building work:
Zero-branch UNKNOWN is reproduced in the base forced-anchor model;
model-slice and anchor-delta findings point at power coverage core/residual optional interactions.
Power/protocol interaction diagnostic narrows the next probe to
power_coverage_elements_full_family_lookup_table_required_progress_blocker
(family=family_009, template=protocol_storage_box).
```

## Timeline And What We Tried

### 1. Original B5A Goal

B5A was intended to run a conservative first-certified-anchor sprint in a workspace copy, not in repo main, and either:

- find a first `CERTIFIED` anchor, or
- produce explainable `UNKNOWN` / `UNPROVEN` triage input.

So far, B5A has not found an anchor.

### 2. Direct Forced-Label / Coordinate Core Diagnostics

Early blocker work focused on anchor `119` and nearby anchors. We investigated direct equality cores for manufacturing groups.

For `manufacturing_5x5::planter_sandleaf::10` around anchor119:

- `x_y_mode` direct equality core shrank from 63 labels to 3 keys.
- Final 3 keys are `INFEASIBLE`.
- Removing any one key gives `UNKNOWN`.
- Single-key controls are `UNKNOWN`.

For `manufacturing_6x4::grinder_dense_blue_iron::14` around anchor119:

- `x_y_mode` direct equality core shrank from 51 labels to 3 keys.
- Final 3 keys are `INFEASIBLE`.
- Removing any one key gives `UNKNOWN`.
- Single-key controls are `UNKNOWN`.

The stable three-key core interpretation was not full pose equality. A no-solve geometry report showed these are partial-field constraints, such as specific `y`, `mode`, or `x` fields, and not simple fixed-pose overlaps.

### 3. No-Overlap Was Not The Main Explanation

We ran no-overlap attribution on m6x4 exchange subsets. The result was negative:

- Base subset was `INFEASIBLE`.
- Removing core no-overlap, ghost no-overlap, both no-overlap, target-group intervals, ghost intervals, and related no-overlap variants all stayed `INFEASIBLE`.

Interpretation: this lowers priority for a pure `NoOverlap2D` / ghost-overlap explanation. The conflict seemed more likely in slot order, signature/domain constraints, power coverage, or family lookup/selector interactions.

### 4. Signature / Region Path

Global-family attribution initially showed that broad mandatory signature membership/bucket deletion changed the status to `UNKNOWN`, but the selector was too broad: it removed thousands of constraints across mandatory groups, including examples from boundary storage, so it was not precise enough.

We split the selector:

- target mandatory signature/bucket vs other mandatory groups
- target `signature__`
- target `is_sig__` bucket
- target `region__`

For all three m6x4 exchange subsets:

- `remove_target_mandatory_signature_membership_or_bucket` changed `INFEASIBLE` to `UNKNOWN`.
- `remove_other_mandatory_signature_membership_or_bucket` stayed `INFEASIBLE`.
- `remove_target_mandatory_signature_var` changed `INFEASIBLE` to `UNKNOWN`.
- `remove_target_mandatory_region` changed `INFEASIBLE` to `UNKNOWN`.
- `remove_target_mandatory_is_sig_bucket` stayed `INFEASIBLE`.

This localized the signal to the target group, especially `signature__` and `region__`, but it was still semantic weakening and not proof.

We then ran a no-solve signature-region equivalence audit for:

```text
group::manufacturing_6x4::grinder_dense_blue_iron::14
```

Result:

- `outcome=equivalent`
- `solver_invoked=false`
- bucket count `4`
- exact union tuple count `16900`
- region union tuple count `16900`
- mismatched bucket count `0`
- overlap tuple count `0`

Then we ran a diagnostic replacement variant:

```text
replace_target_mandatory_region_with_exact_signature_table
```

It removed compact target `region__` constraints and added exact `[x,y,mode,signature]` allowed-assignment tables. The status stayed `INFEASIBLE`.

Interpretation: the compact region tuple language does not appear to be wrong. The blocker is more likely an exact monotonic/signature interaction induced by partial forced fields, not a bad region encoding.

### 5. Signature-Monotonic Forced-Label Precheck

We built a no-solve audit for signature-monotonic contradictions.

For three m6x4 exchange subsets:

- all are no-solve `monotonic_infeasible`
- `solver_invoked=false`
- `proof_source=false`

Examples:

- `source_sweep`: slot15 labels imply allowed signature `{3}`; slot16 `y=65` implies `{2}`; monotonic nondecreasing signature order fails at slot16.
- `source_earlier`: constrained slots are slot11 `{2,3}`, slot14 `{0,1,3}`, slot16 `{2}`; DP narrows previous possible signatures to `[3]` before slot16, then fails on `[2]`.
- `combo_006`: same shape; DP narrows previous possible signatures to `[3]` before slot16, then fails on `[2]`.

We then implemented a guarded/default-off runtime precheck:

```text
EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK
```

It is inside `_validate_coordinate_forced_hint(...)`, after same-x capacity precheck and before CP-SAT cloning/solve.

When enabled, it only short-circuits if forced labels imply an impossible nondecreasing signature sequence for a compact mandatory signature group.

Runtime validation:

- `source_earlier`: `INFEASIBLE`, reason `signature_monotonic_forced_label_infeasible`, `attempted_solver=false`
- `source_sweep`: same
- `combo_006`: same
- control `slot16 y=65 only`: did not trigger, solver still attempted

This precheck is still default-off and not a proof source.

### 6. B5A Retry With Signature-Monotonic Precheck

We ran a bounded workspace B5A retry with the signature-monotonic precheck enabled.

Workspace:

```text
E:\phase3b_workspaces\endfield_phase3b_b5_anchor_20260422_signature_precheck_runtime
```

Result:

- `anchor_found=false`
- final status `UNKNOWN`
- master solve still zero-branch
- `master_start_failure_attribution`:

```json
{
  "coordinate_validation_infeasible": 8,
  "coordinate_validation_signature_monotonic_forced_label_infeasible": 8,
  "coordinate_validation_attempt_limit_reached": 1
}
```

Interpretation: the precheck was useful and participated in attribution, but it did not certify an anchor or eliminate the zero-branch master unknown.

### 7. Residual Coordinate / Pose-Order Diagnostics

We then investigated residual `coordinate_validation_infeasible` anchors. Across the cap128 fresh-source run, residual pose-order taxonomy eventually became complete:

- observed ordering-sensitive anchors: `8`
- missing artifacts: `0`
- two classes:
  - buckwheat class: anchors `159,171,217,229`
  - sandleaf class: anchors `172,173,230,231`

For each class, some orderings produce `INFEASIBLE` and some remain `UNKNOWN`. This is diagnostic but not proof.

We built a geometry/order signature report and an order-independent predicate scan:

- no global order-independent predicate was found
- local clue `y_unique:11` existed only for buckwheat
- existing no-overlap/capacity diagnostics for that clue were negative

Interpretation: the residual geometry/order path is not currently promotable to a runtime/proof precheck.

### 8. Pose-Order Portfolio Observability

A current-source B5A run had portfolio aggregate:

```json
{
  "coordinate_validation_ghost_overlap_forced_domain_infeasible": 2,
  "coordinate_validation_infeasible": 49,
  "coordinate_validation_signature_monotonic_forced_label_infeasible": 34,
  "coordinate_validation_unknown": 27
}
```

We added metadata collection:

```text
ghost_aware_pose_order_portfolio_failure_samples
```

This is reporting only; it does not change solver decisions.

Then we reran start-compatibility with selected-block env and bounded sample capture. The unknown count dropped from `27` to `2`, localized to anchors `130` and `131`, both `y_then_x`.

We then ran pose-order validation probes for anchors `130` and `131` with 30s validation.

Both collapsed to prefix infeasible:

- prefix 1: `boundary_storage_port::boundary_io::0` remained `UNKNOWN`
- prefix 2: adding `protocol_core::protocol_core::18` became `INFEASIBLE`

Interpretation: those portfolio UNKNOWNs were budget/setup artifacts, not stable unknown blockers.

### 9. B5A Retry With Pose-Order Validation 30s

We added a runner parameter:

```powershell
-GhostAwarePoseOrderValidationSeconds
```

Default remains `2.0`. Explicit 30s is used only when requested.

Then we ran a fresh isolated workspace retry:

```text
E:\phase3b_workspaces\endfield_phase3b_b5_anchor_selected_block_pose30_20260422_2235
```

Command shape:

```powershell
scripts\run_phase3b_b5_anchor_sprint.ps1 `
  -CampaignHours 0.1 `
  -MaxAttempts 1 `
  -BendersMaxIter 1 `
  -FormulationProfile selected_block_block64_all_templates `
  -EnableGhostAwareNoSolvePrechecks `
  -GhostAwareCoordinateValidationMaxAnchors 128 `
  -GhostAwareCoordinateValidationSeconds 10 `
  -GhostAwarePoseOrderValidationSeconds 30 `
  -WallTimeoutSeconds 2400
```

Result:

- `anchor_found=false`
- campaign final status `UNKNOWN`
- telemetry wave count `1`
- master solve:
  - status `UNKNOWN`
  - branches `0`
  - conflicts `0`
  - deterministic time about `4.115`
  - wall time about `37.37s`

Final master-start attribution stayed:

```json
{
  "coordinate_validation_ghost_overlap_forced_domain_infeasible": 2,
  "coordinate_validation_signature_monotonic_forced_label_infeasible": 102,
  "coordinate_validation_infeasible": 8
}
```

Pose-order portfolio aggregate became:

```json
{
  "coordinate_validation_ghost_overlap_forced_domain_infeasible": 2,
  "coordinate_validation_signature_monotonic_forced_label_infeasible": 34,
  "coordinate_validation_infeasible": 76
}
```

Notably:

- `coordinate_validation_unknown=0`
- all 112 portfolio attempts rejected
- no compatible anchor found

Interpretation: increasing pose-order validation to 30s solved the portfolio UNKNOWN observability issue, but did not solve the actual B5A blocker.

## Current Bottleneck As I Understand It

The current hard blocker is:

```text
candidate 67x13 still ends in master UNKNOWN with zero branches/conflicts
after all ghost-aware anchor starts are rejected.
```

The start portfolio is no longer opaque:

- 2 anchors are rejected by ghost-overlap forced-domain precheck
- 34 are rejected by signature-monotonic forced-label precheck in the pose-order portfolio
- 76 are coordinate-validation infeasible under 30s pose-order validation
- final selected start attribution still reports 2 / 102 / 8 across the final layer

But the master still falls back to global greedy and then solves to zero-branch `UNKNOWN`.

This makes me think the next useful branch is not more pose-order time. It is either:

1. a proof-preserving way to produce a compatible start despite these rejections, or
2. a deeper formulation/presolve fix for the master zero-branch blocker, likely around power/protocol/family lookup.

## Power / Protocol / Family Lookup Context

Earlier diagnostic work outside the latest B5A retry pointed to a global power/protocol blocker:

```text
power_coverage_elements_full_family_lookup_table_required_progress_blocker
family=family_009
template=protocol_storage_box
```

The rough picture from prior proto-reduction / formulation diagnostics:

- base forced-anchor model can be zero-branch `UNKNOWN`
- deleting only one side is often insufficient
- progress appears when power coverage Element system and family lookup table system are jointly removed or heavily altered
- this is diagnostic deletion, not proof
- all-template block and selected-block formulations reduce some pressure but do not certify an anchor

There were also earlier notes that:

- `block64 + linear family/distance` significantly reduces presolved variables compared to default
- all-template block can reduce deterministic work but may also reduce conflict signal
- full table / full Element coupling may still form a dense propagation graph that consumes time in presolve/model expansion/setup

This is the area where I most need outside judgment.

## What I Am Currently Considering

### Option A: Return To Power/Protocol/Family Lookup Diagnostics

Hypothesis:

The remaining zero-branch master unknown is caused by dense coupling between:

- power coverage witness Elements
- family lookup tables
- protocol storage box / family_009
- residual optional / coverage constraints

Possible next diagnostics:

1. Build a fresh report-only summary of all power/protocol artifacts and current formulation knobs.
2. Re-run a sparse/non-contiguous table-slot diagnostic if current artifacts are stale.
3. Add deterministic-time and presolve-stage telemetry if not already captured enough.
4. Search for a proof-preserving equivalent encoding:
   - replace `Element`-based cover witness channels with explicit guarded cover literals
   - split monolithic family lookup tables by family or shell-pair
   - use linear shell guards where equivalence is already proven
5. Any replacement must first be default-off and equivalence-tested.

My concern:

Some earlier diagnostics rely on semantic deletion or proto mutation. They are useful for localization but not valid proof. I need help separating “promising formulation replacement” from “diagnostic-only weakening”.

### Option B: Start-Repair / Compatible Start Construction

Hypothesis:

Even if many anchor orderings are rejected, there may be a proof-safe way to build a compatible start by changing start construction, not exact model semantics.

Possible next diagnostics:

1. Inspect whether the final start fallback `global_greedy_fallback` is too brittle.
2. Try local repair around rejected `boundary_storage_port + protocol_core` prefix interactions.
3. Investigate whether a different ordering contract can avoid rejections without hiding infeasibility.
4. Keep any start-repair attempt diagnostic/default-off until it is proven not to affect proof semantics.

My concern:

The latest 30s portfolio rejected all 112 attempts. That suggests we may be out of cheap start-repair headroom. Also order-sensitive diagnostics failed to produce a global order-independent predicate.

### Option C: Master Zero-Branch Presolve / Search Configuration

Hypothesis:

The master is not branching because presolve/model setup is consuming the budget or compressing the model into a state where no search progress happens. The issue may be parameter-sensitive or formulation-sensitive.

Possible next diagnostics:

1. Capture full CP-SAT presolve logs for the current selected-block pose30 workspace.
2. Compare protocol-only vs all-template vs selected-block profiles under identical seeds and deterministic time budgets.
3. Track deterministic time vs wall time vs branches/conflicts.
4. Verify whether disabling/enabling probing/symmetry/linearization changes zero-branch behavior.

My concern:

This may explain the symptom but not produce an exact-safe fix unless tied to a concrete encoding change.

## Concrete Questions For You

1. Given the current evidence, do you agree that the next branch should pivot back to power/protocol/family lookup rather than continue pose-order/start-repair?

2. Is the interpretation of the latest pose30 B5A retry sound?

   My interpretation is:

   - portfolio UNKNOWNs were largely budget/setup artifacts
   - pose-order 30s eliminated that uncertainty
   - all 112 starts are now rejected
   - therefore the remaining blocker is deeper than pose-order validation time

3. Do you see a proof-preserving encoding replacement candidate around power coverage Elements and family lookup tables?

   Especially:

   - replacing `Element` witness channels with per-pair guarded cover literals
   - splitting family lookup tables
   - changing table construction without changing allowed tuple semantics
   - adding redundant but solver-friendly constraints

4. What exact equivalence tests would you require before such an encoding replacement is even allowed as default-off runtime code?

5. Are there any modeling-bug smells in the current signature/region/monotonic path despite the equivalence audit passing?

6. Is there any reason to run another bounded B5A attempt now?

   My current answer is no, unless a concrete new proof-preserving formulation/start change lands first.

7. What is the smallest next diagnostic that would most reduce uncertainty?

   I want a next step that is not just “run a larger matrix”.

## Evidence Paths Mentioned In This Letter

These are local paths from the working machine. If only the repo is uploaded, some E: workspace artifacts may not be included. I copied the key numerical results into this letter so the reasoning is still readable.

Current repo:

```text
D:\codex pj\zmd 70x70\endfield_phase3b_project_current
```

Coordinator state:

```text
D:\codex pj\zmd 70x70\phase3b_coordinator_state.md
```

Latest pose30 B5A workspace:

```text
E:\phase3b_workspaces\endfield_phase3b_b5_anchor_selected_block_pose30_20260422_2235
```

Latest pose30 B5A operator summary:

```text
E:\phase3b_workspaces\endfield_phase3b_b5_anchor_selected_block_pose30_20260422_2235\.artifacts\phase3b_b5_anchor_sprint\operator_summary.json
```

Latest pose30 triage:

```text
E:\phase3b_workspaces\endfield_phase3b_b5_anchor_selected_block_pose30_20260422_2235\.artifacts\phase3b_unknown_triage_pose30_20260422\blocker_inventory.json
```

Latest pose30 start-repair evidence surface:

```text
E:\phase3b_workspaces\endfield_phase3b_b5_anchor_selected_block_pose30_20260422_2235\.artifacts\phase3b_start_repair_evidence_surface_pose30_20260422\start_repair_evidence_surface.json
```

Previous current-source cap128 workspace:

```text
E:\phase3b_workspaces\endfield_phase3b_b5_anchor_current_source_selected_block_cap128_20260422_1645
```

Portfolio sample comparison:

```text
E:\phase3b_workspaces\endfield_phase3b_b5_anchor_current_source_selected_block_cap128_20260422_1645\.artifacts\phase3b_start_repair_portfolio_sample_comparison\portfolio_sample_comparison.json
```

Pose-order UNKNOWN resolution:

```text
E:\phase3b_workspaces\endfield_phase3b_b5_anchor_current_source_selected_block_cap128_20260422_1645\.artifacts\phase3b_pose_order_unknown_resolution\pose_order_unknown_resolution.json
```

Residual pose-order taxonomy:

```text
E:\phase3b_workspaces\endfield_phase3b_b5_anchor_current_source_selected_block_cap128_20260422_1645\.artifacts\phase3b_residual_pose_order_taxonomy\residual_pose_order_taxonomy.json
```

Order-independent predicate scan:

```text
E:\phase3b_workspaces\endfield_phase3b_b5_anchor_current_source_selected_block_cap128_20260422_1645\.artifacts\phase3b_order_independent_predicate_scan\order_independent_predicate_scan.json
```

Signature-monotonic runtime validation:

```text
D:\codex pj\zmd 70x70\endfield_phase3b_project_current\.artifacts\phase3b_signature_monotonic_runtime_precheck_validation\runtime_validation.json
```

Signature-region equivalence audit:

```text
D:\codex pj\zmd 70x70\endfield_phase3b_project_current\.artifacts\phase3b_signature_region_equivalence_audit\signature_region_equivalence_67x13_m6x4_anchor119_context.json
```

## What I Need Back

Please respond with:

1. Your diagnosis of the true current bottleneck.
2. Which existing conclusion you distrust most, and why.
3. The smallest next diagnostic or patch you would run.
4. The proof-safety contract for that patch.
5. Specific files/functions in the uploaded repo that you would inspect first.
6. A short ordered plan for the next 1-3 work sessions.

The most useful answer would not be a broad rewrite. I need a surgical next move that either:

- finds a proof-preserving way to break the zero-branch master blocker, or
- proves that the current branch is exhausted and identifies the next exact-safe branch.

