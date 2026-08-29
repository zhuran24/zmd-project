#!/usr/bin/env python3
"""E096: compare exact template and spatial interfaces inside module B."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import traceback
from types import ModuleType
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E096_module_b_interface_thickness/run-001"
)
E095_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E095_y41_module_product_decomposition/run_e095.py"
)
E095_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001/RESULT.json"
)
E095_CHECK = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001/ARTIFACT_CHECK.json"
)
E095_DURABLE = E095_RUNNER.with_name("RESULT.txt")

EXPECTED_HASHES = {
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_RESULT: "78de6850a02e66d1018a6f3f3ec545d624e16bdc0cf7e4ef1b455ea2eb25e609",
    E095_CHECK: "6d75894d7a79cb9611fc20d1121a832777f9cf4eeb8e67bb4fef85066d0ee43f",
    E095_DURABLE: "6794d794cbd512c5bc01379a2f29ace4080127dc8c4d98bd706b9a792e536b14",
}

TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
EXPECTED_B_BODY_COUNT = 91
MIN_ANCHOR_SIDE_COUNT = 20
MAX_ANCHOR_SEPARATOR_COUNT = 15
MIN_SIDE_CANDIDATE_FRACTION = 0.15
MAX_SPATIAL_SEPARATOR_FRACTION = 0.20


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_safe(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            default=str,
        )
    )


def stable_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E096 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E096 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }
    e095 = load_json(E095_RESULT)
    if e095.get("verdict") != "MODULE_B_FRONT_SUBMODEL_CENSORED":
        raise RuntimeError("E096 trigger E095 verdict drift")
    if e095.get("decision") != "DECOMPOSE_MODULE_B_BY_TEMPLATE_OR_BAY":
        raise RuntimeError("E096 trigger E095 decision drift")
    if load_json(E095_CHECK).get("status") != "PASS":
        raise RuntimeError("E096 trigger E095 artifact check is not PASS")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def import_e095() -> ModuleType:
    name = "zmd_e096_pinned_e095"
    spec = importlib.util.spec_from_file_location(name, E095_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import E095 runner: {E095_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def valid_mode_data(
    *,
    e095: ModuleType,
    context: Mapping[str, Any],
    row: Mapping[str, Any],
) -> tuple[set[tuple[int, int]], set[tuple[str, str, int, int]]]:
    module = str(row["module"])
    template = str(row["template"])
    fixed_solid = set(context["fixed_solid"])
    relevant = [
        key
        for key in context["class_counts"]
        if key[0] == module and key[1] == template
    ]
    forced = e095.STABLE_CLASS_BY_BODY.get(str(row["body_digest"]))
    fronts: set[tuple[int, int]] = set()
    supported: set[tuple[str, str, int, int]] = set()
    for pose_index in row["mode_pose_indices"]:
        pose = context["pools"][template][int(pose_index)]
        input_cells = tuple(e095.cell(value) for value in pose["input_port_cells"])
        output_cells = tuple(e095.cell(value) for value in pose["output_port_cells"])
        for class_key in relevant:
            _module, _template, need_in, need_out = class_key
            if forced is not None and (need_in, need_out) != forced:
                continue
            possible_inputs = {
                value
                for value in input_cells
                if e095.in_grid(value) and value not in fixed_solid
            }
            possible_outputs = {
                value
                for value in output_cells
                if e095.in_grid(value) and value not in fixed_solid
            }
            if len(possible_inputs) < need_in or len(possible_outputs) < need_out:
                continue
            supported.add(class_key)
            fronts |= possible_inputs | possible_outputs
    return fronts, supported


def candidate_records(e095: ModuleType, context: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, raw in enumerate(context["body_rows"]):
        if raw["module"] != "B":
            continue
        row = dict(raw)
        fronts, supported = valid_mode_data(e095=e095, context=context, row=row)
        body = tuple(row["body"])
        records.append(
            {
                "candidate_index": index,
                "template": str(row["template"]),
                "body": body,
                "body_digest": str(row["body_digest"]),
                "front_cells": frozenset(fronts),
                "supported_classes": frozenset(supported),
                "bbox": {
                    "min_x": min(value[0] for value in body),
                    "max_x": max(value[0] for value in body),
                    "min_y": min(value[1] for value in body),
                    "max_y": max(value[1] for value in body),
                },
                "is_anchor": body in context["hint_bodies"]["B"],
            }
        )
    if len(records) != 4378:
        raise RuntimeError(f"E096 B candidate count drift: {len(records)}")
    if sum(bool(row["is_anchor"]) for row in records) != EXPECTED_B_BODY_COUNT:
        raise RuntimeError("E096 anchor B body count drift")
    return records


def interface_for_groups(
    records: Sequence[Mapping[str, Any]],
    groups: Mapping[int, str],
) -> dict[str, Any]:
    body_coverers: dict[tuple[int, int], list[int]] = defaultdict(list)
    group_candidate_counts: Counter[str] = Counter()
    group_anchor_counts: Counter[str] = Counter()
    for index, row in enumerate(records):
        group = groups[index]
        group_candidate_counts[group] += 1
        group_anchor_counts[group] += int(bool(row["is_anchor"]))
        for value in row["body"]:
            body_coverers[value].append(index)

    shared_body_cells: set[tuple[int, int]] = set()
    cross_front_body_cells: set[tuple[int, int]] = set()
    directed_front_edges: Counter[tuple[str, str]] = Counter()
    body_edges: Counter[tuple[str, str]] = Counter()
    participating: set[int] = set()

    for value, indices in body_coverers.items():
        present_groups = sorted({groups[index] for index in indices})
        if len(present_groups) > 1:
            shared_body_cells.add(value)
            participating.update(indices)
            for left, right in combinations(present_groups, 2):
                body_edges[(left, right)] += 1

    for index, row in enumerate(records):
        source_group = groups[index]
        for value in row["front_cells"]:
            target_indices = body_coverers.get(value, [])
            target_groups = {
                groups[target]
                for target in target_indices
                if groups[target] != source_group
            }
            if target_groups:
                cross_front_body_cells.add(value)
                participating.add(index)
                participating.update(
                    target
                    for target in target_indices
                    if groups[target] != source_group
                )
                for target_group in target_groups:
                    directed_front_edges[(source_group, target_group)] += 1

    interface_cells = shared_body_cells | cross_front_body_cells
    return {
        "group_candidate_counts": dict(sorted(group_candidate_counts.items())),
        "group_anchor_counts": dict(sorted(group_anchor_counts.items())),
        "shared_body_cell_count": len(shared_body_cells),
        "cross_front_body_cell_count": len(cross_front_body_cells),
        "interface_occupancy_cell_count": len(interface_cells),
        "interface_candidate_count": len(participating),
        "body_interaction_edges": {
            f"{left}<->{right}": count
            for (left, right), count in sorted(body_edges.items())
        },
        "front_body_interaction_edges": {
            f"{left}->{right}": count
            for (left, right), count in sorted(directed_front_edges.items())
        },
        "interface_cell_digest": stable_digest(sorted(interface_cells)),
        "interface_candidate_digest": stable_digest(
            sorted(str(records[index]["body_digest"]) for index in participating)
        ),
    }


def template_interface(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups = {index: str(row["template"]) for index, row in enumerate(records)}
    interface = interface_for_groups(records, groups)
    interface.update(
        {
            "schema": "zmd_e096_template_interface_v1",
            "grouping": "manufacturing_template",
            "class_allocation_dimension_count": 0,
            "class_allocation_log2_box_upper_bound": 0.0,
            "largest_group_candidate_count": max(
                interface["group_candidate_counts"].values()
            ),
            "truth_boundary": (
                "Exact occupancy-interface census; cell states are not asserted "
                "independent and counts do not predict runtime."
            ),
        }
    )
    return interface


def classify_cut(
    row: Mapping[str, Any],
    *,
    axis: str,
    coordinate: int,
) -> str:
    bbox = row["bbox"]
    low = int(bbox[f"min_{axis}"])
    high = int(bbox[f"max_{axis}"])
    if high <= coordinate:
        return "low"
    if low > coordinate:
        return "high"
    return "separator"


def allocation_interface(
    records: Sequence[Mapping[str, Any]],
    groups: Mapping[int, str],
    class_counts: Mapping[tuple[str, str, int, int], int],
) -> dict[str, Any]:
    support_groups: dict[tuple[str, str, int, int], set[str]] = defaultdict(set)
    for index, row in enumerate(records):
        for class_key in row["supported_classes"]:
            support_groups[class_key].add(groups[index])
    dimensions = []
    log2_box = 0.0
    box_size = 1
    for class_key, count in sorted(class_counts.items()):
        groups_for_class = sorted(support_groups.get(class_key, set()))
        if len(groups_for_class) <= 1:
            continue
        dimensions.append(
            {
                "class_key": list(class_key),
                "required_count": int(count),
                "support_groups": groups_for_class,
            }
        )
        box_size *= int(count) + 1
        log2_box += math.log2(int(count) + 1)
    return {
        "class_allocation_dimension_count": len(dimensions),
        "class_allocation_dimensions": dimensions,
        "class_allocation_box_upper_bound": box_size,
        "class_allocation_log2_box_upper_bound": log2_box,
    }


def spatial_frontier(
    records: Sequence[Mapping[str, Any]],
    class_counts: Mapping[tuple[str, str, int, int], int],
) -> list[dict[str, Any]]:
    cuts = [
        *(('x', coordinate) for coordinate in range(1, 68)),
        *(('y', coordinate) for coordinate in range(42, 68)),
    ]
    output: list[dict[str, Any]] = []
    for axis, coordinate in cuts:
        groups = {
            index: classify_cut(row, axis=axis, coordinate=coordinate)
            for index, row in enumerate(records)
        }
        interface = interface_for_groups(records, groups)
        allocation = allocation_interface(records, groups, class_counts)
        group_counts = interface["group_candidate_counts"]
        anchor_counts = interface["group_anchor_counts"]
        nonseparator = int(group_counts.get("low", 0)) + int(
            group_counts.get("high", 0)
        )
        min_side_fraction = (
            min(
                int(group_counts.get("low", 0)),
                int(group_counts.get("high", 0)),
            )
            / nonseparator
            if nonseparator
            else 0.0
        )
        guard = (
            int(anchor_counts.get("low", 0)) >= MIN_ANCHOR_SIDE_COUNT
            and int(anchor_counts.get("high", 0)) >= MIN_ANCHOR_SIDE_COUNT
            and int(anchor_counts.get("separator", 0))
            <= MAX_ANCHOR_SEPARATOR_COUNT
            and min_side_fraction >= MIN_SIDE_CANDIDATE_FRACTION
        )
        row = {
            "axis": axis,
            "coordinate": coordinate,
            "cut_id": f"{axis}_after_{coordinate}",
            "balance_guard_pass": guard,
            "minimum_side_candidate_fraction": min_side_fraction,
            **interface,
            **allocation,
            "separator_candidate_fraction": int(
                group_counts.get("separator", 0)
            )
            / len(records),
            "largest_side_candidate_count": max(
                int(group_counts.get("low", 0)),
                int(group_counts.get("high", 0)),
            ),
        }
        output.append(row)
    output.sort(
        key=lambda row: (
            not bool(row["balance_guard_pass"]),
            int(row["interface_occupancy_cell_count"]),
            int(row["group_candidate_counts"].get("separator", 0)),
            float(row["class_allocation_log2_box_upper_bound"]),
            int(row["largest_side_candidate_count"]),
            str(row["axis"]),
            int(row["coordinate"]),
        )
    )
    return output


def choose(
    template: Mapping[str, Any],
    spatial: Sequence[Mapping[str, Any]],
    universe_count: int,
) -> tuple[str, str, Mapping[str, Any] | None, dict[str, Any]]:
    guarded = [row for row in spatial if row["balance_guard_pass"]]
    if not guarded:
        return (
            "NO_NONTRIVIAL_SPATIAL_SEPARATOR_PASSES_GUARD",
            "SELECT_TEMPLATE_DECOMPOSITION",
            None,
            {"reason": "no guarded spatial cut"},
        )
    best = guarded[0]
    spatial_dominates = (
        int(best["interface_occupancy_cell_count"])
        * 2
        <= int(template["interface_occupancy_cell_count"])
        and int(best["group_candidate_counts"].get("separator", 0))
        <= int(universe_count * MAX_SPATIAL_SEPARATOR_FRACTION)
        and int(best["largest_side_candidate_count"])
        < int(template["largest_group_candidate_count"])
    )
    template_dominates = all(
        int(template["interface_occupancy_cell_count"])
        <= int(row["interface_occupancy_cell_count"])
        and int(template["interface_candidate_count"])
        <= int(row["interface_candidate_count"])
        for row in guarded
    )
    comparison = {
        "template_interface_cells": int(template["interface_occupancy_cell_count"]),
        "template_interface_candidates": int(template["interface_candidate_count"]),
        "template_largest_group_candidates": int(
            template["largest_group_candidate_count"]
        ),
        "spatial_cut_id": str(best["cut_id"]),
        "spatial_interface_cells": int(best["interface_occupancy_cell_count"]),
        "spatial_interface_candidates": int(best["interface_candidate_count"]),
        "spatial_separator_candidates": int(
            best["group_candidate_counts"].get("separator", 0)
        ),
        "spatial_largest_side_candidates": int(
            best["largest_side_candidate_count"]
        ),
        "spatial_class_allocation_dimensions": int(
            best["class_allocation_dimension_count"]
        ),
        "spatial_class_allocation_log2_box_upper_bound": float(
            best["class_allocation_log2_box_upper_bound"]
        ),
        "spatial_dominates": spatial_dominates,
        "template_dominates": template_dominates,
    }
    if spatial_dominates:
        return (
            "SPATIAL_SEPARATOR_INTERFACE_DOMINATES_TEMPLATE_INTERFACE",
            "SELECT_SPATIAL_SEPARATOR_DECOMPOSITION",
            best,
            comparison,
        )
    if template_dominates:
        return (
            "TEMPLATE_INTERFACE_DOMINATES_GUARDED_SPATIAL_INTERFACES",
            "SELECT_TEMPLATE_DECOMPOSITION",
            best,
            comparison,
        )
    return (
        "TEMPLATE_AND_SPATIAL_INTERFACES_ARE_INCOMPARABLE",
        "KEEP_BOTH_AND_BUILD_HYBRID_INTERFACE",
        best,
        comparison,
    )


def run(run_dir: Path) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E096 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    e095 = import_e095()
    context = e095.build_context()
    audit = e095.decomposition_audit(context)
    if audit.get("status") != "PASS":
        raise RuntimeError("E096 imported E095 decomposition is not PASS")
    records = candidate_records(e095, context)
    class_counts = {
        key: int(count)
        for key, count in context["class_counts"].items()
        if key[0] == "B"
    }
    template = template_interface(records)
    spatial = spatial_frontier(records, class_counts)
    verdict, decision, selected, comparison = choose(
        template, spatial, len(records)
    )

    template_path = run_dir / "TEMPLATE_INTERFACE.json"
    spatial_path = run_dir / "SPATIAL_INTERFACE_FRONTIER.json"
    candidate_path = run_dir / "B_CANDIDATE_INTERFACE_RECORDS.json"
    result_path = run_dir / "RESULT.json"
    dump_exclusive(template_path, template)
    dump_exclusive(
        spatial_path,
        {
            "schema": "zmd_e096_spatial_interface_frontier_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "cut_count": len(spatial),
            "guarded_cut_count": sum(
                bool(row["balance_guard_pass"]) for row in spatial
            ),
            "cuts": spatial,
            "truth_boundary": (
                "Exact interaction census under the frozen module-B language; "
                "interface counts do not predict solver runtime."
            ),
        },
    )
    dump_exclusive(
        candidate_path,
        {
            "schema": "zmd_e096_b_candidate_interface_records_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "candidate_count": len(records),
            "candidates": [
                {
                    "candidate_index": int(row["candidate_index"]),
                    "template": str(row["template"]),
                    "body_digest": str(row["body_digest"]),
                    "body": [list(value) for value in row["body"]],
                    "front_cells": [list(value) for value in sorted(row["front_cells"])],
                    "supported_classes": [
                        list(value) for value in sorted(row["supported_classes"])
                    ],
                    "bbox": dict(row["bbox"]),
                    "is_anchor": bool(row["is_anchor"]),
                }
                for row in records
            ],
        },
    )

    result = {
        "schema": "zmd_e096_module_b_interface_thickness_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "candidate_count": len(records),
        "required_body_count": EXPECTED_B_BODY_COUNT,
        "template_interface": {
            "path": display(template_path),
            "sha256": sha256_file(template_path),
            "interface_occupancy_cell_count": template[
                "interface_occupancy_cell_count"
            ],
            "interface_candidate_count": template["interface_candidate_count"],
            "group_candidate_counts": template["group_candidate_counts"],
            "largest_group_candidate_count": template[
                "largest_group_candidate_count"
            ],
            "class_allocation_dimension_count": 0,
        },
        "spatial_frontier": {
            "path": display(spatial_path),
            "sha256": sha256_file(spatial_path),
            "cut_count": len(spatial),
            "guarded_cut_count": sum(
                bool(row["balance_guard_pass"]) for row in spatial
            ),
        },
        "selected_spatial_cut": json_safe(selected) if selected is not None else None,
        "comparison": comparison,
        "candidate_records": {
            "path": display(candidate_path),
            "sha256": sha256_file(candidate_path),
        },
        "truth_boundary": (
            "No-solver interface census only. The selected decomposition is an "
            "authorization for a representation experiment, not a feasibility or "
            "runtime theorem."
        ),
    }
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    run_dir = DEFAULT_RUN_DIR
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(run_dir)
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "candidate_count": result["candidate_count"],
                    "template_interface": result["template_interface"],
                    "selected_spatial_cut": result["selected_spatial_cut"],
                    "comparison": result["comparison"],
                    "result_path": display(result_path),
                    "result_sha256": sha256_file(result_path),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e096_execution_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not failure_path.exists():
            dump_exclusive(failure_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
