"""Stage-B typed plan interpreter — the sole typed master-mutation dispatch.

RFC-001 §7 B5a 拍板 3.  ``apply_compiled_cut`` is the one place a typed
``CompiledCut`` becomes CP-SAT constraints.  It switches on the plan's closed
``operation`` set (one row per master API) and forwards the runtime material —
CP-SAT ``condition_lits`` and the F7 raw ``blocked_cells`` — that the sole
resolver (``lifecycle._resolve_model_scope_binding``) recovered from the ghost
context and frozen snapshot values.

This module is TCB: every argument is exact-type gated, the operation set is
closed, and every path is fail-closed (a master ``False`` return raises so no
partial constraint is ever left attached).  ``master`` is an opaque ``Any`` to
keep ``src/cuts`` import-isolated from the CP-SAT master types.
"""

from __future__ import annotations

from typing import Any

from src.cuts.state_snapshot import blocked_cells_digest_v1
from src.cuts.typed_platform import CompiledCut, ModelScopeBinding


def apply_compiled_cut(
    compiled_cut: CompiledCut,
    master: Any,
    *,
    scope_binding: ModelScopeBinding,
) -> bool:
    """Lower one typed ``CompiledCut`` onto the master under its resolved scope.

    Returns ``True`` on a successful attach; a master rejection (``False``) or
    any body/binding inconsistency raises (fail-closed).  The caller
    (``lifecycle.step_8_apply_to_master``) has already run the §2.6 three-fold
    binding check; the exact-type gates here are defence in depth.
    """

    if type(compiled_cut) is not CompiledCut:
        raise TypeError("apply_compiled_cut requires an exact CompiledCut")
    if type(scope_binding) is not ModelScopeBinding:
        raise TypeError("apply_compiled_cut requires an exact ModelScopeBinding")

    plan = compiled_cut.plan
    operation = plan.operation
    parameters = plan.parameters
    condition_lits = scope_binding.condition_lits

    # A ghost-bound plan is only true under its triggering anchor; attaching it
    # without the selected ghost literal(s) would over-prune after the solver
    # switches anchors (mirror of the legacy fail-closed ghost guard).
    if plan.model_scope.ghost_policy == "bound" and not condition_lits:
        raise ValueError("apply: ghost-bound plan requires the resolved ghost literal(s) (fail-closed)")

    if operation == "region_capacity_le":
        applied = master.add_region_capacity_cut(
            group_cell_weights=parameters["group_cell_weights"],
            capacity=parameters["capacity"],
            condition_lits=condition_lits,
        )
    elif operation == "shape_packing_hall_le":
        applied = master.add_baseline_packing_cut(
            group_id=parameters["group_id"],
            region_kind=parameters["region_kind"],
            capacity=parameters["capacity"],
            condition_lits=condition_lits,
        )
    elif operation == "power_pose_exclusion":
        blocked_cells = scope_binding.blocked_cells
        if blocked_cells is None:
            raise ValueError("apply: power_pose_exclusion requires resolved blocked_cells (fail-closed)")
        # plan↔body layer (RFC-001 §5.3 拍板 6): the binding body must hash to the
        # digest the F7 plan carries, recomputed here at the apply site.
        if blocked_cells_digest_v1(blocked_cells) != parameters["blocked_cells_digest"]:
            raise ValueError("apply: blocked_cells digest mismatch between plan body and binding (fail-closed)")
        applied = master.add_power_pose_exclusion_cut(
            group_id=parameters["group_id"],
            pose_id=parameters["pose_id"],
            blocked_cells=blocked_cells,
            condition_lits=condition_lits,
        )
    else:  # pragma: no cover - ConstraintPlan enforces the closed operation set
        raise ValueError(f"apply: unsupported operation {operation!r} (fail-closed)")

    if not applied:
        raise RuntimeError("apply: master rejected the typed cut (fail-closed; no partial constraint was attached)")
    return True
