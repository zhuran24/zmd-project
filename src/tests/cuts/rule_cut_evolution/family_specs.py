"""Static shadow manifest for the existing cut-family wiring.

The manifest is intentionally outside production and stores identities only.
It is a migration gate: tests compare these rows with independently observed
hard-coded production behavior, but production never imports or consumes the
rows.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final, Generic, Mapping, TypeVar, cast

from src.tests.cuts.rule_cut_evolution.rule_semantics import (
    SHADOW_RULE_SEMANTICS_V1,
    RuleDeploymentState,
    RuleSemanticRegistry,
    StaticSymbolIdentity,
    VersionedRuleRef,
)


_T = TypeVar("_T")
_AUDIT_PREFIX: Final = b"zmd.test-shadow.family-specs.v1:"


def _text(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{field_name} must be a non-empty trimmed exact str")
    return value


def _token(value: object, *, field_name: str) -> str:
    token = _text(value, field_name=field_name)
    if not all(character.islower() or character.isdigit() or character in "._-" for character in token):
        raise ValueError(f"{field_name} must be a stable lower-case token")
    return token


@dataclass(frozen=True, slots=True)
class StaticSlot(Generic[_T]):
    """Exactly one of an identity/data value or an explicit absence reason."""

    value: _T | None
    unavailable_reason: str | None

    def __post_init__(self) -> None:
        if (self.value is None) == (self.unavailable_reason is None):
            raise ValueError("StaticSlot requires exactly one of value/unavailable_reason")
        if self.unavailable_reason is not None:
            _token(self.unavailable_reason, field_name="StaticSlot.unavailable_reason")

    @property
    def is_available(self) -> bool:
        return self.value is not None


def available(value: _T) -> StaticSlot[_T]:
    return StaticSlot(value=value, unavailable_reason=None)


def unavailable(reason: str) -> StaticSlot[_T]:
    return StaticSlot(value=None, unavailable_reason=reason)


class FamilyMode(Enum):
    LITERAL = "literal"
    GEOMETRIC = "geometric"


class CapabilityStage(Enum):
    EXPERIMENTAL = "experimental"
    VALIDATED = "validated"
    COMPILABLE = "compilable"
    ENABLED = "enabled"
    RETIRED = "retired"


class ExecutionPath(Enum):
    TYPED = "TYPED"
    LEGACY_DIAGNOSTIC = "LEGACY_DIAGNOSTIC"


class LifecycleStage(Enum):
    EXPERIMENTAL = "experimental"
    LEGACY_HOLD = "legacy_hold"
    TYPED_SHADOW = "typed_shadow"
    TYPED_COMPILED = "typed_compiled"
    TYPED_ENABLED = "typed_enabled"
    RETIRED = "retired"


class TelemetryProfile(Enum):
    EXPERIMENTAL = "experimental"
    LEGACY_DIAGNOSTIC = "legacy_diagnostic"
    TYPED_SHADOW = "typed_shadow"
    TYPED_COMPILED = "typed_compiled"
    TYPED_ENABLED = "typed_enabled"
    RETIRED = "retired"


class PluginProviderKind(Enum):
    FACTORY = "factory"
    INSTANCE = "instance"


class ReplayKind(Enum):
    TYPED_SINGLE_ENTRY = "typed_single_entry"
    LEGACY_DIAGNOSTIC = "legacy_diagnostic"


class GenerationSurface(Enum):
    EXPERIMENTAL = "experimental"
    TYPED_ATTACH = "typed_attach"
    LEGACY_DIAGNOSTIC = "legacy_diagnostic"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    family: str
    mode: FamilyMode
    proof_schema_version: int
    validator_version: str
    compiler_version: str | None
    stage: CapabilityStage
    required_dependencies: frozenset[str]
    execution_path: ExecutionPath
    requires_ghost_bound: bool

    def __post_init__(self) -> None:
        _token(self.family, field_name="CapabilitySpec.family")
        if type(self.mode) is not FamilyMode:
            raise TypeError("CapabilitySpec.mode must be FamilyMode")
        if type(self.proof_schema_version) is not int or self.proof_schema_version <= 0:
            raise ValueError("proof_schema_version must be a positive exact int")
        _text(self.validator_version, field_name="CapabilitySpec.validator_version")
        if self.compiler_version is not None:
            _text(self.compiler_version, field_name="CapabilitySpec.compiler_version")
        if type(self.stage) is not CapabilityStage:
            raise TypeError("CapabilitySpec.stage must be CapabilityStage")
        if type(self.required_dependencies) is not frozenset or not self.required_dependencies:
            raise TypeError("required_dependencies must be a non-empty exact frozenset")
        for dependency in self.required_dependencies:
            _token(dependency, field_name="CapabilitySpec.required_dependencies")
        if type(self.execution_path) is not ExecutionPath:
            raise TypeError("CapabilitySpec.execution_path must be ExecutionPath")
        if type(self.requires_ghost_bound) is not bool:
            raise TypeError("requires_ghost_bound must be an exact bool")
        if self.stage in {CapabilityStage.COMPILABLE, CapabilityStage.ENABLED}:
            if self.execution_path is not ExecutionPath.TYPED or self.compiler_version is None:
                raise ValueError("compilable/enabled family requires typed path and compiler")
        elif self.compiler_version is not None:
            raise ValueError("non-compilable family cannot advertise a compiler")


@dataclass(frozen=True, slots=True)
class ProofSchemaSpec:
    family: str
    schema_version: int
    cert_kind: str
    allowed_fields: frozenset[str]
    required_fields: frozenset[str]

    def __post_init__(self) -> None:
        _token(self.family, field_name="ProofSchemaSpec.family")
        if type(self.schema_version) is not int or self.schema_version <= 0:
            raise ValueError("ProofSchemaSpec.schema_version must be a positive exact int")
        _token(self.cert_kind, field_name="ProofSchemaSpec.cert_kind")
        if type(self.allowed_fields) is not frozenset or type(self.required_fields) is not frozenset:
            raise TypeError("proof fields must be exact frozensets")
        if "cert_kind" not in self.required_fields or not self.required_fields <= self.allowed_fields:
            raise ValueError("proof required fields must include cert_kind and be allowed")
        for field_id in self.allowed_fields:
            _text(field_id, field_name="ProofSchemaSpec.allowed_fields")


@dataclass(frozen=True, slots=True)
class PluginIdentitySpec:
    kind: PluginProviderKind
    identity: StaticSymbolIdentity
    production_order: int
    factory_construction_order: int | None

    def __post_init__(self) -> None:
        if type(self.kind) is not PluginProviderKind:
            raise TypeError("PluginIdentitySpec.kind must be PluginProviderKind")
        if type(self.identity) is not StaticSymbolIdentity:
            raise TypeError("PluginIdentitySpec.identity must be StaticSymbolIdentity")
        if type(self.production_order) is not int or self.production_order < 0:
            raise ValueError("production_order must be a non-negative exact int")
        if self.kind is PluginProviderKind.FACTORY:
            if type(self.factory_construction_order) is not int or self.factory_construction_order < 0:
                raise ValueError("factory identity requires a non-negative construction order")
        elif self.factory_construction_order is not None:
            raise ValueError("instance identity cannot carry factory construction order")


@dataclass(frozen=True, slots=True)
class SnapshotInputSpec:
    family_input_key: str
    record_type: StaticSymbolIdentity

    def __post_init__(self) -> None:
        _token(self.family_input_key, field_name="SnapshotInputSpec.family_input_key")
        if type(self.record_type) is not StaticSymbolIdentity:
            raise TypeError("SnapshotInputSpec.record_type must be StaticSymbolIdentity")


@dataclass(frozen=True, slots=True)
class SnapshotProjectionSpec:
    snapshot_field_id: str
    builder: StaticSymbolIdentity

    def __post_init__(self) -> None:
        _token(self.snapshot_field_id, field_name="SnapshotProjectionSpec.snapshot_field_id")
        if type(self.builder) is not StaticSymbolIdentity:
            raise TypeError("SnapshotProjectionSpec.builder must be StaticSymbolIdentity")


SUPPORTED_LOWERING_OPERATIONS_V1: Final = frozenset(
    {"region_capacity_le", "shape_packing_hall_le", "power_pose_exclusion"}
)


@dataclass(frozen=True, slots=True)
class LoweringSpec:
    operation: str
    typed_apply_entrypoint: StaticSymbolIdentity
    master_primitive: str

    def __post_init__(self) -> None:
        if self.operation not in SUPPORTED_LOWERING_OPERATIONS_V1:
            raise ValueError("lowering operation is outside the existing closed set")
        if type(self.typed_apply_entrypoint) is not StaticSymbolIdentity:
            raise TypeError("typed_apply_entrypoint must be StaticSymbolIdentity")
        primitive = _text(self.master_primitive, field_name="LoweringSpec.master_primitive")
        if not primitive.startswith("_lower_"):
            raise ValueError("master primitive must be an explicit _lower_* identity")


@dataclass(frozen=True, slots=True)
class ReplaySpec:
    kind: ReplayKind
    entrypoint: StaticSymbolIdentity

    def __post_init__(self) -> None:
        if type(self.kind) is not ReplayKind:
            raise TypeError("ReplaySpec.kind must be ReplayKind")
        if type(self.entrypoint) is not StaticSymbolIdentity:
            raise TypeError("ReplaySpec.entrypoint must be StaticSymbolIdentity")


FAMILY_CONTRACT_IDS_V1: Final = frozenset(
    {
        "apply_atomicity",
        "enabled_authority_gate",
        "experimental_fail_closed",
        "hold_and_quarantine",
        "independent_exact_checker",
        "legacy_diagnostic_replay_hold",
        "malformed_proof",
        "master_proto_unchanged_on_rejection",
        "premise_and_version_drift",
        "proof_plan_interpreter_tiny_master_exact_chain",
        "replay_fail_closed",
        "retired_fail_closed",
        "shadow_zero_master_mutation",
        "stale_snapshot",
        "tcb_fault_propagation",
        "unknown_type",
        "wrong_strengthening",
    }
)


@dataclass(frozen=True, slots=True)
class FamilyTrustSpec:
    capability: CapabilitySpec
    proof_schema: StaticSlot[ProofSchemaSpec]
    rule_semantics: tuple[VersionedRuleRef, ...]
    authority_dependency_closure: frozenset[str]
    consumed_snapshot_field_ids: frozenset[str]
    typed_plugin: StaticSlot[PluginIdentitySpec]
    exact_checker: StaticSlot[StaticSymbolIdentity]
    snapshot_input: StaticSlot[SnapshotInputSpec]
    snapshot_projection: StaticSlot[SnapshotProjectionSpec]
    lowering: StaticSlot[LoweringSpec]
    replay: StaticSlot[ReplaySpec]
    lifecycle_stage: LifecycleStage
    telemetry_profile: TelemetryProfile
    required_contract_ids: tuple[str, ...]

    @property
    def family(self) -> str:
        return self.capability.family

    def __post_init__(self) -> None:
        if type(self.capability) is not CapabilitySpec:
            raise TypeError("FamilyTrustSpec.capability must be CapabilitySpec")
        slot_types: tuple[tuple[str, StaticSlot[object], type[object]], ...] = (
            ("proof_schema", cast(StaticSlot[object], self.proof_schema), ProofSchemaSpec),
            ("typed_plugin", cast(StaticSlot[object], self.typed_plugin), PluginIdentitySpec),
            ("exact_checker", cast(StaticSlot[object], self.exact_checker), StaticSymbolIdentity),
            ("snapshot_input", cast(StaticSlot[object], self.snapshot_input), SnapshotInputSpec),
            ("snapshot_projection", cast(StaticSlot[object], self.snapshot_projection), SnapshotProjectionSpec),
            ("lowering", cast(StaticSlot[object], self.lowering), LoweringSpec),
            ("replay", cast(StaticSlot[object], self.replay), ReplaySpec),
        )
        for name, slot, expected_type in slot_types:
            if type(slot) is not StaticSlot:
                raise TypeError(f"{name} must be StaticSlot")
            if slot.value is not None and type(slot.value) is not expected_type:
                raise TypeError(f"{name} available value must be {expected_type.__name__}")
        if self.proof_schema.value is not None:
            if (
                self.proof_schema.value.family != self.family
                or self.proof_schema.value.schema_version != self.capability.proof_schema_version
            ):
                raise ValueError("proof schema family/version differs from capability")
        if type(self.rule_semantics) is not tuple or not self.rule_semantics:
            raise TypeError("rule_semantics must be a non-empty exact tuple")
        if any(type(ref) is not VersionedRuleRef for ref in self.rule_semantics):
            raise TypeError("rule_semantics must contain VersionedRuleRef")
        if self.rule_semantics[0].rule_id != self.family:
            raise ValueError("first rule semantic must be the family rule")
        if self.authority_dependency_closure != self.capability.required_dependencies:
            raise ValueError("authority dependency closure differs from capability dependencies")
        if type(self.consumed_snapshot_field_ids) is not frozenset:
            raise TypeError("consumed_snapshot_field_ids must be an exact frozenset")
        for field_id in self.consumed_snapshot_field_ids:
            _text(field_id, field_name="consumed_snapshot_field_ids")
        if type(self.lifecycle_stage) is not LifecycleStage:
            raise TypeError("lifecycle_stage must be LifecycleStage")
        if type(self.telemetry_profile) is not TelemetryProfile:
            raise TypeError("telemetry_profile must be TelemetryProfile")
        if type(self.required_contract_ids) is not tuple or not self.required_contract_ids:
            raise TypeError("required_contract_ids must be a non-empty exact tuple")
        if len(self.required_contract_ids) != len(set(self.required_contract_ids)):
            raise ValueError("required_contract_ids cannot contain duplicates")
        if not frozenset(self.required_contract_ids) <= FAMILY_CONTRACT_IDS_V1:
            raise ValueError("required_contract_ids contains an unknown contract")
        self._validate_surface_coherence()

    def _validate_surface_coherence(self) -> None:
        capability = self.capability
        if capability.stage is CapabilityStage.RETIRED:
            if self.lifecycle_stage is not LifecycleStage.RETIRED:
                raise ValueError("retired capability requires retired lifecycle")
            if any(
                slot.is_available
                for slot in (
                    self.proof_schema,
                    self.typed_plugin,
                    self.exact_checker,
                    self.snapshot_input,
                    self.snapshot_projection,
                    self.lowering,
                    self.replay,
                )
            ):
                raise ValueError("retired family cannot advertise a live trust role")
            return
        if not self.proof_schema.is_available or not self.replay.is_available:
            raise ValueError("live family requires proof schema and replay identity")
        replay = cast(ReplaySpec, self.replay.value)
        if capability.execution_path is ExecutionPath.LEGACY_DIAGNOSTIC:
            if replay.kind is not ReplayKind.LEGACY_DIAGNOSTIC:
                raise ValueError("legacy family requires legacy replay")
            if any(
                slot.is_available
                for slot in (self.typed_plugin, self.snapshot_input, self.snapshot_projection, self.lowering)
            ):
                raise ValueError("legacy family cannot advertise typed trust roles")
            if self.lifecycle_stage is not LifecycleStage.LEGACY_HOLD:
                raise ValueError("legacy family requires HOLD-only lifecycle")
            return
        if replay.kind is not ReplayKind.TYPED_SINGLE_ENTRY:
            raise ValueError("typed family requires typed single-entry replay")
        if not self.typed_plugin.is_available or not self.snapshot_input.is_available:
            raise ValueError("typed family requires plugin and snapshot-input identities")
        if capability.stage is CapabilityStage.VALIDATED:
            if self.snapshot_projection.is_available or self.lowering.is_available:
                raise ValueError("typed shadow family cannot advertise projection/lowering")
            if self.lifecycle_stage is not LifecycleStage.TYPED_SHADOW:
                raise ValueError("typed validated family requires shadow lifecycle")
        else:
            if not self.snapshot_projection.is_available or not self.lowering.is_available:
                raise ValueError("compilable/enabled family requires projection/lowering")
            expected_lifecycle = (
                LifecycleStage.TYPED_ENABLED
                if capability.stage is CapabilityStage.ENABLED
                else LifecycleStage.TYPED_COMPILED
            )
            if self.lifecycle_stage is not expected_lifecycle:
                raise ValueError("typed lifecycle differs from capability stage")


@dataclass(frozen=True, slots=True)
class FamilyGenerationSpec:
    family: str
    surface: GenerationSurface
    oracle_name: StaticSlot[str]
    family_version: StaticSlot[str]
    validator_version: StaticSlot[str]
    generator: StaticSlot[StaticSymbolIdentity]
    orchestrator: StaticSlot[StaticSymbolIdentity]
    adapter_factory: StaticSlot[StaticSymbolIdentity]
    preparation_steps: tuple[StaticSymbolIdentity, ...]
    generator_parameter_ids: tuple[str, ...]
    orchestration_context_ids: tuple[str, ...]
    production_typed_order: int | None

    def __post_init__(self) -> None:
        _token(self.family, field_name="FamilyGenerationSpec.family")
        if type(self.surface) is not GenerationSurface:
            raise TypeError("FamilyGenerationSpec.surface must be GenerationSurface")
        slot_types: tuple[tuple[str, StaticSlot[object], type[object]], ...] = (
            ("oracle_name", cast(StaticSlot[object], self.oracle_name), str),
            ("family_version", cast(StaticSlot[object], self.family_version), str),
            ("validator_version", cast(StaticSlot[object], self.validator_version), str),
            ("generator", cast(StaticSlot[object], self.generator), StaticSymbolIdentity),
            ("orchestrator", cast(StaticSlot[object], self.orchestrator), StaticSymbolIdentity),
            ("adapter_factory", cast(StaticSlot[object], self.adapter_factory), StaticSymbolIdentity),
        )
        for name, slot, expected_type in slot_types:
            if type(slot) is not StaticSlot:
                raise TypeError(f"{name} must be StaticSlot")
            if slot.value is not None and type(slot.value) is not expected_type:
                raise TypeError(f"{name} available value must be {expected_type.__name__}")
        for name, values in (
            ("preparation_steps", self.preparation_steps),
            ("generator_parameter_ids", self.generator_parameter_ids),
            ("orchestration_context_ids", self.orchestration_context_ids),
        ):
            if type(values) is not tuple:
                raise TypeError(f"{name} must be an exact tuple")
            if len(values) != len(set(values)):
                raise ValueError(f"{name} cannot contain duplicates")
        if any(type(value) is not StaticSymbolIdentity for value in self.preparation_steps):
            raise TypeError("preparation_steps must contain StaticSymbolIdentity")
        for value in (*self.generator_parameter_ids, *self.orchestration_context_ids):
            _token(value, field_name="generation input ID")
        if self.surface is GenerationSurface.RETIRED:
            if any(
                slot.is_available
                for slot in (
                    self.oracle_name,
                    self.family_version,
                    self.validator_version,
                    self.generator,
                    self.orchestrator,
                    self.adapter_factory,
                )
            ):
                raise ValueError("retired generation cannot advertise live identities")
            if self.production_typed_order is not None:
                raise ValueError("retired generation cannot have typed order")
            return
        if not all(
            slot.is_available
            for slot in (self.oracle_name, self.family_version, self.validator_version, self.generator)
        ):
            raise ValueError("live generation requires oracle, wire versions, and generator")
        if self.surface is GenerationSurface.TYPED_ATTACH:
            if not self.orchestrator.is_available or not self.orchestration_context_ids:
                raise ValueError("typed generation requires orchestrator and context identities")
            if type(self.production_typed_order) is not int or self.production_typed_order < 0:
                raise ValueError("typed generation requires non-negative order")
        elif self.production_typed_order is not None or self.orchestration_context_ids:
            raise ValueError("non-typed generation cannot have typed order/context")


@dataclass(frozen=True, slots=True, init=False)
class FamilySpecRegistry:
    schema_version: int
    rule_semantics: RuleSemanticRegistry
    trust_specs: Mapping[str, FamilyTrustSpec]
    generation_specs: Mapping[str, FamilyGenerationSpec]
    typed_generation_order: tuple[str, ...]
    audit_digest: str

    def __init__(
        self,
        *,
        schema_version: int,
        rule_semantics: RuleSemanticRegistry,
        trust_specs: Mapping[str, FamilyTrustSpec],
        generation_specs: Mapping[str, FamilyGenerationSpec],
        typed_generation_order: tuple[str, ...],
    ) -> None:
        if type(schema_version) is not int or schema_version != 1:
            raise ValueError("FamilySpecRegistry.schema_version must be exact int 1")
        if type(rule_semantics) is not RuleSemanticRegistry:
            raise TypeError("rule_semantics must be RuleSemanticRegistry")
        trust = _checked_mapping(trust_specs, FamilyTrustSpec, "trust_specs")
        generation = _checked_mapping(generation_specs, FamilyGenerationSpec, "generation_specs")
        if frozenset(trust) != frozenset(generation):
            raise ValueError("trust and generation rows must cover identical families")
        for family, trust_row in trust.items():
            generation_row = generation[family]
            for ref in trust_row.rule_semantics:
                if rule_semantics.get(ref.rule_id).semantic_version != ref.semantic_version:
                    raise ValueError(f"{family!r} pins stale rule semantics")
            family_rule = rule_semantics.get(family)
            expected_refs = (
                VersionedRuleRef(family, family_rule.semantic_version),
                *family_rule.semantic_dependencies,
                *family_rule.protocol_obligations,
            )
            if trust_row.rule_semantics != expected_refs:
                raise ValueError(f"{family!r} rule closure differs from semantic ledger")
            if generation_row.family_version.is_available:
                if generation_row.family_version.value != family_rule.semantic_version:
                    raise ValueError(f"{family!r} generator semantic version drift")
            expected_state = {
                (CapabilityStage.VALIDATED, ExecutionPath.LEGACY_DIAGNOSTIC):
                    RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC,
                (CapabilityStage.VALIDATED, ExecutionPath.TYPED):
                    RuleDeploymentState.VALIDATED_SHADOW_ONLY,
                (CapabilityStage.COMPILABLE, ExecutionPath.TYPED): RuleDeploymentState.COMPILABLE,
                (CapabilityStage.ENABLED, ExecutionPath.TYPED): RuleDeploymentState.ENABLED,
                (CapabilityStage.RETIRED, ExecutionPath.LEGACY_DIAGNOSTIC): RuleDeploymentState.RETIRED,
                (CapabilityStage.EXPERIMENTAL, ExecutionPath.TYPED): RuleDeploymentState.EXPERIMENTAL,
            }.get((trust_row.capability.stage, trust_row.capability.execution_path))
            if expected_state is None or family_rule.deployment_state is not expected_state:
                raise ValueError(f"{family!r} lifecycle differs from semantic deployment state")
        if type(typed_generation_order) is not tuple:
            raise TypeError("typed_generation_order must be an exact tuple")
        if len(typed_generation_order) != len(set(typed_generation_order)):
            raise ValueError("typed_generation_order cannot contain duplicates")
        derived = tuple(
            row.family
            for row in sorted(
                (
                    row
                    for row in generation.values()
                    if row.production_typed_order is not None
                ),
                key=lambda row: cast(int, row.production_typed_order),
            )
        )
        indices = tuple(cast(int, generation[name].production_typed_order) for name in derived)
        if indices != tuple(range(len(indices))) or derived != typed_generation_order:
            raise ValueError("typed generation order is non-contiguous or differs from rows")
        projection = {
            "generation_specs": _audit(generation),
            "rule_semantics_audit_digest": rule_semantics.audit_digest,
            "schema_version": schema_version,
            "trust_specs": _audit(trust),
            "typed_generation_order": list(typed_generation_order),
        }
        digest = hashlib.sha256(
            _AUDIT_PREFIX
            + json.dumps(
                projection,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "rule_semantics", rule_semantics)
        object.__setattr__(self, "trust_specs", MappingProxyType(trust))
        object.__setattr__(self, "generation_specs", MappingProxyType(generation))
        object.__setattr__(self, "typed_generation_order", typed_generation_order)
        object.__setattr__(self, "audit_digest", digest)

    def trust(self, family: str) -> FamilyTrustSpec:
        try:
            return self.trust_specs[family]
        except KeyError as exc:
            raise KeyError(f"unknown family trust spec {family!r}") from exc

    def generation(self, family: str) -> FamilyGenerationSpec:
        try:
            return self.generation_specs[family]
        except KeyError as exc:
            raise KeyError(f"unknown family generation spec {family!r}") from exc

    def audit_projection(self) -> dict[str, object]:
        return {
            "generation_specs": _audit(self.generation_specs),
            "rule_semantics_audit_digest": self.rule_semantics.audit_digest,
            "schema_version": self.schema_version,
            "trust_specs": _audit(self.trust_specs),
            "typed_generation_order": list(self.typed_generation_order),
        }


def _checked_mapping(
    raw: Mapping[str, object],
    expected_type: type[_T],
    field_name: str,
) -> dict[str, _T]:
    if not isinstance(raw, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    checked: dict[str, _T] = {}
    for key, value in raw.items():
        _token(key, field_name=f"{field_name} key")
        if type(value) is not expected_type or getattr(value, "family", None) != key:
            raise ValueError(f"{field_name} key/spec identity mismatch")
        checked[key] = cast(_T, value)
    return checked


def _audit(value: object) -> object:
    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, Enum):
        return value.value
    if type(value) is StaticSymbolIdentity:
        return cast(StaticSymbolIdentity, value).audit_projection()
    if type(value) is StaticSlot:
        return (
            {"available": False, "reason": value.unavailable_reason}
            if value.value is None
            else {"available": True, "value": _audit(value.value)}
        )
    if isinstance(value, Mapping):
        return {str(key): _audit(value[key]) for key in sorted(value)}
    if type(value) is tuple:
        return [_audit(item) for item in cast(tuple[object, ...], value)]
    if type(value) is frozenset:
        projected = [_audit(item) for item in cast(frozenset[object], value)]
        return sorted(
            projected,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _audit(getattr(value, item.name)) for item in fields(value)}
    raise TypeError(f"unsupported shadow manifest audit value {type(value).__name__}")


PRODUCTION_AUTHORITY_DEPENDENCIES_V1: Final = frozenset(
    {
        "candidate_placements",
        "canonical_rules",
        "certified_exact_source_tree",
        "commodity_demands",
        "generic_io_requirements",
        "mandatory_exact_instances",
        "orbit_homogeneity_digest",
        "preprocess_plan",
    }
)

_TYPED_COMPILED_CONTRACTS: Final = (
    "hold_and_quarantine",
    "malformed_proof",
    "premise_and_version_drift",
    "stale_snapshot",
    "replay_fail_closed",
    "tcb_fault_propagation",
    "unknown_type",
    "wrong_strengthening",
    "apply_atomicity",
    "master_proto_unchanged_on_rejection",
    "proof_plan_interpreter_tiny_master_exact_chain",
)
_LEGACY_CONTRACTS: Final = (
    "hold_and_quarantine",
    "legacy_diagnostic_replay_hold",
    "tcb_fault_propagation",
    "unknown_type",
)


def _proof(family: str, cert_kind: str, *fields_: str) -> ProofSchemaSpec:
    field_set = frozenset(("cert_kind", *fields_))
    return ProofSchemaSpec(
        family=family,
        schema_version=1,
        cert_kind=cert_kind,
        allowed_fields=field_set,
        required_fields=field_set,
    )


_PROOF_SCHEMAS: Final = MappingProxyType(
    {
        "region_capacity": _proof(
            "region_capacity",
            "region_capacity_combinatorial",
            "cap_R",
            "cells_per_pose",
            "contributing_groups",
            "demand_R",
            "gap",
            "lp_dual_objective",
            "lp_dual_ray_b64",
            "region_cells_bitset_b64",
            "region_kind",
        ),
        "cutset": _proof(
            "cutset",
            "menger_min_cut",
            "commodity_demand",
            "contributing_commodities",
            "cut_edges",
            "cut_size",
            "side_a_bitset_b64",
            "side_b_bitset_b64",
        ),
        "port_exposure": _proof(
            "port_exposure",
            "port_exposure_blocked",
            "active_port_witness_b64",
            "blocking_facility",
            "facility_group",
            "facility_pose_id",
            "front_cell",
            "port_cell",
            "port_direction",
        ),
        "component_reach": _proof(
            "component_reach",
            "bfs_disconnect_witness",
            "blocking_facilities",
            "commodity_id",
            "separator_cells",
            "sink_cell",
            "sink_component_bitset_b64",
            "src_cell",
            "src_component_bitset_b64",
        ),
        "pattern_nogood": _proof(
            "pattern_nogood",
            "bounded_deletion_core",
            "core_minimization",
            "forbidden_pose_pattern",
            "sub_problem_oracle_name",
            "sub_problem_oracle_version",
        ),
        "shape_packing_hall": _proof(
            "shape_packing_hall",
            "hall_interval_witness",
            "contributing_group",
            "exterior_blocks_digest",
            "ghost_rect_repr",
            "group_demand",
            "max_packable",
            "partition_lens",
            "partition_offsets",
            "pose_length",
            "pose_shape_canonical",
            "region_demand",
            "region_kind",
            "region_total_length",
            "total_packable",
        ),
        "power_hitting_set": _proof(
            "power_hitting_set",
            "power_cover_emptyset_ghost",
            "exterior_blocks_digest",
            "facility_cells",
            "facility_group",
            "facility_pose_id",
            "ghost_rect_repr",
            "pole_radius",
            "pole_shape_canonical",
        ),
        "density_envelope": _proof(
            "density_envelope",
            "density_envelope_v1",
            "ghost_rect_repr",
            "group_id",
            "max_allowed_area",
            "oracle_assignment_witness",
            "window_rect",
            "witness_kind",
        ),
    }
)


_F1_SNAPSHOT_FIELDS: Final = frozenset(
    {
        "artifact_hashes",
        "canonical_rules_source_present",
        "digest",
        "exterior_blocks",
        "exterior_blocks_digest",
        "family_inputs.region_capacity.group_demands",
        "family_inputs.region_capacity.group_pose_domains",
        "family_inputs.region_capacity.instance_to_facility_type",
        "family_inputs.region_capacity.pose_occupied_cells",
        "family_inputs.region_capacity.template_dimensions",
        "family_inputs.region_capacity.template_placement_rules",
        "ghost_cells",
        "master_domain_projection",
        "oracle_capabilities",
        "source_digest",
    }
)
_F5_SNAPSHOT_FIELDS: Final = frozenset(
    {
        "artifact_hashes",
        "digest",
        "exterior_blocks_digest",
        "family_inputs.pattern_nogood.artifact_hashes",
        "family_inputs.pattern_nogood.canonical_rules",
        "family_inputs.pattern_nogood.facility_pools",
        "family_inputs.pattern_nogood.facility_templates",
        "family_inputs.pattern_nogood.group_demands",
        "family_inputs.pattern_nogood.group_pose_domains",
        "family_inputs.pattern_nogood.instance_to_facility_type",
        "groups",
        "oracle_capabilities",
        "source_digest",
    }
)
_F6_SNAPSHOT_FIELDS: Final = frozenset(
    {
        "artifact_hashes",
        "blocked_cells_digest",
        "digest",
        "exterior_blocks",
        "exterior_blocks_digest",
        "family_inputs.shape_packing_hall.ghost",
        "family_inputs.shape_packing_hall.group_demands",
        "family_inputs.shape_packing_hall.group_to_facility_type",
        "family_inputs.shape_packing_hall.template_dimensions",
        "family_inputs.shape_packing_hall.template_placement_rules",
        "ghost",
        "ghost_cells",
        "oracle_capabilities",
        "shape_packing_hall_master_domain_projection",
        "source_digest",
    }
)
_F7_SNAPSHOT_FIELDS: Final = frozenset(
    {
        "artifact_hashes",
        "blocked_cells_digest",
        "cell_owner",
        "digest",
        "exterior_blocks",
        "exterior_blocks_digest",
        "family_inputs.power_hitting_set.cell_owner",
        "family_inputs.power_hitting_set.ghost",
        "family_inputs.power_hitting_set.group_pose_domains",
        "family_inputs.power_hitting_set.group_to_facility_type",
        "family_inputs.power_hitting_set.pole_dimensions",
        "family_inputs.power_hitting_set.pole_radius",
        "family_inputs.power_hitting_set.pose_occupied_cells",
        "family_inputs.power_hitting_set.template_needs_power",
        "ghost",
        "ghost_cells",
        "oracle_capabilities",
        "power_hitting_set_master_domain_projection",
        "source_digest",
    }
)


def _rule_refs(family: str) -> tuple[VersionedRuleRef, ...]:
    rule = SHADOW_RULE_SEMANTICS_V1.get(family)
    return (
        VersionedRuleRef(family, rule.semantic_version),
        *rule.semantic_dependencies,
        *rule.protocol_obligations,
    )


def _capability(
    family: str,
    mode: FamilyMode,
    validator: str,
    compiler: str | None,
    stage: CapabilityStage,
    path: ExecutionPath,
    *,
    ghost_bound: bool = False,
) -> CapabilitySpec:
    return CapabilitySpec(
        family=family,
        mode=mode,
        proof_schema_version=1,
        validator_version=validator,
        compiler_version=compiler,
        stage=stage,
        required_dependencies=PRODUCTION_AUTHORITY_DEPENDENCIES_V1,
        execution_path=path,
        requires_ghost_bound=ghost_bound,
    )


_TYPED_REPLAY: Final = ReplaySpec(
    ReplayKind.TYPED_SINGLE_ENTRY,
    StaticSymbolIdentity("src.cuts.typed_platform", "validate_and_compile_cut"),
)
_APPLY_IDENTITY: Final = StaticSymbolIdentity("src.cuts.typed_apply", "apply_compiled_cut")


def _legacy_trust(
    family: str,
    mode: FamilyMode,
    replay_module: str,
) -> FamilyTrustSpec:
    return FamilyTrustSpec(
        capability=_capability(
            family,
            mode,
            "legacy-diagnostic-v1",
            None,
            CapabilityStage.VALIDATED,
            ExecutionPath.LEGACY_DIAGNOSTIC,
        ),
        proof_schema=available(_PROOF_SCHEMAS[family]),
        rule_semantics=_rule_refs(family),
        authority_dependency_closure=PRODUCTION_AUTHORITY_DEPENDENCIES_V1,
        consumed_snapshot_field_ids=frozenset(),
        typed_plugin=unavailable("legacy-diagnostic-only"),
        exact_checker=unavailable("legacy-validator-is-not-independent"),
        snapshot_input=unavailable("legacy-replay-reads-bstate"),
        snapshot_projection=unavailable("no-typed-master-projection"),
        lowering=unavailable("no-trusted-lowering"),
        replay=available(
            ReplaySpec(
                ReplayKind.LEGACY_DIAGNOSTIC,
                StaticSymbolIdentity(replay_module, f"validate_{family}"),
            )
        ),
        lifecycle_stage=LifecycleStage.LEGACY_HOLD,
        telemetry_profile=TelemetryProfile.LEGACY_DIAGNOSTIC,
        required_contract_ids=_LEGACY_CONTRACTS,
    )


_TRUST_ROWS: Final = (
    FamilyTrustSpec(
        capability=_capability(
            "region_capacity",
            FamilyMode.GEOMETRIC,
            "stage-b-f1-validator-v1",
            "stage-b-f1-compiler-v1",
            CapabilityStage.COMPILABLE,
            ExecutionPath.TYPED,
        ),
        proof_schema=available(_PROOF_SCHEMAS["region_capacity"]),
        rule_semantics=_rule_refs("region_capacity"),
        authority_dependency_closure=PRODUCTION_AUTHORITY_DEPENDENCIES_V1,
        consumed_snapshot_field_ids=_F1_SNAPSHOT_FIELDS,
        typed_plugin=available(
            PluginIdentitySpec(
                PluginProviderKind.FACTORY,
                StaticSymbolIdentity(
                    "src.cuts.families.region_capacity_typed",
                    "RegionCapacityPlugin",
                ),
                2,
                0,
            )
        ),
        exact_checker=unavailable("no-production-independent-exact-twin-checker"),
        snapshot_input=available(
            SnapshotInputSpec(
                "region_capacity",
                StaticSymbolIdentity("src.cuts.state_snapshot", "F1RegionInputs"),
            )
        ),
        snapshot_projection=available(
            SnapshotProjectionSpec(
                "master_domain_projection",
                StaticSymbolIdentity(
                    "src.cuts.state_snapshot",
                    "_build_f1_master_domain_projection",
                ),
            )
        ),
        lowering=available(
            LoweringSpec("region_capacity_le", _APPLY_IDENTITY, "_lower_region_capacity_cut")
        ),
        replay=available(_TYPED_REPLAY),
        lifecycle_stage=LifecycleStage.TYPED_COMPILED,
        telemetry_profile=TelemetryProfile.TYPED_COMPILED,
        required_contract_ids=_TYPED_COMPILED_CONTRACTS,
    ),
    _legacy_trust("cutset", FamilyMode.GEOMETRIC, "src.cuts.families.cutset"),
    _legacy_trust("port_exposure", FamilyMode.LITERAL, "src.cuts.families.port_exposure"),
    _legacy_trust("component_reach", FamilyMode.GEOMETRIC, "src.cuts.families.component_reach"),
    FamilyTrustSpec(
        capability=_capability(
            "pattern_nogood",
            FamilyMode.LITERAL,
            "stage-b-f5-shadow-v1",
            None,
            CapabilityStage.VALIDATED,
            ExecutionPath.TYPED,
        ),
        proof_schema=available(_PROOF_SCHEMAS["pattern_nogood"]),
        rule_semantics=_rule_refs("pattern_nogood"),
        authority_dependency_closure=PRODUCTION_AUTHORITY_DEPENDENCIES_V1,
        consumed_snapshot_field_ids=_F5_SNAPSHOT_FIELDS,
        typed_plugin=available(
            PluginIdentitySpec(
                PluginProviderKind.INSTANCE,
                StaticSymbolIdentity("src.cuts.typed_platform", "_PatternNogoodPlugin"),
                0,
                None,
            )
        ),
        exact_checker=available(
            StaticSymbolIdentity(
                "src.cuts.verifiers.binding_empty_domain_verifier",
                "verify_binding_empty_domain",
            )
        ),
        snapshot_input=available(
            SnapshotInputSpec(
                "pattern_nogood",
                StaticSymbolIdentity("src.cuts.state_snapshot", "F5PatternNogoodInputs"),
            )
        ),
        snapshot_projection=unavailable("shadow-only-no-master-projection"),
        lowering=unavailable("shadow-only-no-trusted-lowering"),
        replay=available(_TYPED_REPLAY),
        lifecycle_stage=LifecycleStage.TYPED_SHADOW,
        telemetry_profile=TelemetryProfile.TYPED_SHADOW,
        required_contract_ids=(
            "hold_and_quarantine",
            "malformed_proof",
            "premise_and_version_drift",
            "stale_snapshot",
            "replay_fail_closed",
            "tcb_fault_propagation",
            "unknown_type",
            "shadow_zero_master_mutation",
            "independent_exact_checker",
        ),
    ),
    FamilyTrustSpec(
        capability=_capability(
            "shape_packing_hall",
            FamilyMode.GEOMETRIC,
            "stage-b-f6-validator-v1",
            "stage-b-f6-compiler-v1",
            CapabilityStage.COMPILABLE,
            ExecutionPath.TYPED,
            ghost_bound=True,
        ),
        proof_schema=available(_PROOF_SCHEMAS["shape_packing_hall"]),
        rule_semantics=_rule_refs("shape_packing_hall"),
        authority_dependency_closure=PRODUCTION_AUTHORITY_DEPENDENCIES_V1,
        consumed_snapshot_field_ids=_F6_SNAPSHOT_FIELDS,
        typed_plugin=available(
            PluginIdentitySpec(
                PluginProviderKind.FACTORY,
                StaticSymbolIdentity(
                    "src.cuts.families.shape_packing_hall_typed",
                    "ShapePackingHallPlugin",
                ),
                3,
                2,
            )
        ),
        exact_checker=unavailable("no-production-independent-exact-twin-checker"),
        snapshot_input=available(
            SnapshotInputSpec(
                "shape_packing_hall",
                StaticSymbolIdentity("src.cuts.state_snapshot", "F6HallInputs"),
            )
        ),
        snapshot_projection=available(
            SnapshotProjectionSpec(
                "shape_packing_hall_master_domain_projection",
                StaticSymbolIdentity(
                    "src.cuts.state_snapshot",
                    "_build_f6_master_domain_projection",
                ),
            )
        ),
        lowering=available(
            LoweringSpec(
                "shape_packing_hall_le",
                _APPLY_IDENTITY,
                "_lower_baseline_packing_cut",
            )
        ),
        replay=available(_TYPED_REPLAY),
        lifecycle_stage=LifecycleStage.TYPED_COMPILED,
        telemetry_profile=TelemetryProfile.TYPED_COMPILED,
        required_contract_ids=_TYPED_COMPILED_CONTRACTS,
    ),
    FamilyTrustSpec(
        capability=_capability(
            "power_hitting_set",
            FamilyMode.LITERAL,
            "stage-b-f7-validator-v1",
            "stage-b-f7-compiler-v1",
            CapabilityStage.COMPILABLE,
            ExecutionPath.TYPED,
            ghost_bound=True,
        ),
        proof_schema=available(_PROOF_SCHEMAS["power_hitting_set"]),
        rule_semantics=_rule_refs("power_hitting_set"),
        authority_dependency_closure=PRODUCTION_AUTHORITY_DEPENDENCIES_V1,
        consumed_snapshot_field_ids=_F7_SNAPSHOT_FIELDS,
        typed_plugin=available(
            PluginIdentitySpec(
                PluginProviderKind.FACTORY,
                StaticSymbolIdentity(
                    "src.cuts.families.power_hitting_set_typed",
                    "PowerHittingSetPlugin",
                ),
                1,
                1,
            )
        ),
        exact_checker=unavailable("no-production-independent-exact-twin-checker"),
        snapshot_input=available(
            SnapshotInputSpec(
                "power_hitting_set",
                StaticSymbolIdentity("src.cuts.state_snapshot", "F7PowerInputs"),
            )
        ),
        snapshot_projection=available(
            SnapshotProjectionSpec(
                "power_hitting_set_master_domain_projection",
                StaticSymbolIdentity(
                    "src.cuts.state_snapshot",
                    "_build_f7_master_domain_projection",
                ),
            )
        ),
        lowering=available(
            LoweringSpec(
                "power_pose_exclusion",
                _APPLY_IDENTITY,
                "_lower_power_pose_exclusion_cut",
            )
        ),
        replay=available(_TYPED_REPLAY),
        lifecycle_stage=LifecycleStage.TYPED_COMPILED,
        telemetry_profile=TelemetryProfile.TYPED_COMPILED,
        required_contract_ids=_TYPED_COMPILED_CONTRACTS,
    ),
    FamilyTrustSpec(
        capability=_capability(
            "power_grid_reach",
            FamilyMode.GEOMETRIC,
            "retired-false-premise",
            None,
            CapabilityStage.RETIRED,
            ExecutionPath.LEGACY_DIAGNOSTIC,
        ),
        proof_schema=unavailable("retired-family-has-no-live-proof-schema"),
        rule_semantics=_rule_refs("power_grid_reach"),
        authority_dependency_closure=PRODUCTION_AUTHORITY_DEPENDENCIES_V1,
        consumed_snapshot_field_ids=frozenset(),
        typed_plugin=unavailable("retired-false-premise"),
        exact_checker=unavailable("retired-false-premise"),
        snapshot_input=unavailable("retired-false-premise"),
        snapshot_projection=unavailable("retired-false-premise"),
        lowering=unavailable("retired-false-premise"),
        replay=unavailable("retired-family-is-not-replayable"),
        lifecycle_stage=LifecycleStage.RETIRED,
        telemetry_profile=TelemetryProfile.RETIRED,
        required_contract_ids=("retired_fail_closed",),
    ),
    _legacy_trust(
        "density_envelope",
        FamilyMode.GEOMETRIC,
        "src.cuts.families.density_envelope",
    ),
)


_BENDERS_ORCHESTRATOR: Final = available(
    StaticSymbolIdentity(
        "src.search.benders_loop",
        "LBBDController._maybe_attach_framework_cuts",
    )
)


def _generation(
    family: str,
    surface: GenerationSurface,
    oracle_name: str,
    version: str,
    generator_module: str,
    generator_qualname: str,
    parameters: tuple[str, ...],
    *,
    context: tuple[str, ...] = (),
    order: int | None = None,
    preparation: tuple[StaticSymbolIdentity, ...] = (),
    adapter: StaticSlot[StaticSymbolIdentity] | None = None,
) -> FamilyGenerationSpec:
    return FamilyGenerationSpec(
        family=family,
        surface=surface,
        oracle_name=available(oracle_name),
        family_version=available(version),
        validator_version=available(version),
        generator=available(StaticSymbolIdentity(generator_module, generator_qualname)),
        orchestrator=_BENDERS_ORCHESTRATOR if surface is GenerationSurface.TYPED_ATTACH else unavailable(
            "family-not-on-typed-attach-surface"
        ),
        adapter_factory=adapter or unavailable("generator-has-no-separate-adapter"),
        preparation_steps=preparation,
        generator_parameter_ids=parameters,
        orchestration_context_ids=context,
        production_typed_order=order,
    )


_GENERATION_ROWS: Final = (
    _generation(
        "region_capacity",
        GenerationSurface.TYPED_ATTACH,
        "region_capacity_v1",
        "v1.2",
        "src.cuts.oracles.region_capacity_oracle",
        "generate_region_capacity_cuts",
        ("state", "canonical_rules", "iter_index", "grid_size"),
        context=("state", "canonical_rules", "iter_index"),
        order=0,
    ),
    _generation(
        "cutset",
        GenerationSurface.LEGACY_DIAGNOSTIC,
        "cutset_v1",
        "v1.0",
        "src.cuts.oracles.cutset_oracle",
        "generate_cutset_cuts",
        ("state", "master_solution", "iter_index"),
    ),
    _generation(
        "port_exposure",
        GenerationSurface.LEGACY_DIAGNOSTIC,
        "port_exposure_v2_canonical_dirs",
        "v1.0",
        "src.cuts.oracles.port_exposure_oracle",
        "generate_port_exposure_cuts",
        ("state", "master_solution", "target_poses", "iter_index"),
    ),
    _generation(
        "component_reach",
        GenerationSurface.LEGACY_DIAGNOSTIC,
        "component_reach_v1",
        "v1.1",
        "src.cuts.oracles.component_reach_oracle",
        "generate_component_reach_cuts",
        ("state", "master_solution", "iter_index"),
    ),
    _generation(
        "pattern_nogood",
        GenerationSurface.TYPED_ATTACH,
        "pattern_nogood_v1",
        "v1.0",
        "src.cuts.oracles.pattern_nogood_oracle",
        "generate_pattern_nogood_cuts",
        ("state", "sub_problem_oracle", "full_assignment_literals", "budget", "iter_index"),
        context=("state", "solution", "mandatory_groups", "iter_index"),
        order=3,
        preparation=(
            StaticSymbolIdentity(
                "src.search.benders_loop",
                "LBBDController._framework_full_assignment_literals",
            ),
        ),
        adapter=available(
            StaticSymbolIdentity(
                "src.search.f5_binding_empty_domain_adapter",
                "build_binding_empty_domain_adapter",
            )
        ),
    ),
    _generation(
        "shape_packing_hall",
        GenerationSurface.TYPED_ATTACH,
        "shape_packing_hall_v1",
        "v1.0",
        "src.cuts.oracles.shape_packing_hall_oracle",
        "generate_shape_packing_hall_cuts",
        ("state", "boundary_groups", "region_kinds", "region_demand_overrides", "iter_index"),
        context=("state", "region_demand_overrides", "iter_index"),
        order=2,
        preparation=(
            StaticSymbolIdentity(
                "src.cuts.oracles.shape_packing_hall_oracle",
                "compute_sot_region_demand_overrides",
            ),
        ),
    ),
    _generation(
        "power_hitting_set",
        GenerationSurface.TYPED_ATTACH,
        "power_cover_v2_stencil",
        "v1.0",
        "src.cuts.oracles.power_cover_oracle",
        "generate_power_hitting_set_cuts",
        ("state", "target_poses", "pole_radius", "iter_index"),
        context=("state", "solution", "target_poses", "iter_index"),
        order=1,
        preparation=(
            StaticSymbolIdentity(
                "src.search.benders_loop",
                "LBBDController._framework_target_poses",
            ),
        ),
    ),
    FamilyGenerationSpec(
        family="power_grid_reach",
        surface=GenerationSurface.RETIRED,
        oracle_name=unavailable("retired-false-premise"),
        family_version=unavailable("retired-false-premise"),
        validator_version=unavailable("retired-false-premise"),
        generator=unavailable("retired-false-premise"),
        orchestrator=unavailable("retired-false-premise"),
        adapter_factory=unavailable("retired-false-premise"),
        preparation_steps=(),
        generator_parameter_ids=(),
        orchestration_context_ids=(),
        production_typed_order=None,
    ),
    _generation(
        "density_envelope",
        GenerationSurface.LEGACY_DIAGNOSTIC,
        "density_envelope_v1",
        "v1.0",
        "src.cuts.oracles.density_envelope_oracle",
        "generate_density_envelope_cuts",
        (
            "state",
            "witness_kind",
            "group_id",
            "window_rect",
            "max_allowed_area",
            "assignment_witness",
            "iter_index",
        ),
    ),
)


SHADOW_FAMILY_SPECS_V1: Final = FamilySpecRegistry(
    schema_version=1,
    rule_semantics=SHADOW_RULE_SEMANTICS_V1,
    trust_specs={row.family: row for row in _TRUST_ROWS},
    generation_specs={row.family: row for row in _GENERATION_ROWS},
    typed_generation_order=(
        "region_capacity",
        "power_hitting_set",
        "shape_packing_hall",
        "pattern_nogood",
    ),
)
