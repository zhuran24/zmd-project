#!/usr/bin/env python3
"""E083: audit whether E082's historical big-bay carrier rows are admitted."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import re
from typing import Any

ROOT = Path("/home/zhuran24/zmd-research")
RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E083_historical_bay_carrier_premise_audit/run-001"
)
E082_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E082_bay_alignment_partition_frontier/run-001/RESULT.json"
)
E082_SEED = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E082_bay_alignment_partition_frontier/run-001/GEOMETRY_AWARE_SEED.json"
)
RECOVERY_ROOT = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/"
    "recovery_runs/restart-20260720T075344Z-kYNVbm"
)
PLAN = RECOVERY_ROOT / "count_closure_plan_20260720_v3.json"
FINAL35_STATUS = RECOVERY_ROOT / "big_bays/STATUS.final35-targets.md"
BIG_STATUS = RECOVERY_ROOT / "big_bays/STATUS.md"
EXPECTED_HASHES = {
    E082_RESULT: "4c9242b8068ceb1189cfbf2f076ba929568b45ec4ded8c451c33ddd805c1d489",
    E082_SEED: "030493d7e1cb3ea5fe06edef581114d5dc4aadadec323b2f23add90724c0ca9d",
    PLAN: "1c9d42b00221436518f8e3635828bdad6261d0a5b005714f8817eca6194499e5",
    FINAL35_STATUS: "15274231abe247105951ce00e83dac66dbda11e48c58e4cba3aef50376104301",
    BIG_STATUS: "45d549775983230dc5dfb9c4d4a08fa37e7708e32569114a50749442b4c16a8f",
}
TARGET_RE = re.compile(r"`\((\d+),(\d+),(\d+)\)`")
EXPECTED_ROWS = {
    "F": (10, 5, 4),
    "G": (10, 5, 5),
    "H": (11, 6, 4),
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def write_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def target_tuple(value: Any) -> tuple[int, int, int]:
    if not isinstance(value, list) or len(value) != 3:
        raise RuntimeError(f"invalid target row: {value!r}")
    return int(value[0]), int(value[1]), int(value[2])


def parse_negative_targets(text: str) -> set[tuple[int, int, int]]:
    if "returned exact `INFEASIBLE`, never `UNKNOWN`" not in text:
        raise RuntimeError("historical final35 negative-status contract drift")
    targets: set[tuple[int, int, int]] = set()
    for line in text.splitlines():
        if not line.lstrip().startswith("| `("):
            continue
        match = TARGET_RE.search(line.replace(" ", ""))
        if match is None:
            raise RuntimeError(f"cannot parse historical target row: {line}")
        targets.add(tuple(int(match.group(index)) for index in (1, 2, 3)))
    if not targets:
        raise RuntimeError("historical final35 negative table is empty")
    return targets


def main() -> int:
    if RUN_DIR.exists() and any(RUN_DIR.iterdir()):
        raise FileExistsError(RUN_DIR)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    observed_hashes: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        actual = sha256_file(path)
        observed_hashes[str(path)] = actual
        if actual != expected:
            raise RuntimeError(
                f"E083 frozen identity drift: {path}: {actual} != {expected}"
            )

    e082 = json.loads(E082_RESULT.read_text(encoding="utf-8"))
    seed = json.loads(E082_SEED.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    final35_text = FINAL35_STATUS.read_text(encoding="utf-8")
    big_text = BIG_STATUS.read_text(encoding="utf-8")
    if (
        e082.get("verdict") != "BAY_ALIGNMENT_REORDERS_BALANCED_SEAM_FRONTIER"
        or seed.get("geometry_aware_seed") is None
        or plan.get("schema_version") != "connected_bay_count_closure_plan.v3"
        or plan.get("status") != "SEARCH_PLAN_ONLY"
    ):
        raise RuntimeError("E083 E082 or plan identity drift")

    named_rows = {
        str(name): target_tuple(value)
        for name, value in plan["big_bay_target"]["rows"].items()
    }
    if named_rows != EXPECTED_ROWS:
        raise RuntimeError(f"E083 named big-bay row drift: {named_rows}")
    consumed_capacities = {
        target_tuple(row["capacity"])
        for row in seed["geometry_aware_seed"]["bay_alignment"]["allocation"]
        if int(row["bay_id"]) in {0, 1, 2}
    }
    if consumed_capacities != set(EXPECTED_ROWS.values()):
        raise RuntimeError(
            f"E083 E082 seed does not consume F/G/H exactly: {consumed_capacities}"
        )

    negative_targets = parse_negative_targets(final35_text)
    if EXPECTED_ROWS["G"] not in negative_targets:
        raise RuntimeError("E083 historical G-row negative is absent")
    f_positive_markers = (
        "Target `(10,5,4)`",
        "`OPTIMAL`",
        "independent_periodic_big_bay_replay.json",
        "pure-stdlib `PASS`",
    )
    if not all(marker in big_text for marker in f_positive_markers):
        raise RuntimeError("E083 historical F-row positive record drift")

    required_new = {
        str(name): target_tuple(value)
        for name, value in plan["required_new_local_results"].items()
    }
    if required_new != {"G": EXPECTED_ROWS["G"], "H": EXPECTED_ROWS["H"]}:
        raise RuntimeError(f"E083 required-new-row drift: {required_new}")

    rows: list[dict[str, Any]] = []
    for name in ("F", "G", "H"):
        target = EXPECTED_ROWS[name]
        if name == "F":
            status = "ADMITTED_POSITIVE_LOCAL_AND_INDEPENDENT_REPLAY"
            effect = "eligible_historical_local_row"
        elif target in negative_targets:
            status = "EXACT_INFEASIBLE_IN_RECORDED_FINAL35_CONTEXT"
            effect = "blocks_v3_carrier_in_that_context"
        else:
            status = "REQUIRED_BY_PLAN_BUT_NO_ADMITTED_POSITIVE"
            effect = "unadmitted_carrier_premise"
        rows.append(
            {
                "row_name": name,
                "target": list(target),
                "status": status,
                "effect": effect,
            }
        )

    all_positive = all(
        row["status"] == "ADMITTED_POSITIVE_LOCAL_AND_INDEPENDENT_REPLAY"
        for row in rows
    )
    if all_positive:
        verdict = "E082_HISTORICAL_V3_CARRIER_PREMISES_ADMITTED"
        decision = "CONTINUE_HISTORICAL_V3_PHYSICAL_REPLAY"
    else:
        verdict = "E082_HISTORICAL_V3_CARRIER_BLOCKED_BY_NEGATIVE_OR_UNADMITTED_ROWS"
        decision = "KEEP_E082_AS_COUNT_LOWER_BOUND_USE_E081_CURRENT_GEOMETRY_OR_NEW_ADMITTED_BAY_PLAN"

    audit = {
        "schema": "zmd_e083_historical_bay_carrier_premise_audit_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "input_hashes": observed_hashes,
        "e082_partition": seed["geometry_aware_seed"]["partition_id"],
        "consumed_big_bay_rows": rows,
        "historical_negative_targets": [list(value) for value in sorted(negative_targets)],
        "all_consumed_rows_admitted_positive": all_positive,
        "verdict": verdict,
        "decision": decision,
        "truth_boundary": (
            "The G-row negative applies only to the recorded final35 pole phase "
            "and its two connectivity models. It blocks the unchanged historical "
            "v3 carrier but does not prove target (10,5,5) impossible in every "
            "future geometry. H is unadmitted, not proved infeasible here."
        ),
    }
    audit["audit_digest"] = stable_digest(audit)
    audit_path = RUN_DIR / "PREMISE_AUDIT.json"
    write_exclusive(audit_path, audit)
    result = {
        "schema": "zmd_e083_historical_bay_carrier_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "e082_partition": audit["e082_partition"],
        "consumed_big_bay_rows": rows,
        "all_consumed_rows_admitted_positive": all_positive,
        "premise_audit_path": str(audit_path.relative_to(ROOT)),
        "premise_audit_sha256": sha256_file(audit_path),
        "runner": {
            "path": str(Path(__file__).resolve().relative_to(ROOT)),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "truth_boundary": audit["truth_boundary"],
    }
    result["result_digest"] = stable_digest(result)
    result_path = RUN_DIR / "RESULT.json"
    write_exclusive(result_path, result)
    receipt = {
        "schema": "zmd_e083_historical_bay_carrier_receipt_v1",
        "result_path": str(result_path.relative_to(ROOT)),
        "result_sha256": sha256_file(result_path),
        "premise_audit_sha256": sha256_file(audit_path),
        "verdict": verdict,
        "decision": decision,
    }
    write_exclusive(RUN_DIR / "RESULT_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
