#!/usr/bin/env python3
"""Fail-closed composition gate for the SMM4 local upper-bound recovery input."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence

from identity_contract_v1 import (
    IdentityContractError,
    assert_identity_join,
    canonical_content_projection,
    validate_full_identity,
    validate_projection,
)


SCHEMA = "b1_smm4_composition_gate_v1"
PINS_SCHEMA = "b1_smm4_composition_pins_v1"
INPUT_NAMES = (
    "old_r4_receipt",
    "geometry_admission",
    "strict_instance",
    "formula",
    "variable_map",
)
OLD_UPPER = (1188, 22)
CANDIDATE_UPPER = (1188, 18)
DELTA_ORIENTATIONS = ((22, 54), (54, 22))
OLD_RECEIPT_SEMANTICS = (
    "b1_r4_1188_22_complete_oriented_lex_better_band_"
    "given_a004_admitted_lemmas_v1"
)
FORMULA_SEMANTICS = (
    "given_geometry_admission_no_body_empty_22x54_or_54x22_"
    "satisfies_smm209_cell_cap_v1"
)

# These are the immutable historical input bytes. Paths and filesystem object
# identity are supplied by the fresh authority root and joined separately.
CONTENT_ANCHORS: dict[str, dict[str, Any]] = {
    "old_r4_receipt": {
        "size_bytes": 2613,
        "sha256": "0b3366a3e1640a13675a28d1408b9b96ede3a0e6403e71a8f9222f1f44e5b5c2",
        "mode_octal": "0644",
    },
    "geometry_admission": {
        "size_bytes": 3075,
        "sha256": "abb67f2334756a22650457b3a066d32b48b7d5f8918406b53f4f4140ec3fbfdc",
        "mode_octal": "0644",
    },
    "strict_instance": {
        "size_bytes": 92201,
        "sha256": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
        "mode_octal": "0644",
    },
    "formula": {
        "size_bytes": 283,
        "sha256": "d4b79cd76c80d23e509ad09b1d2e7fa02fa337049f40459ab803f0fc55a4d865",
        "mode_octal": "0644",
    },
    "variable_map": {
        "size_bytes": 1152,
        "sha256": "f02e948739ee63a0e6b74c7a7cae5dc0015211c111c17621bb0d3951cb6c0cce",
        "mode_octal": "0644",
    },
}

RECEIPT_KEYS = {
    "build_manifest",
    "build_record",
    "claim",
    "created_at_utc",
    "formal_attempt",
    "formula",
    "output_directory",
    "production_certified",
    "proof",
    "proof_status",
    "raw_manifest",
    "reservation_copy",
    "reservation_source",
    "schema_version",
    "semantics",
    "status",
    "toolchain_record",
    "upper_bound_update_authorized",
}
RECEIPT_REFERENCE_KEYS = {"path", "sha256", "size_bytes"}
GEOMETRY_KEYS = {
    "claim_boundary",
    "decision",
    "established",
    "geometry_authority",
    "inputs",
    "next_gate",
    "schema_version",
    "status",
    "tool",
}
GEOMETRY_ESTABLISHED_KEYS = {
    "adversarial_review",
    "candidate_band_delta_exact",
    "ceiling_orientations",
    "independent_strict_recomputation",
    "paper_necessity",
    "primary_strict_recomputation",
    "smm_209_necessary_bound",
}
STRICT_INSTANCE_KEYS = {
    "benchmark_id",
    "commodities",
    "coordinate_system",
    "facility_templates",
    "generic_requirements",
    "grid",
    "objective",
    "operation_groups",
    "power",
    "repeatable_auxiliaries",
    "required_instances",
    "routing",
    "schema_version",
    "sentinels",
}
VARIABLE_KEYS = {
    "area",
    "coefficient",
    "combined_inside_cap",
    "entity_endpoint_budget",
    "free_cell_cap",
    "height",
    "id",
    "kind",
    "marked_inside_cap",
    "name",
    "ordinary_inside_cap",
    "outside_cell_floor",
    "outside_incidence_floor",
    "side_sum",
    "total_required_cells",
    "width",
}
HEADER = re.compile(r"^\* #variable= (\d+) #constraint= (\d+) #equal= (\d+) intsize= (\d+)$")
CONSTRAINT = re.compile(r"^(.*?) (>=|=) (-?\d+) ;$")
TERM = re.compile(r"([+-]\d+) x([1-9]\d*)")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class CompositionError(RuntimeError):
    """Raised when the local composition claim cannot be established exactly."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CompositionError(message)


def exact_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    require(type(value) is dict, f"{label}: expected object")
    result = value
    require(set(result) == keys, f"{label}: key set mismatch")
    return result


def exact_integer(value: Any, label: str) -> int:
    require(type(value) is int, f"{label}: expected exact integer")
    return value


def strict_json(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CompositionError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise CompositionError(f"{label}: non-integer JSON number {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CompositionError(f"{label}: malformed JSON: {exc}") from exc


def snapshot_regular(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    raw_path = os.fspath(path)
    require(os.path.isabs(raw_path), f"{label}: path must be absolute")
    normalized = os.path.normpath(raw_path)
    require(raw_path == normalized, f"{label}: path is not normalized")
    require(os.path.realpath(raw_path) == normalized, f"{label}: path contains a symlink or alias")
    fd = os.open(
        normalized,
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode), f"{label}: not a regular file")
        chunks: list[bytes] = []
        while True:
            block = os.read(fd, 1 << 20)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    stable_fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
    require(
        tuple(getattr(before, field) for field in stable_fields)
        == tuple(getattr(after, field) for field in stable_fields),
        f"{label}: file changed during retained-FD read",
    )
    raw = b"".join(chunks)
    require(len(raw) == before.st_size, f"{label}: short read")
    identity = {
        "path": normalized,
        "size_bytes": len(raw),
        "sha256": sha256(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
        "device": before.st_dev,
        "inode": before.st_ino,
        "link_count": before.st_nlink,
    }
    return raw, validate_full_identity(identity, label)


def parse_pins(raw: bytes) -> dict[str, dict[str, dict[str, Any]]]:
    pins = exact_object(strict_json(raw, "composition pins"), {"schema_version", "inputs"}, "composition pins")
    require(pins["schema_version"] == PINS_SCHEMA, "composition pins: schema mismatch")
    inputs = exact_object(pins["inputs"], set(INPUT_NAMES), "composition pins.inputs")
    validated: dict[str, dict[str, dict[str, Any]]] = {}
    for name in INPUT_NAMES:
        pin = exact_object(inputs[name], {"identity", "content_projection"}, f"composition pins.{name}")
        identity = validate_full_identity(pin["identity"], f"composition pins.{name}.identity")
        projection = validate_projection(
            pin["content_projection"],
            f"composition pins.{name}.content_projection",
        )
        require(
            canonical_content_projection(identity, f"composition pins.{name}.identity") == projection,
            f"composition pins.{name}: identity/projection mismatch",
        )
        validated[name] = {
            "identity": identity,
            "content_projection": projection,
        }
    return validated


def validate_input_bindings(
    raw_inputs: Mapping[str, bytes],
    actual_identities: Mapping[str, Mapping[str, Any]],
    pinned_inputs: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    require(set(raw_inputs) == set(INPUT_NAMES), "raw input key set mismatch")
    require(set(actual_identities) == set(INPUT_NAMES), "actual identity key set mismatch")
    require(set(pinned_inputs) == set(INPUT_NAMES), "pinned input key set mismatch")
    bindings: dict[str, dict[str, Any]] = {}
    for name in INPUT_NAMES:
        raw = raw_inputs[name]
        require(type(raw) is bytes, f"{name}: raw input must be bytes")
        actual = validate_full_identity(dict(actual_identities[name]), f"{name}.actual_identity")
        pin = exact_object(dict(pinned_inputs[name]), {"identity", "content_projection"}, f"{name}.pin")
        expected_identity = validate_full_identity(pin["identity"], f"{name}.pin.identity")
        expected_projection = validate_projection(
            pin["content_projection"],
            f"{name}.pin.content_projection",
        )
        projection = assert_identity_join(expected_identity, expected_projection, actual, name)
        anchor = CONTENT_ANCHORS[name]
        require(
            {
                field: actual[field]
                for field in ("size_bytes", "sha256", "mode_octal")
            }
            == anchor,
            f"{name}: immutable historical content anchor mismatch",
        )
        require(len(raw) == actual["size_bytes"], f"{name}: identity size does not match supplied bytes")
        require(sha256(raw) == actual["sha256"], f"{name}: identity hash does not match supplied bytes")
        bindings[name] = {
            "identity": actual,
            "content_projection": projection,
        }
    return bindings


def verify_old_r4_receipt(receipt: Any) -> dict[str, Any]:
    value = exact_object(receipt, RECEIPT_KEYS, "old R4 receipt")
    require(
        value["schema_version"] == "b1_r4_1188_22_pb_authority_receipt_v1"
        and value["status"] == "VERIFIED"
        and value["proof_status"] == "VERIFIED UNSATISFIABLE"
        and value["upper_bound_update_authorized"] is True
        and value["production_certified"] is False,
        "old R4 receipt: terminal authority mismatch",
    )
    require(
        value["claim"] == "machine_verified_complete_lex_better_band_unsat_given_a004_admitted_geometric_lemmas"
        and value["semantics"] == OLD_RECEIPT_SEMANTICS
        and value["formal_attempt"] == "a001",
        "old R4 receipt: claim semantics mismatch",
    )
    require(
        type(value["created_at_utc"]) is str
        and type(value["output_directory"]) is str
        and os.path.isabs(value["output_directory"]),
        "old R4 receipt: provenance fields malformed",
    )
    for name in (
        "build_manifest",
        "build_record",
        "formula",
        "proof",
        "raw_manifest",
        "reservation_copy",
        "reservation_source",
        "toolchain_record",
    ):
        reference = exact_object(value[name], RECEIPT_REFERENCE_KEYS, f"old R4 receipt.{name}")
        require(
            type(reference["path"]) is str
            and type(reference["size_bytes"]) is int
            and reference["size_bytes"] > 0
            and type(reference["sha256"]) is str
            and HEX64.fullmatch(reference["sha256"]) is not None,
            f"old R4 receipt.{name}: malformed byte reference",
        )
    return {
        "status": "VERIFIED",
        "proof_status": "VERIFIED UNSATISFIABLE",
        "semantics": OLD_RECEIPT_SEMANTICS,
        "upper_bound_update_authorized": True,
        "production_certified": False,
    }


def derive_bands(strict_instance: Any) -> dict[str, Any]:
    instance = exact_object(strict_instance, STRICT_INSTANCE_KEYS, "strict instance")
    require(
        instance["schema_version"] == 1
        and instance["benchmark_id"] == "factory_layout_optimality_benchmark_v1",
        "strict instance: schema/benchmark mismatch",
    )
    grid = exact_object(instance["grid"], {"height", "width"}, "strict instance.grid")
    width = exact_integer(grid["width"], "strict instance.grid.width")
    height = exact_integer(grid["height"], "strict instance.grid.height")
    objective = exact_object(
        instance["objective"],
        {"body_cells_only", "kind", "minimum_side"},
        "strict instance.objective",
    )
    minimum_side = exact_integer(objective["minimum_side"], "strict instance.objective.minimum_side")
    require(
        (width, height, minimum_side) == (70, 70, 6)
        and objective["body_cells_only"] is True
        and objective["kind"] == "max_lex_area_min_side",
        "strict instance: grid/objective contract mismatch",
    )
    universe = {
        (candidate_width, candidate_height)
        for candidate_width in range(minimum_side, width + 1)
        for candidate_height in range(minimum_side, height + 1)
    }

    def score(orientation: tuple[int, int]) -> tuple[int, int]:
        return orientation[0] * orientation[1], min(orientation)

    old_band = {orientation for orientation in universe if score(orientation) > OLD_UPPER}
    candidate_band = {orientation for orientation in universe if score(orientation) > CANDIDATE_UPPER}
    delta = candidate_band - old_band
    require(len(old_band) == 2084, "strict instance: old band count is not 2084")
    require(len(candidate_band) == 2086, "strict instance: candidate band count is not 2086")
    require(delta == set(DELTA_ORIENTATIONS), "strict instance: candidate delta is not the two orientations")
    require(old_band <= candidate_band, "strict instance: old band is not a candidate-band subset")
    require(old_band.isdisjoint(delta), "strict instance: old band and delta overlap")
    require(old_band | delta == candidate_band, "strict instance: disjoint union does not cover candidate band")
    return {
        "grid": {"width": width, "height": height},
        "objective": {
            "kind": objective["kind"],
            "body_cells_only": True,
            "minimum_side": minimum_side,
        },
        "old_upper": list(OLD_UPPER),
        "old_band_count": len(old_band),
        "candidate_upper": list(CANDIDATE_UPPER),
        "candidate_band_count": len(candidate_band),
        "delta_orientations": [list(value) for value in DELTA_ORIENTATIONS],
        "old_delta_disjoint": True,
        "old_union_delta_equals_candidate": True,
    }


def verify_geometry_admission(admission: Any) -> dict[str, Any]:
    value = exact_object(admission, GEOMETRY_KEYS, "geometry admission")
    require(
        value["schema_version"] == "b1_sidewise_geometry_admission_v1"
        and value["status"] == "PASS"
        and value["decision"] == "ADMITTED_FOR_PB_ENCODER"
        and value["next_gate"] == "PB_TRANSLATION_ADMISSION",
        "geometry admission: status/decision mismatch",
    )
    established = exact_object(value["established"], GEOMETRY_ESTABLISHED_KEYS, "geometry admission.established")
    require(
        established
        == {
            "adversarial_review": True,
            "candidate_band_delta_exact": True,
            "ceiling_orientations": [[22, 54], [54, 22]],
            "independent_strict_recomputation": True,
            "paper_necessity": True,
            "primary_strict_recomputation": True,
            "smm_209_necessary_bound": True,
        },
        "geometry admission: admitted theorem set mismatch",
    )
    side_sum = 22 + 54
    entity_endpoint_budget = 19
    marked_inside_cap = (2 * side_sum + entity_endpoint_budget) // 2
    ordinary_inside_cap = side_sum + 48
    combined_inside_cap = marked_inside_cap + ordinary_inside_cap
    outside_incidence_floor = 628 + 110 - combined_inside_cap
    outside_cell_floor = (outside_incidence_floor + 3) // 4
    total_required_cells = 1188 + outside_cell_floor
    require(
        (
            side_sum,
            entity_endpoint_budget,
            marked_inside_cap,
            ordinary_inside_cap,
            combined_inside_cap,
            outside_incidence_floor,
            outside_cell_floor,
            total_required_cells,
        )
        == (76, 19, 85, 124, 209, 529, 133, 1321),
        "geometry admission: SMM-209 arithmetic drifted",
    )
    require(total_required_cells > 1320, "geometry admission: exclusion inequality did not close")
    return {
        "admission_status": "PASS",
        "decision": "ADMITTED_FOR_PB_ENCODER",
        "orientations": [[22, 54], [54, 22]],
        "side_sum": side_sum,
        "entity_endpoint_budget": entity_endpoint_budget,
        "marked_inside_cap": marked_inside_cap,
        "ordinary_inside_cap": ordinary_inside_cap,
        "combined_inside_cap": combined_inside_cap,
        "outside_incidence_floor": outside_incidence_floor,
        "outside_cell_floor": outside_cell_floor,
        "total_required_cells": total_required_cells,
        "available_cell_cap": 1320,
        "excluded": True,
    }


def expected_variable_map() -> dict[str, Any]:
    variables = []
    for variable_id, (width, height) in enumerate(DELTA_ORIENTATIONS, start=1):
        variables.append(
            {
                "area": 1188,
                "coefficient": -1,
                "combined_inside_cap": 209,
                "entity_endpoint_budget": 19,
                "free_cell_cap": 1320,
                "height": height,
                "id": variable_id,
                "kind": "oriented_ceiling_selector",
                "marked_inside_cap": 85,
                "name": f"ceiling__w_{width:02d}__h_{height:02d}",
                "ordinary_inside_cap": 124,
                "outside_cell_floor": 133,
                "outside_incidence_floor": 529,
                "side_sum": 76,
                "total_required_cells": 1321,
                "width": width,
            }
        )
    return {
        "schema_version": "b1_sidewise_ceiling_variable_map_v1",
        "semantics": FORMULA_SEMANTICS,
        "variables": variables,
    }


def verify_variable_map(variable_map: Any) -> dict[str, Any]:
    value = exact_object(variable_map, {"schema_version", "semantics", "variables"}, "variable map")
    require(type(value["variables"]) is list and len(value["variables"]) == 2, "variable map: expected two variables")
    for index, variable in enumerate(value["variables"], start=1):
        exact_object(variable, VARIABLE_KEYS, f"variable map.variables[{index}]")
    require(value == expected_variable_map(), "variable map: orientation/selector mapping mismatch")
    return {
        "x1": [22, 54],
        "x2": [54, 22],
        "mapping_exact": True,
    }


def parse_formula(raw: bytes) -> dict[str, Any]:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise CompositionError("formula: non-ASCII bytes") from exc
    require(len(lines) == 5, "formula: line count mismatch")
    header = HEADER.fullmatch(lines[0])
    require(header is not None, "formula: malformed header")
    expected_comment = (
        "* model=b1_sidewise_ceiling_exclusion_pb_v1 "
        f"semantics={FORMULA_SEMANTICS} target=1188,18 old_upper=1188,22 "
        "given_smm209=true"
    )
    require(lines[1] == expected_comment, "formula: provenance comment mismatch")
    constraints: Counter[tuple[str, int, tuple[tuple[int, int], ...]]] = Counter()
    for line in lines[2:]:
        match = CONSTRAINT.fullmatch(line)
        require(match is not None, f"formula: malformed constraint {line!r}")
        body, relation, rhs_raw = match.groups()
        position = 0
        terms: list[tuple[int, int]] = []
        for term in TERM.finditer(body):
            require(body[position : term.start()].strip() == "", "formula: unparsed term bytes")
            coefficient, variable = map(int, term.groups())
            terms.append((variable, coefficient))
            position = term.end()
        require(body[position:].strip() == "" and terms, "formula: term parse gap")
        constraints[(relation, int(rhs_raw), tuple(sorted(terms)))] += 1
    exact_one = ("=", 1, ((1, 1), (2, 1)))
    forbid_x1 = (">=", 0, ((1, -1),))
    forbid_x2 = (">=", 0, ((2, -1),))
    require(
        tuple(map(int, header.groups())) == (2, 3, 1, 0)
        and constraints == Counter({exact_one: 1, forbid_x1: 1, forbid_x2: 1}),
        "formula: exact-one/both-forbid multiset mismatch",
    )
    return {
        "header": {
            "variables": 2,
            "constraints": 3,
            "equalities": 1,
            "intsize": 0,
        },
        "exact_one": "+1 x1 +1 x2 = 1",
        "forbid_x1": "-1 x1 >= 0",
        "forbid_x2": "-1 x2 >= 0",
        "constraint_multiset_exact": True,
    }


def verify_composition(
    raw_inputs: Mapping[str, bytes],
    actual_identities: Mapping[str, Mapping[str, Any]],
    pinned_inputs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Verify the complete local composition claim using already-opened input bytes."""

    bindings = validate_input_bindings(raw_inputs, actual_identities, pinned_inputs)
    old_receipt = verify_old_r4_receipt(strict_json(raw_inputs["old_r4_receipt"], "old R4 receipt"))
    bands = derive_bands(strict_json(raw_inputs["strict_instance"], "strict instance"))
    geometry = verify_geometry_admission(strict_json(raw_inputs["geometry_admission"], "geometry admission"))
    variable_mapping = verify_variable_map(strict_json(raw_inputs["variable_map"], "variable map"))
    formula = parse_formula(raw_inputs["formula"])
    checks = {
        "input_key_sets_and_full7_projection_pins_exact": True,
        "historical_content_hashes_exact": True,
        "old_r4_receipt_verified_unsat": old_receipt["proof_status"] == "VERIFIED UNSATISFIABLE",
        "old_r4_upper_update_authorized": old_receipt["upper_bound_update_authorized"] is True,
        "old_r4_complete_band_semantics_exact": old_receipt["semantics"] == OLD_RECEIPT_SEMANTICS,
        "strict_instance_grid_objective_replayed": True,
        "old_band_count_2084": bands["old_band_count"] == 2084,
        "candidate_band_count_2086": bands["candidate_band_count"] == 2086,
        "delta_exact_two_orientations": bands["delta_orientations"] == [[22, 54], [54, 22]],
        "old_delta_disjoint": bands["old_delta_disjoint"] is True,
        "old_union_delta_equals_candidate": bands["old_union_delta_equals_candidate"] is True,
        "smm209_geometry_admitted": geometry["combined_inside_cap"] == 209,
        "smm209_exclusion_arithmetic_exact": geometry["total_required_cells"] == 1321,
        "orientation_selector_mapping_exact": variable_mapping["mapping_exact"] is True,
        "opb_exact_one_and_both_forbid": formula["constraint_multiset_exact"] is True,
    }
    require(all(checks.values()), "composition checks did not all pass")
    return {
        "schema_version": SCHEMA,
        "status": "PASS",
        "decision": "LOCAL_UPPER_RECOVERY_INPUT_ADMITTED",
        "inputs": bindings,
        "old_r4_authority": old_receipt,
        "independent_band_composition": bands,
        "smm209_geometry": geometry,
        "orientation_variable_mapping": variable_mapping,
        "two_selector_opb": formula,
        "checks": checks,
        "formal_attempt_admitted": True,
        "upper_bound_update_authorized": False,
        "claim_boundary": {
            "composition_gate_only": True,
            "candidate_upper_input": [1188, 18],
            "ledger_upper_remains": [1188, 22],
            "lower_remains": "absent",
            "requires_one_shot_formal_and_detached_receipt": True,
            "attainability": False,
            "optimality": False,
            "whole_instance_infeasibility": False,
            "production_certified": False,
        },
    }


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def write_once(path: Path, raw: bytes) -> None:
    raw_path = os.fspath(path)
    require(os.path.isabs(raw_path), "output: path must be absolute")
    require(raw_path == os.path.normpath(raw_path), "output: path is not normalized")
    require(not path.exists() and not path.is_symlink(), "output: already exists")
    require(path.parent.is_dir() and not path.parent.is_symlink(), "output: parent is not a real directory")
    fd = os.open(
        raw_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(fd, raw[offset:])
            require(written > 0, "output: short write")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pins", type=Path, required=True)
    parser.add_argument("--old-r4-receipt", type=Path, required=True)
    parser.add_argument("--geometry-admission", type=Path, required=True)
    parser.add_argument("--strict-instance", type=Path, required=True)
    parser.add_argument("--formula", type=Path, required=True)
    parser.add_argument("--variable-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    paths = {
        "old_r4_receipt": arguments.old_r4_receipt,
        "geometry_admission": arguments.geometry_admission,
        "strict_instance": arguments.strict_instance,
        "formula": arguments.formula,
        "variable_map": arguments.variable_map,
    }
    try:
        pins_raw, _ = snapshot_regular(arguments.pins, "composition pins")
        pinned_inputs = parse_pins(pins_raw)
        raw_inputs: dict[str, bytes] = {}
        actual_identities: dict[str, dict[str, Any]] = {}
        for name in INPUT_NAMES:
            raw_inputs[name], actual_identities[name] = snapshot_regular(paths[name], name)
        report = verify_composition(raw_inputs, actual_identities, pinned_inputs)
        output_raw = json_bytes(report)
        write_once(arguments.output, output_raw)
    except (CompositionError, IdentityContractError, OSError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "decision": report["decision"],
                "output": str(arguments.output),
                "size_bytes": len(output_raw),
                "sha256": sha256(output_raw),
                "formal_attempt_admitted": report["formal_attempt_admitted"],
                "upper_bound_update_authorized": report["upper_bound_update_authorized"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
