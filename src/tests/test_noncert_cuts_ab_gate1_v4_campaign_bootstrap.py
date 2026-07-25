from __future__ import annotations

import base64
import copy
import importlib.util
from pathlib import Path
from types import ModuleType
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab_trust_gate1_v4_20260724"
HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
NOW = "2026-07-24T12:00:00+00:00"
BOOT_ID = "11111111-2222-3333-4444-555555555555"


def _load(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


AUTH = _load(
    "noncert_cuts_gate1_v4_bootstrap_authority",
    "campaign_authority_v4.py",
)
sys.modules["campaign_authority_v4"] = AUTH
BOOTSTRAP = _load(
    "noncert_cuts_gate1_v4_campaign_bootstrap",
    "gate1_campaign_bootstrap_v4.py",
)


def _write(path: Path, raw: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _full(path: Path) -> dict[str, object]:
    return AUTH.full_identity(AUTH.snapshot_regular(path))


def _fixture_sources(
    tmp_path: Path,
) -> tuple[dict[str, Path], dict[str, Path]]:
    strict: dict[str, Path] = {}
    for role in sorted(BOOTSTRAP.STRICT_INPUT_ROLES):
        if role in BOOTSTRAP.JSON_INPUT_ROLES:
            raw = b'{"fixture":true}\n'
        else:
            raw = f"fixture {role}\n".encode()
        strict[role] = _write(tmp_path / "inputs" / role, raw)
    system = {
        role: _write(
            tmp_path / "system" / role,
            f"fixture executable {role}\n".encode(),
        )
        for role in sorted(BOOTSTRAP.SYSTEM_TOOL_ROLES)
    }
    return strict, system


def _capture_result(
    tmp_path: Path,
    system: dict[str, Path],
) -> dict[str, object]:
    manager = _write(tmp_path / "system" / "systemd-manager", b"manager\n")
    attestor = RESEARCH / "manager_attestor_v4.py"
    state = {
        "boot_id": BOOT_ID,
        "dbus_unique_owner": ":1.77",
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 987654,
        "manager_version": "systemd 261.1",
    }
    attestation = {
        "manager_executable": _full(manager),
        "request": {
            "boot_id": state["boot_id"],
            "dbus_unique_owner": state["dbus_unique_owner"],
            "manager_pid": state["manager_pid"],
            "manager_pid_starttime": state["manager_pid_starttime"],
        },
        "schema": AUTH.ATTESTOR_SCHEMA,
        "status": "PASS",
    }
    tools = {
        "attestor": _full(attestor),
        "python": _full(system["attestor_python"]),
        "sudo": _full(system["sudo"]),
    }
    audit = AUTH.audit_attestor_source(attestor.read_bytes())
    invocation = {
        "argv": [
            str(system["sudo"]),
            "-n",
            "--",
            str(system["attestor_python"]),
            "-I",
            "-c",
            AUTH._LOADER,  # noqa: SLF001
            "--pid",
            str(state["manager_pid"]),
            "--expected-starttime",
            str(state["manager_pid_starttime"]),
            "--expected-boot-id",
            str(state["boot_id"]),
            "--dbus-owner",
            str(state["dbus_unique_owner"]),
        ],
        "exit_code": 0,
        "stdin_sha256": tools["attestor"]["sha256"],
        "stdin_size_bytes": tools["attestor"]["size_bytes"],
        "stdout_base64": base64.b64encode(AUTH.canonical_json(attestation)).decode("ascii"),
    }

    def invoke(
        _: dict[str, object],
    ) -> tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ]:
        return (
            copy.deepcopy(attestation),
            copy.deepcopy(tools),
            {
                "audit": copy.deepcopy(audit),
                "invocation": copy.deepcopy(invocation),
            },
        )

    clock = iter((10, 20, 30, 40))
    return AUTH.capture_manager_epoch_with_transcript(
        attestor_path=attestor,
        busctl_path=system["busctl"],
        python_path=system["attestor_python"],
        sudo_path=system["sudo"],
        probe=lambda _: copy.deepcopy(state),
        invoke=invoke,
        monotonic_ns=lambda: next(clock),
    )


def _bootstrap_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    name: str,
    formal: bool,
) -> tuple[dict[str, Any], dict[str, Path], dict[str, Path]]:
    strict, system = _fixture_sources(tmp_path)
    capture = _capture_result(tmp_path, system)
    monkeypatch.setattr(
        AUTH,
        "capture_manager_epoch_with_transcript",
        lambda **_: copy.deepcopy(capture),
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_observe_repository_head",
        lambda *_: HEAD,
    )
    result = BOOTSTRAP.bootstrap_campaign(
        tmp_path / "campaigns" / name,
        repository_root=ROOT,
        formal_campaign=formal,
        strict_input_paths=strict,
        system_tool_paths=system,
        created_at_utc=NOW,
    )
    return result, strict, system


@pytest.mark.parametrize(
    ("name", "formal", "expected_mode"),
    (
        ("dev-drill-fixture-a001", False, "dev-drill"),
        ("run-fixture-a001", True, "formal"),
    ),
)
def test_bootstrap_seals_selected_bytes_and_only_preregisters_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    formal: bool,
    expected_mode: str,
) -> None:
    (tmp_path / "campaigns").mkdir()
    result, strict, system = _bootstrap_fixture(
        tmp_path,
        monkeypatch,
        name=name,
        formal=formal,
    )
    campaign = Path(result["campaign_dir"])
    root_snapshot = AUTH.snapshot_regular(campaign / "campaign-root.json")
    root = AUTH.validate_campaign_root(
        AUTH.strict_loads(root_snapshot.data, "campaign root"),
        campaign_dir=campaign,
    )
    selection_snapshot = AUTH.snapshot_regular(root["stage_topology"]["gate1_v4"]["selection_path"])
    selection = AUTH.load_gate1_selection_bytes(
        selection_snapshot.data,
        AUTH.detached_identity(selection_snapshot),
    )

    assert result["campaign_mode"] == expected_mode
    assert result["status"] == "AUTHORITY_READY_NO_UNIT_LAUNCHED"
    assert result["formal_arm_launch_authorized"] is False
    assert result["organic_ab16_authorized"] is False
    assert root["campaign_closed"] is False
    assert selection["campaign_root_identity"] == result["campaign_root_identity"]
    assert {
        "gate1_campaign_bootstrap_v4",
        "gate1_campaign_execution_v4",
    } <= set(selection["tools"])

    package_dir = Path(root["package"]["package_dir"])
    for role in BOOTSTRAP.SCRIPT_TOOL_FILES:
        selected = Path(selection["tools"][role]["path"])
        if role == "manager_attestor_v4":
            assert selected == RESEARCH / "manager_attestor_v4.py"
            assert selection["tools"][role] == {
                key: root["manager_epoch"]["attestation_toolchain"]["attestor"][key]
                for key in ("path", "size_bytes", "sha256")
            }
            continue
        expected_name = "campaign_authority_v4.py" if role == "campaign_authority_v4" else f"tool.{role}.py"
        assert selected == package_dir / "payload" / expected_name
        assert selected.suffix == ".py"
        assert selected.read_bytes() == (RESEARCH / BOOTSTRAP.SCRIPT_TOOL_FILES[role]).read_bytes()
    for role in BOOTSTRAP.SYSTEM_TOOL_ROLES:
        assert Path(selection["tools"][role]["path"]) == Path(system[role]).resolve()
    assert selection["inputs"]["project_lock"] == AUTH.detached_identity(AUTH.snapshot_regular(strict["project_lock"]))

    positive = root["stage_topology"]["gate1_v4"]["positive_control"]
    assert Path(positive["common_manifest_path"]).parent.name == "common-prestate"
    assert {Path(path).name for path in positive["binding_paths"].values()} == {"control.json", "treatment.json"}
    prospective = root["stage_topology"]["prospective_ab16"]
    assert len(prospective["arms"]) == 16
    gate = root["stage_topology"]["gate1_v4"]
    assert Path(gate["gate_admission_epoch_path"]) == (
        campaign / "gate1-v4" / "authority" / "manager-epoch-gate-admission.json"
    )
    assert gate["gate_admission_epoch_schema"] == (AUTH.GATE_ADMISSION_EPOCH_SCHEMA)
    selection_path = Path(gate["selection_path"])
    assert selection_path.is_file()
    for path in AUTH.reserved_child_paths(root):
        if path != selection_path:
            assert not path.exists()
            assert not path.is_symlink()

    capture_input = selection["inputs"][BOOTSTRAP.BOOTSTRAP_CAPTURE_INPUT_ROLE]
    capture_value = AUTH.strict_loads(
        AUTH.replay_detached_identity(
            capture_input,
            "bootstrap capture",
        ).data,
        "bootstrap capture",
    )
    assert capture_value["campaign_mode"] == expected_mode
    assert capture_value["formal_creation_explicitly_authorized"] is formal
    assert (
        AUTH.verify_package(
            package_dir,
            expected_manager_epoch=root["manager_epoch"],
            replay_external=True,
        )["status"]
        == "PASS"
    )
    assert selection["tools"]["attestor_python"] == {
        key: root["manager_epoch"]["attestation_toolchain"]["python"][key] for key in ("path", "size_bytes", "sha256")
    }
    assert selection["tools"]["busctl"] == {
        key: root["manager_epoch"]["observation_toolchain"]["busctl"][key] for key in ("path", "size_bytes", "sha256")
    }
    assert selection["tools"]["sudo"] == {
        key: root["manager_epoch"]["attestation_toolchain"]["sudo"][key] for key in ("path", "size_bytes", "sha256")
    }


def test_system_tool_symlink_is_resolved_and_binds_real_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "campaigns"
    parent.mkdir()
    strict, system = _fixture_sources(tmp_path)
    target = system["python3_13"]
    requested = tmp_path / "requested-python3.13"
    requested.symlink_to(target)
    system["python3_13"] = requested
    capture = _capture_result(tmp_path, system)
    monkeypatch.setattr(
        AUTH,
        "capture_manager_epoch_with_transcript",
        lambda **_: copy.deepcopy(capture),
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_observe_repository_head",
        lambda *_: HEAD,
    )
    result = BOOTSTRAP.bootstrap_campaign(
        parent / "dev-drill-symlinked-system-tool",
        repository_root=ROOT,
        formal_campaign=False,
        strict_input_paths=strict,
        system_tool_paths=system,
        created_at_utc=NOW,
    )
    root_snapshot = AUTH.snapshot_regular(Path(result["campaign_dir"]) / "campaign-root.json")
    root = AUTH.validate_campaign_root(
        AUTH.strict_loads(root_snapshot.data, "campaign root"),
        campaign_dir=result["campaign_dir"],
    )
    selection_snapshot = AUTH.snapshot_regular(root["stage_topology"]["gate1_v4"]["selection_path"])
    selection = AUTH.load_gate1_selection_bytes(
        selection_snapshot.data,
        AUTH.detached_identity(selection_snapshot),
    )
    expected = AUTH.detached_identity(AUTH.snapshot_regular(target.resolve()))
    assert selection["tools"]["python3_13"] == expected
    assert Path(selection["tools"]["python3_13"]["path"]) == target.resolve()


def test_canonical_rules_float_is_preserved_as_raw_byte_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "campaigns"
    parent.mkdir()
    strict, system = _fixture_sources(tmp_path)
    rules_raw = b'{"example_float":2.0,"nested":[1.5]}\n'
    strict["canonical_rules"].write_bytes(rules_raw)
    capture = _capture_result(tmp_path, system)
    monkeypatch.setattr(
        AUTH,
        "capture_manager_epoch_with_transcript",
        lambda **_: copy.deepcopy(capture),
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_observe_repository_head",
        lambda *_: HEAD,
    )
    result = BOOTSTRAP.bootstrap_campaign(
        parent / "dev-drill-raw-rules",
        repository_root=ROOT,
        formal_campaign=False,
        strict_input_paths=strict,
        system_tool_paths=system,
        created_at_utc=NOW,
    )
    root_snapshot = AUTH.snapshot_regular(Path(result["campaign_dir"]) / "campaign-root.json")
    root = AUTH.validate_campaign_root(
        AUTH.strict_loads(root_snapshot.data, "campaign root"),
        campaign_dir=result["campaign_dir"],
    )
    selection_snapshot = AUTH.snapshot_regular(root["stage_topology"]["gate1_v4"]["selection_path"])
    selection = AUTH.load_gate1_selection_bytes(
        selection_snapshot.data,
        AUTH.detached_identity(selection_snapshot),
    )
    selected_rules = AUTH.replay_detached_identity(
        selection["inputs"]["canonical_rules"],
        "selected canonical rules",
    )
    assert selected_rules.data == rules_raw


def test_mode_authorization_and_exact_allowlists_fail_before_creation(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "campaigns"
    parent.mkdir()
    strict, system = _fixture_sources(tmp_path)
    with pytest.raises(BOOTSTRAP.BootstrapError, match="requires explicit"):
        BOOTSTRAP.bootstrap_campaign(
            parent / "run-no-flag",
            repository_root=ROOT,
            formal_campaign=False,
            strict_input_paths=strict,
            system_tool_paths=system,
            created_at_utc=NOW,
        )
    with pytest.raises(BOOTSTRAP.BootstrapError, match="rejects formal"):
        BOOTSTRAP.bootstrap_campaign(
            parent / "dev-drill-with-flag",
            repository_root=ROOT,
            formal_campaign=True,
            strict_input_paths=strict,
            system_tool_paths=system,
            created_at_utc=NOW,
        )
    missing = dict(strict)
    missing.pop("project_lock")
    with pytest.raises(BOOTSTRAP.BootstrapError, match="exact pre-registered"):
        BOOTSTRAP.bootstrap_campaign(
            parent / "dev-drill-missing-input",
            repository_root=ROOT,
            formal_campaign=False,
            strict_input_paths=missing,
            system_tool_paths=system,
            created_at_utc=NOW,
        )
    assert list(parent.iterdir()) == []


def test_no_overwrite_stops_before_a_second_live_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "campaigns").mkdir()
    result, strict, system = _bootstrap_fixture(
        tmp_path,
        monkeypatch,
        name="dev-drill-no-overwrite",
        formal=False,
    )
    campaign = Path(result["campaign_dir"])
    before = {
        path.relative_to(campaign).as_posix(): path.read_bytes() for path in campaign.rglob("*") if path.is_file()
    }
    captures = 0

    def forbidden_capture(**_: object) -> object:
        nonlocal captures
        captures += 1
        raise AssertionError("existing campaign must fail before live capture")

    monkeypatch.setattr(
        AUTH,
        "capture_manager_epoch_with_transcript",
        forbidden_capture,
    )
    with pytest.raises(BOOTSTRAP.BootstrapError, match="already exists"):
        BOOTSTRAP.bootstrap_campaign(
            campaign,
            repository_root=ROOT,
            formal_campaign=False,
            strict_input_paths=strict,
            system_tool_paths=system,
            created_at_utc=NOW,
        )
    after = {path.relative_to(campaign).as_posix(): path.read_bytes() for path in campaign.rglob("*") if path.is_file()}
    assert captures == 0
    assert after == before


def test_head_drift_before_creation_leaves_no_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "campaigns"
    parent.mkdir()
    strict, system = _fixture_sources(tmp_path)
    capture = _capture_result(tmp_path, system)
    monkeypatch.setattr(
        AUTH,
        "capture_manager_epoch_with_transcript",
        lambda **_: copy.deepcopy(capture),
    )
    heads = iter((HEAD, "4" * 40))
    monkeypatch.setattr(
        BOOTSTRAP,
        "_observe_repository_head",
        lambda *_: next(heads),
    )
    campaign = parent / "dev-drill-head-drift"
    with pytest.raises(BOOTSTRAP.BootstrapError, match="HEAD drifted"):
        BOOTSTRAP.bootstrap_campaign(
            campaign,
            repository_root=ROOT,
            formal_campaign=False,
            strict_input_paths=strict,
            system_tool_paths=system,
            created_at_utc=NOW,
        )
    assert not campaign.exists()


def test_symlink_campaign_leaf_is_rejected_without_following(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "campaigns"
    parent.mkdir()
    target = tmp_path / "elsewhere"
    target.mkdir()
    link = parent / "dev-drill-link"
    link.symlink_to(target, target_is_directory=True)
    strict, system = _fixture_sources(tmp_path)
    with pytest.raises(BOOTSTRAP.BootstrapError, match="already exists"):
        BOOTSTRAP.bootstrap_campaign(
            link,
            repository_root=ROOT,
            formal_campaign=False,
            strict_input_paths=strict,
            system_tool_paths=system,
            created_at_utc=NOW,
        )
    assert list(target.iterdir()) == []
