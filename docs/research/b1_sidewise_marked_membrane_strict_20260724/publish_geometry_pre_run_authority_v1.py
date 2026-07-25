#!/usr/bin/env python3
"""Freeze every geometry input/tool byte before strict classification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
from typing import Any


ROOT = Path(
    "/home/zhuran24/zmd-pj-codex-baselines/"
    "track-b-b1-sidewise-membrane-20260724"
)
SOURCE_ROOT = Path(
    "/home/zhuran24/zmd-pj-codex-baselines/"
    "track-b-b0-1190-20260721"
)
HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
RUN = (
    ROOT
    / ".artifacts/track_b_b1_sidewise_marked_membrane_strict_20260724"
    / "run-20260723T161302Z-SMM2"
)
RESUME = RUN / "resume-a001/authority.json"
RESUME_EXPECTED = {
    "size_bytes": 3_993,
    "sha256": "24a896999cdea34e3fcde84a1f14be8516f321bbbe3654dd856b1116994b3ca8",
}
STRICT = (
    SOURCE_ROOT
    / "docs/research/cleanroom_rederivation_20260718"
    / "strict/external/problem_instance.json"
)
STRICT_EXPECTED = {
    "size_bytes": 92_201,
    "sha256": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    "mode_octal": "0644",
}
RESEARCH = ROOT / "docs/research/b1_sidewise_marked_membrane_strict_20260724"
TOOLS = {
    "primary_recomputation": RESEARCH / "recompute_entity_endpoint_budget_v1.py",
    "independent_recomputation": RESEARCH
    / "verify_entity_endpoint_budget_independent_v1.py",
    "adversarial_builder": RESEARCH
    / "build_geometry_adversarial_verdict_v1.py",
    "geometry_gate": RESEARCH / "close_geometry_admission_v1.py",
}
DOCUMENTS = {"necessity_proof": RESEARCH / "01_necessity_proof.md"}


class PublishError(RuntimeError):
    """Raised when the pre-run byte closure cannot be published."""


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_same_fd(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    absolute = path.absolute()
    try:
        if absolute.resolve(strict=True) != absolute:
            raise PublishError(f"{label}: noncanonical path")
    except OSError as exc:
        raise PublishError(f"{label}: cannot resolve: {exc}") from exc
    fd = os.open(
        absolute,
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise PublishError(f"{label}: not regular")
        chunks: list[bytes] = []
        while True:
            block = os.read(fd, 1 << 20)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    keys = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    if any(getattr(before, key) != getattr(after, key) for key in keys):
        raise PublishError(f"{label}: changed during read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise PublishError(f"{label}: short read")
    return raw, {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
    }


def parse_json(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise PublishError(f"{label}: duplicate key {key!r}")
            value[key] = item
        return value

    def reject(value: str) -> Any:
        raise PublishError(f"{label}: non-integer JSON {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublishError(f"{label}: malformed JSON: {exc}") from exc


def expect(record: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    for key, value in expected.items():
        if record.get(key) != value:
            raise PublishError(f"{label}: {key} drifted")


def build_payload() -> dict[str, Any]:
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != HEAD:
        raise PublishError("successor HEAD drifted")
    resume_raw, resume_identity = read_same_fd(RESUME, "resume authority")
    expect(resume_identity, RESUME_EXPECTED, "resume authority")
    resume = parse_json(resume_raw, "resume authority")
    if not isinstance(resume, dict):
        raise PublishError("resume authority not an object")
    runner = resume.get("upstream_runner_authority")
    replay = resume.get("upstream_formal_replay")
    if (
        resume.get("status") != "RESUME_AUTHORITY_PASS"
        or not isinstance(runner, dict)
        or runner.get("snapshot_execution") != "same_fd_snapshot_compile_exec"
        or runner.get("runner", {}).get("sha256")
        != "869f6bd6bcab88c73a989a68e288e8ac68eb026e7791e976e2289de7285dd24f"
        or not isinstance(replay, dict)
        or replay.get("status") != "VERIFIED"
        or replay.get("proof_status") != "VERIFIED UNSATISFIABLE"
        or replay.get("upper_bound_update_authorized") is not True
        or replay.get("production_certified") is not False
    ):
        raise PublishError("resume authority semantic replay failed")
    strict_raw, strict_identity = read_same_fd(STRICT, "strict instance")
    del strict_raw
    expect(strict_identity, STRICT_EXPECTED, "strict instance")
    tools: dict[str, Any] = {}
    for key, path in TOOLS.items():
        raw, identity = read_same_fd(path, key)
        del raw
        tools[key] = identity
    documents: dict[str, Any] = {}
    for key, path in DOCUMENTS.items():
        raw, identity = read_same_fd(path, key)
        del raw
        documents[key] = identity
    self_raw, self_identity = read_same_fd(Path(__file__), "authority publisher")
    del self_raw
    return {
        "schema_version": "b1_sidewise_geometry_pre_run_authority_v1",
        "status": "GEOMETRY_PRE_RUN_AUTHORITY_PASS",
        "head": HEAD,
        "run": str(RUN.relative_to(ROOT)),
        "resume_authority": resume_identity,
        "upstream_formal": {
            "runner": runner["runner"],
            "runner_execution": runner["snapshot_execution"],
            "replay_status": replay["status"],
            "proof_status": replay["proof_status"],
            "old_upper": [1188, 22],
            "production_certified": False,
        },
        "strict_instance": strict_identity,
        "tools": tools,
        "documents": documents,
        "publisher": self_identity,
        "authorization": {
            "strict_recomputation": True,
            "adversarial_review": True,
            "geometry_admission": True,
            "pb_or_formal": False,
        },
        "claim_boundary": {
            "pre_run_byte_closure_only": True,
            "geometry_result": "not_yet_run",
            "upper": [1188, 22],
            "lower": "absent",
            "production_certified": False,
        },
    }


def write_once(path: Path, raw: bytes) -> None:
    fd = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(fd, raw[offset:])
            if count <= 0:
                raise PublishError("short output write")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(output_dir: Path) -> dict[str, Any]:
    if output_dir != RUN / "geometry-authority-a001":
        raise PublishError("output must be the fixed no-overwrite authority path")
    if output_dir.exists() or output_dir.is_symlink():
        raise PublishError("geometry authority output exists")
    if RUN.is_symlink() or not RUN.is_dir():
        raise PublishError("strict run is not a real directory")
    payload = build_payload()
    output_dir.mkdir(mode=0o755)
    raw = (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode()
    write_once(output_dir / "authority.json", raw)
    write_once(
        output_dir / "SHA256SUMS",
        f"{sha(raw)}  authority.json\n".encode(),
    )
    return {
        "status": payload["status"],
        "authority": {
            "path": str((output_dir / "authority.json").relative_to(ROOT)),
            "size_bytes": len(raw),
            "sha256": sha(raw),
        },
        "tool_count": len(payload["tools"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = (
            {
                "status": build_payload()["status"],
                "dry_run": True,
            }
            if args.dry_run
            else publish(args.output_dir.absolute())
        )
    except (OSError, PublishError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
