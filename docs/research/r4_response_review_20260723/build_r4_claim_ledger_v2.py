#!/usr/bin/env python3
"""Publish the fixed R4 quantitative claim ledger from inert archived bytes."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
from types import ModuleType
from typing import Any


RESEARCH_DIR = Path(__file__).resolve().parent
ARCHIVER_PATH = RESEARCH_DIR / "archive_r4_response_bundle_v2.py"
UPPER = "upper_bound_1188_22"
WITNESS = "witness_x67_c5_min_repair"
CLAIM_COUNT = 17
CLAIM_OUTPUT_RE = re.compile(r"a[0-9]{3}")
INERT_INSPECTION_NAME = "external-code-inert-inspection.json"
CLAIM_LEDGER_NAME = "quantitative-claim-ledger.json"
CLAIM_IDS = (
    "upper.strict_identity",
    "upper.body_power_halo",
    "upper.active_terminal_accounting",
    "upper.manufacturing_marks",
    "upper.raw_output_slots",
    "upper.marked_side_classes",
    "upper.ordinary_membrane",
    "upper.access_cell_capacity",
    "upper.marked_membrane",
    "upper.boundary_packing",
    "upper.scan_key_cases",
    "upper.final_dimension_scan",
    "witness.common_c3_gate",
    "witness.c3_cut_accounting",
    "witness.c5_separate_corpus",
    "witness.stop_and_claim_boundary",
    "witness.repair_prerequisites",
)

SIDE_CLASSES = [
    {"side": 3, "active": 1, "count": 155},
    {"side": 3, "active": 2, "count": 12},
    {"side": 3, "active": 3, "count": 11},
    {"side": 5, "active": 1, "count": 32},
    {"side": 5, "active": 2, "count": 17},
    {"side": 6, "active": 3, "count": 32},
    {"side": 6, "active": 4, "count": 3},
    {"side": 6, "active": 5, "count": 3},
]
MARKED_SIDE_CLASSES = [
    {"side": 3, "marks": 0, "count": 253},
    {"side": 3, "marks": 1, "count": 57},
    {"side": 5, "marks": 0, "count": 98},
    {"side": 6, "marks": 0, "count": 38},
    {"side": 6, "marks": 1, "count": 32},
    {"side": 6, "marks": 2, "count": 3},
    {"side": 6, "marks": 3, "count": 3},
    {"side": 9, "marks": 3, "count": 2},
]
W2D_HASHES = {
    "c3_result": "7b068e1eb1239b92074f47c5555f770f1b90672f12d923b73564cb1ef149fc0b",
    "c5_result": "cff12e728167cb2af7abe38a5e4ca1860e36ec1889a58fb147cd0dcc1324052b",
    "closeout_json": "8dc19571cdf5ff0912346a3acbdb4a885d2e092d1a7a74d6db01a8f3a64507e0",
    "composer": "27adbd468fe8bac7bbf2333be11d98e51e092ef07bba3b936305402e2c93df8d",
    "manifest_c0": "99fa30698c28a8fedb2189e159333373a9dea2012e691e8d917547a5d0a654a4",
    "manifest_c1": "2baa5f198cea987cfc86f606468a6aa5d5605b8f17c688621109394ac623997f",
}
REPAIR_REQUIRED = [
    "A hash-pinned exact 17-component manifest avoiding c3 (12,4,3).",
    "Independent soundness review for every guarded repair cut.",
    "Proof that no candidate nogood or UNKNOWN is treated as exclusion.",
    "Supervisory authorization superseding W2d STOP before any search.",
]


class LedgerError(RuntimeError):
    """Fail-closed claim-ledger construction error."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode()


def _reject_json_constant(value: str) -> Any:
    raise LedgerError(f"non-finite JSON constant is forbidden: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LedgerError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def _strict_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    absolute = path.absolute()
    if absolute.is_symlink() or absolute.resolve(strict=True) != absolute or not stat.S_ISREG(absolute.stat().st_mode):
        raise LedgerError(f"{label} is not a canonical regular file: {absolute}")
    raw = absolute.read_bytes()
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LedgerError(f"{label} is not strict UTF-8 JSON: {absolute}") from exc
    if not isinstance(parsed, dict):
        raise LedgerError(f"{label} must be a JSON object: {absolute}")
    if raw != _canonical_json_bytes(parsed):
        raise LedgerError(f"{label} bytes are not canonical JSON: {absolute}")
    return parsed, raw


def _validate_utc_timestamp(value: Any, label: str) -> datetime:
    if type(value) is not str or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z",
        value,
    ):
        raise LedgerError(f"{label} is not a canonical UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise LedgerError(f"{label} is not a valid UTC timestamp") from exc
    if parsed.tzinfo != UTC:
        raise LedgerError(f"{label} is not UTC")
    return parsed


def _record(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise LedgerError(f"symlink is not a provenance file: {path}")
    resolved = path.resolve(strict=True)
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise LedgerError(f"not a regular provenance file: {resolved}")
    return {
        "path": str(resolved),
        "size_bytes": resolved.stat().st_size,
        "sha256": _sha256(resolved),
    }


def _builder_tool_binding() -> dict[str, Any]:
    source = Path(__file__).absolute()
    if source.is_symlink() or source.resolve(strict=True) != source:
        raise LedgerError(f"claim ledger builder is not canonical: {source}")
    return _record(source)


def _load_archiver() -> ModuleType:
    if not ARCHIVER_PATH.is_file() or ARCHIVER_PATH.is_symlink():
        raise LedgerError(f"bundle archiver is unavailable: {ARCHIVER_PATH}")
    name = "_r4_response_bundle_archiver_for_claim_ledger"
    spec = importlib.util.spec_from_file_location(name, ARCHIVER_PATH)
    if spec is None or spec.loader is None:
        raise LedgerError("cannot load bundle archiver")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _publish_bytes(path: Path, raw: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise LedgerError(f"no-overwrite target exists: {path}")
    pending = path.with_name(f".{path.name}.pending-{os.getpid():010d}")
    with pending.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.link(pending, path, follow_symlinks=False)
    directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    pending.unlink(missing_ok=True)


def _publish_json(path: Path, payload: Mapping[str, Any]) -> None:
    _publish_bytes(path, _canonical_json_bytes(payload))


def _canonical_existing_directory(path: Path, label: str) -> Path:
    absolute = path.absolute()
    try:
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise LedgerError(f"{label} does not exist: {absolute}") from exc
    if absolute.is_symlink() or resolved != absolute or not stat.S_ISDIR(absolute.stat().st_mode):
        raise LedgerError(f"unsafe {label}: {absolute}")
    return absolute


def _claim_category(response_run: Path) -> tuple[Path, Path]:
    response = _canonical_existing_directory(response_run, "response run")
    claims = _canonical_existing_directory(response / "claims", "claims category")
    if claims.parent != response or claims.name != "claims":
        raise LedgerError(f"unsafe claims category: {claims}")
    return response, claims


def _validate_claim_output_target(response_run: Path, output_dir: Path) -> tuple[Path, Path]:
    _response, claims = _claim_category(response_run)
    if ".." in output_dir.parts:
        raise LedgerError(f"claim output directory must be a fresh direct aNNN child of {claims}: {output_dir}")
    output = output_dir.absolute()
    if output.parent != claims or CLAIM_OUTPUT_RE.fullmatch(output.name) is None:
        raise LedgerError(f"claim output directory must be a fresh direct aNNN child of {claims}: {output}")
    if output.exists() or output.is_symlink():
        raise LedgerError(f"no-overwrite claim output exists: {output}")
    return claims, output


def _create_claim_output_dir(response_run: Path, output_dir: Path) -> Path:
    """Atomically create one fresh direct ``claims/aNNN`` directory."""
    claims, output = _validate_claim_output_target(response_run, output_dir)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(claims, flags)
    try:
        try:
            os.mkdir(output.name, mode=0o755, dir_fd=directory_fd)
        except FileExistsError as exc:
            raise LedgerError(f"no-overwrite claim output exists: {output}") from exc
        created = os.stat(output.name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISDIR(created.st_mode):
            raise LedgerError(f"created claim output is not a directory: {output}")
        if output.is_symlink() or output.resolve(strict=True) != output:
            raise LedgerError(f"created claim output is not canonical: {output}")
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return output


def _validate_existing_claim_output(response_run: Path, output_dir: Path) -> Path:
    _response, claims = _claim_category(response_run)
    if ".." in output_dir.parts:
        raise LedgerError(f"claim output directory is not canonical: {output_dir}")
    output = _canonical_existing_directory(output_dir, "claim output directory")
    if output.parent != claims or CLAIM_OUTPUT_RE.fullmatch(output.name) is None:
        raise LedgerError(f"claim output directory is not a direct aNNN child of {claims}: {output}")
    return output


def _source_occurrences(
    raw_by_id: Mapping[str, bytes],
    specs: Sequence[tuple[str, bytes]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for input_id, snippet in specs:
        raw = raw_by_id[input_id]
        start = raw.find(snippet)
        if start < 0 or raw.find(snippet, start + 1) >= 0:
            raise LedgerError(f"source snippet is absent or non-unique in {input_id}: {snippet!r}")
        end = start + len(snippet)
        result.append(
            {
                "input_id": input_id,
                "start": start,
                "end": end,
                "slice_sha256": _sha256_bytes(raw[start:end]),
            }
        )
    return result


def _claim(
    raw_by_id: Mapping[str, bytes],
    *,
    claim_id: str,
    candidate_id: str,
    checker_id: str,
    result_key: str,
    expected_result: Any,
    kind: str,
    snippets: Sequence[tuple[str, bytes]],
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "candidate_id": candidate_id,
        "checker_id": checker_id,
        "result_key": result_key,
        "expected_result": expected_result,
        "kind": kind,
        "source_occurrences": _source_occurrences(raw_by_id, snippets),
    }


def _claims(raw_by_id: Mapping[str, bytes]) -> list[dict[str, Any]]:
    response = "response_text"
    note = "certificate_markdown"
    code = "certificate_python"
    claims: list[dict[str, Any]] = []
    add = claims.append
    add(
        _claim(
            raw_by_id,
            claim_id="upper.strict_identity",
            candidate_id=UPPER,
            checker_id="upper_counts",
            result_key="strict_identity",
            expected_result={
                "path": "/input/problem_instance.json",
                "sha256": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
                "grid": [70, 70],
                "minimum_objective_side": 6,
            },
            kind="input_identity",
            snippets=[
                (
                    note,
                    b"For the byte-locked strict instance with SHA-256\n"
                    b"`e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c`",
                ),
                (
                    code,
                    b"assert hashlib.sha256(raw).hexdigest() == "
                    b'"e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"',
                ),
            ],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="upper.body_power_halo",
            candidate_id=UPPER,
            checker_id="upper_counts",
            result_key="body_power_halo",
            expected_result={
                "required_instances": 266,
                "manufacturing_instances": 219,
                "required_body_cells": 3544,
                "powered_body_cells": 3325,
                "doubled_weight_total": 792,
                "eligible_placements": {"3x3": 180, "4x6": 220, "5x5": 220, "6x4": 220},
                "eligible_placement_total": 840,
                "pole_capacity": 396,
                "minimum_poles": 9,
                "pole_body_cells": 4,
                "base_body_cells": 3580,
                "remaining_cells": 1320,
            },
            kind="quantitative_necessity",
            snippets=[
                (
                    note,
                    b"The required bodies occupy 3,544 cells. Powered required bodies occupy 3,325\ncells.",
                ),
                (
                    code,
                    b"assert (required_area, powered_area, mi, mo, raw_n, final_n, total_t) == "
                    b"(3544, 3325, 310, 264, 52, 2, 628)",
                ),
            ],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="upper.active_terminal_accounting",
            candidate_id=UPPER,
            checker_id="upper_counts",
            result_key="active_terminal_accounting",
            expected_result={
                "manufacturing_inputs": 310,
                "manufacturing_outputs": 264,
                "raw_outputs": 52,
                "final_inputs": 2,
                "total": 628,
            },
            kind="quantitative_necessity",
            snippets=[
                (note, b"Thus at most `S+48` of the 628 active terminal incidences"),
                (
                    code,
                    b"(3544, 3325, 310, 264, 52, 2, 628)",
                ),
            ],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="upper.manufacturing_marks",
            candidate_id=UPPER,
            checker_id="upper_counts",
            result_key="manufacturing_marks",
            expected_result={"total": 58},
            kind="quantitative_necessity",
            snippets=[
                (note, b"The instance forces 58\nsuch manufacturing marks."),
                (code, b"assert (excess, end_extra, forced_mfg) == (63, 3, 58)"),
            ],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="upper.raw_output_slots",
            candidate_id=UPPER,
            checker_id="upper_counts",
            result_key="raw_output_slots",
            expected_result={
                "demand": 52,
                "providers": {"boundary_storage_port": 46, "protocol_core": 6},
                "noncorner_slots": 52,
                "total_marks": 110,
            },
            kind="quantitative_necessity",
            snippets=[
                (
                    response,
                    b"The 46 boundary-port outputs and all six protocol-core outputs must also be active",
                ),
                (code, b"assert marked == 110 and all(2*r <= s for s,r in forced_sides)"),
            ],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="upper.marked_side_classes",
            candidate_id=UPPER,
            checker_id="upper_counts",
            result_key="marked_side_classes",
            expected_result=MARKED_SIDE_CLASSES,
            kind="coordinate_classification",
            snippets=[
                (
                    note,
                    b"For every marked side class, if `r` marks lie on a side of length `s`, then\n`2r <= s`",
                )
            ],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="upper.ordinary_membrane",
            candidate_id=UPPER,
            checker_id="upper_counts",
            result_key="ordinary_membrane",
            expected_result={
                "side_classes": SIDE_CLASSES,
                "full_contact_excess": 63,
                "endpoint_increment": 3,
                "maximum_endpoint_contacts": 8,
                "endpoint_allowance": 24,
                "total_doubled_excess": 87,
                "manufacturing_boundary_offset": 43,
                "core_output_face": 3,
                "final_input_addend": 2,
                "inside_addend": 5,
                "k_in_offset": 48,
                "outside_numerator": 580,
            },
            kind="quantitative_necessity",
            snippets=[
                (
                    response,
                    b"The inherited ordinary membrane calculation, independently reconstructed by the checker, "
                    b"has full-contact excess 63 and endpoint increment at most 3.",
                )
            ],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="upper.access_cell_capacity",
            candidate_id=UPPER,
            checker_id="marked_geometry",
            result_key="access_cell_enumeration",
            expected_result={
                "port_occurrences": 178,
                "enumeration": {
                    "3": {
                        "combinations_checked": 352440,
                        "nonoverlap_combinations": 30080,
                        "maximum_noncorner_marks": 1,
                    },
                    "4": {
                        "combinations_checked": 3920400,
                        "nonoverlap_combinations": 8192,
                        "maximum_noncorner_marks": 0,
                    },
                },
                "inequality": "t_plus_m_le_4",
            },
            kind="coordinate_exhaustion",
            snippets=[(note, b"**`t + m <= 4`.**")],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="upper.marked_membrane",
            candidate_id=UPPER,
            checker_id="marked_geometry",
            result_key="marked_membrane",
            expected_result={
                "manufacturing_marks": 58,
                "raw_slots": 52,
                "total_marks": 110,
                "maximum_marks_per_side": 3,
                "maximum_marked_side": 9,
                "interval_checks": 381680,
                "endpoint_pair_checks": 81900,
                "maximum_partial_contacts": 8,
                "j_in_offset": 12,
            },
            kind="coordinate_exhaustion",
            snippets=[(note, b"`2J <= 2S + 8*3`, hence `J <= S+12`.")],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="upper.boundary_packing",
            candidate_id=UPPER,
            checker_id="marked_geometry",
            result_key="boundary_packing",
            expected_result={
                "required_bodies": 46,
                "anchors_per_side": 68,
                "maximum_per_supported_boundary": 23,
                "forced_distribution": [23, 23],
                "occupied_cells_per_boundary": 69,
                "unoccupied_cells_per_boundary": 1,
            },
            kind="coordinate_exhaustion",
            snippets=[
                (
                    response,
                    b"There are exactly 46 required boundary ports, so every feasible layout must use exactly "
                    b"23 left-boundary modes and 23 bottom-boundary modes.",
                ),
                (code, b"# 23 left and 23 bottom, covering 69/70 cells on each side."),
            ],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="upper.scan_key_cases",
            candidate_id=UPPER,
            checker_id="marked_geometry",
            result_key="scan_key_cases",
            expected_result={
                "17x70": {
                    "objective": [1190, 17],
                    "outside_cells": 126,
                    "sum": 1316,
                    "full_span_rejected": True,
                },
                "22x54": {
                    "objective": [1188, 22],
                    "outside_cells": 132,
                    "sum": 1320,
                    "full_span_rejected": False,
                },
                "29x41": {
                    "objective": [1189, 29],
                    "outside_cells": 135,
                    "sum": 1324,
                    "full_span_rejected": False,
                },
                "34x35": {
                    "objective": [1190, 34],
                    "outside_cells": 135,
                    "sum": 1325,
                    "full_span_rejected": False,
                },
            },
            kind="dimension_scan",
            snippets=[
                (
                    response,
                    b"34\\cdot35+\\left\\lceil\\frac{678-2(69)}4\\right\\rceil\n=1190+135=1325>1320",
                )
            ],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="upper.final_dimension_scan",
            candidate_id=UPPER,
            checker_id="marked_geometry",
            result_key="final_dimension_scan",
            expected_result={
                "old": {"objective": [1190, 34], "dimensions": [[34, 35]]},
                "marked_only": {"objective": [1190, 17], "dimensions": [[17, 70]]},
                "final": {"objective": [1188, 22], "dimensions": [[22, 54]]},
                "lex_better_survivors": [],
            },
            kind="dimension_scan",
            snippets=[
                (
                    response,
                    b"The remaining relaxation scan has lexicographic maximum (22\\times54)",
                ),
                (
                    code,
                    b"assert new == (1188,22) and new_dims == [(22,54)]",
                ),
            ],
        )
    )
    common = (
        response,
        b"Both complete manifests under the present partition collapse to the same c3 target ((12,4,3))",
    )
    add(
        _claim(
            raw_by_id,
            claim_id="witness.common_c3_gate",
            candidate_id=WITNESS,
            checker_id="w2d_audit",
            result_key="common_c3_gate",
            expected_result={
                "component_count": 17,
                "exact_manifest_count": 2,
                "target": [12, 4, 3],
                "both_manifests_require_target": True,
            },
            kind="authority_replay",
            snippets=[common],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="witness.c3_cut_accounting",
            candidate_id=WITNESS,
            checker_id="w2d_audit",
            result_key="c3_cut_accounting",
            expected_result={
                "status": "INFEASIBLE",
                "imported_sound_cuts": 7156,
                "new_sound_cuts": 12,
                "total_sound_cuts": 7168,
                "candidate_no_good_count": 0,
            },
            kind="authority_replay",
            snippets=[
                (
                    response,
                    b"Reinstantiate the 7,168 sound cuts, guarding any cut whose validity depends on a particular pin.",
                )
            ],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="witness.c5_separate_corpus",
            candidate_id=WITNESS,
            checker_id="w2d_audit",
            result_key="c5_separate_corpus",
            expected_result={
                "target": [10, 4, 4],
                "status": "UNKNOWN",
                "total_sound_cuts": 4010,
                "candidate_no_good_count": 0,
            },
            kind="authority_diagnostic",
            snippets=[
                (
                    response,
                    b"core-guided minimum-repair of the 17-component partition, targeted at x67-c5",
                )
            ],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="witness.stop_and_claim_boundary",
            candidate_id=WITNESS,
            checker_id="w2d_audit",
            result_key="stop_and_claim_boundary",
            expected_result={
                "w2d_stop": True,
                "witness_established": False,
                "global_infeasibility_established": False,
                "search_authorized": False,
            },
            kind="claim_boundary",
            snippets=[
                (
                    response,
                    b"Only after that gate passes should assembly and routing resume.",
                )
            ],
        )
    )
    add(
        _claim(
            raw_by_id,
            claim_id="witness.repair_prerequisites",
            candidate_id=WITNESS,
            checker_id="w2d_audit",
            result_key="repair_prerequisites",
            expected_result={
                "classification": "NEEDS_PREREQUISITES",
                "avoids_common_c3_gate": False,
                "reason": "A c5-only repair leaves both exact manifests' infeasible c3 row unchanged.",
                "required": REPAIR_REQUIRED,
            },
            kind="structural_classification",
            snippets=[
                (
                    response,
                    b"Turn every current component-membership pin into an assumption literal or soft equality.",
                )
            ],
        )
    )
    if len(claims) != CLAIM_COUNT or tuple(item.get("claim_id") for item in claims) != CLAIM_IDS:
        raise LedgerError("canonical claim constructor did not produce the fixed ordered 17 claims")
    claim_keys = {
        "candidate_id",
        "checker_id",
        "claim_id",
        "expected_result",
        "kind",
        "result_key",
        "source_occurrences",
    }
    occurrence_keys = {"end", "input_id", "slice_sha256", "start"}
    for item in claims:
        if set(item) != claim_keys:
            raise LedgerError(f"canonical claim has an unexpected schema: {item.get('claim_id')}")
        occurrences = item.get("source_occurrences")
        if not isinstance(occurrences, list) or not occurrences:
            raise LedgerError(f"canonical claim has no source occurrence: {item.get('claim_id')}")
        for occurrence in occurrences:
            if not isinstance(occurrence, dict) or set(occurrence) != occurrence_keys:
                raise LedgerError(f"canonical claim has a malformed source occurrence: {item.get('claim_id')}")
    return claims


def _raw_inputs(provenance: Mapping[str, Any]) -> dict[str, bytes]:
    inputs = provenance.get("inputs")
    if not isinstance(inputs, list):
        raise LedgerError("response bundle inputs are not an array")
    expected_ids = ("response_text", "certificate_markdown", "certificate_python")
    if tuple(item.get("input_id") for item in inputs if isinstance(item, Mapping)) != expected_ids:
        raise LedgerError("response bundle does not contain the fixed ordered three inputs")
    result: dict[str, bytes] = {}
    for item in inputs:
        if not isinstance(item, Mapping):
            raise LedgerError("response bundle input is not an object")
        input_id = item.get("input_id")
        raw_document = item.get("raw_document")
        if type(input_id) is not str or not isinstance(raw_document, Mapping):
            raise LedgerError("response bundle input provenance is malformed")
        raw_path = raw_document.get("path")
        if type(raw_path) is not str:
            raise LedgerError(f"response bundle path is malformed for {input_id}")
        path = Path(raw_path)
        if _record(path) != dict(raw_document):
            raise LedgerError(f"response bundle raw bytes changed for {input_id}")
        result[input_id] = path.read_bytes()
    return result


def canonical_inert_inspection(
    provenance: Mapping[str, Any],
    raw_by_id: Mapping[str, bytes],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    """Construct the complete canonical inert-inspection payload."""
    _validate_utc_timestamp(created_at_utc, "inert inspection created_at_utc")
    inputs = provenance.get("inputs")
    if not isinstance(inputs, list):
        raise LedgerError("response bundle inputs are not an array")
    python_records = [
        item for item in inputs if isinstance(item, Mapping) and item.get("input_id") == "certificate_python"
    ]
    if len(python_records) != 1:
        raise LedgerError("response bundle has no unique certificate_python input")
    raw_document = python_records[0].get("raw_document")
    if not isinstance(raw_document, Mapping) or type(raw_document.get("path")) is not str:
        raise LedgerError("certificate_python raw provenance is malformed")
    return {
        "schema": "r4_external_code_inert_inspection_v1",
        "created_at_utc": created_at_utc,
        "status": "PASS_INERT_BYTES_ONLY",
        "authority": provenance["authority"],
        "input_bindings": inputs,
        "certificate_python": {
            **_record(Path(str(raw_document["path"]))),
            "physical_line_count": len(raw_by_id["certificate_python"].splitlines()),
        },
        "decoded_as_program": False,
        "parsed_as_program": False,
        "compiled": False,
        "imported": False,
        "executed": False,
        "network_accessed": False,
        "remote_resource_rendered": False,
    }


def canonical_claim_ledger(
    provenance: Mapping[str, Any],
    raw_by_id: Mapping[str, bytes],
    inspection_record: Mapping[str, Any],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    """Construct the complete fixed-17 canonical claim-ledger payload."""
    _validate_utc_timestamp(created_at_utc, "claim ledger created_at_utc")
    claims = _claims(raw_by_id)
    return {
        "schema": "r4_quantitative_claim_ledger_v2",
        "created_at_utc": created_at_utc,
        "cutoff_date": "2026-07-23",
        "status": "COMPLETE",
        "quantitative_claims_complete": True,
        "claim_count": CLAIM_COUNT,
        "claim_ledger_builder_tool": _builder_tool_binding(),
        "authority": provenance["authority"],
        "input_bindings": provenance["inputs"],
        "response_ingest": provenance["response_ingest"],
        "external_code_inert_inspection": dict(inspection_record),
        "claims": claims,
        "candidate_ids": [UPPER, WITNESS],
        "external_response_code_executed": False,
        "claim_boundary": (
            "transcribed external quantitative claims and locally fixed W2d diagnostics; "
            "no candidate is admitted by this ledger"
        ),
    }


def _replay_bundle(authority_run: Path, response_run: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    archiver = _load_archiver()
    response, _claims = _claim_category(response_run)
    try:
        provenance = archiver.check_bundle(
            response,
            authority_run.resolve(strict=True),
        )
    except Exception as exc:
        raise LedgerError(f"response bundle replay failed: {exc}") from exc
    if not isinstance(provenance, dict):
        raise LedgerError("response bundle replay returned a malformed object")
    return provenance, _raw_inputs(provenance)


def replay_claim_ledger(
    authority_run: Path,
    response_run: Path,
    ledger_path: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Strictly replay one immutable ``claims/aNNN`` ledger and its inert inspection."""
    output_dir = _validate_existing_claim_output(response_run, ledger_path.parent)
    expected_ledger_path = output_dir / CLAIM_LEDGER_NAME
    if ledger_path.absolute() != expected_ledger_path:
        raise LedgerError(f"claim ledger path must be exactly {expected_ledger_path}")
    inspection_path = output_dir / INERT_INSPECTION_NAME
    inspection, _inspection_raw = _strict_json(inspection_path, "external-code inert inspection")
    ledger, _ledger_raw = _strict_json(expected_ledger_path, "quantitative claim ledger")
    provenance, raw_by_id = _replay_bundle(authority_run, response_run)

    ingest_time = _validate_utc_timestamp(
        provenance.get("created_at_utc"),
        "response ingest created_at_utc",
    )
    inspection_time = _validate_utc_timestamp(
        inspection.get("created_at_utc"),
        "inert inspection created_at_utc",
    )
    ledger_time = _validate_utc_timestamp(
        ledger.get("created_at_utc"),
        "claim ledger created_at_utc",
    )
    if not ingest_time <= inspection_time <= ledger_time:
        raise LedgerError("response ingest, inert inspection, and ledger timestamps are out of order")

    expected_inspection = canonical_inert_inspection(
        provenance,
        raw_by_id,
        created_at_utc=str(inspection["created_at_utc"]),
    )
    if inspection != expected_inspection:
        raise LedgerError("external-code inert inspection differs from complete canonical replay")
    expected_ledger = canonical_claim_ledger(
        provenance,
        raw_by_id,
        _record(inspection_path),
        created_at_utc=str(ledger["created_at_utc"]),
    )
    if ledger != expected_ledger:
        raise LedgerError("quantitative claim ledger differs from complete fixed-17 canonical replay")
    claims = ledger["claims"]
    if not isinstance(claims, list):
        raise LedgerError("quantitative claim ledger claims are not an array")
    by_id = {
        str(item["claim_id"]): item for item in claims if isinstance(item, dict) and type(item.get("claim_id")) is str
    }
    if len(by_id) != CLAIM_COUNT or tuple(by_id) != CLAIM_IDS:
        raise LedgerError("quantitative claim ledger IDs are not the fixed ordered 17 claims")
    return ledger, by_id


def build_ledger(
    authority_run: Path,
    response_run: Path,
    output_dir: Path,
) -> dict[str, Any]:
    _validate_claim_output_target(response_run, output_dir)
    provenance, raw_by_id = _replay_bundle(authority_run, response_run)
    inspection = canonical_inert_inspection(
        provenance,
        raw_by_id,
        created_at_utc=_utc_now(),
    )
    output_dir = _create_claim_output_dir(response_run, output_dir)
    inspection_path = output_dir / INERT_INSPECTION_NAME
    _publish_json(inspection_path, inspection)
    ledger = canonical_claim_ledger(
        provenance,
        raw_by_id,
        _record(inspection_path),
        created_at_utc=_utc_now(),
    )
    ledger_path = output_dir / CLAIM_LEDGER_NAME
    _publish_json(ledger_path, ledger)
    replayed, _by_id = replay_claim_ledger(authority_run, response_run, ledger_path)
    return replayed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-run", type=Path, required=True)
    parser.add_argument("--response-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        ledger = build_ledger(args.authority_run, args.response_run, args.output_dir)
    except (LedgerError, OSError, ValueError) as exc:
        print(f"R4_LEDGER_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(ledger, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
