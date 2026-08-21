"""Independent reconstruction of the supported pure binding semantics.

The implementation reads only data structures supplied by ``artifacts.py`` and
the data-only capsule request.  It does not import production builders, OR-Tools,
or any project helper outside this closed package.

A routing-aware production binding model can only delete patterns or physical
slots relative to this unfiltered reconstruction.  Therefore this model is a
safe relaxation for negative arithmetic reasoning.  Contract v1 nevertheless
rejects an observed routing context, overload separation, or selection nogood:
the monotonicity argument is documented, but those capabilities are not silently
admitted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Dict

from .artifacts import AuthorityArtifacts
from .protocol import (
    SEMANTICS_CONTRACT_SCHEMA,
    ProtocolError,
    canonical_digest,
    strict_int,
    strict_nonempty_string,
    strict_nonnegative_int,
    strict_positive_int,
    to_fraction,
)


_UNUSED = "__unused__"
_NON_FACILITY_MARKERS = frozenset({"ghost_pick"})
_PLAN_OVERRIDE_KEYS = frozenset(
    {"recipes", "production_targets", "commodity_roles"}
)
_ALLOWED_PORT_DIRECTIONS = frozenset({"N", "S", "E", "W"})
_SUPPORTED_BINDING_INPUT_KEYS = frozenset(
    {
        "canonical_commodity_metadata",
        "canonical_rules_payload",
        "generic_input_slots_by_operation",
        "generic_output_slots_by_operation",
        "utility_operation_by_template",
        "required_generic_inputs",
        "required_generic_outputs",
    }
)
_EXPECTED_CONSTRUCTOR_PARAMETERS = frozenset(
    {
        "placement_solution",
        "facility_pools",
        "instances",
        "required_generic_outputs",
        "required_generic_inputs",
        "project_root",
        "io_requirements_path",
        "generic_input_slots_by_operation",
        "generic_output_slots_by_operation",
        "utility_operation_by_template",
        "routing_context",
        "canonical_rules_payload",
        "canonical_commodity_metadata",
    }
)
_EXPECTED_BUILD_PARAMETERS = frozenset({"use_overload_separation"})
_EXPECTED_CONSTRAINT_FAMILIES = (
    "fixed_pose_side_injection",
    "generic_input_exact_cardinality",
    "generic_output_exact_cardinality",
)


class SemanticError(ProtocolError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = str(code)
        self.detail = str(detail)


@dataclass(frozen=True)
class PortCell:
    x: int
    y: int
    direction: str

    def to_dict(self) -> Dict[str, Any]:
        return {"x": self.x, "y": self.y, "dir": self.direction}


@dataclass(frozen=True)
class OperationProfile:
    operation_type: str
    facility_type: str
    input_slot_counts: Mapping[str, int]
    output_slot_counts: Mapping[str, int]
    generic_input_slots: int
    generic_output_slots: int


@dataclass(frozen=True)
class FixedDomain:
    instance_id: str
    operation_type: str
    input_ports: tuple[PortCell, ...]
    output_ports: tuple[PortCell, ...]
    input_slot_counts: Mapping[str, int]
    output_slot_counts: Mapping[str, int]


@dataclass(frozen=True)
class GenericSlot:
    side: str
    instance_id: str
    operation_type: str
    local_index: int
    port: PortCell

    @property
    def slot_id(self) -> str:
        suffix = "in" if self.side == "generic_input" else "out"
        return f"{self.instance_id}:{suffix}:{self.local_index}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "side": self.side,
            "slot_id": self.slot_id,
            "instance_id": self.instance_id,
            "operation_type": self.operation_type,
            "local_index": self.local_index,
            **self.port.to_dict(),
        }


@dataclass(frozen=True)
class BindingSemanticModel:
    artifact_hashes: Mapping[str, str]
    solution_digest: str
    selected_pose_snapshot_digest: str
    fixed_domains: tuple[FixedDomain, ...]
    generic_input_slots: tuple[GenericSlot, ...]
    generic_output_slots: tuple[GenericSlot, ...]
    required_generic_inputs: Mapping[str, int]
    required_generic_outputs: Mapping[str, int]
    generic_input_slots_by_operation: Mapping[str, int]
    generic_output_slots_by_operation: Mapping[str, int]
    utility_operation_by_template: Mapping[str, str]
    source_rejected_selection_count: int
    routing_context_relaxation_active: bool
    runtime_relaxations: tuple[str, ...]


@dataclass(frozen=True)
class ReconstructedProfiles:
    profiles: Mapping[str, OperationProfile]
    generic_input_slots_by_operation: Mapping[str, int]
    generic_output_slots_by_operation: Mapping[str, int]
    utility_operation_by_template: Mapping[str, str]


def build_semantic_model(
    artifacts: AuthorityArtifacts,
    request: Mapping[str, Any],
) -> BindingSemanticModel:
    solution = _require_mapping(request.get("solution"), "request.solution")
    caller_instances = _index_instances(
        request.get("caller_instances"),
        "request.caller_instances",
    )
    caller_selected_poses = _require_mapping(
        request.get("caller_selected_poses"),
        "request.caller_selected_poses",
    )
    binding_inputs = _require_mapping(
        request.get("binding_inputs"),
        "request.binding_inputs",
    )
    unknown_binding_inputs = sorted(
        str(key) for key in set(binding_inputs) - _SUPPORTED_BINDING_INPUT_KEYS
    )
    if unknown_binding_inputs:
        raise SemanticError(
            "UNSUPPORTED_BINDING_SEMANTICS",
            ",".join(unknown_binding_inputs),
        )

    reconstructed = _derive_operation_profiles(
        artifacts.canonical_rules,
        artifacts.preprocess_plan,
    )
    routing_context_relaxation_active = _validate_semantics_contract(
        request.get("semantics_contract"),
        reconstructed,
    )

    caller_rules = binding_inputs.get("canonical_rules_payload")
    if caller_rules is not None:
        _require_semantic_match(
            caller_rules,
            artifacts.canonical_rules,
            "CALLER_CANONICAL_RULES_DRIFT",
        )
    commodity_metadata = _require_mapping(
        artifacts.canonical_rules.get("commodity_metadata"),
        "canonical_rules.commodity_metadata",
    )
    caller_metadata = binding_inputs.get("canonical_commodity_metadata")
    if caller_metadata is not None:
        _require_semantic_match(
            caller_metadata,
            commodity_metadata,
            "CALLER_COMMODITY_METADATA_DRIFT",
        )

    required_outputs = _normalize_requirements(
        artifacts.generic_io_requirements.get("required_generic_outputs"),
        "required_generic_outputs",
    )
    required_inputs = _normalize_requirements(
        artifacts.generic_io_requirements.get("required_generic_inputs"),
        "required_generic_inputs",
    )
    _require_optional_requirement_match(
        binding_inputs.get("required_generic_outputs"),
        required_outputs,
        "CALLER_GENERIC_OUTPUT_REQUIREMENTS_DRIFT",
    )
    _require_optional_requirement_match(
        binding_inputs.get("required_generic_inputs"),
        required_inputs,
        "CALLER_GENERIC_INPUT_REQUIREMENTS_DRIFT",
    )
    _validate_generic_roles(
        required_outputs=required_outputs,
        required_inputs=required_inputs,
        commodity_metadata=commodity_metadata,
    )
    positive_overlap = sorted(
        {commodity for commodity, count in required_outputs.items() if count > 0}
        & {commodity for commodity, count in required_inputs.items() if count > 0}
    )
    if positive_overlap:
        raise SemanticError(
            "GENERIC_OUTPUT_INPUT_ROLE_OVERLAP",
            ",".join(positive_overlap),
        )

    _require_slot_map_match(
        binding_inputs.get("generic_input_slots_by_operation"),
        reconstructed.generic_input_slots_by_operation,
        "GENERIC_INPUT_SLOT_MAP_DRIFT",
        required=True,
    )
    _require_slot_map_match(
        binding_inputs.get("generic_output_slots_by_operation"),
        reconstructed.generic_output_slots_by_operation,
        "GENERIC_OUTPUT_SLOT_MAP_DRIFT",
        required=True,
    )
    _require_string_map_match(
        binding_inputs.get("utility_operation_by_template"),
        reconstructed.utility_operation_by_template,
        "UTILITY_OPERATION_MAP_DRIFT",
    )

    authority_instances = _index_instances(
        artifacts.mandatory_instances,
        "mandatory_exact_instances",
    )
    if set(caller_instances) != set(authority_instances):
        raise SemanticError(
            "CALLER_INSTANCE_SET_DRIFT",
            "missing="
            + ",".join(sorted(set(authority_instances) - set(caller_instances)))
            + ";extra="
            + ",".join(sorted(set(caller_instances) - set(authority_instances))),
        )
    for instance_id in sorted(authority_instances):
        _require_semantic_match(
            caller_instances[instance_id],
            authority_instances[instance_id],
            f"CALLER_INSTANCE_METADATA_DRIFT:{instance_id}",
        )
    pose_optional_operation_by_template = (
        _derive_pose_optional_operation_by_template(
            reconstructed.utility_operation_by_template,
            authority_instances,
        )
    )

    solution_ids = {
        strict_nonempty_string(raw_instance_id, "solution.instance_id")
        for raw_instance_id in solution
    }
    missing_mandatory = sorted(set(authority_instances) - solution_ids)
    if missing_mandatory:
        raise SemanticError(
            "MANDATORY_PLACEMENT_MISSING",
            ",".join(missing_mandatory),
        )

    canonical_facility_types = {
        profile.facility_type for profile in reconstructed.profiles.values()
    }
    fixed_domains: list[FixedDomain] = []
    input_slots: list[GenericSlot] = []
    output_slots: list[GenericSlot] = []
    selected_pose_preimage: list[Dict[str, Any]] = []

    for raw_instance_id in sorted(solution, key=str):
        instance_id = strict_nonempty_string(raw_instance_id, "solution.instance_id")
        if instance_id in _NON_FACILITY_MARKERS:
            continue
        entry = _require_mapping(solution[raw_instance_id], f"solution.{instance_id}")
        instance = caller_instances.get(instance_id)
        if instance is None:
            instance = _synthesize_pose_optional(
                instance_id,
                entry,
                pose_optional_operation_by_template,
            )

        facility_type = strict_nonempty_string(
            entry.get("facility_type"),
            f"solution.{instance_id}.facility_type",
        )
        instance_facility_type = strict_nonempty_string(
            instance.get("facility_type"),
            f"instances.{instance_id}.facility_type",
        )
        if facility_type != instance_facility_type:
            raise SemanticError(
                "FACILITY_TYPE_MISMATCH",
                f"{instance_id}:{facility_type}!={instance_facility_type}",
            )
        pose_index = strict_int(
            entry.get("pose_idx"),
            f"solution.{instance_id}.pose_idx",
        )
        authority_pool = artifacts.facility_pools.get(facility_type)
        if authority_pool is None:
            raise SemanticError("AUTHORITY_FACILITY_POOL_MISSING", facility_type)
        if pose_index < 0 or pose_index >= len(authority_pool):
            raise SemanticError(
                "POSE_INDEX_OUT_OF_RANGE",
                f"{instance_id}:{facility_type}[{pose_index}]",
            )
        authority_pose = _require_mapping(
            authority_pool[pose_index],
            f"candidate_placements.{facility_type}[{pose_index}]",
        )
        caller_pose = caller_selected_poses.get(instance_id)
        if caller_pose is None:
            raise SemanticError("CALLER_SELECTED_POSE_MISSING", instance_id)
        _require_semantic_match(
            caller_pose,
            authority_pose,
            f"CALLER_SELECTED_POSE_DRIFT:{instance_id}",
        )
        input_ports = _normalize_ports(
            authority_pose.get("input_port_cells", []),
            f"pose.{instance_id}.input_port_cells",
        )
        output_ports = _normalize_ports(
            authority_pose.get("output_port_cells", []),
            f"pose.{instance_id}.output_port_cells",
        )
        selected_pose_preimage.append(
            {
                "instance_id": instance_id,
                "facility_type": facility_type,
                "pose_idx": pose_index,
                "pose_digest": canonical_digest(authority_pose),
            }
        )

        raw_operation_type = instance.get("operation_type")
        operation_type = "" if raw_operation_type is None else str(raw_operation_type)
        if not operation_type:
            if facility_type in canonical_facility_types:
                raise SemanticError("MISSING_OPERATION_TYPE", instance_id)
            continue
        profile = reconstructed.profiles.get(operation_type)
        if profile is None:
            if facility_type in canonical_facility_types:
                raise SemanticError(
                    "UNKNOWN_OPERATION_TYPE",
                    f"{instance_id}:{operation_type}",
                )
            continue
        if profile.facility_type != facility_type:
            raise SemanticError(
                "OPERATION_FACILITY_MISMATCH",
                f"{instance_id}:{operation_type}",
            )

        if profile.generic_input_slots == 0 and profile.generic_output_slots == 0:
            required_input_count = sum(profile.input_slot_counts.values())
            required_output_count = sum(profile.output_slot_counts.values())
            if required_input_count > len(input_ports) or required_output_count > len(
                output_ports
            ):
                raise SemanticError(
                    "PRODUCTION_EXCEPTION_CLASS_PORT_SHORTFALL",
                    f"{instance_id}:input {required_input_count}/{len(input_ports)};"
                    f"output {required_output_count}/{len(output_ports)}",
                )
            fixed_domains.append(
                FixedDomain(
                    instance_id=instance_id,
                    operation_type=operation_type,
                    input_ports=input_ports,
                    output_ports=output_ports,
                    input_slot_counts=dict(profile.input_slot_counts),
                    output_slot_counts=dict(profile.output_slot_counts),
                )
            )

        if required_outputs and profile.generic_output_slots > 0:
            if len(output_ports) != profile.generic_output_slots:
                raise SemanticError(
                    "GENERIC_OUTPUT_PHYSICAL_PORT_COUNT_DRIFT",
                    f"{operation_type}/{instance_id}:declared={profile.generic_output_slots};"
                    f"physical={len(output_ports)}",
                )
            output_slots.extend(
                GenericSlot(
                    side="generic_output",
                    instance_id=instance_id,
                    operation_type=operation_type,
                    local_index=index,
                    port=port,
                )
                for index, port in enumerate(output_ports)
            )
        if required_inputs and profile.generic_input_slots > 0:
            if len(input_ports) != profile.generic_input_slots:
                raise SemanticError(
                    "GENERIC_INPUT_PHYSICAL_PORT_COUNT_DRIFT",
                    f"{operation_type}/{instance_id}:declared={profile.generic_input_slots};"
                    f"physical={len(input_ports)}",
                )
            input_slots.extend(
                GenericSlot(
                    side="generic_input",
                    instance_id=instance_id,
                    operation_type=operation_type,
                    local_index=index,
                    port=port,
                )
                for index, port in enumerate(input_ports)
            )

    source_rejected_selection_count = strict_nonnegative_int(
        _require_mapping(
            request.get("semantics_contract"),
            "request.semantics_contract",
        ).get("source_rejected_selection_count", 0),
        "semantics_contract.source_rejected_selection_count",
    )
    return BindingSemanticModel(
        artifact_hashes=dict(artifacts.hashes),
        solution_digest=canonical_digest(solution),
        selected_pose_snapshot_digest=canonical_digest(selected_pose_preimage),
        fixed_domains=tuple(sorted(fixed_domains, key=lambda item: item.instance_id)),
        generic_input_slots=tuple(sorted(input_slots, key=lambda item: item.slot_id)),
        generic_output_slots=tuple(sorted(output_slots, key=lambda item: item.slot_id)),
        required_generic_inputs=required_inputs,
        required_generic_outputs=required_outputs,
        generic_input_slots_by_operation=dict(
            reconstructed.generic_input_slots_by_operation
        ),
        generic_output_slots_by_operation=dict(
            reconstructed.generic_output_slots_by_operation
        ),
        utility_operation_by_template=dict(
            reconstructed.utility_operation_by_template
        ),
        source_rejected_selection_count=source_rejected_selection_count,
        routing_context_relaxation_active=routing_context_relaxation_active,
        runtime_relaxations=(
            ("routing_context_domain_filter_omitted_monotone_superset",)
            if routing_context_relaxation_active
            else ()
        ),
    )


def _validate_semantics_contract(
    raw: Any,
    reconstructed: ReconstructedProfiles,
) -> bool:
    contract = _require_mapping(raw, "request.semantics_contract")
    if contract.get("schema") != SEMANTICS_CONTRACT_SCHEMA:
        raise SemanticError(
            "SEMANTICS_CONTRACT_SCHEMA_UNSUPPORTED",
            repr(contract.get("schema")),
        )
    expected_keys = {
        "schema",
        "constructor_parameters",
        "build_parameters",
        "constraint_families",
        "routing_context_enabled",
        "overload_separation_enabled",
        "reverification_selection_nogood_count",
        "source_rejected_selection_count",
        "generic_input_slot_policy",
        "generic_output_slot_policy",
        "plan_generic_input_slots_by_operation",
        "plan_generic_output_slots_by_operation",
        "plan_utility_operation_by_template",
    }
    if set(contract) != expected_keys:
        raise SemanticError(
            "SEMANTICS_CONTRACT_KEYS_DRIFT",
            f"missing={sorted(expected_keys - set(contract))};"
            f"extra={sorted(set(contract) - expected_keys)}",
        )
    constructor_parameters = _string_set(
        contract.get("constructor_parameters"),
        "semantics_contract.constructor_parameters",
    )
    if constructor_parameters != _EXPECTED_CONSTRUCTOR_PARAMETERS:
        raise SemanticError(
            "BINDING_CONSTRUCTOR_SURFACE_DRIFT",
            f"caller={sorted(constructor_parameters)};"
            f"expected={sorted(_EXPECTED_CONSTRUCTOR_PARAMETERS)}",
        )
    build_parameters = _string_set(
        contract.get("build_parameters"),
        "semantics_contract.build_parameters",
    )
    if build_parameters != _EXPECTED_BUILD_PARAMETERS:
        raise SemanticError(
            "BINDING_BUILD_SURFACE_DRIFT",
            f"caller={sorted(build_parameters)};expected={sorted(_EXPECTED_BUILD_PARAMETERS)}",
        )
    families = tuple(
        _string_sequence(
            contract.get("constraint_families"),
            "semantics_contract.constraint_families",
        )
    )
    if families != _EXPECTED_CONSTRAINT_FAMILIES:
        raise SemanticError(
            "BINDING_CONSTRAINT_FAMILY_DRIFT",
            f"caller={families};expected={_EXPECTED_CONSTRAINT_FAMILIES}",
        )
    # A routing-aware production filter only removes binding-domain choices.
    # Rebuilding the unfiltered domain is therefore a monotone superset: an
    # arithmetic infeasibility proof for that superset remains valid for the
    # filtered production model.  The observed bit is still certificate-bound.
    routing_context_enabled = contract.get("routing_context_enabled")
    if not isinstance(routing_context_enabled, bool):
        raise SemanticError(
            "ROUTING_CONTEXT_OBSERVATION_INVALID",
            "must be a strict bool",
        )
    routing_context_relaxation_active = routing_context_enabled
    if contract.get("overload_separation_enabled") is not False:
        raise SemanticError("OVERLOAD_SEPARATION_UNSUPPORTED", "must be false")
    if strict_nonnegative_int(
        contract.get("reverification_selection_nogood_count"),
        "semantics_contract.reverification_selection_nogood_count",
    ) != 0:
        raise SemanticError("SELECTION_NOGOOD_UNSUPPORTED", "must be zero")
    strict_nonnegative_int(
        contract.get("source_rejected_selection_count"),
        "semantics_contract.source_rejected_selection_count",
    )
    if contract.get("generic_input_slot_policy") != "plan_derived_physical_exact_count":
        raise SemanticError("GENERIC_INPUT_SLOT_POLICY_DRIFT", "unsupported policy")
    if contract.get("generic_output_slot_policy") != "plan_derived_physical_exact_count":
        raise SemanticError("GENERIC_OUTPUT_SLOT_POLICY_DRIFT", "unsupported policy")
    _require_slot_map_match(
        contract.get("plan_generic_input_slots_by_operation"),
        reconstructed.generic_input_slots_by_operation,
        "SEMANTICS_CONTRACT_INPUT_PLAN_DRIFT",
        required=True,
    )
    _require_slot_map_match(
        contract.get("plan_generic_output_slots_by_operation"),
        reconstructed.generic_output_slots_by_operation,
        "SEMANTICS_CONTRACT_OUTPUT_PLAN_DRIFT",
        required=True,
    )
    _require_string_map_match(
        contract.get("plan_utility_operation_by_template"),
        reconstructed.utility_operation_by_template,
        "SEMANTICS_CONTRACT_UTILITY_PLAN_DRIFT",
    )
    return routing_context_relaxation_active


def _derive_operation_profiles(
    rules: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> ReconstructedProfiles:
    forbidden = sorted(key for key in _PLAN_OVERRIDE_KEYS if key in plan)
    if forbidden:
        raise SemanticError("PREPROCESS_PLAN_NOT_ADDITIVE", ",".join(forbidden))
    globals_payload = _mapping_or_empty(rules.get("globals"))
    logistics = _mapping_or_empty(globals_payload.get("logistics"))
    belt_capacity = to_fraction(
        logistics.get("belt_capacity_per_tick", 1),
        "globals.logistics.belt_capacity_per_tick",
    )
    if belt_capacity <= 0:
        raise SemanticError("BELT_CAPACITY_NOT_POSITIVE", str(belt_capacity))

    profiles: Dict[str, OperationProfile] = {}
    recipes = _mapping_or_empty(rules.get("recipes"))
    for raw_recipe_id, raw_recipe in sorted(recipes.items(), key=lambda item: str(item[0])):
        recipe_id = strict_nonempty_string(raw_recipe_id, "recipes.recipe_id")
        recipe = _require_mapping(raw_recipe, f"recipes.{recipe_id}")
        if set(recipe) != {"template", "ticks_per_cycle", "inputs", "outputs"}:
            raise SemanticError(
                "RECIPE_SCHEMA_DRIFT",
                f"{recipe_id}:{sorted(recipe)}",
            )
        ticks = strict_positive_int(
            recipe.get("ticks_per_cycle"),
            f"recipes.{recipe_id}.ticks_per_cycle",
        )
        outputs = _derive_slot_counts(
            recipe.get("outputs"),
            ticks=ticks,
            belt_capacity=belt_capacity,
            field=f"recipes.{recipe_id}.outputs",
        )
        if not outputs:
            raise SemanticError("RECIPE_OUTPUTS_EMPTY", recipe_id)
        profiles[recipe_id] = OperationProfile(
            operation_type=recipe_id,
            facility_type=strict_nonempty_string(
                recipe.get("template"),
                f"recipes.{recipe_id}.template",
            ),
            input_slot_counts=_derive_slot_counts(
                recipe.get("inputs"),
                ticks=ticks,
                belt_capacity=belt_capacity,
                field=f"recipes.{recipe_id}.inputs",
            ),
            output_slot_counts=outputs,
            generic_input_slots=0,
            generic_output_slots=0,
        )

    utility_operations = _mapping_or_empty(plan.get("utility_operations"))
    utility_operation_by_template: Dict[str, str] = {}
    for raw_operation_type, raw_utility in sorted(
        utility_operations.items(), key=lambda item: str(item[0])
    ):
        operation_type = strict_nonempty_string(
            raw_operation_type,
            "utility_operations.operation_type",
        )
        if operation_type in profiles:
            raise SemanticError("UTILITY_OPERATION_NAMESPACE_COLLISION", operation_type)
        utility = _require_mapping(
            raw_utility,
            f"utility_operations.{operation_type}",
        )
        expected_utility_keys = {
            "facility_type",
            "generic_input_slots",
            "generic_output_slots",
        }
        if set(utility) != expected_utility_keys:
            raise SemanticError(
                "UTILITY_OPERATION_SCHEMA_DRIFT",
                f"{operation_type}:{sorted(utility)}",
            )
        facility_type = strict_nonempty_string(
            utility.get("facility_type"),
            f"utility_operations.{operation_type}.facility_type",
        )
        previous_operation = utility_operation_by_template.get(facility_type)
        if previous_operation is not None and previous_operation != operation_type:
            raise SemanticError(
                "UTILITY_FACILITY_OPERATION_AMBIGUITY",
                f"{facility_type}:{previous_operation},{operation_type}",
            )
        utility_operation_by_template[facility_type] = operation_type
        profiles[operation_type] = OperationProfile(
            operation_type=operation_type,
            facility_type=facility_type,
            input_slot_counts={},
            output_slot_counts={},
            generic_input_slots=strict_nonnegative_int(
                utility.get("generic_input_slots"),
                f"utility_operations.{operation_type}.generic_input_slots",
            ),
            generic_output_slots=strict_nonnegative_int(
                utility.get("generic_output_slots"),
                f"utility_operations.{operation_type}.generic_output_slots",
            ),
        )
    if not profiles:
        raise SemanticError("OPERATION_PROFILES_EMPTY", "rules+plan")
    input_map = {
        operation_type: profile.generic_input_slots
        for operation_type, profile in sorted(profiles.items())
        if profile.generic_input_slots > 0
    }
    output_map = {
        operation_type: profile.generic_output_slots
        for operation_type, profile in sorted(profiles.items())
        if profile.generic_output_slots > 0
    }
    return ReconstructedProfiles(
        profiles=profiles,
        generic_input_slots_by_operation=input_map,
        generic_output_slots_by_operation=output_map,
        utility_operation_by_template=dict(
            sorted(utility_operation_by_template.items())
        ),
    )


def _derive_slot_counts(
    raw: Any,
    *,
    ticks: int,
    belt_capacity: Fraction,
    field: str,
) -> Dict[str, int]:
    section = _mapping_or_empty(raw)
    result: Dict[str, int] = {}
    for raw_commodity, raw_value in sorted(section.items(), key=lambda item: str(item[0])):
        commodity = strict_nonempty_string(raw_commodity, f"{field}.commodity")
        if commodity in result:
            raise SemanticError("COMMODITY_KEY_COLLISION", f"{field}:{commodity}")
        rate = to_fraction(raw_value, f"{field}.{commodity}") / ticks
        if rate <= 0:
            result[commodity] = 0
            continue
        required = rate / belt_capacity
        result[commodity] = int(
            (required.numerator + required.denominator - 1) // required.denominator
        )
    return dict(sorted(result.items()))


def _normalize_requirements(raw: Any, field: str) -> Dict[str, int]:
    section = _mapping_or_empty(raw)
    result: Dict[str, int] = {}
    for raw_commodity, raw_count in section.items():
        commodity = strict_nonempty_string(raw_commodity, f"{field}.commodity")
        if commodity == _UNUSED:
            raise SemanticError("UNUSED_SENTINEL_IN_REQUIREMENTS", field)
        if commodity in result:
            raise SemanticError("COMMODITY_KEY_COLLISION", f"{field}:{commodity}")
        result[commodity] = strict_nonnegative_int(raw_count, f"{field}.{commodity}")
    return dict(sorted(result.items()))


def _validate_generic_roles(
    *,
    required_outputs: Mapping[str, int],
    required_inputs: Mapping[str, int],
    commodity_metadata: Mapping[str, Any],
) -> None:
    if not required_outputs and not required_inputs:
        return
    for commodity in required_outputs:
        metadata = commodity_metadata.get(commodity)
        if not isinstance(metadata, Mapping):
            raise SemanticError("GENERIC_OUTPUT_COMMODITY_UNREGISTERED", commodity)
        if metadata.get("source_kind") != "external_boundary":
            raise SemanticError("GENERIC_OUTPUT_ROLE_MISMATCH", commodity)
    for commodity in required_inputs:
        metadata = commodity_metadata.get(commodity)
        if not isinstance(metadata, Mapping):
            raise SemanticError("GENERIC_INPUT_COMMODITY_UNREGISTERED", commodity)
        if metadata.get("sink_kind") != "generic_input":
            raise SemanticError("GENERIC_INPUT_ROLE_MISMATCH", commodity)
    canonical_inputs = sorted(
        str(commodity)
        for commodity, metadata in commodity_metadata.items()
        if isinstance(metadata, Mapping) and metadata.get("sink_kind") == "generic_input"
    )
    missing = [commodity for commodity in canonical_inputs if commodity not in required_inputs]
    non_positive = [
        commodity
        for commodity in canonical_inputs
        if commodity in required_inputs and required_inputs[commodity] <= 0
    ]
    if missing or non_positive:
        raise SemanticError(
            "GENERIC_INPUT_COMPLETENESS_DRIFT",
            f"missing={missing};non_positive={non_positive}",
        )


def _require_optional_requirement_match(
    caller_value: Any,
    expected: Mapping[str, int],
    code: str,
) -> None:
    if caller_value is None:
        if expected:
            raise SemanticError(code, "caller omitted non-empty authority value")
        return
    normalized = _normalize_requirements(caller_value, code)
    if normalized != dict(expected):
        raise SemanticError(code, f"caller={normalized};expected={dict(expected)}")


def _require_string_map_match(
    raw: Any,
    expected: Mapping[str, str],
    code: str,
) -> None:
    if not isinstance(raw, Mapping):
        raise SemanticError(code, "caller omitted plan-derived identity map")
    normalized: Dict[str, str] = {}
    for raw_key, raw_value in raw.items():
        key = strict_nonempty_string(raw_key, f"{code}.key")
        value = strict_nonempty_string(raw_value, f"{code}.{key}")
        if key in normalized:
            raise SemanticError(code, f"duplicate key {key}")
        normalized[key] = value
    normalized = dict(sorted(normalized.items()))
    if normalized != dict(expected):
        raise SemanticError(code, f"caller={normalized};expected={dict(expected)}")


def _require_slot_map_match(
    raw: Any,
    expected: Mapping[str, int],
    code: str,
    *,
    required: bool,
) -> None:
    if raw is None:
        if required or expected:
            raise SemanticError(code, "caller omitted plan-derived slot map")
        return
    if not isinstance(raw, Mapping):
        raise SemanticError(code, f"not mapping: {type(raw).__name__}")
    normalized: Dict[str, int] = {}
    for raw_operation_type, raw_count in raw.items():
        operation_type = strict_nonempty_string(raw_operation_type, f"{code}.operation")
        count = strict_positive_int(raw_count, f"{code}.{operation_type}")
        if operation_type in normalized:
            raise SemanticError(code, f"duplicate operation {operation_type}")
        normalized[operation_type] = count
    normalized = dict(sorted(normalized.items()))
    if normalized != dict(expected):
        raise SemanticError(code, f"caller={normalized};expected={dict(expected)}")


def _index_instances(raw: Any, field: str) -> Dict[str, Mapping[str, Any]]:
    if isinstance(raw, (str, bytes, bytearray)) or not isinstance(raw, Sequence):
        raise SemanticError("INSTANCES_NOT_ARRAY", f"{field}:{type(raw).__name__}")
    result: Dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(raw):
        instance = _require_mapping(item, f"{field}[{index}]")
        instance_id = strict_nonempty_string(
            instance.get("instance_id"),
            f"{field}[{index}].instance_id",
        )
        if instance_id in result:
            raise SemanticError("DUPLICATE_INSTANCE_ID", f"{field}:{instance_id}")
        result[instance_id] = instance
    return result


def _derive_pose_optional_operation_by_template(
    utility_operation_by_template: Mapping[str, str],
    authoritative_instances: Mapping[str, Mapping[str, Any]],
) -> Dict[str, str]:
    represented_operations = {
        str(instance.get("operation_type", ""))
        for instance in authoritative_instances.values()
        if str(instance.get("operation_type", ""))
    }
    return {
        facility_type: operation_type
        for facility_type, operation_type in sorted(
            utility_operation_by_template.items()
        )
        if operation_type not in represented_operations
    }


def _synthesize_pose_optional(
    instance_id: str,
    solution_entry: Mapping[str, Any],
    operation_by_template: Mapping[str, str],
) -> Mapping[str, Any]:
    if not instance_id.startswith("pose_optional::"):
        raise SemanticError("MISSING_INSTANCE_METADATA", instance_id)
    parts = instance_id.split("::")
    if len(parts) < 3 or not parts[1]:
        raise SemanticError("MISSING_INSTANCE_METADATA", instance_id)
    inferred_template = parts[1]
    solution_template = str(solution_entry.get("facility_type") or "")
    if solution_template and solution_template != inferred_template:
        raise SemanticError(
            "POSE_OPTIONAL_TEMPLATE_IDENTITY_MISMATCH",
            f"{instance_id}:{solution_template}!={inferred_template}",
        )
    facility_type = inferred_template
    operation_type = operation_by_template.get(facility_type)
    if operation_type is None:
        raise SemanticError("MISSING_INSTANCE_METADATA", instance_id)
    return {
        "instance_id": instance_id,
        "facility_type": facility_type,
        "operation_type": operation_type,
    }


def _normalize_ports(raw: Any, field: str) -> tuple[PortCell, ...]:
    if raw is None:
        raw = []
    if isinstance(raw, (str, bytes, bytearray)) or not isinstance(raw, Sequence):
        raise SemanticError("PORT_CELLS_NOT_ARRAY", f"{field}:{type(raw).__name__}")
    result: list[PortCell] = []
    for index, item in enumerate(raw):
        port = _require_mapping(item, f"{field}[{index}]")
        direction = strict_nonempty_string(port.get("dir"), f"{field}[{index}].dir")
        if direction not in _ALLOWED_PORT_DIRECTIONS:
            raise SemanticError("PORT_DIRECTION_INVALID", f"{field}[{index}]:{direction}")
        result.append(
            PortCell(
                x=strict_int(port.get("x"), f"{field}[{index}].x"),
                y=strict_int(port.get("y"), f"{field}[{index}].y"),
                direction=direction,
            )
        )
    return tuple(sorted(result, key=lambda port: (port.x, port.y, port.direction)))


def _require_semantic_match(caller: Any, authority: Any, code: str) -> None:
    caller_digest = canonical_digest(caller)
    authority_digest = canonical_digest(authority)
    if caller_digest != authority_digest:
        raise SemanticError(
            code,
            f"caller_digest={caller_digest};authority_digest={authority_digest}",
        )


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}
    return _require_mapping(value, "mapping")


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SemanticError("EXPECTED_MAPPING", f"{field}:{type(value).__name__}")
    return value


def _string_set(raw: Any, field: str) -> frozenset[str]:
    return frozenset(_string_sequence(raw, field))


def _string_sequence(raw: Any, field: str) -> tuple[str, ...]:
    if isinstance(raw, (str, bytes, bytearray)) or not isinstance(raw, Sequence):
        raise SemanticError("EXPECTED_STRING_ARRAY", field)
    values = tuple(strict_nonempty_string(item, f"{field}[]") for item in raw)
    if len(set(values)) != len(values):
        raise SemanticError("DUPLICATE_STRING_ARRAY_VALUE", field)
    return values
