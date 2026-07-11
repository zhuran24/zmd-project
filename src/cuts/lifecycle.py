"""Cut object schema + 9-step lifecycle (B Design v2 Phase 1.0 P1.1).

Migrated from docs/research/p3_b_design_v2_20260521/poc/b_core_lifecycle_poc.py
(PoC 14/14 PASS) with the following Phase 1 production adjustments:

1. **Active 8-family map** (2026-07-11; historical Phase 0 matrix had 9):
   F1 region_capacity / F2 cutset / F3 port_exposure / F4 component_reach /
   F5 pattern_nogood / F6 shape_packing_hall / F7 power_hitting_set /
   F9 density_envelope. F8 power_grid_reach was retired and deleted on
   2026-07-08 after its game-rule premise was disproved.
2. **CutScope.exterior_blocks_hash** added (cut_lifecycle_v2 v3.2.2,
   Gemini round 21 fix). Step 3 (attach-scope) dispatches by GHOST_AGNOSTIC:
   - GHOST_AGNOSTIC cut: verify ``exterior_blocks_hash`` only (cut可跨 ghost 复用)
   - ghost-bound cut: verify full ``blocked_cells_hash`` (含 ghost ∪ exterior)
3. **Step 2 / Step 8 boundary**: the generic ``step_2_minimize`` entry remains
   fail-closed while F5 uses its family-specific deletion minimizer. Step 8 has
   controlled translators for F1/F5/F6/F7; F2/F3/F4/F9 remain fail-closed and
   the bridge is still default-off / certified-unsafe pending promotion.

PROJECT_LOCK §2B Cut Object Boundary 之 source-of-truth (schema).

Refs:
- docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md v3.2.2 (9-step lifecycle)
- docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md v1.2
- docs/research/p3_b_design_v2_20260521/state_machine_v2.md §2 (BState)
- docs/research/p3_b_design_v2_20260521/poc/b_core_lifecycle_poc.py (源 PoC)
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from collections import Counter  # noqa: F401  (state_machine_v2 后续用)
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)

from src.cuts.cert_schema import validate_cert_payload as _validate_cert_payload

if TYPE_CHECKING:
    from src.cuts.typed_platform import CompiledCut, ModelScopeBinding


# ============================================================================
# Identifier types (cut_lifecycle_v2 v3.2.2 §3)
# ============================================================================

CutId = str
GroupId = str
# Gap 10 (Gemini round 30): PoseId = str (vs PoC int). Source: candidate_placements
# pose_id e.g. "viewer::boundary_required_output_blue_iron_ore_019". CutLiteral.pose_id
# 直接 carry named pose string — anonymization 是 slot 级 (AnonymousSlotRef.slot_index
# 仍 int + anonymous, group 内 slot 可置换). pose 级是几何身份, 不 anonymize.
PoseId = str
Cell = Tuple[int, int]
GhostRectId = str
Hash = str
SourceDigestStr = str
JsonDict = Dict[str, Any]

GHOST_AGNOSTIC: GhostRectId = "__ghost_agnostic__"


def validate_cert_payload(family: str, raw_bytes: bytes) -> JsonDict:
    """Strict schema envelope check for proof-bearing cut cert payload bytes."""

    return _validate_cert_payload(family, raw_bytes)


CutFamily = Literal[
    "region_capacity",  # F1 (geometric)
    "cutset",  # F2 (geometric)
    "port_exposure",  # F3 (literal)
    "component_reach",  # F4 (geometric)
    "pattern_nogood",  # F5 (literal)
    "shape_packing_hall",  # F6 (geometric)
    "power_hitting_set",  # F7 (literal)
    "density_envelope",  # F9 (geometric)
]
# F8 power_grid_reach was deleted 2026-07-08: retired on a false game-rule
# premise (poles need no pole-to-pole network; the protocol core links to
# every placed pole automatically). See card p1-3-m2-coverage-stencil-ruling.

# Family ↔ mode mapping enforces XOR (literal-based vs geometric-based).
# PROJECT_LOCK §3A invariant 3 (family↔mode 不可改).
_FAMILY_MODE_MAP: Dict[str, Literal["literal", "geometric"]] = {
    "region_capacity": "geometric",
    "cutset": "geometric",
    "port_exposure": "literal",
    "component_reach": "geometric",
    "pattern_nogood": "literal",
    "shape_packing_hall": "geometric",
    "power_hitting_set": "literal",
    "density_envelope": "geometric",
}


SOURCE_DIGEST_SCHEMA_VERSION = 2
SOURCE_DIGEST_FIELD_NAMES: Tuple[str, ...] = (
    "canonical_rules",
    "candidate_placements",
    "mandatory_exact_instances",
    "facility_templates",
    "generic_io_requirements",
    "commodity_routes",
    "groups_static",
)

# Runtime-only caches are allowed only at explicitly enumerated source paths.
# Do not treat every ``__*`` key as non-authoritative: schema-valid facility
# template / facility pool identifiers may legally begin with underscores.
SOURCE_DIGEST_RUNTIME_CACHE_KEYS_BY_PATH: Dict[Tuple[str, ...], FrozenSet[str]] = {
    ("candidate_placements",): frozenset(
        {
            "__pose_id_cache__",
            "__pose_id_cache_digest__",
        }
    ),
}

STEP_7_EVALUATION_GUARD_OBLIGATIONS: Tuple[str, ...] = (
    "source_digest",
    "ghost_or_exterior_scope",
    "artifact_hashes",
    "oracle_abstraction_version",
    "active_assumptions",
)


def _is_strict_int(value: object) -> bool:
    """Runtime schema guard: bool/float/string must not pass as an int."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_non_empty_str(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _strict_b64decode(value: object, field_name: str) -> bytes:
    """Decode a required base64 field, rejecting junk characters.

    ``base64.b64decode`` is permissive unless ``validate=True`` is set: it can
    silently ignore non-base64 bytes. Cut JSON is an audit artifact, so accepting
    non-canonical payload text makes tampering harder to spot even when the
    decoded bytes happen to stay unchanged.
    """
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field_name} must be a non-empty base64 string")
    try:
        return base64.b64decode(value, validate=True)
    except Exception as e:
        raise ValueError(f"{field_name} invalid base64: {e}") from e


# ============================================================================
# Cut object schema (cut_lifecycle_v2 v3.2.2 §3)
# ============================================================================


@dataclass(frozen=True)
class AnonymousSlotRef:
    """state_machine_v2 §2 — group/slot 引用消 10^134 label symmetry."""

    group_id: GroupId
    slot_index: int


@dataclass(frozen=True)
class CutLiteral:
    slot_ref: AnonymousSlotRef
    pose_id: PoseId


@dataclass(frozen=True)
class Assumption:
    key: str
    value: str


@dataclass(frozen=True, slots=True)
class ScopeIdentityPreimageV1:
    """Canonical raw preimage for legacy and Stage-B scope identities."""

    ghost_rect: Optional[Tuple[int, int, int, int]]
    blocked_cells: Tuple[Cell, ...]
    exterior_blocks: Tuple[Cell, ...]

    def __post_init__(self) -> None:
        _validate_scope_identity_preimage_v1(self)


def _validate_scope_identity_preimage_v1(
    preimage: ScopeIdentityPreimageV1,
) -> None:
    ghost_rect = preimage.ghost_rect
    if ghost_rect is not None:
        if type(ghost_rect) is not tuple or len(ghost_rect) != 4:
            raise ValueError("identity_preimage.ghost_rect must be an exact four-item tuple or None")
        if not all(_is_strict_int(value) for value in ghost_rect):
            raise ValueError("identity_preimage.ghost_rect values must be strict integers")
        x, y, width, height = ghost_rect
        if x < 0 or y < 0:
            raise ValueError("identity_preimage.ghost_rect x/y must be non-negative")
        if width <= 0 or height <= 0:
            raise ValueError("identity_preimage.ghost_rect width/height must be positive")

    for field_name, cells in (
        ("blocked_cells", preimage.blocked_cells),
        ("exterior_blocks", preimage.exterior_blocks),
    ):
        if type(cells) is not tuple:
            raise ValueError(f"identity_preimage.{field_name} must be an exact tuple")
        for cell in cells:
            if type(cell) is not tuple or len(cell) != 2:
                raise ValueError(f"identity_preimage.{field_name} must contain exact two-item tuples")
            if not all(_is_strict_int(coordinate) for coordinate in cell):
                raise ValueError(f"identity_preimage.{field_name} coordinates must be strict integers")
        if tuple(sorted(cells)) != cells or len(set(cells)) != len(cells):
            raise ValueError(f"identity_preimage.{field_name} must be lexicographically sorted and unique")

    if not set(preimage.exterior_blocks).issubset(preimage.blocked_cells):
        raise ValueError("identity_preimage.exterior_blocks must be a subset of blocked_cells")
    # Defensive fail-closed (B2 dual-review opus#1): unreachable on the certified
    # F1 generation path — there ghost_cells are exactly the cells of ghost_rect,
    # so ghost_rect=None implies ghost_cells=∅ and blocked == exterior. The guard
    # only fires on a degenerate caller-supplied state and errs toward rejection.
    if ghost_rect is None and preimage.blocked_cells != preimage.exterior_blocks:
        raise ValueError("identity_preimage cannot contain ghost cells when ghost_rect is None")


@dataclass(frozen=True)
class CutScope:
    """v3.2.2: ``exterior_blocks_hash`` 新加 (Gemini round 21).

    Step 3 (attach-scope verify) dispatch:
    - GHOST_AGNOSTIC cut: verify ``exterior_blocks_hash`` only
    - ghost-bound cut: verify full ``blocked_cells_hash``
    """

    ghost_rect_id: GhostRectId
    blocked_cells_hash: Hash
    exterior_blocks_hash: Hash  # v3.2.2 新加
    source_digest: SourceDigestStr
    artifact_hashes: Dict[str, Hash] = field(default_factory=dict)
    oracle_abstraction_version: str = ""
    active_assumptions: Tuple[Assumption, ...] = ()
    identity_preimage: Optional[ScopeIdentityPreimageV1] = None

    def __post_init__(self) -> None:
        # Scope data is proof-bearing evidence captured at cut generation time.
        # Callers commonly pass ``state.artifact_hashes``; keep a private snapshot
        # so later BState mutations cannot silently rewrite the cut's replay scope.
        object.__setattr__(self, "artifact_hashes", dict(self.artifact_hashes))


@dataclass(frozen=True)
class OracleCert:
    cert_kind: str
    cert_payload: bytes
    cert_hash: Hash


@dataclass(frozen=True)
class Cut:
    cut_id: CutId
    family: CutFamily
    literals: Optional[Tuple[CutLiteral, ...]] = None
    geometric_payload: Optional[bytes] = None
    scope: Optional[CutScope] = None
    cert: Optional[OracleCert] = None
    family_version: str = ""
    validator_version: str = ""
    payload_schema_version: int = 1
    oracle_name: str = ""
    oracle_cert_hash: Hash = ""
    minimization_audit: Dict[str, int] = field(default_factory=dict)
    created_at: str = ""
    iter_index: int = -1
    is_quarantined: bool = False
    quarantine_reason: str = ""

    def __post_init__(self) -> None:
        has_lit = _has_literal_payload(self.literals)
        has_geo = self.geometric_payload is not None
        _validate_cut_mode(self.cut_id, self.family, has_lit, has_geo)
        scope = _require_scope(self.scope, self.cut_id)
        cert = _require_cert(self.cert, self.cut_id)
        _validate_cut_scalar_schema(self, cert)
        _validate_scope_schema(self.cut_id, scope)
        _validate_literal_schema(self.cut_id, self.literals)


def _has_literal_payload(literals: object) -> bool:
    if literals is None:
        return False
    if not isinstance(literals, tuple):
        # Treat malformed non-None literals as present so the XOR branch remains
        # deterministic; the concrete type error is raised by schema validation.
        return True
    return len(literals) > 0


def _validate_cut_mode(cut_id: object, family: object, has_lit: bool, has_geo: bool) -> None:
    if has_lit == has_geo:
        raise ValueError(
            f"Cut {cut_id}: literals XOR geometric_payload 必须互斥; "
            f"literals={'set' if has_lit else 'empty/None'}, "
            f"geometric_payload={'set' if has_geo else 'None'}"
        )
    if not isinstance(family, str):
        raise ValueError(f"Cut {cut_id}: family 必须是 str")
    mode = _FAMILY_MODE_MAP.get(family)
    if mode is None:
        raise ValueError(f"Cut {cut_id}: family={family} 不在 active F1-F7+F9 registry")
    if mode == "literal" and not has_lit:
        raise ValueError(f"family={family} 要求 literal-based")
    if mode == "geometric" and not has_geo:
        raise ValueError(f"family={family} 要求 geometric")


def _require_scope(scope: object, cut_id: object) -> CutScope:
    if not isinstance(scope, CutScope):
        raise ValueError(f"Cut {cut_id}: scope 必填且必须是 CutScope (cut_lifecycle_v2 §3)")
    return scope


def _require_cert(cert: object, cut_id: object) -> OracleCert:
    if not isinstance(cert, OracleCert):
        raise ValueError(f"Cut {cut_id}: cert 必填且必须是 OracleCert (cut_lifecycle_v2 §3)")
    return cert


def _validate_cut_scalar_schema(cut: Cut, cert: OracleCert) -> None:
    _validate_cut_identity_and_payload(cut)
    _validate_cert_schema(cut.cut_id, cert)
    _validate_cut_metadata_schema(cut)
    _validate_cut_status_schema(cut)


def _validate_cut_identity_and_payload(cut: Cut) -> None:
    if not _is_non_empty_str(cut.cut_id):
        raise ValueError("cut_id 必须是非空 str")
    if cut.literals is not None and not isinstance(cut.literals, tuple):
        raise ValueError(f"Cut {cut.cut_id}: literals 必须是 tuple 或 None")
    if cut.geometric_payload is not None and not isinstance(cut.geometric_payload, bytes):
        raise ValueError(f"Cut {cut.cut_id}: geometric_payload 必须是 bytes")


def _validate_cert_schema(cut_id: CutId, cert: OracleCert) -> None:
    if not _is_non_empty_str(cert.cert_kind):
        raise ValueError(f"Cut {cut_id}: cert_kind 必须是非空 str")
    if not isinstance(cert.cert_payload, bytes):
        raise ValueError(f"Cut {cut_id}: cert_payload 必须是 bytes")
    if not _is_non_empty_str(cert.cert_hash):
        raise ValueError(f"Cut {cut_id}: cert_hash 必须是非空 str")


def _validate_cut_metadata_schema(cut: Cut) -> None:
    string_fields = (
        ("family_version", cut.family_version),
        ("validator_version", cut.validator_version),
        ("oracle_name", cut.oracle_name),
        ("oracle_cert_hash", cut.oracle_cert_hash),
        ("created_at", cut.created_at),
    )
    for field_name, value in string_fields:
        if not isinstance(value, str):
            raise ValueError(f"Cut {cut.cut_id}: {field_name} 必须是 str")
    if not _is_strict_int(cut.payload_schema_version) or cut.payload_schema_version < 1:
        raise ValueError(f"Cut {cut.cut_id}: payload_schema_version 必须是正 int")
    if not _is_strict_int(cut.iter_index):
        raise ValueError(f"Cut {cut.cut_id}: iter_index 必须是 int")


def _validate_cut_status_schema(cut: Cut) -> None:
    if not isinstance(cut.is_quarantined, bool):
        raise ValueError(f"Cut {cut.cut_id}: is_quarantined 必须是 bool")
    if not isinstance(cut.quarantine_reason, str):
        raise ValueError(f"Cut {cut.cut_id}: quarantine_reason 必须是 str")
    if not isinstance(cut.minimization_audit, dict) or not all(
        isinstance(k, str) and _is_strict_int(v) for k, v in cut.minimization_audit.items()
    ):
        raise ValueError(f"Cut {cut.cut_id}: minimization_audit 必须是 dict[str, int]")


def _validate_scope_schema(cut_id: CutId, scope: CutScope) -> None:
    for field_name, value in (
        ("ghost_rect_id", scope.ghost_rect_id),
        ("blocked_cells_hash", scope.blocked_cells_hash),
        ("exterior_blocks_hash", scope.exterior_blocks_hash),
        ("source_digest", scope.source_digest),
    ):
        if not _is_non_empty_str(value):
            raise ValueError(f"Cut {cut_id}: scope.{field_name} 必须是非空 str")
    if not isinstance(scope.artifact_hashes, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in scope.artifact_hashes.items()
    ):
        raise ValueError(f"Cut {cut_id}: scope.artifact_hashes 必须是 dict[str, str]")
    if not isinstance(scope.oracle_abstraction_version, str):
        raise ValueError(f"Cut {cut_id}: scope.oracle_abstraction_version 必须是 str")
    if not isinstance(scope.active_assumptions, tuple):
        raise ValueError(f"Cut {cut_id}: scope.active_assumptions 必须是 tuple[Assumption, ...]")
    for assumption in scope.active_assumptions:
        if not isinstance(assumption, Assumption):
            raise ValueError(f"Cut {cut_id}: active_assumptions 必须只含 Assumption")
        if not _is_non_empty_str(assumption.key) or not isinstance(assumption.value, str):
            raise ValueError(f"Cut {cut_id}: assumption key/value schema invalid")
    if scope.identity_preimage is not None and type(scope.identity_preimage) is not ScopeIdentityPreimageV1:
        raise ValueError(f"Cut {cut_id}: scope.identity_preimage 必须是 ScopeIdentityPreimageV1 或 None")


def _validate_literal_schema(cut_id: CutId, literals: Optional[Tuple[CutLiteral, ...]]) -> None:
    for lit in literals or ():
        if not isinstance(lit, CutLiteral) or not isinstance(lit.slot_ref, AnonymousSlotRef):
            raise ValueError(f"Cut {cut_id}: literal 必须是 CutLiteral")
        if not _is_non_empty_str(lit.slot_ref.group_id):
            raise ValueError(f"Cut {cut_id}: literal group_id 必须是非空 str")
        if not _is_strict_int(lit.slot_ref.slot_index) or lit.slot_ref.slot_index < 0:
            raise ValueError(f"Cut {cut_id}: literal slot_index 必须是非负 int")
        if not _is_non_empty_str(lit.pose_id):
            raise ValueError(f"Cut {cut_id}: literal pose_id 必须是非空 str")


AttachDecision = Literal["ATTACH", "HOLD", "QUARANTINE"]


@dataclass(frozen=True)
class ValidationResult:
    kind: Literal["ok", "unsound", "timeout", "schema_err"]
    elapsed_seconds: float
    detail: Optional[str] = None


# ============================================================================
# BState mini (state_machine_v2 §2 — Phase 1.0 framework scope)
# ============================================================================


@dataclass
class GroupState:
    """state_machine_v2.md §2 contract.

    Gap 12 修 (round 31): selected_poses **必须** List[PoseId] (just pose_id,
    group_id 已在 GroupState.group_id field). 旧版 PoC 写 List[Tuple[GroupId,
    PoseId]] 跟 spec 撕裂. multiset eval 同步修.
    """

    group_id: GroupId
    demand: int
    pose_domain: FrozenSet[PoseId]
    selected_poses: List[PoseId] = field(default_factory=list)

    @property
    def remaining_count(self) -> int:
        return self.demand - len(self.selected_poses)


@dataclass
class BState:
    """Phase 1.0 framework 简化版 — F1 region_capacity 所需 field.

    Phase 1.1+ 各 family 扩 field (e.g., F8 power_network adj list).

    ``canonical_rules`` 新加 (Gemini round 27 B1 finding): parsed canonical_rules
    readonly 引用, 让 ASSUMPTION_VERIFIERS 能真实施 source-of-truth 比对.
    None 表示未 inject; verifier fail-closed 返 False.
    """

    groups: Dict[GroupId, GroupState]
    cell_owner: Dict[Cell, Tuple[GroupId, int]] = field(default_factory=dict)
    ghost_rect: Optional[Tuple[int, int, int, int]] = None  # (x, y, x_span, y_span)
    ghost_cells: FrozenSet[Cell] = frozenset()
    exterior_blocks: FrozenSet[Cell] = frozenset()
    artifact_hashes: Dict[str, Hash] = field(default_factory=dict)
    available_oracle_versions: FrozenSet[str] = frozenset()
    canonical_rules: Optional[JsonDict] = None  # parsed rules/canonical_rules.json
    # Gap 8 (Gemini round 30): operation_type (group_id) → facility_type 映射.
    # Source: mandatory_exact_instances.json. canonical_rules 本身只 facility_template
    # 层有 placement_rule / port_rule 等 — 必须先经此映射才能 lookup. e.g.
    # instance_to_facility_type["boundary_io"] = "boundary_storage_port".
    instance_to_facility_type: Optional[Dict[GroupId, str]] = None
    # facility_templates 直接 ref canonical_rules.facility_templates (alias for
    # fast lookup). e.g. facility_templates["boundary_storage_port"]["dimensions"]
    # = {"w": 1, "h": 3}. helpers/canonical_rules.py 用此字段算 cells_per_pose 等.
    facility_templates: Optional[Dict[str, JsonDict]] = None
    # Gap 9 (Gemini round 30): parsed candidate_placements.json. Pose-level
    # 端口数据 (input_port_cells / output_port_cells) 不在 canonical_rules
    # (template) 层, 在 candidate_placements (pose) 层. F3 / F8 validator 必读此.
    # Structure: {"facility_pools": {ft: [pose, pose, ...]}}
    # 每 pose 含 pose_id (str) + anchor + occupied_cells + input/output_port_cells.
    candidate_placements: Optional[JsonDict] = None
    # GPT pro v4 P0 fix: F2 cutset / F4 component_reach 必须能 verify cert 的
    # commodity_demand / commodity_id 跟真实 commodity registry 一致. Phase 1.5+
    # production inject 这两个 field; Phase 1.1 默认 None → F2/F4 validator
    # fail-closed (不允外部 cut 伪造 commodity).
    # commodity_demands schema: {commodity_id: int} (cross-partition demand sum).
    commodity_demands: Optional[Dict[str, int]] = None
    # commodity_routes schema: {commodity_id: {"src": (x,y), "sink": (x,y)}}
    commodity_routes: Optional[Dict[str, JsonDict]] = None
    source_digest: Optional[SourceDigestStr] = None


# ============================================================================
# Helper functions (cut_lifecycle_v2 v3.2.2 §4)
# ============================================================================


def _capture_scope_cells(value: object, *, field_name: str) -> Tuple[Cell, ...]:
    if not isinstance(value, (set, frozenset)):
        raise ValueError(f"state.{field_name} must be a set of cells")
    captured: List[Cell] = []
    for raw_cell in value:
        if type(raw_cell) is not tuple or len(raw_cell) != 2:
            raise ValueError(f"state.{field_name} must contain exact two-item tuples")
        x, y = raw_cell
        if not _is_strict_int(x) or not _is_strict_int(y):
            raise ValueError(f"state.{field_name} coordinates must be strict integers")
        captured.append((x, y))
    if len(set(captured)) != len(captured):
        raise ValueError(f"state.{field_name} contains duplicate cells")
    return tuple(sorted(captured))


def capture_scope_identity_inputs_v1(
    state: BState,
) -> Tuple[ScopeIdentityPreimageV1, Tuple[Cell, ...]]:
    """Capture raw scope inputs once; retain ghost cells for oracle policy."""

    # Read every live reference before traversing any container.  The oracle
    # consumes only the returned immutable values for both policy selection and
    # identities, so a side-effecting source cannot create a hybrid CutScope.
    raw_ghost_rect = state.ghost_rect
    raw_ghost_cells = state.ghost_cells
    raw_exterior_blocks = state.exterior_blocks

    if raw_ghost_rect is None:
        ghost_rect = None
    else:
        if type(raw_ghost_rect) is not tuple or len(raw_ghost_rect) != 4:
            raise ValueError("state.ghost_rect must be an exact four-item tuple or None")
        if not all(_is_strict_int(value) for value in raw_ghost_rect):
            raise ValueError("state.ghost_rect values must be strict integers")
        ghost_rect = raw_ghost_rect

    ghost_cells = _capture_scope_cells(
        raw_ghost_cells,
        field_name="ghost_cells",
    )
    exterior_blocks = _capture_scope_cells(
        raw_exterior_blocks,
        field_name="exterior_blocks",
    )
    blocked_cells = tuple(sorted(set(ghost_cells).union(exterior_blocks)))
    preimage = ScopeIdentityPreimageV1(
        ghost_rect=ghost_rect,
        blocked_cells=blocked_cells,
        exterior_blocks=exterior_blocks,
    )
    return preimage, ghost_cells


def capture_scope_identity_preimage_v1(state: BState) -> ScopeIdentityPreimageV1:
    """Capture all raw scope identity inputs once into their canonical carrier."""

    preimage, _ghost_cells = capture_scope_identity_inputs_v1(state)
    return preimage


def _compute_legacy_cells_hash(cells: Iterable[Cell]) -> Hash:
    blob = ";".join(f"{x},{y}" for x, y in cells).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def compute_scope_identity_legacy_hashes(
    preimage: ScopeIdentityPreimageV1,
) -> Tuple[GhostRectId, Hash, Hash]:
    """Recompute the three historical scope identities from frozen raw data."""

    if type(preimage) is not ScopeIdentityPreimageV1:
        raise ValueError("preimage must be an exact ScopeIdentityPreimageV1")
    _validate_scope_identity_preimage_v1(preimage)
    return (
        compute_ghost_rect_id(preimage.ghost_rect),
        _compute_legacy_cells_hash(preimage.blocked_cells),
        _compute_legacy_cells_hash(preimage.exterior_blocks),
    )


def compute_ghost_rect_id(rect: Optional[Tuple[int, int, int, int]]) -> GhostRectId:
    if rect is None:
        return GHOST_AGNOSTIC
    blob = f"{rect[0]},{rect[1]},{rect[2]},{rect[3]}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def compute_blocked_cells_hash(state: BState) -> Hash:
    """blocked_cells = ghost ∪ exterior (跨层 sound — 不含 cell_owner)."""
    blocked = sorted(state.ghost_cells | state.exterior_blocks)
    return _compute_legacy_cells_hash(blocked)


def compute_exterior_blocks_hash(state: BState) -> Hash:
    """v3.2.2 新: 仅 exterior_blocks (排除 ghost_cells), GHOST_AGNOSTIC 路径用."""
    blocked = sorted(state.exterior_blocks)
    return _compute_legacy_cells_hash(blocked)


def _is_source_digest_runtime_cache_key(path: Tuple[str, ...], key: str) -> bool:
    return key in SOURCE_DIGEST_RUNTIME_CACHE_KEYS_BY_PATH.get(path, frozenset())


def _source_jsonable(value: Any, path: Tuple[str, ...] = ()) -> Any:
    """Normalize source payloads before hashing; ignore only declared runtime caches."""
    if isinstance(value, dict):
        normalized: Dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_source_digest_runtime_cache_key(path, key_text):
                continue
            normalized[key_text] = _source_jsonable(item, (*path, key_text))
        return normalized
    if isinstance(value, (list, tuple)):
        return [_source_jsonable(item, path) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_source_jsonable(item, path) for item in value), key=repr)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _group_static_source_payload(state: BState) -> JsonDict:
    """Static per-group source fields that validators certify against.

    ``selected_poses`` is deliberately excluded: it is the mutable incumbent
    assignment that Step 7 evaluates.  ``demand`` and ``pose_domain`` are
    canonical problem inputs used by F1/F2/F3/F5/F6/F7/F9 validators/generators,
    so they must participate in replay scope.
    """
    return {
        gid: {
            "demand": group.demand,
            "pose_domain": sorted(group.pose_domain),
        }
        for gid, group in sorted(state.groups.items())
    }


def source_digest_payload(state: BState) -> JsonDict:
    """Return the canonical source payload covered by ``compute_source_digest``."""
    source_fields: JsonDict = {
        "canonical_rules": state.canonical_rules or {},
        "candidate_placements": state.candidate_placements or {},
        "mandatory_exact_instances": state.instance_to_facility_type or {},
        "facility_templates": state.facility_templates or {},
        "generic_io_requirements": state.commodity_demands or {},
        "commodity_routes": state.commodity_routes or {},
        "groups_static": _group_static_source_payload(state),
    }
    if tuple(source_fields) != SOURCE_DIGEST_FIELD_NAMES:
        raise RuntimeError(
            "source digest payload fields drifted from SOURCE_DIGEST_FIELD_NAMES: "
            f"payload={tuple(source_fields)!r}, contract={SOURCE_DIGEST_FIELD_NAMES!r}"
        )
    return {"schema_version": SOURCE_DIGEST_SCHEMA_VERSION, **source_fields}


def compute_source_digest(state: BState) -> SourceDigestStr:
    """Return stable content digest for cross-session cut replay scope.

    ``BState.source_digest`` is treated as an optional caller-side note/cache,
    not as authority. Step 6 must be tied to the actual source payloads injected
    into BState; otherwise a stale or hand-written digest can mask data changes.
    """
    parts = source_digest_payload(state)
    blob = json.dumps(
        _source_jsonable(parts),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def canonical_bytes_for_cert(payload: JsonDict) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")


def validate_cut_integrity(cut: Cut) -> Optional[str]:
    """Return None when cut payload/hash bookkeeping is internally consistent.

    Family validators prove mathematical soundness. This guard catches a lower
    level failure mode first: cert payload edited without updating hash, or a
    geometric cut whose body and cert payload drift apart.
    """
    if cut.cert is None:
        return "cut.cert is None"
    expected_hash = _sha256_hex(cut.cert.cert_payload)
    if cut.cert.cert_hash != expected_hash:
        return f"cert_hash mismatch: cert={cut.cert.cert_hash!r}, expected={expected_hash!r}"
    if cut.oracle_cert_hash and cut.oracle_cert_hash != cut.cert.cert_hash:
        return f"oracle_cert_hash mismatch: oracle={cut.oracle_cert_hash!r}, cert={cut.cert.cert_hash!r}"
    if cut.geometric_payload is not None and cut.geometric_payload != cut.cert.cert_payload:
        return "geometric_payload differs from cert.cert_payload"
    return None


# ============================================================================
# Family 1 region_capacity cert schema + reference generator (v1.2 §6-§7)
# ============================================================================
#
# Phase 1.0 P1.1 carries the PoC F1 generator as **framework reference** for
# the 9-step pipeline. P1.5 (Phase 1.1) re-implements full F1 generator with
# interior_rect + ghost_complement region kinds + Farkas certificate (cand C
# 复用), then this stub is replaced by ``src/cuts/families/region_capacity.py``.


@dataclass(frozen=True)
class RegionCapacityCert:
    region_kind: str  # "left_baseline" | "bottom_baseline" | "interior_rect" | "ghost_complement"
    region_cells_bitset_b64: str
    cap_R: int
    demand_R: int
    gap: int
    contributing_groups: Tuple[Tuple[GroupId, int], ...]
    cells_per_pose: Dict[GroupId, int]  # v1.1 — Gemini round 14 finding #5
    lp_dual_ray_b64: Optional[str] = None
    lp_dual_objective: Optional[float] = None


def _encode_region_bitset(cells: List[Cell], grid_size: int = 70) -> str:
    arr = bytearray(grid_size * grid_size // 8 + 1)
    for x, y in cells:
        idx = x * grid_size + y
        arr[idx // 8] |= 1 << (idx % 8)
    return base64.b64encode(bytes(arr)).decode("ascii")


def _decode_region_bitset(b64: str, grid_size: int = 70) -> FrozenSet[Cell]:
    arr = _strict_b64decode(b64, "region_bitset_b64")
    expected_len = (grid_size * grid_size + 7) // 8
    if len(arr) != expected_len:
        raise ValueError(f"region_bitset length mismatch: got {len(arr)}, expected {expected_len}")
    extra_bits = expected_len * 8 - grid_size * grid_size
    if extra_bits and arr[-1] >> (8 - extra_bits):
        raise ValueError("region_bitset has bits set outside the grid")

    cells = set()
    for x in range(grid_size):
        for y in range(grid_size):
            idx = x * grid_size + y
            if arr[idx // 8] & (1 << (idx % 8)):
                cells.add((x, y))
    return frozenset(cells)


# ============================================================================
# 9-step lifecycle functions (cut_lifecycle_v2 v3.2.2 §2-§9)
# ============================================================================
#
# 9 steps:
#   0. canonicalize      — raw cert dict → canonical bytes
#   1. generate          — oracle 产 (cert, scope) 元组
#   2. minimize          — literal-based deletion / QuickXplain (Phase 1.1 P1.11)
#   3. serialize         — Cut → JSON bytes
#   4. deserialize       — JSON bytes → Cut (schema validated by __post_init__)
#   5. validate          — independent recompute of cert in current state
#   6. attach-scope check — 6-step replay verify → ATTACH | HOLD | QUARANTINE
#   7. evaluate          — family-dispatched evaluate_geometric / evaluate_literal
#   8. apply-to-master   — push cut to CP-SAT master (Phase 1.3 P1.21)
#   9. replay regression — re-validate on new replay state (Step 5 re-entry)


def step_0_canonicalize(raw_cert_dict: JsonDict) -> bytes:
    """Step 0 — raw oracle cert dict → canonical bytes (sort keys, fixed enc)."""
    return canonical_bytes_for_cert(raw_cert_dict)


def step_1_generate_region_capacity_combinatorial(
    state: BState,
    region_kind: str,
    contributing_group: GroupId,
    canonical_rules: JsonDict,
) -> Optional[Cut]:
    """Step 1 (framework reference) — F1 region_capacity combinatorial generator.

    Phase 1.0 P1.1 carries this as the only generator (validates 9-step pipeline).
    Phase 1.1 P1.5 replaces with full F1 + Farkas certificate.

    Returns None on feasible state (no cut).
    """
    if region_kind == "left_baseline":
        region_cells = [(x, 0) for x in range(70)]
    elif region_kind == "bottom_baseline":
        region_cells = [(0, y) for y in range(70)]
    else:
        raise NotImplementedError(
            f"P1.1 framework: only left/bottom baseline; got {region_kind}. P1.5 加 interior_rect + ghost_complement."
        )

    region_set = frozenset(region_cells)

    # v1.2 static cap_R: |R| - ghost ∩ R - exterior ∩ R (不含 cell_owner)
    blocked_in_region = (state.ghost_cells | state.exterior_blocks) & region_set
    cap_R = len(region_cells) - len(blocked_in_region)

    cells_per_pose = {gid: canonical_rules[gid]["cells_per_pose"] for gid in [contributing_group]}
    demand_R = state.groups[contributing_group].demand * cells_per_pose[contributing_group]

    gap = demand_R - cap_R
    if gap <= 0:
        return None

    cert_dict = {
        "cert_kind": "region_capacity_combinatorial",
        "region_kind": region_kind,
        "region_cells_bitset_b64": _encode_region_bitset(region_cells),
        "cap_R": cap_R,
        "demand_R": demand_R,
        "gap": gap,
        "contributing_groups": [[contributing_group, demand_R]],
        "cells_per_pose": cells_per_pose,
        "lp_dual_ray_b64": None,
        "lp_dual_objective": None,
    }
    cert_payload = step_0_canonicalize(cert_dict)
    cert_hash = hashlib.sha256(cert_payload).hexdigest()

    active_assumptions: List[Assumption] = [
        Assumption(
            key="placement_rule",
            value=f"{contributing_group}={canonical_rules[contributing_group]['placement_rule']}",
        ),
    ]
    if region_kind in {"left_baseline", "bottom_baseline"}:
        active_assumptions.append(
            Assumption(
                key="left_or_bottom_boundary_saturation",
                value="left_baseline=23,bottom_baseline=23,demand=46,cells=138",
            )
        )

    return Cut(
        cut_id=f"F1-region-{int(time.time() * 1000)}",
        family="region_capacity",
        literals=None,
        geometric_payload=cert_payload,
        scope=CutScope(
            ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
            blocked_cells_hash=compute_blocked_cells_hash(state),
            exterior_blocks_hash=compute_exterior_blocks_hash(state),  # v3.2.2
            source_digest=compute_source_digest(state),
            artifact_hashes=state.artifact_hashes,
            oracle_abstraction_version="region_capacity_v1",
            active_assumptions=tuple(active_assumptions),
        ),
        cert=OracleCert(
            cert_kind="region_capacity_combinatorial",
            cert_payload=cert_payload,
            cert_hash=cert_hash,
        ),
        family_version="v1.2",
        validator_version="v1.2",
        payload_schema_version=1,
        oracle_name="region_capacity_v1",
        oracle_cert_hash=cert_hash,
        minimization_audit={"size_before": 1, "size_after": 1, "qx_calls": 0},
        iter_index=0,
    )


def step_2_minimize(cut: Cut, state: BState, oracle: Callable[..., object]) -> Cut:
    """Step 2 — literal-based deletion + QuickXplain minimize.

    Phase 1.0 P1.1: stubbed. Implemented in Phase 1.2B-F5 (F5 pattern_nogood
    用 L16 deletion minimizer wrap).
    """
    del oracle
    raise NotImplementedError("Step 2 minimize 在 Phase 1.2B-F5 (F5 pattern_nogood) 实施.")


def _scope_identity_preimage_to_jsonable(
    preimage: Optional[ScopeIdentityPreimageV1],
) -> Optional[JsonDict]:
    if preimage is None:
        return None
    if type(preimage) is not ScopeIdentityPreimageV1:
        raise ValueError("scope.identity_preimage must be an exact ScopeIdentityPreimageV1")
    _validate_scope_identity_preimage_v1(preimage)
    return {
        "version": 1,
        "ghost_rect": (list(preimage.ghost_rect) if preimage.ghost_rect is not None else None),
        "blocked_cells": [list(cell) for cell in preimage.blocked_cells],
        "exterior_blocks": [list(cell) for cell in preimage.exterior_blocks],
    }


def _scope_identity_preimage_from_jsonable(
    value: object,
) -> Optional[ScopeIdentityPreimageV1]:
    if value is None:
        return None
    if type(value) is not dict:
        raise ValueError("scope.identity_preimage must be an object or null")
    expected_fields = {
        "version",
        "ghost_rect",
        "blocked_cells",
        "exterior_blocks",
    }
    if set(value) != expected_fields:
        raise ValueError("scope.identity_preimage fields must match the v1 schema exactly")
    if type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("scope.identity_preimage.version must be the integer 1")

    raw_ghost_rect = value["ghost_rect"]
    if raw_ghost_rect is None:
        ghost_rect = None
    else:
        if type(raw_ghost_rect) is not list or len(raw_ghost_rect) != 4:
            raise ValueError("scope.identity_preimage.ghost_rect must be a four-item array or null")
        ghost_rect = tuple(raw_ghost_rect)

    def parse_cells(raw_cells: object, *, field_name: str) -> Tuple[Cell, ...]:
        if type(raw_cells) is not list:
            raise ValueError(f"scope.identity_preimage.{field_name} must be an array")
        cells: List[Cell] = []
        for raw_cell in raw_cells:
            if type(raw_cell) is not list or len(raw_cell) != 2:
                raise ValueError(f"scope.identity_preimage.{field_name} must contain two-item arrays")
            cells.append((raw_cell[0], raw_cell[1]))
        return tuple(cells)

    return ScopeIdentityPreimageV1(
        ghost_rect=ghost_rect,
        blocked_cells=parse_cells(
            value["blocked_cells"],
            field_name="blocked_cells",
        ),
        exterior_blocks=parse_cells(
            value["exterior_blocks"],
            field_name="exterior_blocks",
        ),
    )


def step_3_serialize(cut: Cut) -> bytes:
    """Step 3 — Cut → JSON bytes."""
    if cut.scope is None or cut.cert is None:
        raise ValueError(f"Cut {cut.cut_id}: scope/cert missing before serialize")
    cut_dict = {
        "cut_id": cut.cut_id,
        "family": cut.family,
        "literals": [
            {
                "slot_ref": {
                    "group_id": lit.slot_ref.group_id,
                    "slot_index": lit.slot_ref.slot_index,
                },
                "pose_id": lit.pose_id,
            }
            for lit in (cut.literals or ())
        ]
        if cut.literals
        else None,
        "geometric_payload": (
            base64.b64encode(cut.geometric_payload).decode("ascii") if cut.geometric_payload else None
        ),
        "scope": {
            "ghost_rect_id": cut.scope.ghost_rect_id,
            "blocked_cells_hash": cut.scope.blocked_cells_hash,
            "exterior_blocks_hash": cut.scope.exterior_blocks_hash,  # v3.2.2
            "source_digest": cut.scope.source_digest,
            "artifact_hashes": dict(cut.scope.artifact_hashes),
            "oracle_abstraction_version": cut.scope.oracle_abstraction_version,
            "active_assumptions": [{"key": a.key, "value": a.value} for a in cut.scope.active_assumptions],
            "identity_preimage": _scope_identity_preimage_to_jsonable(cut.scope.identity_preimage),
        },
        "cert": {
            "cert_kind": cut.cert.cert_kind,
            "cert_payload_b64": base64.b64encode(cut.cert.cert_payload).decode("ascii"),
            "cert_hash": cut.cert.cert_hash,
        },
        "family_version": cut.family_version,
        "validator_version": cut.validator_version,
        "payload_schema_version": cut.payload_schema_version,
        "oracle_name": cut.oracle_name,
        "oracle_cert_hash": cut.oracle_cert_hash,
        "minimization_audit": cut.minimization_audit,
        "created_at": cut.created_at,
        "iter_index": cut.iter_index,
        "is_quarantined": cut.is_quarantined,
        "quarantine_reason": cut.quarantine_reason,
    }
    return json.dumps(cut_dict, sort_keys=True, ensure_ascii=False).encode("utf-8")


def step_4_deserialize(blob: bytes) -> Cut:
    """Step 4 — JSON bytes → Cut. Schema check in __post_init__."""
    d = json.loads(blob)
    literals = None
    if d.get("literals"):
        literals = tuple(
            CutLiteral(
                slot_ref=AnonymousSlotRef(lit["slot_ref"]["group_id"], lit["slot_ref"]["slot_index"]),
                pose_id=lit["pose_id"],
            )
            for lit in d["literals"]
        )
    geometric_payload = None
    if d.get("geometric_payload"):
        geometric_payload = _strict_b64decode(d["geometric_payload"], "geometric_payload")

    scope = CutScope(
        ghost_rect_id=d["scope"]["ghost_rect_id"],
        blocked_cells_hash=d["scope"]["blocked_cells_hash"],
        exterior_blocks_hash=d["scope"]["exterior_blocks_hash"],  # v3.2.2
        source_digest=d["scope"]["source_digest"],
        artifact_hashes=d["scope"]["artifact_hashes"],
        oracle_abstraction_version=d["scope"]["oracle_abstraction_version"],
        active_assumptions=tuple(Assumption(a["key"], a["value"]) for a in d["scope"]["active_assumptions"]),
        identity_preimage=_scope_identity_preimage_from_jsonable(d["scope"].get("identity_preimage")),
    )
    cert = OracleCert(
        cert_kind=d["cert"]["cert_kind"],
        cert_payload=_strict_b64decode(d["cert"]["cert_payload_b64"], "cert.cert_payload_b64"),
        cert_hash=d["cert"]["cert_hash"],
    )
    cut = Cut(
        cut_id=d["cut_id"],
        family=d["family"],
        literals=literals,
        geometric_payload=geometric_payload,
        scope=scope,
        cert=cert,
        family_version=d["family_version"],
        validator_version=d["validator_version"],
        payload_schema_version=d["payload_schema_version"],
        oracle_name=d["oracle_name"],
        oracle_cert_hash=d["oracle_cert_hash"],
        minimization_audit=d.get("minimization_audit", {}),
        created_at=d.get("created_at", ""),
        iter_index=d.get("iter_index", -1),
        is_quarantined=d.get("is_quarantined", False),
        quarantine_reason=d.get("quarantine_reason", ""),
    )
    integrity_error = validate_cut_integrity(cut)
    if integrity_error is not None:
        raise ValueError(f"Cut {cut.cut_id}: {integrity_error}")
    return cut


def step_5_validate_region_capacity(cut: Cut, state: BState, canonical_rules: JsonDict) -> ValidationResult:
    """Step 5 — independent recompute of F1 cert (v1.2 §7).

    GPT pro round 2 fix: validator 入口 schema 走 explicit if (`python -O` 防线).
    """
    t0 = time.monotonic()
    if cut.geometric_payload is None:
        return ValidationResult(
            "schema_err",
            time.monotonic() - t0,
            "cut.geometric_payload is None (F1 schema invariant violated)",
        )
    try:
        cert_dict = json.loads(cut.geometric_payload)
        region_kind = cert_dict["region_kind"]

        if region_kind == "left_baseline":
            region_cells = [(x, 0) for x in range(70)]
        elif region_kind == "bottom_baseline":
            region_cells = [(0, y) for y in range(70)]
        else:
            return ValidationResult(
                "schema_err",
                time.monotonic() - t0,
                f"unsupported region_kind={region_kind}",
            )

        region_set = frozenset(region_cells)

        blocked_in_region = (state.ghost_cells | state.exterior_blocks) & region_set
        recomputed_cap_R = len(region_cells) - len(blocked_in_region)
        if recomputed_cap_R != cert_dict["cap_R"]:
            return ValidationResult(
                "unsound",
                time.monotonic() - t0,
                f"cap_R mismatch: cert={cert_dict['cap_R']}, recomputed={recomputed_cap_R}",
            )

        cert_cells_per_pose = cert_dict["cells_per_pose"]
        recomputed_demand_R = 0
        for gid, _ in cert_dict["contributing_groups"]:
            if gid not in cert_cells_per_pose:
                return ValidationResult(
                    "schema_err",
                    time.monotonic() - t0,
                    f"cert missing cells_per_pose[{gid}]",
                )
            current_cells_per_pose = canonical_rules[gid]["cells_per_pose"]
            if cert_cells_per_pose[gid] != current_cells_per_pose:
                return ValidationResult(
                    "unsound",
                    time.monotonic() - t0,
                    f"cells_per_pose mismatch for {gid}: "
                    f"cert={cert_cells_per_pose[gid]}, current={current_cells_per_pose}",
                )
            recomputed_demand_R += state.groups[gid].demand * cert_cells_per_pose[gid]

        if recomputed_demand_R != cert_dict["demand_R"]:
            return ValidationResult(
                "unsound",
                time.monotonic() - t0,
                f"demand_R mismatch: cert={cert_dict['demand_R']}, recomputed={recomputed_demand_R}",
            )

        if recomputed_demand_R <= recomputed_cap_R:
            return ValidationResult(
                "unsound",
                time.monotonic() - t0,
                f"witness fail: demand_R={recomputed_demand_R} ≤ cap_R={recomputed_cap_R}",
            )

        return ValidationResult("ok", time.monotonic() - t0)
    except Exception as e:
        return ValidationResult("schema_err", time.monotonic() - t0, str(e))


# Assumption verifier dispatch (cut_lifecycle_v2 v3.2.2 §4 Gap 5).
# Production verifier 实施在 src/cuts/assumptions/verifiers.py (P1.4 落地).
# 此函数 delegate 到 assumptions module 的 lookup_verifier — 解耦 dispatch
# table from lifecycle 框架, 让 P1.4+ 加 verifier 不动 lifecycle.py.
def assumption_holds(state: BState, assumption: Assumption) -> bool:
    """Dispatch via assumptions/verifiers.lookup_verifier.

    Lazy import 避 lifecycle ↔ assumptions 循环 import.
    Fail-closed: 未注册的 key → False (PROJECT_LOCK §4 silent recovery 禁).
    """
    from src.cuts.assumptions.verifiers import lookup_verifier

    verifier = lookup_verifier(assumption.key)
    if verifier is None:
        return False
    return verifier(state, assumption.value)


def step_6_attach_scope_check(compiled_cut: "CompiledCut", snapshot: Any) -> AttachDecision:
    """Step 6 — typed digest attestation (RFC-001 §3.2; B5a re-framed).

    Pre-B5a this was the raw-``Cut`` 6-step scope replay (source/ghost/blocked/
    artifact/oracle/assumption).  Those obligations now live in the single
    entry's ``_validate_scope_currentness`` (typed_platform), which runs BEFORE a
    ``CompiledCut`` can exist.  The attach-time role collapses to a fail-closed
    attestation: this compiled cut must have been produced from *this* snapshot.

    ``CompiledCut.snapshot_digest`` (set to ``snapshot.digest`` at compile time)
    and ``scope_digest`` (``_model_scope_digest(plan.model_scope)``) are the
    attestation carriers.  A non-``CompiledCut`` argument, a digest mismatch, or
    a scope-digest that no longer matches its plan all fail closed (QUARANTINE);
    the delegate call-graph (decision → this function) is preserved for the
    sealed step_7 obligation contract.
    """
    from src.cuts.typed_platform import CompiledCut as _CompiledCut
    from src.cuts.typed_platform import _model_scope_digest

    if type(compiled_cut) is not _CompiledCut:
        return "QUARANTINE"
    if compiled_cut.snapshot_digest != getattr(snapshot, "digest", None):
        return "QUARANTINE"
    if _model_scope_digest(compiled_cut.plan.model_scope) != compiled_cut.scope_digest:
        return "QUARANTINE"
    return "ATTACH"


def step_7_evaluation_attach_decision(compiled_cut: "CompiledCut", snapshot: Any) -> AttachDecision:
    """Side-effect-free Step 7 precondition: only attach an attested compiled cut.

    The sealed step_7 obligation contract pins the delegate call-graph
    (``step_7_evaluation_attach_decision`` → ``step_6_attach_scope_check``);
    the typed re-frame keeps that structure and reuses the attestation as the
    single attachability predicate.
    """
    return step_6_attach_scope_check(compiled_cut, snapshot)


def evaluator_scope_matches_current_state(compiled_cut: "CompiledCut", snapshot: Any) -> bool:
    """Fail-closed hot-path scope guard for Step 7 evaluation (typed).

    A compiled cut may only fire while its attestation binds it to the current
    snapshot; anything else fails closed so a stale/mis-bound compiled cut cannot
    prune before the orchestration/resolver machinery handles it.
    """
    return step_7_evaluation_attach_decision(compiled_cut, snapshot) == "ATTACH"


def evaluate_literal_multiset(compiled_cut: "CompiledCut", snapshot: Any) -> bool:
    """Retained checker-anchored literal guard (B5a typed re-frame).

    Pre-B5a this walked ``cut.literals`` against ``state.groups[...].
    selected_poses`` for the raw literal families (F3/F5/F7).  In the typed
    world literal soundness is the single entry's plugin ``validate_plan``
    (F5 → ShadowValidated, F7 → CompiledCut), so the attach-time literal guard
    collapses to the same attestation as every other family.  Kept as a named
    node (sealed step_7 contract requires ``evaluate_literal_multiset`` to call
    ``evaluator_scope_matches_current_state``).
    """
    return evaluator_scope_matches_current_state(compiled_cut, snapshot)


def step_7_evaluate_cut(compiled_cut: "CompiledCut", snapshot: Any) -> bool:
    """Step 7 — typed attach-timing check (RFC-001 §3.1; B5a).

    Reframed from the raw-``Cut`` family-dispatched evaluator to a typed
    attach-timing predicate over a ``CompiledCut`` + ``ValidatedStateSnapshot``.
    Soundness of the cut is already the single entry's job (a ``CompiledCut``
    only exists after full plugin ``parse_and_validate_proof``/``validate_plan``
    against this snapshot); the attach-timing question that remains is whether
    the compiled cut still attests to the current snapshot.  The legacy
    per-incumbent violation filter (a pruning-efficiency heuristic) is not
    reproduced — see the B5a delivery report accept-set note.
    """
    if not evaluator_scope_matches_current_state(compiled_cut, snapshot):
        return False
    return evaluate_literal_multiset(compiled_cut, snapshot)


class MasterModelLike(Protocol):
    """Structural contract for the CP-SAT master consumed by Step 8.

    Implemented by ``MasterPlacementModel`` (which forwards to the exact
    coordinate delegate). Kept as a Protocol so ``src/cuts`` stays
    import-isolated from ``src/models``/``src/search`` — the master is passed
    in duck-typed by the LBBD wiring (M3-4).
    """

    def _lower_region_capacity_cut(
        self,
        *,
        group_cell_weights: Mapping[str, int],
        capacity: int,
        condition_lits: Sequence[Any] = (),
    ) -> bool: ...

    def _lower_power_pose_exclusion_cut(
        self,
        *,
        group_id: str,
        pose_id: str,
        blocked_cells: Iterable[Cell],
        condition_lits: Sequence[Any],
    ) -> bool: ...

    def _lower_baseline_packing_cut(
        self,
        *,
        group_id: str,
        region_kind: str,
        capacity: int,
        condition_lits: Sequence[Any],
    ) -> bool: ...


_GHOST_RECT_DIGEST_PREFIX = b"zmd.ghost-rect.v1:"


def _ghost_rect_digest(rect: List[int]) -> str:
    """Recompute the snapshot-side ghost-rect identity for a live master rect.

    Byte-compatible with ``typed_platform._snapshot_ghost_rect_digest``
    (domain-separated prefix + compact ``[x, y, w, h]`` canonical JSON).
    """

    payload = json.dumps(
        rect,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(_GHOST_RECT_DIGEST_PREFIX + payload).hexdigest()


def _locate_master_ghost_rect(master: Any, target_digest: str) -> Optional[int]:
    """Return the live master ghost-domain index whose rect digest matches.

    The master keeps every candidate ghost anchor as a decision variable; the
    bound cut's ``ghost_rect_digest`` identifies exactly one of them.  The rect
    is reconstructed from the domain cell bbox (the same ``[x, y, w, h]`` the
    snapshot hashed) so the resolver never trusts a caller-supplied index.
    """

    for idx, domain in enumerate(master._ghost_domains):
        cells = domain.get("cells") or ()
        if not cells:
            continue
        xs = [int(cell[0]) for cell in cells]
        ys = [int(cell[1]) for cell in cells]
        min_x = min(xs)
        min_y = min(ys)
        rect = [min_x, min_y, max(xs) - min_x + 1, max(ys) - min_y + 1]
        if _ghost_rect_digest(rect) == target_digest:
            return idx
    return None


def _live_power_coverer_rows(
    master: Any,
    powered_facility_types: Sequence[str],
    live_pools: Mapping[str, Any],
) -> List[object]:
    """Project the live master coverer cache into the F7 projection schema.

    Reads ``_power_coverers_by_template_pose`` (a cache derived AFTER the pools,
    RFC-001 §5.3 / B4 拍板 7) rather than re-deriving from pools, so a mutated
    coverer table is caught by the resolve-time domain projection.  A missing
    cache entry is encoded distinctly from an empty coverer list.
    """

    coverers_by_pose = master._power_coverers_by_template_pose
    pole_pool = live_pools.get("power_pole") or ()
    rows: List[object] = []
    for facility_type in powered_facility_types:
        pool = live_pools.get(facility_type) or ()
        facility_coverers = coverers_by_pose.get(facility_type) or {}
        for pose_index, pose in enumerate(pool):
            pose_id = pose["pose_id"]
            entry = facility_coverers.get(pose_index)
            if entry is None:
                rows.append(
                    {
                        "coverer_entry_state": "missing",
                        "coverer_pole_pose_ids": [],
                        "coverer_pole_pose_indices": [],
                        "facility_type": facility_type,
                        "powered_pose_id": pose_id,
                        "powered_pose_index": pose_index,
                    }
                )
                continue
            indices = sorted(int(pole_index) for pole_index in entry)
            rows.append(
                {
                    "coverer_entry_state": "present",
                    "coverer_pole_pose_ids": [pole_pool[pole_index]["pose_id"] for pole_index in indices],
                    "coverer_pole_pose_indices": indices,
                    "facility_type": facility_type,
                    "powered_pose_id": pose_id,
                    "powered_pose_index": pose_index,
                }
            )
    return rows


def _live_master_domain_projection(master: Any, family: str) -> str:
    """Independently recompute one family's MasterDomainProjectionV1 from the
    LIVE master (RFC-001 §2.6).

    The three row families (facility pool projection / mandatory slot rows /
    template pose registration rows) are extracted from the live master's own
    structures and hashed through the shared snapshot primitive, so any drift
    between the frozen snapshot and the live master surfaces as a digest
    mismatch at resolve time (before the first master mutation).
    """

    from src.cuts.state_snapshot import (  # noqa: SLF001 - shared TCB projection primitives
        _F1_MASTER_DOMAIN_PLACEMENT_RULES,
        _F6_MASTER_DOMAIN_MAX_POSE_LENGTH,
        _F6_MASTER_DOMAIN_PLACEMENT_RULES,
        _master_domain_pose_registrations,
        master_domain_facility_pool_projection_v1,
        master_domain_projection_v1,
        power_hitting_set_master_domain_projection_v1,
    )

    delegate = master._coordinate_delegate
    if delegate is None:
        raise ValueError("resolver: master has no exact coordinate delegate (fail-closed)")
    mandatory_slots = delegate.mandatory_slots
    templates = master.templates
    live_pools = master.facility_pools

    relevant_group_ids: List[str] = []
    for group_id, slots in mandatory_slots.items():
        if not slots:
            continue
        facility_type = slots[0].template
        template = templates.get(facility_type) or {}
        placement_rule = template.get("placement_rule", "free")
        needs_power = bool(template.get("needs_power", False))
        dims = slots[0].dims
        if family == "region_capacity":
            if placement_rule in _F1_MASTER_DOMAIN_PLACEMENT_RULES:
                relevant_group_ids.append(group_id)
        elif family == "shape_packing_hall":
            if (
                placement_rule in _F6_MASTER_DOMAIN_PLACEMENT_RULES
                and min(dims) == 1
                and 2 <= max(dims) <= _F6_MASTER_DOMAIN_MAX_POSE_LENGTH
                and len(slots) >= 1
            ):
                relevant_group_ids.append(group_id)
        elif family == "power_hitting_set":
            if needs_power:
                relevant_group_ids.append(group_id)
        else:  # pragma: no cover - closed operation set upstream
            raise ValueError(f"resolver: unknown projection family {family!r} (fail-closed)")

    relevant_group_ids = sorted(relevant_group_ids)
    powered_facility_types = sorted({mandatory_slots[gid][0].template for gid in relevant_group_ids})
    projection_facility_types = list(powered_facility_types)
    if family == "power_hitting_set" and "power_pole" in live_pools:
        projection_facility_types = sorted(set(powered_facility_types) | {"power_pole"})

    relevant_pools = {
        facility_type: tuple(live_pools[facility_type])
        for facility_type in projection_facility_types
        if facility_type in live_pools
    }
    pose_occupied_cells: Dict[Tuple[str, str], FrozenSet[Cell]] = {}
    for facility_type in projection_facility_types:
        for pose in live_pools.get(facility_type) or ():
            pose_occupied_cells[(facility_type, pose["pose_id"])] = frozenset(
                (int(cell[0]), int(cell[1])) for cell in (pose.get("occupied_cells") or ())
            )

    is_power = family == "power_hitting_set"
    registration_rows, _pose_tuple_by_key = _master_domain_pose_registrations(
        relevant_pools,
        pose_occupied_cells,
        bidirectional=is_power,
        master_scalar_coercions=is_power,
    )

    mandatory_slot_rows: List[object] = []
    for group_id in relevant_group_ids:
        for slot in mandatory_slots[group_id]:
            allowed = sorted(slot.allowed_tuples)
            mandatory_slot_rows.append(
                {
                    "allowed_pose_tuples": [list(pose_tuple) for pose_tuple in allowed],
                    "candidate_pose_count": len(allowed),
                    "facility_type": slot.template,
                    "group_id": group_id,
                    "slot_index": slot.slot_index,
                    "slot_key": slot.key,
                    "slot_kind": slot.slot_kind,
                    "template_dimensions": [slot.dims[0], slot.dims[1]],
                }
            )

    facility_pool_projection = master_domain_facility_pool_projection_v1(relevant_pools)
    if is_power:
        coverer_rows = _live_power_coverer_rows(master, powered_facility_types, live_pools)
        return power_hitting_set_master_domain_projection_v1(
            facility_pool_projection=facility_pool_projection,
            mandatory_slot_rows=mandatory_slot_rows,
            template_pose_registration_rows=registration_rows,
            power_coverer_rows=coverer_rows,
        )
    family_subset = "region_capacity" if family == "region_capacity" else "shape_packing_hall"
    return master_domain_projection_v1(
        family_subset=family_subset,
        facility_pool_projection=facility_pool_projection,
        mandatory_slot_rows=mandatory_slot_rows,
        template_pose_registration_rows=registration_rows,
    )


def _resolve_model_scope_binding(model_scope: Any, snapshot: Any, master: Any) -> "ModelScopeBinding":
    """Sole resolver / constructor path for ``ModelScopeBinding`` (RFC-001 §2.6).

    Binds a compiled cut's master-independent ``ModelScope`` to the live master:
    the ghost literal(s) and blocked-cell body are recovered by object identity
    and frozen-snapshot values, and the master domain projection is recomputed
    live.  Everything is fail-closed; nothing here mutates the master.
    """

    from src.cuts.state_snapshot import blocked_cells_digest_v1
    from src.cuts.typed_platform import _build_model_scope_binding

    snapshot_digest = snapshot.digest

    ghost_policy = model_scope.ghost_policy
    if ghost_policy == "agnostic":
        rect_idx: Optional[int] = None
        ghost_rect_digest: Optional[str] = None
        condition_lits: Tuple[Any, ...] = ()
        blocked_cells: Optional[FrozenSet[Cell]] = None
    elif ghost_policy == "bound":
        target_digest = model_scope.ghost_rect_digest
        rect_idx = _locate_master_ghost_rect(master, target_digest)
        if rect_idx is None:
            raise ValueError("resolver: no live master ghost rect matches the plan ghost_rect_digest (fail-closed)")
        try:
            u_var = master.u_vars[rect_idx]
        except (KeyError, IndexError) as exc:
            raise ValueError("resolver: master lacks a ghost literal for the located rect (fail-closed)") from exc
        condition_lits = (u_var,)
        ghost_rect_digest = target_digest
        blocked = frozenset(snapshot.ghost_cells) | frozenset(snapshot.exterior_blocks)
        if blocked_cells_digest_v1(blocked) != snapshot.blocked_cells_digest:
            raise ValueError("resolver: reconstructed blocked cells drift from the snapshot digest (fail-closed)")
        blocked_cells = blocked
    else:
        raise ValueError(f"resolver: unknown ghost policy {ghost_policy!r} (fail-closed)")

    master_domain_projection = _resolve_live_master_domain_projection(model_scope, snapshot, master)

    return _build_model_scope_binding(
        rect_idx=rect_idx,
        ghost_rect_digest=ghost_rect_digest,
        condition_lits=condition_lits,
        blocked_cells=blocked_cells,
        snapshot_digest=snapshot_digest,
        master_domain_projection=master_domain_projection,
    )


def _resolve_live_master_domain_projection(model_scope: Any, snapshot: Any, master: Any) -> str:
    """Pick the family from the trusted snapshot, then recompute it live.

    The resolver signature carries only the ``ModelScope`` (no family tag), so
    the family is recovered by matching the plan's ``domain_fingerprint``
    against the snapshot's three cached per-family projections — a trusted
    side.  The returned projection is recomputed from the LIVE master, so a
    tampered master fails the step-8 fingerprint equality even though the
    family classification used the intact snapshot.
    """

    fingerprint = model_scope.domain_fingerprint
    if fingerprint == snapshot.master_domain_projection:
        family = "region_capacity"
    elif fingerprint == snapshot.shape_packing_hall_master_domain_projection:
        family = "shape_packing_hall"
    elif fingerprint == snapshot.power_hitting_set_master_domain_projection:
        family = "power_hitting_set"
    else:
        raise ValueError("resolver: plan domain fingerprint matches no snapshot family projection (fail-closed)")
    return _live_master_domain_projection(master, family)


def step_8_apply_to_master(
    compiled_cut: "CompiledCut",
    master: Any,
    *,
    scope_binding: "ModelScopeBinding",
) -> None:
    """Step 8 — push a typed ``CompiledCut`` to the CP-SAT master (RFC-001 §2.6).

    The master is the irreversible trust boundary.  This entry accepts ONLY an
    exact ``CompiledCut`` plus a ``ModelScopeBinding`` produced by the sole
    resolver (``_resolve_model_scope_binding``); a raw ``Cut``, a
    ``ShadowValidated`` (F5), or any non-typed object is refused by the type
    gate BEFORE the master is touched.  It then runs the §2.6 three-fold binding
    check (ghost identity / live domain projection / snapshot digest) — each
    fail-closed with zero master mutation — and dispatches the actual lowering
    through the typed plan interpreter (``typed_apply.apply_compiled_cut``).

    F5 ``pattern_nogood`` has no ``operation`` and never produces a
    ``CompiledCut``, so it structurally cannot reach the master here (RFC-001
    §5.4); its shadow result is dropped by the orchestration layer.
    """

    from src.cuts import typed_apply as _typed_apply
    from src.cuts.typed_platform import CompiledCut as _CompiledCut, ModelScopeBinding as _ModelScopeBinding

    # Type gate FIRST: refuse anything that is not an exact CompiledCut /
    # ModelScopeBinding before reading a single master attribute (fail-closed).
    if type(compiled_cut) is not _CompiledCut:
        raise TypeError("step_8: first argument must be an exact CompiledCut (raw Cut / ShadowValidated refused)")
    if type(scope_binding) is not _ModelScopeBinding:
        raise TypeError("step_8: scope_binding must be an exact ModelScopeBinding from the resolver")

    scope = compiled_cut.plan.model_scope
    # §2.6 three-fold binding check — all fail-closed, none mutates the master.
    if scope.ghost_rect_digest != scope_binding.ghost_rect_digest:
        raise ValueError("step_8: ghost_rect_digest mismatch between plan scope and resolved binding (fail-closed)")
    if scope.domain_fingerprint != scope_binding.master_domain_projection:
        raise ValueError("step_8: live master domain projection drifted from the plan fingerprint (fail-closed)")
    if compiled_cut.snapshot_digest != scope_binding.snapshot_digest:
        raise ValueError("step_8: snapshot digest mismatch between compiled cut and resolved binding (fail-closed)")

    _typed_apply.apply_compiled_cut(compiled_cut, master, scope_binding=scope_binding)


# Step 9 = re-entry into Step 5 (validate) on new replay state.
# 不需要独立函数; ``step_5_validate_*`` 调用即可。


# ============================================================================
# Full lifecycle pipeline (P1.1 framework reference)
# ============================================================================


@dataclass
class LifecycleReport:
    step: str
    ok: bool
    detail: str = ""


def run_lifecycle(
    state_at_gen: BState,
    state_at_replay: BState,
    region_kind: str,
    contributing_group: GroupId,
    canonical_rules: JsonDict,
) -> List[LifecycleReport]:
    """End-to-end framework reference: 9-step lifecycle on F1 region_capacity.

    Phase 1.1+ 各 family generator 接 ``store.add_cut(...)`` 后, 这个 helper
    退化为 framework test fixture (test_lifecycle.py 用).
    """
    reports: List[LifecycleReport] = []

    cut = step_1_generate_region_capacity_combinatorial(state_at_gen, region_kind, contributing_group, canonical_rules)
    if cut is None:
        reports.append(LifecycleReport("step_1_generate", False, "no infeasibility, no cut"))
        return reports
    if cut.geometric_payload is None or cut.cert is None:
        reports.append(LifecycleReport("step_1_generate", False, "generated cut missing payload/cert"))
        return reports
    cert = json.loads(cut.geometric_payload)
    reports.append(
        LifecycleReport(
            "step_1_generate",
            True,
            f"cut_id={cut.cut_id} cap_R={cert['cap_R']} demand_R={cert['demand_R']}",
        )
    )

    blob = step_3_serialize(cut)
    reports.append(LifecycleReport("step_3_serialize", True, f"{len(blob)} bytes"))

    cut_d = step_4_deserialize(blob)
    if cut_d.cert is None or cut.cert is None:
        reports.append(LifecycleReport("step_4_deserialize", False, "missing cert after deserialize"))
        return reports
    if cut_d.cut_id != cut.cut_id or cut_d.cert.cert_hash != cut.cert.cert_hash:
        reports.append(LifecycleReport("step_4_deserialize", False, "round-trip mismatch"))
        return reports
    reports.append(LifecycleReport("step_4_deserialize", True, "round-trip OK"))

    vr_gen = step_5_validate_region_capacity(cut_d, state_at_gen, canonical_rules)
    reports.append(
        LifecycleReport(
            "step_5_validate_at_gen",
            vr_gen.kind == "ok",
            f"{vr_gen.kind} ({vr_gen.elapsed_seconds * 1000:.2f}ms) {vr_gen.detail or ''}",
        )
    )

    # B5a: Step 6/7 attach-scope + evaluate are typed-only now (they take a
    # CompiledCut + ValidatedStateSnapshot).  The raw-Cut attach path was
    # removed with the legacy Step 8 shim; the reference pipeline records the
    # delegation rather than calling the typed chain on legacy fixtures (the
    # end-to-end typed attach lives in src/tests/cuts/test_stage_b_*).
    reports.append(
        LifecycleReport(
            "step_6_7_attach_evaluate",
            True,
            "delegated to typed single entry (validate_and_compile_cut) — RFC-001 §3/§4.9",
        )
    )

    vr_replay = step_5_validate_region_capacity(cut_d, state_at_replay, canonical_rules)
    reports.append(
        LifecycleReport(
            "step_9_replay_validate",
            vr_replay.kind == "ok",
            f"{vr_replay.kind} {vr_replay.detail or ''}",
        )
    )

    return reports
