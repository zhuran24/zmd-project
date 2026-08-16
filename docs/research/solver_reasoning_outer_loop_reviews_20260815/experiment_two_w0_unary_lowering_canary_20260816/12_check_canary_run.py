#!/usr/bin/env python3
"""Independently recheck the completed W0 unary-lowering canary evidence."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable, Mapping


class CheckError(RuntimeError):
    """Raised when the completed canary evidence is inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CheckError(f"cannot read JSON {path}: {exc}") from exc
    _require(isinstance(value, dict), f"top-level JSON must be an object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line:
                continue
            value = json.loads(line)
            _require(isinstance(value, dict), f"JSONL line {index} is not an object: {path}")
            records.append(value)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CheckError(f"cannot read JSONL {path}: {exc}") from exc
    return records


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise CheckError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _verify_evidence_manifest(root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        manifest.get("schema_version") == "zmd_w0_unary_canary_evidence_manifest_v1",
        "unexpected evidence manifest schema",
    )
    checked = 0
    for spec in manifest["files"]:
        path = root / str(spec["path"])
        _require(path.is_file(), f"missing evidence file: {spec['path']}")
        _require(path.stat().st_size == int(spec["size_bytes"]), f"size drift: {spec['path']}")
        _require(_sha256(path) == spec["sha256"], f"SHA-256 drift: {spec['path']}")
        checked += 1
    return {"file_count": checked, "status": "PASS"}


def _event_projection(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    selection_digests: list[str] = []
    signature_distribution: Counter[str] = Counter()
    precheck_distribution: Counter[str] = Counter()
    trigger_true = 0
    active_spec_total = 0
    for record in records:
        if record.get("record_type") != "routing_precheck_failure":
            continue
        selection_digests.append(str(record["selection_digest"]))
        signature_distribution[str(record["local_signature_digest"])] += 1
        reason = str(record.get("reason", ""))
        precheck_distribution[
            "front_blocked" if reason == "routing_front_blocked" else reason
        ] += 1
        trigger_true += int(record.get("posthoc_j_trigger") is True)
        active_spec_total += int(record.get("target_active_port_spec_count", 0))
    ordered_hash = hashlib.sha256(
        "\n".join(selection_digests).encode("ascii")
    ).hexdigest()
    return {
        "record_count": len(selection_digests),
        "distinct_selection_count": len(set(selection_digests)),
        "ordered_selection_digest_hash": ordered_hash,
        "trigger_true_count": trigger_true,
        "active_target_port_spec_total": active_spec_total,
        "signature_distribution": dict(sorted(signature_distribution.items())),
        "precheck_distribution": dict(sorted(precheck_distribution.items())),
    }


def _feedback_projection(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    applied = [record for record in records if record.get("record_type") == "feedback_applied"]
    outcomes = [record for record in records if record.get("record_type") == "feedback_outcome"]
    literals = [int(record["literal_count"]) for record in applied]
    return {
        "applied_count": len(applied),
        "outcome_count": len(outcomes),
        "literal_count_distribution": dict(sorted(Counter(literals).items())),
        "literal_total": sum(literals),
    }


def _verify_arm(
    run_dir: Path,
    arm: str,
    frozen: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    arm_dir = run_dir / arm
    summary = _load_json(arm_dir / "summary.json")
    events_path = arm_dir / "events.jsonl"
    feedback_path = arm_dir / "feedback.jsonl"
    _require(summary.get("arm") == arm, f"arm summary identity mismatch: {arm}")
    _require(_sha256(events_path) == summary["journals"]["events"]["sha256"], f"event hash mismatch: {arm}")
    _require(_sha256(feedback_path) == summary["journals"]["feedback"]["sha256"], f"feedback hash mismatch: {arm}")
    events = _read_jsonl(events_path)
    feedback = _read_jsonl(feedback_path)
    event_projection = _event_projection(events)
    feedback_projection = _feedback_projection(feedback)

    if arm in {"A_BASELINE", "B_OBSERVER_NOOP"}:
        _require(event_projection["record_count"] == int(frozen["event_count"]), f"event count mismatch: {arm}")
        _require(event_projection["distinct_selection_count"] == int(frozen["unique_selection_count"]), f"distinct selection mismatch: {arm}")
        _require(event_projection["trigger_true_count"] == int(frozen["primary_trigger_count"]), f"trigger coverage mismatch: {arm}")
        _require(event_projection["active_target_port_spec_total"] == int(frozen["event_count"]), f"target port-spec count mismatch: {arm}")
        _require(event_projection["signature_distribution"] == frozen["local_signature_digest_distribution"], f"signature distribution mismatch: {arm}")
        _require(event_projection["precheck_distribution"] == frozen["precheck_status_distribution"], f"precheck distribution mismatch: {arm}")
        _require(feedback_projection["applied_count"] == int(frozen["event_count"]), f"point nogood count mismatch: {arm}")
        _require(
            feedback_projection["literal_count_distribution"]
            == {
                int(frozen["point_nogood_literal_count_each"]): int(
                    frozen["event_count"]
                )
            },
            f"point literal distribution mismatch: {arm}",
        )
        _require(feedback_projection["literal_total"] == int(frozen["event_count"]) * int(frozen["point_nogood_literal_count_each"]), f"point literal total mismatch: {arm}")
    else:
        _require(event_projection["record_count"] == 0, "treatment unexpectedly emitted a routing-precheck event")
        _require(feedback_projection["applied_count"] == 0, "treatment unexpectedly emitted feedback")
        _require(summary["terminalStatus"] == "UNKNOWN", "treatment terminal status drift")
        _require(summary["censorStatus"] == "SOLVER_TIMEOUT_BINDING", "treatment censor status drift")
        _require(summary["finalReason"] == "binding_solver_timeout", "treatment reason drift")
        _require(int(summary["counters"].get("binding_solve_calls", 0)) == 1, "treatment solve-call count drift")
        _require(int(summary["selection"]["posthoc_j_trigger_true_count"]) == 0, "treatment observed a J-triggering proposal")
        _require(int(summary["selection"]["target_active_port_spec_total"]) == 0, "treatment observed an active target port spec")

    return summary, event_projection, feedback_projection


def _check(
    *,
    artifact_root: Path,
    tracked_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_manifest = _load_json(artifact_root / "EVIDENCE_MANIFEST.json")
    manifest_check = _verify_evidence_manifest(artifact_root, evidence_manifest)
    run_dir = artifact_root / str(evidence_manifest["run_id"])
    _require((run_dir / ".DONE").is_file(), "run .DONE marker is absent")
    _require((run_dir / "EXIT_CODE").read_text(encoding="utf-8").strip() == "0", "run exit code is nonzero")
    aggregate = _load_json(run_dir / "AGGREGATE_SUMMARY.json")
    _require(aggregate["protocol_freeze_commit"] == tracked_manifest["protocol_freeze_commit"], "protocol commit mismatch")
    frozen = tracked_manifest["baseline_frozen_prefix"]

    arms: dict[str, dict[str, Any]] = {}
    event_projections: dict[str, dict[str, Any]] = {}
    feedback_projections: dict[str, dict[str, Any]] = {}
    for arm in ("A_BASELINE", "B_OBSERVER_NOOP", "C_UNARY_LOWERING"):
        summary, event_projection, feedback_projection = _verify_arm(run_dir, arm, frozen)
        arms[arm] = summary
        event_projections[arm] = event_projection
        feedback_projections[arm] = feedback_projection

    _require(
        event_projections["A_BASELINE"]["ordered_selection_digest_hash"]
        == event_projections["B_OBSERVER_NOOP"]["ordered_selection_digest_hash"],
        "observer-noop changed the ordered selection sequence",
    )
    _require(aggregate["endpoint_before"] == aggregate["endpoint_after"], "endpoint identity changed")
    _require(aggregate["endpoint_sensitivity"]["status"] == "PASS", "endpoint sensitivity failed")
    _require(aggregate["endpoint_sensitivity"]["sensitivity"]["result_count"] == 11, "endpoint sensitivity count drift")
    _require(aggregate["lowering_contract"]["status"] == "PASS", "lowering contract failed")
    _require(
        aggregate["lowering_contract"]["reject_set_relation"]
        == "EQUAL_TO_ACTIVE_041_TRIGGER_SET",
        "lowering reject-set relation drift",
    )

    treatment = arms["C_UNARY_LOWERING"]
    comparable = (
        treatment["terminalStatus"] in {"FEASIBLE", "INFEASIBLE"}
        and treatment["censorStatus"] == "UNCENSORED"
    ) or int(treatment["selection"]["selection_count"]) == int(
        tracked_manifest["run_parameters"]["event_cap"]
    )
    recomputed_verdict = "INCONCLUSIVE" if not comparable else "UNEXPECTED_COMPARABLE_RESULT"
    _require(recomputed_verdict == "INCONCLUSIVE", "post-run checker expected a censored treatment")
    _require(aggregate["evaluation"]["verdict"] == recomputed_verdict, "aggregate verdict drift")
    _require(evidence_manifest["verdict"] == recomputed_verdict, "evidence-manifest verdict drift")

    return {
        "status": "PASS",
        "verdict": recomputed_verdict,
        "protocol_freeze_commit": aggregate["protocol_freeze_commit"],
        "implementation_code_head": aggregate["code_head"],
        "manifest_check": manifest_check,
        "endpoint_sensitivity": {
            "status": "PASS",
            "control_count": 11,
        },
        "lowering_contract": {
            "status": "PASS",
            "added_constraint_count": aggregate["lowering_contract"]["added_constraint_count"],
            "reject_set_relation": aggregate["lowering_contract"]["reject_set_relation"],
            "baseline_variable_count": aggregate["lowering_contract"]["baseline_variable_count"],
            "baseline_constraint_count": aggregate["lowering_contract"]["baseline_constraint_count"],
            "treatment_constraint_count": aggregate["lowering_contract"]["treatment_constraint_count"],
        },
        "arms": {
            arm: {
                "terminalStatus": arms[arm]["terminalStatus"],
                "censorStatus": arms[arm]["censorStatus"],
                "finalReason": arms[arm]["finalReason"],
                "selection_count": arms[arm]["selection"]["selection_count"],
                "j_trigger_true_count": arms[arm]["selection"]["posthoc_j_trigger_true_count"],
                "wall_seconds": arms[arm]["resources"]["total_wall_seconds"],
                "event_projection": event_projections[arm],
                "feedback_projection": feedback_projections[arm],
            }
            for arm in arms
        },
        "observer_same_selection_sequence": True,
        "endpoint_transaction": {
            "delta_L": "ZERO_BY_SCOPE",
            "delta_U": "ZERO_BY_SCOPE",
            "M_t": "N_A_NOT_READY",
            "delta_M": "ZERO_BY_SCOPE",
            "identity_unchanged": True,
        },
        "interpretation": "The unary lowering is sound and the observer is inert, but the treatment was censored before its first binding proposal; zero observed J triggers is therefore not evidence of successful runtime family consumption.",
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    started = time.perf_counter()
    try:
        tracked_manifest = _load_json(args.manifest)
        checked = _check(
            artifact_root=args.artifact_root.resolve(),
            tracked_manifest=tracked_manifest,
        )
        receipt = {
            "schema_version": "zmd_w0_unary_canary_independent_check_v1",
            **checked,
            "artifact_root": str(args.artifact_root.resolve()),
            "evidence_manifest_sha256": _sha256(
                args.artifact_root.resolve() / "EVIDENCE_MANIFEST.json"
            ),
            "tracked_manifest_sha256": _sha256(args.manifest),
            "checker_sha256": _sha256(Path(__file__)),
            "standard_library_only": True,
            "wall_seconds": time.perf_counter() - started,
        }
        encoded = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 0
    except (CheckError, KeyError, TypeError, ValueError, OSError) as exc:
        failure = {
            "schema_version": "zmd_w0_unary_canary_independent_check_v1",
            "status": "FAIL",
            "error": str(exc),
            "wall_seconds": time.perf_counter() - started,
        }
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
