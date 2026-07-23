"""Shadow-only family evolution manifest for the cut platform.

This module describes the *current* F1--F9 wiring without participating in
that wiring.  Milestone A deliberately leaves every production caller on its
existing tables and branches; consistency tests may import this module, but no
runtime module imports it.

Two dependency views are kept separate on purpose:

``authority_dependency_closure``
    The established schema-v1 eight-artifact closure carried by every current
    ``FamilyCapability``.  It is repeated here so a shadow gate can prove exact
    parity before any consumer is migrated.

``consumed_snapshot_field_ids``
    The exact snapshot fields read by the typed single-entry chain for one
    family.  These are audit metadata only.  They do not narrow the v1 wire
    dependency set and never enter a cut, proof, snapshot, plan, digest, or
    semantic fingerprint.

Generation, replay, apply, and plugin references are direct Python objects
captured at import time.  The cross-layer F5 adapter and independent checker
use immutable source identities so importing this shadow module does not pull
``src.search``/``src.models`` into the cut layer.  Identity records have no
resolver.  There is no entry-point discovery, runtime registration API, or
general constraint DSL in this module.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, fields as dataclass_fields, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final, Generic, TypeAlias, TypeVar, cast

from src.cuts.families.component_reach import validate_component_reach
from src.cuts.families.cutset import validate_cutset
from src.cuts.families.density_envelope import validate_density_envelope
from src.cuts.families.port_exposure import validate_port_exposure
from src.cuts.families.power_hitting_set_typed import (
    POWER_HITTING_SET_COMPILER_VERSION,
    POWER_HITTING_SET_VALIDATOR_VERSION,
    PowerHittingSetPlugin,
)
from src.cuts.families.region_capacity_typed import (
    REGION_CAPACITY_COMPILER_VERSION,
    REGION_CAPACITY_VALIDATOR_VERSION,
    RegionCapacityPlugin,
)
from src.cuts.families.shape_packing_hall_typed import (
    SHAPE_PACKING_HALL_COMPILER_VERSION,
    SHAPE_PACKING_HALL_VALIDATOR_VERSION,
    ShapePackingHallPlugin,
)
from src.cuts.oracles.component_reach_oracle import generate_component_reach_cuts
from src.cuts.oracles.cutset_oracle import generate_cutset_cuts
from src.cuts.oracles.density_envelope_oracle import generate_density_envelope_cuts
from src.cuts.oracles.pattern_nogood_oracle import generate_pattern_nogood_cuts
from src.cuts.oracles.port_exposure_oracle import generate_port_exposure_cuts
from src.cuts.oracles.power_cover_oracle import generate_power_hitting_set_cuts
from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
from src.cuts.oracles.shape_packing_hall_oracle import (
    compute_sot_region_demand_overrides,
    generate_shape_packing_hall_cuts,
)
from src.cuts.rule_semantics import (
    PRODUCTION_RULE_SEMANTICS_V1,
    AvailableExactChecker,
    RuleDeploymentState,
    RuleSemanticRegistry,
    VersionedRuleRef,
)
from src.cuts.typed_apply import apply_compiled_cut
from src.cuts.typed_platform import (
    SUPPORTED_OPERATIONS,
    CapabilityStage,
    ConstraintOperation,
    ExecutionPath,
    FamilyCapability,
    FamilyMode,
    FamilyPlugin,
    _PRODUCTION_F5_PLUGIN,
    validate_and_compile_cut,
)
_T = TypeVar("_T")
_FAMILY_MANIFEST_AUDIT_PREFIX: Final = b"zmd.family-manifest.audit.v1:"


class CapabilityUnavailableError(RuntimeError):
    """Raised when a consumer attempts to use an explicitly absent capability."""


@dataclass(frozen=True, slots=True)
class AvailableCapability(Generic[_T]):
    """One capability that exists on the current production surface."""

    value: _T
    is_available: bool = field(default=True, init=False)

    def require(self, *, family: str, capability: str) -> _T:
        del family, capability
        return self.value


@dataclass(frozen=True, slots=True)
class UnavailableCapability:
    """An intentionally absent capability with an auditable reason."""

    reason: str
    is_available: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _require_token(self.reason, field_name="UnavailableCapability.reason")

    def require(self, *, family: str, capability: str) -> object:
        raise CapabilityUnavailableError(
            f"family {family!r} has no {capability}: {self.reason}"
        )


CapabilityAvailability: TypeAlias = AvailableCapability[_T] | UnavailableCapability


def _available(value: _T) -> AvailableCapability[_T]:
    return AvailableCapability(value)


def _unavailable(reason: str) -> UnavailableCapability:
    return UnavailableCapability(reason)


def _require_token(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{field_name} must be a non-empty, trimmed exact str")
    return value


@dataclass(frozen=True, slots=True)
class StaticSymbolIdentity:
    """An audit identity only; it intentionally has no dynamic resolver."""

    module: str
    qualname: str

    def __post_init__(self) -> None:
        module = _require_token(self.module, field_name="StaticSymbolIdentity.module")
        qualname = _require_token(
            self.qualname,
            field_name="StaticSymbolIdentity.qualname",
        )
        if not module.startswith("src."):
            raise ValueError("static family symbols must live below src")
        if "<locals>" in qualname or "<lambda>" in qualname:
            raise ValueError("static family symbols cannot be local functions or lambdas")


@dataclass(frozen=True, slots=True)
class StaticCallableRef:
    """A direct callable reference plus its checked source identity."""

    identity: StaticSymbolIdentity
    target: Callable[..., object] = field(repr=False, compare=False)

    @classmethod
    def capture(cls, target: Callable[..., object]) -> StaticCallableRef:
        if not callable(target):
            raise TypeError("StaticCallableRef target must be callable")
        module = getattr(target, "__module__", None)
        qualname = getattr(target, "__qualname__", None)
        if type(module) is not str or type(qualname) is not str:
            raise TypeError("StaticCallableRef target lacks module/qualname identity")
        return cls(
            identity=StaticSymbolIdentity(module=module, qualname=qualname),
            target=target,
        )

    def __post_init__(self) -> None:
        if type(self.identity) is not StaticSymbolIdentity:
            raise TypeError("StaticCallableRef.identity must be StaticSymbolIdentity")
        if not callable(self.target):
            raise TypeError("StaticCallableRef target must be callable")
        if getattr(self.target, "__module__", None) != self.identity.module:
            raise ValueError("StaticCallableRef module differs from its target")
        if getattr(self.target, "__qualname__", None) != self.identity.qualname:
            raise ValueError("StaticCallableRef qualname differs from its target")


@dataclass(frozen=True, slots=True)
class StaticObjectRef(Generic[_T]):
    """A direct non-discoverable object reference plus its checked type identity."""

    identity: StaticSymbolIdentity
    target: _T = field(repr=False, compare=False)

    @classmethod
    def capture(cls, target: _T) -> StaticObjectRef[_T]:
        identity_source: object = target if isinstance(target, type) else type(target)
        module = getattr(identity_source, "__module__", None)
        qualname = getattr(identity_source, "__qualname__", None)
        if type(module) is not str or type(qualname) is not str:
            raise TypeError("StaticObjectRef target lacks module/qualname identity")
        return cls(
            identity=StaticSymbolIdentity(module=module, qualname=qualname),
            target=target,
        )

    def __post_init__(self) -> None:
        if type(self.identity) is not StaticSymbolIdentity:
            raise TypeError("StaticObjectRef.identity must be StaticSymbolIdentity")
        identity_source: object = self.target if isinstance(self.target, type) else type(self.target)
        if getattr(identity_source, "__module__", None) != self.identity.module:
            raise ValueError("StaticObjectRef module differs from its target type")
        if getattr(identity_source, "__qualname__", None) != self.identity.qualname:
            raise ValueError("StaticObjectRef qualname differs from its target type")


class PluginProviderKind(Enum):
    FACTORY = "factory"
    INSTANCE = "instance"


@dataclass(frozen=True, slots=True)
class PluginProviderSpec:
    kind: PluginProviderKind
    provider: StaticObjectRef[object]

    def __post_init__(self) -> None:
        if type(self.kind) is not PluginProviderKind:
            raise TypeError("PluginProviderSpec.kind must be PluginProviderKind")
        if type(self.provider) is not StaticObjectRef:
            raise TypeError("PluginProviderSpec.provider must be StaticObjectRef")
        if self.kind is PluginProviderKind.FACTORY and not isinstance(self.provider.target, type):
            raise TypeError("factory plugin provider must reference a class")
        if self.kind is PluginProviderKind.INSTANCE and isinstance(self.provider.target, type):
            raise TypeError("instance plugin provider cannot reference a class")

    def build(self) -> FamilyPlugin:
        """Build/return the statically referenced plugin; no discovery occurs."""

        if self.kind is PluginProviderKind.FACTORY:
            plugin_type = cast(type[object], self.provider.target)
            return cast(FamilyPlugin, plugin_type())
        return cast(FamilyPlugin, self.provider.target)


class SnapshotProjectionKind(Enum):
    REGION_CAPACITY = "master_domain_projection"
    SHAPE_PACKING_HALL = "shape_packing_hall_master_domain_projection"
    POWER_HITTING_SET = "power_hitting_set_master_domain_projection"


@dataclass(frozen=True, slots=True)
class SnapshotInputSpec:
    family_input_key: str
    record_type: StaticSymbolIdentity

    def __post_init__(self) -> None:
        _require_token(
            self.family_input_key,
            field_name="SnapshotInputSpec.family_input_key",
        )
        if type(self.record_type) is not StaticSymbolIdentity:
            raise TypeError("SnapshotInputSpec.record_type must be StaticSymbolIdentity")


@dataclass(frozen=True, slots=True)
class SnapshotProjectionSpec:
    kind: SnapshotProjectionKind
    builder: StaticSymbolIdentity

    def __post_init__(self) -> None:
        if type(self.kind) is not SnapshotProjectionKind:
            raise TypeError("SnapshotProjectionSpec.kind must be SnapshotProjectionKind")
        if type(self.builder) is not StaticSymbolIdentity:
            raise TypeError("SnapshotProjectionSpec.builder must be StaticSymbolIdentity")


@dataclass(frozen=True, slots=True)
class LoweringSpec:
    operation: ConstraintOperation
    typed_apply_entrypoint: StaticCallableRef
    master_primitive: str

    def __post_init__(self) -> None:
        if self.operation not in SUPPORTED_OPERATIONS:
            raise ValueError(f"unknown closed lowering operation {self.operation!r}")
        if type(self.typed_apply_entrypoint) is not StaticCallableRef:
            raise TypeError("LoweringSpec.typed_apply_entrypoint must be StaticCallableRef")
        primitive = _require_token(
            self.master_primitive,
            field_name="LoweringSpec.master_primitive",
        )
        if not primitive.startswith("_lower_"):
            raise ValueError("master primitive must be an explicit _lower_* method")


class ReplayKind(Enum):
    TYPED_SINGLE_ENTRY = "typed_single_entry"
    LEGACY_DIAGNOSTIC = "legacy_diagnostic"


@dataclass(frozen=True, slots=True)
class ReplaySpec:
    kind: ReplayKind
    entrypoint: StaticCallableRef

    def __post_init__(self) -> None:
        if type(self.kind) is not ReplayKind:
            raise TypeError("ReplaySpec.kind must be ReplayKind")
        if type(self.entrypoint) is not StaticCallableRef:
            raise TypeError("ReplaySpec.entrypoint must be StaticCallableRef")


class TelemetryProfile(Enum):
    EXPERIMENTAL = "experimental"
    TYPED_COMPILED = "typed_compiled"
    TYPED_ENABLED = "typed_enabled"
    TYPED_SHADOW = "typed_shadow"
    LEGACY_DIAGNOSTIC = "legacy_diagnostic"
    RETIRED = "retired"


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
class ProofSchemaSpec:
    """Static mirror of one family's current cert-payload envelope."""

    family: str
    schema_version: int
    cert_kind: str
    allowed_fields: frozenset[str]
    required_fields: frozenset[str]

    def __post_init__(self) -> None:
        _require_token(self.family, field_name="ProofSchemaSpec.family")
        if type(self.schema_version) is not int or self.schema_version <= 0:
            raise ValueError("ProofSchemaSpec.schema_version must be a positive exact int")
        _require_token(self.cert_kind, field_name="ProofSchemaSpec.cert_kind")
        if type(self.allowed_fields) is not frozenset:
            raise TypeError("ProofSchemaSpec.allowed_fields must be frozenset")
        if type(self.required_fields) is not frozenset:
            raise TypeError("ProofSchemaSpec.required_fields must be frozenset")
        _validate_token_set(
            self.allowed_fields,
            field_name=f"{self.family}.proof_schema.allowed_fields",
        )
        _validate_token_set(
            self.required_fields,
            field_name=f"{self.family}.proof_schema.required_fields",
        )
        if "cert_kind" not in self.required_fields:
            raise ValueError("ProofSchemaSpec.required_fields must include cert_kind")
        if not self.required_fields <= self.allowed_fields:
            raise ValueError("ProofSchemaSpec.required_fields must be a subset of allowed_fields")


@dataclass(frozen=True, slots=True)
class FamilyTrustSpec:
    """The shadow trust row for one current family."""

    capability: FamilyCapability
    proof_schema: CapabilityAvailability[ProofSchemaSpec]
    rule_semantics: tuple[VersionedRuleRef, ...]
    authority_dependency_closure: frozenset[str]
    consumed_snapshot_field_ids: frozenset[str]
    typed_plugin: CapabilityAvailability[PluginProviderSpec]
    production_exact_checker: CapabilityAvailability[
        StaticCallableRef | StaticSymbolIdentity
    ]
    snapshot_input: CapabilityAvailability[SnapshotInputSpec]
    master_domain_projection: CapabilityAvailability[SnapshotProjectionSpec]
    lowering: CapabilityAvailability[LoweringSpec]
    replay: CapabilityAvailability[ReplaySpec]
    telemetry_profile: TelemetryProfile
    required_contract_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.capability) is not FamilyCapability:
            raise TypeError("FamilyTrustSpec.capability must be FamilyCapability")
        _validate_availability(
            self.proof_schema,
            available_types=(ProofSchemaSpec,),
            field_name=f"{self.capability.name}.proof_schema",
        )
        _validate_availability(
            self.typed_plugin,
            available_types=(PluginProviderSpec,),
            field_name=f"{self.capability.name}.typed_plugin",
        )
        _validate_availability(
            self.production_exact_checker,
            available_types=(StaticCallableRef, StaticSymbolIdentity),
            field_name=f"{self.capability.name}.production_exact_checker",
        )
        _validate_availability(
            self.snapshot_input,
            available_types=(SnapshotInputSpec,),
            field_name=f"{self.capability.name}.snapshot_input",
        )
        _validate_availability(
            self.master_domain_projection,
            available_types=(SnapshotProjectionSpec,),
            field_name=f"{self.capability.name}.master_domain_projection",
        )
        _validate_availability(
            self.lowering,
            available_types=(LoweringSpec,),
            field_name=f"{self.capability.name}.lowering",
        )
        _validate_availability(
            self.replay,
            available_types=(ReplaySpec,),
            field_name=f"{self.capability.name}.replay",
        )
        if self.proof_schema.is_available:
            proof_schema = cast(
                ProofSchemaSpec,
                self.proof_schema.require(
                    family=self.capability.name,
                    capability="proof schema",
                ),
            )
            if proof_schema.family != self.capability.name:
                raise ValueError("proof schema family differs from FamilyCapability")
            if proof_schema.schema_version != self.capability.proof_schema_version:
                raise ValueError("proof schema version differs from FamilyCapability")
        if type(self.rule_semantics) is not tuple or not self.rule_semantics:
            raise TypeError("FamilyTrustSpec.rule_semantics must be a non-empty exact tuple")
        if any(type(item) is not VersionedRuleRef for item in self.rule_semantics):
            raise TypeError(
                "FamilyTrustSpec.rule_semantics must contain VersionedRuleRef"
            )
        if len({item.rule_id for item in self.rule_semantics}) != len(self.rule_semantics):
            raise ValueError("FamilyTrustSpec.rule_semantics cannot contain duplicate rule IDs")
        if self.rule_semantics[0].rule_id != self.capability.name:
            raise ValueError("the first rule semantic id must be the family name")
        if type(self.authority_dependency_closure) is not frozenset:
            raise TypeError("authority_dependency_closure must be frozenset")
        if self.authority_dependency_closure != self.capability.required_dependencies:
            raise ValueError("shadow authority dependency closure differs from FamilyCapability")
        _validate_token_set(
            self.authority_dependency_closure,
            field_name=f"{self.capability.name}.authority_dependency_closure",
        )
        if type(self.consumed_snapshot_field_ids) is not frozenset:
            raise TypeError("consumed_snapshot_field_ids must be frozenset")
        _validate_token_set(
            self.consumed_snapshot_field_ids,
            field_name=f"{self.capability.name}.consumed_snapshot_field_ids",
        )
        if type(self.telemetry_profile) is not TelemetryProfile:
            raise TypeError("FamilyTrustSpec.telemetry_profile must be TelemetryProfile")
        _validate_unique_tokens(
            self.required_contract_ids,
            field_name=f"{self.capability.name}.required_contract_ids",
        )
        if not self.required_contract_ids:
            raise ValueError("FamilyTrustSpec.required_contract_ids cannot be empty")
        unknown_contracts = frozenset(self.required_contract_ids) - FAMILY_CONTRACT_IDS_V1
        if unknown_contracts:
            raise ValueError(
                f"{self.capability.name}.required_contract_ids contains unknown contract IDs: "
                f"{sorted(unknown_contracts)!r}"
            )
        self._validate_capability_coherence()

    @property
    def family(self) -> str:
        return cast(str, self.capability.name)

    @property
    def rule_semantic_ids(self) -> tuple[str, ...]:
        return tuple(item.rule_id for item in self.rule_semantics)

    def _validate_capability_coherence(self) -> None:
        stage = self.capability.stage
        path = self.capability.execution_path
        plugin_available = self.typed_plugin.is_available
        input_available = self.snapshot_input.is_available
        projection_available = self.master_domain_projection.is_available
        lowering_available = self.lowering.is_available
        replay_available = self.replay.is_available

        def require_contracts(minimum: frozenset[str]) -> None:
            missing = minimum - frozenset(self.required_contract_ids)
            if missing:
                raise ValueError(
                    f"{self.family}.required_contract_ids is missing stage/path "
                    f"contract(s): {sorted(missing)!r}"
                )

        if stage is CapabilityStage.RETIRED:
            if any(
                (
                    self.proof_schema.is_available,
                    plugin_available,
                    input_available,
                    projection_available,
                    lowering_available,
                    replay_available,
                    self.production_exact_checker.is_available,
                )
            ):
                raise ValueError("retired family cannot advertise live trust capabilities")
            if self.consumed_snapshot_field_ids:
                raise ValueError("retired family cannot advertise consumed snapshot fields")
            if self.telemetry_profile is not TelemetryProfile.RETIRED:
                raise ValueError("retired family requires retired telemetry profile")
            require_contracts(frozenset({"retired_fail_closed"}))
            return

        if not self.proof_schema.is_available:
            raise ValueError("live family requires an explicit proof schema")

        if stage is CapabilityStage.EXPERIMENTAL:
            if path is not ExecutionPath.TYPED:
                raise ValueError("experimental family requires the typed execution path")
            if projection_available or lowering_available or replay_available:
                raise ValueError(
                    "experimental family cannot advertise production projection/lowering/replay"
                )
            if plugin_available is not input_available:
                raise ValueError(
                    "experimental plugin and snapshot input availability must agree"
                )
            if not input_available and self.consumed_snapshot_field_ids:
                raise ValueError(
                    "experimental family without snapshot input cannot consume snapshot fields"
                )
            if self.telemetry_profile is not TelemetryProfile.EXPERIMENTAL:
                raise ValueError("experimental family requires experimental telemetry")
            require_contracts(
                frozenset(
                    {
                        "experimental_fail_closed",
                        "tcb_fault_propagation",
                        "unknown_type",
                    }
                )
            )
            return

        if path is ExecutionPath.LEGACY_DIAGNOSTIC:
            if plugin_available or input_available or projection_available or lowering_available:
                raise ValueError("legacy diagnostic family cannot advertise typed capabilities")
            if self.production_exact_checker.is_available:
                raise ValueError("legacy diagnostic family cannot advertise a production exact checker")
            if self.consumed_snapshot_field_ids:
                raise ValueError("legacy diagnostic family cannot consume ValidatedStateSnapshot")
            if not replay_available:
                raise ValueError("live legacy diagnostic family requires replay")
            if self.telemetry_profile is not TelemetryProfile.LEGACY_DIAGNOSTIC:
                raise ValueError("legacy diagnostic family requires legacy telemetry")
            require_contracts(
                frozenset(
                    {
                        "hold_and_quarantine",
                        "legacy_diagnostic_replay_hold",
                        "tcb_fault_propagation",
                        "unknown_type",
                    }
                )
            )
            return

        if not plugin_available or not input_available or not replay_available:
            raise ValueError("live typed family requires plugin, snapshot input, and replay")
        if stage in {CapabilityStage.COMPILABLE, CapabilityStage.ENABLED}:
            if not projection_available or not lowering_available:
                raise ValueError("compilable family requires projection and lowering")
            expected_telemetry = (
                TelemetryProfile.TYPED_ENABLED
                if stage is CapabilityStage.ENABLED
                else TelemetryProfile.TYPED_COMPILED
            )
            if self.telemetry_profile is not expected_telemetry:
                raise ValueError(
                    "compilable/enabled family has the wrong typed telemetry profile"
                )
            require_contracts(frozenset(_typed_contracts(compiled=True)))
            if stage is CapabilityStage.ENABLED:
                require_contracts(frozenset({"enabled_authority_gate"}))
        else:
            if projection_available or lowering_available:
                raise ValueError("non-compilable typed family cannot advertise projection/lowering")
            if self.telemetry_profile is not TelemetryProfile.TYPED_SHADOW:
                raise ValueError("non-compilable typed family requires typed-shadow telemetry")
            require_contracts(frozenset(_typed_contracts(compiled=False)))


class GenerationSurface(Enum):
    EXPERIMENTAL = "experimental"
    TYPED_ATTACH = "typed_attach"
    LEGACY_DIAGNOSTIC = "legacy_diagnostic"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class FamilyGenerationSpec:
    """The untrusted generation row, intentionally separate from trust."""

    family: str
    surface: GenerationSurface
    oracle_name: CapabilityAvailability[str]
    family_version: CapabilityAvailability[str]
    validator_version: CapabilityAvailability[str]
    generator: CapabilityAvailability[StaticCallableRef]
    generation_invoker: CapabilityAvailability[StaticSymbolIdentity]
    adapter_factory: CapabilityAvailability[
        StaticCallableRef | StaticSymbolIdentity
    ]
    preparation_steps: tuple[StaticSymbolIdentity, ...]
    generator_parameter_ids: tuple[str, ...]
    orchestration_context_ids: tuple[str, ...]
    production_typed_order: int | None

    def __post_init__(self) -> None:
        _require_token(self.family, field_name="FamilyGenerationSpec.family")
        if type(self.surface) is not GenerationSurface:
            raise TypeError("FamilyGenerationSpec.surface must be GenerationSurface")
        for field_name, value in (
            ("oracle_name", self.oracle_name),
            ("family_version", self.family_version),
            ("validator_version", self.validator_version),
        ):
            _validate_availability(
                value,
                available_types=(str,),
                field_name=f"{self.family}.{field_name}",
            )
            if value.is_available:
                _require_token(
                    value.require(family=self.family, capability=field_name),
                    field_name=f"{self.family}.{field_name}",
                )
        _validate_availability(
            self.generator,
            available_types=(StaticCallableRef,),
            field_name=f"{self.family}.generator",
        )
        _validate_availability(
            self.generation_invoker,
            available_types=(StaticSymbolIdentity,),
            field_name=f"{self.family}.generation_invoker",
        )
        _validate_availability(
            self.adapter_factory,
            available_types=(StaticCallableRef, StaticSymbolIdentity),
            field_name=f"{self.family}.adapter_factory",
        )
        _validate_unique_tokens(
            self.generator_parameter_ids,
            field_name=f"{self.family}.generator_parameter_ids",
        )
        _validate_unique_tokens(
            self.orchestration_context_ids,
            field_name=f"{self.family}.orchestration_context_ids",
        )
        if type(self.preparation_steps) is not tuple:
            raise TypeError(f"{self.family}.preparation_steps must be an exact tuple")
        if any(type(item) is not StaticSymbolIdentity for item in self.preparation_steps):
            raise TypeError(
                f"{self.family}.preparation_steps must contain StaticSymbolIdentity"
            )
        if len(set(self.preparation_steps)) != len(self.preparation_steps):
            raise ValueError(f"{self.family}.preparation_steps contains duplicates")
        if self.surface is GenerationSurface.RETIRED:
            if any(
                (
                    self.oracle_name.is_available,
                    self.family_version.is_available,
                    self.validator_version.is_available,
                    self.generator.is_available,
                    self.generation_invoker.is_available,
                    self.adapter_factory.is_available,
                )
            ):
                raise ValueError(
                    "retired generation row cannot advertise version/generator/adapter"
                )
            if self.generator_parameter_ids or self.orchestration_context_ids:
                raise ValueError("retired generation row cannot advertise generation inputs")
            if self.production_typed_order is not None:
                raise ValueError("retired generation row cannot have typed order")
            return
        if not self.generator.is_available:
            raise ValueError("live generation row requires an explicit generator")
        if not all(
            (
                self.oracle_name.is_available,
                self.family_version.is_available,
                self.validator_version.is_available,
            )
        ):
            raise ValueError("live generation row requires oracle and wire versions")
        generator = cast(
            StaticCallableRef,
            self.generator.require(
                family=self.family,
                capability="generator",
            ),
        )
        actual_parameters = tuple(inspect.signature(generator.target).parameters)
        if actual_parameters != self.generator_parameter_ids:
            raise ValueError(
                f"{self.family}.generator_parameter_ids differs from generator signature"
            )
        if self.surface is GenerationSurface.TYPED_ATTACH:
            if not self.generation_invoker.is_available:
                raise ValueError(
                    "typed attach generation requires a static uniform invoker"
                )
            if type(self.production_typed_order) is not int or self.production_typed_order < 0:
                raise ValueError("typed attach generation requires a non-negative exact order")
            if not self.orchestration_context_ids:
                raise ValueError("typed attach generation requires orchestration context IDs")
        elif self.surface is GenerationSurface.EXPERIMENTAL:
            if self.generation_invoker.is_available:
                raise ValueError(
                    "experimental generation cannot advertise a production invoker"
                )
            if self.production_typed_order is not None:
                raise ValueError("experimental generation cannot have typed attach order")
            if self.orchestration_context_ids:
                raise ValueError(
                    "experimental generation has no production orchestration context"
                )
        else:
            if self.generation_invoker.is_available:
                raise ValueError(
                    "legacy diagnostic generation cannot advertise a typed invoker"
                )
            if self.production_typed_order is not None:
                raise ValueError(
                    "legacy diagnostic generation cannot have typed attach order"
                )
            if self.orchestration_context_ids:
                raise ValueError(
                    "legacy diagnostic generation has no production orchestration context"
                )


def _validate_unique_tokens(values: tuple[str, ...], *, field_name: str) -> None:
    if type(values) is not tuple:
        raise TypeError(f"{field_name} must be an exact tuple")
    for value in values:
        _require_token(value, field_name=field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} contains duplicates")


def _validate_token_set(values: frozenset[str], *, field_name: str) -> None:
    for value in values:
        _require_token(value, field_name=field_name)


def _validate_availability(
    value: object,
    *,
    available_types: tuple[type[object], ...],
    field_name: str,
) -> None:
    if type(value) is UnavailableCapability:
        return
    if type(value) is not AvailableCapability:
        raise TypeError(
            f"{field_name} must be AvailableCapability or UnavailableCapability"
        )
    if type(value.value) not in available_types:
        expected = ", ".join(item.__name__ for item in available_types)
        raise TypeError(f"{field_name} available value must be one of: {expected}")


def _audit_value(value: object) -> object:
    """Project manifest data to canonical audit metadata.

    Callable and plugin objects are represented only by their checked static
    identities.  Unsupported future field types fail closed instead of being
    stringified nondeterministically.
    """

    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, Enum):
        return value.value
    if type(value) is StaticCallableRef:
        return {
            "module": value.identity.module,
            "qualname": value.identity.qualname,
        }
    if type(value) is StaticObjectRef:
        return {
            "module": value.identity.module,
            "qualname": value.identity.qualname,
        }
    if type(value) is StaticSymbolIdentity:
        return {
            "module": value.module,
            "qualname": value.qualname,
        }
    if type(value) is AvailableCapability:
        return {
            "available": True,
            "value": _audit_value(value.value),
        }
    if type(value) is UnavailableCapability:
        return {
            "available": False,
            "reason": value.reason,
        }
    if isinstance(value, Mapping):
        projected: dict[str, object] = {}
        for key, item in value.items():
            checked_key = _require_token(key, field_name="family manifest audit mapping key")
            projected[checked_key] = _audit_value(item)
        return {key: projected[key] for key in sorted(projected)}
    if type(value) is tuple:
        return [_audit_value(item) for item in cast(tuple[object, ...], value)]
    if type(value) is list:
        return [_audit_value(item) for item in cast(list[object], value)]
    if type(value) is set:
        projected_items = [
            _audit_value(item) for item in cast(set[object], value)
        ]
        return sorted(
            projected_items,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    if type(value) is frozenset:
        projected_items = [
            _audit_value(item) for item in cast(frozenset[object], value)
        ]
        return sorted(
            projected_items,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _audit_value(getattr(value, item.name))
            for item in dataclass_fields(value)
        }
    raise TypeError(
        f"family manifest audit projection does not support {type(value).__name__}"
    )


@dataclass(frozen=True, slots=True, init=False)
class FamilySpecRegistry:
    """Immutable, exhaustively checked F1--F9 shadow manifest."""

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
            raise TypeError("FamilySpecRegistry.rule_semantics must be RuleSemanticRegistry")
        checked_trust = _checked_spec_mapping(
            trust_specs,
            expected_type=FamilyTrustSpec,
            field_name="trust_specs",
        )
        checked_generation = _checked_spec_mapping(
            generation_specs,
            expected_type=FamilyGenerationSpec,
            field_name="generation_specs",
        )
        if frozenset(checked_trust) != frozenset(checked_generation):
            raise ValueError("trust and generation manifests must cover the same families")
        _validate_unique_tokens(
            typed_generation_order,
            field_name="typed_generation_order",
        )
        derived_order = tuple(
            spec.family
            for spec in sorted(
                (
                    spec
                    for spec in checked_generation.values()
                    if spec.production_typed_order is not None
                ),
                key=lambda spec: cast(int, spec.production_typed_order),
            )
        )
        derived_indices = tuple(
            cast(int, checked_generation[family].production_typed_order)
            for family in derived_order
        )
        if derived_indices != tuple(range(len(derived_indices))):
            raise ValueError("typed generation order indices must be contiguous from zero")
        if derived_order != typed_generation_order:
            raise ValueError("typed generation order differs from generation rows")
        for family, generation in checked_generation.items():
            trust = checked_trust[family]
            missing_rule_ids = (
                frozenset(trust.rule_semantic_ids) - frozenset(rule_semantics.rules)
            )
            if missing_rule_ids:
                raise ValueError(
                    f"family {family!r} references unknown rule semantic IDs: "
                    f"{sorted(missing_rule_ids)!r}"
                )
            for rule_ref in trust.rule_semantics:
                actual_version = rule_semantics.get(rule_ref.rule_id).semantic_version
                if rule_ref.semantic_version != actual_version:
                    raise ValueError(
                        f"family {family!r} pins rule {rule_ref.rule_id!r} at "
                        f"{rule_ref.semantic_version!r}, current version is "
                        f"{actual_version!r}"
                    )
            family_rule = rule_semantics.get(family)
            expected_rule_closure = (
                VersionedRuleRef(
                    rule_id=family,
                    semantic_version=family_rule.semantic_version,
                ),
                *family_rule.semantic_dependencies,
                *family_rule.protocol_obligations,
            )
            if trust.rule_semantics != expected_rule_closure:
                raise ValueError(
                    f"family {family!r} rule semantic closure differs from rule ledger"
                )
            expected_rule_state = {
                (
                    CapabilityStage.EXPERIMENTAL,
                    ExecutionPath.TYPED,
                ): RuleDeploymentState.EXPERIMENTAL,
                (
                    CapabilityStage.COMPILABLE,
                    ExecutionPath.TYPED,
                ): RuleDeploymentState.COMPILABLE,
                (
                    CapabilityStage.ENABLED,
                    ExecutionPath.TYPED,
                ): RuleDeploymentState.ENABLED,
                (
                    CapabilityStage.VALIDATED,
                    ExecutionPath.TYPED,
                ): RuleDeploymentState.VALIDATED_SHADOW_ONLY,
                (
                    CapabilityStage.VALIDATED,
                    ExecutionPath.LEGACY_DIAGNOSTIC,
                ): RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC,
                (
                    CapabilityStage.RETIRED,
                    ExecutionPath.LEGACY_DIAGNOSTIC,
                ): RuleDeploymentState.RETIRED,
            }.get((trust.capability.stage, trust.capability.execution_path))
            if expected_rule_state is None:
                raise ValueError(
                    f"family {family!r} has no registered rule deployment-state mapping"
                )
            if family_rule.deployment_state is not expected_rule_state:
                raise ValueError(
                    f"family {family!r} rule deployment state differs from capability"
                )
            if generation.family_version.is_available:
                generated_family_version = generation.family_version.require(
                    family=family,
                    capability="family version",
                )
                if generated_family_version != family_rule.semantic_version:
                    raise ValueError(
                        f"family {family!r} generated family version differs "
                        "from rule semantic version"
                    )
            if (
                family_rule.exact_twin_checker.is_available
                is not trust.production_exact_checker.is_available
            ):
                raise ValueError(
                    f"family {family!r} exact-checker availability differs from rule ledger"
                )
            if trust.production_exact_checker.is_available:
                family_checker = trust.production_exact_checker.require(
                    family=family,
                    capability="production exact checker",
                )
                checker_identity = (
                    family_checker.identity
                    if type(family_checker) is StaticCallableRef
                    else cast(StaticSymbolIdentity, family_checker)
                )
                rule_checker = family_rule.exact_twin_checker
                if type(rule_checker) is not AvailableExactChecker:
                    raise ValueError(
                        f"family {family!r} rule checker must be AvailableExactChecker"
                    )
                if (
                    checker_identity.module != rule_checker.module
                    or checker_identity.qualname != rule_checker.qualname
                ):
                    raise ValueError(
                        f"family {family!r} exact-checker identity differs from rule ledger"
                    )
            if generation.surface is GenerationSurface.TYPED_ATTACH:
                if trust.capability.execution_path is not ExecutionPath.TYPED:
                    raise ValueError("typed attach generator requires typed trust path")
                if trust.capability.stage in {
                    CapabilityStage.EXPERIMENTAL,
                    CapabilityStage.RETIRED,
                }:
                    raise ValueError(
                        "experimental/retired family cannot have typed attach generator"
                    )
            elif generation.surface is GenerationSurface.EXPERIMENTAL:
                if trust.capability.stage is not CapabilityStage.EXPERIMENTAL:
                    raise ValueError(
                        "experimental generation requires experimental trust stage"
                    )
            elif generation.surface is GenerationSurface.LEGACY_DIAGNOSTIC:
                if trust.capability.execution_path is not ExecutionPath.LEGACY_DIAGNOSTIC:
                    raise ValueError("legacy generator requires legacy diagnostic trust path")
            elif trust.capability.stage is not CapabilityStage.RETIRED:
                raise ValueError("only a retired trust row may have retired generation")
        projection = {
            "generation_specs": _audit_value(checked_generation),
            "rule_semantics_audit_digest": rule_semantics.audit_digest,
            "schema_version": schema_version,
            "trust_specs": _audit_value(checked_trust),
            "typed_generation_order": _audit_value(typed_generation_order),
        }
        audit_digest = hashlib.sha256(
            _FAMILY_MANIFEST_AUDIT_PREFIX
            + json.dumps(
                projection,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "rule_semantics", rule_semantics)
        object.__setattr__(self, "trust_specs", MappingProxyType(checked_trust))
        object.__setattr__(
            self,
            "generation_specs",
            MappingProxyType(checked_generation),
        )
        object.__setattr__(self, "typed_generation_order", typed_generation_order)
        object.__setattr__(self, "audit_digest", audit_digest)

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
            "generation_specs": _audit_value(self.generation_specs),
            "rule_semantics_audit_digest": self.rule_semantics.audit_digest,
            "schema_version": self.schema_version,
            "trust_specs": _audit_value(self.trust_specs),
            "typed_generation_order": _audit_value(self.typed_generation_order),
        }


def _checked_spec_mapping(
    raw: Mapping[str, object],
    *,
    expected_type: type[_T],
    field_name: str,
) -> dict[str, _T]:
    if not isinstance(raw, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    checked: dict[str, _T] = {}
    for raw_family, raw_spec in raw.items():
        family = _require_token(raw_family, field_name=f"{field_name} key")
        if type(raw_spec) is not expected_type:
            raise TypeError(f"{field_name}[{family!r}] must be {expected_type.__name__}")
        spec = raw_spec
        if getattr(spec, "family", None) != family:
            raise ValueError(f"{field_name} key {family!r} differs from spec.family")
        checked[family] = spec
    return checked


PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE: Final = frozenset(
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

_COMMON_TYPED_SNAPSHOT_FIELDS: Final = frozenset(
    {
        "artifact_hashes",
        "digest",
        "exterior_blocks_digest",
        "oracle_capabilities",
        "source_digest",
    }
)
_GHOST_BOUND_SNAPSHOT_FIELDS: Final = frozenset(
    {
        "blocked_cells_digest",
        "ghost",
    }
)

_TYPED_REPLAY = ReplaySpec(
    kind=ReplayKind.TYPED_SINGLE_ENTRY,
    entrypoint=StaticCallableRef.capture(validate_and_compile_cut),
)
_TYPED_APPLY = StaticCallableRef.capture(apply_compiled_cut)

_REGION_PLUGIN = PluginProviderSpec(
    kind=PluginProviderKind.FACTORY,
    provider=StaticObjectRef.capture(RegionCapacityPlugin),
)
_F5_PLUGIN = PluginProviderSpec(
    kind=PluginProviderKind.INSTANCE,
    provider=StaticObjectRef.capture(_PRODUCTION_F5_PLUGIN),
)
_HALL_PLUGIN = PluginProviderSpec(
    kind=PluginProviderKind.FACTORY,
    provider=StaticObjectRef.capture(ShapePackingHallPlugin),
)
_POWER_PLUGIN = PluginProviderSpec(
    kind=PluginProviderKind.FACTORY,
    provider=StaticObjectRef.capture(PowerHittingSetPlugin),
)


def _capability(
    *,
    name: str,
    mode: FamilyMode,
    validator_version: str,
    compiler_version: str | None,
    stage: CapabilityStage,
    execution_path: ExecutionPath,
    requires_ghost_bound: bool = False,
) -> FamilyCapability:
    return FamilyCapability(
        name=name,
        mode=mode,
        proof_schema_version=1,
        validator_version=validator_version,
        compiler_version=compiler_version,
        stage=stage,
        required_dependencies=PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE,
        execution_path=execution_path,
        requires_ghost_bound=requires_ghost_bound,
    )


def _legacy_replay(target: Callable[..., object]) -> AvailableCapability[ReplaySpec]:
    return _available(
        ReplaySpec(
            kind=ReplayKind.LEGACY_DIAGNOSTIC,
            entrypoint=StaticCallableRef.capture(target),
        )
    )


def _typed_contracts(*, compiled: bool) -> tuple[str, ...]:
    common = (
        "hold_and_quarantine",
        "malformed_proof",
        "premise_and_version_drift",
        "stale_snapshot",
        "replay_fail_closed",
        "tcb_fault_propagation",
        "unknown_type",
    )
    if not compiled:
        return common + ("shadow_zero_master_mutation", "independent_exact_checker")
    return common + (
        "wrong_strengthening",
        "apply_atomicity",
        "master_proto_unchanged_on_rejection",
        "proof_plan_interpreter_tiny_master_exact_chain",
    )


def _proof_schema(
    *,
    family: str,
    cert_kind: str,
    fields: tuple[str, ...],
) -> AvailableCapability[ProofSchemaSpec]:
    field_set = frozenset(fields)
    return _available(
        ProofSchemaSpec(
            family=family,
            schema_version=1,
            cert_kind=cert_kind,
            allowed_fields=field_set,
            required_fields=field_set,
        )
    )


def _rule_refs(*refs: tuple[str, str]) -> tuple[VersionedRuleRef, ...]:
    return tuple(
        VersionedRuleRef(rule_id=rule_id, semantic_version=semantic_version)
        for rule_id, semantic_version in refs
    )


_PROOF_SCHEMAS_V1: Final[Mapping[str, AvailableCapability[ProofSchemaSpec]]] = MappingProxyType(
    {
        "region_capacity": _proof_schema(
            family="region_capacity",
            cert_kind="region_capacity_combinatorial",
            fields=(
                "cert_kind",
                "region_kind",
                "region_cells_bitset_b64",
                "cap_R",
                "demand_R",
                "gap",
                "contributing_groups",
                "cells_per_pose",
                "lp_dual_ray_b64",
                "lp_dual_objective",
            ),
        ),
        "cutset": _proof_schema(
            family="cutset",
            cert_kind="menger_min_cut",
            fields=(
                "cert_kind",
                "side_a_bitset_b64",
                "side_b_bitset_b64",
                "cut_edges",
                "cut_size",
                "commodity_demand",
                "contributing_commodities",
            ),
        ),
        "port_exposure": _proof_schema(
            family="port_exposure",
            cert_kind="port_exposure_blocked",
            fields=(
                "cert_kind",
                "facility_group",
                "facility_pose_id",
                "port_cell",
                "port_direction",
                "front_cell",
                "blocking_facility",
                "active_port_witness_b64",
            ),
        ),
        "component_reach": _proof_schema(
            family="component_reach",
            cert_kind="bfs_disconnect_witness",
            fields=(
                "cert_kind",
                "commodity_id",
                "src_cell",
                "sink_cell",
                "src_component_bitset_b64",
                "sink_component_bitset_b64",
                "separator_cells",
                "blocking_facilities",
            ),
        ),
        "pattern_nogood": _proof_schema(
            family="pattern_nogood",
            cert_kind="bounded_deletion_core",
            fields=(
                "cert_kind",
                "sub_problem_oracle_name",
                "sub_problem_oracle_version",
                "forbidden_pose_pattern",
                "core_minimization",
            ),
        ),
        "shape_packing_hall": _proof_schema(
            family="shape_packing_hall",
            cert_kind="hall_interval_witness",
            fields=(
                "cert_kind",
                "region_kind",
                "region_total_length",
                "partition_lens",
                "partition_offsets",
                "pose_length",
                "pose_shape_canonical",
                "max_packable",
                "total_packable",
                "contributing_group",
                "region_demand",
                "group_demand",
                "ghost_rect_repr",
                "exterior_blocks_digest",
            ),
        ),
        "power_hitting_set": _proof_schema(
            family="power_hitting_set",
            cert_kind="power_cover_emptyset_ghost",
            fields=(
                "cert_kind",
                "facility_group",
                "facility_pose_id",
                "facility_cells",
                "pole_radius",
                "pole_shape_canonical",
                "ghost_rect_repr",
                "exterior_blocks_digest",
            ),
        ),
        "density_envelope": _proof_schema(
            family="density_envelope",
            cert_kind="density_envelope_v1",
            fields=(
                "cert_kind",
                "witness_kind",
                "window_rect",
                "group_id",
                "max_allowed_area",
                "oracle_assignment_witness",
                "ghost_rect_repr",
            ),
        ),
    }
)


PRODUCTION_FAMILY_TRUST_SPECS_V1: Final[Mapping[str, FamilyTrustSpec]] = MappingProxyType(
    {
        "region_capacity": FamilyTrustSpec(
            capability=_capability(
                name="region_capacity",
                mode="geometric",
                validator_version=REGION_CAPACITY_VALIDATOR_VERSION,
                compiler_version=REGION_CAPACITY_COMPILER_VERSION,
                stage=CapabilityStage.COMPILABLE,
                execution_path=ExecutionPath.TYPED,
            ),
            proof_schema=_PROOF_SCHEMAS_V1["region_capacity"],
            rule_semantics=_rule_refs(
                ("region_capacity", "v1.2"),
                ("cut_scope_currentness", "v1"),
                ("complete_premise_implication", "v1"),
                ("master_domain_projection_binding", "v1"),
            ),
            authority_dependency_closure=PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE,
            consumed_snapshot_field_ids=_COMMON_TYPED_SNAPSHOT_FIELDS
            | frozenset(
                {
                    "canonical_rules_source_present",
                    "exterior_blocks",
                    "family_inputs.region_capacity.group_demands",
                    "family_inputs.region_capacity.group_pose_domains",
                    "family_inputs.region_capacity.instance_to_facility_type",
                    "family_inputs.region_capacity.pose_occupied_cells",
                    "family_inputs.region_capacity.template_dimensions",
                    "family_inputs.region_capacity.template_placement_rules",
                    "ghost_cells",
                    "master_domain_projection",
                }
            ),
            typed_plugin=_available(_REGION_PLUGIN),
            production_exact_checker=_unavailable(
                "no-production-independent-exact-twin-checker"
            ),
            snapshot_input=_available(
                SnapshotInputSpec(
                    family_input_key="region_capacity",
                    record_type=StaticSymbolIdentity(
                        module="src.cuts.state_snapshot",
                        qualname="F1RegionInputs",
                    ),
                )
            ),
            master_domain_projection=_available(
                SnapshotProjectionSpec(
                    kind=SnapshotProjectionKind.REGION_CAPACITY,
                    builder=StaticSymbolIdentity(
                        module="src.cuts.state_snapshot",
                        qualname="_build_f1_master_domain_projection",
                    ),
                )
            ),
            lowering=_available(
                LoweringSpec(
                    operation="region_capacity_le",
                    typed_apply_entrypoint=_TYPED_APPLY,
                    master_primitive="_lower_region_capacity_cut",
                )
            ),
            replay=_available(_TYPED_REPLAY),
            telemetry_profile=TelemetryProfile.TYPED_COMPILED,
            required_contract_ids=_typed_contracts(compiled=True),
        ),
        "cutset": FamilyTrustSpec(
            capability=_capability(
                name="cutset",
                mode="geometric",
                validator_version="legacy-diagnostic-v1",
                compiler_version=None,
                stage=CapabilityStage.VALIDATED,
                execution_path=ExecutionPath.LEGACY_DIAGNOSTIC,
            ),
            proof_schema=_PROOF_SCHEMAS_V1["cutset"],
            rule_semantics=_rule_refs(
                ("cutset", "v1.0"),
                ("cut_scope_currentness", "v1"),
                ("complete_premise_implication", "v1"),
            ),
            authority_dependency_closure=PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE,
            consumed_snapshot_field_ids=frozenset(),
            typed_plugin=_unavailable("legacy-diagnostic-only"),
            production_exact_checker=_unavailable(
                "legacy-validator-is-not-an-independent-exact-checker"
            ),
            snapshot_input=_unavailable("legacy-replay-reads-bstate"),
            master_domain_projection=_unavailable("no-typed-master-projection"),
            lowering=_unavailable("no-trusted-lowering"),
            replay=_legacy_replay(validate_cutset),
            telemetry_profile=TelemetryProfile.LEGACY_DIAGNOSTIC,
            required_contract_ids=(
                "hold_and_quarantine",
                "legacy_diagnostic_replay_hold",
                "tcb_fault_propagation",
                "unknown_type",
            ),
        ),
        "port_exposure": FamilyTrustSpec(
            capability=_capability(
                name="port_exposure",
                mode="literal",
                validator_version="legacy-diagnostic-v1",
                compiler_version=None,
                stage=CapabilityStage.VALIDATED,
                execution_path=ExecutionPath.LEGACY_DIAGNOSTIC,
            ),
            proof_schema=_PROOF_SCHEMAS_V1["port_exposure"],
            rule_semantics=_rule_refs(
                ("port_exposure", "v1.0"),
                ("cut_scope_currentness", "v1"),
                ("complete_premise_implication", "v1"),
            ),
            authority_dependency_closure=PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE,
            consumed_snapshot_field_ids=frozenset(),
            typed_plugin=_unavailable("legacy-diagnostic-only"),
            production_exact_checker=_unavailable(
                "legacy-validator-is-not-an-independent-exact-checker"
            ),
            snapshot_input=_unavailable("legacy-replay-reads-bstate"),
            master_domain_projection=_unavailable("no-typed-master-projection"),
            lowering=_unavailable("no-trusted-lowering"),
            replay=_legacy_replay(validate_port_exposure),
            telemetry_profile=TelemetryProfile.LEGACY_DIAGNOSTIC,
            required_contract_ids=(
                "hold_and_quarantine",
                "legacy_diagnostic_replay_hold",
                "tcb_fault_propagation",
                "unknown_type",
            ),
        ),
        "component_reach": FamilyTrustSpec(
            capability=_capability(
                name="component_reach",
                mode="geometric",
                validator_version="legacy-diagnostic-v1",
                compiler_version=None,
                stage=CapabilityStage.VALIDATED,
                execution_path=ExecutionPath.LEGACY_DIAGNOSTIC,
            ),
            proof_schema=_PROOF_SCHEMAS_V1["component_reach"],
            rule_semantics=_rule_refs(
                ("component_reach", "v1.1"),
                ("cut_scope_currentness", "v1"),
                ("complete_premise_implication", "v1"),
            ),
            authority_dependency_closure=PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE,
            consumed_snapshot_field_ids=frozenset(),
            typed_plugin=_unavailable("legacy-diagnostic-only"),
            production_exact_checker=_unavailable(
                "legacy-validator-is-not-an-independent-exact-checker"
            ),
            snapshot_input=_unavailable("legacy-replay-reads-bstate"),
            master_domain_projection=_unavailable("no-typed-master-projection"),
            lowering=_unavailable("no-trusted-lowering"),
            replay=_legacy_replay(validate_component_reach),
            telemetry_profile=TelemetryProfile.LEGACY_DIAGNOSTIC,
            required_contract_ids=(
                "hold_and_quarantine",
                "legacy_diagnostic_replay_hold",
                "tcb_fault_propagation",
                "unknown_type",
            ),
        ),
        "pattern_nogood": FamilyTrustSpec(
            capability=_capability(
                name="pattern_nogood",
                mode="literal",
                validator_version="stage-b-f5-shadow-v1",
                compiler_version=None,
                stage=CapabilityStage.VALIDATED,
                execution_path=ExecutionPath.TYPED,
            ),
            proof_schema=_PROOF_SCHEMAS_V1["pattern_nogood"],
            rule_semantics=_rule_refs(
                ("pattern_nogood", "v1.0"),
                ("cut_scope_currentness", "v1"),
                ("complete_premise_implication", "v1"),
            ),
            authority_dependency_closure=PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE,
            consumed_snapshot_field_ids=_COMMON_TYPED_SNAPSHOT_FIELDS
            | frozenset(
                {
                    "family_inputs.pattern_nogood.artifact_hashes",
                    "family_inputs.pattern_nogood.canonical_rules",
                    "family_inputs.pattern_nogood.facility_pools",
                    "family_inputs.pattern_nogood.facility_templates",
                    "family_inputs.pattern_nogood.group_demands",
                    "family_inputs.pattern_nogood.group_pose_domains",
                    "family_inputs.pattern_nogood.instance_to_facility_type",
                    "groups",
                }
            ),
            typed_plugin=_available(_F5_PLUGIN),
            production_exact_checker=_available(
                StaticSymbolIdentity(
                    module="src.cuts.verifiers.binding_empty_domain_verifier",
                    qualname="verify_binding_empty_domain",
                )
            ),
            snapshot_input=_available(
                SnapshotInputSpec(
                    family_input_key="pattern_nogood",
                    record_type=StaticSymbolIdentity(
                        module="src.cuts.state_snapshot",
                        qualname="F5PatternNogoodInputs",
                    ),
                )
            ),
            master_domain_projection=_unavailable("shadow-only-no-master-projection"),
            lowering=_unavailable("shadow-only-no-trusted-lowering"),
            replay=_available(_TYPED_REPLAY),
            telemetry_profile=TelemetryProfile.TYPED_SHADOW,
            required_contract_ids=_typed_contracts(compiled=False),
        ),
        "shape_packing_hall": FamilyTrustSpec(
            capability=_capability(
                name="shape_packing_hall",
                mode="geometric",
                validator_version=SHAPE_PACKING_HALL_VALIDATOR_VERSION,
                compiler_version=SHAPE_PACKING_HALL_COMPILER_VERSION,
                stage=CapabilityStage.COMPILABLE,
                execution_path=ExecutionPath.TYPED,
                requires_ghost_bound=True,
            ),
            proof_schema=_PROOF_SCHEMAS_V1["shape_packing_hall"],
            rule_semantics=_rule_refs(
                ("shape_packing_hall", "v1.0"),
                ("cut_scope_currentness", "v1"),
                ("complete_premise_implication", "v1"),
                ("master_domain_projection_binding", "v1"),
            ),
            authority_dependency_closure=PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE,
            consumed_snapshot_field_ids=_COMMON_TYPED_SNAPSHOT_FIELDS
            | _GHOST_BOUND_SNAPSHOT_FIELDS
            | frozenset(
                {
                    "exterior_blocks",
                    "family_inputs.shape_packing_hall.ghost",
                    "family_inputs.shape_packing_hall.group_demands",
                    "family_inputs.shape_packing_hall.group_to_facility_type",
                    "family_inputs.shape_packing_hall.template_dimensions",
                    "family_inputs.shape_packing_hall.template_placement_rules",
                    "ghost_cells",
                    "shape_packing_hall_master_domain_projection",
                }
            ),
            typed_plugin=_available(_HALL_PLUGIN),
            production_exact_checker=_unavailable(
                "no-production-independent-exact-twin-checker"
            ),
            snapshot_input=_available(
                SnapshotInputSpec(
                    family_input_key="shape_packing_hall",
                    record_type=StaticSymbolIdentity(
                        module="src.cuts.state_snapshot",
                        qualname="F6HallInputs",
                    ),
                )
            ),
            master_domain_projection=_available(
                SnapshotProjectionSpec(
                    kind=SnapshotProjectionKind.SHAPE_PACKING_HALL,
                    builder=StaticSymbolIdentity(
                        module="src.cuts.state_snapshot",
                        qualname="_build_f6_master_domain_projection",
                    ),
                )
            ),
            lowering=_available(
                LoweringSpec(
                    operation="shape_packing_hall_le",
                    typed_apply_entrypoint=_TYPED_APPLY,
                    master_primitive="_lower_baseline_packing_cut",
                )
            ),
            replay=_available(_TYPED_REPLAY),
            telemetry_profile=TelemetryProfile.TYPED_COMPILED,
            required_contract_ids=_typed_contracts(compiled=True),
        ),
        "power_hitting_set": FamilyTrustSpec(
            capability=_capability(
                name="power_hitting_set",
                mode="literal",
                validator_version=POWER_HITTING_SET_VALIDATOR_VERSION,
                compiler_version=POWER_HITTING_SET_COMPILER_VERSION,
                stage=CapabilityStage.COMPILABLE,
                execution_path=ExecutionPath.TYPED,
                requires_ghost_bound=True,
            ),
            proof_schema=_PROOF_SCHEMAS_V1["power_hitting_set"],
            rule_semantics=_rule_refs(
                ("power_hitting_set", "v1.0"),
                ("cut_scope_currentness", "v1"),
                ("complete_premise_implication", "v1"),
                ("master_domain_projection_binding", "v1"),
            ),
            authority_dependency_closure=PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE,
            consumed_snapshot_field_ids=_COMMON_TYPED_SNAPSHOT_FIELDS
            | _GHOST_BOUND_SNAPSHOT_FIELDS
            | frozenset(
                {
                    "cell_owner",
                    "exterior_blocks",
                    "family_inputs.power_hitting_set.cell_owner",
                    "family_inputs.power_hitting_set.ghost",
                    "family_inputs.power_hitting_set.group_pose_domains",
                    "family_inputs.power_hitting_set.group_to_facility_type",
                    "family_inputs.power_hitting_set.pole_dimensions",
                    "family_inputs.power_hitting_set.pole_radius",
                    "family_inputs.power_hitting_set.pose_occupied_cells",
                    "family_inputs.power_hitting_set.template_needs_power",
                    "ghost_cells",
                    "power_hitting_set_master_domain_projection",
                }
            ),
            typed_plugin=_available(_POWER_PLUGIN),
            production_exact_checker=_unavailable(
                "no-production-independent-exact-twin-checker"
            ),
            snapshot_input=_available(
                SnapshotInputSpec(
                    family_input_key="power_hitting_set",
                    record_type=StaticSymbolIdentity(
                        module="src.cuts.state_snapshot",
                        qualname="F7PowerInputs",
                    ),
                )
            ),
            master_domain_projection=_available(
                SnapshotProjectionSpec(
                    kind=SnapshotProjectionKind.POWER_HITTING_SET,
                    builder=StaticSymbolIdentity(
                        module="src.cuts.state_snapshot",
                        qualname="_build_f7_master_domain_projection",
                    ),
                )
            ),
            lowering=_available(
                LoweringSpec(
                    operation="power_pose_exclusion",
                    typed_apply_entrypoint=_TYPED_APPLY,
                    master_primitive="_lower_power_pose_exclusion_cut",
                )
            ),
            replay=_available(_TYPED_REPLAY),
            telemetry_profile=TelemetryProfile.TYPED_COMPILED,
            required_contract_ids=_typed_contracts(compiled=True),
        ),
        "power_grid_reach": FamilyTrustSpec(
            capability=_capability(
                name="power_grid_reach",
                mode="geometric",
                validator_version="retired-false-premise",
                compiler_version=None,
                stage=CapabilityStage.RETIRED,
                execution_path=ExecutionPath.LEGACY_DIAGNOSTIC,
            ),
            proof_schema=_unavailable("retired-family-has-no-live-proof-schema"),
            rule_semantics=_rule_refs(
                ("power_grid_reach", "retired-false-premise-v1"),
            ),
            authority_dependency_closure=PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE,
            consumed_snapshot_field_ids=frozenset(),
            typed_plugin=_unavailable("retired-false-premise"),
            production_exact_checker=_unavailable("retired-false-premise"),
            snapshot_input=_unavailable("retired-false-premise"),
            master_domain_projection=_unavailable("retired-false-premise"),
            lowering=_unavailable("retired-false-premise"),
            replay=_unavailable("retired-family-is-not-replayable"),
            telemetry_profile=TelemetryProfile.RETIRED,
            required_contract_ids=("retired_fail_closed",),
        ),
        "density_envelope": FamilyTrustSpec(
            capability=_capability(
                name="density_envelope",
                mode="geometric",
                validator_version="legacy-diagnostic-v1",
                compiler_version=None,
                stage=CapabilityStage.VALIDATED,
                execution_path=ExecutionPath.LEGACY_DIAGNOSTIC,
            ),
            proof_schema=_PROOF_SCHEMAS_V1["density_envelope"],
            rule_semantics=_rule_refs(
                ("density_envelope", "v1.0"),
                ("cut_scope_currentness", "v1"),
                ("complete_premise_implication", "v1"),
            ),
            authority_dependency_closure=PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE,
            consumed_snapshot_field_ids=frozenset(),
            typed_plugin=_unavailable("legacy-diagnostic-only"),
            production_exact_checker=_unavailable(
                "legacy-validator-is-not-an-independent-exact-checker"
            ),
            snapshot_input=_unavailable("legacy-replay-reads-bstate"),
            master_domain_projection=_unavailable("no-typed-master-projection"),
            lowering=_unavailable("no-trusted-lowering"),
            replay=_legacy_replay(validate_density_envelope),
            telemetry_profile=TelemetryProfile.LEGACY_DIAGNOSTIC,
            required_contract_ids=(
                "hold_and_quarantine",
                "legacy_diagnostic_replay_hold",
                "tcb_fault_propagation",
                "unknown_type",
            ),
        ),
    }
)


def _generator(target: Callable[..., object]) -> AvailableCapability[StaticCallableRef]:
    return _available(StaticCallableRef.capture(target))


_NO_ADAPTER = _unavailable("generator-has-no-separate-adapter")
_NO_TYPED_INVOKER = _unavailable("family-is-not-on-the-typed-attach-surface")
_BENDERS_TARGET_POSES = StaticSymbolIdentity(
    module="src.search.benders_loop",
    qualname="LBBDController._framework_target_poses",
)
_BENDERS_FULL_ASSIGNMENT = StaticSymbolIdentity(
    module="src.search.benders_loop",
    qualname="LBBDController._framework_full_assignment_literals",
)
_REGION_CAPACITY_INVOKER = StaticSymbolIdentity(
    module="src.search.family_generation",
    qualname="invoke_region_capacity_generation",
)
_POWER_HITTING_SET_INVOKER = StaticSymbolIdentity(
    module="src.search.family_generation",
    qualname="invoke_power_hitting_set_generation",
)
_SHAPE_PACKING_HALL_INVOKER = StaticSymbolIdentity(
    module="src.search.family_generation",
    qualname="invoke_shape_packing_hall_generation",
)
_PATTERN_NOGOOD_INVOKER = StaticSymbolIdentity(
    module="src.search.family_generation",
    qualname="invoke_pattern_nogood_generation",
)

PRODUCTION_FAMILY_GENERATION_SPECS_V1: Final[Mapping[str, FamilyGenerationSpec]] = MappingProxyType(
    {
        "region_capacity": FamilyGenerationSpec(
            family="region_capacity",
            surface=GenerationSurface.TYPED_ATTACH,
            oracle_name=_available("region_capacity_v1"),
            family_version=_available("v1.2"),
            validator_version=_available("v1.2"),
            generator=_generator(generate_region_capacity_cuts),
            generation_invoker=_available(_REGION_CAPACITY_INVOKER),
            adapter_factory=_NO_ADAPTER,
            preparation_steps=(),
            generator_parameter_ids=(
                "state",
                "canonical_rules",
                "iter_index",
                "grid_size",
            ),
            orchestration_context_ids=("state", "canonical_rules", "iter_index"),
            production_typed_order=0,
        ),
        "cutset": FamilyGenerationSpec(
            family="cutset",
            surface=GenerationSurface.LEGACY_DIAGNOSTIC,
            oracle_name=_available("cutset_v1"),
            family_version=_available("v1.0"),
            validator_version=_available("v1.0"),
            generator=_generator(generate_cutset_cuts),
            generation_invoker=_NO_TYPED_INVOKER,
            adapter_factory=_NO_ADAPTER,
            preparation_steps=(),
            generator_parameter_ids=("state", "master_solution", "iter_index"),
            orchestration_context_ids=(),
            production_typed_order=None,
        ),
        "port_exposure": FamilyGenerationSpec(
            family="port_exposure",
            surface=GenerationSurface.LEGACY_DIAGNOSTIC,
            oracle_name=_available("port_exposure_v2_canonical_dirs"),
            family_version=_available("v1.0"),
            validator_version=_available("v1.0"),
            generator=_generator(generate_port_exposure_cuts),
            generation_invoker=_NO_TYPED_INVOKER,
            adapter_factory=_NO_ADAPTER,
            preparation_steps=(),
            generator_parameter_ids=(
                "state",
                "master_solution",
                "target_poses",
                "iter_index",
            ),
            orchestration_context_ids=(),
            production_typed_order=None,
        ),
        "component_reach": FamilyGenerationSpec(
            family="component_reach",
            surface=GenerationSurface.LEGACY_DIAGNOSTIC,
            oracle_name=_available("component_reach_v1"),
            family_version=_available("v1.1"),
            validator_version=_available("v1.1"),
            generator=_generator(generate_component_reach_cuts),
            generation_invoker=_NO_TYPED_INVOKER,
            adapter_factory=_NO_ADAPTER,
            preparation_steps=(),
            generator_parameter_ids=("state", "master_solution", "iter_index"),
            orchestration_context_ids=(),
            production_typed_order=None,
        ),
        "pattern_nogood": FamilyGenerationSpec(
            family="pattern_nogood",
            surface=GenerationSurface.TYPED_ATTACH,
            oracle_name=_available("pattern_nogood_v1"),
            family_version=_available("v1.0"),
            validator_version=_available("v1.0"),
            generator=_generator(generate_pattern_nogood_cuts),
            generation_invoker=_available(_PATTERN_NOGOOD_INVOKER),
            adapter_factory=_available(
                StaticSymbolIdentity(
                    module="src.search.f5_binding_empty_domain_adapter",
                    qualname="build_binding_empty_domain_adapter",
                )
            ),
            preparation_steps=(_BENDERS_FULL_ASSIGNMENT,),
            generator_parameter_ids=(
                "state",
                "sub_problem_oracle",
                "full_assignment_literals",
                "budget",
                "iter_index",
            ),
            orchestration_context_ids=(
                "state",
                "solution",
                "mandatory_groups",
                "iter_index",
            ),
            production_typed_order=3,
        ),
        "shape_packing_hall": FamilyGenerationSpec(
            family="shape_packing_hall",
            surface=GenerationSurface.TYPED_ATTACH,
            oracle_name=_available("shape_packing_hall_v1"),
            family_version=_available("v1.0"),
            validator_version=_available("v1.0"),
            generator=_generator(generate_shape_packing_hall_cuts),
            generation_invoker=_available(_SHAPE_PACKING_HALL_INVOKER),
            adapter_factory=_NO_ADAPTER,
            preparation_steps=(
                StaticCallableRef.capture(
                    compute_sot_region_demand_overrides
                ).identity,
            ),
            generator_parameter_ids=(
                "state",
                "boundary_groups",
                "region_kinds",
                "region_demand_overrides",
                "iter_index",
            ),
            orchestration_context_ids=(
                "state",
                "region_demand_overrides",
                "iter_index",
            ),
            production_typed_order=2,
        ),
        "power_hitting_set": FamilyGenerationSpec(
            family="power_hitting_set",
            surface=GenerationSurface.TYPED_ATTACH,
            oracle_name=_available("power_cover_v2_stencil"),
            family_version=_available("v1.0"),
            validator_version=_available("v1.0"),
            generator=_generator(generate_power_hitting_set_cuts),
            generation_invoker=_available(_POWER_HITTING_SET_INVOKER),
            adapter_factory=_NO_ADAPTER,
            preparation_steps=(_BENDERS_TARGET_POSES,),
            generator_parameter_ids=(
                "state",
                "target_poses",
                "pole_radius",
                "iter_index",
            ),
            orchestration_context_ids=("state", "solution", "target_poses", "iter_index"),
            production_typed_order=1,
        ),
        "power_grid_reach": FamilyGenerationSpec(
            family="power_grid_reach",
            surface=GenerationSurface.RETIRED,
            oracle_name=_unavailable("retired-false-premise"),
            family_version=_unavailable("retired-false-premise"),
            validator_version=_unavailable("retired-false-premise"),
            generator=_unavailable("retired-false-premise"),
            generation_invoker=_unavailable("retired-false-premise"),
            adapter_factory=_unavailable("retired-false-premise"),
            preparation_steps=(),
            generator_parameter_ids=(),
            orchestration_context_ids=(),
            production_typed_order=None,
        ),
        "density_envelope": FamilyGenerationSpec(
            family="density_envelope",
            surface=GenerationSurface.LEGACY_DIAGNOSTIC,
            oracle_name=_available("density_envelope_v1"),
            family_version=_available("v1.0"),
            validator_version=_available("v1.0"),
            generator=_generator(generate_density_envelope_cuts),
            generation_invoker=_NO_TYPED_INVOKER,
            adapter_factory=_NO_ADAPTER,
            preparation_steps=(),
            generator_parameter_ids=(
                "state",
                "witness_kind",
                "group_id",
                "window_rect",
                "max_allowed_area",
                "assignment_witness",
                "iter_index",
            ),
            orchestration_context_ids=(),
            production_typed_order=None,
        ),
    }
)

PRODUCTION_TYPED_GENERATION_ORDER_V1: Final = (
    "region_capacity",
    "power_hitting_set",
    "shape_packing_hall",
    "pattern_nogood",
)

PRODUCTION_FAMILY_MANIFEST_V1: Final = FamilySpecRegistry(
    schema_version=1,
    rule_semantics=PRODUCTION_RULE_SEMANTICS_V1,
    trust_specs=PRODUCTION_FAMILY_TRUST_SPECS_V1,
    generation_specs=PRODUCTION_FAMILY_GENERATION_SPECS_V1,
    typed_generation_order=PRODUCTION_TYPED_GENERATION_ORDER_V1,
)

PINNED_PRODUCTION_FAMILY_MANIFEST_AUDIT_DIGEST_V1: Final = (
    "88a0fafea4a30c83c19803fe7614bb6dd01e32b561c6c2f0e65a1700a97e08f2"
)
if (
    PRODUCTION_FAMILY_MANIFEST_V1.audit_digest
    != PINNED_PRODUCTION_FAMILY_MANIFEST_AUDIT_DIGEST_V1
):
    raise RuntimeError(
        "production family manifest v1 drifted without a reviewed version and "
        f"audit-baseline update: {PRODUCTION_FAMILY_MANIFEST_V1.audit_digest}"
    )

# Short aliases are intentionally views of the versioned manifest, not second
# mutable tables.
FAMILY_TRUST_SPECS: Final = PRODUCTION_FAMILY_MANIFEST_V1.trust_specs
FAMILY_GENERATION_SPECS: Final = PRODUCTION_FAMILY_MANIFEST_V1.generation_specs


__all__ = [
    "AvailableCapability",
    "CapabilityAvailability",
    "CapabilityUnavailableError",
    "FAMILY_CONTRACT_IDS_V1",
    "FAMILY_GENERATION_SPECS",
    "FAMILY_TRUST_SPECS",
    "FamilyGenerationSpec",
    "FamilySpecRegistry",
    "FamilyTrustSpec",
    "GenerationSurface",
    "LoweringSpec",
    "PRODUCTION_FAMILY_GENERATION_SPECS_V1",
    "PRODUCTION_FAMILY_MANIFEST_V1",
    "PRODUCTION_FAMILY_TRUST_SPECS_V1",
    "PRODUCTION_TYPED_GENERATION_ORDER_V1",
    "PRODUCTION_V1_AUTHORITY_DEPENDENCY_CLOSURE",
    "PluginProviderKind",
    "PluginProviderSpec",
    "PINNED_PRODUCTION_FAMILY_MANIFEST_AUDIT_DIGEST_V1",
    "ProofSchemaSpec",
    "ReplayKind",
    "ReplaySpec",
    "SnapshotInputSpec",
    "SnapshotProjectionKind",
    "SnapshotProjectionSpec",
    "StaticCallableRef",
    "StaticObjectRef",
    "StaticSymbolIdentity",
    "TelemetryProfile",
    "UnavailableCapability",
]
