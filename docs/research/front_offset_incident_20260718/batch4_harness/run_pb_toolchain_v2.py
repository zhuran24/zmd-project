"""Run the pinned RoundingSat -> VeriPB chain for a translation-gated PB model.

The runner is no-overwrite and records exact argv, tool identities, stdout,
stderr, proof hashes, and the final claim boundary.  VeriPB is invoked only
after RoundingSat reports a complete UNSAT result and emits a non-empty proof.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from typing import Any, Sequence


SEMANTICS = "reconstructed_new_baseline"
PROJECT_ROOT = Path(__file__).resolve().parents[4]


class ToolchainError(RuntimeError):
    """Raised when the proof toolchain cannot be run under the closed contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(project_root.resolve()))
    except ValueError:
        return str(resolved)


def _file_record(path: Path, project_root: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"provenance file is missing: {resolved}")
    return {
        "path": _display_path(resolved, project_root),
        "sha256": _sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _resolve_recorded_path(value: Any, project_root: Path, field: str) -> Path:
    if not isinstance(value, Mapping):
        raise ToolchainError(f"{field} must be an object")
    raw_path = value.get("path")
    if type(raw_path) is not str or not raw_path:
        raise ToolchainError(f"{field}.path must be a non-empty string")
    path = Path(raw_path)
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def _validate_file_record(
    value: Any,
    *,
    expected_path: Path,
    project_root: Path,
    field: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ToolchainError(f"{field} must be an object")
    expected = _file_record(expected_path, project_root)
    if dict(value) != expected:
        raise ToolchainError(f"{field} does not match the current pinned file")
    return expected


def _validate_git_snapshot(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "head",
        "tracked_dirty",
        "tracked_diff_sha256",
        "tracked_diff_size_bytes",
    }:
        raise ToolchainError(f"{field} must be a closed Git snapshot object")
    head = value.get("head")
    diff_hash = value.get("tracked_diff_sha256")
    diff_size = value.get("tracked_diff_size_bytes")
    dirty = value.get("tracked_dirty")
    if type(head) is not str or re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise ToolchainError(f"{field}.head must be a full lowercase Git object id")
    if type(diff_hash) is not str or re.fullmatch(r"[0-9a-f]{64}", diff_hash) is None:
        raise ToolchainError(f"{field}.tracked_diff_sha256 must be a full lowercase SHA-256")
    if type(diff_size) is not int or diff_size < 0:
        raise ToolchainError(f"{field}.tracked_diff_size_bytes must be a non-negative exact integer")
    if type(dirty) is not bool or dirty is not (diff_size > 0):
        raise ToolchainError(f"{field}.tracked_dirty disagrees with the tracked diff size")
    return dict(value)


def _git_snapshot(project_root: Path) -> dict[str, Any]:
    revision = _git_revision(project_root)
    diff_result = subprocess.run(
        [
            "git",
            "-C",
            str(project_root),
            "diff",
            "--binary",
            "--full-index",
            "--no-ext-diff",
            "HEAD",
            "--",
        ],
        check=True,
        capture_output=True,
    )
    tracked_diff = diff_result.stdout
    return {
        "head": revision,
        "tracked_dirty": bool(tracked_diff),
        "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        "tracked_diff_size_bytes": len(tracked_diff),
    }


def _json(path: Path, field: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing {field}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ToolchainError(f"{field} must be a JSON object")
    return payload


def _git_revision(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ToolchainError(f"invalid Git revision from {repo}: {revision!r}")
    return revision


def _run(command: list[str], wall_timeout: float) -> dict[str, Any]:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=wall_timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    return {
        "command": command,
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
    }


def _exclusive_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _exclusive_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _solver_status(stdout: str, stderr: str, timed_out: bool) -> str:
    if timed_out:
        return "EXTERNAL_TIMEOUT"
    lines = {line.strip() for line in f"{stdout}\n{stderr}".splitlines()}
    if "s UNSATISFIABLE" in lines:
        return "UNSATISFIABLE"
    if "s SATISFIABLE" in lines:
        return "SATISFIABLE"
    if "s UNKNOWN" in lines:
        return "UNKNOWN"
    if "s TIMELIMIT" in lines:
        return "TIME_LIMIT"
    return "NO_RESULT"


def _verifier_status(stdout: str, stderr: str, exit_code: int | None) -> str:
    lines = {line.strip() for line in f"{stdout}\n{stderr}".splitlines()}
    if exit_code == 0 and "s VERIFIED UNSATISFIABLE" in lines:
        return "VERIFIED_UNSATISFIABLE"
    return "VERIFICATION_FAILED"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opb", type=Path, required=True)
    parser.add_argument("--meta", type=Path, required=True)
    parser.add_argument("--translation-gate", type=Path, required=True)
    parser.add_argument("--roundingsat", type=Path, required=True)
    parser.add_argument("--roundingsat-repo", type=Path, required=True)
    parser.add_argument("--veripb", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--solver-time-limit", type=float, required=True)
    parser.add_argument("--wall-timeout", type=float, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.solver_time_limit <= 0 or args.wall_timeout <= args.solver_time_limit:
        raise ToolchainError("wall timeout must be greater than the positive solver time limit")
    opb = args.opb.resolve()
    meta_path = args.meta.resolve()
    gate_path = args.translation_gate.resolve()
    roundingsat = args.roundingsat.resolve()
    roundingsat_repo = args.roundingsat_repo.resolve()
    veripb = args.veripb.resolve()
    output_dir = args.output_dir.resolve()
    proof_path = output_dir / "roundingsat.proof.pbp"
    solver_stdout_path = output_dir / "roundingsat.stdout.txt"
    solver_stderr_path = output_dir / "roundingsat.stderr.txt"
    verifier_stdout_path = output_dir / "veripb.stdout.txt"
    verifier_stderr_path = output_dir / "veripb.stderr.txt"
    record_path = output_dir / "toolchain_record.json"
    planned = [
        proof_path,
        solver_stdout_path,
        solver_stderr_path,
        verifier_stdout_path,
        verifier_stderr_path,
        record_path,
    ]
    existing = [str(path) for path in planned if path.exists()]
    if existing:
        raise FileExistsError("refusing to overwrite proof-toolchain output(s): " + ", ".join(existing))
    if not opb.is_file() or not roundingsat.is_file() or not veripb.is_file():
        raise FileNotFoundError("OPB, RoundingSat, and VeriPB paths must all be files")

    meta = _json(meta_path, "encoder metadata")
    gate = _json(gate_path, "translation gate")
    if meta.get("semantics") != SEMANTICS or gate.get("semantics") != SEMANTICS:
        raise ToolchainError("encoder metadata and gate must use reconstructed_new_baseline")
    if gate.get("status") != "PASS" or not all(gate.get("checks", {}).values()):
        raise ToolchainError("translation gate is not a complete PASS")
    expected_opb_hash = meta.get("outputs", {}).get("opb_sha256")
    actual_opb_hash = _sha256(opb)
    if actual_opb_hash != expected_opb_hash:
        raise ToolchainError("OPB hash does not match encoder metadata")

    encoder_path = Path(__file__).with_name("pb_encoder_v2.py")
    gate_source_path = Path(__file__).with_name("verify_pb_translation_v2.py")
    encoder_source = _validate_file_record(
        meta.get("harness_source"),
        expected_path=encoder_path,
        project_root=PROJECT_ROOT,
        field="metadata.harness_source",
    )
    if gate.get("encoder_source") != encoder_source:
        raise ToolchainError("translation gate encoder source does not match metadata")
    gate_source = _validate_file_record(
        gate.get("gate_source"),
        expected_path=gate_source_path,
        project_root=PROJECT_ROOT,
        field="translation_gate.gate_source",
    )
    encoder_git_snapshot = _validate_git_snapshot(
        meta.get("git_snapshot"), "metadata.git_snapshot"
    )
    if meta.get("git_revision") != encoder_git_snapshot["head"]:
        raise ToolchainError("metadata git_revision disagrees with its Git snapshot")
    if gate.get("encoder_git_snapshot") != encoder_git_snapshot:
        raise ToolchainError("translation gate encoder Git snapshot does not match metadata")
    gate_git_snapshot = _validate_git_snapshot(
        gate.get("git_snapshot"), "translation_gate.git_snapshot"
    )

    gate_inputs_raw = gate.get("translation_inputs")
    if not isinstance(gate_inputs_raw, Mapping) or set(gate_inputs_raw) != {
        "meta",
        "opb",
        "var_map",
    }:
        raise ToolchainError("translation gate inputs do not form the closed input set")
    var_map_path = _resolve_recorded_path(
        gate_inputs_raw["var_map"], PROJECT_ROOT, "translation_gate.translation_inputs.var_map"
    )
    gate_inputs = {
        "meta": _validate_file_record(
            gate_inputs_raw["meta"],
            expected_path=meta_path,
            project_root=PROJECT_ROOT,
            field="translation_gate.translation_inputs.meta",
        ),
        "opb": _validate_file_record(
            gate_inputs_raw["opb"],
            expected_path=opb,
            project_root=PROJECT_ROOT,
            field="translation_gate.translation_inputs.opb",
        ),
        "var_map": _validate_file_record(
            gate_inputs_raw["var_map"],
            expected_path=var_map_path,
            project_root=PROJECT_ROOT,
            field="translation_gate.translation_inputs.var_map",
        ),
    }
    runner_source = _file_record(Path(__file__), PROJECT_ROOT)
    runner_git_snapshot = _git_snapshot(PROJECT_ROOT)

    output_dir.mkdir(parents=True, exist_ok=True)
    solver_command = [
        str(roundingsat),
        f"--proof-log={proof_path}",
        f"--time-limit={args.solver_time_limit:g}",
        str(opb),
    ]
    solver = _run(solver_command, args.wall_timeout)
    _exclusive_text(solver_stdout_path, solver["stdout"])
    _exclusive_text(solver_stderr_path, solver["stderr"])
    solver_status = _solver_status(solver["stdout"], solver["stderr"], solver["timed_out"])

    verifier: dict[str, Any] | None = None
    verifier_status = "NOT_RUN_NO_COMPLETE_UNSAT_PROOF"
    if solver_status == "UNSATISFIABLE" and proof_path.is_file() and proof_path.stat().st_size > 0:
        verifier_command = [str(veripb), "--opb", "--stats", str(opb), str(proof_path)]
        verifier = _run(verifier_command, args.wall_timeout)
        _exclusive_text(verifier_stdout_path, verifier["stdout"])
        _exclusive_text(verifier_stderr_path, verifier["stderr"])
        verifier_status = _verifier_status(
            verifier["stdout"], verifier["stderr"], verifier["exit_code"]
        )

    proof_exists = proof_path.is_file()
    verified = verifier_status == "VERIFIED_UNSATISFIABLE"
    record = {
        "schema_version": "front_clear_pb_toolchain_run_v2",
        "semantics": SEMANTICS,
        "argv": list(sys.argv) if argv is None else [str(Path(__file__).resolve()), *map(str, argv)],
        "execution": {
            "solver_time_limit_seconds": args.solver_time_limit,
            "wall_timeout_seconds": args.wall_timeout,
            "random_seed": None,
            "workers": None,
        },
        "inputs": {
            "opb": gate_inputs["opb"],
            "meta": gate_inputs["meta"],
            "var_map": gate_inputs["var_map"],
            "translation_gate": _file_record(gate_path, PROJECT_ROOT),
        },
        "sources": {
            "runner": runner_source,
            "gate": gate_source,
            "encoder": encoder_source,
        },
        "git_snapshots": {
            "runner": runner_git_snapshot,
            "gate": gate_git_snapshot,
            "encoder": encoder_git_snapshot,
        },
        "tools": {
            "roundingsat": {
                "path": str(roundingsat),
                "sha256": _sha256(roundingsat),
                "git_revision": _git_revision(roundingsat_repo),
            },
            "veripb": {"path": str(veripb), "sha256": _sha256(veripb), "version": "3.0.2"},
        },
        "solver": {
            "command": solver["command"],
            "exit_code": solver["exit_code"],
            "timed_out": solver["timed_out"],
            "status": solver_status,
            "stdout_sha256": _sha256(solver_stdout_path),
            "stderr_sha256": _sha256(solver_stderr_path),
        },
        "proof": {
            "path": str(proof_path),
            "exists": proof_exists,
            "complete": solver_status == "UNSATISFIABLE",
            "size_bytes": proof_path.stat().st_size if proof_exists else None,
            "sha256": _sha256(proof_path) if proof_exists else None,
        },
        "verifier": (
            {
                "command": verifier["command"],
                "exit_code": verifier["exit_code"],
                "timed_out": verifier["timed_out"],
                "status": verifier_status,
                "stdout_sha256": _sha256(verifier_stdout_path),
                "stderr_sha256": _sha256(verifier_stderr_path),
            }
            if verifier is not None
            else {"status": verifier_status}
        ),
        "translation_gate_status": gate["status"],
        "claim": (
            "machine_verified_unsat_for_translation_gated_relaxation"
            if verified
            else "none"
        ),
    }
    _exclusive_json(record_path, record)
    print(
        json.dumps(
            {
                "solver_status": solver_status,
                "verifier_status": verifier_status,
                "claim": record["claim"],
                "record": str(record_path),
            },
            sort_keys=True,
        )
    )
    if solver_status == "UNSATISFIABLE":
        return 0 if verified else 1
    return 0 if solver_status in {"SATISFIABLE", "UNKNOWN", "TIME_LIMIT", "EXTERNAL_TIMEOUT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
