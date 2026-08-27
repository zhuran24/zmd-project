#!/usr/bin/env python3
"""E063: scan a causal second-object frontier under one E062 pole near miss."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E063_pole_conditioned_second_object_frontier/run-007"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
MANIFEST_PATH = OUT / "CANDIDATE_MANIFEST.json"
CHUNK_DIR = OUT / "chunks"

E061_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E061_all_one_object_signature_frontier/run_e061.py"
)
E062_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E062_one_object_tradeoff_atlas/run_e062.py"
)
E062_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E065_source_stable_replay_materialization/run-001/e062-source/RESULT.json"
)
E060_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E060_generic_qiaoyu_sink_correction/"
    "run-001/RESULT.json"
)
E055_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E055_causal_pair_assignment_frontier/"
    "run-002/BEST_ASSIGNMENT.json"
)
E055_WITNESS = (
    ROOT
    / "research_lab/local/zero_condition/E055_causal_pair_assignment_frontier/"
    "run-002/BEST_JOINT_WITNESS.json"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONPYCACHEPREFIX": "/tmp/zmd_e063_source_cache_v7",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "287000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E061_RUNNER: "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
    E062_RUNNER: "91770f3ba9a96a3c79bd95c42a4e40b9a540ab537e97079b02f7c57c6fedb67e",
    E062_RESULT: "8ddff564f9359da582bbb212d77a736c2651294c8d335d35c4104b73c0b7d361",
    E060_RESULT: "feb697f506cb2ca2422c1d0e96a02250cb33afcaa21fc86fda939f6ce79409b8",
    E055_ASSIGNMENT: "bf6d1cfcd4c6aaf649a16b9513044b2023b5a9a1a5b39267ebcaad15ffe2c46b",
    E055_WITNESS: "3b36ad647149af238567b3746e165fc60fbd107d47b10d8ba92bf15e4e2ab559",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
}

OLD_POLE_ID = "pose_optional::power_pole::p_x53_y68_o0_m_omni"
NEW_POLE_ID = "pose_optional::power_pole::p_x54_y68_o0_m_omni"
OLD_POLE_POSE = 3725
PARENT_POLE_POSE = 3794
EXPECTED_PARENT_OBJECTIVE = 1
FACE_ENUMERATION_CAP = 256
CHUNK_SIZE = 100
MAX_MATERIALIZED_CANDIDATES = 5
SIX4 = "manufacturing_6x4"


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        ).encode("utf-8")
    ).hexdigest()


def encoded(value: Any) -> bytes:
    return (
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def dump_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded(value))
        handle.flush()
        os.fsync(handle.fileno())


def dump_or_validate(path: Path, value: Any) -> None:
    payload = encoded(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"checkpoint byte drift: {path}")
        return
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_identity() -> dict[str, Any]:
    if Path.cwd().resolve() != ROOT.resolve():
        raise RuntimeError(f"run E063 from research root: {Path.cwd()}")
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E063 must run on research/main")
    mismatches = {
        key: {"expected": expected, "actual": os.environ.get(key)}
        for key, expected in EXPECTED_ENV.items()
        if os.environ.get(key) != expected
    }
    unexpected_exact = sorted(
        key
        for key in os.environ
        if key.startswith("EXACT_") and key not in EXPECTED_ENV
    )
    if mismatches or unexpected_exact:
        raise RuntimeError(
            f"environment mismatch: mismatches={mismatches}, "
            f"unexpected_exact={unexpected_exact}"
        )
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(
                f"frozen identity drift for {path}: {actual} != {expected}"
            )
    e062_result = load_json(E062_RESULT)
    if e062_result.get("verdict") != "ONE_OBJECT_TRADEOFF_NEAR_MISSES_FOUND":
        raise RuntimeError("E063 E062 trigger verdict drift")
    e060_result = load_json(E060_RESULT)
    if (
        e060_result.get("verdict")
        != "GENERIC_QIAOYU_SINK_FREEDOM_REVALIDATES_TWO_ZERO_TARGET"
    ):
        raise RuntimeError("E063 E060 authority successor drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output(
            "status", "--porcelain=v1", "--untracked-files=no"
        ),
    }


def enumerate_directional_face(
    *,
    operation_counts: Mapping[str, int],
    e062: Any,
    options: Mapping[int, Sequence[tuple[Any, ...]]],
    sink_space: Mapping[str, Any],
    optimum: int,
    random_seed: int,
) -> dict[str, Any]:
    if not sink_space["slots"] or any(not rows for rows in options.values()):
        raise RuntimeError("E063 parent face has a structural-empty signature space")
    model = cp_model.CpModel()
    x_vars: dict[tuple[int, int], Any] = {}
    for destination, rows in options.items():
        variables: list[Any] = []
        for option_index, _option in enumerate(rows):
            variable = model.NewBoolVar(f"e063_face_x_{destination}_{option_index}")
            x_vars[(destination, option_index)] = variable
            variables.append(variable)
        model.AddExactlyOne(variables)
    for operation, expected in operation_counts.items():
        model.Add(
            cp_model.LinearExpr.Sum(
                [
                    x_vars[(destination, option_index)]
                    for destination, rows in options.items()
                    for option_index, option in enumerate(rows)
                    if str(option[0]) == operation
                ]
            )
            == int(expected)
        )
    components = sorted(
        {
            int(component)
            for rows in options.values()
            for _operation, _pose_idx, signature in rows
            for part in signature
            for component in part
        }
        | {int(value) for value in sink_space["components"]}
    )
    fine_sources: dict[int, Any] = {}
    fine_sinks: dict[int, Any] = {}
    qiaoyu_sources: dict[int, Any] = {}
    fine_mismatch: dict[int, Any] = {}
    for component in components:
        fine_sources[component] = e062.add_exact_or(
            model,
            name=f"e063_face_source_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in options.items()
                for option_index, option in enumerate(rows)
                if component in set(option[2][1])
            ],
        )
        fine_sinks[component] = e062.add_exact_or(
            model,
            name=f"e063_face_sink_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in options.items()
                for option_index, option in enumerate(rows)
                if component in set(option[2][0])
            ],
        )
        qiaoyu_sources[component] = e062.add_exact_or(
            model,
            name=f"e063_face_qiaoyu_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in options.items()
                for option_index, option in enumerate(rows)
                if component in set(option[2][2])
            ],
        )
        mismatch = model.NewBoolVar(f"e063_face_mismatch_{component}")
        source = fine_sources[component]
        sink = fine_sinks[component]
        model.Add(mismatch >= source - sink)
        model.Add(mismatch >= sink - source)
        model.Add(mismatch <= source + sink)
        model.Add(mismatch <= 2 - source - sink)
        fine_mismatch[component] = mismatch
    sink_component_vars = {
        component: model.NewBoolVar(f"e063_face_qsink_{component}")
        for component in sink_space["components"]
    }
    model.AddExactlyOne(list(sink_component_vars.values()))
    for component in components:
        model.Add(
            qiaoyu_sources[component]
            == (
                sink_component_vars[component]
                if component in sink_component_vars
                else 0
            )
        )
    model.Add(cp_model.LinearExpr.Sum(list(fine_sources.values())) >= 1)
    model.Add(cp_model.LinearExpr.Sum(list(fine_sinks.values())) >= 1)
    model.Add(
        cp_model.LinearExpr.Sum(list(fine_mismatch.values())) == int(optimum)
    )
    model.Minimize(0)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.num_search_workers = 8
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = int(random_seed)
    patterns: list[dict[str, Any]] = []
    for _index in range(FACE_ENUMERATION_CAP):
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            patterns.sort(
                key=lambda row: (
                    row["source_only_components"],
                    row["sink_only_components"],
                    row["qiaoyu_sink_component"],
                    row["fine_source_components"],
                    row["fine_sink_components"],
                )
            )
            return {
                "status": solver.StatusName(status),
                "complete": status == cp_model.INFEASIBLE,
                "pattern_count": len(patterns),
                "patterns": patterns,
            }
        source_set = {
            component
            for component, variable in fine_sources.items()
            if solver.Value(variable) == 1
        }
        sink_set = {
            component
            for component, variable in fine_sinks.items()
            if solver.Value(variable) == 1
        }
        qiaoyu_sink = next(
            component
            for component, variable in sink_component_vars.items()
            if solver.Value(variable) == 1
        )
        pattern = {
            "qiaoyu_sink_component": int(qiaoyu_sink),
            "fine_source_components": sorted(source_set),
            "fine_sink_components": sorted(sink_set),
            "source_only_components": sorted(source_set - sink_set),
            "sink_only_components": sorted(sink_set - source_set),
        }
        patterns.append(pattern)
        literals: list[Any] = []
        for component in components:
            source = fine_sources[component]
            sink = fine_sinks[component]
            q_sink = sink_component_vars.get(component)
            literals.append(source.Not() if component in source_set else source)
            literals.append(sink.Not() if component in sink_set else sink)
            if q_sink is not None:
                literals.append(q_sink.Not() if component == qiaoyu_sink else q_sink)
        model.AddBoolOr(literals)
    return {
        "status": "ENUMERATION_CAP",
        "complete": False,
        "pattern_count": len(patterns),
        "patterns": patterns,
    }


def parent_context(e061: Any, e062: Any) -> dict[str, Any]:
    base = e061.reconstruct()
    alternatives = [
        row
        for row in e061.enumerate_alternatives(
            base=base,
            instance_id=OLD_POLE_ID,
        )
        if int(row["pose_idx"]) == PARENT_POLE_POSE
    ]
    if len(alternatives) != 1:
        raise RuntimeError(f"E063 parent pole alternative drift: {len(alternatives)}")
    alternative = alternatives[0]
    solution = {
        str(key): dict(value) for key, value in alternative["solution"].items()
    }
    if OLD_POLE_ID in solution or NEW_POLE_ID not in solution:
        raise RuntimeError("E063 pole identity transport drift")
    if int(solution[NEW_POLE_ID]["pose_idx"]) != PARENT_POLE_POSE:
        raise RuntimeError("E063 parent pole pose drift")
    occupied, _owners = base["e014"].base_occupancy(
        solution,
        base["inputs"]["pools"],
    )
    selected_poles = {
        int(row["pose_idx"])
        for row in solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    parent_base = dict(base)
    parent_base.update(
        {
            "solution": solution,
            "occupied": occupied,
            "selected_poles": selected_poles,
        }
    )
    bodies = e061.body_rows(
        solution,
        base["inputs"]["pools"],
        base["e014"],
    )
    mode_map = e061.modes_by_footprint(base["inputs"]["pools"])
    descriptors = e061.raw_descriptors(
        bodies=bodies,
        mode_map=mode_map,
        pools=base["inputs"]["pools"],
        enumerate_patterns=base["enumerate_patterns"],
    )
    routing_context = base["build_routing_context"](
        solution,
        base["inputs"]["pools"],
        70,
        70,
    )
    options = e061.map_descriptors(
        descriptors=descriptors,
        routing_context=routing_context,
    )
    sink_space = e061.generic_sink_space(
        candidate=solution,
        routing_context=routing_context,
        inputs=base["inputs"],
        is_port_front_usable=base["is_port_front_usable"],
    )
    calibration = e062.solve_qiaoyu_hard(
        options=options,
        sink_space=sink_space,
        random_seed=63001,
    )
    if (
        calibration.get("status") != "OPTIMAL"
        or int(calibration.get("objective", -1)) != EXPECTED_PARENT_OBJECTIVE
    ):
        raise RuntimeError(f"E063 pole-parent calibration drift: {calibration}")
    directional_face = enumerate_directional_face(
        operation_counts=base["e058"].OPERATION_COUNTS,
        e062=e062,
        options=options,
        sink_space=sink_space,
        optimum=EXPECTED_PARENT_OBJECTIVE,
        random_seed=63002,
    )
    if not bool(directional_face["complete"]):
        raise RuntimeError(f"E063 pole-parent face nonterminal: {directional_face}")
    patterns = list(directional_face["patterns"])
    if not patterns:
        raise RuntimeError("E063 pole-parent optimum face is empty")
    invalid_patterns = [
        row
        for row in patterns
        if len(row["source_only_components"])
        + len(row["sink_only_components"])
        != EXPECTED_PARENT_OBJECTIVE
    ]
    if invalid_patterns:
        raise RuntimeError(
            "E063 pole-parent optimum face contains a non-unit mismatch pattern: "
            f"{invalid_patterns[:3]}"
        )
    mismatch_components = sorted(
        {
            int(component)
            for row in directional_face["patterns"]
            for key in ("source_only_components", "sink_only_components")
            for component in row[key]
        }
    )
    return {
        "base": base,
        "parent_base": parent_base,
        "solution": solution,
        "routing_context": routing_context,
        "bodies": bodies,
        "mode_map": mode_map,
        "fixed_descriptors": descriptors,
        "calibration": calibration,
        "directional_face": directional_face,
        "mismatch_components": mismatch_components,
        "parent_alternative": {
            "source_instance_id": OLD_POLE_ID,
            "replacement_instance_id": NEW_POLE_ID,
            "current_pose_idx": OLD_POLE_POSE,
            "replacement_pose_idx": PARENT_POLE_POSE,
            "replacement_pose_id": str(alternative["pose_id"]),
            "occupied_cells": json_safe(alternative["occupied_cells"]),
        },
    }


def component_boundary_selection(context: Mapping[str, Any]) -> dict[str, Any]:
    base = context["base"]
    solution = context["solution"]
    routing_context = context["routing_context"]
    mismatch_components = [int(value) for value in context["mismatch_components"]]
    boundary_edges: dict[str, dict[int, set[tuple[int, int]]]] = {}
    component_sizes: dict[str, int] = {}
    for target_component in mismatch_components:
        component_cells = set(routing_context.cells_by_component[target_component])
        component_sizes[str(target_component)] = len(component_cells)
        for x, y in component_cells:
            for neighbor in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            ):
                owner = routing_context.occupied_owner_by_cell.get(neighbor)
                if owner is None:
                    continue
                boundary_edges.setdefault(str(owner), {}).setdefault(
                    target_component,
                    set(),
                ).add(neighbor)
    owner_rows: list[dict[str, Any]] = []
    separators: set[str] = set()
    for owner, edge_map in sorted(boundary_edges.items()):
        row = solution[owner]
        facility_type = str(row["facility_type"])
        pose_idx = int(row["pose_idx"])
        touched_components: set[int] = set()
        for x, y in base["e014"].pose_cells(
            base["inputs"]["pools"],
            facility_type,
            pose_idx,
        ):
            for neighbor in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            ):
                component = routing_context.component_by_cell.get(neighbor)
                if component is not None:
                    touched_components.add(int(component))
        is_separator = len(touched_components) > 1
        if is_separator:
            separators.add(owner)
        owner_rows.append(
            {
                "owner": owner,
                "facility_type": facility_type,
                "operation_type": str(row.get("operation_type", "")),
                "pose_idx": pose_idx,
                "boundary_edge_count": sum(len(edges) for edges in edge_map.values()),
                "boundary_edge_count_by_mismatch_component": {
                    str(component): len(edges)
                    for component, edges in sorted(edge_map.items())
                },
                "boundary_mismatch_components": sorted(edge_map),
                "touched_components": sorted(touched_components),
                "is_separator": is_separator,
            }
        )
    six4_ids = {
        str(instance_id)
        for instance_id, row in solution.items()
        if str(row["facility_type"]) == SIX4
    }
    protocol_ids = {
        str(instance_id)
        for instance_id, row in solution.items()
        if str(row["facility_type"]) == "protocol_core"
    }
    selected_ids = (separators | six4_ids | protocol_ids) - {
        OLD_POLE_ID,
        NEW_POLE_ID,
    }
    return {
        "directional_face_pattern_count": int(
            context["directional_face"]["pattern_count"]
        ),
        "mismatch_components": mismatch_components,
        "component_sizes": component_sizes,
        "boundary_owner_count": len(boundary_edges),
        "separator_owner_count": len(separators),
        "six4_body_count": len(six4_ids),
        "protocol_provider_count": len(protocol_ids),
        "selected_object_count": len(selected_ids),
        "selected_ids": sorted(selected_ids),
        "owner_rows": owner_rows,
    }


def build_candidate_manifest(
    *,
    e061: Any,
    context: Mapping[str, Any],
    selection: Mapping[str, Any],
    runner_sha256: str,
) -> dict[str, Any]:
    parent_base = context["parent_base"]
    solution = context["solution"]
    base = context["base"]
    candidates_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    aliases_by_key: Counter[tuple[Any, ...]] = Counter()
    raw_alternative_count = 0
    same_mode_counts: Counter[str] = Counter()
    for instance_id in selection["selected_ids"]:
        row = solution[instance_id]
        facility_type = str(row["facility_type"])
        current_pose_idx = int(row["pose_idx"])
        old_cells = tuple(
            sorted(
                base["e014"].pose_cells(
                    base["inputs"]["pools"],
                    facility_type,
                    current_pose_idx,
                )
            )
        )
        for alternative in e061.enumerate_alternatives(
            base=parent_base,
            instance_id=instance_id,
        ):
            raw_alternative_count += 1
            if bool(alternative["same_footprint"]):
                same_mode_counts[facility_type] += 1
                if facility_type != "protocol_core":
                    continue
                key = (
                    "same_mode",
                    facility_type,
                    old_cells,
                    current_pose_idx,
                    int(alternative["pose_idx"]),
                )
            else:
                new_cells = tuple(
                    sorted(
                        (int(x), int(y))
                        for x, y in alternative["occupied_cells"]
                    )
                )
                key = ("body", facility_type, old_cells, new_cells)
            aliases_by_key[key] += 1
            if key in candidates_by_key:
                continue
            new_cells_payload = (
                [list(cell) for cell in key[3]]
                if key[0] == "body"
                else [list(cell) for cell in old_cells]
            )
            candidates_by_key[key] = {
                "source_instance_id": str(instance_id),
                "facility_type": facility_type,
                "operation_type": str(row.get("operation_type", "")),
                "current_pose_idx": current_pose_idx,
                "replacement_pose_idx": int(alternative["pose_idx"]),
                "replacement_pose_id": str(alternative["pose_id"]),
                "same_footprint": bool(alternative["same_footprint"]),
                "old_occupied_cells": [list(cell) for cell in old_cells],
                "new_occupied_cells": new_cells_payload,
                "selection_reasons": sorted(
                    reason
                    for reason, members in (
                        ("directional_face_separator", {
                            row["owner"]
                            for row in selection["owner_rows"]
                            if bool(row["is_separator"])
                        }),
                        ("six4_terminal_body", {
                            value
                            for value in selection["selected_ids"]
                            if str(solution[value]["facility_type"]) == SIX4
                        }),
                        ("generic_input_provider", {
                            value
                            for value in selection["selected_ids"]
                            if str(solution[value]["facility_type"])
                            == "protocol_core"
                        }),
                    )
                    if instance_id in members
                ),
            }
    candidates = sorted(
        candidates_by_key.values(),
        key=lambda row: (
            str(row["facility_type"]),
            tuple(tuple(cell) for cell in row["old_occupied_cells"]),
            tuple(tuple(cell) for cell in row["new_occupied_cells"]),
            int(row["replacement_pose_idx"]),
            str(row["source_instance_id"]),
        ),
    )
    for index, candidate in enumerate(candidates, 1):
        candidate["candidate_index"] = index
        if candidate["same_footprint"]:
            key = (
                "same_mode",
                candidate["facility_type"],
                tuple(tuple(cell) for cell in candidate["old_occupied_cells"]),
                int(candidate["current_pose_idx"]),
                int(candidate["replacement_pose_idx"]),
            )
        else:
            key = (
                "body",
                candidate["facility_type"],
                tuple(tuple(cell) for cell in candidate["old_occupied_cells"]),
                tuple(tuple(cell) for cell in candidate["new_occupied_cells"]),
            )
        candidate["alias_count_including_representative"] = int(aliases_by_key[key])
        old_set = {tuple(cell) for cell in candidate["old_occupied_cells"]}
        new_set = {tuple(cell) for cell in candidate["new_occupied_cells"]}
        candidate["occupied_symmetric_difference"] = len(old_set ^ new_set)
    manifest = {
        "schema": "zmd_zero_condition_e063_candidate_manifest_v1",
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "parent_pole": context["parent_alternative"],
        "selection": selection,
        "raw_alternative_count": raw_alternative_count,
        "same_mode_counts": dict(sorted(same_mode_counts.items())),
        "distinct_candidate_count": len(candidates),
        "candidates": candidates,
        "ledger_effect": "none",
    }
    dump_or_validate(MANIFEST_PATH, manifest)
    return manifest


def reconstruct_candidate(
    *,
    e061: Any,
    parent_base: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    matches = [
        alternative
        for alternative in e061.enumerate_alternatives(
            base=parent_base,
            instance_id=str(spec["source_instance_id"]),
        )
        if int(alternative["pose_idx"]) == int(spec["replacement_pose_idx"])
        and bool(alternative["same_footprint"]) == bool(spec["same_footprint"])
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "E063 candidate reconstruction drift: "
            f"{spec['candidate_index']} matches={len(matches)}"
        )
    alternative = matches[0]
    actual_cells = sorted(
        (int(x), int(y)) for x, y in alternative["occupied_cells"]
    )
    expected_cells = sorted(
        (int(x), int(y)) for x, y in spec["new_occupied_cells"]
    )
    if actual_cells != expected_cells:
        raise RuntimeError(
            f"E063 candidate cell drift: {spec['candidate_index']}"
        )
    return alternative


def evaluate_candidate(
    *,
    e061: Any,
    e062: Any,
    context: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    alternative = reconstruct_candidate(
        e061=e061,
        parent_base=context["parent_base"],
        spec=spec,
    )
    solution = alternative["solution"]
    base = context["base"]
    routing_context = base["build_routing_context"](
        solution,
        base["inputs"]["pools"],
        70,
        70,
    )
    if str(spec["facility_type"]) == SIX4 and not bool(spec["same_footprint"]):
        descriptors = e061.dynamic_descriptors(
            candidate=solution,
            base=base,
            mode_map=context["mode_map"],
        )
    else:
        descriptors = context["fixed_descriptors"]
    options = e061.map_descriptors(
        descriptors=descriptors,
        routing_context=routing_context,
    )
    sink_space = e061.generic_sink_space(
        candidate=solution,
        routing_context=routing_context,
        inputs=base["inputs"],
        is_port_front_usable=base["is_port_front_usable"],
    )
    directional = e062.solve_qiaoyu_hard(
        options=options,
        sink_space=sink_space,
        random_seed=63100 + int(spec["candidate_index"]),
    )
    joint_replay = None
    if directional.get("status") in {"OPTIMAL", "FEASIBLE"} and int(
        directional.get("objective", -1)
    ) == 0:
        joint_replay = context["base"]["e058"].solve_signature(
            options=options,
            sink_space=sink_space,
            random_seed=64100 + int(spec["candidate_index"]),
        )
        if joint_replay.get("status") not in {"OPTIMAL", "FEASIBLE"}:
            raise RuntimeError(
                "E063 directional zero did not replay in joint signature model: "
                f"candidate={spec['candidate_index']} joint={joint_replay}"
            )
    return {
        "candidate_index": int(spec["candidate_index"]),
        "source_instance_id": str(spec["source_instance_id"]),
        "facility_type": str(spec["facility_type"]),
        "operation_type": str(spec["operation_type"]),
        "current_pose_idx": int(spec["current_pose_idx"]),
        "replacement_pose_idx": int(spec["replacement_pose_idx"]),
        "replacement_pose_id": str(spec["replacement_pose_id"]),
        "same_footprint": bool(spec["same_footprint"]),
        "selection_reasons": list(spec["selection_reasons"]),
        "alias_count_including_representative": int(
            spec["alias_count_including_representative"]
        ),
        "occupied_symmetric_difference": int(
            spec["occupied_symmetric_difference"]
        ),
        "directional": json_safe(directional),
        "joint_replay": json_safe(joint_replay),
    }


def chunk_path(index: int) -> Path:
    return CHUNK_DIR / f"CHUNK_{index:03d}.json"


def scan_candidates(
    *,
    e061: Any,
    e062: Any,
    context: Mapping[str, Any],
    manifest: Mapping[str, Any],
    runner_sha256: str,
) -> list[dict[str, Any]]:
    candidates = [dict(row) for row in manifest["candidates"]]
    all_records: list[dict[str, Any]] = []
    for chunk_index, start in enumerate(range(0, len(candidates), CHUNK_SIZE), 1):
        specs = candidates[start : start + CHUNK_SIZE]
        path = chunk_path(chunk_index)
        spec_digest = stable_digest(specs)
        if path.exists():
            payload = load_json(path)
            if str(payload.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E063 chunk runner: {path}")
            if str(payload.get("spec_digest")) != spec_digest:
                raise RuntimeError(f"stale E063 chunk specs: {path}")
        else:
            records: list[dict[str, Any]] = []
            started = time.monotonic()
            for local_index, spec in enumerate(specs, 1):
                record = evaluate_candidate(
                    e061=e061,
                    e062=e062,
                    context=context,
                    spec=spec,
                )
                records.append(record)
                if (
                    local_index % 20 == 0
                    or record["directional"].get("objective") == 0
                ):
                    print(
                        json.dumps(
                            {
                                "event": "E063_PROGRESS",
                                "chunk": chunk_index,
                                "candidate": start + local_index,
                                "candidate_total": len(candidates),
                                "status": record["directional"].get("status"),
                                "objective": record["directional"].get("objective"),
                                "at_utc": utc_now(),
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
            payload = {
                "schema": "zmd_zero_condition_e063_chunk_v1",
                "created_at_utc": utc_now(),
                "authority": "research_only_noncertified",
                "runner_sha256": runner_sha256,
                "chunk_index": chunk_index,
                "candidate_start_index": start + 1,
                "candidate_count": len(specs),
                "spec_digest": spec_digest,
                "elapsed_seconds": time.monotonic() - started,
                "records": records,
                "ledger_effect": "none",
            }
            dump_exclusive(path, payload)
        all_records.extend(payload["records"])
    if len(all_records) != len(candidates):
        raise RuntimeError(
            f"E063 record coverage drift: {len(all_records)} != {len(candidates)}"
        )
    return all_records


def materialize_candidates(
    *,
    e061: Any,
    context: Mapping[str, Any],
    manifest: Mapping[str, Any],
    zero_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    spec_by_index = {
        int(row["candidate_index"]): row for row in manifest["candidates"]
    }
    selected = sorted(
        zero_records,
        key=lambda row: (
            int(row["occupied_symmetric_difference"]),
            str(row["facility_type"]),
            int(row["replacement_pose_idx"]),
            str(row["source_instance_id"]),
        ),
    )[:MAX_MATERIALIZED_CANDIDATES]
    output: list[dict[str, Any]] = []
    for rank, record in enumerate(selected, 1):
        spec = spec_by_index[int(record["candidate_index"])]
        alternative = reconstruct_candidate(
            e061=e061,
            parent_base=context["parent_base"],
            spec=spec,
        )
        path = OUT / f"PAIR_CANDIDATE_{rank:02d}.json"
        payload = {
            "schema": "zmd_zero_condition_e063_pair_candidate_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "rank": rank,
            "parent_pole": context["parent_alternative"],
            "second_change": spec,
            "signature_result": record,
            "solution": alternative["solution"],
            "ledger_effect": "none",
        }
        dump_exclusive(path, payload)
        output.append(
            {
                "rank": rank,
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
                "candidate_index": int(record["candidate_index"]),
                "source_instance_id": str(record["source_instance_id"]),
                "replacement_pose_idx": int(record["replacement_pose_idx"]),
                "occupied_symmetric_difference": int(
                    record["occupied_symmetric_difference"]
                ),
            }
        )
    return output


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e061 = import_module("zmd_e063_e061", E061_RUNNER)
    e062 = import_module("zmd_e063_e062", E062_RUNNER)
    context = parent_context(e061, e062)
    context["mode_map"] = e061.modes_by_footprint(
        context["base"]["inputs"]["pools"]
    )
    context["fixed_descriptors"] = e061.raw_descriptors(
        bodies=e061.body_rows(
            context["solution"],
            context["base"]["inputs"]["pools"],
            context["base"]["e014"],
        ),
        mode_map=context["mode_map"],
        pools=context["base"]["inputs"]["pools"],
        enumerate_patterns=context["base"]["enumerate_patterns"],
    )
    selection = component_boundary_selection(context)
    manifest = build_candidate_manifest(
        e061=e061,
        context=context,
        selection=selection,
        runner_sha256=runner_sha256,
    )
    records = scan_candidates(
        e061=e061,
        e062=e062,
        context=context,
        manifest=manifest,
        runner_sha256=runner_sha256,
    )
    status_counts = Counter(str(row["directional"]["status"]) for row in records)
    objective_distribution: Counter[int] = Counter()
    zero_records: list[dict[str, Any]] = []
    one_records: list[dict[str, Any]] = []
    nonterminal: list[dict[str, Any]] = []
    for row in records:
        objective = row["directional"].get("objective")
        if objective is not None:
            objective_distribution[int(objective)] += 1
            if int(objective) == 0:
                zero_records.append(row)
            elif int(objective) == 1:
                one_records.append(row)
        elif row["directional"]["status"] not in {
            "INFEASIBLE",
            "STRUCTURAL_EMPTY",
        }:
            nonterminal.append(row)
    materialized = materialize_candidates(
        e061=e061,
        context=context,
        manifest=manifest,
        zero_records=zero_records,
    )
    if nonterminal:
        verdict = "POLE_CONDITIONED_SECOND_OBJECT_NONTERMINAL"
        decision = "CONTINUE_NONTERMINAL_PAIR_CANDIDATES"
    elif zero_records:
        verdict = "POLE_CONDITIONED_TWO_ZERO_SIGNATURE_CANDIDATES"
        decision = "VALIDATE_TOP_PAIR_IN_FULL_CONDITIONAL_BINDING"
    elif one_records:
        verdict = "POLE_CONDITIONED_SECOND_OBJECT_SATURATES_AT_ONE"
        decision = "DERIVE_THIRD_RELATION_OR_SWITCH_NEAR_MISS_PARENT"
    else:
        verdict = "POLE_CONDITIONED_CAUSAL_SUBSET_WORSENS"
        decision = "SWITCH_TO_DISTINCT_SIX4_NEAR_MISS_PARENT"
    return {
        "schema": "zmd_zero_condition_e063_pole_conditioned_second_object_frontier_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "parent_pole": context["parent_alternative"],
        "parent_calibration": context["calibration"],
        "parent_directional_face": context["directional_face"],
        "selection": selection,
        "manifest_path": str(MANIFEST_PATH.relative_to(ROOT)),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
        "candidate_count": int(manifest["distinct_candidate_count"]),
        "status_counts": dict(sorted(status_counts.items())),
        "objective_distribution": {
            str(key): value for key, value in sorted(objective_distribution.items())
        },
        "zero_candidate_count": len(zero_records),
        "one_candidate_count": len(one_records),
        "nonterminal_count": len(nonterminal),
        "zero_candidates": zero_records,
        "best_one_candidates": sorted(
            one_records,
            key=lambda row: (
                int(row["occupied_symmetric_difference"]),
                str(row["facility_type"]),
                int(row["replacement_pose_idx"]),
            ),
        )[:50],
        "nonterminal_candidates": nonterminal,
        "materialized_candidates": materialized,
        "decision": decision,
        "truth_boundary": (
            "E055 first-zero state plus fixed pole pose 3725->3794 and exactly one "
            "additional pose change chosen from multi-component boundary owners "
            "of every unmatched component on the complete directional optimum face, "
            "all current 6x4 bodies, or the protocol core; "
            "candidate-specific corrected target-signature relaxation only."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E063 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "candidates": result["candidate_count"],
                    "distribution": result["objective_distribution"],
                    "zero": result["zero_candidate_count"],
                    "one": result["one_candidate_count"],
                    "nonterminal": result["nonterminal_count"],
                    "decision": result["decision"],
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e063_pole_conditioned_second_object_frontier_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not FAILURE_PATH.exists():
            dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
