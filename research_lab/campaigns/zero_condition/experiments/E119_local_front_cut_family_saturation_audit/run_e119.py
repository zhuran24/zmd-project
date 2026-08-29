#!/usr/bin/env python3
"""E119: no-solver coverage and saturation audit of E117/E118 cuts."""

from __future__ import annotations

from collections import Counter
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import types
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E119_local_front_cut_family_saturation_audit/run-001"
)
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
E117_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E117_high_geometry_local_front_benders/run-001"
)
E117_ITERATIONS = E117_RUN / "BENDERS_ITERATIONS.json"
E117_CUTS = E117_RUN / "LOCAL_FRONT_BLOCKER_CUTS.json"
E117_CHECK = E117_RUN / "ARTIFACT_CHECK.json"
E118_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E118_solver_diverse_local_front_benders/run_e118.py"
)
E118_DURABLE = E118_RUNNER.with_name("RESULT.txt")
E118_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E118_solver_diverse_local_front_benders/run-001"
)
E118_RESULT = E118_RUN / "RESULT.json"
E118_ITERATIONS = E118_RUN / "CONTINUATION_ITERATIONS.json"
E118_NEW_CUTS = E118_RUN / "NEW_LOCAL_FRONT_BLOCKER_CUTS.json"
E118_MERGED_CUTS = E118_RUN / "MERGED_LOCAL_FRONT_BLOCKER_CUTS.json"
E118_CHECK = E118_RUN / "ARTIFACT_CHECK.json"

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E115_RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
    E117_RUNNER: "ff51200bdec11733a27f3a82ffd63dc49a193e36fb1573f7c33d8a8b57d2f3f2",
    E117_ITERATIONS: "ce2cd833601707fdda6bf16ef42bff891eae2076db600da0eb4e3f34a0cfaa29",
    E117_CUTS: "6b671d1b97cb308fd109c75ced4d6521ffa2003deb386c0ad484406d1101e5fd",
    E117_CHECK: "c4529c108fe73ac6c871c3c5133d9592ad8d6091ceb543b58160cd553cd88d9d",
    E118_RUNNER: "13f45e8ba3e8ff6c9a53e8c9b4e640508b7f650c956b13ae87d9c819391ff32f",
    E118_DURABLE: "55e56c60f949a54ff5e1065db3d734e2b347102e36d855c875ae4fb6eed194cd",
    E118_RESULT: "4600f061f6fb4ca947f1108e81361e7643833889c686553c3138d56fccdac8a2",
    E118_ITERATIONS: "0952a02be86887fc37c612e5043e4e92b8fbf1ee66733a34640ef48cfc1d0c24",
    E118_NEW_CUTS: "ab306b1096090d9e20042373e11e116e1a24d84b8cac93d28bc894d2a4a36474",
    E118_MERGED_CUTS: "93b4a05a9a19c2876cd9146f86ce6cbd11ee6a1923a6fed87f22b29ca5710375",
    E118_CHECK: "891d8ec1b41ac1ce178fb8345e748f51833d0279a8681993638e9db6fcbc813b",
}

EXPECTED_UNIVERSE = 1205
EXPECTED_E117_GEOMETRIES = 39
EXPECTED_E118_GEOMETRIES = 8
EXPECTED_E117_CUTS = 504
EXPECTED_E118_CUTS = 83
EXPECTED_MERGED_CUTS = 587


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
        raise RuntimeError("E119 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E119 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E119 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }
    result = load_json(E118_RESULT)
    if result.get("decision") != "MEASURE_CUT_FAMILY_COVERAGE_AND_SATURATION":
        raise RuntimeError("E119 E118 decision drift")
    check = load_json(E118_CHECK)
    if check.get("status") != "PASS" or check.get("classification") != (
        "EIGHT_NEW_GEOMETRIES_EIGHTY_THREE_NEW_CUTS_NO_BEST_IMPROVEMENT"
    ):
        raise RuntimeError("E119 E118 check drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def bbox(row: Mapping[str, Any]) -> tuple[int, int, int, int]:
    xs = [int(value[0]) for value in row["body"]]
    ys = [int(value[1]) for value in row["body"]]
    return min(xs), max(xs), min(ys), max(ys)


def spatial_band(row: Mapping[str, Any]) -> str:
    _min_x, _max_x, min_y, max_y = bbox(row)
    centre2 = min_y + max_y
    lower = (centre2 // 10) * 5
    return f"y{lower:02d}_{lower + 4:02d}"


def subject_address(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(row["template"]),
        str(row["separator_group"]),
        spatial_band(row),
    )


def normalized_body(
    row: Mapping[str, Any], *, origin_x: int, origin_y: int
) -> tuple[tuple[int, int], ...]:
    return tuple(
        sorted(
            (int(value[0]) - origin_x, int(value[1]) - origin_y)
            for value in row["body"]
        )
    )


def option_stencil(
    options: Sequence[Mapping[str, Any]], *, origin_x: int, origin_y: int
) -> tuple[Any, ...]:
    return tuple(
        sorted(
            (
                int(option["need_in"]),
                int(option["need_out"]),
                tuple(
                    sorted(
                        (int(value[0]) - origin_x, int(value[1]) - origin_y)
                        for value in option["input_cells"]
                    )
                ),
                tuple(
                    sorted(
                        (int(value[0]) - origin_x, int(value[1]) - origin_y)
                        for value in option["output_cells"]
                    )
                ),
            )
            for option in options
        )
    )


def structural_payload(
    cut: Mapping[str, Any],
    *,
    rows: Mapping[int, Mapping[str, Any]],
    options: Mapping[int, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    subject_index = int(cut["subject_global_row_index"])
    subject = rows[subject_index]
    min_x, _max_x, min_y, _max_y = bbox(subject)
    blockers = []
    for blocker_index in map(int, cut["core_global_row_indices"]):
        blocker = rows[blocker_index]
        blockers.append(
            {
                "template": str(blocker["template"]),
                "group": str(blocker["separator_group"]),
                "relative_body": normalized_body(
                    blocker, origin_x=min_x, origin_y=min_y
                ),
            }
        )
    blockers.sort(
        key=lambda item: (
            item["template"],
            item["group"],
            item["relative_body"],
        )
    )
    return {
        "subject_template": str(subject["template"]),
        "subject_group": str(subject["separator_group"]),
        "subject_body": normalized_body(subject, origin_x=min_x, origin_y=min_y),
        "subject_option_stencil": option_stencil(
            options[subject_index], origin_x=min_x, origin_y=min_y
        ),
        "blockers": blockers,
    }


def coarse_family(
    cut: Mapping[str, Any], *, rows: Mapping[int, Mapping[str, Any]]
) -> tuple[Any, ...]:
    subject = rows[int(cut["subject_global_row_index"])]
    blocker_multiset = tuple(
        sorted(
            (
                str(rows[int(index)]["template"]),
                str(rows[int(index)]["separator_group"]),
            )
            for index in cut["core_global_row_indices"]
        )
    )
    return (
        str(subject["template"]),
        str(subject["separator_group"]),
        spatial_band(subject),
        int(cut["core_size"]),
        blocker_multiset,
    )


def geometry_records(packet: Mapping[str, Any], cohort: str) -> list[dict[str, Any]]:
    output = []
    for record in packet["records"]:
        if "selected_global_row_indices" not in record:
            continue
        output.append(
            {
                "cohort": cohort,
                "iteration": int(record["iteration"]),
                "selected": set(map(int, record["selected_global_row_indices"])),
                "empty_body_count": int(record["local_front"]["empty_body_count"]),
                "separator_template_vector": tuple(
                    map(int, record["separator_template_vector"])
                ),
            }
        )
    return output


def cut_hits(cut: Mapping[str, Any], selected: set[int]) -> bool:
    required = {
        int(cut["subject_global_row_index"]),
        *map(int, cut["core_global_row_indices"]),
    }
    return required <= selected


def counts_by_address(
    indices: Iterable[int], rows: Mapping[int, Mapping[str, Any]]
) -> dict[str, int]:
    counter = Counter("/".join(subject_address(rows[int(index)])) for index in indices)
    return dict(sorted(counter.items()))


def safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def run(*, run_dir: Path) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E119 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e119_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e119_source_e100")
    e115 = source_module(E115_RUNNER, "zmd_e119_source_e115")
    e117 = source_module(E117_RUNNER, "zmd_e119_source_e117")
    language = e117.build_language(e095=e095, e100=e100, e115=e115)
    options = e117.precompute_options(e095=e095, language=language)
    rows = {int(row["global_row_index"]): row for row in language["rows"]}
    if len(rows) != EXPECTED_UNIVERSE:
        raise RuntimeError("E119 universe count drift")

    e117_cuts = [dict(record) for record in load_json(E117_CUTS)["cuts"]]
    e118_cuts = [dict(record) for record in load_json(E118_NEW_CUTS)["cuts"]]
    merged_cuts = [dict(record) for record in load_json(E118_MERGED_CUTS)["cuts"]]
    if (
        len(e117_cuts) != EXPECTED_E117_CUTS
        or len(e118_cuts) != EXPECTED_E118_CUTS
        or len(merged_cuts) != EXPECTED_MERGED_CUTS
    ):
        raise RuntimeError("E119 cut-count drift")
    if merged_cuts != [*e117_cuts, *e118_cuts]:
        raise RuntimeError("E119 merged cut ordering drift")

    enriched: list[dict[str, Any]] = []
    for cohort, cuts in (("E117", e117_cuts), ("E118", e118_cuts)):
        for cut in cuts:
            payload = structural_payload(cut, rows=rows, options=options)
            family = coarse_family(cut, rows=rows)
            subject = rows[int(cut["subject_global_row_index"])]
            enriched.append(
                {
                    "cohort": cohort,
                    "source_iteration": int(cut["source_iteration"]),
                    "cut_key": str(cut["cut_key"]),
                    "subject_global_row_index": int(
                        cut["subject_global_row_index"]
                    ),
                    "subject_address": list(subject_address(subject)),
                    "subject_template": str(subject["template"]),
                    "subject_group": str(subject["separator_group"]),
                    "subject_spatial_band": spatial_band(subject),
                    "core_size": int(cut["core_size"]),
                    "core_global_row_indices": list(
                        map(int, cut["core_global_row_indices"])
                    ),
                    "structural_signature": stable_digest(payload),
                    "coarse_family": json_safe(family),
                    "coarse_family_digest": stable_digest(family),
                }
            )

    e117_structures = {
        row["structural_signature"] for row in enriched if row["cohort"] == "E117"
    }
    e118_rows = [row for row in enriched if row["cohort"] == "E118"]
    e118_structurally_novel = [
        row for row in e118_rows if row["structural_signature"] not in e117_structures
    ]
    e117_subjects = {
        int(row["subject_global_row_index"])
        for row in enriched
        if row["cohort"] == "E117"
    }
    e118_subjects = {
        int(row["subject_global_row_index"])
        for row in enriched
        if row["cohort"] == "E118"
    }
    e117_blockers = {
        int(value)
        for row in enriched
        if row["cohort"] == "E117"
        for value in row["core_global_row_indices"]
    }
    e118_blockers = {
        int(value)
        for row in enriched
        if row["cohort"] == "E118"
        for value in row["core_global_row_indices"]
    }

    geometries = [
        *geometry_records(load_json(E117_ITERATIONS), "E117"),
        *geometry_records(load_json(E118_ITERATIONS), "E118"),
    ]
    if len(geometries) != EXPECTED_E117_GEOMETRIES + EXPECTED_E118_GEOMETRIES:
        raise RuntimeError("E119 geometry count drift")
    selection_counts: Counter[int] = Counter(
        value for geometry in geometries for value in geometry["selected"]
    )
    e117_selection_counts: Counter[int] = Counter(
        value
        for geometry in geometries
        if geometry["cohort"] == "E117"
        for value in geometry["selected"]
    )

    rejection_records = []
    e118_other_iteration_hit_count = 0
    for geometry in geometries:
        cohort = geometry["cohort"]
        iteration = int(geometry["iteration"])
        selected = geometry["selected"]
        old_hits = [cut for cut in e117_cuts if cut_hits(cut, selected)]
        new_hits = [cut for cut in e118_cuts if cut_hits(cut, selected)]
        if cohort == "E117":
            prior_hits = [
                cut
                for cut in e117_cuts
                if int(cut["source_iteration"]) < iteration and cut_hits(cut, selected)
            ]
            other_same = [
                cut
                for cut in e117_cuts
                if int(cut["source_iteration"]) != iteration
                and cut_hits(cut, selected)
            ]
        else:
            prior_hits = [
                *old_hits,
                *[
                    cut
                    for cut in e118_cuts
                    if int(cut["source_iteration"]) < iteration
                    and cut_hits(cut, selected)
                ],
            ]
            other_same = [
                cut
                for cut in e118_cuts
                if int(cut["source_iteration"]) != iteration
                and cut_hits(cut, selected)
            ]
            e118_other_iteration_hit_count += int(bool(other_same))
        if prior_hits:
            raise RuntimeError(
                f"E119 adaptive generation violated prior cuts: {cohort}/{iteration}"
            )
        own_hits = [
            cut
            for cut in (e117_cuts if cohort == "E117" else e118_cuts)
            if int(cut["source_iteration"]) == iteration and cut_hits(cut, selected)
        ]
        rejection_records.append(
            {
                "cohort": cohort,
                "iteration": iteration,
                "empty_body_count": geometry["empty_body_count"],
                "separator_template_vector": list(
                    geometry["separator_template_vector"]
                ),
                "e117_final_hit_count": len(old_hits),
                "e118_final_hit_count": len(new_hits),
                "own_iteration_hit_count": len(own_hits),
                "other_same_cohort_hit_count": len(other_same),
                "prior_cut_hit_count": 0,
            }
        )

    per_iteration_novelty = []
    seen_structures: set[str] = set()
    for cohort, cuts in (("E117", e117_cuts), ("E118", e118_cuts)):
        if cohort == "E118":
            seen_structures = set(e117_structures)
        for iteration in sorted({int(cut["source_iteration"]) for cut in cuts}):
            rows_at_iteration = [
                row
                for row in enriched
                if row["cohort"] == cohort
                and int(row["source_iteration"]) == iteration
            ]
            new_signatures = {
                row["structural_signature"]
                for row in rows_at_iteration
                if row["structural_signature"] not in seen_structures
            }
            signatures = {row["structural_signature"] for row in rows_at_iteration}
            per_iteration_novelty.append(
                {
                    "cohort": cohort,
                    "iteration": iteration,
                    "cut_count": len(rows_at_iteration),
                    "structural_signature_count": len(signatures),
                    "new_structural_signature_count": len(new_signatures),
                    "new_structural_signature_ratio": safe_ratio(
                        len(new_signatures), len(rows_at_iteration)
                    ),
                }
            )
            seen_structures.update(signatures)

    novel_family_counts = Counter(
        str(row["coarse_family_digest"]) for row in e118_structurally_novel
    )
    dominant_novel_family_digest = (
        novel_family_counts.most_common(1)[0][0] if novel_family_counts else None
    )
    dominant_novel_family_count = (
        novel_family_counts[dominant_novel_family_digest]
        if dominant_novel_family_digest is not None
        else 0
    )
    dominant_rows = [
        row
        for row in e118_structurally_novel
        if row["coarse_family_digest"] == dominant_novel_family_digest
    ]
    dominant_address = (
        tuple(dominant_rows[0]["subject_address"]) if dominant_rows else None
    )
    repeatedly_sampled_pre = {
        index
        for index, count in e117_selection_counts.items()
        if count >= 2
        and dominant_address is not None
        and subject_address(rows[index]) == dominant_address
    }
    dominant_pre_subject_coverage = safe_ratio(
        len(repeatedly_sampled_pre & e117_subjects), len(repeatedly_sampled_pre)
    )

    structural_novelty_ratio = safe_ratio(
        len(e118_structurally_novel), len(e118_rows)
    )
    exact_subject_novelty_ratio = safe_ratio(
        len(e118_subjects - e117_subjects), len(e118_subjects)
    )
    cross_iteration_hit_rate = safe_ratio(
        e118_other_iteration_hit_count, EXPECTED_E118_GEOMETRIES
    )
    dominant_novel_family_share = safe_ratio(
        dominant_novel_family_count, len(e118_structurally_novel)
    )
    all_e118_family_counts = Counter(
        str(row["coarse_family_digest"]) for row in e118_rows
    )
    largest_e118_family_share = safe_ratio(
        all_e118_family_counts.most_common(1)[0][1], len(e118_rows)
    )

    narrow = (
        structural_novelty_ratio is not None
        and structural_novelty_ratio >= 0.50
        and dominant_novel_family_share is not None
        and dominant_novel_family_share >= 0.50
        and dominant_pre_subject_coverage is not None
        and dominant_pre_subject_coverage < 0.50
    )
    plateau = (
        structural_novelty_ratio is not None
        and structural_novelty_ratio <= 0.25
        and exact_subject_novelty_ratio is not None
        and exact_subject_novelty_ratio <= 0.25
        and cross_iteration_hit_rate is not None
        and cross_iteration_hit_rate >= 0.50
        and largest_e118_family_share is not None
        and largest_e118_family_share < 0.50
    )
    if narrow:
        classification = "NARROW_UNSATURATED_FAMILY"
        decision = "TARGET_DOMINANT_WEAK_FAMILY_IN_ONE_BOUNDED_CONTINUATION"
    elif plateau:
        classification = "BROAD_REPETITIVE_PLATEAU"
        decision = "CHANGE_GEOMETRY_PROPOSER_REPRESENTATION"
    else:
        classification = "INCONCLUSIVE_MIXED_SATURATION"
        decision = "DO_NOT_BLINDLY_CONTINUE_SELECT_ONE_MEASURED_DISCRIMINATOR"

    selected_candidates = set(selection_counts)
    all_subjects = e117_subjects | e118_subjects
    all_blockers = e117_blockers | e118_blockers
    repeatedly_selected = {
        index for index, count in selection_counts.items() if count >= 2
    }
    family_atlas = {
        "schema": "zmd_e119_cut_family_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "candidate_universe_count": len(rows),
        "selected_candidate_count": len(selected_candidates),
        "subject_candidate_count": len(all_subjects),
        "blocker_candidate_count": len(all_blockers),
        "selected_but_never_subject_count": len(selected_candidates - all_subjects),
        "repeatedly_selected_but_never_subject_count": len(
            repeatedly_selected - all_subjects
        ),
        "never_selected_candidate_count": len(set(rows) - selected_candidates),
        "never_blocker_candidate_count": len(set(rows) - all_blockers),
        "coverage": {
            "selected_by_address": counts_by_address(selected_candidates, rows),
            "subjects_by_address": counts_by_address(all_subjects, rows),
            "blockers_by_address": counts_by_address(all_blockers, rows),
            "universe_by_address": counts_by_address(rows, rows),
        },
        "cut_counts": {
            "E117": len(e117_cuts),
            "E118": len(e118_cuts),
            "merged": len(merged_cuts),
        },
        "structural_signature_counts": {
            "E117_unique": len(e117_structures),
            "E118_unique": len(
                {row["structural_signature"] for row in e118_rows}
            ),
            "E118_novel_cut_count": len(e118_structurally_novel),
            "E118_novel_signature_count": len(
                {row["structural_signature"] for row in e118_structurally_novel}
            ),
            "merged_unique": len(
                {row["structural_signature"] for row in enriched}
            ),
        },
        "novelty": {
            "E118_structural_novelty_ratio": structural_novelty_ratio,
            "E118_exact_subject_novelty_ratio": exact_subject_novelty_ratio,
            "E118_other_iteration_geometry_hit_rate": cross_iteration_hit_rate,
            "dominant_novel_family_share": dominant_novel_family_share,
            "dominant_novel_family_digest": dominant_novel_family_digest,
            "dominant_novel_subject_address": (
                list(dominant_address) if dominant_address is not None else None
            ),
            "dominant_family_pre_E118_subject_coverage_among_repeat_samples": (
                dominant_pre_subject_coverage
            ),
            "largest_E118_family_share": largest_e118_family_share,
        },
        "per_iteration_novelty": per_iteration_novelty,
        "cuts": enriched,
        "adaptive_guard": (
            "All prior-cut hit counts are zero. Own/later hits are in-sample "
            "explanations and must not be read as predictive accuracy."
        ),
    }
    atlas_path = run_dir / "CUT_FAMILY_ATLAS.json"
    dump_exclusive(atlas_path, family_atlas)

    rejection_packet = {
        "schema": "zmd_e119_geometry_rejection_matrix_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "geometry_count": len(rejection_records),
        "records": rejection_records,
        "all_prior_cut_hit_counts_zero": all(
            int(row["prior_cut_hit_count"]) == 0 for row in rejection_records
        ),
        "E118_geometry_count_hit_by_other_E118_iteration": (
            e118_other_iteration_hit_count
        ),
        "truth_boundary": (
            "Retrospective hits from own/later cuts are adaptive in-sample "
            "explanations, not out-of-sample rejection estimates."
        ),
    }
    rejection_path = run_dir / "GEOMETRY_REJECTION_MATRIX.json"
    dump_exclusive(rejection_path, rejection_packet)

    verdict = classification
    result = {
        "schema": "zmd_e119_local_front_cut_family_saturation_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "narrow_structural_novelty_min": 0.50,
            "narrow_dominant_novel_family_share_min": 0.50,
            "narrow_prior_subject_coverage_max_exclusive": 0.50,
            "plateau_structural_novelty_max": 0.25,
            "plateau_exact_subject_novelty_max": 0.25,
            "plateau_cross_iteration_hit_rate_min": 0.50,
            "plateau_largest_family_share_max_exclusive": 0.50,
            "spatial_band_height": 5,
            "no_solver": True,
        },
        "headline": {
            "candidate_universe_count": len(rows),
            "geometry_count": len(geometries),
            "merged_cut_count": len(merged_cuts),
            "selected_candidate_count": len(selected_candidates),
            "subject_candidate_count": len(all_subjects),
            "blocker_candidate_count": len(all_blockers),
            "E118_structural_novelty_ratio": structural_novelty_ratio,
            "E118_exact_subject_novelty_ratio": exact_subject_novelty_ratio,
            "E118_other_iteration_geometry_hit_rate": cross_iteration_hit_rate,
            "dominant_novel_family_share": dominant_novel_family_share,
            "dominant_family_pre_subject_coverage": dominant_pre_subject_coverage,
            "largest_E118_family_share": largest_e118_family_share,
            "best_empty_body_count_E117": 6,
            "best_empty_body_count_E118": 6,
        },
        "atlas": {
            "path": display(atlas_path),
            "sha256": sha256_file(atlas_path),
        },
        "rejection_matrix": {
            "path": display(rejection_path),
            "sha256": sha256_file(rejection_path),
            "all_prior_cut_hit_counts_zero": True,
        },
        "adaptive_data_caveat": (
            "The 47 geometries were generated under previous cuts. Coverage and "
            "recurrence are descriptive. No absence or feasibility conclusion follows."
        ),
        "truth_boundary": (
            "No-solver audit of a sound cut store. Classification directs research "
            "budget only; it proves neither saturation nor master feasibility."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = __import__("argparse").ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(run_dir=run_dir)
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "headline": result["headline"],
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
            "schema": "zmd_e119_execution_failure_v1",
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
