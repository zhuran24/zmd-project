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


def test_protocol_storage_box_has_front_safe_physical_ports():
    pools = generate_all_pools(load_templates())
    poses = pools["protocol_storage_box"]

    assert len(poses) == 17_952
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
        "manufacturing_3x3": 17_952,
        "manufacturing_5x5": 16_896,
        "manufacturing_6x4": 16_900,
        "protocol_core": 7_200,
        "protocol_storage_box": 17_952,
        "power_pole": 4_761,
        "boundary_storage_port": 136,
    }
