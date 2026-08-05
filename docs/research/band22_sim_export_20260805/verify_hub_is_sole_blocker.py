#!/usr/bin/env python3
"""Attribute every validator error of the band22 export to the foundation hub.

The offline validator injects ``valley4_protocol_core``'s foundation buildings
from ``src/adapters/industrial_planner/base_registry.json`` -- a 2026-03-28
snapshot that carries a 9x9 ``item_port_sp_hub_1`` at (0,0).  The newer vendored
upstream snapshot (``third_party_snapshots/industrial_planner/base-definition.master.ts``,
commit dd334ed5) builds the same base from ``createValley4ProtocolCoreBuiltinEntities()``,
which contains only the bus source and 18 bus segments -- all at negative
coordinates, none inside the 70x70 placeable area, and no hub at all.

This script re-runs the *unmodified* repository validator against the delivered
blueprint twice: once with the shipped registry, once with a scratch copy whose
only edit is dropping that single hub entry (making the base's foundation match
the newer upstream snapshot).  The delta is the machine-checked attribution.

Read-only with respect to the repository: the patched registry is written into
the caller's artifact directory, never into ``src/``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.adapters.industrial_planner.blueprint_validator import (  # noqa: E402
    validate_industrial_planner_blueprint,
)

REGISTRY_DIR = REPO_ROOT / "src/adapters/industrial_planner"
REGISTRY_FILENAMES = ("device_type_registry.json", "base_registry.json", "item_registry.json")
BASE_ID = "valley4_protocol_core"
HUB_TYPE_ID = "item_port_sp_hub_1"

ERROR_BUCKETS = (
    "schema_errors",
    "registry_errors",
    "lot_boundary_errors",
    "placement_constraint_errors",
    "unsupported_rule_errors",
    "overlap_errors",
    "port_mismatch_errors",
)


def summarize(report: Any) -> dict[str, Any]:
    payload = report.to_dict()
    buckets = {name: list(payload[name]) for name in ERROR_BUCKETS if payload[name]}
    return {
        "total_errors": sum(len(values) for values in buckets.values()),
        "errors_by_bucket": {name: len(values) for name, values in buckets.items()},
        "is_import_compatible": payload["is_import_compatible"],
        "is_layout_healthy": payload["is_layout_healthy"],
        "is_clean": payload["is_clean"],
        "foundation_device_count": payload["foundation_device_count"],
        "device_count": payload["device_count"],
        "cell_coverage": payload["cell_coverage"],
        "lot_utilization_percent": payload["lot_utilization_percent"],
        "port_warning_count": len(payload["port_warnings"]),
        "full_errors": buckets,
    }


def build_upstream_aligned_registry(scratch_dir: Path) -> int:
    scratch_dir.mkdir(parents=True, exist_ok=True)
    for filename in REGISTRY_FILENAMES:
        shutil.copyfile(REGISTRY_DIR / filename, scratch_dir / filename)

    base_path = scratch_dir / "base_registry.json"
    payload = json.loads(base_path.read_text(encoding="utf-8"))
    removed = 0
    for base in payload["bases"]:
        if str(base.get("id")) != BASE_ID:
            continue
        kept = [
            entry
            for entry in base.get("foundationBuildings", [])
            if str(entry.get("typeId")) != HUB_TYPE_ID
        ]
        removed = len(base.get("foundationBuildings", [])) - len(kept)
        base["foundationBuildings"] = kept
    if removed != 1:
        raise RuntimeError(f"expected to drop exactly one {HUB_TYPE_ID} entry, dropped {removed}")
    base_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    blueprint = json.loads(args.blueprint.read_text(encoding="utf-8"))

    shipped = summarize(validate_industrial_planner_blueprint(blueprint))

    scratch_dir = out_dir / "registry_without_hub"
    removed = build_upstream_aligned_registry(scratch_dir)
    upstream_aligned = summarize(
        validate_industrial_planner_blueprint(blueprint, registry_dir=scratch_dir)
    )

    verdict = {
        "blueprint": str(args.blueprint),
        "hub_entries_removed": removed,
        "as_shipped_registry_2026_03_28": {
            key: value for key, value in shipped.items() if key != "full_errors"
        },
        "upstream_aligned_registry_dd334ed5": {
            key: value for key, value in upstream_aligned.items() if key != "full_errors"
        },
        "all_errors_attributable_to_hub": upstream_aligned["total_errors"] == 0,
        "errors_removed_by_dropping_hub": shipped["total_errors"] - upstream_aligned["total_errors"],
    }
    (out_dir / "hub_attribution_verdict.json").write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "hub_attribution_errors_as_shipped.json").write_text(
        json.dumps(shipped["full_errors"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
