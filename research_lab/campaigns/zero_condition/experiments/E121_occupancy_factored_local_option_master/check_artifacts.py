#!/usr/bin/env python3
"""Independent equivalence and artifact check for E121."""

from __future__ import annotations

from collections import Counter, defaultdict
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
RUNNER = HERE / "run_e121.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E121_occupancy_factored_local_option_master/run-001"
)
RESULT = RUN / "RESULT.json"
PRIMARY = RUN / "PRIMARY_RESULT.json"
FALLBACK = RUN / "FALLBACK_RESULT.json"
ENCODING = RUN / "ENCODING_AUDIT.json"
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
E115_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E115_separator_template_state_full_consumer/run_e115.py"
)
E117_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E117_high_geometry_local_front_benders/run_e117.py"
)
E117_ITERATIONS = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E117_high_geometry_local_front_benders/run-001/BENDERS_ITERATIONS.json"
)
E118_ITERATIONS = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E118_solver_diverse_local_front_benders/run-001/CONTINUATION_ITERATIONS.json"
)
E120_ENCODING = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E120_integrated_local_option_master/run-002/ENCODING_AUDIT.json"
)

EXPECTED = {
    RUNNER: "e32017a2ff968509d9c16a86e8df526433097142a7c1f2438c77f3ee56cf1fd7",
    RESULT: "8ee3f5097ae3e8980c49ce517be5af9af8d45ff69604aaed655c0d5e22f9a529",
    PRIMARY: "93b7014ea346ba5c78e843a44038ab10fe8f0a5de2da8c1afe4dcc43775268c4",
    FALLBACK: "69a3e3840aa54d0d4a9c01a324c0d7c512bba67943776c7d569e1b412ec15e2e",
    ENCODING: "591f90027517606f6f1c79d808ac1a58555749177172dfd1ce4da4dd18a82209",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E115_RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
    E117_RUNNER: "ff51200bdec11733a27f3a82ffd63dc49a193e36fb1573f7c33d8a8b57d2f3f2",
    E117_ITERATIONS: "ce2cd833601707fdda6bf16ef42bff891eae2076db600da0eb4e3f34a0cfaa29",
    E118_ITERATIONS: "0952a02be86887fc37c612e5043e4e92b8fbf1ee66733a34640ef48cfc1d0c24",
    E120_ENCODING: "102e0e9b5f80548d3f013ec6a67bce774b8753bf9f4ee78f29ae4c3fb3a060ed",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def independent_census(
    *,
    e095: types.ModuleType,
    language: Mapping[str, Any],
    options_by_global: Mapping[int, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    fixed_solid = set(language["context"]["fixed_solid"])
    coverers: dict[tuple[int, int], list[int]] = defaultdict(list)
    for row in language["rows"]:
        global_index = int(row["global_row_index"])
        for value in row["body"]:
            coverers[value].append(global_index)
    relevant = {
        value
        for options in options_by_global.values()
        for option in options
        for field in ("input_cells", "output_cells")
        for value in option[field]
        if e095.in_grid(value)
        and value not in fixed_solid
        and value in coverers
    }
    channel_terms = sum(len(coverers[value]) for value in relevant)
    maximum_channel = max(len(coverers[value]) for value in relevant)
    front_terms = 0
    front_constraints = 0
    maximum_front_terms = 0
    fixed_total = 0
    duplicates = 0
    grouped: Counter[int] = Counter()
    for options in options_by_global.values():
        for option in options:
            grouped[len(option["class_keys"])] += 1
            for front_cells in (option["input_cells"], option["output_cells"]):
                dynamic = sum(value in relevant for value in front_cells)
                fixed = sum(
                    (not e095.in_grid(value)) or value in fixed_solid
                    for value in front_cells
                )
                front_terms += dynamic
                fixed_total += fixed
                front_constraints += 1
                maximum_front_terms = max(maximum_front_terms, dynamic)
                duplicates += len(front_cells) - len(set(front_cells))
    factored = channel_terms + front_terms
    return {
        "candidate_count": len(language["rows"]),
        "body_variable_count": len(language["rows"]),
        "occupancy_variable_count": len(relevant),
        "option_variable_count": sum(len(value) for value in options_by_global.values()),
        "body_option_link_constraint_count": len(options_by_global),
        "occupancy_channel_constraint_count": len(relevant),
        "occupancy_channel_term_count": channel_terms,
        "maximum_occupancy_channel_support": maximum_channel,
        "front_constraint_count": front_constraints,
        "front_occupancy_term_count": front_terms,
        "maximum_front_occupancy_terms": maximum_front_terms,
        "fixed_blocked_term_total": fixed_total,
        "duplicate_front_cell_occurrence_count": duplicates,
        "grouped_class_key_count_distribution": {
            str(key): int(value) for key, value in sorted(grouped.items())
        },
        "factored_dynamic_term_count": factored,
    }


def geometry_equivalence(
    *,
    e095: types.ModuleType,
    e117: types.ModuleType,
    language: Mapping[str, Any],
    options_by_global: Mapping[int, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    rows_by_global = {
        int(row["global_row_index"]): row for row in language["rows"]
    }
    fixed_solid = set(language["context"]["fixed_solid"])
    checked_geometries = 0
    checked_options = 0
    for packet_path in (E117_ITERATIONS, E118_ITERATIONS):
        for record in load(packet_path)["records"]:
            if record.get("master_status") != "OPTIMAL" and record.get(
                "terminal_status"
            ) != "OPTIMAL":
                continue
            selected = set(map(int, record["selected_global_row_indices"]))
            occupied = set(fixed_solid)
            for index in selected:
                occupied.update(rows_by_global[index]["body"])
            for global_index, options in options_by_global.items():
                if global_index not in selected:
                    continue
                for option in options:
                    expanded = e117.option_viable(option, occupied)
                    input_blocked = sum(value in occupied for value in option["input_cells"])
                    output_blocked = sum(value in occupied for value in option["output_cells"])
                    factored = (
                        input_blocked
                        <= len(option["input_cells"]) - int(option["need_in"])
                        and output_blocked
                        <= len(option["output_cells"]) - int(option["need_out"])
                    )
                    require(expanded == factored, "expanded/factored option drift")
                    checked_options += 1
            replay = e117.local_front_check(
                e095=e095,
                selected_globals=selected,
                options_by_global=options_by_global,
                rows_by_global=rows_by_global,
                fixed_solid=fixed_solid,
            )
            require(replay["locally_live"] is False, "known geometry became live")
            checked_geometries += 1
    require(checked_geometries == 47, "known geometry count drift")
    return {
        "checked_geometry_count": checked_geometries,
        "checked_selected_option_count": checked_options,
        "all_expanded_factored_option_results_equal": True,
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E121 check: {OUTPUT}")
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E121 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E121 artifact identity drift: {path}")
        artifact_records[str(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load(RESULT)
    primary = load(PRIMARY)
    fallback = load(FALLBACK)
    encoding = load(ENCODING)
    expanded = load(E120_ENCODING)
    require(result["verdict"] == "OCCUPANCY_FACTORED_LOCAL_OPTION_MASTER_CENSORED", "verdict drift")
    require(result["decision"] == "RUN_SPATIAL_COLLAR_AUDIT_OR_SWITCH_SKELETON", "decision drift")
    require(primary["status"] == "UNKNOWN" and fallback["status"] == "UNKNOWN", "solver status drift")
    require(int(primary["branches"]) == 0, "primary branch drift")
    require(int(fallback["branches"]) == 11572, "fallback branch drift")
    require(result["consumer"] is None, "UNKNOWN leaked consumer")
    for payload in (primary, fallback):
        require("selected_global_row_indices" not in payload, "UNKNOWN leaked geometry")
        require("selected_local_options" not in payload, "UNKNOWN leaked options")

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e121_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e121_check_e100")
    e115 = source_module(E115_RUNNER, "zmd_e121_check_e115")
    e117 = source_module(E117_RUNNER, "zmd_e121_check_e117")
    runner = source_module(RUNNER, "zmd_e121_check_runner")
    language = e117.build_language(e095=e095, e100=e100, e115=e115)
    options = e117.precompute_options(e095=e095, language=language)
    census = independent_census(
        e095=e095,
        language=language,
        options_by_global=options,
    )
    for key, value in census.items():
        require(encoding[key] == value, f"factored census drift: {key}")
    require(
        int(encoding["expanded_dynamic_term_count"])
        == int(expanded["dynamic_term_count"]),
        "expanded baseline drift",
    )
    expected_ratio = int(expanded["dynamic_term_count"]) / int(
        census["factored_dynamic_term_count"]
    )
    require(
        abs(float(encoding["dynamic_term_reduction_ratio"]) - expected_ratio)
        < 1e-12,
        "reduction ratio drift",
    )

    direct = runner.build_factored_model(
        e095=e095,
        e117=e117,
        language=language,
        options_by_global=options,
        add_redundant_cuts=False,
    )
    with_cuts = runner.build_factored_model(
        e095=e095,
        e117=e117,
        language=language,
        options_by_global=options,
        add_redundant_cuts=True,
    )
    require(direct["model"].Validate() == "", "direct factored model invalid")
    require(with_cuts["model"].Validate() == "", "cut factored model invalid")
    require(direct["encoding_audit"]["redundant_cut_count"] == 0, "direct cut leakage")
    require(with_cuts["encoding_audit"]["redundant_cut_count"] == 587, "cut import drift")
    equivalence = geometry_equivalence(
        e095=e095,
        e117=e117,
        language=language,
        options_by_global=options,
    )

    payload = {
        "schema": "zmd_e121_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "OCCUPANCY_FACTORING_EXACT_THIRTY_SEVEN_FOLD_TERM_REDUCTION_BOTH_ARMS_CENSORED",
        "artifact_records": artifact_records,
        "independent_census": census,
        "expanded_dynamic_term_count": int(expanded["dynamic_term_count"]),
        "factored_dynamic_term_count": int(census["factored_dynamic_term_count"]),
        "dynamic_term_reduction_ratio": expected_ratio,
        "geometry_equivalence": equivalence,
        "direct_model_valid": True,
        "redundant_cut_model_valid": True,
        "primary_status": primary["status"],
        "primary_branches": primary["branches"],
        "fallback_status": fallback["status"],
        "fallback_branches": fallback["branches"],
        "decision": result["decision"],
        "truth_boundary": (
            "The checker independently reconstructs the occupancy channels and "
            "matches expanded option viability across all 47 known geometries. "
            "The factorization is exact, but both complete searches remain UNKNOWN."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "expanded_dynamic_term_count": payload[
                    "expanded_dynamic_term_count"
                ],
                "factored_dynamic_term_count": payload[
                    "factored_dynamic_term_count"
                ],
                "dynamic_term_reduction_ratio": payload[
                    "dynamic_term_reduction_ratio"
                ],
                "primary_status": primary["status"],
                "fallback_status": fallback["status"],
                "decision": payload["decision"],
                "output_path": str(OUTPUT.relative_to(ROOT)),
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
