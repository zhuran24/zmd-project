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
    """Delegates to the shared SoT helper (single implementation, fail-closed).

    Was a verbatim 4th copy of the canonical pole-radius lookup on the certified
    attach-scope path; consolidated into src/cuts/helpers/canonical_sot.py so this
    verifier cannot diverge from the F7/F8 cut-family validators (v28 fresh-review
    fresh-pass finding). Local import avoids an import cycle (canonical_sot imports
    src.cuts.lifecycle, which transitively reaches the assumptions registry).
    """
    from src.cuts.helpers.canonical_sot import lookup_canonical_pole_radius

    return lookup_canonical_pole_radius(state)


# The F8-only assumption verifiers ("power_pole_jump_radius" and
# "protocol_core_position") were deleted with the power_grid_reach family
# 2026-07-08 — retired on a false game-rule premise (poles need no
# pole-to-pole network). See memory card p1-3-m2-coverage-stencil-ruling.
# Unknown assumption keys stay fail-closed via lookup_verifier() → None.


_VERIFIERS: Dict[str, Verifier] = {
    "placement_rule": verify_placement_rule,
    "left_or_bottom_boundary_saturation": verify_boundary_saturation,
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
