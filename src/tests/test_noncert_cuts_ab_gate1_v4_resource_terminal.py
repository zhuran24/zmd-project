from __future__ import annotations

import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Mapping, Sequence

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"
LIFECYCLE_PATH = TOOLS / "resource_lifecycle_v4.py"
VERIFIER_PATH = TOOLS / "resource_verifier_v4.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


LIFECYCLE = _load("cuts_gate1_v4_resource_lifecycle_test", LIFECYCLE_PATH)
VERIFIER = _load("cuts_gate1_v4_resource_verifier_test", VERIFIER_PATH)


def _write_json(path: Path, value: object) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(LIFECYCLE.canonical_json_bytes(value))
    _, identity = LIFECYCLE.snapshot_regular(path)
    return identity


def _identity(path: Path) -> dict[str, object]:
    _, result = LIFECYCLE.snapshot_regular(path)
    return result


def _raw_value(raw: bytes) -> dict[str, str]:
    return {
        "base64": base64.b64encode(raw).decode("ascii"),
        "sha256": __import__("hashlib").sha256(raw).hexdigest(),
    }


def _command(
    unit: str,
    fields: Sequence[str],
    values: Mapping[str, str],
) -> Any:
    stdout = "".join(f"{name}={values[name]}\n" for name in fields).encode()
    return LIFECYCLE.CommandEvidence(
        argv=LIFECYCLE._show_argv(unit, fields),
        exit_code=0,
        stdout=stdout,
        stderr=b"",
    )


def _command_record_with_field(
    record: dict[str, object],
    fields: Sequence[str],
    raw: dict[str, str],
    name: str,
    value: str,
) -> None:
    raw[name] = value
    stdout = "".join(f"{field}={raw[field]}\n" for field in fields).encode()
    record["stdout_base64"] = base64.b64encode(stdout).decode("ascii")
    record["stdout_sha256"] = __import__("hashlib").sha256(stdout).hexdigest()


class FakeAdapter:
    def __init__(
        self,
        *,
        unit: str,
        invocation: str,
        keeper_pid: int,
        keeper_starttime: int,
        payload_pid: int,
        returncode: int,
        profile: Mapping[str, int],
        duration_text: str | None = None,
        reset_not_loaded: bool = False,
    ) -> None:
        self.unit = unit
        self.invocation = invocation
        self.keeper_pid = keeper_pid
        self.keeper_starttime = keeper_starttime
        self.payload_pid = payload_pid
        self.returncode = returncode
        self.profile = profile
        self.duration_text = duration_text
        self.reset_not_loaded = reset_not_loaded
        self.phase = "preterminal"
        self.cleaned = False
        self.group = f"/user.slice/user-1000.slice/{unit}"

    def _contract(self) -> dict[str, str]:
        return {
            "MemoryHigh": str(LIFECYCLE.MEMORY_HIGH),
            "MemoryMax": str(LIFECYCLE.MEMORY_MAX),
            "MemorySwapMax": str(LIFECYCLE.MEMORY_SWAP_MAX),
            "OOMPolicy": "continue",
            "KillMode": "control-group",
            "SendSIGKILL": "yes",
            "RuntimeMaxUSec": (
                self.duration_text
                if self.duration_text is not None
                else str(self.profile["runtime_max_seconds"] * 1_000_000)
            ),
        }

    def show(self, unit_name: str, fields: Sequence[str]) -> Any:
        assert unit_name == self.unit
        if tuple(fields) == LIFECYCLE.SYSTEMD_PRETERMINAL_FIELDS:
            values = {
                "ActiveState": "active",
                "SubState": "running",
                "MainPID": str(self.keeper_pid),
                "InvocationID": self.invocation,
                "ControlGroup": self.group,
                **self._contract(),
                "Result": "",
                "ExecMainCode": "0",
                "ExecMainStatus": "0",
                "ExecMainStartTimestampMonotonic": "100",
            }
        elif tuple(fields) == LIFECYCLE.SYSTEMD_TERMINAL_FIELDS:
            assert self.phase in {"terminal", "cleanup"}
            failed = self.returncode != 0
            values = {
                "ActiveState": "failed" if failed else "active",
                "SubState": "failed" if failed else "exited",
                "Result": "exit-code" if failed else "success",
                "ExecMainCode": "1",
                "ExecMainStatus": str(self.returncode),
                "MainPID": "0",
                "InvocationID": self.invocation,
                "ControlGroup": "",
                **self._contract(),
                "ExecMainStartTimestampMonotonic": "100",
                "ExecMainExitTimestampMonotonic": "200",
            }
        else:
            raise AssertionError(f"unexpected systemd field set: {fields}")
        return _command(unit_name, fields, values)

    def read_cgroup(
        self,
        control_group: str,
        fields: Sequence[str],
    ) -> Mapping[str, bytes]:
        assert control_group == self.group
        assert tuple(fields) == LIFECYCLE.CGROUP_RAW_FIELDS
        return {
            "memory.high": f"{LIFECYCLE.MEMORY_HIGH}\n".encode(),
            "memory.max": f"{LIFECYCLE.MEMORY_MAX}\n".encode(),
            "memory.swap.max": f"{LIFECYCLE.MEMORY_SWAP_MAX}\n".encode(),
            "memory.current": b"100\n",
            "memory.peak": b"200\n",
            "memory.swap.current": b"0\n",
            "memory.swap.peak": b"0\n",
            "memory.events": (b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n"),
            "memory.events.local": (b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n"),
            "cgroup.procs": f"{self.keeper_pid}\n".encode(),
            "cgroup.events": b"populated 1\nfrozen 0\n",
        }

    def pid_starttime(self, pid: int) -> int | None:
        if self.cleaned:
            return None
        if pid == self.keeper_pid:
            return self.keeper_starttime
        if pid == self.payload_pid:
            return None
        raise AssertionError(f"unexpected pid {pid}")

    def cgroup_exists(self, control_group: str) -> bool:
        assert control_group == self.group
        return not self.cleaned

    def cleanup(self, unit_name: str) -> Sequence[Any]:
        assert unit_name == self.unit
        self.cleaned = True
        self.phase = "cleanup"
        return (
            LIFECYCLE.CommandEvidence(
                argv=(
                    str(LIFECYCLE.SYSTEMCTL),
                    "--user",
                    "stop",
                    unit_name,
                ),
                exit_code=0,
                stdout=b"",
                stderr=b"",
            ),
            LIFECYCLE.CommandEvidence(
                argv=(str(LIFECYCLE.SYSTEMCTL), "--user", "reset-failed", unit_name),
                exit_code=1 if self.reset_not_loaded else 0,
                stdout=b"",
                stderr=(
                    (f"Failed to reset failed state of unit {unit_name}: Unit {unit_name} not loaded.\n").encode()
                    if self.reset_not_loaded
                    else b""
                ),
            ),
        )

    def load_state(self, unit_name: str) -> Any:
        assert unit_name == self.unit
        assert self.cleaned
        return LIFECYCLE.CommandEvidence(
            argv=LIFECYCLE._load_state_argv(unit_name),
            exit_code=0,
            stdout=b"not-found\n",
            stderr=b"",
        )


def _make_selection(tmp_path: Path) -> Any:
    source = tmp_path / "source.py"
    source.write_text("# pinned source\n", encoding="utf-8")
    strict = tmp_path / "strict.json"
    strict.write_text("{}\n", encoding="utf-8")
    source_identity = _identity(source)
    strict_identity = _identity(strict)
    campaign_id = "a" * 64
    units: dict[str, object] = {}
    for slot in LIFECYCLE.UNIT_SLOTS:
        attempt = tmp_path / "campaign" / "gate1-v4" / slot
        raw_dir = attempt / "raw"
        terminal_dir = attempt / "terminal"
        raw_dir.mkdir(parents=True)
        terminal_dir.mkdir()
        units[slot] = {
            "slot": slot,
            "unit_name": f"cuts-g1v4-{campaign_id[:12]}-{slot}.service",
            "attempt_dir": str(attempt),
            "epoch_checkpoint_paths": {
                phase: str(attempt / "authority" / f"manager-epoch-{phase}.json")
                for phase in (
                    "prelaunch",
                    "preterminal",
                    "terminal",
                    "cleanup",
                    "detached-replay",
                )
            },
            "raw_dir": str(raw_dir),
            "terminal_dir": str(terminal_dir),
            "result_path": str(attempt / "result.json"),
            "contract_profile": ("synthetic" if slot in LIFECYCLE.SYNTHETIC_SLOTS else "formal"),
        }
    root_file = tmp_path / "campaign-root.json"
    root_file.write_text('{"root":true}\n', encoding="utf-8")
    selection: dict[str, object] = {
        "schema_version": LIFECYCLE.SELECTION_SCHEMA,
        "created_at_utc": "2026-07-24T00:00:00Z",
        "purpose": "gate1_v4_child_suite",
        "campaign_id": campaign_id,
        "run_nonce": "run-v4-fixture",
        "package_id": "b" * 64,
        "repository_head": "c" * 40,
        "campaign_root_identity": _identity(root_file),
        "manager_epoch": {
            "schema": "systemd-user-manager-boot-epoch-v1",
            "boot_id": "d" * 32,
            "owner": ":1.42",
        },
        "resource_contract": copy.deepcopy(LIFECYCLE.RESOURCE_CONTRACT),
        "tools": {
            "resource_lifecycle_v4": _identity(LIFECYCLE_PATH),
            "resource_verifier_v4": _identity(VERIFIER_PATH),
            "fixture_source": source_identity,
        },
        "inputs": {"strict_instance": strict_identity},
        "units": units,
        "selection_id": "",
    }
    body = dict(selection)
    body.pop("selection_id")
    selection["selection_id"] = LIFECYCLE._canonical_digest(body)
    selection_path = tmp_path / "campaign" / "gate1-v4" / "selection-a001.json"
    selection_identity = _write_json(selection_path, selection)
    return LIFECYCLE.load_gate1_selection(
        selection_path,
        expected_identity=selection_identity,
    )


def _write_inner(selection: Any, slot: str) -> dict[str, object]:
    paths = LIFECYCLE.lifecycle_paths(selection.value, slot)
    expected = LIFECYCLE.EXPECTED_RETURNCODE[slot]
    invocation = ("1" if slot != "q-postseal-fail" else "2") * 32
    seal_identity = _write_json(
        paths["payload_seal"],
        {
            "schema_version": "fixture-payload-seal-v1",
            "selection_identity": selection.identity,
            "payload_result_identity": {
                "path": str(paths["result"]),
                "size_bytes": 0,
                "sha256": "0" * 64,
            },
        },
    )
    result_identity = _write_json(paths["result"], {"status": "fixture"})
    keeper = 4101
    payload = 4102
    inner = {
        "schema_version": LIFECYCLE.INNER_SCHEMA,
        "created_at_utc": "2026-07-24T00:00:01Z",
        "selection_identity": selection.identity,
        "campaign_id": selection.value["campaign_id"],
        "run_nonce": selection.value["run_nonce"],
        "selection_id": selection.value["selection_id"],
        "manager_epoch_digest": LIFECYCLE._canonical_digest(selection.value["manager_epoch"]),
        "unit_slot": slot,
        "unit_name": selection.value["units"][slot]["unit_name"],
        "invocation_id": invocation,
        "contract_profile": selection.value["units"][slot]["contract_profile"],
        "payload_argv": ["/usr/bin/true"],
        "supervisor_pid": keeper,
        "supervisor_starttime": 1001,
        "payload_pid": payload,
        "payload_starttime": 1002,
        "payload_spawned_monotonic_ns": 10,
        "payload_reaped_monotonic_ns": 20,
        "payload_reaped": True,
        "payload_timed_out": False,
        "payload_returncode": expected,
        "waitid": {
            "si_pid": payload,
            "si_uid": 1000,
            "si_signo": 17,
            "si_status": expected,
            "si_code": os.CLD_EXITED,
        },
        "payload_seal_identity": seal_identity,
        "payload_result_identity": result_identity,
        "keeper_pid": keeper,
        "keeper_starttime": 1001,
        "keeper_ready_monotonic_ns": 30,
    }
    return _write_json(paths["inner"], inner)


def _full_fixture(
    tmp_path: Path,
    slot: str = "q-success",
    *,
    duration_text: str | None = None,
    reset_not_loaded: bool = False,
) -> dict[str, Any]:
    selection = _make_selection(tmp_path)
    inner_identity = _write_inner(selection, slot)
    inner_raw, _ = LIFECYCLE.snapshot_regular(LIFECYCLE.lifecycle_paths(selection.value, slot)["inner"])
    unit = selection.value["units"][slot]
    profile = selection.value["resource_contract"]["profiles"][unit["contract_profile"]]
    adapter = FakeAdapter(
        unit=unit["unit_name"],
        invocation=("2" if slot == "q-postseal-fail" else "1") * 32,
        keeper_pid=4101,
        keeper_starttime=1001,
        payload_pid=4102,
        returncode=LIFECYCLE.EXPECTED_RETURNCODE[slot],
        profile=profile,
        duration_text=duration_text,
        reset_not_loaded=reset_not_loaded,
    )
    pre, pre_identity = LIFECYCLE.capture_preterminal(
        selection=selection,
        unit_slot=slot,
        adapter=adapter,
        now_utc=lambda: "2026-07-24T00:00:02Z",
        monotonic_ns=lambda: 40,
    )
    pre_raw = LIFECYCLE.canonical_json_bytes(pre)
    verifier_identity = _identity(VERIFIER_PATH)
    receipt = VERIFIER.verify_preterminal_bytes(
        selection_raw=selection.raw,
        selection_identity=selection.identity,
        unit_slot=slot,
        inner_raw=inner_raw,
        inner_identity=inner_identity,
        preterminal_raw=pre_raw,
        preterminal_identity=pre_identity,
        verifier_identity=verifier_identity,
        created_at_utc="2026-07-24T00:00:03Z",
    )
    paths = LIFECYCLE.lifecycle_paths(selection.value, slot)
    resource_identity = _write_json(paths["resource_verification"], receipt)
    release = VERIFIER.build_release_token(
        receipt,
        resource_identity,
        released_monotonic_ns=50,
        created_at_utc="2026-07-24T00:00:04Z",
    )
    release_identity = _write_json(paths["release"], release)
    adapter.phase = "terminal"
    terminal, terminal_identity = LIFECYCLE.capture_terminal(
        selection=selection,
        unit_slot=slot,
        adapter=adapter,
        preterminal_identity=pre_identity,
        release_identity=release_identity,
        monotonic=lambda: 1.0,
        monotonic_ns=lambda: 60,
        now_utc=lambda: "2026-07-24T00:00:05Z",
    )
    cleanup, cleanup_identity = LIFECYCLE.capture_cleanup(
        selection=selection,
        unit_slot=slot,
        adapter=adapter,
        terminal_identity=terminal_identity,
        monotonic_ns=lambda: 70,
        now_utc=lambda: "2026-07-24T00:00:06Z",
    )
    return {
        "selection": selection,
        "slot": slot,
        "paths": paths,
        "inner": json.loads(inner_raw),
        "inner_raw": inner_raw,
        "inner_identity": inner_identity,
        "pre": pre,
        "pre_raw": pre_raw,
        "pre_identity": pre_identity,
        "resource": receipt,
        "resource_raw": LIFECYCLE.canonical_json_bytes(receipt),
        "resource_identity": resource_identity,
        "release": release,
        "release_raw": LIFECYCLE.canonical_json_bytes(release),
        "release_identity": release_identity,
        "terminal": terminal,
        "terminal_raw": LIFECYCLE.canonical_json_bytes(terminal),
        "terminal_identity": terminal_identity,
        "cleanup": cleanup,
        "cleanup_raw": LIFECYCLE.canonical_json_bytes(cleanup),
        "cleanup_identity": cleanup_identity,
        "verifier_identity": verifier_identity,
    }


def _detached(fixture: Mapping[str, Any]) -> dict[str, object]:
    return VERIFIER.verify_detached_bytes(
        selection_raw=fixture["selection"].raw,
        selection_identity=fixture["selection"].identity,
        unit_slot=fixture["slot"],
        inner_raw=fixture["inner_raw"],
        inner_identity=fixture["inner_identity"],
        preterminal_raw=fixture["pre_raw"],
        preterminal_identity=fixture["pre_identity"],
        resource_raw=fixture["resource_raw"],
        resource_identity=fixture["resource_identity"],
        release_raw=fixture["release_raw"],
        release_identity=fixture["release_identity"],
        terminal_raw=fixture["terminal_raw"],
        terminal_identity=fixture["terminal_identity"],
        cleanup_raw=fixture["cleanup_raw"],
        cleanup_identity=fixture["cleanup_identity"],
        verifier_identity=fixture["verifier_identity"],
        created_at_utc="2026-07-24T00:00:07Z",
    )


@pytest.mark.parametrize(
    ("slot", "terminal_class"),
    [
        ("q-success", "success"),
        ("q-postseal-fail", "postseal-failure"),
        ("forced-control", "success"),
        ("forced-treatment", "success"),
    ],
)
def test_two_stage_fake_adapter_replay_passes(
    tmp_path: Path,
    slot: str,
    terminal_class: str,
) -> None:
    receipt = _detached(_full_fixture(tmp_path, slot))
    assert receipt["status"] == "PASS"
    assert receipt["terminal_class"] == terminal_class
    assert receipt["derived"]["keeper_only"] is True
    assert receipt["derived"]["payload_status_preserved"] is True
    assert receipt["derived"]["unit_absent"] is True
    assert receipt["mechanism_credible_authorized"] is False
    assert receipt["organic_arm_launch_authorized"] is False


@pytest.mark.parametrize(
    ("field", "raw"),
    [
        ("memory.max", b"1\n"),
        (
            "memory.events",
            b"low 0\nhigh 0\nmax 0\noom 1\noom_kill 0\noom_group_kill 0\n",
        ),
        ("cgroup.procs", b"4101\n9999\n"),
        ("cgroup.events", b"populated 0\nfrozen 0\n"),
    ],
)
def test_preterminal_resource_mutations_fail_closed(
    tmp_path: Path,
    field: str,
    raw: bytes,
) -> None:
    fixture = _full_fixture(tmp_path)
    mutated = copy.deepcopy(fixture["pre"])
    mutated["cgroup_raw"][field] = _raw_value(raw)
    raw_pre = LIFECYCLE.canonical_json_bytes(mutated)
    identity = {
        "path": fixture["pre_identity"]["path"],
        "size_bytes": len(raw_pre),
        "sha256": __import__("hashlib").sha256(raw_pre).hexdigest(),
    }
    with pytest.raises(VERIFIER.VerificationError):
        VERIFIER.verify_preterminal_bytes(
            selection_raw=fixture["selection"].raw,
            selection_identity=fixture["selection"].identity,
            unit_slot=fixture["slot"],
            inner_raw=fixture["inner_raw"],
            inner_identity=fixture["inner_identity"],
            preterminal_raw=raw_pre,
            preterminal_identity=identity,
            verifier_identity=fixture["verifier_identity"],
            created_at_utc="2026-07-24T00:00:08Z",
        )


@pytest.mark.parametrize(
    ("events_raw", "local_raw", "expected_error"),
    [
        (
            b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\nsock_throttled 0\n",
            b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\nsock_throttled 0\n",
            None,
        ),
        (
            b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\nsock_throttled 1\n",
            b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\nsock_throttled 1\n",
            "unsupported nonzero optional memory event",
        ),
        (
            b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\nfuture_counter 0\n",
            b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\nfuture_counter 0\n",
            "memory event field set drifted",
        ),
        (
            b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\nsock_throttled 0\n",
            b"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n",
            "memory event field set drifted",
        ),
    ],
)
def test_preterminal_supported_memory_event_schema_is_fail_closed(
    tmp_path: Path,
    events_raw: bytes,
    local_raw: bytes,
    expected_error: str | None,
) -> None:
    fixture = _full_fixture(tmp_path)
    mutated = copy.deepcopy(fixture["pre"])
    mutated["cgroup_raw"]["memory.events"] = _raw_value(events_raw)
    mutated["cgroup_raw"]["memory.events.local"] = _raw_value(local_raw)
    raw_pre = LIFECYCLE.canonical_json_bytes(mutated)
    identity = {
        "path": fixture["pre_identity"]["path"],
        "size_bytes": len(raw_pre),
        "sha256": __import__("hashlib").sha256(raw_pre).hexdigest(),
    }
    arguments = {
        "selection_raw": fixture["selection"].raw,
        "selection_identity": fixture["selection"].identity,
        "unit_slot": fixture["slot"],
        "inner_raw": fixture["inner_raw"],
        "inner_identity": fixture["inner_identity"],
        "preterminal_raw": raw_pre,
        "preterminal_identity": identity,
        "verifier_identity": fixture["verifier_identity"],
        "created_at_utc": "2026-07-24T00:00:08Z",
    }
    if expected_error is None:
        assert VERIFIER.verify_preterminal_bytes(**arguments)["status"] == "PASS"
    else:
        with pytest.raises(VERIFIER.VerificationError, match=expected_error):
            VERIFIER.verify_preterminal_bytes(**arguments)


def test_terminal_semantically_self_consistent_status_mutation_fails(
    tmp_path: Path,
) -> None:
    fixture = _full_fixture(tmp_path, "q-postseal-fail")
    terminal = copy.deepcopy(fixture["terminal"])
    _command_record_with_field(
        terminal["systemd_command"],
        LIFECYCLE.SYSTEMD_TERMINAL_FIELDS,
        terminal["systemd_raw"],
        "ExecMainStatus",
        "0",
    )
    raw = LIFECYCLE.canonical_json_bytes(terminal)
    fixture["terminal_raw"] = raw
    fixture["terminal_identity"] = {
        "path": fixture["terminal_identity"]["path"],
        "size_bytes": len(raw),
        "sha256": __import__("hashlib").sha256(raw).hexdigest(),
    }
    fixture["cleanup"]["terminal_identity"] = fixture["terminal_identity"]
    fixture["cleanup_raw"] = LIFECYCLE.canonical_json_bytes(fixture["cleanup"])
    fixture["cleanup_identity"] = {
        "path": fixture["cleanup_identity"]["path"],
        "size_bytes": len(fixture["cleanup_raw"]),
        "sha256": __import__("hashlib").sha256(fixture["cleanup_raw"]).hexdigest(),
    }
    with pytest.raises(VERIFIER.VerificationError, match="payload status"):
        _detached(fixture)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cgroup_exists", True),
        ("keeper_current_starttime", 1001),
        ("terminal_control_group_used_as_cleanup_evidence", True),
    ],
)
def test_cleanup_absence_mutations_fail_closed(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    fixture = _full_fixture(tmp_path)
    cleanup = copy.deepcopy(fixture["cleanup"])
    cleanup[field] = value
    raw = LIFECYCLE.canonical_json_bytes(cleanup)
    fixture["cleanup_raw"] = raw
    fixture["cleanup_identity"] = {
        "path": fixture["cleanup_identity"]["path"],
        "size_bytes": len(raw),
        "sha256": __import__("hashlib").sha256(raw).hexdigest(),
    }
    with pytest.raises(VERIFIER.VerificationError, match="cleanup"):
        _detached(fixture)


def test_terminal_pruned_control_group_is_not_cleanup_evidence(tmp_path: Path) -> None:
    fixture = _full_fixture(tmp_path)
    assert fixture["terminal"]["systemd_raw"]["ControlGroup"] == ""
    assert fixture["terminal"]["terminal_control_group_used_as_cleanup_evidence"] is False
    assert fixture["cleanup"]["preterminal_control_group"].startswith("/")
    assert _detached(fixture)["status"] == "PASS"


@pytest.mark.parametrize(
    ("slot", "duration"),
    [("q-success", "2min"), ("forced-control", "25min")],
)
def test_systemd_human_duration_is_recomputed(
    tmp_path: Path,
    slot: str,
    duration: str,
) -> None:
    fixture = _full_fixture(tmp_path, slot, duration_text=duration)
    assert _detached(fixture)["status"] == "PASS"


def test_cleanup_accepts_exact_unit_not_loaded_reset_result(tmp_path: Path) -> None:
    fixture = _full_fixture(tmp_path, reset_not_loaded=True)
    assert fixture["cleanup"]["cleanup_commands"][1]["exit_code"] == 1
    assert _detached(fixture)["status"] == "PASS"


def test_detached_selection_bytes_reject_same_semantics_different_bytes(
    tmp_path: Path,
) -> None:
    selection = _make_selection(tmp_path)
    changed = json.dumps(selection.value, sort_keys=True, indent=2).encode() + b"\n"
    assert json.loads(changed) == selection.value
    with pytest.raises(LIFECYCLE.LifecycleError, match="detached bytes"):
        LIFECYCLE.load_gate1_selection_bytes(changed, selection.identity)
    with pytest.raises(VERIFIER.VerificationError, match="raw bytes"):
        VERIFIER._validate_selection(changed, selection.identity)


def test_snapshot_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}\n", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(LIFECYCLE.LifecycleError, match="symlink"):
        LIFECYCLE.snapshot_regular(link)
    with pytest.raises(VERIFIER.VerificationError, match="symlink"):
        VERIFIER.snapshot_regular(link)


def test_systemctl_adapter_commands_are_user_scoped() -> None:
    unit = "cuts-g1v4-aaaaaaaaaaaa-q-success.service"
    argv = LIFECYCLE._show_argv(unit, LIFECYCLE.SYSTEMD_PRETERMINAL_FIELDS)
    assert argv[:4] == ("/usr/bin/systemctl", "--user", "show", "--no-pager")
    assert argv[-1] == unit


def test_release_before_preterminal_is_rejected(tmp_path: Path) -> None:
    fixture = _full_fixture(tmp_path)
    release = copy.deepcopy(fixture["release"])
    release["released_monotonic_ns"] = fixture["pre"]["captured_monotonic_ns"]
    raw = LIFECYCLE.canonical_json_bytes(release)
    fixture["release_raw"] = raw
    fixture["release_identity"] = {
        "path": fixture["release_identity"]["path"],
        "size_bytes": len(raw),
        "sha256": __import__("hashlib").sha256(raw).hexdigest(),
    }
    fixture["terminal"]["release_identity"] = fixture["release_identity"]
    fixture["terminal_raw"] = LIFECYCLE.canonical_json_bytes(fixture["terminal"])
    fixture["terminal_identity"] = {
        "path": fixture["terminal_identity"]["path"],
        "size_bytes": len(fixture["terminal_raw"]),
        "sha256": __import__("hashlib").sha256(fixture["terminal_raw"]).hexdigest(),
    }
    fixture["cleanup"]["terminal_identity"] = fixture["terminal_identity"]
    fixture["cleanup_raw"] = LIFECYCLE.canonical_json_bytes(fixture["cleanup"])
    fixture["cleanup_identity"] = {
        "path": fixture["cleanup_identity"]["path"],
        "size_bytes": len(fixture["cleanup_raw"]),
        "sha256": __import__("hashlib").sha256(fixture["cleanup_raw"]).hexdigest(),
    }
    with pytest.raises(VERIFIER.VerificationError, match="follow preterminal"):
        _detached(fixture)


def test_supervisor_waitid_reaps_then_holds_as_keeper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection = _make_selection(tmp_path)
    slot = "q-success"
    paths = LIFECYCLE.lifecycle_paths(selection.value, slot)
    _write_json(paths["payload_seal"], {"schema_version": "fixture-seal-v1"})
    _write_json(paths["result"], {"status": "PASS"})

    class FakeProcess:
        pid = 4242
        returncode: int | None = None

        def wait(self, timeout: int | None = None) -> int:
            del timeout
            self.returncode = 0
            return 0

        def send_signal(self, _signal: int) -> None:
            raise AssertionError("clean fake payload must not receive a signal")

        def kill(self) -> None:
            raise AssertionError("clean fake payload must not be killed")

    process = FakeProcess()
    starts = {4241: 2001, 4242: 2002}

    def proc_starttime(pid: int) -> int | None:
        if pid == 4242 and process.returncode is not None:
            return None
        return starts.get(pid)

    monkeypatch.setattr(LIFECYCLE.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(LIFECYCLE.os, "getuid", lambda: 1000)
    monkeypatch.setattr(LIFECYCLE.os, "getpid", lambda: 4241)
    monkeypatch.setattr(LIFECYCLE, "_proc_starttime", proc_starttime)
    monkeypatch.setattr(
        LIFECYCLE,
        "_wait_without_reaping",
        lambda *_args, **_kwargs: SimpleNamespace(
            si_pid=4242,
            si_uid=1000,
            si_signo=17,
            si_status=0,
            si_code=os.CLD_EXITED,
        ),
    )

    ticks = iter(range(10, 10_000))

    def fake_sleep(_seconds: float) -> None:
        if paths["inner"].exists() and not paths["release"].exists():
            _, inner_identity = LIFECYCLE.snapshot_regular(paths["inner"])
            token = {
                "schema_version": LIFECYCLE.RELEASE_SCHEMA,
                "created_at_utc": "2026-07-24T00:00:00Z",
                "selection_identity": selection.identity,
                "campaign_id": selection.value["campaign_id"],
                "run_nonce": selection.value["run_nonce"],
                "selection_id": selection.value["selection_id"],
                "manager_epoch_digest": LIFECYCLE._canonical_digest(selection.value["manager_epoch"]),
                "unit_slot": slot,
                "unit_name": selection.value["units"][slot]["unit_name"],
                "invocation_id": "1" * 32,
                "inner_identity": inner_identity,
                "preterminal_identity": {
                    "path": str(paths["preterminal"]),
                    "size_bytes": 1,
                    "sha256": "1" * 64,
                },
                "resource_verification_identity": {
                    "path": str(paths["resource_verification"]),
                    "size_bytes": 1,
                    "sha256": "2" * 64,
                },
                "verdict": "RESOURCE_PRETERMINAL_PASS",
                "released_monotonic_ns": 100,
            }
            _write_json(paths["release"], token)

    returncode = LIFECYCLE.supervise_payload(
        selection=selection,
        unit_slot=slot,
        payload_argv=["/usr/bin/true"],
        invocation_id="1" * 32,
        popen=lambda *_args, **_kwargs: process,
        monotonic=lambda: float(next(ticks)),
        monotonic_ns=lambda: next(ticks),
        sleep=fake_sleep,
    )
    assert returncode == 0
    inner = json.loads(paths["inner"].read_bytes())
    assert inner["payload_reaped"] is True
    assert inner["keeper_pid"] == inner["supervisor_pid"] == 4241


def test_supervisor_cli_uses_systemd_invocation_id_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection = _make_selection(tmp_path)
    captured: list[str] = []
    monkeypatch.setenv("INVOCATION_ID", "a" * 32)
    monkeypatch.setattr(
        LIFECYCLE,
        "supervise_payload",
        lambda **kwargs: captured.append(kwargs["invocation_id"]) or 0,
    )
    assert (
        LIFECYCLE.main(
            [
                "supervisor",
                "--selection",
                str(selection.identity["path"]),
                "--selection-size",
                str(selection.identity["size_bytes"]),
                "--selection-sha256",
                str(selection.identity["sha256"]),
                "--unit-slot",
                "q-success",
                "/usr/bin/true",
            ]
        )
        == 0
    )
    assert captured == ["a" * 32]


def test_supervisor_cli_rejects_invocation_id_mismatch_or_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection = _make_selection(tmp_path)
    common = [
        "supervisor",
        "--selection",
        str(selection.identity["path"]),
        "--selection-size",
        str(selection.identity["size_bytes"]),
        "--selection-sha256",
        str(selection.identity["sha256"]),
        "--unit-slot",
        "q-success",
    ]
    monkeypatch.setenv("INVOCATION_ID", "a" * 32)
    with pytest.raises(LIFECYCLE.LifecycleError, match="differs"):
        LIFECYCLE.main(
            [
                *common,
                "--invocation-id",
                "b" * 32,
                "/usr/bin/true",
            ]
        )
    monkeypatch.delenv("INVOCATION_ID")
    with pytest.raises(LIFECYCLE.LifecycleError, match="absent"):
        LIFECYCLE.main([*common, "/usr/bin/true"])
