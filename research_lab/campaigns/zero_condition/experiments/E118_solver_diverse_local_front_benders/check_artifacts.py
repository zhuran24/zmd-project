#!/usr/bin/env python3
"""Independent replay of E118 imported/new local-front cut continuation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e118.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E118_solver_diverse_local_front_benders/run-001"
)
RESULT = RUN / "RESULT.json"
ITERATIONS = RUN / "CONTINUATION_ITERATIONS.json"
NEW_CUTS = RUN / "NEW_LOCAL_FRONT_BLOCKER_CUTS.json"
MERGED_CUTS = RUN / "MERGED_LOCAL_FRONT_BLOCKER_CUTS.json"
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
E117_CUTS = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E117_high_geometry_local_front_benders/run-001/LOCAL_FRONT_BLOCKER_CUTS.json"
)
E117_CHECK = E117_CUTS.with_name("ARTIFACT_CHECK.json")

EXPECTED = {
    RUNNER: "13f45e8ba3e8ff6c9a53e8c9b4e640508b7f650c956b13ae87d9c819391ff32f",
    RESULT: "4600f061f6fb4ca947f1108e81361e7643833889c686553c3138d56fccdac8a2",
    ITERATIONS: "0952a02be86887fc37c612e5043e4e92b8fbf1ee66733a34640ef48cfc1d0c24",
    NEW_CUTS: "ab306b1096090d9e20042373e11e116e1a24d84b8cac93d28bc894d2a4a36474",
    MERGED_CUTS: "93b4a05a9a19c2876cd9146f86ce6cbd11ee6a1923a6fed87f22b29ca5710375",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E115_RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
    E117_RUNNER: "ff51200bdec11733a27f3a82ffd63dc49a193e36fb1573f7c33d8a8b57d2f3f2",
    E117_CUTS: "6b671d1b97cb308fd109c75ced4d6521ffa2003deb386c0ad484406d1101e5fd",
    E117_CHECK: "c4529c108fe73ac6c871c3c5133d9592ad8d6091ceb543b58160cd553cd88d9d",
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


def distribution(values: list[Any]) -> dict[str, int]:
    output: dict[str, int] = {}
    for value in values:
        key = str(value)
        output[key] = output.get(key, 0) + 1
    return dict(sorted(output.items()))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E118 check: {OUTPUT}")
    require(
        subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip()
        == "research/main",
        "E118 checker must run on research/main",
    )
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E118 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E118 artifact identity drift: {path}")
        artifact_records[str(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load(RESULT)
    packet = load(ITERATIONS)
    new_packet = load(NEW_CUTS)
    merged_packet = load(MERGED_CUTS)
    imported_packet = load(E117_CUTS)
    require(
        result["verdict"]
        == "SOLVER_DIVERSE_LOCAL_FRONT_BENDERS_CENSORED_NO_IMPROVEMENT",
        "E118 verdict drift",
    )
    require(
        result["decision"] == "MEASURE_CUT_FAMILY_COVERAGE_AND_SATURATION",
        "E118 decision drift",
    )
    require(packet["iteration_count"] == 9, "iteration count drift")
    require(packet["master_terminal_status"] == "UNKNOWN", "terminal drift")
    require(packet["locally_live_geometry_found"] is False, "unexpected geometry")
    require(packet["best_new_empty_body_count"] == 6, "best empty count drift")
    require(new_packet["imported_cut_count"] == 504, "new packet import drift")
    require(new_packet["new_cut_count"] == 83, "new cut count drift")
    require(merged_packet["imported_cut_count"] == 504, "merged import drift")
    require(merged_packet["new_cut_count"] == 83, "merged new count drift")
    require(merged_packet["cut_count"] == 587, "merged count drift")

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e118_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e118_check_e100")
    e115 = source_module(E115_RUNNER, "zmd_e118_check_e115")
    e117 = source_module(E117_RUNNER, "zmd_e118_check_e117")
    e118 = source_module(RUNNER, "zmd_e118_check_runner")
    identity = e118.verify_identity()
    require(identity["runner_sha256"] == EXPECTED[RUNNER], "runner identity drift")

    language = e117.build_language(e095=e095, e100=e100, e115=e115)
    options = e117.precompute_options(e095=e095, language=language)
    master = e117.build_master(language)
    rows_by_global = {
        int(row["global_row_index"]): row for row in language["rows"]
    }
    fixed_solid = set(language["context"]["fixed_solid"])

    imported_records = [dict(record) for record in imported_packet["cuts"]]
    imported = e117.add_death_cuts(master=master, deaths=imported_records)
    require(len(imported) == 504, "import replay count drift")
    reconstructed_new: list[dict[str, Any]] = []
    empty_counts: list[int] = []
    optimal_count = 0
    for position, record in enumerate(packet["records"]):
        require(int(record["iteration"]) == position, "iteration order drift")
        status = str(record["terminal_status"])
        if status == "UNKNOWN":
            require(position == 8, "unexpected UNKNOWN position")
            require(record["primary"]["status"] == "UNKNOWN", "primary status drift")
            require(record["fallback"]["status"] == "UNKNOWN", "fallback status drift")
            require("selected_global_row_indices" not in record, "UNKNOWN leaked witness")
            continue
        require(status == "OPTIMAL", f"unexpected terminal status: {status}")
        require(
            record["terminal_profile"] == "one_worker_pseudo_cost",
            "positive geometry did not come from primary profile",
        )
        require(record["fallback"] is None, "fallback ran after primary positive")
        optimal_count += 1
        selected = set(map(int, record["selected_global_row_indices"]))
        require(len(selected) == 26, "selected body count drift")
        require(selected <= set(rows_by_global), "selected identity escaped language")
        observed_digest = e117.stable_digest(
            sorted(str(rows_by_global[value]["body_digest"]) for value in selected)
        )
        require(observed_digest == record["selected_body_digest"], "body digest drift")
        replay = e117.local_front_check(
            e095=e095,
            selected_globals=selected,
            options_by_global=options,
            rows_by_global=rows_by_global,
            fixed_solid=fixed_solid,
        )
        require(
            e117.stable_digest(replay) == e117.stable_digest(record["local_front"]),
            f"local-front replay drift at iteration {position}",
        )
        require(replay["locally_live"] is False, "locally-live geometry missed")
        empty_counts.append(int(replay["empty_body_count"]))
        require(
            int(record["cut_count_before"]) == len(master["cut_keys"]),
            "cut count before drift",
        )
        added = e117.add_death_cuts(master=master, deaths=replay["deaths"])
        require(len(added) == int(record["new_cut_count"]), "new cut count drift")
        require(
            int(record["cut_count_after"]) == len(master["cut_keys"]),
            "cut count after drift",
        )
        reconstructed_new.extend(
            {**cut, "source_iteration": position} for cut in added
        )

    require(optimal_count == 8, "optimal geometry count drift")
    require(len(reconstructed_new) == 83, "reconstructed new cut count drift")
    require(
        e117.stable_digest(reconstructed_new)
        == e117.stable_digest(new_packet["cuts"]),
        "new cut packet drift",
    )
    reconstructed_merged = [*imported_records, *reconstructed_new]
    require(
        e117.stable_digest(reconstructed_merged)
        == e117.stable_digest(merged_packet["cuts"]),
        "merged cut packet drift",
    )
    require(len(master["cut_keys"]) == 587, "replayed master cut count drift")
    require(master["model"].Validate() == "", "replayed master invalid")
    require(min(empty_counts) == 6, "replayed best empty count drift")

    payload = {
        "schema": "zmd_e118_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "EIGHT_NEW_GEOMETRIES_EIGHTY_THREE_NEW_CUTS_NO_BEST_IMPROVEMENT",
        "artifact_records": artifact_records,
        "imported_cut_count": 504,
        "optimal_geometry_count": optimal_count,
        "new_cut_count": len(reconstructed_new),
        "merged_cut_count": len(reconstructed_merged),
        "new_cut_core_size_distribution": distribution(
            [int(record["core_size"]) for record in reconstructed_new]
        ),
        "new_cut_subject_template_distribution": distribution(
            [str(record["subject_template"]) for record in reconstructed_new]
        ),
        "new_empty_body_count_distribution": distribution(empty_counts),
        "best_prior_empty_body_count": 6,
        "best_new_empty_body_count": min(empty_counts),
        "primary_terminal_status": packet["records"][-1]["primary"]["status"],
        "fallback_terminal_status": packet["records"][-1]["fallback"]["status"],
        "locally_live_geometry_found": False,
        "decision": "MEASURE_CUT_FAMILY_COVERAGE_AND_SATURATION",
        "truth_boundary": (
            "All eight new geometry deaths and 83 cuts replay. The final primary "
            "and fallback masters are UNKNOWN, and the best empty-body diagnostic "
            "remains six; no feasibility or exhaustion claim follows."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "classification": payload["classification"],
                "optimal_geometry_count": optimal_count,
                "new_cut_count": len(reconstructed_new),
                "merged_cut_count": len(reconstructed_merged),
                "best_new_empty_body_count": min(empty_counts),
                "primary_terminal_status": payload["primary_terminal_status"],
                "fallback_terminal_status": payload["fallback_terminal_status"],
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
