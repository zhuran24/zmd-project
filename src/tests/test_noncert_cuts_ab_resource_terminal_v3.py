from __future__ import annotations

import copy
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Mapping

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_ROOT = REPO_ROOT / "docs" / "research" / "noncert_cuts_ab_trust_gate1_v3_20260723"
RECORDER_PATH = TOOL_ROOT / "positive_control_resource_recorder_v2.py"
OBSERVER_PATH = TOOL_ROOT / "launch_selection_observer_v1.py"
VERIFIER_PATH = TOOL_ROOT / "independent_resource_verifier_v2.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECORDER = _load("gate1_resource_recorder_v2_test", RECORDER_PATH)
OBSERVER = _load("gate1_launch_observer_v1_test", OBSERVER_PATH)
VERIFIER = _load("gate1_resource_verifier_v2_test", VERIFIER_PATH)


def _dump(path: Path, value: object) -> None:
    path.write_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _load_json(path: Path) -> dict[str, object]:
    raw, _ = VERIFIER.snapshot_file(path)
    value = json.loads(raw.decode("utf-8"))
    assert isinstance(value, dict)
    return value


def _snapshot(
    *,
    arm: str,
    invocation_id: str,
    monotonic_ns: int,
    peak: int,
    cgroup_procs: list[int],
) -> dict[str, object]:
    cgroup_path = f"/gate1-{arm}.service"
    return {
        "observed_at_utc": "2026-07-23T00:00:00Z",
        "monotonic_ns": monotonic_ns,
        "unit_name": f"gate1-{arm}.service",
        "invocation_id": invocation_id,
        "cgroup_path": cgroup_path,
        "cgroup_dev": 29,
        "cgroup_inode": 100 if arm == "control" else 200,
        "memory": {
            "high": RECORDER.CONTRACT["memory_high_bytes"],
            "max": RECORDER.CONTRACT["memory_max_bytes"],
            "swap_max": RECORDER.CONTRACT["memory_swap_max_bytes"],
            "current": peak,
            "peak": peak,
            "swap_current": 0,
            "swap_peak": 0,
        },
        "memory_events": {
            "low": 0,
            "high": 0,
            "max": 0,
            "oom": 0,
            "oom_kill": 0,
            "oom_group_kill": 0,
        },
        "cgroup_procs": cgroup_procs,
        "ancestor_limits": [
            {
                "path": "/",
                "memory_high": None,
                "memory_max": None,
                "memory_swap_max": None,
            },
            {
                "path": cgroup_path,
                "memory_high": RECORDER.CONTRACT["memory_high_bytes"],
                "memory_max": RECORDER.CONTRACT["memory_max_bytes"],
                "memory_swap_max": RECORDER.CONTRACT["memory_swap_max_bytes"],
            },
        ],
        "systemd": {
            "memory_high_bytes": RECORDER.CONTRACT["memory_high_bytes"],
            "memory_max_bytes": RECORDER.CONTRACT["memory_max_bytes"],
            "memory_swap_max_bytes": RECORDER.CONTRACT["memory_swap_max_bytes"],
            "oom_policy": "continue",
            "kill_mode": "control-group",
            "send_sigkill": True,
            "runtime_max_seconds": 1500,
            "invocation_id": invocation_id,
            "control_group": cgroup_path,
        },
    }


def _raw_chain(
    *,
    arm: str,
    base: int,
    selection: dict[str, object],
    selection_identity: dict[str, object],
    result_identity: dict[str, object],
) -> bytes:
    invocation_id = ("1" if arm == "control" else "2") * 32
    pid = 4001 if arm == "control" else 4002
    selected_arm = selection["arms"][arm]
    cgroup_path = f"/gate1-{arm}.service"
    events = [
        (
            "GENESIS",
            {
                "observed_at_utc": "2026-07-23T00:00:00Z",
                "monotonic_ns": base,
                "run_nonce": selection["run_nonce"],
                "package_id": selection["package_id"],
                "selection_id": selection["selection_id"],
                "selection_identity": selection_identity,
                "arm": arm,
                "unit_name": selected_arm["unit_name"],
                "invocation_id": invocation_id,
                "repository_head": selection["repository_head"],
                "boot_id": "b" * 32,
                "recorder_pid": pid,
                "recorder_identity": selection["tools"][selected_arm["recorder_tool_role"]],
                "runner_identity": selection["tools"][selected_arm["runner_tool_role"]],
                "result_path": selected_arm["result_path"],
                "raw_output_path": selected_arm["raw_output_path"],
                "terminal_envelope_path": selected_arm["terminal_envelope_path"],
                "contract": dict(RECORDER.CONTRACT),
            },
        ),
        (
            "CGROUP_START",
            _snapshot(
                arm=arm,
                invocation_id=invocation_id,
                monotonic_ns=base + 10,
                peak=100,
                cgroup_procs=[pid],
            ),
        ),
        (
            "CHILD_SPAWN",
            {
                "observed_at_utc": "2026-07-23T00:00:01Z",
                "monotonic_ns": base + 20,
                "pid": pid,
                "proc_start_ticks": 1234,
                "pgid": pid,
                "sid": pid,
                "cgroup_path": cgroup_path,
                "argv": ["/synthetic/runner", arm],
            },
        ),
        (
            "SAMPLE",
            _snapshot(
                arm=arm,
                invocation_id=invocation_id,
                monotonic_ns=base + 30,
                peak=500,
                cgroup_procs=[pid],
            ),
        ),
        (
            "CHILD_WAIT",
            {
                "observed_at_utc": "2026-07-23T00:00:02Z",
                "monotonic_ns": base + 40,
                "returncode": 0,
                "termination_reason": None,
                "timed_out": False,
                "term_sent": 0,
                "kill_sent": 0,
                "process_group_clean": True,
                "result_identity": result_identity,
            },
        ),
        (
            "CGROUP_END",
            _snapshot(
                arm=arm,
                invocation_id=invocation_id,
                monotonic_ns=base + 50,
                peak=500,
                cgroup_procs=[],
            ),
        ),
        (
            "SEAL",
            {
                "sealed_at_utc": "2026-07-23T00:00:03Z",
                "monotonic_ns": base + 60,
                "sealed_event_count": 6,
            },
        ),
    ]
    return RECORDER.build_chain(events)


def _arguments(paths: dict[str, Path]) -> dict[str, Path]:
    return {
        "selection_path": paths["selection"],
        "receipt_path": paths["receipt"],
        "control_raw_path": paths["control_raw"],
        "control_terminal_path": paths["control_terminal"],
        "treatment_raw_path": paths["treatment_raw"],
        "treatment_terminal_path": paths["treatment_terminal"],
    }


def _fixture(tmp_path: Path) -> dict[str, Path]:
    runner = tmp_path / "runner.py"
    runner.write_text("# synthetic runner identity\n", encoding="utf-8")
    control_dir = tmp_path / "control"
    treatment_dir = tmp_path / "treatment"
    control_dir.mkdir()
    treatment_dir.mkdir()
    control_result = control_dir / "result.json"
    treatment_result = treatment_dir / "result.json"
    _dump(control_result, {"arm": "control", "status": "UNKNOWN"})
    _dump(treatment_result, {"arm": "treatment", "status": "UNKNOWN"})
    paths = {
        "selection": tmp_path / "selection.json",
        "receipt": tmp_path / "receipt.json",
        "control_raw": control_dir / "resource.jsonl",
        "control_terminal": control_dir / "terminal.json",
        "control_result": control_result,
        "treatment_raw": treatment_dir / "resource.jsonl",
        "treatment_terminal": treatment_dir / "terminal.json",
        "treatment_result": treatment_result,
    }
    common_runner_identity = RECORDER.file_identity(runner)
    recorder_identity = RECORDER.file_identity(RECORDER_PATH)
    observer_identity = RECORDER.file_identity(OBSERVER_PATH)
    receipt_source = tmp_path / "qualification-receipt.json"
    _dump(receipt_source, {"status": "PASS", "authorization_root": False})
    selection = {
        "schema": OBSERVER.SELECTION_SCHEMA,
        "created_at_utc": "2026-07-23T00:00:00Z",
        "purpose": OBSERVER.PAIRED_PURPOSE,
        "run_nonce": "synthetic-pair-a001",
        "package_id": "d" * 64,
        "selection_id": "0" * 64,
        "repository_head": "a" * 40,
        "contract": dict(OBSERVER.CONTRACT),
        "qualification_receipt_identity": RECORDER.file_identity(receipt_source),
        "tools": {
            "runner": common_runner_identity,
            "recorder": recorder_identity,
            "observer": observer_identity,
        },
        "inputs": {"fixture": RECORDER.file_identity(receipt_source)},
        "arm_directories_absent_at_creation": True,
        "arm_launch": True,
        "terminal_observer_tool_role": "observer",
        "arms": {
            label: {
                "arm": label,
                "attempt_dir": str(paths[f"{label}_result"].parent),
                "unit_name": f"gate1-{label}.service",
                "result_path": str(paths[f"{label}_result"]),
                "raw_output_path": str(paths[f"{label}_raw"]),
                "terminal_envelope_path": str(paths[f"{label}_terminal"]),
                "runner_tool_role": "runner",
                "recorder_tool_role": "recorder",
            }
            for label in ("control", "treatment")
        },
    }
    selection_body = dict(selection)
    selection_body.pop("selection_id")
    selection["selection_id"] = OBSERVER._digest(selection_body)
    _dump(paths["selection"], selection)
    selection_identity = RECORDER.file_identity(paths["selection"])
    for label, base in (("control", 1_000), ("treatment", 2_000)):
        result_identity = RECORDER.file_identity(paths[f"{label}_result"])
        paths[f"{label}_raw"].write_bytes(
            _raw_chain(
                arm=label,
                base=base,
                selection=selection,
                selection_identity=selection_identity,
                result_identity=result_identity,
            )
        )
        terminal = OBSERVER.build_terminal_envelope(
            observed_at_utc="2026-07-23T00:00:04Z",
            selection_identity=selection_identity,
            selection_id=selection["selection_id"],
            run_nonce=selection["run_nonce"],
            package_id=selection["package_id"],
            arm=label,
            unit_name=f"gate1-{label}.service",
            invocation_id=("1" if label == "control" else "2") * 32,
            control_group=f"/gate1-{label}.service",
            boot_id="b" * 32,
            active_enter_monotonic_ns=base + 5,
            inactive_enter_monotonic_ns=base + 65,
            result="success",
            exec_main_code="exited",
            exec_main_status=0,
            cgroup_empty=True,
            cgroup_path_present=False,
            cgroup_events={"populated": 0, "frozen": 0},
            inner_raw_identity=RECORDER.file_identity(paths[f"{label}_raw"]),
            arm_result_identity=result_identity,
            observer_identity=observer_identity,
        )
        _dump(paths[f"{label}_terminal"], terminal)
    derived = VERIFIER.derive_pair_inputs(
        selection_path=paths["selection"],
        control_raw_path=paths["control_raw"],
        control_terminal_path=paths["control_terminal"],
        treatment_raw_path=paths["treatment_raw"],
        treatment_terminal_path=paths["treatment_terminal"],
    )
    receipt = OBSERVER.build_paired_resource_receipt(
        created_at_utc="2026-07-23T00:00:05Z",
        selection_identity=derived["selection_identity"],
        selection=derived["selection"],
        arms=derived["arms"],
    )
    _dump(paths["receipt"], receipt)
    return paths


def _mutate_terminal(paths: dict[str, Path], **changes: object) -> None:
    terminal = _load_json(paths["control_terminal"])
    terminal.update(changes)
    _dump(paths["control_terminal"], terminal)


def test_synthetic_pair_passes_and_derives_resource_facts(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    report = VERIFIER.verify_resource_pair(**_arguments(paths))
    control_raw, _ = VERIFIER.snapshot_file(paths["control_raw"])
    recorder_summary = RECORDER.derive_inner_summary(control_raw)
    independent_summary, _ = VERIFIER._derive_inner(control_raw)
    assert report["status"] == "PASS"
    assert independent_summary == recorder_summary
    assert report["contract"]["memory_high_bytes"] == 35 * 1024**3
    assert report["arms"]["control"]["peak_bytes"] == 500
    assert report["arms"]["control"]["swap_peak_bytes"] == 0
    assert report["arms"]["control"]["event_deltas"]["oom_kill"] == 0
    assert report["arms"]["control"]["exit"]["exit_code"] == 0
    assert report["arms"]["control"]["kill_count"] == 0
    assert report["arms"]["control"]["timeout_count"] == 0
    assert report["arms"]["control"]["limit_violation_count"] == 0
    assert report["arms"]["control"]["unit_interval"]["wall_nanoseconds"] == 60


class _FakeTerminalAdapter:
    def __init__(
        self,
        *,
        invocation_id: str = "1" * 32,
        final_result: str = "success",
        final_status: str = "0",
        populated: int = 0,
    ) -> None:
        common = {
            "SubState": "running",
            "Result": "success",
            "ExecMainCode": "exited",
            "ExecMainStatus": final_status,
            "InvocationID": invocation_id,
            "ControlGroup": "/gate1-control.service",
            "ActiveEnterTimestampMonotonic": "1",
            "InactiveEnterTimestampMonotonic": "2",
            "MemoryHigh": str(OBSERVER.CONTRACT["memory_high_bytes"]),
            "MemoryMax": str(OBSERVER.CONTRACT["memory_max_bytes"]),
            "MemorySwapMax": str(OBSERVER.CONTRACT["memory_swap_max_bytes"]),
            "OOMPolicy": "continue",
            "KillMode": "control-group",
            "SendSIGKILL": "yes",
            "RuntimeMaxUSec": str(OBSERVER.CONTRACT["runtime_max_seconds"] * 1_000_000),
        }
        self._rows = [
            {**common, "ActiveState": "active"},
            {
                **common,
                "ActiveState": "inactive",
                "SubState": "dead",
                "Result": final_result,
            },
        ]
        self._populated = populated

    def show(self, unit_name: str) -> Mapping[str, str]:
        assert unit_name == "gate1-control.service"
        return self._rows.pop(0) if len(self._rows) > 1 else self._rows[0]

    def cgroup_events(self, control_group: str) -> tuple[bool, Mapping[str, int]]:
        assert control_group == "/gate1-control.service"
        return True, {"populated": self._populated, "frozen": 0}


def _clock(step: float = 0.1) -> object:
    value = -step

    def tick() -> float:
        nonlocal value
        value += step
        return value

    return tick


def test_outer_observer_waits_for_terminal_unit_and_freezes_envelope(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    paths["control_terminal"].unlink()
    selection_identity = OBSERVER.file_identity(paths["selection"])
    observed = OBSERVER.observe_terminal_unit(
        selection_path=paths["selection"],
        expected_selection_identity=selection_identity,
        arm="control",
        adapter=_FakeTerminalAdapter(),
        timeout_seconds=1,
        poll_seconds=0,
        sleep=lambda _seconds: None,
        monotonic=_clock(),
        now_utc=lambda: datetime(2026, 7, 23, tzinfo=timezone.utc),
    )
    assert observed["result"] == "success"
    assert observed["exec_main_status"] == 0
    assert observed["cgroup_empty"] is True
    assert observed["active_enter_monotonic_ns"] == 1_000
    assert observed["inactive_enter_monotonic_ns"] == 2_000
    assert observed["run_nonce"] == "synthetic-pair-a001"
    assert observed["observer_identity"] == RECORDER.file_identity(OBSERVER_PATH)
    assert paths["control_terminal"].exists()
    with pytest.raises(OBSERVER.ObserverError, match="non-exclusive"):
        OBSERVER.observe_terminal_unit(
            selection_path=paths["selection"],
            expected_selection_identity=selection_identity,
            arm="control",
            adapter=_FakeTerminalAdapter(),
            timeout_seconds=1,
            poll_seconds=0,
            sleep=lambda _seconds: None,
            monotonic=_clock(),
        )


@pytest.mark.parametrize(
    ("adapter", "needle"),
    [
        (_FakeTerminalAdapter(populated=1), "cgroup did not become empty"),
        (_FakeTerminalAdapter(invocation_id="3" * 32), "GENESIS"),
    ],
)
def test_outer_observer_rejects_terminal_or_invocation_drift(
    tmp_path: Path,
    adapter: _FakeTerminalAdapter,
    needle: str,
) -> None:
    paths = _fixture(tmp_path)
    paths["control_terminal"].unlink()
    identity = OBSERVER.file_identity(paths["selection"])
    with pytest.raises(OBSERVER.ObserverError, match=needle):
        OBSERVER.observe_terminal_unit(
            selection_path=paths["selection"],
            expected_selection_identity=identity,
            arm="control",
            adapter=adapter,
            timeout_seconds=1,
            poll_seconds=0,
            sleep=lambda _seconds: None,
            monotonic=_clock(),
        )


def test_outer_observer_records_post_seal_unit_failure_for_verifier_rejection(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    paths["control_terminal"].unlink()
    identity = OBSERVER.file_identity(paths["selection"])
    OBSERVER.observe_terminal_unit(
        selection_path=paths["selection"],
        expected_selection_identity=identity,
        arm="control",
        adapter=_FakeTerminalAdapter(final_result="timeout"),
        timeout_seconds=1,
        poll_seconds=0,
        sleep=lambda _seconds: None,
        monotonic=_clock(),
    )
    with pytest.raises(VERIFIER.VerificationError, match="inner SEAL is insufficient"):
        VERIFIER.verify_resource_pair(**_arguments(paths))


@pytest.mark.parametrize(
    ("changes", "needle"),
    [
        ({"result": "exit-code"}, "inner SEAL is insufficient"),
        (
            {"cgroup_empty": False, "cgroup_events": {"populated": 1, "frozen": 0}},
            "inner SEAL is insufficient",
        ),
        ({"invocation_id": "3" * 32}, "terminal InvocationID drifted"),
        ({"run_nonce": "forged-run"}, "terminal run nonce drifted"),
        (
            {
                "observer_identity": {
                    "path": "/forged/observer.py",
                    "size_bytes": 1,
                    "sha256": "f" * 64,
                }
            },
            "terminal observer identity drifted",
        ),
        ({"exec_main_status": True}, "field type drifted"),
    ],
)
def test_terminal_failure_canaries(
    tmp_path: Path,
    changes: dict[str, object],
    needle: str,
) -> None:
    paths = _fixture(tmp_path)
    _mutate_terminal(paths, **changes)
    with pytest.raises(VERIFIER.VerificationError, match=needle):
        VERIFIER.verify_resource_pair(**_arguments(paths))


def test_missing_terminal_envelope_fails_closed(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    paths["control_terminal"].unlink()
    with pytest.raises(VERIFIER.VerificationError, match="unavailable"):
        VERIFIER.verify_resource_pair(**_arguments(paths))


def test_clean_receipt_cannot_cover_dirty_resealed_raw_chain(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    control_raw, _ = VERIFIER.snapshot_file(paths["control_raw"])
    rows = RECORDER.parse_chain(control_raw)
    events = [(row["event"], copy.deepcopy(row["payload"])) for row in rows]
    events[-2][1]["memory_events"]["high"] = 1
    paths["control_raw"].write_bytes(RECORDER.build_chain(events))
    terminal = _load_json(paths["control_terminal"])
    terminal["inner_raw_identity"] = RECORDER.file_identity(paths["control_raw"])
    _dump(paths["control_terminal"], terminal)
    with pytest.raises(VERIFIER.VerificationError, match="inner resource summary is not clean"):
        VERIFIER.verify_resource_pair(**_arguments(paths))


def test_truncated_raw_chain_fails_closed(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    raw, _ = VERIFIER.snapshot_file(paths["control_raw"])
    paths["control_raw"].write_bytes(raw[:-1])
    with pytest.raises(VERIFIER.VerificationError, match="newline terminated"):
        VERIFIER.verify_resource_pair(**_arguments(paths))


def test_snapshot_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(b"{}\n")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(VERIFIER.VerificationError, match="symlink"):
        VERIFIER.snapshot_file(link)


def test_snapshot_detects_descriptor_toctou(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = tmp_path / "authority.json"
    authority.write_bytes(b"{}\n")
    real_fstat = os.fstat
    calls = 0

    def drifting_fstat(fd: int) -> object:
        nonlocal calls
        calls += 1
        metadata = real_fstat(fd)
        if calls != 2:
            return metadata
        return SimpleNamespace(
            st_dev=metadata.st_dev,
            st_ino=metadata.st_ino,
            st_mode=metadata.st_mode,
            st_size=metadata.st_size + 1,
            st_mtime_ns=metadata.st_mtime_ns,
            st_ctime_ns=metadata.st_ctime_ns,
        )

    monkeypatch.setattr(VERIFIER.os, "fstat", drifting_fstat)
    with pytest.raises(VERIFIER.VerificationError, match="changed during read"):
        VERIFIER.snapshot_file(authority)


@pytest.mark.parametrize(
    ("module", "error_type"),
    [
        (RECORDER, RECORDER.RecorderError),
        (OBSERVER, OBSERVER.ObserverError),
        (VERIFIER, VERIFIER.VerificationError),
    ],
)
def test_snapshot_detects_same_path_inode_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    error_type: type[Exception],
) -> None:
    authority = tmp_path / "authority.json"
    replacement = tmp_path / "replacement.json"
    authority.write_bytes(b'{"same":"bytes"}\n')
    replacement.write_bytes(b'{"same":"bytes"}\n')
    real_read = os.read
    swapped = False

    def swapping_read(fd: int, size: int) -> bytes:
        nonlocal swapped
        chunk = real_read(fd, size)
        if chunk and not swapped:
            os.replace(replacement, authority)
            swapped = True
        return chunk

    monkeypatch.setattr(module.os, "read", swapping_read)
    with pytest.raises(error_type, match=r"changed (during|after) read"):
        module.snapshot_file(authority)


@pytest.mark.parametrize(
    ("module", "error_type"),
    [
        (RECORDER, RECORDER.RecorderError),
        (OBSERVER, OBSERVER.ObserverError),
        (VERIFIER, VERIFIER.VerificationError),
    ],
)
def test_snapshot_rejects_final_path_inode_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    error_type: type[Exception],
) -> None:
    authority = tmp_path / "authority.json"
    authority.write_bytes(b'{"stable":true}\n')
    real_stat = os.stat
    calls = 0

    def drifting_stat(path: object, **kwargs: object) -> object:
        nonlocal calls
        metadata = real_stat(path, **kwargs)
        calls += 1
        if calls != 2:
            return metadata
        return SimpleNamespace(
            st_dev=metadata.st_dev,
            st_ino=metadata.st_ino + 1,
            st_mode=metadata.st_mode,
            st_size=metadata.st_size,
            st_mtime_ns=metadata.st_mtime_ns,
            st_ctime_ns=metadata.st_ctime_ns,
        )

    monkeypatch.setattr(module.os, "stat", drifting_stat)
    with pytest.raises(error_type, match="path changed after read"):
        module.snapshot_file(authority)


def test_snapshot_opens_and_reads_one_descriptor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    authority = tmp_path / "authority.json"
    authority.write_bytes(b'{"stable":true}\n')
    real_open = os.open
    opens = 0

    def counted_open(path: object, flags: int, mode: int = 0o777) -> int:
        nonlocal opens
        opens += 1
        return real_open(path, flags, mode)

    monkeypatch.setattr(VERIFIER.os, "open", counted_open)
    raw, identity = VERIFIER.snapshot_file(authority)
    assert raw == b'{"stable":true}\n'
    assert identity["size_bytes"] == len(raw)
    assert opens == 1


def test_future_recorder_requires_selected_unit_identity(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    selection_identity = RECORDER.file_identity(paths["selection"])
    with pytest.raises(RECORDER.RecorderError, match="selected paired unit"):
        RECORDER.load_paired_launch_selection(
            paths["selection"],
            expected_identity=selection_identity,
            arm="control",
            unit_name="unselected-control.service",
        )


def test_recorder_rejects_legacy_or_ad_hoc_selection_schema(tmp_path: Path) -> None:
    wrapper = tmp_path / "legacy-selection.json"
    _dump(
        wrapper,
        {
            "schema_version": "noncert-cuts-gate1-paired-launch-selection-v1",
            "arm": "control",
            "arm_launch": True,
        },
    )
    with pytest.raises(RECORDER.RecorderError, match="key set drifted"):
        RECORDER.load_paired_launch_selection(
            wrapper,
            expected_identity=RECORDER.file_identity(wrapper),
            arm="control",
            unit_name="gate1-control.service",
        )
