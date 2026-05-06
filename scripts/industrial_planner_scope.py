"""Shared scope metadata for the active IndustrialPlanner checked-artifact contract."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from src.adapters.industrial_planner.blueprint_validator import load_static_registries

ACTIVE_FULL_DEMAND_BASE_IDS: tuple[str, ...] = ("valley4_protocol_core",)

_SCOPE_STATEMENT = (
    "The current certified IndustrialPlanner support contract is intentionally narrowed to "
    "`valley4_protocol_core` (70×70) only. Other known bases are preserved as `future_scope` "
    "for later work and are excluded from the active audit / CI gate."
)

_FUTURE_SCOPE_BASE_REASONS: dict[str, str] = {
    "valley4_infra_outpost": "40×40 valley4 sub-base reserved for a separate future plan.",
    "valley4_rebuilt_command": "40×40 valley4 sub-base reserved for a separate future plan.",
    "valley4_refugee_shelter": "40×40 valley4 sub-base reserved for a separate future plan.",
    "wuling_tianwangping_aid": "50×50 wuling aid base reserved for a separate future plan.",
    "wuling_protocol_core": "80×80 wuling protocol-core base belongs to a different region/production system and stays future-scope.",
}

_FUTURE_SCOPE_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "group_id": "valley4_40x40_subbases",
        "label": "valley4 40×40 sub-bases",
        "base_ids": (
            "valley4_infra_outpost",
            "valley4_rebuilt_command",
            "valley4_refugee_shelter",
        ),
        "summary_note": (
            "These three 40×40 valley4 sub-bases share the same current contract status, so the active reports collapse them into one preserved future-scope group."
        ),
    },
    {
        "group_id": "wuling_50x50_aid_base",
        "label": "wuling 50×50 aid base",
        "base_ids": ("wuling_tianwangping_aid",),
        "summary_note": "Smaller wuling aid base retained as future-scope only.",
    },
    {
        "group_id": "wuling_80x80_protocol_core",
        "label": "wuling 80×80 protocol core",
        "base_ids": ("wuling_protocol_core",),
        "summary_note": "Larger wuling protocol-core outer-deployment work is frozen as future-scope.",
    },
)


def iter_known_base_ids() -> tuple[str, ...]:
    registries = load_static_registries()
    return tuple(str(base_id) for base_id in registries.base_by_id.keys())


def default_active_base_ids() -> tuple[str, ...]:
    known = set(iter_known_base_ids())
    missing = [base_id for base_id in ACTIVE_FULL_DEMAND_BASE_IDS if base_id not in known]
    if missing:
        raise ValueError(
            "active IndustrialPlanner contract references unknown base ids: " + ", ".join(missing)
        )
    return ACTIVE_FULL_DEMAND_BASE_IDS


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = str(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _future_scope_base_records(base_ids: Sequence[str]) -> tuple[dict[str, Any], ...]:
    registries = load_static_registries()
    records: list[dict[str, Any]] = []
    for base_id in _ordered_unique(base_ids):
        base_def = registries.base_by_id.get(base_id, {})
        tags = tuple(str(tag) for tag in base_def.get("tags", []) if str(tag).strip())
        records.append(
            {
                "base_id": base_id,
                "name": str(base_def.get("name", "") or base_id),
                "placeable_size": int(base_def.get("placeableSize", 0) or 0),
                "tags": list(tags),
                "scope_status": "future_scope",
                "reason": _FUTURE_SCOPE_BASE_REASONS.get(
                    base_id,
                    "Preserved future-scope base outside the active 70×70 single-base contract.",
                ),
            }
        )
    return tuple(records)


def _future_scope_group_records(base_ids: Sequence[str]) -> tuple[dict[str, Any], ...]:
    requested = set(str(base_id) for base_id in base_ids)
    base_lookup = {record["base_id"]: record for record in _future_scope_base_records(tuple(requested))}
    groups: list[dict[str, Any]] = []
    for raw_group in _FUTURE_SCOPE_GROUPS:
        member_ids = tuple(base_id for base_id in raw_group["base_ids"] if base_id in requested)
        if not member_ids:
            continue
        placeable_sizes = tuple(
            sorted(
                {
                    int(base_lookup[base_id]["placeable_size"])
                    for base_id in member_ids
                    if base_id in base_lookup
                }
            )
        )
        groups.append(
            {
                "group_id": str(raw_group["group_id"]),
                "label": str(raw_group["label"]),
                "base_ids": list(member_ids),
                "count": len(member_ids),
                "placeable_sizes": list(placeable_sizes),
                "summary_note": str(raw_group["summary_note"]),
            }
        )
    return tuple(groups)


def build_scope_metadata(
    *,
    audited_base_ids: Sequence[str],
    include_future_scope: bool,
) -> dict[str, Any]:
    audited_ids = _ordered_unique(str(base_id) for base_id in audited_base_ids)
    active_contract_ids = default_active_base_ids()
    future_scope_ids = ()
    future_scope_bases: tuple[dict[str, Any], ...] = ()
    future_scope_groups: tuple[dict[str, Any], ...] = ()
    if include_future_scope:
        known_ids = iter_known_base_ids()
        future_scope_ids = tuple(base_id for base_id in known_ids if base_id not in audited_ids)
        future_scope_bases = _future_scope_base_records(future_scope_ids)
        future_scope_groups = _future_scope_group_records(future_scope_ids)
    return {
        "scope_mode": "default_contract_scope" if include_future_scope else "explicit_subset",
        "scope_statement": _SCOPE_STATEMENT,
        "active_contract_base_ids": list(active_contract_ids),
        "audited_base_ids": list(audited_ids),
        "known_base_count": len(iter_known_base_ids()),
        "future_scope_base_count": len(future_scope_ids),
        "future_scope_base_ids": list(future_scope_ids),
        "future_scope_base_groups": list(future_scope_groups),
        "future_scope_bases": list(future_scope_bases),
    }
