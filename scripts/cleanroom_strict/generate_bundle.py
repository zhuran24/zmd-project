#!/usr/bin/env python3
"""Build the neutral clean-room benchmark bundle deterministically.

The external bundle is deliberately assembled from constants in this standalone
script.  It does not import project code or read generated placement domains.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external"

DIRECTIONS = ("N", "E", "S", "W")
DELTA = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}

# Token-aware: ordinary words containing these byte sequences are not rejected.
PROHIBITED_EXTERNAL_TOKENS = (
    "lbbd",
    "benders",
    "master",
    "cut",
    "ghost",
    "front",
    "lift",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "v2.2",
    "candidate_placements",
    "exactsearchsession",
    "pose_id",
    "codegraph",
    "facility_pools",
    "placement_generator",
    "routing_subproblem",
    "binding_subproblem",
    "project_lock",
)


OPERATION_ROWS: tuple[tuple[str, str, int, dict[str, int], dict[str, int]], ...] = (
    ("crusher_blue_iron", "manufacturing_3x3", 34, {"blue_iron_block": 1}, {"blue_iron_powder": 1}),
    ("crusher_buckwheat", "manufacturing_3x3", 6, {"buckwheat": 1}, {"buckwheat_powder": 2}),
    ("crusher_sandleaf", "manufacturing_3x3", 11, {"sandleaf": 1}, {"sandleaf_powder": 3}),
    ("crusher_source", "manufacturing_3x3", 18, {"source_ore": 1}, {"source_powder": 1}),
    (
        "filling_capsule",
        "manufacturing_6x4",
        3,
        {"fine_buckwheat_powder": 2, "steel_bottle": 2},
        {"qiaoyu_capsule": 1},
    ),
    (
        "grinder_dense_blue_iron",
        "manufacturing_6x4",
        17,
        {"blue_iron_powder": 2, "sandleaf_powder": 1},
        {"dense_blue_iron_powder": 1},
    ),
    (
        "grinder_dense_source",
        "manufacturing_6x4",
        9,
        {"sandleaf_powder": 1, "source_powder": 2},
        {"dense_source_powder": 1},
    ),
    (
        "grinder_fine_buckwheat",
        "manufacturing_6x4",
        6,
        {"buckwheat_powder": 2, "sandleaf_powder": 1},
        {"fine_buckwheat_powder": 1},
    ),
    ("molding_bottle", "manufacturing_3x3", 6, {"steel_block": 2}, {"steel_bottle": 1}),
    (
        "packaging_battery",
        "manufacturing_6x4",
        3,
        {"dense_source_powder": 3, "steel_part": 2},
        {"valley_battery": 1},
    ),
    ("parts_maker", "manufacturing_3x3", 6, {"steel_block": 1}, {"steel_part": 1}),
    ("planter_buckwheat", "manufacturing_5x5", 11, {"buckwheat_seed": 1}, {"buckwheat": 1}),
    ("planter_sandleaf", "manufacturing_5x5", 21, {"sandleaf_seed": 1}, {"sandleaf": 1}),
    ("refinery_blue_iron", "manufacturing_3x3", 34, {"blue_iron_ore": 1}, {"blue_iron_block": 1}),
    ("refinery_steel", "manufacturing_3x3", 17, {"dense_blue_iron_powder": 1}, {"steel_block": 1}),
    ("seed_collector_buckwheat", "manufacturing_5x5", 6, {"buckwheat": 1}, {"buckwheat_seed": 2}),
    ("seed_collector_sandleaf", "manufacturing_5x5", 11, {"sandleaf": 1}, {"sandleaf_seed": 2}),
)


def _port(port_id: str, kind: str, x: int, y: int, direction: str) -> dict[str, Any]:
    return {"id": port_id, "kind": kind, "body_cell": {"x": x, "y": y}, "direction": direction}


def _side_ports(kind: str, side: str, width: int, height: int, indices: list[int] | None = None) -> list[dict[str, Any]]:
    if side in ("N", "S"):
        values = list(range(width)) if indices is None else indices
        y = height - 1 if side == "N" else 0
        return [_port(f"{kind}_{side}_{i}", kind, i, y, side) for i in values]
    values = list(range(height)) if indices is None else indices
    x = width - 1 if side == "E" else 0
    return [_port(f"{kind}_{side}_{i}", kind, x, i, side) for i in values]


def _mode(mode_id: str, width: int, height: int, input_side: str, output_side: str) -> dict[str, Any]:
    return {
        "id": mode_id,
        "body": {"width": width, "height": height},
        "ports": _side_ports("input", input_side, width, height)
        + _side_ports("output", output_side, width, height),
    }


def _square_template(size: int, *, requires_power: bool) -> dict[str, Any]:
    return {
        "requires_power": requires_power,
        "placement_rule": "any_body_in_grid",
        "modes": [
            _mode("north_to_south", size, size, "N", "S"),
            _mode("south_to_north", size, size, "S", "N"),
            _mode("east_to_west", size, size, "E", "W"),
            _mode("west_to_east", size, size, "W", "E"),
        ],
    }


def _templates() -> dict[str, Any]:
    core_a = {
        "id": "inputs_north_south",
        "body": {"width": 9, "height": 9},
        "ports": (
            _side_ports("input", "N", 9, 9, list(range(1, 8)))
            + _side_ports("input", "S", 9, 9, list(range(1, 8)))
            + _side_ports("output", "E", 9, 9, [1, 4, 7])
            + _side_ports("output", "W", 9, 9, [1, 4, 7])
        ),
    }
    core_b = {
        "id": "inputs_east_west",
        "body": {"width": 9, "height": 9},
        "ports": (
            _side_ports("input", "E", 9, 9, list(range(1, 8)))
            + _side_ports("input", "W", 9, 9, list(range(1, 8)))
            + _side_ports("output", "N", 9, 9, [1, 4, 7])
            + _side_ports("output", "S", 9, 9, [1, 4, 7])
        ),
    }
    return {
        "manufacturing_3x3": _square_template(3, requires_power=True),
        "manufacturing_5x5": _square_template(5, requires_power=True),
        "manufacturing_6x4": {
            "requires_power": True,
            "placement_rule": "any_body_in_grid",
            "modes": [
                _mode("north_to_south", 6, 4, "N", "S"),
                _mode("south_to_north", 6, 4, "S", "N"),
                _mode("east_to_west", 4, 6, "E", "W"),
                _mode("west_to_east", 4, 6, "W", "E"),
            ],
        },
        "protocol_core": {
            "requires_power": False,
            "placement_rule": "any_body_in_grid",
            "modes": [core_a, core_b],
        },
        "boundary_storage_port": {
            "requires_power": False,
            "placement_rule": "matching_map_boundary",
            "modes": [
                {
                    "id": "left_boundary",
                    "body": {"width": 1, "height": 3},
                    "ports": [_port("output_E_1", "output", 0, 1, "E")],
                },
                {
                    "id": "bottom_boundary",
                    "body": {"width": 3, "height": 1},
                    "ports": [_port("output_N_1", "output", 1, 0, "N")],
                },
            ],
        },
        "power_pole": {
            "requires_power": False,
            "placement_rule": "any_body_in_grid",
            "modes": [{"id": "fixed", "body": {"width": 2, "height": 2}, "ports": []}],
        },
        "storage_box": _square_template(3, requires_power=True),
    }


def build_instance() -> dict[str, Any]:
    operation_groups = []
    required_instances = []
    for operation_id, template_id, count, inputs, outputs in OPERATION_ROWS:
        ids = [f"{operation_id}_{index:03d}" for index in range(1, count + 1)]
        operation_groups.append(
            {
                "id": operation_id,
                "template": template_id,
                "count": count,
                "port_needs": {"inputs": inputs, "outputs": outputs},
                "instance_ids": ids,
            }
        )
        required_instances.extend(
            {"id": instance_id, "template": template_id, "operation": operation_id}
            for instance_id in ids
        )

    required_instances.append({"id": "protocol_core_001", "template": "protocol_core", "operation": "generic_io"})
    required_instances.extend(
        {
            "id": f"boundary_port_{index:03d}",
            "template": "boundary_storage_port",
            "operation": "generic_io",
        }
        for index in range(1, 47)
    )

    commodities = sorted(
        {
            commodity
            for _, _, _, inputs, outputs in OPERATION_ROWS
            for commodity in (*inputs.keys(), *outputs.keys())
        }
    )
    return {
        "schema_version": 1,
        "benchmark_id": "factory_layout_optimality_benchmark_v1",
        "coordinate_system": {
            "origin": "southwest",
            "indexing": "zero_based",
            "x_positive": "east",
            "y_positive": "north",
            "directions": list(DIRECTIONS),
        },
        "grid": {"width": 70, "height": 70},
        "objective": {"kind": "max_lex_area_min_side", "minimum_side": 6, "body_cells_only": True},
        "commodities": commodities,
        "facility_templates": _templates(),
        "operation_groups": operation_groups,
        "required_instances": required_instances,
        "generic_requirements": {
            "raw_outputs": {"blue_iron_ore": 34, "source_ore": 18},
            "final_inputs": {"qiaoyu_capsule": 1, "valley_battery": 1},
            "raw_output_providers": ["boundary_storage_port", "protocol_core"],
            "final_input_providers": ["protocol_core", "storage_box"],
        },
        "repeatable_auxiliaries": ["power_pole", "storage_box"],
        "routing": {
            "component_kinds": ["straight", "turn", "cross", "splitter", "merger"],
            "component_cells_must_avoid_bodies": True,
            "multi_commodity_sharing": True,
            "terminal_output_requires_component_input": "opposite_terminal_direction",
            "terminal_input_requires_component_output": "opposite_terminal_direction",
            "compatible_terminals_share_component": True,
            "crossing": "two_perpendicular_straight_channels_without_transfer",
            "connectivity": "each_active_output_reaches_an_active_input_and_each_active_input_is_reached_per_commodity",
            "throughput_in_scope": False,
        },
        "power": {
            "pole_template": "power_pole",
            "coverage_from_pole_anchor": {"x_min_offset": -5, "x_max_offset": 6, "y_min_offset": -5, "y_max_offset": 6},
            "required_rule": "at_least_one_body_cell_covered",
        },
        "sentinels": {
            "commodity_count": 19,
            "operation_group_count": 17,
            "manufacturing_instance_count": 219,
            "required_instance_count": 266,
            "required_body_area": 3544,
            "manufacturing_input_terminals": 310,
            "manufacturing_output_terminals": 264,
            "generic_raw_output_terminals": 52,
            "generic_final_input_terminals": 2,
            "total_active_terminals": 628,
        },
    }


PROBLEM_MD = """# Factory Layout Optimality Benchmark

This is a self-contained architecture and proof-design problem. Assume no existing implementation.

## Goal

Place all required facilities on a 70 by 70 cell grid, add any number of allowed auxiliary facilities, and connect every required material terminal. Among the remaining cells, maximize the largest axis-aligned rectangle containing no facility body cells. Compare solutions lexicographically by rectangle area and then shorter side; rectangles with a side below 6 are inadmissible.

The requested result is both a feasible layout and an auditable argument that no better objective value exists. A heuristic layout alone is insufficient.

## Authoritative Data

`problem_instance.json` is the machine-readable authority. Coordinates are zero-based with the origin at the southwest corner. A mode gives body-local port cells and outward directions. The access cell of a port is the adjacent cell in that direction.

All required facility bodies must remain in the grid and bodies may not overlap. A body may touch the map boundary. Only a bound, active port needs its access cell to be in the grid and free of facility bodies; an unbound port may face outside the grid or be blocked.

The instance has 219 manufacturing facilities in 17 operation groups, one protocol core, and 46 boundary storage ports. Power poles and storage boxes are repeatable auxiliaries. The data lists exact per-facility material terminal counts, all 19 commodities, and every required instance identifier.

## Material Terminals

Manufacturing terminals accept only the commodity specified by their operation. Counts are exact. Boundary storage ports and protocol-core outputs jointly provide the exact raw-output requirements. Final products must enter active input terminals on the protocol core or storage boxes. Storage-box outputs must remain inactive in this benchmark.

Every active output must reach an active input of the same commodity, and every active input must be reached by an active output. Separate connected regions for one commodity are allowed. Intermediate products may not use storage as a teleporting transfer.

## Transport Components

Transport occupies grid cells outside facility bodies. A straight has one input and the opposite output; a turn has one input and one perpendicular output. A splitter has one input and two or three distinct other outputs; a merger has two or three distinct inputs and one other output. A crossing is exactly two perpendicular straight channels with no transfer between channels. Directions within a component or channel are unique. One component may carry multiple commodities and connects every direction-compatible adjacent active terminal. Capacity and throughput are outside this benchmark.

For a facility output facing direction `d`, a component in its access cell must include `opposite(d)` among its inputs. For a facility input, that component must include `opposite(d)` among its outputs. Thus two outputs may join through a merger and two inputs may be served through a splitter.

## Power

A pole has a 2 by 2 body. From anchor `(x,y)`, its inclusive coverage is `x-5..x+6` by `y-5..y+6`, clipped to the map. Every facility marked `requires_power` must have at least one body cell in some pole's coverage. Pole bodies also participate in non-overlap and in the empty-rectangle objective.

## Deliverable

Design a system capable of producing and auditing an optimality result on one Linux machine with 24 CPU cores and 48 GB memory. Explain:

1. whether the system is monolithic or decomposed, and why;
2. where each geometry, terminal, routing, power, and objective rule is enforced;
3. what information components exchange, including the form of a rejection explanation;
4. the three most likely failure modes and mitigations;
5. CPU, memory, and wall-clock allocation; and
6. how feasibility and the upper-bound argument are independently checked.

Do not assume a particular solver or proof technology. State every additional assumption.
"""


R1_PROMPT_MD = """# Independent Architecture Derivation: Round 1

Treat the attached benchmark as a new problem. Read `problem.md` and `problem_instance.json`, then propose a proof-producing solution architecture from first principles.

Your response must answer all six deliverable questions. Give concrete mathematical variables or data structures, rejection explanations between components if applicable, and an audit path for both the feasible layout and the claim that no better objective exists. Estimate peak memory and identify which steps can be parallelized on the stated machine.

Do not infer any hidden implementation. If the specification leaves a material ambiguity, list it before choosing an explicit assumption. Distinguish a practical search plan from the evidence needed for a final optimality claim.
"""


def build_schema() -> dict[str, Any]:
    coord = {
        "type": "object",
        "additionalProperties": False,
        "required": ["x", "y"],
        "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
    }
    port = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "kind", "body_cell", "direction"],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "kind": {"enum": ["input", "output"]},
            "body_cell": {"$ref": "#/$defs/coordinate"},
            "direction": {"enum": list(DIRECTIONS)},
        },
    }
    mode = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "body", "ports"],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "body": {
                "type": "object",
                "additionalProperties": False,
                "required": ["width", "height"],
                "properties": {"width": {"type": "integer", "minimum": 1}, "height": {"type": "integer", "minimum": 1}},
            },
            "ports": {"type": "array", "items": port},
        },
    }
    string_array = {"type": "array", "items": {"type": "string", "minLength": 1}, "uniqueItems": True}
    commodity_counts = {
        "type": "object",
        "propertyNames": {"type": "string", "minLength": 1},
        "additionalProperties": {"type": "integer", "minimum": 1},
    }
    operation_group = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "template", "count", "port_needs", "instance_ids"],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "template": {"type": "string", "minLength": 1},
            "count": {"type": "integer", "minimum": 1},
            "port_needs": {
                "type": "object",
                "additionalProperties": False,
                "required": ["inputs", "outputs"],
                "properties": {"inputs": commodity_counts, "outputs": commodity_counts},
            },
            "instance_ids": string_array,
        },
    }
    required_instance = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "template", "operation"],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "template": {"type": "string", "minLength": 1},
            "operation": {"type": "string", "minLength": 1},
        },
    }
    sentinel_names = [
        "commodity_count", "operation_group_count", "manufacturing_instance_count", "required_instance_count",
        "required_body_area", "manufacturing_input_terminals", "manufacturing_output_terminals",
        "generic_raw_output_terminals", "generic_final_input_terminals", "total_active_terminals",
    ]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.invalid/factory-layout-optimality-benchmark-v1.schema.json",
        "title": "Factory Layout Optimality Benchmark Instance",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version", "benchmark_id", "coordinate_system", "grid", "objective", "commodities",
            "facility_templates", "operation_groups", "required_instances", "generic_requirements",
            "repeatable_auxiliaries", "routing", "power", "sentinels",
        ],
        "properties": {
            "schema_version": {"const": 1},
            "benchmark_id": {"const": "factory_layout_optimality_benchmark_v1"},
            "coordinate_system": {
                "type": "object",
                "additionalProperties": False,
                "required": ["origin", "indexing", "x_positive", "y_positive", "directions"],
                "properties": {
                    "origin": {"const": "southwest"},
                    "indexing": {"const": "zero_based"},
                    "x_positive": {"const": "east"},
                    "y_positive": {"const": "north"},
                    "directions": {"const": list(DIRECTIONS)},
                },
            },
            "grid": {
                "type": "object",
                "additionalProperties": False,
                "required": ["width", "height"],
                "properties": {"width": {"const": 70}, "height": {"const": 70}},
            },
            "objective": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "minimum_side", "body_cells_only"],
                "properties": {
                    "kind": {"const": "max_lex_area_min_side"},
                    "minimum_side": {"const": 6},
                    "body_cells_only": {"const": True},
                },
            },
            "commodities": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "facility_templates": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["requires_power", "placement_rule", "modes"],
                    "properties": {
                        "requires_power": {"type": "boolean"},
                        "placement_rule": {"enum": ["any_body_in_grid", "matching_map_boundary"]},
                        "modes": {"type": "array", "minItems": 1, "items": mode},
                    },
                },
            },
            "operation_groups": {"type": "array", "items": operation_group},
            "required_instances": {"type": "array", "items": required_instance},
            "generic_requirements": {
                "type": "object",
                "additionalProperties": False,
                "required": ["raw_outputs", "final_inputs", "raw_output_providers", "final_input_providers"],
                "properties": {
                    "raw_outputs": commodity_counts,
                    "final_inputs": commodity_counts,
                    "raw_output_providers": string_array,
                    "final_input_providers": string_array,
                },
            },
            "repeatable_auxiliaries": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "routing": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "component_kinds", "component_cells_must_avoid_bodies", "multi_commodity_sharing",
                    "terminal_output_requires_component_input", "terminal_input_requires_component_output",
                    "compatible_terminals_share_component", "crossing", "connectivity", "throughput_in_scope",
                ],
                "properties": {
                    "component_kinds": {"const": ["straight", "turn", "cross", "splitter", "merger"]},
                    "component_cells_must_avoid_bodies": {"const": True},
                    "multi_commodity_sharing": {"const": True},
                    "terminal_output_requires_component_input": {"const": "opposite_terminal_direction"},
                    "terminal_input_requires_component_output": {"const": "opposite_terminal_direction"},
                    "compatible_terminals_share_component": {"const": True},
                    "crossing": {"const": "two_perpendicular_straight_channels_without_transfer"},
                    "connectivity": {
                        "const": "each_active_output_reaches_an_active_input_and_each_active_input_is_reached_per_commodity"
                    },
                    "throughput_in_scope": {"const": False},
                },
            },
            "power": {
                "type": "object",
                "additionalProperties": False,
                "required": ["pole_template", "coverage_from_pole_anchor", "required_rule"],
                "properties": {
                    "pole_template": {"const": "power_pole"},
                    "coverage_from_pole_anchor": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["x_min_offset", "x_max_offset", "y_min_offset", "y_max_offset"],
                        "properties": {
                            "x_min_offset": {"const": -5}, "x_max_offset": {"const": 6},
                            "y_min_offset": {"const": -5}, "y_max_offset": {"const": 6},
                        },
                    },
                    "required_rule": {"const": "at_least_one_body_cell_covered"},
                },
            },
            "sentinels": {
                "type": "object",
                "additionalProperties": False,
                "required": sentinel_names,
                "properties": {name: {"type": "integer", "minimum": 0} for name in sentinel_names},
            },
        },
        "$defs": {"coordinate": coord},
    }


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")


def rendered_files() -> dict[str, bytes]:
    files = {
        "R1_prompt.md": R1_PROMPT_MD.encode("utf-8"),
        "problem.md": PROBLEM_MD.encode("utf-8"),
        "problem_instance.json": _json_bytes(build_instance()),
        "problem_instance.schema.json": _json_bytes(build_schema()),
    }
    manifest = "".join(f"{hashlib.sha256(files[name]).hexdigest()}  {name}\n" for name in sorted(files))
    files["SHA256SUMS"] = manifest.encode("ascii")
    return files


def poison_findings(files: dict[str, bytes]) -> list[str]:
    findings: list[str] = []
    token_pattern = re.compile(
        r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(token) for token in PROHIBITED_EXTERNAL_TOKENS) + r")(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )
    repository_path_pattern = re.compile(r"(?:/home/|(?<![A-Za-z0-9_])(?:src|docs|scripts|rules|data)/)", re.IGNORECASE)
    for name, payload in sorted(files.items()):
        text = payload.decode("utf-8")
        if any(ord(char) > 127 for char in text):
            findings.append(f"{name}: non-ASCII text")
        for match in token_pattern.finditer(text):
            findings.append(f"{name}: prohibited token {match.group(0)!r}")
        for match in repository_path_pattern.finditer(text):
            findings.append(f"{name}: repository path fragment {match.group(0)!r}")
    return findings


def write_or_check(*, check: bool) -> int:
    files = rendered_files()
    findings = poison_findings(files)
    if findings:
        for finding in findings:
            print(f"external bundle leak: {finding}", file=sys.stderr)
        return 1

    mismatches: list[str] = []
    if check and EXTERNAL.is_dir():
        unexpected = sorted(path.name for path in EXTERNAL.iterdir() if path.name not in files)
        mismatches.extend(f"unexpected:{name}" for name in unexpected)
    for name, expected in sorted(files.items()):
        path = EXTERNAL / name
        if check:
            actual = path.read_bytes() if path.is_file() else None
            if actual != expected:
                mismatches.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    if mismatches:
        print("bundle differs from deterministic source: " + ", ".join(mismatches), file=sys.stderr)
        return 1
    print(f"strict clean-room external bundle {'checked' if check else 'written'}: {len(files)} files")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare committed files with deterministic output")
    args = parser.parse_args()
    return write_or_check(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
