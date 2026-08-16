#!/usr/bin/env python3
"""Aggregate the frozen three-arm W0 unary-lowering canary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping

from w0_canary_receipt_contract import (
    ReceiptContractError,
    dump_receipt,
    make_receipt,
    sha256_file,
    validate_receipt,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MANIFEST_PATH = HERE / "03_CANARY_MANIFEST.json"
ARMS = ("A_BASELINE", "B_OBSERVER_NOOP", "C_UNARY_LOWERING")


class AggregateError(RuntimeError):
    """The arm evidence cannot support a frozen canary verdict."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AggregateError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AggregateError(f"cannot read JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"top-level JSON must be an object: {path}")
    return value


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], str, int]:
    records: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            for index, line in enumerate(handle, start=1):
                require(line.endswith(b"\n"), f"truncated JSONL line {index}: {path}")
                digest.update(line)
                size += len(line)
                try:
                    value = json.loads(line)
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise AggregateError(f"invalid JSONL line {index}: {path}: {exc}") from exc
                require(isinstance(value, dict), f"JSONL line {index} is not an object: {path}")
                records.append(value)
    except OSError as exc:
        raise AggregateError(f"cannot read JSONL {path}: {exc}") from exc
    return records, digest.hexdigest(), size


def load_arm(run_dir: Path, arm: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    arm_dir = run_dir / arm
    receipt = read_json(arm_dir / "arm_receipt.json")
    validate_receipt(receipt)
    require(receipt["result_kind"] == "canary_arm_run", f"wrong arm receipt kind: {arm}")
    require(receipt["subject_identity"]["arm"] == arm, f"arm identity mismatch: {arm}")
    journal = receipt["event_journal"]
    if bool(journal["exists"]):
        records, actual_sha, actual_size = read_jsonl(Path(str(journal["path"])))
        require(actual_sha == journal["sha256"], f"event journal SHA drift: {arm}")
        require(actual_size == int(journal["size_bytes"]), f"event journal size drift: {arm}")
    else:
        records = []
        require(journal["sha256"] is None and int(journal["size_bytes"]) == 0, f"absent journal metadata drift: {arm}")
    return receipt, records


def event_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_index": int(record["event_index"]),
        "selection_digest": str(record["selection_digest"]),
        "precheck_status": str(record["precheck_status"]),
        "precheck_replay_identical": bool(record["precheck_replay_identical"]),
        "target_instance_id": str(record["target_instance_id"]),
        "target_front_cell": list(record["target_front_cell"]),
        "target_commodity": str(record["target_commodity"]),
        "point_nogood_literal_count": int(record["point_nogood_literal_count"]),
        "routing_solve_reached": bool(record["routing_solve_reached"]),
    }


def wall(receipt: Mapping[str, Any]) -> float:
    return float(receipt["resource_vector"]["wall_seconds"])


def classify_endpoint_resource(
    *,
    baseline_wall: float,
    observer_wall: float,
    treatment_wall: float,
    observer_limit: float,
    treatment_limit: float,
    treatment_stronger_terminal: bool,
) -> tuple[str, dict[str, Any]]:
    observer_ratio = observer_wall / baseline_wall if baseline_wall > 0 else float("inf")
    treatment_ratio = treatment_wall / observer_wall if observer_wall > 0 else float("inf")
    observer_ok = observer_ratio <= observer_limit
    treatment_ok = treatment_ratio <= treatment_limit or treatment_stronger_terminal
    if observer_ok and treatment_ok and treatment_wall < observer_wall:
        classification = "ENDPOINT_NEUTRAL_COMPUTE_GAIN"
    elif observer_ok and treatment_ok:
        classification = "ENDPOINT_NEUTRAL_INFRASTRUCTURE"
    else:
        classification = "LOCAL_GAIN_COST_REGRESSION"
    return classification, {
        "baseline_wall_seconds": baseline_wall,
        "observer_wall_seconds": observer_wall,
        "treatment_wall_seconds": treatment_wall,
        "observer_over_baseline_ratio": observer_ratio,
        "treatment_over_observer_ratio": treatment_ratio,
        "observer_limit": observer_limit,
        "treatment_limit": treatment_limit,
        "observer_within_limit": observer_ok,
        "treatment_within_limit_or_stronger_terminal": treatment_ok,
        "treatment_stronger_terminal": treatment_stronger_terminal,
    }


def aggregate(run_dir: Path, run_id: str) -> dict[str, Any]:
    manifest = read_json(MANIFEST_PATH)
    arm_data = {arm: load_arm(run_dir, arm) for arm in ARMS}
    a, a_events = arm_data["A_BASELINE"]
    b, b_events = arm_data["B_OBSERVER_NOOP"]
    c, c_events = arm_data["C_UNARY_LOWERING"]
    event_cap = int(manifest["run_parameters"]["baseline_target_complete_events"])
    c_effective_outcome = (
        "CENSORED"
        if c["terminal_status"] == "UNKNOWN" and c["censor_status"] == "CENSORED"
        else str(c["outcome"])
    )

    hard_failures: list[str] = []
    if a["outcome"] != "ARM_TRACE_COMPLETE":
        hard_failures.append(f"A outcome={a['outcome']}")
    if b["outcome"] != "ARM_TRACE_COMPLETE":
        hard_failures.append(f"B outcome={b['outcome']}")
    if c_effective_outcome not in {
        "ARM_TERMINAL_INFEASIBLE",
        "CENSORED",
        "NO_EFFECT",
    }:
        hard_failures.append(
            f"C effective_outcome={c_effective_outcome}; raw_outcome={c['outcome']}"
        )

    if len(a_events) != event_cap:
        hard_failures.append(f"A event_count={len(a_events)}")
    if len(b_events) != event_cap:
        hard_failures.append(f"B event_count={len(b_events)}")
    if c_events:
        hard_failures.append(f"C event_count={len(c_events)}")

    a_projection = [event_projection(value) for value in a_events]
    b_projection = [event_projection(value) for value in b_events]
    semantic_sequence_equal = a_projection == b_projection
    if not semantic_sequence_equal:
        hard_failures.append("A/B semantic event sequence mismatch")

    for arm, receipt, events in (
        ("A", a, a_events),
        ("B", b, b_events),
    ):
        counters = receipt["counters"]
        if int(counters["binding_proposals"]) != event_cap:
            hard_failures.append(f"{arm} binding_proposals drift")
        if int(counters["j_trigger_true"]) != event_cap:
            hard_failures.append(f"{arm} j_trigger_true drift")
        if int(counters["point_nogoods"]) != event_cap:
            hard_failures.append(f"{arm} point_nogood count drift")
        if int(counters["routing_solves"]) != 0:
            hard_failures.append(f"{arm} unexpectedly reached routing solve")
        if any(bool(event["routing_solve_reached"]) for event in events):
            hard_failures.append(f"{arm} journal says routing solve reached")

    c_counters = c["counters"]
    if int(c_counters["binding_proposals"]) != 0:
        hard_failures.append("C produced a binding proposal")
    if int(c_counters["routing_prechecks"]) != 0:
        hard_failures.append("C reached routing precheck")
    if int(c_counters["point_nogoods"]) != 0:
        hard_failures.append("C emitted point nogood")
    if c_effective_outcome == "ARM_TERMINAL_INFEASIBLE" and c["terminal_status"] != "INFEASIBLE":
        hard_failures.append(f"C terminal_status={c['terminal_status']}")
    if c_effective_outcome == "CENSORED" and not (
        c["terminal_status"] == "UNKNOWN" and c["censor_status"] == "CENSORED"
    ):
        hard_failures.append(
            "C censored outcome lacks UNKNOWN/CENSORED terminal identity"
        )

    for arm, receipt in (("A", a), ("B", b), ("C", c)):
        transaction = receipt["endpoint_transaction"]
        if transaction.get("source_identity_unchanged") is not True:
            hard_failures.append(f"{arm} endpoint identity changed")
        if receipt["output_surfaces_before"] != receipt["output_surfaces_after"]:
            hard_failures.append(f"{arm} public output surface changed")

    if c_effective_outcome == "CENSORED":
        endpoint_class = "NOT_COMPARABLE_CENSORED"
        baseline_wall = wall(a)
        observer_wall = wall(b)
        treatment_wall = wall(c)
        cost_account = {
            "baseline_wall_seconds": baseline_wall,
            "observer_wall_seconds": observer_wall,
            "treatment_wall_seconds": treatment_wall,
            "observer_over_baseline_ratio": (
                observer_wall / baseline_wall if baseline_wall > 0 else None
            ),
            "treatment_over_observer_ratio": (
                treatment_wall / observer_wall if observer_wall > 0 else None
            ),
            "comparison_status": "NOT_COMPARABLE_CENSORED",
            "reason": (
                "C reached no binding proposal but did not prove INFEASIBLE within "
                "the frozen 20-second solve budget; raw costs are reported without "
                "a compute-gain verdict."
            ),
        }
    else:
        endpoint_class, cost_account = classify_endpoint_resource(
            baseline_wall=wall(a),
            observer_wall=wall(b),
            treatment_wall=wall(c),
            observer_limit=float(
                manifest["pre_registered_predictions"][
                    "observation_noop_wall_overhead_max_ratio"
                ]
            ),
            treatment_limit=float(
                manifest["pre_registered_predictions"][
                    "treatment_common_milestone_wall_regression_max_ratio"
                ]
            ),
            treatment_stronger_terminal=c["terminal_status"] == "INFEASIBLE",
        )

    if any(receipt["outcome"] in {"PROTOCOL_VIOLATION", "FAIL_SOUNDNESS"} for receipt in (a, b, c)):
        final_outcome = "PROTOCOL_VIOLATION"
    elif hard_failures:
        final_outcome = "PROTOCOL_VIOLATION"
    elif (
        a["outcome"] == "CENSORED"
        or b["outcome"] == "CENSORED"
        or c_effective_outcome == "CENSORED"
    ):
        final_outcome = "INCONCLUSIVE"
    elif c_effective_outcome == "NO_EFFECT":
        final_outcome = "NO_LOCAL_EFFECT"
    elif endpoint_class == "LOCAL_GAIN_COST_REGRESSION":
        final_outcome = "LOCAL_EFFECT_WITH_COST_REGRESSION"
    else:
        final_outcome = "CANARY_PASS_LOCAL_CONSUMPTION"

    granted = {
        "CANARY_PASS_LOCAL_CONSUMPTION": [
            "permits_owner_review_of_one_next_narrow_proved_theorem_canary",
            "records_W0_unary_lowering_as_verified_research_capability",
        ],
        "LOCAL_EFFECT_WITH_COST_REGRESSION": [
            "records_W0_unary_lowering_as_locally_effective_research_artifact",
            "blocks_expansion_until_cost_migration_is_resolved",
        ],
        "NO_LOCAL_EFFECT": ["blocks_claim_that_W0_theorem_was_consumed_effectively"],
        "INCONCLUSIVE": [
            "records_local_structural_effect_without_terminal_promotion",
            "preserves_existing_research_authorization_without_promotion",
        ],
        "PROTOCOL_VIOLATION": ["blocks_all_canary_promotion"],
    }[final_outcome]

    receipt = make_receipt(
        result_kind="canary_aggregate",
        outcome=final_outcome,
        subject_identity={
            "run_id": run_id,
            "layout_id": "W0-ALIGNMENT",
            "judgment_id": "J-W0-GHOST-FRONT-BOUNDARY-041-V1",
            "arm_receipt_sha256": {
                arm: sha256_file(run_dir / arm / "arm_receipt.json") for arm in ARMS
            },
        },
        verified_scope={
            "arm_count": 3,
            "baseline_event_count": len(a_events),
            "observer_event_count": len(b_events),
            "treatment_event_count": len(c_events),
            "A_B_semantic_sequence_equal": semantic_sequence_equal,
            "treatment_terminal_status": c["terminal_status"],
            "treatment_censor_status": c["censor_status"],
            "treatment_raw_outcome": c["outcome"],
            "treatment_effective_outcome": c_effective_outcome,
            "local_structural_effect_observed": (
                len(b_events) == event_cap
                and len(c_events) == 0
                and int(c_counters["binding_proposals"]) == 0
                and int(c_counters["routing_prechecks"]) == 0
            ),
            "endpoint_sources_unchanged": not any(
                "endpoint identity changed" in value for value in hard_failures
            ),
        },
        granted_effects=granted,
        details={
            "schema_version": "zmd_w0_unary_canary_aggregate_receipt_v1",
            "status": "PASS" if final_outcome == "CANARY_PASS_LOCAL_CONSUMPTION" else "NON_PASS",
            "endpoint_resource_classification": endpoint_class,
            "cost_account": cost_account,
            "hard_failures": hard_failures,
            "local_effect": {
                "baseline_target_events": len(a_events),
                "observer_target_events": len(b_events),
                "treatment_target_events": len(c_events),
                "point_nogoods_avoided_vs_observer": int(b["counters"]["point_nogoods"])
                - int(c["counters"]["point_nogoods"]),
                "point_nogood_literals_avoided_vs_observer": int(
                    b["counters"]["point_nogood_literals"]
                )
                - int(c["counters"]["point_nogood_literals"]),
                "selection_sequence_sha256_A": a["selection_sequence"]["sha256"],
                "selection_sequence_sha256_B": b["selection_sequence"]["sha256"],
                "S2_target_domain_cardinality_before": int(
                    b["model_snapshot_S2"]["generic_output_envelope"][
                        "target_effective_domain_cardinality"
                    ]
                ),
                "S2_target_domain_cardinality_after": int(
                    c["model_snapshot_S2"]["generic_output_envelope"][
                        "target_effective_domain_cardinality"
                    ]
                ),
                "S2_target_active_values_before": int(
                    b["model_snapshot_S2"]["generic_output_envelope"][
                        "target_effective_active_value_count"
                    ]
                ),
                "S2_target_active_values_after": int(
                    c["model_snapshot_S2"]["generic_output_envelope"][
                        "target_effective_active_value_count"
                    ]
                ),
                "terminal_effect_status": (
                    "CENSORED"
                    if c_effective_outcome == "CENSORED"
                    else c["terminal_status"]
                ),
            },
            "endpoint_transaction": c["endpoint_transaction"],
            "arm_outcomes": {
                **{arm: arm_data[arm][0]["outcome"] for arm in ARMS},
                "C_UNARY_LOWERING_EFFECTIVE": c_effective_outcome,
            },
            "arm_terminal_statuses": {
                arm: arm_data[arm][0]["terminal_status"] for arm in ARMS
            },
            "arm_resource_vectors": {
                arm: arm_data[arm][0]["resource_vector"] for arm in ARMS
            },
            "run_dir": str(run_dir),
            "aggregated_at_unix": time.time(),
        },
        contract_extra={
            "aggregator_path": str(Path(__file__).resolve().relative_to(ROOT)),
            "aggregator_sha256": sha256_file(Path(__file__).resolve()),
        },
    )
    return receipt


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        receipt = aggregate(args.run_dir.resolve(), args.run_id)
        text = dump_receipt(receipt, args.output)
        print(text, end="")
        return 0 if receipt["outcome"] == "CANARY_PASS_LOCAL_CONSUMPTION" else 2
    except (
        AggregateError,
        ReceiptContractError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        IndexError,
    ) as exc:
        receipt = make_receipt(
            result_kind="canary_aggregate",
            outcome="PROTOCOL_VIOLATION",
            subject_identity={"run_id": args.run_id, "layout_id": "W0-ALIGNMENT"},
            verified_scope={"completed": False, "failure_stage": "aggregate"},
            granted_effects=["blocks_all_canary_promotion"],
            details={
                "schema_version": "zmd_w0_unary_canary_aggregate_receipt_v1",
                "status": "FAIL",
                "error": str(exc),
            },
        )
        text = dump_receipt(receipt, args.output)
        print(text, end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
