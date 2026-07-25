#!/usr/bin/env python3
"""Fail-closed agreement gate for the two independent B1 recomputations."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
EXPECTED_METRICS = {
    "total_pattern_placements": 203_340_800,
    "baseline_survivors": 165_541_238,
    "refined_survivors": 165_541_100,
    "incremental_pruned": 138,
    "baseline_oriented_dimensions": 2_151,
    "refined_oriented_dimensions": 2_127,
    "side_70_dimensions_removed": 24,
}
EXPECTED_CLASS_TABLE = (
    (3, 1, 155),
    (3, 2, 12),
    (3, 3, 11),
    (5, 1, 32),
    (5, 2, 17),
    (6, 3, 32),
    (6, 4, 3),
    (6, 5, 3),
)
SCRIPT_ROOT = Path(__file__).resolve().parent
COORDINATE_SCRIPT = SCRIPT_ROOT / "verify_b1_q_membrane_halo_v1.py"
INDEPENDENT_SCRIPT = SCRIPT_ROOT / "recompute_b1_q_membrane_halo_independent_v1.py"


class AgreementError(ValueError):
    """A report is malformed or the independent computations disagree."""


def _reject_constant(value: str) -> Any:
    raise AgreementError(f"non-finite JSON number is forbidden: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AgreementError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AgreementError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AgreementError(f"{path} root must be an object")
    return value, hashlib.sha256(raw).hexdigest()


def _map(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AgreementError(f"{field} must be an object")
    return value


def _seq(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise AgreementError(f"{field} must be an array")
    return value


def _int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise AgreementError(f"{field} must be an exact integer")
    return int(value)


def _pair(value: Any, field: str) -> tuple[int, int]:
    items = _seq(value, field)
    if len(items) != 2:
        raise AgreementError(f"{field} must contain two integers")
    return _int(items[0], f"{field}[0]"), _int(items[1], f"{field}[1]")


def _coordinate_metrics(root: Mapping[str, Any]) -> dict[str, int]:
    metrics = _map(root.get("metrics"), "coordinate.metrics")
    return {
        "total_pattern_placements": _int(metrics.get("pattern_placement_corpus"), "pattern_placement_corpus"),
        "baseline_survivors": _int(metrics.get("baseline_surviving_placements"), "baseline survivors"),
        "refined_survivors": _int(metrics.get("refined_surviving_placements"), "refined survivors"),
        "incremental_pruned": _int(metrics.get("incremental_pruned_placements"), "incremental pruned"),
        "baseline_oriented_dimensions": _int(metrics.get("old_oriented_dimensions"), "old dimensions"),
        "refined_oriented_dimensions": _int(metrics.get("surviving_oriented_dimensions"), "surviving dimensions"),
        "side_70_dimensions_removed": _int(metrics.get("side_70_dimensions_removed"), "side-70 dimensions"),
    }


def _independent_metrics(root: Mapping[str, Any]) -> dict[str, int]:
    metrics = _map(root.get("metrics"), "independent.metrics")
    names = {
        "total_pattern_placements": "total_pattern_placements",
        "baseline_survivors": "baseline_survivors",
        "refined_survivors": "refined_survivors",
        "incremental_pruned": "incremental_pruned",
        "baseline_oriented_dimensions": "baseline_surviving_oriented_dimensions",
        "refined_oriented_dimensions": "refined_surviving_oriented_dimensions",
        "side_70_dimensions_removed": "baseline_side_70_dimensions_removed",
    }
    return {common: _int(metrics.get(source), f"independent.metrics.{source}") for common, source in names.items()}


def _coordinate_classes(root: Mapping[str, Any]) -> tuple[tuple[int, int, int], ...]:
    ledger = _map(root.get("ledger"), "coordinate.ledger")
    records = _seq(ledger.get("class_table"), "coordinate.class_table")
    return tuple(
        sorted(
            (
                _int(_map(item, "coordinate.class").get("span"), "span"),
                _int(_map(item, "coordinate.class").get("maximum"), "maximum"),
                _int(_map(item, "coordinate.class").get("count"), "count"),
            )
            for item in records
        )
    )


def _independent_classes(root: Mapping[str, Any]) -> tuple[tuple[int, int, int], ...]:
    ledger = _map(root.get("strict_ledger"), "independent.strict_ledger")
    records = _seq(ledger.get("class_table"), "independent.class_table")
    return tuple(
        sorted(
            (
                _int(_map(item, "independent.class").get("side"), "side"),
                _int(
                    _map(item, "independent.class").get("active_allowance"),
                    "active_allowance",
                ),
                _int(_map(item, "independent.class").get("count"), "count"),
            )
            for item in records
        )
    )


def _prunes(root: Mapping[str, Any], *, independent: bool) -> dict[tuple[int, int], int]:
    records = _seq(root.get("incremental_prunes"), "incremental_prunes")
    result: dict[tuple[int, int], int] = {}
    key = "pruned_pattern_placements" if independent else "pruned"
    for raw in records:
        item = _map(raw, "incremental_prunes[]")
        dimension = (
            _int(item.get("width"), "width"),
            _int(item.get("height"), "height"),
        )
        if dimension in result:
            raise AgreementError(f"duplicate prune dimension: {dimension}")
        result[dimension] = _int(item.get(key), key)
    return result


def _ceiling(root: Mapping[str, Any], *, independent: bool) -> dict[tuple[int, int], int]:
    if independent:
        ceiling = _map(root.get("ceiling"), "independent.ceiling")
        records = _seq(ceiling.get("dimensions"), "independent.ceiling.dimensions")
        return {
            (
                _int(_map(raw, "ceiling dimension").get("width"), "width"),
                _int(_map(raw, "ceiling dimension").get("height"), "height"),
            ): _int(
                _map(raw, "ceiling dimension").get("refined_pattern_placements"),
                "refined_pattern_placements",
            )
            for raw in records
        }
    ceiling = _map(root.get("ceiling_band"), "coordinate.ceiling_band")
    result: dict[tuple[int, int], int] = {}
    for name, raw in ceiling.items():
        parts = name.split("x")
        if len(parts) != 2 or not all(part.isdecimal() for part in parts):
            raise AgreementError(f"invalid ceiling dimension key: {name!r}")
        result[(int(parts[0]), int(parts[1]))] = _int(_map(raw, f"ceiling_band.{name}").get("surviving"), "surviving")
    return result


def _claim_checks(coordinate: Mapping[str, Any], independent: Mapping[str, Any]) -> None:
    claim = _map(coordinate.get("claim_boundary"), "coordinate.claim_boundary")
    expected = {
        "upper_ledger_only": True,
        "new_upper_bound": False,
        "witness": "absent_and_unrelated",
        "attainability": False,
        "global_optimality": False,
        "production_certified": False,
    }
    if dict(claim) != expected:
        raise AgreementError(f"coordinate claim boundary drift: {claim}")
    scope = _map(independent.get("claim_scope"), "independent.claim_scope")
    if scope.get("kind") != "necessary_condition_recomputation_only":
        raise AgreementError("independent claim kind drift")
    exclusions = set(_seq(scope.get("does_not_prove"), "claim_scope.does_not_prove"))
    required = {
        "witness",
        "attainability",
        "routing_feasibility",
        "global_optimality",
        "production_CERTIFIED_status",
    }
    if exclusions != required:
        raise AgreementError(f"independent claim exclusions drift: {exclusions}")


def compare(coordinate_path: Path, independent_path: Path) -> dict[str, Any]:
    coordinate, coordinate_sha = _load(coordinate_path)
    independent, independent_sha = _load(independent_path)
    if coordinate.get("status") != "PASS" or independent.get("status") != "PASS":
        raise AgreementError("both input reports must have status PASS")

    coordinate_metrics = _coordinate_metrics(coordinate)
    independent_metrics = _independent_metrics(independent)
    if coordinate_metrics != independent_metrics or coordinate_metrics != EXPECTED_METRICS:
        raise AgreementError(f"metric disagreement: {coordinate_metrics} != {independent_metrics}")

    coordinate_classes = _coordinate_classes(coordinate)
    independent_classes = _independent_classes(independent)
    if coordinate_classes != independent_classes or coordinate_classes != EXPECTED_CLASS_TABLE:
        raise AgreementError("class-table disagreement")

    coordinate_provenance = _map(coordinate.get("provenance"), "coordinate.provenance")
    strict_sha = _map(coordinate.get("strict_instance"), "coordinate.strict_instance").get("sha256")
    provenance = _map(independent.get("provenance"), "independent.provenance")
    coordinate_script_sha = hashlib.sha256(COORDINATE_SCRIPT.read_bytes()).hexdigest()
    independent_script_sha = hashlib.sha256(INDEPENDENT_SCRIPT.read_bytes()).hexdigest()
    if (
        strict_sha != EXPECTED_STRICT_SHA256
        or provenance.get("strict_instance_sha256") != EXPECTED_STRICT_SHA256
        or provenance.get("imports_primary_recompute_or_encoder") is not False
        or coordinate_provenance.get("imports_independent_recompute_or_encoder") is not False
        or coordinate_provenance.get("script_sha256") != coordinate_script_sha
        or provenance.get("script_sha256") != independent_script_sha
    ):
        raise AgreementError("strict provenance or independence marker drift")

    coordinate_frontier = _map(coordinate.get("frontier"), "coordinate.frontier")
    independent_frontier = _map(independent.get("frontier"), "independent.frontier")
    objective = _pair(coordinate_frontier.get("objective"), "coordinate objective")
    if objective != (1190, 34):
        raise AgreementError(f"coordinate frontier drift: {objective}")
    if (
        _pair(independent_frontier.get("old_upper"), "old_upper") != objective
        or _pair(independent_frontier.get("new_upper"), "new_upper") != objective
    ):
        raise AgreementError("frontier disagreement")

    dimensions = {
        _pair(item, "oriented_dimensions[]")
        for item in _seq(coordinate_frontier.get("oriented_dimensions"), "oriented_dimensions")
    }
    if dimensions != {(34, 35), (35, 34)}:
        raise AgreementError(f"ceiling dimensions drift: {dimensions}")
    coordinate_ceiling = _ceiling(coordinate, independent=False)
    independent_ceiling = _ceiling(independent, independent=True)
    if coordinate_ceiling != independent_ceiling or coordinate_ceiling != {
        (34, 35): 59_173,
        (35, 34): 59_173,
    }:
        raise AgreementError("ceiling-band disagreement")

    coordinate_prunes = _prunes(coordinate, independent=False)
    independent_prunes = _prunes(independent, independent=True)
    expected_prunes = {(34, 35): 47, (35, 34): 47, (29, 41): 22, (41, 29): 22}
    if coordinate_prunes != independent_prunes or coordinate_prunes != expected_prunes:
        raise AgreementError("incremental-prune disagreement")

    coordinate_ledger = _map(coordinate.get("ledger"), "coordinate.ledger")
    coordinate_halo = _map(coordinate_ledger.get("halo"), "coordinate.ledger.halo")
    independent_halo = _map(independent.get("halo"), "independent.halo")
    halo_common = {
        "orbit_count": 14,
        "total_weight": 396,
        "placement_count": 840,
        "powered_area": 3325,
        "minimum_poles": 9,
    }
    observed_coordinate_halo = {
        name: _int(coordinate_halo.get(name), f"coordinate.halo.{name}") for name in halo_common
    }
    observed_independent_halo = {
        "orbit_count": _int(independent_halo.get("orbit_count"), "orbit_count"),
        "total_weight": _int(independent_halo.get("total_weight"), "total_weight"),
        "placement_count": _int(independent_halo.get("placement_total"), "placement_total"),
        "powered_area": _int(independent_halo.get("powered_area"), "powered_area"),
        "minimum_poles": _int(independent_halo.get("pole_lower_bound"), "pole_lower_bound"),
    }
    if observed_coordinate_halo != halo_common or observed_independent_halo != halo_common:
        raise AgreementError("halo recomputation disagreement")

    expected_saturation = {
        "required_outputs": 52,
        "boundary_capacity": 46,
        "protocol_core_capacity": 6,
        "identity": "52 = 46 * 1 + 6",
    }
    coordinate_saturation = _map(
        coordinate_ledger.get("raw_provider_saturation"),
        "coordinate.raw_provider_saturation",
    )
    independent_ledger = _map(independent.get("strict_ledger"), "independent.strict_ledger")
    independent_saturation = _map(
        independent_ledger.get("raw_provider_saturation"),
        "independent.raw_provider_saturation",
    )
    if dict(coordinate_saturation) != expected_saturation or dict(independent_saturation) != expected_saturation:
        raise AgreementError("raw-provider saturation disagreement")

    boundary = _map(coordinate.get("boundary_patterns"), "coordinate.boundary_patterns")
    independent_boundary = _map(independent.get("boundary"), "independent.boundary")
    if (
        boundary.get("count") != 47
        or boundary.get("q_cells_per_pattern") != 46
        or independent_boundary.get("pattern_count") != 47
        or independent_boundary.get("q_cardinality_each") != 46
    ):
        raise AgreementError("boundary-pattern count disagreement")
    expected_gaps = [[0, gap] for gap in range(0, 70, 3)] + [[gap, 0] for gap in range(3, 70, 3)]
    if boundary.get("gap_pairs") != expected_gaps:
        raise AgreementError("coordinate gap-pair corpus is incomplete")

    coordinate_canaries = _map(coordinate.get("canaries"), "coordinate.canaries")
    if any(_map(record, "coordinate canary").get("pass") is not True for record in coordinate_canaries.values()):
        raise AgreementError("a coordinate mutation canary did not fire")
    independent_canaries = _map(independent.get("canaries"), "independent.canaries")
    boolean_canaries = [value for value in independent_canaries.values() if type(value) is bool]
    if not boolean_canaries or not all(boolean_canaries):
        raise AgreementError("an independent mutation canary did not fire")
    _claim_checks(coordinate, independent)

    return {
        "schema_version": "b1_q_membrane_halo_agreement_v1",
        "status": "PASS",
        "corpus_errors": [],
        "inputs": {
            "coordinate_report": {
                "path": str(coordinate_path),
                "sha256": coordinate_sha,
            },
            "independent_report": {
                "path": str(independent_path),
                "sha256": independent_sha,
            },
        },
        "scripts": {
            "coordinate_sha256": coordinate_script_sha,
            "independent_sha256": independent_script_sha,
        },
        "strict_instance_sha256": EXPECTED_STRICT_SHA256,
        "metrics": coordinate_metrics,
        "class_table": [list(item) for item in coordinate_classes],
        "halo": halo_common,
        "raw_provider_saturation": expected_saturation,
        "frontier": {
            "old": [1190, 34],
            "new": [1190, 34],
            "oriented_dimensions": [[34, 35], [35, 34]],
        },
        "ceiling_survivors": {
            f"{width}x{height}": count for (width, height), count in sorted(coordinate_ceiling.items())
        },
        "incremental_prunes": {
            f"{width}x{height}": count for (width, height), count in sorted(coordinate_prunes.items())
        },
        "claim_boundary": "agreement_only_no_claim_upgrade",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coordinate", type=Path, required=True)
    parser.add_argument("--independent", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = compare(args.coordinate.resolve(), args.independent.resolve())
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output.resolve()
        if not output.parent.is_dir():
            raise FileNotFoundError(f"output parent does not exist: {output.parent}")
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
