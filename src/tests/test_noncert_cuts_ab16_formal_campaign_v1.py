from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
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


def _identity(tag: str) -> dict[str, object]:
    return {
        "path": f"/evidence/{tag}.json",
        "sha256": hashlib.sha256(tag.encode()).hexdigest(),
        "size_bytes": len(tag),
    }


class Campaign:
    starttimes = {41: 9001}

    @staticmethod
    def same_manager_epoch(left: object, right: object) -> bool:
        return left == right

    @classmethod
    def _read_proc_starttime(cls, pid: int) -> int:
        return cls.starttimes.get(pid, 9001)

    @staticmethod
    def validate_manager_epoch_capture_transcript(
        transcript: object,
        *,
        expected_epoch: object,
    ) -> None:
        assert transcript == {"expected_epoch": expected_epoch}


def _boundary(tmp_path: Path) -> Any:
    formal = tmp_path / "formal-campaign-a001"
    formal.mkdir()
    epoch = {"dbus_unique_owner": ":1.42", "boot_id": "b" * 32}
    return SimpleNamespace(
        context={"campaign_module": Campaign, "root_identity": _identity("root")},
        root={"manager_epoch": epoch, "package": {"package_id": "c" * 64}},
        formal_dir=formal,
    )


class Store:
    def __init__(self, fail: str = "", *, return_before_fail: bool = False) -> None:
        self.fail = fail
        self.return_before_fail = return_before_fail
        self.records: dict[str, dict[str, Any]] = {}
        self.attempts: dict[str, int] = {}

    @staticmethod
    def _identity(path: Path | str) -> dict[str, object]:
        name = Path(path).name
        return {
            "path": str(path),
            "sha256": hashlib.sha256(name.encode()).hexdigest(),
            "size_bytes": len(name),
        }

    def publish(
        self,
        path: Path | str,
        value: Any,
        _label: str,
        *,
        publication: Any | None = None,
    ) -> dict[str, object]:
        name = Path(path).name
        self.attempts[name] = self.attempts.get(name, 0) + 1
        identity = self._identity(path)
        if name == self.fail:
            if publication is not None and self.return_before_fail:
                publication.note_returned(identity)
            raise OSError(f"injected {name} publication failure")
        if name in self.records:
            raise FileExistsError(name)
        if publication is not None:
            publication.note_returned(identity)
        self.records[name] = dict(value)
        if publication is not None:
            publication.note_recorded(identity)
        return identity


class FakeReference:
    def __init__(self, fault: str = "") -> None:
        self.fault = fault
        self.events: list[str] = []
        self.client = ":1.7"
        self.owner = ":1.42"

    def _event(self, name: str) -> None:
        self.events.append(name)
        if self.fault == name:
            raise RuntimeError(f"uncertain {name}")

    def acquire(self, *, unit_name: str, **_: object) -> dict[str, str]:
        self._event("acquire")
        return {
            "client_unique_name": self.client,
            "manager_owner_after": self.owner,
            "manager_owner_before": self.owner,
            "unit_name": unit_name,
        }

    def verify(self, *, expected_manager_owner: str) -> dict[str, str]:
        self._event("verify")
        return {
            "client_unique_name": self.client,
            "manager_owner": expected_manager_owner,
            "unit_name": "outer.service",
        }

    def release(self, *, unit_name: str, **_: object) -> dict[str, str]:
        self._event("release")
        return {
            "client_unique_name": self.client,
            "manager_owner_after": self.owner,
            "manager_owner_before": self.owner,
            "unit_name": unit_name,
        }

    def close(self) -> None:
        self._event("close")

    def abort_close(self) -> bool:
        self._event("abort_close")
        return self.fault != "abort_false"


def _lock_evidence() -> list[dict[str, object]]:
    return [
        {"device": 7, "inode": index + 10, "path": path, "uid": os.getuid()}
        for index, path in enumerate(HELPER.LOCK_PATHS)
    ]


def _acquire(
    boundary: Any,
    state: Any,
    store: Store,
    reference: FakeReference,
    *,
    selection_identity: Any | None = None,
    locks: Any | None = None,
) -> dict[str, object]:
    chosen_selection = selection_identity or _identity("selection")
    state.directory_created = True
    state.marker_identity = state.marker_identity or _identity("attempt")
    state.selection_identity = state.selection_identity or chosen_selection
    state.outer_prelaunch_identity = state.outer_prelaunch_identity or _identity("outer-prelaunch")
    state.outer_start_identity = state.outer_start_identity or _identity("outer-start")
    state.resource_identity = state.resource_identity or _identity("resource")
    if not state.outer_launch_attempted:
        STATE.begin_outer_launch(state)
        STATE.record_outer_launch_return(
            state,
            {"runner_returned": True, "unit_name": "outer.service"},
        )
    return STATE.acquire_reference_once(
        boundary,
        state,
        store,
        reference,
        unit_name="outer.service",
        selection_identity=chosen_selection,
        resource_identity=state.resource_identity,
        lock_evidence=locks or _lock_evidence(),
        manager_epoch_capture={
            "manager_epoch": boundary.root["manager_epoch"],
            "transcript": {"expected_epoch": boundary.root["manager_epoch"]},
        },
    )


def _finalize(
    boundary: Any,
    state: Any,
    store: Store,
    *,
    prove_unref: bool,
    reason: str,
) -> dict[str, object]:
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
    assert reference.events.count("acquire") == 1
    assert reference.events.count("abort_close") == 1
    assert reference.events.count("release") == 0
    assert reference.events.count("close") == 0
    with pytest.raises(STATE.CloseoutStateError):
        _finalize(boundary, state, store, prove_unref=False, reason=kind)


@pytest.mark.parametrize(
    ("fault", "failed_receipt", "expected", "abort_count", "close_count"),
    [
        ("", "", "RECORDED", 0, 1),
        ("release", "", "UNREF_UNPROVEN_CONNECTION_DROPPED", 1, 0),
        ("", "unref-call.json", "UNREF_UNPROVEN_CONNECTION_DROPPED", 1, 0),
        ("close", "", "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN", 0, 1),
        ("", "reference-release.json", "CONNECTION_CLOSED_RELEASE_UNRECORDED", 0, 1),
    ],
)
def test_unref_and_connection_effects_are_never_repeated(
    tmp_path: Path,
    fault: str,
    failed_receipt: str,
    expected: str,
    abort_count: int,
    close_count: int,
) -> None:
    boundary, state = _boundary(tmp_path), STATE.AttemptState()
    reference, store = FakeReference(), Store(failed_receipt)
    assert _acquire(boundary, state, store, reference)["kind"] == "RECORDED"
    reference.fault = fault
    result = _finalize(boundary, state, store, prove_unref=True, reason="normal")
    assert result["kind"] == expected
    assert reference.events.count("release") == 1
    assert reference.events.count("abort_close") == abort_count
    assert reference.events.count("close") == close_count
    with pytest.raises(STATE.CloseoutStateError):
        _finalize(boundary, state, store, prove_unref=True, reason="repeat")


@pytest.mark.parametrize(
    "mutation",
    ["acquire_keys", "acquire_owner", "verify_client", "lock_count"],
)
def test_acquisition_schema_and_join_drift_fail_closed(tmp_path: Path, mutation: str) -> None:
    boundary, state, store = _boundary(tmp_path), STATE.AttemptState(), Store()

    class DriftReference(FakeReference):
        def acquire(self, **kwargs: object) -> dict[str, str]:
            result = super().acquire(**kwargs)
            if mutation == "acquire_keys":
                result["extra"] = "forbidden"
            elif mutation == "acquire_owner":
                result["manager_owner_after"] = ":1.404"
            return result

        def verify(self, **kwargs: object) -> dict[str, str]:
            result = super().verify(**kwargs)
            if mutation == "verify_client":
                result["client_unique_name"] = ":1.999"
            return result

    selection: Any = _identity("selection")
    locks: Any = _lock_evidence()
    if mutation == "lock_count":
        locks = locks[:2]
    reference = DriftReference()
    result = _acquire(
        boundary,
        state,
        store,
        reference,
        selection_identity=selection,
        locks=locks,
    )
    assert result["kind"] == "REF_ACQUIRE_RETURNED_BUT_UNRECORDED"
    assert _finalize(
        boundary,
        state,
        store,
        prove_unref=False,
        reason=result["kind"],
    )["kind"] == "UNREF_UNPROVEN_CONNECTION_DROPPED"
    assert reference.events.count("acquire") == 1
    assert reference.events.count("abort_close") == 1
    assert reference.events.count("release") == 0
    assert reference.events.count("close") == 0


def test_acquisition_rejects_missing_or_null_lifecycle_predecessor_before_refunit(
    tmp_path: Path,
) -> None:
    boundary, reference = _boundary(tmp_path), FakeReference()
    with pytest.raises(STATE.CloseoutStateError, match="attempt/barrier boundary"):
        STATE.acquire_reference_once(
            boundary,
            STATE.AttemptState(),
            Store(),
            reference,
            unit_name="outer.service",
            selection_identity=_identity("selection"),
            resource_identity=_identity("resource"),
            lock_evidence=_lock_evidence(),
            manager_epoch_capture={
                "manager_epoch": boundary.root["manager_epoch"],
                "transcript": {"expected_epoch": boundary.root["manager_epoch"]},
            },
        )
    assert reference.events == []

    state = _consumed_state(
        selection_identity={"sha256": None},
        outer_prelaunch_identity=_identity("prelaunch"),
        outer_start_identity=_identity("start"),
        resource_identity=_identity("resource"),
    )
    state.outer_launch_attempted = True
    state.outer_launch_return = {"runner_returned": True}
    with pytest.raises(STATE.CloseoutStateError, match="unproved null join"):
        STATE.acquire_reference_once(
            boundary,
            state,
            Store(),
            reference,
            unit_name="outer.service",
            selection_identity={"sha256": None},
            resource_identity=_identity("resource"),
            lock_evidence=_lock_evidence(),
            manager_epoch_capture={
                "manager_epoch": boundary.root["manager_epoch"],
                "transcript": {"expected_epoch": boundary.root["manager_epoch"]},
            },
        )
    assert reference.events == []


def test_outer_launch_effect_is_monotone_without_start_proof() -> None:
    state = STATE.AttemptState(
        selection_identity=_identity("selection"),
        outer_prelaunch_identity=_identity("outer-prelaunch"),
    )
    STATE.begin_outer_launch(state)
    with pytest.raises(STATE.CloseoutStateError):
        STATE.begin_outer_launch(state)
    assert state.outer_launch_attempted is True and state.outer_launch_return is None
    STATE.record_outer_launch_return(state, {"runner_returned": True, "unit_name": "outer.service"})
    with pytest.raises(STATE.CloseoutStateError):
        STATE.record_outer_launch_return(state, {"runner_returned": True})
    assert state.outer_start_identity is None


def test_markerless_directory_is_consumed_without_future_joins(tmp_path: Path) -> None:
    boundary, state = _boundary(tmp_path), STATE.AttemptState(directory_created=True)
    store = Store("attempt-consumption.json", return_before_fail=True)
    with pytest.raises(STATE.CloseoutStateError, match="markerless"):
        STATE.publish_attempt_consumption(
            boundary,
            state,
            store,
            created_at_utc="2026-07-27T00:00:00Z",
        )
    record = store.records["markerless-consumed-incomplete.json"]
    assert record["no_backfill"] is True
    assert record["phase"] == "DIRECTORY_CREATED_MARKER_UNRECORDED"
    assert record["marker_canonical_identity_recorded"] is False
    assert record["attempt_consumption_effect"]["returned"] is True
    assert "selection_identity" not in record
    assert "reference_release_identity" not in record
    with pytest.raises(STATE.CloseoutStateError):
        STATE.publish_attempt_consumption(
            boundary,
            state,
            store,
            created_at_utc="2026-07-27T00:00:01Z",
        )
    assert store.attempts["attempt-consumption.json"] == 1
    assert store.attempts["markerless-consumed-incomplete.json"] == 1


def _consumed_state(**proofs: object) -> Any:
    return STATE.AttemptState(
        directory_created=True,
        marker_identity=_identity("attempt"),
        **proofs,
    )


def test_incomplete_phase_allows_semantic_lower_bound_null_but_rejects_join_drift(
    tmp_path: Path,
) -> None:
    boundary = _boundary(tmp_path)
    valid = _consumed_state(selection_identity=_identity("selection"))
    result = STATE.publish_consumed_incomplete(
        boundary,
        valid,
        Store(),
        phase="SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
        failure_record={"code": "TEST", "detail": "expected"},
    )
    assert result["record"]["lower_bound"] is None

    missing = _consumed_state()
    with pytest.raises(STATE.CloseoutStateError, match="required proof"):
        STATE.publish_consumed_incomplete(
            boundary,
            missing,
            Store(),
            phase="SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
            failure_record={"code": "TEST", "detail": "expected"},
        )
    future = _consumed_state(
        selection_identity=_identity("selection"),
        outer_start_identity=_identity("outer-start"),
    )
    with pytest.raises(STATE.CloseoutStateError, match="future proof"):
        STATE.publish_consumed_incomplete(
            boundary,
            future,
            Store(),
            phase="SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
            failure_record={"code": "TEST", "detail": "expected"},
        )
    extra = _consumed_state(selection_identity=_identity("selection"))
    with pytest.raises(STATE.CloseoutStateError, match="external join"):
        STATE.publish_consumed_incomplete(
            boundary,
            extra,
            Store(),
            phase="SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
            failure_record={"code": "TEST", "detail": "expected"},
            external_joins={"forbidden": _identity("forbidden")},
        )

    impossible = _consumed_state(selection_identity=_identity("selection"))
    impossible.connection_action = "close"
    with pytest.raises(STATE.CloseoutStateError, match="effect ordering"):
        STATE.publish_consumed_incomplete(
            boundary,
            impossible,
            Store(),
            phase="SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
            failure_record={"code": "TEST", "detail": "expected"},
        )


def test_null_frozen_join_is_not_converted_to_semantic_null(tmp_path: Path) -> None:
    boundary = _boundary(tmp_path)
    state = _consumed_state(
        selection_identity=_identity("selection"),
        outer_prelaunch_identity=_identity("prelaunch"),
        outer_start_identity=_identity("start"),
        resource_identity=_identity("resource"),
        acquire_identity=_identity("acquisition"),
    )
    state.release_attempted = True
    frozen = _absent_frozen("outer", "formal", "outer.service")
    frozen["unit_name"] = None
    with pytest.raises(STATE.CloseoutStateError):
        STATE.publish_consumed_incomplete(
            boundary,
            state,
            Store(),
            phase="UNREF_FAILED_OR_UNCERTAIN",
            failure_record={"code": "UNREF", "detail": "expected"},
            external_joins={"frozen_outer_identity": frozen},
        )


def test_uncertain_incomplete_publication_is_never_retried(tmp_path: Path) -> None:
    boundary = _boundary(tmp_path)
    state = _consumed_state(selection_identity=_identity("selection"))
    store = Store(
        "incomplete-selection-recorded-outer-not-launched.json",
        return_before_fail=True,
    )
    arguments = {
        "phase": "SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
        "failure_record": {"code": "TEST", "detail": "expected"},
    }
    with pytest.raises(OSError):
        STATE.publish_consumed_incomplete(boundary, state, store, **arguments)
    with pytest.raises(STATE.CloseoutStateError):
        STATE.publish_consumed_incomplete(boundary, state, store, **arguments)
    assert store.attempts["incomplete-selection-recorded-outer-not-launched.json"] == 1


def _active(invocation: str = "1" * 32) -> dict[str, str]:
    return {
        "LoadState": "loaded",
        "ActiveState": "active",
        "SubState": "running",
        "MainPID": "41",
        "InvocationID": invocation,
        "ControlGroup": "/user.slice/outer",
    }


def _arm_evidence(slot: str, unit_name: str) -> dict[str, object]:
    return {
        "campaign_root_identity": _identity("root"),
        "formal_selection_identity": _identity("formal-selection"),
        "launch_identity": _identity(f"{slot}-launch"),
        "package_id": "c" * 64,
        "pre_run_identity": _identity(f"{slot}-pre"),
        "prelaunch_receipt_identity": _identity(f"{slot}-receipt"),
        "request_identity": _identity(f"{slot}-request"),
        "selection_identity": _identity(f"{slot}-selection"),
        "slot": slot,
        "source": "arm",
        "unit_name": unit_name,
    }


class ChildHost:
    freeze_identity = HELPER.PinnedHost.freeze_identity

    def __init__(
        self,
        shown: dict[str, str],
        *,
        fail_absence: bool = False,
        fail_cgroup: bool = False,
    ) -> None:
        self.shown = shown
        self.fail_absence = fail_absence
        self.fail_cgroup = fail_cgroup
        self.stops = 0
        self.cleaned_units: set[str] = set()

    def show(self, _unit: str) -> dict[str, str]:
        return dict(self.shown)

    def cgroup_processes(self, _group: str) -> list[dict[str, int]]:
        if self.fail_cgroup:
            raise OSError("cgroup read failed")
        return [{"pid": 41, "starttime": 9001}]

    def stop_reset_once(self, unit: str) -> list[dict[str, str]]:
        self.stops += 1
        self.cleaned_units.add(unit)
        return []

    def wait_state(self, *_: object, **__: object) -> dict[str, object]:
        if self.fail_absence:
            raise RuntimeError("residual child")
        self.shown = dict(HELPER.ABSENT)
        return {
            "cgroup_absent": True,
            "processes_absent": True,
            "systemctl": dict(HELPER.ABSENT),
        }


def _target(tmp_path: Path, *, evidence: bool) -> Any:
    slot = HELPER.ARM_SEQUENCE[0]
    selection = _identity(f"{slot}-selection")
    pre_run = _identity(f"{slot}-pre")
    return HELPER.ChildTarget(
        source="arm",
        slot=slot,
        unit_name="ab16-child.service",
        inner_path=tmp_path / "inner.json",
        prelaunch_evidence=_arm_evidence(slot, "ab16-child.service") if evidence else None,
        selection_identity=selection,
        pre_run_identity=pre_run,
    )


def test_valid_inner_cannot_upgrade_missing_prelaunch_ownership(tmp_path: Path) -> None:
    class InnerStore(Store):
        def document(self, _path: Path, _label: str) -> tuple[dict[str, object], dict[str, object]]:
            slot = HELPER.ARM_SEQUENCE[0]
            return {
                "slot": slot,
                "unit_name": "ab16-child.service",
                "invocation_id": "1" * 32,
                "runner_selection_identity": _identity(f"{slot}-selection"),
                "pre_run_authority_identity": _identity(f"{slot}-pre"),
            }, _identity("inner")

    target, host = _target(tmp_path, evidence=False), ChildHost(_active())
    target.inner_path.touch()
    result = HELPER._contain(InnerStore(), host, target, abnormal=True)  # noqa: SLF001
    assert result["classification"] == "IDENTITY_GAP"
    assert host.stops == 0


@pytest.mark.parametrize("damage", ["missing", "selection", "unit"])
def test_active_same_name_without_exact_prelaunch_provenance_is_never_stopped(
    tmp_path: Path,
    damage: str,
) -> None:
    target = _target(tmp_path, evidence=damage != "missing")
    if damage != "missing":
        assert target.prelaunch_evidence is not None
        evidence = dict(target.prelaunch_evidence)
        if damage == "selection":
            evidence["selection_identity"] = _identity("other-selection")
        else:
            evidence["unit_name"] = "other-child.service"
        target = HELPER.ChildTarget(
            target.source,
            target.slot,
            target.unit_name,
            target.inner_path,
            evidence,
            target.selection_identity,
            target.pre_run_identity,
            target.selection_token,
        )
    host = ChildHost(_active())

    result = HELPER._contain(Store(), host, target, abnormal=True)  # noqa: SLF001

    assert result["classification"] == "IDENTITY_GAP"
    assert result["prelaunch_owned"] is False
    assert host.stops == 0


@pytest.mark.parametrize(
    ("fail_absence", "classification"),
    [(False, "STARTED_CONTAINED_PASS"), (True, "CONTAINMENT_FAILED")],
)
def test_owned_child_gets_one_bounded_stop_reset_and_exact_absence(
    tmp_path: Path,
    fail_absence: bool,
    classification: str,
) -> None:
    host = ChildHost(_active(), fail_absence=fail_absence)
    result = HELPER._contain(  # noqa: SLF001
        Store(),
        host,
        _target(tmp_path, evidence=True),
        abnormal=True,
    )
    assert result["classification"] == classification
    assert host.stops == 1
    assert result["stop_count"] == result["reset_count"] == 1


def _absent_frozen(source: str, slot: str, unit_name: str = "") -> dict[str, object]:
    return {
        "control_group": "",
        "identity_complete": True,
        "invocation_id": "",
        "ownership_classification": "ABSENT",
        "processes": [],
        "slot": slot,
        "source": source,
        "unit_name": unit_name,
    }


def _frozen_ledger(first: dict[str, object] | None = None) -> dict[str, object]:
    children = [
        _absent_frozen(source, slot)
        for source, slot in HELPER.EXPECTED_CHILD_ORDER
    ]
    if first is not None:
        children[0] = first
    return {
        "child_audit_identity": _identity("child-audit"),
        "children": children,
        "outer": _absent_frozen("outer", "formal", "outer.service"),
    }


def _absence_observation(
    ledger: dict[str, object],
    *,
    absent: bool,
) -> dict[str, object]:
    checked = HELPER.validate_frozen_ledger(ledger)
    records = []
    for item in [*checked["children"], checked["outer"]]:
        runtime_absent = absent or not item["unit_name"]
        identity_complete = item["identity_complete"] is True
        records.append(
            {
                "cgroup_absent": runtime_absent and identity_complete,
                "control_group": item["control_group"],
                "identity_complete": item["identity_complete"],
                "processes": [dict(process) for process in item["processes"]],
                "processes_absent": runtime_absent and identity_complete,
                "slot": item["slot"],
                "source": item["source"],
                "systemctl": dict(HELPER.ABSENT) if runtime_absent else _active(),
                "unit_absent": runtime_absent,
                "unit_name": item["unit_name"],
            }
        )
    return {
        "all_absent": all(
            record["unit_absent"]
            and record["cgroup_absent"]
            and record["processes_absent"]
            for record in records
        ),
        "records": records,
    }


def test_cgroup_read_error_freezes_an_incomplete_identity_and_never_proves_absence() -> None:
    class FrozenHost(ChildHost):
        observe_frozen_absence = HELPER.PinnedHost.observe_frozen_absence
        processes_absent = HELPER.PinnedHost.processes_absent
        cgroup_path = staticmethod(HELPER.PinnedHost.cgroup_path)

        def __init__(self) -> None:
            super().__init__(_active(), fail_cgroup=True)
            self.boundary = SimpleNamespace(context={"campaign_module": Campaign})

        def show(self, _unit: str) -> dict[str, str]:
            return dict(HELPER.ABSENT)

    host = FrozenHost()
    frozen = host.freeze_identity(
        source="gate1",
        slot=HELPER.GATE1_SLOTS[0],
        unit_name="ab16-child.service",
        shown=_active(),
        ownership_classification="IDENTITY_GAP",
    )
    assert frozen["identity_complete"] is False
    assert frozen["processes"] == []
    observation = host.observe_frozen_absence(_frozen_ledger(frozen))
    assert observation["all_absent"] is False
    assert observation["records"][0]["identity_complete"] is False


def test_process_absence_is_bound_to_pid_starttime_not_pid_reuse() -> None:
    host = SimpleNamespace(
        boundary=SimpleNamespace(context={"campaign_module": Campaign})
    )
    Campaign.starttimes = {41: 9002}
    try:
        assert HELPER.PinnedHost.processes_absent(
            host,
            [{"pid": 41, "starttime": 9001}],
        ) is True
        with pytest.raises(STATE.CloseoutStateError):
            HELPER.PinnedHost.processes_absent(
                host,
                [{"pid": 41, "starttime": None}],
            )
    finally:
        Campaign.starttimes = {41: 9001}


@pytest.mark.parametrize("mutation", ["missing", "reordered", "duplicate_slot", "duplicate_unit"])
def test_frozen_ledger_requires_exact_finite_identity_order(mutation: str) -> None:
    ledger = _frozen_ledger()
    if mutation == "missing":
        ledger["children"].pop()
    elif mutation == "reordered":
        ledger["children"][0], ledger["children"][1] = ledger["children"][1], ledger["children"][0]
    elif mutation == "duplicate_slot":
        ledger["children"][1] = dict(ledger["children"][0])
    else:
        ledger["children"][0]["unit_name"] = "duplicate.service"
        ledger["children"][1]["unit_name"] = "duplicate.service"
    with pytest.raises(STATE.CloseoutStateError):
        HELPER.validate_frozen_ledger(ledger)


def test_child_audit_continues_from_early_gap_to_later_owned_active_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = []
    for index, (source, slot) in enumerate(HELPER.EXPECTED_CHILD_ORDER):
        unit = "broken.service" if index == 0 else "owned-later.service" if index == 1 else ""
        selection = _identity(f"{slot}-selection")
        evidence = None
        if index == 1:
            evidence = {
                "campaign_root_identity": _identity("root"),
                "formal_selection_identity": _identity("formal-selection"),
                "gate1_ownership_identity": _identity("gate1-ownership"),
                "package_id": "c" * 64,
                "prelaunch_checkpoint_identity": _identity("gate1-checkpoint"),
                "selection_identity": selection,
                "selection_token": "gate1-token",
                "slot": slot,
                "source": "gate1",
                "unit_name": unit,
            }
        targets.append(
            HELPER.ChildTarget(
                source,
                slot,
                unit,
                tmp_path / f"{slot}.json",
                evidence,
                selection,
                None,
                "gate1-token" if source == "gate1" else "",
            )
        )

    class AuditHost(ChildHost):
        def show(self, unit: str) -> dict[str, str]:
            if unit == "broken.service":
                raise OSError("injected early audit failure")
            if unit == "owned-later.service" and unit not in self.cleaned_units:
                return _active()
            return dict(HELPER.ABSENT)

        def observe_frozen_absence(self, ledger: Any) -> dict[str, object]:
            return _absence_observation(ledger, absent=False)

    host = AuditHost(_active())
    monkeypatch.setattr(HELPER, "build_child_ledger", lambda *_args, **_kwargs: targets)
    boundary = _boundary(tmp_path)
    formal_selection = {"child_audit_path": str(boundary.formal_dir / "child-audit.json")}
    result = HELPER.audit_children(
        boundary,
        Store(),
        host,
        FakeReference(),
        formal_selection,
        abnormal=True,
    )
    assert len(result["record"]["records"]) == 20
    assert result["record"]["records"][0]["classification"] == "AUDIT_FAILED"
    assert result["record"]["records"][0]["stop_count"] == 0
    assert result["record"]["records"][1]["stop_count"] == 1
    assert result["record"]["records"][1]["classification"] == "STARTED_CONTAINED_PASS"
    assert result["record"]["status"] == "CONSUMED_INCOMPLETE"
    assert host.stops == 1


def test_normal_child_cleanup_replays_exact_gate1_and_all_organic_receipts_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = [
        HELPER.ChildTarget(
            source,
            slot,
            f"normal-{index:02d}.service",
            tmp_path / f"{slot}.json",
            None,
            _identity(f"{slot}-selection"),
            _identity(f"{slot}-pre") if source == "arm" else None,
            "gate1-token" if source == "gate1" else "",
        )
        for index, (source, slot) in enumerate(HELPER.EXPECTED_CHILD_ORDER)
    ]

    class NormalHost(ChildHost):
        def show(self, _unit: str) -> dict[str, str]:
            return dict(HELPER.ABSENT)

        def observe_frozen_absence(self, ledger: Any) -> dict[str, object]:
            return _absence_observation(ledger, absent=True)

    continuation_calls = 0
    organic_calls: list[str] = []
    gate1_detached = [_identity(f"gate1-detached-{index}") for index in range(4)]

    def continuation(_context: Any) -> tuple[dict[str, object], dict[str, object]]:
        nonlocal continuation_calls
        continuation_calls += 1
        return {"detached_replay_identities": gate1_detached}, _identity("gate1-continuation")

    def load_consumption(
        _context: Any,
        *,
        slot: str,
        required_credible: bool,
    ) -> dict[str, object]:
        assert required_credible is True
        organic_calls.append(slot)
        return {
            "consumption_id": f"consumed-{slot}",
            "resource_replay_identity": _identity(f"{slot}-replay"),
            "resource_terminal_identity": _identity(f"{slot}-terminal"),
        }

    monkeypatch.setattr(HELPER, "build_child_ledger", lambda *_args, **_kwargs: targets)
    monkeypatch.setattr(HELPER.authority, "_continuation", continuation)
    monkeypatch.setattr(HELPER.authority, "_load_consumption", load_consumption)
    boundary = _boundary(tmp_path)
    host = NormalHost(dict(HELPER.ABSENT))

    result = HELPER.audit_children(
        boundary,
        Store(),
        host,
        FakeReference(),
        {"child_audit_path": str(boundary.formal_dir / "child-audit.json")},
        abnormal=False,
    )

    assert result["record"]["status"] == "PASS"
    assert result["record"]["mode"] == "NORMAL_REPLAY"
    assert result["record"]["containment_used"] is False
    assert continuation_calls == 1
    assert organic_calls == list(HELPER.ARM_SEQUENCE)
    replay = result["record"]["normal_replay"]
    assert replay["gate1_continuation_identity"] == _identity("gate1-continuation")
    assert replay["gate1_detached_identities"] == gate1_detached
    assert replay["arm_cleanup_replay"] == {
        slot: {
            "consumption_id": f"consumed-{slot}",
            "resource_replay_identity": _identity(f"{slot}-replay"),
            "resource_terminal_identity": _identity(f"{slot}-terminal"),
        }
        for slot in HELPER.ARM_SEQUENCE
    }
    assert host.stops == 0


class HoldPort:
    def __init__(self, tmp_path: Path, *, absent: bool) -> None:
        self.absent = absent
        self.release_count = 0
        self.descriptors = [
            os.open(tmp_path / f"lock-{index}", os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
            for index in range(3)
        ]

    def lock_evidence(self) -> list[dict[str, object]]:
        return [
            {
                "device": os.fstat(descriptor).st_dev,
                "inode": os.fstat(descriptor).st_ino,
                "path": HELPER.LOCK_PATHS[index],
                "uid": os.getuid(),
            }
            for index, descriptor in enumerate(self.descriptors)
        ]

    def observe_frozen_absence(self, ledger: Any) -> dict[str, object]:
        return _absence_observation(ledger, absent=self.absent)

    def release_locks_once(self) -> dict[str, object]:
        self.release_count += 1
        if self.release_count != 1:
            raise AssertionError("lock release repeated")
        evidence = self.lock_evidence()
        for descriptor in self.descriptors:
            os.close(descriptor)
        return {"lock_identities": evidence, "released": True}

    def close_for_test(self) -> None:
        for descriptor in self.descriptors:
            try:
                os.close(descriptor)
            except OSError:
                pass


class ScriptedWaiter:
    def __init__(
        self,
        on_wait: Callable[[int], None] | None = None,
        *,
        announce_failures: int = 0,
        wait_failures: int = 0,
    ) -> None:
        self.on_wait = on_wait
        self.announce_failures = announce_failures
        self.wait_failures = wait_failures
        self.announce_attempts = 0
        self.wait_attempts = 0
        self.events: list[dict[str, object]] = []

    def announce(self, event: Any) -> None:
        self.announce_attempts += 1
        if self.announce_attempts <= self.announce_failures:
            raise RuntimeError("injected announce failure")
        self.events.append(dict(event))

    def wait(self, _seconds: float) -> None:
        self.wait_attempts += 1
        if self.wait_attempts <= self.wait_failures:
            raise RuntimeError("injected wait failure")
        if self.on_wait is None:
            raise AssertionError("containment wait was not expected")
        self.on_wait(self.wait_attempts)


def _hold_ledger() -> dict[str, object]:
    return _frozen_ledger()


def _coordinator(
    tmp_path: Path,
    *,
    absent: bool,
    failed_receipt: str = "",
    return_before_fail: bool = False,
) -> tuple[Any, Any, HoldPort, ScriptedWaiter, Store, FakeReference]:
    boundary = _boundary(tmp_path)
    reference = FakeReference()
    store = Store(failed_receipt, return_before_fail=return_before_fail)
    state = STATE.AttemptState(directory_created=True)
    STATE.publish_attempt_consumption(
        boundary,
        state,
        store,
        created_at_utc="2026-07-27T00:00:00Z",
    )
    state.selection_identity = _identity("selection")
    state.outer_prelaunch_identity = _identity("outer-prelaunch")
    state.outer_start_identity = _identity("outer-start")
    state.resource_identity = _identity("resource")
    assert _acquire(
        boundary,
        state,
        store,
        reference,
        selection_identity=state.selection_identity,
    )["kind"] == "RECORDED"
    state.barrier_identity = _identity("barrier")
    port, waiter = HoldPort(tmp_path, absent=absent), ScriptedWaiter()
    coordinator = STATE.ContainmentHoldCoordinator(
        boundary,
        state,
        store,
        port,
        waiter=waiter,
    )
    return coordinator, state, port, waiter, store, reference


@contextmanager
def _coordinator_scope(
    tmp_path: Path,
    *,
    absent: bool,
    failed_receipt: str = "",
    return_before_fail: bool = False,
) -> Iterator[tuple[Any, Any, HoldPort, ScriptedWaiter, Store, FakeReference]]:
    values = _coordinator(
        tmp_path,
        absent=absent,
        failed_receipt=failed_receipt,
        return_before_fail=return_before_fail,
    )
    try:
        yield values
    finally:
        values[2].close_for_test()


def _enter(coordinator: Any) -> dict[str, object]:
    return coordinator.enter(
        unit_name="outer.service",
        failure_record={"code": "CHILD_RESIDUAL", "detail": "test"},
        ledger=_hold_ledger(),
        reference_reason="POST_BARRIER_FAILURE",
    )


def test_containment_hold_keeps_locks_and_side_effects_until_absence(tmp_path: Path) -> None:
    with _coordinator_scope(tmp_path, absent=False) as (
        coordinator,
        _state,
        port,
        _waiter,
        store,
        reference,
    ):
        returned = False
        wait_observations = 0

        def before_absence(_attempt: int) -> None:
            nonlocal wait_observations
            wait_observations += 1
            assert returned is False
            assert port.release_count == 0
            assert all(os.fstat(descriptor) for descriptor in port.descriptors)
            assert reference.events.count("release") == 1
            assert reference.events.count("close") == 1
            assert reference.events.count("abort_close") == 0
            assert "containment-hold.json" in store.records
            if wait_observations == 2:
                port.absent = True

        coordinator.waiter = ScriptedWaiter(before_absence)
        result = _enter(coordinator)
        returned = True

        assert wait_observations == 2
        assert port.release_count == 1
        assert result["status"] == "CONSUMED_INCOMPLETE"
        assert result["detached_replay_required"] is True
        assert "detached-incomplete.json" not in store.records
        names = list(store.records)
        assert names.index("containment-cleared-after-hold.json") < names.index("lock-release.json")

        detached = STATE.verify_detached_incomplete_chain(
            expected_campaign_root_identity=coordinator.boundary.context["root_identity"],
            expected_package_id=coordinator.boundary.root["package"]["package_id"],
            **result["detached_replay_input"],
        )
        assert detached["status"] == "VERIFIED_INCOMPLETE"
        assert detached["success_eligible"] is False
        assert not any(detached["authorizations"].values())


def test_reference_terminal_exception_enters_hold_before_lock_release(tmp_path: Path) -> None:
    with _coordinator_scope(tmp_path, absent=False) as (
        coordinator,
        state,
        port,
        _waiter,
        _store,
        reference,
    ):
        state.release_attempted = True
        returned = False

        def before_absence(_attempt: int) -> None:
            assert returned is False
            assert port.release_count == 0
            assert all(os.fstat(descriptor) for descriptor in port.descriptors)
            assert reference.events.count("release") == 0
            assert reference.events.count("close") == 0
            assert reference.events.count("abort_close") == 1
            port.absent = True

        coordinator.waiter = ScriptedWaiter(before_absence)
        result = _enter(coordinator)
        returned = True

        assert port.release_count == 1
        assert result["status"] == "CONSUMED_INCOMPLETE"
        assert any(
            item["code"] == "REFERENCE_TERMINAL_FAILED_OR_UNCERTAIN"
            for item in result["errors"]
        )
        assert reference.events.count("abort_close") == 1


def test_waiter_failures_do_not_unwind_hold_or_repeat_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(STATE, "HOLD_POLL_SECONDS", 0.01)
    with _coordinator_scope(tmp_path, absent=False) as (
        coordinator,
        _state,
        port,
        _waiter,
        _store,
        reference,
    ):
        returned = False

        def before_absence(attempt: int) -> None:
            assert attempt == 2
            assert returned is False
            assert port.release_count == 0
            assert all(os.fstat(descriptor) for descriptor in port.descriptors)
            assert reference.events.count("release") == 1
            assert reference.events.count("close") == 1
            assert reference.events.count("abort_close") == 0
            port.absent = True

        waiter = ScriptedWaiter(
            before_absence,
            announce_failures=1,
            wait_failures=1,
        )
        coordinator.waiter = waiter
        result = _enter(coordinator)
        returned = True

        assert waiter.announce_attempts == 2
        assert waiter.wait_attempts == 2
        assert result["status"] == "CONSUMED_INCOMPLETE"
        assert port.release_count == 1
        assert reference.events.count("release") == 1
        assert reference.events.count("close") == 1
        error_codes = {item["code"] for item in result["errors"]}
        assert "CONTAINMENT_ANNOUNCEMENT_FAILED" in error_codes
        assert "CONTAINMENT_WAITER_FAILED" in error_codes


def test_clearance_publication_returned_unrecorded_forbids_retry(tmp_path: Path) -> None:
    boundary = _boundary(tmp_path)
    state = STATE.AttemptState()
    store = Store(
        "containment-cleared-after-hold.json",
        return_before_fail=True,
    )
    with pytest.raises(OSError, match="publication failure"):
        STATE._publish_once(  # noqa: SLF001
            state,
            store,
            "containment-clearance",
            boundary.formal_dir / "containment-cleared-after-hold.json",
            {"status": "CONTAINMENT_CLEARED_AFTER_HOLD"},
            "containment clearance",
        )
    effect = state.publication("containment-clearance")
    assert effect.attempted is True
    assert effect.returned_identity is not None
    assert effect.recorded_identity is None
    assert store.attempts["containment-cleared-after-hold.json"] == 1
    with pytest.raises(STATE.CloseoutStateError, match="cannot be attempted twice"):
        STATE._publish_once(  # noqa: SLF001
            state,
            store,
            "containment-clearance",
            boundary.formal_dir / "containment-cleared-after-hold.json",
            {"status": "CONTAINMENT_CLEARED_AFTER_HOLD"},
            "containment clearance",
        )
    assert store.attempts["containment-cleared-after-hold.json"] == 1


def test_lock_receipt_failure_does_not_repeat_real_release(tmp_path: Path) -> None:
    with _coordinator_scope(
        tmp_path,
        absent=True,
        failed_receipt="lock-release.json",
        return_before_fail=True,
    ) as (coordinator, _state, port, _waiter, store, _reference):
        result = _enter(coordinator)
        assert result["status"] == "CONSUMED_INCOMPLETE"
        assert port.release_count == 1
        assert store.attempts["lock-release.json"] == 1


@pytest.mark.parametrize(
    "mutation",
    ["hold_schema", "lock_schema", "authorization", "absence", "release"],
)
def test_pure_detached_incomplete_verifier_rejects_mutated_chain(
    tmp_path: Path,
    mutation: str,
) -> None:
    with _coordinator_scope(tmp_path, absent=True) as (
        coordinator,
        _state,
        _port,
        _waiter,
        _store,
        _reference,
    ):
        result = _enter(coordinator)
        replay = copy.deepcopy(result["detached_replay_input"])
    if mutation == "hold_schema":
        replay["hold_record"]["schema_version"] = "wrong"
    elif mutation == "lock_schema":
        replay["lock_release_record"]["schema_version"] = "wrong"
    elif mutation == "authorization":
        replay["clearance_record"]["authorizations"]["upper_bound_update_authorized"] = True
    elif mutation == "absence":
        replay["clearance_record"]["final_observation"]["records"][0]["unit_absent"] = False
    else:
        replay["lock_release_record"]["effect"]["released"] = False
    with pytest.raises(STATE.CloseoutStateError):
        STATE.verify_detached_incomplete_chain(
            expected_campaign_root_identity=coordinator.boundary.context["root_identity"],
            expected_package_id=coordinator.boundary.root["package"]["package_id"],
            **replay,
        )


@pytest.mark.parametrize("frozen_index", range(21))
def test_detached_verifier_checks_every_frozen_runtime_identity(
    tmp_path: Path,
    frozen_index: int,
) -> None:
    with _coordinator_scope(tmp_path, absent=True) as (
        coordinator,
        _state,
        _port,
        _waiter,
        _store,
        _reference,
    ):
        result = _enter(coordinator)
        replay = copy.deepcopy(result["detached_replay_input"])
    ledger = replay["hold_record"]["frozen_ledger"]
    frozen = ledger["children"][frozen_index] if frozen_index < 20 else ledger["outer"]
    frozen["control_group"] = "/user.slice/malformed"
    frozen["invocation_id"] = "f" * 32
    frozen["processes"] = [{"pid": 41, "starttime": 0}]

    with pytest.raises(STATE.CloseoutStateError):
        STATE.verify_detached_incomplete_chain(
            expected_campaign_root_identity=coordinator.boundary.context["root_identity"],
            expected_package_id=coordinator.boundary.root["package"]["package_id"],
            **replay,
        )


def test_fixed_arm_order_and_claim_boundary() -> None:
    expected = (
        "region-capacity-ab-control",
        "region-capacity-ab-treatment",
        "region-capacity-ba-treatment",
        "region-capacity-ba-control",
        "shape-packing-hall-ab-control",
        "shape-packing-hall-ab-treatment",
        "shape-packing-hall-ba-treatment",
        "shape-packing-hall-ba-control",
        "power-hitting-set-ab-control",
        "power-hitting-set-ab-treatment",
        "power-hitting-set-ba-treatment",
        "power-hitting-set-ba-control",
        "bundle-ab-control",
        "bundle-ab-treatment",
        "bundle-ba-treatment",
        "bundle-ba-control",
    )
    assert HELPER.ARM_SEQUENCE == expected
    assert len(HELPER.ARM_SEQUENCE) == 16
    assert HELPER.FALSE_AUTHORIZATIONS and not any(HELPER.FALSE_AUTHORIZATIONS.values())
