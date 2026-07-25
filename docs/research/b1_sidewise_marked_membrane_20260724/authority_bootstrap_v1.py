#!/usr/bin/env python3
"""Create the no-overwrite authority and game-pause receipt for this B1 round."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
SOURCE_ROOT = Path("/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721")
SUCCESSOR_ROOT = Path(__file__).resolve().parents[3]
CORE_PLAN = Path("/home/zhuran24/zmd-pj/ccc_last_reply_20260720.md")
CORE_PLAN_SHA256 = "0987d2d0a22da57b72ee94e3eb4d232a7389461f2ed031764d938a0789157422"
PROJECT_LOCK_SHA256 = "33632dfdb2297425e42066b2cf0749ca6b9ab1f8653e810b6f2e53ded1025410"
STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
A004_SHA256 = "2ebceb7bcdf93ad8cffa75e49eef89af679729f64a47a06ae27fa44682c206ff"
FORMAL_RECEIPT_SHA256 = "0b3366a3e1640a13675a28d1408b9b96ede3a0e6403e71a8f9222f1f44e5b5c2"
R4_SELECTED_RECEIPT_SHA256 = "cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4"
R4_PACKAGE_ID = "1a1288a705e699b406d6636c56170f39cb2aecfce18337943e6114035b53369f"
SOURCE_DIFF_SHA256 = "d46364394e6408a0fd6dc5a3d718c3175439b3698bd4587baf3dcb87c7c9f21a"
SOURCE_DIFF_SIZE = 4616
SOURCE_STATUS_SHA256 = "a1b5ac32109602d7ae65d49c37bf487ae6c9887718fe05cbd7b455e80d1b5c6d"
SOURCE_STATUS_SIZE = 1173

ARTIFACT_ROOT = SUCCESSOR_ROOT / ".artifacts/track_b_b1_sidewise_marked_membrane_20260724"
RUN_RE = re.compile(r"run-[0-9]{8}T[0-9]{6}Z-[A-Za-z0-9_-]{4,16}")

A004_PATH = (
    SOURCE_ROOT
    / ".artifacts/track_b_r4_external_brain_handoff_20260722"
    / "responses/run-20260723T023657Z-R4resp-357f260d"
    / "admission/a004/admission.json"
)
R4_PACKAGE_SHA_PATH = (
    SOURCE_ROOT
    / ".artifacts/track_b_r4_external_brain_handoff_20260722"
    / "run-20260722T084343Z-R4hP1A/package/SHA256SUMS"
)
R4_SELECTED_RECEIPT_PATH = (
    SOURCE_ROOT
    / ".artifacts/track_b_r4_external_brain_handoff_20260722"
    / "run-20260722T084343Z-R4hP1A"
    / "verifications/independent-a002-20260722T0845Z/receipt.json"
)
BUILD_DIR = SOURCE_ROOT / ".artifacts/track_b_b1_r4_1188_22_pb_20260723" / "build-a001-20260723T091353Z-398f8725"
FORMAL_DIR = SOURCE_ROOT / ".artifacts/track_b_b1_r4_1188_22_pb_20260723" / "formal-a001-20260723T091800Z-398f8725"
FORMAL_RECEIPT_PATH = FORMAL_DIR / "authority_receipt.json"
FORMAL_RUNNER_PATH = SOURCE_ROOT / "docs/research/b1_r4_1188_22_pb_20260723" / "run_b1_r4_1188_22_pb_toolchain_v1.py"

OVERLAY_PATHS = (
    "scripts/preflight_gate.py",
    "src/tests/test_preflight_gate.py",
    "src/tests/test_r1_upper_bound_pb_v1.py",
)
OWNED_PATHS = (
    "scripts/preflight_gate.py",
    "src/tests/test_preflight_gate.py",
    "src/tests/test_r1_upper_bound_pb_v1.py",
    "src/tests/test_b1_sidewise_marked_membrane_v1.py",
    "docs/research/b1_sidewise_marked_membrane_20260724/README.md",
    "docs/research/b1_sidewise_marked_membrane_20260724/01_necessity_proof.md",
    "docs/research/b1_sidewise_marked_membrane_20260724/02_model_contract.md",
    "docs/research/b1_sidewise_marked_membrane_20260724/03_execution_record.md",
    "docs/research/b1_sidewise_marked_membrane_20260724/authority_bootstrap_v1.py",
    "docs/research/b1_sidewise_marked_membrane_20260724/sidewise_marked_membrane_v1.py",
    "docs/research/b1_sidewise_marked_membrane_20260724/independent_sidewise_marked_membrane_v1.py",
    "docs/research/b1_sidewise_marked_membrane_20260724/fixtures/core_face_exclusivity.json",
    "docs/research/b1_sidewise_marked_membrane_20260724/fixtures/endpoint_capacity.json",
)


class BootstrapError(RuntimeError):
    """A provenance, authority, or no-overwrite gate failure."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_same_fd(path: Path, label: str) -> tuple[bytes, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise BootstrapError(f"cannot open {label}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise BootstrapError(f"{label} is not a regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        if identity_before != identity_after:
            raise BootstrapError(f"{label} changed during same-fd read")
        raw = b"".join(chunks)
        if len(raw) != before.st_size:
            raise BootstrapError(f"{label} short read")
        return raw, before
    finally:
        os.close(descriptor)


def file_record(path: Path, root: Path, label: str) -> dict[str, Any]:
    raw, metadata = _read_same_fd(path, label)
    try:
        display = str(path.resolve(strict=True).relative_to(root.resolve(strict=True)))
    except ValueError:
        display = str(path.resolve(strict=True))
    return {
        "path": display,
        "size_bytes": len(raw),
        "sha256": _sha256(raw),
        "mode": stat.S_IMODE(metadata.st_mode),
    }


def _expect_hash(path: Path, expected: str, label: str) -> dict[str, Any]:
    record = file_record(path, SUCCESSOR_ROOT, label)
    if record["sha256"] != expected:
        raise BootstrapError(f"{label} SHA-256 drifted")
    return record


def _git_bytes(root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
    )
    return completed.stdout


def _head(root: Path) -> str:
    return _git_bytes(root, "rev-parse", "HEAD").decode("ascii").strip()


def _source_git_snapshot() -> dict[str, Any]:
    if _head(SOURCE_ROOT) != EXPECTED_HEAD:
        raise BootstrapError("source authority HEAD drifted")
    exclusion = ":(exclude).artifacts/track_b_b1_r4_1188_22_pb_20260723/**"
    diff = _git_bytes(
        SOURCE_ROOT,
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "HEAD",
        "--",
        ".",
        exclusion,
    )
    status_bytes = _git_bytes(
        SOURCE_ROOT,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=normal",
        "--",
        ".",
        exclusion,
    )
    result = {
        "head": EXPECTED_HEAD,
        "tracked_diff_size_bytes": len(diff),
        "tracked_diff_sha256": _sha256(diff),
        "status_size_bytes": len(status_bytes),
        "status_sha256": _sha256(status_bytes),
        "artifact_exclusion": (".artifacts/track_b_b1_r4_1188_22_pb_20260723/**"),
    }
    expected = {
        "head": EXPECTED_HEAD,
        "tracked_diff_size_bytes": SOURCE_DIFF_SIZE,
        "tracked_diff_sha256": SOURCE_DIFF_SHA256,
        "status_size_bytes": SOURCE_STATUS_SIZE,
        "status_sha256": SOURCE_STATUS_SHA256,
        "artifact_exclusion": (".artifacts/track_b_b1_r4_1188_22_pb_20260723/**"),
    }
    if result != expected:
        raise BootstrapError("source authority Git snapshot drifted")
    return result


def _replay_formal_authority() -> dict[str, Any]:
    runner_raw, _ = _read_same_fd(FORMAL_RUNNER_PATH, "formal replay runner")
    del runner_raw
    spec = importlib.util.spec_from_file_location(
        "b1_sidewise_upstream_receipt_replay",
        FORMAL_RUNNER_PATH,
    )
    if spec is None or spec.loader is None:
        raise BootstrapError("cannot load formal replay runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    identity = {
        "path": (
            ".artifacts/track_b_b1_r4_1188_22_pb_20260723/formal-a001-20260723T091800Z-398f8725/authority_receipt.json"
        ),
        "size_bytes": 2613,
        "sha256": FORMAL_RECEIPT_SHA256,
    }
    result = module._replay_authority_receipt(
        FORMAL_DIR,
        (SOURCE_ROOT / ".artifacts/track_b_b1_r4_1188_22_pb_20260723" / "formal_attempt_a001.reservation.json"),
        BUILD_DIR / "build_record.json",
        BUILD_DIR / "SHA256SUMS",
        SOURCE_ROOT,
        identity,
    )
    summary = {
        "status": result["status"],
        "claim": result["claim"],
        "proof_status": result["payload"]["proof_status"],
        "upper_bound_update_authorized": result["payload"]["upper_bound_update_authorized"],
        "production_certified": result["payload"]["production_certified"],
        "receipt": result["receipt"],
    }
    expected_claim = "machine_verified_complete_lex_better_band_unsat_given_a004_admitted_geometric_lemmas"
    if (
        summary["status"] != "VERIFIED"
        or summary["claim"] != expected_claim
        or summary["proof_status"] != "VERIFIED UNSATISFIABLE"
        or summary["upper_bound_update_authorized"] is not True
        or summary["production_certified"] is not False
        or summary["receipt"] != identity
    ):
        raise BootstrapError("formal authority replay did not reproduce VERIFIED")
    return summary


def _overlay_records() -> dict[str, Any]:
    records: dict[str, Any] = {}
    for relative in OVERLAY_PATHS:
        source = SOURCE_ROOT / relative
        successor = SUCCESSOR_ROOT / relative
        source_raw, _ = _read_same_fd(source, f"source overlay {relative}")
        successor_raw, _ = _read_same_fd(successor, f"successor overlay {relative}")
        if source_raw != successor_raw:
            raise BootstrapError(f"successor overlay differs from source: {relative}")
        records[relative] = {
            "source": file_record(source, SOURCE_ROOT, f"source overlay {relative}"),
            "successor": file_record(
                successor,
                SUCCESSOR_ROOT,
                f"successor overlay {relative}",
            ),
        }
    return records


def _owned_records() -> dict[str, Any]:
    expected_research = {
        Path(relative).relative_to("docs/research/b1_sidewise_marked_membrane_20260724")
        for relative in OWNED_PATHS
        if relative.startswith("docs/research/b1_sidewise_marked_membrane_20260724/")
    }
    research_root = SUCCESSOR_ROOT / "docs/research/b1_sidewise_marked_membrane_20260724"
    actual_research = {
        path.relative_to(research_root)
        for path in research_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    if actual_research != expected_research:
        raise BootstrapError("owned research file set is not closed")
    return {
        relative: file_record(
            SUCCESSOR_ROOT / relative,
            SUCCESSOR_ROOT,
            f"owned source {relative}",
        )
        for relative in OWNED_PATHS
    }


def _write_exclusive(path: Path, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o644)
    try:
        written = 0
        while written < len(raw):
            count = os.write(descriptor, raw[written:])
            if count <= 0:
                raise BootstrapError(f"short write: {path}")
            written += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def _prepare_output(output_dir: Path) -> tuple[Path, Path]:
    if output_dir.parent != ARTIFACT_ROOT or RUN_RE.fullmatch(output_dir.name) is None:
        raise BootstrapError("output must be a canonical direct run child")
    if output_dir.exists() or output_dir.is_symlink():
        raise BootstrapError("output run already exists")
    if ARTIFACT_ROOT.exists():
        if ARTIFACT_ROOT.is_symlink() or not ARTIFACT_ROOT.is_dir():
            raise BootstrapError("artifact root is not a real directory")
    else:
        ARTIFACT_ROOT.mkdir(mode=0o755)
    output_dir.mkdir(mode=0o755)
    bootstrap_dir = output_dir / "bootstrap-a001"
    bootstrap_dir.mkdir(mode=0o755)
    return output_dir, bootstrap_dir


def build_payload() -> dict[str, Any]:
    if SOURCE_ROOT.is_symlink() or not SOURCE_ROOT.is_dir():
        raise BootstrapError("source authority root is not a real directory")
    if SUCCESSOR_ROOT.is_symlink() or not SUCCESSOR_ROOT.is_dir():
        raise BootstrapError("successor root is not a real directory")
    if _head(SUCCESSOR_ROOT) != EXPECTED_HEAD:
        raise BootstrapError("successor HEAD drifted")
    package_sha_record = _expect_hash(
        R4_PACKAGE_SHA_PATH,
        R4_PACKAGE_ID,
        "R4 package SHA256SUMS",
    )
    return {
        "schema_version": "b1_sidewise_membrane_bootstrap_authority_v1",
        "status": "AUTHORITY_REPLAY_PASS",
        "source_authority": {
            "root": str(SOURCE_ROOT),
            "git_snapshot": _source_git_snapshot(),
        },
        "successor": {
            "root": str(SUCCESSOR_ROOT),
            "head": EXPECTED_HEAD,
            "detached": (
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(SUCCESSOR_ROOT),
                        "symbolic-ref",
                        "-q",
                        "HEAD",
                    ],
                    check=False,
                    capture_output=True,
                ).returncode
                != 0
            ),
        },
        "inputs": {
            "core_plan": _expect_hash(CORE_PLAN, CORE_PLAN_SHA256, "core plan"),
            "project_lock": _expect_hash(
                SOURCE_ROOT / "PROJECT_LOCK.md",
                PROJECT_LOCK_SHA256,
                "PROJECT_LOCK",
            ),
            "strict_instance": _expect_hash(
                (
                    SOURCE_ROOT
                    / "docs/research/cleanroom_rederivation_20260718"
                    / "strict/external/problem_instance.json"
                ),
                STRICT_SHA256,
                "strict instance",
            ),
            "r4_package_sha256sums": package_sha_record,
            "r4_selected_receipt": _expect_hash(
                R4_SELECTED_RECEIPT_PATH,
                R4_SELECTED_RECEIPT_SHA256,
                "R4 selected receipt",
            ),
            "a004_admission": _expect_hash(
                A004_PATH,
                A004_SHA256,
                "a004 admission",
            ),
            "formal_receipt": _expect_hash(
                FORMAL_RECEIPT_PATH,
                FORMAL_RECEIPT_SHA256,
                "formal receipt",
            ),
        },
        "upstream_formal_replay": _replay_formal_authority(),
        "accepted_overlay": _overlay_records(),
        "owned_sources": _owned_records(),
        "ledger": {"upper": [1188, 22], "lower": "absent"},
        "claim_boundary": {
            "authority_bridge_only": True,
            "strict_recomputation_executed": False,
            "geometry_admitted": False,
            "pb_or_solver_executed": False,
            "upper_updated": False,
            "production_certified": False,
        },
    }


def publish(output_dir: Path) -> dict[str, Any]:
    payload = build_payload()
    output_dir, bootstrap_dir = _prepare_output(output_dir)
    authority_path = bootstrap_dir / "authority.json"
    authority_raw = _json_bytes(payload)
    _write_exclusive(authority_path, authority_raw)
    sums_raw = (f"{_sha256(authority_raw)}  authority.json\n").encode()
    _write_exclusive(bootstrap_dir / "SHA256SUMS", sums_raw)
    authority_identity = {
        "path": str(authority_path.relative_to(SUCCESSOR_ROOT)),
        "size_bytes": len(authority_raw),
        "sha256": _sha256(authority_raw),
    }
    pause = {
        "schema_version": "b1_sidewise_membrane_pause_v1",
        "status": "PAUSE_FOR_USER_GAME_END",
        "authority": authority_identity,
        "game_end_authorized": False,
        "completed": [
            "upstream_authority_replay",
            "isolated_successor_bootstrap",
            "lightweight_model_kernel",
            "synthetic_independent_fixture_checks",
            "reader_facing_terminal_documents",
        ],
        "forbidden_until_explicit_user_authorization": [
            "full_strict_instance_optimizer",
            "pb_encoder_or_build",
            "roundingsat",
            "veripb",
            "systemd_worker",
            "full_preflight",
        ],
        "next_gate": "explicit_user_message_confirming_game_has_ended",
        "ledger": {"upper": [1188, 22], "lower": "absent"},
        "claim_boundary": ("resume_checkpoint_only_no_geometry_admission_or_upper_update"),
    }
    pause_raw = _json_bytes(pause)
    _write_exclusive(output_dir / "PAUSE_FOR_USER_GAME_END.json", pause_raw)
    return {
        "status": pause["status"],
        "output_dir": str(output_dir),
        "authority": authority_identity,
        "pause": {
            "path": str((output_dir / "PAUSE_FOR_USER_GAME_END.json").relative_to(SUCCESSOR_ROOT)),
            "size_bytes": len(pause_raw),
            "sha256": _sha256(pause_raw),
        },
        "ledger": pause["ledger"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = publish(args.output_dir.absolute())
        print(json.dumps(result, sort_keys=True))
        return 0
    except (BootstrapError, OSError, subprocess.CalledProcessError) as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL_CLOSED",
                    "error": str(exc),
                    "ledger": {"upper": [1188, 22], "lower": "absent"},
                    "claim_boundary": "none",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
