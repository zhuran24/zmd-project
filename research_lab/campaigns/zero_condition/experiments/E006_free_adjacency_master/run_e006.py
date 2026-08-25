#!/usr/bin/env python3
"""E006: maximize adjacent free-cell pairs in the no-ghost master.

Research-only. The existing E001 checked pocket cut is retained. The new objective
is a constructive heuristic and grants no production or certified effect.
"""

from __future__ import annotations

import datetime
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
E001_DIR = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay"
)
E001_RUNNER = E001_DIR / "run_experiment.py"
E001_JUDGMENT = E001_DIR / "JUDGMENT.json"
E001_LOWERING = E001_DIR / "LOWERING_CONTRACT.json"
E001_CERTIFICATE = (
    HISTORY_ROOT
    / ".artifacts/lowerbound_ladder_20260824/blue_iron_pocket_cut/BLUE_IRON_POCKET_CUT_CERTIFICATE.json"
)
E001_REPLACEMENT_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E001_pocket_cut_replay/run-002/REPLACEMENT_ASSIGNMENT.json"
)
E001_REPLACEMENT_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E001_pocket_cut_replay/run-002/REPLACEMENT_LAYOUT.json"
)
A1_LAYOUT = (
    HISTORY_ROOT
    / ".artifacts/lowerbound_ladder_20260824/phaseA1_noghost_master/MASTER_LAYOUT_A1.json"
)
OUT = ROOT / "research_lab/local/zero_condition/E006_free_adjacency_master/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
ASSIGNMENT_PATH = OUT / "PERMEABILITY_ASSIGNMENT.json"
LAYOUT_PATH = OUT / "PERMEABILITY_LAYOUT.json"

EXPECTED_HASHES: dict[Path, str] = {
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E001_JUDGMENT: "8637837d349af1057e9666d31f37e47a83dbc45d36914f8498e76558a732d953",
    E001_LOWERING: "49e7856635d1be9bb2a22b014eb5f2ba988208513a66c15240d535d4fcafa3da",
    E001_CERTIFICATE: "c589d7682fe7ecdc5d8784b311d51e0f48031af70b3be1dda936a16c4ef97d17",
    E001_REPLACEMENT_ASSIGNMENT: "ac80efdf293b12d852b62355815eaaeec7df5ae53b5078a4db9af24a41b55e91",
    E001_REPLACEMENT_LAYOUT: "752fb1706dba76ded658775750eaa6ac9f6816500e678a07ad18c3fce7d69f97",
    A1_LAYOUT: "9e545fdf29e55978a8237fc4c1f1183f9643abfe04b6e8d2a8a5319c31c4df83",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
    HISTORY_ROOT / "rules/canonical_rules.json": "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0",
    HISTORY_ROOT / "rules/preprocess_plan.json": "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee",
    ROOT / "src/models/master_model.py": "d1ada57bc6dcef1818341b26dfd482fb7c1623d106734b8f1a49061c2e7c1371",
    ROOT / "src/models/pose_bool_exact_master.py": "8991b7f98b95ee255c4967b13fc2d22bf6eed5ec54ad1f0e48377a44db0dbd90",
    ROOT / "src/models/cp_sat_worker_config.py": "4f9a4847f179f1ed15d61b17bcdc2340c82c1ec2494abd1eb7402f919c84ba50",
    ROOT / "src/models/routing_binding_context.py": "9f9e4d058a561ca570f3c4fd7f5d5095a1bcff558e0608408b0760fc7609f7c2",
    ROOT / "src/search/pr2_l0_fixed_witness_core.py": "eae892a25f2e97c8f8cca4f58c205c8c18e829c7deba3407628aeab69c79eda1",
}

EXPECTED_ENV: dict[str, str] = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "260825",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
}
MASTER_CAP_SECONDS = 240.0
GRID_W = 70
GRID_H = 70
TOTAL_GRID_EDGES = GRID_H * (GRID_W - 1) + GRID_W * (GRID_H - 1)


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

    consumed_tracked = {
        str(path.relative_to(ROOT))
        for path in EXPECTED_HASHES
        if path.is_relative_to(ROOT) and git_output("ls-files", "--", str(path.relative_to(ROOT)))
    }
    dirty_consumed: list[str] = []
    for line in git_output("status", "--porcelain=v1", "--untracked-files=no").splitlines():
        relative = line[3:].strip()
        if " -> " in relative:
            relative = relative.split(" -> ", 1)[1]
        if relative in consumed_tracked:
            dirty_consumed.append(relative)
    if dirty_consumed:
        raise RuntimeError(f"consumed tracked source is dirty: {dirty_consumed}")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def import_e001_module() -> Any:
    spec = importlib.util.spec_from_file_location("zmd_e001_committed_runner", E001_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load committed E001 runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reconstruct_solution(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    raw = payload.get("solution")
    if not isinstance(raw, Mapping):
        raise RuntimeError(f"assignment lacks solution: {path}")
    solution = {
        str(instance_id): dict(record)
        for instance_id, record in raw.items()
        if isinstance(record, Mapping) and str(instance_id) != "ghost_pick"
    }
    if sum(bool(row.get("is_mandatory")) for row in solution.values()) != 266:
        raise RuntimeError(f"mandatory count drift in {path}")
    return solution


def solution_layout(solution: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    placements = sorted(
        [dict(row) for row in solution.values()],
        key=lambda row: (
            not bool(row.get("is_mandatory")),
            str(row.get("facility_type", "")),
            str(row.get("operation_type", "")),
            str(row.get("instance_id", "")),
        ),
    )
    return {
        "schema": "zmd_e006_free_adjacency_layout_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ghost_rect": None,
        "mandatory_placement_count": sum(
            bool(row.get("is_mandatory")) for row in placements
        ),
        "total_selected_placement_count": len(placements),
        "power_coverage_in_master": True,
        "binding_routing_terminal_validator_run": False,
        "placements": placements,
    }


def occupancy_from_solution(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> set[tuple[int, int]]:
    occupied: set[tuple[int, int]] = set()
    for instance_id, row in solution.items():
        facility_type = str(row.get("facility_type", ""))
        pose_idx = int(row.get("pose_idx", -1))
        pool = pools.get(facility_type, [])
        if not (0 <= pose_idx < len(pool)):
            raise RuntimeError(f"pose out of range for {instance_id}")
        for raw_cell in pool[pose_idx].get("occupied_cells", []):
            cell = (int(raw_cell[0]), int(raw_cell[1]))
            if cell in occupied:
                raise RuntimeError(f"solution overlap at {cell}")
            occupied.add(cell)
    return occupied


def free_adjacency_score(free_cells: set[tuple[int, int]]) -> int:
    return sum(
        int((x + 1, y) in free_cells) + int((x, y + 1) in free_cells)
        for x, y in free_cells
    )


def morphology(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src.models.routing_binding_context import build_routing_binding_context

    context = build_routing_binding_context(
        solution,
        pools,
        GRID_W,
        GRID_H,
    )
    component_sizes = sorted(
        (len(cells) for cells in context.cells_by_component.values()),
        reverse=True,
    )
    free_cells = set(context.component_by_cell)
    return {
        "occupied_cell_count": len(context.occupied_cells),
        "free_cell_count": len(free_cells),
        "free_adjacency_score": free_adjacency_score(free_cells),
        "free_component_count": len(component_sizes),
        "largest_free_component": component_sizes[0] if component_sizes else 0,
        "component_sizes": component_sizes,
        "free_cell_set_digest": stable_digest(sorted(free_cells)),
    }


def add_free_adjacency_objective(master: Any) -> dict[str, Any]:
    delegate = master._coordinate_delegate
    if getattr(delegate, "master_representation", None) != "pose_bool_exact_v1":
        raise RuntimeError("E006 requires pose_bool_exact_v1")
    cell_poses = getattr(delegate, "_sac_cell_poses", None)
    if not isinstance(cell_poses, dict):
        raise RuntimeError("pose-bool cell occupancy cache is missing")
    proto = master.model.Proto()
    if len(proto.objective.vars) or len(proto.objective.coeffs):
        raise RuntimeError("master already has an integer objective")
    floating = getattr(proto, "floating_point_objective", None)
    if floating is not None and len(getattr(floating, "vars", [])):
        raise RuntimeError("master already has a floating-point objective")

    variables_before = len(proto.variables)
    constraints_before = len(proto.constraints)
    edge_vars: list[Any] = []
    edge_records: list[tuple[tuple[int, int], tuple[int, int], int]] = []
    for x in range(GRID_W):
        for y in range(GRID_H):
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if nx >= GRID_W or ny >= GRID_H:
                    continue
                a_terms = list(cell_poses.get((x, y), []))
                b_terms = list(cell_poses.get((nx, ny), []))
                edge = master.model.NewBoolVar(f"e006_free_edge_{x}_{y}_{nx}_{ny}")
                if a_terms:
                    master.model.Add(edge + sum(a_terms) <= 1)
                if b_terms:
                    master.model.Add(edge + sum(b_terms) <= 1)
                master.model.Add(edge + sum(a_terms) + sum(b_terms) >= 1)
                edge_vars.append(edge)
                edge_records.append(((x, y), (nx, ny), int(edge.Index())))
    if len(edge_vars) != TOTAL_GRID_EDGES:
        raise RuntimeError(
            f"free adjacency edge count drift: {len(edge_vars)} != {TOTAL_GRID_EDGES}"
        )
    master.model.Maximize(sum(edge_vars))
    return {
        "encoding": "exact_adjacent_free_pair_boolean_v1",
        "edge_variable_count": len(edge_vars),
        "variables_before": variables_before,
        "variables_after": len(master.model.Proto().variables),
        "variable_delta": len(master.model.Proto().variables) - variables_before,
        "constraints_before": constraints_before,
        "constraints_after": len(master.model.Proto().constraints),
        "constraint_delta": len(master.model.Proto().constraints) - constraints_before,
        "edge_variable_indices_digest": stable_digest(edge_records),
    }


def baseline_morphologies(
    *,
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    a1_layout = load_json(A1_LAYOUT)
    e001_layout = load_json(E001_REPLACEMENT_LAYOUT)

    def from_layout(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        placements = payload.get("placements")
        if not isinstance(placements, list):
            raise RuntimeError("baseline layout lacks placements")
        return {
            str(row["instance_id"]): dict(row)
            for row in placements
            if isinstance(row, Mapping)
        }

    return {
        "A1": morphology(solution=from_layout(a1_layout), pools=pools),
        "E001": morphology(solution=from_layout(e001_layout), pools=pools),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    environment = verify_environment()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    e001 = import_e001_module()
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    a1_parent = e001.load_parent_solution()
    hint_solution = reconstruct_solution(E001_REPLACEMENT_ASSIGNMENT)
    baselines = baseline_morphologies(pools=inputs["pools"])

    started = time.monotonic()
    build_started = time.monotonic()
    master = e001.construct_master(stack, inputs)
    master.build()
    build_seconds = time.monotonic() - build_started
    lowering = e001.audit_and_attach_lowering(
        master=master,
        inputs=inputs,
        parent_solution=a1_parent,
    )
    objective = add_free_adjacency_objective(master)

    hint = {
        instance_id: int(row["pose_idx"])
        for instance_id, row in hint_solution.items()
    }
    solve_started = time.monotonic()
    status_code = master.solve(
        time_limit_seconds=MASTER_CAP_SECONDS,
        solution_hint=hint,
        known_feasible_hint=True,
        hint_inactive_residual_optionals=False,
    )
    solve_seconds = time.monotonic() - solve_started
    solver = master._solver
    status = solver.StatusName(status_code) if solver is not None else "NO_SOLVER"
    cp_model = stack["cp_model"]
    master_record: dict[str, Any] = {
        "status": status,
        "status_code": int(status_code),
        "build_seconds": build_seconds,
        "solve_seconds": solve_seconds,
        "cap_seconds": MASTER_CAP_SECONDS,
        "raw_variable_count": len(master.model.Proto().variables),
        "raw_constraint_count": len(master.model.Proto().constraints),
        "last_solve": json_safe(master.build_stats.get("last_solve", {})),
        "objective_encoding": objective,
        "pocket_cut_lowering": lowering,
    }
    result: dict[str, Any] = {
        "schema": "zmd_zero_condition_e006_free_adjacency_master_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "environment": environment,
        "baselines": baselines,
        "master": master_record,
        "ledger_effect": "none",
        "binding_routing_terminal_validator_run": False,
        "elapsed_seconds": time.monotonic() - started,
    }
    if status_code not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        result["verdict"] = (
            "MASTER_INFEASIBLE_RESEARCH_ONLY"
            if status == "INFEASIBLE"
            else "MASTER_UNKNOWN"
            if status == "UNKNOWN"
            else "MASTER_EXECUTION_FAILURE"
        )
        result["truth_boundary"] = "No candidate morphology was established."
        return result

    objective_value = int(round(float(solver.ObjectiveValue())))
    objective_bound = float(solver.BestObjectiveBound())
    solution = master.extract_solution()
    candidate_morphology = morphology(solution=solution, pools=inputs["pools"])
    if candidate_morphology["free_adjacency_score"] != objective_value:
        raise RuntimeError(
            "objective/recomputed morphology mismatch: "
            f"{objective_value} != {candidate_morphology['free_adjacency_score']}"
        )

    selected_cut_literals: dict[str, int] = {}
    for row in lowering["resolved_literals"]:
        variable = master.model.GetBoolVarFromProtoIndex(int(row["consumer_var_index"]))
        selected_cut_literals[str(row["source_instance_id"])] = int(solver.Value(variable))
    if sum(selected_cut_literals.values()) > 3:
        raise RuntimeError(f"candidate violates E001 cut: {selected_cut_literals}")

    assignment = {
        "schema": "zmd_e006_free_adjacency_assignment_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "status": status,
        "scope": "zero_condition_placement_plus_power_e001_cut_free_adjacency_objective",
        "objective_value": objective_value,
        "solution": json_safe(solution),
    }
    layout = solution_layout(solution)
    dump_exclusive(ASSIGNMENT_PATH, assignment)
    dump_exclusive(LAYOUT_PATH, layout)

    e001_baseline = baselines["E001"]
    adjacency_gain = objective_value - int(e001_baseline["free_adjacency_score"])
    component_reduction = int(e001_baseline["free_component_count"]) - int(
        candidate_morphology["free_component_count"]
    )
    if adjacency_gain > 0 and component_reduction > 0:
        verdict = "PERMEABILITY_CANDIDATE"
    elif adjacency_gain > 0:
        verdict = "ADJACENCY_GAIN_WITHOUT_COMPONENT_REDUCTION"
    else:
        verdict = "NO_MEASURED_PERMEABILITY_GAIN"

    result.update(
        {
            "verdict": verdict,
            "objective": {
                "sense": "maximize",
                "value": objective_value,
                "best_bound": objective_bound,
                "optimal": status == "OPTIMAL",
                "gap_to_bound": objective_bound - objective_value,
            },
            "candidate": {
                "assignment_path": str(ASSIGNMENT_PATH.relative_to(ROOT)),
                "assignment_sha256": sha256_file(ASSIGNMENT_PATH),
                "layout_path": str(LAYOUT_PATH.relative_to(ROOT)),
                "layout_sha256": sha256_file(LAYOUT_PATH),
                "mandatory_count": sum(
                    bool(row.get("is_mandatory")) for row in solution.values()
                ),
                "total_selected_placement_count": len(solution),
                "selected_e001_cut_literals": selected_cut_literals,
                "morphology": candidate_morphology,
                "adjacency_gain_over_e001": adjacency_gain,
                "component_reduction_over_e001": component_reduction,
                "largest_component_gain_over_e001": int(
                    candidate_morphology["largest_free_component"]
                )
                - int(e001_baseline["largest_free_component"]),
            },
            "truth_boundary": (
                "Placement-plus-power candidate under the E001 cut and exact "
                "free-adjacency objective encoding. No binding or routing conclusion."
            ),
            "elapsed_seconds": time.monotonic() - started,
        }
    )
    del master
    gc.collect()
    return result


def main() -> int:
    if any(path.exists() for path in (RESULT_PATH, FAILURE_PATH, ASSIGNMENT_PATH, LAYOUT_PATH)):
        raise FileExistsError(f"refusing to overwrite E006 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "status": result["master"]["status"],
                    "objective": result.get("objective"),
                    "candidate_morphology": result.get("candidate", {}).get("morphology"),
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        import traceback

        failure = {
            "schema": "zmd_zero_condition_e006_failure_v1",
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
