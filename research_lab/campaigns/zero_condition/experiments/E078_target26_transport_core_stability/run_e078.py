#!/usr/bin/env python3
"""E078: test target-26 semantic transport-core stability on the frozen parent face."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Iterable, Mapping

ROOT = Path("/home/zhuran24/zmd-research")
EXPERIMENT_DIR = ROOT / "research_lab/campaigns/zero_condition/experiments/E078_target26_transport_core_stability"
DEFAULT_RUN_DIR = ROOT / "research_lab/local/zero_condition/E078_target26_transport_core_stability/run-003"
PROJECT_PYTHON = Path("/home/zhuran24/zmd-pj/.venv/bin/python")

PROBES = (
    ("support_neighbors", EXPERIMENT_DIR / "probe_support_neighbors.py"),
    ("one_option_neighbors", EXPERIMENT_DIR / "probe_one_option_neighbors.py"),
    ("core_touch", EXPERIMENT_DIR / "probe_core_touch.py"),
    ("universal_rewrite", EXPERIMENT_DIR / "probe_universal_rewrite.py"),
)

PINNED_INPUTS = {
    "e069_result": ROOT / "research_lab/local/zero_condition/E069_six4_near_miss_complete_face/run-001/RESULT.json",
    "e069_parent_solution": ROOT / "research_lab/local/zero_condition/E069_six4_near_miss_complete_face/run-001/PARENT_SOLUTION.json",
    "e069_face_context": ROOT / "research_lab/local/zero_condition/E069_six4_near_miss_complete_face/run-001/FACE_CONTEXT.json",
    "e070_result": ROOT / "research_lab/local/zero_condition/E070_dual_filling_signature_targets/run-004/RESULT.json",
    "e074_result": ROOT / "research_lab/local/zero_condition/E074_minimum_assignment_transport_core/run-001/RESULT.json",
    "e074_atlas": ROOT / "research_lab/local/zero_condition/E074_minimum_assignment_transport_core/run-001/TRANSPORT_CORE_ATLAS.json",
    "e074_target26": ROOT / "research_lab/local/zero_condition/E074_minimum_assignment_transport_core/run-001/TARGET_026_TRANSPORT.json",
}

EXPECTED_INPUT_SHA256 = {
    "e069_result": "cc16d6f308856201cfe06d85617290481ecde85815e5c83f1d9a4acbeb4efcaa",
    "e069_parent_solution": "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    "e069_face_context": "c05a4e94ea370e8b674e44cd7206a9189ddd2102b824d36acd65975395c46c3e",
    "e070_result": "e15599c5c967cdc5ab74fb755b41d32cb476d68544a1f09b0b4c8be57a1829ed",
    "e074_result": "e3e59cc773b88f033d754a97ec16e28e9e18980c9f02b55ab8980851b95fa7c9",
    "e074_atlas": "b1e7e2b4ad9b4d01e185a644c534e6528343cf1eba1be7d79f678dc6867ad459",
    "e074_target26": "609e0be6613f27531e9a24bc757b3dbeb7574d6422e9eb55615cf117d74658f4",
}

EXPECTED_CORE_BODY_IDS = (
    "grinder_dense_source_001",
    "grinder_fine_buckwheat_002",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parse_last_json(stdout: str, *, label: str) -> Mapping[str, Any]:
    for raw_line in reversed(stdout.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, Mapping):
            return dict(value)
    raise RuntimeError(f"{label} emitted no terminal JSON object")


def run_probe(*, name: str, path: Path, run_dir: Path) -> dict[str, Any]:
    cache_dir = run_dir / "pycache" / name
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPYCACHEPREFIX"] = str(cache_dir)
    started = time.monotonic()
    completed = subprocess.run(
        [str(PROJECT_PYTHON), str(path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    elapsed = time.monotonic() - started
    payload = parse_last_json(completed.stdout, label=name)
    if completed.returncode != 0:
        raise RuntimeError(
            f"{name} failed rc={completed.returncode}: "
            f"stdout_tail={completed.stdout[-2000:]!r} stderr_tail={completed.stderr[-2000:]!r}"
        )
    return {
        "name": name,
        "source": str(path.relative_to(ROOT)),
        "source_sha256": sha256_file(path),
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode("utf-8")).hexdigest(),
        "terminal": dict(payload),
    }


def walk_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from walk_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_mappings(child)


def extract_stable_body_witnesses(target26: Any) -> list[dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in walk_mappings(target26):
        instance_id = row.get("source_instance_id")
        if instance_id not in EXPECTED_CORE_BODY_IDS:
            continue
        compact = {
            key: row[key]
            for key in (
                "source_instance_id",
                "body_digest",
                "occupied_cells_digest",
                "operation",
                "current_operation",
                "destination",
                "pose_idx",
            )
            if key in row
        }
        current = output.get(str(instance_id))
        if current is None or len(compact) > len(current):
            output[str(instance_id)] = compact
    missing = sorted(set(EXPECTED_CORE_BODY_IDS) - set(output))
    if missing:
        raise RuntimeError(f"E078 stable body witnesses missing from E074 target26: {missing}")
    return [output[instance_id] for instance_id in EXPECTED_CORE_BODY_IDS]


def require_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"E078 expected integer {key}, got {value!r}")
    return int(value)


def classify(probe_results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    support = probe_results["support_neighbors"]["terminal"]
    one_option = probe_results["one_option_neighbors"]["terminal"]
    core_touch = probe_results["core_touch"]["terminal"]
    universal = probe_results["universal_rewrite"]["terminal"]

    raw_alternatives = require_int(one_option, "raw_one_option_alternative_count")
    valid_neighbors = require_int(one_option, "valid_one_option_neighbor_count")
    valid_destinations = require_int(one_option, "valid_destination_support_count")
    anomaly_count = require_int(one_option, "anomaly_count")

    primary_status_counts = {
        str(key): int(value)
        for key, value in dict(
            one_option.get("transport_primary_status_counts", {})
        ).items()
    }
    core_size_distribution = {
        str(key): int(value)
        for key, value in dict(
            one_option.get("transport_core_size_distribution", {})
        ).items()
    }
    reference_support_status_counts = {
        str(key): int(value)
        for key, value in dict(
            one_option.get("reference_support_status_counts", {})
        ).items()
    }
    alternate_support_status_counts = {
        str(key): int(value)
        for key, value in dict(
            one_option.get("alternate_support_status_counts", {})
        ).items()
    }
    alternate_synthetic_status_counts = {
        str(key): int(value)
        for key, value in dict(
            one_option.get("alternate_synthetic_status_counts", {})
        ).items()
    }
    selected_support_counts = {
        str(key): int(value)
        for key, value in dict(one_option.get("selected_support_counts", {})).items()
    }
    selected_synthetic_counts = {
        str(key): int(value)
        for key, value in dict(
            one_option.get("selected_synthetic_destination_counts", {})
        ).items()
    }

    neighbor_exact = (
        str(one_option.get("status")) == "OPTIMAL"
        and raw_alternatives == 168
        and valid_neighbors == 25
        and valid_destinations == 25
        and anomaly_count == 0
        and primary_status_counts == {"OPTIMAL": 25}
        and core_size_distribution == {"2": 25}
        and reference_support_status_counts == {"OPTIMAL": 25}
        and selected_support_counts == {"8,9": 25}
        and selected_synthetic_counts == {"9": 25}
    )
    minimum_core_nonunique = (
        alternate_support_status_counts == {"OPTIMAL": 25}
        and alternate_synthetic_status_counts == {"OPTIMAL": 25}
    )

    core_touch_closed = (
        str(core_touch.get("status")) == "INFEASIBLE"
        and core_touch.get("core_touch_parent_exists") is False
        and str(core_touch.get("verdict"))
        == "NO_PARENT_FACE_ASSIGNMENT_CHANGES_REFERENCE_CORE_ROWS"
    )

    universal_status = str(universal.get("status"))
    universal_no_counterexample = (
        universal_status == "INFEASIBLE"
        and universal.get("counterexample_found") is False
        and str(universal.get("verdict"))
        == "NO_PARENT_FACE_COUNTEREXAMPLE_TO_REFERENCE_REWRITE"
    )

    support_consistent = (
        str(support.get("status")) == "OPTIMAL"
        and support.get("enumeration_terminal") == "EXHAUSTED"
        and int(support.get("neighbor_support_count", -1)) == 25
        and dict(support.get("transport_primary_status_counts", {}))
        == {"OPTIMAL": 25}
        and {
            str(key): int(value)
            for key, value in dict(
                support.get("transport_core_size_distribution", {})
            ).items()
        }
        == {"2": 25}
        and dict(support.get("reference_support_status_counts", {}))
        == {"OPTIMAL": 25}
    )

    reference_rewrite_stable = (
        neighbor_exact
        and core_touch_closed
        and universal_no_counterexample
        and support_consistent
    )
    return {
        "raw_one_option_alternative_count": raw_alternatives,
        "valid_one_option_neighbor_count": valid_neighbors,
        "valid_destination_support_count": valid_destinations,
        "one_option_anomaly_count": anomaly_count,
        "one_option_primary_status_counts": primary_status_counts,
        "one_option_core_size_distribution": core_size_distribution,
        "one_option_reference_support_status_counts": reference_support_status_counts,
        "one_option_alternate_support_status_counts": alternate_support_status_counts,
        "one_option_alternate_synthetic_status_counts": alternate_synthetic_status_counts,
        "one_option_selected_support_counts": selected_support_counts,
        "one_option_selected_synthetic_destination_counts": selected_synthetic_counts,
        "minimum_core_is_nonunique": minimum_core_nonunique,
        "core_touch_status": core_touch.get("status"),
        "core_touch_parent_exists": core_touch.get("core_touch_parent_exists"),
        "universal_rewrite_status": universal_status,
        "universal_counterexample_found": universal.get("counterexample_found"),
        "neighbor_layer_exact": neighbor_exact,
        "core_rows_frozen_on_parent_face": core_touch_closed,
        "reference_rewrite_has_no_parent_face_counterexample": universal_no_counterexample,
        "support_neighbor_layer_exact": support_consistent,
        "reference_rewrite_stable_on_full_parent_face": reference_rewrite_stable,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    input_identity: dict[str, dict[str, Any]] = {}
    for name, path in PINNED_INPUTS.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        expected = EXPECTED_INPUT_SHA256[name]
        if actual != expected:
            raise RuntimeError(
                f"E078 input identity drift for {name}: expected={expected} actual={actual}"
            )
        input_identity[name] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": actual,
            "bytes": path.stat().st_size,
        }

    probe_results: dict[str, dict[str, Any]] = {}
    for name, path in PROBES:
        probe_results[name] = run_probe(name=name, path=path, run_dir=run_dir)

    classification = classify(probe_results)
    target26 = load_json(PINNED_INPUTS["e074_target26"])
    stable_body_witnesses = extract_stable_body_witnesses(target26)

    atlas = {
        "schema": "zmd_e078_transport_core_stability_atlas_v1",
        "created_at_utc": utc_now(),
        "scope": "frozen_E069_target26_terminal_signature_parent_face",
        "input_identity": input_identity,
        "probe_results": probe_results,
        "classification": classification,
        "stable_body_witnesses": stable_body_witnesses,
        "local_handle_notice": (
            "Destination rows 8 and 9 are frozen-context handles only. Cross-context "
            "consumers must remap the stable body witnesses and verify uniqueness."
        ),
    }
    atlas_path = run_dir / "STABILITY_ATLAS.json"
    atomic_json(atlas_path, atlas)
    atlas_sha256 = sha256_file(atlas_path)

    stable = classification["reference_rewrite_stable_on_full_parent_face"]
    nonunique = classification["minimum_core_is_nonunique"]
    verdict = (
        "TARGET26_REFERENCE_TWO_ROW_REWRITE_STABLE_ON_FULL_FROZEN_PARENT_FACE_BUT_MINIMUM_CORES_NONUNIQUE"
        if stable and nonunique
        else "TARGET26_REFERENCE_TWO_ROW_REWRITE_STABLE_ON_FULL_FROZEN_PARENT_FACE"
        if stable
        else "TARGET26_TRANSPORT_REWRITE_STABILITY_REFUTED_OR_NONTERMINAL"
    )
    decision = (
        "KEEP_REFERENCE_REWRITE_AS_CONSTRUCTIVE_SPEC_DO_NOT_PROMOTE_UNIQUE_CORE_TEST_CROSS_GEOMETRY_AND_PHYSICAL_REALIZATION"
        if stable and nonunique
        else "FOLD_TARGET26_INTO_CUT_DEFICIENCY_AND_TEST_PHYSICAL_REALIZATION"
        if stable
        else "INSPECT_COUNTEREXAMPLE_AND_NARROW_TRANSPORT_CORE_CLAIM"
    )
    result = {
        "schema": "zmd_e078_transport_core_stability_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "scope": {
            "geometry": "E069 frozen occupied geometry",
            "target": 26,
            "model": "terminal-signature abstraction with one synthetic dual filling option",
            "nonclaims": [
                "no physical pose realization",
                "no full binding",
                "no routing or throughput",
                "no cross-geometry stability theorem",
                "no certified master cut",
            ],
        },
        "classification": classification,
        "reference_rewrite": {
            "local_destination_handles": [8, 9],
            "stable_body_witnesses": stable_body_witnesses,
            "minimum_changed_row_count": 2,
            "minimum_core_unique": not nonunique,
            "interpretation": (
                "The rows 8/9 rewrite is a stable full-face constructive specification, "
                "but other minimum two-row supports and synthetic destinations also exist."
            ),
        },
        "input_identity": input_identity,
        "runner": {
            "path": str(Path(__file__).resolve().relative_to(ROOT)),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "probe_sources": {
            name: {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
            }
            for name, path in PROBES
        },
        "stability_atlas_path": str(atlas_path.relative_to(ROOT)),
        "stability_atlas_sha256": atlas_sha256,
        "truth_boundary": (
            "This result is confined to the complete target-26 parent face under the "
            "frozen E069 geometry and terminal-signature abstraction. It establishes one "
            "stable reference two-row rewrite, not a unique minimum transport core. It "
            "proves neither physical realizability nor stability after geometry, component, "
            "body, mode, binding, or routing context changes. Stable witnesses, not local "
            "row or component numbers, are the transportable objects."
        ),
    }
    result["result_digest"] = stable_digest(result)
    result_path = run_dir / "RESULT.json"
    atomic_json(result_path, result)
    receipt = {
        "schema": "zmd_e078_transport_core_stability_receipt_v1",
        "result_path": str(result_path.relative_to(ROOT)),
        "result_sha256": sha256_file(result_path),
        "stability_atlas_sha256": atlas_sha256,
        "verdict": verdict,
        "decision": decision,
    }
    atomic_json(run_dir / "RESULT_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
