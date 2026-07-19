"""Run the provenance-closed R1 residual-band RoundingSat -> VeriPB chain.

This research runner is deliberately target-specific.  It accepts only the
R1 strict-upper-bound encoder/gate schemas, refuses to overwrite any planned
artifact, monitors proof growth and free disk space, and records enough state
to distinguish an emitted proof from a complete, VeriPB-verified proof.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from typing import Any


SCHEMA_VERSION = "r1_upper_bound_pb_toolchain_run_v1"
SEMANTICS = "r1_strict_upper_bound_1326_34_research"
MODEL_SCHEMA = "r1_upper_bound_pb_v1"
METADATA_SCHEMA = "r1_upper_bound_pb_metadata_v1"
VAR_MAP_SCHEMA = "r1_upper_bound_pb_var_map_v1"
ESTIMATE_SCHEMA = "r1_upper_bound_pb_estimate_v1"
GATE_SCHEMA = "r1_upper_bound_pb_translation_gate_v1"
ENCODER_NAME = "r1_upper_bound_pb_encoder_v1.py"
GATE_NAME = "verify_r1_upper_bound_pb_translation_v1.py"
RUNNER_NAME = "run_r1_upper_bound_pb_toolchain_v1.py"
FORMAL_PROOF_LIMIT_BYTES = 5_000_000_000
FORMAL_MIN_FREE_BYTES = 10_737_418_240
EXPECTED_MEMORY_HIGH = 34 * 1024**3
EXPECTED_MEMORY_MAX = 38 * 1024**3
EXPECTED_SWAP_MAX = 16 * 1024**3
EXPECTED_OOM_POLICY = "continue"
PROJECT_ROOT = Path(__file__).resolve().parents[4]

REQUIRED_GATE_CHECKS = frozenset(
    {
        "strict_bundle_closed_and_hashed",
        "encoder_provenance_match",
        "translation_inputs_closed_and_hashed",
        "metadata_reconstruction_match",
        "estimate_reconstruction_match",
        "variable_map_dense",
        "variable_map_exact",
        "opb_header_exact",
        "constraint_multiset_exact",
        "boundary_patterns_exhaustive",
        "lex_better_partition_exact",
        "two_stage_theorem_coverage_exact",
        "corpus_exhaustive_unsat",
        "semantic_canaries_pass",
    }
)
INPUT_PATHS = {
    "problem_instance": "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json",
    "problem_instance_schema": (
        "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.schema.json"
    ),
    "problem_md": "docs/research/cleanroom_rederivation_20260718/strict/external/problem.md",
    "sha256s": "docs/research/cleanroom_rederivation_20260718/strict/external/SHA256SUMS",
}
EVIDENCE_PATHS = {
    "r1_strict_response": "docs/research/cleanroom_rederivation_20260718/04_r1_strict_response_gpt_pro_verbatim.md",
    "r1_strict_judgment": "docs/research/cleanroom_rederivation_20260718/05_r1_strict_judgment_20260720.md",
    "independent_recomputation": "docs/research/cleanroom_rederivation_20260718/verify_r1_strict_bounds.py",
}


class ToolchainError(RuntimeError):
    """Raised when a fail-closed toolchain invariant is not satisfied."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _file_record(path: Path, project_root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ToolchainError(f"not a provenance file: {resolved}")
    return {
        "path": _display_path(resolved, project_root),
        "sha256": _sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _strict_json(path: Path, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ToolchainError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ToolchainError(f"{label} contains non-finite number {value}")

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ToolchainError(f"cannot load {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ToolchainError(f"{label} must be a JSON object")
    return payload


def _exclusive_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _exclusive_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _git_snapshot(repo: Path) -> dict[str, Any]:
    def run(*arguments: str, binary: bool = False) -> str | bytes:
        completed = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=True,
            capture_output=True,
        )
        if binary:
            return completed.stdout
        return completed.stdout.decode("utf-8", errors="strict").rstrip("\n")

    head = str(run("rev-parse", "HEAD"))
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise ToolchainError(f"invalid Git revision for {repo}: {head!r}")
    diff = run("diff", "--binary", "--full-index", "--no-ext-diff", "HEAD", "--", binary=True)
    assert isinstance(diff, bytes)
    status = run("status", "--porcelain=v1", "-z", "--untracked-files=normal", binary=True)
    assert isinstance(status, bytes)
    return {
        "head": head,
        "tracked_dirty": bool(diff),
        "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
        "tracked_diff_size_bytes": len(diff),
        "status_dirty": bool(status),
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "status_size_bytes": len(status),
    }


def _validate_git_snapshot(value: Any, label: str) -> dict[str, Any]:
    expected_keys = {
        "head",
        "tracked_dirty",
        "tracked_diff_sha256",
        "tracked_diff_size_bytes",
        "status_dirty",
        "status_sha256",
        "status_size_bytes",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise ToolchainError(f"{label} is not a closed Git snapshot")
    head = value["head"]
    digest = value["tracked_diff_sha256"]
    size = value["tracked_diff_size_bytes"]
    dirty = value["tracked_dirty"]
    status_digest = value["status_sha256"]
    status_size = value["status_size_bytes"]
    status_dirty = value["status_dirty"]
    if type(head) is not str or re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise ToolchainError(f"{label}.head is invalid")
    if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ToolchainError(f"{label}.tracked_diff_sha256 is invalid")
    if type(size) is not int or size < 0 or type(dirty) is not bool or dirty != (size > 0):
        raise ToolchainError(f"{label} dirty/size contract is invalid")
    if type(status_digest) is not str or re.fullmatch(r"[0-9a-f]{64}", status_digest) is None:
        raise ToolchainError(f"{label}.status_sha256 is invalid")
    if (
        type(status_size) is not int
        or status_size < 0
        or type(status_dirty) is not bool
        or status_dirty != (status_size > 0)
    ):
        raise ToolchainError(f"{label} status dirty/size contract is invalid")
    return dict(value)


def _validate_file_record(value: Any, expected: Path, root: Path, label: str) -> dict[str, Any]:
    current = _file_record(expected, root)
    if not isinstance(value, Mapping) or dict(value) != current:
        raise ToolchainError(f"{label} does not match the current file")
    return current


def _validate_record_map(value: Any, expected: Mapping[str, str], root: Path, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise ToolchainError(f"{label} is not the closed expected file set")
    return {
        key: _validate_file_record(value[key], root / relative, root, f"{label}.{key}")
        for key, relative in expected.items()
    }


def _repo_identity(repo: Path) -> dict[str, Any]:
    def run(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.rstrip("\n")

    revision = run("rev-parse", "HEAD")
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ToolchainError("RoundingSat repository returned an invalid revision")
    status = run("status", "--porcelain=v1", "--untracked-files=normal")
    return {
        "revision": revision,
        "branch": run("branch", "--show-current"),
        "dirty": bool(status),
        "status_porcelain_v1": status.splitlines(),
    }


def _read_cgroup_file(cgroup_dir: Path, name: str) -> str | None:
    path = cgroup_dir / name
    try:
        return path.read_text(encoding="ascii").strip()
    except OSError:
        return None


def _integer_map(raw: str | None) -> dict[str, int] | None:
    if raw is None:
        return None
    result: dict[str, int] = {}
    try:
        for line in raw.splitlines():
            key, value = line.split()
            result[key] = int(value)
    except (ValueError, TypeError):
        return None
    return result


def _cgroup_state(expected_unit: str | None, require_contract: bool) -> dict[str, Any]:
    raw = Path("/proc/self/cgroup").read_text(encoding="ascii").strip()
    unified = [line.split("::", 1)[1] for line in raw.splitlines() if "::" in line]
    relative = unified[0] if len(unified) == 1 else None
    cgroup_dir = Path("/sys/fs/cgroup") / relative.lstrip("/") if relative else None
    values = {
        name: _read_cgroup_file(cgroup_dir, name) if cgroup_dir is not None else None
        for name in ("memory.high", "memory.max", "memory.swap.max", "memory.current", "memory.peak")
    }
    events = _integer_map(
        _read_cgroup_file(cgroup_dir, "memory.events") if cgroup_dir is not None else None
    )
    policy_argv: list[str] | None = None
    policy_exit: int | None = None
    policy_stdout = ""
    policy_stderr = ""
    if expected_unit:
        policy_argv = [
            "systemctl",
            "--user",
            "show",
            expected_unit,
            "--property=OOMPolicy",
            "--value",
        ]
        completed = subprocess.run(policy_argv, capture_output=True, text=True, timeout=10)
        policy_exit = completed.returncode
        policy_stdout = completed.stdout
        policy_stderr = completed.stderr
    checks = {
        "unified_cgroup_found": relative is not None,
        "expected_unit_in_cgroup_path": bool(expected_unit and relative and expected_unit in relative),
        "memory_high_exact": values["memory.high"] == str(EXPECTED_MEMORY_HIGH),
        "memory_max_exact": values["memory.max"] == str(EXPECTED_MEMORY_MAX),
        "memory_swap_max_exact": values["memory.swap.max"] == str(EXPECTED_SWAP_MAX),
        "oom_policy_exact": policy_exit == 0 and policy_stdout.strip() == EXPECTED_OOM_POLICY,
    }
    if require_contract and (not expected_unit or not all(checks.values())):
        raise ToolchainError(f"required cgroup contract is not exact: {checks}")
    return {
        "required": require_contract,
        "expected_systemd_unit": expected_unit,
        "proc_self_cgroup": raw.splitlines(),
        "cgroup_path": relative,
        "values": values,
        "memory_events": events,
        "oom_policy_query": {
            "argv": policy_argv,
            "exit_code": policy_exit,
            "stdout": policy_stdout,
            "stderr": policy_stderr,
        },
        "checks": checks,
        "contract_pass": all(checks.values()),
    }


def _free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def _sample(resources: list[dict[str, Any]], output_dir: Path, phase: str, proof: Path | None) -> None:
    resources.append(
        {
            "timestamp_utc": _utc_now(),
            "phase": phase,
            "free_bytes": _free_bytes(output_dir),
            "proof_size_bytes": proof.stat().st_size if proof is not None and proof.is_file() else None,
        }
    )


def _terminate_group(process: subprocess.Popen[Any]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def _run_child(
    command: list[str],
    *,
    stdout_path: Path,
    stderr_path: Path,
    wall_timeout: float,
    monitor_interval: float,
    output_dir: Path,
    resources: list[dict[str, Any]],
    phase: str,
    min_free_bytes: int,
    proof_path: Path | None = None,
    proof_limit_bytes: int | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    termination_reason: str | None = None
    spawn_error: str | None = None
    with stdout_path.open("x", encoding="utf-8", newline="\n") as stdout_handle, stderr_path.open(
        "x", encoding="utf-8", newline="\n"
    ) as stderr_handle:
        try:
            process = subprocess.Popen(
                command,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                start_new_session=True,
            )
        except OSError as exc:
            process = None
            spawn_error = f"{type(exc).__name__}: {exc}"
        if process is not None:
            while process.poll() is None:
                _sample(resources, output_dir, phase, proof_path)
                elapsed = time.monotonic() - started
                current_free = resources[-1]["free_bytes"]
                current_proof = resources[-1]["proof_size_bytes"]
                if elapsed > wall_timeout:
                    termination_reason = "wall_timeout"
                elif current_free < min_free_bytes:
                    termination_reason = "disk_free_below_minimum"
                elif (
                    proof_limit_bytes is not None
                    and current_proof is not None
                    and current_proof > proof_limit_bytes
                ):
                    termination_reason = "proof_size_limit_exceeded"
                if termination_reason is not None:
                    _terminate_group(process)
                    break
                time.sleep(min(monitor_interval, max(0.01, wall_timeout - elapsed)))
            exit_code = process.wait()
            _sample(resources, output_dir, f"{phase}_complete", proof_path)
            completion_free = resources[-1]["free_bytes"]
            completion_proof = resources[-1]["proof_size_bytes"]
            if termination_reason is None and completion_free < min_free_bytes:
                termination_reason = "disk_free_below_minimum_at_completion"
            elif (
                termination_reason is None
                and proof_limit_bytes is not None
                and completion_proof is not None
                and completion_proof > proof_limit_bytes
            ):
                termination_reason = "proof_size_limit_exceeded_at_completion"
        else:
            exit_code = None
    return {
        "argv": command,
        "exit_code": exit_code,
        "timed_out": termination_reason == "wall_timeout",
        "termination_reason": termination_reason,
        "spawn_error": spawn_error,
        "elapsed_seconds": time.monotonic() - started,
        "stdout": _file_record(stdout_path, PROJECT_ROOT),
        "stderr": _file_record(stderr_path, PROJECT_ROOT),
    }


def _status_lines(*paths: Path) -> list[str]:
    result: list[str] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("s "):
                result.append(stripped)
    return result


def _proof_tail(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        return {"nonempty": False, "conclusion_line": None, "end_line": None, "complete": False}
    with path.open("rb") as handle:
        handle.seek(max(0, path.stat().st_size - 65_536))
        tail = handle.read().decode("utf-8", errors="replace")
    lines = [line.rstrip("\r") for line in tail.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    conclusion = lines[-2] if len(lines) >= 2 else None
    end = lines[-1] if lines else None
    complete = (
        conclusion is not None
        and re.fullmatch(r"conclusion UNSAT : [1-9][0-9]*", conclusion) is not None
        and end == "end pseudo-Boolean proof"
    )
    return {"nonempty": True, "conclusion_line": conclusion, "end_line": end, "complete": complete}


def _verifier_error_markers(*paths: Path) -> list[str]:
    markers: list[str] = []
    pattern = re.compile(r"(?:^|\b)(?:error|fatal|exception|traceback|verification failed|invalid proof)(?:\b|:)", re.I)
    for path in paths:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if pattern.search(line):
                markers.append(line.strip())
    return markers


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--opb", type=Path, required=True)
    parser.add_argument("--meta", type=Path, required=True)
    parser.add_argument("--var-map", type=Path, required=True)
    parser.add_argument("--estimate", type=Path, required=True)
    parser.add_argument("--translation-gate", type=Path, required=True)
    parser.add_argument("--roundingsat", type=Path, required=True)
    parser.add_argument("--roundingsat-repo", type=Path, required=True)
    parser.add_argument("--veripb", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--solver-time-limit", type=float, required=True)
    parser.add_argument("--solver-wall-timeout", type=float, required=True)
    parser.add_argument("--verifier-wall-timeout", type=float, required=True)
    parser.add_argument("--proof-limit-bytes", type=int, required=True)
    parser.add_argument("--min-free-bytes", type=int, required=True)
    parser.add_argument("--monitor-interval", type=float, required=True)
    parser.add_argument("--expected-systemd-unit")
    parser.add_argument("--require-cgroup-contract", action="store_true")
    return parser


def _preflight(args: argparse.Namespace) -> dict[str, Any]:
    root = args.project_root.resolve(strict=True)
    if root != PROJECT_ROOT.resolve(strict=True):
        raise ToolchainError("--project-root must identify this runner's repository")
    if args.proof_limit_bytes != FORMAL_PROOF_LIMIT_BYTES:
        raise ToolchainError("formal proof limit must be exactly 5000000000 bytes")
    if args.min_free_bytes != FORMAL_MIN_FREE_BYTES:
        raise ToolchainError("formal minimum free space must be exactly 10737418240 bytes")
    if min(args.solver_time_limit, args.solver_wall_timeout, args.verifier_wall_timeout, args.monitor_interval) <= 0:
        raise ToolchainError("all time limits and monitor interval must be positive")
    if args.solver_wall_timeout <= args.solver_time_limit:
        raise ToolchainError("solver wall timeout must exceed the solver time limit")

    paths = {
        name: value.resolve(strict=True)
        for name, value in {
            "opb": args.opb,
            "meta": args.meta,
            "var_map": args.var_map,
            "estimate": args.estimate,
            "translation_gate": args.translation_gate,
            "roundingsat": args.roundingsat,
            "roundingsat_repo": args.roundingsat_repo,
            "veripb": args.veripb,
        }.items()
    }
    if not paths["roundingsat"].is_file() or not paths["veripb"].is_file():
        raise ToolchainError("tool paths must be regular files")
    if not paths["roundingsat_repo"].is_dir():
        raise ToolchainError("RoundingSat repository must be a directory")

    meta = _strict_json(paths["meta"], "encoder metadata")
    estimate = _strict_json(paths["estimate"], "estimate")
    var_map = _strict_json(paths["var_map"], "variable map")
    gate = _strict_json(paths["translation_gate"], "translation gate")
    if meta.get("schema_version") != METADATA_SCHEMA or meta.get("model_schema_version") != MODEL_SCHEMA:
        raise ToolchainError("metadata schema is not the exact R1 v1 schema")
    if meta.get("variable_map_schema_version") != VAR_MAP_SCHEMA or meta.get("semantics") != SEMANTICS:
        raise ToolchainError("metadata variable-map schema or semantics mismatch")
    if estimate.get("schema_version") != ESTIMATE_SCHEMA or estimate.get("semantics") != SEMANTICS:
        raise ToolchainError("estimate schema or semantics mismatch")
    if estimate.get("model_schema_version") != MODEL_SCHEMA:
        raise ToolchainError("estimate model schema mismatch")
    if estimate.get("metadata_schema_version") != METADATA_SCHEMA:
        raise ToolchainError("estimate metadata schema mismatch")
    if estimate.get("variable_map_schema_version") != VAR_MAP_SCHEMA:
        raise ToolchainError("estimate variable-map schema mismatch")
    if var_map.get("schema_version") != VAR_MAP_SCHEMA or var_map.get("semantics") != SEMANTICS:
        raise ToolchainError("variable-map schema or semantics mismatch")
    if gate.get("schema_version") != GATE_SCHEMA or gate.get("semantics") != SEMANTICS:
        raise ToolchainError("translation-gate schema or semantics mismatch")
    checks = gate.get("checks")
    if not isinstance(checks, Mapping) or set(checks) != REQUIRED_GATE_CHECKS:
        raise ToolchainError("translation gate does not expose the exact required check set")
    if any(value is not True for value in checks.values()):
        raise ToolchainError("not every translation-gate check is exactly true")
    if gate.get("status") != "PASS" or gate.get("corpus_errors") != []:
        raise ToolchainError("translation gate is not a corpus-clean PASS")

    encoder_path = Path(__file__).with_name(ENCODER_NAME)
    gate_source_path = Path(__file__).with_name(GATE_NAME)
    runner_path = Path(__file__).with_name(RUNNER_NAME)
    encoder_source = _validate_file_record(meta.get("harness_source"), encoder_path, root, "metadata.harness_source")
    if estimate.get("harness_source") != encoder_source or gate.get("encoder_source") != encoder_source:
        raise ToolchainError("encoder source provenance does not close across estimate/meta/gate")
    gate_source = _validate_file_record(gate.get("gate_source"), gate_source_path, root, "gate.gate_source")
    runner_source = _file_record(runner_path, root)
    inputs = _validate_record_map(meta.get("inputs"), INPUT_PATHS, root, "metadata.inputs")
    evidence = _validate_record_map(meta.get("evidence"), EVIDENCE_PATHS, root, "metadata.evidence")
    if estimate.get("inputs") != inputs or estimate.get("evidence") != evidence:
        raise ToolchainError("estimate and metadata strict bundles differ")

    meta_git = _validate_git_snapshot(meta.get("git_snapshot"), "metadata.git_snapshot")
    estimate_git = _validate_git_snapshot(estimate.get("git_snapshot"), "estimate.git_snapshot")
    gate_git = _validate_git_snapshot(gate.get("git_snapshot"), "gate.git_snapshot")
    if estimate_git != meta_git or gate.get("encoder_git_snapshot") != meta_git:
        raise ToolchainError("encoder Git provenance does not close across records")
    current_git = _git_snapshot(root)
    if gate_git != current_git:
        raise ToolchainError("repository tracked state drifted after translation gate")

    _validate_file_record(meta.get("estimate"), paths["estimate"], root, "metadata.estimate")
    outputs = meta.get("outputs")
    if not isinstance(outputs, Mapping) or set(outputs) != {"opb", "var_map", "metadata"}:
        raise ToolchainError("metadata outputs are not the exact closed output set")
    opb_record = _validate_file_record(outputs["opb"], paths["opb"], root, "metadata.outputs.opb")
    var_map_record = _validate_file_record(outputs["var_map"], paths["var_map"], root, "metadata.outputs.var_map")
    metadata_output = outputs["metadata"]
    if (
        not isinstance(metadata_output, Mapping)
        or set(metadata_output) != {"path"}
        or type(metadata_output.get("path")) is not str
        or Path(metadata_output["path"]).resolve() != paths["meta"]
    ):
        raise ToolchainError("metadata self path is not exact")
    translation_inputs = gate.get("translation_inputs")
    expected_translation = {
        "opb": opb_record,
        "meta": _file_record(paths["meta"], root),
        "var_map": var_map_record,
        "estimate": _file_record(paths["estimate"], root),
    }
    if not isinstance(translation_inputs, Mapping) or dict(translation_inputs) != expected_translation:
        raise ToolchainError("gate translation inputs do not match exact current files")

    planning = estimate.get("proof_size_planning")
    if not isinstance(planning, Mapping) or planning.get("decision") != "GO":
        raise ToolchainError("estimate is not GO")
    bound = planning.get("bound_bytes")
    user_limit = planning.get("user_limit_bytes")
    if type(bound) is not int or bound <= 0 or bound > args.proof_limit_bytes:
        raise ToolchainError("estimate proof bound exceeds the formal proof limit")
    if user_limit != args.proof_limit_bytes:
        raise ToolchainError("estimate proof limit does not match runner proof limit")
    if _free_bytes(args.output_dir.resolve().parent) < args.min_free_bytes:
        raise ToolchainError("preflight disk free space is below the formal minimum")

    cgroup = _cgroup_state(args.expected_systemd_unit, args.require_cgroup_contract)
    tools_start = {
        "roundingsat": {
            "file": _file_record(paths["roundingsat"], root),
            "repository": _repo_identity(paths["roundingsat_repo"]),
        },
        "veripb": {"file": _file_record(paths["veripb"], root)},
    }
    return {
        "root": root,
        "paths": paths,
        "meta": meta,
        "estimate": estimate,
        "gate": gate,
        "inputs": {
            **expected_translation,
            "translation_gate": _file_record(paths["translation_gate"], root),
        },
        "sources": {"encoder": encoder_source, "gate": gate_source, "runner": runner_source},
        "git_snapshots": {"encoder": meta_git, "gate": gate_git, "runner": current_git},
        "cgroup_start": cgroup,
        "tools_start": tools_start,
    }


def _planned_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "started": output_dir / "toolchain_started.json",
        "record": output_dir / "toolchain_record.json",
        "resources": output_dir / "resource_monitor.json",
        "proof": output_dir / "roundingsat.proof.pbp",
        "solver_stdout": output_dir / "roundingsat.stdout.txt",
        "solver_stderr": output_dir / "roundingsat.stderr.txt",
        "verifier_stdout": output_dir / "veripb.stdout.txt",
        "verifier_stderr": output_dir / "veripb.stderr.txt",
        "version_stdout": output_dir / "veripb.version.stdout.txt",
        "version_stderr": output_dir / "veripb.version.stderr.txt",
    }


def _execute(args: argparse.Namespace, effective_argv: list[str]) -> int:
    output_dir = args.output_dir.resolve()
    planned = _planned_paths(output_dir)
    existing = [str(path) for path in planned.values() if path.exists()]
    if existing:
        raise ToolchainError("refusing to overwrite planned output(s): " + ", ".join(existing))
    output_dir.mkdir(parents=True, exist_ok=True)
    context = _preflight(args)
    paths = context["paths"]
    resources: list[dict[str, Any]] = []
    _sample(resources, output_dir, "pre_children", planned["proof"])
    started = {
        "schema_version": SCHEMA_VERSION,
        "semantics": SEMANTICS,
        "started_at_utc": _utc_now(),
        "argv": effective_argv,
        "inputs": context["inputs"],
        "sources": context["sources"],
        "git_snapshots": context["git_snapshots"],
        "tools_before_execution": context["tools_start"],
        "limits": {
            "proof_limit_bytes": args.proof_limit_bytes,
            "min_free_bytes": args.min_free_bytes,
            "solver_time_limit_seconds": args.solver_time_limit,
            "solver_wall_timeout_seconds": args.solver_wall_timeout,
            "verifier_wall_timeout_seconds": args.verifier_wall_timeout,
            "monitor_interval_seconds": args.monitor_interval,
        },
        "cgroup": context["cgroup_start"],
    }
    _exclusive_json(planned["started"], started)

    version = _run_child(
        [str(paths["veripb"]), "--version"],
        stdout_path=planned["version_stdout"],
        stderr_path=planned["version_stderr"],
        wall_timeout=min(30.0, args.verifier_wall_timeout),
        monitor_interval=args.monitor_interval,
        output_dir=output_dir,
        resources=resources,
        phase="veripb_version",
        min_free_bytes=args.min_free_bytes,
    )
    solver_argv = [
        str(paths["roundingsat"]),
        f"--proof-log={planned['proof']}",
        f"--time-limit={args.solver_time_limit:g}",
        str(paths["opb"]),
    ]
    solver = _run_child(
        solver_argv,
        stdout_path=planned["solver_stdout"],
        stderr_path=planned["solver_stderr"],
        wall_timeout=args.solver_wall_timeout,
        monitor_interval=args.monitor_interval,
        output_dir=output_dir,
        resources=resources,
        phase="roundingsat",
        min_free_bytes=args.min_free_bytes,
        proof_path=planned["proof"],
        proof_limit_bytes=args.proof_limit_bytes,
    )
    solver_status_lines = _status_lines(planned["solver_stdout"], planned["solver_stderr"])
    solver_declared_unsat = solver_status_lines == ["s UNSATISFIABLE"]
    tail = _proof_tail(planned["proof"])
    proof_tail_complete = tail["complete"] is True
    solver_success = (
        version["exit_code"] == 0
        and version["termination_reason"] is None
        and solver["exit_code"] == 0
        and solver["termination_reason"] is None
        and solver_declared_unsat
        and proof_tail_complete
    )

    opb_before_verifier = _sha256(paths["opb"])
    proof_before_verifier = _sha256(planned["proof"]) if planned["proof"].is_file() else None
    verifier: dict[str, Any] | None = None
    verifier_status_lines: list[str] = []
    verifier_errors: list[str] = []
    if solver_success:
        verifier = _run_child(
            [str(paths["veripb"]), "--opb", "--stats", str(paths["opb"]), str(planned["proof"])],
            stdout_path=planned["verifier_stdout"],
            stderr_path=planned["verifier_stderr"],
            wall_timeout=args.verifier_wall_timeout,
            monitor_interval=args.monitor_interval,
            output_dir=output_dir,
            resources=resources,
            phase="veripb",
            min_free_bytes=args.min_free_bytes,
            proof_path=planned["proof"],
            proof_limit_bytes=args.proof_limit_bytes,
        )
        verifier_status_lines = _status_lines(planned["verifier_stdout"], planned["verifier_stderr"])
        verifier_errors = _verifier_error_markers(planned["verifier_stdout"], planned["verifier_stderr"])
    else:
        _exclusive_text(planned["verifier_stdout"], "")
        _exclusive_text(planned["verifier_stderr"], "")

    opb_after_verifier = _sha256(paths["opb"])
    proof_after_verifier = _sha256(planned["proof"]) if planned["proof"].is_file() else None
    hashes_stable = (
        opb_before_verifier == opb_after_verifier == context["inputs"]["opb"]["sha256"]
        and proof_before_verifier is not None
        and proof_before_verifier == proof_after_verifier
    )
    tools_end = {
        "roundingsat": {
            "file": _file_record(paths["roundingsat"], context["root"]),
            "repository": _repo_identity(paths["roundingsat_repo"]),
        },
        "veripb": {"file": _file_record(paths["veripb"], context["root"])},
    }
    tools_stable = tools_end == context["tools_start"]
    veripb_verified = bool(
        verifier is not None
        and verifier["exit_code"] == 0
        and verifier["termination_reason"] is None
        and verifier_status_lines == ["s VERIFIED UNSATISFIABLE"]
        and not verifier_errors
        and hashes_stable
        and tools_stable
    )
    claim = (
        "machine_verified_residual_band_unsat_for_translation_gated_r1_upper_bound"
        if solver_success and veripb_verified
        else "none"
    )

    cgroup_end = _cgroup_state(args.expected_systemd_unit, False)
    minimum_free = min(sample["free_bytes"] for sample in resources)
    resource_payload = {
        "schema_version": "r1_upper_bound_pb_resource_monitor_v1",
        "semantics": SEMANTICS,
        "samples": resources,
        "minimum_free_bytes_observed": minimum_free,
        "limits": {
            "proof_limit_bytes": args.proof_limit_bytes,
            "min_free_bytes": args.min_free_bytes,
        },
        "cgroup_start": context["cgroup_start"],
        "cgroup_end": cgroup_end,
    }
    _exclusive_json(planned["resources"], resource_payload)
    proof_record = _file_record(planned["proof"], context["root"]) if planned["proof"].is_file() else None
    record = {
        "schema_version": SCHEMA_VERSION,
        "semantics": SEMANTICS,
        "started_at_utc": started["started_at_utc"],
        "finished_at_utc": _utc_now(),
        "argv": effective_argv,
        "inputs": context["inputs"],
        "sources": context["sources"],
        "git_snapshots": context["git_snapshots"],
        "tools": {
            "roundingsat": {
                **context["tools_start"]["roundingsat"]["file"],
                "repository": context["tools_start"]["roundingsat"]["repository"],
                "after_execution": tools_end["roundingsat"],
                "stable": tools_end["roundingsat"] == context["tools_start"]["roundingsat"],
            },
            "veripb": {
                **context["tools_start"]["veripb"]["file"],
                "after_execution": tools_end["veripb"],
                "stable": tools_end["veripb"] == context["tools_start"]["veripb"],
                "version_argv": version["argv"],
                "version_exit_code": version["exit_code"],
                "version_timed_out": version["timed_out"],
                "version_stdout": planned["version_stdout"].read_text(encoding="utf-8", errors="replace"),
                "version_stderr": planned["version_stderr"].read_text(encoding="utf-8", errors="replace"),
                "version_stdout_file": version["stdout"],
                "version_stderr_file": version["stderr"],
            },
            "stable": tools_stable,
        },
        "execution": started["limits"],
        "solver": {
            **solver,
            "status_lines": solver_status_lines,
            "solver_declared_unsat": solver_declared_unsat,
        },
        "proof": {
            "file": proof_record,
            "tail": tail,
            "proof_tail_complete": proof_tail_complete,
            "sha256_before_verifier": proof_before_verifier,
            "sha256_after_verifier": proof_after_verifier,
        },
        "verifier": (
            {
                **verifier,
                "status_lines": verifier_status_lines,
                "error_markers": verifier_errors,
                "veripb_verified": veripb_verified,
            }
            if verifier is not None
            else {
                "argv": [str(paths["veripb"]), "--opb", "--stats", str(paths["opb"]), str(planned["proof"])],
                "exit_code": None,
                "status": "NOT_RUN_NO_COMPLETE_UNSAT_PROOF",
                "status_lines": [],
                "error_markers": [],
                "veripb_verified": False,
                "stdout": _file_record(planned["verifier_stdout"], context["root"]),
                "stderr": _file_record(planned["verifier_stderr"], context["root"]),
            }
        ),
        "hash_stability": {
            "opb_before_verifier": opb_before_verifier,
            "opb_after_verifier": opb_after_verifier,
            "proof_before_verifier": proof_before_verifier,
            "proof_after_verifier": proof_after_verifier,
            "stable": hashes_stable,
        },
        "translation_gate": {
            "file": context["inputs"]["translation_gate"],
            "status": context["gate"]["status"],
            "corpus_errors": context["gate"]["corpus_errors"],
            "checks": context["gate"]["checks"],
        },
        "resource_monitor": _file_record(planned["resources"], context["root"]),
        "minimum_free_bytes_observed": minimum_free,
        "solver_declared_unsat": solver_declared_unsat,
        "proof_tail_complete": proof_tail_complete,
        "veripb_verified": veripb_verified,
        "tools_stable": tools_stable,
        "claim": claim,
        "claim_boundary": {
            "verified_component": "the translation-gated 22-dimension residual-band OPB is UNSAT",
            "veripb_verified_meaning": "research-grade machine-verifiable proof for that residual band",
            "sealed_certified": False,
            "historical_pb_judgments_restored": [],
            "complete_lemma_dependency": (
                "combine this residual-band proof with the separate elementary free-cell-cap exclusion "
                "4900 - 3544 - 4 * 2 = 1348 for area greater than 1348"
            ),
        },
    }
    _exclusive_json(planned["record"], record)
    print(json.dumps({"claim": claim, "record": str(planned["record"])}, sort_keys=True))
    return 0 if claim != "none" else 1


def main(argv: Sequence[str] | None = None) -> int:
    effective = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(effective)
    lock_dir = Path(f"/run/user/{os.getuid()}")
    lock_path = lock_dir / "r1_upper_bound_pb_toolchain_v1.lock"
    try:
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as exc:
        print(f"ToolchainError: cannot open singleton lock {lock_path}: {exc}", file=sys.stderr)
        return 2
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"ToolchainError: another PB toolchain owns {lock_path}", file=sys.stderr)
            return 2
        try:
            return _execute(args, [str(Path(__file__).resolve()), *effective])
        except (ToolchainError, FileNotFoundError, FileExistsError, OSError, subprocess.SubprocessError) as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
    finally:
        os.close(lock_fd)


if __name__ == "__main__":
    raise SystemExit(main())
