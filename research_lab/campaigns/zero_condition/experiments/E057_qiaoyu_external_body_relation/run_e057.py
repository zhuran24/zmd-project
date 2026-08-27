#!/usr/bin/env python3
"""E057: add one core-side 6x4 body and seek the second zero."""

from __future__ import annotations

from collections import Counter
import copy
import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E057_qiaoyu_external_body_relation/run-004"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
BEST_WITNESS_PATH = OUT / "BEST_JOINT_WITNESS.json"
BEST_ASSIGNMENT_PATH = OUT / "BEST_ASSIGNMENT.json"
BEST_LAYOUT_PATH = OUT / "BEST_LAYOUT.json"

E055_RESULT = ROOT / "research_lab/local/zero_condition/E055_causal_pair_assignment_frontier/run-002/RESULT.json"
E055_ASSIGNMENT = E055_RESULT.with_name("BEST_ASSIGNMENT.json")
E055_WITNESS = E055_RESULT.with_name("BEST_JOINT_WITNESS.json")
E056_RESULT = ROOT / "research_lab/local/zero_condition/E056_causal_pair_mode_frontier/run-001/RESULT.json"
E056_POSITIVE = E056_RESULT.with_name("POSITIVE_RESULT.json")
E056_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E056_causal_pair_mode_frontier/run_e056.py"
E055_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E055_causal_pair_assignment_frontier/run_e055.py"
E053_HELPER = ROOT / "research_lab/campaigns/zero_condition/experiments/E053_merged_6x4_first_zero_joint/run_e053.py"
E051_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E051_positive_commodity_frontier/run_e051.py"

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "284000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E055_RESULT: "5a81cd6c58151643b345a888f8bd782ba9c5bbdfe00c21e5ac2beccc90576efa",
    E055_ASSIGNMENT: "bf6d1cfcd4c6aaf649a16b9513044b2023b5a9a1a5b39267ebcaad15ffe2c46b",
    E055_WITNESS: "3b36ad647149af238567b3746e165fc60fbd107d47b10d8ba92bf15e4e2ab559",
    E056_RESULT: "f515b94165bed656f567de2f6be63759d98f4fb3e4628538810650962e74dab8",
    E056_POSITIVE: "e18b93e374318077752a6b054e228a66c67aecfae14e152900613138f3fc1d66",
    E056_RUNNER: "840a30a26e25c485e71b4891dbc68dc9e2c18d8608ffcc0404eda512d17d9e34",
    E055_RUNNER: "5722d921d66f4bd4b7126c42a9be50d47ee4cb2c7c0873f2a3f161d402cabad6",
    E053_HELPER: "4d7e19c30471ffcb9abe68e7b5324bf9703881d6159aa91a46f79ba61ad605ef",
    E051_RUNNER: "e287c3c4323494b894792435b44fe2c23458345ca2f7409b06309170e9c4ca87",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
}

MERGED_BLOCK = "6x4_merged"
ADDED_INSTANCE = "grinder_dense_blue_iron_004"
FINE_ZERO = "fine_buckwheat_powder"
QIAOYU_ZERO = "qiaoyu_capsule"
PARENT_POSITIVE = 18
PARENT_TOTAL = 139
CALIBRATION_SECONDS = 45.0
PRIMARY_SECONDS = 150.0
SECONDARY_SECONDS = 150.0


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str))


def stable_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def dump_exclusive(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(json_safe(payload), ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, capture_output=True)
    return completed.stdout.strip()


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_identity() -> dict[str, Any]:
    mismatches = {key: (os.environ.get(key), value) for key, value in EXPECTED_ENV.items() if os.environ.get(key) != value}
    unexpected = sorted(key for key in os.environ if key.startswith("EXACT_") and key not in EXPECTED_ENV)
    if mismatches or unexpected:
        raise RuntimeError(f"environment mismatch: {mismatches}; unexpected={unexpected}")
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift for {path}: {actual} != {expected}")
    result_55 = load_json(E055_RESULT)
    result_56 = load_json(E056_RESULT)
    positive_56 = load_json(E056_POSITIVE)
    if result_55.get("verdict") != "ASSIGNMENT_FRONTIER_LEX_SATURATED_AT_18_139":
        raise RuntimeError("E057 E055 trigger drift")
    if result_56.get("verdict") != "MODE_FRONTIER_TOTAL_NONTERMINAL":
        raise RuntimeError("E057 E056 terminal drift")
    if positive_56.get("verdict") != "MODE_FRONTIER_ONE_ZERO_OPTIMAL" or int(positive_56["positive_solve"]["positive_commodity_count"]) != 18:
        raise RuntimeError("E057 E056 positive frontier drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output("status", "--porcelain=v1", "--untracked-files=no"),
    }


def expand_context(context: Mapping[str, Any]) -> dict[str, Any]:
    base = context["base"]
    e041 = base["e041"]
    e043 = base["e043"]
    solution = context["warm_solution"]
    pools = base["inputs"]["pools"]
    blocks = [copy.deepcopy(row) for row in context["expanded"]["blocks"]]
    selected_ids_by_block = {str(key): set(values) for key, values in context["expanded"]["selected_ids_by_block"].items()}
    if ADDED_INSTANCE in set().union(*selected_ids_by_block.values()):
        raise RuntimeError("E057 added body already belongs to assignment context")
    row = solution.get(ADDED_INSTANCE)
    if row is None or str(row["facility_type"]) != "manufacturing_6x4":
        raise RuntimeError("E057 added body identity drift")
    if int(row["pose_idx"]) != 6239 or str(row["operation_type"]) != "grinder_dense_blue_iron":
        raise RuntimeError("E057 added body state drift")

    block = next(item for item in blocks if str(item["block_id"]) == MERGED_BLOCK)
    ordered_ids = [str(value) for value in block["source_instance_ids_by_destination"]]
    if ADDED_INSTANCE in ordered_ids:
        raise RuntimeError("E057 duplicate appended body")
    inherited_payloads = [
        copy.deepcopy(value) for value in block["selected_literal_payloads"]
    ]
    inherited_modes = [
        [int(value) for value in values]
        for values in block["mode_pose_indices_by_destination"]
    ]
    ordered_ids.append(ADDED_INSTANCE)
    payloads = [
        *inherited_payloads,
        e043.pose_payload(instance_id=ADDED_INSTANCE, row=row, pools=pools),
    ]
    current_body = e041.body_cells(
        pools=pools,
        facility_type=str(row["facility_type"]),
        pose_idx=int(row["pose_idx"]),
    )
    added_modes = sorted(
        pose_idx
        for pose_idx in range(len(pools[str(row["facility_type"])]))
        if e041.body_cells(
            pools=pools,
            facility_type=str(row["facility_type"]),
            pose_idx=pose_idx,
        )
        == current_body
    )
    if added_modes != [6238, 6239]:
        raise RuntimeError(f"E057 added-body mode drift: {added_modes}")
    operation_counts = Counter(str(solution[instance_id]["operation_type"]) for instance_id in ordered_ids)
    permutation_count = math.factorial(len(ordered_ids))
    for count in operation_counts.values():
        permutation_count //= math.factorial(int(count))
    block["operation_multiset"] = dict(sorted(operation_counts.items()))
    block["operation_diversity"] = len(operation_counts)
    block["selected_literal_count"] = len(payloads)
    block["selected_literal_payloads"] = payloads
    block["selected_literals"] = [str(payload["literal_key"]) for payload in payloads]
    block["source_instance_ids_by_destination"] = ordered_ids
    block["selection_digest"] = stable_digest(payloads)
    block["semantic_permutation_count_including_identity"] = permutation_count
    block["owner_refresh"] = "qiaoyu_external_component15_body"
    block["mode_pose_indices_by_destination"] = [*inherited_modes, added_modes]
    selected_ids_by_block[MERGED_BLOCK].add(ADDED_INSTANCE)

    mode_enabled_ids = {
        str(summary["source_instance_id"])
        for summary in context["expanded"]["mode_summary"]
        if bool(summary["mode_enabled"])
    }
    mode_enabled_ids.add(ADDED_INSTANCE)
    mode_summary = [
        copy.deepcopy(summary) for summary in context["expanded"]["mode_summary"]
    ]
    mode_summary.append(
        {
            "block_id": MERGED_BLOCK,
            "destination": len(ordered_ids) - 1,
            "source_instance_id": ADDED_INSTANCE,
            "facility_type": str(row["facility_type"]),
            "current_operation": str(row["operation_type"]),
            "current_pose_idx": int(row["pose_idx"]),
            "mode_enabled": True,
            "mode_pose_indices": added_modes,
            "mode_count": len(added_modes),
            "body_digest": stable_digest(sorted(current_body)),
        }
    )
    exchangeability = base["e031"].exchangeability_audit(
        neighborhoods=blocks,
        mandatory=base["mandatory"],
        generic=base["generic"],
    )
    if exchangeability.get("status") != "PASS":
        raise RuntimeError("E057 exchangeability audit failed")
    state_by_location = {
        (str(block_id), int(destination)): dict(state)
        for (block_id, destination), state in context["state_by_location"].items()
    }
    added_location = (MERGED_BLOCK, len(ordered_ids) - 1)
    state_by_location[added_location] = {
        "destination": int(added_location[1]),
        "instance_id": ADDED_INSTANCE,
        "operation": str(row["operation_type"]),
        "pose_idx": int(row["pose_idx"]),
    }
    return {
        "blocks": blocks,
        "selected_ids_by_block": selected_ids_by_block,
        "mode_summary": mode_summary,
        "mode_enabled_ids": sorted(mode_enabled_ids),
        "added_instance_id": ADDED_INSTANCE,
        "added_location": added_location,
        "state_by_location": state_by_location,
        "exchangeability": exchangeability,
        "context_digest": stable_digest({
            "blocks": blocks,
            "selected_ids_by_block": {
                key: sorted(values)
                for key, values in selected_ids_by_block.items()
            },
            "mode_summary": mode_summary,
        }),
    }


def constrain_frontier(built: Mapping[str, Any], context: Mapping[str, Any], expanded: Mapping[str, Any], *, impose_qiaoyu_relation: bool) -> None:
    block_by_id = {str(row["block_id"]): row for row in built["blocks"]}
    state_by_location = expanded["state_by_location"]
    source_location = context["source_location"]
    capsule_location = context["capsule_location"]
    added_location = expanded["added_location"]
    for (block_id, destination, mode_index, operation), variable in built["y_vars"].items():
        location = (str(block_id), int(destination))
        current = state_by_location[location]
        pose_idx = int(block_by_id[str(block_id)]["mode_pose_indices_by_destination"][int(destination)][int(mode_index)])
        if impose_qiaoyu_relation and location == source_location:
            if str(operation) != "grinder_dense_blue_iron":
                built["binding_model"].model.Add(variable == 0)
            continue
        if impose_qiaoyu_relation and location == capsule_location:
            if str(operation) != "grinder_fine_buckwheat":
                built["binding_model"].model.Add(variable == 0)
            continue
        if impose_qiaoyu_relation and location == added_location:
            if str(operation) != "filling_capsule":
                built["binding_model"].model.Add(variable == 0)
            continue
        if str(block_id) != MERGED_BLOCK:
            built["binding_model"].model.Add(
                variable == int(str(operation) == str(current["operation"]) and pose_idx == int(current["pose_idx"]))
            )


def build_variant(context: Mapping[str, Any], expanded: Mapping[str, Any], *, fixed_state: Mapping[str, Sequence[Mapping[str, Any]]] | None, objective_kind: str, positive_target: int | None, impose_qiaoyu_relation: bool, require_qiaoyu_zero: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    base = context["base"]
    helper = context["helper"]
    built = helper.build_joint(
        base,
        expanded,
        fixed_state=fixed_state,
        warm_solution=context["warm_solution"],
        warm_endpoint={"selection": context["warm_witness"]["joint_selection"]},
    )
    positive_vars, total_expr = context["e051"].attach_positive_variables(built, prefix=f"e057_{objective_kind}")
    constrain_frontier(built, context, expanded, impose_qiaoyu_relation=impose_qiaoyu_relation)
    for commodity in ([FINE_ZERO, QIAOYU_ZERO] if require_qiaoyu_zero else [FINE_ZERO]):
        built["binding_model"].model.Add(cp_model.LinearExpr.Sum(list(built["compiled"]["mismatch_vars"][commodity].values())) == 0)
    positive_expr = cp_model.LinearExpr.Sum(list(positive_vars.values()))
    if positive_target is not None:
        built["binding_model"].model.Add(positive_expr == int(positive_target))
    if objective_kind == "positive_count":
        built["binding_model"].model.Minimize(positive_expr)
    elif objective_kind == "total_mismatch":
        built["binding_model"].model.Minimize(total_expr)
    else:
        raise ValueError(objective_kind)
    return built, positive_vars


def qiaoyu_domain_audit(built: Mapping[str, Any], expanded: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    routing = built["routing_context"]
    binding_model = built["binding_model"]
    for row in built["domain_stats"]:
        if str(row["block_id"]) != MERGED_BLOCK or str(row["operation"]) != "filling_capsule":
            continue
        components: set[int] = set()
        fronts: set[tuple[int, int]] = set()
        for pattern in binding_model.binding_domains[str(row["virtual_owner"])][1:]:
            for port in pattern.get("output_ports", []):
                if str(port.get("commodity")) != QIAOYU_ZERO:
                    continue
                cell = (int(port["x"]), int(port["y"]))
                component = routing.component_by_cell.get(cell)
                if component is not None:
                    components.add(int(component))
                fronts.add(cell)
        if components:
            rows.append({
                "destination": int(row["destination"]),
                "mode_index": int(row["mode_index"]),
                "pose_idx": int(row["pose_idx"]),
                "active_pattern_count": int(row["active_pattern_count"]),
                "components": sorted(components),
                "fronts": [list(cell) for cell in sorted(fronts)],
                "is_added_body": int(row["destination"]) == int(expanded["added_location"][1]),
            })
    component15 = [row for row in rows if 15 in row["components"]]
    return {
        "all_filling_capsule_mode_count": len(rows),
        "component15_choice_count": len(component15),
        "component15_choices": component15,
        "statement": "The inherited causal grinder occupies one original component-15 body; the appended body restores a third available component-15 capsule destination.",
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e056 = import_module("zmd_e057_e056", E056_RUNNER)
    context = e056.reconstruct()
    context["e056"] = e056
    expanded = expand_context(context)
    base = context["base"]
    fixed_state: dict[str, list[dict[str, Any]]] = {}
    for block in expanded["blocks"]:
        block_id = str(block["block_id"])
        rows: list[dict[str, Any]] = []
        for destination in range(len(block["mode_pose_indices_by_destination"])):
            state = expanded["state_by_location"][(block_id, destination)]
            rows.append(
                {
                    "destination": destination,
                    "instance_id": str(state["instance_id"]),
                    "operation": str(state["operation"]),
                    "pose_idx": int(state["pose_idx"]),
                }
            )
        fixed_state[block_id] = rows
    calibration_built, calibration_positive = build_variant(
        context, expanded,
        fixed_state=fixed_state,
        objective_kind="total_mismatch",
        positive_target=PARENT_POSITIVE,
        impose_qiaoyu_relation=False,
        require_qiaoyu_zero=False,
    )
    with context["helper"].heartbeat("e057_calibration"):
        calibration = context["helper"].solve_variant(
            calibration_built,
            positive_vars=calibration_positive,
            random_seed=57001,
            objective_kind="total_mismatch",
            seconds=CALIBRATION_SECONDS,
        )
    if calibration["status"] != "OPTIMAL" or int(calibration["total_mismatch"]) != PARENT_TOTAL or int(calibration["positive_commodity_count"]) != PARENT_POSITIVE:
        return {
            "schema": "zmd_zero_condition_e057_qiaoyu_external_body_relation_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": "E057_CONTEXT_CALIBRATION_REJECTED",
            "identity": identity,
            "calibration": context["helper"].compact(calibration),
            "decision": "REPAIR_EXTERNAL_BODY_CONTEXT",
            "ledger_effect": "none",
        }

    primary_built, primary_positive = build_variant(
        context, expanded,
        fixed_state=None,
        objective_kind="positive_count",
        positive_target=None,
        impose_qiaoyu_relation=True,
        require_qiaoyu_zero=True,
    )
    domain_audit = qiaoyu_domain_audit(primary_built, expanded)
    if domain_audit["component15_choice_count"] < 4:
        raise RuntimeError(f"E057 expected four component-15 capsule choices: {domain_audit}")
    with context["helper"].heartbeat("e057_positive"):
        primary = context["helper"].solve_variant(
            primary_built,
            positive_vars=primary_positive,
            random_seed=57002,
            objective_kind="positive_count",
            seconds=PRIMARY_SECONDS,
        )
    primary_public = context["helper"].compact(primary)
    if primary["status"] not in {"OPTIMAL", "FEASIBLE"}:
        verdict = "QIAOYU_EXTERNAL_BODY_RELATION_INFEASIBLE" if primary["status"] == "INFEASIBLE" else "QIAOYU_EXTERNAL_BODY_RELATION_NONTERMINAL"
        decision = "SELECT_NEXT_STRUCTURED_CAUSE" if primary["status"] == "INFEASIBLE" else "CONTINUE_OR_REFORMULATE_CAUSAL_SOLVE"
        return {
            "schema": "zmd_zero_condition_e057_qiaoyu_external_body_relation_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "verdict": verdict,
            "identity": identity,
            "calibration": context["helper"].compact(calibration),
            "expanded_context": {
                "context_digest": expanded["context_digest"],
                "added_instance_id": ADDED_INSTANCE,
                "added_location": list(expanded["added_location"]),
                "mode_enabled_destination_count": sum(bool(row["mode_enabled"]) for row in expanded["mode_summary"]),
                "exchangeability": expanded["exchangeability"],
            },
            "qiaoyu_domain_audit": domain_audit,
            "primary": primary_public,
            "secondary": None,
            "materialized": None,
            "decision": decision,
            "truth_boundary": "One appended component-15 6x4 body and one fixed causal relation only.",
            "ledger_effect": "none",
        }

    secondary_built, secondary_positive = build_variant(
        context, expanded,
        fixed_state=None,
        objective_kind="total_mismatch",
        positive_target=int(primary["positive_commodity_count"]),
        impose_qiaoyu_relation=True,
        require_qiaoyu_zero=True,
    )
    with context["helper"].heartbeat("e057_total"):
        secondary = context["helper"].solve_variant(
            secondary_built,
            positive_vars=secondary_positive,
            random_seed=57003,
            objective_kind="total_mismatch",
            seconds=SECONDARY_SECONDS,
        )
    materialized = None
    if secondary["status"] == "OPTIMAL":
        old_paths = (context["helper"].BEST_WITNESS_PATH, context["helper"].BEST_ASSIGNMENT_PATH, context["helper"].BEST_LAYOUT_PATH)
        context["helper"].BEST_WITNESS_PATH = BEST_WITNESS_PATH
        context["helper"].BEST_ASSIGNMENT_PATH = BEST_ASSIGNMENT_PATH
        context["helper"].BEST_LAYOUT_PATH = BEST_LAYOUT_PATH
        try:
            materialized = context["helper"].materialize_and_replay(
                base,
                expanded,
                secondary,
                optimum_positive_count=int(secondary["positive_commodity_count"]),
                required_zero_commodities=[FINE_ZERO, QIAOYU_ZERO],
            )
        finally:
            (context["helper"].BEST_WITNESS_PATH, context["helper"].BEST_ASSIGNMENT_PATH, context["helper"].BEST_LAYOUT_PATH) = old_paths

    if int(primary["positive_commodity_count"]) <= 17:
        verdict = "QIAOYU_EXTERNAL_BODY_SECOND_ZERO_OPTIMAL" if primary["status"] == "OPTIMAL" else "QIAOYU_EXTERNAL_BODY_SECOND_ZERO_FEASIBLE_NONTERMINAL"
        decision = "RECOMPUTE_RESIDUAL_FROM_SECOND_ZERO_STATE" if materialized is not None else "RETAIN_SECOND_ZERO_AND_COMPLETE_SECONDARY_SOLVE"
    else:
        verdict = "QIAOYU_EXTERNAL_BODY_RELATION_NO_SECOND_ZERO"
        decision = "SELECT_NEXT_STRUCTURED_CAUSE"
    return {
        "schema": "zmd_zero_condition_e057_qiaoyu_external_body_relation_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "calibration": context["helper"].compact(calibration),
        "expanded_context": {
            "context_digest": expanded["context_digest"],
            "added_instance_id": ADDED_INSTANCE,
            "added_location": list(expanded["added_location"]),
            "mode_enabled_destination_count": sum(bool(row["mode_enabled"]) for row in expanded["mode_summary"]),
            "exchangeability": expanded["exchangeability"],
        },
        "qiaoyu_domain_audit": domain_audit,
        "primary": primary_public,
        "secondary": context["helper"].compact(secondary),
        "materialized": materialized,
        "decision": decision,
        "truth_boundary": "One appended component-15 6x4 body under the inherited fine-powder causal relation and fixed occupied geometry.",
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists():
        raise FileExistsError("refusing to overwrite E057 terminal result")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(json.dumps({
            "verdict": result["verdict"],
            "calibration": result.get("calibration"),
            "primary": result.get("primary"),
            "secondary": result.get("secondary"),
            "decision": result["decision"],
            "result_path": str(RESULT_PATH),
            "result_sha256": sha256_file(RESULT_PATH),
        }, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e057_qiaoyu_external_body_relation_failure_v1",
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
