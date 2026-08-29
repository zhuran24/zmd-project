#!/usr/bin/env python3
"""E109: exact side tests for E108's final two body-feasible splits."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
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
    "E109_last_two_template_split_discriminator/run-001"
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
E108_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E108_nested_template_projection_atlas/run_e108.py"
)
E108_DURABLE = E108_RUNNER.with_name("RESULT.txt")
E108_SNAPSHOT = E108_RUNNER.with_name("MACHINE_SNAPSHOT.json")
E108_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E108_nested_template_projection_atlas/run-001"
)
E108_RESULT = E108_RUN / "RESULT.json"
E108_BODY = E108_RUN / "BODY_TEMPLATE_PROJECTION.json"
E108_CHECK = E108_RUN / "ARTIFACT_CHECK.json"

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E104_RUNNER: "1b2eae0a788e0f4be4cf4af857b8f5b4ceb16f17a215eed41c7d68d656a315fd",
    E105_RUNNER: "7dbdf3be073dd77b6ef091b4302442aa5766882d2f384b285576b84c368588b9",
    E108_RUNNER: "b85cc525f001735fe818d9692387a9aceaa61cee4d82dbf1867ad0c920504e48",
    E108_DURABLE: "820f2b40405fbecb505953574b4647919a19b2dfd759304007472c48986c6d47",
    E108_SNAPSHOT: "86006ee56ce5a96a76b9c5bf55d8d8c29078498bfdb813ba2be3308c94f61c24",
    E108_RESULT: "c53855a54af9ad79bb278d80a084b9c0d7b66f6242bbf75cdff408ca9991c8f9",
    E108_BODY: "24fdc3943a341321a44ddf99197dc4daea82d71ff4bfd16d1f5469269ebdae80",
    E108_CHECK: "17095258691adafc54c29bf48dbc901a65cfa2d694293c044782262c306bb9c1",
}

TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
TARGETS = (
    {
        "target_id": "upper_3_0_4",
        "upper": (3, 0, 4),
        "lower": (7, 6, 6),
    },
    {
        "target_id": "upper_6_0_3",
        "upper": (6, 0, 3),
        "lower": (4, 6, 7),
    },
)


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
        raise RuntimeError("E109 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E109 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E109 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    e108 = load_json(E108_RESULT)
    if e108.get("verdict") != "TEMPLATE_PROJECTION_ATLAS_CENSORED":
        raise RuntimeError("E109 E108 verdict drift")
    check = load_json(E108_CHECK)
    if check.get("status") != "PASS" or check.get("decision") != (
        "TEST_ONLY_TWO_REMAINING_BODY_FEASIBLE_SPLITS"
    ):
        raise RuntimeError("E109 E108 check drift")
    expected_targets = {tuple(value) for value in check["remaining_body_feasible_vectors"]}
    if expected_targets != {tuple(row["upper"]) for row in TARGETS}:
        raise RuntimeError("E109 target vector drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def count_map(values: tuple[int, int, int]) -> dict[str, int]:
    return {
        template: int(values[index])
        for index, template in enumerate(TEMPLATES)
    }


def body_hint_for_vector(
    body_atlas: dict[str, Any],
    vector: tuple[int, int, int],
) -> set[int]:
    matches = [
        row
        for row in body_atlas["vectors"]
        if tuple(map(int, row["vector"])) == vector
    ]
    if len(matches) != 1:
        raise RuntimeError(f"E109 body witness remap drift: {vector}: {len(matches)}")
    witness = matches[0]["witness"]
    indices = set(map(int, witness["selected_global_indices"]))
    if len(indices) != 26:
        raise RuntimeError(f"E109 body witness size drift: {vector}")
    return indices


def summarize_side(path: Path, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": display(path),
        "sha256": sha256_file(path),
        "status": result["status"],
        "elapsed_seconds": result["elapsed_seconds"],
        "branches": result["branches"],
        "conflicts": result["conflicts"],
        "candidate_count": result["candidate_count"],
        "selected_body_count": result.get("selected_body_count", 0),
        "allocation_tuple": result.get("allocation_tuple"),
    }


def run(
    *,
    run_dir: Path,
    upper_seconds: float,
    lower_seconds: float,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E109 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e109_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e109_source_e100")
    e104 = source_module(E104_RUNNER, "zmd_e109_source_e104")
    e105 = source_module(E105_RUNNER, "zmd_e109_source_e105")
    prepared = e104.reconstruct(e095=e095, e100=e100)
    body_atlas = load_json(E108_BODY)
    global_counts = {
        key: int(count)
        for key, count in prepared["context"]["class_counts"].items()
        if key[0] == "B"
    }
    if len(global_counts) != 8:
        raise RuntimeError("E109 class count drift")

    records: list[dict[str, Any]] = []
    closed_splits: list[dict[str, Any]] = []
    survivors: list[dict[str, Any]] = []
    censored: list[dict[str, Any]] = []

    for index, target in enumerate(TARGETS):
        target_id = str(target["target_id"])
        upper_vector = tuple(map(int, target["upper"]))
        lower_vector = tuple(map(int, target["lower"]))
        hints = body_hint_for_vector(body_atlas, upper_vector)
        record: dict[str, Any] = {
            "target_id": target_id,
            "upper_template_vector": list(upper_vector),
            "lower_template_vector": list(lower_vector),
            "body_hint_count": len(hints),
        }

        upper_model = e105.build_nested_model(
            e095=e095,
            prepared=prepared,
            nested_side="upper",
            template_counts=count_map(upper_vector),
            body_hint_indices=hints,
            allocation_caps=global_counts,
        )
        upper = e105.solve_nested(
            upper_model,
            seconds=upper_seconds,
            seed=109100 + index,
        )
        upper_path = run_dir / f"{target_id}_UPPER_RESULT.json"
        dump_exclusive(upper_path, upper)
        record["upper"] = summarize_side(upper_path, upper)

        if upper["status"] == "INFEASIBLE":
            record["classification"] = "SPLIT_CLOSED_BY_UPPER_INFEASIBILITY"
            closed_splits.append(
                {
                    "target_id": target_id,
                    "upper": list(upper_vector),
                    "lower": list(lower_vector),
                    "decisive_side": "upper",
                    "decisive_path": display(upper_path),
                    "decisive_sha256": sha256_file(upper_path),
                }
            )
            records.append(record)
            continue
        if upper["status"] not in {"OPTIMAL", "FEASIBLE"}:
            record["classification"] = "SPLIT_CENSORED_AT_UPPER"
            censored.append(
                {
                    "target_id": target_id,
                    "side": "upper",
                    "status": upper["status"],
                    "path": display(upper_path),
                    "sha256": sha256_file(upper_path),
                }
            )
            records.append(record)
            continue

        lower_model = e105.build_nested_model(
            e095=e095,
            prepared=prepared,
            nested_side="lower",
            template_counts=count_map(lower_vector),
            body_hint_indices=hints,
            allocation_caps=global_counts,
        )
        lower = e105.solve_nested(
            lower_model,
            seconds=lower_seconds,
            seed=109200 + index,
        )
        lower_path = run_dir / f"{target_id}_LOWER_RESULT.json"
        dump_exclusive(lower_path, lower)
        record["lower"] = summarize_side(lower_path, lower)

        if lower["status"] == "INFEASIBLE":
            record["classification"] = "SPLIT_CLOSED_BY_LOWER_INFEASIBILITY"
            closed_splits.append(
                {
                    "target_id": target_id,
                    "upper": list(upper_vector),
                    "lower": list(lower_vector),
                    "decisive_side": "lower",
                    "decisive_path": display(lower_path),
                    "decisive_sha256": sha256_file(lower_path),
                }
            )
        elif lower["status"] in {"OPTIMAL", "FEASIBLE"}:
            record["classification"] = "SPLIT_INDIVIDUALLY_FRONT_FEASIBLE"
            survivors.append(
                {
                    "target_id": target_id,
                    "upper": list(upper_vector),
                    "lower": list(lower_vector),
                    "upper_allocation_tuple": upper["allocation_tuple"],
                    "lower_allocation_tuple": lower["allocation_tuple"],
                    "upper_path": display(upper_path),
                    "upper_sha256": sha256_file(upper_path),
                    "lower_path": display(lower_path),
                    "lower_sha256": sha256_file(lower_path),
                }
            )
        else:
            record["classification"] = "SPLIT_CENSORED_AT_LOWER"
            censored.append(
                {
                    "target_id": target_id,
                    "side": "lower",
                    "status": lower["status"],
                    "path": display(lower_path),
                    "sha256": sha256_file(lower_path),
                }
            )
        records.append(record)

    if len(closed_splits) == len(TARGETS):
        verdict = "RESERVED_Y60_TEMPLATE_PROJECTION_CLOSED"
        decision = "RESTORE_E103_EXPLICIT_Y59_SEPARATOR"
    elif survivors:
        verdict = "LAST_TWO_DISCRIMINATOR_HAS_TEMPLATE_SURVIVORS"
        decision = "RUN_ALLOCATION_HANDSHAKE_ON_SURVIVING_SPLITS"
    else:
        verdict = "LAST_TWO_TEMPLATE_SPLITS_CENSORED"
        decision = "REPLAY_ONLY_CENSORED_SPLIT_SIDES"

    result = {
        "schema": "zmd_e109_last_two_template_split_discriminator_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "upper_seconds_per_split": upper_seconds,
            "lower_seconds_per_split": lower_seconds,
            "source_isolated_helpers": True,
            "target_count": len(TARGETS),
        },
        "records": records,
        "closed_split_count": len(closed_splits),
        "closed_splits": closed_splits,
        "survivor_count": len(survivors),
        "survivors": survivors,
        "censored_count": len(censored),
        "censored": censored,
        "truth_boundary": (
            "Each exact side negative closes only its named template split under "
            "the source-stable manufacturing-free-y60 context. Individual side "
            "positives do not prove class-allocation compatibility. UNKNOWN creates no rule."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--upper-seconds", type=float, default=45.0)
    parser.add_argument("--lower-seconds", type=float, default=75.0)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            upper_seconds=float(args.upper_seconds),
            lower_seconds=float(args.lower_seconds),
        )
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "closed_split_count": result["closed_split_count"],
                    "survivor_count": result["survivor_count"],
                    "censored_count": result["censored_count"],
                    "records": [
                        {
                            "target_id": row["target_id"],
                            "classification": row["classification"],
                            "upper_status": row["upper"]["status"],
                            "lower_status": row.get("lower", {}).get("status"),
                        }
                        for row in result["records"]
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
            "schema": "zmd_e109_execution_failure_v1",
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
