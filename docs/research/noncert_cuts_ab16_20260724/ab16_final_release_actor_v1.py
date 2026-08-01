#!/usr/bin/env python3
"""Package-pinned, outside-root final release actor for prospective AB16.

The actor is deliberately later than formal-root closure.  It owns exactly
one retained parent directory descriptor and four non-refundable,
preallocated staging extents.  It first publishes one receipt for each of
the two package-pinned replays and may then publish exactly one of the fixed
success/failure terminal leaves only after:

* the RefUnit lifecycle has reached its exact terminal state;
* the recovery, broker, and closure actors are absent;
* the formal root has been closed by the single-use closure actor; and
* two distinct package-pinned outside-root replayers accepted the same byte
  graph.

The unselected staging inode is sealed read-only in place.  A request, reply,
ACK, descriptor, or publication uncertainty is terminal and is never
retryable.  This research-only role grants no witness, cut, bound,
production, certified, or Stage-B authority.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import os
from pathlib import Path
import secrets
import select
import socket
import stat
from typing import Final, cast

from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_budget_broker_v1 as broker,
)


PACKAGE_ROLE: Final = "ab16-final-release-actor-v1"
ACTOR_SCHEMA: Final = "noncert-cuts-ab16-final-release-actor-v1"
READY_SCHEMA: Final = "noncert-cuts-ab16-final-release-actor-ready-v1"
REQUEST_SCHEMA: Final = "noncert-cuts-ab16-final-release-request-v1"
RESPONSE_SCHEMA: Final = "noncert-cuts-ab16-final-release-response-v1"
HANDOFF_SCHEMA: Final = "noncert-cuts-ab16-final-release-owner-handoff-v1"
REPLAY_RECEIPT_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-root-replay-receipt-v1"
)
EVIDENCE_SCHEMA: Final = "noncert-cuts-ab16-post-root-closure-evidence-v1"
RESULT_SCHEMA: Final = "noncert-cuts-ab16-final-release-result-v1"
PRIMARY_REPLAY_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-root-outside-replay-primary-v1"
)
ALTERNATE_REPLAY_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-root-outside-replay-alternate-v1"
)
CLOSURE_RESULT_SCHEMA: Final = "noncert-cuts-ab16-closure-result-v2"
SUCCESS_TERMINAL_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-dual-lock-release-v4"
)
FAILURE_TERMINAL_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-failure-terminal-release-v5"
)
SUCCESS_TARGET: Final = "dual-lock-release.json"
FAILURE_TARGET: Final = "failure-terminal-release.json"
PRIMARY_REPLAY_TARGET: Final = "formal-root-replay-primary.json"
ALTERNATE_REPLAY_TARGET: Final = "formal-root-replay-alternate.json"
SHA256_HEX = frozenset("0123456789abcdef")
FALSE_AUTHORITY: Final = {
    "changes_certified_exact": False,
    "changes_cut_state": False,
    "changes_lower_bound": False,
    "changes_production": False,
    "changes_upper_bound": False,
    "research_only": True,
}


class FinalReleaseProtocolError(RuntimeError):
    """The outside-root final release protocol failed closed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _exact_keys(
    value: Mapping[str, object],
    expected: set[str],
    *,
    label: str,
) -> None:
    if set(value) != expected:
        raise FinalReleaseProtocolError(
            "FRAME_SHAPE_MISMATCH",
            f"{label} keys differ",
        )


def _sha256(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in SHA256_HEX for character in value)
    ):
        raise FinalReleaseProtocolError(
            "IDENTITY_DRIFT",
            f"{label} is not SHA-256",
        )
    return value


def _nonce(value: object) -> str:
    return _sha256(value, label="nonce")


def _content_identity(
    value: object,
    *,
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or set(value) != {"sha256", "size_bytes"}:
        raise FinalReleaseProtocolError(
            "IDENTITY_DRIFT",
            f"{label} content identity shape differs",
        )
    digest = _sha256(value["sha256"], label=f"{label}.sha256")
    size = value["size_bytes"]
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise FinalReleaseProtocolError(
            "IDENTITY_DRIFT",
            f"{label}.size_bytes is invalid",
        )
    return {"sha256": digest, "size_bytes": size}


def _artifact_identity(
    value: object,
    *,
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "path",
        "sha256",
        "size_bytes",
    }:
        raise FinalReleaseProtocolError(
            "IDENTITY_DRIFT",
            f"{label} artifact identity shape differs",
        )
    path = value["path"]
    if not isinstance(path, str) or not path:
        raise FinalReleaseProtocolError(
            "IDENTITY_DRIFT",
            f"{label}.path is invalid",
        )
    identity = _content_identity(
        {
            "sha256": value["sha256"],
            "size_bytes": value["size_bytes"],
        },
        label=label,
    )
    return {"path": path, **identity}


def _message_identity(value: object) -> dict[str, object]:
    raw = broker.canonical_json_bytes(value)
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _process_actor(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "schema_version",
        "pid",
        "pid_starttime",
        "uid",
    }:
        raise FinalReleaseProtocolError(
            "ACTOR_IDENTITY_DRIFT",
            f"{label} actor shape differs",
        )
    if (
        isinstance(value["pid"], bool)
        or not isinstance(value["pid"], int)
        or value["pid"] <= 0
        or isinstance(value["pid_starttime"], bool)
        or not isinstance(value["pid_starttime"], int)
        or value["pid_starttime"] <= 0
        or isinstance(value["uid"], bool)
        or not isinstance(value["uid"], int)
        or value["uid"] < 0
    ):
        raise FinalReleaseProtocolError(
            "ACTOR_IDENTITY_DRIFT",
            f"{label} actor scalar differs",
        )
    return dict(value)


def _parent_identity(descriptor: int) -> dict[str, object]:
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        raise FinalReleaseProtocolError(
            "PARENT_IDENTITY_DRIFT",
            "final-release parent FD is not a directory",
        )
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode_octal": f"{stat.S_IMODE(metadata.st_mode):04o}",
        "uid": metadata.st_uid,
    }


def _directory_identity(path: Path) -> dict[str, object]:
    try:
        descriptor = broker.budget._open_absolute_directory_no_symlinks(  # noqa: SLF001
            path
        )
    except Exception as exc:
        raise FinalReleaseProtocolError(
            "PARENT_JOIN_FAILED",
            "final-release directory cannot be opened without symlinks",
        ) from exc
    try:
        return _parent_identity(descriptor)
    finally:
        os.close(descriptor)


def _replay_result(
    value: object,
    *,
    schema: str,
    implementation: str,
    label: str,
) -> dict[str, object]:
    expected = {
        "actor_absence",
        "authority",
        "authority_scope",
        "formal_manifest_identity",
        "formal_root",
        "implementation",
        "manifest_entries_sha256",
        "schema_version",
        "state",
        "terminal_join_sha256",
    }
    if type(value) is not dict:
        raise FinalReleaseProtocolError(
            "REPLAY_DRIFT",
            f"{label} result is not one object",
        )
    _exact_keys(value, expected, label=label)
    manifest = _artifact_identity(
        value["formal_manifest_identity"],
        label=f"{label} formal manifest",
    )
    root = value["formal_root"]
    absence = value["actor_absence"]
    if (
        value["schema_version"] != schema
        or value["implementation"] != implementation
        or value["state"] != "FORMAL_ROOT_CLOSURE_ACCEPTED"
        or value["authority_scope"] != "AB16_RESEARCH_ONLY"
        or value["authority"] != FALSE_AUTHORITY
        or type(root) is not dict
        or set(root) != {"device", "inode", "mode_octal", "path", "uid"}
        or type(absence) is not dict
        or set(absence) != {"broker", "closure", "recovery"}
    ):
        raise FinalReleaseProtocolError(
            "REPLAY_DRIFT",
            f"{label} discriminator or root shape differs",
        )
    for role in ("broker", "closure", "recovery"):
        observation = absence[role]
        if (
            type(observation) is not dict
            or observation.get("state") != "EXACT_ACTOR_ABSENT"
            or type(observation.get("actor")) is not dict
        ):
            raise FinalReleaseProtocolError(
                "REPLAY_DRIFT",
                f"{label} {role} absence differs",
            )
    result = dict(value)
    result["formal_manifest_identity"] = manifest
    result["manifest_entries_sha256"] = _sha256(
        value["manifest_entries_sha256"],
        label=f"{label}.manifest_entries_sha256",
    )
    result["terminal_join_sha256"] = _sha256(
        value["terminal_join_sha256"],
        label=f"{label}.terminal_join_sha256",
    )
    return result


def _terminal_request(
    payload: Mapping[str, object],
    *,
    formal_root_path: Path,
    expected_primary_source: Mapping[str, object],
    expected_alternate_source: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    _exact_keys(
        payload,
        {
            "alternate_replay",
            "alternate_replay_receipt_identity",
            "alternate_replay_source_identity",
            "branch",
            "closure_result",
            "primary_replay",
            "primary_replay_receipt_identity",
            "primary_replay_source_identity",
            "reference_completion",
            "terminal_join_sha256",
            "terminal_record",
        },
        label="final release payload",
    )
    branch = payload["branch"]
    if branch not in {"success", "incomplete"}:
        raise FinalReleaseProtocolError(
            "BRANCH_DRIFT",
            "final release branch differs",
        )
    terminal_join_sha256 = _sha256(
        payload["terminal_join_sha256"],
        label="terminal join",
    )
    primary_source = _content_identity(
        payload["primary_replay_source_identity"],
        label="primary replay source",
    )
    alternate_source = _content_identity(
        payload["alternate_replay_source_identity"],
        label="alternate replay source",
    )
    if (
        primary_source != dict(expected_primary_source)
        or alternate_source != dict(expected_alternate_source)
        or primary_source["sha256"] == alternate_source["sha256"]
    ):
        raise FinalReleaseProtocolError(
            "REPLAY_SOURCE_DRIFT",
            "outside replay source identities are absent, mixed, or collapsed",
        )
    primary_receipt = _artifact_identity(
        payload["primary_replay_receipt_identity"],
        label="primary replay receipt",
    )
    alternate_receipt = _artifact_identity(
        payload["alternate_replay_receipt_identity"],
        label="alternate replay receipt",
    )
    root_prefix = formal_root_path.resolve(strict=False)
    for receipt in (primary_receipt, alternate_receipt):
        receipt_path = Path(cast(str, receipt["path"])).resolve(strict=False)
        if receipt_path == root_prefix or receipt_path.is_relative_to(root_prefix):
            raise FinalReleaseProtocolError(
                "REPLAY_RECEIPT_INSIDE_ROOT",
                "outside replay receipt is inside the closed formal root",
            )
    if primary_receipt["path"] == alternate_receipt["path"]:
        raise FinalReleaseProtocolError(
            "REPLAY_RECEIPT_COLLAPSED",
            "outside replay receipts share one path",
        )
    primary = _replay_result(
        payload["primary_replay"],
        schema=PRIMARY_REPLAY_SCHEMA,
        implementation="package-pinned-primary-v1",
        label="primary replay",
    )
    alternate = _replay_result(
        payload["alternate_replay"],
        schema=ALTERNATE_REPLAY_SCHEMA,
        implementation="package-pinned-stdlib-alternate-v1",
        label="alternate replay",
    )
    comparable_fields = {
        "actor_absence",
        "authority",
        "authority_scope",
        "formal_manifest_identity",
        "formal_root",
        "manifest_entries_sha256",
        "state",
        "terminal_join_sha256",
    }
    primary_root = cast(Mapping[str, object], primary["formal_root"])
    primary_manifest = cast(
        Mapping[str, object],
        primary["formal_manifest_identity"],
    )
    if (
        any(primary[field] != alternate[field] for field in comparable_fields)
        or primary["terminal_join_sha256"] != terminal_join_sha256
        or Path(cast(str, primary_root["path"])).resolve(strict=False)
        != root_prefix
    ):
        raise FinalReleaseProtocolError(
            "REPLAY_DISAGREEMENT",
            "outside replayers did not accept the same closed byte graph",
        )
    closure = payload["closure_result"]
    if type(closure) is not dict or set(closure) != {
        "budget_terminal_identity",
        "control_endpoint_absence",
        "final_closure_actor_descriptors",
        "final_release_binding",
        "final_same_uid_process_scope",
        "final_writable_root_descriptor_scan",
        "formal_manifest_identity",
        "recovery_terminal_identity",
        "schema_version",
        "state",
    }:
        raise FinalReleaseProtocolError(
            "CLOSURE_RESULT_DRIFT",
            "closure result shape differs",
        )
    if (
        closure["schema_version"] != CLOSURE_RESULT_SCHEMA
        or closure["state"] != "ROOT_CLOSED_NO_WRITERS"
        or _content_identity(
            {
                "sha256": cast(Mapping[str, object], closure["formal_manifest_identity"])[
                    "sha256"
                ],
                "size_bytes": cast(
                    Mapping[str, object],
                    closure["formal_manifest_identity"],
                )["size_bytes"],
            },
            label="closure formal manifest",
        )
        != {
            "sha256": primary_manifest["sha256"],
            "size_bytes": primary_manifest["size_bytes"],
        }
    ):
        raise FinalReleaseProtocolError(
            "CLOSURE_RESULT_DRIFT",
            "closure result does not bind the replayed manifest",
        )
    reference = payload["reference_completion"]
    if type(reference) is not dict or reference.get("kind") not in {
        "CONNECTION_UNCERTAIN",
        "NO_REFERENCE_OPENED",
        "RECORDED_CONNECTION_CLOSED",
    }:
        raise FinalReleaseProtocolError(
            "REFERENCE_TERMINAL_DRIFT",
            "RefUnit completion is absent or malformed",
        )
    if branch == "success" and reference["kind"] != "RECORDED_CONNECTION_CLOSED":
        raise FinalReleaseProtocolError(
            "REFERENCE_TERMINAL_DRIFT",
            "success final release lacks a closed RefUnit connection",
        )
    evidence = {
        "schema_version": EVIDENCE_SCHEMA,
        "alternate_replay_identity": _message_identity(alternate),
        "alternate_replay_receipt_identity": alternate_receipt,
        "alternate_replay_source_identity": alternate_source,
        "branch": branch,
        "closure_result_identity": _message_identity(closure),
        "formal_manifest_identity": primary["formal_manifest_identity"],
        "primary_replay_identity": _message_identity(primary),
        "primary_replay_receipt_identity": primary_receipt,
        "primary_replay_source_identity": primary_source,
        "reference_completion_identity": _message_identity(reference),
        "state": "CLOSED_ROOT_DUAL_REPLAY_ACCEPTED",
        "terminal_join_sha256": terminal_join_sha256,
    }
    terminal = payload["terminal_record"]
    if type(terminal) is not dict:
        raise FinalReleaseProtocolError(
            "TERMINAL_RECORD_DRIFT",
            "final terminal record is not one object",
        )
    expected_schema = (
        SUCCESS_TERMINAL_SCHEMA
        if branch == "success"
        else FAILURE_TERMINAL_SCHEMA
    )
    expected_outcome = "VERIFIED" if branch == "success" else "INCOMPLETE"
    if (
        terminal.get("schema_version") != expected_schema
        or terminal.get("outcome") != expected_outcome
        or terminal.get("authority_scope") != "AB16_RESEARCH_ONLY"
        or terminal.get("production_certified") is not False
        or terminal.get("production_authority_changed") is not False
        or terminal.get("bounds_changed") is not False
        or terminal.get("upper_bound") != [1188, 18]
        or terminal.get("lower_bound") != "absent"
        or terminal.get("post_root_closure") != evidence
    ):
        raise FinalReleaseProtocolError(
            "TERMINAL_RECORD_DRIFT",
            "final terminal record does not bind the accepted closure evidence",
        )
    return dict(terminal), evidence


class _FinalReleaseServer:
    def __init__(
        self,
        connection: socket.socket,
        *,
        parent_fd: int,
        success_fd: int,
        failure_fd: int,
        primary_replay_fd: int,
        alternate_replay_fd: int,
        success_extent: Mapping[str, object],
        failure_extent: Mapping[str, object],
        primary_replay_extent: Mapping[str, object],
        alternate_replay_extent: Mapping[str, object],
        formal_root_path: Path,
        release_root_path: Path,
        expected_peer: Mapping[str, int],
        actor: Mapping[str, object],
        nonce: str,
        primary_replay_source_identity: Mapping[str, object],
        alternate_replay_source_identity: Mapping[str, object],
    ) -> None:
        self.connection = connection
        self.parent_fd = parent_fd
        self.success_fd = success_fd
        self.failure_fd = failure_fd
        self.primary_replay_fd = primary_replay_fd
        self.alternate_replay_fd = alternate_replay_fd
        self.success_extent = broker.validate_prepared_extent(success_extent)
        self.failure_extent = broker.validate_prepared_extent(failure_extent)
        self.primary_replay_extent = broker.validate_prepared_extent(
            primary_replay_extent
        )
        self.alternate_replay_extent = broker.validate_prepared_extent(
            alternate_replay_extent
        )
        self.formal_root_path = formal_root_path
        self.release_root_path = release_root_path
        self.expected_peer = dict(expected_peer)
        self.actor = dict(actor)
        self.nonce = _nonce(nonce)
        self.primary_source = _content_identity(
            primary_replay_source_identity,
            label="expected primary replay source",
        )
        self.alternate_source = _content_identity(
            alternate_replay_source_identity,
            label="expected alternate replay source",
        )
        self._published_replays: dict[
            str, dict[str, object]
        ] = {}
        self._validate_extent_ownership()

    def _validate_extent_ownership(self) -> None:
        parent_identity = _parent_identity(self.parent_fd)
        if (
            parent_identity != self.success_extent["parent_identity"]
            or parent_identity != self.failure_extent["parent_identity"]
            or parent_identity
            != self.primary_replay_extent["parent_identity"]
            or parent_identity
            != self.alternate_replay_extent["parent_identity"]
            or parent_identity != _directory_identity(self.release_root_path)
            or self.success_extent["target_name"] != SUCCESS_TARGET
            or self.failure_extent["target_name"] != FAILURE_TARGET
            or self.primary_replay_extent["target_name"]
            != PRIMARY_REPLAY_TARGET
            or self.alternate_replay_extent["target_name"]
            != ALTERNATE_REPLAY_TARGET
            or self.success_extent["artifact_class"] != "closeout"
            or self.failure_extent["artifact_class"] != "closeout"
            or self.primary_replay_extent["artifact_class"] != "closeout"
            or self.alternate_replay_extent["artifact_class"] != "closeout"
            or broker._identity(self.success_fd)  # noqa: SLF001
            != self.success_extent["staging_identity"]
            or broker._identity(self.failure_fd)  # noqa: SLF001
            != self.failure_extent["staging_identity"]
            or broker._identity(self.primary_replay_fd)  # noqa: SLF001
            != self.primary_replay_extent["staging_identity"]
            or broker._identity(self.alternate_replay_fd)  # noqa: SLF001
            != self.alternate_replay_extent["staging_identity"]
        ):
            raise FinalReleaseProtocolError(
                "EXTENT_IDENTITY_DRIFT",
                "outside-root final-release extent identity differs",
            )
        formal_identity = _directory_identity(self.formal_root_path)
        formal_absolute = Path(os.path.abspath(self.formal_root_path))
        release_absolute = Path(os.path.abspath(self.release_root_path))
        if (
            release_absolute == formal_absolute
            or release_absolute.is_relative_to(formal_absolute)
            or (
                formal_identity["device"],
                formal_identity["inode"],
            )
            == (
                parent_identity["device"],
                parent_identity["inode"],
            )
        ):
            raise FinalReleaseProtocolError(
                "RELEASE_ROOT_INSIDE_FORMAL_ROOT",
                "final release parent collapsed into the closed formal root",
            )

    def _seal_unselected(self, descriptor: int) -> dict[str, object]:
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
        identity = broker._identity(descriptor)  # noqa: SLF001
        if identity["mode_octal"] != "0444":
            raise FinalReleaseProtocolError(
                "UNSELECTED_SEAL_DRIFT",
                "unselected release staging inode is not read-only",
            )
        return identity

    def _close_owned(self, *, seal: bool) -> None:
        errors: list[BaseException] = []
        if seal:
            for descriptor in (
                self.success_fd,
                self.failure_fd,
                self.primary_replay_fd,
                self.alternate_replay_fd,
            ):
                if descriptor < 0:
                    continue
                try:
                    os.fchmod(descriptor, 0o444)
                    os.fsync(descriptor)
                except BaseException as exc:
                    errors.append(exc)
        for attribute in (
            "success_fd",
            "failure_fd",
            "primary_replay_fd",
            "alternate_replay_fd",
            "parent_fd",
        ):
            descriptor = getattr(self, attribute)
            if descriptor < 0:
                continue
            setattr(self, attribute, -1)
            try:
                os.close(descriptor)
            except BaseException as exc:
                errors.append(exc)
        if errors:
            primary = FinalReleaseProtocolError(
                "OWNERSHIP_RELEASE_UNCERTAIN",
                "final-release FD cleanup is uncertain",
            )
            for error in errors:
                primary.add_note(f"{type(error).__name__}: {error}")
            raise primary

    def _request(
        self,
        *,
        action: str,
        sequence: int,
    ) -> Mapping[str, object]:
        frame = broker.receive_frame(
            self.connection,
            require_message_credentials=True,
        )
        peer = {
            key: frame.peer[key]
            for key in ("pid", "pid_starttime", "uid")
        }
        expected_peer = {
            key: self.expected_peer[key]
            for key in ("pid", "pid_starttime", "uid")
        }
        request = frame.record
        if (
            peer != expected_peer
            or request.get("schema_version") != REQUEST_SCHEMA
            or request.get("action") != action
            or request.get("nonce") != self.nonce
            or request.get("sequence") != sequence
            or type(request.get("payload")) is not dict
        ):
            raise FinalReleaseProtocolError(
                "REQUEST_IDENTITY_DRIFT",
                f"{action} request identity differs",
            )
        return cast(Mapping[str, object], request["payload"])

    def _acknowledge(
        self,
        *,
        action: str,
        sequence: int,
        result: Mapping[str, object],
    ) -> None:
        acknowledgement = broker.receive_frame(
            self.connection,
            require_message_credentials=True,
        )
        expected = {
            "schema_version": REQUEST_SCHEMA,
            "action": action,
            "nonce": self.nonce,
            "payload": {
                "result_sha256": _message_identity(result)["sha256"],
            },
            "sequence": sequence,
        }
        if acknowledgement.record != expected:
            raise FinalReleaseProtocolError(
                "ACK_IDENTITY_DRIFT",
                f"{action} is absent or uncertain",
            )

    def _publish_replay_receipt(
        self,
        *,
        implementation: str,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        _exact_keys(
            payload,
            {"implementation", "result", "source_identity"},
            label=f"{implementation} replay receipt",
        )
        if payload["implementation"] != implementation:
            raise FinalReleaseProtocolError(
                "REPLAY_DRIFT",
                "replay receipt implementation differs",
            )
        if implementation == "primary":
            schema = PRIMARY_REPLAY_SCHEMA
            discriminator = "package-pinned-primary-v1"
            source = self.primary_source
            extent = self.primary_replay_extent
            descriptor = self.primary_replay_fd
        elif implementation == "alternate":
            schema = ALTERNATE_REPLAY_SCHEMA
            discriminator = "package-pinned-stdlib-alternate-v1"
            source = self.alternate_source
            extent = self.alternate_replay_extent
            descriptor = self.alternate_replay_fd
        else:
            raise FinalReleaseProtocolError(
                "REPLAY_DRIFT",
                "replay receipt implementation is unknown",
            )
        supplied_source = _content_identity(
            payload["source_identity"],
            label=f"{implementation} replay source",
        )
        result = _replay_result(
            payload["result"],
            schema=schema,
            implementation=discriminator,
            label=f"{implementation} replay",
        )
        formal_root = cast(Mapping[str, object], result["formal_root"])
        if (
            supplied_source != source
            or Path(cast(str, formal_root["path"])).resolve(strict=False)
            != self.formal_root_path.resolve(strict=False)
            or implementation in self._published_replays
        ):
            raise FinalReleaseProtocolError(
                "REPLAY_DRIFT",
                "replay source, root, or exact-once state differs",
            )
        receipt = {
            "authority": FALSE_AUTHORITY,
            "authority_scope": "AB16_RESEARCH_ONLY",
            "implementation": implementation,
            "result": result,
            "schema_version": REPLAY_RECEIPT_SCHEMA,
            "source_identity": source,
            "state": "FORMAL_ROOT_REPLAY_RECEIPT_ACCEPTED",
        }
        published = broker.publish_preallocated_extent(
            extent,
            parent_fd=self.parent_fd,
            staging_fd=descriptor,
            raw=broker.canonical_json_bytes(receipt),
        )
        identity = {
            "path": str(
                self.release_root_path
                / cast(str, extent["target_name"])
            ),
            "sha256": published["sha256"],
            "size_bytes": published["size_bytes"],
        }
        envelope: dict[str, object] = {
            "receipt_identity": _artifact_identity(
                identity,
                label=f"{implementation} replay receipt",
            ),
            "result": result,
            "source_identity": source,
        }
        self._published_replays[implementation] = envelope
        return envelope

    def run(self) -> int:
        broker.send_frame(
            self.connection,
            {
                "schema_version": READY_SCHEMA,
                "actor": self.actor,
                "nonce": self.nonce,
                "state": "READY_OUTSIDE_ROOT_FIXED_EXTENTS",
            },
        )
        publication_may_have_happened = False
        current_sequence = 1
        try:
            for implementation in ("primary", "alternate"):
                payload = self._request(
                    action="PUBLISH_REPLAY_RECEIPT",
                    sequence=current_sequence,
                )
                publication_may_have_happened = True
                result = self._publish_replay_receipt(
                    implementation=implementation,
                    payload=payload,
                )
                broker.send_frame(
                    self.connection,
                    {
                        "schema_version": RESPONSE_SCHEMA,
                        "action": "PUBLISH_REPLAY_RECEIPT",
                        "actor": self.actor,
                        "nonce": self.nonce,
                        "result": result,
                        "sequence": current_sequence,
                        "status": "PASS",
                    },
                )
                current_sequence += 1
                self._acknowledge(
                    action="REPLAY_RECEIPT_ACK",
                    sequence=current_sequence,
                    result=result,
                )
                current_sequence += 1

            payload = self._request(
                action="PUBLISH_FINAL_RELEASE",
                sequence=current_sequence,
            )
            terminal, evidence = _terminal_request(
                payload,
                formal_root_path=self.formal_root_path,
                expected_primary_source=self.primary_source,
                expected_alternate_source=self.alternate_source,
            )
            if (
                payload["primary_replay"]
                != self._published_replays["primary"]["result"]
                or payload["primary_replay_receipt_identity"]
                != self._published_replays["primary"]["receipt_identity"]
                or payload["alternate_replay"]
                != self._published_replays["alternate"]["result"]
                or payload["alternate_replay_receipt_identity"]
                != self._published_replays["alternate"][
                    "receipt_identity"
                ]
            ):
                raise FinalReleaseProtocolError(
                    "REPLAY_RECEIPT_DRIFT",
                    "final release differs from the actor-published replay receipts",
                )
            branch = cast(str, payload["branch"])
            selected_extent, selected_fd, unused_fd = (
                (
                    self.success_extent,
                    self.success_fd,
                    self.failure_fd,
                )
                if branch == "success"
                else (
                    self.failure_extent,
                    self.failure_fd,
                    self.success_fd,
                )
            )
            publication_may_have_happened = True
            selected_identity = broker.publish_preallocated_extent(
                selected_extent,
                parent_fd=self.parent_fd,
                staging_fd=selected_fd,
                raw=broker.canonical_json_bytes(terminal),
            )
            unused_identity = self._seal_unselected(unused_fd)
            os.fsync(self.parent_fd)
            if _parent_identity(self.parent_fd) != _directory_identity(
                self.release_root_path
            ):
                raise FinalReleaseProtocolError(
                    "PARENT_JOIN_FAILED",
                    "final-release absolute parent identity drifted",
                )
            result = {
                "schema_version": RESULT_SCHEMA,
                "branch": branch,
                "evidence": evidence,
                "selected_identity": selected_identity,
                "state": "FINAL_RELEASE_PUBLISHED_UNUSED_SEALED",
                "unused_staging_identity": unused_identity,
            }
            broker.send_frame(
                self.connection,
                {
                    "schema_version": RESPONSE_SCHEMA,
                    "action": "PUBLISH_FINAL_RELEASE",
                    "actor": self.actor,
                    "nonce": self.nonce,
                    "result": result,
                    "sequence": current_sequence,
                    "status": "PASS",
                },
            )
            current_sequence += 1
            self._acknowledge(
                action="FINAL_RELEASE_ACK",
                sequence=current_sequence,
                result=result,
            )
            self._close_owned(seal=True)
            return 0
        except BaseException as exc:
            try:
                broker.send_frame(
                    self.connection,
                    {
                        "schema_version": RESPONSE_SCHEMA,
                        "action": "FAIL_CLOSED",
                        "actor": self.actor,
                        "code": getattr(exc, "code", type(exc).__name__),
                        "nonce": self.nonce,
                        "result": {
                            "message": str(exc),
                            "publication_may_have_happened": (
                                publication_may_have_happened
                            ),
                            "retry_eligible": False,
                        },
                        "sequence": current_sequence,
                        "status": "FAIL_CLOSED",
                    },
                )
            except BaseException:
                pass
            try:
                self._close_owned(seal=True)
            except BaseException:
                pass
            return 2
        finally:
            try:
                self.connection.close()
            except BaseException:
                pass


class FinalReleaseProcess:
    """Supervisor handle for one package-pinned outside-root final actor."""

    def __init__(
        self,
        *,
        pid: int,
        pidfd: int,
        pidfd_method: str,
        connection: socket.socket,
        nonce: str,
        actor: Mapping[str, object],
        source_identity: Mapping[str, object],
        ready_handshake_identity: Mapping[str, object],
        primary_replay_source_identity: Mapping[str, object],
        alternate_replay_source_identity: Mapping[str, object],
    ) -> None:
        self.pid = pid
        self.pidfd = pidfd
        self.pidfd_method = pidfd_method
        self.connection = connection
        self.nonce = _nonce(nonce)
        self.actor = dict(actor)
        self.source_identity = _content_identity(
            source_identity,
            label="final-release actor source",
        )
        self.ready_handshake_identity = _content_identity(
            ready_handshake_identity,
            label="final-release READY handshake",
        )
        self.primary_replay_source_identity = _content_identity(
            primary_replay_source_identity,
            label="primary replay source",
        )
        self.alternate_replay_source_identity = _content_identity(
            alternate_replay_source_identity,
            label="alternate replay source",
        )
        self._next_sequence = 1
        self._replay_receipts: dict[
            str, dict[str, object]
        ] = {}
        self._terminal_attempted = False
        self._exit_proved = False
        self._close_attempted = False

    def publish_replay_receipt(
        self,
        *,
        implementation: str,
        result: Mapping[str, object],
    ) -> dict[str, object]:
        expected_implementation = (
            "primary"
            if not self._replay_receipts
            else (
                "alternate"
                if set(self._replay_receipts) == {"primary"}
                else None
            )
        )
        if implementation != expected_implementation:
            raise FinalReleaseProtocolError(
                "REPLAY_RECEIPT_ALREADY_ATTEMPTED",
                "replay receipt order or exact-once state differs",
            )
        source = (
            self.primary_replay_source_identity
            if implementation == "primary"
            else self.alternate_replay_source_identity
        )
        sequence = self._next_sequence
        # Cross the no-retry boundary before sending: a lost reply cannot
        # prove that rename/fsync did not happen.
        self._replay_receipts[implementation] = {}
        broker.send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "PUBLISH_REPLAY_RECEIPT",
                "nonce": self.nonce,
                "payload": {
                    "implementation": implementation,
                    "result": dict(result),
                    "source_identity": source,
                },
                "sequence": sequence,
            },
        )
        response = broker.receive_frame(
            self.connection,
            require_message_credentials=True,
        )
        record = response.record
        envelope = record.get("result")
        if (
            record.get("status") != "PASS"
            or record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("action") != "PUBLISH_REPLAY_RECEIPT"
            or record.get("actor") != self.actor
            or record.get("nonce") != self.nonce
            or record.get("sequence") != sequence
            or type(envelope) is not dict
            or set(envelope)
            != {"receipt_identity", "result", "source_identity"}
            or envelope["result"] != dict(result)
            or envelope["source_identity"] != source
        ):
            raise FinalReleaseProtocolError(
                str(record.get("code", "REPLAY_RECEIPT_FAIL_CLOSED")),
                "replay receipt publication failed or response drifted",
            )
        _artifact_identity(
            envelope["receipt_identity"],
            label=f"{implementation} replay receipt",
        )
        broker.send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "REPLAY_RECEIPT_ACK",
                "nonce": self.nonce,
                "payload": {
                    "result_sha256": _message_identity(envelope)["sha256"],
                },
                "sequence": sequence + 1,
            },
        )
        self._next_sequence += 2
        self._replay_receipts[implementation] = dict(envelope)
        return dict(envelope)

    def publish_final_release(
        self,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        if (
            self._terminal_attempted
            or set(self._replay_receipts)
            != {"primary", "alternate"}
            or any(not record for record in self._replay_receipts.values())
        ):
            raise FinalReleaseProtocolError(
                "FINAL_RELEASE_ALREADY_ATTEMPTED",
                "final release is duplicate or precedes both replay receipts",
            )
        self._terminal_attempted = True
        sequence = self._next_sequence
        broker.send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "PUBLISH_FINAL_RELEASE",
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": sequence,
            },
        )
        response = broker.receive_frame(
            self.connection,
            require_message_credentials=True,
        )
        record = response.record
        result = record.get("result")
        if (
            record.get("status") != "PASS"
            or record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("action") != "PUBLISH_FINAL_RELEASE"
            or record.get("actor") != self.actor
            or record.get("nonce") != self.nonce
            or record.get("sequence") != sequence
            or type(result) is not dict
        ):
            raise FinalReleaseProtocolError(
                str(record.get("code", "FINAL_RELEASE_FAIL_CLOSED")),
                (
                    str(result.get("message", "final release failed closed"))
                    if type(result) is dict
                    else "final release response differs"
                ),
            )
        broker.send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "FINAL_RELEASE_ACK",
                "nonce": self.nonce,
                "payload": {
                    "result_sha256": _message_identity(result)["sha256"],
                },
                "sequence": sequence + 1,
            },
        )
        self._next_sequence += 2
        return dict(result)

    def prove_exit(self, *, timeout_milliseconds: int = 5000) -> None:
        if self._exit_proved:
            raise FinalReleaseProtocolError(
                "PROCESS_ALREADY_WAITED",
                "final-release exit cannot be proved twice",
            )
        poller = select.poll()
        poller.register(self.pidfd, select.POLLIN | select.POLLHUP)
        if not poller.poll(timeout_milliseconds):
            raise FinalReleaseProtocolError(
                "ACTOR_EXIT_NOT_PROVED",
                "final-release actor pidfd did not report exit",
            )
        self._exit_proved = True

    def close(self) -> None:
        if self._close_attempted:
            return
        self._close_attempted = True
        errors: list[BaseException] = []
        try:
            self.connection.close()
        except BaseException as exc:
            errors.append(exc)
        descriptor = self.pidfd
        self.pidfd = -1
        try:
            os.close(descriptor)
        except BaseException as exc:
            errors.append(exc)
        if errors:
            primary = FinalReleaseProtocolError(
                "OWNERSHIP_RELEASE_UNCERTAIN",
                "final-release control or pidfd close failed",
            )
            for error in errors:
                primary.add_note(
                    f"{type(error).__name__}: {error}"
                )
            raise primary


def spawn_persistent_final_release(
    *,
    formal_root: Path,
    release_root: Path,
    parent_fd: int,
    success_fd: int,
    failure_fd: int,
    primary_replay_fd: int,
    alternate_replay_fd: int,
    success_extent: Mapping[str, object],
    failure_extent: Mapping[str, object],
    primary_replay_extent: Mapping[str, object],
    alternate_replay_extent: Mapping[str, object],
    primary_replay_source_identity: Mapping[str, object],
    alternate_replay_source_identity: Mapping[str, object],
    source_identity: Mapping[str, object],
    expected_peer: Mapping[str, int],
    nonce: str | None = None,
) -> FinalReleaseProcess:
    """Fork the package-pinned role with only its fixed outside-root FDs."""

    session_nonce = secrets.token_hex(32) if nonce is None else _nonce(nonce)
    parent, child = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    parent.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    child.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    peer = {
        key: expected_peer[key]
        for key in ("pid", "pid_starttime", "uid")
    }
    pid = os.fork()
    if pid == 0:
        parent.close()
        actor = {
            "schema_version": ACTOR_SCHEMA,
            **broker.process_identity(),
        }
        code = 2
        try:
            broker.close_unlisted_descriptors(
                {
                    child.fileno(),
                    parent_fd,
                    success_fd,
                    failure_fd,
                    primary_replay_fd,
                    alternate_replay_fd,
                }
            )
            server = _FinalReleaseServer(
                child,
                parent_fd=parent_fd,
                success_fd=success_fd,
                failure_fd=failure_fd,
                primary_replay_fd=primary_replay_fd,
                alternate_replay_fd=alternate_replay_fd,
                success_extent=success_extent,
                failure_extent=failure_extent,
                primary_replay_extent=primary_replay_extent,
                alternate_replay_extent=alternate_replay_extent,
                formal_root_path=formal_root,
                release_root_path=release_root,
                expected_peer=peer,
                actor=actor,
                nonce=session_nonce,
                primary_replay_source_identity=primary_replay_source_identity,
                alternate_replay_source_identity=(
                    alternate_replay_source_identity
                ),
            )
            code = server.run()
        except BaseException:
            code = 2
        os._exit(code)
    child_close_attempted = False
    parent_close_attempted = False
    parent_descriptor_entries = [
        ("final-release parent", parent_fd),
        ("final-release success extent", success_fd),
        ("final-release failure extent", failure_fd),
        ("final-release primary replay extent", primary_replay_fd),
        ("final-release alternate replay extent", alternate_replay_fd),
    ]
    parent_descriptor_close_attempted = [
        False for _entry in parent_descriptor_entries
    ]

    def close_parent_descriptors() -> None:
        primary: BaseException | None = None
        for index, (label, descriptor) in enumerate(
            parent_descriptor_entries
        ):
            if parent_descriptor_close_attempted[index]:
                continue
            parent_descriptor_close_attempted[index] = True
            try:
                os.close(descriptor)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        f"{label} close also failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
        if primary is not None:
            raise primary

    pidfd = -1
    pidfd_method = ""
    ready_phase_started = False
    try:
        child_close_attempted = True
        child.close()
        close_parent_descriptors()
        pidfd, pidfd_method = broker.open_pidfd(pid)
        ready_phase_started = True
        ready = broker.receive_frame(
            parent,
            require_message_credentials=True,
        ).record
        actor = _process_actor(ready.get("actor"), label="ready")
        if (
            ready.get("schema_version") != READY_SCHEMA
            or ready.get("state") != "READY_OUTSIDE_ROOT_FIXED_EXTENTS"
            or ready.get("nonce") != session_nonce
            or actor["pid"] != pid
            or actor["pid_starttime"] != broker.process_starttime(pid)
        ):
            raise FinalReleaseProtocolError(
                "READY_IDENTITY_DRIFT",
                "final-release actor READY differs",
            )
        process = FinalReleaseProcess(
            pid=pid,
            pidfd=pidfd,
            pidfd_method=pidfd_method,
            connection=parent,
            nonce=session_nonce,
            actor=actor,
            source_identity=source_identity,
            ready_handshake_identity=_message_identity(ready),
            primary_replay_source_identity=(
                primary_replay_source_identity
            ),
            alternate_replay_source_identity=(
                alternate_replay_source_identity
            ),
        )
        pidfd = -1
        return process
    except BaseException as exc:
        if not child_close_attempted:
            child_close_attempted = True
            broker.preserve_spawn_cleanup_failure(
                exc,
                label="final-release child socket",
                cleanup=child.close,
            )
        broker.preserve_spawn_cleanup_failure(
            exc,
            label="final-release parent capabilities",
            cleanup=close_parent_descriptors,
        )
        if not parent_close_attempted:
            parent_close_attempted = True
            broker.preserve_spawn_cleanup_failure(
                exc,
                label="final-release parent control",
                cleanup=parent.close,
            )
        broker.terminate_and_reap_spawned_child(pid, primary=exc)
        if pidfd >= 0:
            owned_pidfd = pidfd
            pidfd = -1
            broker.preserve_spawn_cleanup_failure(
                exc,
                label="final-release pidfd",
                cleanup=lambda: os.close(owned_pidfd),
            )
        if not ready_phase_started:
            raise
        if isinstance(exc, FinalReleaseProtocolError):
            raise
        raise FinalReleaseProtocolError(
            "READY_IDENTITY_DRIFT",
            "final-release actor exited before one verified READY",
        ) from exc


def spawn_final_release_for_test(
    *,
    formal_root: Path,
    release_root: Path,
    parent_fd: int,
    success_fd: int,
    failure_fd: int,
    primary_replay_fd: int,
    alternate_replay_fd: int,
    success_extent: Mapping[str, object],
    failure_extent: Mapping[str, object],
    primary_replay_extent: Mapping[str, object],
    alternate_replay_extent: Mapping[str, object],
    primary_replay_source_identity: Mapping[str, object],
    alternate_replay_source_identity: Mapping[str, object],
    source_identity: Mapping[str, object],
    nonce: str | None = None,
) -> FinalReleaseProcess:
    """Fork the role for zero-authority focused tests; not a formal launcher."""

    return spawn_persistent_final_release(
        formal_root=formal_root,
        release_root=release_root,
        parent_fd=parent_fd,
        success_fd=success_fd,
        failure_fd=failure_fd,
        primary_replay_fd=primary_replay_fd,
        alternate_replay_fd=alternate_replay_fd,
        success_extent=success_extent,
        failure_extent=failure_extent,
        primary_replay_extent=primary_replay_extent,
        alternate_replay_extent=alternate_replay_extent,
        primary_replay_source_identity=primary_replay_source_identity,
        alternate_replay_source_identity=alternate_replay_source_identity,
        source_identity=source_identity,
        expected_peer=broker.process_identity(),
        nonce=nonce,
    )


def attach_broker_forked_final_release(
    handoff: Mapping[str, object],
    descriptors: tuple[int, ...],
) -> FinalReleaseProcess:
    """Accept the broker's sole final-release control and pidfd transfer.

    The final actor already owns the outside parent and all four staging extents;
    the supervisor receives only the connected control socket and actor pidfd.
    """

    expected = {
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
    if set(handoff) != expected or len(descriptors) != 2:
        for descriptor in descriptors:
            os.close(descriptor)
        raise FinalReleaseProtocolError(
            "BROKER_HANDOFF_SHAPE_DRIFT",
            "final-release handoff shape or FD count differs",
        )
    control_fd, pidfd = descriptors
    connection: socket.socket | None = None
    try:
        actor = _process_actor(handoff["actor"], label="handoff")
        source = _content_identity(
            handoff["role_source_identity"],
            label="final-release actor source",
        )
        _content_identity(
            handoff["primary_replay_source_identity"],
            label="handoff primary replay source",
        )
        _content_identity(
            handoff["alternate_replay_source_identity"],
            label="handoff alternate replay source",
        )
        prepared_identity = _content_identity(
            handoff["prepared_release_identity"],
            label="prepared final release",
        )
        ready_handshake_identity = _content_identity(
            handoff["ready_handshake_identity"],
            label="final-release READY handshake",
        )
        control_identity = handoff["control_descriptor_identity"]
        if (
            handoff["schema_version"] != HANDOFF_SCHEMA
            or handoff["role"] != PACKAGE_ROLE
            or type(handoff["broker_actor"]) is not dict
            or type(handoff["formal_root_path"]) is not str
            or not handoff["formal_root_path"]
            or type(handoff["release_root_path"]) is not str
            or not handoff["release_root_path"]
            or type(control_identity) is not dict
            or control_identity != broker._identity(control_fd)  # noqa: SLF001
            or not isinstance(handoff["pidfd_method"], str)
            or actor["pid_starttime"]
            != broker.process_starttime(cast(int, actor["pid"]))
            or broker._pidfd_target_pid(pidfd)  # noqa: SLF001
            != actor["pid"]
            or broker.pidfd_reports_exit(pidfd)
            or cast(int, prepared_identity["size_bytes"]) <= 0
        ):
            raise FinalReleaseProtocolError(
                "BROKER_HANDOFF_IDENTITY_DRIFT",
                "final-release handoff identity differs",
            )
        connection = socket.socket(fileno=control_fd)
        broker._socket_type(connection)  # noqa: SLF001
        return FinalReleaseProcess(
            pid=cast(int, actor["pid"]),
            pidfd=pidfd,
            pidfd_method=cast(str, handoff["pidfd_method"]),
            connection=connection,
            nonce=_nonce(handoff["nonce"]),
            actor=actor,
            source_identity=source,
            ready_handshake_identity=ready_handshake_identity,
            primary_replay_source_identity=cast(
                Mapping[str, object],
                handoff["primary_replay_source_identity"],
            ),
            alternate_replay_source_identity=cast(
                Mapping[str, object],
                handoff["alternate_replay_source_identity"],
            ),
        )
    except BaseException:
        if connection is None:
            os.close(control_fd)
        else:
            connection.close()
        os.close(pidfd)
        raise


__all__ = [
    "ACTOR_SCHEMA",
    "ALTERNATE_REPLAY_SCHEMA",
    "CLOSURE_RESULT_SCHEMA",
    "EVIDENCE_SCHEMA",
    "FAILURE_TERMINAL_SCHEMA",
    "FinalReleaseProcess",
    "FinalReleaseProtocolError",
    "HANDOFF_SCHEMA",
    "PACKAGE_ROLE",
    "PRIMARY_REPLAY_SCHEMA",
    "READY_SCHEMA",
    "REQUEST_SCHEMA",
    "RESPONSE_SCHEMA",
    "RESULT_SCHEMA",
    "SUCCESS_TERMINAL_SCHEMA",
    "attach_broker_forked_final_release",
    "spawn_final_release_for_test",
    "spawn_persistent_final_release",
]
