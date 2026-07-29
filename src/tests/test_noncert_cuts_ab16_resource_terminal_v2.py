from __future__ import annotations

import base64
from collections.abc import Iterator
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Mapping, Sequence

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/noncert_cuts_ab16_20260724"
LIFECYCLE_PATH = TOOLS / "organic_resource_lifecycle_v2.py"
VERIFIER_PATH = TOOLS / "organic_resource_verifier_v2.py"
ORCHESTRATOR_PATH = TOOLS / "organic_unit_orchestrator_v2.py"
GATE1_TOOLS = ROOT / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"
MANAGER_AUTHORITY_PATH = GATE1_TOOLS / "campaign_authority_v4.py"
MANAGER_ATTESTOR_PATH = GATE1_TOOLS / "manager_attestor_v4.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


LIFECYCLE = _load("ab16_resource_lifecycle_v2_test", LIFECYCLE_PATH)
VERIFIER = _load("ab16_resource_verifier_v2_test", VERIFIER_PATH)
ORCHESTRATOR = _load("ab16_unit_orchestrator_v2_test", ORCHESTRATOR_PATH)
MANAGER_AUTHORITY = _load("ab16_manager_authority_test", MANAGER_AUTHORITY_PATH)


def _identity(path: Path) -> dict[str, object]:
    return dict(LIFECYCLE.snapshot_regular(path).identity)


def _write(path: Path, value: object) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    return LIFECYCLE.write_json_exclusive(path, value)


def _full_identity(path: Path) -> dict[str, object]:
    return dict(MANAGER_AUTHORITY.full_identity(MANAGER_AUTHORITY.snapshot_regular(path)))


def _manager_material(
    authority_dir: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    tool_dir = authority_dir / "manager-tools"
    tool_dir.mkdir()
    tools: dict[str, Path] = {}
    for role in ("systemd", "busctl", "sudo", "python"):
        path = tool_dir / role
        path.write_bytes(f"fixture {role}\n".encode())
        tools[role] = path
    attestor_identity = _full_identity(MANAGER_ATTESTOR_PATH)
    audit = MANAGER_AUTHORITY.audit_attestor_source(MANAGER_ATTESTOR_PATH.read_bytes())
    epoch: dict[str, object] = {
        "attestation_toolchain": {
            "attestor": attestor_identity,
            "python": _full_identity(tools["python"]),
            "sudo": _full_identity(tools["sudo"]),
        },
        "attestor_ast_audit": audit,
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "capture_protocol": ("double-unprivileged-join-plus-read-only-sudo-attestation-v4"),
        "dbus_unique_owner": ":1.42",
        "manager_executable": _full_identity(tools["systemd"]),
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 101,
        "manager_version": "systemd 261.1",
        "observation_toolchain": {"busctl": _full_identity(tools["busctl"])},
        "schema": MANAGER_AUTHORITY.MANAGER_EPOCH_SCHEMA,
    }
    state = {
        key: epoch[key]
        for key in (
            "boot_id",
            "dbus_unique_owner",
            "manager_features",
            "manager_pid",
            "manager_pid_starttime",
            "manager_version",
        )
    }
    attestation = {
        "manager_executable": epoch["manager_executable"],
        "request": {
            "boot_id": epoch["boot_id"],
            "dbus_unique_owner": epoch["dbus_unique_owner"],
            "manager_pid": epoch["manager_pid"],
            "manager_pid_starttime": epoch["manager_pid_starttime"],
        },
        "schema": MANAGER_AUTHORITY.ATTESTOR_SCHEMA,
        "status": "PASS",
    }
    attestation_tools = epoch["attestation_toolchain"]
    assert isinstance(attestation_tools, dict)
    invocation = {
        "argv": [
            attestation_tools["sudo"]["path"],
            "-n",
            "--",
            attestation_tools["python"]["path"],
            "-I",
            "-c",
            MANAGER_AUTHORITY._LOADER,  # noqa: SLF001
            "--pid",
            str(epoch["manager_pid"]),
            "--expected-starttime",
            str(epoch["manager_pid_starttime"]),
            "--expected-boot-id",
            epoch["boot_id"],
            "--dbus-owner",
            epoch["dbus_unique_owner"],
        ],
        "exit_code": 0,
        "stdin_sha256": attestor_identity["sha256"],
        "stdin_size_bytes": attestor_identity["size_bytes"],
        "stdout_base64": base64.b64encode(MANAGER_AUTHORITY.canonical_json(attestation)).decode("ascii"),
    }
    rounds = []
    for index in (1, 2):
        rounds.append(
            {
                "attestation_toolchain": copy.deepcopy(epoch["attestation_toolchain"]),
                "attestor_ast_audit": copy.deepcopy(epoch["attestor_ast_audit"]),
                "attestor_invocation": copy.deepcopy(invocation),
                "observation_toolchain": copy.deepcopy(epoch["observation_toolchain"]),
                "observation_finished_monotonic_ns": index * 20,
                "observation_started_monotonic_ns": index * 20 - 10,
                "privileged_attestation": copy.deepcopy(attestation),
                "round_index": index,
                "unprivileged_after": copy.deepcopy(state),
                "unprivileged_before": copy.deepcopy(state),
            }
        )
    transcript = {
        "capture_protocol": ("two-round-before-read-only-attestor-after-transcript-v4"),
        "rounds": rounds,
        "schema": MANAGER_AUTHORITY.MANAGER_EPOCH_TRANSCRIPT_SCHEMA,
    }
    MANAGER_AUTHORITY.validate_manager_epoch_capture_transcript(
        transcript,
        expected_epoch=epoch,
    )
    return epoch, transcript


def _tool_identity(path: Path) -> dict[str, object]:
    return dict(LIFECYCLE.snapshot_regular(path).identity)


def _detached(identity: Mapping[str, object]) -> dict[str, object]:
    return {key: identity[key] for key in ("path", "sha256", "size_bytes")}


def _write_campaign_json(path: Path, value: object) -> dict[str, object]:
    raw = (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    return LIFECYCLE.write_exclusive(path, raw)


def _campaign_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


_VERIFIER_HISTORY_CONTRACT_NAMES = (
    "HISTORY_FREEZE_HEAD",
    "HISTORY_FREEZE_MANIFEST_MODE",
    "HISTORY_FREEZE_MANIFEST_PATH",
    "HISTORY_FREEZE_MANIFEST_SHA256",
    "HISTORY_FREEZE_MANIFEST_SIZE",
    "HISTORY_SOURCE_COMMIT",
    "HISTORY_SOURCE_TREE",
    "HISTORY_SOURCE_GLOB",
    "HISTORY_ARTIFACT_COUNT",
    "HISTORY_SOURCE_COUNT",
    "HISTORY_REPOSITORY_ROOT",
    "HISTORY_FROZEN_ROOTS",
)


@pytest.fixture(autouse=True)
def _restore_verifier_history_contract() -> Iterator[None]:
    original = {
        name: getattr(VERIFIER, name)
        for name in _VERIFIER_HISTORY_CONTRACT_NAMES
    }
    original_loader = getattr(ORCHESTRATOR, "_load_pinned_module")
    try:
        yield
    finally:
        for name, value in original.items():
            setattr(VERIFIER, name, value)
        setattr(ORCHESTRATOR, "_load_pinned_module", original_loader)


def _run_fixture_git(
    git_path: Path,
    repository_root: Path,
    *arguments: str,
) -> bytes:
    completed = subprocess.run(
        [str(git_path), "-C", str(repository_root), *arguments],
        check=False,
        close_fds=True,
        env={
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+0000",
            "GIT_AUTHOR_EMAIL": "ab16-fixture@example.invalid",
            "GIT_AUTHOR_NAME": "AB16 Fixture",
            "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+0000",
            "GIT_COMMITTER_EMAIL": "ab16-fixture@example.invalid",
            "GIT_COMMITTER_NAME": "AB16 Fixture",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": str(repository_root.parent / "git-home"),
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
            "TZ": "UTC",
        },
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert completed.returncode == 0, (
        arguments,
        completed.stderr.decode("utf-8", "replace"),
    )
    return completed.stdout


def _build_history_archive_fixture(tmp_path: Path) -> dict[str, Any]:
    raw_git_path = shutil.which("git")
    assert raw_git_path is not None
    git_path = Path(raw_git_path).resolve(strict=True)
    repository_root = tmp_path / "history-repository"
    repository_root.mkdir()
    (tmp_path / "git-home").mkdir()
    _run_fixture_git(git_path, repository_root, "init", "--quiet")

    readme_path = repository_root / "README.fixture"
    readme_path.write_bytes(b"history base\n")
    readme_path.chmod(0o644)
    _run_fixture_git(git_path, repository_root, "add", "--", "README.fixture")
    _run_fixture_git(
        git_path,
        repository_root,
        "-c",
        "commit.gpgSign=false",
        "commit",
        "--quiet",
        "--no-gpg-sign",
        "-m",
        "history base",
    )
    history_head = (
        _run_fixture_git(git_path, repository_root, "rev-parse", "--verify", "HEAD^{commit}")
        .decode("ascii")
        .strip()
    )

    source_relative = "docs/research/noncert_cuts_ab16_20260724/fixture_history_v1.py"
    source_path = repository_root / source_relative
    source_path.parent.mkdir(parents=True)
    archived_source = b"ARCHIVED_FIXTURE = True\n"
    source_path.write_bytes(archived_source)
    source_path.chmod(0o644)
    _run_fixture_git(git_path, repository_root, "add", "--", source_relative)
    _run_fixture_git(
        git_path,
        repository_root,
        "-c",
        "commit.gpgSign=false",
        "commit",
        "--quiet",
        "--no-gpg-sign",
        "-m",
        "archive history source",
    )
    source_commit = (
        _run_fixture_git(git_path, repository_root, "rev-parse", "--verify", "HEAD^{commit}")
        .decode("ascii")
        .strip()
    )
    source_tree = (
        _run_fixture_git(
            git_path,
            repository_root,
            "rev-parse",
            "--verify",
            f"{source_commit}^{{tree}}",
        )
        .decode("ascii")
        .strip()
    )
    source_blob = (
        _run_fixture_git(
            git_path,
            repository_root,
            "rev-parse",
            "--verify",
            f"{source_commit}:{source_relative}",
        )
        .decode("ascii")
        .strip()
    )

    source_path.write_bytes(b"LIVE_FIXTURE = True\n")
    source_path.chmod(0o644)
    _run_fixture_git(git_path, repository_root, "add", "--", source_relative)
    _run_fixture_git(
        git_path,
        repository_root,
        "-c",
        "commit.gpgSign=false",
        "commit",
        "--quiet",
        "--no-gpg-sign",
        "-m",
        "advance live source",
    )
    current_head = (
        _run_fixture_git(git_path, repository_root, "rev-parse", "--verify", "HEAD^{commit}")
        .decode("ascii")
        .strip()
    )

    frozen_root = ".artifacts/noncert_cuts_ab16_fixture/history-frozen"
    artifact_relative = f"{frozen_root}/terminal.json"
    artifact_path = repository_root / artifact_relative
    artifact_path.parent.mkdir(parents=True)
    artifact_identity = LIFECYCLE.write_exclusive(
        artifact_path,
        b'{"fixture":"immutable failed Gate A artifact"}\n',
    )
    source_member = {
        "mode": 0o644,
        "path": source_relative,
        "sha256": hashlib.sha256(archived_source).hexdigest(),
        "size_bytes": len(archived_source),
    }
    artifact_member = {
        "mode": artifact_identity["mode"],
        "path": artifact_relative,
        "sha256": artifact_identity["sha256"],
        "size_bytes": artifact_identity["size_bytes"],
    }
    history_manifest = {
        "created_at_utc": "2026-07-24T00:00:00Z",
        "file_count": 2,
        "files": sorted(
            [artifact_member, source_member],
            key=lambda member: str(member["path"]).encode("utf-8"),
        ),
        "frozen_roots": [frozen_root],
        "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_FREEZE",
        "repository_head": history_head,
        "repository_root": str(repository_root),
        "schema_version": "noncert-cuts-ab16-terminal-reference-history-freeze-v1",
        "v1_source_glob": "docs/research/noncert_cuts_ab16_20260724/*_v1.py",
    }
    manifest_path = (
        repository_root
        / ".artifacts/noncert_cuts_ab16_fixture/history-freeze/manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_identity = LIFECYCLE.write_exclusive(
        manifest_path,
        (
            json.dumps(
                history_manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8"),
    )
    manifest_path.chmod(0o400)
    manifest_identity = _identity(manifest_path)

    source_records = [
        {
            "git_blob_oid": source_blob,
            "git_mode": "100644",
            "mode": 0o644,
            "path": source_relative,
            "sha256": source_member["sha256"],
            "size_bytes": source_member["size_bytes"],
        }
    ]
    source_member_digest = hashlib.sha256(
        VERIFIER.canonical_json_bytes(source_records) + b"\n"
    ).hexdigest()
    contract = {
        "HISTORY_FREEZE_HEAD": history_head,
        "HISTORY_FREEZE_MANIFEST_MODE": manifest_identity["mode"],
        "HISTORY_FREEZE_MANIFEST_PATH": manifest_identity["path"],
        "HISTORY_FREEZE_MANIFEST_SHA256": manifest_identity["sha256"],
        "HISTORY_FREEZE_MANIFEST_SIZE": manifest_identity["size_bytes"],
        "HISTORY_SOURCE_COMMIT": source_commit,
        "HISTORY_SOURCE_TREE": source_tree,
        "HISTORY_SOURCE_GLOB": history_manifest["v1_source_glob"],
        "HISTORY_ARTIFACT_COUNT": 1,
        "HISTORY_SOURCE_COUNT": 1,
        "HISTORY_REPOSITORY_ROOT": repository_root,
        "HISTORY_FROZEN_ROOTS": (frozen_root,),
    }
    for name, value in contract.items():
        setattr(VERIFIER, name, value)
    pinned_loader = getattr(ORCHESTRATOR, "_load_pinned_module")

    def load_fixture_pinned_module(
        identity: Mapping[str, Any],
        *,
        module_name: str,
    ) -> ModuleType:
        module = pinned_loader(identity, module_name=module_name)
        if Path(str(identity["path"])) == VERIFIER_PATH:
            for name, value in contract.items():
                setattr(module, name, value)
        return module

    setattr(ORCHESTRATOR, "_load_pinned_module", load_fixture_pinned_module)
    return {
        "current_head": current_head,
        "git_identity": _tool_identity(git_path),
        "manifest_identity": manifest_identity,
        "replay": {
            "artifact_file_count": 1,
            "authorizations": {
                "formal_campaign_creation_authorized": False,
                "organic_arm_launch_authorized": False,
            },
            "file_count": 2,
            "manifest_identity": manifest_identity,
            "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_REPLAY",
            "schema_version": "noncert-cuts-ab16-terminal-reference-history-replay-v2",
            "source_file_count": 1,
            "source_materialization": {
                "commit": source_commit,
                "file_count": 1,
                "manifest_head_parent": history_head,
                "member_digest": source_member_digest,
                "tree": source_tree,
            },
            "status": "PASS",
            "verdict": "IMMUTABLE_FAILED_GATE_A_HISTORY_REPLAY_PASS",
        },
        "repository_root": repository_root,
    }


class FakeAdapter:
    def __init__(
        self,
        *,
        attempt_dir: Path,
        slot: str,
        payload_exit_code: int = 0,
        epoch_drift_phase: str | None = None,
        transcript_drift_phase: str | None = None,
        terminal_invocation_drift: bool = False,
        terminal_capture_error: bool = False,
        oom_kill: int = 0,
        cleanup_residual: bool = False,
        abort_cleanup_residual: bool = False,
        memory_max_adjustment: int = 0,
        collect_mode: str = "inactive-or-failed",
    ) -> None:
        self.attempt_dir = attempt_dir
        self.slot = slot
        self.payload_exit_code = payload_exit_code
        self.epoch_drift_phase = epoch_drift_phase
        self.transcript_drift_phase = transcript_drift_phase
        self.terminal_invocation_drift = terminal_invocation_drift
        self.terminal_capture_error = terminal_capture_error
        self.oom_kill = oom_kill
        self.cleanup_residual = cleanup_residual
        self.abort_cleanup_residual = abort_cleanup_residual
        self.memory_max_adjustment = memory_max_adjustment
        self.collect_mode = collect_mode
        self.clock = 100
        self.invocation = "0123456789abcdef0123456789abcdef"
        self.keeper_pid = 4100
        self.payload_pid = 4101
        self.abort_count = 0
        self.reference: FakeReference | None = None
        pre_run = VERIFIER.snapshot_json(attempt_dir / "pre-run-authority.json").value
        self.resource_contract = copy.deepcopy(pre_run["resource_contract"])
        self.manager_epoch = copy.deepcopy(pre_run["manager_epoch"])
        self.manager_transcript = copy.deepcopy(
            VERIFIER.snapshot_json(pre_run["preselection_transcript_identity"]["path"]).value
        )

    def monotonic_ns(self) -> int:
        self.clock += 100
        return self.clock

    def observe_manager_epoch(self, phase: str) -> Any:
        epoch = copy.deepcopy(self.manager_epoch)
        if phase == self.epoch_drift_phase:
            epoch["boot_id"] = "boot-drift"
        transcript = copy.deepcopy(self.manager_transcript)
        if phase == self.transcript_drift_phase:
            transcript["rounds"][0]["round_index"] = 99
        return ORCHESTRATOR.EpochCapture(
            manager_epoch=epoch,
            transcript=transcript,
        )

    def open_unit_reference(self) -> Any:
        assert self.reference is None
        self.reference = FakeReference(
            manager_owner=self.manager_epoch["dbus_unique_owner"],
        )
        return self.reference

    def capture_reference_state(
        self,
        *,
        unit_name: str,
        invocation_id: str,
    ) -> Any:
        assert unit_name.endswith(".service")
        assert invocation_id == self.invocation
        return ORCHESTRATOR.TerminalEvidence(
            captured_at_monotonic_ns=self.monotonic_ns(),
            systemd_raw={
                "ActiveState": "active",
                "CollectMode": self.collect_mode,
                "ControlGroup": "/user.slice/ab16.scope",
                "InvocationID": self.invocation,
                "LoadState": "loaded",
                "SubState": "running",
            },
        )

    def launch_and_wait_for_keeper(
        self,
        *,
        unit_name: str,
        systemd_run_argv: Sequence[str],
        payload_argv: Sequence[str],
    ) -> Any:
        assert unit_name.endswith(".service")
        assert f"--property=MemoryHigh={self.resource_contract['memory_high_bytes']}" in systemd_run_argv
        assert f"--property=MemoryMax={self.resource_contract['memory_max_bytes']}" in systemd_run_argv
        assert (f"--property=MemorySwapMax={self.resource_contract['memory_swap_max_bytes']}") in systemd_run_argv
        assert f"--property=CollectMode={self.resource_contract['collect_mode']}" in systemd_run_argv
        assert f"--property=RuntimeMaxSec={self.resource_contract['runtime_max_seconds']}" in systemd_run_argv
        assert payload_argv
        payload_result_identity = _write(
            self.attempt_dir / "result.json",
            {
                "schema_version": "noncert-cuts-ab16-organic-arm-result-v1",
                "slot": self.slot,
                "status": "UNKNOWN",
            },
        )
        launch = ORCHESTRATOR.LaunchEvidence(
            invocation_id=self.invocation,
            supervisor_pid=self.keeper_pid,
            supervisor_starttime=77,
            payload_pid=self.payload_pid,
            payload_starttime=78,
            payload_seal_monotonic_ns=300,
            payload_exit_monotonic_ns=400,
            payload_exit_code=self.payload_exit_code,
            payload_signal=0,
            payload_reaped=True,
            keeper_ready_monotonic_ns=500,
        )
        pre_run_snapshot = LIFECYCLE.snapshot_regular(self.attempt_dir / "pre-run-authority.json")
        selection_snapshot = LIFECYCLE.snapshot_regular(self.attempt_dir / "selection.json")
        pre_run = LIFECYCLE.strict_loads(pre_run_snapshot.raw, "fixture pre-run")
        selection = LIFECYCLE.strict_loads(
            selection_snapshot.raw,
            "fixture selection",
        )
        launch_epoch_snapshot = LIFECYCLE.snapshot_regular(self.attempt_dir / "manager-epoch-launch.json")
        launch_epoch = LIFECYCLE.strict_loads(
            launch_epoch_snapshot.raw,
            "fixture launch epoch",
        )
        inner = LIFECYCLE.build_inner_record(
            pre_run,
            pre_run_snapshot.identity,
            selection,
            selection_snapshot.identity,
            invocation_id=launch.invocation_id,
            launch_observation=launch_epoch,
            supervisor_pid=launch.supervisor_pid,
            supervisor_starttime=launch.supervisor_starttime,
            payload_pid=launch.payload_pid,
            payload_starttime=launch.payload_starttime,
            payload_seal_monotonic_ns=launch.payload_seal_monotonic_ns,
            payload_exit_monotonic_ns=launch.payload_exit_monotonic_ns,
            payload_exit_code=launch.payload_exit_code,
            payload_signal=launch.payload_signal,
            payload_reaped=launch.payload_reaped,
            payload_result_identity=payload_result_identity,
            keeper_ready_monotonic_ns=launch.keeper_ready_monotonic_ns,
        )
        _write(self.attempt_dir / "inner-lifecycle.json", inner)
        return launch

    def capture_preterminal(
        self,
        *,
        unit_name: str,
        launch: Any,
    ) -> Any:
        assert launch.payload_exit_monotonic_ns == 400
        self.clock = 700
        events = f"low 0\nhigh 0\nmax 0\noom 0\noom_kill {self.oom_kill}\noom_group_kill 0\n"
        return ORCHESTRATOR.PreterminalEvidence(
            captured_at_monotonic_ns=700,
            systemd_raw={
                "ActiveState": "active",
                "CollectMode": self.collect_mode,
                "ControlGroup": "/user.slice/ab16.scope",
                "InvocationID": self.invocation,
                "KillMode": "control-group",
                "MainPID": str(self.keeper_pid),
                "MemoryHigh": str(self.resource_contract["memory_high_bytes"]),
                "MemoryMax": str(self.resource_contract["memory_max_bytes"] + self.memory_max_adjustment),
                "MemorySwapMax": str(self.resource_contract["memory_swap_max_bytes"]),
                "OOMPolicy": "continue",
                "RuntimeMaxUSec": str(self.resource_contract["runtime_max_seconds"] * 1_000_000),
                "SendSIGKILL": "yes",
                "SubState": "running",
            },
            cgroup_raw={
                "cgroup.events": "populated 1\nfrozen 0\n",
                "cgroup.procs": f"{self.keeper_pid}\n",
                "memory.current": "100",
                "memory.events": events,
                "memory.high": str(self.resource_contract["memory_high_bytes"]),
                "memory.max": str(self.resource_contract["memory_max_bytes"]),
                "memory.peak": "200",
                "memory.swap.current": "0",
                "memory.swap.max": str(self.resource_contract["memory_swap_max_bytes"]),
            },
            payload_current_starttime=None,
            keeper_current_starttime=77,
        )

    def release_keeper(
        self,
        *,
        unit_name: str,
        release_path: Path,
        launch: Any,
    ) -> None:
        assert release_path.is_file()
        assert launch.payload_reaped is True

    def capture_terminal(
        self,
        *,
        unit_name: str,
        invocation_id: str,
    ) -> Any:
        assert invocation_id == self.invocation
        if self.terminal_capture_error:
            raise RuntimeError("fixture terminal capture failed")
        captured = self.monotonic_ns()
        observed = "fedcba9876543210fedcba9876543210" if self.terminal_invocation_drift else self.invocation
        failed = self.payload_exit_code != 0
        return ORCHESTRATOR.TerminalEvidence(
            captured_at_monotonic_ns=captured,
            systemd_raw={
                "ActiveState": "failed" if failed else "inactive",
                "CollectMode": self.collect_mode,
                "ControlGroup": "",
                "ExecMainCode": "exited",
                "ExecMainStatus": str(self.payload_exit_code),
                "InvocationID": observed,
                "LoadState": "loaded",
                "Result": "exit-code" if failed else "success",
                "SubState": "failed" if failed else "dead",
            },
        )

    def wait_reference_stability(self, hold_ns: int) -> None:
        assert hold_ns == LIFECYCLE.REFERENCE_STABILITY_HOLD_NS
        self.clock += hold_ns

    def capture_cleanup(
        self,
        *,
        unit_name: str,
        launch: Any,
        control_group: str,
    ) -> Any:
        assert control_group == "/user.slice/ab16.scope"
        return ORCHESTRATOR.CleanupEvidence(
            captured_at_monotonic_ns=self.monotonic_ns(),
            payload_current_starttime=None,
            keeper_current_starttime=77 if self.cleanup_residual else None,
            cgroup_path=control_group,
            cgroup_path_exists=self.cleanup_residual,
            unit_load_state="loaded" if self.cleanup_residual else "not-found",
            matching_unit_names=[unit_name] if self.cleanup_residual else [],
        )

    def abort_and_capture_cleanup(
        self,
        *,
        unit_name: str,
        launch: Any,
        control_group: str | None,
    ) -> Any:
        self.abort_count += 1
        residual = self.abort_cleanup_residual
        return ORCHESTRATOR.CleanupEvidence(
            captured_at_monotonic_ns=self.monotonic_ns(),
            payload_current_starttime=78 if residual else None,
            keeper_current_starttime=77 if residual else None,
            cgroup_path=control_group or "/user.slice/ab16.scope",
            cgroup_path_exists=residual,
            unit_load_state="loaded" if residual else "not-found",
            matching_unit_names=[unit_name] if residual else [],
        )


class FakeReference:
    def __init__(self, *, manager_owner: str) -> None:
        self.manager_owner = manager_owner
        self._acquired_unit: str | None = None
        self.client_unique_name = ":1.900"
        self.abort_count = 0

    @property
    def acquired_unit(self) -> str | None:
        return self._acquired_unit

    def _call(self, *, unit_name: str) -> dict[str, str]:
        return {
            "client_unique_name": self.client_unique_name,
            "manager_owner_after": self.manager_owner,
            "manager_owner_before": self.manager_owner,
            "unit_name": unit_name,
        }

    def acquire(
        self,
        *,
        unit_name: str,
        expected_manager_owner: str,
    ) -> dict[str, str]:
        assert expected_manager_owner == self.manager_owner
        assert self._acquired_unit is None
        self._acquired_unit = unit_name
        return self._call(unit_name=unit_name)

    def verify(self, *, expected_manager_owner: str) -> dict[str, str]:
        assert expected_manager_owner == self.manager_owner
        assert self._acquired_unit is not None
        return self._call(unit_name=self._acquired_unit)

    def release(
        self,
        *,
        unit_name: str,
        expected_manager_owner: str,
    ) -> dict[str, str]:
        assert expected_manager_owner == self.manager_owner
        assert self._acquired_unit == unit_name
        self._acquired_unit = None
        return self._call(unit_name=unit_name)

    def close(self) -> None:
        assert self._acquired_unit is None

    def abort_close(self) -> bool:
        self.abort_count += 1
        was_held = self._acquired_unit is not None
        self._acquired_unit = None
        return was_held


def _fixture(
    tmp_path: Path,
    *,
    postseal_failure_exit_code: int = 0,
    execution_class: str | None = None,
) -> tuple[Path, Path, Path]:
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    authority_dir = tmp_path / "authority"
    authority_dir.mkdir()
    identities: dict[str, dict[str, object]] = {}
    for name in (
        "root",
        "continuation",
        "manifest",
        "suite-selection",
        "baseline",
        "prestate",
        "binding",
        "strict",
        "systemctl",
        "systemd-run",
    ):
        path = authority_dir / f"{name}.json"
        identities[name] = _write(path, {"name": name})
    history_archive = _build_history_archive_fixture(tmp_path)
    identities["git"] = dict(history_archive["git_identity"])
    history_repository_head = str(history_archive["current_head"])
    history_repository_root = Path(str(history_archive["repository_root"]))
    identities["environment"] = _write(
        authority_dir / "environment.json",
        {
            "clear_ambient": True,
            "schema_version": "noncert-cuts-ab16-launch-environment-v2",
            "variables": {
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
                "HOME": "/home/fixture",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PATH": "/usr/bin:/bin",
                "PYTHONHASHSEED": "0",
                "TZ": "UTC",
                "XDG_RUNTIME_DIR": "/run/user/1000",
            },
        },
    )
    manager_epoch, manager_transcript = _manager_material(authority_dir)
    workload_python_path = authority_dir / "workload-tools/python3.13"
    workload_python_path.parent.mkdir()
    workload_python_path.write_bytes(b"fixture workload python3.13\n")
    preselection_transcript_identity = _write(
        authority_dir / "preselection-transcript.json",
        manager_transcript,
    )
    preselection = LIFECYCLE.build_epoch_observation(
        phase="preselection",
        slot="region-capacity-ab-control",
        observed_epoch=manager_epoch,
        observed_at_monotonic_ns=100,
        capture_transcript_identity=preselection_transcript_identity,
    )
    identities["preselection"] = _write(
        authority_dir / "preselection.json",
        preselection,
    )
    capability_transcript = {
        "argv": ["busctl", "--user", "introspect"],
        "busctl_identity": _tool_identity(Path(manager_epoch["observation_toolchain"]["busctl"]["path"])),
        "exit_code": 0,
        "manager_epoch_digest": LIFECYCLE.epoch_digest(manager_epoch),
        "purpose": "AB16_GATE_A_REFERENCE_CAPABILITY_RAW_TRANSCRIPT",
        "schema_version": "noncert-cuts-ab16-reference-capability-transcript-v1",
        "stderr": "",
        "stdout": (".RefUnit method s - -\n.UnrefUnit method s - -\n"),
    }
    capability_transcript_identity = _write(
        authority_dir / "reference-capability-transcript.json",
        capability_transcript,
    )
    capability_identity = _write(
        authority_dir / "reference-capability.json",
        {
            "manager_epoch_digest": LIFECYCLE.epoch_digest(manager_epoch),
            "methods": {
                "RefUnit": {
                    "in_signature": "s",
                    "interface": "org.freedesktop.systemd1.Manager",
                    "out_signature": "-",
                },
                "UnrefUnit": {
                    "in_signature": "s",
                    "interface": "org.freedesktop.systemd1.Manager",
                    "out_signature": "-",
                },
            },
            "purpose": "AB16_GATE_A_REFERENCE_CAPABILITY_REPLAY",
            "schema_version": "noncert-cuts-ab16-reference-capability-v1",
            "status": "PASS",
            "transcript_identity": capability_transcript_identity,
            "verdict": "REFUNIT_UNREFUNIT_EXACT_SURFACE_PASS",
        },
    )
    history_snapshot_root = authority_dir / "history-source-snapshot-a001/repository"
    history_snapshot_root.mkdir(parents=True)
    history_snapshot_manifest_identity = _write(
        authority_dir / "history-snapshot-manifest-identity.json",
        {"schema_version": "fixture-history-snapshot-manifest-v1"},
    )
    history_snapshot_receipt_identity = _write(
        authority_dir / "history-snapshot-materialization-identity.json",
        {"schema_version": "fixture-history-snapshot-materialization-v1"},
    )
    history_manifest_identity = dict(history_archive["manifest_identity"])
    history_freeze_replay_identity = _write(
        authority_dir / "history-freeze-replay.json",
        history_archive["replay"],
    )
    if execution_class is None:
        execution_class = "FORMAL_AB16" if postseal_failure_exit_code == 0 else "DISPOSABLE_LIVE_DRILL"
    formal = execution_class == "FORMAL_AB16"
    history_manifest_role = "history_freeze_manifest" if formal else "input.history_freeze_manifest"
    strict_input_identities = {
        history_manifest_role: history_manifest_identity,
        "strict": identities["strict"],
    }
    package_dir = authority_dir / "package"
    (package_dir / "payload").mkdir(parents=True)
    libsystemd_identity = LIFECYCLE.write_exclusive(
        package_dir / "payload/libsystemd.so",
        b"fixture pinned libsystemd bytes\n",
    )
    formal_literal = "fixture-selected-byte-launch-v1"
    formal_authority_identity: dict[str, object] | None = None
    formal_loader_identity: dict[str, object] | None = None
    snapshot_manifest_identity: dict[str, object] | None = None
    snapshot_receipt_identity: dict[str, object] | None = None
    snapshot_member_identity: dict[str, object] | None = None
    snapshot_root: Path | None = None
    runner_relative = "docs/research/noncert_cuts_ab16_20260724/organic_arm_runner_v1.py"
    if formal:
        formal_authority_identity = LIFECYCLE.write_exclusive(
            package_dir / "payload/tool.ab16_authority_v2.py",
            b"# fixture package-pinned authority\n",
        )
        formal_loader_identity = LIFECYCLE.write_exclusive(
            package_dir / "payload/tool.ab16_formal_loader_v1.py",
            b"# fixture selected-byte loader\n",
        )
        snapshot_root = authority_dir / "source-snapshot-a001/repository"
        snapshot_member_path = snapshot_root / runner_relative
        snapshot_member_path.parent.mkdir(parents=True)
        snapshot_member_identity = LIFECYCLE.write_exclusive(
            snapshot_member_path,
            (TOOLS / "organic_arm_runner_v1.py").read_bytes(),
        )
        member = {
            "git_blob_oid": "1" * 40,
            "git_mode": "100644",
            "materialized_mode": snapshot_member_identity["mode"],
            "path": runner_relative,
            "raw_sha256": snapshot_member_identity["sha256"],
            "size_bytes": snapshot_member_identity["size_bytes"],
            "source_kind": "git_blob",
        }
        snapshot_manifest_identity = _write_campaign_json(
            package_dir / "payload/input.ab16_repository_snapshot.json",
            {
                "archive_descriptor": {
                    "package_role": "input.ab16_repository_snapshot.zip",
                    "sha256": "2" * 64,
                    "size_bytes": 1,
                },
                "authority_scope": "AB16_RESEARCH_ONLY",
                "import_mode": "ordinary_pathfinder",
                "member_count": 1,
                "members": [member],
                "ordered_member_digest": hashlib.sha256(
                    (
                        json.dumps(
                            [member],
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                ).hexdigest(),
                "repository_head": history_repository_head,
                "repository_tree": "3" * 40,
                "schema_version": "noncert-cuts-ab16-repository-snapshot-v1",
                "total_bytes": snapshot_member_identity["size_bytes"],
            },
        )
    projected_external = {role: dict(identity) for role, identity in strict_input_identities.items()}
    planned_source_set_digest = hashlib.sha256(
        (
            json.dumps(
                projected_external,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    ).hexdigest()
    if formal:
        assert formal_authority_identity is not None
        package_manifest_identity = _write_campaign_json(
            package_dir / "package-manifest.json",
            {
                "external_sources": [
                    {
                        "package_path": "payload/tool.ab16_authority_v2.py",
                        "parse_json": False,
                        "role": "tool.ab16_authority_v2.py",
                        "source_identity": _detached(formal_authority_identity),
                    }
                ],
                "schema_version": "fixture-formal-package-manifest-v1",
            },
        )
    else:
        package_manifest_identity = _write(
            package_dir / "package-manifest.json",
            {
                "authorizations": {
                    "arm_launch_authorized": False,
                    "formal_campaign_creation_authorized": False,
                    "solver_run_authorized": False,
                },
                "external_source_identities": projected_external,
                "sealed_payload_identities": {
                    "libsystemd": libsystemd_identity,
                },
                "planned_source_set_digest": planned_source_set_digest,
                "purpose": "AB16_GATE_A_DISPOSABLE_DRILL_SOURCE_PACKAGE",
                "schema_version": ("noncert-cuts-ab16-disposable-drill-package-manifest-v2"),
            },
        )
    seal_lines = [
        f"{package_manifest_identity['sha256']}  package-manifest.json\n",
        f"{libsystemd_identity['sha256']}  payload/libsystemd.so\n",
    ]
    if formal:
        assert (
            formal_authority_identity is not None
            and formal_loader_identity is not None
            and snapshot_manifest_identity is not None
        )
        seal_lines.extend(
            [
                (
                    f"{formal_authority_identity['sha256']}  "
                    "payload/tool.ab16_authority_v2.py\n"
                ),
                (
                    f"{snapshot_manifest_identity['sha256']}  "
                    "payload/input.ab16_repository_snapshot.json\n"
                ),
                (
                    f"{formal_loader_identity['sha256']}  "
                    "payload/tool.ab16_formal_loader_v1.py\n"
                ),
            ]
        )
    package_seal_identity = LIFECYCLE.write_exclusive(
        package_dir / "SHA256SUMS",
        "".join(seal_lines).encode("ascii"),
    )
    output_names = {
        "attempt_result": "result.json",
        "abort_reference_release": "abort-unit-reference-release.json",
        "cleanup": "cleanup.json",
        "detached_replay": "detached-replay.json",
        "inner": "inner-lifecycle.json",
        "preterminal": "preterminal-resource.json",
        "reference_acquisition": "unit-reference-acquisition.json",
        "reference_release": "unit-reference-release.json",
        "release": "release-token.json",
        "resource_verification": "independent-resource-verification.json",
        "terminal": "terminal-envelope.json",
    }
    epoch_names = {
        phase: f"manager-epoch-{phase}.json"
        for phase in (
            "launch",
            "preterminal",
            "reference-acquire",
            "release",
            "terminal-first",
            "terminal-stable",
            "reference-release",
            "cleanup",
            "detached-replay",
        )
    }
    transcript_names = {
        phase: f"manager-epoch-{phase}-transcript.json"
        for phase in (
            "launch",
            "preterminal",
            "reference-acquire",
            "release",
            "terminal-first",
            "terminal-stable",
            "reference-release",
            "cleanup",
            "detached-replay",
        )
    }
    pre_run_path = attempt / "pre-run-authority.json"
    selection_path = attempt / "selection.json"
    package = {
        "manifest_identity": package_manifest_identity,
        "package_id": package_seal_identity["sha256"],
        "seal_identity": package_seal_identity,
    }
    tool_identities = {
        "attestor_python": _tool_identity(
            Path(manager_epoch["attestation_toolchain"]["python"]["path"])
        ),
        "busctl": _tool_identity(Path(manager_epoch["observation_toolchain"]["busctl"]["path"])),
        "manager_attestor": _tool_identity(MANAGER_ATTESTOR_PATH),
        "manager_epoch_authority": _tool_identity(MANAGER_AUTHORITY_PATH),
        "organic_arm_runner": _tool_identity(TOOLS / "organic_arm_runner_v1.py"),
        "organic_resource_lifecycle": _tool_identity(LIFECYCLE_PATH),
        "organic_resource_verifier": _tool_identity(VERIFIER_PATH),
        "organic_unit_orchestrator": _tool_identity(ORCHESTRATOR_PATH),
        "python3_13": _tool_identity(workload_python_path),
        "systemd_unit_reference": _tool_identity(TOOLS / "systemd_unit_reference_v1.py"),
        "libsystemd": libsystemd_identity,
        "sudo": _tool_identity(Path(manager_epoch["attestation_toolchain"]["sudo"]["path"])),
        "systemctl": identities["systemctl"],
        "systemd_run": identities["systemd-run"],
    }
    authority_chain = {
        "campaign_root_identity": identities["root"],
        "continuation_identity": identities["continuation"],
        "manager_epoch_authority_identity": identities["preselection"],
        "package": package,
    }
    expected_payload_status = {
        "exit_code": postseal_failure_exit_code,
        "expectation": ("SUCCESS" if postseal_failure_exit_code == 0 else "POST_SEAL_FAILURE"),
        "signal": 0,
    }
    execution_source: dict[str, object] | None = None
    if formal:
        assert (
            formal_loader_identity is not None
            and snapshot_manifest_identity is not None
            and snapshot_member_identity is not None
            and snapshot_root is not None
        )
        snapshot_receipt_identity = _write_campaign_json(
            authority_dir / "source-snapshot-a001/materialization-receipt.json",
            {
                "authority_scope": "AB16_RESEARCH_ONLY",
                "candidate_identity": identities["strict"],
                "created_at_utc": "2026-07-27T00:00:00Z",
                "import_mode": "ordinary_pathfinder",
                "member_count": 1,
                "ordered_member_digest": _campaign_json(
                    Path(snapshot_manifest_identity["path"])
                )["ordered_member_digest"],
                "package_id": package["package_id"],
                "repository_head": history_repository_head,
                "repository_tree": "3" * 40,
                "schema_version": "noncert-cuts-ab16-repository-snapshot-materialization-v1",
                "snapshot_archive_identity": {
                    "path": str(package_dir / "payload/input.ab16_repository_snapshot.zip"),
                    "sha256": "2" * 64,
                    "size_bytes": 1,
                },
                "snapshot_manifest_identity": _detached(snapshot_manifest_identity),
                "snapshot_root": str(snapshot_root),
                "status": "PASS",
                "total_bytes": snapshot_member_identity["size_bytes"],
            },
        )
        execution_source = LIFECYCLE.build_sealed_execution_source(
            live_source_provenance_root=str(history_repository_root),
            sealed_snapshot_execution_root=str(snapshot_root),
            snapshot_manifest_identity=_detached(snapshot_manifest_identity),
            snapshot_materialization_receipt_identity=_detached(snapshot_receipt_identity),
            package_id=str(package["package_id"]),
            literal_identity={
                "sha256": hashlib.sha256(formal_literal.encode()).hexdigest(),
                "size_bytes": len(formal_literal.encode()),
            },
            python_identity=tool_identities["python3_13"],
            loader_identity=formal_loader_identity,
            authority_identity=formal_authority_identity,
            runner_snapshot_relative_path=runner_relative,
            runner_snapshot_member_identity=snapshot_member_identity,
            runner_package_tool_identity=tool_identities["organic_arm_runner"],
            initial_working_directory=str(authority_dir),
            pre_run_authority_path=str(pre_run_path),
            runner_selection_path=str(selection_path),
            module_origin_receipt_path=str(attempt / "module-origin-receipt.json"),
            tmpdir=str(attempt / "tmp"),
        )
        payload_argv = LIFECYCLE.build_formal_direct_argv(
            execution_source,
            literal=formal_literal,
            role="organic-arm",
            campaign_dir=str(authority_dir),
            pre_run_path=str(pre_run_path),
            selection_path=str(selection_path),
            module_origin_receipt_path=str(attempt / "module-origin-receipt.json"),
        )
        supervisor_argv = LIFECYCLE.build_formal_direct_argv(
            execution_source,
            literal=formal_literal,
            role="organic-supervisor",
            campaign_dir=str(authority_dir),
            pre_run_path=str(pre_run_path),
            selection_path=str(selection_path),
            module_origin_receipt_path=str(attempt / "supervisor-module-origin-receipt.json"),
        )
    else:
        snapshot_root = history_snapshot_root
        snapshot_manifest_identity = history_snapshot_manifest_identity
        snapshot_receipt_identity = history_snapshot_receipt_identity
        payload_argv = [
            tool_identities["python3_13"]["path"],
            "-I",
            identities["strict"]["path"],
        ]
        supervisor_argv = [
            tool_identities["python3_13"]["path"],
            "-I",
            str(LIFECYCLE_PATH),
            "supervise",
            "--pre-run",
            str(pre_run_path),
            "--selection",
            str(selection_path),
        ]
    assert (
        snapshot_root is not None
        and snapshot_manifest_identity is not None
        and snapshot_receipt_identity is not None
    )
    launch = {
        "cwd": str(authority_dir) if formal else str(history_repository_root),
        "environment_identity": identities["environment"],
        "libsystemd_path": libsystemd_identity["path"],
        "payload_argv": payload_argv,
        "python3_13_path": tool_identities["python3_13"]["path"],
        "supervisor_argv": supervisor_argv,
        "systemctl_path": identities["systemctl"]["path"],
        "systemd_run_path": identities["systemd-run"]["path"],
    }
    if formal:
        launch["execution_source"] = execution_source
    pre_run = {
        "arm": "control",
        "arm_binding_identity": identities["binding"],
        "arm_launch_authorized": False,
        "arm_selection_write_authorized": True,
        "attempt_dir": str(attempt),
        "authority_chain": authority_chain,
        "baseline_admission_identity": identities["baseline"],
        "baseline_incumbent_sha256": "b" * 64,
        "campaign_id": "c" * 64,
        "campaign_root_identity": identities["root"],
        "common_prestate_identity": identities["prestate"],
        "configuration": "region-capacity",
        "continuation_identity": identities["continuation"],
        "epoch_observation_paths": {phase: str(attempt / name) for phase, name in epoch_names.items()},
        "epoch_transcript_paths": {phase: str(attempt / name) for phase, name in transcript_names.items()},
        "execution_class": execution_class,
        "expected_payload_status": expected_payload_status,
        "live_source_provenance_root": str(history_repository_root),
        "launch": launch,
        "manager_epoch": manager_epoch,
        "order": "ab",
        "output_paths": {role: str(attempt / name) for role, name in output_names.items()},
        "package": package,
        "pre_run_authority_path": str(pre_run_path),
        "prelaunch_allowlist": ["pre-run-authority.json", "selection.json"],
        "preflight_results": {
            "epoch_identity_pass": True,
            "head_identity_pass": True,
            "history_freeze_replay_pass": True,
            "libsystemd_identity_pass": True,
            "package_replay_pass": True,
            "path_preregistration_pass": True,
            "reference_capability_pass": True,
            "reference_contract_pass": True,
            "resource_contract_pass": True,
            "slot_order_pass": True,
            "strict_inputs_replay_pass": True,
            "tool_identities_replay_pass": True,
        },
        "preselection_epoch_identity": identities["preselection"],
        "preselection_transcript_identity": preselection_transcript_identity,
        "prospective_manifest_identity": identities["manifest"],
        "purpose": "PROSPECTIVE_AB16_ORGANIC_ARM_PRE_RUN_AUTHORITY",
        "reference_capability_identity": capability_identity,
        "reference_capability_transcript_identity": capability_transcript_identity,
        "reference_contract": copy.deepcopy(LIFECYCLE.REFERENCE_CONTRACT),
        "repository_head": history_repository_head,
        "repository_git_tool_identity": identities["git"],
        "repository_root": str(history_repository_root),
        "resource_contract": dict(LIFECYCLE.FORMAL_RESOURCE_CONTRACT if formal else LIFECYCLE.DRILL_RESOURCE_CONTRACT),
        "run_nonce": "run-a",
        "runner_selection_path": str(selection_path),
        "schema_version": "noncert-cuts-ab16-organic-pre-run-authority-v2",
        "sealed_snapshot_execution_root": str(snapshot_root),
        "seed": 2026072301,
        "snapshot_manifest_identity": _detached(snapshot_manifest_identity),
        "snapshot_materialization_receipt_identity": _detached(
            snapshot_receipt_identity
        ),
        "slot": "region-capacity-ab-control",
        "solver_run_authorized": False,
        "status": "PASS",
        "strict_input_identities": strict_input_identities,
        "suite_selection_identity": identities["suite-selection"],
        "history_freeze_replay_identity": history_freeze_replay_identity,
        "tool_identities": tool_identities,
        "unit_name": "cuts-ab16-region-capacity-ab-control.service",
        "verdict": "AB16_ORGANIC_PRE_RUN_AUTHORITY_PASS",
        "workers": 1,
    }
    LIFECYCLE.validate_pre_run_authority(pre_run)
    pre_run_identity = _write(pre_run_path, pre_run)
    selection = {
        "arm": "control",
        "arm_binding_identity": identities["binding"],
        "attempt_dir": str(attempt),
        "authority_chain": authority_chain,
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": formal,
            "production_certified_authorized": False,
            "solver_run_authorized": formal,
        },
        "baseline_admission_identity": identities["baseline"],
        "baseline_incumbent_sha256": "b" * 64,
        "campaign_id": "c" * 64,
        "common_prestate_identity": identities["prestate"],
        "configuration": "region-capacity",
        "enabled_families": [],
        "execution_class": execution_class,
        "expected_payload_status": expected_payload_status,
        "fresh_process_required": True,
        "live_source_provenance_root": pre_run["live_source_provenance_root"],
        "manifest_identity": identities["manifest"],
        "order": "ab",
        "pre_run_authority_identity": pre_run_identity,
        "purpose": (
            "prospective_noncert_cuts_ab16_formal_arm" if formal else "noncert_cuts_ab16_disposable_live_drill"
        ),
        "repository_head": history_repository_head,
        "repository_git_tool_identity": identities["git"],
        "repository_root": str(history_repository_root),
        "run_nonce": "run-a",
        "schema_version": (
            "noncert-cuts-ab16-organic-arm-selection-v1" if formal else "noncert-cuts-ab16-organic-drill-selection-v1"
        ),
        "sealed_snapshot_execution_root": pre_run[
            "sealed_snapshot_execution_root"
        ],
        "seed": 2026072301,
        "selection_nonce": "selection-a",
        "snapshot_manifest_identity": pre_run["snapshot_manifest_identity"],
        "snapshot_materialization_receipt_identity": pre_run[
            "snapshot_materialization_receipt_identity"
        ],
        "slot": "region-capacity-ab-control",
        "unit_name": "cuts-ab16-region-capacity-ab-control.service",
        "workers": 1,
    }
    LIFECYCLE.validate_runner_selection(
        selection,
        pre_run_authority=pre_run,
        pre_run_authority_identity=pre_run_identity,
    )
    _write(selection_path, selection)
    return attempt, pre_run_path, selection_path


def _run(
    tmp_path: Path,
    *,
    execution_class: str | None = None,
    **adapter_kwargs: object,
) -> tuple[Path, dict[str, object]]:
    exit_code = adapter_kwargs.get("payload_exit_code", 0)
    assert type(exit_code) is int
    attempt, pre_run_path, selection_path = _fixture(
        tmp_path,
        postseal_failure_exit_code=exit_code,
        execution_class=execution_class,
    )
    result = ORCHESTRATOR.orchestrate_with_adapter(
        pre_run_path=pre_run_path,
        selection_path=selection_path,
        adapter=FakeAdapter(
            attempt_dir=attempt,
            slot="region-capacity-ab-control",
            **adapter_kwargs,
        ),
    )
    return attempt, result


def _evidence(attempt: Path) -> dict[str, Any]:
    pre_run = VERIFIER.snapshot_json(attempt / "pre-run-authority.json")
    paths = pre_run.value["output_paths"]
    return {
        "pre_run": pre_run,
        "selection": VERIFIER.snapshot_json(attempt / "selection.json"),
        "inner": VERIFIER.snapshot_json(paths["inner"]),
        "preterminal": VERIFIER.snapshot_json(paths["preterminal"]),
        "payload_result": VERIFIER.snapshot_json(paths["attempt_result"]),
        "resource": VERIFIER.snapshot_json(paths["resource_verification"]),
        "reference_acquisition": VERIFIER.snapshot_json(paths["reference_acquisition"]),
        "release": VERIFIER.snapshot_json(paths["release"]),
        "terminal": VERIFIER.snapshot_json(paths["terminal"]),
        "reference_release": VERIFIER.snapshot_json(paths["reference_release"]),
        "cleanup": VERIFIER.snapshot_json(paths["cleanup"]),
        "detached_epoch": VERIFIER.snapshot_json(pre_run.value["epoch_observation_paths"]["detached-replay"]),
        "verifier_tool_identity": VERIFIER.current_tool_identity(),
    }


def _mutated(snapshot: Any, mutate: Any) -> Any:
    value = copy.deepcopy(snapshot.value)
    mutate(value)
    return VERIFIER.Snapshot(
        raw=snapshot.raw,
        value=value,
        identity=copy.deepcopy(snapshot.identity),
    )


def _offline_epoch_observer(
    *,
    pre_run: Mapping[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    transcript = VERIFIER.snapshot_json(pre_run["preselection_transcript_identity"]["path"]).value
    tools = pre_run["tool_identities"]

    def capture_manager_epoch_with_transcript(**kwargs: object) -> dict[str, object]:
        assert kwargs == {
            "attestor_path": tools["manager_attestor"]["path"],
            "busctl_path": tools["busctl"]["path"],
            "python_path": tools["attestor_python"]["path"],
            "sudo_path": tools["sudo"]["path"],
        }
        return {
            "manager_epoch": copy.deepcopy(pre_run["manager_epoch"]),
            "transcript": copy.deepcopy(transcript),
        }

    authority = SimpleNamespace(
        capture_manager_epoch_with_transcript=capture_manager_epoch_with_transcript,
        validate_manager_epoch=MANAGER_AUTHORITY.validate_manager_epoch,
        validate_manager_epoch_capture_transcript=(MANAGER_AUTHORITY.validate_manager_epoch_capture_transcript),
    )
    monkeypatch.setattr(
        ORCHESTRATOR,
        "_load_pinned_module",
        lambda *_args, **_kwargs: authority,
    )
    return ORCHESTRATOR.build_pinned_epoch_observer(pre_run)


@pytest.mark.parametrize(
    "phase",
    [
        "launch",
        "preterminal",
        "reference-acquire",
        "release",
        "terminal-first",
        "terminal-stable",
        "reference-release",
        "cleanup",
        "detached-replay",
    ],
)
def test_pinned_epoch_observer_accepts_every_preregistered_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = VERIFIER.snapshot_json(pre_run_path).value
    observer = _offline_epoch_observer(
        pre_run=pre_run,
        monkeypatch=monkeypatch,
    )

    captured = observer(phase)

    assert phase in ORCHESTRATOR.EPOCH_PHASES
    assert len(ORCHESTRATOR.EPOCH_PHASES) == 9
    assert captured.manager_epoch == pre_run["manager_epoch"]
    assert captured.transcript == VERIFIER.snapshot_json(pre_run["preselection_transcript_identity"]["path"]).value
    assert not list(attempt.glob("manager-epoch-*.json"))


def test_pinned_epoch_observer_uses_independent_attestor_python(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = VERIFIER.snapshot_json(pre_run_path).value
    tools = pre_run["tool_identities"]
    attestor_python_path = Path(tools["attestor_python"]["path"])
    workload_python_path = Path(tools["python3_13"]["path"])
    assert attestor_python_path != workload_python_path
    assert attestor_python_path.read_bytes() != workload_python_path.read_bytes()

    observer = _offline_epoch_observer(
        pre_run=pre_run,
        monkeypatch=monkeypatch,
    )

    captured = observer("launch")

    assert captured.manager_epoch == pre_run["manager_epoch"]


def test_pinned_epoch_observer_rejects_python3_13_as_attestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = VERIFIER.snapshot_json(pre_run_path).value
    tools = pre_run["tool_identities"]
    workload_python_path = Path(tools["python3_13"]["path"])
    assert tools["attestor_python"] != tools["python3_13"]

    poisoned_pre_run = copy.deepcopy(pre_run)
    poisoned_pre_run["tool_identities"]["attestor_python"] = copy.deepcopy(
        tools["python3_13"]
    )
    drifted_epoch = copy.deepcopy(pre_run["manager_epoch"])
    drifted_epoch["attestation_toolchain"]["python"] = _full_identity(
        workload_python_path
    )

    def capture_manager_epoch_with_transcript(**kwargs: object) -> dict[str, object]:
        assert kwargs["python_path"] == tools["python3_13"]["path"]
        return {
            "manager_epoch": copy.deepcopy(drifted_epoch),
            "transcript": {},
        }

    authority = SimpleNamespace(
        capture_manager_epoch_with_transcript=capture_manager_epoch_with_transcript,
        validate_manager_epoch=lambda _epoch: None,
        validate_manager_epoch_capture_transcript=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        ORCHESTRATOR,
        "_load_pinned_module",
        lambda *_args, **_kwargs: authority,
    )
    observer = ORCHESTRATOR.build_pinned_epoch_observer(poisoned_pre_run)

    with pytest.raises(
        ORCHESTRATOR.OrchestratorError,
        match="live manager/boot epoch drifted",
    ):
        observer("launch")


@pytest.mark.parametrize("phase", ["terminal", "unknown-phase"])
def test_pinned_epoch_observer_rejects_old_or_unknown_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = VERIFIER.snapshot_json(pre_run_path).value
    observer = _offline_epoch_observer(
        pre_run=pre_run,
        monkeypatch=monkeypatch,
    )

    with pytest.raises(
        ORCHESTRATOR.OrchestratorError,
        match="unsupported manager epoch phase",
    ):
        observer(phase)


def test_reference_held_across_two_terminal_snapshots_then_unref_cleanup(
    tmp_path: Path,
) -> None:
    attempt, result = _run(tmp_path)
    assert result["status"] == "PASS"
    assert result["verdict"] == "RESOURCE_TERMINAL_CLEANUP_REPLAY_PASS"
    terminal = VERIFIER.snapshot_json(attempt / "terminal-envelope.json").value
    acquisition = VERIFIER.snapshot_json(attempt / "unit-reference-acquisition.json").value
    release = VERIFIER.snapshot_json(attempt / "unit-reference-release.json").value
    cleanup = VERIFIER.snapshot_json(attempt / "cleanup.json").value

    invocation_id = acquisition["systemd_raw"]["InvocationID"]
    assert invocation_id == "0123456789abcdef0123456789abcdef"
    assert terminal["first_systemd_raw"]["InvocationID"] == invocation_id
    assert terminal["stable_systemd_raw"]["InvocationID"] == invocation_id
    assert terminal["first_systemd_raw"] == terminal["stable_systemd_raw"]
    assert (
        terminal["stable_captured_at_monotonic_ns"] - terminal["first_captured_at_monotonic_ns"]
        >= LIFECYCLE.REFERENCE_STABILITY_HOLD_NS
    )
    assert acquisition["call_evidence"]["client_unique_name"] == release["call_evidence"]["client_unique_name"]
    assert release["reference_acquisition_identity"] == _identity(attempt / "unit-reference-acquisition.json")
    assert cleanup["reference_release_identity"] == _identity(attempt / "unit-reference-release.json")
    assert cleanup["cgroup_path_exists"] is False
    assert cleanup["unit_load_state"] == "not-found"
    assert cleanup["matching_unit_names"] == []


def test_detached_replay_rejects_deleted_standalone_epoch_observation(
    tmp_path: Path,
) -> None:
    attempt, _result = _run(tmp_path)
    evidence = _evidence(attempt)
    pre_run = evidence["pre_run"].value
    Path(pre_run["epoch_observation_paths"]["reference-acquire"]).unlink()

    with pytest.raises(
        VERIFIER.VerificationError,
        match="symlink or invalid file path",
    ):
        VERIFIER.verify_detached(**evidence)


def test_detached_replay_rejects_mutated_standalone_epoch_observation(
    tmp_path: Path,
) -> None:
    attempt, _result = _run(tmp_path)
    evidence = _evidence(attempt)
    pre_run = evidence["pre_run"].value
    observation_path = Path(pre_run["epoch_observation_paths"]["release"])
    observation = VERIFIER.snapshot_json(observation_path).value
    observation["observed_at_monotonic_ns"] += 1
    observation_path.unlink()
    _write(observation_path, observation)

    with pytest.raises(
        VERIFIER.VerificationError,
        match="release standalone/embedded epoch observation differs",
    ):
        VERIFIER.verify_detached(**evidence)


def test_detached_replay_rejects_impossible_epoch_event_ordering(
    tmp_path: Path,
) -> None:
    attempt, _result = _run(tmp_path)
    evidence = _evidence(attempt)
    pre_run = evidence["pre_run"].value
    observation_path = Path(pre_run["epoch_observation_paths"]["terminal-first"])
    terminal = copy.deepcopy(evidence["terminal"].value)
    impossible_time = terminal["first_captured_at_monotonic_ns"] + 1
    terminal["manager_epoch_observation"]["observed_at_monotonic_ns"] = impossible_time
    observation = copy.deepcopy(terminal["manager_epoch_observation"])
    observation_path.unlink()
    _write(observation_path, observation)
    evidence["terminal"] = VERIFIER.Snapshot(
        raw=evidence["terminal"].raw,
        value=terminal,
        identity=copy.deepcopy(evidence["terminal"].identity),
    )

    with pytest.raises(
        VERIFIER.VerificationError,
        match="manager epoch observation time chain failed",
    ):
        VERIFIER.verify_detached(**evidence)


def test_expected_postseal_failure_is_not_hidden_by_reference(
    tmp_path: Path,
) -> None:
    attempt, result = _run(tmp_path, payload_exit_code=7)
    assert result["status"] == "PASS"
    assert result["verdict"] == "EXPECTED_POST_SEAL_FAILURE_REPLAY_PASS"
    terminal = VERIFIER.snapshot_json(attempt / "terminal-envelope.json").value
    assert terminal["first_systemd_raw"]["Result"] == "exit-code"
    assert terminal["first_systemd_raw"]["ExecMainStatus"] == "7"
    assert (attempt / "unit-reference-release.json").is_file()
    assert (attempt / "cleanup.json").is_file()


@pytest.mark.parametrize("replacement", ["", "f" * 32])
def test_terminal_invocation_must_be_nonempty_and_exact(
    tmp_path: Path,
    replacement: str,
) -> None:
    attempt, _result = _run(tmp_path)
    evidence = _evidence(attempt)

    def replace_both(value: dict[str, Any]) -> None:
        value["first_systemd_raw"]["InvocationID"] = replacement
        value["stable_systemd_raw"]["InvocationID"] = replacement

    evidence["terminal"] = _mutated(
        evidence["terminal"],
        replace_both,
    )
    with pytest.raises(
        VERIFIER.VerificationError,
        match="exact unit identity",
    ):
        VERIFIER.verify_detached(**evidence)


def test_terminal_hold_shorter_than_one_second_fails_closed(
    tmp_path: Path,
) -> None:
    attempt, _result = _run(tmp_path)
    evidence = _evidence(attempt)

    def shorten(value: dict[str, Any]) -> None:
        value["stable_captured_at_monotonic_ns"] = (
            value["first_captured_at_monotonic_ns"] + LIFECYCLE.REFERENCE_STABILITY_HOLD_NS - 1
        )
        value["stable_manager_epoch_observation"]["observed_at_monotonic_ns"] = (
            value["stable_captured_at_monotonic_ns"] - 1
        )

    evidence["terminal"] = _mutated(evidence["terminal"], shorten)
    pre_run = evidence["pre_run"].value
    stable_epoch_path = Path(pre_run["epoch_observation_paths"]["terminal-stable"])
    stable_epoch_path.unlink()
    _write(
        stable_epoch_path,
        evidence["terminal"].value["stable_manager_epoch_observation"],
    )
    with pytest.raises(
        VERIFIER.VerificationError,
        match="stability interval",
    ):
        VERIFIER.verify_detached(**evidence)


@pytest.mark.parametrize(
    ("target", "mutation", "message"),
    [
        (
            "reference_release",
            lambda value: value["call_evidence"].__setitem__(
                "client_unique_name",
                ":1.901",
            ),
            "same DBus client",
        ),
        (
            "reference_release",
            lambda value: value.__setitem__(
                "reference_acquisition_identity",
                {**value["reference_acquisition_identity"], "sha256": "0" * 64},
            ),
            "identity chain",
        ),
        (
            "cleanup",
            lambda value: value.__setitem__("cgroup_path_exists", True),
            "absence of residual",
        ),
    ],
)
def test_reference_chain_and_post_unref_cleanup_mutations_fail_closed(
    tmp_path: Path,
    target: str,
    mutation: Any,
    message: str,
) -> None:
    attempt, _result = _run(tmp_path)
    evidence = _evidence(attempt)
    evidence[target] = _mutated(evidence[target], mutation)
    with pytest.raises(VERIFIER.VerificationError, match=message):
        VERIFIER.verify_detached(**evidence)


def test_post_reference_failure_aborts_reference_and_proves_cleanup(
    tmp_path: Path,
) -> None:
    attempt, pre_run, selection = _fixture(tmp_path)
    adapter = FakeAdapter(
        attempt_dir=attempt,
        slot="region-capacity-ab-control",
        terminal_capture_error=True,
    )
    with pytest.raises(Exception, match="fixture terminal capture failed"):
        ORCHESTRATOR.orchestrate_with_adapter(
            pre_run_path=pre_run,
            selection_path=selection,
            adapter=adapter,
        )
    assert adapter.reference is not None
    assert adapter.reference.abort_count == 1
    assert adapter.reference.acquired_unit is None
    abort = VERIFIER.snapshot_json(attempt / "abort-unit-reference-release.json").value
    assert abort["status"] == "RECORDED"
    assert abort["verdict"] == "REFERENCE_CONNECTION_ABORTED_NO_PASS"
    cleanup = VERIFIER.snapshot_json(attempt / "cleanup.json").value
    assert cleanup["schema_version"] == "noncert-cuts-ab16-abort-cleanup-v2"
    assert cleanup["status"] == "PASS"
    assert cleanup["authorizations"]["runtime_effect_authorized"] is False


def test_abort_without_cleanup_proof_is_incomplete(tmp_path: Path) -> None:
    attempt, pre_run, selection = _fixture(tmp_path)
    adapter = FakeAdapter(
        attempt_dir=attempt,
        slot="region-capacity-ab-control",
        terminal_capture_error=True,
        abort_cleanup_residual=True,
    )
    with pytest.raises(
        ORCHESTRATOR.OrchestratorError,
        match="cleanup could not be established",
    ):
        ORCHESTRATOR.orchestrate_with_adapter(
            pre_run_path=pre_run,
            selection_path=selection,
            adapter=adapter,
        )
    assert not (attempt / "cleanup.json").exists()
    assert not (attempt / "detached-replay.json").exists()


def test_formal_selected_byte_systemd_tail_and_three_open_files_are_exact(
    tmp_path: Path,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = LIFECYCLE.strict_loads(
        LIFECYCLE.snapshot_regular(pre_run_path).raw,
        "formal fixture pre-run",
    )
    launch = pre_run["launch"]
    raw = launch["supervisor_argv"]
    argv = LIFECYCLE.build_systemd_run_argv(
        systemd_run_path=launch["systemd_run_path"],
        unit_name=pre_run["unit_name"],
        supervisor_argv=raw,
        resource_contract=pre_run["resource_contract"],
        execution_class=pre_run["execution_class"],
    )
    assert argv.count("--") == 1
    separator = argv.index("--")
    selected = launch["execution_source"]["selected_byte_launch"]
    assert argv[separator - 3 : separator] == [
        f"--property=OpenFile={selected['python_identity']['path']}:ab16-python:read-only",
        f"--property=OpenFile={selected['loader_identity']['path']}:ab16-loader:read-only",
        f"--property=OpenFile={selected['authority_identity']['path']}:ab16-authority:read-only",
    ]
    assert argv[separator + 1 :] == [
        "/proc/self/fd/3",
        "-I",
        "-B",
        "-c",
        raw[4],
        "systemd-openfile",
        raw[6],
        *raw[7:],
    ]
    assert launch["payload_argv"][5] == "direct"
    assert launch["payload_argv"][6] == raw[6]


def test_disposable_drill_systemd_argv_remains_legacy_byte_shape(
    tmp_path: Path,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(
        tmp_path,
        postseal_failure_exit_code=23,
        execution_class="DISPOSABLE_LIVE_DRILL",
    )
    pre_run = LIFECYCLE.strict_loads(
        LIFECYCLE.snapshot_regular(pre_run_path).raw,
        "drill fixture pre-run",
    )
    launch = pre_run["launch"]
    actual = LIFECYCLE.build_systemd_run_argv(
        systemd_run_path=launch["systemd_run_path"],
        unit_name=pre_run["unit_name"],
        supervisor_argv=launch["supervisor_argv"],
        resource_contract=pre_run["resource_contract"],
        execution_class=pre_run["execution_class"],
    )
    contract = pre_run["resource_contract"]
    assert actual == [
        launch["systemd_run_path"],
        "--user",
        "--quiet",
        f"--unit={pre_run['unit_name'].removesuffix('.service')}",
        f"--property=MemoryHigh={contract['memory_high_bytes']}",
        f"--property=MemoryMax={contract['memory_max_bytes']}",
        f"--property=MemorySwapMax={contract['memory_swap_max_bytes']}",
        f"--property=CollectMode={contract['collect_mode']}",
        f"--property=OOMPolicy={contract['oom_policy']}",
        f"--property=KillMode={contract['kill_mode']}",
        "--property=SendSIGKILL=yes",
        f"--property=RuntimeMaxSec={contract['runtime_max_seconds']}",
        "--",
        *launch["supervisor_argv"],
    ]
    assert all("OpenFile=" not in argument for argument in actual)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda source: source.__setitem__("unexpected", False),
        lambda source: source.__setitem__("loader_role", "parallel-loader"),
        lambda source: source.__setitem__("runner_module", "ambient.runner"),
        lambda source: source["environment"].__setitem__("PYTHONPATH", "/ambient"),
        lambda source: source["selected_byte_launch"].__setitem__(
            "open_file_names",
            ["ab16-loader", "ab16-python", "ab16-authority"],
        ),
        lambda source: source["selected_byte_launch"].__setitem__(
            "fd_map",
            {"authority": 4, "loader": 5, "python": 3},
        ),
        lambda source: source["selected_byte_launch"].__setitem__(
            "authority_identity",
            source["selected_byte_launch"]["loader_identity"],
        ),
    ],
)
def test_formal_execution_source_mutations_fail_closed(
    tmp_path: Path,
    mutation: Any,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = LIFECYCLE.strict_loads(
        LIFECYCLE.snapshot_regular(pre_run_path).raw,
        "formal fixture pre-run",
    )
    changed = copy.deepcopy(pre_run)
    mutation(changed["launch"]["execution_source"])
    with pytest.raises(LIFECYCLE.LifecycleError):
        LIFECYCLE.validate_pre_run_authority(changed)
    with pytest.raises(VERIFIER.VerificationError):
        VERIFIER.validate_pre_run_authority(changed)
