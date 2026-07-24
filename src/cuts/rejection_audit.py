"""Versioned, audit-only rejection facts for cut research.

This module is intentionally outside the cut authority graph.  A
``RejectionRecordV1`` reuses an existing ``cut_id`` or semantic fingerprint as
its subject; it has no record ID and no field or API that can be attached to,
promote, compile, replay, or apply a cut.  Its hashes are domain-separated
audit-sidecar hashes only.

The active adapter registry names the current stable terminal seams without
resolving or invoking them.  Binding, routing, and power migrations remain
explicitly deferred until each has a parity vector proving zero control-flow
change.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Final, Protocol


_RECORD_AUDIT_PREFIX: Final = b"zmd.rejection-audit.record.v1:"
_INDEX_AUDIT_PREFIX: Final = b"zmd.rejection-audit.index.v1:"
_ASSUMPTION_AUDIT_PREFIX: Final = b"zmd.rejection-audit.assumptions.v1:"


def _require_text(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value or value.strip() != value or "\x00" in value:
        raise ValueError(f"{field_name} must be a non-empty, trimmed exact str without NUL")
    return value


def _require_token(value: object, *, field_name: str) -> str:
    token = _require_text(value, field_name=field_name)
    if not all(character.islower() or character.isdigit() or character in "._-" for character in token):
        raise ValueError(f"{field_name} must contain only lowercase token characters")
    return token


def _require_sha256(value: object, *, field_name: str) -> str:
    if type(value) is not str or len(value) != 64 or value != value.lower():
        raise ValueError(f"{field_name} must be a lowercase 64-hex SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a lowercase 64-hex SHA-256 digest") from exc
    return value


def _audit_digest(prefix: bytes, projection: object) -> str:
    payload = json.dumps(
        projection,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(prefix + payload).hexdigest()


def assumption_audit_digest_v1(
    assumptions: tuple[tuple[str, str], ...],
) -> str:
    """Return the common audit-only digest for a complete assumption multiset.

    The digest is intentionally domain-separated from every authority digest.
    Ordering is canonicalized because scope assumptions are logical premises,
    not an execution sequence.  Duplicate pairs remain represented.
    """

    if type(assumptions) is not tuple:
        raise TypeError("assumption_audit_digest_v1 requires an exact tuple")
    checked: list[tuple[str, str]] = []
    for item in assumptions:
        if type(item) is not tuple or len(item) != 2:
            raise TypeError(
                "assumption_audit_digest_v1 items must be exact (key, value) tuples"
            )
        key, value = item
        _require_text(key, field_name="assumption audit key")
        if type(value) is not str or "\x00" in value:
            raise ValueError("assumption audit value must be an exact str without NUL")
        checked.append((key, value))
    return _audit_digest(_ASSUMPTION_AUDIT_PREFIX, sorted(checked))


class RejectionSubjectKind(Enum):
    CUT_ID = "cut_id"
    SEMANTIC_FINGERPRINT = "semantic_fingerprint"


@dataclass(frozen=True, slots=True)
class RejectionSubjectV1:
    """An existing cut authority key reused by the audit sidecar."""

    kind: RejectionSubjectKind
    value: str

    def __post_init__(self) -> None:
        if type(self.kind) is not RejectionSubjectKind:
            raise TypeError("RejectionSubjectV1.kind must be RejectionSubjectKind")
        if self.kind is RejectionSubjectKind.CUT_ID:
            _require_text(self.value, field_name="RejectionSubjectV1 cut_id")
        else:
            _require_sha256(
                self.value,
                field_name="RejectionSubjectV1 semantic_fingerprint",
            )


class DigestAvailability(Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class AuditDigestEvidenceV1:
    """One honest digest claim: exact SHA-256 or an explicit absence reason."""

    availability: DigestAvailability
    digest: str | None
    unavailable_reason: str | None

    def __post_init__(self) -> None:
        if type(self.availability) is not DigestAvailability:
            raise TypeError("AuditDigestEvidenceV1.availability must be DigestAvailability")
        if self.availability is DigestAvailability.AVAILABLE:
            _require_sha256(self.digest, field_name="AuditDigestEvidenceV1.digest")
            if self.unavailable_reason is not None:
                raise ValueError("available digest cannot carry unavailable_reason")
            return
        if self.digest is not None:
            raise ValueError("unavailable digest cannot carry a digest value")
        _require_text(
            self.unavailable_reason,
            field_name="AuditDigestEvidenceV1.unavailable_reason",
        )

    @classmethod
    def available(cls, digest: str) -> AuditDigestEvidenceV1:
        return cls(
            availability=DigestAvailability.AVAILABLE,
            digest=digest,
            unavailable_reason=None,
        )

    @classmethod
    def unavailable(cls, reason: str) -> AuditDigestEvidenceV1:
        return cls(
            availability=DigestAvailability.UNAVAILABLE,
            digest=None,
            unavailable_reason=reason,
        )

    def audit_projection(self) -> dict[str, object]:
        return {
            "availability": self.availability.value,
            "digest": self.digest,
            "unavailable_reason": self.unavailable_reason,
        }


class PremiseVerdict(Enum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class RejectionPremiseV1:
    """One member of a seam's complete, statically ordered premise vector."""

    premise_id: str
    expected: str
    verdict: PremiseVerdict
    observed: str | None
    unavailable_reason: str | None

    def __post_init__(self) -> None:
        _require_token(self.premise_id, field_name="RejectionPremiseV1.premise_id")
        _require_text(self.expected, field_name="RejectionPremiseV1.expected")
        if type(self.verdict) is not PremiseVerdict:
            raise TypeError("RejectionPremiseV1.verdict must be PremiseVerdict")
        if self.verdict is PremiseVerdict.UNAVAILABLE:
            if self.observed is not None:
                raise ValueError("unavailable premise cannot carry an observed value")
            _require_text(
                self.unavailable_reason,
                field_name="RejectionPremiseV1.unavailable_reason",
            )
            return
        _require_text(self.observed, field_name="RejectionPremiseV1.observed")
        if self.unavailable_reason is not None:
            raise ValueError("evaluated premise cannot carry unavailable_reason")

    def audit_projection(self) -> dict[str, object]:
        return {
            "expected": self.expected,
            "observed": self.observed,
            "premise_id": self.premise_id,
            "unavailable_reason": self.unavailable_reason,
            "verdict": self.verdict.value,
        }


class EvidenceKind(Enum):
    CUT_STORE = "cut_store"
    PROOF = "proof"
    SNAPSHOT = "snapshot"
    LOG = "log"
    ARTIFACT = "artifact"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class EvidenceReferenceV1:
    """An opaque evidence locator; this module deliberately has no resolver."""

    kind: EvidenceKind
    reference: str
    content_digest: AuditDigestEvidenceV1

    def __post_init__(self) -> None:
        if type(self.kind) is not EvidenceKind:
            raise TypeError("EvidenceReferenceV1.kind must be EvidenceKind")
        _require_text(self.reference, field_name="EvidenceReferenceV1.reference")
        if type(self.content_digest) is not AuditDigestEvidenceV1:
            raise TypeError("EvidenceReferenceV1.content_digest must be AuditDigestEvidenceV1")

    def audit_projection(self) -> dict[str, object]:
        return {
            "content_digest": self.content_digest.audit_projection(),
            "kind": self.kind.value,
            "reference": self.reference,
        }


class CostUnit(Enum):
    WALL_TIME_NS = "wall_time_ns"
    CPU_TIME_NS = "cpu_time_ns"
    SOLVER_CALLS = "solver_calls"
    WORK_UNITS = "work_units"


@dataclass(frozen=True, slots=True)
class RejectionCostMeasureV1:
    unit: CostUnit
    value: int

    def __post_init__(self) -> None:
        if type(self.unit) is not CostUnit:
            raise TypeError("RejectionCostMeasureV1.unit must be CostUnit")
        if type(self.value) is not int or self.value < 0:
            raise ValueError("RejectionCostMeasureV1.value must be a non-negative exact int")

    def audit_projection(self) -> dict[str, object]:
        return {"unit": self.unit.value, "value": self.value}


@dataclass(frozen=True, slots=True)
class RejectionCostV1:
    """Measured cost vector, or an explicit reason why no measure exists."""

    measures: tuple[RejectionCostMeasureV1, ...]
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.measures) is not tuple or not all(
            type(item) is RejectionCostMeasureV1 for item in self.measures
        ):
            raise TypeError("RejectionCostV1.measures must be tuple[RejectionCostMeasureV1, ...]")
        units = tuple(item.unit for item in self.measures)
        if len(units) != len(set(units)):
            raise ValueError("RejectionCostV1.measures contains duplicate units")
        if self.measures:
            if self.unavailable_reason is not None:
                raise ValueError("measured cost cannot carry unavailable_reason")
        else:
            _require_text(
                self.unavailable_reason,
                field_name="RejectionCostV1.unavailable_reason",
            )

    def audit_projection(self) -> dict[str, object]:
        return {
            "measures": [item.audit_projection() for item in self.measures],
            "unavailable_reason": self.unavailable_reason,
        }


class RejectionDisposition(Enum):
    REJECTED = "rejected"
    HOLD = "hold"
    QUARANTINE = "quarantine"


class ResponsibilityScope(Enum):
    RULE_REGISTRY = "rule_registry"
    REPRESENTATION = "representation"
    SNAPSHOT_STATE = "snapshot_state"
    PROOF_SEMANTICS = "proof_semantics"
    LOWERING = "lowering"
    LEGACY_VALIDATOR = "legacy_validator"
    CUT_STORE_TRANSITION = "cut_store_transition"
    EXTERNAL_DEPENDENCY = "external_dependency"
    ORCHESTRATION = "orchestration"


@dataclass(frozen=True, slots=True)
class StaticAuditSymbolV1:
    """Static source identity only; intentionally no import or resolver API."""

    module: str
    qualname: str

    def __post_init__(self) -> None:
        module = _require_text(self.module, field_name="StaticAuditSymbolV1.module")
        _require_text(self.qualname, field_name="StaticAuditSymbolV1.qualname")
        if not module.startswith("src."):
            raise ValueError("StaticAuditSymbolV1.module must live below src")
        if "<locals>" in self.qualname or "<lambda>" in self.qualname:
            raise ValueError("StaticAuditSymbolV1.qualname cannot be local or lambda")


@dataclass(frozen=True, slots=True)
class RejectionReasonBindingV1:
    """One stable reason plus its conservative, non-invented premise facts."""

    reason_code: str
    responsibility_scope: ResponsibilityScope
    disposition: RejectionDisposition
    premise_verdicts: tuple[PremiseVerdict, ...]

    def __post_init__(self) -> None:
        _require_token(self.reason_code, field_name="RejectionReasonBindingV1.reason_code")
        if type(self.responsibility_scope) is not ResponsibilityScope:
            raise TypeError(
                "RejectionReasonBindingV1.responsibility_scope must be ResponsibilityScope"
            )
        if type(self.disposition) is not RejectionDisposition:
            raise TypeError("RejectionReasonBindingV1.disposition must be RejectionDisposition")
        if (
            type(self.premise_verdicts) is not tuple
            or not self.premise_verdicts
            or not all(
                type(verdict) is PremiseVerdict
                for verdict in self.premise_verdicts
            )
        ):
            raise TypeError(
                "RejectionReasonBindingV1.premise_verdicts must be a "
                "non-empty tuple[PremiseVerdict, ...]"
            )


@dataclass(frozen=True, slots=True)
class RejectionAdapterSpecV1:
    """Closed audit adapter contract for one already-stable rejection seam.

    Each reason owns an exact verdict vector.  A seam that exposes only a
    terminal stage must use ``UNAVAILABLE`` for ambiguous internal history;
    record producers may not infer a linear trace that the source did not
    expose.
    """

    adapter_id: str
    source: StaticAuditSymbolV1
    reason_bindings: tuple[RejectionReasonBindingV1, ...]
    required_premise_ids: tuple[str, ...]
    audit_only: bool = True

    def __post_init__(self) -> None:
        _require_token(self.adapter_id, field_name="RejectionAdapterSpecV1.adapter_id")
        if type(self.source) is not StaticAuditSymbolV1:
            raise TypeError("RejectionAdapterSpecV1.source must be StaticAuditSymbolV1")
        if type(self.reason_bindings) is not tuple or not self.reason_bindings or not all(
            type(item) is RejectionReasonBindingV1 for item in self.reason_bindings
        ):
            raise TypeError(
                "RejectionAdapterSpecV1.reason_bindings must be a non-empty "
                "tuple[RejectionReasonBindingV1, ...]"
            )
        reason_codes = tuple(item.reason_code for item in self.reason_bindings)
        if len(reason_codes) != len(set(reason_codes)):
            raise ValueError("RejectionAdapterSpecV1.reason_bindings contains duplicate reason codes")
        if type(self.required_premise_ids) is not tuple or not self.required_premise_ids:
            raise TypeError("RejectionAdapterSpecV1.required_premise_ids must be a non-empty tuple")
        for premise_id in self.required_premise_ids:
            _require_token(
                premise_id,
                field_name="RejectionAdapterSpecV1.required_premise_ids item",
            )
        if len(self.required_premise_ids) != len(set(self.required_premise_ids)):
            raise ValueError("RejectionAdapterSpecV1.required_premise_ids contains duplicates")
        for binding in self.reason_bindings:
            if len(binding.premise_verdicts) != len(self.required_premise_ids):
                raise ValueError(
                    "rejection reason premise verdicts must exactly cover the "
                    "adapter premise vector"
                )
            if all(
                verdict is PremiseVerdict.SATISFIED
                for verdict in binding.premise_verdicts
            ):
                raise ValueError(
                    "rejection reason premise verdicts must contain a "
                    "violation or unavailable fact"
                )
        if type(self.audit_only) is not bool or not self.audit_only:
            raise ValueError("RejectionAdapterSpecV1.audit_only must be exact True")

    def reason_binding(self, reason_code: str) -> RejectionReasonBindingV1:
        for binding in self.reason_bindings:
            if binding.reason_code == reason_code:
                return binding
        raise KeyError(
            f"adapter {self.adapter_id!r} has no stable reason code {reason_code!r}"
        )


def _binding(
    reason_code: str,
    scope: ResponsibilityScope,
    disposition: RejectionDisposition,
    premise_verdicts: tuple[PremiseVerdict, ...],
) -> RejectionReasonBindingV1:
    return RejectionReasonBindingV1(
        reason_code=reason_code,
        responsibility_scope=scope,
        disposition=disposition,
        premise_verdicts=premise_verdicts,
    )


_S = PremiseVerdict.SATISFIED
_V = PremiseVerdict.VIOLATED
_U = PremiseVerdict.UNAVAILABLE


_TYPED_PLATFORM_ADAPTER = RejectionAdapterSpecV1(
    adapter_id="typed_platform.cut_rejection.v1",
    source=StaticAuditSymbolV1(
        module="src.cuts.typed_platform",
        qualname="validate_and_compile_cut_audited",
    ),
    reason_bindings=(
        _binding(
            "registry",
            ResponsibilityScope.RULE_REGISTRY,
            RejectionDisposition.REJECTED,
            (_V, _U, _U, _U, _U),
        ),
        _binding(
            "envelope",
            ResponsibilityScope.REPRESENTATION,
            RejectionDisposition.REJECTED,
            (_U, _V, _U, _U, _U),
        ),
        _binding(
            "scope",
            ResponsibilityScope.SNAPSHOT_STATE,
            RejectionDisposition.REJECTED,
            (_U, _S, _V, _U, _U),
        ),
        _binding(
            "proof",
            ResponsibilityScope.PROOF_SEMANTICS,
            RejectionDisposition.REJECTED,
            (_U, _S, _S, _V, _U),
        ),
        _binding(
            "plan",
            ResponsibilityScope.LOWERING,
            RejectionDisposition.REJECTED,
            (_S, _S, _S, _U, _V),
        ),
    ),
    required_premise_ids=(
        "family_registered",
        "schema_version_current",
        "scope_current",
        "proof_sound",
        "plan_sound",
    ),
)

_BENDERS_AUDIT_ADAPTER = RejectionAdapterSpecV1(
    adapter_id="benders.framework_rejection_audit.v1",
    source=StaticAuditSymbolV1(
        module="src.search.benders_loop",
        qualname="LBBDController._maybe_attach_framework_cuts",
    ),
    reason_bindings=(
        _binding(
            "adapter",
            ResponsibilityScope.REPRESENTATION,
            RejectionDisposition.REJECTED,
            (_S, _V, _U, _U, _U, _U, _U, _U, _U),
        ),
        _binding(
            "registry",
            ResponsibilityScope.RULE_REGISTRY,
            RejectionDisposition.REJECTED,
            (_S, _S, _V, _U, _U, _U, _U, _U, _U),
        ),
        _binding(
            "envelope",
            ResponsibilityScope.REPRESENTATION,
            RejectionDisposition.REJECTED,
            (_S, _S, _U, _V, _U, _U, _U, _U, _U),
        ),
        _binding(
            "scope",
            ResponsibilityScope.SNAPSHOT_STATE,
            RejectionDisposition.REJECTED,
            (_S, _S, _U, _S, _V, _U, _U, _U, _U),
        ),
        _binding(
            "proof",
            ResponsibilityScope.PROOF_SEMANTICS,
            RejectionDisposition.REJECTED,
            (_S, _S, _U, _S, _S, _V, _U, _U, _U),
        ),
        _binding(
            "plan",
            ResponsibilityScope.LOWERING,
            RejectionDisposition.REJECTED,
            (_S, _S, _S, _S, _S, _U, _V, _U, _U),
        ),
        _binding(
            "attach_timing",
            ResponsibilityScope.SNAPSHOT_STATE,
            RejectionDisposition.REJECTED,
            (_S, _S, _S, _S, _S, _S, _S, _S, _V),
        ),
        _binding(
            "semantic_duplicate",
            ResponsibilityScope.ORCHESTRATION,
            RejectionDisposition.REJECTED,
            (_S, _S, _S, _S, _S, _S, _S, _V, _U),
        ),
    ),
    required_premise_ids=(
        "cut_generated",
        "adapter_admitted",
        "family_registered",
        "schema_version_current",
        "scope_current",
        "proof_sound",
        "plan_sound",
        "semantic_unique",
        "attach_timing_current",
    ),
)

_REPLAY_ADAPTER = RejectionAdapterSpecV1(
    adapter_id="replay.rejection_outcome.v1",
    source=StaticAuditSymbolV1(
        module="src.cuts.replay",
        qualname="replay_cut_audited",
    ),
    reason_bindings=(
        _binding(
            "cut_integrity_failed",
            ResponsibilityScope.REPRESENTATION,
            RejectionDisposition.QUARANTINE,
            (_S, _V, _U, _U),
        ),
        _binding(
            "typed_adapter_rejected",
            ResponsibilityScope.REPRESENTATION,
            RejectionDisposition.QUARANTINE,
            (_S, _S, _V, _U),
        ),
        _binding(
            "typed_rejected_registry",
            ResponsibilityScope.RULE_REGISTRY,
            RejectionDisposition.QUARANTINE,
            (_S, _S, _S, _V),
        ),
        _binding(
            "typed_rejected_envelope",
            ResponsibilityScope.REPRESENTATION,
            RejectionDisposition.QUARANTINE,
            (_S, _S, _S, _V),
        ),
        _binding(
            "typed_rejected_scope",
            ResponsibilityScope.SNAPSHOT_STATE,
            RejectionDisposition.HOLD,
            (_S, _S, _S, _V),
        ),
        _binding(
            "typed_rejected_proof",
            ResponsibilityScope.PROOF_SEMANTICS,
            RejectionDisposition.QUARANTINE,
            (_S, _S, _S, _V),
        ),
        _binding(
            "typed_rejected_plan",
            ResponsibilityScope.LOWERING,
            RejectionDisposition.QUARANTINE,
            (_S, _S, _S, _V),
        ),
        _binding(
            "legacy_diagnostic_unsound",
            ResponsibilityScope.LEGACY_VALIDATOR,
            RejectionDisposition.QUARANTINE,
            (_S, _S, _U, _V),
        ),
        _binding(
            "legacy_diagnostic_timeout",
            ResponsibilityScope.EXTERNAL_DEPENDENCY,
            RejectionDisposition.QUARANTINE,
            (_S, _S, _U, _V),
        ),
        _binding(
            "legacy_diagnostic_schema_err",
            ResponsibilityScope.REPRESENTATION,
            RejectionDisposition.QUARANTINE,
            (_S, _S, _U, _V),
        ),
        _binding(
            "legacy_diagnostic_error",
            ResponsibilityScope.LEGACY_VALIDATOR,
            RejectionDisposition.QUARANTINE,
            (_S, _S, _U, _V),
        ),
    ),
    required_premise_ids=(
        "cut_registered",
        "cut_integrity",
        "adapter_representation_valid",
        "replay_validation",
    ),
)

# CutStore has a terminal QuarantineReason seam but no structured HOLD reason
# object.  HOLD is therefore represented by the replay adapter's
# ``typed_rejected_scope`` binding; the CutStore adapter below intentionally
# covers only actual ``quarantine_cut`` transitions.
_CUT_STORE_ADAPTER = RejectionAdapterSpecV1(
    adapter_id="cut_store.quarantine_transition.v1",
    source=StaticAuditSymbolV1(
        module="src.cuts.store",
        qualname="CutStore.quarantine_cut_audited",
    ),
    reason_bindings=tuple(
        _binding(
            binding.reason_code,
            binding.responsibility_scope,
            RejectionDisposition.QUARANTINE,
            (_S, _S, _U),
        )
        for binding in _REPLAY_ADAPTER.reason_bindings
        if binding.disposition is RejectionDisposition.QUARANTINE
    )
    + (
        _binding(
            "ghost_transition_replay",
            ResponsibilityScope.CUT_STORE_TRANSITION,
            RejectionDisposition.QUARANTINE,
            (_S, _S, _U),
        ),
    ),
    required_premise_ids=(
        "cut_registered",
        "terminal_reason_stable",
        "transition_authorized",
    ),
)


REJECTION_ADAPTER_SPECS_V1: Final[Mapping[str, RejectionAdapterSpecV1]] = MappingProxyType(
    {
        _TYPED_PLATFORM_ADAPTER.adapter_id: _TYPED_PLATFORM_ADAPTER,
        _BENDERS_AUDIT_ADAPTER.adapter_id: _BENDERS_AUDIT_ADAPTER,
        _REPLAY_ADAPTER.adapter_id: _REPLAY_ADAPTER,
        _CUT_STORE_ADAPTER.adapter_id: _CUT_STORE_ADAPTER,
    }
)

STABLE_REJECTION_REASON_CODES_V1: Final = frozenset(
    binding.reason_code
    for adapter in REJECTION_ADAPTER_SPECS_V1.values()
    for binding in adapter.reason_bindings
)


@dataclass(frozen=True, slots=True)
class DeferredRejectionMigrationV1:
    """A lower-layer migration that is deliberately not active in this batch."""

    migration_id: str
    subsystem: str
    source_modules: tuple[str, ...]
    prerequisite: str
    parity_vector_required: bool = True
    audit_only_required: bool = True
    authority_change_forbidden: bool = True

    def __post_init__(self) -> None:
        _require_token(self.migration_id, field_name="DeferredRejectionMigrationV1.migration_id")
        _require_token(self.subsystem, field_name="DeferredRejectionMigrationV1.subsystem")
        if type(self.source_modules) is not tuple or not self.source_modules:
            raise TypeError("DeferredRejectionMigrationV1.source_modules must be a non-empty tuple")
        for module in self.source_modules:
            checked = _require_text(
                module,
                field_name="DeferredRejectionMigrationV1.source_modules item",
            )
            if not checked.startswith("src."):
                raise ValueError("deferred rejection source modules must live below src")
        if len(self.source_modules) != len(set(self.source_modules)):
            raise ValueError("DeferredRejectionMigrationV1.source_modules contains duplicates")
        _require_text(self.prerequisite, field_name="DeferredRejectionMigrationV1.prerequisite")
        for field_name in (
            "parity_vector_required",
            "audit_only_required",
            "authority_change_forbidden",
        ):
            if type(getattr(self, field_name)) is not bool or not getattr(self, field_name):
                raise ValueError(f"DeferredRejectionMigrationV1.{field_name} must be exact True")


DEFERRED_REJECTION_MIGRATIONS_V1: Final = (
    DeferredRejectionMigrationV1(
        migration_id="binding.failures.v1",
        subsystem="binding",
        source_modules=(
            "src.models.binding_subproblem",
            "src.models.port_binding",
        ),
        prerequisite=(
            "Add only after a pure-audit parity vector covers every selected stable "
            "terminal reason without changing binding control flow."
        ),
    ),
    DeferredRejectionMigrationV1(
        migration_id="routing.failures.v1",
        subsystem="routing",
        source_modules=(
            "src.models.routing_subproblem",
            "src.models.patch_routing_core",
        ),
        prerequisite=(
            "Add only after terminal routing reasons are stabilized and a pure-audit "
            "parity vector proves identical routing outputs and failure ordering."
        ),
    ),
    DeferredRejectionMigrationV1(
        migration_id="power.failures.v1",
        subsystem="power",
        source_modules=(
            "src.models.power_placement_subproblem",
            "src.models.scip_power_separator",
        ),
        prerequisite=(
            "Add only after power failure ownership is sealed and a pure-audit "
            "parity vector proves identical solver inputs, outputs, and hashes."
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class RejectionRecordV1:
    """Immutable structured failure fact; never a trusted-cut credential."""

    subject: RejectionSubjectV1
    adapter_id: str
    family: str
    reason_code: str
    reason_detail: str
    responsibility_scope: ResponsibilityScope
    disposition: RejectionDisposition
    premises: tuple[RejectionPremiseV1, ...]
    instance_digest: AuditDigestEvidenceV1
    state_digest: AuditDigestEvidenceV1
    assumption_digest: AuditDigestEvidenceV1
    evidence_references: tuple[EvidenceReferenceV1, ...]
    cost: RejectionCostV1
    schema_version: int = field(default=1, init=False)
    audit_record_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.subject) is not RejectionSubjectV1:
            raise TypeError("RejectionRecordV1.subject must be RejectionSubjectV1")
        adapter_id = _require_token(self.adapter_id, field_name="RejectionRecordV1.adapter_id")
        try:
            adapter = REJECTION_ADAPTER_SPECS_V1[adapter_id]
        except KeyError as exc:
            raise ValueError(f"unknown rejection adapter {adapter_id!r}") from exc
        _require_token(self.family, field_name="RejectionRecordV1.family")
        reason_code = _require_token(
            self.reason_code,
            field_name="RejectionRecordV1.reason_code",
        )
        try:
            binding = adapter.reason_binding(reason_code)
        except KeyError as exc:
            raise ValueError(str(exc)) from exc
        _require_text(self.reason_detail, field_name="RejectionRecordV1.reason_detail")
        if type(self.responsibility_scope) is not ResponsibilityScope:
            raise TypeError("RejectionRecordV1.responsibility_scope must be ResponsibilityScope")
        if self.responsibility_scope is not binding.responsibility_scope:
            raise ValueError("rejection responsibility scope contradicts the adapter reason binding")
        if type(self.disposition) is not RejectionDisposition:
            raise TypeError("RejectionRecordV1.disposition must be RejectionDisposition")
        if self.disposition is not binding.disposition:
            raise ValueError("rejection disposition contradicts the adapter reason binding")
        if type(self.premises) is not tuple or not self.premises or not all(
            type(item) is RejectionPremiseV1 for item in self.premises
        ):
            raise TypeError(
                "RejectionRecordV1.premises must be a non-empty tuple[RejectionPremiseV1, ...]"
            )
        premise_ids = tuple(item.premise_id for item in self.premises)
        if premise_ids != adapter.required_premise_ids:
            raise ValueError(
                "rejection premises must exactly match the adapter's complete ordered premise vector"
            )
        if all(item.verdict is PremiseVerdict.SATISFIED for item in self.premises):
            raise ValueError("rejection record must contain a violated or unavailable premise")
        if tuple(item.verdict for item in self.premises) != binding.premise_verdicts:
            raise ValueError(
                "rejection premise verdicts contradict the adapter reason binding"
            )
        for field_name in (
            "instance_digest",
            "state_digest",
            "assumption_digest",
        ):
            if type(getattr(self, field_name)) is not AuditDigestEvidenceV1:
                raise TypeError(f"RejectionRecordV1.{field_name} must be AuditDigestEvidenceV1")
        if type(self.evidence_references) is not tuple or not self.evidence_references or not all(
            type(item) is EvidenceReferenceV1 for item in self.evidence_references
        ):
            raise TypeError(
                "RejectionRecordV1.evidence_references must be a non-empty "
                "tuple[EvidenceReferenceV1, ...]"
            )
        evidence_keys = tuple(
            (item.kind, item.reference) for item in self.evidence_references
        )
        if len(evidence_keys) != len(set(evidence_keys)):
            raise ValueError("RejectionRecordV1.evidence_references contains duplicates")
        if type(self.cost) is not RejectionCostV1:
            raise TypeError("RejectionRecordV1.cost must be RejectionCostV1")
        object.__setattr__(
            self,
            "audit_record_digest",
            _audit_digest(_RECORD_AUDIT_PREFIX, self.audit_projection()),
        )

    def audit_projection(self) -> dict[str, object]:
        """Canonical audit projection; never an authority digest projection."""

        return {
            "adapter_id": self.adapter_id,
            "assumption_digest": self.assumption_digest.audit_projection(),
            "cost": self.cost.audit_projection(),
            "disposition": self.disposition.value,
            "evidence_references": [
                item.audit_projection() for item in self.evidence_references
            ],
            "family": self.family,
            "instance_digest": self.instance_digest.audit_projection(),
            "premises": [item.audit_projection() for item in self.premises],
            "reason_code": self.reason_code,
            "reason_detail": self.reason_detail,
            "responsibility_scope": self.responsibility_scope.value,
            "schema_version": self.schema_version,
            "state_digest": self.state_digest.audit_projection(),
            "subject": {
                "kind": self.subject.kind.value,
                "value": self.subject.value,
            },
        }


def rejection_record_ledger_projection_v1(
    record: RejectionRecordV1,
) -> dict[str, object]:
    """Serialize a record for a non-authoritative ledger index.

    ``audit_projection`` excludes its own digest to keep hashing acyclic.  A
    ledger entry carries that digest alongside the projection so readers can
    validate the sidecar without treating it as an authority credential.
    """

    if type(record) is not RejectionRecordV1:
        raise TypeError(
            "rejection_record_ledger_projection_v1 requires an exact "
            "RejectionRecordV1"
        )
    projection = record.audit_projection()
    projection["audit_record_digest"] = record.audit_record_digest
    return projection


class AuditEmitStatus(Enum):
    APPENDED = "appended"
    DUPLICATE = "duplicate"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AuditEmitOutcomeV1:
    status: AuditEmitStatus
    audit_record_digest: str
    index_audit_digest: str | None
    detail: str = ""

    def __post_init__(self) -> None:
        if type(self.status) is not AuditEmitStatus:
            raise TypeError("AuditEmitOutcomeV1.status must be AuditEmitStatus")
        _require_sha256(
            self.audit_record_digest,
            field_name="AuditEmitOutcomeV1.audit_record_digest",
        )
        if self.status is AuditEmitStatus.FAILED:
            if self.index_audit_digest is not None:
                raise ValueError("failed audit outcome cannot claim an index audit digest")
            _require_text(self.detail, field_name="AuditEmitOutcomeV1.detail")
            return
        _require_sha256(
            self.index_audit_digest,
            field_name="AuditEmitOutcomeV1.index_audit_digest",
        )
        if self.detail:
            raise ValueError("successful audit outcome cannot carry failure detail")


class RejectionAuditSinkV1(Protocol):
    def emit(self, record: RejectionRecordV1) -> AuditEmitOutcomeV1: ...


class RejectionAuditIndexV1:
    """In-memory append-only audit index keyed only by existing cut subjects."""

    __slots__ = ("_by_subject", "_record_digests", "_records")

    def __init__(self) -> None:
        self._records: list[RejectionRecordV1] = []
        self._record_digests: set[str] = set()
        self._by_subject: dict[RejectionSubjectV1, list[RejectionRecordV1]] = {}

    @property
    def records(self) -> tuple[RejectionRecordV1, ...]:
        return tuple(self._records)

    @property
    def index_audit_digest(self) -> str:
        return _audit_digest(
            _INDEX_AUDIT_PREFIX,
            {
                "record_digests": [
                    record.audit_record_digest for record in self._records
                ],
                "schema_version": 1,
            },
        )

    def records_for(
        self,
        subject: RejectionSubjectV1,
    ) -> tuple[RejectionRecordV1, ...]:
        if type(subject) is not RejectionSubjectV1:
            raise TypeError("audit index subject must be an exact RejectionSubjectV1")
        return tuple(self._by_subject.get(subject, ()))

    def emit(self, record: RejectionRecordV1) -> AuditEmitOutcomeV1:
        if type(record) is not RejectionRecordV1:
            raise TypeError("audit index accepts only exact RejectionRecordV1")
        if record.audit_record_digest in self._record_digests:
            return AuditEmitOutcomeV1(
                status=AuditEmitStatus.DUPLICATE,
                audit_record_digest=record.audit_record_digest,
                index_audit_digest=self.index_audit_digest,
            )
        self._records.append(record)
        self._record_digests.add(record.audit_record_digest)
        self._by_subject.setdefault(record.subject, []).append(record)
        return AuditEmitOutcomeV1(
            status=AuditEmitStatus.APPENDED,
            audit_record_digest=record.audit_record_digest,
            index_audit_digest=self.index_audit_digest,
        )


def emit_rejection_audit(
    record: RejectionRecordV1,
    sink: RejectionAuditSinkV1,
) -> AuditEmitOutcomeV1:
    """Best-effort audit emission that never changes the caller's cut decision."""

    if type(record) is not RejectionRecordV1:
        raise TypeError("emit_rejection_audit requires an exact RejectionRecordV1")
    try:
        emit = getattr(sink, "emit")
        if not callable(emit):
            raise TypeError("audit sink lacks callable emit")
        outcome = emit(record)
        if type(outcome) is not AuditEmitOutcomeV1:
            raise TypeError("audit sink returned a non-AuditEmitOutcomeV1")
        if outcome.audit_record_digest != record.audit_record_digest:
            raise ValueError("audit sink outcome refers to a different rejection record")
        return outcome
    except Exception as exc:  # Audit transport cannot alter cut control flow.
        try:
            detail = str(exc).replace("\x00", "\\x00").strip()
        except Exception:
            detail = type(exc).__name__
        if not detail:
            detail = type(exc).__name__
        return AuditEmitOutcomeV1(
            status=AuditEmitStatus.FAILED,
            audit_record_digest=record.audit_record_digest,
            index_audit_digest=None,
            detail=detail,
        )


__all__ = [
    "AuditDigestEvidenceV1",
    "AuditEmitOutcomeV1",
    "AuditEmitStatus",
    "CostUnit",
    "DEFERRED_REJECTION_MIGRATIONS_V1",
    "DeferredRejectionMigrationV1",
    "DigestAvailability",
    "EvidenceKind",
    "EvidenceReferenceV1",
    "PremiseVerdict",
    "REJECTION_ADAPTER_SPECS_V1",
    "RejectionAdapterSpecV1",
    "RejectionAuditIndexV1",
    "RejectionAuditSinkV1",
    "RejectionCostMeasureV1",
    "RejectionCostV1",
    "RejectionDisposition",
    "RejectionPremiseV1",
    "RejectionReasonBindingV1",
    "RejectionRecordV1",
    "RejectionSubjectKind",
    "RejectionSubjectV1",
    "ResponsibilityScope",
    "STABLE_REJECTION_REASON_CODES_V1",
    "StaticAuditSymbolV1",
    "assumption_audit_digest_v1",
    "emit_rejection_audit",
    "rejection_record_ledger_projection_v1",
]
