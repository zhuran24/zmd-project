# IndustrialPlanner preprocess face R7 audit — R6-F-01 fix confirmation + hash-closure generalization

Snapshot checked: `/mnt/data/zmd_r7_snapshot_e8c7dac3.zip`

Expected sha256: `e8c7dac3ca8af15e8ea23098f70304735a7b4a1bf6ee75045122f5ad64ae5179`

Observed sha256: `e8c7dac3ca8af15e8ea23098f70304735a7b4a1bf6ee75045122f5ad64ae5179`

Repo root audited after extraction: `/mnt/data/zmd_r7_audit/project`

## Verdict

本轮零 soundness finding.

R6-F-01 的修复在当前快照内是 sound 的：`preprocess_plan.json` 不能再用 `recipes` / `production_targets` / `commodity_roles` 静默覆盖 canonical truth；plan 已进入 exact campaign hash 闭包与 preflight frozen registry；旧 campaign state 缺少 `preprocess_plan` hash key 会按预期 fail-closed mismatch。

本轮没有代码补丁。Q4 发现两处非 soundness 的文档/metadata 精度问题，均不改变证明语义；其中一处如果修需要触碰冻结工件 hash，故本审查未直接改动。

## Self-checks run

- Archive sha256 verification: PASS.
- Targeted regression:
  - `python -m pytest -q src/tests/test_preprocess_context.py src/tests/test_preprocess_plan_schema.py src/tests/test_preprocess_plan_exact_hash.py`
  - Result: `11 passed`.
- Hash/resume/env probes:
  - `test_v84_exact_artifact_hashes_reject_symlinked_project_authority`: PASS.
  - `test_v96_exact_artifact_hashes_reject_symlinked_parent_project_authority`: PASS.
  - `test_campaign_resume_rejects_stale_candidate_placement_hash`: PASS.
  - `test_v80_certified_exact_env_guard_blocks_unclassified_exact_knob`: PASS.
  - `test_v80_certified_exact_env_guard_blocks_known_proof_knob`: PASS.
  - `test_v80_certified_exact_env_guard_allows_production_wrapper_operational_envs`: PASS.
- `python scripts/check_p1_2_proof_obligations.py`: PASS, `P1.2 proof obligation check passed: 8 obligations anchored`.
- `python scripts/preflight_gate.py` was attempted but exceeded the sandbox timeout; I did not use it as evidence.
- `candidate_placements.json` was regenerated only for audit probes because the lightweight snapshot intentionally omits this external artifact. Regenerated result: `66,403` placements, `45,773,799` bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`.

Full `src/tests` was not run in this audit window; the conclusion above is based on code review, targeted tests, and focused probes for the requested surface.

## Q1 — R6-F-01 fix review

### Builder fail-closed gate

The canonical override reject is placed inside the common builder, not only in one loader. `src/interchange/preprocess_context.py:147-181` validates payload types and rejects any top-level plan key in `PLAN_CANONICAL_OVERRIDE_KEYS = ("recipes", "production_targets", "commodity_roles")` before recipe/target/commodity parsing begins. The canonical truth is then read exclusively from `rules_payload` at `src/interchange/preprocess_context.py:183-198`, and metadata source tags are set to `canonical_rules` at `src/interchange/preprocess_context.py:219-221`.

Both public loading paths go through this builder:

- `load_default_preprocess_context()` reads `rules/canonical_rules.json` and `rules/preprocess_plan.json`, then calls the builder at `src/interchange/preprocess_context.py:355-360`.
- `load_preprocess_context_from_paths()` also calls the same builder at `src/interchange/preprocess_context.py:363-371`.

I did not find a plan path that consumes `recipes`, `production_targets`, or `commodity_roles` before the reject. Before the reject, the builder only reads canonical globals/templates/metadata and plan metadata; no forbidden plan section is merged or interpreted.

`_merge_overlay()` still exists at `src/interchange/preprocess_context.py:339-342`, but this audit did not find it used to build canonical recipe/target/commodity semantics. Its previous dangerous use has been removed from the active context path.

### Runtime consumers of the plan

`src/preprocess/operation_profiles.py:17` imports `load_default_preprocess_context()` at module import time, and `OPERATION_PORT_PROFILES` is derived from that context. Because this import path uses the builder, a plan carrying forbidden canonical override keys fails closed before runtime operation profiles can be produced.

`src/models/binding_subproblem.py:57-96` directly reads `rules/preprocess_plan.json` for `utility_operations.wireless_sink.generic_input_slots`. That direct loader does not schema-validate the whole plan and does not reject forbidden top-level keys by itself, but it also does not consume those keys. In the certified exact path, the operation-profile import path reaches the builder gate first; independently, the plan bytes are now hash-bound. Therefore this direct utility-slot reader is not an R6-F-01 residual override seam.

### Hash closure and sentinel semantics

`src/search/exact_campaign.py:192-204` now has two groups:

- `EXACT_HASH_FILES`: `mandatory_exact_instances`, `candidate_placements`, `canonical_rules`, `generic_io_requirements`.
- `OPTIONAL_EXACT_HASH_FILES`: `preprocess_plan -> rules/preprocess_plan.json`.

The missing sentinel is `__MISSING_OPTIONAL_EXACT_ARTIFACT__` at `src/search/exact_campaign.py:204`. It cannot collide with a real sha256 digest under normal comparison because a sha256 digest is 64 lowercase hexadecimal characters; the sentinel contains underscores and uppercase letters and has a different shape.

`sha256_file()` at `src/search/exact_campaign.py:259-271` rejects symlink components and non-regular files before hashing. For optional files, `compute_exact_artifact_hashes()` at `src/search/exact_campaign.py:274-284` uses the missing sentinel only when the optional path does not exist and no symlink component is present; if the path exists but is symlinked, non-regular, or unreadable, the hash path raises instead of silently accepting a sentinel. This is fail-closed.

Resume comparison is full dict equality. `_validate_existing_state()` rejects any `artifact_hashes` mapping that is not exactly equal to current hashes at `src/search/exact_campaign.py:1458-1490`; `ExactCampaign.load_or_create()` computes current hashes before resume at `src/search/exact_campaign.py:1805-1863`; `is_compatible_with_current_hashes()` also uses exact equality at `src/search/exact_campaign.py:1888-1889`. A probe that removed only the `preprocess_plan` key from a saved state produced `artifact_hash_mismatch` and reset the state, as desired.

### Schema layer and regression strength

`rules/preprocess_plan.schema.json` no longer admits `recipes`, `production_targets`, or `commodity_roles` because the schema has only `$schema`, `metadata`, `cycle_groups`, and `utility_operations` as top-level properties plus `additionalProperties: false`. Runtime does not rely on schema validation as the only defense; direct JSON loading still reaches the builder gate for context construction. This gives two layers for tests/tools and one hard runtime layer for any path that bypasses schema validation.

The new tests are discriminating:

- `src/tests/test_preprocess_context.py` parameterizes the three forbidden keys and expects `ValueError` containing `additive-only`. Under the old `_merge_overlay` behavior, those cases would have built a context instead of failing.
- `src/tests/test_preprocess_plan_exact_hash.py` mutates `rules/preprocess_plan.json` in a temporary project and asserts the `preprocess_plan` hash key exists and changes. Under the unpatched hash list, that test would fail because the key was absent or unchanged.

## Q2 — certified exact runtime input/hash-closure enumeration

I searched the exact runtime, model, interchange, and relevant script surfaces for JSON/file/env consumers, then classified whether the source can change certified solve/binding/routing/proof behavior. The table below lists the runtime input surface actually audited.

| Source/config | Certified runtime effect | Closure status | Verdict |
| --- | --- | --- | --- |
| `rules/canonical_rules.json` | Grid/objective globals, facility templates, canonical recipes/targets/commodity metadata, publication admissibility, model validation helpers. Read by `load_default_preprocess_context()`, `load_project_data()`, and exact-campaign validators. | In `EXACT_HASH_FILES` and `scripts/preflight_gate.py::FROZEN_ARTIFACTS`. | Closed. |
| `rules/preprocess_plan.json` | Runtime operation profiles via `PreprocessContext`, binding utility slots for `wireless_sink`, cycle/utility declarations used by preprocess/regeneration. | In `OPTIONAL_EXACT_HASH_FILES` and `FROZEN_ARTIFACTS`; production file exists and is frozen. | Closed by R6 fix. |
| `data/preprocessed/mandatory_exact_instances.json` | Mandatory facility instances placed by exact master. | In `EXACT_HASH_FILES` and `FROZEN_ARTIFACTS`. | Closed. |
| `data/preprocessed/candidate_placements.json` | Candidate pools and geometry domains. | In `EXACT_HASH_FILES`; in `EXTERNAL_FROZEN_ARTIFACTS` because it is an external large artifact. | Closed; omission from lightweight checkout is expected, not a bug. |
| `data/preprocessed/generic_io_requirements.json` | Required generic input/output counts and safe exact lower bounds; read by binding and exact campaign validation. | In `EXACT_HASH_FILES` and `FROZEN_ARTIFACTS`. | Closed. |
| `data/preprocessed/commodity_demands.json` | Used by flow diagnostics and heuristic feasible finder. In certified exact, it populates diagnostic flow status only; acceptance still depends on exact binding/routing proof after this diagnostic. | Not in exact hash closure. | Not a same-class soundness gap under current certified path. Re-audit if future code branches certified success/failure on this diagnostic artifact. |
| `data/preprocessed/machine_counts.json`, `data/preprocessed/port_budget.json` | Preprocess regeneration/audit inputs, not certified exact solve/proof inputs. | Not in exact hash closure. | No closure need for current certified runtime. |
| `data/preprocessed/all_facility_instances.json`, `data/preprocessed/exploratory_optional_caps.json` | Exploratory or regeneration surface; exact path uses mandatory instances. | Not in exact hash closure. | No certified exact closure need. |
| `rules/canonical_rules.schema.json`, `rules/preprocess_plan.schema.json` | Test/tool schema validation. The runtime builder/model validators do not load these schema files as proof semantics. | Not in exact hash closure. | No closure need. Changing schema alone does not change certified runtime behavior. |
| `data/checkpoints/exact_campaign_state.json` | Resume/checkpoint state. Current hashes are recomputed first and full equality is required before reuse. | Runtime state, not source truth. | No stale-source seam; old states without plan key mismatch fail closed. |
| `data/checkpoints/benders_cuts.jsonl` and persisted cut sidecars | Operational cut history/triage. Certified exact structured cut payload records current artifact hashes; raw persisted candidate cuts are not taken as proof objects for certified acceptance. | Not source truth. | No R6-class hash gap found. |
| `data/checkpoints/master_hints/*.json`, `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH` | Warm-start/master hints only. Loaded hints are applied through solver hints, not constraints or proof clauses. Invalid/missing hints are skipped. | Env classified operational. | No closure need. |
| `EXACT_*` environment variables | Potentially alter runtime. Guard is deny-unknown: unclassified `EXACT_*` names block merely by presence; known proof-semantics names must remain canonical false/default; operational allowlist covers time, logging, hints, workers, search profile, and solver parameters. | Controlled by runtime env guard in `src/search/benders_loop.py:758-907` and invocation sites. | Closed. Probe confirmed unknown `EXACT_FUTURE_UNKNOWN_KNOB=0` blocks and `EXACT_USE_HIGHS_MASTER=1` blocks. |
| `EXACT_COORDINATE_MASTER_SEARCH_PROFILE` | Changes CP-SAT search decision strategies, not constraints/proof semantics. | Operational env allowlist. | No closure need. |
| `EXACT_USE_HIGHS_MASTER` / HiGHS candidate evaluator files | Alternative/experimental master reads canonical/preprocessed artifacts, but the env knob is a known proof-semantics blocker in certified exact. | Blocks when truthy. | No certified gap. |
| Python module constants/tables | Code is part of the repository snapshot, not an external runtime artifact. The formerly dangerous `OPERATION_PORT_PROFILES` table is now derived from hash-bound canonical rules + plan. | Versioned code, not artifact hash. | No unhash file source found. |
| Adapter registries under `src/adapters/industrial_planner/*.json` | Export/validator/adapter surface, not exact solver/proof runtime. | Out of certified exact runtime closure. | No closure need for this audit scope. |
| Viewer/export files under `data/solutions`, `data/blueprints`, `data/examples`, `src/render/*` | Publication/viewer/export output consumers. They are not solve-source inputs. | Out of solver input closure. | No same-class gap. |
| `.artifacts/*`, telemetry JSON/JSONL | Diagnostics, triage, phase3b research artifacts. | Out of certified exact source closure. | No same-class gap. |

No runtime semantic file/config source with R6-F-01 shape was found outside `EXACT_HASH_FILES` / `OPTIONAL_EXACT_HASH_FILES` / frozen-artifact registration.

## Q3 — independent spot checks from r6 conclusions

### 266 mandatory demand math

I regenerated and cross-checked the preprocess demand objects through `load_default_preprocess_context()`, `solve_demands()`, `generate_ceil_machine_counts()`, `generate_port_budget()`, and `generate_generic_io_requirements()`.

Observed counts:

- Context: `17` recipes, `2` production targets, `2` cycle groups, `4` utility operations.
- Demand-solver production machine total: `219`.
- `mandatory_exact_instances.json` total: `266`.
- `boundary_io` instances: `46`.
- `protocol_core` instances: `1`.

Therefore the r6 arithmetic holds: `266 = 219 + 46 + 1`.

### 52-slot generic I/O balance

Observed generic output requirements:

- `blue_iron_ore`: `34`.
- `source_ore`: `18`.
- Total external generic outputs required: `52`.

Observed port availability:

- Boundary storage ports available on left/bottom boundary: `46`.
- Protocol core extra generic outputs: `6`.
- Total available generic outputs: `52`.
- Port budget status: `FEASIBLE`.

The 52-slot balance claim holds.

### Candidate pool

Regenerating `data/preprocessed/candidate_placements.json` from `python src/placement/placement_generator.py` produced the expected pool size and external hash:

- Total placements: `66,403`.
- Bytes: `45,773,799`.
- sha256: `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`.

## Q4 — documentation consistency

### Code-aligned docs confirmed

The following statements match current code behavior:

- `PROJECT_LOCK.md` states the frozen artifact set, calls out `preprocess_plan.json` as additive-only, says plan edits feed runtime operation profiles/binding slots and are exact-hash/preflight-bound, and documents the deny-unknown `EXACT_*` policy.
- `specs/04_recipe_and_demand_expansion.md:9` states canonical owns recipes/targets/commodity metadata, plan keeps only cycle groups and utility operations, forbidden keys fail closed, and plan is hash/preflight-bound.
- `specs/18_preprocess_context_contract.md:28-32` explicitly corrects the old regeneration-only claim and says operation profiles and binding utility slots consume plan data at runtime.
- `specs/20_canonical_rules_consolidation.md:23-32` and `:47` match the R6 behavior: plan is additive-only, cannot shadow canonical truth, and is hash-bound because it feeds runtime operation profiles.

### DOC-LOW-01 — stale plan metadata wording inside frozen artifact

Severity: LOW / documentation-metadata only, not soundness.

Location: `rules/preprocess_plan.json:5`.

The metadata description still says: `optional future overrides after canonical rules consolidation`. After R6-F-01, canonical recipe/target/commodity overrides are forbidden fail-closed, so this phrase is stale. It does not alter certified semantics because metadata is not used for constraints, forbidden top-level keys are rejected by the builder, and the plan bytes are hash-bound.

Suggested repair, if owner wants wording precision: change the description to something like `Additive preprocess overlay for cycle groups and utility operation slot declarations; canonical rules own recipes, production targets, and commodity metadata.`

Frozen-artifact impact if repaired: this edit would change the frozen `preprocess_plan` hash. It must be advanced with the full frozen ritual: update the expected plan sha256 in `scripts/preflight_gate.py::FROZEN_ARTIFACTS`, update any PROJECT_LOCK/spec references to the plan hash, and ensure exact hash tests/probes expect the new digest. I did not patch this file in the audit because the current stale phrase is not a proof-semantics flaw and touching it would churn a frozen artifact solely for wording.

### DOC-LOW-02 — `specs/19` retains phase-historical wording that under-specifies R6 runtime plan binding

Severity: LOW / documentation precision only, not soundness.

Location: `specs/19_phase3_frozen_compatible_preprocess_regeneration.md:37`, with related phase-history bullets at `:59-63`.

Line 35 correctly says `preprocess_plan.json` is additive-only and bound into the exact campaign hash closure + preflight registry. Line 37 then says the consolidation keeps the `certified runtime input surface unchanged`, while R6 now documents and enforces that the plan itself feeds runtime operation profiles/binding utility slots. The intended historical meaning appears to be “the frozen preprocess artifact trio remains the default placement/IO source,” not “no plan bytes affect certified runtime semantics.”

Suggested textual diff, documentation only:

```diff
--- a/specs/19_phase3_frozen_compatible_preprocess_regeneration.md
+++ b/specs/19_phase3_frozen_compatible_preprocess_regeneration.md
@@
-This reduces duplicated truth while keeping the certified runtime input surface unchanged.
+This reduces duplicated truth while keeping the default frozen preprocess placement/IO artifact surface
+unchanged.  `preprocess_plan.json` is now explicitly treated as a hash-bound runtime semantic
+input for operation-profile and utility-slot derivation; it is not a shadow override layer.
@@
-- keep certified runtime reading the same frozen preprocess artifacts
+- keep certified runtime reading the same frozen preprocess placement/IO artifacts, with the
+  additive plan separately hash-bound for operation-profile and utility-slot semantics
```

No frozen artifact hash changes are required for this spec-only repair.

## Frozen artifact clause

No code or frozen artifact was modified by this audit.

The only regenerated file was `data/preprocessed/candidate_placements.json`, used as a local probe because the lightweight snapshot omits the external artifact. Expected external registration for that file remains:

- path: `data/preprocessed/candidate_placements.json`
- sha256: `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`
- bytes: `45,773,799`
- registration surfaces: `src/search/exact_campaign.py::EXACT_HASH_FILES`, `scripts/preflight_gate.py::EXTERNAL_FROZEN_ARTIFACTS`, `PROJECT_LOCK.md` external artifact clause, and `data/external_artifacts.json`.

Current frozen plan hash remains:

- path: `rules/preprocess_plan.json`
- sha256: `1bcf0d13e1709cd7e04ddea439ee005e837584f2f66a1a921159d198019c9ed8`
- bytes: `1,387`
- registration surfaces: `src/search/exact_campaign.py::OPTIONAL_EXACT_HASH_FILES`, `scripts/preflight_gate.py::FROZEN_ARTIFACTS`, `PROJECT_LOCK.md`, and specs 04/18/19/20.

Because this audit delivered no source modification, no patch package is attached.
