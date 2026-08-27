#!/usr/bin/env python3
"""E058: exact all-6x4 terminal-signature frontier on the E055 geometry."""

from __future__ import annotations

from collections import Counter, defaultdict
import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E058_all6x4_terminal_signature_frontier/run-004"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
CENSUS_PATH = OUT / "SIGNATURE_CENSUS.json"

E055_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E055_causal_pair_assignment_frontier/run-002/RESULT.json"
)
E055_ASSIGNMENT = E055_RESULT.with_name("BEST_ASSIGNMENT.json")
E055_WITNESS = E055_RESULT.with_name("BEST_JOINT_WITNESS.json")
E057_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E057_qiaoyu_external_body_relation/run-004/RESULT.json"
)
E057_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E057_qiaoyu_external_body_relation/run_e057.py"
)
E056_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E056_causal_pair_mode_frontier/run_e056.py"
)
E041_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E041_joint_port_mode_assignment/run_e041.py"
)
E041_HELPER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E041_joint_port_mode_assignment/conditional_mode_owner_binding.py"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E001_pocket_cut_replay/run_experiment.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "285000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E055_RESULT: "5a81cd6c58151643b345a888f8bd782ba9c5bbdfe00c21e5ac2beccc90576efa",
    E055_ASSIGNMENT: "bf6d1cfcd4c6aaf649a16b9513044b2023b5a9a1a5b39267ebcaad15ffe2c46b",
    E055_WITNESS: "3b36ad647149af238567b3746e165fc60fbd107d47b10d8ba92bf15e4e2ab559",
    E057_RESULT: "1cb96ea6785c0ded75f68f42f0d2d829e0a1c5bc6401b949710a9e524eb708c3",
    E057_RUNNER: "d6180ebdabd5b1ef23b39fc7bddd8b76f39c87e10999d473f7f98f144b84f850",
    E056_RUNNER: "840a30a26e25c485e71b4891dbc68dc9e2c18d8608ffcc0404eda512d17d9e34",
    E041_RUNNER: "5731b294e5c3070617d3a29e8912e4f859da207c6f183354ad9c7194f2d54b06",
    E041_HELPER: "98464fc5c9ee181a69392e582c2194edd0c213965b6c62672ece190fb1370dad",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
}

FACILITY_TYPE = "manufacturing_6x4"
BLOCK_ID = "all6x4_signature"
FINE = "fine_buckwheat_powder"
QIAOYU = "qiaoyu_capsule"
FILLING = "filling_capsule"
FINE_GRINDER = "grinder_fine_buckwheat"
CORE_COMPONENT = 15
EXPECTED_BODY_COUNT = 38
EXPECTED_OPERATION_COUNTS = {
    "filling_capsule": 3,
    "grinder_dense_blue_iron": 17,
    "grinder_dense_source": 9,
    "grinder_fine_buckwheat": 6,
    "packaging_battery": 3,
}
SOLVE_SECONDS = 90.0
SOLVE_WORKERS = 8


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


def verify_identity() -> dict[str, Any]:
    mismatches = {
        key: {"expected": value, "actual": os.environ.get(key)}
        for key, value in EXPECTED_ENV.items()
        if os.environ.get(key) != value
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
    e057 = load_json(E057_RESULT)
    if e057.get("verdict") != "QIAOYU_EXTERNAL_BODY_RELATION_INFEASIBLE":
        raise RuntimeError("E058 E057 trigger verdict drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output(
            "status", "--porcelain=v1", "--untracked-files=no"
        ),
    }


def component_set_for_ports(
    ports: Sequence[Mapping[str, Any]],
    *,
    port_type: str,
    commodity: str,
    routing_context: Any,
) -> tuple[int, ...]:
    components: set[int] = set()
    for port in ports:
        if str(port.get("type")) != port_type:
            continue
        if str(port.get("commodity")) != commodity:
            continue
        cell = (int(port["x"]), int(port["y"]))
        component = routing_context.component_by_cell.get(cell)
        if component is None:
            raise RuntimeError(
                f"active terminal has no free component: {commodity}/{port_type}/{cell}"
            )
        components.add(int(component))
    return tuple(sorted(components))


def terminal_signature(
    pattern: Mapping[str, Any],
    *,
    routing_context: Any,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    input_ports = [dict(row) for row in pattern.get("input_ports", [])]
    output_ports = [dict(row) for row in pattern.get("output_ports", [])]
    return (
        component_set_for_ports(
            input_ports,
            port_type="input",
            commodity=FINE,
            routing_context=routing_context,
        ),
        component_set_for_ports(
            output_ports,
            port_type="output",
            commodity=FINE,
            routing_context=routing_context,
        ),
        component_set_for_ports(
            output_ports,
            port_type="output",
            commodity=QIAOYU,
            routing_context=routing_context,
        ),
    )


def current_signature(
    ports: Sequence[Mapping[str, Any]],
    *,
    instance_id: str,
    routing_context: Any,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    selected = [row for row in ports if str(row.get("instance_id")) == instance_id]
    input_ports = [
        {**row, "type": "input"}
        for row in selected
        if str(row.get("type")) == "in"
    ]
    output_ports = [
        {**row, "type": "output"}
        for row in selected
        if str(row.get("type")) == "out"
    ]
    return terminal_signature(
        {"input_ports": input_ports, "output_ports": output_ports},
        routing_context=routing_context,
    )


def build_signature_census() -> dict[str, Any]:
    from src.models.routing_binding_context import build_routing_binding_context

    e056 = import_module("zmd_e058_e056", E056_RUNNER)
    e041 = import_module("zmd_e058_e041", E041_RUNNER)
    conditional = import_module("zmd_e058_conditional", E041_HELPER)
    context = e056.reconstruct()
    base = context["base"]
    solution = context["warm_solution"]
    witness = load_json(E055_WITNESS)
    inputs = base["inputs"]
    pools = inputs["pools"]
    routing_context = build_routing_binding_context(solution, pools, 70, 70)

    raw_bodies: list[dict[str, Any]] = []
    seen_body: set[str] = set()
    for instance_id, row in solution.items():
        if str(row.get("facility_type")) != FACILITY_TYPE:
            continue
        cells = tuple(
            sorted(
                e041.body_cells(
                    pools=pools,
                    facility_type=FACILITY_TYPE,
                    pose_idx=int(row["pose_idx"]),
                )
            )
        )
        body_digest = stable_digest(cells)
        if body_digest in seen_body:
            raise RuntimeError(f"duplicate 6x4 occupied body: {body_digest}")
        seen_body.add(body_digest)
        modes = sorted(
            pose_idx
            for pose_idx in range(len(pools[FACILITY_TYPE]))
            if tuple(
                sorted(
                    e041.body_cells(
                        pools=pools,
                        facility_type=FACILITY_TYPE,
                        pose_idx=pose_idx,
                    )
                )
            )
            == cells
        )
        current_pose = int(row["pose_idx"])
        if current_pose not in modes:
            raise RuntimeError(f"current pose absent from same-body modes: {instance_id}")
        raw_bodies.append(
            {
                "source_instance_id": str(instance_id),
                "body_digest": body_digest,
                "occupied_cells": [list(cell) for cell in cells],
                "current_operation": str(row["operation_type"]),
                "current_pose_idx": current_pose,
                "mode_pose_indices": modes,
                "sort_key": [list(cells)[0], body_digest],
            }
        )
    raw_bodies.sort(
        key=lambda row: (
            tuple(row["occupied_cells"][0]),
            str(row["body_digest"]),
        )
    )
    if len(raw_bodies) != EXPECTED_BODY_COUNT:
        raise RuntimeError(f"6x4 body count drift: {len(raw_bodies)}")
    operation_counts = Counter(str(row["current_operation"]) for row in raw_bodies)
    if dict(sorted(operation_counts.items())) != EXPECTED_OPERATION_COUNTS:
        raise RuntimeError(f"6x4 operation multiset drift: {operation_counts}")

    payloads: list[dict[str, Any]] = []
    for body in raw_bodies:
        source = str(body["source_instance_id"])
        payloads.append(
            base["e043"].pose_payload(
                instance_id=source,
                row=solution[source],
                pools=pools,
            )
        )
    permutation_count = math.factorial(EXPECTED_BODY_COUNT)
    for count in operation_counts.values():
        permutation_count //= math.factorial(int(count))
    block = {
        "block_id": BLOCK_ID,
        "facility_type": FACILITY_TYPE,
        "operation_multiset": dict(sorted(operation_counts.items())),
        "operation_diversity": len(operation_counts),
        "selected_literal_count": len(payloads),
        "selected_literal_payloads": payloads,
        "selected_literals": [str(row["literal_key"]) for row in payloads],
        "source_instance_ids_by_destination": [
            str(row["source_instance_id"]) for row in raw_bodies
        ],
        "selection_digest": stable_digest(payloads),
        "semantic_permutation_count_including_identity": permutation_count,
        "owner_refresh": "all6x4_terminal_signature",
        "mode_pose_indices_by_destination": [
            [int(value) for value in row["mode_pose_indices"]]
            for row in raw_bodies
        ],
    }
    selected_ids = {
        BLOCK_ID: {str(row["source_instance_id"]) for row in raw_bodies}
    }
    (
        placement_solution,
        virtual_instances,
        virtual_metadata,
        _block_metadata,
    ) = e041.conditional_mode_owner_registration(
        full_solution=solution,
        inputs=inputs,
        blocks=[block],
        selected_ids_by_block=selected_ids,
    )
    plan = inputs["plan"]
    generic = inputs["generic"]
    binding_model = conditional.ConditionalModeOwnerPortBindingModel(
        conditional_owner_metadata=virtual_metadata,
        placement_solution=placement_solution,
        facility_pools=pools,
        instances=[*inputs["instances"], *virtual_instances],
        project_root=HISTORY_ROOT,
        required_generic_outputs=generic.get("required_generic_outputs", {}),
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        generic_input_slots_by_operation=plan["generic_input_slots_by_operation"],
        generic_output_slots_by_operation=plan["generic_output_slots_by_operation"],
        utility_operation_by_template=plan["utility_operation_by_template"],
        canonical_rules_payload=inputs["rules"],
        routing_context=routing_context,
    )
    build_started = time.monotonic()
    binding_model.build(use_overload_separation=False)
    domain_build_seconds = time.monotonic() - build_started

    options_by_body: dict[int, list[dict[str, Any]]] = defaultdict(list)
    operation_signature_stats: dict[str, Counter[str]] = defaultdict(Counter)
    active_pattern_count = 0
    inactive_only_count = 0
    for owner_id in sorted(virtual_metadata):
        metadata = virtual_metadata[owner_id]
        destination = int(metadata["destination"])
        domain = binding_model.binding_domains.get(owner_id)
        if not domain or not bool(domain[0].get("joint_inactive")):
            raise RuntimeError(f"conditional domain drift: {owner_id}")
        if len(domain) == 1:
            inactive_only_count += 1
            continue
        by_signature: dict[
            tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
            int,
        ] = Counter()
        pattern_indices_by_signature: dict[
            tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
            list[int],
        ] = defaultdict(list)
        for active_index, pattern in enumerate(domain[1:]):
            signature = terminal_signature(pattern, routing_context=routing_context)
            by_signature[signature] += 1
            pattern_indices_by_signature[signature].append(active_index)
            active_pattern_count += 1
        for signature, pattern_count in sorted(by_signature.items()):
            fine_in, fine_out, qiaoyu_out = signature
            option = {
                "destination": destination,
                "body_digest": raw_bodies[destination]["body_digest"],
                "source_instance_id": raw_bodies[destination]["source_instance_id"],
                "mode_index": int(metadata["mode_index"]),
                "pose_idx": int(metadata["pose_idx"]),
                "operation": str(metadata["operation"]),
                "fine_input_components": list(fine_in),
                "fine_output_components": list(fine_out),
                "qiaoyu_output_components": list(qiaoyu_out),
                "active_pattern_count": int(pattern_count),
                "active_pattern_indices": pattern_indices_by_signature[signature],
            }
            option["signature_digest"] = stable_digest(
                {
                    "fine_in": fine_in,
                    "fine_out": fine_out,
                    "qiaoyu_out": qiaoyu_out,
                }
            )
            options_by_body[destination].append(option)
            operation_signature_stats[str(metadata["operation"])][
                str(option["signature_digest"])
            ] += int(pattern_count)

    current_ports = [dict(row) for row in witness["joint_port_specs"]]
    dynamic_selected_by_pose: dict[int, dict[str, Any]] = {}
    for rows in witness["selected_pattern_by_block"].values():
        for selected in rows:
            pose_idx = int(selected["pose_idx"])
            if pose_idx in dynamic_selected_by_pose:
                raise RuntimeError(f"duplicate dynamic selected pose: {pose_idx}")
            dynamic_selected_by_pose[pose_idx] = dict(selected)
    current_options: dict[int, int] = {}
    current_signature_transport: dict[int, str] = {}
    for destination, body in enumerate(raw_bodies):
        current_pose = int(body["current_pose_idx"])
        dynamic = dynamic_selected_by_pose.get(current_pose)
        if dynamic is not None:
            selected_pattern = int(dynamic["pattern_index"])
            candidates = [
                index
                for index, option in enumerate(options_by_body[destination])
                if str(option["operation"]) == str(dynamic["operation"])
                and int(option["pose_idx"]) == current_pose
                and selected_pattern in set(option["active_pattern_indices"])
            ]
            transport = "frozen_block_destination_pattern"
        else:
            signature = current_signature(
                current_ports,
                instance_id=str(body["source_instance_id"]),
                routing_context=routing_context,
            )
            candidates = [
                index
                for index, option in enumerate(options_by_body[destination])
                if str(option["operation"]) == str(body["current_operation"])
                and int(option["pose_idx"]) == current_pose
                and tuple(option["fine_input_components"]) == signature[0]
                and tuple(option["fine_output_components"]) == signature[1]
                and tuple(option["qiaoyu_output_components"]) == signature[2]
            ]
            transport = "outside_named_owner_ports"
        if len(candidates) != 1:
            raise RuntimeError(
                f"current signature option drift at body {destination}: {candidates}"
            )
        current_options[destination] = candidates[0]
        current_signature_transport[destination] = transport
        selected_option = options_by_body[destination][candidates[0]]
        body["current_signature"] = {
            "fine_input_components": selected_option["fine_input_components"],
            "fine_output_components": selected_option["fine_output_components"],
            "qiaoyu_output_components": selected_option["qiaoyu_output_components"],
            "transport": transport,
        }

    fixed_fine_sources = {
        int(routing_context.component_by_cell[(int(row["x"]), int(row["y"]))])
        for row in current_ports
        if str(row.get("commodity")) == FINE
        and str(row.get("type")) == "out"
    }
    fixed_fine_sinks = {
        int(routing_context.component_by_cell[(int(row["x"]), int(row["y"]))])
        for row in current_ports
        if str(row.get("commodity")) == FINE
        and str(row.get("type")) == "in"
    }
    qiaoyu_sinks = {
        int(routing_context.component_by_cell[(int(row["x"]), int(row["y"]))])
        for row in current_ports
        if str(row.get("commodity")) == QIAOYU
        and str(row.get("type")) == "in"
    }
    qiaoyu_sources = {
        int(routing_context.component_by_cell[(int(row["x"]), int(row["y"]))])
        for row in current_ports
        if str(row.get("commodity")) == QIAOYU
        and str(row.get("type")) == "out"
    }
    if fixed_fine_sources != fixed_fine_sinks or not fixed_fine_sources:
        raise RuntimeError(
            f"E055 fine-zero witness drift: src={fixed_fine_sources} sink={fixed_fine_sinks}"
        )
    if qiaoyu_sinks != {CORE_COMPONENT}:
        raise RuntimeError(f"qiaoyu core component drift: {qiaoyu_sinks}")
    if qiaoyu_sources == qiaoyu_sinks:
        raise RuntimeError("E055 witness unexpectedly already has qiaoyu zero")

    target_nonempty_operations = {
        str(option["operation"])
        for options in options_by_body.values()
        for option in options
        if option["fine_input_components"]
        or option["fine_output_components"]
        or option["qiaoyu_output_components"]
    }
    if target_nonempty_operations != {FILLING, FINE_GRINDER}:
        raise RuntimeError(
            f"unexpected target-signature operations: {target_nonempty_operations}"
        )
    if any(not options_by_body[index] for index in range(EXPECTED_BODY_COUNT)):
        raise RuntimeError("one or more 6x4 bodies have no active signature option")

    return {
        "schema": "zmd_zero_condition_e058_signature_census_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "body_count": len(raw_bodies),
        "operation_counts": dict(sorted(operation_counts.items())),
        "bodies": raw_bodies,
        "options_by_body": {
            str(key): value for key, value in sorted(options_by_body.items())
        },
        "current_options": {
            str(key): value for key, value in sorted(current_options.items())
        },
        "current_signature_transport": {
            str(key): value
            for key, value in sorted(current_signature_transport.items())
        },
        "fixed_witness": {
            "fine_components": sorted(fixed_fine_sources),
            "qiaoyu_source_components": sorted(qiaoyu_sources),
            "qiaoyu_sink_components": sorted(qiaoyu_sinks),
        },
        "domain_build_seconds": domain_build_seconds,
        "virtual_owner_count": len(virtual_metadata),
        "inactive_only_owner_count": inactive_only_count,
        "active_pattern_count": active_pattern_count,
        "signature_option_count": sum(len(value) for value in options_by_body.values()),
        "operation_signature_stats": {
            operation: {
                "signature_count": len(counter),
                "active_pattern_count": sum(counter.values()),
            }
            for operation, counter in sorted(operation_signature_stats.items())
        },
        "target_nonempty_operations": sorted(target_nonempty_operations),
        "ledger_effect": "none",
    }


def add_exact_or(
    model: cp_model.CpModel,
    *,
    name: str,
    contributors: Sequence[Any],
) -> Any:
    variable = model.NewBoolVar(name)
    if not contributors:
        model.Add(variable == 0)
        return variable
    for contributor in contributors:
        model.Add(variable >= contributor)
    model.Add(variable <= cp_model.LinearExpr.Sum(list(contributors)))
    return variable


def relaxed_options(
    census: Mapping[str, Any],
) -> tuple[dict[int, list[dict[str, Any]]], dict[str, int]]:
    output: dict[int, list[dict[str, Any]]] = {}
    for key, raw_options in census["options_by_body"].items():
        destination = int(key)
        grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
        for raw in raw_options:
            option = dict(raw)
            operation = str(option["operation"])
            operation_class = (
                operation if operation in {FILLING, FINE_GRINDER} else "other"
            )
            group_key = (
                int(option["mode_index"]),
                int(option["pose_idx"]),
                operation_class,
                tuple(option["fine_input_components"]),
                tuple(option["fine_output_components"]),
                tuple(option["qiaoyu_output_components"]),
            )
            if group_key not in grouped:
                option["operation"] = operation_class
                option["collapsed_operations"] = [operation]
                grouped[group_key] = option
            else:
                grouped[group_key]["active_pattern_count"] += int(
                    option["active_pattern_count"]
                )
                grouped[group_key]["collapsed_operations"].append(operation)
        output[destination] = sorted(
            grouped.values(),
            key=lambda row: (
                str(row["operation"]),
                int(row["pose_idx"]),
                str(row["signature_digest"]),
            ),
        )
    return output, {FILLING: 3, FINE_GRINDER: 6, "other": 29}


def solve_arm(
    *,
    name: str,
    census: Mapping[str, Any],
    require_fine: bool,
    require_qiaoyu: bool,
    collapse_other: bool,
    fix_current: bool,
) -> dict[str, Any]:
    if collapse_other:
        options_by_body, operation_counts = relaxed_options(census)
    else:
        options_by_body = {
            int(key): [dict(row) for row in value]
            for key, value in census["options_by_body"].items()
        }
        operation_counts = {
            str(key): int(value)
            for key, value in census["operation_counts"].items()
        }
    bodies = [dict(row) for row in census["bodies"]]
    model = cp_model.CpModel()
    x_vars: dict[tuple[int, int], Any] = {}
    for destination in range(len(bodies)):
        variables: list[Any] = []
        for option_index, _option in enumerate(options_by_body[destination]):
            variable = model.NewBoolVar(f"e058_{name}_{destination}_{option_index}")
            x_vars[(destination, option_index)] = variable
            variables.append(variable)
        model.AddExactlyOne(variables)

    for operation, expected in sorted(operation_counts.items()):
        contributors = [
            x_vars[(destination, option_index)]
            for destination, options in options_by_body.items()
            for option_index, option in enumerate(options)
            if str(option["operation"]) == operation
        ]
        model.Add(cp_model.LinearExpr.Sum(contributors) == int(expected))

    if fix_current:
        if collapse_other:
            raise RuntimeError("fixed-current calibration requires exact operations")
        for destination, option_index in census["current_options"].items():
            model.Add(x_vars[(int(destination), int(option_index))] == 1)

    component_universe = sorted(
        {
            int(component)
            for options in options_by_body.values()
            for option in options
            for field in (
                "fine_input_components",
                "fine_output_components",
                "qiaoyu_output_components",
            )
            for component in option[field]
        }
        | {CORE_COMPONENT}
    )
    fine_sources: dict[int, Any] = {}
    fine_sinks: dict[int, Any] = {}
    qiaoyu_sources: dict[int, Any] = {}
    for component in component_universe:
        fine_sources[component] = add_exact_or(
            model,
            name=f"e058_{name}_fine_src_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, options in options_by_body.items()
                for option_index, option in enumerate(options)
                if component in set(option["fine_output_components"])
            ],
        )
        fine_sinks[component] = add_exact_or(
            model,
            name=f"e058_{name}_fine_sink_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, options in options_by_body.items()
                for option_index, option in enumerate(options)
                if component in set(option["fine_input_components"])
            ],
        )
        qiaoyu_sources[component] = add_exact_or(
            model,
            name=f"e058_{name}_qiaoyu_src_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, options in options_by_body.items()
                for option_index, option in enumerate(options)
                if component in set(option["qiaoyu_output_components"])
            ],
        )

    if require_fine:
        for component in component_universe:
            model.Add(fine_sources[component] == fine_sinks[component])
        model.Add(cp_model.LinearExpr.Sum(list(fine_sources.values())) >= 1)
        model.Add(cp_model.LinearExpr.Sum(list(fine_sinks.values())) >= 1)
    if require_qiaoyu:
        for component in component_universe:
            model.Add(
                qiaoyu_sources[component]
                == int(component == CORE_COMPONENT)
            )

    operation_change_terms: list[Any] = []
    mode_change_terms: list[Any] = []
    for destination, options in options_by_body.items():
        current_operation = str(bodies[destination]["current_operation"])
        current_class = (
            current_operation
            if not collapse_other or current_operation in {FILLING, FINE_GRINDER}
            else "other"
        )
        current_pose = int(bodies[destination]["current_pose_idx"])
        for option_index, option in enumerate(options):
            variable = x_vars[(destination, option_index)]
            if str(option["operation"]) != current_class:
                operation_change_terms.append(variable)
            if int(option["pose_idx"]) != current_pose:
                mode_change_terms.append(variable)
    mode_weight = EXPECTED_BODY_COUNT + 1
    objective = (
        mode_weight * cp_model.LinearExpr.Sum(operation_change_terms)
        + cp_model.LinearExpr.Sum(mode_change_terms)
    )
    model.Minimize(objective)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_SECONDS
    solver.parameters.num_search_workers = SOLVE_WORKERS
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = 58000 + sum(ord(char) for char in name)
    started = time.monotonic()
    status = solver.Solve(model)
    elapsed = time.monotonic() - started
    status_name = solver.StatusName(status)
    result: dict[str, Any] = {
        "name": name,
        "status": status_name,
        "elapsed_seconds": elapsed,
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "best_bound": float(solver.BestObjectiveBound()),
        "objective": None,
        "operation_change_count": None,
        "mode_change_count": None,
        "fine_source_components": None,
        "fine_sink_components": None,
        "qiaoyu_source_components": None,
        "selected_options": None,
        "require_fine": require_fine,
        "require_qiaoyu": require_qiaoyu,
        "collapse_other": collapse_other,
        "fix_current": fix_current,
        "model_size": {
            "variables": len(model.Proto().variables),
            "constraints": len(model.Proto().constraints),
            "signature_choice_variables": len(x_vars),
        },
    }
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return result
    result["objective"] = int(round(solver.ObjectiveValue()))
    selected: list[dict[str, Any]] = []
    operation_changes = 0
    mode_changes = 0
    for destination, options in options_by_body.items():
        indices = [
            index
            for index in range(len(options))
            if solver.Value(x_vars[(destination, index)]) == 1
        ]
        if len(indices) != 1:
            raise RuntimeError(f"E058 option extraction drift: {destination}/{indices}")
        option = dict(options[indices[0]])
        current_operation = str(bodies[destination]["current_operation"])
        current_class = (
            current_operation
            if not collapse_other or current_operation in {FILLING, FINE_GRINDER}
            else "other"
        )
        op_changed = str(option["operation"]) != current_class
        mode_changed = int(option["pose_idx"]) != int(
            bodies[destination]["current_pose_idx"]
        )
        operation_changes += int(op_changed)
        mode_changes += int(mode_changed)
        selected.append(
            {
                **option,
                "operation_changed": op_changed,
                "mode_changed": mode_changed,
            }
        )
    result["operation_change_count"] = operation_changes
    result["mode_change_count"] = mode_changes
    result["fine_source_components"] = sorted(
        component
        for component, variable in fine_sources.items()
        if solver.Value(variable) == 1
    )
    result["fine_sink_components"] = sorted(
        component
        for component, variable in fine_sinks.items()
        if solver.Value(variable) == 1
    )
    result["qiaoyu_source_components"] = sorted(
        component
        for component, variable in qiaoyu_sources.items()
        if solver.Value(variable) == 1
    )
    result["selected_options"] = selected
    return result


def run() -> dict[str, Any]:
    identity = verify_identity()
    census = build_signature_census()
    dump_exclusive(CENSUS_PATH, census)
    arms = {
        "calibration": solve_arm(
            name="calibration",
            census=census,
            require_fine=True,
            require_qiaoyu=False,
            collapse_other=False,
            fix_current=True,
        ),
        "fine_only": solve_arm(
            name="fine_only",
            census=census,
            require_fine=True,
            require_qiaoyu=False,
            collapse_other=False,
            fix_current=False,
        ),
        "qiaoyu_only": solve_arm(
            name="qiaoyu_only",
            census=census,
            require_fine=False,
            require_qiaoyu=True,
            collapse_other=False,
            fix_current=False,
        ),
        "joint": solve_arm(
            name="joint",
            census=census,
            require_fine=True,
            require_qiaoyu=True,
            collapse_other=False,
            fix_current=False,
        ),
        "joint_other_relaxation": solve_arm(
            name="joint_other_relaxation",
            census=census,
            require_fine=True,
            require_qiaoyu=True,
            collapse_other=True,
            fix_current=False,
        ),
    }
    calibration = arms["calibration"]
    fine_only = arms["fine_only"]
    qiaoyu_only = arms["qiaoyu_only"]
    joint = arms["joint"]
    relaxed = arms["joint_other_relaxation"]
    if calibration["status"] not in {"OPTIMAL", "FEASIBLE"}:
        verdict = "TERMINAL_SIGNATURE_CALIBRATION_REJECTED"
        decision = "REPAIR_SIGNATURE_COMPILER"
    elif fine_only["status"] not in {"OPTIMAL", "FEASIBLE"} or qiaoyu_only[
        "status"
    ] not in {"OPTIMAL", "FEASIBLE"}:
        verdict = "TERMINAL_SIGNATURE_SINGLE_CONDITION_REJECTED"
        decision = "REPAIR_SIGNATURE_COMPILER"
    elif relaxed["status"] == "INFEASIBLE":
        verdict = "FIXED_GEOMETRY_6X4_TWO_ZERO_SIGNATURE_CONFLICT"
        decision = "REQUIRE_GEOMETRY_CHANGE_OR_DIFFERENT_FIRST_ZERO_STATE"
    elif joint["status"] == "INFEASIBLE" and relaxed["status"] in {
        "OPTIMAL",
        "FEASIBLE",
    }:
        verdict = "EXACT_6X4_OPERATION_SPLIT_BLOCKS_TWO_ZERO_SIGNATURE"
        decision = "MATERIALIZE_RELAXED_SIGNATURE_CAUSE"
    elif joint["status"] in {"OPTIMAL", "FEASIBLE"}:
        verdict = "TWO_ZERO_SIGNATURE_CANDIDATE"
        decision = "VALIDATE_SIGNATURE_ASSIGNMENT_IN_FULL_JOINT_CONSUMER"
    else:
        verdict = "TWO_ZERO_SIGNATURE_FRONTIER_NONTERMINAL"
        decision = "CONTINUE_OR_REFORMULATE_SIGNATURE_SOLVES"
    return {
        "schema": "zmd_zero_condition_e058_all6x4_signature_frontier_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "census_path": str(CENSUS_PATH.relative_to(ROOT)),
        "census_sha256": sha256_file(CENSUS_PATH),
        "census_summary": {
            key: census[key]
            for key in (
                "body_count",
                "operation_counts",
                "domain_build_seconds",
                "virtual_owner_count",
                "inactive_only_owner_count",
                "active_pattern_count",
                "signature_option_count",
                "operation_signature_stats",
                "fixed_witness",
            )
        },
        "arms": arms,
        "decision": decision,
        "truth_boundary": (
            "Fixed E055 occupied geometry; all 38 current manufacturing-6x4 bodies; "
            "native same-body modes and front-filtered active patterns collapsed only "
            "by fine-input, fine-output, and qiaoyu-output component signatures. The "
            "model omits unrelated terminal uniqueness, generic resources, and full "
            "binding coupling, so infeasibility is scoped sound and feasibility is "
            "proposal-only."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists() or CENSUS_PATH.exists():
        raise FileExistsError("refusing to overwrite E058 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "arms": {
                        key: {
                            "status": value["status"],
                            "objective": value.get("objective"),
                            "operation_changes": value.get("operation_change_count"),
                            "mode_changes": value.get("mode_change_count"),
                        }
                        for key, value in result["arms"].items()
                    },
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
            "schema": "zmd_zero_condition_e058_all6x4_signature_frontier_failure_v1",
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
