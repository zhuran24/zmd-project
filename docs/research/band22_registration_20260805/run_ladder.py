#!/home/zhuran24/zmd-pj/.venv/bin/python
"""Run the band22 v2 intake, fixed-master, and official-gate rungs serially."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone
import uuid

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT_ROOT = ROOT / ".artifacts" / "band22_registration_20260805"
GUARDED = HERE / "run_guarded.sh"
R2 = ROOT / ".artifacts/band22_strict_redesign_replies_20260805/r2_strict_empty_v2/band22_strict_empty_v2_delivery/band22_strict_witness_v2.json"
TAG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}\Z")
RUNGS = ((1, "intake", "INTAKE_ACCEPTED"), (2, "master", "MASTER_FEASIBLE"), (3, "gates", None))

def _utc(compact: bool = False) -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%SZ") if compact else now.isoformat(timespec="seconds")

def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()

def _write_receipt(path: Path, payload: dict[str, object]) -> None:
    data = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solution", type=Path, default=R2)
    parser.add_argument("--tag", default="v2", help="strict leaf token, at most 32 characters")
    parser.add_argument("--max-rung", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--master-validation-seconds", type=float, default=600.0)
    parser.add_argument("--binding-seconds", type=float, default=600.0)
    parser.add_argument("--routing-seconds", type=float, default=600.0)
    parser.add_argument("--max-gate-wall-seconds", type=float, default=20400.0)
    parser.add_argument("--outer-seconds", type=int, default=21600)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--binding-alt-cap", type=int, default=0)
    return parser

def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if TAG_RE.fullmatch(args.tag) is None:
        raise SystemExit("--tag is not a strict leaf token")
    budgets = (args.master_validation_seconds, args.binding_seconds, args.routing_seconds, args.max_gate_wall_seconds)
    if any(value <= 0 for value in budgets) or args.workers <= 0 or args.binding_alt_cap < 0:
        raise SystemExit("budgets/workers must be positive and --binding-alt-cap non-negative")
    if int(args.max_gate_wall_seconds) + 600 > args.outer_seconds:
        raise SystemExit("--outer-seconds must leave at least 600s after the gate wall cap")

    solution = args.solution.resolve(strict=True)
    if not solution.is_file():
        raise SystemExit("--solution must be a regular file")
    witness_sha = _sha256(solution)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    ladder_id = uuid.uuid4().hex
    ladder_dir = OUT_ROOT / f"ladder-{args.tag}-{_utc(True)}-{ladder_id[:8]}"
    ladder_dir.mkdir(mode=0o700, exist_ok=False)
    started = _utc()
    rung_records: list[dict[str, object]] = []
    exit_code, stop_reason = 0, "max_rung_reached"

    for ordinal, stage, continue_verdict in RUNGS:
        if ordinal > args.max_rung:
            break
        if _sha256(solution) != witness_sha:
            exit_code, stop_reason = 1, "WITNESS_BYTES_DRIFTED"
            break
        rung_parent = ladder_dir / f"rung-{ordinal}-{stage}"
        rung_parent.mkdir(mode=0o700, exist_ok=False)
        rung_tag = f"{args.tag}-r{ordinal}-{ladder_id[:8]}"
        command = [str(GUARDED), "--tag", rung_tag, "--outer-seconds", str(args.outer_seconds),
                   "--memory-max", "24G", "--", "--solution", str(solution),
                   "--out-dir", str(rung_parent), "--stop-after", stage,
                   "--master-validation-seconds", str(args.master_validation_seconds),
                   "--binding-seconds", str(args.binding_seconds), "--routing-seconds", str(args.routing_seconds),
                   "--max-gate-wall-seconds", str(args.max_gate_wall_seconds), "--workers", str(args.workers),
                   "--binding-alt-cap", str(args.binding_alt_cap)]
        env = {key: value for key, value in os.environ.items() if not key.startswith("EXACT_") and key not in {"PYTHONPATH", "PYTHONHOME"}}
        wrapper_started = os.times().elapsed
        with (rung_parent / "guarded.log").open("xb") as log:
            completed = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, check=False)
        run_dirs = [path for path in rung_parent.iterdir() if path.is_dir()]
        done = run_dirs[0] / f"{rung_tag}.DONE" if len(run_dirs) == 1 else None
        record: dict[str, object] = {"ordinal": ordinal, "name": stage, "attempted": True,
                                    "wrapper_exit_code": completed.returncode, "wrapper_wall_seconds": round(os.times().elapsed - wrapper_started, 3),
                                    "run_dir": str(run_dirs[0]) if len(run_dirs) == 1 else None}
        try:
            if done is None or not done.is_file():
                raise ValueError("exactly one run directory with a terminal receipt is required")
            receipt = json.loads(done.read_text(encoding="utf-8"))
            if not isinstance(receipt, dict):
                raise ValueError("terminal receipt is not a JSON object")
            result = Path(str(receipt.get("result_path", "")))
            if receipt.get("tag") != rung_tag or result.parent != run_dirs[0]:
                raise ValueError("terminal receipt identity does not match its rung")
            if _sha256(result) != receipt.get("result_sha256"):
                raise ValueError("terminal result hash mismatch")
            driver_result = json.loads(result.read_text(encoding="utf-8"))
            driver_witness, driver_provenance = ((driver_result.get("witness"), driver_result.get("provenance")) if isinstance(driver_result, dict) else (None, None))
            if (not isinstance(driver_witness, dict) or not isinstance(driver_provenance, dict) or driver_witness.get("sha256") != witness_sha or driver_provenance.get("witness_sha256") != witness_sha or Path(str(driver_witness.get("path", ""))).resolve() != solution or _sha256(solution) != witness_sha):
                raise ValueError("driver witness identity differs from the immutable ladder pin")
            record.update({"driver_receipt": str(done), "verdict": receipt.get("verdict"),
                           "censored": receipt.get("censored"),
                           "censored_stage": receipt.get("censored_stage"),
                           "censored_at_seconds": receipt.get("censored_at_seconds"),
                           "total_wall_seconds": receipt.get("total_wall_seconds"),
                           "vm_hwm_mb": receipt.get("vm_hwm_mb")})
            verdict = str(receipt.get("verdict"))
            violation = (completed.returncode != receipt.get("exit_code") or "CONTRACT_VIOLATION" in verdict or verdict in {"HARNESS_ERROR", "INVALIDATED_SIDE_EFFECT_AUDIT"})
            should_continue = (not violation and receipt.get("censored") is False and
                               completed.returncode == 0 and verdict == continue_verdict)
            record["continued"] = bool(should_continue)
            rung_records.append(record)
            if ordinal == 3:
                exit_code = 1 if violation else 0
                stop_reason = "contract_violation" if violation else "gates_terminal"
                break
            if not should_continue:
                exit_code = 1 if violation else 0
                stop_reason = "contract_violation" if violation else "terminal_or_censored"
                break
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            record.update({"verdict": None, "censored": None, "continued": False,
                           "contract_error": f"{type(exc).__name__}: {exc}"})
            rung_records.append(record)
            exit_code, stop_reason = 1, "missing_or_invalid_terminal_receipt"
            break

    attempted = {int(record["ordinal"]) for record in rung_records}
    for ordinal, stage, _expected in RUNGS:
        if ordinal not in attempted:
            rung_records.append({"ordinal": ordinal, "name": stage, "attempted": False,
                                 "reason": "prior_rung_not_admitted_or_max_rung"})
    peak = max((float(record["vm_hwm_mb"]) for record in rung_records
                if isinstance(record.get("vm_hwm_mb"), (int, float))), default=None)
    last = next((record for record in reversed(rung_records) if record.get("attempted") is True), {})
    payload: dict[str, object] = {
        "receipt": "band22_registration_ladder", "schema_version": "band22-registration-ladder/1",
        "ladder_uuid": ladder_id, "tag": args.tag, "started_utc": started, "finished_utc": _utc(),
        "research_only": True, "witness": {"path": str(solution), "sha256": witness_sha,
        "role": "R2_primary" if solution == R2.resolve(strict=False) else "explicit_single_witness",
        "selection_policy": "one immutable witness for every rung; R1 is never automatic or spliced"},
        "budgets": {"master_validation_seconds": args.master_validation_seconds,
        "binding_seconds": args.binding_seconds, "routing_seconds": args.routing_seconds,
        "max_gate_wall_seconds": args.max_gate_wall_seconds, "outer_seconds": args.outer_seconds,
        "workers": args.workers, "binding_alt_cap": args.binding_alt_cap,
        "memory_max": "24G", "memory_swap_max": "0"}, "rungs": rung_records,
        "peak_vm_hwm_mb": peak, "terminal": {"reason": stop_reason, "exit_code": exit_code,
        "verdict": last.get("verdict"), "censored": last.get("censored")},
        "censoring_contract": "a censored rung proves neither direction and stops the ladder; no retry follows",
    }
    receipt_path = ladder_dir / "LADDER_RECEIPT.json"
    _write_receipt(receipt_path, payload)
    print(receipt_path)
    return exit_code
if __name__ == "__main__":
    raise SystemExit(main())
