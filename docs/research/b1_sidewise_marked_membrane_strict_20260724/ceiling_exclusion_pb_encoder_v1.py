#!/usr/bin/env python3
"""Emit the transparent two-selector OPB for the admitted ceiling pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any


HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
AUTHORITY_SCHEMA = "b1_sidewise_pb_pre_run_authority_v1"
MODEL_SCHEMA = "b1_sidewise_ceiling_exclusion_pb_v1"
SEMANTICS = (
    "given_geometry_admission_no_body_empty_22x54_or_54x22_"
    "satisfies_smm209_cell_cap_v1"
)
PROOF_LIMIT_BYTES = 5_000_000_000
LOW_WATER_BYTES = 10 * 1024 * 1024 * 1024
RESERVATION_BYTES = PROOF_LIMIT_BYTES
ORIENTATIONS = ((22, 54), (54, 22))


class EncoderError(RuntimeError):
    """Raised when authority, arithmetic, or output closure fails."""


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def snapshot(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    fd = os.open(
        path.absolute(),
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise EncoderError(f"{label}: not regular")
        chunks: list[bytes] = []
        while True:
            block = os.read(fd, 1 << 20)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise EncoderError(f"{label}: changed during read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise EncoderError(f"{label}: short read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
    }


def strict_json(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise EncoderError(f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise EncoderError(f"{label}: non-integer JSON {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EncoderError(f"{label}: malformed JSON: {exc}") from exc


def require(ok: bool, message: str) -> None:
    if not ok:
        raise EncoderError(message)


def match_identity(
    actual: dict[str, Any],
    pinned: dict[str, Any],
    label: str,
) -> None:
    require(
        all(
            actual.get(field) == pinned.get(field)
            for field in ("size_bytes", "sha256", "mode_octal")
        ),
        f"{label}: byte identity drifted",
    )


def load_authority(
    authority_path: Path,
    tool_identity: dict[str, Any],
    geometry_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    authority_raw, authority_identity = snapshot(authority_path, "PB authority")
    authority = strict_json(authority_raw, "PB authority")
    require(isinstance(authority, dict), "PB authority is not an object")
    require(
        authority.get("schema_version") == AUTHORITY_SCHEMA
        and authority.get("status") == "PB_PRE_RUN_AUTHORITY_PASS"
        and authority.get("head") == HEAD,
        "PB authority status/head mismatch",
    )
    tools = authority.get("tools")
    require(isinstance(tools, dict), "PB authority tools missing")
    match_identity(tool_identity, tools.get("encoder", {}), "encoder")
    geometry_raw, geometry_identity = snapshot(
        geometry_path, "geometry admission"
    )
    match_identity(
        geometry_identity,
        authority.get("geometry_admission", {}),
        "geometry admission",
    )
    geometry = strict_json(geometry_raw, "geometry admission")
    require(
        isinstance(geometry, dict)
        and geometry.get("schema_version")
        == "b1_sidewise_geometry_admission_v1"
        and geometry.get("status") == "PASS"
        and geometry.get("decision") == "ADMITTED_FOR_PB_ENCODER",
        "geometry admission semantics failed",
    )
    established = geometry.get("established")
    require(
        isinstance(established, dict)
        and established.get("smm_209_necessary_bound") is True
        and established.get("ceiling_orientations")
        == [[22, 54], [54, 22]]
        and established.get("candidate_band_delta_exact") is True,
        "geometry admission theorem set drifted",
    )
    return authority, authority_identity, geometry_identity


def variable_map() -> dict[str, Any]:
    variables: list[dict[str, Any]] = []
    for variable_id, (width, height) in enumerate(ORIENTATIONS, start=1):
        side_sum = width + height
        marked_inside = (2 * side_sum + 19) // 2
        ordinary_inside = side_sum + 48
        combined_inside = marked_inside + ordinary_inside
        outside_incidence = 628 + 110 - combined_inside
        outside_cells = (outside_incidence + 3) // 4
        total_cells = width * height + outside_cells
        coefficient = 1320 - total_cells
        record = {
            "id": variable_id,
            "name": f"ceiling__w_{width:02d}__h_{height:02d}",
            "kind": "oriented_ceiling_selector",
            "width": width,
            "height": height,
            "area": width * height,
            "side_sum": side_sum,
            "entity_endpoint_budget": 19,
            "marked_inside_cap": marked_inside,
            "ordinary_inside_cap": ordinary_inside,
            "combined_inside_cap": combined_inside,
            "outside_incidence_floor": outside_incidence,
            "outside_cell_floor": outside_cells,
            "total_required_cells": total_cells,
            "free_cell_cap": 1320,
            "coefficient": coefficient,
        }
        variables.append(record)
    require(
        variables
        == [
            {
                "id": 1,
                "name": "ceiling__w_22__h_54",
                "kind": "oriented_ceiling_selector",
                "width": 22,
                "height": 54,
                "area": 1188,
                "side_sum": 76,
                "entity_endpoint_budget": 19,
                "marked_inside_cap": 85,
                "ordinary_inside_cap": 124,
                "combined_inside_cap": 209,
                "outside_incidence_floor": 529,
                "outside_cell_floor": 133,
                "total_required_cells": 1321,
                "free_cell_cap": 1320,
                "coefficient": -1,
            },
            {
                "id": 2,
                "name": "ceiling__w_54__h_22",
                "kind": "oriented_ceiling_selector",
                "width": 54,
                "height": 22,
                "area": 1188,
                "side_sum": 76,
                "entity_endpoint_budget": 19,
                "marked_inside_cap": 85,
                "ordinary_inside_cap": 124,
                "combined_inside_cap": 209,
                "outside_incidence_floor": 529,
                "outside_cell_floor": 133,
                "total_required_cells": 1321,
                "free_cell_cap": 1320,
                "coefficient": -1,
            },
        ],
        "ceiling arithmetic drifted",
    )
    return {
        "schema_version": "b1_sidewise_ceiling_variable_map_v1",
        "semantics": SEMANTICS,
        "variables": variables,
    }


def render_formula() -> bytes:
    lines = [
        "* #variable= 2 #constraint= 3 #equal= 1 intsize= 0",
        (
            f"* model={MODEL_SCHEMA} semantics={SEMANTICS} "
            "target=1188,18 old_upper=1188,22 "
            "given_smm209=true"
        ),
        "+1 x1 +1 x2 = 1 ;",
        "-1 x1 >= 0 ;",
        "-1 x2 >= 0 ;",
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode()


def write_once(path: Path, raw: bytes) -> None:
    fd = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(fd, raw[offset:])
            if count <= 0:
                raise EncoderError("short output write")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)


def estimate_payload(
    authority_identity: dict[str, Any],
    geometry_identity: dict[str, Any],
    tool_identity: dict[str, Any],
) -> dict[str, Any]:
    formula = render_formula()
    mapping = json_bytes(variable_map())
    return {
        "schema_version": "b1_sidewise_ceiling_estimate_v1",
        "status": "PASS",
        "model": MODEL_SCHEMA,
        "semantics": SEMANTICS,
        "pb_authority": authority_identity,
        "geometry_admission": geometry_identity,
        "tool": tool_identity,
        "counts": {
            "variables": 2,
            "constraints": 3,
            "equalities": 1,
            "oriented_ceiling_dimensions": 2,
        },
        "predicted": {
            "formula_size_bytes": len(formula),
            "formula_sha256": sha(formula),
            "variable_map_size_bytes": len(mapping),
            "variable_map_sha256": sha(mapping),
        },
        "resource_contract": {
            "proof_limit_bytes": PROOF_LIMIT_BYTES,
            "artifact_low_water_bytes": LOW_WATER_BYTES,
            "proof_reservation_bytes": RESERVATION_BYTES,
            "required_free_before_formal_bytes": (
                LOW_WATER_BYTES + RESERVATION_BYTES
            ),
            "memory_high_bytes": 35 * 1024**3,
            "memory_max_bytes": 39 * 1024**3,
            "memory_swap_max_bytes": 16 * 1024**3,
            "oom_policy": "continue",
            "single_worker": True,
        },
        "formal_run_authorized": False,
        "claim_boundary": {
            "estimate_only": True,
            "unsat_or_proof": False,
            "upper": [1188, 22],
            "lower": "absent",
        },
    }


def publish_estimate(
    output: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    require(not output.exists() and not output.is_symlink(), "estimate exists")
    require(
        output.parent.is_dir() and not output.parent.is_symlink(),
        "estimate parent is not a real directory",
    )
    raw = json_bytes(payload)
    write_once(output, raw)
    return {
        "status": payload["status"],
        "mode": "estimate",
        "output": str(output),
        "size_bytes": len(raw),
        "sha256": sha(raw),
    }


def publish_build(
    output_dir: Path,
    estimate_path: Path,
    authority_identity: dict[str, Any],
    geometry_identity: dict[str, Any],
    tool_identity: dict[str, Any],
) -> dict[str, Any]:
    require(
        not output_dir.exists() and not output_dir.is_symlink(),
        "build directory exists",
    )
    estimate_raw, estimate_identity = snapshot(estimate_path, "estimate")
    estimate = strict_json(estimate_raw, "estimate")
    expected = estimate_payload(
        authority_identity, geometry_identity, tool_identity
    )
    require(estimate == expected, "estimate semantic replay failed")
    output_dir.mkdir(mode=0o755)
    formula_raw = render_formula()
    map_raw = json_bytes(variable_map())
    formula_id = {
        "path": "formula.opb",
        "size_bytes": len(formula_raw),
        "sha256": sha(formula_raw),
    }
    map_id = {
        "path": "variable_map.json",
        "size_bytes": len(map_raw),
        "sha256": sha(map_raw),
    }
    meta = {
        "schema_version": "b1_sidewise_ceiling_encoder_metadata_v1",
        "status": "BUILD_ONLY",
        "model": MODEL_SCHEMA,
        "semantics": SEMANTICS,
        "pb_authority": authority_identity,
        "geometry_admission": geometry_identity,
        "estimate": estimate_identity,
        "encoder": tool_identity,
        "formula": formula_id,
        "variable_map": map_id,
        "counts": {
            "variables": 2,
            "constraints": 3,
            "equalities": 1,
        },
        "band_composition": {
            "old_verified_band_count": 2084,
            "new_ceiling_pair_count": 2,
            "candidate_band_count": 2086,
            "candidate_upper": [1188, 18],
        },
        "formal_run_authorized": False,
        "claim_boundary": {
            "build_only": True,
            "translation_not_yet_admitted": True,
            "unsat_or_proof": False,
            "upper": [1188, 22],
            "lower": "absent",
            "production_certified": False,
        },
    }
    meta_raw = json_bytes(meta)
    meta_id = {
        "path": "encoder.meta.json",
        "size_bytes": len(meta_raw),
        "sha256": sha(meta_raw),
    }
    build_record = {
        "schema_version": "b1_sidewise_ceiling_build_record_v1",
        "status": "BUILD_ONLY_PASS",
        "inputs": {
            "pb_authority": authority_identity,
            "geometry_admission": geometry_identity,
            "estimate": estimate_identity,
            "encoder": tool_identity,
        },
        "outputs": {
            "formula": formula_id,
            "variable_map": map_id,
            "metadata": meta_id,
        },
        "formal_run_authorized": False,
    }
    build_raw = json_bytes(build_record)
    build_id = {
        "path": "build_record.json",
        "size_bytes": len(build_raw),
        "sha256": sha(build_raw),
    }
    files = {
        "formula.opb": formula_raw,
        "variable_map.json": map_raw,
        "encoder.meta.json": meta_raw,
        "build_record.json": build_raw,
        "estimate.json": estimate_raw,
    }
    for name, raw in files.items():
        write_once(output_dir / name, raw)
    sums = "".join(
        f"{sha(raw)}  {name}\n" for name, raw in sorted(files.items())
    ).encode()
    write_once(output_dir / "SHA256SUMS", sums)
    return {
        "status": "BUILD_ONLY_PASS",
        "mode": "build",
        "output_dir": str(output_dir),
        "formula": formula_id,
        "variable_map": map_id,
        "metadata": meta_id,
        "build_record": build_id,
        "manifest": {
            "path": "SHA256SUMS",
            "size_bytes": len(sums),
            "sha256": sha(sums),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pb-authority", type=Path, required=True)
    parser.add_argument("--geometry-admission", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--estimate-output", type=Path)
    modes.add_argument("--build-dir", type=Path)
    parser.add_argument("--estimate", type=Path)
    args = parser.parse_args()
    try:
        _, tool_identity = snapshot(Path(__file__), "encoder")
        _, authority_identity, geometry_identity = load_authority(
            args.pb_authority,
            tool_identity,
            args.geometry_admission,
        )
        if args.estimate_output is not None:
            result = publish_estimate(
                args.estimate_output,
                estimate_payload(
                    authority_identity,
                    geometry_identity,
                    tool_identity,
                ),
            )
        else:
            require(args.estimate is not None, "--estimate is required for build")
            result = publish_build(
                args.build_dir,
                args.estimate,
                authority_identity,
                geometry_identity,
                tool_identity,
            )
    except (OSError, EncoderError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
