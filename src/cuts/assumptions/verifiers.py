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

    Validates state.canonical_rules[group]["placement_rule"] == rule.
    Returns False if state.canonical_rules is None (fail-closed) or malformed
    value or rules mismatch.
    """
    rules = getattr(state, "canonical_rules", None)
    if rules is None:
        return False
    kv = _parse_kv_pair(value)
    if kv is None:
        return False
    group, expected_rule = kv
    group_entry = rules.get(group)
    if not isinstance(group_entry, dict):
        return False
    actual_rule = group_entry.get("placement_rule")
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


_VERIFIERS: Dict[str, Verifier] = {
    "placement_rule": verify_placement_rule,
    "left_or_bottom_boundary_saturation": verify_boundary_saturation,
}


def lookup_verifier(key: str) -> Optional[Verifier]:
    """Returns verifier function for assumption key, or None if not registered.

    None → assumption_holds returns False (fail-closed per PROJECT_LOCK §4).
    """
    return _VERIFIERS.get(key)


def register_verifier(key: str, fn: Verifier) -> None:
    """Register a production verifier. Phase 1.1+ family validator 加 key 时调.

    Overwrite 既有 entry (允许 mock 测试). 不允许 None — 注册必非空.
    """
    if fn is None:
        raise ValueError(f"verifier for key={key!r} 不能为 None")
    _VERIFIERS[key] = fn
