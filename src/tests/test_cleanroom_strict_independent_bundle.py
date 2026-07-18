from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = ROOT / "scripts/cleanroom_strict/generate_bundle.py"
VALIDATOR_PATH = ROOT / "scripts/cleanroom_strict/validate_layout.py"
EXTERNAL = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


generator = _load_module("cleanroom_strict_generator_test", GENERATOR_PATH)
validator = _load_module("cleanroom_strict_validator_test", VALIDATOR_PATH)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode()


def _port(port_id: str, kind: str, direction: str) -> dict[str, object]:
    return {"id": port_id, "kind": kind, "body_cell": {"x": 0, "y": 0}, "direction": direction}


def _mini_instance(modes: list[dict[str, object]], required: list[dict[str, str]], raw: dict[str, int], final: dict[str, int]) -> dict[str, object]:
    commodities = sorted(set(raw) | set(final))
    return {
        "schema_version": 1,
        "benchmark_id": "factory_layout_optimality_benchmark_v1",
        "coordinate_system": {
            "origin": "southwest",
            "indexing": "zero_based",
            "x_positive": "east",
            "y_positive": "north",
            "directions": ["N", "E", "S", "W"],
        },
        "grid": {"width": 12, "height": 12},
        "objective": {"kind": "max_lex_area_min_side", "minimum_side": 6, "body_cells_only": True},
        "commodities": commodities,
        "facility_templates": {
            "node": {"requires_power": False, "placement_rule": "any_body_in_grid", "modes": modes},
            "power_pole": {
                "requires_power": False,
                "placement_rule": "any_body_in_grid",
                "modes": [{"id": "fixed", "body": {"width": 1, "height": 1}, "ports": []}],
            },
        },
        "operation_groups": [],
        "required_instances": required,
        "generic_requirements": {
            "raw_outputs": raw,
            "final_inputs": final,
            "raw_output_providers": ["node"],
            "final_input_providers": ["node"],
        },
        "repeatable_auxiliaries": ["power_pole"],
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
            "coverage_from_pole_anchor": {
                "x_min_offset": -5,
                "x_max_offset": 6,
                "y_min_offset": -5,
                "y_max_offset": 6,
            },
            "required_rule": "at_least_one_body_cell_covered",
        },
        "sentinels": {
            "commodity_count": len(commodities),
            "operation_group_count": 0,
            "manufacturing_instance_count": 0,
            "required_instance_count": len(required),
            "required_body_area": len(required),
            "manufacturing_input_terminals": 0,
            "manufacturing_output_terminals": 0,
            "generic_raw_output_terminals": sum(raw.values()),
            "generic_final_input_terminals": sum(final.values()),
            "total_active_terminals": sum(raw.values()) + sum(final.values()),
        },
    }


def _placement(instance_id: str, mode: dict[str, object], x: int, y: int, bindings: dict[str, str | None]) -> dict[str, object]:
    return {
        "instance_id": instance_id,
        "template": "node",
        "mode": mode["id"],
        "anchor": {"x": x, "y": y},
        "port_bindings": bindings,
    }


def _objective(instance: dict[str, object], placements: list[dict[str, object]], routes: list[dict[str, object]]) -> dict[str, object]:
    del routes  # Transport cells intentionally do not affect this objective.
    occupied = {(item["anchor"]["x"], item["anchor"]["y"]) for item in placements}
    best = validator._best_empty_rectangle(12, 12, occupied, 6)
    return {
        "rectangle": {key: best[key] for key in ("x", "y", "width", "height")},
        "area": best["area"],
        "min_side": best["min_side"],
    }


def _run(instance: dict[str, object], placements: list[dict[str, object]], routes: list[dict[str, object]]):
    instance_payload = _json_bytes(instance)
    instance_sha256 = hashlib.sha256(instance_payload).hexdigest()
    witness = {
        "schema_version": 1,
        "instance_digest": "sha256:" + instance_sha256,
        "required_placements": placements,
        "optional_placements": [],
        "route_components": routes,
        "claimed_objective": _objective(instance, placements, routes),
    }
    return validator.validate_bytes(
        instance_payload,
        _json_bytes(witness),
        expected_instance_sha256=instance_sha256,
    )


def test_external_bundle_is_deterministic_neutral_and_has_expected_sentinels() -> None:
    assert generator.write_or_check(check=True) == 0
    files = generator.rendered_files()
    assert not generator.poison_findings(files)
    instance = json.loads(files["problem_instance.json"])
    assert instance["sentinels"] == {
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
    }
    assert len(instance["required_instances"]) == 266
    assert validator.EXPECTED_INSTANCE_SHA256 == hashlib.sha256(files["problem_instance.json"]).hexdigest()
    assert "candidate_placements" not in files["problem_instance.json"].decode().lower()
    manifest_lines = files["SHA256SUMS"].decode().splitlines()
    assert len(manifest_lines) == 4
    for line in manifest_lines:
        digest, name = line.split("  ", 1)
        assert digest == hashlib.sha256(files[name]).hexdigest()


def test_bundle_check_rejects_unexpected_external_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    external = tmp_path / "external"
    monkeypatch.setattr(generator, "EXTERNAL", external)
    assert generator.write_or_check(check=False) == 0
    (external / "private_notes.md").write_text("must not be pasted\n", encoding="utf-8")
    assert generator.write_or_check(check=True) == 1


def test_validator_default_rejects_self_consistent_replacement_instance() -> None:
    mode = {"id": "fixed", "body": {"width": 1, "height": 1}, "ports": []}
    replacement = _mini_instance([mode], [], {}, {})
    instance_payload = _json_bytes(replacement)
    witness = {
        "schema_version": 1,
        "instance_digest": "sha256:" + hashlib.sha256(instance_payload).hexdigest(),
        "required_placements": [],
        "optional_placements": [],
        "route_components": [],
        "claimed_objective": {
            "rectangle": {"x": 0, "y": 0, "width": 12, "height": 12},
            "area": 144,
            "min_side": 12,
        },
    }

    report, code = validator.validate_bytes(instance_payload, _json_bytes(witness))
    assert code == 2
    assert report["status"] == "CONTRACT_ERROR"
    assert "instance SHA-256 differs" in report["errors"][0]["message"]


def test_validator_accepts_inactive_out_of_grid_port_and_ignores_route_cells_for_objective() -> None:
    mode = {
        "id": "east_with_idle_west",
        "body": {"width": 1, "height": 1},
        "ports": [_port("out_e", "output", "E"), _port("in_w", "input", "W")],
    }
    required = [
        {"id": "source", "template": "node", "operation": "generic_io"},
        {"id": "sink", "template": "node", "operation": "generic_io"},
    ]
    instance = _mini_instance([mode], required, {"ore": 1}, {"ore": 1})
    placements = [
        _placement("source", mode, 0, 1, {"out_e": "ore", "in_w": None}),
        _placement("sink", mode, 5, 1, {"out_e": None, "in_w": "ore"}),
    ]
    routes = [
        {"cell": {"x": x, "y": 1}, "kind": "straight", "inputs": ["W"], "outputs": ["E"], "commodities": ["ore"]}
        for x in range(1, 5)
    ]
    # This disconnected proof-subgraph component lies inside the best body-empty rectangle.
    routes.append({"cell": {"x": 6, "y": 6}, "kind": "straight", "inputs": ["W"], "outputs": ["E"], "commodities": ["ore"]})
    report, code = _run(instance, placements, routes)
    assert code == 0, report
    assert report["status"] == "LAYOUT_FEASIBLE"
    assert report["recomputed_objective"]["area"] == 120


def test_validator_rejects_active_out_of_grid_port_and_wrong_terminal_direction() -> None:
    mode = {
        "id": "east_west",
        "body": {"width": 1, "height": 1},
        "ports": [_port("out_e", "output", "E"), _port("in_w", "input", "W")],
    }
    required = [
        {"id": "source", "template": "node", "operation": "generic_io"},
        {"id": "sink", "template": "node", "operation": "generic_io"},
    ]
    instance = _mini_instance([mode], required, {"ore": 1}, {"ore": 1})
    placements = [
        _placement("source", mode, 0, 1, {"out_e": None, "in_w": "ore"}),
        _placement("sink", mode, 5, 1, {"out_e": "ore", "in_w": None}),
    ]
    report, code = _run(instance, placements, [])
    assert code == 1
    assert any(issue["category"] == "P" and "outside grid" in issue["message"] for issue in report["errors"])

    placements = [
        _placement("source", mode, 0, 1, {"out_e": "ore", "in_w": None}),
        _placement("sink", mode, 5, 1, {"out_e": None, "in_w": "ore"}),
    ]
    wrong_routes = [
        {"cell": {"x": 1, "y": 1}, "kind": "straight", "inputs": ["N"], "outputs": ["S"], "commodities": ["ore"]}
    ]
    report, code = _run(instance, placements, wrong_routes)
    assert code == 1
    assert any(issue["category"] == "R" and "direction-compatible" in issue["message"] for issue in report["errors"])


def test_merger_and_splitter_share_one_component_across_commodities_and_terminals() -> None:
    modes = [
        {"id": "source_e", "body": {"width": 1, "height": 1}, "ports": [_port("out_e", "output", "E")]},
        {"id": "source_n", "body": {"width": 1, "height": 1}, "ports": [_port("out_n", "output", "N")]},
        {"id": "sink_w", "body": {"width": 1, "height": 1}, "ports": [_port("in_w", "input", "W")]},
        {"id": "sink_s", "body": {"width": 1, "height": 1}, "ports": [_port("in_s", "input", "S")]},
    ]
    required = [
        {"id": instance_id, "template": "node", "operation": "generic_io"}
        for instance_id in ("source_a", "source_b", "sink_a", "sink_b")
    ]
    instance = _mini_instance(modes, required, {"ore_a": 1, "ore_b": 1}, {"ore_a": 1, "ore_b": 1})
    placements = [
        _placement("source_a", modes[0], 1, 1, {"out_e": "ore_a"}),
        _placement("source_b", modes[1], 2, 0, {"out_n": "ore_b"}),
        _placement("sink_a", modes[2], 5, 1, {"in_w": "ore_a"}),
        _placement("sink_b", modes[3], 4, 2, {"in_s": "ore_b"}),
    ]
    shared = ["ore_a", "ore_b"]
    routes = [
        {"cell": {"x": 2, "y": 1}, "kind": "merger", "inputs": ["W", "S"], "outputs": ["E"], "commodities": shared},
        {"cell": {"x": 3, "y": 1}, "kind": "straight", "inputs": ["W"], "outputs": ["E"], "commodities": shared},
        {"cell": {"x": 4, "y": 1}, "kind": "splitter", "inputs": ["W"], "outputs": ["E", "N"], "commodities": shared},
    ]
    report, code = _run(instance, placements, routes)
    assert code == 0, report


def test_turn_and_cross_connect_only_their_declared_directions() -> None:
    turn_modes = [
        {"id": "source_e", "body": {"width": 1, "height": 1}, "ports": [_port("out_e", "output", "E")]},
        {"id": "sink_s", "body": {"width": 1, "height": 1}, "ports": [_port("in_s", "input", "S")]},
    ]
    required = [
        {"id": "source", "template": "node", "operation": "generic_io"},
        {"id": "sink", "template": "node", "operation": "generic_io"},
    ]
    instance = _mini_instance(turn_modes, required, {"ore": 1}, {"ore": 1})
    placements = [
        _placement("source", turn_modes[0], 1, 1, {"out_e": "ore"}),
        _placement("sink", turn_modes[1], 2, 3, {"in_s": "ore"}),
    ]
    routes = [
        {"cell": {"x": 2, "y": 1}, "kind": "turn", "inputs": ["W"], "outputs": ["N"], "commodities": ["ore"]},
        {"cell": {"x": 2, "y": 2}, "kind": "straight", "inputs": ["S"], "outputs": ["N"], "commodities": ["ore"]},
    ]
    report, code = _run(instance, placements, routes)
    assert code == 0, report

    cross_modes = [
        {"id": "source_e", "body": {"width": 1, "height": 1}, "ports": [_port("out_e", "output", "E")]},
        {"id": "sink_w", "body": {"width": 1, "height": 1}, "ports": [_port("in_w", "input", "W")]},
        {"id": "source_n", "body": {"width": 1, "height": 1}, "ports": [_port("out_n", "output", "N")]},
        {"id": "sink_s", "body": {"width": 1, "height": 1}, "ports": [_port("in_s", "input", "S")]},
    ]
    required = [
        {"id": name, "template": "node", "operation": "generic_io"}
        for name in ("west_source", "east_sink", "south_source", "north_sink")
    ]
    instance = _mini_instance(cross_modes, required, {"horizontal": 1, "vertical": 1}, {"horizontal": 1, "vertical": 1})
    placements = [
        _placement("west_source", cross_modes[0], 0, 3, {"out_e": "horizontal"}),
        _placement("east_sink", cross_modes[1], 6, 3, {"in_w": "horizontal"}),
        _placement("south_source", cross_modes[2], 3, 0, {"out_n": "vertical"}),
        _placement("north_sink", cross_modes[3], 3, 6, {"in_s": "vertical"}),
    ]
    routes = [
        *[
            {"cell": {"x": x, "y": 3}, "kind": "straight", "inputs": ["W"], "outputs": ["E"], "commodities": ["horizontal"]}
            for x in (1, 2, 4, 5)
        ],
        *[
            {"cell": {"x": 3, "y": y}, "kind": "straight", "inputs": ["S"], "outputs": ["N"], "commodities": ["vertical"]}
            for y in (1, 2, 4, 5)
        ],
        {
            "cell": {"x": 3, "y": 3},
            "kind": "cross",
            "channels": [
                {"inputs": ["W"], "outputs": ["E"], "commodities": ["horizontal"]},
                {"inputs": ["S"], "outputs": ["N"], "commodities": ["vertical"]},
            ],
        },
    ]
    report, code = _run(instance, placements, routes)
    assert code == 0, report

    broken = copy.deepcopy(routes)
    broken[-1]["channels"][0]["commodities"] = ["vertical"]
    report, code = _run(instance, placements, broken)
    assert code == 1
    assert any(issue["category"] == "R" for issue in report["errors"])


@pytest.mark.parametrize(
    "payload_mutator",
    [
        lambda text: text.replace('"width": 12', '"width": true', 1),
        lambda text: text.replace('"width": 12', '"width": NaN', 1),
        lambda text: text.replace('"width": 12', '"width": 12, "width": 12', 1),
        lambda text: text.replace('"width": 12', '"width": 12, "surprise": 1', 1),
    ],
)
def test_strict_parser_rejects_bool_nonfinite_duplicate_and_unknown(payload_mutator) -> None:
    mode = {"id": "fixed", "body": {"width": 1, "height": 1}, "ports": []}
    instance = _mini_instance([mode], [], {}, {})
    instance_payload = payload_mutator(_json_bytes(instance).decode()).encode()
    empty_witness = _json_bytes(
        {
            "schema_version": 1,
            "instance_digest": "sha256:" + "0" * 64,
            "required_placements": [],
            "optional_placements": [],
            "route_components": [],
            "claimed_objective": {"rectangle": {"x": 0, "y": 0, "width": 12, "height": 12}, "area": 144, "min_side": 12},
        }
    )
    report, code = validator.validate_bytes(
        instance_payload,
        empty_witness,
        expected_instance_sha256=hashlib.sha256(instance_payload).hexdigest(),
    )
    assert code == 2
    assert report["status"] == "CONTRACT_ERROR"


def test_validator_rejects_empty_instance_id_before_layout_validation() -> None:
    mode = {"id": "fixed", "body": {"width": 1, "height": 1}, "ports": []}
    instance = _mini_instance([mode], [], {}, {})
    instance_payload = _json_bytes(instance)
    instance_sha256 = hashlib.sha256(instance_payload).hexdigest()
    witness = {
        "schema_version": 1,
        "instance_digest": "sha256:" + instance_sha256,
        "required_placements": [],
        "optional_placements": [
            _placement("", mode, 0, 0, {}),
        ],
        "route_components": [],
        "claimed_objective": {
            "rectangle": {"x": 0, "y": 0, "width": 12, "height": 12},
            "area": 144,
            "min_side": 12,
        },
    }

    report, code = validator.validate_bytes(
        instance_payload,
        _json_bytes(witness),
        expected_instance_sha256=instance_sha256,
    )
    assert code == 2
    assert report["status"] == "CONTRACT_ERROR"
    assert report["errors"][0]["pointer"] == "/optional_placements/0/instance_id"


def test_validator_rejects_oversized_claim_before_materializing_cells(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mode = {"id": "fixed", "body": {"width": 1, "height": 1}, "ports": []}
    instance = _mini_instance([mode], [], {}, {})
    instance_payload = _json_bytes(instance)
    instance_sha256 = hashlib.sha256(instance_payload).hexdigest()
    witness = {
        "schema_version": 1,
        "instance_digest": "sha256:" + instance_sha256,
        "required_placements": [],
        "optional_placements": [],
        "route_components": [],
        "claimed_objective": {
            "rectangle": {"x": 0, "y": 0, "width": 10**100, "height": 12},
            "area": 0,
            "min_side": 0,
        },
    }
    builtin_range = range

    def reject_huge_range(*args):
        result = builtin_range(*args)
        if len(result) > 1_000:
            raise AssertionError("validator attempted to materialize an unbounded rectangle")
        return result

    monkeypatch.setattr(validator, "range", reject_huge_range, raising=False)
    report, code = validator.validate_bytes(
        instance_payload,
        _json_bytes(witness),
        expected_instance_sha256=instance_sha256,
    )
    assert code == 1
    assert report["status"] == "LAYOUT_INVALID"
    assert any("leaves the grid" in issue["message"] for issue in report["errors"])


def _brute_best(width: int, height: int, occupied: set[tuple[int, int]], minimum_side: int) -> tuple[int, int]:
    best = (0, 0)
    for x0 in range(width):
        for y0 in range(height):
            for x1 in range(x0 + minimum_side, width + 1):
                for y1 in range(y0 + minimum_side, height + 1):
                    if all((x, y) not in occupied for x in range(x0, x1) for y in range(y0, y1)):
                        best = max(best, ((x1 - x0) * (y1 - y0), min(x1 - x0, y1 - y0)))
    return best


def test_empty_rectangle_algorithm_matches_small_grid_bruteforce() -> None:
    rng = random.Random(20260718)
    for _ in range(40):
        occupied = {(x, y) for x in range(7) for y in range(6) if rng.random() < 0.25}
        fast = validator._best_empty_rectangle(7, 6, occupied, 2)
        assert (fast["area"], fast["min_side"]) == _brute_best(7, 6, occupied, 2)


def test_validator_is_stdlib_only_and_runs_from_an_isolated_copy(tmp_path: Path) -> None:
    tree = ast.parse(VALIDATOR_PATH.read_text(encoding="utf-8"))
    roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    roots.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert roots <= {"__future__", "argparse", "collections", "dataclasses", "hashlib", "json", "pathlib", "sys", "typing"}

    copied = tmp_path / "validate_layout.py"
    copied.write_bytes(VALIDATOR_PATH.read_bytes())
    result = subprocess.run(
        [sys.executable, "-I", str(copied), "--help"],
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "LAYOUT_FEASIBLE" not in result.stdout
