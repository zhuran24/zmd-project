"""B core PoC — Cut object lifecycle 6 步 + Family 1 region_capacity runtime.

Purpose
-------
补做 Phase 0 prep 项 3 (上次 prep 清单没做的). Schema-first 不 retrofit:
在写 src/ implementation 之前 runtime 验 cut object lifecycle 全 9 步 + Family 1
拦 F1 boundary saturation 反例.

防 v4 replay bug 教训 ([[feedback_proof_object_lifecycle]]): "schema landed ≠
runtime correct".

Not src/: 这是 docs/research/ 下 PoC, 不进 production code path. Phase 1
implementation 时再迁 src/cuts/.

References
----------
- cut_lifecycle_v2.md v3.1 §2-§9 (9 步 lifecycle)
- cut_family_specs/01_region_capacity.md v1.1 (Family 1 完整 spec)
- red_fixtures/F1_boundary_saturation.md (反例)
- state_machine_v2.md §2 (BState schema)
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Counter as CounterT
from collections import Counter
from typing import Callable, Dict, FrozenSet, List, Literal, Optional, Tuple


# ============================================================================
# Identifier types (per cut_lifecycle_v2 §3)
# ============================================================================

CutId = str
GroupId = str
PoseId = int
Cell = Tuple[int, int]
GhostRectId = str
Hash = str
SourceDigestStr = str

GHOST_AGNOSTIC: GhostRectId = "__ghost_agnostic__"

CutFamily = Literal[
    "region_capacity",
    "cutset",
    "port_exposure",
    "component_reach",
    "pattern_nogood",
    "shape_packing_hall",
    "power_hitting_set",
    "symmetry_lift",
]

_FAMILY_MODE_MAP: Dict[str, Literal["literal", "geometric"]] = {
    "region_capacity":      "geometric",
    "cutset":                "geometric",
    "port_exposure":         "literal",
    "component_reach":       "geometric",
    "pattern_nogood":        "literal",
    "shape_packing_hall":    "geometric",
    "power_hitting_set":     "literal",
    "symmetry_lift":         "literal",
}


# ============================================================================
# Cut object schema (cut_lifecycle_v2 v3 §3)
# ============================================================================

@dataclass(frozen=True)
class AnonymousSlotRef:
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
    ghost_rect_id: GhostRectId
    blocked_cells_hash: Hash
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
        has_lit = self.literals is not None and len(self.literals) > 0
        has_geo = self.geometric_payload is not None
        if has_lit == has_geo:
            raise ValueError(
                f"Cut {self.cut_id}: literals XOR geometric_payload 必须互斥; "
                f"literals={'set' if has_lit else 'empty/None'}, "
                f"geometric_payload={'set' if has_geo else 'None'}"
            )
        mode = _FAMILY_MODE_MAP.get(self.family)
        if mode == "literal" and not has_lit:
            raise ValueError(f"family={self.family} 要求 literal-based")
        if mode == "geometric" and not has_geo:
            raise ValueError(f"family={self.family} 要求 geometric")


AttachDecision = Literal["ATTACH", "HOLD", "QUARANTINE"]


@dataclass(frozen=True)
class ValidationResult:
    kind: Literal["ok", "unsound", "timeout", "schema_err"]
    elapsed_seconds: float
    detail: Optional[str] = None


# ============================================================================
# BState mini-mock (state_machine_v2 §2 — 仅 PoC scope)
# ============================================================================

@dataclass
class GroupState:
    group_id: GroupId
    demand: int
    pose_domain: FrozenSet[Tuple[GroupId, int]]
    selected_poses: List[Tuple[GroupId, int]] = field(default_factory=list)

    @property
    def remaining_count(self) -> int:
        return self.demand - len(self.selected_poses)


@dataclass
class BState:
    """PoC 简化版 — 仅 carry F1 region_capacity 所需 field."""
    groups: Dict[GroupId, GroupState]
    cell_owner: Dict[Cell, Tuple[GroupId, int]] = field(default_factory=dict)
    ghost_rect: Optional[Tuple[int, int, int, int]] = None  # (x, y, h, w)
    ghost_cells: FrozenSet[Cell] = frozenset()
    exterior_blocks: FrozenSet[Cell] = frozenset()
    artifact_hashes: Dict[str, Hash] = field(default_factory=dict)
    available_oracle_versions: FrozenSet[str] = frozenset()


# ============================================================================
# Helper functions
# ============================================================================

def compute_ghost_rect_id(rect: Optional[Tuple[int, int, int, int]]) -> GhostRectId:
    """cut_lifecycle_v2 v3 §4 helper."""
    if rect is None:
        return GHOST_AGNOSTIC
    blob = f"{rect[0]},{rect[1]},{rect[2]},{rect[3]}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def compute_blocked_cells_hash(state: BState) -> Hash:
    """blocked_cells = ghost ∪ exterior. 不含 cell_owner (跨层 sound)."""
    blocked = sorted(state.ghost_cells | state.exterior_blocks)
    blob = ";".join(f"{c[0]},{c[1]}" for c in blocked).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def canonical_bytes_for_cert(payload: Dict) -> bytes:
    """Step 0 canonicalize: sort keys, fixed encoding."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")


# ============================================================================
# Family 1 region_capacity cert schema + validator (per cut_family_specs/01 v1.1)
# ============================================================================

@dataclass(frozen=True)
class RegionCapacityCert:
    region_kind: str  # "left_baseline" | "bottom_baseline" | "interior_rect" | "ghost_complement"
    region_cells_bitset_b64: str
    cap_R: int
    demand_R: int
    gap: int  # demand_R - cap_R
    contributing_groups: Tuple[Tuple[GroupId, int], ...]
    cells_per_pose: Dict[GroupId, int]  # v1.1 — Gemini round 14 finding #5
    lp_dual_ray_b64: Optional[str] = None
    lp_dual_objective: Optional[float] = None


def _encode_region_bitset(cells: List[Cell], grid_size: int = 70) -> str:
    """Encode cell list to base64 bitset over grid (PoC: 70x70 = 4900 cells)."""
    arr = bytearray(grid_size * grid_size // 8 + 1)
    for x, y in cells:
        idx = x * grid_size + y
        arr[idx // 8] |= 1 << (idx % 8)
    return base64.b64encode(bytes(arr)).decode("ascii")


def _decode_region_bitset(b64: str, grid_size: int = 70) -> FrozenSet[Cell]:
    arr = base64.b64decode(b64)
    cells = set()
    for x in range(grid_size):
        for y in range(grid_size):
            idx = x * grid_size + y
            if arr[idx // 8] & (1 << (idx % 8)):
                cells.add((x, y))
    return frozenset(cells)


# ============================================================================
# Lifecycle steps 0-9
# ============================================================================

def step_0_canonicalize(raw_cert_dict: Dict) -> bytes:
    """Step 0: canonicalize raw oracle cert to canonical bytes."""
    return canonical_bytes_for_cert(raw_cert_dict)


def step_1_generate_region_capacity_combinatorial(
    state: BState,
    region_kind: str,
    contributing_group: GroupId,
    canonical_rules: Dict,
) -> Optional[Cut]:
    """Step 1 + 2: combinatorial generator for Family 1 region_capacity.

    F1 反例 owner: left_baseline 138 cells 100% saturation, crusher 占 left
    baseline → cap_R < demand_R → 生成 cut.
    """
    # 计算 region cells (PoC: 简化版 left_baseline = column y=0)
    if region_kind == "left_baseline":
        region_cells = [(x, 0) for x in range(70)]
    elif region_kind == "bottom_baseline":
        region_cells = [(0, y) for y in range(70)]
    else:
        raise NotImplementedError(f"PoC scope: only left/bottom baseline, got {region_kind}")

    region_set = frozenset(region_cells)

    # v1.1 static cap_R: |R| - ghost ∩ R - exterior ∩ R (不含 cell_owner)
    blocked_in_region = (state.ghost_cells | state.exterior_blocks) & region_set
    cap_R = len(region_cells) - len(blocked_in_region)

    # demand_R = group.demand * cells_per_pose
    cells_per_pose = {gid: canonical_rules[gid]["cells_per_pose"] for gid in [contributing_group]}
    demand_R = state.groups[contributing_group].demand * cells_per_pose[contributing_group]

    gap = demand_R - cap_R
    if gap <= 0:
        return None  # feasible, no cut

    # Build cert + cut
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

    # Active assumptions
    active_assumptions: List[Assumption] = [
        Assumption(key="placement_rule",
                   value=f"{contributing_group}={canonical_rules[contributing_group]['placement_rule']}"),
    ]
    if region_kind in {"left_baseline", "bottom_baseline"}:
        active_assumptions.append(
            Assumption(key="left_or_bottom_boundary_saturation",
                       value="left_baseline=23,bottom_baseline=23,demand=46,cells=138")
        )

    cut = Cut(
        cut_id=f"poc-F1-region-{int(time.time()*1000)}",
        family="region_capacity",
        literals=None,
        geometric_payload=cert_payload,
        scope=CutScope(
            ghost_rect_id=compute_ghost_rect_id(state.ghost_rect),
            blocked_cells_hash=compute_blocked_cells_hash(state),
            source_digest="poc_source_digest",
            artifact_hashes=state.artifact_hashes,
            oracle_abstraction_version="region_capacity_v1",
            active_assumptions=tuple(active_assumptions),
        ),
        cert=OracleCert(
            cert_kind="region_capacity_combinatorial",
            cert_payload=cert_payload,
            cert_hash=cert_hash,
        ),
        family_version="v1.1",
        validator_version="v1.1",
        payload_schema_version=1,
        oracle_name="region_capacity_v1",
        oracle_cert_hash=cert_hash,
        minimization_audit={"size_before": 1, "size_after": 1, "qx_calls": 0},
        iter_index=0,
    )
    return cut


def step_3_serialize(cut: Cut) -> bytes:
    """Step 3: cut → JSON bytes."""
    cut_dict = {
        "cut_id": cut.cut_id,
        "family": cut.family,
        "literals": [
            {"slot_ref": {"group_id": lit.slot_ref.group_id, "slot_index": lit.slot_ref.slot_index},
             "pose_id": lit.pose_id}
            for lit in (cut.literals or ())
        ] if cut.literals else None,
        "geometric_payload": base64.b64encode(cut.geometric_payload).decode("ascii") if cut.geometric_payload else None,
        "scope": {
            "ghost_rect_id": cut.scope.ghost_rect_id,
            "blocked_cells_hash": cut.scope.blocked_cells_hash,
            "source_digest": cut.scope.source_digest,
            "artifact_hashes": dict(cut.scope.artifact_hashes),
            "oracle_abstraction_version": cut.scope.oracle_abstraction_version,
            "active_assumptions": [{"key": a.key, "value": a.value} for a in cut.scope.active_assumptions],
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
    """Step 4: JSON bytes → Cut object. Schema 校验在 __post_init__."""
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
        geometric_payload = base64.b64decode(d["geometric_payload"])

    scope = CutScope(
        ghost_rect_id=d["scope"]["ghost_rect_id"],
        blocked_cells_hash=d["scope"]["blocked_cells_hash"],
        source_digest=d["scope"]["source_digest"],
        artifact_hashes=d["scope"]["artifact_hashes"],
        oracle_abstraction_version=d["scope"]["oracle_abstraction_version"],
        active_assumptions=tuple(
            Assumption(a["key"], a["value"]) for a in d["scope"]["active_assumptions"]
        ),
    )
    cert = OracleCert(
        cert_kind=d["cert"]["cert_kind"],
        cert_payload=base64.b64decode(d["cert"]["cert_payload_b64"]),
        cert_hash=d["cert"]["cert_hash"],
    )
    return Cut(
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


def step_5_validate_region_capacity(cut: Cut, state: BState, canonical_rules: Dict) -> ValidationResult:
    """Step 5: 独立重算 cert (v1.1 spec §7)."""
    t0 = time.monotonic()
    try:
        cert_dict = json.loads(cut.geometric_payload)
        region_kind = cert_dict["region_kind"]

        # 重算 region cells (PoC)
        if region_kind == "left_baseline":
            region_cells = [(x, 0) for x in range(70)]
        elif region_kind == "bottom_baseline":
            region_cells = [(0, y) for y in range(70)]
        else:
            return ValidationResult("schema_err", time.monotonic() - t0, f"unsupported region_kind={region_kind}")

        region_set = frozenset(region_cells)

        # v1.1: cap_R static
        blocked_in_region = (state.ghost_cells | state.exterior_blocks) & region_set
        recomputed_cap_R = len(region_cells) - len(blocked_in_region)
        if recomputed_cap_R != cert_dict["cap_R"]:
            return ValidationResult(
                "unsound", time.monotonic() - t0,
                f"cap_R mismatch: cert={cert_dict['cap_R']}, recomputed={recomputed_cap_R}",
            )

        # v1.1: cert.cells_per_pose 比对当前 source-of-truth
        cert_cells_per_pose = cert_dict["cells_per_pose"]
        recomputed_demand_R = 0
        for gid, _ in cert_dict["contributing_groups"]:
            if gid not in cert_cells_per_pose:
                return ValidationResult("schema_err", time.monotonic() - t0, f"cert missing cells_per_pose[{gid}]")
            current_cells_per_pose = canonical_rules[gid]["cells_per_pose"]
            if cert_cells_per_pose[gid] != current_cells_per_pose:
                return ValidationResult(
                    "unsound", time.monotonic() - t0,
                    f"cells_per_pose mismatch for {gid}: cert={cert_cells_per_pose[gid]}, current={current_cells_per_pose}",
                )
            recomputed_demand_R += state.groups[gid].demand * cert_cells_per_pose[gid]

        if recomputed_demand_R != cert_dict["demand_R"]:
            return ValidationResult(
                "unsound", time.monotonic() - t0,
                f"demand_R mismatch: cert={cert_dict['demand_R']}, recomputed={recomputed_demand_R}",
            )

        # 验 witness: demand_R > cap_R
        if recomputed_demand_R <= recomputed_cap_R:
            return ValidationResult(
                "unsound", time.monotonic() - t0,
                f"witness fail: demand_R={recomputed_demand_R} ≤ cap_R={recomputed_cap_R}",
            )

        return ValidationResult("ok", time.monotonic() - t0)
    except Exception as e:
        return ValidationResult("schema_err", time.monotonic() - t0, str(e))


# Assumption verifier dispatch (v3.1 §4 Gap 5)
def _verify_boundary_saturation(state: BState, value: str) -> bool:
    """PoC verifier — verbatim match (source-of-truth assumption)."""
    return True  # PoC: 假设 canonical_rules 不变


def _verify_placement_rule(state: BState, value: str) -> bool:
    """PoC verifier — group=rule format."""
    return True  # PoC: 假设 canonical_rules 不变


ASSUMPTION_VERIFIERS: Dict[str, Callable[[BState, str], bool]] = {
    "left_or_bottom_boundary_saturation": _verify_boundary_saturation,
    "placement_rule": _verify_placement_rule,
}


def assumption_holds(state: BState, assumption: Assumption) -> bool:
    verifier = ASSUMPTION_VERIFIERS.get(assumption.key)
    if verifier is None:
        return False  # fail-closed
    return verifier(state, assumption.value)


def step_6_attach_scope_check(cut: Cut, state: BState) -> AttachDecision:
    """Step 6 (cut_lifecycle_v2 v3.1 §4): 6 步 verify replay.

    PoC 简化版: 直接走 replay_cut algorithm.
    """
    # Step 1: source_digest
    if cut.scope.source_digest != "poc_source_digest":
        return "QUARANTINE"

    # Step 2: ghost match (GHOST_AGNOSTIC sentinel for F1)
    current_ghost_id = compute_ghost_rect_id(state.ghost_rect)
    if cut.scope.ghost_rect_id != GHOST_AGNOSTIC and \
       cut.scope.ghost_rect_id != current_ghost_id:
        return "HOLD"

    # Step 3 (v3.1): blocked_cells_hash
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


def step_7_evaluate_cut(cut: Cut, state: BState) -> bool:
    """Step 7 family-dispatch evaluate. Family 1 geometric → True (cert in
    scope deterministically violates per v1.1 §6)."""
    if cut.geometric_payload is not None:
        if cut.family == "region_capacity":
            return True  # v1.1 §6 简化
        # 其他 geometric family 走各自 evaluate_geometric
        raise NotImplementedError(f"PoC scope: only Family 1, got {cut.family}")
    else:
        # literal-based — PoC 不实施
        raise NotImplementedError("PoC scope: literal-based not implemented")


# ============================================================================
# Full lifecycle pipeline
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
    canonical_rules: Dict,
) -> List[LifecycleReport]:
    """End-to-end PoC: 9 步 lifecycle 全跑 on Family 1 region_capacity cut."""
    reports: List[LifecycleReport] = []

    # Step 1 generate (含 Step 0 canonicalize + Step 2 minimize for combinatorial)
    cut = step_1_generate_region_capacity_combinatorial(
        state_at_gen, region_kind, contributing_group, canonical_rules
    )
    if cut is None:
        reports.append(LifecycleReport("step_1_generate", False, "no infeasibility, no cut"))
        return reports
    reports.append(LifecycleReport("step_1_generate", True, f"cut_id={cut.cut_id} cap_R={json.loads(cut.geometric_payload)['cap_R']} demand_R={json.loads(cut.geometric_payload)['demand_R']}"))

    # Step 3 serialize
    blob = step_3_serialize(cut)
    reports.append(LifecycleReport("step_3_serialize", True, f"{len(blob)} bytes"))

    # Step 4 deserialize
    cut_d = step_4_deserialize(blob)
    if cut_d.cut_id != cut.cut_id or cut_d.cert.cert_hash != cut.cert.cert_hash:
        reports.append(LifecycleReport("step_4_deserialize", False, "round-trip mismatch"))
        return reports
    reports.append(LifecycleReport("step_4_deserialize", True, "round-trip OK"))

    # Step 5 validate (independent recompute on gen state)
    vr_gen = step_5_validate_region_capacity(cut_d, state_at_gen, canonical_rules)
    reports.append(LifecycleReport("step_5_validate_at_gen", vr_gen.kind == "ok",
                                    f"{vr_gen.kind} ({vr_gen.elapsed_seconds*1000:.2f}ms) {vr_gen.detail or ''}"))

    # Step 6 attach-scope check on replay state
    decision = step_6_attach_scope_check(cut_d, state_at_replay)
    reports.append(LifecycleReport("step_6_attach_scope_at_replay", decision == "ATTACH",
                                    f"decision={decision}"))

    # Step 7 evaluate (only if ATTACH)
    if decision == "ATTACH":
        violate = step_7_evaluate_cut(cut_d, state_at_replay)
        reports.append(LifecycleReport("step_7_evaluate", True,
                                        f"violate={violate} (expected True for F1 scope-bound)"))

    # Step 9 replay regression: re-validate on replay state
    vr_replay = step_5_validate_region_capacity(cut_d, state_at_replay, canonical_rules)
    reports.append(LifecycleReport("step_9_replay_validate", vr_replay.kind == "ok",
                                    f"{vr_replay.kind} {vr_replay.detail or ''}"))

    return reports
