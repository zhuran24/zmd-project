#!/usr/bin/env python3
"""Run the locked 512-case B1 conditional-halo diagnostic corpus.

This orchestration layer is deliberately SAT-construction-only: every control
and treatment arm must be closed by the deterministic constructor followed by
the independent assignment checker.  It never invokes RoundingSat, VeriPB, or
any other formal-proof fallback.  Cases run sequentially in canonical corpus
order and become resumable only after an exclusive, independently checked
checkpoint has been written.

The output directory is no-overwrite.  A first invocation must name a path
that does not exist; a later invocation must pass ``--resume`` and match the
byte-locked batch identity.  Interrupted attempts remain as immutable history
and are never reused as evidence.  A new attempt directory is allocated for
the next try.  At least 10 GiB of free space is required before every child
and after every case.  Low disk or an UNKNOWN construction closes the current
invocation as INCOMPLETE without a global mathematical claim.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from contextlib import suppress
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any


SCHEMA = "b1_conditional_halo_diagnostic_orchestration_v1"
IDENTITY_SCHEMA = "b1_conditional_halo_diagnostic_batch_identity_v1"
SUBPROCESS_SCHEMA = "b1_conditional_halo_subprocess_record_v1"
CHECKPOINT_SCHEMA = "b1_conditional_halo_case_checkpoint_v1"
RUN_INDEX_SCHEMA = "b1_conditional_halo_run_index_v1"
CORPUS_SCHEMA = "b1_conditional_halo_diagnostic_corpus_v1"
PAIR_RUN_SCHEMA = "b1_conditional_halo_pair_run_v1"
MANIFEST_VERIFICATION_SCHEMA = "b1_conditional_halo_run_manifest_verification_v1"
COMPLETION_SCHEMA = "b1_conditional_halo_diagnostic_completion_v1"
TRANSLATION_GATE_SCHEMA = "b1_conditional_halo_translation_gate_v1"
CANARY_SCHEMA = "b1_conditional_halo_encoder_canaries_v1"
TRANSLATION_ADMISSION_SCHEMA = "b1_conditional_halo_translation_admission_v1"
ASSIGNMENT_SCHEMA = "b1_conditional_halo_full_assignment_v1"
CHECKED_SAT_SCHEMA = "b1_conditional_halo_sat_assignment_check_v1"

EXPECTED_CASES = 512
EXPECTED_ARMS = 1_024
ARTIFACT_LOW_WATER_BYTES = 10 * 1024**3
DEFAULT_NODE_LIMIT = 250_000
CHILD_WALL_TIMEOUT_SECONDS = 300
PROCESS_GROUP_TERM_GRACE_SECONDS = 5.0
PROCESS_GROUP_KILL_GRACE_SECONDS = 5.0
PROCESS_GROUP_POLL_SECONDS = 0.05
LOCKED_CORPUS_SHA256 = "8ec528984431b89bed95008f8d56290b11d5e105d89aec107b1aa85689d7843d"
LOCKED_GEOMETRY_ADMISSION_SHA256 = "22f25ecb1b0cf22190f8ea3add3a5f422d6f51f19577d906286a6c97a571d0da"
LOCKED_STENCIL_SHA256 = "e862ac93b6a27793de764507ace7b2c736122efdd8184f30a205aba551bda1e7"
EXPECTED_PYTHON = Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESEARCH_DIR = Path(__file__).resolve().parent
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts/track_b_b1_conditional_halo_20260722"
AUTHORITY_RUN_ID = "run-20260722T015946Z-zkMRiF"
AUTHORITY_RUN_ROOT = ARTIFACT_ROOT / AUTHORITY_RUN_ID
AUTHORITY_SCAN_ROOT = AUTHORITY_RUN_ROOT / "scan"
MANIFEST_NAME = "SHA256SUMS.recursive"
PAIR_RUN_NAME = "pair_run.json"
SOURCE_MANIFEST_NAME = "SHA256SUMS.source"
ORCHESTRATION_MANIFEST_NAME = "SHA256SUMS.orchestration"

SCRIPT_NAMES = {
    "encoder": "b1_conditional_halo_fixed_rectangle_encoder_v1.py",
    "translation_gate": "verify_b1_conditional_halo_translation_v1.py",
    "canaries": "run_b1_conditional_halo_encoder_canaries_v1.py",
    "translation_admission": "close_b1_conditional_halo_translation_gate_v1.py",
    "constructor": "construct_b1_conditional_halo_sat_assignment_v1.py",
    "sat_checker": "check_b1_conditional_halo_sat_assignment_v1.py",
    "pair_runner": "run_b1_conditional_halo_scan_v1.py",
    "manifest_verifier": "verify_b1_conditional_halo_run_manifest_v1.py",
    "completion": "close_b1_conditional_halo_diagnostic_completion_v1.py",
}


class OrchestrationError(ValueError):
    """A batch identity, artifact, subprocess, or completion check failed."""


class IncompleteRun(RuntimeError):
    """The batch stopped safely without authorizing a mathematical claim."""

    def __init__(self, reason: str, case_index: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.case_index = case_index


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise OrchestrationError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise OrchestrationError(f"non-finite JSON number forbidden: {value}")


def _load(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(
            path.resolve(strict=True).read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except OrchestrationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OrchestrationError(f"cannot load {label}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise OrchestrationError(f"{label} root must be an object")
    return value


def _array(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise OrchestrationError(f"{label} must be an array")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.resolve(strict=True).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _record(path: Path, root: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise OrchestrationError(f"symlink forbidden as provenance input: {path}")
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise OrchestrationError(f"not a regular provenance file: {resolved}")
    return {
        "path": _display(resolved, root),
        "sha256": _sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _record_path(value: Any, root: Path, label: str) -> Path:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256", "size_bytes"}:
        raise OrchestrationError(f"{label} is not an exact file record")
    raw = value.get("path")
    if type(raw) is not str or not raw:
        raise OrchestrationError(f"{label}.path is malformed")
    candidate = Path(raw)
    path = candidate if candidate.is_absolute() else root / candidate
    if _record(path, root) != dict(value):
        raise OrchestrationError(f"{label} is stale")
    return path.resolve(strict=True)


def _pending_target(path: Path) -> Path | None:
    match = re.fullmatch(r"\.(.+)\.pending-(\d{6})", path.name)
    if match is None:
        return None
    if path.is_symlink() or not path.is_file():
        raise OrchestrationError(f"atomic pending object is not a regular file: {path}")
    return path.with_name(match.group(1))


def _next_pending(path: Path) -> Path:
    prefix = f".{path.name}.pending-"
    numbers: list[int] = []
    for child in path.parent.iterdir():
        if not child.name.startswith(prefix):
            continue
        target = _pending_target(child)
        if target != path:
            raise OrchestrationError(f"malformed atomic pending name: {child}")
        numbers.append(int(child.name.removeprefix(prefix)))
    number = max(numbers, default=0) + 1
    if number > 999_999:
        raise OrchestrationError(f"atomic pending identifiers exhausted for {path}")
    return path.with_name(f"{prefix}{number:06d}")


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_publish_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise OrchestrationError(f"unsafe publication directory: {path.parent}")
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"atomic publication target already exists: {path}")
    pending = _next_pending(path)
    with pending.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(pending, path, follow_symlinks=False)
    except BaseException:
        # The unpublished pending bytes are immutable crash history.  A later
        # recovery may publish a new pending generation but never this one.
        raise
    _fsync_directory(path.parent)
    try:
        pending.unlink()
    except OSError:
        # Publication already committed.  A same-inode pending alias is safe
        # to preserve and is ignored by exact artifact-tree verification.
        pass
    else:
        _fsync_directory(path.parent)


def _exclusive_json(path: Path, payload: Any) -> None:
    raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    _atomic_publish_bytes(path, raw)


def _exclusive_text(path: Path, value: str) -> None:
    _atomic_publish_bytes(path, value.encode("ascii"))


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def _ensure_space(path: Path, case_index: int, phase: str) -> int:
    free = _free_bytes(path)
    if free < ARTIFACT_LOW_WATER_BYTES:
        raise IncompleteRun(
            f"artifact_low_water:{phase}:free={free}:required={ARTIFACT_LOW_WATER_BYTES}",
            case_index,
        )
    return free


def _script_paths() -> dict[str, Path]:
    paths = {role: RESEARCH_DIR / name for role, name in SCRIPT_NAMES.items()}
    for role, path in paths.items():
        resolved = path.resolve(strict=True)
        if resolved.parent != RESEARCH_DIR.resolve() or not resolved.is_file() or resolved.is_symlink():
            raise OrchestrationError(f"{role} is not a regular fixed research script: {resolved}")
    return paths


def _validate_python() -> Path:
    expected = EXPECTED_PYTHON.resolve(strict=True)
    actual = Path(sys.executable).resolve(strict=True)
    if actual != expected:
        raise OrchestrationError(f"orchestrator requires fixed Python {expected}; got {actual}")
    return actual


def _validate_corpus(path: Path) -> tuple[Mapping[str, Any], Sequence[Any]]:
    if path.name != "ceiling-diagnostic-corpus-v2.json" or _sha256(path) != LOCKED_CORPUS_SHA256:
        raise OrchestrationError("corpus is not the locked v2 byte identity")
    corpus = _load(path, "locked diagnostic corpus")
    cases = _array(corpus.get("cases"), "corpus.cases")
    if (
        corpus.get("schema_version") != CORPUS_SCHEMA
        or corpus.get("status") != "PASS"
        or corpus.get("manifest_state") != "BUILT_BEFORE_RESULTS"
        or corpus.get("solver_results_included") is not False
        or corpus.get("corpus_errors") != []
        or corpus.get("case_count") != EXPECTED_CASES
        or len(cases) != EXPECTED_CASES
    ):
        raise OrchestrationError("locked diagnostic corpus contract drifted")
    groups: dict[str, list[str]] = {}
    for index, raw in enumerate(cases):
        if not isinstance(raw, Mapping):
            raise OrchestrationError(f"corpus case {index} is not an object")
        expected = {
            "case_index": index,
            "case_id": f"case_{index:03d}",
            "pair_id": f"pair_{index:03d}",
        }
        if any(raw.get(key) != value for key, value in expected.items()):
            raise OrchestrationError(f"corpus case {index} canonical identity drifted")
        group = raw.get("transpose_group_id")
        variant = raw.get("variant")
        if type(group) is not str or variant not in {"original", "transpose"}:
            raise OrchestrationError(f"corpus case {index} transpose identity drifted")
        groups.setdefault(group, []).append(str(variant))
    if len(groups) != 256 or any(variants != ["original", "transpose"] for variants in groups.values()):
        raise OrchestrationError("corpus is not 256 ordered original/transpose groups")
    return corpus, cases


def _identity_payload(
    root: Path,
    output_dir: Path,
    corpus: Path,
    geometry: Path,
    stencil: Path,
    scripts: Mapping[str, Path],
    python: Path,
    node_limit: int,
) -> dict[str, Any]:
    return {
        "schema_version": IDENTITY_SCHEMA,
        "status": "LOCKED_BEFORE_RESULTS",
        "authority_run_id": AUTHORITY_RUN_ID,
        "project_root": str(root),
        "output_directory": str(output_dir),
        "inputs": {
            "corpus": _record(corpus, root),
            "geometry_admission": _record(geometry, root),
            "stencil": _record(stencil, root),
        },
        "tools": {
            "python": _record(python, root),
            "orchestrator": _record(Path(__file__), root),
            "scripts": {role: _record(path, root) for role, path in sorted(scripts.items())},
        },
        "contract": {
            "case_count": EXPECTED_CASES,
            "arm_count": EXPECTED_ARMS,
            "canonical_order": "case_index_0_through_511",
            "model_scope": "diagnostic_fixed_pattern",
            "constructor_node_limit": node_limit,
            "child_wall_timeout_seconds": CHILD_WALL_TIMEOUT_SECONDS,
            "artifact_low_water_bytes": ARTIFACT_LOW_WATER_BYTES,
            "formal_tools_authorized": False,
            "proof_fallback_authorized": False,
            "no_overwrite": True,
        },
        "claim_boundary": [
            "fixed 512-case sampled diagnostic only",
            "every terminal arm must be independently CHECKED_SAT",
            "does not invoke or accept a formal UNSAT proof fallback",
            "does not lower the global upper bound or prove full-band UNSAT",
            "does not prove a witness, attainability, routing feasibility, or global optimality",
            "research artifact; not production CERTIFIED evidence",
        ],
    }


def _recoverable_unpublished_identity(output: Path, identity_path: Path) -> bool:
    """Return true only for an empty/pre-publication batch-root shell."""

    for child in output.iterdir():
        target = _pending_target(child)
        if target != identity_path:
            return False
    return True


def _prepare_output(args: argparse.Namespace, identity: Mapping[str, Any]) -> Path:
    if args.output_dir.is_symlink():
        raise OrchestrationError("output directory must not be a symlink")
    output = args.output_dir.resolve(strict=False)
    artifact_root = AUTHORITY_SCAN_ROOT.resolve(strict=True)
    try:
        output.relative_to(artifact_root)
    except ValueError as exc:
        raise OrchestrationError(f"--output-dir must be below {artifact_root}") from exc
    if output == artifact_root:
        raise OrchestrationError("--output-dir must be a unique child below the B1 artifact root")
    identity_path = output / "batch-identity.json"
    if args.resume:
        resolved = output.resolve(strict=True)
        if resolved.is_symlink() or not resolved.is_dir():
            raise OrchestrationError("resume output must be a real directory")
        if identity_path.exists() or identity_path.is_symlink():
            existing = _load(identity_path, "batch identity")
            if dict(existing) != dict(identity):
                raise OrchestrationError("resume batch identity or source bytes drifted")
        elif _recoverable_unpublished_identity(output, identity_path):
            _exclusive_json(identity_path, identity)
        else:
            raise OrchestrationError("resume root lacks a published identity and is not an empty partial shell")
    else:
        if output.exists():
            raise OrchestrationError("new output directory already exists; use --resume only for an exact identity")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir(mode=0o700, exist_ok=False)
        _exclusive_json(identity_path, identity)
    for name in ("attempts", "checkpoints", "status-events", "finalization"):
        directory = output / name
        directory.mkdir(exist_ok=True)
        if directory.is_symlink() or not directory.is_dir():
            raise OrchestrationError(f"unsafe batch directory: {directory}")
    return output


def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_process_group_exit(pgid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while _process_group_exists(pgid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(PROCESS_GROUP_POLL_SECONDS)
    return True


def _terminate_process_group(process: subprocess.Popen[Any]) -> bool:
    """Terminate only the uniquely owned session/PGID created for ``process``."""

    pgid = process.pid
    if not _process_group_exists(pgid):
        return True
    with suppress(ProcessLookupError):
        os.killpg(pgid, signal.SIGTERM)
    if process.poll() is None:
        with suppress(subprocess.TimeoutExpired):
            process.wait(timeout=PROCESS_GROUP_TERM_GRACE_SECONDS)
    if _wait_for_process_group_exit(pgid, PROCESS_GROUP_TERM_GRACE_SECONDS):
        return True
    with suppress(ProcessLookupError):
        os.killpg(pgid, signal.SIGKILL)
    if process.poll() is None:
        with suppress(subprocess.TimeoutExpired):
            process.wait(timeout=PROCESS_GROUP_KILL_GRACE_SECONDS)
    return _wait_for_process_group_exit(pgid, PROCESS_GROUP_KILL_GRACE_SECONDS)


def _invoke(
    *,
    label: str,
    argv: list[str],
    log_dir: Path,
    root: Path,
    low_water_path: Path,
    case_index: int,
    wall_timeout_seconds: float = CHILD_WALL_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    if wall_timeout_seconds <= 0:
        raise OrchestrationError("child wall timeout must be positive")
    _ensure_space(low_water_path, case_index, f"before_{label}")
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{label}.stdout"
    stderr_path = log_dir / f"{label}.stderr"
    record_path = log_dir / f"{label}.json"
    if any(path.exists() for path in (stdout_path, stderr_path, record_path)):
        raise OrchestrationError(f"subprocess log collision for {label}")
    started_utc = _utc_now()
    started_ns = time.time_ns()
    started = time.monotonic()
    process: subprocess.Popen[str] | None = None
    process_group_clean = True
    descendant_cleanup_performed = False
    termination_reason = "completed"
    interrupted: BaseException | None = None
    env = os.environ.copy()
    env.update({"LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "TZ": "UTC"})
    with (
        stdout_path.open("x", encoding="utf-8", newline="\n") as stdout,
        stderr_path.open("x", encoding="utf-8", newline="\n") as stderr,
    ):
        try:
            process = subprocess.Popen(
                argv,
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                text=True,
                start_new_session=True,
            )
            try:
                exit_code = process.wait(timeout=wall_timeout_seconds)
            except subprocess.TimeoutExpired:
                termination_reason = "wall_timeout"
                descendant_cleanup_performed = True
                process_group_clean = _terminate_process_group(process)
                exit_code = process.returncode if process.returncode is not None else -999
                interrupted = OrchestrationError(
                    f"{label} exceeded {wall_timeout_seconds:g}s wall timeout; "
                    f"process_group_clean={process_group_clean}"
                )
            else:
                if _process_group_exists(process.pid):
                    termination_reason = "descendant_cleanup_after_parent_exit"
                    descendant_cleanup_performed = True
                    process_group_clean = _terminate_process_group(process)
                    if not process_group_clean:
                        interrupted = OrchestrationError(f"{label} left an unclean uniquely owned process group")
        except BaseException as exc:
            if interrupted is None:
                interrupted = exc
            if termination_reason == "completed":
                termination_reason = f"interrupted:{type(exc).__name__}"
            exit_code = -999 if process is None else process.poll()
            if process is not None:
                descendant_cleanup_performed = _process_group_exists(process.pid)
                process_group_clean = _terminate_process_group(process)
                exit_code = process.returncode
        finally:
            stdout.flush()
            stderr.flush()
    ended_ns = time.time_ns()
    payload = {
        "schema_version": SUBPROCESS_SCHEMA,
        "label": label,
        "case_index": case_index,
        "argv": argv,
        "cwd": str(root),
        "environment_overrides": {"LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "TZ": "UTC"},
        "started_at_utc": started_utc,
        "ended_at_utc": _utc_now(),
        "started_time_ns": started_ns,
        "ended_time_ns": ended_ns,
        "elapsed_seconds": time.monotonic() - started,
        "wall_timeout_seconds": wall_timeout_seconds,
        "pid": process.pid if process is not None else None,
        "exit_code": exit_code,
        "interrupted": interrupted is not None,
        "termination_reason": termination_reason,
        "descendant_cleanup_performed": descendant_cleanup_performed,
        "process_group_clean": process_group_clean,
        "stdout": _record(stdout_path, root),
        "stderr": _record(stderr_path, root),
        "free_bytes_after_subprocess": _free_bytes(low_water_path),
    }
    _exclusive_json(record_path, payload)
    stdout_value = stdout_path.read_text(encoding="utf-8")
    stderr_value = stderr_path.read_text(encoding="utf-8")
    if interrupted is not None:
        raise interrupted
    return subprocess.CompletedProcess(argv, int(exit_code), stdout_value, stderr_value)


def _expect_json(path: Path, schema: str, status: str, label: str) -> Mapping[str, Any]:
    value = _load(path, label)
    if value.get("schema_version") != schema or value.get("status") != status:
        raise OrchestrationError(f"{label} did not close as {schema}/{status}")
    return value


def _require_exit(completed: subprocess.CompletedProcess[str], label: str) -> None:
    if completed.returncode != 0:
        raise OrchestrationError(
            f"{label} exited {completed.returncode}; stdout/stderr are preserved in the attempt log"
        )


def _is_redundant_published_pending(path: Path) -> bool:
    target = _pending_target(path)
    if target is None:
        return False
    if target.is_symlink() or not target.is_file() or not os.path.samefile(path, target):
        raise OrchestrationError(f"pending artifact is not an alias of its published target: {path}")
    return True


def _tree_manifest(directory: Path, manifest_name: str) -> Path:
    entries: list[tuple[str, str]] = []
    for path in sorted(directory.rglob("*"), key=lambda item: item.relative_to(directory).as_posix()):
        relative = path.relative_to(directory).as_posix()
        if _is_redundant_published_pending(path):
            continue
        if path.is_symlink():
            raise OrchestrationError(f"symlink forbidden in artifact tree: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise OrchestrationError(f"non-regular tree artifact: {relative}")
        if relative != manifest_name:
            entries.append((relative, _sha256(path)))
    if not entries:
        raise OrchestrationError("artifact-tree manifest would be empty")
    manifest = directory / manifest_name
    _exclusive_text(manifest, "".join(f"{digest}  {relative}\n" for relative, digest in entries))
    return manifest


def _verify_tree_manifest(manifest: Path, manifest_name: str) -> None:
    directory = manifest.resolve(strict=True).parent
    if manifest.name != manifest_name:
        raise OrchestrationError(f"tree manifest must be named {manifest_name}")
    lines = manifest.read_text(encoding="ascii").splitlines()
    expected: dict[str, str] = {}
    for line_number, line in enumerate(lines, 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\x00\r\n]+)", line)
        if match is None:
            raise OrchestrationError(f"malformed source manifest line {line_number}")
        digest, relative = match.groups()
        pure = PurePosixPath(relative)
        if (
            pure.is_absolute()
            or pure.as_posix() != relative
            or any(part in {"", ".", ".."} for part in pure.parts)
            or relative in expected
            or relative == manifest_name
            or "\\" in relative
        ):
            raise OrchestrationError(f"unsafe source manifest path: {relative!r}")
        expected[relative] = digest
    actual: dict[str, str] = {}
    for path in sorted(directory.rglob("*"), key=lambda item: item.relative_to(directory).as_posix()):
        relative = path.relative_to(directory).as_posix()
        if _is_redundant_published_pending(path):
            continue
        if path.is_symlink():
            raise OrchestrationError(f"symlink in source artifact tree: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise OrchestrationError(f"non-regular source artifact: {relative}")
        if relative != manifest_name:
            actual[relative] = _sha256(path)
    if not expected or list(expected) != sorted(expected) or actual != expected:
        raise OrchestrationError("source artifact manifest is empty, unsorted, or stale")


def _verify_recursive_manifest(run_dir: Path) -> None:
    manifest = run_dir / MANIFEST_NAME
    lines = manifest.resolve(strict=True).read_text(encoding="ascii").splitlines()
    expected: dict[str, str] = {}
    for line_number, line in enumerate(lines, 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\x00\r\n]+)", line)
        if match is None:
            raise OrchestrationError(f"malformed pair manifest line {line_number}")
        digest, relative = match.groups()
        pure = PurePosixPath(relative)
        if (
            pure.is_absolute()
            or pure.as_posix() != relative
            or any(part in {"", ".", ".."} for part in pure.parts)
            or relative in expected
            or relative in {MANIFEST_NAME, PAIR_RUN_NAME}
            or "\\" in relative
        ):
            raise OrchestrationError(f"unsafe pair manifest path: {relative!r}")
        expected[relative] = digest
    if not expected or list(expected) != sorted(expected):
        raise OrchestrationError("pair manifest is empty or not sorted")
    actual: dict[str, str] = {}
    for path in sorted(run_dir.rglob("*"), key=lambda item: item.relative_to(run_dir).as_posix()):
        relative = path.relative_to(run_dir).as_posix()
        if path.is_symlink():
            raise OrchestrationError(f"symlink in pair run: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise OrchestrationError(f"non-regular pair-run artifact: {relative}")
        if relative not in {MANIFEST_NAME, PAIR_RUN_NAME}:
            actual[relative] = _sha256(path)
    if actual != expected:
        raise OrchestrationError("pair recursive manifest is stale")


def _checkpoint_path(output: Path, index: int) -> Path:
    return output / "checkpoints" / f"case-{index:03d}.json"


def _validate_checkpoint(path: Path, case: Mapping[str, Any], root: Path) -> Mapping[str, Any]:
    checkpoint = _load(path, f"checkpoint {case['case_index']}")
    if (
        set(checkpoint)
        != {
            "schema_version",
            "status",
            "entry",
            "attempt_complete",
            "corpus_errors",
        }
        or checkpoint.get("schema_version") != CHECKPOINT_SCHEMA
        or checkpoint.get("status") != "PASS"
        or checkpoint.get("corpus_errors") != []
    ):
        raise OrchestrationError(f"checkpoint {case['case_index']} schema/status drifted")
    entry = checkpoint.get("entry")
    expected_keys = {
        "case_index",
        "case_id",
        "pair_id",
        "transpose_group_id",
        "pair_run",
        "run_manifest",
        "manifest_verification",
    }
    if not isinstance(entry, Mapping) or set(entry) != expected_keys:
        raise OrchestrationError(f"checkpoint {case['case_index']} entry key set drifted")
    for key in ("case_index", "case_id", "pair_id", "transpose_group_id"):
        if entry.get(key) != case.get(key):
            raise OrchestrationError(f"checkpoint {case['case_index']} identity drifted")
    pair_record_path = _record_path(entry["pair_run"], root, "checkpoint.pair_run")
    manifest_path = _record_path(entry["run_manifest"], root, "checkpoint.run_manifest")
    verification_path = _record_path(entry["manifest_verification"], root, "checkpoint.manifest_verification")
    attempt_complete_path = _record_path(checkpoint.get("attempt_complete"), root, "checkpoint.attempt_complete")
    attempt_complete = _load(attempt_complete_path, "checkpoint attempt completion")
    attempt_marker = _load(attempt_complete_path.parent / "attempt-start.json", "checkpoint attempt marker")
    if (
        attempt_complete.get("schema_version") != CHECKPOINT_SCHEMA
        or attempt_complete.get("status") != "PASS"
        or attempt_complete.get("case") != dict(case)
        or attempt_complete.get("entry") != dict(entry)
        or attempt_complete.get("formal_tools_invoked") is not False
        or attempt_marker.get("schema_version") != SCHEMA
        or attempt_marker.get("status") != "STARTED"
        or attempt_marker.get("case") != dict(case)
    ):
        raise OrchestrationError(f"checkpoint {case['case_index']} attempt summary drifted")
    marker_identity_path = _record_path(
        attempt_marker.get("batch_identity"), root, "checkpoint.attempt_marker.batch_identity"
    )
    marker_identity = _load(marker_identity_path, "checkpoint batch identity")
    if (
        marker_identity.get("schema_version") != IDENTITY_SCHEMA
        or marker_identity.get("status") != "LOCKED_BEFORE_RESULTS"
    ):
        raise OrchestrationError("checkpoint attempt does not bind a locked batch identity")
    source_manifest_path = _record_path(attempt_complete.get("source_manifest"), root, "checkpoint.source_manifest")
    if source_manifest_path.name != SOURCE_MANIFEST_NAME:
        raise OrchestrationError("checkpoint source manifest path is not canonical")
    _verify_tree_manifest(source_manifest_path, SOURCE_MANIFEST_NAME)
    orchestration_manifest_path = _record_path(
        attempt_complete.get("orchestration_manifest"), root, "checkpoint.orchestration_manifest"
    )
    _verify_tree_manifest(orchestration_manifest_path, ORCHESTRATION_MANIFEST_NAME)
    source_admission = _load(source_manifest_path.parent / "translation-admission.json", "source admission")
    source_admission_inputs = source_admission.get("inputs")
    if not isinstance(source_admission_inputs, Mapping):
        raise OrchestrationError("source admission input map is missing")
    for role, value in source_admission_inputs.items():
        _record_path(value, root, f"source_admission.inputs.{role}")
    run_dir = pair_record_path.parent
    if pair_record_path.name != PAIR_RUN_NAME or manifest_path != run_dir / MANIFEST_NAME:
        raise OrchestrationError("checkpoint pair-run paths are not canonical")
    _verify_recursive_manifest(run_dir)
    record = _load(pair_record_path, "checkpoint pair run")
    arms = record.get("arms")
    preflight = record.get("preflight")
    if (
        record.get("schema_version") != PAIR_RUN_SCHEMA
        or record.get("status") != "COMPLETE"
        or record.get("case") != dict(case)
        or record.get("case_index") != case.get("case_index")
        or record.get("pair_id") != case.get("pair_id")
        or record.get("attribution") != "treatment_survivor"
        or not isinstance(arms, Mapping)
        or set(arms) != {"control", "treatment"}
        or any(not isinstance(arms[arm], Mapping) or arms[arm].get("terminal_status") != "CHECKED_SAT" for arm in arms)
        or not isinstance(preflight, Mapping)
        or preflight.get("decision") != "NOT_REQUIRED_CHECKED_SAT"
        or preflight.get("formal_tool_checked") is not False
        or preflight.get("formal_child_spawned") is not False
        or record.get("tools") is not None
    ):
        raise OrchestrationError(f"checkpoint {case['case_index']} is not a no-formal two-arm CHECKED_SAT run")
    verification = _load(verification_path, "checkpoint manifest verification")
    if (
        verification.get("schema_version") != MANIFEST_VERIFICATION_SCHEMA
        or verification.get("status") != "PASS"
        or verification.get("corpus_errors") != []
        or verification.get("inputs")
        != {"manifest": _record(manifest_path, root), "pair_run": _record(pair_record_path, root)}
    ):
        raise OrchestrationError(f"checkpoint {case['case_index']} manifest verification drifted")
    return entry


def _validate_unpublished_attempt_shell(attempt: Path) -> None:
    """Accept only bytes that can precede publication of attempt-start.json."""

    marker = attempt / "attempt-start.json"
    for child in attempt.iterdir():
        if child.name in {"source", "orchestration"}:
            if child.is_symlink() or not child.is_dir() or any(child.iterdir()):
                raise OrchestrationError(f"unpublished attempt shell contains nonempty work: {attempt}")
            continue
        if _pending_target(child) == marker:
            continue
        raise OrchestrationError(f"unpublished attempt shell contains unexpected object: {child}")


def _next_attempt(output: Path, case: Mapping[str, Any], root: Path) -> Path:
    index = int(case["case_index"])
    case_root = output / "attempts" / f"case-{index:03d}"
    case_root.mkdir(parents=True, exist_ok=True)
    if case_root.is_symlink() or not case_root.is_dir():
        raise OrchestrationError(f"unsafe case attempt directory: {case_root}")
    numbers = []
    for child in case_root.iterdir():
        match = re.fullmatch(r"attempt-(\d{3})", child.name)
        if match is None or child.is_symlink() or not child.is_dir():
            raise OrchestrationError(f"unexpected object in case attempt history: {child}")
        marker_path = child / "attempt-start.json"
        if marker_path.is_symlink():
            raise OrchestrationError(f"attempt marker must not be a symlink: {marker_path}")
        if not marker_path.exists() and not marker_path.is_symlink():
            _validate_unpublished_attempt_shell(child)
            numbers.append(int(match.group(1)))
            continue
        marker = _load(marker_path, f"case {index} attempt marker")
        if (
            marker.get("schema_version") != SCHEMA
            or marker.get("status") != "STARTED"
            or marker.get("case") != dict(case)
            or marker.get("batch_identity") != _record(output / "batch-identity.json", root)
        ):
            raise OrchestrationError(f"case {index} attempt marker identity drifted: {child}")
        numbers.append(int(match.group(1)))
    number = max(numbers, default=0) + 1
    if number > 999:
        raise OrchestrationError(f"case {index} exhausted immutable attempt identifiers")
    attempt = case_root / f"attempt-{number:03d}"
    attempt.mkdir(mode=0o700, exist_ok=False)
    for name in ("source", "orchestration"):
        (attempt / name).mkdir()
    _exclusive_json(
        attempt / "attempt-start.json",
        {
            "schema_version": SCHEMA,
            "status": "STARTED",
            "started_at_utc": _utc_now(),
            "case": dict(case),
            "batch_identity": _record(output / "batch-identity.json", root),
            "claim_at_start": "none",
        },
    )
    return attempt


def _command(python: Path, script: Path, *arguments: str) -> list[str]:
    return [str(python), str(script), *arguments]


def _run_case(
    *,
    root: Path,
    output: Path,
    case: Mapping[str, Any],
    corpus: Path,
    geometry: Path,
    stencil: Path,
    scripts: Mapping[str, Path],
    python: Path,
    node_limit: int,
) -> Mapping[str, Any]:
    index = int(case["case_index"])
    _ensure_space(output, index, "case_start")
    attempt = _next_attempt(output, case, root)
    source = attempt / "source"
    logs = attempt / "orchestration"
    model_paths: dict[str, Path] = {}
    for arm in ("control", "treatment"):
        model_paths[f"{arm}_opb"] = source / f"{arm}.opb"
        model_paths[f"{arm}_meta"] = source / f"{arm}.meta.json"
        model_paths[f"{arm}_var_map"] = source / f"{arm}.var-map.json"
    encoder_argv = _command(
        python,
        scripts["encoder"],
        "--project-root",
        str(root),
        "--geometry-admission",
        str(geometry),
        "--corpus",
        str(corpus),
        "--case-index",
        str(index),
        "--model-scope",
        "diagnostic_fixed_pattern",
        "--control-opb",
        str(model_paths["control_opb"]),
        "--control-meta",
        str(model_paths["control_meta"]),
        "--control-var-map",
        str(model_paths["control_var_map"]),
        "--treatment-opb",
        str(model_paths["treatment_opb"]),
        "--treatment-meta",
        str(model_paths["treatment_meta"]),
        "--treatment-var-map",
        str(model_paths["treatment_var_map"]),
    )
    _require_exit(
        _invoke(
            label="01_encoder",
            argv=encoder_argv,
            log_dir=logs,
            root=root,
            low_water_path=output,
            case_index=index,
        ),
        "encoder",
    )

    gate = source / "translation-gate.json"
    paired_args = [
        "--project-root",
        str(root),
        "--geometry-admission",
        str(geometry),
        "--corpus",
        str(corpus),
        "--case-index",
        str(index),
        "--model-scope",
        "diagnostic_fixed_pattern",
        "--control-opb",
        str(model_paths["control_opb"]),
        "--control-meta",
        str(model_paths["control_meta"]),
        "--control-var-map",
        str(model_paths["control_var_map"]),
        "--treatment-opb",
        str(model_paths["treatment_opb"]),
        "--treatment-meta",
        str(model_paths["treatment_meta"]),
        "--treatment-var-map",
        str(model_paths["treatment_var_map"]),
    ]
    _require_exit(
        _invoke(
            label="02_translation_gate",
            argv=_command(python, scripts["translation_gate"], *paired_args, "--output", str(gate)),
            log_dir=logs,
            root=root,
            low_water_path=output,
            case_index=index,
        ),
        "translation gate",
    )
    gate_payload = _expect_json(gate, TRANSLATION_GATE_SCHEMA, "PASS", "translation gate")
    if gate_payload.get("case_index") != index or gate_payload.get("model_scope") != "diagnostic_fixed_pattern":
        raise OrchestrationError("translation gate case/scope identity drifted")

    canaries = source / "encoder-canaries.json"
    with tempfile.TemporaryDirectory(prefix=f"b1-r2-case-{index:03d}-") as temporary:
        canary_work = Path(temporary) / "canary-work"
        _require_exit(
            _invoke(
                label="03_encoder_canaries",
                argv=_command(
                    python,
                    scripts["canaries"],
                    *paired_args,
                    "--output-dir",
                    str(canary_work),
                    "--output",
                    str(canaries),
                ),
                log_dir=logs,
                root=root,
                low_water_path=output,
                case_index=index,
            ),
            "encoder canaries",
        )
    canary_payload = _expect_json(canaries, CANARY_SCHEMA, "PASS", "encoder canaries")
    if canary_payload.get("all_killed") is not True or canary_payload.get("case_index") != index:
        raise OrchestrationError("encoder canary closure drifted")

    admission = source / "translation-admission.json"
    admission_argv = _command(
        python,
        scripts["translation_admission"],
        "--project-root",
        str(root),
        "--geometry-admission",
        str(geometry),
        "--corpus",
        str(corpus),
        "--control-opb",
        str(model_paths["control_opb"]),
        "--control-meta",
        str(model_paths["control_meta"]),
        "--control-var-map",
        str(model_paths["control_var_map"]),
        "--treatment-opb",
        str(model_paths["treatment_opb"]),
        "--treatment-meta",
        str(model_paths["treatment_meta"]),
        "--treatment-var-map",
        str(model_paths["treatment_var_map"]),
        "--translation-gate",
        str(gate),
        "--canaries",
        str(canaries),
        "--output",
        str(admission),
    )
    _require_exit(
        _invoke(
            label="04_translation_admission",
            argv=admission_argv,
            log_dir=logs,
            root=root,
            low_water_path=output,
            case_index=index,
        ),
        "translation admission",
    )
    admission_payload = _expect_json(admission, TRANSLATION_ADMISSION_SCHEMA, "PASS", "translation admission")
    if any(
        admission_payload.get(key) != case.get(key)
        for key in ("case_index", "case_id", "pair_id", "transpose_group_id")
    ):
        raise OrchestrationError("translation admission logical pair identity drifted")
    admission_inputs = admission_payload.get("inputs")
    if not isinstance(admission_inputs, Mapping):
        raise OrchestrationError("translation admission input map is missing")
    _record_path(admission_inputs.get("encoder_canaries"), root, "admission canaries")

    checked_paths: dict[str, Path] = {}
    for arm, ordinal in (("control", 5), ("treatment", 7)):
        assignment = source / f"{arm}.assignment.json"
        checked = source / f"{arm}.checked-sat.json"
        constructor = _invoke(
            label=f"{ordinal:02d}_{arm}_constructor",
            argv=_command(
                python,
                scripts["constructor"],
                "--project-root",
                str(root),
                "--geometry-admission",
                str(geometry),
                "--stencil",
                str(stencil),
                "--corpus",
                str(corpus),
                "--case-index",
                str(index),
                "--arm",
                arm,
                "--opb",
                str(model_paths[f"{arm}_opb"]),
                "--metadata",
                str(model_paths[f"{arm}_meta"]),
                "--var-map",
                str(model_paths[f"{arm}_var_map"]),
                "--output",
                str(assignment),
                "--node-limit",
                str(node_limit),
            ),
            log_dir=logs,
            root=root,
            low_water_path=output,
            case_index=index,
        )
        if constructor.returncode == 3:
            unknown = _load(assignment, f"{arm} UNKNOWN construction")
            if unknown.get("status") != "UNKNOWN" or unknown.get("case_index") != index:
                raise OrchestrationError(f"{arm} constructor exit 3 without a bound UNKNOWN record")
            raise IncompleteRun(f"constructor_unknown:{arm}", index)
        _require_exit(constructor, f"{arm} constructor")
        assignment_payload = _load(assignment, f"{arm} assignment")
        if (
            assignment_payload.get("schema_version") != ASSIGNMENT_SCHEMA
            or assignment_payload.get("arm") != arm
            or assignment_payload.get("case_index") != index
        ):
            raise OrchestrationError(f"{arm} constructor output identity drifted")
        _require_exit(
            _invoke(
                label=f"{ordinal + 1:02d}_{arm}_independent_checker",
                argv=_command(
                    python,
                    scripts["sat_checker"],
                    "--project-root",
                    str(root),
                    "--geometry-admission",
                    str(geometry),
                    "--arm",
                    arm,
                    "--opb",
                    str(model_paths[f"{arm}_opb"]),
                    "--metadata",
                    str(model_paths[f"{arm}_meta"]),
                    "--var-map",
                    str(model_paths[f"{arm}_var_map"]),
                    "--assignment",
                    str(assignment),
                    "--output",
                    str(checked),
                ),
                log_dir=logs,
                root=root,
                low_water_path=output,
                case_index=index,
            ),
            f"{arm} independent checker",
        )
        checked_payload = _expect_json(checked, CHECKED_SAT_SCHEMA, "PASS", f"{arm} checked SAT")
        if (
            checked_payload.get("assignment_status") != "CHECKED_SAT"
            or checked_payload.get("arm") != arm
            or checked_payload.get("case_index") != index
        ):
            raise OrchestrationError(f"{arm} checked-SAT identity drifted")
        checked_paths[arm] = checked

    source_manifest = _tree_manifest(source, SOURCE_MANIFEST_NAME)
    pair_run_dir = attempt / "pair-run"
    runner_argv = _command(
        python,
        scripts["pair_runner"],
        "--project-root",
        str(root),
        "--corpus",
        str(corpus),
        "--case-index",
        str(index),
        "--geometry-admission",
        str(geometry),
        "--translation-admission",
        str(admission),
        "--translation-gate",
        str(gate),
        "--control-opb",
        str(model_paths["control_opb"]),
        "--control-meta",
        str(model_paths["control_meta"]),
        "--control-var-map",
        str(model_paths["control_var_map"]),
        "--treatment-opb",
        str(model_paths["treatment_opb"]),
        "--treatment-meta",
        str(model_paths["treatment_meta"]),
        "--treatment-var-map",
        str(model_paths["treatment_var_map"]),
        "--control-checked-sat",
        str(checked_paths["control"]),
        "--treatment-checked-sat",
        str(checked_paths["treatment"]),
        "--output-dir",
        str(pair_run_dir),
    )
    if any("roundingsat" in argument.lower() or "veripb" in argument.lower() for argument in runner_argv):
        raise OrchestrationError("formal tool argument unexpectedly entered the pair-run argv")
    _require_exit(
        _invoke(
            label="09_pair_runner_checked_sat_only",
            argv=runner_argv,
            log_dir=logs,
            root=root,
            low_water_path=output,
            case_index=index,
        ),
        "pair runner",
    )
    pair_record = pair_run_dir / PAIR_RUN_NAME
    pair_payload = _expect_json(pair_record, PAIR_RUN_SCHEMA, "COMPLETE", "pair run")
    pair_preflight = pair_payload.get("preflight")
    if (
        pair_payload.get("case") != dict(case)
        or pair_payload.get("attribution") != "treatment_survivor"
        or not isinstance(pair_preflight, Mapping)
        or pair_preflight.get("decision") != "NOT_REQUIRED_CHECKED_SAT"
        or pair_preflight.get("formal_tool_checked") is not False
        or pair_preflight.get("formal_child_spawned") is not False
        or pair_payload.get("tools") is not None
    ):
        raise OrchestrationError("pair runner did not remain on the checked-SAT-only path")

    manifest_verification = attempt / "manifest-verification.json"
    _require_exit(
        _invoke(
            label="10_independent_recursive_manifest_verifier",
            argv=_command(
                python,
                scripts["manifest_verifier"],
                "--project-root",
                str(root),
                "--run-dir",
                str(pair_run_dir),
                "--manifest",
                str(pair_run_dir / MANIFEST_NAME),
                "--record",
                str(pair_record),
                "--output",
                str(manifest_verification),
            ),
            log_dir=logs,
            root=root,
            low_water_path=output,
            case_index=index,
        ),
        "independent recursive manifest verifier",
    )
    _expect_json(
        manifest_verification,
        MANIFEST_VERIFICATION_SCHEMA,
        "PASS",
        "manifest verification",
    )
    _ensure_space(output, index, "case_end")
    orchestration_manifest = _tree_manifest(logs, ORCHESTRATION_MANIFEST_NAME)
    entry = {
        "case_index": index,
        "case_id": case["case_id"],
        "pair_id": case["pair_id"],
        "transpose_group_id": case["transpose_group_id"],
        "pair_run": _record(pair_record, root),
        "run_manifest": _record(pair_run_dir / MANIFEST_NAME, root),
        "manifest_verification": _record(manifest_verification, root),
    }
    attempt_summary = {
        "schema_version": CHECKPOINT_SCHEMA,
        "status": "PASS",
        "case": dict(case),
        "attempt_directory": str(attempt),
        "source_manifest": _record(source_manifest, root),
        "orchestration_manifest": _record(orchestration_manifest, root),
        "entry": entry,
        "free_bytes_after_case": _free_bytes(output),
        "formal_tools_invoked": False,
        "claim_boundary": ["artifact completion only; no global upper-bound or full-band claim"],
    }
    _exclusive_json(attempt / "attempt-complete.json", attempt_summary)
    checkpoint = {
        "schema_version": CHECKPOINT_SCHEMA,
        "status": "PASS",
        "entry": entry,
        "attempt_complete": _record(attempt / "attempt-complete.json", root),
        "corpus_errors": [],
    }
    _exclusive_json(_checkpoint_path(output, index), checkpoint)
    return _validate_checkpoint(_checkpoint_path(output, index), case, root)


def _existing_entries(output: Path, cases: Sequence[Any], root: Path) -> list[Mapping[str, Any]]:
    entries: list[Mapping[str, Any]] = []
    saw_gap = False
    for index, raw in enumerate(cases):
        if not isinstance(raw, Mapping):
            raise OrchestrationError(f"corpus case {index} is not an object")
        checkpoint = _checkpoint_path(output, index)
        if checkpoint.is_symlink():
            raise OrchestrationError(f"checkpoint must not be a symlink: {checkpoint}")
        if checkpoint.exists():
            if saw_gap:
                raise OrchestrationError("checkpoint sequence has a canonical-order gap")
            entries.append(_validate_checkpoint(checkpoint, raw, root))
        else:
            saw_gap = True
    for child in (output / "checkpoints").iterdir():
        target = _pending_target(child)
        candidate = child if target is None else target
        match = re.fullmatch(r"case-(\d{3})\.json", candidate.name)
        if (
            match is None
            or int(match.group(1)) >= EXPECTED_CASES
            or (target is None and (child.is_symlink() or not child.is_file()))
        ):
            raise OrchestrationError(f"unexpected checkpoint object: {child}")
    return entries


def _run_index_payload(root: Path, corpus: Path, entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(entries) != EXPECTED_CASES:
        raise OrchestrationError("cannot build run index before all 512 checkpoints")
    paired = []
    pair_shas: set[str] = set()
    for index, entry in enumerate(entries):
        if entry.get("case_index") != index:
            raise OrchestrationError("run-index entries are not in canonical case order")
        pair_record_path = _record_path(entry.get("pair_run"), root, f"entry[{index}].pair_run")
        pair_sha = _load(pair_record_path, f"pair run {index}").get("paired_generation_sha256")
        if type(pair_sha) is not str or re.fullmatch(r"[0-9a-f]{64}", pair_sha) is None or pair_sha in pair_shas:
            raise OrchestrationError("paired-generation identities are malformed or duplicate")
        pair_shas.add(pair_sha)
        paired.append(dict(entry))
    return {
        "schema_version": RUN_INDEX_SCHEMA,
        "status": "PASS",
        "corpus_manifest": _record(corpus, root),
        "pair_count": EXPECTED_CASES,
        "arm_count": EXPECTED_ARMS,
        "entries": paired,
        "corpus_errors": [],
    }


def _finalization_attempt(output: Path) -> Path:
    root = output / "finalization"
    numbers = []
    for child in root.iterdir():
        match = re.fullmatch(r"attempt-(\d{3})", child.name)
        if match is None or child.is_symlink() or not child.is_dir():
            raise OrchestrationError(f"unexpected finalization history object: {child}")
        numbers.append(int(match.group(1)))
    number = max(numbers, default=0) + 1
    if number > 999:
        raise OrchestrationError("finalization attempt identifiers exhausted")
    attempt = root / f"attempt-{number:03d}"
    attempt.mkdir(exist_ok=False)
    return attempt


def _complete_batch(
    *,
    root: Path,
    output: Path,
    corpus: Path,
    entries: Sequence[Mapping[str, Any]],
    python: Path,
    completion_script: Path,
) -> Mapping[str, Any]:
    run_index = output / "run-index.json"
    expected_index = _run_index_payload(root, corpus, entries)
    if run_index.is_symlink():
        raise OrchestrationError("canonical run index must not be a symlink")
    if run_index.exists():
        if dict(_load(run_index, "canonical run index")) != expected_index:
            raise OrchestrationError("existing canonical run index is stale")
    else:
        _exclusive_json(run_index, expected_index)
    completion = output / "diagnostic-completion.json"
    if completion.is_symlink():
        raise OrchestrationError("canonical diagnostic completion must not be a symlink")
    if completion.exists():
        value = _expect_json(completion, COMPLETION_SCHEMA, "PASS", "diagnostic completion")
        completion_inputs = value.get("inputs")
        if not isinstance(completion_inputs, Mapping) or completion_inputs.get("run_index") != _record(run_index, root):
            raise OrchestrationError("existing diagnostic completion is stale")
        return value
    finalization = _finalization_attempt(output)
    candidate = finalization / "diagnostic-completion.candidate.json"
    _require_exit(
        _invoke(
            label="01_diagnostic_completion",
            argv=_command(
                python,
                completion_script,
                "--project-root",
                str(root),
                "--corpus",
                str(corpus),
                "--run-index",
                str(run_index),
                "--output",
                str(candidate),
            ),
            log_dir=finalization,
            root=root,
            low_water_path=output,
            case_index=EXPECTED_CASES,
        ),
        "diagnostic completion",
    )
    candidate_value = _expect_json(candidate, COMPLETION_SCHEMA, "PASS", "diagnostic completion candidate")
    candidate_inputs = candidate_value.get("inputs")
    if not isinstance(candidate_inputs, Mapping) or candidate_inputs.get("run_index") != _record(run_index, root):
        raise OrchestrationError("diagnostic completion candidate does not bind the canonical run index")
    _atomic_publish_bytes(completion, candidate.read_bytes())
    published = _expect_json(completion, COMPLETION_SCHEMA, "PASS", "diagnostic completion")
    if dict(published) != dict(candidate_value):
        raise OrchestrationError("published diagnostic completion bytes drifted from the checked candidate")
    return published


def _status_event(
    output: Path,
    *,
    status: str,
    reason: str,
    completed_pairs: int,
    next_case: int | None,
) -> Path:
    event = output / "status-events" / f"status-{time.time_ns()}.json"
    payload = {
        "schema_version": SCHEMA,
        "status": status,
        "recorded_at_utc": _utc_now(),
        "reason": reason,
        "completed_pairs": completed_pairs,
        "completed_arms": 2 * completed_pairs,
        "next_case_index": next_case,
        "free_bytes": _free_bytes(output),
        "artifact_low_water_bytes": ARTIFACT_LOW_WATER_BYTES,
        "formal_tools_invoked": False,
        "global_upper_bound": [1190, 34],
        "global_update_authorized": False,
        "claim_boundary": [
            "batch orchestration status only",
            "INCOMPLETE or FAIL authorizes no SAT, UNSAT, pruning, upper-bound, or stopping claim",
            "sample completion does not establish full-band UNSAT or lower U",
        ],
    }
    _exclusive_json(event, payload)
    return event


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True, help="locked ceiling-diagnostic-corpus-v2.json")
    parser.add_argument("--geometry-admission", type=Path, required=True)
    parser.add_argument("--stencil", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="new batch root, or exact root with --resume")
    parser.add_argument("--resume", action="store_true", help="resume only an exact byte-locked existing batch")
    parser.add_argument("--node-limit", type=int, default=DEFAULT_NODE_LIMIT)
    return parser


def _interrupt_signal(_signum: int, _frame: Any) -> None:
    raise KeyboardInterrupt


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    for interrupt_signal in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(interrupt_signal, _interrupt_signal)
    output: Path | None = None
    completed_count = 0
    try:
        root = args.project_root.resolve(strict=True)
        if root != PROJECT_ROOT.resolve(strict=True):
            raise OrchestrationError("--project-root must identify this isolated worktree")
        if type(args.node_limit) is not int or args.node_limit <= 0:
            raise OrchestrationError("--node-limit must be a positive exact integer")
        python = _validate_python()
        scripts = _script_paths()
        corpus = args.corpus.resolve(strict=True)
        geometry = args.geometry_admission.resolve(strict=True)
        stencil = args.stencil.resolve(strict=True)
        if corpus != (AUTHORITY_RUN_ROOT / "diagnostic-corpus/ceiling-diagnostic-corpus-v2.json").resolve(strict=True):
            raise OrchestrationError("--corpus must be the v2 corpus inside the authority run")
        if geometry != (AUTHORITY_RUN_ROOT / "geometry/geometry-admission.json").resolve(strict=True):
            raise OrchestrationError("--geometry-admission must be the gate inside the authority run")
        _, cases = _validate_corpus(corpus)
        if _sha256(geometry) != LOCKED_GEOMETRY_ADMISSION_SHA256:
            raise OrchestrationError("geometry admission is not the locked authority bytes")
        if _sha256(stencil) != LOCKED_STENCIL_SHA256:
            raise OrchestrationError("conditional-halo stencil is not the locked authority bytes")
        tentative_output = args.output_dir.resolve(strict=False)
        identity = _identity_payload(
            root,
            tentative_output,
            corpus,
            geometry,
            stencil,
            scripts,
            python,
            args.node_limit,
        )
        output = _prepare_output(args, identity)
        entries = _existing_entries(output, cases, root)
        completed_count = len(entries)
        for index in range(completed_count, EXPECTED_CASES):
            case = cases[index]
            if not isinstance(case, Mapping):
                raise OrchestrationError(f"corpus case {index} is not an object")
            entry = _run_case(
                root=root,
                output=output,
                case=case,
                corpus=corpus,
                geometry=geometry,
                stencil=stencil,
                scripts=scripts,
                python=python,
                node_limit=args.node_limit,
            )
            entries.append(entry)
            completed_count += 1
        completion = _complete_batch(
            root=root,
            output=output,
            corpus=corpus,
            entries=entries,
            python=python,
            completion_script=scripts["completion"],
        )
        event = _status_event(
            output,
            status="COMPLETE",
            reason="all_512_pairs_and_1024_arms_closed",
            completed_pairs=completed_count,
            next_case=None,
        )
        print(
            json.dumps(
                {
                    "status": "COMPLETE",
                    "completed_pairs": completed_count,
                    "completion": str(output / "diagnostic-completion.json"),
                    "completion_sha256": _sha256(output / "diagnostic-completion.json"),
                    "status_event": str(event),
                    "proof_status": completion.get("proof_status"),
                },
                sort_keys=True,
            )
        )
        return 0
    except IncompleteRun as exc:
        if output is not None:
            event = _status_event(
                output,
                status="INCOMPLETE",
                reason=exc.reason,
                completed_pairs=completed_count,
                next_case=exc.case_index,
            )
            print(
                json.dumps(
                    {
                        "status": "INCOMPLETE",
                        "reason": exc.reason,
                        "completed_pairs": completed_count,
                        "next_case_index": exc.case_index,
                        "status_event": str(event),
                    },
                    sort_keys=True,
                )
            )
        else:
            print(f"INCOMPLETE: {exc.reason}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        if output is not None:
            event = _status_event(
                output,
                status="INCOMPLETE",
                reason="operator_interrupt",
                completed_pairs=completed_count,
                next_case=completed_count,
            )
            print(
                json.dumps(
                    {
                        "status": "INCOMPLETE",
                        "reason": "operator_interrupt",
                        "completed_pairs": completed_count,
                        "status_event": str(event),
                    },
                    sort_keys=True,
                )
            )
        return 130
    except (OrchestrationError, OSError, subprocess.SubprocessError) as exc:
        if output is not None:
            event = _status_event(
                output,
                status="FAIL",
                reason=f"{type(exc).__name__}: {exc}",
                completed_pairs=completed_count,
                next_case=completed_count,
            )
            print(
                json.dumps(
                    {
                        "status": "FAIL",
                        "reason": f"{type(exc).__name__}: {exc}",
                        "completed_pairs": completed_count,
                        "status_event": str(event),
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
        else:
            print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
