#!/usr/bin/env python3
"""AB16-only outer RefUnit, child-containment, and closeout primitives.

Boundary construction, selection, unit launch, and experiment semantics remain
in ``ab16_formal_campaign_v1.py``.  This module owns irreversible lifecycle
effects after an attempt directory exists.  Child identities come only from
sealed Gate1 or AB16 selection evidence; no name pattern is used for discovery.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import fcntl
import hashlib
import os
from pathlib import Path, PurePosixPath
import signal
import stat
import subprocess
import time
from typing import Any

import ab16_authority_v2 as authority
import ab16_outer_closeout_state_v1 as closeout_state


GATE1_OWNERSHIP_SCHEMA = "noncert-cuts-ab16-formal-gate1-prelaunch-ownership-v1"
ARM_PRELAUNCH_SCHEMA = "noncert-cuts-ab16-formal-arm-prelaunch-v1"
CHILD_AUDIT_SCHEMA = "noncert-cuts-ab16-formal-child-audit-v1"
GATE1_OWNERSHIP_FIELDS = {
    "all_units_absent",
    "authorizations",
    "campaign_root_identity",
    "formal_selection_identity",
    "gate1_selection_identity",
    "locks",
    "manager_epoch_capture",
    "outer_reference_acquisition_identity",
    "outer_reference_verification",
    "outer_resource_identity",
    "package_id",
    "schema_version",
    "units",
}
LOCK_PATHS = closeout_state.LOCK_PATHS
GATE1_SLOTS = closeout_state.GATE1_SLOTS
ARM_SEQUENCE = closeout_state.ARM_SEQUENCE
FALSE_AUTHORIZATIONS = closeout_state.FALSE_AUTHORIZATIONS
ABSENT = closeout_state.ABSENT_SYSTEMD_STATE
CHILD_FIELDS = tuple(ABSENT)
UNIT_RE = closeout_state.UNIT_RE
INVOCATION_RE = closeout_state.INVOCATION_RE


class OuterCloseoutError(RuntimeError):
    """An AB16 outer-lifecycle invariant failed closed."""


class ChildAuditPublicationError(OuterCloseoutError):
    """Expose one uncertain child-audit publication without permitting a retry."""

    retry_forbidden = True

    def __init__(
        self,
        error: BaseException,
        *,
        record: Mapping[str, object],
        ledger: Mapping[str, object],
        publication_effect: Mapping[str, object],
    ) -> None:
        super().__init__(f"finite child audit publication failed or is uncertain: {error}")
        self.record = dict(record)
        self.ledger = dict(ledger)
        self.publication_effect = dict(publication_effect)


_failure = closeout_state.failure
_same_epoch = closeout_state.same_epoch


def _system_env() -> dict[str, str]:
    runtime = f"/run/user/{os.getuid()}"
    return {"DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime}/bus", "LANG": "C", "LC_ALL": "C",
            "PATH": "/usr/bin:/bin", "XDG_RUNTIME_DIR": runtime}


class TerminationLatch:
    """Record SIGINT/SIGTERM without unwinding or closing lock descriptors."""

    def __init__(self) -> None:
        self.records: list[dict[str, int]] = []
        self._previous: dict[int, Any] = {}

    def _record(self, signum: int, _frame: object = None) -> None:
        if self.records:
            self.records[0]["count"] += 1
        else:
            self.records.append({"count": 1, "monotonic_ns": time.monotonic_ns(), "signal": signum})

    def install(self) -> None:
        if self._previous:
            raise OuterCloseoutError("termination latch is already installed")
        for signum in (signal.SIGINT, signal.SIGTERM):
            self._previous[signum] = signal.getsignal(signum)
            signal.signal(signum, self._record)

    def restore(self) -> None:
        for signum, handler in self._previous.items():
            signal.signal(signum, handler)
        self._previous.clear()


class SleepWaiter:
    def announce(self, event: Mapping[str, object]) -> None:
        print(authority.canonical_json(dict(event)).decode("utf-8"), flush=True)

    @staticmethod
    def wait(seconds: float) -> None:
        time.sleep(seconds)


@dataclass(frozen=True)
class ChildTarget:
    source: str
    slot: str
    unit_name: str
    inner_path: Path
    prelaunch_evidence: Mapping[str, Any] | None
    selection_identity: Mapping[str, Any] | None = None
    pre_run_identity: Mapping[str, Any] | None = None
    selection_token: str = ""
    provenance_error: Mapping[str, str] | None = None


class ReceiptStore:
    """Canonical O_EXCL publication with same-byte readback."""

    def __init__(self) -> None:
        self._attempted_paths: set[str] = set()

    @staticmethod
    def identity(path: Path | str) -> dict[str, object]:
        return authority.detached_identity(authority.snapshot_regular(path))

    @staticmethod
    def document(path: Path | str, label: str) -> tuple[Mapping[str, Any], dict[str, object]]:
        snapshot = authority.snapshot_regular(path)
        value = authority.strict_loads(snapshot.data, label)
        if type(value) is not dict:
            raise OuterCloseoutError(f"{label} is not one canonical JSON object")
        return value, authority.detached_identity(snapshot)

    def publish(
        self,
        path: Path | str,
        value: Mapping[str, Any],
        label: str,
        *,
        publication: closeout_state.PublicationEffect | None = None,
    ) -> dict[str, object]:
        absolute = str(Path(path).absolute())
        if absolute in self._attempted_paths:
            raise OuterCloseoutError(f"{label} publication was already attempted")
        self._attempted_paths.add(absolute)
        if publication is not None and not publication.attempted:
            raise OuterCloseoutError(f"{label} publication effect was not begun")
        record = dict(value)
        identity = authority._write_exclusive(path, authority.canonical_json(record))  # noqa: SLF001
        if publication is not None:
            publication.note_returned(identity)
        replay, replay_identity = self.document(path, label)
        if replay != record or replay_identity != identity:
            raise OuterCloseoutError(f"{label} O_EXCL readback drifted")
        if publication is not None:
            publication.note_recorded(identity)
        return identity


EXPECTED_CHILD_ORDER = closeout_state.EXPECTED_CHILD_ORDER
validate_frozen_ledger = closeout_state.validate_frozen_ledger
_validate_process_identity = closeout_state.validate_process_identity


def _incomplete_frozen_identity(
    *,
    source: str,
    slot: str,
    unit_name: str,
    ownership_classification: str,
    error: BaseException | str,
    invocation_id: str = "",
    control_group: str = "",
) -> dict[str, object]:
    return {
        "control_group": control_group,
        "identity_complete": False,
        "identity_error": _failure("FROZEN_IDENTITY_INCOMPLETE", error),
        "invocation_id": invocation_id,
        "ownership_classification": ownership_classification,
        "processes": [],
        "slot": slot,
        "source": source,
        "unit_name": unit_name,
    }

class PinnedHost:
    """Retained-FD systemctl execution and the exact three-lock lease."""

    def __init__(self, boundary: Any, held_locks: Mapping[str, int]) -> None:
        self.boundary = boundary
        self.held_locks = dict(held_locks)
        self.cleaned_units: set[str] = set()
        self.locks_released = False

    def run(
        self, arguments: Sequence[str], *, timeout: int = 60, role: str = "systemctl",
        cwd: Path | None = None, env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        expected = self.boundary.root["authority_tools"].get(role)
        if type(expected) is not dict or type(expected.get("path")) is not str:
            raise OuterCloseoutError(f"pinned {role} identity is absent")
        path = Path(expected["path"])
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            before = os.fstat(descriptor)
            digest = hashlib.sha256()
            while block := os.read(descriptor, 1 << 20):
                digest.update(block)
            current = os.stat(path, follow_symlinks=False)
            signature = (before.st_dev, before.st_ino, before.st_mode, before.st_size, before.st_mtime_ns)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_size != expected["size_bytes"]
                or digest.hexdigest() != expected["sha256"]
                or (current.st_dev, current.st_ino) != signature[:2]
            ):
                raise OuterCloseoutError(f"{role} retained-FD identity drifted")
            os.lseek(descriptor, 0, os.SEEK_SET)
            completed = subprocess.run(
                [path.name, *arguments],
                executable=f"/proc/self/fd/{descriptor}", pass_fds=(descriptor,), close_fds=True,
                check=False, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout, cwd=cwd, env=dict(env) if env is not None else _system_env(),
            )
            after = os.fstat(descriptor)
            current = os.stat(path, follow_symlinks=False)
            after_signature = (after.st_dev, after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns)
            if signature != after_signature or (current.st_dev, current.st_ino) != signature[:2]:
                raise OuterCloseoutError(f"{role} changed across retained-FD execution")
        finally:
            os.close(descriptor)
        if completed.returncode != 0 or completed.stderr:
            raise OuterCloseoutError(f"{role} failed: exit={completed.returncode}, stderr={completed.stderr!r}")
        return completed

    def show(self, unit_name: str) -> dict[str, str]:
        if UNIT_RE.fullmatch(unit_name) is None:
            raise OuterCloseoutError("unit name is outside the exact service grammar")
        completed = self.run(["--user", "show", unit_name, *[f"--property={field}" for field in CHILD_FIELDS]])
        values: dict[str, str] = {}
        for line in completed.stdout.decode("utf-8", "strict").splitlines():
            key, separator, value = line.partition("=")
            if not separator or key in values:
                raise OuterCloseoutError("systemctl show output is malformed or duplicated")
            values[key] = value
        if set(values) != set(CHILD_FIELDS):
            raise OuterCloseoutError("systemctl show field set drifted")
        return values

    @staticmethod
    def cgroup_path(control_group: str) -> Path:
        pure = PurePosixPath(closeout_state.validate_control_group(control_group))
        return Path("/sys/fs/cgroup").joinpath(*pure.parts[1:])

    def cgroup_processes(self, control_group: str) -> list[dict[str, int]]:
        group = self.cgroup_path(control_group)
        if not os.path.lexists(group):
            return []
        campaign = self.boundary.context["campaign_module"]
        raw = campaign._read_pseudofile_same_fd(  # noqa: SLF001
            group / "cgroup.procs", label="AB16 exact child cgroup.procs", limit=1 << 20
        )
        tokens = raw.decode("ascii", "strict").split()
        if any(not token.isdigit() or int(token) <= 0 for token in tokens):
            raise OuterCloseoutError("cgroup.procs contains a malformed PID")
        pids = sorted({int(item) for item in tokens})
        processes = []
        for pid in pids:
            starttime = campaign._read_proc_starttime(pid)  # noqa: SLF001
            if type(starttime) is not int or starttime <= 0:
                raise OuterCloseoutError("cgroup PID starttime is absent or malformed")
            processes.append({"pid": pid, "starttime": starttime})
        return processes

    def processes_absent(self, processes: Sequence[Mapping[str, int]]) -> bool:
        reader = self.boundary.context["campaign_module"]._read_proc_starttime  # noqa: SLF001
        checked = [
            _validate_process_identity(process, f"frozen process {index}")
            for index, process in enumerate(processes)
        ]
        for process in checked:
            try:
                current = reader(process["pid"])
                if type(current) is not int or current <= 0:
                    raise OuterCloseoutError("live PID starttime is absent or malformed")
                if current == process["starttime"]:
                    return False
            except (FileNotFoundError, ProcessLookupError):
                continue
        return True

    def stop_reset_once(self, unit_name: str) -> list[dict[str, str]]:
        if unit_name in self.cleaned_units:
            raise OuterCloseoutError(f"stop/reset was already attempted for {unit_name}")
        self.cleaned_units.add(unit_name)
        failures = []
        for action in ("stop", "reset-failed"):
            try:
                self.run(["--user", action, unit_name])
            except Exception as exc:
                failures.append(_failure(f"{action.upper()}_FAILED", exc))
        return failures

    def wait_state(
        self, unit_name: str, control_group: str, processes: Sequence[Mapping[str, int]], *,
        referenced: bool, timeout: float = 120,
    ) -> dict[str, object]:
        deadline = time.monotonic() + timeout
        group = self.cgroup_path(control_group)
        while time.monotonic() <= deadline:
            shown = self.show(unit_name)
            unit_ok = (
                shown["LoadState"] == "loaded" and shown["ActiveState"] == "inactive"
                if referenced
                else shown == ABSENT
            )
            if unit_ok and not os.path.lexists(group) and self.processes_absent(processes):
                return {"cgroup_absent": True, "processes_absent": True, "systemctl": shown,
                        "unit_kept_loaded_by_reference": referenced}
            time.sleep(0.25)
        raise OuterCloseoutError(f"exact unit/cgroup/PID state timed out: {unit_name}")

    def freeze_identity(
        self, *, source: str, slot: str, unit_name: str, shown: Mapping[str, str],
        ownership_classification: str,
    ) -> dict[str, object]:
        """Freeze only the exact observed unit/cgroup/PID identities."""

        if shown == ABSENT:
            return {
                "control_group": "",
                "identity_complete": True,
                "invocation_id": "",
                "ownership_classification": ownership_classification,
                "processes": [],
                "slot": slot,
                "source": source,
                "unit_name": unit_name,
            }
        invocation = shown.get("InvocationID", "")
        control_group = shown.get("ControlGroup", "")
        try:
            if set(shown) != set(CHILD_FIELDS):
                raise OuterCloseoutError("systemctl identity field set drifted")
            if UNIT_RE.fullmatch(unit_name) is None:
                raise OuterCloseoutError("frozen unit name is malformed")
            if INVOCATION_RE.fullmatch(invocation) is None:
                raise OuterCloseoutError("frozen InvocationID is malformed")
            if not shown["MainPID"].isdigit() or int(shown["MainPID"]) <= 0:
                raise OuterCloseoutError("frozen MainPID is absent")
            self.cgroup_path(control_group)
            processes = self.cgroup_processes(control_group)
            if not any(item["pid"] == int(shown["MainPID"]) for item in processes):
                raise OuterCloseoutError("frozen cgroup does not contain MainPID")
        except Exception as exc:
            return _incomplete_frozen_identity(
                source=source,
                slot=slot,
                unit_name=unit_name,
                ownership_classification=ownership_classification,
                error=exc,
                invocation_id=invocation if type(invocation) is str else "",
                control_group=control_group if type(control_group) is str else "",
            )
        return {
            "control_group": control_group,
            "identity_complete": True,
            "invocation_id": invocation,
            "ownership_classification": ownership_classification,
            "processes": processes,
            "slot": slot,
            "source": source,
            "unit_name": unit_name,
        }

    def observe_frozen_absence(self, ledger: Mapping[str, object]) -> dict[str, object]:
        """Observe the same finite ledger without another stop/reset or discovery."""

        checked = validate_frozen_ledger(ledger)
        records = []
        for item in [*checked["children"], checked["outer"]]:
            unit_name = str(item["unit_name"])
            shown = ABSENT if not unit_name else self.show(unit_name)
            control_group = str(item["control_group"])
            if item["identity_complete"] is True:
                group_absent = not control_group or not os.path.lexists(self.cgroup_path(control_group))
                process_absent = self.processes_absent(item["processes"])
            else:
                group_absent = False
                process_absent = False
            records.append({
                "cgroup_absent": group_absent,
                "control_group": control_group,
                "identity_complete": item["identity_complete"],
                "processes": [dict(process) for process in item["processes"]],
                "processes_absent": process_absent,
                "slot": item["slot"],
                "source": item["source"],
                "systemctl": shown,
                "unit_absent": shown == ABSENT,
                "unit_name": unit_name,
            })
        return {"all_absent": all(
            record["unit_absent"] and record["cgroup_absent"] and record["processes_absent"]
            for record in records
        ), "records": records}

    def lock_evidence(self) -> list[dict[str, object]]:
        if set(self.held_locks) != set(LOCK_PATHS) or self.locks_released:
            raise OuterCloseoutError("the exact three-lock lease is not held")
        evidence = []
        for path in LOCK_PATHS:
            opened, current = os.fstat(self.held_locks[path]), os.stat(path, follow_symlinks=False)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_uid != os.getuid()
                or stat.S_IMODE(opened.st_mode) != 0o600
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
            ):
                raise OuterCloseoutError("lock FD/path identity drifted")
            probe = os.open(path, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                try:
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    raise OuterCloseoutError("formal lock is not exclusively held")
            finally:
                os.close(probe)
            evidence.append({"device": opened.st_dev, "inode": opened.st_ino,
                             "path": path, "uid": opened.st_uid})
        return evidence

    def release_locks_once(self) -> dict[str, object]:
        identities = self.lock_evidence()
        self.locks_released = True
        for path in LOCK_PATHS:
            os.close(self.held_locks.pop(path))
        return {"lock_identities": identities, "released": True}


def _lease(boundary: Any, host: PinnedHost, reference: Any, expected_epoch: object) -> dict[str, object]:
    capture = authority._capture_current_manager_epoch(boundary.context)  # noqa: SLF001
    campaign = boundary.context["campaign_module"]
    if not _same_epoch(boundary, capture["manager_epoch"]) or not campaign.same_manager_epoch(
        capture["manager_epoch"], expected_epoch
    ):
        raise OuterCloseoutError("manager/boot epoch drifted while lease was held")
    return {
        "locks": host.lock_evidence(),
        "manager_epoch_capture": capture,
        "outer_reference_verification": reference.verify(
            expected_manager_owner=boundary.root["manager_epoch"]["dbus_unique_owner"]),
    }


def _gate1(boundary: Any) -> tuple[Mapping[str, Any], dict[str, object]]:
    path = Path(boundary.root["stage_topology"]["gate1_v4"]["selection_path"])
    snapshot = authority.snapshot_regular(path)
    identity = authority.detached_identity(snapshot)
    campaign = boundary.context["campaign_module"]
    selection = campaign.load_gate1_selection_bytes(snapshot.data, identity)
    campaign.validate_gate1_selection(selection, root=boundary.root)
    if set(selection["units"]) != set(GATE1_SLOTS):
        raise OuterCloseoutError("Gate1 unit slots drifted")
    return selection, identity


def _gate1_absence_paths(unit: Mapping[str, Any]) -> list[Path]:
    attempt, raw, terminal = Path(unit["attempt_dir"]), Path(unit["raw_dir"]), Path(unit["terminal_dir"])
    return [
        attempt, raw, terminal, Path(unit["result_path"]), raw / "payload-seal.json",
        raw / "systemd-run-launch.json", raw / "inner-lifecycle.json",
        *(terminal / name for name in ("preterminal.json", "resource-verification.json", "release-token.json",
                                      "terminal.json", "cleanup.json", "detached-resource-replay.json")),
        *(Path(path) for path in unit["epoch_checkpoint_paths"].values()),
    ]


def capture_gate1_ownership(
    boundary: Any, store: ReceiptStore, host: PinnedHost,
    formal_selection: Mapping[str, Any], formal_selection_identity: Mapping[str, Any],
    reference: Any, *, resource_identity: Mapping[str, Any],
    acquisition_identity: Mapping[str, Any],
) -> dict[str, object]:
    gate1, gate1_identity = _gate1(boundary)
    units = []
    for slot in GATE1_SLOTS:
        selected = gate1["units"][slot]
        shown = host.show(selected["unit_name"])
        if shown != ABSENT:
            raise OuterCloseoutError(f"Gate1 prelaunch unit is not absent: {slot}")
        absence_paths = _gate1_absence_paths(selected)
        if any(path.exists() or path.is_symlink() for path in absence_paths):
            raise OuterCloseoutError(f"Gate1 prelaunch surface exists: {slot}")
        units.append({"absence_paths": [str(path) for path in absence_paths], "slot": slot,
                      "systemctl": shown, "unit_name": selected["unit_name"]})
    if _gate1(boundary) != (gate1, gate1_identity):
        raise OuterCloseoutError("Gate1 selection drifted during ownership capture")
    record = {
        "all_units_absent": True,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "campaign_root_identity": boundary.context["root_identity"],
        "formal_selection_identity": dict(formal_selection_identity),
        "gate1_selection_identity": gate1_identity,
        **_lease(boundary, host, reference, boundary.root["manager_epoch"]),
        "outer_reference_acquisition_identity": dict(acquisition_identity),
        "outer_resource_identity": dict(resource_identity),
        "package_id": boundary.root["package"]["package_id"],
        "schema_version": GATE1_OWNERSHIP_SCHEMA,
        "units": units,
    }
    return store.publish(formal_selection["gate1_prelaunch_ownership_path"],
                         record, "Gate1 prelaunch ownership")


def build_arm_prelaunch_request(
    boundary: Any, store: ReceiptStore, formal_selection_identity: Mapping[str, Any],
    slot: str, ordinal: int,
) -> dict[str, object]:
    if not 1 <= ordinal <= len(ARM_SEQUENCE) or slot != ARM_SEQUENCE[ordinal - 1]:
        raise OuterCloseoutError("AB16 arm order drifted")
    return {
        "arm_selection_identity": store.identity(boundary.preregistration["arm_selection_paths"][slot]),
        "campaign_root_identity": boundary.context["root_identity"],
        "formal_selection_identity": dict(formal_selection_identity),
        "ordinal": ordinal,
        "package_id": boundary.root["package"]["package_id"],
        "pre_run_authority_identity": store.identity(boundary.preregistration["pre_run_authority_paths"][slot]),
        "schema_version": ARM_PRELAUNCH_SCHEMA,
        "slot": slot,
        "status": "REQUESTED",
    }


def validate_arm_prelaunch_receipt(
    boundary: Any, store: ReceiptStore, request: Mapping[str, Any],
    request_identity: Mapping[str, Any], receipt_path: Path | str,
) -> tuple[Mapping[str, Any], dict[str, object]]:
    if type(request.get("slot")) is not str or type(request.get("ordinal")) is not int:
        raise OuterCloseoutError("prelaunch request slot/ordinal types drifted")
    expected_request = build_arm_prelaunch_request(
        boundary, store, store.identity(boundary.formal_dir / "selection.json"),
        str(request.get("slot")), int(request.get("ordinal", 0)))
    receipt, receipt_identity = store.document(receipt_path, f"{request.get('slot')} prelaunch receipt")
    basis = {key: value for key, value in expected_request.items() if key != "status"}
    extras = {"authorizations", "locks", "manager_epoch_capture", "outer_reference_verification",
              "request_identity", "status", "systemctl", "unit_name"}
    if (
        request != expected_request
        or set(receipt) != set(basis) | extras
        or any(receipt[key] != value for key, value in basis.items())
        or receipt["authorizations"] != FALSE_AUTHORIZATIONS
        or receipt["request_identity"] != request_identity
        or receipt["status"] != "PASS"
        or receipt["systemctl"] != ABSENT
        or not _same_epoch(boundary, receipt["manager_epoch_capture"].get("manager_epoch"))
    ):
        raise OuterCloseoutError(f"{request.get('slot')} prelaunch receipt drifted")
    return receipt, receipt_identity


def service_arm_prelaunch(
    boundary: Any, store: ReceiptStore, host: PinnedHost,
    formal_selection: Mapping[str, Any], reference: Any, *, slot: str, ordinal: int,
) -> dict[str, object]:
    paths = formal_selection["arm_prelaunch_paths"][slot]
    request, request_identity = store.document(paths["request"], f"{slot} prelaunch request")
    expected_request = build_arm_prelaunch_request(
        boundary, store, store.identity(boundary.formal_dir / "selection.json"), slot, ordinal)
    if request != expected_request:
        raise OuterCloseoutError(f"{slot} prelaunch request join drifted")
    pre_run, pre_run_identity = store.document(
        boundary.preregistration["pre_run_authority_paths"][slot], f"{slot} pre-run")
    selected, _ = store.document(boundary.preregistration["arm_selection_paths"][slot], f"{slot} selection")
    lifecycle, _ = authority._resource_modules(boundary.context)  # noqa: SLF001
    checked = lifecycle.validate_pre_run_authority(pre_run, expected_slot=slot)
    chosen = lifecycle.validate_runner_selection(
        selected, pre_run_authority=checked, pre_run_authority_identity=pre_run_identity)
    if (
        checked["unit_name"] != chosen["unit_name"]
        or checked["attempt_dir"] != chosen["attempt_dir"]
        or checked["attempt_dir"] != boundary.preregistration["attempt_dirs"][slot]
    ):
        raise OuterCloseoutError(f"{slot} selected identity drifted")
    shown = host.show(checked["unit_name"])
    record = {
        **{key: value for key, value in expected_request.items() if key != "status"},
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        **_lease(boundary, host, reference, checked["manager_epoch"]),
        "request_identity": request_identity,
        "status": "PASS" if shown == ABSENT else "REFUSED_IDENTITY_COLLISION",
        "systemctl": shown, "unit_name": checked["unit_name"],
    }
    identity = store.publish(paths["receipt"], record, f"{slot} prelaunch receipt")
    if shown != ABSENT:
        raise OuterCloseoutError(f"{slot} exact unit name was already present")
    validate_arm_prelaunch_receipt(boundary, store, request, request_identity, paths["receipt"])
    return identity


def _gate1_owned(
    boundary: Any, store: ReceiptStore, host: PinnedHost, reference: Any,
    ownership: Mapping[str, Any] | None, gate1: Mapping[str, Any],
    gate1_identity: Mapping[str, Any], ownership_identity: Mapping[str, Any] | None,
    slot: str,
) -> Mapping[str, Any] | None:
    selected = gate1["units"][slot]
    checkpoint = Path(selected["epoch_checkpoint_paths"]["prelaunch"])
    if (
        ownership is None
        or ownership_identity is None
        or not checkpoint.is_file()
        or checkpoint.is_symlink()
    ):
        return None
    expected_units = [
        {"absence_paths": [str(path) for path in _gate1_absence_paths(gate1["units"][name])],
         "slot": name, "systemctl": ABSENT, "unit_name": gate1["units"][name]["unit_name"]}
        for name in GATE1_SLOTS
    ]
    current_reference = reference.verify(
        expected_manager_owner=boundary.root["manager_epoch"]["dbus_unique_owner"])
    owned = (
        set(ownership) == GATE1_OWNERSHIP_FIELDS
        and ownership.get("schema_version") == GATE1_OWNERSHIP_SCHEMA
        and ownership.get("all_units_absent") is True
        and ownership.get("authorizations") == FALSE_AUTHORIZATIONS
        and ownership.get("campaign_root_identity") == boundary.context["root_identity"]
        and ownership.get("package_id") == boundary.root["package"]["package_id"]
        and ownership.get("formal_selection_identity")
            == store.identity(boundary.formal_dir / "selection.json")
        and ownership.get("gate1_selection_identity") == gate1_identity
        and ownership.get("outer_reference_acquisition_identity")
            == store.identity(boundary.formal_dir / "reference-acquisition.json")
        and ownership.get("outer_resource_identity") == store.identity(boundary.formal_dir / "resource-live.json")
        and ownership.get("locks") == host.lock_evidence()
        and ownership.get("outer_reference_verification") == current_reference
        and _same_epoch(boundary, ownership.get("manager_epoch_capture", {}).get("manager_epoch"))
        and ownership.get("units") == expected_units
    )
    if not owned:
        return None
    driver_source = authority._source_snapshot(  # noqa: SLF001
        boundary.context["files"], boundary.context["sources"], "tool.gate1_campaign_driver_v4.py")
    driver = authority._load_module(  # noqa: SLF001
        driver_source, f"_ab16_gate1_driver_{driver_source.sha256[:16]}")
    checkpoint_snapshot = authority.snapshot_regular(checkpoint)
    root_snapshot = authority.snapshot_regular(boundary.campaign / "campaign-root.json")
    selection_snapshot = authority.snapshot_regular(boundary.root["stage_topology"]["gate1_v4"]["selection_path"])
    driver.replay_lifecycle_epoch_checkpoint(
        checkpoint_raw=checkpoint_snapshot.data, checkpoint_identity=authority.detached_identity(checkpoint_snapshot),
        campaign_root_raw=root_snapshot.data, campaign_root_identity=authority.detached_identity(root_snapshot),
        selection_raw=selection_snapshot.data, selection_identity=gate1_identity,
        unit_slot=slot, phase="prelaunch")
    return {
        "campaign_root_identity": boundary.context["root_identity"],
        "formal_selection_identity": store.identity(boundary.formal_dir / "selection.json"),
        "gate1_ownership_identity": dict(ownership_identity),
        "package_id": boundary.root["package"]["package_id"],
        "prelaunch_checkpoint_identity": authority.detached_identity(checkpoint_snapshot),
        "selection_identity": dict(gate1_identity),
        "selection_token": gate1["selection_id"],
        "slot": slot,
        "source": "gate1",
        "unit_name": selected["unit_name"],
    }


def build_child_ledger(
    boundary: Any, store: ReceiptStore, host: PinnedHost,
    reference: Any, formal_selection: Mapping[str, Any],
) -> list[ChildTarget]:
    """Build the finite ledger only from sealed selections and fixed order."""

    for field in ("attempt_dirs", "pre_run_authority_paths", "arm_selection_paths"):
        value = boundary.preregistration.get(field)
        if type(value) is not dict or set(value) != set(ARM_SEQUENCE):
            raise OuterCloseoutError(f"preregistration {field} slot set drifted")
    prelaunch_paths = formal_selection.get("arm_prelaunch_paths")
    if type(prelaunch_paths) is not dict or set(prelaunch_paths) != set(ARM_SEQUENCE):
        raise OuterCloseoutError("formal arm prelaunch slot set drifted")
    if any(
        type(prelaunch_paths[slot]) is not dict
        or set(prelaunch_paths[slot]) != {"receipt", "request"}
        for slot in ARM_SEQUENCE
    ):
        raise OuterCloseoutError("formal arm prelaunch path schema drifted")
    gate1, gate1_identity = _gate1(boundary)
    ownership_path = Path(formal_selection["gate1_prelaunch_ownership_path"])
    ownership: Mapping[str, Any] | None = None
    ownership_identity: Mapping[str, Any] | None = None
    ownership_error: Mapping[str, str] | None = None
    if ownership_path.is_file() and not ownership_path.is_symlink():
        try:
            ownership, ownership_identity = store.document(ownership_path, "Gate1 ownership")
        except Exception as exc:
            ownership_error = _failure("GATE1_PRELAUNCH_PROVENANCE_REPLAY_FAILED", exc)
    elif os.path.lexists(ownership_path):
        ownership_error = _failure(
            "GATE1_PRELAUNCH_PROVENANCE_SURFACE_INVALID",
            "Gate1 ownership is not one regular non-symlink file",
        )
    else:
        ownership_error = _failure(
            "GATE1_PRELAUNCH_PROVENANCE_ABSENT",
            "Gate1 ownership receipt is absent",
        )
    targets: list[ChildTarget] = []
    for slot in GATE1_SLOTS:
        evidence: Mapping[str, Any] | None = None
        provenance_error = ownership_error
        if provenance_error is None:
            try:
                evidence = _gate1_owned(
                    boundary,
                    store,
                    host,
                    reference,
                    ownership,
                    gate1,
                    gate1_identity,
                    ownership_identity,
                    slot,
                )
                if evidence is None:
                    provenance_error = _failure(
                        "GATE1_PRELAUNCH_PROVENANCE_UNPROVEN",
                        f"{slot} Gate1 ownership joins did not verify",
                    )
            except Exception as exc:
                provenance_error = _failure("GATE1_PRELAUNCH_PROVENANCE_REPLAY_FAILED", exc)
        selected = gate1["units"][slot]
        targets.append(ChildTarget(
            "gate1",
            slot,
            selected["unit_name"],
            Path(selected["raw_dir"]) / "inner-lifecycle.json",
            evidence,
            gate1_identity,
            None,
            gate1["selection_id"],
            provenance_error,
        ))
    lifecycle: Any | None = None
    verifier: Any | None = None
    resource_modules_error: Mapping[str, str] | None = None
    try:
        lifecycle, verifier = authority._resource_modules(boundary.context)  # noqa: SLF001
    except Exception as exc:
        resource_modules_error = _failure("ARM_RESOURCE_PROVENANCE_LOADER_FAILED", exc)
    formal_selection_identity: Mapping[str, Any] | None = None
    formal_selection_error: Mapping[str, str] | None = None
    try:
        formal_selection_identity = store.identity(boundary.formal_dir / "selection.json")
    except Exception as exc:
        formal_selection_error = _failure("FORMAL_SELECTION_IDENTITY_REPLAY_FAILED", exc)
    for slot in ARM_SEQUENCE:
        attempt = Path(boundary.preregistration["attempt_dirs"][slot])
        pre_path = Path(boundary.preregistration["pre_run_authority_paths"][slot])
        select_path = Path(boundary.preregistration["arm_selection_paths"][slot])
        pre_exists = pre_path.is_file() and not pre_path.is_symlink()
        select_exists = select_path.is_file() and not select_path.is_symlink()
        unit, pre_identity, select_identity, prelaunch_evidence = "", None, None, None
        pre: Mapping[str, Any] | None = None
        checked: Mapping[str, Any] | None = None
        provenance_error = resource_modules_error
        if os.path.lexists(pre_path) and not pre_exists:
            provenance_error = _failure(
                "ARM_PRE_RUN_PROVENANCE_SURFACE_INVALID",
                f"{slot} pre-run authority is not one regular non-symlink file",
            )
        elif os.path.lexists(select_path) and not select_exists:
            provenance_error = _failure(
                "ARM_SELECTION_PROVENANCE_SURFACE_INVALID",
                f"{slot} selection is not one regular non-symlink file",
            )
        elif select_exists and not pre_exists:
            provenance_error = _failure(
                "ARM_SELECTION_WITHOUT_PRE_RUN",
                f"{slot} selection exists without pre-run authority",
            )
        elif pre_exists and provenance_error is None:
            try:
                pre, pre_identity = store.document(pre_path, f"{slot} pre-run")
                if lifecycle is None:
                    raise OuterCloseoutError("arm lifecycle validator is unavailable")
                checked = lifecycle.validate_pre_run_authority(pre, expected_slot=slot)
                unit = checked["unit_name"]
                if checked["attempt_dir"] != str(attempt):
                    raise OuterCloseoutError(f"{slot} attempt directory drifted")
            except Exception as exc:
                provenance_error = _failure("ARM_PRE_RUN_PROVENANCE_REPLAY_FAILED", exc)
        if unit and provenance_error is None and formal_selection_error is not None:
            provenance_error = formal_selection_error
        if unit and select_exists and provenance_error is None:
            try:
                selected, select_identity = store.document(select_path, f"{slot} selection")
                if (
                    lifecycle is None
                    or verifier is None
                    or checked is None
                    or pre is None
                    or pre_identity is None
                ):
                    raise OuterCloseoutError("arm provenance validators are unavailable")
                lifecycle.validate_runner_selection(
                    selected, pre_run_authority=checked, pre_run_authority_identity=pre_identity)
                replayed_pre = verifier.validate_pre_run_authority(pre, expected_slot=slot)
                verifier._validate_selection(  # noqa: SLF001
                    selected, pre_run=replayed_pre, pre_run_identity=pre_identity)
                receipt_path = Path(formal_selection["arm_prelaunch_paths"][slot]["receipt"])
                launch_path = attempt / "manager-epoch-launch.json"
                receipt_exists = receipt_path.is_file() and not receipt_path.is_symlink()
                launch_exists = launch_path.is_file() and not launch_path.is_symlink()
                receipt_present = os.path.lexists(receipt_path)
                launch_present = os.path.lexists(launch_path)
                if (receipt_present and not receipt_exists) or (launch_present and not launch_exists):
                    provenance_error = _failure(
                        "ARM_PRELAUNCH_PROVENANCE_SURFACE_INVALID",
                        f"{slot} receipt/launch contains a non-regular or symlink surface",
                    )
                elif receipt_exists and launch_exists:
                    request_path = Path(formal_selection["arm_prelaunch_paths"][slot]["request"])
                    request, request_identity = store.document(request_path, f"{slot} request")
                    receipt, receipt_identity = validate_arm_prelaunch_receipt(
                        boundary, store, request, request_identity, receipt_path)
                    launch, launch_identity = store.document(launch_path, f"{slot} launch")
                    verifier._replay_epoch_observation_file(  # noqa: SLF001
                        pre_run=replayed_pre, phase="launch", embedded_observation=launch)
                    owned = (
                        receipt["unit_name"] == unit
                        and receipt["locks"] == host.lock_evidence()
                        and receipt["outer_reference_verification"] == reference.verify(
                            expected_manager_owner=boundary.root["manager_epoch"]["dbus_unique_owner"])
                    )
                    if owned:
                        prelaunch_evidence = {
                            "campaign_root_identity": boundary.context["root_identity"],
                            "formal_selection_identity": formal_selection_identity,
                            "launch_identity": launch_identity,
                            "package_id": boundary.root["package"]["package_id"],
                            "pre_run_identity": pre_identity,
                            "prelaunch_receipt_identity": receipt_identity,
                            "request_identity": request_identity,
                            "selection_identity": select_identity,
                            "slot": slot,
                            "source": "arm",
                            "unit_name": unit,
                        }
                    else:
                        provenance_error = _failure(
                            "ARM_PRELAUNCH_PROVENANCE_UNPROVEN",
                            f"{slot} prelaunch ownership joins did not verify",
                        )
                elif receipt_present or launch_present:
                    provenance_error = _failure(
                        "ARM_PRELAUNCH_PROVENANCE_INCOMPLETE",
                        f"{slot} receipt/launch pair is incomplete",
                    )
            except Exception as exc:
                provenance_error = _failure("ARM_PRELAUNCH_PROVENANCE_REPLAY_FAILED", exc)
        targets.append(ChildTarget(
            "arm",
            slot,
            unit,
            attempt / "inner-lifecycle.json",
            prelaunch_evidence,
            select_identity,
            pre_identity,
            "",
            provenance_error,
        ))
    return targets


def _prelaunch_evidence_matches(target: ChildTarget) -> bool:
    evidence = target.prelaunch_evidence
    if type(evidence) is not dict:
        return False
    common = {
        "campaign_root_identity",
        "formal_selection_identity",
        "package_id",
        "selection_identity",
        "slot",
        "source",
        "unit_name",
    }
    expected = (
        common | {"gate1_ownership_identity", "prelaunch_checkpoint_identity", "selection_token"}
        if target.source == "gate1"
        else common
        | {
            "launch_identity",
            "pre_run_identity",
            "prelaunch_receipt_identity",
            "request_identity",
        }
    )
    if set(evidence) != expected:
        return False
    try:
        closeout_state.reject_none(evidence, f"{target.source}/{target.slot} prelaunch evidence")
        for key, value in evidence.items():
            if key.endswith("_identity"):
                closeout_state.validate_identity_join(
                    value,
                    f"{target.source}/{target.slot} {key}",
                )
    except Exception:
        return False
    if (
        evidence["source"] != target.source
        or evidence["slot"] != target.slot
        or evidence["unit_name"] != target.unit_name
        or evidence["selection_identity"] != target.selection_identity
    ):
        return False
    if target.source == "gate1" and evidence["selection_token"] != target.selection_token:
        return False
    if target.source == "arm" and evidence["pre_run_identity"] != target.pre_run_identity:
        return False
    return target.source in {"gate1", "arm"}


def _contain(
    store: ReceiptStore, host: PinnedHost, target: ChildTarget, *, abnormal: bool
) -> dict[str, object]:
    prelaunch_owned = _prelaunch_evidence_matches(target)
    base = {
        "inner_path": str(target.inner_path),
        "prelaunch_owned": prelaunch_owned,
        "slot": target.slot, "source": target.source, "unit_name": target.unit_name,
    }
    if target.prelaunch_evidence is not None:
        base["prelaunch_evidence"] = dict(target.prelaunch_evidence)
    if target.provenance_error is not None:
        base["provenance_error"] = dict(target.provenance_error)
    if not target.unit_name:
        if target.provenance_error is not None:
            return {
                **base,
                "classification": "IDENTITY_GAP",
                "errors": [dict(target.provenance_error)],
                "frozen_identity": _incomplete_frozen_identity(
                    source=target.source,
                    slot=target.slot,
                    unit_name="",
                    ownership_classification="IDENTITY_GAP",
                    error=target.provenance_error["detail"],
                ),
            }
        return {
            **base,
            "classification": "NOT_CREATED",
            "frozen_identity": host.freeze_identity(
                source=target.source, slot=target.slot, unit_name="", shown=ABSENT,
                ownership_classification="NOT_CREATED"),
        }
    shown = host.show(target.unit_name)
    if shown == ABSENT:
        return {
            **base,
            "classification": "ABSENT",
            "frozen_identity": host.freeze_identity(
                source=target.source, slot=target.slot, unit_name=target.unit_name, shown=shown,
                ownership_classification="ABSENT"),
            "systemctl": shown,
        }
    if not abnormal:
        return {
            **base,
            "classification": "CONTAINMENT_REQUIRED",
            "frozen_identity": host.freeze_identity(
                source=target.source, slot=target.slot, unit_name=target.unit_name, shown=shown,
                ownership_classification="CONTAINMENT_REQUIRED"),
            "systemctl": shown,
        }
    attributable, expected_invocation, inner_identity = prelaunch_owned, "", None
    if target.inner_path.is_file() and not target.inner_path.is_symlink():
        inner, inner_identity = store.document(target.inner_path, f"{target.slot} inner")
        invocation = inner.get("invocation_id")
        selection_join = (
            inner.get("selection_id") == target.selection_token
            if target.source == "gate1"
            else inner.get("runner_selection_identity") == target.selection_identity
            and inner.get("pre_run_authority_identity") == target.pre_run_identity
        )
        inner_join = (
            inner.get("slot", inner.get("unit_slot")) == target.slot
            and inner.get("unit_name") == target.unit_name
            and type(invocation) is str
            and INVOCATION_RE.fullmatch(invocation) is not None
            and selection_join
        )
        attributable = prelaunch_owned and inner_join
        expected_invocation = invocation if attributable else ""
    identity_ok = (
        attributable
        and shown["LoadState"] == "loaded"
        and shown["ActiveState"] in {"active", "activating", "deactivating", "failed"}
        and INVOCATION_RE.fullmatch(shown["InvocationID"]) is not None
        and (not inner_identity or shown["InvocationID"] == expected_invocation)
        and shown["MainPID"].isdigit()
        and int(shown["MainPID"]) > 0
    )
    if not identity_ok:
        return {
            **base,
            "classification": "IDENTITY_GAP",
            "frozen_identity": host.freeze_identity(
                source=target.source, slot=target.slot, unit_name=target.unit_name, shown=shown,
                ownership_classification="IDENTITY_GAP"),
            "systemctl": shown,
        }
    try:
        processes = host.cgroup_processes(shown["ControlGroup"])
        stable = (
            any(item["pid"] == int(shown["MainPID"]) for item in processes)
            and host.show(target.unit_name) == shown
            and host.cgroup_processes(shown["ControlGroup"]) == processes
        )
    except Exception as exc:
        return {
            **base,
            "classification": "IDENTITY_GAP",
            "errors": [_failure("CHILD_IDENTITY_FREEZE_FAILED", exc)],
            "frozen_identity": _incomplete_frozen_identity(
                source=target.source,
                slot=target.slot,
                unit_name=target.unit_name,
                ownership_classification="IDENTITY_GAP",
                error=exc,
                invocation_id=shown.get("InvocationID", ""),
                control_group=shown.get("ControlGroup", ""),
            ),
            "systemctl": shown,
        }
    if not stable:
        return {
            **base,
            "classification": "IDENTITY_GAP",
            "frozen_identity": host.freeze_identity(
                source=target.source, slot=target.slot, unit_name=target.unit_name, shown=shown,
                ownership_classification="IDENTITY_GAP"),
            "systemctl": shown,
        }
    frozen = {"control_group": shown["ControlGroup"], "inner_identity": inner_identity,
              "processes": processes, "systemctl": shown}
    try:
        errors = host.stop_reset_once(target.unit_name)
    except Exception as exc:
        errors = [_failure("CHILD_STOP_RESET_FAILED_OR_UNCERTAIN", exc)]
    try:
        absence = host.wait_state(target.unit_name, shown["ControlGroup"], processes, referenced=False)
    except Exception as exc:
        errors.append(_failure("CHILD_ABSENCE_UNPROVED", exc))
        absence = {"cgroup_absent": False, "processes_absent": False}
    return {
        **base,
        "absence": absence,
        "classification": "STARTED_CONTAINED_PASS" if not errors else "CONTAINMENT_FAILED",
        "errors": errors, "prestate": frozen, "reset_count": 1, "stop_count": 1,
        "frozen_identity": {
            "control_group": shown["ControlGroup"],
            "identity_complete": True,
            "invocation_id": shown["InvocationID"],
            "ownership_classification": (
                "STARTED_CONTAINED_PASS" if not errors else "CONTAINMENT_FAILED"
            ),
            "processes": processes,
            "slot": target.slot,
            "source": target.source,
            "unit_name": target.unit_name,
        },
    }


def audit_children(
    boundary: Any, store: ReceiptStore, host: PinnedHost, reference: Any,
    formal_selection: Mapping[str, Any], *, abnormal: bool,
) -> dict[str, object]:
    targets = build_child_ledger(boundary, store, host, reference, formal_selection)
    if [(target.source, target.slot) for target in targets] != list(EXPECTED_CHILD_ORDER):
        raise OuterCloseoutError("finite child target order drifted")
    nonempty_units = [target.unit_name for target in targets if target.unit_name]
    if len(nonempty_units) != len(set(nonempty_units)):
        raise OuterCloseoutError("finite child targets contain duplicate unit names")
    records: list[dict[str, object]] = []
    failed_classifications = {
        "AUDIT_FAILED",
        "CONTAINMENT_FAILED",
        "CONTAINMENT_REQUIRED",
        "IDENTITY_GAP",
    }
    abnormal_mode = abnormal
    for target in targets:
        try:
            item = _contain(store, host, target, abnormal=abnormal_mode)
            if item["classification"] == "CONTAINMENT_REQUIRED":
                abnormal_mode = True
                item = _contain(store, host, target, abnormal=True)
        except Exception as exc:
            abnormal_mode = True
            effect_attempted = target.unit_name in getattr(host, "cleaned_units", set())
            item = {
                "classification": "AUDIT_FAILED",
                "errors": [_failure("CHILD_AUDIT_FAILED", exc)],
                "frozen_identity": _incomplete_frozen_identity(
                    source=target.source,
                    slot=target.slot,
                    unit_name=target.unit_name,
                    ownership_classification="AUDIT_FAILED",
                    error=exc,
                ),
                "inner_path": str(target.inner_path),
                "prelaunch_owned": _prelaunch_evidence_matches(target),
                "reset_count": int(effect_attempted),
                "slot": target.slot,
                "source": target.source,
                "stop_count": int(effect_attempted),
                "unit_name": target.unit_name,
            }
            if target.provenance_error is not None:
                item["provenance_error"] = dict(target.provenance_error)
        records.append(item)
        if item["classification"] in failed_classifications:
            abnormal_mode = True
    replay: dict[str, object] = {}
    audit_errors: list[dict[str, str]] = []
    if not abnormal_mode:
        arm_cleanup_replay: dict[str, object] = {}
        replay = {"arm_cleanup_replay": arm_cleanup_replay}
        try:
            continuation, continuation_identity = authority._continuation(boundary.context)  # noqa: SLF001
            replay["gate1_continuation_identity"] = continuation_identity
            replay["gate1_detached_identities"] = continuation["detached_replay_identities"]
        except Exception as exc:
            audit_errors.append(_failure("GATE1_NORMAL_CLEANUP_REPLAY_FAILED", exc))
        for slot in ARM_SEQUENCE:
            try:
                consumption = authority._load_consumption(  # noqa: SLF001
                    boundary.context,
                    slot=slot,
                    required_credible=True,
                )
                arm_cleanup_replay[slot] = {
                    "consumption_id": consumption["consumption_id"],
                    "resource_replay_identity": consumption["resource_replay_identity"],
                    "resource_terminal_identity": consumption["resource_terminal_identity"],
                }
            except Exception as exc:
                audit_errors.append(_failure(
                    "ARM_NORMAL_CLEANUP_REPLAY_FAILED",
                    f"{slot}: {type(exc).__name__}: {exc}",
                ))
        if audit_errors:
            abnormal_mode = True
    frozen_children = [item["frozen_identity"] for item in records]
    dummy_outer = host.freeze_identity(
        source="outer", slot="formal", unit_name="", shown=ABSENT, ownership_classification="NOT_STARTED")
    try:
        observation = host.observe_frozen_absence(
            {"child_audit_identity": {}, "children": frozen_children, "outer": dummy_outer})
    except Exception as exc:
        abnormal_mode = True
        observation_error = _failure("CHILD_FINAL_OBSERVATION_FAILED", exc)
        observation = {
            "all_absent": False,
            "error": observation_error,
            "records": [],
        }
        audit_errors.append(observation_error)
    all_absent = observation["all_absent"]
    containment_used = any(
        int(item.get("stop_count", 0)) > 0 or int(item.get("reset_count", 0)) > 0
        for item in records
    )
    record = {
        "all_children_absent": all_absent,
        "audit_errors": audit_errors,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "containment_used": containment_used,
        "mode": "ABNORMAL" if abnormal_mode else "NORMAL_REPLAY",
        "normal_replay": replay,
        "frozen_children": frozen_children,
        "final_observation": observation,
        "records": records,
        "schema_version": CHILD_AUDIT_SCHEMA,
        "status": (
            "PASS"
            if all_absent and not abnormal_mode and not containment_used and replay and not audit_errors
            and all(item["classification"] not in failed_classifications for item in records)
            else "CONSUMED_INCOMPLETE"
        ),
    }
    publication = closeout_state.PublicationEffect()
    publication.begin()
    pending_ledger: dict[str, object] = {
        "child_audit_identity": None,
        "children": frozen_children,
    }
    try:
        identity = store.publish(
            formal_selection["child_audit_path"],
            record,
            "finite child audit",
            publication=publication,
        )
        checked_identity = closeout_state.validate_identity_join(identity, "finite child audit")
        if publication.returned_identity is None:
            publication.note_returned(checked_identity)
        if publication.recorded_identity is None:
            publication.note_recorded(checked_identity)
        if publication.recorded_identity != checked_identity:
            raise OuterCloseoutError("finite child audit proof/effect identity drifted")
    except Exception as exc:
        publication.note_error(exc)
        pending_ledger["child_audit_identity"] = publication.recorded_identity
        raise ChildAuditPublicationError(
            exc,
            record=record,
            ledger=pending_ledger,
            publication_effect=publication.record(),
        ) from exc
    identity = checked_identity
    return {
        "identity": identity,
        "ledger": {"child_audit_identity": identity, "children": frozen_children},
        "publication_effect": publication.record(),
        "record": record,
    }


def bind_outer_ledger(child_audit: Mapping[str, Any], outer: Mapping[str, Any]) -> dict[str, object]:
    ledger = dict(child_audit["ledger"])
    if type(ledger.get("children")) is not list or type(outer) is not dict:
        raise OuterCloseoutError("finite child/outer ledger is malformed")
    identity = closeout_state.validate_identity_join(
        child_audit.get("identity"),
        "finite child audit",
    )
    if ledger.get("child_audit_identity") != identity:
        raise OuterCloseoutError("finite child audit identity join drifted")
    ledger["outer"] = dict(outer)
    return validate_frozen_ledger(ledger)
