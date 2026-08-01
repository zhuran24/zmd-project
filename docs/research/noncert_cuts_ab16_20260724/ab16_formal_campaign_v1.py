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
import select
import selectors
import signal
import socket
import stat
import struct
import sys
import time
from typing import Any, cast, Protocol

from docs.research.noncert_cuts_ab16_20260724 import ab16_authority_v2 as authority
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_budget_broker_v1 as budget_broker,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_controller_v1 as formal_controller,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_closure_actor_v1 as closure_actor,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_final_release_actor_v1 as final_release_actor,
)
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
from docs.research.noncert_cuts_ab16_20260724 import (
    replay_ab16_formal_root_alt_v1 as formal_root_replay_alternate,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    replay_ab16_formal_root_v1 as formal_root_replay_primary,
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
MAX_FORMAL_SUPERVISOR_SESSION_BYTES = 64 * 1024
FORMAL_SUPERVISOR_SESSION_FD = 10
FORMAL_SUPERVISOR_SESSION_SCHEMA = (
    "noncert-cuts-ab16-formal-supervisor-session-v1"
)
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SELECTED_ROLES_V1 = ("python", "loader", "authority")
_SELECTED_ROLES_V2 = (
    "python",
    "loader",
    "authority",
    "native_helper_wrapper",
    "native_helper",
)
_SELECTED_OPENFILE_NAMES_V2 = {
    "authority": "ab16-authority",
    "loader": "ab16-loader",
    "native_helper": "ab16-native-helper",
    "native_helper_wrapper": "ab16-native-helper-wrapper",
    "python": "ab16-python",
}
_BUDGET_BROKER_OPENFILE_NAME = "ab16-budget-broker"
CONTAINMENT_GUARDIAN_ABSENCE_SCHEMA = (
    "noncert-cuts-ab16-containment-guardian-absence-v1"
)
FAILURE_RELEASE_SCHEMA = "noncert-cuts-ab16-formal-pre-release-failure-v4"
FAILURE_TERMINAL_RELEASE_SCHEMA = (
    "noncert-cuts-ab16-formal-failure-terminal-release-v5"
)
FINAL_RELEASE_RESULT_SCHEMA = "noncert-cuts-ab16-final-release-result-v1"
PRIMARY_FORMAL_ROOT_REPLAY_SCHEMA = (
    "noncert-cuts-ab16-formal-root-outside-replay-primary-v1"
)
ALTERNATE_FORMAL_ROOT_REPLAY_SCHEMA = (
    "noncert-cuts-ab16-formal-root-outside-replay-alternate-v1"
)
FINAL_TERMINAL_PREDECESSOR_JOIN_SCHEMA = (
    "noncert-cuts-ab16-final-terminal-predecessor-join-v1"
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


class FormalTerminalTailPort(Protocol):
    """Package-pinned capabilities for the fixed post-RefUnit closure tail."""

    def bind_closure_process_baseline(
        self,
        resource_admission_receipt: Mapping[str, object],
    ) -> Mapping[str, object]: ...

    def prepare_closure(
        self,
        *,
        branch: str,
        terminal_join_sha256: str,
    ) -> Mapping[str, object]: ...

    def publish_disarm_intent(
        self,
        *,
        terminal_join_sha256: str,
    ) -> Mapping[str, object]: ...

    def disarm_recovery_once(
        self,
        *,
        disarm_intent: Mapping[str, object],
    ) -> Mapping[str, object]: ...

    def prove_recovery_absence(
        self,
        *,
        disarm_observation: Mapping[str, object],
    ) -> Mapping[str, object]: ...

    def retire_broker_once(
        self,
        *,
        recovery_absence: Mapping[str, object],
    ) -> Mapping[str, object]: ...

    def close_root_once(
        self,
        *,
        broker_absence: Mapping[str, object],
        terminal_join_sha256: str,
    ) -> Mapping[str, object]: ...

    def replay_closed_root(
        self,
        *,
        implementation: str,
    ) -> Mapping[str, object]: ...

    def publish_final_release(
        self,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]: ...

    def prove_final_release_absence(
        self,
        *,
        final_release_result: Mapping[str, object],
    ) -> Mapping[str, object]: ...


class FormalSelectionTransitionPort(Protocol):
    """Irreversible phase transition on the same preregistered broker session."""

    def bind_formal_selection(
        self,
        selection_identity: Mapping[str, object],
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class FormalSupervisorCapabilities:
    """Package-pinned writable capabilities admitted by the selected loader."""

    budget_backend: object
    receipt_budget_bindings: Mapping[str, Mapping[str, object]]
    selection_transition: FormalSelectionTransitionPort
    terminal_tail_port: FormalTerminalTailPort


class FormalLaunchClaimantRegistrar(Protocol):
    """Pidfd-bound bootstrap-admin surface used before selected-child release."""

    def register_formal_launch_claimant(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
    ) -> object: ...

    def register_formal_supervisor(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
    ) -> Mapping[str, object]: ...


def _validate_formal_supervisor_capabilities(
    value: object,
) -> FormalSupervisorCapabilities:
    if type(value) is not FormalSupervisorCapabilities:
        raise FormalCampaignError(
            "formal supervisor lacks its package-pinned capability bundle"
        )
    capabilities = cast(FormalSupervisorCapabilities, value)
    backend = capabilities.budget_backend
    if not all(
        callable(getattr(backend, method, None))
        for method in ("maximum_bytes", "publish_bytes")
    ):
        raise FormalCampaignError(
            "formal supervisor budget backend surface drifted"
        )
    bindings: dict[str, dict[str, object]] = {}
    for raw_path, raw_binding in capabilities.receipt_budget_bindings.items():
        path = Path(raw_path)
        if (
            type(raw_path) is not str
            or not path.is_absolute()
            or str(path) != str(path.absolute())
            or type(raw_binding) is not dict
            or set(raw_binding) != {"artifact_class", "label"}
            or type(raw_binding["artifact_class"]) is not str
            or not raw_binding["artifact_class"]
            or type(raw_binding["label"]) is not str
            or not raw_binding["label"]
        ):
            raise FormalCampaignError(
                "formal supervisor receipt budget binding drifted"
            )
        bindings[raw_path] = dict(raw_binding)
    if not bindings:
        raise FormalCampaignError(
            "formal supervisor receipt budget bindings are empty"
        )
    transition = capabilities.selection_transition
    if not callable(getattr(transition, "bind_formal_selection", None)):
        raise FormalCampaignError(
            "formal supervisor selection transition capability drifted"
        )
    tail = capabilities.terminal_tail_port
    if not all(
        callable(getattr(tail, method, None))
        for method in (
            "prepare_closure",
            "bind_closure_process_baseline",
            "publish_disarm_intent",
            "disarm_recovery_once",
            "prove_recovery_absence",
            "retire_broker_once",
            "close_root_once",
            "replay_closed_root",
            "publish_final_release",
            "prove_final_release_absence",
        )
    ):
        raise FormalCampaignError(
            "formal supervisor terminal-tail capability surface drifted"
        )
    return FormalSupervisorCapabilities(
        budget_backend=backend,
        receipt_budget_bindings=bindings,
        selection_transition=transition,
        terminal_tail_port=tail,
    )


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
    guardian_absence_identity: dict[str, object] | None = None
    supervisor_raw_lock_release_identity: dict[str, object] | None = None
    reference_connection_close_identity: dict[str, object] | None = None
    terminal_tail_port: FormalTerminalTailPort | None = None
    post_root_closure: dict[str, object] | None = None
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


def _prospective_resource_authority(
    authority_context: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    profile_identity = authority_context.get(
        "resource_budget_profile_identity"
    )
    bundles = authority_context.get(
        "resource_calibration_authorization_bundles"
    )
    calibration_tools = authority_context.get(
        "calibration_tool_content_identities"
    )
    if (
        type(profile_identity) is not dict
        or set(profile_identity)
        != {"mode", "path", "sha256", "size_bytes"}
        or type(bundles) is not dict
        or type(bundles.get(resource_admission.FORMAL_ORGANIC_ARM))
        is not dict
        or type(calibration_tools) is not dict
        or set(calibration_tools)
        != resource_admission.CALIBRATION_TOOL_ROLES
    ):
        raise FormalCampaignError(
            "formal resource admission lacks its exact prospective authority"
        )
    bundle_entry = bundles[resource_admission.FORMAL_ORGANIC_ARM]
    if (
        set(bundle_entry) != {"identity", "record"}
        or type(bundle_entry["identity"]) is not dict
        or type(bundle_entry["record"]) is not dict
    ):
        raise FormalCampaignError(
            "formal resource calibration bundle is malformed"
        )
    profile_expected_identity = {
        key: profile_identity[key]
        for key in ("path", "sha256", "size_bytes")
    }
    if profile_identity["mode"] != 0o444:
        raise FormalCampaignError(
            "formal resource budget profile is not readonly"
        )
    profile, observed_profile_identity = _read_record(
        cast(str, profile_identity["path"]),
        expected_identity=profile_expected_identity,
        label="formal resource budget profile",
    )
    if observed_profile_identity != profile_expected_identity:
        raise FormalCampaignError(
            "formal resource budget profile identity drifted"
        )
    return {
        "calibration_authorization_bundle": dict(
            bundle_entry["record"]
        ),
        "calibration_authorization_bundle_identity": dict(
            bundle_entry["identity"]
        ),
        "enforced_budget_profile": profile,
        # The retained authority identity additionally binds the readonly
        # mode.  Resource-profile replay has its own exact byte-identity shape
        # and must not receive that transport-only field.
        "enforced_budget_profile_identity": profile_expected_identity,
        "expected_calibration_tool_identities": {
            role: dict(identity)
            for role, identity in sorted(calibration_tools.items())
        },
    }


def validate_resource_gate(
    campaign_dir: Path | str,
    *,
    authority_context: Mapping[str, object],
    lock_identities: Sequence[Mapping[str, object]],
    observation_context: Mapping[str, object],
    meminfo: Mapping[str, int] | None = None,
    disk_free: int | None = None,
    conflicts: Sequence[Mapping[str, object]] | None = None,
    allowed_same_uid_processes: Sequence[Mapping[str, int]] = (),
) -> dict[str, object]:
    """Validate one post-lock formal admission and return its strict receipt."""

    prospective = _prospective_resource_authority(
        authority_context
    )
    try:
        return resource_admission.evaluate_prospective_resource_admission(
            campaign_dir,
            stage=resource_admission.FORMAL_ORGANIC_ARM,
            lock_identities=lock_identities,
            lock_identity_format=resource_admission.FORMAL_LOCK_IDENTITY_FORMAT,
            observation_context=observation_context,
            **prospective,
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
        raise FormalCampaignError("selected-byte argv is not a fixed selected-FD form")
    try:
        parsed = json.loads(argv[6])
    except (TypeError, json.JSONDecodeError) as exc:
        raise FormalCampaignError("selected-byte identity JSON is malformed") from exc
    if type(parsed) is not dict or frozenset(parsed) not in {
        frozenset(_SELECTED_ROLES_V1),
        frozenset(_SELECTED_ROLES_V2),
    }:
        raise FormalCampaignError("selected-byte identity field set drifted")
    result: dict[str, dict[str, object]] = {}
    ordered_roles = (
        _SELECTED_ROLES_V2
        if set(parsed) == set(_SELECTED_ROLES_V2)
        else _SELECTED_ROLES_V1
    )
    for name in ordered_roles:
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


def _selected_transport(
    spec: Mapping[str, object],
    identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object] | None:
    """Close the v2 retained-source and broker endpoint transport.

    Historical selected-byte v1 specs have exactly three regular identities
    and no transport extension.  Prospective v2 specs must bind all five
    regular package members to the persistent broker owner's retained
    ``/proc/<pid>/fd/<n>`` aliases and bind FD8 to that same owner's broker
    endpoint.  Cross-cohort mixtures fail closed.
    """

    if set(identities) == set(_SELECTED_ROLES_V1):
        if (
            "selected_fd_transport" in spec
            or "budget_broker_endpoint_identity" in spec
        ):
            raise FormalCampaignError(
                "historical selected-byte spec mixed prospective transport"
            )
        return None
    if set(identities) != set(_SELECTED_ROLES_V2):
        raise FormalCampaignError("selected-byte transport cohort is unsupported")
    transport = spec.get("selected_fd_transport")
    endpoint = spec.get("budget_broker_endpoint_identity")
    if (
        type(transport) is not dict
        or set(transport) != {"owner", "roles", "schema_version"}
        or transport.get("schema_version")
        != launch_validator.SELECTED_FD_TRANSPORT_SCHEMA
        or type(endpoint) is not dict
        or set(endpoint) != {"device", "inode", "mode", "path", "uid"}
    ):
        raise FormalCampaignError(
            "prospective selected-byte transport is absent or malformed"
        )
    owner = transport["owner"]
    roles = transport["roles"]
    if (
        type(owner) is not dict
        or set(owner) != {"pid", "pid_starttime", "uid"}
        or any(
            type(owner[field]) is not int
            or isinstance(owner[field], bool)
            for field in ("pid", "pid_starttime", "uid")
        )
        or owner["pid"] <= 0
        or owner["pid_starttime"] <= 0
        or owner["uid"] < 0
        or type(roles) is not dict
        or set(roles) != set(_SELECTED_ROLES_V2)
    ):
        raise FormalCampaignError(
            "prospective selected-byte transport owner/role set drifted"
        )
    checked_roles: dict[str, dict[str, object]] = {}
    for role in _SELECTED_ROLES_V2:
        item = roles[role]
        expected = identities[role]
        package_path = launch_validator.SELECTED_FD_TRANSPORT_PACKAGE_PATHS[role]
        if type(item) is not dict or set(item) != {
            "descriptor",
            "mode",
            "package_path",
            "proc_fd_path",
            "sha256",
            "size_bytes",
        }:
            raise FormalCampaignError(
                f"prospective selected-byte transport {role} is malformed"
            )
        descriptor = item["descriptor"]
        if (
            type(descriptor) is not int
            or isinstance(descriptor, bool)
            or descriptor < 3
            or item["mode"] != expected["mode"]
            or item["package_path"] != package_path
            or item["proc_fd_path"]
            != f"/proc/{owner['pid']}/fd/{descriptor}"
            or item["sha256"] != expected["sha256"]
            or item["size_bytes"] != expected["size_bytes"]
        ):
            raise FormalCampaignError(
                f"prospective selected-byte transport {role} identity drifted"
            )
        checked_roles[role] = dict(item)
    if (
        type(endpoint["device"]) is not int
        or isinstance(endpoint["device"], bool)
        or endpoint["device"] < 0
        or type(endpoint["inode"]) is not int
        or isinstance(endpoint["inode"], bool)
        or endpoint["inode"] <= 0
        or endpoint["mode"] != 0o600
        or type(endpoint["path"]) is not str
        or not Path(endpoint["path"]).is_absolute()
        or type(endpoint["uid"]) is not int
        or isinstance(endpoint["uid"], bool)
        or endpoint["uid"] != owner["uid"]
    ):
        raise FormalCampaignError(
            "prospective selected-byte broker endpoint identity drifted"
        )
    return {
        "endpoint": dict(endpoint),
        "owner": dict(owner),
        "roles": checked_roles,
        "schema_version": transport["schema_version"],
    }


def _require_selected_transport_live(transport: Mapping[str, object]) -> None:
    owner = cast(Mapping[str, object], transport["owner"])
    endpoint = cast(Mapping[str, object], transport["endpoint"])
    try:
        if guardian.read_process_starttime(cast(int, owner["pid"])) != owner[
            "pid_starttime"
        ]:
            raise FormalCampaignError(
                "prospective selected-byte transport owner identity drifted"
            )
        observed = os.stat(cast(str, endpoint["path"]), follow_symlinks=False)
    except OSError as exc:
        raise FormalCampaignError(
            "prospective selected-byte broker endpoint is unavailable"
        ) from exc
    if (
        not stat.S_ISSOCK(observed.st_mode)
        or observed.st_dev != endpoint["device"]
        or observed.st_ino != endpoint["inode"]
        or stat.S_IMODE(observed.st_mode) != endpoint["mode"]
        or observed.st_uid != endpoint["uid"]
    ):
        raise FormalCampaignError(
            "prospective selected-byte broker endpoint live identity drifted"
        )
    roles = cast(
        Mapping[str, Mapping[str, object]],
        transport["roles"],
    )
    for role in _SELECTED_ROLES_V2:
        item = roles[role]
        try:
            descriptor = os.open(
                cast(str, item["proc_fd_path"]),
                os.O_RDONLY | os.O_CLOEXEC,
            )
        except OSError as exc:
            raise FormalCampaignError(
                f"selected-FD retained {role} is unavailable"
            ) from exc
        primary: BaseException | None = None
        try:
            before = os.fstat(descriptor)
            digest = hashlib.sha256()
            offset = 0
            while offset < before.st_size:
                block = os.pread(
                    descriptor,
                    min(1 << 20, before.st_size - offset),
                    offset,
                )
                if not block:
                    raise FormalCampaignError(
                        f"selected-FD retained {role} ended early"
                    )
                digest.update(block)
                offset += len(block)
            after = os.fstat(descriptor)
            signature_fields = (
                "st_dev",
                "st_ino",
                "st_mode",
                "st_nlink",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
            )
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or stat.S_IMODE(before.st_mode) != item["mode"]
                or before.st_size != item["size_bytes"]
                or digest.hexdigest() != item["sha256"]
                or any(
                    getattr(before, field) != getattr(after, field)
                    for field in signature_fields
                )
            ):
                raise FormalCampaignError(
                    f"selected-FD retained {role} identity drifted"
                )
        except BaseException as exc:
            primary = exc
            raise
        finally:
            try:
                os.close(descriptor)
            except BaseException as cleanup_exc:
                if primary is not None:
                    primary.add_note(
                        f"selected-FD retained {role} cleanup failed: "
                        f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                    )
                else:
                    raise


def build_selected_systemd_argv(
    *,
    systemd_run_path: str,
    spec: Mapping[str, object],
) -> list[str]:
    """Build the exact systemd-run argv around an authority-validated spec."""

    if type(systemd_run_path) is not str or not Path(systemd_run_path).is_absolute():
        raise FormalCampaignError("pinned systemd-run path is malformed")
    identities = _selected_identities(spec)
    transport = _selected_transport(spec, identities)
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
    open_file_properties: list[str]
    if transport is None:
        open_file_properties = [
            f"--property=OpenFile={identities['python']['path']}:ab16-python:read-only",
            f"--property=OpenFile={identities['loader']['path']}:ab16-loader:read-only",
            f"--property=OpenFile={identities['authority']['path']}:ab16-authority:read-only",
        ]
    else:
        _require_selected_transport_live(transport)
        transport_roles = cast(
            Mapping[str, Mapping[str, object]],
            transport["roles"],
        )
        open_file_properties = [
            (
                "--property=OpenFile="
                f"{transport_roles[role]['proc_fd_path']}:"
                f"{_SELECTED_OPENFILE_NAMES_V2[role]}:read-only"
            )
            for role in _SELECTED_ROLES_V2
        ]
        endpoint = cast(Mapping[str, object], transport["endpoint"])
        open_file_properties.append(
            "--property=OpenFile="
            f"{endpoint['path']}:{_BUDGET_BROKER_OPENFILE_NAME}"
        )
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
        "--property=StandardInput=null",
        "--property=StandardOutput=journal",
        "--property=StandardError=journal",
        *open_file_properties,
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


def _connect_selected_broker(transport: Mapping[str, object]) -> int:
    """Connect FD8 without authenticating or minting broker authority."""

    _require_selected_transport_live(transport)
    endpoint = cast(Mapping[str, object], transport["endpoint"])
    owner = cast(Mapping[str, object], transport["owner"])
    connection = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    primary: BaseException | None = None
    try:
        connection.connect(cast(str, endpoint["path"]))
        metadata = os.fstat(connection.fileno())
        peer_raw = connection.getsockopt(
            socket.SOL_SOCKET,
            socket.SO_PEERCRED,
            struct.calcsize("3i"),
        )
        peer_pid, peer_uid, _peer_gid = struct.unpack("3i", peer_raw)
        if (
            not stat.S_ISSOCK(metadata.st_mode)
            or peer_pid != owner["pid"]
            or peer_uid != owner["uid"]
            or guardian.read_process_starttime(peer_pid)
            != owner["pid_starttime"]
        ):
            raise FormalCampaignError(
                "prospective selected-byte broker peer identity drifted"
            )
        _require_selected_transport_live(transport)
        return connection.detach()
    except BaseException as exc:
        primary = exc
        raise
    finally:
        if connection.fileno() >= 0:
            try:
                connection.close()
            except BaseException as cleanup_exc:
                if primary is not None:
                    primary.add_note(
                        "selected broker connection cleanup failed: "
                        f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                    )
                else:
                    raise


def run_selected_direct_result(
    *,
    context: Mapping[str, object],
    role: str,
    role_argv: Sequence[str],
    timeout_seconds: float,
    cancel_requested: Callable[[], bool] | None = None,
    formal_launch_claim_descriptor: int | None = None,
    formal_launch_claim_identity: Mapping[str, object] | None = None,
    formal_launch_claimant_registrar: (
        FormalLaunchClaimantRegistrar | None
    ) = None,
) -> SelectedDirectResult:
    """Run one fresh selected role through its exact selected-FD cohort.

    The embedded selected-byte literal remains the first executing trust
    primitive.  This function only opens the already-authorized bytes and
    arranges their fixed descriptors.  Prospective nonbudget roles receive an
    unauthenticated broker connection on FD8 solely so the v2 literal can close
    the exact six-FD transport; the selected loader closes it before invoking
    the role.
    """

    outer_spec = context["outer_spec"]
    identities = _selected_identities(outer_spec)
    transport = _selected_transport(outer_spec, identities)
    selected = outer_spec["selected_byte_argv"]
    requires_child_bound_broker = role in {
        "formal-orchestrator",
        "formal-supervisor",
    }
    if role == "formal-orchestrator":
        if (
            type(formal_launch_claim_descriptor) is not int
            or formal_launch_claim_descriptor < 3
            or type(formal_launch_claim_identity) is not dict
            or formal_launch_claimant_registrar is None
            or not callable(
                getattr(
                    formal_launch_claimant_registrar,
                    "register_formal_launch_claimant",
                    None,
                )
            )
        ):
            raise FormalCampaignError(
                "formal orchestrator lacks its sealed claim and pidfd registrar"
            )
        claim_argument = json.dumps(
            dict(formal_launch_claim_identity),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        claim_argv = [
            "--formal-launch-claim-fd",
            "9",
            "--formal-launch-claim-identity",
            claim_argument,
        ]
    elif role == "formal-supervisor":
        if (
            formal_launch_claim_descriptor is not None
            or formal_launch_claim_identity is not None
            or formal_launch_claimant_registrar is None
            or not callable(
                getattr(
                    formal_launch_claimant_registrar,
                    "register_formal_supervisor",
                    None,
                )
            )
        ):
            raise FormalCampaignError(
                "formal supervisor lacks its pidfd-bound session registrar"
            )
        claim_argv = [
            "--formal-supervisor-session-fd",
            str(FORMAL_SUPERVISOR_SESSION_FD),
        ]
    else:
        if (
            formal_launch_claim_descriptor is not None
            or formal_launch_claim_identity is not None
            or formal_launch_claimant_registrar is not None
        ):
            raise FormalCampaignError(
                "non-orchestrator role received a formal-launch claim"
            )
        claim_argv = []
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
        *claim_argv,
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
    child_ready_read = -1
    child_ready_write = -1
    child_release_read = -1
    child_release_write = -1
    supervisor_session_read = -1
    supervisor_session_write = -1
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
        selected_files = [
            (3, identities["python"], "Python"),
            (4, identities["loader"], "loader"),
            (5, identities["authority"], "authority"),
        ]
        if transport is not None:
            selected_files.extend(
                (
                    (
                        6,
                        identities["native_helper_wrapper"],
                        "native helper wrapper",
                    ),
                    (7, identities["native_helper"], "native helper"),
                )
            )
        for target, identity, label in selected_files:
            opened[target] = own_descriptor(_open_selected(identity, label))
        if transport is not None and not requires_child_bound_broker:
            opened[8] = own_descriptor(
                _connect_selected_broker(transport)
            )
        if role == "formal-orchestrator":
            assert formal_launch_claim_descriptor is not None
            opened[9] = own_descriptor(
                os.dup(formal_launch_claim_descriptor)
            )
        stdout_read, stdout_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
        pipes.update((own_descriptor(stdout_read), own_descriptor(stdout_write)))
        stderr_read, stderr_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
        pipes.update((own_descriptor(stderr_read), own_descriptor(stderr_write)))
        for target, source in opened.items():
            high[target] = own_descriptor(
                fcntl.fcntl(source, fcntl.F_DUPFD_CLOEXEC, 20)
            )
        if requires_child_bound_broker:
            assert transport is not None
            assert formal_launch_claimant_registrar is not None
            child_ready_read, child_ready_write = (
                own_descriptor(descriptor)
                for descriptor in os.pipe2(os.O_CLOEXEC)
            )
            child_release_read, child_release_write = (
                own_descriptor(descriptor)
                for descriptor in os.pipe2(os.O_CLOEXEC)
            )
            if role == "formal-supervisor":
                supervisor_session_read, supervisor_session_write = (
                    own_descriptor(descriptor)
                    for descriptor in os.pipe2(os.O_CLOEXEC)
                )
            pid = os.fork()
            if pid == 0:
                try:
                    os.close(child_ready_read)
                    os.close(child_release_write)
                    if supervisor_session_write >= 0:
                        os.close(supervisor_session_write)
                    for target, source in high.items():
                        os.dup2(source, target, inheritable=True)
                    os.dup2(stdout_write, 1, inheritable=True)
                    os.dup2(stderr_write, 2, inheritable=True)
                    os.close(stdout_read)
                    os.close(stderr_read)
                    broker_descriptor = _connect_selected_broker(transport)
                    try:
                        os.dup2(
                            broker_descriptor,
                            8,
                            inheritable=True,
                        )
                    finally:
                        if broker_descriptor != 8:
                            os.close(broker_descriptor)
                    if role == "formal-supervisor":
                        os.dup2(
                            supervisor_session_read,
                            FORMAL_SUPERVISOR_SESSION_FD,
                            inheritable=True,
                        )
                        if (
                            supervisor_session_read
                            != FORMAL_SUPERVISOR_SESSION_FD
                        ):
                            os.close(supervisor_session_read)
                    if os.write(child_ready_write, b"1") != 1:
                        os._exit(126)
                    os.close(child_ready_write)
                    while True:
                        try:
                            release = os.read(child_release_read, 1)
                            break
                        except InterruptedError:
                            continue
                    os.close(child_release_read)
                    if release != b"1":
                        os._exit(126)
                    os.execve("/proc/self/fd/3", command, {})
                except BaseException:
                    os._exit(126)
            ready_write_error = close_owned(child_ready_write)
            child_ready_write = -1
            release_read_error = close_owned(child_release_read)
            child_release_read = -1
            supervisor_read_error = close_owned(
                supervisor_session_read
            )
            supervisor_session_read = -1
            if ready_write_error is not None:
                raise ready_write_error
            if release_read_error is not None:
                raise release_read_error
            if supervisor_read_error is not None:
                raise supervisor_read_error
            ready = os.read(child_ready_read, 1)
            ready_read_error = close_owned(child_ready_read)
            child_ready_read = -1
            if ready_read_error is not None:
                raise ready_read_error
            if ready != b"1":
                raise FormalCampaignError(
                    "selected formal orchestrator failed before preregistration"
                )
            pidfd, pidfd_method = budget_broker.open_pidfd(pid)
            try:
                expected_peer = {
                    "pid": pid,
                    "pid_starttime": guardian.read_process_starttime(pid),
                    "uid": os.getuid(),
                }
                if pidfd_method not in {
                    "python-os.pidfd_open",
                    "libc-pidfd_open",
                }:
                    raise FormalCampaignError(
                        "selected formal orchestrator pidfd source drifted"
                    )
                if role == "formal-orchestrator":
                    assert formal_launch_claim_identity is not None
                    registration = (
                        formal_launch_claimant_registrar.
                        register_formal_launch_claimant(
                            {
                                "claim_identity": dict(
                                    formal_launch_claim_identity
                                ),
                                "expected_peer": expected_peer,
                            },
                            pidfd=pidfd,
                        )
                    )
                    record = getattr(registration, "record", None)
                    result = (
                        record.get("result")
                        if type(record) is dict
                        else None
                    )
                    if result != {
                        "claim_identity": dict(
                            formal_launch_claim_identity
                        ),
                        "expected_peer": expected_peer,
                        "state": "CLAIMANT_REGISTERED",
                    }:
                        raise FormalCampaignError(
                            "selected formal orchestrator registration drifted"
                        )
                else:
                    session = dict(
                        formal_launch_claimant_registrar.
                        register_formal_supervisor(
                            {
                                "expected_peer": expected_peer,
                                "package_id": context["package_id"],
                            },
                            pidfd=pidfd,
                        )
                    )
                    session_raw = authority.canonical_json(session)
                    if (
                        session.get("schema_version")
                        != FORMAL_SUPERVISOR_SESSION_SCHEMA
                        or session.get("expected_peer") != expected_peer
                        or session.get("package_id")
                        != context["package_id"]
                        or not session_raw
                        or len(session_raw)
                        > MAX_FORMAL_SUPERVISOR_SESSION_BYTES
                    ):
                        raise FormalCampaignError(
                            "selected formal supervisor session registration drifted"
                        )
                    if os.write(child_release_write, b"1") != 1:
                        raise FormalCampaignError(
                            "selected formal supervisor release was short"
                        )
                    release_write_error = close_owned(
                        child_release_write
                    )
                    child_release_write = -1
                    if release_write_error is not None:
                        raise release_write_error
                    offset = 0
                    while offset < len(session_raw):
                        written = os.write(
                            supervisor_session_write,
                            session_raw[offset:],
                        )
                        if written <= 0:
                            raise FormalCampaignError(
                                "selected formal supervisor session write made no progress"
                            )
                        offset += written
                    supervisor_write_error = close_owned(
                        supervisor_session_write
                    )
                    supervisor_session_write = -1
                    if supervisor_write_error is not None:
                        raise supervisor_write_error
            finally:
                os.close(pidfd)
            if child_release_write >= 0:
                if os.write(child_release_write, b"1") != 1:
                    raise FormalCampaignError(
                        f"selected {role} release was short"
                    )
                release_write_error = close_owned(child_release_write)
                child_release_write = -1
                if release_write_error is not None:
                    raise release_write_error
        else:
            actions: list[tuple[Any, ...]] = [
                *((
                    os.POSIX_SPAWN_DUP2,
                    high[target],
                    target,
                ) for target in tuple(opened)),
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
        launch_resource_authority=_prospective_resource_authority(
            context
        ),
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
        authority_context=context,
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
                authority_context=context,
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

    return {
        "pre_unref_cleanup_identity": pre_unref_identity,
        "status": "PRE_UNREF_RECEIPTS_READY_FOR_DETACHED_REPLAY",
    }


def _release_guardian_and_raw_locks(
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
        or state.pre_unref_identity is None
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
        != success_verifier.GUARDIAN_LOCK_CLOSE_SCHEMA
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
        detached_success_identity=state.detached_success_identity,
        guardian_close_identity=guardian_close_identity,
        guardian_identity=state.guardian.unit_identity,
        pre_unref_cleanup_identity=state.pre_unref_identity,
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
            "expected_detached_success_identity": state.detached_success_identity,
            "expected_pre_unref_cleanup_identity": state.pre_unref_identity,
        },
    )
    closeout_state.record_late_proof_once(
        state.attempt,
        "guardian_absence_identity",
        guardian_absence_identity,
    )
    state.guardian_absence_identity = guardian_absence_identity

    _post_release_signal_checkpoint(
        latch,
        phase="supervisor exact-once raw lock release",
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
        phase="supervisor raw lock-release receipt publication",
    )
    raw_record = _common_receipt(
        context,
        state.selection_identity,
        phase="supervisor_raw_lock_release",
        detached_substantive_identity=state.detached_success_identity,
        detached_substantive_kind="success_v3",
        failure_pre_release_identity="absent",
        guardian_absence_identity=guardian_absence_identity,
        guardian_close_identity=guardian_close_identity,
        lock_identities=lock_identities,
        outcome="SUCCESS_CANDIDATE",
        supervisor_release={
            "after_guardian_absence": True,
            "attempted": True,
            "recorded": True,
            "returned": True,
        },
    )
    raw_identity = _publish_tracked_phase(
        state.attempt,
        store,
        key="supervisor-raw-lock-release",
        path=paths["supervisor_raw_lock_release"],
        record=raw_record,
        validator=success_verifier.validate_supervisor_raw_lock_release,
        validator_kwargs={
            "expected": expected,
            "expected_lock_identities": lock_identities,
            "expected_detached_substantive_identity": (
                state.detached_success_identity
            ),
            "expected_detached_substantive_kind": "success_v3",
            "expected_failure_pre_release_identity": "absent",
            "expected_guardian_absence_identity": (
                guardian_absence_identity
            ),
            "expected_guardian_close_identity": guardian_close_identity,
        },
    )
    state.supervisor_raw_lock_release_identity = raw_identity
    closeout_state.record_late_proof_once(
        state.attempt,
        "supervisor_raw_lock_release_identity",
        raw_identity,
    )
    return {
        "supervisor_raw_lock_release_identity": raw_identity,
        "guardian_absence_identity": guardian_absence_identity,
        "guardian_lock_close_identity": guardian_close_identity,
        "lock_identities": lock_identities,
        "lock_release_effect": release_effect,
    }


def _content_identity(
    value: object,
    *,
    label: str,
) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value) != {"sha256", "size_bytes"}
        or type(value["sha256"]) is not str
        or SHA256_RE.fullmatch(value["sha256"]) is None
        or isinstance(value["size_bytes"], bool)
        or not isinstance(value["size_bytes"], int)
        or value["size_bytes"] <= 0
    ):
        raise IrreversibleFormalFailure(
            f"{label} content identity is malformed"
        )
    return dict(value)


def _canonical_message_identity(value: object) -> dict[str, object]:
    raw = authority.canonical_json(value)
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _validate_closure_final_release_join(
    closure_handoff: object,
    final_release_handoff: object,
    *,
    final_release_pidfd: int,
) -> dict[str, object]:
    if (
        type(closure_handoff) is not dict
        or type(final_release_handoff) is not dict
    ):
        raise IrreversibleFormalFailure(
            "closure/final-release handoff join is absent"
        )
    expected_final_fields = {
        "actor",
        "alternate_replay_source_identity",
        "broker_actor",
        "control_descriptor_identity",
        "formal_root_path",
        "nonce",
        "pidfd_method",
        "prepared_release_identity",
        "primary_replay_source_identity",
        "ready_handshake_identity",
        "release_root_path",
        "role",
        "role_source_identity",
        "schema_version",
    }
    actor = final_release_handoff.get("actor")
    try:
        pidfd_target = budget_broker._pidfd_target_pid(  # noqa: SLF001
            final_release_pidfd
        )
        actor_starttime = (
            budget_broker.process_starttime(cast(int, actor["pid"]))
            if type(actor) is dict and type(actor.get("pid")) is int
            else None
        )
        actor_exited = budget_broker.pidfd_reports_exit(
            final_release_pidfd
        )
    except (OSError, budget_broker.BrokerProtocolError) as exc:
        raise IrreversibleFormalFailure(
            "closure/final-release actor pidfd cannot be verified"
        ) from exc
    if (
        type(actor) is not dict
        or set(actor)
        != {"schema_version", "pid", "pid_starttime", "uid"}
        or set(final_release_handoff) != expected_final_fields
        or final_release_handoff.get("schema_version")
        != final_release_actor.HANDOFF_SCHEMA
        or final_release_handoff.get("role")
        != final_release_actor.PACKAGE_ROLE
        or actor["schema_version"] != final_release_actor.ACTOR_SCHEMA
        or type(actor["pid"]) is not int
        or type(actor["pid_starttime"]) is not int
        or type(actor["uid"]) is not int
        or actor["uid"] != os.getuid()
        or closure_handoff.get("final_release_actor") != actor
        or closure_handoff.get("final_release_pidfd_method")
        != final_release_handoff.get("pidfd_method")
        or closure_handoff.get("final_release_handoff_identity")
        != _canonical_message_identity(final_release_handoff)
        or pidfd_target != actor["pid"]
        or actor_starttime != actor["pid_starttime"]
        or actor_exited
    ):
        raise IrreversibleFormalFailure(
            "closure/final-release actor authority join drifted"
        )
    return {
        "final_release_actor": dict(actor),
        "final_release_handoff_identity": (
            _canonical_message_identity(final_release_handoff)
        ),
        "final_release_pidfd_method": final_release_handoff[
            "pidfd_method"
        ],
        "state": "FINAL_RELEASE_ACTOR_PIDFD_JOINED",
    }


class _PersistentFormalTerminalTail:
    """Single-session adapter from selected supervisor to closure actors."""

    def __init__(
        self,
        *,
        broker_client: budget_broker.BrokerSessionClient,
        budget_backend: budget_broker.BrokerProcessFormalBudgetBackend,
        context: Mapping[str, object],
        formal_root: Path,
    ) -> None:
        self._broker = broker_client
        self._backend = budget_backend
        self._context = dict(context)
        self._formal_root = Path(os.path.abspath(formal_root))
        self._baseline: dict[str, object] | None = None
        self._baseline_sha256: str | None = None
        self._closure: closure_actor.DetachedClosureProcess | None = None
        self._final_release: final_release_actor.FinalReleaseProcess | None = None
        self._final_release_join: dict[str, object] | None = None
        self._branch: str | None = None
        self._terminal_join_sha256: str | None = None
        self._disarm_observation: dict[str, object] | None = None
        self._broker_contract: dict[str, object] | None = None
        self._root_inventory: dict[str, object] | None = None

    def bind_closure_process_baseline(
        self,
        resource_admission_receipt: Mapping[str, object],
    ) -> Mapping[str, object]:
        if self._baseline is not None:
            raise IrreversibleFormalFailure(
                "closure process baseline cannot be bound twice"
            )
        measurements = resource_admission_receipt.get("measurements")
        if type(measurements) is not dict:
            raise IrreversibleFormalFailure(
                "resource admission lacks closure process measurements"
            )
        baseline = measurements.get("same_uid_process_baseline")
        baseline_sha256 = measurements.get(
            "same_uid_process_baseline_sha256"
        )
        try:
            checked = resource_admission.validate_same_uid_process_baseline(
                baseline,
                expected_sha256=baseline_sha256,
                require_live=True,
            )
        except Exception as exc:
            raise IrreversibleFormalFailure(
                "closure process baseline failed independent replay"
            ) from exc
        self._baseline = dict(checked)
        self._baseline_sha256 = cast(str, baseline_sha256)
        return {
            "same_uid_process_baseline_sha256": baseline_sha256,
            "state": "CLOSURE_PROCESS_BASELINE_BOUND",
        }

    @staticmethod
    def _result(
        frame: budget_broker.ReceivedFrame,
        *,
        label: str,
    ) -> dict[str, object]:
        result = frame.record.get("result")
        if type(result) is not dict:
            raise IrreversibleFormalFailure(
                f"{label} broker result is absent"
            )
        return dict(result)

    @staticmethod
    def _prove_pidfd_exit(
        descriptor: int,
        *,
        label: str,
        timeout_milliseconds: int = 5000,
    ) -> None:
        poller = select.poll()
        poller.register(descriptor, select.POLLIN | select.POLLHUP)
        if not poller.poll(timeout_milliseconds):
            raise IrreversibleFormalFailure(
                f"{label} pidfd did not report terminal exit"
            )

    def prepare_closure(
        self,
        *,
        branch: str,
        terminal_join_sha256: str,
    ) -> Mapping[str, object]:
        if (
            self._closure is not None
            or self._final_release is not None
            or branch not in {"success", "incomplete"}
            or SHA256_RE.fullmatch(terminal_join_sha256) is None
        ):
            raise IrreversibleFormalFailure(
                "closure preparation state or identity drifted"
            )
        response = self._broker.request(
            "PREPARE_CLOSURE",
            {},
            expected_fd_counts=frozenset({4}),
        )
        descriptors = list(response.descriptors)
        result = self._result(
            response,
            label="closure preparation",
        )
        try:
            if (
                set(result)
                != {
                    "schema_version",
                    "closure_handoff",
                    "final_release_handoff",
                    "registration",
                }
                or result["schema_version"]
                != budget_broker.CLOSURE_CONTROL_TRANSFER_SCHEMA
                or type(result["closure_handoff"]) is not dict
                or type(result["final_release_handoff"]) is not dict
                or type(result["registration"]) is not dict
            ):
                raise IrreversibleFormalFailure(
                    "closure preparation envelope drifted"
                )
            final_release_join = _validate_closure_final_release_join(
                result["closure_handoff"],
                result["final_release_handoff"],
                final_release_pidfd=descriptors[3],
            )
            closure = closure_actor.attach_broker_forked_closure(
                cast(Mapping[str, object], result["closure_handoff"]),
                tuple(descriptors[:2]),
            )
            descriptors[:2] = []
            final_release = (
                final_release_actor.attach_broker_forked_final_release(
                    cast(
                        Mapping[str, object],
                        result["final_release_handoff"],
                    ),
                    tuple(descriptors),
                )
            )
            descriptors.clear()
        except BaseException:
            for descriptor in descriptors:
                try:
                    os.close(descriptor)
                except BaseException:
                    pass
            raise
        self._closure = closure
        self._final_release = final_release
        self._final_release_join = final_release_join
        self._branch = branch
        self._terminal_join_sha256 = terminal_join_sha256
        return {
            "broker_registration": dict(
                cast(Mapping[str, object], result["registration"])
            ),
            "closure_actor": dict(closure.actor),
            "final_release_actor": dict(final_release.actor),
            "final_release_handoff_identity": final_release_join[
                "final_release_handoff_identity"
            ],
            "final_release_pidfd_method": final_release_join[
                "final_release_pidfd_method"
            ],
            "state": "CLOSURE_AND_FINAL_RELEASE_CONTROL_PREPARED",
            "terminal_join_sha256": terminal_join_sha256,
        }

    def publish_disarm_intent(
        self,
        *,
        terminal_join_sha256: str,
    ) -> Mapping[str, object]:
        if (
            self._closure is None
            or terminal_join_sha256 != self._terminal_join_sha256
        ):
            raise IrreversibleFormalFailure(
                "recovery disarm intent precedes exact closure preparation"
            )
        result = self._result(
            self._broker.request(
                "PUBLISH_DISARM_INTENT",
                {"terminal_join_sha256": terminal_join_sha256},
            ),
            label="recovery disarm intent",
        )
        if (
            result.get("schema_version")
            != budget_broker.RECOVERY_DISARM_INTENT_SCHEMA
            or result.get("state")
            != "RECOVERY_DISARM_INTENT_PUBLISHED"
            or result.get("terminal_join_sha256")
            != terminal_join_sha256
        ):
            raise IrreversibleFormalFailure(
                "recovery disarm intent result drifted"
            )
        return {
            "intent": result,
            "intent_sha256": _canonical_message_identity(result)["sha256"],
            "state": "RECOVERY_DISARM_INTENT_PUBLISHED",
        }

    def disarm_recovery_once(
        self,
        *,
        disarm_intent: Mapping[str, object],
    ) -> Mapping[str, object]:
        intent_sha256 = disarm_intent.get("intent_sha256")
        if (
            SHA256_RE.fullmatch(cast(str, intent_sha256))
            is None
        ):
            raise IrreversibleFormalFailure(
                "recovery disarm intent identity is absent"
            )
        result = self._result(
            self._broker.request(
                "DISARM_RECOVERY",
                {"disarm_intent_sha256": intent_sha256},
            ),
            label="recovery disarm",
        )
        if set(result) != {
            "handoff_identity",
            "lock_release",
            "terminal",
        }:
            raise IrreversibleFormalFailure(
                "recovery disarm response shape drifted"
            )
        self._disarm_observation = dict(result)
        return {
            "observation": result,
            "state": "RECOVERY_DISARMED_ACKNOWLEDGED",
        }

    def prove_recovery_absence(
        self,
        *,
        disarm_observation: Mapping[str, object],
    ) -> Mapping[str, object]:
        observation = disarm_observation.get("observation")
        if (
            type(observation) is not dict
            or observation != self._disarm_observation
            or cast(Mapping[str, object], observation["terminal"]).get(
                "pidfd_exit_proved"
            )
            is not True
            or cast(Mapping[str, object], observation["lock_release"]).get(
                "state"
            )
            != "RECOVERY_TAKEOVER_LOCK_RELEASED"
        ):
            raise IrreversibleFormalFailure(
                "recovery absence or takeover-lock release is not proved"
            )
        return {
            "observation": dict(observation),
            "state": "RECOVERY_ABSENT_TAKEOVER_LOCK_RELEASED",
        }

    def retire_broker_once(
        self,
        *,
        recovery_absence: Mapping[str, object],
    ) -> Mapping[str, object]:
        if (
            recovery_absence.get("state")
            != "RECOVERY_ABSENT_TAKEOVER_LOCK_RELEASED"
            or self._broker.closed
        ):
            raise IrreversibleFormalFailure(
                "broker retirement precedes recovery absence"
            )
        status = self._result(
            self._broker.request("STATUS", {}),
            label="broker pre-exit status",
        )
        actor_pid = self._broker.actor.get("pid")
        if isinstance(actor_pid, bool) or not isinstance(actor_pid, int):
            raise IrreversibleFormalFailure(
                "broker actor PID is invalid"
            )
        pidfd, _method = budget_broker.open_pidfd(actor_pid)
        try:
            if (
                budget_broker.process_starttime(actor_pid)
                != self._broker.actor["pid_starttime"]
            ):
                raise IrreversibleFormalFailure(
                    "broker actor identity drifted before EXIT"
                )
            exited = self._result(
                self._broker.request("EXIT", {}),
                label="broker EXIT",
            )
            self._broker.connection.close()
            self._broker.closed = True
            self._prove_pidfd_exit(
                pidfd,
                label="persistent budget broker",
            )
        finally:
            os.close(pidfd)
        if (
            exited.get("state") != "BROKER_EXIT_ACCEPTED"
            or type(exited.get("root_inventory")) is not dict
            or type(status.get("contract")) is not dict
        ):
            raise IrreversibleFormalFailure(
                "broker EXIT result or root inventory drifted"
            )
        self._broker_contract = dict(
            cast(Mapping[str, object], status["contract"])
        )
        self._root_inventory = dict(
            cast(Mapping[str, object], exited["root_inventory"])
        )
        return {
            "broker_actor": dict(self._broker.actor),
            "contract": dict(self._broker_contract),
            "root_inventory": dict(self._root_inventory),
            "state": "BROKER_ABSENT_NO_ROOT_WRITERS",
        }

    def close_root_once(
        self,
        *,
        broker_absence: Mapping[str, object],
        terminal_join_sha256: str,
    ) -> Mapping[str, object]:
        if (
            self._closure is None
            or self._baseline is None
            or self._baseline_sha256 is None
            or self._broker_contract is None
            or self._root_inventory is None
            or self._final_release_join is None
            or broker_absence.get("state")
            != "BROKER_ABSENT_NO_ROOT_WRITERS"
            or terminal_join_sha256 != self._terminal_join_sha256
            or self._disarm_observation is None
        ):
            raise IrreversibleFormalFailure(
                "formal root closure prerequisites are incomplete"
            )
        process = self._closure
        result = process.close_root(
            {
                "budget_contract": self._broker_contract,
                "disarm_observation": self._disarm_observation,
                "root_inventory": self._root_inventory,
                "same_uid_process_baseline": self._baseline,
                "same_uid_process_baseline_sha256": (
                    self._baseline_sha256
                ),
                "terminal_join_sha256": terminal_join_sha256,
            }
        )
        process.prove_exit()
        process.close()
        self._closure = None
        expected_final_release_binding = {
            "actor": self._final_release_join["final_release_actor"],
            "handoff_identity": self._final_release_join[
                "final_release_handoff_identity"
            ],
            "phase": "FINAL_CLOSURE_SCOPE",
            "pidfd_method": self._final_release_join[
                "final_release_pidfd_method"
            ],
            "state": "LIVE_EXACT_FINAL_RELEASE_ACTOR_BOUND",
        }
        if (
            result.get("state") != "ROOT_CLOSED_NO_WRITERS"
            or result.get("final_release_binding")
            != expected_final_release_binding
        ):
            raise IrreversibleFormalFailure(
                "closure actor did not preserve the final-release identity join"
            )
        return result

    @staticmethod
    def _replay_receipt_bytes(
        envelope: Mapping[str, object],
        *,
        implementation: str,
    ) -> None:
        identity = closeout_state.validate_identity_join(
            cast(Mapping[str, object], envelope["receipt_identity"]),
            f"{implementation} replay receipt",
        )
        path = Path(cast(str, identity["path"]))
        parent_fd = budget_broker.budget._open_absolute_directory_no_symlinks(  # noqa: SLF001
            path.parent
        )
        descriptor = -1
        try:
            descriptor = os.open(
                path.name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
            metadata = os.fstat(descriptor)
            raw = b"".join(
                os.pread(
                    descriptor,
                    min(1024 * 1024, metadata.st_size - offset),
                    offset,
                )
                for offset in range(0, metadata.st_size, 1024 * 1024)
            )
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(parent_fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o444
            or metadata.st_nlink != 1
            or metadata.st_size != identity["size_bytes"]
            or hashlib.sha256(raw).hexdigest() != identity["sha256"]
        ):
            raise IrreversibleFormalFailure(
                f"{implementation} replay receipt bytes drifted"
            )
        try:
            record = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IrreversibleFormalFailure(
                f"{implementation} replay receipt is not strict JSON"
            ) from exc
        if (
            type(record) is not dict
            or authority.canonical_json(record) != raw
            or record.get("schema_version")
            != final_release_actor.REPLAY_RECEIPT_SCHEMA
            or record.get("implementation") != implementation
            or record.get("result") != envelope["result"]
            or record.get("source_identity")
            != envelope["source_identity"]
            or record.get("state")
            != "FORMAL_ROOT_REPLAY_RECEIPT_ACCEPTED"
        ):
            raise IrreversibleFormalFailure(
                f"{implementation} replay receipt self-replay failed"
            )

    def replay_closed_root(
        self,
        *,
        implementation: str,
    ) -> Mapping[str, object]:
        if self._final_release is None:
            raise IrreversibleFormalFailure(
                "outside replay lacks its fixed final-release actor"
            )
        if implementation == "primary":
            result = formal_root_replay_primary.replay_formal_root(
                self._formal_root
            )
        elif implementation == "alternate":
            result = formal_root_replay_alternate.replay_formal_root(
                self._formal_root
            )
        else:
            raise IrreversibleFormalFailure(
                "outside replay implementation is unknown"
            )
        envelope = self._final_release.publish_replay_receipt(
            implementation=implementation,
            result=result,
        )
        self._replay_receipt_bytes(
            envelope,
            implementation=implementation,
        )
        return envelope

    def publish_final_release(
        self,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        if self._final_release is None:
            raise IrreversibleFormalFailure(
                "outside final-release actor is absent"
            )
        return self._final_release.publish_final_release(payload)

    def prove_final_release_absence(
        self,
        *,
        final_release_result: Mapping[str, object],
    ) -> Mapping[str, object]:
        if (
            self._final_release is None
            or final_release_result.get("state")
            != "FINAL_RELEASE_PUBLISHED_UNUSED_SEALED"
        ):
            raise IrreversibleFormalFailure(
                "outside final-release result is absent"
            )
        process = self._final_release
        process.prove_exit()
        actor = dict(process.actor)
        process.close()
        self._final_release = None
        return {
            "actor": actor,
            "state": "FINAL_RELEASE_ACTOR_ABSENT",
        }


def formal_supervisor_capabilities_from_fd(
    fd: int,
    *,
    native_budget_helper: object,
    campaign_dir: Path | str,
    supervisor_session: Mapping[str, object],
) -> FormalSupervisorCapabilities:
    """Consume the pidfd-bound FD8 session and build one shared capability."""

    expected_session_fields = {
        "broker_actor",
        "broker_grant",
        "broker_nonce_sha256",
        "credential",
        "expected_peer",
        "formal_budget_runtime_identity",
        "owner_actor",
        "package_id",
        "schema_version",
    }
    owned_fd = -1
    client: budget_broker.BrokerSessionClient | None = None
    try:
        if fd != 8:
            raise FormalCampaignError(
                "formal supervisor budget broker must arrive on fixed FD8"
            )
        owned_fd = fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 20)
        os.close(fd)
        context = authority.replay_formal_launch_context(
            campaign_dir=Path(campaign_dir)
        )
        runtime = context["formal_budget_runtime"]
        expected_peer = budget_broker.process_identity()
        actor = {
            "schema_version": budget_broker.ACTOR_SCHEMA,
            **cast(
                Mapping[str, object],
                cast(Mapping[str, object], runtime)[
                    "broker_actor_identity"
                ],
            ),
        }
        if (
            type(supervisor_session) is not dict
            or set(supervisor_session) != expected_session_fields
            or supervisor_session["schema_version"]
            != FORMAL_SUPERVISOR_SESSION_SCHEMA
            or supervisor_session["package_id"] != context["package_id"]
            or supervisor_session["expected_peer"] != expected_peer
            or supervisor_session["broker_actor"] != actor
            or type(supervisor_session["credential"]) is not str
            or SHA256_RE.fullmatch(
                cast(str, supervisor_session["credential"])
            )
            is None
            or supervisor_session["broker_nonce_sha256"]
            != hashlib.sha256(
                cast(str, cast(Mapping[str, object], runtime)["broker_nonce"])
                .encode("ascii")
            ).hexdigest()
            or supervisor_session["formal_budget_runtime_identity"]
            != _canonical_message_identity(runtime)
            or supervisor_session["broker_grant"]
            != budget_broker.build_session_grant(
                credential=cast(str, supervisor_session["credential"]),
                expected_peer=expected_peer,
                role="formal-supervisor",
            ).as_record()
        ):
            raise FormalCampaignError(
                "formal supervisor owner session identity drifted"
            )
        transferred = owned_fd
        owned_fd = -1
        client = budget_broker.attach_registered_nonarm_session(
            transferred,
            broker_actor=actor,
            broker_nonce=cast(
                str,
                cast(Mapping[str, object], runtime)["broker_nonce"],
            ),
            credential=cast(str, supervisor_session["credential"]),
            role="formal-supervisor",
            native_helper=cast(
                budget_broker.NativeHelperProtocol,
                native_budget_helper,
            ),
        )
        material = formal_controller.formal_supervisor_budget_material(
            context
        )
        backend = budget_broker.BrokerProcessFormalBudgetBackend(
            broker_client=client,
            native_helper=cast(
                budget_broker.NativeHelperProtocol,
                native_budget_helper,
            ),
            formal_root=Path(cast(str, material["formal_root"])),
            enforced_budget_profile=cast(
                Mapping[str, object],
                material["profile"],
            ),
            resource_calibration_authorization_bundle=cast(
                Mapping[str, object],
                material["calibration_bundle"],
            ),
            resource_calibration_authorization_bundle_identity=cast(
                Mapping[str, object],
                material["calibration_bundle_identity"],
            ),
            expected_calibration_tool_identities=cast(
                Mapping[str, Mapping[str, object]],
                material["calibration_tool_content_identities"],
            ),
            authority_binding={
                "budget_profile_identity": context[
                    "resource_budget_profile_identity"
                ],
                "filesystem_write_confinement": (
                    "not-applicable-persistent-supervisor-v1"
                ),
                "formal_budget_runtime": runtime,
                "formal_root_contract_identity": cast(
                    Mapping[str, object],
                    runtime,
                )["formal_root_contract_identity"],
                "formal_resource_calibration_bundle_identity": material[
                    "calibration_bundle_identity"
                ],
                "selected_fd_transport": context[
                    "selected_fd_transport"
                ],
            },
            fixed_artifacts=cast(
                Mapping[str, Mapping[str, object]],
                material["fixed_artifacts"],
            ),
            fixed_channels=cast(
                Mapping[str, Mapping[str, object]],
                material["fixed_channels"],
            ),
            fixed_directories=cast(
                Mapping[str, Mapping[str, object]],
                material["fixed_directories"],
            ),
            require_worker_confinement=False,
        )
        tail = _PersistentFormalTerminalTail(
            broker_client=client,
            budget_backend=backend,
            context=context,
            formal_root=Path(cast(str, material["formal_root"])),
        )
        return FormalSupervisorCapabilities(
            budget_backend=backend,
            receipt_budget_bindings=cast(
                Mapping[str, Mapping[str, object]],
                material["receipt_budget_bindings"],
            ),
            selection_transition=backend,
            terminal_tail_port=tail,
        )
    except BaseException as exc:
        try:
            if client is not None:
                client.close()
            elif owned_fd >= 0:
                os.close(owned_fd)
        except BaseException as cleanup_error:
            exc.add_note(
                "formal supervisor factory cleanup also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
        raise


def _tail_control_result(
    value: Mapping[str, object],
    *,
    state: str,
    label: str,
) -> dict[str, object]:
    record = dict(value)
    if not record or record.get("state") != state:
        raise IrreversibleFormalFailure(
            f"{label} did not reach its exact terminal state"
        )
    closeout_state.reject_none(record, label)
    return record


def _tail_replay_envelope(
    value: Mapping[str, object],
    *,
    schema: str,
    implementation: str,
    label: str,
) -> dict[str, object]:
    if set(value) != {"receipt_identity", "result", "source_identity"}:
        raise IrreversibleFormalFailure(
            f"{label} envelope field set drifted"
        )
    receipt_identity = closeout_state.validate_identity_join(
        cast(Mapping[str, object], value["receipt_identity"]),
        f"{label} outside receipt",
    )
    source_identity = _content_identity(
        value["source_identity"],
        label=f"{label} package source",
    )
    result = value["result"]
    if (
        type(result) is not dict
        or result.get("schema_version") != schema
        or result.get("implementation") != implementation
        or result.get("state") != "FORMAL_ROOT_CLOSURE_ACCEPTED"
        or result.get("authority_scope") != AUTHORITY_SCOPE
        or result.get("authority")
        != {
            "changes_certified_exact": False,
            "changes_cut_state": False,
            "changes_lower_bound": False,
            "changes_production": False,
            "changes_upper_bound": False,
            "research_only": True,
        }
    ):
        raise IrreversibleFormalFailure(
            f"{label} outside replay discriminator drifted"
        )
    return {
        "receipt_identity": receipt_identity,
        "result": dict(result),
        "source_identity": source_identity,
    }


def _complete_post_reference_budget_tail(
    *,
    context: Mapping[str, object],
    state: SupervisorState,
    branch: str,
    reference_completion: Mapping[str, object],
    terminal_basis: Mapping[str, object],
    terminal_record_builder: Callable[
        [Mapping[str, object]],
        Mapping[str, object],
    ],
) -> dict[str, object]:
    """Close the formal root, replay it twice, then publish one outside join."""

    port = state.terminal_tail_port
    if port is None:
        raise IrreversibleFormalFailure(
            "package-pinned formal terminal tail capability is absent"
        )
    if branch not in {"success", "incomplete"}:
        raise IrreversibleFormalFailure(
            "formal terminal tail branch is invalid"
        )
    terminal_join_sha256 = hashlib.sha256(
        authority.canonical_json(terminal_basis)
    ).hexdigest()
    prepared = _tail_control_result(
        port.prepare_closure(
            branch=branch,
            terminal_join_sha256=terminal_join_sha256,
        ),
        state="CLOSURE_AND_FINAL_RELEASE_CONTROL_PREPARED",
        label="formal closure preparation",
    )
    disarm_intent = _tail_control_result(
        port.publish_disarm_intent(
            terminal_join_sha256=terminal_join_sha256,
        ),
        state="RECOVERY_DISARM_INTENT_PUBLISHED",
        label="recovery disarm intent",
    )
    disarm_observation = _tail_control_result(
        port.disarm_recovery_once(
            disarm_intent=disarm_intent,
        ),
        state="RECOVERY_DISARMED_ACKNOWLEDGED",
        label="recovery disarm",
    )
    recovery_absence = _tail_control_result(
        port.prove_recovery_absence(
            disarm_observation=disarm_observation,
        ),
        state="RECOVERY_ABSENT_TAKEOVER_LOCK_RELEASED",
        label="recovery absence",
    )
    broker_absence = _tail_control_result(
        port.retire_broker_once(
            recovery_absence=recovery_absence,
        ),
        state="BROKER_ABSENT_NO_ROOT_WRITERS",
        label="broker absence",
    )
    closure_result = _tail_control_result(
        port.close_root_once(
            broker_absence=broker_absence,
            terminal_join_sha256=terminal_join_sha256,
        ),
        state="ROOT_CLOSED_NO_WRITERS",
        label="formal root closure",
    )
    primary = _tail_replay_envelope(
        port.replay_closed_root(implementation="primary"),
        schema=PRIMARY_FORMAL_ROOT_REPLAY_SCHEMA,
        implementation="package-pinned-primary-v1",
        label="primary formal-root replay",
    )
    alternate = _tail_replay_envelope(
        port.replay_closed_root(implementation="alternate"),
        schema=ALTERNATE_FORMAL_ROOT_REPLAY_SCHEMA,
        implementation="package-pinned-stdlib-alternate-v1",
        label="alternate formal-root replay",
    )
    primary_result = cast(
        Mapping[str, object],
        primary["result"],
    )
    alternate_result = cast(
        Mapping[str, object],
        alternate["result"],
    )
    comparable = {
        "actor_absence",
        "authority",
        "authority_scope",
        "formal_manifest_identity",
        "formal_root",
        "manifest_entries_sha256",
        "state",
        "terminal_join_sha256",
    }
    if (
        any(
            primary_result.get(field) != alternate_result.get(field)
            for field in comparable
        )
        or primary_result.get("terminal_join_sha256")
        != terminal_join_sha256
        or primary["source_identity"]["sha256"]
        == alternate["source_identity"]["sha256"]
        or primary["receipt_identity"]["path"]
        == alternate["receipt_identity"]["path"]
    ):
        raise IrreversibleFormalFailure(
            "formal-root outside replays disagree or are not independent"
        )
    formal_manifest_identity = closeout_state.validate_identity_join(
        cast(
            Mapping[str, object],
            primary_result["formal_manifest_identity"],
        ),
        "formal root manifest",
    )
    evidence = {
        "schema_version": (
            success_verifier.POST_ROOT_CLOSURE_EVIDENCE_SCHEMA
        ),
        "alternate_replay_identity": _canonical_message_identity(
            alternate_result
        ),
        "alternate_replay_receipt_identity": alternate[
            "receipt_identity"
        ],
        "alternate_replay_source_identity": alternate["source_identity"],
        "branch": branch,
        "closure_result_identity": _canonical_message_identity(
            closure_result
        ),
        "formal_manifest_identity": formal_manifest_identity,
        "primary_replay_identity": _canonical_message_identity(
            primary_result
        ),
        "primary_replay_receipt_identity": primary["receipt_identity"],
        "primary_replay_source_identity": primary["source_identity"],
        "reference_completion_identity": _canonical_message_identity(
            reference_completion
        ),
        "state": "CLOSED_ROOT_DUAL_REPLAY_ACCEPTED",
        "terminal_join_sha256": terminal_join_sha256,
    }
    checked_evidence = (
        success_verifier.validate_post_root_closure_evidence(
            evidence,
            expected_branch=branch,
            expected_terminal_join_sha256=terminal_join_sha256,
        )
    )
    terminal_record = dict(
        terminal_record_builder(checked_evidence)
    )
    publication_key = (
        "dual-lock-release"
        if branch == "success"
        else "failure-terminal-release"
    )
    publication = state.attempt.publication(publication_key)
    publication.begin()
    try:
        # The outside actor owns the exact rename/fsync/ACK boundary.  The
        # supervisor crosses the no-retry boundary before sending the sole
        # request because a lost reply cannot prove that publication did not
        # occur.
        publication.note_publication_may_have_happened()
        final_result = port.publish_final_release(
            {
                "alternate_replay": alternate_result,
                "alternate_replay_receipt_identity": alternate[
                    "receipt_identity"
                ],
                "alternate_replay_source_identity": alternate[
                    "source_identity"
                ],
                "branch": branch,
                "closure_result": closure_result,
                "primary_replay": primary_result,
                "primary_replay_receipt_identity": primary[
                    "receipt_identity"
                ],
                "primary_replay_source_identity": primary["source_identity"],
                "reference_completion": dict(reference_completion),
                "terminal_join_sha256": terminal_join_sha256,
                "terminal_record": terminal_record,
            }
        )
        if (
            set(final_result)
            != {
                "branch",
                "evidence",
                "schema_version",
                "selected_identity",
                "state",
                "unused_staging_identity",
            }
            or final_result.get("schema_version")
            != FINAL_RELEASE_RESULT_SCHEMA
            or final_result.get("state")
            != "FINAL_RELEASE_PUBLISHED_UNUSED_SEALED"
            or final_result.get("branch") != branch
            or final_result.get("evidence") != checked_evidence
            or type(final_result.get("unused_staging_identity")) is not dict
            or cast(
                Mapping[str, object],
                final_result["unused_staging_identity"],
            ).get("mode_octal")
            != "0444"
        ):
            raise IrreversibleFormalFailure(
                "outside-root final release result drifted"
            )
        selected_identity = closeout_state.validate_identity_join(
            cast(
                Mapping[str, object],
                final_result["selected_identity"],
            ),
            "outside-root final release",
        )
        publication.note_returned(selected_identity)
        final_release_absence = _tail_control_result(
            port.prove_final_release_absence(
                final_release_result=final_result,
            ),
            state="FINAL_RELEASE_ACTOR_ABSENT",
            label="outside-root final-release actor absence",
        )
        publication.note_recorded(selected_identity)
    except BaseException as exc:
        publication.note_error(exc)
        raise
    state.post_root_closure = checked_evidence
    return {
        "closure_preparation": prepared,
        "final_release_actor_absence": final_release_absence,
        "post_root_closure": checked_evidence,
        "selected_identity": selected_identity,
        "terminal_record": terminal_record,
    }


def _complete_reference_and_final_success(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    latch: closeout_helper.TerminationLatch,
    expected: Mapping[str, object],
    lock_identities: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Close RefUnit on the retained connection, then publish the final join."""

    if (
        state.selection is None
        or state.selection_identity is None
        or state.outer_identity is None
        or state.observer_identity is None
        or state.pre_unref_identity is None
        or state.detached_success_identity is None
        or state.guardian_close_identity is None
        or state.guardian_absence_identity is None
        or state.supervisor_raw_lock_release_identity is None
        or not host.locks_released
    ):
        raise IrreversibleFormalFailure(
            "post-lock RefUnit completion lacks its unique predecessor chain"
        )
    paths = state.selection["outer_spec"]["receipt_paths"]
    checked_locks = closeout_state._validate_lock_evidence(  # noqa: SLF001
        lock_identities
    )
    _post_release_signal_checkpoint(
        latch,
        phase="exact-once RefUnit Unref with connection retained",
    )
    released = closeout_state.release_reference_retained_once(
        boundary,
        state.attempt,
        store,
        unit_name=str(state.outer_identity["unit_name"]),
        observer_identity=state.observer_identity,
        pre_unref_cleanup_identity=state.pre_unref_identity,
    )
    if released.get("kind") != "RECORDED_CONNECTION_RETAINED":
        raise IrreversibleFormalFailure(
            f"post-lock RefUnit Unref did not become canonical: {released}"
        )
    unref_record, unref_identity = store.document(
        boundary.formal_dir / "unref-call.json",
        "prospective Unref call",
    )
    checked_unref = success_verifier.validate_unref_call(
        unref_record,
        expected=expected,
        expected_outer_identity=state.outer_identity,
        expected_acquisition_identity=cast(
            Mapping[str, object],
            state.attempt.acquire_identity,
        ),
        expected_client_unique_name=str(
            cast(Mapping[str, object], state.attempt.acquire_return)[
                "client_unique_name"
            ]
        ),
        expected_observer_identity=state.observer_identity,
        expected_pre_unref_cleanup_identity=state.pre_unref_identity,
    )
    release_record, release_identity = store.document(
        paths["reference_release"],
        "prospective reference release",
    )
    success_verifier.validate_reference_release(
        release_record,
        expected=expected,
        expected_outer_identity=state.outer_identity,
        expected_acquisition_identity=cast(
            Mapping[str, object],
            state.attempt.acquire_identity,
        ),
        expected_unref_call_identity=unref_identity,
        expected_observer_identity=state.observer_identity,
        expected_pre_unref_cleanup_identity=state.pre_unref_identity,
        expected_raw_lock_release_identity=(
            state.supervisor_raw_lock_release_identity
        ),
    )
    if (
        state.attempt.unref_call_identity != unref_identity
        or state.attempt.reference_release_identity != release_identity
        or checked_unref["call"] != state.attempt.release_return
    ):
        raise IrreversibleFormalFailure(
            "post-lock RefUnit release readback identity drifted"
        )

    _post_release_signal_checkpoint(
        latch,
        phase="post-Unref unit cgroup and PID absence wait",
    )
    post = host.wait_state(
        str(state.outer_identity["unit_name"]),
        str(state.outer_identity["control_group"]),
        state.outer_identity["processes"],
        referenced=False,
        timeout=RECORD_WAIT_SECONDS,
    )
    _post_release_signal_checkpoint(
        latch,
        phase="post-Unref absence receipt publication",
    )
    post_record = _common_receipt(
        context,
        state.selection_identity,
        phase="post_unref_absence",
        cgroup_absent=post["cgroup_absent"],
        load_state={
            "reference_release_identity": release_identity,
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

    _post_release_signal_checkpoint(
        latch,
        phase="same-connection manager client and library verification",
    )
    closed = closeout_state.close_released_reference_once(
        boundary,
        state.attempt,
        store,
        unit_name=str(state.outer_identity["unit_name"]),
        post_unref_absence_identity=post_identity,
    )
    if closed.get("kind") != "RECORDED_CONNECTION_CLOSED":
        raise IrreversibleFormalFailure(
            f"post-Unref connection close did not become canonical: {closed}"
        )
    terminal_record, terminal_identity = store.document(
        paths["reference_terminal"],
        "prospective reference terminal",
    )
    checked_terminal = success_verifier.validate_reference_terminal(
        terminal_record,
        expected=expected,
        expected_outer_identity=state.outer_identity,
        expected_acquisition_identity=cast(
            Mapping[str, object],
            state.attempt.acquire_identity,
        ),
        expected_release_identity=release_identity,
        expected_unref_call_identity=unref_identity,
        expected_post_unref_absence_identity=post_identity,
        expected_client_unique_name=str(
            cast(Mapping[str, object], state.attempt.acquire_return)[
                "client_unique_name"
            ]
        ),
    )
    close_record, close_identity = store.document(
        paths["reference_connection_close"],
        "prospective reference connection close",
    )
    success_verifier.validate_reference_connection_close(
        close_record,
        expected=expected,
        expected_outer_identity=state.outer_identity,
        expected_reference_terminal_identity=terminal_identity,
        expected_connection_verification=cast(
            Mapping[str, object],
            checked_terminal["connection_verification"],
        ),
    )
    if (
        state.attempt.reference_terminal_identity != terminal_identity
        or state.attempt.reference_connection_close_identity != close_identity
    ):
        raise IrreversibleFormalFailure(
            "reference terminal/connection-close readback identity drifted"
        )
    state.reference_terminal = {
        "identity": terminal_identity,
        "kind": "RECORDED_CONNECTION_CLOSED",
    }
    state.reference_connection_close_identity = close_identity

    _post_release_signal_checkpoint(
        latch,
        phase="formal-root closure and dual outside replay",
    )
    reference_completion = {
        "kind": "RECORDED_CONNECTION_CLOSED",
        "post_unref_absence_identity": post_identity,
        "reference_connection_close_identity": close_identity,
        "reference_release_identity": release_identity,
        "reference_terminal_identity": terminal_identity,
        "uncertainty_terminal": "absent",
    }
    terminal_basis = {
        "branch": "success",
        "detached_success_identity": state.detached_success_identity,
        "guardian_absence_identity": state.guardian_absence_identity,
        "guardian_close_identity": state.guardian_close_identity,
        "lock_identities": checked_locks,
        "reference_completion": reference_completion,
        "schema_version": FINAL_TERMINAL_PREDECESSOR_JOIN_SCHEMA,
        "supervisor_raw_lock_release_identity": (
            state.supervisor_raw_lock_release_identity
        ),
    }

    def build_dual(
        post_root_closure: Mapping[str, object],
    ) -> Mapping[str, object]:
        return _common_receipt(
            context,
            state.selection_identity,
            phase="dual_lock_release",
            detached_success_identity=state.detached_success_identity,
            guardian_absence_identity=state.guardian_absence_identity,
            guardian_close_identity=state.guardian_close_identity,
            lock_identities=checked_locks,
            post_root_closure=dict(post_root_closure),
            post_unref_absence_identity=post_identity,
            reference_connection_close_identity=close_identity,
            reference_release_identity=release_identity,
            reference_terminal_identity=terminal_identity,
            supervisor_raw_lock_release_identity=(
                state.supervisor_raw_lock_release_identity
            ),
            terminal_join={
                "broker_absent_before_manifest": True,
                "detached_success_before_guardian_close": True,
                "formal_root_closed_before_outside_replays": True,
                "guardian_absence_before_supervisor_release": True,
                "locks_released_after_substantive_verification": True,
                "outside_replays_before_final_join": True,
                "post_unref_absence_before_reference_terminal": True,
                "raw_lock_release_before_unref": True,
                "recovery_disarmed_before_manifest": True,
                "reference_terminal_before_connection_close": True,
                "reference_connection_close_before_final_join": True,
            },
        )

    tail = _complete_post_reference_budget_tail(
        context=context,
        state=state,
        branch="success",
        reference_completion=reference_completion,
        terminal_basis=terminal_basis,
        terminal_record_builder=build_dual,
    )
    dual_record = cast(Mapping[str, object], tail["terminal_record"])
    dual_identity = closeout_state.validate_identity_join(
        cast(Mapping[str, object], tail["selected_identity"]),
        "success outside-root final release",
    )
    release_paths = context.get("formal_final_release_paths")
    if (
        type(release_paths) is not dict
        or set(release_paths) != {"incomplete", "success"}
        or dual_identity["path"] != release_paths["success"]
    ):
        raise IrreversibleFormalFailure(
            "success final release escaped its fixed outside-root path"
        )
    success_verifier.validate_dual_lock_release(
        dual_record,
        expected=expected,
        expected_lock_identities=checked_locks,
        expected_detached_success_identity=state.detached_success_identity,
        expected_guardian_absence_identity=state.guardian_absence_identity,
        expected_guardian_close_identity=state.guardian_close_identity,
        expected_raw_lock_release_identity=(
            state.supervisor_raw_lock_release_identity
        ),
        expected_reference_release_identity=release_identity,
        expected_post_unref_absence_identity=post_identity,
        expected_reference_terminal_identity=terminal_identity,
        expected_reference_connection_close_identity=close_identity,
        expected_post_root_closure=cast(
            Mapping[str, object],
            tail["post_root_closure"],
        ),
    )
    state.dual_release_identity = dual_identity
    closeout_state.record_late_proof_once(
        state.attempt,
        "dual_lock_release_identity",
        dual_identity,
    )
    return {
        "dual_lock_release_identity": dual_identity,
        "post_unref_absence_identity": post_identity,
        "reference_connection_close_identity": close_identity,
        "reference_release_identity": release_identity,
        "reference_terminal_identity": terminal_identity,
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
        or state.pre_unref_identity is None
        or state.attempt.reference is None
        or state.attempt.release_attempted
    ):
        raise FormalCampaignError(
            "detached success verifier lacks one retained pre-Unref reference"
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


def _wait_failure_quiescence(
    *,
    host: closeout_helper.PinnedHost,
    ledger: Mapping[str, object],
    attempt: closeout_state.AttemptState,
    reference_retained: bool,
) -> dict[str, object]:
    while True:
        try:
            observation = host.observe_frozen_quiescence(
                ledger,
                reference_retained=reference_retained,
            )
            if observation["all_runtime_quiescent"] is True:
                return closeout_state.validate_runtime_quiescence(
                    observation,
                    ledger=ledger,
                    reference_retained=reference_retained,
                )
        except BaseException as exc:
            item = _failure("FAILURE_RUNTIME_QUIESCENCE_OBSERVATION_FAILED", exc)
            if item not in attempt.errors:
                attempt.errors.append(item)
        time.sleep(closeout_state.HOLD_POLL_SECONDS)


def _failure_reference_state(
    state: SupervisorState,
    *,
    context: Mapping[str, object],
) -> dict[str, object]:
    attempt = state.attempt
    if attempt.acquire_identity is not None:
        if (
            attempt.reference is None
            or attempt.acquire_return is None
            or attempt.release_attempted
            or attempt.connection_action
        ):
            raise IrreversibleFormalFailure(
                "canonical failure RefUnit is not retained before detached replay"
            )
        verification = attempt.reference.verify(
            expected_manager_owner=str(
                cast(Mapping[str, object], context["manager_epoch"])[
                    "dbus_unique_owner"
                ]
            )
        )
        return {
            "acquisition_identity": attempt.acquire_identity,
            "connection_verification": verification,
            "kind": "HELD",
            "terminal_identity": "absent",
        }
    terminal = _failure_reference_terminal(state)
    if terminal["kind"] == "NO_REFERENCE_OPENED":
        return {
            "acquisition_identity": "absent",
            "connection_verification": "absent",
            "kind": "NO_REFERENCE_OPENED",
            "terminal_identity": "absent",
        }
    identity = terminal.get("identity")
    if type(identity) is not dict:
        raise IrreversibleFormalFailure(
            "uncertain reference connection lacks a canonical drop receipt"
        )
    return {
        "acquisition_identity": "absent",
        "connection_verification": "absent",
        "kind": "CONNECTION_UNCERTAIN_DROPPED",
        "terminal_identity": identity,
    }


def _recorded_incomplete_identity(
    state: closeout_state.AttemptState,
) -> dict[str, object] | str:
    if state.incomplete_identity is not None:
        return closeout_state.validate_identity_join(
            state.incomplete_identity,
            "formal incomplete",
        )
    markerless = state.publications.get(
        closeout_state.FORMAL_MARKERLESS_INCOMPLETE
    )
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
    ledger: Mapping[str, object],
    lock_identities: Sequence[Mapping[str, object]],
    runtime_quiescence: Mapping[str, object] | None = None,
    reference_state: Mapping[str, object] | None = None,
    guardian_absence_identity: Mapping[str, object] | None = None,
    final_observation: Mapping[str, object] | None = None,
    reference_terminal: Mapping[str, object] | None = None,
    containment_hold_identity: Mapping[str, object] | str = "absent",
    containment_clearance_identity: Mapping[str, object] | str = "absent",
    containment_lock_release_identity: Mapping[str, object] | str = "absent",
    containment_lock_release_publication: Mapping[str, object] | str = "absent",
) -> dict[str, object]:
    del guardian_absence_identity, final_observation, reference_terminal
    if runtime_quiescence is None or reference_state is None:
        raise IrreversibleFormalFailure(
            "legacy failure-release topology is disabled for the prospective cohort"
        )
    checked_ledger = closeout_state.validate_frozen_ledger(ledger)
    checked_reference_state = dict(reference_state)
    reference_retained = checked_reference_state.get("kind") == "HELD"
    checked_quiescence = closeout_state.validate_runtime_quiescence(
        runtime_quiescence,
        ledger=checked_ledger,
        reference_retained=reference_retained,
    )
    if checked_quiescence["all_runtime_quiescent"] is not True:
        raise IrreversibleFormalFailure(
            "failure release cannot be published before runtime quiescence"
        )
    if set(checked_reference_state) != {
        "acquisition_identity",
        "connection_verification",
        "kind",
        "terminal_identity",
    }:
        raise IrreversibleFormalFailure("failure reference-state shape drifted")
    if reference_retained:
        checked_reference_state["acquisition_identity"] = (
            closeout_state.validate_identity_join(
                checked_reference_state["acquisition_identity"],
                "failure reference acquisition",
            )
        )
        if (
            checked_reference_state["connection_verification"]
            != state.attempt.acquire_return
            and checked_reference_state["connection_verification"]
            != getattr(state.attempt.reference, "verification", None)
        ):
            # The independent verifier will replay the exact acquisition
            # receipt.  Here we only reject a missing producer-side join.
            closeout_state.reject_none(
                checked_reference_state["connection_verification"],
                "failure retained reference verification",
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
            "frozen_ledger": checked_ledger,
            "reference_state": checked_reference_state,
            "runtime_quiescence": checked_quiescence,
        },
        "created_at_utc": _utc_now(),
        "detached_success_output_identity": detached_success_identity,
        "formal_selection_identity": (
            state.selection_identity
            if state.selection_identity is not None
            else "absent"
        ),
        "incomplete_identity": _recorded_incomplete_identity(state.attempt),
        "lock_identities": checked_locks,
        "lock_lifecycle": {
            "detached_incomplete_is_next_required_step": True,
            "guardian_absence_required_after_detached": True,
            "raw_lock_release_required_after_guardian_absence": True,
            "reference_completion_required_after_raw_release": (
                reference_retained
            ),
            "supervisor_lock_release_permitted": False,
            "supervisor_locks_must_remain_held": True,
        },
        "lower_bound": "absent",
        "outcome": "INCOMPLETE",
        "package_id": context["package_id"],
        "phase": phase,
        "production_authority_changed": False,
        "production_certified": False,
        "reference_retained": reference_retained,
        "retry_eligible": False,
        "runtime_quiescent": True,
        "schema_version": FAILURE_RELEASE_SCHEMA,
        "status": "INCOMPLETE_PRE_RELEASE",
        "stage_b_changed": False,
        "success_eligible": False,
        "upper_bound": [1188, 18],
    }
    identity = store.publish(
        boundary.formal_dir / "failure-release.json",
        record,
        "formal failure release",
    )
    state.attempt.failure_pre_release_identity = identity
    if reference_retained:
        state.attempt.observer_identity = identity
        state.attempt.pre_unref_cleanup_identity = identity
        state.observer_identity = identity
        state.pre_unref_identity = identity
    return identity


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
    state.attempt.detached_incomplete_identity = identity
    return {
        "detached_incomplete_identity": identity,
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
    }


def _publish_failure_raw_lock_release(
    *,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    detached_identity: Mapping[str, object],
    failure_pre_release_identity: Mapping[str, object],
    guardian_absence_identity: Mapping[str, object],
) -> dict[str, object]:
    """Release the supervisor lease only after detached failure replay/guardian absence."""

    checked_detached = closeout_state.validate_identity_join(
        detached_identity,
        "failure detached substantive replay",
    )
    checked_failure = closeout_state.validate_identity_join(
        failure_pre_release_identity,
        "failure pre-release",
    )
    checked_guardian = closeout_state.validate_identity_join(
        guardian_absence_identity,
        "failure guardian absence",
    )
    if (
        state.attempt.failure_pre_release_identity != checked_failure
        or state.attempt.detached_incomplete_identity != checked_detached
        or state.attempt.lock_release_attempted
        or host.locks_released
    ):
        raise IrreversibleFormalFailure(
            "failure raw release crossed its detached/lock boundary"
        )
    lock_identities = host.lock_evidence()
    closeout_state.begin_supervisor_lock_release(state.attempt)
    release_effect = host.release_locks_once()
    closeout_state.record_supervisor_lock_release_return(
        state.attempt,
        release_effect,
    )
    selection: dict[str, object] | str = (
        state.selection_identity
        if state.selection_identity is not None
        else "absent"
    )
    record = {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_CLAIMS),
        "campaign_root_identity": context["campaign_root_identity"],
        "created_at_utc": _utc_now(),
        "detached_substantive_identity": checked_detached,
        "detached_substantive_kind": "incomplete_v4",
        "failure_pre_release_identity": checked_failure,
        "formal_selection_identity": selection,
        "guardian_absence_identity": checked_guardian,
        "guardian_close_identity": "combined-in-guardian-absence",
        "lock_identities": lock_identities,
        "manager_epoch": dict(context["manager_epoch"]),
        "outcome": "INCOMPLETE",
        "package_id": context["package_id"],
        "schema_version": closeout_state.SUPERVISOR_RAW_LOCK_RELEASE_SCHEMA,
        "status": "INCOMPLETE",
        "supervisor_release": {
            "after_guardian_absence": True,
            "attempted": True,
            "recorded": True,
            "returned": True,
        },
    }
    expected = {
        "campaign_root_identity": context["campaign_root_identity"],
        "formal_selection_identity": selection,
        "manager_epoch": context["manager_epoch"],
        "package_id": context["package_id"],
    }
    path = context["outer_spec"]["receipt_paths"][
        "supervisor_raw_lock_release"
    ]
    identity = _publish_tracked_phase(
        state.attempt,
        store,
        key="supervisor-raw-lock-release",
        path=path,
        record=record,
        validator=success_verifier.validate_supervisor_raw_lock_release,
        validator_kwargs={
            "expected": expected,
            "expected_lock_identities": lock_identities,
            "expected_detached_substantive_identity": checked_detached,
            "expected_detached_substantive_kind": "incomplete_v4",
            "expected_failure_pre_release_identity": checked_failure,
            "expected_guardian_absence_identity": checked_guardian,
            "expected_guardian_close_identity": (
                "combined-in-guardian-absence"
            ),
        },
    )
    state.attempt.supervisor_raw_lock_release_identity = identity
    state.supervisor_raw_lock_release_identity = identity
    return {
        "lock_identities": lock_identities,
        "lock_release_effect": release_effect,
        "supervisor_raw_lock_release_identity": identity,
    }


def _failure_reference_completion(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    failure_pre_release_identity: Mapping[str, object],
    observer_identity: Mapping[str, object] | None = None,
    pre_unref_cleanup_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Complete the retained RefUnit after raw release, or report exact uncertainty."""

    absent: dict[str, object] = {
        "kind": "NO_REFERENCE_OPENED",
        "post_unref_absence_identity": "absent",
        "reference_connection_close_identity": "absent",
        "reference_release_identity": "absent",
        "reference_terminal_identity": "absent",
        "uncertainty_terminal": "absent",
    }
    if state.attempt.acquire_identity is None:
        terminal = _failure_reference_terminal(state)
        if terminal["kind"] == "NO_REFERENCE_OPENED":
            return absent
        return {
            **absent,
            "kind": "CONNECTION_UNCERTAIN",
            "uncertainty_terminal": terminal,
        }
    if (
        state.selection_identity is None
        or state.outer_identity is None
        or state.supervisor_raw_lock_release_identity is None
        or not host.locks_released
    ):
        raise IrreversibleFormalFailure(
            "failure RefUnit completion lacks its post-raw predecessor chain"
        )
    checked_failure = closeout_state.validate_identity_join(
        failure_pre_release_identity,
        "failure RefUnit pre-release basis",
    )
    checked_observer = closeout_state.validate_identity_join(
        observer_identity if observer_identity is not None else checked_failure,
        "failure RefUnit observer basis",
    )
    checked_pre_unref = closeout_state.validate_identity_join(
        (
            pre_unref_cleanup_identity
            if pre_unref_cleanup_identity is not None
            else checked_failure
        ),
        "failure RefUnit pre-Unref basis",
    )
    expected = _normal_expected(context, state.selection_identity)
    unit_name = str(state.outer_identity["unit_name"])
    attempt = state.attempt
    if not attempt.release_attempted:
        released = closeout_state.release_reference_retained_once(
            boundary,
            attempt,
            store,
            unit_name=unit_name,
            observer_identity=checked_observer,
            pre_unref_cleanup_identity=checked_pre_unref,
        )
        if released.get("kind") != "RECORDED_CONNECTION_RETAINED":
            return {
                **absent,
                "kind": "CONNECTION_UNCERTAIN",
                "uncertainty_terminal": _failure_reference_terminal(state),
            }
    elif (
        attempt.connection_action
        or not attempt.release_returned
        or attempt.release_return is None
        or attempt.unref_call_identity is None
        or attempt.reference_release_identity is None
    ):
        if not attempt.connection_action:
            terminal = closeout_state.finalize_reference_once(
                boundary,
                attempt,
                store,
                unit_name=unit_name,
                prove_unref=False,
                reason="POST_RAW_REFERENCE_RELEASE_UNCERTAIN",
            )
            state.reference_terminal = dict(terminal)
        return {
            **absent,
            "kind": "CONNECTION_UNCERTAIN",
            "uncertainty_terminal": _failure_reference_terminal(state),
        }
    unref_record, unref_identity = store.document(
        boundary.formal_dir / "unref-call.json",
        "failure Unref call",
    )
    success_verifier.validate_unref_call(
        unref_record,
        expected=expected,
        expected_outer_identity=state.outer_identity,
        expected_acquisition_identity=cast(
            Mapping[str, object],
            state.attempt.acquire_identity,
        ),
        expected_client_unique_name=str(
            cast(Mapping[str, object], state.attempt.acquire_return)[
                "client_unique_name"
            ]
        ),
        expected_observer_identity=checked_observer,
        expected_pre_unref_cleanup_identity=checked_pre_unref,
    )
    paths = state.selection["outer_spec"]["receipt_paths"]
    release_record, release_identity = store.document(
        paths["reference_release"],
        "failure reference release",
    )
    success_verifier.validate_reference_release(
        release_record,
        expected=expected,
        expected_outer_identity=state.outer_identity,
        expected_acquisition_identity=cast(
            Mapping[str, object],
            state.attempt.acquire_identity,
        ),
        expected_unref_call_identity=unref_identity,
        expected_observer_identity=checked_observer,
        expected_pre_unref_cleanup_identity=checked_pre_unref,
        expected_raw_lock_release_identity=cast(
            Mapping[str, object],
            state.supervisor_raw_lock_release_identity,
        ),
    )
    post = host.wait_state(
        unit_name,
        str(state.outer_identity["control_group"]),
        state.outer_identity["processes"],
        referenced=False,
        timeout=RECORD_WAIT_SECONDS,
    )
    post_record = _common_receipt(
        context,
        state.selection_identity,
        phase="post_unref_absence",
        cgroup_absent=post["cgroup_absent"],
        load_state={
            "reference_release_identity": release_identity,
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
    closed = closeout_state.close_released_reference_once(
        boundary,
        state.attempt,
        store,
        unit_name=unit_name,
        post_unref_absence_identity=post_identity,
    )
    if closed.get("kind") != "RECORDED_CONNECTION_CLOSED":
        return {
            "kind": "CONNECTION_UNCERTAIN",
            "post_unref_absence_identity": post_identity,
            "reference_connection_close_identity": "unrecorded",
            "reference_release_identity": release_identity,
            "reference_terminal_identity": (
                state.attempt.reference_terminal_identity or "unrecorded"
            ),
            "uncertainty_terminal": _failure_reference_terminal(state),
        }
    terminal_identity = cast(
        Mapping[str, object],
        state.attempt.reference_terminal_identity,
    )
    close_identity = cast(
        Mapping[str, object],
        state.attempt.reference_connection_close_identity,
    )
    terminal_record, terminal_readback = store.document(
        paths["reference_terminal"],
        "failure reference terminal",
    )
    checked_terminal = success_verifier.validate_reference_terminal(
        terminal_record,
        expected=expected,
        expected_outer_identity=state.outer_identity,
        expected_acquisition_identity=cast(
            Mapping[str, object],
            state.attempt.acquire_identity,
        ),
        expected_release_identity=release_identity,
        expected_unref_call_identity=unref_identity,
        expected_post_unref_absence_identity=post_identity,
        expected_client_unique_name=str(
            cast(Mapping[str, object], state.attempt.acquire_return)[
                "client_unique_name"
            ]
        ),
    )
    close_record, close_readback = store.document(
        paths["reference_connection_close"],
        "failure reference connection close",
    )
    success_verifier.validate_reference_connection_close(
        close_record,
        expected=expected,
        expected_outer_identity=state.outer_identity,
        expected_reference_terminal_identity=terminal_identity,
        expected_connection_verification=cast(
            Mapping[str, object],
            checked_terminal["connection_verification"],
        ),
    )
    if terminal_readback != terminal_identity or close_readback != close_identity:
        raise IrreversibleFormalFailure(
            "failure reference terminal/connection close readback drifted"
        )
    return {
        "kind": "RECORDED_CONNECTION_CLOSED",
        "post_unref_absence_identity": post_identity,
        "reference_connection_close_identity": close_identity,
        "reference_release_identity": release_identity,
        "reference_terminal_identity": terminal_identity,
        "uncertainty_terminal": "absent",
    }


def _reference_completion_snapshot(
    state: SupervisorState,
) -> dict[str, object]:
    """Capture a post-raw terminal reference state without inventing proof."""

    attempt = state.attempt
    if attempt.reference_connection_close_identity is not None:
        return {
            "kind": "RECORDED_CONNECTION_CLOSED",
            "post_unref_absence_identity": closeout_state.validate_identity_join(
                attempt.post_unref_absence_identity,
                "failure snapshot post-Unref absence",
            ),
            "reference_connection_close_identity": (
                closeout_state.validate_identity_join(
                    attempt.reference_connection_close_identity,
                    "failure snapshot connection close",
                )
            ),
            "reference_release_identity": closeout_state.validate_identity_join(
                attempt.reference_release_identity,
                "failure snapshot reference release",
            ),
            "reference_terminal_identity": closeout_state.validate_identity_join(
                attempt.reference_terminal_identity,
                "failure snapshot reference terminal",
            ),
            "uncertainty_terminal": "absent",
        }
    if attempt.acquire_identity is None:
        terminal = _failure_reference_terminal(state)
        if terminal["kind"] == "NO_REFERENCE_OPENED":
            return {
                "kind": "NO_REFERENCE_OPENED",
                "post_unref_absence_identity": "absent",
                "reference_connection_close_identity": "absent",
                "reference_release_identity": "absent",
                "reference_terminal_identity": "absent",
                "uncertainty_terminal": "absent",
            }
    terminal = _failure_reference_terminal(state)

    def optional(value: Mapping[str, object] | None) -> dict[str, object] | str:
        return (
            "unrecorded"
            if value is None
            else closeout_state.validate_identity_join(
                value,
                "failure uncertain reference identity",
            )
        )

    return {
        "kind": "CONNECTION_UNCERTAIN",
        "post_unref_absence_identity": optional(
            attempt.post_unref_absence_identity
        ),
        "reference_connection_close_identity": optional(
            attempt.reference_connection_close_identity
        ),
        "reference_release_identity": optional(
            attempt.reference_release_identity
        ),
        "reference_terminal_identity": optional(
            attempt.reference_terminal_identity
        ),
        "uncertainty_terminal": terminal,
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
    guardian_absence_identity: Mapping[str, object],
    supervisor_raw_lock_release_identity: Mapping[str, object],
    reference_completion: Mapping[str, object],
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
    checked_guardian = closeout_state.validate_identity_join(
        guardian_absence_identity,
        "failure terminal guardian absence",
    )
    checked_raw = closeout_state.validate_identity_join(
        supervisor_raw_lock_release_identity,
        "failure terminal raw lock release",
    )
    checked_completion = dict(reference_completion)
    terminal_basis = {
        "branch": "incomplete",
        "detached_substantive_identity": detached_identity,
        "detached_substantive_kind": detached_substantive_kind,
        "failure_pre_release_identity": checked_failure,
        "guardian_absence_identity": checked_guardian,
        "lock_identities": checked_locks,
        "reference_completion": checked_completion,
        "schema_version": FINAL_TERMINAL_PREDECESSOR_JOIN_SCHEMA,
        "supervisor_raw_lock_release_identity": checked_raw,
    }

    def build_failure_terminal(
        post_root_closure: Mapping[str, object],
    ) -> Mapping[str, object]:
        return {
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
            "guardian_absence_identity": checked_guardian,
            "lock_identities": checked_locks,
            "lock_release_effect": checked_release,
            "lower_bound": "absent",
            "outcome": "INCOMPLETE",
            "package_id": context["package_id"],
            "phase": phase,
            "post_root_closure": dict(post_root_closure),
            "production_authority_changed": False,
            "production_certified": False,
            "reference_completion": checked_completion,
            "retry_eligible": False,
            "schema_version": FAILURE_TERMINAL_RELEASE_SCHEMA,
            "stage_b_changed": False,
            "status": "INCOMPLETE_RELEASED",
            "success_eligible": False,
            "supervisor_raw_lock_release_identity": checked_raw,
            "terminal_join": {
                "broker_absent_before_manifest": True,
                "detached_substantive_before_guardian_absence": True,
                "formal_root_closed_before_outside_replays": True,
                "guardian_absence_before_raw_lock_release": True,
                "outside_replays_before_final_join": True,
                "raw_lock_release_before_reference_completion": True,
                "recovery_disarmed_before_manifest": True,
                "reference_connection_close_before_final_join": (
                    checked_completion.get("kind")
                    == "RECORDED_CONNECTION_CLOSED"
                ),
                "reference_uncertainty_is_terminal": (
                    checked_completion.get("kind")
                    in {"CONNECTION_UNCERTAIN", "NO_REFERENCE_OPENED"}
                ),
            },
            "upper_bound": [1188, 18],
        }

    tail = _complete_post_reference_budget_tail(
        context=context,
        state=state,
        branch="incomplete",
        reference_completion=checked_completion,
        terminal_basis=terminal_basis,
        terminal_record_builder=build_failure_terminal,
    )
    record = cast(Mapping[str, object], tail["terminal_record"])
    identity = closeout_state.validate_identity_join(
        cast(Mapping[str, object], tail["selected_identity"]),
        "incomplete outside-root final release",
    )
    release_paths = context.get("formal_final_release_paths")
    if (
        type(release_paths) is not dict
        or set(release_paths) != {"incomplete", "success"}
        or identity["path"] != release_paths["incomplete"]
    ):
        raise IrreversibleFormalFailure(
            "incomplete final release escaped its fixed outside-root path"
        )
    success_verifier.validate_failure_terminal_release(
        record,
        context=context,
        expected_identity=identity,
        expected_lock_identities=checked_locks,
        expected_detached_substantive_identity=detached_identity,
        expected_detached_substantive_kind=detached_substantive_kind,
        expected_failure_pre_release_identity=checked_failure,
        expected_selection_identity=state.selection_identity,
        expected_guardian_absence_identity=checked_guardian,
        expected_raw_lock_release_identity=checked_raw,
        expected_reference_completion=checked_completion,
        expected_post_root_closure=cast(
            Mapping[str, object],
            tail["post_root_closure"],
        ),
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
    failure_pre_release_identity: Mapping[str, object],
    guardian_absence_callback: Callable[[], Mapping[str, object]] | None = None,
    guardian_absence_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    del guardian_absence_identity
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
    if guardian_absence_callback is None:
        raise IrreversibleFormalFailure(
            "legacy pre-detached guardian absence is disabled"
        )
    checked_guardian_absence = closeout_state.validate_identity_join(
        guardian_absence_callback(),
        "failure guardian absence",
    )
    if state.attempt.guardian_absence_identity is None:
        state.attempt.guardian_absence_identity = checked_guardian_absence
    elif state.attempt.guardian_absence_identity != checked_guardian_absence:
        raise IrreversibleFormalFailure(
            "failure guardian absence identity changed before lock release"
        )
    detached_identity = closeout_state.validate_identity_join(
        cast(
            Mapping[str, object],
            detached["detached_incomplete_identity"],
        ),
        "detached incomplete before failure raw release",
    )
    raw = _publish_failure_raw_lock_release(
        context=context,
        state=state,
        store=store,
        host=host,
        detached_identity=detached_identity,
        failure_pre_release_identity=failure_pre_release_identity,
        guardian_absence_identity=checked_guardian_absence,
    )
    try:
        completion = _failure_reference_completion(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            host=host,
            failure_pre_release_identity=failure_pre_release_identity,
        )
    except BaseException as exc:
        item = _failure("FAILURE_REFERENCE_COMPLETION_FAILED_OR_UNCERTAIN", exc)
        if item not in state.attempt.errors:
            state.attempt.errors.append(item)
        completion = _reference_completion_snapshot(state)
    terminal_identity = _publish_failure_terminal_release(
        boundary=boundary,
        context=context,
        state=state,
        store=store,
        phase=phase,
        lock_identities=checked_locks,
        lock_release_effect=raw["lock_release_effect"],
        detached_substantive_identity=detached_identity,
        detached_substantive_kind="incomplete_v4",
        failure_pre_release_identity=failure_pre_release_identity,
        guardian_absence_identity=checked_guardian_absence,
        supervisor_raw_lock_release_identity=cast(
            Mapping[str, object],
            raw["supervisor_raw_lock_release_identity"],
        ),
        reference_completion=completion,
    )
    return {
        **detached,
        "failure_terminal_release_identity": terminal_identity,
        "guardian_absence_identity": checked_guardian_absence,
        "lock_release": raw["lock_release_effect"],
        "reference_completion": completion,
        "supervisor_raw_lock_release_identity": raw[
            "supervisor_raw_lock_release_identity"
        ],
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
    phase = (
        "DIRECTORY_CREATED_MARKER_UNRECORDED"
        if state.attempt.directory_created
        and state.attempt.marker_identity is None
        else _failure_phase(state)
    )
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


def _prepare_failure_pre_release(
    *,
    boundary: authority.FormalRuntimeBoundary,
    context: Mapping[str, object],
    state: SupervisorState,
    store: closeout_helper.ReceiptStore,
    host: closeout_helper.PinnedHost,
    error: BaseException,
) -> dict[str, object]:
    """Freeze/contain the finite ledger and publish a locks-held failure basis."""

    phase = (
        "DIRECTORY_CREATED_MARKER_UNRECORDED"
        if state.attempt.directory_created
        and state.attempt.marker_identity is None
        else _failure_phase(state)
    )
    if state.attempt.marker_identity is not None:
        if state.attempt.incomplete_identity is None:
            closeout_state.publish_consumed_incomplete(
                boundary,
                state.attempt,
                store,
                phase="PROSPECTIVE_FAILURE_CHAIN",
                failure_record=_failure("FORMAL_CAMPAIGN_FAILED", error),
            )
    elif not state.attempt.directory_created:
        raise IrreversibleFormalFailure(
            "formal failure has no consumed no-overwrite root"
        )
    elif _recorded_incomplete_identity(state.attempt) == "unrecorded":
        raise IrreversibleFormalFailure(
            "markerless formal attempt lacks its canonical incomplete receipt"
        )

    if (
        state.attempt.reference is not None
        and state.attempt.acquire_identity is None
        and not state.attempt.connection_action
    ):
        unit_name = (
            str(state.selection["outer_spec"]["unit_name"])
            if state.selection is not None
            else str(context["outer_spec"]["unit_name"])
        )
        dropped = closeout_state.finalize_reference_once(
            boundary,
            state.attempt,
            store,
            unit_name=unit_name,
            prove_unref=False,
            reason="ACQUIRE_UNPROVEN_FAILURE_BEFORE_DETACHED_REPLAY",
        )
        state.reference_terminal = dict(dropped)
        if dropped.get("kind") in {
            "CONNECTION_DROP_FAILED_OR_UNCERTAIN",
            "CONNECTION_DROPPED_RECEIPT_UNRECORDED",
        }:
            raise IrreversibleFormalFailure(
                "unproven RefUnit connection could not be canonically dropped"
            )

    if state.selection is None:
        ledger = initial_ledger(
            _outer_inactive_identity(str(context["outer_spec"]["unit_name"]))
        )
    else:
        frozen_outer = _freeze_failure_outer(state=state, host=host)
        if (
            state.ledger is not None
            and state.attempt.barrier_identity is not None
            and state.child_audit_identity is None
        ):
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
            state.child_audit_identity = child["identity"]
            ledger = closeout_helper.bind_outer_ledger(child, frozen_outer)
        elif state.ledger is not None:
            ledger = closeout_state.validate_frozen_ledger(state.ledger)
            ledger["outer"] = frozen_outer
        else:
            ledger = initial_ledger(frozen_outer)
        outer = ledger["outer"]
        owned = (
            [str(outer["unit_name"])]
            if outer["identity_complete"] is True
            and (
                outer["invocation_id"]
                or outer["control_group"]
                or outer["processes"]
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
            "prospective failure containment",
        ):
            if item not in state.attempt.errors:
                state.attempt.errors.append(item)
        state.ledger = ledger
        if outer["identity_complete"] is True and outer["unit_name"]:
            state.outer_identity = {
                key: outer[key]
                for key in (
                    "control_group",
                    "invocation_id",
                    "processes",
                    "unit_name",
                )
            }

    reference_state = _failure_reference_state(state, context=context)
    quiescence = _wait_failure_quiescence(
        host=host,
        ledger=ledger,
        attempt=state.attempt,
        reference_retained=reference_state["kind"] == "HELD",
    )
    locks = host.lock_evidence()
    failure_identity = _publish_failure_release(
        boundary=boundary,
        context=context,
        state=state,
        store=store,
        phase=phase,
        ledger=ledger,
        runtime_quiescence=quiescence,
        reference_state=reference_state,
        lock_identities=locks,
    )
    return {
        "failure_pre_release_identity": failure_identity,
        "ledger": ledger,
        "lock_identities": locks,
        "phase": phase,
        "reference_state": reference_state,
        "runtime_quiescence": quiescence,
    }


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
        if (
            state.guardian_absence_identity is None
            or state.supervisor_raw_lock_release_identity is None
        ):
            raise IrreversibleFormalFailure(
                "released late failure lacks guardian/raw-release joins"
            )
        try:
            reference_completion = _failure_reference_completion(
                boundary=boundary,
                context=context,
                state=state,
                store=store,
                host=host,
                failure_pre_release_identity="absent",
            )
        except BaseException as exc:
            item = _failure(
                "FAILURE_REFERENCE_COMPLETION_FAILED_OR_UNCERTAIN",
                exc,
            )
            if item not in state.attempt.errors:
                state.attempt.errors.append(item)
            reference_completion = _reference_completion_snapshot(state)
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
            guardian_absence_identity=state.guardian_absence_identity,
            supervisor_raw_lock_release_identity=(
                state.supervisor_raw_lock_release_identity
            ),
            reference_completion=reference_completion,
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


def _close_failed_campaign_v4(
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
    """Prospective failure chain with RefUnit retained through raw lock release."""

    state.failure = _failure("FORMAL_CAMPAIGN_FAILED", error)
    if state.failure not in state.attempt.errors:
        state.attempt.errors.append(state.failure)
    if host.locks_released:
        if (
            state.detached_success_identity is None
            or state.guardian_absence_identity is None
            or state.supervisor_raw_lock_release_identity is None
            or type(state.attempt.lock_release_return) is not dict
            or state.selection_identity is None
        ):
            raise IrreversibleFormalFailure(
                "post-raw failure lacks its locks-held substantive chain"
            )
        if (
            state.attempt.acquire_identity is not None
            and state.attempt.reference_connection_close_identity is None
            and not state.attempt.connection_action
        ):
            if state.observer_identity is None or state.pre_unref_identity is None:
                raise IrreversibleFormalFailure(
                    "post-raw failure lacks its success cleanup basis"
                )
            completion = _failure_reference_completion(
                boundary=boundary,
                context=context,
                state=state,
                store=store,
                host=host,
                failure_pre_release_identity=state.pre_unref_identity,
                observer_identity=state.observer_identity,
                pre_unref_cleanup_identity=state.pre_unref_identity,
            )
        else:
            completion = _reference_completion_snapshot(state)
        terminal = _publish_failure_terminal_release(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            phase=_failure_phase(state),
            lock_identities=cast(
                Sequence[Mapping[str, object]],
                state.selection["lock_identities"],
            ),
            lock_release_effect=state.attempt.lock_release_return,
            detached_substantive_identity=state.detached_success_identity,
            detached_substantive_kind="success_v3",
            failure_pre_release_identity="absent",
            guardian_absence_identity=state.guardian_absence_identity,
            supervisor_raw_lock_release_identity=(
                state.supervisor_raw_lock_release_identity
            ),
            reference_completion=completion,
        )
        return {
            "failure_terminal_release_identity": terminal,
            "formal_selection_identity": state.selection_identity,
            "outcome": "INCOMPLETE",
            "phase": _failure_phase(state),
            "reference_completion": completion,
        }
    prepared = _prepare_failure_pre_release(
        boundary=boundary,
        context=context,
        state=state,
        store=store,
        host=host,
        error=error,
    )

    def guardian_absence() -> Mapping[str, object]:
        if state.selection_identity is None:
            closed = _close_preselection(
                context=context,
                state=state,
                admission_identity=admission_identity,
                store=store,
                host=host,
            )
            identity = closed["guardian_absence_identity"]
            if type(identity) is not dict:
                raise IrreversibleFormalFailure(
                    "markerless/unselected failure lacks guardian absence"
                )
            return identity
        port = FailureContainmentPort(
            boundary=boundary,
            context=context,
            state=state,
            store=store,
            host=host,
            latch=latch,
        )
        return port.prepare_guardian_release(
            cast(Mapping[str, object], prepared["ledger"])
        )

    completed = _complete_pre_release_failure(
        boundary=boundary,
        context=context,
        state=state,
        store=store,
        host=host,
        phase=str(prepared["phase"]),
        lock_identities=cast(
            Sequence[Mapping[str, object]],
            prepared["lock_identities"],
        ),
        failure_pre_release_identity=cast(
            Mapping[str, object],
            prepared["failure_pre_release_identity"],
        ),
        guardian_absence_callback=guardian_absence,
    )
    return {
        **prepared,
        **completed,
        "formal_selection_identity": (
            state.selection_identity
            if state.selection_identity is not None
            else "absent"
        ),
        "outcome": "INCOMPLETE",
    }


def run_formal_campaign(
    campaign_dir: Path | str,
    *,
    capabilities: FormalSupervisorCapabilities | None = None,
) -> dict[str, object]:
    """Consume exactly one externally selected formal AB16 campaign."""

    checked_capabilities = _validate_formal_supervisor_capabilities(
        capabilities
    )
    store = closeout_helper.ReceiptStore(
        budget_backend=checked_capabilities.budget_backend,
        budget_bindings=checked_capabilities.receipt_budget_bindings,
    )
    boundary, context, admission, admission_identity = load_formal_admission(
        campaign_dir
    )
    expected_receipt_bindings = context.get(
        "formal_receipt_budget_bindings"
    )
    if (
        type(expected_receipt_bindings) is not dict
        or expected_receipt_bindings
        != {
            path: dict(binding)
            for path, binding in sorted(
                checked_capabilities.receipt_budget_bindings.items()
            )
        }
    ):
        raise FormalCampaignError(
            "formal supervisor receipt budget bindings do not equal the "
            "package-bound context"
        )
    held_locks = acquire_formal_locks()
    host = closeout_helper.PinnedHost(boundary, held_locks)
    try:
        initial_lock_identities = host.lock_evidence()
        resource_gate = validate_resource_gate(
            context["campaign_dir"],
            authority_context=context,
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
        checked_capabilities.terminal_tail_port.bind_closure_process_baseline(
            resource_gate
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
    state = SupervisorState(
        terminal_tail_port=checked_capabilities.terminal_tail_port,
    )
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
            transition_result = dict(
                checked_capabilities.selection_transition.
                bind_formal_selection(selection_identity)
            )
            if transition_result.get("selection_identity") != (
                selection_identity
            ):
                raise IrreversibleFormalFailure(
                    "formal supervisor broker selection transition drifted"
                )
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
                phase="guardian and raw supervisor lock release after detached replay",
            )
            raw_release = _release_guardian_and_raw_locks(
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
            terminal = _complete_reference_and_final_success(
                boundary=boundary,
                context=context,
                state=state,
                store=store,
                host=host,
                latch=latch,
                expected=_normal_expected(
                    context,
                    selection_identity,
                ),
                lock_identities=cast(
                    Sequence[Mapping[str, object]],
                    raw_release["lock_identities"],
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
                closeout = _close_failed_campaign_v4(
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
            **raw_release,
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


def main(
    argv: Sequence[str] | None = None,
    *,
    formal_supervisor_capabilities: FormalSupervisorCapabilities | None = None,
) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = run_formal_campaign(
            arguments.campaign_dir,
            capabilities=formal_supervisor_capabilities,
        )
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
