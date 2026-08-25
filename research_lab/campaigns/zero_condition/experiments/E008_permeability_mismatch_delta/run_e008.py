#!/usr/bin/env python3
"""E008: compare exact per-commodity mismatch minima for E001 and E006.

Research-only. One fresh optimization model is built per commodity, using the
E004 formulation and production-precheck comparison.
"""

from __future__ import annotations

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
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
E004_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E004_component_mismatch_atlas/run_e004.py"
)
E004_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E004_component_mismatch_atlas/run-001/RESULT.json"
)
E006_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E006_free_adjacency_master/run-003/RESULT.json"
)
E006_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E006_free_adjacency_master/run-003/PERMEABILITY_ASSIGNMENT.json"
)
E006_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E006_free_adjacency_master/run-003/PERMEABILITY_LAYOUT.json"
)
E007_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E007_permeability_interface/run-001/RESULT.json"
)
OUT = ROOT / "research_lab/local/zero_condition/E008_permeability_mismatch_delta/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

EXPECTED_HASHES: dict[Path, str] = {
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E004_RESULT: "490349a2778c46f7d209e199d7da34b73649d0ddcb5095a837731423a8460a69",
    E006_RESULT: "e3ce1ad7f557c1ee52c45588f9bc4ede701939fa444f9c7653157be71551d7d5",
    E006_ASSIGNMENT: "29692d8465374498100e6f58069c92eabb69460d8fc742912ec0984877218b43",
    E006_LAYOUT: "dd228aa137651251f63e8b473579d371d78b28781de4fd76518681eec830edd8",
    E007_RESULT: "51b0ed0c8b10e1454b5fb7c1785e7b9c9a9db56501c5d420e300daaec511bdee",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
    HISTORY_ROOT / "rules/canonical_rules.json": "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0",
    HISTORY_ROOT / "rules/preprocess_plan.json": "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee",
    ROOT / "src/models/binding_subproblem.py": "b5c6ebf84b31ef35a73e596d34eab96e2609f08e43cd3c2ff322e369646c5eba",
    ROOT / "src/models/port_binding.py": "9ed6c34873c5d8e3f7640a8507021e48ca2d850de2edc429482f3699700adc53",
    ROOT / "src/models/routing_binding_context.py": "9f9e4d058a561ca570f3c4fd7f5d5095a1bcff558e0608408b0760fc7609f7c2",
    ROOT / "src/models/routing_subproblem.py": "7554b0f24176b86104095ee47b8ec8ed5dfc4098c3df2f661231b0cf2f0ae718",
    ROOT / "src/search/pr2_l0_fixed_witness_core.py": "eae892a25f2e97c8f8cca4f58c205c8c18e829c7deba3407628aeab69c79eda1",
}
EXPECTED_ENV: dict[str, str] = {
    "PYTHONHASHSEED": "0",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
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


def verify_environment() -> dict[str, Any]:
    actual = {key: os.environ.get(key) for key in EXPECTED_ENV}
    mismatches = {
        key: {"expected": expected, "actual": actual[key]}
        for key, expected in EXPECTED_ENV.items()
        if actual[key] != expected
    }
    unexpected = sorted(
        key
        for key in os.environ
        if key.startswith("EXACT_") and key not in EXPECTED_ENV
    )
    if mismatches or unexpected:
        raise RuntimeError(
            f"environment mismatch: mismatches={mismatches}, unexpected={unexpected}"
        )
    return {"actual": actual, "unexpected_exact_variables": unexpected}


def verify_identity() -> dict[str, Any]:
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift for {path}: {actual} != {expected}")
    e007 = load_json(E007_RESULT)
    if e007.get("verdict") != "PERMEABILITY_COMPONENT_BINDING_INFEASIBLE":
        raise RuntimeError("E007 trigger is not the expected component failure")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def import_e004() -> Any:
    spec = importlib.util.spec_from_file_location("zmd_e004_formulation", E004_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load E004 runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reconstruct_solution() -> dict[str, dict[str, Any]]:
    assignment = load_json(E006_ASSIGNMENT)
    layout = load_json(E006_LAYOUT)
    raw = assignment.get("solution")
    placements = layout.get("placements")
    if not isinstance(raw, Mapping) or not isinstance(placements, list):
        raise RuntimeError("E006 assignment/layout structure is invalid")
    solution = {
        str(instance_id): dict(record)
        for instance_id, record in raw.items()
        if isinstance(record, Mapping) and str(instance_id) != "ghost_pick"
    }
    layout_solution = {
        str(record["instance_id"]): dict(record)
        for record in placements
        if isinstance(record, Mapping)
    }
    if json_safe(solution) != json_safe(layout_solution):
        raise RuntimeError("E006 assignment and layout disagree")
    if sum(bool(row.get("is_mandatory")) for row in solution.values()) != 266:
        raise RuntimeError("E006 mandatory count drift")
    return solution


def run() -> dict[str, Any]:
    identity = verify_identity()
    environment = verify_environment()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    e004 = import_e004()

    from src.models.binding_subproblem import load_binding_plan_semantics
    from src.models.master_model import (
        load_generic_io_requirements_artifact,
        load_project_data,
    )
    from src.models.routing_binding_context import build_routing_binding_context
    from src.models.routing_subproblem import RoutingPlacementCore

    baseline = load_json(E004_RESULT)
    baseline_by_commodity = {
        str(row["commodity"]): int(row["minimum_mismatch_count"])
        for row in baseline["commodity_results"]
    }
    if len(baseline_by_commodity) != 19:
        raise RuntimeError("E004 baseline commodity count drift")

    solution = reconstruct_solution()
    instances, pools, rules = load_project_data(
        HISTORY_ROOT,
        solve_mode="certified_exact",
    )
    generic = load_generic_io_requirements_artifact(HISTORY_ROOT)
    plan = load_binding_plan_semantics(project_root=HISTORY_ROOT)
    routing_context = build_routing_binding_context(
        solution,
        pools,
        GRID_W,
        GRID_H,
    )
    placement_core = RoutingPlacementCore.from_occupied_cells(
        set(routing_context.occupied_cells),
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )

    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    for index, commodity in enumerate(sorted(baseline_by_commodity), 1):
        print(
            json.dumps(
                {
                    "event": "E008_COMMODITY_START",
                    "index": index,
                    "total": 19,
                    "commodity": commodity,
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        measured = e004.solve_commodity(
            commodity=commodity,
            solution=solution,
            instances=instances,
            pools=pools,
            rules=rules,
            generic=generic,
            plan=plan,
            routing_context=routing_context,
            placement_core=placement_core,
        )
        if measured["status"] != "OPTIMAL":
            raise RuntimeError(
                f"E008 commodity did not reach OPTIMAL: {commodity} {measured['status']}"
            )
        current = int(measured["minimum_mismatch_count"])
        previous = baseline_by_commodity[commodity]
        measured["e004_baseline_minimum"] = previous
        measured["delta_e006_minus_e001"] = current - previous
        rows.append(measured)
        print(
            json.dumps(
                {
                    "event": "E008_COMMODITY_DONE",
                    "commodity": commodity,
                    "baseline": previous,
                    "current": current,
                    "delta": current - previous,
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    baseline_total = sum(baseline_by_commodity.values())
    current_total = sum(int(row["minimum_mismatch_count"]) for row in rows)
    improved = [row["commodity"] for row in rows if row["delta_e006_minus_e001"] < 0]
    unchanged = [row["commodity"] for row in rows if row["delta_e006_minus_e001"] == 0]
    worsened = [row["commodity"] for row in rows if row["delta_e006_minus_e001"] > 0]
    deltas = {
        str(row["commodity"]): int(row["delta_e006_minus_e001"])
        for row in rows
    }

    e007 = load_json(E007_RESULT)
    old_pruned = 4101
    new_pruned = int(
        e007["binding"]["compiled_interface"]["routing_aware_filter_stats"][
            "front_blocked_patterns_pruned"
        ]
    )
    old_surviving = 12955
    new_surviving = int(
        e007["binding"]["compiled_interface"]["filtered_binding_option_count"]
    )

    if current_total < baseline_total and len(improved) > len(worsened):
        verdict = "PERMEABILITY_PROXY_PARTIAL_INTERFACE_IMPROVEMENT"
    elif current_total == baseline_total and not improved and not worsened:
        verdict = "PERMEABILITY_PROXY_NO_INTERFACE_MOVEMENT"
    elif current_total >= baseline_total:
        verdict = "PERMEABILITY_PROXY_REGRESSED_INTERFACE"
    else:
        verdict = "PERMEABILITY_PROXY_MIXED_INTERFACE_EFFECT"

    component_sizes = sorted(
        (len(cells) for cells in routing_context.cells_by_component.values()),
        reverse=True,
    )
    return {
        "schema": "zmd_zero_condition_e008_permeability_mismatch_delta_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "environment": environment,
        "fixed_occupancy": {
            "occupied_cell_count": len(routing_context.occupied_cells),
            "free_cell_count": GRID_W * GRID_H - len(routing_context.occupied_cells),
            "free_component_count": len(component_sizes),
            "largest_free_component": component_sizes[0] if component_sizes else 0,
        },
        "aggregate": {
            "e001_total_minimum_mismatch": baseline_total,
            "e006_total_minimum_mismatch": current_total,
            "delta": current_total - baseline_total,
            "relative_change": (current_total - baseline_total) / baseline_total,
            "improved_count": len(improved),
            "unchanged_count": len(unchanged),
            "worsened_count": len(worsened),
            "improved_commodities": improved,
            "unchanged_commodities": unchanged,
            "worsened_commodities": worsened,
            "per_commodity_delta": deltas,
        },
        "front_domain_comparison": {
            "e001_front_blocked_patterns_pruned": old_pruned,
            "e006_front_blocked_patterns_pruned": new_pruned,
            "delta_pruned": new_pruned - old_pruned,
            "e001_surviving_binding_patterns": old_surviving,
            "e006_surviving_binding_patterns": new_surviving,
            "delta_surviving": new_surviving - old_surviving,
        },
        "commodity_results": rows,
        "production_comparison": (
            "Every optimum witness was replayed through production "
            "run_exact_routing_precheck by the E004 formulation."
        ),
        "truth_boundary": (
            "Exact mismatch delta between two fixed layouts, one fresh model per "
            "commodity. It does not characterize every candidate reachable by the "
            "free-adjacency objective."
        ),
        "routing_solver_run": False,
        "ledger_effect": "none",
        "elapsed_seconds": time.monotonic() - started,
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E008 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "aggregate": result["aggregate"],
                    "front_domain_comparison": result["front_domain_comparison"],
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e008_failure_v1",
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
