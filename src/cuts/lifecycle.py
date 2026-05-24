"""Cut object schema + 9-step lifecycle (B Design v2 Phase 1.0 P1.1).

Migrated from docs/research/p3_b_design_v2_20260521/poc/b_core_lifecycle_poc.py
(PoC 14/14 PASS) with the following Phase 1 production adjustments:

1. **9-family map** (Phase 0 final, vs PoC 8-family with symmetry_lift):
   F1 region_capacity / F2 cutset / F3 port_exposure / F4 component_reach /
   F5 pattern_nogood / F6 shape_packing_hall / F7 power_hitting_set /
   F8 power_grid_reach / F9 density_envelope.
   ``symmetry_lift`` removed (not in Phase 0 final 9-family matrix).
2. **CutScope.exterior_blocks_hash** added (cut_lifecycle_v2 v3.2.2,
   Gemini round 21 fix). Step 3 (attach-scope) dispatches by GHOST_AGNOSTIC:
   - GHOST_AGNOSTIC cut: verify ``exterior_blocks_hash`` only (cut可跨 ghost 复用)
   - ghost-bound cut: verify full ``blocked_cells_hash`` (含 ghost ∪ exterior)
3. **Step 2 (minimize) / Step 8 (apply-to-master)** stubbed with NotImplementedError;
   implemented in Phase 1.1 P1.11 (F5 deletion + QuickXplain) and Phase 1.3 P1.21
   (master CP-SAT apply), respectively.

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
from typing import Any, Callable, Dict, FrozenSet, List, Literal, Optional, Protocol, Tuple


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

CutFamily = Literal[
    "region_capacity",       # F1 (geometric)
    "cutset",                # F2 (geometric)
    "port_exposure",         # F3 (literal)
    "component_reach",       # F4 (geometric)
    "pattern_nogood",        # F5 (literal)
    "shape_packing_hall",    # F6 (geometric)
    "power_hitting_set",     # F7 (literal)
    "power_grid_reach",      # F8 (geometric)
    "density_envelope",      # F9 (geometric)
]

# Family ↔ mode mapping enforces XOR (literal-based vs geometric-based).
# PROJECT_LOCK §3A invariant 3 (family↔mode 不可改).
_FAMILY_MODE_MAP: Dict[str, Literal["literal", "geometric"]] = {
    "region_capacity":      "geometric",
    "cutset":                "geometric",
    "port_exposure":         "literal",
    "component_reach":       "geometric",
    "pattern_nogood":        "literal",
    "shape_packing_hall":    "geometric",
    "power_hitting_set":     "literal",
    "power_grid_reach":      "geometric",
    "density_envelope":      "geometric",
}


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


@dataclass(frozen=True)
class CutScope:
    """v3.2.2: ``exterior_blocks_hash`` 新加 (Gemini round 21).

    Step 3 (attach-scope verify) dispatch:
    - GHOST_AGNOSTIC cut: verify ``exterior_blocks_hash`` only
    - ghost-bound cut: verify full ``blocked_cells_hash``
    """
    ghost_rect_id: GhostRectId
    blocked_cells_hash: Hash
    exterior_blocks_hash: Hash       # v3.2.2 新加
    source_digest: SourceDigestStr
    artifact_hashes: Dict[str, Hash] = field(default_factory=dict)
    oracle_abstraction_version: str = ""
    active_assumptions: Tuple[Assumption, ...] = ()


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
        raise ValueError(f"Cut {cut_id}: family={family} 不在 9-family 表")
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

def compute_ghost_rect_id(rect: Optional[Tuple[int, int, int, int]]) -> GhostRectId:
    if rect is None:
        return GHOST_AGNOSTIC
    blob = f"{rect[0]},{rect[1]},{rect[2]},{rect[3]}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def compute_blocked_cells_hash(state: BState) -> Hash:
    """blocked_cells = ghost ∪ exterior (跨层 sound — 不含 cell_owner)."""
    blocked = sorted(state.ghost_cells | state.exterior_blocks)
    blob = ";".join(f"{c[0]},{c[1]}" for c in blocked).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def compute_exterior_blocks_hash(state: BState) -> Hash:
    """v3.2.2 新: 仅 exterior_blocks (排除 ghost_cells), GHOST_AGNOSTIC 路径用."""
    blocked = sorted(state.exterior_blocks)
    blob = ";".join(f"{c[0]},{c[1]}" for c in blocked).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _source_jsonable(value: Any) -> Any:
    """Normalize source payloads before hashing; ignore runtime caches."""
    if isinstance(value, dict):
        normalized: Dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.startswith("__"):
                continue
            normalized[str(key)] = _source_jsonable(item)
        return normalized
    if isinstance(value, (list, tuple)):
        return [_source_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_source_jsonable(item) for item in value), key=repr)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def compute_source_digest(state: BState) -> SourceDigestStr:
    """Return stable content digest for cross-session cut replay scope.

    ``BState.source_digest`` is treated as an optional caller-side note/cache,
    not as authority. Step 6 must be tied to the actual source payloads injected
    into BState; otherwise a stale or hand-written digest can mask data changes.
    """
    parts: JsonDict = {
        "schema_version": 1,
        "canonical_rules": state.canonical_rules or {},
        "candidate_placements": state.candidate_placements or {},
        "mandatory_exact_instances": state.instance_to_facility_type or {},
        "facility_templates": state.facility_templates or {},
        "generic_io_requirements": state.commodity_demands or {},
        "commodity_routes": state.commodity_routes or {},
    }
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
        return (
            f"oracle_cert_hash mismatch: oracle={cut.oracle_cert_hash!r}, "
            f"cert={cut.cert.cert_hash!r}"
        )
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
        raise ValueError(
            f"region_bitset length mismatch: got {len(arr)}, expected {expected_len}"
        )
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
            f"P1.1 framework: only left/bottom baseline; got {region_kind}. "
            f"P1.5 加 interior_rect + ghost_complement."
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
        cut_id=f"F1-region-{int(time.time()*1000)}",
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
    raise NotImplementedError(
        "Step 2 minimize 在 Phase 1.2B-F5 (F5 pattern_nogood) 实施."
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
        ] if cut.literals else None,
        "geometric_payload": (
            base64.b64encode(cut.geometric_payload).decode("ascii")
            if cut.geometric_payload else None
        ),
        "scope": {
            "ghost_rect_id": cut.scope.ghost_rect_id,
            "blocked_cells_hash": cut.scope.blocked_cells_hash,
            "exterior_blocks_hash": cut.scope.exterior_blocks_hash,  # v3.2.2
            "source_digest": cut.scope.source_digest,
            "artifact_hashes": dict(cut.scope.artifact_hashes),
            "oracle_abstraction_version": cut.scope.oracle_abstraction_version,
            "active_assumptions": [
                {"key": a.key, "value": a.value}
                for a in cut.scope.active_assumptions
            ],
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
                slot_ref=AnonymousSlotRef(
                    lit["slot_ref"]["group_id"], lit["slot_ref"]["slot_index"]
                ),
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
        active_assumptions=tuple(
            Assumption(a["key"], a["value"]) for a in d["scope"]["active_assumptions"]
        ),
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


def step_5_validate_region_capacity(
    cut: Cut, state: BState, canonical_rules: JsonDict
) -> ValidationResult:
    """Step 5 — independent recompute of F1 cert (v1.2 §7).

    GPT pro round 2 fix: validator 入口 schema 走 explicit if (`python -O` 防线).
    """
    t0 = time.monotonic()
    if cut.geometric_payload is None:
        return ValidationResult(
            "schema_err", time.monotonic() - t0,
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
                "schema_err", time.monotonic() - t0,
                f"unsupported region_kind={region_kind}",
            )

        region_set = frozenset(region_cells)

        blocked_in_region = (state.ghost_cells | state.exterior_blocks) & region_set
        recomputed_cap_R = len(region_cells) - len(blocked_in_region)
        if recomputed_cap_R != cert_dict["cap_R"]:
            return ValidationResult(
                "unsound", time.monotonic() - t0,
                f"cap_R mismatch: cert={cert_dict['cap_R']}, recomputed={recomputed_cap_R}",
            )

        cert_cells_per_pose = cert_dict["cells_per_pose"]
        recomputed_demand_R = 0
        for gid, _ in cert_dict["contributing_groups"]:
            if gid not in cert_cells_per_pose:
                return ValidationResult(
                    "schema_err", time.monotonic() - t0,
                    f"cert missing cells_per_pose[{gid}]",
                )
            current_cells_per_pose = canonical_rules[gid]["cells_per_pose"]
            if cert_cells_per_pose[gid] != current_cells_per_pose:
                return ValidationResult(
                    "unsound", time.monotonic() - t0,
                    f"cells_per_pose mismatch for {gid}: "
                    f"cert={cert_cells_per_pose[gid]}, current={current_cells_per_pose}",
                )
            recomputed_demand_R += state.groups[gid].demand * cert_cells_per_pose[gid]

        if recomputed_demand_R != cert_dict["demand_R"]:
            return ValidationResult(
                "unsound", time.monotonic() - t0,
                f"demand_R mismatch: cert={cert_dict['demand_R']}, recomputed={recomputed_demand_R}",
            )

        if recomputed_demand_R <= recomputed_cap_R:
            return ValidationResult(
                "unsound", time.monotonic() - t0,
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


def step_6_attach_scope_check(cut: Cut, state: BState) -> AttachDecision:
    """Step 6 — 6-step attach-scope replay verify (cut_lifecycle_v2 v3.2.2 §4).

    Dispatch (v3.2.2 round 21 fix):
    - GHOST_AGNOSTIC cut: verify ``exterior_blocks_hash`` only (cut可跨 ghost 复用)
    - ghost-bound cut: verify full ``blocked_cells_hash``
    """
    if cut.scope is None:
        return "QUARANTINE"
    # Step 1: source_digest
    if cut.scope.source_digest != compute_source_digest(state):
        return "QUARANTINE"

    # Step 2: ghost match
    current_ghost_id = compute_ghost_rect_id(state.ghost_rect)
    is_ghost_agnostic = cut.scope.ghost_rect_id == GHOST_AGNOSTIC
    if not is_ghost_agnostic and cut.scope.ghost_rect_id != current_ghost_id:
        return "HOLD"

    # Step 3 (v3.2.2 dispatch): blocked_cells_hash OR exterior_blocks_hash
    if is_ghost_agnostic:
        # cut family agnostic to ghost — verify exterior_blocks_hash only
        if cut.scope.exterior_blocks_hash != compute_exterior_blocks_hash(state):
            return "QUARANTINE"
    else:
        # ghost-bound — verify full blocked_cells_hash (ghost ∪ exterior)
        if cut.scope.blocked_cells_hash != compute_blocked_cells_hash(state):
            return "QUARANTINE"

    # Step 4: artifact_hashes
    for fname, h in cut.scope.artifact_hashes.items():
        if state.artifact_hashes.get(fname) != h:
            return "QUARANTINE"

    # Step 5: oracle version
    if cut.scope.oracle_abstraction_version not in state.available_oracle_versions:
        return "HOLD"

    # Step 6: active_assumptions
    for assumption in cut.scope.active_assumptions:
        if not assumption_holds(state, assumption):
            return "HOLD"

    return "ATTACH"


def evaluate_literal_multiset(cut: Cut, state: BState) -> bool:
    """Generic literal-based cut evaluator (state_machine_v2 §5 multiset 语义).

    Used by all literal-based families (F3 port_exposure / F5 pattern_nogood /
    F7 power_hitting_set). Per state_machine_v2 §5 + Gemini round 27 finding B3:
    slot indices inside a group are **anonymous** (any permutation of named
    instances within a group yields the same group-anonymous state). So a cut
    that lists ``(group=crusher, slot=2, pose=p1)`` is equivalent to
    ``(group=crusher, slot=5, pose=p1)`` after slot relabeling — must enumerate
    **multiset subset match**, not slot-index 1-to-1.

    Returns True iff for every (group_id, pose_id) demand count in
    ``cut.literals``, ``state.groups[group_id].selected_poses`` contains at
    least that many copies (Counter ≥ Counter).

    Pre-check: each referenced group has enough total selected_poses
    (avoid unnecessary Counter walk). False on missing group.
    """
    from collections import Counter

    if cut.literals is None or len(cut.literals) == 0:
        return False  # literal-based cut without literals is no-op

    # Aggregate cut demand per (group_id, pose_id)
    cut_demand: Counter[Tuple[GroupId, PoseId]] = Counter()
    for lit in cut.literals:
        cut_demand[(lit.slot_ref.group_id, lit.pose_id)] += 1

    # Pre-check: each group has at least required_slot_count
    referenced_groups: Dict[GroupId, int] = {}
    for (gid, _), c in cut_demand.items():
        referenced_groups[gid] = referenced_groups.get(gid, 0) + c
    for gid, required in referenced_groups.items():
        if gid not in state.groups:
            return False
        if len(state.groups[gid].selected_poses) < required:
            return False

    # Multiset subset match — Gap 12 修 (round 31): selected_poses is List[PoseId]
    # per spec, **不**是 List[Tuple]. group_id comes from outer loop.
    state_counts: Counter[Tuple[GroupId, PoseId]] = Counter()
    for gid in referenced_groups:
        for pose_id in state.groups[gid].selected_poses:
            state_counts[(gid, pose_id)] += 1

    for k, demand_count in cut_demand.items():
        if state_counts[k] < demand_count:
            return False
    return True


def step_7_evaluate_cut(cut: Cut, state: BState) -> bool:
    """Step 7 — family-dispatched evaluate.

    GPT pro v2 round 1+2 P0-1 fix: 原硬编码 `region_capacity → return True` 是
    Step F 修复未接入 production framework 的死路 — family 函数 evaluate_geometric_*
    已真重算 sound, 但 framework 入口仍 bypass. 必须 dispatch 到 family evaluator.

    Geometric: F1 region_capacity / F2 cutset / F4 component_reach 各有
    families/<name>.evaluate_geometric_*. 其它 geometric family (F6/F8/F9
    Phase 1.2/1.5+) 落地后注册到此 dispatch.

    Literal: F3 port_exposure / F5 pattern_nogood / F7 power_hitting_set 走
    generic evaluate_literal_multiset (state_machine_v2 §5 multiset semantics).
    """
    if cut.geometric_payload is not None:
        # Lazy import 避循环 (families import lifecycle for BState/Cut types).
        from src.cuts.families.component_reach import evaluate_geometric_component_reach
        from src.cuts.families.cutset import evaluate_geometric_cutset
        from src.cuts.families.density_envelope import evaluate_geometric_density_envelope
        from src.cuts.families.region_capacity import evaluate_geometric_region_capacity
        if cut.family == "region_capacity":
            return evaluate_geometric_region_capacity(cut, state)
        if cut.family == "cutset":
            return evaluate_geometric_cutset(cut, state)
        if cut.family == "component_reach":
            return evaluate_geometric_component_reach(cut, state)
        if cut.family == "density_envelope":
            return evaluate_geometric_density_envelope(cut, state)
        raise NotImplementedError(
            f"family={cut.family} geometric evaluator 未注册 — "
            f"Phase 1.2/1.5+ F6/F8 实施时加入此 dispatch."
        )
    # literal-based — generic multiset eval (F3/F5/F7 all use this)
    return evaluate_literal_multiset(cut, state)


class MasterModelLike(Protocol):
    """Structural placeholder for the future CP-SAT master integration."""


def step_8_apply_to_master(cut: Cut, master_model: MasterModelLike) -> None:
    """Step 8 — push cut as constraint to CP-SAT master."""
    del master_model
    raise NotImplementedError(
        "Step 8 apply-to-master 在 Phase 1.3 P1.21 (benders_loop integration) 实施."
    )


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

    cut = step_1_generate_region_capacity_combinatorial(
        state_at_gen, region_kind, contributing_group, canonical_rules
    )
    if cut is None:
        reports.append(LifecycleReport("step_1_generate", False, "no infeasibility, no cut"))
        return reports
    if cut.geometric_payload is None or cut.cert is None:
        reports.append(LifecycleReport("step_1_generate", False, "generated cut missing payload/cert"))
        return reports
    cert = json.loads(cut.geometric_payload)
    reports.append(LifecycleReport(
        "step_1_generate", True,
        f"cut_id={cut.cut_id} cap_R={cert['cap_R']} demand_R={cert['demand_R']}",
    ))

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
    reports.append(LifecycleReport(
        "step_5_validate_at_gen", vr_gen.kind == "ok",
        f"{vr_gen.kind} ({vr_gen.elapsed_seconds*1000:.2f}ms) {vr_gen.detail or ''}",
    ))

    decision = step_6_attach_scope_check(cut_d, state_at_replay)
    reports.append(LifecycleReport(
        "step_6_attach_scope_at_replay", decision == "ATTACH",
        f"decision={decision}",
    ))

    if decision == "ATTACH":
        violate = step_7_evaluate_cut(cut_d, state_at_replay)
        reports.append(LifecycleReport(
            "step_7_evaluate", True,
            f"violate={violate} (expected True for F1 scope-bound)",
        ))

    vr_replay = step_5_validate_region_capacity(cut_d, state_at_replay, canonical_rules)
    reports.append(LifecycleReport(
        "step_9_replay_validate", vr_replay.kind == "ok",
        f"{vr_replay.kind} {vr_replay.detail or ''}",
    ))

    return reports
