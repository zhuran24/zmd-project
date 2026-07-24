"""Reusable test-only onboarding contract for an unadmitted cut family.

The fixture reuses the existing ``region_capacity_le`` plan operation.  Its
static rows are identity-only, while the executable roles below remain
separate functions so tests can exercise generator, verifier, independent
interpreter, tiny CP-SAT model, and exact checker without granting production
admission.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from enum import Enum
from typing import Final, Mapping, cast

from ortools.sat.python import cp_model

from src.cuts.typed_platform import ConstraintPlan, ModelScope
from src.tests.cuts.rule_cut_evolution.family_specs import (
    PRODUCTION_AUTHORITY_DEPENDENCIES_V1,
    SHADOW_FAMILY_SPECS_V1,
    CapabilitySpec,
    CapabilityStage,
    ExecutionPath,
    FamilyGenerationSpec,
    FamilyMode,
    FamilySpecRegistry,
    FamilyTrustSpec,
    GenerationSurface,
    LifecycleStage,
    LoweringSpec,
    PluginIdentitySpec,
    PluginProviderKind,
    ProofSchemaSpec,
    ReplayKind,
    ReplaySpec,
    SnapshotInputSpec,
    SnapshotProjectionSpec,
    TelemetryProfile,
    available,
    unavailable,
)
from src.tests.cuts.rule_cut_evolution.rule_semantics import (
    InformationLayer,
    RuleDeploymentState,
    RuleSemanticRegistry,
    RuleSemanticSpec,
    SemanticFacet,
    SemanticPolarity,
    StaticSymbolIdentity,
    VersionedFact,
    VersionedRuleRef,
    ExactCheckerSpec,
)


SHADOW_FAMILY: Final = "test_region_capacity_contract"
SHADOW_SEMANTIC_VERSION: Final = "v0.test"
SHADOW_SNAPSHOT_FINGERPRINT: Final = hashlib.sha256(b"shadow-onboarding-snapshot-v1").hexdigest()
_PROOF_PREFIX: Final = b"zmd.test-shadow.onboarding-proof.v1:"
_SEMANTIC_PREFIX: Final = b"zmd.test-shadow.onboarding-semantic.v1:"


class ShadowDisposition(Enum):
    HOLD = "HOLD"
    QUARANTINE = "QUARANTINE"


@dataclass(frozen=True, slots=True)
class ShadowPremises:
    capacity: int
    group_cell_weights: tuple[tuple[str, int], ...]
    semantic_version: str = SHADOW_SEMANTIC_VERSION

    def __post_init__(self) -> None:
        if type(self.capacity) is not int or self.capacity < 0:
            raise ValueError("capacity must be a non-negative exact int")
        if type(self.group_cell_weights) is not tuple or not self.group_cell_weights:
            raise TypeError("group_cell_weights must be a non-empty exact tuple")
        groups: list[str] = []
        for item in self.group_cell_weights:
            if type(item) is not tuple or len(item) != 2:
                raise TypeError("each group weight must be an exact pair")
            group_id, weight = item
            if type(group_id) is not str or not group_id:
                raise ValueError("group ID must be a non-empty exact str")
            if type(weight) is not int or weight <= 0:
                raise ValueError("group weight must be a positive exact int")
            groups.append(group_id)
        if len(groups) != len(set(groups)):
            raise ValueError("group IDs cannot repeat")
        if type(self.semantic_version) is not str or not self.semantic_version:
            raise ValueError("semantic_version must be a non-empty exact str")

    @property
    def weights(self) -> Mapping[str, int]:
        return dict(self.group_cell_weights)

    @property
    def digest(self) -> str:
        projection = {
            "capacity": self.capacity,
            "group_cell_weights": list(self.group_cell_weights),
            "semantic_version": self.semantic_version,
        }
        return hashlib.sha256(
            _PROOF_PREFIX
            + json.dumps(projection, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


DEFAULT_PREMISES: Final = ShadowPremises(
    capacity=2,
    group_cell_weights=(("alpha", 2), ("beta", 1)),
)


def _candidate_rule() -> RuleSemanticSpec:
    exact_checker = ExactCheckerSpec(
        identity=StaticSymbolIdentity(
            "src.tests.cuts.rule_cut_evolution.contract_harness",
            "independent_exact_checker",
        ),
        checker_id="test.region_capacity.exact",
        checker_version="v1",
        independence_basis="Finite assignment enumeration independent of generator and verifier.",
        unavailable_reason=None,
    )
    return RuleSemanticSpec(
        rule_id=SHADOW_FAMILY,
        semantic_version=SHADOW_SEMANTIC_VERSION,
        information_dependencies=frozenset({InformationLayer.MASTER}),
        authoritative_owner=InformationLayer.MASTER,
        representation_owner=InformationLayer.MASTER,
        necessary_projection=SemanticFacet(
            SemanticPolarity.NECESSARY_PROJECTION,
            SHADOW_SEMANTIC_VERSION,
            InformationLayer.MASTER,
            "The registered weighted selection does not exceed registered capacity.",
            "src/tests/cuts/rule_cut_evolution/contract_harness.py",
        ),
        sufficient_restriction=None,
        exact_semantics=SemanticFacet(
            SemanticPolarity.EXACT_SEMANTICS,
            SHADOW_SEMANTIC_VERSION,
            InformationLayer.MASTER,
            "The fixture inequality exactly describes its finite tiny-master premise.",
            "src/tests/cuts/rule_cut_evolution/contract_harness.py",
        ),
        complete_premises=(
            VersionedFact("test_capacity", "v1", InformationLayer.MASTER),
            VersionedFact("test_group_cell_weights", "v1", InformationLayer.MASTER),
            VersionedFact("test_snapshot_projection", "v1", InformationLayer.MASTER),
        ),
        assumptions=(),
        invalidation_conditions=(
            VersionedFact("semantic_version_changed", "v1", InformationLayer.PRECHECK),
            VersionedFact("premise_digest_changed", "v1", InformationLayer.MASTER),
            VersionedFact("snapshot_projection_changed", "v1", InformationLayer.MASTER),
        ),
        exact_twin_checker=exact_checker,
        semantic_dependencies=(),
        protocol_obligations=(
            VersionedRuleRef("cut_scope_currentness", "v1"),
            VersionedRuleRef("complete_premise_implication", "v1"),
            VersionedRuleRef("master_domain_projection_binding", "v1"),
        ),
        deployment_state=RuleDeploymentState.COMPILABLE,
        source_refs=("src/tests/cuts/rule_cut_evolution/contract_harness.py",),
    )


def build_shadow_onboarding_registry() -> FamilySpecRegistry:
    """Add one static fixture row without altering production admission."""

    candidate_rule = _candidate_rule()
    rule_registry = RuleSemanticRegistry(
        schema_version=1,
        rules={**SHADOW_FAMILY_SPECS_V1.rule_semantics.rules, SHADOW_FAMILY: candidate_rule},
    )
    rule_refs = (
        VersionedRuleRef(SHADOW_FAMILY, SHADOW_SEMANTIC_VERSION),
        *candidate_rule.protocol_obligations,
    )
    proof_fields = frozenset(
        {
            "capacity",
            "cert_kind",
            "family",
            "group_cell_weights",
            "premise_digest",
            "semantic_version",
            "snapshot_fingerprint",
        }
    )
    trust = FamilyTrustSpec(
        capability=CapabilitySpec(
            family=SHADOW_FAMILY,
            mode=FamilyMode.GEOMETRIC,
            proof_schema_version=1,
            validator_version="test-shadow-validator-v1",
            compiler_version="test-shadow-compiler-v1",
            stage=CapabilityStage.COMPILABLE,
            required_dependencies=PRODUCTION_AUTHORITY_DEPENDENCIES_V1,
            execution_path=ExecutionPath.TYPED,
            requires_ghost_bound=False,
        ),
        proof_schema=available(
            ProofSchemaSpec(
                family=SHADOW_FAMILY,
                schema_version=1,
                cert_kind="test_region_capacity_witness",
                allowed_fields=proof_fields,
                required_fields=proof_fields,
            )
        ),
        rule_semantics=rule_refs,
        authority_dependency_closure=PRODUCTION_AUTHORITY_DEPENDENCIES_V1,
        consumed_snapshot_field_ids=frozenset(
            {
                "digest",
                "master_domain_projection",
                "family_inputs.test_region_capacity_contract",
            }
        ),
        typed_plugin=available(
            PluginIdentitySpec(
                PluginProviderKind.FACTORY,
                StaticSymbolIdentity(
                    "src.tests.cuts.rule_cut_evolution.contract_harness",
                    "ShadowContractPluginIdentity",
                ),
                4,
                3,
            )
        ),
        exact_checker=available(
            cast(StaticSymbolIdentity, candidate_rule.exact_twin_checker.identity)
        ),
        snapshot_input=available(
            SnapshotInputSpec(
                SHADOW_FAMILY,
                StaticSymbolIdentity(
                    "src.tests.cuts.rule_cut_evolution.contract_harness",
                    "ShadowPremises",
                ),
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
            LoweringSpec(
                "region_capacity_le",
                StaticSymbolIdentity("src.cuts.typed_apply", "apply_compiled_cut"),
                "_lower_region_capacity_cut",
            )
        ),
        replay=available(
            ReplaySpec(
                ReplayKind.TYPED_SINGLE_ENTRY,
                StaticSymbolIdentity(
                    "src.tests.cuts.rule_cut_evolution.contract_harness",
                    "verify_proof_to_plan",
                ),
            )
        ),
        lifecycle_stage=LifecycleStage.TYPED_COMPILED,
        telemetry_profile=TelemetryProfile.TYPED_COMPILED,
        required_contract_ids=(
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
            "independent_exact_checker",
        ),
    )
    generation = FamilyGenerationSpec(
        family=SHADOW_FAMILY,
        surface=GenerationSurface.TYPED_ATTACH,
        oracle_name=available("test_region_capacity_contract_v1"),
        family_version=available(SHADOW_SEMANTIC_VERSION),
        validator_version=available("test-shadow-validator-v1"),
        generator=available(
            StaticSymbolIdentity(
                "src.tests.cuts.rule_cut_evolution.contract_harness",
                "generate_proof",
            )
        ),
        orchestrator=available(
            StaticSymbolIdentity(
                "src.tests.cuts.rule_cut_evolution.contract_harness",
                "test_only_semantic_chain",
            )
        ),
        adapter_factory=unavailable("generator-has-no-separate-adapter"),
        preparation_steps=(),
        generator_parameter_ids=("premises", "snapshot_fingerprint"),
        orchestration_context_ids=("premises", "snapshot_fingerprint"),
        production_typed_order=4,
    )
    return FamilySpecRegistry(
        schema_version=1,
        rule_semantics=rule_registry,
        trust_specs={**SHADOW_FAMILY_SPECS_V1.trust_specs, SHADOW_FAMILY: trust},
        generation_specs={
            **SHADOW_FAMILY_SPECS_V1.generation_specs,
            SHADOW_FAMILY: generation,
        },
        typed_generation_order=(
            *SHADOW_FAMILY_SPECS_V1.typed_generation_order,
            SHADOW_FAMILY,
        ),
    )


def generate_proof(
    premises: ShadowPremises = DEFAULT_PREMISES,
    snapshot_fingerprint: str = SHADOW_SNAPSHOT_FINGERPRINT,
) -> bytes:
    payload = {
        "capacity": premises.capacity,
        "cert_kind": "test_region_capacity_witness",
        "family": SHADOW_FAMILY,
        "group_cell_weights": dict(premises.group_cell_weights),
        "premise_digest": premises.digest,
        "semantic_version": premises.semantic_version,
        "snapshot_fingerprint": snapshot_fingerprint,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate proof field {key!r}")
        result[key] = value
    return result


def verify_proof_to_plan(
    proof: bytes,
    *,
    premises: ShadowPremises = DEFAULT_PREMISES,
    snapshot_fingerprint: str = SHADOW_SNAPSHOT_FINGERPRINT,
) -> ConstraintPlan:
    """Strict verifier/compiler for the fixture; all drift rejects pre-plan."""

    if type(proof) is not bytes or not proof:
        raise TypeError("proof must be non-empty exact bytes")
    try:
        parsed = json.loads(
            proof.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("malformed shadow proof") from exc
    if type(parsed) is not dict:
        raise ValueError("shadow proof must be an object")
    expected_fields = cast(
        ProofSchemaSpec,
        build_shadow_onboarding_registry().trust(SHADOW_FAMILY).proof_schema.value,
    ).required_fields
    if frozenset(parsed) != expected_fields:
        raise ValueError("shadow proof fields differ from the closed proof schema")
    if parsed["cert_kind"] != "test_region_capacity_witness":
        raise ValueError("unknown shadow proof type")
    if parsed["family"] != SHADOW_FAMILY:
        raise ValueError("shadow proof family mismatch")
    if parsed["semantic_version"] != premises.semantic_version:
        raise ValueError("shadow semantic version drift")
    if parsed["premise_digest"] != premises.digest:
        raise ValueError("shadow premise drift")
    if parsed["snapshot_fingerprint"] != snapshot_fingerprint:
        raise ValueError("stale shadow snapshot")
    if parsed["capacity"] != premises.capacity:
        raise ValueError("wrong strengthening: capacity differs from complete premises")
    weights = parsed["group_cell_weights"]
    if type(weights) is not dict or weights != dict(premises.group_cell_weights):
        raise ValueError("wrong strengthening: weights differ from complete premises")
    semantic_fingerprint = hashlib.sha256(_SEMANTIC_PREFIX + proof).hexdigest()
    return ConstraintPlan(
        family=SHADOW_FAMILY,
        schema_version=1,
        semantic_fingerprint=semantic_fingerprint,
        model_scope=ModelScope(
            ghost_policy="agnostic",
            ghost_rect_digest=None,
            domain_fingerprint=snapshot_fingerprint,
        ),
        operation="region_capacity_le",
        parameters={
            "capacity": premises.capacity,
            "group_cell_weights": weights,
        },
    )


def independent_interpreter(plan: ConstraintPlan, selected_groups: frozenset[str]) -> bool:
    """Interpret the closed plan without calling the verifier or tiny master."""

    if type(plan) is not ConstraintPlan or plan.family != SHADOW_FAMILY:
        raise TypeError("independent interpreter requires the exact shadow plan")
    if plan.operation != "region_capacity_le":
        raise ValueError("independent interpreter rejects unknown operation")
    weights = plan.parameters["group_cell_weights"]
    capacity = plan.parameters["capacity"]
    if not isinstance(weights, Mapping) or type(capacity) is not int:
        raise TypeError("shadow plan parameter schema drift")
    return sum(cast(int, weights[group]) for group in selected_groups) <= capacity


def independent_exact_checker(premises: ShadowPremises, plan: ConstraintPlan) -> bool:
    """Finite exact twin that does not call generator, verifier, or interpreter."""

    if type(premises) is not ShadowPremises or type(plan) is not ConstraintPlan:
        raise TypeError("exact checker requires exact premises and ConstraintPlan")
    if plan.family != SHADOW_FAMILY or plan.operation != "region_capacity_le":
        return False
    plan_weights = plan.parameters["group_cell_weights"]
    plan_capacity = plan.parameters["capacity"]
    if not isinstance(plan_weights, Mapping) or type(plan_capacity) is not int:
        return False
    groups = tuple(group for group, _weight in premises.group_cell_weights)
    for bits in itertools.product((False, True), repeat=len(groups)):
        selected = tuple(group for group, enabled in zip(groups, bits, strict=True) if enabled)
        ground_truth = (
            sum(premises.weights[group] for group in selected) <= premises.capacity
        )
        plan_truth = sum(cast(int, plan_weights[group]) for group in selected) <= plan_capacity
        if ground_truth != plan_truth:
            return False
    return True


class TinyRealMaster:
    """A tiny real CP-SAT model used only by the contract tests."""

    def __init__(self, groups: tuple[str, ...]) -> None:
        self.model = cp_model.CpModel()
        self.variables = {group: self.model.new_bool_var(group) for group in groups}

    def proto_bytes(self) -> bytes:
        return str(self.model.proto).encode("utf-8")

    def apply(self, plan: ConstraintPlan) -> None:
        """Closed fixture lowering; validates everything before mutation."""

        if type(plan) is not ConstraintPlan or plan.family != SHADOW_FAMILY:
            raise TypeError("tiny master requires the exact shadow plan")
        if plan.model_scope.domain_fingerprint != SHADOW_SNAPSHOT_FINGERPRINT:
            raise ValueError("tiny master rejects stale snapshot before mutation")
        if plan.operation != "region_capacity_le":
            raise ValueError("tiny master rejects unknown operation before mutation")
        raw_weights = plan.parameters["group_cell_weights"]
        capacity = plan.parameters["capacity"]
        if not isinstance(raw_weights, Mapping) or type(capacity) is not int:
            raise TypeError("tiny master rejects malformed plan before mutation")
        if frozenset(raw_weights) != frozenset(self.variables):
            raise ValueError("tiny master rejects premise drift before mutation")
        terms = [
            self.variables[group] * cast(int, raw_weights[group])
            for group in sorted(self.variables)
        ]
        self.model.add(sum(terms) <= capacity)

    def solve_assignment(self, selected_groups: frozenset[str]) -> bool:
        for group, variable in self.variables.items():
            self.model.add(variable == int(group in selected_groups))
        return cp_model.CpSolver().solve(self.model) in {
            cp_model.OPTIMAL,
            cp_model.FEASIBLE,
        }


def production_disposition(*, proof_valid: bool) -> ShadowDisposition:
    """A shadow result never promotes itself onto the trusted apply surface."""

    return ShadowDisposition.HOLD if proof_valid else ShadowDisposition.QUARANTINE
