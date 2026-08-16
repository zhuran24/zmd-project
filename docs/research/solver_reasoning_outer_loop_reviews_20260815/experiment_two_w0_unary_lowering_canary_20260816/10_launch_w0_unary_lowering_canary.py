#!/usr/bin/env python3
"""Launch, aggregate, and close the frozen W0 unary-lowering canary run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


PROTOCOL_FREEZE_COMMIT = "0339c745b6c7f498fc989398de380a78578fc785"
ARM_ORDER = ("A_BASELINE", "B_OBSERVER_NOOP", "C_UNARY_LOWERING")
PUBLIC_RUNTIME_PATHS = (
    "data/solutions/final_solution.json",
    "data/blueprints/optimal_blueprint.json",
    "data/solutions/certified_delivery_manifest.json",
    "data/checkpoints",
)


class LaunchError(RuntimeError):
    """The frozen canary launcher cannot complete its evidence transaction."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LaunchError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LaunchError(f"cannot read JSON {path}: {exc}") from exc
    _require(isinstance(value, dict), f"top-level JSON must be an object: {path}")
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise LaunchError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _tree_identity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"state": "ABSENT"}
    if path.is_file():
        return {
            "state": "FILE",
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
    records: list[dict[str, Any]] = []
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        records.append(
            {
                "path": str(child.relative_to(path)),
                "sha256": _sha256(child),
                "size_bytes": child.stat().st_size,
            }
        )
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "state": "DIRECTORY",
        "file_count": len(records),
        "tree_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _capture_endpoint(
    *,
    code_root: Path,
    evidence_root: Path,
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for spec in protocol["current_endpoint_sources"]:
        path = code_root / str(spec["path"])
        _require(path.is_file(), f"missing endpoint source: {spec['path']}")
        actual = _sha256(path)
        _require(actual == spec["sha256"], f"endpoint source drift: {spec['path']}")
        record: dict[str, Any] = {
            "role": spec["role"],
            "path": spec["path"],
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }
        if spec["role"] == "durable_exact_status":
            payload = _load_json(path)
            _require(
                str(payload.get("status", "")).upper()
                == str(spec["expected_status"]).upper(),
                "durable status drift",
            )
            _require(
                payload.get("best_certified_result")
                == spec["expected_best_certified_result"],
                "best_certified_result drift",
            )
            record["status"] = payload.get("status")
            record["best_certified_result"] = payload.get("best_certified_result")
        elif spec["role"] == "stable_claim_ledger":
            claims: dict[str, Mapping[str, Any]] = {}
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                if isinstance(item, dict) and item.get("id"):
                    claims[str(item["id"])] = item
            for claim_id in spec["required_claim_ids"]:
                _require(str(claim_id) in claims, f"missing endpoint claim {claim_id}")
            record["required_claims"] = {
                str(claim_id): {
                    "status": claims[str(claim_id)].get("status"),
                    "statement": claims[str(claim_id)].get("statement"),
                }
                for claim_id in spec["required_claim_ids"]
            }
        sources.append(record)

    protected: list[dict[str, Any]] = []
    for spec in protocol["protected_surfaces"]:
        path = code_root / str(spec["path"])
        _require(path.is_file(), f"missing protected surface: {spec['path']}")
        actual = _sha256(path)
        _require(actual == spec["sha256"], f"protected surface drift: {spec['path']}")
        protected.append(
            {
                "path": spec["path"],
                "sha256": actual,
                "size_bytes": path.stat().st_size,
            }
        )

    runtime = {
        relative: _tree_identity(evidence_root / relative)
        for relative in PUBLIC_RUNTIME_PATHS
    }
    return {
        "sources": sources,
        "protected_surfaces": protected,
        "public_runtime_paths": runtime,
    }


def _run_checked(
    command: Sequence[str],
    *,
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    timeout: float,
    env: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=dict(env),
        )
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_text(exc.stdout or "", encoding="utf-8")
        stderr_path.write_text(exc.stderr or "", encoding="utf-8")
        raise LaunchError(f"child timed out after {timeout}s: {' '.join(command)}") from exc
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise LaunchError(
            f"child exited {completed.returncode}: {' '.join(command)}; "
            f"see {stdout_path} and {stderr_path}"
        )
    completed.elapsed_seconds = time.perf_counter() - started  # type: ignore[attr-defined]
    return completed


def _arm_contract_matches_frozen(
    summary: Mapping[str, Any],
    frozen: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    selection = summary["selection"]
    counters = summary["counters"]
    spectrum = summary["failure_spectrum"]
    if int(selection["selection_count"]) != int(frozen["event_count"]):
        reasons.append("selection_count")
    if int(selection["distinct_selection_count"]) != int(frozen["unique_selection_count"]):
        reasons.append("unique_selection_count")
    if int(selection["posthoc_j_trigger_true_count"]) != int(frozen["primary_trigger_count"]):
        reasons.append("primary_trigger_count")
    if spectrum["precheck_status_distribution"] != frozen["precheck_status_distribution"]:
        reasons.append("precheck_status_distribution")
    if (
        spectrum["local_signature_digest_distribution"]
        != frozen["local_signature_digest_distribution"]
    ):
        reasons.append("local_signature_digest_distribution")
    if int(counters.get("point_nogoods", 0)) != int(frozen["event_count"]):
        reasons.append("point_nogood_count")
    expected_literals = int(frozen["event_count"]) * int(
        frozen["point_nogood_literal_count_each"]
    )
    if int(counters.get("point_nogood_literals", 0)) != expected_literals:
        reasons.append("point_nogood_literal_total")
    return not reasons, reasons


def _relative_regression(after: float, before: float) -> float:
    if before <= 0:
        return 0.0 if after <= 0 else float("inf")
    return (after - before) / before


def _evaluate(
    *,
    manifest: Mapping[str, Any],
    endpoint_before: Mapping[str, Any],
    endpoint_after: Mapping[str, Any],
    sensitivity: Mapping[str, Any],
    lowering: Mapping[str, Any],
    arms: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    hard_failures: list[str] = []
    if sensitivity.get("status") != "PASS":
        hard_failures.append("endpoint_sensitivity")
    if lowering.get("status") != "PASS":
        hard_failures.append("lowering_contract")
    if endpoint_before != endpoint_after:
        hard_failures.append("endpoint_or_protected_surface_changed")

    frozen = manifest["baseline_frozen_prefix"]
    a_ok, a_reasons = _arm_contract_matches_frozen(arms["A_BASELINE"], frozen)
    b_ok, b_reasons = _arm_contract_matches_frozen(arms["B_OBSERVER_NOOP"], frozen)
    observer_same_sequence = (
        arms["A_BASELINE"]["selection"]["ordered_selection_digest_hash"]
        == arms["B_OBSERVER_NOOP"]["selection"]["ordered_selection_digest_hash"]
    )
    if not observer_same_sequence:
        b_reasons.append("observer_changed_selection_sequence")
        b_ok = False

    c = arms["C_UNARY_LOWERING"]
    c_selection = c["selection"]
    c_zero_trigger = int(c_selection["posthoc_j_trigger_true_count"]) == 0
    c_zero_port = int(c_selection["target_active_port_spec_total"]) == 0
    c_terminal = c["terminalStatus"] in {"FEASIBLE", "INFEASIBLE"} and c[
        "censorStatus"
    ] == "UNCENSORED"
    c_cap = int(c_selection["selection_count"]) == int(
        manifest["run_parameters"]["event_cap"]
    )
    c_comparable = c_terminal or c_cap

    a_wall = float(arms["A_BASELINE"]["resources"]["total_wall_seconds"])
    b_wall = float(arms["B_OBSERVER_NOOP"]["resources"]["total_wall_seconds"])
    c_wall = float(c["resources"]["total_wall_seconds"])
    observer_regression = _relative_regression(b_wall, a_wall)
    treatment_regression = _relative_regression(c_wall, b_wall)
    observer_cost_ok = observer_regression <= 0.15
    treatment_cost_ok = treatment_regression <= 0.25 or c_terminal

    if hard_failures:
        verdict = "LOWERING_UNSOUND_OR_OVERREACH"
        endpoint_classification = "INCONCLUSIVE"
    elif not a_ok or not b_ok:
        verdict = "INCONCLUSIVE"
        endpoint_classification = "INCONCLUSIVE"
    elif c_comparable and (not c_zero_trigger or not c_zero_port):
        verdict = "NO_LOCAL_EFFECT"
        endpoint_classification = "INCONCLUSIVE"
    elif c_comparable and c_zero_trigger and c_zero_port:
        if observer_cost_ok and treatment_cost_ok:
            verdict = "CANARY_PASS_LOCAL_CONSUMPTION"
            endpoint_classification = (
                "ENDPOINT_NEUTRAL_COMPUTE_GAIN"
                if c_terminal and c_wall < b_wall
                else "ENDPOINT_NEUTRAL_INFRASTRUCTURE"
            )
        else:
            verdict = "LOCAL_EFFECT_WITH_COST_REGRESSION"
            endpoint_classification = "LOCAL_GAIN_COST_REGRESSION"
    else:
        verdict = "INCONCLUSIVE"
        endpoint_classification = "INCONCLUSIVE"

    return {
        "verdict": verdict,
        "endpoint_classification": endpoint_classification,
        "hard_failures": hard_failures,
        "baseline_frozen_prefix_match": {
            "A_BASELINE": {"pass": a_ok, "reasons": a_reasons},
            "B_OBSERVER_NOOP": {"pass": b_ok, "reasons": b_reasons},
            "observer_same_selection_sequence": observer_same_sequence,
        },
        "treatment_effect": {
            "zero_j_trigger": c_zero_trigger,
            "zero_target_active_port_spec": c_zero_port,
            "terminal_milestone": c_terminal,
            "event_cap_milestone": c_cap,
            "comparable_milestone": c_comparable,
            "terminalStatus": c["terminalStatus"],
            "censorStatus": c["censorStatus"],
            "finalReason": c["finalReason"],
        },
        "cost": {
            "A_wall_seconds": a_wall,
            "B_wall_seconds": b_wall,
            "C_wall_seconds": c_wall,
            "B_vs_A_regression": observer_regression,
            "C_vs_B_regression": treatment_regression,
            "observer_tolerance": 0.15,
            "treatment_tolerance": 0.25,
            "observer_cost_ok": observer_cost_ok,
            "treatment_cost_ok_or_stronger_terminal": treatment_cost_ok,
        },
        "endpoint_transaction": {
            "delta_L": "ZERO_BY_SCOPE",
            "delta_U": "ZERO_BY_SCOPE",
            "M_t": "N_A_NOT_READY",
            "delta_M": "ZERO_BY_SCOPE",
            "endpoint_identity_unchanged": endpoint_before == endpoint_after,
        },
    }


def _evidence_manifest(root: Path, run_dir: Path, aggregate: Mapping[str, Any]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        files.append(
            {
                "path": str(path.relative_to(root)),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return {
        "schema_version": "zmd_w0_unary_canary_evidence_manifest_v1",
        "research_only": True,
        "artifact_root": str(root),
        "run_id": run_dir.name,
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "verdict": aggregate["evaluation"]["verdict"],
        "files": files,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--run-id", default="w0-unary-canary-r1-20260816")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    code_root = args.code_root.resolve()
    evidence_root = args.evidence_root.resolve()
    here = Path(__file__).resolve().parent
    manifest_path = here / "08_CANARY_MANIFEST.json"
    contract_path = here / "05_LOWERING_CONTRACT_V1.json"
    endpoint_protocol_path = here / "03_ENDPOINT_METRICS_PROTOCOL_V1.json"
    manifest = _load_json(manifest_path)
    endpoint_protocol = _load_json(endpoint_protocol_path)
    _require(
        manifest.get("protocol_freeze_commit") == PROTOCOL_FREEZE_COMMIT,
        "launcher manifest protocol commit mismatch",
    )
    artifact_root = evidence_root / str(manifest["artifact_root"])
    run_dir = artifact_root / str(args.run_id)
    _require(not run_dir.exists(), f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    started = time.perf_counter()
    exit_code = 1
    try:
        endpoint_before = _capture_endpoint(
            code_root=code_root,
            evidence_root=evidence_root,
            protocol=endpoint_protocol,
        )
        _write_json(run_dir / "endpoint_before.json", endpoint_before)

        sensitivity_output = run_dir / "endpoint_sensitivity.json"
        _run_checked(
            [
                str(args.python),
                str(here / "06_check_endpoint_metrics.py"),
                "--protocol",
                str(endpoint_protocol_path),
                "--output",
                str(sensitivity_output),
            ],
            cwd=code_root,
            stdout_path=run_dir / "endpoint_sensitivity.stdout.log",
            stderr_path=run_dir / "endpoint_sensitivity.stderr.log",
            timeout=120,
            env={**os.environ, "PYTHONPATH": str(code_root)},
        )

        arms: dict[str, dict[str, Any]] = {}
        arm_commands: dict[str, list[str]] = {}
        child_timeout = float(manifest["run_parameters"]["arm_watchdog_seconds"]) + 180.0
        for arm in ARM_ORDER:
            arm_dir = run_dir / arm
            command = [
                str(args.python),
                str(here / "09_w0_unary_lowering_canary.py"),
                "--arm",
                arm,
                "--code-root",
                str(code_root),
                "--evidence-root",
                str(evidence_root),
                "--output-dir",
                str(arm_dir),
                "--manifest",
                str(manifest_path),
                "--contract",
                str(contract_path),
                "--python",
                str(args.python),
            ]
            arm_commands[arm] = command
            _run_checked(
                command,
                cwd=code_root,
                stdout_path=run_dir / f"{arm}.stdout.log",
                stderr_path=run_dir / f"{arm}.stderr.log",
                timeout=child_timeout,
                env={**os.environ, "PYTHONPATH": str(code_root)},
            )
            arms[arm] = _load_json(arm_dir / "summary.json")

        baseline_snapshot = run_dir / "A_BASELINE" / "model_snapshot.json"
        treatment_snapshot = run_dir / "C_UNARY_LOWERING" / "model_snapshot.json"
        baseline_meta = _load_json(run_dir / "A_BASELINE" / "model_metadata.json")
        treatment_meta = _load_json(
            run_dir / "C_UNARY_LOWERING" / "model_metadata.json"
        )
        lowering_metadata = {
            "schema_version": "zmd_w0_lowering_metadata_v1",
            "target": treatment_meta["target"],
            "baseline_variable_count": baseline_meta["variable_count"],
            "treatment_variable_count": treatment_meta["variable_count"],
            "baseline_snapshot_digest": baseline_meta["model_snapshot_digest"],
            "treatment_snapshot_digest": treatment_meta["model_snapshot_digest"],
        }
        lowering_metadata_path = run_dir / "lowering_metadata.json"
        _write_json(lowering_metadata_path, lowering_metadata)
        lowering_output = run_dir / "lowering_contract_receipt.json"
        _run_checked(
            [
                str(args.python),
                str(here / "07_check_lowering_contract.py"),
                "--contract",
                str(contract_path),
                "--baseline",
                str(baseline_snapshot),
                "--treatment",
                str(treatment_snapshot),
                "--metadata",
                str(lowering_metadata_path),
                "--output",
                str(lowering_output),
            ],
            cwd=code_root,
            stdout_path=run_dir / "lowering_contract.stdout.log",
            stderr_path=run_dir / "lowering_contract.stderr.log",
            timeout=120,
            env={**os.environ, "PYTHONPATH": str(code_root)},
        )

        endpoint_after = _capture_endpoint(
            code_root=code_root,
            evidence_root=evidence_root,
            protocol=endpoint_protocol,
        )
        _write_json(run_dir / "endpoint_after.json", endpoint_after)
        sensitivity = _load_json(sensitivity_output)
        lowering = _load_json(lowering_output)
        evaluation = _evaluate(
            manifest=manifest,
            endpoint_before=endpoint_before,
            endpoint_after=endpoint_after,
            sensitivity=sensitivity,
            lowering=lowering,
            arms=arms,
        )
        aggregate = {
            "schema_version": "zmd_w0_unary_canary_aggregate_v1",
            "research_only": True,
            "run_id": str(args.run_id),
            "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
            "code_head": subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=code_root,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout.strip(),
            "implementation_files": {
                str(path.relative_to(code_root)): _sha256(path)
                for path in (
                    here / "05_LOWERING_CONTRACT_V1.json",
                    here / "06_check_endpoint_metrics.py",
                    here / "07_check_lowering_contract.py",
                    here / "08_CANARY_MANIFEST.json",
                    here / "09_w0_unary_lowering_canary.py",
                    here / "10_launch_w0_unary_lowering_canary.py",
                )
            },
            "arm_commands": arm_commands,
            "arms": arms,
            "endpoint_sensitivity": sensitivity,
            "lowering_contract": lowering,
            "endpoint_before": endpoint_before,
            "endpoint_after": endpoint_after,
            "evaluation": evaluation,
            "total_launcher_wall_seconds": time.perf_counter() - started,
        }
        _write_json(run_dir / "AGGREGATE_SUMMARY.json", aggregate)
        _write_json(
            run_dir / "RUN_MANIFEST.json",
            {
                "schema_version": "zmd_w0_unary_canary_run_manifest_v1",
                "run_id": str(args.run_id),
                "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
                "artifact_root": str(artifact_root),
                "code_root": str(code_root),
                "evidence_root": str(evidence_root),
                "python": str(args.python),
                "verdict": evaluation["verdict"],
            },
        )
        exit_code = 0
        _write_text(run_dir / "EXIT_CODE", "0\n")
        (run_dir / ".DONE").touch()
        evidence_manifest = _evidence_manifest(artifact_root, run_dir, aggregate)
        _write_json(artifact_root / "EVIDENCE_MANIFEST.json", evidence_manifest)
        return 0
    except Exception as exc:  # noqa: BLE001
        _write_json(
            run_dir / "LAUNCH_FAILURE.json",
            {
                "schema_version": "zmd_w0_unary_canary_launch_failure_v1",
                "status": "HARNESS_ERROR",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "wall_seconds": time.perf_counter() - started,
            },
        )
        return 1
    finally:
        _write_text(run_dir / "EXIT_CODE", f"{exit_code}\n")
        (run_dir / ".DONE").touch()


if __name__ == "__main__":
    raise SystemExit(main())
