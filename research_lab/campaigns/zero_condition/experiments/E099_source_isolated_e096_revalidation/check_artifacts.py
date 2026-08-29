#!/usr/bin/env python3
"""Independent joins and branch guards for E099 source-isolated revalidation."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e099.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E099_source_isolated_e096_revalidation/run-002"
)
RESULT = RUN / "RESULT.json"
REPLAY = RUN / "INDEPENDENT_REPLAY.json"
COMPARISON = RUN / "PROJECTION_COMPARISON.json"
SOURCE_RESULT = RUN / "source-isolated-e096/RESULT.json"
TEMPLATE = RUN / "source-isolated-e096/TEMPLATE_INTERFACE.json"
SPATIAL = RUN / "source-isolated-e096/SPATIAL_INTERFACE_FRONTIER.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"

EXPECTED = {
    RUNNER: "f8af9579d8921d23fc57595360e460bc65b673e3ea0b393e4d1226614908acd0",
    RESULT: "cb602a987cd47382b8dd64ed224f931029d7a41abf2a9d367e2e6df21b767f55",
    REPLAY: "5963a1e1d1b7859a0820ef285a2cc46d0f57818ddcb155b67d0c3378344501f0",
    COMPARISON: "a0996ccff175974c3d52c537f4135295badcdd6836a7465aecb641d818ad4e7c",
    SOURCE_RESULT: "41e23ccc0344f2d5997307ce4fd042058c29257ebe650dee2ca8b6dec9455e7c",
    TEMPLATE: "f9201e96afb5e754e54efb0fa951840f9db12c48f40ec0bb581ebca45a712d1c",
    SPATIAL: "2c052f2da4964ceab45342555fa2f70b4df25972b4835d4579b5e628d5403ff5",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E099 check: {OUTPUT}")
    records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E099 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E099 artifact identity drift: {path}")
        records[str(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    result = load(RESULT)
    replay = load(REPLAY)
    comparison = load(COMPARISON)
    source = load(SOURCE_RESULT)
    template = load(TEMPLATE)
    spatial = load(SPATIAL)

    require(
        result["verdict"]
        == "SOURCE_ISOLATED_REPLAY_INVALIDATES_COMMITTED_E096_SELECTION",
        "E099 verdict drift",
    )
    require(
        result["decision"]
        == "RETRACT_E096_E097_AND_BUILD_HYBRID_INTERFACE_FROM_E095",
        "E099 decision drift",
    )
    require(
        result["source_execution"]["bytecode_cache_consumed_for_these_modules"]
        is False,
        "E099 source isolation marker drift",
    )
    require(replay["status"] == "PASS", "E099 independent replay is not PASS")
    require(
        replay["verdict"] == source["verdict"]
        == "TEMPLATE_AND_SPATIAL_INTERFACES_ARE_INCOMPARABLE",
        "E099 source/replay verdict join drift",
    )
    require(
        replay["decision"] == source["decision"]
        == "KEEP_BOTH_AND_BUILD_HYBRID_INTERFACE",
        "E099 source/replay decision join drift",
    )
    require(replay["selected_cut_id"] == "x_after_41", "E099 cut identity drift")
    require(comparison["source_matches_e098"] is True, "E099 E098 match drift")
    require(
        comparison["source_matches_committed_snapshot"] is False,
        "E099 committed-snapshot comparison drift",
    )
    require(
        int(comparison["committed_difference_count"]) == 19,
        "E099 committed difference count drift",
    )

    source_projection = comparison["source_projection"]
    committed_projection = comparison["committed_projection"]
    require(
        source_projection == result["source_stable_interface"],
        "E099 source projection/result drift",
    )
    require(source_projection["candidate_count"] == 4378, "candidate drift")
    require(source_projection["required_body_count"] == 91, "body demand drift")
    require(
        source_projection["template"]["group_candidate_counts"]
        == {
            "manufacturing_3x3": 1335,
            "manufacturing_5x5": 1018,
            "manufacturing_6x4": 2025,
        },
        "source template domain drift",
    )
    require(
        source_projection["selected"]["group_candidate_counts"]
        == {"high": 1399, "low": 2805, "separator": 174},
        "source spatial group drift",
    )
    require(
        source_projection["selected"]["group_anchor_counts"]
        == {"high": 23, "low": 66, "separator": 2},
        "source anchor group drift",
    )
    require(
        source_projection["selected"]["interface_occupancy_cell_count"] == 224,
        "source interface-cell drift",
    )
    require(
        source_projection["selected"]["interface_candidate_count"] == 1116,
        "source interface-candidate drift",
    )
    require(
        source_projection["selected"]["class_allocation_dimension_count"] == 8,
        "source allocation dimension drift",
    )
    require(
        math.isclose(
            float(
                source_projection["selected"][
                    "class_allocation_log2_box_upper_bound"
                ]
            ),
            25.39934468967273,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "source allocation-box drift",
    )

    require(
        committed_projection["selected"]["cut_id"] == "x_after_34",
        "committed cut comparison drift",
    )
    require(
        committed_projection["verdict"]
        == "SPATIAL_SEPARATOR_INTERFACE_DOMINATES_TEMPLATE_INTERFACE",
        "committed verdict comparison drift",
    )
    difference_paths = {row["path"] for row in comparison["committed_differences"]}
    for required_path in (
        "verdict",
        "decision",
        "selected.cut_id",
        "selected.group_candidate_counts.separator",
        "template.group_candidate_counts.manufacturing_5x5",
        "template.group_candidate_counts.manufacturing_6x4",
    ):
        require(required_path in difference_paths, f"missing difference: {required_path}")

    require(template["group_candidate_counts"] == source_projection["template"]["group_candidate_counts"], "template artifact join drift")
    selected = source["selected_spatial_cut"]
    require(selected["cut_id"] == "x_after_41", "source-result selected cut drift")
    require(
        int(spatial["guarded_cut_count"]) == int(replay["guarded_cut_count"]),
        "spatial guarded-count join drift",
    )

    payload = {
        "schema": "zmd_e099_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "artifact_records": records,
        "verdict": result["verdict"],
        "decision": result["decision"],
        "source_stable_e096_verdict": source["verdict"],
        "source_stable_e096_decision": source["decision"],
        "selected_cut_id": selected["cut_id"],
        "committed_difference_count": comparison["committed_difference_count"],
        "truth_boundary": (
            "Independent artifact joins and frozen branch guards. This checker "
            "confirms source-replay divergence; it makes no module-B feasibility claim."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "verdict": payload["verdict"],
                "decision": payload["decision"],
                "selected_cut_id": payload["selected_cut_id"],
                "committed_difference_count": payload[
                    "committed_difference_count"
                ],
                "output_path": str(OUTPUT.relative_to(ROOT)),
                "output_sha256": sha256(OUTPUT),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
