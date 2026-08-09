#!/usr/bin/env python3
"""Run the v2 small-bay weak active-terminal closure batch persistently."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
SCRIPTS = RECOVERY / "scripts"
SOURCE = SCRIPTS / "query_terminal_parent_triples_root.py"
HINT = RECOVERY / "inputs/reduced_targeted_allocation_p7_36_final.json"
OUTPUT = RECOVERY / "fixed_bays/final35_weak_closure_20260720.json"
EXPECTED = {
    SOURCE: "b8d0ab3b771b4ce4cd77cf5edd8d036a560f9b2126c542a549ae7c8caaf7042f",
    SCRIPTS / "reduced_connected_allocation.py": (
        "2f7382688565c0d3b180b5d41a1c66ae32c1733e83fa4d59bc05f631bc60afcc"
    ),
    SCRIPTS / "reduced_backbone_component_frontiers.py": (
        "15e027d9fc719daa7c904589a2c8cd068b83845bcda7d6393db7f4cf084263e4"
    ),
    SCRIPTS / "component_frontier_patterns.py": (
        "bd00682b3d03656d556073c4c2b4ed2f4cac565df96b9d9c08fa465dbbec1400"
    ),
    SCRIPTS / "current35_component_frontiers.py": (
        "13e1ed5bd5bc386970077ac51abd5eabb8a987dc9010f04c3d3026456f098861"
    ),
    SCRIPTS / "zmd_backbone_front_compact.py": (
        "14b128be038e29d4434e3de822740c961ace7c1d45f24bf4d50dd5f4b101c0be"
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_source() -> object:
    for path, expected in EXPECTED.items():
        observed = sha256(path)
        require(observed == expected, f"hash drift for {path}: {observed}")
    spec = importlib.util.spec_from_file_location("final35_weak_closure_source", SOURCE)
    require(spec is not None and spec.loader is not None, f"cannot load {SOURCE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["final35_weak_closure_source"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    require(not OUTPUT.exists(), f"refusing overwrite: {OUTPUT}")
    module = load_source()
    original_path = Path

    def persistent_path(value: object) -> Path:
        parsed = original_path(value)
        if parsed == original_path("/tmp/zmd_backbone_front_compact.py"):
            return SCRIPTS / "zmd_backbone_front_compact.py"
        return parsed

    module.BASE = SCRIPTS
    module.Path = persistent_path
    return int(
        module.main(
            [
                "--out",
                str(OUTPUT),
                "--queries",
                "11:9,1,2;12:5,1,1;13:5,1,1;14:5,1,1;15:4,2,0;16:4,2,0;4:11,4,4",
                "--seconds-per-query",
                "240",
                "--workers",
                "8",
                "--seed",
                "20260720",
                "--hint-source",
                str(HINT),
            ]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
