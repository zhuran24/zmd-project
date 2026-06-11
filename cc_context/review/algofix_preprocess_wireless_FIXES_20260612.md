# preprocess F-01/F-02 complete repair: omni_wireless geometry + binding semantics

## Scope

This patch completes the certified preprocess repair chain for the `protocol_storage_box` canonical `omni_wireless` semantics. It adopts the archived generator repair, then makes binding/routing/flow/docs/tests agree with the new no-physical-port geometry.

## W1 generator-side repair adopted

Applied `cc_context/review/algoaudit_preprocess_face_r1_20260612.patch` as the starting point.

Key effects:

- `protocol_storage_box` is enumerated as a 3x3 no-port omni pose: `orientation = 0`, `port_mode = "omni"`, all anchors `x,y in [0,67]`, count `68 * 68 = 4,624`.
- `is_edge_starved()` now evaluates the routing front cell `(port.x, port.y) + DIR_DELTA[port.dir]`; a side is pruned only when all active front cells for that side are out of grid.
- Added geometry contract tests covering no-port omni boxes and front-cell starvation behavior.

Regenerated candidate artifact facts from this patch:

```text
manufacturing_3x3       4 * 68 * 64 = 17,408
manufacturing_5x5       4 * 66 * 62 = 16,368
manufacturing_6x4       4 * 65 * 63 = 16,380
protocol_core           2 * 58 * 58 = 6,728
protocol_storage_box    68 * 68     = 4,624
power_pole              69 * 69     = 4,761
boundary_storage_port   2 * 67      = 134
total                                 66,403
sha256                                adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
bytes                                 45,773,799
```

The generated `data/preprocessed/candidate_placements.json` is intentionally not included in the patch or delivery zip.

## W2 binding wireless consumption semantics

`src/models/binding_subproblem.py` now treats `operation_type == "wireless_sink"` as routing-free generic input capacity.

Implementation details:

- Added `load_wireless_sink_generic_input_slots()` backed by `rules/preprocess_plan.json::utility_operations.wireless_sink.generic_input_slots`.
- For every selected `wireless_sink` instance, `_build_generic_input_domains()` creates exactly that many virtual input slots. Current canonical count is 3.
- Virtual slots keep the normal binding rows: each slot has `AddExactlyOne(commodities + __unused__)`, and `_add_generic_input_requirements()` still enforces `sum(commodity vars) == required`.
- Virtual slots have no `x`, `y`, `dir`, or physical port cell. They are marked `virtual=True` and `routing_free=True`.
- `extract_selection()["generic_inputs"]` still reports bindings with stable ids like `{instance_id}:in:{k}`.
- `extract_port_specs()` skips `routing_free` / `virtual` slots, so no fake sink port reaches routing or flow.
- Boundary and protocol-core generic output semantics are unchanged.

Soundness argument: the binding capacity math is unchanged, only the geometric carrier changed from non-existent physical ports to canonical virtual slots. For a positive required commodity, the exact same `sum(vars) == required` row must be satisfied. For `required == 0`, all commodity vars are fixed to 0 and `__unused__` occupies every slot. If requirements exceed virtual capacity, CP-SAT remains infeasible. No artificial coordinates are introduced, so routing cannot silently prove a belt to a fake port.

## W3 routing and flow consistency

Routing and flow receive terminals only through `port_specs`. Since virtual wireless sink slots are deliberately omitted from `extract_port_specs()`, wireless sink consumption creates no sink front. The routing precheck therefore sees zero blocked ports and zero port-adherence literals for a no-port wireless box. The diagnostic flow path likewise receives no wireless commodity demand when demands are derived from emitted port specs.

Tiny probe result:

```text
[pre-W2 simulated old binding]
generic_input_slot_count=0
status=INFEASIBLE
port_specs=[]

[post-W2 virtual wireless slots]
generic_input_slot_count=3
status=FEASIBLE
port_specs=[]
routing_precheck=feasible blocked_ports=[]
routing_status=FEASIBLE port_adherence={'exact_links': 0, 'blocked_ports': 0, 'ports': 0}
flow_status=FEASIBLE wireless_nodes=False
```

This is the intended certified semantics: selected boxes consume generic inputs in binding, but require no belt route to the box.

## W4 frozen artifact lock/spec/docs updates

Updated the current artifact contract to:

```text
size   45,773,799 bytes
sha256 adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
```

Updated registration points include:

- `PROJECT_LOCK.md`
- `specs/06_candidate_placement_enumeration.md`
- `specs/05_facility_instance_definition.md`
- `docs/exact_campaign_operations.md`
- `docs/README.md` through `docs/subjects/certified_exact_contract.md` projection sync
- `FILE_STATUS.md`
- `data/external_artifacts.json`
- `START_HERE.md`
- `CLAUDE.md`
- `data/solutions/exact_full_scale_status.{json,md}`
- `scripts/preflight_gate.py`
- project overview/testing/review/glossary docs under `docs/项目说明/`

The old artifact hash `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f` is explicitly marked superseded/hash-incompatible. The new regression `test_campaign_resume_rejects_stale_candidate_placement_hash()` locks the fail-closed resume behavior through `artifact_hash_mismatch`.

`rules/canonical_rules.json` was not changed.

## W5 hint-chain residual

`scripts/blueprint_to_master_hint.py` now maps community blueprint `item_port_storager_1` / `protocol_storage_box` rotations to the omni pose at the same anchor: any rotation maps to `(orientation=0, port_mode="omni")`. The converter can emit advisory synthetic `pose_optional::protocol_storage_box::...` hint ids for optional protocol boxes.

`data/hints/blueprint_2026_05_13_master_hint.json` is documented as stale because its stored `pose_idx` values were generated against the superseded candidate pool. The source community blueprint is not in this package, so I could not regenerate that hint. This is not a soundness risk because CP-SAT hints are advisory only; stale hints can hurt search efficiency but cannot become proof evidence.

## W6 verification logs

Generated and verified artifact:

- `candidate_generation.log`
- `candidate_sha256.log`
- `candidate_size.log`
- `preprocess_face_probe.log`

Targeted regressions:

```text
python -m pytest -q -p no:randomly \
  src/tests/test_preprocess_candidate_geometry_contract.py \
  src/tests/test_p0_certified_soundness_fixes.py \
  src/tests/test_wireless_sink_binding_semantics.py \
  src/tests/test_binding.py::test_binding_model_assigns_generic_wireless_sink_inputs \
  src/tests/test_exact_contract.py::test_binding_recognizes_pose_optional_protocol_storage_box \
  src/tests/test_blueprint_to_master_hint.py \
  --tb=short

35 passed
```

Other checks:

```text
python scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 8 obligations anchored

python scripts/gen_authoritative_numbers.py --check
core node up to date

python scripts/sync_doc_subjects.py --check
doc subject projection check passed: 6 subjects, 19 fields, 30 projections

python scripts/check_external_artifacts.py --require candidate_placements
external artifact check passed: data/preprocessed/candidate_placements.json verified

python -m ruff check <changed python files>
All checks passed!

git diff --check
passed
```

Full pytest attempt:

```text
python -m pytest -q -p no:randomly src/tests/ --tb=short
```

This run was started and logged, but it did not complete inside the 1200 second execution window. The captured log reached 16% with no failures printed before the container timeout killed the command, so there is no full-suite failure summary from this sandbox run. The partial log is included as `full_pytest.log`, with `full_pytest_status.log` recording the timeout.

## New/updated regression tests

- `src/tests/test_preprocess_candidate_geometry_contract.py`
- `src/tests/test_wireless_sink_binding_semantics.py`
- Updated `src/tests/test_binding.py::test_binding_model_assigns_generic_wireless_sink_inputs`
- Updated `src/tests/test_exact_contract.py::test_binding_recognizes_pose_optional_protocol_storage_box`
- Updated `src/tests/test_blueprint_to_master_hint.py` for omni storage hint mapping
- Updated pool count assertions in `src/tests/test_master.py` and `src/tests/test_regression.py`
