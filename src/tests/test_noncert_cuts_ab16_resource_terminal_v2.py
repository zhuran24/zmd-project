from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
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
        "git",
        "systemctl",
        "systemd-run",
    ):
        path = authority_dir / f"{name}.json"
        identities[name] = _write(path, {"name": name})
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
    frozen_source = ROOT / "docs/research/noncert_cuts_ab16_20260724/organic_resource_lifecycle_v1.py"
    frozen_source_identity = _tool_identity(frozen_source)
    history_manifest = {
        "created_at_utc": "2026-07-24T00:00:00Z",
        "file_count": 1,
        "files": [
            {
                "mode": frozen_source_identity["mode"],
                "path": str(frozen_source.relative_to(ROOT)),
                "sha256": frozen_source_identity["sha256"],
                "size_bytes": frozen_source_identity["size_bytes"],
            }
        ],
        "frozen_roots": ["docs/research/noncert_cuts_ab16_20260724"],
        "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_FREEZE",
        "repository_head": "d" * 40,
        "repository_root": str(ROOT),
        "schema_version": ("noncert-cuts-ab16-terminal-reference-history-freeze-v1"),
        "v1_source_glob": ("docs/research/noncert_cuts_ab16_20260724/*_v1.py"),
    }
    history_manifest_identity = LIFECYCLE.write_exclusive(
        authority_dir / "history-freeze-manifest.json",
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
    history_freeze_replay_identity = _write(
        authority_dir / "history-freeze-replay.json",
        {
            "authorizations": {
                "formal_campaign_creation_authorized": False,
                "organic_arm_launch_authorized": False,
            },
            "file_count": 1,
            "manifest_identity": history_manifest_identity,
            "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_REPLAY",
            "schema_version": ("noncert-cuts-ab16-terminal-reference-history-replay-v1"),
            "status": "PASS",
            "verdict": "IMMUTABLE_FAILED_GATE_A_HISTORY_REPLAY_PASS",
        },
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
    package_seal_identity = LIFECYCLE.write_exclusive(
        package_dir / "SHA256SUMS",
        (
            f"{package_manifest_identity['sha256']}  package-manifest.json\n"
            f"{libsystemd_identity['sha256']}  payload/libsystemd.so\n"
        ).encode("ascii"),
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
    payload_script = str(TOOLS / "organic_arm_runner_v1.py") if formal else identities["strict"]["path"]
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
        "launch": {
            "cwd": str(ROOT),
            "environment_identity": identities["environment"],
            "libsystemd_path": libsystemd_identity["path"],
            "payload_argv": [
                manager_epoch["attestation_toolchain"]["python"]["path"],
                "-I",
                payload_script,
            ],
            "python3_13_path": manager_epoch["attestation_toolchain"]["python"]["path"],
            "supervisor_argv": [
                manager_epoch["attestation_toolchain"]["python"]["path"],
                "-I",
                str(LIFECYCLE_PATH),
                "supervise",
                "--pre-run",
                str(pre_run_path),
                "--selection",
                str(selection_path),
            ],
            "systemctl_path": identities["systemctl"]["path"],
            "systemd_run_path": identities["systemd-run"]["path"],
        },
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
        "repository_head": "d" * 40,
        "repository_git_tool_identity": identities["git"],
        "repository_root": str(ROOT),
        "resource_contract": dict(LIFECYCLE.FORMAL_RESOURCE_CONTRACT if formal else LIFECYCLE.DRILL_RESOURCE_CONTRACT),
        "run_nonce": "run-a",
        "runner_selection_path": str(selection_path),
        "schema_version": "noncert-cuts-ab16-organic-pre-run-authority-v2",
        "seed": 2026072301,
        "slot": "region-capacity-ab-control",
        "solver_run_authorized": False,
        "status": "PASS",
        "strict_input_identities": strict_input_identities,
        "suite_selection_identity": identities["suite-selection"],
        "history_freeze_replay_identity": history_freeze_replay_identity,
        "tool_identities": {
            "busctl": _tool_identity(Path(manager_epoch["observation_toolchain"]["busctl"]["path"])),
            "manager_attestor": _tool_identity(MANAGER_ATTESTOR_PATH),
            "manager_epoch_authority": _tool_identity(MANAGER_AUTHORITY_PATH),
            "organic_arm_runner": _tool_identity(TOOLS / "organic_arm_runner_v1.py"),
            "organic_resource_lifecycle": _tool_identity(LIFECYCLE_PATH),
            "organic_resource_verifier": _tool_identity(VERIFIER_PATH),
            "organic_unit_orchestrator": _tool_identity(ORCHESTRATOR_PATH),
            "python3_13": _tool_identity(Path(manager_epoch["attestation_toolchain"]["python"]["path"])),
            "systemd_unit_reference": _tool_identity(TOOLS / "systemd_unit_reference_v1.py"),
            "libsystemd": libsystemd_identity,
            "sudo": _tool_identity(Path(manager_epoch["attestation_toolchain"]["sudo"]["path"])),
            "systemctl": identities["systemctl"],
            "systemd_run": identities["systemd-run"],
        },
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
        "manifest_identity": identities["manifest"],
        "order": "ab",
        "pre_run_authority_identity": pre_run_identity,
        "purpose": (
            "prospective_noncert_cuts_ab16_formal_arm" if formal else "noncert_cuts_ab16_disposable_live_drill"
        ),
        "repository_head": "d" * 40,
        "repository_git_tool_identity": identities["git"],
        "repository_root": str(ROOT),
        "run_nonce": "run-a",
        "schema_version": (
            "noncert-cuts-ab16-organic-arm-selection-v1" if formal else "noncert-cuts-ab16-organic-drill-selection-v1"
        ),
        "seed": 2026072301,
        "selection_nonce": "selection-a",
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
    authority = SimpleNamespace(
        capture_manager_epoch_with_transcript=lambda **_kwargs: {
            "manager_epoch": copy.deepcopy(pre_run["manager_epoch"]),
            "transcript": copy.deepcopy(transcript),
        },
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
