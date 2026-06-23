"""Independent phase-1 re-verifier for whole-layout INFEASIBLE nogoods.

Existence (∃ witness) can be rechecked cheaply by finding another witness.
Non-existence (∀ = INFEASIBLE) is different: sound confirmation requires
another complete solver to independently conclude INFEASIBLE for the same
feasibility question. This module is therefore not a FIX-1-style lightweight
witness finder. It rebuilds a fresh feasibility subproblem and solves it with
an independent, heterogeneous CP-SAT solver profile.

NAMED-TCB: The negative proof boundary here is CP-SAT's infeasibility result on
a freshly built subproblem, plus the binding/routing model constructors imported
below. The caller's live master, live solver, in-flight caches, and previous
subproblem objects are not proof authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ortools.sat.python import cp_model

from src.models.binding_subproblem import PortBindingModel


INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION = 1
INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY = (
    "independent_whole_layout_infeasibility_reverifier_v1"
)

REVERIFY_STATUS_CONFIRMED_INFEASIBLE = "CONFIRMED_INFEASIBLE"
REVERIFY_STATUS_DIVERGED_FEASIBLE = "DIVERGED_FEASIBLE"
REVERIFY_STATUS_TIMEOUT = "TIMEOUT"
REVERIFY_STATUS_EXCEPTION = "EXCEPTION"
REVERIFY_STATUS_UNKNOWN = "UNKNOWN"

_BINDING_REVERIFY_RANDOM_SEED = 8675309
_BINDING_REVERIFY_WORKERS = 2
_DEFAULT_REVERIFY_SECONDS = 600.0


@dataclass(frozen=True)
class IndependentInfeasibilityReverificationVerdict:
    schema_version: int
    authority: str
    confirmed: bool
    status: str
    stage: str
    reason: str
    independent_status: Optional[str] = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "authority": str(self.authority),
            "confirmed": bool(self.confirmed),
            "status": str(self.status),
            "stage": str(self.stage),
            "reason": str(self.reason),
            "independent_status": (
                None if self.independent_status is None else str(self.independent_status)
            ),
            "details": dict(self.details),
        }


def reverify_whole_layout_infeasibility(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    instances: Sequence[Mapping[str, Any]],
    project_root: Path,
    proof_stage: str,
    binding_exhausted: bool,
    routing_exhausted: bool,
    binding_kwargs: Optional[Mapping[str, Any]] = None,
    time_limit_seconds: float = _DEFAULT_REVERIFY_SECONDS,
) -> IndependentInfeasibilityReverificationVerdict:
    """Fail-closed re-verification for a pending whole-layout nogood.

    Phase 1 deliberately confirms only the binding-INFEASIBLE case. Routing
    exhaustion requires proving every binding/routing alternative infeasible;
    this conservative implementation declines to mint that proof unless the
    independently rebuilt binding model is itself already INFEASIBLE. Legal
    routing-exhausted cuts may therefore be skipped and the candidate may remain
    open/UNKNOWN. That is an intentional soundness tradeoff, not a completeness
    bug.
    """

    try:
        if not binding_exhausted:
            return _unknown(
                stage=proof_stage,
                reason="binding_exhaustion_required_for_whole_layout_reverify",
            )
        binding_verdict = _reverify_binding_infeasible(
            solution=solution,
            facility_pools=facility_pools,
            instances=instances,
            project_root=project_root,
            binding_kwargs=binding_kwargs,
            time_limit_seconds=time_limit_seconds,
        )
        if not routing_exhausted:
            return binding_verdict
        if binding_verdict.confirmed:
            return IndependentInfeasibilityReverificationVerdict(
                schema_version=INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION,
                authority=INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY,
                confirmed=True,
                status=REVERIFY_STATUS_CONFIRMED_INFEASIBLE,
                stage=str(proof_stage),
                reason="routing_exhaustion_reverified_by_binding_infeasible",
                independent_status=binding_verdict.independent_status,
                details={
                    **dict(binding_verdict.details),
                    "routing_phase1_policy": "confirmed_only_when_binding_is_independently_infeasible",
                },
            )
        return _unknown(
            stage=proof_stage,
            reason="routing_exhaustion_phase1_conservative_unknown",
            independent_status=binding_verdict.independent_status,
            details={
                "binding_reverification": binding_verdict.to_dict(),
                "routing_phase1_policy": (
                    "no routing ALL-INFEASIBLE cut without an independent full "
                    "exhaustion proof"
                ),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return IndependentInfeasibilityReverificationVerdict(
            schema_version=INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION,
            authority=INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY,
            confirmed=False,
            status=REVERIFY_STATUS_EXCEPTION,
            stage=str(proof_stage),
            reason="independent_infeasibility_reverify_exception",
            details={"exception_type": type(exc).__name__, "message": str(exc)},
        )


def _reverify_binding_infeasible(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    instances: Sequence[Mapping[str, Any]],
    project_root: Path,
    binding_kwargs: Optional[Mapping[str, Any]],
    time_limit_seconds: float,
) -> IndependentInfeasibilityReverificationVerdict:
    binding_model = PortBindingModel(
        placement_solution=solution,
        facility_pools={
            str(template): [dict(pose) for pose in poses]
            for template, poses in facility_pools.items()
        },
        instances=[dict(instance) for instance in instances],
        project_root=project_root,
        **dict(binding_kwargs or {}),
    )
    binding_model.build()
    binding_summary = binding_model.extract_conflict_summary()
    invalid_reasons = list(binding_summary.get("invalid_binding_input_reasons", []) or [])
    if invalid_reasons:
        return _unknown(
            stage="binding",
            reason="independent_binding_input_invalid",
            details={
                "invalid_binding_input_reasons": invalid_reasons,
                "binding_summary": binding_summary,
            },
        )

    status_name, stats = _solve_with_independent_cp_sat(
        binding_model.model,
        time_limit_seconds=time_limit_seconds,
    )
    details = {
        "binding_summary": binding_summary,
        "solver_stats": stats,
    }
    if status_name == "INFEASIBLE":
        return IndependentInfeasibilityReverificationVerdict(
            schema_version=INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION,
            authority=INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY,
            confirmed=True,
            status=REVERIFY_STATUS_CONFIRMED_INFEASIBLE,
            stage="binding",
            reason="independent_binding_solver_confirmed_infeasible",
            independent_status=status_name,
            details=details,
        )
    if status_name in {"OPTIMAL", "FEASIBLE"}:
        return IndependentInfeasibilityReverificationVerdict(
            schema_version=INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION,
            authority=INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY,
            confirmed=False,
            status=REVERIFY_STATUS_DIVERGED_FEASIBLE,
            stage="binding",
            reason="independent_binding_solver_found_feasible",
            independent_status="FEASIBLE",
            details=details,
        )
    return IndependentInfeasibilityReverificationVerdict(
        schema_version=INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION,
        authority=INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY,
        confirmed=False,
        status=REVERIFY_STATUS_TIMEOUT,
        stage="binding",
        reason="independent_binding_solver_uncertain",
        independent_status=status_name,
        details=details,
    )


def _solve_with_independent_cp_sat(
    model: cp_model.CpModel,
    *,
    time_limit_seconds: float,
) -> Tuple[str, Dict[str, Any]]:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.001, float(time_limit_seconds))
    # Heterogeneous profile versus the production binding solve:
    # production uses FIXED_SEARCH and env-resolved workers; this verifier uses
    # a new solver object with portfolio search, randomization, and a hard-coded
    # worker/seed profile. These parameters are deliberately not EXACT_* knobs.
    solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
    solver.parameters.random_seed = _BINDING_REVERIFY_RANDOM_SEED
    solver.parameters.randomize_search = True
    solver.parameters.num_search_workers = _BINDING_REVERIFY_WORKERS
    status = solver.Solve(model)
    status_name = str(solver.StatusName(status))
    return status_name, {
        "status": status_name,
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "search_branching": "PORTFOLIO_SEARCH",
        "random_seed": _BINDING_REVERIFY_RANDOM_SEED,
        "randomize_search": True,
        "num_search_workers": _BINDING_REVERIFY_WORKERS,
    }


def _unknown(
    *,
    stage: str,
    reason: str,
    independent_status: Optional[str] = None,
    details: Optional[Mapping[str, Any]] = None,
) -> IndependentInfeasibilityReverificationVerdict:
    return IndependentInfeasibilityReverificationVerdict(
        schema_version=INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION,
        authority=INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY,
        confirmed=False,
        status=REVERIFY_STATUS_UNKNOWN,
        stage=str(stage),
        reason=str(reason),
        independent_status=independent_status,
        details=dict(details or {}),
    )
