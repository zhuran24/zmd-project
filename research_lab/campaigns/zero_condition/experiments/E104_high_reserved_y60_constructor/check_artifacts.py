#!/usr/bin/env python3
"""Independent branch-aware replay for E104 reserved-y60 constructor."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e104.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E104_high_reserved_y60_constructor/run-002"
)
RESULT = RUN / "RESULT.json"
HIGH = RUN / "HIGH_RESULT.json"
AUDIT = RUN / "RESERVED_ROW_AUDIT.json"
LOW = RUN / "LOW_RESULT.json"
MODULE_B = RUN / "MODULE_B_WITNESS.json"
COMBINED = RUN / "COMBINED_WITNESS.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
APPARATUS_FAILURE = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E104_high_reserved_y60_constructor/run-001/FAILURE.json"
)
E101_BODY = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E101_x42_allocation_handshake/run-001/BODY_ONLY_RESULT.json"
)
E103_LIVE = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E103_high_side_interface_capacity_audit/run-003/LIVE_HIGH_CANDIDATES.json"
)

EXPECTED = {
    RUNNER: "1b2eae0a788e0f4be4cf4af857b8f5b4ceb16f17a215eed41c7d68d656a315fd",
    RESULT: "381c6547ed2b94773de4f1fadfe747459aaed307d6c3461f2875a2bdf4817b04",
    HIGH: "f76ce51a60aeaba6ef11e1ca117d0c9e5c9dec716767a2dec93758bc51fb5043",
    AUDIT: "9277248c332d1f132ae21e9121f08fe7009f69f7a432bd19a6e0a9797d62277c",
    APPARATUS_FAILURE: "6be000abb310c078c6422a5fad53f81caf75063247a207bd0a7c4fb1bced7878",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E103_LIVE: "ebf0c34b174df7036cf6c4bf2f3283dd4ea303998f62520cbd0c74d70aebfd08",
}
RESERVED_Y = 60
STABLE_DIGESTS = {
    "da277903615efb73fbc9bb30716cae3b9b96654bed9905addebba0e27accf33d",
    "ef71d17d5e4db7bb4c3baeeee913780c753409802365896a67988bfcb43176be",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cell(value: Sequence[int]) -> tuple[int, int]:
    return int(value[0]), int(value[1])


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def independent_audit() -> dict[str, Any]:
    payload = load(E103_LIVE)
    candidates = list(payload["candidates"])
    require(int(payload["candidate_count"]) == 1205, "E103 live count drift")
    lower: list[Mapping[str, Any]] = []
    upper: list[Mapping[str, Any]] = []
    removed: list[Mapping[str, Any]] = []
    for row in candidates:
        body = [cell(value) for value in row["body"]]
        if any(y == RESERVED_Y for _x, y in body):
            removed.append(row)
        elif max(y for _x, y in body) <= RESERVED_Y - 1:
            lower.append(row)
        elif min(y for _x, y in body) >= RESERVED_Y + 1:
            upper.append(row)
        else:
            raise RuntimeError("E104 independent side classification failed")
    require((len(lower), len(removed), len(upper)) == (812, 195, 198), "side counts drift")

    lower_body = {cell(value) for row in lower for value in row["body"]}
    upper_body = {cell(value) for row in upper for value in row["body"]}
    lower_front = {cell(value) for row in lower for value in row["front_cells"]}
    upper_front = {cell(value) for row in upper for value in row["front_cells"]}
    surviving = [*lower, *upper]
    anchor_counts = Counter(
        "lower" if row in lower else "upper"
        for row in surviving
        if bool(row["is_anchor"])
    )
    stable = {
        str(row["body_digest"])
        for row in surviving
        if str(row["body_digest"]) in STABLE_DIGESTS
    }
    require(stable == STABLE_DIGESTS, "stable E078 body survival drift")
    return {
        "live_high_candidate_count": len(candidates),
        "removed_candidate_count": len(removed),
        "survivor_candidate_count": len(surviving),
        "nested_side_candidate_counts": {"lower": len(lower), "upper": len(upper)},
        "survivor_template_candidate_counts": dict(
            sorted(Counter(str(row["template"]) for row in surviving).items())
        ),
        "removed_template_candidate_counts": dict(
            sorted(Counter(str(row["template"]) for row in removed).items())
        ),
        "surviving_anchor_counts": dict(sorted(anchor_counts.items())),
        "removed_anchor_count": sum(bool(row["is_anchor"]) for row in removed),
        "stable_body_digest_count": len(stable),
        "cross_body_cell_count": len(lower_body & upper_body),
        "lower_front_upper_body_intersection_count": len(lower_front & upper_body),
        "upper_front_lower_body_intersection_count": len(upper_front & lower_body),
        "cross_front_front_intersection_count": len(lower_front & upper_front),
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E104 check: {OUTPUT}")
    records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E104 artifact: {path}")
        observed = sha256(path)
        require(observed == expected, f"E104 artifact identity drift: {path}")
        records[str(path)] = {"sha256": observed, "size_bytes": path.stat().st_size}

    result = load(RESULT)
    high = load(HIGH)
    audit = load(AUDIT)
    apparatus = load(APPARATUS_FAILURE)
    body = load(E101_BODY)
    replay = independent_audit()

    require(apparatus.get("error") == "ModuleNotFoundError", "apparatus failure identity drift")
    require("No module named 'src'" in str(apparatus.get("detail")), "apparatus cause drift")
    require(body.get("status") == "OPTIMAL", "E101 body witness drift")
    require(body.get("side_body_counts") == {"high": 26, "low": 65}, "E101 side count drift")
    require(
        sha256(RUNNER) == result["identity"]["runner_sha256"],
        "runner identity join drift",
    )
    require(sha256(HIGH) == result["high"]["sha256"], "high join drift")
    require(sha256(AUDIT) == result["reserved_row_audit"]["sha256"], "audit join drift")
    require(audit.get("status") == "PASS", "reserved-row audit is not PASS")
    for key in (
        "live_high_candidate_count",
        "removed_candidate_count",
        "survivor_candidate_count",
        "nested_side_candidate_counts",
        "cross_body_cell_count",
        "lower_front_upper_body_intersection_count",
        "upper_front_lower_body_intersection_count",
        "cross_front_front_intersection_count",
    ):
        require(audit[key] == replay[key], f"independent audit drift: {key}")
    require(audit["surviving_hint_count"] == 22, "surviving hint count drift")
    require(audit["removed_hint_count"] == 3, "removed hint count drift")

    require(high.get("status") == "UNKNOWN", "E104 high status drift")
    require(result["high"]["status"] == "UNKNOWN", "wrapper high status drift")
    require(int(high.get("candidate_count", -1)) == 1010, "high candidate count drift")
    require(int(high.get("matched_hint_count", -1)) == 22, "high hint count drift")
    require(int(high.get("selected_body_count", 0) or 0) == 0, "censored high leaks bodies")
    require(high.get("allocation_tuple") is None, "censored high leaks allocation")
    require(high.get("nested_allocations") is None, "censored high leaks nested allocation")
    require(result.get("low") is None, "censored high unexpectedly ran low")
    require(result.get("module_b_witness") is None, "censored high leaks module-B witness")
    require(result.get("combined_witness") is None, "censored high leaks combined witness")
    require(not LOW.exists() and not MODULE_B.exists() and not COMBINED.exists(), "unexpected downstream files")
    require(
        result.get("verdict") == "RESERVED_Y60_HIGH_CONSTRUCTOR_CENSORED",
        "E104 verdict drift",
    )
    require(
        result.get("decision") == "EXTERNALIZE_LOWER_UPPER_CLASS_ALLOCATIONS",
        "E104 decision drift",
    )

    payload = {
        "schema": "zmd_e104_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "CENSORED_HIGH_NO_ALLOCATION",
        "artifact_records": records,
        "independent_reserved_row_replay": replay,
        "high_status": high["status"],
        "high_branches": int(high["branches"]),
        "high_conflicts": int(high["conflicts"]),
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "Independent finite geometry replay and branch join. UNKNOWN remains "
            "censored; no allocation, witness or infeasibility claim is admitted."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "classification": payload["classification"],
                "high_status": payload["high_status"],
                "decision": payload["decision"],
                "output_path": str(OUTPUT.relative_to(ROOT)),
                "output_sha256": sha256(OUTPUT),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
