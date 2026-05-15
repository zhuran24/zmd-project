"""Convert IP v2 blueprint -> master.solve() solution_hint Dict[instance_id, pose_idx].

Reads a community/user-tuned IP v2 blueprint JSON (devices + origin + rotation)
and produces a JSON file usable as `initial_solution_hint` for master_model.solve().

Mapping rules (verified 2026-05-16 from candidate_placements + IP v2 source):

  typeId -> facility_type (by footprint size):
    item_port_unloader_1   (3x1) -> boundary_storage_port
    item_port_grinder_1    (3x3) -> manufacturing_3x3
    item_port_furnance_1   (3x3) -> manufacturing_3x3
    item_port_cmpt_mc_1    (3x3) -> manufacturing_3x3
    item_port_shaper_1     (3x3) -> manufacturing_3x3
    item_port_seedcol_1    (5x5) -> manufacturing_5x5
    item_port_planter_1    (5x5) -> manufacturing_5x5
    item_port_thickener_1  (6x4) -> manufacturing_6x4
    item_port_filling_pd_mc_1   (6x4) -> manufacturing_6x4
    item_port_tools_asm_mc_1    (6x4) -> manufacturing_6x4
    item_port_sp_hub_1     (9x9) -> protocol_core
    item_port_storager_1   (3x3) -> protocol_storage_box   (optional, skipped)
    item_port_power_sta_1  (2x2) -> power_pole             (optional, skipped)
    item_port_power_diffuser_1 (2x2) -> power_pole         (optional, skipped)

  rotation (degrees) -> (orientation, port_mode):
    Square manufacturing (3x3, 5x5):
      0   -> (0, 'TB')   # output top,    input bottom
      90  -> (0, 'LR')   # output right,  input left
      180 -> (0, 'BT')   # output bottom, input top
      270 -> (0, 'RL')   # output left,   input right
    Rectangular manufacturing (6x4):
      0   -> (0, 'TB')
      90  -> (1, 'LR')
      180 -> (0, 'BT')
      270 -> (1, 'RL')
    Boundary storage port (3x1):
      90  -> (0, 'left_base')
      180 -> (1, 'bottom_base')
    Protocol core (9x9):
      0   -> (0, 'core_LR_out')   # only rotation 0 observed in blueprint
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

TYPE_ID_TO_FACILITY: Dict[str, str] = {
    "item_port_unloader_1": "boundary_storage_port",
    "item_port_grinder_1": "manufacturing_3x3",
    "item_port_furnance_1": "manufacturing_3x3",
    "item_port_cmpt_mc_1": "manufacturing_3x3",
    "item_port_shaper_1": "manufacturing_3x3",
    "item_port_seedcol_1": "manufacturing_5x5",
    "item_port_planter_1": "manufacturing_5x5",
    "item_port_thickener_1": "manufacturing_6x4",
    "item_port_filling_pd_mc_1": "manufacturing_6x4",
    "item_port_tools_asm_mc_1": "manufacturing_6x4",
    "item_port_sp_hub_1": "protocol_core",
}

SQUARE_MANUF_TYPES = {"manufacturing_3x3", "manufacturing_5x5"}
RECT_MANUF_TYPES = {"manufacturing_6x4"}

SQUARE_MANUF_ROT: Dict[int, Tuple[int, str]] = {
    0: (0, "TB"),
    90: (0, "LR"),
    180: (0, "BT"),
    270: (0, "RL"),
}
RECT_MANUF_ROT: Dict[int, Tuple[int, str]] = {
    0: (0, "TB"),
    90: (1, "LR"),
    180: (0, "BT"),
    270: (1, "RL"),
}
BOUNDARY_ROT: Dict[int, Tuple[int, str]] = {
    90: (0, "left_base"),
    180: (1, "bottom_base"),
}


def rotation_to_orient_mode(facility_type: str, rotation: int) -> Optional[Tuple[int, str]]:
    if facility_type in SQUARE_MANUF_TYPES:
        return SQUARE_MANUF_ROT.get(rotation)
    if facility_type in RECT_MANUF_TYPES:
        return RECT_MANUF_ROT.get(rotation)
    if facility_type == "boundary_storage_port":
        return BOUNDARY_ROT.get(rotation)
    if facility_type == "protocol_core":
        return (0, "core_LR_out") if rotation == 0 else None
    return None


def build_pose_lookup(
    candidate_placements: Dict[str, List[dict]],
) -> Dict[str, Dict[Tuple[int, int, int, str], int]]:
    """For each facility_type, map (anchor_x, anchor_y, orientation, port_mode) -> pose_idx."""
    lookup: Dict[str, Dict[Tuple[int, int, int, str], int]] = {}
    for facility_type, poses in candidate_placements.items():
        idx_map: Dict[Tuple[int, int, int, str], int] = {}
        for idx, pose in enumerate(poses):
            anchor = pose["anchor"]
            params = pose["pose_params"]
            key = (
                int(anchor["x"]),
                int(anchor["y"]),
                int(params.get("orientation", 0)),
                str(params.get("port_mode", "")),
            )
            idx_map[key] = idx
        lookup[facility_type] = idx_map
    return lookup


def convert(
    blueprint_path: Path,
    candidate_placements_path: Path,
    mandatory_instances_path: Path,
    out_path: Optional[Path] = None,
    verbose: bool = True,
) -> Dict[str, int]:
    blueprint = json.loads(blueprint_path.read_text())
    with candidate_placements_path.open() as f:
        cp = json.load(f)
    pose_lookup = build_pose_lookup(cp["facility_pools"])
    mandatory = json.loads(mandatory_instances_path.read_text())

    instances_by_type: Dict[str, List[str]] = defaultdict(list)
    for inst in mandatory:
        instances_by_type[inst["facility_type"]].append(inst["instance_id"])

    hint_pose_indices_by_type: Dict[str, List[int]] = defaultdict(list)
    counters = {
        "device_total": 0,
        "device_kept": 0,
        "device_skipped_typeid": 0,
        "device_skipped_rotation": 0,
        "device_skipped_lookup_miss": 0,
    }

    for device in blueprint.get("devices", []):
        type_id = device.get("typeId", "")
        if not type_id.startswith("item_port_"):
            continue
        if type_id not in TYPE_ID_TO_FACILITY:
            counters["device_skipped_typeid"] += 1
            continue
        facility_type = TYPE_ID_TO_FACILITY[type_id]
        counters["device_total"] += 1
        rotation = int(device.get("rotation", 0))
        om = rotation_to_orient_mode(facility_type, rotation)
        if om is None:
            counters["device_skipped_rotation"] += 1
            if verbose:
                print(
                    f"[skip] no rotation map: typeId={type_id} rotation={rotation}",
                    file=sys.stderr,
                )
            continue
        orient, port_mode = om
        origin = device["origin"]
        key = (int(origin["x"]), int(origin["y"]), int(orient), port_mode)
        idx = pose_lookup.get(facility_type, {}).get(key)
        if idx is None:
            counters["device_skipped_lookup_miss"] += 1
            if verbose:
                print(
                    f"[skip] no pose match: facility={facility_type} "
                    f"anchor={origin} orient={orient} port_mode={port_mode}",
                    file=sys.stderr,
                )
            continue
        hint_pose_indices_by_type[facility_type].append(idx)
        counters["device_kept"] += 1

    solution_hint: Dict[str, int] = {}
    coverage_per_type: Dict[str, Tuple[int, int]] = {}
    for facility_type, pose_indices in hint_pose_indices_by_type.items():
        instance_ids = instances_by_type.get(facility_type, [])
        zipped = list(zip(instance_ids, pose_indices))
        for inst_id, pose_idx in zipped:
            solution_hint[inst_id] = int(pose_idx)
        coverage_per_type[facility_type] = (len(zipped), len(instance_ids))

    if verbose:
        print(f"[summary] devices: {counters}", file=sys.stderr)
        for ft, (hinted, total) in sorted(coverage_per_type.items()):
            print(
                f"[summary] {ft}: hinted {hinted}/{total} mandatory instances",
                file=sys.stderr,
            )
        print(f"[summary] total hint entries: {len(solution_hint)}", file=sys.stderr)

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(solution_hint, indent=2, sort_keys=True))
        if verbose:
            print(f"[wrote] {out_path}", file=sys.stderr)

    return solution_hint


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--blueprint",
        type=Path,
        default=Path("/home/zhuran24/下载/BP-2026-05-13 08_35_36.blueprint(1).json"),
        help="IP v2 blueprint JSON file",
    )
    ap.add_argument(
        "--candidate-placements",
        type=Path,
        default=PROJECT_ROOT / "data" / "preprocessed" / "candidate_placements.json",
    )
    ap.add_argument(
        "--mandatory-instances",
        type=Path,
        default=PROJECT_ROOT / "data" / "preprocessed" / "mandatory_exact_instances.json",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "data" / "hints" / "blueprint_2026_05_13_master_hint.json",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    convert(
        blueprint_path=args.blueprint,
        candidate_placements_path=args.candidate_placements,
        mandatory_instances_path=args.mandatory_instances,
        out_path=args.out,
        verbose=not args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
