"""Run the research-only B1 ``(1188,22)`` RoundingSat -> VeriPB chain.

This target-specific runner accepts only the independently translation-gated
complete oriented lex-better band whose geometric premises were admitted by
the byte-locked R4 a004 authority chain.  It replays that authority, pins every
formal tool and input identity, requires the approved cgroup contract, refuses
every overwrite, and records raw child output plus resource telemetry.  A
successful run establishes only that this PB band is inconsistent given those
admitted premises; it says nothing about a witness or attainability.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from types import ModuleType
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[3]

SCHEMA_VERSION = "b1_r4_1188_22_pb_toolchain_run_v1"
RESOURCE_SCHEMA = "b1_r4_1188_22_pb_resource_monitor_v1"
SEMANTICS = "b1_r4_1188_22_complete_oriented_lex_better_band_given_a004_admitted_lemmas_v1"
MODEL_SCHEMA = "b1_r4_1188_22_pb_v1"
METADATA_SCHEMA = "b1_r4_1188_22_pb_metadata_v1"
VAR_MAP_SCHEMA = "b1_r4_1188_22_pb_var_map_v1"
ESTIMATE_SCHEMA = "b1_r4_1188_22_pb_estimate_v1"
GATE_SCHEMA = "b1_r4_1188_22_pb_translation_gate_v1"
BUILD_RECORD_SCHEMA = "b1_r4_1188_22_pb_build_record_v1"
AUTHORITY_RECEIPT_SCHEMA = "b1_r4_1188_22_pb_authority_receipt_v1"
ENCODER_NAME = "b1_r4_1188_22_pb_encoder_v1.py"
GATE_NAME = "verify_b1_r4_1188_22_pb_translation_v1.py"
RUNNER_NAME = "run_b1_r4_1188_22_pb_toolchain_v1.py"

FORMAL_PROOF_LIMIT_BYTES = 5_000_000_000
FORMAL_MIN_FREE_BYTES = 10_737_418_240
FORMAL_SOLVER_TIME_LIMIT_SECONDS = 3_600
FORMAL_SOLVER_WALL_TIMEOUT_SECONDS = 3_900
FORMAL_VERIFIER_WALL_TIMEOUT_SECONDS = 3_600
FORMAL_MONITOR_INTERVAL_SECONDS = 1
FORMAL_GATE_WALL_TIMEOUT_SECONDS = 300
FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES = FORMAL_MIN_FREE_BYTES + FORMAL_PROOF_LIMIT_BYTES

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
EXPECTED_PYTHON_PATH = PROJECT_ROOT / ".venv-uvbolt-backup/bin/python"
EXPECTED_PYTHON_SHA256 = "74fceb0fdd29c31cf066ac8d92465975ea4ac8592308d7c888e26a70092d8eeb"
EXPECTED_PROJECT_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
ARTIFACT_EXCLUSION = ".artifacts/track_b_b1_r4_1188_22_pb_20260723/**"

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "track_b_b1_r4_1188_22_pb_20260723"
SINGLETON_LOCK_NAME = "zmd_pj_prod_scale_solver.lock"
ATTEMPT_MARKER_NAME = "formal_attempt_a001.reservation.json"

REQUIRED_GATE_CHECKS = frozenset(
    {
        "a004_admission_replay_pass",
        "strict_bundle_closed_and_hashed",
        "encoder_provenance_match",
        "translation_inputs_closed_and_hashed",
        "metadata_reconstruction_match",
        "estimate_reconstruction_match",
        "variable_map_dense",
        "variable_map_exact",
        "opb_header_exact",
        "constraint_multiset_exact",
        "strict_sentinels_exact",
        "ordinary_membrane_exact",
        "power_halo_exact",
        "marked_terminal_census_exact",
        "access_cell_enumeration_exact",
        "marked_membrane_exact",
        "boundary_packing_exact",
        "lex_better_band_exact",
        "complete_band_corpus_unsat",
        "semantic_canaries_pass",
    }
)

INPUT_PATHS = {
    "problem_instance": ("docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"),
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

A004_AUTHORITY_RUN = (
    PROJECT_ROOT / ".artifacts/track_b_r4_external_brain_handoff_20260722" / "run-20260722T084343Z-R4hP1A"
)
A004_RESPONSE_RUN = (
    PROJECT_ROOT
    / ".artifacts/track_b_r4_external_brain_handoff_20260722/responses"
    / "run-20260723T023657Z-R4resp-357f260d"
)
A004_LEDGER = A004_RESPONSE_RUN / "claims/a004/quantitative-claim-ledger.json"
A004_REPORTS = (
    A004_RESPONSE_RUN / "recomputations/upper-counts-a004/report.json",
    A004_RESPONSE_RUN / "recomputations/marked-geometry-a004/report.json",
    A004_RESPONSE_RUN / "recomputations/w2d-audit-a004/report.json",
)
A004_VERDICT = A004_RESPONSE_RUN / "adversarial/a004/verdict.json"
A004_ADMISSION = A004_RESPONSE_RUN / "admission/a004/admission.json"
A004_REPLAY_TOOL = (
    PROJECT_ROOT / "docs/research/r4_response_review_20260723" / "close_r4_response_candidate_admission_v2.py"
)
A004_REPLAY_TOOL_SIZE = 17_955
A004_REPLAY_TOOL_SHA256 = "cf47cc662e3c3cf6e7e13915869866a09067854b837a5a775bdf8504dfd3f5d5"
A004_ADMISSION_SIZE = 10_273
A004_ADMISSION_SHA256 = "2ebceb7bcdf93ad8cffa75e49eef89af679729f64a47a06ae27fa44682c206ff"
A004_UPPER_CANDIDATE = "upper_bound_1188_22"
A004_FALSE_AUTHORIZATIONS = frozenset(
    {
        "formal_run_authorized",
        "encoder_execution_authorized",
        "solver_run_authorized",
        "search_run_authorized",
        "assembly_run_authorized",
        "router_run_authorized",
        "track_w_execution_authorized",
    }
)
A004_FALSE_FIELDS = frozenset(
    {
        "upper_bound_changed",
        *A004_FALSE_AUTHORIZATIONS,
        "external_response_code_executed",
        "witness_established",
        "attainability_established",
        "optimality_established",
        "global_infeasibility_established",
        "production_certified",
    }
)
FORMAL_OUTPUT_RE = re.compile(r"formal-a001-[0-9]{8}T[0-9]{6}Z-398f8725")
BUILD_OUTPUT_RE = re.compile(r"build-a001-[0-9]{8}T[0-9]{6}Z-398f8725")
BUILD_PAYLOAD_NAMES = frozenset(
    {
        "estimate.json",
        "formula.opb",
        "encoder.meta.json",
        "variable_map.json",
        "translation_gate.json",
        "estimate.stdout.txt",
        "estimate.stderr.txt",
        "encode.stdout.txt",
        "encode.stderr.txt",
        "translation_gate.stdout.txt",
        "translation_gate.stderr.txt",
    }
)

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


class ToolchainInterrupted(BaseException):
    """A caught operator/service signal that must cross broad Exception guards."""

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


def _absolute_file_record(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ToolchainError("not_provenance_file", f"not a provenance file: {resolved}")
    return {
        "path": str(resolved),
        "sha256": _sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _type_exact_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(_type_exact_equal(actual[key], expected[key]) for key in expected)
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _type_exact_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def _optional_file_record(path: Path, project_root: Path) -> dict[str, Any] | None:
    try:
        return _file_record(path, project_root)
    except (OSError, ToolchainError):
        return None


def _strict_json_loads(raw: str, label: str) -> Any:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ToolchainError("invalid_json", f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ToolchainError("invalid_json", f"{label} contains non-finite number {value}")

    def invalid_float(value: str) -> Any:
        raise ToolchainError("invalid_json", f"{label} contains floating-point number {value}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
            parse_float=invalid_float,
        )
    except ToolchainError:
        raise
    except json.JSONDecodeError as exc:
        raise ToolchainError("invalid_json", f"cannot parse {label}: {exc}") from exc


def _strict_json(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ToolchainError("invalid_json", f"cannot load {label}: {exc}") from exc
    payload = _strict_json_loads(raw, label)
    if not isinstance(payload, dict):
        raise ToolchainError("invalid_json", f"{label} must be a JSON object")
    return payload


def _canonical_regular_file(path: Path, label: str) -> Path:
    absolute = path.absolute()
    try:
        mode = absolute.lstat().st_mode
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise ToolchainError(
            "a004_authority_failure",
            f"cannot resolve {label}: {exc}",
        ) from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode) or resolved != absolute:
        raise ToolchainError(
            "a004_authority_failure",
            f"{label} is not a canonical non-symlink regular file",
        )
    return resolved


def _canonical_existing_directory(path: Path, label: str) -> Path:
    absolute = path.absolute()
    try:
        mode = absolute.lstat().st_mode
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise ToolchainError(
            "output_path_invalid",
            f"cannot resolve {label}: {exc}",
        ) from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode) or resolved != absolute:
        raise ToolchainError(
            "output_path_invalid",
            f"{label} is not a canonical non-symlink directory",
        )
    return resolved


@contextmanager
def _no_bytecode_writes() -> Iterator[None]:
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.dont_write_bytecode = previous


def _load_a004_replay_tool() -> ModuleType:
    tool = _canonical_regular_file(A004_REPLAY_TOOL, "a004 replay tool")
    if tool.stat().st_size != A004_REPLAY_TOOL_SIZE or _sha256(tool) != A004_REPLAY_TOOL_SHA256:
        raise ToolchainError(
            "a004_authority_failure",
            "a004 replay tool size or SHA-256 drifted",
        )
    module_name = "b1_r4_1188_22_a004_replay_tool"
    spec = importlib.util.spec_from_file_location(module_name, tool)
    if spec is None or spec.loader is None:
        raise ToolchainError(
            "a004_authority_failure",
            "cannot construct the a004 admission replay module",
        )
    module = importlib.util.module_from_spec(spec)
    try:
        with _no_bytecode_writes():
            spec.loader.exec_module(module)
    except Exception as exc:
        raise ToolchainError(
            "a004_authority_failure",
            f"cannot load the a004 admission replay tool: {exc}",
        ) from exc
    return module


def _a004_authority_replay(root: Path) -> dict[str, Any]:
    """Replay a004 completely and close the exact B1-design admission semantics."""
    admission_path = _canonical_regular_file(A004_ADMISSION, "a004 admission")
    admission_record = _file_record(admission_path, root)
    if admission_record["size_bytes"] != A004_ADMISSION_SIZE or admission_record["sha256"] != A004_ADMISSION_SHA256:
        raise ToolchainError(
            "a004_authority_failure",
            "a004 admission size or SHA-256 drifted",
        )
    module = _load_a004_replay_tool()
    replay = getattr(module, "replay_admission", None)
    if not callable(replay):
        raise ToolchainError(
            "a004_authority_failure",
            "a004 replay tool lacks callable replay_admission",
        )
    try:
        with _no_bytecode_writes():
            value = replay(
                A004_AUTHORITY_RUN,
                A004_RESPONSE_RUN,
                A004_LEDGER,
                A004_REPORTS,
                A004_VERDICT,
                admission_path,
            )
    except Exception as exc:
        raise ToolchainError(
            "a004_authority_failure",
            f"complete a004 admission replay failed: {exc}",
        ) from exc
    if (
        not isinstance(value, Mapping)
        or set(value) != {"admission", "verdict_replay", "admission_record"}
        or not isinstance(value["admission"], Mapping)
        or not isinstance(value["verdict_replay"], Mapping)
        or not isinstance(value["admission_record"], Mapping)
    ):
        raise ToolchainError(
            "a004_authority_failure",
            "complete a004 replay returned a malformed closed context",
        )
    replay_record = value["admission_record"]
    if (
        replay_record.get("size_bytes") != A004_ADMISSION_SIZE
        or replay_record.get("sha256") != A004_ADMISSION_SHA256
        or Path(str(replay_record.get("path"))).resolve(strict=True) != admission_path
    ):
        raise ToolchainError(
            "a004_authority_failure",
            "a004 replay did not bind the fixed admission bytes",
        )
    admission = dict(value["admission"])
    candidate = admission.get("candidates", {}).get(A004_UPPER_CANDIDATE)
    if (
        admission.get("schema") != "r4_response_candidate_admission_v2"
        or admission.get("status") != "PARTIAL"
        or candidate
        != {
            "verdict": "PASS",
            "research_followup_admitted": True,
            "b1_followup_input_admitted": True,
            "proposed_upper_ledger": [1188, 22],
        }
        or admission.get("current_project_ledger") != {"U": [1190, 34], "L": "absent"}
        or any(admission.get(name) is not False for name in A004_FALSE_FIELDS)
    ):
        raise ToolchainError(
            "a004_authority_failure",
            "a004 admission does not have the fixed B1-design-only semantics",
        )
    replay_tool_path = _canonical_regular_file(A004_REPLAY_TOOL, "a004 replay tool")
    replay_tool_record = {
        "path": str(replay_tool_path),
        "sha256": _sha256(replay_tool_path),
        "size_bytes": replay_tool_path.stat().st_size,
    }
    absolute_admission_record = {
        "path": str(admission_path),
        "sha256": admission_record["sha256"],
        "size_bytes": admission_record["size_bytes"],
    }
    encoder_binding = {
        "admission": absolute_admission_record,
        "admission_closer": replay_tool_record,
        "replay_summary": {
            "status": admission["status"],
            "upper_candidate": candidate,
            "current_project_ledger": admission["current_project_ledger"],
            "false_fields": {name: admission[name] for name in sorted(A004_FALSE_FIELDS)},
        },
    }
    return {
        "status": "PASS",
        "admission": admission,
        "admission_record": admission_record,
        "replay_tool": _file_record(replay_tool_path, root),
        "ledger": _file_record(A004_LEDGER, root),
        "reports": [_file_record(path, root) for path in A004_REPORTS],
        "verdict": _file_record(A004_VERDICT, root),
        "authority_run": str(A004_AUTHORITY_RUN.resolve(strict=True)),
        "response_run": str(A004_RESPONSE_RUN.resolve(strict=True)),
        "replay_result_keys": sorted(value),
        "encoder_binding": encoder_binding,
    }


def _require_a004_unchanged(
    expected: Mapping[str, Any],
    root: Path,
    phase: str,
) -> dict[str, Any]:
    current = _a004_authority_replay(root)
    if current != dict(expected):
        raise ToolchainError(
            "a004_authority_drift",
            f"a004 authority changed at {phase}",
        )
    return current


def _require_file_identity(
    path: Path,
    expected: Mapping[str, Any],
    root: Path,
    phase: str,
    failure_code: str,
) -> dict[str, Any]:
    current = _file_record(path, root)
    if not _type_exact_equal(current, dict(expected)):
        raise ToolchainError(
            failure_code,
            f"file identity drifted at {phase}: {path}",
        )
    return current


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
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
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
        ".",
        f":(exclude){ARTIFACT_EXCLUSION}",
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
        f":(exclude){ARTIFACT_EXCLUSION}",
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
        "artifact_exclusion": ARTIFACT_EXCLUSION,
    }


def _source_snapshot(repo: Path) -> dict[str, Any]:
    """Snapshot source state while excluding this run's permitted artifact root."""
    head = str(_git_command(repo, "rev-parse", "HEAD"))
    exclude = f":(exclude){ARTIFACT_EXCLUSION}"
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
        "artifact_exclusion": ARTIFACT_EXCLUSION,
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
        "artifact_exclusion",
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
    artifact_exclusion = value["artifact_exclusion"]
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
    if artifact_exclusion != ARTIFACT_EXCLUSION:
        raise ToolchainError(
            "git_snapshot_invalid",
            f"{label}.artifact_exclusion is invalid",
        )
    return dict(value)


def _validate_file_record(value: Any, expected: Path, root: Path, label: str) -> dict[str, Any]:
    current = _file_record(expected, root)
    if not isinstance(value, Mapping) or not _type_exact_equal(dict(value), current):
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


def _build_manifest_report(
    manifest_path: Path,
    build_dir: Path,
) -> dict[str, Any]:
    try:
        raw = manifest_path.read_bytes()
        text = raw.decode("ascii")
    except (OSError, UnicodeError) as exc:
        raise ToolchainError(
            "build_authority_failure",
            f"cannot read build manifest: {exc}",
        ) from exc
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in text.splitlines(keepends=True):
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)\n", line)
        if match is None or match.group(2) in seen:
            raise ToolchainError(
                "build_authority_failure",
                "build manifest is malformed or duplicated",
            )
        digest, name = match.groups()
        seen.add(name)
        path = _canonical_regular_file(
            build_dir / name,
            f"build payload {name}",
        )
        if path.parent != build_dir or _sha256(path) != digest:
            raise ToolchainError(
                "build_authority_failure",
                f"build payload hash or path drifted for {name}",
            )
        entries.append(
            {
                "path": name,
                "sha256": digest,
                "size_bytes": path.stat().st_size,
            }
        )
    names = [entry["path"] for entry in entries]
    if names != sorted(BUILD_PAYLOAD_NAMES):
        raise ToolchainError(
            "build_authority_failure",
            "build manifest does not enumerate the exact fixed payload",
        )
    current_names = {path.name for path in build_dir.iterdir()}
    if current_names != BUILD_PAYLOAD_NAMES | {"SHA256SUMS", "build_record.json"}:
        raise ToolchainError(
            "build_authority_failure",
            "build attempt has a missing or unexpected member",
        )
    return {
        "file": _absolute_file_record(manifest_path),
        "covered_files": names,
        "entries": entries,
        "excluded_to_avoid_hash_cycle": [
            "SHA256SUMS",
            "build_record.json",
        ],
    }


def _validate_build_authority(
    paths: Mapping[str, Path],
    root: Path,
) -> dict[str, Any]:
    build_record_path = _canonical_regular_file(
        paths["build_record"],
        "build record",
    )
    build_manifest_path = _canonical_regular_file(
        paths["build_manifest"],
        "build manifest",
    )
    build_dir = _canonical_existing_directory(
        build_record_path.parent,
        "build attempt",
    )
    if (
        build_manifest_path.parent != build_dir
        or build_record_path.name != "build_record.json"
        or build_manifest_path.name != "SHA256SUMS"
        or BUILD_OUTPUT_RE.fullmatch(build_dir.name) is None
        or build_dir.parent
        != _canonical_existing_directory(
            ARTIFACT_ROOT,
            "formal artifact root",
        )
    ):
        raise ToolchainError(
            "build_authority_failure",
            "build record/manifest are not the pinned direct-child attempt",
        )
    expected_output_names = {
        "estimate": "estimate.json",
        "opb": "formula.opb",
        "meta": "encoder.meta.json",
        "var_map": "variable_map.json",
        "gate": "translation_gate.json",
    }
    for formal_name, file_name in expected_output_names.items():
        path = _canonical_regular_file(
            paths["translation_gate" if formal_name == "gate" else formal_name],
            f"build output {formal_name}",
        )
        if path != build_dir / file_name:
            raise ToolchainError(
                "build_authority_failure",
                f"formal {formal_name} is not the selected build output",
            )

    manifest = _build_manifest_report(build_manifest_path, build_dir)
    record = _strict_json(build_record_path, "build record")
    expected_record_keys = {
        "schema_version",
        "semantics",
        "status",
        "created_at_utc",
        "argv",
        "project_root",
        "git_head",
        "attempt",
        "sources",
        "runs",
        "outputs",
        "manifest",
        "claim",
        "formal_run_authorized",
        "proof_status",
    }
    if set(record) != expected_record_keys:
        raise ToolchainError(
            "build_authority_failure",
            "build record key set drifted",
        )
    if (
        record.get("schema_version") != BUILD_RECORD_SCHEMA
        or record.get("semantics") != SEMANTICS
        or record.get("status") != "PASS"
        or record.get("project_root") != str(root)
        or record.get("git_head") != EXPECTED_PROJECT_HEAD
        or record.get("attempt") != build_dir.name
        or record.get("claim") != "none"
        or record.get("formal_run_authorized") is not False
        or record.get("proof_status") != "build_and_translation_only_no_unsat_or_proof_claim"
        or not _type_exact_equal(record.get("manifest"), manifest)
    ):
        raise ToolchainError(
            "build_authority_failure",
            "build record status, claim boundary, or manifest binding drifted",
        )
    encoder = Path(__file__).with_name(ENCODER_NAME).resolve(strict=True)
    gate_source = Path(__file__).with_name(GATE_NAME).resolve(strict=True)
    fixed_python_invocation = EXPECTED_PYTHON_PATH.absolute()
    fixed_python = EXPECTED_PYTHON_PATH.resolve(strict=True)
    expected_sources = {
        "encoder": _absolute_file_record(encoder),
        "translation_gate": _absolute_file_record(gate_source),
        "python_invocation_path": str(fixed_python_invocation),
        "python": _absolute_file_record(fixed_python),
    }
    if not _type_exact_equal(record.get("sources"), expected_sources):
        raise ToolchainError(
            "build_authority_failure",
            "build builder or Python identity drifted",
        )
    expected_outputs = {
        name: _absolute_file_record(build_dir / file_name) for name, file_name in sorted(expected_output_names.items())
    }
    if not _type_exact_equal(record.get("outputs"), expected_outputs):
        raise ToolchainError(
            "build_authority_failure",
            "build record output identities drifted",
        )

    expected_run_specs = [
        (
            "estimate",
            [
                str(fixed_python_invocation),
                "-B",
                str(encoder),
                "estimate",
                "--project-root",
                str(root),
                "--output",
                str(build_dir / "estimate.json"),
                "--proof-limit-bytes",
                str(FORMAL_PROOF_LIMIT_BYTES),
            ],
        ),
        (
            "encode",
            [
                str(fixed_python_invocation),
                "-B",
                str(encoder),
                "encode",
                "--project-root",
                str(root),
                "--estimate",
                str(build_dir / "estimate.json"),
                "--opb-out",
                str(build_dir / "formula.opb"),
                "--meta-out",
                str(build_dir / "encoder.meta.json"),
                "--var-map-out",
                str(build_dir / "variable_map.json"),
            ],
        ),
        (
            "translation_gate",
            [
                str(fixed_python_invocation),
                "-B",
                str(gate_source),
                "--project-root",
                str(root),
                "--opb",
                str(build_dir / "formula.opb"),
                "--meta",
                str(build_dir / "encoder.meta.json"),
                "--var-map",
                str(build_dir / "variable_map.json"),
                "--estimate",
                str(build_dir / "estimate.json"),
                "--output",
                str(build_dir / "translation_gate.json"),
            ],
        ),
    ]
    runs = record.get("runs")
    if not isinstance(runs, list) or len(runs) != len(expected_run_specs):
        raise ToolchainError(
            "build_authority_failure",
            "build record must contain exactly three child runs",
        )
    for run, (stage, expected_argv) in zip(runs, expected_run_specs):
        expected_keys = {
            "stage",
            "argv",
            "return_code",
            "timed_out",
            "started_wall_time_ns",
            "finished_wall_time_ns",
            "stdout",
            "stderr",
        }
        if not isinstance(run, Mapping) or set(run) != expected_keys:
            raise ToolchainError(
                "build_authority_failure",
                f"build {stage} child record shape drifted",
            )
        if (
            run.get("stage") != stage
            or not _type_exact_equal(run.get("argv"), expected_argv)
            or type(run.get("return_code")) is not int
            or run.get("return_code") != 0
            or run.get("timed_out") is not False
            or type(run.get("started_wall_time_ns")) is not int
            or type(run.get("finished_wall_time_ns")) is not int
            or run["finished_wall_time_ns"] < run["started_wall_time_ns"]
            or not _type_exact_equal(
                run.get("stdout"),
                _absolute_file_record(build_dir / f"{stage}.stdout.txt"),
            )
            or not _type_exact_equal(
                run.get("stderr"),
                _absolute_file_record(build_dir / f"{stage}.stderr.txt"),
            )
        ):
            raise ToolchainError(
                "build_authority_failure",
                f"build {stage} child execution did not close",
            )
    expected_build_argv = [
        str(encoder),
        "build",
        "--project-root",
        str(root),
        "--gate-script",
        str(gate_source),
        "--output-dir",
        str(build_dir),
        "--proof-limit-bytes",
        str(FORMAL_PROOF_LIMIT_BYTES),
    ]
    if not _type_exact_equal(record.get("argv"), expected_build_argv):
        raise ToolchainError(
            "build_authority_failure",
            "build top-level argv drifted",
        )
    return {
        "directory": str(build_dir),
        "record": _absolute_file_record(build_record_path),
        "manifest": manifest,
        "payload": {
            entry["path"]: {
                "path": str(build_dir / entry["path"]),
                "sha256": entry["sha256"],
                "size_bytes": entry["size_bytes"],
            }
            for entry in manifest["entries"]
        },
        "status": "PASS",
        "formal_authorization": "downstream_runner_must_replay_this_exact_authority",
    }


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
        type(relative) is str and type(expected_unit) is str and expected_unit and Path(relative).name == expected_unit
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
    cgroup_dir = Path("/sys/fs/cgroup") / str(relative).lstrip("/") if isinstance(relative, str) else None
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
        "expected_unit_is_cgroup_leaf": _expected_unit_is_cgroup_leaf(relative, expected_unit),
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
        "monotonic_nanoseconds": time.monotonic_ns(),
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
    started_monotonic_ns = time.monotonic_ns()
    started = time.monotonic()
    termination_reason: str | None = None
    spawn_error: str | None = None
    child_cgroup: dict[str, Any] | None = None
    process: subprocess.Popen[Any] | None = None
    process_group_clean = True
    completion_cgroup_procs: list[str] = []
    with (
        stdout_path.open("x", encoding="utf-8", newline="\n") as stdout_handle,
        stderr_path.open("x", encoding="utf-8", newline="\n") as stderr_handle,
    ):
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
                if expected_cgroup_path is not None and child_cgroup.get("unified_path") != expected_cgroup_path:
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
                    if expected_cgroup_path is not None and active_child.get("unified_path") != expected_cgroup_path:
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
                    active_pid=None,
                )
                completion_free = resources[-1]["free_bytes"]
                completion_proof = resources[-1]["proof_size_bytes"]
                cgroup_sample = resources[-1]["cgroup"]
                completion_cgroup_procs = cgroup_sample["cgroup_procs"] if cgroup_sample else []
                unexpected_procs = {pid for pid in completion_cgroup_procs if pid != str(os.getpid())}
                if termination_reason is None and unexpected_procs:
                    termination_reason = "child_cgroup_not_clean_at_completion"
                elif termination_reason is None and completion_free < min_free_bytes:
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
        finally:
            if process is not None and _process_group_exists(process.pid):
                process_group_clean = _terminate_group(process)
    finished_wall_time_ns = time.time_ns()
    return {
        "argv": command,
        "started_at_utc": started_at_utc,
        "started_wall_time_ns": started_wall_time_ns,
        "finished_at_utc": _utc_now(),
        "finished_wall_time_ns": finished_wall_time_ns,
        "exit_code": exit_code,
        "timed_out": termination_reason == "wall_timeout",
        "termination_reason": termination_reason,
        "spawn_error": spawn_error,
        "elapsed_nanoseconds": max(0, time.monotonic_ns() - started_monotonic_ns),
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
    parser.add_argument("--build-record", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--roundingsat", type=Path, required=True)
    parser.add_argument("--roundingsat-repo", type=Path, required=True)
    parser.add_argument("--veripb", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--solver-time-limit", type=int, required=True)
    parser.add_argument("--solver-wall-timeout", type=int, required=True)
    parser.add_argument("--verifier-wall-timeout", type=int, required=True)
    parser.add_argument("--proof-limit-bytes", type=int, required=True)
    parser.add_argument("--min-free-bytes", type=int, required=True)
    parser.add_argument("--monitor-interval", type=int, required=True)
    parser.add_argument("--expected-systemd-unit")
    parser.add_argument("--require-cgroup-contract", action="store_true")
    return parser


def _validate_exact_runtime_contract(args: argparse.Namespace) -> None:
    if Path(sys.executable).resolve() != EXPECTED_PYTHON_PATH.resolve(strict=True):
        raise ToolchainError(
            "runtime_contract_mismatch",
            f"formal B1 must use the pinned interpreter {EXPECTED_PYTHON_PATH}",
        )
    if _sha256(Path(sys.executable).resolve(strict=True)) != EXPECTED_PYTHON_SHA256:
        raise ToolchainError(
            "tool_identity_drift",
            "pinned Python interpreter SHA-256 drifted",
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
        if type(value) is not int or value != expected:
            raise ToolchainError(
                "runtime_contract_mismatch",
                f"--{name.replace('_', '-')} must be exactly {expected}",
            )
    if not args.require_cgroup_contract or not args.expected_systemd_unit:
        raise ToolchainError(
            "resource_contract_mismatch",
            "formal B1 requires --require-cgroup-contract and --expected-systemd-unit",
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
    python_record = _file_record(Path(sys.executable), root)
    if python_record["sha256"] != EXPECTED_PYTHON_SHA256:
        raise ToolchainError("tool_identity_drift", "Python SHA-256 drifted")
    return {
        "python": {"file": python_record},
        "roundingsat": {"file": roundingsat_record, "repository": repository},
        "veripb": {"file": veripb_record, "expected_version": EXPECTED_VERIPB_VERSION},
    }


def _preflight(args: argparse.Namespace) -> dict[str, Any]:
    root = args.project_root.resolve(strict=True)
    if root != PROJECT_ROOT.resolve(strict=True):
        raise ToolchainError("project_root_mismatch", "--project-root must identify this repository")
    current_head = str(_git_command(root, "rev-parse", "HEAD"))
    if current_head != EXPECTED_PROJECT_HEAD:
        raise ToolchainError(
            "repository_identity_drift",
            f"formal B1 requires HEAD {EXPECTED_PROJECT_HEAD}",
        )
    _validate_exact_runtime_contract(args)
    if not args.output_dir.is_absolute() or any(part in {".", ".."} for part in args.output_dir.parts):
        raise ToolchainError(
            "output_path_invalid",
            "--output-dir must be an absolute canonical direct-child path",
        )
    artifact_root = _canonical_existing_directory(ARTIFACT_ROOT, "formal artifact root")
    output_dir = args.output_dir.absolute()
    if output_dir.parent != artifact_root or FORMAL_OUTPUT_RE.fullmatch(output_dir.name) is None:
        raise ToolchainError(
            "output_path_invalid",
            f"--output-dir must be a formal-a001 direct child of {artifact_root}",
        )
    if output_dir.exists() or output_dir.is_symlink():
        raise ToolchainError("output_exists", "formal output directory must be fresh")
    a004_authority = _a004_authority_replay(root)

    raw_paths = {
        "opb": args.opb,
        "meta": args.meta,
        "var_map": args.var_map,
        "estimate": args.estimate,
        "translation_gate": args.translation_gate,
        "build_record": args.build_record,
        "build_manifest": args.build_manifest,
        "roundingsat": args.roundingsat,
        "roundingsat_repo": args.roundingsat_repo,
        "veripb": args.veripb,
    }
    try:
        paths = {name: value.resolve(strict=True) for name, value in raw_paths.items()}
    except OSError as exc:
        raise ToolchainError("missing_input", f"cannot resolve formal input: {exc}") from exc
    for name in (
        "opb",
        "meta",
        "var_map",
        "estimate",
        "translation_gate",
        "build_record",
        "build_manifest",
    ):
        if not paths[name].is_file():
            raise ToolchainError("missing_input", f"{name} is not a regular file")
    if not paths["roundingsat_repo"].is_dir():
        raise ToolchainError("tool_identity_drift", "RoundingSat repository is not a directory")

    build_authority = _validate_build_authority(paths, root)
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
    expected_upstream = a004_authority["encoder_binding"]
    if (
        meta.get("upstream_authority") != expected_upstream
        or estimate.get("upstream_authority") != expected_upstream
        or gate.get("upstream_authority") != expected_upstream
    ):
        raise ToolchainError(
            "a004_authority_failure",
            "encoder, estimate, and gate do not bind the replayed a004 authority",
        )

    encoder_path = Path(__file__).with_name(ENCODER_NAME)
    gate_source_path = Path(__file__).with_name(GATE_NAME)
    runner_path = Path(__file__)
    encoder_source = _validate_file_record(meta.get("harness_source"), encoder_path, root, "metadata.harness_source")
    if estimate.get("harness_source") != encoder_source or gate.get("encoder_source") != encoder_source:
        raise ToolchainError("provenance_mismatch", "encoder source provenance does not close")
    gate_source = _validate_file_record(gate.get("gate_source"), gate_source_path, root, "gate.gate_source")
    runner_source = _file_record(runner_path, root)
    inputs = _validate_record_map(meta.get("inputs"), INPUT_PATHS, EXPECTED_INPUT_SHA256, root, "metadata.inputs")
    if estimate.get("inputs") != inputs:
        raise ToolchainError("provenance_mismatch", "estimate and metadata strict bundles differ")
    if gate.get("strict_inputs") != inputs:
        raise ToolchainError("provenance_mismatch", "gate strict bundle does not close")

    meta_git = _validate_git_snapshot(meta.get("git_snapshot"), "metadata.git_snapshot")
    estimate_git = _validate_git_snapshot(estimate.get("git_snapshot"), "estimate.git_snapshot")
    gate_git = _validate_git_snapshot(gate.get("git_snapshot"), "gate.git_snapshot")
    if any(snapshot["head"] != EXPECTED_PROJECT_HEAD for snapshot in (meta_git, estimate_git, gate_git)):
        raise ToolchainError(
            "repository_identity_drift",
            "encoder or gate Git snapshot is not bound to the fixed HEAD",
        )
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
    var_map_record = _validate_file_record(outputs["var_map"], paths["var_map"], root, "metadata.outputs.var_map")
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
            "build_record": _file_record(paths["build_record"], root),
            "build_manifest": _file_record(paths["build_manifest"], root),
        },
        "strict_inputs": inputs,
        "a004_authority": a004_authority,
        "build_authority": build_authority,
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
        "build_record": output_dir / "build_authority.record.json",
        "build_manifest": output_dir / "build_authority.SHA256SUMS",
        "reservation": output_dir / "formal_attempt.reservation.json",
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
        "receipt": output_dir / "authority_receipt.json",
    }


def _snapshot_inputs(context: Mapping[str, Any], planned: Mapping[str, Path]) -> dict[str, Any]:
    source_names = {
        "opb": "opb",
        "meta": "meta",
        "var_map": "var_map",
        "estimate": "estimate",
        "translation_gate": "gate",
        "build_record": "build_record",
        "build_manifest": "build_manifest",
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
    return (
        stdout
        == [
            f"Running VeriPB version {EXPECTED_VERIPB_VERSION}",
            f"veripb {EXPECTED_VERIPB_VERSION}",
        ]
        and not stderr
    )


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
    excluded = {
        manifest_path.name,
        "toolchain_record.json",
        "authority_receipt.json",
    }
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
        type(name) is str and type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
        for name, digest in entries.items()
    ):
        return False
    allowed_downstream = {
        manifest_path.name,
        "toolchain_record.json",
        "authority_receipt.json",
    }
    current_names: list[str] = []
    for path in output_dir.iterdir():
        if path.name in allowed_downstream:
            if path.is_symlink() or not path.is_file():
                return False
            continue
        if path.is_symlink() or not path.is_file():
            return False
        current_names.append(path.name)
    current_names.sort()
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


def _receipt_file_record(
    value: Any,
    expected_path: Path,
    root: Path,
    field: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ToolchainError(
            "authority_receipt_failure",
            f"{field} must be a file identity",
        )
    current = _file_record(expected_path, root)
    if not _type_exact_equal(dict(value), current):
        raise ToolchainError(
            "authority_receipt_failure",
            f"{field} bytes drifted",
        )
    return current


def _closed_mapping(
    value: Any,
    expected_keys: set[str],
    field: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise ToolchainError(
            "authority_receipt_failure",
            f"{field} is not the closed expected object",
        )
    return value


def _is_utc_timestamp(value: Any) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def _closed_proc_cgroup(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ToolchainError(
            "authority_receipt_failure",
            f"{field} must be a process cgroup record",
        )
    keys = set(value)
    if keys == {"pid", "raw", "unified_path"}:
        if (
            type(value.get("pid")) is not int
            or value["pid"] <= 0
            or not isinstance(value.get("raw"), list)
            or not all(type(item) is str for item in value["raw"])
            or not isinstance(value.get("unified_path"), str)
            or not value["unified_path"].startswith("/")
        ):
            raise ToolchainError(
                "authority_receipt_failure",
                f"{field} has invalid process cgroup fields",
            )
    elif keys == {"pid", "error", "unified_path"}:
        if (
            type(value.get("pid")) is not int
            or value["pid"] <= 0
            or type(value.get("error")) is not str
            or value.get("unified_path") is not None
        ):
            raise ToolchainError(
                "authority_receipt_failure",
                f"{field} has invalid process cgroup failure fields",
            )
    else:
        raise ToolchainError(
            "authority_receipt_failure",
            f"{field} process cgroup key set drifted",
        )
    return value


def _closed_child_run(
    value: Any,
    *,
    field: str,
    stdout_path: Path,
    stderr_path: Path,
    root: Path,
) -> Mapping[str, Any]:
    child = _closed_mapping(
        value,
        {
            "argv",
            "started_at_utc",
            "started_wall_time_ns",
            "finished_at_utc",
            "finished_wall_time_ns",
            "exit_code",
            "timed_out",
            "termination_reason",
            "spawn_error",
            "elapsed_nanoseconds",
            "child_cgroup",
            "completion_cgroup_procs",
            "process_group_clean",
            "stdout",
            "stderr",
        },
        field,
    )
    exit_code = child.get("exit_code")
    termination_reason = child.get("termination_reason")
    spawn_error = child.get("spawn_error")
    child_cgroup = child.get("child_cgroup")
    if (
        not isinstance(child.get("argv"), list)
        or not all(type(item) is str for item in child["argv"])
        or not _is_utc_timestamp(child.get("started_at_utc"))
        or not _is_utc_timestamp(child.get("finished_at_utc"))
        or type(child.get("started_wall_time_ns")) is not int
        or type(child.get("finished_wall_time_ns")) is not int
        or child["finished_wall_time_ns"] < child["started_wall_time_ns"]
        or (exit_code is not None and type(exit_code) is not int)
        or type(child.get("timed_out")) is not bool
        or child["timed_out"] is not (termination_reason == "wall_timeout")
        or (termination_reason is not None and type(termination_reason) is not str)
        or (spawn_error is not None and type(spawn_error) is not str)
        or type(child.get("elapsed_nanoseconds")) is not int
        or child["elapsed_nanoseconds"] < 0
        or not isinstance(child.get("completion_cgroup_procs"), list)
        or not all(type(item) is str and item.isdigit() for item in child["completion_cgroup_procs"])
        or type(child.get("process_group_clean")) is not bool
        or not _type_exact_equal(
            child.get("stdout"),
            _file_record(stdout_path, root),
        )
        or not _type_exact_equal(
            child.get("stderr"),
            _file_record(stderr_path, root),
        )
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            f"{field} child execution semantics drifted",
        )
    if child_cgroup is not None:
        _closed_proc_cgroup(child_cgroup, f"{field}.child_cgroup")
    if spawn_error is None and child_cgroup is None:
        raise ToolchainError(
            "authority_receipt_failure",
            f"{field} omits the spawned child cgroup",
        )
    if spawn_error is not None and exit_code is not None:
        raise ToolchainError(
            "authority_receipt_failure",
            f"{field} reports both a spawn failure and an exit code",
        )
    return child


def _closed_integer_map(value: Any, field: str) -> Mapping[str, int]:
    if (
        not isinstance(value, Mapping)
        or not value
        or not all(type(key) is str and key and type(item) is int and item >= 0 for key, item in value.items())
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            f"{field} is not a non-empty non-negative integer map",
        )
    return value


def _closed_cgroup_state(
    value: Any,
    *,
    field: str,
    expected_unit: str,
    required: bool,
) -> Mapping[str, Any]:
    cgroup = _closed_mapping(
        value,
        {
            "required",
            "expected_systemd_unit",
            "self",
            "cgroup_path",
            "cgroup_directory",
            "leaf_values",
            "memory_events",
            "cgroup_procs",
            "ancestor_limits",
            "systemd_properties",
            "checks",
            "contract_pass",
        },
        field,
    )
    self_record = _closed_proc_cgroup(cgroup.get("self"), f"{field}.self")
    relative = cgroup.get("cgroup_path")
    leaf = _closed_mapping(
        cgroup.get("leaf_values"),
        {
            "memory.high",
            "memory.max",
            "memory.swap.max",
            "memory.current",
            "memory.peak",
        },
        f"{field}.leaf_values",
    )
    for name, item in leaf.items():
        if item is not None and type(item) is not str:
            raise ToolchainError(
                "authority_receipt_failure",
                f"{field}.leaf_values.{name} is not textual",
            )
    events = _closed_integer_map(cgroup.get("memory_events"), f"{field}.memory_events")
    procs = cgroup.get("cgroup_procs")
    ancestors = cgroup.get("ancestor_limits")
    properties = _closed_mapping(
        cgroup.get("systemd_properties"),
        {
            "MemoryHigh",
            "MemoryMax",
            "MemorySwapMax",
            "OOMPolicy",
            "KillMode",
            "SendSIGKILL",
        },
        f"{field}.systemd_properties",
    )
    expected_property_values = {
        "MemoryHigh": str(EXPECTED_MEMORY_HIGH),
        "MemoryMax": str(EXPECTED_MEMORY_MAX),
        "MemorySwapMax": str(EXPECTED_SWAP_MAX),
        "OOMPolicy": EXPECTED_OOM_POLICY,
        "KillMode": EXPECTED_KILL_MODE,
        "SendSIGKILL": EXPECTED_SEND_SIGKILL,
    }
    for name, expected in expected_property_values.items():
        item = _closed_mapping(
            properties.get(name),
            {"argv", "exit_code", "stdout", "stderr", "value"},
            f"{field}.systemd_properties.{name}",
        )
        if (
            not _type_exact_equal(
                item.get("argv"),
                [
                    "systemctl",
                    "--user",
                    "show",
                    expected_unit,
                    f"--property={name}",
                    "--value",
                ],
            )
            or item.get("exit_code") != 0
            or type(item.get("stdout")) is not str
            or type(item.get("stderr")) is not str
            or item.get("value") != expected
        ):
            raise ToolchainError(
                "authority_receipt_failure",
                f"{field}.systemd_properties.{name} drifted",
            )
    expected_checks = {
        "unified_cgroup_found",
        "expected_unit_is_cgroup_leaf",
        "memory_high_exact",
        "memory_max_exact",
        "memory_swap_max_exact",
        "memory_events_readable",
        "systemd_memory_high_exact",
        "systemd_memory_max_exact",
        "systemd_memory_swap_max_exact",
        "oom_policy_exact",
        "kill_mode_exact",
        "send_sigkill_exact",
        "ancestor_limits_allow_contract",
    }
    checks = _closed_mapping(cgroup.get("checks"), expected_checks, f"{field}.checks")
    if (
        cgroup.get("required") is not required
        or cgroup.get("expected_systemd_unit") != expected_unit
        or type(relative) is not str
        or not relative.startswith("/")
        or Path(relative).name != expected_unit
        or cgroup.get("cgroup_directory") != str(Path("/sys/fs/cgroup") / relative.lstrip("/"))
        or self_record.get("unified_path") != relative
        or leaf.get("memory.high") != str(EXPECTED_MEMORY_HIGH)
        or leaf.get("memory.max") != str(EXPECTED_MEMORY_MAX)
        or leaf.get("memory.swap.max") != str(EXPECTED_SWAP_MAX)
        or not isinstance(procs, list)
        or not all(type(item) is str and item.isdigit() for item in procs)
        or not isinstance(ancestors, list)
        or not ancestors
        or not all(
            isinstance(item, Mapping)
            and set(item) == {"path", "memory_high", "memory_max", "memory_swap_max"}
            and type(item.get("path")) is str
            and all(
                item.get(name) is None or type(item.get(name)) is str
                for name in ("memory_high", "memory_max", "memory_swap_max")
            )
            for item in ancestors
        )
        or not _ancestor_limits_allow_contract(ancestors)
        or any(item is not True for item in checks.values())
        or cgroup.get("contract_pass") is not True
        or not events
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            f"{field} cgroup contract semantics drifted",
        )
    return cgroup


def _closed_telemetry_sample(
    value: Any,
    *,
    field: str,
    expected_cgroup_path: str,
) -> Mapping[str, Any]:
    sample = _closed_mapping(
        value,
        {
            "timestamp_utc",
            "monotonic_nanoseconds",
            "phase",
            "free_bytes",
            "proof_size_bytes",
            "active_child",
            "cgroup",
        },
        field,
    )
    proof_size = sample.get("proof_size_bytes")
    active = sample.get("active_child")
    cgroup = _closed_mapping(
        sample.get("cgroup"),
        {
            "memory_current",
            "memory_peak",
            "memory_swap_current",
            "memory_swap_peak",
            "memory_events",
            "cgroup_procs",
        },
        f"{field}.cgroup",
    )
    for name in (
        "memory_current",
        "memory_peak",
        "memory_swap_current",
        "memory_swap_peak",
    ):
        item = cgroup.get(name)
        if item is not None and (type(item) is not str or not item.isdigit()):
            raise ToolchainError(
                "authority_receipt_failure",
                f"{field}.cgroup.{name} is invalid",
            )
    _closed_integer_map(cgroup.get("memory_events"), f"{field}.cgroup.memory_events")
    cgroup_procs = cgroup.get("cgroup_procs")
    if (
        not _is_utc_timestamp(sample.get("timestamp_utc"))
        or type(sample.get("monotonic_nanoseconds")) is not int
        or sample["monotonic_nanoseconds"] < 0
        or type(sample.get("phase")) is not str
        or not sample["phase"]
        or type(sample.get("free_bytes")) is not int
        or sample["free_bytes"] < 0
        or (proof_size is not None and (type(proof_size) is not int or proof_size < 0))
        or not isinstance(cgroup_procs, list)
        or not all(type(item) is str and item.isdigit() for item in cgroup_procs)
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            f"{field} telemetry fields drifted",
        )
    if active is not None:
        active_record = _closed_proc_cgroup(active, f"{field}.active_child")
        if active_record.get("unified_path") != expected_cgroup_path:
            raise ToolchainError(
                "authority_receipt_failure",
                f"{field} active child escaped the formal cgroup",
            )
    return sample


def _single_argv_value(argv: Sequence[str], option: str) -> str:
    positions = [index for index, item in enumerate(argv) if item == option]
    if len(positions) != 1 or positions[0] + 1 >= len(argv):
        raise ToolchainError(
            "authority_receipt_failure",
            f"formal argv does not contain exactly one {option}",
        )
    value = argv[positions[0] + 1]
    if type(value) is not str or not value or value.startswith("--"):
        raise ToolchainError(
            "authority_receipt_failure",
            f"formal argv has an invalid value for {option}",
        )
    return value


def _replay_started_record(
    started: Any,
    *,
    record: Mapping[str, Any],
    inputs: Mapping[str, Any],
    input_copies: Mapping[str, Any],
    strict_inputs: Mapping[str, Any],
    a004_authority: Mapping[str, Any],
    build_authority: Mapping[str, Any],
    reservation_source: Mapping[str, Any],
    reservation_copy: Mapping[str, Any],
    sources: Mapping[str, Any],
    git_snapshots: Mapping[str, Any],
    tools: Mapping[str, Any],
    execution: Mapping[str, Any],
    cgroup: Mapping[str, Any],
) -> None:
    started = _closed_mapping(
        started,
        {
            "schema_version",
            "semantics",
            "formal_attempt",
            "started_at_utc",
            "argv",
            "inputs",
            "input_copies",
            "strict_inputs",
            "a004_authority",
            "build_authority",
            "reservation",
            "sources",
            "git_snapshots",
            "tools_before_execution",
            "limits",
            "cgroup",
            "claim_at_start",
        },
        "toolchain_started",
    )
    started_reservation = _closed_mapping(
        started.get("reservation"),
        {"source", "copy"},
        "toolchain_started.reservation",
    )
    if (
        started.get("schema_version") != SCHEMA_VERSION
        or started.get("semantics") != SEMANTICS
        or started.get("formal_attempt") != "a001"
        or started.get("started_at_utc") != record.get("started_at_utc")
        or not _is_utc_timestamp(started.get("started_at_utc"))
        or not _type_exact_equal(started.get("argv"), record.get("argv"))
        or not _type_exact_equal(started.get("inputs"), inputs)
        or not _type_exact_equal(started.get("input_copies"), input_copies)
        or not _type_exact_equal(started.get("strict_inputs"), strict_inputs)
        or not _type_exact_equal(started.get("a004_authority"), a004_authority)
        or not _type_exact_equal(started.get("build_authority"), build_authority)
        or not _type_exact_equal(
            started_reservation.get("source"),
            reservation_source,
        )
        or not _type_exact_equal(
            started_reservation.get("copy"),
            reservation_copy,
        )
        or not _type_exact_equal(started.get("sources"), sources)
        or not _type_exact_equal(started.get("git_snapshots"), git_snapshots)
        or not _type_exact_equal(started.get("tools_before_execution"), tools)
        or not _type_exact_equal(started.get("limits"), execution)
        or not _type_exact_equal(started.get("cgroup"), cgroup)
        or started.get("claim_at_start") != "none"
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "toolchain_started semantics do not close against the final record",
        )


def _replay_toolchain_record_semantics(
    record: Mapping[str, Any],
    output_dir: Path,
    reservation_marker: Path,
    build_record: Path,
    build_manifest: Path,
    root: Path,
) -> bool:
    """Replay the complete claim-bearing record without trusting its builder."""

    _closed_mapping(
        record,
        {
            "schema_version",
            "semantics",
            "formal_attempt",
            "started_at_utc",
            "finished_at_utc",
            "argv",
            "inputs",
            "input_copies",
            "inputs_after_execution",
            "inputs_stable",
            "strict_inputs",
            "build_authority",
            "reservation",
            "a004_authority",
            "sources",
            "git_snapshots",
            "tools",
            "execution",
            "solver",
            "proof",
            "verifier",
            "hash_stability",
            "translation_gate",
            "artifact_manifest",
            "resource_monitor",
            "failure_codes",
            "solver_declared_unsat",
            "proof_tail_complete",
            "veripb_verified",
            "claim",
            "verified_result_candidate",
            "upper_bound_update_authorized",
            "publication_status",
            "claim_boundary",
        },
        "toolchain_record",
    )
    if (
        record.get("schema_version") != SCHEMA_VERSION
        or record.get("semantics") != SEMANTICS
        or record.get("formal_attempt") != "a001"
        or not _is_utc_timestamp(record.get("started_at_utc"))
        or not _is_utc_timestamp(record.get("finished_at_utc"))
        or not isinstance(record.get("argv"), list)
        or not all(type(item) is str for item in record["argv"])
        or not isinstance(record.get("failure_codes"), list)
        or not all(type(item) is str and item for item in record["failure_codes"])
        or len(set(record["failure_codes"])) != len(record["failure_codes"])
        or type(record.get("inputs_stable")) is not bool
        or type(record.get("solver_declared_unsat")) is not bool
        or type(record.get("proof_tail_complete")) is not bool
        or type(record.get("veripb_verified")) is not bool
        or type(record.get("upper_bound_update_authorized")) is not bool
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "toolchain record top-level identity drifted",
        )
    success = record.get("verified_result_candidate") == (
        "machine_verified_complete_lex_better_band_unsat_given_a004_admitted_geometric_lemmas"
    )

    planned = _planned_paths(output_dir)
    expected_systemd_unit = _single_argv_value(
        record["argv"],
        "--expected-systemd-unit",
    )
    source_build_dir = build_record.resolve(strict=True).parent
    source_paths = {
        "estimate": source_build_dir / "estimate.json",
        "opb": source_build_dir / "formula.opb",
        "meta": source_build_dir / "encoder.meta.json",
        "var_map": source_build_dir / "variable_map.json",
        "translation_gate": source_build_dir / "translation_gate.json",
        "build_record": build_record,
        "build_manifest": build_manifest,
    }
    expected_argv = [
        str(Path(__file__).resolve(strict=True)),
        "--project-root",
        str(root),
        "--opb",
        str(source_paths["opb"]),
        "--meta",
        str(source_paths["meta"]),
        "--var-map",
        str(source_paths["var_map"]),
        "--estimate",
        str(source_paths["estimate"]),
        "--translation-gate",
        str(source_paths["translation_gate"]),
        "--build-record",
        str(source_paths["build_record"]),
        "--build-manifest",
        str(source_paths["build_manifest"]),
        "--roundingsat",
        str(EXPECTED_ROUNDINGSAT_PATH.resolve(strict=True)),
        "--roundingsat-repo",
        str(EXPECTED_ROUNDINGSAT_REPO.resolve(strict=True)),
        "--veripb",
        str(EXPECTED_VERIPB_PATH.resolve(strict=True)),
        "--output-dir",
        str(output_dir),
        "--solver-time-limit",
        str(FORMAL_SOLVER_TIME_LIMIT_SECONDS),
        "--solver-wall-timeout",
        str(FORMAL_SOLVER_WALL_TIMEOUT_SECONDS),
        "--verifier-wall-timeout",
        str(FORMAL_VERIFIER_WALL_TIMEOUT_SECONDS),
        "--proof-limit-bytes",
        str(FORMAL_PROOF_LIMIT_BYTES),
        "--min-free-bytes",
        str(FORMAL_MIN_FREE_BYTES),
        "--monitor-interval",
        str(FORMAL_MONITOR_INTERVAL_SECONDS),
        "--expected-systemd-unit",
        expected_systemd_unit,
        "--require-cgroup-contract",
    ]
    if re.fullmatch(
        r"b1-r4-1188-22-formal-a001-[0-9]{8}T[0-9]{6}Z[.]service",
        expected_systemd_unit,
    ) is None or not _type_exact_equal(record.get("argv"), expected_argv):
        raise ToolchainError(
            "authority_receipt_failure",
            "formal top-level argv is not the canonical fixed invocation",
        )
    formal_copy_paths = {
        "estimate": planned["estimate"],
        "opb": planned["opb"],
        "meta": planned["meta"],
        "var_map": planned["var_map"],
        "translation_gate": planned["gate"],
        "build_record": planned["build_record"],
        "build_manifest": planned["build_manifest"],
    }
    expected_inputs = {name: _file_record(path, root) for name, path in source_paths.items()}
    expected_copies = {name: _file_record(path, root) for name, path in formal_copy_paths.items()}
    gate_payload = _strict_json(planned["gate"], "formal translation gate")
    if (
        not _type_exact_equal(record.get("inputs"), expected_inputs)
        or not _type_exact_equal(record.get("inputs_after_execution"), expected_inputs)
        or record.get("inputs_stable") is not True
        or not _type_exact_equal(record.get("input_copies"), expected_copies)
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "toolchain input/copy provenance drifted",
        )

    strict_inputs = _validate_record_map(
        record.get("strict_inputs"),
        INPUT_PATHS,
        EXPECTED_INPUT_SHA256,
        root,
        "toolchain_record.strict_inputs",
    )
    build_paths = {
        **source_paths,
        "translation_gate": source_paths["translation_gate"],
    }
    current_build = _validate_build_authority(build_paths, root)
    build_section = _closed_mapping(
        record.get("build_authority"),
        {"preflight", "after_execution", "stable"},
        "toolchain_record.build_authority",
    )
    if (
        build_section.get("stable") is not True
        or not _type_exact_equal(build_section.get("preflight"), current_build)
        or not _type_exact_equal(build_section.get("after_execution"), current_build)
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "build authority semantics drifted",
        )

    current_a004 = _a004_authority_replay(root)
    a004_section = _closed_mapping(
        record.get("a004_authority"),
        {
            "preflight",
            "after_translation_gate",
            "before_roundingsat",
            "after_roundingsat",
            "after_veripb",
            "before_final_claim",
            "stable",
        },
        "toolchain_record.a004_authority",
    )
    if a004_section.get("stable") is not True or any(
        not _type_exact_equal(a004_section.get(name), current_a004)
        for name in (
            "preflight",
            "after_translation_gate",
            "before_roundingsat",
            "after_roundingsat",
            "after_veripb",
            "before_final_claim",
        )
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "a004 authority semantics drifted",
        )

    current_reservation = _file_record(reservation_marker, root)
    current_reservation_copy = _file_record(planned["reservation"], root)
    reservation = _closed_mapping(
        record.get("reservation"),
        {
            "source_at_reservation",
            "copy",
            "after_translation_gate",
            "before_roundingsat",
            "after_veripb",
            "before_final_claim",
            "stable",
        },
        "toolchain_record.reservation",
    )
    if (
        reservation.get("stable") is not True
        or not _type_exact_equal(reservation.get("copy"), current_reservation_copy)
        or any(
            not _type_exact_equal(reservation.get(name), current_reservation)
            for name in (
                "source_at_reservation",
                "after_translation_gate",
                "before_roundingsat",
                "after_veripb",
                "before_final_claim",
            )
        )
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "formal reservation semantics drifted",
        )
    reservation_payload = _strict_json(reservation_marker, "formal reservation")
    _closed_mapping(
        reservation_payload,
        {
            "schema_version",
            "attempt",
            "reserved_at_utc",
            "output_dir",
            "argv",
            "git_head",
        },
        "formal_reservation",
    )
    if (
        reservation_payload.get("schema_version") != "b1_r4_1188_22_pb_formal_attempt_reservation_v1"
        or reservation_payload.get("attempt") != "a001"
        or not _is_utc_timestamp(reservation_payload.get("reserved_at_utc"))
        or reservation_payload.get("output_dir") != str(output_dir)
        or reservation_payload.get("git_head") != EXPECTED_PROJECT_HEAD
        or not _type_exact_equal(reservation_payload.get("argv"), record.get("argv"))
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "formal reservation payload drifted",
        )

    current_sources = {
        "encoder": _file_record(Path(__file__).with_name(ENCODER_NAME), root),
        "gate": _file_record(Path(__file__).with_name(GATE_NAME), root),
        "runner": _file_record(Path(__file__), root),
    }
    sources = _closed_mapping(
        record.get("sources"),
        {"before", "after", "stable"},
        "toolchain_record.sources",
    )
    if (
        sources.get("stable") is not True
        or not _type_exact_equal(sources.get("before"), current_sources)
        or not _type_exact_equal(sources.get("after"), current_sources)
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "source byte identities drifted",
        )

    git = record.get("git_snapshots")
    if not isinstance(git, Mapping) or set(git) != {
        "encoder",
        "gate",
        "runner",
        "source_surface_start",
        "source_surface_end",
        "source_surface_stable",
    }:
        raise ToolchainError(
            "authority_receipt_failure",
            "Git snapshot closure drifted",
        )
    encoder_git = _validate_git_snapshot(git.get("encoder"), "receipt.encoder_git")
    gate_git = _validate_git_snapshot(git.get("gate"), "receipt.gate_git")
    runner_git = _validate_git_snapshot(git.get("runner"), "receipt.runner_git")
    current_git = _git_snapshot(root)
    current_source_surface = _source_snapshot(root)
    if (
        git.get("source_surface_stable") is not True
        or not _type_exact_equal(gate_git, current_git)
        or not _type_exact_equal(runner_git, current_git)
        or not _type_exact_equal(git.get("source_surface_start"), current_source_surface)
        or not _type_exact_equal(git.get("source_surface_end"), current_source_surface)
        or encoder_git["head"] != EXPECTED_PROJECT_HEAD
        or not _type_exact_equal(
            encoder_git,
            gate_payload.get("encoder_git_snapshot"),
        )
        or not _type_exact_equal(gate_git, gate_payload.get("git_snapshot"))
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "Git state no longer matches the formal run",
        )

    tools = _closed_mapping(
        record.get("tools"),
        {
            "before",
            "after",
            "stable",
            "veripb_version_exact",
            "veripb_version_probe",
        },
        "toolchain_record.tools",
    )
    current_tools = _validate_tool_paths(
        {
            "roundingsat": EXPECTED_ROUNDINGSAT_PATH.resolve(strict=True),
            "roundingsat_repo": EXPECTED_ROUNDINGSAT_REPO.resolve(strict=True),
            "veripb": EXPECTED_VERIPB_PATH.resolve(strict=True),
        },
        root,
    )
    version_probe = tools.get("veripb_version_probe")
    if version_probe is not None:
        version_probe = _closed_child_run(
            version_probe,
            field="toolchain_record.tools.veripb_version_probe",
            stdout_path=planned["version_stdout"],
            stderr_path=planned["version_stderr"],
            root=root,
        )
    if (
        type(tools.get("veripb_version_exact")) is not bool
        or tools.get("stable") is not True
        or not _type_exact_equal(tools.get("before"), current_tools)
        or not _type_exact_equal(tools.get("after"), current_tools)
        or (
            success
            and (
                tools.get("veripb_version_exact") is not True
                or version_probe is None
                or not _type_exact_equal(
                    version_probe.get("argv"),
                    [
                        str(EXPECTED_VERIPB_PATH.resolve(strict=True)),
                        "--version",
                    ],
                )
                or not _veripb_version_ok(
                    planned["version_stdout"],
                    planned["version_stderr"],
                    version_probe,
                )
                or version_probe.get("process_group_clean") is not True
                or _error_markers(
                    planned["version_stdout"],
                    planned["version_stderr"],
                )
            )
        )
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "formal tool identities drifted",
        )

    execution = _closed_mapping(
        record.get("execution"),
        {
            "proof_limit_bytes",
            "min_free_bytes",
            "proof_planning_bound_bytes",
            "preflight_reserved_proof_bytes",
            "preflight_free_bytes",
            "solver_time_limit_seconds",
            "solver_wall_timeout_seconds",
            "verifier_wall_timeout_seconds",
            "translation_gate_wall_timeout_seconds",
            "monitor_interval_seconds",
        },
        "toolchain_record.execution",
    )
    if (
        any(type(value) is not int for value in execution.values())
        or execution.get("proof_limit_bytes") != FORMAL_PROOF_LIMIT_BYTES
        or execution.get("min_free_bytes") != FORMAL_MIN_FREE_BYTES
        or execution.get("preflight_reserved_proof_bytes") != FORMAL_PROOF_LIMIT_BYTES
        or execution.get("proof_planning_bound_bytes")
        != _strict_json(
            planned["estimate"],
            "formal estimate copy",
        )
        .get("proof_size_planning", {})
        .get("bound_bytes")
        or execution["preflight_free_bytes"] < FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES
        or execution.get("solver_time_limit_seconds") != FORMAL_SOLVER_TIME_LIMIT_SECONDS
        or execution.get("solver_wall_timeout_seconds") != FORMAL_SOLVER_WALL_TIMEOUT_SECONDS
        or execution.get("verifier_wall_timeout_seconds") != FORMAL_VERIFIER_WALL_TIMEOUT_SECONDS
        or execution.get("translation_gate_wall_timeout_seconds") != FORMAL_GATE_WALL_TIMEOUT_SECONDS
        or execution.get("monitor_interval_seconds") != FORMAL_MONITOR_INTERVAL_SECONDS
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "execution resource contract drifted",
        )

    solver = _closed_mapping(
        record.get("solver"),
        {
            "run",
            "status_lines",
            "stdout_status_lines",
            "stderr_status_lines",
            "error_markers",
            "declared_unsat",
        },
        "toolchain_record.solver",
    )
    verifier = _closed_mapping(
        record.get("verifier"),
        {
            "run",
            "status_lines",
            "stdout_status_lines",
            "stderr_status_lines",
            "error_markers",
            "verified_unsat",
        },
        "toolchain_record.verifier",
    )
    proof = _closed_mapping(
        record.get("proof"),
        {
            "file",
            "tail",
            "fresh_for_solver",
            "sha256_before_verifier",
            "sha256_after_verifier",
        },
        "toolchain_record.proof",
    )
    hash_stability = _closed_mapping(
        record.get("hash_stability"),
        {
            "formula_before_solver",
            "formula_after_solver",
            "formula_before_verifier",
            "formula_after_verifier",
            "proof_before_verifier",
            "proof_after_verifier",
            "stable",
        },
        "toolchain_record.hash_stability",
    )
    proof_tail = _closed_mapping(
        proof.get("tail"),
        {"nonempty", "conclusion_line", "end_line", "complete"},
        "toolchain_record.proof.tail",
    )
    solver_run = solver.get("run")
    if solver_run is not None:
        solver_run = _closed_child_run(
            solver_run,
            field="toolchain_record.solver.run",
            stdout_path=planned["solver_stdout"],
            stderr_path=planned["solver_stderr"],
            root=root,
        )
    verifier_run = verifier.get("run")
    if verifier_run is not None:
        verifier_run = _closed_child_run(
            verifier_run,
            field="toolchain_record.verifier.run",
            stdout_path=planned["verifier_stdout"],
            stderr_path=planned["verifier_stderr"],
            root=root,
        )
    current_solver_stdout_status = _status_lines(planned["solver_stdout"])
    current_solver_stderr_status = _status_lines(planned["solver_stderr"])
    current_solver_status = current_solver_stdout_status + current_solver_stderr_status
    current_solver_errors = _error_markers(
        planned["solver_stdout"],
        planned["solver_stderr"],
    )
    current_verifier_stdout_status = _status_lines(planned["verifier_stdout"])
    current_verifier_stderr_status = _status_lines(planned["verifier_stderr"])
    current_verifier_status = current_verifier_stdout_status + current_verifier_stderr_status
    current_verifier_errors = _error_markers(
        planned["verifier_stdout"],
        planned["verifier_stderr"],
    )
    if (
        record.get("claim") != "none"
        or record.get("upper_bound_update_authorized") is not False
        or record.get("publication_status") != "requires_successful_detached_authority_receipt_replay"
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "raw toolchain record improperly publishes a claim",
        )
    formula_digest = _sha256(planned["opb"])
    proof_digest = _sha256(planned["proof"]) if planned["proof"].is_file() else None
    if (
        not _type_exact_equal(solver.get("status_lines"), current_solver_status)
        or not _type_exact_equal(
            solver.get("stdout_status_lines"),
            current_solver_stdout_status,
        )
        or not _type_exact_equal(
            solver.get("stderr_status_lines"),
            current_solver_stderr_status,
        )
        or not _type_exact_equal(solver.get("error_markers"), current_solver_errors)
        or type(solver.get("declared_unsat")) is not bool
        or solver.get("declared_unsat")
        is not _stdout_status_exact(
            planned["solver_stdout"],
            planned["solver_stderr"],
            "s UNSATISFIABLE",
        )
        or not _type_exact_equal(verifier.get("status_lines"), current_verifier_status)
        or not _type_exact_equal(
            verifier.get("stdout_status_lines"),
            current_verifier_stdout_status,
        )
        or not _type_exact_equal(
            verifier.get("stderr_status_lines"),
            current_verifier_stderr_status,
        )
        or not _type_exact_equal(
            verifier.get("error_markers"),
            current_verifier_errors,
        )
        or type(verifier.get("verified_unsat")) is not bool
        or verifier.get("verified_unsat")
        is not _stdout_status_exact(
            planned["verifier_stdout"],
            planned["verifier_stderr"],
            "s VERIFIED UNSATISFIABLE",
        )
        or type(proof.get("fresh_for_solver")) is not bool
        or not _type_exact_equal(proof_tail, _proof_tail(planned["proof"]))
        or proof.get("sha256_before_verifier") != proof_digest
        or proof.get("sha256_after_verifier") != proof_digest
        or type(hash_stability.get("stable")) is not bool
        or record.get("solver_declared_unsat") is not solver.get("declared_unsat")
        or record.get("proof_tail_complete") is not proof_tail.get("complete")
        or record.get("veripb_verified") is not verifier.get("verified_unsat")
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "raw solver/verifier/proof records do not replay from their bytes",
        )
    if success and (
        record.get("failure_codes") != []
        or record.get("solver_declared_unsat") is not True
        or record.get("proof_tail_complete") is not True
        or record.get("veripb_verified") is not True
        or solver.get("declared_unsat") is not True
        or solver.get("status_lines") != ["s UNSATISFIABLE"]
        or solver.get("stdout_status_lines") != ["s UNSATISFIABLE"]
        or solver.get("stderr_status_lines") != []
        or solver.get("error_markers") != []
        or verifier.get("verified_unsat") is not True
        or verifier.get("status_lines") != ["s VERIFIED UNSATISFIABLE"]
        or verifier.get("stdout_status_lines") != ["s VERIFIED UNSATISFIABLE"]
        or verifier.get("stderr_status_lines") != []
        or verifier.get("error_markers") != []
        or solver_run is None
        or solver_run.get("exit_code") not in (0, 1)
        or solver_run.get("termination_reason") is not None
        or solver_run.get("process_group_clean") is not True
        or not _type_exact_equal(
            solver_run.get("argv"),
            [
                str(EXPECTED_ROUNDINGSAT_PATH.resolve(strict=True)),
                f"--proof-log={planned['proof']}",
                f"--time-limit={FORMAL_SOLVER_TIME_LIMIT_SECONDS:g}",
                str(planned["opb"]),
            ],
        )
        or not _type_exact_equal(
            solver_run.get("stdout"),
            _file_record(planned["solver_stdout"], root),
        )
        or not _type_exact_equal(
            solver_run.get("stderr"),
            _file_record(planned["solver_stderr"], root),
        )
        or verifier_run is None
        or verifier_run.get("exit_code") != 0
        or verifier_run.get("termination_reason") is not None
        or verifier_run.get("process_group_clean") is not True
        or not _type_exact_equal(
            verifier_run.get("argv"),
            [
                str(EXPECTED_VERIPB_PATH.resolve(strict=True)),
                "--opb",
                "--stats",
                str(planned["opb"]),
                str(planned["proof"]),
            ],
        )
        or not _type_exact_equal(
            verifier_run.get("stdout"),
            _file_record(planned["verifier_stdout"], root),
        )
        or not _type_exact_equal(
            verifier_run.get("stderr"),
            _file_record(planned["verifier_stderr"], root),
        )
        or proof.get("fresh_for_solver") is not True
        or not _type_exact_equal(
            proof.get("file"),
            _file_record(planned["proof"], root),
        )
        or _proof_tail(planned["proof"]).get("complete") is not True
        or not _type_exact_equal(
            proof_tail,
            _proof_tail(planned["proof"]),
        )
        or hash_stability.get("stable") is not True
        or any(
            hash_stability.get(name) != formula_digest
            for name in (
                "formula_before_solver",
                "formula_after_solver",
                "formula_before_verifier",
                "formula_after_verifier",
            )
        )
        or any(
            hash_stability.get(name) != proof_digest
            for name in (
                "proof_before_verifier",
                "proof_after_verifier",
            )
        )
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "solver/proof/verifier success semantics drifted",
        )
    if not success and (
        record.get("verified_result_candidate") != "none"
        or not isinstance(record.get("failure_codes"), list)
        or not record.get("failure_codes")
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "failed record is not an explicit fail-closed result",
        )

    translation = _closed_mapping(
        record.get("translation_gate"),
        {
            "file",
            "status",
            "corpus_errors",
            "checks",
            "recheck_run",
            "recheck_file",
            "recheck_byte_exact",
        },
        "toolchain_record.translation_gate",
    )
    gate_recheck_run = translation.get("recheck_run")
    if gate_recheck_run is not None:
        gate_recheck_run = _closed_child_run(
            gate_recheck_run,
            field="toolchain_record.translation_gate.recheck_run",
            stdout_path=planned["gate_recheck_stdout"],
            stderr_path=planned["gate_recheck_stderr"],
            root=root,
        )
    current_gate_recheck_file = _optional_file_record(
        planned["gate_recheck"],
        root,
    )
    if (
        not _type_exact_equal(
            translation.get("file"),
            expected_inputs["translation_gate"],
        )
        or translation.get("status") != gate_payload.get("status")
        or not _type_exact_equal(
            translation.get("corpus_errors"),
            gate_payload.get("corpus_errors"),
        )
        or not isinstance(translation.get("checks"), Mapping)
        or set(translation["checks"]) != REQUIRED_GATE_CHECKS
        or not _type_exact_equal(
            translation.get("recheck_file"),
            current_gate_recheck_file,
        )
        or not _type_exact_equal(gate_payload.get("checks"), translation["checks"])
        or type(translation.get("recheck_byte_exact")) is not bool
        or gate_recheck_run is None
        or not _type_exact_equal(
            gate_recheck_run.get("argv"),
            [
                str(EXPECTED_PYTHON_PATH.resolve(strict=True)),
                str(Path(__file__).with_name(GATE_NAME).resolve(strict=True)),
                "--project-root",
                str(root),
                "--opb",
                str(source_paths["opb"]),
                "--meta",
                str(source_paths["meta"]),
                "--var-map",
                str(source_paths["var_map"]),
                "--estimate",
                str(source_paths["estimate"]),
                "--output",
                str(planned["gate_recheck"]),
            ],
        )
        or (
            success
            and (
                translation.get("status") != "PASS"
                or translation.get("corpus_errors") != []
                or any(value is not True for value in translation["checks"].values())
                or translation.get("recheck_byte_exact") is not True
                or planned["gate_recheck"].read_bytes() != planned["gate"].read_bytes()
                or gate_recheck_run.get("exit_code") != 0
                or gate_recheck_run.get("termination_reason") is not None
                or gate_recheck_run.get("process_group_clean") is not True
                or _error_markers(
                    planned["gate_recheck_stdout"],
                    planned["gate_recheck_stderr"],
                )
            )
        )
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "translation-gate success semantics drifted",
        )

    manifest_report = _closed_mapping(
        record.get("artifact_manifest"),
        {
            "file",
            "entries",
            "covered_files",
            "excluded_to_avoid_hash_cycle",
            "stable_recheck",
            "critical_hashes_match",
        },
        "toolchain_record.artifact_manifest",
    )
    manifest_entries = manifest_report.get("entries")
    expected_success_manifest_names = {
        path.name for name, path in planned.items() if name not in {"record", "checksums", "receipt"}
    }
    if (
        not isinstance(manifest_entries, Mapping)
        or not all(
            type(name) is str
            and re.fullmatch(r"[A-Za-z0-9_.-]+", name) is not None
            and type(digest) is str
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
            for name, digest in manifest_entries.items()
        )
        or not _type_exact_equal(
            manifest_report.get("file"),
            _file_record(planned["checksums"], root),
        )
        or not _type_exact_equal(
            manifest_report.get("covered_files"),
            sorted(manifest_entries),
        )
        or not _type_exact_equal(
            manifest_report.get("excluded_to_avoid_hash_cycle"),
            [
                "SHA256SUMS",
                "authority_receipt.json",
                "toolchain_record.json",
            ],
        )
        or type(manifest_report.get("stable_recheck")) is not bool
        or type(manifest_report.get("critical_hashes_match")) is not bool
        or (success and set(manifest_entries) != expected_success_manifest_names)
        or manifest_report.get("stable_recheck") is not True
        or (success and manifest_report.get("critical_hashes_match") is not True)
        or not _checksum_manifest_stable(
            output_dir,
            planned["checksums"],
            manifest_report,
        )
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "formal artifact manifest semantics drifted",
        )

    resource = _closed_mapping(
        record.get("resource_monitor"),
        {
            "schema_version",
            "file",
            "sample_count",
            "minimum_free_bytes_observed",
            "maximum_proof_bytes_observed",
            "cgroup_start",
            "cgroup_end",
            "cgroup_stable",
            "memory_event_deltas",
            "oom_clean",
        },
        "toolchain_record.resource_monitor",
    )
    cgroup_start = _closed_cgroup_state(
        resource.get("cgroup_start"),
        field="toolchain_record.resource_monitor.cgroup_start",
        expected_unit=expected_systemd_unit,
        required=True,
    )
    cgroup_end = _closed_cgroup_state(
        resource.get("cgroup_end"),
        field="toolchain_record.resource_monitor.cgroup_end",
        expected_unit=expected_systemd_unit,
        required=False,
    )
    derived_cgroup_stable = bool(
        cgroup_end["contract_pass"]
        and cgroup_end["cgroup_path"] == cgroup_start["cgroup_path"]
        and _type_exact_equal(
            cgroup_end["systemd_properties"],
            cgroup_start["systemd_properties"],
        )
    )
    derived_event_deltas = _event_deltas(
        cgroup_start["memory_events"],
        cgroup_end["memory_events"],
    )
    derived_oom_clean = bool(
        derived_event_deltas is not None and all(derived_event_deltas.get(key, 0) == 0 for key in OOM_EVENT_KEYS)
    )
    main_pid = str(cgroup_start["self"]["pid"])
    for field, child in (
        ("translation_gate.recheck_run", gate_recheck_run),
        ("tools.veripb_version_probe", version_probe),
        ("solver.run", solver_run),
        ("verifier.run", verifier_run),
    ):
        if child is None:
            continue
        child_cgroup = child.get("child_cgroup")
        if (
            not isinstance(child_cgroup, Mapping)
            or child_cgroup.get("unified_path") != cgroup_start["cgroup_path"]
            or child["completion_cgroup_procs"] != [main_pid]
        ):
            raise ToolchainError(
                "authority_receipt_failure",
                f"{field} cgroup provenance drifted",
            )
    if (
        resource.get("schema_version") != RESOURCE_SCHEMA
        or not _type_exact_equal(
            resource.get("file"),
            _file_record(planned["telemetry"], root),
        )
        or type(resource.get("sample_count")) is not int
        or resource["sample_count"] <= 0
        or type(resource.get("minimum_free_bytes_observed")) is not int
        or resource["minimum_free_bytes_observed"] < FORMAL_MIN_FREE_BYTES
        or type(resource.get("maximum_proof_bytes_observed")) is not int
        or resource["maximum_proof_bytes_observed"] > FORMAL_PROOF_LIMIT_BYTES
        or type(resource.get("cgroup_stable")) is not bool
        or resource.get("cgroup_stable") is not derived_cgroup_stable
        or not _type_exact_equal(
            resource.get("memory_event_deltas"),
            derived_event_deltas,
        )
        or type(resource.get("oom_clean")) is not bool
        or resource.get("oom_clean") is not derived_oom_clean
        or resource.get("oom_clean") is not True
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "resource/OOM/disk semantics drifted",
        )
    try:
        telemetry_lines = [line for line in planned["telemetry"].read_text(encoding="utf-8").splitlines() if line]
        telemetry_payloads = [
            _strict_json_loads(line, f"resource telemetry line {index}")
            for index, line in enumerate(telemetry_lines, start=1)
        ]
    except (OSError, UnicodeError, ToolchainError) as exc:
        raise ToolchainError(
            "authority_receipt_failure",
            f"resource telemetry is malformed: {exc}",
        ) from exc
    if (
        len(telemetry_payloads) != resource["sample_count"]
        or not telemetry_payloads
        or not all(isinstance(item, dict) for item in telemetry_payloads)
        or min(item.get("free_bytes", -1) for item in telemetry_payloads) != resource["minimum_free_bytes_observed"]
        or max((item.get("proof_size_bytes") or 0) for item in telemetry_payloads)
        != resource["maximum_proof_bytes_observed"]
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "resource telemetry does not reproduce the recorded extrema",
        )
    for index, sample in enumerate(telemetry_payloads, start=1):
        _closed_telemetry_sample(
            sample,
            field=f"resource_monitor.sample[{index}]",
            expected_cgroup_path=cgroup_start["cgroup_path"],
        )
    if any(
        left["monotonic_nanoseconds"] > right["monotonic_nanoseconds"]
        for left, right in zip(telemetry_payloads, telemetry_payloads[1:])
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "resource telemetry monotonic clock moved backwards",
        )

    started = _strict_json(planned["started"], "toolchain started record")
    expected_started_git = {
        name: git[name]
        for name in (
            "encoder",
            "gate",
            "runner",
            "source_surface_start",
        )
    }
    _replay_started_record(
        started,
        record=record,
        inputs=expected_inputs,
        input_copies=expected_copies,
        strict_inputs=strict_inputs,
        a004_authority=a004_section["preflight"],
        build_authority=build_section["preflight"],
        reservation_source=reservation["source_at_reservation"],
        reservation_copy=reservation["copy"],
        sources=sources["before"],
        git_snapshots=expected_started_git,
        tools=tools["before"],
        execution=execution,
        cgroup=cgroup_start,
    )

    expected_boundary = {
        "research_grade": True,
        "verified_component": (
            "the independently translation-gated complete oriented lex-better dimension OPB above (1188,22) is UNSAT"
        ),
        "assumption": ("the geometric necessity lemmas admitted by the fixed R4 a004 authority are given"),
        "does_not_prove": [
            "the a004-admitted geometric lemmas inside the PB proof",
            "a witness or feasible lower bound",
            "attainability of (1188,22)",
            "global optimality",
            "whole-instance infeasibility",
        ],
        "lower_bound_ledger": "absent_and_unrelated",
        "upper_bound_on_success_only": [1188, 22],
        "upper_bound_on_any_failure": [1190, 34],
        "production_status": "research_only_not_production_certified",
        "next_track": "stop_after_this_regression_round",
        "publication_requires_authority_receipt": True,
    }
    if not _type_exact_equal(record.get("claim_boundary"), expected_boundary):
        raise ToolchainError(
            "authority_receipt_failure",
            "claim boundary semantics drifted",
        )
    if not _type_exact_equal(strict_inputs, record.get("strict_inputs")):
        raise ToolchainError(
            "authority_receipt_failure",
            "strict input closure drifted",
        )
    return success


def _replay_authority_receipt(
    output_dir: Path,
    reservation_marker: Path,
    build_record: Path,
    build_manifest: Path,
    root: Path,
    expected_receipt_identity: Mapping[str, Any],
) -> dict[str, Any]:
    receipt_path = _canonical_regular_file(
        output_dir / "authority_receipt.json",
        "authority receipt",
    )
    record_path = _canonical_regular_file(
        output_dir / "toolchain_record.json",
        "toolchain record",
    )
    manifest_path = _canonical_regular_file(
        output_dir / "SHA256SUMS",
        "formal raw manifest",
    )
    receipt = _strict_json(receipt_path, "authority receipt")
    current_receipt_identity = _file_record(receipt_path, root)
    if not _type_exact_equal(
        current_receipt_identity,
        dict(expected_receipt_identity),
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "authority receipt detached byte identity drifted",
        )
    expected_keys = {
        "schema_version",
        "semantics",
        "created_at_utc",
        "formal_attempt",
        "status",
        "claim",
        "proof_status",
        "upper_bound_update_authorized",
        "production_certified",
        "output_directory",
        "raw_manifest",
        "toolchain_record",
        "reservation_source",
        "reservation_copy",
        "build_record",
        "build_manifest",
        "formula",
        "proof",
    }
    if set(receipt) != expected_keys:
        raise ToolchainError(
            "authority_receipt_failure",
            "authority receipt key set drifted",
        )
    record = _strict_json(record_path, "toolchain record")
    success = _replay_toolchain_record_semantics(
        record,
        output_dir,
        reservation_marker,
        build_record,
        build_manifest,
        root,
    )
    claim = record.get("verified_result_candidate")
    expected_status = "VERIFIED" if success else "FAIL_CLOSED"
    expected_proof_status = "VERIFIED UNSATISFIABLE" if success else "NO_MACHINE_VERIFIED_UNSAT_CLAIM"
    if (
        receipt.get("schema_version") != AUTHORITY_RECEIPT_SCHEMA
        or receipt.get("semantics") != SEMANTICS
        or not _is_utc_timestamp(receipt.get("created_at_utc"))
        or receipt.get("formal_attempt") != "a001"
        or receipt.get("status") != expected_status
        or receipt.get("claim") != claim
        or receipt.get("proof_status") != expected_proof_status
        or receipt.get("upper_bound_update_authorized") is not success
        or receipt.get("production_certified") is not False
        or receipt.get("output_directory") != str(output_dir)
    ):
        raise ToolchainError(
            "authority_receipt_failure",
            "authority receipt claim semantics drifted",
        )
    _receipt_file_record(
        receipt.get("raw_manifest"),
        manifest_path,
        root,
        "raw_manifest",
    )
    _receipt_file_record(
        receipt.get("toolchain_record"),
        record_path,
        root,
        "toolchain_record",
    )
    _receipt_file_record(
        receipt.get("reservation_source"),
        reservation_marker,
        root,
        "reservation_source",
    )
    _receipt_file_record(
        receipt.get("reservation_copy"),
        output_dir / "formal_attempt.reservation.json",
        root,
        "reservation_copy",
    )
    _receipt_file_record(
        receipt.get("build_record"),
        build_record,
        root,
        "build_record",
    )
    _receipt_file_record(
        receipt.get("build_manifest"),
        build_manifest,
        root,
        "build_manifest",
    )
    _receipt_file_record(
        receipt.get("formula"),
        output_dir / "formula.opb",
        root,
        "formula",
    )
    proof = output_dir / "roundingsat.proof.pbp"
    if success:
        _receipt_file_record(receipt.get("proof"), proof, root, "proof")
    elif receipt.get("proof") is not None:
        _receipt_file_record(receipt.get("proof"), proof, root, "proof")
    return {
        "receipt": current_receipt_identity,
        "payload": receipt,
        "claim": claim,
        "status": expected_status,
    }


def _reserve_formal_attempt(
    context: Mapping[str, Any],
    effective_argv: list[str],
) -> Path:
    output_dir = context["output_dir"]
    artifact_root = _canonical_existing_directory(
        ARTIFACT_ROOT,
        "formal artifact root at reservation",
    )
    if output_dir.parent != artifact_root or output_dir.exists() or output_dir.is_symlink():
        raise ToolchainError(
            "output_path_invalid",
            "formal output path changed before reservation",
        )
    marker = artifact_root / ATTEMPT_MARKER_NAME
    try:
        _exclusive_json(
            marker,
            {
                "schema_version": "b1_r4_1188_22_pb_formal_attempt_reservation_v1",
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
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        root_fd = os.open(artifact_root, flags)
        try:
            before = os.fstat(root_fd)
            current = os.stat(artifact_root, follow_symlinks=False)
            if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
                raise ToolchainError(
                    "output_path_invalid",
                    "formal artifact root changed during reservation",
                )
            os.mkdir(output_dir.name, mode=0o700, dir_fd=root_fd)
            created = os.stat(output_dir.name, dir_fd=root_fd, follow_symlinks=False)
            if not stat.S_ISDIR(created.st_mode):
                raise ToolchainError(
                    "output_path_invalid",
                    "reserved formal output is not a directory",
                )
            os.fsync(root_fd)
        finally:
            os.close(root_fd)
    except OSError:
        # The persistent reservation deliberately remains: a001 was consumed.
        raise
    if output_dir.is_symlink() or output_dir.resolve(strict=True) != output_dir:
        raise ToolchainError(
            "output_path_invalid",
            "reserved formal output is not canonical",
        )
    return marker


def _execute(args: argparse.Namespace, effective_argv: list[str]) -> int:
    context = _preflight(args)
    output_dir = context["output_dir"]
    reservation_marker = _reserve_formal_attempt(context, effective_argv)
    planned = _planned_paths(output_dir)
    reservation_identity = _file_record(reservation_marker, context["root"])
    _exclusive_bytes(planned["reservation"], reservation_marker.read_bytes())
    reservation_copy = _file_record(planned["reservation"], context["root"])
    if (
        reservation_copy["sha256"] != reservation_identity["sha256"]
        or reservation_copy["size_bytes"] != reservation_identity["size_bytes"]
    ):
        raise ToolchainError(
            "reservation_identity_drift",
            "formal reservation copy differs from the persistent marker",
        )
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
        "a004_authority": context["a004_authority"],
        "build_authority": context["build_authority"],
        "reservation": {
            "source": reservation_identity,
            "copy": reservation_copy,
        },
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
        and gate_recheck_file["sha256"] == context["inputs"]["translation_gate"]["sha256"]
        and gate_recheck_file["size_bytes"] == context["inputs"]["translation_gate"]["size_bytes"]
        and planned["gate_recheck"].read_bytes() == paths["translation_gate"].read_bytes()
    )
    if not gate_recheck_exact:
        failures.append("translation_gate_recheck_mismatch")
    a004_after_gate = _require_a004_unchanged(
        context["a004_authority"],
        context["root"],
        "after_translation_gate_recheck",
    )
    reservation_after_gate = _require_file_identity(
        reservation_marker,
        reservation_identity,
        context["root"],
        "after_translation_gate_recheck",
        "reservation_identity_drift",
    )

    version: dict[str, Any] | None = None
    if gate_recheck_exact and not failures:
        version = _run_child(
            [str(paths["veripb"]), "--version"],
            stdout_path=planned["version_stdout"],
            stderr_path=planned["version_stderr"],
            wall_timeout=30,
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
        version is not None and _veripb_version_ok(planned["version_stdout"], planned["version_stderr"], version)
    )
    if version is not None and not version_exact:
        failures.append("veripb_version_mismatch")
    a004_before_solver = _require_a004_unchanged(
        context["a004_authority"],
        context["root"],
        "before_roundingsat",
    )
    reservation_before_solver = _require_file_identity(
        reservation_marker,
        reservation_identity,
        context["root"],
        "before_roundingsat",
        "reservation_identity_drift",
    )

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
    solver_declared_unsat = _stdout_status_exact(planned["solver_stdout"], planned["solver_stderr"], "s UNSATISFIABLE")
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
    a004_after_solver = _require_a004_unchanged(
        context["a004_authority"],
        context["root"],
        "after_roundingsat",
    )

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
    a004_after_verifier = _require_a004_unchanged(
        context["a004_authority"],
        context["root"],
        "after_veripb",
    )
    reservation_after_verifier = _require_file_identity(
        reservation_marker,
        reservation_identity,
        context["root"],
        "after_veripb",
        "reservation_identity_drift",
    )
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
    source_files_end = {name: _optional_file_record(path, context["root"]) for name, path in source_paths.items()}
    source_files_stable = source_files_end == context["sources"]
    if not source_files_stable:
        failures.append("source_file_hash_drift")
    input_end = {
        name: _optional_file_record(paths[name], context["root"])
        for name in (
            "opb",
            "meta",
            "var_map",
            "estimate",
            "translation_gate",
            "build_record",
            "build_manifest",
        )
    }
    inputs_stable = all(_type_exact_equal(input_end[name], context["inputs"][name]) for name in input_end)
    if not inputs_stable:
        failures.append("input_hash_drift")
    build_authority_end = _validate_build_authority(paths, context["root"])
    build_authority_stable = _type_exact_equal(
        build_authority_end,
        context["build_authority"],
    )
    if not build_authority_stable:
        failures.append("build_authority_drift")

    cgroup_end = _cgroup_state(args.expected_systemd_unit, False)
    cgroup_stable = bool(
        cgroup_end["contract_pass"]
        and cgroup_end["cgroup_path"] == context["cgroup_start"]["cgroup_path"]
        and cgroup_end["systemd_properties"] == context["cgroup_start"]["systemd_properties"]
    )
    if not cgroup_stable:
        failures.append("resource_contract_mismatch")
    event_deltas = _event_deltas(context["cgroup_start"]["memory_events"], cgroup_end["memory_events"])
    oom_clean = bool(event_deltas is not None and all(event_deltas.get(key, 0) == 0 for key in OOM_EVENT_KEYS))
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
    formula_record = _file_record(planned["opb"], context["root"])
    proof_record = _optional_file_record(planned["proof"], context["root"])
    artifact_manifest = _write_checksum_manifest(output_dir, planned["checksums"])
    artifact_manifest_stable = _checksum_manifest_stable(output_dir, planned["checksums"], artifact_manifest)
    manifest_entries = artifact_manifest["entries"]
    critical_manifest_hashes_match = bool(
        manifest_entries.get(planned["opb"].name) == formula_hash_after_verifier
        and proof_hash_after_verifier is not None
        and manifest_entries.get(planned["proof"].name) == proof_hash_after_verifier
        and manifest_entries.get(planned["telemetry"].name) == telemetry_record["sha256"]
        and gate_recheck_file is not None
        and manifest_entries.get(planned["gate_recheck"].name) == gate_recheck_file["sha256"]
        and all(
            manifest_entries.get(planned[planned_name].name) == copied_inputs[source_name]["sha256"]
            for source_name, planned_name in {
                "opb": "opb",
                "meta": "meta",
                "var_map": "var_map",
                "estimate": "estimate",
                "translation_gate": "gate",
                "build_record": "build_record",
                "build_manifest": "build_manifest",
            }.items()
        )
        and manifest_entries.get(planned["reservation"].name) == reservation_copy["sha256"]
        and all(
            manifest_entries.get(Path(child[stream]["path"]).name) == child[stream]["sha256"]
            for child in (gate_recheck, version, solver, verifier)
            if child is not None
            for stream in ("stdout", "stderr")
        )
    )
    if not artifact_manifest_stable:
        failures.append("artifact_manifest_recheck_failed")
    if not critical_manifest_hashes_match:
        failures.append("artifact_manifest_critical_hash_mismatch")
    a004_final = _require_a004_unchanged(
        context["a004_authority"],
        context["root"],
        "before_final_claim",
    )
    reservation_final = _require_file_identity(
        reservation_marker,
        reservation_identity,
        context["root"],
        "before_final_claim",
        "reservation_identity_drift",
    )
    failures = list(dict.fromkeys(failures))
    verified_result_candidate = (
        "machine_verified_complete_lex_better_band_unsat_given_a004_admitted_geometric_lemmas"
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
        "build_authority": {
            "preflight": context["build_authority"],
            "after_execution": build_authority_end,
            "stable": build_authority_stable,
        },
        "reservation": {
            "source_at_reservation": reservation_identity,
            "copy": reservation_copy,
            "after_translation_gate": reservation_after_gate,
            "before_roundingsat": reservation_before_solver,
            "after_veripb": reservation_after_verifier,
            "before_final_claim": reservation_final,
            "stable": True,
        },
        "a004_authority": {
            "preflight": context["a004_authority"],
            "after_translation_gate": a004_after_gate,
            "before_roundingsat": a004_before_solver,
            "after_roundingsat": a004_after_solver,
            "after_veripb": a004_after_verifier,
            "before_final_claim": a004_final,
            "stable": True,
        },
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
        "claim": "none",
        "verified_result_candidate": verified_result_candidate,
        "upper_bound_update_authorized": False,
        "publication_status": ("requires_successful_detached_authority_receipt_replay"),
        "claim_boundary": {
            "research_grade": True,
            "verified_component": (
                "the independently translation-gated complete oriented lex-better "
                "dimension OPB above (1188,22) is UNSAT"
            ),
            "assumption": ("the geometric necessity lemmas admitted by the fixed R4 a004 authority are given"),
            "does_not_prove": [
                "the a004-admitted geometric lemmas inside the PB proof",
                "a witness or feasible lower bound",
                "attainability of (1188,22)",
                "global optimality",
                "whole-instance infeasibility",
            ],
            "lower_bound_ledger": "absent_and_unrelated",
            "upper_bound_on_success_only": [1188, 22],
            "upper_bound_on_any_failure": [1190, 34],
            "production_status": "research_only_not_production_certified",
            "next_track": "stop_after_this_regression_round",
            "publication_requires_authority_receipt": True,
        },
    }
    _exclusive_json(planned["record"], record)
    receipt = {
        "schema_version": AUTHORITY_RECEIPT_SCHEMA,
        "semantics": SEMANTICS,
        "created_at_utc": _utc_now(),
        "formal_attempt": "a001",
        "status": ("VERIFIED" if verified_result_candidate != "none" else "FAIL_CLOSED"),
        "claim": verified_result_candidate,
        "proof_status": (
            "VERIFIED UNSATISFIABLE" if verified_result_candidate != "none" else "NO_MACHINE_VERIFIED_UNSAT_CLAIM"
        ),
        "upper_bound_update_authorized": (verified_result_candidate != "none"),
        "production_certified": False,
        "output_directory": str(output_dir),
        "raw_manifest": artifact_manifest["file"],
        "toolchain_record": _file_record(planned["record"], context["root"]),
        "reservation_source": reservation_final,
        "reservation_copy": reservation_copy,
        "build_record": input_end["build_record"],
        "build_manifest": input_end["build_manifest"],
        "formula": formula_record,
        "proof": proof_record,
    }
    _exclusive_json(planned["receipt"], receipt)
    receipt_identity = _file_record(planned["receipt"], context["root"])
    replayed_receipt = _replay_authority_receipt(
        output_dir,
        reservation_marker,
        paths["build_record"],
        paths["build_manifest"],
        context["root"],
        receipt_identity,
    )
    print(
        json.dumps(
            {
                "claim": replayed_receipt["claim"],
                "raw_record_claim": record["claim"],
                "verified_result_candidate": verified_result_candidate,
                "failure_codes": failures,
                "record": str(planned["record"]),
                "authority_receipt": replayed_receipt["receipt"],
            },
            sort_keys=True,
        )
    )
    return 0 if replayed_receipt["claim"] != "none" else 1


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
        artifact_root = _canonical_existing_directory(
            ARTIFACT_ROOT,
            "formal artifact root for failure marker",
        )
        output_dir = args.output_dir.absolute()
        mode = output_dir.lstat().st_mode
        if (
            stat.S_ISLNK(mode)
            or not stat.S_ISDIR(mode)
            or output_dir.resolve(strict=True) != output_dir
            or output_dir.parent != artifact_root
            or FORMAL_OUTPUT_RE.fullmatch(output_dir.name) is None
            or (output_dir / "toolchain_record.json").exists()
        ):
            return
        payload: dict[str, Any] = {
            "schema_version": "b1_r4_1188_22_pb_failure_v1",
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
        previous_handlers = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}

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
