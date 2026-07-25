#!/usr/bin/env python3
"""Corrected independent flat-instance check for the a002 geometry attempt.

The immutable v1 implementation correctly handles manufacturing entities but
mistook the required ``generic_io`` core/boundary instances for operation
groups.  This wrapper snapshots and executes those v1 bytes, independently
checks that the only non-group operation is exactly the expected 47
``generic_io`` entities, removes that classification field in an in-memory
copy, and then runs the unchanged flat derivation.  It never imports the
primary recomputation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from types import ModuleType
from typing import Any


HELPER = Path(__file__).with_name(
    "verify_entity_endpoint_budget_independent_v1.py"
)
HELPER_ID = {
    "size_bytes": 22_368,
    "sha256": "ced07b522cbc21e25f4b59740f51885643afa97925c68da115b8cddf93c6063b",
    "mode_octal": "0644",
}
STRICT_SHA = (
    "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
)


class IndependentV2Error(RuntimeError):
    """Raised when the corrected independent path cannot replay exactly."""


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
            raise IndependentV2Error(f"{label}: not regular")
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
        raise IndependentV2Error(f"{label}: changed during read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise IndependentV2Error(f"{label}: short read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
    }


def load_helper(raw: bytes) -> ModuleType:
    name = "_b1_sidewise_independent_v1_snapshot"
    module = ModuleType(name)
    module.__file__ = str(HELPER)
    module.__package__ = None
    sys.modules[name] = module
    exec(
        compile(raw, str(HELPER), "exec", dont_inherit=True),
        module.__dict__,
    )
    return module


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
                raise IndependentV2Error("short output write")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--geometry-authority", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        helper_raw, helper_identity = snapshot(HELPER, "v1 helper")
        for field, expected in HELPER_ID.items():
            if helper_identity.get(field) != expected:
                raise IndependentV2Error(f"v1 helper {field} drifted")
        helper = load_helper(helper_raw)
        strict_raw, strict_identity = snapshot(args.instance, "strict instance")
        if strict_identity["sha256"] != STRICT_SHA:
            raise IndependentV2Error("strict SHA-256 mismatch")
        _, tool_identity = snapshot(Path(__file__), "independent v2 tool")
        authority_identity = helper.check_authority(
            args.geometry_authority,
            tool_identity,
            strict_identity,
        )
        data = helper.object_(
            helper.decode(strict_raw, "strict instance"),
            "strict instance",
        )
        group_ids = {
            str(group.get("id"))
            for group in helper.list_(data.get("operation_groups"), "groups")
            if isinstance(group, dict)
        }
        corrected = copy.deepcopy(data)
        generic_rows: list[dict[str, Any]] = []
        for item in helper.list_(
            corrected.get("required_instances"), "required"
        ):
            row = helper.object_(item, "required row")
            operation = row.get("operation")
            if operation not in group_ids:
                generic_rows.append(row)
                if operation != "generic_io":
                    raise IndependentV2Error(
                        "unexpected non-group operation identity"
                    )
                row.pop("operation")
        generic_templates = {
            str(row.get("template")) for row in generic_rows
        }
        if len(generic_rows) != 47 or generic_templates != {
            "boundary_storage_port",
            "protocol_core",
        }:
            raise IndependentV2Error("generic_io entity partition drifted")
        results = helper.derive_flat(corrected)
        results["generic_io_classification_fix"] = {
            "status": "PASS",
            "entity_count": len(generic_rows),
            "templates": sorted(generic_templates),
            "v1_helper": helper_identity,
        }
        report = {
            "schema_version": "b1_sidewise_independent_recomputation_v1",
            "status": "PASS",
            "tool": tool_identity,
            "geometry_authority": authority_identity,
            "strict_instance": strict_identity,
            "results": results,
            "claim_boundary": {
                "independent_geometry_recomputation_only": True,
                "pb_or_formal_proof": False,
                "upper_updated": False,
                "production_certified": False,
            },
        }
        raw = (
            json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False)
            + "\n"
        ).encode()
        if args.output.exists() or args.output.is_symlink():
            raise IndependentV2Error("output exists")
        if args.output.parent.is_symlink() or not args.output.parent.is_dir():
            raise IndependentV2Error("output parent is not a real directory")
        write_once(args.output, raw)
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 2
    print(
        json.dumps(
            {
                "status": "PASS",
                "output": str(args.output),
                "size_bytes": len(raw),
                "sha256": sha(raw),
                "combined_inside_cap": results["combined_inside_cap"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
