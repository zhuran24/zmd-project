#!/usr/bin/env python3
"""E029: derive the residual operation-to-footprint swap surface at objective 166."""

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
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E029_operation_assignment_surface/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E028_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E028_static_coupling_pair/run-001/RESULT.json"
)
E028_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E028_static_coupling_pair/run-001/BEST_PAIR_ASSIGNMENT.json"
)
E028_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E028_static_coupling_pair/run-001/BEST_PAIR_LAYOUT.json"
)
E028_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E028_static_coupling_pair/run-001/BEST_PAIR_ENDPOINT.json"
)
E022_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E022_residual_action_surface/run-003/RESULT.json"
)
E025_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E025_live_beam_residual_surface/run-004/RESULT.json"
)
E013_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E013_residual_boundary_coverage/run_e013.py"
)
E022_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E022_residual_action_surface/run_e022.py"
)
E028_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E028_static_coupling_pair/run_e028.py"
)

EXPECTED_HASHES: dict[Path, str] = {
    E028_RESULT: "38901057591ffe6f3e3d8e0b00045e7facc86abc4f307dd46a9604c38c4a7c41",
    E028_ASSIGNMENT: "02383c24dfc4528714cb371c6d07b38481dabcfaa6868cdbe65002a9a30b8b95",
    E028_LAYOUT: "d700ff3b124bd1fdcf75c35a82f890aa4f36d002238754ecd05db742418a7abc",
    E028_ENDPOINT: "5c0089cfd1cb4376ebfe1da361142705a352b1f7507b0ce390248f6facd54a97",
    E022_RESULT: "d43463034c81d1ce4185f76312a25173e880da9744bcc5bd2023e4610a1e6e83",
    E025_RESULT: "3a2d076ba283ccfaf946c772cbbc25a530b14849bcd433516965edc3b7670c5a",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E022_RUNNER: "060440bd8b5ba2cba7647987fa30bed7b08e8d8ca155d9ddcaed6cd276e09507",
    E028_RUNNER: "ec94e662d29f8a856a31018c7ef89acc2e4b1568d97b1b9d1d33ce8e407517a5",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
}

OBJECTIVE = 166
PORTFOLIO_SIZE = 12
MAX_PORTFOLIO_USES_PER_LITERAL = 3
REVERSE_E028_PAIR = frozenset(
    {
        "mandatory::group::manufacturing_6x4::packaging_battery::17::6049",
        "mandatory::group::manufacturing_6x4::grinder_dense_blue_iron::14::6189",
    }
)
SWAPPABLE_FACILITY_TYPES = {
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
}


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
        raise RuntimeError("E029 must run on research/main")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("PYTHONHASHSEED must be 0")
    unexpected_exact = sorted(key for key in os.environ if key.startswith("EXACT_"))
    if unexpected_exact:
        raise RuntimeError(f"unexpected EXACT_* environment: {unexpected_exact}")
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
    result = load_json(E028_RESULT)
    if result.get("verdict") != "SIMULTANEOUS_PAIR_MATERIAL_IMPROVEMENT":
        raise RuntimeError("E028 trigger verdict drift")
    if int(result["best_child"]["objective"]) != OBJECTIVE:
        raise RuntimeError("E028 objective drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output(
            "status", "--porcelain=v1", "--untracked-files=no"
        ),
    }


def load_state() -> tuple[
    dict[str, dict[str, Any]],
    dict[str, Any],
    Mapping[str, Sequence[Mapping[str, Any]]],
    list[Mapping[str, Any]],
]:
    assignment = load_json(E028_ASSIGNMENT)
    layout = load_json(E028_LAYOUT)
    endpoint = load_json(E028_ENDPOINT)
    raw = assignment.get("solution")
    placements = layout.get("placements")
    if not isinstance(raw, Mapping) or not isinstance(placements, list):
        raise RuntimeError("E028 assignment/layout structure drift")
    solution = {
        str(instance_id): dict(row)
        for instance_id, row in raw.items()
        if isinstance(row, Mapping)
    }
    layout_solution = {
        str(row["instance_id"]): dict(row)
        for row in placements
        if isinstance(row, Mapping)
    }
    if json_safe(solution) != json_safe(layout_solution):
        raise RuntimeError("E028 assignment/layout content drift")
    result = load_json(E028_RESULT)
    if stable_digest(solution) != str(result["best_child"]["placement_digest"]):
        raise RuntimeError("E028 placement digest drift")
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != OBJECTIVE:
        raise RuntimeError("E028 endpoint objective drift")
    if str(endpoint["selection_digest"]) != str(
        result["best_child"]["binding_selection_digest"]
    ):
        raise RuntimeError("E028 endpoint selection digest drift")
    candidate_payload = load_json(
        HISTORY_ROOT / "data/preprocessed/candidate_placements.json"
    )
    pools = candidate_payload.get("facility_pools")
    if not isinstance(pools, Mapping):
        raise RuntimeError("candidate placement pools drift")
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    if not isinstance(mandatory, list):
        raise RuntimeError("mandatory instances drift")
    return solution, endpoint, pools, mandatory


def build_incidence(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    endpoint: Mapping[str, Any],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    group_by_instance: Mapping[str, str],
    e013: Any,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, set[int]]]:
    selected_components = endpoint["selected_components"]
    mismatch_boundaries = endpoint["mismatch_boundaries"]
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
                    f"E029 mismatch role drift: {commodity} component {component_id}"
                )
            observation_id = len(observations)
            literal_keys: set[str] = set()
            for owner in boundary["boundary_owners"]:
                key, payload = e013.literal_identity(
                    owner=owner,
                    solution=solution,
                    group_by_instance=group_by_instance,
                    facility_pools=pools,
                )
                existing = literals.get(key)
                if existing is None:
                    literals[key] = payload
                else:
                    existing["source_instance_ids"] = sorted(
                        set(existing["source_instance_ids"])
                        | set(payload["source_instance_ids"])
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
    if len(observations) != OBJECTIVE:
        raise RuntimeError(
            f"E029 observation count drift: {len(observations)} != {OBJECTIVE}"
        )
    return observations, literals, observation_ids_by_literal


def swap_candidates(
    *,
    literals: Mapping[str, Mapping[str, Any]],
    observation_ids_by_literal: Mapping[str, set[int]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = [
        (key, dict(payload))
        for key, payload in literals.items()
        if str(payload.get("kind")) == "mandatory_group_pose"
        and str(payload.get("facility_type")) in SWAPPABLE_FACILITY_TYPES
        and len(payload.get("source_instance_ids", [])) == 1
    ]
    rows: list[dict[str, Any]] = []
    for left_index in range(len(eligible)):
        left_key, left = eligible[left_index]
        for right_index in range(left_index + 1, len(eligible)):
            right_key, right = eligible[right_index]
            if str(left["facility_type"]) != str(right["facility_type"]):
                continue
            if str(left["operation_type"]) == str(right["operation_type"]):
                continue
            pair_set = frozenset({left_key, right_key})
            left_obs = set(observation_ids_by_literal.get(left_key, set()))
            right_obs = set(observation_ids_by_literal.get(right_key, set()))
            union = left_obs | right_obs
            intersection = left_obs & right_obs
            rows.append(
                {
                    "pair_key": " <-> ".join(sorted(pair_set)),
                    "left_literal": left_key,
                    "right_literal": right_key,
                    "left": json_safe(left),
                    "right": json_safe(right),
                    "facility_type": str(left["facility_type"]),
                    "union_coverage": len(union),
                    "overlap_coverage": len(intersection),
                    "left_coverage": len(left_obs),
                    "right_coverage": len(right_obs),
                    "coverage_fraction": len(union) / OBJECTIVE,
                    "returns_known_e028_parent": pair_set == REVERSE_E028_PAIR,
                    "union_observation_digest": stable_digest(sorted(union)),
                }
            )
    rows.sort(
        key=lambda row: (
            -int(row["union_coverage"]),
            int(row["overlap_coverage"]),
            -min(int(row["left_coverage"]), int(row["right_coverage"])),
            str(row["pair_key"]),
        )
    )

    portfolio: list[dict[str, Any]] = []
    use_count: dict[str, int] = defaultdict(int)
    for row in rows:
        if row["returns_known_e028_parent"]:
            continue
        left = str(row["left_literal"])
        right = str(row["right_literal"])
        if (
            use_count[left] >= MAX_PORTFOLIO_USES_PER_LITERAL
            or use_count[right] >= MAX_PORTFOLIO_USES_PER_LITERAL
        ):
            continue
        selected = dict(row)
        selected["portfolio_rank"] = len(portfolio) + 1
        portfolio.append(selected)
        use_count[left] += 1
        use_count[right] += 1
        if len(portfolio) >= PORTFOLIO_SIZE:
            break
    if not portfolio:
        raise RuntimeError("E029 produced no operation-swap portfolio")
    return rows, portfolio


def run() -> dict[str, Any]:
    identity = verify_identity()
    started = time.monotonic()
    e013 = import_module("zmd_e029_e013", E013_RUNNER)
    e022 = import_module("zmd_e029_e022", E022_RUNNER)

    solution, endpoint, pools, mandatory = load_state()
    group_by_instance = e013.group_mapping(mandatory)
    state = {
        "class_index": 166,
        "retained_state": {
            "objective": OBJECTIVE,
            "placement_digest": stable_digest(solution),
            "binding_selection_digest": endpoint["selection_digest"],
            "free_cell_set_digest": endpoint["morphology"]["free_cell_set_digest"],
            "source": "E028 simultaneous operation-swap child",
        },
        "solution": solution,
        "shared_binding": endpoint,
    }
    surface = e022.build_state_surface(
        state=state,
        group_by_instance=group_by_instance,
        facility_pools=pools,
        e013=e013,
    )
    observations, literals, observation_ids_by_literal = build_incidence(
        solution=solution,
        endpoint=endpoint,
        pools=pools,
        group_by_instance=group_by_instance,
        e013=e013,
    )
    if str(surface["observation_manifest_digest"]) != stable_digest(observations):
        raise RuntimeError("E029 observation manifest drift")
    if str(surface["literal_manifest_digest"]) != stable_digest(literals):
        raise RuntimeError("E029 literal manifest drift")

    old = load_json(E022_RESULT)
    parents = [
        dict(row)
        for row in old["state_surfaces"]
        if int(row["class_index"]) in {1, 2, 3}
    ]
    if len(parents) != 3:
        raise RuntimeError("E029 retained parent surface drift")
    live_comparison = e022.compare_surfaces([surface, *parents])
    surface_168 = load_json(E025_RESULT)["objective_168_surface"]
    lineage_comparison = e022.compare_surfaces([surface, surface_168])

    all_swaps, portfolio = swap_candidates(
        literals=literals,
        observation_ids_by_literal=observation_ids_by_literal,
    )
    reverse = [row for row in all_swaps if row["returns_known_e028_parent"]]
    if len(reverse) != 1:
        raise RuntimeError(f"E029 reverse E028 pair count drift: {len(reverse)}")

    if int(portfolio[0]["union_coverage"]) >= 24:
        verdict = "OPERATION_ASSIGNMENT_SWAP_PORTFOLIO_PLAUSIBLE"
        next_test = "exact shared-binding replay of diversified swap portfolio"
    else:
        verdict = "OPERATION_ASSIGNMENT_SURFACE_DIFFUSE"
        next_test = "pose-binding cohabitation neighborhood"
    return {
        "schema": "zmd_zero_condition_e029_operation_assignment_surface_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "objective_166_surface": surface,
        "live_beam_comparison": live_comparison,
        "lineage_166_vs_168": lineage_comparison,
        "operation_swap_surface": {
            "eligible_literal_count": len(
                {
                    row["left_literal"]
                    for row in all_swaps
                }
                | {
                    row["right_literal"]
                    for row in all_swaps
                }
            ),
            "candidate_pair_count": len(all_swaps),
            "known_reverse_pair": reverse[0],
            "top_raw_pairs": all_swaps[:40],
            "portfolio_size": len(portfolio),
            "max_portfolio_uses_per_literal": MAX_PORTFOLIO_USES_PER_LITERAL,
            "selected_portfolio": portfolio,
            "portfolio_digest": stable_digest(portfolio),
        },
        "decision_reading": {
            "next_test": next_test,
            "selected_first_swap": portfolio[0],
            "statement": (
                "The swap portfolio preserves occupied geometry by construction; "
                "static domains and exact shared binding remain the consumers."
            ),
        },
        "routing_solver_run": False,
        "truth_boundary": (
            "Residual boundary incidence and an occupancy-preserving swap proposal "
            "surface for one fully materialized objective-166 endpoint."
        ),
        "ledger_effect": "none",
        "elapsed_seconds": time.monotonic() - started,
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E029 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        first = result["decision_reading"]["selected_first_swap"]
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "observation_count": result["objective_166_surface"][
                        "observation_count"
                    ],
                    "literal_count": result["objective_166_surface"][
                        "literal_count"
                    ],
                    "candidate_pair_count": result["operation_swap_surface"][
                        "candidate_pair_count"
                    ],
                    "portfolio_size": result["operation_swap_surface"][
                        "portfolio_size"
                    ],
                    "first_swap": {
                        "pair_key": first["pair_key"],
                        "union_coverage": first["union_coverage"],
                        "coverage_fraction": first["coverage_fraction"],
                    },
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
            "schema": "zmd_zero_condition_e029_operation_assignment_surface_failure_v1",
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
