#!/usr/bin/env python3
"""Independent branch-aware replay for E100 reserved-x42 hybrid constructor."""

from __future__ import annotations

from collections import Counter
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
RUNNER = HERE / "run_e100.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E100_source_stable_reserved_x42_hybrid/run-001"
)
RESULT = RUN / "RESULT.json"
MODULE_B = RUN / "MODULE_B_RESULT.json"
AUDIT = RUN / "RESERVED_COLUMN_AUDIT.json"
COMBINED = RUN / "COMBINED_WITNESS.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
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
E099_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E099_source_isolated_e096_revalidation/run-002/RESULT.json"
)

EXPECTED = {
    RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    RESULT: "d4de0239604cf4713164069fda553965275566c1840238ec4fa98446ba71b12c",
    MODULE_B: "da25935b9d9340117f1c2d7567de9d4e0fe397f2ce80eb944c148757906f2897",
    AUDIT: "9bdfea97b315971bfe4c913c9c4dc75d18c1078c885e61bacc877d2604e2668f",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
    E099_RESULT: "cb602a987cd47382b8dd64ed224f931029d7a41abf2a9d367e2e6df21b767f55",
}
RESERVED_X = 42
SEAM_Y = 41


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
    code = compile(
        raw,
        f"<source-isolated:{path}:{hashlib.sha256(raw).hexdigest()}>",
        "exec",
        dont_inherit=True,
    )
    exec(code, module.__dict__)
    return module


def cell(value: Any) -> tuple[int, int]:
    if isinstance(value, Mapping):
        return int(value["x"]), int(value["y"])
    return int(value[0]), int(value[1])


def in_grid(value: tuple[int, int]) -> bool:
    return 0 <= value[0] < 70 and 0 <= value[1] < 70


def reconstruct_audit(e095: types.ModuleType) -> dict[str, Any]:
    context = e095.build_context()
    require(e095.decomposition_audit(context)["status"] == "PASS", "E095 audit drift")
    all_b = [dict(row) for row in context["body_rows"] if row["module"] == "B"]
    rows: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for row in all_b:
        body = tuple(row["body"])
        xs = [x for x, _y in body]
        if RESERVED_X in xs:
            removed.append(row)
        elif max(xs) <= 41:
            rows.append({**row, "side": "low"})
        elif min(xs) >= 43:
            rows.append({**row, "side": "high"})
        else:
            raise RuntimeError(f"checker side classification drift: {body}")

    anchor = set(context["hint_bodies"]["B"])
    fixed_hits = {
        (RESERVED_X, y)
        for y in range(SEAM_Y + 1, 70)
        if (RESERVED_X, y) in set(context["fixed_solid"])
    }

    def fronts(side: str) -> set[tuple[int, int]]:
        output: set[tuple[int, int]] = set()
        for row in rows:
            if row["side"] != side:
                continue
            template = str(row["template"])
            for pose_index in row["mode_pose_indices"]:
                pose = context["pools"][template][int(pose_index)]
                for field in ("input_port_cells", "output_port_cells"):
                    output.update(
                        value
                        for raw in pose[field]
                        for value in [cell(raw)]
                        if in_grid(value)
                    )
        return output

    low_body = {
        value for row in rows if row["side"] == "low" for value in row["body"]
    }
    high_body = {
        value for row in rows if row["side"] == "high" for value in row["body"]
    }
    low_front = fronts("low")
    high_front = fronts("high")
    return {
        "all_b_candidate_count": len(all_b),
        "removed_candidate_count": len(removed),
        "survivor_candidate_count": len(rows),
        "side_candidate_counts": dict(
            sorted(Counter(str(row["side"]) for row in rows).items())
        ),
        "side_template_candidate_counts": {
            f"{side}:{template}": int(count)
            for (side, template), count in sorted(
                Counter(
                    (str(row["side"]), str(row["template"])) for row in rows
                ).items()
            )
        },
        "removed_template_candidate_counts": dict(
            sorted(Counter(str(row["template"]) for row in removed).items())
        ),
        "anchor_removed_count": sum(tuple(row["body"]) in anchor for row in removed),
        "anchor_hint_count": sum(tuple(row["body"]) in anchor for row in rows),
        "reserved_column_fixed_solid_count": len(fixed_hits),
        "cross_body_cell_count": len(low_body & high_body),
        "low_front_high_body_intersection_count": len(low_front & high_body),
        "high_front_low_body_intersection_count": len(high_front & low_body),
        "cross_front_front_intersection_count": len(low_front & high_front),
        "cross_front_front_cells": [list(value) for value in sorted(low_front & high_front)],
    }


def semantic_replay(
    e095: types.ModuleType,
    selected: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    context = e095.build_context()
    require(len(selected) == 219, "combined selected count drift")
    fixed_solid = set(context["fixed_solid"])
    occupied = set(fixed_solid)
    side_counts: Counter[str] = Counter()
    b_count = 0
    for index, row in enumerate(selected):
        body = {cell(value) for value in row["body"]}
        require(not body & occupied, f"combined overlap at row {index}")
        occupied |= body
        if str(row["module"]) == "B":
            b_count += 1
            require(all(x != RESERVED_X for x, _y in body), "B body on x42")
            side = str(row.get("side", ""))
            require(side in {"low", "high"}, "B side drift")
            if side == "low":
                require(max(x for x, _y in body) <= 41, "low body crosses x42")
            else:
                require(min(x for x, _y in body) >= 43, "high body crosses x42")
            side_counts[side] += 1
    require(b_count == 91, "combined B count drift")
    require(
        Counter(str(row["operation"]) for row in selected)
        == context["operation_counts"],
        "combined operation multiset drift",
    )
    require(
        Counter(tuple(row["class_key"]) for row in selected)
        == context["class_counts"],
        "combined class multiset drift",
    )

    unpowered: list[int] = []
    front_failures: list[int] = []
    for index, row in enumerate(selected):
        body = {cell(value) for value in row["body"]}
        if not body & set(context["fixed_coverage"]):
            unpowered.append(index)
        pose = context["pools"][str(row["template"])][int(row["pose_index"])]
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
    require(not unpowered, f"unpowered rows: {unpowered[:5]}")
    require(not front_failures, f"front failures: {front_failures[:5]}")
    return {
        "selected_manufacturing_count": len(selected),
        "module_b_body_count": b_count,
        "module_b_side_counts": dict(sorted(side_counts.items())),
        "unpowered_count": 0,
        "front_failure_count": 0,
        "occupied_cell_count": len(occupied),
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E100 check: {OUTPUT}")
    records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E100 artifact/input: {path}")
        actual = sha256(path)
        require(actual == expected, f"E100 artifact/input drift: {path}")
        records[str(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    result = load(RESULT)
    module_b = load(MODULE_B)
    audit = load(AUDIT)
    require(result["identity"]["runner_sha256"] == sha256(RUNNER), "runner join drift")
    require(result["module_b"]["sha256"] == sha256(MODULE_B), "module join drift")
    require(
        result["reserved_column_audit"]["sha256"] == sha256(AUDIT),
        "audit join drift",
    )
    require(module_b["status"] == result["module_b"]["status"], "status join drift")
    require(load(E099_RESULT)["source_stable_interface"]["selected"]["cut_id"] == "x_after_41", "E099 cut drift")

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e100_check_source_e095")
    replay_audit = reconstruct_audit(e095)
    for key, value in replay_audit.items():
        require(audit[key] == value, f"E100 audit replay drift: {key}")
    require(audit["status"] == "PASS", "E100 audit status drift")

    status = str(module_b["status"])
    branch: dict[str, Any]
    if status in {"OPTIMAL", "FEASIBLE"}:
        require(COMBINED.is_file(), "positive E100 lacks combined witness")
        require(result["combined_witness"] is not None, "positive pointer missing")
        require(
            sha256(COMBINED) == result["combined_witness"]["sha256"],
            "combined witness join drift",
        )
        require(
            result["verdict"] == "SOURCE_STABLE_RESERVED_X42_FRONT_WITNESS_FOUND",
            "positive verdict drift",
        )
        require(
            result["decision"]
            == "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING",
            "positive decision drift",
        )
        combined = load(COMBINED)
        require(combined["status"] == "PASS", "combined witness status drift")
        branch = {
            "classification": "POSITIVE_NATIVE_FRONT_WITNESS",
            "semantic_replay": semantic_replay(
                e095, combined["selected_manufacturing"]
            ),
        }
    elif status == "INFEASIBLE":
        require(not COMBINED.exists(), "negative E100 carries combined witness")
        require(result["combined_witness"] is None, "negative pointer present")
        require(
            result["verdict"]
            == "SOURCE_STABLE_RESERVED_X42_CONSTRUCTOR_INFEASIBLE",
            "negative verdict drift",
        )
        require(
            result["decision"]
            == "RESTORE_X41_SEPARATOR_AND_SOLVE_HYBRID_ALLOCATIONS",
            "negative decision drift",
        )
        branch = {"classification": "CONTEXTUAL_INFEASIBLE"}
    else:
        require(not COMBINED.exists(), "censored E100 carries combined witness")
        require(result["combined_witness"] is None, "censored pointer present")
        require(
            result["verdict"] == "SOURCE_STABLE_RESERVED_X42_CONSTRUCTOR_CENSORED",
            "censored verdict drift",
        )
        require(
            result["decision"]
            == "SOLVE_X42_LOW_HIGH_SIDES_CONDITIONED_ON_ALLOCATIONS",
            "censored decision drift",
        )
        require(int(result["module_b"]["selected_body_count"]) == 0, "censored selected bodies")
        require(not module_b.get("selected_manufacturing"), "censored module carries witness")
        branch = {"classification": "CENSORED_NO_INCUMBENT"}

    payload = {
        "schema": "zmd_e100_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "artifact_records": records,
        "module_b_status": status,
        "verdict": result["verdict"],
        "decision": result["decision"],
        "audit_replay": replay_audit,
        "branch": branch,
        "truth_boundary": (
            "Branch-aware source-replayed artifact check. Negative/censored "
            "branches remain scoped to reserved x=42."
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
