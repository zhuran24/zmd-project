#!/usr/bin/env python3
"""Record and finalize AB16 Gate A without authorizing Gate B.

The ``record-preflight`` command first replays a completed disposable drill,
then runs the repository's package-pinned full preflight and writes immutable
stdout, stderr, and receipt files.  The ``finalize`` command independently
replays those bytes, the live manager/boot epoch, repository HEAD, planned
sources, and the complete resource/terminal chain before publishing one
non-authorizing Gate-A receipt.

Neither command creates a formal campaign, solver selection, or organic arm.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from typing import Any


RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import ab16_campaign_bootstrap_v2 as bootstrap  # noqa: E402
import disposable_drill_authority_v2 as drill_authority  # noqa: E402
import organic_resource_verifier_v2 as verifier  # noqa: E402


PREFLIGHT_SCHEMA = "noncert-cuts-ab16-gate-a-full-preflight-receipt-v3"
GATE_A_SCHEMA = "noncert-cuts-ab16-bootstrap-gate-a-receipt-v2"
PREFLIGHT_PURPOSE = "AB16_GATE_A_FULL_PREFLIGHT"
GATE_A_PURPOSE = "AB16_OFFLINE_SOURCE_SET_PREFLIGHT"
PREFLIGHT_EXECUTION_STRATEGY = "same-fd-python-prefix-and-nested-executable-v2"
RUN_NONCE_RE = re.compile(r"run-[A-Za-z0-9][A-Za-z0-9._-]{4,123}\Z")
APPROVAL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{5,127}\Z")
TIMEOUT_SCALE = "12"
PREFLIGHT_TIMEOUT_SECONDS = 60 * 60
TOOL_SOURCE_ROLE = "script.gate_a_validation_v2"
PREFLIGHT_SOURCE_ROLE = "input.preflight_gate"

_SCRIPT_LOADER = r"""
import hashlib
import os
import stat
import sys
python_fd = int(sys.argv[1])
script_fd = int(sys.argv[2])
python_path = sys.argv[3]
python_mode = int(sys.argv[4])
python_size = int(sys.argv[5])
python_sha256 = sys.argv[6]
source_path = sys.argv[7]
script_mode = int(sys.argv[8])
script_size = int(sys.argv[9])
script_sha256 = sys.argv[10]
forwarded = sys.argv[11:]

def snapshot_fd(fd, expected_mode, expected_size, expected_sha256, label):
    before = os.fstat(fd)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or stat.S_IMODE(before.st_mode) != expected_mode
    ):
        raise RuntimeError(label + " descriptor metadata drifted")
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    chunks = []
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        chunks.append(chunk)
    after = os.fstat(fd)
    before_signature = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_signature = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    raw = b"".join(chunks)
    if (
        before_signature != after_signature
        or len(raw) != expected_size
        or digest.hexdigest() != expected_sha256
    ):
        raise RuntimeError(label + " descriptor identity drifted")
    return raw

snapshot_fd(
    python_fd,
    python_mode,
    python_size,
    python_sha256,
    "Python",
)
raw = snapshot_fd(
    script_fd,
    script_mode,
    script_size,
    script_sha256,
    "script",
)
fd_executable = "/proc/{}/fd/{}".format(os.getpid(), python_fd)
if (
    not os.path.isabs(python_path)
    or not os.path.exists(fd_executable)
    or not os.path.samefile(fd_executable, python_path)
):
    raise RuntimeError("Python descriptor/path join drifted")
sys.executable = fd_executable
sys._base_executable = fd_executable
sys.argv = [source_path, *forwarded]
scope = {
    "__builtins__": __builtins__,
    "__cached__": None,
    "__doc__": None,
    "__file__": source_path,
    "__loader__": None,
    "__name__": "__main__",
    "__package__": None,
    "__spec__": None,
}
exec(compile(raw, source_path, "exec", dont_inherit=True), scope, scope)
""".strip()


def _loader_identity() -> dict[str, object]:
    raw = _SCRIPT_LOADER.encode("utf-8")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


class GateAValidationError(RuntimeError):
    """Gate A evidence is absent, stale, malformed, or non-PASS."""


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _identity(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "mode",
        "path",
        "sha256",
        "size_bytes",
    }:
        raise GateAValidationError(f"{label} identity key set drifted")
    record = value
    if (
        type(record["mode"]) is not int
        or type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["sha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
    ):
        raise GateAValidationError(f"{label} identity is malformed")
    return dict(record)


def _snapshot_identity(path: Path | str) -> dict[str, object]:
    _raw, identity = verifier.snapshot_bytes(_absolute(path))
    return identity


def _same_identity(
    observed: Mapping[str, Any],
    expected: object,
    label: str,
) -> None:
    if dict(observed) != _identity(expected, label):
        raise GateAValidationError(f"{label} byte identity drifted")


def _validate_authority_ready(
    value: object,
    *,
    planned_source_set_digest: str,
    pre_run_identity: Mapping[str, Any],
    run_nonce: str,
    selection_identity: Mapping[str, Any],
) -> Mapping[str, Any]:
    expected_keys = {
        "authorizations",
        "disposable_drill_ready",
        "formal_campaign_created",
        "planned_source_set_digest",
        "pre_run_authority_identity",
        "purpose",
        "run_nonce",
        "schema_version",
        "selection_identity",
        "status",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise GateAValidationError("authority-ready key set drifted")
    if (
        value["authorizations"]
        != {
            "arm_launch_authorized": False,
            "formal_campaign_creation_authorized": False,
            "solver_run_authorized": False,
        }
        or value["disposable_drill_ready"] is not True
        or value["formal_campaign_created"] is not False
        or value["planned_source_set_digest"] != planned_source_set_digest
        or value["pre_run_authority_identity"] != pre_run_identity
        or value["purpose"] != drill_authority.RESULT_PURPOSE
        or value["run_nonce"] != run_nonce
        or value["schema_version"] != drill_authority.RESULT_SCHEMA
        or value["selection_identity"] != selection_identity
        or value["status"] != "PASS"
    ):
        raise GateAValidationError("authority-ready semantics drifted")
    return value


def _mkdir_exclusive(path: Path) -> None:
    absolute = _absolute(path)
    try:
        absolute.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise GateAValidationError(f"no-overwrite directory already exists: {absolute}") from exc


def _planned_sources(authority_root: Path) -> tuple[dict[str, Any], str]:
    path = authority_root / "authority/planned-source-identities.json"
    snapshot = verifier.snapshot_json(path)
    value = snapshot.value
    if set(value) != {
        "planned_source_identities",
        "planned_source_set_digest",
        "purpose",
        "schema_version",
    }:
        raise GateAValidationError("planned-source authority key set drifted")
    sources = value["planned_source_identities"]
    digest = value["planned_source_set_digest"]
    if type(sources) is not dict or type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise GateAValidationError("planned-source authority is malformed")
    return dict(sources), digest


def _reobserve_planned_sources(
    *,
    repository_root: Path,
    sources: Mapping[str, Mapping[str, Any]],
    expected_digest: str,
) -> None:
    strict_paths = {
        role.removeprefix("input."): identity["path"] for role, identity in sources.items() if role.startswith("input.")
    }
    system_paths = {
        role.removeprefix("system."): identity["requested_path"]
        for role, identity in sources.items()
        if role.startswith("system.")
    }
    drill_authority._reobserve_sources(  # noqa: SLF001
        strict_input_paths=strict_paths,
        system_tool_paths=system_paths,
        expected=sources,
        expected_digest=expected_digest,
    )
    head = drill_authority._observe_repository_head(  # noqa: SLF001
        repository_root,
        sources,
    )
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise GateAValidationError("repository HEAD replay is malformed")


def _verify_current_tool(
    *,
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, object]:
    expected_full = sources.get(TOOL_SOURCE_ROLE)
    if type(expected_full) is not dict:
        raise GateAValidationError("Gate-A validation tool is not planned")
    expected = {field: expected_full[field] for field in ("mode", "path", "sha256", "size_bytes")}
    current = _snapshot_identity(Path(__file__))
    _same_identity(current, expected, "Gate-A validation tool")
    return current


def _verify_drill(
    authority_root: Path,
) -> dict[str, object]:
    """Replay the complete immutable drill without writing a new receipt."""

    pre_run_path = authority_root / "attempt/pre-run-authority.json"
    selection_path = authority_root / "attempt/selection.json"
    pre_run = verifier.snapshot_json(pre_run_path)
    selection = verifier.snapshot_json(selection_path)
    verified_pre_run = verifier.validate_pre_run_authority(pre_run.value)
    if verified_pre_run["execution_class"] != "DISPOSABLE_LIVE_DRILL":
        raise GateAValidationError("Gate-A evidence is not a disposable drill")
    paths = verified_pre_run["output_paths"]
    stored = verifier.snapshot_json(paths["detached_replay"])
    replayed = verifier.verify_detached(
        pre_run=pre_run,
        selection=selection,
        inner=verifier.snapshot_json(paths["inner"]),
        preterminal=verifier.snapshot_json(paths["preterminal"]),
        payload_result=verifier.snapshot_json(paths["attempt_result"]),
        resource=verifier.snapshot_json(paths["resource_verification"]),
        reference_acquisition=verifier.snapshot_json(paths["reference_acquisition"]),
        release=verifier.snapshot_json(paths["release"]),
        terminal=verifier.snapshot_json(paths["terminal"]),
        reference_release=verifier.snapshot_json(paths["reference_release"]),
        cleanup=verifier.snapshot_json(paths["cleanup"]),
        detached_epoch=verifier.snapshot_json(verified_pre_run["epoch_observation_paths"]["detached-replay"]),
        verifier_tool_identity=verified_pre_run["tool_identities"]["organic_resource_verifier"],
    )
    if stored.value != replayed or replayed.get("status") != "PASS":
        raise GateAValidationError("disposable drill detached replay differs")
    ready = verifier.snapshot_json(authority_root / "authority/authority-ready.json")
    sources, digest = _planned_sources(authority_root)
    _validate_authority_ready(
        ready.value,
        planned_source_set_digest=digest,
        pre_run_identity=pre_run.identity,
        run_nonce=verified_pre_run["run_nonce"],
        selection_identity=selection.identity,
    )
    _verify_current_tool(sources=sources)
    return {
        "authority_ready_identity": ready.identity,
        "detached_replay_identity": stored.identity,
        "planned_source_set_digest": digest,
        "pre_run": dict(verified_pre_run),
        "pre_run_identity": pre_run.identity,
        "selection_identity": selection.identity,
        "sources": sources,
    }


def _open_verified(
    identity: object,
    label: str,
) -> tuple[int, tuple[int, ...]]:
    expected = _identity(identity, label)
    path = Path(expected["path"])
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise GateAValidationError(f"cannot open pinned {label}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise GateAValidationError(f"pinned {label} is not a regular file")
        os.lseek(descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(descriptor)
        signature = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != signature or {
            "mode": stat.S_IMODE(after.st_mode),
            "path": str(path),
            "sha256": digest.hexdigest(),
            "size_bytes": size,
        } != expected:
            raise GateAValidationError(f"pinned {label} identity drifted")
        return descriptor, signature
    except Exception:
        os.close(descriptor)
        raise


def _recheck_open(
    descriptor: int,
    signature: tuple[int, ...],
    expected: object,
    label: str,
) -> None:
    observed = os.fstat(descriptor)
    current = (
        observed.st_dev,
        observed.st_ino,
        observed.st_mode,
        observed.st_nlink,
        observed.st_size,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )
    if current != signature:
        raise GateAValidationError(f"pinned {label} metadata drifted")
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    expected_record = _identity(expected, label)
    if digest.hexdigest() != expected_record["sha256"] or size != expected_record["size_bytes"]:
        raise GateAValidationError(f"pinned {label} bytes drifted")


def _run_same_fd_python_script(
    *,
    python_identity: Mapping[str, Any],
    script_identity: Mapping[str, Any],
    repository: Path,
    forwarded: Sequence[str],
    environment: Mapping[str, str],
    timeout_seconds: float,
) -> subprocess.CompletedProcess[bytes]:
    """Run one script while the verified Python and script FDs remain open."""

    verified_python = _identity(python_identity, "preflight Python")
    verified_script = _identity(script_identity, "preflight script")
    python_fd, python_signature = _open_verified(
        verified_python,
        "preflight Python",
    )
    try:
        script_fd, script_signature = _open_verified(
            verified_script,
            "preflight script",
        )
    except Exception:
        os.close(python_fd)
        raise
    actual_argv = [
        str(verified_python["path"]),
        "-I",
        "-c",
        _SCRIPT_LOADER,
        str(python_fd),
        str(script_fd),
        str(verified_python["path"]),
        str(verified_python["mode"]),
        str(verified_python["size_bytes"]),
        str(verified_python["sha256"]),
        str(verified_script["path"]),
        str(verified_script["mode"]),
        str(verified_script["size_bytes"]),
        str(verified_script["sha256"]),
        *forwarded,
    ]
    try:
        return subprocess.run(
            actual_argv,
            check=False,
            close_fds=True,
            cwd=repository,
            env=dict(environment),
            executable=f"/proc/self/fd/{python_fd}",
            pass_fds=(python_fd, script_fd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    finally:
        try:
            _recheck_open(
                python_fd,
                python_signature,
                verified_python,
                "preflight Python",
            )
            _recheck_open(
                script_fd,
                script_signature,
                verified_script,
                "preflight script",
            )
        finally:
            os.close(script_fd)
            os.close(python_fd)


def record_full_preflight(
    *,
    authority_root: Path | str,
    repository_root: Path | str,
    output_dir: Path | str,
) -> dict[str, object]:
    """Run one package-pinned full preflight after a detached drill PASS."""

    root = _absolute(authority_root)
    repository = _absolute(repository_root)
    evidence = _verify_drill(root)
    pre_run = evidence["pre_run"]
    if pre_run["repository_root"] != str(repository):
        raise GateAValidationError("preflight repository root differs from drill")
    sources = evidence["sources"]
    _reobserve_planned_sources(
        repository_root=repository,
        sources=sources,
        expected_digest=evidence["planned_source_set_digest"],
    )
    expected_head = pre_run["repository_head"]
    observed_head = drill_authority._observe_repository_head(  # noqa: SLF001
        repository,
        sources,
    )
    if observed_head != expected_head:
        raise GateAValidationError("repository HEAD drifted before full preflight")
    python_identity = pre_run["tool_identities"]["python3_13"]
    preflight_full = sources.get(PREFLIGHT_SOURCE_ROLE)
    if type(preflight_full) is not dict:
        raise GateAValidationError("preflight script is not a planned input")
    preflight_identity = {field: preflight_full[field] for field in ("mode", "path", "sha256", "size_bytes")}
    output = _absolute(output_dir)
    _mkdir_exclusive(output)
    started_at_utc = _utc_now()
    started_ns = time.monotonic_ns()
    environment = dict(os.environ)
    environment["PREFLIGHT_TIMEOUT_SCALE"] = TIMEOUT_SCALE
    timed_out = False
    try:
        completed = _run_same_fd_python_script(
            python_identity=python_identity,
            script_identity=preflight_identity,
            repository=repository,
            forwarded=("--full",),
            environment=environment,
            timeout_seconds=PREFLIGHT_TIMEOUT_SECONDS,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
    finished_ns = time.monotonic_ns()
    stdout_identity = bootstrap.authority.write_exclusive(
        output / "stdout.log",
        stdout,
        mode=0o444,
    )
    stdout_identity = {
        "mode": 0o444,
        **stdout_identity,
    }
    stderr_identity = bootstrap.authority.write_exclusive(
        output / "stderr.log",
        stderr,
        mode=0o444,
    )
    stderr_identity = {
        "mode": 0o444,
        **stderr_identity,
    }
    receipt = {
        "authorizations": {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        },
        "authority_ready_identity": evidence["authority_ready_identity"],
        "command": {
            "argv": [
                python_identity["path"],
                "-I",
                preflight_identity["path"],
                "--full",
            ],
            "execution_strategy": PREFLIGHT_EXECUTION_STRATEGY,
            "loader_identity": _loader_identity(),
        },
        "detached_replay_identity": evidence["detached_replay_identity"],
        "duration_monotonic_ns": finished_ns - started_ns,
        "exit_code": exit_code,
        "finished_at_utc": _utc_now(),
        "planned_source_set_digest": evidence["planned_source_set_digest"],
        "pre_run_authority_identity": evidence["pre_run_identity"],
        "preflight_script_identity": preflight_identity,
        "preflight_timeout_scale": TIMEOUT_SCALE,
        "purpose": PREFLIGHT_PURPOSE,
        "python_identity": python_identity,
        "repository_head": expected_head,
        "repository_root": str(repository),
        "runner_tool_identity": _verify_current_tool(sources=sources),
        "schema_version": PREFLIGHT_SCHEMA,
        "started_at_utc": started_at_utc,
        "status": "PASS" if exit_code == 0 and not timed_out else "FAIL_CLOSED",
        "stderr_identity": stderr_identity,
        "stdout_identity": stdout_identity,
        "timed_out": timed_out,
    }
    receipt_identity = bootstrap.authority.write_exclusive(
        output / "receipt.json",
        verifier.canonical_json_bytes(receipt),
        mode=0o444,
    )
    return {
        "receipt": receipt,
        "receipt_identity": {
            "mode": 0o444,
            **receipt_identity,
        },
        "status": receipt["status"],
    }


def _verify_preflight_receipt(
    *,
    receipt_path: Path | str,
    evidence: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, object]]:
    snapshot = verifier.snapshot_json(receipt_path)
    receipt = snapshot.value
    expected_keys = {
        "authorizations",
        "authority_ready_identity",
        "command",
        "detached_replay_identity",
        "duration_monotonic_ns",
        "exit_code",
        "finished_at_utc",
        "planned_source_set_digest",
        "pre_run_authority_identity",
        "preflight_script_identity",
        "preflight_timeout_scale",
        "purpose",
        "python_identity",
        "repository_head",
        "repository_root",
        "runner_tool_identity",
        "schema_version",
        "started_at_utc",
        "status",
        "stderr_identity",
        "stdout_identity",
        "timed_out",
    }
    if set(receipt) != expected_keys:
        raise GateAValidationError("full-preflight receipt key set drifted")
    authorizations = receipt["authorizations"]
    if (
        authorizations
        != {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        }
        or receipt["schema_version"] != PREFLIGHT_SCHEMA
        or receipt["purpose"] != PREFLIGHT_PURPOSE
        or receipt["status"] != "PASS"
        or receipt["exit_code"] != 0
        or receipt["timed_out"] is not False
        or receipt["preflight_timeout_scale"] != TIMEOUT_SCALE
        or receipt["authority_ready_identity"] != evidence["authority_ready_identity"]
        or receipt["detached_replay_identity"] != evidence["detached_replay_identity"]
        or receipt["pre_run_authority_identity"] != evidence["pre_run_identity"]
        or receipt["planned_source_set_digest"] != evidence["planned_source_set_digest"]
        or receipt["repository_head"] != evidence["pre_run"]["repository_head"]
        or receipt["repository_root"] != evidence["pre_run"]["repository_root"]
    ):
        raise GateAValidationError("full-preflight receipt is not an exact PASS")
    sources = evidence["sources"]
    expected_script_full = sources[PREFLIGHT_SOURCE_ROLE]
    expected_script = {field: expected_script_full[field] for field in ("mode", "path", "sha256", "size_bytes")}
    if (
        receipt["preflight_script_identity"] != expected_script
        or receipt["python_identity"] != evidence["pre_run"]["tool_identities"]["python3_13"]
        or receipt["runner_tool_identity"] != _verify_current_tool(sources=sources)
        or receipt["command"]
        != {
            "argv": [
                receipt["python_identity"]["path"],
                "-I",
                receipt["preflight_script_identity"]["path"],
                "--full",
            ],
            "execution_strategy": PREFLIGHT_EXECUTION_STRATEGY,
            "loader_identity": _loader_identity(),
        }
    ):
        raise GateAValidationError("full-preflight tool/command identity drifted")
    for field in ("stdout_identity", "stderr_identity"):
        observed = _snapshot_identity(receipt[field]["path"])
        _same_identity(observed, receipt[field], f"full-preflight {field}")
    return receipt, snapshot.identity


def finalize_gate_a(
    *,
    authority_root: Path | str,
    preflight_receipt: Path | str,
    output_path: Path | str,
    approval_id: str,
    target_campaign_dir: Path | str,
    run_nonce: str,
) -> dict[str, object]:
    """Publish one Gate-A PASS that still cannot create a formal campaign."""

    if APPROVAL_ID_RE.fullmatch(approval_id) is None:
        raise GateAValidationError("Gate-A approval_id is invalid")
    if RUN_NONCE_RE.fullmatch(run_nonce) is None:
        raise GateAValidationError("future campaign run nonce is invalid")
    target = _absolute(target_campaign_dir)
    if target.name != run_nonce or target.exists() or target.is_symlink():
        raise GateAValidationError("future campaign target must be absent and match run nonce")
    root = _absolute(authority_root)
    evidence = _verify_drill(root)
    pre_run = evidence["pre_run"]
    sources = evidence["sources"]
    repository = Path(pre_run["repository_root"])
    _reobserve_planned_sources(
        repository_root=repository,
        sources=sources,
        expected_digest=evidence["planned_source_set_digest"],
    )
    observed_head = drill_authority._observe_repository_head(  # noqa: SLF001
        repository,
        sources,
    )
    if observed_head != pre_run["repository_head"]:
        raise GateAValidationError("repository HEAD drifted at Gate-A finalize")
    current_epoch = drill_authority._capture_live_manager_epoch(sources)  # noqa: SLF001
    if current_epoch["manager_epoch"] != pre_run["manager_epoch"]:
        raise GateAValidationError("manager/boot epoch drifted at Gate-A finalize")
    receipt, receipt_identity = _verify_preflight_receipt(
        receipt_path=preflight_receipt,
        evidence=evidence,
    )
    del receipt
    gate_a = {
        "approval_id": approval_id,
        "arm_launch_authorized": False,
        "created_at_utc": _utc_now(),
        "decision": "PASS",
        "disposable_authority_ready_identity": evidence["authority_ready_identity"],
        "disposable_detached_replay_identity": evidence["detached_replay_identity"],
        "formal_campaign_creation_authorized": False,
        "full_preflight_receipt_identity": receipt_identity,
        "gate": "A",
        "history_freeze_replay_identity": pre_run["history_freeze_replay_identity"],
        "manager_epoch": pre_run["manager_epoch"],
        "offline_candidate_only": True,
        "planned_source_set_digest": evidence["planned_source_set_digest"],
        "purpose": GATE_A_PURPOSE,
        "reference_capability_identity": pre_run["reference_capability_identity"],
        "reference_capability_transcript_identity": pre_run["reference_capability_transcript_identity"],
        "repository_head": pre_run["repository_head"],
        "repository_root": pre_run["repository_root"],
        "run_nonce": run_nonce,
        "schema_version": GATE_A_SCHEMA,
        "target_campaign_dir": str(target),
    }
    identity = bootstrap.authority.write_exclusive(
        _absolute(output_path),
        bootstrap.authority.canonical_json(gate_a),
        mode=0o444,
    )
    return {
        "gate_a": gate_a,
        "gate_a_identity": {
            "mode": 0o444,
            **identity,
        },
        "status": "PASS",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preflight = commands.add_parser("record-preflight")
    preflight.add_argument("--authority-root", required=True, type=Path)
    preflight.add_argument("--repository-root", required=True, type=Path)
    preflight.add_argument("--output-dir", required=True, type=Path)
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--authority-root", required=True, type=Path)
    finalize.add_argument("--preflight-receipt", required=True, type=Path)
    finalize.add_argument("--output", required=True, type=Path)
    finalize.add_argument("--approval-id", required=True)
    finalize.add_argument("--target-campaign-dir", required=True, type=Path)
    finalize.add_argument("--run-nonce", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "record-preflight":
            result = record_full_preflight(
                authority_root=args.authority_root,
                repository_root=args.repository_root,
                output_dir=args.output_dir,
            )
        elif args.command == "finalize":
            result = finalize_gate_a(
                authority_root=args.authority_root,
                preflight_receipt=args.preflight_receipt,
                output_path=args.output,
                approval_id=args.approval_id,
                target_campaign_dir=args.target_campaign_dir,
                run_nonce=args.run_nonce,
            )
        else:
            raise GateAValidationError("unknown Gate-A validation command")
    except Exception as exc:
        print(
            json.dumps(
                {
                    "detail": str(exc),
                    "status": "FAIL_CLOSED",
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
