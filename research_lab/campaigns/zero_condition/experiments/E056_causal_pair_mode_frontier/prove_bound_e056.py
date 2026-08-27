#!/usr/bin/env python3
"""E056 bound proof: test whether the exact 18-positive face can beat total 139."""

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

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / "research_lab/local/zero_condition/E056_causal_pair_mode_frontier/run-001"
BOUND_PATH = OUT / "BOUND_RESULT.json"
FAILURE_PATH = OUT / "BOUND_FAILURE.json"
RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E056_causal_pair_mode_frontier/run_e056.py"
)
POSITIVE_PATH = OUT / "POSITIVE_RESULT.json"
NONTERMINAL_RESULT = OUT / "RESULT.json"
EXPECTED_RUNNER_SHA = "840a30a26e25c485e71b4891dbc68dc9e2c18d8608ffcc0404eda512d17d9e34"
EXPECTED_POSITIVE_SHA = "e18b93e374318077752a6b054e228a66c67aecfae14e152900613138f3fc1d66"
EXPECTED_NONTERMINAL_SHA = "f515b94165bed656f567de2f6be63759d98f4fb3e4628538810650962e74dab8"
TOTAL_UPPER_BOUND = 138
SOLVE_SECONDS = 210.0


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
    identities = {
        "runner": sha256_file(RUNNER),
        "positive": sha256_file(POSITIVE_PATH),
        "nonterminal_result": sha256_file(NONTERMINAL_RESULT),
    }
    expected = {
        "runner": EXPECTED_RUNNER_SHA,
        "positive": EXPECTED_POSITIVE_SHA,
        "nonterminal_result": EXPECTED_NONTERMINAL_SHA,
    }
    if identities != expected:
        raise RuntimeError(f"E056 bound identity drift: {identities} != {expected}")

    runner = import_module("zmd_e056_bound_runner", RUNNER)
    identity = runner.verify_identity()
    positive_payload = load_json(POSITIVE_PATH)
    positive = positive_payload["positive_solve"]
    if (
        positive.get("status") != "OPTIMAL"
        or int(positive["positive_commodity_count"]) != 18
    ):
        raise RuntimeError("E056 bound requires exact positive optimum 18")

    context = runner.reconstruct()
    built, positive_vars = runner.build_variant(
        context,
        fixed_state=None,
        objective_kind="total_mismatch",
        positive_target=18,
    )
    all_mismatch = [
        variable
        for commodity in built["compiled"]["commodities"]
        for variable in built["compiled"]["mismatch_vars"][commodity].values()
    ]
    total_expr = cp_model.LinearExpr.Sum(all_mismatch)
    built["binding_model"].model.Add(total_expr <= TOTAL_UPPER_BOUND)
    built["binding_model"].model.Minimize(0)
    solve = context["helper"].solve_variant(
        built,
        positive_vars=positive_vars,
        random_seed=56301,
        objective_kind="feasibility",
        seconds=SOLVE_SECONDS,
    )

    if solve["status"] == "INFEASIBLE":
        verdict = "MODE_FRONTIER_TOTAL_138_INFEASIBLE"
        decision = "ACCEPT_LEX_OPTIMUM_18_139_AND_SELECT_NEW_CAUSE"
    elif solve["status"] in {"OPTIMAL", "FEASIBLE"}:
        verdict = "MODE_FRONTIER_BELOW_139_FEASIBLE"
        decision = "MATERIALIZE_AND_MINIMIZE_NEW_TOTAL_STATE"
    else:
        verdict = "MODE_FRONTIER_BOUND_NONTERMINAL"
        decision = "PRESERVE_18_139_WITNESS_AND_DEFER_SECONDARY_BOUND"

    payload = {
        "schema": "zmd_zero_condition_e056_mode_frontier_bound_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "checked_artifacts": identities,
        "positive_optimum": 18,
        "known_feasible_total": 139,
        "tested_total_upper_bound": TOTAL_UPPER_BOUND,
        "solve": context["helper"].compact(solve),
        "decision": decision,
        "truth_boundary": (
            "Same E056 causal relation, fixed occupied geometry and non-6x4 "
            "choices, with admitted 6x4 modes/assignments free, positive count "
            "fixed at 18, and total mismatch constrained to at most 138."
        ),
        "ledger_effect": "none",
    }
    dump_exclusive(BOUND_PATH, payload)
    return payload


def main() -> int:
    if BOUND_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E056 bound outputs")
    try:
        result = run()
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "status": result["solve"].get("status"),
                    "total": result["solve"].get("total_mismatch"),
                    "decision": result["decision"],
                    "result_path": str(BOUND_PATH),
                    "result_sha256": sha256_file(BOUND_PATH),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e056_mode_frontier_bound_failure_v1",
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
