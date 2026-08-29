#!/usr/bin/env python3
"""E106: bounded nested template-split frontier under reserved y60."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback
import types
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E106_nested_template_split_frontier/run-001"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E095_y41_module_product_decomposition/run_e095.py"
)
E095_MODULE_A = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001/MODULE_A_RESULT.json"
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
E101_BODY = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E101_x42_allocation_handshake/run-001/BODY_ONLY_RESULT.json"
)
E104_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E104_high_reserved_y60_constructor/run_e104.py"
)
E104_DURABLE = E104_RUNNER.with_name("RESULT.txt")
E104_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E104_high_reserved_y60_constructor/run-002/RESULT.json"
)
E104_CHECK = E104_RESULT.with_name("ARTIFACT_CHECK.json")
E105_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E105_nested_allocation_handshake/run_e105.py"
)
E105_DURABLE = E105_RUNNER.with_name("RESULT.txt")
E105_SNAPSHOT = E105_RUNNER.with_name("MACHINE_SNAPSHOT.json")
E105_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E105_nested_allocation_handshake/run-003/RESULT.json"
)
E105_CHECK = E105_RESULT.with_name("ARTIFACT_CHECK.json")

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E104_RUNNER: "1b2eae0a788e0f4be4cf4af857b8f5b4ceb16f17a215eed41c7d68d656a315fd",
    E104_DURABLE: "359ad5214e751853f97d0944cf47af27ad0b85f8f7b9f8fb2cbdaee6bde46098",
    E104_RESULT: "381c6547ed2b94773de4f1fadfe747459aaed307d6c3461f2875a2bdf4817b04",
    E104_CHECK: "7d2167688af5e8b49233d26df49bfaf764dd372e9c103d9437157db483457d86",
    E105_RUNNER: "7dbdf3be073dd77b6ef091b4302442aa5766882d2f384b285576b84c368588b9",
    E105_DURABLE: "9881812d3d6ce3a0ec4064e9ab8fa95b5c1afa46697b624ae6354ea1cc2721f3",
    E105_SNAPSHOT: "eba0f95cc8722545a45a63f715e4f1e9b8a967a800da025935abeec1204aecee",
    E105_RESULT: "95ae95cc649097aae4010cb5ebe96f6027fefdfac2ee469d877cb8940a009ecb",
    E105_CHECK: "38e1d0f1fde3e689f04a17101805cf3e3c874b5f7941324b552945bab473a346",
}

TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
TOTAL_TEMPLATES = {
    "manufacturing_3x3": 10,
    "manufacturing_5x5": 6,
    "manufacturing_6x4": 10,
}
OUTER_LOW_TEMPLATES = {
    "manufacturing_3x3": 43,
    "manufacturing_5x5": 11,
    "manufacturing_6x4": 11,
}
EXPECTED_BODY_COUNT = 26
EXPECTED_SURVIVORS = 1010
EXPECTED_CLASS_COUNT = 8
INITIAL_UPPER_NOGOOD = (3, 2, 2)
INITIAL_LOWER_NOGOOD = (7, 4, 8)
DEFAULT_MAX_TEMPLATE_PROPOSALS = 4
DEFAULT_MAX_ALLOCATIONS = 3


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def process_snapshot() -> dict[str, int]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "ru_maxrss_kib": int(usage.ru_maxrss),
        "minor_page_faults": int(usage.ru_minflt),
        "major_page_faults": int(usage.ru_majflt),
        "voluntary_context_switches": int(usage.ru_nvcsw),
        "involuntary_context_switches": int(usage.ru_nivcsw),
    }


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
            f"<source-isolated:{path}:{hashlib.sha256(raw).hexdigest()}>",
            "exec",
            dont_inherit=True,
        ),
        module.__dict__,
    )
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E106 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E106 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(f"E106 input drift: {path}: {observed} != {expected}")
        checked[display(path)] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }

    e104 = load_json(E104_RESULT)
    if e104.get("verdict") != "RESERVED_Y60_HIGH_CONSTRUCTOR_CENSORED":
        raise RuntimeError("E106 E104 verdict drift")
    if e104.get("decision") != "EXTERNALIZE_LOWER_UPPER_CLASS_ALLOCATIONS":
        raise RuntimeError("E106 E104 decision drift")
    if load_json(E104_CHECK).get("classification") != "CENSORED_HIGH_NO_ALLOCATION":
        raise RuntimeError("E106 E104 check drift")

    e105 = load_json(E105_RESULT)
    if e105.get("verdict") != "NESTED_TEMPLATE_SPLIT_NATIVE_FRONT_INFEASIBLE":
        raise RuntimeError("E106 E105 verdict drift")
    if e105.get("decision") != "ADD_EXACT_BODY_TEMPLATE_SPLIT_NOGOOD":
        raise RuntimeError("E106 E105 decision drift")
    check = load_json(E105_CHECK)
    if check.get("status") != "PASS" or check.get("classification") != (
        "EXACT_NESTED_TEMPLATE_SPLIT_NOGOOD"
    ):
        raise RuntimeError("E106 E105 check drift")
    body_counts = e105.get("body_only", {}).get("nested_side_template_counts")
    expected_counts = {
        "lower:manufacturing_3x3": 7,
        "lower:manufacturing_5x5": 4,
        "lower:manufacturing_6x4": 8,
        "upper:manufacturing_3x3": 3,
        "upper:manufacturing_5x5": 2,
        "upper:manufacturing_6x4": 2,
    }
    if body_counts != expected_counts:
        raise RuntimeError("E106 E105 split identity drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def solver_for(seed: int, seconds: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = int(seed)
    solver.parameters.stop_after_first_solution = True
    return solver


def build_body_frontier(prepared: Mapping[str, Any]) -> dict[str, Any]:
    rows = [dict(row) for row in prepared["survivors"]]
    if len(rows) != EXPECTED_SURVIVORS:
        raise RuntimeError(f"E106 survivor count drift: {len(rows)}")
    context = prepared["context"]
    model = cp_model.CpModel()
    variables = [model.NewBoolVar(f"frontier_body_{index}") for index in range(len(rows))]
    by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, row in enumerate(rows):
        for value in row["body"]:
            by_cell[value].append(variables[index])
    for terms in by_cell.values():
        if len(terms) > 1:
            model.AddAtMostOne(terms)

    for template, required in sorted(TOTAL_TEMPLATES.items()):
        model.Add(
            sum(
                variables[index]
                for index, row in enumerate(rows)
                if str(row["template"]) == template
            )
            == int(required)
        )

    fixed_coverage = set(context["fixed_coverage"])
    disabled_unpowered = 0
    for index, row in enumerate(rows):
        if not set(row["body"]) & fixed_coverage:
            model.Add(variables[index] == 0)
            disabled_unpowered += 1

    stable_indices: dict[str, int] = {}
    for instance_id, footprint in context["stable_footprints"].items():
        matches = [
            index for index, row in enumerate(rows) if tuple(row["body"]) == footprint
        ]
        if len(matches) != 1:
            raise RuntimeError(f"E106 stable body remap drift: {instance_id}")
        stable_indices[instance_id] = matches[0]
        model.Add(variables[matches[0]] == 1)

    matched_hints = 0
    for index, row in enumerate(rows):
        hinted = int(row["global_row_index"]) in prepared["body_hint_indices"]
        model.AddHint(variables[index], int(hinted))
        matched_hints += int(hinted)
    if matched_hints != 22:
        raise RuntimeError(f"E106 body hint drift: {matched_hints}")

    upper_count_vars: dict[str, Any] = {}
    for template in TEMPLATES:
        maximum = int(TOTAL_TEMPLATES[template])
        variable = model.NewIntVar(0, maximum, f"upper_count_{template}")
        upper_count_vars[template] = variable
        model.Add(
            variable
            == sum(
                variables[index]
                for index, row in enumerate(rows)
                if str(row["nested_side"]) == "upper"
                and str(row["template"]) == template
            )
        )
    ordered_upper_vars = [upper_count_vars[template] for template in TEMPLATES]
    model.AddForbiddenAssignments(ordered_upper_vars, [list(INITIAL_UPPER_NOGOOD)])

    error = model.Validate()
    if error:
        raise RuntimeError(f"E106 body frontier invalid: {error}")
    return {
        "model": model,
        "rows": rows,
        "variables": variables,
        "upper_count_vars": upper_count_vars,
        "ordered_upper_vars": ordered_upper_vars,
        "stable_indices": stable_indices,
        "disabled_unpowered_candidate_count": disabled_unpowered,
        "matched_hint_count": matched_hints,
    }


def split_record(upper: Sequence[int]) -> dict[str, Any]:
    if len(upper) != len(TEMPLATES):
        raise RuntimeError("E106 upper split width drift")
    upper_tuple = tuple(map(int, upper))
    lower_tuple = tuple(
        int(TOTAL_TEMPLATES[template]) - upper_tuple[index]
        for index, template in enumerate(TEMPLATES)
    )
    return {
        "template_order": list(TEMPLATES),
        "upper": list(upper_tuple),
        "lower": list(lower_tuple),
        "upper_counts": {
            template: int(upper_tuple[index])
            for index, template in enumerate(TEMPLATES)
        },
        "lower_counts": {
            template: int(lower_tuple[index])
            for index, template in enumerate(TEMPLATES)
        },
        "upper_body_count": sum(upper_tuple),
        "lower_body_count": sum(lower_tuple),
        "split_digest": stable_digest(
            {
                "template_order": TEMPLATES,
                "upper": upper_tuple,
                "lower": lower_tuple,
            }
        ),
    }


def solve_body_frontier(
    body_model: Mapping[str, Any],
    *,
    seconds: float,
    seed: int,
    forbidden_count_before: int,
) -> dict[str, Any]:
    model = body_model["model"]
    before = process_snapshot()
    started = time.monotonic()
    solver = solver_for(seed, seconds)
    status_code = solver.Solve(model)
    elapsed = time.monotonic() - started
    after = process_snapshot()
    status = solver.StatusName(status_code)
    result: dict[str, Any] = {
        "schema": "zmd_e106_body_template_proposal_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": status,
        "elapsed_seconds": elapsed,
        "seed": seed,
        "solve_seconds": seconds,
        "candidate_count": len(body_model["rows"]),
        "model_variable_count": len(model.Proto().variables),
        "model_constraint_count": len(model.Proto().constraints),
        "disabled_unpowered_candidate_count": body_model[
            "disabled_unpowered_candidate_count"
        ],
        "matched_hint_count": body_model["matched_hint_count"],
        "forbidden_split_count_before": forbidden_count_before,
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "process_before": before,
        "process_after": after,
    }
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected = [
            index
            for index, variable in enumerate(body_model["variables"])
            if solver.Value(variable)
        ]
        if len(selected) != EXPECTED_BODY_COUNT:
            raise RuntimeError("E106 body proposal count drift")
        rows = body_model["rows"]
        upper = [
            int(solver.Value(body_model["upper_count_vars"][template]))
            for template in TEMPLATES
        ]
        split = split_record(upper)
        observed = Counter(
            (str(rows[index]["nested_side"]), str(rows[index]["template"]))
            for index in selected
        )
        expected_observed = Counter()
        for template, count in split["upper_counts"].items():
            expected_observed[("upper", template)] = int(count)
        for template, count in split["lower_counts"].items():
            expected_observed[("lower", template)] = int(count)
        if observed != expected_observed:
            raise RuntimeError("E106 split count replay drift")
        result.update(
            {
                "selected_body_count": len(selected),
                "selected_local_indices": selected,
                "selected_global_indices": [
                    int(rows[index]["global_row_index"]) for index in selected
                ],
                "selected_body_digest": stable_digest(
                    sorted(str(rows[index]["body_digest"]) for index in selected)
                ),
                "split": split,
            }
        )
    return result


def add_split_nogood(body_model: Mapping[str, Any], upper: Sequence[int]) -> None:
    body_model["model"].AddForbiddenAssignments(
        body_model["ordered_upper_vars"],
        [list(map(int, upper))],
    )


def choose_nested_sides(split: Mapping[str, Any]) -> tuple[str, str]:
    counts = {
        "lower": int(split["lower_body_count"]),
        "upper": int(split["upper_body_count"]),
    }
    proposer = min(
        ("lower", "upper"),
        key=lambda side: (
            counts[side],
            812 if side == "lower" else 198,
            side,
        ),
    )
    return proposer, "upper" if proposer == "lower" else "lower"


def nested_template_counts(split: Mapping[str, Any], side: str) -> dict[str, int]:
    value = split[f"{side}_counts"]
    return {template: int(value[template]) for template in TEMPLATES}


def run(
    *,
    run_dir: Path,
    body_seconds: float,
    proposer_seconds: float,
    consumer_seconds: float,
    outer_low_seconds: float,
    max_template_proposals: int,
    max_allocations: int,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E106 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e106_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e106_source_e100")
    e101 = source_module(E101_RUNNER, "zmd_e106_source_e101")
    e104 = source_module(E104_RUNNER, "zmd_e106_source_e104")
    e105 = source_module(E105_RUNNER, "zmd_e106_source_e105")
    prepared = e104.reconstruct(e095=e095, e100=e100)
    body_model = build_body_frontier(prepared)

    global_counts = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    class_keys = tuple(sorted(global_counts))
    if len(class_keys) != EXPECTED_CLASS_COUNT:
        raise RuntimeError("E106 class count drift")
    outer_low_hint_indices = set(map(int, load_json(E101_BODY)["selected_body_indices"]))

    split_nogoods: list[dict[str, Any]] = [
        {
            **split_record(INITIAL_UPPER_NOGOOD),
            "source": "E105",
            "classification": "EXACT_NESTED_TEMPLATE_SPLIT_NOGOOD",
            "evidence": {
                "result_path": display(E105_RESULT),
                "result_sha256": sha256_file(E105_RESULT),
                "check_path": display(E105_CHECK),
                "check_sha256": sha256_file(E105_CHECK),
            },
        }
    ]
    body_records: list[dict[str, Any]] = []
    handshake_records: list[dict[str, Any]] = []
    allocation_nogoods: list[dict[str, Any]] = []
    final_module_b: dict[str, Any] | None = None
    final_combined: dict[str, Any] | None = None
    total_high_allocation_nogood: list[int] | None = None
    terminal = "TEMPLATE_PROPOSAL_LIMIT"

    for proposal_index in range(max_template_proposals):
        body = solve_body_frontier(
            body_model,
            seconds=body_seconds,
            seed=106100 + proposal_index,
            forbidden_count_before=len(split_nogoods),
        )
        body_path = run_dir / f"BODY_PROPOSAL_{proposal_index:02d}.json"
        dump_exclusive(body_path, body)
        body_record: dict[str, Any] = {
            "proposal_index": proposal_index,
            "path": display(body_path),
            "sha256": sha256_file(body_path),
            "status": body["status"],
            "elapsed_seconds": body["elapsed_seconds"],
            "branches": body["branches"],
            "conflicts": body["conflicts"],
            "forbidden_split_count_before": len(split_nogoods),
        }
        body_records.append(body_record)
        if body["status"] == "INFEASIBLE":
            terminal = "BODY_FRONTIER_INFEASIBLE"
            break
        if body["status"] not in {"OPTIMAL", "FEASIBLE"}:
            terminal = f"BODY_FRONTIER_{body['status']}"
            break

        split = dict(body["split"])
        body_record["split"] = split
        body_record["selected_body_digest"] = body["selected_body_digest"]
        proposer_side, consumer_side = choose_nested_sides(split)
        selected_hint_indices = set(map(int, body["selected_global_indices"]))
        proposer_model = e105.build_nested_model(
            e095=e095,
            prepared=prepared,
            nested_side=proposer_side,
            template_counts=nested_template_counts(split, proposer_side),
            body_hint_indices=selected_hint_indices,
            allocation_caps=global_counts,
        )
        split_closed = False

        for allocation_index in range(max_allocations):
            proposer = e105.solve_nested(
                proposer_model,
                seconds=proposer_seconds,
                seed=106200 + proposal_index * 10 + allocation_index,
            )
            proposer_path = (
                run_dir
                / f"PROPOSER_{proposal_index:02d}_{allocation_index:02d}.json"
            )
            dump_exclusive(proposer_path, proposer)
            record: dict[str, Any] = {
                "proposal_index": proposal_index,
                "allocation_index": allocation_index,
                "split": split,
                "proposer_side": proposer_side,
                "consumer_side": consumer_side,
                "proposer_path": display(proposer_path),
                "proposer_sha256": sha256_file(proposer_path),
                "proposer_status": proposer["status"],
                "proposer_elapsed_seconds": proposer["elapsed_seconds"],
                "proposer_branches": proposer["branches"],
                "proposer_conflicts": proposer["conflicts"],
            }
            handshake_records.append(record)

            if proposer["status"] == "INFEASIBLE":
                if allocation_index > 0:
                    terminal = "PROPOSER_EXHAUSTED_AFTER_ALLOCATION_NOGOODS"
                    record["effect"] = (
                        "EXACT_REMAINDER_EMPTY_REQUIRES_CHAIN_REPLAY_BEFORE_SPLIT_PROMOTION"
                    )
                    break
                upper_vector = list(map(int, split["upper"]))
                add_split_nogood(body_model, upper_vector)
                nogood_path = run_dir / f"SPLIT_NOGOOD_{len(split_nogoods):02d}.json"
                nogood = {
                    "schema": "zmd_e106_exact_nested_template_split_nogood_v1",
                    "created_at_utc": utc_now(),
                    "authority": "research_only_noncertified",
                    "ledger_effect": "none",
                    **split,
                    "source": "E106",
                    "proposal_index": proposal_index,
                    "proposer_side": proposer_side,
                    "classification": "DIRECT_PROPOSER_INFEASIBLE",
                    "proposer_path": display(proposer_path),
                    "proposer_sha256": sha256_file(proposer_path),
                    "truth_boundary": (
                        "Exact only for this lower/upper template split in the "
                        "source-stable manufacturing-free-y60 context."
                    ),
                }
                dump_exclusive(nogood_path, nogood)
                split_nogoods.append(
                    {
                        **nogood,
                        "path": display(nogood_path),
                        "sha256": sha256_file(nogood_path),
                    }
                )
                record["effect"] = "EXACT_TEMPLATE_SPLIT_NOGOOD"
                record["nogood_path"] = display(nogood_path)
                record["nogood_sha256"] = sha256_file(nogood_path)
                split_closed = True
                break

            if proposer["status"] not in {"OPTIMAL", "FEASIBLE"}:
                terminal = f"PROPOSER_{proposer['status']}"
                record["effect"] = "CENSORED_NO_NOGOOD"
                break

            proposer_tuple = list(map(int, proposer["allocation_tuple"]))
            remaining_caps = {
                key: int(global_counts[key]) - proposer_tuple[index]
                for index, key in enumerate(class_keys)
            }
            consumer_model = e105.build_nested_model(
                e095=e095,
                prepared=prepared,
                nested_side=consumer_side,
                template_counts=nested_template_counts(split, consumer_side),
                body_hint_indices=selected_hint_indices,
                allocation_caps=remaining_caps,
            )
            consumer = e105.solve_nested(
                consumer_model,
                seconds=consumer_seconds,
                seed=106300 + proposal_index * 10 + allocation_index,
            )
            consumer_path = (
                run_dir
                / f"CONSUMER_{proposal_index:02d}_{allocation_index:02d}.json"
            )
            dump_exclusive(consumer_path, consumer)
            record.update(
                {
                    "proposer_allocation_tuple": proposer_tuple,
                    "consumer_path": display(consumer_path),
                    "consumer_sha256": sha256_file(consumer_path),
                    "consumer_status": consumer["status"],
                    "consumer_elapsed_seconds": consumer["elapsed_seconds"],
                    "consumer_branches": consumer["branches"],
                    "consumer_conflicts": consumer["conflicts"],
                }
            )

            if consumer["status"] == "INFEASIBLE":
                proposer_model["model"].AddForbiddenAssignments(
                    [proposer_model["allocation_vars"][key] for key in class_keys],
                    [proposer_tuple],
                )
                allocation_nogood = {
                    "proposal_index": proposal_index,
                    "split_digest": split["split_digest"],
                    "proposer_side": proposer_side,
                    "proposer_allocation_tuple": proposer_tuple,
                    "consumer_side": consumer_side,
                    "classification": "EXACT_PROPOSER_ALLOCATION_NOGOOD",
                    "consumer_path": display(consumer_path),
                    "consumer_sha256": sha256_file(consumer_path),
                }
                allocation_nogoods.append(allocation_nogood)
                record["effect"] = "EXACT_PROPOSER_ALLOCATION_NOGOOD"
                continue

            if consumer["status"] not in {"OPTIMAL", "FEASIBLE"}:
                terminal = f"CONSUMER_{consumer['status']}"
                record["effect"] = "CENSORED_NO_NOGOOD"
                break

            high = e105.merge_high(
                class_keys=class_keys,
                left=proposer,
                right=consumer,
            )
            high_path = run_dir / f"HIGH_WITNESS_{proposal_index:02d}_{allocation_index:02d}.json"
            dump_exclusive(high_path, high)
            high_tuple = list(map(int, high["allocation_tuple"]))
            outer_low_allocation = e101.complement_allocation(
                class_keys,
                global_counts,
                high_tuple,
            )
            outer_low_model = e101.build_side_model(
                e095=e095,
                restricted=prepared["restricted"],
                side="low",
                template_counts=OUTER_LOW_TEMPLATES,
                body_hint_indices=outer_low_hint_indices,
                fixed_allocation=outer_low_allocation,
            )
            outer_low = e101.solve_side(
                outer_low_model,
                seconds=outer_low_seconds,
                seed=106400 + proposal_index * 10 + allocation_index,
            )
            outer_low_path = (
                run_dir
                / f"OUTER_LOW_{proposal_index:02d}_{allocation_index:02d}.json"
            )
            dump_exclusive(outer_low_path, outer_low)
            record.update(
                {
                    "high_path": display(high_path),
                    "high_sha256": sha256_file(high_path),
                    "total_high_allocation_tuple": high_tuple,
                    "outer_low_path": display(outer_low_path),
                    "outer_low_sha256": sha256_file(outer_low_path),
                    "outer_low_status": outer_low["status"],
                    "outer_low_elapsed_seconds": outer_low["elapsed_seconds"],
                }
            )

            if outer_low["status"] in {"OPTIMAL", "FEASIBLE"}:
                combined = e101.combine_side_witnesses(
                    e095=e095,
                    restricted=prepared["restricted"],
                    low=outer_low,
                    high=high,
                )
                final_module_b = combined["module_b"]
                final_combined = combined["combined"]
                module_b_path = run_dir / "MODULE_B_WITNESS.json"
                combined_path = run_dir / "COMBINED_WITNESS.json"
                dump_exclusive(module_b_path, final_module_b)
                dump_exclusive(combined_path, final_combined)
                record["effect"] = "PAIRED_219_BODY_NATIVE_FRONT_WITNESS"
                terminal = "FULL_POSITIVE"
                break

            if outer_low["status"] == "INFEASIBLE":
                total_high_allocation_nogood = high_tuple
                record["effect"] = "EXACT_TOTAL_HIGH_ALLOCATION_NOGOOD"
                terminal = "OUTER_LOW_INFEASIBLE"
                break

            record["effect"] = "OUTER_LOW_CENSORED"
            terminal = f"OUTER_LOW_{outer_low['status']}"
            break

        if terminal != "TEMPLATE_PROPOSAL_LIMIT":
            break
        if split_closed:
            continue
        terminal = "ALLOCATION_LIMIT"
        break

    split_store_path = run_dir / "TEMPLATE_SPLIT_NOGOODS.json"
    dump_exclusive(
        split_store_path,
        {
            "schema": "zmd_e106_template_split_nogood_store_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "template_order": list(TEMPLATES),
            "nogood_count": len(split_nogoods),
            "nogoods": split_nogoods,
            "truth_boundary": (
                "Every listed split is backed by exact nested-side infeasibility. "
                "No untested or censored split is included."
            ),
        },
    )

    if terminal == "FULL_POSITIVE":
        verdict = "NESTED_TEMPLATE_FRONTIER_WITNESS_FOUND"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    elif terminal == "BODY_FRONTIER_INFEASIBLE":
        verdict = "RESERVED_Y60_TEMPLATE_FRONTIER_EXHAUSTED"
        decision = "RESTORE_E103_EXPLICIT_Y59_SEPARATOR"
    elif terminal.startswith("BODY_FRONTIER_"):
        verdict = "NESTED_TEMPLATE_BODY_FRONTIER_CENSORED"
        decision = "REPLAY_ONLY_PINNED_BODY_FRONTIER"
    elif terminal == "PROPOSER_EXHAUSTED_AFTER_ALLOCATION_NOGOODS":
        verdict = "NESTED_SPLIT_ALLOCATION_REMAINDER_EXHAUSTED"
        decision = "REPLAY_NOGOOD_CHAIN_BEFORE_PROMOTING_TEMPLATE_SPLIT"
    elif terminal.startswith("PROPOSER_"):
        verdict = "NESTED_TEMPLATE_PROPOSER_CENSORED"
        decision = "REPLAY_ONLY_PINNED_NESTED_PROPOSER"
    elif terminal.startswith("CONSUMER_"):
        verdict = "NESTED_TEMPLATE_CONSUMER_CENSORED"
        decision = "REPLAY_ONLY_PINNED_NESTED_CONSUMER"
    elif terminal == "OUTER_LOW_INFEASIBLE":
        verdict = "NESTED_TEMPLATE_TOTAL_HIGH_ALLOCATION_REJECTED"
        decision = "RECORD_TOTAL_HIGH_ALLOCATION_NOGOOD"
    elif terminal.startswith("OUTER_LOW_"):
        verdict = "NESTED_TEMPLATE_OUTER_LOW_CENSORED"
        decision = "REPLAY_ONLY_PINNED_OUTER_LOW_COMPLEMENT"
    elif terminal == "ALLOCATION_LIMIT":
        verdict = "NESTED_ALLOCATION_VECTOR_LIMIT_REACHED"
        decision = "CONTINUE_FROM_SPLIT_AND_ALLOCATION_NOGOOD_STORE"
    else:
        verdict = "NESTED_TEMPLATE_SPLIT_FRONTIER_LIMIT_REACHED"
        decision = "CONTINUE_FROM_TEMPLATE_SPLIT_NOGOOD_STORE"

    module_b_path = run_dir / "MODULE_B_WITNESS.json"
    combined_path = run_dir / "COMBINED_WITNESS.json"
    result = {
        "schema": "zmd_e106_nested_template_split_frontier_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "terminal": terminal,
        "identity": identity,
        "controls": {
            "body_seconds_per_proposal": body_seconds,
            "proposer_seconds_per_allocation": proposer_seconds,
            "consumer_seconds_per_allocation": consumer_seconds,
            "outer_low_seconds": outer_low_seconds,
            "max_template_proposals": max_template_proposals,
            "max_allocations_per_proposal": max_allocations,
            "source_isolated_helpers": True,
            "initial_upper_split_nogood": list(INITIAL_UPPER_NOGOOD),
        },
        "body_records": body_records,
        "handshake_records": handshake_records,
        "template_split_nogood_store": {
            "path": display(split_store_path),
            "sha256": sha256_file(split_store_path),
            "nogood_count": len(split_nogoods),
            "new_nogood_count": len(split_nogoods) - 1,
        },
        "allocation_nogoods": allocation_nogoods,
        "total_high_allocation_nogood": total_high_allocation_nogood,
        "module_b_witness": (
            {
                "path": display(module_b_path),
                "sha256": sha256_file(module_b_path),
                "selected_body_count": final_module_b["selected_body_count"],
                "selected_assignment_digest": final_module_b[
                    "selected_assignment_digest"
                ],
            }
            if final_module_b is not None
            else None
        ),
        "combined_witness": (
            {
                "path": display(combined_path),
                "sha256": sha256_file(combined_path),
                "status": final_combined["status"],
                "selected_manufacturing_count": final_combined[
                    "selected_manufacturing_count"
                ],
                "selected_assignment_digest": final_combined[
                    "selected_assignment_digest"
                ],
            }
            if final_combined is not None
            else None
        ),
        "truth_boundary": (
            "Only exact nested-side negatives enter the template split store. "
            "Only exact consumer negatives enter the proposer-allocation store. "
            "UNKNOWN creates no nogood. A full replayed positive alone transfers."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--body-seconds", type=float, default=15.0)
    parser.add_argument("--proposer-seconds", type=float, default=35.0)
    parser.add_argument("--consumer-seconds", type=float, default=45.0)
    parser.add_argument("--outer-low-seconds", type=float, default=70.0)
    parser.add_argument(
        "--max-template-proposals",
        type=int,
        default=DEFAULT_MAX_TEMPLATE_PROPOSALS,
    )
    parser.add_argument("--max-allocations", type=int, default=DEFAULT_MAX_ALLOCATIONS)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            body_seconds=float(args.body_seconds),
            proposer_seconds=float(args.proposer_seconds),
            consumer_seconds=float(args.consumer_seconds),
            outer_low_seconds=float(args.outer_low_seconds),
            max_template_proposals=int(args.max_template_proposals),
            max_allocations=int(args.max_allocations),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "terminal": result["terminal"],
                    "body_proposal_count": len(result["body_records"]),
                    "handshake_record_count": len(result["handshake_records"]),
                    "template_split_nogood_count": result[
                        "template_split_nogood_store"
                    ]["nogood_count"],
                    "new_template_split_nogood_count": result[
                        "template_split_nogood_store"
                    ]["new_nogood_count"],
                    "allocation_nogood_count": len(result["allocation_nogoods"]),
                    "combined_witness": result["combined_witness"] is not None,
                    "result_path": display(result_path),
                    "result_sha256": sha256_file(result_path),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e106_execution_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not failure_path.exists():
            dump_exclusive(failure_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
