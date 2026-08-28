#!/usr/bin/env python3
"""E073: replay one E072 direct owner bridge in the exact signature consumer."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E073_direct_owner_bridge_replay/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
RECORDS_PATH = OUT / "ALTERNATIVE_RECORDS.json"
CHUNK_DIR = OUT / "chunks"

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"
E061_RUNNER = (
    EXPERIMENT_ROOT / "E061_all_one_object_signature_frontier/run_e061.py"
)
E062_RUNNER = EXPERIMENT_ROOT / "E062_one_object_tradeoff_atlas/run_e062.py"
E063_RUNNER = (
    EXPERIMENT_ROOT / "E063_pole_conditioned_second_object_frontier/run_e063.py"
)
E069_RUNNER = EXPERIMENT_ROOT / "E069_six4_near_miss_complete_face/run_e069.py"
E071_RUNNER = (
    EXPERIMENT_ROOT / "E071_dual_signature_destination_atlas/run_e071.py"
)
E072_RUNNER = (
    EXPERIMENT_ROOT / "E072_half_signature_component_bridges/run_e072.py"
)

E069_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001/RESULT.json"
)
E071_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E071_dual_signature_destination_atlas/run-001/RESULT.json"
)
E072_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E072_half_signature_component_bridges/run-001/RESULT.json"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONPYCACHEPREFIX": "/tmp/zmd_e073_source_cache_v1",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "299000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E061_RUNNER: "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
    E062_RUNNER: "91770f3ba9a96a3c79bd95c42a4e40b9a540ab537e97079b02f7c57c6fedb67e",
    E063_RUNNER: "e925b4470ecb002701b262c5d8bcfbe88177eb8da373502354174f178f39caf9",
    E069_RESULT: "38cd4ec548bd18ad70b3549e04d225a4e4a226489bd8ed111c9f72554640769f",
    E071_RESULT: "__E071_RESULT_SHA256__",
    E072_RESULT: "__E072_RESULT_SHA256__",
}

FILLING = "filling_capsule"
CHUNK_SIZE = 100
MAX_MATERIALIZED = 5


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def encoded(value: Any) -> bytes:
    return (
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def dump_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded(value))
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def audit_module(module: Any, expected_path: Path) -> dict[str, Any]:
    expected = expected_path.resolve()
    functions: list[dict[str, str]] = []
    foreign: list[dict[str, str]] = []
    for name, value in sorted(vars(module).items()):
        if not inspect.isfunction(value) or value.__module__ != module.__name__:
            continue
        actual = Path(value.__code__.co_filename).resolve()
        record = {"name": str(name), "code_filename": str(actual)}
        functions.append(record)
        if actual != expected:
            foreign.append(record)
    if foreign:
        raise RuntimeError(f"foreign functions loaded for {expected_path}: {foreign[:10]}")
    return {
        "module": str(module.__name__),
        "source": str(expected_path.relative_to(ROOT)),
        "source_sha256": sha256_file(expected_path),
        "function_count": len(functions),
        "foreign_function_count": 0,
    }


def audit_nested_modules(prefixes: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, module in sorted(sys.modules.items()):
        if module is None or not any(name.startswith(prefix) for prefix in prefixes):
            continue
        file_value = getattr(module, "__file__", None)
        if not isinstance(file_value, str):
            continue
        path = Path(file_value).resolve()
        source = (
            Path(importlib.util.source_from_cache(str(path))).resolve()
            if path.suffix == ".pyc"
            else path
        )
        rows.append(audit_module(module, source))
    return rows


def verify_identity() -> dict[str, Any]:
    if Path.cwd().resolve() != ROOT.resolve():
        raise RuntimeError(f"run E073 from research root: {Path.cwd()}")
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E073 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"E073 requires a clean tracked worktree: {tracked_status}")
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
            f"environment mismatch: {mismatches}; unexpected={unexpected_exact}"
        )
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift: {path}: {actual} != {expected}")

    e071 = load_json(E071_RESULT)
    e072 = load_json(E072_RESULT)
    if e071.get("verdict") != "DUAL_SIGNATURE_DESTINATION_COMPATIBILITY_IDENTIFIED":
        raise RuntimeError("E073 E071 verdict drift")
    if e072.get("verdict") != "DIRECT_OWNER_BRIDGES_PRESERVE_HALF_SIGNATURE":
        raise RuntimeError(f"E073 E072 verdict drift: {e072.get('verdict')}")
    if int(e072.get("direct_destination_preserving_count", 0)) <= 0:
        raise RuntimeError("E073 trigger lacks a direct preserving proposal")

    for result, runner, label in (
        (e071, E071_RUNNER, "E071"),
        (e072, E072_RUNNER, "E072"),
    ):
        actual_runner = sha256_file(runner)
        if str(result["identity"]["runner_sha256"]) != actual_runner:
            raise RuntimeError(f"E073 current {label} runner differs from frozen execution")
    atlas_path = ROOT / str(e072["bridge_atlas_path"])
    if not atlas_path.is_file():
        raise FileNotFoundError(atlas_path)
    atlas_sha = sha256_file(atlas_path)
    if atlas_sha != str(e072["bridge_atlas_sha256"]):
        raise RuntimeError("E073 E072 bridge atlas hash mismatch")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "e071_runner_sha256": sha256_file(E071_RUNNER),
        "e072_runner_sha256": sha256_file(E072_RUNNER),
        "e072_atlas_path": str(atlas_path.relative_to(ROOT)),
        "e072_atlas_sha256": atlas_sha,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": tracked_status,
    }


def select_proposal() -> dict[str, Any]:
    e072 = load_json(E072_RESULT)
    proposals = [
        dict(row)
        for row in e072["selected_proposals"]
        if row.get("owner_count") == 1
        and not bool(row.get("moves_destination_body"))
        and len(row.get("path_owners", [])) == 1
    ]
    if not proposals:
        raise RuntimeError("E073 no direct destination-preserving proposal")
    selected = proposals[0]
    if str(selected["path_owners"][0]) == str(selected["destination_owner"]):
        raise RuntimeError("E073 selected path moves the half-signature body")
    if str(selected["half_signature_category"]) not in {
        "qiaoyu_29_half",
        "fine_36_half",
    }:
        raise RuntimeError(f"E073 unexpected half-signature category: {selected}")
    if not selected.get("terminal_variants"):
        raise RuntimeError("E073 proposal lacks terminal-cell variants")
    return selected


def candidate_context(
    *,
    e061: Any,
    parent: Mapping[str, Any],
    solution: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    base = parent["base"]
    routing_context = base["build_routing_context"](
        solution,
        base["inputs"]["pools"],
        70,
        70,
    )
    descriptors = e061.dynamic_descriptors(
        candidate=solution,
        base=base,
        mode_map=parent["mode_map"],
    )
    options = e061.map_descriptors(
        descriptors=descriptors,
        routing_context=routing_context,
    )
    sink_space = e061.generic_sink_space(
        candidate=solution,
        routing_context=routing_context,
        inputs=base["inputs"],
        is_port_front_usable=base["is_port_front_usable"],
    )
    return {
        "routing_context": routing_context,
        "descriptors": descriptors,
        "options": options,
        "sink_space": sink_space,
    }


def mapped_variant(
    *,
    variant: Mapping[str, Any],
    routing_context: Any,
) -> dict[str, Any]:
    active = [tuple(int(value) for value in cell) for cell in variant["active_cells"]]
    fine_cells = [
        tuple(int(value) for value in cell) for cell in variant["fine_input_cells"]
    ]
    qiaoyu_cells = [
        tuple(int(value) for value in cell)
        for cell in variant["qiaoyu_output_cells"]
    ]
    free = set(routing_context.component_by_cell)
    blocked = sorted(cell for cell in active if cell not in free)
    if blocked:
        return {
            "status": "TERMINAL_CELLS_BLOCKED",
            "blocked_cells": [list(cell) for cell in blocked],
            "signature": None,
        }
    fine_components = tuple(
        sorted(
            {
                int(routing_context.component_by_cell[cell])
                for cell in fine_cells
            }
        )
    )
    qiaoyu_components = tuple(
        sorted(
            {
                int(routing_context.component_by_cell[cell])
                for cell in qiaoyu_cells
            }
        )
    )
    return {
        "status": "MAPPED",
        "blocked_cells": [],
        "fine_input_components": list(fine_components),
        "qiaoyu_output_components": list(qiaoyu_components),
        "signature": (fine_components, (), qiaoyu_components),
    }


def force_option(
    *,
    e061: Any,
    e071: Any,
    candidate: Mapping[str, Any],
    proposal: Mapping[str, Any],
    variant: Mapping[str, Any],
    random_seed: int,
) -> dict[str, Any]:
    mapped = mapped_variant(
        variant=variant,
        routing_context=candidate["routing_context"],
    )
    result: dict[str, Any] = {
        "raw_pattern_index": int(variant["raw_pattern_index"]),
        "mapping": json_safe(mapped),
        "matching_option_indices": [],
        "forced_result": None,
    }
    if mapped["status"] != "MAPPED":
        return result
    destination = int(proposal["destination"])
    pose_idx = int(proposal["option"]["pose_idx"])
    matching = [
        option_index
        for option_index, (operation, candidate_pose, signature) in enumerate(
            candidate["options"][destination]
        )
        if str(operation) == FILLING
        and int(candidate_pose) == pose_idx
        and tuple(tuple(int(value) for value in part) for part in signature)
        == tuple(mapped["signature"])
    ]
    result["matching_option_indices"] = matching
    if len(matching) != 1:
        return result
    result["forced_result"] = e071.solve_configuration(
        e061=e061,
        options=candidate["options"],
        sink_space=candidate["sink_space"],
        synthetic_destination=None,
        forced_actual=(destination, int(matching[0])),
        random_seed=int(random_seed),
    )
    return result


def chunk_path(index: int) -> Path:
    return CHUNK_DIR / f"CHUNK_{index:03d}.json"


def scan_alternatives(
    *,
    e061: Any,
    e071: Any,
    parent: Mapping[str, Any],
    proposal: Mapping[str, Any],
    runner_sha256: str,
) -> list[dict[str, Any]]:
    owner = str(proposal["path_owners"][0])
    alternatives = e061.enumerate_alternatives(
        base=parent["parent_base"],
        instance_id=owner,
    )
    by_solution: dict[str, dict[str, Any]] = {}
    alias_counts: Counter[str] = Counter()
    for alternative in alternatives:
        digest = stable_digest(alternative["solution"])
        alias_counts[digest] += 1
        by_solution.setdefault(digest, alternative)
    ordered = [
        (digest, by_solution[digest], int(alias_counts[digest]) - 1)
        for digest in sorted(
            by_solution,
            key=lambda key: (
                int(by_solution[key]["pose_idx"]),
                str(by_solution[key]["pose_id"]),
                key,
            ),
        )
    ]
    all_records: list[dict[str, Any]] = []
    for chunk_index, start in enumerate(range(0, len(ordered), CHUNK_SIZE), 1):
        rows = ordered[start : start + CHUNK_SIZE]
        path = chunk_path(chunk_index)
        spec_digest = stable_digest(
            [
                {
                    "solution_digest": digest,
                    "pose_idx": int(alternative["pose_idx"]),
                    "pose_id": str(alternative["pose_id"]),
                    "alias_count": alias_count,
                }
                for digest, alternative, alias_count in rows
            ]
        )
        if path.exists():
            payload = load_json(path)
            if str(payload.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E073 chunk runner: {path}")
            if str(payload.get("spec_digest")) != spec_digest:
                raise RuntimeError(f"stale E073 chunk alternatives: {path}")
        else:
            records: list[dict[str, Any]] = []
            started = time.monotonic()
            for local_index, (solution_digest, alternative, alias_count) in enumerate(
                rows,
                1,
            ):
                solution = {
                    str(key): dict(value)
                    for key, value in alternative["solution"].items()
                }
                record: dict[str, Any] = {
                    "scan_index": start + local_index,
                    "owner": owner,
                    "facility_type": str(
                        parent["solution"][owner]["facility_type"]
                    ),
                    "current_pose_idx": int(
                        parent["solution"][owner]["pose_idx"]
                    ),
                    "replacement_pose_idx": int(alternative["pose_idx"]),
                    "replacement_pose_id": str(alternative["pose_id"]),
                    "same_footprint": bool(alternative["same_footprint"]),
                    "solution_digest": solution_digest,
                    "alias_count": alias_count,
                    "candidate_status": "BUILT",
                    "unforced_result": None,
                    "variant_results": [],
                }
                try:
                    candidate = candidate_context(
                        e061=e061,
                        parent=parent,
                        solution=solution,
                    )
                except RuntimeError as exc:
                    record["candidate_status"] = "STRUCTURAL_EMPTY"
                    record["detail"] = str(exc)
                    records.append(record)
                    continue
                record["unforced_result"] = e061.solve_signature(
                    options=candidate["options"],
                    sink_space=candidate["sink_space"],
                    random_seed=730000 + start + local_index,
                )
                record["variant_results"] = [
                    force_option(
                        e061=e061,
                        e071=e071,
                        candidate=candidate,
                        proposal=proposal,
                        variant=variant,
                        random_seed=(
                            731000
                            + 100 * (start + local_index)
                            + variant_index
                        ),
                    )
                    for variant_index, variant in enumerate(
                        proposal["terminal_variants"],
                        1,
                    )
                ]
                record["candidate_status"] = "EVALUATED"
                records.append(record)
                forced_zero = any(
                    (variant.get("forced_result") or {}).get("status")
                    in {"OPTIMAL", "FEASIBLE"}
                    for variant in record["variant_results"]
                )
                unforced_zero = (
                    record["unforced_result"].get("status")
                    in {"OPTIMAL", "FEASIBLE"}
                )
                if local_index % 20 == 0 or forced_zero or unforced_zero:
                    print(
                        json.dumps(
                            {
                                "event": "E073_PROGRESS",
                                "chunk": chunk_index,
                                "alternative": start + local_index,
                                "alternative_total": len(ordered),
                                "pose_idx": int(alternative["pose_idx"]),
                                "unforced": record["unforced_result"].get(
                                    "status"
                                ),
                                "forced_zero": forced_zero,
                                "at_utc": utc_now(),
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
            payload = {
                "schema": "zmd_zero_condition_e073_chunk_v1",
                "created_at_utc": utc_now(),
                "authority": "research_only_noncertified",
                "runner_sha256": runner_sha256,
                "chunk_index": chunk_index,
                "alternative_start_index": start + 1,
                "alternative_count": len(rows),
                "spec_digest": spec_digest,
                "elapsed_seconds": time.monotonic() - started,
                "records": records,
                "ledger_effect": "none",
            }
            dump_exclusive(path, payload)
        all_records.extend(payload["records"])
    return all_records


def materialize_candidates(
    *,
    e061: Any,
    parent: Mapping[str, Any],
    proposal: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    successful = [
        row
        for row in records
        if any(
            (variant.get("forced_result") or {}).get("status")
            in {"OPTIMAL", "FEASIBLE"}
            for variant in row.get("variant_results", [])
        )
        or (row.get("unforced_result") or {}).get("status")
        in {"OPTIMAL", "FEASIBLE"}
    ]
    successful.sort(
        key=lambda row: (
            not any(
                (variant.get("forced_result") or {}).get("status")
                in {"OPTIMAL", "FEASIBLE"}
                for variant in row.get("variant_results", [])
            ),
            int(row["replacement_pose_idx"]),
            str(row["replacement_pose_id"]),
        )
    )
    owner = str(proposal["path_owners"][0])
    alternatives = {
        int(row["pose_idx"]): row
        for row in e061.enumerate_alternatives(
            base=parent["parent_base"],
            instance_id=owner,
        )
    }
    output: list[dict[str, Any]] = []
    for rank, row in enumerate(successful[:MAX_MATERIALIZED], 1):
        alternative = alternatives[int(row["replacement_pose_idx"])]
        path = OUT / f"ZERO_CANDIDATE_{rank:02d}.json"
        payload = {
            "schema": "zmd_zero_condition_e073_zero_candidate_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "rank": rank,
            "proposal": proposal,
            "alternative_record": row,
            "solution": alternative["solution"],
            "ledger_effect": "none",
        }
        dump_exclusive(path, payload)
        output.append(
            {
                "rank": rank,
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
                "replacement_pose_idx": int(row["replacement_pose_idx"]),
            }
        )
    return output


def run() -> dict[str, Any]:
    identity = verify_identity()
    proposal = select_proposal()
    e061 = import_module("zmd_e073_e061", E061_RUNNER)
    e062 = import_module("zmd_e073_e062", E062_RUNNER)
    e063 = import_module("zmd_e073_e063", E063_RUNNER)
    e069 = import_module("zmd_e073_e069", E069_RUNNER)
    e071 = import_module("zmd_e073_e071", E071_RUNNER)
    e072 = import_module("zmd_e073_e072", E072_RUNNER)
    direct_origins = [
        audit_module(e061, E061_RUNNER),
        audit_module(e062, E062_RUNNER),
        audit_module(e063, E063_RUNNER),
        audit_module(e069, E069_RUNNER),
        audit_module(e071, E071_RUNNER),
        audit_module(e072, E072_RUNNER),
    ]
    parent = e069.reconstruct_parent(e061, e062, e063)
    nested_origins = audit_nested_modules(
        (
            "zmd_e073_",
            "zmd_e061_",
            "zmd_e062_",
            "zmd_e063_",
            "zmd_e069_",
            "zmd_e071_",
            "zmd_e072_",
        )
    )
    records = scan_alternatives(
        e061=e061,
        e071=e071,
        parent=parent,
        proposal=proposal,
        runner_sha256=str(identity["runner_sha256"]),
    )
    records_payload = {
        "schema": "zmd_zero_condition_e073_alternative_records_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "proposal": proposal,
        "record_count": len(records),
        "records": records,
        "ledger_effect": "none",
    }
    dump_exclusive(RECORDS_PATH, records_payload)

    forced_zero = [
        row
        for row in records
        if any(
            (variant.get("forced_result") or {}).get("status")
            in {"OPTIMAL", "FEASIBLE"}
            for variant in row.get("variant_results", [])
        )
    ]
    unforced_zero = [
        row
        for row in records
        if (row.get("unforced_result") or {}).get("status")
        in {"OPTIMAL", "FEASIBLE"}
    ]
    nonterminal = [
        row
        for row in records
        if (
            (row.get("unforced_result") or {}).get("status")
            not in {
                None,
                "OPTIMAL",
                "FEASIBLE",
                "INFEASIBLE",
                "STRUCTURAL_EMPTY",
            }
            or any(
                (variant.get("forced_result") or {}).get("status")
                not in {
                    None,
                    "OPTIMAL",
                    "FEASIBLE",
                    "INFEASIBLE",
                    "STRUCTURAL_EMPTY",
                }
                for variant in row.get("variant_results", [])
            )
        )
    ]
    materialized = materialize_candidates(
        e061=e061,
        parent=parent,
        proposal=proposal,
        records=records,
    )
    if forced_zero:
        verdict = "DIRECT_OWNER_BRIDGE_REALIZES_FORCED_HALF_SIGNATURE"
        decision = "VALIDATE_FORCED_ZERO_IN_FULL_CONDITIONAL_BINDING"
    elif unforced_zero:
        verdict = "DIRECT_OWNER_MOVE_CREATES_DIFFERENT_TWO_ZERO_RELATION"
        decision = "INSPECT_UNFORCED_ZERO_THEN_VALIDATE_FULL_BINDING"
    elif nonterminal:
        verdict = "DIRECT_OWNER_BRIDGE_REPLAY_NONTERMINAL"
        decision = "CONTINUE_ONLY_NONTERMINAL_ALTERNATIVES"
    else:
        verdict = "DIRECT_OWNER_BRIDGE_REJECTED_BY_EXACT_SIGNATURE_CONSUMER"
        decision = "TEST_NEXT_DIRECT_OR_SHORTEST_MULTI_OWNER_BRIDGE"

    status_counts: Counter[str] = Counter()
    for row in records:
        status_counts[str(row["candidate_status"])] += 1
        unforced = row.get("unforced_result") or {}
        if unforced.get("status"):
            status_counts[f"unforced::{unforced['status']}"] += 1
        for variant in row.get("variant_results", []):
            forced = variant.get("forced_result") or {}
            if forced.get("status"):
                status_counts[f"forced::{forced['status']}"] += 1
            elif variant.get("mapping", {}).get("status"):
                status_counts[
                    f"mapping::{variant['mapping']['status']}"
                ] += 1
    return {
        "schema": "zmd_zero_condition_e073_direct_owner_bridge_replay_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "module_origin_audit": {
            "direct": direct_origins,
            "nested": nested_origins,
        },
        "proposal": proposal,
        "alternative_count": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "forced_zero_count": len(forced_zero),
        "unforced_zero_count": len(unforced_zero),
        "nonterminal_count": len(nonterminal),
        "selected_forced_zero_records": forced_zero[:20],
        "selected_unforced_zero_records": unforced_zero[:20],
        "nonterminal_records": nonterminal,
        "materialized_candidates": materialized,
        "alternative_records_path": str(RECORDS_PATH.relative_to(ROOT)),
        "alternative_records_sha256": sha256_file(RECORDS_PATH),
        "decision": decision,
        "truth_boundary": (
            "E069 fixed first-zero parent with every legal fixed-outside pose "
            "alternative of one E072-selected path owner; original destination, "
            "real filling mode, and exact terminal-cell variant forced in the "
            "corrected two-zero signature consumer."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E073 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "owner": result["proposal"]["path_owners"][0],
                    "alternatives": result["alternative_count"],
                    "forced_zero": result["forced_zero_count"],
                    "unforced_zero": result["unforced_zero_count"],
                    "nonterminal": result["nonterminal_count"],
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
            "schema": "zmd_zero_condition_e073_direct_owner_bridge_replay_failure_v1",
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
