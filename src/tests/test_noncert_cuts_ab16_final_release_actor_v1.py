from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import sys
from typing import cast

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
sys.path.insert(0, str(RESEARCH))
try:
    from docs.research.noncert_cuts_ab16_20260724 import (
        ab16_budget_broker_v1 as broker,
    )
    from docs.research.noncert_cuts_ab16_20260724 import (
        ab16_final_release_actor_v1 as final_release,
    )
finally:
    sys.path.remove(str(RESEARCH))


MAXIMUM_BYTES = 256 * 1024


def _content_identity(tag: str) -> dict[str, object]:
    raw = tag.encode("utf-8")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _artifact_identity(path: Path, tag: str) -> dict[str, object]:
    return {
        "path": str(path),
        **_content_identity(tag),
    }


def _actor(tag: str) -> dict[str, object]:
    return {
        "schema_version": f"actor-{tag}-v1",
        "pid": 1000 + len(tag),
        "pid_starttime": 2000 + len(tag),
        "uid": os.getuid(),
    }


def _extent(
    parent_fd: int,
    *,
    staging_name: str,
    target_name: str,
) -> tuple[dict[str, object], int]:
    descriptor = os.open(
        staging_name,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
        dir_fd=parent_fd,
    )
    os.posix_fallocate(descriptor, 0, MAXIMUM_BYTES)
    os.fsync(descriptor)
    return (
        {
            "schema_version": broker.PREPARED_EXTENT_SCHEMA,
            "artifact_class": "closeout",
            "maximum_bytes": MAXIMUM_BYTES,
            "parent_identity": broker._parent_identity(parent_fd),  # noqa: SLF001
            "parent_path": ".",
            "staging_identity": broker._identity(descriptor),  # noqa: SLF001
            "staging_name": staging_name,
            "target_name": target_name,
        },
        descriptor,
    )


def _closure_inputs(
    tmp_path: Path,
    formal_root: Path,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    manifest = {
        "path": "formal-closure/formal-manifest.json",
        **_content_identity("manifest"),
    }
    terminal_join = hashlib.sha256(b"terminal-join").hexdigest()
    formal_root_identity = {
        "device": os.stat(formal_root).st_dev,
        "inode": os.stat(formal_root).st_ino,
        "mode_octal": "0700",
        "path": str(formal_root),
        "uid": os.getuid(),
    }
    absence = {
        role: {
            "actor": _actor(role),
            "observed_starttime": None,
            "state": "EXACT_ACTOR_ABSENT",
        }
        for role in ("broker", "closure", "recovery")
    }
    common = {
        "actor_absence": absence,
        "authority": dict(final_release.FALSE_AUTHORITY),
        "authority_scope": "AB16_RESEARCH_ONLY",
        "formal_manifest_identity": manifest,
        "formal_root": formal_root_identity,
        "manifest_entries_sha256": hashlib.sha256(b"entries").hexdigest(),
        "state": "FORMAL_ROOT_CLOSURE_ACCEPTED",
        "terminal_join_sha256": terminal_join,
    }
    primary = {
        **common,
        "implementation": "package-pinned-primary-v1",
        "schema_version": final_release.PRIMARY_REPLAY_SCHEMA,
    }
    alternate = {
        **common,
        "implementation": "package-pinned-stdlib-alternate-v1",
        "schema_version": final_release.ALTERNATE_REPLAY_SCHEMA,
    }
    closure = {
        "schema_version": "noncert-cuts-ab16-closure-result-v2",
        "budget_terminal_identity": {
            "path": "formal-closure/budget-terminal.json",
            **_content_identity("budget"),
        },
        "control_endpoint_absence": {"state": "CONTROL_ENDPOINTS_ABSENT"},
        "final_closure_actor_descriptors": {"state": "FIXED_ALLOWLIST"},
        "final_release_binding": {
            "actor": _actor("final-release"),
            "handoff_identity": _content_identity("final-release-handoff"),
            "phase": "FINAL_CLOSURE_SCOPE",
            "pidfd_method": "python-os.pidfd_open",
            "state": "LIVE_EXACT_FINAL_RELEASE_ACTOR_BOUND",
        },
        "final_same_uid_process_scope": {"state": "NO_CONFLICT"},
        "final_writable_root_descriptor_scan": {
            "excluded_pids": [],
            "observed": [],
            "state": "NO_WRITABLE_ROOT_DESCRIPTORS",
        },
        "formal_manifest_identity": manifest,
        "recovery_terminal_identity": {
            "path": "formal-closure/recovery-disarm-terminal.json",
            **_content_identity("recovery"),
        },
        "state": "ROOT_CLOSED_NO_WRITERS",
    }
    reference = {
        "kind": "RECORDED_CONNECTION_CLOSED",
        "post_unref_absence_identity": _artifact_identity(
            tmp_path / "post-unref.json",
            "post-unref",
        ),
        "reference_connection_close_identity": _artifact_identity(
            tmp_path / "connection-close.json",
            "connection-close",
        ),
        "reference_release_identity": _artifact_identity(
            tmp_path / "reference-release.json",
            "reference-release",
        ),
        "reference_terminal_identity": _artifact_identity(
            tmp_path / "reference-terminal.json",
            "reference-terminal",
        ),
        "uncertainty_terminal": "absent",
    }
    return primary, alternate, closure, reference


def _payload(
    tmp_path: Path,
    formal_root: Path,
    *,
    primary_source: dict[str, object],
    alternate_source: dict[str, object],
    branch: str = "success",
) -> dict[str, object]:
    primary, alternate, closure, reference = _closure_inputs(
        tmp_path,
        formal_root,
    )
    primary_receipt = _artifact_identity(
        tmp_path / "outside-primary" / "receipt.json",
        "primary-receipt",
    )
    alternate_receipt = _artifact_identity(
        tmp_path / "outside-alternate" / "receipt.json",
        "alternate-receipt",
    )
    terminal_join = cast(str, primary["terminal_join_sha256"])
    evidence = {
        "schema_version": final_release.EVIDENCE_SCHEMA,
        "alternate_replay_identity": final_release._message_identity(  # noqa: SLF001
            alternate
        ),
        "alternate_replay_receipt_identity": alternate_receipt,
        "alternate_replay_source_identity": alternate_source,
        "branch": branch,
        "closure_result_identity": final_release._message_identity(  # noqa: SLF001
            closure
        ),
        "formal_manifest_identity": primary["formal_manifest_identity"],
        "primary_replay_identity": final_release._message_identity(  # noqa: SLF001
            primary
        ),
        "primary_replay_receipt_identity": primary_receipt,
        "primary_replay_source_identity": primary_source,
        "reference_completion_identity": final_release._message_identity(  # noqa: SLF001
            reference
        ),
        "state": "CLOSED_ROOT_DUAL_REPLAY_ACCEPTED",
        "terminal_join_sha256": terminal_join,
    }
    terminal = {
        "authority_scope": "AB16_RESEARCH_ONLY",
        "bounds_changed": False,
        "lower_bound": "absent",
        "outcome": "VERIFIED" if branch == "success" else "INCOMPLETE",
        "post_root_closure": evidence,
        "production_authority_changed": False,
        "production_certified": False,
        "schema_version": (
            final_release.SUCCESS_TERMINAL_SCHEMA
            if branch == "success"
            else final_release.FAILURE_TERMINAL_SCHEMA
        ),
        "upper_bound": [1188, 18],
    }
    return {
        "alternate_replay": alternate,
        "alternate_replay_receipt_identity": alternate_receipt,
        "alternate_replay_source_identity": alternate_source,
        "branch": branch,
        "closure_result": closure,
        "primary_replay": primary,
        "primary_replay_receipt_identity": primary_receipt,
        "primary_replay_source_identity": primary_source,
        "reference_completion": reference,
        "terminal_join_sha256": terminal_join,
        "terminal_record": terminal,
    }


def _spawn(
    tmp_path: Path,
) -> tuple[
    final_release.FinalReleaseProcess,
    Path,
    Path,
    dict[str, object],
    dict[str, object],
]:
    formal_root = tmp_path / "formal-root"
    release_root = tmp_path / "outside-final-release"
    formal_root.mkdir()
    release_root.mkdir()
    parent_fd = os.open(
        release_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    success_extent, success_fd = _extent(
        parent_fd,
        staging_name=".success.stage",
        target_name=final_release.SUCCESS_TARGET,
    )
    failure_extent, failure_fd = _extent(
        parent_fd,
        staging_name=".failure.stage",
        target_name=final_release.FAILURE_TARGET,
    )
    primary_replay_extent, primary_replay_fd = _extent(
        parent_fd,
        staging_name=".primary-replay.stage",
        target_name=final_release.PRIMARY_REPLAY_TARGET,
    )
    alternate_replay_extent, alternate_replay_fd = _extent(
        parent_fd,
        staging_name=".alternate-replay.stage",
        target_name=final_release.ALTERNATE_REPLAY_TARGET,
    )
    primary_source = _content_identity("primary-source")
    alternate_source = _content_identity("alternate-source")
    process = final_release.spawn_final_release_for_test(
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
        primary_replay_source_identity=primary_source,
        alternate_replay_source_identity=alternate_source,
        source_identity=_content_identity("final-release-source"),
    )
    return (
        process,
        formal_root,
        release_root,
        primary_source,
        alternate_source,
    )


def _close(process: final_release.FinalReleaseProcess) -> None:
    try:
        process.prove_exit()
    finally:
        process.close()


def test_final_release_close_attempts_control_and_pidfd_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingConnection:
        def __init__(self) -> None:
            self.close_count = 0

        def close(self) -> None:
            self.close_count += 1
            raise RuntimeError("deterministic control close failure")

    sentinel = 987_655
    pidfd_close_count = 0

    def tracked_close(descriptor: int) -> None:
        nonlocal pidfd_close_count
        assert descriptor == sentinel
        pidfd_close_count += 1

    connection = FailingConnection()
    process = final_release.FinalReleaseProcess(
        pid=os.getpid(),
        pidfd=sentinel,
        pidfd_method="python-os.pidfd_open",
        connection=cast(object, connection),  # type: ignore[arg-type]
        nonce="a" * 64,
        actor={
            "schema_version": final_release.ACTOR_SCHEMA,
            **broker.process_identity(),
        },
        source_identity=_content_identity("actor-source"),
        ready_handshake_identity=_content_identity("ready"),
        primary_replay_source_identity=_content_identity("primary"),
        alternate_replay_source_identity=_content_identity("alternate"),
    )
    monkeypatch.setattr(final_release.os, "close", tracked_close)
    with pytest.raises(final_release.FinalReleaseProtocolError) as blocked:
        process.close()
    assert blocked.value.code == "OWNERSHIP_RELEASE_UNCERTAIN"
    assert connection.close_count == 1
    assert pidfd_close_count == 1
    assert process.pidfd == -1
    process.close()
    assert connection.close_count == 1
    assert pidfd_close_count == 1


def _publish_replay_receipts(
    process: final_release.FinalReleaseProcess,
    payload: dict[str, object],
) -> None:
    primary = process.publish_replay_receipt(
        implementation="primary",
        result=cast(dict[str, object], payload["primary_replay"]),
    )
    alternate = process.publish_replay_receipt(
        implementation="alternate",
        result=cast(dict[str, object], payload["alternate_replay"]),
    )
    payload["primary_replay_receipt_identity"] = primary[
        "receipt_identity"
    ]
    payload["alternate_replay_receipt_identity"] = alternate[
        "receipt_identity"
    ]
    evidence = cast(
        dict[str, object],
        cast(dict[str, object], payload["terminal_record"])[
            "post_root_closure"
        ],
    )
    evidence["primary_replay_receipt_identity"] = primary[
        "receipt_identity"
    ]
    evidence["alternate_replay_receipt_identity"] = alternate[
        "receipt_identity"
    ]


def test_final_release_publishes_only_after_dual_replay_and_seals_unused(
    tmp_path: Path,
) -> None:
    process, formal_root, release_root, primary_source, alternate_source = (
        _spawn(tmp_path)
    )
    before = list(formal_root.iterdir())
    payload = _payload(
        tmp_path,
        formal_root,
        primary_source=primary_source,
        alternate_source=alternate_source,
    )
    _publish_replay_receipts(process, payload)
    result = process.publish_final_release(payload)
    _close(process)

    assert result["state"] == "FINAL_RELEASE_PUBLISHED_UNUSED_SEALED"
    assert result["branch"] == "success"
    assert result["evidence"] == payload["terminal_record"]["post_root_closure"]
    target = release_root / final_release.SUCCESS_TARGET
    assert target.exists()
    assert stat.S_IMODE(target.stat().st_mode) == 0o444
    unused = release_root / ".failure.stage"
    assert unused.exists()
    assert stat.S_IMODE(unused.stat().st_mode) == 0o444
    assert not (release_root / final_release.FAILURE_TARGET).exists()
    for replay_target in (
        final_release.PRIMARY_REPLAY_TARGET,
        final_release.ALTERNATE_REPLAY_TARGET,
    ):
        replay_path = release_root / replay_target
        assert replay_path.exists()
        assert stat.S_IMODE(replay_path.stat().st_mode) == 0o444
    assert list(formal_root.iterdir()) == before


def test_final_release_rejects_replay_disagreement_before_publication(
    tmp_path: Path,
) -> None:
    process, formal_root, release_root, primary_source, alternate_source = (
        _spawn(tmp_path)
    )
    payload = _payload(
        tmp_path,
        formal_root,
        primary_source=primary_source,
        alternate_source=alternate_source,
    )
    cast(dict[str, object], payload["alternate_replay"])[
        "manifest_entries_sha256"
    ] = hashlib.sha256(b"forged").hexdigest()
    _publish_replay_receipts(process, payload)

    with pytest.raises(
        final_release.FinalReleaseProtocolError,
        match="REPLAY_DISAGREEMENT",
    ):
        process.publish_final_release(payload)
    _close(process)

    assert not (release_root / final_release.SUCCESS_TARGET).exists()
    assert not (release_root / final_release.FAILURE_TARGET).exists()
    assert stat.S_IMODE((release_root / ".success.stage").stat().st_mode) == 0o444
    assert stat.S_IMODE((release_root / ".failure.stage").stat().st_mode) == 0o444


def test_final_release_success_requires_closed_refunit_connection(
    tmp_path: Path,
) -> None:
    process, formal_root, release_root, primary_source, alternate_source = (
        _spawn(tmp_path)
    )
    payload = _payload(
        tmp_path,
        formal_root,
        primary_source=primary_source,
        alternate_source=alternate_source,
    )
    reference = cast(dict[str, object], payload["reference_completion"])
    reference["kind"] = "CONNECTION_UNCERTAIN"
    _publish_replay_receipts(process, payload)

    with pytest.raises(
        final_release.FinalReleaseProtocolError,
        match="REFERENCE_TERMINAL_DRIFT",
    ):
        process.publish_final_release(payload)
    _close(process)

    assert not (release_root / final_release.SUCCESS_TARGET).exists()
    assert not (release_root / final_release.FAILURE_TARGET).exists()


def test_final_release_rejects_collapsed_replay_sources(
    tmp_path: Path,
) -> None:
    process, formal_root, release_root, primary_source, alternate_source = (
        _spawn(tmp_path)
    )
    payload = _payload(
        tmp_path,
        formal_root,
        primary_source=primary_source,
        alternate_source=alternate_source,
    )
    payload["alternate_replay_source_identity"] = primary_source
    _publish_replay_receipts(process, payload)

    with pytest.raises(
        final_release.FinalReleaseProtocolError,
        match="REPLAY_SOURCE_DRIFT",
    ):
        process.publish_final_release(payload)
    _close(process)

    assert not (release_root / final_release.SUCCESS_TARGET).exists()
    assert not (release_root / final_release.FAILURE_TARGET).exists()


def test_final_release_is_no_overwrite_and_preserves_unknown_target(
    tmp_path: Path,
) -> None:
    process, formal_root, release_root, primary_source, alternate_source = (
        _spawn(tmp_path)
    )
    target = release_root / final_release.SUCCESS_TARGET
    target.write_bytes(b"unknown-existing-target\n")
    payload = _payload(
        tmp_path,
        formal_root,
        primary_source=primary_source,
        alternate_source=alternate_source,
    )
    _publish_replay_receipts(process, payload)

    with pytest.raises(final_release.FinalReleaseProtocolError):
        process.publish_final_release(payload)
    _close(process)

    assert target.read_bytes() == b"unknown-existing-target\n"
    assert not (release_root / final_release.FAILURE_TARGET).exists()


def test_final_release_incomplete_branch_uses_only_failure_leaf(
    tmp_path: Path,
) -> None:
    process, formal_root, release_root, primary_source, alternate_source = (
        _spawn(tmp_path)
    )
    payload = _payload(
        tmp_path,
        formal_root,
        primary_source=primary_source,
        alternate_source=alternate_source,
        branch="incomplete",
    )
    reference = cast(dict[str, object], payload["reference_completion"])
    reference["kind"] = "CONNECTION_UNCERTAIN"
    evidence = cast(
        dict[str, object],
        cast(dict[str, object], payload["terminal_record"])[
            "post_root_closure"
        ],
    )
    evidence["reference_completion_identity"] = (
        final_release._message_identity(reference)  # noqa: SLF001
    )
    _publish_replay_receipts(process, payload)

    result = process.publish_final_release(payload)
    _close(process)

    assert result["branch"] == "incomplete"
    assert (release_root / final_release.FAILURE_TARGET).exists()
    assert not (release_root / final_release.SUCCESS_TARGET).exists()
    assert stat.S_IMODE((release_root / ".success.stage").stat().st_mode) == 0o444


def test_final_release_lost_ack_is_terminal_and_not_retryable(
    tmp_path: Path,
) -> None:
    process, formal_root, release_root, primary_source, alternate_source = (
        _spawn(tmp_path)
    )
    payload = _payload(
        tmp_path,
        formal_root,
        primary_source=primary_source,
        alternate_source=alternate_source,
    )
    _publish_replay_receipts(process, payload)
    broker.send_frame(
        process.connection,
        {
            "schema_version": final_release.REQUEST_SCHEMA,
            "action": "PUBLISH_FINAL_RELEASE",
            "nonce": process.nonce,
            "payload": payload,
            "sequence": 5,
        },
    )
    response = broker.receive_frame(
        process.connection,
        require_message_credentials=True,
    )
    assert response.record["status"] == "PASS"
    assert (
        response.record["result"]["state"]
        == "FINAL_RELEASE_PUBLISHED_UNUSED_SEALED"
    )
    process.connection.close()
    process.prove_exit()
    os.close(process.pidfd)

    target = release_root / final_release.SUCCESS_TARGET
    assert target.exists()
    assert stat.S_IMODE(target.stat().st_mode) == 0o444
    assert not (release_root / final_release.FAILURE_TARGET).exists()
    # There is no surviving control capability with which to ACK or retry.
    assert process._terminal_attempted is False  # noqa: SLF001


def test_final_release_rejects_release_root_below_formal_root_before_publish(
    tmp_path: Path,
) -> None:
    formal_root = tmp_path / "formal-root"
    release_root = formal_root / "outside-final-release"
    release_root.mkdir(parents=True)
    parent_fd = os.open(
        release_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    prepared = {
        purpose: _extent(
            parent_fd,
            staging_name=f".{purpose}.stage",
            target_name=target,
        )
        for purpose, target in {
            "success": final_release.SUCCESS_TARGET,
            "failure": final_release.FAILURE_TARGET,
            "primary": final_release.PRIMARY_REPLAY_TARGET,
            "alternate": final_release.ALTERNATE_REPLAY_TARGET,
        }.items()
    }

    with pytest.raises(
        final_release.FinalReleaseProtocolError,
        match="READY_IDENTITY_DRIFT",
    ):
        final_release.spawn_final_release_for_test(
            formal_root=formal_root,
            release_root=release_root,
            parent_fd=parent_fd,
            success_fd=prepared["success"][1],
            failure_fd=prepared["failure"][1],
            primary_replay_fd=prepared["primary"][1],
            alternate_replay_fd=prepared["alternate"][1],
            success_extent=prepared["success"][0],
            failure_extent=prepared["failure"][0],
            primary_replay_extent=prepared["primary"][0],
            alternate_replay_extent=prepared["alternate"][0],
            primary_replay_source_identity=_content_identity(
                "primary-source"
            ),
            alternate_replay_source_identity=_content_identity(
                "alternate-source"
            ),
            source_identity=_content_identity("final-release-source"),
        )

    assert not (release_root / final_release.SUCCESS_TARGET).exists()
    assert not (release_root / final_release.FAILURE_TARGET).exists()
    assert not (release_root / final_release.PRIMARY_REPLAY_TARGET).exists()
    assert not (
        release_root / final_release.ALTERNATE_REPLAY_TARGET
    ).exists()
