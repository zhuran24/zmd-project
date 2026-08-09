"""F5 pattern_nogood generator + sub-problem oracle adapter contract (P1.2B-F5).

Phase 1.2 P1.2B-F5 scope:
- ``SubProblemOracleAdapter`` Protocol — uniform contract for binding /
  routing / pcr_cut / d2_separator adapters (Phase 1.5+ wires real ones).
- ``_REGISTERED_SUB_PROBLEM_ORACLES`` module-level registry (closed-set).
  Phase 1.2 default empty; tests register fakes via ``register_sub_problem_oracle``.
- ``generate_pattern_nogood_cuts`` — wraps ``deletion_minimize_core`` over an
  adapter's ``query`` method and produces 0 or 1 F5 Cut object.

Fail-closed: any caller-contract violation, registry miss, version mismatch,
or generator-internal exception returns ``[]`` (never partial / unverified cut).

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F5
- docs/项目说明/12_go_criteria.md §8.1.x acceptance A
- docs/research/p3_b_design_v2_20260521/cut_family_specs/05_pattern_nogood.md
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Protocol, Tuple

from src.cuts.helpers.bounded_core_minimizer import (
    CoreMinimizeResult,
    LiteralAssignment,
    MinimizerBudget,
    OracleVerdict,
    canonical_relabel,
    deletion_minimize_core,
)
from src.cuts.lifecycle import (
    AnonymousSlotRef,
    BState,
    Cut,
    CutLiteral,
    CutScope,
    OracleCert,
    compute_blocked_cells_hash,
    compute_exterior_blocks_hash,
    compute_ghost_rect_id,
    compute_source_digest,
)


# ============================================================================
# Module-level constants (F1-F4 oracle 风格一致)
# ============================================================================

ORACLE_NAME: str = "pattern_nogood_v1"
FAMILY_VERSION: str = "v1.0"
VALIDATOR_VERSION: str = "v1.0"
CERT_KIND: str = "bounded_deletion_core"


# ============================================================================
# SubProblemOracleAdapter — Protocol + registry
# ============================================================================


@dataclass(frozen=True)
class LiftableScope:
    """Whitelist projection of BState handed to sub-problem oracle adapters.

    M4-D2 (orbit-lift design v2 §4 ④): an F5 verdict is only liftable if it
    was derived WITHOUT reading incumbent-derived mutable state. The old
    ``query(core, state: BState, ...)`` contract handed adapters the whole
    BState — including ``groups[*].selected_poses`` and ``cell_owner`` — so
    the whitelist was merely verbal. This projection makes it structural:
    the blacklisted fields do not exist on the object an adapter receives.

    Whitelist rationale per field: frozen-artifact snapshots
    (candidate_placements / canonical_rules / facility_templates /
    artifact_hashes), group-structure constants (instance_to_facility_type,
    group_demands, group_pose_domains). Candidate-level constants (ghost,
    exterior) are deliberately NOT included — a verdict depending on them
    must be scope-bound via CutScope, which pattern_nogood does not do.
    """

    facility_pools: Mapping[str, Any]
    canonical_rules: Mapping[str, Any]
    instance_to_facility_type: Mapping[str, str]
    facility_templates: Mapping[str, Any]
    group_demands: Mapping[str, int]
    group_pose_domains: Mapping[str, FrozenSet[str]]
    artifact_hashes: Mapping[str, str]


def build_liftable_scope(state: BState) -> LiftableScope:
    """Project a BState onto the adapter whitelist (drops selected_poses,
    cell_owner, ghost/exterior and every other incumbent-derived field)."""
    placements = state.candidate_placements or {}
    pools = placements.get("facility_pools") if isinstance(placements, dict) else {}
    return LiftableScope(
        facility_pools=pools or {},
        canonical_rules=state.canonical_rules or {},
        instance_to_facility_type=dict(state.instance_to_facility_type or {}),
        facility_templates=state.facility_templates or {},
        group_demands={
            gid: int(group.demand) for gid, group in state.groups.items()
        },
        group_pose_domains={
            gid: frozenset(group.pose_domain) for gid, group in state.groups.items()
        },
        artifact_hashes=dict(state.artifact_hashes or {}),
    )


class SubProblemOracleAdapter(Protocol):
    """Sub-problem oracle adapter contract (M4-D2: liftable form).

    binding_subproblem / routing_subproblem / pcr_cut / d2_separator adapters
    implement this protocol so the F5 generator and validator can re-verify
    via a uniform API. The verdict MUST be a function of (core, whitelisted
    scope) only — the LiftableScope projection structurally withholds
    incumbent state, and an adapter whose verdict would depend on anything
    else must return FEASIBLE/ERROR (refuse to lift) instead.
    """

    name: str  # registry key (e.g. "binding_empty_domain_v1"); validator membership-checks
    version: str  # validator strict-equals at re-verify time

    def query_liftable(
        self,
        core: Tuple[LiteralAssignment, ...],
        scope: LiftableScope,
        *,
        deadline_seconds: float,
    ) -> Tuple[OracleVerdict, Optional[bytes]]:
        """Return (verdict, witness_blob).

        witness_blob may be ``None`` or empty bytes — validator does not bind
        on witness identity (per Gemini F5 round 1 fix #1), only the verdict
        matters. Adapters are not required to extract IIS/Core bytes.
        """
        ...


_REGISTERED_SUB_PROBLEM_ORACLES: Dict[str, SubProblemOracleAdapter] = {}


def register_sub_problem_oracle(adapter: SubProblemOracleAdapter) -> None:
    """Register an adapter under its self-reported name. Idempotent on same name."""
    if not isinstance(adapter.name, str) or not adapter.name:
        raise ValueError(f"adapter.name must be non-empty str, got {adapter.name!r}")
    if not isinstance(adapter.version, str) or not adapter.version:
        raise ValueError(
            f"adapter.version must be non-empty str, got {adapter.version!r}"
        )
    _REGISTERED_SUB_PROBLEM_ORACLES[adapter.name] = adapter


def lookup_sub_problem_oracle(name: str) -> Optional[SubProblemOracleAdapter]:
    """Closed-set lookup. Returns None for unregistered name (caller fail-closed)."""
    return _REGISTERED_SUB_PROBLEM_ORACLES.get(name)


def clear_sub_problem_oracle_registry() -> None:
    """Test-only — reset registry to empty between cases."""
    _REGISTERED_SUB_PROBLEM_ORACLES.clear()


def registered_sub_problem_oracle_names() -> Tuple[str, ...]:
    """Return current registry keys (sorted, for stable test/audit output)."""
    return tuple(sorted(_REGISTERED_SUB_PROBLEM_ORACLES.keys()))


# ============================================================================
# Generator
# ============================================================================


def generate_pattern_nogood_cuts(
    state: BState,
    *,
    sub_problem_oracle: SubProblemOracleAdapter,
    full_assignment_literals: Tuple[CutLiteral, ...],
    budget: MinimizerBudget = MinimizerBudget(),
    iter_index: int = -1,
) -> List[Cut]:
    """Produce 0 or 1 F5 cut from a known-INFEASIBLE sub-problem assignment.

    Fail-closed returns ``[]`` when:
    - sub_problem_oracle.name not in registry, or version mismatch
    - full_assignment_literals empty
    - initial verify of full assignment is not INFEASIBLE
    - any internal exception during cert build

    Caller responsibility (benders_loop / Phase 1.5+):
    - sub_problem_oracle is the same adapter that just returned INFEASIBLE on
      the current master assignment.
    - full_assignment_literals are the literals from the master assignment
      that fed the sub-problem.
    """
    if not full_assignment_literals:
        return []

    registered = lookup_sub_problem_oracle(sub_problem_oracle.name)
    if registered is None or registered.version != sub_problem_oracle.version:
        return []

    assignment_triples: Tuple[LiteralAssignment, ...] = tuple(
        (lit.slot_ref.group_id, lit.slot_ref.slot_index, lit.pose_id)
        for lit in full_assignment_literals
    )

    # Wall-clock tracking for the whole generate call: each adapter.query
    # gets the *remaining* deadline (per Gemini F5 review #4 deadline leak fix),
    # not the full budget. Otherwise multiple oracle calls compound wall time.
    import time as _time

    gen_t0 = _time.monotonic()

    # M4-D2: adapters only ever see the whitelist projection — never the
    # BState with its incumbent-derived fields (selected_poses, cell_owner).
    liftable_scope = build_liftable_scope(state)

    def oracle_cb(core: Tuple[LiteralAssignment, ...]) -> OracleVerdict:
        remaining = budget.max_seconds - (_time.monotonic() - gen_t0)
        if remaining <= 0.0:
            # Budget already exhausted — do not call oracle with a 0.1s floor
            # (per Gemini F5 round 2 review #A: floor causes a "0.1s deadline
            # storm" of guaranteed-TIMEOUT queries near the end of the budget).
            # Returning TIMEOUT lets the minimizer's wall-clock check exit
            # cleanly on the next iteration with stopped_reason=TIMEOUT.
            return "TIMEOUT"
        verdict, _blob = sub_problem_oracle.query_liftable(
            core, liftable_scope, deadline_seconds=remaining
        )
        # witness_blob unused: per Gemini F5 round 1 review #1, sub-problem
        # witness bytes are non-deterministic; validator re-queries oracle for
        # INFEASIBLE confirmation, witness identity is not bound.
        return verdict

    try:
        result = deletion_minimize_core(assignment_triples, oracle_cb, budget)
    except ValueError:
        return []
    except Exception:  # noqa: BLE001 — fail-closed against any adapter bug
        return []

    # M4-D1 (orbit-lift design v2 §4 ②③): the cert carries the CANONICALLY
    # RELABELLED core, and whatever is emitted must itself have been verified
    # INFEASIBLE by the oracle — re-query after relabelling instead of
    # assuming slot-label invariance of the adapter.
    try:
        relabelled_core = canonical_relabel(result.core)
    except ValueError:
        return []
    if _has_duplicate_group_pose(relabelled_core):
        # BLOCK-2: a multiset pattern («two copies of (g, p) needed to be
        # infeasible») cannot be represented faithfully by boolean presence;
        # emitting it would collapse "≥2 copies" into "≥1 copy" (over-prune).
        return []
    if oracle_cb(relabelled_core) != "INFEASIBLE":
        return []

    try:
        cut = _build_pattern_nogood_cut(
            state=state,
            sub_problem_oracle=sub_problem_oracle,
            relabelled_core=relabelled_core,
            result=result,
            iter_index=iter_index,
        )
    except Exception:  # noqa: BLE001 — fail-closed
        return []
    return [cut]


def _has_duplicate_group_pose(core: Tuple[LiteralAssignment, ...]) -> bool:
    pairs = [(g, p) for (g, _s, p) in core]
    return len(set(pairs)) != len(pairs)


def _build_pattern_nogood_cut(
    *,
    state: BState,
    sub_problem_oracle: SubProblemOracleAdapter,
    relabelled_core: Tuple[LiteralAssignment, ...],
    result: CoreMinimizeResult,
    iter_index: int,
) -> Cut:
    """Construct F5 Cut from minimize result.

    Cert payload structure (canonical JSON, sorted keys, only
    deterministic-across-worker fields — per Gemini F5 review #1, sub-problem
    witness bytes are NOT deterministic so are excluded from cert_payload):

        cert_kind: "bounded_deletion_core"
        sub_problem_oracle_name: str (∈ registry)
        sub_problem_oracle_version: str (strict-equals registry value)
        forbidden_pose_pattern: list of [group_id, slot_index, pose_id]
        core_minimization: {size_before, size_after, calls, stopped_reason,
                            is_verified_infeasible}

    Cut top-level fields satisfy R3 ``validate_cut_integrity``:
    - ``cut.cert.cert_hash`` = sha256(cert_payload_bytes)
    - ``cut.oracle_cert_hash`` = cert.cert_hash (R3 invariant).

    Soundness is preserved by the validator's re-query of the oracle on
    ``forbidden_pose_pattern`` — the sub-problem solver must independently
    return INFEASIBLE on the cert literals, regardless of what witness bytes
    it emits.
    """
    # M4-D1: the caller supplies the canonically relabelled, oracle re-verified
    # core; the cert serialises exactly what was verified.
    deduped_core: Tuple[LiteralAssignment, ...] = relabelled_core

    cert_payload_dict: Dict[str, Any] = {
        "cert_kind": CERT_KIND,
        "sub_problem_oracle_name": sub_problem_oracle.name,
        "sub_problem_oracle_version": sub_problem_oracle.version,
        "forbidden_pose_pattern": [[g, s, p] for (g, s, p) in deduped_core],
        "core_minimization": {
            "size_before": int(result.size_before),
            "size_after": int(result.size_after),
            "calls": int(result.calls),
            "stopped_reason": result.stopped_reason.value,
            "is_verified_infeasible": bool(result.is_verified_infeasible),
        },
    }
    cert_payload_bytes = json.dumps(
        cert_payload_dict, sort_keys=True, ensure_ascii=False
    ).encode("utf-8")
    cert_hash = hashlib.sha256(cert_payload_bytes).hexdigest()

    cut_literals: Tuple[CutLiteral, ...] = tuple(
        CutLiteral(
            slot_ref=AnonymousSlotRef(group_id=g, slot_index=s),
            pose_id=p,
        )
        for (g, s, p) in deduped_core
    )

    source_digest = compute_source_digest(state)

    scope = CutScope(
        ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
        blocked_cells_hash=compute_blocked_cells_hash(state),
        exterior_blocks_hash=compute_exterior_blocks_hash(state),
        source_digest=source_digest,
        oracle_abstraction_version=sub_problem_oracle.name,
        artifact_hashes=dict(state.artifact_hashes),
    )

    cut = Cut(
        cut_id=f"f5_{iter_index}_{cert_hash[:12]}",
        family="pattern_nogood",
        literals=cut_literals,
        geometric_payload=None,
        scope=scope,
        cert=OracleCert(
            cert_kind=CERT_KIND,
            cert_payload=cert_payload_bytes,
            cert_hash=cert_hash,
        ),
        family_version=FAMILY_VERSION,
        validator_version=VALIDATOR_VERSION,
        oracle_name=ORACLE_NAME,
        oracle_cert_hash=cert_hash,  # R3 invariant: == cert.cert_hash
        minimization_audit={
            "size_before": int(result.size_before),
            "size_after": int(result.size_after),
            "calls": int(result.calls),
        },
        iter_index=iter_index,
    )
    return cut
