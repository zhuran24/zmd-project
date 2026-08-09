#!/usr/bin/env python3
"""Publish the no-overwrite a002 geometry authority after v1 fail-closed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from types import ModuleType
from typing import Any


ROOT = Path(
    "/home/zhuran24/zmd-pj-codex-baselines/"
    "track-b-b1-sidewise-membrane-20260724"
)
RESEARCH = ROOT / "docs/research/b1_sidewise_marked_membrane_strict_20260724"
RUN = (
    ROOT
    / ".artifacts/track_b_b1_sidewise_marked_membrane_strict_20260724"
    / "run-20260723T161302Z-SMM2"
)
V1_PUBLISHER = RESEARCH / "publish_geometry_pre_run_authority_v1.py"
V1_PUBLISHER_ID = {
    "size_bytes": 9_444,
    "sha256": "fcc552203b4d0fe4816c879c2363334e9e38ebe333007110bd8265c432b8fb2e",
    "mode_octal": "0644",
}
V1_HELPER = RESEARCH / "verify_entity_endpoint_budget_independent_v1.py"
V1_HELPER_ID = {
    "size_bytes": 22_368,
    "sha256": "ced07b522cbc21e25f4b59740f51885643afa97925c68da115b8cddf93c6063b",
    "mode_octal": "0644",
}
PRIOR_AUTHORITY = RUN / "geometry-authority-a001/authority.json"
PRIOR_AUTHORITY_ID = {
    "size_bytes": 4_131,
    "sha256": "65971b88694964e0b0fd9d4c68c0e352cbbb20256a0cc44794c3a00bb210ce6a",
    "mode_octal": "0644",
}
PRIOR_PRIMARY = RUN / "recomputations-a001/primary.json"
PRIOR_PRIMARY_ID = {
    "size_bytes": 4_008,
    "sha256": "5b42ee69a79f44646ac849a6e707382bb502b038fe6a60c97d02a10eb158d3d1",
    "mode_octal": "0644",
}


class PublishV2Error(RuntimeError):
    """Raised when a002 cannot freeze a complete byte closure."""


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
            raise PublishV2Error(f"{label}: not regular")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
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
        raise PublishV2Error(f"{label}: changed during read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise PublishV2Error(f"{label}: short read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
    }


def expect(actual: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    for field, value in expected.items():
        if actual.get(field) != value:
            raise PublishV2Error(f"{label}: {field} drifted")


def load_v1(raw: bytes) -> ModuleType:
    name = "_b1_sidewise_geometry_authority_v1_snapshot"
    module = ModuleType(name)
    module.__file__ = str(V1_PUBLISHER)
    module.__package__ = None
    sys.modules[name] = module
    exec(
        compile(raw, str(V1_PUBLISHER), "exec", dont_inherit=True),
        module.__dict__,
    )
    return module


def build_payload() -> dict[str, Any]:
    v1_raw, v1_identity = snapshot(V1_PUBLISHER, "v1 publisher")
    expect(v1_identity, V1_PUBLISHER_ID, "v1 publisher")
    module = load_v1(v1_raw)
    module.TOOLS["independent_recomputation"] = (
        RESEARCH / "verify_entity_endpoint_budget_independent_v2.py"
    )
    payload = module.build_payload()
    prior_authority_raw, prior_authority_identity = snapshot(
        PRIOR_AUTHORITY, "a001 authority"
    )
    del prior_authority_raw
    expect(prior_authority_identity, PRIOR_AUTHORITY_ID, "a001 authority")
    prior_primary_raw, prior_primary_identity = snapshot(
        PRIOR_PRIMARY, "a001 primary"
    )
    del prior_primary_raw
    expect(prior_primary_identity, PRIOR_PRIMARY_ID, "a001 primary")
    helper_raw, helper_identity = snapshot(V1_HELPER, "v1 independent helper")
    del helper_raw
    expect(helper_identity, V1_HELPER_ID, "v1 independent helper")
    self_raw, self_identity = snapshot(Path(__file__), "a002 publisher")
    del self_raw
    payload["authority_generation"] = "a002"
    payload["prior_attempt"] = {
        "authority": prior_authority_identity,
        "primary_report": prior_primary_identity,
        "independent_status": "FAIL_CLOSED",
        "independent_exit_code": 2,
        "first_error": "flat operation-instance join mismatch",
        "admitted": False,
        "immutable_history": True,
    }
    payload["dependencies"] = {
        "independent_v1_helper": helper_identity,
        "v1_authority_publisher": v1_identity,
    }
    payload["publisher_wrapper"] = self_identity
    payload["claim_boundary"]["a001_failure_preserved"] = True
    return payload


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
                raise PublishV2Error("short output write")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(output_dir: Path) -> dict[str, Any]:
    if output_dir != RUN / "geometry-authority-a002":
        raise PublishV2Error("output must be fixed geometry-authority-a002")
    if output_dir.exists() or output_dir.is_symlink():
        raise PublishV2Error("a002 output already exists")
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
        "generation": payload["authority_generation"],
        "authority": {
            "path": str((output_dir / "authority.json").relative_to(ROOT)),
            "size_bytes": len(raw),
            "sha256": sha(raw),
        },
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
                "generation": "a002",
                "dry_run": True,
            }
            if args.dry_run
            else publish(args.output_dir.absolute())
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
