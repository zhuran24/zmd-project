#!/usr/bin/env python3
"""Build one no-overwrite, non-authorizing AB16 disposable-drill authority.

The resulting directory is deliberately outside every formal campaign root.
It binds the complete Gate-A planned source set, the live manager/boot epoch,
the small drill resource contract, and the exact lifecycle entry points.  It
creates no unit and grants no solver, organic-arm, or formal-campaign
authority.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
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
import organic_resource_lifecycle_v2 as lifecycle  # noqa: E402
import organic_resource_verifier_v2 as verifier  # noqa: E402


AUTHORITY_SCHEMA = "noncert-cuts-ab16-disposable-drill-authority-v2"
ROOT_SCHEMA = "noncert-cuts-ab16-disposable-drill-root-v2"
CONTROL_SCHEMA = "noncert-cuts-ab16-disposable-drill-control-v2"
PACKAGE_SCHEMA = "noncert-cuts-ab16-disposable-drill-package-manifest-v2"
RESULT_SCHEMA = "noncert-cuts-ab16-disposable-drill-authority-result-v2"
PURPOSE = "AB16_GATE_A_DISPOSABLE_DRILL_AUTHORITY"
PACKAGE_PURPOSE = "AB16_GATE_A_DISPOSABLE_DRILL_SOURCE_PACKAGE"
RESULT_PURPOSE = "AB16_GATE_A_DISPOSABLE_DRILL_AUTHORITY_READY"
DRILL_SLOT = "region-capacity-ab-control"
RUN_NONCE_RE = re.compile(r"drill-[A-Za-z0-9][A-Za-z0-9_.-]{4,95}\Z")

TOOL_SOURCE_ROLES = {
    "busctl": "system.busctl",
    "manager_attestor": "script.manager_attestor_v4",
    "manager_epoch_authority": "script.campaign_authority_v4",
    "organic_arm_runner": "script.organic_arm_runner_v1",
    "organic_resource_lifecycle": "script.organic_resource_lifecycle_v2",
    "organic_resource_verifier": "script.organic_resource_verifier_v2",
    "organic_unit_orchestrator": "script.organic_unit_orchestrator_v2",
    "python3_13": "system.python3_13",
    "systemd_unit_reference": "script.systemd_unit_reference_v1",
    "sudo": "system.sudo",
    "systemctl": "system.systemctl",
    "systemd_run": "system.systemd_run",
}


class DrillAuthorityError(RuntimeError):
    """The disposable authority could not be built without ambiguity."""


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _identity(value: Mapping[str, Any]) -> dict[str, object]:
    return {
        "mode": value["mode"],
        "path": value["path"],
        "sha256": value["sha256"],
        "size_bytes": value["size_bytes"],
    }


def _snapshot_identity(path: Path | str) -> dict[str, object]:
    return dict(lifecycle.snapshot_regular(_absolute(path)).identity)


def _write(path: Path, value: object) -> dict[str, object]:
    return lifecycle.write_json_exclusive(path, value)


def _mkdir(path: Path) -> None:
    try:
        path.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise DrillAuthorityError(f"no-overwrite directory already exists: {path}") from exc


def _capture_live_manager_epoch(
    planned_sources: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Observe the current epoch with only identities in the planned set."""

    try:
        captured = bootstrap.authority.capture_manager_epoch_with_transcript(
            attestor_path=planned_sources["script.manager_attestor_v4"]["path"],
            busctl_path=planned_sources["system.busctl"]["path"],
            python_path=planned_sources["system.attestor_python"]["path"],
            sudo_path=planned_sources["system.sudo"]["path"],
        )
        if type(captured) is not dict or set(captured) != {
            "manager_epoch",
            "transcript",
        }:
            raise ValueError("live manager capture returned the wrong schema")
        bootstrap.authority.validate_manager_epoch(captured["manager_epoch"])
        bootstrap.authority.validate_manager_epoch_capture_transcript(
            captured["transcript"],
            expected_epoch=captured["manager_epoch"],
        )
    except Exception as exc:
        raise DrillAuthorityError("live manager/boot capture failed closed") from exc
    return captured


def _capture_reference_capability(
    *,
    busctl_identity: Mapping[str, Any],
    manager_epoch: Mapping[str, Any],
) -> tuple[dict[str, object], dict[str, object]]:
    """Run pinned busctl introspection and derive the exact Ref/Unref surface."""

    expected = _identity(busctl_identity)
    path = Path(str(expected["path"]))
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DrillAuthorityError("cannot open pinned busctl for capability capture") from exc
    argv = [
        "busctl",
        "--user",
        "introspect",
        "org.freedesktop.systemd1",
        "/org/freedesktop/systemd1",
        "org.freedesktop.systemd1.Manager",
    ]
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise DrillAuthorityError("pinned busctl is not a singly linked regular file")
        os.lseek(descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        observed = {
            "mode": stat.S_IMODE(before.st_mode),
            "path": str(path),
            "sha256": digest.hexdigest(),
            "size_bytes": size,
        }
        if observed != expected or size != before.st_size:
            raise DrillAuthorityError("pinned busctl identity drifted")
        completed = subprocess.run(
            argv,
            check=False,
            close_fds=True,
            env=dict(os.environ),
            executable=f"/proc/self/fd/{descriptor}",
            pass_fds=(descriptor,),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise DrillAuthorityError("pinned busctl drifted during introspection")
    except subprocess.TimeoutExpired as exc:
        raise DrillAuthorityError("busctl capability introspection timed out") from exc
    finally:
        os.close(descriptor)
    try:
        stdout = completed.stdout.decode("utf-8", "strict")
        stderr = completed.stderr.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise DrillAuthorityError("busctl capability output is not UTF-8") from exc
    if completed.returncode != 0 or stderr:
        raise DrillAuthorityError("busctl capability introspection failed closed")
    methods: dict[str, dict[str, str]] = {}
    for line in stdout.splitlines():
        fields = line.split()
        if fields and fields[0] in {".RefUnit", ".UnrefUnit"}:
            if len(fields) < 5 or fields[1:5] != ["method", "s", "-", "-"]:
                raise DrillAuthorityError("RefUnit/UnrefUnit signature drifted")
            name = fields[0][1:]
            if name in methods:
                raise DrillAuthorityError("duplicate RefUnit/UnrefUnit introspection row")
            methods[name] = {
                "in_signature": fields[2],
                "interface": "org.freedesktop.systemd1.Manager",
                "out_signature": fields[3],
            }
    if set(methods) != {"RefUnit", "UnrefUnit"}:
        raise DrillAuthorityError("RefUnit/UnrefUnit capability is incomplete")
    transcript = {
        "argv": argv,
        "busctl_identity": expected,
        "exit_code": completed.returncode,
        "manager_epoch_digest": lifecycle.epoch_digest(manager_epoch),
        "purpose": "AB16_GATE_A_REFERENCE_CAPABILITY_RAW_TRANSCRIPT",
        "schema_version": "noncert-cuts-ab16-reference-capability-transcript-v1",
        "stderr": stderr,
        "stdout": stdout,
    }
    receipt = {
        "manager_epoch_digest": lifecycle.epoch_digest(manager_epoch),
        "methods": methods,
        "purpose": "AB16_GATE_A_REFERENCE_CAPABILITY_REPLAY",
        "schema_version": "noncert-cuts-ab16-reference-capability-v1",
        "status": "PASS",
        "verdict": "REFUNIT_UNREFUNIT_EXACT_SURFACE_PASS",
    }
    return transcript, receipt


def _observe_repository_head(
    repository_root: Path,
    planned_sources: Mapping[str, Mapping[str, Any]],
) -> str:
    try:
        serialized_git_path = planned_sources["system.git"]["path"]
        if type(serialized_git_path) is not str:
            raise TypeError("planned Git identity path is not a string")
        return bootstrap._observe_repository_head(  # noqa: SLF001
            repository_root,
            Path(serialized_git_path),
            expected_identity=planned_sources["system.git"],
        )
    except Exception as exc:
        raise DrillAuthorityError("repository HEAD replay failed closed") from exc


def _replay_history_freeze(
    *,
    manifest_path: Path | str,
    repository_root: Path,
) -> dict[str, object]:
    snapshot = lifecycle.snapshot_regular(_absolute(manifest_path))
    try:
        value = bootstrap.authority.strict_loads(
            snapshot.raw,
            "terminal-reference history freeze",
        )
    except Exception as exc:
        raise DrillAuthorityError("history-freeze manifest JSON is invalid") from exc
    if bootstrap.authority.canonical_json(value) != snapshot.raw:
        raise DrillAuthorityError("history-freeze manifest is not canonical campaign-authority JSON")
    if type(value) is not dict or set(value) != {
        "created_at_utc",
        "file_count",
        "files",
        "frozen_roots",
        "purpose",
        "repository_head",
        "repository_root",
        "schema_version",
        "v1_source_glob",
    }:
        raise DrillAuthorityError("history-freeze manifest schema drifted")
    if (
        value["schema_version"] != "noncert-cuts-ab16-terminal-reference-history-freeze-v1"
        or value["purpose"] != "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_FREEZE"
        or value["repository_root"] != str(repository_root)
        or value["repository_head"] != "398f8725c770f3c36408adebe9448a890ed886fe"
        or type(value["file_count"]) is not int
        or type(value["files"]) is not list
        or value["file_count"] != len(value["files"])
    ):
        raise DrillAuthorityError("history-freeze manifest scalar semantics drifted")
    seen: set[str] = set()
    for raw in value["files"]:
        if type(raw) is not dict or set(raw) != {
            "mode",
            "path",
            "sha256",
            "size_bytes",
        }:
            raise DrillAuthorityError("history-freeze member schema drifted")
        relative = raw["path"]
        if (
            type(relative) is not str
            or not relative
            or relative in seen
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise DrillAuthorityError("history-freeze member path is invalid")
        seen.add(relative)
        observed = lifecycle.snapshot_regular(repository_root / relative).identity
        if observed != {
            "mode": raw["mode"],
            "path": str(repository_root / relative),
            "sha256": raw["sha256"],
            "size_bytes": raw["size_bytes"],
        }:
            raise DrillAuthorityError("history-freeze member byte identity drifted")
    return {
        "authorizations": {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
        },
        "file_count": len(seen),
        "manifest_identity": snapshot.identity,
        "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_REPLAY",
        "schema_version": "noncert-cuts-ab16-terminal-reference-history-replay-v1",
        "status": "PASS",
        "verdict": "IMMUTABLE_FAILED_GATE_A_HISTORY_REPLAY_PASS",
    }


def _launch_environment() -> dict[str, object]:
    value = {
        "clear_ambient": True,
        "schema_version": lifecycle.LAUNCH_ENVIRONMENT_SCHEMA,
        "variables": {
            "DBUS_SESSION_BUS_ADDRESS": os.environ.get(
                "DBUS_SESSION_BUS_ADDRESS",
                "",
            ),
            "HOME": os.environ.get("HOME", ""),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": os.environ.get("PATH", ""),
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""),
        },
    }
    try:
        lifecycle.validate_launch_environment(value)
    except Exception as exc:
        raise DrillAuthorityError("fixed drill launch environment is invalid") from exc
    return value


def _package(
    package_dir: Path,
    *,
    planned_sources: Mapping[str, Mapping[str, Any]],
    planned_source_set_digest: str,
) -> dict[str, object]:
    """Seal source identities and the exact libsystemd bytes used at runtime."""

    _mkdir(package_dir)
    payload_dir = package_dir / "payload"
    _mkdir(payload_dir)
    source_identity = _identity(planned_sources["system.libsystemd"])
    source_snapshot = lifecycle.snapshot_regular(source_identity["path"])
    if {field: source_snapshot.identity[field] for field in source_identity} != source_identity:
        raise DrillAuthorityError("libsystemd source identity drifted before package copy")
    libsystemd_identity = lifecycle.write_exclusive(
        payload_dir / "libsystemd.so",
        source_snapshot.raw,
    )
    manifest_path = package_dir / "package-manifest.json"
    manifest = {
        "authorizations": {
            "arm_launch_authorized": False,
            "formal_campaign_creation_authorized": False,
            "solver_run_authorized": False,
        },
        "external_source_identities": dict(planned_sources),
        "sealed_payload_identities": {
            "libsystemd": libsystemd_identity,
        },
        "planned_source_set_digest": planned_source_set_digest,
        "purpose": PACKAGE_PURPOSE,
        "schema_version": PACKAGE_SCHEMA,
    }
    manifest_identity = _write(manifest_path, manifest)
    seal_raw = (
        f"{manifest_identity['sha256']}  package-manifest.json\n"
        f"{libsystemd_identity['sha256']}  payload/libsystemd.so\n"
    ).encode("ascii")
    seal_path = package_dir / "SHA256SUMS"
    seal_identity = lifecycle.write_exclusive(seal_path, seal_raw)
    members = {str(item.relative_to(package_dir)) for item in package_dir.rglob("*") if item.is_file()}
    if members != {
        "SHA256SUMS",
        "package-manifest.json",
        "payload/libsystemd.so",
    }:
        raise DrillAuthorityError("disposable package member set drifted")
    return {
        "libsystemd_identity": libsystemd_identity,
        "manifest_identity": manifest_identity,
        "package_id": seal_identity["sha256"],
        "seal_identity": seal_identity,
    }


def _control_record(
    *,
    kind: str,
    run_nonce: str,
    planned_source_set_digest: str,
    paths: Mapping[str, str],
) -> dict[str, object]:
    return {
        "authorizations": {
            "arm_launch_authorized": False,
            "formal_campaign_creation_authorized": False,
            "solver_run_authorized": False,
        },
        "kind": kind,
        "paths": dict(paths),
        "planned_source_set_digest": planned_source_set_digest,
        "purpose": PURPOSE,
        "run_nonce": run_nonce,
        "schema_version": CONTROL_SCHEMA,
    }


def _reobserve_sources(
    *,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
    expected: Mapping[str, Mapping[str, Any]],
    expected_digest: str,
) -> None:
    current, _, _, _ = bootstrap._planned_source_identities(  # noqa: SLF001
        strict_input_paths=strict_input_paths,
        system_tool_paths=system_tool_paths,
    )
    if current != expected or bootstrap._source_set_digest(current) != expected_digest:  # noqa: SLF001
        raise DrillAuthorityError("planned source bytes drifted during authority build")


def build_disposable_drill_authority(
    *,
    output_dir: Path | str,
    repository_root: Path | str,
    repository_head: str,
    run_nonce: str,
    expected_planned_source_set_digest: str,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
) -> dict[str, object]:
    """Publish an inert drill selection without creating a formal campaign."""

    destination = _absolute(output_dir)
    repository = _absolute(repository_root)
    if type(run_nonce) is not str or RUN_NONCE_RE.fullmatch(run_nonce) is None or destination.name != run_nonce:
        raise DrillAuthorityError("drill directory/run nonce binding is invalid")
    if type(repository_head) is not str or re.fullmatch(r"[0-9a-f]{40}", repository_head) is None:
        raise DrillAuthorityError("repository_head is invalid")
    if (
        type(expected_planned_source_set_digest) is not str
        or re.fullmatch(r"[0-9a-f]{64}", expected_planned_source_set_digest) is None
    ):
        raise DrillAuthorityError("planned source-set digest is invalid")
    bootstrap.authority._reject_symlink_chain(destination.parent)  # noqa: SLF001
    if destination.exists() or destination.is_symlink():
        raise DrillAuthorityError("disposable drill authority already exists")

    planned, _, system_paths, _ = bootstrap._planned_source_identities(  # noqa: SLF001
        strict_input_paths=strict_input_paths,
        system_tool_paths=system_tool_paths,
    )
    planned_digest = bootstrap._source_set_digest(planned)  # noqa: SLF001
    if planned_digest != expected_planned_source_set_digest:
        raise DrillAuthorityError("planned source-set digest drifted before drill build")
    observed_head = _observe_repository_head(repository, planned)
    if observed_head != repository_head:
        raise DrillAuthorityError("repository HEAD differs from drill preregistration")
    history_replay = _replay_history_freeze(
        manifest_path=strict_input_paths["history_freeze_manifest"],
        repository_root=repository,
    )
    capture = _capture_live_manager_epoch(planned)
    manager_epoch = capture["manager_epoch"]
    transcript = capture["transcript"]
    capability_transcript, capability_receipt = _capture_reference_capability(
        busctl_identity=planned["system.busctl"],
        manager_epoch=manager_epoch,
    )

    _mkdir(destination)
    authority_dir = destination / "authority"
    attempt_dir = destination / "attempt"
    package_dir = authority_dir / "package"
    _mkdir(authority_dir)
    _mkdir(attempt_dir)

    planned_identity = _write(
        authority_dir / "planned-source-identities.json",
        {
            "planned_source_identities": planned,
            "planned_source_set_digest": planned_digest,
            "purpose": PURPOSE,
            "schema_version": AUTHORITY_SCHEMA,
        },
    )
    transcript_identity = _write(
        authority_dir / "manager-transcript-preselection.json",
        transcript,
    )
    transcript_identity = _snapshot_identity(transcript_identity["path"])
    epoch_record = lifecycle.build_epoch_observation(
        phase="preselection",
        slot=DRILL_SLOT,
        observed_epoch=manager_epoch,
        observed_at_monotonic_ns=time.monotonic_ns(),
        capture_transcript_identity=transcript_identity,
    )
    epoch_identity = _write(
        authority_dir / "manager-epoch-preselection.json",
        epoch_record,
    )
    capability_transcript_identity = _write(
        authority_dir / "reference-capability-transcript.json",
        capability_transcript,
    )
    capability_receipt = {
        **capability_receipt,
        "transcript_identity": capability_transcript_identity,
    }
    capability_identity = _write(
        authority_dir / "reference-capability.json",
        capability_receipt,
    )
    history_replay_identity = _write(
        authority_dir / "history-freeze-replay.json",
        history_replay,
    )
    environment_identity = _write(
        authority_dir / "launch-environment.json",
        _launch_environment(),
    )
    environment_identity = _snapshot_identity(environment_identity["path"])
    package_build = _package(
        package_dir,
        planned_sources=planned,
        planned_source_set_digest=planned_digest,
    )
    libsystemd_identity = package_build["libsystemd_identity"]
    package = {
        "manifest_identity": package_build["manifest_identity"],
        "package_id": package_build["package_id"],
        "seal_identity": package_build["seal_identity"],
    }

    common_prestate_path = authority_dir / "common-prestate.json"
    binding_path = authority_dir / "bindings" / f"{DRILL_SLOT}.json"
    _mkdir(binding_path.parent)
    path_map = {
        "attempt_dir": str(attempt_dir),
        "binding_path": str(binding_path),
        "common_prestate_path": str(common_prestate_path),
        "pre_run_authority_path": str(attempt_dir / "pre-run-authority.json"),
        "runner_selection_path": str(attempt_dir / "selection.json"),
    }
    root_identity = _write(
        authority_dir / "drill-root.json",
        {
            **_control_record(
                kind="DISPOSABLE_DRILL_ROOT",
                run_nonce=run_nonce,
                planned_source_set_digest=planned_digest,
                paths=path_map,
            ),
            "manager_epoch": manager_epoch,
            "repository_head": repository_head,
            "repository_root": str(repository),
        },
    )
    continuation_identity = _write(
        authority_dir / "continuation.json",
        _control_record(
            kind="NONAUTHORIZING_DISPOSABLE_CONTINUATION",
            run_nonce=run_nonce,
            planned_source_set_digest=planned_digest,
            paths=path_map,
        ),
    )
    common_prestate_identity = _write(
        common_prestate_path,
        _control_record(
            kind="INERT_COMMON_PRESTATE",
            run_nonce=run_nonce,
            planned_source_set_digest=planned_digest,
            paths=path_map,
        ),
    )
    arm_binding_identity = _write(
        binding_path,
        _control_record(
            kind="INERT_CONTROL_ARM_BINDING",
            run_nonce=run_nonce,
            planned_source_set_digest=planned_digest,
            paths=path_map,
        ),
    )
    baseline_identity = _write(
        authority_dir / "baseline-admission.json",
        _control_record(
            kind="INERT_BASELINE_ADMISSION",
            run_nonce=run_nonce,
            planned_source_set_digest=planned_digest,
            paths=path_map,
        ),
    )
    manifest_identity = _write(
        authority_dir / "drill-manifest.json",
        _control_record(
            kind="DISPOSABLE_DRILL_MANIFEST",
            run_nonce=run_nonce,
            planned_source_set_digest=planned_digest,
            paths=path_map,
        ),
    )
    suite_identity = _write(
        authority_dir / "suite-selection.json",
        _control_record(
            kind="DISPOSABLE_DRILL_SUITE_SELECTION",
            run_nonce=run_nonce,
            planned_source_set_digest=planned_digest,
            paths=path_map,
        ),
    )

    tools = {role: _identity(planned[source_role]) for role, source_role in TOOL_SOURCE_ROLES.items()}
    tools["libsystemd"] = dict(libsystemd_identity)
    strict_inputs = {role: _identity(identity) for role, identity in sorted(planned.items())}
    payload_path = planned["script.disposable_drill_payload_v1"]["path"]
    output_names = {
        "attempt_result": "result.json",
        "cleanup": "cleanup.json",
        "detached_replay": "detached-replay.json",
        "inner": "inner-lifecycle.json",
        "preterminal": "preterminal-resource.json",
        "reference_acquisition": "unit-reference-acquisition.json",
        "reference_release": "unit-reference-release.json",
        "abort_reference_release": "abort-unit-reference-release.json",
        "release": "release-token.json",
        "resource_verification": "resource-verification.json",
        "terminal": "terminal-envelope.json",
    }
    phases = tuple(item for item in lifecycle.PHASES if item != "preselection")
    unit_suffix = hashlib.sha256(f"{run_nonce}:{planned_digest}".encode("utf-8")).hexdigest()[:12]
    unit_name = f"noncert-cuts-ab16-gatea-drill-{unit_suffix}.service"
    authority_chain = {
        "drill_root_identity": root_identity,
        "planned_source_authority_identity": planned_identity,
        "planned_source_set_digest": planned_digest,
    }
    expected_payload_status = {
        "exit_code": 0,
        "expectation": "SUCCESS",
        "signal": 0,
    }
    pre_run = {
        "arm": "control",
        "arm_binding_identity": arm_binding_identity,
        "arm_launch_authorized": False,
        "arm_selection_write_authorized": True,
        "attempt_dir": str(attempt_dir),
        "authority_chain": authority_chain,
        "baseline_admission_identity": baseline_identity,
        "baseline_incumbent_sha256": common_prestate_identity["sha256"],
        "campaign_id": f"disposable-drill-{unit_suffix}",
        "campaign_root_identity": root_identity,
        "common_prestate_identity": common_prestate_identity,
        "configuration": "region-capacity",
        "continuation_identity": continuation_identity,
        "epoch_observation_paths": {phase: str(attempt_dir / f"manager-epoch-{phase}.json") for phase in phases},
        "epoch_transcript_paths": {phase: str(attempt_dir / f"manager-transcript-{phase}.json") for phase in phases},
        "execution_class": "DISPOSABLE_LIVE_DRILL",
        "expected_payload_status": expected_payload_status,
        "launch": {
            "cwd": str(repository),
            "environment_identity": environment_identity,
            "payload_argv": [
                tools["python3_13"]["path"],
                "-I",
                payload_path,
                "--selection",
                str(attempt_dir / "selection.json"),
                "--output",
                str(attempt_dir / "result.json"),
            ],
            "libsystemd_path": tools["libsystemd"]["path"],
            "python3_13_path": tools["python3_13"]["path"],
            "supervisor_argv": [
                tools["python3_13"]["path"],
                "-I",
                tools["organic_resource_lifecycle"]["path"],
                "supervise",
                "--pre-run",
                str(attempt_dir / "pre-run-authority.json"),
                "--selection",
                str(attempt_dir / "selection.json"),
            ],
            "systemctl_path": tools["systemctl"]["path"],
            "systemd_run_path": tools["systemd_run"]["path"],
        },
        "manager_epoch": manager_epoch,
        "order": "ab",
        "output_paths": {role: str(attempt_dir / name) for role, name in output_names.items()},
        "package": package,
        "pre_run_authority_path": str(attempt_dir / "pre-run-authority.json"),
        "prelaunch_allowlist": [
            "pre-run-authority.json",
            "selection.json",
        ],
        "preflight_results": {
            "epoch_identity_pass": True,
            "head_identity_pass": True,
            "package_replay_pass": True,
            "path_preregistration_pass": True,
            "resource_contract_pass": True,
            "reference_contract_pass": True,
            "reference_capability_pass": True,
            "libsystemd_identity_pass": True,
            "history_freeze_replay_pass": True,
            "slot_order_pass": True,
            "strict_inputs_replay_pass": True,
            "tool_identities_replay_pass": True,
        },
        "preselection_epoch_identity": epoch_identity,
        "preselection_transcript_identity": transcript_identity,
        "reference_capability_identity": capability_identity,
        "reference_capability_transcript_identity": capability_transcript_identity,
        "history_freeze_replay_identity": history_replay_identity,
        "prospective_manifest_identity": manifest_identity,
        "purpose": lifecycle.PRE_RUN_PURPOSE,
        "repository_git_tool_identity": _identity(planned["system.git"]),
        "repository_head": repository_head,
        "repository_root": str(repository),
        "resource_contract": lifecycle.DRILL_RESOURCE_CONTRACT,
        "reference_contract": lifecycle.REFERENCE_CONTRACT,
        "run_nonce": run_nonce,
        "runner_selection_path": str(attempt_dir / "selection.json"),
        "schema_version": lifecycle.PRE_RUN_AUTHORITY_SCHEMA,
        "seed": 0,
        "slot": DRILL_SLOT,
        "solver_run_authorized": False,
        "status": "PASS",
        "strict_input_identities": strict_inputs,
        "suite_selection_identity": suite_identity,
        "tool_identities": tools,
        "unit_name": unit_name,
        "verdict": "AB16_ORGANIC_PRE_RUN_AUTHORITY_PASS",
        "workers": 1,
    }
    lifecycle.validate_pre_run_authority(pre_run)
    verifier.validate_pre_run_authority(pre_run)
    pre_run_identity = _write(
        attempt_dir / "pre-run-authority.json",
        pre_run,
    )
    selection = {
        "arm": "control",
        "arm_binding_identity": arm_binding_identity,
        "attempt_dir": str(attempt_dir),
        "authority_chain": authority_chain,
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": False,
            "production_certified_authorized": False,
            "solver_run_authorized": False,
        },
        "baseline_admission_identity": baseline_identity,
        "baseline_incumbent_sha256": common_prestate_identity["sha256"],
        "campaign_id": pre_run["campaign_id"],
        "common_prestate_identity": common_prestate_identity,
        "configuration": "region-capacity",
        "enabled_families": [],
        "execution_class": "DISPOSABLE_LIVE_DRILL",
        "expected_payload_status": expected_payload_status,
        "fresh_process_required": True,
        "manifest_identity": manifest_identity,
        "order": "ab",
        "pre_run_authority_identity": pre_run_identity,
        "purpose": lifecycle.DRILL_SELECTION_PURPOSE,
        "repository_git_tool_identity": pre_run["repository_git_tool_identity"],
        "repository_head": repository_head,
        "repository_root": str(repository),
        "run_nonce": run_nonce,
        "schema_version": lifecycle.DRILL_SELECTION_SCHEMA,
        "seed": 0,
        "selection_nonce": f"{run_nonce}-selection",
        "slot": DRILL_SLOT,
        "unit_name": unit_name,
        "workers": 1,
    }
    lifecycle.validate_runner_selection(
        selection,
        pre_run_authority=pre_run,
        pre_run_authority_identity=pre_run_identity,
    )
    selection_identity = _write(
        attempt_dir / "selection.json",
        selection,
    )
    _reobserve_sources(
        strict_input_paths=strict_input_paths,
        system_tool_paths=system_tool_paths,
        expected=planned,
        expected_digest=planned_digest,
    )
    if set(item.name for item in attempt_dir.iterdir()) != {
        "pre-run-authority.json",
        "selection.json",
    }:
        raise DrillAuthorityError("prelaunch attempt allowlist was not preserved")
    result = {
        "authorizations": {
            "arm_launch_authorized": False,
            "formal_campaign_creation_authorized": False,
            "solver_run_authorized": False,
        },
        "disposable_drill_ready": True,
        "formal_campaign_created": False,
        "planned_source_set_digest": planned_digest,
        "pre_run_authority_identity": pre_run_identity,
        "purpose": RESULT_PURPOSE,
        "run_nonce": run_nonce,
        "schema_version": RESULT_SCHEMA,
        "selection_identity": selection_identity,
        "status": "PASS",
    }
    result_identity = _write(authority_dir / "authority-ready.json", result)
    return {
        "authority_result": result,
        "authority_result_identity": result_identity,
        "formal_campaign_created": False,
        "pre_run_authority_identity": pre_run_identity,
        "selection_identity": selection_identity,
        "status": "PASS",
    }


def _strict_path_map(path: Path, label: str) -> dict[str, Path]:
    snapshot = lifecycle.snapshot_regular(_absolute(path))
    value = lifecycle.strict_loads(snapshot.raw, label)
    if type(value) is not dict or any(type(role) is not str or type(item) is not str for role, item in value.items()):
        raise DrillAuthorityError(f"{label} must map role strings to path strings")
    return {role: Path(item) for role, item in value.items()}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--repository-head", required=True)
    parser.add_argument("--run-nonce", required=True)
    parser.add_argument("--planned-source-set-digest", required=True)
    parser.add_argument("--strict-inputs-json", required=True, type=Path)
    parser.add_argument("--system-tools-json", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = build_disposable_drill_authority(
            output_dir=arguments.output_dir,
            repository_root=arguments.repository_root,
            repository_head=arguments.repository_head,
            run_nonce=arguments.run_nonce,
            expected_planned_source_set_digest=arguments.planned_source_set_digest,
            strict_input_paths=_strict_path_map(
                arguments.strict_inputs_json,
                "strict input path map",
            ),
            system_tool_paths=_strict_path_map(
                arguments.system_tools_json,
                "system tool path map",
            ),
        )
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
