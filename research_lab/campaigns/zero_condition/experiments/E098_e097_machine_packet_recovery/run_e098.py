#!/usr/bin/env python3
"""E098: recover missing E096/E097 machine packets without silent rebinding."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from types import ModuleType
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E098_e097_machine_packet_recovery/run-001"
)

E095_DIR = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E095_y41_module_product_decomposition"
)
E095_RUNNER = E095_DIR / "run_e095.py"
E095_DURABLE = E095_DIR / "RESULT.txt"
E095_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001/RESULT.json"
)
E095_CHECK = E095_RESULT.with_name("ARTIFACT_CHECK.json")
E095_MODULE_A = E095_RESULT.with_name("MODULE_A_RESULT.json")

E096_DIR = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E096_module_b_interface_thickness"
)
E096_RUNNER = E096_DIR / "run_e096.py"
E096_CHECKER = E096_DIR / "check_artifacts.py"
E096_SNAPSHOT = E096_DIR / "MACHINE_SNAPSHOT.json"
E096_DURABLE = E096_DIR / "RESULT.txt"
E096_OLD_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E096_module_b_interface_thickness/run-001"
)

E097_DIR = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E097_reserved_x35_module_b_constructor"
)
E097_RUNNER = E097_DIR / "run_e097.py"
E097_CHECKER = E097_DIR / "check_artifacts.py"
E097_DURABLE = E097_DIR / "RESULT.txt"
E097_OLD_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E097_reserved_x35_module_b_constructor/run-001"
)

EXPECTED_HASHES = {
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_DURABLE: "9d1411c0aac5c01b8d065051d26e204ddbe0e2751c45e81feb1b5002fe1cbe88",
    E095_RESULT: "78de6850a02e66d1018a6f3f3ec545d624e16bdc0cf7e4ef1b455ea2eb25e609",
    E095_CHECK: "6d75894d7a79cb9611fc20d1121a832777f9cf4eeb8e67bb4fef85066d0ee43f",
    E095_MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
    E096_RUNNER: "5a46528e795fa7e866c1ba79eea20fb6b0ce770def46e30fbbd15311576463ec",
    E096_CHECKER: "9126781ee66eb0cfb3b19eed22d975abc41fbe13df54a862aad9f42038ec78cd",
    E096_SNAPSHOT: "2fea85fa6d1b7d60454179dcea89d3aaf9191102ff28c870bbbce6409160c3d9",
    E096_DURABLE: "98bd4b5fad453169343586124e5dd6e184ed0176f5bbe928e2d01c66baf101f7",
    E097_RUNNER: "66a96d5d9dbd934d28327b1ea44cb81d7dbfe5682a799b0659e68e6c5866cad4",
    E097_CHECKER: "c5126cbd3ae60ba03991e3eaae803d06a149f04baea0f4b0d31ce5bab2cf3068",
    E097_DURABLE: "fa857a5f8f791192a478e71f9c2b7cb961b7f67b5dd44e9630198bfc294c4286",
}
STALE_E095_DURABLE_HASH = (
    "6794d794cbd512c5bc01379a2f29ace4080127dc8c4d98bd706b9a792e536b14"
)
E097_SECONDS = 240.0
E097_SEED = 97001


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


def import_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E098 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E098 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(f"E098 input drift: {path}: {observed} != {expected}")
        checked[display(path)] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }

    e096_source = E096_RUNNER.read_text(encoding="utf-8")
    e097_source = E097_RUNNER.read_text(encoding="utf-8")
    if STALE_E095_DURABLE_HASH not in e096_source:
        raise RuntimeError("E098 E096 stale durable hash is no longer present")
    if STALE_E095_DURABLE_HASH not in e097_source:
        raise RuntimeError("E098 E097 stale durable hash is no longer present")

    old_e096_result = E096_OLD_RUN / "RESULT.json"
    old_e096_check = E096_OLD_RUN / "ARTIFACT_CHECK.json"
    old_e097_required = [
        E097_OLD_RUN / "RESULT.json",
        E097_OLD_RUN / "MODULE_B_RESULT.json",
        E097_OLD_RUN / "RESERVED_COLUMN_AUDIT.json",
        E097_OLD_RUN / "ARTIFACT_CHECK.json",
    ]
    if old_e096_result.exists() or old_e096_check.exists():
        raise RuntimeError("E098 expected old E096 terminal packet to be absent")
    if any(path.exists() for path in old_e097_required):
        raise RuntimeError("E098 expected old E097 terminal packet to be absent")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
        "incident": {
            "stale_e095_durable_hash": STALE_E095_DURABLE_HASH,
            "committed_e095_durable_hash": EXPECTED_HASHES[E095_DURABLE],
            "old_e096_terminal_packet_present": False,
            "old_e097_terminal_packet_present": False,
            "old_e096_recovery_failure_present": (
                E096_OLD_RUN / "FAILURE.json"
            ).is_file(),
        },
    }


def patch_e096_for_recovery(module: ModuleType) -> None:
    if module.EXPECTED_HASHES[module.E095_DURABLE] != STALE_E095_DURABLE_HASH:
        raise RuntimeError("E098 E096 stale pin value drift")
    module.EXPECTED_HASHES[module.E095_DURABLE] = EXPECTED_HASHES[E095_DURABLE]


def patch_e096_checker(checker: ModuleType, run_dir: Path) -> None:
    checker.RUN = run_dir
    checker.RESULT = run_dir / "RESULT.json"
    checker.TEMPLATE = run_dir / "TEMPLATE_INTERFACE.json"
    checker.SPATIAL = run_dir / "SPATIAL_INTERFACE_FRONTIER.json"
    checker.CANDIDATES = run_dir / "B_CANDIDATE_INTERFACE_RECORDS.json"
    checker.OUTPUT = run_dir / "ARTIFACT_CHECK.json"
    checker.EXPECTED = {
        checker.RUNNER: sha256_file(checker.RUNNER),
        checker.RESULT: sha256_file(checker.RESULT),
        checker.TEMPLATE: sha256_file(checker.TEMPLATE),
        checker.SPATIAL: sha256_file(checker.SPATIAL),
        checker.CANDIDATES: sha256_file(checker.CANDIDATES),
    }


def compare_e096_snapshot(
    result: Mapping[str, Any], snapshot: Mapping[str, Any], check: Mapping[str, Any]
) -> dict[str, Any]:
    selected = result["selected_spatial_cut"]
    expected_selected = snapshot["selected_spatial_cut"]
    comparisons = {
        "candidate_count": result["candidate_count"] == snapshot["candidate_count"],
        "required_body_count": result["required_body_count"]
        == snapshot["required_body_count"],
        "template_interface": {
            key: result["template_interface"][key]
            == snapshot["template_interface"][key]
            for key in (
                "group_candidate_counts",
                "interface_occupancy_cell_count",
                "interface_candidate_count",
                "largest_group_candidate_count",
                "class_allocation_dimension_count",
            )
        },
        "selected_spatial_cut": {
            key: selected[key] == expected_selected[key]
            for key in (
                "cut_id",
                "axis",
                "coordinate",
                "balance_guard_pass",
                "group_candidate_counts",
                "group_anchor_counts",
                "interface_occupancy_cell_count",
                "interface_candidate_count",
                "separator_candidate_fraction",
                "largest_side_candidate_count",
                "class_allocation_dimension_count",
                "class_allocation_log2_box_upper_bound",
            )
        },
        "verdict": result["verdict"]
        == snapshot["terminal_result"]["verdict"],
        "decision": result["decision"]
        == snapshot["terminal_result"]["decision"],
        "check_status": check.get("status") == "PASS",
    }
    flat = [
        comparisons["candidate_count"],
        comparisons["required_body_count"],
        *comparisons["template_interface"].values(),
        *comparisons["selected_spatial_cut"].values(),
        comparisons["verdict"],
        comparisons["decision"],
        comparisons["check_status"],
    ]
    if not all(flat):
        raise RuntimeError(f"E098 E096 semantic snapshot mismatch: {comparisons}")
    return {"status": "PASS", "comparisons": comparisons}


def patch_e097_for_recovery(
    module: ModuleType, e096_result: Path, e096_check: Path
) -> None:
    if module.EXPECTED_HASHES[module.E095_DURABLE] != STALE_E095_DURABLE_HASH:
        raise RuntimeError("E098 E097 stale durable pin value drift")
    module.EXPECTED_HASHES[module.E095_DURABLE] = EXPECTED_HASHES[E095_DURABLE]
    old_result = module.E096_RESULT
    old_check = module.E096_CHECK
    module.EXPECTED_HASHES.pop(old_result)
    module.EXPECTED_HASHES.pop(old_check)
    module.E096_RESULT = e096_result
    module.E096_CHECK = e096_check
    module.EXPECTED_HASHES[e096_result] = sha256_file(e096_result)
    module.EXPECTED_HASHES[e096_check] = sha256_file(e096_check)


def patch_e097_checker(
    checker: ModuleType, run_dir: Path, e096_result: Path
) -> None:
    checker.RUN = run_dir
    checker.RESULT = run_dir / "RESULT.json"
    checker.MODULE_B = run_dir / "MODULE_B_RESULT.json"
    checker.AUDIT = run_dir / "RESERVED_COLUMN_AUDIT.json"
    checker.COMBINED = run_dir / "COMBINED_WITNESS.json"
    checker.OUTPUT = run_dir / "ARTIFACT_CHECK.json"
    old_e096 = checker.E096_RESULT
    checker.EXPECTED.pop(old_e096)
    checker.E096_RESULT = e096_result
    checker.EXPECTED[e096_result] = sha256_file(e096_result)


def run(run_dir: Path) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E098 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    e096_run_dir = run_dir / "e096-semantic-rerun"
    e096 = import_module(E096_RUNNER, "zmd_e098_recovered_e096")
    patch_e096_for_recovery(e096)
    e096_result_value = e096.run(e096_run_dir)
    e096_result_path = e096_run_dir / "RESULT.json"

    e096_checker = import_module(E096_CHECKER, "zmd_e098_recovered_e096_check")
    patch_e096_checker(e096_checker, e096_run_dir)
    if int(e096_checker.main()) != 0:
        raise RuntimeError("E098 E096 checker returned nonzero")
    e096_check_path = e096_run_dir / "ARTIFACT_CHECK.json"
    e096_check_value = load_json(e096_check_path)
    snapshot_comparison = compare_e096_snapshot(
        e096_result_value, load_json(E096_SNAPSHOT), e096_check_value
    )
    snapshot_path = run_dir / "E096_SNAPSHOT_COMPARISON.json"
    dump_exclusive(snapshot_path, snapshot_comparison)

    e097_run_dir = run_dir / "e097-branch-replay"
    e097 = import_module(E097_RUNNER, "zmd_e098_recovered_e097")
    patch_e097_for_recovery(e097, e096_result_path, e096_check_path)
    e097_result_value = e097.run(
        run_dir=e097_run_dir,
        seconds=E097_SECONDS,
        seed=E097_SEED,
    )
    e097_result_path = e097_run_dir / "RESULT.json"

    e097_checker = import_module(E097_CHECKER, "zmd_e098_recovered_e097_check")
    patch_e097_checker(e097_checker, e097_run_dir, e096_result_path)
    if int(e097_checker.main()) != 0:
        raise RuntimeError("E098 E097 checker returned nonzero")
    e097_check_path = e097_run_dir / "ARTIFACT_CHECK.json"
    e097_check_value = load_json(e097_check_path)
    if e097_check_value.get("status") != "PASS":
        raise RuntimeError("E098 recovered E097 checker is not PASS")

    module_status = str(e097_result_value["module_b"]["status"])
    verdict = str(e097_result_value["verdict"])
    decision = str(e097_result_value["decision"])
    classification = str(e097_check_value["branch"]["classification"])
    if module_status in {"OPTIMAL", "FEASIBLE"}:
        recovery_verdict = "E097_POSITIVE_BRANCH_RECOVERED"
    elif module_status == "INFEASIBLE":
        recovery_verdict = "E097_CONTEXTUAL_NEGATIVE_BRANCH_RECOVERED"
    else:
        recovery_verdict = "E097_CENSORED_BRANCH_RECOVERED"

    result = {
        "schema": "zmd_e098_e097_machine_packet_recovery_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": recovery_verdict,
        "decision": decision,
        "identity": identity,
        "e096_recovery": {
            "result_path": display(e096_result_path),
            "result_sha256": sha256_file(e096_result_path),
            "check_path": display(e096_check_path),
            "check_sha256": sha256_file(e096_check_path),
            "snapshot_comparison_path": display(snapshot_path),
            "snapshot_comparison_sha256": sha256_file(snapshot_path),
            "snapshot_match": True,
            "verdict": e096_result_value["verdict"],
            "decision": e096_result_value["decision"],
            "selected_cut_id": e096_result_value["selected_spatial_cut"]["cut_id"],
        },
        "e097_replay": {
            "result_path": display(e097_result_path),
            "result_sha256": sha256_file(e097_result_path),
            "module_b_path": display(e097_run_dir / "MODULE_B_RESULT.json"),
            "module_b_sha256": sha256_file(e097_run_dir / "MODULE_B_RESULT.json"),
            "audit_path": display(e097_run_dir / "RESERVED_COLUMN_AUDIT.json"),
            "audit_sha256": sha256_file(
                e097_run_dir / "RESERVED_COLUMN_AUDIT.json"
            ),
            "check_path": display(e097_check_path),
            "check_sha256": sha256_file(e097_check_path),
            "module_b_status": module_status,
            "verdict": verdict,
            "decision": decision,
            "branch_classification": classification,
            "combined_witness": e097_result_value.get("combined_witness"),
            "elapsed_seconds": e097_result_value["module_b"]["elapsed_seconds"],
            "branches": e097_result_value["module_b"]["branches"],
            "conflicts": e097_result_value["module_b"]["conflicts"],
        },
        "truth_boundary": (
            "Fresh semantic recovery and branch replay. The lost E096/E097 byte "
            "packets are not resurrected. The recovered branch is authoritative "
            "only under the reserved-x35 fixed-skeleton native-front restriction."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    run_dir = DEFAULT_RUN_DIR
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(run_dir)
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "module_b_status": result["e097_replay"]["module_b_status"],
                    "branch_classification": result["e097_replay"][
                        "branch_classification"
                    ],
                    "e096_snapshot_match": result["e096_recovery"][
                        "snapshot_match"
                    ],
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
            "schema": "zmd_e098_execution_failure_v1",
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
