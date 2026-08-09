#!/usr/bin/env python3
"""Independently verify the admitted ``(1188,22)`` PB translation.

The gate imports neither the encoder nor any R3/R4 mathematical checker.  It
uses the existing a004 admission closer only to replay the upstream authority,
then independently rederives the strict-instance arithmetic, selector band,
variable map, and complete OPB constraint multiset.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from types import ModuleType
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SEMANTICS = "b1_r4_1188_22_complete_oriented_lex_better_band_given_a004_admitted_lemmas_v1"
MODEL_SCHEMA = "b1_r4_1188_22_pb_v1"
META_SCHEMA = "b1_r4_1188_22_pb_metadata_v1"
METADATA_SCHEMA = META_SCHEMA
VAR_MAP_SCHEMA = "b1_r4_1188_22_pb_var_map_v1"
ESTIMATE_SCHEMA = "b1_r4_1188_22_pb_estimate_v1"
GATE_SCHEMA = "b1_r4_1188_22_pb_translation_gate_v1"
ENCODER_NAME = "b1_r4_1188_22_pb_encoder_v1"
ENCODER_SOURCE = Path(__file__).with_name("b1_r4_1188_22_pb_encoder_v1.py")
GATE_SOURCE = Path(__file__)

EXPECTED_GIT_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
TARGET_AREA = 1_188
TARGET_MIN_SIDE = 22
EXPECTED_VARIABLES = 2_084
EXPECTED_CONSTRAINTS = 2_192
EXPECTED_EQUALITIES = 1
EXPECTED_FULL_SPAN = 107
PROOF_LIMIT_BYTES = 5_000_000_000
MINIMUM_PLANNING_BYTES = 512 * 1024 * 1024

INPUT_PATHS = {
    "problem_instance": Path("docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"),
    "problem_instance_schema": Path(
        "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.schema.json"
    ),
    "problem_md": Path("docs/research/cleanroom_rederivation_20260718/strict/external/problem.md"),
    "sha256s": Path("docs/research/cleanroom_rederivation_20260718/strict/external/SHA256SUMS"),
}
INPUT_SHA256 = {
    "problem_instance": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    "problem_instance_schema": "5a85e23502e7b13feef495b8cc1ab243c65b0297d2a0f0f008258926e95c6b23",
    "problem_md": "c041e38d2144f2b4bace0c6c8567e3c7cdd5433f53981829f6ea6a8e03e0221f",
    "sha256s": "8810d5d6a80d92438628b7694216d3b3c6c1be50543072ec9c3bcf510d9c4d70",
}
INPUT_SIZE = {
    "problem_instance": 92_201,
    "problem_instance_schema": 12_695,
    "problem_md": 4_036,
    "sha256s": 339,
}

ADMISSION_CLOSER = Path("docs/research/r4_response_review_20260723/close_r4_response_candidate_admission_v2.py")
ADMISSION_CLOSER_SHA256 = "cf47cc662e3c3cf6e7e13915869866a09067854b837a5a775bdf8504dfd3f5d5"
ADMISSION_CLOSER_SIZE = 17_955
AUTHORITY_RUN = Path(".artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A")
RESPONSE_RUN = Path(
    ".artifacts/track_b_r4_external_brain_handoff_20260722/responses/run-20260723T023657Z-R4resp-357f260d"
)
A004_LEDGER = RESPONSE_RUN / "claims/a004/quantitative-claim-ledger.json"
A004_REPORTS = (
    RESPONSE_RUN / "recomputations/upper-counts-a004/report.json",
    RESPONSE_RUN / "recomputations/marked-geometry-a004/report.json",
    RESPONSE_RUN / "recomputations/w2d-audit-a004/report.json",
)
A004_VERDICT = RESPONSE_RUN / "adversarial/a004/verdict.json"
A004_ADMISSION = RESPONSE_RUN / "admission/a004/admission.json"
A004_ADMISSION_SHA256 = "2ebceb7bcdf93ad8cffa75e49eef89af679729f64a47a06ae27fa44682c206ff"
A004_ADMISSION_SIZE = 10_273

EXPECTED_CLASS_TABLE = Counter(
    {
        (3, 1): 155,
        (3, 2): 12,
        (3, 3): 11,
        (5, 1): 32,
        (5, 2): 17,
        (6, 3): 32,
        (6, 4): 3,
        (6, 5): 3,
    }
)
EXPECTED_MARKED_CLASS_TABLE = Counter(
    {
        (3, 0): 253,
        (3, 1): 57,
        (5, 0): 98,
        (6, 0): 38,
        (6, 1): 32,
        (6, 2): 3,
        (6, 3): 3,
        (9, 3): 2,
    }
)
HALO_DOUBLED_WEIGHTS = {
    (3, 3): 2,
    (5, 1): 8,
    (5, 5): 16,
    (7, 7): 8,
    (9, 3): 2,
    (9, 9): 2,
    (11, 1): 2,
    (11, 3): 12,
    (11, 5): 22,
    (11, 7): 2,
    (11, 9): 2,
    (13, 11): 25,
    (15, 3): 2,
    (17, 3): 8,
}
STEPS = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}

REQUIRED_CHECKS = frozenset(
    {
        "a004_admission_replay_pass",
        "strict_bundle_closed_and_hashed",
        "encoder_provenance_match",
        "translation_inputs_closed_and_hashed",
        "metadata_reconstruction_match",
        "estimate_reconstruction_match",
        "variable_map_dense",
        "variable_map_exact",
        "opb_header_exact",
        "constraint_multiset_exact",
        "strict_sentinels_exact",
        "ordinary_membrane_exact",
        "power_halo_exact",
        "marked_terminal_census_exact",
        "access_cell_enumeration_exact",
        "marked_membrane_exact",
        "boundary_packing_exact",
        "lex_better_band_exact",
        "complete_band_corpus_unsat",
        "semantic_canaries_pass",
    }
)

HEADER_RE = re.compile(
    r"^\*\s+#variable=\s+(\d+)\s+#constraint=\s+(\d+)\s+"
    r"#equal=\s+(\d+)\s+intsize=\s+(\d+)\s*$"
)
CONSTRAINT_RE = re.compile(r"^(.*?)\s+(>=|=)\s+([+-]?\d+)\s*;\s*$")
TERM_RE = re.compile(r"\s*([+-]\d+)\s+x([1-9]\d*)")
ConstraintKey = tuple[str, int, tuple[tuple[int, int], ...]]


class GateError(ValueError):
    """Raised for malformed, incomplete, or inconsistent gate inputs."""


def _exact_int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise GateError(f"{field} must be an exact integer")
    return int(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GateError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise GateError(f"{field} must be an array")
    return value


def _expect(value: Any, expected: Any, field: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise GateError(f"{field} must be {expected!r}, got {value!r}")


def _one(values: Iterable[Any], field: str) -> Any:
    unique = set(values)
    if len(unique) != 1:
        raise GateError(f"{field} must have one invariant value")
    return next(iter(unique))


def _reject_constant(value: str) -> Any:
    raise GateError(f"non-finite JSON number is forbidden: {value}")


def _reject_float(value: str) -> Any:
    raise GateError(f"floating-point JSON number is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(raw: bytes | str, field: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateError(f"{field} is not strict JSON: {exc}") from exc


def _type_exact_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(_type_exact_equal(actual[key], expected[key]) for key in expected)
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _type_exact_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_regular(path: Path, field: str) -> Path:
    absolute = path.absolute()
    try:
        mode = absolute.lstat().st_mode
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise GateError(f"cannot resolve {field}: {exc}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode) or resolved != absolute:
        raise GateError(f"{field} must be a canonical non-symlink regular file")
    return resolved


def _file_record(path: Path, root: Path) -> dict[str, Any]:
    resolved = _canonical_regular(path, str(path))
    raw = resolved.read_bytes()
    try:
        display = str(resolved.relative_to(root.resolve(strict=True)))
    except ValueError:
        display = str(resolved)
    return {"path": display, "sha256": _sha(raw), "size_bytes": len(raw)}


def _absolute_record(path: Path) -> dict[str, Any]:
    resolved = _canonical_regular(path, str(path))
    raw = resolved.read_bytes()
    return {"path": str(resolved), "sha256": _sha(raw), "size_bytes": len(raw)}


def _git_snapshot(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    head = (
        subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
        )
        .stdout.decode("ascii")
        .strip()
    )
    if head != EXPECTED_GIT_HEAD:
        raise GateError("current Git HEAD differs from the pinned baseline")
    exclude = ":(exclude).artifacts/track_b_b1_r4_1188_22_pb_20260723/**"
    diff = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--binary",
            "--full-index",
            "--no-ext-diff",
            "HEAD",
            "--",
            ".",
            exclude,
        ],
        check=True,
        capture_output=True,
    ).stdout
    status_raw = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=normal",
            "--",
            ".",
            exclude,
        ],
        check=True,
        capture_output=True,
    ).stdout
    return {
        "head": head,
        "tracked_dirty": bool(diff),
        "tracked_diff_sha256": _sha(diff),
        "tracked_diff_size_bytes": len(diff),
        "status_dirty": bool(status_raw),
        "status_sha256": _sha(status_raw),
        "status_size_bytes": len(status_raw),
        "artifact_exclusion": ".artifacts/track_b_b1_r4_1188_22_pb_20260723/**",
    }


def _load_closer(path: Path) -> ModuleType:
    source = _canonical_regular(path, "a004 admission closer")
    spec = importlib.util.spec_from_file_location(
        "_b1_r4_a004_admission_replay_gate",
        source,
    )
    if spec is None or spec.loader is None:
        raise GateError("cannot load a004 admission closer")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _replay_a004(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    closer_record = _absolute_record(root / ADMISSION_CLOSER)
    if closer_record != {
        "path": str((root / ADMISSION_CLOSER).resolve()),
        "sha256": ADMISSION_CLOSER_SHA256,
        "size_bytes": ADMISSION_CLOSER_SIZE,
    }:
        raise GateError("a004 admission closer bytes drifted")
    admission_record = _absolute_record(root / A004_ADMISSION)
    if admission_record != {
        "path": str((root / A004_ADMISSION).resolve()),
        "sha256": A004_ADMISSION_SHA256,
        "size_bytes": A004_ADMISSION_SIZE,
    }:
        raise GateError("a004 admission bytes drifted")
    replay = _load_closer(root / ADMISSION_CLOSER).replay_admission(
        root / AUTHORITY_RUN,
        root / RESPONSE_RUN,
        root / A004_LEDGER,
        [root / path for path in A004_REPORTS],
        root / A004_VERDICT,
        root / A004_ADMISSION,
    )
    if not isinstance(replay, Mapping) or set(replay) != {
        "admission",
        "verdict_replay",
        "admission_record",
    }:
        raise GateError("a004 replay shape drifted")
    admission = _mapping(replay["admission"], "a004 admission")
    expected_upper = {
        "verdict": "PASS",
        "research_followup_admitted": True,
        "b1_followup_input_admitted": True,
        "proposed_upper_ledger": [1188, 22],
    }
    candidates = _mapping(admission.get("candidates"), "a004 candidates")
    if not _type_exact_equal(candidates.get("upper_bound_1188_22"), expected_upper):
        raise GateError("a004 upper candidate is not admitted")
    if admission.get("status") != "PARTIAL" or not _type_exact_equal(
        admission.get("current_project_ledger"),
        {"U": [1190, 34], "L": "absent"},
    ):
        raise GateError("a004 status or current ledger drifted")
    false_fields = (
        "upper_bound_changed",
        "formal_run_authorized",
        "encoder_execution_authorized",
        "solver_run_authorized",
        "search_run_authorized",
        "assembly_run_authorized",
        "router_run_authorized",
        "track_w_execution_authorized",
        "external_response_code_executed",
        "witness_established",
        "attainability_established",
        "optimality_established",
        "global_infeasibility_established",
        "production_certified",
    )
    if any(admission.get(field) is not False for field in false_fields):
        raise GateError("a004 safety/authorization fields drifted")
    if not _type_exact_equal(replay.get("admission_record"), admission_record):
        raise GateError("a004 replay byte record drifted")
    return {
        "admission": admission_record,
        "admission_closer": closer_record,
        "replay_summary": {
            "status": "PARTIAL",
            "upper_candidate": expected_upper,
            "current_project_ledger": {"U": [1190, 34], "L": "absent"},
            "false_fields": {field: False for field in false_fields},
        },
    }


def _verify_sha256_manifest(
    raw: bytes,
    inputs: Mapping[str, bytes],
) -> bool:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise GateError("SHA256SUMS is not ASCII") from exc
    entries: dict[str, str] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None:
            raise GateError("SHA256SUMS is malformed")
        name = match.group(2)
        if name in entries:
            raise GateError("SHA256SUMS contains a duplicate")
        entries[name] = match.group(1)
    expected_names = {
        "problem_instance.json": "problem_instance",
        "problem_instance.schema.json": "problem_instance_schema",
        "problem.md": "problem_md",
    }
    if set(entries) != {*expected_names, "R1_prompt.md"}:
        return False
    return entries["R1_prompt.md"] == ("5154e299b472e0f3c50507fa2820e86b480789f50e2608f4d8ca455cefb7c916") and all(
        entries[name] == _sha(inputs[key]) for name, key in expected_names.items()
    )


def _ceil_div(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise GateError("ceil divisor must be positive")
    return -((-numerator) // denominator)


def _mode_area(template: Mapping[str, Any], field: str) -> int:
    values = []
    for raw_mode in _array(template.get("modes"), f"{field}.modes"):
        body = _mapping(_mapping(raw_mode, f"{field}.mode").get("body"), f"{field}.body")
        width = _exact_int(body.get("width"), f"{field}.width")
        height = _exact_int(body.get("height"), f"{field}.height")
        if width <= 0 or height <= 0:
            raise GateError(f"{field} body dimensions must be positive")
        values.append(width * height)
    return _exact_int(_one(values, f"{field} body area"), f"{field} body area")


def _side(mode: Mapping[str, Any], port: Mapping[str, Any], field: str) -> int:
    body = _mapping(mode.get("body"), f"{field}.body")
    direction = port.get("direction")
    if direction not in STEPS:
        raise GateError(f"{field} has an invalid direction")
    return _exact_int(
        body.get("width" if direction in {"N", "S"} else "height"),
        f"{field}.side",
    )


def _port_key(
    mode: Mapping[str, Any],
    port: Mapping[str, Any],
    field: str,
) -> tuple[int, int, str]:
    body = _mapping(mode.get("body"), f"{field}.body")
    cell = _mapping(port.get("body_cell"), f"{field}.body_cell")
    width = _exact_int(body.get("width"), f"{field}.width")
    height = _exact_int(body.get("height"), f"{field}.height")
    x = _exact_int(cell.get("x"), f"{field}.x")
    y = _exact_int(cell.get("y"), f"{field}.y")
    direction = port.get("direction")
    if direction not in STEPS or port.get("kind") not in {"input", "output"}:
        raise GateError(f"{field} kind/direction is invalid")
    if not (0 <= x < width and 0 <= y < height):
        raise GateError(f"{field} body cell is outside the body")
    if not {
        "N": y == height - 1,
        "E": x == width - 1,
        "S": y == 0,
        "W": x == 0,
    }[str(direction)]:
        raise GateError(f"{field} body cell is not on its declared body edge")
    return x, y, str(direction)


def _corner(mode: Mapping[str, Any], port: Mapping[str, Any], field: str) -> bool:
    body = _mapping(mode.get("body"), f"{field}.body")
    x, y, _direction = _port_key(mode, port, field)
    width = _exact_int(body.get("width"), f"{field}.width")
    height = _exact_int(body.get("height"), f"{field}.height")
    return x in {0, width - 1} and y in {0, height - 1}


def _needs(group: Mapping[str, Any], plural: str, field: str) -> int:
    values = _mapping(
        _mapping(group.get("port_needs"), f"{field}.port_needs").get(plural),
        f"{field}.{plural}",
    )
    result = sum(_exact_int(value, f"{field}.{plural}.{name}") for name, value in values.items())
    if result < 0:
        raise GateError(f"{field}.{plural} is negative")
    return result


def _weight2(
    x: int,
    y: int,
    weights: Mapping[tuple[int, int], int],
) -> int:
    key = tuple(sorted((abs(2 * x - 1), abs(2 * y - 1)), reverse=True))
    return weights.get(key, 0)


def _derive_halo(
    *,
    coverage: tuple[int, int, int, int],
    body_dimensions: Sequence[tuple[int, int]],
    powered_area: int,
    pole_body_dimensions: tuple[int, int],
    weights: Mapping[tuple[int, int], int],
) -> dict[str, Any]:
    x_min, x_max, y_min, y_max = coverage
    pole_width, pole_height = pole_body_dimensions
    pole_cells = {(x, y) for x in range(pole_width) for y in range(pole_height)}
    placement_counts: dict[str, int] = {}
    violations: list[dict[str, Any]] = []
    minimum_slack2: int | None = None
    for width, height in sorted(set(body_dimensions)):
        count = 0
        for anchor_x in range(x_min - width + 1, x_max + 1):
            for anchor_y in range(y_min - height + 1, y_max + 1):
                cells = {(anchor_x + body_x, anchor_y + body_y) for body_x in range(width) for body_y in range(height)}
                if cells & pole_cells:
                    continue
                count += 1
                slack2 = sum(_weight2(x, y, weights) for x, y in cells) - 2 * len(cells)
                minimum_slack2 = slack2 if minimum_slack2 is None else min(minimum_slack2, slack2)
                if slack2 < 0:
                    violations.append(
                        {
                            "body": [width, height],
                            "anchor": [anchor_x, anchor_y],
                            "slack2": slack2,
                        }
                    )
        placement_counts[f"{width}x{height}"] = count
    total_weight2 = sum(_weight2(x, y, weights) for x in range(-20, 21) for y in range(-20, 21))
    if total_weight2 <= 0 or total_weight2 % 2:
        raise GateError("halo weight is not a positive doubled integer")
    total_weight = total_weight2 // 2
    return {
        "orbit_count": len(weights),
        "doubled_weights": [{"u": u, "v": v, "weight2": value} for (u, v), value in sorted(weights.items())],
        "total_weight2": total_weight2,
        "total_weight": total_weight,
        "body_dimensions": [list(pair) for pair in sorted(set(body_dimensions))],
        "placement_counts": placement_counts,
        "placement_count": sum(placement_counts.values()),
        "violations": violations,
        "minimum_slack2": minimum_slack2,
        "powered_area": powered_area,
        "minimum_poles": _ceil_div(powered_area, total_weight),
    }


def _enumerate_access(
    templates: Mapping[str, Any],
) -> tuple[int, dict[str, Any]]:
    occurrences: list[tuple[str, bool, frozenset[tuple[int, int]]]] = []
    for template_name, raw_template in templates.items():
        template = _mapping(raw_template, f"templates.{template_name}")
        for mode_index, raw_mode in enumerate(_array(template.get("modes"), f"{template_name}.modes")):
            mode = _mapping(raw_mode, f"{template_name}.modes[{mode_index}]")
            body = _mapping(mode.get("body"), f"{template_name}.body")
            width = _exact_int(body.get("width"), f"{template_name}.width")
            height = _exact_int(body.get("height"), f"{template_name}.height")
            keys: list[tuple[int, int, str]] = []
            for port_index, raw_port in enumerate(_array(mode.get("ports"), f"{template_name}.ports")):
                port = _mapping(raw_port, f"{template_name}.ports[{port_index}]")
                x, y, direction = _port_key(
                    mode,
                    port,
                    f"{template_name}.ports[{port_index}]",
                )
                keys.append((x, y, direction))
                dx, dy = STEPS[direction]
                anchor_x, anchor_y = -dx - x, -dy - y
                body_cells = frozenset(
                    (anchor_x + body_x, anchor_y + body_y) for body_x in range(width) for body_y in range(height)
                )
                occurrences.append(
                    (
                        direction,
                        not _corner(mode, port, f"{template_name}.port"),
                        body_cells,
                    )
                )
            if len(keys) != len(set(keys)):
                raise GateError(f"{template_name} has duplicate physical port keys")
    by_direction = {direction: [item for item in occurrences if item[0] == direction] for direction in STEPS}
    result: dict[str, Any] = {}
    for terminal_count in (3, 4):
        checked = 0
        nonoverlap = 0
        maximum_marks = -1
        for directions in itertools.combinations(STEPS, terminal_count):
            for choice in itertools.product(*(by_direction[direction] for direction in directions)):
                checked += 1
                bodies = [item[2] for item in choice]
                if any(bodies[left] & bodies[right] for left in range(terminal_count) for right in range(left)):
                    continue
                nonoverlap += 1
                marks = sum(item[1] for item in choice)
                maximum_marks = max(maximum_marks, marks)
                if terminal_count + marks > 4:
                    raise GateError("t(z)+m(z)<=4 counterexample")
        result[f"t{terminal_count}"] = {
            "combinations_checked": checked,
            "nonoverlap_combinations": nonoverlap,
            "maximum_noncorner_marks": maximum_marks,
        }
    return len(occurrences), result


def _interval_certificate(
    patterns: set[tuple[int, int]],
) -> dict[str, int]:
    """Exhaust the one-dimensional contact lemma used at every R endpoint.

    A contact interval is also the projection of the facility body row or
    column immediately outside the contacted side of ``R``.  Consequently,
    two partial contacts crossing the same directed endpoint both contain the
    endpoint coordinate in their body projection and cannot be body-disjoint.
    This finite check derives the one-contact-per-endpoint premise instead of
    accepting the constant eight as an input.
    """

    maximum_marks = max(marks for _span, marks in patterns)
    interval_checks = 0
    endpoint_checks = 0
    maximum_body_disjoint_crossers = 0
    for edge in range(6, 71):
        partial: dict[int, list[tuple[int, int]]] = {0: [], edge - 1: []}
        for length, marks in sorted(patterns):
            for start in range(-length + 1, edge):
                overlap = [position for position in range(length) if 0 <= start + position < edge]
                full = len(overlap) == length
                for selected in itertools.combinations(range(length), marks):
                    exposed = sum(position in overlap for position in selected)
                    limit = len(overlap) if full else len(overlap) + marks
                    if 2 * exposed > limit:
                        raise GateError("marked-contact interval inequality failed")
                    interval_checks += 1
                if not full and start < 0:
                    partial[0].append((start, start + length - 1))
                if not full and start + length > edge:
                    partial[edge - 1].append((start, start + length - 1))
        for endpoint, intervals in partial.items():
            maximum_body_disjoint_crossers = max(
                maximum_body_disjoint_crossers,
                1 if intervals else 0,
            )
            for first, second in itertools.combinations(intervals, 2):
                if not (first[0] <= endpoint <= first[1] and second[0] <= endpoint <= second[1]):
                    raise GateError("marked endpoint overlap failed")
                body_projection_overlap = max(first[0], second[0]) <= min(first[1], second[1])
                if not body_projection_overlap:
                    raise GateError("two endpoint-crossing contacts could be body-disjoint")
                endpoint_checks += 1
    return {
        "interval_checks": interval_checks,
        "endpoint_pair_checks": endpoint_checks,
        "maximum_body_disjoint_crossers_per_endpoint": maximum_body_disjoint_crossers,
        "directed_side_count": len(STEPS),
        "endpoints_per_directed_side": 2,
        "directed_endpoint_count": 2 * len(STEPS),
        "maximum_marks_per_partial_contact": maximum_marks,
    }


def _band_for_bounds(minimum_side: int, maximum_side: int) -> list[tuple[int, int]]:
    return [
        (width, height)
        for width in range(minimum_side, maximum_side + 1)
        for height in range(minimum_side, maximum_side + 1)
        if width * height > TARGET_AREA or (width * height == TARGET_AREA and min(width, height) > TARGET_MIN_SIDE)
    ]


def _derive(problem_payload: Any) -> dict[str, Any]:
    """Recompute the strict geometry/accounting without encoder implementation."""

    problem = _mapping(problem_payload, "problem_instance")
    _expect(
        problem.get("benchmark_id"),
        "factory_layout_optimality_benchmark_v1",
        "benchmark_id",
    )
    _expect(problem.get("schema_version"), 1, "schema_version")
    grid = _mapping(problem.get("grid"), "grid")
    grid_width = _exact_int(grid.get("width"), "grid.width")
    grid_height = _exact_int(grid.get("height"), "grid.height")
    objective = _mapping(problem.get("objective"), "objective")
    if (
        grid_width,
        grid_height,
        objective.get("minimum_side"),
        objective.get("kind"),
        objective.get("body_cells_only"),
    ) != (70, 70, 6, "max_lex_area_min_side", True):
        raise GateError("grid/objective strict identity drifted")
    coordinate = _mapping(problem.get("coordinate_system"), "coordinate_system")
    if list(_array(coordinate.get("directions"), "directions")) != [
        "N",
        "E",
        "S",
        "W",
    ]:
        raise GateError("cardinal directions drifted")

    templates = _mapping(problem.get("facility_templates"), "facility_templates")
    body_areas = {
        str(name): _mode_area(_mapping(template, f"templates.{name}"), str(name))
        for name, template in templates.items()
    }
    required_raw = _array(problem.get("required_instances"), "required_instances")
    required: dict[str, Mapping[str, Any]] = {}
    template_counts: Counter[str] = Counter()
    for index, raw_instance in enumerate(required_raw):
        instance = _mapping(raw_instance, f"required[{index}]")
        instance_id = instance.get("id")
        template_name = instance.get("template")
        if type(instance_id) is not str or not instance_id or instance_id in required:
            raise GateError("required instance id is invalid or duplicated")
        if type(template_name) is not str or template_name not in templates:
            raise GateError("required instance template is unknown")
        required[instance_id] = instance
        template_counts[template_name] += 1
    groups: dict[str, Mapping[str, Any]] = {}
    for index, raw_group in enumerate(_array(problem.get("operation_groups"), "operation_groups")):
        group = _mapping(raw_group, f"operation_groups[{index}]")
        group_id = group.get("id")
        template_name = group.get("template")
        if type(group_id) is not str or not group_id or group_id in groups:
            raise GateError("operation group id is invalid or duplicated")
        if type(template_name) is not str or template_name not in templates:
            raise GateError("operation group template is unknown")
        count = _exact_int(group.get("count"), f"groups.{group_id}.count")
        ids = _array(group.get("instance_ids"), f"groups.{group_id}.instance_ids")
        if len(ids) != count or len(set(ids)) != count:
            raise GateError("operation group count/list mismatch")
        for instance_id in ids:
            if type(instance_id) is not str or instance_id not in required:
                raise GateError("operation group references an unknown instance")
            instance = required[instance_id]
            if instance.get("operation") != group_id or instance.get("template") != template_name:
                raise GateError("operation group/instance binding drifted")
        groups[group_id] = group

    powered = [
        instance
        for instance in required.values()
        if _mapping(
            templates[str(instance["template"])],
            f"templates.{instance['template']}",
        ).get("requires_power")
        is True
    ]
    required_body_area = sum(count * body_areas[name] for name, count in template_counts.items())
    powered_area = sum(body_areas[str(instance["template"])] for instance in powered)
    manufacturing_instances = sum(
        _exact_int(group.get("count"), f"groups.{group_id}.count") for group_id, group in groups.items()
    )
    manufacturing_inputs = sum(
        _exact_int(group.get("count"), f"groups.{group_id}.count") * _needs(group, "inputs", group_id)
        for group_id, group in groups.items()
    )
    manufacturing_outputs = sum(
        _exact_int(group.get("count"), f"groups.{group_id}.count") * _needs(group, "outputs", group_id)
        for group_id, group in groups.items()
    )
    generic = _mapping(problem.get("generic_requirements"), "generic requirements")
    raw_output_count = sum(
        _exact_int(value, f"raw_outputs.{name}")
        for name, value in _mapping(
            generic.get("raw_outputs"),
            "raw outputs",
        ).items()
    )
    final_input_count = sum(
        _exact_int(value, f"final_inputs.{name}")
        for name, value in _mapping(
            generic.get("final_inputs"),
            "final inputs",
        ).items()
    )
    active_inputs = manufacturing_inputs + final_input_count
    active_outputs = manufacturing_outputs + raw_output_count
    total_terminals = active_inputs + active_outputs
    commodities = _array(problem.get("commodities"), "commodities")
    if any(type(name) is not str or not name for name in commodities) or len(set(commodities)) != len(commodities):
        raise GateError("commodity list drifted")
    strict_sentinels = {
        "required_instances": len(required),
        "manufacturing_instances": manufacturing_instances,
        "required_body_area": required_body_area,
        "powered_manufacturing_area": powered_area,
        "manufacturing_input_terminals": manufacturing_inputs,
        "manufacturing_output_terminals": manufacturing_outputs,
        "generic_raw_output_terminals": raw_output_count,
        "generic_final_input_terminals": final_input_count,
        "active_input_terminals": active_inputs,
        "active_output_terminals": active_outputs,
        "total_active_terminals": total_terminals,
        "operation_groups": len(groups),
        "commodities": len(commodities),
    }
    expected_sentinels = {
        "required_instances": 266,
        "manufacturing_instances": 219,
        "required_body_area": 3544,
        "powered_manufacturing_area": 3325,
        "manufacturing_input_terminals": 310,
        "manufacturing_output_terminals": 264,
        "generic_raw_output_terminals": 52,
        "generic_final_input_terminals": 2,
        "active_input_terminals": 312,
        "active_output_terminals": 316,
        "total_active_terminals": 628,
        "operation_groups": 17,
        "commodities": 19,
    }
    if strict_sentinels != expected_sentinels:
        raise GateError("strict count sentinel drift")
    declared = _mapping(problem.get("sentinels"), "sentinels")
    declared_map = {
        "required_instance_count": "required_instances",
        "manufacturing_instance_count": "manufacturing_instances",
        "required_body_area": "required_body_area",
        "manufacturing_input_terminals": "manufacturing_input_terminals",
        "manufacturing_output_terminals": "manufacturing_output_terminals",
        "generic_raw_output_terminals": "generic_raw_output_terminals",
        "generic_final_input_terminals": "generic_final_input_terminals",
        "total_active_terminals": "total_active_terminals",
        "operation_group_count": "operation_groups",
        "commodity_count": "commodities",
    }
    for declared_name, fact_name in declared_map.items():
        _expect(
            declared.get(declared_name),
            strict_sentinels[fact_name],
            f"sentinels.{declared_name}",
        )

    powered_shapes: set[tuple[int, int]] = set()
    for instance in powered:
        template = _mapping(
            templates[str(instance["template"])],
            f"templates.{instance['template']}",
        )
        for raw_mode in _array(template.get("modes"), "powered modes"):
            mode = _mapping(raw_mode, "powered mode")
            body = _mapping(mode.get("body"), "powered body")
            powered_shapes.add(
                (
                    _exact_int(body.get("width"), "powered width"),
                    _exact_int(body.get("height"), "powered height"),
                )
            )

    classes: Counter[tuple[int, int]] = Counter()
    marked_classes: Counter[tuple[int, int]] = Counter()
    patterns: set[tuple[int, int]] = set()
    manufacturing_marks = 0
    for group_id, group in groups.items():
        template_name = str(group["template"])
        template = _mapping(templates[template_name], f"templates.{template_name}")
        count = _exact_int(group.get("count"), f"groups.{group_id}.count")
        needs = {
            "inputs": _needs(group, "inputs", group_id),
            "outputs": _needs(group, "outputs", group_id),
        }
        spans: list[int] = []
        mode_ports: list[tuple[Mapping[str, Any], list[Mapping[str, Any]]]] = []
        for raw_mode in _array(template.get("modes"), f"{template_name}.modes"):
            mode = _mapping(raw_mode, f"{template_name}.mode")
            ports = [
                _mapping(port, f"{template_name}.port") for port in _array(mode.get("ports"), f"{template_name}.ports")
            ]
            for port in ports:
                _port_key(mode, port, f"{template_name}.port")
                spans.append(_side(mode, port, f"{template_name}.port"))
            mode_ports.append((mode, ports))
        span = _exact_int(_one(spans, f"{template_name} side span"), "side span")
        classes[(span, max(needs.values()))] += count
        marks_for_group = 0
        for plural, kind in (("inputs", "input"), ("outputs", "output")):
            corner_counts = {
                sum(_corner(mode, port, f"{template_name}.{kind}") for port in ports if port.get("kind") == kind)
                for mode, ports in mode_ports
            }
            capacities = {sum(port.get("kind") == kind for port in ports) for _mode, ports in mode_ports}
            if corner_counts != {2} or min(capacities) < needs[plural]:
                raise GateError("manufacturing port capacity/corner census drifted")
            marks = max(0, needs[plural] - 2)
            marked_classes[(span, marks)] += count
            patterns.add((span, marks))
            marks_for_group += marks
        manufacturing_marks += count * marks_for_group

    boundary_count = template_counts["boundary_storage_port"]
    boundary = _mapping(templates.get("boundary_storage_port"), "boundary")
    if boundary.get("placement_rule") != "matching_map_boundary":
        raise GateError("boundary placement rule drifted")
    boundary_modes: set[tuple[int, int, str]] = set()
    for raw_mode in _array(boundary.get("modes"), "boundary modes"):
        mode = _mapping(raw_mode, "boundary mode")
        body = _mapping(mode.get("body"), "boundary body")
        ports = [_mapping(port, "boundary port") for port in _array(mode.get("ports"), "boundary ports")]
        if len(ports) != 1 or ports[0].get("kind") != "output" or _corner(mode, ports[0], "boundary port"):
            raise GateError("boundary raw-output slot geometry drifted")
        boundary_modes.add(
            (
                _exact_int(body.get("width"), "boundary width"),
                _exact_int(body.get("height"), "boundary height"),
                str(ports[0].get("direction")),
            )
        )
        if _side(mode, ports[0], "boundary port") != 3:
            raise GateError("boundary side length drifted")
    if boundary_modes != {(1, 3, "E"), (3, 1, "N")}:
        raise GateError("boundary modes drifted")
    classes[(3, 1)] += boundary_count
    marked_classes[(3, 1)] += boundary_count
    patterns.add((3, 1))

    core = _mapping(templates.get("protocol_core"), "protocol core")
    core_patterns: set[tuple[int, int]] = set()
    core_slot_counts: set[int] = set()
    for raw_mode in _array(core.get("modes"), "protocol core modes"):
        mode = _mapping(raw_mode, "protocol core mode")
        faces: dict[str, list[Mapping[str, Any]]] = {}
        for raw_port in _array(mode.get("ports"), "protocol core ports"):
            port = _mapping(raw_port, "protocol core port")
            if port.get("kind") == "output":
                if _corner(mode, port, "protocol core output"):
                    raise GateError("protocol core raw output is at a corner")
                faces.setdefault(str(port.get("direction")), []).append(port)
        if sorted(len(items) for items in faces.values()) != [3, 3]:
            raise GateError("protocol core output split drifted")
        core_slot_counts.add(sum(len(items) for items in faces.values()))
        core_patterns.update((_side(mode, items[0], "protocol core face"), len(items)) for items in faces.values())
    if core_patterns != {(9, 3)} or core_slot_counts != {6}:
        raise GateError("protocol core output face drifted")
    marked_classes[(9, 3)] += 2
    patterns.add((9, 3))
    if classes != EXPECTED_CLASS_TABLE:
        raise GateError("ordinary membrane class table drifted")
    if marked_classes != EXPECTED_MARKED_CLASS_TABLE:
        raise GateError("marked membrane class table drifted")

    excess = sum(count * max(0, 2 * active - span) for (span, active), count in classes.items())
    directed_endpoints = 2 * len(STEPS)
    maximum_endpoint_extra = max(active - max(0, 2 * active - span) for span, active in classes)
    endpoint_correction = directed_endpoints * maximum_endpoint_extra
    total_excess = excess + endpoint_correction
    membrane_floor = total_excess // 2
    inside_addend = 3 + final_input_count
    inside_constant = membrane_floor + inside_addend
    ordinary_numerator = total_terminals - inside_constant
    if (
        excess,
        directed_endpoints,
        maximum_endpoint_extra,
        endpoint_correction,
        total_excess,
        membrane_floor,
        inside_addend,
        inside_constant,
        ordinary_numerator,
    ) != (63, 8, 3, 24, 87, 43, 5, 48, 580):
        raise GateError("ordinary membrane constants drifted")

    provider_slots: dict[str, int] = {}
    for provider_name in _array(
        generic.get("raw_output_providers"),
        "raw-output providers",
    ):
        if type(provider_name) is not str or provider_name not in templates:
            raise GateError("raw-output provider is unknown")
        template = _mapping(templates[provider_name], f"templates.{provider_name}")
        counts: set[int] = set()
        for raw_mode in _array(template.get("modes"), f"{provider_name}.modes"):
            mode = _mapping(raw_mode, f"{provider_name}.mode")
            outputs = [
                _mapping(port, f"{provider_name}.port")
                for port in _array(mode.get("ports"), f"{provider_name}.ports")
                if _mapping(port, f"{provider_name}.port").get("kind") == "output"
            ]
            if any(_corner(mode, port, provider_name) for port in outputs):
                raise GateError("raw-output slot is at a corner")
            counts.add(len(outputs))
        provider_slots[provider_name] = template_counts[provider_name] * _exact_int(
            _one(counts, f"{provider_name} slots"), "slot count"
        )
    if provider_slots != {"boundary_storage_port": 46, "protocol_core": 6}:
        raise GateError("raw-output slot census drifted")
    raw_noncorner_slots = sum(provider_slots.values())
    total_marks = manufacturing_marks + raw_noncorner_slots
    if (manufacturing_marks, raw_noncorner_slots, total_marks) != (58, 52, 110):
        raise GateError("marked-terminal census drifted")

    occurrence_count, access = _enumerate_access(templates)
    expected_access = {
        "t3": {
            "combinations_checked": 352_440,
            "nonoverlap_combinations": 30_080,
            "maximum_noncorner_marks": 1,
        },
        "t4": {
            "combinations_checked": 3_920_400,
            "nonoverlap_combinations": 8_192,
            "maximum_noncorner_marks": 0,
        },
    }
    if occurrence_count != 178 or access != expected_access:
        raise GateError("access-cell enumeration drifted")
    maximum_marks = max(marks for _span, marks in patterns)
    maximum_marked_side = max(span for span, marks in patterns if marks)
    if maximum_marks != 3 or maximum_marked_side != 9 or not all(2 * marks <= span for span, marks in patterns):
        raise GateError("marked side extrema drifted")
    interval_certificate = _interval_certificate(patterns)
    interval_checks = interval_certificate["interval_checks"]
    endpoint_checks = interval_certificate["endpoint_pair_checks"]
    if (
        (interval_checks, endpoint_checks) != (381_680, 81_900)
        or interval_certificate["maximum_body_disjoint_crossers_per_endpoint"] != 1
        or interval_certificate["directed_endpoint_count"] != directed_endpoints
        or interval_certificate["maximum_marks_per_partial_contact"] != maximum_marks
    ):
        raise GateError("marked membrane coordinate census drifted")
    partial_contacts = (
        interval_certificate["directed_endpoint_count"]
        * interval_certificate["maximum_body_disjoint_crossers_per_endpoint"]
    )
    marked_inside_offset = partial_contacts * maximum_marks // 2
    marked_numerator = ordinary_numerator + total_marks - marked_inside_offset
    if (marked_inside_offset, marked_numerator) != (12, 678):
        raise GateError("marked membrane constants drifted")

    power = _mapping(problem.get("power"), "power")
    _expect(
        power.get("required_rule"),
        "at_least_one_body_cell_covered",
        "power.required_rule",
    )
    pole_name = power.get("pole_template")
    if type(pole_name) is not str or pole_name not in templates:
        raise GateError("pole template drifted")
    pole_template = _mapping(templates[pole_name], "pole template")
    pole_shapes = {
        (
            _exact_int(
                _mapping(_mapping(mode, "pole mode").get("body"), "pole body").get("width"),
                "pole width",
            ),
            _exact_int(
                _mapping(_mapping(mode, "pole mode").get("body"), "pole body").get("height"),
                "pole height",
            ),
        )
        for mode in _array(pole_template.get("modes"), "pole modes")
    }
    if pole_shapes != {(2, 2)} or body_areas[pole_name] != 4:
        raise GateError("pole body geometry drifted")
    coverage_map = _mapping(
        power.get("coverage_from_pole_anchor"),
        "power coverage",
    )
    coverage = (
        _exact_int(coverage_map.get("x_min_offset"), "coverage x min"),
        _exact_int(coverage_map.get("x_max_offset"), "coverage x max"),
        _exact_int(coverage_map.get("y_min_offset"), "coverage y min"),
        _exact_int(coverage_map.get("y_max_offset"), "coverage y max"),
    )
    if coverage != (-5, 6, -5, 6):
        raise GateError("power coverage offsets drifted")
    halo = _derive_halo(
        coverage=coverage,
        body_dimensions=sorted(powered_shapes),
        powered_area=powered_area,
        pole_body_dimensions=(2, 2),
        weights=HALO_DOUBLED_WEIGHTS,
    )
    if (
        halo["orbit_count"] != 14
        or halo["total_weight2"] != 792
        or halo["total_weight"] != 396
        or halo["placement_counts"] != {"3x3": 180, "4x6": 220, "5x5": 220, "6x4": 220}
        or halo["placement_count"] != 840
        or halo["violations"]
        or halo["minimum_poles"] != 9
    ):
        raise GateError("power halo certificate drifted")
    pole_body_area = body_areas[pole_name]
    free_cell_cap = grid_width * grid_height - required_body_area - halo["minimum_poles"] * pole_body_area
    if free_cell_cap != 1320:
        raise GateError("free-cell cap drifted")

    anchors = list(range(70 - 2))
    chosen: list[int] = []
    next_free = 0
    for anchor in anchors:
        if anchor >= next_free:
            chosen.append(anchor)
            next_free = anchor + 3
    distributions = [
        left for left in range(boundary_count + 1) if left <= len(chosen) and boundary_count - left <= len(chosen)
    ]
    boundary_packing = {
        "anchors_per_supported_side": len(anchors),
        "maximum_per_supported_side": len(chosen),
        "forced_distribution": [23, 23],
        "occupied_cells_per_supported_side": 3 * len(chosen),
    }
    if distributions != [23] or boundary_packing != {
        "anchors_per_supported_side": 68,
        "maximum_per_supported_side": 23,
        "forced_distribution": [23, 23],
        "occupied_cells_per_supported_side": 69,
    }:
        raise GateError("boundary 23+23 packing drifted")

    dimensions = _band_for_bounds(6, 70)
    factor_pairs = [
        (width_value, height_value)
        for width_value in range(6, 71)
        for height_value in range(6, 71)
        if width_value * height_value == TARGET_AREA
    ]
    full_span = [pair for pair in dimensions if 70 in pair]

    outside_access_incidence_cap = len(STEPS)

    def access_bound(width_value: int, height_value: int) -> tuple[int, int, int]:
        side_sum = width_value + height_value
        ordinary = _ceil_div(
            ordinary_numerator - side_sum,
            outside_access_incidence_cap,
        )
        marked = _ceil_div(
            marked_numerator - 2 * side_sum,
            outside_access_incidence_cap,
        )
        return ordinary, marked, max(ordinary, marked)

    variables: list[dict[str, Any]] = []
    arithmetic_survivors: list[tuple[int, int]] = []
    combined_survivors: list[tuple[int, int]] = []
    for width_value, height_value in dimensions:
        ordinary_access, marked_access, access_lower = access_bound(
            width_value,
            height_value,
        )
        total = width_value * height_value + access_lower
        coefficient = free_cell_cap - total
        is_full_span = 70 in (width_value, height_value)
        variables.append(
            {
                "id": len(variables) + 1,
                "name": (f"dimension__w_{width_value:02d}__h_{height_value:02d}"),
                "kind": "oriented_dimension_selector",
                "width": width_value,
                "height": height_value,
                "area": width_value * height_value,
                "minimum_side": min(width_value, height_value),
                "side_sum": width_value + height_value,
                "marked_bound_applicable": min(width_value, height_value) >= 9,
                "ordinary_access_lower_bound": ordinary_access,
                "marked_access_lower_bound": marked_access,
                "access_lower_bound": access_lower,
                "total_required_cells": total,
                "coefficient": coefficient,
                "full_span": is_full_span,
            }
        )
        if coefficient >= 0:
            arithmetic_survivors.append((width_value, height_value))
            if not is_full_span:
                combined_survivors.append((width_value, height_value))
    non_full = [item for item in variables if not item["full_span"]]
    minimum_non_full = min(int(item["total_required_cells"]) for item in non_full)
    minimizers = [
        (int(item["width"]), int(item["height"]))
        for item in non_full
        if item["total_required_cells"] == minimum_non_full
    ]
    if (
        len(dimensions) != 2084
        or factor_pairs
        != [
            (18, 66),
            (22, 54),
            (27, 44),
            (33, 36),
            (36, 33),
            (44, 27),
            (54, 22),
            (66, 18),
        ]
        or [pair for pair in factor_pairs if pair in dimensions] != [(27, 44), (33, 36), (36, 33), (44, 27)]
        or min(min(pair) for pair in dimensions) != 17
        or len(full_span) != 107
        or arithmetic_survivors != [(17, 70), (70, 17)]
        or combined_survivors
        or minimum_non_full != 1322
        or minimizers != [(27, 44), (44, 27)]
        or sum(item["coefficient"] > 0 for item in variables) != 2
        or sum(item["coefficient"] < 0 for item in variables) != 2082
        or any(item["coefficient"] == 0 for item in variables)
    ):
        raise GateError("complete lex-better band arithmetic drifted")

    strict_metadata = {
        **strict_sentinels,
        "boundary_instances": boundary_count,
        "protocol_core_instances": template_counts["protocol_core"],
        "pole_body_area": pole_body_area,
        "port_occurrences": occurrence_count,
    }
    metadata_facts = {
        "grid": {"width": 70, "height": 70, "area": 4900},
        "objective": {
            "kind": "max_lex_area_min_side",
            "minimum_side": 6,
            "target_area": 1188,
            "target_min_side": 22,
            "orientation": "ordered_width_height",
        },
        "strict_sentinels": strict_metadata,
        "ordinary_membrane": {
            "class_table": [
                {
                    "side_span": span,
                    "active_side_cap": active,
                    "multiplicity": count,
                }
                for (span, active), count in sorted(classes.items())
            ],
            "full_contact_excess": excess,
            "directed_endpoints": directed_endpoints,
            "maximum_endpoint_extra": maximum_endpoint_extra,
            "endpoint_correction": endpoint_correction,
            "twice_k_minus_l_cap": total_excess,
            "manufacturing_boundary_additive_cap": membrane_floor,
            "protocol_core_side_output_cap": 3,
            "generic_final_input_terminals": final_input_count,
            "additional_inside_terminals": inside_addend,
            "inside_terminal_additive_cap": inside_constant,
            "outside_access_incidence_cap": outside_access_incidence_cap,
            "outside_terminal_numerator_constant": ordinary_numerator,
        },
        "power_halo": {key: value for key, value in halo.items() if key != "violations"}
        | {"violation_count": len(halo["violations"])},
        "marked_terminals": {
            "manufacturing_marks": manufacturing_marks,
            "raw_output_slots": provider_slots,
            "raw_noncorner_marks": raw_noncorner_slots,
            "total_marks": total_marks,
            "class_table": [
                {"side_span": span, "marks": marks, "multiplicity": count}
                for (span, marks), count in sorted(marked_classes.items())
            ],
        },
        "access_cell_enumeration": {
            "port_occurrences": occurrence_count,
            "enumeration": {"3": access["t3"], "4": access["t4"]},
            "inequality": "t(z)+m(z)<=4",
        },
        "marked_membrane": {
            "maximum_marks_per_side": maximum_marks,
            "maximum_marked_side": maximum_marked_side,
            **interval_certificate,
            "maximum_partial_contacts": partial_contacts,
            "inside_offset": marked_inside_offset,
            "outside_numerator_constant": marked_numerator,
        },
        "boundary_packing": {
            "required_bodies": boundary_count,
            "anchors_per_supported_boundary": len(anchors),
            "maximum_per_supported_boundary": len(chosen),
            "forced_distribution": [23, 23],
            "occupied_cells_per_supported_boundary": 69,
            "unoccupied_cells_per_supported_boundary": 1,
            "full_span_dimensions_forbidden": True,
        },
        "free_cell_cap": {
            "value": free_cell_cap,
            "identity": "4900 - 3544 - 9 * 4 = 1320",
        },
        "lex_better_band": {
            "width_range": [6, 70],
            "height_range": [6, 70],
            "oriented": True,
            "predicate": ("area > 1188 or (area == 1188 and min(width,height) > 22)"),
            "dimension_count": len(dimensions),
            "area_1188_factor_pairs": [list(pair) for pair in factor_pairs],
            "area_1188_band_pairs": [list(pair) for pair in factor_pairs if pair in dimensions],
            "minimum_side_in_band": min(min(pair) for pair in dimensions),
            "full_span_dimension_count": len(full_span),
            "arithmetic_survivors": [list(pair) for pair in arithmetic_survivors],
            "final_survivors": [list(pair) for pair in combined_survivors],
            "minimum_non_full_total": minimum_non_full,
            "minimum_non_full_dimensions": [list(pair) for pair in minimizers],
        },
        "necessary_inequality": {
            "display": ("wh + max(ceil((580-w-h)/4), ceil((678-2w-2h)/4)) <= 1320"),
            "ordinary_numerator_constant": ordinary_numerator,
            "marked_numerator_constant": marked_numerator,
            "divisor": outside_access_incidence_cap,
            "rhs": free_cell_cap,
            "marked_bound_minimum_side": maximum_marked_side,
        },
    }
    return {
        "strict_sentinels": strict_metadata,
        "class_table": classes,
        "marked_class_table": marked_classes,
        "manufacturing_marks": manufacturing_marks,
        "raw_noncorner_slots": raw_noncorner_slots,
        "total_marks": total_marks,
        "access_cell_enumeration": {
            "port_occurrences": occurrence_count,
            **access,
        },
        "marked_interval_checks": interval_checks,
        "marked_endpoint_pair_checks": endpoint_checks,
        "halo": halo,
        "free_cell_cap": free_cell_cap,
        "boundary_packing": boundary_packing,
        "dimensions": dimensions,
        "factor_pairs": factor_pairs,
        "full_span_dimensions": full_span,
        "arithmetic_survivors": arithmetic_survivors,
        "combined_survivors": combined_survivors,
        "minimum_non_full_span_lhs": minimum_non_full,
        "minimum_non_full_span_lhs_dimensions": minimizers,
        "variables": variables,
        "metadata_facts": metadata_facts,
        "ordinary_constants": {
            "excess": excess,
            "endpoint_correction": endpoint_correction,
            "membrane_floor": membrane_floor,
            "inside_constant": inside_constant,
            "outside_numerator": ordinary_numerator,
        },
        "marked_constants": {
            "maximum_marks": maximum_marks,
            "maximum_marked_side": maximum_marked_side,
            "partial_contacts": partial_contacts,
            "inside_offset": marked_inside_offset,
            "outside_numerator": marked_numerator,
        },
    }


def _counts(facts: Mapping[str, Any]) -> dict[str, int]:
    variables = _array(facts.get("variables"), "facts.variables")
    full_span = sum(_mapping(item, "facts.variable").get("full_span") is True for item in variables)
    positive = sum(
        _exact_int(_mapping(item, "facts.variable").get("coefficient"), "coefficient") > 0 for item in variables
    )
    negative = sum(
        _exact_int(_mapping(item, "facts.variable").get("coefficient"), "coefficient") < 0 for item in variables
    )
    zero = len(variables) - positive - negative
    return {
        "oriented_dimensions": len(variables),
        "selector_variables": len(variables),
        "variables": len(variables),
        "equality_constraints": 1,
        "arithmetic_implication_constraints": len(variables),
        "full_span_forbid_constraints": full_span,
        "constraints": 1 + len(variables) + full_span,
        "arithmetic_survivors": positive + zero,
        "final_survivors": len(_array(facts.get("combined_survivors"), "combined survivors")),
        "positive_arithmetic_coefficients": positive,
        "negative_arithmetic_coefficients": negative,
        "zero_arithmetic_coefficients": zero,
    }


def _constraint_key(
    relation: str,
    rhs: int,
    terms: Iterable[tuple[int, int]],
) -> ConstraintKey:
    if relation not in {"=", ">="} or type(rhs) is not int:
        raise GateError("invalid constraint relation or right-hand side")
    combined: Counter[int] = Counter()
    for variable, coefficient in terms:
        if type(variable) is not int or variable <= 0:
            raise GateError("constraint variable id must be a positive exact integer")
        if type(coefficient) is not int:
            raise GateError("constraint coefficient must be an exact integer")
        combined[variable] += coefficient
    canonical = tuple((variable, combined[variable]) for variable in sorted(combined) if combined[variable] != 0)
    if not canonical:
        raise GateError("constraint must have at least one nonzero term")
    return relation, rhs, canonical


def _build_expected(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Build the expected selector model without using the encoder module."""

    variables = [dict(_mapping(item, "facts.variable")) for item in _array(facts.get("variables"), "facts.variables")]
    constraints: Counter[ConstraintKey] = Counter()
    constraints[
        _constraint_key(
            "=",
            1,
            (
                (
                    _exact_int(item.get("id"), "variable.id"),
                    1,
                )
                for item in variables
            ),
        )
    ] += 1
    for item in variables:
        variable_id = _exact_int(item.get("id"), "variable.id")
        coefficient = _exact_int(item.get("coefficient"), "variable.coefficient")
        constraints[_constraint_key(">=", 0, ((variable_id, coefficient),))] += 1
        if item.get("full_span") is True:
            constraints[_constraint_key(">=", 0, ((variable_id, -1),))] += 1
    counts = _counts(facts)
    if (
        len(variables) != EXPECTED_VARIABLES
        or sum(constraints.values()) != EXPECTED_CONSTRAINTS
        or counts
        != {
            "oriented_dimensions": 2084,
            "selector_variables": 2084,
            "variables": 2084,
            "equality_constraints": 1,
            "arithmetic_implication_constraints": 2084,
            "full_span_forbid_constraints": 107,
            "constraints": 2192,
            "arithmetic_survivors": 2,
            "final_survivors": 0,
            "positive_arithmetic_coefficients": 2,
            "negative_arithmetic_coefficients": 2082,
            "zero_arithmetic_coefficients": 0,
        }
    ):
        raise GateError("expected model size/accounting drifted")
    return {
        "variables": variables,
        "constraints": constraints,
        "counts": counts,
    }


def _parse_opb(raw: bytes) -> dict[str, Any]:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise GateError("OPB is not ASCII") from exc
    if len(lines) < 2:
        raise GateError("OPB is missing its header or provenance comment")
    header_match = HEADER_RE.fullmatch(lines[0])
    header = None
    if header_match is not None:
        header = {
            "variables": int(header_match.group(1)),
            "constraints": int(header_match.group(2)),
            "equalities": int(header_match.group(3)),
            "intsize": int(header_match.group(4)),
        }
    expected_comment = (
        f"* model={MODEL_SCHEMA} generated_by={ENCODER_NAME} "
        f"semantics={SEMANTICS} target=1188,22 "
        "given_inequality=wh+max(ceil((580-w-h)/4),"
        "ceil((678-2w-2h)/4))<=1320 full_span_forbidden=true"
    )
    constraints: Counter[ConstraintKey] = Counter()
    parse_errors: list[str] = []
    for line_number, line in enumerate(lines[2:], start=3):
        match = CONSTRAINT_RE.fullmatch(line)
        if match is None:
            parse_errors.append(f"line {line_number}: malformed constraint")
            continue
        tokens = match.group(1).split()
        if len(tokens) == 0 or len(tokens) % 2:
            parse_errors.append(f"line {line_number}: malformed term list")
            continue
        terms: list[tuple[int, int]] = []
        seen_variables: set[int] = set()
        try:
            for offset in range(0, len(tokens), 2):
                coefficient_token, variable_token = tokens[offset : offset + 2]
                if re.fullmatch(r"[+-]\d+", coefficient_token) is None:
                    raise ValueError
                if re.fullmatch(r"x[1-9]\d*", variable_token) is None:
                    raise ValueError
                coefficient = int(coefficient_token)
                variable = int(variable_token[1:])
                if coefficient == 0 or not (-(2**63) <= coefficient < 2**63):
                    raise ValueError
                if variable in seen_variables or variable > EXPECTED_VARIABLES:
                    raise ValueError
                seen_variables.add(variable)
                terms.append((variable, coefficient))
            rhs = int(match.group(3))
            if not (-(2**63) <= rhs < 2**63):
                raise ValueError
            key = _constraint_key(
                match.group(2),
                rhs,
                terms,
            )
        except (GateError, ValueError):
            parse_errors.append(f"line {line_number}: invalid term")
            continue
        constraints[key] += 1
    return {
        "header": header,
        "comment_exact": lines[1] == expected_comment,
        "constraints": constraints,
        "parse_errors": parse_errors,
        "line_count": len(lines),
    }


def _constraint_display(key: ConstraintKey) -> str:
    relation, rhs, terms = key
    rendered = " ".join(f"{coefficient:+d} x{variable}" for variable, coefficient in terms)
    return f"{rendered} {relation} {rhs} ;"


def _constraint_diff(
    expected: Counter[ConstraintKey],
    actual: Counter[ConstraintKey],
) -> dict[str, Any]:
    missing = expected - actual
    unexpected = actual - expected
    return {
        "missing_examples": [_constraint_display(key) for key in sorted(missing, key=repr)[:5]],
        "missing_total": sum(missing.values()),
        "unexpected_examples": [_constraint_display(key) for key in sorted(unexpected, key=repr)[:5]],
        "unexpected_total": sum(unexpected.values()),
    }


def _planning(opb_bytes: int, user_limit_bytes: int) -> dict[str, Any]:
    bound = max(MINIMUM_PLANNING_BYTES, 1_024 * opb_bytes)
    return {
        "bound_bytes": bound,
        "user_limit_bytes": user_limit_bytes,
        "decision": "GO" if bound <= user_limit_bytes else "NO_GO",
        "basis": {
            "method": "max_512_mib_or_1024_times_projected_opb_bytes",
            "floor_bytes": MINIMUM_PLANNING_BYTES,
            "opb_multiplier": 1_024,
            "projected_opb_bytes": opb_bytes,
        },
    }


def _claim_scope() -> dict[str, Any]:
    return {
        "given_geometric_lemmas": {
            "inside_opb": False,
            "coverage": (
                "the a004-admitted ordinary membrane, conditional marked "
                "membrane, access-cell, power-halo, and boundary full-span lemmas"
            ),
            "trust": "read-only complete replay of the byte-locked a004 admission",
        },
        "arithmetic_band": {
            "inside_opb": True,
            "coverage": ("all 2084 oriented 6<=w,h<=70 dimensions lexicographically better than (1188,22)"),
            "mechanism": (
                "exactly-one selector, one transparent arithmetic implication "
                "per dimension, and one forbid per full-span selector"
            ),
        },
        "combined_statement": (
            "given the a004-admitted geometric lemmas, the complete lex-better dimension band is arithmetically UNSAT"
        ),
        "limitations": [
            "translation only; no solver UNSAT or proof verification claim",
            "does not prove the a004-admitted geometric lemmas",
            "does not provide a witness or prove attainability or global optimality",
            "research artifact; not sealed or production CERTIFIED evidence",
        ],
    }


def _input_records(root: Path) -> tuple[dict[str, bytes], dict[str, dict[str, Any]]]:
    raw_inputs: dict[str, bytes] = {}
    records: dict[str, dict[str, Any]] = {}
    for key, relative in INPUT_PATHS.items():
        path = _canonical_regular(root / relative, f"strict input {key}")
        raw = path.read_bytes()
        raw_inputs[key] = raw
        records[key] = _file_record(path, root)
        if len(raw) != INPUT_SIZE[key] or _sha(raw) != INPUT_SHA256[key]:
            raise GateError(f"strict input {key} bytes drifted")
    if not _verify_sha256_manifest(
        raw_inputs["sha256s"],
        {key: raw_inputs[key] for key in raw_inputs if key != "sha256s"},
    ):
        raise GateError("strict four-entry SHA256SUMS closure failed")
    _strict_json(
        raw_inputs["problem_instance_schema"],
        "problem instance schema",
    )
    return raw_inputs, {key: records[key] for key in sorted(records)}


def _load_json_file(path: Path, field: str) -> tuple[dict[str, Any], bytes]:
    resolved = _canonical_regular(path, field)
    raw = resolved.read_bytes()
    value = _strict_json(raw, field)
    if not isinstance(value, dict):
        raise GateError(f"{field} must contain a JSON object")
    return value, raw


def _record_matches(
    candidate: Any,
    path: Path,
    root: Path,
) -> bool:
    return isinstance(candidate, dict) and _type_exact_equal(
        candidate,
        _file_record(path, root),
    )


def _argv_valid(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(type(item) is str for item in value)


def _semantic_canaries(facts: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    dimensions = list(_array(facts.get("dimensions"), "dimensions"))
    variables = list(_array(facts.get("variables"), "variables"))
    by_dimension = {(item["width"], item["height"]): item for item in variables}
    canaries = {
        "ceil_signed_edges": {
            "pass": (
                _ceil_div(1, 4),
                _ceil_div(-1, 4),
                _ceil_div(-5, 4),
            )
            == (1, 0, -1)
        },
        "oriented_tie_break": {
            "pass": [list(pair) for pair in dimensions if pair[0] * pair[1] == TARGET_AREA]
            == [[27, 44], [33, 36], [36, 33], [44, 27]]
        },
        "full_span_survivor_closure": {
            "pass": [
                [item["width"], item["height"]] for item in variables if item["coefficient"] >= 0 and item["full_span"]
            ]
            == [[17, 70], [70, 17]]
        },
        "non_full_ceiling": {
            "pass": (
                facts.get("minimum_non_full_span_lhs") == 1322
                and facts.get("minimum_non_full_span_lhs_dimensions") == [(27, 44), (44, 27)]
            )
        },
        "decisive_dimension_points": {
            "pass": {
                pair: (
                    by_dimension[pair]["access_lower_bound"],
                    by_dimension[pair]["total_required_cells"],
                    by_dimension[pair]["coefficient"],
                )
                for pair in ((34, 35), (29, 41), (17, 70))
            }
            == {
                (34, 35): (135, 1325, -5),
                (29, 41): (135, 1324, -4),
                (17, 70): (126, 1316, 4),
            }
        },
    }
    return canaries


def verify_translation(
    *,
    project_root: Path,
    opb_path: Path,
    meta_path: Path,
    var_map_path: Path,
    estimate_path: Path,
) -> dict[str, Any]:
    """Return a complete fail-closed translation report."""

    root = project_root.resolve(strict=True)
    if root != PROJECT_ROOT.resolve(strict=True):
        raise GateError("--project-root must identify this repository")
    raw_inputs, input_records = _input_records(root)
    authority = _replay_a004(root)
    git_snapshot = _git_snapshot(root)
    encoder_record = _file_record(ENCODER_SOURCE, root)
    gate_record = _file_record(GATE_SOURCE, root)
    facts = _derive(_strict_json(raw_inputs["problem_instance"], "problem instance"))
    expected = _build_expected(facts)
    expected_counts = expected["counts"]

    opb_resolved = _canonical_regular(opb_path, "OPB")
    meta_resolved = _canonical_regular(meta_path, "metadata")
    map_resolved = _canonical_regular(var_map_path, "variable map")
    estimate_resolved = _canonical_regular(estimate_path, "estimate")
    opb_raw = opb_resolved.read_bytes()
    metadata, meta_raw = _load_json_file(meta_resolved, "metadata")
    variable_map, map_raw = _load_json_file(map_resolved, "variable map")
    estimate, estimate_raw = _load_json_file(estimate_resolved, "estimate")
    loaded_translation_records = {
        "estimate": {
            "path": _file_record(estimate_resolved, root)["path"],
            "sha256": _sha(estimate_raw),
            "size_bytes": len(estimate_raw),
        },
        "meta": {
            "path": _file_record(meta_resolved, root)["path"],
            "sha256": _sha(meta_raw),
            "size_bytes": len(meta_raw),
        },
        "opb": {
            "path": _file_record(opb_resolved, root)["path"],
            "sha256": _sha(opb_raw),
            "size_bytes": len(opb_raw),
        },
        "var_map": {
            "path": _file_record(map_resolved, root)["path"],
            "sha256": _sha(map_raw),
            "size_bytes": len(map_raw),
        },
    }
    parsed = _parse_opb(opb_raw)

    metadata_keys = {
        "schema_version",
        "model_schema_version",
        "variable_map_schema_version",
        "semantics",
        "harness",
        "argv",
        "project_root",
        "harness_source",
        "inputs",
        "upstream_authority",
        "git_snapshot",
        "estimate",
        "derived_facts",
        "counts",
        "outputs",
        "claim_scope",
        "proof_status",
    }
    estimate_keys = {
        "schema_version",
        "model_schema_version",
        "metadata_schema_version",
        "variable_map_schema_version",
        "semantics",
        "harness",
        "argv",
        "project_root",
        "harness_source",
        "inputs",
        "upstream_authority",
        "git_snapshot",
        "derived_facts",
        "counts",
        "projected_outputs",
        "proof_size_planning",
    }
    map_keys = {
        "schema_version",
        "model_schema_version",
        "semantics",
        "variable_count",
        "variables",
    }
    outputs = metadata.get("outputs")
    outputs_map = outputs if isinstance(outputs, dict) else {}
    translation_inputs_closed = (
        set(metadata) == metadata_keys
        and set(estimate) == estimate_keys
        and set(variable_map) == map_keys
        and set(outputs_map) == {"opb", "var_map", "metadata"}
        and _record_matches(outputs_map.get("opb"), opb_resolved, root)
        and _record_matches(outputs_map.get("var_map"), map_resolved, root)
        and _type_exact_equal(
            outputs_map.get("metadata"),
            {"path": str(meta_resolved.absolute())},
        )
        and _record_matches(metadata.get("estimate"), estimate_resolved, root)
    )
    encoder_provenance = (
        metadata.get("harness") == ENCODER_NAME
        and estimate.get("harness") == ENCODER_NAME
        and _type_exact_equal(metadata.get("harness_source"), encoder_record)
        and _type_exact_equal(estimate.get("harness_source"), encoder_record)
        and metadata.get("project_root") == str(root)
        and estimate.get("project_root") == str(root)
        and _type_exact_equal(metadata.get("git_snapshot"), git_snapshot)
        and _type_exact_equal(estimate.get("git_snapshot"), git_snapshot)
        and _argv_valid(metadata.get("argv"))
        and _argv_valid(estimate.get("argv"))
    )
    common_identity = (
        metadata.get("model_schema_version") == MODEL_SCHEMA
        and estimate.get("model_schema_version") == MODEL_SCHEMA
        and variable_map.get("model_schema_version") == MODEL_SCHEMA
        and metadata.get("semantics") == SEMANTICS
        and estimate.get("semantics") == SEMANTICS
        and variable_map.get("semantics") == SEMANTICS
        and _type_exact_equal(metadata.get("inputs"), input_records)
        and _type_exact_equal(estimate.get("inputs"), input_records)
        and _type_exact_equal(metadata.get("upstream_authority"), authority)
        and _type_exact_equal(estimate.get("upstream_authority"), authority)
    )
    metadata_reconstruction = (
        common_identity
        and metadata.get("schema_version") == METADATA_SCHEMA
        and metadata.get("variable_map_schema_version") == VAR_MAP_SCHEMA
        and _type_exact_equal(metadata.get("derived_facts"), facts["metadata_facts"])
        and _type_exact_equal(metadata.get("counts"), expected_counts)
        and _type_exact_equal(metadata.get("claim_scope"), _claim_scope())
        and metadata.get("proof_status") == "translation_only_no_unsat_or_proof_claim"
    )
    planning = estimate.get("proof_size_planning")
    planning_valid = False
    if isinstance(planning, dict):
        limit = planning.get("user_limit_bytes")
        if type(limit) is int and limit > 0:
            planning_valid = _type_exact_equal(
                planning,
                _planning(len(opb_raw), limit),
            )
    estimate_reconstruction = (
        common_identity
        and estimate.get("schema_version") == ESTIMATE_SCHEMA
        and estimate.get("metadata_schema_version") == METADATA_SCHEMA
        and estimate.get("variable_map_schema_version") == VAR_MAP_SCHEMA
        and _type_exact_equal(estimate.get("derived_facts"), facts["metadata_facts"])
        and _type_exact_equal(estimate.get("counts"), expected_counts)
        and _type_exact_equal(
            estimate.get("projected_outputs"),
            {"opb_bytes": len(opb_raw)},
        )
        and planning_valid
    )

    actual_variables = variable_map.get("variables")
    actual_variable_list = actual_variables if isinstance(actual_variables, list) else []
    actual_ids = [item.get("id") if isinstance(item, dict) else None for item in actual_variable_list]
    variable_dense = (
        variable_map.get("schema_version") == VAR_MAP_SCHEMA
        and type(variable_map.get("variable_count")) is int
        and variable_map.get("variable_count") == EXPECTED_VARIABLES
        and len(actual_variable_list) == EXPECTED_VARIABLES
        and all(type(value) is int for value in actual_ids)
        and actual_ids == list(range(1, EXPECTED_VARIABLES + 1))
    )
    variable_exact = _type_exact_equal(
        actual_variable_list,
        expected["variables"],
    )
    expected_header = {
        "variables": EXPECTED_VARIABLES,
        "constraints": EXPECTED_CONSTRAINTS,
        "equalities": EXPECTED_EQUALITIES,
        "intsize": 64,
    }
    header_exact = parsed["header"] == expected_header and parsed["comment_exact"] and not parsed["parse_errors"]
    diff = _constraint_diff(expected["constraints"], parsed["constraints"])
    constraint_exact = not parsed["parse_errors"] and diff["missing_total"] == 0 and diff["unexpected_total"] == 0
    canaries = _semantic_canaries(facts)
    checks = {
        "a004_admission_replay_pass": True,
        "strict_bundle_closed_and_hashed": True,
        "encoder_provenance_match": encoder_provenance,
        "translation_inputs_closed_and_hashed": translation_inputs_closed,
        "metadata_reconstruction_match": metadata_reconstruction,
        "estimate_reconstruction_match": estimate_reconstruction,
        "variable_map_dense": variable_dense,
        "variable_map_exact": variable_exact,
        "opb_header_exact": header_exact,
        "constraint_multiset_exact": constraint_exact,
        "strict_sentinels_exact": facts["strict_sentinels"]["total_active_terminals"] == 628,
        "ordinary_membrane_exact": facts["ordinary_constants"]
        == {
            "excess": 63,
            "endpoint_correction": 24,
            "membrane_floor": 43,
            "inside_constant": 48,
            "outside_numerator": 580,
        },
        "power_halo_exact": (
            facts["halo"]["total_weight"] == 396
            and facts["halo"]["placement_count"] == 840
            and facts["halo"]["minimum_poles"] == 9
            and facts["halo"]["violations"] == []
        ),
        "marked_terminal_census_exact": (
            facts["manufacturing_marks"],
            facts["raw_noncorner_slots"],
            facts["total_marks"],
        )
        == (58, 52, 110),
        "access_cell_enumeration_exact": (
            facts["access_cell_enumeration"]["port_occurrences"] == 178
            and facts["access_cell_enumeration"]["t3"]["nonoverlap_combinations"] == 30_080
            and facts["access_cell_enumeration"]["t4"]["nonoverlap_combinations"] == 8_192
        ),
        "marked_membrane_exact": facts["marked_constants"]
        == {
            "maximum_marks": 3,
            "maximum_marked_side": 9,
            "partial_contacts": 8,
            "inside_offset": 12,
            "outside_numerator": 678,
        },
        "boundary_packing_exact": facts["boundary_packing"]
        == {
            "anchors_per_supported_side": 68,
            "maximum_per_supported_side": 23,
            "forced_distribution": [23, 23],
            "occupied_cells_per_supported_side": 69,
        },
        "lex_better_band_exact": (
            len(facts["dimensions"]) == EXPECTED_VARIABLES and len(facts["full_span_dimensions"]) == EXPECTED_FULL_SPAN
        ),
        "complete_band_corpus_unsat": facts["combined_survivors"] == [],
        "semantic_canaries_pass": all(item["pass"] is True for item in canaries.values()),
    }
    if set(checks) != REQUIRED_CHECKS:
        raise GateError("translation check set drifted")
    corpus_errors = [
        f"variable {index + 1} differs"
        for index, (actual, expected_item) in enumerate(zip(actual_variable_list, expected["variables"]))
        if not _type_exact_equal(actual, expected_item)
    ]
    if len(actual_variable_list) != len(expected["variables"]):
        corpus_errors.append("variable-map length differs")
    current_translation_records = {
        "estimate": _file_record(estimate_resolved, root),
        "meta": _file_record(meta_resolved, root),
        "opb": _file_record(opb_resolved, root),
        "var_map": _file_record(map_resolved, root),
    }
    if not _type_exact_equal(
        current_translation_records,
        loaded_translation_records,
    ):
        raise GateError("translation input changed during gate replay")
    return {
        "schema_version": GATE_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "metadata_schema_version": METADATA_SCHEMA,
        "variable_map_schema_version": VAR_MAP_SCHEMA,
        "semantics": SEMANTICS,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "project_root": str(root),
        "inputs": {
            "opb": _file_record(opb_resolved, root),
            "metadata": _file_record(meta_resolved, root),
            "variable_map": _file_record(map_resolved, root),
            "estimate": _file_record(estimate_resolved, root),
            "strict": input_records,
        },
        "upstream_authority": authority,
        "git_snapshot": git_snapshot,
        "encoder_git_snapshot": metadata.get("git_snapshot"),
        "encoder_source": encoder_record,
        "gate_source": gate_record,
        "strict_inputs": input_records,
        "translation_inputs": current_translation_records,
        "corpus_count": len(expected["variables"]),
        "arithmetic_survivors": [list(pair) for pair in facts["arithmetic_survivors"]],
        "full_span_rejections_of_arithmetic_survivors": [
            list(pair) for pair in facts["arithmetic_survivors"] if 70 in pair
        ],
        "corpus_errors": corpus_errors[:20],
        "minimum_non_full_span_lhs": facts["minimum_non_full_span_lhs"],
        "minimum_non_full_span_lhs_dimensions": [list(pair) for pair in facts["minimum_non_full_span_lhs_dimensions"]],
        "constraint_diff": diff,
        "opb_parse_errors": parsed["parse_errors"],
        "semantic_canaries": canaries,
        "claim_scope": _claim_scope(),
        "proof_status": "translation_gate_only_no_unsat_or_proof_claim",
    }


def _canonical_output(path: Path) -> Path:
    absolute = path.absolute()
    try:
        parent_mode = absolute.parent.lstat().st_mode
        parent = absolute.parent.resolve(strict=True)
    except OSError as exc:
        raise GateError(f"cannot resolve output parent: {exc}") from exc
    if stat.S_ISLNK(parent_mode) or not stat.S_ISDIR(parent_mode) or parent != absolute.parent:
        raise GateError("output parent must be a canonical non-symlink directory")
    if absolute.exists() or absolute.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing output: {absolute}")
    if absolute.resolve(strict=False) != absolute:
        raise GateError("output target path is not canonical")
    return absolute


def _exclusive_json(path: Path, payload: Any) -> None:
    target = _canonical_output(path)
    raw = (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with target.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--opb", type=Path, required=True)
    parser.add_argument("--meta", type=Path, required=True)
    parser.add_argument("--var-map", type=Path, required=True)
    parser.add_argument("--estimate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = _canonical_output(args.output)
    try:
        report = verify_translation(
            project_root=args.project_root,
            opb_path=args.opb,
            meta_path=args.meta,
            var_map_path=args.var_map,
            estimate_path=args.estimate,
        )
    except (GateError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        report = {
            "schema_version": GATE_SCHEMA,
            "semantics": SEMANTICS,
            "status": "FAIL",
            "checks": {name: False for name in sorted(REQUIRED_CHECKS)},
            "errors": [f"{type(exc).__name__}: {exc}"],
            "claim_scope": _claim_scope(),
            "proof_status": "translation_gate_only_no_unsat_or_proof_claim",
        }
    # The target was already validated above; the exclusive writer rechecks it.
    _exclusive_json(output, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "output": str(output),
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
