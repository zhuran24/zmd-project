"""Exact recipe-equivalence matching for the IndustrialPlanner adapter.

This module builds a static signature for every canonical recipe in the current
repository slice and compares it against IndustrialPlanner's checked-in target
recipe registry. The matcher is intentionally strict: it only proves an
`exact_match` when machine family, cycle time, translated input multiset, and
translated output multiset all match exactly and uniquely.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.adapters.endfield_calc.semantic_mapping import (
    SemanticRegistry,
    current_repository_semantic_registry,
)
from src.adapters.industrial_planner.commodity_resolver import (
    canonical_rules_payload,
    translate_canonical_item_id,
)

_ITEM_REGISTRY_PATH = Path(__file__).resolve().parent / "item_registry.json"


@dataclass(frozen=True)
class CanonicalRecipeSignature:
    canonical_recipe_id: str
    canonical_facility_type: str
    expected_machine_type: str | None
    cycle_seconds: Fraction | None
    translated_inputs: tuple[tuple[str, Fraction], ...]
    translated_outputs: tuple[tuple[str, Fraction], ...]
    warnings: tuple[str, ...] = ()
    translation_failed: bool = False


@dataclass(frozen=True)
class TargetRecipeSignature:
    target_recipe_id: str
    machine_type: str | None
    cycle_seconds: Fraction | None
    inputs: tuple[tuple[str, Fraction], ...]
    outputs: tuple[tuple[str, Fraction], ...]


@dataclass(frozen=True)
class TargetRecipeMatch:
    canonical_recipe_id: str
    status: str
    expected_machine_type: str | None
    expected_cycle_seconds: str | None
    matched_target_recipe_id: str | None
    matched_machine_type: str | None
    warnings: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def load_item_registry_payload() -> dict[str, Any]:
    return json.loads(_ITEM_REGISTRY_PATH.read_text(encoding="utf-8"))


def build_canonical_recipe_signatures(
    *,
    canonical_rules: Mapping[str, Any] | None = None,
    semantic_registry: SemanticRegistry | None = None,
) -> dict[str, CanonicalRecipeSignature]:
    rules_payload = canonical_rules or canonical_rules_payload()
    semantic_registry = semantic_registry or current_repository_semantic_registry()
    recipe_rules = rules_payload.get("recipes") if isinstance(rules_payload.get("recipes"), Mapping) else {}
    globals_payload = rules_payload.get("globals") if isinstance(rules_payload.get("globals"), Mapping) else {}
    time_payload = globals_payload.get("time") if isinstance(globals_payload.get("time"), Mapping) else {}
    tick_interval_seconds = _to_fraction(time_payload.get("tick_interval_seconds", 1))
    recipe_mapping_by_id = {
        mapping.canonical_id: mapping
        for mapping in semantic_registry.recipe_mappings
    }

    signatures: dict[str, CanonicalRecipeSignature] = {}
    for canonical_recipe_id, raw_recipe in sorted(recipe_rules.items()):
        if not isinstance(raw_recipe, Mapping):
            continue
        mapping = recipe_mapping_by_id.get(canonical_recipe_id)
        warnings: list[str] = []
        expected_machine_type = mapping.upstream_facility_id if mapping is not None else None
        if mapping is None:
            warnings.append(
                f"no semantic recipe mapping is registered for canonical recipe {canonical_recipe_id!r}"
            )

        cycle_seconds: Fraction | None = None
        try:
            cycle_seconds = _to_fraction(raw_recipe.get("ticks_per_cycle", 0)) * tick_interval_seconds
        except Exception as exc:  # pragma: no cover - defensive only.
            warnings.append(
                f"failed to derive cycleSeconds for canonical recipe {canonical_recipe_id!r}: {exc}"
            )

        translated_inputs, input_warnings, input_failed = _translate_canonical_io_mapping(
            raw_recipe.get("inputs"),
            semantic_registry=semantic_registry,
            context=f"canonical recipe {canonical_recipe_id} inputs",
        )
        translated_outputs, output_warnings, output_failed = _translate_canonical_io_mapping(
            raw_recipe.get("outputs"),
            semantic_registry=semantic_registry,
            context=f"canonical recipe {canonical_recipe_id} outputs",
        )
        warnings.extend(input_warnings)
        warnings.extend(output_warnings)

        signatures[str(canonical_recipe_id)] = CanonicalRecipeSignature(
            canonical_recipe_id=str(canonical_recipe_id),
            canonical_facility_type=str(raw_recipe.get("template", mapping.canonical_facility_type if mapping else "")),
            expected_machine_type=expected_machine_type,
            cycle_seconds=cycle_seconds,
            translated_inputs=translated_inputs,
            translated_outputs=translated_outputs,
            warnings=tuple(sorted(set(warnings))),
            translation_failed=bool(input_failed or output_failed),
        )
    return signatures


def build_target_recipe_signatures(
    *,
    item_registry_payload: Mapping[str, Any] | None = None,
) -> tuple[TargetRecipeSignature, ...]:
    payload = item_registry_payload or load_item_registry_payload()
    raw_recipes = payload.get("recipes") if isinstance(payload.get("recipes"), Sequence) else ()
    signatures: list[TargetRecipeSignature] = []
    for raw_recipe in raw_recipes:
        if not isinstance(raw_recipe, Mapping):
            continue
        signatures.append(
            TargetRecipeSignature(
                target_recipe_id=str(raw_recipe.get("id", "")).strip(),
                machine_type=_optional_string(raw_recipe.get("machineType")),
                cycle_seconds=_optional_fraction(raw_recipe.get("cycleSeconds")),
                inputs=_normalize_target_io_entries(raw_recipe.get("inputs")),
                outputs=_normalize_target_io_entries(raw_recipe.get("outputs")),
            )
        )
    signatures.sort(key=lambda entry: entry.target_recipe_id)
    return tuple(signatures)


def match_canonical_recipe_to_target(
    canonical_signature: CanonicalRecipeSignature,
    *,
    target_signatures: Sequence[TargetRecipeSignature],
) -> TargetRecipeMatch:
    expected_cycle_seconds = _fraction_to_str(canonical_signature.cycle_seconds)
    if canonical_signature.translation_failed:
        return TargetRecipeMatch(
            canonical_recipe_id=canonical_signature.canonical_recipe_id,
            status="translation_failure",
            expected_machine_type=canonical_signature.expected_machine_type,
            expected_cycle_seconds=expected_cycle_seconds,
            matched_target_recipe_id=None,
            matched_machine_type=None,
            warnings=canonical_signature.warnings,
        )

    exact_matches = [
        candidate
        for candidate in target_signatures
        if candidate.machine_type == canonical_signature.expected_machine_type
        and candidate.cycle_seconds == canonical_signature.cycle_seconds
        and candidate.inputs == canonical_signature.translated_inputs
        and candidate.outputs == canonical_signature.translated_outputs
    ]
    if len(exact_matches) == 1:
        candidate = exact_matches[0]
        return TargetRecipeMatch(
            canonical_recipe_id=canonical_signature.canonical_recipe_id,
            status="exact_match",
            expected_machine_type=canonical_signature.expected_machine_type,
            expected_cycle_seconds=expected_cycle_seconds,
            matched_target_recipe_id=candidate.target_recipe_id,
            matched_machine_type=candidate.machine_type,
            warnings=canonical_signature.warnings,
        )
    if len(exact_matches) > 1:
        candidate_ids = ", ".join(sorted(candidate.target_recipe_id for candidate in exact_matches))
        return TargetRecipeMatch(
            canonical_recipe_id=canonical_signature.canonical_recipe_id,
            status="ambiguous",
            expected_machine_type=canonical_signature.expected_machine_type,
            expected_cycle_seconds=expected_cycle_seconds,
            matched_target_recipe_id=None,
            matched_machine_type=canonical_signature.expected_machine_type,
            warnings=tuple(sorted(set((*canonical_signature.warnings, f"multiple exact target recipes matched: {candidate_ids}")))),
        )

    machine_family_matches = [
        candidate
        for candidate in target_signatures
        if candidate.cycle_seconds == canonical_signature.cycle_seconds
        and candidate.inputs == canonical_signature.translated_inputs
        and candidate.outputs == canonical_signature.translated_outputs
    ]
    if len(machine_family_matches) == 1:
        candidate = machine_family_matches[0]
        return TargetRecipeMatch(
            canonical_recipe_id=canonical_signature.canonical_recipe_id,
            status="machine_family_mismatch",
            expected_machine_type=canonical_signature.expected_machine_type,
            expected_cycle_seconds=expected_cycle_seconds,
            matched_target_recipe_id=candidate.target_recipe_id,
            matched_machine_type=candidate.machine_type,
            warnings=tuple(sorted(set((*canonical_signature.warnings, "machine family did not match even though cycle and I/O matched exactly")))),
        )

    cycle_matches = [
        candidate
        for candidate in target_signatures
        if candidate.machine_type == canonical_signature.expected_machine_type
        and candidate.inputs == canonical_signature.translated_inputs
        and candidate.outputs == canonical_signature.translated_outputs
    ]
    if len(cycle_matches) == 1:
        candidate = cycle_matches[0]
        return TargetRecipeMatch(
            canonical_recipe_id=canonical_signature.canonical_recipe_id,
            status="cycle_mismatch",
            expected_machine_type=canonical_signature.expected_machine_type,
            expected_cycle_seconds=expected_cycle_seconds,
            matched_target_recipe_id=candidate.target_recipe_id,
            matched_machine_type=candidate.machine_type,
            warnings=tuple(sorted(set((*canonical_signature.warnings, "cycleSeconds did not match even though machine family and I/O matched exactly")))),
        )

    canonical_input_item_ids = frozenset(item_id for item_id, _ in canonical_signature.translated_inputs)
    canonical_output_item_ids = frozenset(item_id for item_id, _ in canonical_signature.translated_outputs)
    io_matches = [
        candidate
        for candidate in target_signatures
        if candidate.machine_type == canonical_signature.expected_machine_type
        and candidate.cycle_seconds == canonical_signature.cycle_seconds
        and frozenset(item_id for item_id, _ in candidate.inputs) == canonical_input_item_ids
        and frozenset(item_id for item_id, _ in candidate.outputs) == canonical_output_item_ids
    ]
    if len(io_matches) == 1:
        candidate = io_matches[0]
        return TargetRecipeMatch(
            canonical_recipe_id=canonical_signature.canonical_recipe_id,
            status="io_mismatch",
            expected_machine_type=canonical_signature.expected_machine_type,
            expected_cycle_seconds=expected_cycle_seconds,
            matched_target_recipe_id=candidate.target_recipe_id,
            matched_machine_type=candidate.machine_type,
            warnings=tuple(sorted(set((*canonical_signature.warnings, "input/output multiset did not match even though machine family and cycleSeconds matched")))),
        )

    io_matches = [
        candidate
        for candidate in target_signatures
        if candidate.machine_type == canonical_signature.expected_machine_type
        and candidate.cycle_seconds == canonical_signature.cycle_seconds
    ]
    if len(io_matches) == 1:
        candidate = io_matches[0]
        return TargetRecipeMatch(
            canonical_recipe_id=canonical_signature.canonical_recipe_id,
            status="io_mismatch",
            expected_machine_type=canonical_signature.expected_machine_type,
            expected_cycle_seconds=expected_cycle_seconds,
            matched_target_recipe_id=candidate.target_recipe_id,
            matched_machine_type=candidate.machine_type,
            warnings=tuple(sorted(set((*canonical_signature.warnings, "input/output multiset did not match even though machine family and cycleSeconds matched")))),
        )

    warnings = list(canonical_signature.warnings)
    if canonical_signature.expected_machine_type is None:
        warnings.append("no expected target machine family was available for exact matching")
    else:
        warnings.append("no target recipe matched the expected machine family / cycle / I/O signature exactly")
    return TargetRecipeMatch(
        canonical_recipe_id=canonical_signature.canonical_recipe_id,
        status="no_match",
        expected_machine_type=canonical_signature.expected_machine_type,
        expected_cycle_seconds=expected_cycle_seconds,
        matched_target_recipe_id=None,
        matched_machine_type=None,
        warnings=tuple(sorted(set(warnings))),
    )


def build_recipe_match_index(
    *,
    canonical_rules: Mapping[str, Any] | None = None,
    item_registry_payload: Mapping[str, Any] | None = None,
    semantic_registry: SemanticRegistry | None = None,
) -> dict[str, TargetRecipeMatch]:
    canonical_signatures = build_canonical_recipe_signatures(
        canonical_rules=canonical_rules,
        semantic_registry=semantic_registry,
    )
    target_signatures = build_target_recipe_signatures(item_registry_payload=item_registry_payload)
    return {
        recipe_id: match_canonical_recipe_to_target(signature, target_signatures=target_signatures)
        for recipe_id, signature in sorted(canonical_signatures.items())
    }


def build_canonical_recipe_match_index(
    *,
    canonical_rules: Mapping[str, Any] | None = None,
    item_registry_payload: Mapping[str, Any] | None = None,
    semantic_registry: SemanticRegistry | None = None,
) -> dict[str, TargetRecipeMatch]:
    return build_recipe_match_index(
        canonical_rules=canonical_rules,
        item_registry_payload=item_registry_payload,
        semantic_registry=semantic_registry,
    )


def _translate_canonical_io_mapping(
    raw_mapping: Any,
    *,
    semantic_registry: SemanticRegistry,
    context: str,
) -> tuple[tuple[tuple[str, Fraction], ...], tuple[str, ...], bool]:
    normalized = raw_mapping if isinstance(raw_mapping, Mapping) else {}
    totals: defaultdict[str, Fraction] = defaultdict(Fraction)
    warnings: list[str] = []
    translation_failed = False
    for raw_item_id, raw_amount in sorted(normalized.items()):
        translation = translate_canonical_item_id(
            raw_item_id,
            semantic_registry=semantic_registry,
            allow_upstream_passthrough=True,
        )
        warnings.extend(translation.warnings)
        if translation.translated_item_id is None:
            translation_failed = True
            warnings.append(
                f"{context}: commodity {raw_item_id!r} could not be translated into the IndustrialPlanner item namespace"
            )
            continue
        totals[translation.translated_item_id] += _to_fraction(raw_amount)
    return (
        tuple(sorted((item_id, amount) for item_id, amount in totals.items())),
        tuple(sorted(set(warnings))),
        translation_failed,
    )


def _normalize_target_io_entries(raw_entries: Any) -> tuple[tuple[str, Fraction], ...]:
    if not isinstance(raw_entries, Sequence):
        return ()
    totals: defaultdict[str, Fraction] = defaultdict(Fraction)
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping):
            continue
        item_id = str(raw_entry.get("itemId", "")).strip()
        if not item_id:
            continue
        totals[item_id] += _to_fraction(raw_entry.get("amount", 0))
    return tuple(sorted((item_id, amount) for item_id, amount in totals.items()))


def _optional_fraction(value: Any) -> Fraction | None:
    if value is None or value == "":
        return None
    return _to_fraction(value)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _to_fraction(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise TypeError("boolean values are not valid Fraction inputs")
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        return Fraction(str(value))
    if isinstance(value, str):
        return Fraction(value)
    return Fraction(str(value))


def _fraction_to_str(value: Fraction | None) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "CanonicalRecipeSignature",
    "TargetRecipeMatch",
    "TargetRecipeSignature",
    "build_canonical_recipe_match_index",
    "build_canonical_recipe_signatures",
    "build_recipe_match_index",
    "build_target_recipe_signatures",
    "load_item_registry_payload",
    "match_canonical_recipe_to_target",
]
