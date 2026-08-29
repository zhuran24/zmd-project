#!/usr/bin/env python3
"""Independent no-solver artifact replay for E088."""

from __future__ import annotations

from collections import Counter
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
RUN1 = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E088_module_b_front_rule_signature_atlas/run-001"
)
RUN2 = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E088_module_b_front_rule_signature_atlas/run-002"
)
FAILURE = RUN1 / "FAILURE.json"
RESULT = RUN2 / "RESULT.json"
ATLAS = RUN2 / "SIGNATURE_ATLAS.json"
CANDIDATES = RUN2 / "CANDIDATE_SIGNATURES.json"
OUTPUT = RUN2 / "ARTIFACT_CHECK.json"

EXPECTED = {
    RESULT: "ba1ecfa3772f7b0a7837818f4945a303e12ab15b61853aaf5fb773cc142bd2c8",
    ATLAS: "06cebb6ef75aa3584f9779b768698b2bf89041b7f0f18c1a81c198f734df15c6",
    CANDIDATES: "3037fe5f2539fc4b155cde387481d60681cd34a0302656e58a73870bfff64798",
}
EXPECTED_CANDIDATES = 4353
EXPECTED_REGISTERED = 178
EXPECTED_STENCIL_SIGNATURES = 146
EXPECTED_SUPPORT_SIGNATURES = 3709
EXPECTED_REGISTERED_STENCIL_SIGNATURES = 33
EXPECTED_REGISTERED_SUPPORT_SIGNATURES = 164
EXPECTED_DOMAIN_COUNTS = {
    "manufacturing_3x3": 1335,
    "manufacturing_5x5": 1008,
    "manufacturing_6x4": 2010,
}
THRESHOLDS = (0.5, 0.8, 0.9, 0.95)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, payload: Any) -> None:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def concentration(
    rows: Sequence[Mapping[str, Any]],
    threshold: float,
) -> dict[str, Any]:
    target = int(math.ceil(EXPECTED_REGISTERED * threshold))
    covered = 0
    universe = 0
    selected: list[str] = []
    for row in rows:
        registered = int(row["registered_count"])
        if registered <= 0:
            continue
        covered += registered
        universe += int(row["universe_count"])
        selected.append(str(row["signature_id"]))
        if covered >= target:
            break
    return {
        "threshold": threshold,
        "target_registered_count": target,
        "covered_registered_count": covered,
        "signature_count": len(selected),
        "bulk_candidate_count": universe,
        "signature_ids": selected,
    }


def recompute_summaries(
    candidates: Sequence[Mapping[str, Any]],
    signature_field: str,
) -> list[dict[str, Any]]:
    universe: Counter[str] = Counter()
    registered: Counter[str] = Counter()
    current: Counter[str] = Counter()
    for row in candidates:
        signature = str(row[signature_field])
        universe[signature] += 1
        if bool(row["registered"]):
            registered[signature] += 1
        if bool(row["is_current_footprint"]):
            current[signature] += 1
    rows = [
        {
            "signature_id": signature,
            "universe_count": int(universe[signature]),
            "registered_count": int(registered[signature]),
            "unregistered_count": int(
                universe[signature] - registered[signature]
            ),
            "current_footprint_count": int(current[signature]),
            "registered_fraction": (
                float(registered[signature] / universe[signature])
                if universe[signature]
                else 0.0
            ),
        }
        for signature in sorted(universe)
    ]
    rows.sort(
        key=lambda row: (
            -int(row["registered_count"]),
            int(row["universe_count"]),
            str(row["signature_id"]),
        )
    )
    return rows


def summary_projection(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    keys = (
        "signature_id",
        "universe_count",
        "registered_count",
        "unregistered_count",
        "current_footprint_count",
        "registered_fraction",
    )
    return [{key: row[key] for key in keys} for row in rows]


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E088 artifact: {path}")
        require(
            sha256_file(path) == expected,
            f"E088 artifact identity drift: {path}",
        )

    failure = load_json(FAILURE)
    result = load_json(RESULT)
    atlas = load_json(ATLAS)
    candidate_payload = load_json(CANDIDATES)
    candidates = list(candidate_payload["candidates"])

    require(
        failure.get("status") == "EXECUTION_FAILURE"
        and "B domain drift" in str(failure.get("detail", "")),
        "E088 run-001 apparatus failure drift",
    )
    require(
        result["verdict"]
        == "REGISTERED_B_FAILURES_ARE_TOO_DIFFUSE_FOR_BOUNDED_BULK_COMPILATION",
        "E088 verdict drift",
    )
    require(
        result["decision"]
        == "RULE_FAILURES_DIFFUSE_REVISE_MODULE_B_GEOMETRY_OR_DECOMPOSE",
        "E088 decision drift",
    )
    require(result["selected_bulk_family"] is None, "unexpected bulk family")
    require(bool(result["all_registered_rows_exactly_remapped"]), "remap not exact")

    require(len(candidates) == EXPECTED_CANDIDATES, "candidate count drift")
    require(
        int(candidate_payload["candidate_count"]) == len(candidates),
        "candidate envelope count drift",
    )
    indices = [int(row["candidate_index"]) for row in candidates]
    require(len(indices) == len(set(indices)), "duplicate candidate index")
    body_digests = [str(row["body_digest"]) for row in candidates]
    require(len(body_digests) == len(set(body_digests)), "duplicate body digest")

    registered_count = sum(bool(row["registered"]) for row in candidates)
    stable_override_count = sum(bool(row["stable_override"]) for row in candidates)
    domain_counts = dict(
        sorted(Counter(str(row["template"]) for row in candidates).items())
    )
    require(registered_count == EXPECTED_REGISTERED, "registered count drift")
    require(stable_override_count == 2, "stable override count drift")
    require(domain_counts == EXPECTED_DOMAIN_COUNTS, "domain counts drift")

    stencil_rows = recompute_summaries(candidates, "stencil_signature")
    support_rows = recompute_summaries(candidates, "support_signature")
    require(
        len(stencil_rows) == EXPECTED_STENCIL_SIGNATURES,
        "stencil signature count drift",
    )
    require(
        len(support_rows) == EXPECTED_SUPPORT_SIGNATURES,
        "support signature count drift",
    )
    require(
        sum(int(row["registered_count"] > 0) for row in stencil_rows)
        == EXPECTED_REGISTERED_STENCIL_SIGNATURES,
        "registered stencil signature count drift",
    )
    require(
        sum(int(row["registered_count"] > 0) for row in support_rows)
        == EXPECTED_REGISTERED_SUPPORT_SIGNATURES,
        "registered support signature count drift",
    )

    atlas_stencil = summary_projection(atlas["stencil_signatures"])
    atlas_support = summary_projection(atlas["support_signatures"])
    require(
        summary_projection(stencil_rows) == atlas_stencil,
        "stencil atlas aggregation drift",
    )
    require(
        summary_projection(support_rows) == atlas_support,
        "support atlas aggregation drift",
    )

    stencil_concentration = {
        str(threshold): concentration(stencil_rows, threshold)
        for threshold in THRESHOLDS
    }
    support_concentration = {
        str(threshold): concentration(support_rows, threshold)
        for threshold in THRESHOLDS
    }
    require(
        stencil_concentration == result["stencil_concentration"],
        "stencil concentration drift",
    )
    require(
        support_concentration == result["support_concentration"],
        "support concentration drift",
    )

    support80 = support_concentration["0.8"]
    stencil90 = stencil_concentration["0.9"]
    support_bulk_admitted = (
        int(support80["signature_count"]) <= 8
        and int(support80["bulk_candidate_count"]) <= 2500
    )
    stencil_bulk_admitted = (
        int(stencil90["signature_count"]) <= 4
        and int(stencil90["bulk_candidate_count"]) <= 3500
    )
    require(not support_bulk_admitted, "support bulk criterion unexpectedly passes")
    require(not stencil_bulk_admitted, "stencil bulk criterion unexpectedly passes")

    output = {
        "schema": "zmd_e088_module_b_front_rule_signature_artifact_check_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "artifact_sha256": {
            str(path.relative_to(ROOT)): expected
            for path, expected in EXPECTED.items()
        },
        "run_001_apparatus_failure_preserved": True,
        "candidate_count": len(candidates),
        "domain_counts": domain_counts,
        "registered_b_rule_count": registered_count,
        "registered_b_fraction": registered_count / len(candidates),
        "stable_override_candidate_count": stable_override_count,
        "stencil_signature_count": len(stencil_rows),
        "support_signature_count": len(support_rows),
        "registered_stencil_signature_count": sum(
            int(row["registered_count"] > 0) for row in stencil_rows
        ),
        "registered_support_signature_count": sum(
            int(row["registered_count"] > 0) for row in support_rows
        ),
        "stencil_80": stencil_concentration["0.8"],
        "stencil_90": stencil90,
        "support_80": support80,
        "support_90": support_concentration["0.9"],
        "decision": result["decision"],
        "truth_boundary": (
            "Independent no-solver aggregation replay. It verifies the finite "
            "candidate/signature census and predeclared concentration decision; "
            "it proves no candidate feasible or infeasible and authorizes no "
            "shared signature cut."
        ),
    }
    dump_exclusive(OUTPUT, output)
    print(
        json.dumps(
            {
                "status": output["status"],
                "candidate_count": output["candidate_count"],
                "registered_b_rule_count": output["registered_b_rule_count"],
                "stencil_signature_count": output["stencil_signature_count"],
                "support_signature_count": output["support_signature_count"],
                "decision": output["decision"],
                "output_path": str(OUTPUT.relative_to(ROOT)),
                "output_sha256": sha256_file(OUTPUT),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
