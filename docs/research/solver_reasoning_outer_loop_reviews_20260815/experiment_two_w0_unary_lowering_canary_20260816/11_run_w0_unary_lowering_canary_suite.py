#!/usr/bin/env python3
"""Launch or execute the frozen W0 unary-lowering canary suite."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
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
CONTRACT_CHECKER = HERE / "06_check_w0_unary_lowering_contract.py"
SENSITIVITY_CHECKER = HERE / "08_check_endpoint_metrics_sensitivity.py"
ARM_RUNNER = HERE / "09_run_w0_unary_lowering_arm.py"
AGGREGATOR = HERE / "10_aggregate_w0_unary_lowering_canary.py"
ARMS = ("A_BASELINE", "B_OBSERVER_NOOP", "C_UNARY_LOWERING")


class SuiteError(RuntimeError):
    """The canary suite cannot honor its frozen execution order."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SuiteError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SuiteError(f"cannot read JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"top-level JSON must be an object: {path}")
    return value


def write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    write_text_atomic(
        path,
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SuiteError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def expected_artifact_root(manifest: Mapping[str, Any]) -> Path:
    return (ROOT / str(manifest["run_parameters"]["artifact_root"])).resolve()


def ensure_run_dir(run_dir: Path, manifest: Mapping[str, Any]) -> None:
    artifact_root = expected_artifact_root(manifest)
    try:
        run_dir.relative_to(artifact_root)
    except ValueError as exc:
        raise SuiteError(f"run directory escapes frozen artifact root: {run_dir}") from exc
    run_dir.mkdir(parents=True, exist_ok=True)


def run_command(
    command: list[str],
    *,
    log_path: Path,
    timeout_seconds: float,
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with log_path.open("wb") as log:
        log.write(("COMMAND " + " ".join(command) + "\n").encode("utf-8"))
        log.flush()
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                check=False,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
            )
            return int(result.returncode)
        except subprocess.TimeoutExpired:
            log.write(
                f"\nSUITE_TIMEOUT after {time.perf_counter() - started:.6f}s\n".encode(
                    "utf-8"
                )
            )
            log.flush()
            os.fsync(log.fileno())
            return 124


def load_pass_receipt(path: Path, expected_kind: str) -> dict[str, Any]:
    receipt = read_json(path)
    validate_receipt(receipt)
    require(receipt["result_kind"] == expected_kind, f"wrong receipt kind: {path}")
    require(receipt["outcome"] == "PASS", f"prerequisite did not PASS: {path}")
    return receipt


def tree_manifest(root: Path, *, exclude_names: set[str] | None = None) -> list[dict[str, Any]]:
    excludes = exclude_names or set()
    records: list[dict[str, Any]] = []
    for path in sorted(value for value in root.rglob("*") if value.is_file()):
        if path.name in excludes:
            continue
        records.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return records


def update_top_level_evidence_manifest(
    artifact_root: Path,
    *,
    run_id: str,
    run_dir: Path,
    final_outcome: str,
    implementation_head: str,
) -> Path:
    path = artifact_root / "EVIDENCE_MANIFEST.json"
    payload = {
        "schema_version": "zmd_w0_unary_canary_local_evidence_manifest_v1",
        "research_only": True,
        "artifact_root": str(artifact_root.relative_to(ROOT)),
        "protocol_freeze_commit": "57a17a7672cf879fc39e0e67a044590a85cb47a2",
        "prelaunch_revision_commit": "988d1b787778c211f5e8b930b7f6cf093581aed8",
        "implementation_head": implementation_head,
        "latest_run_id": run_id,
        "runs": [
            {
                "run_id": run_id,
                "run_dir": str(run_dir.relative_to(ROOT)),
                "final_outcome": final_outcome,
                "files": tree_manifest(run_dir),
            }
        ],
    }
    write_json_atomic(path, payload)
    return path


def worker(run_dir: Path, run_id: str) -> int:
    manifest = read_json(MANIFEST_PATH)
    ensure_run_dir(run_dir, manifest)
    implementation_head = git("rev-parse", "HEAD")
    write_text_atomic(run_dir / "RUN_ID", run_id + "\n")
    write_text_atomic(run_dir / "IMPLEMENTATION_HEAD", implementation_head + "\n")

    preflight = run_dir / "preflight"
    contract_receipt_path = preflight / "lowering_contract_receipt.json"
    sensitivity_receipt_path = preflight / "endpoint_sensitivity_receipt.json"

    contract_rc = run_command(
        [
            sys.executable,
            str(CONTRACT_CHECKER),
            "--output",
            str(contract_receipt_path),
        ],
        log_path=preflight / "lowering_contract.log",
        timeout_seconds=300.0,
    )
    require(contract_rc == 0, f"lowering contract checker rc={contract_rc}")
    load_pass_receipt(contract_receipt_path, "lowering_contract_check")

    sensitivity_rc = run_command(
        [
            sys.executable,
            str(SENSITIVITY_CHECKER),
            "--contract-receipt",
            str(contract_receipt_path),
            "--output",
            str(sensitivity_receipt_path),
        ],
        log_path=preflight / "endpoint_sensitivity.log",
        timeout_seconds=300.0,
    )
    require(sensitivity_rc == 0, f"endpoint sensitivity checker rc={sensitivity_rc}")
    load_pass_receipt(sensitivity_receipt_path, "endpoint_metric_sensitivity_check")

    arm_exit_codes: dict[str, int] = {}
    arm_timeout = {
        "A_BASELINE": float(manifest["run_parameters"]["minimal_baseline_arm_watchdog_seconds"]) + 60.0,
        "B_OBSERVER_NOOP": float(manifest["run_parameters"]["observation_noop_arm_watchdog_seconds"]) + 60.0,
        "C_UNARY_LOWERING": float(manifest["run_parameters"]["treatment_arm_watchdog_seconds"]) + 60.0,
    }
    for arm in ARMS:
        rc = run_command(
            [
                sys.executable,
                str(ARM_RUNNER),
                "--arm",
                arm,
                "--run-id",
                run_id,
                "--run-dir",
                str(run_dir),
                "--contract-receipt",
                str(contract_receipt_path),
                "--sensitivity-receipt",
                str(sensitivity_receipt_path),
            ],
            log_path=run_dir / arm / "arm.log",
            timeout_seconds=arm_timeout[arm],
        )
        arm_exit_codes[arm] = rc
        if rc != 0:
            raise SuiteError(f"arm {arm} returned rc={rc}; later arms were not launched")

    aggregate_path = run_dir / "CANARY_AGGREGATE.json"
    aggregate_rc = run_command(
        [
            sys.executable,
            str(AGGREGATOR),
            "--run-dir",
            str(run_dir),
            "--run-id",
            run_id,
            "--output",
            str(aggregate_path),
        ],
        log_path=run_dir / "aggregate.log",
        timeout_seconds=120.0,
    )
    require(aggregate_path.is_file(), "aggregate receipt is missing")
    aggregate_receipt = read_json(aggregate_path)
    validate_receipt(aggregate_receipt)
    final_outcome = str(aggregate_receipt["outcome"])

    suite_receipt = make_receipt(
        result_kind="canary_suite_run",
        outcome=final_outcome,
        subject_identity={
            "run_id": run_id,
            "run_dir": str(run_dir.relative_to(ROOT)),
            "implementation_head": implementation_head,
        },
        verified_scope={
            "contract_checker_rc": contract_rc,
            "sensitivity_checker_rc": sensitivity_rc,
            "arm_exit_codes": arm_exit_codes,
            "aggregate_rc": aggregate_rc,
            "aggregate_outcome": final_outcome,
        },
        granted_effects=list(aggregate_receipt["granted_effects"]),
        non_implications=list(aggregate_receipt["non_implications"]),
        details={
            "schema_version": "zmd_w0_unary_canary_suite_receipt_v1",
            "status": "PASS" if final_outcome == "CANARY_PASS_LOCAL_CONSUMPTION" else "NON_PASS",
            "aggregate_receipt_path": str(aggregate_path.relative_to(ROOT)),
            "aggregate_receipt_sha256": sha256_file(aggregate_path),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        contract_extra={
            "suite_script_path": str(Path(__file__).resolve().relative_to(ROOT)),
            "suite_script_sha256": sha256_file(Path(__file__).resolve()),
            "implementation_head": implementation_head,
        },
    )
    dump_receipt(suite_receipt, run_dir / "SUITE_RECEIPT.json")

    artifact_root = expected_artifact_root(manifest)
    evidence_manifest = update_top_level_evidence_manifest(
        artifact_root,
        run_id=run_id,
        run_dir=run_dir,
        final_outcome=final_outcome,
        implementation_head=implementation_head,
    )
    write_text_atomic(run_dir / "EXIT_CODE", str(0 if final_outcome == "CANARY_PASS_LOCAL_CONSUMPTION" else 2) + "\n")
    write_text_atomic(run_dir / ".DONE", "")
    write_text_atomic(artifact_root / "LATEST", run_id + "\n")
    write_text_atomic(
        artifact_root / "EVIDENCE_MANIFEST_SHA256",
        sha256_file(evidence_manifest) + "\n",
    )
    return 0 if final_outcome == "CANARY_PASS_LOCAL_CONSUMPTION" else 2


def failure_worker(run_dir: Path, run_id: str, exc: Exception) -> int:
    try:
        receipt = make_receipt(
            result_kind="canary_suite_run",
            outcome="PROTOCOL_VIOLATION",
            subject_identity={"run_id": run_id, "run_dir": str(run_dir)},
            verified_scope={"completed": False, "failure_stage": "suite_worker"},
            granted_effects=["blocks_all_canary_promotion"],
            details={
                "schema_version": "zmd_w0_unary_canary_suite_receipt_v1",
                "status": "FAIL",
                "error": str(exc),
                "failed_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
        dump_receipt(receipt, run_dir / "SUITE_RECEIPT.json")
        write_text_atomic(run_dir / "EXIT_CODE", "1\n")
        write_text_atomic(run_dir / ".DONE", "")
    except Exception:
        pass
    return 1


def make_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"w0-unary-canary-{timestamp}-{git('rev-parse', '--short=10', 'HEAD')}"


def launch_detached(run_dir: Path, run_id: str) -> int:
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "full.log"
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--run-dir",
                str(run_dir),
                "--run-id",
                run_id,
            ],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    write_text_atomic(run_dir / "PID", str(process.pid) + "\n")
    launch_receipt = make_receipt(
        result_kind="canary_suite_launch",
        outcome="LAUNCHED",
        subject_identity={
            "run_id": run_id,
            "run_dir": str(run_dir.relative_to(ROOT)),
            "pid": process.pid,
            "implementation_head": git("rev-parse", "HEAD"),
        },
        verified_scope={
            "process_started": True,
            "start_new_session": True,
            "result_available": False,
        },
        granted_effects=["permits_monitoring_only_until_DONE_and_SUITE_RECEIPT_exist"],
        details={
            "schema_version": "zmd_w0_unary_canary_launch_receipt_v1",
            "status": "RUNNING",
            "log_path": str(log_path.relative_to(ROOT)),
        },
    )
    text = dump_receipt(launch_receipt, run_dir / "LAUNCH_RECEIPT.json")
    print(text, end="")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--detach", action="store_true")
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    manifest = read_json(MANIFEST_PATH)
    run_id = str(args.run_id or make_run_id())
    run_dir = (
        args.run_dir.resolve()
        if args.run_dir is not None
        else expected_artifact_root(manifest) / run_id
    )
    ensure_run_dir(run_dir, manifest)

    if args.worker:
        try:
            return worker(run_dir, run_id)
        except (
            SuiteError,
            ReceiptContractError,
            OSError,
            KeyError,
            TypeError,
            ValueError,
            IndexError,
            subprocess.SubprocessError,
        ) as exc:
            return failure_worker(run_dir, run_id, exc)
    if args.detach:
        return launch_detached(run_dir, run_id)
    try:
        return worker(run_dir, run_id)
    except (
        SuiteError,
        ReceiptContractError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        IndexError,
        subprocess.SubprocessError,
    ) as exc:
        return failure_worker(run_dir, run_id, exc)


if __name__ == "__main__":
    raise SystemExit(main())
