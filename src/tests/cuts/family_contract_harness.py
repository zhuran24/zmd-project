"""Reusable, test-only acceptance harness for a newly wired cut family.

The objects in this module never enter the production manifest.  In
particular, ``test_region_capacity_contract`` is not a lifecycle ``Cut`` family
and has no wire-schema row.  It exists only to prove that a family with its own
generator/verifier/checker roles can reuse the already-closed
``region_capacity_le`` lowering primitive through one local manifest row.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Final, Literal, cast

from src.cuts import typed_platform as _platform
from src.cuts.family_specs import (
    AvailableCapability,
    FamilyGenerationSpec,
    FamilySpecRegistry,
    FamilyTrustSpec,
    PluginProviderKind,
    PluginProviderSpec,
    ProofSchemaSpec,
    PRODUCTION_FAMILY_MANIFEST_V1,
    StaticObjectRef,
    StaticSymbolIdentity,
)
from src.cuts.rule_semantics import (
    PRODUCTION_RULE_SEMANTICS_V1,
    RuleSemanticFacet,
    RuleSemanticRegistry,
    VersionedRuleRef,
)
from src.cuts.state_snapshot import ValidatedStateSnapshot
from src.cuts.typed_platform import (
    CompiledCut,
    ConstraintPlan,
    CutEnvelope,
    CutRejection,
    FamilyCapabilityRegistry,
    FamilyPlugin,
    FrozenFamilyProof,
    ModelScope,
    SemanticCutRejection,
    cut_to_envelope_v1,
    validate_and_compile_cut,
)
from src.tests.cuts import test_stage_b_region_capacity as _f1_fixture


TEST_ONLY_FAMILY: Final = "test_region_capacity_contract"
TEST_ONLY_GROUP_ID: Final = "group::miner::mining::0"
TEST_ONLY_CERT_KIND: Final = "test_only_region_capacity_contract"
_TEST_ONLY_FINGERPRINT_PREFIX: Final = b"zmd.test.family-contract.semantic.v1:"


@dataclass(frozen=True, slots=True)
class ContractEvidence:
    """One stable pytest node that witnesses a family contract."""

    node_id: str
    seam: str
    expected_failure: str
    authority_effect: Literal["none"] = "none"

    def __post_init__(self) -> None:
        if (
            type(self.node_id) is not str
            or self.node_id.count("::") != 1
            or not self.node_id.startswith("src/tests/cuts/test_")
        ):
            raise ValueError("ContractEvidence.node_id must be one static cut-test node")
        for field_name in ("seam", "expected_failure"):
            value = getattr(self, field_name)
            if type(value) is not str or not value or value.strip() != value:
                raise ValueError(f"ContractEvidence.{field_name} must be a trimmed string")
        if self.authority_effect != "none":
            raise ValueError("family contract evidence must not mutate authority")


def _e(node_id: str, seam: str, expected_failure: str) -> ContractEvidence:
    return ContractEvidence(
        node_id=node_id,
        seam=seam,
        expected_failure=expected_failure,
    )


FAMILY_CONTRACT_EVIDENCE_V1: Final[Mapping[str, tuple[ContractEvidence, ...]]] = (
    MappingProxyType(
        {
            "apply_atomicity": (
                _e(
                    "src/tests/cuts/test_stage_b_contracts.py::"
                    "test_failed_lowering_preserves_master_proto_and_internal_caches",
                    "typed lowering",
                    "master refusal leaves proto and caches unchanged",
                ),
            ),
            "enabled_authority_gate": (
                _e(
                    "src/tests/cuts/test_family_specs_shadow_gate.py::"
                    "test_manifest_protocol_represents_experimental_and_enabled_stages",
                    "manifest stage gate",
                    "enabled authority requires its explicit contract",
                ),
            ),
            "experimental_fail_closed": (
                _e(
                    "src/tests/cuts/test_family_specs_shadow_gate.py::"
                    "test_manifest_protocol_represents_experimental_and_enabled_stages",
                    "manifest stage gate",
                    "experimental rows cannot advertise lowering or replay",
                ),
            ),
            "hold_and_quarantine": (
                _e(
                    "src/tests/cuts/test_replay.py::test_replay_hold_when_exterior_blocks_change",
                    "CutStore replay transition",
                    "recoverable drift remains HOLD",
                ),
                _e(
                    "src/tests/cuts/test_replay.py::test_replay_quarantine_on_integrity_drift",
                    "CutStore replay transition",
                    "integrity drift enters QUARANTINE",
                ),
            ),
            "independent_exact_checker": (
                _e(
                    "src/tests/cuts/test_family_contract_matrix.py::"
                    "test_test_only_family_roles_are_independent_and_non_production",
                    "test-only role separation",
                    "checker role is distinct and is not advertised as production",
                ),
            ),
            "legacy_diagnostic_replay_hold": (
                _e(
                    "src/tests/cuts/test_replay.py::"
                    "test_legacy_family_replay_never_reactivates_into_active_store",
                    "legacy replay",
                    "diagnostic replay cannot reactivate authority",
                ),
            ),
            "malformed_proof": (
                _e(
                    "src/tests/cuts/test_family_contract_matrix.py::"
                    "test_test_only_family_malformed_proof_is_rejected",
                    "typed proof parser",
                    "malformed proof is rejected before plan construction",
                ),
            ),
            "master_proto_unchanged_on_rejection": (
                _e(
                    "src/tests/cuts/test_stage_b_contracts.py::"
                    "test_step_8_rejects_domain_projection_misbinding_without_master_mutation",
                    "step-8 binding gate",
                    "rejection leaves the real master proto unchanged",
                ),
            ),
            "premise_and_version_drift": (
                _e(
                    "src/tests/cuts/test_family_contract_matrix.py::"
                    "test_test_only_family_premise_and_version_drift_are_rejected",
                    "proof and envelope gates",
                    "false premise and schema drift fail before compilation",
                ),
            ),
            "proof_plan_interpreter_tiny_master_exact_chain": (
                _e(
                    "src/tests/cuts/test_family_contract_matrix.py::"
                    "test_test_only_family_full_differential_chain_reuses_closed_operation",
                    "differential acceptance chain",
                    "proof, plan, interpreter, tiny master, and checker must agree",
                ),
            ),
            "replay_fail_closed": (
                _e(
                    "src/tests/cuts/test_replay.py::"
                    "test_replay_quarantine_when_post_attach_validation_unsound",
                    "replay validation",
                    "unsound replay cannot attach",
                ),
            ),
            "retired_fail_closed": (
                _e(
                    "src/tests/cuts/test_family_specs_shadow_gate.py::"
                    "test_contract_ids_and_unavailable_capabilities_fail_closed",
                    "retired manifest capability",
                    "unavailable retired capability raises",
                ),
            ),
            "shadow_zero_master_mutation": (
                _e(
                    "src/tests/cuts/test_stage_b_contracts.py::"
                    "test_step_8_rejects_raw_and_shadow_results_without_touching_master",
                    "step-8 exact type gate",
                    "shadow result is refused before master access",
                ),
            ),
            "stale_snapshot": (
                _e(
                    "src/tests/cuts/test_family_contract_matrix.py::"
                    "test_test_only_family_stale_snapshot_scope_is_rejected",
                    "scope currentness",
                    "stale source identity is rejected before plugin dispatch",
                ),
            ),
            "tcb_fault_propagation": (
                _e(
                    "src/tests/cuts/test_family_contract_matrix.py::"
                    "test_test_only_family_tcb_fault_propagates",
                    "typed plugin TCB boundary",
                    "unexpected verifier exception propagates",
                ),
            ),
            "unknown_type": (
                _e(
                    "src/tests/cuts/test_family_contract_matrix.py::"
                    "test_test_only_family_unknown_entry_type_fails_closed",
                    "single typed entry",
                    "unknown input type fails before dispatch",
                ),
            ),
            "wrong_strengthening": (
                _e(
                    "src/tests/cuts/test_family_contract_matrix.py::"
                    "test_test_only_family_wrong_strengthening_is_rejected",
                    "family plan verifier",
                    "stronger parameters not entailed by the proof are rejected",
                ),
            ),
        }
    )
)


@dataclass(frozen=True, slots=True)
class TestOnlyRegionCapacityProof(FrozenFamilyProof):
    __test__ = False

    cert_kind: str
    capacity: int
    group_cell_weights: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        FrozenFamilyProof.__post_init__(self)
        if self.cert_kind != TEST_ONLY_CERT_KIND:
            raise ValueError("test-only proof has the wrong cert_kind")
        if type(self.capacity) is not int or self.capacity < 0:
            raise ValueError("test-only proof capacity must be a non-negative exact int")
        if (
            type(self.group_cell_weights) is not tuple
            or not self.group_cell_weights
            or tuple(sorted(self.group_cell_weights)) != self.group_cell_weights
        ):
            raise ValueError("test-only proof weights must be a non-empty sorted tuple")
        seen: set[str] = set()
        for group_id, weight in self.group_cell_weights:
            if type(group_id) is not str or not group_id or group_id in seen:
                raise ValueError("test-only proof group IDs must be unique strings")
            if type(weight) is not int or weight <= 0:
                raise ValueError("test-only proof weights must be positive exact ints")
            seen.add(group_id)


@dataclass(frozen=True, slots=True)
class TestOnlyRegionCapacityBody:
    capacity: int
    group_cell_weights: tuple[tuple[str, int], ...]


def generate_test_only_region_capacity_proof(
    *,
    capacity: int,
    group_cell_weights: Mapping[str, int],
) -> bytes:
    """Untrusted test generator; it does not validate the generated claim."""

    proof = {
        "capacity": capacity,
        "cert_kind": TEST_ONLY_CERT_KIND,
        "group_cell_weights": dict(sorted(group_cell_weights.items())),
    }
    return _platform._proof_frame(  # noqa: SLF001 - test-only shared wire primitive
        family=TEST_ONLY_FAMILY,
        schema_version=1,
        proof=proof,
    )


def invoke_test_only_region_capacity_generation(
    capacity: int,
    group_cell_weights: Mapping[str, int],
) -> bytes:
    """Uniform test-only invoker, kept distinct from the generator role."""

    return generate_test_only_region_capacity_proof(
        capacity=capacity,
        group_cell_weights=group_cell_weights,
    )


def verify_test_only_region_capacity_proof(
    proof: TestOnlyRegionCapacityProof,
    snapshot: ValidatedStateSnapshot,
) -> None:
    """Test-only family verifier, independent of generator construction."""

    if type(proof) is not TestOnlyRegionCapacityProof:
        raise TypeError("test-only verifier requires TestOnlyRegionCapacityProof")
    if type(snapshot) is not ValidatedStateSnapshot:
        raise TypeError("test-only verifier requires ValidatedStateSnapshot")
    weighted_demand = 0
    for group_id, weight in proof.group_cell_weights:
        group = snapshot.groups.get(group_id)
        if group is None:
            raise SemanticCutRejection(
                "proof",
                f"test-only proof references unknown group {group_id!r}",
            )
        weighted_demand += weight * group.demand
    if weighted_demand <= proof.capacity:
        raise SemanticCutRejection(
            "proof",
            "test-only proof premise does not establish a violated capacity",
        )


def exact_check_test_only_region_capacity(
    proof: TestOnlyRegionCapacityProof,
    *,
    group_presence_counts: Mapping[str, int],
) -> bool:
    """Brute-force-style test twin; intentionally reads the proof, not plan."""

    total = 0
    for group_id, weight in proof.group_cell_weights:
        count = group_presence_counts.get(group_id, 0)
        if type(count) is not int or count < 0:
            raise ValueError("test-only exact checker counts must be non-negative ints")
        for _unused in range(count):
            total += weight
    return total <= proof.capacity


def interpret_test_only_region_capacity_plan(
    plan: ConstraintPlan,
    *,
    group_presence_counts: Mapping[str, int],
) -> bool:
    """Independent plan interpreter: a direct weighted-sum implementation."""

    if plan.family != TEST_ONLY_FAMILY or plan.operation != "region_capacity_le":
        raise ValueError("test-only interpreter received the wrong family/operation")
    raw_weights = plan.parameters["group_cell_weights"]
    capacity = plan.parameters["capacity"]
    if not isinstance(raw_weights, Mapping) or type(capacity) is not int:
        raise TypeError("test-only interpreter received malformed plan parameters")
    activity = 0
    for group_id, weight in raw_weights.items():
        if type(group_id) is not str or type(weight) is not int:
            raise TypeError("test-only interpreter received malformed weights")
        activity += weight * group_presence_counts.get(group_id, 0)
    return activity <= capacity


def _test_only_semantic_fingerprint(
    *,
    parameters: Mapping[str, object],
    model_scope: ModelScope,
    snapshot: ValidatedStateSnapshot,
) -> str:
    projection = {
        "family": TEST_ONLY_FAMILY,
        "model_scope": {
            "domain_fingerprint": model_scope.domain_fingerprint,
            "ghost_policy": model_scope.ghost_policy,
            "ghost_rect_digest": model_scope.ghost_rect_digest,
        },
        "operation": "region_capacity_le",
        "parameters": parameters,
        "schema_version": 1,
        "snapshot_source_digest": snapshot.source_digest,
    }
    payload = json.dumps(
        projection,
        allow_nan=False,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(_TEST_ONLY_FINGERPRINT_PREFIX + payload).hexdigest()


class TestOnlyRegionCapacityPlugin:
    """Test-only plugin with no lifecycle or production-manifest registration."""

    def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> FrozenFamilyProof:
        try:
            raw = _platform._decode_proof_frame(  # noqa: SLF001 - test-only parser
                proof_payload,
                expected_family=TEST_ONLY_FAMILY,
                expected_schema_version=1,
            )
            if frozenset(raw) != frozenset(
                {"capacity", "cert_kind", "group_cell_weights"}
            ):
                raise ValueError("test-only proof fields are not exact")
            if raw["cert_kind"] != TEST_ONLY_CERT_KIND:
                raise ValueError("test-only proof cert_kind differs")
            raw_capacity = raw["capacity"]
            raw_weights = raw["group_cell_weights"]
            if type(raw_capacity) is not int or raw_capacity < 0:
                raise ValueError("test-only proof capacity is invalid")
            if type(raw_weights) is not dict or not raw_weights:
                raise ValueError("test-only proof weights are invalid")
            checked_weights: list[tuple[str, int]] = []
            for raw_group_id, raw_weight in raw_weights.items():
                if type(raw_group_id) is not str or not raw_group_id:
                    raise ValueError("test-only proof group ID is invalid")
                if type(raw_weight) is not int or raw_weight <= 0:
                    raise ValueError("test-only proof weight is invalid")
                checked_weights.append((raw_group_id, raw_weight))
            proof = TestOnlyRegionCapacityProof(
                family=TEST_ONLY_FAMILY,
                schema_version=1,
                cert_kind=TEST_ONLY_CERT_KIND,
                capacity=raw_capacity,
                group_cell_weights=tuple(sorted(checked_weights)),
            )
        except ValueError as exc:
            raise SemanticCutRejection(
                "proof",
                str(exc) or type(exc).__name__,
            ) from exc
        verify_test_only_region_capacity_proof(proof, snapshot)
        return proof

    def derive_body(self, proof: FrozenFamilyProof) -> object:
        if type(proof) is not TestOnlyRegionCapacityProof:
            raise TypeError("test-only compiler requires its exact proof type")
        return TestOnlyRegionCapacityBody(
            capacity=proof.capacity,
            group_cell_weights=proof.group_cell_weights,
        )

    def compile(
        self,
        body: object,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> ConstraintPlan:
        if (
            type(body) is not TestOnlyRegionCapacityBody
            or type(proof) is not TestOnlyRegionCapacityProof
        ):
            raise TypeError("test-only compiler requires exact body/proof types")
        if (
            body.capacity != proof.capacity
            or body.group_cell_weights != proof.group_cell_weights
        ):
            raise TypeError("test-only body differs from its frozen proof")
        model_scope = ModelScope(
            ghost_policy="agnostic",
            ghost_rect_digest=None,
            domain_fingerprint=snapshot.master_domain_projection,
        )
        parameters: dict[str, object] = {
            "capacity": body.capacity,
            "group_cell_weights": dict(body.group_cell_weights),
        }
        return ConstraintPlan(
            family=TEST_ONLY_FAMILY,
            schema_version=1,
            semantic_fingerprint=_test_only_semantic_fingerprint(
                parameters=parameters,
                model_scope=model_scope,
                snapshot=snapshot,
            ),
            model_scope=model_scope,
            operation="region_capacity_le",
            parameters=parameters,
        )

    def validate_plan(
        self,
        plan: ConstraintPlan,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> None:
        if (
            type(plan) is not ConstraintPlan
            or type(proof) is not TestOnlyRegionCapacityProof
        ):
            raise TypeError("test-only plan verifier requires exact plan/proof types")
        expected_parameters: dict[str, object] = {
            "capacity": proof.capacity,
            "group_cell_weights": dict(proof.group_cell_weights),
        }
        if (
            plan.family != TEST_ONLY_FAMILY
            or plan.schema_version != 1
            or plan.operation != "region_capacity_le"
        ):
            raise SemanticCutRejection(
                "plan",
                "test-only plan family/schema/operation differs",
            )
        if dict(plan.parameters) != expected_parameters:
            raise SemanticCutRejection(
                "plan",
                "test-only plan parameters strengthen or drift from the proof",
            )
        if (
            plan.model_scope.ghost_policy != "agnostic"
            or plan.model_scope.ghost_rect_digest is not None
            or plan.model_scope.domain_fingerprint
            != snapshot.master_domain_projection
        ):
            raise SemanticCutRejection(
                "plan",
                "test-only plan scope differs from the snapshot projection",
            )
        expected_fingerprint = _test_only_semantic_fingerprint(
            parameters=expected_parameters,
            model_scope=plan.model_scope,
            snapshot=snapshot,
        )
        if plan.semantic_fingerprint != expected_fingerprint:
            raise SemanticCutRejection(
                "plan",
                "test-only plan semantic fingerprint is stale",
            )


class TestOnlyTcbFaultPlugin(TestOnlyRegionCapacityPlugin):
    """Fault injector proving unexpected verifier errors remain TCB failures."""

    def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> FrozenFamilyProof:
        del proof_payload, snapshot
        raise RuntimeError("test-only TCB verifier fault")


def _renamed_facet(
    facet: RuleSemanticFacet | None,
    *,
    field_name: str,
) -> RuleSemanticFacet | None:
    if facet is None:
        return None
    return replace(
        facet,
        facet_id=f"{TEST_ONLY_FAMILY}.{field_name}",
    )


def build_test_only_family_manifest(
    *,
    plugin_type: type[TestOnlyRegionCapacityPlugin] = TestOnlyRegionCapacityPlugin,
) -> FamilySpecRegistry:
    """Build a local two-family manifest; production globals stay untouched."""

    if not issubclass(plugin_type, TestOnlyRegionCapacityPlugin):
        raise TypeError("test-only plugin_type must derive from the fixture plugin")
    base_trust = PRODUCTION_FAMILY_MANIFEST_V1.trust("region_capacity")
    base_generation = PRODUCTION_FAMILY_MANIFEST_V1.generation("region_capacity")
    base_rule = PRODUCTION_RULE_SEMANTICS_V1.get("region_capacity")
    fixture_rule = replace(
        base_rule,
        rule_id=TEST_ONLY_FAMILY,
        necessary_projection=_renamed_facet(
            base_rule.necessary_projection,
            field_name="necessary_projection",
        ),
        sufficient_restriction=_renamed_facet(
            base_rule.sufficient_restriction,
            field_name="sufficient_restriction",
        ),
        exact_semantics=_renamed_facet(
            base_rule.exact_semantics,
            field_name="exact_semantics",
        ),
    )
    rule_registry = RuleSemanticRegistry(
        schema_version=1,
        information_dag=PRODUCTION_RULE_SEMANTICS_V1.information_dag,
        rules={
            **PRODUCTION_RULE_SEMANTICS_V1.rules,
            TEST_ONLY_FAMILY: fixture_rule,
        },
    )

    fixture_capability = replace(
        base_trust.capability,
        name=TEST_ONLY_FAMILY,
        validator_version="test-only-family-verifier-v1",
        compiler_version="test-only-family-compiler-v1",
    )
    fixture_provider = PluginProviderSpec(
        kind=PluginProviderKind.FACTORY,
        provider=StaticObjectRef.capture(plugin_type),
        production_order=3,
        factory_construction_order=1,
    )
    fixture_trust = replace(
        base_trust,
        capability=fixture_capability,
        proof_schema=AvailableCapability(
            ProofSchemaSpec(
                family=TEST_ONLY_FAMILY,
                schema_version=1,
                cert_kind=TEST_ONLY_CERT_KIND,
                allowed_fields=frozenset(
                    {"capacity", "cert_kind", "group_cell_weights"}
                ),
                required_fields=frozenset(
                    {"capacity", "cert_kind", "group_cell_weights"}
                ),
            )
        ),
        rule_semantics=(
            VersionedRuleRef(
                rule_id=TEST_ONLY_FAMILY,
                semantic_version=fixture_rule.semantic_version,
            ),
            *base_trust.rule_semantics[1:],
        ),
        typed_plugin=AvailableCapability(fixture_provider),
    )
    fixture_generation = replace(
        base_generation,
        family=TEST_ONLY_FAMILY,
        oracle_name=AvailableCapability("test-only-region-capacity-generator-v1"),
        validator_version=AvailableCapability("test-only-family-verifier-v1"),
        generator=AvailableCapability(
            StaticSymbolIdentity(
                module=__name__,
                qualname="generate_test_only_region_capacity_proof",
            )
        ),
        generation_invoker=AvailableCapability(
            StaticSymbolIdentity(
                module=__name__,
                qualname="invoke_test_only_region_capacity_generation",
            )
        ),
        generator_parameter_ids=("capacity", "group_cell_weights"),
        orchestration_context_ids=("capacity", "group_cell_weights"),
        production_typed_order=1,
    )
    return FamilySpecRegistry(
        schema_version=1,
        rule_semantics=rule_registry,
        trust_specs={
            "region_capacity": base_trust,
            TEST_ONLY_FAMILY: fixture_trust,
        },
        generation_specs={
            "region_capacity": base_generation,
            TEST_ONLY_FAMILY: fixture_generation,
        },
        typed_generation_order=("region_capacity", TEST_ONLY_FAMILY),
    )


def build_test_only_family_registry(
    manifest: FamilySpecRegistry,
) -> FamilyCapabilityRegistry:
    capabilities = {
        family: trust.capability
        for family, trust in manifest.trust_specs.items()
    }
    plugins: dict[str, FamilyPlugin] = {}
    for family in manifest.typed_plugin_order:
        provider = cast(
            PluginProviderSpec,
            manifest.trust(family).typed_plugin.require(
                family=family,
                capability="typed plugin",
            ),
        )
        plugins[family] = provider.build()
    return FamilyCapabilityRegistry(
        capabilities=capabilities,
        plugins=plugins,
        family_specs=manifest,
    )


@dataclass(frozen=True, slots=True)
class TestOnlyFamilyWorld:
    envelope: CutEnvelope
    snapshot: ValidatedStateSnapshot
    manifest: FamilySpecRegistry
    registry: FamilyCapabilityRegistry


def build_test_only_family_world(
    *,
    capacity: int = 1,
    plugin_type: type[TestOnlyRegionCapacityPlugin] = TestOnlyRegionCapacityPlugin,
) -> TestOnlyFamilyWorld:
    """Create a local proof/snapshot/registry world without a lifecycle row."""

    _state, raw_cut, snapshot, _compiled = _f1_fixture._compile_production_cut()
    manifest = build_test_only_family_manifest(plugin_type=plugin_type)
    semantic_version = manifest.rule_semantics.get(
        TEST_ONLY_FAMILY
    ).semantic_version
    base_envelope = cut_to_envelope_v1(raw_cut)
    proof_payload = generate_test_only_region_capacity_proof(
        capacity=capacity,
        group_cell_weights={TEST_ONLY_GROUP_ID: 1},
    )
    scope = replace(
        base_envelope.scope,
        family=TEST_ONLY_FAMILY,
        assumptions=(),
    )
    envelope = replace(
        base_envelope,
        cut_id="test-only-family-contract-cut",
        family=TEST_ONLY_FAMILY,
        proof_payload=proof_payload,
        proof_hash=hashlib.sha256(proof_payload).hexdigest(),
        scope=scope,
        provenance=replace(
            base_envelope.provenance,
            family_version=semantic_version,
            validator_version="test-only-family-verifier-v1",
            oracle_name="test-only-region-capacity-generator-v1",
        ),
    )
    registry = build_test_only_family_registry(manifest)
    return TestOnlyFamilyWorld(
        envelope=envelope,
        snapshot=snapshot,
        manifest=manifest,
        registry=registry,
    )


def compile_test_only_family(world: TestOnlyFamilyWorld) -> CompiledCut:
    result = validate_and_compile_cut(
        world.envelope,
        world.snapshot,
        world.registry,
    )
    if type(result) is CutRejection:
        raise AssertionError(
            f"test-only family unexpectedly rejected at {result.stage}: {result.reason}"
        )
    if type(result) is not CompiledCut:
        raise AssertionError("test-only compilable family did not produce CompiledCut")
    return result
