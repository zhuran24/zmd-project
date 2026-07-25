#!/usr/bin/env python3
"""Pure-stdlib replay for one feasible persisted c5 priority-query artifact."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


RUN = Path(__file__).resolve().parent
REFERENCE = RUN / "independent_c5_pole_phase_replay_reference.py"
HELPER = RUN / "c5_pole_phase_search.py"
ROOT = Path("/home/zhuran24/zmd-pj-codex")
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
OUTPUT = RUN / "independent_priority_replay.json"
CANDIDATE_SHA256 = "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
ALLOWED_TARGETS = {(9, 5, 4), (12, 5, 3), (11, 4, 4), (11, 5, 3), (10, 5, 4)}


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json_pinned(path: Path, expected: str) -> Any:
    observed = sha256(path)
    require(observed == expected, f"hash drift for {path}: {observed}")
    return json.loads(path.read_bytes())


def load_reference() -> Any:
    spec = importlib.util.spec_from_file_location("persisted_c5_replay_reference", REFERENCE)
    require(spec is not None and spec.loader is not None, "reference import spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def strict_modes(strict: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (str(template), str(mode["id"])): mode
        for template, template_record in strict["facility_templates"].items()
        for mode in template_record["modes"]
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args(argv)
    source_path = args.source.resolve()
    require(source_path.parent == RUN, "source must be inside this recovery query directory")
    require(len(args.expected_sha256) == 64, "expected source sha256 length")
    require(not OUTPUT.exists(), f"refusing overwrite: {OUTPUT}")

    ref = load_reference()
    source = load_json_pinned(source_path, args.expected_sha256)
    candidate = load_json_pinned(CANDIDATE, CANDIDATE_SHA256)
    strict = load_json_pinned(STRICT, STRICT_SHA256)
    require(source["schema_version"] == "c5_priority_query_attempt.v1", "source schema")
    winner = source["query"]
    require(winner["status"] in {"OPTIMAL", "FEASIBLE"}, "source query is not feasible")
    target = tuple(int(value) for value in winner["target"])
    require(target in ALLOWED_TARGETS, f"unexpected target: {target}")
    require(int(winner["moved_x"]) == 66, "moved x")
    require(int(winner["uniform_y_shift"]) == 0, "uniform y shift")

    pole_anchors = {
        tuple(int(value) for value in anchor) for anchor in winner["all_35_pole_anchors"]
    }
    require(len(pole_anchors) == 35, "pole count")
    require({(66, 5), (66, 17), (66, 29)} <= pole_anchors, "moved anchors")
    require(not {(65, 5), (65, 17), (65, 29)} & pole_anchors, "old anchors remain")

    core = ref.rect(ref.CORE_ANCHOR, 9, 9)
    backbone = (
        {(x, y) for x in ref.VERTICAL_LANES for y in range(1, ref.GRID_SIZE)}
        | {(x, y) for y in ref.HORIZONTAL_LANES for x in range(1, ref.GRID_SIZE)}
        | ref.ring(core)
    ) - core
    protected = ref.rect(
        (ref.PROTECTED[0], ref.PROTECTED[1]), ref.PROTECTED[2], ref.PROTECTED[3]
    )
    pole_cells = set().union(*(ref.rect(anchor, 2, 2) for anchor in pole_anchors))
    left_anchors = ref.boundary_anchors(69)
    bottom_anchors = ref.boundary_anchors(0)
    boundary = (
        {(0, y) for anchor in left_anchors for y in range(anchor, anchor + 3)}
        | {(x, 0) for anchor in bottom_anchors for x in range(anchor, anchor + 3)}
    )
    fixed_body = core | pole_cells | boundary
    require(len(pole_cells) == 140, "pole bodies overlap")
    require(not fixed_body & (backbone | protected), "fixed collision")
    body_domain = ref.GRID - fixed_body - backbone - protected
    c5 = next(component for component in ref.components(body_domain) if (60, 2) in component)
    require((min(x for x, _y in c5), min(y for _x, y in c5)) == (60, 2), "c5 origin")
    gateways = {
        cell for cell in c5 if any(adjacent in backbone for adjacent in ref.neighbours(cell))
    }
    require(gateways, "c5 gateways")

    power_rule = strict["power"]["coverage_from_pole_anchor"]
    power = {
        (x, y)
        for anchor in pole_anchors
        for x in range(
            max(0, anchor[0] + int(power_rule["x_min_offset"])),
            min(ref.GRID_SIZE - 1, anchor[0] + int(power_rule["x_max_offset"])) + 1,
        )
        for y in range(
            max(0, anchor[1] + int(power_rule["y_min_offset"])),
            min(ref.GRID_SIZE - 1, anchor[1] + int(power_rule["y_max_offset"])) + 1,
        )
    }
    modes = strict_modes(strict)
    occupied: set[tuple[int, int]] = set()
    decoded = []
    template_counts: Counter[str] = Counter()
    coverage_counts = []
    templates = ref.TEMPLATES
    requirements = ref.REQUIREMENTS
    for selected_index, selected in enumerate(winner["selected"]):
        template = str(selected["template"])
        mode_id = str(selected["mode"])
        require(template in templates, f"template {selected_index}")
        pose_index = int(selected["pose_index"])
        raw = candidate["facility_pools"][template][pose_index]
        candidate_mode = str(raw["pose_params"]["port_mode"])
        require(ref.MODE_MAP[candidate_mode] == mode_id, f"candidate mode {selected_index}")
        anchor = (int(raw["anchor"]["x"]), int(raw["anchor"]["y"]))
        require(list(anchor) == selected["anchor"], f"anchor {selected_index}")
        body = {(int(cell[0]), int(cell[1])) for cell in raw["occupied_cells"]}
        require(body == {tuple(cell) for cell in selected["body"]}, f"body {selected_index}")
        mode = modes[(template, mode_id)]
        require(
            body == ref.rect(anchor, int(mode["body"]["width"]), int(mode["body"]["height"])),
            f"strict body {selected_index}",
        )
        require(body <= c5, f"body outside c5 {selected_index}")
        require(not occupied & body, f"body overlap {selected_index}")
        occupied.update(body)
        ports = ref.strict_ports(mode, anchor)
        candidate_inputs = {
            (int(port["x"]), int(port["y"])) for port in raw["input_port_cells"]
        }
        candidate_outputs = {
            (int(port["x"]), int(port["y"])) for port in raw["output_port_cells"]
        }
        require(
            candidate_inputs == {port["access"] for port in ports if port["kind"] == "input"},
            f"candidate input parity {selected_index}",
        )
        require(
            candidate_outputs == {port["access"] for port in ports if port["kind"] == "output"},
            f"candidate output parity {selected_index}",
        )
        available = [port for port in ports if port["access"] not in fixed_body]
        inputs = tuple(sorted(port["access"] for port in available if port["kind"] == "input"))
        outputs = tuple(sorted(port["access"] for port in available if port["kind"] == "output"))
        require(inputs == tuple(tuple(cell) for cell in selected["inputs"]), f"inputs {selected_index}")
        require(outputs == tuple(tuple(cell) for cell in selected["outputs"]), f"outputs {selected_index}")
        coverage = len(body & power)
        require(coverage >= 1, f"unpowered {selected_index}")
        coverage_counts.append(coverage)
        template_counts[template] += 1
        decoded.append(
            {
                "selected_index": selected_index,
                "template": template,
                "mode": mode_id,
                "pose_index": pose_index,
                "anchor": list(anchor),
                "inputs": inputs,
                "outputs": outputs,
                "power_body_cells": coverage,
            }
        )
    require(
        tuple(template_counts[template] for template in templates) == target,
        "template counts",
    )
    expected_body_cells = 9 * target[0] + 25 * target[1] + 24 * target[2]
    require(len(occupied) == expected_body_cells, "body cell count")

    residual = c5 - occupied
    main = ref.reachable(gateways, residual)
    require(main == residual, "residual BFS is disconnected")
    require(len(residual) == len(c5) - expected_body_cells, "residual cell count")
    outside_main = backbone | protected
    for selected, decoded_row in zip(winner["selected"], decoded, strict=True):
        connected_inputs = sum(
            cell not in occupied and (cell in main or cell in outside_main)
            for cell in decoded_row["inputs"]
        )
        connected_outputs = sum(
            cell not in occupied and (cell in main or cell in outside_main)
            for cell in decoded_row["outputs"]
        )
        require(
            connected_inputs == int(selected["connected_clear_inputs"]),
            f"connected inputs {decoded_row['selected_index']}",
        )
        require(
            connected_outputs == int(selected["connected_clear_outputs"]),
            f"connected outputs {decoded_row['selected_index']}",
        )
        decoded_row["available_inputs"] = len(decoded_row["inputs"])
        decoded_row["available_outputs"] = len(decoded_row["outputs"])
        decoded_row["connected_clear_inputs"] = connected_inputs
        decoded_row["connected_clear_outputs"] = connected_outputs

    active_counts: dict[int, Counter[str]] = defaultdict(Counter)
    active_rows = []
    active_keys = set()
    for active in winner["selected_weak_active"]:
        selected_index = int(active["selected_index"])
        require(0 <= selected_index < len(decoded), "active selected index")
        kind = str(active["kind"])
        require(kind in {"input", "output"}, "active kind")
        port_index = int(active["port_index"])
        key = (selected_index, kind, port_index)
        require(key not in active_keys, f"duplicate active incidence {key}")
        active_keys.add(key)
        cells = decoded[selected_index][f"{kind}s"]
        require(0 <= port_index < len(cells), f"active port index {key}")
        cell = cells[port_index]
        require(list(cell) == active["cell"], f"active cell {key}")
        require(cell not in occupied, f"active occupied {key}")
        require(cell in main or cell in outside_main, f"active disconnected {key}")
        active_counts[selected_index][kind] += 1
        active_rows.append(
            {
                "selected_index": selected_index,
                "kind": kind,
                "port_index": port_index,
                "cell": list(cell),
            }
        )
    expected_active = 2 * target[0] + 2 * target[1] + 4 * target[2]
    require(len(active_rows) == expected_active, "active incidence count")
    require(
        all(
            active_counts[index] == requirements[row["template"]]
            for index, row in enumerate(decoded)
        ),
        "active multiplicities",
    )

    result = {
        "schema_version": "independent_c5_priority_replay.v1",
        "status": "C5_PRIORITY_WINNER_INDEPENDENTLY_VERIFIED",
        "classification": "research_pure_stdlib_replay_no_router_no_solver",
        "claim_boundary": (
            "Pure-stdlib replay of the selected custom-pole query: source hash, 35 poles, "
            "candidate/strict body and front parity, power, non-overlap, complete residual BFS, "
            "and optional active-front incidences. No CP model or router is imported or called."
        ),
        "input_sha256": {
            str(source_path): args.expected_sha256,
            str(CANDIDATE): CANDIDATE_SHA256,
            str(STRICT): STRICT_SHA256,
            str(REFERENCE): sha256(REFERENCE),
            str(HELPER): sha256(HELPER),
        },
        "winner": {
            "target": list(target),
            "moved_pole_anchors": [[66, 5], [66, 17], [66, 29]],
            "all_35_pole_anchors": [
                list(anchor) for anchor in sorted(pole_anchors, key=lambda cell: (cell[1], cell[0]))
            ],
            "pole_count": len(pole_anchors),
            "pole_body_cells": len(pole_cells),
            "selected_facilities": len(decoded),
            "template_totals": list(target),
            "body_cells": len(occupied),
            "body_overlap_count": 0,
            "power_coverage_min_body_cells": min(coverage_counts),
            "power_coverage_max_body_cells": max(coverage_counts),
            "c5_component_cells": len(c5),
            "gateway_cells": len(gateways),
            "residual_cells": len(residual),
            "residual_reachable_cells": len(main),
            "all_residual_connected": main == residual,
            "weak_active_incidences": len(active_rows),
            "all_weak_active_connected": True,
            "selected_availability": decoded,
            "selected_weak_active": active_rows,
        },
    }
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(OUTPUT), "status": result["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
