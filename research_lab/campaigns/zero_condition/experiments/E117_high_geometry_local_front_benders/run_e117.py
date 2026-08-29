#!/usr/bin/env python3
"""E117: geometry-first local-front Benders for the x42-high language."""

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
    "E117_high_geometry_local_front_benders/run-001"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E095_y41_module_product_decomposition/run_e095.py"
E100_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E100_source_stable_reserved_x42_hybrid/run_e100.py"
E101_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E101_x42_allocation_handshake/run_e101.py"
E101_BODY = ROOT / "research_lab/local/zero_condition/E101_x42_allocation_handshake/run-001/BODY_ONLY_RESULT.json"
E103_RUN = ROOT / "research_lab/local/zero_condition/E103_high_side_interface_capacity_audit/run-003"
E103_RESULT = E103_RUN / "RESULT.json"
E103_CHECK = E103_RUN / "ARTIFACT_CHECK.json"
E103_LIVE = E103_RUN / "LIVE_HIGH_CANDIDATES.json"
E110_RUN = ROOT / "research_lab/local/zero_condition/E110_explicit_separator_template_duty_atlas/run-001"
E110_PROJECTION = E110_RUN / "SEPARATOR_TEMPLATE_PROJECTION.json"
E110_CHECK = E110_RUN / "ARTIFACT_CHECK.json"
E114_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E114_e110_fixed_geometry_direct_consumer/run_e114.py"
E114_RUN = ROOT / "research_lab/local/zero_condition/E114_e110_fixed_geometry_direct_consumer/run-001"
E114_DIAGNOSTICS = E114_RUN / "FIXED_GEOMETRY_DEATH_DIAGNOSTICS.json"
E114_CHECK = E114_RUN / "ARTIFACT_CHECK.json"
E115_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E115_separator_template_state_full_consumer/run_e115.py"
E115_RUN = ROOT / "research_lab/local/zero_condition/E115_separator_template_state_full_consumer/run-001"
E115_STATE_RESULTS = E115_RUN / "STATE_CONSUMER_RESULTS.json"
E115_CHECK = E115_RUN / "ARTIFACT_CHECK.json"
E116_DURABLE = ROOT / "research_lab/campaigns/zero_condition/experiments/E116_low_cardinality_separator_tuple_discriminator/RESULT.txt"
E116_RESULT = ROOT / "research_lab/local/zero_condition/E116_low_cardinality_separator_tuple_discriminator/run-001/RESULT.json"
E116_CHECK = E116_RESULT.with_name("ARTIFACT_CHECK.json")

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E103_RESULT: "6fefd59e3b8c5551501a2504e9c620bb6cc5468ac5847b92baa20a8ec6e6a32c",
    E103_CHECK: "63ba0d4085263d12c153db0f639bfd984f9bfd373de0b9828eeaf6e94f98850d",
    E103_LIVE: "ebf0c34b174df7036cf6c4bf2f3283dd4ea303998f62520cbd0c74d70aebfd08",
    E110_PROJECTION: "73570c931c8e8c053ec5a17feaa821e4e69511443882eac01110b470a6537413",
    E110_CHECK: "4b25595170b280f34951f563e61c5a17de46e1cc6b6afbfa97ee7e9421b17bf6",
    E114_RUNNER: "e893bdc7df70ce93f66c3976a06e3fd15e2d81b492fd2463b9d17cec4cd16e5d",
    E114_DIAGNOSTICS: "a8e0f73fd99efb63e5220a2b4137700255d95e30a27c3a2060d71e06df99ed12",
    E114_CHECK: "36b224f752e05e92e58a0d161e8d59e3dd59595c290abb55f896a2a29d471aef",
    E115_RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
    E115_STATE_RESULTS: "41f0560f5170d127fc7cbaeea379d47f70dd712f9eeb123e9b42a83148ae7a06",
    E115_CHECK: "7e76312570612dc299f73e7dec192fdaa19fc13dee28b958055146571955d76a",
    E116_DURABLE: "f52c19e3ad51fbdf81662729a56cc6acaa14c3c7f6a2c66e375ab6b089a15032",
    E116_RESULT: "2b7b93d9a4d1235a7284d9f11eb6512fbc13a3ceb4eda42928cdf7e7c15e378d",
    E116_CHECK: "f186dda5a79c50a094953a98147bf5668dd8c1e75ec11226e86064184d946d37",
}

TEMPLATES = ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4")
HIGH_TEMPLATE_COUNTS = {
    "manufacturing_3x3": 10,
    "manufacturing_5x5": 6,
    "manufacturing_6x4": 10,
}
LOW_TEMPLATE_COUNTS = {
    "manufacturing_3x3": 43,
    "manufacturing_5x5": 11,
    "manufacturing_6x4": 11,
}
EXPECTED_LIVE_COUNT = 1205
EXPECTED_BODY_COUNT = 26
EXPECTED_OPEN_VECTOR_COUNT = 25
EXACT_NEGATIVE_SEPARATOR_VECTORS = {(0, 3, 0), (5, 0, 0)}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
            default=str,
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


def source_module(
    path: Path,
    name: str,
    package: str | None = None,
) -> types.ModuleType:
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
        raise RuntimeError("E117 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E117 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E117 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }
    if load_json(E103_CHECK).get("status") != "PASS":
        raise RuntimeError("E117 E103 check is not PASS")
    if load_json(E110_CHECK).get("status") != "PASS":
        raise RuntimeError("E117 E110 check is not PASS")
    if load_json(E114_CHECK).get("status") != "PASS":
        raise RuntimeError("E117 E114 check is not PASS")
    e115 = load_json(E115_STATE_RESULTS)
    observed_negative = {
        tuple(map(int, row["separator_template_vector"]))
        for row in e115["records"]
        if row["high"]["status"] == "INFEASIBLE"
    }
    if observed_negative != EXACT_NEGATIVE_SEPARATOR_VECTORS:
        raise RuntimeError("E117 E115 negative-vector drift")
    e116 = load_json(E116_CHECK)
    if e116.get("status") != "PASS" or e116.get("decision") != (
        "RETIRE_SEPARATOR_CLASS_FIXATION_AS_PRIMARY_DISCRIMINATOR"
    ):
        raise RuntimeError("E117 E116 continuation drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def build_language(
    *,
    e095: types.ModuleType,
    e100: types.ModuleType,
    e115: types.ModuleType,
) -> dict[str, Any]:
    restricted = e100.build_restricted_context(e095)
    language = e115.load_language(restricted)
    live_globals = set(map(int, language["live_global_indices"]))
    if len(live_globals) != EXPECTED_LIVE_COUNT:
        raise RuntimeError("E117 live-row count drift")
    restricted_rows = [dict(row) for row in restricted["rows"]]
    rows: list[dict[str, Any]] = []
    for global_index, row in enumerate(restricted_rows):
        if global_index not in live_globals:
            continue
        rows.append(
            {
                **row,
                "global_row_index": global_index,
                "separator_group": str(language["group_by_global"][global_index]),
            }
        )
    if len(rows) != EXPECTED_LIVE_COUNT:
        raise RuntimeError("E117 restored live rows drift")

    all_vectors = set(language["allowed_by_vector"])
    open_vectors = sorted(all_vectors - EXACT_NEGATIVE_SEPARATOR_VECTORS)
    if len(all_vectors) != 27 or len(open_vectors) != EXPECTED_OPEN_VECTOR_COUNT:
        raise RuntimeError("E117 separator vector set drift")

    diagnostics = load_json(E114_DIAGNOSTICS)
    zero_by_vector = {
        tuple(map(int, record["separator_template_vector"])): int(
            record["zero_domain_body_count"]
        )
        for record in diagnostics["records"]
    }
    e110 = load_json(E110_PROJECTION)
    records_by_vector = {
        tuple(map(int, record["vector"])): record for record in e110["vectors"]
    }
    hint_vector = min(open_vectors, key=lambda vector: (zero_by_vector[vector], vector))
    hint_globals = set(
        map(
            int,
            records_by_vector[hint_vector]["witness"]["selected_global_indices"],
        )
    )
    if len(hint_globals) != EXPECTED_BODY_COUNT or not hint_globals <= live_globals:
        raise RuntimeError("E117 hint geometry drift")
    return {
        "restricted": restricted,
        "context": restricted["base"],
        "class_keys": tuple(language["class_keys"]),
        "global_class_counts": dict(language["global_class_counts"]),
        "rows": rows,
        "open_vectors": open_vectors,
        "hint_vector": hint_vector,
        "hint_globals": hint_globals,
    }


def precompute_options(
    *,
    e095: types.ModuleType,
    language: Mapping[str, Any],
) -> dict[int, tuple[dict[str, Any], ...]]:
    context = language["context"]
    class_keys = tuple(language["class_keys"])
    pools = context["pools"]
    output: dict[int, tuple[dict[str, Any], ...]] = {}
    for row in language["rows"]:
        global_index = int(row["global_row_index"])
        template = str(row["template"])
        forced = e095.STABLE_CLASS_BY_BODY.get(str(row["body_digest"]))
        unique: dict[tuple[Any, ...], dict[str, Any]] = {}
        for pose_index in row["mode_pose_indices"]:
            pose = pools[template][int(pose_index)]
            input_cells = tuple(e095.cell(value) for value in pose["input_port_cells"])
            output_cells = tuple(e095.cell(value) for value in pose["output_port_cells"])
            for class_key in class_keys:
                if class_key[1] != template:
                    continue
                need_in, need_out = int(class_key[2]), int(class_key[3])
                if forced is not None and (need_in, need_out) != tuple(forced):
                    continue
                if need_in > len(input_cells) or need_out > len(output_cells):
                    continue
                identity = (
                    int(pose_index),
                    need_in,
                    need_out,
                    input_cells,
                    output_cells,
                )
                record = unique.setdefault(
                    identity,
                    {
                        "pose_index": int(pose_index),
                        "need_in": need_in,
                        "need_out": need_out,
                        "input_cells": input_cells,
                        "output_cells": output_cells,
                        "class_keys": [],
                    },
                )
                record["class_keys"].append(class_key)
        options = tuple(
            {
                **record,
                "class_keys": tuple(sorted(record["class_keys"])),
            }
            for _identity, record in sorted(unique.items())
        )
        if not options:
            raise RuntimeError(f"E117 no syntactic options for live row: {global_index}")
        output[global_index] = options
    return output


def build_master(language: Mapping[str, Any]) -> dict[str, Any]:
    rows = list(language["rows"])
    model = cp_model.CpModel()
    body_vars = [model.NewBoolVar(f"body_{index}") for index in range(len(rows))]
    local_by_global = {
        int(row["global_row_index"]): index for index, row in enumerate(rows)
    }
    if len(local_by_global) != len(rows):
        raise RuntimeError("E117 master global identity collision")

    by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, row in enumerate(rows):
        for value in row["body"]:
            by_cell[value].append(body_vars[index])
    for terms in by_cell.values():
        if len(terms) > 1:
            model.AddAtMostOne(terms)

    for template, required in sorted(HIGH_TEMPLATE_COUNTS.items()):
        model.Add(
            sum(
                body_vars[index]
                for index, row in enumerate(rows)
                if str(row["template"]) == template
            )
            == int(required)
        )

    coverage = set(language["context"]["fixed_coverage"])
    disabled_unpowered = 0
    for index, row in enumerate(rows):
        if not set(row["body"]) & coverage:
            model.Add(body_vars[index] == 0)
            disabled_unpowered += 1
    if disabled_unpowered:
        raise RuntimeError(f"E117 E103 live row lost power: {disabled_unpowered}")

    stable_indices: dict[str, int] = {}
    for instance_id, footprint in language["context"]["stable_footprints"].items():
        matches = [
            index for index, row in enumerate(rows) if tuple(row["body"]) == footprint
        ]
        if len(matches) != 1:
            raise RuntimeError(f"E117 stable remap drift: {instance_id}")
        stable_indices[instance_id] = matches[0]
        model.Add(body_vars[matches[0]] == 1)

    separator_count_vars: list[Any] = []
    for template in TEMPLATES:
        variable = model.NewIntVar(
            0,
            int(HIGH_TEMPLATE_COUNTS[template]),
            f"separator_{template}",
        )
        separator_count_vars.append(variable)
        model.Add(
            variable
            == sum(
                body_vars[index]
                for index, row in enumerate(rows)
                if str(row["separator_group"]) == "separator"
                and str(row["template"]) == template
            )
        )
    model.AddAllowedAssignments(
        separator_count_vars,
        [list(vector) for vector in language["open_vectors"]],
    )

    matched_hints = 0
    for index, row in enumerate(rows):
        hinted = int(row["global_row_index"]) in language["hint_globals"]
        model.AddHint(body_vars[index], int(hinted))
        matched_hints += int(hinted)
    if matched_hints != EXPECTED_BODY_COUNT:
        raise RuntimeError("E117 hint count drift")

    error = model.Validate()
    if error:
        raise RuntimeError(f"E117 master invalid: {error}")
    return {
        "model": model,
        "rows": rows,
        "body_vars": body_vars,
        "local_by_global": local_by_global,
        "separator_count_vars": separator_count_vars,
        "stable_indices": stable_indices,
        "matched_hint_count": matched_hints,
        "cut_keys": set(),
    }


def master_solver(*, seconds: float, seed: int) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = int(seed)
    solver.parameters.stop_after_first_solution = True
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.randomize_search = True
    return solver


def option_viable(
    *,
    e095: types.ModuleType,
    option: Mapping[str, Any],
    occupied: set[tuple[int, int]],
) -> bool:
    free_inputs = sum(
        e095.in_grid(value) and value not in occupied
        for value in option["input_cells"]
    )
    free_outputs = sum(
        e095.in_grid(value) and value not in occupied
        for value in option["output_cells"]
    )
    return free_inputs >= int(option["need_in"]) and free_outputs >= int(
        option["need_out"]
    )


def body_empty_under(
    *,
    e095: types.ModuleType,
    subject_global: int,
    blocker_globals: Sequence[int],
    options_by_global: Mapping[int, Sequence[Mapping[str, Any]]],
    rows_by_global: Mapping[int, Mapping[str, Any]],
    fixed_solid: set[tuple[int, int]],
) -> bool:
    occupied = set(fixed_solid)
    occupied.update(rows_by_global[subject_global]["body"])
    for global_index in blocker_globals:
        occupied.update(rows_by_global[int(global_index)]["body"])
    return not any(
        option_viable(e095=e095, option=option, occupied=occupied)
        for option in options_by_global[subject_global]
    )


def local_front_check(
    *,
    e095: types.ModuleType,
    selected_globals: set[int],
    options_by_global: Mapping[int, Sequence[Mapping[str, Any]]],
    rows_by_global: Mapping[int, Mapping[str, Any]],
    fixed_solid: set[tuple[int, int]],
) -> dict[str, Any]:
    deaths: list[dict[str, Any]] = []
    viable_option_count_by_body: dict[str, int] = {}
    for subject_global in sorted(selected_globals):
        all_options = options_by_global[subject_global]
        front_union = {
            value
            for option in all_options
            for field in ("input_cells", "output_cells")
            for value in option[field]
            if e095.in_grid(value)
        }
        blocker_impact: dict[int, int] = {}
        for other_global in sorted(selected_globals - {subject_global}):
            overlap = front_union & set(rows_by_global[other_global]["body"])
            if overlap:
                blocker_impact[other_global] = len(overlap)
        relevant = sorted(blocker_impact)
        occupied = set(fixed_solid)
        occupied.update(rows_by_global[subject_global]["body"])
        for blocker in relevant:
            occupied.update(rows_by_global[blocker]["body"])
        viable_options = [
            option
            for option in all_options
            if option_viable(e095=e095, option=option, occupied=occupied)
        ]
        viable_option_count_by_body[str(subject_global)] = len(viable_options)
        if viable_options:
            continue
        core = sorted(relevant, key=lambda value: (blocker_impact[value], value))
        retained: list[int] = list(core)
        for blocker in list(core):
            trial = [value for value in retained if value != blocker]
            if body_empty_under(
                e095=e095,
                subject_global=subject_global,
                blocker_globals=trial,
                options_by_global=options_by_global,
                rows_by_global=rows_by_global,
                fixed_solid=fixed_solid,
            ):
                retained = trial
        if not body_empty_under(
            e095=e095,
            subject_global=subject_global,
            blocker_globals=retained,
            options_by_global=options_by_global,
            rows_by_global=rows_by_global,
            fixed_solid=fixed_solid,
        ):
            raise RuntimeError("E117 minimized blocker core lost emptiness")
        for blocker in retained:
            trial = [value for value in retained if value != blocker]
            if body_empty_under(
                e095=e095,
                subject_global=subject_global,
                blocker_globals=trial,
                options_by_global=options_by_global,
                rows_by_global=rows_by_global,
                fixed_solid=fixed_solid,
            ):
                raise RuntimeError("E117 blocker core is not inclusion-minimal")
        deaths.append(
            {
                "subject_global_row_index": subject_global,
                "subject_body_digest": str(
                    rows_by_global[subject_global]["body_digest"]
                ),
                "subject_template": str(rows_by_global[subject_global]["template"]),
                "subject_group": str(
                    rows_by_global[subject_global]["separator_group"]
                ),
                "syntactic_option_count": len(all_options),
                "relevant_selected_blocker_count": len(relevant),
                "core_size": len(retained),
                "core_global_row_indices": retained,
                "core_body_digests": [
                    str(rows_by_global[value]["body_digest"]) for value in retained
                ],
                "cut_key": stable_digest((subject_global, retained)),
            }
        )
    return {
        "selected_body_count": len(selected_globals),
        "locally_live": not deaths,
        "empty_body_count": len(deaths),
        "deaths": deaths,
        "viable_option_count_by_body": viable_option_count_by_body,
    }


def add_death_cuts(
    *,
    master: dict[str, Any],
    deaths: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    added: list[dict[str, Any]] = []
    for death in deaths:
        key = str(death["cut_key"])
        if key in master["cut_keys"]:
            continue
        subject_local = master["local_by_global"][
            int(death["subject_global_row_index"])
        ]
        blocker_locals = [
            master["local_by_global"][int(value)]
            for value in death["core_global_row_indices"]
        ]
        master["model"].Add(
            master["body_vars"][subject_local]
            + sum(master["body_vars"][index] for index in blocker_locals)
            <= len(blocker_locals)
        )
        master["cut_keys"].add(key)
        added.append(dict(death))
    return added


def class_hall_diagnosis(
    *,
    e095: types.ModuleType,
    selected_globals: set[int],
    options_by_global: Mapping[int, Sequence[Mapping[str, Any]]],
    rows_by_global: Mapping[int, Mapping[str, Any]],
    fixed_solid: set[tuple[int, int]],
    class_keys: Sequence[tuple[str, str, int, int]],
    class_caps: Mapping[tuple[str, str, int, int], int],
) -> dict[str, Any]:
    occupied = set(fixed_solid)
    for global_index in selected_globals:
        occupied.update(rows_by_global[global_index]["body"])
    allowed: dict[int, set[tuple[str, str, int, int]]] = {}
    for global_index in selected_globals:
        values: set[tuple[str, str, int, int]] = set()
        for option in options_by_global[global_index]:
            if option_viable(e095=e095, option=option, occupied=occupied):
                values.update(tuple(key) for key in option["class_keys"])
        allowed[global_index] = values
    if any(not values for values in allowed.values()):
        raise RuntimeError("E117 Hall diagnosis received locally-dead geometry")
    violations: list[dict[str, Any]] = []
    for mask in range(1, 1 << len(class_keys)):
        subset = {
            class_keys[index]
            for index in range(len(class_keys))
            if mask & (1 << index)
        }
        forced = [
            global_index
            for global_index, values in allowed.items()
            if values <= subset
        ]
        capacity = sum(int(class_caps[key]) for key in subset)
        if len(forced) > capacity:
            violations.append(
                {
                    "class_subset": [list(key) for key in sorted(subset)],
                    "capacity": capacity,
                    "forced_body_count": len(forced),
                    "excess": len(forced) - capacity,
                    "forced_global_row_indices": sorted(forced),
                }
            )
    violations.sort(
        key=lambda row: (
            -int(row["excess"]),
            len(row["class_subset"]),
            row["class_subset"],
        )
    )
    return {
        "allowed_class_count_distribution": dict(
            sorted(Counter(len(values) for values in allowed.values()).items())
        ),
        "hall_violation_count": len(violations),
        "strongest_hall_violation": violations[0] if violations else None,
    }


def run(
    *,
    run_dir: Path,
    master_seconds: float,
    high_primary_seconds: float,
    high_fallback_seconds: float,
    low_seconds: float,
    max_iterations: int,
    total_seconds: float,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E117 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e117_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e117_source_e100")
    e101 = source_module(E101_RUNNER, "zmd_e117_source_e101")
    e114 = source_module(E114_RUNNER, "zmd_e117_source_e114")
    e115 = source_module(E115_RUNNER, "zmd_e117_source_e115")
    language = build_language(e095=e095, e100=e100, e115=e115)
    options_by_global = precompute_options(e095=e095, language=language)
    master = build_master(language)
    rows_by_global = {
        int(row["global_row_index"]): row for row in language["rows"]
    }
    fixed_solid = set(language["context"]["fixed_solid"])

    unary_dead = [
        global_index
        for global_index in sorted(rows_by_global)
        if body_empty_under(
            e095=e095,
            subject_global=global_index,
            blocker_globals=[],
            options_by_global=options_by_global,
            rows_by_global=rows_by_global,
            fixed_solid=fixed_solid,
        )
    ]
    if unary_dead:
        raise RuntimeError(f"E117 E103 live rows are unary-dead: {unary_dead[:10]}")

    started = time.monotonic()
    iterations: list[dict[str, Any]] = []
    cut_records: list[dict[str, Any]] = []
    locally_live_geometry: dict[str, Any] | None = None
    high_result: dict[str, Any] | None = None
    high_hall: dict[str, Any] | None = None
    low_result: dict[str, Any] | None = None
    module_b: dict[str, Any] | None = None
    combined: dict[str, Any] | None = None
    module_b_path = run_dir / "MODULE_B_WITNESS.json"
    combined_path = run_dir / "COMBINED_WITNESS.json"
    master_terminal_status = "NOT_RUN"
    module_b_path = run_dir / "MODULE_B_WITNESS.json"
    combined_path = run_dir / "COMBINED_WITNESS.json"

    for iteration in range(max_iterations):
        remaining = float(total_seconds) - (time.monotonic() - started)
        if remaining <= 1.0:
            master_terminal_status = "TOTAL_BUDGET_EXHAUSTED"
            break
        solver = master_solver(
            seconds=min(float(master_seconds), max(0.5, remaining - 0.25)),
            seed=117100 + iteration,
        )
        before = process_snapshot()
        solve_started = time.monotonic()
        status_code = solver.Solve(master["model"])
        elapsed = time.monotonic() - solve_started
        after = process_snapshot()
        status = solver.StatusName(status_code)
        master_terminal_status = status
        iteration_record: dict[str, Any] = {
            "iteration": iteration,
            "master_status": status,
            "master_elapsed_seconds": elapsed,
            "master_branches": int(solver.NumBranches()),
            "master_conflicts": int(solver.NumConflicts()),
            "cut_count_before": len(master["cut_keys"]),
            "process_before": before,
            "process_after": after,
        }
        if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            iterations.append(iteration_record)
            break
        selected_locals = [
            index
            for index, variable in enumerate(master["body_vars"])
            if solver.Value(variable)
        ]
        if len(selected_locals) != EXPECTED_BODY_COUNT:
            raise RuntimeError("E117 master selected body count drift")
        selected_globals = {
            int(master["rows"][index]["global_row_index"])
            for index in selected_locals
        }
        separator_vector = tuple(
            int(solver.Value(variable))
            for variable in master["separator_count_vars"]
        )
        if separator_vector not in set(language["open_vectors"]):
            raise RuntimeError("E117 master separator vector escaped allowed set")
        check = local_front_check(
            e095=e095,
            selected_globals=selected_globals,
            options_by_global=options_by_global,
            rows_by_global=rows_by_global,
            fixed_solid=fixed_solid,
        )
        iteration_record.update(
            {
                "selected_global_row_indices": sorted(selected_globals),
                "selected_body_digest": stable_digest(
                    sorted(
                        str(rows_by_global[value]["body_digest"])
                        for value in selected_globals
                    )
                ),
                "separator_template_vector": list(separator_vector),
                "local_front": check,
            }
        )
        if check["locally_live"]:
            locally_live_geometry = {
                "iteration": iteration,
                "selected_global_row_indices": sorted(selected_globals),
                "selected_body_digest": iteration_record["selected_body_digest"],
                "separator_template_vector": list(separator_vector),
                "viable_option_count_by_body": check[
                    "viable_option_count_by_body"
                ],
            }
            iteration_record["new_cut_count"] = 0
            iterations.append(iteration_record)
            break
        added = add_death_cuts(master=master, deaths=check["deaths"])
        if not added:
            raise RuntimeError("E117 front-dead geometry produced no new cuts")
        cut_records.extend(
            {
                **record,
                "source_iteration": iteration,
            }
            for record in added
        )
        iteration_record["new_cut_count"] = len(added)
        iteration_record["cut_count_after"] = len(master["cut_keys"])
        iterations.append(iteration_record)

    cuts_path = run_dir / "LOCAL_FRONT_BLOCKER_CUTS.json"
    dump_exclusive(
        cuts_path,
        {
            "schema": "zmd_e117_local_front_blocker_cuts_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "cut_count": len(cut_records),
            "unique_cut_count": len({record["cut_key"] for record in cut_records}),
            "cuts": cut_records,
            "truth_boundary": (
                "Each cut forbids selecting its subject with all listed blockers. "
                "The inclusion-minimal core is sufficient to keep every local option dead."
            ),
        },
    )
    iterations_path = run_dir / "BENDERS_ITERATIONS.json"
    dump_exclusive(
        iterations_path,
        {
            "schema": "zmd_e117_benders_iterations_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "iteration_count": len(iterations),
            "master_terminal_status": master_terminal_status,
            "locally_live_geometry_found": locally_live_geometry is not None,
            "records": iterations,
        },
    )

    geometry_path = run_dir / "LOCALLY_LIVE_GEOMETRY.json"
    high_path = run_dir / "HIGH_FIXED_GEOMETRY_RESULT.json"
    low_path = run_dir / "LOW_COMPLEMENT_RESULT.json"
    if locally_live_geometry is not None:
        dump_exclusive(geometry_path, locally_live_geometry)
        selected_globals = set(
            map(int, locally_live_geometry["selected_global_row_indices"])
        )

        def high_builder() -> dict[str, Any]:
            bundle = e114.fix_geometry(
                e095=e095,
                e101=e101,
                restricted=language["restricted"],
                selected_indices=selected_globals,
            )
            bundle["base_context"] = language["context"]
            return bundle

        remaining = float(total_seconds) - (time.monotonic() - started)
        primary_budget = min(
            float(high_primary_seconds), max(0.5, remaining - 0.25)
        )
        fallback_budget = min(
            float(high_fallback_seconds),
            max(0.0, remaining - primary_budget - 0.25),
        )
        high_solve = e114.solve_with_fallback(
            builder=high_builder,
            e095=e095,
            primary_seconds=primary_budget,
            fallback_seconds=fallback_budget,
            seed=117500,
        )
        high_result = (
            high_solve["fallback"]
            if high_solve["fallback"] is not None
            else high_solve["primary"]
        )
        dump_exclusive(
            high_path,
            {
                "primary": high_solve["primary"],
                "fallback": high_solve["fallback"],
                "terminal": high_result,
            },
        )
        if high_result["status"] == "INFEASIBLE":
            high_hall = class_hall_diagnosis(
                e095=e095,
                selected_globals=selected_globals,
                options_by_global=options_by_global,
                rows_by_global=rows_by_global,
                fixed_solid=fixed_solid,
                class_keys=language["class_keys"],
                class_caps=language["global_class_counts"],
            )
        elif high_result["status"] in {"OPTIMAL", "FEASIBLE"}:
            complement = e101.complement_allocation(
                language["class_keys"],
                language["global_class_counts"],
                list(map(int, high_result["allocation_tuple"])),
            )
            low_hints = set(
                map(int, load_json(E101_BODY)["selected_body_indices"])
            )
            low_bundle = e101.build_side_model(
                e095=e095,
                restricted=language["restricted"],
                side="low",
                template_counts=LOW_TEMPLATE_COUNTS,
                body_hint_indices=low_hints,
                fixed_allocation=complement,
            )
            low_bundle["base_context"] = language["context"]
            remaining = float(total_seconds) - (time.monotonic() - started)
            low_result = e114.solve_bundle(
                e095=e095,
                bundle=low_bundle,
                seconds=min(float(low_seconds), max(0.5, remaining - 0.25)),
                seed=117700,
                profile="multiworker_automatic",
            )
            dump_exclusive(low_path, low_result)
            if low_result["status"] in {"OPTIMAL", "FEASIBLE"}:
                pair = e101.combine_side_witnesses(
                    e095=e095,
                    restricted=language["restricted"],
                    low=low_result,
                    high=high_result,
                )
                module_b = pair["module_b"]
                combined = pair["combined"]
                dump_exclusive(module_b_path, module_b)
                dump_exclusive(combined_path, combined)

    if combined is not None:
        verdict = "LOCAL_FRONT_BENDERS_REACHES_219_BODY_NATIVE_FRONT_WITNESS"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    elif high_result is not None and high_result["status"] in {
        "OPTIMAL",
        "FEASIBLE",
    }:
        verdict = "LOCALLY_LIVE_HIGH_GEOMETRY_HAS_FULL_HIGH_WITNESS"
        decision = "CONTINUE_ONLY_X42_LOW_ALLOCATION_HANDSHAKE"
    elif locally_live_geometry is not None:
        verdict = "LOCALLY_LIVE_HIGH_GEOMETRY_FOUND_FULL_CLASS_CONSUMER_NOT_PAIRED"
        decision = "FREEZE_GEOMETRY_AND_DECOMPOSE_CLASS_ASSIGNMENT"
    elif master_terminal_status == "INFEASIBLE":
        verdict = "OPEN_X42_SEPARATOR_STATES_LOCAL_FRONT_INFEASIBLE"
        decision = "RETIRE_SOURCE_STABLE_X42_SUFFICIENT_CONSTRUCTOR"
    else:
        verdict = "HIGH_GEOMETRY_LOCAL_FRONT_BENDERS_CENSORED"
        decision = "CONTINUE_FROM_PERSISTED_BLOCKER_CUTS"

    result = {
        "schema": "zmd_e117_high_geometry_local_front_benders_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "master_seconds_per_iteration": master_seconds,
            "high_primary_seconds": high_primary_seconds,
            "high_fallback_seconds": high_fallback_seconds,
            "low_seconds": low_seconds,
            "max_iterations": max_iterations,
            "total_seconds": total_seconds,
            "source_isolated_helpers": True,
        },
        "language": {
            "live_candidate_count": len(language["rows"]),
            "open_separator_template_vector_count": len(language["open_vectors"]),
            "excluded_exact_negative_vectors": [
                list(vector) for vector in sorted(EXACT_NEGATIVE_SEPARATOR_VECTORS)
            ],
            "hint_separator_template_vector": list(language["hint_vector"]),
            "syntactic_option_count": sum(
                len(values) for values in options_by_global.values()
            ),
            "unary_dead_candidate_count": len(unary_dead),
        },
        "benders": {
            "iterations_path": display(iterations_path),
            "iterations_sha256": sha256_file(iterations_path),
            "iteration_count": len(iterations),
            "master_terminal_status": master_terminal_status,
            "cuts_path": display(cuts_path),
            "cuts_sha256": sha256_file(cuts_path),
            "cut_count": len(cut_records),
            "locally_live_geometry_found": locally_live_geometry is not None,
        },
        "locally_live_geometry": (
            {
                "path": display(geometry_path),
                "sha256": sha256_file(geometry_path),
                **locally_live_geometry,
            }
            if locally_live_geometry is not None
            else None
        ),
        "high_consumer": (
            {
                "path": display(high_path),
                "sha256": sha256_file(high_path),
                "status": high_result["status"],
                "elapsed_seconds": high_result["elapsed_seconds"],
                "branches": high_result["branches"],
                "conflicts": high_result["conflicts"],
                "hall_diagnosis": high_hall,
            }
            if high_result is not None
            else None
        ),
        "low_consumer": (
            {
                "path": display(low_path),
                "sha256": sha256_file(low_path),
                "status": low_result["status"],
                "elapsed_seconds": low_result["elapsed_seconds"],
                "branches": low_result["branches"],
                "conflicts": low_result["conflicts"],
            }
            if low_result is not None
            else None
        ),
        "module_b_witness": (
            {
                "path": display(module_b_path),
                "sha256": sha256_file(module_b_path),
                "selected_body_count": module_b["selected_body_count"],
                "selected_assignment_digest": module_b["selected_assignment_digest"],
            }
            if module_b is not None
            else None
        ),
        "combined_witness": (
            {
                "path": display(combined_path),
                "sha256": sha256_file(combined_path),
                "status": combined["status"],
                "selected_manufacturing_count": combined[
                    "selected_manufacturing_count"
                ],
                "selected_assignment_digest": combined[
                    "selected_assignment_digest"
                ],
            }
            if combined is not None
            else None
        ),
        "total_elapsed_seconds": time.monotonic() - started,
        "truth_boundary": (
            "Blocker cuts prove only local mode/class death under selected body "
            "containment. A locally-live geometry still requires global class assignment."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--master-seconds", type=float, default=5.0)
    parser.add_argument("--high-primary-seconds", type=float, default=25.0)
    parser.add_argument("--high-fallback-seconds", type=float, default=25.0)
    parser.add_argument("--low-seconds", type=float, default=30.0)
    parser.add_argument("--max-iterations", type=int, default=80)
    parser.add_argument("--total-seconds", type=float, default=240.0)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            master_seconds=float(args.master_seconds),
            high_primary_seconds=float(args.high_primary_seconds),
            high_fallback_seconds=float(args.high_fallback_seconds),
            low_seconds=float(args.low_seconds),
            max_iterations=int(args.max_iterations),
            total_seconds=float(args.total_seconds),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "benders": result["benders"],
                    "locally_live_geometry": result[
                        "locally_live_geometry"
                    ]
                    is not None,
                    "high_consumer": result["high_consumer"],
                    "low_consumer": result["low_consumer"],
                    "combined_witness": result["combined_witness"] is not None,
                    "total_elapsed_seconds": result["total_elapsed_seconds"],
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
            "schema": "zmd_e117_execution_failure_v1",
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
