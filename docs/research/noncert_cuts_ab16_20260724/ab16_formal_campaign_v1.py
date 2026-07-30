#!/usr/bin/env python3
"""Thin fail-closed supervisor for one formal AB16 campaign.

This package-pinned role consumes, but never publishes, Gate-B approval,
formal launch admission, or formal selection.  It owns only the outer
campaign lifecycle:

* acquire the exact three formal locks and duplicate the same open-file
  descriptions to the independently selected guardian;
* consume the one formal attempt, validate the external selection, and launch
  the selected whole-campaign outer unit exactly once;
* acquire and release the existing ``PersistentUnitReference`` only through
  the closeout-state owner;
* service helper-owned Gate1/organic prelaunch evidence, mirror the finite
  4+16+outer ledger to the guardian, and preserve containment after failure;
* publish normal outer receipts, release locks in the fixed post-Unref order,
  and launch the independent success verifier as a fresh selected-byte role.

It contains no Gate1, baseline, solver, cut, witness, classification, detached
success, or mathematical implementation.  Every successful or incomplete
record remains research-only and preserves ``U=(1188,18)``, ``L=absent``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import sys
import time
from typing import Any, cast, Protocol

from docs.research.noncert_cuts_ab16_20260724 import ab16_authority_v2 as authority
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_launch_validator_v1 as launch_validator,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_success_verifier_v1 as success_verifier,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_outer_closeout_state_v1 as closeout_state,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_outer_guardian_v1 as guardian,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_outer_refunit_closeout_v1 as closeout_helper,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_resource_admission_v1 as resource_admission,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    systemd_unit_reference_v1 as unit_reference,
)


AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
ARM_SEQUENCE = tuple(closeout_state.ARM_SEQUENCE)
GATE1_SLOTS = tuple(closeout_state.GATE1_SLOTS)
LEDGER_PHASES = closeout_state.GUARDIAN_LEDGER_PHASES
FALSE_CLAIMS = dict(launch_validator.FALSE_CLAIMS)
POLL_SECONDS = 0.10
RECORD_WAIT_SECONDS = 600.0
GUARDIAN_WAIT_SECONDS = 120.0
MAX_SELECTED_OUTPUT = 8 * 1024 * 1024
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
CONTAINMENT_GUARDIAN_ABSENCE_SCHEMA = (
    "noncert-cuts-ab16-containment-guardian-absence-v1"
)
FAILURE_RELEASE_SCHEMA = "noncert-cuts-ab16-formal-pre-release-failure-v3"
FAILURE_TERMINAL_RELEASE_SCHEMA = (
    "noncert-cuts-ab16-formal-failure-terminal-release-v3"
)

FULL_SHOW_FIELDS = (
    "ActiveState",
    "CollectMode",
    "ControlGroup",
    "ExecMainCode",
    "ExecMainStatus",
    "InvocationID",
    "KillMode",
    "LoadState",
    "MainPID",
    "MemoryHigh",
    "MemoryMax",
    "MemorySwapMax",
    "OOMPolicy",
    "Result",
    "RuntimeMaxUSec",
    "SendSIGKILL",
    "SubState",
)
TERMINAL_FIELDS = (
    "ActiveState",
    "CollectMode",
    "ControlGroup",
    "ExecMainCode",
    "ExecMainStatus",
    "InvocationID",
    "LoadState",
    "Result",
    "SubState",
)
class FormalCampaignError(RuntimeError):
    """One formal connector invariant failed closed."""


class IrreversibleFormalFailure(FormalCampaignError):
    """A side effect may have happened and must never be retried."""


@dataclass(frozen=True)
class SelectedDirectResult:
    """Captured exit status and bounded output from one selected-byte role."""

    returncode: int
    stderr: bytes
    stdout: bytes


class GuardianLaunchFailure(IrreversibleFormalFailure):
    """The selected guardian launch failed after its exact prelaunch check."""

    def __init__(
        self,
        error: BaseException,
        *,
        containment_cleared: bool,
        cleanup_errors: Sequence[Mapping[str, str]],
        frozen_identity: Mapping[str, object] | None,
    ) -> None:
        super().__init__(f"guardian launch failed or is uncertain: {error}")
        self.containment_cleared = containment_cleared
        self.cleanup_errors = [dict(item) for item in cleanup_errors]
        self.frozen_identity = (
            dict(frozen_identity) if frozen_identity is not None else None
        )


@dataclass
class GuardianSession:
    """Supervisor-side proof/effect state for one guardian connection."""

    unit_name: str
    unit_identity: dict[str, object]
    listener: guardian.GuardianControlListener
    connection: Any
    ready: dict[str, object]
    ready_identity: dict[str, object]
    last_message_identity: dict[str, object]
    process_pidfd: int | None
    activation_sent: bool = False
    activation_returned: bool = False
    terminal_sent: bool = False
    close_received: bool = False
    connection_close_attempted: bool = False
    connection_close_returned: bool = False
    connection_close_error: dict[str, str] | None = None
    connection_closed: bool = False
    listener_closed: bool = False


@dataclass
class SupervisorState:
    """Campaign-specific state layered over the monotone closeout owner."""

    attempt: closeout_state.AttemptState = field(default_factory=closeout_state.AttemptState)
    selection: dict[str, object] | None = None
    selection_identity: dict[str, object] | None = None
    outer_identity: dict[str, object] | None = None
    outer_resource_admission: dict[str, object] | None = None
    guardian: GuardianSession | None = None
    ledger: dict[str, object] | None = None
    ledger_sequence: int = 0
    controller_identity: dict[str, object] | None = None
    child_audit_identity: dict[str, object] | None = None
    outer_terminal_identity: dict[str, object] | None = None
    observer_identity: dict[str, object] | None = None
    pre_unref_identity: dict[str, object] | None = None
    post_unref_identity: dict[str, object] | None = None
    detached_success_identity: dict[str, object] | None = None
    reference_terminal: dict[str, object] | None = None
    guardian_close_identity: dict[str, object] | None = None
    dual_release_identity: dict[str, object] | None = None
    failure: dict[str, str] | None = None

    @property
    def success_eligible(self) -> bool:
        return (
            self.failure is None
            and not self.attempt.irreversible_incomplete
            and self.selection_identity is not None
        )


class FailureContainmentPort:
    """Bind guardian absence ahead of the supervisor's final lock release."""

    def __init__(
        self,
        *,
        boundary: authority.FormalRuntimeBoundary,
        context: Mapping[str, object],
        state: SupervisorState,
        store: closeout_helper.ReceiptStore,
        host: closeout_helper.PinnedHost,
        latch: closeout_helper.TerminationLatch,
    ) -> None:
        self.boundary = boundary
        self.context = dict(context)
        self.state = state
        self.store = store
        self.host = host
        self.latch = latch

    def lock_evidence(self) -> list[dict[str, object]]:
        return self.host.lock_evidence()

    def observe_frozen_absence(
        self,
        ledger: Mapping[str, object],
    ) -> dict[str, object]:
        return self.host.observe_frozen_absence(ledger)

    def prepare_guardian_release(
        self,
        ledger: Mapping[str, object],
    ) -> dict[str, object]:
        """Stop only the handoff-bound guardian, prove absence, and publish once."""

        session = self.state.guardian
        if session is None or self.state.selection_identity is None:
            raise IrreversibleFormalFailure(
                "failure containment lacks the selected guardian identity"
            )
        closeout_state.validate_frozen_ledger(ledger)
        errors: list[dict[str, str]] = []
        if not session.connection_close_attempted:
            try:
                _close_guardian_connection(session)
            except BaseException as exc:
                errors.append(
                    _failure(
                        "GUARDIAN_CONTROL_DROP_FAILED_OR_UNCERTAIN",
                        exc,
                    )
                )
        elif not session.connection_close_returned:
            errors.append(
                session.connection_close_error
                or _failure(
                    "GUARDIAN_CONTROL_DROP_FAILED_OR_UNCERTAIN",
                    "guardian connection close returned no canonical effect",
                )
            )
        shown = self.host.show(session.unit_name)
        if shown != closeout_helper.ABSENT:
            current = _guardian_unit_identity(
                self.host,
                unit_name=session.unit_name,
                shown=shown,
            )
            if current != session.unit_identity:
                raise IrreversibleFormalFailure(
                    "guardian identity drifted before failure containment"
                )
            if session.unit_name not in self.host.cleaned_units:
                errors.extend(self.host.stop_reset_once(session.unit_name))
        while True:
            try:
                absence = _wait_guardian_absence(
                    self.host,
                    session,
                    timeout_seconds=GUARDIAN_WAIT_SECONDS,
                )
                break
            except BaseException as exc:
                item = _failure(
                    "GUARDIAN_ABSENCE_WAIT_FAILED",
                    exc,
                )
                if item not in errors:
                    errors.append(item)
                time.sleep(closeout_state.HOLD_POLL_SECONDS)
        record = {
            "authorizations": dict(FALSE_CLAIMS),
            "campaign_root_identity": self.context["campaign_root_identity"],
            "errors": errors,
            "formal_selection_identity": self.state.selection_identity,
            "frozen_ledger_sha256": hashlib.sha256(
                authority.canonical_json(
                    closeout_state.validate_frozen_ledger(ledger)
                )
            ).hexdigest(),
            "guardian_absence": absence,
            "guardian_identity": session.unit_identity,
            "lower_bound": "absent",
            "outcome": "INCOMPLETE",
            "package_id": self.context["package_id"],
            "production_certified": False,
            "schema_version": CONTAINMENT_GUARDIAN_ABSENCE_SCHEMA,
            "status": "GUARDIAN_ABSENT",
            "success_eligible": False,
            "upper_bound": [1188, 18],
        }
        return self.store.publish(
            self.boundary.formal_dir
            / "containment-guardian-absence.json",
            record,
            "containment guardian absence",
        )

    def release_locks_once(self) -> dict[str, object]:
        return self.host.release_locks_once()


class Clock(Protocol):
    def __call__(self) -> float:
        """Return a monotonic timestamp."""


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _failure(code: str, error: BaseException | str) -> dict[str, str]:
    return closeout_state.failure(code, error)


def _process_identity(pid: int) -> dict[str, int]:
    if type(pid) is not int or pid <= 0:
        raise FormalCampaignError("process PID is malformed")
    starttime = guardian.read_process_starttime(pid)
    if type(starttime) is not int or starttime <= 0:
        raise FormalCampaignError("process starttime is malformed")
    return {"pid": pid, "starttime": starttime}


def _validate_live_launch_owner(
    artifact: Mapping[str, object],
    *,
    label: str,
) -> dict[str, int]:
    """Prove that the exact external launch-owner session is still alive."""

    publisher = artifact.get("publisher")
    if type(publisher) is not dict:
        raise FormalCampaignError(f"{label} lacks its validated publisher")
    actor = publisher.get("actor")
    if type(actor) is not dict:
        raise FormalCampaignError(f"{label} lacks its validated publisher actor")
    pid = actor.get("pid")
    starttime = actor.get("starttime")
    if type(pid) is not int or type(starttime) is not int:
        raise FormalCampaignError(f"{label} publisher process identity is malformed")
    if pid == os.getpid():
        raise FormalCampaignError(f"{label} was self-authorized by the formal supervisor")
    expected = {"pid": pid, "starttime": starttime}
    observed = _process_identity(pid)
    if observed != expected:
        raise FormalCampaignError(f"{label} publisher process identity is no longer live")
    return expected


def _identity(path: Path | str) -> dict[str, object]:
    return authority.detached_identity(authority.snapshot_regular(path))


def _read_record(
    path: Path | str,
    *,
    expected_identity: Mapping[str, object] | None,
    label: str,
) -> tuple[dict[str, Any], dict[str, object]]:
    try:
        return launch_validator.read_canonical_record(
            path,
            expected_identity=expected_identity,
            label=label,
        )
    except Exception as exc:
        raise FormalCampaignError(f"{label} replay failed: {exc}") from exc


def _wait_record(
    path: Path | str,
    *,
    expected_identity: Mapping[str, object] | None,
    label: str,
    timeout_seconds: float,
    monotonic: Clock = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    checkpoint: Callable[[], None] | None = None,
) -> tuple[dict[str, Any], dict[str, object]]:
    target = Path(path)
    deadline = monotonic() + timeout_seconds
    while monotonic() <= deadline:
        if checkpoint is not None:
            checkpoint()
        try:
            observed = os.lstat(target)
        except FileNotFoundError:
            sleeper(POLL_SECONDS)
            continue
        except OSError as exc:
            raise FormalCampaignError(
                f"{label} surface could not be inspected"
            ) from exc
        observed_mode = stat.S_IMODE(observed.st_mode)
        if stat.S_ISREG(observed.st_mode) and observed_mode == 0o444:
            return _read_record(
                target,
                expected_identity=expected_identity,
                label=label,
            )
        if stat.S_ISREG(observed.st_mode) and observed_mode == 0o600:
            sleeper(POLL_SECONDS)
            continue
        raise FormalCampaignError(
            f"{label} surface is not one completed readonly regular file"
        )
    raise FormalCampaignError(f"{label} did not appear before its fixed deadline")


def _common_receipt(
    context: Mapping[str, object],
    selection_identity: Mapping[str, object],
    *,
    phase: str,
    **payload: object,
) -> dict[str, object]:
    expected_payload = success_verifier.PHASE_PAYLOAD_FIELDS.get(phase)
    if expected_payload is None or set(payload) != set(expected_payload):
        raise FormalCampaignError(f"{phase} receipt payload field set drifted")
    return {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_CLAIMS),
        "campaign_root_identity": context["campaign_root_identity"],
        "created_at_utc": _utc_now(),
        "formal_selection_identity": dict(selection_identity),
        "manager_epoch": dict(context["manager_epoch"]),
        "package_id": context["package_id"],
        "schema_version": success_verifier.PHASE_SCHEMAS[phase],
        "status": "PASS",
        **payload,
    }


def _publish_phase(
    store: closeout_helper.ReceiptStore,
    *,
    path: Path | str,
    record: Mapping[str, object],
    phase: str,
    validator: Callable[..., Mapping[str, object]],
    validator_kwargs: Mapping[str, object],
    publication: closeout_state.PublicationEffect | None = None,
) -> dict[str, object]:
    try:
        checked = dict(validator(record, **dict(validator_kwargs)))
    except Exception as exc:
        raise FormalCampaignError(f"{phase} proposed receipt failed its independent schema: {exc}") from exc
    return store.publish(path, checked, phase, publication=publication)


def validate_resource_gate(
    campaign_dir: Path | str,
    *,
    lock_identities: Sequence[Mapping[str, object]],
    observation_context: Mapping[str, object],
    meminfo: Mapping[str, int] | None = None,
    disk_free: int | None = None,
    conflicts: Sequence[Mapping[str, object]] | None = None,
    allowed_same_uid_processes: Sequence[Mapping[str, int]] = (),
) -> dict[str, object]:
    """Validate one post-lock formal admission and return its strict receipt."""

    try:
        return resource_admission.evaluate_resource_admission(
            campaign_dir,
            stage=resource_admission.FORMAL_ORGANIC_ARM,
            lock_identities=lock_identities,
            lock_identity_format=resource_admission.FORMAL_LOCK_IDENTITY_FORMAT,
            observation_context=observation_context,
            meminfo=meminfo,
            disk_free=disk_free,
            conflicts=conflicts,
            allowed_same_uid_processes=allowed_same_uid_processes,
        )
    except resource_admission.ResourceAdmissionError as exc:
        raise FormalCampaignError(f"formal resource admission failed: {exc}") from exc


def _formal_resource_allowlist(
    state: SupervisorState,
) -> list[dict[str, int]]:
    session = state.guardian
    if session is None:
        raise FormalCampaignError("formal resource recheck lacks its live guardian")
    actor = session.ready.get("guardian_process_identity")
    if type(actor) is not dict or set(actor) != {"pid", "starttime"}:
        raise FormalCampaignError("guardian resource allowlist identity is malformed")
    pid = actor["pid"]
    starttime = actor["starttime"]
    if type(pid) is not int or type(starttime) is not int:
        raise FormalCampaignError("guardian resource allowlist values are malformed")
    expected = _process_identity(pid)
    if expected != {"pid": pid, "starttime": starttime}:
        raise FormalCampaignError("guardian resource allowlist identity is no longer live")
    supervisor = _process_identity(os.getpid())
    if supervisor is None or supervisor == expected:
        raise FormalCampaignError("formal supervisor resource identity is malformed")
    return [supervisor, {"pid": pid, "starttime": starttime}]


def _resource_observation_context(
    context: Mapping[str, object],
    *,
    authority_identity: Mapping[str, object],
    kind: str,
    target: str,
    ordinal: int = 0,
    slot: str = "",
) -> dict[str, object]:
    campaign_identity = context.get("campaign_root_identity")
    if type(campaign_identity) is not dict:
        raise FormalCampaignError("formal resource scope identity is malformed")
    scope_id = campaign_identity.get("sha256")
    authority_id = authority_identity.get("sha256")
    if type(scope_id) is not str or type(authority_id) is not str:
        raise FormalCampaignError("formal resource SHA-256 identity is malformed")
    sequence = ordinal + 1 if kind == "FORMAL_ORGANIC_ARM_PRELAUNCH" else {
        "FORMAL_INITIAL_POST_LOCK": 0,
        "FORMAL_OUTER_PRELAUNCH": 1,
    }.get(kind)
    if sequence is None:
        raise FormalCampaignError(f"unknown formal resource observation {kind!r}")
    return {
        "authority_id": authority_id,
        "disk_path": str(Path(str(context["campaign_dir"])).absolute()),
        "kind": kind,
        "ordinal": ordinal,
        "scope_id": scope_id,
        "sequence": sequence,
        "slot": slot,
        "target": target,
    }


def acquire_formal_locks() -> dict[str, int]:
    """Acquire the exact three lock files nonblocking, preserving open FDs."""

    held: dict[str, int] = {}
    try:
        for raw in closeout_state.LOCK_PATHS:
            path = Path(raw)
            if path.exists() and path.is_symlink():
                raise FormalCampaignError(f"formal lock is symlinked: {path}")
            descriptor = os.open(
                path,
                os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
            )
            opened = os.fstat(descriptor)
            current = os.stat(path, follow_symlinks=False)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or opened.st_uid != os.getuid()
                or stat.S_IMODE(opened.st_mode) != 0o600
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
            ):
                os.close(descriptor)
                raise FormalCampaignError(f"formal lock identity is unsafe: {path}")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            held[str(path)] = descriptor
    except BaseException as exc:
        for descriptor in held.values():
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise FormalCampaignError("one of the exact three formal locks is unavailable") from exc
    if tuple(held) != tuple(closeout_state.LOCK_PATHS):
        raise FormalCampaignError("formal lock acquisition order drifted")
    return held


def _selected_identities(spec: Mapping[str, object]) -> dict[str, dict[str, object]]:
    argv = spec.get("selected_byte_argv")
    if (
        type(argv) is not list
        or len(argv) < 7
        or argv[:4] != ["/proc/self/fd/3", "-I", "-B", "-c"]
        or argv[5] != "systemd-openfile"
    ):
        raise FormalCampaignError("selected-byte argv is not the fixed three-FD form")
    try:
        parsed = json.loads(argv[6])
    except (TypeError, json.JSONDecodeError) as exc:
        raise FormalCampaignError("selected-byte identity JSON is malformed") from exc
    if type(parsed) is not dict or set(parsed) != {"authority", "loader", "python"}:
        raise FormalCampaignError("selected-byte identity field set drifted")
    result: dict[str, dict[str, object]] = {}
    for name in ("authority", "loader", "python"):
        identity = parsed[name]
        if (
            type(identity) is not dict
            or set(identity) != {"mode", "path", "sha256", "size_bytes"}
            or type(identity["mode"]) is not int
            or type(identity["path"]) is not str
            or not Path(identity["path"]).is_absolute()
            or type(identity["sha256"]) is not str
            or SHA256_RE.fullmatch(identity["sha256"]) is None
            or type(identity["size_bytes"]) is not int
            or identity["size_bytes"] <= 0
        ):
            raise FormalCampaignError(f"selected-byte {name} identity is malformed")
        result[name] = dict(identity)
    return result


def build_selected_systemd_argv(
    *,
    systemd_run_path: str,
    spec: Mapping[str, object],
) -> list[str]:
    """Build the exact systemd-run argv around an authority-validated spec."""

    if type(systemd_run_path) is not str or not Path(systemd_run_path).is_absolute():
        raise FormalCampaignError("pinned systemd-run path is malformed")
    identities = _selected_identities(spec)
    contract = spec["resource_contract"]
    if type(contract) is not dict or contract != launch_validator.OUTER_RESOURCE_CONTRACT:
        raise FormalCampaignError("selected unit resource contract drifted")
    unit_name = spec["unit_name"]
    working_directory = spec["working_directory"]
    selected = spec["selected_byte_argv"]
    if (
        type(unit_name) is not str
        or closeout_state.UNIT_RE.fullmatch(unit_name) is None
        or type(working_directory) is not str
        or not Path(working_directory).is_absolute()
    ):
        raise FormalCampaignError("selected unit name/working directory is malformed")
    return [
        systemd_run_path,
        "--user",
        "--quiet",
        "--no-block",
        "--service-type=exec",
        f"--unit={unit_name.removesuffix('.service')}",
        f"--working-directory={working_directory}",
        f"--property=MemoryHigh={contract['memory_high_bytes']}",
        f"--property=MemoryMax={contract['memory_max_bytes']}",
        f"--property=MemorySwapMax={contract['memory_swap_max_bytes']}",
        f"--property=CollectMode={contract['collect_mode']}",
        f"--property=OOMPolicy={contract['oom_policy']}",
        f"--property=KillMode={contract['kill_mode']}",
        "--property=SendSIGKILL=yes",
        f"--property=RuntimeMaxSec={contract['runtime_max_sec']}",
        f"--property=OpenFile={identities['python']['path']}:ab16-python:read-only",
        f"--property=OpenFile={identities['loader']['path']}:ab16-loader:read-only",
        f"--property=OpenFile={identities['authority']['path']}:ab16-authority:read-only",
        "--",
        *selected,
    ]


def _parse_show(raw: bytes, fields: Sequence[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in raw.decode("utf-8", "strict").splitlines():
        key, separator, value = line.partition("=")
        if not separator or key in result:
            raise FormalCampaignError(f"{label} systemctl output is malformed")
        result[key] = value
    if set(result) != set(fields):
        raise FormalCampaignError(f"{label} systemctl field set drifted")
    return result


def show_full(host: closeout_helper.PinnedHost, unit_name: str) -> dict[str, str]:
    completed = host.run(
        [
            "--user",
            "show",
            unit_name,
            *(f"--property={field}" for field in FULL_SHOW_FIELDS),
        ]
    )
    return _parse_show(completed.stdout, FULL_SHOW_FIELDS, "formal unit")


def _duration_seconds(value: str) -> int:
    scales = (("min", 60.0), ("us", 0.000001), ("ms", 0.001), ("h", 3600.0), ("s", 1.0))
    for suffix, scale in scales:
        if value.endswith(suffix):
            return int(float(value[: -len(suffix)]) * scale)
    if value.isdigit():
        return int(value) // 1_000_000
    raise FormalCampaignError("systemd duration is malformed")


def wait_unit_live(
    host: closeout_helper.PinnedHost,
    *,
    unit_name: str,
    resource_contract: Mapping[str, object],
    timeout_seconds: float,
    on_frozen: Callable[[Mapping[str, object]], None] | None = None,
) -> tuple[dict[str, str], dict[str, object], dict[str, object]]:
    """Verify systemd properties and actual cgroup files for one selected unit."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        shown = show_full(host, unit_name)
        control_group = shown["ControlGroup"]
        if shown["LoadState"] == "loaded" and shown["ActiveState"] == "active" and control_group:
            frozen = host.freeze_identity(
                source="outer",
                slot="formal",
                unit_name=unit_name,
                shown={
                    field: shown[field]
                    for field in closeout_helper.CHILD_FIELDS
                },
                ownership_classification="OUTER_LIVE_VERIFIED",
            )
            frozen = closeout_state.validate_frozen_identity(
                frozen,
                expected_source="outer",
                expected_slot="formal",
            )
            if frozen["identity_complete"] is not True:
                raise FormalCampaignError(
                    "selected live unit identity is incomplete"
                )
            if on_frozen is not None:
                on_frozen(frozen)
            root = host.cgroup_path(control_group)
            campaign = host.boundary.context["campaign_module"]
            actual = {
                field: int(
                    campaign._read_pseudofile_same_fd(  # noqa: SLF001
                        root / path,
                        label=f"{unit_name} {path}",
                        limit=128,
                    )
                    .decode("ascii", "strict")
                    .strip()
                )
                for field, path in (
                    ("memory_high_bytes", "memory.high"),
                    ("memory_max_bytes", "memory.max"),
                    ("memory_swap_max_bytes", "memory.swap.max"),
                )
            }
            expected_properties = {
                "collect_mode": shown["CollectMode"],
                "kill_mode": shown["KillMode"],
                "memory_high_bytes": int(shown["MemoryHigh"]),
                "memory_max_bytes": int(shown["MemoryMax"]),
                "memory_swap_max_bytes": int(shown["MemorySwapMax"]),
                "oom_policy": shown["OOMPolicy"],
                "runtime_max_sec": _duration_seconds(shown["RuntimeMaxUSec"]),
                "send_sigkill": shown["SendSIGKILL"] == "yes",
            }
            if expected_properties != dict(resource_contract) or actual != {
                name: resource_contract[name]
                for name in (
                    "memory_high_bytes",
                    "memory_max_bytes",
                    "memory_swap_max_bytes",
                )
            }:
                raise FormalCampaignError("selected unit systemd/cgroup resource contract drifted")
            return shown, actual, frozen
        time.sleep(POLL_SECONDS)
    raise FormalCampaignError(f"selected unit did not become live: {unit_name}")


def wait_unit_terminal(
    host: closeout_helper.PinnedHost,
    *,
    unit_name: str,
    timeout_seconds: float,
) -> tuple[dict[str, str], dict[str, str], int]:
    deadline = time.monotonic() + timeout_seconds
    first: dict[str, str] | None = None
    first_ns = 0
    while time.monotonic() <= deadline:
        shown = show_full(host, unit_name)
        terminal = {field: shown[field] for field in TERMINAL_FIELDS}
        if (
            shown["LoadState"] == "loaded"
            and shown["ActiveState"] == "inactive"
            and shown["SubState"] == "dead"
        ):
            now_ns = time.monotonic_ns()
            if first is None or terminal != first:
                first = terminal
                first_ns = now_ns
            elif now_ns - first_ns >= 1_000_000_000:
                return first, terminal, now_ns - first_ns
        time.sleep(POLL_SECONDS)
    raise FormalCampaignError("outer terminal metadata did not remain stable for one second")


def _empty_frozen(source: str, slot: str, unit_name: str = "") -> dict[str, object]:
    return {
        "control_group": "",
        "identity_complete": True,
        "invocation_id": "",
        "ownership_classification": "NOT_STARTED",
        "processes": [],
        "slot": slot,
        "source": source,
        "unit_name": unit_name,
    }


def initial_ledger(outer_identity: Mapping[str, object]) -> dict[str, object]:
    ledger = {
        "child_audit_identity": {},
        "children": [
            _empty_frozen(source, slot)
            for source, slot in closeout_state.EXPECTED_CHILD_ORDER
        ],
        "outer": dict(outer_identity),
    }
    return closeout_state.validate_frozen_ledger(ledger)


def _open_selected(identity: Mapping[str, object], label: str) -> int:
    """Open one selected program without weakening the literal's own replay."""

    descriptor = os.open(
        str(identity["path"]),
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        before = os.fstat(descriptor)
        current = os.stat(str(identity["path"]), follow_symlinks=False)
        signature = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        digest = hashlib.sha256()
        offset = 0
        while offset < before.st_size:
            block = os.pread(
                descriptor,
                min(1 << 20, before.st_size - offset),
                offset,
            )
            if not block:
                raise FormalCampaignError(f"selected {label} ended early")
            digest.update(block)
            offset += len(block)
        after = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != identity["mode"]
            or before.st_size != identity["size_bytes"]
            or digest.hexdigest() != identity["sha256"]
            or signature
            != (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_nlink,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            or (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)
        ):
            raise FormalCampaignError(f"selected {label} FD/path identity drifted")
        return descriptor
    except BaseException as exc:
        try:
            os.close(descriptor)
        except BaseException as cleanup_exc:
            exc.add_note(
                f"selected {label} cleanup close failed: "
                f"{type(cleanup_exc).__name__}: {cleanup_exc}"
            )
        raise


def run_selected_direct_result(
    *,
    context: Mapping[str, object],
    role: str,
    role_argv: Sequence[str],
    timeout_seconds: float,
    cancel_requested: Callable[[], bool] | None = None,
) -> SelectedDirectResult:
    """Run one fresh selected role through fixed FDs 3/4/5.

    The embedded selected-byte literal remains the first executing trust
    primitive.  This function only opens the already-authorized bytes and
    arranges their fixed descriptors.
    """

    outer_spec = context["outer_spec"]
    identities = _selected_identities(outer_spec)
    selected = outer_spec["selected_byte_argv"]
    command = [
        "/proc/self/fd/3",
        "-I",
        "-B",
        "-c",
        selected[4],
        "direct",
        selected[6],
        "--campaign-dir",
        str(context["campaign_dir"]),
        "--role",
        role,
        "--",
        *role_argv,
    ]
    opened: dict[int, int] = {}
    pipes: set[int] = set()
    high: dict[int, int] = {}
    owned_descriptors: set[int] = set()
    selector = selectors.DefaultSelector()
    pid: int | None = None
    child_reaped = False
    failure: BaseException | None = None

    def own_descriptor(descriptor: int) -> int:
        owned_descriptors.add(descriptor)
        return descriptor

    def close_owned(descriptor: int) -> BaseException | None:
        if descriptor not in owned_descriptors:
            return None
        # Relinquish ownership before close: a failing close may already have
        # released the numeric descriptor, so retrying could close a reused FD.
        owned_descriptors.remove(descriptor)
        pipes.discard(descriptor)
        try:
            os.close(descriptor)
        except BaseException as exc:
            return exc
        return None

    def close_many(descriptors: Sequence[int]) -> BaseException | None:
        first_error: BaseException | None = None
        for descriptor in descriptors:
            error = close_owned(descriptor)
            if first_error is None and error is not None:
                first_error = error
        return first_error

    try:
        for target, identity, label in (
            (3, identities["python"], "Python"),
            (4, identities["loader"], "loader"),
            (5, identities["authority"], "authority"),
        ):
            opened[target] = own_descriptor(_open_selected(identity, label))
        stdout_read, stdout_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
        pipes.update((own_descriptor(stdout_read), own_descriptor(stdout_write)))
        stderr_read, stderr_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
        pipes.update((own_descriptor(stderr_read), own_descriptor(stderr_write)))
        for target, source in opened.items():
            high[target] = own_descriptor(
                fcntl.fcntl(source, fcntl.F_DUPFD_CLOEXEC, 20)
            )
        actions: list[tuple[Any, ...]] = [
            *((
                os.POSIX_SPAWN_DUP2,
                high[target],
                target,
            ) for target in (3, 4, 5)),
            (os.POSIX_SPAWN_DUP2, stdout_write, 1),
            (os.POSIX_SPAWN_DUP2, stderr_write, 2),
            (os.POSIX_SPAWN_CLOSE, stdout_read),
            (os.POSIX_SPAWN_CLOSE, stderr_read),
        ]
        pid = os.posix_spawn(
            "/proc/self/fd/3",
            command,
            {},
            file_actions=actions,
        )
        high_close_error = close_many(tuple(high.values()))
        if high_close_error is not None:
            raise high_close_error
        stdout_close_error = close_owned(stdout_write)
        stderr_close_error = close_owned(stderr_write)
        if stdout_close_error is not None:
            raise stdout_close_error
        if stderr_close_error is not None:
            raise stderr_close_error
        selector.register(stdout_read, selectors.EVENT_READ, "stdout")
        selector.register(stderr_read, selectors.EVENT_READ, "stderr")
        output = {"stdout": bytearray(), "stderr": bytearray()}
        deadline = time.monotonic() + timeout_seconds
        status: int | None = None
        while selector.get_map() or status is None:
            if cancel_requested is not None and cancel_requested():
                raise IrreversibleFormalFailure(
                    f"selected {role} was cancelled by its owning coordinator"
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise IrreversibleFormalFailure(
                    f"selected {role} timed out after launch"
                )
            for key, _event in selector.select(min(0.25, remaining)):
                block = os.read(key.fd, 64 * 1024)
                if block:
                    output[str(key.data)].extend(block)
                    if len(output[str(key.data)]) > MAX_SELECTED_OUTPUT:
                        raise IrreversibleFormalFailure(
                            f"selected {role} output exceeded its limit"
                        )
                else:
                    selector.unregister(key.fd)
                    close_error = close_owned(key.fd)
                    if close_error is not None:
                        raise close_error
            if status is None:
                observed, raw_status = os.waitpid(pid, os.WNOHANG)
                if observed == pid:
                    status = raw_status
                    child_reaped = True
        returncode = os.waitstatus_to_exitcode(status)
        stdout = bytes(output["stdout"])
        stderr = bytes(output["stderr"])
        return SelectedDirectResult(
            returncode=returncode,
            stderr=stderr,
            stdout=stdout,
        )
    except BaseException as exc:
        failure = exc
        if pid is not None and not child_reaped:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except BaseException:
                pass
            while not child_reaped:
                try:
                    observed, _status = os.waitpid(pid, 0)
                    child_reaped = observed == pid
                    if not child_reaped:
                        exc.add_note(
                            f"selected {role} cleanup wait returned pid "
                            f"{observed}, expected {pid}"
                        )
                        break
                except InterruptedError:
                    continue
                except ChildProcessError:
                    child_reaped = True
                except BaseException as cleanup_exc:
                    exc.add_note(
                        f"selected {role} cleanup wait failed: "
                        f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                    )
                    break
        raise
    finally:
        cleanup_error: BaseException | None = None
        try:
            selector.close()
        except BaseException as exc:
            cleanup_error = exc
        descriptor_cleanup_error = close_many(tuple(owned_descriptors))
        if cleanup_error is None and descriptor_cleanup_error is not None:
            cleanup_error = descriptor_cleanup_error
        if failure is None and cleanup_error is not None:
            raise cleanup_error


def run_selected_direct(
    *,
    context: Mapping[str, object],
    role: str,
    role_argv: Sequence[str],
    timeout_seconds: float,
) -> tuple[bytes, bytes]:
    """Run one selected role and require the historical strict rc=0 contract."""

    result = run_selected_direct_result(
        context=context,
        role=role,
        role_argv=role_argv,
        timeout_seconds=timeout_seconds,
    )
    if result.returncode != 0 or result.stderr:
        raise IrreversibleFormalFailure(
            f"selected {role} failed: exit={result.returncode}, "
            f"stderr={result.stderr!r}"
        )
    return result.stdout, result.stderr


def _guardian_unit_identity(
    host: closeout_helper.PinnedHost,
    *,
    unit_name: str,
    shown: Mapping[str, str],
) -> dict[str, object]:
    control_group = shown["ControlGroup"]
    processes = host.cgroup_processes(control_group)
    main_pid = int(shown["MainPID"]) if shown["MainPID"].isdigit() else 0
    record = {
        "control_group": control_group,
        "invocation_id": shown["InvocationID"],
        "processes": processes,
        "unit_name": unit_name,
    }
    if (
        shown["LoadState"] != "loaded"
        or shown["ActiveState"] != "active"
        or closeout_state.INVOCATION_RE.fullmatch(record["invocation_id"]) is None
        or not any(item["pid"] == main_pid for item in processes)
    ):
        raise FormalCampaignError("guardian live identity is incomplete")
    return launch_validator.validate_guardian_unit_identity(record)


def _launch_selected_unit(
    host: closeout_helper.PinnedHost,
    *,
    context: Mapping[str, object],
    spec: Mapping[str, object],
    resource_admission_receipt: Mapping[str, object],
    launch_owner_check: Callable[[], None],
) -> dict[str, object]:
    systemd_run = host.boundary.root["authority_tools"]["systemd_run"]
    command = build_selected_systemd_argv(
        systemd_run_path=str(systemd_run["path"]),
        spec=spec,
    )
    completed = host.run(
        command[1:],
        role="systemd_run",
        cwd=Path(str(context["snapshot_root"])),
        env={
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "TZ": "UTC",
        },
        launch_resource_admission=resource_admission_receipt,
        launch_owner_check=launch_owner_check,
    )
    final_resource_admission = host.take_final_launch_resource_admission()
    return {
        "argv": command,
        "resource_admission": final_resource_admission,
        "returncode": completed.returncode,
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
    }


def _pidfd_open(identity: Mapping[str, object]) -> int | None:
    checked = launch_validator.validate_process_identity(
        identity,
        "guardian pidfd process",
    )
    opener = getattr(os, "pidfd_open", None)
    if not callable(opener):
        return None
    descriptor = opener(checked["pid"], 0)
    if guardian.read_process_starttime(checked["pid"]) != checked["starttime"]:
        os.close(descriptor)
        raise FormalCampaignError("guardian PID identity changed across pidfd_open")
    return descriptor


def guardian_is_alive(session: GuardianSession) -> bool:
    process = session.unit_identity["processes"][0]
    try:
        if guardian.read_process_starttime(process["pid"]) != process["starttime"]:
            return False
    except (FileNotFoundError, ProcessLookupError):
        return False
    if session.process_pidfd is not None:
        poller = selectors.DefaultSelector()
        try:
            poller.register(session.process_pidfd, selectors.EVENT_READ)
            if poller.select(0):
                return False
        finally:
            poller.close()
    return True


def _wait_uncertain_unit_resolution(
    host: closeout_helper.PinnedHost,
    unit_name: str,
    *,
    timeout_seconds: float,
    monotonic: Clock = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, str]:
    """Observe one exact prelaunch-absent unit across its launch uncertainty window."""

    deadline = monotonic() + timeout_seconds
    while monotonic() <= deadline:
        shown = host.show(unit_name)
        if shown != closeout_helper.ABSENT:
            return shown
        sleeper(POLL_SECONDS)
    return dict(closeout_helper.ABSENT)


def start_guardian(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    admission: Mapping[str, object],
    admission_identity: Mapping[str, object],
    resource_admission_receipt: Mapping[str, object],
    host: closeout_helper.PinnedHost,
    store: closeout_helper.ReceiptStore,
) -> GuardianSession:
    """Launch the authority-closed guardian and transfer the same lock FDs."""

    spec = context["guardian_spec"]
    unit_name = str(spec["unit_name"])
    if host.show(unit_name) != closeout_helper.ABSENT:
        raise FormalCampaignError(
            "selected guardian unit was not absent before its sole launch"
        )
    listener = guardian.GuardianControlListener(
        context["guardian_control_socket_path"],
        retirement_path=context["guardian_control_retired_socket_path"],
    )
    connection: Any = None
    frozen_identity: dict[str, object] | None = None
    observed_unit_identity: dict[str, object] | None = None
    cleanup_errors: list[dict[str, str]] = []

    def remember_guardian(
        frozen: Mapping[str, object],
    ) -> None:
        nonlocal observed_unit_identity
        if observed_unit_identity is not None:
            raise IrreversibleFormalFailure(
                "guardian live identity was frozen twice"
            )
        observed_unit_identity = {
            "control_group": frozen["control_group"],
            "invocation_id": frozen["invocation_id"],
            "processes": frozen["processes"],
            "unit_name": frozen["unit_name"],
        }

    def check_launch_owner() -> None:
        _validate_live_launch_owner(
            admission,
            label="formal launch admission at guardian launch",
        )

    try:
        _launch_selected_unit(
            host,
            context=context,
            spec=spec,
            resource_admission_receipt=resource_admission_receipt,
            launch_owner_check=check_launch_owner,
        )
        shown, _cgroup, _frozen = wait_unit_live(
            host,
            unit_name=unit_name,
            resource_contract=spec["resource_contract"],
            timeout_seconds=GUARDIAN_WAIT_SECONDS,
            on_frozen=remember_guardian,
        )
        unit_identity = _guardian_unit_identity(
            host,
            unit_name=unit_name,
            shown=shown,
        )
        if (
            observed_unit_identity is None
            or observed_unit_identity != unit_identity
        ):
            raise IrreversibleFormalFailure(
                "guardian live identity drifted after its first freeze"
            )
        guardian_process = unit_identity["processes"][0]
        listener.socket.settimeout(GUARDIAN_WAIT_SECONDS)
        connection = listener.accept_once(
            expected_peer_process=guardian_process,
            process_starttime_reader=guardian.read_process_starttime,
        )
        connection.settimeout(None)
        handoff = guardian.build_lock_handoff_record(
            admission=admission,
            admission_identity=admission_identity,
            expected_context=context,
            guardian_process_identity=guardian_process,
            guardian_unit_identity=unit_identity,
            control_socket_identity=listener.identity,
            lock_identities=host.lock_evidence(),
            supervisor_process_identity=_process_identity(os.getpid()),
        )
        handoff_identity = guardian.send_frame(
            connection,
            handoff,
            file_descriptors=tuple(
                host.held_locks[path]
                for path in closeout_state.LOCK_PATHS
            ),
        )
        ready, ready_identity = _wait_record(
            context["guardian_ready_path"],
            expected_identity=None,
            label="outer guardian ready",
            timeout_seconds=GUARDIAN_WAIT_SECONDS,
        )
        checked_ready = launch_validator.validate_guardian_ready(
            ready,
            admission=admission,
            admission_identity=admission_identity,
            expected_context=context,
        )
        if (
            checked_ready["guardian_unit_identity"] != unit_identity
            or checked_ready["handoff_message_identity"] != handoff_identity
            or checked_ready["lock_identities"] != host.lock_evidence()
        ):
            raise FormalCampaignError("guardian ready/handoff identity join drifted")
        listener.close_once()
        listener.remove_path_once()
        return GuardianSession(
            unit_name=unit_name,
            unit_identity=unit_identity,
            listener=listener,
            connection=connection,
            ready=checked_ready,
            ready_identity=ready_identity,
            last_message_identity=handoff_identity,
            process_pidfd=_pidfd_open(guardian_process),
            listener_closed=True,
        )
    except BaseException as exc:
        if connection is not None:
            try:
                connection.close()
            except BaseException as close_error:
                cleanup_errors.append(
                    _failure(
                        "GUARDIAN_CONTROL_CLOSE_FAILED_OR_UNCERTAIN",
                        close_error,
                    )
                )
        if not listener.closed:
            try:
                listener.close_once()
            except BaseException as close_error:
                cleanup_errors.append(
                    _failure(
                        "GUARDIAN_LISTENER_CLOSE_FAILED_OR_UNCERTAIN",
                        close_error,
                    )
                )
        if listener.bound and not listener.remove_attempted:
            try:
                listener.remove_path_once()
            except BaseException as remove_error:
                cleanup_errors.append(
                    _failure(
                        "GUARDIAN_LISTENER_REMOVE_FAILED_OR_UNCERTAIN",
                        remove_error,
                    )
                )
        if listener.parent_owned:
            try:
                listener.abandon_parent_once()
            except BaseException as abandon_error:
                cleanup_errors.append(
                    _failure(
                        "GUARDIAN_LISTENER_PARENT_ABANDON_FAILED_OR_UNCERTAIN",
                        abandon_error,
                    )
                )
        containment_cleared = False
        try:
            shown = _wait_uncertain_unit_resolution(
                host,
                unit_name,
                timeout_seconds=GUARDIAN_WAIT_SECONDS,
            )
            if shown == closeout_helper.ABSENT:
                containment_cleared = True
            else:
                unit_identity = _guardian_unit_identity(
                    host,
                    unit_name=unit_name,
                    shown=shown,
                )
                if (
                    observed_unit_identity is not None
                    and unit_identity != observed_unit_identity
                ):
                    cleanup_errors.append(
                        _failure(
                            "GUARDIAN_LAUNCH_CONTAINMENT_IDENTITY_GAP",
                            "same-name guardian no longer matches its first frozen identity",
                        )
                    )
                    raise IrreversibleFormalFailure(
                        "guardian identity changed before launch-failure containment"
                    )
                frozen_identity = {
                    "control_group": unit_identity["control_group"],
                    "identity_complete": True,
                    "invocation_id": unit_identity["invocation_id"],
                    "ownership_classification": "PRELAUNCH_OWNED_ACTIVE",
                    "processes": unit_identity["processes"],
                    "slot": "guardian",
                    "source": "outer-guardian",
                    "unit_name": unit_identity["unit_name"],
                }
                cleanup_errors.extend(host.stop_reset_once(unit_name))
                observed = host.wait_state(
                    unit_name,
                    str(unit_identity["control_group"]),
                    unit_identity["processes"],
                    referenced=False,
                    timeout=GUARDIAN_WAIT_SECONDS,
                )
                containment_cleared = (
                    not cleanup_errors
                    and observed["systemctl"] == closeout_helper.ABSENT
                    and observed["cgroup_absent"] is True
                    and observed["processes_absent"] is True
                )
        except BaseException as cleanup_error:
            cleanup_errors.append(
                _failure(
                    "GUARDIAN_LAUNCH_CONTAINMENT_FAILED_OR_UNCERTAIN",
                    cleanup_error,
                )
            )
        raise GuardianLaunchFailure(
            exc,
            containment_cleared=containment_cleared,
            cleanup_errors=cleanup_errors,
            frozen_identity=frozen_identity,
        ) from exc


def load_formal_admission(
    campaign_dir: Path | str,
) -> tuple[
    authority.FormalRuntimeBoundary,
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    boundary = authority.replay_formal_runtime_boundary(campaign_dir)
    context = launch_validator.replay_formal_launch_context(
        authority,
        boundary.campaign,
    )
    admission, admission_identity = _read_record(
        context["formal_admission_path"],
        expected_identity=None,
        label="formal launch admission",
    )
    checked = launch_validator.validate_admission(
        admission,
        expected_context=context,
    )
    _validate_live_launch_owner(checked, label="formal launch admission")
    return boundary, context, checked, admission_identity


def wait_and_validate_selection(
    *,
    context: Mapping[str, object],
    admission: Mapping[str, object],
    admission_identity: Mapping[str, object],
    guardian_session: GuardianSession,
    marker: Mapping[str, object],
    marker_identity: Mapping[str, object],
    checkpoint: Callable[[], None] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    selection, selection_identity = _wait_record(
        context["formal_selection_path"],
        expected_identity=None,
        label="formal launch selection",
        timeout_seconds=RECORD_WAIT_SECONDS,
        checkpoint=checkpoint,
    )
    checked = launch_validator.validate_selection(
        selection,
        admission=admission,
        admission_identity=admission_identity,
        guardian_ready=guardian_session.ready,
        guardian_ready_identity=guardian_session.ready_identity,
        attempt_consumption=marker,
        attempt_consumption_identity=marker_identity,
        expected_context=context,
    )
    _validate_live_launch_owner(checked, label="formal launch selection")
    return checked, selection_identity


def activate_guardian(
    session: GuardianSession,
    *,
    context: Mapping[str, object],
    selection_identity: Mapping[str, object],
) -> dict[str, object]:
    if session.activation_sent:
        raise IrreversibleFormalFailure("guardian activation cannot be sent twice")
    record = guardian.build_activation_record(
        expected_context=context,
        formal_selection_identity=selection_identity,
        guardian_ready_identity=session.ready_identity,
    )
    session.activation_sent = True
    identity = guardian.send_frame(session.connection, record)
    session.activation_returned = True
    session.last_message_identity = identity
    return identity


def send_ledger_update(
    session: GuardianSession,
    *,
    context: Mapping[str, object],
    selection_identity: Mapping[str, object],
    ledger: Mapping[str, object],
    phase: str,
    sequence: int,
) -> dict[str, object]:
    if not session.activation_sent or session.terminal_sent:
        raise IrreversibleFormalFailure("guardian ledger update crossed its activation/terminal boundary")
    record = guardian.build_ledger_update_record(
        expected_context=context,
        formal_selection_identity=selection_identity,
        ledger=ledger,
        phase=phase,
        previous_message_identity=session.last_message_identity,
        sequence=sequence,
    )
    identity = guardian.send_frame(session.connection, record)
    session.last_message_identity = identity
    return identity


def send_guardian_terminal(
    session: GuardianSession,
    *,
    context: Mapping[str, object],
    selection_identity: Mapping[str, object],
    ledger: Mapping[str, object],
    command: str,
    reason: str,
) -> dict[str, object]:
    if not session.activation_sent or session.terminal_sent:
        raise IrreversibleFormalFailure("guardian terminal command cannot be repeated")
    record = guardian.build_terminal_record(
        expected_context=context,
        command=command,
        formal_selection_identity=selection_identity,
        ledger=ledger,
        previous_message_identity=session.last_message_identity,
        reason=reason,
    )
    session.terminal_sent = True
    identity = guardian.send_frame(session.connection, record)
    session.last_message_identity = identity
    return identity


def send_preselection_cancel(
    session: GuardianSession,
    *,
    context: Mapping[str, object],
    admission_identity: Mapping[str, object],
    lock_identities: object,
    reason: str,
) -> dict[str, object]:
    """Cancel one guardian that never received a formal selection."""

    if session.activation_sent or session.terminal_sent:
        raise IrreversibleFormalFailure(
            "guardian preselection cancel crossed activation"
        )
    record = guardian.build_preselection_cancel_record(
        expected_context=context,
        formal_admission_identity=admission_identity,
        guardian_ready_identity=session.ready_identity,
        lock_identities=lock_identities,
        reason=reason,
    )
    session.terminal_sent = True
    identity = guardian.send_frame(session.connection, record)
    session.last_message_identity = identity
    frame = guardian.receive_frame(session.connection, expected_fd_count=0)
    ack = frame.record
    if (
        type(ack) is not dict
        or ack.get("schema_version") != guardian.GUARDIAN_PRESELECTION_ACK_SCHEMA
        or ack.get("status") != "PRESELECTION_CANCELLED"
        or ack.get("outcome") != "PERMANENT_INCOMPLETE"
        or ack.get("formal_selection_absent") is not True
        or ack.get("errors") != []
    ):
        raise IrreversibleFormalFailure(
            "guardian preselection cancellation did not close cleanly"
        )
    session.close_received = True
    return {"identity": frame.identity, "record": dict(ack)}


def _close_guardian_connection(session: GuardianSession) -> None:
    if session.connection_close_attempted:
        raise IrreversibleFormalFailure(
            "guardian control connection cannot be closed twice"
        )
    session.connection_close_attempted = True
    try:
        session.connection.close()
    except BaseException as exc:
        session.connection_close_error = _failure(
            "GUARDIAN_CONTROL_CLOSE_FAILED_OR_UNCERTAIN",
            exc,
        )
        raise
    session.connection_close_returned = True
    session.connection_closed = True


def _close_pidfd(session: GuardianSession) -> None:
    if session.process_pidfd is not None:
        os.close(session.process_pidfd)
        session.process_pidfd = None


def _wait_guardian_absence(
    host: closeout_helper.PinnedHost,
    session: GuardianSession,
    *,
    timeout_seconds: float,
) -> dict[str, object]:
    identity = session.unit_identity
    observed = host.wait_state(
        session.unit_name,
        str(identity["control_group"]),
        identity["processes"],
        referenced=False,
        timeout=timeout_seconds,
    )
    if (
        observed["systemctl"] != closeout_helper.ABSENT
        or observed["cgroup_absent"] is not True
        or observed["processes_absent"] is not True
    ):
        raise IrreversibleFormalFailure(
            "guardian unit/cgroup/PID absence was not established"
        )
    _close_pidfd(session)
    return {
        "cgroup_absent": True,
        "pid_absent": True,
        "systemctl": observed["systemctl"],
        "unit_absent": True,
    }


def _outer_inactive_identity(unit_name: str) -> dict[str, object]:
    return _empty_frozen("outer", "formal", unit_name)


def _replace_ledger_identity(
    ledger: Mapping[str, object],
    *,
    source: str,
    slot: str,
    identity: Mapping[str, object],
) -> dict[str, object]:
    checked = closeout_state.validate_frozen_ledger(ledger)
    frozen = closeout_state.validate_frozen_identity(
        identity,
        expected_source=source,
        expected_slot=slot,
    )
    if source == "outer":
        if slot != "formal":
            raise FormalCampaignError("outer ledger slot drifted")
        checked["outer"] = frozen
    else:
        expected = list(closeout_state.EXPECTED_CHILD_ORDER)
        try:
            index = expected.index((source, slot))
        except ValueError as exc:
            raise FormalCampaignError(
                f"child ledger slot escaped fixed order: {source}/{slot}"
            ) from exc
        checked["children"][index] = frozen
    return closeout_state.validate_frozen_ledger(checked)


def _send_next_ledger_phase(
    *,
    context: Mapping[str, object],
    state: SupervisorState,
    phase: str,
) -> None:
    if (
        state.guardian is None
        or state.selection_identity is None
        or state.ledger is None
    ):
        raise FormalCampaignError("guardian ledger phase lacks selected state")
    sequence = state.ledger_sequence + 1
    if sequence > len(LEDGER_PHASES) or LEDGER_PHASES[sequence - 1] != phase:
        raise IrreversibleFormalFailure(
            f"guardian ledger phase/order drifted: {sequence}/{phase}"
        )
    state.ledger_sequence = sequence
    send_ledger_update(
        state.guardian,
        context=context,
        selection_identity=state.selection_identity,
        ledger=state.ledger,
        phase=phase,
        sequence=sequence,
    )


def _mirror_gate1_prelaunch(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
) -> None:
    """Mirror all four selected Gate1 names before releasing the outer barrier."""

    if (
        state.selection is None
        or state.ledger is None
        or state.attempt.reference is None
    ):
        raise FormalCampaignError("Gate1 prelaunch mirror lacks selected RefUnit state")
    targets = closeout_helper.build_child_ledger(
        boundary,
        store,
        host,
        state.attempt.reference,
        state.selection,
        expected_allowed_same_uid_processes=_formal_resource_allowlist(state),
    )
    gate1_targets = [target for target in targets if target.source == "gate1"]
    if [target.slot for target in gate1_targets] != list(GATE1_SLOTS):
        raise IrreversibleFormalFailure("Gate1 prelaunch mirror order drifted")
    for target in gate1_targets:
        if not target.unit_name or host.show(target.unit_name) != closeout_helper.ABSENT:
            raise IrreversibleFormalFailure(
                f"Gate1 prelaunch mirror is not absent: {target.slot}"
            )
        state.ledger = _replace_ledger_identity(
            state.ledger,
            source="gate1",
            slot=target.slot,
            identity=_empty_frozen(
                "gate1",
                target.slot,
                target.unit_name,
            ),
        )
    _send_next_ledger_phase(
        context=context,
        state=state,
        phase="gate1:prelaunch",
    )


def _mirror_arm_prelaunch(
    *,
    context: Mapping[str, object],
    state: SupervisorState,
    host: closeout_helper.PinnedHost,
    slot: str,
    unit_name: str,
) -> None:
    """Mirror one exact arm name before its canonical launch permission exists."""

    if slot not in ARM_SEQUENCE or closeout_state.UNIT_RE.fullmatch(unit_name) is None:
        raise IrreversibleFormalFailure("arm prelaunch mirror identity is malformed")
    if state.ledger is None or host.show(unit_name) != closeout_helper.ABSENT:
        raise IrreversibleFormalFailure(
            f"{slot} arm prelaunch mirror is not stably absent"
        )
    state.ledger = _replace_ledger_identity(
        state.ledger,
        source="arm",
        slot=slot,
        identity=_empty_frozen("arm", slot, unit_name),
    )
    _send_next_ledger_phase(
        context=context,
        state=state,
        phase=f"arm:{slot}:prelaunch",
    )


def _guard_running(
    state: SupervisorState,
    host: closeout_helper.PinnedHost,
    latch: closeout_helper.TerminationLatch,
) -> None:
    if latch.records:
        raise IrreversibleFormalFailure(
            f"termination signal latched: {latch.records[0]}"
        )
    session = state.guardian
    if session is None or not guardian_is_alive(session):
        raise IrreversibleFormalFailure(
            "guardian died before the normal release boundary"
        )
    if state.outer_identity is not None:
        shown = show_full(
            host,
            str(state.outer_identity["unit_name"]),
        )
        if shown["LoadState"] != "loaded" or shown["ActiveState"] not in {
            "active",
            "activating",
        }:
            raise IrreversibleFormalFailure(
                "outer controller terminated before the expected campaign milestone"
            )


def _normal_closeout_checkpoint(
    state: SupervisorState,
    latch: closeout_helper.TerminationLatch,
    *,
    phase: str,
) -> None:
    """Forbid a normal-closeout side effect after signal or guardian loss."""

    if type(phase) is not str or not phase:
        raise FormalCampaignError("normal closeout checkpoint phase is malformed")
    if latch.records:
        raise IrreversibleFormalFailure(
            f"termination signal latched before {phase}: {latch.records[0]}"
        )
    if state.guardian is None or not guardian_is_alive(state.guardian):
        raise IrreversibleFormalFailure(
            f"guardian died before {phase}"
        )


def _post_release_signal_checkpoint(
    latch: closeout_helper.TerminationLatch,
    *,
    phase: str,
) -> None:
    """Keep a late signal from preserving success after runtime isolation."""

    if type(phase) is not str or not phase:
        raise FormalCampaignError("post-release checkpoint phase is malformed")
    if latch.records:
        raise IrreversibleFormalFailure(
            f"termination signal latched before {phase}: {latch.records[0]}"
        )


def _supervisor_checkpoint(
    state: SupervisorState,
    host: closeout_helper.PinnedHost,
    latch: closeout_helper.TerminationLatch,
) -> None:
    """Reject latched termination or guardian loss before a new side effect."""

    if state.guardian is None:
        if latch.records:
            raise IrreversibleFormalFailure(
                f"termination signal latched: {latch.records[0]}"
            )
        return
    _guard_running(state, host, latch)


def _child_unit_name(
    boundary: authority.FormalRuntimeBoundary,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    reference: object,
    selection: Mapping[str, object],
    *,
    expected_allowed_same_uid_processes: Sequence[Mapping[str, int]],
    source: str,
    slot: str,
) -> str:
    targets = closeout_helper.build_child_ledger(
        boundary,
        store,
        host,
        reference,
        selection,
        expected_allowed_same_uid_processes=expected_allowed_same_uid_processes,
    )
    matches = [
        target
        for target in targets
        if target.source == source and target.slot == slot
    ]
    if len(matches) != 1 or not matches[0].unit_name:
        raise FormalCampaignError(
            f"{source}/{slot} does not resolve to one selected unit"
        )
    return matches[0].unit_name


def _wait_and_mirror_child(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    latch: closeout_helper.TerminationLatch,
    source: str,
    slot: str,
    deadline: float,
) -> dict[str, object]:
    if (
        state.selection is None
        or state.selection_identity is None
        or state.guardian is None
        or state.ledger is None
        or state.attempt.reference is None
    ):
        raise FormalCampaignError(
            "child mirror lacks selected supervisor prerequisites"
        )
    unit_name = _child_unit_name(
        boundary,
        store,
        host,
        state.attempt.reference,
        state.selection,
        expected_allowed_same_uid_processes=_formal_resource_allowlist(state),
        source=source,
        slot=slot,
    )
    while time.monotonic() <= deadline:
        _guard_running(state, host, latch)
        shown = host.show(unit_name)
        if (
            shown["LoadState"] == "loaded"
            and shown["ActiveState"]
            in {"active", "activating", "deactivating", "failed"}
            and shown["InvocationID"]
            and shown["ControlGroup"]
            and shown["MainPID"].isdigit()
            and int(shown["MainPID"]) > 0
        ):
            frozen = closeout_helper.freeze_selected_child_identity(
                boundary,
                store,
                host,
                state.attempt.reference,
                state.selection,
                expected_allowed_same_uid_processes=_formal_resource_allowlist(
                    state
                ),
                source=source,
                slot=slot,
            )
            if frozen["classification"] != "PRELAUNCH_OWNED_ACTIVE":
                raise IrreversibleFormalFailure(
                    f"{source}/{slot} launch identity was not frozen active"
                )
            state.ledger = _replace_ledger_identity(
                state.ledger,
                source=source,
                slot=slot,
                identity=frozen["frozen_identity"],
            )
            _send_next_ledger_phase(
                context=context,
                phase=f"{source}:{slot}:live",
                state=state,
            )
            return frozen
        time.sleep(POLL_SECONDS)
    raise IrreversibleFormalFailure(
        f"{source}/{slot} did not expose one stable selected launch identity"
    )


def _wait_arm_request(
    *,
    state: SupervisorState,
    host: closeout_helper.PinnedHost,
    latch: closeout_helper.TerminationLatch,
    path: Path | str,
    slot: str,
    deadline: float,
) -> None:
    target = Path(path)
    while time.monotonic() <= deadline:
        _guard_running(state, host, latch)
        try:
            observed = os.lstat(target)
        except FileNotFoundError:
            time.sleep(POLL_SECONDS)
            continue
        except OSError as exc:
            raise IrreversibleFormalFailure(
                f"{slot} prelaunch request surface could not be inspected"
            ) from exc
        observed_mode = stat.S_IMODE(observed.st_mode)
        if stat.S_ISREG(observed.st_mode) and observed_mode == 0o444:
            return
        if stat.S_ISREG(observed.st_mode) and observed_mode == 0o600:
            time.sleep(POLL_SECONDS)
            continue
        raise IrreversibleFormalFailure(
            f"{slot} prelaunch request surface is unsafe"
        )
    raise IrreversibleFormalFailure(
        f"{slot} prelaunch request did not appear"
    )


def _publish_outer_barrier(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    gate1_ownership_identity: Mapping[str, object],
) -> dict[str, object]:
    attempt = state.attempt
    if (
        state.selection_identity is None
        or attempt.outer_start_identity is None
        or attempt.resource_identity is None
        or attempt.acquire_identity is None
        or attempt.barrier_identity is not None
    ):
        raise FormalCampaignError("outer barrier prerequisites are incomplete")
    record = {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_CLAIMS),
        "campaign_root_identity": context["campaign_root_identity"],
        "formal_selection_identity": state.selection_identity,
        "gate1_prelaunch_ownership_identity": dict(gate1_ownership_identity),
        "lock_identities": host.lock_evidence(),
        "manager_epoch": context["manager_epoch"],
        "outer_resource_identity": attempt.resource_identity,
        "outer_start_identity": attempt.outer_start_identity,
        "reference_acquisition_identity": attempt.acquire_identity,
        "released": True,
        "schema_version": "noncert-cuts-ab16-outer-barrier-release-v1",
        "status": "RELEASED",
    }
    effect = attempt.publication("outer-barrier")
    effect.begin()
    try:
        identity = store.publish(
            state.selection["outer_spec"]["barrier_path"],
            record,
            "outer barrier release",
            publication=effect,
        )
    except BaseException as exc:
        effect.note_error(exc)
        raise IrreversibleFormalFailure(
            f"outer barrier publication failed or is uncertain: {exc}"
        ) from exc
    attempt.barrier_identity = identity
    return identity


def _build_reference(
    boundary: authority.FormalRuntimeBoundary,
) -> unit_reference.PersistentUnitReference:
    library = boundary.root["authority_tools"]["libsystemd"]
    return unit_reference.PersistentUnitReference(
        library_path=library["path"],
        expected_library_identity=library,
    )


def _read_controller_result(
    *,
    context: Mapping[str, object],
    selection_identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    path = Path(str(context["formal_attempt_dir"])) / "controller-result.json"
    raw, identity = _wait_record(
        path,
        expected_identity=None,
        label="formal controller result",
        timeout_seconds=RECORD_WAIT_SECONDS,
    )
    checked = success_verifier.validate_controller_result(
        raw,
        context=context,
        selection_identity=selection_identity,
    )
    return checked, identity


def _publish_tracked_phase(
    state: closeout_state.AttemptState,
    store: closeout_helper.ReceiptStore,
    *,
    key: str,
    path: Path | str,
    record: Mapping[str, object],
    validator: Callable[..., Mapping[str, object]],
    validator_kwargs: Mapping[str, object],
) -> dict[str, object]:
    effect = state.publication(key)
    effect.begin()
    try:
        return _publish_phase(
            store,
            path=path,
            record=record,
            phase=key,
            validator=validator,
            validator_kwargs=validator_kwargs,
            publication=effect,
        )
    except BaseException as exc:
        effect.note_error(exc)
        raise


def _normal_expected(
    context: Mapping[str, object],
    selection_identity: Mapping[str, object],
) -> dict[str, object]:
    return {
        "campaign_root_identity": context["campaign_root_identity"],
        "formal_selection_identity": dict(selection_identity),
        "manager_epoch": context["manager_epoch"],
        "package_id": context["package_id"],
    }


def _publish_outer_prelaunch(
    *,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
) -> dict[str, object]:
    if state.selection is None or state.selection_identity is None:
        raise FormalCampaignError("outer prelaunch lacks formal selection")
    unit_name = str(state.selection["outer_spec"]["unit_name"])
    shown = host.show(unit_name)
    if shown != closeout_helper.ABSENT:
        raise IrreversibleFormalFailure(
            "selected outer unit was not absent before its sole launch"
        )
    launch_locks = host.lock_evidence()
    launch_context = _resource_observation_context(
        context,
        authority_identity=state.selection_identity,
        kind="FORMAL_OUTER_PRELAUNCH",
        target=unit_name,
    )
    launch_admission = validate_resource_gate(
        context["campaign_dir"],
        lock_identities=launch_locks,
        observation_context=launch_context,
        allowed_same_uid_processes=_formal_resource_allowlist(state),
    )
    if host.lock_evidence() != launch_locks:
        raise IrreversibleFormalFailure(
            "formal lock identities drifted across outer resource admission"
        )
    empty = _outer_inactive_identity(unit_name)
    record = _common_receipt(
        context,
        state.selection_identity,
        phase="outer_prelaunch",
        outer_identity=success_verifier.validate_outer_identity(
            {
                key: empty[key]
                for key in (
                    "control_group",
                    "invocation_id",
                    "processes",
                    "unit_name",
                )
            },
            expected_unit_name=unit_name,
            active=False,
        ),
        prelaunch_absence={
            "cgroup_absent": True,
            "load_state": "not-found",
            "lock_identities": launch_locks,
            "pid_absent": True,
        },
        resource_admission=launch_admission,
    )
    identity = _publish_tracked_phase(
        state.attempt,
        store,
        key="outer_prelaunch",
        path=state.selection["outer_spec"]["receipt_paths"]["outer_prelaunch"],
        record=record,
        validator=success_verifier.validate_outer_prelaunch,
        validator_kwargs={
            "expected": _normal_expected(context, state.selection_identity),
            "expected_unit_name": unit_name,
            "expected_lock_identities": state.selection["lock_identities"],
            "expected_observation_context": launch_context,
            "expected_allowed_same_uid_processes": _formal_resource_allowlist(
                state
            ),
        },
    )
    state.attempt.outer_prelaunch_identity = identity
    state.outer_resource_admission = dict(launch_admission)
    if state.guardian is None or state.ledger is not None:
        raise IrreversibleFormalFailure(
            "outer prelaunch cannot initialize its guardian ledger"
        )
    state.ledger = initial_ledger(empty)
    state.ledger_sequence = 1
    send_ledger_update(
        state.guardian,
        context=context,
        selection_identity=state.selection_identity,
        ledger=state.ledger,
        phase="outer:prelaunch",
        sequence=state.ledger_sequence,
    )
    return identity


def _launch_outer(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
) -> dict[str, object]:
    if (
        state.selection is None
        or state.selection_identity is None
        or state.attempt.outer_prelaunch_identity is None
        or state.outer_resource_admission is None
    ):
        raise FormalCampaignError("outer launch lacks prelaunch proof")

    def require_launch_owner_live() -> None:
        if state.guardian is None or not guardian_is_alive(state.guardian):
            raise IrreversibleFormalFailure(
                "guardian died before the selected outer launch syscall"
            )
        _formal_resource_allowlist(state)

    closeout_state.begin_outer_launch(state.attempt)
    effect = _launch_selected_unit(
        host,
        context=context,
        spec=state.selection["outer_spec"],
        resource_admission_receipt=state.outer_resource_admission,
        launch_owner_check=require_launch_owner_live,
    )
    closeout_state.record_outer_launch_return(state.attempt, effect)

    def remember_outer(frozen_identity: Mapping[str, object]) -> None:
        if state.outer_identity is not None or state.ledger is None:
            raise IrreversibleFormalFailure(
                "outer live identity was frozen twice"
            )
        state.outer_identity = {
            "control_group": frozen_identity["control_group"],
            "invocation_id": frozen_identity["invocation_id"],
            "processes": frozen_identity["processes"],
            "unit_name": frozen_identity["unit_name"],
        }
        state.ledger = _replace_ledger_identity(
            state.ledger,
            source="outer",
            slot="formal",
            identity=frozen_identity,
        )

    shown, limits, frozen = wait_unit_live(
        host,
        unit_name=str(state.selection["outer_spec"]["unit_name"]),
        resource_contract=state.selection["outer_spec"]["resource_contract"],
        timeout_seconds=GUARDIAN_WAIT_SECONDS,
        on_frozen=remember_outer,
    )
    outer_identity = {
        "control_group": frozen["control_group"],
        "invocation_id": frozen["invocation_id"],
        "processes": frozen["processes"],
        "unit_name": frozen["unit_name"],
    }
    if (
        state.outer_identity != outer_identity
        or state.ledger is None
        or state.guardian is None
        or state.ledger_sequence != 1
    ):
        raise FormalCampaignError("outer launch lost its guardian")
    state.ledger_sequence = 2
    send_ledger_update(
        state.guardian,
        context=context,
        selection_identity=state.selection_identity,
        ledger=state.ledger,
        phase="outer:formal",
        sequence=2,
    )

    start_record = _common_receipt(
        context,
        state.selection_identity,
        phase="outer_start",
        launch_effect={
            "attempted": True,
            "outer_prelaunch_identity": state.attempt.outer_prelaunch_identity,
            "recorded": True,
            "returned": True,
        },
        outer_identity=outer_identity,
        resource_admission=effect["resource_admission"],
    )
    start_identity = _publish_tracked_phase(
        state.attempt,
        store,
        key="outer_start",
        path=state.selection["outer_spec"]["receipt_paths"]["outer_start"],
        record=start_record,
        validator=success_verifier.validate_outer_start,
        validator_kwargs={
            "expected": _normal_expected(context, state.selection_identity),
            "expected_resource_admission": state.outer_resource_admission,
            "expected_unit_name": state.selection["outer_spec"]["unit_name"],
        },
    )
    state.attempt.outer_start_identity = start_identity

    contract = state.selection["outer_spec"]["resource_contract"]
    systemd_properties = {
        **dict(contract),
        "outer_start_identity": start_identity,
    }
    resource_record = _common_receipt(
        context,
        state.selection_identity,
        phase="outer_resource",
        cgroup_limits=limits,
        outer_identity=outer_identity,
        systemd_properties=systemd_properties,
    )
    resource_identity = _publish_tracked_phase(
        state.attempt,
        store,
        key="outer_resource",
        path=state.selection["outer_spec"]["receipt_paths"]["outer_resource"],
        record=resource_record,
        validator=success_verifier.validate_outer_resource,
        validator_kwargs={
            "expected": _normal_expected(context, state.selection_identity),
            "expected_outer_identity": outer_identity,
            "resource_contract": contract,
        },
    )
    state.attempt.resource_identity = resource_identity
    if shown["InvocationID"] != outer_identity["invocation_id"]:
        raise IrreversibleFormalFailure(
            "outer systemd identity changed after resource verification"
        )
    return outer_identity


def _acquire_outer_reference(
    *,
    boundary: authority.FormalRuntimeBoundary,
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
) -> dict[str, object]:
    if (
        state.selection is None
        or state.selection_identity is None
        or state.attempt.resource_identity is None
    ):
        raise FormalCampaignError("RefUnit lacks selected outer resource proof")
    reference = _build_reference(boundary)
    capture = authority._capture_current_manager_epoch(  # noqa: SLF001
        boundary.context
    )
    result = closeout_state.acquire_reference_once(
        boundary,
        state.attempt,
        store,
        reference,
        unit_name=str(state.selection["outer_spec"]["unit_name"]),
        selection_identity=state.selection_identity,
        resource_identity=state.attempt.resource_identity,
        lock_evidence=host.lock_evidence(),
        manager_epoch_capture=capture,
    )
    if result.get("kind") != "RECORDED":
        raise IrreversibleFormalFailure(
            f"RefUnit acquisition did not become canonical: {result}"
        )
    return result


def _service_fixed_campaign(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    latch: closeout_helper.TerminationLatch,
) -> tuple[dict[str, object], dict[str, object]]:
    if (
        state.selection is None
        or state.selection_identity is None
        or state.attempt.reference is None
        or state.attempt.acquire_identity is None
        or state.attempt.resource_identity is None
    ):
        raise FormalCampaignError("campaign service lacks RefUnit prerequisites")
    gate1_ownership = closeout_helper.capture_gate1_ownership(
        boundary,
        store,
        host,
        state.selection,
        state.selection_identity,
        state.attempt.reference,
        resource_identity=state.attempt.resource_identity,
        acquisition_identity=state.attempt.acquire_identity,
    )
    _mirror_gate1_prelaunch(
        boundary=boundary,
        context=context,
        state=state,
        store=store,
        host=host,
    )
    _publish_outer_barrier(
        boundary=boundary,
        context=context,
        state=state,
        store=store,
        host=host,
        gate1_ownership_identity=gate1_ownership,
    )
    deadline = time.monotonic() + float(
        state.selection["outer_spec"]["resource_contract"]["runtime_max_sec"]
    )
    for slot in GATE1_SLOTS:
        _wait_and_mirror_child(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            host=host,
            latch=latch,
            source="gate1",
            slot=slot,
            deadline=deadline,
        )
    for ordinal, slot in enumerate(ARM_SEQUENCE, start=1):
        paths = state.selection["arm_prelaunch_paths"][slot]
        _wait_arm_request(
            state=state,
            host=host,
            latch=latch,
            path=paths["request"],
            slot=slot,
            deadline=deadline,
        )

        def before_arm_receipt(
            mirrored_slot: str,
            unit_name: str,
        ) -> Mapping[str, object]:
            _mirror_arm_prelaunch(
                context=context,
                state=state,
                host=host,
                slot=mirrored_slot,
                unit_name=unit_name,
            )
            return validate_resource_gate(
                context["campaign_dir"],
                lock_identities=host.lock_evidence(),
                observation_context=_resource_observation_context(
                    context,
                    authority_identity=state.selection_identity,
                    kind="FORMAL_ORGANIC_ARM_PRELAUNCH",
                    target=unit_name,
                    ordinal=ordinal,
                    slot=mirrored_slot,
                ),
                allowed_same_uid_processes=_formal_resource_allowlist(state),
            )

        arm_resource_context = _resource_observation_context(
            context,
            authority_identity=state.selection_identity,
            kind="FORMAL_ORGANIC_ARM_PRELAUNCH",
            target="DERIVE_FROM_VALIDATED_PRE_RUN",
            ordinal=ordinal,
            slot=slot,
        )
        closeout_helper.service_arm_prelaunch(
            boundary,
            store,
            host,
            state.selection,
            state.attempt.reference,
            slot=slot,
            ordinal=ordinal,
            expected_allowed_same_uid_processes=_formal_resource_allowlist(
                state
            ),
            expected_resource_observation_context=arm_resource_context,
            before_receipt_publish=before_arm_receipt,
        )
        _wait_and_mirror_child(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            host=host,
            latch=latch,
            source="arm",
            slot=slot,
            deadline=deadline,
        )
    if state.ledger_sequence != len(LEDGER_PHASES):
        raise IrreversibleFormalFailure(
            "finite child ledger did not cover outer plus all twenty children"
        )
    return _read_controller_result(
        context=context,
        selection_identity=state.selection_identity,
    )


def _publish_normal_closeout(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    latch: closeout_helper.TerminationLatch,
    controller_identity: Mapping[str, object],
) -> dict[str, object]:
    if (
        state.selection is None
        or state.selection_identity is None
        or state.outer_identity is None
        or state.ledger is None
        or state.guardian is None
        or state.attempt.reference is None
        or state.attempt.acquire_identity is None
    ):
        raise FormalCampaignError("normal closeout prerequisites are incomplete")
    paths = state.selection["outer_spec"]["receipt_paths"]
    expected = _normal_expected(context, state.selection_identity)

    _normal_closeout_checkpoint(
        state,
        latch,
        phase="normal child cleanup replay",
    )
    child = closeout_helper.audit_children(
        boundary,
        store,
        host,
        state.attempt.reference,
        state.selection,
        abnormal=False,
        expected_allowed_same_uid_processes=_formal_resource_allowlist(state),
        prior_launch_ledger=state.ledger,
    )
    bound_ledger = closeout_helper.bind_outer_ledger(
        child,
        state.ledger["outer"],
    )
    state.child_audit_identity = child["identity"]
    state.ledger = bound_ledger
    if child["record"]["status"] != "PASS":
        raise IrreversibleFormalFailure(
            "normal child cleanup replay did not prove all twenty identities absent"
        )

    _normal_closeout_checkpoint(
        state,
        latch,
        phase="outer stable terminal wait",
    )
    first, stable, hold_ns = wait_unit_terminal(
        host,
        unit_name=str(state.outer_identity["unit_name"]),
        timeout_seconds=RECORD_WAIT_SECONDS,
    )
    _normal_closeout_checkpoint(
        state,
        latch,
        phase="outer terminal receipt publication",
    )
    terminal_record = _common_receipt(
        context,
        state.selection_identity,
        phase="outer_terminal",
        outer_identity=state.outer_identity,
        stable_terminal={
            "child_audit_identity": state.child_audit_identity,
            "controller_result_identity": dict(controller_identity),
            "first_systemd": first,
            "reference_acquisition_identity": state.attempt.acquire_identity,
            "stability_hold_ns": hold_ns,
            "stable_systemd": stable,
        },
    )
    state.outer_terminal_identity = _publish_tracked_phase(
        state.attempt,
        store,
        key="outer_terminal",
        path=paths["outer_terminal"],
        record=terminal_record,
        validator=success_verifier.validate_outer_terminal,
        validator_kwargs={
            "expected": expected,
            "expected_outer_identity": state.outer_identity,
        },
    )

    _normal_closeout_checkpoint(
        state,
        latch,
        phase="outer scoped stop/reset",
    )
    cleanup_errors = host.stop_reset_once(
        str(state.outer_identity["unit_name"])
    )
    if cleanup_errors:
        raise IrreversibleFormalFailure(
            f"outer scoped stop/reset failed: {cleanup_errors}"
        )
    cleanup_observation = host.wait_state(
        str(state.outer_identity["unit_name"]),
        str(state.outer_identity["control_group"]),
        state.outer_identity["processes"],
        referenced=True,
        timeout=RECORD_WAIT_SECONDS,
    )
    _normal_closeout_checkpoint(
        state,
        latch,
        phase="observer receipt publication",
    )
    heavy_absence = {
        "all_absent": True,
        "child_audit_identity": state.child_audit_identity,
        "outer_terminal_identity": state.outer_terminal_identity,
    }
    observer_record = _common_receipt(
        context,
        state.selection_identity,
        phase="observer",
        heavy_absence=heavy_absence,
        outer_identity=state.outer_identity,
    )
    observer_identity = _publish_tracked_phase(
        state.attempt,
        store,
        key="observer",
        path=paths["observer"],
        record=observer_record,
        validator=success_verifier.validate_observer,
        validator_kwargs={
            "expected": expected,
            "expected_outer_identity": state.outer_identity,
        },
    )
    state.observer_identity = observer_identity
    closeout_state.record_late_proof_once(
        state.attempt,
        "observer_identity",
        observer_identity,
    )

    _normal_closeout_checkpoint(
        state,
        latch,
        phase="pre-Unref cleanup receipt publication",
    )
    pre_unref_record = _common_receipt(
        context,
        state.selection_identity,
        phase="pre_unref_cleanup",
        child_audit_identity=state.child_audit_identity,
        heavy_absence=heavy_absence,
        observer_identity=observer_identity,
        outer_cleanup={
            "cgroup_absent": cleanup_observation["cgroup_absent"],
            "keeper_absent": cleanup_observation["processes_absent"],
            "load_state": cleanup_observation["systemctl"]["LoadState"],
            "outer_terminal_identity": state.outer_terminal_identity,
            "payload_absent": cleanup_observation["processes_absent"],
            "unit_kept_loaded_by_reference": cleanup_observation[
                "unit_kept_loaded_by_reference"
            ],
        },
        outer_identity=state.outer_identity,
    )
    pre_unref_identity = _publish_tracked_phase(
        state.attempt,
        store,
        key="pre_unref_cleanup",
        path=paths["pre_unref_cleanup"],
        record=pre_unref_record,
        validator=success_verifier.validate_pre_unref_cleanup,
        validator_kwargs={
            "expected": expected,
            "expected_outer_identity": state.outer_identity,
        },
    )
    state.pre_unref_identity = pre_unref_identity
    closeout_state.record_late_proof_once(
        state.attempt,
        "pre_unref_cleanup_identity",
        pre_unref_identity,
    )

    _normal_closeout_checkpoint(
        state,
        latch,
        phase="exact-once RefUnit Unref/close",
    )
    reference_terminal = closeout_state.finalize_reference_once(
        boundary,
        state.attempt,
        store,
        unit_name=str(state.outer_identity["unit_name"]),
        prove_unref=True,
        reason="NORMAL_SUCCESS_CLOSEOUT",
        observer_identity=observer_identity,
        pre_unref_cleanup_identity=pre_unref_identity,
    )
    state.reference_terminal = dict(reference_terminal)
    if reference_terminal.get("kind") != "RECORDED":
        raise IrreversibleFormalFailure(
            f"RefUnit release did not become canonical: {reference_terminal}"
        )
    _normal_closeout_checkpoint(
        state,
        latch,
        phase="post-Unref absence wait",
    )
    post = host.wait_state(
        str(state.outer_identity["unit_name"]),
        str(state.outer_identity["control_group"]),
        state.outer_identity["processes"],
        referenced=False,
        timeout=RECORD_WAIT_SECONDS,
    )
    _normal_closeout_checkpoint(
        state,
        latch,
        phase="post-Unref absence receipt publication",
    )
    post_record = _common_receipt(
        context,
        state.selection_identity,
        phase="post_unref_absence",
        cgroup_absent=post["cgroup_absent"],
        load_state={
            "reference_release_identity": state.attempt.reference_release_identity,
            "value": post["systemctl"]["LoadState"],
        },
        outer_identity=state.outer_identity,
        pid_absent=post["processes_absent"],
    )
    post_identity = _publish_tracked_phase(
        state.attempt,
        store,
        key="post_unref_absence",
        path=paths["post_unref_absence"],
        record=post_record,
        validator=success_verifier.validate_post_unref_absence,
        validator_kwargs={
            "expected": expected,
            "expected_outer_identity": state.outer_identity,
        },
    )
    state.post_unref_identity = post_identity
    closeout_state.record_late_proof_once(
        state.attempt,
        "post_unref_absence_identity",
        post_identity,
    )
    return {
        "post_unref_absence_identity": post_identity,
        "status": "SUBSTANTIVE_RECEIPTS_READY_FOR_DETACHED_REPLAY",
    }


def _release_guardian_and_locks(
    *,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    latch: closeout_helper.TerminationLatch,
    expected: Mapping[str, object],
) -> dict[str, object]:
    if (
        state.selection is None
        or state.selection_identity is None
        or state.guardian is None
        or state.ledger is None
        or state.post_unref_identity is None
        or state.detached_success_identity is None
    ):
        raise FormalCampaignError(
            "guardian release lacks detached substantive closeout proof"
        )
    if host.locks_released:
        raise IrreversibleFormalFailure(
            "guardian release began after supervisor locks were released"
        )
    paths = state.selection["outer_spec"]["receipt_paths"]
    _normal_closeout_checkpoint(
        state,
        latch,
        phase="guardian exact-once lock close",
    )
    closeout_state.begin_guardian_close(state.attempt)
    send_guardian_terminal(
        state.guardian,
        context=context,
        selection_identity=state.selection_identity,
        ledger=state.ledger,
        command="NORMAL_RELEASE",
        reason="NORMAL_SUCCESS_HEAVY_IDENTITIES_ABSENT",
    )
    frame = guardian.receive_frame(
        state.guardian.connection,
        expected_fd_count=0,
    )
    close_record = frame.record
    closeout_state.record_guardian_close_return(
        state.attempt,
        {
            "message_identity": frame.identity,
            "success_eligible": close_record.get("success_eligible"),
        },
    )
    if (
        type(close_record) is not dict
        or set(close_record) != set(guardian.LOCK_CLOSE_FIELDS)
        or close_record.get("schema_version")
        != guardian.GUARDIAN_LOCK_CLOSE_SCHEMA
        or close_record.get("status") != "GUARDIAN_COPIES_CLOSED"
        or close_record.get("outcome") != "SUCCESS_CANDIDATE"
        or close_record.get("success_eligible") is not True
        or close_record.get("errors") != []
        or close_record.get("frozen_ledger") != state.ledger
    ):
        raise IrreversibleFormalFailure(
            "guardian did not return one normal eligible lock-close record"
        )
    _normal_closeout_checkpoint(
        state,
        latch,
        phase="guardian lock-close receipt publication",
    )
    close_effect = state.attempt.publication("guardian-lock-close")
    close_effect.begin()
    try:
        guardian_close_identity = store.publish(
            paths["guardian_lock_close"],
            close_record,
            "guardian lock close",
            publication=close_effect,
        )
    except BaseException as exc:
        close_effect.note_error(exc)
        raise
    state.guardian_close_identity = guardian_close_identity
    closeout_state.record_late_proof_once(
        state.attempt,
        "guardian_close_identity",
        guardian_close_identity,
    )
    state.guardian.close_received = True
    _normal_closeout_checkpoint(
        state,
        latch,
        phase="guardian control connection close",
    )
    _close_guardian_connection(state.guardian)

    _normal_closeout_checkpoint(
        state,
        latch,
        phase="guardian terminal absence wait",
    )
    guardian_absence = _wait_guardian_absence(
        host,
        state.guardian,
        timeout_seconds=GUARDIAN_WAIT_SECONDS,
    )
    _post_release_signal_checkpoint(
        latch,
        phase="guardian absence receipt publication",
    )
    absence_record = _common_receipt(
        context,
        state.selection_identity,
        phase="guardian_absence",
        guardian_close_identity=guardian_close_identity,
        guardian_identity=state.guardian.unit_identity,
        post_unref_absence_identity=state.post_unref_identity,
        **guardian_absence,
    )
    guardian_absence_identity = _publish_tracked_phase(
        state.attempt,
        store,
        key="guardian_absence",
        path=paths["guardian_absence"],
        record=absence_record,
        validator=success_verifier.validate_guardian_absence,
        validator_kwargs={
            "expected": expected,
            "expected_guardian_close_identity": guardian_close_identity,
            "expected_guardian_identity": state.guardian.unit_identity,
            "expected_post_unref_absence_identity": state.post_unref_identity,
        },
    )
    closeout_state.record_late_proof_once(
        state.attempt,
        "guardian_absence_identity",
        guardian_absence_identity,
    )

    _post_release_signal_checkpoint(
        latch,
        phase="supervisor exact-once lock release",
    )
    lock_identities = host.lock_evidence()
    closeout_state.begin_supervisor_lock_release(state.attempt)
    release_effect = host.release_locks_once()
    closeout_state.record_supervisor_lock_release_return(
        state.attempt,
        release_effect,
    )
    _post_release_signal_checkpoint(
        latch,
        phase="dual-lock-release receipt publication",
    )
    dual_record = _common_receipt(
        context,
        state.selection_identity,
        phase="dual_lock_release",
        detached_success_identity=state.detached_success_identity,
        guardian_absence_identity=guardian_absence_identity,
        guardian_close_identity=guardian_close_identity,
        lock_identities=lock_identities,
        supervisor_release={
            "after_guardian_absence": True,
            "attempted": True,
            "recorded": True,
            "returned": True,
        },
        terminal_join={
            "detached_success_before_guardian_close": True,
            "guardian_absence_before_supervisor_release": True,
            "locks_released_after_substantive_verification": True,
        },
    )
    dual_identity = _publish_tracked_phase(
        state.attempt,
        store,
        key="dual-lock-release",
        path=paths["dual_lock_release"],
        record=dual_record,
        validator=success_verifier.validate_dual_lock_release,
        validator_kwargs={
            "expected": expected,
            "expected_lock_identities": lock_identities,
            "expected_detached_success_identity": (
                state.detached_success_identity
            ),
            "expected_guardian_absence_identity": (
                guardian_absence_identity
            ),
            "expected_guardian_close_identity": guardian_close_identity,
        },
    )
    state.dual_release_identity = dual_identity
    closeout_state.record_late_proof_once(
        state.attempt,
        "dual_lock_release_identity",
        dual_identity,
    )
    return {
        "dual_lock_release_identity": dual_identity,
        "guardian_absence_identity": guardian_absence_identity,
        "guardian_lock_close_identity": guardian_close_identity,
    }


def _run_detached_success(
    *,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
) -> dict[str, object]:
    if (
        state.selection is None
        or state.selection_identity is None
        or state.post_unref_identity is None
    ):
        raise FormalCampaignError(
            "detached success verifier lacks post-Unref substantive proof"
        )
    if host.locks_released:
        raise IrreversibleFormalFailure(
            "detached success verifier started after supervisor lock release"
        )
    lock_identities = host.lock_evidence()
    if state.selection["lock_identities"] != lock_identities:
        raise IrreversibleFormalFailure(
            "detached success verifier lock identities drifted"
        )
    closeout_state.begin_detached_success_verifier(state.attempt)
    stdout, stderr = run_selected_direct(
        context=context,
        role="formal-success-verifier",
        role_argv=(
            "--campaign-dir",
            str(context["campaign_dir"]),
            "--formal-selection",
            str(context["formal_selection_path"]),
        ),
        timeout_seconds=RECORD_WAIT_SECONDS,
    )
    closeout_state.record_detached_success_verifier_return(
        state.attempt,
        {
            "lock_identities": lock_identities,
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        },
    )
    if host.locks_released or host.lock_evidence() != lock_identities:
        raise IrreversibleFormalFailure(
            "supervisor locks changed during detached substantive replay"
        )
    path = state.selection["outer_spec"]["receipt_paths"][
        "detached_closeout"
    ]
    record, identity = store.document(
        path,
        "formal detached success",
    )
    success_verifier.validate_pre_release_success(
        record,
        context=context,
        selection_identity=state.selection_identity,
        expected_lock_identities=lock_identities,
    )
    state.detached_success_identity = identity
    closeout_state.record_late_proof_once(
        state.attempt,
        "detached_success_identity",
        identity,
    )
    return {
        "detached_success_identity": identity,
        "status": "PRE_RELEASE_VERIFIED",
    }


def _create_consumed_attempt(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
) -> tuple[dict[str, object], dict[str, object]]:
    """Create the sole attempt and prove its canonical consumption marker."""

    authority._mkdir_exclusive(boundary.formal_dir)  # noqa: SLF001
    state.attempt.directory_created = True
    child_parent_error: BaseException | None = None
    try:
        authority._mkdir_exclusive(  # noqa: SLF001
            boundary.formal_dir / "arm-prelaunch"
        )
    except BaseException as exc:
        child_parent_error = exc
    marker_identity = closeout_state.publish_attempt_consumption(
        boundary,
        state.attempt,
        store,
        created_at_utc=_utc_now(),
    )
    marker, replay_identity = store.document(
        boundary.formal_dir / "attempt-consumption.json",
        "formal attempt consumption",
    )
    checked = launch_validator.validate_attempt_consumption(
        marker,
        expected_context=context,
    )
    if replay_identity != marker_identity:
        raise IrreversibleFormalFailure(
            "attempt consumption readback identity drifted"
        )
    if child_parent_error is not None:
        raise IrreversibleFormalFailure(
            "arm-prelaunch directory creation failed after attempt consumption: "
            f"{child_parent_error}"
        )
    return checked, marker_identity


def _failure_phase(state: SupervisorState) -> str:
    attempt = state.attempt
    if attempt.selection_identity is None:
        return "ATTEMPT_RECORDED_SELECTION_UNRECORDED"
    if not attempt.outer_launch_attempted:
        return "SELECTION_RECORDED_OUTER_NOT_LAUNCHED"
    if attempt.outer_start_identity is None:
        return "OUTER_LAUNCH_FAILED_OR_UNCERTAIN"
    if attempt.resource_identity is None:
        return "OUTER_STARTED_RESOURCE_UNRECORDED"
    if not attempt.acquire_attempted:
        return "OUTER_STARTED_REF_UNACQUIRED"
    if not attempt.acquire_returned:
        return "REF_ACQUIRE_FAILED_OR_UNCERTAIN"
    if attempt.acquire_identity is None:
        if attempt.connection_action == "abort_close":
            return "ACQUIRE_UNPROVEN_CONNECTION_DROPPED"
        return "REF_ACQUIRE_RETURNED_BUT_UNRECORDED"
    if attempt.reference_release_identity is None:
        if attempt.connection_action == "abort_close":
            return "UNREF_UNPROVEN_CONNECTION_DROPPED"
        if attempt.close_attempted and not attempt.close_returned:
            return "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN"
        if attempt.close_returned:
            return "CONNECTION_CLOSED_RELEASE_UNRECORDED"
        if attempt.release_returned:
            return "UNREF_RETURNED_BUT_UNRECORDED"
        if attempt.release_attempted:
            return "UNREF_FAILED_OR_UNCERTAIN"
        return "REFERENCE_HELD_PRE_UNREF_FAILURE"
    if attempt.post_unref_absence_identity is None:
        return "POST_UNREF_ABSENCE_UNPROVED"
    if attempt.detached_success_identity is None:
        return (
            "DETACHED_SUCCESS_VERIFIER_FAILED_OR_UNCERTAIN"
            if attempt.detached_success_verifier_attempted
            else "DETACHED_SUCCESS_VERIFIER_NOT_ATTEMPTED"
        )
    if attempt.guardian_close_identity is None:
        return (
            "GUARDIAN_CLOSE_FAILED_OR_UNCERTAIN"
            if attempt.guardian_close_attempted
            else "GUARDIAN_CLOSE_NOT_ATTEMPTED"
        )
    if attempt.guardian_absence_identity is None:
        return "GUARDIAN_ABSENCE_UNPROVED"
    if attempt.lock_release_return is None:
        return (
            "SUPERVISOR_LOCK_RELEASE_FAILED_OR_UNCERTAIN"
            if attempt.lock_release_attempted
            else "SUPERVISOR_LOCK_RELEASE_NOT_ATTEMPTED"
        )
    if attempt.dual_lock_release_identity is None:
        publication = attempt.publications.get("dual-lock-release")
        return (
            "DUAL_LOCK_RELEASE_RECEIPT_FAILED_OR_UNCERTAIN"
            if publication is not None and publication.attempted
            else "DUAL_LOCK_RELEASE_RECEIPT_NOT_ATTEMPTED"
        )
    return "FINAL_SUCCESS_RETURN_FAILED_OR_UNCERTAIN"


def _freeze_failure_outer(
    *,
    state: SupervisorState,
    host: closeout_helper.PinnedHost,
) -> dict[str, object]:
    if state.selection is None:
        return _outer_inactive_identity("")
    unit_name = str(state.selection["outer_spec"]["unit_name"])
    if state.ledger is not None:
        recorded = closeout_state.validate_frozen_ledger(
            state.ledger
        )["outer"]
        active = bool(
            recorded["invocation_id"]
            or recorded["control_group"]
            or recorded["processes"]
        )
        if (
            active
            or not state.attempt.outer_launch_attempted
            or state.attempt.outer_start_identity is not None
        ):
            return recorded
    shown = host.show(unit_name)
    if (
        shown == closeout_helper.ABSENT
        and state.attempt.outer_launch_attempted
        and state.attempt.outer_start_identity is None
    ):
        shown = _wait_uncertain_unit_resolution(
            host,
            unit_name,
            timeout_seconds=GUARDIAN_WAIT_SECONDS,
        )
    if shown == closeout_helper.ABSENT:
        return _outer_inactive_identity(unit_name)
    frozen = host.freeze_identity(
        source="outer",
        slot="formal",
        unit_name=unit_name,
        shown=shown,
        ownership_classification="PRELAUNCH_OWNED_ACTIVE",
    )
    checked = closeout_state.validate_frozen_identity(
        frozen,
        expected_source="outer",
        expected_slot="formal",
    )
    if checked["identity_complete"] is not True:
        raise IrreversibleFormalFailure(
            "outer launch identity could not be frozen for containment"
        )
    if state.outer_identity is not None and {
        key: checked[key]
        for key in ("control_group", "invocation_id", "processes", "unit_name")
    } != state.outer_identity:
        raise IrreversibleFormalFailure(
            "outer runtime identity drifted before containment"
        )
    return checked


def _hold_locks_forever(
    *,
    host: closeout_helper.PinnedHost,
    reason: BaseException | str,
) -> None:
    announcement = {
        "authorizations": dict(FALSE_CLAIMS),
        "isolation_active": True,
        "lower_bound": "absent",
        "reason": str(reason),
        "status": "CONTAINMENT_HOLD_EVIDENCE_GAP",
        "success_eligible": False,
        "upper_bound": [1188, 18],
    }
    print(
        authority.canonical_json(announcement).decode("utf-8"),
        file=sys.stderr,
        flush=True,
    )
    while True:
        try:
            host.lock_evidence()
        except BaseException:
            pass
        time.sleep(closeout_state.HOLD_POLL_SECONDS)


def _wait_ledger_absence(
    *,
    host: closeout_helper.PinnedHost,
    ledger: Mapping[str, object],
    attempt: closeout_state.AttemptState,
) -> dict[str, object]:
    while True:
        try:
            observation = host.observe_frozen_absence(ledger)
            if observation["all_absent"] is True:
                return observation
        except BaseException as exc:
            item = _failure("FINAL_ABSENCE_OBSERVATION_FAILED", exc)
            if item not in attempt.errors:
                attempt.errors.append(item)
        time.sleep(closeout_state.HOLD_POLL_SECONDS)


def _recorded_incomplete_identity(
    state: closeout_state.AttemptState,
) -> dict[str, object] | str:
    if state.incomplete_identity is not None:
        return closeout_state.validate_identity_join(
            state.incomplete_identity,
            "formal incomplete",
        )
    markerless = state.publications.get("markerless-consumed-incomplete")
    if markerless is not None and markerless.recorded_identity is not None:
        return closeout_state.validate_identity_join(
            markerless.recorded_identity,
            "markerless incomplete",
        )
    return "unrecorded"


def _publish_failure_release(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    phase: str,
    guardian_absence_identity: Mapping[str, object],
    ledger: Mapping[str, object],
    final_observation: Mapping[str, object],
    reference_terminal: Mapping[str, object],
    lock_identities: Sequence[Mapping[str, object]],
    containment_hold_identity: Mapping[str, object] | str = "absent",
    containment_clearance_identity: Mapping[str, object] | str = "absent",
    containment_lock_release_identity: Mapping[str, object] | str = "absent",
    containment_lock_release_publication: Mapping[str, object] | str = "absent",
) -> dict[str, object]:
    checked_ledger = closeout_state.validate_frozen_ledger(ledger)
    checked_observation = closeout_state.validate_absence_observation(
        final_observation,
        ledger=checked_ledger,
    )
    if checked_observation["all_absent"] is not True:
        raise IrreversibleFormalFailure(
            "failure release cannot be published before heavy absence"
        )
    checked_terminal = closeout_state._validate_reference_terminal(  # noqa: SLF001
        reference_terminal
    )
    checked_locks = closeout_state._validate_lock_evidence(  # noqa: SLF001
        lock_identities
    )

    def optional_identity(
        value: Mapping[str, object] | str,
        label: str,
    ) -> dict[str, object] | str:
        if type(value) is str and value in {"absent", "unrecorded"}:
            return value
        return closeout_state.validate_identity_join(value, label)

    detached_success_path = Path(
        str(context["outer_spec"]["receipt_paths"]["detached_closeout"])
    )
    detached_success_identity: dict[str, object] | str = "absent"
    if os.path.lexists(detached_success_path):
        detached_success_identity = _identity(detached_success_path)
    checked_lock_publication: dict[str, object] | str
    if containment_lock_release_publication == "absent":
        checked_lock_publication = "absent"
    else:
        checked_lock_publication = (
            closeout_state._validate_publication_effect_record(  # noqa: SLF001
                containment_lock_release_publication,
                "lock-release",
            )
        )
    record = {
        "attempt_directory_created": state.attempt.directory_created,
        "attempt_marker_identity": (
            state.attempt.marker_identity
            if state.attempt.marker_identity is not None
            else "absent"
        ),
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_CLAIMS),
        "b6_changed": False,
        "bounds_changed": False,
        "campaign_root_identity": context["campaign_root_identity"],
        "cleanup_evidence": {
            "containment_clearance_identity": optional_identity(
                containment_clearance_identity,
                "failure containment clearance",
            ),
            "containment_hold_identity": optional_identity(
                containment_hold_identity,
                "failure containment hold",
            ),
            "containment_lock_release_identity": optional_identity(
                containment_lock_release_identity,
                "failure containment lock release",
            ),
            "containment_lock_release_publication": checked_lock_publication,
            "errors": closeout_state.validate_failure_list(
                state.attempt.errors,
                "failure cleanup",
            ),
            "final_observation": checked_observation,
            "frozen_ledger": checked_ledger,
            "reference_terminal": checked_terminal,
        },
        "created_at_utc": _utc_now(),
        "detached_success_output_identity": detached_success_identity,
        "formal_selection_identity": (
            state.selection_identity
            if state.selection_identity is not None
            else "absent"
        ),
        "guardian_absence_identity": closeout_state.validate_identity_join(
            guardian_absence_identity,
            "failure guardian absence",
        ),
        "heavy_identities_absent": True,
        "incomplete_identity": _recorded_incomplete_identity(state.attempt),
        "lock_identities": checked_locks,
        "lock_lifecycle": {
            "detached_incomplete_is_next_required_step": True,
            "supervisor_lock_release_permitted": False,
            "supervisor_locks_must_remain_held": True,
        },
        "lower_bound": "absent",
        "outcome": "INCOMPLETE",
        "package_id": context["package_id"],
        "phase": phase,
        "production_authority_changed": False,
        "production_certified": False,
        "retry_eligible": False,
        "schema_version": FAILURE_RELEASE_SCHEMA,
        "status": "INCOMPLETE_PRE_RELEASE",
        "stage_b_changed": False,
        "success_eligible": False,
        "upper_bound": [1188, 18],
    }
    return store.publish(
        boundary.formal_dir / "failure-release.json",
        record,
        "formal failure release",
    )


def _run_detached_incomplete(
    *,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    expected_lock_identities: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    checked_locks = closeout_state._validate_lock_evidence(  # noqa: SLF001
        expected_lock_identities
    )
    if host.locks_released or host.lock_evidence() != checked_locks:
        raise IrreversibleFormalFailure(
            "detached incomplete verifier started without its exact three locks"
        )
    path = Path(str(context["formal_attempt_dir"])) / "failure-release.json"
    failure_release_identity = _identity(path)
    stdout, stderr = run_selected_direct(
        context=context,
        role="formal-success-verifier",
        role_argv=(
            "--campaign-dir",
            str(context["campaign_dir"]),
            "--incomplete-release",
            str(path),
        ),
        timeout_seconds=RECORD_WAIT_SECONDS,
    )
    record, identity = store.document(
        state.selection["outer_spec"]["receipt_paths"][
            "detached_incomplete_closeout"
        ]
        if state.selection is not None
        else context["outer_spec"]["receipt_paths"][
            "detached_incomplete_closeout"
        ],
        "formal detached incomplete",
    )
    if (
        record.get("schema_version")
        != success_verifier.INCOMPLETE_RECEIPT_SCHEMA
        or record.get("status") != "PRE_RELEASE_VERIFIED_INCOMPLETE"
        or record.get("authority_scope") != AUTHORITY_SCOPE
        or record.get("authorizations") != FALSE_CLAIMS
        or record.get("success_eligible") is not False
        or record.get("upper_bound") != [1188, 18]
        or record.get("lower_bound") != "absent"
        or record.get("bounds_changed") is not False
        or record.get("production_certified") is not False
        or record.get("production_authority_changed") is not False
        or record.get("b6_changed") is not False
        or record.get("stage_b_changed") is not False
        or type(record.get("input_identities")) is not dict
        or record["input_identities"].get("failure_release_identity")
        != failure_release_identity
    ):
        raise IrreversibleFormalFailure(
            "detached incomplete verifier crossed its claim boundary"
        )
    if host.locks_released or host.lock_evidence() != checked_locks:
        raise IrreversibleFormalFailure(
            "supervisor locks changed during detached incomplete replay"
        )
    return {
        "detached_incomplete_identity": identity,
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
    }


def _publish_failure_terminal_release(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    phase: str,
    lock_identities: Sequence[Mapping[str, object]],
    lock_release_effect: Mapping[str, object],
    detached_substantive_identity: Mapping[str, object],
    detached_substantive_kind: str,
    failure_pre_release_identity: Mapping[str, object] | str,
    terminal_predecessor_identity: Mapping[str, object] | str = "absent",
) -> dict[str, object]:
    checked_locks = closeout_state._validate_lock_evidence(  # noqa: SLF001
        lock_identities
    )
    checked_release = closeout_state._validate_lock_release_effect(  # noqa: SLF001
        lock_release_effect,
        expected_locks=checked_locks,
    )
    detached_identity = closeout_state.validate_identity_join(
        detached_substantive_identity,
        "failure terminal detached substantive replay",
    )
    if failure_pre_release_identity == "absent":
        checked_failure: dict[str, object] | str = "absent"
    else:
        checked_failure = closeout_state.validate_identity_join(
            failure_pre_release_identity,
            "failure pre-release",
        )
    if (
        type(terminal_predecessor_identity) is str
        and terminal_predecessor_identity in {"absent", "unrecorded"}
    ):
        checked_predecessor: dict[str, object] | str = str(
            terminal_predecessor_identity
        )
    else:
        checked_predecessor = closeout_state.validate_identity_join(
            terminal_predecessor_identity,
            "failure terminal predecessor",
        )
    record = {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_CLAIMS),
        "b6_changed": False,
        "bounds_changed": False,
        "campaign_root_identity": context["campaign_root_identity"],
        "created_at_utc": _utc_now(),
        "detached_substantive_identity": detached_identity,
        "detached_substantive_kind": detached_substantive_kind,
        "failure_pre_release_identity": checked_failure,
        "formal_selection_identity": (
            state.selection_identity
            if state.selection_identity is not None
            else "absent"
        ),
        "lock_identities": checked_locks,
        "lock_release_effect": checked_release,
        "lower_bound": "absent",
        "outcome": "INCOMPLETE",
        "package_id": context["package_id"],
        "phase": phase,
        "production_authority_changed": False,
        "production_certified": False,
        "retry_eligible": False,
        "schema_version": FAILURE_TERMINAL_RELEASE_SCHEMA,
        "stage_b_changed": False,
        "status": "INCOMPLETE_RELEASED",
        "success_eligible": False,
        "terminal_join": {
            "detached_substantive_before_supervisor_release": True,
            "locks_released_after_substantive_verification": True,
            "terminal_predecessor_is_unique": True,
        },
        "terminal_predecessor_identity": checked_predecessor,
        "upper_bound": [1188, 18],
    }
    identity = store.publish(
        boundary.formal_dir / "failure-terminal-release.json",
        record,
        "formal failure terminal release",
    )
    replay, replay_identity = store.document(
        boundary.formal_dir / "failure-terminal-release.json",
        "formal failure terminal release",
    )
    if replay_identity != identity:
        raise IrreversibleFormalFailure(
            "failure terminal release readback identity drifted"
        )
    success_verifier.validate_failure_terminal_release(
        replay,
        context=context,
        expected_identity=identity,
        expected_lock_identities=checked_locks,
        expected_detached_substantive_identity=detached_identity,
        expected_detached_substantive_kind=detached_substantive_kind,
        expected_failure_pre_release_identity=checked_failure,
        expected_selection_identity=state.selection_identity,
        expected_terminal_predecessor_identity=checked_predecessor,
    )
    return identity


def _complete_pre_release_failure(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    phase: str,
    lock_identities: Sequence[Mapping[str, object]],
    guardian_absence_identity: Mapping[str, object],
    failure_pre_release_identity: Mapping[str, object],
) -> dict[str, object]:
    checked_locks = closeout_state._validate_lock_evidence(  # noqa: SLF001
        lock_identities
    )
    detached = _run_detached_incomplete(
        context=context,
        state=state,
        store=store,
        host=host,
        expected_lock_identities=checked_locks,
    )
    checked_guardian_absence = closeout_state.validate_identity_join(
        guardian_absence_identity,
        "failure guardian absence",
    )
    if state.attempt.guardian_absence_identity is None:
        state.attempt.guardian_absence_identity = checked_guardian_absence
    elif state.attempt.guardian_absence_identity != checked_guardian_absence:
        raise IrreversibleFormalFailure(
            "failure guardian absence identity changed before lock release"
        )
    if state.attempt.lock_release_attempted or host.locks_released:
        raise IrreversibleFormalFailure(
            "pre-release failure reached lock release more than once"
        )
    closeout_state.begin_supervisor_lock_release(state.attempt)
    release = host.release_locks_once()
    closeout_state.record_supervisor_lock_release_return(
        state.attempt,
        release,
    )
    detached_identity = closeout_state.validate_identity_join(
        cast(
            Mapping[str, object],
            detached["detached_incomplete_identity"],
        ),
        "detached incomplete before failure terminal release",
    )
    terminal_identity = _publish_failure_terminal_release(
        boundary=boundary,
        context=context,
        state=state,
        store=store,
        phase=phase,
        lock_identities=checked_locks,
        lock_release_effect=release,
        detached_substantive_identity=detached_identity,
        detached_substantive_kind="detached_incomplete_v3",
        failure_pre_release_identity=failure_pre_release_identity,
    )
    return {
        **detached,
        "failure_terminal_release_identity": terminal_identity,
        "lock_release": release,
    }


def _close_preselection(
    *,
    context: Mapping[str, object],
    state: SupervisorState,
    admission_identity: Mapping[str, object],
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
) -> dict[str, object]:
    session = state.guardian
    if session is None:
        identities = host.lock_evidence()
        return {
            "guardian_absence_identity": "absent",
            "lock_identities": identities,
        }
    selection_absent = not os.path.lexists(context["formal_selection_path"])
    cleanup_errors: list[dict[str, str]] = []
    if selection_absent:
        try:
            send_preselection_cancel(
                session,
                context=context,
                admission_identity=admission_identity,
                lock_identities=host.lock_evidence(),
                reason="FORMAL_SELECTION_NOT_ESTABLISHED",
            )
        except BaseException as exc:
            cleanup_errors.append(
                _failure(
                    "GUARDIAN_PRESELECTION_CANCEL_FAILED_OR_UNCERTAIN",
                    exc,
                )
            )
    if not session.connection_close_attempted:
        try:
            _close_guardian_connection(session)
        except BaseException as exc:
            cleanup_errors.append(
                _failure(
                    "GUARDIAN_CONTROL_DROP_FAILED_OR_UNCERTAIN",
                    exc,
                )
            )
    elif not session.connection_close_returned:
        cleanup_errors.append(
            session.connection_close_error
            or _failure(
                "GUARDIAN_CONTROL_DROP_FAILED_OR_UNCERTAIN",
                "guardian connection close returned no canonical effect",
            )
        )
    shown = host.show(session.unit_name)
    if shown != closeout_helper.ABSENT:
        current = _guardian_unit_identity(
            host,
            unit_name=session.unit_name,
            shown=shown,
        )
        if current != session.unit_identity:
            _hold_locks_forever(
                host=host,
                reason="guardian identity drifted with an unvalidated selection",
            )
        if session.unit_name not in host.cleaned_units:
            cleanup_errors.extend(host.stop_reset_once(session.unit_name))
    while True:
        try:
            guardian_absence = _wait_guardian_absence(
                host,
                session,
                timeout_seconds=GUARDIAN_WAIT_SECONDS,
            )
            break
        except BaseException as exc:
            item = _failure("GUARDIAN_ABSENCE_WAIT_FAILED", exc)
            if item not in cleanup_errors:
                cleanup_errors.append(item)
            time.sleep(closeout_state.HOLD_POLL_SECONDS)
    if not state.attempt.directory_created:
        identities = host.lock_evidence()
        return {
            "guardian_absence_identity": "absent",
            "lock_identities": identities,
        }
    preselection_ledger = initial_ledger(
        _outer_inactive_identity(
            str(context["outer_spec"]["unit_name"])
        )
    )
    for item in cleanup_errors:
        if item not in state.attempt.errors:
            state.attempt.errors.append(item)
    final_observation = _wait_ledger_absence(
        host=host,
        ledger=preselection_ledger,
        attempt=state.attempt,
    )
    absence_record = {
        "authorizations": dict(FALSE_CLAIMS),
        "campaign_root_identity": context["campaign_root_identity"],
        "errors": cleanup_errors,
        "formal_selection_identity": "absent",
        "frozen_ledger_sha256": hashlib.sha256(
            authority.canonical_json(preselection_ledger)
        ).hexdigest(),
        "guardian_absence": guardian_absence,
        "guardian_identity": session.unit_identity,
        "lower_bound": "absent",
        "outcome": "INCOMPLETE",
        "package_id": context["package_id"],
        "production_certified": False,
        "schema_version": CONTAINMENT_GUARDIAN_ABSENCE_SCHEMA,
        "status": "GUARDIAN_ABSENT",
        "success_eligible": False,
        "upper_bound": [1188, 18],
    }
    guardian_absence_identity = store.publish(
        Path(str(context["formal_attempt_dir"]))
        / "containment-guardian-absence.json",
        absence_record,
        (
            "preselection guardian absence"
            if selection_absent
            else "invalid-selection guardian absence"
        ),
    )
    identities = host.lock_evidence()
    return {
        "final_observation": final_observation,
        "guardian_absence_identity": guardian_absence_identity,
        "ledger": preselection_ledger,
        "lock_identities": identities,
        "reference_terminal": {"kind": "NO_REFERENCE_OPENED"},
    }


def _early_selected_closeout(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    latch: closeout_helper.TerminationLatch,
    error: BaseException,
) -> dict[str, object]:
    phase = _failure_phase(state)
    if state.attempt.incomplete_identity is None:
        external: dict[str, object] = {}
        frozen_outer = _freeze_failure_outer(state=state, host=host)
        if phase in {
            "UNREF_FAILED_OR_UNCERTAIN",
            "UNREF_RETURNED_BUT_UNRECORDED",
            "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN",
            "CONNECTION_CLOSED_RELEASE_UNRECORDED",
            "POST_UNREF_ABSENCE_UNPROVED",
        }:
            external["frozen_outer_identity"] = frozen_outer
        incomplete = closeout_state.publish_consumed_incomplete(
            boundary,
            state.attempt,
            store,
            phase=phase,
            failure_record=_failure("FORMAL_CAMPAIGN_FAILED", error),
            external_joins=external,
        )
    else:
        incomplete = {"identity": state.attempt.incomplete_identity}
        frozen_outer = _freeze_failure_outer(state=state, host=host)

    ledger = initial_ledger(frozen_outer)
    owned = (
        [str(frozen_outer["unit_name"])]
        if frozen_outer["identity_complete"] is True
        and (
            frozen_outer["invocation_id"]
            or frozen_outer["control_group"]
            or frozen_outer["processes"]
        )
        else []
    )
    containment = closeout_helper.contain_frozen_ledger_once(
        host,
        ledger,
        owned_unit_names=owned,
    )
    for item in closeout_state.validate_failure_list(
        containment["errors"],
        "early selected containment",
    ):
        if item not in state.attempt.errors:
            state.attempt.errors.append(item)
    unit_name = str(frozen_outer["unit_name"])
    terminal = closeout_state.finalize_reference_once(
        boundary,
        state.attempt,
        store,
        unit_name=unit_name,
        prove_unref=state.attempt.acquire_identity is not None,
        reason="EARLY_SELECTED_FAILURE",
        observer_identity=state.observer_identity,
        pre_unref_cleanup_identity=state.pre_unref_identity,
    )
    state.reference_terminal = dict(terminal)
    if terminal.get("kind") in {
        "CONNECTION_DROP_FAILED_OR_UNCERTAIN",
        "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN",
    }:
        state.attempt.errors.append(
            _failure("REFERENCE_TERMINAL_UNCERTAIN", str(terminal))
        )
    observation = _wait_ledger_absence(
        host=host,
        ledger=ledger,
        attempt=state.attempt,
    )
    release_port = FailureContainmentPort(
        boundary=boundary,
        context=context,
        state=state,
        store=store,
        host=host,
        latch=latch,
    )
    lock_identities = host.lock_evidence()
    try:
        guardian_absence_identity = release_port.prepare_guardian_release(
            ledger
        )
    except BaseException as exc:
        _hold_locks_forever(host=host, reason=exc)
    failure_release_identity = _publish_failure_release(
        boundary=boundary,
        context=context,
        state=state,
        store=store,
        phase=phase,
        guardian_absence_identity=guardian_absence_identity,
        ledger=ledger,
        final_observation=observation,
        reference_terminal=terminal,
        lock_identities=lock_identities,
    )
    return {
        "containment": containment,
        "final_observation": observation,
        "guardian_absence_identity": guardian_absence_identity,
        "failure_release_identity": failure_release_identity,
        "incomplete_identity": incomplete["identity"],
        "lock_identities": lock_identities,
        "outcome": "INCOMPLETE",
        "phase": phase,
        "reference_terminal": terminal,
    }


def _post_barrier_closeout(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    latch: closeout_helper.TerminationLatch,
    error: BaseException,
) -> dict[str, object]:
    if state.selection is None or state.ledger is None:
        _hold_locks_forever(
            host=host,
            reason="post-barrier failure lacks its selected finite ledger",
        )
    if state.child_audit_identity is None:
        try:
            child = closeout_helper.audit_children(
                boundary,
                store,
                host,
                state.attempt.reference,
                state.selection,
                abnormal=True,
                expected_allowed_same_uid_processes=_formal_resource_allowlist(
                    state
                ),
                prior_launch_ledger=state.ledger,
            )
        except closeout_helper.ChildAuditPublicationError as exc:
            if exc.publication_effect.get("recorded") is not True:
                _hold_locks_forever(host=host, reason=exc)
            child = {
                "identity": exc.publication_effect["recorded_identity"],
                "ledger": exc.ledger,
                "record": exc.record,
            }
        bound_ledger = closeout_helper.bind_outer_ledger(
            child,
            _freeze_failure_outer(state=state, host=host),
        )
        state.child_audit_identity = child["identity"]
        state.ledger = bound_ledger
    outer = state.ledger["outer"]
    owned = (
        [str(outer["unit_name"])]
        if outer["identity_complete"] is True
        and (outer["invocation_id"] or outer["control_group"] or outer["processes"])
        else []
    )
    containment = closeout_helper.contain_frozen_ledger_once(
        host,
        state.ledger,
        owned_unit_names=owned,
    )
    for item in closeout_state.validate_failure_list(
        containment["errors"],
        "post-barrier containment",
    ):
        if item not in state.attempt.errors:
            state.attempt.errors.append(item)
    port = FailureContainmentPort(
        boundary=boundary,
        context=context,
        state=state,
        store=store,
        host=host,
        latch=latch,
    )
    coordinator = closeout_state.ContainmentHoldCoordinator(
        boundary,
        state.attempt,
        store,
        port,
        waiter=closeout_helper.SleepWaiter(),
        latch=latch,
    )
    phase = (
        "CONTAINMENT_HOLD"
        if state.attempt.barrier_identity is not None
        else "BARRIER_FAILED_OR_UNCERTAIN_CONTAINMENT_HOLD"
    )
    result = coordinator.enter(
        unit_name=str(outer["unit_name"]),
        failure_record=_failure("FORMAL_CAMPAIGN_FAILED", error),
        ledger=state.ledger,
        reference_reason="POST_BARRIER_CONTAINMENT",
        incomplete_phase=phase,
    )
    replay = result.get("detached_replay_input")
    if type(replay) is not dict:
        raise IrreversibleFormalFailure(
            "containment closeout lacks detached replay input"
        )
    state.reference_terminal = dict(
        replay["hold_record"]["reference_terminal"]
    )
    failure_release_identity = _publish_failure_release(
        boundary=boundary,
        context=context,
        state=state,
        store=store,
        phase=phase,
        guardian_absence_identity=replay["guardian_absence_identity"],
        ledger=state.ledger,
        final_observation=replay["clearance_record"][
            "final_observation"
        ],
        reference_terminal=state.reference_terminal,
        lock_identities=replay["lock_identities"],
        containment_hold_identity=replay["hold_identity"],
        containment_clearance_identity=replay["clearance_identity"],
    )
    return {
        **result,
        "failure_release_identity": failure_release_identity,
        "guardian_absence_identity": replay["guardian_absence_identity"],
        "lock_identities": replay["lock_identities"],
        "phase": phase,
    }


def _failure_reference_terminal(
    state: SupervisorState,
) -> dict[str, object]:
    if state.reference_terminal is not None:
        return closeout_state._validate_reference_terminal(  # noqa: SLF001
            state.reference_terminal
        )
    attempt = state.attempt
    if attempt.reference_release_identity is not None:
        return {
            "identity": closeout_state.validate_identity_join(
                attempt.reference_release_identity,
                "failure reference release",
            ),
            "kind": "RECORDED",
        }
    abort_effect = attempt.publications.get("reference-abort-close")
    if abort_effect is not None and abort_effect.recorded_identity is not None:
        return {
            "identity": closeout_state.validate_identity_join(
                abort_effect.recorded_identity,
                "failure reference abort",
            ),
            "kind": "UNREF_UNPROVEN_CONNECTION_DROPPED",
        }
    if attempt.connection_action == "close":
        kind = (
            "CONNECTION_CLOSED_RELEASE_UNRECORDED"
            if attempt.close_returned
            else "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN"
        )
    elif attempt.connection_action == "abort_close":
        kind = (
            "CONNECTION_DROPPED_RECEIPT_UNRECORDED"
            if attempt.abort_close_return is not None
            else "CONNECTION_DROP_FAILED_OR_UNCERTAIN"
        )
    elif attempt.reference is None:
        return {"kind": "NO_REFERENCE_OPENED"}
    else:
        kind = "REFERENCE_TERMINAL_FAILED_OR_UNCERTAIN"
    matching = next(
        (
            item
            for item in reversed(attempt.errors)
            if item["code"] == kind
            or (
                kind == "REFERENCE_TERMINAL_FAILED_OR_UNCERTAIN"
                and item["code"].startswith("UNREF_")
            )
        ),
        _failure(kind, "reference terminal effect lacks a canonical receipt"),
    )
    return closeout_state._validate_reference_terminal(  # noqa: SLF001
        {"failure": matching, "kind": kind}
    )


def _late_failure_closeout(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    latch: closeout_helper.TerminationLatch,
    error: BaseException,
) -> dict[str, object]:
    phase = _failure_phase(state)
    external: dict[str, object]
    if phase in {
        "GUARDIAN_CLOSE_NOT_ATTEMPTED",
        "GUARDIAN_CLOSE_FAILED_OR_UNCERTAIN",
        "GUARDIAN_ABSENCE_UNPROVED",
        "SUPERVISOR_LOCK_RELEASE_NOT_ATTEMPTED",
        "SUPERVISOR_LOCK_RELEASE_FAILED_OR_UNCERTAIN",
        "DUAL_LOCK_RELEASE_RECEIPT_NOT_ATTEMPTED",
        "DUAL_LOCK_RELEASE_RECEIPT_FAILED_OR_UNCERTAIN",
        "DETACHED_SUCCESS_VERIFIER_NOT_ATTEMPTED",
        "DETACHED_SUCCESS_VERIFIER_FAILED_OR_UNCERTAIN",
        "FINAL_SUCCESS_RETURN_FAILED_OR_UNCERTAIN",
    }:
        if (
            state.child_audit_identity is None
            or state.outer_terminal_identity is None
        ):
            raise IrreversibleFormalFailure(
                "late closeout lacks child/outer terminal joins"
            )
        external = {
            "child_audit_identity": state.child_audit_identity,
            "outer_terminal_identity": state.outer_terminal_identity,
        }
    else:
        external = {
            "frozen_outer_identity": _freeze_failure_outer(
                state=state,
                host=host,
            )
        }
    if host.locks_released:
        lock_identities = closeout_state._validate_lock_evidence(  # noqa: SLF001
            cast(
                Sequence[Mapping[str, object]],
                state.selection["lock_identities"],
            )
        )
        lock_release_effect = state.attempt.lock_release_return
        if (
            type(lock_release_effect) is not dict
            or state.detached_success_identity is None
        ):
            raise IrreversibleFormalFailure(
                "released late failure lacks its locks-held substantive replay"
            )
        terminal_predecessor: Mapping[str, object] | str = (
            state.dual_release_identity
            if state.dual_release_identity is not None
            else "unrecorded"
        )
        terminal_identity = _publish_failure_terminal_release(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            phase=phase,
            lock_identities=lock_identities,
            lock_release_effect=lock_release_effect,
            detached_substantive_identity=state.detached_success_identity,
            detached_substantive_kind="pre_release_success_v2",
            failure_pre_release_identity="absent",
            terminal_predecessor_identity=terminal_predecessor,
        )
        return {
            "failure_terminal_release_identity": terminal_identity,
            "outcome": "INCOMPLETE",
            "phase": phase,
            "post_release_terminal_only": True,
        }
    incomplete = closeout_state.publish_consumed_incomplete(
        boundary,
        state.attempt,
        store,
        phase=phase,
        failure_record=_failure("FORMAL_CAMPAIGN_FAILED", error),
        external_joins=external,
    )
    if state.ledger is None:
        state.ledger = initial_ledger(
            _freeze_failure_outer(state=state, host=host)
        )
    observation = _wait_ledger_absence(
        host=host,
        ledger=state.ledger,
        attempt=state.attempt,
    )
    terminal = _failure_reference_terminal(state)
    lock_identities = host.lock_evidence()
    if state.attempt.guardian_absence_identity is None:
        port = FailureContainmentPort(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            host=host,
            latch=latch,
        )
        try:
            guardian_absence = port.prepare_guardian_release(state.ledger)
        except BaseException as exc:
            _hold_locks_forever(host=host, reason=exc)
    else:
        guardian_absence = state.attempt.guardian_absence_identity
    if state.attempt.lock_release_attempted:
        _hold_locks_forever(
            host=host,
            reason="supervisor lock release was already attempted without a returned effect",
        )
    failure_release_identity = _publish_failure_release(
        boundary=boundary,
        context=context,
        state=state,
        store=store,
        phase=phase,
        guardian_absence_identity=guardian_absence,
        ledger=state.ledger,
        final_observation=observation,
        reference_terminal=terminal,
        lock_identities=lock_identities,
    )
    return {
        "failure_release_identity": failure_release_identity,
        "guardian_absence_identity": guardian_absence,
        "incomplete_identity": incomplete["identity"],
        "lock_identities": lock_identities,
        "outcome": "INCOMPLETE",
        "phase": phase,
    }


def _close_failed_campaign(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    admission_identity: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    latch: closeout_helper.TerminationLatch,
    error: BaseException,
) -> dict[str, object]:
    state.failure = _failure("FORMAL_CAMPAIGN_FAILED", error)
    if state.failure not in state.attempt.errors:
        state.attempt.errors.append(state.failure)
    barrier_effect = state.attempt.publications.get("outer-barrier")
    potentially_post_barrier = (
        state.attempt.barrier_identity is not None
        or (barrier_effect is not None and barrier_effect.attempted)
    )
    late_failure = (
        host.locks_released
        or state.attempt.release_attempted
        or state.attempt.guardian_close_attempted
        or state.attempt.lock_release_attempted
        or state.attempt.detached_success_verifier_attempted
    )
    result: dict[str, object]

    def checked_preselection(
        value: Mapping[str, object],
    ) -> tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
        dict[str, object],
        list[dict[str, object]],
    ]:
        guardian_absence = closeout_state.validate_identity_join(
            cast(Mapping[str, object], value["guardian_absence_identity"]),
            "preselection guardian absence",
        )
        ledger = closeout_state.validate_frozen_ledger(
            cast(Mapping[str, object], value["ledger"])
        )
        observation = closeout_state.validate_absence_observation(
            cast(Mapping[str, object], value["final_observation"]),
            ledger=ledger,
        )
        terminal = closeout_state._validate_reference_terminal(  # noqa: SLF001
            cast(Mapping[str, object], value["reference_terminal"])
        )
        locks = closeout_state._validate_lock_evidence(  # noqa: SLF001
            cast(Sequence[Mapping[str, object]], value["lock_identities"])
        )
        return guardian_absence, ledger, observation, terminal, locks

    if state.attempt.marker_identity is None:
        closed = _close_preselection(
            context=context,
            state=state,
            admission_identity=admission_identity,
            store=store,
            host=host,
        )
        result = {
            "outcome": "INCOMPLETE",
            "phase": "DIRECTORY_CREATED_MARKER_UNRECORDED"
            if state.attempt.directory_created
            else "ATTEMPT_DIRECTORY_NOT_CREATED",
        }
        if (
            not state.attempt.directory_created
            or closed["guardian_absence_identity"] == "absent"
        ):
            raise IrreversibleFormalFailure(
                "preselection failure lacks a durable root for locks-held replay"
            )
        guardian_absence, ledger, observation, terminal, locks = (
            checked_preselection(closed)
        )
        release_identity = _publish_failure_release(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            phase=str(result["phase"]),
            guardian_absence_identity=guardian_absence,
            ledger=ledger,
            final_observation=observation,
            reference_terminal=terminal,
            lock_identities=locks,
        )
        result["failure_release_identity"] = release_identity
        result.update(
            _complete_pre_release_failure(
                boundary=boundary,
                context=context,
                state=state,
                store=store,
                host=host,
                phase=str(result["phase"]),
                lock_identities=locks,
                guardian_absence_identity=guardian_absence,
                failure_pre_release_identity=release_identity,
            )
        )
        return result
    if state.selection_identity is None:
        if state.attempt.incomplete_identity is None:
            closeout_state.publish_consumed_incomplete(
                boundary,
                state.attempt,
                store,
                phase="ATTEMPT_RECORDED_SELECTION_UNRECORDED",
                failure_record=state.failure,
            )
        closed = _close_preselection(
            context=context,
            state=state,
            admission_identity=admission_identity,
            store=store,
            host=host,
        )
        guardian_absence, ledger, observation, terminal, locks = (
            checked_preselection(closed)
        )
        release_identity = _publish_failure_release(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            phase="ATTEMPT_RECORDED_SELECTION_UNRECORDED",
            guardian_absence_identity=guardian_absence,
            ledger=ledger,
            final_observation=observation,
            reference_terminal=terminal,
            lock_identities=locks,
        )
        result = {
            "failure_release_identity": release_identity,
            "outcome": "INCOMPLETE",
            "phase": "ATTEMPT_RECORDED_SELECTION_UNRECORDED",
        }
        result.update(
            _complete_pre_release_failure(
                boundary=boundary,
                context=context,
                state=state,
                store=store,
                host=host,
                phase=str(result["phase"]),
                lock_identities=locks,
                guardian_absence_identity=guardian_absence,
                failure_pre_release_identity=release_identity,
            )
        )
        return result
    if late_failure:
        result = _late_failure_closeout(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            host=host,
            latch=latch,
            error=error,
        )
    elif potentially_post_barrier:
        result = _post_barrier_closeout(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            host=host,
            latch=latch,
            error=error,
        )
    else:
        result = _early_selected_closeout(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            host=host,
            latch=latch,
            error=error,
        )
    if result.get("post_release_terminal_only") is True:
        return {
            **result,
            "formal_selection_identity": state.selection_identity,
            "outcome": "INCOMPLETE",
            "phase": str(result["phase"]),
        }
    if "failure_release_identity" not in result:
        raise IrreversibleFormalFailure(
            "consumed failure returned without a failure-release receipt"
        )
    selected_locks = closeout_state._validate_lock_evidence(  # noqa: SLF001
        cast(Sequence[Mapping[str, object]], result["lock_identities"])
    )
    selected_guardian_absence = closeout_state.validate_identity_join(
        cast(
            Mapping[str, object],
            result["guardian_absence_identity"],
        ),
        "selected failure guardian absence",
    )
    selected_failure_release = closeout_state.validate_identity_join(
        cast(Mapping[str, object], result["failure_release_identity"]),
        "selected pre-release failure",
    )
    result.update(
        _complete_pre_release_failure(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            host=host,
            phase=str(result["phase"]),
            lock_identities=selected_locks,
            guardian_absence_identity=selected_guardian_absence,
            failure_pre_release_identity=selected_failure_release,
        )
    )
    return {
        **result,
        "formal_selection_identity": state.selection_identity,
        "outcome": "INCOMPLETE",
        "phase": str(result["phase"]),
    }


def run_formal_campaign(campaign_dir: Path | str) -> dict[str, object]:
    """Consume exactly one externally selected formal AB16 campaign."""

    boundary, context, admission, admission_identity = load_formal_admission(
        campaign_dir
    )
    held_locks = acquire_formal_locks()
    host = closeout_helper.PinnedHost(boundary, held_locks)
    try:
        initial_lock_identities = host.lock_evidence()
        resource_gate = validate_resource_gate(
            context["campaign_dir"],
            lock_identities=initial_lock_identities,
            observation_context=_resource_observation_context(
                context,
                authority_identity=admission_identity,
                kind="FORMAL_INITIAL_POST_LOCK",
                target=str(context["formal_attempt_dir"]),
            ),
            allowed_same_uid_processes=[_process_identity(os.getpid())],
        )
        if host.lock_evidence() != initial_lock_identities:
            raise FormalCampaignError(
                "formal lock identities drifted across initial resource admission"
            )
    except BaseException as exc:
        try:
            host.release_locks_once()
        except BaseException as cleanup_error:
            exc.add_note(
                "formal post-lock resource admission cleanup failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
        raise
    store = closeout_helper.ReceiptStore()
    state = SupervisorState()
    latch = closeout_helper.TerminationLatch()
    try:
        latch.install()
    except BaseException:
        host.release_locks_once()
        raise
    try:
        try:
            _supervisor_checkpoint(state, host, latch)
            state.guardian = start_guardian(
                boundary=boundary,
                context=context,
                admission=admission,
                admission_identity=admission_identity,
                resource_admission_receipt=resource_gate,
                host=host,
                store=store,
            )
            _supervisor_checkpoint(state, host, latch)
            marker, marker_identity = _create_consumed_attempt(
                boundary=boundary,
                context=context,
                state=state,
                store=store,
            )
            _supervisor_checkpoint(state, host, latch)
            selection, selection_identity = wait_and_validate_selection(
                context=context,
                admission=admission,
                admission_identity=admission_identity,
                guardian_session=state.guardian,
                marker=marker,
                marker_identity=marker_identity,
                checkpoint=lambda: _supervisor_checkpoint(
                    state,
                    host,
                    latch,
                ),
            )
            state.selection = selection
            state.selection_identity = selection_identity
            state.attempt.selection_identity = selection_identity
            if selection["lock_identities"] != host.lock_evidence():
                raise IrreversibleFormalFailure(
                    "formal selection lock identities drifted"
                )
            _supervisor_checkpoint(state, host, latch)
            activate_guardian(
                state.guardian,
                context=context,
                selection_identity=selection_identity,
            )
            _supervisor_checkpoint(state, host, latch)
            _publish_outer_prelaunch(
                context=context,
                state=state,
                store=store,
                host=host,
            )
            _supervisor_checkpoint(state, host, latch)
            _launch_outer(
                boundary=boundary,
                context=context,
                state=state,
                store=store,
                host=host,
            )
            _supervisor_checkpoint(state, host, latch)
            _acquire_outer_reference(
                boundary=boundary,
                state=state,
                store=store,
                host=host,
            )
            _supervisor_checkpoint(state, host, latch)
            controller, controller_identity = _service_fixed_campaign(
                boundary=boundary,
                context=context,
                state=state,
                store=store,
                host=host,
                latch=latch,
            )
            state.controller_identity = controller_identity
            _publish_normal_closeout(
                boundary=boundary,
                context=context,
                state=state,
                store=store,
                host=host,
                latch=latch,
                controller_identity=controller_identity,
            )
            _normal_closeout_checkpoint(
                state,
                latch,
                phase="detached substantive success verifier launch",
            )
            detached = _run_detached_success(
                context=context,
                state=state,
                store=store,
                host=host,
            )
            _normal_closeout_checkpoint(
                state,
                latch,
                phase="guardian and supervisor lock release after detached replay",
            )
            terminal = _release_guardian_and_locks(
                context=context,
                state=state,
                store=store,
                host=host,
                latch=latch,
                expected=_normal_expected(
                    context,
                    selection_identity,
                ),
            )
        except BaseException as exc:
            if isinstance(exc, GuardianLaunchFailure):
                if not exc.containment_cleared:
                    _hold_locks_forever(host=host, reason=exc)
                _hold_locks_forever(
                    host=host,
                    reason=(
                        "guardian launch failed before a durable attempt root; "
                        "lock release has no locks-held detached replay"
                    ),
                )
            try:
                closeout = _close_failed_campaign(
                    boundary=boundary,
                    context=context,
                    admission_identity=admission_identity,
                    state=state,
                    store=store,
                    host=host,
                    latch=latch,
                    error=exc,
                )
            except BaseException as closeout_error:
                if not host.locks_released:
                    _hold_locks_forever(
                        host=host,
                        reason=(
                            "formal failure closeout failed or is uncertain: "
                            f"{type(closeout_error).__name__}: {closeout_error}"
                        ),
                    )
                raise
            return {
                **closeout,
                "failure": _failure("FORMAL_CAMPAIGN_FAILED", exc),
                "resource_gate": resource_gate,
            }
        if not host.locks_released:
            raise IrreversibleFormalFailure(
                "success returned before the supervisor released its locks"
            )
        _post_release_signal_checkpoint(
            latch,
            phase="VERIFIED supervisor return",
        )
        return {
            **detached,
            **terminal,
            "controller_result_identity": controller_identity,
            "formal_selection_identity": selection_identity,
            "outcome": "VERIFIED",
            "resource_gate": resource_gate,
            "status": "VERIFIED",
        }
    finally:
        if host.locks_released:
            latch.restore()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = run_formal_campaign(arguments.campaign_dir)
    except BaseException as exc:
        print(
            f"FAIL_CLOSED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return 125
    print(authority.canonical_json(result).decode("utf-8"), flush=True)
    return 0 if result["outcome"] == "VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
