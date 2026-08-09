import copy

import pytest

from src.placement.placement_generator import (
    GRID_H,
    GRID_W,
    generate_all_pools,
    get_port_front_cell,
    load_templates,
)


def _in_grid(x: int, y: int) -> bool:
    return 0 <= x < GRID_W and 0 <= y < GRID_H


def _single_mutated_template(template_id: str, mutator):
    templates = load_templates()
    mutated_template = copy.deepcopy(templates[template_id])
    mutator(mutated_template)
    return {template_id: mutated_template}


def test_generate_all_pools_rejects_schema_valid_template_geometry_drift():
    cases = [
        (
            "protocol_core",
            lambda tpl: tpl["dimensions"].__setitem__("w", 10),
            r"protocol_core.*9x9",
        ),
        (
            "protocol_storage_box",
            lambda tpl: tpl["dimensions"].__setitem__("w", 4),
            r"protocol_storage_box.*w == h",
        ),
        (
            "power_pole",
            lambda tpl: tpl["dimensions"].__setitem__("w", 3),
            r"power_pole.*2x2",
        ),
        (
            "power_pole",
            lambda tpl: tpl.__setitem__("power_coverage_radius", 99),
            r"power_coverage_radius.*radius-5",
        ),
        (
            "boundary_storage_port",
            lambda tpl: tpl["dimensions"].__setitem__("w", 2),
            r"boundary_storage_port.*1x3",
        ),
        (
            "manufacturing_6x4",
            lambda tpl: tpl.__setitem__("dimensions", {"w": 4, "h": 6}),
            r"long_sides.*w > h",
        ),
        (
            "manufacturing_6x4",
            lambda tpl: tpl.__setitem__("rotatable", False),
            r"manufacturing_6x4\.rotatable.*rotatable=True",
        ),
        (
            "protocol_core",
            lambda tpl: tpl.__setitem__("rotatable", False),
            r"protocol_core\.rotatable.*rotatable=True",
        ),
        (
            "boundary_storage_port",
            lambda tpl: tpl.__setitem__("rotatable", False),
            r"boundary_storage_port\.rotatable.*rotatable=True",
        ),
        (
            "manufacturing_3x3",
            lambda tpl: tpl.__setitem__("is_solid_z", False),
            r"manufacturing_3x3\.is_solid_z.*occupied_cells",
        ),
    ]

    for template_id, mutator, expected_message in cases:
        with pytest.raises(ValueError, match=expected_message):
            generate_all_pools(_single_mutated_template(template_id, mutator))


def test_protocol_storage_box_has_complete_physical_port_geometry():
    pools = generate_all_pools(load_templates())
    poses = pools["protocol_storage_box"]

    assert len(poses) == 18_496
    assert {pose["pose_params"]["port_mode"] for pose in poses} == {
        "TB",
        "BT",
        "RL",
        "LR",
    }
    assert {pose["pose_params"]["orientation"] for pose in poses} == {0}

    for pose in poses:
        assert len(pose["input_port_cells"]) == 3
        assert len(pose["output_port_cells"]) == 3
        assert len(pose["occupied_cells"]) == 9
        assert len({tuple(cell) for cell in pose["occupied_cells"]}) == 9


def test_generated_bodies_stay_in_grid_and_physical_access_cells_are_at_most_one_step_oog():
    pools = generate_all_pools(load_templates())

    failures = []
    templates_with_oog_access_cells = set()
    for template_id, poses in pools.items():
        for pose in poses:
            for x, y in pose["occupied_cells"]:
                if not _in_grid(int(x), int(y)):
                    failures.append((template_id, pose["pose_id"], "occupied_cells", (x, y)))
            for side_key in ("input_port_cells", "output_port_cells"):
                for port in pose.get(side_key, []) or []:
                    fx, fy = get_port_front_cell(port)
                    if not (-1 <= fx <= GRID_W and -1 <= fy <= GRID_H):
                        failures.append((template_id, pose["pose_id"], side_key, port, (fx, fy)))
                    elif not _in_grid(fx, fy):
                        templates_with_oog_access_cells.add(template_id)

    assert failures == []
    assert templates_with_oog_access_cells == {
        "protocol_core",
        "protocol_storage_box",
    }


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


def test_edge_poses_retain_physical_ports_that_may_be_inactive():
    pools = generate_all_pools(load_templates())

    core_pose = next(
        pose
        for pose in pools["protocol_core"]
        if pose["anchor"] == {"x": 1, "y": 0}
        and pose["pose_params"]["orientation"] == 0
    )
    assert [port for port in core_pose["input_port_cells"] if port["dir"] == "S"] == [
        {"x": x, "y": -1, "dir": "S"}
        for x in range(2, 9)
    ]
    assert all(
        _in_grid(*get_port_front_cell(port))
        for port in core_pose["input_port_cells"]
        if port["dir"] == "N"
    )

    box_pose = next(
        pose
        for pose in pools["protocol_storage_box"]
        if pose["anchor"] == {"x": 10, "y": 0}
        and pose["pose_params"]["port_mode"] == "TB"
    )
    assert box_pose["input_port_cells"] == [
        {"x": x, "y": 3, "dir": "N"}
        for x in range(10, 13)
    ]
    assert box_pose["output_port_cells"] == [
        {"x": x, "y": -1, "dir": "S"}
        for x in range(10, 13)
    ]


def test_template_pool_counts_match_activation_aware_closed_forms():
    pools = generate_all_pools(load_templates())
    counts = {template_id: len(poses) for template_id, poses in pools.items()}

    # Manufacturing modes require both physical sides; generic core/box ports
    # may be unused, so only those templates retain body-in-grid edge poses.
    assert counts == {
        "manufacturing_3x3": 17_952,
        "manufacturing_5x5": 16_896,
        "manufacturing_6x4": 16_900,
        "protocol_core": 7_688,
        "protocol_storage_box": 18_496,
        "power_pole": 4_761,
        "boundary_storage_port": 136,
    }
