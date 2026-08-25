#!/usr/bin/env python3
"""E005: quantify free-component morphology and audit the existing F4 path.

Research-only. The script reads two fixed layouts and pinned source code. It does
not attach a cut, modify the solver, update U/L, or grant certification.
"""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E005_component_morphology_and_f4_gap/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

A1_LAYOUT = (
    HISTORY_ROOT
    / ".artifacts/lowerbound_ladder_20260824/phaseA1_noghost_master/MASTER_LAYOUT_A1.json"
)
E001_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E001_pocket_cut_replay/run-002/REPLACEMENT_LAYOUT.json"
)
E004_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E004_component_mismatch_atlas/run-001/RESULT.json"
)

EXPECTED_HASHES: dict[Path, str] = {
    A1_LAYOUT: "9e545fdf29e55978a8237fc4c1f1183f9643abfe04b6e8d2a8a5319c31c4df83",
    E001_LAYOUT: "752fb1706dba76ded658775750eaa6ac9f6816500e678a07ad18c3fce7d69f97",
    E004_RESULT: "490349a2778c46f7d209e199d7da34b73649d0ddcb5095a837731423a8460a69",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    ROOT / "src/models/master_model.py": "d1ada57bc6dcef1818341b26dfd482fb7c1623d106734b8f1a49061c2e7c1371",
    ROOT / "src/models/routing_binding_context.py": "9f9e4d058a561ca570f3c4fd7f5d5095a1bcff558e0608408b0760fc7609f7c2",
    ROOT / "src/search/benders_loop.py": "461fc6875ca16781c1d0d81720aee98747a3d2c984a4c1bf1afda4f384af1bc3",
    ROOT / "src/cuts/oracles/component_reach_oracle.py": "0828648c56d385fe40baa60be62034a77caf717cbcd78e4a557185d98231cb7a",
    ROOT / "src/cuts/families/component_reach.py": "e1ca76d1606c8b761e09126288edf4c5e380c35b87d0d281ffc641b62fcc28f2",
    ROOT / "src/cuts/typed_platform.py": "cce881457c63647dbba58750e1c4884351a31987057ac72b9cd0aeecaf44b45b",
    ROOT / "src/cuts/lifecycle.py": "9b944572c3bc787317a2e9bfaaf4e3ce472ba8fd953269772b24535bbef1ac1a",
    ROOT
    / "docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md": "55e95f19f9a28959e5753105c92403238bfbaf50f8bbfcec55d169ae8de856af",
}

GRID_W = 70
GRID_H = 70


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


def stable_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def dump_exclusive(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            json_safe(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def verify_identity() -> dict[str, Any]:
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"identity drift for {path}: {actual} != {expected}")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def reconstruct_solution(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    placements = payload.get("placements")
    if not isinstance(placements, list):
        raise RuntimeError(f"layout lacks placements: {path}")
    solution = {
        str(record["instance_id"]): dict(record)
        for record in placements
        if isinstance(record, Mapping)
    }
    if len(solution) != len(placements):
        raise RuntimeError(f"layout has duplicate/invalid instance ids: {path}")
    mandatory = sum(bool(row.get("is_mandatory")) for row in solution.values())
    if mandatory != 266:
        raise RuntimeError(f"mandatory count drift in {path}: {mandatory}")
    return solution


def translated_shape(cells: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    material = set(cells)
    min_x = min(x for x, _y in material)
    min_y = min(y for _x, y in material)
    return tuple(sorted((x - min_x, y - min_y) for x, y in material))


def dihedral_shape(cells: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    base = translated_shape(cells)

    def normalize(points: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
        points_set = set(points)
        min_x = min(x for x, _y in points_set)
        min_y = min(y for _x, y in points_set)
        return tuple(sorted((x - min_x, y - min_y) for x, y in points_set))

    variants: list[tuple[tuple[int, int], ...]] = []
    current = set(base)
    for _index in range(4):
        variants.append(normalize(current))
        variants.append(normalize({(-x, y) for x, y in current}))
        current = {(-y, x) for x, y in current}
    return min(variants)


def free_adjacency_score(free_cells: set[tuple[int, int]]) -> int:
    return sum(
        int((x + 1, y) in free_cells) + int((x, y + 1) in free_cells)
        for x, y in free_cells
    )


def component_records(
    *,
    context: Any,
    solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[int, dict[str, Any]]:
    records: dict[int, dict[str, Any]] = {}
    for raw_component, raw_cells in context.cells_by_component.items():
        component = int(raw_component)
        cells = set(raw_cells)
        min_x = min(x for x, _y in cells)
        min_y = min(y for _x, y in cells)
        translated = translated_shape(cells)
        dihedral = dihedral_shape(cells)
        ys = {y for _x, y in cells}
        xs = {x for x, _y in cells}

        owner_edges: Counter[str] = Counter()
        boundary_cell_semantics: list[tuple[int, int, str, str]] = []
        seen_boundary_cells: set[tuple[int, int, str]] = set()
        for x, y in cells:
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                owner = context.occupied_owner_by_cell.get((nx, ny))
                if owner is None:
                    continue
                owner_id = str(owner)
                owner_edges[owner_id] += 1
                record = solution[owner_id]
                boundary_key = (nx, ny, owner_id)
                if boundary_key not in seen_boundary_cells:
                    seen_boundary_cells.add(boundary_key)
                    boundary_cell_semantics.append(
                        (
                            nx - min_x,
                            ny - min_y,
                            str(record.get("facility_type", "")),
                            str(record.get("operation_type", "")),
                        )
                    )

        owner_semantics: list[tuple[Any, ...]] = []
        power_pole_owner_count = 0
        for owner_id, edge_count in sorted(owner_edges.items()):
            record = solution[owner_id]
            facility_type = str(record.get("facility_type", ""))
            operation_type = str(record.get("operation_type", ""))
            pose_idx = int(record.get("pose_idx", -1))
            pool = pools.get(facility_type, [])
            if not (0 <= pose_idx < len(pool)):
                raise RuntimeError(f"pose index drift for boundary owner {owner_id}")
            pose = pool[pose_idx]
            params = dict(pose.get("pose_params", {}) or {})
            anchor = dict(record.get("anchor", {}) or {})
            if facility_type == "power_pole":
                power_pole_owner_count += 1
            owner_semantics.append(
                (
                    facility_type,
                    operation_type,
                    int(anchor.get("x", 0)) - min_x,
                    int(anchor.get("y", 0)) - min_y,
                    str(params.get("orientation", "")),
                    str(params.get("port_mode", "")),
                    int(edge_count),
                )
            )

        shape_signature = stable_digest(translated)
        dihedral_signature = stable_digest(dihedral)
        cell_semantic_signature = stable_digest(
            [translated, sorted(boundary_cell_semantics)]
        )
        owner_semantic_signature = stable_digest(
            [translated, sorted(owner_semantics)]
        )
        records[component] = {
            "component_id": component,
            "cells": cells,
            "cell_set_digest": stable_digest(sorted(cells)),
            "size": len(cells),
            "bbox": {
                "width": max(xs) - min(xs) + 1,
                "height": max(ys) - min(ys) + 1,
            },
            "is_one_cell_line": len(xs) == 1 or len(ys) == 1,
            "line_orientation": (
                "vertical"
                if len(xs) == 1 and len(ys) > 1
                else "horizontal"
                if len(ys) == 1 and len(xs) > 1
                else "singleton"
                if len(cells) == 1
                else None
            ),
            "shape_signature": shape_signature,
            "dihedral_shape_signature": dihedral_signature,
            "cell_semantic_signature": cell_semantic_signature,
            "owner_semantic_signature": owner_semantic_signature,
            "boundary_owner_count": len(owner_edges),
            "power_pole_boundary_owner_count": power_pole_owner_count,
            "boundary_owner_semantics": sorted(owner_semantics),
        }
    return records


def family_summary(
    *,
    records: Mapping[int, Mapping[str, Any]],
    weighted_components: Sequence[int],
    signature_key: str,
) -> dict[str, Any]:
    counts = Counter(str(records[int(component)][signature_key]) for component in weighted_components)
    total = len(weighted_components)
    top = [
        {"signature": signature, "observations": count}
        for signature, count in counts.most_common(20)
    ]
    return {
        "observation_count": total,
        "family_count": len(counts),
        "top_5_coverage": (
            sum(count for _signature, count in counts.most_common(5)) / total
            if total
            else 0.0
        ),
        "top_10_coverage": (
            sum(count for _signature, count in counts.most_common(10)) / total
            if total
            else 0.0
        ),
        "top_families": top,
    }


def morphology_audit() -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src.models.master_model import load_project_data
    from src.models.routing_binding_context import build_routing_binding_context

    _instances, pools, _rules = load_project_data(
        HISTORY_ROOT,
        solve_mode="certified_exact",
    )
    a1_solution = reconstruct_solution(A1_LAYOUT)
    e001_solution = reconstruct_solution(E001_LAYOUT)
    a1_context = build_routing_binding_context(
        a1_solution,
        pools,
        GRID_W,
        GRID_H,
    )
    e001_context = build_routing_binding_context(
        e001_solution,
        pools,
        GRID_W,
        GRID_H,
    )
    a1_records = component_records(
        context=a1_context,
        solution=a1_solution,
        pools=pools,
    )
    e001_records = component_records(
        context=e001_context,
        solution=e001_solution,
        pools=pools,
    )

    a1_by_cells = {
        frozenset(record["cells"]): component for component, record in a1_records.items()
    }
    e001_by_cells = {
        frozenset(record["cells"]): component for component, record in e001_records.items()
    }
    persistent_sets = set(a1_by_cells) & set(e001_by_cells)
    persistence_rows: list[dict[str, Any]] = []
    for cell_set in sorted(persistent_sets, key=lambda value: (len(value), sorted(value))):
        a1_component = a1_by_cells[cell_set]
        e001_component = e001_by_cells[cell_set]
        persistence_rows.append(
            {
                "a1_component": a1_component,
                "e001_component": e001_component,
                "size": len(cell_set),
                "shape_same": (
                    a1_records[a1_component]["shape_signature"]
                    == e001_records[e001_component]["shape_signature"]
                ),
                "owner_semantic_same": (
                    a1_records[a1_component]["owner_semantic_signature"]
                    == e001_records[e001_component]["owner_semantic_signature"]
                ),
            }
        )

    e004 = load_json(E004_RESULT)
    mismatch_observations: list[int] = []
    mismatch_commodities_by_component: dict[int, set[str]] = defaultdict(set)
    for row in e004["commodity_results"]:
        commodity = str(row["commodity"])
        for component in row["selected_components"]["mismatch_components"]:
            component_int = int(component)
            mismatch_observations.append(component_int)
            mismatch_commodities_by_component[component_int].add(commodity)
    if any(component not in e001_records for component in mismatch_observations):
        raise RuntimeError("E004 mismatch component id is absent from E001 geometry")

    all_e001 = sorted(e001_records)
    mismatch_unique = sorted(set(mismatch_observations))
    signature_keys = (
        "shape_signature",
        "dihedral_shape_signature",
        "cell_semantic_signature",
        "owner_semantic_signature",
    )
    all_family_summaries = {
        key: family_summary(
            records=e001_records,
            weighted_components=all_e001,
            signature_key=key,
        )
        for key in signature_keys
    }
    mismatch_family_summaries = {
        key: family_summary(
            records=e001_records,
            weighted_components=mismatch_observations,
            signature_key=key,
        )
        for key in signature_keys
    }

    most_shared = sorted(
        (
            {
                "component_id": component,
                "commodity_count": len(commodities),
                "commodities": sorted(commodities),
                "size": int(e001_records[component]["size"]),
                "shape_signature": str(e001_records[component]["shape_signature"]),
                "boundary_owner_count": int(
                    e001_records[component]["boundary_owner_count"]
                ),
            }
            for component, commodities in mismatch_commodities_by_component.items()
        ),
        key=lambda row: (-row["commodity_count"], -row["size"], row["component_id"]),
    )[:30]

    free_a1 = set(a1_context.component_by_cell)
    free_e001 = set(e001_context.component_by_cell)
    return {
        "a1": {
            "component_count": len(a1_records),
            "free_cell_count": len(free_a1),
            "free_adjacency_score": free_adjacency_score(free_a1),
            "shape_family_count": len(
                {record["shape_signature"] for record in a1_records.values()}
            ),
        },
        "e001": {
            "component_count": len(e001_records),
            "free_cell_count": len(free_e001),
            "free_adjacency_score": free_adjacency_score(free_e001),
            "one_cell_line_fraction": sum(
                bool(record["is_one_cell_line"]) for record in e001_records.values()
            )
            / len(e001_records),
            "small_component_le_20_fraction": sum(
                int(record["size"]) <= 20 for record in e001_records.values()
            )
            / len(e001_records),
            "power_pole_boundary_fraction": sum(
                int(record["power_pole_boundary_owner_count"]) > 0
                for record in e001_records.values()
            )
            / len(e001_records),
            "families": all_family_summaries,
        },
        "persistence": {
            "exact_cell_set_persistent_count": len(persistent_sets),
            "a1_only_component_count": len(set(a1_by_cells) - persistent_sets),
            "e001_only_component_count": len(set(e001_by_cells) - persistent_sets),
            "persistent_shape_same_count": sum(
                bool(row["shape_same"]) for row in persistence_rows
            ),
            "persistent_owner_semantic_same_count": sum(
                bool(row["owner_semantic_same"]) for row in persistence_rows
            ),
        },
        "e004_mismatch": {
            "observation_count": len(mismatch_observations),
            "unique_component_count": len(mismatch_unique),
            "one_cell_line_fraction": sum(
                bool(e001_records[component]["is_one_cell_line"])
                for component in mismatch_observations
            )
            / len(mismatch_observations),
            "small_component_le_20_fraction": sum(
                int(e001_records[component]["size"]) <= 20
                for component in mismatch_observations
            )
            / len(mismatch_observations),
            "power_pole_boundary_fraction": sum(
                int(e001_records[component]["power_pole_boundary_owner_count"]) > 0
                for component in mismatch_observations
            )
            / len(mismatch_observations),
            "families": mismatch_family_summaries,
            "most_shared_components": most_shared,
        },
        "component_records": {
            str(component): {
                key: value
                for key, value in record.items()
                if key not in {"cells", "boundary_owner_semantics"}
            }
            for component, record in sorted(e001_records.items())
        },
    }


def find_function(
    tree: ast.AST,
    *,
    name: str,
    class_name: str | None = None,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    if class_name is None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                return node
    else:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name:
                        return child
    raise RuntimeError(f"function not found: {class_name or '<module>'}.{name}")


def literal_strings(node: ast.AST) -> set[str]:
    return {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }


def called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            names.add(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            names.add(child.func.attr)
    return names


def find_bstate_call(node: ast.AST) -> ast.Call:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            if child.func.id == "BState":
                return child
    raise RuntimeError("production state builder contains no BState call")


def extract_frozenset_assignment(tree: ast.AST, target_name: str) -> set[str]:
    for node in ast.walk(tree):
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if not isinstance(target, ast.Name) or target.id != target_name or value is None:
            continue
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            if value.func.id == "frozenset" and value.args:
                return {
                    str(item.value)
                    for item in getattr(value.args[0], "elts", [])
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                }
    raise RuntimeError(f"frozenset assignment not found: {target_name}")


def typed_component_capability(tree: ast.AST) -> dict[str, Any]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values, strict=True):
            if not (
                isinstance(key, ast.Constant)
                and key.value == "component_reach"
                and isinstance(value, ast.Call)
            ):
                continue
            keywords = {item.arg: item.value for item in value.keywords if item.arg}

            def render(field: str) -> Any:
                raw = keywords.get(field)
                if isinstance(raw, ast.Constant):
                    return raw.value
                if isinstance(raw, ast.Attribute):
                    return raw.attr
                if raw is None:
                    return None
                return ast.dump(raw, include_attributes=False)

            return {
                "mode": render("mode"),
                "stage": render("stage"),
                "compiler_version": render("compiler_version"),
                "execution_path": render("execution_path"),
            }
    raise RuntimeError("component_reach capability not found")


def architecture_audit() -> dict[str, Any]:
    benders_path = ROOT / "src/search/benders_loop.py"
    oracle_path = ROOT / "src/cuts/oracles/component_reach_oracle.py"
    family_path = ROOT / "src/cuts/families/component_reach.py"
    typed_path = ROOT / "src/cuts/typed_platform.py"
    lifecycle_path = ROOT / "src/cuts/lifecycle.py"

    benders_source = benders_path.read_text(encoding="utf-8")
    oracle_source = oracle_path.read_text(encoding="utf-8")
    family_source = family_path.read_text(encoding="utf-8")
    typed_source = typed_path.read_text(encoding="utf-8")
    lifecycle_source = lifecycle_path.read_text(encoding="utf-8")
    benders_tree = ast.parse(benders_source)
    oracle_tree = ast.parse(oracle_source)
    family_tree = ast.parse(family_source)
    typed_tree = ast.parse(typed_source)
    lifecycle_tree = ast.parse(lifecycle_source)

    enabled_families = extract_frozenset_assignment(
        benders_tree,
        "_CUT_FRAMEWORK_ALL_FAMILIES",
    )
    state_builder = find_function(
        benders_tree,
        class_name="LBBDController",
        name="_build_cut_framework_state",
    )
    attach = find_function(
        benders_tree,
        class_name="LBBDController",
        name="_maybe_attach_framework_cuts",
    )
    bstate_call = find_bstate_call(state_builder)
    bstate_keywords = {item.arg: item.value for item in bstate_call.keywords if item.arg}
    cell_owner_node = bstate_keywords.get("cell_owner")
    state_cell_owner_is_empty = isinstance(cell_owner_node, ast.Dict) and not cell_owner_node.keys
    state_has_commodity_routes = "commodity_routes" in bstate_keywords
    state_oracles = literal_strings(bstate_keywords.get("available_oracle_versions", ast.Constant(None)))

    oracle_generate = find_function(
        oracle_tree,
        name="generate_component_reach_cuts",
    )
    oracle_try = find_function(oracle_tree, name="_try_generate_one")
    oracle_build = find_function(oracle_tree, name="_build_component_reach_cut")
    oracle_generate_source = ast.get_source_segment(oracle_source, oracle_generate) or ""
    oracle_try_source = ast.get_source_segment(oracle_source, oracle_try) or ""
    oracle_build_source = ast.get_source_segment(oracle_source, oracle_build) or ""

    scope_validator = find_function(family_tree, name="_validate_component_scope")
    scope_source = ast.get_source_segment(family_source, scope_validator) or ""
    recovery = find_function(
        lifecycle_tree,
        name="_resolve_live_master_domain_projection",
    )
    recovery_strings = literal_strings(recovery)
    capability = typed_component_capability(typed_tree)

    attach_calls = called_names(attach)
    mathematical_rule_present = all(
        token in oracle_source
        for token in ("bfs_component", "sink in src_component", "separator_cells")
    ) and "witness fail: src/sink now reachable" in family_source
    requires_routes = "if state.commodity_routes is None" in oracle_generate_source
    requires_ghost = "if state.ghost_rect is None" in oracle_generate_source
    fixed_pair_schema = all(
        token in oracle_try_source
        for token in ('route.get("src")', 'route.get("sink")')
    )
    empty_causal_payload = '"blocking_facilities": []' in oracle_build_source
    ghost_agnostic_rejected = "GHOST_AGNOSTIC" in scope_source and "unsound" in scope_source
    orchestrator_calls_f4 = "generate_component_reach_cuts" in attach_calls
    typed_compiler_present = capability["compiler_version"] is not None
    step8_recognizes_f4 = "component_reach" in recovery_strings

    findings = {
        "mathematical_rule_present": mathematical_rule_present,
        "oracle_requires_commodity_routes": requires_routes,
        "oracle_requires_non_null_ghost": requires_ghost,
        "oracle_object_is_one_fixed_src_sink_pair_per_commodity": fixed_pair_schema,
        "oracle_emits_empty_blocking_facilities": empty_causal_payload,
        "validator_rejects_ghost_agnostic_scope": ghost_agnostic_rejected,
        "live_enabled_family_set": sorted(enabled_families),
        "live_enabled_family_set_contains_f4": "component_reach" in enabled_families,
        "live_state_cell_owner_is_empty": state_cell_owner_is_empty,
        "live_state_supplies_commodity_routes": state_has_commodity_routes,
        "live_state_available_oracles": sorted(state_oracles),
        "live_state_available_oracles_contains_f4": "component_reach_v1" in state_oracles,
        "live_attach_calls_f4_generator": orchestrator_calls_f4,
        "typed_capability": capability,
        "typed_compiler_present": typed_compiler_present,
        "step8_master_domain_resolver_recognizes_f4": step8_recognizes_f4,
        "step8_master_domain_families": sorted(
            recovery_strings
            & {"region_capacity", "shape_packing_hall", "power_hitting_set", "component_reach"}
        ),
    }
    absent_live_requirements = [
        name
        for name, ok in (
            ("enabled_family", findings["live_enabled_family_set_contains_f4"]),
            ("cell_owner", not findings["live_state_cell_owner_is_empty"]),
            ("commodity_routes", findings["live_state_supplies_commodity_routes"]),
            ("oracle_capability", findings["live_state_available_oracles_contains_f4"]),
            ("generator_call", findings["live_attach_calls_f4_generator"]),
            ("typed_compiler", findings["typed_compiler_present"]),
            ("step8_domain", findings["step8_master_domain_resolver_recognizes_f4"]),
        )
        if not ok
    ]
    return {
        "classification": (
            "MATHEMATICS_PRESENT_BUT_LIVE_CONSUMPTION_ABSENT_AND_OBJECT_MISMATCH"
        ),
        "findings": findings,
        "absent_live_requirements": absent_live_requirements,
        "object_space_gap": {
            "legacy_f4": "one fixed src/sink pair in one ghost-bound free-cell state",
            "current_wall": (
                "selectable sets of many source/sink terminals whose component "
                "compatibility depends jointly on binding choices and placement"
            ),
            "missing_transport": (
                "a cause-bearing mapping from component mismatch to group/optional "
                "pose literals or to a positive placement resource"
            ),
        },
        "source_coordinates": {
            "state_builder": [state_builder.lineno, state_builder.end_lineno],
            "attach_orchestration": [attach.lineno, attach.end_lineno],
            "oracle_generate": [oracle_generate.lineno, oracle_generate.end_lineno],
            "oracle_try_one": [oracle_try.lineno, oracle_try.end_lineno],
            "oracle_build": [oracle_build.lineno, oracle_build.end_lineno],
            "scope_validator": [scope_validator.lineno, scope_validator.end_lineno],
            "step8_family_recovery": [recovery.lineno, recovery.end_lineno],
        },
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    started = time.monotonic()
    morphology = morphology_audit()
    architecture = architecture_audit()

    shape_coverage = morphology["e004_mismatch"]["families"][
        "shape_signature"
    ]["top_10_coverage"]
    owner_semantic_coverage = morphology["e004_mismatch"]["families"][
        "owner_semantic_signature"
    ]["top_10_coverage"]
    persistence = morphology["persistence"]["exact_cell_set_persistent_count"]
    component_count = morphology["a1"]["component_count"]
    f4_live = not architecture["absent_live_requirements"]

    if f4_live:
        verdict = "EXISTING_F4_LIVE_REPAIR_PATH"
    elif shape_coverage >= 0.70 and owner_semantic_coverage >= 0.60:
        verdict = "FULL_SEMANTIC_LOCAL_FAMILY_COMPRESSIBLE"
    elif shape_coverage >= 0.70 or persistence / component_count >= 0.90:
        verdict = "SHAPE_COMPRESSIBLE_CAUSAL_LONG_TAIL_POSITIVE_PERMEABILITY_NEXT"
    else:
        verdict = "MORPHOLOGY_LONG_TAIL_POSITIVE_PERMEABILITY_NEXT"

    return {
        "schema": "zmd_zero_condition_e005_component_morphology_f4_gap_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "morphology": morphology,
        "f4_architecture": architecture,
        "decision_reading": {
            "shape_top10_mismatch_coverage": shape_coverage,
            "owner_semantic_top10_mismatch_coverage": owner_semantic_coverage,
            "a1_to_e001_exact_component_persistence_fraction": persistence
            / component_count,
            "existing_f4_live_end_to_end": f4_live,
            "selected_next_probe": (
                "maximize free-cell adjacency as a positive solver-chosen "
                "permeability surrogate; do not prescribe a fixed corridor shape"
            ),
            "secondary_path": (
                "retain exact small boundary causes as local checked judgments when "
                "they recur, but do not treat shape identity alone as a sound cut"
            ),
        },
        "truth_boundary": (
            "Exact morphology for A1/E001 and exact static architecture facts for "
            "the pinned source revision. Diagnostic signatures are not future-family "
            "soundness proofs."
        ),
        "ledger_effect": "none",
        "elapsed_seconds": time.monotonic() - started,
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E005 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                    "shape_top10_coverage": result["decision_reading"][
                        "shape_top10_mismatch_coverage"
                    ],
                    "owner_semantic_top10_coverage": result["decision_reading"][
                        "owner_semantic_top10_mismatch_coverage"
                    ],
                    "component_persistence": result["decision_reading"][
                        "a1_to_e001_exact_component_persistence_fraction"
                    ],
                    "f4_absent_requirements": result["f4_architecture"][
                        "absent_live_requirements"
                    ],
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        import traceback

        failure = {
            "schema": "zmd_zero_condition_e005_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
