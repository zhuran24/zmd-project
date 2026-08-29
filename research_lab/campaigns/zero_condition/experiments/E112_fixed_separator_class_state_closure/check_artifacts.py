#!/usr/bin/env python3
"""Independent replay for E112's complete separator class atlas."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import types
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e112.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E112_fixed_separator_class_state_closure/run-001"
)
RESULT = RUN / "RESULT.json"
FIXED = RUN / "FIXED_STATE_RESULTS.json"
MANIFEST = RUN / "SEPARATOR_CLASS_ATLAS_MANIFEST.json"
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
E110_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E110_explicit_separator_template_duty_atlas/run_e110.py"
)
E110_PROJECTION = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E110_explicit_separator_template_duty_atlas/run-001/"
    "SEPARATOR_TEMPLATE_PROJECTION.json"
)
E111_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E111_separator_native_front_class_atlas/run_e111.py"
)
E111_PROJECTION = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E111_separator_native_front_class_atlas/run-003/"
    "SEPARATOR_CLASS_PROJECTION.json"
)
E111_CHECK = E111_PROJECTION.with_name("ARTIFACT_CHECK.json")
E111_RESIDUAL = E111_PROJECTION.with_name("RESIDUAL_CLASS_STATES.json")

EXPECTED = {
    RUNNER: "125d79f51cd3c030eafc4fdbc2da61c76ca91fef1a11dfdcba9813243371460a",
    RESULT: "da64e4a66ff0826c1b9aa56b69fda4fe7855739acc60e853522241dc5bd9fa0e",
    FIXED: "49d7a98000ca7ea53c622b76415f485b98e745e0b19ce090ba1f92af3e1accb4",
    MANIFEST: "45767f5f1a00d051701e1bd6787a77a813e23d1958652c632dbfea336113db2a",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E110_RUNNER: "30b2fc298ef56ba68053d47977ef139890e862568b53bba70bdf541f677a1fea",
    E110_PROJECTION: "73570c931c8e8c053ec5a17feaa821e4e69511443882eac01110b470a6537413",
    E111_RUNNER: "ea0ce5442c485b6c992b2ec27edb86b18bfc6354bb22e0295909ee5813b435e4",
    E111_PROJECTION: "58d8a27697ae03612ce770afece3d0bf395fb2dd8e7c6ad9a92163222ba5464c",
    E111_CHECK: "cc52d98fb0a5e0cdc715855174315e627dfd2de8d271dda317ee802779ade786",
    E111_RESIDUAL: "d5731a2260565d09eecc9f90e5eef761b63709622b09e6306ad3959efa50ccf0",
}

EXPECTED_FORMAL = 353
EXPECTED_PRIOR_POSITIVE = 301
EXPECTED_NEW_POSITIVE = 49
EXPECTED_NEGATIVE = 3
TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
EXPECTED_NEGATIVE_STATES = {
    (0, 0, 1, 0, 0, 0, 0, 3),
    (0, 1, 0, 0, 0, 0, 0, 3),
    (1, 0, 0, 0, 0, 0, 0, 3),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def allocation_set(values: Sequence[Sequence[int]]) -> set[tuple[int, ...]]:
    return {tuple(map(int, value)) for value in values}


def replay_positive_witnesses(
    *,
    e095: types.ModuleType,
    prepared: Mapping[str, Any],
    fixed_payload: Mapping[str, Any],
    class_keys: Sequence[tuple[str, str, int, int]],
) -> dict[str, Any]:
    rows_by_global = {
        int(row["global_row_index"]): row
        for row in prepared["rows"]
        if str(row["separator_group"]) == "separator"
    }
    fixed_solid = set(prepared["context"]["fixed_solid"])
    fixed_coverage = set(prepared["context"]["fixed_coverage"])
    pools = prepared["context"]["pools"]
    replayed: list[dict[str, Any]] = []

    for record in fixed_payload["records"]:
        if record["classification"] != "FIXED_STATE_FEASIBLE":
            continue
        state = tuple(map(int, record["allocation_tuple"]))
        witness = record["witness"]
        assignments = [dict(value) for value in witness["selected_assignments"]]
        require(
            len(assignments) == int(witness["selected_body_count"]) == sum(state),
            "E112 positive witness count drift",
        )
        require(
            stable_digest(assignments) == witness["selected_assignment_digest"],
            "E112 positive witness digest drift",
        )

        selected_globals: set[int] = set()
        selected_body_cells: set[tuple[int, int]] = set()
        assignment_sources: list[tuple[dict[str, Any], Mapping[str, Any]]] = []
        for assignment in assignments:
            global_index = int(assignment["global_row_index"])
            require(global_index not in selected_globals, "duplicate positive row")
            selected_globals.add(global_index)
            require(global_index in rows_by_global, "positive row is not separator-live")
            source = rows_by_global[global_index]
            require(
                str(source["template"]) == str(assignment["template"]),
                "positive template transport drift",
            )
            require(
                str(source["body_digest"]) == str(assignment["body_digest"]),
                "positive body-digest transport drift",
            )
            body = tuple(tuple(map(int, value)) for value in assignment["body"])
            require(tuple(source["body"]) == body, "positive body transport drift")
            body_set = set(body)
            require(not selected_body_cells & body_set, "positive body overlap")
            selected_body_cells |= body_set
            require(bool(body_set & fixed_coverage), "positive body unpowered")
            assignment_sources.append((assignment, source))

        class_counts: Counter[tuple[str, str, int, int]] = Counter()
        template_counts: Counter[str] = Counter()
        for assignment, source in assignment_sources:
            pose_index = int(assignment["pose_index"])
            require(pose_index in source["mode_pose_indices"], "positive pose drift")
            class_key = tuple(assignment["class_key"])
            require(class_key in class_keys, "positive class key drift")
            require(class_key[1] == source["template"], "positive class/template drift")
            forced = e095.STABLE_CLASS_BY_BODY.get(str(source["body_digest"]))
            if forced is not None:
                require(
                    (int(class_key[2]), int(class_key[3]))
                    == tuple(map(int, forced)),
                    "positive stable class drift",
                )
            pose = pools[str(source["template"])][pose_index]
            for field, need_key in (
                ("input_port_cells", "need_in"),
                ("output_port_cells", "need_out"),
            ):
                front = tuple(e095.cell(value) for value in pose[field])
                blocked = sum(
                    (not e095.in_grid(value))
                    or value in fixed_solid
                    or value in selected_body_cells
                    for value in front
                )
                require(
                    blocked <= len(front) - int(assignment[need_key]),
                    "positive native-front replay failed",
                )
            class_counts[class_key] += 1
            template_counts[str(source["template"])] += 1

        require(
            tuple(int(class_counts[key]) for key in class_keys) == state,
            "positive allocation replay drift",
        )
        observed_template = tuple(template_counts[template] for template in TEMPLATES)
        require(
            observed_template == tuple(map(int, record["template_vector"])),
            "positive template-vector replay drift",
        )
        replayed.append(
            {
                "allocation_tuple": list(state),
                "template_vector": list(observed_template),
                "selected_body_count": len(assignments),
            }
        )
    require(len(replayed) == EXPECTED_NEW_POSITIVE, "new positive replay count drift")
    return {
        "replayed_positive_count": len(replayed),
        "replayed_positive_digest": stable_digest(
            sorted(tuple(row["allocation_tuple"]) for row in replayed)
        ),
        "records": replayed,
    }


def replay_negative_states(
    *,
    e095: types.ModuleType,
    e111: types.ModuleType,
    e112: types.ModuleType,
    prepared: Mapping[str, Any],
    formal_states: Sequence[tuple[int, ...]],
    class_keys: Sequence[tuple[str, str, int, int]],
    class_caps: Mapping[tuple[str, str, int, int], int],
) -> list[dict[str, Any]]:
    replays: list[dict[str, Any]] = []
    for index, state in enumerate(sorted(EXPECTED_NEGATIVE_STATES)):
        side_model = e112.build_fixed_model(
            e095=e095,
            e111=e111,
            prepared=prepared,
            formal_states=formal_states,
            class_keys=class_keys,
            class_caps=class_caps,
            state=state,
        )
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 112900 + index
        solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
        solver.parameters.symmetry_level = 3
        solver.parameters.cp_model_probing_level = 3
        started = time.monotonic()
        status_code = solver.Solve(side_model["model"])
        elapsed = time.monotonic() - started
        status = solver.StatusName(status_code)
        require(status == "INFEASIBLE", f"negative replay censored: {state}: {status}")
        replays.append(
            {
                "allocation_tuple": list(state),
                "template_vector": list(
                    e111.template_vector_from_allocation(
                        class_keys=class_keys,
                        allocation=state,
                    )
                ),
                "status": status,
                "elapsed_seconds": elapsed,
                "branches": int(solver.NumBranches()),
                "conflicts": int(solver.NumConflicts()),
                "workers": 1,
                "search_branching": "AUTOMATIC_SEARCH",
                "symmetry_level": 3,
                "probing_level": 3,
            }
        )
    return replays


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E112 check: {OUTPUT}")
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E112 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E112 artifact identity drift: {path}")
        artifact_records[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load(RESULT)
    fixed = load(FIXED)
    manifest = load(MANIFEST)
    prior_projection = load(E111_PROJECTION)
    e111_check = load(E111_CHECK)
    residual = load(E111_RESIDUAL)
    require(result["verdict"] == "SEPARATOR_NATIVE_FRONT_RELAXATION_ATLAS_COMPLETE", "verdict drift")
    require(result["decision"] == "BUILD_SIDE_CONDITIONED_SEPARATOR_INTERFACE", "decision drift")
    require(manifest["complete"] is True, "manifest is not complete")
    summary = manifest["summary"]
    require(int(summary["formal_state_count"]) == EXPECTED_FORMAL, "formal count drift")
    require(int(summary["prior_positive_state_count"]) == EXPECTED_PRIOR_POSITIVE, "prior positive drift")
    require(int(summary["new_positive_state_count"]) == EXPECTED_NEW_POSITIVE, "new positive drift")
    require(int(summary["positive_state_count"]) == 350, "total positive drift")
    require(int(summary["negative_state_count"]) == EXPECTED_NEGATIVE, "negative count drift")
    require(int(summary["unknown_state_count"]) == 0, "unknown count drift")
    require(summary["negative_count_by_template_vector"] == {"1/0/3": 3}, "negative template pattern drift")
    require(e111_check["status"] == "PASS", "E111 check drift")

    prior_positive = {
        tuple(map(int, row["allocation_tuple"]))
        for row in prior_projection["records"]
    }
    new_positive = allocation_set(fixed["new_positive_states"])
    negative = allocation_set(fixed["negative_states"])
    unknown = allocation_set(fixed["unknown_states"])
    residual_states = {
        tuple(map(int, row["allocation_tuple"]))
        for row in residual["residual_states"]
    }
    require(len(prior_positive) == EXPECTED_PRIOR_POSITIVE, "prior positive set drift")
    require(len(new_positive) == EXPECTED_NEW_POSITIVE, "new positive set drift")
    require(negative == EXPECTED_NEGATIVE_STATES, "negative state identity drift")
    require(not unknown, "unexpected unknown states")
    require(new_positive | negative == residual_states, "residual partition drift")
    require(not (new_positive & negative), "positive/negative overlap")
    require(
        allocation_set(manifest["positive_states"]) == prior_positive | new_positive,
        "manifest positive set drift",
    )
    require(
        allocation_set(manifest["negative_states"]) == negative,
        "manifest negative set drift",
    )

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e112_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e112_check_e100")
    e110 = source_module(E110_RUNNER, "zmd_e112_check_e110")
    e111 = source_module(E111_RUNNER, "zmd_e112_check_e111")
    e112 = source_module(RUNNER, "zmd_e112_check_runner")
    prepared = e110.restore_three_groups(e095=e095, e100=e100)
    class_caps = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    class_keys = tuple(sorted(class_caps))
    require([list(key) for key in class_keys] == residual["class_order"], "class order drift")
    template_vectors = sorted(
        {
            tuple(map(int, row["vector"]))
            for row in load(E110_PROJECTION)["vectors"]
        }
    )
    formal_states = e111.formal_class_states(
        class_keys=class_keys,
        class_caps=class_caps,
        template_vectors=template_vectors,
    )
    require(len(formal_states) == EXPECTED_FORMAL, "formal basis replay drift")
    require(
        prior_positive | new_positive | negative == set(formal_states),
        "complete formal partition drift",
    )

    positive_replay = replay_positive_witnesses(
        e095=e095,
        prepared=prepared,
        fixed_payload=fixed,
        class_keys=class_keys,
    )
    require(
        positive_replay["replayed_positive_digest"]
        == stable_digest(sorted(new_positive)),
        "new positive replay digest drift",
    )
    negative_replays = replay_negative_states(
        e095=e095,
        e111=e111,
        e112=e112,
        prepared=prepared,
        formal_states=formal_states,
        class_keys=class_keys,
        class_caps=class_caps,
    )

    compact_rule = {
        "template_vector": [1, 0, 3],
        "manufacturing_6x4_5in_1out_count": 3,
        "manufacturing_3x3_total_count": 1,
        "manufacturing_3x3_class": "any_of_three_B_classes",
        "covered_state_count": 3,
        "covered_states": [list(value) for value in sorted(negative)],
    }
    payload = {
        "schema": "zmd_e112_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "COMPLETE_SEPARATOR_RELAXATION_ATLAS_350_POSITIVE_3_NEGATIVE",
        "artifact_records": artifact_records,
        "formal_state_count": EXPECTED_FORMAL,
        "positive_state_count": 350,
        "negative_state_count": 3,
        "unknown_state_count": 0,
        "positive_replay": positive_replay,
        "negative_replays": negative_replays,
        "compact_negative_rule": compact_rule,
        "positive_state_digest": summary["positive_state_digest"],
        "negative_state_digest": summary["negative_state_digest"],
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "The 353-state separator-only relaxation is exactly partitioned. "
            "Three negative tuples are solver-diverse replayed necessary nogoods; "
            "350 positives remain optimistic until low/high occupancy is restored."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "positive_state_count": 350,
                "negative_state_count": 3,
                "negative_rule": compact_rule,
                "decision": payload["decision"],
                "output_path": display(OUTPUT),
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
