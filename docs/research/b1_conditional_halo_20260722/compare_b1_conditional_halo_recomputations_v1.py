#!/usr/bin/env python3
"""Fail-closed agreement gate for the two B1 conditional-halo recomputations."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DIRECT_SCRIPT = Path(__file__).resolve().with_name("verify_b1_conditional_halo_coordinates_v1.py")
PREFIX_SCRIPT = Path(__file__).resolve().with_name("recompute_b1_conditional_halo_prefix_v1.py")
STENCIL_PATH = Path(__file__).resolve().with_name("conditional_halo_stencil_v1.json")
EXPECTED_STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"


class AgreementError(RuntimeError):
    """A report is stale, malformed, or disagrees with its independent peer."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AgreementError(message)


def reject_constant(token: str) -> Any:
    raise AgreementError(f"non-finite JSON token: {token}")


def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AgreementError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load(path: Path) -> tuple[dict[str, Any], bytes, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicate, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AgreementError(f"cannot parse {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} root must be an object")
    return value, raw, hashlib.sha256(raw).hexdigest()


def object_value(value: Any, field: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), f"{field} must be an object")
    return value


def array_value(value: Any, field: str) -> Sequence[Any]:
    require(isinstance(value, Sequence) and not isinstance(value, (str, bytes)), f"{field} must be an array")
    return value


def integer(value: Any, field: str) -> int:
    require(type(value) is int, f"{field} must be an exact integer")
    return int(value)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        display = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        display = str(path.resolve())
    return {"path": display, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def validate_provenance(root: Mapping[str, Any], *, direct: bool) -> None:
    provenance = object_value(root.get("provenance"), "provenance")
    script = object_value(provenance.get("script"), "provenance.script")
    strict = object_value(provenance.get("strict_instance"), "provenance.strict_instance")
    stencil = object_value(provenance.get("stencil"), "provenance.stencil")
    expected_script = DIRECT_SCRIPT if direct else PREFIX_SCRIPT
    require(script.get("sha256") == sha(expected_script), "embedded script SHA is stale")
    require(
        integer(script.get("size_bytes"), "script.size_bytes") == expected_script.stat().st_size,
        "embedded script size is stale",
    )
    require(strict.get("sha256") == EXPECTED_STRICT_SHA256, "strict SHA drift")
    require(stencil.get("sha256") == sha(STENCIL_PATH), "stencil SHA drift")
    independence_key = (
        "imports_or_executes_other_recomputer_encoder_or_r3_verifier"
        if direct
        else "imports_or_executes_primary_recomputer_encoder_or_r3_verifier"
    )
    require(provenance.get(independence_key) is False, "independence marker is not false")


def validate_common(root: Mapping[str, Any], *, direct: bool) -> None:
    expected_schema = (
        "b1_conditional_halo_coordinate_recompute_v1" if direct else "b1_conditional_halo_prefix_recompute_v1"
    )
    require(root.get("schema_version") == expected_schema, "report schema mismatch")
    require(root.get("evidence_cutoff") == "2026-07-22", "evidence cutoff mismatch")
    require(
        root.get("status") == "PASS" and root.get("scope") == "geometry_only_pre_encoder", "report not geometry PASS"
    )
    require(list(array_value(root.get("corpus_errors"), "corpus_errors")) == [], "report contains corpus errors")
    expected_algorithm = (
        "direct_weighted_cell_to_rectangle_anchor_accumulation"
        if direct
        else "independent_70x70_grid_prefix_inclusion_exclusion"
    )
    require(root.get("algorithm") == expected_algorithm, "algorithm identity mismatch")
    validate_provenance(root, direct=direct)

    statement = object_value(root.get("conditional_halo"), "conditional_halo")
    require(
        (statement.get("rhs_original"), statement.get("rhs_doubled"), statement.get("pole_quantifier"))
        == (3325, 6650, "all_selected_poles"),
        "conditional-halo statement mismatch",
    )
    require(
        statement.get("cross_pole_stencil_overlap_subtracted") is False, "cross-pole overlap must not be subtracted"
    )
    require(
        statement.get("optional_storage_box_omitted_as_safe_relaxation") is True,
        "storage-box relaxation marker missing",
    )

    actual_p = object_value(root.get("actual_p_ledger"), "actual_p_ledger")
    require(actual_p.get("status") == "PROVED", "actual-P ledger is not proved")
    require(
        (
            actual_p.get("minimum_selected_poles"),
            actual_p.get("ceiling_minimum_lhs_at_P9"),
            actual_p.get("ceiling_minimum_lhs_at_P10"),
            actual_p.get("ceiling_selected_poles"),
            actual_p.get("ceiling_exact_nine_is_derived_not_assumed"),
        )
        == (9, 1318, 1322, 9, True),
        "actual-P ceiling derivation mismatch",
    )
    claims = set(array_value(root.get("claim_boundary"), "claim_boundary"))
    required_claims = {
        "necessary_condition_recomputation_only",
        "no_witness",
        "no_attainability",
        "no_routing_feasibility",
        "no_upper_bound_improvement",
        "no_global_optimality",
        "no_production_CERTIFIED_status",
    }
    require(claims == required_claims, "claim boundary mismatch")


def compare(direct_path: Path, prefix_path: Path) -> dict[str, Any]:
    direct, _, direct_sha = load(direct_path)
    prefix, _, prefix_sha = load(prefix_path)
    validate_common(direct, direct=True)
    validate_common(prefix, direct=False)

    checks: list[dict[str, str]] = []
    for field, check_id in (
        ("strict_ledger", "strict-ledger-exact-agreement"),
        ("stencil", "expanded-stencil-exact-agreement"),
        ("local_halo_certificate", "840-local-placement-exact-agreement"),
        ("conditional_halo", "all-selected-poles-statement-agreement"),
        ("actual_p_ledger", "actual-p-ledger-exact-agreement"),
        ("ceiling_corpus", "full-ceiling-corpus-exact-agreement"),
        ("claim_boundary", "claim-boundary-exact-agreement"),
    ):
        require(direct.get(field) == prefix.get(field), f"independent reports disagree on {field}")
        checks.append({"id": check_id, "status": "PASS"})

    ceiling = object_value(direct.get("ceiling_corpus"), "ceiling_corpus")
    expected_scalars = {
        "rectangle_count": 2_520,
        "pole_anchor_count": 4_761,
        "pair_count": 11_997_720,
        "clipped_total2_min": 218,
        "clipped_total2_max": 792,
        "c2_min": 0,
        "c2_max": 792,
        "body_intersection_pairs": 3_170_162,
        "nonzero_removed_pairs": 5_936_612,
        "nonzero_deficit_pairs": 9_568_548,
    }
    for field, expected in expected_scalars.items():
        require(integer(ceiling.get(field), f"ceiling.{field}") == expected, f"ceiling {field} drift")
    require(ceiling.get("objective") == [1190, 34], "ceiling objective drift")
    require(ceiling.get("dimensions") == [[34, 35], [35, 34]], "ceiling dimensions drift")
    canonical_digest = ceiling.get("canonical_digest_sha256")
    require(isinstance(canonical_digest, str) and len(canonical_digest) == 64, "bad canonical digest")
    checks.extend(
        [
            {"id": "complete-2520-by-4761-corpus", "status": "PASS"},
            {"id": "canonical-record-digest-agreement", "status": "PASS"},
            {"id": "histogram-and-body-conflict-agreement", "status": "PASS"},
            {"id": "independent-source-hashes-current", "status": "PASS"},
        ]
    )
    return {
        "schema_version": "b1_conditional_halo_recomputation_agreement_v1",
        "evidence_cutoff": "2026-07-22",
        "status": "PASS",
        "scope": "geometry_only_pre_encoder",
        "inputs": {
            "coordinate": {"path": str(direct_path), "sha256": direct_sha, "size_bytes": direct_path.stat().st_size},
            "prefix": {"path": str(prefix_path), "sha256": prefix_sha, "size_bytes": prefix_path.stat().st_size},
            "coordinate_script": snapshot(DIRECT_SCRIPT),
            "prefix_script": snapshot(PREFIX_SCRIPT),
            "stencil": snapshot(STENCIL_PATH),
        },
        "ceiling_corpus": {
            "rectangle_count": 2_520,
            "pole_anchor_count": 4_761,
            "pair_count": 11_997_720,
            "canonical_digest_sha256": canonical_digest,
            "body_intersection_pairs": 3_170_162,
            "nonzero_removed_pairs": 5_936_612,
            "nonzero_deficit_pairs": 9_568_548,
        },
        "checks": checks,
        "corpus_errors": [],
        "claim_boundary": list(direct["claim_boundary"]),
    }


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    require(path.parent.is_dir(), f"output parent missing: {path.parent}")
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coordinate", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = compare(args.coordinate.resolve(strict=True), args.prefix.resolve(strict=True))
        write_exclusive(args.output.resolve(), report)
    except (OSError, AgreementError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "PASS", "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
