#!/usr/bin/env python3
"""Check external large-artifact contracts.

By default, artifacts marked optional in the lightweight GitHub checkout may be
absent. Use `--require` to make a specific artifact mandatory before running a
full certified-exact solve that needs it.
"""
from __future__ import annotations

import argparse
import sys

from external_artifacts import find_artifact, load_manifest, verify_artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Check external large-artifact contracts.")
    parser.add_argument("--require", action="append", default=[], help="Artifact id that must be present.")
    args = parser.parse_args()

    try:
        artifacts = load_manifest()
    except Exception as exc:  # noqa: BLE001 - manifest parse error should be reported plainly.
        print(f"external artifact check failed: {exc}", file=sys.stderr)
        return 2

    required = set(args.require)
    errors: list[str] = []
    notes: list[str] = []
    for artifact in artifacts:
        if artifact.artifact_id in required:
            object.__setattr__(artifact, "optional_in_lightweight_checkout", False)
        ok, message = verify_artifact(artifact)
        if ok:
            notes.append(message)
        else:
            errors.append(message)

    for artifact_id in sorted(required - {a.artifact_id for a in artifacts}):
        try:
            find_artifact(artifact_id)
        except KeyError:
            errors.append(f"unknown required external artifact: {artifact_id}")

    if errors:
        print("external artifact check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("external artifact check passed: " + "; ".join(notes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
