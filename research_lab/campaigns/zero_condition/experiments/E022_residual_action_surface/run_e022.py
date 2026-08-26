#!/usr/bin/env python3
"""E022: compare residual boundary-action surfaces across the E021 beam."""

from __future__ import annotations

from collections import defaultdict
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

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / "research_lab/local/zero_condition/E022_residual_action_surface/run-003"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E021_ROOT = ROOT / "research_lab/local/zero_condition/E021_fifth_step_class_probe/run-001"
E021_RESULT = E021_ROOT / "RESULT.json"
E021_MANIFEST = E021_ROOT / "CLASS_BEAM_MANIFEST.json"
E021_FACE = E021_ROOT / "OPTIMUM_FACE_AUDIT.json"
E021_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E021_fifth_step_class_probe/run_e021.py"
)
E013_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E013_residual_boundary_coverage/run_e013.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "262100",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}

EXPECTED_HASHES: dict[Path, str] = {
    E021_RESULT: "bf582d3a86b8308a8816b447b4b484f7d64044988003236a41fa384457e2bdb9",
    E021_MANIFEST: "abb73768c4b4590d31f9c9dc055a04c8bede775f2ce508c76fe989a4e2605787",
    E021_FACE: "bc6e729eaf6d25caa35560be0f514e820162ff91c1bfde344c2d0a937e1b099f",
    E021_RUNNER: "e3a346a635c1de009bd9bb60208530eb3af93491971b3030454faf52d1f15b0d",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E021_ROOT / "CLASS_01.json": "fb374531a73ae8663d57eee089dfc8b0aeb6c91ce4586aeab9d23c4ce3adc911",
    E021_ROOT / "CLASS_02.json": "658be8db4f1050ed3f8de2ec99f9f7d4dac495387ceba9b59eaa0106d5457d6c",
    E021_ROOT / "CLASS_03.json": "670e774e44cbdc3bdef788f40d3c8fdbe16d91ce6c3990346dfe2fca4e513ea1",
    E021_ROOT / "CLASS_04.json": "0261299f100a91827f8bf9a96b586729d4225106cab985c09045bb3be2bfb639",
}

TOP_LIMIT = 40
SET_COVER_BUDGETS = (1, 2, 4)


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


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E022 must run on research/main")
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
    result = load_json(E021_RESULT)
    if result.get("verdict") != "FIFTH_STEP_CLASS_INVARIANT_IMPROVEMENT":
        raise RuntimeError("E021 verdict drift")
    if int(result["branch_response"]["best_child_objective"]) != 173:
        raise RuntimeError("E021 objective drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output("status", "--porcelain=v1", "--untracked-files=no"),
    }


def reconstruct_retained_states(
    *,
    e001: Any,
    e004: Any,
    e014: Any,
    e017: Any,
    e019: Any,
    e021: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    pair_solution = e017.load_pair_solution()
    seeds = e019.seed_records()
    e020 = load_json(e021.E020_RESULT)
    class_parents = [
        dict(row)
        for row in e020["retained_beam"]
        if int(row["objective"]) == e021.PARENT_OBJECTIVE
    ]
    e021_result = load_json(E021_RESULT)
    retained_by_class = {
        int(row["provenance"]["parent_class_index"]): dict(row)
        for row in e021_result["retained_class_beam"]
    }
    if set(retained_by_class) != {1, 2, 3, 4}:
        raise RuntimeError("E021 retained class index surface drift")

    reconstructed: list[dict[str, Any]] = []
    for class_index, class_state in enumerate(class_parents, 1):
        parent_solution = e021.reconstruct_parent_solution(
            class_state=class_state,
            seeds=seeds,
            pair_solution=pair_solution,
            inputs=inputs,
            e014=e014,
            e017=e017,
        )
        checkpoint = load_json(E021_ROOT / f"CLASS_{class_index:02d}.json")
        retained = retained_by_class[class_index]
        matches = [
            dict(record)
            for record in checkpoint["candidate_records"]
            if str(record["candidate_solution_digest"])
            == str(retained["placement_digest"])
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"E022 retained child lookup drift for class {class_index}: "
                f"{len(matches)}"
            )
        record = matches[0]
        solution = e017.reconstruct_candidate(
            arm=checkpoint,
            record=record,
            pair_solution=parent_solution,
            inputs=inputs,
            e014=e014,
        )
        if stable_digest(solution) != str(retained["placement_digest"]):
            raise RuntimeError(f"E022 placement reconstruction drift class {class_index}")
        compact_shared = dict(record["shared_binding"])
        if int(compact_shared["objective"]) != 173:
            raise RuntimeError(f"E022 shared objective drift class {class_index}")
        if str(compact_shared["selection_digest"]) != str(
            retained["binding_selection_digest"]
        ):
            raise RuntimeError(f"E022 selection reconstruction drift class {class_index}")
        from src.models.routing_binding_context import build_routing_binding_context

        routing_context = build_routing_binding_context(
            solution,
            inputs["pools"],
            70,
            70,
        )
        compact_shared["mismatch_boundaries"] = {
            commodity: [
                e004.boundary_profile(
                    component=int(component),
                    routing_context=routing_context,
                    solution=solution,
                )
                for component in compact_shared["selected_components"][commodity][
                    "mismatch_components"
                ]
            ]
            for commodity in sorted(compact_shared["selected_components"])
        }
        shared = compact_shared
        reconstructed.append(
            {
                "class_index": class_index,
                "retained_state": retained,
                "solution": solution,
                "shared_binding": shared,
            }
        )
    return inputs, reconstructed


def build_state_surface(
    *,
    state: Mapping[str, Any],
    group_by_instance: Mapping[str, str],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    e013: Any,
) -> dict[str, Any]:
    class_index = int(state["class_index"])
    solution = state["solution"]
    shared = state["shared_binding"]
    selected_components = shared["selected_components"]
    mismatch_boundaries = shared["mismatch_boundaries"]

    observations: list[dict[str, Any]] = []
    literals: dict[str, dict[str, Any]] = {}
    observation_ids_by_literal: dict[str, set[int]] = defaultdict(set)
    for commodity in sorted(mismatch_boundaries):
        selected = selected_components[commodity]
        source_only = {int(value) for value in selected["source_only_components"]}
        sink_only = {int(value) for value in selected["sink_only_components"]}
        for boundary in mismatch_boundaries[commodity]:
            component_id = int(boundary["component_id"])
            if component_id in source_only and component_id not in sink_only:
                role = "source_only"
            elif component_id in sink_only and component_id not in source_only:
                role = "sink_only"
            else:
                raise RuntimeError(
                    f"E022 mismatch role drift class={class_index} "
                    f"commodity={commodity} component={component_id}"
                )
            observation_id = len(observations)
            literal_keys: set[str] = set()
            for owner in boundary["boundary_owners"]:
                key, payload = e013.literal_identity(
                    owner=owner,
                    solution=solution,
                    group_by_instance=group_by_instance,
                    facility_pools=facility_pools,
                )
                existing = literals.get(key)
                if existing is None:
                    literals[key] = payload
                else:
                    existing["source_instance_ids"] = sorted(
                        set(existing["source_instance_ids"])
                        | set(payload["source_instance_ids"])
                    )
                    for field in (
                        "kind",
                        "consumer_id",
                        "facility_type",
                        "operation_type",
                        "pose_idx",
                        "pose_id",
                        "occupied_cells",
                    ):
                        if existing[field] != payload[field]:
                            raise RuntimeError(
                                f"E022 literal transport drift class={class_index} "
                                f"key={key} field={field}"
                            )
                literal_keys.add(key)
            observations.append(
                {
                    "observation_id": observation_id,
                    "commodity": commodity,
                    "component_id": component_id,
                    "component_size": int(boundary["component_size"]),
                    "role": role,
                    "literal_keys": sorted(literal_keys),
                    "boundary_owner_count": int(boundary["boundary_owner_count"]),
                }
            )
            for key in literal_keys:
                observation_ids_by_literal[key].add(observation_id)

    expected = int(shared["objective"])
    if len(observations) != expected:
        raise RuntimeError(
            f"E022 observation count drift class={class_index}: "
            f"{len(observations)} != {expected}"
        )
    ranking = sorted(
        (
            {
                **json_safe(payload),
                "observation_count": len(observation_ids_by_literal[key]),
            }
            for key, payload in literals.items()
        ),
        key=lambda row: (-int(row["observation_count"]), str(row["literal_key"])),
    )
    rank_by_literal = {
        str(row["literal_key"]): index
        for index, row in enumerate(ranking, 1)
    }
    exact_cover = [
        e013.exact_max_coverage(
            observations=observations,
            literals=literals,
            observation_ids_by_literal=observation_ids_by_literal,
            budget=budget,
        )
        for budget in SET_COVER_BUDGETS
    ]
    return {
        "class_index": class_index,
        "retained_state": json_safe(state["retained_state"]),
        "observation_count": len(observations),
        "literal_count": len(literals),
        "observation_manifest_digest": stable_digest(observations),
        "literal_manifest_digest": stable_digest(literals),
        "ranking_digest": stable_digest(
            [
                (str(row["literal_key"]), int(row["observation_count"]))
                for row in ranking
            ]
        ),
        "top_literals": ranking[:TOP_LIMIT],
        "rank_by_literal": rank_by_literal,
        "coverage_by_literal": {
            key: len(observation_ids_by_literal[key])
            for key in sorted(observation_ids_by_literal)
        },
        "literal_payloads": json_safe(literals),
        "exact_coverage_by_budget": exact_cover,
    }


def set_jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def compare_surfaces(surfaces: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pairwise: list[dict[str, Any]] = []
    for left_index in range(len(surfaces)):
        for right_index in range(left_index + 1, len(surfaces)):
            left = surfaces[left_index]
            right = surfaces[right_index]
            row: dict[str, Any] = {
                "left_class": int(left["class_index"]),
                "right_class": int(right["class_index"]),
                "same_ranking_digest": (
                    str(left["ranking_digest"]) == str(right["ranking_digest"])
                ),
            }
            for limit in (10, 20):
                left_set = {
                    str(item["literal_key"])
                    for item in left["top_literals"][:limit]
                }
                right_set = {
                    str(item["literal_key"])
                    for item in right["top_literals"][:limit]
                }
                row[f"top_{limit}_intersection_count"] = len(left_set & right_set)
                row[f"top_{limit}_jaccard"] = set_jaccard(left_set, right_set)
            pairwise.append(row)

    common_keys = set.intersection(
        *(set(surface["coverage_by_literal"]) for surface in surfaces)
    )
    common_rows: list[dict[str, Any]] = []
    first_payloads = surfaces[0]["literal_payloads"]
    for key in sorted(common_keys):
        payload = dict(first_payloads[key])
        counts: dict[str, int] = {}
        ranks: dict[str, int] = {}
        for surface in surfaces:
            class_key = str(surface["class_index"])
            counts[class_key] = int(surface["coverage_by_literal"][key])
            ranks[class_key] = int(surface["rank_by_literal"][key])
            other_payload = surface["literal_payloads"][key]
            for field in (
                "kind",
                "consumer_id",
                "facility_type",
                "operation_type",
                "pose_idx",
                "pose_id",
                "occupied_cells",
            ):
                if payload[field] != other_payload[field]:
                    raise RuntimeError(
                        f"E022 common literal payload drift key={key} field={field}"
                    )
        values = list(counts.values())
        common_rows.append(
            {
                **json_safe(payload),
                "coverage_by_class": counts,
                "rank_by_class": ranks,
                "minimum_coverage": min(values),
                "maximum_coverage": max(values),
                "coverage_range": max(values) - min(values),
                "total_coverage": sum(values),
            }
        )
    common_rows.sort(
        key=lambda row: (
            -int(row["minimum_coverage"]),
            -int(row["total_coverage"]),
            int(row["coverage_range"]),
            str(row["literal_key"]),
        )
    )

    leaders = [str(surface["top_literals"][0]["literal_key"]) for surface in surfaces]
    top10_intersection = set.intersection(
        *(
            {
                str(row["literal_key"])
                for row in surface["top_literals"][:10]
            }
            for surface in surfaces
        )
    )
    if len(set(leaders)) == 1:
        verdict = "RESIDUAL_ACTION_SURFACE_COMMON_LEADER"
    elif top10_intersection:
        verdict = "RESIDUAL_ACTION_SURFACE_SHARED_PORTFOLIO"
    else:
        verdict = "RESIDUAL_ACTION_SURFACE_DIVERGENT"
    return {
        "verdict": verdict,
        "leader_by_class": {
            str(surface["class_index"]): leaders[index]
            for index, surface in enumerate(surfaces)
        },
        "distinct_leader_count": len(set(leaders)),
        "common_literal_count": len(common_keys),
        "common_top10_literals": sorted(top10_intersection),
        "common_top10_count": len(top10_intersection),
        "robust_common_ranking": common_rows[:TOP_LIMIT],
        "selected_common_action": common_rows[0] if common_rows else None,
        "pairwise_overlap": pairwise,
        "all_ranking_digests_equal": len(
            {str(surface["ranking_digest"]) for surface in surfaces}
        )
        == 1,
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    started = time.monotonic()
    e013 = import_module("zmd_e022_e013", E013_RUNNER)
    e021 = import_module("zmd_e022_e021", E021_RUNNER)
    e021_identity = e021.verify_identity()
    e001 = import_module("zmd_e022_e001", e021.E001_RUNNER)
    e004 = import_module("zmd_e022_e004", e021.E004_RUNNER)
    e014 = import_module("zmd_e022_e014", e021.E014_RUNNER)
    e017 = import_module("zmd_e022_e017", e021.E017_RUNNER)
    e019 = import_module("zmd_e022_e019", e021.E019_RUNNER)

    inputs, states = reconstruct_retained_states(
        e001=e001,
        e004=e004,
        e014=e014,
        e017=e017,
        e019=e019,
        e021=e021,
    )
    group_by_instance = e013.group_mapping(inputs["instances"])
    surfaces = [
        build_state_surface(
            state=state,
            group_by_instance=group_by_instance,
            facility_pools=inputs["pools"],
            e013=e013,
        )
        for state in states
    ]
    comparison = compare_surfaces(surfaces)
    return {
        "schema": "zmd_zero_condition_e022_residual_action_surface_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "e021_dependency_identity": e021_identity,
        "state_count": len(surfaces),
        "parent_objective": 173,
        "state_surfaces": surfaces,
        "comparison": comparison,
        "verdict": comparison["verdict"],
        "decision_reading": {
            "selected_next_common_action": (
                comparison["selected_common_action"]["literal_key"]
                if comparison["selected_common_action"] is not None
                else None
            ),
            "action_specific_quotient_only": True,
            "next_step": (
                "cross-state exact replay of the robust common leader"
                if comparison["selected_common_action"] is not None
                else "state-specific expansion or simultaneous multi-pose neighborhood"
            ),
        },
        "routing_solver_run": False,
        "truth_boundary": (
            "Residual boundary-touch action surfaces of four fixed objective-173 "
            "shared-binding witnesses. Coverage proposes actions but does not prove "
            "mobility, repair, or routing feasibility."
        ),
        "ledger_effect": "none",
        "elapsed_seconds": time.monotonic() - started,
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E022 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "leaders": result["comparison"]["leader_by_class"],
                    "common_top10_count": result["comparison"]["common_top10_count"],
                    "selected_common_action": result["decision_reading"][
                        "selected_next_common_action"
                    ],
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
            "schema": "zmd_zero_condition_e022_residual_action_surface_failure_v1",
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
