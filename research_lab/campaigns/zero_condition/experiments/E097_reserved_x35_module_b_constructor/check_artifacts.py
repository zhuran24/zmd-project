#!/usr/bin/env python3
"""Branch-aware independent artifact replay for E097."""

from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E097_reserved_x35_module_b_constructor/run-001"
)
RUNNER = Path(__file__).with_name("run_e097.py")
RESULT = RUN / "RESULT.json"
MODULE_B = RUN / "MODULE_B_RESULT.json"
AUDIT = RUN / "RESERVED_COLUMN_AUDIT.json"
COMBINED = RUN / "COMBINED_WITNESS.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
E095_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E095_y41_module_product_decomposition/run_e095.py"
)
E095_MODULE_A = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001/MODULE_A_RESULT.json"
)
E096_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E096_module_b_interface_thickness/run-001/RESULT.json"
)

EXPECTED = {
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
    E096_RESULT: "b16062ce71a9bf40943bd9adcb788249b68099906ab4bb360d48800230dc10f2",
}
RESERVED_X = 35
SEAM_Y = 41


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cell(value: Any) -> tuple[int, int]:
    if isinstance(value, Mapping):
        return int(value["x"]), int(value["y"])
    return int(value[0]), int(value[1])


def in_grid(value: tuple[int, int]) -> bool:
    return 0 <= value[0] < 70 and 0 <= value[1] < 70


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def import_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def semantic_replay(
    e095: ModuleType,
    selected: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    context = e095.build_context()
    require(len(selected) == 219, "combined selected count drift")
    fixed_solid = set(context["fixed_solid"])
    occupied = set(fixed_solid)
    body_owner: dict[tuple[int, int], str] = {
        value: "fixed" for value in fixed_solid
    }
    b_count = 0
    side_counts: Counter[str] = Counter()
    for index, row in enumerate(selected):
        body = {cell(value) for value in row["body"]}
        require(bool(body), f"empty selected body: {index}")
        for value in body:
            require(value not in body_owner, f"body overlap at {value}")
            body_owner[value] = f"manufacturing::{index}"
        occupied |= body
        if str(row["module"]) == "B":
            b_count += 1
            require(
                all(x != RESERVED_X for x, _y in body),
                f"module-B body occupies reserved x=35: {index}",
            )
            side = str(row.get("side", ""))
            require(side in {"low", "high"}, f"invalid B side: {side}")
            if side == "low":
                require(max(x for x, _y in body) <= 34, "low body crosses cut")
            else:
                require(min(x for x, _y in body) >= 36, "high body crosses cut")
            side_counts[side] += 1
    require(b_count == 91, "combined module-B count drift")

    operation_counts = Counter(str(row["operation"]) for row in selected)
    require(
        operation_counts == context["operation_counts"],
        "combined named-operation multiset drift",
    )
    class_counts = Counter(tuple(row["class_key"]) for row in selected)
    require(class_counts == context["class_counts"], "combined class multiset drift")

    unpowered: list[int] = []
    front_failures: list[int] = []
    for index, row in enumerate(selected):
        body = {cell(value) for value in row["body"]}
        if not body & set(context["fixed_coverage"]):
            unpowered.append(index)
        template = str(row["template"])
        pose = context["pools"][template][int(row["pose_index"])]
        free_inputs = [
            value
            for raw in pose["input_port_cells"]
            for value in [cell(raw)]
            if in_grid(value) and value not in occupied
        ]
        free_outputs = [
            value
            for raw in pose["output_port_cells"]
            for value in [cell(raw)]
            if in_grid(value) and value not in occupied
        ]
        if len(free_inputs) < int(row["need_in"]) or len(free_outputs) < int(
            row["need_out"]
        ):
            front_failures.append(index)
    require(not unpowered, f"combined unpowered rows: {unpowered[:5]}")
    require(not front_failures, f"combined front failures: {front_failures[:5]}")
    return {
        "selected_manufacturing_count": len(selected),
        "module_b_body_count": b_count,
        "module_b_side_counts": dict(sorted(side_counts.items())),
        "operation_count": sum(operation_counts.values()),
        "class_count": sum(class_counts.values()),
        "unpowered_count": 0,
        "front_failure_count": 0,
        "occupied_cell_count": len(occupied),
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E097 check: {OUTPUT}")
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing pinned input: {path}")
        require(sha256(path) == expected, f"pinned input drift: {path}")
    for path in (RUNNER, RESULT, MODULE_B, AUDIT):
        require(path.is_file(), f"missing E097 artifact: {path}")

    result = load(RESULT)
    module_b = load(MODULE_B)
    audit = load(AUDIT)
    require(
        sha256(RUNNER) == result["identity"]["runner_sha256"],
        "E097 runner identity drift",
    )
    require(
        sha256(MODULE_B) == result["module_b"]["sha256"],
        "E097 module-B identity drift",
    )
    require(
        sha256(AUDIT) == result["reserved_column_audit"]["sha256"],
        "E097 audit identity drift",
    )
    require(audit["status"] == "PASS", "reserved-column audit is not PASS")
    require(audit["all_b_candidate_count"] == 4378, "B universe drift")
    require(audit["separator_candidate_count"] == 436, "separator drift")
    require(audit["survivor_candidate_count"] == 3942, "survivor drift")
    require(
        audit["side_candidate_counts"] == {"high": 2027, "low": 1915},
        "side candidate count drift",
    )
    require(audit["reserved_column_fixed_solid_count"] == 0, "fixed x35 drift")
    require(audit["cross_body_cell_count"] == 0, "cross body drift")
    require(
        audit["low_front_high_body_intersection_count"] == 0
        and audit["high_front_low_body_intersection_count"] == 0,
        "cross-side front/body drift",
    )
    require(module_b["status"] == result["module_b"]["status"], "status join drift")

    status = str(module_b["status"])
    branch: dict[str, Any]
    if status in {"OPTIMAL", "FEASIBLE"}:
        require(COMBINED.is_file(), "positive E097 lacks combined witness")
        require(result["combined_witness"] is not None, "positive result lacks pointer")
        require(
            sha256(COMBINED) == result["combined_witness"]["sha256"],
            "combined witness identity drift",
        )
        require(
            result["verdict"] == "RESERVED_X35_MODULE_B_FRONT_WITNESS_FOUND",
            "positive verdict drift",
        )
        require(
            result["decision"]
            == "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING",
            "positive decision drift",
        )
        e095 = import_module(E095_RUNNER, "zmd_e097_check_e095")
        combined = load(COMBINED)
        replay = semantic_replay(e095, combined["selected_manufacturing"])
        require(combined["status"] == "PASS", "combined witness status drift")
        branch = {
            "classification": "POSITIVE_NATIVE_FRONT_WITNESS",
            "combined_witness_sha256": sha256(COMBINED),
            "semantic_replay": replay,
        }
    elif status == "INFEASIBLE":
        require(not COMBINED.exists(), "negative E097 carries combined witness")
        require(result["combined_witness"] is None, "negative result carries pointer")
        require(
            result["verdict"] == "RESERVED_X35_SUFFICIENT_CONSTRUCTOR_INFEASIBLE",
            "negative verdict drift",
        )
        require(
            result["decision"]
            == "RESTORE_EXPLICIT_SEPARATOR_AND_SOLVE_CONDITIONED_ALLOCATIONS",
            "negative decision drift",
        )
        branch = {"classification": "CONTEXTUAL_INFEASIBLE"}
    else:
        require(not COMBINED.exists(), "censored E097 carries combined witness")
        require(result["combined_witness"] is None, "censored result carries pointer")
        require(
            result["verdict"] == "RESERVED_X35_MODULE_B_CONSTRUCTOR_CENSORED",
            "censored verdict drift",
        )
        require(
            result["decision"]
            == "SOLVE_LOW_HIGH_SIDES_CONDITIONED_ON_ALLOCATION_VECTORS",
            "censored decision drift",
        )
        require(
            int(result["module_b"]["selected_body_count"]) == 0,
            "censored result carries selected bodies",
        )
        branch = {"classification": "CENSORED_NO_INCUMBENT"}

    payload = {
        "schema": "zmd_e097_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "runner_sha256": sha256(RUNNER),
        "result_sha256": sha256(RESULT),
        "module_b_sha256": sha256(MODULE_B),
        "audit_sha256": sha256(AUDIT),
        "module_b_status": status,
        "verdict": result["verdict"],
        "decision": result["decision"],
        "branch": branch,
        "truth_boundary": (
            "Branch-aware artifact replay. A positive is replayed at the complete "
            "native-front class layer; negative/censored branches remain scoped to "
            "the reserved-x35 sufficient restriction."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": branch["classification"],
                "module_b_status": status,
                "verdict": result["verdict"],
                "decision": result["decision"],
                "output_path": str(OUTPUT.relative_to(ROOT)),
                "output_sha256": sha256(OUTPUT),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
