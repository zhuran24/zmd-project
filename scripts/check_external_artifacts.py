#!/usr/bin/env python3
"""Check recoverable external artifacts declared in data/external_artifacts.json."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from external_artifacts import load_external_artifacts, validate_artifact  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        metavar="NAME|all",
        help="Require the named artifact to be present and hash-valid. Default: missing artifacts are reported but allowed.",
    )
    args = parser.parse_args()

    artifacts = load_external_artifacts()
    required = set(args.require)
    require_all = "all" in required
    failures: list[str] = []
    checked = 0
    missing_allowed = 0

    for name, artifact in artifacts.items():
        must_exist = require_all or name in required
        ok, message = validate_artifact(artifact)
        if ok:
            checked += 1
            print(f"OK {name}: {message}")
            continue
        if must_exist:
            failures.append(f"{name}: {message}")
            continue
        missing_allowed += 1
        print(f"MISSING-ALLOWED {name}: {message}; restore before {', '.join(artifact.required_for) or 'production use'}")

    if failures:
        print(f"external artifact check failed: {len(failures)} issue(s)", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(
        f"external artifact check passed: {checked} present, {missing_allowed} missing allowed, {len(artifacts)} declared"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
