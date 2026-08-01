from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
import hashlib
import inspect
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
    import ab16_arm_attempt_closure_v1 as closure
    import ab16_budget_broker_v1 as broker
finally:
    sys.path.pop(0)


ARM_SLOT = "organic-00"
ATTEMPT_PREFIX = f"arms/{ARM_SLOT}"
MAXIMUM_BYTES = 1024 * 1024


def test_closure_protocol_matches_package_broker_adapter() -> None:
    assert broker.ARM_TERMINAL_SCHEMA == closure.ARM_BUDGET_TERMINAL_SCHEMA
    assert broker.ARM_RECONCILE_SCHEMA == closure.ARM_BUDGET_RECONCILE_SCHEMA
    assert broker.JOURNAL_SCHEMA == closure.BROKER_JOURNAL_SCHEMA
    assert broker.ARM_MANIFEST_NAME == closure.TERMINAL_MANIFEST_NAME
    assert broker.ARM_TERMINAL_DIRECTORY == (
        closure.ARM_BUDGET_TERMINAL_DIRECTORY
    )
    assert broker.ARM_MANIFEST_BUDGET_LABEL == closure.MANIFEST_BUDGET_LABEL
    assert broker.ARM_MANIFEST_ARTIFACT_CLASS == (
        closure.MANIFEST_ARTIFACT_CLASS
    )
    assert list(
        inspect.signature(
            broker.BrokerProcessFormalBudgetBackend.publish_arm_manifest_and_seal
        ).parameters
    ) == [
        "self",
        "path",
        "raw",
        "maximum_bytes",
        "artifact_class",
        "label",
        "arm_slot",
        "arm_attempt_prefix",
        "arm_allocation_identity",
        "expected_path_types_before",
    ]


def _identity(label: str) -> dict[str, object]:
    raw = label.encode("utf-8")
    return {
        "path": f"/authority/{label}.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _bindings() -> dict[str, object]:
    result = {key: _identity(key) for key in closure.BINDING_KEYS}
    result["arm_allocation_identity"] = {
        "sha256": hashlib.sha256(b"arm-allocation").hexdigest(),
        "size_bytes": len(b"arm-allocation"),
    }
    return result


def _write_no_replace(path: Path, raw: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | os.O_NOFOLLOW,
        0o600,
    )
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            assert written > 0
            offset += written
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class _AtomicBackend:
    def __init__(
        self,
        formal_root: Path,
        before: Sequence[Mapping[str, object]],
    ) -> None:
        self.formal_root = formal_root
        self.before = [dict(row) for row in before]
        self.after: list[dict[str, object]] | None = None
        self.state = "ALLOCATED"
        self.seal_calls = 0
        self.replay_calls = 0
        self.fail_after_manifest = False
        self.tamper_ack = False
        self.accepted: tuple[dict[str, object], dict[str, object]] | None = None

    def maximum_bytes(self, label: str, *, artifact_class: str) -> int:
        assert (label, artifact_class) in {
            (
                closure.MANIFEST_BUDGET_LABEL,
                closure.MANIFEST_ARTIFACT_CLASS,
            ),
            (
                closure.REPLAY_BUDGET_LABEL,
                closure.REPLAY_ARTIFACT_CLASS,
            ),
            (
                closure.CONSUMPTION_BUDGET_LABEL,
                closure.CONSUMPTION_ARTIFACT_CLASS,
            ),
        }
        return MAXIMUM_BYTES

    def publish_arm_manifest_and_seal(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
        arm_slot: str,
        arm_attempt_prefix: str,
        arm_allocation_identity: Mapping[str, object],
        expected_path_types_before: Sequence[Mapping[str, object]],
    ) -> Mapping[str, object]:
        self.seal_calls += 1
        if self.state != "ALLOCATED":
            raise RuntimeError(f"arm is already {self.state}")
        self.state = "SEALED_PENDING"
        assert path == (
            self.formal_root
            / arm_attempt_prefix
            / closure.TERMINAL_MANIFEST_NAME
        )
        assert maximum_bytes == MAXIMUM_BYTES
        assert artifact_class == closure.MANIFEST_ARTIFACT_CLASS
        assert label == closure.MANIFEST_BUDGET_LABEL
        assert arm_slot == ARM_SLOT
        assert [dict(row) for row in expected_path_types_before] == self.before
        _write_no_replace(path, raw)
        if self.fail_after_manifest:
            self.state = "SEALED_INCOMPLETE"
            raise RuntimeError("simulated fsync/terminal uncertainty")

        manifest_identity = closure._publication_identity(path, raw)  # noqa: SLF001
        after_all = closure._add_inventory_regular(  # noqa: SLF001
            cast(Sequence[Mapping[str, str]], self.before),
            f"{arm_attempt_prefix}/{closure.TERMINAL_MANIFEST_NAME}",
        )
        terminal_relative = (
            f"{closure.ARM_BUDGET_TERMINAL_DIRECTORY}/{arm_slot}.json"
        )
        after_all = closure._add_inventory_regular(  # noqa: SLF001
            after_all,
            terminal_relative,
        )
        intent_path = self.formal_root / "budget/journal/00000003.json"
        intent_raw = closure._canonical_json(  # noqa: SLF001
            {
                "action": "ARM_SEALING_INTENT",
                "arm_slot": arm_slot,
                "event_sequence": 3,
            }
        )
        _write_no_replace(intent_path, intent_raw)
        sealing_intent_identity = closure._publication_identity(  # noqa: SLF001
            intent_path,
            intent_raw,
        )
        arm_rows: list[dict[str, object]] = [
            dict(row)
            for row in after_all
            if (
                row["path"] == arm_attempt_prefix
                or cast(str, row["path"]).startswith(
                    f"{arm_attempt_prefix}/",
                )
            )
        ]
        reconcile = {
            "arm_slot": arm_slot,
            "category_limits": {
                "closeout": 3 * MAXIMUM_BYTES,
                "publication": MAXIMUM_BYTES,
            },
            "category_remaining": {
                "closeout": 0,
                "publication": 0,
            },
            "reserved_bytes": 4 * MAXIMUM_BYTES,
            "schema_version": closure.ARM_BUDGET_RECONCILE_SCHEMA,
            "spent_or_stranded_bytes": 4 * MAXIMUM_BYTES,
            "unspent_reserved_bytes": 0,
        }
        terminal = closure._expected_arm_budget_terminal(  # noqa: SLF001
            arm_slot=arm_slot,
            attempt_prefix=arm_attempt_prefix,
            allocation_identity=arm_allocation_identity,
            manifest_identity=manifest_identity,
            arm_expected_path_types=arm_rows,
            arm_expected_path_types_digest=closure._inventory_digest(  # noqa: SLF001
                arm_rows
            ),
            manifest_allocation_debit=closure._expected_manifest_debit(  # noqa: SLF001
                attempt_prefix=arm_attempt_prefix,
                maximum_bytes=maximum_bytes,
            ),
            arm_budget_reconcile=reconcile,
            sealing_intent_identity=sealing_intent_identity,
            global_journal_sequence_snapshot={
                "next_event_sequence": 4,
                "sealing_intent_event_sequence": 3,
            },
            terminal_relative_path=terminal_relative,
            replay_maximum_bytes=MAXIMUM_BYTES,
            consumption_maximum_bytes=MAXIMUM_BYTES,
        )
        terminal_raw = closure._canonical_json(terminal)  # noqa: SLF001
        terminal_path = self.formal_root / terminal_relative
        _write_no_replace(terminal_path, terminal_raw)
        self.after = arm_rows
        self.state = "SEALED"
        wire_result = {
            "terminal": terminal,
            "terminal_identity": closure._publication_identity(  # noqa: SLF001
                terminal_path,
                terminal_raw,
            ),
        }
        result: dict[str, object] = {
            **wire_result,
            "response_authentication": {
                "nonce": "test-broker-nonce",
                "response_sequence": 7,
                "response_sha256": hashlib.sha256(
                    closure._canonical_json(wire_result)  # noqa: SLF001
                ).hexdigest(),
            },
        }
        if self.tamper_ack:
            result["terminal"] = {**terminal, "status": "FORGED"}
        return result

    def acknowledge(
        self,
        published: Mapping[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        if self.accepted is not None:
            return self.accepted
        response_authentication = cast(
            Mapping[str, object],
            published["arm_seal_response_authentication"],
        )
        event = {
            "action": closure.PRIOR_RESPONSE_ACCEPTED_ACTION,
            "actor": {
                "pid": os.getpid(),
                "pid_starttime": 1,
                "schema_version": "noncert-cuts-ab16-budget-broker-actor-v1",
                "uid": os.getuid(),
            },
            "event_sequence": 4,
            "nonce": response_authentication["nonce"],
            "request_sha256": hashlib.sha256(b"next-request").hexdigest(),
            "result": {
                "arm_attempt_prefix": ATTEMPT_PREFIX,
                "arm_slot": ARM_SLOT,
                "continuation": "next-arm",
                "manifest_identity": published["manifest_identity"],
                "prior_response_authentication": dict(
                    response_authentication
                ),
                "schema_version": (
                    "noncert-cuts-ab16-prior-arm-seal-response-accepted-v1"
                ),
                "state": "PRIOR_RESPONSE_ACCEPTED",
                "successor_arm_slot": "organic-01",
                "terminal_identity": published[
                    "arm_budget_terminal_identity"
                ],
            },
            "schema_version": closure.BROKER_JOURNAL_SCHEMA,
        }
        raw = closure._canonical_json(event)  # noqa: SLF001
        path = self.formal_root / "budget/journal/00000004.json"
        _write_no_replace(path, raw)
        identity = closure._publication_identity(path, raw)  # noqa: SLF001
        self.accepted = cast(dict[str, object], event["result"]), identity
        return self.accepted

    def publish_accepted_arm_replay(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        label: str,
    ) -> Mapping[str, object]:
        assert self.state == "SEALED"
        assert path == (
            self.formal_root
            / closure.ARM_REPLAY_DIRECTORY
            / f"{ARM_SLOT}.json"
        )
        assert maximum_bytes == MAXIMUM_BYTES
        assert label == closure.REPLAY_BUDGET_LABEL
        self.replay_calls += 1
        _write_no_replace(path, raw)
        return closure._publication_identity(path, raw)  # noqa: SLF001


def _inventory_before() -> list[dict[str, object]]:
    return [
        {"path": "arms", "type": "directory"},
        {"path": ATTEMPT_PREFIX, "type": "directory"},
        {"path": f"{ATTEMPT_PREFIX}/nested", "type": "directory"},
        {
            "path": f"{ATTEMPT_PREFIX}/nested/payload.bin",
            "type": "regular",
        },
        {"path": "budget", "type": "directory"},
        {
            "path": closure.ARM_BUDGET_TERMINAL_DIRECTORY,
            "type": "directory",
        },
        {"path": "budget/journal", "type": "directory"},
        {"path": "replays", "type": "directory"},
        {"path": closure.ARM_REPLAY_DIRECTORY, "type": "directory"},
    ]


def _case(
    tmp_path: Path,
) -> tuple[Path, Path, _AtomicBackend, dict[str, object]]:
    formal_root = tmp_path / "formal"
    attempt = formal_root / ATTEMPT_PREFIX
    (attempt / "nested").mkdir(parents=True)
    (formal_root / closure.ARM_BUDGET_TERMINAL_DIRECTORY).mkdir(
        parents=True,
    )
    (formal_root / "budget/journal").mkdir(parents=True)
    (formal_root / closure.ARM_REPLAY_DIRECTORY).mkdir(parents=True)
    (attempt / "nested/payload.bin").write_bytes(b"payload\n")
    bindings = _bindings()
    backend = _AtomicBackend(formal_root, _inventory_before())
    return formal_root, attempt, backend, bindings


def _publish(
    formal_root: Path,
    backend: _AtomicBackend,
    bindings: Mapping[str, object],
) -> dict[str, object]:
    return closure.publish_arm_attempt_manifest(
        formal_root,
        arm_attempt_prefix=ATTEMPT_PREFIX,
        arm_slot=ARM_SLOT,
        bindings=bindings,
        expected_path_types_before=_inventory_before(),
        budget_backend=backend,
    )


def _replay(
    formal_root: Path,
    backend: _AtomicBackend,
    bindings: Mapping[str, object],
    published: Mapping[str, object],
) -> dict[str, object]:
    assert backend.after is not None
    accepted_record, accepted_identity = backend.acknowledge(published)
    return closure.replay_and_publish_arm_attempt_root(
        formal_root,
        arm_attempt_prefix=ATTEMPT_PREFIX,
        arm_slot=ARM_SLOT,
        bindings=bindings,
        expected_path_types=backend.after,
        expected_manifest_identity=cast(
            Mapping[str, object],
            published["manifest_identity"],
        ),
        expected_arm_budget_terminal=cast(
            Mapping[str, object],
            published["arm_budget_terminal"],
        ),
        expected_arm_budget_terminal_identity=cast(
            Mapping[str, object],
            published["arm_budget_terminal_identity"],
        ),
        expected_arm_seal_response_authentication=cast(
            Mapping[str, object],
            published["arm_seal_response_authentication"],
        ),
        prior_response_accepted_result=accepted_record,
        prior_response_accepted_identity=accepted_identity,
        accepted_continuation="next-arm",
        accepted_successor_arm_slot="organic-01",
        replay_path=(
            formal_root
            / closure.ARM_REPLAY_DIRECTORY
            / f"{ARM_SLOT}.json"
        ),
        budget_backend=backend,
    )


def test_atomic_manifest_seal_and_independent_replay_close_exact_arm(
    tmp_path: Path,
) -> None:
    formal_root, attempt, backend, bindings = _case(tmp_path)
    published = _publish(formal_root, backend, bindings)

    assert backend.state == "SEALED"
    assert backend.seal_calls == 1
    manifest = cast(dict[str, object], published["manifest"])
    assert manifest["schema_version"] == closure.MANIFEST_SCHEMA
    assert all(
        entry["path"] != closure.TERMINAL_MANIFEST_NAME
        for entry in cast(list[dict[str, object]], manifest["entries"])
    )
    assert (attempt / closure.TERMINAL_MANIFEST_NAME).is_file()
    terminal = cast(dict[str, object], published["arm_budget_terminal"])
    assert terminal["schema_version"] == closure.ARM_BUDGET_TERMINAL_SCHEMA
    assert terminal["allocation_state"] == closure.PENDING_ALLOCATION_STATE
    assert terminal["status"] == closure.PENDING_TERMINAL_STATUS
    assert "terminal_identity" not in terminal

    replayed = _replay(formal_root, backend, bindings, published)
    verified = closure.verify_published_arm_attempt_replay(
        cast(str, cast(dict[str, object], replayed["replay_identity"])["path"]),
        expected_replay_identity=cast(
            Mapping[str, object],
            replayed["replay_identity"],
        ),
        expected_manifest_identity=cast(
            Mapping[str, object],
            published["manifest_identity"],
        ),
        expected_arm_budget_terminal_identity=cast(
            Mapping[str, object],
            published["arm_budget_terminal_identity"],
        ),
        expected_arm_seal_response_authentication=cast(
            Mapping[str, object],
            published["arm_seal_response_authentication"],
        ),
        expected_prior_response_accepted_identity=backend.acknowledge(
            published
        )[1],
        expected_accepted_continuation="next-arm",
        expected_accepted_successor_arm_slot="organic-01",
        arm_attempt_prefix=ATTEMPT_PREFIX,
        arm_slot=ARM_SLOT,
        bindings=bindings,
    )
    assert verified["schema_version"] == closure.REPLAY_SCHEMA
    assert verified["authorizations"] == closure.FALSE_AUTHORIZATIONS


@pytest.mark.parametrize(
    ("kind", "expected_code"),
    [
        ("regular", "ROOT_CLOSURE_MISMATCH"),
        ("directory", "ROOT_CLOSURE_MISMATCH"),
        ("staging", "STAGING_PRESENT"),
        ("symlink", "SYMLINK_REJECTED"),
        ("fifo", "SPECIAL_NODE_REJECTED"),
        ("hardlink", "HARDLINK_REJECTED"),
    ],
)
def test_replay_rejects_every_unregistered_or_unsafe_node(
    tmp_path: Path,
    kind: str,
    expected_code: str,
) -> None:
    formal_root, attempt, backend, bindings = _case(tmp_path)
    published = _publish(formal_root, backend, bindings)
    target = attempt / (
        f"{closure.STAGING_PREFIX}unknown"
        if kind == "staging"
        else "unknown"
    )
    if kind in {"regular", "staging"}:
        target.write_bytes(b"unknown")
    elif kind == "directory":
        target.mkdir()
    elif kind == "symlink":
        target.symlink_to("/tmp")
    elif kind == "fifo":
        os.mkfifo(target)
    else:
        os.link(attempt / "nested/payload.bin", target)

    with pytest.raises(closure.ArmAttemptClosureError) as caught:
        _replay(formal_root, backend, bindings, published)
    assert caught.value.code == expected_code
    assert target.lexists() if hasattr(target, "lexists") else os.path.lexists(target)


def test_replay_rejects_missing_registered_member(tmp_path: Path) -> None:
    formal_root, attempt, backend, bindings = _case(tmp_path)
    published = _publish(formal_root, backend, bindings)
    (attempt / "nested/payload.bin").unlink()

    with pytest.raises(closure.ArmAttemptClosureError) as caught:
        _replay(formal_root, backend, bindings, published)
    assert caught.value.code == "ROOT_CLOSURE_MISMATCH"


def test_atomic_action_uncertainty_is_permanent_and_not_retried(
    tmp_path: Path,
) -> None:
    formal_root, _attempt, backend, bindings = _case(tmp_path)
    backend.fail_after_manifest = True
    with pytest.raises(closure.ArmAttemptClosureError) as first:
        _publish(formal_root, backend, bindings)
    assert first.value.code == "ARM_SEAL_FAILED_OR_UNCERTAIN"
    assert backend.state == "SEALED_INCOMPLETE"

    with pytest.raises(closure.ArmAttemptClosureError):
        _publish(formal_root, backend, bindings)
    assert backend.seal_calls == 1


def test_manifest_ack_tamper_fails_after_irreversible_seal(tmp_path: Path) -> None:
    formal_root, _attempt, backend, bindings = _case(tmp_path)
    backend.tamper_ack = True
    with pytest.raises(closure.ArmAttemptClosureError) as caught:
        _publish(formal_root, backend, bindings)
    assert caught.value.code == "ARM_BUDGET_TERMINAL_INVALID"
    assert backend.state == "SEALED"


def test_manifest_and_replay_are_no_overwrite(tmp_path: Path) -> None:
    formal_root, _attempt, backend, bindings = _case(tmp_path)
    published = _publish(formal_root, backend, bindings)
    with pytest.raises(closure.ArmAttemptClosureError):
        _publish(formal_root, backend, bindings)
    assert backend.seal_calls == 1

    _replay(formal_root, backend, bindings, published)
    with pytest.raises(closure.ArmAttemptClosureError) as caught:
        _replay(formal_root, backend, bindings, published)
    assert caught.value.code == "REPLAY_PREEXISTS"
    assert backend.replay_calls == 1


def test_midwalk_late_write_is_rejected_and_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formal_root, attempt, backend, bindings = _case(tmp_path)
    published = _publish(formal_root, backend, bindings)
    original = closure._read_regular  # noqa: SLF001
    injected = False

    def inject(
        parent_fd: int,
        name: str,
        before: os.stat_result,
        relative: str,
        *,
        capture: bool,
    ) -> tuple[str, bytes | None]:
        nonlocal injected
        result = original(
            parent_fd,
            name,
            before,
            relative,
            capture=capture,
        )
        if relative == "nested/payload.bin" and not injected:
            injected = True
            (attempt / "nested/late.bin").write_bytes(b"late")
        return result

    monkeypatch.setattr(closure, "_read_regular", inject)
    with pytest.raises(closure.ArmAttemptClosureError) as caught:
        _replay(formal_root, backend, bindings, published)
    assert caught.value.code == "ROOT_CHANGED"
    assert (attempt / "nested/late.bin").read_bytes() == b"late"


def test_midwalk_parent_replacement_fails_final_absolute_join(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formal_root, attempt, backend, bindings = _case(tmp_path)
    published = _publish(formal_root, backend, bindings)
    original = closure._read_regular  # noqa: SLF001
    injected = False

    def inject(
        parent_fd: int,
        name: str,
        before: os.stat_result,
        relative: str,
        *,
        capture: bool,
    ) -> tuple[str, bytes | None]:
        nonlocal injected
        result = original(
            parent_fd,
            name,
            before,
            relative,
            capture=capture,
        )
        if relative == "nested/payload.bin" and not injected:
            injected = True
            (formal_root / "arms").rename(formal_root / "arms-old")
            (formal_root / "arms" / ARM_SLOT).mkdir(parents=True)
            (formal_root / "arms" / ARM_SLOT / "replacement").write_bytes(
                b"unknown",
            )
        return result

    monkeypatch.setattr(closure, "_read_regular", inject)
    with pytest.raises(closure.ArmAttemptClosureError) as caught:
        _replay(formal_root, backend, bindings, published)
    assert caught.value.code == "ROOT_CHANGED"
    assert (formal_root / "arms" / ARM_SLOT / "replacement").is_file()
    assert (
        formal_root
        / "arms-old"
        / ARM_SLOT
        / closure.TERMINAL_MANIFEST_NAME
    ).is_file()
    assert attempt != formal_root / "arms-old" / ARM_SLOT


def test_detached_replay_tamper_is_rejected(tmp_path: Path) -> None:
    formal_root, _attempt, backend, bindings = _case(tmp_path)
    published = _publish(formal_root, backend, bindings)
    replayed = _replay(formal_root, backend, bindings, published)
    replay_identity = cast(dict[str, object], replayed["replay_identity"])
    replay_path = Path(cast(str, replay_identity["path"]))
    replay_path.chmod(0o600)
    replay_path.write_bytes(replay_path.read_bytes() + b" ")
    _accepted_record, accepted_identity = backend.acknowledge(published)

    with pytest.raises(closure.ArmAttemptClosureError) as caught:
        closure.verify_published_arm_attempt_replay(
            replay_path,
            expected_replay_identity=replay_identity,
            expected_manifest_identity=cast(
                Mapping[str, object],
                published["manifest_identity"],
            ),
            expected_arm_budget_terminal_identity=cast(
                Mapping[str, object],
                published["arm_budget_terminal_identity"],
            ),
            expected_arm_seal_response_authentication=cast(
                Mapping[str, object],
                published["arm_seal_response_authentication"],
            ),
            expected_prior_response_accepted_identity=accepted_identity,
            expected_accepted_continuation="next-arm",
            expected_accepted_successor_arm_slot="organic-01",
            arm_attempt_prefix=ATTEMPT_PREFIX,
            arm_slot=ARM_SLOT,
            bindings=bindings,
        )
    assert caught.value.code == "REPLAY_IDENTITY_DRIFT"


def test_replay_rejects_terminal_or_binding_tamper(tmp_path: Path) -> None:
    formal_root, _attempt, backend, bindings = _case(tmp_path)
    published = _publish(formal_root, backend, bindings)
    accepted_record, accepted_identity = backend.acknowledge(published)
    forged_terminal = copy.deepcopy(published["arm_budget_terminal"])
    assert isinstance(forged_terminal, dict)
    forged_terminal["allocation_state"] = "ALLOCATED"
    with pytest.raises(closure.ArmAttemptClosureError) as terminal_error:
        closure.replay_and_publish_arm_attempt_root(
            formal_root,
            arm_attempt_prefix=ATTEMPT_PREFIX,
            arm_slot=ARM_SLOT,
            bindings=bindings,
            expected_path_types=cast(
                Sequence[Mapping[str, object]],
                backend.after,
            ),
            expected_manifest_identity=cast(
                Mapping[str, object],
                published["manifest_identity"],
            ),
            expected_arm_budget_terminal=forged_terminal,
            expected_arm_budget_terminal_identity=cast(
                Mapping[str, object],
                published["arm_budget_terminal_identity"],
            ),
            expected_arm_seal_response_authentication=cast(
                Mapping[str, object],
                published["arm_seal_response_authentication"],
            ),
            prior_response_accepted_result=accepted_record,
            prior_response_accepted_identity=accepted_identity,
            accepted_continuation="next-arm",
            accepted_successor_arm_slot="organic-01",
            replay_path=(
                formal_root
                / closure.ARM_REPLAY_DIRECTORY
                / f"{ARM_SLOT}.json"
            ),
            budget_backend=backend,
        )
    assert terminal_error.value.code == "ARM_BUDGET_TERMINAL_INVALID"

    forged_bindings = copy.deepcopy(bindings)
    forged_bindings["arm_selection_identity"] = _identity("forged-selection")
    with pytest.raises(closure.ArmAttemptClosureError) as binding_error:
        _replay(formal_root, backend, forged_bindings, published)
    assert binding_error.value.code in {
        "ARM_BUDGET_TERMINAL_INVALID",
        "MANIFEST_INVALID",
    }


def test_replay_path_is_fixed_and_outside_attempt(tmp_path: Path) -> None:
    formal_root, attempt, backend, bindings = _case(tmp_path)
    published = _publish(formal_root, backend, bindings)
    assert backend.after is not None
    accepted_record, accepted_identity = backend.acknowledge(published)
    with pytest.raises(closure.ArmAttemptClosureError) as caught:
        closure.replay_and_publish_arm_attempt_root(
            formal_root,
            arm_attempt_prefix=ATTEMPT_PREFIX,
            arm_slot=ARM_SLOT,
            bindings=bindings,
            expected_path_types=backend.after,
            expected_manifest_identity=cast(
                Mapping[str, object],
                published["manifest_identity"],
            ),
            expected_arm_budget_terminal=cast(
                Mapping[str, object],
                published["arm_budget_terminal"],
            ),
            expected_arm_budget_terminal_identity=cast(
                Mapping[str, object],
                published["arm_budget_terminal_identity"],
            ),
            expected_arm_seal_response_authentication=cast(
                Mapping[str, object],
                published["arm_seal_response_authentication"],
            ),
            prior_response_accepted_result=accepted_record,
            prior_response_accepted_identity=accepted_identity,
            accepted_continuation="next-arm",
            accepted_successor_arm_slot="organic-01",
            replay_path=attempt / "forbidden-replay.json",
            budget_backend=backend,
        )
    assert caught.value.code == "REPLAY_PATH_INVALID"
    assert not (attempt / "forbidden-replay.json").exists()


def test_later_formal_root_writes_do_not_expand_closed_arm_scope(
    tmp_path: Path,
) -> None:
    formal_root, _attempt, backend, bindings = _case(tmp_path)
    published = _publish(formal_root, backend, bindings)
    later_arm = formal_root / "arms/organic-01"
    later_arm.mkdir()
    (later_arm / "later.json").write_bytes(b"later arm remains legal\n")

    replayed = _replay(formal_root, backend, bindings, published)
    assert cast(dict[str, object], replayed["replay"])["status"] == (
        "REPLAY_ACCEPTED_NO_GLOBAL_AUTHORITY"
    )
    terminal = cast(dict[str, object], published["arm_budget_terminal"])
    assert "expected_path_types" not in terminal
    assert all(
        cast(str, row["path"]).startswith(f"{ATTEMPT_PREFIX}/")
        or row["path"] == ATTEMPT_PREFIX
        for row in cast(
            list[dict[str, object]],
            terminal["arm_expected_path_types"],
        )
    )


def test_replay_requires_durable_prior_response_accepted_join(
    tmp_path: Path,
) -> None:
    formal_root, _attempt, backend, bindings = _case(tmp_path)
    published = _publish(formal_root, backend, bindings)
    accepted_record, accepted_identity = backend.acknowledge(published)
    accepted_path = Path(cast(str, accepted_identity["path"]))
    accepted_path.unlink()

    assert backend.after is not None
    with pytest.raises(closure.ArmAttemptClosureError) as missing:
        closure.replay_and_publish_arm_attempt_root(
            formal_root,
            arm_attempt_prefix=ATTEMPT_PREFIX,
            arm_slot=ARM_SLOT,
            bindings=bindings,
            expected_path_types=backend.after,
            expected_manifest_identity=cast(
                Mapping[str, object],
                published["manifest_identity"],
            ),
            expected_arm_budget_terminal=cast(
                Mapping[str, object],
                published["arm_budget_terminal"],
            ),
            expected_arm_budget_terminal_identity=cast(
                Mapping[str, object],
                published["arm_budget_terminal_identity"],
            ),
            expected_arm_seal_response_authentication=cast(
                Mapping[str, object],
                published["arm_seal_response_authentication"],
            ),
            prior_response_accepted_result=accepted_record,
            prior_response_accepted_identity=accepted_identity,
            accepted_continuation="next-arm",
            accepted_successor_arm_slot="organic-01",
            replay_path=(
                formal_root
                / closure.ARM_REPLAY_DIRECTORY
                / f"{ARM_SLOT}.json"
            ),
            budget_backend=backend,
        )
    assert missing.value.code == "PUBLISHED_IDENTITY_OPEN_FAILED"
