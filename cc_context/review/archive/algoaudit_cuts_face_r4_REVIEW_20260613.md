# 终末地 IndustrialPlanner cuts R4 review

Snapshot: `/mnt/data/zmd_snapshot_278e4d67.zip`  
Expected sha256: `278e4d67f97a88cab7bba697ec96df2f04d43ce1475bc65aef4a22519d1885a0`  
Observed sha256: `278e4d67f97a88cab7bba697ec96df2f04d43ce1475bc65aef4a22519d1885a0`  
Scope: CUT-R3-H1 repair confirmation, lazy-demand/count cut family, deletion-core generic-slot consumption spot-check, and Q3 maintenance spot checks.

## Verdict

本轮有 1 个新的 soundness finding，已给出补丁与回归：`CUT-R4-H1`。

该 finding 当前仍在 env-gated pose-bool/cell-pattern/port-active 路径上，公开 certified 默认路径仍受 `pose_bool_master_not_certified` blocker 保护；但若未来 promote，该缺陷会从 hardening 直接升级为 master cut soundness 风险。

## Finding CUT-R4-H1: saturated generic-output does not imply routing-visible when the same commodity is a routing-free generic-input sink

Severity: High for future certified promotion; env-gated in this snapshot.

Files:

- Original snapshot: `src/models/pose_bool_exact_master.py:196-200`
- Binding consumer proving the counterexample is routing-free: `src/models/binding_subproblem.py:1055-1061`
- Role/generation interaction: `src/interchange/preprocess_context.py:271-285`, `src/preprocess/demand_solver.py:182-191`
- Regression after patch: `src/tests/test_wireless_front_consumers_r4.py:567-722`

### What was wrong

The R3 repair correctly changed generic-output slots from “always visible” to “visible only when required generic-output total globally saturates mandatory generic-output capacity.” The missing premise is that saturation proves only:

```text
for every physical generic-output slot s: assignment(s) != __unused__
```

It does not prove:

```text
for every physical generic-output slot s: assignment(s) is routing-visible
```

A positive `required_generic_outputs` commodity can also be in the routing-free sink set if it is also a positive `required_generic_inputs` commodity. Binding then treats its selected physical generic-output slot as non-unused, but `extract_port_specs()` drops it because routing-free sink commodities have no routing sink. In that state, a front-cell blocker does not make routing infeasible, yet the old pose-bool visible demand treated the saturated generic-output port as a routed front.

The current default data does not contain such an overlap (`blue_iron_ore`/`source_ore` are generic outputs; `qiaoyu_capsule`/`valley_battery` are generic inputs), but the cut-side premise was not encoded. The validator requires generic-input commodities to be production targets and not recipe inputs, but it does not make `source_kind == external_boundary` disjoint from `sink_kind == generic_input`; the demand generator independently emits `required_generic_outputs` from `source_kind == external_boundary` and `required_generic_inputs` from `sink_kind == generic_input`.

### Repro probe

Probe file used locally: `/mnt/data/zmd_review_r4/probe_cut_r4_h1.py`.

Counterexample shape:

- two `boundary_io` physical generic-output slots;
- `required_generic_outputs = {"wireless_ore": 2}`;
- `required_generic_inputs = {"wireless_ore": 1}`;
- one `protocol_storage_box` virtual wireless sink;
- one blocker occupying the first boundary port front cell.

On the original snapshot:

```text
binding_status FEASIBLE
selection {'binding_choice': {'blk': 0}, 'generic_inputs': {'sink1:in:0': 'wireless_ore', 'sink1:in:1': '__unused__', 'sink1:in:2': '__unused__'}, 'generic_outputs': {'b1:out:0': 'wireless_ore', 'b2:out:0': 'wireless_ore'}}
port_specs []
profile_demands (0, 1, 0, 1)
saturated True
solver_before_cut OPTIMAL
cut_added True
solver_after_cut INFEASIBLE
```

The binding is feasible and exports no routing terminal, so the placement-plus-binding is feasible with respect to routed fronts. The old cell-pattern cut then bans the placement pattern.

After the patch:

```text
binding_status FEASIBLE
port_specs []
profile_demands (0, 0, 0, 1)
saturated True
solver_before_cut OPTIMAL
cut_added False
solver_after_cut OPTIMAL
```

### Fix

Patch: `zmd_cut_r4_h1_patch.diff`.

The fix splits “saturated” from “routing-visible.” `generic_output_visible` is now counted only when both conditions hold:

1. required generic-output total globally saturates mandatory generic-output capacity;
2. every positive required generic-output commodity is disjoint from `_routing_free_sink_commodities()`.

If the requirement set mixes routed and routing-free generic-output commodities, pose-bool per-pose visible demand fails closed to 0 for generic-output slots. This is intentionally weaker: a future binding-aware or global-count cut could recover strength, but the current per-pose consumer cannot safely attribute the routed commodities to particular physical slots.

## Q1: CUT-R3-H1 repair confirmation after patch

### Saturation proof chain

Binding generic-output domains are built per physical output slot for `boundary_io` and `protocol_core`; every such slot receives an `AddExactlyOne` over all required generic-output commodities plus `__unused__` (`src/models/binding_subproblem.py:709-748`). For each generic-output commodity `c`, binding adds `sum(slot_var[c]) == required[c]` (`src/models/binding_subproblem.py:809-820`). Therefore, if:

```text
sum_c required[c] == number_of_physical_generic_output_slots
```

then the total number of non-`__unused__` assignments equals the number of slots, so no slot can be `__unused__`. This does not depend on per-commodity distribution, because the current binding domain gives every generic-output slot the same commodity set plus sentinel.

The valid post-patch implication used by cuts is narrower:

```text
required_total == capacity_total
AND positive_required_generic_outputs ∩ routing_free_sink_commodities == ∅
=> every mandatory generic-output slot is necessarily active and routing-visible.
```

The counterexample above shows why the second conjunct is necessary.

### Capacity statistics paths

Main path: `_mandatory_generic_output_capacity_total()` first consumes `owner._mandatory_groups`; for each group it uses `operation_type`, `profile.generic_output_slots`, and `count = group.count or len(instance_ids)` (`src/models/pose_bool_exact_master.py:155-174`). In the real master construction, `_build_mandatory_groups()` writes both `count = len(members)` and `instance_ids` from the same sorted member list (`src/models/master_model.py:2969-2988`), and `MasterPlacementModel.from_core` deep-copies those groups into the runtime owner (`src/models/master_model.py:2733-2734`). Thus the production delegate does not produce a `count`/`instance_ids` disagreement.

Fallback path: when no owner `_mandatory_groups` exists, the delegate falls back to `_mandatory_operation_by_group × _instance_ids_by_group`; any generic-output provider without an instance list returns `None`, which prevents saturation (`src/models/pose_bool_exact_master.py:176-194`). This is the intended fail-closed behavior for hand-built delegates/tests.

Possible disagreement if a test manually injects an inconsistent `_mandatory_groups` record is not a production-chain soundness issue: the main path is authoritative whenever groups exist, and the real constructor writes consistent records.

### Strict equality cases

`required < capacity`: not saturated, generic-output slots are not counted visible. This may miss an exact count cut, but it cannot over-cut.

`required > capacity`: not saturated by strict equality. Binding is globally infeasible or RAB-filtered capacity may fail the current placement, but cuts do not infer per-port routing visibility from that impossible or filtered state.

`required == capacity`: sound only after adding the routing-visible-disjointness check above. Without it, equality could hold while every selected physical generic-output slot is intentionally dropped by `extract_port_specs()`.

### Consumer propagation table

| Consumer | Code | Effect of smaller visible demand | R4 conclusion |
| --- | --- | --- | --- |
| Pose-level front-clear count, env `EXACT_USE_PORT_ACTIVE` | `src/models/pose_bool_exact_master.py:468-502` | Removes or weakens proactive hard-clearance constraints | Required for soundness in CUT-R4-H1; otherwise build-time count can over-cut routing-free saturated outputs. |
| Cell-pattern visibility cache | `src/models/pose_bool_exact_master.py:257-297`, `:1021-1039`, `:1152-1189` | Removes raw per-cell port candidates | Required for soundness; raw cell cuts need every physical port on that side to be necessarily routed. |
| Lazy-demand/count cut | `src/models/pose_bool_exact_master.py:1092-1135` | Removes per-pose count cut when demand cannot be safely attributed to that pose | Weakening only; current per-pose cut has no binding identity, so mixed generic routed/routing-free output must not be counted. |
| Legacy helper `_mandatory_port_side_is_routing_visible()` | `src/models/pose_bool_exact_master.py:240-255` | Same visible semantics if called | No active call site found in this snapshot; kept consistent by shared `_profile_port_demands()`. |

## Q2: lazy-demand/count cut family exactness

The lazy-demand cut shape is:

```text
sum(blockers_on_front_cells) <= K - demand    OnlyEnforceIf(pose_var)
```

where `K` is the number of physical ports on a side, and `demand` is `_routing_visible_profile_demands(op_type)` (`src/models/pose_bool_exact_master.py:1092-1129`). The theorem is: if the pose is selected, at least `demand` routed active fronts must be clear, so at most `K - demand` front cells may be blocked.

For concrete operation ports, exact pose-level binding enumerates combinations over physical port indices and rejects only when total required slots exceed the port count (`src/models/port_binding.py:143-179`). That makes the count cut exact: it does not care which physical ports are clear, only that enough clear ports remain for binding to choose.

For saturated generic-output slots where all positive required generic-output commodities are routed, every physical generic-output slot is active and routed, so the count demand is safe. In current canonical utility profiles the only generic-output providers are `boundary_io` with one slot and `protocol_core` with six slots; the lazy cut skips `K <= demand`, so the saturated default case mostly falls to the stricter cell-pattern cache rather than adding a separate count cut.

For unsaturated generic-output slots, generic inputs, and mixed routed/routing-free generic-output requirements, the lazy cut now sees zero generic-output demand. This is a deliberate weakness, not an over-cut: the current per-pose cut lacks binding identity and cannot prove which physical slot will carry a routed commodity.

Trigger/fail-closed behavior:

- The Benders path only reaches lazy-demand under `EXACT_B1_LAZY_DEMAND_CUT` and a pose-bool delegate (`src/search/benders_loop.py:5499-5506`, `:5627-5659`).
- `_profile_port_demands()` returns zero demand for unknown operation profiles by `KeyError` (`src/models/pose_bool_exact_master.py:204-208`).
- Saturation exceptions return false (`src/models/pose_bool_exact_master.py:196-202`), and the new routing-visible-disjointness helper also fails closed to false (`src/models/pose_bool_exact_master.py:133-140`).
- If the selected instance has no pose var, missing pose pool, zero demand, or no slackful side, `add_routing_port_lazy_demand_cut()` returns `False` without emitting a cut (`src/models/pose_bool_exact_master.py:1113-1130`).

Cell-pattern and lazy-demand combination is safe because both are necessary conditions over the same selected pose semantics. The cell cut is only registered when every physical port candidate is necessarily active and routed; the lazy cut only enforces a count of clear routed fronts. Adding both intersects two necessary conditions. Binding-local rejections are still tried before placement-level projection while alternatives remain (`src/search/benders_loop.py:5306-5324`).

## Deletion-core generic-slot consumption spot-check

Deletion-core receives routing-visible port keys from the current binding `port_specs` (`src/search/benders_loop.py:5519-5539`). Those specs already omit `__unused__`, virtual generic inputs, and routing-free outputs (`src/models/binding_subproblem.py:1037-1061`). The minimizer converts specs into per-instance visible keys (`src/search/routing_deletion_core_minimizer.py:41-68`) and `_oracle_front_blocked()` filters raw pose ports against that key set before checking front cells (`src/search/routing_deletion_core_minimizer.py:125-136`).

The R4 test `test_deletion_core_oracle_consumes_filtered_routing_visible_ports` verifies this boundary: raw geometry alone reports a blocked output, but the filtered empty visible-port map makes the oracle return false (`src/tests/test_wireless_front_consumers_r4.py:37-64`).

## Q3 maintenance spot checks

V82 persisted cuts remain telemetry-only. Runtime metadata publishes `persisted_exact_safe_cut_replay_input_count` but forces `persisted_exact_safe_cut_replay_enabled=False` (`src/search/benders_loop.py:1039-1059`, `:6880-6887`). The regression asserts forged persisted cuts are counted but not replayed (`src/tests/test_v82_persisted_cut_replay_fail_closed.py:123-128`, `:160-165`). The proof-obligation checker also anchors those needles (`scripts/check_p1_2_proof_obligations.py:1302-1312`).

F1-F9 lifecycle boundary remains present. `src/cuts/lifecycle.py` still states the 9-family map and that Step 2 / Step 8 are stubbed (`src/cuts/lifecycle.py:6-17`). `step_2_minimize()` and `step_8_apply_to_master()` still raise `NotImplementedError` (`src/cuts/lifecycle.py:716-725`, `:1106-1111`). The phase review gate parses `step_8_apply_to_master` and requires it to remain fail-closed while P1.3B is blocked (`scripts/check_phase_review_gate.py:217-244`, `:319-323`), with a regression that swaps in a non-raising fake lifecycle and expects an error (`src/tests/test_phase_review_gate.py:113-122`).

C-3/C-4 latent documentation is still present as known doc-tree findings, not re-reported here: C-3 is recorded as F9 “scope extension” cross-doc inconsistency, and C-4 as README hand-maintained line-count drift (`docs/research/doc_tree_full_audit_20260604/FINDINGS.md:35`, `:62`).

## Patch summary

Patched files:

- `src/models/pose_bool_exact_master.py`
- `src/tests/test_wireless_front_consumers_r4.py`
- `PROJECT_LOCK.md`
- `specs/10_benders_decomposition_and_cut_design.md`

Patch file: `/mnt/data/zmd_review_r4/zmd_cut_r4_h1_patch.diff`.

## Verification

Commands run from `/mnt/data/zmd_review_r4/project` using Python 3.13 after offline dependency install from `zmd_py313_linux_x86_64.zip`:

```text
python3.13 src/placement/placement_generator.py
# generated data/preprocessed/candidate_placements.json sha256:
# adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0

python3.13 -m pytest -q src/tests/test_wireless_front_consumers_r4.py -p no:randomly
# 12 passed in 0.34s

python3.13 -m pytest -q \
  src/tests/cuts \
  src/tests/test_wireless_front_consumers_r4.py \
  src/tests/test_binding.py \
  src/tests/test_v82_persisted_cut_replay_fail_closed.py \
  src/tests/test_benders_cut_condition_lits.py \
  src/tests/test_benders_cut_replay_condition_lifecycle.py \
  -p no:randomly
# 515 passed in 10.65s

python3.13 scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

Full `python -m pytest -q src/tests` was not run. Initial collection before offline dependency installation failed on missing OR-Tools, and the first post-install targeted run exposed the expected missing generated `candidate_placements.json`; after regenerating that artifact with the expected hash above, the targeted suites passed.
