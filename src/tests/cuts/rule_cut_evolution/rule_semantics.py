"""Identity-only shadow ledger for rule ownership and semantic evolution.

This is test/offline infrastructure.  Production code must not import it.  The
rows mirror the currently hard-coded cut surface so maintainers can review a
proposed migration before any authority or runtime wiring changes.

Every executable role is represented by source identity only.  In particular,
this module has no import loader, callable target, resolver, builder, or plugin
factory.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping


_AUDIT_PREFIX: Final = b"zmd.test-shadow.rule-semantics.v1:"
_TOKEN_RE: Final = re.compile(r"^[a-z0-9][a-z0-9_.:-]*$")


def _token(value: object, *, field_name: str) -> str:
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a stable lower-case identifier")
    return value


def _text(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{field_name} must be a non-empty trimmed exact str")
    return value


@dataclass(frozen=True, slots=True, order=True)
class StaticSymbolIdentity:
    """A source identity, deliberately incapable of resolving an object."""

    module: str
    qualname: str

    def __post_init__(self) -> None:
        module = _text(self.module, field_name="StaticSymbolIdentity.module")
        qualname = _text(self.qualname, field_name="StaticSymbolIdentity.qualname")
        if not module.startswith("src."):
            raise ValueError("static identities must be rooted below src")
        if "<locals>" in qualname or "<lambda>" in qualname:
            raise ValueError("static identities cannot name local functions or lambdas")

    def audit_projection(self) -> dict[str, str]:
        return {"module": self.module, "qualname": self.qualname}


class InformationLayer(Enum):
    PRECHECK = "precheck"
    MASTER = "master"
    RAB_FILTER = "rab_filter"
    BINDING = "binding"
    ROUTING = "routing"
    TERMINAL_VALIDATION = "terminal_validation"


INFORMATION_ORDER_V1: Final = (
    InformationLayer.PRECHECK,
    InformationLayer.MASTER,
    InformationLayer.RAB_FILTER,
    InformationLayer.BINDING,
    InformationLayer.ROUTING,
    InformationLayer.TERMINAL_VALIDATION,
)
_INFORMATION_RANK: Final = MappingProxyType(
    {layer: index for index, layer in enumerate(INFORMATION_ORDER_V1)}
)


class SemanticPolarity(Enum):
    NECESSARY_PROJECTION = "necessary_projection"
    SUFFICIENT_RESTRICTION = "sufficient_restriction"
    EXACT_SEMANTICS = "exact_semantics"


class RuleDeploymentState(Enum):
    SHARED_PROTOCOL = "shared_protocol"
    EXPERIMENTAL = "experimental"
    VALIDATED_SHADOW_ONLY = "validated_shadow_only"
    VALIDATED_LEGACY_DIAGNOSTIC = "validated_legacy_diagnostic"
    COMPILABLE = "compilable"
    ENABLED = "enabled"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class VersionedFact:
    fact_id: str
    semantic_version: str
    owner: InformationLayer

    def __post_init__(self) -> None:
        _token(self.fact_id, field_name="VersionedFact.fact_id")
        _text(self.semantic_version, field_name="VersionedFact.semantic_version")
        if type(self.owner) is not InformationLayer:
            raise TypeError("VersionedFact.owner must be InformationLayer")

    def audit_projection(self) -> dict[str, str]:
        return {
            "fact_id": self.fact_id,
            "owner": self.owner.value,
            "semantic_version": self.semantic_version,
        }


@dataclass(frozen=True, slots=True)
class SemanticFacet:
    polarity: SemanticPolarity
    semantic_version: str
    owner: InformationLayer
    claim: str
    source_ref: str

    def __post_init__(self) -> None:
        if type(self.polarity) is not SemanticPolarity:
            raise TypeError("SemanticFacet.polarity must be SemanticPolarity")
        _text(self.semantic_version, field_name="SemanticFacet.semantic_version")
        if type(self.owner) is not InformationLayer:
            raise TypeError("SemanticFacet.owner must be InformationLayer")
        _text(self.claim, field_name="SemanticFacet.claim")
        _text(self.source_ref, field_name="SemanticFacet.source_ref")

    def audit_projection(self) -> dict[str, str]:
        return {
            "claim": self.claim,
            "owner": self.owner.value,
            "polarity": self.polarity.value,
            "semantic_version": self.semantic_version,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class ExactCheckerSpec:
    identity: StaticSymbolIdentity | None
    checker_id: str | None
    checker_version: str | None
    independence_basis: str | None
    unavailable_reason: str | None

    def __post_init__(self) -> None:
        if self.identity is None and self.unavailable_reason is None:
            raise ValueError("ExactCheckerSpec requires exactly one available identity or unavailable reason")
        available = self.identity is not None
        if available:
            if type(self.identity) is not StaticSymbolIdentity:
                raise TypeError("ExactCheckerSpec.identity must be StaticSymbolIdentity")
            _token(self.checker_id, field_name="ExactCheckerSpec.checker_id")
            _text(self.checker_version, field_name="ExactCheckerSpec.checker_version")
            _text(self.independence_basis, field_name="ExactCheckerSpec.independence_basis")
            if self.unavailable_reason is not None:
                raise ValueError("available checker cannot carry unavailable_reason")
        else:
            if any(value is not None for value in (self.checker_id, self.checker_version, self.independence_basis)):
                raise ValueError("unavailable checker cannot carry checker metadata")
            _token(self.unavailable_reason, field_name="ExactCheckerSpec.unavailable_reason")

    @property
    def is_available(self) -> bool:
        return self.identity is not None

    def audit_projection(self) -> dict[str, object]:
        if self.identity is None:
            return {"available": False, "reason": self.unavailable_reason}
        return {
            "available": True,
            "checker_id": self.checker_id,
            "checker_version": self.checker_version,
            "identity": self.identity.audit_projection(),
            "independence_basis": self.independence_basis,
        }


@dataclass(frozen=True, slots=True)
class VersionedRuleRef:
    rule_id: str
    semantic_version: str

    def __post_init__(self) -> None:
        _token(self.rule_id, field_name="VersionedRuleRef.rule_id")
        _text(self.semantic_version, field_name="VersionedRuleRef.semantic_version")

    def audit_projection(self) -> dict[str, str]:
        return {"rule_id": self.rule_id, "semantic_version": self.semantic_version}


@dataclass(frozen=True, slots=True)
class RuleSemanticSpec:
    rule_id: str
    semantic_version: str
    information_dependencies: frozenset[InformationLayer]
    authoritative_owner: InformationLayer
    representation_owner: InformationLayer
    necessary_projection: SemanticFacet | None
    sufficient_restriction: SemanticFacet | None
    exact_semantics: SemanticFacet | None
    complete_premises: tuple[VersionedFact, ...]
    assumptions: tuple[VersionedFact, ...]
    invalidation_conditions: tuple[VersionedFact, ...]
    exact_twin_checker: ExactCheckerSpec
    semantic_dependencies: tuple[VersionedRuleRef, ...]
    protocol_obligations: tuple[VersionedRuleRef, ...]
    deployment_state: RuleDeploymentState
    source_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _token(self.rule_id, field_name="RuleSemanticSpec.rule_id")
        _text(self.semantic_version, field_name="RuleSemanticSpec.semantic_version")
        if type(self.information_dependencies) is not frozenset or not self.information_dependencies:
            raise TypeError("information_dependencies must be a non-empty exact frozenset")
        if any(type(layer) is not InformationLayer for layer in self.information_dependencies):
            raise TypeError("information_dependencies must contain InformationLayer values")
        if type(self.authoritative_owner) is not InformationLayer:
            raise TypeError("authoritative_owner must be InformationLayer")
        if type(self.representation_owner) is not InformationLayer:
            raise TypeError("representation_owner must be InformationLayer")
        maximum = max(self.information_dependencies, key=_INFORMATION_RANK.__getitem__)
        if self.authoritative_owner is not maximum:
            raise ValueError("authoritative_owner must be the latest information dependency")
        if self.representation_owner not in self.information_dependencies:
            raise ValueError("representation_owner must be an information dependency")
        facets = (
            (SemanticPolarity.NECESSARY_PROJECTION, self.necessary_projection),
            (SemanticPolarity.SUFFICIENT_RESTRICTION, self.sufficient_restriction),
            (SemanticPolarity.EXACT_SEMANTICS, self.exact_semantics),
        )
        for expected, facet in facets:
            if facet is not None:
                if type(facet) is not SemanticFacet or facet.polarity is not expected:
                    raise TypeError(f"{expected.value} has the wrong facet type/polarity")
                if facet.semantic_version != self.semantic_version:
                    raise ValueError("semantic facet version drift")
        if self.deployment_state is RuleDeploymentState.RETIRED:
            if self.exact_semantics is not None:
                raise ValueError("retired rule cannot advertise live exact semantics")
        elif self.exact_semantics is None:
            raise ValueError("live rule requires exact semantics")
        for name, values in (
            ("complete_premises", self.complete_premises),
            ("assumptions", self.assumptions),
            ("invalidation_conditions", self.invalidation_conditions),
        ):
            if type(values) is not tuple:
                raise TypeError(f"{name} must be an exact tuple")
            if any(type(value) is not VersionedFact for value in values):
                raise TypeError(f"{name} must contain VersionedFact")
            ids = tuple(value.fact_id for value in values)
            if len(ids) != len(set(ids)):
                raise ValueError(f"{name} cannot contain duplicate IDs")
        if not self.complete_premises:
            raise ValueError("complete_premises cannot be empty")
        if not self.invalidation_conditions:
            raise ValueError("invalidation_conditions cannot be empty")
        if type(self.exact_twin_checker) is not ExactCheckerSpec:
            raise TypeError("exact_twin_checker must be ExactCheckerSpec")
        for name, refs in (
            ("semantic_dependencies", self.semantic_dependencies),
            ("protocol_obligations", self.protocol_obligations),
        ):
            if type(refs) is not tuple or any(type(ref) is not VersionedRuleRef for ref in refs):
                raise TypeError(f"{name} must be an exact tuple of VersionedRuleRef")
        if type(self.deployment_state) is not RuleDeploymentState:
            raise TypeError("deployment_state must be RuleDeploymentState")
        if type(self.source_refs) is not tuple or not self.source_refs:
            raise TypeError("source_refs must be a non-empty exact tuple")
        for source_ref in self.source_refs:
            _text(source_ref, field_name="RuleSemanticSpec.source_refs")

    def audit_projection(self) -> dict[str, object]:
        def facet(value: SemanticFacet | None) -> object:
            return None if value is None else value.audit_projection()

        return {
            "assumptions": [item.audit_projection() for item in self.assumptions],
            "authoritative_owner": self.authoritative_owner.value,
            "complete_premises": [item.audit_projection() for item in self.complete_premises],
            "deployment_state": self.deployment_state.value,
            "exact_semantics": facet(self.exact_semantics),
            "exact_twin_checker": self.exact_twin_checker.audit_projection(),
            "information_dependencies": sorted(layer.value for layer in self.information_dependencies),
            "invalidation_conditions": [
                item.audit_projection() for item in self.invalidation_conditions
            ],
            "necessary_projection": facet(self.necessary_projection),
            "protocol_obligations": [item.audit_projection() for item in self.protocol_obligations],
            "representation_owner": self.representation_owner.value,
            "rule_id": self.rule_id,
            "semantic_dependencies": [item.audit_projection() for item in self.semantic_dependencies],
            "semantic_version": self.semantic_version,
            "source_refs": list(self.source_refs),
            "sufficient_restriction": facet(self.sufficient_restriction),
        }


@dataclass(frozen=True, slots=True, init=False)
class RuleSemanticRegistry:
    schema_version: int
    rules: Mapping[str, RuleSemanticSpec]
    audit_digest: str

    def __init__(self, *, schema_version: int, rules: Mapping[str, RuleSemanticSpec]) -> None:
        if type(schema_version) is not int or schema_version != 1:
            raise ValueError("RuleSemanticRegistry.schema_version must be exact int 1")
        if not isinstance(rules, Mapping) or not rules:
            raise TypeError("RuleSemanticRegistry.rules must be a non-empty mapping")
        checked: dict[str, RuleSemanticSpec] = {}
        for key, value in rules.items():
            _token(key, field_name="RuleSemanticRegistry.rules key")
            if type(value) is not RuleSemanticSpec or value.rule_id != key:
                raise ValueError("rule mapping key/spec identity mismatch")
            checked[key] = value
        for rule in checked.values():
            for ref in (*rule.semantic_dependencies, *rule.protocol_obligations):
                target = checked.get(ref.rule_id)
                if target is None:
                    raise ValueError(f"{rule.rule_id!r} references unknown rule {ref.rule_id!r}")
                if target.semantic_version != ref.semantic_version:
                    raise ValueError(f"{rule.rule_id!r} pins stale rule version {ref.rule_id!r}")
        projection = {
            "rules": [checked[key].audit_projection() for key in sorted(checked)],
            "schema_version": schema_version,
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
        object.__setattr__(self, "rules", MappingProxyType(checked))
        object.__setattr__(self, "audit_digest", digest)

    def get(self, rule_id: str) -> RuleSemanticSpec:
        try:
            return self.rules[rule_id]
        except KeyError as exc:
            raise KeyError(f"unknown rule semantic spec {rule_id!r}") from exc

    def audit_projection(self) -> dict[str, object]:
        return {
            "rules": [self.rules[key].audit_projection() for key in sorted(self.rules)],
            "schema_version": self.schema_version,
        }


def _fact(fact_id: str, owner: InformationLayer) -> VersionedFact:
    return VersionedFact(fact_id=fact_id, semantic_version="v1", owner=owner)


def _facet(
    rule_id: str,
    version: str,
    polarity: SemanticPolarity,
    owner: InformationLayer,
    claim: str,
    source_ref: str,
) -> SemanticFacet:
    return SemanticFacet(
        polarity=polarity,
        semantic_version=version,
        owner=owner,
        claim=claim,
        source_ref=source_ref,
    )


def _unavailable(reason: str) -> ExactCheckerSpec:
    return ExactCheckerSpec(
        identity=None,
        checker_id=None,
        checker_version=None,
        independence_basis=None,
        unavailable_reason=reason,
    )


_COMMON_INVALIDATIONS: Final = (
    _fact("semantic_version_changed", InformationLayer.PRECHECK),
    _fact("registered_premise_invalidated", InformationLayer.TERMINAL_VALIDATION),
    _fact("master_representation_changed", InformationLayer.MASTER),
)
_SCOPE_REF: Final = VersionedRuleRef("cut_scope_currentness", "v1")
_PREMISE_REF: Final = VersionedRuleRef("complete_premise_implication", "v1")
_MASTER_BINDING_REF: Final = VersionedRuleRef("master_domain_projection_binding", "v1")


def _rule(
    *,
    rule_id: str,
    version: str,
    dependencies: frozenset[InformationLayer],
    owner: InformationLayer,
    representation_owner: InformationLayer,
    premises: tuple[VersionedFact, ...],
    assumptions: tuple[VersionedFact, ...] = (),
    necessary_claim: str | None = None,
    exact_claim: str | None,
    checker: ExactCheckerSpec,
    protocols: tuple[VersionedRuleRef, ...],
    state: RuleDeploymentState,
    source_ref: str,
    invalidations: tuple[VersionedFact, ...] = _COMMON_INVALIDATIONS,
) -> RuleSemanticSpec:
    necessary = (
        None
        if necessary_claim is None
        else _facet(
            rule_id,
            version,
            SemanticPolarity.NECESSARY_PROJECTION,
            representation_owner,
            necessary_claim,
            source_ref,
        )
    )
    exact = (
        None
        if exact_claim is None
        else _facet(
            rule_id,
            version,
            SemanticPolarity.EXACT_SEMANTICS,
            owner,
            exact_claim,
            source_ref,
        )
    )
    return RuleSemanticSpec(
        rule_id=rule_id,
        semantic_version=version,
        information_dependencies=dependencies,
        authoritative_owner=owner,
        representation_owner=representation_owner,
        necessary_projection=necessary,
        sufficient_restriction=None,
        exact_semantics=exact,
        complete_premises=premises,
        assumptions=assumptions,
        invalidation_conditions=invalidations,
        exact_twin_checker=checker,
        semantic_dependencies=(),
        protocol_obligations=protocols,
        deployment_state=state,
        source_refs=(source_ref,),
    )


_RULE_ROWS: Final = (
    _rule(
        rule_id="cut_scope_currentness",
        version="v1",
        dependencies=frozenset({InformationLayer.PRECHECK, InformationLayer.MASTER}),
        owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        premises=(
            _fact("scope_source_identity", InformationLayer.PRECHECK),
            _fact("scope_artifact_identity", InformationLayer.PRECHECK),
            _fact("scope_state_identity", InformationLayer.MASTER),
        ),
        exact_claim="A cut is current only for the source, artifact, and state identity it records.",
        checker=_unavailable("protocol_assertion_only"),
        protocols=(),
        state=RuleDeploymentState.SHARED_PROTOCOL,
        source_ref="src/cuts/typed_platform.py",
    ),
    _rule(
        rule_id="complete_premise_implication",
        version="v1",
        dependencies=frozenset(
            {InformationLayer.BINDING, InformationLayer.ROUTING, InformationLayer.TERMINAL_VALIDATION}
        ),
        owner=InformationLayer.TERMINAL_VALIDATION,
        representation_owner=InformationLayer.TERMINAL_VALIDATION,
        premises=(
            _fact("failure_responsibility_scope", InformationLayer.BINDING),
            _fact("failure_state_identity", InformationLayer.ROUTING),
            _fact("repair_disjunction_is_necessary", InformationLayer.TERMINAL_VALIDATION),
        ),
        exact_claim="A lower-layer failure may imply only a repair disjunction under its complete premises.",
        checker=_unavailable("protocol_assertion_only"),
        protocols=(),
        state=RuleDeploymentState.SHARED_PROTOCOL,
        source_ref="docs/项目说明/REASONING_METHOD.md",
    ),
    _rule(
        rule_id="master_domain_projection_binding",
        version="v1",
        dependencies=frozenset({InformationLayer.MASTER}),
        owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        premises=(
            _fact("snapshot_master_projection", InformationLayer.MASTER),
            _fact("live_master_projection", InformationLayer.MASTER),
            _fact("model_scope_binding", InformationLayer.MASTER),
        ),
        exact_claim="A trusted plan can mutate only the live master represented by its snapshot projection.",
        checker=_unavailable("protocol_assertion_only"),
        protocols=(_SCOPE_REF,),
        state=RuleDeploymentState.SHARED_PROTOCOL,
        source_ref="src/cuts/lifecycle.py:step_8_apply_to_master",
    ),
    _rule(
        rule_id="region_capacity",
        version="v1.2",
        dependencies=frozenset({InformationLayer.MASTER}),
        owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        premises=tuple(
            _fact(item, InformationLayer.MASTER)
            for item in (
                "f1_region_definition",
                "f1_group_demands",
                "f1_pose_cell_weights",
                "f1_ghost_policy",
            )
        ),
        assumptions=(_fact("f1_boundary_saturation_policy", InformationLayer.MASTER),),
        necessary_claim="Selected group-cell demand cannot exceed recomputed region capacity.",
        exact_claim="Every legal placement satisfies the region-capacity inequality under the same premises.",
        checker=_unavailable("no_independent_production_checker"),
        protocols=(_SCOPE_REF, _PREMISE_REF, _MASTER_BINDING_REF),
        state=RuleDeploymentState.COMPILABLE,
        source_ref="src/cuts/families/region_capacity_typed.py",
    ),
    _rule(
        rule_id="cutset",
        version="v1.0",
        dependencies=frozenset({InformationLayer.ROUTING}),
        owner=InformationLayer.ROUTING,
        representation_owner=InformationLayer.ROUTING,
        premises=tuple(
            _fact(item, InformationLayer.ROUTING)
            for item in ("f2_free_cell_partition", "f2_cut_edges", "f2_commodity_demand")
        ),
        exact_claim="A certified minimum cut bounds the routed commodity under the recorded partition.",
        checker=_unavailable("legacy_diagnostic_only"),
        protocols=(_SCOPE_REF, _PREMISE_REF),
        state=RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC,
        source_ref="src/cuts/families/cutset.py",
    ),
    _rule(
        rule_id="port_exposure",
        version="v1.0",
        dependencies=frozenset({InformationLayer.MASTER, InformationLayer.BINDING}),
        owner=InformationLayer.BINDING,
        representation_owner=InformationLayer.BINDING,
        premises=(
            _fact("f3_facility_pose_identity", InformationLayer.MASTER),
            _fact("f3_active_port_identity", InformationLayer.BINDING),
            _fact("f3_blocking_facility_identity", InformationLayer.BINDING),
        ),
        exact_claim="A required active port binding exposes its identity port cell rather than a blocked cell.",
        checker=_unavailable("legacy_diagnostic_only"),
        protocols=(_SCOPE_REF, _PREMISE_REF),
        state=RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC,
        source_ref="src/cuts/families/port_exposure.py",
    ),
    _rule(
        rule_id="component_reach",
        version="v1.1",
        dependencies=frozenset({InformationLayer.ROUTING}),
        owner=InformationLayer.ROUTING,
        representation_owner=InformationLayer.ROUTING,
        premises=tuple(
            _fact(item, InformationLayer.ROUTING)
            for item in ("f4_source_sink_identity", "f4_live_free_cells", "f4_component_partition")
        ),
        exact_claim="The recorded source and sink are disconnected in the complete live routing graph.",
        checker=_unavailable("legacy_diagnostic_only"),
        protocols=(_SCOPE_REF, _PREMISE_REF),
        state=RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC,
        source_ref="src/cuts/families/component_reach.py",
    ),
    _rule(
        rule_id="pattern_nogood",
        version="v1.0",
        dependencies=frozenset({InformationLayer.MASTER, InformationLayer.BINDING}),
        owner=InformationLayer.BINDING,
        representation_owner=InformationLayer.BINDING,
        premises=(
            _fact("f5_forbidden_pose_pattern", InformationLayer.MASTER),
            _fact("f5_oracle_identity", InformationLayer.BINDING),
            _fact("f5_frozen_binding_inputs", InformationLayer.BINDING),
        ),
        assumptions=(_fact("f5_pose_level_binding_model", InformationLayer.BINDING),),
        exact_claim="A pose conjunction is forbidden only when its frozen binding domain is independently empty.",
        checker=ExactCheckerSpec(
            identity=StaticSymbolIdentity(
                "src.cuts.verifiers.binding_empty_domain_verifier",
                "verify_binding_empty_domain",
            ),
            checker_id="f5.binding_empty_domain",
            checker_version="rfc-002-v1",
            independence_basis="Pure frozen-input derivation independent of the generator and adapter.",
            unavailable_reason=None,
        ),
        protocols=(_SCOPE_REF, _PREMISE_REF),
        state=RuleDeploymentState.VALIDATED_SHADOW_ONLY,
        source_ref="src/cuts/verifiers/binding_empty_domain_verifier.py",
    ),
    _rule(
        rule_id="shape_packing_hall",
        version="v1.0",
        dependencies=frozenset({InformationLayer.MASTER}),
        owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        premises=tuple(
            _fact(item, InformationLayer.MASTER)
            for item in ("f6_ghost_bound", "f6_baseline_partition", "f6_pose_shape", "f6_group_demand")
        ),
        necessary_claim="A rigid baseline group cannot select more poses than the ghost-split intervals hold.",
        exact_claim="Every legal baseline placement satisfies the recomputed single-shape Hall bound.",
        checker=_unavailable("no_independent_production_checker"),
        protocols=(_SCOPE_REF, _PREMISE_REF, _MASTER_BINDING_REF),
        state=RuleDeploymentState.COMPILABLE,
        source_ref="src/cuts/families/shape_packing_hall_typed.py",
    ),
    _rule(
        rule_id="power_hitting_set",
        version="v1.0",
        dependencies=frozenset({InformationLayer.MASTER}),
        owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        premises=tuple(
            _fact(item, InformationLayer.MASTER)
            for item in (
                "f7_ghost_bound",
                "f7_facility_pose_identity",
                "f7_power_stencil",
                "f7_cover_set_inputs",
            )
        ),
        assumptions=(_fact("f7_power_cover_v2_stencil", InformationLayer.MASTER),),
        necessary_claim="A powered pose with an empty ghost-only canonical pole cover set cannot be selected.",
        exact_claim="Every selected powered pose has a canonical pole placement that covers it.",
        checker=_unavailable("no_independent_production_checker"),
        protocols=(_SCOPE_REF, _PREMISE_REF, _MASTER_BINDING_REF),
        state=RuleDeploymentState.COMPILABLE,
        source_ref="src/cuts/families/power_hitting_set_typed.py",
    ),
    _rule(
        rule_id="power_grid_reach",
        version="retired-false-premise-v1",
        dependencies=frozenset({InformationLayer.ROUTING}),
        owner=InformationLayer.ROUTING,
        representation_owner=InformationLayer.ROUTING,
        premises=(_fact("f8_pole_to_pole_network_required", InformationLayer.ROUTING),),
        assumptions=(_fact("f8_false_game_rule_premise", InformationLayer.ROUTING),),
        exact_claim=None,
        checker=_unavailable("retired_false_premise"),
        protocols=(),
        state=RuleDeploymentState.RETIRED,
        source_ref="PROJECT_LOCK.md:F8-retirement",
        invalidations=(_fact("f8_pole_network_premise_falsified", InformationLayer.ROUTING),),
    ),
    _rule(
        rule_id="density_envelope",
        version="v1.0",
        dependencies=frozenset({InformationLayer.MASTER}),
        owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        premises=tuple(
            _fact(item, InformationLayer.MASTER)
            for item in ("f9_ghost_bound", "f9_window_rect", "f9_static_safe_area_bound", "f9_group_assignment_witness")
        ),
        assumptions=(_fact("f9_area_only_witness", InformationLayer.MASTER),),
        exact_claim="The complete assignment witness cannot fit within the registered safe area bound.",
        checker=_unavailable("legacy_diagnostic_only"),
        protocols=(_SCOPE_REF, _PREMISE_REF),
        state=RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC,
        source_ref="src/cuts/families/density_envelope.py",
    ),
)


SHADOW_RULE_SEMANTICS_V1: Final = RuleSemanticRegistry(
    schema_version=1,
    rules={row.rule_id: row for row in _RULE_ROWS},
)
