"""Production assumption verifier dispatch (cut_lifecycle_v2 v3.2.2 §4 Gap 5).

Phase 1.0 P1.4 (per Gemini round 27 B1 finding): ASSUMPTION_VERIFIERS 必须真
读 ``state.canonical_rules`` (parsed rules/canonical_rules.json readonly ref)
比对 cert 内 source-of-truth assumption 值. 否则 stub return True 让 cut
silent attach 即便 source rotated — 违 PROJECT_LOCK §4 fail-closed 原则.

API:
- ``lookup_verifier(key)`` → Optional[Callable] (lifecycle.assumption_holds 调)
- ``register_verifier(key, fn)`` — Phase 1.1+ family validator 加新 key 时调

Phase 1.0 P1.4 wired:
- ``placement_rule``: F1/F3/F6/F8/... — group=rule format, 验跟 canonical_rules 一致
- ``left_or_bottom_boundary_saturation``: F1 — boundary saturation static invariant

Phase 1.1+ extends (per cut_family_specs/*):
- ``boundary_pose_shape`` (F2)
- ``boundary_region`` (F2)
- ``power_pole_radius`` (F3/F7)
- ``power_pole_shape`` (F3/F7)
- ``g1_blocks_AB_path`` (F4 state-conditioned)

Refs:
- docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md v3.2.2 §4 Gap 5
- PROJECT_LOCK.md §3A invariant 4 (HOLD vs Quarantine)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, Optional

if TYPE_CHECKING:
    from src.cuts.lifecycle import BState

Verifier = Callable[["BState", str], bool]


def _parse_kv_pair(value: str) -> Optional[tuple[str, str]]:
    """Parse "key=val" string. Returns None on malformed input."""
    parts = value.split("=", 1)
    if len(parts) != 2:
        return None
    k, v = parts[0].strip(), parts[1].strip()
    if not k or not v:
        return None
    return (k, v)


def verify_placement_rule(state: "BState", value: str) -> bool:
    """Assumption "placement_rule": value = "{group}={rule}".

    Gap 8 (Gemini round 30) 修: placement_rule lookup 经
    ``helpers.canonical_rules.placement_rule_for_group(state, group)``,
    **不**直接 query state.canonical_rules.get(group). gid 是 operation_type
    (e.g. "boundary_io"), 不是 canonical_rules 顶层 key.

    Fail-closed: state.facility_templates / instance_to_facility_type None
    → helper 返 "unknown" → verifier False. canonical_rules None 同理.
    """
    kv = _parse_kv_pair(value)
    if kv is None:
        return False
    group, expected_rule = kv

    # Lazy import 避 circular (assumptions ← lifecycle ← helpers ← assumptions)
    from src.cuts.helpers.canonical_rules import placement_rule_for_group
    actual_rule = placement_rule_for_group(state, group)
    if actual_rule == "unknown":
        return False
    return actual_rule == expected_rule


def verify_boundary_saturation(state: "BState", value: str) -> bool:
    """Assumption "left_or_bottom_boundary_saturation": source-of-truth invariant.

    value 是 "left_baseline=23,bottom_baseline=23,demand=46,cells=138" — 表示
    canonical_rules 决定 boundary 上限. Phase 1.0 P1.4 仅校验 state.canonical_rules
    非空 (source 存在) — 真正 saturation 数字校验 P1.21 source_digest 实施时加.

    Fail-closed: canonical_rules None → False (无 source 不可信).
    """
    rules = getattr(state, "canonical_rules", None)
    if rules is None:
        return False
    return True


def _parse_radius_value(value: str) -> Optional[float]:
    """Parse "R=<float>" assumption value. Returns None on malformed / non-positive."""
    kv = _parse_kv_pair(value)
    if kv is None:
        return None
    key, rhs = kv
    if key != "R":
        return None
    try:
        radius = float(rhs)
    except ValueError:
        return None
    if radius <= 0.0:
        return None
    return radius


def _lookup_canonical_pole_radius(state: "BState") -> Optional[float]:
    """Read state.canonical_rules.facility_templates.power_pole.power_coverage_radius.

    Returns None on any missing layer / non-numeric / bool — fail-closed.
    """
    rules = getattr(state, "canonical_rules", None)
    if not isinstance(rules, dict):
        return None
    templates = rules.get("facility_templates")
    if not isinstance(templates, dict):
        return None
    pole_tpl = templates.get("power_pole")
    if not isinstance(pole_tpl, dict):
        return None
    canonical_radius = pole_tpl.get("power_coverage_radius")
    if isinstance(canonical_radius, bool):
        return None
    if not isinstance(canonical_radius, (int, float)):
        return None
    return float(canonical_radius)


def verify_power_pole_jump_radius(state: "BState", value: str) -> bool:
    """Assumption "power_pole_jump_radius": F8 source-of-truth binding.

    value format: "R=<float>". Gemini F8 round 3 Finding #2 (CRITICAL):
    validator cannot trust caller-supplied ``pole_jump_radius`` from the
    cert payload — a malicious prover could forge R=0.001 to fake a BFS
    disconnect. The active_assumption check (attach-scope step 6) re-reads
    canonical_rules and rejects any cert whose radius doesn't match.

    Phase 1.2 single-case: canonical_rules.facility_templates.power_pole
    exposes ``power_coverage_radius`` (pole→facility, 5.0 in real data).
    Phase 1.5+ will introduce a dedicated pole-to-pole jump radius field;
    until then, the simplification "pole-to-pole = power_coverage_radius"
    is documented in spec §1c, and this verifier enforces that link.

    Fail-closed: malformed value / canonical layers missing / mismatch.
    """
    cert_radius = _parse_radius_value(value)
    if cert_radius is None:
        return False
    canonical_radius = _lookup_canonical_pole_radius(state)
    if canonical_radius is None:
        return False
    return canonical_radius == cert_radius


def _parse_position_value(value: str) -> Optional[tuple[int, int]]:
    """Parse "(x,y)" assumption value as (int, int). None on malformed."""
    if not (value.startswith("(") and value.endswith(")")):
        return None
    inner = value[1:-1]
    parts = inner.split(",", 1)
    if len(parts) != 2:
        return None
    try:
        ax = int(parts[0].strip())
        ay = int(parts[1].strip())
    except ValueError:
        return None
    return (ax, ay)


def _protocol_core_footprint_owned(
    state: "BState", anchor: tuple[int, int], pc_size: int
) -> bool:
    """True iff every cell in the 9×9 footprint at ``anchor`` is owned by a
    group mapped to facility_type=protocol_core in state.cell_owner."""
    instance_to_facility_type = state.instance_to_facility_type
    cell_owner = state.cell_owner
    if instance_to_facility_type is None or not cell_owner:
        return False
    for dx in range(pc_size):
        for dy in range(pc_size):
            owner = cell_owner.get((anchor[0] + dx, anchor[1] + dy))
            if owner is None:
                return False
            gid = owner[0] if isinstance(owner, tuple) else owner
            if instance_to_facility_type.get(gid) != "protocol_core":
                return False
    return True


def verify_protocol_core_position(state: "BState", value: str) -> bool:
    """Assumption "protocol_core_position": F8 anchor binding.

    value format: "(<x>,<y>)". Gemini F8 round 3 Finding #2 (CRITICAL):
    cert's ``protocol_core_cell`` must match master_solution. A forged
    anchor (e.g., off-grid corner) can produce an artificially disconnected
    BFS without reflecting any real placement.

    Phase 1.2 single-case (fail-closed):
    - parse "(x,y)" — fail on malformed format
    - bounds: 0 ≤ x, y AND x + 9 ≤ 70 AND y + 9 ≤ 70 (protocol_core is 9×9
      and must fit in the 70×70 grid)
    - cross-check with state: if the canonical 9×9 footprint at (x, y) has
      every cell in ``state.cell_owner`` mapped to (group_id, _) where the
      ``state.instance_to_facility_type[group_id] == "protocol_core"``, the
      anchor is verified. If no such mapping is available (fixture/test
      state without cell_owner), accept the bounds-only check.

    Phase 1.5+: full master-state cross-check unconditional.
    """
    parsed = _parse_position_value(value)
    if parsed is None:
        return False
    ax, ay = parsed
    grid_size = 70
    pc_size = 9
    if ax < 0 or ay < 0 or ax + pc_size > grid_size or ay + pc_size > grid_size:
        return False
    # If no master placement info, bounds-only is the Phase 1.2 contract.
    if state.instance_to_facility_type is None or not state.cell_owner:
        return True
    return _protocol_core_footprint_owned(state, (ax, ay), pc_size)


_VERIFIERS: Dict[str, Verifier] = {
    "placement_rule": verify_placement_rule,
    "left_or_bottom_boundary_saturation": verify_boundary_saturation,
    "power_pole_jump_radius": verify_power_pole_jump_radius,
    "protocol_core_position": verify_protocol_core_position,
}


def lookup_verifier(key: str) -> Optional[Verifier]:
    """Returns verifier function for assumption key, or None if not registered.

    None → assumption_holds returns False (fail-closed per PROJECT_LOCK §4).
    """
    return _VERIFIERS.get(key)


def register_verifier(key: str, fn: Verifier, *, overwrite: bool = False) -> None:
    """Register a production verifier. Phase 1.1+ family validator 加 key 时调.

    fn 不允许 None — 注册必非空.

    Gemini round 28 finding #2: 拒 silent overwrite — 防 P1.5+ 不同 family
    碰巧注册同名 key (e.g. F2 + F4 都用 boundary_shape) 静默替换. 显式
    ``overwrite=True`` 走覆盖路径 (mock 测试 / spec 迭代时用).
    """
    if fn is None:
        raise ValueError(f"verifier for key={key!r} 不能为 None")
    if key in _VERIFIERS and not overwrite:
        raise ValueError(
            f"verifier for key={key!r} 已 registered; "
            f"pass overwrite=True 显式 (Gemini round 28 finding #2 fail-closed)"
        )
    _VERIFIERS[key] = fn
