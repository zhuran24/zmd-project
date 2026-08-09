"""Run the research-only R3 arithmetic RoundingSat -> VeriPB chain.

This target-specific runner accepts only the independently translation-gated
B0 arithmetic model.  It pins every formal tool and input identity, requires
the approved cgroup contract, refuses every overwrite, and records raw child
output plus resource telemetry.  A successful run establishes only that the
lex-better arithmetic band is inconsistent given the separately reviewed R3
geometric lemmas; it says nothing about a witness or attainability.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from typing import Any


SCHEMA_VERSION = "r3_upper_bound_pb_toolchain_run_v1"
RESOURCE_SCHEMA = "r3_upper_bound_pb_resource_monitor_v1"
SEMANTICS = "r3_strict_upper_bound_1190_34_arithmetic_given_geometry_v1"
MODEL_SCHEMA = "r3_upper_bound_pb_v1"
METADATA_SCHEMA = "r3_upper_bound_pb_metadata_v1"
VAR_MAP_SCHEMA = "r3_upper_bound_pb_var_map_v1"
ESTIMATE_SCHEMA = "r3_upper_bound_pb_estimate_v1"
GATE_SCHEMA = "r3_upper_bound_pb_translation_gate_v1"
ENCODER_NAME = "r3_upper_bound_pb_encoder_v1.py"
GATE_NAME = "verify_r3_upper_bound_pb_translation_v1.py"
RUNNER_NAME = "run_r3_upper_bound_pb_toolchain_v1.py"

FORMAL_PROOF_LIMIT_BYTES = 5_000_000_000
FORMAL_MIN_FREE_BYTES = 10_737_418_240
FORMAL_SOLVER_TIME_LIMIT_SECONDS = 3_600.0
FORMAL_SOLVER_WALL_TIMEOUT_SECONDS = 3_900.0
FORMAL_VERIFIER_WALL_TIMEOUT_SECONDS = 3_600.0
FORMAL_MONITOR_INTERVAL_SECONDS = 1.0
FORMAL_GATE_WALL_TIMEOUT_SECONDS = 300.0
FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES = (
    FORMAL_MIN_FREE_BYTES + FORMAL_PROOF_LIMIT_BYTES
)

EXPECTED_MEMORY_HIGH = 35 * 1024**3
EXPECTED_MEMORY_MAX = 39 * 1024**3
EXPECTED_SWAP_MAX = 16 * 1024**3
EXPECTED_OOM_POLICY = "continue"
EXPECTED_KILL_MODE = "control-group"
EXPECTED_SEND_SIGKILL = "yes"

EXPECTED_ROUNDINGSAT_PATH = Path("/home/zhuran24/tools/roundingsat/build/roundingsat")
EXPECTED_ROUNDINGSAT_SHA256 = "08bb2542bcf09d99366f35e6fcfc7c79e002eca360ab9da027944c719fa3f8bf"
EXPECTED_ROUNDINGSAT_REPO = Path("/home/zhuran24/tools/roundingsat")
EXPECTED_ROUNDINGSAT_REVISION = "d4edbf7908a9bb951fd181940919e0f3ac7ab1ee"
EXPECTED_VERIPB_PATH = Path("/home/zhuran24/.cargo/bin/veripb")
EXPECTED_VERIPB_SHA256 = "a0c72df075b924af3b698ae808f86d3b55067168534397a0cc3d49594777b971"
EXPECTED_VERIPB_VERSION = "3.0.2"
EXPECTED_PYTHON_PATH = Path(
    "/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13"
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "track_b_b0_1190_34"
SINGLETON_LOCK_NAME = "zmd_pj_prod_scale_solver.lock"
ATTEMPT_MARKER_NAME = "formal_attempt_a001.reservation.json"

REQUIRED_GATE_CHECKS = frozenset(
    {
        "strict_bundle_closed_and_hashed",
        "r3_evidence_closed_and_hashed",
        "encoder_provenance_match",
        "translation_inputs_closed_and_hashed",
        "metadata_reconstruction_match",
        "estimate_reconstruction_match",
        "variable_map_dense",
        "variable_map_exact",
        "opb_header_exact",
        "constraint_multiset_exact",
        "strict_sentinels_exact",
        "membrane_class_table_exact",
        "halo_certificate_exact",
        "lex_better_band_exact",
        "arithmetic_corpus_unsat",
        "semantic_canaries_pass",
    }
)

INPUT_PATHS = {
    "problem_instance": (
        "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
    ),
    "problem_instance_schema": (
        "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.schema.json"
    ),
    "problem_md": "docs/research/cleanroom_rederivation_20260718/strict/external/problem.md",
    "sha256s": "docs/research/cleanroom_rederivation_20260718/strict/external/SHA256SUMS",
}
EXPECTED_INPUT_SHA256 = {
    "problem_instance": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    "problem_instance_schema": "5a85e23502e7b13feef495b8cc1ab243c65b0297d2a0f0f008258926e95c6b23",
    "problem_md": "c041e38d2144f2b4bace0c6c8567e3c7cdd5433f53981829f6ea6a8e03e0221f",
    "sha256s": "8810d5d6a80d92438628b7694216d3b3c6c1be50543072ec9c3bcf510d9c4d70",
}
EVIDENCE_PATHS = {
    "r3_response": "docs/research/cleanroom_rederivation_20260718/09_r3_response_gpt_pro_verbatim.md",
    "r3_judgment": "docs/research/cleanroom_rederivation_20260718/10_r3_judgment_20260720.md",
    "r3_adversarial_verdict": (
        "docs/research/cleanroom_rederivation_20260718/11_r3_adversarial_verdict_20260720.md"
    ),
    "independent_recomputation": (
        "docs/research/cleanroom_rederivation_20260718/verify_r3_certificates.py"
    ),
}
EXPECTED_EVIDENCE_SHA256 = {
    "r3_response": "f0670a76fbd57cabcd41d50823421921d336b50fd36da61e6ab5b2f408c4a700",
    "r3_judgment": "8651e8b5a6deb255824293dc2bad35394c7e5d4143cc82ff0ed674ab93adb89e",
    "r3_adversarial_verdict": "d48ba75040c61d042d091a893f0331b837ebc994d2b18ad429bcb9fef4856da0",
    "independent_recomputation": (
        "589b87a086f2c25015b535c5c12d68b6842aaa1f16fe449bcb94e3a733bd076a"
    ),
}

ERROR_MARKER = re.compile(
    r"(?:^|\b)(?:error|fatal|exception|traceback|panic|panicked|failed|unsupported|"
    r"verification failed|checking error|invalid proof)(?:\b|:)",
    re.IGNORECASE,
)
OOM_EVENT_KEYS = frozenset({"oom", "oom_kill", "oom_group_kill"})


class ToolchainError(RuntimeError):
    """A closed-contract preflight or execution error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ToolchainInterrupted(RuntimeError):
    """A caught operator/service signal; it can never carry a proof claim."""

    def __init__(self, signum: int) -> None:
        super().__init__(f"received signal {signum}")
        self.signum = signum


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
        raise ToolchainError("not_provenance_file", f"not a provenance file: {resolved}")
    return {
        "path": _display_path(resolved, project_root),
        "sha256": _sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _optional_file_record(path: Path, project_root: Path) -> dict[str, Any] | None:
    try:
        return _file_record(path, project_root)
    except (OSError, ToolchainError):
        return None


def _strict_json(path: Path, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ToolchainError("invalid_json", f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ToolchainError("invalid_json", f"{label} contains non-finite number {value}")

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
        )
    except ToolchainError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ToolchainError("invalid_json", f"cannot load {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ToolchainError("invalid_json", f"{label} must be a JSON object")
    return payload


def _exclusive_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _exclusive_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)


def _exclusive_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _append_jsonl(path: Path, payload: Any) -> None:
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC, 0o600)
    try:
        written = os.write(descriptor, encoded)
        if written != len(encoded):
            raise ToolchainError("telemetry_write_failure", "short write to telemetry JSONL")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _git_command(repo: Path, *arguments: str, binary: bool = False) -> str | bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
    )
    if binary:
        return completed.stdout
    return completed.stdout.decode("utf-8", errors="strict").rstrip("\n")


def _git_snapshot(repo: Path) -> dict[str, Any]:
    head = str(_git_command(repo, "rev-parse", "HEAD"))
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise ToolchainError("git_snapshot_invalid", f"invalid Git revision for {repo}: {head!r}")
    diff = _git_command(
        repo,
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "HEAD",
        "--",
        binary=True,
    )
    status = _git_command(
        repo,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=normal",
        binary=True,
    )
    assert isinstance(diff, bytes) and isinstance(status, bytes)
    return {
        "head": head,
        "tracked_dirty": bool(diff),
        "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
        "tracked_diff_size_bytes": len(diff),
        "status_dirty": bool(status),
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "status_size_bytes": len(status),
    }


def _source_snapshot(repo: Path) -> dict[str, Any]:
    """Snapshot source state while excluding this run's permitted artifact root."""
    head = str(_git_command(repo, "rev-parse", "HEAD"))
    exclude = ":(exclude).artifacts/track_b_b0_1190_34/**"
    diff = _git_command(
        repo,
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "HEAD",
        "--",
        ".",
        exclude,
        binary=True,
    )
    status = _git_command(
        repo,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=normal",
        "--",
        ".",
        exclude,
        binary=True,
    )
    assert isinstance(diff, bytes) and isinstance(status, bytes)
    return {
        "head": head,
        "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
        "tracked_diff_size_bytes": len(diff),
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
        raise ToolchainError("git_snapshot_invalid", f"{label} is not a closed Git snapshot")
    head = value["head"]
    diff_hash = value["tracked_diff_sha256"]
    diff_size = value["tracked_diff_size_bytes"]
    tracked_dirty = value["tracked_dirty"]
    status_hash = value["status_sha256"]
    status_size = value["status_size_bytes"]
    status_dirty = value["status_dirty"]
    if type(head) is not str or re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise ToolchainError("git_snapshot_invalid", f"{label}.head is invalid")
    if type(diff_hash) is not str or re.fullmatch(r"[0-9a-f]{64}", diff_hash) is None:
        raise ToolchainError("git_snapshot_invalid", f"{label}.tracked_diff_sha256 is invalid")
    if (
        type(diff_size) is not int
        or diff_size < 0
        or type(tracked_dirty) is not bool
        or tracked_dirty != (diff_size > 0)
    ):
        raise ToolchainError("git_snapshot_invalid", f"{label} tracked dirty/size mismatch")
    if type(status_hash) is not str or re.fullmatch(r"[0-9a-f]{64}", status_hash) is None:
        raise ToolchainError("git_snapshot_invalid", f"{label}.status_sha256 is invalid")
    if (
        type(status_size) is not int
        or status_size < 0
        or type(status_dirty) is not bool
        or status_dirty != (status_size > 0)
    ):
        raise ToolchainError("git_snapshot_invalid", f"{label} status dirty/size mismatch")
    return dict(value)


def _validate_file_record(value: Any, expected: Path, root: Path, label: str) -> dict[str, Any]:
    current = _file_record(expected, root)
    if not isinstance(value, Mapping) or dict(value) != current:
        raise ToolchainError("provenance_mismatch", f"{label} does not match the current file")
    return current


def _validate_record_map(
    value: Any,
    expected: Mapping[str, str],
    pinned_hashes: Mapping[str, str],
    root: Path,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise ToolchainError("provenance_mismatch", f"{label} is not the closed expected file set")
    records = {
        key: _validate_file_record(value[key], root / relative, root, f"{label}.{key}")
        for key, relative in expected.items()
    }
    actual_hashes = {key: record["sha256"] for key, record in records.items()}
    if actual_hashes != dict(pinned_hashes):
        raise ToolchainError("strict_input_hash_drift", f"{label} pinned SHA-256 map drifted")
    return records


def _repo_identity(repo: Path) -> dict[str, Any]:
    revision = str(_git_command(repo, "rev-parse", "HEAD"))
    status = str(_git_command(repo, "status", "--porcelain=v1", "--untracked-files=normal"))
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ToolchainError("tool_identity_drift", "RoundingSat repository revision is invalid")
    return {
        "revision": revision,
        "branch": str(_git_command(repo, "branch", "--show-current")),
        "dirty": bool(status),
        "status_porcelain_v1": status.splitlines(),
    }


def _read_text(path: Path) -> str | None:
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


def _proc_cgroup(pid: int) -> dict[str, Any]:
    path = Path("/proc") / str(pid) / "cgroup"
    try:
        raw = path.read_text(encoding="ascii").strip()
    except OSError as exc:
        return {"pid": pid, "error": f"{type(exc).__name__}: {exc}", "unified_path": None}
    unified = [line.split("::", 1)[1] for line in raw.splitlines() if "::" in line]
    return {
        "pid": pid,
        "raw": raw.splitlines(),
        "unified_path": unified[0] if len(unified) == 1 else None,
    }


def _systemd_property(unit: str, name: str) -> dict[str, Any]:
    argv = ["systemctl", "--user", "show", unit, f"--property={name}", "--value"]
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return {
            "argv": argv,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "value": completed.stdout.strip() if completed.returncode == 0 else None,
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "argv": argv,
            "exit_code": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "value": None,
        }


def _expected_unit_is_cgroup_leaf(relative: Any, expected_unit: Any) -> bool:
    return bool(
        type(relative) is str
        and type(expected_unit) is str
        and expected_unit
        and Path(relative).name == expected_unit
    )


def _limit_allows_contract(value: Any, required: int) -> bool:
    if value == "max":
        return True
    return type(value) is str and value.isdigit() and int(value) >= required


def _ancestor_limits_allow_contract(ancestors: Sequence[Mapping[str, Any]]) -> bool:
    if not ancestors:
        return False
    cgroup_root = str(Path("/sys/fs/cgroup"))
    for item in ancestors:
        limits = (
            item.get("memory_high"),
            item.get("memory_max"),
            item.get("memory_swap_max"),
        )
        # The cgroup-v2 root has no limit files: unlike a missing non-root
        # controller value, this is the kernel's unbounded root semantics.
        if item.get("path") == cgroup_root and limits == (None, None, None):
            continue
        if not (
            _limit_allows_contract(limits[0], EXPECTED_MEMORY_HIGH)
            and _limit_allows_contract(limits[1], EXPECTED_MEMORY_MAX)
            and _limit_allows_contract(limits[2], EXPECTED_SWAP_MAX)
        ):
            return False
    return True


def _cgroup_state(expected_unit: str | None, require_contract: bool) -> dict[str, Any]:
    self_cgroup = _proc_cgroup(os.getpid())
    relative = self_cgroup.get("unified_path")
    cgroup_dir = (
        Path("/sys/fs/cgroup") / str(relative).lstrip("/")
        if isinstance(relative, str)
        else None
    )
    leaf_values = {
        name: _read_text(cgroup_dir / name) if cgroup_dir is not None else None
        for name in (
            "memory.high",
            "memory.max",
            "memory.swap.max",
            "memory.current",
            "memory.peak",
        )
    }
    events = _integer_map(_read_text(cgroup_dir / "memory.events") if cgroup_dir else None)
    cgroup_procs = _read_text(cgroup_dir / "cgroup.procs") if cgroup_dir else None
    properties = {
        name: _systemd_property(expected_unit, name) if expected_unit else None
        for name in (
            "MemoryHigh",
            "MemoryMax",
            "MemorySwapMax",
            "OOMPolicy",
            "KillMode",
            "SendSIGKILL",
        )
    }
    expected_properties = {
        "MemoryHigh": str(EXPECTED_MEMORY_HIGH),
        "MemoryMax": str(EXPECTED_MEMORY_MAX),
        "MemorySwapMax": str(EXPECTED_SWAP_MAX),
        "OOMPolicy": EXPECTED_OOM_POLICY,
        "KillMode": EXPECTED_KILL_MODE,
        "SendSIGKILL": EXPECTED_SEND_SIGKILL,
    }
    property_checks = {
        name: isinstance(properties[name], Mapping)
        and properties[name].get("exit_code") == 0
        and properties[name].get("value") == expected
        for name, expected in expected_properties.items()
    }
    ancestors: list[dict[str, Any]] = []
    if cgroup_dir is not None:
        current = cgroup_dir
        cgroup_root = Path("/sys/fs/cgroup")
        while current == cgroup_root or cgroup_root in current.parents:
            ancestors.append(
                {
                    "path": str(current),
                    "memory_high": _read_text(current / "memory.high"),
                    "memory_max": _read_text(current / "memory.max"),
                    "memory_swap_max": _read_text(current / "memory.swap.max"),
                }
            )
            if current == cgroup_root:
                break
            current = current.parent

    ancestor_limits_allow_contract = _ancestor_limits_allow_contract(ancestors)
    checks = {
        "unified_cgroup_found": isinstance(relative, str),
        "expected_unit_is_cgroup_leaf": _expected_unit_is_cgroup_leaf(
            relative, expected_unit
        ),
        "memory_high_exact": leaf_values["memory.high"] == str(EXPECTED_MEMORY_HIGH),
        "memory_max_exact": leaf_values["memory.max"] == str(EXPECTED_MEMORY_MAX),
        "memory_swap_max_exact": leaf_values["memory.swap.max"] == str(EXPECTED_SWAP_MAX),
        "memory_events_readable": events is not None,
        "systemd_memory_high_exact": property_checks["MemoryHigh"],
        "systemd_memory_max_exact": property_checks["MemoryMax"],
        "systemd_memory_swap_max_exact": property_checks["MemorySwapMax"],
        "oom_policy_exact": property_checks["OOMPolicy"],
        "kill_mode_exact": property_checks["KillMode"],
        "send_sigkill_exact": property_checks["SendSIGKILL"],
        "ancestor_limits_allow_contract": ancestor_limits_allow_contract,
    }
    contract_pass = bool(expected_unit) and all(checks.values())
    if require_contract and not contract_pass:
        raise ToolchainError(
            "resource_contract_mismatch",
            f"required cgroup contract is not exact: {checks}",
        )
    return {
        "required": require_contract,
        "expected_systemd_unit": expected_unit,
        "self": self_cgroup,
        "cgroup_path": relative,
        "cgroup_directory": str(cgroup_dir) if cgroup_dir else None,
        "leaf_values": leaf_values,
        "memory_events": events,
        "cgroup_procs": cgroup_procs.splitlines() if cgroup_procs else [],
        "ancestor_limits": ancestors,
        "systemd_properties": properties,
        "checks": checks,
        "contract_pass": contract_pass,
    }


def _free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def _nearest_existing_ancestor(path: Path) -> Path:
    current = path
    while not current.exists():
        if current == current.parent:
            raise ToolchainError("output_path_invalid", f"no existing ancestor for {path}")
        current = current.parent
    return current


def _sample(
    resources: list[dict[str, Any]],
    output_dir: Path,
    phase: str,
    proof: Path | None,
    *,
    telemetry_path: Path | None = None,
    cgroup_dir: Path | None = None,
    active_pid: int | None = None,
) -> None:
    sample = {
        "timestamp_utc": _utc_now(),
        "monotonic_seconds": time.monotonic(),
        "phase": phase,
        "free_bytes": _free_bytes(output_dir),
        "proof_size_bytes": proof.stat().st_size if proof is not None and proof.is_file() else None,
        "active_child": _proc_cgroup(active_pid) if active_pid is not None else None,
        "cgroup": (
            {
                "memory_current": _read_text(cgroup_dir / "memory.current"),
                "memory_peak": _read_text(cgroup_dir / "memory.peak"),
                "memory_swap_current": _read_text(cgroup_dir / "memory.swap.current"),
                "memory_swap_peak": _read_text(cgroup_dir / "memory.swap.peak"),
                "memory_events": _integer_map(_read_text(cgroup_dir / "memory.events")),
                "cgroup_procs": (_read_text(cgroup_dir / "cgroup.procs") or "").splitlines(),
            }
            if cgroup_dir is not None
            else None
        ),
    }
    resources.append(sample)
    if telemetry_path is not None:
        _append_jsonl(telemetry_path, sample)


def _process_group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_group(process: subprocess.Popen[Any]) -> bool:
    process_group = process.pid
    if _process_group_exists(process_group):
        try:
            os.killpg(process_group, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    if _process_group_exists(process_group):
        try:
            os.killpg(process_group, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        return False
    return not _process_group_exists(process_group)


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
    telemetry_path: Path | None = None,
    expected_cgroup_path: str | None = None,
) -> dict[str, Any]:
    started_at_utc = _utc_now()
    started_wall_time_ns = time.time_ns()
    started = time.monotonic()
    termination_reason: str | None = None
    spawn_error: str | None = None
    child_cgroup: dict[str, Any] | None = None
    process: subprocess.Popen[Any] | None = None
    process_group_clean = True
    completion_cgroup_procs: list[str] = []
    with stdout_path.open("x", encoding="utf-8", newline="\n") as stdout_handle, stderr_path.open(
        "x", encoding="utf-8", newline="\n"
    ) as stderr_handle:
        try:
            try:
                process = subprocess.Popen(
                    command,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    text=True,
                    start_new_session=True,
                )
            except OSError as exc:
                spawn_error = f"{type(exc).__name__}: {exc}"
            if process is not None:
                child_cgroup = _proc_cgroup(process.pid)
                if (
                    expected_cgroup_path is not None
                    and child_cgroup.get("unified_path") != expected_cgroup_path
                ):
                    termination_reason = "child_cgroup_mismatch"
                    _terminate_group(process)
                cgroup_dir = (
                    Path("/sys/fs/cgroup") / expected_cgroup_path.lstrip("/")
                    if expected_cgroup_path is not None
                    else None
                )
                while process.poll() is None:
                    _sample(
                        resources,
                        output_dir,
                        phase,
                        proof_path,
                        telemetry_path=telemetry_path,
                        cgroup_dir=cgroup_dir,
                        active_pid=process.pid,
                    )
                    active_child = resources[-1]["active_child"]
                    elapsed = time.monotonic() - started
                    current_free = resources[-1]["free_bytes"]
                    current_proof = resources[-1]["proof_size_bytes"]
                    if (
                        expected_cgroup_path is not None
                        and active_child.get("unified_path") != expected_cgroup_path
                    ):
                        termination_reason = "child_cgroup_mismatch_during_run"
                    elif elapsed > wall_timeout:
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
                _sample(
                    resources,
                    output_dir,
                    f"{phase}_complete",
                    proof_path,
                    telemetry_path=telemetry_path,
                    cgroup_dir=cgroup_dir,
                    active_pid=process.pid,
                )
                completion_free = resources[-1]["free_bytes"]
                completion_proof = resources[-1]["proof_size_bytes"]
                cgroup_sample = resources[-1]["cgroup"]
                completion_cgroup_procs = cgroup_sample["cgroup_procs"] if cgroup_sample else []
                unexpected_procs = {
                    pid for pid in completion_cgroup_procs if pid != str(os.getpid())
                }
                if termination_reason is None and unexpected_procs:
                    termination_reason = "child_cgroup_not_clean_at_completion"
                elif termination_reason is None and completion_free < min_free_bytes:
                    termination_reason = "disk_free_below_minimum_at_completion"
                elif (
                    termination_reason is None
                    and
                    proof_limit_bytes is not None
                    and completion_proof is not None
                    and completion_proof > proof_limit_bytes
                ):
                    termination_reason = "proof_size_limit_exceeded_at_completion"
            else:
                exit_code = None
        finally:
            if process is not None and _process_group_exists(process.pid):
                process_group_clean = _terminate_group(process)
    return {
        "argv": command,
        "started_at_utc": started_at_utc,
        "started_wall_time_ns": started_wall_time_ns,
        "finished_at_utc": _utc_now(),
        "finished_wall_time_ns": time.time_ns(),
        "exit_code": exit_code,
        "timed_out": termination_reason == "wall_timeout",
        "termination_reason": termination_reason,
        "spawn_error": spawn_error,
        "elapsed_seconds": time.monotonic() - started,
        "child_cgroup": child_cgroup,
        "completion_cgroup_procs": completion_cgroup_procs,
        "process_group_clean": process_group_clean,
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


def _stdout_status_exact(stdout_path: Path, stderr_path: Path, expected: str) -> bool:
    return _status_lines(stdout_path) == [expected] and _status_lines(stderr_path) == []


def _error_markers(*paths: Path) -> list[str]:
    result: list[str] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if ERROR_MARKER.search(line):
                result.append(line.strip())
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
    return {
        "nonempty": True,
        "conclusion_line": conclusion,
        "end_line": end,
        "complete": complete,
    }


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


def _validate_exact_runtime_contract(args: argparse.Namespace) -> None:
    if Path(sys.executable).resolve() != EXPECTED_PYTHON_PATH.resolve(strict=True):
        raise ToolchainError(
            "runtime_contract_mismatch",
            f"formal B0 must use the pinned interpreter {EXPECTED_PYTHON_PATH}",
        )
    exact_values = {
        "proof_limit_bytes": FORMAL_PROOF_LIMIT_BYTES,
        "min_free_bytes": FORMAL_MIN_FREE_BYTES,
        "solver_time_limit": FORMAL_SOLVER_TIME_LIMIT_SECONDS,
        "solver_wall_timeout": FORMAL_SOLVER_WALL_TIMEOUT_SECONDS,
        "verifier_wall_timeout": FORMAL_VERIFIER_WALL_TIMEOUT_SECONDS,
        "monitor_interval": FORMAL_MONITOR_INTERVAL_SECONDS,
    }
    for name, expected in exact_values.items():
        value = getattr(args, name)
        if type(value) is float and not math.isfinite(value):
            raise ToolchainError("runtime_contract_mismatch", f"--{name.replace('_', '-')} must be finite")
        if value != expected:
            raise ToolchainError(
                "runtime_contract_mismatch",
                f"--{name.replace('_', '-')} must be exactly {expected:g}",
            )
    if not args.require_cgroup_contract or not args.expected_systemd_unit:
        raise ToolchainError(
            "resource_contract_mismatch",
            "formal B0 requires --require-cgroup-contract and --expected-systemd-unit",
        )


def _validate_tool_paths(paths: Mapping[str, Path], root: Path) -> dict[str, Any]:
    if paths["roundingsat"] != EXPECTED_ROUNDINGSAT_PATH.resolve(strict=True):
        raise ToolchainError("tool_identity_drift", "RoundingSat path is not the pinned formal binary")
    if paths["roundingsat_repo"] != EXPECTED_ROUNDINGSAT_REPO.resolve(strict=True):
        raise ToolchainError("tool_identity_drift", "RoundingSat source repository path is not pinned")
    if paths["veripb"] != EXPECTED_VERIPB_PATH.resolve(strict=True):
        raise ToolchainError("tool_identity_drift", "VeriPB path is not the pinned formal binary")
    for name in ("roundingsat", "veripb"):
        if not paths[name].is_file() or not os.access(paths[name], os.X_OK):
            raise ToolchainError("tool_identity_drift", f"{name} is not an executable regular file")
    roundingsat_record = _file_record(paths["roundingsat"], root)
    veripb_record = _file_record(paths["veripb"], root)
    if roundingsat_record["sha256"] != EXPECTED_ROUNDINGSAT_SHA256:
        raise ToolchainError("tool_identity_drift", "RoundingSat SHA-256 drifted")
    if veripb_record["sha256"] != EXPECTED_VERIPB_SHA256:
        raise ToolchainError("tool_identity_drift", "VeriPB SHA-256 drifted")
    repository = _repo_identity(paths["roundingsat_repo"])
    if repository["revision"] != EXPECTED_ROUNDINGSAT_REVISION or repository["dirty"]:
        raise ToolchainError("tool_identity_drift", "RoundingSat source revision is not pinned and clean")
    return {
        "python": {"file": _file_record(Path(sys.executable), root)},
        "roundingsat": {"file": roundingsat_record, "repository": repository},
        "veripb": {"file": veripb_record, "expected_version": EXPECTED_VERIPB_VERSION},
    }


def _preflight(args: argparse.Namespace) -> dict[str, Any]:
    root = args.project_root.resolve(strict=True)
    if root != PROJECT_ROOT.resolve(strict=True):
        raise ToolchainError("project_root_mismatch", "--project-root must identify this repository")
    _validate_exact_runtime_contract(args)
    output_dir = args.output_dir.resolve(strict=False)
    artifact_root = ARTIFACT_ROOT.resolve(strict=False)
    try:
        output_dir.relative_to(artifact_root)
    except ValueError as exc:
        raise ToolchainError(
            "output_path_invalid",
            f"--output-dir must be below {artifact_root}",
        ) from exc
    if output_dir == artifact_root or output_dir.exists():
        raise ToolchainError("output_exists", "formal output directory must be new and non-root")

    raw_paths = {
        "opb": args.opb,
        "meta": args.meta,
        "var_map": args.var_map,
        "estimate": args.estimate,
        "translation_gate": args.translation_gate,
        "roundingsat": args.roundingsat,
        "roundingsat_repo": args.roundingsat_repo,
        "veripb": args.veripb,
    }
    try:
        paths = {name: value.resolve(strict=True) for name, value in raw_paths.items()}
    except OSError as exc:
        raise ToolchainError("missing_input", f"cannot resolve formal input: {exc}") from exc
    for name in ("opb", "meta", "var_map", "estimate", "translation_gate"):
        if not paths[name].is_file():
            raise ToolchainError("missing_input", f"{name} is not a regular file")
    if not paths["roundingsat_repo"].is_dir():
        raise ToolchainError("tool_identity_drift", "RoundingSat repository is not a directory")

    meta = _strict_json(paths["meta"], "encoder metadata")
    estimate = _strict_json(paths["estimate"], "estimate")
    var_map = _strict_json(paths["var_map"], "variable map")
    gate = _strict_json(paths["translation_gate"], "translation gate")
    if (
        meta.get("schema_version") != METADATA_SCHEMA
        or meta.get("model_schema_version") != MODEL_SCHEMA
        or meta.get("variable_map_schema_version") != VAR_MAP_SCHEMA
        or meta.get("semantics") != SEMANTICS
    ):
        raise ToolchainError("schema_mismatch", "metadata schema or semantics mismatch")
    if (
        estimate.get("schema_version") != ESTIMATE_SCHEMA
        or estimate.get("model_schema_version") != MODEL_SCHEMA
        or estimate.get("metadata_schema_version") != METADATA_SCHEMA
        or estimate.get("variable_map_schema_version") != VAR_MAP_SCHEMA
        or estimate.get("semantics") != SEMANTICS
    ):
        raise ToolchainError("schema_mismatch", "estimate schema or semantics mismatch")
    if (
        var_map.get("schema_version") != VAR_MAP_SCHEMA
        or var_map.get("model_schema_version") != MODEL_SCHEMA
        or var_map.get("semantics") != SEMANTICS
    ):
        raise ToolchainError("schema_mismatch", "variable-map schema or semantics mismatch")
    if (
        gate.get("schema_version") != GATE_SCHEMA
        or gate.get("model_schema_version") != MODEL_SCHEMA
        or gate.get("metadata_schema_version") != METADATA_SCHEMA
        or gate.get("variable_map_schema_version") != VAR_MAP_SCHEMA
        or gate.get("semantics") != SEMANTICS
    ):
        raise ToolchainError("schema_mismatch", "translation-gate schema or semantics mismatch")
    checks = gate.get("checks")
    if not isinstance(checks, Mapping) or set(checks) != REQUIRED_GATE_CHECKS:
        raise ToolchainError("translation_gate_failure", "translation gate has the wrong closed check set")
    if any(value is not True for value in checks.values()):
        raise ToolchainError("translation_gate_failure", "not every translation-gate check is true")
    if (
        gate.get("status") != "PASS"
        or gate.get("corpus_errors") != []
        or gate.get("proof_status") != "translation_gate_only_no_unsat_or_proof_claim"
    ):
        raise ToolchainError("translation_gate_failure", "translation gate is not a corpus-clean PASS")

    encoder_path = Path(__file__).with_name(ENCODER_NAME)
    gate_source_path = Path(__file__).with_name(GATE_NAME)
    runner_path = Path(__file__)
    encoder_source = _validate_file_record(
        meta.get("harness_source"), encoder_path, root, "metadata.harness_source"
    )
    if estimate.get("harness_source") != encoder_source or gate.get("encoder_source") != encoder_source:
        raise ToolchainError("provenance_mismatch", "encoder source provenance does not close")
    gate_source = _validate_file_record(
        gate.get("gate_source"), gate_source_path, root, "gate.gate_source"
    )
    runner_source = _file_record(runner_path, root)
    inputs = _validate_record_map(
        meta.get("inputs"), INPUT_PATHS, EXPECTED_INPUT_SHA256, root, "metadata.inputs"
    )
    evidence = _validate_record_map(
        meta.get("evidence"), EVIDENCE_PATHS, EXPECTED_EVIDENCE_SHA256, root, "metadata.evidence"
    )
    if estimate.get("inputs") != inputs or estimate.get("evidence") != evidence:
        raise ToolchainError("provenance_mismatch", "estimate and metadata strict bundles differ")
    if gate.get("strict_inputs") != inputs or gate.get("evidence") != evidence:
        raise ToolchainError("provenance_mismatch", "gate strict/evidence bundles do not close")

    meta_git = _validate_git_snapshot(meta.get("git_snapshot"), "metadata.git_snapshot")
    estimate_git = _validate_git_snapshot(estimate.get("git_snapshot"), "estimate.git_snapshot")
    gate_git = _validate_git_snapshot(gate.get("git_snapshot"), "gate.git_snapshot")
    if estimate_git != meta_git or gate.get("encoder_git_snapshot") != meta_git:
        raise ToolchainError("provenance_mismatch", "encoder Git provenance does not close")
    current_git = _git_snapshot(root)
    if gate_git != current_git:
        raise ToolchainError("source_state_drift", "repository state drifted after translation gate")

    _validate_file_record(meta.get("estimate"), paths["estimate"], root, "metadata.estimate")
    outputs = meta.get("outputs")
    if not isinstance(outputs, Mapping) or set(outputs) != {"opb", "var_map", "metadata"}:
        raise ToolchainError("provenance_mismatch", "metadata outputs are not closed")
    opb_record = _validate_file_record(outputs["opb"], paths["opb"], root, "metadata.outputs.opb")
    var_map_record = _validate_file_record(
        outputs["var_map"], paths["var_map"], root, "metadata.outputs.var_map"
    )
    metadata_output = outputs["metadata"]
    if (
        not isinstance(metadata_output, Mapping)
        or set(metadata_output) != {"path"}
        or type(metadata_output.get("path")) is not str
        or Path(metadata_output["path"]).resolve() != paths["meta"]
    ):
        raise ToolchainError("provenance_mismatch", "metadata self path is not exact")
    expected_translation = {
        "estimate": _file_record(paths["estimate"], root),
        "meta": _file_record(paths["meta"], root),
        "opb": opb_record,
        "var_map": var_map_record,
    }
    if gate.get("translation_inputs") != expected_translation:
        raise ToolchainError("provenance_mismatch", "gate translation inputs do not match current files")

    planning = estimate.get("proof_size_planning")
    if not isinstance(planning, Mapping) or planning.get("decision") != "GO":
        raise ToolchainError("estimate_no_go", "estimate is not GO")
    bound = planning.get("bound_bytes")
    user_limit = planning.get("user_limit_bytes")
    if type(bound) is not int or bound <= 0 or bound > FORMAL_PROOF_LIMIT_BYTES:
        raise ToolchainError("estimate_no_go", "estimate proof bound exceeds the formal cap")
    if user_limit != FORMAL_PROOF_LIMIT_BYTES:
        raise ToolchainError("estimate_no_go", "estimate uses a different proof cap")
    projected = estimate.get("projected_outputs")
    if (
        not isinstance(projected, Mapping)
        or set(projected) != {"opb_bytes"}
        or projected.get("opb_bytes") != paths["opb"].stat().st_size
    ):
        raise ToolchainError("estimate_no_go", "estimate OPB byte projection drifted")
    disk_base = _nearest_existing_ancestor(output_dir.parent)
    free = _free_bytes(disk_base)
    if free < FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES:
        raise ToolchainError(
            "disk_low_water",
            "free space minus the full 5 GB proof cap would violate the 10 GiB low-water mark",
        )

    cgroup_start = _cgroup_state(args.expected_systemd_unit, True)
    tools_start = _validate_tool_paths(paths, root)
    source_snapshot = _source_snapshot(root)
    return {
        "root": root,
        "output_dir": output_dir,
        "paths": paths,
        "meta": meta,
        "estimate": estimate,
        "gate": gate,
        "inputs": {
            **expected_translation,
            "translation_gate": _file_record(paths["translation_gate"], root),
        },
        "strict_inputs": inputs,
        "evidence": evidence,
        "sources": {"encoder": encoder_source, "gate": gate_source, "runner": runner_source},
        "git_snapshots": {
            "encoder": meta_git,
            "gate": gate_git,
            "runner": current_git,
            "source_surface_start": source_snapshot,
        },
        "cgroup_start": cgroup_start,
        "tools_start": tools_start,
        "proof_bound_bytes": bound,
        "preflight_free_bytes": free,
    }


def _planned_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "started": output_dir / "toolchain_started.json",
        "record": output_dir / "toolchain_record.json",
        "telemetry": output_dir / "resource_monitor.jsonl",
        "opb": output_dir / "formula.opb",
        "meta": output_dir / "encoder.meta.json",
        "var_map": output_dir / "variable_map.json",
        "estimate": output_dir / "estimate.json",
        "gate": output_dir / "translation_gate.json",
        "gate_recheck": output_dir / "translation_gate.recheck.json",
        "gate_recheck_stdout": output_dir / "translation_gate.recheck.stdout.txt",
        "gate_recheck_stderr": output_dir / "translation_gate.recheck.stderr.txt",
        "proof": output_dir / "roundingsat.proof.pbp",
        "solver_stdout": output_dir / "roundingsat.stdout.txt",
        "solver_stderr": output_dir / "roundingsat.stderr.txt",
        "verifier_stdout": output_dir / "veripb.stdout.txt",
        "verifier_stderr": output_dir / "veripb.stderr.txt",
        "version_stdout": output_dir / "veripb.version.stdout.txt",
        "version_stderr": output_dir / "veripb.version.stderr.txt",
        "checksums": output_dir / "SHA256SUMS",
    }


def _snapshot_inputs(context: Mapping[str, Any], planned: Mapping[str, Path]) -> dict[str, Any]:
    source_names = {
        "opb": "opb",
        "meta": "meta",
        "var_map": "var_map",
        "estimate": "estimate",
        "translation_gate": "gate",
    }
    records: dict[str, Any] = {}
    for source_name, planned_name in source_names.items():
        source = context["paths"][source_name]
        destination = planned[planned_name]
        _exclusive_bytes(destination, source.read_bytes())
        record = _file_record(destination, context["root"])
        if record["sha256"] != context["inputs"][source_name]["sha256"]:
            raise ToolchainError("artifact_copy_drift", f"copied {source_name} hash drifted")
        records[source_name] = record
    return records


def _veripb_version_ok(stdout_path: Path, stderr_path: Path, child: Mapping[str, Any]) -> bool:
    if child.get("exit_code") != 0 or child.get("termination_reason") is not None:
        return False
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace").splitlines()
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    return stdout == [
        f"Running VeriPB version {EXPECTED_VERIPB_VERSION}",
        f"veripb {EXPECTED_VERIPB_VERSION}",
    ] and not stderr


def _event_deltas(
    before: Mapping[str, int] | None,
    after: Mapping[str, int] | None,
) -> dict[str, int] | None:
    if before is None or after is None or set(before) != set(after):
        return None
    return {key: after[key] - before[key] for key in sorted(before)}


def _tool_records_now(paths: Mapping[str, Path], root: Path) -> dict[str, Any]:
    return {
        "python": {"file": _optional_file_record(Path(sys.executable), root)},
        "roundingsat": {
            "file": _optional_file_record(paths["roundingsat"], root),
            "repository": _repo_identity(paths["roundingsat_repo"]),
        },
        "veripb": {
            "file": _optional_file_record(paths["veripb"], root),
            "expected_version": EXPECTED_VERIPB_VERSION,
        },
    }


def _add_child_failures(
    failures: list[str],
    child: Mapping[str, Any],
    prefix: str,
    *,
    accepted_exit_codes: frozenset[int] = frozenset({0}),
) -> None:
    if child.get("spawn_error") is not None:
        failures.append(f"{prefix}_spawn_failure")
    reason = child.get("termination_reason")
    if reason is not None:
        failures.append(f"{prefix}_{reason}")
    exit_code = child.get("exit_code")
    if exit_code is not None and exit_code not in accepted_exit_codes:
        failures.append(f"{prefix}_nonzero_exit")
    if child.get("process_group_clean") is not True:
        failures.append(f"{prefix}_process_group_not_clean")


def _write_checksum_manifest(
    output_dir: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """Seal every completed raw artifact without introducing a hash cycle."""
    excluded = {manifest_path.name, "toolchain_record.json"}
    entries: list[tuple[str, str]] = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if path.name in excluded:
            continue
        if path.is_symlink() or not path.is_file():
            raise ToolchainError(
                "artifact_manifest_failure",
                f"unexpected non-regular artifact before manifest: {path}",
            )
        entries.append((_sha256(path), path.name))
    if not entries:
        raise ToolchainError("artifact_manifest_failure", "artifact manifest would be empty")
    _exclusive_text(
        manifest_path,
        "".join(f"{digest}  {name}\n" for digest, name in entries),
    )
    return {
        "file": _file_record(manifest_path, PROJECT_ROOT),
        "entries": {name: digest for digest, name in entries},
        "covered_files": [name for _, name in entries],
        "excluded_to_avoid_hash_cycle": sorted(excluded),
    }


def _checksum_manifest_stable(
    output_dir: Path,
    manifest_path: Path,
    report: Mapping[str, Any],
) -> bool:
    entries = report.get("entries")
    if not isinstance(entries, Mapping) or not all(
        type(name) is str
        and type(digest) is str
        and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
        for name, digest in entries.items()
    ):
        return False
    current_names = sorted(
        path.name
        for path in output_dir.iterdir()
        if path.is_file() and path.name not in {manifest_path.name, "toolchain_record.json"}
    )
    if current_names != sorted(entries):
        return False
    expected_text = "".join(f"{entries[name]}  {name}\n" for name in sorted(entries))
    try:
        if manifest_path.read_text(encoding="ascii") != expected_text:
            return False
        if _file_record(manifest_path, PROJECT_ROOT) != report.get("file"):
            return False
        return all(_sha256(output_dir / name) == entries[name] for name in current_names)
    except (OSError, UnicodeError, ToolchainError):
        return False


def _reserve_formal_attempt(
    context: Mapping[str, Any],
    effective_argv: list[str],
) -> Path:
    output_dir = context["output_dir"]
    marker = ARTIFACT_ROOT / ATTEMPT_MARKER_NAME
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        _exclusive_json(
            marker,
            {
                "schema_version": "r3_upper_bound_pb_formal_attempt_reservation_v1",
                "attempt": "a001",
                "reserved_at_utc": _utc_now(),
                "output_dir": str(output_dir),
                "argv": effective_argv,
                "git_head": context["git_snapshots"]["runner"]["head"],
            },
        )
    except FileExistsError as exc:
        raise ToolchainError(
            "formal_attempt_already_consumed",
            f"formal attempt a001 is already reserved by {marker}",
        ) from exc
    try:
        output_dir.mkdir(mode=0o700, exist_ok=False)
    except OSError:
        # The persistent reservation deliberately remains: a001 was consumed.
        raise
    return marker


def _execute(args: argparse.Namespace, effective_argv: list[str]) -> int:
    context = _preflight(args)
    output_dir = context["output_dir"]
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    _reserve_formal_attempt(context, effective_argv)
    planned = _planned_paths(output_dir)
    copied_inputs = _snapshot_inputs(context, planned)
    paths = context["paths"]
    resources: list[dict[str, Any]] = []
    cgroup_path = context["cgroup_start"]["cgroup_path"]
    cgroup_dir = Path(context["cgroup_start"]["cgroup_directory"])
    _sample(
        resources,
        output_dir,
        "pre_children",
        planned["proof"],
        telemetry_path=planned["telemetry"],
        cgroup_dir=cgroup_dir,
    )
    started = {
        "schema_version": SCHEMA_VERSION,
        "semantics": SEMANTICS,
        "formal_attempt": "a001",
        "started_at_utc": _utc_now(),
        "argv": effective_argv,
        "inputs": context["inputs"],
        "input_copies": copied_inputs,
        "strict_inputs": context["strict_inputs"],
        "evidence": context["evidence"],
        "sources": context["sources"],
        "git_snapshots": context["git_snapshots"],
        "tools_before_execution": context["tools_start"],
        "limits": {
            "proof_limit_bytes": args.proof_limit_bytes,
            "min_free_bytes": args.min_free_bytes,
            "proof_planning_bound_bytes": context["proof_bound_bytes"],
            "preflight_reserved_proof_bytes": args.proof_limit_bytes,
            "preflight_free_bytes": context["preflight_free_bytes"],
            "solver_time_limit_seconds": args.solver_time_limit,
            "solver_wall_timeout_seconds": args.solver_wall_timeout,
            "verifier_wall_timeout_seconds": args.verifier_wall_timeout,
            "translation_gate_wall_timeout_seconds": FORMAL_GATE_WALL_TIMEOUT_SECONDS,
            "monitor_interval_seconds": args.monitor_interval,
        },
        "cgroup": context["cgroup_start"],
        "claim_at_start": "none",
    }
    _exclusive_json(planned["started"], started)

    failures: list[str] = []
    gate_source_path = Path(__file__).with_name(GATE_NAME).resolve(strict=True)
    gate_recheck = _run_child(
        [
            str(Path(sys.executable).resolve(strict=True)),
            str(gate_source_path),
            "--project-root",
            str(context["root"]),
            "--opb",
            str(paths["opb"]),
            "--meta",
            str(paths["meta"]),
            "--var-map",
            str(paths["var_map"]),
            "--estimate",
            str(paths["estimate"]),
            "--output",
            str(planned["gate_recheck"]),
        ],
        stdout_path=planned["gate_recheck_stdout"],
        stderr_path=planned["gate_recheck_stderr"],
        wall_timeout=FORMAL_GATE_WALL_TIMEOUT_SECONDS,
        monitor_interval=args.monitor_interval,
        output_dir=output_dir,
        resources=resources,
        phase="translation_gate_recheck",
        min_free_bytes=args.min_free_bytes,
        telemetry_path=planned["telemetry"],
        expected_cgroup_path=cgroup_path,
    )
    _add_child_failures(failures, gate_recheck, "translation_gate_recheck")
    gate_recheck_file = _optional_file_record(planned["gate_recheck"], context["root"])
    gate_recheck_exact = bool(
        gate_recheck.get("exit_code") == 0
        and gate_recheck.get("termination_reason") is None
        and gate_recheck_file is not None
        and gate_recheck_file["sha256"]
        == context["inputs"]["translation_gate"]["sha256"]
        and gate_recheck_file["size_bytes"]
        == context["inputs"]["translation_gate"]["size_bytes"]
        and planned["gate_recheck"].read_bytes() == paths["translation_gate"].read_bytes()
    )
    if not gate_recheck_exact:
        failures.append("translation_gate_recheck_mismatch")

    version: dict[str, Any] | None = None
    if gate_recheck_exact and not failures:
        version = _run_child(
            [str(paths["veripb"]), "--version"],
            stdout_path=planned["version_stdout"],
            stderr_path=planned["version_stderr"],
            wall_timeout=30.0,
            monitor_interval=args.monitor_interval,
            output_dir=output_dir,
            resources=resources,
            phase="veripb_version",
            min_free_bytes=args.min_free_bytes,
            telemetry_path=planned["telemetry"],
            expected_cgroup_path=cgroup_path,
        )
        _add_child_failures(failures, version, "veripb_version")
    else:
        _exclusive_text(planned["version_stdout"], "")
        _exclusive_text(planned["version_stderr"], "")
    version_exact = bool(
        version is not None
        and _veripb_version_ok(planned["version_stdout"], planned["version_stderr"], version)
    )
    if version is not None and not version_exact:
        failures.append("veripb_version_mismatch")

    formula_hash_before_solver = _sha256(planned["opb"])
    solver: dict[str, Any] | None = None
    if planned["proof"].exists():
        failures.append("proof_preexisted_solver")
    if version_exact and not failures:
        solver = _run_child(
            [
                str(paths["roundingsat"]),
                f"--proof-log={planned['proof']}",
                f"--time-limit={args.solver_time_limit:g}",
                str(planned["opb"]),
            ],
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
            telemetry_path=planned["telemetry"],
            expected_cgroup_path=cgroup_path,
        )
        _add_child_failures(
            failures,
            solver,
            "solver",
            accepted_exit_codes=frozenset({0, 1}),
        )
    else:
        _exclusive_text(planned["solver_stdout"], "")
        _exclusive_text(planned["solver_stderr"], "")

    solver_stdout_status_lines = _status_lines(planned["solver_stdout"])
    solver_stderr_status_lines = _status_lines(planned["solver_stderr"])
    solver_status_lines = solver_stdout_status_lines + solver_stderr_status_lines
    solver_errors = _error_markers(planned["solver_stdout"], planned["solver_stderr"])
    solver_declared_unsat = _stdout_status_exact(
        planned["solver_stdout"], planned["solver_stderr"], "s UNSATISFIABLE"
    )
    tail = _proof_tail(planned["proof"])
    proof_fresh_for_solver = bool(
        solver is not None
        and planned["proof"].is_file()
        and planned["proof"].stat().st_mtime_ns >= solver["started_wall_time_ns"]
    )
    if solver is not None:
        if not solver_declared_unsat:
            failures.append("solver_non_unsat_status")
        if solver_errors:
            failures.append("solver_error_marker")
        if not tail["nonempty"]:
            failures.append("proof_missing")
        elif not tail["complete"]:
            failures.append("proof_truncated")
        if not proof_fresh_for_solver:
            failures.append("proof_not_fresh_for_solver")
    formula_hash_after_solver = _sha256(planned["opb"])
    if formula_hash_after_solver != formula_hash_before_solver:
        failures.append("formula_hash_drift_after_solver")

    proof_hash_before_verifier = _sha256(planned["proof"]) if planned["proof"].is_file() else None
    formula_hash_before_verifier = _sha256(planned["opb"])
    solver_success = bool(
        solver is not None
        and solver.get("exit_code") in (0, 1)
        and solver.get("termination_reason") is None
        and solver_declared_unsat
        and not solver_errors
        and tail["complete"]
        and proof_fresh_for_solver
        and formula_hash_before_solver == formula_hash_after_solver
        and not failures
    )
    verifier: dict[str, Any] | None = None
    if solver_success:
        verifier = _run_child(
            [
                str(paths["veripb"]),
                "--opb",
                "--stats",
                str(planned["opb"]),
                str(planned["proof"]),
            ],
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
            telemetry_path=planned["telemetry"],
            expected_cgroup_path=cgroup_path,
        )
        _add_child_failures(failures, verifier, "verifier")
    else:
        _exclusive_text(planned["verifier_stdout"], "")
        _exclusive_text(planned["verifier_stderr"], "")

    verifier_stdout_status_lines = _status_lines(planned["verifier_stdout"])
    verifier_stderr_status_lines = _status_lines(planned["verifier_stderr"])
    verifier_status_lines = verifier_stdout_status_lines + verifier_stderr_status_lines
    verifier_errors = _error_markers(planned["verifier_stdout"], planned["verifier_stderr"])
    if verifier is not None:
        if not _stdout_status_exact(
            planned["verifier_stdout"],
            planned["verifier_stderr"],
            "s VERIFIED UNSATISFIABLE",
        ):
            failures.append("verifier_non_verified_status")
        if verifier_errors:
            failures.append("verifier_error_marker")
    formula_hash_after_verifier = _sha256(planned["opb"])
    proof_hash_after_verifier = _sha256(planned["proof"]) if planned["proof"].is_file() else None
    hash_stability = (
        formula_hash_before_solver
        == formula_hash_after_solver
        == formula_hash_before_verifier
        == formula_hash_after_verifier
        == copied_inputs["opb"]["sha256"]
        == context["inputs"]["opb"]["sha256"]
        and proof_hash_before_verifier is not None
        and proof_hash_before_verifier == proof_hash_after_verifier
    )
    if not hash_stability:
        failures.append("formula_or_proof_hash_drift")

    tools_end = _tool_records_now(paths, context["root"])
    tools_stable = tools_end == context["tools_start"]
    if not tools_stable:
        failures.append("tool_identity_drift")
    source_end = _source_snapshot(context["root"])
    source_stable = source_end == context["git_snapshots"]["source_surface_start"]
    if not source_stable:
        failures.append("source_state_drift")
    source_paths = {
        "encoder": Path(__file__).with_name(ENCODER_NAME),
        "gate": Path(__file__).with_name(GATE_NAME),
        "runner": Path(__file__),
    }
    source_files_end = {
        name: _optional_file_record(path, context["root"])
        for name, path in source_paths.items()
    }
    source_files_stable = source_files_end == context["sources"]
    if not source_files_stable:
        failures.append("source_file_hash_drift")
    input_end = {
        name: _optional_file_record(paths[name], context["root"])
        for name in ("opb", "meta", "var_map", "estimate", "translation_gate")
    }
    inputs_stable = all(input_end[name] == context["inputs"][name] for name in input_end)
    if not inputs_stable:
        failures.append("input_hash_drift")

    cgroup_end = _cgroup_state(args.expected_systemd_unit, False)
    cgroup_stable = bool(
        cgroup_end["contract_pass"]
        and cgroup_end["cgroup_path"] == context["cgroup_start"]["cgroup_path"]
        and cgroup_end["systemd_properties"] == context["cgroup_start"]["systemd_properties"]
    )
    if not cgroup_stable:
        failures.append("resource_contract_mismatch")
    event_deltas = _event_deltas(
        context["cgroup_start"]["memory_events"], cgroup_end["memory_events"]
    )
    oom_clean = bool(
        event_deltas is not None
        and all(event_deltas.get(key, 0) == 0 for key in OOM_EVENT_KEYS)
    )
    if not oom_clean:
        failures.append("oom_cgroup_event")

    minimum_free = min(sample["free_bytes"] for sample in resources)
    maximum_proof = max(
        (sample["proof_size_bytes"] or 0 for sample in resources),
        default=0,
    )
    if minimum_free < args.min_free_bytes:
        failures.append("disk_low_water")
    if maximum_proof > args.proof_limit_bytes:
        failures.append("proof_size_limit")
    veripb_verified = bool(
        verifier is not None
        and verifier.get("exit_code") == 0
        and verifier.get("termination_reason") is None
        and _stdout_status_exact(
            planned["verifier_stdout"],
            planned["verifier_stderr"],
            "s VERIFIED UNSATISFIABLE",
        )
        and not verifier_errors
    )

    telemetry_record = _file_record(planned["telemetry"], context["root"])
    proof_record = _optional_file_record(planned["proof"], context["root"])
    artifact_manifest = _write_checksum_manifest(output_dir, planned["checksums"])
    artifact_manifest_stable = _checksum_manifest_stable(
        output_dir, planned["checksums"], artifact_manifest
    )
    manifest_entries = artifact_manifest["entries"]
    critical_manifest_hashes_match = bool(
        manifest_entries.get(planned["opb"].name) == formula_hash_after_verifier
        and proof_hash_after_verifier is not None
        and manifest_entries.get(planned["proof"].name) == proof_hash_after_verifier
        and manifest_entries.get(planned["telemetry"].name) == telemetry_record["sha256"]
        and gate_recheck_file is not None
        and manifest_entries.get(planned["gate_recheck"].name)
        == gate_recheck_file["sha256"]
        and all(
            manifest_entries.get(planned[planned_name].name)
            == copied_inputs[source_name]["sha256"]
            for source_name, planned_name in {
                "opb": "opb",
                "meta": "meta",
                "var_map": "var_map",
                "estimate": "estimate",
                "translation_gate": "gate",
            }.items()
        )
        and all(
            manifest_entries.get(Path(child[stream]["path"]).name)
            == child[stream]["sha256"]
            for child in (gate_recheck, version, solver, verifier)
            if child is not None
            for stream in ("stdout", "stderr")
        )
    )
    if not artifact_manifest_stable:
        failures.append("artifact_manifest_recheck_failed")
    if not critical_manifest_hashes_match:
        failures.append("artifact_manifest_critical_hash_mismatch")
    failures = list(dict.fromkeys(failures))
    claim = (
        "machine_verified_lex_better_arithmetic_band_unsat_given_r3_geometric_lemmas"
        if not failures and solver_success and veripb_verified
        else "none"
    )
    record = {
        "schema_version": SCHEMA_VERSION,
        "semantics": SEMANTICS,
        "formal_attempt": "a001",
        "started_at_utc": started["started_at_utc"],
        "finished_at_utc": _utc_now(),
        "argv": effective_argv,
        "inputs": context["inputs"],
        "input_copies": copied_inputs,
        "inputs_after_execution": input_end,
        "inputs_stable": inputs_stable,
        "strict_inputs": context["strict_inputs"],
        "evidence": context["evidence"],
        "sources": {
            "before": context["sources"],
            "after": source_files_end,
            "stable": source_files_stable,
        },
        "git_snapshots": {
            **context["git_snapshots"],
            "source_surface_end": source_end,
            "source_surface_stable": source_stable,
        },
        "tools": {
            "before": context["tools_start"],
            "after": tools_end,
            "stable": tools_stable,
            "veripb_version_exact": version_exact,
            "veripb_version_probe": version,
        },
        "execution": started["limits"],
        "solver": {
            "run": solver,
            "status_lines": solver_status_lines,
            "stdout_status_lines": solver_stdout_status_lines,
            "stderr_status_lines": solver_stderr_status_lines,
            "error_markers": solver_errors,
            "declared_unsat": solver_declared_unsat,
        },
        "proof": {
            "file": proof_record,
            "tail": tail,
            "fresh_for_solver": proof_fresh_for_solver,
            "sha256_before_verifier": proof_hash_before_verifier,
            "sha256_after_verifier": proof_hash_after_verifier,
        },
        "verifier": {
            "run": verifier,
            "status_lines": verifier_status_lines,
            "stdout_status_lines": verifier_stdout_status_lines,
            "stderr_status_lines": verifier_stderr_status_lines,
            "error_markers": verifier_errors,
            "verified_unsat": veripb_verified,
        },
        "hash_stability": {
            "formula_before_solver": formula_hash_before_solver,
            "formula_after_solver": formula_hash_after_solver,
            "formula_before_verifier": formula_hash_before_verifier,
            "formula_after_verifier": formula_hash_after_verifier,
            "proof_before_verifier": proof_hash_before_verifier,
            "proof_after_verifier": proof_hash_after_verifier,
            "stable": hash_stability,
        },
        "translation_gate": {
            "file": context["inputs"]["translation_gate"],
            "status": context["gate"]["status"],
            "corpus_errors": context["gate"]["corpus_errors"],
            "checks": context["gate"]["checks"],
            "recheck_run": gate_recheck,
            "recheck_file": gate_recheck_file,
            "recheck_byte_exact": gate_recheck_exact,
        },
        "artifact_manifest": {
            **artifact_manifest,
            "stable_recheck": artifact_manifest_stable,
            "critical_hashes_match": critical_manifest_hashes_match,
        },
        "resource_monitor": {
            "schema_version": RESOURCE_SCHEMA,
            "file": telemetry_record,
            "sample_count": len(resources),
            "minimum_free_bytes_observed": minimum_free,
            "maximum_proof_bytes_observed": maximum_proof,
            "cgroup_start": context["cgroup_start"],
            "cgroup_end": cgroup_end,
            "cgroup_stable": cgroup_stable,
            "memory_event_deltas": event_deltas,
            "oom_clean": oom_clean,
        },
        "failure_codes": failures,
        "solver_declared_unsat": solver_declared_unsat,
        "proof_tail_complete": tail["complete"],
        "veripb_verified": veripb_verified,
        "claim": claim,
        "claim_boundary": {
            "research_grade": True,
            "verified_component": (
                "the independently translation-gated oriented lex-better dimension OPB is UNSAT"
            ),
            "assumption": (
                "the R3 membrane, incidence-cap, and power-halo geometric lemmas are given"
            ),
            "does_not_prove": [
                "the R3 geometric lemmas inside the PB proof",
                "a witness or lower bound",
                "attainability of (1190,34)",
                "global optimality",
            ],
            "lower_bound_ledger": "absent_and_unrelated",
            "production_status": "not_applicable",
            "next_track": "B1_not_started",
        },
    }
    _exclusive_json(planned["record"], record)
    print(
        json.dumps(
            {
                "claim": claim,
                "failure_codes": failures,
                "record": str(planned["record"]),
            },
            sort_keys=True,
        )
    )
    return 0 if claim != "none" else 1


def _persistent_failure_marker(
    args: argparse.Namespace,
    *,
    failure_code: str,
    error: str,
    signum: int | None = None,
    filename: str = "toolchain_failed.json",
) -> None:
    """Best-effort persistent no-claim marker after child cleanup has completed."""
    try:
        output_dir = args.output_dir.resolve(strict=True)
        output_dir.relative_to(ARTIFACT_ROOT.resolve(strict=False))
        if not output_dir.is_dir() or (output_dir / "toolchain_record.json").exists():
            return
        payload: dict[str, Any] = {
            "schema_version": "r3_upper_bound_pb_failure_v1",
            "recorded_at_utc": _utc_now(),
            "claim": "none",
            "failure_code": failure_code,
            "error": error,
        }
        if signum is not None:
            payload["signal"] = signum
        _exclusive_json(
            output_dir / filename,
            payload,
        )
    except (OSError, ToolchainError, ValueError):
        return


def main(argv: Sequence[str] | None = None) -> int:
    effective = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(effective)
    lock_dir = Path(f"/run/user/{os.getuid()}")
    lock_path = lock_dir / SINGLETON_LOCK_NAME
    try:
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    except OSError as exc:
        print(
            json.dumps(
                {
                    "claim": "none",
                    "failure_code": "singleton_lock_failure",
                    "error": f"cannot open {lock_path}: {exc}",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(
                json.dumps(
                    {
                        "claim": "none",
                        "failure_code": "singleton_lock_busy",
                        "error": f"another prod-scale worker owns {lock_path}",
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
        previous_handlers = {
            signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)
        }

        def interrupt(signum: int, _frame: Any) -> None:
            raise ToolchainInterrupted(signum)

        for signum in previous_handlers:
            signal.signal(signum, interrupt)
        try:
            return _execute(args, [str(Path(__file__).resolve()), *effective])
        except ToolchainInterrupted as exc:
            _persistent_failure_marker(
                args,
                failure_code="toolchain_interrupted",
                error=str(exc),
                signum=exc.signum,
                filename="toolchain_interrupted.json",
            )
            print(
                json.dumps(
                    {
                        "claim": "none",
                        "failure_code": "toolchain_interrupted",
                        "signal": exc.signum,
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 130 if exc.signum == signal.SIGINT else 128 + exc.signum
        except ToolchainError as exc:
            _persistent_failure_marker(
                args,
                failure_code=exc.code,
                error=str(exc),
            )
            print(
                json.dumps(
                    {"claim": "none", "failure_code": exc.code, "error": str(exc)},
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
        except (FileNotFoundError, FileExistsError, OSError, subprocess.SubprocessError) as exc:
            _persistent_failure_marker(
                args,
                failure_code="unclassified_runtime_error",
                error=f"{type(exc).__name__}: {exc}",
            )
            print(
                json.dumps(
                    {
                        "claim": "none",
                        "failure_code": "unclassified_runtime_error",
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
        except Exception as exc:
            _persistent_failure_marker(
                args,
                failure_code="unexpected_runtime_error",
                error=f"{type(exc).__name__}: {exc}",
            )
            print(
                json.dumps(
                    {
                        "claim": "none",
                        "failure_code": "unexpected_runtime_error",
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
        finally:
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
    finally:
        os.close(lock_fd)


if __name__ == "__main__":
    raise SystemExit(main())
