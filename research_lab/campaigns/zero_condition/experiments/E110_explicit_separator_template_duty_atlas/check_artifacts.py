#!/usr/bin/env python3
"""Independent replay of E110's separator template-duty atlas."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import types
from typing import Any, Mapping

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e110.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E110_explicit_separator_template_duty_atlas/run-001"
)
RESULT = RUN / "RESULT.json"
PROJECTION = RUN / "SEPARATOR_TEMPLATE_PROJECTION.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E095_y41_module_product_decomposition/run_e095.py"
)
E100_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E100_source_stable_reserved_x42_hybrid/run_e100.py"
)
E103_LIVE = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E103_high_side_interface_capacity_audit/run-003/LIVE_HIGH_CANDIDATES.json"
)
E109_CHECK = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E109_last_two_template_split_discriminator/run-001/ARTIFACT_CHECK.json"
)

EXPECTED = {
    RUNNER: "30b2fc298ef56ba68053d47977ef139890e862568b53bba70bdf541f677a1fea",
    RESULT: "6b454d85725ac91ffdb7478231fb6b0900d077c701d1a2c81c6d75acff889664",
    PROJECTION: "73570c931c8e8c053ec5a17feaa821e4e69511443882eac01110b470a6537413",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E103_LIVE: "ebf0c34b174df7036cf6c4bf2f3283dd4ea303998f62520cbd0c74d70aebfd08",
    E109_CHECK: "a065ff1730e445bea7ae6825413b27a7bee641b63c4f20c084050229a9a511a0",
}
TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
TOTALS = Counter(
    {
        "manufacturing_3x3": 10,
        "manufacturing_5x5": 6,
        "manufacturing_6x4": 10,
    }
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def source_module(path: Path, name: str, package: str | None = None) -> types.ModuleType:
    raw = path.read_bytes()
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = package if package is not None else name.rpartition(".")[0]
    module.__loader__ = None
    sys.modules[name] = module
    exec(
        compile(
            raw,
            f"<source-isolated-check:{path}:{hashlib.sha256(raw).hexdigest()}>",
            "exec",
            dont_inherit=True,
        ),
        module.__dict__,
    )
    return module


def vector_set(payload: Mapping[str, Any]) -> set[tuple[int, int, int]]:
    return {tuple(map(int, row["vector"])) for row in payload["vectors"]}


def replay_witnesses(
    prepared: Mapping[str, Any],
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    rows_by_global = {
        int(row["global_row_index"]): row for row in prepared["rows"]
    }
    coverage = set(prepared["context"]["fixed_coverage"])
    stable = prepared["context"]["stable_footprints"]
    records: list[dict[str, Any]] = []
    for vector_record in projection["vectors"]:
        vector = tuple(map(int, vector_record["vector"]))
        witness = vector_record["witness"]
        indices = list(map(int, witness["selected_global_indices"]))
        require(len(indices) == len(set(indices)) == 26, "witness identity/count drift")
        selected = [rows_by_global[index] for index in indices]
        occupied: set[tuple[int, int]] = set()
        total_counts: Counter[str] = Counter()
        group_counts: Counter[tuple[str, str]] = Counter()
        for row in selected:
            body = set(row["body"])
            require(not occupied & body, "witness body overlap")
            occupied |= body
            require(bool(body & coverage), "witness unpowered body")
            template = str(row["template"])
            group = str(row["separator_group"])
            total_counts[template] += 1
            group_counts[(group, template)] += 1
        require(total_counts == TOTALS, "witness global template totals drift")
        for instance_id, footprint in stable.items():
            require(
                any(tuple(row["body"]) == footprint for row in selected),
                f"stable body missing: {instance_id}",
            )
        observed_vector = tuple(
            group_counts[("separator", template)] for template in TEMPLATES
        )
        require(observed_vector == vector, "witness separator vector drift")
        expected_group_counts = {
            f"{group}:{template}": int(count)
            for (group, template), count in sorted(group_counts.items())
        }
        require(
            expected_group_counts == witness["group_template_counts"],
            "witness group-template table drift",
        )
        records.append(
            {
                "vector": list(vector),
                "selected_body_count": len(selected),
                "occupied_cell_count": len(occupied),
                "stable_body_count": len(stable),
            }
        )
    return {"witness_count": len(records), "records": records}


def independent_enumeration(
    runner: types.ModuleType,
    prepared: Mapping[str, Any],
) -> dict[str, Any]:
    body_model = runner.build_model(prepared)
    model = body_model["model"]
    found: set[tuple[int, int, int]] = set()
    solves: list[dict[str, Any]] = []
    for iteration in range(100):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 110900 + iteration
        solver.parameters.search_branching = cp_model.PSEUDO_COST_SEARCH
        solver.parameters.symmetry_level = 0
        solver.parameters.cp_model_probing_level = 0
        solver.parameters.stop_after_first_solution = True
        started = time.monotonic()
        status_code = solver.Solve(model)
        elapsed = time.monotonic() - started
        status = solver.StatusName(status_code)
        solves.append(
            {
                "iteration": iteration,
                "status": status,
                "elapsed_seconds": elapsed,
                "branches": int(solver.NumBranches()),
                "conflicts": int(solver.NumConflicts()),
            }
        )
        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            vector = tuple(
                int(solver.Value(body_model["separator_count_vars"][template]))
                for template in TEMPLATES
            )
            require(vector not in found, "independent enumeration duplicate")
            found.add(vector)
            model.AddForbiddenAssignments(
                body_model["ordered_separator_vars"],
                [list(vector)],
            )
            continue
        require(status == "INFEASIBLE", f"independent enumeration censored: {status}")
        break
    require(solves[-1]["status"] == "INFEASIBLE", "enumeration did not close")
    return {
        "status": "COMPLETE",
        "vector_count": len(found),
        "vectors": [list(vector) for vector in sorted(found)],
        "solves": solves,
        "workers": 1,
        "search_branching": "PSEUDO_COST_SEARCH",
        "symmetry_level": 0,
        "probing_level": 0,
    }


def summary_from_vectors(vectors: set[tuple[int, int, int]]) -> dict[str, Any]:
    body_counts = [sum(vector) for vector in vectors]
    return {
        "separator_body_count_min": min(body_counts),
        "separator_body_count_max": max(body_counts),
        "per_template_min": {
            template: min(vector[index] for vector in vectors)
            for index, template in enumerate(TEMPLATES)
        },
        "per_template_max": {
            template: max(vector[index] for vector in vectors)
            for index, template in enumerate(TEMPLATES)
        },
        "body_count_distribution": {
            str(count): sum(value == count for value in body_counts)
            for count in sorted(set(body_counts))
        },
        "zero_separator_vector_present": (0, 0, 0) in vectors,
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E110 check: {OUTPUT}")
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E110 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E110 artifact identity drift: {path}")
        artifact_records[str(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    result = load(RESULT)
    projection = load(PROJECTION)
    require(result["verdict"] == "EXPLICIT_SEPARATOR_TEMPLATE_DUTY_ATLAS_COMPLETE", "verdict drift")
    require(result["decision"] == "ATTACH_CLASS_COORDINATES_TO_SEPARATOR_VECTORS", "decision drift")
    require(projection["complete"] is True and projection["status"] == "COMPLETE", "projection incomplete")
    require(projection["terminal_status"] == "INFEASIBLE", "projection terminal drift")
    require(int(projection["vector_count"]) == 27, "vector count drift")
    producer_vectors = vector_set(projection)
    require(len(producer_vectors) == 27, "producer vector uniqueness drift")
    require(result["summary"] == summary_from_vectors(producer_vectors), "summary drift")
    e109 = load(E109_CHECK)
    require(
        e109["classification"]
        == "SEVEN_STATE_BODY_ATLAS_FULLY_COVERED_BY_EXACT_SPLIT_NOGOODS",
        "E109 closure identity drift",
    )

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e110_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e110_check_e100")
    runner = source_module(RUNNER, "zmd_e110_check_runner")
    prepared = runner.restore_three_groups(e095=e095, e100=e100)
    require(prepared["group_counts"] == {"high": 239, "low": 812, "separator": 154}, "restored group drift")
    require(prepared["anchor_group_counts"] == {"high": 5, "low": 19, "separator": 1}, "anchor group drift")

    witness_replay = replay_witnesses(prepared, projection)
    independent = independent_enumeration(runner, prepared)
    independent_vectors = {tuple(value) for value in independent["vectors"]}
    require(independent_vectors == producer_vectors, "independent vector set drift")

    payload = {
        "schema": "zmd_e110_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "TWENTY_SEVEN_SEPARATOR_TEMPLATE_VECTORS_EXACTLY_ENUMERATED",
        "artifact_records": artifact_records,
        "restored_group_counts": prepared["group_counts"],
        "restored_anchor_group_counts": prepared["anchor_group_counts"],
        "witness_replay": witness_replay,
        "independent_enumeration": independent,
        "summary": summary_from_vectors(producer_vectors),
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "Independent one-worker separator-vector enumeration plus replay of "
            "all body/power witnesses. The 27-vector atlas is exact only at the "
            "body/power layer; side counts in representative witnesses are not unique."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "vector_count": independent["vector_count"],
                "summary": payload["summary"],
                "decision": payload["decision"],
                "output_path": str(OUTPUT.relative_to(ROOT)),
                "output_sha256": sha256(OUTPUT),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
