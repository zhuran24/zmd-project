from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
SPEC = importlib.util.spec_from_file_location(
    "_ab16_outer_refunit_closeout_v1_test",
    RESEARCH / "ab16_outer_refunit_closeout_v1.py",
)
assert SPEC is not None and SPEC.loader is not None
HELPER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HELPER
sys.path.insert(0, str(RESEARCH))
try:
    SPEC.loader.exec_module(HELPER)
finally:
    sys.path.remove(str(RESEARCH))
STATE = sys.modules["ab16_outer_closeout_state_v1"]


class Campaign:
    @staticmethod
    def same_manager_epoch(left: object, right: object) -> bool:
        return left == right

    @staticmethod
    def _read_proc_starttime(_pid: int) -> int:
        return 9001


def _boundary(tmp_path: Path) -> Any:
    formal = tmp_path / "formal-campaign-a001"
    formal.mkdir()
    epoch = {"dbus_unique_owner": ":1.42", "boot_id": "b" * 32}
    return SimpleNamespace(
        context={"campaign_module": Campaign, "root_identity": {"sha256": "a" * 64}},
        root={"manager_epoch": epoch, "package": {"package_id": "c" * 64}},
        formal_dir=formal,
    )


class Store:
    def __init__(self, fail: str = "") -> None:
        self.fail = fail
        self.records: dict[str, dict[str, Any]] = {}

    def publish(self, path: Path | str, value: Any, _label: str) -> dict[str, object]:
        name = Path(path).name
        if name == self.fail:
            raise OSError(f"injected {name} publication failure")
        if name in self.records:
            raise FileExistsError(name)
        self.records[name] = dict(value)
        return {"path": str(path), "sha256": name.encode().hex().ljust(64, "0")[:64]}


class FakeReference:
    def __init__(self, fault: str = "") -> None:
        self.fault = fault
        self.events: list[str] = []

    def _event(self, name: str) -> None:
        self.events.append(name)
        if self.fault == name:
            raise RuntimeError(f"uncertain {name}")
    def acquire(self, **_: object) -> dict[str, str]:
        self._event("acquire")
        return {"client_unique_name": ":1.7", "unit_name": "outer.service"}

    def verify(self, **_: object) -> dict[str, str]:
        self._event("verify")
        return {"client_unique_name": ":1.7", "unit_name": "outer.service"}

    def release(self, **_: object) -> dict[str, str]:
        self._event("release")
        return {"client_unique_name": ":1.7", "unit_name": "outer.service"}

    def close(self) -> None:
        self._event("close")

    def abort_close(self) -> bool:
        self._event("abort_close")
        return self.fault != "abort_false"


def _acquire(boundary: Any, state: Any, store: Store, reference: FakeReference) -> dict[str, object]:
    return STATE.acquire_reference_once(
        boundary,
        state,
        store,
        reference,
        unit_name="outer.service",
        selection_identity={"sha256": "d" * 64},
        resource_identity={"sha256": "e" * 64},
        lock_evidence=[{"path": path} for path in HELPER.LOCK_PATHS],
        manager_epoch_capture={"manager_epoch": boundary.root["manager_epoch"]},
    )


def _finalize(boundary: Any, state: Any, store: Store, *, prove_unref: bool, reason: str) -> dict[str, object]:
    return STATE.finalize_reference_once(
        boundary,
        state,
        store,
        unit_name="outer.service",
        prove_unref=prove_unref,
        reason=reason,
    )


@pytest.mark.parametrize(
    ("fault", "failed_receipt", "kind"),
    [
        ("acquire", "", "REF_ACQUIRE_FAILED_OR_UNCERTAIN"),
        ("", "reference-acquisition.json", "REF_ACQUIRE_RETURNED_BUT_UNRECORDED"),
    ],
)
def test_acquire_uncertainty_drops_same_connection_once(
    tmp_path: Path,
    fault: str,
    failed_receipt: str,
    kind: str,
) -> None:
    boundary, state = _boundary(tmp_path), STATE.AttemptState()
    reference, store = FakeReference(fault), Store(failed_receipt)
    assert _acquire(boundary, state, store, reference)["kind"] == kind

    result = _finalize(boundary, state, store, prove_unref=False, reason=kind)
    assert result["kind"] == "UNREF_UNPROVEN_CONNECTION_DROPPED"
    assert reference.events.count("abort_close") == 1
    assert "release" not in reference.events
    with pytest.raises(STATE.CloseoutStateError):
        _finalize(boundary, state, store, prove_unref=False, reason=kind)


@pytest.mark.parametrize(
    ("fault", "failed_receipt", "expected"),
    [
        ("", "", "RECORDED"),
        ("release", "", "UNREF_UNPROVEN_CONNECTION_DROPPED"),
        ("", "unref-call.json", "UNREF_UNPROVEN_CONNECTION_DROPPED"),
        ("close", "", "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN"),
        ("", "reference-release.json", "CONNECTION_CLOSED_RELEASE_UNRECORDED"),
    ],
)
def test_unref_and_connection_effects_are_never_repeated(
    tmp_path: Path,
    fault: str,
    failed_receipt: str,
    expected: str,
) -> None:
    boundary, state = _boundary(tmp_path), STATE.AttemptState()
    reference, acquisition_store = FakeReference(), Store()
    assert _acquire(boundary, state, acquisition_store, reference)["kind"] == "RECORDED"
    reference.fault = fault
    result = _finalize(boundary, state, Store(failed_receipt), prove_unref=True, reason="normal")
    assert result["kind"] == expected
    assert reference.events.count("release") == 1
    assert reference.events.count("abort_close") <= 1
    assert reference.events.count("close") <= 1
    with pytest.raises(STATE.CloseoutStateError):
        _finalize(boundary, state, Store(), prove_unref=True, reason="repeat")


def _active(invocation: str = "1" * 32) -> dict[str, str]:
    return {
        "LoadState": "loaded",
        "ActiveState": "active",
        "SubState": "running",
        "MainPID": "41",
        "InvocationID": invocation,
        "ControlGroup": "/user.slice/outer",
    }


class ChildHost:
    freeze_identity = HELPER.PinnedHost.freeze_identity
    def __init__(self, shown: dict[str, str], *, fail_absence: bool = False) -> None:
        self.shown = shown
        self.fail_absence = fail_absence
        self.stops = 0

    def show(self, _unit: str) -> dict[str, str]:
        return dict(self.shown)

    def cgroup_processes(self, _group: str) -> list[dict[str, int]]:
        return [{"pid": 41, "starttime": 9001}]

    def stop_reset_once(self, _unit: str) -> list[dict[str, str]]:
        self.stops += 1
        return []

    def wait_state(self, *_: object, **__: object) -> dict[str, object]:
        if self.fail_absence:
            raise RuntimeError("residual child")
        self.shown = dict(HELPER.ABSENT)
        return {"cgroup_absent": True, "processes_absent": True, "systemctl": dict(HELPER.ABSENT)}


def _target(tmp_path: Path, *, provenance: bool) -> Any:
    return HELPER.ChildTarget(
        source="arm",
        slot=HELPER.ARM_SEQUENCE[0],
        unit_name="ab16-child.service",
        inner_path=tmp_path / "inner.json",
        prelaunch_provenance=provenance,
    )


def test_missing_prelaunch_provenance_never_stops_same_name(tmp_path: Path) -> None:
    host = ChildHost(_active())
    result = HELPER._contain(  # noqa: SLF001
        Store(), host, _target(tmp_path, provenance=False), abnormal=True
    )
    assert result["classification"] == "IDENTITY_GAP"
    assert host.stops == 0


def test_malformed_inner_invocation_cannot_upgrade_child_identity(tmp_path: Path) -> None:
    class InnerStore(Store):
        def document(self, _path: Path, _label: str) -> tuple[dict[str, object], dict[str, object]]:
            return {"slot": HELPER.ARM_SEQUENCE[0], "unit_name": "ab16-child.service", "invocation_id": ""}, {}

    target, host = _target(tmp_path, provenance=False), ChildHost(_active())
    target.inner_path.touch()
    result = HELPER._contain(InnerStore(), host, target, abnormal=True)  # noqa: SLF001
    assert result["classification"] == "IDENTITY_GAP"
    assert host.stops == 0


@pytest.mark.parametrize(("fail_absence", "classification"), [(False, "STARTED_CONTAINED_PASS"), (True, "CONTAINMENT_FAILED")])
def test_owned_child_gets_one_bounded_stop_reset_and_exact_absence(
    tmp_path: Path,
    fail_absence: bool,
    classification: str,
) -> None:
    host = ChildHost(_active(), fail_absence=fail_absence)
    result = HELPER._contain(  # noqa: SLF001
        Store(), host, _target(tmp_path, provenance=True), abnormal=True
    )
    assert result["classification"] == classification
    assert host.stops == 1
    assert result["stop_count"] == result["reset_count"] == 1


def test_markerless_directory_is_consumed_without_future_joins(tmp_path: Path) -> None:
    boundary, state = _boundary(tmp_path), STATE.AttemptState(directory_created=True)
    store = Store("attempt-consumption.json")
    with pytest.raises(STATE.CloseoutStateError, match="markerless"):
        STATE.publish_attempt_consumption(
            boundary, state, store, created_at_utc="2026-07-27T00:00:00Z"
        )
    record = store.records["markerless-consumed-incomplete.json"]
    assert record["no_backfill"] is True
    assert record["phase"] == "DIRECTORY_CREATED_MARKER_UNRECORDED"
    assert "selection_identity" not in record
    assert "reference_release_identity" not in record


class HoldPort:
    def __init__(self, tmp_path: Path, *, absent: bool) -> None:
        self.absent = absent
        self.release_count = 0
        self.descriptors = [
            os.open(tmp_path / f"lock-{index}", os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
            for index in range(3)
        ]

    def lock_evidence(self) -> list[dict[str, object]]:
        return [{"inode": os.fstat(descriptor).st_ino} for descriptor in self.descriptors]
    def observe_frozen_absence(self, _ledger: Any) -> dict[str, object]:
        return {"all_absent": self.absent, "records": []}
    def release_locks_once(self) -> dict[str, object]:
        self.release_count += 1
        if self.release_count != 1:
            raise AssertionError("lock release repeated")
        evidence = self.lock_evidence()
        for descriptor in self.descriptors:
            os.close(descriptor)
        return {"lock_identities": evidence, "released": True}


class ControlledWaiter:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.tick = threading.Event()

    def announce(self, event: Any) -> None:
        self.events.append(dict(event))

    def wait(self, _seconds: float) -> None:
        self.tick.wait()
        self.tick.clear()


def _hold_ledger() -> dict[str, object]:
    child = {
        "control_group": "", "invocation_id": "", "ownership_classification": "ABSENT",
        "processes": [], "slot": "unused", "source": "arm", "unit_name": "",
    }
    return {
        "child_audit_identity": {"sha256": "1" * 64},
        "children": [dict(child) for _ in range(20)],
        "outer": {**child, "slot": "formal", "source": "outer", "unit_name": "outer.service"},
    }


def _coordinator(
    tmp_path: Path, *, absent: bool, failed_receipt: str = ""
) -> tuple[Any, Any, HoldPort, ControlledWaiter, Store, FakeReference]:
    boundary, state = _boundary(tmp_path), STATE.AttemptState(directory_created=True)
    state.marker_identity = {"sha256": "2" * 64}
    reference, store = FakeReference(), Store(failed_receipt)
    assert _acquire(boundary, state, store, reference)["kind"] == "RECORDED"
    port, waiter = HoldPort(tmp_path, absent=absent), ControlledWaiter()
    coordinator = STATE.ContainmentHoldCoordinator(
        boundary, state, store, port, waiter=waiter
    )
    return coordinator, state, port, waiter, store, reference


def test_containment_hold_keeps_locks_and_side_effects_until_absence(tmp_path: Path) -> None:
    coordinator, _state, port, waiter, store, reference = _coordinator(tmp_path, absent=False)
    result: list[dict[str, object]] = []
    thread = threading.Thread(
        target=lambda: result.append(coordinator.enter(
            unit_name="outer.service",
            failure_record={"code": "CHILD_RESIDUAL", "detail": "test"},
            ledger=_hold_ledger(),
            reference_reason="POST_BARRIER_FAILURE",
        )),
        daemon=True,
    )
    thread.start()
    deadline = time.monotonic() + 2
    while "containment-hold.json" not in store.records and time.monotonic() < deadline:
        time.sleep(0.01)
    assert thread.is_alive() and port.release_count == 0
    assert all(os.fstat(descriptor) for descriptor in port.descriptors)
    for _ in range(2):
        waiter.tick.set()
        time.sleep(0.02)
    assert reference.events.count("release") == reference.events.count("close") == 1
    port.absent = True
    waiter.tick.set()
    thread.join(2)
    assert not thread.is_alive() and port.release_count == 1
    assert result[0]["status"] == "CONSUMED_INCOMPLETE"
    names = list(store.records)
    assert names.index("containment-cleared-after-hold.json") < names.index("lock-release.json") < names.index(
        "detached-incomplete.json")


@pytest.mark.parametrize("failed_receipt", ["containment-hold.json", "containment-cleared-after-hold.json"])
def test_containment_evidence_gap_never_releases_locks(
    tmp_path: Path, failed_receipt: str
) -> None:
    coordinator, _state, port, waiter, _store, _reference = _coordinator(
        tmp_path, absent=failed_receipt == "containment-hold.json", failed_receipt=failed_receipt
    )
    thread = threading.Thread(
        target=lambda: coordinator.enter(
            unit_name="outer.service",
            failure_record={"code": "RESIDUAL", "detail": "test"},
            ledger=_hold_ledger(),
            reference_reason="POST_BARRIER_FAILURE",
        ),
        daemon=True,
    )
    thread.start()
    time.sleep(0.05)
    if failed_receipt == "containment-cleared-after-hold.json":
        port.absent = True
        waiter.tick.set()
        time.sleep(0.05)
    assert thread.is_alive() and port.release_count == 0


def test_lock_receipt_failure_does_not_repeat_real_release(tmp_path: Path) -> None:
    coordinator, _state, port, _waiter, _store, _reference = _coordinator(
        tmp_path, absent=True, failed_receipt="lock-release.json"
    )
    result = coordinator.enter(
        unit_name="outer.service",
        failure_record={"code": "RESIDUAL", "detail": "test"},
        ledger=_hold_ledger(),
        reference_reason="POST_BARRIER_FAILURE",
    )
    assert result["status"] == "CONSUMED_INCOMPLETE"
    assert port.release_count == 1


def test_fixed_arm_order_claim_boundary_and_source_caps() -> None:
    expected = []
    for configuration in HELPER.CONFIGURATIONS:
        expected.extend(
            [
                f"{configuration}-ab-control",
                f"{configuration}-ab-treatment",
                f"{configuration}-ba-treatment",
                f"{configuration}-ba-control",
            ]
        )
    assert list(HELPER.ARM_SEQUENCE) == expected
    assert len(HELPER.ARM_SEQUENCE) == 16
    assert HELPER.FALSE_AUTHORIZATIONS and not any(HELPER.FALSE_AUTHORIZATIONS.values())
    assert len((RESEARCH / "ab16_outer_refunit_closeout_v1.py").read_text().splitlines()) <= 810
    assert len((RESEARCH / "ab16_outer_closeout_state_v1.py").read_text().splitlines()) <= 440
    assert len(Path(__file__).read_text().splitlines()) <= 420
