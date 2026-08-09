#!/usr/bin/env python3
"""Run supplemental x66/dy0 target (10, 4, 4) via the pinned phase runner."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_phase_target.py"
EXPECTED_RUNNER = "e28d76a453a9a941c2a470bf1b3a460cdf226669019f22161d26c81e1145d43c"


def main() -> int:
    spec = importlib.util.spec_from_file_location("c5_count_closure_supplement_runner", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("phase runner import failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    base = module.load_base()
    base.require(base.sha256(RUNNER) == EXPECTED_RUNNER, "phase runner hash drift")
    module.TARGETS = set(module.TARGETS) | {(10, 4, 4)}
    return int(
        module.main(
            [
                "--attempt",
                "11",
                "--moved-x",
                "66",
                "--y-shift",
                "0",
                "--target",
                "10,4,4",
                "--seconds",
                "300",
            ]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
