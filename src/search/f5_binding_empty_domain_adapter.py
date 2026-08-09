"""F5 sub-problem oracle adapter: binding empty-domain check (M4-D2).

The FIRST production adapter behind the F5 query_liftable contract, and the
only binding-derived verdict that is sound to lift (M4-D2 recon, §2):

- ``PortBindingModel`` has exactly two INFEASIBLE modes on the certified
  path. The generic-I/O demand-equality mode is ANTI-MONOTONE — placing more
  facilities adds slots and relaxes the equality — so a subset-INFEASIBLE
  there does NOT imply superset-INFEASIBLE and must never be lifted.
- The empty-binding-domain mode is a pure ``(operation_type, pose)`` property
  derived entirely from frozen artifacts: if the pose-level port-binding
  enumeration is empty, EVERY layout containing that (group, pose) literal
  fails binding. That verdict is layout-independent, slot-label independent
  (σ-relabel invariant by construction) and therefore liftable.

This adapter answers INFEASIBLE iff some core literal names a pose whose
binding domain it can re-derive as empty from the whitelisted scope alone.
Everything else — including genuine demand shortfalls — is answered
FEASIBLE ("no liftable refutation"), which merely produces no cut.

Lives in ``src/search`` (not ``src/cuts``): the adapter needs
``src.models.port_binding``, and ``src/cuts`` stays import-isolated from
``src/models`` by design (MasterModelLike Protocol note in lifecycle).
"""
from __future__ import annotations

import os
from typing import Mapping, Optional, Tuple

from src.cuts.helpers.bounded_core_minimizer import LiteralAssignment, OracleVerdict
from src.cuts.oracles.pattern_nogood_oracle import LiftableScope
from src.models.port_binding import (
    enumerate_pose_level_port_bindings,
    supports_exact_pose_level_binding,
)
from src.preprocess.operation_profiles import get_operation_port_profile

ADAPTER_NAME = "binding_empty_domain_v1"
ADAPTER_VERSION = "v1.0"

# RAB-SEP routing-aware binding filters pose domains by the REST of the
# incumbent layout (front-block) — with it enabled, "domain empty" is no
# longer a pure frozen-artifact property and must not be lifted (recon R3).
_ROUTING_AWARE_BINDING_ENV = "EXACT_B1_ROUTING_AWARE_BINDING"
_FALSE_VALUES = {"", "0", "false", "no", "off"}


class BindingEmptyDomainAdapter:
    """query_liftable implementation for the empty-binding-domain verdict.

    ``group_operation_types`` maps group_id → operation_type; it is group
    structure derived from the frozen mandatory instances (whitelist), and is
    injected at construction because neither BState nor LiftableScope carries
    operation_type (recon R4: group_id is the synthetic
    ``group::{tpl}::{op}::{idx}`` string, NOT the operation_type itself).
    """

    name = ADAPTER_NAME
    version = ADAPTER_VERSION

    def __init__(self, *, group_operation_types: Mapping[str, str]) -> None:
        self._group_operation_types = {
            str(k): str(v) for k, v in group_operation_types.items()
        }

    def query_liftable(
        self,
        core: Tuple[LiteralAssignment, ...],
        scope: LiftableScope,
        *,
        deadline_seconds: float,
    ) -> Tuple[OracleVerdict, Optional[bytes]]:
        del deadline_seconds  # frozen-artifact set lookups; never near a deadline
        if os.environ.get(_ROUTING_AWARE_BINDING_ENV, "").strip().lower() not in (
            _FALSE_VALUES
        ):
            # Domain emptiness would depend on incumbent front-blocks —
            # refuse to lift anything (fail-closed towards "no cut").
            return "FEASIBLE", None
        for group_id, _slot, pose_id in core:
            operation_type = self._group_operation_types.get(str(group_id))
            if operation_type is None:
                continue  # unknown group — cannot re-derive, no verdict from it
            if not supports_exact_pose_level_binding(operation_type):
                # Generic-hub instance: its only failure mode is the
                # anti-monotone demand equality — never liftable (recon R1).
                continue
            facility_type = scope.instance_to_facility_type.get(str(group_id))
            if facility_type is None:
                continue
            pose = self._find_pose(scope, facility_type, str(pose_id))
            if pose is None:
                continue
            # Port-count pre-check: the enumeration RAISES (rather than
            # returning []) when the pose physically has fewer port cells
            # than the profile requires — which is itself a sound liftable
            # refutation (no layout can ever bind this pose). Pre-checking
            # keeps the INFEASIBLE decision off exception semantics.
            try:
                profile = get_operation_port_profile(operation_type)
            except Exception:  # noqa: BLE001 — unknown op → no verdict
                continue
            have_in = len(pose.get("input_port_cells") or [])
            have_out = len(pose.get("output_port_cells") or [])
            need_in = sum(profile.input_slots.values())
            need_out = sum(profile.output_slots.values())
            if have_in < need_in or have_out < need_out:
                return "INFEASIBLE", None
            try:
                domain = enumerate_pose_level_port_bindings(operation_type, pose)
            except Exception:  # noqa: BLE001 — untrusted enumeration input
                continue  # cannot re-derive → contributes no verdict
            if not domain:
                # This literal alone can never bind — any superset layout
                # fails binding. Liftable single-literal refutation.
                return "INFEASIBLE", None
        return "FEASIBLE", None

    @staticmethod
    def _find_pose(
        scope: LiftableScope, facility_type: str, pose_id: str
    ) -> Optional[Mapping[str, object]]:
        pool = scope.facility_pools.get(facility_type)
        if not isinstance(pool, list):
            return None
        for pose in pool:
            if isinstance(pose, Mapping) and str(pose.get("pose_id", "")) == pose_id:
                return pose
        return None


def build_binding_empty_domain_adapter(
    mandatory_groups,
) -> BindingEmptyDomainAdapter:
    """Construct the adapter from master._mandatory_groups records
    (group_id/operation_type are group-structure constants)."""
    mapping = {}
    for group in mandatory_groups or []:
        if not isinstance(group, Mapping):
            continue
        gid = str(group.get("group_id") or "")
        op = str(group.get("operation_type") or "")
        if gid and op:
            mapping[gid] = op
    return BindingEmptyDomainAdapter(group_operation_types=mapping)
