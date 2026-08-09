#!/usr/bin/env python3
"""Build the admitted R4 ``(1188, 22)`` upper-candidate arithmetic OPB.

This research-only producer treats the byte-locked R4 a004 admission as its
only upstream authority.  It read-only replays that complete admission chain,
independently rebuilds the strict-instance arithmetic, and emits a transparent
finite selector model.  It does not prove the admitted geometric lemmas and
does not itself establish UNSAT, a witness, attainability, or optimality.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
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
import time
from types import ModuleType
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESEARCH_DIR = Path(__file__).resolve().parent
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "track_b_b1_r4_1188_22_pb_20260723"

MODEL_SCHEMA = "b1_r4_1188_22_pb_v1"
METADATA_SCHEMA = "b1_r4_1188_22_pb_metadata_v1"
VAR_MAP_SCHEMA = "b1_r4_1188_22_pb_var_map_v1"
ESTIMATE_SCHEMA = "b1_r4_1188_22_pb_estimate_v1"
GATE_SCHEMA = "b1_r4_1188_22_pb_translation_gate_v1"
BUILD_RECORD_SCHEMA = "b1_r4_1188_22_pb_build_record_v1"
SEMANTICS = "b1_r4_1188_22_complete_oriented_lex_better_band_given_a004_admitted_lemmas_v1"
HARNESS = "b1_r4_1188_22_pb_encoder_v1"

EXPECTED_GIT_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
TARGET_AREA = 1_188
TARGET_MIN_SIDE = 22
GRID_SIDE = 70
MINIMUM_SIDE = 6
FREE_CELL_CAP = 1_320
ORDINARY_NUMERATOR = 580
MARKED_NUMERATOR = 678
INCIDENCE_CAP = 4
EXPECTED_VARIABLES = 2_084
EXPECTED_CONSTRAINTS = 2_192
EXPECTED_FULL_SPAN = 107
PROOF_LIMIT_BYTES = 5_000_000_000
PLANNING_FLOOR_BYTES = 512 * 1024 * 1024
PLANNING_OPB_MULTIPLIER = 1_024
GATE_TIMEOUT_SECONDS = 300
FIXED_PYTHON = PROJECT_ROOT / ".venv-uvbolt-backup/bin/python"
FIXED_PYTHON_SHA256 = "74fceb0fdd29c31cf066ac8d92465975ea4ac8592308d7c888e26a70092d8eeb"

REQUIRED_GATE_CHECKS = frozenset(
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
BUILD_PAYLOAD_NAMES = frozenset(
    {
        "estimate.json",
        "formula.opb",
        "encoder.meta.json",
        "variable_map.json",
        "translation_gate.json",
        "estimate.stdout.txt",
        "estimate.stderr.txt",
        "encode.stdout.txt",
        "encode.stderr.txt",
        "translation_gate.stdout.txt",
        "translation_gate.stderr.txt",
    }
)

STRICT_ROOT = Path("docs/research/cleanroom_rederivation_20260718/strict/external")
INPUT_PATHS = {
    "problem_instance": STRICT_ROOT / "problem_instance.json",
    "problem_instance_schema": STRICT_ROOT / "problem_instance.schema.json",
    "problem_md": STRICT_ROOT / "problem.md",
    "sha256s": STRICT_ROOT / "SHA256SUMS",
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

R4_REVIEW_DIR = Path("docs/research/r4_response_review_20260723")
ADMISSION_CLOSER = R4_REVIEW_DIR / "close_r4_response_candidate_admission_v2.py"
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

EXPECTED_ORDINARY_CLASSES = Counter(
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
EXPECTED_MARKED_CLASSES = Counter(
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
ATTEMPT_RE = re.compile(r"build-a(?P<number>[0-9]{3})-(?P<timestamp>[0-9]{8}T[0-9]{6}Z)-398f8725")


class EncoderError(ValueError):
    """Raised when an authority, derivation, or output contract fails."""


@dataclass(frozen=True, slots=True)
class Snapshot:
    key: str
    path: Path
    display_path: str
    raw: bytes
    sha256: str

    @property
    def text(self) -> str:
        return self.raw.decode("utf-8")

    def record(self) -> dict[str, Any]:
        return {
            "path": self.display_path,
            "sha256": self.sha256,
            "size_bytes": len(self.raw),
        }


@dataclass(frozen=True, slots=True)
class Constraint:
    terms: tuple[tuple[int, int], ...]
    relation: str
    rhs: int

    def render(self) -> str:
        body = " ".join(
            f"{'+' if coefficient >= 0 else ''}{coefficient} x{variable}" for variable, coefficient in self.terms
        )
        return f"{body} {self.relation} {self.rhs} ;"


class VariableRecord(dict[str, Any]):
    """JSON selector record with typed dimension access for audits/tests."""

    @property
    def width(self) -> int:
        return int(self["width"])

    @property
    def height(self) -> int:
        return int(self["height"])


@dataclass(slots=True)
class DerivedModel:
    variables: list[VariableRecord]
    constraints: list[Constraint]
    derived_facts: dict[str, Any]
    counts: dict[str, int]


def _exact_int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise EncoderError(f"{field} must be an exact integer")
    return int(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EncoderError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise EncoderError(f"{field} must be an array")
    return value


def _expect(value: Any, expected: Any, field: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise EncoderError(f"{field} must be {expected!r}, got {value!r}")


def _one(values: Iterable[Any], field: str) -> Any:
    unique = set(values)
    if len(unique) != 1:
        raise EncoderError(f"{field} must have one invariant value")
    return next(iter(unique))


def _reject_constant(value: str) -> Any:
    raise EncoderError(f"non-finite JSON number is forbidden: {value}")


def _reject_float(value: str) -> Any:
    raise EncoderError(f"floating-point JSON number is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EncoderError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads_strict_json(raw: str | bytes, field: str = "JSON") -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EncoderError(f"{field} is not strict JSON: {exc}") from exc


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _display_path(path: Path, root: Path) -> str:
    resolved = path.resolve(strict=True)
    try:
        return str(resolved.relative_to(root.resolve(strict=True)))
    except ValueError:
        return str(resolved)


def _canonical_regular(path: Path, field: str) -> Path:
    absolute = path.absolute()
    try:
        mode = absolute.lstat().st_mode
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise EncoderError(f"cannot resolve {field}: {exc}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode) or resolved != absolute:
        raise EncoderError(f"{field} must be a canonical non-symlink regular file")
    return resolved


def _canonical_directory(path: Path, field: str) -> Path:
    absolute = path.absolute()
    try:
        mode = absolute.lstat().st_mode
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise EncoderError(f"cannot resolve {field}: {exc}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode) or resolved != absolute:
        raise EncoderError(f"{field} must be a canonical non-symlink directory")
    return resolved


def _file_record(path: Path, root: Path) -> dict[str, Any]:
    resolved = _canonical_regular(path, str(path))
    raw = resolved.read_bytes()
    return {
        "path": _display_path(resolved, root),
        "sha256": _sha256_bytes(raw),
        "size_bytes": len(raw),
    }


def _absolute_record(path: Path) -> dict[str, Any]:
    resolved = _canonical_regular(path, str(path))
    raw = resolved.read_bytes()
    return {
        "path": str(resolved),
        "sha256": _sha256_bytes(raw),
        "size_bytes": len(raw),
    }


def _snapshot(key: str, path: Path, root: Path) -> Snapshot:
    resolved = _canonical_regular(path, key)
    raw = resolved.read_bytes()
    return Snapshot(
        key=key,
        path=resolved,
        display_path=_display_path(resolved, root),
        raw=raw,
        sha256=_sha256_bytes(raw),
    )


def _git_bytes(root: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
    ).stdout


def _git_snapshot(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    head = _git_bytes(root, "rev-parse", "HEAD").decode("ascii").strip()
    if head != EXPECTED_GIT_HEAD:
        raise EncoderError(f"Git HEAD drifted: {head!r}")
    exclude = ":(exclude).artifacts/track_b_b1_r4_1188_22_pb_20260723/**"
    diff = _git_bytes(
        root,
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "HEAD",
        "--",
        ".",
        exclude,
    )
    status_bytes = _git_bytes(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=normal",
        "--",
        ".",
        exclude,
    )
    return {
        "head": head,
        "tracked_dirty": bool(diff),
        "tracked_diff_sha256": _sha256_bytes(diff),
        "tracked_diff_size_bytes": len(diff),
        "status_dirty": bool(status_bytes),
        "status_sha256": _sha256_bytes(status_bytes),
        "status_size_bytes": len(status_bytes),
        "artifact_exclusion": ".artifacts/track_b_b1_r4_1188_22_pb_20260723/**",
    }


def _load_module(path: Path) -> ModuleType:
    source = _canonical_regular(path, "a004 admission closer")
    spec = importlib.util.spec_from_file_location(
        "_b1_r4_a004_admission_replay_encoder",
        source,
    )
    if spec is None or spec.loader is None:
        raise EncoderError("cannot load the a004 admission closer")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def replay_a004(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve(strict=True)
    if root != PROJECT_ROOT.resolve(strict=True):
        raise EncoderError("--project-root must identify this repository")
    _git_snapshot(root)
    closer_path = root / ADMISSION_CLOSER
    closer = _absolute_record(closer_path)
    if closer["sha256"] != ADMISSION_CLOSER_SHA256 or closer["size_bytes"] != ADMISSION_CLOSER_SIZE:
        raise EncoderError("a004 admission closer bytes drifted")
    admission_path = root / A004_ADMISSION
    admission_record = _absolute_record(admission_path)
    if admission_record["sha256"] != A004_ADMISSION_SHA256 or admission_record["size_bytes"] != A004_ADMISSION_SIZE:
        raise EncoderError("a004 admission bytes drifted")
    module = _load_module(closer_path)
    replay = module.replay_admission(
        root / AUTHORITY_RUN,
        root / RESPONSE_RUN,
        root / A004_LEDGER,
        [root / path for path in A004_REPORTS],
        root / A004_VERDICT,
        admission_path,
    )
    if not isinstance(replay, Mapping) or set(replay) != {
        "admission",
        "verdict_replay",
        "admission_record",
    }:
        raise EncoderError("a004 replay returned an unexpected closed shape")
    admission = _mapping(replay["admission"], "a004 admission")
    upper = _mapping(
        _mapping(admission.get("candidates"), "a004 candidates").get("upper_bound_1188_22"),
        "a004 upper candidate",
    )
    expected_upper = {
        "verdict": "PASS",
        "research_followup_admitted": True,
        "b1_followup_input_admitted": True,
        "proposed_upper_ledger": [1188, 22],
    }
    if dict(upper) != expected_upper:
        raise EncoderError("a004 does not admit the (1188,22) B1 follow-up")
    if admission.get("status") != "PARTIAL":
        raise EncoderError("a004 overall status drifted")
    if admission.get("current_project_ledger") != {"U": [1190, 34], "L": "absent"}:
        raise EncoderError("a004 current project ledger drifted")
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
        raise EncoderError("a004 safety or authorization fields drifted")
    if replay.get("admission_record") != admission_record:
        raise EncoderError("a004 replay admission byte record drifted")
    return {
        "admission": admission_record,
        "admission_closer": closer,
        "replay_summary": {
            "status": admission["status"],
            "upper_candidate": expected_upper,
            "current_project_ledger": {"U": [1190, 34], "L": "absent"},
            "false_fields": {field: False for field in false_fields},
        },
    }


def load_bound_snapshots(
    project_root: Path,
) -> tuple[dict[str, Snapshot], dict[str, Any]]:
    root = project_root.resolve(strict=True)
    inputs = {key: _snapshot(key, root / relative, root) for key, relative in INPUT_PATHS.items()}
    for key, snapshot in inputs.items():
        if snapshot.sha256 != INPUT_SHA256[key] or len(snapshot.raw) != INPUT_SIZE[key]:
            raise EncoderError(f"strict input {key} bytes drifted")
    manifest_lines = inputs["sha256s"].text.splitlines()
    manifest: dict[str, str] = {}
    for line in manifest_lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if match is None or match.group(2) in manifest:
            raise EncoderError("strict SHA256SUMS is malformed or duplicated")
        manifest[match.group(2)] = match.group(1)
    expected_manifest = {
        "R1_prompt.md": ("5154e299b472e0f3c50507fa2820e86b480789f50e2608f4d8ca455cefb7c916"),
        "problem_instance.json": INPUT_SHA256["problem_instance"],
        "problem_instance.schema.json": INPUT_SHA256["problem_instance_schema"],
        "problem.md": INPUT_SHA256["problem_md"],
    }
    if manifest != expected_manifest:
        raise EncoderError("strict SHA256SUMS does not match the four-entry bundle")
    loads_strict_json(inputs["problem_instance_schema"].raw, "problem instance schema")
    authority = replay_a004(root)
    return inputs, authority


def _mode_area(template: Mapping[str, Any], field: str) -> int:
    areas: list[int] = []
    for index, raw_mode in enumerate(_array(template.get("modes"), f"{field}.modes")):
        body = _mapping(_mapping(raw_mode, f"{field}.modes[{index}]").get("body"), f"{field}.body")
        width = _exact_int(body.get("width"), f"{field}.body.width")
        height = _exact_int(body.get("height"), f"{field}.body.height")
        if width <= 0 or height <= 0:
            raise EncoderError(f"{field} has nonpositive body dimensions")
        areas.append(width * height)
    return _exact_int(_one(areas, f"{field} body area"), f"{field} body area")


def _side_length(mode: Mapping[str, Any], port: Mapping[str, Any], field: str) -> int:
    body = _mapping(mode.get("body"), f"{field}.body")
    direction = port.get("direction")
    if direction not in STEPS:
        raise EncoderError(f"{field} has a non-cardinal port direction")
    return _exact_int(
        body.get("width" if direction in {"N", "S"} else "height"),
        f"{field}.side",
    )


def _is_corner(mode: Mapping[str, Any], port: Mapping[str, Any], field: str) -> bool:
    body = _mapping(mode.get("body"), f"{field}.body")
    cell = _mapping(port.get("body_cell"), f"{field}.body_cell")
    width = _exact_int(body.get("width"), f"{field}.width")
    height = _exact_int(body.get("height"), f"{field}.height")
    x = _exact_int(cell.get("x"), f"{field}.x")
    y = _exact_int(cell.get("y"), f"{field}.y")
    return x in {0, width - 1} and y in {0, height - 1}


def _validate_port(
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
        raise EncoderError(f"{field} kind/direction is invalid")
    if not (0 <= x < width and 0 <= y < height):
        raise EncoderError(f"{field} body cell is outside the body")
    on_edge = {
        "N": y == height - 1,
        "E": x == width - 1,
        "S": y == 0,
        "W": x == 0,
    }[str(direction)]
    if not on_edge:
        raise EncoderError(f"{field} body cell is not on its declared body edge")
    return x, y, str(direction)


def _need_total(group: Mapping[str, Any], plural: str, field: str) -> int:
    needs = _mapping(
        _mapping(group.get("port_needs"), f"{field}.port_needs").get(plural),
        f"{field}.{plural}",
    )
    total = sum(_exact_int(value, f"{field}.{plural}.{key}") for key, value in needs.items())
    if total < 0:
        raise EncoderError(f"{field}.{plural} is negative")
    return total


def ceil_div(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise EncoderError("ceil divisor must be positive")
    return -((-numerator) // denominator)


def _halo_weight2(x: int, y: int) -> int:
    key = tuple(sorted((abs(2 * x - 1), abs(2 * y - 1)), reverse=True))
    return HALO_DOUBLED_WEIGHTS.get(key, 0)


def _derive_halo(
    powered_shapes: set[tuple[int, int]],
    coverage: Mapping[str, Any],
    pole_shape: tuple[int, int],
    powered_area: int,
) -> dict[str, Any]:
    x_min = _exact_int(coverage.get("x_min_offset"), "power.x_min_offset")
    x_max = _exact_int(coverage.get("x_max_offset"), "power.x_max_offset")
    y_min = _exact_int(coverage.get("y_min_offset"), "power.y_min_offset")
    y_max = _exact_int(coverage.get("y_max_offset"), "power.y_max_offset")
    if (x_min, x_max, y_min, y_max) != (-5, 6, -5, 6):
        raise EncoderError("power coverage offsets drifted")
    pole_width, pole_height = pole_shape
    pole_cells = {(x, y) for x in range(pole_width) for y in range(pole_height)}
    placement_counts: dict[str, int] = {}
    violations: list[dict[str, Any]] = []
    minimum_slack2: int | None = None
    for width, height in sorted(powered_shapes):
        count = 0
        for anchor_x in range(x_min - width + 1, x_max + 1):
            for anchor_y in range(y_min - height + 1, y_max + 1):
                cells = {(anchor_x + x, anchor_y + y) for x in range(width) for y in range(height)}
                if cells & pole_cells:
                    continue
                count += 1
                slack2 = sum(_halo_weight2(x, y) for x, y in cells) - 2 * len(cells)
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
    total_weight2 = sum(_halo_weight2(x, y) for x in range(-20, 21) for y in range(-20, 21))
    if total_weight2 % 2:
        raise EncoderError("halo doubled weight is not even")
    total_weight = total_weight2 // 2
    return {
        "orbit_count": len(HALO_DOUBLED_WEIGHTS),
        "doubled_weights": [
            {"u": u, "v": v, "weight2": value} for (u, v), value in sorted(HALO_DOUBLED_WEIGHTS.items())
        ],
        "total_weight2": total_weight2,
        "total_weight": total_weight,
        "body_dimensions": [list(pair) for pair in sorted(powered_shapes)],
        "placement_counts": placement_counts,
        "placement_count": sum(placement_counts.values()),
        "violations": violations,
        "minimum_slack2": minimum_slack2,
        "powered_area": powered_area,
        "minimum_poles": ceil_div(powered_area, total_weight),
    }


def _port_occurrences(
    templates: Mapping[str, Any],
) -> tuple[list[tuple[str, bool, frozenset[tuple[int, int]]]], dict[str, Any]]:
    occurrences: list[tuple[str, bool, frozenset[tuple[int, int]]]] = []
    for template_name, raw_template in templates.items():
        if type(template_name) is not str:
            raise EncoderError("facility template names must be strings")
        template = _mapping(raw_template, f"templates.{template_name}")
        for mode_index, raw_mode in enumerate(_array(template.get("modes"), f"templates.{template_name}.modes")):
            mode = _mapping(raw_mode, f"{template_name}.modes[{mode_index}]")
            body = _mapping(mode.get("body"), f"{template_name}.body")
            width = _exact_int(body.get("width"), f"{template_name}.width")
            height = _exact_int(body.get("height"), f"{template_name}.height")
            keys: list[tuple[int, int, str]] = []
            for port_index, raw_port in enumerate(_array(mode.get("ports"), f"{template_name}.ports")):
                port = _mapping(raw_port, f"{template_name}.ports[{port_index}]")
                x, y, direction = _validate_port(
                    mode,
                    port,
                    f"{template_name}.modes[{mode_index}].ports[{port_index}]",
                )
                keys.append((x, y, direction))
                dx, dy = STEPS[direction]
                anchor_x, anchor_y = -dx - x, -dy - y
                cells = frozenset(
                    (anchor_x + body_x, anchor_y + body_y) for body_x in range(width) for body_y in range(height)
                )
                occurrences.append((direction, not _is_corner(mode, port, template_name), cells))
            if len(keys) != len(set(keys)):
                raise EncoderError(f"{template_name} has duplicate physical port keys")
    by_direction = {direction: [item for item in occurrences if item[0] == direction] for direction in STEPS}
    enumeration: dict[str, Any] = {}
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
                    raise EncoderError("t(z)+m(z)<=4 has a counterexample")
        enumeration[str(terminal_count)] = {
            "combinations_checked": checked,
            "nonoverlap_combinations": nonoverlap,
            "maximum_noncorner_marks": maximum_marks,
        }
    return occurrences, enumeration


def _marked_interval_certificate(
    patterns: set[tuple[int, int]],
    maximum_marks: int,
) -> dict[str, int]:
    interval_checks = 0
    endpoint_pair_checks = 0
    maximum_body_disjoint_crossers = 0
    for edge in range(MINIMUM_SIDE, GRID_SIDE + 1):
        partial: dict[int, list[tuple[int, int]]] = {0: [], edge - 1: []}
        for length, marks in sorted(patterns):
            for start in range(-length + 1, edge):
                overlap = [position for position in range(length) if 0 <= start + position < edge]
                full = len(overlap) == length
                for selected in itertools.combinations(range(length), marks):
                    exposed = sum(position in overlap for position in selected)
                    limit = len(overlap) if full else len(overlap) + marks
                    if 2 * exposed > limit:
                        raise EncoderError("marked-contact interval inequality failed")
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
                    raise EncoderError("marked endpoint overlap certificate failed")
                if max(first[0], second[0]) > min(first[1], second[1]):
                    raise EncoderError("endpoint crossers could be body-disjoint")
                endpoint_pair_checks += 1
    return {
        "interval_checks": interval_checks,
        "endpoint_pair_checks": endpoint_pair_checks,
        "maximum_body_disjoint_crossers_per_endpoint": maximum_body_disjoint_crossers,
        "directed_side_count": len(STEPS),
        "endpoints_per_directed_side": 2,
        "directed_endpoint_count": 2 * len(STEPS),
        "maximum_marks_per_partial_contact": maximum_marks,
    }


def _canonical_constraint(
    terms: Iterable[tuple[int, int]],
    relation: str,
    rhs: int,
) -> Constraint:
    combined: Counter[int] = Counter()
    for variable, coefficient in terms:
        if type(variable) is not int or variable <= 0:
            raise EncoderError("constraint variable id must be a positive exact integer")
        if type(coefficient) is not int:
            raise EncoderError("constraint coefficient must be an exact integer")
        combined[variable] += coefficient
    canonical = tuple((variable, combined[variable]) for variable in sorted(combined) if combined[variable] != 0)
    if relation not in {"=", ">="} or type(rhs) is not int or not canonical:
        raise EncoderError("invalid canonical constraint")
    return Constraint(canonical, relation, rhs)


def derive_model(problem_payload: Any) -> DerivedModel:
    """Independently rebuild all admitted arithmetic and the complete PB model."""

    problem = _mapping(problem_payload, "problem_instance")
    _expect(
        problem.get("benchmark_id"),
        "factory_layout_optimality_benchmark_v1",
        "benchmark_id",
    )
    _expect(problem.get("schema_version"), 1, "schema_version")
    grid = _mapping(problem.get("grid"), "grid")
    width = _exact_int(grid.get("width"), "grid.width")
    height = _exact_int(grid.get("height"), "grid.height")
    if (width, height) != (GRID_SIDE, GRID_SIDE):
        raise EncoderError("strict grid must remain 70x70")
    objective = _mapping(problem.get("objective"), "objective")
    _expect(objective.get("kind"), "max_lex_area_min_side", "objective.kind")
    _expect(objective.get("body_cells_only"), True, "objective.body_cells_only")
    _expect(objective.get("minimum_side"), MINIMUM_SIDE, "objective.minimum_side")
    coordinate = _mapping(problem.get("coordinate_system"), "coordinate_system")
    if list(_array(coordinate.get("directions"), "coordinate directions")) != [
        "N",
        "E",
        "S",
        "W",
    ]:
        raise EncoderError("strict cardinal direction order drifted")

    templates = _mapping(problem.get("facility_templates"), "facility_templates")
    body_areas = {
        str(name): _mode_area(
            _mapping(template, f"templates.{name}"),
            f"templates.{name}",
        )
        for name, template in templates.items()
    }
    required_raw = _array(problem.get("required_instances"), "required_instances")
    required: dict[str, Mapping[str, Any]] = {}
    template_counts: Counter[str] = Counter()
    for index, raw_instance in enumerate(required_raw):
        instance = _mapping(raw_instance, f"required_instances[{index}]")
        instance_id = instance.get("id")
        template_name = instance.get("template")
        if type(instance_id) is not str or not instance_id or instance_id in required:
            raise EncoderError(f"required instance id {index} is invalid or duplicated")
        if type(template_name) is not str or template_name not in templates:
            raise EncoderError(f"required instance template {index} is unknown")
        required[instance_id] = instance
        template_counts[template_name] += 1

    groups_raw = _array(problem.get("operation_groups"), "operation_groups")
    groups: dict[str, Mapping[str, Any]] = {}
    for index, raw_group in enumerate(groups_raw):
        group = _mapping(raw_group, f"operation_groups[{index}]")
        group_id = group.get("id")
        template_name = group.get("template")
        if type(group_id) is not str or not group_id or group_id in groups:
            raise EncoderError(f"operation group id {index} is invalid or duplicated")
        if type(template_name) is not str or template_name not in templates:
            raise EncoderError(f"operation group template {index} is unknown")
        count = _exact_int(group.get("count"), f"operation_groups[{index}].count")
        instance_ids = _array(
            group.get("instance_ids"),
            f"operation_groups[{index}].instance_ids",
        )
        if len(instance_ids) != count or len(set(instance_ids)) != count:
            raise EncoderError(f"operation group {group_id} count/list mismatch")
        for instance_id in instance_ids:
            if type(instance_id) is not str or instance_id not in required:
                raise EncoderError(f"operation group {group_id} references an unknown instance")
            instance = required[instance_id]
            if instance.get("operation") != group_id or instance.get("template") != template_name:
                raise EncoderError(f"operation group {group_id} disagrees with its instance")
        groups[group_id] = group

    required_body_area = sum(count * body_areas[name] for name, count in template_counts.items())
    powered_instances = [
        instance
        for instance in required.values()
        if _mapping(
            templates[str(instance["template"])],
            f"templates.{instance['template']}",
        ).get("requires_power")
        is True
    ]
    powered_body_area = sum(body_areas[str(instance["template"])] for instance in powered_instances)
    manufacturing_instances = sum(
        _exact_int(group.get("count"), f"groups.{group_id}.count") for group_id, group in groups.items()
    )
    manufacturing_inputs = sum(
        _exact_int(group.get("count"), f"groups.{group_id}.count") * _need_total(group, "inputs", group_id)
        for group_id, group in groups.items()
    )
    manufacturing_outputs = sum(
        _exact_int(group.get("count"), f"groups.{group_id}.count") * _need_total(group, "outputs", group_id)
        for group_id, group in groups.items()
    )
    generic = _mapping(problem.get("generic_requirements"), "generic_requirements")
    raw_outputs = _mapping(generic.get("raw_outputs"), "generic.raw_outputs")
    final_inputs_map = _mapping(generic.get("final_inputs"), "generic.final_inputs")
    raw_output_count = sum(_exact_int(value, f"generic.raw_outputs.{name}") for name, value in raw_outputs.items())
    final_input_count = sum(
        _exact_int(value, f"generic.final_inputs.{name}") for name, value in final_inputs_map.items()
    )
    active_inputs = manufacturing_inputs + final_input_count
    active_outputs = manufacturing_outputs + raw_output_count
    total_terminals = active_inputs + active_outputs
    commodities = _array(problem.get("commodities"), "commodities")
    if any(type(name) is not str or not name for name in commodities) or len(set(commodities)) != len(commodities):
        raise EncoderError("commodity list is invalid")
    strict_sentinels = {
        "required_instances": len(required),
        "manufacturing_instances": manufacturing_instances,
        "required_body_area": required_body_area,
        "powered_manufacturing_area": powered_body_area,
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
        raise EncoderError("strict count sentinels drifted")
    declared_sentinels = _mapping(problem.get("sentinels"), "sentinels")
    for key in (
        "required_instance_count",
        "manufacturing_instance_count",
        "required_body_area",
        "manufacturing_input_terminals",
        "manufacturing_output_terminals",
        "generic_raw_output_terminals",
        "generic_final_input_terminals",
        "total_active_terminals",
        "operation_group_count",
        "commodity_count",
    ):
        expected_key = {
            "required_instance_count": "required_instances",
            "manufacturing_instance_count": "manufacturing_instances",
            "operation_group_count": "operation_groups",
            "commodity_count": "commodities",
        }.get(key, key)
        _expect(
            declared_sentinels.get(key),
            strict_sentinels[expected_key],
            f"sentinels.{key}",
        )

    ordinary_classes: Counter[tuple[int, int]] = Counter()
    marked_classes: Counter[tuple[int, int]] = Counter()
    marked_patterns: set[tuple[int, int]] = set()
    manufacturing_marks = 0
    powered_shapes: set[tuple[int, int]] = set()
    for instance in powered_instances:
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
    for group_id, group in groups.items():
        template_name = str(group["template"])
        template = _mapping(templates[template_name], f"templates.{template_name}")
        count = _exact_int(group.get("count"), f"groups.{group_id}.count")
        needs = {
            "inputs": _need_total(group, "inputs", group_id),
            "outputs": _need_total(group, "outputs", group_id),
        }
        all_spans: list[int] = []
        kind_spans: dict[str, list[int]] = {"input": [], "output": []}
        for mode_index, raw_mode in enumerate(_array(template.get("modes"), f"templates.{template_name}.modes")):
            mode = _mapping(raw_mode, f"{template_name}.modes[{mode_index}]")
            for port_index, raw_port in enumerate(_array(mode.get("ports"), f"{template_name}.ports")):
                port = _mapping(raw_port, f"{template_name}.ports[{port_index}]")
                _validate_port(mode, port, f"{template_name}.ports[{port_index}]")
                span = _side_length(mode, port, f"{template_name}.ports[{port_index}]")
                all_spans.append(span)
                kind_spans[str(port["kind"])].append(span)
        span = _exact_int(_one(all_spans, f"{template_name} port side span"), "side span")
        ordinary_classes[(span, max(needs.values()))] += count
        group_marks = 0
        for plural, kind in (("inputs", "input"), ("outputs", "output")):
            _one(kind_spans[kind], f"{template_name} {kind} side span")
            corner_counts: set[int] = set()
            capacity_counts: set[int] = set()
            for raw_mode in _array(template.get("modes"), f"{template_name}.modes"):
                mode = _mapping(raw_mode, f"{template_name}.mode")
                ports = [
                    _mapping(port, f"{template_name}.{kind}")
                    for port in _array(mode.get("ports"), f"{template_name}.ports")
                    if _mapping(port, f"{template_name}.{kind}").get("kind") == kind
                ]
                capacity_counts.add(len(ports))
                corner_counts.add(sum(_is_corner(mode, port, f"{template_name}.{kind}") for port in ports))
            if min(capacity_counts) < needs[plural] or corner_counts != {2}:
                raise EncoderError(f"{template_name} active/corner port capacity drifted")
            marks = max(0, needs[plural] - 2)
            marked_classes[(span, marks)] += count
            marked_patterns.add((span, marks))
            group_marks += marks
        manufacturing_marks += count * group_marks

    boundary_count = template_counts["boundary_storage_port"]
    boundary = _mapping(templates.get("boundary_storage_port"), "boundary_storage_port")
    _expect(
        boundary.get("placement_rule"),
        "matching_map_boundary",
        "boundary placement_rule",
    )
    boundary_modes: set[tuple[int, int, str]] = set()
    boundary_spans: set[int] = set()
    for raw_mode in _array(boundary.get("modes"), "boundary modes"):
        mode = _mapping(raw_mode, "boundary mode")
        body = _mapping(mode.get("body"), "boundary body")
        ports = [_mapping(port, "boundary port") for port in _array(mode.get("ports"), "boundary ports")]
        if len(ports) != 1 or ports[0].get("kind") != "output":
            raise EncoderError("boundary mode must have exactly one output")
        boundary_modes.add(
            (
                _exact_int(body.get("width"), "boundary width"),
                _exact_int(body.get("height"), "boundary height"),
                str(ports[0].get("direction")),
            )
        )
        boundary_spans.add(_side_length(mode, ports[0], "boundary output"))
        if _is_corner(mode, ports[0], "boundary output"):
            raise EncoderError("boundary raw-output slot must be noncorner")
    if boundary_modes != {(1, 3, "E"), (3, 1, "N")} or boundary_spans != {3}:
        raise EncoderError("boundary mode geometry drifted")
    ordinary_classes[(3, 1)] += boundary_count
    marked_classes[(3, 1)] += boundary_count
    marked_patterns.add((3, 1))

    core = _mapping(templates.get("protocol_core"), "protocol_core")
    core_face_patterns: set[tuple[int, int]] = set()
    core_slot_counts: set[int] = set()
    for raw_mode in _array(core.get("modes"), "protocol_core.modes"):
        mode = _mapping(raw_mode, "protocol_core.mode")
        faces: dict[str, list[Mapping[str, Any]]] = {}
        for raw_port in _array(mode.get("ports"), "protocol_core.ports"):
            port = _mapping(raw_port, "protocol_core.port")
            if port.get("kind") == "output":
                if _is_corner(mode, port, "protocol_core.output"):
                    raise EncoderError("protocol-core raw-output slot must be noncorner")
                faces.setdefault(str(port.get("direction")), []).append(port)
        if sorted(len(ports) for ports in faces.values()) != [3, 3]:
            raise EncoderError("protocol core output split drifted")
        core_slot_counts.add(sum(len(ports) for ports in faces.values()))
        core_face_patterns.update(
            (_side_length(mode, ports[0], "protocol core face"), len(ports)) for ports in faces.values()
        )
    if core_face_patterns != {(9, 3)} or core_slot_counts != {6}:
        raise EncoderError("protocol core output geometry drifted")
    marked_classes[(9, 3)] += 2
    marked_patterns.add((9, 3))

    if ordinary_classes != EXPECTED_ORDINARY_CLASSES:
        raise EncoderError("ordinary membrane class table drifted")
    if marked_classes != EXPECTED_MARKED_CLASSES:
        raise EncoderError("marked membrane class table drifted")
    full_contact_excess = sum(
        count * max(0, 2 * allowance - span) for (span, allowance), count in ordinary_classes.items()
    )
    endpoint_contacts = 2 * len(STEPS)
    maximum_endpoint_extra = max(allowance - max(0, 2 * allowance - span) for span, allowance in ordinary_classes)
    endpoint_correction = endpoint_contacts * maximum_endpoint_extra
    membrane_total = full_contact_excess + endpoint_correction
    membrane_floor = membrane_total // 2
    core_face = 3
    inside_addend = core_face + final_input_count
    inside_constant = membrane_floor + inside_addend
    ordinary_numerator = total_terminals - inside_constant
    if (
        full_contact_excess,
        endpoint_contacts,
        maximum_endpoint_extra,
        endpoint_correction,
        membrane_total,
        membrane_floor,
        inside_addend,
        inside_constant,
        ordinary_numerator,
    ) != (63, 8, 3, 24, 87, 43, 5, 48, ORDINARY_NUMERATOR):
        raise EncoderError("ordinary membrane constants drifted")

    provider_slots: dict[str, int] = {}
    for provider_name in _array(
        generic.get("raw_output_providers"),
        "generic.raw_output_providers",
    ):
        if type(provider_name) is not str or provider_name not in templates:
            raise EncoderError("unknown raw-output provider")
        template = _mapping(templates[provider_name], f"templates.{provider_name}")
        slot_counts: set[int] = set()
        for raw_mode in _array(template.get("modes"), f"{provider_name}.modes"):
            mode = _mapping(raw_mode, f"{provider_name}.mode")
            outputs = [
                _mapping(port, f"{provider_name}.port")
                for port in _array(mode.get("ports"), f"{provider_name}.ports")
                if _mapping(port, f"{provider_name}.port").get("kind") == "output"
            ]
            if any(_is_corner(mode, port, provider_name) for port in outputs):
                raise EncoderError("raw-output provider has a corner output")
            slot_counts.add(len(outputs))
        slots = _exact_int(_one(slot_counts, f"{provider_name} output slots"), "slots")
        provider_slots[provider_name] = template_counts[provider_name] * slots
    if provider_slots != {"boundary_storage_port": 46, "protocol_core": 6}:
        raise EncoderError("raw-output provider slot census drifted")
    raw_noncorner_marks = sum(provider_slots.values())
    total_marks = manufacturing_marks + raw_noncorner_marks
    if (manufacturing_marks, raw_noncorner_marks, total_marks) != (58, 52, 110):
        raise EncoderError("marked-terminal census drifted")

    occurrences, access_enumeration = _port_occurrences(templates)
    expected_access = {
        "3": {
            "combinations_checked": 352_440,
            "nonoverlap_combinations": 30_080,
            "maximum_noncorner_marks": 1,
        },
        "4": {
            "combinations_checked": 3_920_400,
            "nonoverlap_combinations": 8_192,
            "maximum_noncorner_marks": 0,
        },
    }
    if len(occurrences) != 178 or access_enumeration != expected_access:
        raise EncoderError("access-cell t(z)+m(z) enumeration drifted")

    maximum_marks = max(marks for _, marks in marked_patterns)
    maximum_marked_side = max(span for span, marks in marked_patterns if marks > 0)
    if (
        maximum_marks,
        maximum_marked_side,
        all(2 * marks <= span for span, marks in marked_patterns),
    ) != (3, 9, True):
        raise EncoderError("marked membrane extrema drifted")
    interval_certificate = _marked_interval_certificate(
        marked_patterns,
        maximum_marks,
    )
    if interval_certificate != {
        "interval_checks": 381_680,
        "endpoint_pair_checks": 81_900,
        "maximum_body_disjoint_crossers_per_endpoint": 1,
        "directed_side_count": 4,
        "endpoints_per_directed_side": 2,
        "directed_endpoint_count": 8,
        "maximum_marks_per_partial_contact": 3,
    }:
        raise EncoderError("marked interval certificate count drifted")
    maximum_partial_contacts = (
        interval_certificate["directed_endpoint_count"]
        * interval_certificate["maximum_body_disjoint_crossers_per_endpoint"]
    )
    marked_inside_offset = maximum_partial_contacts * maximum_marks // 2
    if marked_inside_offset != 12:
        raise EncoderError("marked inside offset drifted")
    marked_numerator = ordinary_numerator + total_marks - marked_inside_offset
    if marked_numerator != MARKED_NUMERATOR:
        raise EncoderError("marked outside numerator drifted")

    power = _mapping(problem.get("power"), "power")
    _expect(
        power.get("required_rule"),
        "at_least_one_body_cell_covered",
        "power.required_rule",
    )
    pole_template_name = power.get("pole_template")
    if type(pole_template_name) is not str or pole_template_name not in templates:
        raise EncoderError("power pole template drifted")
    pole_template = _mapping(templates[pole_template_name], "pole template")
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
    if pole_shapes != {(2, 2)} or body_areas[pole_template_name] != 4:
        raise EncoderError("pole body geometry drifted")
    halo = _derive_halo(
        powered_shapes,
        _mapping(power.get("coverage_from_pole_anchor"), "power coverage"),
        (2, 2),
        powered_body_area,
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
        raise EncoderError("power-halo certificate drifted")
    free_cell_cap = width * height - required_body_area - halo["minimum_poles"] * 4
    if free_cell_cap != FREE_CELL_CAP:
        raise EncoderError("free-cell cap drifted")

    boundary_anchors = list(range(width - 2))
    chosen_anchors: list[int] = []
    next_free = 0
    for anchor in boundary_anchors:
        if anchor >= next_free:
            chosen_anchors.append(anchor)
            next_free = anchor + 3
    per_boundary = len(chosen_anchors)
    distributions = [
        left for left in range(boundary_count + 1) if left <= per_boundary and boundary_count - left <= per_boundary
    ]
    if (
        boundary_count,
        len(boundary_anchors),
        per_boundary,
        distributions,
        3 * per_boundary,
        width - 3 * per_boundary,
    ) != (46, 68, 23, [23], 69, 1):
        raise EncoderError("boundary 23+23 packing drifted")

    all_dimensions = [(w, h) for w in range(MINIMUM_SIDE, GRID_SIDE + 1) for h in range(MINIMUM_SIDE, GRID_SIDE + 1)]
    factor_pairs = [pair for pair in all_dimensions if pair[0] * pair[1] == TARGET_AREA]
    dimensions = [
        (w, h)
        for w, h in all_dimensions
        if w * h > TARGET_AREA or (w * h == TARGET_AREA and min(w, h) > TARGET_MIN_SIDE)
    ]

    def access_lower_bound(w: int, h: int) -> tuple[int, int, int]:
        side_sum = w + h
        ordinary = ceil_div(ORDINARY_NUMERATOR - side_sum, INCIDENCE_CAP)
        marked = ceil_div(MARKED_NUMERATOR - 2 * side_sum, INCIDENCE_CAP)
        return ordinary, marked, max(ordinary, marked)

    variables: list[VariableRecord] = []
    arithmetic_survivors: list[tuple[int, int]] = []
    final_survivors: list[tuple[int, int]] = []
    for w, h in dimensions:
        ordinary_access, marked_access, access = access_lower_bound(w, h)
        total = w * h + access
        coefficient = free_cell_cap - total
        full_span = w == GRID_SIDE or h == GRID_SIDE
        record = VariableRecord(
            {
                "id": len(variables) + 1,
                "name": f"dimension__w_{w:02d}__h_{h:02d}",
                "kind": "oriented_dimension_selector",
                "width": w,
                "height": h,
                "area": w * h,
                "minimum_side": min(w, h),
                "side_sum": w + h,
                "marked_bound_applicable": min(w, h) >= maximum_marked_side,
                "ordinary_access_lower_bound": ordinary_access,
                "marked_access_lower_bound": marked_access,
                "access_lower_bound": access,
                "total_required_cells": total,
                "coefficient": coefficient,
                "full_span": full_span,
            }
        )
        variables.append(record)
        if coefficient >= 0:
            arithmetic_survivors.append((w, h))
            if not full_span:
                final_survivors.append((w, h))

    full_span_variables = [record for record in variables if record["full_span"]]
    constraints = [
        _canonical_constraint(
            ((record["id"], 1) for record in variables),
            "=",
            1,
        ),
        *(
            _canonical_constraint(
                ((record["id"], record["coefficient"]),),
                ">=",
                0,
            )
            for record in variables
        ),
        *(_canonical_constraint(((record["id"], -1),), ">=", 0) for record in full_span_variables),
    ]
    positive_coefficients = [record for record in variables if record["coefficient"] > 0]
    negative_coefficients = [record for record in variables if record["coefficient"] < 0]
    zero_coefficients = [record for record in variables if record["coefficient"] == 0]
    non_full = [record for record in variables if not record["full_span"]]
    minimum_non_full_total = min(int(record["total_required_cells"]) for record in non_full)
    minimum_non_full_dimensions = [
        [int(record["width"]), int(record["height"])]
        for record in non_full
        if record["total_required_cells"] == minimum_non_full_total
    ]
    area_tie_in_band = [[w, h] for w, h in dimensions if w * h == TARGET_AREA]
    if factor_pairs != [
        (18, 66),
        (22, 54),
        (27, 44),
        (33, 36),
        (36, 33),
        (44, 27),
        (54, 22),
        (66, 18),
    ]:
        raise EncoderError("area-1188 factor pair census drifted")
    if (
        len(dimensions) != EXPECTED_VARIABLES
        or area_tie_in_band != [[27, 44], [33, 36], [36, 33], [44, 27]]
        or min(min(w, h) for w, h in dimensions) != 17
        or len(full_span_variables) != EXPECTED_FULL_SPAN
        or arithmetic_survivors != [(17, 70), (70, 17)]
        or final_survivors
        or len(positive_coefficients) != 2
        or len(negative_coefficients) != 2_082
        or zero_coefficients
        or {record["coefficient"] for record in positive_coefficients} != {4}
        or minimum_non_full_total != 1_322
        or minimum_non_full_dimensions != [[27, 44], [44, 27]]
    ):
        raise EncoderError("complete lex-better band arithmetic drifted")

    counts = {
        "oriented_dimensions": len(dimensions),
        "selector_variables": len(variables),
        "variables": len(variables),
        "equality_constraints": 1,
        "arithmetic_implication_constraints": len(variables),
        "full_span_forbid_constraints": len(full_span_variables),
        "constraints": len(constraints),
        "arithmetic_survivors": len(arithmetic_survivors),
        "final_survivors": len(final_survivors),
        "positive_arithmetic_coefficients": len(positive_coefficients),
        "negative_arithmetic_coefficients": len(negative_coefficients),
        "zero_arithmetic_coefficients": len(zero_coefficients),
    }
    if counts != {
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
    }:
        raise EncoderError("final PB model size drifted")

    derived_facts = {
        "grid": {"width": width, "height": height, "area": width * height},
        "objective": {
            "kind": "max_lex_area_min_side",
            "minimum_side": MINIMUM_SIDE,
            "target_area": TARGET_AREA,
            "target_min_side": TARGET_MIN_SIDE,
            "orientation": "ordered_width_height",
        },
        "strict_sentinels": {
            **strict_sentinels,
            "boundary_instances": boundary_count,
            "protocol_core_instances": template_counts["protocol_core"],
            "pole_body_area": 4,
            "port_occurrences": len(occurrences),
        },
        "ordinary_membrane": {
            "class_table": [
                {"side_span": span, "active_side_cap": active, "multiplicity": count}
                for (span, active), count in sorted(ordinary_classes.items())
            ],
            "full_contact_excess": full_contact_excess,
            "directed_endpoints": endpoint_contacts,
            "maximum_endpoint_extra": maximum_endpoint_extra,
            "endpoint_correction": endpoint_correction,
            "twice_k_minus_l_cap": membrane_total,
            "manufacturing_boundary_additive_cap": membrane_floor,
            "protocol_core_side_output_cap": core_face,
            "generic_final_input_terminals": final_input_count,
            "additional_inside_terminals": inside_addend,
            "inside_terminal_additive_cap": inside_constant,
            "outside_access_incidence_cap": INCIDENCE_CAP,
            "outside_terminal_numerator_constant": ordinary_numerator,
        },
        "power_halo": {key: value for key, value in halo.items() if key != "violations"}
        | {"violation_count": len(halo["violations"])},
        "marked_terminals": {
            "manufacturing_marks": manufacturing_marks,
            "raw_output_slots": provider_slots,
            "raw_noncorner_marks": raw_noncorner_marks,
            "total_marks": total_marks,
            "class_table": [
                {"side_span": span, "marks": marks, "multiplicity": count}
                for (span, marks), count in sorted(marked_classes.items())
            ],
        },
        "access_cell_enumeration": {
            "port_occurrences": len(occurrences),
            "enumeration": access_enumeration,
            "inequality": "t(z)+m(z)<=4",
        },
        "marked_membrane": {
            "maximum_marks_per_side": maximum_marks,
            "maximum_marked_side": maximum_marked_side,
            **interval_certificate,
            "maximum_partial_contacts": maximum_partial_contacts,
            "inside_offset": marked_inside_offset,
            "outside_numerator_constant": marked_numerator,
        },
        "boundary_packing": {
            "required_bodies": boundary_count,
            "anchors_per_supported_boundary": len(boundary_anchors),
            "maximum_per_supported_boundary": per_boundary,
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
            "width_range": [MINIMUM_SIDE, GRID_SIDE],
            "height_range": [MINIMUM_SIDE, GRID_SIDE],
            "oriented": True,
            "predicate": "area > 1188 or (area == 1188 and min(width,height) > 22)",
            "dimension_count": len(dimensions),
            "area_1188_factor_pairs": [list(pair) for pair in factor_pairs],
            "area_1188_band_pairs": area_tie_in_band,
            "minimum_side_in_band": min(min(pair) for pair in dimensions),
            "full_span_dimension_count": len(full_span_variables),
            "arithmetic_survivors": [list(pair) for pair in arithmetic_survivors],
            "final_survivors": [list(pair) for pair in final_survivors],
            "minimum_non_full_total": minimum_non_full_total,
            "minimum_non_full_dimensions": minimum_non_full_dimensions,
        },
        "necessary_inequality": {
            "display": ("wh + max(ceil((580-w-h)/4), ceil((678-2w-2h)/4)) <= 1320"),
            "ordinary_numerator_constant": ordinary_numerator,
            "marked_numerator_constant": marked_numerator,
            "divisor": INCIDENCE_CAP,
            "rhs": free_cell_cap,
            "marked_bound_minimum_side": maximum_marked_side,
        },
    }
    return DerivedModel(
        variables=variables,
        constraints=constraints,
        derived_facts=derived_facts,
        counts=counts,
    )


def render_opb(model: DerivedModel) -> bytes:
    equalities = sum(constraint.relation == "=" for constraint in model.constraints)
    lines = [
        (f"* #variable= {len(model.variables)} #constraint= {len(model.constraints)} #equal= {equalities} intsize= 64"),
        (
            f"* model={MODEL_SCHEMA} generated_by={HARNESS} semantics={SEMANTICS} "
            "target=1188,22 "
            "given_inequality=wh+max(ceil((580-w-h)/4),"
            "ceil((678-2w-2h)/4))<=1320 "
            "full_span_forbidden=true"
        ),
        *(constraint.render() for constraint in model.constraints),
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


def _argv_record(argv: Sequence[str] | None) -> list[str]:
    if argv is None:
        return list(sys.argv)
    return [str(Path(__file__).resolve()), *(str(value) for value in argv)]


def _records(snapshots: Mapping[str, Snapshot]) -> dict[str, dict[str, Any]]:
    return {key: snapshots[key].record() for key in sorted(snapshots)}


def _planning(opb_bytes: int, user_limit_bytes: int) -> dict[str, Any]:
    bound = max(PLANNING_FLOOR_BYTES, PLANNING_OPB_MULTIPLIER * opb_bytes)
    return {
        "bound_bytes": bound,
        "user_limit_bytes": user_limit_bytes,
        "decision": "GO" if bound <= user_limit_bytes else "NO_GO",
        "basis": {
            "method": "max_512_mib_or_1024_times_projected_opb_bytes",
            "floor_bytes": PLANNING_FLOOR_BYTES,
            "opb_multiplier": PLANNING_OPB_MULTIPLIER,
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


def _canonical_output_parent(path: Path, field: str) -> Path:
    absolute = path.absolute()
    parent = _canonical_directory(absolute.parent, f"{field} parent")
    if parent != absolute.parent:
        raise EncoderError(f"{field} parent path is not canonical")
    if absolute.exists() or absolute.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing {field}: {absolute}")
    if absolute.resolve(strict=False) != absolute:
        raise EncoderError(f"{field} has a non-canonical target path")
    return absolute


def _exclusive_bytes(path: Path, raw: bytes, field: str) -> None:
    target = _canonical_output_parent(path, field)
    with target.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _exclusive_text(path: Path, text: str, field: str) -> None:
    _exclusive_bytes(path, text.encode("utf-8"), field)


def _exclusive_json(path: Path, payload: Any, field: str) -> None:
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
    _exclusive_bytes(path, raw, field)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ensure_artifact_root() -> Path:
    parent = _canonical_directory(ARTIFACT_ROOT.parent, "artifact-root parent")
    if parent != ARTIFACT_ROOT.parent.absolute():
        raise EncoderError("artifact-root parent is not canonical")
    if ARTIFACT_ROOT.is_symlink():
        raise EncoderError("artifact root must not be a symlink")
    if not ARTIFACT_ROOT.exists():
        os.mkdir(ARTIFACT_ROOT, mode=0o700)
    return _canonical_directory(ARTIFACT_ROOT, "artifact root")


def _prepare_build_attempt(path: Path) -> Path:
    if not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise EncoderError("build output must be an absolute canonical path")
    artifact_root = _ensure_artifact_root()
    target = path.absolute()
    if target.parent != artifact_root:
        raise EncoderError("build output must be a direct child of the artifact root")
    match = ATTEMPT_RE.fullmatch(target.name)
    if match is None:
        raise EncoderError("build output name does not match the fixed build-attempt contract")
    used: set[int] = set()
    for entry in artifact_root.iterdir():
        existing = ATTEMPT_RE.fullmatch(entry.name)
        if existing is None:
            continue
        if entry.is_symlink():
            raise EncoderError("an existing build-attempt path is a symlink")
        used.add(int(existing.group("number")))
    expected = 1
    while expected in used:
        expected += 1
    if int(match.group("number")) != expected:
        raise EncoderError(f"build attempt must use the lowest unused index a{expected:03d}")
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"build attempt already exists: {target}")
    os.mkdir(target, mode=0o700)
    return _canonical_directory(target, "build attempt")


def _run_build_child(
    command: Sequence[str],
    *,
    root: Path,
    stdout_path: Path,
    stderr_path: Path,
    stage: str,
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started_ns = time.time_ns()
    try:
        completed = subprocess.run(
            list(command),
            cwd=root,
            env=environment,
            capture_output=True,
            timeout=GATE_TIMEOUT_SECONDS,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        return_code: int | None = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        return_code = None
        timed_out = True
    _exclusive_bytes(stdout_path, stdout, f"{stage} stdout")
    _exclusive_bytes(stderr_path, stderr, f"{stage} stderr")
    result = {
        "stage": stage,
        "argv": list(command),
        "return_code": return_code,
        "timed_out": timed_out,
        "started_wall_time_ns": started_ns,
        "finished_wall_time_ns": time.time_ns(),
        "stdout": _absolute_record(stdout_path),
        "stderr": _absolute_record(stderr_path),
    }
    return result


def _require_build_child_success(result: Mapping[str, Any]) -> None:
    stage = result.get("stage")
    if result.get("timed_out") is True:
        raise EncoderError(f"{stage} exceeded the {GATE_TIMEOUT_SECONDS}-second limit")
    if result.get("return_code") != 0:
        raise EncoderError(f"{stage} exited with status {result.get('return_code')}")


def _write_build_manifest(
    attempt: Path,
    *,
    expected_names: frozenset[str] | None = BUILD_PAYLOAD_NAMES,
) -> dict[str, Any]:
    manifest_path = attempt / "SHA256SUMS"
    if manifest_path.exists() or manifest_path.is_symlink():
        raise FileExistsError(f"build manifest already exists: {manifest_path}")
    entries: list[dict[str, Any]] = []
    excluded = frozenset({"SHA256SUMS", "build_record.json"})
    current_names = {path.name for path in attempt.iterdir() if path.name not in excluded}
    if expected_names is not None and current_names != expected_names:
        missing = sorted(expected_names - current_names)
        unexpected = sorted(current_names - expected_names)
        raise EncoderError(f"build payload member mismatch: missing={missing!r}, unexpected={unexpected!r}")
    for path in sorted(attempt.iterdir(), key=lambda value: value.name):
        if path.name in excluded:
            continue
        resolved = _canonical_regular(path, f"build artifact {path.name}")
        if resolved.parent != attempt:
            raise EncoderError("build artifact escaped its attempt directory")
        raw = resolved.read_bytes()
        entries.append(
            {
                "path": path.name,
                "sha256": _sha256_bytes(raw),
                "size_bytes": len(raw),
            }
        )
    text = "".join(f"{entry['sha256']}  {entry['path']}\n" for entry in entries)
    _exclusive_text(manifest_path, text, "build checksum manifest")
    for entry in entries:
        path = attempt / entry["path"]
        if _absolute_record(path) != {
            "path": str(path),
            "sha256": entry["sha256"],
            "size_bytes": entry["size_bytes"],
        }:
            raise EncoderError("build checksum manifest did not replay")
    return {
        "file": _absolute_record(manifest_path),
        "covered_files": [entry["path"] for entry in entries],
        "entries": entries,
        "excluded_to_avoid_hash_cycle": sorted(excluded),
    }


def _fixed_python() -> tuple[Path, Path]:
    invocation = FIXED_PYTHON.absolute()
    try:
        resolved = invocation.resolve(strict=True)
        mode = resolved.lstat().st_mode
    except OSError as exc:
        raise EncoderError(f"cannot resolve fixed Python: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise EncoderError("fixed Python target is not a regular file")
    if _sha256_bytes(resolved.read_bytes()) != FIXED_PYTHON_SHA256:
        raise EncoderError("fixed Python SHA-256 drifted")
    if Path(sys.executable).resolve(strict=True) != resolved:
        raise EncoderError("build must run under the fixed Python interpreter")
    return invocation, resolved


def command_build(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    root = args.project_root.resolve(strict=True)
    if root != PROJECT_ROOT.resolve(strict=True):
        raise EncoderError("--project-root must identify this repository")
    python, python_resolved = _fixed_python()
    gate_source = _canonical_regular(args.gate_script, "translation gate source")
    expected_gate = RESEARCH_DIR / "verify_b1_r4_1188_22_pb_translation_v1.py"
    if gate_source != expected_gate:
        raise EncoderError("build must use the target-specific translation gate")

    attempt = _prepare_build_attempt(args.output_dir)
    paths = {
        "estimate": attempt / "estimate.json",
        "opb": attempt / "formula.opb",
        "meta": attempt / "encoder.meta.json",
        "var_map": attempt / "variable_map.json",
        "gate": attempt / "translation_gate.json",
    }
    source = _canonical_regular(Path(__file__), "encoder source")
    runs: list[dict[str, Any]] = []
    manifest_written = False
    try:
        estimate_command = [
            str(python),
            "-B",
            str(source),
            "estimate",
            "--project-root",
            str(root),
            "--output",
            str(paths["estimate"]),
            "--proof-limit-bytes",
            str(args.proof_limit_bytes),
        ]
        estimate_run = _run_build_child(
            estimate_command,
            root=root,
            stdout_path=attempt / "estimate.stdout.txt",
            stderr_path=attempt / "estimate.stderr.txt",
            stage="estimate",
        )
        runs.append(estimate_run)
        _require_build_child_success(estimate_run)
        encode_command = [
            str(python),
            "-B",
            str(source),
            "encode",
            "--project-root",
            str(root),
            "--estimate",
            str(paths["estimate"]),
            "--opb-out",
            str(paths["opb"]),
            "--meta-out",
            str(paths["meta"]),
            "--var-map-out",
            str(paths["var_map"]),
        ]
        encode_run = _run_build_child(
            encode_command,
            root=root,
            stdout_path=attempt / "encode.stdout.txt",
            stderr_path=attempt / "encode.stderr.txt",
            stage="encode",
        )
        runs.append(encode_run)
        _require_build_child_success(encode_run)
        gate_command = [
            str(python),
            "-B",
            str(gate_source),
            "--project-root",
            str(root),
            "--opb",
            str(paths["opb"]),
            "--meta",
            str(paths["meta"]),
            "--var-map",
            str(paths["var_map"]),
            "--estimate",
            str(paths["estimate"]),
            "--output",
            str(paths["gate"]),
        ]
        gate_run = _run_build_child(
            gate_command,
            root=root,
            stdout_path=attempt / "translation_gate.stdout.txt",
            stderr_path=attempt / "translation_gate.stderr.txt",
            stage="translation_gate",
        )
        runs.append(gate_run)
        _require_build_child_success(gate_run)
        gate = loads_strict_json(paths["gate"].read_bytes(), "translation gate")
        if not isinstance(gate, Mapping):
            raise EncoderError("translation gate must be a JSON object")
        checks = gate.get("checks")
        if (
            gate.get("schema_version") != GATE_SCHEMA
            or gate.get("model_schema_version") != MODEL_SCHEMA
            or gate.get("metadata_schema_version") != METADATA_SCHEMA
            or gate.get("variable_map_schema_version") != VAR_MAP_SCHEMA
            or gate.get("semantics") != SEMANTICS
            or gate.get("status") != "PASS"
            or gate.get("corpus_errors") != []
            or not isinstance(checks, Mapping)
            or set(checks) != REQUIRED_GATE_CHECKS
            or any(value is not True for value in checks.values())
            or gate.get("proof_status") != "translation_gate_only_no_unsat_or_proof_claim"
            or gate.get("encoder_source") != _file_record(source, root)
            or gate.get("gate_source") != _file_record(gate_source, root)
            or gate.get("translation_inputs")
            != {
                "estimate": _file_record(paths["estimate"], root),
                "meta": _file_record(paths["meta"], root),
                "opb": _file_record(paths["opb"], root),
                "var_map": _file_record(paths["var_map"], root),
            }
        ):
            raise EncoderError("translation gate did not close the complete band")
        estimate = loads_strict_json(paths["estimate"].read_bytes(), "estimate")
        if not isinstance(estimate, Mapping):
            raise EncoderError("estimate must be a JSON object")
        planning = _mapping(estimate.get("proof_size_planning"), "proof planning")
        if planning.get("decision") != "GO" or planning.get("user_limit_bytes") != args.proof_limit_bytes:
            raise EncoderError("build estimate is not a closed GO")
        manifest = _write_build_manifest(attempt)
        manifest_written = True
        record = {
            "schema_version": BUILD_RECORD_SCHEMA,
            "semantics": SEMANTICS,
            "status": "PASS",
            "created_at_utc": _utc_now(),
            "argv": _argv_record(argv),
            "project_root": str(root),
            "git_head": EXPECTED_GIT_HEAD,
            "attempt": attempt.name,
            "sources": {
                "encoder": _absolute_record(source),
                "translation_gate": _absolute_record(gate_source),
                "python_invocation_path": str(python),
                "python": _absolute_record(python_resolved),
            },
            "runs": runs,
            "outputs": {name: _absolute_record(path) for name, path in sorted(paths.items())},
            "manifest": manifest,
            "claim": "none",
            "formal_run_authorized": False,
            "proof_status": "build_and_translation_only_no_unsat_or_proof_claim",
        }
        _exclusive_json(attempt / "build_record.json", record, "build record")
    except (EncoderError, OSError, subprocess.SubprocessError, ValueError) as exc:
        failure = {
            "schema_version": "b1_r4_1188_22_pb_build_failure_v1",
            "semantics": SEMANTICS,
            "status": "FAIL",
            "created_at_utc": _utc_now(),
            "argv": _argv_record(argv),
            "attempt": attempt.name,
            "runs": runs,
            "claim": "none",
            "formal_run_authorized": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        failure_name = "build_post_seal_failed.json" if manifest_written else "build_failed.json"
        try:
            _exclusive_json(attempt / failure_name, failure, "build failure record")
        except (EncoderError, OSError, ValueError):
            pass
        if not manifest_written:
            try:
                _write_build_manifest(attempt, expected_names=None)
            except (EncoderError, OSError, ValueError):
                pass
        print(
            json.dumps(
                {"status": "FAIL", "attempt": str(attempt), "error": str(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "status": "PASS",
                "attempt": str(attempt),
                "manifest_sha256": manifest["file"]["sha256"],
                "build_record_sha256": _absolute_record(attempt / "build_record.json")["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


def _estimate_payload(
    *,
    project_root: Path,
    proof_limit_bytes: int,
    argv: Sequence[str] | None,
) -> tuple[dict[str, Any], DerivedModel, bytes]:
    if proof_limit_bytes <= 0:
        raise EncoderError("--proof-limit-bytes must be positive")
    root = project_root.resolve(strict=True)
    inputs, authority = load_bound_snapshots(root)
    model = derive_model(loads_strict_json(inputs["problem_instance"].raw, "problem instance"))
    opb = render_opb(model)
    return (
        {
            "schema_version": ESTIMATE_SCHEMA,
            "model_schema_version": MODEL_SCHEMA,
            "metadata_schema_version": METADATA_SCHEMA,
            "variable_map_schema_version": VAR_MAP_SCHEMA,
            "semantics": SEMANTICS,
            "harness": HARNESS,
            "argv": _argv_record(argv),
            "project_root": str(root),
            "harness_source": _file_record(Path(__file__), root),
            "inputs": _records(inputs),
            "upstream_authority": authority,
            "git_snapshot": _git_snapshot(root),
            "derived_facts": model.derived_facts,
            "counts": model.counts,
            "projected_outputs": {"opb_bytes": len(opb)},
            "proof_size_planning": _planning(len(opb), proof_limit_bytes),
        },
        model,
        opb,
    )


def command_estimate(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    payload, _model, opb = _estimate_payload(
        project_root=args.project_root,
        proof_limit_bytes=args.proof_limit_bytes,
        argv=argv,
    )
    _exclusive_json(args.output, payload, "estimate output")
    print(
        json.dumps(
            {
                "decision": payload["proof_size_planning"]["decision"],
                "opb_bytes": len(opb),
                "output": str(args.output.absolute()),
            },
            sort_keys=True,
        )
    )
    return 0


def _load_estimate(path: Path, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot = _snapshot("estimate", path, root)
    payload = loads_strict_json(snapshot.raw, "estimate")
    if not isinstance(payload, dict):
        raise EncoderError("estimate must be a JSON object")
    return payload, snapshot.record()


def _check_estimate(
    estimate: Mapping[str, Any],
    *,
    root: Path,
    model: DerivedModel,
    opb: bytes,
    inputs: Mapping[str, Snapshot],
    authority: Mapping[str, Any],
) -> None:
    expected_keys = {
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
    if set(estimate) != expected_keys:
        raise EncoderError("estimate key set is not closed")
    scalars = {
        "schema_version": ESTIMATE_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "metadata_schema_version": METADATA_SCHEMA,
        "variable_map_schema_version": VAR_MAP_SCHEMA,
        "semantics": SEMANTICS,
        "harness": HARNESS,
        "project_root": str(root),
    }
    if any(estimate.get(key) != value for key, value in scalars.items()):
        raise EncoderError("estimate schema/semantics identity drifted")
    estimate_argv = estimate.get("argv")
    if (
        not isinstance(estimate_argv, list)
        or not estimate_argv
        or any(type(value) is not str for value in estimate_argv)
    ):
        raise EncoderError("estimate argv must be a nonempty string array")
    planning = _mapping(estimate.get("proof_size_planning"), "proof planning")
    user_limit = _exact_int(planning.get("user_limit_bytes"), "user proof limit")
    if dict(planning) != _planning(len(opb), user_limit):
        raise EncoderError("estimate proof planning drifted")
    if planning.get("decision") != "GO":
        raise EncoderError("estimate is not GO")
    expected = {
        "harness_source": _file_record(Path(__file__), root),
        "inputs": _records(inputs),
        "upstream_authority": dict(authority),
        "git_snapshot": _git_snapshot(root),
        "derived_facts": model.derived_facts,
        "counts": model.counts,
        "projected_outputs": {"opb_bytes": len(opb)},
    }
    if any(estimate.get(key) != value for key, value in expected.items()):
        raise EncoderError("estimate provenance/model drifted")


def command_encode(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    root = args.project_root.resolve(strict=True)
    outputs = [
        args.opb_out.absolute(),
        args.meta_out.absolute(),
        args.var_map_out.absolute(),
    ]
    if len(set(outputs)) != 3 or len({path.resolve(strict=False) for path in outputs}) != 3:
        raise EncoderError("OPB, metadata, and variable-map outputs must be distinct")
    for path, field in zip(outputs, ("OPB output", "metadata output", "variable-map output")):
        _canonical_output_parent(path, field)
    inputs, authority = load_bound_snapshots(root)
    model = derive_model(loads_strict_json(inputs["problem_instance"].raw, "problem instance"))
    opb = render_opb(model)
    estimate, estimate_record = _load_estimate(args.estimate, root)
    _check_estimate(
        estimate,
        root=root,
        model=model,
        opb=opb,
        inputs=inputs,
        authority=authority,
    )
    _exclusive_bytes(args.opb_out, opb, "OPB output")
    var_map = {
        "schema_version": VAR_MAP_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "semantics": SEMANTICS,
        "variable_count": len(model.variables),
        "variables": model.variables,
    }
    _exclusive_json(args.var_map_out, var_map, "variable-map output")
    meta = {
        "schema_version": METADATA_SCHEMA,
        "model_schema_version": MODEL_SCHEMA,
        "variable_map_schema_version": VAR_MAP_SCHEMA,
        "semantics": SEMANTICS,
        "harness": HARNESS,
        "argv": _argv_record(argv),
        "project_root": str(root),
        "harness_source": _file_record(Path(__file__), root),
        "inputs": _records(inputs),
        "upstream_authority": authority,
        "git_snapshot": _git_snapshot(root),
        "estimate": estimate_record,
        "derived_facts": model.derived_facts,
        "counts": model.counts,
        "outputs": {
            "opb": _file_record(args.opb_out, root),
            "var_map": _file_record(args.var_map_out, root),
            "metadata": {"path": str(args.meta_out.absolute())},
        },
        "claim_scope": _claim_scope(),
        "proof_status": "translation_only_no_unsat_or_proof_claim",
    }
    _exclusive_json(args.meta_out, meta, "metadata output")
    print(
        json.dumps(
            {
                "status": "generated",
                "opb": str(args.opb_out.absolute()),
                "variables": model.counts["variables"],
                "constraints": model.counts["constraints"],
            },
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    estimate = subparsers.add_parser(
        "estimate",
        help="write a no-overwrite build-only size/resource estimate",
    )
    estimate.add_argument("--project-root", type=Path, required=True)
    estimate.add_argument("--output", type=Path, required=True)
    estimate.add_argument(
        "--proof-limit-bytes",
        type=int,
        default=PROOF_LIMIT_BYTES,
    )

    encode = subparsers.add_parser(
        "encode",
        help="write the transparent OPB, metadata, and variable map",
    )
    encode.add_argument("--project-root", type=Path, required=True)
    encode.add_argument("--estimate", type=Path, required=True)
    encode.add_argument("--opb-out", type=Path, required=True)
    encode.add_argument("--meta-out", type=Path, required=True)
    encode.add_argument("--var-map-out", type=Path, required=True)

    build = subparsers.add_parser(
        "build",
        help="create and seal one no-overwrite build-only authority attempt",
    )
    build.add_argument("--project-root", type=Path, required=True)
    build.add_argument("--gate-script", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument(
        "--proof-limit-bytes",
        type=int,
        default=PROOF_LIMIT_BYTES,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    recorded_argv = list(argv) if argv is not None else None
    if args.command == "estimate":
        return command_estimate(args, recorded_argv)
    if args.command == "encode":
        return command_encode(args, recorded_argv)
    if args.command == "build":
        return command_build(args, recorded_argv)
    raise EncoderError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
