#!/usr/bin/env python3
"""E049: recover and test external empty-owner rescue relations from E047."""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E049_external_rescue_graph/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
GRAPH_PATH = OUT / "RESCUE_GRAPH.json"
ARM_MANIFEST_PATH = OUT / "ARM_MANIFEST.json"

E047_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E047_simultaneous_body_pair_proposer/"
    "run-001/RESULT.json"
)
DEAD_DIAGNOSTICS = E047_RESULT.with_name("DEAD_DIAGNOSTICS.json")
PARENT_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E046_objective145_integrated_geometry_portfolio/"
    "run-001/SEED_A_BEST_ASSIGNMENT.json"
)
PARENT_ENDPOINT = PARENT_ASSIGNMENT.with_name("SEED_A_BEST_ENDPOINT.json")

E047_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E047_simultaneous_body_pair_proposer/run_e047.py"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E001_pocket_cut_replay/run_experiment.py"
)
E002_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E002_component_commodity_core/run_component_core.py"
)
E004_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E004_component_mismatch_atlas/run_e004.py"
)
E013_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E013_residual_boundary_coverage/run_e013.py"
)
E014_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E014_fixed_outside_mobility/run_e014.py"
)
E015_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E015_shared_binding_gradient/run_e015.py"
)
E027_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E027_final_unary_discriminator/run_e027.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "279000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E047_RESULT: "72bee868f4799a75c2acb007c66f5e24a0fb1686801cddef845e2df5abe9f6c0",
    DEAD_DIAGNOSTICS: "93d6bcea1de21f8bb8d060ab1943072f73d60300ded8ec95cfca9beb16415dba",
    PARENT_ASSIGNMENT: "cb67a16cc022bed9cd332aebf65962cda1fdf819ecac4b8d768f7ae6738198f4",
    PARENT_ENDPOINT: "eabbd025a69e18e905604e47f72076af11317f99c5b03d6c0ca601f0190ad59e",
    E047_RUNNER: "7c7ed75fecd64662c8b133405a8d0051750aa3b41c5eaba7620ac1dcab94abf9",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E027_RUNNER: "9adf39e7817873b5f3909fe784b80f6213d6134ef9bb7d2e09bef3146c0f2704",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
}

PARENT_OBJECTIVE = 144
EDGE_LIMIT = 8
SEED_LIMIT = 3
EXCLUDED_FACILITY_TYPES = {"boundary_storage_port", "protocol_core", "power_pole"}


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


def arm_path(index: int) -> Path:
    return OUT / f"EDGE_{index:02d}.json"


def seed_paths(index: int) -> dict[str, Path]:
    return {
        "summary": OUT / f"SEED_{index:02d}.json",
        "assignment": OUT / f"SEED_{index:02d}_ASSIGNMENT.json",
        "layout": OUT / f"SEED_{index:02d}_LAYOUT.json",
        "endpoint": OUT / f"SEED_{index:02d}_ENDPOINT.json",
    }


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E049 must run on research/main")
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
    result = load_json(E047_RESULT)
    endpoint = load_json(PARENT_ENDPOINT)
    if result.get("verdict") != "BODY_PAIR_GEOMETRY_SEEDS_PROPOSED":
        raise RuntimeError("E049 E047 trigger verdict drift")
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E049 parent endpoint drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output(
            "status", "--porcelain=v1", "--untracked-files=no"
        ),
    }


def parse_owner_record(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        payload = dict(raw)
    elif isinstance(raw, str):
        parsed = ast.literal_eval(raw)
        if not isinstance(parsed, Mapping):
            raise RuntimeError(f"E049 parsed owner is not a mapping: {raw!r}")
        payload = dict(parsed)
    else:
        raise RuntimeError(f"E049 unsupported owner encoding: {type(raw).__name__}")
    required = {"instance_id", "facility_type", "operation_type", "pose_idx", "pose_id"}
    missing = sorted(required - set(payload))
    if missing:
        raise RuntimeError(f"E049 owner record missing fields: {missing}")
    payload["instance_id"] = str(payload["instance_id"])
    payload["facility_type"] = str(payload["facility_type"])
    payload["operation_type"] = str(payload["operation_type"])
    payload["pose_idx"] = int(payload["pose_idx"])
    payload["pose_id"] = str(payload["pose_id"])
    return payload


def load_parent() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    assignment = load_json(PARENT_ASSIGNMENT)
    raw = assignment.get("solution")
    if not isinstance(raw, Mapping):
        raise RuntimeError("E049 parent assignment drift")
    solution = {
        str(instance_id): dict(row)
        for instance_id, row in raw.items()
        if isinstance(row, Mapping)
    }
    endpoint = load_json(PARENT_ENDPOINT)
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E049 parent endpoint drift")
    return solution, endpoint


def build_rescue_graph(
    *,
    parent: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    mandatory: Sequence[Mapping[str, Any]],
    e013: Any,
    runner_sha256: str,
) -> dict[str, Any]:
    if GRAPH_PATH.exists():
        payload = load_json(GRAPH_PATH)
        if str(payload.get("runner_sha256")) != runner_sha256:
            raise RuntimeError("stale E049 rescue graph")
        return payload

    dead = load_json(DEAD_DIAGNOSTICS)
    rows = dead.get("rows")
    if not isinstance(rows, list) or len(rows) != 94:
        raise RuntimeError("E049 dead diagnostic row count drift")
    selected_sources = sorted(
        {str(row["action"]["source_instance_id"]) for row in rows}
    )
    selected_source_set = set(selected_sources)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    raw_owner_strings: list[str] = []
    parsed_owner_ids: list[str] = []
    for row in rows:
        action = dict(row["action"])
        source = str(action["source_instance_id"])
        parsed = [parse_owner_record(value) for value in row["empty_filtered_domains"]]
        owner_ids = sorted(str(value["instance_id"]) for value in parsed)
        raw_owner_strings.extend(str(value) for value in row["empty_filtered_domains"])
        parsed_owner_ids.extend(owner_ids)
        by_id = {str(value["instance_id"]): value for value in parsed}
        for owner_id in sorted(set(owner_ids) - {source}):
            grouped[(source, owner_id)].append(
                {
                    "action_key": str(row["action_key"]),
                    "source_action": action,
                    "empty_owner_ids": owner_ids,
                    "empty_owner_count": len(owner_ids),
                    "owner_record": by_id[owner_id],
                }
            )

    internal_edges = sorted(
        {
            (source, owner)
            for source, owner in grouped
            if owner in selected_source_set
        }
    )
    clean_edges: list[dict[str, Any]] = []
    group_by_instance = e013.group_mapping(mandatory)
    for (source, owner), candidates in grouped.items():
        clean = [row for row in candidates if row["empty_owner_ids"] == [owner]]
        if not clean:
            continue
        representative = sorted(
            clean,
            key=lambda row: (
                int(row["source_action"]["replacement_pose_idx"]),
                str(row["action_key"]),
            ),
        )[0]
        owner_record = dict(representative["owner_record"])
        _, owner_target = e013.literal_identity(
            owner=owner_record,
            solution=parent,
            group_by_instance=group_by_instance,
            facility_pools=inputs["pools"],
        )
        if str(owner_target["facility_type"]) in EXCLUDED_FACILITY_TYPES:
            continue
        clean_edges.append(
            {
                "edge_key": f"{source}->{owner}",
                "source_instance_id": source,
                "owner_instance_id": owner,
                "edge_frequency": len(candidates),
                "clean_action_count": len(clean),
                "representative_action_key": representative["action_key"],
                "source_action": json_safe(representative["source_action"]),
                "owner_record": json_safe(owner_record),
                "owner_target": json_safe(owner_target),
            }
        )
    clean_edges.sort(
        key=lambda row: (
            -int(row["edge_frequency"]),
            str(row["source_instance_id"]),
            str(row["owner_instance_id"]),
            int(row["source_action"]["replacement_pose_idx"]),
        )
    )
    selected_edges = clean_edges[:EDGE_LIMIT]
    if not selected_edges:
        raise RuntimeError("E049 produced no clean external rescue edges")

    synthetic_owner = str(selected_edges[0]["owner_instance_id"])
    augmented_ids = selected_source_set | {synthetic_owner}
    legacy_synthetic_hits = sum(
        bool(set(str(value) for value in row["empty_filtered_domains"]) & augmented_ids)
        for row in rows
    )
    parsed_synthetic_hits = sum(
        synthetic_owner
        in {
            parse_owner_record(value)["instance_id"]
            for value in row["empty_filtered_domains"]
        }
        for row in rows
    )
    payload = {
        "schema": "zmd_zero_condition_e049_structured_rescue_graph_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "parent_objective": PARENT_OBJECTIVE,
        "dead_row_count": len(rows),
        "selected_source_ids": selected_sources,
        "structured_edge_count": len(grouped),
        "structured_internal_edge_count": len(internal_edges),
        "structured_internal_edges": [list(value) for value in internal_edges],
        "clean_external_edge_count": len(clean_edges),
        "selected_edge_count": len(selected_edges),
        "selected_edges": selected_edges,
        "all_edge_summaries": [
            {
                "source_instance_id": source,
                "owner_instance_id": owner,
                "frequency": len(candidates),
                "minimum_empty_owner_count": min(
                    int(row["empty_owner_count"]) for row in candidates
                ),
            }
            for (source, owner), candidates in sorted(
                grouped.items(),
                key=lambda item: (-len(item[1]), item[0]),
            )
        ],
        "transport_audit": {
            "legacy_owner_encoding": "stringified_mapping",
            "legacy_actual_internal_intersection_count": sum(
                bool(set(str(value) for value in row["empty_filtered_domains"]) & selected_source_set)
                for row in rows
            ),
            "structured_actual_internal_edge_count": len(internal_edges),
            "synthetic_added_owner": synthetic_owner,
            "legacy_synthetic_intersection_count": legacy_synthetic_hits,
            "structured_synthetic_intersection_count": parsed_synthetic_hits,
            "finding": (
                "The E047 direct-rescue consumer intersects stringified owner "
                "mappings with instance IDs. The current six-target graph truly "
                "has no internal edge, but the transport would miss one if present."
            ),
        },
        "raw_owner_string_count": len(raw_owner_strings),
        "parsed_owner_id_count": len(parsed_owner_ids),
        "ledger_effect": "none",
    }
    dump_exclusive(GRAPH_PATH, payload)
    return payload


def compact_shared(shared: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": shared.get("status"),
        "objective": shared.get("objective"),
        "selection_digest": shared.get("selection_digest"),
        "port_specs_digest": shared.get("port_specs_digest"),
        "per_commodity": json_safe(shared.get("per_commodity", {})),
        "positive_commodity_count": shared.get("positive_commodity_count"),
        "zero_mismatch_commodities": json_safe(
            shared.get("zero_mismatch_commodities", [])
        ),
        "morphology": json_safe(shared.get("morphology", {})),
        "filtered_binding_option_count": shared.get(
            "filtered_binding_option_count"
        ),
        "empty_filtered_domains": json_safe(
            shared.get("empty_filtered_domains", [])
        ),
    }


def owner_action(
    *,
    owner_target: Mapping[str, Any],
    replacement_pose_idx: int,
    replacement_pose_id: str,
) -> dict[str, Any]:
    source_ids = [str(value) for value in owner_target["source_instance_ids"]]
    if len(source_ids) != 1:
        raise RuntimeError("E049 owner target lacks one source instance")
    return {
        "source_instance_id": source_ids[0],
        "facility_type": str(owner_target["facility_type"]),
        "current_pose_idx": int(owner_target["pose_idx"]),
        "replacement_pose_idx": int(replacement_pose_idx),
        "replacement_pose_id": str(replacement_pose_id),
    }


def evaluate_edge(
    *,
    index: int,
    edge: Mapping[str, Any],
    parent: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    power: Mapping[str, Any],
    e001: Any,
    e002: Any,
    e004: Any,
    e014: Any,
    e015: Any,
    e047: Any,
    runner_sha256: str,
) -> dict[str, Any]:
    path = arm_path(index)
    if path.exists():
        payload = load_json(path)
        if str(payload.get("runner_sha256")) != runner_sha256:
            raise RuntimeError(f"stale E049 edge checkpoint: {path}")
        if str(payload.get("edge_key")) != str(edge["edge_key"]):
            raise RuntimeError(f"E049 edge checkpoint identity drift: {path}")
        return payload

    source_action = dict(edge["source_action"])
    source_child = e047.apply_action(
        solution=parent,
        action=source_action,
        inputs=inputs,
        e014=e014,
    )
    source_diagnostic = e014.screen_component_interface(
        solution=source_child,
        inputs=inputs,
        e001=e001,
        e002=e002,
    )
    if source_diagnostic.get("status") != "PORT_DOMAIN_EMPTY":
        raise RuntimeError(
            f"E049 source action no longer reproduces PORT_DOMAIN_EMPTY: {edge['edge_key']}"
        )
    source_empty_ids = sorted(
        str(value["instance_id"])
        for value in source_diagnostic.get("empty_filtered_domains", [])
    )
    if source_empty_ids != [str(edge["owner_instance_id"])]:
        raise RuntimeError(
            f"E049 clean owner drift for {edge['edge_key']}: {source_empty_ids}"
        )

    occupied, _ = e014.base_occupancy(source_child, inputs["pools"])
    selected_poles = {
        int(row["pose_idx"])
        for row in source_child.values()
        if str(row.get("facility_type")) == "power_pole"
    }
    alternatives = e014.enumerate_alternatives(
        target=edge["owner_target"],
        base_solution=source_child,
        pools=inputs["pools"],
        occupied=occupied,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    )
    records: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(alternatives, 1):
        solution = candidate["solution"]
        try:
            shared = e015.solve_shared_mismatch(
                solution=solution,
                inputs=inputs,
                e004=e004,
                random_seed=490000 + index * 1000 + candidate_index,
                include_boundaries=False,
            )
        except RuntimeError as exc:
            if "empty binding domain" not in str(exc):
                raise
            diagnostic = e014.screen_component_interface(
                solution=solution,
                inputs=inputs,
                e001=e001,
                e002=e002,
            )
            if diagnostic.get("status") != "PORT_DOMAIN_EMPTY":
                raise RuntimeError(
                    "E049 pair empty-domain exception did not reproduce: "
                    f"{diagnostic.get('status')}"
                )
            shared = {
                "status": "PORT_DOMAIN_EMPTY",
                "objective": None,
                "empty_filtered_domains": diagnostic.get(
                    "empty_filtered_domains", []
                ),
                "filtered_binding_option_count": diagnostic.get(
                    "filtered_binding_option_count"
                ),
                "morphology": diagnostic.get("morphology"),
            }
        compact = compact_shared(shared)
        records.append(
            {
                "owner_pose_idx": int(candidate["pose_idx"]),
                "owner_pose_id": str(candidate["pose_id"]),
                "same_footprint": bool(candidate["same_footprint"]),
                "candidate_solution_digest": stable_digest(solution),
                "shared_binding": compact,
            }
        )
        if candidate_index % 20 == 0 or compact.get("objective") == 0:
            print(
                json.dumps(
                    {
                        "event": "E049_EDGE_PROGRESS",
                        "edge": index,
                        "candidate": candidate_index,
                        "candidate_total": len(alternatives),
                        "status": compact.get("status"),
                        "objective": compact.get("objective"),
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    payload = {
        "schema": "zmd_zero_condition_e049_external_rescue_edge_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "parent_objective": PARENT_OBJECTIVE,
        "edge_index": index,
        "edge_key": str(edge["edge_key"]),
        "edge_frequency": int(edge["edge_frequency"]),
        "source_action": json_safe(source_action),
        "owner_target": json_safe(edge["owner_target"]),
        "source_empty_owner_ids": source_empty_ids,
        "owner_alternative_count": len(alternatives),
        "status_counts": dict(
            sorted(Counter(row["shared_binding"]["status"] for row in records).items())
        ),
        "records": records,
        "ledger_effect": "none",
    }
    dump_exclusive(path, payload)
    return payload


def reconstruct_candidate(
    *,
    edge: Mapping[str, Any],
    record: Mapping[str, Any],
    parent: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e014: Any,
    e047: Any,
) -> dict[str, dict[str, Any]]:
    child = e047.apply_action(
        solution=parent,
        action=edge["source_action"],
        inputs=inputs,
        e014=e014,
    )
    child = e047.apply_action(
        solution=child,
        action=owner_action(
            owner_target=edge["owner_target"],
            replacement_pose_idx=int(record["owner_pose_idx"]),
            replacement_pose_id=str(record["owner_pose_id"]),
        ),
        inputs=inputs,
        e014=e014,
    )
    digest = stable_digest(child)
    if digest != str(record["candidate_solution_digest"]):
        raise RuntimeError("E049 candidate reconstruction digest drift")
    return child


def materialize_seed(
    *,
    seed_index: int,
    row: Mapping[str, Any],
    edge_by_key: Mapping[str, Mapping[str, Any]],
    parent: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e001: Any,
    e004: Any,
    e014: Any,
    e015: Any,
    e027: Any,
    e047: Any,
    runner_sha256: str,
) -> dict[str, Any]:
    paths = seed_paths(seed_index)
    if paths["summary"].exists():
        payload = load_json(paths["summary"])
        if str(payload.get("runner_sha256")) != runner_sha256:
            raise RuntimeError(f"stale E049 seed summary: {seed_index}")
        return payload
    edge = edge_by_key[str(row["edge_key"])]
    solution = reconstruct_candidate(
        edge=edge,
        record=row["record"],
        parent=parent,
        inputs=inputs,
        e014=e014,
        e047=e047,
    )
    endpoint = e027.materialize_shared_endpoint(
        solution=solution,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=499000 + seed_index,
    )
    expected = int(row["record"]["shared_binding"]["objective"])
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != expected:
        raise RuntimeError("E049 seed endpoint materialization drift")
    dump_exclusive(
        paths["assignment"],
        {
            "schema": "zmd_zero_condition_e049_rescued_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "parent_objective": PARENT_OBJECTIVE,
            "shared_mismatch_objective": int(endpoint["objective"]),
            "edge_key": str(row["edge_key"]),
            "source_action": json_safe(edge["source_action"]),
            "owner_pose_idx": int(row["record"]["owner_pose_idx"]),
            "solution": solution,
        },
    )
    dump_exclusive(paths["layout"], e001.solution_layout(solution))
    dump_exclusive(paths["endpoint"], endpoint)
    payload = {
        "schema": "zmd_zero_condition_e049_rescued_seed_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "seed_index": seed_index,
        "edge_key": str(row["edge_key"]),
        "edge_frequency": int(row["edge_frequency"]),
        "objective": int(endpoint["objective"]),
        "source_action": json_safe(edge["source_action"]),
        "owner_target": json_safe(edge["owner_target"]),
        "owner_pose_idx": int(row["record"]["owner_pose_idx"]),
        "owner_pose_id": str(row["record"]["owner_pose_id"]),
        "owner_same_footprint": bool(row["record"]["same_footprint"]),
        "placement_digest": stable_digest(solution),
        "binding_selection_digest": endpoint["selection_digest"],
        "per_commodity": endpoint["per_commodity"],
        "positive_commodity_count": endpoint["positive_commodity_count"],
        "zero_mismatch_commodities": endpoint["zero_mismatch_commodities"],
        "morphology": endpoint["morphology"],
        "filtered_binding_option_count": endpoint[
            "filtered_binding_option_count"
        ],
        "assignment_path": str(paths["assignment"].relative_to(ROOT)),
        "assignment_sha256": sha256_file(paths["assignment"]),
        "layout_path": str(paths["layout"].relative_to(ROOT)),
        "layout_sha256": sha256_file(paths["layout"]),
        "endpoint_path": str(paths["endpoint"].relative_to(ROOT)),
        "endpoint_sha256": sha256_file(paths["endpoint"]),
        "ledger_effect": "none",
    }
    dump_exclusive(paths["summary"], payload)
    return payload


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e047 = import_module("zmd_e049_e047", E047_RUNNER)
    e001 = import_module("zmd_e049_e001", E001_RUNNER)
    e002 = import_module("zmd_e049_e002", E002_RUNNER)
    e004 = import_module("zmd_e049_e004", E004_RUNNER)
    e013 = import_module("zmd_e049_e013", E013_RUNNER)
    e014 = import_module("zmd_e049_e014", E014_RUNNER)
    e015 = import_module("zmd_e049_e015", E015_RUNNER)
    e027 = import_module("zmd_e049_e027", E027_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    parent, parent_endpoint = load_parent()
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    if not isinstance(mandatory, list):
        raise RuntimeError("E049 mandatory instance payload drift")
    graph = build_rescue_graph(
        parent=parent,
        inputs=inputs,
        mandatory=mandatory,
        e013=e013,
        runner_sha256=runner_sha256,
    )
    selected_edges = [dict(value) for value in graph["selected_edges"]]
    power = e014.build_power_semantics(e001, stack, inputs)

    arms: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    all_optimal: list[dict[str, Any]] = []
    aggregate_status = Counter()
    for index, edge in enumerate(selected_edges, 1):
        print(
            json.dumps(
                {
                    "event": "E049_EDGE_START",
                    "edge": index,
                    "edge_key": edge["edge_key"],
                    "frequency": edge["edge_frequency"],
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        arm = evaluate_edge(
            index=index,
            edge=edge,
            parent=parent,
            inputs=inputs,
            power=power,
            e001=e001,
            e002=e002,
            e004=e004,
            e014=e014,
            e015=e015,
            e047=e047,
            runner_sha256=runner_sha256,
        )
        arms.append(arm)
        path = arm_path(index)
        manifest_rows.append(
            {
                "edge_index": index,
                "edge_key": edge["edge_key"],
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
            }
        )
        aggregate_status.update(arm["status_counts"])
        for record in arm["records"]:
            if str(record["shared_binding"]["status"]) != "OPTIMAL":
                continue
            all_optimal.append(
                {
                    "edge_index": index,
                    "edge_key": edge["edge_key"],
                    "edge_frequency": int(edge["edge_frequency"]),
                    "record": record,
                }
            )

    manifest_payload = {
        "schema": "zmd_zero_condition_e049_edge_manifest_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "runner_sha256": runner_sha256,
        "parent_objective": PARENT_OBJECTIVE,
        "arms": manifest_rows,
        "ledger_effect": "none",
    }
    if ARM_MANIFEST_PATH.exists():
        old = load_json(ARM_MANIFEST_PATH)
        if str(old.get("runner_sha256")) != runner_sha256:
            raise RuntimeError("stale E049 arm manifest")
        if json_safe(old.get("arms")) != json_safe(manifest_rows):
            raise RuntimeError("E049 arm manifest drift")
    else:
        dump_exclusive(ARM_MANIFEST_PATH, manifest_payload)

    ranked = sorted(
        all_optimal,
        key=lambda row: (
            int(row["record"]["shared_binding"]["objective"]),
            -int(row["record"]["shared_binding"].get("filtered_binding_option_count") or 0),
            -int(row["edge_frequency"]),
            str(row["edge_key"]),
            int(row["record"]["owner_pose_idx"]),
        ),
    )
    selected_seed_rows: list[dict[str, Any]] = []
    seen_states: set[str] = set()
    for row in ranked:
        digest = str(row["record"]["candidate_solution_digest"])
        if digest in seen_states:
            continue
        seen_states.add(digest)
        selected_seed_rows.append(row)
        if len(selected_seed_rows) >= SEED_LIMIT:
            break
    edge_by_key = {str(value["edge_key"]): value for value in selected_edges}
    seeds = [
        materialize_seed(
            seed_index=index,
            row=row,
            edge_by_key=edge_by_key,
            parent=parent,
            inputs=inputs,
            e001=e001,
            e004=e004,
            e014=e014,
            e015=e015,
            e027=e027,
            e047=e047,
            runner_sha256=runner_sha256,
        )
        for index, row in enumerate(selected_seed_rows, 1)
    ]

    best_objective = min((int(seed["objective"]) for seed in seeds), default=None)
    routing: dict[str, Any] = {"status": "NOT_REACHED_NO_RESCUED_STATE"}
    if best_objective == 0:
        verdict = "EXTERNAL_RESCUE_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
        best = next(seed for seed in seeds if int(seed["objective"]) == 0)
        solution = load_json(ROOT / str(best["assignment_path"]))["solution"]
        routing = e014.screen_component_interface(
            solution=solution,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
    elif seeds:
        verdict = "EXTERNAL_RESCUE_RELATIONS_CONFIRMED"
        decision = "REVALUE_RESCUED_GEOMETRIES_WITH_JOINT_MIDDLE"
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
    else:
        verdict = "EXTERNAL_RESCUE_GRAPH_NO_ADMITTED_PAIR"
        decision = "BUILD_NATIVE_SIMULTANEOUS_GEOMETRY_CONTEXT"

    distribution = Counter(
        int(row["record"]["shared_binding"]["objective"])
        for row in all_optimal
    )
    return {
        "schema": "zmd_zero_condition_e049_external_rescue_graph_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "parent_objective": PARENT_OBJECTIVE,
        "parent_binding_selection_digest": parent_endpoint["selection_digest"],
        "rescue_graph_path": str(GRAPH_PATH.relative_to(ROOT)),
        "rescue_graph_sha256": sha256_file(GRAPH_PATH),
        "transport_audit": graph["transport_audit"],
        "structured_internal_edge_count": graph["structured_internal_edge_count"],
        "clean_external_edge_count": graph["clean_external_edge_count"],
        "selected_edge_count": len(selected_edges),
        "selected_edges": selected_edges,
        "edge_summaries": [
            {
                "edge_index": arm["edge_index"],
                "edge_key": arm["edge_key"],
                "edge_frequency": arm["edge_frequency"],
                "owner_alternative_count": arm["owner_alternative_count"],
                "status_counts": arm["status_counts"],
                "best_objective": min(
                    (
                        int(row["shared_binding"]["objective"])
                        for row in arm["records"]
                        if row["shared_binding"]["status"] == "OPTIMAL"
                    ),
                    default=None,
                ),
            }
            for arm in arms
        ],
        "status_counts": dict(sorted(aggregate_status.items())),
        "optimal_rescued_state_count": len(all_optimal),
        "objective_distribution": {
            str(key): value for key, value in sorted(distribution.items())
        },
        "arm_manifest_path": str(ARM_MANIFEST_PATH.relative_to(ROOT)),
        "arm_manifest_sha256": sha256_file(ARM_MANIFEST_PATH),
        "materialized_seeds": seeds,
        "best_objective": best_objective,
        "routing": routing,
        "decision": decision,
        "truth_boundary": (
            "At most eight clean external empty-owner edges selected from E047's "
            "94 frozen dead actions; one representative source action per edge, "
            "with exhaustive exact owner pose alternatives under that source move."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists():
        raise FileExistsError("refusing to overwrite E049 terminal result")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "selected_edge_count": result["selected_edge_count"],
                    "status_counts": result["status_counts"],
                    "optimal_rescued_state_count": result[
                        "optimal_rescued_state_count"
                    ],
                    "best_objective": result["best_objective"],
                    "decision": result["decision"],
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
            "schema": "zmd_zero_condition_e049_external_rescue_graph_failure_v1",
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
