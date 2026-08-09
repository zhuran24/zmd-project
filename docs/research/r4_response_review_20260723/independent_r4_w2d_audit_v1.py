#!/usr/bin/env python3
"""Independently classify the pinned W2d evidence without starting work."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


EXPECTED_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
BASE = Path("docs/research/witness_constructor_20260717/07_routing_aware")
GEOMETRY = BASE / "recovery_runs/resume-20260720T101428Z-IrO7qi/geometry"
ASSEMBLY = GEOMETRY / "anchor7_34_c5_x67_assembly_builds/run-20260720T182204Z-ea407fa"
C3_RUN = GEOMETRY / "anchor7_34/c3_trace_tuned_formal_runs/run-20260720T185210Z-ea407fa"
C5_RUN = GEOMETRY / "anchor7_34_c5_x67_resume_formal_runs/run-20260720T183943Z-ea407fa"
FILES = {
    "closeout_json": (
        BASE / "08_track_w_w2d_failure_report_20260721.json",
        "8dc19571cdf5ff0912346a3acbdb4a885d2e092d1a7a74d6db01a8f3a64507e0",
    ),
    "composer": (
        ASSEMBLY / "build_only_report.json",
        "27adbd468fe8bac7bbf2333be11d98e51e092ef07bba3b936305402e2c93df8d",
    ),
    "manifest_c0": (
        ASSEMBLY / "x67_pending_manifest_c0_swap.json",
        "99fa30698c28a8fedb2189e159333373a9dea2012e691e8d917547a5d0a654a4",
    ),
    "manifest_c1": (
        ASSEMBLY / "x67_pending_manifest_c1_swap.json",
        "2baa5f198cea987cfc86f606468a6aa5d5605b8f17c688621109394ac623997f",
    ),
    "c3_result": (
        C3_RUN / "c3-t12-4-3-trace-a001/result.json",
        "7b068e1eb1239b92074f47c5555f770f1b90672f12d923b73564cb1ef149fc0b",
    ),
    "c5_result": (
        C5_RUN / "c5-t10-4-4-x67-resume-a001/result.json",
        "cff12e728167cb2af7abe38a5e4ca1860e36ec1889a58fb147cd0dcc1324052b",
    ),
}


class AuditError(RuntimeError):
    """The pinned W2d evidence did not replay exactly."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def regular(root: Path, relative: Path) -> Path:
    path = root / relative
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {relative}")
    require(path.resolve(strict=True) == path.absolute(), f"aliased file: {relative}")
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def component_target(manifest: dict[str, Any], component: int) -> list[int]:
    rows = manifest.get("components")
    require(isinstance(rows, list) and len(rows) == 17, "manifest is not 17-component")
    indexed = {row.get("component"): row for row in rows if isinstance(row, dict)}
    require(set(indexed) == set(range(17)), "manifest component IDs differ")
    return indexed[component].get("target")


def audit(root_arg: Path) -> dict[str, Any]:
    require(not root_arg.is_symlink(), "W2d root is a symlink")
    root = root_arg.resolve(strict=True)
    head = regular(root, Path(".git/HEAD")).read_text(encoding="ascii").strip()
    require(re.fullmatch(r"[0-9a-f]{40}", head) is not None, "HEAD is not detached")
    require(head == EXPECTED_HEAD, "W2d HEAD differs")
    identities: dict[str, str] = {}
    documents: dict[str, dict[str, Any]] = {}
    for name, (relative, expected) in FILES.items():
        path = regular(root, relative)
        actual = sha256(path)
        require(actual == expected, f"{name} SHA-256 differs")
        identities[name] = actual
        if relative.suffix == ".json":
            documents[name] = strict_json(path)

    report = documents["closeout_json"]
    composer = documents["composer"]
    manifests = [documents["manifest_c0"], documents["manifest_c1"]]
    c3, c5 = documents["c3_result"], documents["c5_result"]
    branches = {"c0_swap_m3_to_m6", "c1_swap_m3_to_m6"}
    require(report.get("baseline_head") == head, "closeout baseline differs")
    require(report.get("direction_gate") == "W2d", "closeout gate differs")
    require(
        report.get("status") == "CURRENT_CONSTRUCTION_CAMPAIGN_CLOSED_WITHOUT_WITNESS",
        "W2d is not closed",
    )
    require(report["decisive_gate"].get("exact_manifest_count") == 2, "manifest count differs")
    require(
        {item.get("count_closure_branch") for item in manifests} == branches,
        "manifest branches differ",
    )
    require(all(component_target(item, 3) == [12, 4, 3] for item in manifests), "c3 rows differ")
    closure = composer.get("manifest_contract", {}).get("exact_count_closure_branches", {})
    require(set(closure) == branches, "composer branch set differs")
    require(all(closure[name].get("c3") == [12, 4, 3] for name in branches), "composer c3 differs")
    require(composer.get("candidate_emitted") is False, "composer emitted a candidate")
    require(c3.get("target") == [12, 4, 3], "c3 target differs")
    require(c3.get("status") == "INFEASIBLE", "c3 status differs")
    require(c3.get("classification") == "SOUND_CUT_MODEL_INFEASIBLE", "c3 class differs")
    c3_resume = c3.get("resume_accounting", {})
    require(c3_resume.get("imported_targeted_separator_cut_count") == 7156, "c3 import differs")
    require(c3_resume.get("continuation_targeted_separator_cut_count") == 12, "c3 new cuts differ")
    require(c3_resume.get("total_targeted_separator_cut_count") == 7168, "c3 total differs")
    require(c3.get("candidate_no_good_count") == 0, "c3 candidate nogood exists")
    require(c5.get("target") == [10, 4, 4], "c5 target differs")
    require(c5.get("status") == "UNKNOWN", "c5 status differs")
    require(c5.get("classification") == "NO_ACCEPTED_CANDIDATE", "c5 class differs")
    c5_resume = c5.get("resume_accounting", {})
    require(c5_resume.get("total_targeted_separator_cut_count") == 4010, "c5 total differs")
    require(c5.get("candidate_no_good_count") == 0, "c5 candidate nogood exists")
    stopped = set(report.get("stopped_work", []))
    require("no Track W solver or router launch" in stopped, "W2d STOP is absent")
    return {
        "schema": "r4_independent_checker_output_v1",
        "checker_id": "w2d_audit",
        "results": {
            "w2d_authority_identity": {"root": str(root), "head": head, "file_sha256": identities},
            "common_c3_gate": {
                "component_count": 17,
                "exact_manifest_count": 2,
                "target": [12, 4, 3],
                "both_manifests_require_target": True,
            },
            "c3_cut_accounting": {
                "status": "INFEASIBLE",
                "imported_sound_cuts": 7156,
                "new_sound_cuts": 12,
                "total_sound_cuts": 7168,
                "candidate_no_good_count": 0,
            },
            "c5_separate_corpus": {
                "target": [10, 4, 4],
                "status": "UNKNOWN",
                "total_sound_cuts": 4010,
                "candidate_no_good_count": 0,
            },
            "stop_and_claim_boundary": {
                "w2d_stop": True,
                "witness_established": False,
                "global_infeasibility_established": False,
                "search_authorized": False,
            },
            "repair_prerequisites": {
                "classification": "NEEDS_PREREQUISITES",
                "avoids_common_c3_gate": False,
                "reason": "A c5-only repair leaves both exact manifests' infeasible c3 row unchanged.",
                "required": [
                    "A hash-pinned exact 17-component manifest avoiding c3 (12,4,3).",
                    "Independent soundness review for every guarded repair cut.",
                    "Proof that no candidate nogood or UNKNOWN is treated as exclusion.",
                    "Supervisory authorization superseding W2d STOP before any search.",
                ],
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("w2d_root", type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.w2d_root)
    except (AuditError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        failure = {"schema": "r4_independent_checker_output_v1", "checker_id": "w2d_audit", "error": str(exc)}
        print(json.dumps(failure))
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
