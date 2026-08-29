#!/usr/bin/env python3
"""Independent replay of E117 local-front containment cuts and iterations."""

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
RUNNER = HERE / "run_e117.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E117_high_geometry_local_front_benders/run-001"
)
RESULT = RUN / "RESULT.json"
ITERATIONS = RUN / "BENDERS_ITERATIONS.json"
CUTS = RUN / "LOCAL_FRONT_BLOCKER_CUTS.json"
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

EXPECTED = {
    RUNNER: "ff51200bdec11733a27f3a82ffd63dc49a193e36fb1573f7c33d8a8b57d2f3f2",
    RESULT: "1efe295bd816c0844cc550850c6c8d12c09b77a08b942bec9ca25aad8153054d",
    ITERATIONS: "ce2cd833601707fdda6bf16ef42bff891eae2076db600da0eb4e3f34a0cfaa29",
    CUTS: "6b671d1b97cb308fd109c75ced4d6521ffa2003deb386c0ad484406d1101e5fd",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E115_RUNNER: "a0edaedefb0c71ca5424f2bed27336d4a8e7519f8b0d60bff95d70667d619782",
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


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E117 check: {OUTPUT}")
    require(
        subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip()
        == "research/main",
        "E117 checker must run on research/main",
    )
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E117 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E117 artifact identity drift: {path}")
        artifact_records[str(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load(RESULT)
    packet = load(ITERATIONS)
    cuts_packet = load(CUTS)
    require(
        result["verdict"] == "HIGH_GEOMETRY_LOCAL_FRONT_BENDERS_CENSORED",
        "E117 verdict drift",
    )
    require(
        result["decision"] == "CONTINUE_FROM_PERSISTED_BLOCKER_CUTS",
        "E117 decision drift",
    )
    require(packet["iteration_count"] == 40, "E117 iteration count drift")
    require(packet["master_terminal_status"] == "UNKNOWN", "terminal drift")
    require(packet["locally_live_geometry_found"] is False, "unexpected geometry")
    require(cuts_packet["cut_count"] == cuts_packet["unique_cut_count"] == 504, "cut count drift")

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e117_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e117_check_e100")
    e115 = source_module(E115_RUNNER, "zmd_e117_check_e115")
    e117 = source_module(RUNNER, "zmd_e117_check_runner")
    identity = e117.verify_identity()
    require(identity["runner_sha256"] == EXPECTED[RUNNER], "runner self identity drift")

    language = e117.build_language(e095=e095, e100=e100, e115=e115)
    options = e117.precompute_options(e095=e095, language=language)
    master = e117.build_master(language)
    rows_by_global = {
        int(row["global_row_index"]): row for row in language["rows"]
    }
    fixed_solid = set(language["context"]["fixed_solid"])
    open_vectors = set(language["open_vectors"])

    reconstructed_cuts: list[dict[str, Any]] = []
    empty_counts: list[int] = []
    optimal_count = 0
    for position, record in enumerate(packet["records"]):
        require(int(record["iteration"]) == position, "iteration order drift")
        status = str(record["master_status"])
        if status == "UNKNOWN":
            require(position == len(packet["records"]) - 1, "nonterminal UNKNOWN")
            require("selected_global_row_indices" not in record, "UNKNOWN has witness")
            continue
        require(status == "OPTIMAL", f"unexpected master status: {status}")
        optimal_count += 1
        selected = set(map(int, record["selected_global_row_indices"]))
        require(len(selected) == 26, "selected body count drift")
        require(selected <= set(rows_by_global), "selected identity escaped language")
        require(
            tuple(map(int, record["separator_template_vector"])) in open_vectors,
            "separator vector escaped open language",
        )
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
        require(replay["locally_live"] is False, "locally-live iteration missed")
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
        reconstructed_cuts.extend(
            {**cut, "source_iteration": position} for cut in added
        )

    require(optimal_count == 39, "optimal iteration count drift")
    require(len(reconstructed_cuts) == 504, "reconstructed cut count drift")
    require(
        e117.stable_digest(reconstructed_cuts)
        == e117.stable_digest(cuts_packet["cuts"]),
        "reconstructed cut packet drift",
    )
    require(master["model"].Validate() == "", "replayed master invalid")

    size_distribution: dict[str, int] = {}
    template_distribution: dict[str, int] = {}
    for cut in reconstructed_cuts:
        size = str(int(cut["core_size"]))
        size_distribution[size] = size_distribution.get(size, 0) + 1
        template = str(cut["subject_template"])
        template_distribution[template] = template_distribution.get(template, 0) + 1
    payload = {
        "schema": "zmd_e117_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "FIVE_HUNDRED_FOUR_LOCAL_FRONT_CONTAINMENT_CUTS_REPLAYED",
        "artifact_records": artifact_records,
        "optimal_geometry_count": optimal_count,
        "terminal_master_status": "UNKNOWN",
        "locally_live_geometry_found": False,
        "cut_count": len(reconstructed_cuts),
        "cut_core_size_distribution": dict(sorted(size_distribution.items())),
        "cut_subject_template_distribution": dict(sorted(template_distribution.items())),
        "empty_body_count_min": min(empty_counts),
        "empty_body_count_max": max(empty_counts),
        "decision": "CONTINUE_FROM_PERSISTED_BLOCKER_CUTS_WITH_SOLVER_DIVERSITY",
        "truth_boundary": (
            "All 504 cuts are independently reconstructed as inclusion-minimal "
            "selected-body containment sets that keep one subject locally front-dead. "
            "The final five-second master UNKNOWN is censored and proves no closure."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "classification": payload["classification"],
                "optimal_geometry_count": optimal_count,
                "cut_count": len(reconstructed_cuts),
                "empty_body_count_min": min(empty_counts),
                "terminal_master_status": "UNKNOWN",
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
