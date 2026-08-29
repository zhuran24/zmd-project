#!/usr/bin/env python3
"""Independent replay and residual extraction for E111."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import types
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e111.py"
RUN_ROOT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E111_separator_native_front_class_atlas"
)
RUN1 = RUN_ROOT / "run-001"
RUN2 = RUN_ROOT / "run-002"
RUN3 = RUN_ROOT / "run-003"
FAILURE1 = RUN1 / "FAILURE.json"
RESULT2 = RUN2 / "RESULT.json"
PROJECTION2 = RUN2 / "SEPARATOR_CLASS_PROJECTION.json"
AUDIT2 = RUN2 / "COUPLING_AUDIT.json"
RESULT3 = RUN3 / "RESULT.json"
PROJECTION3 = RUN3 / "SEPARATOR_CLASS_PROJECTION.json"
AUDIT3 = RUN3 / "COUPLING_AUDIT.json"
OUTPUT = RUN3 / "ARTIFACT_CHECK.json"
RESIDUAL = RUN3 / "RESIDUAL_CLASS_STATES.json"
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

EXPECTED = {
    RUNNER: "ea0ce5442c485b6c992b2ec27edb86b18bfc6354bb22e0295909ee5813b435e4",
    FAILURE1: "85c74a0e3b7a99e237c37202362d1fb70836aca776a894cafcbaa1e485aca81a",
    RESULT2: "67fbfb932f0ce7f3965f6bdc9d8e6fd983603d81161ba199a7325707b8a49a30",
    PROJECTION2: "8d2f1feeee44f8fb03e436e6baa8060362e49b960b35e253b9a15c63dcf09c6b",
    AUDIT2: "5b72f4323b9f602955b187d26ed2567ddebeb818a3bb2b29065c7f58d2e4fe3c",
    RESULT3: "044863b79194b591156ee991e78519aecb101553b98d9aaa27bf8e2d81a6cbad",
    PROJECTION3: "58d8a27697ae03612ce770afece3d0bf395fb2dd8e7c6ad9a92163222ba5464c",
    AUDIT3: "880476606673319b3b869c31c5957094855f4c6240c78de97afa52b8b65903b6",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E110_RUNNER: "30b2fc298ef56ba68053d47977ef139890e862568b53bba70bdf541f677a1fea",
    E110_PROJECTION: "73570c931c8e8c053ec5a17feaa821e4e69511443882eac01110b470a6537413",
}
EXPECTED_FORMAL = 353
EXPECTED_RUN2 = 168
EXPECTED_RUN3 = 301
EXPECTED_RESIDUAL = 52
TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)


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


def allocation_set(payload: Mapping[str, Any]) -> set[tuple[int, ...]]:
    return {
        tuple(map(int, record["allocation_tuple"]))
        for record in payload["records"]
    }


def replay_coupling_audit(
    *,
    e095: types.ModuleType,
    e111: types.ModuleType,
    prepared: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    replay = e111.coupling_audit(e095=e095, prepared=prepared)
    for key in (
        "candidate_counts",
        "body_union_cell_counts",
        "front_union_cell_counts",
        "body_body_intersections",
        "front_body_intersections",
        "front_front_intersections",
    ):
        require(replay[key] == expected[key], f"coupling audit drift: {key}")
    return {
        key: replay[key]
        for key in (
            "candidate_counts",
            "body_body_intersections",
            "front_body_intersections",
            "front_front_intersections",
        )
    }


def replay_witnesses(
    *,
    e095: types.ModuleType,
    prepared: Mapping[str, Any],
    projection: Mapping[str, Any],
    class_keys: Sequence[tuple[str, str, int, int]],
    formal_states: set[tuple[int, ...]],
) -> dict[str, Any]:
    rows_by_global = {
        int(row["global_row_index"]): row
        for row in prepared["rows"]
        if str(row["separator_group"]) == "separator"
    }
    fixed_solid = set(prepared["context"]["fixed_solid"])
    fixed_coverage = set(prepared["context"]["fixed_coverage"])
    pools = prepared["context"]["pools"]
    records: list[dict[str, Any]] = []
    seen: set[tuple[int, ...]] = set()

    for record in projection["records"]:
        allocation = tuple(map(int, record["allocation_tuple"]))
        require(allocation in formal_states, "producer state outside formal basis")
        require(allocation not in seen, "duplicate producer state")
        seen.add(allocation)
        witness = record["witness"]
        assignments = [dict(value) for value in witness["selected_assignments"]]
        require(
            len(assignments) == int(witness["selected_body_count"]) == sum(allocation),
            "selected assignment count drift",
        )
        require(
            stable_digest(assignments) == witness["selected_assignment_digest"],
            "selected assignment digest drift",
        )
        class_counts: Counter[tuple[str, str, int, int]] = Counter()
        template_counts: Counter[str] = Counter()
        selected_body_cells: set[tuple[int, int]] = set()
        selected_globals: set[int] = set()
        assignment_sources: list[tuple[dict[str, Any], Mapping[str, Any]]] = []

        for assignment in assignments:
            global_index = int(assignment["global_row_index"])
            require(global_index not in selected_globals, "duplicate selected row")
            selected_globals.add(global_index)
            require(global_index in rows_by_global, "selected row not separator-live")
            source = rows_by_global[global_index]
            require(
                str(source["template"]) == str(assignment["template"]),
                "template transport drift",
            )
            require(
                str(source["body_digest"]) == str(assignment["body_digest"]),
                "body digest transport drift",
            )
            body = tuple(tuple(map(int, value)) for value in assignment["body"])
            require(tuple(source["body"]) == body, "body transport drift")
            body_set = set(body)
            require(
                not selected_body_cells & body_set,
                "selected separator body overlap",
            )
            selected_body_cells |= body_set
            require(
                bool(body_set & fixed_coverage),
                "selected separator body unpowered",
            )
            assignment_sources.append((assignment, source))

        for assignment, source in assignment_sources:
            pose_index = int(assignment["pose_index"])
            require(pose_index in source["mode_pose_indices"], "pose transport drift")
            class_key = tuple(assignment["class_key"])
            require(class_key in class_keys, "unknown class key")
            require(class_key[1] == source["template"], "class/template drift")
            forced = e095.STABLE_CLASS_BY_BODY.get(str(source["body_digest"]))
            if forced is not None:
                require(
                    (int(class_key[2]), int(class_key[3]))
                    == tuple(map(int, forced)),
                    "stable class drift",
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
                    "separator native-front replay failed",
                )
            class_counts[class_key] += 1
            template_counts[str(source["template"])] += 1

        observed_allocation = tuple(int(class_counts[key]) for key in class_keys)
        require(observed_allocation == allocation, "allocation witness drift")
        observed_template = tuple(template_counts[template] for template in TEMPLATES)
        require(
            observed_template == tuple(map(int, record["template_vector"])),
            "template-vector witness drift",
        )
        require(
            observed_template == tuple(map(int, witness["template_vector"])),
            "witness template-vector drift",
        )
        records.append(
            {
                "allocation_tuple": list(allocation),
                "template_vector": list(observed_template),
                "selected_body_count": len(assignments),
                "selected_body_cell_count": len(selected_body_cells),
            }
        )
    return {
        "replayed_state_count": len(records),
        "replayed_state_digest": stable_digest(sorted(seen)),
        "records": records,
    }


def main() -> int:
    if OUTPUT.exists() or RESIDUAL.exists():
        raise FileExistsError("refusing to overwrite E111 checker outputs")
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E111 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E111 artifact identity drift: {path}")
        artifact_records[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    failure = load(FAILURE1)
    require(failure["status"] == "NATIVE_ABORT_BEFORE_TERMINAL_OUTPUT", "run-001 failure status drift")
    require(failure["error"] == "OR_TOOLS_CHECK_FAILURE", "run-001 failure identity drift")
    result2 = load(RESULT2)
    result3 = load(RESULT3)
    projection2 = load(PROJECTION2)
    projection3 = load(PROJECTION3)
    audit2 = load(AUDIT2)
    audit3 = load(AUDIT3)
    require(result2["verdict"] == "SEPARATOR_NATIVE_FRONT_RELAXATION_ATLAS_CENSORED", "run-002 verdict drift")
    require(result3["verdict"] == "SEPARATOR_NATIVE_FRONT_RELAXATION_ATLAS_CENSORED", "run-003 verdict drift")
    require(projection2["complete"] is False and projection2["terminal_status"] == "UNKNOWN", "run-002 terminal drift")
    require(projection3["complete"] is False and projection3["terminal_status"] == "UNKNOWN", "run-003 terminal drift")
    states2 = allocation_set(projection2)
    states3 = allocation_set(projection3)
    require(len(states2) == EXPECTED_RUN2, "run-002 state count drift")
    require(len(states3) == EXPECTED_RUN3, "run-003 state count drift")
    require(states2 <= states3, "run-002 is not a state prefix subset")

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e111_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e111_check_e100")
    e110 = source_module(E110_RUNNER, "zmd_e111_check_e110")
    e111 = source_module(RUNNER, "zmd_e111_check_runner")
    prepared = e110.restore_three_groups(e095=e095, e100=e100)
    class_caps = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    class_keys = tuple(sorted(class_caps))
    template_vectors = sorted(
        {
            tuple(map(int, record["vector"]))
            for record in load(E110_PROJECTION)["vectors"]
        }
    )
    formal_states = set(
        e111.formal_class_states(
            class_keys=class_keys,
            class_caps=class_caps,
            template_vectors=template_vectors,
        )
    )
    require(len(formal_states) == EXPECTED_FORMAL, "formal state count drift")
    require(states3 <= formal_states, "run-003 contains nonformal state")

    coupling_replay = replay_coupling_audit(
        e095=e095,
        e111=e111,
        prepared=prepared,
        expected=audit3,
    )
    require(
        {
            key: audit2[key]
            for key in (
                "candidate_counts",
                "body_body_intersections",
                "front_body_intersections",
                "front_front_intersections",
            )
        }
        == coupling_replay,
        "run-002/run-003 coupling audit drift",
    )
    witness_replay = replay_witnesses(
        e095=e095,
        prepared=prepared,
        projection=projection3,
        class_keys=class_keys,
        formal_states=formal_states,
    )
    require(
        witness_replay["replayed_state_digest"] == projection3["state_digest"],
        "replayed state digest drift",
    )

    residual_states = sorted(formal_states - states3)
    require(len(residual_states) == EXPECTED_RESIDUAL, "residual state count drift")
    residual_payload = {
        "schema": "zmd_e111_residual_separator_class_states_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "OPEN",
        "formal_state_count": len(formal_states),
        "positive_state_count": len(states3),
        "residual_state_count": len(residual_states),
        "class_order": [list(key) for key in class_keys],
        "residual_states": [
            {
                "allocation_tuple": list(state),
                "template_vector": list(
                    e111.template_vector_from_allocation(
                        class_keys=class_keys,
                        allocation=state,
                    )
                ),
            }
            for state in residual_states
        ],
        "residual_state_digest": stable_digest(residual_states),
        "source_projection": {
            "path": display(PROJECTION3),
            "sha256": sha256(PROJECTION3),
        },
        "truth_boundary": (
            "These 52 states are unresolved because run-003 stopped UNKNOWN after "
            "finding 301 positives. They are not negative."
        ),
    }
    dump_exclusive(RESIDUAL, residual_payload)

    payload = {
        "schema": "zmd_e111_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "THREE_HUNDRED_ONE_SEPARATOR_STATES_REPLAYED_FIFTY_TWO_UNRESOLVED",
        "artifact_records": artifact_records,
        "apparatus_failure": {
            "path": display(FAILURE1),
            "sha256": sha256(FAILURE1),
            "scientific_effect": "none",
        },
        "run_progression": {
            "run_002_positive_state_count": len(states2),
            "run_003_positive_state_count": len(states3),
            "run_002_subset_run_003": True,
            "formal_state_count": len(formal_states),
            "residual_state_count": len(residual_states),
        },
        "coupling_replay": coupling_replay,
        "witness_replay": witness_replay,
        "residual_state_file": {
            "path": display(RESIDUAL),
            "sha256": sha256(RESIDUAL),
            "residual_state_count": len(residual_states),
            "residual_state_digest": residual_payload["residual_state_digest"],
        },
        "verdict": result3["verdict"],
        "decision": "FIX_AND_CLASSIFY_ONLY_FIFTY_TWO_RESIDUAL_STATES",
        "truth_boundary": (
            "All 301 positives are independently replayed in the optimistic "
            "separator-only model. The remaining 52 formal states are unresolved, "
            "not absent. Side compatibility is outside E111."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "positive_state_count": len(states3),
                "residual_state_count": len(residual_states),
                "decision": payload["decision"],
                "output_path": display(OUTPUT),
                "output_sha256": sha256(OUTPUT),
                "residual_path": display(RESIDUAL),
                "residual_sha256": sha256(RESIDUAL),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
