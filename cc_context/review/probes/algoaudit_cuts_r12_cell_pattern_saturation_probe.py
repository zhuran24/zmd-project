from __future__ import annotations

from pathlib import Path
import hashlib
import os
import time

os.environ.setdefault("EXACT_USE_POSE_BOOL_MASTER", "1")

from src.models.binding_subproblem import load_wireless_sink_generic_input_slots
from src.models.master_model import (
    MasterPlacementModel,
    infer_exact_required_pose_optional_counts,
    load_generic_io_requirements_artifact,
    load_project_data,
)
from src.models.pose_bool_exact_master import _DIR_DELTA


def _pose_cells(pose, key):
    return [(int(c[0]), int(c[1])) for c in pose.get(key, []) or []]


def main() -> None:
    root = Path(".")
    candidate_path = root / "data" / "preprocessed" / "candidate_placements.json"
    blob = candidate_path.read_bytes()
    print("candidate_sha256", hashlib.sha256(blob).hexdigest(), flush=True)
    print("candidate_bytes", len(blob), flush=True)

    instances, pools, rules = load_project_data(root, solve_mode="certified_exact")
    generic_io = load_generic_io_requirements_artifact(root)
    wireless_slots = (
        load_wireless_sink_generic_input_slots(project_root=root)
        if generic_io.get("required_generic_inputs", {})
        else 0
    )
    counts = infer_exact_required_pose_optional_counts(
        rules,
        generic_io,
        wireless_sink_generic_input_slots=wireless_slots,
    )
    print("mandatory_instances", len(instances), flush=True)
    print("required_optional_counts", counts, flush=True)
    print("wireless_sink_generic_input_slots", wireless_slots, flush=True)

    start = time.perf_counter()
    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        ghost_rect=(27, 15),
        solve_mode="certified_exact",
        generic_io_requirements=generic_io,
        wireless_sink_generic_input_slots=wireless_slots,
        exact_required_pose_optional_counts=counts,
    )
    print("constructor_seconds", round(time.perf_counter() - start, 3), flush=True)
    delegate = model._coordinate_delegate
    assert delegate is not None and type(delegate).__name__ == "PoseBoolExactMasterDelegate"

    capacity = delegate._mandatory_generic_output_capacity_total()
    required = delegate._required_generic_output_slot_total()
    saturated = delegate._generic_output_slots_are_globally_saturated()
    print("generic_output_capacity", capacity, flush=True)
    print("generic_output_required", required, flush=True)
    print("generic_output_saturated", saturated, flush=True)

    forbidden = delegate._forbidden_cells()
    feasible_pose_count = 0
    exact_side_pose_count = 0
    cell_pattern_front_pairs_checked = 0
    cell_pattern_out_of_grid_fronts = 0
    cell_pattern_self_overlap_count = 0
    cell_pattern_intra_port_duplicate_keys = 0
    candidate_pose_duplicate_occupied_cells = 0

    # Raw-data equivalent of the cell-pattern exactness hazards.  The real cache
    # maps each pose BoolVar into a port index iff its mandatory side is proven
    # necessarily routing-visible.  A duplicate literal or self-overlap can only
    # arise from duplicated occupied cells/ports inside one pose, or from that
    # same pose occupying its own terminal front cell.
    for group in model._mandatory_groups:
        gid = str(group["group_id"])
        tpl = str(group["facility_type"])
        op = str(group.get("operation_type", ""))
        delegate._mandatory_operation_by_group[gid] = op
        pool = model.facility_pools.get(tpl, [])
        for _pose_idx, cells in delegate._feasible_poses(tpl, forbidden):
            feasible_pose_count += 1
        for pose in pool:
            occupied = _pose_cells(pose, "occupied_cells")
            if len(occupied) != len(set(occupied)):
                candidate_pose_duplicate_occupied_cells += 1
            occupied_set = set(occupied)
            if not occupied_set:
                continue
            if any(not (0 <= x < delegate.grid_w and 0 <= y < delegate.grid_h) for x, y in occupied_set):
                continue
            if any(cell in forbidden for cell in occupied_set):
                continue
            for side_key in ("input_port_cells", "output_port_cells"):
                ports = list(pose.get(side_key, []) or [])
                if not delegate._mandatory_port_side_is_cell_pattern_exact(gid, side_key, len(ports)):
                    continue
                exact_side_pose_count += 1
                port_keys = [
                    (int(p.get("x", 0)), int(p.get("y", 0)), str(p.get("dir", "")))
                    for p in ports
                ]
                if len(port_keys) != len(set(port_keys)):
                    cell_pattern_intra_port_duplicate_keys += 1
                for x, y, direction in port_keys:
                    dx, dy = _DIR_DELTA.get(str(direction), (None, None))
                    if dx is None:
                        continue
                    front = (int(x) + int(dx), int(y) + int(dy))
                    if not (0 <= front[0] < delegate.grid_w and 0 <= front[1] < delegate.grid_h):
                        cell_pattern_out_of_grid_fronts += 1
                        continue
                    cell_pattern_front_pairs_checked += 1
                    if front in occupied_set:
                        cell_pattern_self_overlap_count += 1

    for tpl, pool in model.facility_pools.items():
        for pose in pool:
            occupied = _pose_cells(pose, "occupied_cells")
            if len(occupied) != len(set(occupied)):
                candidate_pose_duplicate_occupied_cells += 1

    print("mandatory_feasible_pose_count", feasible_pose_count, flush=True)
    print("cell_pattern_exact_side_pose_count", exact_side_pose_count, flush=True)
    print("cell_pattern_front_pairs_checked", cell_pattern_front_pairs_checked, flush=True)
    print("cell_pattern_out_of_grid_fronts", cell_pattern_out_of_grid_fronts, flush=True)
    print("cell_pattern_self_overlap_count", cell_pattern_self_overlap_count, flush=True)
    print("cell_pattern_intra_port_duplicate_keys", cell_pattern_intra_port_duplicate_keys, flush=True)
    print("candidate_pose_duplicate_occupied_cells", candidate_pose_duplicate_occupied_cells, flush=True)

    assert required == capacity == 52, (required, capacity)
    assert saturated is True
    assert candidate_pose_duplicate_occupied_cells == 0
    assert cell_pattern_self_overlap_count == 0
    assert cell_pattern_intra_port_duplicate_keys == 0
    print("probe_ok", flush=True)


if __name__ == "__main__":
    main()
