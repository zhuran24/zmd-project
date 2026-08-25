#!/usr/bin/env python3
"""E012: compare E011 mismatch minima with E001/E006/E009 baselines."""

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
E008_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E008_permeability_mismatch_delta/run-001/RESULT.json"
)
E010_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E010_pattern_exposed_mismatch_delta/run-001/RESULT.json"
)
E011_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E011_guarded_joint_step/run-001/RESULT.json"
)
E011_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E011_guarded_joint_step/run-001/GUARDED_PERMEABILITY_ASSIGNMENT.json"
)
E011_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E011_guarded_joint_step/run-001/GUARDED_PERMEABILITY_LAYOUT.json"
)
OUT = ROOT / "research_lab/local/zero_condition/E012_joint_step_mismatch_delta/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

EXPECTED_HASHES: dict[Path, str] = {
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E004_RESULT: "490349a2778c46f7d209e199d7da34b73649d0ddcb5095a837731423a8460a69",
    E008_RESULT: "07cb000e85ba1795d851f1b79e3e4d82af9974cc4b68369932e50fb2205d67d9",
    E010_RESULT: "6e0965a159c52c6e49a5e0c8afc2a57472f8df0669d5631ed04c73749770d4fe",
    E011_RESULT: "8ccc4b94d988d4de21c2199d3c2d883f8301c27c38e230632a229bd5cc38ff4d",
    E011_ASSIGNMENT: "06eb57dad02863be58107a64a76b68f39adf00e6ed028a0fbdd64328fc7c2c45",
    E011_LAYOUT: "1707b28d5b910fd69efd9c2192659b1aa951d8291d3c15e9d1f07ea566f814b7",
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
    if load_json(E011_RESULT).get("verdict") != "JOINT_STEP_FAITHFUL_CANDIDATE":
        raise RuntimeError("E011 trigger drift")
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
    assignment = load_json(E011_ASSIGNMENT)
    layout = load_json(E011_LAYOUT)
    raw = assignment.get("solution")
    placements = layout.get("placements")
    if not isinstance(raw, Mapping) or not isinstance(placements, list):
        raise RuntimeError("E011 assignment/layout structure is invalid")
    solution = {
        str(instance_id): dict(record)
        for instance_id, record in raw.items()
        if isinstance(record, Mapping)
    }
    layout_solution = {
        str(record["instance_id"]): dict(record)
        for record in placements
        if isinstance(record, Mapping)
    }
    if json_safe(solution) != json_safe(layout_solution):
        raise RuntimeError("E011 assignment and layout disagree")
    if sum(bool(row.get("is_mandatory")) for row in solution.values()) != 266:
        raise RuntimeError("E011 mandatory count drift")
    return solution


def minima_by_commodity(payload: Mapping[str, Any]) -> dict[str, int]:
    return {
        str(row["commodity"]): int(row["minimum_mismatch_count"])
        for row in payload["commodity_results"]
    }


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

    baselines = {
        "E001": minima_by_commodity(load_json(E004_RESULT)),
        "E006": minima_by_commodity(load_json(E008_RESULT)),
        "E009": minima_by_commodity(load_json(E010_RESULT)),
    }
    commodity_set = set(baselines["E001"])
    if len(commodity_set) != 19 or any(set(values) != commodity_set for values in baselines.values()):
        raise RuntimeError("baseline commodity sets disagree")

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
    for index, commodity in enumerate(sorted(commodity_set), 1):
        print(
            json.dumps(
                {
                    "event": "E012_COMMODITY_START",
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
                f"commodity did not reach OPTIMAL: {commodity} {measured['status']}"
            )
        current = int(measured["minimum_mismatch_count"])
        measured.update(
            {
                "e001_minimum": baselines["E001"][commodity],
                "e006_minimum": baselines["E006"][commodity],
                "e009_minimum": baselines["E009"][commodity],
                "delta_from_e009": current - baselines["E009"][commodity],
            }
        )
        rows.append(measured)
        print(
            json.dumps(
                {
                    "event": "E012_COMMODITY_DONE",
                    "commodity": commodity,
                    "e009": baselines["E009"][commodity],
                    "e011": current,
                    "delta": current - baselines["E009"][commodity],
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    current = {
        str(row["commodity"]): int(row["minimum_mismatch_count"])
        for row in rows
    }
    totals = {
        label: sum(values.values()) for label, values in baselines.items()
    }
    totals["E011"] = sum(current.values())
    improved = [
        commodity
        for commodity in sorted(commodity_set)
        if current[commodity] < baselines["E009"][commodity]
    ]
    unchanged = [
        commodity
        for commodity in sorted(commodity_set)
        if current[commodity] == baselines["E009"][commodity]
    ]
    worsened = [
        commodity
        for commodity in sorted(commodity_set)
        if current[commodity] > baselines["E009"][commodity]
    ]
    zero = [commodity for commodity in sorted(commodity_set) if current[commodity] == 0]

    if totals["E011"] < totals["E009"] and len(improved) > len(worsened):
        verdict = "GUARDED_JOINT_STEP_BROAD_MISMATCH_IMPROVEMENT"
    elif totals["E011"] < totals["E009"]:
        verdict = "GUARDED_JOINT_STEP_MIXED_MISMATCH_IMPROVEMENT"
    else:
        verdict = "GUARDED_JOINT_STEP_NO_MISMATCH_IMPROVEMENT"

    component_sizes = sorted(
        (len(cells) for cells in routing_context.cells_by_component.values()),
        reverse=True,
    )
    return {
        "schema": "zmd_zero_condition_e012_joint_step_mismatch_delta_v1",
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
            "totals": totals,
            "e011_minus_e009": totals["E011"] - totals["E009"],
            "relative_change_from_e009": (
                totals["E011"] - totals["E009"]
            )
            / totals["E009"],
            "improved_count": len(improved),
            "unchanged_count": len(unchanged),
            "worsened_count": len(worsened),
            "improved": improved,
            "unchanged": unchanged,
            "worsened": worsened,
            "zero_mismatch_commodities": zero,
        },
        "per_commodity": {
            commodity: {
                "E001": baselines["E001"][commodity],
                "E006": baselines["E006"][commodity],
                "E009": baselines["E009"][commodity],
                "E011": current[commodity],
                "delta_from_E009": current[commodity]
                - baselines["E009"][commodity],
            }
            for commodity in sorted(commodity_set)
        },
        "commodity_results": rows,
        "production_comparison": (
            "Every optimum witness was evaluated by production "
            "run_exact_routing_precheck through the E004 formulation."
        ),
        "routing_solver_run": False,
        "truth_boundary": (
            "Exact per-commodity mismatch comparison for four fixed layouts; no "
            "convergence or global necessity claim."
        ),
        "ledger_effect": "none",
        "elapsed_seconds": time.monotonic() - started,
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E012 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "aggregate": result["aggregate"],
                    "per_commodity": result["per_commodity"],
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
            "schema": "zmd_zero_condition_e012_failure_v1",
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
