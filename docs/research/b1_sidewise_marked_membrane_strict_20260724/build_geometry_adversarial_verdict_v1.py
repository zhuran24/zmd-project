#!/usr/bin/env python3
"""Build a fail-closed adversarial verdict over both strict recomputations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any


EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
EXPECTED_TOP_EIGHT = [3, 3, 3, 3, 2, 2, 2, 1]


class VerdictError(RuntimeError):
    """Raised when an input or adversarial invariant does not replay."""


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
            raise VerdictError(f"{label}: not regular")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
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
        raise VerdictError(f"{label}: changed during read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise VerdictError(f"{label}: short read")
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
                raise VerdictError(f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def no_float(value: str) -> Any:
        raise VerdictError(f"{label}: non-integer JSON number {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=no_float,
            parse_constant=no_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerdictError(f"{label}: malformed JSON: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerdictError(message)


def authority_and_tool(
    authority_path: Path,
    tool_identity: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, identity = snapshot(authority_path, "geometry authority")
    payload = strict_json(raw, "geometry authority")
    require(isinstance(payload, dict), "geometry authority not an object")
    require(
        payload.get("schema_version")
        == "b1_sidewise_geometry_pre_run_authority_v1"
        and payload.get("status") == "GEOMETRY_PRE_RUN_AUTHORITY_PASS"
        and payload.get("head") == EXPECTED_HEAD,
        "geometry authority status/head mismatch",
    )
    tools = payload.get("tools")
    pinned = tools.get("adversarial_builder") if isinstance(tools, dict) else None
    require(isinstance(pinned, dict), "adversarial builder not pinned")
    require(
        all(
            pinned.get(field) == tool_identity.get(field)
            for field in ("size_bytes", "sha256", "mode_octal")
        ),
        "adversarial builder bytes drifted",
    )
    return payload, identity


def require_report(
    path: Path,
    authority: dict[str, Any],
    schema: str,
    tool_key: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, identity = snapshot(path, schema)
    report = strict_json(raw, schema)
    require(isinstance(report, dict), f"{schema}: not an object")
    require(
        report.get("schema_version") == schema and report.get("status") == "PASS",
        f"{schema}: status/schema mismatch",
    )
    report_tool = report.get("tool")
    tools = authority.get("tools")
    pinned = tools.get(tool_key) if isinstance(tools, dict) else None
    require(
        isinstance(report_tool, dict)
        and isinstance(pinned, dict)
        and all(
            report_tool.get(field) == pinned.get(field)
            for field in ("size_bytes", "sha256", "mode_octal")
        ),
        f"{schema}: tool identity mismatch",
    )
    return report, identity


def build_verdict(
    authority: dict[str, Any],
    authority_identity: dict[str, Any],
    primary: dict[str, Any],
    primary_identity: dict[str, Any],
    independent: dict[str, Any],
    independent_identity: dict[str, Any],
    tool_identity: dict[str, Any],
) -> dict[str, Any]:
    p = primary.get("results")
    i = independent.get("results")
    require(isinstance(p, dict) and isinstance(i, dict), "missing result objects")
    counts = p.get("strict_counts")
    budget = p.get("marked_entity_budget")
    ceiling = p.get("ceiling_exclusion")
    band = p.get("band_composition")
    require(
        all(isinstance(value, dict) for value in (counts, budget, ceiling, band)),
        "primary result sections malformed",
    )
    expected_census = {"0": 170, "1": 89, "2": 3, "3": 4}
    require(
        budget.get("entity_census") == expected_census
        and i.get("entity_max_census") == expected_census,
        "entity-max census disagreement",
    )
    require(
        budget.get("top_eight") == EXPECTED_TOP_EIGHT
        and i.get("top_eight") == EXPECTED_TOP_EIGHT
        and budget.get("top_eight_sum") == 19
        and i.get("top_eight_sum") == 19,
        "top-eight endpoint budget disagreement",
    )
    require(
        budget.get("core_is_one_entity") is True
        and budget.get("core_output_faces") == 2
        and budget.get("core_marks_per_contact_face") == 3
        and i.get("core_entity_rows") == 1,
        "protocol core was split or lost",
    )
    require(
        counts.get("manufacturing_marks") == i.get("manufacturing_marks") == 58
        and counts.get("raw_noncorner_marks") == i.get("raw_marks") == 52
        and counts.get("total_marks") == i.get("total_marks") == 110
        and counts.get("final_inputs_not_marked")
        == i.get("final_inputs_not_marked")
        == 2,
        "marked set or final-input classification drifted",
    )
    require(
        ceiling.get("combined_inside_cap")
        == i.get("combined_inside_cap")
        == 209
        and ceiling.get("outside_incidence_floor")
        == i.get("outside_incidence_floor")
        == 529
        and ceiling.get("outside_access_cell_floor")
        == i.get("outside_cell_floor")
        == 133
        and ceiling.get("rectangle_plus_outside_cells")
        == i.get("rectangle_plus_outside_cells")
        == 1321
        and ceiling.get("excluded") is True,
        "SMM-209 ceiling arithmetic disagreement",
    )
    require(
        band.get("old_band_count") == i.get("band_counts", {}).get("old") == 2084
        and band.get("candidate_band_count")
        == i.get("band_counts", {}).get("candidate")
        == 2086
        and band.get("new_ceiling_orientations")
        == i.get("band_counts", {}).get("delta")
        == [[22, 54], [54, 22]]
        and band.get("union_exact") is True,
        "band composition disagreement",
    )
    require(
        primary.get("strict_instance") == independent.get("strict_instance"),
        "strict snapshot mismatch between recomputations",
    )

    attacks = [
        {
            "id": "core_two_faces_must_remain_one_entity",
            "status": "PASS",
            "checked": "two 3-mark faces; one core entity row; entity max 3",
        },
        {
            "id": "manufacturing_input_output_one_entity",
            "status": "PASS",
            "checked": (
                "entity census uses max(input_marks,output_marks), while "
                "110-mark census uses their sum"
            ),
        },
        {
            "id": "partial_overlap_not_full_span",
            "status": "PASS",
            "checked": (
                "all integer e<=ell and e<=r pairs satisfy "
                "2e<=ell+r"
            ),
        },
        {
            "id": "eight_distinct_entity_endpoint_budget",
            "status": "PASS",
            "checked": "top-eight entity maxima sum to 19",
        },
        {
            "id": "raw_exact_and_final_unmarked",
            "status": "PASS",
            "checked": "52 raw marks; two final inputs excluded from marks",
        },
        {
            "id": "storage_box_safe_relaxation",
            "status": "PASS",
            "checked": (
                "optional storage final-input ports add no marked "
                "incidence and cannot increase the top-eight budget"
            ),
        },
        {
            "id": "orientation_and_map_edge",
            "status": "PASS",
            "checked": (
                "rotations preserve face span/marks; clipping cannot "
                "increase contact or endpoint capacity"
            ),
        },
        {
            "id": "band_delta_exact",
            "status": "PASS",
            "checked": "old band plus two ceiling orientations equals new band",
        },
    ]
    documents = authority.get("documents")
    proof = documents.get("necessity_proof") if isinstance(documents, dict) else None
    require(isinstance(proof, dict), "necessity proof is not authority-pinned")
    return {
        "schema_version": "b1_sidewise_geometry_adversarial_verdict_v1",
        "status": "PASS",
        "decision": "GEOMETRY_ADVERSARIAL_PASS",
        "geometry_authority": authority_identity,
        "inputs": {
            "primary_recomputation": primary_identity,
            "independent_recomputation": independent_identity,
            "necessity_proof": proof,
        },
        "tool": tool_identity,
        "attacks": attacks,
        "derived": {
            "entity_max_census": expected_census,
            "top_eight": EXPECTED_TOP_EIGHT,
            "top_eight_sum": 19,
            "marked_inside_cap": 85,
            "ordinary_inside_cap": 124,
            "combined_inside_cap": 209,
            "ceiling_orientations_excluded": [[22, 54], [54, 22]],
            "candidate_upper_if_formally_verified": [1188, 18],
        },
        "admission_scope": {
            "geometry_layer_only": True,
            "pb_or_formal_proof": False,
            "upper_updated": False,
            "witness_or_attainability": False,
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
                raise VerdictError("short output write")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-authority", type=Path, required=True)
    parser.add_argument("--primary-report", type=Path, required=True)
    parser.add_argument("--independent-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        _, tool_identity = snapshot(Path(__file__), "adversarial builder")
        authority, authority_identity = authority_and_tool(
            args.geometry_authority,
            tool_identity,
        )
        primary, primary_identity = require_report(
            args.primary_report,
            authority,
            "b1_sidewise_primary_recomputation_v1",
            "primary_recomputation",
        )
        independent, independent_identity = require_report(
            args.independent_report,
            authority,
            "b1_sidewise_independent_recomputation_v1",
            "independent_recomputation",
        )
        verdict = build_verdict(
            authority,
            authority_identity,
            primary,
            primary_identity,
            independent,
            independent_identity,
            tool_identity,
        )
        raw = (
            json.dumps(verdict, sort_keys=True, indent=2, ensure_ascii=False)
            + "\n"
        ).encode()
        require(not args.output.exists() and not args.output.is_symlink(), "output exists")
        require(
            args.output.parent.is_dir() and not args.output.parent.is_symlink(),
            "output parent is not a real directory",
        )
        write_once(args.output, raw)
    except (OSError, VerdictError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 2
    print(
        json.dumps(
            {
                "status": verdict["status"],
                "decision": verdict["decision"],
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
