"""Independent proof verifiers for the typed cut platform (RFC-002 family).

Each verifier re-derives a family's window conclusion from frozen-artifact
facts with an algorithm that shares no code path with the generator's oracle /
adapter / registry surface, closing the common-mode failure the plain oracle
re-query leaves open.  Verifiers are TCB: pure, deterministic, env-free and
fail-closed (any derivation failure REFUTES, never silently accepts).
"""
from __future__ import annotations

from src.cuts.verifiers.binding_empty_domain_verifier import (
    BindingDomainUndecidable,
    BindingEmptyDomainVerdict,
    binding_domain_is_empty,
    verify_binding_empty_domain,
)

__all__ = [
    "BindingDomainUndecidable",
    "BindingEmptyDomainVerdict",
    "binding_domain_is_empty",
    "verify_binding_empty_domain",
]
