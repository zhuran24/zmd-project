#!/usr/bin/env python3
"""Independent check for E119 cut-family coverage and novelty metrics."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e119.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E119_local_front_cut_family_saturation_audit/run-001"
)
RESULT = RUN / "RESULT.json"
ATLAS = RUN / "CUT_FAMILY_ATLAS.json"
MATRIX = RUN / "GEOMETRY_REJECTION_MATRIX.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E095_y41_module_product_decomposition/run_e095.py"
E100_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E100_source_stable_reserved_x42_hybrid/run_e100.py"
E115_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E115_separator_template_state_full_consumer/run_e115.py"
E117_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E117_high_geometry_local_front_benders/run_e117.py"
E117_ITERATIONS = ROOT / "research_lab/local/zero_condition/E117_high_geometry_local_front_benders/run-001/BENDERS_ITERATIONS.json"
E117_CUTS = E117_ITERATIONS.with_name("LOCAL_FRONT_BLOCKER_CUTS.json")
E118_ITERATIONS = ROOT / "research_lab/local/zero_condition/E118_solver_diverse_local_front_benders/run-001/CONTINUATION_ITERATIONS.json"
E118_CUTS = E118_ITERATIONS.with_name("NEW_LOCAL_FRONT_BLOCKER_CUTS.json")

EXPECTED = {
    RUNNER: "6bdd42a01dac166d6e4958762fa3f148bc3b4e3df695001110651e9b6ba485d8",
    RESULT: "1e587146d34e1e42dfe5261ed5d179f772e594fb6b455154cf5666576b57b8e4",
    ATLAS: "8d3a5ebfedd6e169fe0ba5e88dd546fd8ea758fea81b674be0141e6e0668f8c0",
    MATRIX: "92dd864cb9c74ea1a74aa46f4cc49411e8999cde1e77e4aa103f1129a3bcb682",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E115_RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
    E117_RUNNER: "ff51200bdec11733a27f3a82ffd63dc49a193e36fb1573f7c33d8a8b57d2f3f2",
    E117_ITERATIONS: "ce2cd833601707fdda6bf16ef42bff891eae2076db600da0eb4e3f34a0cfaa29",
    E117_CUTS: "6b671d1b97cb308fd109c75ced4d6521ffa2003deb386c0ad484406d1101e5fd",
    E118_ITERATIONS: "0952a02be86887fc37c612e5043e4e92b8fbf1ee66733a34640ef48cfc1d0c24",
    E118_CUTS: "ab306b1096090d9e20042373e11e116e1a24d84b8cac93d28bc894d2a4a36474",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
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
    exec(compile(raw, f"<e119-check:{path}:{hashlib.sha256(raw).hexdigest()}>", "exec"), module.__dict__)
    return module


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def bbox(row: Mapping[str, Any]) -> tuple[int, int, int, int]:
    xs = [int(value[0]) for value in row["body"]]
    ys = [int(value[1]) for value in row["body"]]
    return min(xs), max(xs), min(ys), max(ys)


def band(row: Mapping[str, Any]) -> str:
    _x0, _x1, y0, y1 = bbox(row)
    lower = ((y0 + y1) // 10) * 5
    return f"y{lower:02d}_{lower + 4:02d}"


def normalized_body(row: Mapping[str, Any], x0: int, y0: int) -> list[list[int]]:
    return [
        [int(value[0]) - x0, int(value[1]) - y0]
        for value in sorted(row["body"])
    ]


def option_stencil(options: Sequence[Mapping[str, Any]], x0: int, y0: int) -> list[Any]:
    values = []
    for option in options:
        values.append(
            [
                int(option["need_in"]),
                int(option["need_out"]),
                sorted([[int(v[0]) - x0, int(v[1]) - y0] for v in option["input_cells"]]),
                sorted([[int(v[0]) - x0, int(v[1]) - y0] for v in option["output_cells"]]),
            ]
        )
    return sorted(values)


def structural_signature(
    cut: Mapping[str, Any],
    rows: Mapping[int, Mapping[str, Any]],
    options: Mapping[int, Sequence[Mapping[str, Any]]],
) -> str:
    subject_index = int(cut["subject_global_row_index"])
    subject = rows[subject_index]
    x0, _x1, y0, _y1 = bbox(subject)
    blockers = []
    for index in map(int, cut["core_global_row_indices"]):
        row = rows[index]
        blockers.append(
            [
                str(row["template"]),
                str(row["separator_group"]),
                normalized_body(row, x0, y0),
            ]
        )
    blockers.sort(key=lambda value: json.dumps(value, sort_keys=True))
    return digest(
        {
            "subject_template": str(subject["template"]),
            "subject_group": str(subject["separator_group"]),
            "subject_body": normalized_body(subject, x0, y0),
            "subject_option_stencil": option_stencil(options[subject_index], x0, y0),
            "blockers": blockers,
        }
    )


def cut_hits(cut: Mapping[str, Any], selected: set[int]) -> bool:
    needed = {int(cut["subject_global_row_index"])} | {
        int(value) for value in cut["core_global_row_indices"]
    }
    return needed <= selected


def geometries(packet: Mapping[str, Any], cohort: str) -> list[dict[str, Any]]:
    return [
        {
            "cohort": cohort,
            "iteration": int(record["iteration"]),
            "selected": set(map(int, record["selected_global_row_indices"])),
        }
        for record in packet["records"]
        if "selected_global_row_indices" in record
    ]


def ratio(n: int, d: int) -> float:
    require(d > 0, "zero denominator")
    return n / d


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E119 check: {OUTPUT}")
    require(
        subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
        == "research/main",
        "wrong branch",
    )
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing artifact {path}")
        actual = sha256(path)
        require(actual == expected, f"identity drift {path}")
        artifact_records[str(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    result = load(RESULT)
    atlas = load(ATLAS)
    matrix = load(MATRIX)
    require(result["verdict"] == "INCONCLUSIVE_MIXED_SATURATION", "verdict drift")
    require(
        result["decision"] == "DO_NOT_BLINDLY_CONTINUE_SELECT_ONE_MEASURED_DISCRIMINATOR",
        "decision drift",
    )

    source_module(OPERATION_PROFILES, "src.preprocess.operation_profiles", package="src.preprocess")
    e095 = source_module(E095_RUNNER, "e119_check_e095")
    e100 = source_module(E100_RUNNER, "e119_check_e100")
    e115 = source_module(E115_RUNNER, "e119_check_e115")
    e117 = source_module(E117_RUNNER, "e119_check_e117")
    language = e117.build_language(e095=e095, e100=e100, e115=e115)
    options = e117.precompute_options(e095=e095, language=language)
    rows = {int(row["global_row_index"]): row for row in language["rows"]}
    require(len(rows) == 1205, "universe drift")

    old = [dict(row) for row in load(E117_CUTS)["cuts"]]
    new = [dict(row) for row in load(E118_CUTS)["cuts"]]
    require(len(old) == 504 and len(new) == 83, "cut count drift")
    old_signatures = {structural_signature(row, rows, options) for row in old}
    new_signatures = [structural_signature(row, rows, options) for row in new]
    novel_cut_count = sum(value not in old_signatures for value in new_signatures)
    old_subjects = {int(row["subject_global_row_index"]) for row in old}
    new_subjects = {int(row["subject_global_row_index"]) for row in new}
    blockers = {
        int(value)
        for row in [*old, *new]
        for value in row["core_global_row_indices"]
    }
    geometry_rows = [
        *geometries(load(E117_ITERATIONS), "E117"),
        *geometries(load(E118_ITERATIONS), "E118"),
    ]
    require(len(geometry_rows) == 47, "geometry count drift")
    selected = {value for row in geometry_rows for value in row["selected"]}
    require(len(selected) == 328, "selected coverage drift")
    require(len(old_subjects | new_subjects) == 270, "subject coverage drift")
    require(len(blockers) == 302, "blocker coverage drift")
    require(novel_cut_count == 61, "structural novelty numerator drift")
    require(ratio(novel_cut_count, len(new)) == result["headline"]["E118_structural_novelty_ratio"], "novelty ratio drift")
    require(ratio(len(new_subjects - old_subjects), len(new_subjects)) == 0.28, "subject novelty drift")

    other_hits = 0
    for row in geometry_rows:
        prior: list[Mapping[str, Any]]
        if row["cohort"] == "E117":
            prior = [
                cut for cut in old
                if int(cut["source_iteration"]) < row["iteration"]
            ]
        else:
            prior = [*old, *[
                cut for cut in new
                if int(cut["source_iteration"]) < row["iteration"]
            ]]
            other_hits += int(any(
                int(cut["source_iteration"]) != row["iteration"]
                and cut_hits(cut, row["selected"])
                for cut in new
            ))
        require(not any(cut_hits(cut, row["selected"]) for cut in prior), "prior cut hit")
    require(other_hits == 0, "cross-iteration recurrence drift")
    require(matrix["all_prior_cut_hit_counts_zero"] is True, "matrix guard drift")
    require(matrix["E118_geometry_count_hit_by_other_E118_iteration"] == 0, "matrix recurrence drift")

    require(atlas["structural_signature_counts"]["E117_unique"] == 392, "old signature drift")
    require(atlas["structural_signature_counts"]["E118_unique"] == 79, "new signature drift")
    require(atlas["structural_signature_counts"]["merged_unique"] == 451, "merged signature drift")
    require(atlas["novelty"]["dominant_novel_family_share"] < 0.05, "family concentration drift")
    require(atlas["novelty"]["dominant_novel_family_share"] > 0.049, "family share lower drift")
    require(atlas["novelty"]["dominant_family_pre_E118_subject_coverage_among_repeat_samples"] == 1.0, "family coverage drift")

    payload = {
        "schema": "zmd_e119_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "HIGH_STRUCTURAL_NOVELTY_LOW_SUBJECT_NOVELTY_ZERO_CROSS_GEOMETRY_REUSE",
        "artifact_records": artifact_records,
        "candidate_universe_count": 1205,
        "geometry_count": 47,
        "merged_cut_count": 587,
        "selected_candidate_count": 328,
        "subject_candidate_count": 270,
        "blocker_candidate_count": 302,
        "E118_structurally_novel_cut_count": 61,
        "E118_structural_novelty_ratio": 61 / 83,
        "E118_exact_subject_novelty_ratio": 0.28,
        "E118_cross_iteration_geometry_hit_count": 0,
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "Metrics independently recomputed from pinned cut and geometry packets. "
            "Adaptive own/later-cut hits remain descriptive and no saturation claim follows."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "selected_candidate_count": 328,
                "subject_candidate_count": 270,
                "blocker_candidate_count": 302,
                "E118_structural_novelty_ratio": 61 / 83,
                "E118_exact_subject_novelty_ratio": 0.28,
                "cross_iteration_hit_count": 0,
                "decision": result["decision"],
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
