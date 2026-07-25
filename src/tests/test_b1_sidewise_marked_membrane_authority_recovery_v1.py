from __future__ import annotations

import copy
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
from typing import Any, Callable

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724"
ATTESTOR_PATH = RESEARCH / "privileged_manager_exe_attestor_v1.py"


def _load(filename: str) -> ModuleType:
    path = RESEARCH / filename
    name = f"_test_smm3_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def manager() -> ModuleType:
    return _load("manager_epoch_authority_v1.py")


@pytest.fixture(scope="module")
def verifier() -> ModuleType:
    return _load("verify_smm3_two_stage_v1.py")


@pytest.fixture(scope="module")
def recovery() -> ModuleType:
    return _load("run_smm3_authority_recovery_v1.py")


@pytest.fixture(scope="module")
def attempt_runner() -> ModuleType:
    return _load("run_smm3_two_stage_attempt_v1.py")


def _sha(character: str) -> str:
    return character * 64


def _tool_identity(
    path: str,
    digest_character: str,
    *,
    mode: int,
    device: int,
    inode: int,
) -> dict[str, Any]:
    return {
        "requested_path": path,
        "path": path,
        "size_bytes": 4096 + inode,
        "mode": mode,
        "mode_octal": f"{mode:04o}",
        "sha256": _sha(digest_character),
        "device": device,
        "inode": inode,
    }


def _epoch() -> dict[str, Any]:
    return {
        "schema": "systemd-user-manager-boot-epoch-v1",
        "boot_id": "01234567-89ab-cdef-0123-456789abcdef",
        "dbus_unique_owner": ":1.42",
        "manager_pid": 2118,
        "manager_pid_starttime": 3154,
        "manager_version": "261.1-1-arch",
        "manager_features": "+PAM +AUDIT +SELINUX",
        "manager_executable": {
            "path": "/usr/lib/systemd/systemd",
            "size_bytes": 2_000_000,
            "mode": 0o755,
            "mode_octal": "0755",
            "sha256": ("de79adab851d295b6a6d403d03552bf16f0f51642f4f7da07bf0e9c139719953"),
            "device": 259,
            "inode": 9001,
        },
        "observation_toolchain": {
            "busctl": _tool_identity(
                "/usr/bin/busctl",
                "e",
                mode=0o755,
                device=259,
                inode=9005,
            ),
        },
        "attestation_toolchain": {
            "attestor": _tool_identity(
                str(ATTESTOR_PATH),
                "a",
                mode=0o644,
                device=259,
                inode=9002,
            ),
            "sudo": _tool_identity(
                "/usr/bin/sudo",
                "b",
                mode=0o4755,
                device=259,
                inode=9003,
            ),
            "python": _tool_identity(
                "/usr/bin/python3.14",
                "c",
                mode=0o755,
                device=259,
                inode=9004,
            ),
        },
    }


def _json_identity(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    metadata = path.stat()
    return {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "mode_octal": f"{metadata.st_mode & 0o7777:04o}",
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "link_count": metadata.st_nlink,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )
    return _json_identity(path)


def _resource_contract() -> dict[str, Any]:
    return {
        "memory_high_bytes": 35 * 1024**3,
        "memory_max_bytes": 39 * 1024**3,
        "memory_swap_max_bytes": 16 * 1024**3,
        "oom_policy": "continue",
        "kill_mode": "control-group",
        "send_sigkill": "yes",
        "single_worker": True,
        "proof_limit_bytes": 5_000_000_000,
        "artifact_low_water_bytes": 10 * 1024**3,
        "required_free_before_formal_bytes": 10 * 1024**3 + 5_000_000_000,
        "formal_attempt_limit": 1,
        "formal_runtime_max_seconds": 9000,
        "formal_payload_wait_seconds": 8000,
        "formal_keeper_timeout_seconds": 8700,
        "formal_roundingsat_time_limit_seconds": 3600,
        "formal_roundingsat_monitor_limit_seconds": 3900,
        "formal_veripb_time_limit_seconds": 3600,
    }


def _timing_contract(*, formal: bool = False) -> dict[str, int]:
    return {
        "runtime_max_seconds": 9000 if formal else 120,
        "payload_wait_seconds": 8000 if formal else 30,
        "keeper_timeout_seconds": 8700 if formal else 90,
        "roundingsat_time_limit_seconds": 3600,
        "roundingsat_monitor_limit_seconds": 3900,
        "veripb_time_limit_seconds": 3600,
    }


def _lifecycle(
    verifier: ModuleType,
    *,
    postseal_failure: bool = False,
) -> dict[str, dict[str, Any]]:
    epoch = _epoch()
    nonce = "smm3-fixture-0001"
    unit = "b1-smm3-fixture-0001.service"
    attempt = "synthetic-postseal-fail-a001" if postseal_failure else "synthetic-success-a001"
    invocation = "1" * 32
    supervisor = 1001
    payload = 1002
    contract = _resource_contract()
    timing = _timing_contract()
    purpose = "synthetic_postseal_failure" if postseal_failure else "synthetic_success"
    runtime_usec = timing["runtime_max_seconds"] * 1_000_000
    cgroup_path = "/sys/fs/cgroup/user.slice/test-fixture.service"
    control_group = "/user.slice/test-fixture.service"
    authority = {
        "schema_version": verifier.AUTHORITY_SCHEMA,
        "status": "PRE_RUN_AUTHORITY_PASS",
        "run_nonce": nonce,
        "manager_epoch": copy.deepcopy(epoch),
        "resource_contract": copy.deepcopy(contract),
        "binaries": {
            "systemctl": {
                "path": "/usr/bin/systemctl",
            },
        },
    }
    selection = {
        "schema_version": verifier.SELECTION_SCHEMA,
        "status": "SELECTED_CONSUMED",
        "run_nonce": nonce,
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "manager_epoch": copy.deepcopy(epoch),
        "resource_contract": copy.deepcopy(contract),
        "timing_contract": copy.deepcopy(timing),
        "formal_admission": None,
        "upper_bound_update_authorized": False,
    }
    initial_systemd_raw = {
        "ActiveState": "active\n",
        "SubState": "running\n",
        "MainPID": f"{supervisor}\n",
        "InvocationID": f"{invocation}\n",
        "ControlGroup": f"{control_group}\n",
        "MemoryHigh": f"{35 * 1024**3}\n",
        "MemoryMax": f"{39 * 1024**3}\n",
        "MemorySwapMax": f"{16 * 1024**3}\n",
        "OOMPolicy": "continue\n",
        "KillMode": "control-group\n",
        "SendSIGKILL": "yes\n",
        "RuntimeMaxUSec": f"{runtime_usec}\n",
    }
    initial_cgroup_raw = {
        "memory.high": f"{35 * 1024**3}\n",
        "memory.max": f"{39 * 1024**3}\n",
        "memory.swap.max": f"{16 * 1024**3}\n",
        "memory.current": "2097152\n",
        "memory.peak": "2097152\n",
        "memory.swap.current": "0\n",
        "memory.swap.peak": "0\n",
        "memory.events": ("low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n"),
        "memory.events.local": ("low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n"),
        "cgroup.procs": f"{supervisor}\n{payload}\n",
        "cgroup.events": "populated 1\nfrozen 0\n",
    }
    launch = {
        "schema_version": verifier.LAUNCH_SCHEMA,
        "status": "LAUNCHED",
        "run_nonce": nonce,
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "invocation_id": invocation,
        "manager_epoch": copy.deepcopy(epoch),
        "resource_contract": copy.deepcopy(contract),
        "timing_contract": copy.deepcopy(timing),
        "supervisor_pid": supervisor,
        "payload_pid": payload,
        "pid_starttimes": {
            str(supervisor): 50_001,
            str(payload): 50_002,
        },
        "initial_systemd_raw": initial_systemd_raw,
        "initial_cgroup_path": cgroup_path,
        "initial_cgroup_raw": initial_cgroup_raw,
        "upper_bound_update_authorized": False,
    }
    payload_terminal = {
        "schema_version": verifier.PAYLOAD_TERMINAL_SCHEMA,
        "run_nonce": nonce,
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "invocation_id": invocation,
        "manager_epoch": copy.deepcopy(epoch),
        "resource_contract": copy.deepcopy(contract),
        "timing_contract": copy.deepcopy(timing),
        "supervisor_pid": supervisor,
        "payload_pid": payload,
        "keeper_pid": supervisor,
        "payload_reaped": True,
        "supervisor_role": "keeper",
        "waitid": {
            "si_pid": payload,
            "si_uid": 1000,
            "si_signo": int(verifier.signal.SIGCHLD),
            "si_status": 7 if postseal_failure else 0,
            "si_code": int(verifier.os.CLD_EXITED),
        },
        "waitpid": {
            "kind": "CLD_EXITED",
            "exit_code": 7 if postseal_failure else 0,
            "signal": None,
            "core_dumped": False,
        },
        "wait_status": {
            "code": "CLD_EXITED",
            "status": 7 if postseal_failure else 0,
        },
        "seal_written": True,
        "reaped_monotonic_ns": 300,
    }
    systemd_raw = {
        "ActiveState": "active\n",
        "SubState": "running\n",
        "MainPID": f"{supervisor}\n",
        "InvocationID": f"{invocation}\n",
        "ControlGroup": f"{control_group}\n",
        "MemoryHigh": f"{35 * 1024**3}\n",
        "MemoryMax": f"{39 * 1024**3}\n",
        "MemorySwapMax": f"{16 * 1024**3}\n",
        "OOMPolicy": "continue\n",
        "KillMode": "control-group\n",
        "SendSIGKILL": "yes\n",
        "RuntimeMaxUSec": f"{runtime_usec}\n",
    }
    cgroup_raw = {
        "memory.high": f"{35 * 1024**3}\n",
        "memory.max": f"{39 * 1024**3}\n",
        "memory.swap.max": f"{16 * 1024**3}\n",
        "memory.current": "1048576\n",
        "memory.peak": "2097152\n",
        "memory.swap.current": "0\n",
        "memory.swap.peak": "0\n",
        "memory.events": ("low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n"),
        "memory.events.local": ("low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n"),
        "cgroup.procs": f"{supervisor}\n",
        "cgroup.events": "populated 1\nfrozen 0\n",
    }
    preterminal = {
        "schema_version": verifier.PRETERMINAL_SCHEMA,
        "status": "PRETERMINAL_CAPTURED",
        "run_nonce": nonce,
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "invocation_id": invocation,
        "manager_epoch": copy.deepcopy(epoch),
        "resource_contract": copy.deepcopy(contract),
        "timing_contract": copy.deepcopy(timing),
        "supervisor_pid": supervisor,
        "payload_pid": payload,
        "keeper_pid": supervisor,
        "payload_reaped": True,
        "release_created": False,
        "systemd_raw": systemd_raw,
        "cgroup_path": cgroup_path,
        "cgroup_raw": cgroup_raw,
        "captured_monotonic_ns": 400,
        "upper_bound_update_authorized": False,
    }
    terminal_class = "postseal-failure" if postseal_failure else "success"
    terminal = {
        "schema_version": verifier.TERMINAL_SCHEMA,
        "status": "TERMINAL_CAPTURED",
        "run_nonce": nonce,
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "invocation_id": invocation,
        "manager_epoch": copy.deepcopy(epoch),
        "resource_contract": copy.deepcopy(contract),
        "timing_contract": copy.deepcopy(timing),
        "systemd_raw": {
            "ActiveState": ("failed\n" if postseal_failure else "active\n"),
            "SubState": ("failed\n" if postseal_failure else "exited\n"),
            "Result": ("exit-code\n" if postseal_failure else "success\n"),
            "ExecMainCode": "1\n",
            "ExecMainStatus": ("7\n" if postseal_failure else "0\n"),
            "MainPID": "0\n",
            "InvocationID": f"{invocation}\n",
            # systemd 261 may prune the empty cgroup before terminal capture.
            "ControlGroup": "\n",
            "MemoryHigh": f"{35 * 1024**3}\n",
            "MemoryMax": f"{39 * 1024**3}\n",
            "MemorySwapMax": f"{16 * 1024**3}\n",
            "OOMPolicy": "continue\n",
            "KillMode": "control-group\n",
            "SendSIGKILL": "yes\n",
            "RuntimeMaxUSec": f"{runtime_usec}\n",
        },
        "captured_monotonic_ns": 600,
        "upper_bound_update_authorized": False,
    }
    cleanup = {
        "schema_version": verifier.CLEANUP_SCHEMA,
        "status": "CLEANUP_CAPTURED",
        "run_nonce": nonce,
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "invocation_id": invocation,
        "manager_epoch": copy.deepcopy(epoch),
        "resource_contract": copy.deepcopy(contract),
        "timing_contract": copy.deepcopy(timing),
        "stop": {
            "argv": ["/usr/bin/systemctl", "--user", "stop", unit],
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
        },
        "reset_failed": {
            "argv": ["/usr/bin/systemctl", "--user", "reset-failed", unit],
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
        },
        "load_state": {
            "argv": [
                "/usr/bin/systemctl",
                "--user",
                "show",
                unit,
                "--property=LoadState",
                "--value",
            ],
            "exit_code": 0,
            "stdout": "not-found\n",
            "stderr": "",
        },
        "unit_absent": True,
        "checked_pids": [supervisor, payload],
        "pid_starttimes": {
            str(supervisor): 50_001,
            str(payload): 50_002,
        },
        "remaining_pids": [],
        "cgroup_path": cgroup_path,
        "cgroup_absent": True,
        "terminal_control_group_used_as_cleanup_evidence": False,
        "captured_monotonic_ns": 700,
        "upper_bound_update_authorized": False,
    }
    return {
        "authority": authority,
        "selection": selection,
        "launch": launch,
        "payload_terminal": payload_terminal,
        "preterminal": preterminal,
        "terminal": terminal,
        "cleanup": cleanup,
        "current_epoch": copy.deepcopy(epoch),
        "terminal_class": {"value": terminal_class},
    }


def _validate_lifecycle(
    verifier: ModuleType,
    fixture: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return verifier.validate_terminal_cleanup(
        fixture["authority"],
        fixture["selection"],
        fixture["launch"],
        fixture["payload_terminal"],
        fixture["preterminal"],
        fixture["terminal"],
        fixture["cleanup"],
        fixture["current_epoch"],
        expected_terminal=fixture["terminal_class"]["value"],
    )


def test_privileged_attestor_source_passes_narrow_ast_policy(
    manager: ModuleType,
) -> None:
    raw = ATTESTOR_PATH.read_bytes()
    audit = manager._audit_attestor_ast(raw)
    assert audit == {
        "policy": manager.AST_POLICY,
        "status": "PASS",
        "ast_node_count": audit["ast_node_count"],
        "source_size_bytes": len(raw),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
    }
    assert audit["ast_node_count"] > 1_000


@pytest.mark.parametrize(
    "injected",
    [
        b"\nimport subprocess\n",
        b"\nimport socket\n",
        b"\nimport signal\n",
        b"\nos.system('id')\n",
        b"\nos.kill(1, 0)\n",
        # Numeric flags must not provide a back door around the O_RDONLY-only
        # module-attribute whitelist.
        b"\nos.open('/tmp/forbidden-write', 1)\n",
    ],
)
def test_privileged_attestor_ast_rejects_process_network_signal_and_write(
    manager: ModuleType,
    injected: bytes,
) -> None:
    with pytest.raises(manager.ManagerEpochError):
        manager._audit_attestor_ast(ATTESTOR_PATH.read_bytes() + injected)


def test_privileged_invocation_fails_closed_on_sudo_failure_and_tool_drift(
    manager: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = ATTESTOR_PATH.read_bytes()
    tools = {
        "attestor": _tool_identity(
            str(ATTESTOR_PATH),
            "a",
            mode=0o644,
            device=1,
            inode=11,
        ),
        "sudo": _tool_identity(
            "/usr/bin/sudo",
            "b",
            mode=0o4755,
            device=1,
            inode=12,
        ),
        "python": _tool_identity(
            "/usr/bin/python3.14",
            "c",
            mode=0o755,
            device=1,
            inode=13,
        ),
    }
    ast_receipt = {
        "policy": manager.AST_POLICY,
        "status": "PASS",
        "ast_node_count": 1,
        "source_size_bytes": len(raw),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
    }

    monkeypatch.setattr(
        manager,
        "_tool_snapshots",
        lambda *_args: (raw, copy.deepcopy(tools), copy.deepcopy(ast_receipt)),
    )
    monkeypatch.setattr(
        manager.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout=b"",
            stderr=b"sudo: a password is required\n",
        ),
    )
    with pytest.raises(manager.ManagerEpochError, match="exited 1"):
        manager._invoke_privileged_attestor(
            _epoch(),
            sudo_path="/usr/bin/sudo",
            python_path="/usr/bin/python3.14",
            attestor_path=ATTESTOR_PATH,
        )

    snapshots = [
        (raw, copy.deepcopy(tools), copy.deepcopy(ast_receipt)),
        (raw, copy.deepcopy(tools), copy.deepcopy(ast_receipt)),
    ]
    snapshots[1][1]["sudo"]["sha256"] = _sha("d")
    monkeypatch.setattr(
        manager,
        "_tool_snapshots",
        lambda *_args: snapshots.pop(0),
    )
    monkeypatch.setattr(
        manager.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=b"{}\n",
            stderr=b"",
        ),
    )
    with pytest.raises(manager.ManagerEpochError, match="toolchain changed"):
        manager._invoke_privileged_attestor(
            _epoch(),
            sudo_path="/usr/bin/sudo",
            python_path="/usr/bin/python3.14",
            attestor_path=ATTESTOR_PATH,
        )


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("boot_id",), "fedcba98-7654-3210-fedc-ba9876543210"),
        (("dbus_unique_owner",), ":1.43"),
        (("manager_pid",), 2119),
        (("manager_pid_starttime",), 3155),
        (("manager_version",), "261.2"),
        (("manager_features",), "+PAM"),
        (("manager_executable", "path"), "/usr/lib/systemd/systemd-mutated"),
        (("manager_executable", "sha256"), _sha("d")),
        (("manager_executable", "device"), 260),
        (("manager_executable", "inode"), 9005),
        (("observation_toolchain", "busctl", "sha256"), _sha("d")),
        (("observation_toolchain", "busctl", "inode"), 9010),
        (("attestation_toolchain", "attestor", "sha256"), _sha("d")),
        (("attestation_toolchain", "sudo", "sha256"), _sha("d")),
        (("attestation_toolchain", "python", "sha256"), _sha("d")),
    ],
)
def test_manager_epoch_rejects_every_identity_and_toolchain_drift(
    manager: ModuleType,
    path: tuple[str, ...],
    replacement: Any,
) -> None:
    left = _epoch()
    right = copy.deepcopy(left)
    target: dict[str, Any] = right
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = replacement
    assert manager.same_epoch(left, left)
    assert not manager.same_epoch(left, right)


def test_manager_capture_rejects_owner_or_starttime_drift_around_attestor(
    manager: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = {
        key: value
        for key, value in _epoch().items()
        if key
        in {
            "boot_id",
            "dbus_unique_owner",
            "manager_pid",
            "manager_pid_starttime",
            "manager_version",
            "manager_features",
        }
    }
    second = copy.deepcopy(first)
    second["manager_pid_starttime"] += 1
    states = [first, second]
    monkeypatch.setattr(
        manager,
        "_user_manager_state",
        lambda _busctl_path: states.pop(0),
    )
    busctl = _tool_identity(
        "/usr/bin/busctl",
        "e",
        mode=0o755,
        device=259,
        inode=9005,
    )
    monkeypatch.setattr(
        manager,
        "_snapshot_path",
        lambda *_args, **_kwargs: (None, copy.deepcopy(busctl)),
    )
    monkeypatch.setattr(
        manager,
        "_invoke_privileged_attestor",
        lambda *_args, **_kwargs: (
            copy.deepcopy(_epoch()["manager_executable"]),
            {"privileged": "fixture"},
        ),
    )
    with pytest.raises(manager.ManagerEpochError, match="changed across"):
        manager._capture_once(
            sudo_path="/usr/bin/sudo",
            python_path="/usr/bin/python3.14",
            attestor_path=ATTESTOR_PATH,
            busctl_path="/usr/bin/busctl",
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("device", 260),
        ("inode", 9005),
        ("sha256", _sha("d")),
        ("observation_toolchain.busctl.sha256", _sha("d")),
    ],
)
def test_independent_verifier_epoch_join_includes_executable_inode_and_bytes(
    verifier: ModuleType,
    field: str,
    replacement: Any,
) -> None:
    left = _epoch()
    right = copy.deepcopy(left)
    if field == "observation_toolchain.busctl.sha256":
        right["observation_toolchain"]["busctl"]["sha256"] = replacement
    else:
        right["manager_executable"][field] = replacement
    assert verifier._same_epoch(left, left)
    assert not verifier._same_epoch(left, right)


@pytest.mark.parametrize("postseal_failure", [False, True])
def test_two_stage_synthetic_terminal_classes_validate_offline(
    verifier: ModuleType,
    postseal_failure: bool,
) -> None:
    fixture = _lifecycle(verifier, postseal_failure=postseal_failure)
    result = _validate_lifecycle(verifier, fixture)
    assert result["payload_exit_status"] == (7 if postseal_failure else 0)
    assert result["terminal_class"] == ("postseal-failure" if postseal_failure else "success")
    assert result["unit_absent"] is True
    assert result["cgroup_absent"] is True


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda value: value["preterminal"]["cgroup_raw"].__setitem__(
                "memory.max",
                "1\n",
            ),
            "memory.max mismatch",
        ),
        (
            lambda value: value["preterminal"]["cgroup_raw"].__setitem__(
                "memory.events",
                "low 0\nhigh 0\nmax 0\noom 1\noom_kill 0\noom_group_kill 0\n",
            ),
            "memory.events oom",
        ),
        (
            lambda value: value["authority"]["resource_contract"].__setitem__(
                "oom_policy",
                "stop",
            ),
            "oom_policy mismatch",
        ),
        (
            lambda value: value["authority"]["resource_contract"].__setitem__(
                "formal_veripb_time_limit_seconds",
                3599,
            ),
            "formal_veripb_time_limit_seconds mismatch",
        ),
        (
            lambda value: value["selection"]["timing_contract"].__setitem__(
                "runtime_max_seconds",
                119,
            ),
            "runtime_max_seconds mismatch",
        ),
        (
            lambda value: value["selection"].__setitem__(
                "upper_bound_update_authorized",
                True,
            ),
            "consumed non-authorizing",
        ),
        (
            lambda value: value["selection"].__setitem__(
                "status",
                "SELECTED",
            ),
            "consumed non-authorizing",
        ),
        (
            lambda value: value["launch"]["initial_systemd_raw"].__setitem__(
                "RuntimeMaxUSec",
                "119000000\n",
            ),
            "launch: raw RuntimeMaxUSec mismatch",
        ),
        (
            lambda value: value["launch"]["pid_starttimes"].pop("1002"),
            "PID starttime anchors are incomplete",
        ),
        (
            lambda value: value["payload_terminal"]["waitid"].__setitem__(
                "si_status",
                7,
            ),
            "waitid, waitpid, and wait_status",
        ),
        (
            lambda value: value["launch"].__setitem__(
                "invocation_id",
                "2" * 32,
            ),
            "InvocationID mismatch",
        ),
        (
            lambda value: value["preterminal"].__setitem__(
                "release_created",
                True,
            ),
            "release already existed",
        ),
        (
            lambda value: value["terminal"]["systemd_raw"].__setitem__(
                "Result",
                "exit-code\n",
            ),
            "Result mismatch",
        ),
        (
            lambda value: value["cleanup"].__setitem__(
                "remaining_pids",
                [1001],
            ),
            "remain",
        ),
        (
            lambda value: value["cleanup"]["stop"].__setitem__(
                "exit_code",
                1,
            ),
            "raw stop command result is invalid",
        ),
        (
            lambda value: value["selection"]["manager_epoch"].__setitem__(
                "dbus_unique_owner",
                ":1.99",
            ),
            "manager/boot epoch mismatch",
        ),
    ],
)
def test_two_stage_resource_epoch_release_terminal_and_cleanup_mutations_fail(
    verifier: ModuleType,
    mutator: Callable[[dict[str, dict[str, Any]]], None],
    match: str,
) -> None:
    fixture = _lifecycle(verifier)
    mutator(fixture)
    with pytest.raises(verifier.VerificationError, match=match):
        _validate_lifecycle(verifier, fixture)


def test_cleanup_accepts_exact_systemd_261_already_unloaded_reset(
    verifier: ModuleType,
) -> None:
    fixture = _lifecycle(verifier)
    unit = fixture["cleanup"]["unit"]
    fixture["cleanup"]["reset_failed"].update(
        {
            "exit_code": 1,
            "stdout": "",
            "stderr": (f"Failed to reset failed state of unit {unit}: Unit {unit} not loaded.\n"),
        }
    )
    _validate_lifecycle(verifier, fixture)


@pytest.mark.parametrize(
    "field,value",
    [
        ("stderr", "Unit missing\n"),
        ("stdout", "not-found\n"),
        ("exit_code", 2),
    ],
)
def test_cleanup_rejects_noncanonical_nonzero_reset(
    verifier: ModuleType,
    field: str,
    value: object,
) -> None:
    fixture = _lifecycle(verifier)
    unit = fixture["cleanup"]["unit"]
    fixture["cleanup"]["reset_failed"].update(
        {
            "exit_code": 1,
            "stdout": "",
            "stderr": (f"Failed to reset failed state of unit {unit}: Unit {unit} not loaded.\n"),
            field: value,
        }
    )
    with pytest.raises(
        verifier.VerificationError,
        match="raw reset_failed command result is invalid",
    ):
        _validate_lifecycle(verifier, fixture)


def test_common_identity_and_release_lifecycle_helpers_fail_closed(
    verifier: ModuleType,
    tmp_path: Path,
) -> None:
    path = tmp_path / "resource.json"
    expected = _write_json(
        path,
        {
            "schema_version": verifier.RESOURCE_RECEIPT_SCHEMA,
            "status": "PASS",
        },
    )
    payload, actual = verifier._load_json(path, "fixture resource")
    assert payload["status"] == "PASS"
    verifier._identity_matches(expected, actual, "fixture resource")
    drifted = copy.deepcopy(expected)
    drifted["sha256"] = _sha("d")
    with pytest.raises(verifier.VerificationError, match="sha256 identity"):
        verifier._identity_matches(drifted, actual, "fixture resource")

    fixture = _lifecycle(verifier)
    validation = verifier.validate_launch_and_preterminal(
        fixture["authority"],
        fixture["selection"],
        fixture["launch"],
        fixture["payload_terminal"],
        fixture["preterminal"],
        fixture["current_epoch"],
    )
    release = {
        "run_nonce": validation["run_nonce"],
        "attempt": validation["attempt"],
        "unit": validation["unit"],
        "invocation_id": validation["invocation_id"],
        "manager_epoch": copy.deepcopy(fixture["current_epoch"]),
    }

    def release_joins() -> bool:
        return (
            verifier._run_nonce(release, "release token") == validation["run_nonce"]
            and verifier._unit(release, "release token") == validation["unit"]
            and verifier._invocation_id(release, "release token") == validation["invocation_id"]
            and release["attempt"] == validation["attempt"]
            and verifier._same_epoch(
                release["manager_epoch"],
                fixture["current_epoch"],
            )
        )

    assert release_joins()
    release["invocation_id"] = "2" * 32
    assert not release_joins()


def test_outer_attempt_pre_registration_is_closed(
    attempt_runner: ModuleType,
) -> None:
    accepted = {
        ("synthetic-success-a001", "synthetic_success"),
        ("synthetic-postseal-fail-a001", "synthetic_postseal_failure"),
        ("a002", "formal"),
    }
    for attempt, purpose in accepted:
        attempt_runner._validate_attempt_name(attempt, purpose)
    with pytest.raises(attempt_runner.AttemptError, match="pre-registered"):
        attempt_runner._validate_attempt_name("a002", "synthetic_success")
    with pytest.raises(attempt_runner.AttemptError, match="pre-registered"):
        attempt_runner._validate_attempt_name("a003", "formal")


def test_pinned_source_loader_and_contract_helpers_are_exact(
    attempt_runner: ModuleType,
) -> None:
    identity = {"sha256": _sha("f")}
    argv = attempt_runner._make_loader_argv(
        "/fixed/python",
        Path("/fixed/worker.py"),
        identity,
        ["--flag", "value"],
    )
    assert argv[:4] == [
        "/fixed/python",
        "-I",
        "-c",
        attempt_runner.PINNED_SOURCE_LOADER,
    ]
    assert argv[4:] == [
        "/fixed/worker.py",
        _sha("f"),
        "--flag",
        "value",
    ]
    loader = attempt_runner.PINNED_SOURCE_LOADER
    assert "O_NOFOLLOW" in loader
    assert "os.fstat(f)" in loader
    assert "hashlib.sha256(r).hexdigest()!=e" in loader
    assert "exec(compile(r,p,'exec'" in loader
    with pytest.raises(attempt_runner.AttemptError, match="SHA-256"):
        attempt_runner._make_loader_argv(
            "/fixed/python",
            Path("/fixed/worker.py"),
            {"sha256": "not-a-digest"},
            [],
        )

    authority = {"resource_contract": _resource_contract()}
    assert attempt_runner._resource_contract(authority) == authority["resource_contract"]
    assert {
        key: authority["resource_contract"][key]
        for key in (
            "formal_runtime_max_seconds",
            "formal_payload_wait_seconds",
            "formal_keeper_timeout_seconds",
            "formal_roundingsat_time_limit_seconds",
            "formal_roundingsat_monitor_limit_seconds",
            "formal_veripb_time_limit_seconds",
        )
    } == {
        "formal_runtime_max_seconds": 9000,
        "formal_payload_wait_seconds": 8000,
        "formal_keeper_timeout_seconds": 8700,
        "formal_roundingsat_time_limit_seconds": 3600,
        "formal_roundingsat_monitor_limit_seconds": 3900,
        "formal_veripb_time_limit_seconds": 3600,
    }
    mutated = copy.deepcopy(authority)
    mutated["resource_contract"]["memory_max_bytes"] -= 1
    with pytest.raises(attempt_runner.AttemptError, match="memory_max_bytes"):
        attempt_runner._resource_contract(mutated)
    mutated = copy.deepcopy(authority)
    mutated["resource_contract"]["formal_keeper_timeout_seconds"] -= 1
    with pytest.raises(
        attempt_runner.AttemptError,
        match="formal_keeper_timeout_seconds",
    ):
        attempt_runner._resource_contract(mutated)


def test_outer_selection_is_o_excl_and_post_selection_drift_consumes_it(
    attempt_runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = {
        "run_nonce": "smm3-fixture-0001",
        "resource_contract": _resource_contract(),
    }
    authority_identity = {
        "path": "/authority.json",
        "size_bytes": 123,
        "sha256": _sha("a"),
        "mode_octal": "0644",
    }
    payload_identity = {
        "path": "/payload-spec.json",
        "size_bytes": 456,
        "sha256": _sha("b"),
        "mode_octal": "0644",
    }
    monkeypatch.setattr(
        attempt_runner,
        "_epoch",
        lambda *_args, **_kwargs: copy.deepcopy(_epoch()),
    )
    path = tmp_path / "selection.json"
    payload, identity = attempt_runner._publish_selection(
        authority=authority,
        authority_identity=authority_identity,
        orchestrator=SimpleNamespace(),
        path=path,
        attempt="a002",
        purpose="formal",
        unit="b1-smm3-fixture-0001.service",
        worker_argv=["/fixed/worker.py"],
        payload_spec_identity=payload_identity,
        formal_admission={
            "path": "/formal-admission.json",
            "size_bytes": 789,
            "sha256": _sha("c"),
            "mode_octal": "0644",
        },
    )
    assert payload["status"] == "SELECTED_CONSUMED"
    assert identity == _json_identity(path)
    with pytest.raises(attempt_runner.AttemptError, match="O_EXCL"):
        attempt_runner._publish_selection(
            authority=authority,
            authority_identity=authority_identity,
            orchestrator=SimpleNamespace(),
            path=path,
            attempt="a002",
            purpose="formal",
            unit="b1-smm3-fixture-0001.service",
            worker_argv=["/fixed/worker.py"],
            payload_spec_identity=payload_identity,
            formal_admission={
                "path": "/formal-admission.json",
                "size_bytes": 789,
                "sha256": _sha("c"),
                "mode_octal": "0644",
            },
        )

    consumed = tmp_path / "selection-consumed.json"
    calls = 0

    def drift_after_selection(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise attempt_runner.AttemptError("manager/boot epoch drifted")
        return copy.deepcopy(_epoch())

    monkeypatch.setattr(attempt_runner, "_epoch", drift_after_selection)
    with pytest.raises(attempt_runner.AttemptError, match="epoch drifted"):
        attempt_runner._publish_selection(
            authority=authority,
            authority_identity=authority_identity,
            orchestrator=SimpleNamespace(),
            path=consumed,
            attempt="a002",
            purpose="formal",
            unit="b1-smm3-fixture-0001.service",
            worker_argv=["/fixed/worker.py"],
            payload_spec_identity=payload_identity,
            formal_admission={
                "path": "/formal-admission.json",
                "size_bytes": 789,
                "sha256": _sha("c"),
                "mode_octal": "0644",
            },
        )
    assert consumed.is_file()


def test_bootstrap_pins_privileged_and_ordinary_tool_boundaries(
    recovery: ModuleType,
    attempt_runner: ModuleType,
) -> None:
    source = inspect.getsource(recovery.current_toolchain_snapshot) + inspect.getsource(recovery.bootstrap_payload)
    assert '"privileged_attestor"' in source
    assert '"sudo"' in source
    assert '"privileged_python"' in source
    assert '"attempt_runner"' in source
    assert '"independent_verifier"' in source
    assert "attestation_toolchain" in source
    assert "identity_matches" in source

    # The outer lifecycle runner remains ordinary-user code.  Only the pinned
    # manager helper is allowed to invoke sudo.
    outer_source = inspect.getsource(attempt_runner)
    assert "subprocess" in outer_source
    assert "sudo -n" not in outer_source
    assert '"/usr/bin/sudo"' not in outer_source
    manager_source = (RESEARCH / "manager_epoch_authority_v1.py").read_text()
    assert '"-n"' in manager_source
    assert '"--"' in manager_source
    assert "_LOADER" in manager_source


def test_recovery_closeout_binds_verified_detached_result_and_is_no_overwrite(
    attempt_runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    formal_dir = run_dir / "formal-attempt-a002"
    formal_dir.mkdir(parents=True)
    authority_path = run_dir / "authority.json"
    authority_identity = _write_json(authority_path, {"authority": "fixture"})
    manager_epoch = _epoch()
    authority = {
        "run": "run",
        "run_nonce": "smm3-fixture-0001",
        "manager_epoch": manager_epoch,
    }
    detached_path = formal_dir / "detached-verification.json"
    _write_json(
        detached_path,
        {
            "schema_version": "b1_sidewise_smm3_detached_closeout_v1",
            "status": "VERIFIED",
            "inputs": {"authority": authority_identity},
            "manager_epoch": manager_epoch,
            "upper_bound_update_authorized": True,
            "ledger": {"upper": [1188, 18], "lower": "absent"},
            "production_certified": False,
        },
    )
    monkeypatch.setattr(attempt_runner, "ROOT", tmp_path)
    monkeypatch.setattr(
        attempt_runner,
        "_load_authority",
        lambda _path: (
            copy.deepcopy(authority),
            copy.deepcopy(authority_identity),
            SimpleNamespace(same_epoch=lambda left, right: left == right),
        ),
    )
    monkeypatch.setattr(
        attempt_runner,
        "_epoch",
        lambda *_args, **_kwargs: copy.deepcopy(manager_epoch),
    )
    output = run_dir / "closeout-a001.json"
    result = attempt_runner._publish_recovery_closeout(
        authority_path=authority_path,
        result_path=detached_path,
        output=output,
    )
    assert result["status"] == "VERIFIED"
    assert result["ledger"] == {"upper": [1188, 18], "lower": "absent"}
    closeout = json.loads(output.read_text(encoding="ascii"))
    assert closeout["result"] == _json_identity(detached_path)
    assert closeout["next_required_task"] == "CUTS_GATE1_V4_AUTHORITY_COMPLETION"
    with pytest.raises(attempt_runner.AttemptError, match="O_EXCL"):
        attempt_runner._publish_recovery_closeout(
            authority_path=authority_path,
            result_path=detached_path,
            output=output,
        )
