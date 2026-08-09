"""Attach spike E2' harness: prod-scale C1 master + direct Step 8 load.

This is a research-only, non-certifying harness.  It deliberately does not use
the production ``EXACT_CUT_FRAMEWORK_ATTACH`` gate and never writes campaign,
checkpoint, hint-persistence, or strong-status artifacts.

The only implemented workload is ``f5-overlap``.  Each cut forbids two
different mandatory groups from occupying the same real pose.  The master
already enforces NoOverlap2D, so these are content-distinct but redundant valid
inequalities: they exercise F5 lowering/proto/solve cost without changing the
feasible set.

Current production code has a fail-closed seam: lifecycle Step 8 permits a
GHOST_AGNOSTIC F5 cut and forwards empty condition_lits, while the coordinate
delegate rejects empty condition_lits.  This harness alone wraps the master and
replaces that empty sequence with one shared BoolVar fixed to true.  Therefore
the measured F5 constraint has one extra ``OnlyEnforceIf(const_true)`` layer
relative to a future native unconditional lowering.  The shim is forbidden in
production and exists only for this spike.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping, Sequence
from unittest import mock


PROJECT_ROOT = Path("/home/zhuran24/zmd-pj")
DEFAULT_OUT = Path("/home/zhuran24/m5_runs/spike_e2_result.json")
FORBIDDEN_ENV_NAMES = (
    "EXACT_CUT_FRAMEWORK_ATTACH",
    "EXACT_F7_GENERATOR_ENABLED",
    "EXACT_USE_POSE_BOOL_MASTER",
    "EXACT_MASTER_HINT_PERSISTENCE",
)
WORKLOAD_NAME = "f5-overlap"
F5_ADAPTER_NAME = "e2_static_pose_overlap_v1"
F5_ADAPTER_VERSION = "v1.0"
HARNESS_SHIM_NAME = "f5_empty_condition_to_const_true"
TARGET_TEMPLATE = "manufacturing_3x3"


def _sanitize_environment() -> dict[str, bool]:
    """Remove the four forbidden knobs before importing any project module."""

    for name in FORBIDDEN_ENV_NAMES:
        os.environ.pop(name, None)
    assertions = {name: name not in os.environ for name in FORBIDDEN_ENV_NAMES}
    if not all(assertions.values()):
        raise AssertionError(f"forbidden environment cleanup failed: {assertions}")
    # Match the direct-build skeleton while allowing the formal runner to
    # provide its own fifth-knife value.
    os.environ.setdefault("EXACT_MASTER_CP_SAT_WORKERS", "6")
    return assertions


ENV_ASSERTIONS = _sanitize_environment()
sys.path.insert(0, str(PROJECT_ROOT))


@dataclass(frozen=True)
class PreparedF5OverlapWorkload:
    """Keep the proof state, shared scope, and cuts in one immutable bundle.

    A future ghost-bound workload must expand this bundle atomically with
    ``(rect_idx, domain, u_var)``.  Those values must never be looked up or
    passed separately from the state/cuts they condition.  This workload is
    GHOST_AGNOSTIC, so there is intentionally no ghost tuple to carry.
    """

    state: Any
    shared_scope: Any
    cuts: tuple[Any, ...]
    adapter: Any
    metadata: Mapping[str, Any]


class StaticPoseOverlapAdapter:
    """Harness-local liftable oracle for static occupied-cell overlap.

    The verdict uses only fields exposed through LiftableScope.  Pose indices
    are cached per frozen artifact map/template so 10K validator replays do not
    repeatedly scan the 44 MiB placement artifact.
    """

    name = F5_ADAPTER_NAME
    version = F5_ADAPTER_VERSION

    def __init__(self) -> None:
        self._pose_cells_cache: dict[
            tuple[int, tuple[tuple[str, str], ...], str],
            dict[str, frozenset[tuple[int, int]]],
        ] = {}

    @staticmethod
    def _artifact_key(scope: Any) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted((str(key), str(value)) for key, value in scope.artifact_hashes.items())
        )

    def _pose_cells(
        self,
        scope: Any,
        group_id: str,
        pose_id: str,
    ) -> frozenset[tuple[int, int]] | None:
        facility_type = scope.instance_to_facility_type.get(str(group_id))
        if not isinstance(facility_type, str) or not facility_type:
            return None
        cache_key = (
            id(scope.facility_pools),
            self._artifact_key(scope),
            facility_type,
        )
        pose_map = self._pose_cells_cache.get(cache_key)
        if pose_map is None:
            raw_pool = scope.facility_pools.get(facility_type)
            if not isinstance(raw_pool, list):
                return None
            pose_map = {}
            for raw_pose in raw_pool:
                if not isinstance(raw_pose, Mapping):
                    return None
                raw_pose_id = raw_pose.get("pose_id")
                occupied = raw_pose.get("occupied_cells")
                if not isinstance(raw_pose_id, str) or not raw_pose_id:
                    return None
                if raw_pose_id in pose_map or not isinstance(occupied, list) or not occupied:
                    return None
                cells: set[tuple[int, int]] = set()
                for raw_cell in occupied:
                    if (
                        not isinstance(raw_cell, list)
                        or len(raw_cell) != 2
                        or isinstance(raw_cell[0], bool)
                        or not isinstance(raw_cell[0], int)
                        or isinstance(raw_cell[1], bool)
                        or not isinstance(raw_cell[1], int)
                    ):
                        return None
                    cells.add((int(raw_cell[0]), int(raw_cell[1])))
                pose_map[raw_pose_id] = frozenset(cells)
            self._pose_cells_cache[cache_key] = pose_map
        return pose_map.get(str(pose_id))

    def query_liftable(
        self,
        core: tuple[tuple[str, int, str], ...],
        scope: Any,
        *,
        deadline_seconds: float,
    ) -> tuple[str, bytes | None]:
        del deadline_seconds  # frozen-map lookups only
        if len(core) < 2:
            return "FEASIBLE", None
        for left, right in combinations(core, 2):
            left_group, _left_slot, left_pose = left
            right_group, _right_slot, right_pose = right
            if left_group == right_group:
                continue
            left_cells = self._pose_cells(scope, left_group, left_pose)
            right_cells = self._pose_cells(scope, right_group, right_pose)
            if left_cells is None or right_cells is None:
                return "UNKNOWN", None
            if not left_cells.isdisjoint(right_cells):
                return "INFEASIBLE", None
        return "FEASIBLE", None


class F5EmptyConditionToConstTrueShim:
    """Harness-only bridge for the agnostic-F5 lifecycle/delegate seam.

    All attributes and the other three Step-8 family methods fall through to
    the real MasterPlacementModel.  Only F5's empty condition is adapted, using
    one shared literal fixed true on the real CpModel.  The real coordinate
    delegate still performs pose resolution, alias checks, presence-literal
    construction, constraint insertion, telemetry, and witness invalidation.
    """

    def __init__(self, master: Any) -> None:
        self._master = master
        self._delegate = getattr(master, "_coordinate_delegate", None)
        if self._delegate is None:
            raise RuntimeError("F5 harness shim requires the coordinate delegate")
        self._const_true = master.model.NewBoolVar("e2_harness_f5_const_true")
        master.model.Add(self._const_true == 1)

    @property
    def const_true_name(self) -> str:
        return str(self._const_true.Name())

    def add_pattern_nogood_cut(
        self,
        *,
        pattern: Sequence[tuple[str, str]],
        condition_lits: Sequence[Any],
    ) -> bool:
        conditions = tuple(condition_lits)
        if not conditions:
            conditions = (self._const_true,)
        return bool(
            self._delegate.add_pattern_nogood_cut(
                pattern=pattern,
                condition_lits=conditions,
            )
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._master, name)


def _build_static_framework_state(master: Any, session: Any) -> tuple[Any, Any, str]:
    """Assemble a ghost-agnostic BState from the production master materials."""

    from src.cuts.lifecycle import (
        GHOST_AGNOSTIC,
        BState,
        CutScope,
        GroupState,
        compute_blocked_cells_hash,
        compute_exterior_blocks_hash,
        compute_ghost_rect_id,
        compute_source_digest,
    )
    from src.search.orbit_homogeneity import (
        ORBIT_HOMOGENEITY_DIGEST_KEY,
        compute_orbit_homogeneity_digest,
    )

    mandatory_groups = getattr(master, "_mandatory_groups", None)
    facility_pools = getattr(master, "facility_pools", None)
    templates = getattr(master, "templates", None)
    rules = getattr(master, "rules", None)
    if not mandatory_groups or not facility_pools or not templates or rules is None:
        raise RuntimeError("master is missing cut-framework state materials")

    pose_domains: dict[str, frozenset[str]] = {}
    groups: dict[str, Any] = {}
    instance_to_facility_type: dict[str, str] = {}
    for raw_group in mandatory_groups:
        if not isinstance(raw_group, Mapping):
            raise RuntimeError("master._mandatory_groups contains a non-mapping")
        group_id = str(raw_group.get("group_id") or "")
        facility_type = str(raw_group.get("facility_type") or "")
        count = int(raw_group.get("count", 0))
        raw_pool = facility_pools.get(facility_type)
        if not group_id or not facility_type or count <= 0 or not isinstance(raw_pool, list):
            raise RuntimeError(f"malformed mandatory group: {raw_group!r}")
        if facility_type not in pose_domains:
            pose_domains[facility_type] = frozenset(
                str(pose.get("pose_id"))
                for pose in raw_pool
                if isinstance(pose, Mapping) and pose.get("pose_id")
            )
        pose_domain = pose_domains[facility_type]
        if not pose_domain:
            raise RuntimeError(f"empty pose domain for mandatory group {group_id!r}")
        groups[group_id] = GroupState(
            group_id=group_id,
            demand=count,
            pose_domain=pose_domain,
            selected_poses=[],
        )
        instance_to_facility_type[group_id] = facility_type

    # Digest ordering is proof-bearing: finish the full artifact map, including
    # P-HOM, before BState and the shared CutScope snapshot are constructed.
    homogeneity_digest = compute_orbit_homogeneity_digest(
        getattr(master, "source_instances", None) or [],
        facility_pools,
    )
    if homogeneity_digest is None:
        raise RuntimeError("P-HOM failed: refusing to construct F5 workload")
    artifact_hashes = dict(session.artifact_hashes)
    artifact_hashes[ORBIT_HOMOGENEITY_DIGEST_KEY] = homogeneity_digest
    final_artifact_hashes = dict(artifact_hashes)

    state = BState(
        groups=groups,
        cell_owner={},
        ghost_rect=None,
        ghost_cells=frozenset(),
        exterior_blocks=frozenset(),
        artifact_hashes=final_artifact_hashes,
        available_oracle_versions=frozenset(
            {
                "region_capacity_v1",
                "power_cover_v2_stencil",
                "shape_packing_hall_v1",
                "binding_empty_domain_v1",
                F5_ADAPTER_NAME,
            }
        ),
        canonical_rules=rules,
        instance_to_facility_type=instance_to_facility_type,
        facility_templates=templates,
        candidate_placements={"facility_pools": facility_pools},
    )
    source_digest = compute_source_digest(state)
    state.source_digest = source_digest
    if compute_ghost_rect_id(state.ghost_rect) != GHOST_AGNOSTIC:
        raise AssertionError("static F5 state is not ghost-agnostic")

    shared_scope = CutScope(
        ghost_rect_id=GHOST_AGNOSTIC,
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=compute_exterior_blocks_hash(state),
        source_digest=source_digest,
        artifact_hashes=dict(state.artifact_hashes),
        oracle_abstraction_version=F5_ADAPTER_NAME,
        active_assumptions=(),
    )
    return state, shared_scope, source_digest


def _eligible_group_pairs(master: Any) -> tuple[tuple[str, str], ...]:
    groups = sorted(
        str(group["group_id"])
        for group in master._mandatory_groups
        if str(group.get("facility_type", "")) == TARGET_TEMPLATE
    )
    if len(groups) < 2:
        raise RuntimeError(
            f"{TARGET_TEMPLATE!r} has {len(groups)} mandatory groups; need at least 2"
        )
    return tuple(combinations(groups, 2))


def _unique_delegate_pose_ids(master: Any) -> tuple[str, ...]:
    delegate = master._coordinate_delegate
    tuple_by_idx = getattr(delegate, "_template_pose_tuple_by_idx", {}).get(
        TARGET_TEMPLATE,
        {},
    )
    pool = master.facility_pools.get(TARGET_TEMPLATE)
    if not isinstance(tuple_by_idx, Mapping) or not tuple_by_idx or not isinstance(pool, list):
        raise RuntimeError(f"delegate has no pose tuple map for {TARGET_TEMPLATE!r}")

    seen_tuples: set[tuple[int, int, int]] = set()
    seen_pose_ids: set[str] = set()
    pose_ids: list[str] = []
    for raw_idx, raw_tuple in sorted(tuple_by_idx.items(), key=lambda item: int(item[0])):
        pose_idx = int(raw_idx)
        if not (0 <= pose_idx < len(pool)):
            raise RuntimeError(f"delegate pose index out of range: {pose_idx}")
        pose_tuple = tuple(int(value) for value in raw_tuple)
        if len(pose_tuple) != 3:
            raise RuntimeError(f"delegate pose tuple malformed: {raw_tuple!r}")
        if pose_tuple in seen_tuples:
            continue
        seen_tuples.add(pose_tuple)
        pose_id = str(pool[pose_idx].get("pose_id") or "")
        if not pose_id or pose_id in seen_pose_ids:
            raise RuntimeError(f"missing or duplicate pose_id at index {pose_idx}: {pose_id!r}")
        seen_pose_ids.add(pose_id)
        pose_ids.append(pose_id)
    if not pose_ids:
        raise RuntimeError(f"no unique delegate poses for {TARGET_TEMPLATE!r}")
    return tuple(pose_ids)


def _build_f5_overlap_cut(
    *,
    cut_index: int,
    pattern: tuple[tuple[str, int, str], ...],
    state: Any,
    shared_scope: Any,
    adapter: StaticPoseOverlapAdapter,
    liftable_scope: Any,
) -> Any:
    from src.cuts.helpers.bounded_core_minimizer import (
        MinimizerBudget,
        canonical_relabel,
        deletion_minimize_core,
    )
    from src.cuts.lifecycle import (
        AnonymousSlotRef,
        Cut,
        CutLiteral,
        OracleCert,
        canonical_bytes_for_cert,
    )

    def oracle(core: tuple[tuple[str, int, str], ...]) -> str:
        verdict, _witness = adapter.query_liftable(
            core,
            liftable_scope,
            deadline_seconds=1.0,
        )
        return verdict

    minimized = deletion_minimize_core(
        pattern,
        oracle,
        MinimizerBudget(max_calls=8, max_seconds=1.0),
    )
    relabelled = canonical_relabel(minimized.core)
    if relabelled != pattern or not minimized.is_minimal:
        raise RuntimeError(
            f"static overlap core did not remain a minimal pair: "
            f"input={pattern!r}, result={relabelled!r}, minimal={minimized.is_minimal}"
        )

    cert_dict = {
        "cert_kind": "bounded_deletion_core",
        "sub_problem_oracle_name": adapter.name,
        "sub_problem_oracle_version": adapter.version,
        "forbidden_pose_pattern": [list(item) for item in relabelled],
        "core_minimization": {
            "size_before": int(minimized.size_before),
            "size_after": int(minimized.size_after),
            "calls": int(minimized.calls),
            "stopped_reason": minimized.stopped_reason.value,
            "is_verified_infeasible": bool(minimized.is_verified_infeasible),
        },
    }
    payload = canonical_bytes_for_cert(cert_dict)
    cert_hash = hashlib.sha256(payload).hexdigest()
    literals = tuple(
        CutLiteral(
            slot_ref=AnonymousSlotRef(group_id=group_id, slot_index=slot_index),
            pose_id=pose_id,
        )
        for group_id, slot_index, pose_id in relabelled
    )
    return Cut(
        cut_id=f"e2_f5_overlap_{cut_index:06d}_{cert_hash[:12]}",
        family="pattern_nogood",
        literals=literals,
        geometric_payload=None,
        scope=shared_scope,
        cert=OracleCert(
            cert_kind="bounded_deletion_core",
            cert_payload=payload,
            cert_hash=cert_hash,
        ),
        family_version="v1.0",
        validator_version="v1.0",
        payload_schema_version=1,
        oracle_name="pattern_nogood_v1",
        oracle_cert_hash=cert_hash,
        minimization_audit={
            "size_before": int(minimized.size_before),
            "size_after": int(minimized.size_after),
            "calls": int(minimized.calls),
        },
        iter_index=cut_index,
    )


def _prepare_f5_overlap_workload(master: Any, session: Any, n_cuts: int) -> PreparedF5OverlapWorkload:
    from src.cuts.oracles.pattern_nogood_oracle import (
        build_liftable_scope,
        lookup_sub_problem_oracle,
        register_sub_problem_oracle,
    )

    state, shared_scope, source_digest = _build_static_framework_state(master, session)
    adapter = StaticPoseOverlapAdapter()
    if lookup_sub_problem_oracle(adapter.name) is not None:
        raise RuntimeError(f"F5 adapter name already registered: {adapter.name!r}")
    register_sub_problem_oracle(adapter)
    if lookup_sub_problem_oracle(adapter.name) is not adapter:
        raise AssertionError("F5 adapter registry did not retain the harness adapter")

    group_pairs = _eligible_group_pairs(master)
    pose_ids = _unique_delegate_pose_ids(master)
    capacity = len(group_pairs) * len(pose_ids)
    if n_cuts > capacity:
        raise ValueError(
            f"requested {n_cuts} F5 overlap cuts but deterministic capacity is {capacity} "
            f"({len(group_pairs)} group pairs × {len(pose_ids)} unique poses)"
        )

    liftable_scope = build_liftable_scope(state)
    cuts: list[Any] = []
    used_pairs: set[tuple[str, str]] = set()
    used_pose_ids: set[str] = set()
    # Pose-major order deliberately exposes the same content-addressed presence
    # literals to all group pairs before moving to the next pose.  This exercises
    # the reuse landed for M3-2 instead of manufacturing 10K disjoint helper sets.
    for pose_id in pose_ids:
        for group_left, group_right in group_pairs:
            pattern = (
                (group_left, 0, pose_id),
                (group_right, 0, pose_id),
            )
            cut = _build_f5_overlap_cut(
                cut_index=len(cuts),
                pattern=pattern,
                state=state,
                shared_scope=shared_scope,
                adapter=adapter,
                liftable_scope=liftable_scope,
            )
            cuts.append(cut)
            used_pairs.add((group_left, group_right))
            used_pose_ids.add(pose_id)
            if len(cuts) == n_cuts:
                break
        if len(cuts) == n_cuts:
            break
    if len(cuts) != n_cuts:
        raise AssertionError(f"constructed {len(cuts)} cuts; requested {n_cuts}")
    if any(cut.scope is not shared_scope for cut in cuts):
        raise AssertionError("F5 overlap cuts do not share the precomputed CutScope")

    return PreparedF5OverlapWorkload(
        state=state,
        shared_scope=shared_scope,
        cuts=tuple(cuts),
        adapter=adapter,
        metadata={
            "template": TARGET_TEMPLATE,
            "mandatory_group_count": len(
                {
                    group_id
                    for pair in group_pairs
                    for group_id in pair
                }
            ),
            "group_pair_count_available": len(group_pairs),
            "group_pair_count_used": len(used_pairs),
            "unique_delegate_pose_count_available": len(pose_ids),
            "unique_pose_count_used": len(used_pose_ids),
            "workload_capacity": capacity,
            "source_digest": source_digest,
            "artifact_hash_count": len(state.artifact_hashes),
            "shared_scope": True,
            "ghost_rect_id": str(shared_scope.ghost_rect_id),
        },
    )


def _prevalidate_f5_overlap(prepared: PreparedF5OverlapWorkload) -> dict[str, Any]:
    import src.cuts.lifecycle as lifecycle
    from src.cuts.replay import FAMILY_VALIDATORS

    if not prepared.cuts:
        return {
            "integrity_ok": 0,
            "validator_ok": 0,
            "scope_ok": 0,
            "full_scope_recompute_decision": "NOT_RUN",
            "cached_source_digest_rechecks": 0,
        }
    validator = FAMILY_VALIDATORS.get("pattern_nogood")
    if validator is None:
        raise RuntimeError("pattern_nogood family validator is not registered")

    state = prepared.state
    expected_source_digest = str(prepared.shared_scope.source_digest)
    # Step 6 intentionally recomputes the 44 MiB source payload every call.  All
    # 10K cuts here share one immutable state/scope, so perform one unpatched
    # production recomputation, then memoize only that same-state digest while
    # still invoking the real step_6_attach_scope_check for every cut.
    full_decision = lifecycle.step_6_attach_scope_check(prepared.cuts[0], state)
    if full_decision != "ATTACH":
        raise RuntimeError(f"full Step-6 scope recompute failed: {full_decision}")
    original_compute_source_digest = lifecycle.compute_source_digest

    def cached_compute_source_digest(current_state: Any) -> str:
        if current_state is state:
            return expected_source_digest
        return original_compute_source_digest(current_state)

    integrity_ok = 0
    validator_ok = 0
    scope_ok = 0
    with mock.patch.object(
        lifecycle,
        "compute_source_digest",
        side_effect=cached_compute_source_digest,
    ):
        for index, cut in enumerate(prepared.cuts):
            integrity_error = lifecycle.validate_cut_integrity(cut)
            if integrity_error is not None:
                raise RuntimeError(
                    f"cut[{index}] integrity failed: {integrity_error}"
                )
            integrity_ok += 1

            validation = validator(cut, state, state.canonical_rules or {})
            if getattr(validation, "kind", None) != "ok":
                raise RuntimeError(
                    f"cut[{index}] F5 validator failed: "
                    f"kind={getattr(validation, 'kind', None)!r}, "
                    f"detail={getattr(validation, 'detail', None)!r}"
                )
            validator_ok += 1

            decision = lifecycle.step_6_attach_scope_check(cut, state)
            if decision != "ATTACH":
                raise RuntimeError(f"cut[{index}] Step-6 decision={decision!r}")
            scope_ok += 1

    expected = len(prepared.cuts)
    if (integrity_ok, validator_ok, scope_ok) != (expected, expected, expected):
        raise AssertionError(
            "prevalidation count mismatch: "
            f"integrity={integrity_ok}, validator={validator_ok}, scope={scope_ok}, "
            f"expected={expected}"
        )
    return {
        "integrity_ok": integrity_ok,
        "validator_ok": validator_ok,
        "scope_ok": scope_ok,
        "full_scope_recompute_decision": full_decision,
        "cached_source_digest_rechecks": scope_ok,
    }


def _proto_counts(master: Any) -> dict[str, int]:
    proto = master.model.Proto()
    return {
        "variables": len(proto.variables),
        "constraints": len(proto.constraints),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P1.3A E2' direct Step-8 attach spike harness",
    )
    parser.add_argument("--cuts", type=int, default=0, help="number of cuts; 0 is baseline")
    parser.add_argument(
        "--workload",
        choices=(WORKLOAD_NAME,),
        default=WORKLOAD_NAME,
    )
    parser.add_argument("--solve-limit", type=float, default=1800.0, help="CP-SAT seconds")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="result JSON path")
    parser.add_argument(
        "--ghost", type=int, nargs=2, default=(6, 6), metavar=("W", "H"),
        help="ghost rect (w h); default 6 6 = spike baseline shape",
    )
    args = parser.parse_args()
    if args.cuts < 0:
        parser.error("--cuts must be non-negative")
    if args.solve_limit <= 0.0:
        parser.error("--solve-limit must be positive")
    return args


def main() -> int:
    from src.cuts.lifecycle import step_8_apply_to_master
    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import ExactSearchSession

    args = _parse_args()
    result: dict[str, Any] = {
        "n_cuts_requested": int(args.cuts),
        "workload": str(args.workload),
        "solve_limit_seconds": float(args.solve_limit),
        "harness_shim": HARNESS_SHIM_NAME,
        "harness_shim_active": False,
        "forbidden_env_absent": dict(ENV_ASSERTIONS),
        "n_cuts_attached": 0,
        "cut_generation_seconds": 0.0,
        "prevalidate_seconds": 0.0,
        "attach_seconds": 0.0,
    }

    session = ExactSearchSession.create(PROJECT_ROOT, solve_mode="certified_exact")
    print("session ready", flush=True)

    core_started = time.perf_counter()
    core = MasterPlacementModel.build_exact_core(
        session.instances,
        session.facility_pools,
        session.rules,
        generic_io_requirements=session.core.generic_io_requirements,
        wireless_sink_generic_input_slots=session.core.wireless_sink_generic_input_slots,
    )
    result["core_build_seconds"] = round(time.perf_counter() - core_started, 3)

    master_started = time.perf_counter()
    master = MasterPlacementModel.from_exact_core(core, ghost_rect=tuple(args.ghost))
    if not getattr(master, "_built", False):
        master.build()
    result["master_build_seconds"] = round(time.perf_counter() - master_started, 3)
    print(
        f"built: core={result['core_build_seconds']}s "
        f"master={result['master_build_seconds']}s",
        flush=True,
    )

    delegate = getattr(master, "_coordinate_delegate", None)
    master_assertions = {
        "exact_mode": master.exact_mode is True,
        "coordinate_delegate_present": delegate is not None,
        "coordinate_representation_v2": (
            getattr(delegate, "master_representation", None) == "coordinate_exact_v2"
        ),
        "c1_power_pole_representation": (
            getattr(delegate, "c1_power_pole_representation", None) is True
        ),
        "hint_persistence_context_unset": (
            getattr(master, "_hint_persistence_context", None) is None
        ),
    }
    if not all(master_assertions.values()):
        raise AssertionError(f"master pre-attach assertions failed: {master_assertions}")
    result["master_assertions"] = master_assertions

    framework_count_before = int(
        master.build_stats.get("coordinate_framework_cut_count", 0)
    )
    proto_before = _proto_counts(master)
    result["framework_cut_count_before"] = framework_count_before
    result["proto_before_attach"] = proto_before

    prepared: PreparedF5OverlapWorkload | None = None
    shim: F5EmptyConditionToConstTrueShim | None = None
    prevalidation = {
        "integrity_ok": 0,
        "validator_ok": 0,
        "scope_ok": 0,
        "full_scope_recompute_decision": "NOT_RUN",
        "cached_source_digest_rechecks": 0,
    }
    if args.cuts > 0:
        generation_started = time.perf_counter()
        prepared = _prepare_f5_overlap_workload(master, session, int(args.cuts))
        result["cut_generation_seconds"] = round(
            time.perf_counter() - generation_started,
            6,
        )
        result["workload_metadata"] = dict(prepared.metadata)

        prevalidate_started = time.perf_counter()
        prevalidation = _prevalidate_f5_overlap(prepared)
        result["prevalidate_seconds"] = round(
            time.perf_counter() - prevalidate_started,
            6,
        )
        print(
            "PREVALIDATE: "
            f"{prevalidation['integrity_ok']}/{args.cuts} integrity, "
            f"{prevalidation['validator_ok']}/{args.cuts} validator, "
            f"{prevalidation['scope_ok']}/{args.cuts} scope, "
            f"{result['prevalidate_seconds']}s",
            flush=True,
        )

        # Shim construction is outside the attach timer.  All cuts share this
        # one const-true literal; there is no per-cut harness-side definition.
        shim = F5EmptyConditionToConstTrueShim(master)
        result["harness_shim_active"] = True
        result["harness_shim_const_true_literal"] = shim.const_true_name
        result["proto_after_shim_init"] = _proto_counts(master)

        attach_started = time.perf_counter()
        for cut in prepared.cuts:
            step_8_apply_to_master(cut, shim)
        result["attach_seconds"] = round(time.perf_counter() - attach_started, 6)
        result["n_cuts_attached"] = len(prepared.cuts)
        print(
            f"ATTACH: {result['n_cuts_attached']} cuts in "
            f"{result['attach_seconds']}s",
            flush=True,
        )
    else:
        result["workload_metadata"] = None
        result["proto_after_shim_init"] = dict(proto_before)

    result["prevalidation"] = prevalidation
    framework_count_after = int(
        master.build_stats.get("coordinate_framework_cut_count", 0)
    )
    framework_delta = framework_count_after - framework_count_before
    framework_assertion = framework_delta == int(args.cuts)
    if not framework_assertion:
        raise AssertionError(
            f"coordinate_framework_cut_count delta={framework_delta}, "
            f"expected={args.cuts}"
        )
    result["framework_cut_count_after"] = framework_count_after
    result["framework_cut_count_delta"] = framework_delta
    result["framework_cut_count_delta_assertion"] = framework_assertion
    result["n_cuts_attached_assertion"] = (
        int(result["n_cuts_attached"]) == int(args.cuts)
    )
    if not result["n_cuts_attached_assertion"]:
        raise AssertionError(
            f"attached={result['n_cuts_attached']}, requested={args.cuts}"
        )
    result["proto_after_attach"] = _proto_counts(master)
    result["proto_constraint_delta"] = (
        result["proto_after_attach"]["constraints"]
        - result["proto_before_attach"]["constraints"]
    )

    solve_started = time.perf_counter()
    master.solve(
        time_limit_seconds=float(args.solve_limit),
        solution_hint=None,
        known_feasible_hint=False,
    )
    solve_stats = dict(master.build_stats.get("last_solve", {}))
    result["solve"] = {
        "status": str(solve_stats.get("status")),
        "wall": round(time.perf_counter() - solve_started, 3),
        "branches": solve_stats.get("branches"),
        "conflicts": solve_stats.get("conflicts"),
        "deterministic_time": solve_stats.get("deterministic_time"),
    }
    print(f"SOLVE: {result['solve']}", flush=True)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    print(f"E2_HARNESS_DONE out={out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
