"""CP-SAT worker configuration helpers.

Defaults:
- master: 8
- local_capacity: 8
- binding: 4
- routing: 8

Precedence:
1. stage-specific env, e.g. EXACT_MASTER_CP_SAT_WORKERS
2. global EXACT_CP_SAT_WORKERS
3. built-in defaults
"""

from __future__ import annotations

import os
from typing import Any, Dict, Tuple

DEFAULT_MASTER_CP_SAT_WORKERS = 8
DEFAULT_LOCAL_CAPACITY_CP_SAT_WORKERS = 8
DEFAULT_BINDING_CP_SAT_WORKERS = 4
DEFAULT_ROUTING_CP_SAT_WORKERS = 8

_GLOBAL_WORKER_ENV = "EXACT_CP_SAT_WORKERS"
_STAGE_ENV_NAMES = {
    "master": "EXACT_MASTER_CP_SAT_WORKERS",
    "local_capacity": "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS",
    "binding": "EXACT_BINDING_CP_SAT_WORKERS",
    "routing": "EXACT_ROUTING_CP_SAT_WORKERS",
}


def _parse_worker_value(raw_value: str, *, env_name: str) -> int:
    try:
        worker_count = int(str(raw_value).strip())
    except Exception as exc:  # pragma: no cover - defensive parsing branch.
        raise ValueError(f"{env_name} must be an integer worker count") from exc
    if worker_count <= 0:
        raise ValueError(f"{env_name} must be >= 1")
    return int(worker_count)


def resolve_cp_sat_worker_count(*, env_name: str, default: int) -> int:
    worker_count, _resolved_from = _resolve_cp_sat_worker_count_with_source(
        env_name=env_name,
        default=default,
    )
    return worker_count


def _resolve_cp_sat_worker_count_with_source(*, env_name: str, default: int) -> Tuple[int, str]:
    raw_value = os.getenv(env_name)
    resolved_from = env_name
    if raw_value is None or not str(raw_value).strip():
        raw_value = os.getenv(_GLOBAL_WORKER_ENV)
        resolved_from = _GLOBAL_WORKER_ENV
    if raw_value is None or not str(raw_value).strip():
        return int(default), "default"
    return _parse_worker_value(str(raw_value), env_name=resolved_from), resolved_from


def resolve_exact_cp_sat_worker_profile() -> Dict[str, int]:
    return {
        "master": resolve_cp_sat_worker_count(
            env_name="EXACT_MASTER_CP_SAT_WORKERS",
            default=DEFAULT_MASTER_CP_SAT_WORKERS,
        ),
        "local_capacity": resolve_cp_sat_worker_count(
            env_name="EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS",
            default=DEFAULT_LOCAL_CAPACITY_CP_SAT_WORKERS,
        ),
        "binding": resolve_cp_sat_worker_count(
            env_name="EXACT_BINDING_CP_SAT_WORKERS",
            default=DEFAULT_BINDING_CP_SAT_WORKERS,
        ),
        "routing": resolve_cp_sat_worker_count(
            env_name="EXACT_ROUTING_CP_SAT_WORKERS",
            default=DEFAULT_ROUTING_CP_SAT_WORKERS,
        ),
    }


def resolve_exact_cp_sat_worker_profile_details() -> Dict[str, Dict[str, Any]]:
    defaults = {
        "master": DEFAULT_MASTER_CP_SAT_WORKERS,
        "local_capacity": DEFAULT_LOCAL_CAPACITY_CP_SAT_WORKERS,
        "binding": DEFAULT_BINDING_CP_SAT_WORKERS,
        "routing": DEFAULT_ROUTING_CP_SAT_WORKERS,
    }
    details: Dict[str, Dict[str, Any]] = {}
    for stage, env_name in _STAGE_ENV_NAMES.items():
        worker_count, source = _resolve_cp_sat_worker_count_with_source(
            env_name=env_name,
            default=defaults[stage],
        )
        details[stage] = {
            "workers": int(worker_count),
            "source": source,
            "default": int(defaults[stage]),
            "env_name": env_name,
            "global_env_name": _GLOBAL_WORKER_ENV,
        }
    return details


def format_exact_cp_sat_worker_profile(
    profile_details: Dict[str, Dict[str, Any]] | None = None,
) -> str:
    details = profile_details or resolve_exact_cp_sat_worker_profile_details()
    ordered_stages = ("master", "local_capacity", "binding", "routing")
    formatted = []
    for stage in ordered_stages:
        stage_details = details[stage]
        formatted.append(f"{stage}={stage_details['workers']}[{stage_details['source']}]")
    return "resolved_cp_sat_worker_profile: " + ", ".join(formatted)


# Phase 3C P0 #3 (UNSAT subsolver portfolio, R12-revised conservative variant).
# These LNS subsolvers are unhelpful for max_lex(area, min_side) optimization
# in CP-SAT 9.15 — they target feasibility/MaxSAT scenarios that don't apply
# to our master placement model. Verified against ortools/sat/cp_model_search.cc.
# See docs/research/agent_transcripts/a55a893f5ab38c083.output for full audit.
MASTER_IGNORE_SUBSOLVERS_FOR_MAX_LEX = (
    "rins",
    "rens",
    "graph_arc_lns",
    "graph_cst_lns",
    "feasibility_pump",
    "violation_ls",
)


def apply_master_cp_sat_subsolver_filter(solver) -> Tuple[str, ...]:
    """Apply Phase 3C P0 #3 conservative subsolver filter to a master CpSolver.

    Only sets ignore_subsolvers (always-safe LNS exclusion); does NOT set
    explicit subsolvers list, since CP-SAT search_branching=FIXED interaction
    with explicit subsolvers is unverified for our portfolio configuration.

    Returns the tuple of ignored subsolver names (for logging).
    """
    for name in MASTER_IGNORE_SUBSOLVERS_FOR_MAX_LEX:
        solver.parameters.ignore_subsolvers.append(name)
    return MASTER_IGNORE_SUBSOLVERS_FOR_MAX_LEX
