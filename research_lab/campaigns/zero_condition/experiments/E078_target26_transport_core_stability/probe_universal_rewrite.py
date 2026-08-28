#!/usr/bin/env python3
"""E078 arm 4: refute universality of the fixed target-26 row rewrite."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from ortools.sat.python import cp_model

HERE = Path(__file__).resolve().parent
SUPPORT = HERE / "probe_support_neighbors.py"


def load_support() -> Any:
    spec = importlib.util.spec_from_file_location("zmd_e078_support_for_universal", SUPPORT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {SUPPORT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module.__name__] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    base = load_support()
    model = cp_model.CpModel()
    parent = base.e074.add_assignment_copy(
        model=model,
        prefix="e078_universal_parent",
        rows_by_destination=base.actual,
        operation_counts=base.e061.OPERATION_COUNTS,
        sink_components=base.context["sink_space"]["components"],
    )
    base.add_parent_face_constraints(model, parent)

    # Arm 3 independently proves these rows are fixed on the parent face. Pinning
    # them here keeps the rewrite comparison explicit rather than relying on that
    # sibling result during model construction.
    for destination in base.CORE_ROWS:
        model.Add(
            parent["x_vars"][
                (destination, base.reference_native_index[destination])
            ]
            == 1
        )

    zero_reference = {
        int(row["destination"]): dict(row["selected_option"])
        for row in base.witness["zero_assignment"]
        if int(row["destination"]) in base.CORE_ROWS
    }
    if sorted(zero_reference) != list(base.CORE_ROWS):
        raise RuntimeError("E078 zero-reference core rows missing")

    def exact_or(name: str, contributors: Sequence[Any]) -> Any:
        variable = model.NewBoolVar(name)
        if not contributors:
            model.Add(variable == 0)
            return variable
        for contributor in contributors:
            model.Add(variable >= contributor)
        model.Add(variable <= cp_model.LinearExpr.Sum(list(contributors)))
        return variable

    def xor(name: str, left: Any, right: Any) -> Any:
        variable = model.NewBoolVar(name)
        model.Add(variable >= left - right)
        model.Add(variable >= right - left)
        model.Add(variable <= left + right)
        model.Add(variable <= 2 - left - right)
        return variable

    components = sorted(
        {
            int(component)
            for rows in base.actual.values()
            for option in rows
            for part in option["signature"]
            for component in part
        }
        | {
            int(component)
            for option in zero_reference.values()
            for part in option["signature"]
            for component in part
        }
    )
    mismatches: dict[int, Any] = {}
    qiaoyu_failures: dict[int, Any] = {}
    for component in components:
        source_terms: list[Any] = []
        sink_terms: list[Any] = []
        qiaoyu_terms: list[Any] = []
        for destination, rows in base.actual.items():
            if destination in base.CORE_ROWS:
                continue
            for option_index, option in enumerate(rows):
                variable = parent["x_vars"][(destination, option_index)]
                if component in set(option["signature"][1]):
                    source_terms.append(variable)
                if component in set(option["signature"][0]):
                    sink_terms.append(variable)
                if component in set(option["signature"][2]):
                    qiaoyu_terms.append(variable)
        for option in zero_reference.values():
            signature = option["signature"]
            if component in {int(value) for value in signature[1]}:
                source_terms.append(1)
            if component in {int(value) for value in signature[0]}:
                sink_terms.append(1)
            if component in {int(value) for value in signature[2]}:
                qiaoyu_terms.append(1)

        source = exact_or(f"e078_rewrite_source_{component}", source_terms)
        sink = exact_or(f"e078_rewrite_sink_{component}", sink_terms)
        qiaoyu = exact_or(f"e078_rewrite_qiaoyu_{component}", qiaoyu_terms)
        mismatches[component] = xor(
            f"e078_rewrite_mismatch_{component}", source, sink
        )
        failure = model.NewBoolVar(f"e078_qiaoyu_failure_{component}")
        if component == base.e074.TARGET_QIAOYU_COMPONENT:
            model.Add(failure + qiaoyu == 1)
        else:
            model.Add(failure == qiaoyu)
        qiaoyu_failures[component] = failure

    if base.e074.TARGET_QIAOYU_COMPONENT not in components:
        raise RuntimeError("E078 target qiaoyu component absent from rewrite domain")
    model.Add(
        cp_model.LinearExpr.Sum(
            list(mismatches.values()) + list(qiaoyu_failures.values())
        )
        >= 1
    )
    run = base.solver(85001, 60.0)
    status = run.Solve(model)
    payload: dict[str, Any] = {
        "status": run.StatusName(status),
        "target": base.TARGET,
        "counterexample_found": status in (cp_model.OPTIMAL, cp_model.FEASIBLE),
        "branches": int(run.NumBranches()),
        "conflicts": int(run.NumConflicts()),
        "wall_time": float(run.WallTime()),
        "core_rows_local": list(base.CORE_ROWS),
        "stable_core_bodies": [
            {
                "destination_local": destination,
                "source_instance_id": str(
                    base.body_by_destination[destination]["source_instance_id"]
                ),
                "body_digest": str(
                    base.body_by_destination[destination]["body_digest"]
                ),
                "baseline_option": base.reference_by_destination[destination][
                    "selected_option"
                ],
                "zero_option": zero_reference[destination],
            }
            for destination in base.CORE_ROWS
        ],
    }
    if status == cp_model.INFEASIBLE:
        payload["verdict"] = "NO_PARENT_FACE_COUNTEREXAMPLE_TO_REFERENCE_REWRITE"
    elif status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        payload["verdict"] = "REFERENCE_REWRITE_COUNTEREXAMPLE_FOUND"
        payload["remaining_fine_mismatch_components"] = [
            component
            for component, variable in mismatches.items()
            if run.Value(variable)
        ]
        payload["remaining_qiaoyu_failure_components"] = [
            component
            for component, variable in qiaoyu_failures.items()
            if run.Value(variable)
        ]
    else:
        payload["verdict"] = "REFERENCE_REWRITE_NONTERMINAL"
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
