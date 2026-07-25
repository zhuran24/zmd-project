#!/usr/bin/env python3
"""Search one target directly in the simultaneous three-column final35 geometry.

The all-residual model is preferred.  The optional-terminal model is available
only as an explicit fallback.  Every invocation writes one exclusive checkpoint
under this recovery run.  No production router is imported or run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
HERE = RECOVERY / "big_bays"
ALL_RESIDUAL_SCRIPT = HERE / "big_bay_all_residual_search.py"
REPLAY_SCRIPT = HERE / "independent_periodic_big_bay_replay.py"
EXPECTED = {
    ALL_RESIDUAL_SCRIPT: "7d357c8ab1293698bd9381202890380aeb3464a3b6b5952cd5ab5df5803ef92a",
    REPLAY_SCRIPT: "59ae9ec52084f463833751ebd45fbadd6a7287a52da937c50cfd697ea78135c7",
}


class SearchError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SearchError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


for pinned_path, expected_digest in EXPECTED.items():
    require(pinned_path.is_file(), f"missing pinned script: {pinned_path}")
    require(sha256(pinned_path) == expected_digest, f"script hash drift: {pinned_path}")

sys.path.insert(0, str(HERE))
import big_bay_all_residual_search as all_residual  # noqa: E402
import independent_periodic_big_bay_replay as replay  # noqa: E402


def combined_fixed(strict: Mapping[str, Any], bay_name: str) -> dict[str, Any]:
    raw = replay.fixed_geometry(strict, combined=True)
    return {
        **raw,
        "pole_anchors": raw["poles"],
        "c5": raw["bays"][bay_name],
        "origin": replay.BAYS[bay_name],
        "gateways": raw["gateways"][bay_name],
    }


def output_path(
    bay_name: str,
    target: tuple[int, int, int],
    model_name: str,
    seconds: float,
) -> Path:
    target_text = "-".join(str(value) for value in target)
    return HERE / "final35_attempts" / bay_name / f"t{target_text}_{model_name}_s{int(seconds)}.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bay", choices=tuple(replay.BAYS), default="c0")
    parser.add_argument("--target", type=int, nargs=3, required=True)
    parser.add_argument("--model", choices=("all-residual", "optional-terminal"), default="all-residual")
    parser.add_argument("--seconds", type=float, default=240.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    require(60.0 <= args.seconds <= 300.0, "seconds must be within [60,300]")
    require(args.workers == 8, "search is pinned to 8 workers")
    target = tuple(int(value) for value in args.target)
    require(len(target) == 3 and all(value >= 0 for value in target), "target")
    output = output_path(args.bay, target, args.model, args.seconds)
    require(not output.exists(), f"refusing overwrite: {output}")

    geometry = all_residual.geometry
    candidate = geometry.load_pinned(geometry.CANDIDATE_PATH)
    strict = geometry.load_pinned(geometry.STRICT_PATH)
    old = geometry.load_pinned(geometry.HINT_PATH)
    modes = geometry.base.strict_modes(strict)
    fixed = combined_fixed(strict, args.bay)
    poses, domain_counts = geometry.base.build_domain(candidate, modes, fixed)
    hints = geometry.hint_body_modes(old, args.bay, fixed["origin"])
    if args.model == "all-residual":
        result = all_residual.solve_all_residual(
            poses,
            target,
            fixed,
            hints,
            args.seconds,
            args.workers,
            20260721 + int(tuple(replay.BAYS).index(args.bay)),
        )
    else:
        result = geometry.base.solve_phase(
            poses,
            target,
            fixed,
            hints,
            args.seconds,
            args.workers,
            20261721 + int(tuple(replay.BAYS).index(args.bay)),
        )
    result.update(
        {
            "schema_version": "final35_big_bay_target_checkpoint.v1",
            "classification": "research_local_final35_big_bay_query_no_router",
            "claim_boundary": "One local final35 large-bay query only; no global layout or commodity-routing conclusion.",
            "bay": args.bay,
            "origin": list(fixed["origin"]),
            "target": list(target),
            "connectivity_model": args.model,
            "all_35_pole_anchors": [list(anchor) for anchor in sorted(fixed["pole_anchors"])],
            "simultaneous_moved_columns": {"17": 18, "29": 30, "41": 42},
            "domain_counts": domain_counts,
            "seconds_limit": args.seconds,
            "search_script_sha256": sha256(Path(__file__)),
            "pinned_script_sha256": {str(path): digest for path, digest in EXPECTED.items()},
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "status": result["status"]}, sort_keys=True))
    return 0 if result["status"] in {"OPTIMAL", "FEASIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
