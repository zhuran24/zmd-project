#!/usr/bin/env python3
"""Independently verify one recursive B1 paired-run artifact manifest.

The manifest deliberately excludes itself and ``pair_run.json`` to avoid a
hash cycle.  This verifier rebuilds the recursive file set, rejects links and
other non-regular objects, checks every byte hash, and then validates the
paired control/treatment terminal-state attribution.  It never imports the
encoder or any of its semantic helpers.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


SCHEMA = "b1_conditional_halo_run_manifest_verification_v1"
RUN_SCHEMA = "b1_conditional_halo_pair_run_v1"
MANIFEST_NAME = "SHA256SUMS.recursive"
RUN_RECORD_NAME = "pair_run.json"
CHECKED_SAT_SCHEMA = "b1_conditional_halo_sat_assignment_check_v1"
ASSIGNMENT_SCHEMA = "b1_conditional_halo_full_assignment_v1"
META_SCHEMA = "b1_conditional_halo_fixed_rectangle_metadata_v1"
VAR_MAP_SCHEMA = "b1_conditional_halo_fixed_rectangle_var_map_v1"
TERMINAL = frozenset({"CHECKED_SAT"})
INCOMPLETE = frozenset({"UNKNOWN", "NO_GO", "ERROR", "SAT_UNCHECKED", "NOT_RUN"})
INPUT_ROLES = frozenset(
    {
        "geometry_admission",
        "corpus_manifest",
        "control_opb",
        "control_metadata",
        "control_var_map",
        "treatment_opb",
        "treatment_metadata",
        "treatment_var_map",
        "translation_gate",
        "translation_admission",
        "stencil",
        "r1_translation_gate",
    }
)


class ManifestError(ValueError):
    """A recursive manifest or run record failed closed."""


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise ManifestError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ManifestError(f"non-finite JSON number forbidden: {value}")


def _load(path: Path, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(
            path.resolve(strict=True).read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except ManifestError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot load {label}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ManifestError(f"{label} root must be an object")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _record(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    if resolved.is_symlink() or not resolved.is_file():
        raise ManifestError(f"not a regular provenance file: {resolved}")
    return {
        "path": _display(resolved, root),
        "sha256": _sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _record_path(value: Any, root: Path, label: str) -> Path:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256", "size_bytes"}:
        raise ManifestError(f"{label} is not an exact three-field file record")
    raw = value.get("path")
    if type(raw) is not str or not raw:
        raise ManifestError(f"{label}.path is malformed")
    candidate = Path(raw)
    path = candidate if candidate.is_absolute() else root / candidate
    try:
        actual = _record(path, root)
    except OSError as exc:
        raise ManifestError(f"cannot resolve {label}: {exc}") from exc
    if actual != dict(value):
        raise ManifestError(f"{label} is stale")
    return path.resolve(strict=True)


def _same_bytes(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    return first.get("sha256") == second.get("sha256") and first.get("size_bytes") == second.get("size_bytes")


def _array(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ManifestError(f"{label} must be an array")
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise ManifestError(f"{label} must be an exact integer")
    return int(value)


def _parse_opb(path: Path) -> tuple[int, list[tuple[tuple[tuple[int, int], ...], str, int]]]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ManifestError(f"cannot parse copied OPB: {exc}") from exc
    if not lines:
        raise ManifestError("copied OPB is empty")
    header = re.fullmatch(
        r"\* #variable= ([1-9]\d*) #constraint= ([1-9]\d*) #equal= (\d+) intsize= 64",
        lines[0],
    )
    if header is None:
        raise ManifestError("copied OPB header is malformed")
    variable_count, constraint_count = map(int, header.group(1, 2))
    constraints: list[tuple[tuple[tuple[int, int], ...], str, int]] = []
    for line_number, line in enumerate(lines[1:], 2):
        if line.startswith("*"):
            continue
        match = re.fullmatch(r"((?:[+-]\d+ x[1-9]\d* )+)(>=|=) (-?\d+) ;", line)
        if match is None:
            raise ManifestError(f"malformed copied OPB constraint line {line_number}")
        terms = tuple(
            (int(variable), int(coefficient))
            for coefficient, variable in re.findall(r"([+-]\d+) x([1-9]\d*)", match[1])
        )
        if not terms or len({variable for variable, _ in terms}) != len(terms):
            raise ManifestError(f"duplicate/empty term list on copied OPB line {line_number}")
        if any(variable > variable_count or coefficient == 0 for variable, coefficient in terms):
            raise ManifestError(f"out-of-range/zero OPB term on line {line_number}")
        constraints.append((terms, match[2], int(match[3])))
    if len(constraints) != constraint_count:
        raise ManifestError("copied OPB constraint count does not match header")
    return variable_count, constraints


def _satisfies(constraints: Sequence[tuple[tuple[tuple[int, int], ...], str, int]], values: Sequence[int]) -> bool:
    for terms, relation, rhs in constraints:
        lhs = sum(coefficient * values[variable - 1] for variable, coefficient in terms)
        if (relation == "=" and lhs != rhs) or (relation == ">=" and lhs < rhs):
            return False
    return True


def _pattern_cells(left_gap: int, bottom_gap: int) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    def anchors(gap: int) -> tuple[int, ...]:
        cells = [value for value in range(70) if value != gap]
        chunks = tuple(tuple(cells[index : index + 3]) for index in range(0, 69, 3))
        if any(chunk != tuple(range(chunk[0], chunk[0] + 3)) for chunk in chunks):
            raise ManifestError("selected boundary-pattern gap is malformed")
        return tuple(chunk[0] for chunk in chunks)

    left, bottom = anchors(left_gap), anchors(bottom_gap)
    body = {(0, anchor + offset) for anchor in left for offset in range(3)} | {
        (anchor + offset, 0) for anchor in bottom for offset in range(3)
    }
    q_cells = {(1, anchor + 1) for anchor in left} | {(anchor + 1, 1) for anchor in bottom}
    if len(body) != 138 or len(q_cells) != 46 or body & q_cells:
        raise ManifestError("selected boundary pattern does not have the strict 138/46 shape")
    return body, q_cells


def _exclusive_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _manifest_entries(path: Path) -> dict[str, str]:
    try:
        lines = path.resolve(strict=True).read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ManifestError(f"cannot read recursive manifest: {exc}") from exc
    if not lines:
        raise ManifestError("recursive manifest is empty")
    entries: dict[str, str] = {}
    for index, line in enumerate(lines, 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\x00\r\n]+)", line)
        if match is None:
            raise ManifestError(f"malformed manifest line {index}")
        digest, relative = match.groups()
        pure = PurePosixPath(relative)
        if (
            pure.is_absolute()
            or relative != pure.as_posix()
            or relative in {"", "."}
            or any(part in {"", ".", ".."} for part in pure.parts)
            or "\\" in relative
        ):
            raise ManifestError(f"unsafe or non-normalized manifest path: {relative!r}")
        if relative in entries:
            raise ManifestError(f"duplicate manifest path: {relative!r}")
        if relative in {MANIFEST_NAME, RUN_RECORD_NAME}:
            raise ManifestError(f"hash-cycle exclusion was included: {relative}")
        entries[relative] = digest
    if list(entries) != sorted(entries):
        raise ManifestError("recursive manifest paths are not sorted")
    return entries


def _actual_files(run_dir: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in sorted(run_dir.rglob("*"), key=lambda item: item.relative_to(run_dir).as_posix()):
        relative = path.relative_to(run_dir).as_posix()
        if path.is_symlink():
            raise ManifestError(f"symlink forbidden in run directory: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ManifestError(f"non-regular object forbidden in run directory: {relative}")
        if relative not in {MANIFEST_NAME, RUN_RECORD_NAME}:
            files[relative] = path
    if not files:
        raise ManifestError("recursive manifest would cover no artifacts")
    return files


def _expected_attribution(control: str, treatment: str) -> tuple[str, str]:
    if (control, treatment) == ("CHECKED_SAT", "CHECKED_SAT"):
        return "treatment_survivor", "COMPLETE"
    return "incomplete", "INCOMPLETE"


def _record_shape(value: Any) -> bool:
    return bool(
        isinstance(value, Mapping)
        and set(value) == {"path", "sha256", "size_bytes"}
        and type(value.get("path")) is str
        and bool(value.get("path"))
        and type(value.get("sha256")) is str
        and re.fullmatch(r"[0-9a-f]{64}", value["sha256"])
        and type(value.get("size_bytes")) is int
        and value["size_bytes"] >= 0
    )


def _covered_path(
    value: Any,
    directory: Path,
    root: Path,
    entries: Mapping[str, str],
    label: str,
) -> Path:
    path = _record_path(value, root, label)
    try:
        relative = path.relative_to(directory).as_posix()
    except ValueError as exc:
        raise ManifestError(f"{label} is not inside the paired-run directory") from exc
    if entries.get(relative) != value.get("sha256"):
        raise ManifestError(f"{label} is not exactly covered by the recursive manifest")
    return path


def _load_copied_inputs(
    record: Mapping[str, Any], directory: Path, root: Path, entries: Mapping[str, str]
) -> dict[str, Path]:
    sources = record.get("inputs")
    copies = record.get("input_copies")
    if (
        not isinstance(sources, Mapping)
        or not isinstance(copies, Mapping)
        or set(sources) != INPUT_ROLES
        or set(copies) != INPUT_ROLES
    ):
        raise ManifestError("source/copied input role set is not the exact twelve-role contract")
    paths: dict[str, Path] = {}
    for role in sorted(INPUT_ROLES):
        source = sources[role]
        copied = copies[role]
        if not _record_shape(source):
            raise ManifestError(f"inputs.{role} is not an exact three-field source record")
        path = _covered_path(copied, directory, root, entries, f"input_copies.{role}")
        if not _same_bytes(source, copied):
            raise ManifestError(f"input_copies.{role} does not preserve the pre-snapshot bytes")
        paths[role] = path
    revalidation = record.get("pre_seal_revalidation")
    checked_roles = [
        "control.record",
        "control.assignment",
        "control.checker",
        "treatment.record",
        "treatment.assignment",
        "treatment.checker",
    ]
    allowed_hard_links = {*(f"input.{role}" for role in INPUT_ROLES), *checked_roles}
    hard_links = revalidation.get("hard_link_snapshot_roles") if isinstance(revalidation, Mapping) else None
    if (
        not isinstance(revalidation, Mapping)
        or set(revalidation)
        != {
            "status",
            "source_input_roles",
            "input_copy_roles",
            "checked_sat_copy_roles",
            "hard_link_snapshot_roles",
            "copy_strategy",
        }
        or revalidation.get("status") != "PASS"
        or revalidation.get("source_input_roles") != sorted(INPUT_ROLES)
        or revalidation.get("input_copy_roles") != sorted(INPUT_ROLES)
        or revalidation.get("checked_sat_copy_roles") != checked_roles
        or revalidation.get("copy_strategy") != "hard_link_same_filesystem_exclusive_copy_on_exdev"
        or not isinstance(hard_links, Sequence)
        or isinstance(hard_links, (str, bytes))
        or list(hard_links) != sorted(set(hard_links))
        or not set(hard_links) <= allowed_hard_links
    ):
        raise ManifestError("pre-seal source/copy revalidation record is not exact")
    return paths


def _model_pair(
    copied: Mapping[str, Path], record: Mapping[str, Any]
) -> tuple[
    dict[str, tuple[int, list[tuple[tuple[tuple[int, int], ...], str, int]]]],
    tuple[tuple[tuple[int, int], ...], str, int],
]:
    parsed = {arm: _parse_opb(copied[f"{arm}_opb"]) for arm in ("control", "treatment")}
    if parsed["control"][0] != 4_841 or parsed["treatment"][0] != 4_841:
        raise ManifestError("copied paired OPBs do not each have 4841 variables")
    control = Counter(parsed["control"][1])
    treatment = Counter(parsed["treatment"][1])
    added = treatment - control
    removed = control - treatment
    if sum(added.values()) != 1 or removed:
        raise ManifestError("copied treatment does not differ by exactly one added row")
    halo = next(iter(added))
    if halo[1:] != (">=", 6_650) or any(coefficient <= 0 for _, coefficient in halo[0]):
        raise ManifestError("copied treatment-only row is not doubled halo >=6650")
    paired = record.get("paired_diff")
    if (
        not isinstance(paired, Mapping)
        or paired.get("exactly_one_conditional_halo") is not True
        or paired.get("rhs_doubled") != 6_650
    ):
        raise ManifestError("pair-run treatment-diff declaration drifted")
    return parsed, halo


def _validate_checked_arm(
    arm: str,
    arm_record: Mapping[str, Any],
    record: Mapping[str, Any],
    copied_inputs: Mapping[str, Path],
    parsed_models: Mapping[str, tuple[int, list[tuple[tuple[tuple[int, int], ...], str, int]]]],
    halo: tuple[tuple[tuple[int, int], ...], str, int],
    directory: Path,
    root: Path,
    entries: Mapping[str, str],
) -> None:
    paired_sha = record.get("paired_generation_sha256")
    if (
        arm_record.get("arm") != arm
        or arm_record.get("paired_generation_sha256") != paired_sha
        or arm_record.get("terminal_status") != "CHECKED_SAT"
        or arm_record.get("failure_codes") != []
        or arm_record.get("claim") != "assignment_satisfies_relaxed_fixed_geometry_model"
    ):
        raise ManifestError(f"{arm} is not an exact CHECKED_SAT terminal arm")
    snapshot = arm_record.get("checked_sat")
    if not isinstance(snapshot, Mapping) or set(snapshot) != {"source", "copied", "validated_schema"}:
        raise ManifestError(f"{arm} checked-SAT snapshot record is missing")
    if not _record_shape(snapshot.get("source")) or snapshot.get("validated_schema") != CHECKED_SAT_SCHEMA:
        raise ManifestError(f"{arm} checked-SAT source/schema binding is malformed")
    copied_records = snapshot.get("copied")
    if not isinstance(copied_records, Mapping) or set(copied_records) != {"record", "assignment", "checker"}:
        raise ManifestError(f"{arm} checked-SAT copied evidence set is incomplete")
    evidence_paths = {
        role: _covered_path(value, directory, root, entries, f"arms.{arm}.checked_sat.copied.{role}")
        for role, value in copied_records.items()
    }
    checked = _load(evidence_paths["record"], f"copied {arm} checked-SAT record")
    if not _same_bytes(snapshot["source"], copied_records["record"]):
        raise ManifestError(f"{arm} copied checked-SAT record differs from its validated source")
    if (
        checked.get("schema_version") != CHECKED_SAT_SCHEMA
        or checked.get("status") != "PASS"
        or checked.get("assignment_status") != "CHECKED_SAT"
        or checked.get("arm") != arm
        or checked.get("model_scope") != "diagnostic_fixed_pattern"
        or checked.get("case_index") != record.get("case_index")
        or checked.get("paired_generation_sha256") != paired_sha
    ):
        raise ManifestError(f"copied {arm} checked-SAT record identity/status drifted")
    assignment_source = checked.get("assignment")
    checker_source = checked.get("checker_source")
    if (
        not _record_shape(assignment_source)
        or not _record_shape(checker_source)
        or not _same_bytes(assignment_source, copied_records["assignment"])
        or not _same_bytes(checker_source, copied_records["checker"])
        or checked.get("assignment_sha256") != copied_records["assignment"].get("sha256")
    ):
        raise ManifestError(f"copied {arm} assignment/checker source binding drifted")
    try:
        ast.parse(evidence_paths["checker"].read_text(encoding="utf-8"), filename=str(evidence_paths["checker"]))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise ManifestError(f"copied {arm} checker source is not parseable Python: {exc}") from exc

    source_inputs = record["inputs"]
    expected_model = {
        "opb": source_inputs[f"{arm}_opb"],
        "metadata": source_inputs[f"{arm}_metadata"],
        "var_map": source_inputs[f"{arm}_var_map"],
    }
    if checked.get("model") != expected_model:
        raise ManifestError(f"copied {arm} checked-SAT record is bound to the wrong model")
    assignment = _load(evidence_paths["assignment"], f"copied {arm} assignment")
    metadata = _load(copied_inputs[f"{arm}_metadata"], f"copied {arm} metadata")
    var_map = _load(copied_inputs[f"{arm}_var_map"], f"copied {arm} variable map")
    if (
        assignment.get("schema_version") != ASSIGNMENT_SCHEMA
        or assignment.get("opb_sha256") != source_inputs[f"{arm}_opb"].get("sha256")
        or assignment.get("case_index") != record.get("case_index")
        or assignment.get("case_id") != record.get("case_id")
        or assignment.get("pair_id") != record.get("pair_id")
        or assignment.get("paired_generation_sha256") != paired_sha
    ):
        raise ManifestError(f"copied {arm} assignment identity/model binding drifted")
    values_raw = _array(assignment.get("values"), f"{arm} assignment.values")
    if len(values_raw) != 4_841 or any(type(value) is not int or value not in {0, 1} for value in values_raw):
        raise ManifestError(f"copied {arm} assignment is not a full 4841-bit vector")
    values = list(values_raw)
    if not _satisfies(parsed_models[arm][1], values):
        raise ManifestError(f"copied {arm} assignment does not satisfy its copied OPB")

    case = record.get("case")
    if not isinstance(case, Mapping):
        raise ManifestError("pair-run case record is missing")
    if (
        metadata.get("schema_version") != META_SCHEMA
        or metadata.get("status") != "PASS"
        or metadata.get("arm") != arm
        or metadata.get("model_scope") != "diagnostic_fixed_pattern"
        or metadata.get("case") != case
        or metadata.get("paired_generation_sha256") != paired_sha
    ):
        raise ManifestError(f"copied {arm} metadata identity drifted")
    outputs = metadata.get("outputs")
    if (
        not isinstance(outputs, Mapping)
        or outputs.get("opb") != source_inputs[f"{arm}_opb"]
        or outputs.get("var_map") != source_inputs[f"{arm}_var_map"]
    ):
        raise ManifestError(f"copied {arm} metadata output bindings drifted")
    variables = _array(var_map.get("variables"), f"copied {arm} var_map.variables")
    if (
        var_map.get("schema_version") != VAR_MAP_SCHEMA
        or var_map.get("status") != "PASS"
        or var_map.get("model_scope") != "diagnostic_fixed_pattern"
        or var_map.get("case") != case
        or var_map.get("paired_generation_sha256") != paired_sha
        or var_map.get("variable_count") != 4_841
        or len(variables) != 4_841
    ):
        raise ManifestError(f"copied {arm} variable-map contract drifted")
    for expected_id, variable in enumerate(variables, 1):
        if not isinstance(variable, Mapping) or variable.get("id") != expected_id:
            raise ManifestError(f"copied {arm} variable map is not dense and ordered")

    pattern_records = [variable for variable in variables if variable.get("kind") == "boundary_pattern"]
    pole_records = [variable for variable in variables if variable.get("kind") == "pole_anchor"]
    count_records = [variable for variable in variables if variable.get("kind") == "pole_count"]
    selected_patterns = [variable for variable in pattern_records if values[variable["id"] - 1]]
    selected_poles = [variable for variable in pole_records if values[variable["id"] - 1]]
    selected_counts = [variable for variable in count_records if values[variable["id"] - 1]]
    if len(selected_patterns) != 1 or len(selected_counts) != 1:
        raise ManifestError(f"copied {arm} assignment does not select one pattern/count")
    selected_delta = _integer(selected_patterns[0].get("delta"), "selected pattern delta")
    selected_count = _integer(selected_counts[0].get("count"), "selected pole count")
    actual_p = len(selected_poles)
    if selected_delta != case.get("delta") or selected_count != actual_p or not 9 <= actual_p <= 41:
        raise ManifestError(f"copied {arm} selected pattern/pole count drifted")
    w, h, x, y, a_delta, e_delta = (
        _integer(case.get(key), f"case.{key}") for key in ("w", "h", "x", "y", "a_delta", "e_delta")
    )
    rectangle = {(xx, yy) for xx in range(x, x + w) for yy in range(y, y + h)}
    bodies = [
        {(variable["x"] + dx, variable["y"] + dy) for dx in range(2) for dy in range(2)} for variable in selected_poles
    ]
    rectangle_conflicts = sum(bool(body & rectangle) for body in bodies)
    overlap_pairs = sum(bool(first & second) for index, first in enumerate(bodies) for second in bodies[index + 1 :])
    pattern_body, q_cells = _pattern_cells(
        _integer(selected_patterns[0].get("left_gap"), "selected left_gap"),
        _integer(selected_patterns[0].get("bottom_gap"), "selected bottom_gap"),
    )
    pattern_conflicts = sum(bool(body & (pattern_body | q_cells)) for body in bodies)
    r1_lhs = w * h + -(-(580 - w - h + a_delta // 2 + e_delta) // 4) + 4 * (actual_p - 9)
    halo_lhs2 = sum(coefficient * values[variable - 1] for variable, coefficient in halo[0])
    expected_semantic = {
        "full_original_variables": 4_841,
        "selected_delta": selected_delta,
        "selected_count": selected_count,
        "actual_p": actual_p,
        "r1_count_lhs": r1_lhs,
        "pole_rectangle_conflicts": rectangle_conflicts,
        "pole_pair_overlaps": overlap_pairs,
        "pattern_pole_conflicts": pattern_conflicts,
        "halo_lhs2": halo_lhs2,
        "halo_rhs2": 6_650 if arm == "treatment" else None,
    }
    if checked.get("semantic_checks") != expected_semantic:
        raise ManifestError(f"copied {arm} checked-SAT semantic ledger does not independently recompute")
    if r1_lhs > 1_320 or any((rectangle_conflicts, overlap_pairs, pattern_conflicts)):
        raise ManifestError(f"copied {arm} assignment violates recomputed fixed-geometry semantics")
    if arm == "treatment" and halo_lhs2 < 6_650:
        raise ManifestError("copied treatment assignment violates the conditional-halo row")


def _validate_run_record(
    record: Mapping[str, Any], directory: Path, root: Path, entries: Mapping[str, str]
) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    checks["run_schema_exact"] = record.get("schema_version") == RUN_SCHEMA
    case_index = record.get("case_index")
    checks["case_index_exact_integer"] = type(case_index) is int and 0 <= case_index < 512
    checks["case_id_canonical"] = record.get("case_id") == (
        f"case_{case_index:03d}" if type(case_index) is int and 0 <= case_index < 512 else None
    )
    checks["pair_id_present"] = type(record.get("pair_id")) is str and bool(record.get("pair_id"))
    checks["transpose_group_id_present"] = type(record.get("transpose_group_id")) is str and bool(
        record.get("transpose_group_id")
    )
    pair_sha = record.get("paired_generation_sha256")
    checks["paired_generation_sha256_well_formed"] = bool(
        type(pair_sha) is str and re.fullmatch(r"[0-9a-f]{64}", pair_sha)
    )
    arms = record.get("arms")
    checks["arm_set_exact"] = isinstance(arms, Mapping) and set(arms) == {"control", "treatment"}
    control_status = treatment_status = "ERROR"
    if checks["arm_set_exact"]:
        control = arms["control"]
        treatment = arms["treatment"]
        checks["arm_records_are_objects"] = isinstance(control, Mapping) and isinstance(treatment, Mapping)
        if checks["arm_records_are_objects"]:
            control_status = control.get("terminal_status")
            treatment_status = treatment.get("terminal_status")
            checks["arm_statuses_known"] = control_status in TERMINAL and treatment_status in TERMINAL
            checks["arm_labels_exact"] = control.get("arm") == "control" and treatment.get("arm") == "treatment"
            checks["arm_pair_bindings_match"] = all(
                arm.get("paired_generation_sha256") == pair_sha for arm in (control, treatment)
            )
        else:
            checks.update(
                {
                    "arm_statuses_known": False,
                    "arm_labels_exact": False,
                    "arm_pair_bindings_match": False,
                }
            )
    else:
        checks.update(
            {
                "arm_records_are_objects": False,
                "arm_statuses_known": False,
                "arm_labels_exact": False,
                "arm_pair_bindings_match": False,
            }
        )
    attribution, status = _expected_attribution(str(control_status), str(treatment_status))
    checks["attribution_exact"] = record.get("attribution") == attribution
    if status == "INCOMPLETE" and isinstance(record.get("preflight"), Mapping):
        status = "NO_GO" if record["preflight"].get("decision") == "NO_GO" else status
    checks["run_status_exact"] = record.get("status") == status
    ledger = record.get("bound_ledger")
    checks["diagnostic_bound_unchanged"] = bool(
        isinstance(ledger, Mapping)
        and ledger.get("inherited_upper_bound") == [1190, 34]
        and ledger.get("control_upper_bound") == [1190, 34]
        and ledger.get("treatment_upper_bound") == [1190, 34]
        and ledger.get("global_update_authorized") is False
    )
    claim = record.get("claim_boundary")
    checks["claim_boundary_present"] = (
        isinstance(claim, Sequence) and not isinstance(claim, (str, bytes)) and bool(claim)
    )
    if all(checks.values()):
        copied_inputs = _load_copied_inputs(record, directory, root, entries)
        parsed_models, halo = _model_pair(copied_inputs, record)
        assert isinstance(arms, Mapping)
        for arm in ("control", "treatment"):
            arm_record = arms[arm]
            if not isinstance(arm_record, Mapping):
                raise ManifestError(f"{arm} arm record is not an object")
            _validate_checked_arm(
                arm,
                arm_record,
                record,
                copied_inputs,
                parsed_models,
                halo,
                directory,
                root,
                entries,
            )
        checks["dual_checked_sat_evidence_independently_validated"] = True
    return checks


def verify(run_dir: Path, manifest_path: Path, record_path: Path, project_root: Path) -> dict[str, Any]:
    root = project_root.resolve(strict=True)
    directory = run_dir.resolve(strict=True)
    if not directory.is_dir() or directory.is_symlink():
        raise ManifestError("run directory must be a real directory")
    if manifest_path.resolve(strict=True) != directory / MANIFEST_NAME:
        raise ManifestError(f"manifest must be {MANIFEST_NAME} at run root")
    if record_path.resolve(strict=True) != directory / RUN_RECORD_NAME:
        raise ManifestError(f"run record must be {RUN_RECORD_NAME} at run root")
    entries = _manifest_entries(manifest_path)
    actual = _actual_files(directory)
    checks = {
        "recursive_file_set_exact": set(entries) == set(actual),
        "recursive_hashes_exact": set(entries) == set(actual)
        and all(_sha256(actual[name]) == entries[name] for name in entries),
    }
    record = _load(record_path, "pair run record")
    checks.update(_validate_run_record(record, directory, root, entries))
    manifest_record = record.get("artifact_manifest")
    checks["run_record_manifest_binding_exact"] = bool(
        isinstance(manifest_record, Mapping)
        and manifest_record.get("file") == _record(manifest_path, root)
        and manifest_record.get("covered_files") == sorted(entries)
        and manifest_record.get("excluded_to_avoid_hash_cycle") == [MANIFEST_NAME, RUN_RECORD_NAME]
        and manifest_record.get("entries") == entries
    )
    errors = [name for name, passed in checks.items() if passed is not True]
    return {
        "schema_version": SCHEMA,
        "status": "PASS" if not errors else "FAIL",
        "project_root": str(root),
        "run_directory": str(directory),
        "inputs": {
            "manifest": _record(manifest_path, root),
            "pair_run": _record(record_path, root),
        },
        "case_index": record.get("case_index"),
        "case_id": record.get("case_id"),
        "pair_id": record.get("pair_id"),
        "transpose_group_id": record.get("transpose_group_id"),
        "paired_generation_sha256": record.get("paired_generation_sha256"),
        "checks": checks,
        "counts": {
            "manifest_entries": len(entries),
            "actual_covered_files": len(actual),
        },
        "corpus_errors": errors,
        "claim_boundary": [
            "independently reparses copied models and checks both complete assignments",
            "accepts only exact dual CHECKED_SAT evidence for the v1 diagnostic corpus",
            "does not prove UNSAT, a witness, attainability, or global optimality",
            "research artifact; not production CERTIFIED evidence",
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.output.exists():
        print("FAIL: output already exists", file=sys.stderr)
        return 2
    try:
        payload = verify(args.run_dir, args.manifest, args.record, args.project_root)
    except (ManifestError, OSError) as exc:
        payload = {
            "schema_version": SCHEMA,
            "status": "FAIL",
            "project_root": str(args.project_root.resolve(strict=False)),
            "checks": {},
            "corpus_errors": [f"{type(exc).__name__}: {exc}"],
            "claim_boundary": ["verification failed closed; no claim is authorized"],
        }
    try:
        _exclusive_json(args.output.resolve(), payload)
    except OSError as exc:
        print(f"FAIL: cannot write output: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": payload["status"], "output": str(args.output.resolve())}, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
