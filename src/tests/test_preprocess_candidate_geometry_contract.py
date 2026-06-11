from src.placement.placement_generator import (
    GRID_H,
    GRID_W,
    generate_all_pools,
    get_port_front_cell,
    load_templates,
)


def _in_grid(x: int, y: int) -> bool:
    return 0 <= x < GRID_W and 0 <= y < GRID_H


def test_protocol_storage_box_omni_wireless_has_no_physical_ports_and_full_anchor_domain():
    pools = generate_all_pools(load_templates())
    poses = pools["protocol_storage_box"]

    assert len(poses) == (GRID_W - 3 + 1) * (GRID_H - 3 + 1)
    assert {pose["pose_params"]["port_mode"] for pose in poses} == {"omni"}
    assert {pose["pose_params"]["orientation"] for pose in poses} == {0}
    assert {(pose["anchor"]["x"], pose["anchor"]["y"]) for pose in poses} == {
        (x, y)
        for x in range(GRID_W - 3 + 1)
        for y in range(GRID_H - 3 + 1)
    }

    for pose in poses:
        assert pose["input_port_cells"] == []
        assert pose["output_port_cells"] == []
        assert len(pose["occupied_cells"]) == 9
        assert len({tuple(cell) for cell in pose["occupied_cells"]}) == 9


def test_all_generated_physical_port_fronts_are_routable_grid_cells():
    pools = generate_all_pools(load_templates())

    failures = []
    for template_id, poses in pools.items():
        for pose in poses:
            for side_key in ("input_port_cells", "output_port_cells"):
                for port in pose.get(side_key, []) or []:
                    fx, fy = get_port_front_cell(port)
                    if not _in_grid(fx, fy):
                        failures.append((template_id, pose["pose_id"], side_key, port, (fx, fy)))

    assert failures == []


def test_physical_ports_are_outward_adjacent_to_their_body_bbox():
    pools = generate_all_pools(load_templates())

    failures = []
    for template_id, poses in pools.items():
        for pose in poses:
            occupied = [tuple(cell) for cell in pose["occupied_cells"]]
            xs = [cell[0] for cell in occupied]
            ys = [cell[1] for cell in occupied]
            x0, x1 = min(xs), max(xs)
            y0, y1 = min(ys), max(ys)
            for side_key in ("input_port_cells", "output_port_cells"):
                for port in pose.get(side_key, []) or []:
                    px, py, direction = int(port["x"]), int(port["y"]), str(port["dir"])
                    ok = (
                        direction == "N" and py == y1 + 1 and x0 <= px <= x1
                    ) or (
                        direction == "S" and py == y0 - 1 and x0 <= px <= x1
                    ) or (
                        direction == "W" and px == x0 - 1 and y0 <= py <= y1
                    ) or (
                        direction == "E" and px == x1 + 1 and y0 <= py <= y1
                    )
                    if not ok:
                        failures.append((template_id, pose["pose_id"], side_key, port, (x0, y0, x1, y1)))

    assert failures == []


def test_template_pool_counts_match_front_safe_closed_forms():
    pools = generate_all_pools(load_templates())
    counts = {template_id: len(poses) for template_id, poses in pools.items()}

    # For physical-port templates, active edge fronts need a one-cell in-grid
    # routing moat beyond the outside-adjacent port coordinate.
    assert counts == {
        "manufacturing_3x3": 4 * 68 * 64,
        "manufacturing_5x5": 4 * 66 * 62,
        "manufacturing_6x4": 4 * 65 * 63,
        "protocol_core": 2 * 58 * 58,
        "protocol_storage_box": 68 * 68,
        "power_pole": 69 * 69,
        "boundary_storage_port": 2 * 67,
    }
