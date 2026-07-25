#!/usr/bin/env python3
"""Close the three geometry gates before any PB encoding is permitted."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any


SCHEMA = "b1_sidewise_geometry_admission_v1"
AUTHORITY_SCHEMA = "b1_sidewise_geometry_pre_run_authority_v1"
HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
EXPECTED_ATTACKS = [
    "core_two_faces_must_remain_one_entity",
    "manufacturing_input_output_one_entity",
    "partial_overlap_not_full_span",
    "eight_distinct_entity_endpoint_budget",
    "raw_exact_and_final_unmarked",
    "storage_box_safe_relaxation",
    "orientation_and_map_edge",
    "band_delta_exact",
]


class GateError(RuntimeError):
    """Raised when geometry admission cannot be closed exactly."""


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_one(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    fd = os.open(
        path.absolute(),
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise GateError(f"{label}: not regular")
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
        raise GateError(f"{label}: changed during read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise GateError(f"{label}: short read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
    }


def parse(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise GateError(f"{label}: duplicate key {key!r}")
            value[key] = item
        return value

    def reject(value: str) -> Any:
        raise GateError(f"{label}: non-integer JSON number {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateError(f"{label}: malformed JSON: {exc}") from exc


def require(ok: bool, message: str) -> None:
    if not ok:
        raise GateError(message)


def load_json(path: Path, label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, identity = read_one(path, label)
    value = parse(raw, label)
    require(isinstance(value, dict), f"{label}: not an object")
    return value, identity


def pinned_match(
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


def build(
    authority: dict[str, Any],
    authority_identity: dict[str, Any],
    tool_identity: dict[str, Any],
    primary: dict[str, Any],
    primary_identity: dict[str, Any],
    independent: dict[str, Any],
    independent_identity: dict[str, Any],
    verdict: dict[str, Any],
    verdict_identity: dict[str, Any],
) -> dict[str, Any]:
    require(
        authority.get("schema_version") == AUTHORITY_SCHEMA
        and authority.get("status") == "GEOMETRY_PRE_RUN_AUTHORITY_PASS"
        and authority.get("head") == HEAD,
        "pre-run geometry authority failed",
    )
    tools = authority.get("tools")
    require(isinstance(tools, dict), "authority tools missing")
    pinned_match(tool_identity, tools.get("geometry_gate", {}), "geometry gate")
    require(
        primary.get("schema_version")
        == "b1_sidewise_primary_recomputation_v1"
        and primary.get("status") == "PASS",
        "primary recomputation failed",
    )
    require(
        independent.get("schema_version")
        == "b1_sidewise_independent_recomputation_v1"
        and independent.get("status") == "PASS",
        "independent recomputation failed",
    )
    pinned_match(
        primary.get("tool", {}),
        tools.get("primary_recomputation", {}),
        "primary tool",
    )
    pinned_match(
        independent.get("tool", {}),
        tools.get("independent_recomputation", {}),
        "independent tool",
    )
    require(
        verdict.get("schema_version")
        == "b1_sidewise_geometry_adversarial_verdict_v1"
        and verdict.get("status") == "PASS"
        and verdict.get("decision") == "GEOMETRY_ADVERSARIAL_PASS",
        "adversarial verdict failed",
    )
    pinned_match(
        verdict.get("tool", {}),
        tools.get("adversarial_builder", {}),
        "adversarial builder",
    )
    inputs = verdict.get("inputs")
    require(isinstance(inputs, dict), "verdict inputs missing")
    require(
        inputs.get("primary_recomputation") == primary_identity
        and inputs.get("independent_recomputation") == independent_identity,
        "verdict does not bind the supplied report bytes",
    )
    attacks = verdict.get("attacks")
    require(
        isinstance(attacks, list)
        and [item.get("id") for item in attacks if isinstance(item, dict)]
        == EXPECTED_ATTACKS
        and all(
            isinstance(item, dict) and item.get("status") == "PASS"
            for item in attacks
        ),
        "adversarial attack ledger is incomplete or reordered",
    )
    expected_derived = {
        "entity_max_census": {"0": 170, "1": 89, "2": 3, "3": 4},
        "top_eight": [3, 3, 3, 3, 2, 2, 2, 1],
        "top_eight_sum": 19,
        "marked_inside_cap": 85,
        "ordinary_inside_cap": 124,
        "combined_inside_cap": 209,
        "ceiling_orientations_excluded": [[22, 54], [54, 22]],
        "candidate_upper_if_formally_verified": [1188, 18],
    }
    require(verdict.get("derived") == expected_derived, "verdict derivation drifted")
    expected_scope = {
        "geometry_layer_only": True,
        "pb_or_formal_proof": False,
        "upper_updated": False,
        "witness_or_attainability": False,
        "production_certified": False,
    }
    require(
        verdict.get("admission_scope") == expected_scope,
        "verdict claim boundary drifted",
    )
    primary_results = primary.get("results")
    independent_results = independent.get("results")
    require(
        isinstance(primary_results, dict)
        and isinstance(independent_results, dict),
        "recomputation results missing",
    )
    ceiling = primary_results.get("ceiling_exclusion")
    band = primary_results.get("band_composition")
    require(
        isinstance(ceiling, dict)
        and ceiling.get("combined_inside_cap") == 209
        and ceiling.get("rectangle_plus_outside_cells") == 1321
        and ceiling.get("available_cell_cap") == 1320
        and ceiling.get("excluded") is True,
        "primary ceiling exclusion semantics drifted",
    )
    require(
        independent_results.get("combined_inside_cap") == 209
        and independent_results.get("rectangle_plus_outside_cells") == 1321,
        "independent ceiling exclusion semantics drifted",
    )
    require(
        isinstance(band, dict)
        and band.get("old_band_count") == 2084
        and band.get("candidate_band_count") == 2086
        and band.get("new_ceiling_orientations")
        == [[22, 54], [54, 22]]
        and band.get("union_exact") is True,
        "band composition semantics drifted",
    )
    documents = authority.get("documents")
    require(
        isinstance(documents, dict)
        and inputs.get("necessity_proof") == documents.get("necessity_proof"),
        "verdict does not bind the authority-pinned paper proof",
    )
    return {
        "schema_version": SCHEMA,
        "status": "PASS",
        "decision": "ADMITTED_FOR_PB_ENCODER",
        "geometry_authority": authority_identity,
        "inputs": {
            "primary_recomputation": primary_identity,
            "independent_recomputation": independent_identity,
            "adversarial_verdict": verdict_identity,
            "necessity_proof": documents["necessity_proof"],
        },
        "tool": tool_identity,
        "established": {
            "paper_necessity": True,
            "primary_strict_recomputation": True,
            "independent_strict_recomputation": True,
            "adversarial_review": True,
            "smm_209_necessary_bound": True,
            "ceiling_orientations": [[22, 54], [54, 22]],
            "candidate_band_delta_exact": True,
        },
        "next_gate": "PB_TRANSLATION_ADMISSION",
        "claim_boundary": {
            "geometry_admitted_for_encoder_design": True,
            "formal_unsat_not_yet_established": True,
            "upper_remains": [1188, 22],
            "lower_remains": "absent",
            "witness_or_attainability": False,
            "optimality": False,
            "production_certified": False,
        },
    }


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
                raise GateError("short output write")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-authority", type=Path, required=True)
    parser.add_argument("--primary-report", type=Path, required=True)
    parser.add_argument("--independent-report", type=Path, required=True)
    parser.add_argument("--adversarial-verdict", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        authority, authority_identity = load_json(
            args.geometry_authority, "geometry authority"
        )
        primary, primary_identity = load_json(args.primary_report, "primary")
        independent, independent_identity = load_json(
            args.independent_report, "independent"
        )
        verdict, verdict_identity = load_json(
            args.adversarial_verdict, "adversarial verdict"
        )
        _, tool_identity = read_one(Path(__file__), "geometry gate")
        payload = build(
            authority,
            authority_identity,
            tool_identity,
            primary,
            primary_identity,
            independent,
            independent_identity,
            verdict,
            verdict_identity,
        )
        raw = (
            json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False)
            + "\n"
        ).encode()
        require(not args.output.exists() and not args.output.is_symlink(), "output exists")
        require(
            args.output.parent.is_dir() and not args.output.parent.is_symlink(),
            "output parent is not a real directory",
        )
        write_once(args.output, raw)
    except (OSError, GateError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 2
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"],
                "output": str(args.output),
                "size_bytes": len(raw),
                "sha256": sha(raw),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
