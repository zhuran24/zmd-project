#!/usr/bin/env python3
"""No-overwrite c5 resume at crossing-protected anchor (57,34)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = ROOT / (
    "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
RUN = RECOVERY / "crossing-protected-c5-resume-kvlPpd"
CROSSING = RECOVERY / "crossing-protected-c5-vchJNd/run_crossing_search.py"
PRIOR_UNKNOWN = RECOVERY / "crossing-protected-c5-vchJNd/attempt_01_anchor_57_33.json"
HELPER_SOURCE = RECOVERY / "scripts/c5_pole_phase_search.py"
HINT = RECOVERY / "inputs/reduced_targeted_allocation_p7_36_final.json"
C11_RESULT = RECOVERY / "c11-protected-relocation-probe-EYLj1q/result.json"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
EXPECTED = {
    CROSSING: "e417106b7753376312470a1203e15312badf2ba9551d81d3e466519a5860861d",
    PRIOR_UNKNOWN: "1b17938c77a72e74da21e398049df82519a1ca896212c23db2191c57d191dcb9",
    HELPER_SOURCE: "c7053f9ff3adc41f6d5519c2d76e45b663de2cc4c8b21c53959cf8acff666620",
    HINT: "6c51a1ee5bef15e555242896a0a11da24c8f18746a215db53c277deee537ee80",
    C11_RESULT: "7777f458f4b6856f7fde55d7a923c32c691cac1d0a1363e707905de05766a230",
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}
ANCHOR = (57, 34)
TARGET = (12, 3, 3)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> int:
    for path, expected in EXPECTED.items():
        require(sha256(path) == expected, f"hash drift for {path}: {sha256(path)}")
    prior = json.loads(PRIOR_UNKNOWN.read_bytes())
    require(prior["status"] == "UNKNOWN", "prior result is not UNKNOWN")
    write_exclusive(
        RUN / "stage_00_start.json",
        {
            "schema_version": "crossing_protected_c5_resume_start.v1",
            "pid": os.getpid(),
            "anchor": list(ANCHOR),
            "target": list(TARGET),
            "seconds": 240,
            "workers": 8,
            "prior_unknown_path": str(PRIOR_UNKNOWN),
            "prior_unknown_sha256": EXPECTED[PRIOR_UNKNOWN],
            "prior_unknown_claim": "UNKNOWN gives no conclusion and is not excluded.",
            "input_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        },
    )
    crossing = load_module("crossing_resume_geometry", CROSSING)
    helper = load_module("crossing_resume_helper", HELPER_SOURCE)
    candidate = json.loads(CANDIDATE.read_bytes())
    strict = json.loads(STRICT.read_bytes())
    hint = json.loads(HINT.read_bytes())
    c11 = json.loads(C11_RESULT.read_bytes())
    fixed = crossing.build_fixed(helper, strict, ANCHOR)
    base = load_module("crossing_resume_base", crossing.BASE_RUNNER)
    require(base.c11_selected_still_legal(c11, fixed), "c11 selected invalidated")
    poses, domain_counts = helper.build_domain(candidate, helper.strict_modes(strict), fixed)
    result = helper.solve_phase(
        poses,
        TARGET,
        fixed,
        helper.hint_body_modes(hint, fixed["origin"]),
        240.0,
        8,
        20260934,
    )
    losses = crossing.quadrant_losses(set(fixed["protected"]), set(fixed["backbone"]))
    result.update(
        {
            "protected_rect": {"anchor": list(ANCHOR), "width": 6, "height": 7},
            "protected_cells": [list(cell) for cell in sorted(fixed["protected"])],
            "all_35_pole_anchors": [list(cell) for cell in sorted(fixed["pole_anchors"])],
            "backbone_overlap_cells": len(set(fixed["protected"]) & set(fixed["backbone"])),
            "new_body_forbidden_cells": len(set(fixed["protected"]) - set(fixed["backbone"])),
            "quadrant_new_forbidden": losses,
            "c11_selected_still_body_and_power_legal": True,
            "domain_counts": domain_counts,
        }
    )
    write_exclusive(RUN / "result.json", result)
    summary = {
        "schema_version": "crossing_protected_c5_resume.v1",
        "status": result["status"],
        "classification": "research_local_weak_active_terminal_query_no_router",
        "claim_boundary": (
            "Only anchor (57,34) and c5 target (12,3,3) are classified. UNKNOWN gives no conclusion. "
            "A feasible result remains local until c4/c9/c10 and independent replays accept."
        ),
        "result_path": str(RUN / "result.json"),
        "result_sha256": sha256(RUN / "result.json"),
    }
    write_exclusive(RUN / "summary.json", summary)
    print(f"anchor={ANCHOR} status={result['status']} seconds={result['wall_time_seconds']:.3f}", flush=True)
    return 0 if result["status"] in {"OPTIMAL", "FEASIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
