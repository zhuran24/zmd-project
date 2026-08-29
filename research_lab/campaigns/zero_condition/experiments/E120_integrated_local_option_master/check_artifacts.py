#!/usr/bin/env python3
"""Independent artifact and semantic audit for E120."""

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
RUNNER = HERE / "run_e120.py"
RUN1 = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E120_integrated_local_option_master/run-001"
)
RUN2 = RUN1.with_name("run-002")
FAILURE = RUN1 / "FAILURE.json"
RESULT = RUN2 / "RESULT.json"
PRIMARY = RUN2 / "PRIMARY_RESULT.json"
FALLBACK = RUN2 / "FALLBACK_RESULT.json"
ENCODING = RUN2 / "ENCODING_AUDIT.json"
OUTPUT = RUN2 / "ARTIFACT_CHECK.json"
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
E118_CUTS = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E118_solver_diverse_local_front_benders/run-001/"
    "MERGED_LOCAL_FRONT_BLOCKER_CUTS.json"
)

EXPECTED = {
    RUNNER: "92b9c0a01b1076e47965e6f4d32a3e1d323b64fdf4c75666db1f3730bb7901b0",
    FAILURE: "e71f567475e637f22c6b183a8d37d26c5fa1f628bb162ab3b614522916b91436",
    RESULT: "f9218f63300dd6f24bdb10668c6944a3fbd1edf7d9ba30d421660f12c2e0eb60",
    PRIMARY: "ae2de80e3aa51971972d60ee5047c16adc2753e2282bab80c47ee91ff89df0ca",
    FALLBACK: "5118b771306ae6a473b579f78214fd2d08cf1fefc5e798f5ec6f043cf435e0e1",
    ENCODING: "102e0e9b5f80548d3f013ec6a67bce774b8753bf9f4ee78f29ae4c3fb3a060ed",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E115_RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
    E117_RUNNER: "ff51200bdec11733a27f3a82ffd63dc49a193e36fb1573f7c33d8a8b57d2f3f2",
    E117_ITERATIONS: "ce2cd833601707fdda6bf16ef42bff891eae2076db600da0eb4e3f34a0cfaa29",
    E118_ITERATIONS: "0952a02be86887fc37c612e5043e4e92b8fbf1ee66733a34640ef48cfc1d0c24",
    E118_CUTS: "93b4a05a9a19c2876cd9146f86ce6cbd11ee6a1923a6fed87f22b29ca5710375",
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


def semantic_census(
    *,
    e095: types.ModuleType,
    language: Mapping[str, Any],
    options_by_global: Mapping[int, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    rows = list(language["rows"])
    fixed_solid = set(language["context"]["fixed_solid"])
    coverers: dict[tuple[int, int], list[int]] = defaultdict(list)
    for row in rows:
        global_index = int(row["global_row_index"])
        for value in row["body"]:
            coverers[value].append(global_index)

    option_count = 0
    front_constraint_count = 0
    dynamic_term_count = 0
    fixed_blocked_total = 0
    maximum_dynamic_terms = 0
    grouped: Counter[int] = Counter()
    for global_index in sorted(options_by_global):
        for option in options_by_global[global_index]:
            option_count += 1
            grouped[len(option["class_keys"])] += 1
            for front_cells in (option["input_cells"], option["output_cells"]):
                fixed_blocked = sum(
                    (not e095.in_grid(value)) or value in fixed_solid
                    for value in front_cells
                )
                dynamic = sum(
                    len(coverers.get(value, ()))
                    for value in front_cells
                    if e095.in_grid(value) and value not in fixed_solid
                )
                front_constraint_count += 1
                dynamic_term_count += dynamic
                fixed_blocked_total += fixed_blocked
                maximum_dynamic_terms = max(maximum_dynamic_terms, dynamic)
    return {
        "candidate_count": len(rows),
        "option_variable_count": option_count,
        "body_option_link_constraint_count": len(options_by_global),
        "front_constraint_count": front_constraint_count,
        "dynamic_term_count": dynamic_term_count,
        "fixed_blocked_term_total": fixed_blocked_total,
        "maximum_dynamic_term_count_per_front_constraint": maximum_dynamic_terms,
        "grouped_class_key_count_distribution": {
            str(key): int(value) for key, value in sorted(grouped.items())
        },
    }


def known_geometry_replay(
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
    records: list[dict[str, Any]] = []
    for cohort, packet_path in (
        ("E117", E117_ITERATIONS),
        ("E118", E118_ITERATIONS),
    ):
        packet = load(packet_path)
        for record in packet["records"]:
            if record.get("master_status") != "OPTIMAL" and record.get(
                "terminal_status"
            ) != "OPTIMAL":
                continue
            selected = set(map(int, record["selected_global_row_indices"]))
            replay = e117.local_front_check(
                e095=e095,
                selected_globals=selected,
                options_by_global=options_by_global,
                rows_by_global=rows_by_global,
                fixed_solid=fixed_solid,
            )
            require(replay["locally_live"] is False, "known geometry became live")
            stored = record["local_front"]
            require(
                int(replay["empty_body_count"])
                == int(stored["empty_body_count"]),
                "known geometry empty-count drift",
            )
            records.append(
                {
                    "cohort": cohort,
                    "iteration": int(record["iteration"]),
                    "empty_body_count": int(replay["empty_body_count"]),
                }
            )
    require(len(records) == 47, f"known geometry count drift: {len(records)}")
    return {
        "geometry_count": len(records),
        "empty_body_count_min": min(row["empty_body_count"] for row in records),
        "empty_body_count_max": max(row["empty_body_count"] for row in records),
        "records": records,
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E120 check: {OUTPUT}")
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E120 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E120 artifact identity drift: {path}")
        artifact_records[str(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    failure = load(FAILURE)
    require(failure["status"] == "EXECUTION_FAILURE", "run-001 status drift")
    require(failure["error"] == "RuntimeError", "run-001 error drift")
    require("MODULE_A_RESULT.json" in failure["detail"], "run-001 cause drift")

    result = load(RESULT)
    primary = load(PRIMARY)
    fallback = load(FALLBACK)
    encoding = load(ENCODING)
    require(result["verdict"] == "INTEGRATED_LOCAL_OPTION_MASTER_CENSORED", "verdict drift")
    require(result["decision"] == "CHANGE_GEOMETRY_REPRESENTATION_OR_SKELETON", "decision drift")
    require(primary["status"] == "UNKNOWN", "primary status drift")
    require(fallback["status"] == "UNKNOWN", "fallback status drift")
    require(int(primary["branches"]) == 0, "primary branch telemetry drift")
    require(int(fallback["branches"]) == 8846, "fallback branch telemetry drift")
    require(int(fallback["encoding_audit"]["redundant_cut_count"]) == 587, "fallback cut drift")
    for payload in (primary, fallback):
        require("selected_global_row_indices" not in payload, "UNKNOWN leaked body witness")
        require("selected_local_options" not in payload, "UNKNOWN leaked option witness")
    require(result["consumer"] is None, "UNKNOWN leaked consumer")

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e120_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e120_check_e100")
    e115 = source_module(E115_RUNNER, "zmd_e120_check_e115")
    e117 = source_module(E117_RUNNER, "zmd_e120_check_e117")
    runner = source_module(RUNNER, "zmd_e120_check_runner")
    language = e117.build_language(e095=e095, e100=e100, e115=e115)
    options = e117.precompute_options(e095=e095, language=language)
    census = semantic_census(
        e095=e095,
        language=language,
        options_by_global=options,
    )
    for key, value in census.items():
        require(encoding[key] == value, f"encoding census drift: {key}")

    direct = runner.build_integrated_model(
        e095=e095,
        e117=e117,
        language=language,
        options_by_global=options,
        add_redundant_cuts=False,
    )
    with_cuts = runner.build_integrated_model(
        e095=e095,
        e117=e117,
        language=language,
        options_by_global=options,
        add_redundant_cuts=True,
    )
    require(direct["model"].Validate() == "", "direct model invalid")
    require(with_cuts["model"].Validate() == "", "cut model invalid")
    require(direct["encoding_audit"]["redundant_cut_count"] == 0, "direct cut leakage")
    require(with_cuts["encoding_audit"]["redundant_cut_count"] == 587, "cut import drift")
    geometry_replay = known_geometry_replay(
        e095=e095,
        e117=e117,
        language=language,
        options_by_global=options,
    )

    payload = {
        "schema": "zmd_e120_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "EXACT_LOCAL_OPTION_ENCODING_REPLAYED_BOTH_SOLVER_ARMS_CENSORED",
        "artifact_records": artifact_records,
        "run_001_classification": "INPUT_IDENTITY_FAILURE_NO_SCIENTIFIC_EFFECT",
        "semantic_census": census,
        "known_geometry_replay": geometry_replay,
        "direct_model_valid": True,
        "redundant_cut_model_valid": True,
        "primary_status": primary["status"],
        "primary_branches": primary["branches"],
        "fallback_status": fallback["status"],
        "fallback_branches": fallback["branches"],
        "decision": result["decision"],
        "truth_boundary": (
            "The checker independently reconstructs the exact local-option coefficient "
            "census and all 47 known dead geometries. Both full searches remain UNKNOWN; "
            "no feasibility or infeasibility claim follows."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "model_variable_count": encoding["model_variable_count"],
                "model_constraint_count": encoding["model_constraint_count"],
                "dynamic_term_count": census["dynamic_term_count"],
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
