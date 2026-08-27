#!/usr/bin/env python3
"""Finish E056 by minimizing total mismatch on the exact mode-frontier face."""

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
OUT = ROOT / "research_lab/local/zero_condition/E056_causal_pair_mode_frontier/run-001"
POSITIVE_PATH = OUT / "POSITIVE_RESULT.json"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "RESUME_FAILURE.json"
BEST_WITNESS_PATH = OUT / "BEST_JOINT_WITNESS.json"
BEST_ASSIGNMENT_PATH = OUT / "BEST_ASSIGNMENT.json"
BEST_LAYOUT_PATH = OUT / "BEST_LAYOUT.json"
RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E056_causal_pair_mode_frontier/run_e056.py"
)
EXPECTED_RUNNER_SHA = "840a30a26e25c485e71b4891dbc68dc9e2c18d8608ffcc0404eda512d17d9e34"
EXPECTED_POSITIVE_SHA = "e18b93e374318077752a6b054e228a66c67aecfae14e152900613138f3fc1d66"
TOTAL_SECONDS = 180.0


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


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run() -> dict[str, Any]:
    if sha256_file(RUNNER) != EXPECTED_RUNNER_SHA:
        raise RuntimeError("E056 computational runner drift")
    if sha256_file(POSITIVE_PATH) != EXPECTED_POSITIVE_SHA:
        raise RuntimeError("E056 positive checkpoint drift")
    runner = import_module("zmd_e056_resume_runner", RUNNER)
    identity = runner.verify_identity()
    positive_payload = load_json(POSITIVE_PATH)
    positive = positive_payload["positive_solve"]
    if positive.get("status") != "OPTIMAL":
        raise RuntimeError("E056 positive checkpoint is not terminal")
    optimum_positive = int(positive["positive_commodity_count"])
    if optimum_positive != 18:
        raise RuntimeError("E056 resume expects the exact one-zero face")

    context = runner.reconstruct()
    built, positive_vars = runner.build_variant(
        context,
        fixed_state=None,
        objective_kind="total_mismatch",
        positive_target=optimum_positive,
    )
    total = context["helper"].solve_variant(
        built,
        positive_vars=positive_vars,
        random_seed=56201,
        objective_kind="total_mismatch",
        seconds=TOTAL_SECONDS,
    )

    materialized = None
    if total["status"] == "OPTIMAL":
        helper = context["helper"]
        old_paths = (
            helper.BEST_WITNESS_PATH,
            helper.BEST_ASSIGNMENT_PATH,
            helper.BEST_LAYOUT_PATH,
        )
        helper.BEST_WITNESS_PATH = BEST_WITNESS_PATH
        helper.BEST_ASSIGNMENT_PATH = BEST_ASSIGNMENT_PATH
        helper.BEST_LAYOUT_PATH = BEST_LAYOUT_PATH
        try:
            materialized = helper.materialize_and_replay(
                context["base"],
                context["expanded"],
                total,
                optimum_positive_count=optimum_positive,
                required_zero_commodities=[runner.TARGET_COMMODITY],
            )
        finally:
            (
                helper.BEST_WITNESS_PATH,
                helper.BEST_ASSIGNMENT_PATH,
                helper.BEST_LAYOUT_PATH,
            ) = old_paths

    if total["status"] == "OPTIMAL":
        total_value = int(total["total_mismatch"])
        if total_value < runner.EXPECTED_TOTAL:
            verdict = "MODE_FRONTIER_SECONDARY_TOTAL_IMPROVEMENT"
            decision = "RECOMPUTE_RESIDUAL_WITH_ONE_ZERO"
        else:
            verdict = "MODE_FRONTIER_LEX_SATURATED_AT_18_139"
            decision = "SELECT_NEXT_STRUCTURED_COMMODITY_CAUSE"
    elif total["status"] == "FEASIBLE":
        verdict = "MODE_FRONTIER_TOTAL_FEASIBLE_NONTERMINAL"
        decision = "RETAIN_WITNESS_AND_CONTINUE_TOTAL_SOLVE"
    else:
        verdict = "MODE_FRONTIER_TOTAL_NONTERMINAL"
        decision = "CONTINUE_OR_REFORMULATE_TOTAL_SOLVE"

    payload = {
        "schema": "zmd_zero_condition_e056_mode_frontier_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "positive_checkpoint_path": str(POSITIVE_PATH.relative_to(ROOT)),
        "positive_checkpoint_sha256": sha256_file(POSITIVE_PATH),
        "calibration": positive_payload["calibration"],
        "positive_solve": positive,
        "total_solve": context["helper"].compact(total),
        "materialized": materialized,
        "decision": decision,
        "truth_boundary": positive_payload["truth_boundary"],
        "ledger_effect": "none",
    }
    dump_exclusive(RESULT_PATH, payload)
    return payload


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E056 resume outputs")
    try:
        result = run()
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "positive": result["positive_solve"].get(
                        "positive_commodity_count"
                    ),
                    "total": result["total_solve"].get("total_mismatch"),
                    "status": result["total_solve"].get("status"),
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
            "schema": "zmd_zero_condition_e056_mode_frontier_resume_failure_v1",
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
