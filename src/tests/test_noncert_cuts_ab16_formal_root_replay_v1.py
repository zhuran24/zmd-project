from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
sys.path.insert(0, str(RESEARCH))
try:
    import replay_ab16_formal_root_alt_v1 as alternate
    import replay_ab16_formal_root_v1 as primary
finally:
    sys.path.pop(0)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8") + b"\n"


def _identity(path: str, raw: bytes) -> dict[str, object]:
    return {
        "artifact_class": "closeout",
        "maximum_bytes": 4096,
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _entry(path: Path, root: Path) -> dict[str, object]:
    relative = path.relative_to(root).as_posix()
    metadata = path.stat(follow_symlinks=False)
    if path.is_dir():
        return {
            "mode_octal": f"{metadata.st_mode & 0o7777:04o}",
            "path": relative,
            "type": "directory",
        }
    raw = path.read_bytes()
    return {
        "mode_octal": f"{metadata.st_mode & 0o7777:04o}",
        "path": relative,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "type": "regular",
    }


def _closed_root(tmp_path: Path) -> Path:
    root = tmp_path / "formal"
    (root / "formal-closure").mkdir(parents=True, mode=0o700)
    (root / "locks").mkdir(mode=0o700)

    absent_actor = {
        "schema_version": "noncert-cuts-ab16-closure-actor-v1",
        "pid": 2**30,
        "pid_starttime": 1,
        "uid": os.getuid(),
    }
    terminal_join_sha256 = "a" * 64
    same_uid_baseline = {
        "mode": "LIVE_PROCFS_FULL_SCOPE",
        "observed_uid": os.getuid(),
        "policy_id": (
            "exact-resource-gate-pid-starttime-classification-v1"
        ),
        "process_scope_contract": (
            "EXACT_PID_STARTTIME_CLASSIFICATION_NO_GLOBAL_FD_SCAN"
        ),
        "processes": [],
        "schema_version": (
            "noncert-cuts-ab16-same-uid-process-baseline-v1"
        ),
        "threat_boundary": "NONADVERSARIAL_SAME_UID_AMBIENT",
    }
    same_uid_baseline_sha256 = hashlib.sha256(
        _canonical(same_uid_baseline).removesuffix(b"\n")
    ).hexdigest()
    writer_capability_closure = {
        "broker_exit_proved": True,
        "closure_actor_descriptors": [0, 1, 2, 3],
        "recovery_exit_proved": True,
        "same_uid_process_scope": {
            "allowed_runtime_actors": [],
            "baseline_live_processes": [],
            "baseline_sha256": same_uid_baseline_sha256,
            "policy_id": (
                "exact-resource-gate-pid-starttime-classification-v1"
            ),
            "state": "EXACT_BASELINE_OR_PACKAGE_ACTOR_SCOPE",
            "threat_boundary": "NONADVERSARIAL_SAME_UID_AMBIENT",
        },
        "state": "PACKAGE_WRITERS_EXITED_CLOSURE_FIXED_FDS_ONLY",
    }
    recovery = _canonical(
        {
            "schema_version": (
                "noncert-cuts-ab16-recovery-disarm-terminal-v1"
            ),
            "broker_actor": {
                **absent_actor,
                "schema_version": (
                    "noncert-cuts-ab16-budget-broker-actor-v1"
                ),
            },
            "closure_actor": absent_actor,
            "recovery_actor": {
                **absent_actor,
                "schema_version": (
                    "noncert-cuts-ab16-recovery-actor-v1"
                ),
            },
            "recovery_observation": {"state": "DISARMED"},
            "state": "RECOVERY_ABSENT_AND_TAKEOVER_LOCK_RELEASED",
            "terminal_join_sha256": terminal_join_sha256,
        }
    )
    budget = _canonical(
        {
            "schema_version": (
                "noncert-cuts-ab16-formal-root-budget-terminal-v2"
            ),
            "broker_actor": {
                **absent_actor,
                "schema_version": (
                    "noncert-cuts-ab16-budget-broker-actor-v1"
                ),
            },
            "budget_contract": {
                "research_only": True,
                "schema_version": "fixture-budget-v1",
            },
            "closure_actor": absent_actor,
            "same_uid_process_baseline": same_uid_baseline,
            "same_uid_process_baseline_sha256": (
                same_uid_baseline_sha256
            ),
            "state": "BUDGET_TERMINAL_AFTER_RECOVERY_DISARM",
            "terminal_join_sha256": terminal_join_sha256,
            "writer_capability_closure": writer_capability_closure,
        }
    )
    lock = _canonical(
        {
            "schema_version": (
                "noncert-cuts-ab16-closure-lock-consumption-v1"
            ),
            "state": "CLOSURE_ACTOR_CONSUMED",
        }
    )
    members = {
        "formal-closure/recovery-disarm-terminal.json": recovery,
        "formal-closure/budget-terminal.json": budget,
        "locks/formal-closure-consumption.json": lock,
    }
    for relative, raw in members.items():
        path = root / relative
        path.write_bytes(raw)
        path.chmod(0o444)

    entries = sorted(
        (
            _entry(path, root)
            for path in root.rglob("*")
            if path.relative_to(root).as_posix()
            != "formal-closure/formal-manifest.json"
        ),
        key=lambda item: (str(item["path"]), str(item["type"])),
    )
    manifest = _canonical(
        {
            "schema_version": (
                "noncert-cuts-ab16-formal-manifest-v2"
            ),
            "authority": dict(primary.FALSE_AUTHORITY),
            "budget_terminal_identity": _identity(
                "formal-closure/budget-terminal.json",
                budget,
            ),
            "closure_actor": absent_actor,
            "entries": entries,
            "entries_sha256": hashlib.sha256(
                _canonical(entries)
            ).hexdigest(),
            "excluded_terminal_path": (
                "formal-closure/formal-manifest.json"
            ),
            "lock_consumption_identity": _identity(
                "locks/formal-closure-consumption.json",
                lock,
            ),
            "recovery_terminal_identity": _identity(
                "formal-closure/recovery-disarm-terminal.json",
                recovery,
            ),
            "same_uid_process_baseline_sha256": (
                same_uid_baseline_sha256
            ),
            "terminal_join_sha256": terminal_join_sha256,
            "writer_capability_closure": writer_capability_closure,
        }
    )
    manifest_path = root / "formal-closure/formal-manifest.json"
    manifest_path.write_bytes(manifest)
    manifest_path.chmod(0o444)
    return root


def _rewrite_manifest_for_current_members(
    root: Path,
    manifest: dict[str, object],
) -> None:
    budget_path = root / "formal-closure/budget-terminal.json"
    budget_raw = budget_path.read_bytes()
    recovery_path = (
        root / "formal-closure/recovery-disarm-terminal.json"
    )
    recovery_raw = recovery_path.read_bytes()
    entries = sorted(
        (
            _entry(path, root)
            for path in root.rglob("*")
            if path.relative_to(root).as_posix()
            != "formal-closure/formal-manifest.json"
        ),
        key=lambda item: (str(item["path"]), str(item["type"])),
    )
    manifest["budget_terminal_identity"] = _identity(
        "formal-closure/budget-terminal.json",
        budget_raw,
    )
    manifest["recovery_terminal_identity"] = _identity(
        "formal-closure/recovery-disarm-terminal.json",
        recovery_raw,
    )
    manifest["entries"] = entries
    manifest["entries_sha256"] = hashlib.sha256(
        _canonical(entries)
    ).hexdigest()
    manifest_path = root / "formal-closure/formal-manifest.json"
    manifest_path.chmod(0o600)
    manifest_path.write_bytes(_canonical(manifest))
    manifest_path.chmod(0o444)


def test_dual_formal_root_replayers_join_exact_closure(
    tmp_path: Path,
) -> None:
    root = _closed_root(tmp_path)
    first = primary.replay_formal_root(root)
    second = alternate.replay_formal_root(root)

    assert first["state"] == second["state"]
    assert (
        first["formal_manifest_identity"]
        == second["formal_manifest_identity"]
    )
    assert (
        first["manifest_entries_sha256"]
        == second["manifest_entries_sha256"]
    )
    assert (
        first["terminal_join_sha256"]
        == second["terminal_join_sha256"]
    )
    assert set(first["actor_absence"]) == {
        "broker",
        "closure",
        "recovery",
    }
    assert first["actor_absence"] == second["actor_absence"]
    assert first["implementation"] != second["implementation"]
    assert hashlib.sha256(Path(primary.__file__).read_bytes()).hexdigest() != (
        hashlib.sha256(Path(alternate.__file__).read_bytes()).hexdigest()
    )


def test_dual_replayers_reject_consistent_byte_graph_with_forged_baseline_digest(
    tmp_path: Path,
) -> None:
    root = _closed_root(tmp_path)
    budget_path = root / "formal-closure/budget-terminal.json"
    budget = json.loads(budget_path.read_bytes())
    forged_digest = "b" * 64
    budget["same_uid_process_baseline_sha256"] = forged_digest
    budget_path.chmod(0o600)
    budget_path.write_bytes(_canonical(budget))
    budget_path.chmod(0o444)
    manifest_path = root / "formal-closure/formal-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["same_uid_process_baseline_sha256"] = forged_digest
    _rewrite_manifest_for_current_members(root, manifest)
    with pytest.raises(RuntimeError, match="baseline"):
        primary.replay_formal_root(root)
    with pytest.raises(
        alternate.AlternateFormalRootReplayError,
        match="baseline",
    ):
        alternate.replay_formal_root(root)


@pytest.mark.parametrize("implementation", [primary, alternate])
def test_formal_root_replayer_requires_registered_broker_actor_absence(
    tmp_path: Path,
    implementation: object,
) -> None:
    root = _closed_root(tmp_path)
    current_actor = {
        "schema_version": (
            "noncert-cuts-ab16-budget-broker-actor-v1"
        ),
        "pid": os.getpid(),
        "pid_starttime": int(
            Path("/proc/self/stat")
            .read_text(encoding="ascii")
            .rsplit(")", 1)[1]
            .split()[19]
        ),
        "uid": os.getuid(),
    }
    for relative in (
        "formal-closure/recovery-disarm-terminal.json",
        "formal-closure/budget-terminal.json",
    ):
        path = root / relative
        payload = json.loads(path.read_bytes())
        payload["broker_actor"] = current_actor
        path.chmod(0o600)
        path.write_bytes(_canonical(payload))
        path.chmod(0o444)
    manifest_path = root / "formal-closure/formal-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    _rewrite_manifest_for_current_members(root, manifest)

    with pytest.raises(RuntimeError, match="broker actor"):
        implementation.replay_formal_root(root)  # type: ignore[attr-defined]


@pytest.mark.parametrize("implementation", [primary, alternate])
def test_formal_root_replayer_rejects_post_manifest_member(
    tmp_path: Path,
    implementation: object,
) -> None:
    root = _closed_root(tmp_path)
    (root / "late.bin").write_bytes(b"late")
    with pytest.raises(RuntimeError, match="manifest"):
        implementation.replay_formal_root(root)  # type: ignore[attr-defined]


@pytest.mark.parametrize("implementation", [primary, alternate])
def test_formal_root_replayer_rejects_symlink(
    tmp_path: Path,
    implementation: object,
) -> None:
    root = _closed_root(tmp_path)
    (root / "late-link").symlink_to("/dev/null")
    with pytest.raises(RuntimeError, match="symlink|special"):
        implementation.replay_formal_root(root)  # type: ignore[attr-defined]
