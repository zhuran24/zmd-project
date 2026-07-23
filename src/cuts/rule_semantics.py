"""Static, audit-only rule-semantics ledger for cut-family evolution.

This module deliberately has no production-runtime imports.  It records the
semantic ownership facts required by ``00_master_roadmap.md`` section 0b
without changing any Cut, proof, snapshot, plan, replay, or authority schema.

The digest exposed here is explicitly an *audit* digest.  It must never be
mixed into source, scope, proof, plan, snapshot, compiled-cut, or campaign
authority digests.

The milestone-A production seed is intentionally bounded: it covers F1--F9
and the three direct cut-protocol rules that those families already consume
(scope currentness, complete-premise implication, and master-domain binding).
It is not a census of every business rule in the repository.  Adding a direct
business rule requires an explicit versioned row and the same owner/polarity
checks; absence from this bounded seed conveys no authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping, TypeAlias


_AUDIT_DIGEST_PREFIX: Final = b"zmd.rule-semantics.audit.v1:"
_ROW_AUDIT_DIGEST_PREFIX: Final = b"zmd.rule-semantics.row.audit.v1:"
_STABLE_ID_RE: Final = re.compile(r"^[a-z0-9][a-z0-9_.:-]*$")


def _require_exact_positive_int(value: object, *, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field_name} must be a positive exact int")
    return value


def _require_stable_id(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value or _STABLE_ID_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a non-empty stable identifier")
    return value


def _require_non_empty_str(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{field_name} must be a non-empty, trimmed exact str")
    return value


def _require_exact_tuple(value: object, *, field_name: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{field_name} must be an exact tuple")
    return value


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class InformationLayer(Enum):
    """Version-1 information-owner nodes from the current project pipeline."""

    PRECHECK = "precheck"
    MASTER = "master"
    RAB_FILTER = "rab_filter"
    BINDING = "binding"
    ROUTING = "routing"
    TERMINAL_VALIDATION = "terminal_validation"


@dataclass(frozen=True, slots=True)
class InformationDependencyEdge:
    """A hard information-order edge from an earlier to a later owner."""

    prerequisite: InformationLayer
    dependent: InformationLayer

    def __post_init__(self) -> None:
        if type(self.prerequisite) is not InformationLayer:
            raise TypeError("InformationDependencyEdge.prerequisite must be InformationLayer")
        if type(self.dependent) is not InformationLayer:
            raise TypeError("InformationDependencyEdge.dependent must be InformationLayer")
        if self.prerequisite is self.dependent:
            raise ValueError("information dependency edges cannot be self-loops")

    def audit_projection(self) -> dict[str, str]:
        return {
            "dependent": self.dependent.value,
            "prerequisite": self.prerequisite.value,
        }


@dataclass(frozen=True, slots=True)
class InformationDependencyDagV1:
    """Explicit, versioned information-dependency DAG.

    Edges are the only source of ordering.  Enum values are labels, never
    sortable authority ranks.  ``unique_maximum`` therefore remains correct if
    the pipeline later gains branches or incomparable layers.
    """

    dag_id: str
    schema_version: int
    nodes: frozenset[InformationLayer]
    edges: tuple[InformationDependencyEdge, ...]

    def __post_init__(self) -> None:
        _require_stable_id(self.dag_id, field_name="InformationDependencyDagV1.dag_id")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("InformationDependencyDagV1.schema_version must be exact int 1")
        if type(self.nodes) is not frozenset or not self.nodes:
            raise TypeError("InformationDependencyDagV1.nodes must be a non-empty exact frozenset")
        for node in self.nodes:
            if type(node) is not InformationLayer:
                raise TypeError("InformationDependencyDagV1.nodes must contain only InformationLayer")
        _require_exact_tuple(self.edges, field_name="InformationDependencyDagV1.edges")
        seen_edges: set[tuple[InformationLayer, InformationLayer]] = set()
        adjacency: dict[InformationLayer, set[InformationLayer]] = {node: set() for node in self.nodes}
        for edge in self.edges:
            if type(edge) is not InformationDependencyEdge:
                raise TypeError("InformationDependencyDagV1.edges must contain InformationDependencyEdge")
            if edge.prerequisite not in self.nodes or edge.dependent not in self.nodes:
                raise ValueError("information dependency edge references a node outside the DAG")
            key = (edge.prerequisite, edge.dependent)
            if key in seen_edges:
                raise ValueError("InformationDependencyDagV1.edges cannot contain duplicates")
            seen_edges.add(key)
            adjacency[edge.prerequisite].add(edge.dependent)

        visiting: set[InformationLayer] = set()
        visited: set[InformationLayer] = set()

        def visit(node: InformationLayer) -> None:
            if node in visiting:
                raise ValueError("information dependency graph must be acyclic")
            if node in visited:
                return
            visiting.add(node)
            for dependent in adjacency[node]:
                visit(dependent)
            visiting.remove(node)
            visited.add(node)

        for node in self.nodes:
            visit(node)

    def reaches(self, prerequisite: InformationLayer, dependent: InformationLayer) -> bool:
        """Return whether ``prerequisite`` is at or before ``dependent``."""

        if type(prerequisite) is not InformationLayer or type(dependent) is not InformationLayer:
            raise TypeError("InformationDependencyDagV1.reaches arguments must be InformationLayer")
        if prerequisite not in self.nodes or dependent not in self.nodes:
            raise ValueError("InformationDependencyDagV1.reaches argument is outside the DAG")
        if prerequisite is dependent:
            return True
        adjacency: dict[InformationLayer, tuple[InformationLayer, ...]] = {
            node: tuple(
                edge.dependent
                for edge in self.edges
                if edge.prerequisite is node
            )
            for node in self.nodes
        }
        pending = list(adjacency[prerequisite])
        visited: set[InformationLayer] = set()
        while pending:
            node = pending.pop()
            if node is dependent:
                return True
            if node in visited:
                continue
            visited.add(node)
            pending.extend(adjacency[node])
        return False

    def unique_maximum(self, dependencies: frozenset[InformationLayer]) -> InformationLayer:
        """Compute the unique latest owner among explicit dependency nodes."""

        if type(dependencies) is not frozenset or not dependencies:
            raise TypeError("information dependencies must be a non-empty exact frozenset")
        for dependency in dependencies:
            if type(dependency) is not InformationLayer:
                raise TypeError("information dependencies must contain only InformationLayer")
            if dependency not in self.nodes:
                raise ValueError("information dependency is outside the registered DAG")
        maxima = {
            candidate
            for candidate in dependencies
            if not any(
                candidate is not other and self.reaches(candidate, other)
                for other in dependencies
            )
        }
        if len(maxima) != 1:
            values = sorted(node.value for node in maxima)
            raise ValueError(f"information dependencies have no unique maximum owner: {values!r}")
        return next(iter(maxima))

    def audit_projection(self) -> dict[str, object]:
        return {
            "dag_id": self.dag_id,
            "edges": sorted(
                (edge.audit_projection() for edge in self.edges),
                key=lambda item: (item["prerequisite"], item["dependent"]),
            ),
            "nodes": sorted(node.value for node in self.nodes),
            "schema_version": self.schema_version,
        }


class SemanticPolarity(Enum):
    NECESSARY_PROJECTION = "necessary_projection"
    SUFFICIENT_RESTRICTION = "sufficient_restriction"
    EXACT_SEMANTICS = "exact_semantics"


@dataclass(frozen=True, slots=True)
class RuleSemanticFacet:
    """One polarity-specific semantic statement."""

    facet_id: str
    semantic_version: str
    polarity: SemanticPolarity
    owner: InformationLayer
    claim: str
    source_ref: str

    def __post_init__(self) -> None:
        _require_stable_id(self.facet_id, field_name="RuleSemanticFacet.facet_id")
        _require_non_empty_str(self.semantic_version, field_name="RuleSemanticFacet.semantic_version")
        if type(self.polarity) is not SemanticPolarity:
            raise TypeError("RuleSemanticFacet.polarity must be SemanticPolarity")
        if type(self.owner) is not InformationLayer:
            raise TypeError("RuleSemanticFacet.owner must be InformationLayer")
        _require_non_empty_str(self.claim, field_name="RuleSemanticFacet.claim")
        _require_non_empty_str(self.source_ref, field_name="RuleSemanticFacet.source_ref")

    def audit_projection(self) -> dict[str, str]:
        return {
            "claim": self.claim,
            "facet_id": self.facet_id,
            "owner": self.owner.value,
            "polarity": self.polarity.value,
            "semantic_version": self.semantic_version,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class PremiseSpec:
    premise_id: str
    semantic_version: str
    owner: InformationLayer
    source_ref: str

    def __post_init__(self) -> None:
        _require_stable_id(self.premise_id, field_name="PremiseSpec.premise_id")
        _require_non_empty_str(self.semantic_version, field_name="PremiseSpec.semantic_version")
        if type(self.owner) is not InformationLayer:
            raise TypeError("PremiseSpec.owner must be InformationLayer")
        _require_non_empty_str(self.source_ref, field_name="PremiseSpec.source_ref")

    def audit_projection(self) -> dict[str, str]:
        return {
            "owner": self.owner.value,
            "premise_id": self.premise_id,
            "semantic_version": self.semantic_version,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class AssumptionSpec:
    assumption_id: str
    semantic_version: str
    owner: InformationLayer
    source_ref: str

    def __post_init__(self) -> None:
        _require_stable_id(self.assumption_id, field_name="AssumptionSpec.assumption_id")
        _require_non_empty_str(self.semantic_version, field_name="AssumptionSpec.semantic_version")
        if type(self.owner) is not InformationLayer:
            raise TypeError("AssumptionSpec.owner must be InformationLayer")
        _require_non_empty_str(self.source_ref, field_name="AssumptionSpec.source_ref")

    def audit_projection(self) -> dict[str, str]:
        return {
            "assumption_id": self.assumption_id,
            "owner": self.owner.value,
            "semantic_version": self.semantic_version,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class InvalidationConditionSpec:
    condition_id: str
    semantic_version: str
    owner: InformationLayer
    source_ref: str

    def __post_init__(self) -> None:
        _require_stable_id(self.condition_id, field_name="InvalidationConditionSpec.condition_id")
        _require_non_empty_str(self.semantic_version, field_name="InvalidationConditionSpec.semantic_version")
        if type(self.owner) is not InformationLayer:
            raise TypeError("InvalidationConditionSpec.owner must be InformationLayer")
        _require_non_empty_str(self.source_ref, field_name="InvalidationConditionSpec.source_ref")

    def audit_projection(self) -> dict[str, str]:
        return {
            "condition_id": self.condition_id,
            "owner": self.owner.value,
            "semantic_version": self.semantic_version,
            "source_ref": self.source_ref,
        }


class ExactCheckerUnavailableReason(Enum):
    NO_INDEPENDENT_PRODUCTION_CHECKER = "no_independent_production_checker"
    LEGACY_DIAGNOSTIC_ONLY = "legacy_diagnostic_only"
    RETIRED_FALSE_PREMISE = "retired_false_premise"
    PROTOCOL_ASSERTION_ONLY = "protocol_assertion_only"


@dataclass(frozen=True, slots=True)
class AvailableExactChecker:
    """Static identity of an existing independent production checker.

    The module/qualname pair is descriptive metadata, not a dynamic import
    instruction.  Runtime loading from this record is intentionally unsupported.
    """

    checker_id: str
    checker_version: str
    module: str
    qualname: str
    independence_basis: str

    def __post_init__(self) -> None:
        _require_stable_id(self.checker_id, field_name="AvailableExactChecker.checker_id")
        _require_non_empty_str(self.checker_version, field_name="AvailableExactChecker.checker_version")
        _require_non_empty_str(self.module, field_name="AvailableExactChecker.module")
        _require_non_empty_str(self.qualname, field_name="AvailableExactChecker.qualname")
        _require_non_empty_str(
            self.independence_basis,
            field_name="AvailableExactChecker.independence_basis",
        )

    @property
    def is_available(self) -> bool:
        return True

    def audit_projection(self) -> dict[str, object]:
        return {
            "available": True,
            "checker_id": self.checker_id,
            "checker_version": self.checker_version,
            "independence_basis": self.independence_basis,
            "module": self.module,
            "qualname": self.qualname,
        }


@dataclass(frozen=True, slots=True)
class UnavailableExactChecker:
    reason: ExactCheckerUnavailableReason
    detail: str

    def __post_init__(self) -> None:
        if type(self.reason) is not ExactCheckerUnavailableReason:
            raise TypeError("UnavailableExactChecker.reason must be ExactCheckerUnavailableReason")
        _require_non_empty_str(self.detail, field_name="UnavailableExactChecker.detail")

    @property
    def is_available(self) -> bool:
        return False

    def audit_projection(self) -> dict[str, object]:
        return {
            "available": False,
            "detail": self.detail,
            "reason": self.reason.value,
        }


ExactCheckerCapability: TypeAlias = AvailableExactChecker | UnavailableExactChecker


class RuleDeploymentState(Enum):
    """Current deployment truth; this is not a promotion mechanism."""

    EXPERIMENTAL = "experimental"
    COMPILABLE = "compilable"
    ENABLED = "enabled"
    VALIDATED_SHADOW_ONLY = "validated_shadow_only"
    VALIDATED_LEGACY_DIAGNOSTIC = "validated_legacy_diagnostic"
    RETIRED = "retired"
    SHARED_PROTOCOL = "shared_protocol"


@dataclass(frozen=True, slots=True)
class VersionedRuleRef:
    """A rule-ledger edge pinned to the referenced semantic version."""

    rule_id: str
    semantic_version: str

    def __post_init__(self) -> None:
        _require_stable_id(self.rule_id, field_name="VersionedRuleRef.rule_id")
        _require_non_empty_str(
            self.semantic_version,
            field_name="VersionedRuleRef.semantic_version",
        )

    def audit_projection(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "semantic_version": self.semantic_version,
        }


@dataclass(frozen=True, slots=True)
class RuleSemanticSpec:
    """Versioned semantic ledger row for one rule or cut family."""

    rule_id: str
    semantic_version: str
    deployment_state: RuleDeploymentState
    information_dependencies: frozenset[InformationLayer]
    authoritative_owner: InformationLayer
    representation_owner: InformationLayer
    necessary_projection: RuleSemanticFacet | None
    sufficient_restriction: RuleSemanticFacet | None
    exact_semantics: RuleSemanticFacet | None
    complete_premises: tuple[PremiseSpec, ...]
    assumptions: tuple[AssumptionSpec, ...]
    invalidation_conditions: tuple[InvalidationConditionSpec, ...]
    exact_twin_checker: ExactCheckerCapability
    protocol_obligations: tuple[VersionedRuleRef, ...]
    source_refs: tuple[str, ...]
    semantic_dependencies: tuple[VersionedRuleRef, ...] = ()

    def __post_init__(self) -> None:
        _require_stable_id(self.rule_id, field_name="RuleSemanticSpec.rule_id")
        _require_non_empty_str(self.semantic_version, field_name="RuleSemanticSpec.semantic_version")
        if type(self.deployment_state) is not RuleDeploymentState:
            raise TypeError("RuleSemanticSpec.deployment_state must be RuleDeploymentState")
        if type(self.information_dependencies) is not frozenset or not self.information_dependencies:
            raise TypeError("RuleSemanticSpec.information_dependencies must be a non-empty exact frozenset")
        for dependency in self.information_dependencies:
            if type(dependency) is not InformationLayer:
                raise TypeError("RuleSemanticSpec.information_dependencies must contain InformationLayer")
        if type(self.authoritative_owner) is not InformationLayer:
            raise TypeError("RuleSemanticSpec.authoritative_owner must be InformationLayer")
        if type(self.representation_owner) is not InformationLayer:
            raise TypeError("RuleSemanticSpec.representation_owner must be InformationLayer")

        expected_facets = (
            ("necessary_projection", self.necessary_projection, SemanticPolarity.NECESSARY_PROJECTION),
            ("sufficient_restriction", self.sufficient_restriction, SemanticPolarity.SUFFICIENT_RESTRICTION),
            ("exact_semantics", self.exact_semantics, SemanticPolarity.EXACT_SEMANTICS),
        )
        facet_ids: set[str] = set()
        for field_name, facet, expected_polarity in expected_facets:
            if facet is None:
                continue
            if type(facet) is not RuleSemanticFacet:
                raise TypeError(f"RuleSemanticSpec.{field_name} must be RuleSemanticFacet or None")
            if facet.polarity is not expected_polarity:
                raise ValueError(f"RuleSemanticSpec.{field_name} has the wrong semantic polarity")
            if facet.semantic_version != self.semantic_version:
                raise ValueError(
                    f"RuleSemanticSpec.{field_name} semantic version differs from rule"
                )
            if facet.facet_id in facet_ids:
                raise ValueError("one semantic facet cannot be reused across polarity columns")
            facet_ids.add(facet.facet_id)

        _require_exact_tuple(self.complete_premises, field_name="RuleSemanticSpec.complete_premises")
        _require_exact_tuple(self.assumptions, field_name="RuleSemanticSpec.assumptions")
        _require_exact_tuple(
            self.invalidation_conditions,
            field_name="RuleSemanticSpec.invalidation_conditions",
        )
        _require_exact_tuple(
            self.semantic_dependencies,
            field_name="RuleSemanticSpec.semantic_dependencies",
        )
        _require_exact_tuple(
            self.protocol_obligations,
            field_name="RuleSemanticSpec.protocol_obligations",
        )
        _require_exact_tuple(self.source_refs, field_name="RuleSemanticSpec.source_refs")
        if not self.complete_premises:
            raise ValueError("RuleSemanticSpec.complete_premises cannot be empty")
        if not self.invalidation_conditions:
            raise ValueError("RuleSemanticSpec.invalidation_conditions cannot be empty")
        if not self.source_refs:
            raise ValueError("RuleSemanticSpec.source_refs cannot be empty")

        self._validate_typed_tuple(
            self.complete_premises,
            expected_type=PremiseSpec,
            id_attribute="premise_id",
            field_name="complete_premises",
        )
        self._validate_typed_tuple(
            self.assumptions,
            expected_type=AssumptionSpec,
            id_attribute="assumption_id",
            field_name="assumptions",
        )
        self._validate_typed_tuple(
            self.invalidation_conditions,
            expected_type=InvalidationConditionSpec,
            id_attribute="condition_id",
            field_name="invalidation_conditions",
        )
        semantic_dependency_ids = self._validate_rule_refs(
            self.semantic_dependencies,
            field_name="semantic_dependencies",
        )
        protocol_obligation_ids = self._validate_rule_refs(
            self.protocol_obligations,
            field_name="protocol_obligations",
        )
        overlap = semantic_dependency_ids & protocol_obligation_ids
        if overlap:
            raise ValueError(
                "one rule reference cannot be both a semantic dependency and "
                f"protocol obligation: {sorted(overlap)!r}"
            )
        for source_ref in self.source_refs:
            _require_non_empty_str(source_ref, field_name="RuleSemanticSpec.source_refs item")
        if len(set(self.source_refs)) != len(self.source_refs):
            raise ValueError("RuleSemanticSpec.source_refs cannot contain duplicates")
        if type(self.exact_twin_checker) not in {AvailableExactChecker, UnavailableExactChecker}:
            raise TypeError(
                "RuleSemanticSpec.exact_twin_checker must be AvailableExactChecker "
                "or UnavailableExactChecker"
            )

        if self.deployment_state is RuleDeploymentState.RETIRED:
            if any(
                facet is not None
                for facet in (
                    self.necessary_projection,
                    self.sufficient_restriction,
                    self.exact_semantics,
                )
            ):
                raise ValueError("retired rules cannot advertise a live semantic facet")
            if type(self.exact_twin_checker) is not UnavailableExactChecker:
                raise ValueError("retired rules cannot advertise an available exact checker")
        if self.deployment_state is RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC:
            if self.necessary_projection is not None:
                raise ValueError("legacy diagnostic rules cannot advertise a production necessary projection")
            if type(self.exact_twin_checker) is not UnavailableExactChecker:
                raise ValueError("legacy diagnostic rules cannot advertise an available exact checker")
        if (
            self.deployment_state
            in {RuleDeploymentState.COMPILABLE, RuleDeploymentState.ENABLED}
            and self.necessary_projection is None
        ):
            raise ValueError("compilable or enabled rules require a necessary projection")

    @staticmethod
    def _validate_typed_tuple(
        values: tuple[object, ...],
        *,
        expected_type: type[object],
        id_attribute: str,
        field_name: str,
    ) -> None:
        seen_ids: set[str] = set()
        for value in values:
            if type(value) is not expected_type:
                raise TypeError(f"RuleSemanticSpec.{field_name} contains the wrong type")
            stable_id = getattr(value, id_attribute)
            if stable_id in seen_ids:
                raise ValueError(f"RuleSemanticSpec.{field_name} contains duplicate IDs")
            seen_ids.add(stable_id)

    def audit_projection(self) -> dict[str, object]:
        checker = self.exact_twin_checker
        return {
            "assumptions": [item.audit_projection() for item in self.assumptions],
            "authoritative_owner": self.authoritative_owner.value,
            "complete_premises": [item.audit_projection() for item in self.complete_premises],
            "deployment_state": self.deployment_state.value,
            "protocol_obligations": [
                dependency.audit_projection()
                for dependency in self.protocol_obligations
            ],
            "semantic_dependencies": [
                dependency.audit_projection()
                for dependency in self.semantic_dependencies
            ],
            "exact_semantics": (
                None if self.exact_semantics is None else self.exact_semantics.audit_projection()
            ),
            "exact_twin_checker": checker.audit_projection(),
            "information_dependencies": sorted(node.value for node in self.information_dependencies),
            "invalidation_conditions": [
                item.audit_projection() for item in self.invalidation_conditions
            ],
            "necessary_projection": (
                None
                if self.necessary_projection is None
                else self.necessary_projection.audit_projection()
            ),
            "representation_owner": self.representation_owner.value,
            "rule_id": self.rule_id,
            "semantic_version": self.semantic_version,
            "source_refs": list(self.source_refs),
            "sufficient_restriction": (
                None
                if self.sufficient_restriction is None
                else self.sufficient_restriction.audit_projection()
            ),
        }

    @property
    def semantic_dependency_ids(self) -> tuple[str, ...]:
        return tuple(dependency.rule_id for dependency in self.semantic_dependencies)

    @property
    def protocol_obligation_ids(self) -> tuple[str, ...]:
        return tuple(dependency.rule_id for dependency in self.protocol_obligations)

    def _validate_rule_refs(
        self,
        refs: tuple[VersionedRuleRef, ...],
        *,
        field_name: str,
    ) -> set[str]:
        rule_ids: set[str] = set()
        for rule_ref in refs:
            if type(rule_ref) is not VersionedRuleRef:
                raise TypeError(
                    f"RuleSemanticSpec.{field_name} must contain VersionedRuleRef"
                )
            if rule_ref.rule_id == self.rule_id:
                raise ValueError("RuleSemanticSpec cannot reference itself")
            if rule_ref.rule_id in rule_ids:
                raise ValueError(
                    f"RuleSemanticSpec.{field_name} cannot contain duplicates"
                )
            rule_ids.add(rule_ref.rule_id)
        return rule_ids


@dataclass(frozen=True, slots=True, init=False)
class RuleSemanticRegistry:
    """Immutable semantic ledger with fail-closed cross-row validation."""

    schema_version: int
    information_dag: InformationDependencyDagV1
    rules: Mapping[str, RuleSemanticSpec]
    rule_content_digests: Mapping[tuple[str, str], str]
    audit_digest: str

    def __init__(
        self,
        *,
        schema_version: int,
        information_dag: InformationDependencyDagV1,
        rules: Mapping[str, RuleSemanticSpec],
    ) -> None:
        _require_exact_positive_int(schema_version, field_name="RuleSemanticRegistry.schema_version")
        if schema_version != 1:
            raise ValueError("RuleSemanticRegistry.schema_version must be exact int 1")
        if type(information_dag) is not InformationDependencyDagV1:
            raise TypeError("RuleSemanticRegistry.information_dag must be InformationDependencyDagV1")
        if not isinstance(rules, Mapping) or not rules:
            raise TypeError("RuleSemanticRegistry.rules must be a non-empty mapping")
        captured: dict[str, RuleSemanticSpec] = {}
        for raw_rule_id, spec in rules.items():
            rule_id = _require_stable_id(raw_rule_id, field_name="RuleSemanticRegistry rule key")
            if type(spec) is not RuleSemanticSpec:
                raise TypeError(f"RuleSemanticRegistry rule {rule_id!r} must be RuleSemanticSpec")
            if spec.rule_id != rule_id:
                raise ValueError(f"RuleSemanticRegistry key {rule_id!r} differs from spec.rule_id")
            captured[rule_id] = spec

        for rule_id, spec in captured.items():
            for relation_name, references in (
                ("semantic dependency", spec.semantic_dependencies),
                ("protocol obligation", spec.protocol_obligations),
            ):
                for reference in references:
                    if reference.rule_id not in captured:
                        raise ValueError(
                            f"rule {rule_id!r} references unknown {relation_name} "
                            f"{reference.rule_id!r}"
                        )
                    actual_version = captured[reference.rule_id].semantic_version
                    if reference.semantic_version != actual_version:
                        raise ValueError(
                            f"rule {rule_id!r} pins {relation_name} "
                            f"{reference.rule_id!r} at {reference.semantic_version!r}, "
                            f"current version is {actual_version!r}"
                        )
            semantic_scope_owners = {
                item.owner for item in spec.complete_premises
            } | {
                item.owner for item in spec.assumptions
            }
            if spec.exact_semantics is not None:
                semantic_scope_owners.add(spec.exact_semantics.owner)
            semantic_scope_owners.update(
                captured[reference.rule_id].authoritative_owner
                for reference in spec.semantic_dependencies
            )
            missing_dependencies = (
                frozenset(semantic_scope_owners) - spec.information_dependencies
            )
            if missing_dependencies:
                raise ValueError(
                    f"rule {rule_id!r} information dependencies omit semantic-scope "
                    f"owner(s): {sorted(item.value for item in missing_dependencies)!r}"
                )
            computed_owner = information_dag.unique_maximum(spec.information_dependencies)
            if computed_owner is not spec.authoritative_owner:
                raise ValueError(
                    f"rule {rule_id!r} authoritative owner {spec.authoritative_owner.value!r} "
                    f"does not match DAG-derived owner {computed_owner.value!r}"
                )
            if not information_dag.reaches(spec.representation_owner, spec.authoritative_owner):
                raise ValueError(
                    f"rule {rule_id!r} representation owner cannot be later than or "
                    "incomparable with its authoritative owner"
                )
            representation_facets = tuple(
                facet
                for facet in (
                    spec.necessary_projection,
                    spec.sufficient_restriction,
                )
                if facet is not None
            )
            if spec.representation_owner is not spec.authoritative_owner:
                if not representation_facets:
                    raise ValueError(
                        f"rule {rule_id!r} represented above authority requires a "
                        "necessary projection or sufficient restriction"
                    )
            for facet in representation_facets:
                if facet.owner is not spec.representation_owner:
                    raise ValueError(
                        f"rule {rule_id!r} {facet.polarity.value} owner differs "
                        "from representation owner"
                    )
            if spec.exact_semantics is not None and spec.exact_semantics.owner is not spec.authoritative_owner:
                raise ValueError(f"rule {rule_id!r} exact semantics must remain at the authoritative owner")
            for condition in spec.invalidation_conditions:
                if condition.owner not in information_dag.nodes:
                    raise ValueError(
                        f"rule {rule_id!r} invalidation condition owner is outside the DAG"
                    )

        dependency_adjacency = {
            rule_id: (
                *spec.semantic_dependency_ids,
                *spec.protocol_obligation_ids,
            )
            for rule_id, spec in captured.items()
        }
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(rule_id: str) -> None:
            if rule_id in visiting:
                raise ValueError("versioned rule reference graph must be acyclic")
            if rule_id in visited:
                return
            visiting.add(rule_id)
            for dependency in dependency_adjacency[rule_id]:
                visit(dependency)
            visiting.remove(rule_id)
            visited.add(rule_id)

        for rule_id in captured:
            visit(rule_id)

        projection = {
            "information_dag": information_dag.audit_projection(),
            "rules": [
                captured[rule_id].audit_projection()
                for rule_id in sorted(captured)
            ],
            "schema_version": schema_version,
        }
        rule_content_digests = {
            (rule_id, captured[rule_id].semantic_version): hashlib.sha256(
                _ROW_AUDIT_DIGEST_PREFIX
                + _canonical_json_bytes(captured[rule_id].audit_projection())
            ).hexdigest()
            for rule_id in sorted(captured)
        }
        audit_digest = hashlib.sha256(
            _AUDIT_DIGEST_PREFIX + _canonical_json_bytes(projection)
        ).hexdigest()
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "information_dag", information_dag)
        object.__setattr__(self, "rules", MappingProxyType(captured))
        object.__setattr__(
            self,
            "rule_content_digests",
            MappingProxyType(rule_content_digests),
        )
        object.__setattr__(self, "audit_digest", audit_digest)

    def get(self, rule_id: str) -> RuleSemanticSpec:
        checked = _require_stable_id(rule_id, field_name="RuleSemanticRegistry.get rule_id")
        try:
            return self.rules[checked]
        except KeyError as exc:
            raise KeyError(f"unknown rule semantic ID: {checked!r}") from exc

    def audit_projection(self) -> dict[str, object]:
        return {
            "information_dag": self.information_dag.audit_projection(),
            "rules": [
                self.rules[rule_id].audit_projection()
                for rule_id in sorted(self.rules)
            ],
            "schema_version": self.schema_version,
        }


PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1: Final = InformationDependencyDagV1(
    dag_id="cut_information_dependency_dag",
    schema_version=1,
    nodes=frozenset(InformationLayer),
    edges=(
        InformationDependencyEdge(InformationLayer.PRECHECK, InformationLayer.MASTER),
        InformationDependencyEdge(InformationLayer.MASTER, InformationLayer.RAB_FILTER),
        InformationDependencyEdge(InformationLayer.RAB_FILTER, InformationLayer.BINDING),
        InformationDependencyEdge(InformationLayer.BINDING, InformationLayer.ROUTING),
        InformationDependencyEdge(InformationLayer.ROUTING, InformationLayer.TERMINAL_VALIDATION),
    ),
)


def _facet(
    rule_id: str,
    semantic_version: str,
    polarity: SemanticPolarity,
    owner: InformationLayer,
    claim: str,
    source_ref: str,
) -> RuleSemanticFacet:
    return RuleSemanticFacet(
        facet_id=f"{rule_id}.{polarity.value}",
        semantic_version=semantic_version,
        polarity=polarity,
        owner=owner,
        claim=claim,
        source_ref=source_ref,
    )


def _premise(premise_id: str, owner: InformationLayer, source_ref: str) -> PremiseSpec:
    return PremiseSpec(
        premise_id=premise_id,
        semantic_version="v1",
        owner=owner,
        source_ref=source_ref,
    )


def _assumption(assumption_id: str, owner: InformationLayer, source_ref: str) -> AssumptionSpec:
    return AssumptionSpec(
        assumption_id=assumption_id,
        semantic_version="v1",
        owner=owner,
        source_ref=source_ref,
    )


def _invalidates(condition_id: str, owner: InformationLayer, source_ref: str) -> InvalidationConditionSpec:
    return InvalidationConditionSpec(
        condition_id=condition_id,
        semantic_version="v1",
        owner=owner,
        source_ref=source_ref,
    )


def _rules(*refs: tuple[str, str]) -> tuple[VersionedRuleRef, ...]:
    return tuple(
        VersionedRuleRef(rule_id=rule_id, semantic_version=semantic_version)
        for rule_id, semantic_version in refs
    )


_COMMON_INVALIDATIONS: Final = (
    _invalidates(
        "semantic_version_changed",
        InformationLayer.PRECHECK,
        "docs/项目说明/00_master_roadmap.md#0b",
    ),
    _invalidates(
        "registered_premise_invalidated",
        InformationLayer.TERMINAL_VALIDATION,
        "docs/项目说明/00_master_roadmap.md#0b",
    ),
    _invalidates(
        "master_representation_changed",
        InformationLayer.MASTER,
        "docs/项目说明/00_master_roadmap.md#0b",
    ),
)


def _unavailable(
    reason: ExactCheckerUnavailableReason,
    detail: str,
) -> UnavailableExactChecker:
    return UnavailableExactChecker(reason=reason, detail=detail)


_RULE_SPECS_V1: Final[tuple[RuleSemanticSpec, ...]] = (
    RuleSemanticSpec(
        rule_id="cut_scope_currentness",
        semantic_version="v1",
        deployment_state=RuleDeploymentState.SHARED_PROTOCOL,
        information_dependencies=frozenset(
            {
                InformationLayer.PRECHECK,
                InformationLayer.MASTER,
            }
        ),
        authoritative_owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        necessary_projection=None,
        sufficient_restriction=None,
        exact_semantics=_facet(
            "cut_scope_currentness",
            "v1",
            SemanticPolarity.EXACT_SEMANTICS,
            InformationLayer.MASTER,
            "A cut is current only when its complete source, artifact, ghost, oracle, and assumption scope matches.",
            "src/cuts/typed_platform.py:ScopeManifest",
        ),
        complete_premises=(
            _premise(
                "scope_source_identity",
                InformationLayer.PRECHECK,
                "src/cuts/typed_platform.py:ScopeManifest",
            ),
            _premise(
                "scope_artifact_identity",
                InformationLayer.PRECHECK,
                "src/cuts/typed_platform.py:ScopeManifest",
            ),
            _premise(
                "scope_state_identity",
                InformationLayer.MASTER,
                "src/cuts/state_snapshot.py:ValidatedStateSnapshot",
            ),
        ),
        assumptions=(),
        invalidation_conditions=_COMMON_INVALIDATIONS,
        exact_twin_checker=_unavailable(
            ExactCheckerUnavailableReason.PROTOCOL_ASSERTION_ONLY,
            "Currentness is a typed-platform protocol assertion, not an independent family exact checker.",
        ),
        protocol_obligations=(),
        source_refs=(
            "src/cuts/typed_platform.py:ScopeManifest",
            "src/cuts/state_snapshot.py:ValidatedStateSnapshot",
        ),
    ),
    RuleSemanticSpec(
        rule_id="complete_premise_implication",
        semantic_version="v1",
        deployment_state=RuleDeploymentState.SHARED_PROTOCOL,
        information_dependencies=frozenset(
            {
                InformationLayer.BINDING,
                InformationLayer.ROUTING,
                InformationLayer.TERMINAL_VALIDATION,
            }
        ),
        authoritative_owner=InformationLayer.TERMINAL_VALIDATION,
        representation_owner=InformationLayer.TERMINAL_VALIDATION,
        necessary_projection=None,
        sufficient_restriction=None,
        exact_semantics=_facet(
            "complete_premise_implication",
            "v1",
            SemanticPolarity.EXACT_SEMANTICS,
            InformationLayer.TERMINAL_VALIDATION,
            "A learned cut is admissible only as complete premises implying a necessary repair disjunction.",
            "docs/项目说明/00_master_roadmap.md#0b",
        ),
        complete_premises=(
            _premise(
                "failure_responsibility_scope",
                InformationLayer.BINDING,
                "docs/项目说明/00_master_roadmap.md#0b",
            ),
            _premise(
                "failure_state_identity",
                InformationLayer.ROUTING,
                "docs/项目说明/00_master_roadmap.md#0b",
            ),
            _premise(
                "repair_disjunction_is_necessary",
                InformationLayer.TERMINAL_VALIDATION,
                "docs/项目说明/00_master_roadmap.md#0b",
            ),
        ),
        assumptions=(),
        invalidation_conditions=_COMMON_INVALIDATIONS,
        exact_twin_checker=_unavailable(
            ExactCheckerUnavailableReason.PROTOCOL_ASSERTION_ONLY,
            "The implication discipline is a protocol invariant and has no standalone exact twin checker.",
        ),
        protocol_obligations=(),
        source_refs=("docs/项目说明/00_master_roadmap.md#0b",),
    ),
    RuleSemanticSpec(
        rule_id="master_domain_projection_binding",
        semantic_version="v1",
        deployment_state=RuleDeploymentState.SHARED_PROTOCOL,
        information_dependencies=frozenset({InformationLayer.MASTER}),
        authoritative_owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        necessary_projection=None,
        sufficient_restriction=None,
        exact_semantics=_facet(
            "master_domain_projection_binding",
            "v1",
            SemanticPolarity.EXACT_SEMANTICS,
            InformationLayer.MASTER,
            "A compiled cut may mutate only the exact live master domain represented by its validated snapshot projection.",
            "src/cuts/lifecycle.py:step_8_apply_to_master",
        ),
        complete_premises=(
            _premise(
                "snapshot_master_projection",
                InformationLayer.MASTER,
                "src/cuts/state_snapshot.py:MasterDomainProjectionV1",
            ),
            _premise(
                "live_master_projection",
                InformationLayer.MASTER,
                "src/cuts/lifecycle.py:_live_master_domain_projection",
            ),
            _premise(
                "model_scope_binding",
                InformationLayer.MASTER,
                "src/cuts/typed_platform.py:ModelScopeBinding",
            ),
        ),
        assumptions=(),
        invalidation_conditions=_COMMON_INVALIDATIONS,
        exact_twin_checker=_unavailable(
            ExactCheckerUnavailableReason.PROTOCOL_ASSERTION_ONLY,
            "Master-domain identity is an apply-boundary protocol assertion.",
        ),
        protocol_obligations=_rules(("cut_scope_currentness", "v1")),
        source_refs=(
            "src/cuts/state_snapshot.py:MasterDomainProjectionV1",
            "src/cuts/lifecycle.py:step_8_apply_to_master",
        ),
    ),
    RuleSemanticSpec(
        rule_id="region_capacity",
        semantic_version="v1.2",
        deployment_state=RuleDeploymentState.COMPILABLE,
        information_dependencies=frozenset({InformationLayer.MASTER}),
        authoritative_owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        necessary_projection=_facet(
            "region_capacity",
            "v1.2",
            SemanticPolarity.NECESSARY_PROJECTION,
            InformationLayer.MASTER,
            "For the registered region premises, selected group-cell demand cannot exceed recomputed region capacity.",
            "src/cuts/families/region_capacity_typed.py",
        ),
        sufficient_restriction=None,
        exact_semantics=_facet(
            "region_capacity",
            "v1.2",
            SemanticPolarity.EXACT_SEMANTICS,
            InformationLayer.MASTER,
            "Every legal placement satisfies the region-capacity inequality under the same complete premises.",
            "src/cuts/families/region_capacity.py",
        ),
        complete_premises=(
            _premise("f1_region_definition", InformationLayer.MASTER, "src/cuts/families/region_capacity.py"),
            _premise("f1_group_demands", InformationLayer.MASTER, "src/cuts/state_snapshot.py:F1RegionInputs"),
            _premise("f1_pose_cell_weights", InformationLayer.MASTER, "src/cuts/state_snapshot.py:F1RegionInputs"),
            _premise("f1_ghost_policy", InformationLayer.MASTER, "src/cuts/families/region_capacity.py"),
        ),
        assumptions=(
            _assumption(
                "f1_boundary_saturation_policy",
                InformationLayer.MASTER,
                "src/cuts/assumptions/verifiers.py",
            ),
        ),
        invalidation_conditions=_COMMON_INVALIDATIONS,
        exact_twin_checker=_unavailable(
            ExactCheckerUnavailableReason.NO_INDEPENDENT_PRODUCTION_CHECKER,
            "The typed family verifier is not a separately implemented exact twin checker.",
        ),
        protocol_obligations=_rules(
            ("cut_scope_currentness", "v1"),
            ("complete_premise_implication", "v1"),
            ("master_domain_projection_binding", "v1"),
        ),
        source_refs=(
            "src/cuts/families/region_capacity.py",
            "src/cuts/families/region_capacity_typed.py",
        ),
    ),
    RuleSemanticSpec(
        rule_id="cutset",
        semantic_version="v1.0",
        deployment_state=RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC,
        information_dependencies=frozenset({InformationLayer.ROUTING}),
        authoritative_owner=InformationLayer.ROUTING,
        representation_owner=InformationLayer.ROUTING,
        necessary_projection=None,
        sufficient_restriction=None,
        exact_semantics=_facet(
            "cutset",
            "v1.0",
            SemanticPolarity.EXACT_SEMANTICS,
            InformationLayer.ROUTING,
            "Required commodity connectivity must cross every separating free-cell cut with sufficient capacity.",
            "src/cuts/families/cutset.py",
        ),
        complete_premises=(
            _premise("f2_free_cell_partition", InformationLayer.ROUTING, "src/cuts/families/cutset.py"),
            _premise("f2_cut_edges", InformationLayer.ROUTING, "src/cuts/families/cutset.py"),
            _premise("f2_commodity_demand", InformationLayer.ROUTING, "src/cuts/families/cutset.py"),
        ),
        assumptions=(),
        invalidation_conditions=_COMMON_INVALIDATIONS,
        exact_twin_checker=_unavailable(
            ExactCheckerUnavailableReason.LEGACY_DIAGNOSTIC_ONLY,
            "F2 has only a legacy diagnostic validator and no production independent exact checker.",
        ),
        protocol_obligations=_rules(
            ("cut_scope_currentness", "v1"),
            ("complete_premise_implication", "v1"),
        ),
        source_refs=("src/cuts/families/cutset.py", "src/cuts/replay.py"),
    ),
    RuleSemanticSpec(
        rule_id="port_exposure",
        semantic_version="v1.0",
        deployment_state=RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC,
        information_dependencies=frozenset(
            {
                InformationLayer.MASTER,
                InformationLayer.BINDING,
            }
        ),
        authoritative_owner=InformationLayer.BINDING,
        representation_owner=InformationLayer.BINDING,
        necessary_projection=None,
        sufficient_restriction=None,
        exact_semantics=_facet(
            "port_exposure",
            "v1.0",
            SemanticPolarity.EXACT_SEMANTICS,
            InformationLayer.BINDING,
            "A required active port binding must expose its identity port cell rather than a blocked one.",
            "src/cuts/families/port_exposure.py",
        ),
        complete_premises=(
            _premise("f3_facility_pose_identity", InformationLayer.MASTER, "src/cuts/families/port_exposure.py"),
            _premise("f3_active_port_identity", InformationLayer.BINDING, "src/cuts/families/port_exposure.py"),
            _premise("f3_blocking_facility_identity", InformationLayer.BINDING, "src/cuts/families/port_exposure.py"),
        ),
        assumptions=(),
        invalidation_conditions=_COMMON_INVALIDATIONS,
        exact_twin_checker=_unavailable(
            ExactCheckerUnavailableReason.LEGACY_DIAGNOSTIC_ONLY,
            "F3 has only a legacy diagnostic validator and no production independent exact checker.",
        ),
        protocol_obligations=_rules(
            ("cut_scope_currentness", "v1"),
            ("complete_premise_implication", "v1"),
        ),
        source_refs=("src/cuts/families/port_exposure.py", "src/cuts/replay.py"),
    ),
    RuleSemanticSpec(
        rule_id="component_reach",
        semantic_version="v1.1",
        deployment_state=RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC,
        information_dependencies=frozenset({InformationLayer.ROUTING}),
        authoritative_owner=InformationLayer.ROUTING,
        representation_owner=InformationLayer.ROUTING,
        necessary_projection=None,
        sufficient_restriction=None,
        exact_semantics=_facet(
            "component_reach",
            "v1.1",
            SemanticPolarity.EXACT_SEMANTICS,
            InformationLayer.ROUTING,
            "Required source and sink cells must belong to one reachable component of the live free-cell graph.",
            "src/cuts/families/component_reach.py",
        ),
        complete_premises=(
            _premise("f4_source_sink_identity", InformationLayer.ROUTING, "src/cuts/families/component_reach.py"),
            _premise("f4_live_free_cells", InformationLayer.ROUTING, "src/cuts/families/component_reach.py"),
            _premise("f4_component_partition", InformationLayer.ROUTING, "src/cuts/families/component_reach.py"),
        ),
        assumptions=(),
        invalidation_conditions=_COMMON_INVALIDATIONS,
        exact_twin_checker=_unavailable(
            ExactCheckerUnavailableReason.LEGACY_DIAGNOSTIC_ONLY,
            "F4 has only a legacy diagnostic validator and no production independent exact checker.",
        ),
        protocol_obligations=_rules(
            ("cut_scope_currentness", "v1"),
            ("complete_premise_implication", "v1"),
        ),
        source_refs=("src/cuts/families/component_reach.py", "src/cuts/replay.py"),
    ),
    RuleSemanticSpec(
        rule_id="pattern_nogood",
        semantic_version="v1.0",
        deployment_state=RuleDeploymentState.VALIDATED_SHADOW_ONLY,
        information_dependencies=frozenset(
            {
                InformationLayer.MASTER,
                InformationLayer.BINDING,
            }
        ),
        authoritative_owner=InformationLayer.BINDING,
        representation_owner=InformationLayer.BINDING,
        necessary_projection=None,
        sufficient_restriction=None,
        exact_semantics=_facet(
            "pattern_nogood",
            "v1.0",
            SemanticPolarity.EXACT_SEMANTICS,
            InformationLayer.BINDING,
            "A forbidden pose conjunction is invalid only when its frozen pose-level binding domain is independently empty.",
            "src/cuts/verifiers/binding_empty_domain_verifier.py",
        ),
        complete_premises=(
            _premise("f5_forbidden_pose_pattern", InformationLayer.MASTER, "src/cuts/typed_platform.py"),
            _premise("f5_oracle_identity", InformationLayer.BINDING, "src/cuts/typed_platform.py"),
            _premise("f5_frozen_binding_inputs", InformationLayer.BINDING, "src/cuts/state_snapshot.py:F5PatternNogoodInputs"),
        ),
        assumptions=(
            _assumption(
                "f5_pose_level_binding_model",
                InformationLayer.BINDING,
                "src/cuts/verifiers/binding_empty_domain_verifier.py",
            ),
        ),
        invalidation_conditions=_COMMON_INVALIDATIONS,
        exact_twin_checker=AvailableExactChecker(
            checker_id="f5.binding_empty_domain",
            checker_version="rfc-002-v1",
            module="src.cuts.verifiers.binding_empty_domain_verifier",
            qualname="verify_binding_empty_domain",
            independence_basis=(
                "Pure frozen-input complete-matching derivation with no import "
                "of the generator oracle or adapter surface."
            ),
        ),
        protocol_obligations=_rules(
            ("cut_scope_currentness", "v1"),
            ("complete_premise_implication", "v1"),
        ),
        source_refs=(
            "src/cuts/typed_platform.py:_verify_f5_binding_empty_domain",
            "src/cuts/verifiers/binding_empty_domain_verifier.py",
        ),
    ),
    RuleSemanticSpec(
        rule_id="shape_packing_hall",
        semantic_version="v1.0",
        deployment_state=RuleDeploymentState.COMPILABLE,
        information_dependencies=frozenset({InformationLayer.MASTER}),
        authoritative_owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        necessary_projection=_facet(
            "shape_packing_hall",
            "v1.0",
            SemanticPolarity.NECESSARY_PROJECTION,
            InformationLayer.MASTER,
            "A rigid baseline shape group cannot select more poses than fit in the ghost-split interval capacity.",
            "src/cuts/families/shape_packing_hall_typed.py",
        ),
        sufficient_restriction=None,
        exact_semantics=_facet(
            "shape_packing_hall",
            "v1.0",
            SemanticPolarity.EXACT_SEMANTICS,
            InformationLayer.MASTER,
            "Every legal baseline placement satisfies the recomputed single-shape Hall interval bound.",
            "src/cuts/families/shape_packing_hall.py",
        ),
        complete_premises=(
            _premise("f6_ghost_bound", InformationLayer.MASTER, "src/cuts/families/shape_packing_hall.py"),
            _premise("f6_baseline_partition", InformationLayer.MASTER, "src/cuts/state_snapshot.py:F6HallInputs"),
            _premise("f6_pose_shape", InformationLayer.MASTER, "src/cuts/state_snapshot.py:F6HallInputs"),
            _premise("f6_group_demand", InformationLayer.MASTER, "src/cuts/state_snapshot.py:F6HallInputs"),
        ),
        assumptions=(),
        invalidation_conditions=_COMMON_INVALIDATIONS,
        exact_twin_checker=_unavailable(
            ExactCheckerUnavailableReason.NO_INDEPENDENT_PRODUCTION_CHECKER,
            "The typed family verifier is not a separately implemented exact twin checker.",
        ),
        protocol_obligations=_rules(
            ("cut_scope_currentness", "v1"),
            ("complete_premise_implication", "v1"),
            ("master_domain_projection_binding", "v1"),
        ),
        source_refs=(
            "src/cuts/families/shape_packing_hall.py",
            "src/cuts/families/shape_packing_hall_typed.py",
        ),
    ),
    RuleSemanticSpec(
        rule_id="power_hitting_set",
        semantic_version="v1.0",
        deployment_state=RuleDeploymentState.COMPILABLE,
        information_dependencies=frozenset({InformationLayer.MASTER}),
        authoritative_owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        necessary_projection=_facet(
            "power_hitting_set",
            "v1.0",
            SemanticPolarity.NECESSARY_PROJECTION,
            InformationLayer.MASTER,
            "A powered facility pose with an empty ghost-only canonical pole CoverSet cannot be selected.",
            "src/cuts/families/power_hitting_set_typed.py",
        ),
        sufficient_restriction=None,
        exact_semantics=_facet(
            "power_hitting_set",
            "v1.0",
            SemanticPolarity.EXACT_SEMANTICS,
            InformationLayer.MASTER,
            "Every selected powered facility pose has at least one canonical pole placement that covers it.",
            "src/cuts/families/power_hitting_set.py",
        ),
        complete_premises=(
            _premise("f7_ghost_bound", InformationLayer.MASTER, "src/cuts/families/power_hitting_set.py"),
            _premise("f7_facility_pose_identity", InformationLayer.MASTER, "src/cuts/state_snapshot.py:F7PowerInputs"),
            _premise("f7_power_stencil", InformationLayer.MASTER, "src/cuts/helpers/power_cover.py"),
            _premise("f7_cover_set_inputs", InformationLayer.MASTER, "src/cuts/state_snapshot.py:F7PowerInputs"),
        ),
        assumptions=(
            _assumption(
                "f7_power_cover_v2_stencil",
                InformationLayer.MASTER,
                "src/cuts/families/power_hitting_set.py",
            ),
        ),
        invalidation_conditions=_COMMON_INVALIDATIONS,
        exact_twin_checker=_unavailable(
            ExactCheckerUnavailableReason.NO_INDEPENDENT_PRODUCTION_CHECKER,
            "The typed family verifier is not a separately implemented exact twin checker.",
        ),
        protocol_obligations=_rules(
            ("cut_scope_currentness", "v1"),
            ("complete_premise_implication", "v1"),
            ("master_domain_projection_binding", "v1"),
        ),
        source_refs=(
            "src/cuts/families/power_hitting_set.py",
            "src/cuts/families/power_hitting_set_typed.py",
        ),
    ),
    RuleSemanticSpec(
        rule_id="power_grid_reach",
        semantic_version="retired-false-premise-v1",
        deployment_state=RuleDeploymentState.RETIRED,
        information_dependencies=frozenset({InformationLayer.ROUTING}),
        authoritative_owner=InformationLayer.ROUTING,
        representation_owner=InformationLayer.ROUTING,
        necessary_projection=None,
        sufficient_restriction=None,
        exact_semantics=None,
        complete_premises=(
            _premise(
                "f8_pole_to_pole_network_required",
                InformationLayer.ROUTING,
                "PROJECT_LOCK.md:F8-retirement",
            ),
        ),
        assumptions=(
            _assumption(
                "f8_false_game_rule_premise",
                InformationLayer.ROUTING,
                "PROJECT_LOCK.md:F8-retirement",
            ),
        ),
        invalidation_conditions=(
            _invalidates(
                "f8_pole_network_premise_falsified",
                InformationLayer.ROUTING,
                "PROJECT_LOCK.md:F8-retirement",
            ),
        ),
        exact_twin_checker=_unavailable(
            ExactCheckerUnavailableReason.RETIRED_FALSE_PREMISE,
            "F8 was retired because the game does not require a pole-to-pole power network.",
        ),
        protocol_obligations=(),
        source_refs=(
            "PROJECT_LOCK.md:F8-retirement",
            "docs/项目说明/21_glossary.md:active-cut-families",
        ),
    ),
    RuleSemanticSpec(
        rule_id="density_envelope",
        semantic_version="v1.0",
        deployment_state=RuleDeploymentState.VALIDATED_LEGACY_DIAGNOSTIC,
        information_dependencies=frozenset({InformationLayer.MASTER}),
        authoritative_owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        necessary_projection=None,
        sufficient_restriction=None,
        exact_semantics=_facet(
            "density_envelope",
            "v1.0",
            SemanticPolarity.EXACT_SEMANTICS,
            InformationLayer.MASTER,
            "Occupied area of one group inside a window cannot exceed the recomputed static safe area bound.",
            "src/cuts/families/density_envelope.py",
        ),
        complete_premises=(
            _premise("f9_ghost_bound", InformationLayer.MASTER, "src/cuts/families/density_envelope.py"),
            _premise("f9_window_rect", InformationLayer.MASTER, "src/cuts/families/density_envelope.py"),
            _premise("f9_static_safe_area_bound", InformationLayer.MASTER, "src/cuts/families/density_envelope.py"),
            _premise("f9_group_assignment_witness", InformationLayer.MASTER, "src/cuts/families/density_envelope.py"),
        ),
        assumptions=(
            _assumption(
                "f9_area_only_witness",
                InformationLayer.MASTER,
                "PROJECT_LOCK.md:F9-area-based-counting-lock",
            ),
        ),
        invalidation_conditions=_COMMON_INVALIDATIONS,
        exact_twin_checker=_unavailable(
            ExactCheckerUnavailableReason.LEGACY_DIAGNOSTIC_ONLY,
            "F9 has only a legacy diagnostic validator and no production independent exact checker.",
        ),
        protocol_obligations=_rules(
            ("cut_scope_currentness", "v1"),
            ("complete_premise_implication", "v1"),
        ),
        source_refs=("src/cuts/families/density_envelope.py", "src/cuts/replay.py"),
    ),
)


PRODUCTION_RULE_SEMANTICS_V1: Final = RuleSemanticRegistry(
    schema_version=1,
    information_dag=PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1,
    rules={spec.rule_id: spec for spec in _RULE_SPECS_V1},
)

PINNED_PRODUCTION_RULE_CONTENT_DIGESTS_V1: Final = MappingProxyType(
    {
        (
            "complete_premise_implication",
            "v1",
        ): "9abb8cdb6c52538b7b9e1320bbeded2cc6ccc1f9b91f17bdec708263f882468f",
        (
            "component_reach",
            "v1.1",
        ): "132afcf98efa65c9fa8264aade1836fa004c90b5e7753296ff62c806e0fe6a3d",
        (
            "cut_scope_currentness",
            "v1",
        ): "e433d209283b3bfcbaa8a96a067fe68202c8d5384e0d9acf3f150f509a3306a8",
        (
            "cutset",
            "v1.0",
        ): "ee347084cbccb257705aefbe77f7c5aa4ba4f50568b90cb82153ad89a57c5e75",
        (
            "density_envelope",
            "v1.0",
        ): "db6c7084539eece29500ddd2711edc555f1aff1c217e634cf127b9e739881471",
        (
            "master_domain_projection_binding",
            "v1",
        ): "7f136189df1cc12c568c88447615daddaca35cc2c9080ba2a2f2b0d3da970e20",
        (
            "pattern_nogood",
            "v1.0",
        ): "14d2088344da915d92d9578b3b3844cc1ea5a11d8b753fb9482bf895dd872be7",
        (
            "port_exposure",
            "v1.0",
        ): "bb938b4a04a124796cb3a2364deec94067dd5f8cb75e00d733f794a97d54c843",
        (
            "power_grid_reach",
            "retired-false-premise-v1",
        ): "bd4cfc04c4d879525b3940c6f8795aff3b926b8247e4d8fa0c36dc10101001db",
        (
            "power_hitting_set",
            "v1.0",
        ): "128f891b1e74389ab9f84945203b698f0820a3fa32222ff81957dd3080e0c9c1",
        (
            "region_capacity",
            "v1.2",
        ): "16a6ed23530889a70ca623f4e7db16b58c4f4ec7e6a9f437ad6f56df60cac6e6",
        (
            "shape_packing_hall",
            "v1.0",
        ): "ac6bbf734e93a974394f1e98563a573512f2ee3d8777a67fb8ac4911798413c9",
    }
)
PINNED_PRODUCTION_RULE_LEDGER_AUDIT_DIGEST_V1: Final = (
    "34da1cc245dd8967c64e22462abe48cf81535d55042a55f6148ad758499bceed"
)

if (
    PRODUCTION_RULE_SEMANTICS_V1.rule_content_digests
    != PINNED_PRODUCTION_RULE_CONTENT_DIGESTS_V1
    or PRODUCTION_RULE_SEMANTICS_V1.audit_digest
    != PINNED_PRODUCTION_RULE_LEDGER_AUDIT_DIGEST_V1
):
    raise RuntimeError(
        "production rule-semantics v1 drifted without a reviewed semantic-version "
        "bump and audit-baseline update"
    )


__all__ = [
    "AssumptionSpec",
    "AvailableExactChecker",
    "ExactCheckerCapability",
    "ExactCheckerUnavailableReason",
    "InformationDependencyDagV1",
    "InformationDependencyEdge",
    "InformationLayer",
    "InvalidationConditionSpec",
    "PRODUCTION_INFORMATION_DEPENDENCY_DAG_V1",
    "PRODUCTION_RULE_SEMANTICS_V1",
    "PINNED_PRODUCTION_RULE_CONTENT_DIGESTS_V1",
    "PINNED_PRODUCTION_RULE_LEDGER_AUDIT_DIGEST_V1",
    "PremiseSpec",
    "RuleDeploymentState",
    "RuleSemanticFacet",
    "RuleSemanticRegistry",
    "RuleSemanticSpec",
    "SemanticPolarity",
    "UnavailableExactChecker",
    "VersionedRuleRef",
]
