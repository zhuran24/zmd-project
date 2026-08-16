#!/usr/bin/env python3
"""Run the eleven frozen Endpoint Metrics Protocol v1 sensitivity controls."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable, Mapping

from endpoint_metrics import (
    EndpointMetricError,
    capture_identity_snapshot,
    enumerate_rectangles,
    evaluate_endpoint_state,
    marginal_domain_envelope,
    rectangle_score,
    resource_snapshot,
)
from w0_canary_receipt_contract import (
    ReceiptContractError,
    dump_receipt,
    make_receipt,
    validate_receipt,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROTOCOL_PATH = HERE / "02_ENDPOINT_METRICS_PROTOCOL_V1.json"


class SensitivityError(RuntimeError):
    """A frozen synthetic sensor control did not behave as specified."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SensitivityError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SensitivityError(f"cannot read JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"top-level JSON must be an object: {path}")
    return value


def state(
    rectangles: tuple[tuple[int, int, int, int], ...],
    *,
    witnesses: list[tuple[int, int]],
    excluded: list[tuple[int, int, int, int]],
    context_hash: str,
) -> dict[str, Any]:
    return evaluate_endpoint_state(
        rectangles=rectangles,
        witness_scores=witnesses,
        excluded_rectangles=excluded,
        context_hash=context_hash,
        expected_context_hash=context_hash,
    )


def endpoint_core(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in ("L_t", "U_t", "M_t", "G_t", "B_t")}


def run_controls(protocol: Mapping[str, Any]) -> list[dict[str, Any]]:
    context_hash = str(protocol["identity"]["contextHash"])
    fixture = protocol["synthetic_fixture"]
    rectangles = enumerate_rectangles(
        int(fixture["grid_width"]),
        int(fixture["grid_height"]),
        int(fixture["min_side"]),
    )
    initial_witness = tuple(int(value) for value in fixture["initial_witness_score"])
    expected_ids = [str(item["id"]) for item in protocol["sensitivity_tests"]]
    require(len(expected_ids) == 11, "frozen sensitivity matrix must contain 11 tests")

    results: list[dict[str, Any]] = []

    def record(test_id: str, control_class: str, callback: Callable[[], Mapping[str, Any]]) -> None:
        started = time.perf_counter()
        details = dict(callback())
        results.append(
            {
                "id": test_id,
                "control_class": control_class,
                "status": "PASS",
                "details": details,
                "wall_seconds": time.perf_counter() - started,
            }
        )

    def sens_01() -> Mapping[str, Any]:
        before = state(rectangles, witnesses=[initial_witness], excluded=[], context_hash=context_hash)
        after = state(rectangles, witnesses=[(8, 2)], excluded=[], context_hash=context_hash)
        require(after["L_t"]["value"] == [8, 2], "higher-area witness did not move L")
        require(int(after["M_t"]["value"]) < int(before["M_t"]["value"]), "M did not decrease")
        return {"before": endpoint_core(before), "after": endpoint_core(after)}

    def sens_02() -> Mapping[str, Any]:
        # The frozen mutation uses an abstract score pair. It tests the comparator,
        # not geometric realizability. A realizable secondary control is included.
        require((8, 4) > (8, 2), "second lex key did not order abstract scores")
        require((12, 3) > (12, 2), "second lex key failed realizable score control")
        before = state(rectangles, witnesses=[(8, 2)], excluded=[], context_hash=context_hash)
        after = state(rectangles, witnesses=[(8, 4)], excluded=[], context_hash=context_hash)
        require(after["L_t"]["value"] == [8, 4], "same-area higher-min-side witness did not move L")
        return {
            "before_L": before["L_t"],
            "after_L": after["L_t"],
            "interpretation": "abstract comparator control plus realizable (12,2)->(12,3) secondary control",
        }

    def prepared_top_band() -> tuple[list[tuple[int, int, int, int]], tuple[int, int], list[tuple[int, int, int, int]]]:
        counts = Counter(rectangle_score(rectangle) for rectangle in rectangles)
        target_score = next(score for score in sorted(counts, reverse=True) if counts[score] > 1)
        higher = [rectangle for rectangle in rectangles if rectangle_score(rectangle) > target_score]
        target = [rectangle for rectangle in rectangles if rectangle_score(rectangle) == target_score]
        return higher, target_score, target

    def sens_03() -> Mapping[str, Any]:
        higher, target_score, target = prepared_top_band()
        before = state(rectangles, witnesses=[initial_witness], excluded=higher, context_hash=context_hash)
        after = state(rectangles, witnesses=[initial_witness], excluded=[*higher, target[0]], context_hash=context_hash)
        require(before["U_t"]["value"] == list(target_score), "prepared band is not highest")
        require(after["U_t"] == before["U_t"], "U moved before the band was closed")
        require(int(after["B_t"]["value"]) == int(before["B_t"]["value"]) - 1, "B did not decrease by one")
        return {"score": list(target_score), "before_B": before["B_t"], "after_B": after["B_t"]}

    def sens_04() -> Mapping[str, Any]:
        higher, target_score, target = prepared_top_band()
        before = state(rectangles, witnesses=[initial_witness], excluded=higher, context_hash=context_hash)
        after = state(rectangles, witnesses=[initial_witness], excluded=[*higher, *target], context_hash=context_hash)
        require(before["U_t"]["value"] == list(target_score), "prepared band is not highest")
        require(after["U_t"]["value"] != before["U_t"]["value"], "U did not move after closing top band")
        require(int(after["G_t"]["value"]) == int(before["G_t"]["value"]) - 1, "G did not decrease by one")
        return {"closed_score": list(target_score), "before": endpoint_core(before), "after": endpoint_core(after)}

    def sens_05() -> Mapping[str, Any]:
        low = next(rectangle for rectangle in rectangles if rectangle_score(rectangle) <= initial_witness)
        before = state(rectangles, witnesses=[initial_witness], excluded=[], context_hash=context_hash)
        after = state(rectangles, witnesses=[initial_witness], excluded=[low], context_hash=context_hash)
        require(endpoint_core(after) == endpoint_core(before), "low-score exclusion changed endpoint currencies")
        return {"excluded_rectangle": list(low), "score": list(rectangle_score(low))}

    def sens_06() -> Mapping[str, Any]:
        selected = rectangles[0]
        once = state(rectangles, witnesses=[initial_witness], excluded=[selected], context_hash=context_hash)
        twice = state(
            rectangles,
            witnesses=[initial_witness, initial_witness],
            excluded=[selected, selected],
            context_hash=context_hash,
        )
        require(once == twice, "duplicate witness/exclusion was not idempotent")
        return {"state": endpoint_core(once)}

    def sens_07() -> Mapping[str, Any]:
        try:
            evaluate_endpoint_state(
                rectangles=rectangles,
                witness_scores=[initial_witness],
                excluded_rectangles=[],
                context_hash="0" * 64,
                expected_context_hash=context_hash,
            )
        except EndpointMetricError as exc:
            return {"fail_closed": True, "error": str(exc)}
        raise SensitivityError("stale context was accepted")

    def sens_08() -> Mapping[str, Any]:
        value = state(rectangles, witnesses=[], excluded=[], context_hash=context_hash)
        require(value["L_t"]["value"] == "ABSENT", "L did not become ABSENT")
        require(value["M_t"] == {"value": "N_A_NOT_READY", "type": "N_A_NOT_READY"}, "M fabricated a number")
        require(value["G_t"] == {"value": "N_A_NOT_READY", "type": "N_A_NOT_READY"}, "G fabricated a number")
        return {"L_t": value["L_t"], "M_t": value["M_t"], "G_t": value["G_t"]}

    def sens_09() -> Mapping[str, Any]:
        before = resource_snapshot(stage_costs={"binding": 10.0, "routing": 0.0}, total_cost=10.0)
        after = resource_snapshot(stage_costs={"binding": 0.0, "routing": 10.0}, total_cost=10.0)
        require(before["total_cost"] == after["total_cost"], "total cost changed")
        require(before["stages"] != after["stages"], "hotspot migration was invisible")
        return {"before": before, "after": after}

    def sens_10() -> Mapping[str, Any]:
        value = resource_snapshot(stage_costs={"binding": 3.0, "routing": "NOT_REACHED"}, total_cost=3.0)
        require(value["stages"]["routing"]["type"] == "NOT_REACHED", "NOT_REACHED became numeric zero")
        return value

    def sens_11() -> Mapping[str, Any]:
        before = marginal_domain_envelope([4])
        after = marginal_domain_envelope([3])
        require(before["domain_cardinality_sum"] == 4, "baseline domain size drift")
        require(after["domain_cardinality_sum"] == 3, "treatment domain size drift")
        require(after["exact_joint_cardinality_claimed"] is False, "box envelope claimed exact count")
        return {"before": before, "after": after}

    controls: list[tuple[str, str, Callable[[], Mapping[str, Any]]]] = [
        ("SENS-01-HIGHER-AREA-WITNESS", "positive", sens_01),
        ("SENS-02-SAME-AREA-HIGHER-MIN-SIDE", "positive", sens_02),
        ("SENS-03-REMOVE-ONE-FROM-TOP-BAND", "positive", sens_03),
        ("SENS-04-CLOSE-TOP-BAND", "positive", sens_04),
        ("SENS-05-IRRELEVANT-LOW-SCORE-EXCLUSION", "negative", sens_05),
        ("SENS-06-IDEMPOTENT-DUPLICATE", "negative", sens_06),
        ("SENS-07-STALE-CONTEXT", "stale", sens_07),
        ("SENS-08-ABSENT-LOWER-BOUND", "negative", sens_08),
        ("SENS-09-HOTSPOT-MIGRATION", "positive", sens_09),
        ("SENS-10-NOT-REACHED", "negative", sens_10),
        ("SENS-11-UNARY-DOMAIN-REMOVAL", "positive", sens_11),
    ]
    require([test_id for test_id, _kind, _callback in controls] == expected_ids, "implemented sensitivity IDs drift from frozen protocol")
    for test_id, control_class, callback in controls:
        record(test_id, control_class, callback)
    return results


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    started = time.perf_counter()
    try:
        contract_receipt = read_json(args.contract_receipt)
        validate_receipt(contract_receipt)
        require(contract_receipt["result_kind"] == "lowering_contract_check", "wrong prerequisite receipt kind")
        require(contract_receipt["outcome"] == "PASS", "lowering contract prerequisite did not PASS")

        protocol = read_json(PROTOCOL_PATH)
        identity_records = [*protocol["current_endpoint_sources"], *protocol["protected_surfaces"]]
        identity_snapshot = capture_identity_snapshot(ROOT, identity_records)
        controls = run_controls(protocol)
        class_counts = Counter(str(item["control_class"]) for item in controls)
        require(all(item["status"] == "PASS" for item in controls), "a sensitivity control did not PASS")

        receipt = make_receipt(
            result_kind="endpoint_metric_sensitivity_check",
            outcome="PASS",
            subject_identity={
                "protocol_path": str(PROTOCOL_PATH.relative_to(ROOT)),
                "protocol_schema_version": protocol["schema_version"],
                "contextHash": protocol["identity"]["contextHash"],
            },
            verified_scope={
                "sensitivity_control_count": len(controls),
                "positive_control_count": class_counts["positive"],
                "negative_control_count": class_counts["negative"],
                "stale_control_count": class_counts["stale"],
                "endpoint_and_protected_identity_count": len(identity_snapshot),
            },
            granted_effects=[
                "permits_A_BASELINE_B_OBSERVER_NOOP_C_UNARY_LOWERING_execution_when_contract_PASS_is_current",
                "permits_ZERO_MEASURED_or_ZERO_BY_SCOPE_labels_under_protocol_v1",
            ],
            details={
                "schema_version": "zmd_endpoint_metric_sensitivity_receipt_v1",
                "status": "PASS",
                "controls": controls,
                "identity_snapshot": identity_snapshot,
                "prerequisite_contract_receipt": {
                    "path": str(args.contract_receipt),
                    "outcome": contract_receipt["outcome"],
                    "contract_identity": contract_receipt["contract_identity"],
                },
                "wall_seconds": time.perf_counter() - started,
            },
            contract_extra={
                "endpoint_protocol_path": str(PROTOCOL_PATH.relative_to(ROOT)),
            },
        )
        text = dump_receipt(receipt, args.output)
        print(text, end="")
        return 0
    except (
        SensitivityError,
        EndpointMetricError,
        ReceiptContractError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        IndexError,
    ) as exc:
        receipt = make_receipt(
            result_kind="endpoint_metric_sensitivity_check",
            outcome="SENSOR_UNVALIDATED",
            subject_identity={
                "protocol_path": str(PROTOCOL_PATH.relative_to(ROOT)),
                "contextHash": "5e15112638b849e3b04b674be30fd4c0b7c8fd41f73caecfce5f05b44cc1bded",
            },
            verified_scope={"completed": False, "failure_stage": "sensitivity_matrix"},
            granted_effects=["blocks_true_canary_arms"],
            details={
                "schema_version": "zmd_endpoint_metric_sensitivity_receipt_v1",
                "status": "FAIL",
                "error": str(exc),
                "wall_seconds": time.perf_counter() - started,
            },
        )
        text = dump_receipt(receipt, args.output)
        print(text, end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
