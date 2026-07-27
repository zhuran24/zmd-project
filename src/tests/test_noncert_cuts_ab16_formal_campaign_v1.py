from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import inspect
import os
from pathlib import Path
import sys
import threading
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
    from docs.research.noncert_cuts_ab16_20260724 import (
        ab16_formal_campaign_v1 as FORMAL,
    )
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
    observer_identity: dict[str, object] | None = None,
    pre_unref_cleanup_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    return STATE.finalize_reference_once(
        boundary,
        state,
        store,
        unit_name="outer.service",
        prove_unref=prove_unref,
        reason=reason,
        observer_identity=observer_identity,
        pre_unref_cleanup_identity=pre_unref_cleanup_identity,
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
    if expected == "RECORDED":
        assert store.records["unref-call.json"]["status"] == "UNREF_RETURNED_INCOMPLETE"
    with pytest.raises(STATE.CloseoutStateError):
        _finalize(boundary, state, store, prove_unref=True, reason="repeat")


def test_normal_unref_binds_observer_and_precleanup_before_side_effect(
    tmp_path: Path,
) -> None:
    boundary, state, store = _boundary(tmp_path), STATE.AttemptState(), Store()
    reference = FakeReference()
    assert _acquire(boundary, state, store, reference)["kind"] == "RECORDED"
    observer = _identity("observer")
    cleanup = _identity("pre-unref-cleanup")

    result = _finalize(
        boundary,
        state,
        store,
        prove_unref=True,
        reason="NORMAL_SUCCESS",
        observer_identity=observer,
        pre_unref_cleanup_identity=cleanup,
    )

    assert result["kind"] == "RECORDED"
    call = store.records["unref-call.json"]
    assert call["status"] == "UNREF_RETURNED"
    assert call["observer_identity"] == observer
    assert call["pre_unref_cleanup_identity"] == cleanup
    assert state.observer_identity == observer
    assert state.pre_unref_cleanup_identity == cleanup
    assert reference.events.count("release") == reference.events.count("close") == 1

    partial_root = tmp_path / "partial"
    partial_root.mkdir()
    boundary2, state2, store2 = _boundary(partial_root), STATE.AttemptState(), Store()
    reference2 = FakeReference()
    assert _acquire(boundary2, state2, store2, reference2)["kind"] == "RECORDED"
    with pytest.raises(STATE.CloseoutStateError, match="together"):
        _finalize(
            boundary2,
            state2,
            store2,
            prove_unref=True,
            reason="NORMAL_SUCCESS",
            observer_identity=observer,
        )
    assert reference2.events.count("release") == 0


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

    def processes_absent(self, processes: Any) -> bool:
        return not processes or bool(self.cleaned_units)

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


@pytest.mark.parametrize(
    ("shown", "classification"),
    [
        (_active(), "PRELAUNCH_OWNED_ACTIVE"),
        (dict(HELPER.ABSENT), "PRELAUNCH_OWNED_ABSENT"),
    ],
)
def test_freeze_selected_child_uses_prelaunch_provenance_without_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shown: dict[str, str],
    classification: str,
) -> None:
    target = _target(tmp_path, evidence=True)
    class StableHost(ChildHost):
        cgroup_path = staticmethod(HELPER.PinnedHost.cgroup_path)

    host = StableHost(shown)
    monkeypatch.setattr(
        HELPER,
        "build_child_ledger",
        lambda *_args, **_kwargs: [target],
    )

    result = HELPER.freeze_selected_child_identity(
        _boundary(tmp_path),
        Store(),
        host,
        FakeReference(),
        {},
        source="arm",
        slot=target.slot,
    )

    assert result["classification"] == classification
    assert result["unit_name"] == target.unit_name
    assert result["frozen_identity"]["identity_complete"] is True
    assert host.stops == 0
    if classification.endswith("ABSENT"):
        assert result["frozen_identity"]["invocation_id"] == ""
    else:
        assert result["frozen_identity"]["invocation_id"] == "1" * 32


def test_freeze_selected_child_rejects_same_name_without_prelaunch_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _target(tmp_path, evidence=False)
    host = ChildHost(_active())
    monkeypatch.setattr(
        HELPER,
        "build_child_ledger",
        lambda *_args, **_kwargs: [target],
    )

    with pytest.raises(HELPER.OuterCloseoutError, match="prelaunch ownership"):
        HELPER.freeze_selected_child_identity(
            _boundary(tmp_path),
            Store(),
            host,
            FakeReference(),
            {},
            source="arm",
            slot=target.slot,
        )
    assert host.stops == 0


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


def _pre_unref_failure_state(*, release_returned: bool) -> Any:
    call = {
        "client_unique_name": ":1.7",
        "manager_owner_after": ":1.42",
        "manager_owner_before": ":1.42",
        "unit_name": "outer.service",
    }
    state = _consumed_state(
        selection_identity=_identity("selection"),
        outer_prelaunch_identity=_identity("outer-prelaunch"),
        outer_start_identity=_identity("outer-start"),
        resource_identity=_identity("resource"),
        acquire_identity=_identity("acquisition"),
        barrier_identity=_identity("barrier"),
        observer_identity=_identity("observer"),
        pre_unref_cleanup_identity=_identity("pre-unref-cleanup"),
    )
    state.outer_launch_attempted = True
    state.outer_launch_return = {"runner_returned": True}
    state.acquire_attempted = True
    state.acquire_returned = True
    state.acquire_return = dict(call)
    state.release_attempted = True
    if release_returned:
        state.release_returned = True
        state.release_return = dict(call)
    return state


@pytest.mark.parametrize(
    ("phase", "release_returned"),
    [
        ("UNREF_FAILED_OR_UNCERTAIN", False),
        ("UNREF_RETURNED_BUT_UNRECORDED", True),
    ],
)
def test_unref_failure_phase_uses_only_established_predecessor_proofs(
    tmp_path: Path,
    phase: str,
    release_returned: bool,
) -> None:
    boundary_root = tmp_path / phase.lower()
    boundary_root.mkdir()
    result = STATE.publish_consumed_incomplete(
        _boundary(boundary_root),
        _pre_unref_failure_state(release_returned=release_returned),
        Store(),
        phase=phase,
        failure_record={"code": "UNREF_TEST", "detail": "expected"},
        external_joins={
            "frozen_outer_identity": _absent_frozen(
                "outer",
                "formal",
                "outer.service",
            )
        },
    )

    joins = result["record"]["joins"]
    assert joins["observer_identity"] == _identity("observer")
    assert joins["pre_unref_cleanup_identity"] == _identity("pre-unref-cleanup")
    assert "unref_call_identity" not in joins
    assert "reference_release_identity" not in joins


def test_unref_failure_phase_rejects_missing_or_future_proofs(tmp_path: Path) -> None:
    missing = _pre_unref_failure_state(release_returned=False)
    missing.observer_identity = None
    missing.pre_unref_cleanup_identity = None
    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    with pytest.raises(STATE.CloseoutStateError, match="required proof observer_identity"):
        STATE.publish_consumed_incomplete(
            _boundary(missing_root),
            missing,
            Store(),
            phase="UNREF_FAILED_OR_UNCERTAIN",
            failure_record={"code": "UNREF_TEST", "detail": "expected"},
            external_joins={
                "frozen_outer_identity": _absent_frozen(
                    "outer",
                    "formal",
                    "outer.service",
                )
            },
        )

    future = _pre_unref_failure_state(release_returned=False)
    future.unref_call_identity = _identity("future-unref-call")
    future_root = tmp_path / "future"
    future_root.mkdir()
    with pytest.raises(STATE.CloseoutStateError, match="future proof unref_call_identity"):
        STATE.publish_consumed_incomplete(
            _boundary(future_root),
            future,
            Store(),
            phase="UNREF_FAILED_OR_UNCERTAIN",
            failure_record={"code": "UNREF_TEST", "detail": "expected"},
            external_joins={
                "frozen_outer_identity": _absent_frozen(
                    "outer",
                    "formal",
                    "outer.service",
                )
            },
        )


def test_containment_hold_retains_pre_unref_proofs_but_rejects_future_proof(
    tmp_path: Path,
) -> None:
    state = _pre_unref_failure_state(release_returned=False)
    state.release_attempted = False
    external = {
        "child_audit_identity": _identity("child-audit"),
        "frozen_outer_identity": _absent_frozen(
            "outer",
            "formal",
            "outer.service",
        ),
    }
    result = STATE.publish_consumed_incomplete(
        _boundary(tmp_path),
        state,
        Store(),
        phase="CONTAINMENT_HOLD",
        failure_record={"code": "CONTAINMENT_TEST", "detail": "expected"},
        external_joins=external,
    )
    assert result["record"]["joins"]["observer_identity"] == _identity("observer")
    assert result["record"]["joins"]["pre_unref_cleanup_identity"] == _identity(
        "pre-unref-cleanup"
    )

    future_root = tmp_path / "future"
    future_root.mkdir()
    future = _pre_unref_failure_state(release_returned=False)
    future.release_attempted = False
    future.post_unref_absence_identity = _identity("future-post-unref")
    with pytest.raises(
        STATE.CloseoutStateError,
        match="future proof post_unref_absence_identity",
    ):
        STATE.publish_consumed_incomplete(
            _boundary(future_root),
            future,
            Store(),
            phase="CONTAINMENT_HOLD",
            failure_record={"code": "CONTAINMENT_TEST", "detail": "expected"},
            external_joins=external,
        )


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


def _owned_audit_targets(
    tmp_path: Path,
    *,
    first_owned: bool,
) -> list[Any]:
    targets: list[Any] = []
    for index, (source, slot) in enumerate(HELPER.EXPECTED_CHILD_ORDER):
        unit_name = f"owned-{index:02d}.service"
        selection = _identity(f"{slot}-selection")
        pre_run = _identity(f"{slot}-pre") if source == "arm" else None
        evidence: dict[str, object] | None = None
        if index == 0 and first_owned:
            evidence = {
                "campaign_root_identity": _identity("root"),
                "formal_selection_identity": _identity("formal-selection"),
                "gate1_ownership_identity": _identity("gate1-ownership"),
                "package_id": "c" * 64,
                "prelaunch_checkpoint_identity": _identity("gate1-checkpoint"),
                "selection_identity": selection,
                "selection_token": "gate1-token",
                "slot": slot,
                "source": source,
                "unit_name": unit_name,
            }
        targets.append(
            HELPER.ChildTarget(
                source,
                slot,
                unit_name,
                tmp_path / f"{slot}.json",
                evidence,
                selection,
                pre_run,
                "gate1-token" if source == "gate1" else "",
            )
        )
    return targets


def _active_frozen(target: Any, invocation: str = "1" * 32) -> dict[str, object]:
    return {
        "control_group": "/user.slice/outer",
        "identity_complete": True,
        "invocation_id": invocation,
        "ownership_classification": "PRELAUNCH_OWNED_ACTIVE",
        "processes": [{"pid": 41, "starttime": 9001}],
        "slot": target.slot,
        "source": target.source,
        "unit_name": target.unit_name,
    }


class PriorLedgerHost(ChildHost):
    cgroup_path = staticmethod(HELPER.PinnedHost.cgroup_path)

    def __init__(self, active_unit: str, invocation: str = "1" * 32) -> None:
        super().__init__(_active(invocation))
        self.active_unit = active_unit

    def show(self, unit: str) -> dict[str, str]:
        if unit == self.active_unit and unit not in self.cleaned_units:
            return dict(self.shown)
        return dict(HELPER.ABSENT)

    def observe_frozen_absence(self, ledger: Any) -> dict[str, object]:
        return _absence_observation(ledger, absent=True)


def test_takeover_freezes_and_contains_child_launched_before_live_ledger_update(
    tmp_path: Path,
) -> None:
    targets = _owned_audit_targets(tmp_path, first_owned=True)
    first = targets[0]
    ledger = {
        "child_audit_identity": {},
        "children": [
            _absent_frozen(source, slot, target.unit_name)
            for target, (source, slot) in zip(
                targets,
                HELPER.EXPECTED_CHILD_ORDER,
                strict=True,
            )
        ],
        "outer": _absent_frozen("outer", "formal", "outer.service"),
    }
    host = PriorLedgerHost(first.unit_name)

    frozen = HELPER.freeze_takeover_child_ledger(host, ledger, targets)

    first_frozen = frozen["ledger"]["children"][0]
    assert first_frozen["unit_name"] == first.unit_name
    assert first_frozen["invocation_id"] == "1" * 32
    assert first_frozen["processes"] == [{"pid": 41, "starttime": 9001}]
    assert frozen["owned_unit_names"] == [first.unit_name]
    contained = HELPER.contain_frozen_ledger_once(
        host,
        frozen["ledger"],
        owned_unit_names=frozen["owned_unit_names"],
    )
    assert contained["all_absent"] is True
    assert contained["records"][0]["classification"] == "STARTED_CONTAINED_PASS"
    assert host.stops == 1


def test_takeover_same_name_without_prelaunch_provenance_is_observe_only(
    tmp_path: Path,
) -> None:
    targets = _owned_audit_targets(tmp_path, first_owned=False)
    first = targets[0]
    ledger = {
        "child_audit_identity": {},
        "children": [
            _absent_frozen(source, slot, target.unit_name)
            for target, (source, slot) in zip(
                targets,
                HELPER.EXPECTED_CHILD_ORDER,
                strict=True,
            )
        ],
        "outer": _absent_frozen("outer", "formal", "outer.service"),
    }

    class IdentityGapHost(PriorLedgerHost):
        def observe_frozen_absence(self, checked: Any) -> dict[str, object]:
            return _absence_observation(checked, absent=False)

    host = IdentityGapHost(first.unit_name)
    frozen = HELPER.freeze_takeover_child_ledger(host, ledger, targets)

    assert frozen["owned_unit_names"] == []
    assert frozen["ledger"]["children"][0]["ownership_classification"] == "IDENTITY_GAP"
    assert any(
        item["code"] == "GUARDIAN_CHILD_OWNERSHIP_IDENTITY_GAP"
        for item in frozen["errors"]
    )
    contained = HELPER.contain_frozen_ledger_once(
        host,
        frozen["ledger"],
        owned_unit_names=[],
    )
    assert contained["all_absent"] is False
    assert contained["records"][0]["classification"] == "IDENTITY_GAP"
    assert host.stops == 0


@pytest.mark.parametrize(
    ("prior_kind", "first_owned", "live_invocation", "classification", "stops"),
    [
        ("ACTIVE", True, "1" * 32, "STARTED_CONTAINED_PASS", 1),
        ("ACTIVE", True, "2" * 32, "IDENTITY_GAP", 0),
        ("ACTIVE", False, "1" * 32, "IDENTITY_GAP", 0),
        ("NOT_STARTED", True, "1" * 32, "STARTED_CONTAINED_PASS", 1),
        ("NOT_STARTED", False, "1" * 32, "IDENTITY_GAP", 0),
    ],
)
def test_abnormal_audit_stops_only_exact_prior_or_prelaunch_owned_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prior_kind: str,
    first_owned: bool,
    live_invocation: str,
    classification: str,
    stops: int,
) -> None:
    targets = _owned_audit_targets(tmp_path, first_owned=first_owned)
    first = targets[0]
    prior_children = [
        _absent_frozen(source, slot, target.unit_name)
        for target, (source, slot) in zip(
            targets,
            HELPER.EXPECTED_CHILD_ORDER,
            strict=True,
        )
    ]
    if prior_kind == "ACTIVE":
        prior_children[0] = _active_frozen(first)
    prior = {
        "child_audit_identity": {},
        "children": prior_children,
        "outer": _absent_frozen("outer", "formal", "outer.service"),
    }
    host = PriorLedgerHost(first.unit_name, live_invocation)
    monkeypatch.setattr(
        HELPER,
        "build_child_ledger",
        lambda *_args, **_kwargs: targets,
    )
    boundary = _boundary(tmp_path)

    result = HELPER.audit_children(
        boundary,
        Store(),
        host,
        FakeReference(),
        {"child_audit_path": str(boundary.formal_dir / "child-audit.json")},
        abnormal=True,
        prior_launch_ledger=prior,
    )

    first_record = result["record"]["records"][0]
    assert first_record["classification"] == classification
    assert first_record.get("stop_count", 0) == stops
    assert host.stops == stops
    if classification == "IDENTITY_GAP":
        assert first_record["prelaunch_owned"] is first_owned
        assert any(
            item["code"] == "PRIOR_FROZEN_IDENTITY_GAP"
            for item in first_record["errors"]
        )


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
    first = targets[0]
    targets[0] = HELPER.ChildTarget(
        first.source,
        first.slot,
        first.unit_name,
        first.inner_path,
        {
            "campaign_root_identity": _identity("root"),
            "formal_selection_identity": _identity("formal-selection"),
            "gate1_ownership_identity": _identity("gate1-ownership"),
            "package_id": "c" * 64,
            "prelaunch_checkpoint_identity": _identity("gate1-checkpoint"),
            "selection_identity": first.selection_identity,
            "selection_token": first.selection_token,
            "slot": first.slot,
            "source": first.source,
            "unit_name": first.unit_name,
        },
        first.selection_identity,
        first.pre_run_identity,
        first.selection_token,
    )

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
    historical_children = [
        _absent_frozen(source, slot, target.unit_name)
        for target, (source, slot) in zip(
            targets,
            HELPER.EXPECTED_CHILD_ORDER,
            strict=True,
        )
    ]
    historical_children[0] = {
        "control_group": "/user.slice/outer",
        "identity_complete": True,
        "invocation_id": "1" * 32,
        "ownership_classification": "PRELAUNCH_OWNED_ACTIVE",
        "processes": [{"pid": 41, "starttime": 9001}],
        "slot": HELPER.EXPECTED_CHILD_ORDER[0][1],
        "source": HELPER.EXPECTED_CHILD_ORDER[0][0],
        "unit_name": targets[0].unit_name,
    }
    prior_ledger = {
        "child_audit_identity": {},
        "children": historical_children,
        "outer": _absent_frozen("outer", "formal", "outer.service"),
    }

    result = HELPER.audit_children(
        boundary,
        Store(),
        host,
        FakeReference(),
        {"child_audit_path": str(boundary.formal_dir / "child-audit.json")},
        abnormal=False,
        prior_launch_ledger=prior_ledger,
    )

    assert result["record"]["status"] == "PASS"
    assert result["record"]["mode"] == "NORMAL_REPLAY"
    assert result["record"]["containment_used"] is False
    assert result["record"]["frozen_children"][0]["invocation_id"] == "1" * 32
    assert result["record"]["records"][0]["systemctl"] == HELPER.ABSENT
    assert result["ledger"]["child_audit_identity"] == result["identity"]
    assert prior_ledger["child_audit_identity"] == {}
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


def _late_closeout_state(phase: str) -> Any:
    call = {
        "client_unique_name": ":1.7",
        "manager_owner_after": ":1.42",
        "manager_owner_before": ":1.42",
        "unit_name": "outer.service",
    }
    state = _consumed_state(
        selection_identity=_identity("selection"),
        outer_prelaunch_identity=_identity("outer-prelaunch"),
        outer_start_identity=_identity("outer-start"),
        resource_identity=_identity("resource"),
        acquire_identity=_identity("acquisition"),
        barrier_identity=_identity("barrier"),
        unref_call_identity=_identity("unref-call"),
        reference_release_identity=_identity("reference-release"),
    )
    state.outer_launch_attempted = True
    state.outer_launch_return = {"runner_returned": True}
    state.acquire_attempted = True
    state.acquire_returned = True
    state.acquire_return = dict(call)
    state.release_attempted = True
    state.release_returned = True
    state.release_return = dict(call)
    state.close_attempted = True
    state.close_returned = True
    state.connection_action = "close"
    STATE.record_late_proof_once(state, "observer_identity", _identity("observer"))
    STATE.record_late_proof_once(
        state,
        "pre_unref_cleanup_identity",
        _identity("pre-unref-cleanup"),
    )
    STATE.record_late_proof_once(
        state,
        "post_unref_absence_identity",
        _identity("post-unref-absence"),
    )
    if phase == "GUARDIAN_CLOSE_NOT_ATTEMPTED":
        return state
    STATE.begin_guardian_close(state)
    if phase == "GUARDIAN_CLOSE_FAILED_OR_UNCERTAIN":
        return state
    STATE.record_guardian_close_return(state, {"acknowledged": True})
    STATE.record_late_proof_once(
        state,
        "guardian_close_identity",
        _identity("guardian-close"),
    )
    if phase == "GUARDIAN_ABSENCE_UNPROVED":
        return state
    STATE.record_late_proof_once(
        state,
        "guardian_absence_identity",
        _identity("guardian-absence"),
    )
    if phase == "SUPERVISOR_LOCK_RELEASE_NOT_ATTEMPTED":
        return state
    STATE.begin_supervisor_lock_release(state)
    if phase == "SUPERVISOR_LOCK_RELEASE_FAILED_OR_UNCERTAIN":
        return state
    STATE.record_supervisor_lock_release_return(state, {"released": True})
    if phase == "DUAL_LOCK_RELEASE_RECEIPT_NOT_ATTEMPTED":
        return state
    publication = state.publication("dual-lock-release")
    publication.begin()
    if phase == "DUAL_LOCK_RELEASE_RECEIPT_FAILED_OR_UNCERTAIN":
        publication.note_error(OSError("injected dual-lock publication uncertainty"))
        return state
    dual_identity = _identity("dual-lock-release")
    publication.note_returned(dual_identity)
    publication.note_recorded(dual_identity)
    STATE.record_late_proof_once(
        state,
        "dual_lock_release_identity",
        dual_identity,
    )
    if phase == "DETACHED_SUCCESS_VERIFIER_NOT_ATTEMPTED":
        return state
    STATE.begin_detached_success_verifier(state)
    return state


@pytest.mark.parametrize(
    ("phase", "last_join"),
    [
        ("GUARDIAN_CLOSE_NOT_ATTEMPTED", "post_unref_absence_identity"),
        ("GUARDIAN_CLOSE_FAILED_OR_UNCERTAIN", "post_unref_absence_identity"),
        ("GUARDIAN_ABSENCE_UNPROVED", "guardian_close_identity"),
        ("SUPERVISOR_LOCK_RELEASE_NOT_ATTEMPTED", "guardian_absence_identity"),
        ("SUPERVISOR_LOCK_RELEASE_FAILED_OR_UNCERTAIN", "guardian_absence_identity"),
        ("DUAL_LOCK_RELEASE_RECEIPT_NOT_ATTEMPTED", "guardian_absence_identity"),
        ("DUAL_LOCK_RELEASE_RECEIPT_FAILED_OR_UNCERTAIN", "guardian_absence_identity"),
        ("DETACHED_SUCCESS_VERIFIER_NOT_ATTEMPTED", "dual_lock_release_identity"),
        ("DETACHED_SUCCESS_VERIFIER_FAILED_OR_UNCERTAIN", "dual_lock_release_identity"),
    ],
)
def test_late_incomplete_phases_bind_only_established_proofs(
    tmp_path: Path,
    phase: str,
    last_join: str,
) -> None:
    state = _late_closeout_state(phase)
    supervisor = FORMAL.SupervisorState()
    supervisor.attempt = state
    assert FORMAL._failure_phase(supervisor) == phase
    result = STATE.publish_consumed_incomplete(
        _boundary(tmp_path),
        state,
        Store(),
        phase=phase,
        failure_record={"code": phase, "detail": "injected late closeout failure"},
        external_joins={
            "child_audit_identity": _identity("child-audit"),
            "outer_terminal_identity": _identity("outer-terminal"),
        },
    )

    record = result["record"]
    assert record["status"] == "CONSUMED_INCOMPLETE"
    assert record["retry_eligible"] is False
    assert not any(record["authorizations"].values())
    assert last_join in record["joins"]
    phase_order = [
        "post_unref_absence_identity",
        "guardian_close_identity",
        "guardian_absence_identity",
        "dual_lock_release_identity",
    ]
    assert not any(
        name in record["joins"]
        for name in phase_order[phase_order.index(last_join) + 1 :]
    )


def test_late_incomplete_rejects_future_proof_and_missing_dual_publication(
    tmp_path: Path,
) -> None:
    state = _late_closeout_state("GUARDIAN_CLOSE_FAILED_OR_UNCERTAIN")
    state.guardian_absence_identity = _identity("future-guardian-absence")
    with pytest.raises(STATE.CloseoutStateError, match="future proof"):
        STATE.publish_consumed_incomplete(
            _boundary(tmp_path),
            state,
            Store(),
            phase="GUARDIAN_CLOSE_FAILED_OR_UNCERTAIN",
            failure_record={"code": "LATE", "detail": "expected"},
            external_joins={
                "child_audit_identity": _identity("child-audit"),
                "outer_terminal_identity": _identity("outer-terminal"),
            },
        )

    missing_publication = _late_closeout_state(
        "SUPERVISOR_LOCK_RELEASE_FAILED_OR_UNCERTAIN"
    )
    STATE.record_supervisor_lock_release_return(
        missing_publication,
        {"released": True},
    )
    missing_root = tmp_path / "missing-publication"
    missing_root.mkdir()
    with pytest.raises(STATE.CloseoutStateError, match="attempted publication"):
        STATE.publish_consumed_incomplete(
            _boundary(missing_root),
            missing_publication,
            Store(),
            phase="DUAL_LOCK_RELEASE_RECEIPT_FAILED_OR_UNCERTAIN",
            failure_record={"code": "LATE", "detail": "expected"},
            external_joins={
                "child_audit_identity": _identity("child-audit"),
                "outer_terminal_identity": _identity("outer-terminal"),
            },
        )


class HoldPort:
    def __init__(self, tmp_path: Path, *, absent: bool) -> None:
        self.absent = absent
        self.guardian_release_count = 0
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

    def prepare_guardian_release(self, ledger: Any) -> dict[str, object]:
        STATE.validate_frozen_ledger(ledger)
        self.guardian_release_count += 1
        if self.guardian_release_count != 1:
            raise AssertionError("guardian release repeated")
        return _identity("containment-guardian-absence")

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
        assert result["detached_replay_required"] is True
        assert port.release_count == 1
        assert store.attempts["lock-release.json"] == 1
        replay = result["detached_replay_input"]
        assert replay["lock_release_identity"] == "unrecorded"
        assert replay["lock_release_effect"] == replay["lock_release_record"]["effect"]
        assert replay["guardian_absence_identity"] == replay["lock_release_record"][
            "guardian_absence_identity"
        ]
        assert replay["hold_identity"] == Store._identity(
            coordinator.boundary.formal_dir / "containment-hold.json"
        )
        assert replay["clearance_identity"] == Store._identity(
            coordinator.boundary.formal_dir
            / "containment-cleared-after-hold.json"
        )
        assert replay["incomplete_identity"] == Store._identity(
            coordinator.boundary.formal_dir
            / "incomplete-containment-hold.json"
        )
        assert replay["lock_release_publication"]["attempted"] is True
        assert replay["lock_release_publication"]["returned"] is True
        assert replay["lock_release_publication"]["recorded"] is False


def test_no_reference_opened_terminal_is_exact_and_has_no_synthetic_join() -> None:
    assert STATE._validate_reference_terminal(  # noqa: SLF001
        {"kind": "NO_REFERENCE_OPENED"}
    ) == {"kind": "NO_REFERENCE_OPENED"}
    with pytest.raises(STATE.CloseoutStateError, match="field set drifted"):
        STATE._validate_reference_terminal(  # noqa: SLF001
            {
                "identity": _identity("synthetic-reference"),
                "kind": "NO_REFERENCE_OPENED",
            }
        )


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


def test_launch_uncertainty_observes_the_exact_unit_until_it_appears() -> None:
    active = {"LoadState": "loaded"}

    class Host:
        def __init__(self) -> None:
            self.observations = [dict(HELPER.ABSENT), active]
            self.names: list[str] = []

        def show(self, unit_name: str) -> dict[str, str]:
            self.names.append(unit_name)
            return self.observations.pop(0)

    ticks = iter((0.0, 0.5, 1.0))
    sleeps: list[float] = []
    host = Host()

    observed = FORMAL._wait_uncertain_unit_resolution(
        host,  # type: ignore[arg-type]
        "outer.service",
        timeout_seconds=2.0,
        monotonic=lambda: next(ticks),
        sleeper=sleeps.append,
    )

    assert observed == active
    assert host.names == ["outer.service", "outer.service"]
    assert sleeps == [FORMAL.POLL_SECONDS]


def test_launch_uncertainty_requires_the_whole_bounded_absence_window() -> None:
    class Host:
        calls = 0

        def show(self, unit_name: str) -> dict[str, str]:
            assert unit_name == "outer.service"
            self.calls += 1
            return dict(HELPER.ABSENT)

    ticks = iter((0.0, 0.5, 1.5))
    host = Host()

    observed = FORMAL._wait_uncertain_unit_resolution(
        host,  # type: ignore[arg-type]
        "outer.service",
        timeout_seconds=1.0,
        monotonic=lambda: next(ticks),
        sleeper=lambda _seconds: None,
    )

    assert observed == HELPER.ABSENT
    assert host.calls == 1


def test_supervisor_checkpoint_blocks_new_effects_after_signal_or_guardian_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = FORMAL.SupervisorState()
    latched = SimpleNamespace(records=[{"signal": 15}])
    with pytest.raises(
        FORMAL.IrreversibleFormalFailure,
        match="termination signal latched",
    ):
        FORMAL._supervisor_checkpoint(
            state,
            SimpleNamespace(),  # type: ignore[arg-type]
            latched,  # type: ignore[arg-type]
        )
    with pytest.raises(
        FORMAL.IrreversibleFormalFailure,
        match="termination signal latched",
    ):
        FORMAL._post_release_signal_checkpoint(
            latched,  # type: ignore[arg-type]
            phase="detached success verifier launch",
        )

    state.guardian = SimpleNamespace()
    clear = SimpleNamespace(records=[])
    monkeypatch.setattr(FORMAL, "guardian_is_alive", lambda _session: False)
    with pytest.raises(
        FORMAL.IrreversibleFormalFailure,
        match="guardian died",
    ):
        FORMAL._supervisor_checkpoint(
            state,
            SimpleNamespace(),  # type: ignore[arg-type]
            clear,  # type: ignore[arg-type]
        )


def test_takeover_audit_exception_keeps_guardian_alive_and_locks_held() -> None:
    guardian_module = FORMAL.guardian
    port = guardian_module.ExistingCloseoutResidualPort.__new__(
        guardian_module.ExistingCloseoutResidualPort
    )
    port.boundary = SimpleNamespace()
    port.selection = {}
    port.store = SimpleNamespace()
    port.host = SimpleNamespace()
    port.containment_attempted = False
    port.takeover_freeze_attempted = False
    port.takeover_ledger = None
    port.takeover_release_eligible = None
    port.takeover_owned_unit_names = []
    port.ownership_errors = []
    port._recorded_reference_verification = lambda _ledger: {}  # type: ignore[method-assign]  # noqa: SLF001

    def fail_build(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("injected takeover build failure")

    port.helper = SimpleNamespace(build_child_ledger=fail_build)
    ledger = _frozen_ledger()

    class StopHold(BaseException):
        pass

    class Lease:
        abort = False
        evidence_calls = 0
        close_calls = 0

        def evidence(self) -> list[dict[str, object]]:
            if self.abort:
                raise StopHold
            self.evidence_calls += 1
            return _lock_evidence()

        def close_local_copies_once(self) -> dict[str, object]:
            self.close_calls += 1
            raise AssertionError("release-ineligible takeover closed lock FDs")

    lease = Lease()
    close_calls: list[str] = []

    class Guardian:
        latest_ledger = ledger
        ledger_update_count = 1
        selection_identity = _identity("selection")
        effects = SimpleNamespace(errors=[])

        @staticmethod
        def hold_until_supervisor_death(**_kwargs: object) -> dict[str, object]:
            return {"status": "SUPERVISOR_EXITED"}

        @staticmethod
        def close_locks_after_absence(**_kwargs: object) -> dict[str, object]:
            close_calls.append("close")
            raise AssertionError("release-ineligible takeover entered lock close")

        @staticmethod
        def _require_lease() -> Lease:
            return lease

    entered_wait = threading.Event()
    unblock = threading.Event()
    returned = threading.Event()

    def blocking_waiter(_seconds: float) -> None:
        entered_wait.set()
        unblock.wait()

    def run_hold() -> None:
        try:
            guardian_module._permanent_peer_loss_hold(  # noqa: SLF001
                Guardian(),
                port=port,
                waiter=blocking_waiter,
                poll_interval_seconds=0.01,
            )
        except StopHold:
            pass
        finally:
            returned.set()

    thread = threading.Thread(target=run_hold, daemon=True)
    thread.start()
    assert entered_wait.wait(timeout=1.0)
    assert thread.is_alive()
    assert returned.is_set() is False
    assert port.takeover_freeze_attempted is True
    assert port.takeover_release_eligible is False
    assert any(
        item["code"] == "GUARDIAN_TAKEOVER_LEDGER_IDENTITY_GAP"
        for item in port.ownership_errors
    )
    assert close_calls == []
    assert lease.close_calls == 0
    assert lease.evidence_calls >= 1
    lease.abort = True
    unblock.set()
    thread.join(timeout=1.0)
    assert thread.is_alive() is False


def test_prelaunch_mirror_precedes_every_child_launch_permission() -> None:
    service_source = inspect.getsource(FORMAL._service_fixed_campaign)
    assert service_source.index("_mirror_gate1_prelaunch(") < service_source.index(
        "_publish_outer_barrier("
    )
    assert "before_receipt_publish=" in service_source

    arm_source = inspect.getsource(HELPER.service_arm_prelaunch)
    assert arm_source.index("before_receipt_publish(slot, checked[\"unit_name\"])") < (
        arm_source.index("store.publish(")
    )
    assert FORMAL.LEDGER_PHASES == (
        "outer:prelaunch",
        "outer:formal",
        "gate1:prelaunch",
        *(f"gate1:{slot}:live" for slot in HELPER.GATE1_SLOTS),
        *(
            phase
            for slot in HELPER.ARM_SEQUENCE
            for phase in (f"arm:{slot}:prelaunch", f"arm:{slot}:live")
        ),
    )


def test_normal_closeout_has_latch_checks_at_every_late_effect_boundary() -> None:
    normal = inspect.getsource(FORMAL._publish_normal_closeout)
    release = inspect.getsource(FORMAL._release_guardian_and_locks)
    driver = inspect.getsource(FORMAL.run_formal_campaign)
    for phase in (
        "normal child cleanup replay",
        "outer stable terminal wait",
        "outer terminal receipt publication",
        "outer scoped stop/reset",
        "observer receipt publication",
        "pre-Unref cleanup receipt publication",
        "exact-once RefUnit Unref/close",
        "post-Unref absence wait",
        "post-Unref absence receipt publication",
    ):
        assert f'phase="{phase}"' in normal
    for phase in (
        "guardian exact-once lock close",
        "guardian lock-close receipt publication",
        "guardian control connection close",
        "guardian terminal absence wait",
        "guardian absence receipt publication",
        "supervisor exact-once lock release",
        "dual-lock-release receipt publication",
    ):
        assert f'phase="{phase}"' in release
    assert 'phase="detached success verifier launch"' in driver
    assert 'phase="VERIFIED supervisor return"' in driver


@pytest.mark.parametrize(
    "boundary_name",
    [
        "after-child-audit",
        "before-unref",
        "before-guardian-close",
        "before-supervisor-lock-release",
        "before-detached-verifier",
    ],
)
def test_latched_termination_stops_each_late_success_side_effect(
    boundary_name: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    latch = SimpleNamespace(records=[])

    if boundary_name in {"after-child-audit", "before-unref"}:
        state = FORMAL.SupervisorState()
        state.selection_identity = _identity("selection")
        state.selection = {
            "outer_spec": {
                "receipt_paths": {
                    key: str(tmp_path / f"{key}.json")
                    for key in (
                        "observer",
                        "outer_terminal",
                        "post_unref_absence",
                        "pre_unref_cleanup",
                    )
                },
                "unit_name": "outer.service",
            }
        }
        state.outer_identity = {
            "control_group": "/user.slice/outer.service",
            "invocation_id": "a" * 32,
            "processes": [{"pid": 41, "starttime": 9001}],
            "unit_name": "outer.service",
        }
        state.ledger = _frozen_ledger()
        state.guardian = SimpleNamespace()
        state.attempt.reference = object()
        state.attempt.acquire_identity = _identity("acquisition")
        state.attempt.barrier_identity = _identity("barrier")
        original = FORMAL._normal_closeout_checkpoint
        target = (
            "outer stable terminal wait"
            if boundary_name == "after-child-audit"
            else "exact-once RefUnit Unref/close"
        )

        def checkpoint(
            checked_state: Any,
            checked_latch: Any,
            *,
            phase: str,
        ) -> None:
            if phase == target:
                checked_latch.records.append({"signal": 15})
            original(checked_state, checked_latch, phase=phase)

        class Host:
            def stop_reset_once(self, _unit_name: str) -> list[object]:
                events.append("stop-reset")
                return []

            def wait_state(self, *_args: object, **_kwargs: object) -> dict[str, object]:
                events.append("cleanup-wait")
                return {
                    "cgroup_absent": True,
                    "processes_absent": True,
                    "systemctl": {
                        **HELPER.ABSENT,
                        "LoadState": "loaded",
                    },
                    "unit_kept_loaded_by_reference": True,
                }

        monkeypatch.setattr(FORMAL, "_normal_closeout_checkpoint", checkpoint)
        monkeypatch.setattr(FORMAL, "guardian_is_alive", lambda _session: True)
        monkeypatch.setattr(
            FORMAL.closeout_helper,
            "audit_children",
            lambda *_args, **_kwargs: events.append("child-audit")
            or {
                "identity": _identity("child-audit"),
                "ledger": state.ledger,
                "record": {"status": "PASS"},
            },
        )
        monkeypatch.setattr(
            FORMAL.closeout_helper,
            "bind_outer_ledger",
            lambda _child, _outer: state.ledger,
        )
        monkeypatch.setattr(
            FORMAL,
            "wait_unit_terminal",
            lambda *_args, **_kwargs: events.append("terminal-wait")
            or ({}, {}, 1),
        )
        monkeypatch.setattr(
            FORMAL,
            "_publish_tracked_phase",
            lambda _attempt, _store, *, key, **_kwargs: events.append(
                f"publish:{key}"
            )
            or _identity(key),
        )

        def unref(*_args: object, **_kwargs: object) -> object:
            events.append("unref")
            raise AssertionError("latched closeout reached Unref")

        monkeypatch.setattr(FORMAL.closeout_state, "finalize_reference_once", unref)
        monkeypatch.setattr(
            FORMAL,
            "_release_guardian_and_locks",
            lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("latched closeout reached guardian release")
            ),
        )
        with pytest.raises(
            FORMAL.IrreversibleFormalFailure,
            match="termination signal latched",
        ):
            FORMAL._publish_normal_closeout(
                boundary=SimpleNamespace(),
                context={
                    "campaign_root_identity": _identity("root"),
                    "manager_epoch": {},
                    "package_id": "c" * 64,
                },
                state=state,
                store=SimpleNamespace(),
                host=Host(),  # type: ignore[arg-type]
                latch=latch,  # type: ignore[arg-type]
                controller_identity=_identity("controller"),
            )
        if boundary_name == "after-child-audit":
            assert events == ["child-audit"]
        else:
            assert "publish:pre_unref_cleanup" in events
            assert "unref" not in events
        return

    if boundary_name in {
        "before-guardian-close",
        "before-supervisor-lock-release",
    }:
        state = FORMAL.SupervisorState()
        state.selection_identity = _identity("selection")
        state.selection = {
            "outer_spec": {
                "receipt_paths": {
                    "dual_lock_release": str(tmp_path / "dual.json"),
                    "guardian_absence": str(tmp_path / "guardian-absence.json"),
                    "guardian_lock_close": str(tmp_path / "guardian-close.json"),
                }
            }
        }
        state.ledger = _frozen_ledger()
        state.post_unref_identity = _identity("post-unref")
        state.attempt.post_unref_absence_identity = state.post_unref_identity
        state.guardian = SimpleNamespace(
            close_received=False,
            connection=object(),
            unit_identity={
                "control_group": "/user.slice/guardian.service",
                "invocation_id": "b" * 32,
                "processes": [{"pid": 42, "starttime": 9002}],
                "unit_name": "guardian.service",
            },
        )
        original_normal = FORMAL._normal_closeout_checkpoint
        original_post = FORMAL._post_release_signal_checkpoint

        def normal_checkpoint(
            checked_state: Any,
            checked_latch: Any,
            *,
            phase: str,
        ) -> None:
            if (
                boundary_name == "before-guardian-close"
                and phase == "guardian exact-once lock close"
            ):
                checked_latch.records.append({"signal": 15})
            original_normal(checked_state, checked_latch, phase=phase)

        def post_checkpoint(checked_latch: Any, *, phase: str) -> None:
            if (
                boundary_name == "before-supervisor-lock-release"
                and phase == "supervisor exact-once lock release"
            ):
                checked_latch.records.append({"signal": 15})
            original_post(checked_latch, phase=phase)

        close_record = {key: None for key in FORMAL.guardian.LOCK_CLOSE_FIELDS}
        close_record.update(
            {
                "errors": [],
                "frozen_ledger": state.ledger,
                "outcome": "SUCCESS_CANDIDATE",
                "schema_version": FORMAL.guardian.GUARDIAN_LOCK_CLOSE_SCHEMA,
                "status": "GUARDIAN_COPIES_CLOSED",
                "success_eligible": True,
            }
        )

        class Host:
            def lock_evidence(self) -> list[dict[str, object]]:
                return _lock_evidence()

            def release_locks_once(self) -> dict[str, object]:
                events.append("supervisor-lock-release")
                return {"released": True}

        monkeypatch.setattr(FORMAL, "_normal_closeout_checkpoint", normal_checkpoint)
        monkeypatch.setattr(
            FORMAL,
            "_post_release_signal_checkpoint",
            post_checkpoint,
        )
        monkeypatch.setattr(FORMAL, "guardian_is_alive", lambda _session: True)
        monkeypatch.setattr(
            FORMAL,
            "send_guardian_terminal",
            lambda *_args, **_kwargs: events.append("guardian-close"),
        )
        monkeypatch.setattr(
            FORMAL.guardian,
            "receive_frame",
            lambda *_args, **_kwargs: SimpleNamespace(
                identity=_identity("guardian-ack"),
                record=close_record,
            ),
        )
        monkeypatch.setattr(
            FORMAL,
            "_close_guardian_connection",
            lambda _session: events.append("guardian-connection-close"),
        )
        monkeypatch.setattr(
            FORMAL,
            "_wait_guardian_absence",
            lambda *_args, **_kwargs: events.append("guardian-absence-wait")
            or {
                "cgroup_absent": True,
                "pid_absent": True,
                "systemctl": HELPER.ABSENT,
                "unit_absent": True,
            },
        )
        monkeypatch.setattr(
            FORMAL,
            "_publish_tracked_phase",
            lambda _attempt, _store, *, key, **_kwargs: events.append(
                f"publish:{key}"
            )
            or _identity(key),
        )
        with pytest.raises(
            FORMAL.IrreversibleFormalFailure,
            match="termination signal latched",
        ):
            FORMAL._release_guardian_and_locks(
                context={
                    "campaign_root_identity": _identity("root"),
                    "manager_epoch": {},
                    "package_id": "c" * 64,
                },
                state=state,
                store=Store(),
                host=Host(),  # type: ignore[arg-type]
                latch=latch,  # type: ignore[arg-type]
                expected={},
            )
        if boundary_name == "before-guardian-close":
            assert "guardian-close" not in events
        else:
            assert "guardian-absence-wait" in events
            assert "supervisor-lock-release" not in events
        return

    with pytest.raises(
        FORMAL.IrreversibleFormalFailure,
        match="termination signal latched",
    ):
        latch.records.append({"signal": 15})
        FORMAL._post_release_signal_checkpoint(
            latch,  # type: ignore[arg-type]
            phase="detached success verifier launch",
        )
        events.append("detached-success")
    assert events == []


def test_selection_wait_checkpoint_precedes_candidate_consumption(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "selection.json"
    candidate.write_text("{}\n", encoding="utf-8")
    calls: list[str] = []

    def stop() -> None:
        calls.append("checkpoint")
        raise FORMAL.IrreversibleFormalFailure("stop before read")

    with pytest.raises(
        FORMAL.IrreversibleFormalFailure,
        match="stop before read",
    ):
        FORMAL._wait_record(
            candidate,
            expected_identity=None,
            label="selection",
            timeout_seconds=1.0,
            monotonic=lambda: 0.0,
            sleeper=lambda _seconds: None,
            checkpoint=stop,
        )
    assert calls == ["checkpoint"]


def test_guardian_connection_close_uncertainty_is_never_retried() -> None:
    class Connection:
        calls = 0

        def close(self) -> None:
            self.calls += 1
            raise OSError("uncertain close")

    connection = Connection()
    session = FORMAL.GuardianSession(
        unit_name="guardian.service",
        unit_identity={"processes": [{"pid": 41, "starttime": 9001}]},
        listener=SimpleNamespace(),
        connection=connection,
        ready={},
        ready_identity=_identity("ready"),
        last_message_identity=_identity("message"),
        process_pidfd=None,
    )

    with pytest.raises(OSError, match="uncertain close"):
        FORMAL._close_guardian_connection(session)
    with pytest.raises(
        FORMAL.IrreversibleFormalFailure,
        match="cannot be closed twice",
    ):
        FORMAL._close_guardian_connection(session)

    assert connection.calls == 1
    assert session.connection_close_attempted is True
    assert session.connection_close_returned is False
    assert session.connection_closed is False
    assert session.connection_close_error == {
        "code": "GUARDIAN_CONTROL_CLOSE_FAILED_OR_UNCERTAIN",
        "detail": "OSError: uncertain close",
    }


def test_outer_identity_is_frozen_before_resource_or_receipt_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = FORMAL.SupervisorState()
    selection_identity = _identity("selection")
    prelaunch_identity = _identity("outer-prelaunch")
    state.selection = {
        "outer_spec": {
            "resource_contract": {},
            "unit_name": "outer.service",
        }
    }
    state.selection_identity = selection_identity
    state.attempt.selection_identity = selection_identity
    state.attempt.outer_prelaunch_identity = prelaunch_identity
    state.guardian = SimpleNamespace()
    state.ledger = FORMAL.initial_ledger(
        FORMAL._outer_inactive_identity("outer.service")
    )
    state.ledger_sequence = 1
    frozen = {
        "control_group": "/user.slice/outer.service",
        "identity_complete": True,
        "invocation_id": "a" * 32,
        "ownership_classification": "OUTER_LIVE_VERIFIED",
        "processes": [{"pid": 41, "starttime": 9001}],
        "slot": "formal",
        "source": "outer",
        "unit_name": "outer.service",
    }
    monkeypatch.setattr(
        FORMAL,
        "_launch_selected_unit",
        lambda *_args, **_kwargs: {"returncode": 0},
    )

    def fail_after_freeze(
        _host: object,
        *,
        on_frozen: Callable[[Any], None],
        **_kwargs: object,
    ) -> None:
        on_frozen(frozen)
        raise FORMAL.FormalCampaignError("resource drift")

    monkeypatch.setattr(FORMAL, "wait_unit_live", fail_after_freeze)

    class Host:
        def show(self, _unit_name: str) -> dict[str, str]:
            pytest.fail("failure containment re-read the same-name unit")

    host = Host()
    with pytest.raises(FORMAL.FormalCampaignError, match="resource drift"):
        FORMAL._launch_outer(
            boundary=SimpleNamespace(),
            context={},
            state=state,
            store=SimpleNamespace(),
            host=host,  # type: ignore[arg-type]
        )

    assert state.outer_identity == {
        "control_group": frozen["control_group"],
        "invocation_id": frozen["invocation_id"],
        "processes": frozen["processes"],
        "unit_name": frozen["unit_name"],
    }
    assert state.attempt.outer_start_identity is None
    assert FORMAL._freeze_failure_outer(
        state=state,
        host=host,  # type: ignore[arg-type]
    ) == frozen


class _DriverHost:
    def __init__(self, _boundary: object, _locks: object) -> None:
        self.locks_released = False
        self.release_count = 0
        self.lock_identities = _lock_evidence()

    def lock_evidence(self) -> list[dict[str, object]]:
        if self.locks_released:
            raise RuntimeError("locks already released")
        return copy.deepcopy(self.lock_identities)

    def release_locks_once(self) -> dict[str, object]:
        if self.locks_released:
            raise RuntimeError("locks released twice")
        self.locks_released = True
        self.release_count += 1
        return {
            "lock_identities": copy.deepcopy(self.lock_identities),
            "released": True,
        }


class _DriverLatch:
    instances: list["_DriverLatch"] = []

    def __init__(self) -> None:
        self.installed = False
        self.records: list[dict[str, int]] = []
        self.restored = False
        self.__class__.instances.append(self)

    def install(self) -> None:
        self.installed = True

    def restore(self) -> None:
        self.restored = True


def _patch_driver_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[list[str], dict[str, object]]:
    events: list[str] = []
    boundary = SimpleNamespace(
        campaign=tmp_path,
        formal_dir=tmp_path / "formal-attempt-a001",
    )
    context = {
        "campaign_dir": str(tmp_path),
        "formal_attempt_dir": str(boundary.formal_dir),
        "package_id": "c" * 64,
    }
    admission = {"schema_version": "admission"}
    admission_identity = _identity("admission")
    monkeypatch.setattr(
        FORMAL,
        "load_formal_admission",
        lambda _path: (
            boundary,
            context,
            admission,
            admission_identity,
        ),
    )
    monkeypatch.setattr(
        FORMAL,
        "validate_resource_gate",
        lambda _path: events.append("resource") or {"status": "PASS"},
    )
    monkeypatch.setattr(
        FORMAL,
        "acquire_formal_locks",
        lambda: events.append("locks") or {"locks": 1},
    )
    monkeypatch.setattr(
        FORMAL.closeout_helper,
        "PinnedHost",
        _DriverHost,
    )
    monkeypatch.setattr(
        FORMAL.closeout_helper,
        "ReceiptStore",
        lambda: SimpleNamespace(),
    )
    _DriverLatch.instances.clear()
    monkeypatch.setattr(
        FORMAL.closeout_helper,
        "TerminationLatch",
        _DriverLatch,
    )
    monkeypatch.setattr(
        FORMAL,
        "_supervisor_checkpoint",
        lambda *_args: None,
    )
    return events, {
        "admission": admission,
        "admission_identity": admission_identity,
        "boundary": boundary,
        "context": context,
    }


def test_top_level_driver_preserves_the_fixed_success_order_and_release(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events, _ = _patch_driver_shell(monkeypatch, tmp_path)
    guardian_session = SimpleNamespace()
    marker, marker_identity = {"consumed": True}, _identity("marker")
    selection_identity = _identity("selection")
    selection = {
        "lock_identities": _lock_evidence(),
        "outer_spec": {"receipt_paths": {}},
    }

    def start_guardian(**_: object) -> object:
        events.append("guardian")
        return guardian_session

    def create_attempt(**kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        events.append("attempt")
        state = kwargs["state"]
        assert isinstance(state, FORMAL.SupervisorState)
        state.attempt.directory_created = True
        state.attempt.marker_identity = marker_identity
        return marker, marker_identity

    monkeypatch.setattr(FORMAL, "start_guardian", start_guardian)
    monkeypatch.setattr(FORMAL, "_create_consumed_attempt", create_attempt)
    monkeypatch.setattr(
        FORMAL,
        "wait_and_validate_selection",
        lambda **_: events.append("selection")
        or (selection, selection_identity),
    )
    for name, event in (
        ("activate_guardian", "activate"),
        ("_publish_outer_prelaunch", "outer-prelaunch"),
        ("_launch_outer", "outer-launch"),
        ("_acquire_outer_reference", "ref-acquire"),
    ):
        monkeypatch.setattr(
            FORMAL,
            name,
            lambda *args, _event=event, **kwargs: events.append(_event)
            or {"status": "PASS"},
        )
    controller_identity = _identity("controller")
    monkeypatch.setattr(
        FORMAL,
        "_service_fixed_campaign",
        lambda **_: events.append("campaign")
        or ({"status": "PASS"}, controller_identity),
    )

    def normal_closeout(**kwargs: object) -> dict[str, object]:
        events.append("normal-closeout")
        host = kwargs["host"]
        assert isinstance(host, _DriverHost)
        host.release_locks_once()
        return {"status": "PASS"}

    monkeypatch.setattr(FORMAL, "_publish_normal_closeout", normal_closeout)
    monkeypatch.setattr(
        FORMAL,
        "_run_detached_success",
        lambda **_: events.append("detached-success")
        or {"detached_success_identity": _identity("detached")},
    )

    result = FORMAL.run_formal_campaign(tmp_path)

    assert result["outcome"] == "VERIFIED"
    assert events == [
        "resource",
        "locks",
        "guardian",
        "attempt",
        "selection",
        "activate",
        "outer-prelaunch",
        "outer-launch",
        "ref-acquire",
        "campaign",
        "normal-closeout",
        "detached-success",
    ]
    assert len(_DriverLatch.instances) == 1
    assert _DriverLatch.instances[0].installed is True
    assert _DriverLatch.instances[0].restored is True


def test_top_level_driver_routes_marker_boundary_failure_without_later_effects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events, _ = _patch_driver_shell(monkeypatch, tmp_path)
    guardian_session = SimpleNamespace()
    monkeypatch.setattr(
        FORMAL,
        "start_guardian",
        lambda **_: events.append("guardian") or guardian_session,
    )

    def fail_marker(**kwargs: object) -> None:
        events.append("attempt")
        state = kwargs["state"]
        assert isinstance(state, FORMAL.SupervisorState)
        state.attempt.directory_created = True
        raise RuntimeError("marker write uncertain")

    monkeypatch.setattr(FORMAL, "_create_consumed_attempt", fail_marker)

    def close_failed(**kwargs: object) -> dict[str, object]:
        events.append("failure-closeout")
        state = kwargs["state"]
        host = kwargs["host"]
        assert isinstance(state, FORMAL.SupervisorState)
        assert state.attempt.directory_created is True
        assert state.attempt.marker_identity is None
        assert isinstance(host, _DriverHost)
        host.release_locks_once()
        return {
            "outcome": "INCOMPLETE",
            "phase": "DIRECTORY_CREATED_MARKER_UNRECORDED",
        }

    monkeypatch.setattr(FORMAL, "_close_failed_campaign", close_failed)
    for name in (
        "wait_and_validate_selection",
        "activate_guardian",
        "_publish_outer_prelaunch",
        "_launch_outer",
        "_acquire_outer_reference",
        "_service_fixed_campaign",
        "_publish_normal_closeout",
        "_run_detached_success",
    ):
        monkeypatch.setattr(
            FORMAL,
            name,
            lambda *args, _name=name, **kwargs: pytest.fail(
                f"{_name} ran after the marker boundary failed"
            ),
        )

    result = FORMAL.run_formal_campaign(tmp_path)

    assert result["outcome"] == "INCOMPLETE"
    assert result["phase"] == "DIRECTORY_CREATED_MARKER_UNRECORDED"
    assert events == ["resource", "locks", "guardian", "attempt", "failure-closeout"]
    assert _DriverLatch.instances[0].restored is True


def test_live_launch_owner_is_external_and_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = {
        "publisher": {
            "actor": {
                "pid": 4242,
                "starttime": 31337,
            },
        },
    }
    monkeypatch.setattr(
        FORMAL,
        "_process_identity",
        lambda pid: {"pid": pid, "starttime": 31337},
    )
    monkeypatch.setattr(FORMAL.os, "getpid", lambda: 9999)
    assert FORMAL._validate_live_launch_owner(  # noqa: SLF001
        artifact,
        label="fixture",
    ) == {"pid": 4242, "starttime": 31337}

    monkeypatch.setattr(
        FORMAL,
        "_process_identity",
        lambda pid: {"pid": pid, "starttime": 31338},
    )
    with pytest.raises(FORMAL.FormalCampaignError, match="no longer live"):
        FORMAL._validate_live_launch_owner(artifact, label="fixture")  # noqa: SLF001

    monkeypatch.setattr(FORMAL.os, "getpid", lambda: 4242)
    with pytest.raises(FORMAL.FormalCampaignError, match="self-authorized"):
        FORMAL._validate_live_launch_owner(artifact, label="fixture")  # noqa: SLF001
