#!/usr/bin/env python3
"""Finish E054 from the frozen pair manifest after a materializer lookup bug."""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / "research_lab/local/zero_condition/E054_causal_fine_powder_operation_swaps/run-001"
RESULT = OUT / "RESULT.json"
FAILURE = OUT / "FAILURE.json"
MANIFEST = OUT / "PAIR_MANIFEST.json"
BEST_WITNESS = OUT / "BEST_JOINT_WITNESS.json"
BEST_ASSIGNMENT = OUT / "BEST_ASSIGNMENT.json"
BEST_LAYOUT = OUT / "BEST_LAYOUT.json"
E054 = ROOT / "research_lab/campaigns/zero_condition/experiments/E054_causal_fine_powder_operation_swaps/run_e054.py"
E053 = ROOT / "research_lab/campaigns/zero_condition/experiments/E053_merged_6x4_first_zero_joint/run_e053.py"
E051 = ROOT / "research_lab/campaigns/zero_condition/experiments/E051_positive_commodity_frontier/run_e051.py"
EXPECTED = {
    E054: "5b92368f3219b4e5f4d62c58e9a9f8cae4bc6f2d9f4d07932fdcfac4e60e5ad2",
    E053: "4d7e19c30471ffcb9abe68e7b5324bf9703881d6159aa91a46f79ba61ad605ef",
    E051: "e287c3c4323494b894792435b44fe2c23458345ca2f7409b06309170e9c4ca87",
    MANIFEST: "3ee0e70b6a9d6ac97c98b98fbb398991a56cc8b5abe5f0803cb1e466882f15c1",
    FAILURE: "ae539ada3301fc11407b2efc588ecac9d304b419bc251971ebbdc050fcbef76d",
}


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def mod(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def compact(result: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in result.items() if k not in {"joint_selection", "joint_port_specs", "selected_pattern_by_block"}}


def dump(path: Path, value: Any) -> None:
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def run() -> dict[str, Any]:
    checked = {}
    for path, expected in EXPECTED.items():
        actual = sha(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"identity drift {path}: {actual}")
    e054 = mod("e054_resume", E054)
    helper = mod("e053_resume", E053)
    e051 = mod("e051_resume", E051)
    base = e051.reconstruct_context()
    base["e051"] = e051
    expanded = e054.extend_relevant_modes(base, helper.expanded_context(base))
    state_by_location, _ = e054.current_state_maps(base, expanded)
    fixed = base["e041"].fixed_state_for_solution(
        solution=base["best_solution"], blocks=expanded["blocks"],
        selected_ids_by_block=expanded["selected_ids_by_block"], pools=base["inputs"]["pools"])
    built = helper.build_joint(base, expanded, fixed_state=fixed,
        warm_solution=base["best_solution"], warm_endpoint=base["best_endpoint"])
    with helper.heartbeat("e054_resume_calibration"):
        calibration = base["e041"].solve_mode_joint(built, time_limit_seconds=45.0, random_seed=54501)
    if calibration["status"] != "OPTIMAL" or int(calibration["objective"]) != 139:
        raise RuntimeError("resume calibration drift")

    pairs = [dict(row) for row in json.loads(MANIFEST.read_text())["pairs"]]
    feasible = [row for row in pairs if row["solve"]["status"] in {"OPTIMAL", "FEASIBLE"}]
    feasible.sort(key=lambda row: (int(row["solve"]["positive_commodity_count"]), int(row["solve"]["total_mismatch"]), str(row["pair_key"])))
    chosen = feasible[0]
    source = (str(chosen["source_location"][0]), int(chosen["source_location"][1]))
    capsule = (str(chosen["capsule_location"][0]), int(chosen["capsule_location"][1]))
    total_built, positives = e054.build_pair_model(helper, e051, base, expanded,
        state_by_location=state_by_location, source_location=source,
        capsule_location=capsule, objective="total_mismatch")
    total = helper.solve_variant(total_built, positive_vars=positives,
        random_seed=54502, objective_kind="total_mismatch", seconds=180.0)

    materialized = None
    if total["status"] == "OPTIMAL":
        old = (helper.BEST_WITNESS_PATH, helper.BEST_ASSIGNMENT_PATH, helper.BEST_LAYOUT_PATH)
        helper.BEST_WITNESS_PATH, helper.BEST_ASSIGNMENT_PATH, helper.BEST_LAYOUT_PATH = BEST_WITNESS, BEST_ASSIGNMENT, BEST_LAYOUT
        try:
            materialized = helper.materialize_and_replay(base, expanded, total,
                optimum_positive_count=int(total["positive_commodity_count"]),
                required_zero_commodities=[e054.TARGET_COMMODITY])
        finally:
            helper.BEST_WITNESS_PATH, helper.BEST_ASSIGNMENT_PATH, helper.BEST_LAYOUT_PATH = old

    if total["status"] == "OPTIMAL":
        verdict = "CAUSAL_OPERATION_SWAP_FIRST_ZERO_OPTIMAL"
        decision = "RECOMPUTE_RESIDUAL_WITH_POSITIVE_COUNT_PRIORITY"
    elif total["status"] == "FEASIBLE":
        verdict = "CAUSAL_OPERATION_SWAP_FIRST_ZERO_FEASIBLE_NONTERMINAL"
        decision = "RETAIN_WITNESS_AND_CONTINUE_TOTAL_SOLVE"
    else:
        verdict = "CAUSAL_OPERATION_SWAP_TOTAL_NONTERMINAL"
        decision = "RETAIN_FEASIBLE_PAIR_AND_CONTINUE_TOTAL_SOLVE"
    return {
        "schema": "zmd_zero_condition_e054_causal_operation_swaps_v1",
        "created_at_utc": now(), "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": {"checked_hashes": checked, "executor_sha256": sha(Path(__file__).resolve())},
        "resume_provenance": {"failure_path": str(FAILURE.relative_to(ROOT)), "failure_sha256": sha(FAILURE),
            "statement": "The preliminary failure occurred after all nine pair solves, during materializer helper lookup. Frozen pair results are reused; only the selected total solve and materialization are rerun."},
        "calibration": compact(calibration),
        "expanded_context": {"context_digest": expanded["context_digest"],
            "mode_enabled_destination_count": sum(bool(row["mode_enabled"]) for row in expanded["mode_summary"])},
        "pair_manifest_path": str(MANIFEST.relative_to(ROOT)), "pair_manifest_sha256": sha(MANIFEST),
        "pair_records": pairs, "feasible_pair_count": len(feasible), "selected_pair": chosen,
        "total_optimization": compact(total), "materialized": materialized,
        "decision": decision,
        "truth_boundary": "Nine capsule/right-edge-grinder operation swaps under E053 frozen geometry and expanded relevant-mode context only.",
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT.exists():
        raise FileExistsError(RESULT)
    try:
        result = run()
        dump(RESULT, result)
        total = result["total_optimization"]
        print(json.dumps({"verdict": result["verdict"], "feasible_pairs": result["feasible_pair_count"],
            "selected_pair": result["selected_pair"]["pair_key"], "total_status": total["status"],
            "total_mismatch": total.get("total_mismatch"), "positive_count": total.get("positive_commodity_count"),
            "zero_commodities": total.get("zero_mismatch_commodities"), "decision": result["decision"],
            "result_path": str(RESULT), "result_sha256": sha(RESULT)}, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"schema": "zmd_zero_condition_e054_resume_failure_v1", "created_at_utc": now(),
            "status": "EXECUTION_FAILURE", "error": type(exc).__name__, "detail": str(exc),
            "traceback": traceback.format_exc(), "ledger_effect": "none"}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
