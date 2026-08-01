#!/usr/bin/env python3
"""Primary, read-only outside replay for one closed prospective AB16 formal root.

The replay does not publish into the formal root and grants no witness, cut,
bound, production, certified, or Stage-B authority.  Its caller is responsible
for publishing the returned canonical record into a fresh outside-root receipt
root.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Final

from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_budget_broker_v1 as broker,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_closure_actor_v1 as closure,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_resource_admission_v1 as resource_admission,
)


REPLAY_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-root-outside-replay-primary-v1"
)
FORMAL_MANIFEST_SCHEMA: Final = "noncert-cuts-ab16-formal-manifest-v2"
BUDGET_TERMINAL_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-root-budget-terminal-v2"
)
AUTHORITY_SCOPE: Final = "AB16_RESEARCH_ONLY"
FORMAL_MANIFEST_PATH: Final = "formal-closure/formal-manifest.json"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
FALSE_AUTHORITY: Final = {
    "changes_certified_exact": False,
    "changes_cut_state": False,
    "changes_lower_bound": False,
    "changes_production": False,
    "changes_upper_bound": False,
    "research_only": True,
}


class FormalRootReplayError(RuntimeError):
    """A closed-root replay invariant failed closed."""


def _strict_canonical_json(raw: bytes, *, label: str) -> dict[str, Any]:
    def pairs_without_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise FormalRootReplayError(
                    f"{label} contains duplicate key {key!r}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(
            raw,
            object_pairs_hook=pairs_without_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                FormalRootReplayError(
                    f"{label} contains non-finite token {token}"
                )
            ),
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise FormalRootReplayError(f"{label} is not strict JSON") from exc
    if type(value) is not dict or broker.canonical_json_bytes(value) != raw:
        raise FormalRootReplayError(
            f"{label} is not one canonical JSON object"
        )
    return value


def _identity_from_entry(
    entry: Mapping[str, object],
) -> dict[str, object]:
    return {
        "path": entry["path"],
        "sha256": entry["sha256"],
        "size_bytes": entry["size_bytes"],
    }


def _process_absent(actor: object, *, label: str) -> dict[str, object]:
    if (
        type(actor) is not dict
        or set(actor) != {"schema_version", "pid", "pid_starttime", "uid"}
        or type(actor["pid"]) is not int
        or type(actor["pid_starttime"]) is not int
        or type(actor["uid"]) is not int
        or actor["pid"] <= 0
        or actor["pid_starttime"] <= 0
        or actor["uid"] < 0
    ):
        raise FormalRootReplayError(f"{label} actor identity is malformed")
    pid = actor["pid"]
    try:
        raw_stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except FileNotFoundError:
        observed_starttime = None
    except OSError as exc:
        raise FormalRootReplayError(
            f"{label} actor absence cannot be observed"
        ) from exc
    else:
        try:
            observed_starttime = int(raw_stat.rsplit(")", 1)[1].split()[19])
        except (IndexError, ValueError) as exc:
            raise FormalRootReplayError(
                f"{label} actor starttime is malformed"
            ) from exc
    if observed_starttime == actor["pid_starttime"]:
        raise FormalRootReplayError(f"{label} actor is still live")
    return {
        "actor": dict(actor),
        "observed_starttime": observed_starttime,
        "state": "EXACT_ACTOR_ABSENT",
    }


def replay_formal_root(root: Path | str) -> dict[str, object]:
    """Replay one already-closed root without acquiring a write capability."""

    absolute = Path(os.path.abspath(root))
    entries = closure.snapshot_root_entries(absolute)
    by_path = {
        str(entry["path"]): entry
        for entry in entries
    }
    if len(by_path) != len(entries):
        raise FormalRootReplayError("formal root contains duplicate paths")
    manifest_entry = by_path.get(FORMAL_MANIFEST_PATH)
    if (
        type(manifest_entry) is not dict
        or manifest_entry.get("type") != "regular"
        or manifest_entry.get("mode_octal") != "0444"
    ):
        raise FormalRootReplayError(
            "formal root lacks its fixed read-only manifest"
        )
    manifest_raw = (absolute / FORMAL_MANIFEST_PATH).read_bytes()
    manifest = _strict_canonical_json(
        manifest_raw,
        label="formal root manifest",
    )
    expected_fields = {
        "authority",
        "budget_terminal_identity",
        "closure_actor",
        "entries",
        "entries_sha256",
        "excluded_terminal_path",
        "lock_consumption_identity",
        "recovery_terminal_identity",
        "same_uid_process_baseline_sha256",
        "schema_version",
        "terminal_join_sha256",
        "writer_capability_closure",
    }
    if (
        set(manifest) != expected_fields
        or manifest["schema_version"] != FORMAL_MANIFEST_SCHEMA
        or manifest["authority"] != FALSE_AUTHORITY
        or manifest["excluded_terminal_path"] != FORMAL_MANIFEST_PATH
        or not isinstance(manifest["terminal_join_sha256"], str)
        or SHA256_RE.fullmatch(manifest["terminal_join_sha256"]) is None
        or type(manifest["entries"]) is not list
    ):
        raise FormalRootReplayError(
            "formal root manifest discriminator or field set drifted"
        )
    manifest_entries = manifest["entries"]
    actual_without_manifest = [
        entry
        for entry in entries
        if entry["path"] != FORMAL_MANIFEST_PATH
    ]
    if manifest_entries != actual_without_manifest:
        raise FormalRootReplayError(
            "manifest entries do not equal the complete root minus the fixed manifest"
        )
    entries_digest = hashlib.sha256(
        broker.canonical_json_bytes(manifest_entries)
    ).hexdigest()
    if manifest["entries_sha256"] != entries_digest:
        raise FormalRootReplayError("formal root manifest entry digest drifted")
    if (
        manifest_entry["sha256"] != hashlib.sha256(manifest_raw).hexdigest()
        or manifest_entry["size_bytes"] != len(manifest_raw)
    ):
        raise FormalRootReplayError("formal root manifest identity drifted")

    for field, expected_path in (
        (
            "budget_terminal_identity",
            "formal-closure/budget-terminal.json",
        ),
        (
            "recovery_terminal_identity",
            "formal-closure/recovery-disarm-terminal.json",
        ),
        (
            "lock_consumption_identity",
            "locks/formal-closure-consumption.json",
        ),
    ):
        identity = manifest[field]
        entry = by_path.get(expected_path)
        if (
            type(identity) is not dict
            or type(entry) is not dict
            or entry.get("type") != "regular"
            or any(
                identity.get(key) != value
                for key, value in _identity_from_entry(entry).items()
            )
        ):
            raise FormalRootReplayError(
                f"formal root {field} does not bind its fixed member"
            )

    recovery_raw = (
        absolute / "formal-closure/recovery-disarm-terminal.json"
    ).read_bytes()
    recovery_terminal = _strict_canonical_json(
        recovery_raw,
        label="recovery disarm terminal",
    )
    if (
        recovery_terminal.get("state")
        != "RECOVERY_ABSENT_AND_TAKEOVER_LOCK_RELEASED"
        or recovery_terminal.get("terminal_join_sha256")
        != manifest["terminal_join_sha256"]
        or recovery_terminal.get("closure_actor")
        != manifest["closure_actor"]
        or type(recovery_terminal.get("recovery_actor")) is not dict
    ):
        raise FormalRootReplayError(
            "recovery disarm terminal does not join the formal manifest"
        )
    budget_raw = (
        absolute / "formal-closure/budget-terminal.json"
    ).read_bytes()
    budget_terminal = _strict_canonical_json(
        budget_raw,
        label="budget terminal",
    )
    budget_fields = {
        "broker_actor",
        "budget_contract",
        "closure_actor",
        "same_uid_process_baseline",
        "same_uid_process_baseline_sha256",
        "schema_version",
        "state",
        "terminal_join_sha256",
        "writer_capability_closure",
    }
    if (
        set(budget_terminal) != budget_fields
        or budget_terminal["schema_version"]
        != BUDGET_TERMINAL_SCHEMA
        or budget_terminal["closure_actor"] != manifest["closure_actor"]
        or budget_terminal["state"]
        != "BUDGET_TERMINAL_AFTER_RECOVERY_DISARM"
        or budget_terminal["terminal_join_sha256"]
        != manifest["terminal_join_sha256"]
        or budget_terminal["broker_actor"]
        != recovery_terminal.get("broker_actor")
        or budget_terminal["same_uid_process_baseline_sha256"]
        != manifest["same_uid_process_baseline_sha256"]
        or budget_terminal["writer_capability_closure"]
        != manifest["writer_capability_closure"]
    ):
        raise FormalRootReplayError(
            "budget terminal does not join the formal manifest"
        )
    resource_admission.validate_same_uid_process_baseline(
        budget_terminal["same_uid_process_baseline"],
        expected_sha256=budget_terminal[
            "same_uid_process_baseline_sha256"
        ],
        require_live=False,
    )
    actor_absence = {
        "broker": _process_absent(
            budget_terminal["broker_actor"],
            label="broker",
        ),
        "closure": _process_absent(
            manifest["closure_actor"],
            label="closure",
        ),
        "recovery": _process_absent(
            recovery_terminal["recovery_actor"],
            label="recovery",
        ),
    }
    root_identity = os.stat(absolute, follow_symlinks=False)
    return {
        "actor_absence": actor_absence,
        "authority": dict(FALSE_AUTHORITY),
        "authority_scope": AUTHORITY_SCOPE,
        "formal_manifest_identity": _identity_from_entry(
            manifest_entry
        ),
        "formal_root": {
            "device": root_identity.st_dev,
            "inode": root_identity.st_ino,
            "mode_octal": f"{root_identity.st_mode & 0o7777:04o}",
            "path": str(absolute),
            "uid": root_identity.st_uid,
        },
        "implementation": "package-pinned-primary-v1",
        "manifest_entries_sha256": entries_digest,
        "schema_version": REPLAY_SCHEMA,
        "state": "FORMAL_ROOT_CLOSURE_ACCEPTED",
        "terminal_join_sha256": manifest["terminal_join_sha256"],
    }


__all__ = [
    "AUTHORITY_SCOPE",
    "FALSE_AUTHORITY",
    "FormalRootReplayError",
    "REPLAY_SCHEMA",
    "replay_formal_root",
]
