#!/usr/bin/env python3
"""E072: component-owner bridge atlas for E071 feasible half-signatures."""

from __future__ import annotations

from collections import defaultdict, deque
import datetime
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E072_half_signature_component_bridges/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
ATLAS_PATH = OUT / "BRIDGE_ATLAS.json"

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"
E061_RUNNER = (
    EXPERIMENT_ROOT / "E061_all_one_object_signature_frontier/run_e061.py"
)
E062_RUNNER = EXPERIMENT_ROOT / "E062_one_object_tradeoff_atlas/run_e062.py"
E063_RUNNER = (
    EXPERIMENT_ROOT / "E063_pole_conditioned_second_object_frontier/run_e063.py"
)
E069_RUNNER = EXPERIMENT_ROOT / "E069_six4_near_miss_complete_face/run_e069.py"
E071_RUNNER = (
    EXPERIMENT_ROOT / "E071_dual_signature_destination_atlas/run_e071.py"
)

E069_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001/RESULT.json"
)
E071_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E071_dual_signature_destination_atlas/run-001/RESULT.json"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONPYCACHEPREFIX": "/tmp/zmd_e072_source_cache_v1",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "298000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E061_RUNNER: "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
    E062_RUNNER: "91770f3ba9a96a3c79bd95c42a4e40b9a540ab537e97079b02f7c57c6fedb67e",
    E063_RUNNER: "e925b4470ecb002701b262c5d8bcfbe88177eb8da373502354174f178f39caf9",
    E069_RESULT: "38cd4ec548bd18ad70b3549e04d225a4e4a226489bd8ed111c9f72554640769f",
}

FILLING = "filling_capsule"
FINE = "fine_buckwheat_powder"
QIAOYU = "qiaoyu_capsule"
TARGET_FINE_COMPONENT = 36
TARGET_QIAOYU_COMPONENT = 29
EXPECTED_ACTUAL_DESTINATION = 24
MAX_PATHS_PER_RELATION = 64
MAX_RANKED_PROPOSALS = 100

Node = tuple[str, int | str]


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def audit_module(module: Any, expected_path: Path) -> dict[str, Any]:
    expected = expected_path.resolve()
    functions: list[dict[str, str]] = []
    foreign: list[dict[str, str]] = []
    for name, value in sorted(vars(module).items()):
        if not inspect.isfunction(value) or value.__module__ != module.__name__:
            continue
        actual = Path(value.__code__.co_filename).resolve()
        record = {"name": str(name), "code_filename": str(actual)}
        functions.append(record)
        if actual != expected:
            foreign.append(record)
    if foreign:
        raise RuntimeError(f"foreign functions loaded for {expected_path}: {foreign[:10]}")
    return {
        "module": str(module.__name__),
        "source": str(expected_path.relative_to(ROOT)),
        "source_sha256": sha256_file(expected_path),
        "function_count": len(functions),
        "foreign_function_count": 0,
    }


def audit_nested_modules(prefixes: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, module in sorted(sys.modules.items()):
        if module is None or not any(name.startswith(prefix) for prefix in prefixes):
            continue
        file_value = getattr(module, "__file__", None)
        if not isinstance(file_value, str):
            continue
        path = Path(file_value).resolve()
        source = (
            Path(importlib.util.source_from_cache(str(path))).resolve()
            if path.suffix == ".pyc"
            else path
        )
        rows.append(audit_module(module, source))
    return rows


def verify_identity() -> dict[str, Any]:
    if Path.cwd().resolve() != ROOT.resolve():
        raise RuntimeError(f"run E072 from research root: {Path.cwd()}")
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E072 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"E072 requires a clean tracked worktree: {tracked_status}")
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
            f"environment mismatch: {mismatches}; unexpected={unexpected_exact}"
        )
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift: {path}: {actual} != {expected}")

    before = sha256_file(E071_RESULT)
    e071 = load_json(E071_RESULT)
    after = sha256_file(E071_RESULT)
    if before != after:
        raise RuntimeError("E072 E071 result changed while loading")
    if e071.get("verdict") != "DUAL_SIGNATURE_DESTINATION_COMPATIBILITY_IDENTIFIED":
        raise RuntimeError(f"E072 E071 verdict drift: {e071.get('verdict')}")
    current_runner = sha256_file(E071_RUNNER)
    if str(e071["identity"]["runner_sha256"]) != current_runner:
        raise RuntimeError("E072 current E071 runner differs from frozen execution")
    atlas_path = ROOT / str(e071["destination_atlas_path"])
    if not atlas_path.is_file():
        raise FileNotFoundError(atlas_path)
    atlas_sha = sha256_file(atlas_path)
    if atlas_sha != str(e071["destination_atlas_sha256"]):
        raise RuntimeError("E072 E071 destination atlas hash mismatch")
    if (
        bool(e071["actual_destination_feasible"])
        or str(e071["forced_actual_result"]["status"]) != "INFEASIBLE"
        or int(e071["nonterminal_count"]) != 0
    ):
        raise RuntimeError("E072 E071 terminal destination result drift")
    half = e071["real_filling_inventory"][
        "feasible_half_signature_destinations"
    ]
    if not half:
        raise RuntimeError("E072 trigger requires at least one feasible half-signature")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "e071_result_sha256": before,
        "e071_runner_sha256": current_runner,
        "e071_atlas_path": str(atlas_path.relative_to(ROOT)),
        "e071_atlas_sha256": atlas_sha,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": tracked_status,
    }


def terminal_cells_for_option(
    *,
    context: Mapping[str, Any],
    destination: int,
    option: Mapping[str, Any],
) -> list[dict[str, Any]]:
    pose_idx = int(option["pose_idx"])
    expected_fine = tuple(int(value) for value in option["fine_input_components"])
    expected_qiaoyu = tuple(
        int(value) for value in option["qiaoyu_output_components"]
    )
    pose = context["base"]["inputs"]["pools"]["manufacturing_6x4"][pose_idx]
    raw_patterns, _cache = context["base"]["enumerate_patterns"](FILLING, pose)
    routing_context = context["routing_context"]
    free_cells = set(routing_context.component_by_cell)
    matches: dict[str, dict[str, Any]] = {}
    for pattern_index, pattern in enumerate(raw_patterns):
        active = tuple(
            sorted(
                (int(port["x"]), int(port["y"]))
                for port in pattern["active_ports"]
            )
        )
        if any(cell not in free_cells for cell in active):
            continue
        fine_cells = tuple(
            sorted(
                (int(port["x"]), int(port["y"]))
                for port in pattern["input_ports"]
                if str(port["commodity"]) == FINE
            )
        )
        qiaoyu_cells = tuple(
            sorted(
                (int(port["x"]), int(port["y"]))
                for port in pattern["output_ports"]
                if str(port["commodity"]) == QIAOYU
            )
        )
        fine_components = tuple(
            sorted(
                {
                    int(routing_context.component_by_cell[cell])
                    for cell in fine_cells
                }
            )
        )
        qiaoyu_components = tuple(
            sorted(
                {
                    int(routing_context.component_by_cell[cell])
                    for cell in qiaoyu_cells
                }
            )
        )
        if fine_components != expected_fine or qiaoyu_components != expected_qiaoyu:
            continue
        record = {
            "destination": int(destination),
            "pose_idx": pose_idx,
            "raw_pattern_index": int(pattern_index),
            "active_cells": [list(cell) for cell in active],
            "fine_input_cells": [list(cell) for cell in fine_cells],
            "fine_input_components": list(fine_components),
            "qiaoyu_output_cells": [list(cell) for cell in qiaoyu_cells],
            "qiaoyu_output_components": list(qiaoyu_components),
        }
        matches[stable_digest(record)] = record
    if not matches:
        raise RuntimeError(
            f"E072 could not recover terminal cells for destination {destination}: {option}"
        )
    return [matches[key] for key in sorted(matches)]


def owner_component_graph(context: Mapping[str, Any]) -> dict[str, Any]:
    routing_context = context["routing_context"]
    base = context["base"]
    component_to_owners: dict[int, set[str]] = defaultdict(set)
    owner_to_components: dict[str, set[int]] = defaultdict(set)
    owner_metadata: dict[str, dict[str, Any]] = {}
    for owner, row in sorted(context["solution"].items()):
        facility_type = str(row["facility_type"])
        pose_idx = int(row["pose_idx"])
        touched: set[int] = set()
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
                    touched.add(int(component))
        owner_metadata[str(owner)] = {
            "owner": str(owner),
            "facility_type": facility_type,
            "operation_type": str(row.get("operation_type", "")),
            "pose_idx": pose_idx,
            "touched_components": sorted(touched),
        }
        for component in touched:
            component_to_owners[component].add(str(owner))
            owner_to_components[str(owner)].add(component)
    return {
        "component_to_owners": {
            str(component): sorted(owners)
            for component, owners in sorted(component_to_owners.items())
        },
        "owner_to_components": {
            owner: sorted(components)
            for owner, components in sorted(owner_to_components.items())
        },
        "owner_metadata": owner_metadata,
        "graph_digest": stable_digest(
            {
                "component_to_owners": {
                    str(component): sorted(owners)
                    for component, owners in sorted(component_to_owners.items())
                },
                "owner_to_components": {
                    owner: sorted(components)
                    for owner, components in sorted(owner_to_components.items())
                },
            }
        ),
    }


def neighbors(graph: Mapping[str, Any], node: Node) -> Iterable[Node]:
    kind, value = node
    if kind == "component":
        for owner in graph["component_to_owners"].get(str(int(value)), []):
            yield ("owner", str(owner))
    elif kind == "owner":
        for component in graph["owner_to_components"].get(str(value), []):
            yield ("component", int(component))
    else:
        raise ValueError(node)


def shortest_paths(
    graph: Mapping[str, Any],
    *,
    start_component: int,
    target_component: int,
) -> dict[str, Any]:
    start: Node = ("component", int(start_component))
    target: Node = ("component", int(target_component))
    if start == target:
        return {
            "distance_edges": 0,
            "owner_count": 0,
            "path_count": 1,
            "paths": [{"nodes": [["component", int(start_component)]], "owners": []}],
        }
    distance: dict[Node, int] = {start: 0}
    queue: deque[Node] = deque([start])
    while queue:
        node = queue.popleft()
        for nxt in sorted(neighbors(graph, node), key=lambda item: (item[0], str(item[1]))):
            if nxt in distance:
                continue
            distance[nxt] = distance[node] + 1
            queue.append(nxt)
    if target not in distance:
        return {
            "distance_edges": None,
            "owner_count": None,
            "path_count": 0,
            "paths": [],
        }

    paths: list[list[Node]] = []

    def visit(node: Node, path: list[Node]) -> None:
        if len(paths) >= MAX_PATHS_PER_RELATION:
            return
        if node == target:
            paths.append(list(path))
            return
        for nxt in sorted(neighbors(graph, node), key=lambda item: (item[0], str(item[1]))):
            if distance.get(nxt) != distance[node] + 1:
                continue
            if distance[nxt] > distance[target]:
                continue
            visit(nxt, [*path, nxt])

    visit(start, [start])
    payload_paths = [
        {
            "nodes": [[kind, value] for kind, value in path],
            "owners": [str(value) for kind, value in path if kind == "owner"],
            "components": [int(value) for kind, value in path if kind == "component"],
        }
        for path in paths
    ]
    return {
        "distance_edges": int(distance[target]),
        "owner_count": sum(kind == "owner" for kind, _value in paths[0]),
        "path_count": len(payload_paths),
        "path_enumeration_capped": len(paths) >= MAX_PATHS_PER_RELATION,
        "paths": payload_paths,
    }


def build_relations(
    *,
    e061: Any,
    context: Mapping[str, Any],
    e071_result: Mapping[str, Any],
    graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    bodies = e061.body_rows(
        context["solution"],
        context["base"]["inputs"]["pools"],
        context["base"]["e014"],
    )
    inventory = e071_result["real_filling_inventory"]
    feasible_half = set(
        int(value) for value in inventory["feasible_half_signature_destinations"]
    )
    relations: list[dict[str, Any]] = []
    for destination in sorted(feasible_half):
        row = inventory["destinations"][str(destination)]
        body = bodies[destination]
        destination_owner = str(body["source_instance_id"])
        for category in ("qiaoyu_29_half", "fine_36_half", "exact_dual"):
            for option in row["categories"][category]:
                terminal_variants = terminal_cells_for_option(
                    context=context,
                    destination=destination,
                    option=option,
                )
                fine_components = [
                    int(value) for value in option["fine_input_components"]
                ]
                qiaoyu_components = [
                    int(value) for value in option["qiaoyu_output_components"]
                ]
                if category == "qiaoyu_29_half":
                    starts = [
                        value
                        for value in fine_components
                        if value != TARGET_FINE_COMPONENT
                    ]
                    target = TARGET_FINE_COMPONENT
                    relation_kind = "merge_fine_input_to_36"
                elif category == "fine_36_half":
                    starts = [
                        value
                        for value in qiaoyu_components
                        if value != TARGET_QIAOYU_COMPONENT
                    ]
                    target = TARGET_QIAOYU_COMPONENT
                    relation_kind = "merge_qiaoyu_output_to_29"
                else:
                    starts = []
                    target = TARGET_FINE_COMPONENT
                    relation_kind = "already_exact_dual"
                if category == "exact_dual":
                    path_payload = {
                        "distance_edges": 0,
                        "owner_count": 0,
                        "path_count": 1,
                        "paths": [],
                    }
                    starts = [TARGET_FINE_COMPONENT]
                else:
                    if not starts:
                        raise RuntimeError(
                            f"E072 half-signature lacks a mismatched component: {row}/{option}"
                        )
                    if len(starts) != 1:
                        raise RuntimeError(
                            f"E072 expected singleton half component: {starts}"
                        )
                    path_payload = shortest_paths(
                        graph,
                        start_component=starts[0],
                        target_component=target,
                    )
                for path in path_payload.get("paths", []) or [None]:
                    owners = [] if path is None else list(path["owners"])
                    owner_records = [
                        graph["owner_metadata"][owner] for owner in owners
                    ]
                    relations.append(
                        {
                            "destination": int(destination),
                            "destination_owner": destination_owner,
                            "source_instance_id": str(row["source_instance_id"]),
                            "current_operation": str(row["current_operation"]),
                            "current_pose_idx": int(row["current_pose_idx"]),
                            "half_signature_category": category,
                            "relation_kind": relation_kind,
                            "option": option,
                            "terminal_variants": terminal_variants,
                            "start_component": int(starts[0]),
                            "target_component": int(target),
                            "distance_edges": path_payload["distance_edges"],
                            "owner_count": path_payload["owner_count"],
                            "path_count": path_payload["path_count"],
                            "path_enumeration_capped": path_payload.get(
                                "path_enumeration_capped", False
                            ),
                            "path_nodes": [] if path is None else path["nodes"],
                            "path_owners": owners,
                            "path_owner_records": owner_records,
                            "moves_destination_body": destination_owner in owners,
                        }
                    )
    return relations


def run() -> dict[str, Any]:
    identity = verify_identity()
    e061 = import_module("zmd_e072_e061", E061_RUNNER)
    e062 = import_module("zmd_e072_e062", E062_RUNNER)
    e063 = import_module("zmd_e072_e063", E063_RUNNER)
    e069 = import_module("zmd_e072_e069", E069_RUNNER)
    e071 = import_module("zmd_e072_e071", E071_RUNNER)
    direct_origins = [
        audit_module(e061, E061_RUNNER),
        audit_module(e062, E062_RUNNER),
        audit_module(e063, E063_RUNNER),
        audit_module(e069, E069_RUNNER),
        audit_module(e071, E071_RUNNER),
    ]
    context = e069.reconstruct_parent(e061, e062, e063)
    nested_origins = audit_nested_modules(
        (
            "zmd_e072_",
            "zmd_e061_",
            "zmd_e062_",
            "zmd_e063_",
            "zmd_e069_",
            "zmd_e071_",
        )
    )
    e071_result = load_json(E071_RESULT)
    graph = owner_component_graph(context)
    relations = build_relations(
        e061=e061,
        context=context,
        e071_result=e071_result,
        graph=graph,
    )
    preserving = [row for row in relations if not row["moves_destination_body"]]
    direct_preserving = [
        row
        for row in preserving
        if row["owner_count"] == 1
    ]
    ranked = sorted(
        relations,
        key=lambda row: (
            row["owner_count"] is None,
            10**9 if row["owner_count"] is None else int(row["owner_count"]),
            bool(row["moves_destination_body"]),
            0 if row["half_signature_category"] == "qiaoyu_29_half" else 1,
            int(row["destination"]),
            int(row["option"]["pose_idx"]),
            tuple(row["path_owners"]),
        ),
    )
    atlas = {
        "schema": "zmd_zero_condition_e072_half_signature_component_bridges_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "target": {
            "fine_input_component": TARGET_FINE_COMPONENT,
            "qiaoyu_output_component": TARGET_QIAOYU_COMPONENT,
        },
        "e071_feasible_destinations": e071_result["feasible_destinations"],
        "e071_feasible_half_destinations": e071_result[
            "real_filling_inventory"
        ]["feasible_half_signature_destinations"],
        "graph": graph,
        "relation_count": len(relations),
        "relations": relations,
        "ledger_effect": "none",
    }
    dump_exclusive(ATLAS_PATH, atlas)

    if not relations:
        verdict = "NO_REAL_HALF_SIGNATURE_ON_FEASIBLE_DESTINATION"
        decision = "SEARCH_NEW_DUAL_MODE_DIRECTLY"
    elif direct_preserving:
        verdict = "DIRECT_OWNER_BRIDGES_PRESERVE_HALF_SIGNATURE"
        decision = "TEST_DIRECT_OWNER_BRIDGES_IN_SIGNATURE_CONSUMER"
    elif preserving:
        verdict = "BOUNDED_MULTI_OWNER_BRIDGES_IDENTIFIED"
        decision = "BUILD_SHORTEST_SIMULTANEOUS_BRIDGE_CONTEXT"
    else:
        verdict = "ALL_BRIDGES_MOVE_HALF_SIGNATURE_BODY"
        decision = "SWITCH_TO_BODY_OR_MODE_TRANSPORT"
    owner_count_distribution: dict[str, int] = defaultdict(int)
    for row in relations:
        key = "NONE" if row["owner_count"] is None else str(row["owner_count"])
        owner_count_distribution[key] += 1
    return {
        "schema": "zmd_zero_condition_e072_half_signature_component_bridges_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "module_origin_audit": {
            "direct": direct_origins,
            "nested": nested_origins,
        },
        "target": atlas["target"],
        "relation_count": len(relations),
        "owner_count_distribution": dict(sorted(owner_count_distribution.items())),
        "destination_preserving_relation_count": len(preserving),
        "direct_destination_preserving_count": len(direct_preserving),
        "selected_proposals": ranked[:MAX_RANKED_PROPOSALS],
        "bridge_atlas_path": str(ATLAS_PATH.relative_to(ROOT)),
        "bridge_atlas_sha256": sha256_file(ATLAS_PATH),
        "decision": decision,
        "truth_boundary": (
            "E069 fixed component partition and E071 real filling half-signatures "
            "on synthetic-feasible destinations; bipartite component-owner paths "
            "are causal proposals only."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E072 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        best = result["selected_proposals"][0] if result["selected_proposals"] else None
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "relations": result["relation_count"],
                    "owner_count_distribution": result[
                        "owner_count_distribution"
                    ],
                    "preserving": result["destination_preserving_relation_count"],
                    "direct_preserving": result[
                        "direct_destination_preserving_count"
                    ],
                    "best": (
                        None
                        if best is None
                        else {
                            "destination": best["destination"],
                            "category": best["half_signature_category"],
                            "start_component": best["start_component"],
                            "target_component": best["target_component"],
                            "owners": best["path_owners"],
                            "moves_destination_body": best[
                                "moves_destination_body"
                            ],
                        }
                    ),
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
            "schema": "zmd_zero_condition_e072_half_signature_component_bridges_failure_v1",
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
