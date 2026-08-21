"""Compatibility facade for the closed-world binding proof capsule.

The implementation lives in ``src.search.independent_binding_reverify``.  This
module preserves the historical import surface used by the Benders controller
without carrying proof semantics of its own.
"""

from __future__ import annotations

from src.search.independent_binding_reverify.api import (
    IndependentInfeasibilityReverificationVerdict,
    STATUS_CONFIRMED_INFEASIBLE,
    STATUS_DIVERGED_FEASIBLE,
    STATUS_EXCEPTION,
    STATUS_TIMEOUT,
    STATUS_UNKNOWN,
    VERIFIER_AUTHORITY,
    VERIFIER_SCHEMA_VERSION,
    reverify_whole_layout_infeasibility,
)

INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION = VERIFIER_SCHEMA_VERSION
INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY = VERIFIER_AUTHORITY
REVERIFY_STATUS_CONFIRMED_INFEASIBLE = STATUS_CONFIRMED_INFEASIBLE
REVERIFY_STATUS_DIVERGED_FEASIBLE = STATUS_DIVERGED_FEASIBLE
REVERIFY_STATUS_TIMEOUT = STATUS_TIMEOUT
REVERIFY_STATUS_EXCEPTION = STATUS_EXCEPTION
REVERIFY_STATUS_UNKNOWN = STATUS_UNKNOWN

__all__ = [
    "INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY",
    "INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION",
    "IndependentInfeasibilityReverificationVerdict",
    "REVERIFY_STATUS_CONFIRMED_INFEASIBLE",
    "REVERIFY_STATUS_DIVERGED_FEASIBLE",
    "REVERIFY_STATUS_EXCEPTION",
    "REVERIFY_STATUS_TIMEOUT",
    "REVERIFY_STATUS_UNKNOWN",
    "reverify_whole_layout_infeasibility",
]
