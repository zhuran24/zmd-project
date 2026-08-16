#!/usr/bin/env python3
"""Independently recheck the GPT-5.6 Pro W0 canary lineage.

This post-run checker is standard-library-only. It does not import the lowering,
arm runner, aggregator, Phase -1 harness, OR-Tools, or any project model code.
It recomputes the scientific verdict from immutable arm receipts and append-only
journals, while preserving the original suite-orchestration defect as separate
apparatus history.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ARTIFACT_ROOT = ROOT / ".artifacts/solver_reasoning_outer_loop_w0_unary_canary_20260816"
APPARATUS_RUN_ID = "w0-unary-canary-20260816T170830Z-edf13896a8"
SCIENTIFIC_RUN_ID = "w0-unary-canary-20260816T171013Z-d3ad19d479"
AGGREGATE_NAME = "CANARY_AGGREGATE_GPT56PRO.json"
EXPECTED_SEQUENCE_SHA256 = "9cc4637b444bc66ac2def1151441bc703802f1433c99db456c2fa81225e94f64"
CANARY_MANIFEST_RELATIVE_PATH = (
    "docs/research/solver_reasoning_outer_loop_reviews_20260815/"
    "experiment_two_w0_unary_lowering_canary_20260816/03_CANARY_MANIFEST.json"
)
RECEIPT_SCHEMA_RELATIVE_PATH = (
    "docs/research/solver_reasoning_outer_loop_reviews_20260815/"
    "experiment_two_w0_unary_lowering_canary_20260816/03B_RECEIPT_ENVELOPE_SCHEMA_V1.json"
)
LINEAGE_MANIFEST_RELATIVE_PATH = (
    ".artifacts/solver_reasoning_outer_loop_w0_unary_canary_20260816/"
    "EVIDENCE_MANIFEST_GPT56PRO_LINEAGE.json"
)
COMMIT_CHAIN = (
    "57a17a7672cf879fc39e0e67a044590a85cb47a2",
    "988d1b787778c211f5e8b930b7f6cf093581aed8",
    "edf13896a867ae14be8d5add3f08a41c0f4c5322",
    "d3ad19d479eb5ea696ccda374fee655b81f6cfab",
    "fe60db52b65eaa5c3664ad758a06b4427447b4a6",
    "4ce4e7ea7f8e44ab6a0f451d33ba61b4daf948bf",
)


class CheckError(RuntimeError):
    """The local evidence does not support the recorded verdict."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CheckError(f"cannot read JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"top-level JSON must be an object: {path}")
    return value


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise CheckError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest(), size


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
                    raise CheckError(f"invalid JSONL line {index} in {path}: {exc}") from exc
                require(isinstance(value, dict), f"JSONL line {index} is not an object: {path}")
                records.append(value)
    except OSError as exc:
        raise CheckError(f"cannot read JSONL {path}: {exc}") from exc
    return records, digest.hexdigest(), size


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CheckError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def verify_commit_chain() -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for commit in COMMIT_CHAIN:
        git("cat-file", "-e", f"{commit}^{{commit}}")
        values.append(
            {
                "commit": commit,
                "subject": git("show", "-s", "--format=%s", commit),
            }
        )
    return values


def schema_location(path: Sequence[str | int]) -> str:
    return "/".join(str(part) for part in path) or "<root>"


def schema_type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, Mapping)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    raise CheckError(f"unsupported receipt-schema type: {expected_type}")


def validate_schema_value(
    value: Any,
    schema: Mapping[str, Any],
    *,
    path: tuple[str | int, ...] = (),
) -> None:
    location = schema_location(path)

    if "const" in schema:
        require(value == schema["const"], f"receipt schema const mismatch at {location}")

    expected_type = schema.get("type")
    if expected_type is not None:
        require(isinstance(expected_type, str), f"invalid receipt-schema type at {location}")
        require(
            schema_type_matches(value, expected_type),
            f"receipt schema type mismatch at {location}: expected {expected_type}",
        )

    if isinstance(value, Mapping):
        min_properties = schema.get("minProperties")
        if min_properties is not None:
            require(len(value) >= int(min_properties), f"too few properties at {location}")

        required = schema.get("required", [])
        require(isinstance(required, list), f"invalid required list in schema at {location}")
        missing = [field for field in required if field not in value]
        require(not missing, f"receipt schema missing fields at {location}: {missing}")

        properties = schema.get("properties", {})
        require(isinstance(properties, Mapping), f"invalid properties map in schema at {location}")
        for field, child_schema in properties.items():
            if field not in value:
                continue
            require(isinstance(child_schema, Mapping), f"invalid child schema at {location}/{field}")
            validate_schema_value(value[field], child_schema, path=(*path, str(field)))

        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            require(not extras, f"unexpected receipt fields at {location}: {extras}")

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if min_items is not None:
            require(len(value) >= int(min_items), f"too few items at {location}")
        if schema.get("uniqueItems") is True:
            for index, item in enumerate(value):
                require(item not in value[:index], f"duplicate array item at {location}/{index}")
        item_schema = schema.get("items")
        if item_schema is not None:
            require(isinstance(item_schema, Mapping), f"invalid item schema at {location}")
            for index, item in enumerate(value):
                validate_schema_value(item, item_schema, path=(*path, index))

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if min_length is not None:
            require(len(value) >= int(min_length), f"string too short at {location}")
        pattern = schema.get("pattern")
        if pattern is not None:
            require(isinstance(pattern, str), f"invalid regex pattern in schema at {location}")
            require(re.search(pattern, value) is not None, f"string pattern mismatch at {location}")


def verify_envelope(receipt: Mapping[str, Any], *, expected_kind: str) -> None:
    schema = read_json(ROOT / RECEIPT_SCHEMA_RELATIVE_PATH)
    validate_schema_value(receipt, schema)
    require(receipt["result_kind"] == expected_kind, f"wrong receipt kind: {receipt.get('result_kind')}")


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


def sequence_sha256(records: Sequence[Mapping[str, Any]]) -> str:
    material = "".join(f"{record['selection_digest']}\n" for record in records)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def verify_baseline_arm(
    run_dir: Path,
    arm: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    receipt_path = run_dir / arm / "arm_receipt.json"
    receipt = read_json(receipt_path)
    verify_envelope(receipt, expected_kind="canary_arm_run")
    require(receipt["outcome"] == "ARM_TRACE_COMPLETE", f"{arm} did not complete trace")
    require(receipt["terminal_status"] == "EVENT_CAP_REACHED", f"{arm} terminal drift")
    require(receipt["censor_status"] == "UNCENSORED", f"{arm} censor drift")

    journal_path = Path(str(receipt["event_journal"]["path"]))
    records, actual_sha, actual_size = read_jsonl(journal_path)
    require(actual_sha == receipt["event_journal"]["sha256"], f"{arm} journal SHA drift")
    require(actual_size == int(receipt["event_journal"]["size_bytes"]), f"{arm} journal size drift")
    require(len(records) == 1007, f"{arm} event count={len(records)}")
    require([int(value["event_index"]) for value in records] == list(range(1, 1008)), f"{arm} indices drift")
    digests = [str(value["selection_digest"]) for value in records]
    require(len(set(digests)) == 1007, f"{arm} duplicate selection digest")
    require(sequence_sha256(records) == EXPECTED_SEQUENCE_SHA256, f"{arm} sequence SHA drift")

    for value in records:
        require(value["record_type"] == "binding_precheck_reject", f"{arm} record type drift")
        require(value["precheck_status"] == "front_blocked", f"{arm} precheck family drift")
        require(value["precheck_replay_identical"] is True, f"{arm} replay mismatch")
        require(value["target_instance_id"] == "boundary_port_041", f"{arm} target instance drift")
        require(value["target_front_cell"] == [1, 53], f"{arm} target front drift")
        require(value["target_commodity"] == "source_ore", f"{arm} target commodity drift")
        require(int(value["point_nogood_literal_count"]) == 285, f"{arm} literal count drift")
        require(value["routing_solve_reached"] is False, f"{arm} reached routing solve")

    counters = receipt["counters"]
    expected_counts = {
        "binding_proposals": 1007,
        "binding_solve_calls": 1007,
        "j_trigger_true": 1007,
        "point_nogoods": 1007,
        "point_nogood_literals": 286995,
        "routing_prechecks": 1007,
        "routing_builds": 0,
        "routing_solves": 0,
    }
    for field, expected in expected_counts.items():
        require(int(counters[field]) == expected, f"{arm} {field}={counters[field]}")
    require(receipt["endpoint_transaction"]["source_identity_unchanged"] is True, f"{arm} endpoint identity changed")
    require(receipt["output_surfaces_before"] == receipt["output_surfaces_after"], f"{arm} output surface changed")

    summary = {
        "receipt_sha256": sha256_file(receipt_path)[0],
        "journal_sha256": actual_sha,
        "event_count": len(records),
        "sequence_sha256": sequence_sha256(records),
        "wall_seconds": float(receipt["resource_vector"]["wall_seconds"]),
        "cpu_seconds": float(receipt["resource_vector"]["cpu_seconds"]),
        "peak_rss_bytes": int(receipt["resource_vector"]["peak_rss_bytes"]),
        "binding_solve_seconds": float(receipt["timings"]["binding_solve_seconds"]),
        "trigger_evaluator_seconds": float(receipt["timings"]["trigger_evaluator_seconds"]),
    }
    return receipt, records, summary


def verify_treatment_arm(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt_path = run_dir / "C_UNARY_LOWERING/arm_receipt.json"
    receipt = read_json(receipt_path)
    verify_envelope(receipt, expected_kind="canary_arm_run")
    require(receipt["terminal_status"] == "UNKNOWN", "C terminal is not UNKNOWN")
    require(receipt["censor_status"] == "CENSORED", "C censor status drift")
    require(receipt["final_reason"] == "binding_timeout", "C final reason drift")
    counters = receipt["counters"]
    require(int(counters["binding_solve_calls"]) == 1, "C solve-call count drift")
    for field in (
        "binding_proposals",
        "routing_prechecks",
        "routing_builds",
        "routing_solves",
        "point_nogoods",
        "point_nogood_literals",
    ):
        require(int(counters[field]) == 0, f"C {field} is nonzero")

    envelope = receipt["model_snapshot_S2"]["generic_output_envelope"]
    require(int(envelope["target_effective_domain_cardinality"]) == 1, "C target domain did not shrink to one")
    require(int(envelope["target_effective_active_value_count"]) == 0, "C active target values survived")
    require(int(envelope["effective_after_compiled_restriction"]["domain_cardinality_sum"]) == 154, "C domain sum drift")
    require(abs(float(envelope["effective_after_compiled_restriction"]["box_bits"]) - 80.83308753677896) < 1e-12, "C box-bits drift")
    lowering = receipt["lowering_application"]
    require(isinstance(lowering, dict), "C lacks lowering application receipt")
    require(int(lowering["new_constraint_count"]) == 1, "C lowering did not add exactly one constraint")
    require(lowering["slot_id"] == "boundary_port_041:out:0", "C lowering target slot drift")
    require(lowering["forced_value"] == "__unused__", "C lowering forced value drift")
    require(receipt["endpoint_transaction"]["source_identity_unchanged"] is True, "C endpoint identity changed")
    require(receipt["output_surfaces_before"] == receipt["output_surfaces_after"], "C output surface changed")

    summary = {
        "receipt_sha256": sha256_file(receipt_path)[0],
        "raw_outcome": receipt["outcome"],
        "effective_outcome": "CENSORED",
        "terminal_status": receipt["terminal_status"],
        "censor_status": receipt["censor_status"],
        "binding_solve_seconds": float(receipt["timings"]["binding_solve_seconds"]),
        "wall_seconds": float(receipt["resource_vector"]["wall_seconds"]),
        "cpu_seconds": float(receipt["resource_vector"]["cpu_seconds"]),
        "peak_rss_bytes": int(receipt["resource_vector"]["peak_rss_bytes"]),
        "target_domain_before": 3,
        "target_domain_after": 1,
        "active_values_before": 2,
        "active_values_after": 0,
        "proposal_count": 0,
    }
    return receipt, summary


def verify_preflight(run_dir: Path) -> dict[str, Any]:
    contract_path = run_dir / "preflight/lowering_contract_receipt.json"
    sensitivity_path = run_dir / "preflight/endpoint_sensitivity_receipt.json"
    contract = read_json(contract_path)
    sensitivity = read_json(sensitivity_path)
    verify_envelope(contract, expected_kind="lowering_contract_check")
    verify_envelope(sensitivity, expected_kind="endpoint_metric_sensitivity_check")
    require(contract["outcome"] == "PASS", "lowering contract did not PASS")
    require(contract["verified_scope"]["proto_delta_exact"] is True, "proto delta not exact")
    require(int(contract["verified_scope"]["mutation_canary_count"]) == 4, "mutation count drift")
    require(sensitivity["outcome"] == "PASS", "endpoint sensitivity did not PASS")
    require(int(sensitivity["verified_scope"]["sensitivity_control_count"]) == 11, "sensitivity count drift")
    return {
        "contract_receipt_sha256": sha256_file(contract_path)[0],
        "sensitivity_receipt_sha256": sha256_file(sensitivity_path)[0],
        "proto_delta_exact": True,
        "mutation_canary_count": 4,
        "sensitivity_control_count": 11,
    }


def verify_aggregate(run_dir: Path, arm_receipt_hashes: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    path = run_dir / AGGREGATE_NAME
    aggregate = read_json(path)
    verify_envelope(aggregate, expected_kind="canary_aggregate")
    require(aggregate["outcome"] == "INCONCLUSIVE", "aggregate verdict drift")
    require(aggregate["hard_failures"] == [], "aggregate has hard failures")
    scope = aggregate["verified_scope"]
    require(scope["A_B_semantic_sequence_equal"] is True, "aggregate lost A/B parity")
    require(scope["compiled_domain_effect_observed"] is True, "aggregate lost compiled-domain effect")
    require(scope["runtime_family_collapse_observed"] is False, "aggregate overclaims runtime family collapse")
    require(scope["treatment_effective_outcome"] == "CENSORED", "aggregate treatment classification drift")
    require(aggregate["endpoint_resource_classification"] == "NOT_COMPARABLE_CENSORED", "aggregate resource classification drift")
    local = aggregate["local_effect"]
    require(local["causal_avoidance_claimed"] is False, "aggregate claims causal avoidance")
    require(local["runtime_family_coverage_observed"] is False, "aggregate claims runtime family coverage")
    require(int(local["raw_point_nogood_count_difference_vs_observer"]) == 1007, "raw nogood difference drift")
    require(int(local["raw_point_nogood_literal_difference_vs_observer"]) == 286995, "raw literal difference drift")
    require(aggregate["endpoint_transaction"]["source_identity_unchanged"] is True, "aggregate endpoint identity drift")
    for arm, expected_hash in arm_receipt_hashes.items():
        require(aggregate["subject_identity"]["arm_receipt_sha256"][arm] == expected_hash, f"aggregate arm hash drift: {arm}")
    return aggregate, {
        "aggregate_sha256": sha256_file(path)[0],
        "verdict": aggregate["outcome"],
        "endpoint_resource_classification": aggregate["endpoint_resource_classification"],
        "compiled_domain_effect_observed": True,
        "runtime_family_collapse_observed": False,
        "causal_avoidance_claimed": False,
    }


def verify_apparatus_run() -> dict[str, Any]:
    run_dir = ARTIFACT_ROOT / APPARATUS_RUN_ID
    suite_path = run_dir / "SUITE_RECEIPT.json"
    suite = read_json(suite_path)
    verify_envelope(suite, expected_kind="canary_suite_run")
    require(suite["outcome"] == "PROTOCOL_VIOLATION", "apparatus-run verdict drift")
    require("A_BASELINE returned rc=1" in str(suite.get("error", "")), "apparatus failure reason drift")
    require(not (run_dir / "A_BASELINE/arm_receipt.json").exists(), "apparatus run unexpectedly has an arm receipt")
    require((run_dir / ".DONE").is_file(), "apparatus run lacks DONE marker")
    return {
        "run_id": APPARATUS_RUN_ID,
        "suite_receipt_sha256": sha256_file(suite_path)[0],
        "outcome": suite["outcome"],
        "entered_first_binding_solve": False,
        "scientific_evidence_effect": "NONE",
    }


def build_receipt() -> dict[str, Any]:
    started = time.perf_counter()
    commits = verify_commit_chain()
    run_dir = ARTIFACT_ROOT / SCIENTIFIC_RUN_ID
    require((run_dir / ".DONE").is_file(), "scientific run lacks DONE marker")
    require((run_dir / "EXIT_CODE").read_text(encoding="utf-8").strip() == "1", "historical suite exit code drift")

    preflight = verify_preflight(run_dir)
    a, a_events, a_summary = verify_baseline_arm(run_dir, "A_BASELINE")
    b, b_events, b_summary = verify_baseline_arm(run_dir, "B_OBSERVER_NOOP")
    require([event_projection(value) for value in a_events] == [event_projection(value) for value in b_events], "A/B semantic sequences differ")
    require(a_summary["sequence_sha256"] == b_summary["sequence_sha256"], "A/B sequence hash differs")
    observer_ratio = b_summary["wall_seconds"] / a_summary["wall_seconds"]
    require(observer_ratio <= 1.15, "observer overhead exceeds frozen tolerance")

    c, c_summary = verify_treatment_arm(run_dir)
    arm_hashes = {
        "A_BASELINE": a_summary["receipt_sha256"],
        "B_OBSERVER_NOOP": b_summary["receipt_sha256"],
        "C_UNARY_LOWERING": c_summary["receipt_sha256"],
    }
    aggregate, aggregate_summary = verify_aggregate(run_dir, arm_hashes)
    apparatus = verify_apparatus_run()

    suite_path = run_dir / "SUITE_RECEIPT.json"
    historical_suite = read_json(suite_path)
    require(historical_suite["outcome"] == "PROTOCOL_VIOLATION", "historical suite receipt drift")
    require("arm C_UNARY_LOWERING returned rc=2" in str(historical_suite.get("error", "")), "historical classifier defect reason drift")

    return {
        "result_kind": "gpt56pro_canary_postrun_check",
        "outcome": "PASS",
        "subject_identity": {
            "lineage": "gpt56pro-57a17a7",
            "apparatus_run_id": APPARATUS_RUN_ID,
            "scientific_run_id": SCIENTIFIC_RUN_ID,
            "judgment_id": "J-W0-GHOST-FRONT-BOUNDARY-041-V1",
        },
        "verified_scope": {
            "commit_count": len(commits),
            "preflight_contract_pass": True,
            "endpoint_sensitivity_pass": True,
            "A_event_count": len(a_events),
            "B_event_count": len(b_events),
            "A_B_semantic_sequence_equal": True,
            "C_binding_proposals": int(c["counters"]["binding_proposals"]),
            "compiled_domain_effect_observed": True,
            "runtime_family_collapse_observed": False,
            "scientific_verdict": aggregate["outcome"],
        },
        "authority_basis": {
            "authority_class": "research_only_non_authorizing",
            "source_paths": [
                "docs/research/solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/00_OWNER_AUTHORIZATION_20260816.md",
                "docs/research/solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md",
                "docs/research/solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md",
            ],
        },
        "granted_effects": [
            "permits_tracked_report_to_record_INCONCLUSIVE",
            "records_compiled_domain_effect_without_runtime_family_promotion",
        ],
        "non_implications": [
            "no_canary_PASS",
            "no_runtime_family_collapse_claim",
            "no_compute_gain_claim",
            "no_generic_D3_or_D4_unlock",
            "no_cross_layout_generality",
            "no_bound_or_certified_status_update",
            "no_production_or_publication_authority",
        ],
        "contract_identity": {
            "protocol_freeze_commit": COMMIT_CHAIN[0],
            "prelaunch_revision_commit": COMMIT_CHAIN[1],
            "manifest_path": CANARY_MANIFEST_RELATIVE_PATH,
            "receipt_schema_path": RECEIPT_SCHEMA_RELATIVE_PATH,
            "lineage_manifest_path": LINEAGE_MANIFEST_RELATIVE_PATH,
            "implementation_commits": list(COMMIT_CHAIN[2:]),
            "aggregate_path": str((run_dir / AGGREGATE_NAME).relative_to(ROOT)),
            "aggregate_sha256": aggregate_summary["aggregate_sha256"],
            "checker_path": str(Path(__file__).resolve().relative_to(ROOT)),
            "checker_sha256": sha256_file(Path(__file__).resolve())[0],
        },
        "schema_version": "zmd_gpt56pro_w0_canary_postrun_check_v1",
        "status": "PASS",
        "scientific_verdict": "INCONCLUSIVE",
        "commit_chain": commits,
        "apparatus_history": apparatus,
        "preflight": preflight,
        "arms": {
            "A_BASELINE": a_summary,
            "B_OBSERVER_NOOP": b_summary,
            "C_UNARY_LOWERING": c_summary,
        },
        "observer_effect": {
            "wall_ratio_B_over_A": observer_ratio,
            "within_15_percent_tolerance": True,
            "trigger_evaluator_seconds_B": b_summary["trigger_evaluator_seconds"],
        },
        "aggregate": aggregate_summary,
        "historical_suite_classifier_defect": {
            "suite_receipt_sha256": sha256_file(suite_path)[0],
            "raw_outcome": historical_suite["outcome"],
            "effect_on_scientific_verdict": "NONE_AFTER_IMMUTABLE_ARM_REAGGREGATION",
        },
        "wall_seconds": time.perf_counter() - started,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    started = time.perf_counter()
    try:
        receipt = build_receipt()
        text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        print(text, end="")
        return 0
    except (CheckError, OSError, KeyError, TypeError, ValueError, IndexError) as exc:
        receipt = {
            "result_kind": "gpt56pro_canary_postrun_check",
            "outcome": "FAIL",
            "subject_identity": {"lineage": "gpt56pro-57a17a7"},
            "verified_scope": {"completed": False, "failure_stage": "postrun_check"},
            "authority_basis": {
                "authority_class": "research_only_non_authorizing",
                "source_paths": [
                    "docs/research/solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md"
                ],
            },
            "granted_effects": ["blocks_lineage_report_acceptance"],
            "non_implications": ["no_scientific_verdict"],
            "contract_identity": {
                "protocol_freeze_commit": COMMIT_CHAIN[0],
                "prelaunch_revision_commit": COMMIT_CHAIN[1],
                "manifest_path": CANARY_MANIFEST_RELATIVE_PATH,
                "receipt_schema_path": RECEIPT_SCHEMA_RELATIVE_PATH,
                "lineage_manifest_path": LINEAGE_MANIFEST_RELATIVE_PATH,
                "checker_path": str(Path(__file__).resolve().relative_to(ROOT)),
            },
            "schema_version": "zmd_gpt56pro_w0_canary_postrun_check_v1",
            "status": "FAIL",
            "error": str(exc),
            "wall_seconds": time.perf_counter() - started,
        }
        text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        print(text, end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
