"""Stage-B typed validate-and-compile platform.

The module is deliberately independent of every master-model implementation.
It accepts one immutable envelope and one validated snapshot, dispatches through
an explicit family registry, and returns one of three immutable result variants.
No function in this module can mutate or even receive a master model.

Schema-v1 ``Cut`` objects enter only through :func:`cut_to_envelope_v1`.  That
adapter proves the legacy body/certificate equality before discarding the body,
then places the canonical proof in a domain-separated, self-describing frame.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import math
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import Callable, Final, Literal, Protocol, TypeAlias, cast

from src.cuts.state_snapshot import (
    F5PatternNogoodInputs,
    GroupSnapshot,
    ValidatedStateSnapshot,
)


FrozenScalar: TypeAlias = None | bool | int | float | str
FrozenParameter: TypeAlias = (
    FrozenScalar | Mapping[str, "FrozenParameter"] | tuple["FrozenParameter", ...] | frozenset["FrozenParameter"]
)
ConstraintOperation: TypeAlias = Literal[
    "region_capacity_le",
    "shape_packing_hall_le",
    "power_pose_exclusion",
]
FamilyMode: TypeAlias = Literal["literal", "geometric"]

SUPPORTED_OPERATIONS: Final = frozenset(
    {
        "power_pose_exclusion",
        "region_capacity_le",
        "shape_packing_hall_le",
    }
)

_PROOF_FRAME_PREFIX = b"zmd.proof.v1:"
_PLAN_DIGEST_PREFIX = b"zmd.constraint-plan.v1:"
_MODEL_SCOPE_DIGEST_PREFIX = b"zmd.model-scope.v1:"
_COMPILED_CUT_DIGEST_PREFIX = b"zmd.compiled-cut.v1:"
_GHOST_RECT_DIGEST_PREFIX = b"zmd.ghost-rect.v1:"
_COMMON_MODE_UNTRUSTED = "common-mode-untrusted"
_GHOST_AGNOSTIC = "__ghost_agnostic__"
_PRODUCTION_V1_ARTIFACT_DEPENDENCIES = frozenset(
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
_MISSING_OPTIONAL_EXACT_ARTIFACT_HASH = "__MISSING_OPTIONAL_EXACT_ARTIFACT__"
_MISSING_ARTIFACT_IDENTITY_PREFIX = b"zmd.missing-artifact-identity.v1:"
_OPTIONAL_PRODUCTION_ARTIFACTS = frozenset({"commodity_demands", "preprocess_plan"})
_MAX_PROOF_JSON_NESTING = 128

# These tokens implement the same Python-level private-construction convention
# as ValidatedStateSnapshot.  Per the owner's 2026-07-06 ruling, deliberate
# in-process attacks through computed getattr/vars, pickle state rewriting, or
# subclass overrides remain deferred to the release-hardening batch.  The
# Stage-B AST gates cover constant reflection, aliases, and production uses.
_COMPILED_CUT_CONSTRUCTION_TOKEN: Final = object()
_SHADOW_VALIDATED_CONSTRUCTION_TOKEN: Final = object()
_MODEL_SCOPE_BINDING_CONSTRUCTION_TOKEN: Final = object()


def _is_exact_int(value: object) -> bool:
    return type(value) is int


def _require_non_empty_str(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value:
        raise TypeError(f"{field_name} must be a non-empty exact str")
    return value


def _require_sha256(value: object, *, field_name: str) -> str:
    if type(value) is not str or len(value) != 64 or value != value.lower():
        raise ValueError(f"{field_name} must be a lowercase 64-hex SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a lowercase 64-hex SHA-256 digest") from exc
    return value


def _freeze_parameter(value: object, *, path: str) -> FrozenParameter:
    """Recursively copy a plan value into immutable builtin projections."""

    if value is None:
        return None
    if type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        number = value
        if not math.isfinite(number):
            raise ValueError(f"{path} contains a non-finite float")
        return number
    if type(value) is str:
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, FrozenParameter] = {}
        for raw_key, item in value.items():
            if type(raw_key) is not str:
                raise TypeError(f"{path} contains a mapping key that is not an exact str")
            key = raw_key
            if key in frozen:
                raise ValueError(f"{path} contains duplicate key {key!r}")
            frozen[key] = _freeze_parameter(item, path=f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze_parameter(item, path=f"{path}[{index}]") for index, item in enumerate(value))
    if isinstance(value, Set) and not isinstance(value, (str, bytes, bytearray)):
        try:
            return frozenset(_freeze_parameter(item, path=f"{path}{{item}}") for item in value)
        except TypeError as exc:
            raise TypeError(f"{path} contains a set item that is not hashable after freezing") from exc
    raise TypeError(f"{path} contains unsupported value type {type(value).__name__}")


def _freeze_parameter_mapping(value: object) -> Mapping[str, FrozenParameter]:
    if not isinstance(value, Mapping):
        raise TypeError("parameters must be a mapping")
    frozen = _freeze_parameter(value, path="parameters")
    if not isinstance(frozen, Mapping):  # pragma: no cover - guarded above
        raise AssertionError("parameter mapping freeze did not produce a mapping")
    return frozen


def _canonical_node(value: object) -> object:
    """Return a deterministic, type-tagged JSON projection."""

    if value is None:
        return ["null"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", value]
    if type(value) is float:
        number = value
        if not math.isfinite(number):
            raise ValueError("digest projection contains a non-finite float")
        return ["float", number]
    if type(value) is str:
        return ["str", value]
    if isinstance(value, Mapping):
        items: list[list[object]] = []
        for raw_key in sorted(value):
            if type(raw_key) is not str:
                raise TypeError("digest projection contains a non-string mapping key")
            key = raw_key
            items.append([key, _canonical_node(value[key])])
        return ["mapping", items]
    if isinstance(value, tuple):
        return ["sequence", [_canonical_node(item) for item in value]]
    if isinstance(value, frozenset):
        nodes = [_canonical_node(item) for item in value]
        nodes.sort(key=_canonical_json_bytes)
        return ["set", nodes]
    raise TypeError(f"digest projection contains unsupported type {type(value).__name__}")


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _domain_digest(prefix: bytes, projection: object) -> str:
    return hashlib.sha256(prefix + _canonical_json_bytes(projection)).hexdigest()


def _reject_duplicate_json_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON object contains duplicate key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"JSON contains forbidden non-finite constant {value}")


def _validate_json_nesting(raw: bytes, *, field_name: str) -> None:
    """Bound JSON nesting before the CPython decoder enters recursive C code.

    Brackets inside strings are data, not structure.  The escape-state machine
    also handles escaped backslashes correctly: only the byte immediately
    following an unescaped backslash is skipped.
    """

    depth = 0
    in_string = False
    escaped = False
    for byte in raw:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 0x5C:  # backslash
                escaped = True
            elif byte == 0x22:  # double quote
                in_string = False
            continue
        if byte == 0x22:
            in_string = True
        elif byte in (0x5B, 0x7B):  # [ or {
            depth += 1
            if depth > _MAX_PROOF_JSON_NESTING:
                raise ValueError(f"{field_name} exceeds maximum JSON nesting depth {_MAX_PROOF_JSON_NESTING}")
        elif byte in (0x5D, 0x7D):  # ] or }
            depth -= 1


def _load_strict_json(raw: bytes, *, field_name: str) -> object:
    if type(raw) is not bytes:
        raise TypeError(f"{field_name} must be exact bytes")
    _validate_json_nesting(raw, field_name=field_name)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{field_name} must be UTF-8 JSON") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_json_pairs,
            parse_constant=_reject_json_constant,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"{field_name} is not strict JSON") from exc


def _capture_exact_json_primitive(
    value: object,
    *,
    path: str,
    active: set[int],
) -> object:
    """Capture the exact JSON domain once, without key/string coercions."""

    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite float")
        return value
    if type(value) not in {dict, list}:
        raise TypeError(f"{path} accepts only exact dict/list/str/int/bool/null/finite-float")
    node_id = id(value)
    if node_id in active:
        raise ValueError(f"{path} contains a cycle")
    active.add(node_id)
    try:
        if type(value) is list:
            return [
                _capture_exact_json_primitive(
                    item,
                    path=f"{path}[{index}]",
                    active=active,
                )
                for index, item in enumerate(value)
            ]
        captured: dict[str, object] = {}
        checked_mapping = cast(dict[object, object], value)
        for raw_key, item in checked_mapping.items():
            if type(raw_key) is not str:
                raise TypeError(f"{path} contains a key that is not an exact str")
            captured[raw_key] = _capture_exact_json_primitive(
                item,
                path=f"{path}.{raw_key}",
                active=active,
            )
        return captured
    finally:
        active.remove(node_id)


@dataclass(frozen=True, slots=True)
class DependencyHash:
    """One schema-declared artifact dependency and its immutable identity."""

    name: str
    digest: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.name, field_name="DependencyHash.name")
        _require_sha256(self.digest, field_name="DependencyHash.digest")


@dataclass(frozen=True, slots=True)
class ScopeAssumption:
    """Frozen v1 assumption projection carried by a scope manifest."""

    key: str
    value: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.key, field_name="ScopeAssumption.key")
        _require_non_empty_str(self.value, field_name="ScopeAssumption.value")


@dataclass(frozen=True, slots=True)
class ScopeManifest:
    """Complete, immutable dependency declaration for one proof envelope."""

    scope_schema_version: int
    family: str
    ghost_policy: Literal["agnostic", "bound"]
    ghost_rect_digest: str | None
    blocked_cells_digest: str | None
    exterior_blocks_digest: str
    source_digest: str
    dependency_hashes: tuple[DependencyHash, ...]
    oracle_abstraction_version: str
    assumptions: tuple[ScopeAssumption, ...]

    def __post_init__(self) -> None:
        if not _is_exact_int(self.scope_schema_version) or self.scope_schema_version != 1:
            raise ValueError("ScopeManifest.scope_schema_version must be exact int 1")
        _require_non_empty_str(self.family, field_name="ScopeManifest.family")
        if type(self.ghost_policy) is not str or self.ghost_policy not in {"agnostic", "bound"}:
            raise ValueError("ScopeManifest.ghost_policy must be 'agnostic' or 'bound'")
        if type(self.dependency_hashes) is not tuple or not all(
            type(item) is DependencyHash for item in self.dependency_hashes
        ):
            raise TypeError("ScopeManifest.dependency_hashes must be tuple[DependencyHash, ...]")
        if type(self.assumptions) is not tuple or not all(type(item) is ScopeAssumption for item in self.assumptions):
            raise TypeError("ScopeManifest.assumptions must be tuple[ScopeAssumption, ...]")
        dependency_names = tuple(item.name for item in self.dependency_hashes)
        if dependency_names != tuple(sorted(dependency_names)):
            raise ValueError("ScopeManifest.dependency_hashes must be sorted by name")
        if len(dependency_names) != len(set(dependency_names)):
            raise ValueError("ScopeManifest.dependency_hashes contains duplicate names")
        assumption_keys = tuple(item.key for item in self.assumptions)
        if len(assumption_keys) != len(set(assumption_keys)):
            raise ValueError("ScopeManifest.assumptions contains duplicate keys")
        if self.ghost_policy == "agnostic":
            if self.ghost_rect_digest is not None or self.blocked_cells_digest is not None:
                raise ValueError("agnostic scope cannot carry ghost/blocked digests")
        else:
            _require_sha256(self.ghost_rect_digest, field_name="ScopeManifest.ghost_rect_digest")
            _require_sha256(self.blocked_cells_digest, field_name="ScopeManifest.blocked_cells_digest")
        _require_sha256(
            self.exterior_blocks_digest,
            field_name="ScopeManifest.exterior_blocks_digest",
        )
        _require_sha256(self.source_digest, field_name="ScopeManifest.source_digest")
        _require_non_empty_str(
            self.oracle_abstraction_version,
            field_name="ScopeManifest.oracle_abstraction_version",
        )


@dataclass(frozen=True, slots=True)
class CutProvenance:
    """Audit-only v1 metadata; none of these fields controls compilation."""

    family_version: str
    validator_version: str
    oracle_name: str
    oracle_cert_hash: str
    created_at: str
    iter_index: int

    def __post_init__(self) -> None:
        for field_name in (
            "family_version",
            "validator_version",
            "oracle_name",
            "created_at",
        ):
            if type(getattr(self, field_name)) is not str:
                raise TypeError(f"CutProvenance.{field_name} must be an exact str")
        if self.oracle_cert_hash:
            _require_sha256(
                self.oracle_cert_hash,
                field_name="CutProvenance.oracle_cert_hash",
            )
        elif type(self.oracle_cert_hash) is not str:
            raise TypeError("CutProvenance.oracle_cert_hash must be an exact str")
        if not _is_exact_int(self.iter_index):
            raise TypeError("CutProvenance.iter_index must be an exact int")


@dataclass(frozen=True, slots=True)
class CutEnvelope:
    """RFC-001 seven-field body-free proof envelope."""

    cut_id: str
    family: str
    family_schema_version: int
    proof_payload: bytes
    proof_hash: str
    scope: ScopeManifest
    provenance: CutProvenance

    def __post_init__(self) -> None:
        _require_non_empty_str(self.cut_id, field_name="CutEnvelope.cut_id")
        _require_non_empty_str(self.family, field_name="CutEnvelope.family")
        if not _is_exact_int(self.family_schema_version) or self.family_schema_version <= 0:
            raise ValueError("CutEnvelope.family_schema_version must be a positive exact int")
        if type(self.proof_payload) is not bytes or not self.proof_payload:
            raise TypeError("CutEnvelope.proof_payload must be non-empty exact bytes")
        proof_hash = _require_sha256(self.proof_hash, field_name="CutEnvelope.proof_hash")
        if hashlib.sha256(self.proof_payload).hexdigest() != proof_hash:
            raise ValueError("CutEnvelope.proof_hash does not match proof_payload")
        if type(self.scope) is not ScopeManifest or self.scope.family != self.family:
            raise ValueError("CutEnvelope.scope must be a ScopeManifest for the same family")
        if type(self.provenance) is not CutProvenance:
            raise TypeError("CutEnvelope.provenance must be CutProvenance")


@dataclass(frozen=True, slots=True)
class ModelScope:
    """Master-independent model scope; domain fingerprint is opaque until B3."""

    ghost_policy: Literal["agnostic", "bound"]
    ghost_rect_digest: str | None
    domain_fingerprint: str

    def __post_init__(self) -> None:
        if type(self.ghost_policy) is not str or self.ghost_policy not in {"agnostic", "bound"}:
            raise ValueError("ModelScope.ghost_policy must be 'agnostic' or 'bound'")
        if self.ghost_policy == "agnostic":
            if self.ghost_rect_digest is not None:
                raise ValueError("agnostic ModelScope cannot carry ghost_rect_digest")
        else:
            _require_sha256(self.ghost_rect_digest, field_name="ModelScope.ghost_rect_digest")
        _require_non_empty_str(
            self.domain_fingerprint,
            field_name="ModelScope.domain_fingerprint",
        )


def _validate_plan_parameters(
    operation: str,
    parameters: Mapping[str, FrozenParameter],
) -> None:
    expected_keys_by_operation = {
        "region_capacity_le": frozenset({"capacity", "group_cell_weights"}),
        "shape_packing_hall_le": frozenset({"capacity", "group_id", "region_kind"}),
        "power_pose_exclusion": frozenset({"blocked_cells_digest", "group_id", "pose_id"}),
    }
    if frozenset(parameters) != expected_keys_by_operation[operation]:
        raise ValueError(f"parameters do not match operation {operation!r} schema")
    if operation == "region_capacity_le":
        capacity = parameters["capacity"]
        weights = parameters["group_cell_weights"]
        if type(capacity) is not int or capacity < 0:
            raise ValueError("region_capacity_le capacity must be a non-negative exact int")
        if not isinstance(weights, Mapping) or not weights:
            raise ValueError("region_capacity_le group_cell_weights must be a non-empty mapping")
        for group_id, weight in weights.items():
            _require_non_empty_str(group_id, field_name="group_cell_weights key")
            if type(weight) is not int or weight <= 0:
                raise ValueError("region_capacity_le weights must be positive exact ints")
        return
    if operation == "shape_packing_hall_le":
        _require_non_empty_str(parameters["group_id"], field_name="shape_packing_hall_le group_id")
        _require_non_empty_str(
            parameters["region_kind"],
            field_name="shape_packing_hall_le region_kind",
        )
        capacity = parameters["capacity"]
        if type(capacity) is not int or capacity < 0:
            raise ValueError("shape_packing_hall_le capacity must be a non-negative exact int")
        return
    _require_non_empty_str(parameters["group_id"], field_name="power_pose_exclusion group_id")
    _require_non_empty_str(parameters["pose_id"], field_name="power_pose_exclusion pose_id")
    _require_sha256(
        parameters["blocked_cells_digest"],
        field_name="power_pose_exclusion blocked_cells_digest",
    )


def _model_scope_projection(scope: ModelScope) -> dict[str, object]:
    return {
        "domain_fingerprint": scope.domain_fingerprint,
        "ghost_policy": scope.ghost_policy,
        "ghost_rect_digest": scope.ghost_rect_digest,
        "schema_version": 1,
    }


def _model_scope_digest(scope: ModelScope) -> str:
    return _domain_digest(_MODEL_SCOPE_DIGEST_PREFIX, _model_scope_projection(scope))


@dataclass(frozen=True, slots=True, init=False)
class ConstraintPlan:
    """Deep-frozen, content-addressed typed lowering plan."""

    family: str
    schema_version: int
    semantic_fingerprint: str
    model_scope: ModelScope
    operation: ConstraintOperation
    parameters: Mapping[str, FrozenParameter]
    digest: str

    def __init__(
        self,
        *,
        family: str,
        schema_version: int,
        semantic_fingerprint: str,
        model_scope: ModelScope,
        operation: str,
        parameters: Mapping[str, object],
    ) -> None:
        checked_family = _require_non_empty_str(family, field_name="ConstraintPlan.family")
        if not _is_exact_int(schema_version) or schema_version <= 0:
            raise ValueError("ConstraintPlan.schema_version must be a positive exact int")
        checked_fingerprint = _require_sha256(
            semantic_fingerprint,
            field_name="ConstraintPlan.semantic_fingerprint",
        )
        if type(model_scope) is not ModelScope:
            raise TypeError("ConstraintPlan.model_scope must be ModelScope")
        if type(operation) is not str or operation not in SUPPORTED_OPERATIONS:
            raise ValueError(f"ConstraintPlan.operation is outside the closed set: {operation!r}")
        checked_operation = cast(ConstraintOperation, operation)
        frozen_parameters = _freeze_parameter_mapping(parameters)
        _validate_plan_parameters(checked_operation, frozen_parameters)
        projection = {
            "family": checked_family,
            "model_scope": _canonical_node(_model_scope_projection(model_scope)),
            "operation": checked_operation,
            "parameters": _canonical_node(frozen_parameters),
            "schema_version": schema_version,
            "semantic_fingerprint": checked_fingerprint,
        }
        digest = _domain_digest(_PLAN_DIGEST_PREFIX, projection)
        object.__setattr__(self, "family", checked_family)
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "semantic_fingerprint", checked_fingerprint)
        object.__setattr__(self, "model_scope", model_scope)
        object.__setattr__(self, "operation", checked_operation)
        object.__setattr__(self, "parameters", frozen_parameters)
        object.__setattr__(self, "digest", digest)


@dataclass(frozen=True, slots=True, init=False)
class CompiledCut:
    """Only the atomic typed entry may create this master-consumable result."""

    cut_id: str
    proof_digest: str
    scope_digest: str
    snapshot_digest: str
    plan: ConstraintPlan
    digest: str

    def __init__(
        self,
        *,
        cut_id: str,
        proof_digest: str,
        scope_digest: str,
        snapshot_digest: str,
        plan: ConstraintPlan,
        _construction_token: object,
    ) -> None:
        if _construction_token is not _COMPILED_CUT_CONSTRUCTION_TOKEN:
            raise TypeError("CompiledCut is private; use validate_and_compile_cut()")
        checked_cut_id = _require_non_empty_str(cut_id, field_name="CompiledCut.cut_id")
        checked_proof = _require_sha256(proof_digest, field_name="CompiledCut.proof_digest")
        checked_scope = _require_sha256(scope_digest, field_name="CompiledCut.scope_digest")
        checked_snapshot = _require_sha256(snapshot_digest, field_name="CompiledCut.snapshot_digest")
        if type(plan) is not ConstraintPlan:
            raise TypeError("CompiledCut.plan must be ConstraintPlan")
        digest = _domain_digest(
            _COMPILED_CUT_DIGEST_PREFIX,
            {
                "cut_id": checked_cut_id,
                "plan_digest": plan.digest,
                "proof_digest": checked_proof,
                "scope_digest": checked_scope,
                "snapshot_digest": checked_snapshot,
            },
        )
        object.__setattr__(self, "cut_id", checked_cut_id)
        object.__setattr__(self, "proof_digest", checked_proof)
        object.__setattr__(self, "scope_digest", checked_scope)
        object.__setattr__(self, "snapshot_digest", checked_snapshot)
        object.__setattr__(self, "plan", plan)
        object.__setattr__(self, "digest", digest)


@dataclass(frozen=True, slots=True, init=False)
class ShadowValidated:
    """Validation succeeded but the family has no typed compile authority."""

    cut_id: str
    proof_digest: str
    snapshot_digest: str
    telemetry_tag: str

    def __init__(
        self,
        *,
        cut_id: str,
        proof_digest: str,
        snapshot_digest: str,
        telemetry_tag: str,
        _construction_token: object,
    ) -> None:
        if _construction_token is not _SHADOW_VALIDATED_CONSTRUCTION_TOKEN:
            raise TypeError("ShadowValidated is private; use validate_and_compile_cut()")
        object.__setattr__(self, "cut_id", _require_non_empty_str(cut_id, field_name="ShadowValidated.cut_id"))
        object.__setattr__(
            self,
            "proof_digest",
            _require_sha256(proof_digest, field_name="ShadowValidated.proof_digest"),
        )
        object.__setattr__(
            self,
            "snapshot_digest",
            _require_sha256(snapshot_digest, field_name="ShadowValidated.snapshot_digest"),
        )
        object.__setattr__(
            self,
            "telemetry_tag",
            _require_non_empty_str(telemetry_tag, field_name="ShadowValidated.telemetry_tag"),
        )


@dataclass(frozen=True, slots=True)
class CutRejection:
    """Fail-closed result carrying the pipeline stage and audit reason."""

    stage: str
    reason: str
    cut_id: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.stage, field_name="CutRejection.stage")
        _require_non_empty_str(self.reason, field_name="CutRejection.reason")
        _require_non_empty_str(self.cut_id, field_name="CutRejection.cut_id")


class SemanticCutRejection(ValueError):
    """A proof/scope fact was well-formed but cannot be soundly admitted.

    Only this exception class is translated into :class:`CutRejection` by the
    atomic entry point.  Representation failures, plugin contract violations,
    and TCB faults deliberately propagate.
    """

    stage: str
    reason: str

    def __init__(self, stage: str, reason: str) -> None:
        self.stage = _require_non_empty_str(stage, field_name="semantic rejection stage")
        self.reason = _require_non_empty_str(reason, field_name="semantic rejection reason")
        super().__init__(self.reason)


@dataclass(frozen=True, slots=True, init=False)
class ModelScopeBinding:
    """Resolved live-master scope identity; its sole resolver lands in B5."""

    rect_idx: int | None
    ghost_rect_digest: str | None
    condition_lits: tuple[object, ...]
    blocked_cells: frozenset[tuple[int, int]] | None
    snapshot_digest: str
    master_domain_projection: str

    def __init__(
        self,
        *,
        rect_idx: int | None,
        ghost_rect_digest: str | None,
        condition_lits: tuple[object, ...],
        blocked_cells: frozenset[tuple[int, int]] | None,
        snapshot_digest: str,
        master_domain_projection: str,
        _construction_token: object,
    ) -> None:
        if _construction_token is not _MODEL_SCOPE_BINDING_CONSTRUCTION_TOKEN:
            raise TypeError("ModelScopeBinding is private; the B5 resolver is its only constructor")
        if rect_idx is not None and (type(rect_idx) is not int or rect_idx < 0):
            raise ValueError("ModelScopeBinding.rect_idx must be a non-negative exact int or None")
        if ghost_rect_digest is not None:
            _require_sha256(ghost_rect_digest, field_name="ModelScopeBinding.ghost_rect_digest")
        if type(condition_lits) is not tuple:
            raise TypeError("ModelScopeBinding.condition_lits must be tuple")
        if blocked_cells is not None and type(blocked_cells) is not frozenset:
            raise TypeError("ModelScopeBinding.blocked_cells must be frozenset or None")
        object.__setattr__(self, "rect_idx", rect_idx)
        object.__setattr__(self, "ghost_rect_digest", ghost_rect_digest)
        object.__setattr__(self, "condition_lits", condition_lits)
        object.__setattr__(self, "blocked_cells", blocked_cells)
        object.__setattr__(
            self,
            "snapshot_digest",
            _require_sha256(snapshot_digest, field_name="ModelScopeBinding.snapshot_digest"),
        )
        object.__setattr__(
            self,
            "master_domain_projection",
            _require_sha256(
                master_domain_projection,
                field_name="ModelScopeBinding.master_domain_projection",
            ),
        )


@dataclass(frozen=True, slots=True)
class FrozenFamilyProof:
    """Base identity shared by parsed, family-specific immutable proofs."""

    family: str
    schema_version: int

    def __post_init__(self) -> None:
        _require_non_empty_str(self.family, field_name="FrozenFamilyProof.family")
        if not _is_exact_int(self.schema_version) or self.schema_version <= 0:
            raise ValueError("FrozenFamilyProof.schema_version must be a positive exact int")


@dataclass(frozen=True, slots=True)
class PatternNogoodCoreAudit:
    """Frozen F5 minimization audit embedded in its proof."""

    size_before: int
    size_after: int
    calls: int
    stopped_reason: str
    is_verified_infeasible: bool


@dataclass(frozen=True, slots=True)
class PatternNogoodProof(FrozenFamilyProof):
    """Snapshot-native F5 proof projection."""

    cert_kind: str
    sub_problem_oracle_name: str
    sub_problem_oracle_version: str
    forbidden_pose_pattern: tuple[tuple[str, int, str], ...]
    core_minimization: PatternNogoodCoreAudit


@dataclass(frozen=True, slots=True)
class PatternNogoodBody:
    """Pure body projection derived from a parsed F5 proof."""

    forbidden_pose_pattern: tuple[tuple[str, int, str], ...]


class FamilyPlugin(Protocol):
    """Explicit dependency-injection seam for every typed family chain."""

    def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> FrozenFamilyProof: ...

    def derive_body(self, proof: FrozenFamilyProof) -> object: ...

    def compile(
        self,
        body: object,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> ConstraintPlan: ...

    def validate_plan(
        self,
        plan: ConstraintPlan,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> None: ...


class CapabilityStage(Enum):
    EXPERIMENTAL = "experimental"
    VALIDATED = "validated"
    COMPILABLE = "compilable"
    ENABLED = "enabled"
    RETIRED = "retired"


class ExecutionPath(Enum):
    TYPED = "TYPED"
    LEGACY_DIAGNOSTIC = "LEGACY_DIAGNOSTIC"


@dataclass(frozen=True, slots=True)
class FamilyCapability:
    """One family registry row; compiler authority is represented explicitly."""

    name: str
    mode: FamilyMode
    proof_schema_version: int
    validator_version: str
    compiler_version: str | None
    stage: CapabilityStage
    required_dependencies: frozenset[str]
    execution_path: ExecutionPath

    def __post_init__(self) -> None:
        _require_non_empty_str(self.name, field_name="FamilyCapability.name")
        if type(self.mode) is not str or self.mode not in {"literal", "geometric"}:
            raise ValueError("FamilyCapability.mode must be literal or geometric")
        if not _is_exact_int(self.proof_schema_version) or self.proof_schema_version <= 0:
            raise ValueError("FamilyCapability.proof_schema_version must be a positive exact int")
        _require_non_empty_str(
            self.validator_version,
            field_name="FamilyCapability.validator_version",
        )
        if self.compiler_version is not None:
            _require_non_empty_str(
                self.compiler_version,
                field_name="FamilyCapability.compiler_version",
            )
        if type(self.stage) is not CapabilityStage:
            raise TypeError("FamilyCapability.stage must be CapabilityStage")
        if type(self.execution_path) is not ExecutionPath:
            raise TypeError("FamilyCapability.execution_path must be ExecutionPath")
        if type(self.required_dependencies) is not frozenset:
            raise TypeError("FamilyCapability.required_dependencies must be frozenset")
        for dependency in self.required_dependencies:
            _require_non_empty_str(dependency, field_name="required dependency")


_PLUGIN_METHOD_PARAMETERS: Final = {
    "compile": ("body", "proof", "snapshot"),
    "derive_body": ("proof",),
    "parse_and_validate_proof": ("proof_payload", "snapshot"),
    "validate_plan": ("plan", "proof", "snapshot"),
}


def _validate_plugin_contract(plugin: object, *, family: str) -> FamilyPlugin:
    """Validate the runtime half of the structural FamilyPlugin contract."""

    for method_name, expected_names in _PLUGIN_METHOD_PARAMETERS.items():
        method = getattr(plugin, method_name, None)
        if not callable(method):
            raise TypeError(f"registry plugin {family!r} lacks callable {method_name}")
        if inspect.iscoroutinefunction(method):
            raise TypeError(f"registry plugin {family!r} {method_name} cannot be async")
        try:
            parameters = tuple(inspect.signature(method).parameters.values())
        except (TypeError, ValueError) as exc:
            raise TypeError(f"registry plugin {family!r} has no inspectable {method_name} signature") from exc
        if tuple(parameter.name for parameter in parameters) != expected_names:
            raise TypeError(f"registry plugin {family!r} {method_name} parameters must be {expected_names!r}")
        if any(
            parameter.kind
            not in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            }
            or parameter.default is not inspect.Parameter.empty
            for parameter in parameters
        ):
            raise TypeError(f"registry plugin {family!r} {method_name} must use required positional parameters only")
    return cast(FamilyPlugin, plugin)


@dataclass(frozen=True, slots=True, init=False)
class FamilyCapabilityRegistry:
    """Immutable registry with an explicit plugin injection seam."""

    capabilities: Mapping[str, FamilyCapability]
    plugins: Mapping[str, FamilyPlugin]

    def __init__(
        self,
        *,
        capabilities: Mapping[str, FamilyCapability],
        plugins: Mapping[str, FamilyPlugin],
    ) -> None:
        if not isinstance(capabilities, Mapping) or not isinstance(plugins, Mapping):
            raise TypeError("registry capabilities/plugins must be mappings")
        checked_capabilities: dict[str, FamilyCapability] = {}
        for raw_name, capability in capabilities.items():
            name = _require_non_empty_str(raw_name, field_name="registry capability key")
            if type(capability) is not FamilyCapability:
                raise TypeError(f"registry capability {name!r} must be FamilyCapability")
            if capability.name != name:
                raise ValueError(f"registry key {name!r} does not match capability.name")
            checked_capabilities[name] = capability
        checked_plugins: dict[str, FamilyPlugin] = {}
        for raw_name, plugin in plugins.items():
            name = _require_non_empty_str(raw_name, field_name="registry plugin key")
            if name not in checked_capabilities:
                raise ValueError(f"registry plugin {name!r} has no capability row")
            checked_plugins[name] = _validate_plugin_contract(plugin, family=name)
        for name, capability in checked_capabilities.items():
            has_plugin = name in checked_plugins
            if capability.execution_path is ExecutionPath.LEGACY_DIAGNOSTIC and has_plugin:
                raise ValueError(f"legacy diagnostic family {name!r} cannot register a typed plugin")
            if capability.execution_path is ExecutionPath.TYPED and capability.stage is CapabilityStage.VALIDATED:
                if not has_plugin:
                    raise ValueError(f"typed VALIDATED family {name!r} requires a validator plugin")
            if capability.stage in {CapabilityStage.COMPILABLE, CapabilityStage.ENABLED}:
                if capability.execution_path is not ExecutionPath.TYPED:
                    raise ValueError(f"compilable family {name!r} must use the typed execution path")
                if not has_plugin or capability.compiler_version is None:
                    raise ValueError(f"compilable family {name!r} requires plugin and compiler_version")
            elif capability.compiler_version is not None:
                raise ValueError(f"non-compilable family {name!r} cannot advertise compiler_version")
            if capability.stage is CapabilityStage.RETIRED and has_plugin:
                raise ValueError(f"retired family {name!r} cannot register a plugin")
        object.__setattr__(self, "capabilities", MappingProxyType(checked_capabilities))
        object.__setattr__(self, "plugins", MappingProxyType(checked_plugins))


_F5_STOPPED_REASONS = frozenset(
    {
        "EXCEPTION_FAIL_CLOSED",
        "INFEASIBLE_VERIFIED",
        "MAX_CALLS",
        "TIMEOUT",
    }
)


def _decode_proof_frame(
    proof_payload: bytes,
    *,
    expected_family: str,
    expected_schema_version: int,
) -> dict[str, object]:
    if type(proof_payload) is not bytes or not proof_payload.startswith(_PROOF_FRAME_PREFIX):
        raise ValueError("proof payload lacks zmd.proof.v1 domain frame")
    decoded = _load_strict_json(
        proof_payload[len(_PROOF_FRAME_PREFIX) :],
        field_name="proof frame",
    )
    if type(decoded) is not dict:
        raise ValueError("proof frame must decode to an exact object")
    frame = decoded
    if frozenset(frame) != frozenset({"family", "proof", "schema_version"}):
        raise ValueError("proof frame fields must be exactly family/proof/schema_version")
    if frame["family"] != expected_family:
        raise ValueError("proof frame family does not match capability")
    if type(frame["schema_version"]) is not int or frame["schema_version"] != expected_schema_version:
        raise ValueError("proof frame schema_version does not match capability")
    proof = frame["proof"]
    if type(proof) is not dict:
        raise ValueError("proof frame proof must be an exact object")
    return proof


def _validate_envelope_proof_frame(envelope: CutEnvelope) -> dict[str, object]:
    """Validate framing; malformed representations deliberately propagate."""

    proof = _decode_proof_frame(
        envelope.proof_payload,
        expected_family=envelope.family,
        expected_schema_version=envelope.family_schema_version,
    )
    canonical = _proof_frame(
        family=envelope.family,
        schema_version=envelope.family_schema_version,
        proof=proof,
    )
    if canonical != envelope.proof_payload:
        raise ValueError("proof frame is not in canonical encoding")
    return proof


def _parse_f5_core_audit(value: object) -> PatternNogoodCoreAudit:
    if type(value) is not dict:
        raise ValueError("F5 core_minimization must be an exact object")
    audit = value
    expected = frozenset(
        {
            "calls",
            "is_verified_infeasible",
            "size_after",
            "size_before",
            "stopped_reason",
        }
    )
    if frozenset(audit) != expected:
        raise ValueError("F5 core_minimization fields are not exact")
    for field_name in ("calls", "size_after", "size_before"):
        field_value = audit[field_name]
        if type(field_value) is not int or field_value < 0:
            raise ValueError(f"F5 core_minimization.{field_name} must be non-negative exact int")
    size_after = audit["size_after"]
    size_before = audit["size_before"]
    calls = audit["calls"]
    if type(size_after) is not int or type(size_before) is not int or type(calls) is not int:
        raise AssertionError("validated F5 audit integer lost its exact type")
    if size_after > size_before:
        raise ValueError("F5 core_minimization.size_after exceeds size_before")
    stopped_reason = audit["stopped_reason"]
    if type(stopped_reason) is not str or stopped_reason not in _F5_STOPPED_REASONS:
        raise ValueError("F5 core_minimization.stopped_reason is outside the closed set")
    if audit["is_verified_infeasible"] is not True:
        raise ValueError("F5 core_minimization must declare is_verified_infeasible=true")
    return PatternNogoodCoreAudit(
        size_before=size_before,
        size_after=size_after,
        calls=calls,
        stopped_reason=stopped_reason,
        is_verified_infeasible=True,
    )


def _parse_f5_pattern(value: object) -> tuple[tuple[str, int, str], ...]:
    if type(value) is not list or not value:
        raise ValueError("F5 forbidden_pose_pattern must be a non-empty exact list")
    pattern: list[tuple[str, int, str]] = []
    seen_triples: set[tuple[str, int, str]] = set()
    seen_slots: set[tuple[str, int]] = set()
    seen_group_poses: set[tuple[str, str]] = set()
    for index, raw_entry in enumerate(value):
        if type(raw_entry) is not list or len(raw_entry) != 3:
            raise ValueError(f"F5 forbidden_pose_pattern[{index}] must be an exact three-item list")
        raw_group, raw_slot, raw_pose = raw_entry
        group_id = _require_f5_non_empty_str(raw_group, field_name="F5 pattern group_id")
        pose_id = _require_f5_non_empty_str(raw_pose, field_name="F5 pattern pose_id")
        if type(raw_slot) is not int or raw_slot < 0:
            raise ValueError("F5 pattern slot_index must be a non-negative exact int")
        slot = raw_slot
        triple = (group_id, slot, pose_id)
        if triple in seen_triples:
            raise ValueError("F5 forbidden_pose_pattern contains a duplicate triple")
        if (group_id, slot) in seen_slots:
            raise ValueError("F5 forbidden_pose_pattern reuses an anonymous slot")
        if (group_id, pose_id) in seen_group_poses:
            raise ValueError("F5 forbidden_pose_pattern contains duplicate group/pose")
        seen_triples.add(triple)
        seen_slots.add((group_id, slot))
        seen_group_poses.add((group_id, pose_id))
        pattern.append(triple)
    frozen_pattern = tuple(pattern)
    from src.cuts.helpers.bounded_core_minimizer import canonical_relabel

    if frozen_pattern != canonical_relabel(frozen_pattern):
        raise ValueError("F5 forbidden_pose_pattern is not canonically relabelled")
    return frozen_pattern


def _require_f5_non_empty_str(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{field_name} must be a non-empty exact str")
    return value


def _parse_f5_proof(proof_payload: bytes) -> PatternNogoodProof:
    """Parse one F5 frame into its sole frozen family-proof object."""

    proof = _decode_proof_frame(
        proof_payload,
        expected_family="pattern_nogood",
        expected_schema_version=1,
    )
    expected_fields = frozenset(
        {
            "cert_kind",
            "core_minimization",
            "forbidden_pose_pattern",
            "sub_problem_oracle_name",
            "sub_problem_oracle_version",
        }
    )
    if frozenset(proof) != expected_fields:
        raise ValueError("F5 proof fields are not exact")
    if proof["cert_kind"] != "bounded_deletion_core":
        raise ValueError("F5 cert_kind must be bounded_deletion_core")
    oracle_name = _require_f5_non_empty_str(
        proof["sub_problem_oracle_name"],
        field_name="F5 sub_problem_oracle_name",
    )
    oracle_version = _require_f5_non_empty_str(
        proof["sub_problem_oracle_version"],
        field_name="F5 sub_problem_oracle_version",
    )
    core_audit = _parse_f5_core_audit(proof["core_minimization"])
    pattern = _parse_f5_pattern(proof["forbidden_pose_pattern"])
    if len(pattern) != core_audit.size_after:
        raise ValueError("F5 pattern length does not match core_minimization.size_after")
    return PatternNogoodProof(
        family="pattern_nogood",
        schema_version=1,
        cert_kind="bounded_deletion_core",
        sub_problem_oracle_name=oracle_name,
        sub_problem_oracle_version=oracle_version,
        forbidden_pose_pattern=pattern,
        core_minimization=core_audit,
    )


def _validate_f5_proof(
    proof: PatternNogoodProof,
    snapshot: ValidatedStateSnapshot,
) -> None:
    """Validate a frozen F5 proof against only snapshot-resident facts."""

    if type(proof) is not PatternNogoodProof:
        raise TypeError("F5 validator requires PatternNogoodProof")
    if type(snapshot) is not ValidatedStateSnapshot:
        raise TypeError("F5 validator requires ValidatedStateSnapshot")
    if proof.family != "pattern_nogood" or proof.schema_version != 1:
        raise SemanticCutRejection("proof", "F5 frozen proof family/schema identity is invalid")
    if proof.sub_problem_oracle_name not in snapshot.oracle_capabilities:
        raise SemanticCutRejection("proof", "F5 sub-problem oracle is unavailable in this snapshot")
    per_group_count: dict[str, int] = {}
    for group_id, slot, pose_id in proof.forbidden_pose_pattern:
        group = snapshot.groups.get(group_id)
        if type(group) is not GroupSnapshot:
            raise SemanticCutRejection("proof", f"F5 proof references unknown group {group_id!r}")
        if slot >= group.demand:
            raise SemanticCutRejection("proof", f"F5 proof slot exceeds group {group_id!r} demand")
        if pose_id not in group.pose_domain:
            raise SemanticCutRejection("proof", f"F5 proof pose {pose_id!r} is outside group domain")
        per_group_count[group_id] = per_group_count.get(group_id, 0) + 1
        if per_group_count[group_id] > group.demand:
            raise SemanticCutRejection(
                "proof",
                f"F5 proof contains more literals than group {group_id!r} demand",
            )


_F5_REVERIFY_DEADLINE_SECONDS = 15.0


def _f5_liftable_inputs(snapshot: ValidatedStateSnapshot) -> F5PatternNogoodInputs:
    inputs = snapshot.family_inputs.get("pattern_nogood")
    if type(inputs) is not F5PatternNogoodInputs:
        raise TypeError("validated snapshot lacks exact F5PatternNogoodInputs")
    return inputs


def _reverify_f5_oracle(
    proof: PatternNogoodProof,
    snapshot: ValidatedStateSnapshot,
) -> None:
    """Run the legacy-equivalent registry/version/query_liftable obligation."""

    from src.cuts.oracles.pattern_nogood_oracle import (
        LiftableScope,
        lookup_sub_problem_oracle,
    )

    adapter = lookup_sub_problem_oracle(proof.sub_problem_oracle_name)
    if adapter is None:
        raise SemanticCutRejection(
            "proof",
            f"F5 sub-problem oracle {proof.sub_problem_oracle_name!r} is not registered",
        )
    if type(adapter.version) is not str:
        raise TypeError("F5 oracle adapter.version must be an exact str")
    if adapter.version != proof.sub_problem_oracle_version:
        raise SemanticCutRejection(
            "proof",
            "F5 sub-problem oracle version differs from the frozen proof",
        )
    inputs = _f5_liftable_inputs(snapshot)
    liftable_scope = LiftableScope(
        facility_pools=inputs.facility_pools,
        canonical_rules=inputs.canonical_rules,
        instance_to_facility_type=inputs.instance_to_facility_type,
        facility_templates=inputs.facility_templates,
        group_demands=inputs.group_demands,
        group_pose_domains=inputs.group_pose_domains,
        artifact_hashes=inputs.artifact_hashes,
    )
    # The oracle is an external soundness dependency.  Its exceptions are not
    # semantic proof rejections and therefore propagate through the entry point.
    raw_result = adapter.query_liftable(
        proof.forbidden_pose_pattern,
        liftable_scope,
        deadline_seconds=_F5_REVERIFY_DEADLINE_SECONDS,
    )
    if type(raw_result) is not tuple or len(raw_result) != 2:
        raise TypeError("F5 oracle query_liftable must return an exact two-item tuple")
    verdict, witness = raw_result
    if type(verdict) is not str or verdict not in {
        "FEASIBLE",
        "INFEASIBLE",
        "TIMEOUT",
        "UNKNOWN",
    }:
        raise TypeError("F5 oracle query_liftable returned an invalid verdict")
    if witness is not None and type(witness) is not bytes:
        raise TypeError("F5 oracle query_liftable witness must be exact bytes or None")
    if verdict != "INFEASIBLE":
        raise SemanticCutRejection(
            "proof",
            f"F5 sub-problem oracle returned {verdict}, expected INFEASIBLE",
        )


class _PatternNogoodPlugin:
    """F5 typed validator with the complete legacy oracle obligation chain."""

    def parse_and_validate_proof(
        self,
        proof_payload: bytes,
        snapshot: ValidatedStateSnapshot,
    ) -> PatternNogoodProof:
        try:
            proof = _parse_f5_proof(proof_payload)
        except ValueError as exc:
            raise SemanticCutRejection("proof", str(exc) or type(exc).__name__) from exc
        _validate_f5_proof(proof, snapshot)
        _reverify_f5_oracle(proof, snapshot)
        return proof

    def derive_body(self, proof: FrozenFamilyProof) -> PatternNogoodBody:
        if type(proof) is not PatternNogoodProof:
            raise TypeError("F5 derive_body requires PatternNogoodProof")
        return PatternNogoodBody(forbidden_pose_pattern=proof.forbidden_pose_pattern)

    def compile(
        self,
        body: object,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> ConstraintPlan:
        del body, proof, snapshot
        raise TypeError("F5 is shadow-only and has no Stage-B compiler")

    def validate_plan(
        self,
        plan: ConstraintPlan,
        proof: FrozenFamilyProof,
        snapshot: ValidatedStateSnapshot,
    ) -> None:
        del plan, proof, snapshot
        raise TypeError("F5 is shadow-only and has no ConstraintPlan")


_PRODUCTION_F5_PLUGIN: Final[FamilyPlugin] = _PatternNogoodPlugin()


def build_production_registry() -> FamilyCapabilityRegistry:
    """Build the sole production B1.5 capability registry.

    F1/F6/F7 are typed but remain EXPERIMENTAL until their B2-B4 vertical
    slices install compilers.  Legacy families are diagnostic-only, and F8 is
    retained as an explicit retired metadata row.
    """

    capabilities = {
        "region_capacity": FamilyCapability(
            name="region_capacity",
            mode="geometric",
            proof_schema_version=1,
            validator_version="stage-b-pending-b2",
            compiler_version=None,
            stage=CapabilityStage.EXPERIMENTAL,
            required_dependencies=_PRODUCTION_V1_ARTIFACT_DEPENDENCIES,
            execution_path=ExecutionPath.TYPED,
        ),
        "cutset": FamilyCapability(
            name="cutset",
            mode="geometric",
            proof_schema_version=1,
            validator_version="legacy-diagnostic-v1",
            compiler_version=None,
            stage=CapabilityStage.VALIDATED,
            required_dependencies=_PRODUCTION_V1_ARTIFACT_DEPENDENCIES,
            execution_path=ExecutionPath.LEGACY_DIAGNOSTIC,
        ),
        "port_exposure": FamilyCapability(
            name="port_exposure",
            mode="literal",
            proof_schema_version=1,
            validator_version="legacy-diagnostic-v1",
            compiler_version=None,
            stage=CapabilityStage.VALIDATED,
            required_dependencies=_PRODUCTION_V1_ARTIFACT_DEPENDENCIES,
            execution_path=ExecutionPath.LEGACY_DIAGNOSTIC,
        ),
        "component_reach": FamilyCapability(
            name="component_reach",
            mode="geometric",
            proof_schema_version=1,
            validator_version="legacy-diagnostic-v1",
            compiler_version=None,
            stage=CapabilityStage.VALIDATED,
            required_dependencies=_PRODUCTION_V1_ARTIFACT_DEPENDENCIES,
            execution_path=ExecutionPath.LEGACY_DIAGNOSTIC,
        ),
        "pattern_nogood": FamilyCapability(
            name="pattern_nogood",
            mode="literal",
            proof_schema_version=1,
            validator_version="stage-b-f5-shadow-v1",
            compiler_version=None,
            stage=CapabilityStage.VALIDATED,
            required_dependencies=_PRODUCTION_V1_ARTIFACT_DEPENDENCIES,
            execution_path=ExecutionPath.TYPED,
        ),
        "shape_packing_hall": FamilyCapability(
            name="shape_packing_hall",
            mode="geometric",
            proof_schema_version=1,
            validator_version="stage-b-pending-b3",
            compiler_version=None,
            stage=CapabilityStage.EXPERIMENTAL,
            required_dependencies=_PRODUCTION_V1_ARTIFACT_DEPENDENCIES,
            execution_path=ExecutionPath.TYPED,
        ),
        "power_hitting_set": FamilyCapability(
            name="power_hitting_set",
            mode="literal",
            proof_schema_version=1,
            validator_version="stage-b-pending-b4",
            compiler_version=None,
            stage=CapabilityStage.EXPERIMENTAL,
            required_dependencies=_PRODUCTION_V1_ARTIFACT_DEPENDENCIES,
            execution_path=ExecutionPath.TYPED,
        ),
        "power_grid_reach": FamilyCapability(
            name="power_grid_reach",
            mode="geometric",
            proof_schema_version=1,
            validator_version="retired-false-premise",
            compiler_version=None,
            stage=CapabilityStage.RETIRED,
            required_dependencies=_PRODUCTION_V1_ARTIFACT_DEPENDENCIES,
            execution_path=ExecutionPath.LEGACY_DIAGNOSTIC,
        ),
        "density_envelope": FamilyCapability(
            name="density_envelope",
            mode="geometric",
            proof_schema_version=1,
            validator_version="legacy-diagnostic-v1",
            compiler_version=None,
            stage=CapabilityStage.VALIDATED,
            required_dependencies=_PRODUCTION_V1_ARTIFACT_DEPENDENCIES,
            execution_path=ExecutionPath.LEGACY_DIAGNOSTIC,
        ),
    }
    return FamilyCapabilityRegistry(
        capabilities=capabilities,
        plugins={"pattern_nogood": _PRODUCTION_F5_PLUGIN},
    )


def _reject_truncated_v1_scope_identity(kind: str, legacy_value: str) -> str:
    """Reject lifecycle's 16-hex identities when no raw preimage is carried.

    Rehashing a 64-bit legacy digest cannot turn it into a 256-bit proof
    identity.  ``CutScope`` currently carries no ghost tuple or complete cell
    set, so the schema-v1 adapter has no sound upgrade path yet.
    """

    checked_kind = _require_non_empty_str(kind, field_name="v1 scope identity kind")
    _require_non_empty_str(legacy_value, field_name=f"legacy {checked_kind} identity")
    raise ValueError(f"legacy {checked_kind} identity has no raw preimage; truncated digests cannot enter Stage-B")


def _normalize_v1_artifact_identity(name: str, value: object) -> str:
    """Lift an established v1 artifact identity into the full-digest domain.

    Exact campaigns represent an absent optional input with a stable sentinel.
    The typed proof boundary carries only full SHA-256 identities, so that one
    legacy absence state is framed and hashed rather than admitted as a fake
    digest.  Present artifacts retain their existing full digest unchanged.
    """

    checked_name = _require_non_empty_str(name, field_name="artifact dependency name")
    if type(value) is str and value == _MISSING_OPTIONAL_EXACT_ARTIFACT_HASH:
        if checked_name not in _OPTIONAL_PRODUCTION_ARTIFACTS:
            raise ValueError(f"mandatory artifact dependency {checked_name!r} cannot be absent")
        return hashlib.sha256(_MISSING_ARTIFACT_IDENTITY_PREFIX + checked_name.encode("utf-8")).hexdigest()
    return _require_sha256(value, field_name=f"artifact dependency {checked_name!r}")


def _snapshot_ghost_rect_digest(snapshot: ValidatedStateSnapshot) -> str | None:
    if snapshot.ghost is None:
        return None
    return hashlib.sha256(
        _GHOST_RECT_DIGEST_PREFIX + _canonical_json_bytes(list(snapshot.ghost.as_tuple()))
    ).hexdigest()


def _literal_body_projection(cut: object, proof: Mapping[str, object]) -> tuple[tuple[str, int, str], ...]:
    literals = getattr(cut, "literals", None)
    if type(literals) is not tuple or not literals:
        raise ValueError("literal v1 body must be a non-empty tuple")
    actual = tuple(
        (
            _require_non_empty_str(literal.slot_ref.group_id, field_name="literal group_id"),
            cast(int, literal.slot_ref.slot_index),
            _require_non_empty_str(literal.pose_id, field_name="literal pose_id"),
        )
        for literal in literals
    )
    if any(type(slot) is not int or slot < 0 for _, slot, _ in actual):
        raise ValueError("literal slot_index must be a non-negative exact int")
    family = getattr(cut, "family", None)
    expected: tuple[tuple[str, int, str], ...]
    if family == "pattern_nogood":
        raw_pattern = proof.get("forbidden_pose_pattern")
        if type(raw_pattern) is not list:
            raise ValueError("F5 proof lacks forbidden_pose_pattern body projection")
        expected_items: list[tuple[str, int, str]] = []
        for entry in cast(list[object], raw_pattern):
            if type(entry) is not list or len(entry) != 3:
                raise ValueError("F5 proof body projection is malformed")
            group, slot, pose = cast(list[object], entry)
            if type(slot) is not int:
                raise ValueError("F5 proof body slot is not an exact int")
            expected_items.append(
                (
                    _require_non_empty_str(group, field_name="F5 proof body group"),
                    slot,
                    _require_non_empty_str(pose, field_name="F5 proof body pose"),
                )
            )
        expected = tuple(expected_items)
    elif family == "port_exposure":
        blocking = proof.get("blocking_facility")
        if type(blocking) is not list or len(blocking) != 3:
            raise ValueError("F3 proof blocking_facility body projection is malformed")
        block_group, block_slot, block_pose = cast(list[object], blocking)
        if type(block_slot) is not int:
            raise ValueError("F3 proof blocking slot is not an exact int")
        expected = (
            (
                _require_non_empty_str(proof.get("facility_group"), field_name="F3 facility_group"),
                0,
                _require_non_empty_str(proof.get("facility_pose_id"), field_name="F3 facility_pose_id"),
            ),
            (
                _require_non_empty_str(block_group, field_name="F3 blocking group"),
                block_slot,
                _require_non_empty_str(block_pose, field_name="F3 blocking pose"),
            ),
        )
    elif family == "power_hitting_set":
        expected = (
            (
                _require_non_empty_str(proof.get("facility_group"), field_name="F7 facility_group"),
                0,
                _require_non_empty_str(proof.get("facility_pose_id"), field_name="F7 facility_pose_id"),
            ),
        )
    else:
        raise ValueError(f"no v1 literal body projection exists for family {family!r}")
    if sorted(actual) != sorted(expected):
        raise ValueError("v1 literal body differs from proof canonical projection")
    return tuple(sorted(actual))


def _proof_frame(*, family: str, schema_version: int, proof: Mapping[str, object]) -> bytes:
    if type(proof) is not dict:
        raise TypeError("proof projection must be an exact dict")
    captured_proof = _capture_exact_json_primitive(
        proof,
        path="proof",
        active=set(),
    )
    frame = {
        "family": family,
        "proof": captured_proof,
        "schema_version": schema_version,
    }
    return _PROOF_FRAME_PREFIX + _canonical_json_bytes(frame)


def cut_to_envelope_v1(cut: object) -> CutEnvelope:
    """Convert one schema-v1 ``Cut`` after strict body/proof equality checks."""

    # Runtime import keeps the typed platform independent of lifecycle module
    # initialization while retaining exact schema-v1 type and integrity checks.
    from src.cuts.lifecycle import Cut, validate_cert_payload, validate_cut_integrity

    if type(cut) is not Cut:
        raise TypeError("cut_to_envelope_v1 requires an exact lifecycle.Cut")
    checked_cut = cut
    schema_version = checked_cut.payload_schema_version
    if type(schema_version) is not int or schema_version != 1:
        raise ValueError("v1 payload_schema_version must be exact int 1")
    if type(checked_cut.is_quarantined) is not bool:
        raise TypeError("v1 is_quarantined must be an exact bool")
    if type(checked_cut.quarantine_reason) is not str:
        raise TypeError("v1 quarantine_reason must be an exact str")
    if checked_cut.is_quarantined or checked_cut.quarantine_reason:
        raise ValueError("quarantined cuts cannot enter the Stage-B adapter")
    integrity_error = validate_cut_integrity(checked_cut)
    if integrity_error is not None:
        raise ValueError(f"v1 cut integrity failed: {integrity_error}")
    if checked_cut.cert is None or checked_cut.scope is None:  # pragma: no cover - Cut invariant
        raise ValueError("v1 cut lacks cert or scope")
    _validate_json_nesting(
        checked_cut.cert.cert_payload,
        field_name="v1 cert payload",
    )
    if checked_cut.geometric_payload is not None:
        _validate_json_nesting(
            checked_cut.geometric_payload,
            field_name="v1 geometric body",
        )
    proof = validate_cert_payload(checked_cut.family, checked_cut.cert.cert_payload)
    if checked_cut.cert.cert_kind != proof.get("cert_kind"):
        raise ValueError("v1 cert_kind differs from proof cert_kind")
    mode = "geometric" if checked_cut.geometric_payload is not None else "literal"
    if mode == "geometric":
        if checked_cut.geometric_payload is None:  # pragma: no cover - branch guard
            raise AssertionError("geometric cut lost its body")
        body_projection = validate_cert_payload(checked_cut.family, checked_cut.geometric_payload)
        if body_projection != proof:
            raise ValueError("v1 geometric body differs from proof canonical projection")
    else:
        _literal_body_projection(checked_cut, proof)
    framed_proof = _proof_frame(
        family=checked_cut.family,
        schema_version=schema_version,
        proof=proof,
    )
    ghost_policy: Literal["agnostic", "bound"]
    ghost_rect_digest: str | None
    blocked_cells_digest: str | None
    if checked_cut.scope.ghost_rect_id == _GHOST_AGNOSTIC:
        ghost_policy = "agnostic"
        ghost_rect_digest = None
        blocked_cells_digest = None
    else:
        ghost_policy = "bound"
        ghost_rect_digest = _reject_truncated_v1_scope_identity(
            "ghost-rect",
            checked_cut.scope.ghost_rect_id,
        )
        blocked_cells_digest = _reject_truncated_v1_scope_identity(
            "blocked-cells",
            checked_cut.scope.blocked_cells_hash,
        )
    dependencies = tuple(
        DependencyHash(
            name=name,
            digest=_normalize_v1_artifact_identity(name, digest),
        )
        for name, digest in sorted(checked_cut.scope.artifact_hashes.items())
    )
    assumptions = tuple(
        ScopeAssumption(key=assumption.key, value=assumption.value)
        for assumption in checked_cut.scope.active_assumptions
    )
    scope = ScopeManifest(
        scope_schema_version=1,
        family=checked_cut.family,
        ghost_policy=ghost_policy,
        ghost_rect_digest=ghost_rect_digest,
        blocked_cells_digest=blocked_cells_digest,
        exterior_blocks_digest=_reject_truncated_v1_scope_identity(
            "exterior-blocks",
            checked_cut.scope.exterior_blocks_hash,
        ),
        source_digest=checked_cut.scope.source_digest,
        dependency_hashes=dependencies,
        oracle_abstraction_version=checked_cut.scope.oracle_abstraction_version,
        assumptions=assumptions,
    )
    provenance = CutProvenance(
        family_version=checked_cut.family_version,
        validator_version=checked_cut.validator_version,
        oracle_name=checked_cut.oracle_name,
        oracle_cert_hash=checked_cut.oracle_cert_hash,
        created_at=checked_cut.created_at,
        iter_index=checked_cut.iter_index,
    )
    return CutEnvelope(
        cut_id=checked_cut.cut_id,
        family=checked_cut.family,
        family_schema_version=schema_version,
        proof_payload=framed_proof,
        proof_hash=hashlib.sha256(framed_proof).hexdigest(),
        scope=scope,
        provenance=provenance,
    )


def _validate_scope_currentness(
    envelope: CutEnvelope,
    snapshot: ValidatedStateSnapshot,
    capability: FamilyCapability,
) -> str | None:
    scope = envelope.scope
    if scope.family != envelope.family:
        return "scope family mismatch"
    if scope.source_digest != snapshot.source_digest:
        return "scope source digest is stale"
    dependency_map = {item.name: item.digest for item in scope.dependency_hashes}
    if frozenset(dependency_map) != capability.required_dependencies:
        return "scope dependency set differs from family manifest"
    current_dependencies: dict[str, str] = {}
    for name in dependency_map:
        if name not in snapshot.artifact_hashes:
            return f"snapshot is missing artifact dependency {name!r}"
        current_dependencies[name] = _normalize_v1_artifact_identity(
            name,
            snapshot.artifact_hashes[name],
        )
    if current_dependencies != dependency_map:
        return "scope dependency digest differs from snapshot"
    if scope.oracle_abstraction_version not in snapshot.oracle_capabilities:
        return "scope oracle abstraction is unavailable"
    if scope.assumptions:
        return "typed assumption verification is not available before B5"
    if scope.exterior_blocks_digest != snapshot.exterior_blocks_digest:
        return "scope exterior-block identity is stale"
    if scope.ghost_policy == "agnostic":
        if scope.ghost_rect_digest is not None or scope.blocked_cells_digest is not None:
            return "agnostic scope carries ghost-bound identities"
        return None
    if snapshot.ghost is None:
        return "ghost-bound scope has no snapshot ghost"
    expected_ghost = _snapshot_ghost_rect_digest(snapshot)
    if scope.ghost_rect_digest != expected_ghost:
        return "scope ghost identity is stale"
    if scope.blocked_cells_digest != snapshot.blocked_cells_digest:
        return "scope blocked-cell identity is stale"
    return None


def _audit_frozen_proof_node(
    value: object,
    *,
    path: str,
    active: set[int],
) -> None:
    """Reject mutable aliases and raw proof bytes anywhere below a proof."""

    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise TypeError(f"{path} contains a non-finite float")
        return
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(f"{path} exposes raw proof bytes")
    node_id = id(value)
    if node_id in active:
        raise TypeError(f"{path} contains a cyclic proof object graph")
    if type(value) is tuple:
        active.add(node_id)
        try:
            for index, item in enumerate(cast(tuple[object, ...], value)):
                _audit_frozen_proof_node(item, path=f"{path}[{index}]", active=active)
        finally:
            active.remove(node_id)
        return
    if type(value) is frozenset:
        active.add(node_id)
        try:
            for item in cast(frozenset[object], value):
                _audit_frozen_proof_node(item, path=f"{path}{{item}}", active=active)
        finally:
            active.remove(node_id)
        return
    if is_dataclass(value) and not isinstance(value, type):
        parameters = getattr(type(value), "__dataclass_params__", None)
        if parameters is None or not parameters.frozen:
            raise TypeError(f"{path} contains a dataclass that is not frozen")
        active.add(node_id)
        try:
            for field in fields(value):
                _audit_frozen_proof_node(
                    getattr(value, field.name),
                    path=f"{path}.{field.name}",
                    active=active,
                )
        finally:
            active.remove(node_id)
        return
    raise TypeError(f"{path} contains mutable or unsupported type {type(value).__name__}")


def _validate_deep_frozen_proof(proof: object) -> None:
    if not is_dataclass(proof) or isinstance(proof, type):
        raise TypeError("family parser must return a frozen dataclass proof")
    _audit_frozen_proof_node(proof, path="proof", active=set())


def _validate_compiled_plan(
    plan: object,
    *,
    envelope: CutEnvelope,
    capability: FamilyCapability,
) -> ConstraintPlan:
    if type(plan) is not ConstraintPlan:
        raise TypeError("family compiler must return an exact ConstraintPlan")
    checked = plan
    if checked.family != envelope.family:
        raise SemanticCutRejection(
            "plan",
            "ConstraintPlan.family differs from envelope family",
        )
    if checked.schema_version != capability.proof_schema_version:
        raise SemanticCutRejection(
            "plan",
            "ConstraintPlan.schema_version differs from family capability",
        )
    if checked.model_scope.ghost_policy != envelope.scope.ghost_policy:
        raise SemanticCutRejection(
            "plan",
            "ConstraintPlan model scope ghost_policy differs from envelope scope",
        )
    if checked.model_scope.ghost_rect_digest != envelope.scope.ghost_rect_digest:
        raise SemanticCutRejection(
            "plan",
            "ConstraintPlan model scope ghost identity differs from envelope scope",
        )
    operation_by_family = {
        "power_hitting_set": "power_pose_exclusion",
        "region_capacity": "region_capacity_le",
        "shape_packing_hall": "shape_packing_hall_le",
    }
    if operation_by_family.get(envelope.family) != checked.operation:
        raise SemanticCutRejection(
            "plan",
            "ConstraintPlan.operation is invalid for envelope family",
        )
    return checked


ValidateAndCompileResult: TypeAlias = CompiledCut | ShadowValidated | CutRejection


def _semantic_rejection_result(
    rejection: SemanticCutRejection,
    *,
    cut_id: str,
) -> CutRejection:
    return CutRejection(
        stage=rejection.stage,
        reason=rejection.reason,
        cut_id=cut_id,
    )


def validate_and_compile_cut(
    envelope: CutEnvelope,
    snapshot: ValidatedStateSnapshot,
    registry: FamilyCapabilityRegistry,
) -> ValidateAndCompileResult:
    """Run RFC-001 steps 2-6 as one master-independent fail-closed function."""

    if type(envelope) is not CutEnvelope:
        raise TypeError("envelope must be an exact CutEnvelope")
    if type(snapshot) is not ValidatedStateSnapshot:
        raise TypeError("snapshot must be an exact ValidatedStateSnapshot")
    if type(registry) is not FamilyCapabilityRegistry:
        raise TypeError("registry must be an exact FamilyCapabilityRegistry")
    framed_proof = _validate_envelope_proof_frame(envelope)
    capability = registry.capabilities.get(envelope.family)
    if capability is None:
        return CutRejection(stage="registry", reason="family is absent from registry", cut_id=envelope.cut_id)
    if envelope.family_schema_version != capability.proof_schema_version:
        return CutRejection(
            stage="envelope",
            reason="proof schema version differs from capability",
            cut_id=envelope.cut_id,
        )
    scope_error = _validate_scope_currentness(envelope, snapshot, capability)
    if scope_error is not None:
        return CutRejection(stage="scope", reason=scope_error, cut_id=envelope.cut_id)
    if envelope.family == "pattern_nogood":
        framed_oracle = framed_proof.get("sub_problem_oracle_name")
        if type(framed_oracle) is str and framed_oracle != envelope.scope.oracle_abstraction_version:
            return CutRejection(
                stage="proof",
                reason="F5 proof oracle identity differs from envelope scope",
                cut_id=envelope.cut_id,
            )
    if capability.stage is CapabilityStage.RETIRED:
        return CutRejection(stage="registry", reason="family is retired", cut_id=envelope.cut_id)
    if capability.execution_path is ExecutionPath.LEGACY_DIAGNOSTIC:
        return CutRejection(
            stage="registry",
            reason="legacy diagnostic family cannot enter typed dispatch",
            cut_id=envelope.cut_id,
        )
    if capability.stage is CapabilityStage.EXPERIMENTAL:
        return CutRejection(
            stage="registry",
            reason="experimental family has no complete typed chain",
            cut_id=envelope.cut_id,
        )
    plugin = registry.plugins.get(envelope.family)
    if plugin is None:  # Registry construction forbids this state for reachable stages.
        return CutRejection(stage="registry", reason="typed plugin is unavailable", cut_id=envelope.cut_id)
    try:
        proof = plugin.parse_and_validate_proof(envelope.proof_payload, snapshot)
        if not isinstance(proof, FrozenFamilyProof):
            raise TypeError("FamilyPlugin.parse_and_validate_proof must return FrozenFamilyProof")
        if proof.family != envelope.family:
            raise TypeError("family plugin returned a proof for a different family")
        if proof.schema_version != capability.proof_schema_version:
            raise TypeError("family plugin returned a proof for a different schema version")
        _validate_deep_frozen_proof(proof)
        if type(proof) is PatternNogoodProof:
            if proof.sub_problem_oracle_name != envelope.scope.oracle_abstraction_version:
                raise SemanticCutRejection(
                    "proof",
                    "F5 proof oracle identity differs from envelope scope",
                )
    except SemanticCutRejection as rejection:
        return _semantic_rejection_result(rejection, cut_id=envelope.cut_id)
    if capability.stage is CapabilityStage.VALIDATED:
        return ShadowValidated(
            cut_id=envelope.cut_id,
            proof_digest=envelope.proof_hash,
            snapshot_digest=snapshot.digest,
            telemetry_tag=_COMMON_MODE_UNTRUSTED,
            _construction_token=_SHADOW_VALIDATED_CONSTRUCTION_TOKEN,
        )
    try:
        body = plugin.derive_body(proof)
        _audit_frozen_proof_node(body, path="body", active=set())
    except SemanticCutRejection as rejection:
        return _semantic_rejection_result(rejection, cut_id=envelope.cut_id)
    try:
        candidate_plan = plugin.compile(body, proof, snapshot)
        plan = _validate_compiled_plan(
            candidate_plan,
            envelope=envelope,
            capability=capability,
        )
    except SemanticCutRejection as rejection:
        return _semantic_rejection_result(rejection, cut_id=envelope.cut_id)
    try:
        validate_plan_runtime = cast(
            Callable[[ConstraintPlan, FrozenFamilyProof, ValidatedStateSnapshot], object],
            plugin.validate_plan,
        )
        validation_result = validate_plan_runtime(plan, proof, snapshot)
        if validation_result is not None:
            raise TypeError("FamilyPlugin.validate_plan must return None")
    except SemanticCutRejection as rejection:
        return _semantic_rejection_result(rejection, cut_id=envelope.cut_id)
    return CompiledCut(
        cut_id=envelope.cut_id,
        proof_digest=envelope.proof_hash,
        scope_digest=_model_scope_digest(plan.model_scope),
        snapshot_digest=snapshot.digest,
        plan=plan,
        _construction_token=_COMPILED_CUT_CONSTRUCTION_TOKEN,
    )


__all__ = [
    "CapabilityStage",
    "CompiledCut",
    "ConstraintPlan",
    "CutEnvelope",
    "CutProvenance",
    "CutRejection",
    "DependencyHash",
    "ExecutionPath",
    "FamilyCapability",
    "FamilyCapabilityRegistry",
    "FamilyPlugin",
    "FrozenFamilyProof",
    "ModelScope",
    "ModelScopeBinding",
    "PatternNogoodBody",
    "PatternNogoodCoreAudit",
    "PatternNogoodProof",
    "SUPPORTED_OPERATIONS",
    "ScopeAssumption",
    "ScopeManifest",
    "SemanticCutRejection",
    "ShadowValidated",
    "ValidateAndCompileResult",
    "build_production_registry",
    "cut_to_envelope_v1",
    "validate_and_compile_cut",
]
