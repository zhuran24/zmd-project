"""Diff helpers between two normalized catalog payloads."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from src.interchange.normalized_catalog import normalize_catalog_payload

_SectionSignatureBuilder = Callable[[Mapping[str, Any]], Any]


def build_catalog_diff_report(
    reference_catalog: Mapping[str, Any],
    candidate_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    reference = normalize_catalog_payload(reference_catalog)
    candidate = normalize_catalog_payload(candidate_catalog)

    sections = {
        "items": _diff_named_section(reference["items"], candidate["items"], signature_builder=_item_signature),
        "recipes": _diff_named_section(reference["recipes"], candidate["recipes"], signature_builder=_recipe_signature),
        "facilities": _diff_named_section(reference["facilities"], candidate["facilities"], signature_builder=_facility_signature),
    }

    return {
        "metadata": {
            "reference_source": str(reference["metadata"]["source"]),
            "candidate_source": str(candidate["metadata"]["source"]),
        },
        **sections,
        "power": _diff_power_section(reference["power"], candidate["power"]),
    }


def render_catalog_diff_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Catalog Diff Report",
        "",
        f"- Reference source: `{report['metadata']['reference_source']}`",
        f"- Candidate source: `{report['metadata']['candidate_source']}`",
        "",
    ]

    for section_name in ("items", "recipes", "facilities"):
        section = report[section_name]
        lines.extend(
            [
                f"## {section_name.capitalize()}",
                "",
                f"- Reference count: {section['reference_count']}",
                f"- Candidate count: {section['candidate_count']}",
                f"- Shared count: {section['shared_count']}",
                f"- Shared exact count: {section['shared_exact_count']}",
                f"- Shared mismatched count: {section['shared_mismatched_count']}",
                f"- Shared but different: {', '.join(section['shared_mismatched'][:10]) or '(none)' }",
                f"- Only in reference: {', '.join(section['only_in_reference'][:10]) or '(none)' }",
                f"- Only in candidate: {', '.join(section['only_in_candidate'][:10]) or '(none)' }",
                "",
            ]
        )

    power = report["power"]
    lines.extend(
        [
            "## Power Entries",
            "",
            f"- Reference count: {power['reference_count']}",
            f"- Candidate count: {power['candidate_count']}",
            f"- Shared count: {power['shared_count']}",
            f"- Only in reference: {', '.join(power['only_in_reference'][:10]) or '(none)' }",
            f"- Only in candidate: {', '.join(power['only_in_candidate'][:10]) or '(none)' }",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _diff_named_section(
    reference_entries: Sequence[Mapping[str, Any]],
    candidate_entries: Sequence[Mapping[str, Any]],
    *,
    signature_builder: _SectionSignatureBuilder,
) -> dict[str, Any]:
    reference_lookup = {
        str(entry.get("id", "")): signature_builder(entry)
        for entry in reference_entries
        if str(entry.get("id", ""))
    }
    candidate_lookup = {
        str(entry.get("id", "")): signature_builder(entry)
        for entry in candidate_entries
        if str(entry.get("id", ""))
    }
    reference_ids = set(reference_lookup.keys())
    candidate_ids = set(candidate_lookup.keys())
    shared_ids = reference_ids & candidate_ids
    mismatched = sorted(
        entry_id
        for entry_id in shared_ids
        if reference_lookup[entry_id] != candidate_lookup[entry_id]
    )
    return {
        "reference_count": len(reference_ids),
        "candidate_count": len(candidate_ids),
        "shared_count": len(shared_ids),
        "shared_exact_count": len(shared_ids) - len(mismatched),
        "shared_mismatched_count": len(mismatched),
        "shared_mismatched": mismatched,
        "only_in_reference": sorted(entry_id for entry_id in reference_ids - candidate_ids if entry_id),
        "only_in_candidate": sorted(entry_id for entry_id in candidate_ids - reference_ids if entry_id),
    }


def _item_signature(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(entry.get("id", "")),
        "category": str(entry.get("category", "unknown")),
        "unit": str(entry.get("unit", "item")),
    }


def _recipe_signature(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(entry.get("id", "")),
        "facility_type": str(entry.get("facility_type", "unknown")),
        "cycle_seconds": round(float(entry.get("cycle_seconds", 0.0)), 6),
        "inputs": [
            {
                "item_id": str(flow.get("item_id", "")),
                "amount": round(float(flow.get("amount", 0.0)), 6),
            }
            for flow in entry.get("inputs", [])
        ],
        "outputs": [
            {
                "item_id": str(flow.get("item_id", "")),
                "amount": round(float(flow.get("amount", 0.0)), 6),
            }
            for flow in entry.get("outputs", [])
        ],
    }


def _facility_signature(entry: Mapping[str, Any]) -> dict[str, Any]:
    footprint = entry.get("footprint") if isinstance(entry.get("footprint"), Mapping) else {}
    return {
        "id": str(entry.get("id", "")),
        "footprint": {
            "w": int(footprint.get("w", 1)),
            "h": int(footprint.get("h", 1)),
        },
        "rotatable": bool(entry.get("rotatable", False)),
        "needs_power": bool(entry.get("needs_power", False)),
        "port_rule": str(entry.get("port_rule", "none")),
    }


def _diff_power_section(reference_entries: Sequence[Mapping[str, Any]], candidate_entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    reference_keys = {
        f"{entry.get('facility_id','')}:{entry.get('mode','')}:{round(float(entry.get('value_kw',0.0)), 6)}"
        for entry in reference_entries
    }
    candidate_keys = {
        f"{entry.get('facility_id','')}:{entry.get('mode','')}:{round(float(entry.get('value_kw',0.0)), 6)}"
        for entry in candidate_entries
    }
    shared = reference_keys & candidate_keys
    return {
        "reference_count": len(reference_keys),
        "candidate_count": len(candidate_keys),
        "shared_count": len(shared),
        "only_in_reference": sorted(entry for entry in reference_keys - candidate_keys if entry),
        "only_in_candidate": sorted(entry for entry in candidate_keys - reference_keys if entry),
    }
