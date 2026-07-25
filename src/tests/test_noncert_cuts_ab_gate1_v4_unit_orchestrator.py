from __future__ import annotations

import base64
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"
HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
NOW = "2026-07-24T00:00:00Z"
BOOT = "11111111-2222-3333-4444-555555555555"


def test_public_orchestrator_has_no_runtime_or_lifecycle_callback_seam() -> None:
    assert set(inspect.signature(ORCHESTRATOR.orchestrate_selected_unit).parameters) == {
        "campaign_root_identity",
        "selection_identity",
        "unit_slot",
    }


def _load(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


AUTH = _load("campaign_authority_v4", "campaign_authority_v4.py")
LIFECYCLE = _load("resource_lifecycle_v4", "resource_lifecycle_v4.py")
_load("resource_verifier_v4", "resource_verifier_v4.py")
_load("gate1_campaign_driver_v4", "gate1_campaign_driver_v4.py")
PAYLOAD = _load("cuts_gate1_v4_unit_payload", "gate1_payload_v4.py")
ORCHESTRATOR = _load(
    "cuts_gate1_v4_unit_orchestrator",
    "gate1_unit_orchestrator_v4.py",
)


def _write(path: Path, raw: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _detached(path: Path) -> dict[str, object]:
    return AUTH.detached_identity(AUTH.snapshot_regular(path))


def _full(path: Path) -> dict[str, object]:
    return AUTH.full_identity(AUTH.snapshot_regular(path))


def _epoch(tmp_path: Path) -> dict[str, object]:
    manager = _write(tmp_path / "epoch/systemd", b"systemd manager bytes\n")
    busctl = _write(tmp_path / "epoch/busctl", b"fixture busctl\n")
    sudo = _write(tmp_path / "epoch/sudo", b"fixture sudo\n")
    python = _write(tmp_path / "epoch/python3", b"fixture python\n")
    attestor = RESEARCH / "manager_attestor_v4.py"
    return {
        "attestation_toolchain": {
            "attestor": _full(attestor),
            "python": _full(python),
            "sudo": _full(sudo),
        },
        "attestor_ast_audit": AUTH.audit_attestor_source(attestor.read_bytes()),
        "boot_id": BOOT,
        "capture_protocol": ("double-unprivileged-join-plus-read-only-sudo-attestation-v4"),
        "dbus_unique_owner": ":1.77",
        "manager_executable": _full(manager),
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 987654,
        "manager_version": "systemd 261.1",
        "observation_toolchain": {"busctl": _full(busctl)},
        "schema": AUTH.MANAGER_EPOCH_SCHEMA,
    }


def _fixture(tmp_path: Path) -> dict[str, Any]:
    campaign = tmp_path / "dev-drill-campaign"
    (campaign / "campaign-authority").mkdir(parents=True)
    mandatory = _write(tmp_path / "inputs/mandatory.json", b'{"instances":[]}\n')
    candidates = _write(tmp_path / "inputs/candidates.json", b'{"facility_pools":{}}\n')
    epoch = _epoch(tmp_path)
    package = AUTH.build_package(
        campaign / "campaign-authority/package",
        [
            AUTH.SourceSpec("candidates.json", candidates, parse_json=True),
            AUTH.SourceSpec("mandatory.json", mandatory, parse_json=True),
        ],
        repository_head=HEAD,
        run_nonce="cuts-gate1-v4-unit-fixture",
        manager_epoch=epoch,
    )
    required_roles = set(AUTH.REQUIRED_GATE1_TOOL_ROLES) | set(ORCHESTRATOR.REQUIRED_EXECUTION_TOOL_ROLES)
    tools: dict[str, dict[str, object]] = {}
    for role in sorted(required_roles):
        implementation = RESEARCH / f"{role}.py"
        if not implementation.is_file():
            implementation = _write(
                tmp_path / f"selected-tools/{role}",
                f"fixture tool role: {role}\n".encode(),
            )
        tools[role] = _detached(implementation)
    tools["attestor_python"] = _detached(Path(epoch["attestation_toolchain"]["python"]["path"]))
    tools["busctl"] = _detached(Path(epoch["observation_toolchain"]["busctl"]["path"]))
    tools["manager_attestor_v4"] = _detached(Path(epoch["attestation_toolchain"]["attestor"]["path"]))
    tools["sudo"] = _detached(Path(epoch["attestation_toolchain"]["sudo"]["path"]))
    # The payload's selected forced callback is a harmless fixture; tests inject
    # its callable rather than executing these bytes.
    selected_delegate = _write(
        tmp_path / "tools/positive_control_formal_v4.py",
        b"# selected positive-control fixture\n",
    )
    tools["positive_control_formal_v4"] = _detached(selected_delegate)
    inputs: dict[str, dict[str, object]] = {}
    for role in AUTH.REQUIRED_GATE1_INPUT_ROLES:
        if role == "candidate_placements":
            source = candidates
        elif role == "mandatory_instances":
            source = mandatory
        elif role == "project_lock":
            source = _write(
                tmp_path / "repo/PROJECT_LOCK.md",
                b"# fixture project lock\n",
            )
        else:
            source = _write(
                tmp_path / f"inputs/{role}",
                f"fixture input role: {role}\n".encode(),
            )
        inputs[role] = _detached(source)
    root = AUTH.build_campaign_root(
        campaign,
        package=package,
        repository_head=HEAD,
        run_nonce="cuts-gate1-v4-unit-fixture",
        manager_epoch=epoch,
        authority_tools=tools,
        strict_inputs=inputs,
        created_at_utc=NOW,
    )
    root_identity = AUTH.write_campaign_root(campaign, root)
    root_path = campaign / "campaign-root.json"
    selection = AUTH.make_gate1_selection(
        root,
        campaign_root_identity=root_identity,
        tools=tools,
        inputs=inputs,
        created_at_utc=NOW,
    )
    selection_identity = AUTH.write_gate1_selection(
        root_path,
        root_identity,
        selection,
    )
    return {
        "campaign": campaign,
        "delegate_path": selected_delegate,
        "epoch": epoch,
        "root": root,
        "root_identity": root_identity,
        "selection": selection,
        "selection_identity": selection_identity,
        "tools": tools,
    }


def _prepare_payload_dirs(fixture: dict[str, Any], slot: str) -> None:
    unit = fixture["selection"]["units"][slot]
    Path(unit["attempt_dir"]).mkdir(parents=True)
    Path(unit["raw_dir"]).mkdir()
    Path(unit["terminal_dir"]).mkdir()


@pytest.mark.parametrize(
    ("slot", "expected"),
    (("q-success", 0), ("q-postseal-fail", 7)),
)
def test_synthetic_payload_seals_before_selected_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    slot: str,
    expected: int,
) -> None:
    fixture = _fixture(tmp_path)
    _prepare_payload_dirs(fixture, slot)
    monkeypatch.setattr(PAYLOAD.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(PAYLOAD.os, "getuid", lambda: 1000)
    returncode = PAYLOAD.publish_selected_payload(
        campaign_root_identity=fixture["root_identity"],
        selection_identity=fixture["selection_identity"],
        unit_slot=slot,
        now_utc=lambda: NOW,
    )
    unit = fixture["selection"]["units"][slot]
    result_path = Path(unit["result_path"])
    seal_path = Path(unit["raw_dir"]) / "payload-seal.json"
    assert returncode == expected
    result = json.loads(result_path.read_bytes())
    seal = json.loads(seal_path.read_bytes())
    assert result["sealed_before_exit"] is True
    assert result["expected_returncode"] == expected
    assert seal["expected_returncode"] == expected
    assert seal["result_identity"] == _detached(result_path)
    assert seal["payload_complete"] is True
    with pytest.raises(PAYLOAD.PayloadError, match="already exists"):
        PAYLOAD.publish_selected_payload(
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            unit_slot=slot,
            now_utc=lambda: NOW,
        )


def test_forced_payload_delegates_only_to_selected_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    _prepare_payload_dirs(fixture, "forced-treatment")
    monkeypatch.setattr(PAYLOAD.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(PAYLOAD.os, "getuid", lambda: 1000)
    calls: list[dict[str, object]] = []

    def delegate(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "PASS",
            "arm": "treatment",
            "profile": "disposable_drill",
            "generated": 1,
            "compiled": 1,
            "applied": 1,
            "support_tool_identity": fixture["tools"]["positive_control_v4"],
            "post_solve_performed": False,
            "organic_arm_launch_authorized": False,
            "global_claim_authorized": False,
        }

    assert (
        PAYLOAD.publish_selected_payload(
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            unit_slot="forced-treatment",
            delegate=delegate,
            now_utc=lambda: NOW,
        )
        == 0
    )
    assert len(calls) == 1
    assert calls[0]["unit_slot"] == "forced-treatment"
    result = json.loads(Path(fixture["selection"]["units"]["forced-treatment"]["result_path"]).read_bytes())
    assert result["delegated_tool_identity"] == fixture["tools"]["positive_control_formal_v4"]
    assert result["organic_arm_launch_authorized"] is False
    with pytest.raises(PAYLOAD.PayloadError, match="organic or unknown"):
        PAYLOAD.publish_selected_payload(
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            unit_slot="region-capacity",
            delegate=delegate,
        )


def test_formal_delegate_and_support_are_loaded_from_selected_bytes() -> None:
    formal_path = RESEARCH / "positive_control_formal_v4.py"
    support_path = RESEARCH / "positive_control_v4.py"
    formal_raw = formal_path.read_bytes()
    support_raw = support_path.read_bytes()
    callback = PAYLOAD._load_delegate_from_selected_bytes(  # noqa: SLF001
        formal_raw,
        _detached(formal_path),
        PAYLOAD.DEFAULT_DELEGATE_ENTRYPOINT,
        support_raw=support_raw,
        support_identity=_detached(support_path),
        project_root=ROOT,
    )

    assert callback.__name__ == "run_forced_payload_v4"
    assert callback.__globals__["_SUPPORT_SELECTED_IDENTITY"] == _detached(support_path)
    assert callback.__globals__["_PROJECT_ROOT"] == ROOT
    with pytest.raises(PAYLOAD.PayloadError, match="support failed to load"):
        PAYLOAD._load_delegate_from_selected_bytes(  # noqa: SLF001
            formal_raw,
            _detached(formal_path),
            PAYLOAD.DEFAULT_DELEGATE_ENTRYPOINT,
            support_raw=b"this is not Python",
            support_identity={
                "path": str(support_path),
                "size_bytes": len(b"this is not Python"),
                "sha256": hashlib.sha256(b"this is not Python").hexdigest(),
            },
            project_root=ROOT,
        )


def test_forced_payload_fails_before_callback_on_selected_tool_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    _prepare_payload_dirs(fixture, "forced-control")
    fixture["delegate_path"].write_bytes(b"drifted\n")
    monkeypatch.setattr(PAYLOAD.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(PAYLOAD.os, "getuid", lambda: 1000)
    called = False

    def delegate(**_: object) -> dict[str, object]:
        nonlocal called
        called = True
        return {
            "status": "PASS",
            "arm": "control",
            "organic_arm_launch_authorized": False,
        }

    with pytest.raises(AUTH.AuthorityError, match="drift"):
        PAYLOAD.publish_selected_payload(
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            unit_slot="forced-control",
            delegate=delegate,
        )
    assert called is False


class _FakeRuntime:
    def __init__(
        self,
        events: list[str],
        inner_path: Path,
        *,
        cleanup_failure: bool = False,
    ) -> None:
        self.events = events
        self.inner_path = inner_path
        self.launch_argv: tuple[str, ...] | None = None
        self.cleanup_failure = cleanup_failure

    def launch(
        self,
        argv: list[str] | tuple[str, ...],
        *,
        timeout_seconds: int,
    ) -> object:
        self.events.append("launch")
        self.launch_argv = tuple(argv)
        assert timeout_seconds > 0
        return ORCHESTRATOR.LaunchObservation(
            argv=tuple(argv),
            exit_code=0,
            stdout=b"launch-ok\n",
            stderr=b"",
            started_monotonic_ns=100,
            finished_monotonic_ns=200,
        )

    def wait_for_regular(self, path: Path, *, timeout_seconds: int) -> None:
        self.events.append("wait-inner")
        assert path == self.inner_path
        assert timeout_seconds > 0
        AUTH.write_exclusive(path, AUTH.canonical_json({"inner": "fixture"}))

    def wait_for_terminal(self, unit_name: str, *, timeout_seconds: int) -> None:
        self.events.append("wait-terminal")
        assert unit_name.endswith(".service")
        assert timeout_seconds > 0

    def cleanup(self, unit_name: str) -> tuple[object, ...]:
        self.events.append("emergency-cleanup")
        if self.cleanup_failure:
            raise RuntimeError("fixture cleanup failed")
        return (
            LIFECYCLE.CommandEvidence(
                argv=(str(LIFECYCLE.SYSTEMCTL), "--user", "stop", unit_name),
                exit_code=0,
                stdout=b"",
                stderr=b"",
            ),
            LIFECYCLE.CommandEvidence(
                argv=(str(LIFECYCLE.SYSTEMCTL), "--user", "reset-failed", unit_name),
                exit_code=0,
                stdout=b"",
                stderr=b"",
            ),
        )

    def load_state(self, unit_name: str) -> object:
        self.events.append("emergency-load-state")
        return LIFECYCLE.CommandEvidence(
            argv=LIFECYCLE._load_state_argv(unit_name),  # noqa: SLF001
            exit_code=0,
            stdout=b"not-found\n",
            stderr=b"",
        )


def test_orchestrator_orders_all_live_epoch_and_lifecycle_phases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    slot = "q-success"
    unit = fixture["selection"]["units"][slot]
    paths = LIFECYCLE.lifecycle_paths(fixture["selection"], slot)
    events: list[str] = []
    runtime = _FakeRuntime(events, paths["inner"])
    monkeypatch.setattr(ORCHESTRATOR.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(ORCHESTRATOR.os, "getuid", lambda: 1000)

    def checkpoint(**kwargs: object) -> dict[str, object]:
        phase = str(kwargs["phase"])
        events.append(f"epoch:{phase}")
        assert kwargs["sudo_path"] == Path(fixture["epoch"]["attestation_toolchain"]["sudo"]["path"])
        path = Path(unit["epoch_checkpoint_paths"][phase])
        return AUTH.write_exclusive(
            path,
            AUTH.canonical_json({"phase": phase}),
        )

    def capture_preterminal(**_: object) -> tuple[dict[str, object], dict[str, object]]:
        events.append("capture-preterminal")
        value = {"preterminal": "fixture"}
        identity = AUTH.write_exclusive(
            paths["preterminal"],
            AUTH.canonical_json(value),
        )
        return value, identity

    def verify_preterminal(**_: object) -> dict[str, object]:
        events.append("verify-preterminal")
        return {"resource": "PASS"}

    def build_release(
        *_: object,
        **__: object,
    ) -> dict[str, object]:
        events.append("build-release")
        return {"release": "PASS"}

    def capture_terminal(**_: object) -> tuple[dict[str, object], dict[str, object]]:
        events.append("capture-terminal")
        value = {"terminal": "fixture"}
        identity = AUTH.write_exclusive(paths["terminal"], AUTH.canonical_json(value))
        return value, identity

    def capture_cleanup(**_: object) -> tuple[dict[str, object], dict[str, object]]:
        events.append("capture-cleanup")
        value = {"cleanup": "fixture"}
        identity = AUTH.write_exclusive(paths["cleanup"], AUTH.canonical_json(value))
        return value, identity

    def verify_detached(**_: object) -> dict[str, object]:
        events.append("verify-detached")
        return {"detached": "PASS"}

    result = ORCHESTRATOR._orchestrate_selected_unit_with(  # noqa: SLF001
        campaign_root_identity=fixture["root_identity"],
        selection_identity=fixture["selection_identity"],
        unit_slot=slot,
        runtime=runtime,
        checkpoint=checkpoint,
        capture_preterminal=capture_preterminal,
        verify_preterminal=verify_preterminal,
        build_release=build_release,
        capture_terminal=capture_terminal,
        capture_cleanup=capture_cleanup,
        verify_detached=verify_detached,
        now_utc=lambda: NOW,
        monotonic_ns=lambda: 500,
    )
    assert events == [
        "epoch:prelaunch",
        "launch",
        "wait-inner",
        "epoch:preterminal",
        "capture-preterminal",
        "verify-preterminal",
        "build-release",
        "wait-terminal",
        "epoch:terminal",
        "capture-terminal",
        "epoch:cleanup",
        "capture-cleanup",
        "epoch:detached-replay",
        "verify-detached",
    ]
    assert result["unit_slot"] == slot
    assert Path(result["detached_identity"]["path"]).name == (ORCHESTRATOR.DETACHED_REPLAY_FILENAME)
    assert runtime.launch_argv is not None
    argv = runtime.launch_argv
    assert argv[0] == fixture["tools"]["systemd_run"]["path"]
    assert "--user" in argv
    assert f"--unit={unit['unit_name']}" in argv
    assert f"--working-directory={tmp_path / 'repo'}" in argv
    assert "--property=MemoryHigh=37580963840" in argv
    assert "--property=MemoryMax=41875931136" in argv
    assert "--property=MemorySwapMax=17179869184" in argv
    assert "--property=OOMPolicy=continue" in argv
    assert "--property=KillMode=control-group" in argv
    assert "--property=SendSIGKILL=yes" in argv
    assert "--property=RuntimeMaxSec=120" in argv
    assert not any(Path(item).name == "sudo" for item in argv)
    separator = argv.index("--")
    supervisor_command = argv[separator + 1 :]
    assert supervisor_command[:4] == (
        fixture["tools"]["python3_13"]["path"],
        "-I",
        "-c",
        ORCHESTRATOR.SELECTED_BYTE_ENTRYPOINT_LOADER,
    )
    supervisor_manifest = json.loads(base64.b64decode(supervisor_command[4], validate=True))
    assert supervisor_manifest["target"]["role"] == "resource_lifecycle_v4"
    assert supervisor_manifest["aliases"] == []
    supervisor_args = supervisor_manifest["argv"]
    nested_python = supervisor_args.index(
        fixture["tools"]["python3_13"]["path"],
    )
    payload_command = supervisor_args[nested_python:]
    assert payload_command[:4] == [
        fixture["tools"]["python3_13"]["path"],
        "-I",
        "-c",
        ORCHESTRATOR.SELECTED_BYTE_ENTRYPOINT_LOADER,
    ]
    payload_manifest = json.loads(base64.b64decode(payload_command[4], validate=True))
    assert payload_manifest["target"]["role"] == "gate1_payload_v4"
    assert [(member["alias"], member["role"]) for member in payload_manifest["aliases"]] == [
        ("campaign_authority_v4", "campaign_authority_v4"),
        ("resource_lifecycle_v4", "resource_lifecycle_v4"),
    ]
    assert fixture["tools"]["resource_lifecycle_v4"]["path"] not in argv
    assert fixture["tools"]["gate1_payload_v4"]["path"] not in argv


def test_epoch_drift_stops_before_later_lifecycle_and_consumes_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    slot = "q-success"
    unit = fixture["selection"]["units"][slot]
    paths = LIFECYCLE.lifecycle_paths(fixture["selection"], slot)
    events: list[str] = []
    runtime = _FakeRuntime(events, paths["inner"])
    monkeypatch.setattr(ORCHESTRATOR.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(ORCHESTRATOR.os, "getuid", lambda: 1000)

    def checkpoint(**kwargs: object) -> dict[str, object]:
        phase = str(kwargs["phase"])
        events.append(f"epoch:{phase}")
        if phase == "preterminal":
            raise ORCHESTRATOR.OrchestrationError("manager epoch drift")
        return AUTH.write_exclusive(
            Path(unit["epoch_checkpoint_paths"][phase]),
            AUTH.canonical_json({"phase": phase}),
        )

    with pytest.raises(ORCHESTRATOR.OrchestrationError, match="epoch drift"):
        ORCHESTRATOR._orchestrate_selected_unit_with(  # noqa: SLF001
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            unit_slot=slot,
            runtime=runtime,
            checkpoint=checkpoint,
        )
    assert events == [
        "epoch:prelaunch",
        "launch",
        "wait-inner",
        "epoch:preterminal",
        "emergency-cleanup",
        "emergency-load-state",
    ]
    assert Path(unit["attempt_dir"]).is_dir()
    assert not paths["preterminal"].exists()


def test_verifier_failure_cleans_unit_without_publishing_terminal_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    slot = "q-success"
    unit = fixture["selection"]["units"][slot]
    paths = LIFECYCLE.lifecycle_paths(fixture["selection"], slot)
    events: list[str] = []
    runtime = _FakeRuntime(events, paths["inner"])
    monkeypatch.setattr(ORCHESTRATOR.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(ORCHESTRATOR.os, "getuid", lambda: 1000)
    sentinel = ORCHESTRATOR.OrchestrationError("fixture verifier failure")

    def checkpoint(**kwargs: object) -> dict[str, object]:
        phase = str(kwargs["phase"])
        events.append(f"epoch:{phase}")
        return AUTH.write_exclusive(
            Path(unit["epoch_checkpoint_paths"][phase]),
            AUTH.canonical_json({"phase": phase}),
        )

    def capture_preterminal(**_: object) -> tuple[dict[str, object], dict[str, object]]:
        events.append("capture-preterminal")
        value = {"preterminal": "fixture"}
        identity = AUTH.write_exclusive(paths["preterminal"], AUTH.canonical_json(value))
        return value, identity

    def fail_verification(**_: object) -> dict[str, object]:
        events.append("verify-preterminal")
        raise sentinel

    with pytest.raises(ORCHESTRATOR.OrchestrationError) as captured:
        ORCHESTRATOR._orchestrate_selected_unit_with(  # noqa: SLF001
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            unit_slot=slot,
            runtime=runtime,
            checkpoint=checkpoint,
            capture_preterminal=capture_preterminal,
            verify_preterminal=fail_verification,
        )
    assert captured.value is sentinel
    assert events == [
        "epoch:prelaunch",
        "launch",
        "wait-inner",
        "epoch:preterminal",
        "capture-preterminal",
        "verify-preterminal",
        "emergency-cleanup",
        "emergency-load-state",
    ]
    for unpublished in (
        paths["resource_verification"],
        paths["release"],
        paths["terminal"],
        paths["cleanup"],
        Path(unit["terminal_dir"]) / ORCHESTRATOR.DETACHED_REPLAY_FILENAME,
    ):
        assert not unpublished.exists()


def test_launch_exception_still_cleans_exact_selected_unit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    slot = "q-success"
    paths = LIFECYCLE.lifecycle_paths(fixture["selection"], slot)
    events: list[str] = []

    class FailingLaunchRuntime(_FakeRuntime):
        def launch(
            self,
            argv: list[str] | tuple[str, ...],
            *,
            timeout_seconds: int,
        ) -> object:
            self.events.append("launch")
            raise TimeoutError("fixture launch timeout")

    runtime = FailingLaunchRuntime(events, paths["inner"])
    monkeypatch.setattr(ORCHESTRATOR.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(ORCHESTRATOR.os, "getuid", lambda: 1000)

    with pytest.raises(TimeoutError, match="fixture launch timeout"):
        ORCHESTRATOR._orchestrate_selected_unit_with(  # noqa: SLF001
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            unit_slot=slot,
            runtime=runtime,
            checkpoint=lambda **_: AUTH.write_exclusive(
                Path(fixture["selection"]["units"][slot]["epoch_checkpoint_paths"]["prelaunch"]),
                AUTH.canonical_json({"phase": "prelaunch"}),
            ),
        )
    assert events == ["launch", "emergency-cleanup", "emergency-load-state"]


def test_prelaunch_failure_never_touches_unit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    paths = LIFECYCLE.lifecycle_paths(fixture["selection"], "q-success")
    events: list[str] = []
    runtime = _FakeRuntime(events, paths["inner"])
    monkeypatch.setattr(ORCHESTRATOR.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(ORCHESTRATOR.os, "getuid", lambda: 1000)

    with pytest.raises(ORCHESTRATOR.OrchestrationError, match="prelaunch rejected"):
        ORCHESTRATOR._orchestrate_selected_unit_with(  # noqa: SLF001
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            unit_slot="q-success",
            runtime=runtime,
            checkpoint=lambda **_: (_ for _ in ()).throw(ORCHESTRATOR.OrchestrationError("prelaunch rejected")),
        )
    assert events == []


def test_cleanup_failure_preserves_both_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    slot = "q-success"
    paths = LIFECYCLE.lifecycle_paths(fixture["selection"], slot)
    events: list[str] = []
    runtime = _FakeRuntime(events, paths["inner"], cleanup_failure=True)
    monkeypatch.setattr(ORCHESTRATOR.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(ORCHESTRATOR.os, "getuid", lambda: 1000)

    def checkpoint(**kwargs: object) -> dict[str, object]:
        phase = str(kwargs["phase"])
        if phase == "preterminal":
            raise ORCHESTRATOR.OrchestrationError("primary epoch failure")
        return AUTH.write_exclusive(
            Path(fixture["selection"]["units"][slot]["epoch_checkpoint_paths"][phase]),
            AUTH.canonical_json({"phase": phase}),
        )

    with pytest.raises(BaseExceptionGroup) as captured:
        ORCHESTRATOR._orchestrate_selected_unit_with(  # noqa: SLF001
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            unit_slot=slot,
            runtime=runtime,
            checkpoint=checkpoint,
        )
    assert [str(error) for error in captured.value.exceptions] == [
        "primary epoch failure",
        "fixture cleanup failed",
    ]
    assert events == [
        "launch",
        "wait-inner",
        "emergency-cleanup",
    ]


def test_orchestrator_rejects_tool_drift_and_existing_attempt_before_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    slot = "q-success"
    events: list[str] = []
    runtime = _FakeRuntime(
        events,
        LIFECYCLE.lifecycle_paths(fixture["selection"], slot)["inner"],
    )
    monkeypatch.setattr(ORCHESTRATOR.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(ORCHESTRATOR.os, "getuid", lambda: 1000)
    systemd_run_path = Path(fixture["tools"]["systemd_run"]["path"])
    systemd_run_path.write_bytes(b"drifted systemd-run fixture\n")
    with pytest.raises(AUTH.AuthorityError, match="drift"):
        ORCHESTRATOR._orchestrate_selected_unit_with(  # noqa: SLF001
            campaign_root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            unit_slot=slot,
            runtime=runtime,
        )
    assert events == []

    # A fresh authority demonstrates the no-overwrite attempt guard.
    second = _fixture(tmp_path / "second")
    second_unit = second["selection"]["units"][slot]
    Path(second_unit["attempt_dir"]).mkdir(parents=True)
    second_events: list[str] = []
    second_runtime = _FakeRuntime(
        second_events,
        LIFECYCLE.lifecycle_paths(second["selection"], slot)["inner"],
    )
    with pytest.raises(ORCHESTRATOR.OrchestrationError, match="already exists"):
        ORCHESTRATOR._orchestrate_selected_unit_with(  # noqa: SLF001
            campaign_root_identity=second["root_identity"],
            selection_identity=second["selection_identity"],
            unit_slot=slot,
            runtime=second_runtime,
        )
    assert second_events == []


def test_formal_profile_command_and_future_organic_slot_are_separate(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    argv = ORCHESTRATOR.build_systemd_run_argv(
        root_identity=fixture["root_identity"],
        selection_identity=fixture["selection_identity"],
        selection=fixture["selection"],
        unit_slot="forced-control",
    )
    assert "--property=RuntimeMaxSec=1500" in argv
    assert f"--unit={fixture['selection']['units']['forced-control']['unit_name']}" in argv
    with pytest.raises(ORCHESTRATOR.OrchestrationError, match="organic or unknown"):
        ORCHESTRATOR.build_systemd_run_argv(
            root_identity=fixture["root_identity"],
            selection_identity=fixture["selection_identity"],
            selection=fixture["selection"],
            unit_slot="region-capacity",
        )
    positive = fixture["root"]["stage_topology"]["gate1_v4"]["positive_control"]
    assert positive["common_manifest_path"].endswith("/common-prestate/manifest.json")
    assert set(positive["binding_paths"]) == {"control", "treatment"}


def test_selected_entrypoint_loader_executes_only_snapshotted_alias_and_target(
    tmp_path: Path,
) -> None:
    alias = _write(
        tmp_path / "selected/fixture_alias.py",
        b"VALUE = 'selected-alias-ok'\n",
    )
    target = _write(
        tmp_path / "selected/fixture_target.py",
        b"import fixture_alias\nprint(fixture_alias.VALUE)\n",
    )
    tools = {
        "python3_13": _detached(Path(sys.executable).resolve()),
        "alias_role": _detached(alias),
        "target_role": _detached(target),
    }
    command = ORCHESTRATOR._selected_entrypoint_command(  # noqa: SLF001
        selection={"tools": tools},
        target_role="target_role",
        aliases=(("fixture_alias", "alias_role"),),
        argv=(),
    )
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    assert completed.returncode == 0
    assert completed.stdout == b"selected-alias-ok\n"
    assert completed.stderr == b""

    target.write_bytes(b"print('drifted target')\n")
    drifted = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    assert drifted.returncode != 0
    assert b"target detached identity drifted" in drifted.stderr
