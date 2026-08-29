#!/usr/bin/env python3
"""Independent solver replay and exact fixed-geometry death diagnosis for E114."""

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
RUNNER = HERE / "run_e114.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E114_e110_fixed_geometry_direct_consumer/run-001"
)
RESULT = RUN / "RESULT.json"
HIGH_RESULTS = RUN / "HIGH_FIXED_GEOMETRY_RESULTS.json"
LOW_RESULTS = RUN / "LOW_ALLOCATION_RESULTS.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
DIAGNOSTICS = RUN / "FIXED_GEOMETRY_DEATH_DIAGNOSTICS.json"
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
E101_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E101_x42_allocation_handshake/run_e101.py"
)
E110_PROJECTION = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E110_explicit_separator_template_duty_atlas/run-001/"
    "SEPARATOR_TEMPLATE_PROJECTION.json"
)

EXPECTED = {
    RUNNER: "e893bdc7df70ce93f66c3976a06e3fd15e2d81b492fd2463b9d17cec4cd16e5d",
    RESULT: "58348a482fb4936aca55d06d161e49804ee7e3c032544a64d97a5b5ceee46d22",
    HIGH_RESULTS: "a6c6e74ec5361891adae9904cbc675996b725b539e807817e2403344b36e6318",
    LOW_RESULTS: "c3203e10a2500706d9ef8107a71080ab9388d81a10b9059954360a6c0c193499",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E110_PROJECTION: "73570c931c8e8c053ec5a17feaa821e4e69511443882eac01110b470a6537413",
}

HIGH_TEMPLATE_COUNTS = {
    "manufacturing_3x3": 10,
    "manufacturing_5x5": 6,
    "manufacturing_6x4": 10,
}
EXPECTED_GEOMETRIES = 27
EXPECTED_BODIES = 26
EXPECTED_CLASSES = 8


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


def group_of(row: Mapping[str, Any]) -> str:
    ys = [int(value[1]) for value in row["body"]]
    if max(ys) <= 59:
        return "low"
    if min(ys) > 59:
        return "high"
    return "separator"


def fixed_bundle(
    *,
    e095: types.ModuleType,
    e101: types.ModuleType,
    restricted: Mapping[str, Any],
    selected: set[int],
) -> dict[str, Any]:
    bundle = e101.build_side_model(
        e095=e095,
        restricted=restricted,
        side="high",
        template_counts=HIGH_TEMPLATE_COUNTS,
        body_hint_indices=set(selected),
        fixed_allocation=None,
    )
    mapped = {
        int(row["global_row_index"])
        for row in bundle["rows"]
        if int(row["global_row_index"]) in selected
    }
    require(mapped == selected, "fixed body remap drift")
    for index, row in enumerate(bundle["rows"]):
        bundle["model"].Add(
            bundle["body_vars"][index]
            == int(int(row["global_row_index"]) in selected)
        )
    error = bundle["model"].Validate()
    require(not error, f"fixed model invalid: {error}")
    return bundle


def viable_domains(
    *,
    e095: types.ModuleType,
    bundle: Mapping[str, Any],
    selected: set[int],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    rows = bundle["rows"]
    local_by_global = {
        int(row["global_row_index"]): index for index, row in enumerate(rows)
    }
    selected_local = {local_by_global[index] for index in selected}
    occupied = set(context["fixed_solid"])
    for local_index in selected_local:
        body = set(rows[local_index]["body"])
        require(not occupied & body, "diagnostic body overlap")
        occupied |= body

    allowed_by_body: dict[int, set[tuple[str, str, int, int]]] = {
        index: set() for index in selected_local
    }
    option_count_by_body: Counter[int] = Counter()
    for mode in bundle["mode_rows"]:
        body_index = int(mode["body_index"])
        if body_index not in selected_local:
            continue
        input_cells = tuple(mode["input_cells"])
        output_cells = tuple(mode["output_cells"])
        free_inputs = sum(
            e095.in_grid(value) and value not in occupied for value in input_cells
        )
        free_outputs = sum(
            e095.in_grid(value) and value not in occupied for value in output_cells
        )
        if free_inputs < int(mode["need_in"]) or free_outputs < int(mode["need_out"]):
            continue
        class_key = tuple(mode["class_key"])
        allowed_by_body[body_index].add(class_key)
        option_count_by_body[body_index] += 1

    zero_bodies = sorted(
        index for index in selected_local if not allowed_by_body[index]
    )
    zero_records = [
        {
            "local_body_index": index,
            "global_row_index": int(rows[index]["global_row_index"]),
            "body_digest": str(rows[index]["body_digest"]),
            "template": str(rows[index]["template"]),
            "separator_group": group_of(rows[index]),
            "current_owner": rows[index]["current_owner"],
        }
        for index in zero_bodies
    ]

    class_keys = tuple(bundle["class_keys"])
    global_counts = dict(bundle["global_class_counts"])
    hall_violations: list[dict[str, Any]] = []
    if not zero_bodies:
        for mask in range(1, 1 << len(class_keys)):
            subset = {
                class_keys[index]
                for index in range(len(class_keys))
                if mask & (1 << index)
            }
            forced_bodies = [
                index
                for index in selected_local
                if allowed_by_body[index] and allowed_by_body[index] <= subset
            ]
            capacity = sum(int(global_counts[key]) for key in subset)
            excess = len(forced_bodies) - capacity
            if excess > 0:
                hall_violations.append(
                    {
                        "class_subset": [list(key) for key in sorted(subset)],
                        "capacity": capacity,
                        "forced_body_count": len(forced_bodies),
                        "excess": excess,
                        "forced_global_indices": sorted(
                            int(rows[index]["global_row_index"])
                            for index in forced_bodies
                        ),
                    }
                )
        hall_violations.sort(
            key=lambda row: (
                -int(row["excess"]),
                len(row["class_subset"]),
                row["class_subset"],
            )
        )

    if zero_bodies:
        death_kind = "EMPTY_BODY_MODE_CLASS_DOMAIN"
    elif hall_violations:
        death_kind = "CLASS_HALL_DEFICIT"
    else:
        death_kind = "UNEXPLAINED_SOLVER_NEGATIVE"

    return {
        "death_kind": death_kind,
        "selected_body_count": len(selected_local),
        "zero_domain_body_count": len(zero_bodies),
        "zero_domain_bodies": zero_records,
        "minimum_viable_option_count": min(
            (int(option_count_by_body[index]) for index in selected_local),
            default=0,
        ),
        "maximum_viable_option_count": max(
            (int(option_count_by_body[index]) for index in selected_local),
            default=0,
        ),
        "total_viable_mode_class_option_count": sum(
            int(option_count_by_body[index]) for index in selected_local
        ),
        "allowed_class_count_distribution": dict(
            sorted(
                Counter(
                    len(allowed_by_body[index]) for index in selected_local
                ).items()
            )
        ),
        "strongest_hall_violation": (
            hall_violations[0] if hall_violations else None
        ),
        "hall_violation_count": len(hall_violations),
    }


def main() -> int:
    if OUTPUT.exists() or DIAGNOSTICS.exists():
        raise FileExistsError("refusing to overwrite E114 checker outputs")
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E114 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E114 artifact identity drift: {path}")
        artifact_records[str(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load(RESULT)
    high = load(HIGH_RESULTS)
    low = load(LOW_RESULTS)
    projection = load(E110_PROJECTION)
    require(
        result["verdict"]
        == "ALL_E110_REPRESENTATIVE_GEOMETRIES_FAIL_FULL_HIGH_NATIVE_FRONT",
        "E114 verdict drift",
    )
    require(
        result["decision"]
        == "USE_FULL_CONSUMER_DEATHS_TO_REDESIGN_GEOMETRY_OR_JOINT_COLLAR",
        "E114 decision drift",
    )
    require(int(high["formal_geometry_count"]) == EXPECTED_GEOMETRIES, "formal count drift")
    require(int(high["tested_geometry_count"]) == EXPECTED_GEOMETRIES, "tested count drift")
    require(int(high["negative_geometry_count"]) == EXPECTED_GEOMETRIES, "negative count drift")
    require(int(high["positive_geometry_count"]) == 0, "unexpected high positive")
    require(int(high["unknown_geometry_count"]) == 0, "unexpected high UNKNOWN")
    require(low["records"] == [], "unexpected low consumer record")
    require(int(projection["vector_count"]) == EXPECTED_GEOMETRIES, "projection count drift")

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e114_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e114_check_e100")
    e101 = source_module(E101_RUNNER, "zmd_e114_check_e101")
    restricted = e100.build_restricted_context(e095)
    vector_by_iteration = {
        int(row["iteration"]): row for row in projection["vectors"]
    }
    require(len(vector_by_iteration) == EXPECTED_GEOMETRIES, "iteration identity drift")

    replay_records: list[dict[str, Any]] = []
    death_records: list[dict[str, Any]] = []
    zero_body_frequency: Counter[str] = Counter()
    zero_template_frequency: Counter[str] = Counter()
    zero_group_frequency: Counter[str] = Counter()
    replay_elapsed_total = 0.0

    for record in high["records"]:
        iteration = int(record["geometry"]["iteration"])
        source = vector_by_iteration[iteration]
        selected = set(map(int, source["witness"]["selected_global_indices"]))
        require(len(selected) == EXPECTED_BODIES, "selected geometry size drift")
        require(record["terminal_status"] == "INFEASIBLE", "producer terminal drift")

        bundle = fixed_bundle(
            e095=e095,
            e101=e101,
            restricted=restricted,
            selected=selected,
        )
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 15.0
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 114900 + iteration
        solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
        solver.parameters.symmetry_level = 3
        solver.parameters.cp_model_probing_level = 3
        solver.parameters.stop_after_first_solution = True
        started = time.monotonic()
        status_code = solver.Solve(bundle["model"])
        elapsed = time.monotonic() - started
        replay_elapsed_total += elapsed
        status = solver.StatusName(status_code)
        require(status == "INFEASIBLE", f"E114 diverse replay drift: {iteration}: {status}")

        death = viable_domains(
            e095=e095,
            bundle=bundle,
            selected=selected,
            context=restricted["base"],
        )
        require(
            death["death_kind"] != "UNEXPLAINED_SOLVER_NEGATIVE",
            f"E114 fixed negative lacks exact domain explanation: {iteration}",
        )
        for row in death["zero_domain_bodies"]:
            zero_body_frequency[str(row["body_digest"])] += 1
            zero_template_frequency[str(row["template"])] += 1
            zero_group_frequency[str(row["separator_group"])] += 1
        death_records.append(
            {
                "geometry_id": str(record["geometry_id"]),
                "iteration": iteration,
                "separator_template_vector": list(map(int, source["vector"])),
                **death,
            }
        )
        replay_records.append(
            {
                "geometry_id": str(record["geometry_id"]),
                "iteration": iteration,
                "producer_status": "INFEASIBLE",
                "replay_status": status,
                "elapsed_seconds": elapsed,
                "branches": int(solver.NumBranches()),
                "conflicts": int(solver.NumConflicts()),
                "workers": 1,
                "search_branching": "AUTOMATIC_SEARCH",
                "symmetry_level": 3,
                "probing_level": 3,
            }
        )

    death_kind_counts = Counter(str(row["death_kind"]) for row in death_records)
    diagnostics = {
        "schema": "zmd_e114_fixed_geometry_death_diagnostics_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "geometry_count": len(death_records),
        "death_kind_counts": dict(sorted(death_kind_counts.items())),
        "zero_domain_body_occurrence_count": sum(
            int(row["zero_domain_body_count"]) for row in death_records
        ),
        "zero_domain_unique_body_digest_count": len(zero_body_frequency),
        "zero_domain_body_digest_frequency": dict(
            zero_body_frequency.most_common()
        ),
        "zero_domain_template_frequency": dict(
            zero_template_frequency.most_common()
        ),
        "zero_domain_group_frequency": dict(
            zero_group_frequency.most_common()
        ),
        "records": death_records,
        "truth_boundary": (
            "Exact fixed-body native-front death classification. Empty domains are "
            "body-specific; Hall deficits are class-assignment conditions inside one "
            "fixed geometry. Neither generalizes to an E110 template state without a "
            "separate proof."
        ),
    }
    dump_exclusive(DIAGNOSTICS, diagnostics)

    payload = {
        "schema": "zmd_e114_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "TWENTY_SEVEN_FIXED_GEOMETRIES_DIVERSELY_REPLAYED_AND_EXPLAINED",
        "artifact_records": artifact_records,
        "solver_diverse_replay": {
            "geometry_count": len(replay_records),
            "all_infeasible": True,
            "total_elapsed_seconds": replay_elapsed_total,
            "records": replay_records,
        },
        "death_diagnostics": {
            "path": str(DIAGNOSTICS.relative_to(ROOT)),
            "sha256": sha256(DIAGNOSTICS),
            "death_kind_counts": dict(sorted(death_kind_counts.items())),
            "zero_domain_body_occurrence_count": diagnostics[
                "zero_domain_body_occurrence_count"
            ],
            "zero_domain_unique_body_digest_count": diagnostics[
                "zero_domain_unique_body_digest_count"
            ],
            "zero_domain_template_frequency": diagnostics[
                "zero_domain_template_frequency"
            ],
            "zero_domain_group_frequency": diagnostics[
                "zero_domain_group_frequency"
            ],
        },
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "All 27 stored E110 representative geometries are exact negatives under "
            "the complete x42-high native-front consumer. They are not a complete "
            "geometry basis for any separator template state."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "geometry_count": len(replay_records),
                "death_kind_counts": payload["death_diagnostics"][
                    "death_kind_counts"
                ],
                "zero_domain_body_occurrence_count": payload[
                    "death_diagnostics"
                ]["zero_domain_body_occurrence_count"],
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
