from __future__ import annotations

import base64
import copy
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Sequence

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/noncert_cuts_ab16_20260724"
LIFECYCLE_PATH = TOOLS / "organic_resource_lifecycle_v1.py"
VERIFIER_PATH = TOOLS / "organic_resource_verifier_v1.py"
ORCHESTRATOR_PATH = TOOLS / "organic_unit_orchestrator_v1.py"
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


LIFECYCLE = _load("ab16_resource_lifecycle_test", LIFECYCLE_PATH)
VERIFIER = _load("ab16_resource_verifier_test", VERIFIER_PATH)
ORCHESTRATOR = _load("ab16_unit_orchestrator_test", ORCHESTRATOR_PATH)
MANAGER_AUTHORITY = _load("ab16_manager_authority_test", MANAGER_AUTHORITY_PATH)


def _identity(path: Path) -> dict[str, object]:
    return dict(LIFECYCLE.snapshot_regular(path).identity)


def _detached(identity: dict[str, object]) -> dict[str, object]:
    return {field: identity[field] for field in ("path", "sha256", "size_bytes")}


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
        payload_result = {
            "schema_version": "noncert-cuts-ab16-organic-arm-result-v1",
            "slot": self.slot,
            "status": "UNKNOWN",
        }
        payload_result_identity = LIFECYCLE.write_exclusive(
            self.attempt_dir / "result.json",
            LIFECYCLE.canonical_json_bytes(payload_result) + b"\n",
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
        self.clock = 1100
        observed = "fedcba9876543210fedcba9876543210" if self.terminal_invocation_drift else self.invocation
        failed = self.payload_exit_code != 0
        return ORCHESTRATOR.TerminalEvidence(
            captured_at_monotonic_ns=1100,
            systemd_raw={
                "ActiveState": "failed" if failed else "inactive",
                "ControlGroup": "",
                "ExecMainCode": "exited",
                "ExecMainStatus": str(self.payload_exit_code),
                "InvocationID": observed,
                "Result": "exit-code" if failed else "success",
                "SubState": "failed" if failed else "dead",
            },
        )

    def capture_cleanup(
        self,
        *,
        unit_name: str,
        launch: Any,
        control_group: str,
    ) -> Any:
        assert control_group == "/user.slice/ab16.scope"
        self.clock = 1300
        return ORCHESTRATOR.CleanupEvidence(
            captured_at_monotonic_ns=1300,
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


def _fixture(
    tmp_path: Path,
    *,
    postseal_failure_exit_code: int = 0,
) -> tuple[Path, Path, Path]:
    authority_attempt = tmp_path / "attempt"
    attempt = authority_attempt / "run"
    attempt.mkdir(parents=True)
    (authority_attempt / "support").mkdir()
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
        "package-manifest",
        "package-seal",
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
            "schema_version": "noncert-cuts-ab16-launch-environment-v1",
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
    output_names = {
        "attempt_result": "result.json",
        "cleanup": "cleanup.json",
        "detached_replay": "detached-replay.json",
        "inner": "inner-lifecycle.json",
        "preterminal": "preterminal-resource.json",
        "release": "release-token.json",
        "resource_verification": "independent-resource-verification.json",
        "terminal": "terminal-envelope.json",
    }
    epoch_names = {
        phase: f"manager-epoch-{phase}.json"
        for phase in (
            "launch",
            "preterminal",
            "release",
            "terminal",
            "cleanup",
            "detached-replay",
        )
    }
    transcript_names = {
        phase: f"manager-epoch-{phase}-transcript.json"
        for phase in (
            "launch",
            "preterminal",
            "release",
            "terminal",
            "cleanup",
            "detached-replay",
        )
    }
    pre_run_path = attempt / "pre-run-authority.json"
    selection_path = attempt / "selection.json"
    package = {
        "manifest_identity": identities["package-manifest"],
        "package_id": identities["package-seal"]["sha256"],
        "seal_identity": identities["package-seal"],
    }
    authority_chain = {
        "campaign_root_identity": identities["root"],
        "continuation_identity": identities["continuation"],
        "manager_epoch_authority_identity": identities["preselection"],
        "package": package,
    }
    execution_class = "FORMAL_AB16"
    expected_payload_status = {
        "exit_code": postseal_failure_exit_code,
        "expectation": ("SUCCESS" if postseal_failure_exit_code == 0 else "POST_SEAL_FAILURE"),
        "signal": 0,
    }
    tool_identities = {
        "busctl": _tool_identity(Path(manager_epoch["observation_toolchain"]["busctl"]["path"])),
        "manager_attestor": _tool_identity(MANAGER_ATTESTOR_PATH),
        "manager_epoch_authority": _tool_identity(MANAGER_AUTHORITY_PATH),
        "organic_arm_runner": _tool_identity(TOOLS / "organic_arm_runner_v1.py"),
        "organic_resource_lifecycle": _tool_identity(LIFECYCLE_PATH),
        "organic_resource_verifier": _tool_identity(VERIFIER_PATH),
        "organic_unit_orchestrator": _tool_identity(ORCHESTRATOR_PATH),
        "python3_13": _tool_identity(Path(manager_epoch["attestation_toolchain"]["python"]["path"])),
        "sudo": _tool_identity(Path(manager_epoch["attestation_toolchain"]["sudo"]["path"])),
        "systemctl": identities["systemctl"],
        "systemd_run": identities["systemd-run"],
    }
    execution_tool_identities = {
        **tool_identities,
        "ab16_contract": _tool_identity(TOOLS / "ab16_contract_v1.py"),
        "ab16_terminal_gate": _tool_identity(TOOLS / "ab16_terminal_gate_v1.py"),
        "organic_arm_replay": _tool_identity(TOOLS / "organic_arm_replay_v1.py"),
    }
    research_only_authorizations = {
        "cut_authorized": False,
        "family_global_soundness_authorized": False,
        "global_claim_authorized": False,
        "lower_bound_authorized": False,
        "mathematical_claim_authorized": False,
        "optimality_authorized": False,
        "production_certified_authorized": False,
        "stage_b_promotion_authorized": False,
        "upper_bound_authorized": False,
        "witness_authorized": False,
    }
    input_set_identity = _write(
        authority_attempt / "attempt-input-set.json",
        {"schema_version": "noncert-cuts-ab16-attempt-input-set-v2"},
    )
    execution = {
        "attempt_ordinal": 1,
        "authorizations": research_only_authorizations,
        "authority_attempt_dir": str(authority_attempt),
        "authority_chain": authority_chain,
        "campaign_id": "c" * 64,
        "campaign_root_identity": identities["root"],
        "continuation_identity": identities["continuation"],
        "input_set_identity": input_set_identity,
        "input_set_sha256": "e" * 64,
        "manager_epoch": manager_epoch,
        "manifest_identity": _detached(identities["manifest"]),
        "package": package,
        "pre_run_authority_path": str(pre_run_path),
        "preregistration_sha256": "f" * 64,
        "repository_git_tool_identity": identities["git"],
        "repository_head": "d" * 40,
        "repository_root": str(ROOT),
        "run_dir": str(attempt),
        "run_nonce": "run-a",
        "schema_version": LIFECYCLE.ATTEMPT_EXECUTION_SCHEMA,
        "scientific_input_set_sha256": "1" * 64,
        "scientific_materialization_sha256": "2" * 64,
        "selection_path": str(selection_path),
        "slot": "region-capacity-ab-control",
        "status": "READY",
        "suite_selection_identity": _detached(identities["suite-selection"]),
        "support_dir": str(authority_attempt / "support"),
        "tool_identities": execution_tool_identities,
        "unit_name": "cuts-ab16-region-capacity-ab-control.service",
    }
    execution_identity = _detached(_write(authority_attempt / "attempt-execution.json", execution))
    payload_script = str(TOOLS / "organic_arm_runner_v1.py")
    pre_run = {
        "arm": "control",
        "arm_binding_identity": identities["binding"],
        "arm_launch_authorized": False,
        "arm_selection_write_authorized": True,
        "attempt_execution_identity": execution_identity,
        "attempt_dir": str(attempt),
        "attempt_ordinal": 1,
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
            "package_replay_pass": True,
            "path_preregistration_pass": True,
            "resource_contract_pass": True,
            "slot_order_pass": True,
            "strict_inputs_replay_pass": True,
            "tool_identities_replay_pass": True,
        },
        "preselection_epoch_identity": identities["preselection"],
        "preselection_transcript_identity": preselection_transcript_identity,
        "prospective_manifest_identity": _detached(identities["manifest"]),
        "preregistration_sha256": "f" * 64,
        "purpose": "PROSPECTIVE_AB16_ORGANIC_ARM_PRE_RUN_AUTHORITY",
        "repository_head": "d" * 40,
        "repository_git_tool_identity": identities["git"],
        "repository_root": str(ROOT),
        "resource_contract": dict(LIFECYCLE.FORMAL_RESOURCE_CONTRACT),
        "run_nonce": "run-a",
        "runner_selection_path": str(selection_path),
        "schema_version": LIFECYCLE.PRE_RUN_AUTHORITY_SCHEMA,
        "seed": 2026072301,
        "slot": "region-capacity-ab-control",
        "solver_run_authorized": False,
        "status": "PASS",
        "strict_input_identities": {"strict": identities["strict"]},
        "suite_selection_identity": _detached(identities["suite-selection"]),
        "tool_identities": tool_identities,
        "unit_name": "cuts-ab16-region-capacity-ab-control.service",
        "verdict": "AB16_ORGANIC_PRE_RUN_AUTHORITY_PASS",
        "workers": 1,
    }
    LIFECYCLE.validate_pre_run_authority(pre_run)
    pre_run_identity = _detached(_write(pre_run_path, pre_run))
    selection = {
        "arm": "control",
        "arm_binding_identity": identities["binding"],
        "attempt_execution_identity": execution_identity,
        "attempt_dir": str(attempt),
        "attempt_ordinal": 1,
        "authority_chain": authority_chain,
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": True,
            "production_certified_authorized": False,
            "solver_run_authorized": True,
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
        "manifest_identity": _detached(identities["manifest"]),
        "order": "ab",
        "pre_run_authority_identity": pre_run_identity,
        "preregistration_sha256": "f" * 64,
        "purpose": "prospective_noncert_cuts_ab16_formal_arm",
        "repository_head": "d" * 40,
        "repository_git_tool_identity": identities["git"],
        "repository_root": str(ROOT),
        "run_nonce": "run-a",
        "schema_version": LIFECYCLE.RUNNER_SELECTION_SCHEMA,
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
    **adapter_kwargs: object,
) -> tuple[Path, dict[str, object]]:
    exit_code = adapter_kwargs.get("payload_exit_code", 0)
    assert type(exit_code) is int
    attempt, pre_run_path, selection_path = _fixture(
        tmp_path,
        postseal_failure_exit_code=exit_code,
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


def test_two_stage_success_and_detached_replay(tmp_path: Path) -> None:
    attempt, result = _run(tmp_path)
    assert result["status"] == "PASS"
    assert result["verdict"] == "RESOURCE_TERMINAL_CLEANUP_REPLAY_PASS"
    assert result["authorizations"]["global_claim_authorized"] is False
    assert (attempt / "detached-replay.json").is_file()
    terminal = VERIFIER.snapshot_json(attempt / "terminal-envelope.json").value
    cleanup = VERIFIER.snapshot_json(attempt / "cleanup.json").value
    assert terminal["systemd_raw"]["ControlGroup"] == ""
    assert cleanup["cgroup_path_exists"] is False
    assert cleanup["unit_load_state"] == "not-found"


def test_every_live_phase_binds_fresh_double_round_epoch_transcript(
    tmp_path: Path,
) -> None:
    attempt, _result = _run(tmp_path)
    pre_run = VERIFIER.snapshot_json(attempt / "pre-run-authority.json").value
    for phase in (
        "launch",
        "preterminal",
        "release",
        "terminal",
        "cleanup",
        "detached-replay",
    ):
        observation = VERIFIER.snapshot_json(Path(pre_run["epoch_observation_paths"][phase])).value
        transcript = VERIFIER.snapshot_json(Path(pre_run["epoch_transcript_paths"][phase]))
        assert observation["phase"] == phase
        assert observation["observed_epoch"] == pre_run["manager_epoch"]
        assert observation["capture_transcript_identity"] == transcript.identity
        assert [item["round_index"] for item in transcript.value["rounds"]] == [
            1,
            2,
        ]
        MANAGER_AUTHORITY.validate_manager_epoch_capture_transcript(
            transcript.value,
            expected_epoch=pre_run["manager_epoch"],
        )


def test_postseal_payload_failure_is_not_hidden_by_keeper(tmp_path: Path) -> None:
    attempt, result = _run(tmp_path, payload_exit_code=7)
    assert result["status"] == "PASS"
    assert result["verdict"] == "EXPECTED_POST_SEAL_FAILURE_REPLAY_PASS"
    assert (attempt / "release-token.json").is_file()
    assert (attempt / "terminal-envelope.json").is_file()
    assert (attempt / "cleanup.json").is_file()
    assert (attempt / "detached-replay.json").is_file()


def test_unregistered_payload_failure_still_fails_closed(tmp_path: Path) -> None:
    attempt, pre_run, selection = _fixture(tmp_path)
    with pytest.raises(Exception, match="differs from preregistration"):
        ORCHESTRATOR.orchestrate_with_adapter(
            pre_run_path=pre_run,
            selection_path=selection,
            adapter=FakeAdapter(
                attempt_dir=attempt,
                slot="region-capacity-ab-control",
                payload_exit_code=7,
            ),
        )
    assert not (attempt / "release-token.json").exists()
    assert not (attempt / "detached-replay.json").exists()


@pytest.mark.parametrize(
    "adapter_kwargs",
    [
        {"epoch_drift_phase": "preterminal"},
        {"oom_kill": 1},
        {"memory_max_adjustment": -1},
    ],
)
def test_post_launch_failure_stops_selected_unit_and_proves_cleanup(
    tmp_path: Path,
    adapter_kwargs: dict[str, object],
) -> None:
    attempt, pre_run, selection = _fixture(tmp_path)
    adapter = FakeAdapter(
        attempt_dir=attempt,
        slot="region-capacity-ab-control",
        **adapter_kwargs,
    )
    with pytest.raises(Exception):
        ORCHESTRATOR.orchestrate_with_adapter(
            pre_run_path=pre_run,
            selection_path=selection,
            adapter=adapter,
        )
    assert adapter.abort_count == 1
    cleanup = VERIFIER.snapshot_json(attempt / "cleanup.json").value
    assert cleanup["schema_version"] == "noncert-cuts-ab16-abort-cleanup-v1"
    assert cleanup["status"] == "PASS"
    assert cleanup["verdict"] == "SELECTED_UNIT_ABORT_CLEANUP_PASS"
    assert cleanup["authorizations"]["runtime_effect_authorized"] is False


def test_post_launch_failure_without_cleanup_proof_is_incomplete(
    tmp_path: Path,
) -> None:
    attempt, pre_run, selection = _fixture(tmp_path)
    adapter = FakeAdapter(
        attempt_dir=attempt,
        slot="region-capacity-ab-control",
        oom_kill=1,
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
    assert adapter.abort_count == 1
    assert not (attempt / "cleanup.json").exists()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"epoch_drift_phase": "preterminal"}, "epoch drift"),
        ({"transcript_drift_phase": "preterminal"}, "transcript semantic"),
        ({"terminal_invocation_drift": True}, "terminal status"),
        ({"oom_kill": 1}, "OOM event"),
        ({"memory_max_adjustment": -1}, "resource contract"),
        ({"collect_mode": "inactive"}, "preterminal supervisor"),
        ({"cleanup_residual": True}, "cleanup did not prove"),
    ],
)
def test_lifecycle_mutations_fail_closed(
    tmp_path: Path,
    kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(Exception, match=message):
        _run(tmp_path, **kwargs)


def test_pre_run_tool_and_selection_join_mutations_fail(tmp_path: Path) -> None:
    _attempt, pre_run_path, selection_path = _fixture(tmp_path)
    pre_run = copy.deepcopy(VERIFIER.snapshot_json(pre_run_path).value)
    pre_run["tool_identities"]["organic_resource_verifier"]["sha256"] = "0" * 64
    with pytest.raises(VERIFIER.VerificationError, match="tool"):
        VERIFIER.validate_pre_run_authority(pre_run)
    original_pre_run = VERIFIER.snapshot_json(pre_run_path)
    selection = copy.deepcopy(VERIFIER.snapshot_json(selection_path).value)
    selection["pre_run_authority_identity"]["sha256"] = "1" * 64
    with pytest.raises(VERIFIER.VerificationError, match="pre-run identity"):
        VERIFIER._validate_selection(
            selection,
            pre_run=original_pre_run.value,
            pre_run_identity=original_pre_run.identity,
        )


def test_preselection_transcript_semantics_fail_closed(tmp_path: Path) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = copy.deepcopy(VERIFIER.snapshot_json(pre_run_path).value)
    original_transcript = VERIFIER.snapshot_json(pre_run["preselection_transcript_identity"]["path"]).value
    mutated_transcript = copy.deepcopy(original_transcript)
    mutated_transcript["rounds"][0]["round_index"] = 99
    mutated_transcript_identity = _write(
        tmp_path / "authority/mutated-preselection-transcript.json",
        mutated_transcript,
    )
    mutated_observation = LIFECYCLE.build_epoch_observation(
        phase="preselection",
        slot=pre_run["slot"],
        observed_epoch=pre_run["manager_epoch"],
        observed_at_monotonic_ns=101,
        capture_transcript_identity=mutated_transcript_identity,
    )
    pre_run["preselection_transcript_identity"] = mutated_transcript_identity
    pre_run["preselection_epoch_identity"] = _write(
        tmp_path / "authority/mutated-preselection-observation.json",
        mutated_observation,
    )
    with pytest.raises(
        VERIFIER.VerificationError,
        match="transcript semantic replay",
    ):
        VERIFIER.validate_pre_run_authority(pre_run)


@pytest.mark.parametrize(
    ("field", "mutation", "message"),
    [
        ("repository_root", "relative/path", "repository root"),
    ],
)
def test_pre_run_repository_and_execution_mutations_fail_closed(
    tmp_path: Path,
    field: str,
    mutation: object,
    message: str,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = copy.deepcopy(VERIFIER.snapshot_json(pre_run_path).value)
    pre_run[field] = mutation
    with pytest.raises(VERIFIER.VerificationError, match=message):
        VERIFIER.validate_pre_run_authority(pre_run)


def test_resource_contract_constants_and_systemd_argv_are_exact() -> None:
    assert LIFECYCLE.FORMAL_RESOURCE_CONTRACT == {
        "collect_mode": "inactive-or-failed",
        "kill_mode": "control-group",
        "memory_high_bytes": 35 * 1024**3,
        "memory_max_bytes": 39 * 1024**3,
        "memory_swap_max_bytes": 16 * 1024**3,
        "oom_policy": "continue",
        "runtime_max_seconds": 3600,
        "send_sigkill": True,
        "single_worker": True,
    }
    assert VERIFIER.FORMAL_RESOURCE_CONTRACT == LIFECYCLE.FORMAL_RESOURCE_CONTRACT
    formal_argv = LIFECYCLE.build_systemd_run_argv(
        systemd_run_path="/usr/bin/systemd-run",
        unit_name="cuts-ab16-formal-fixture.service",
        supervisor_argv=["/python", "-I", "/supervisor.py"],
        resource_contract=LIFECYCLE.FORMAL_RESOURCE_CONTRACT,
        execution_class="FORMAL_AB16",
    )
    assert "--property=RuntimeMaxSec=3600" in formal_argv
    assert "--property=CollectMode=inactive-or-failed" in formal_argv


@pytest.mark.parametrize("field", ["send_sigkill", "single_worker"])
def test_resource_contract_rejects_boolean_integer_alias(
    tmp_path: Path,
    field: str,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = copy.deepcopy(VERIFIER.snapshot_json(pre_run_path).value)
    pre_run["resource_contract"][field] = 1
    with pytest.raises(
        VERIFIER.VerificationError,
        match="exact boolean",
    ):
        VERIFIER.validate_pre_run_authority(pre_run)
    with pytest.raises(
        LIFECYCLE.LifecycleError,
        match="exact boolean",
    ):
        LIFECYCLE.validate_pre_run_authority(pre_run)


def test_pre_run_launch_tool_join_and_selection_payload_join_fail_closed(
    tmp_path: Path,
) -> None:
    _attempt, pre_run_path, selection_path = _fixture(tmp_path)
    pre_run_snapshot = VERIFIER.snapshot_json(pre_run_path)
    pre_run = copy.deepcopy(pre_run_snapshot.value)
    pre_run["launch"]["systemctl_path"] = pre_run["launch"]["systemd_run_path"]
    with pytest.raises(VERIFIER.VerificationError, match="systemctl_path"):
        VERIFIER.validate_pre_run_authority(pre_run)
    selection = copy.deepcopy(VERIFIER.snapshot_json(selection_path).value)
    selection["expected_payload_status"]["exit_code"] = 3
    with pytest.raises(
        VERIFIER.VerificationError,
        match="expected_payload_status",
    ):
        VERIFIER._validate_selection(
            selection,
            pre_run=pre_run_snapshot.value,
            pre_run_identity=pre_run_snapshot.identity,
        )


def test_pinned_launch_environment_semantics_fail_closed(tmp_path: Path) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = copy.deepcopy(VERIFIER.snapshot_json(pre_run_path).value)
    environment = copy.deepcopy(VERIFIER.snapshot_json(pre_run["launch"]["environment_identity"]["path"]).value)
    environment["variables"]["PYTHONHASHSEED"] = "random"
    pre_run["launch"]["environment_identity"] = _write(
        tmp_path / "authority/mutated-environment.json",
        environment,
    )
    with pytest.raises(
        VERIFIER.VerificationError,
        match="fixed values",
    ):
        VERIFIER.validate_pre_run_authority(pre_run)


def test_live_adapter_passes_only_pinned_environment_to_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = VERIFIER.snapshot_json(pre_run_path).value
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(
        argv: Sequence[str],
        **kwargs: object,
    ) -> SimpleNamespace:
        calls.append((list(argv), dict(kwargs)))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setenv("AB16_UNPINNED_SECRET", "must-not-propagate")
    adapter = ORCHESTRATOR.SubprocessLifecycleAdapter(
        pre_run=pre_run,
        epoch_observer=lambda _phase: pytest.fail("epoch observer was called"),
        run=fake_run,
    )
    adapter._run(  # noqa: SLF001
        [str(pre_run["launch"]["systemctl_path"]), "--version"],
        timeout=1,
    )
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv == [pre_run["launch"]["systemctl_path"], "--version"]
    assert Path(argv[0]).is_absolute()
    assert "pass_fds" not in kwargs
    assert "executable" not in kwargs
    assert kwargs["close_fds"] is True
    assert kwargs["env"] == {
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
        "HOME": "/home/fixture",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "TZ": "UTC",
        "XDG_RUNTIME_DIR": "/run/user/1000",
    }
    assert "AB16_UNPINNED_SECRET" not in kwargs["env"]


@pytest.mark.parametrize(
    ("role", "launch_field"),
    [
        ("systemctl", "systemctl_path"),
        ("systemd_run", "systemd_run_path"),
    ],
)
def test_live_adapter_uses_pinned_absolute_path_as_argv0(
    tmp_path: Path,
    role: str,
    launch_field: str,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = VERIFIER.snapshot_json(pre_run_path).value
    pinned_path = pre_run["launch"][launch_field]
    observed_argv: list[list[str]] = []

    def fake_run(
        argv: Sequence[str],
        **_kwargs: object,
    ) -> SimpleNamespace:
        observed_argv.append(list(argv))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    assert pre_run["tool_identities"][role]["path"] == pinned_path
    assert Path(pinned_path).name not in {"systemctl", "systemd-run"}
    assert Path(pinned_path).is_absolute()
    adapter = ORCHESTRATOR.SubprocessLifecycleAdapter(
        pre_run=pre_run,
        epoch_observer=lambda _phase: pytest.fail("epoch observer was called"),
        run=fake_run,
    )
    adapter._run([pinned_path, "--fixture-probe"], timeout=1)  # noqa: SLF001
    assert observed_argv == [[pinned_path, "--fixture-probe"]]


def test_live_adapter_rejects_prelaunch_executable_byte_drift(
    tmp_path: Path,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = VERIFIER.snapshot_json(pre_run_path).value
    executable = Path(pre_run["launch"]["systemctl_path"])
    executable.chmod(0o644)
    executable.write_bytes(b"ordinary prelaunch package drift")

    adapter = ORCHESTRATOR.SubprocessLifecycleAdapter(
        pre_run=pre_run,
        epoch_observer=lambda _phase: pytest.fail("epoch observer was called"),
        run=lambda *_args, **_kwargs: pytest.fail("drifted executable was launched"),
    )
    with pytest.raises(
        ORCHESTRATOR.OrchestratorError,
        match="ordinary-user executable byte identity drifted",
    ):
        adapter._run([str(executable), "--version"], timeout=1)  # noqa: SLF001


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        (OSError("fixture exec failure"), "systemctl command execution failed"),
        (
            ORCHESTRATOR.subprocess.TimeoutExpired(cmd=["fixture-systemctl"], timeout=1),
            "systemctl command execution failed",
        ),
        (
            SimpleNamespace(returncode=23, stdout=b"", stderr=b"fixture failure"),
            r"ordinary-user command failed \(23\)",
        ),
    ],
)
def test_live_adapter_reports_ordinary_command_failures(
    tmp_path: Path,
    outcome: object,
    message: str,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = VERIFIER.snapshot_json(pre_run_path).value
    executable = Path(pre_run["launch"]["systemctl_path"])

    def failing_run(
        _argv: Sequence[str],
        **_kwargs: object,
    ) -> SimpleNamespace:
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, SimpleNamespace)
        return outcome

    adapter = ORCHESTRATOR.SubprocessLifecycleAdapter(
        pre_run=pre_run,
        epoch_observer=lambda _phase: pytest.fail("epoch observer was called"),
        run=failing_run,
    )
    with pytest.raises(
        ORCHESTRATOR.OrchestratorError,
        match=message,
    ):
        adapter._run([str(executable), "--version"], timeout=1)  # noqa: SLF001


@pytest.mark.parametrize(
    ("role", "launch_field"),
    [
        ("systemctl", "systemctl_path"),
        ("systemd_run", "systemd_run_path"),
    ],
)
def test_live_adapter_runs_a_small_local_fixture_binary_for_each_system_tool(
    tmp_path: Path,
    role: str,
    launch_field: str,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = copy.deepcopy(VERIFIER.snapshot_json(pre_run_path).value)
    executable = tmp_path / f"fixture-true-{role}"
    executable.write_bytes(Path("/usr/bin/true").read_bytes())
    executable.chmod(0o555)
    identity = _tool_identity(executable)
    pre_run["launch"][launch_field] = str(executable)
    pre_run["tool_identities"][role] = identity
    adapter = ORCHESTRATOR.SubprocessLifecycleAdapter(
        pre_run=pre_run,
        epoch_observer=lambda _phase: pytest.fail("epoch observer was called"),
    )
    completed = adapter._run([str(executable)], timeout=5)  # noqa: SLF001
    assert completed.returncode == 0


def test_epoch_attestor_capture_uses_pinned_environment_and_restores_ambient(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _attempt, pre_run_path, _selection_path = _fixture(tmp_path)
    pre_run = VERIFIER.snapshot_json(pre_run_path).value
    transcript = VERIFIER.snapshot_json(pre_run["preselection_transcript_identity"]["path"]).value
    captured_environments: list[dict[str, str]] = []

    def capture_manager_epoch_with_transcript(**kwargs: str) -> dict[str, object]:
        assert kwargs == {
            "attestor_path": pre_run["tool_identities"]["manager_attestor"]["path"],
            "busctl_path": pre_run["tool_identities"]["busctl"]["path"],
            "python_path": pre_run["tool_identities"]["python3_13"]["path"],
            "sudo_path": pre_run["tool_identities"]["sudo"]["path"],
        }
        captured_environments.append(dict(ORCHESTRATOR.os.environ))
        return {
            "manager_epoch": copy.deepcopy(pre_run["manager_epoch"]),
            "transcript": copy.deepcopy(transcript),
        }

    fake_authority = SimpleNamespace(
        capture_manager_epoch_with_transcript=capture_manager_epoch_with_transcript,
        validate_manager_epoch=lambda _value: None,
        validate_manager_epoch_capture_transcript=lambda _value, **_kwargs: None,
    )
    monkeypatch.setattr(
        ORCHESTRATOR,
        "_load_pinned_module",
        lambda *_args, **_kwargs: fake_authority,
    )
    monkeypatch.setenv("AB16_UNPINNED_SECRET", "must-be-restored-only")
    observer = ORCHESTRATOR.build_pinned_epoch_observer(pre_run)
    capture = observer("launch")
    assert capture.manager_epoch == pre_run["manager_epoch"]
    assert captured_environments == [
        {
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
            "HOME": "/home/fixture",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": "/usr/bin:/bin",
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "XDG_RUNTIME_DIR": "/run/user/1000",
        }
    ]
    assert ORCHESTRATOR.os.environ["AB16_UNPINNED_SECRET"] == "must-be-restored-only"


def test_same_fd_reader_rejects_hardlink_and_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    _write(source, {"value": 1})
    hardlink = tmp_path / "hardlink.json"
    hardlink.hardlink_to(source)
    with pytest.raises(LIFECYCLE.LifecycleError, match="regular file"):
        LIFECYCLE.snapshot_regular(source)
    target = tmp_path / "target.json"
    target.symlink_to(source)
    with pytest.raises(VERIFIER.VerificationError, match="symlink"):
        VERIFIER.snapshot_json(target)


def test_dirfd_walk_rejects_symlinked_parent_for_reads_and_writes(
    tmp_path: Path,
) -> None:
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    source = real_parent / "source.json"
    _write(source, {"value": 1})
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    linked_source = linked_parent / "source.json"
    for snapshot, error in (
        (LIFECYCLE.snapshot_regular, LIFECYCLE.LifecycleError),
        (VERIFIER.snapshot_json, VERIFIER.VerificationError),
        (ORCHESTRATOR.snapshot_bytes, ORCHESTRATOR.OrchestratorError),
    ):
        with pytest.raises(error, match="symlink"):
            snapshot(linked_source)
    with pytest.raises(LIFECYCLE.LifecycleError, match="symlink"):
        LIFECYCLE.write_json_exclusive(
            linked_parent / "lifecycle-output.json",
            {"value": 2},
        )
    with pytest.raises(VERIFIER.VerificationError, match="symlink"):
        VERIFIER.write_exclusive(
            linked_parent / "verifier-output.json",
            {"value": 3},
        )
    assert not (real_parent / "lifecycle-output.json").exists()
    assert not (real_parent / "verifier-output.json").exists()


def test_same_fd_reader_rejects_mid_read_metadata_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "mutable.json"
    _write(source, {"value": 1})
    original_read = LIFECYCLE.os.read
    changed = False

    def mutating_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        chunk = original_read(descriptor, size)
        if chunk and not changed:
            changed = True
            source.chmod(0o644)
        return chunk

    monkeypatch.setattr(LIFECYCLE.os, "read", mutating_read)
    with pytest.raises(LIFECYCLE.LifecycleError, match="changed during same-FD"):
        LIFECYCLE.snapshot_regular(source)


@pytest.mark.parametrize("payload_exit_code", [0, 7])
def test_ordinary_user_supervisor_writes_inner_and_waits_for_pass_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload_exit_code: int,
) -> None:
    attempt, pre_run_path, selection_path = _fixture(
        tmp_path,
        postseal_failure_exit_code=payload_exit_code,
    )
    pre_run_snapshot = LIFECYCLE.snapshot_regular(pre_run_path)
    selection_snapshot = LIFECYCLE.snapshot_regular(selection_path)
    pre_run = LIFECYCLE.strict_loads(pre_run_snapshot.raw, "pre-run")
    transcript = VERIFIER.snapshot_json(pre_run["preselection_transcript_identity"]["path"]).value
    launch_transcript_identity = _write(
        Path(pre_run["epoch_transcript_paths"]["launch"]),
        transcript,
    )
    launch_epoch = LIFECYCLE.build_epoch_observation(
        phase="launch",
        slot=pre_run["slot"],
        observed_epoch=pre_run["manager_epoch"],
        observed_at_monotonic_ns=150,
        capture_transcript_identity=launch_transcript_identity,
    )
    _write(attempt / "manager-epoch-launch.json", launch_epoch)
    _write(
        attempt / "result.json",
        {
            "schema_version": "noncert-cuts-ab16-organic-arm-result-v1",
            "slot": pre_run["slot"],
            "status": "UNKNOWN",
        },
    )

    class FakeProcess:
        pid = 9191
        returncode = payload_exit_code
        reaped = False

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            self.reaped = True
            return payload_exit_code

        def send_signal(self, value: int) -> None:
            raise AssertionError(f"unexpected signal {value}")

        def kill(self) -> None:
            raise AssertionError("unexpected kill")

    process = FakeProcess()
    observed_popen: dict[str, object] = {}
    clock = {"value": 200}

    def monotonic_ns() -> int:
        clock["value"] += 10
        return clock["value"]

    def proc_starttime(pid: int) -> int | None:
        if pid == LIFECYCLE.os.getpid():
            return 77
        if pid == process.pid:
            return None if process.reaped else 78
        raise AssertionError(f"unexpected pid {pid}")

    def wait_without_reaping(
        pid: int,
        *,
        timeout_seconds: float,
        monotonic: object,
        sleep: object,
    ) -> object:
        del timeout_seconds, monotonic, sleep
        assert pid == process.pid
        return SimpleNamespace(
            si_code=LIFECYCLE.os.CLD_EXITED,
            si_status=payload_exit_code,
        )

    def release_on_sleep(_seconds: float) -> None:
        inner_path = attempt / "inner-lifecycle.json"
        release_path = attempt / "release-token.json"
        if not inner_path.exists() or release_path.exists():
            return
        inner_identity = _identity(inner_path)
        resource = {
            "inner_identity": _detached(inner_identity),
            "schema_version": "noncert-cuts-ab16-resource-verification-v1",
            "status": "PASS",
            "verdict": LIFECYCLE._expected_resource_verdict(pre_run),  # noqa: SLF001
        }
        resource_identity = _write(
            attempt / "independent-resource-verification.json",
            resource,
        )
        _write(
            release_path,
            {
                "campaign_id": pre_run["campaign_id"],
                "invocation_id": "0123456789abcdef0123456789abcdef",
                "keeper_pid": LIFECYCLE.os.getpid(),
                "keeper_starttime": 77,
                "pre_run_authority_identity": pre_run_snapshot.identity,
                "resource_verification_identity": resource_identity,
                "run_nonce": pre_run["run_nonce"],
                "runner_selection_identity": selection_snapshot.identity,
                "schema_version": "noncert-cuts-ab16-release-token-v1",
                "slot": pre_run["slot"],
                "unit_name": pre_run["unit_name"],
                "verdict": LIFECYCLE._expected_resource_verdict(pre_run),  # noqa: SLF001
            },
        )

    def fake_popen(*args: object, **kwargs: object) -> FakeProcess:
        observed_popen["args"] = args
        observed_popen["kwargs"] = kwargs
        return process

    monkeypatch.setenv("INVOCATION_ID", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(LIFECYCLE.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(LIFECYCLE.os, "getuid", lambda: 1000)
    result = LIFECYCLE.supervise_payload(
        pre_run_path=pre_run_path,
        selection_path=selection_path,
        popen=fake_popen,
        monotonic=lambda: 1.0,
        monotonic_ns=monotonic_ns,
        sleep=release_on_sleep,
        proc_starttime=proc_starttime,
        wait_without_reaping=wait_without_reaping,
    )
    assert result == payload_exit_code
    inner = VERIFIER.snapshot_json(attempt / "inner-lifecycle.json").value
    assert inner["payload_reaped"] is True
    assert inner["keeper_pid"] == LIFECYCLE.os.getpid()
    popen_kwargs = observed_popen["kwargs"]
    assert isinstance(popen_kwargs, dict)
    assert popen_kwargs["env"] == {
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
        "HOME": "/home/fixture",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "TZ": "UTC",
        "XDG_RUNTIME_DIR": "/run/user/1000",
    }
