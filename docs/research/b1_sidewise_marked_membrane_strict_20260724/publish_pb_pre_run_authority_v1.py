#!/usr/bin/env python3
"""Freeze PB/formal inputs and tools after geometry admission."""

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
RESEARCH = ROOT / "docs/research/b1_sidewise_marked_membrane_strict_20260724"
RESUME = RUN / "resume-a001/authority.json"
RESUME_ID = {
    "size_bytes": 3_993,
    "sha256": "24a896999cdea34e3fcde84a1f14be8516f321bbbe3654dd856b1116994b3ca8",
    "mode_octal": "0644",
}
GEOMETRY = RUN / "geometry-admission-a002/admission.json"
GEOMETRY_ID = {
    "size_bytes": 3_075,
    "sha256": "abb67f2334756a22650457b3a066d32b48b7d5f8918406b53f4f4140ec3fbfdc",
    "mode_octal": "0644",
}
STRICT = (
    SOURCE_ROOT
    / "docs/research/cleanroom_rederivation_20260718"
    / "strict/external/problem_instance.json"
)
STRICT_ID = {
    "size_bytes": 92_201,
    "sha256": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    "mode_octal": "0644",
}
TOOLS = {
    "encoder": RESEARCH / "ceiling_exclusion_pb_encoder_v1.py",
    "translation_gate": RESEARCH / "verify_ceiling_exclusion_translation_v1.py",
    "formal_worker": RESEARCH / "run_ceiling_exclusion_formal_v1.py",
    "formal_launcher": RESEARCH / "launch_ceiling_exclusion_formal_v1.py",
    "formal_closer": RESEARCH / "close_ceiling_exclusion_formal_v1.py",
}
ROUNDINGSAT = Path("/home/zhuran24/tools/roundingsat/build/roundingsat")
ROUNDINGSAT_ID = {
    "size_bytes": 2_305_360,
    "sha256": "08bb2542bcf09d99366f35e6fcfc7c79e002eca360ab9da027944c719fa3f8bf",
    "mode_octal": "0755",
}
VERIPB = Path("/home/zhuran24/.cargo/bin/veripb")
VERIPB_ID = {
    "size_bytes": 3_317_320,
    "sha256": "a0c72df075b924af3b698ae808f86d3b55067168534397a0cc3d49594777b971",
    "mode_octal": "0755",
}
FIXED_PYTHON = Path(
    "/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13"
)
FIXED_PYTHON_TARGET_ID = {
    "size_bytes": 31_514_832,
    "sha256": "74fceb0fdd29c31cf066ac8d92465975ea4ac8592308d7c888e26a70092d8eeb",
    "mode_octal": "0755",
}


class AuthorityError(RuntimeError):
    """Raised when the PB pre-run authority cannot close."""


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def snapshot(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    fd = os.open(
        path.absolute(),
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise AuthorityError(f"{label}: not regular")
        chunks: list[bytes] = []
        while True:
            block = os.read(fd, 1 << 20)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise AuthorityError(f"{label}: changed during read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise AuthorityError(f"{label}: short read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
    }


def resolved_executable(path: Path, label: str) -> dict[str, Any]:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise AuthorityError(f"{label}: cannot resolve: {exc}") from exc
    raw, target = snapshot(resolved, f"{label} target")
    del raw
    return {
        "path": str(path.absolute()),
        "resolved_path": str(resolved),
        "target": target,
    }


def parse(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AuthorityError(f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise AuthorityError(f"{label}: non-integer JSON {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorityError(f"{label}: malformed JSON: {exc}") from exc


def expect(actual: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    for field, value in expected.items():
        if actual.get(field) != value:
            raise AuthorityError(f"{label}: {field} drifted")


def build_payload() -> dict[str, Any]:
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != HEAD:
        raise AuthorityError("successor HEAD drifted")
    resume_raw, resume_identity = snapshot(RESUME, "resume authority")
    expect(resume_identity, RESUME_ID, "resume authority")
    resume = parse(resume_raw, "resume authority")
    runner = resume.get("upstream_runner_authority") if isinstance(resume, dict) else None
    replay = resume.get("upstream_formal_replay") if isinstance(resume, dict) else None
    if (
        not isinstance(resume, dict)
        or resume.get("status") != "RESUME_AUTHORITY_PASS"
        or not isinstance(runner, dict)
        or runner.get("snapshot_execution") != "same_fd_snapshot_compile_exec"
        or runner.get("runner", {}).get("sha256")
        != "869f6bd6bcab88c73a989a68e288e8ac68eb026e7791e976e2289de7285dd24f"
        or not isinstance(replay, dict)
        or replay.get("status") != "VERIFIED"
        or replay.get("proof_status") != "VERIFIED UNSATISFIABLE"
        or replay.get("upper_bound_update_authorized") is not True
    ):
        raise AuthorityError("upstream formal replay authority failed")
    geometry_raw, geometry_identity = snapshot(GEOMETRY, "geometry admission")
    expect(geometry_identity, GEOMETRY_ID, "geometry admission")
    geometry = parse(geometry_raw, "geometry admission")
    if (
        not isinstance(geometry, dict)
        or geometry.get("status") != "PASS"
        or geometry.get("decision") != "ADMITTED_FOR_PB_ENCODER"
        or geometry.get("established", {}).get("smm_209_necessary_bound")
        is not True
        or geometry.get("claim_boundary", {}).get("upper_remains")
        != [1188, 22]
    ):
        raise AuthorityError("geometry admission semantics failed")
    strict_raw, strict_identity = snapshot(STRICT, "strict instance")
    del strict_raw
    expect(strict_identity, STRICT_ID, "strict instance")
    tools: dict[str, Any] = {}
    for key, path in TOOLS.items():
        raw, identity = snapshot(path, key)
        del raw
        tools[key] = identity
    roundingsat_raw, roundingsat_identity = snapshot(
        ROUNDINGSAT, "RoundingSat"
    )
    del roundingsat_raw
    expect(roundingsat_identity, ROUNDINGSAT_ID, "RoundingSat")
    veripb_raw, veripb_identity = snapshot(VERIPB, "VeriPB")
    del veripb_raw
    expect(veripb_identity, VERIPB_ID, "VeriPB")
    python_identity = resolved_executable(FIXED_PYTHON, "fixed Python")
    expect(
        python_identity["target"],
        FIXED_PYTHON_TARGET_ID,
        "fixed Python target",
    )
    self_raw, self_identity = snapshot(Path(__file__), "PB authority publisher")
    del self_raw
    return {
        "schema_version": "b1_sidewise_pb_pre_run_authority_v1",
        "status": "PB_PRE_RUN_AUTHORITY_PASS",
        "head": HEAD,
        "run": str(RUN.relative_to(ROOT)),
        "resume_authority": resume_identity,
        "upstream_formal": {
            "runner": runner["runner"],
            "runner_execution": runner["snapshot_execution"],
            "old_receipt": replay["receipt"],
            "old_band_replay_status": replay["status"],
            "old_proof_status": replay["proof_status"],
            "old_upper": [1188, 22],
        },
        "geometry_admission": geometry_identity,
        "strict_instance": strict_identity,
        "tools": tools,
        "binaries": {
            "roundingsat": roundingsat_identity,
            "veripb": veripb_identity,
            "fixed_python": python_identity,
        },
        "publisher": self_identity,
        "resource_contract": {
            "memory_high_bytes": 35 * 1024**3,
            "memory_max_bytes": 39 * 1024**3,
            "memory_swap_max_bytes": 16 * 1024**3,
            "oom_policy": "continue",
            "kill_mode": "control-group",
            "send_sigkill": "yes",
            "proof_limit_bytes": 5_000_000_000,
            "artifact_low_water_bytes": 10 * 1024**3,
            "required_free_before_formal_bytes": (
                10 * 1024**3 + 5_000_000_000
            ),
            "single_worker": True,
            "formal_attempt_limit": 1,
        },
        "authorization": {
            "estimate": True,
            "build_only": True,
            "translation_gate": True,
            "formal_preflight": True,
            "formal_attempt": (
                "conditional_on_translation_and_resource_gates"
            ),
            "upper_update": (
                "conditional_on_verified_unsat_and_terminal_envelope"
            ),
        },
        "ledger_before": {"upper": [1188, 22], "lower": "absent"},
        "claim_boundary": {
            "pre_run_byte_closure_only": True,
            "formal_not_yet_run": True,
            "upper_updated": False,
            "witness_or_attainability": False,
            "optimality": False,
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
                raise AuthorityError("short output write")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(output_dir: Path) -> dict[str, Any]:
    if output_dir != RUN / "pb-authority-a001":
        raise AuthorityError("output must be fixed pb-authority-a001")
    if output_dir.exists() or output_dir.is_symlink():
        raise AuthorityError("PB authority output exists")
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
            {"status": build_payload()["status"], "dry_run": True}
            if args.dry_run
            else publish(args.output_dir.absolute())
        )
    except (OSError, AuthorityError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
