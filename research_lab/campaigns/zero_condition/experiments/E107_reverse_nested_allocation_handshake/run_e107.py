#!/usr/bin/env python3
"""E107: reverse lower-proposer / upper-consumer allocation handshake."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import traceback
import types
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E107_reverse_nested_allocation_handshake/run-001"
)
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
E100_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E100_source_stable_reserved_x42_hybrid/run_e100.py"
)
E101_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E101_x42_allocation_handshake/run_e101.py"
)
E101_BODY = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E101_x42_allocation_handshake/run-001/BODY_ONLY_RESULT.json"
)
E104_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E104_high_reserved_y60_constructor/run_e104.py"
)
E105_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E105_nested_allocation_handshake/run_e105.py"
)
E106_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E106_nested_template_split_frontier/run_e106.py"
)
E106_DURABLE = E106_RUNNER.with_name("RESULT.txt")
E106_SNAPSHOT = E106_RUNNER.with_name("MACHINE_SNAPSHOT.json")
E106_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E106_nested_template_split_frontier/run-001"
)
E106_RESULT = E106_RUN / "RESULT.json"
E106_CHECK = E106_RUN / "ARTIFACT_CHECK.json"
E106_SPLIT_STORE = E106_RUN / "TEMPLATE_SPLIT_NOGOODS.json"
E106_BODY_OPEN = E106_RUN / "BODY_PROPOSAL_03.json"

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_RUNNER: "a06e606b3e93056c924703fc6c009fa545b69db0148b9aeb785c18e2ec0b4bf4",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E104_RUNNER: "1b2eae0a788e0f4be4cf4af857b8f5b4ceb16f17a215eed41c7d68d656a315fd",
    E105_RUNNER: "7dbdf3be073dd77b6ef091b4302442aa5766882d2f384b285576b84c368588b9",
    E106_RUNNER: "485698087b044f99fa5ca6146c16421e7600c8780474691e60939ede944d66ab",
    E106_DURABLE: "1f5dab11310f2512878f312ffffb2ecf89fa0367b414389e0c0d2e0a2d55b7d6",
    E106_SNAPSHOT: "dcff8cbb7ac97187c00fa62689b2afb4e763194be9222cce37a47e8a767c2d00",
    E106_RESULT: "026fe686944616305ff5056a574152a5c8d57fac44b15a797563b555c33316ae",
    E106_CHECK: "acad46fdf658475d2dcc801a624514dde4213e0c890424debb7e2d5fb4ba9cfc",
    E106_SPLIT_STORE: "48cac90a3e704b82b0e50c22644a604214156d8dcfbbaa90c78a5ae5f74ecb96",
    E106_BODY_OPEN: "8293d53a8985b1631e7211e562e7422e783a36741f6e20b8945431db6d032f0a",
}

TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
LOWER_TEMPLATES = {
    "manufacturing_3x3": 5,
    "manufacturing_5x5": 4,
    "manufacturing_6x4": 9,
}
UPPER_TEMPLATES = {
    "manufacturing_3x3": 5,
    "manufacturing_5x5": 2,
    "manufacturing_6x4": 1,
}
OUTER_LOW_TEMPLATES = {
    "manufacturing_3x3": 43,
    "manufacturing_5x5": 11,
    "manufacturing_6x4": 11,
}
OPEN_UPPER_SPLIT = (5, 2, 1)
OPEN_LOWER_SPLIT = (5, 4, 9)
EXPECTED_CLASS_COUNT = 8
DEFAULT_MAX_VECTORS = 3


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


def process_snapshot() -> dict[str, int]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "ru_maxrss_kib": int(usage.ru_maxrss),
        "minor_page_faults": int(usage.ru_minflt),
        "major_page_faults": int(usage.ru_majflt),
        "voluntary_context_switches": int(usage.ru_nvcsw),
        "involuntary_context_switches": int(usage.ru_nivcsw),
    }


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
        raise RuntimeError("E107 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E107 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(f"E107 input drift: {path}: {observed} != {expected}")
        checked[display(path)] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }

    result = load_json(E106_RESULT)
    if result.get("verdict") != "NESTED_ALLOCATION_VECTOR_LIMIT_REACHED":
        raise RuntimeError("E107 E106 verdict drift")
    if result.get("decision") != "CONTINUE_FROM_SPLIT_AND_ALLOCATION_NOGOOD_STORE":
        raise RuntimeError("E107 E106 decision drift")
    check = load_json(E106_CHECK)
    if check.get("status") != "PASS" or check.get("classification") != (
        "THREE_NEW_SPLIT_NOGOODS_AND_THREE_ALLOCATION_NOGOODS_REPLAYED"
    ):
        raise RuntimeError("E107 E106 check drift")
    if tuple(map(int, check.get("open_split_upper", []))) != OPEN_UPPER_SPLIT:
        raise RuntimeError("E107 open split drift")
    body = load_json(E106_BODY_OPEN)
    split = body.get("split", {})
    if tuple(map(int, split.get("upper", []))) != OPEN_UPPER_SPLIT:
        raise RuntimeError("E107 open body upper split drift")
    if tuple(map(int, split.get("lower", []))) != OPEN_LOWER_SPLIT:
        raise RuntimeError("E107 open body lower split drift")
    if len(result.get("allocation_nogoods", [])) != 3:
        raise RuntimeError("E107 prior allocation store drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def run(
    *,
    run_dir: Path,
    lower_seconds: float,
    upper_seconds: float,
    outer_low_seconds: float,
    max_vectors: int,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E107 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e107_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e107_source_e100")
    e101 = source_module(E101_RUNNER, "zmd_e107_source_e101")
    e104 = source_module(E104_RUNNER, "zmd_e107_source_e104")
    e105 = source_module(E105_RUNNER, "zmd_e107_source_e105")
    prepared = e104.reconstruct(e095=e095, e100=e100)
    open_body = load_json(E106_BODY_OPEN)
    body_hint_indices = set(map(int, open_body["selected_global_indices"]))

    global_counts = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    class_keys = tuple(sorted(global_counts))
    if len(class_keys) != EXPECTED_CLASS_COUNT:
        raise RuntimeError("E107 class count drift")

    lower_model = e105.build_nested_model(
        e095=e095,
        prepared=prepared,
        nested_side="lower",
        template_counts=LOWER_TEMPLATES,
        body_hint_indices=body_hint_indices,
        allocation_caps=global_counts,
    )
    outer_low_hint_indices = set(map(int, load_json(E101_BODY)["selected_body_indices"]))
    prior = load_json(E106_RESULT)
    prior_upper_nogoods = [
        list(map(int, row["proposer_allocation_tuple"]))
        for row in prior["allocation_nogoods"]
    ]
    prior_lower_complements = [
        [
            int(global_counts[key]) - int(vector[index])
            for index, key in enumerate(class_keys)
        ]
        for vector in prior_upper_nogoods
    ]

    records: list[dict[str, Any]] = []
    new_lower_nogoods: list[list[int]] = []
    final_module_b: dict[str, Any] | None = None
    final_combined: dict[str, Any] | None = None
    total_high_allocation_nogood: list[int] | None = None
    terminal = "VECTOR_LIMIT"

    for iteration in range(max_vectors):
        lower = e105.solve_nested(
            lower_model,
            seconds=lower_seconds,
            seed=107100 + iteration,
        )
        lower_path = run_dir / f"LOWER_PROPOSER_{iteration:02d}.json"
        dump_exclusive(lower_path, lower)
        record: dict[str, Any] = {
            "iteration": iteration,
            "lower_path": display(lower_path),
            "lower_sha256": sha256_file(lower_path),
            "lower_status": lower["status"],
            "lower_elapsed_seconds": lower["elapsed_seconds"],
            "lower_branches": lower["branches"],
            "lower_conflicts": lower["conflicts"],
        }
        records.append(record)

        if lower["status"] == "INFEASIBLE":
            terminal = (
                "LOWER_DIRECT_INFEASIBLE"
                if iteration == 0
                else "LOWER_FACE_EXHAUSTED_AFTER_UPPER_NOGOODS"
            )
            record["effect"] = "NO_AUTOMATIC_SPLIT_PROMOTION_PENDING_CHAIN_REPLAY"
            break
        if lower["status"] not in {"OPTIMAL", "FEASIBLE"}:
            terminal = f"LOWER_{lower['status']}"
            record["effect"] = "CENSORED_NO_NOGOOD"
            break

        lower_tuple = list(map(int, lower["allocation_tuple"]))
        upper_allocation = e101.complement_allocation(
            class_keys,
            global_counts,
            lower_tuple,
        )
        upper_tuple = [int(upper_allocation[key]) for key in class_keys]
        record["lower_allocation_tuple"] = lower_tuple
        record["upper_complement_tuple"] = upper_tuple

        upper_model = e105.build_nested_model(
            e095=e095,
            prepared=prepared,
            nested_side="upper",
            template_counts=UPPER_TEMPLATES,
            body_hint_indices=body_hint_indices,
            allocation_caps=upper_allocation,
        )
        upper = e105.solve_nested(
            upper_model,
            seconds=upper_seconds,
            seed=107200 + iteration,
        )
        upper_path = run_dir / f"UPPER_CONSUMER_{iteration:02d}.json"
        dump_exclusive(upper_path, upper)
        record.update(
            {
                "upper_path": display(upper_path),
                "upper_sha256": sha256_file(upper_path),
                "upper_status": upper["status"],
                "upper_elapsed_seconds": upper["elapsed_seconds"],
                "upper_branches": upper["branches"],
                "upper_conflicts": upper["conflicts"],
            }
        )

        if upper["status"] == "INFEASIBLE":
            lower_model["model"].AddForbiddenAssignments(
                [lower_model["allocation_vars"][key] for key in class_keys],
                [lower_tuple],
            )
            new_lower_nogoods.append(lower_tuple)
            record["effect"] = "EXACT_LOWER_ALLOCATION_NOGOOD"
            continue
        if upper["status"] not in {"OPTIMAL", "FEASIBLE"}:
            terminal = f"UPPER_{upper['status']}"
            record["effect"] = "CENSORED_NO_NOGOOD"
            break

        high = e105.merge_high(
            class_keys=class_keys,
            left=lower,
            right=upper,
        )
        high_path = run_dir / f"HIGH_WITNESS_{iteration:02d}.json"
        dump_exclusive(high_path, high)
        high_tuple = list(map(int, high["allocation_tuple"]))
        outer_low_allocation = e101.complement_allocation(
            class_keys,
            global_counts,
            high_tuple,
        )
        outer_low_model = e101.build_side_model(
            e095=e095,
            restricted=prepared["restricted"],
            side="low",
            template_counts=OUTER_LOW_TEMPLATES,
            body_hint_indices=outer_low_hint_indices,
            fixed_allocation=outer_low_allocation,
        )
        outer_low = e101.solve_side(
            outer_low_model,
            seconds=outer_low_seconds,
            seed=107300 + iteration,
        )
        outer_low_path = run_dir / f"OUTER_LOW_{iteration:02d}.json"
        dump_exclusive(outer_low_path, outer_low)
        record.update(
            {
                "high_path": display(high_path),
                "high_sha256": sha256_file(high_path),
                "total_high_allocation_tuple": high_tuple,
                "outer_low_path": display(outer_low_path),
                "outer_low_sha256": sha256_file(outer_low_path),
                "outer_low_status": outer_low["status"],
                "outer_low_elapsed_seconds": outer_low["elapsed_seconds"],
            }
        )

        if outer_low["status"] in {"OPTIMAL", "FEASIBLE"}:
            combined = e101.combine_side_witnesses(
                e095=e095,
                restricted=prepared["restricted"],
                low=outer_low,
                high=high,
            )
            final_module_b = combined["module_b"]
            final_combined = combined["combined"]
            module_b_path = run_dir / "MODULE_B_WITNESS.json"
            combined_path = run_dir / "COMBINED_WITNESS.json"
            dump_exclusive(module_b_path, final_module_b)
            dump_exclusive(combined_path, final_combined)
            record["effect"] = "PAIRED_219_BODY_NATIVE_FRONT_WITNESS"
            terminal = "FULL_POSITIVE"
            break
        if outer_low["status"] == "INFEASIBLE":
            total_high_allocation_nogood = high_tuple
            record["effect"] = "EXACT_TOTAL_HIGH_ALLOCATION_NOGOOD"
            terminal = "OUTER_LOW_INFEASIBLE"
            break
        record["effect"] = "OUTER_LOW_CENSORED"
        terminal = f"OUTER_LOW_{outer_low['status']}"
        break

    store_path = run_dir / "BIDIRECTIONAL_ALLOCATION_STORE.json"
    dump_exclusive(
        store_path,
        {
            "schema": "zmd_e107_bidirectional_allocation_store_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "split": {
                "template_order": list(TEMPLATES),
                "upper": list(OPEN_UPPER_SPLIT),
                "lower": list(OPEN_LOWER_SPLIT),
                "split_digest": str(open_body["split"]["split_digest"]),
            },
            "e106_upper_vectors_rejected_by_lower": prior_upper_nogoods,
            "e106_lower_complements": prior_lower_complements,
            "e107_lower_vectors_rejected_by_upper": new_lower_nogoods,
            "truth_boundary": (
                "E106 vectors are upper-feasible/lower-infeasible. E107 vectors are "
                "lower-feasible/upper-infeasible. No UNKNOWN enters either list."
            ),
        },
    )

    if terminal == "FULL_POSITIVE":
        verdict = "REVERSE_HANDSHAKE_NATIVE_FRONT_WITNESS_FOUND"
        decision = "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING"
    elif terminal in {
        "LOWER_DIRECT_INFEASIBLE",
        "LOWER_FACE_EXHAUSTED_AFTER_UPPER_NOGOODS",
    }:
        verdict = "OPEN_SPLIT_ALLOCATION_FACE_EXHAUSTED_PENDING_REPLAY"
        decision = "REPLAY_COMPLETE_NOGOOD_CHAIN_BEFORE_SPLIT_PROMOTION"
    elif terminal.startswith("LOWER_"):
        verdict = "REVERSE_HANDSHAKE_LOWER_PROPOSER_CENSORED"
        decision = "REPLAY_ONLY_PINNED_LOWER_PROPOSER"
    elif terminal.startswith("UPPER_"):
        verdict = "REVERSE_HANDSHAKE_UPPER_CONSUMER_CENSORED"
        decision = "REPLAY_ONLY_PINNED_UPPER_COMPLEMENT"
    elif terminal == "OUTER_LOW_INFEASIBLE":
        verdict = "REVERSE_HANDSHAKE_TOTAL_HIGH_ALLOCATION_REJECTED"
        decision = "RECORD_TOTAL_HIGH_ALLOCATION_NOGOOD"
    elif terminal.startswith("OUTER_LOW_"):
        verdict = "REVERSE_HANDSHAKE_OUTER_LOW_CENSORED"
        decision = "REPLAY_ONLY_PINNED_OUTER_LOW_COMPLEMENT"
    else:
        verdict = "REVERSE_HANDSHAKE_VECTOR_LIMIT_REACHED"
        decision = "CONTINUE_FROM_BIDIRECTIONAL_ALLOCATION_STORE"

    module_b_path = run_dir / "MODULE_B_WITNESS.json"
    combined_path = run_dir / "COMBINED_WITNESS.json"
    result = {
        "schema": "zmd_e107_reverse_nested_allocation_handshake_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "terminal": terminal,
        "identity": identity,
        "controls": {
            "lower_seconds_per_vector": lower_seconds,
            "upper_seconds_per_vector": upper_seconds,
            "outer_low_seconds": outer_low_seconds,
            "max_new_lower_vectors": max_vectors,
            "source_isolated_helpers": True,
            "proposal_direction": "lower_to_upper",
        },
        "split": {
            "template_order": list(TEMPLATES),
            "upper": list(OPEN_UPPER_SPLIT),
            "lower": list(OPEN_LOWER_SPLIT),
            "split_digest": str(open_body["split"]["split_digest"]),
        },
        "prior_upper_nogood_count": len(prior_upper_nogoods),
        "records": records,
        "new_lower_allocation_nogoods": new_lower_nogoods,
        "bidirectional_store": {
            "path": display(store_path),
            "sha256": sha256_file(store_path),
            "e106_upper_nogood_count": len(prior_upper_nogoods),
            "e107_lower_nogood_count": len(new_lower_nogoods),
        },
        "total_high_allocation_nogood": total_high_allocation_nogood,
        "module_b_witness": (
            {
                "path": display(module_b_path),
                "sha256": sha256_file(module_b_path),
                "selected_body_count": final_module_b["selected_body_count"],
                "selected_assignment_digest": final_module_b[
                    "selected_assignment_digest"
                ],
            }
            if final_module_b is not None
            else None
        ),
        "combined_witness": (
            {
                "path": display(combined_path),
                "sha256": sha256_file(combined_path),
                "status": final_combined["status"],
                "selected_manufacturing_count": final_combined[
                    "selected_manufacturing_count"
                ],
                "selected_assignment_digest": final_combined[
                    "selected_assignment_digest"
                ],
            }
            if final_combined is not None
            else None
        ),
        "truth_boundary": (
            "Each E107 nogood rejects one exact lower-feasible allocation whose "
            "upper complement is exact INFEASIBLE. Split promotion requires a "
            "separate complete-chain replay. UNKNOWN creates no nogood."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--lower-seconds", type=float, default=60.0)
    parser.add_argument("--upper-seconds", type=float, default=35.0)
    parser.add_argument("--outer-low-seconds", type=float, default=70.0)
    parser.add_argument("--max-vectors", type=int, default=DEFAULT_MAX_VECTORS)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            lower_seconds=float(args.lower_seconds),
            upper_seconds=float(args.upper_seconds),
            outer_low_seconds=float(args.outer_low_seconds),
            max_vectors=int(args.max_vectors),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "terminal": result["terminal"],
                    "record_count": len(result["records"]),
                    "new_lower_nogood_count": len(
                        result["new_lower_allocation_nogoods"]
                    ),
                    "combined_witness": result["combined_witness"] is not None,
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
            "schema": "zmd_e107_execution_failure_v1",
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
