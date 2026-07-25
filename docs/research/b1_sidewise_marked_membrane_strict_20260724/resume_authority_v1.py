#!/usr/bin/env python3
"""Publish the post-pause authority for the strict sidewise-membrane run.

The historical SMM1 bootstrap is immutable and did not bind the untracked
upstream formal runner's bytes.  This successor authority closes that gap:
it snapshots the runner once through an O_NOFOLLOW file descriptor, checks
that snapshot against the old toolchain record, and executes that exact
snapshot with ``compile``/``exec``.  It never imports the runner by pathname.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import ModuleType
from typing import Any


SUCCESSOR_ROOT = Path(
    "/home/zhuran24/zmd-pj-codex-baselines/"
    "track-b-b1-sidewise-membrane-20260724"
)
SOURCE_ROOT = Path(
    "/home/zhuran24/zmd-pj-codex-baselines/"
    "track-b-b0-1190-20260721"
)
EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"

OLD_RUN = (
    SUCCESSOR_ROOT
    / ".artifacts/track_b_b1_sidewise_marked_membrane_20260724"
    / "run-20260723T155052Z-SMM1"
)
OLD_AUTHORITY = OLD_RUN / "bootstrap-a001/authority.json"
OLD_PAUSE = OLD_RUN / "PAUSE_FOR_USER_GAME_END.json"
OLD_AUTHORITY_ID = {
    "size_bytes": 9_236,
    "sha256": "7257d87767a2e81703281d8849744d741838147a9e380484e9b30bd48ed9f1f8",
}
OLD_PAUSE_ID = {
    "size_bytes": 1_018,
    "sha256": "96f9ced9b0c8547304ccce9ecae4df752af0060bc5111082f20ecc5bce218363",
}

UPSTREAM_ARTIFACT_ROOT = (
    SOURCE_ROOT / ".artifacts/track_b_b1_r4_1188_22_pb_20260723"
)
BUILD_DIR = (
    UPSTREAM_ARTIFACT_ROOT / "build-a001-20260723T091353Z-398f8725"
)
FORMAL_DIR = (
    UPSTREAM_ARTIFACT_ROOT / "formal-a001-20260723T091800Z-398f8725"
)
TOOLCHAIN_RECORD = FORMAL_DIR / "toolchain_record.json"
TOOLCHAIN_RECORD_ID = {
    "size_bytes": 154_545,
    "sha256": "b99c9dd62b9be3c06de93d125bd2feaadc761f9eb541eb3d39a72070f33314f3",
    "mode_octal": "0644",
}
FORMAL_RUNNER = (
    SOURCE_ROOT
    / "docs/research/b1_r4_1188_22_pb_20260723"
    / "run_b1_r4_1188_22_pb_toolchain_v1.py"
)
FORMAL_RUNNER_ID = {
    "size_bytes": 169_658,
    "sha256": "869f6bd6bcab88c73a989a68e288e8ac68eb026e7791e976e2289de7285dd24f",
    "mode_octal": "0644",
}
FORMAL_RECEIPT_ID = {
    "path": (
        ".artifacts/track_b_b1_r4_1188_22_pb_20260723/"
        "formal-a001-20260723T091800Z-398f8725/authority_receipt.json"
    ),
    "size_bytes": 2_613,
    "sha256": "0b3366a3e1640a13675a28d1408b9b96ede3a0e6403e71a8f9222f1f44e5b5c2",
}
STRICT_INSTANCE = (
    SOURCE_ROOT
    / "docs/research/cleanroom_rederivation_20260718"
    / "strict/external/problem_instance.json"
)
STRICT_INSTANCE_ID = {
    "size_bytes": 92_201,
    "sha256": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    "mode_octal": "0644",
}
ARTIFACT_ROOT = (
    SUCCESSOR_ROOT
    / ".artifacts/track_b_b1_sidewise_marked_membrane_strict_20260724"
)


class AuthorityError(RuntimeError):
    """Raised when a byte, semantic, or output authority check fails."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict_json(raw: bytes, label: str) -> Any:
    def reject_constant(value: str) -> Any:
        raise AuthorityError(f"{label}: non-finite JSON number {value!r}")

    def reject_float(value: str) -> Any:
        raise AuthorityError(f"{label}: floating-point JSON number {value!r}")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AuthorityError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorityError(f"{label}: invalid strict JSON: {exc}") from exc


def _read_same_fd(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    """Read, identify, and verify a file through one O_NOFOLLOW descriptor."""

    absolute = path.absolute()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(
        os, "O_NOFOLLOW", 0
    )
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise AuthorityError(f"{label}: cannot open: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise AuthorityError(f"{label}: not a regular file")
        chunks: list[bytes] = []
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    stable_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_nlink",
        "st_uid",
        "st_gid",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    if any(getattr(before, field) != getattr(after, field) for field in stable_fields):
        raise AuthorityError(f"{label}: file changed during same-FD read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise AuthorityError(f"{label}: short or extended read")
    return raw, {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": _sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
        "device": before.st_dev,
        "inode": before.st_ino,
        "link_count": before.st_nlink,
    }


def _expect_identity(
    actual: dict[str, Any],
    expected: dict[str, Any],
    label: str,
) -> None:
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            raise AuthorityError(
                f"{label}: {key} drifted: "
                f"{actual.get(key)!r} != {expected_value!r}"
            )


def _snapshot_json(
    path: Path,
    expected: dict[str, Any],
    label: str,
) -> tuple[Any, dict[str, Any], bytes]:
    raw, identity = _read_same_fd(path, label)
    _expect_identity(identity, expected, label)
    return _strict_json(raw, label), identity, raw


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _load_runner_snapshot(raw: bytes) -> ModuleType:
    """Execute the already-verified runner bytes without reopening its path."""

    name = "_b1_sidewise_upstream_formal_runner_snapshot"
    module = ModuleType(name)
    module.__file__ = str(FORMAL_RUNNER)
    module.__package__ = None
    sys.modules[name] = module
    code = compile(raw, str(FORMAL_RUNNER), "exec", dont_inherit=True)
    exec(code, module.__dict__)
    return module


def _replay_formal_authority(
    runner_raw: bytes,
    runner_identity: dict[str, Any],
    toolchain_payload: Any,
) -> dict[str, Any]:
    if not isinstance(toolchain_payload, dict):
        raise AuthorityError("toolchain record is not an object")
    sources = toolchain_payload.get("sources")
    if not isinstance(sources, dict):
        raise AuthorityError("toolchain record sources missing")
    expected_record = {
        "path": (
            "docs/research/b1_r4_1188_22_pb_20260723/"
            "run_b1_r4_1188_22_pb_toolchain_v1.py"
        ),
        "size_bytes": FORMAL_RUNNER_ID["size_bytes"],
        "sha256": FORMAL_RUNNER_ID["sha256"],
    }
    for phase in ("before", "after"):
        phase_payload = sources.get(phase)
        if not isinstance(phase_payload, dict):
            raise AuthorityError(f"toolchain sources.{phase} missing")
        if phase_payload.get("runner") != expected_record:
            raise AuthorityError(
                f"toolchain sources.{phase}.runner identity drifted"
            )
    _expect_identity(runner_identity, FORMAL_RUNNER_ID, "formal runner")
    module = _load_runner_snapshot(runner_raw)
    replay = getattr(module, "_replay_authority_receipt", None)
    if not callable(replay):
        raise AuthorityError("snapshotted runner lacks replay function")
    result = replay(
        FORMAL_DIR,
        UPSTREAM_ARTIFACT_ROOT / "formal_attempt_a001.reservation.json",
        BUILD_DIR / "build_record.json",
        BUILD_DIR / "SHA256SUMS",
        SOURCE_ROOT,
        FORMAL_RECEIPT_ID,
    )
    summary = {
        "status": result["status"],
        "claim": result["claim"],
        "proof_status": result["payload"]["proof_status"],
        "upper_bound_update_authorized": result["payload"][
            "upper_bound_update_authorized"
        ],
        "production_certified": result["payload"]["production_certified"],
        "receipt": result["receipt"],
        "execution": "same_fd_snapshot_compile_exec",
    }
    expected_claim = (
        "machine_verified_complete_lex_better_band_unsat_"
        "given_a004_admitted_geometric_lemmas"
    )
    if (
        summary["status"] != "VERIFIED"
        or summary["claim"] != expected_claim
        or summary["proof_status"] != "VERIFIED UNSATISFIABLE"
        or summary["upper_bound_update_authorized"] is not True
        or summary["production_certified"] is not False
        or summary["receipt"] != FORMAL_RECEIPT_ID
    ):
        raise AuthorityError("upstream formal replay did not reproduce VERIFIED")
    return summary


def _write_exclusive(path: Path, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(
        os, "O_NOFOLLOW", 0
    )
    descriptor = os.open(path, flags, 0o644)
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(descriptor, raw[offset:])
            if count <= 0:
                raise AuthorityError(f"short write: {path}")
            offset += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode()


def build_payload(game_end_authorized: bool) -> dict[str, Any]:
    if game_end_authorized is not True:
        raise AuthorityError("explicit game-end authorization is required")
    if _git_head(SUCCESSOR_ROOT) != EXPECTED_HEAD:
        raise AuthorityError("successor HEAD drifted")
    old_authority, old_authority_identity, _ = _snapshot_json(
        OLD_AUTHORITY,
        OLD_AUTHORITY_ID,
        "SMM1 authority",
    )
    old_pause, old_pause_identity, _ = _snapshot_json(
        OLD_PAUSE,
        OLD_PAUSE_ID,
        "SMM1 pause",
    )
    if not isinstance(old_authority, dict) or not isinstance(old_pause, dict):
        raise AuthorityError("historical SMM1 payload is malformed")
    if (
        old_authority.get("status") != "AUTHORITY_REPLAY_PASS"
        or old_authority.get("ledger")
        != {"upper": [1_188, 22], "lower": "absent"}
        or old_pause.get("status") != "PAUSE_FOR_USER_GAME_END"
        or old_pause.get("authority", {}).get("size_bytes")
        != OLD_AUTHORITY_ID["size_bytes"]
        or old_pause.get("authority", {}).get("sha256")
        != OLD_AUTHORITY_ID["sha256"]
    ):
        raise AuthorityError("historical SMM1 semantics drifted")
    toolchain_payload, toolchain_identity, _ = _snapshot_json(
        TOOLCHAIN_RECORD,
        TOOLCHAIN_RECORD_ID,
        "old formal toolchain record",
    )
    runner_raw, runner_identity = _read_same_fd(
        FORMAL_RUNNER,
        "old formal replay runner",
    )
    _expect_identity(runner_identity, FORMAL_RUNNER_ID, "old formal replay runner")
    strict_raw, strict_identity = _read_same_fd(
        STRICT_INSTANCE,
        "strict instance",
    )
    del strict_raw
    _expect_identity(strict_identity, STRICT_INSTANCE_ID, "strict instance")
    replay = _replay_formal_authority(
        runner_raw,
        runner_identity,
        toolchain_payload,
    )
    self_raw, self_identity = _read_same_fd(
        Path(__file__),
        "resume authority tool",
    )
    del self_raw
    return {
        "schema_version": "b1_sidewise_membrane_resume_authority_v1",
        "status": "RESUME_AUTHORITY_PASS",
        "game_end_authorization": {
            "explicit_user_authorization_received": True,
            "scope": (
                "resume approved Track B sidewise-membrane plan from "
                "PAUSE_FOR_USER_GAME_END"
            ),
        },
        "successor": {
            "root": str(SUCCESSOR_ROOT),
            "head": EXPECTED_HEAD,
        },
        "historical_pause": {
            "authority": old_authority_identity,
            "pause": old_pause_identity,
            "immutable": True,
        },
        "upstream_runner_authority": {
            "runner": runner_identity,
            "old_toolchain_record": toolchain_identity,
            "toolchain_before_after_match": True,
            "snapshot_execution": "same_fd_snapshot_compile_exec",
        },
        "strict_instance": strict_identity,
        "resume_authority_tool": self_identity,
        "upstream_formal_replay": replay,
        "ledger_before": {"upper": [1_188, 22], "lower": "absent"},
        "claim_boundary": {
            "authority_hardening_only": True,
            "geometry_admitted": False,
            "pb_or_solver_executed": False,
            "upper_updated": False,
            "production_certified": False,
        },
    }


def publish(output_dir: Path, game_end_authorized: bool) -> dict[str, Any]:
    if output_dir.parent != ARTIFACT_ROOT:
        raise AuthorityError("output must be a direct child of the artifact root")
    if output_dir.exists() or output_dir.is_symlink():
        raise AuthorityError("output run already exists")
    if ARTIFACT_ROOT.exists():
        if ARTIFACT_ROOT.is_symlink() or not ARTIFACT_ROOT.is_dir():
            raise AuthorityError("artifact root is not a real directory")
    else:
        ARTIFACT_ROOT.mkdir(mode=0o755)
    payload = build_payload(game_end_authorized)
    output_dir.mkdir(mode=0o755)
    resume_dir = output_dir / "resume-a001"
    resume_dir.mkdir(mode=0o755)
    raw = _json_bytes(payload)
    _write_exclusive(resume_dir / "authority.json", raw)
    sums = f"{_sha(raw)}  authority.json\n".encode()
    _write_exclusive(resume_dir / "SHA256SUMS", sums)
    return {
        "status": payload["status"],
        "authority": {
            "path": str((resume_dir / "authority.json").relative_to(SUCCESSOR_ROOT)),
            "size_bytes": len(raw),
            "sha256": _sha(raw),
        },
        "upstream_formal_replay": payload["upstream_formal_replay"]["status"],
        "ledger": payload["ledger_before"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--game-end-authorized",
        action="store_true",
        help="record the user's explicit authorization to leave the pause",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.dry_run:
            payload = build_payload(args.game_end_authorized)
            result = {
                "status": payload["status"],
                "upstream_formal_replay": payload["upstream_formal_replay"][
                    "status"
                ],
                "ledger": payload["ledger_before"],
            }
        else:
            result = publish(
                args.output_dir.absolute(),
                args.game_end_authorized,
            )
    except (AuthorityError, OSError, subprocess.SubprocessError) as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL_CLOSED",
                    "error": str(exc),
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
