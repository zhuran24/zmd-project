#!/usr/bin/env python3
"""E065: materialize source-stable E057-E062 replay results."""

from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E065_source_stable_replay_materialization/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
RECEIPT_PATH = OUT / "RESULT_RECEIPT.json"

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"

RUNNERS: dict[str, dict[str, Any]] = {
    "E057": {
        "source": EXPERIMENT_ROOT
        / "E057_qiaoyu_external_body_relation/run_e057.py",
        "output_dir": OUT / "e057-source",
        "patches": {
            "OUT": ".",
            "RESULT_PATH": "RESULT.json",
            "FAILURE_PATH": "FAILURE.json",
            "BEST_WITNESS_PATH": "BEST_JOINT_WITNESS.json",
            "BEST_ASSIGNMENT_PATH": "BEST_ASSIGNMENT.json",
            "BEST_LAYOUT_PATH": "BEST_LAYOUT.json",
        },
        "required": ("RESULT.json", "SOURCE_ORIGINS.json"),
        "old_result": ROOT
        / "research_lab/local/zero_condition/"
        "E057_qiaoyu_external_body_relation/run-004/RESULT.json",
        "old_sha256": "1cb96ea6785c0ded75f68f42f0d2d829e0a1c5bc6401b949710a9e524eb708c3",
    },
    "E058": {
        "source": EXPERIMENT_ROOT
        / "E058_all6x4_terminal_signature_frontier/run_e058.py",
        "output_dir": OUT / "e058-source",
        "patches": {
            "OUT": ".",
            "RESULT_PATH": "RESULT.json",
            "FAILURE_PATH": "FAILURE.json",
            "CENSUS_PATH": "SIGNATURE_CENSUS.json",
        },
        "required": (
            "RESULT.json",
            "SIGNATURE_CENSUS.json",
            "SOURCE_ORIGINS.json",
        ),
        "old_result": ROOT
        / "research_lab/local/zero_condition/"
        "E058_all6x4_terminal_signature_frontier/run-004/RESULT.json",
        "old_sha256": "d1295cd0988e751512968d1ad248f3e6da53ce912f52f6f28820f491c6fe27b4",
    },
    "E059": {
        "source": EXPERIMENT_ROOT
        / "E059_two_zero_tradeoff_certificate/run_e059.py",
        "output_dir": OUT / "e059-source",
        "patches": {
            "OUT": ".",
            "RESULT_PATH": "RESULT.json",
            "FAILURE_PATH": "FAILURE.json",
        },
        "required": ("RESULT.json", "SOURCE_ORIGINS.json"),
        "old_result": ROOT
        / "research_lab/local/zero_condition/"
        "E059_two_zero_tradeoff_certificate/run-001/RESULT.json",
        "old_sha256": "c1404d1b41b5b6dd3069b9692387d35ab5962bfee0d0b3dfcc0d970915c7daff",
    },
    "E060": {
        "source": EXPERIMENT_ROOT
        / "E060_generic_qiaoyu_sink_correction/run_e060.py",
        "output_dir": OUT / "e060-source",
        "patches": {
            "OUT": ".",
            "RESULT_PATH": "RESULT.json",
            "FAILURE_PATH": "FAILURE.json",
        },
        "required": ("RESULT.json", "SOURCE_ORIGINS.json"),
        "old_result": ROOT
        / "research_lab/local/zero_condition/"
        "E060_generic_qiaoyu_sink_correction/run-001/RESULT.json",
        "old_sha256": "feb697f506cb2ca2422c1d0e96a02250cb33afcaa21fc86fda939f6ce79409b8",
    },
    "E061": {
        "source": EXPERIMENT_ROOT
        / "E061_all_one_object_signature_frontier/run_e061.py",
        "output_dir": OUT / "e061-source",
        "patches": {
            "OUT": ".",
            "RESULT_PATH": "RESULT.json",
            "FAILURE_PATH": "FAILURE.json",
            "NON6_PATH": "NON6_SCAN.json",
            "SIX4_PATH": "SIX4_SCAN.json",
        },
        "required": (
            "RESULT.json",
            "NON6_SCAN.json",
            "SIX4_SCAN.json",
            "SOURCE_ORIGINS.json",
        ),
        "old_result": ROOT
        / "research_lab/local/zero_condition/"
        "E061_all_one_object_signature_frontier/run-001/RESULT.json",
        "old_sha256": "0559401660d99c69127c7f65f287900a6ca205b9f6bfce64b9e607d1dda785b2",
    },
    "E062": {
        "source": EXPERIMENT_ROOT
        / "E062_one_object_tradeoff_atlas/run_e062.py",
        "output_dir": OUT / "e062-source",
        "patches": {
            "OUT": ".",
            "RESULT_PATH": "RESULT.json",
            "FAILURE_PATH": "FAILURE.json",
            "NON6_PATH": "NON6_ATLAS.json",
            "SIX4_PATH": "SIX4_ATLAS.json",
        },
        "required": (
            "RESULT.json",
            "NON6_ATLAS.json",
            "SIX4_ATLAS.json",
            "SOURCE_ORIGINS.json",
        ),
        "old_result": ROOT
        / "research_lab/local/zero_condition/"
        "E062_one_object_tradeoff_atlas/run-001/RESULT.json",
        "old_sha256": "87141cbc5db98e45b69422d4b1b5e486d38c15a0dc6f677066b55b099108ff08",
    },
}

VOLATILE_KEYS = {
    "created_at_utc",
    "identity",
    "elapsed_seconds",
    "wall_time",
    "branches",
    "conflicts",
    "domain_build_seconds",
    "runner_sha256",
    "research_head",
    "tracked_status",
}

CHILD_BOOTSTRAP = r'''
from __future__ import annotations
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys

source = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
patches = json.loads(sys.argv[3])
module_name = "zmd_e065_" + source.parent.name + "_" + str(os.getpid())
spec = importlib.util.spec_from_file_location(module_name, source)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot import {source}")
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)

origins = []
foreign = []
for name, value in sorted(vars(module).items()):
    if not inspect.isfunction(value) or value.__module__ != module_name:
        continue
    actual = Path(value.__code__.co_filename).resolve()
    record = {"name": name, "code_filename": str(actual)}
    origins.append(record)
    if actual != source:
        foreign.append(record)
if foreign:
    raise RuntimeError(f"foreign module-level functions: {foreign}")

out.mkdir(parents=True, exist_ok=True)
origin_path = out / "SOURCE_ORIGINS.json"
origin_payload = {
    "schema": "zmd_zero_condition_e065_source_origins_v1",
    "source": str(source),
    "source_sha256": module.sha256_file(source),
    "function_count": len(origins),
    "foreign_function_count": len(foreign),
    "functions": origins,
}
origin_bytes = (
    json.dumps(
        origin_payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    + "\n"
).encode("utf-8")
if origin_path.exists():
    if origin_path.read_bytes() != origin_bytes:
        raise RuntimeError(f"source-origin receipt drift: {origin_path}")
else:
    with origin_path.open("xb") as handle:
        handle.write(origin_bytes)
        handle.flush()
        os.fsync(handle.fileno())

for name, relative in patches.items():
    setattr(module, name, out if relative == "." else out / relative)

raise SystemExit(int(module.main()))
'''


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    encoded = (
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def expected_env(source: Path) -> dict[str, str]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "EXPECTED_ENV"
            for target in node.targets
        ):
            continue
        value = ast.literal_eval(node.value)
        if not isinstance(value, dict) or not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in value.items()
        ):
            raise RuntimeError(f"invalid EXPECTED_ENV in {source}")
        return dict(value)
    raise RuntimeError(f"EXPECTED_ENV not found in {source}")


def required_paths(spec: Mapping[str, Any]) -> list[Path]:
    output_dir = Path(spec["output_dir"])
    return [output_dir / str(name) for name in spec["required"]]


def output_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def run_label(label: str) -> dict[str, Any]:
    spec = RUNNERS[label]
    source = Path(spec["source"])
    output_dir = Path(spec["output_dir"])
    paths = required_paths(spec)
    if all(path.is_file() for path in paths):
        origin = load_json(output_dir / "SOURCE_ORIGINS.json")
        if int(origin.get("foreign_function_count", -1)) != 0:
            raise RuntimeError(f"existing {label} source-origin receipt is not clean")
        return {
            "label": label,
            "status": "REUSED_COMPLETE",
            "source": output_record(source),
            "outputs": [output_record(path) for path in paths],
        }
    if output_dir.exists() and any(output_dir.iterdir()):
        existing = {path.name for path in output_dir.iterdir() if path.is_file()}
        allowed = {
            *(str(name) for name in spec["required"]),
            "FAILURE.json",
        }
        allowed.update(
            path.name for path in output_dir.glob("PROCESS_RECEIPT_*.json")
        )
        unknown = sorted(existing - allowed)
        if unknown:
            raise RuntimeError(
                f"partial E065 output directory has unknown files: {unknown}"
            )
        if (output_dir / "FAILURE.json").exists():
            raise RuntimeError(f"prior runner failure requires a new E065 run: {output_dir}")

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("EXACT_")
        and key not in {"PYTHONHASHSEED", "PYTHONPYCACHEPREFIX"}
    }
    env.update(expected_env(source))
    with tempfile.TemporaryDirectory(prefix=f"zmd_e065_{label.lower()}_") as cache:
        env["PYTHONPYCACHEPREFIX"] = cache
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                CHILD_BOOTSTRAP,
                str(source),
                str(output_dir),
                json.dumps(spec["patches"], sort_keys=True),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    process_receipt = {
        "schema": "zmd_zero_condition_e065_process_receipt_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "label": label,
        "source": output_record(source),
        "python": sys.executable,
        "returncode": int(completed.returncode),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "expected_env": expected_env(source),
        "ledger_effect": "none",
    }
    receipt_index = 1 + len(list(output_dir.glob("PROCESS_RECEIPT_*.json")))
    receipt_path = output_dir / f"PROCESS_RECEIPT_{receipt_index:03d}.json"
    dump_exclusive(receipt_path, process_receipt)
    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} source replay failed with exit {completed.returncode}: "
            f"{completed.stderr[-2000:]}"
        )
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"{label} source replay missing outputs: {missing}")
    origin = load_json(output_dir / "SOURCE_ORIGINS.json")
    if int(origin.get("foreign_function_count", -1)) != 0:
        raise RuntimeError(f"{label} source replay loaded foreign functions")
    return {
        "label": label,
        "status": "COMPLETED",
        "source": output_record(source),
        "process_receipt": output_record(receipt_path),
        "outputs": [output_record(path) for path in paths],
    }


def is_evidence_locator(key: str) -> bool:
    return key.endswith("_path") or key.endswith("_sha256")


def scientific_projection(value: Any) -> Any:
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, child in sorted(value.items()):
            text = str(key)
            if text in VOLATILE_KEYS or is_evidence_locator(text):
                continue
            output[text] = scientific_projection(child)
        return output
    if isinstance(value, list):
        return [scientific_projection(child) for child in value]
    return value


def verify_old_result(spec: Mapping[str, Any]) -> Mapping[str, Any]:
    path = Path(spec["old_result"])
    actual = sha256_file(path)
    expected = str(spec["old_sha256"])
    if actual != expected:
        raise RuntimeError(f"old result identity drift: {path}: {actual} != {expected}")
    return load_json(path)


def stable_result_record(
    label: str,
    old: Mapping[str, Any],
    fresh: Mapping[str, Any],
) -> dict[str, Any]:
    old_projection = scientific_projection(old)
    fresh_projection = scientific_projection(fresh)
    if old_projection != fresh_projection:
        raise RuntimeError(f"{label} scientific projection changed")
    digest = hashlib.sha256(
        json.dumps(
            old_projection,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "label": label,
        "status": "SCIENTIFIC_FIELDS_IDENTICAL",
        "verdict": old.get("verdict"),
        "decision": old.get("decision"),
        "scientific_projection_digest": digest,
    }


def normalized_pattern_set(payload: Mapping[str, Any]) -> list[str]:
    return sorted(
        json.dumps(
            scientific_projection(row),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for row in payload["patterns"]
    )


def optimization_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    projected = scientific_projection(payload)
    projected.pop("presence", None)
    return projected


def representative_difference(
    *,
    label: str,
    old: Mapping[str, Any],
    fresh: Mapping[str, Any],
) -> dict[str, Any] | None:
    old_presence = old.get("presence")
    fresh_presence = fresh.get("presence")
    if old_presence == fresh_presence:
        return None
    return {
        "label": label,
        "old_presence": old_presence,
        "fresh_presence": fresh_presence,
    }


def verify_e059(
    old: Mapping[str, Any],
    fresh: Mapping[str, Any],
) -> dict[str, Any]:
    for key in ("verdict", "decision"):
        if old.get(key) != fresh.get(key):
            raise RuntimeError(f"E059 source replay changed {key}")
    old_other = scientific_projection(old)
    fresh_other = scientific_projection(fresh)
    for payload in (old_other, fresh_other):
        payload.pop("tradeoffs", None)
        payload.pop("qiaoyu_hard_optimum_face", None)
    if old_other != fresh_other:
        raise RuntimeError("E059 non-tradeoff scientific fields changed")

    representative_differences: list[dict[str, Any]] = []
    old_tradeoffs = old["tradeoffs"]
    fresh_tradeoffs = fresh["tradeoffs"]
    if set(old_tradeoffs) != set(fresh_tradeoffs):
        raise RuntimeError("E059 tradeoff-arm set changed")
    for name in sorted(old_tradeoffs):
        if optimization_summary(old_tradeoffs[name]) != optimization_summary(
            fresh_tradeoffs[name]
        ):
            raise RuntimeError(f"E059 tradeoff arm changed: {name}")
        difference = representative_difference(
            label=name,
            old=old_tradeoffs[name],
            fresh=fresh_tradeoffs[name],
        )
        if difference is not None:
            representative_differences.append(difference)

    old_face = old["qiaoyu_hard_optimum_face"]
    fresh_face = fresh["qiaoyu_hard_optimum_face"]
    for key in (
        "common_sink_components",
        "common_source_components",
        "exact_relaxed_pattern_sets_equal",
        "sink_only_component_class",
        "source_only_component_class",
    ):
        if old_face.get(key) != fresh_face.get(key):
            raise RuntimeError(f"E059 optimum-face field changed: {key}")
    face_digests: dict[str, str] = {}
    for arm in ("exact", "relaxed"):
        old_arm = old_face[arm]
        fresh_arm = fresh_face[arm]
        for key in ("status", "complete", "pattern_count"):
            if old_arm.get(key) != fresh_arm.get(key):
                raise RuntimeError(f"E059 {arm} face changed: {key}")
        old_patterns = normalized_pattern_set(old_arm)
        fresh_patterns = normalized_pattern_set(fresh_arm)
        if old_patterns != fresh_patterns:
            raise RuntimeError(f"E059 {arm} optimum-face pattern set changed")
        face_digests[arm] = hashlib.sha256(
            "\n".join(old_patterns).encode("utf-8")
        ).hexdigest()
    return {
        "label": "E059",
        "status": "OBJECTIVES_AND_COMPLETE_FACE_IDENTICAL",
        "verdict": fresh.get("verdict"),
        "decision": fresh.get("decision"),
        "face_pattern_set_digests": face_digests,
        "representative_difference_count": len(representative_differences),
        "representative_differences": representative_differences,
    }


def repair_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "feasible_filling_components": payload["feasible_filling_components"],
        "feasible_grinder_components": payload["feasible_grinder_components"],
        "filling": sorted(
            (int(row["component"]), str(row["status"]))
            for row in payload["filling_capsule"]
        ),
        "grinder": sorted(
            (int(row["component"]), str(row["status"]))
            for row in payload["grinder_fine_buckwheat"]
        ),
    }


def verify_e060(
    old: Mapping[str, Any],
    fresh: Mapping[str, Any],
) -> dict[str, Any]:
    for key in ("verdict", "decision"):
        if old.get(key) != fresh.get(key):
            raise RuntimeError(f"E060 source replay changed {key}")
    old_other = scientific_projection(old)
    fresh_other = scientific_projection(fresh)
    for payload in (old_other, fresh_other):
        payload.pop("arms", None)
        payload.pop("qiaoyu_hard_optimum_face", None)
        payload.pop("single_signature_repairs", None)
    if old_other != fresh_other:
        raise RuntimeError("E060 non-arm scientific fields changed")

    representative_differences: list[dict[str, Any]] = []
    old_arms = old["arms"]
    fresh_arms = fresh["arms"]
    if set(old_arms) != set(fresh_arms):
        raise RuntimeError("E060 arm set changed")
    for name in sorted(old_arms):
        if optimization_summary(old_arms[name]) != optimization_summary(
            fresh_arms[name]
        ):
            raise RuntimeError(f"E060 arm changed: {name}")
        difference = representative_difference(
            label=name,
            old=old_arms[name],
            fresh=fresh_arms[name],
        )
        if difference is not None:
            representative_differences.append(difference)

    old_face = old["qiaoyu_hard_optimum_face"]
    fresh_face = fresh["qiaoyu_hard_optimum_face"]
    for key in (
        "all_selected_sink_components",
        "common_sink_components",
        "common_source_components",
        "exact_relaxed_pattern_sets_equal",
        "sink_only_component_class",
        "source_only_component_class",
    ):
        if old_face.get(key) != fresh_face.get(key):
            raise RuntimeError(f"E060 optimum-face field changed: {key}")
    face_digests: dict[str, str] = {}
    for arm in ("exact", "relaxed"):
        old_arm = old_face[arm]
        fresh_arm = fresh_face[arm]
        for key in ("status", "complete", "pattern_count"):
            if old_arm.get(key) != fresh_arm.get(key):
                raise RuntimeError(f"E060 {arm} face changed: {key}")
        old_patterns = normalized_pattern_set(old_arm)
        fresh_patterns = normalized_pattern_set(fresh_arm)
        if old_patterns != fresh_patterns:
            raise RuntimeError(f"E060 {arm} optimum-face pattern set changed")
        face_digests[arm] = hashlib.sha256(
            "\n".join(old_patterns).encode("utf-8")
        ).hexdigest()
    if repair_summary(old["single_signature_repairs"]) != repair_summary(
        fresh["single_signature_repairs"]
    ):
        raise RuntimeError("E060 synthetic repair outcomes changed")
    return {
        "label": "E060",
        "status": "OBJECTIVES_AND_COMPLETE_FACE_IDENTICAL",
        "verdict": fresh.get("verdict"),
        "decision": fresh.get("decision"),
        "face_pattern_set_digests": face_digests,
        "representative_difference_count": len(representative_differences),
        "representative_differences": representative_differences,
    }


def improvement_identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    tradeoff = dict(row["tradeoff"])
    return (
        str(row["source_instance_id"]),
        str(row["facility_type"]),
        int(row["current_pose_idx"]),
        int(row["replacement_pose_idx"]),
        str(row["replacement_pose_id"]),
        int(row.get("alias_count", 0)),
        str(tradeoff["status"]),
        int(tradeoff["objective"]),
    )


def atlas_projection(atlas: Mapping[str, Any]) -> dict[str, Any]:
    projected = scientific_projection(atlas)
    projected.pop("strict_improvements", None)
    projected.pop("nonterminal_candidates", None)
    return projected


def verify_e062(
    old: Mapping[str, Any],
    fresh: Mapping[str, Any],
) -> dict[str, Any]:
    for key in (
        "verdict",
        "decision",
        "total_objective_distribution",
        "strict_improvement_count",
        "nonterminal_count",
    ):
        if old.get(key) != fresh.get(key):
            raise RuntimeError(f"E062 source replay changed {key}")
    if atlas_projection(old["non6_atlas"]) != atlas_projection(
        fresh["non6_atlas"]
    ):
        raise RuntimeError("E062 non6 atlas changed outside representatives")
    if atlas_projection(old["six4_atlas"]) != atlas_projection(
        fresh["six4_atlas"]
    ):
        raise RuntimeError("E062 six4 atlas changed outside representatives")

    old_rows = sorted(old["strict_improvements"], key=improvement_identity)
    fresh_rows = sorted(fresh["strict_improvements"], key=improvement_identity)
    old_ids = [improvement_identity(row) for row in old_rows]
    fresh_ids = [improvement_identity(row) for row in fresh_rows]
    if old_ids != fresh_ids or len(old_ids) != 5:
        raise RuntimeError("E062 physical near-miss identities changed")

    representative_differences: list[dict[str, Any]] = []
    unchanged_representatives: list[dict[str, Any]] = []
    for old_row, fresh_row in zip(old_rows, fresh_rows, strict=True):
        identity = improvement_identity(old_row)
        old_presence = dict(old_row["tradeoff"]["presence"])
        fresh_presence = dict(fresh_row["tradeoff"]["presence"])
        record = {
            "source_instance_id": identity[0],
            "facility_type": identity[1],
            "current_pose_idx": identity[2],
            "replacement_pose_idx": identity[3],
            "replacement_pose_id": identity[4],
            "objective": identity[-1],
            "old_presence": old_presence,
            "fresh_presence": fresh_presence,
        }
        if old_presence == fresh_presence:
            unchanged_representatives.append(record)
        else:
            representative_differences.append(record)
    return {
        "status": "PHYSICAL_AND_OBJECTIVE_FRONTIER_IDENTICAL",
        "verdict": fresh.get("verdict"),
        "decision": fresh.get("decision"),
        "objective_distribution": fresh["total_objective_distribution"],
        "near_miss_count": len(fresh_rows),
        "representative_difference_count": len(representative_differences),
        "representative_differences": representative_differences,
        "unchanged_representatives": unchanged_representatives,
        "warning": (
            "A selected optimum-face presence witness is not the complete face and "
            "must not be used as E063's sole causal component."
        ),
    }


def verify_all() -> dict[str, Any]:
    if RESULT_PATH.exists() or RECEIPT_PATH.exists():
        raise FileExistsError("refusing to overwrite E065 terminal outputs")
    replay_records: list[dict[str, Any]] = []
    old_results: dict[str, Mapping[str, Any]] = {}
    fresh_results: dict[str, Mapping[str, Any]] = {}
    checked_hashes: dict[str, dict[str, str]] = {}
    for label, spec in RUNNERS.items():
        paths = required_paths(spec)
        missing = [path for path in paths if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"{label} replay incomplete: {missing}")
        origin = load_json(Path(spec["output_dir"]) / "SOURCE_ORIGINS.json")
        if int(origin.get("foreign_function_count", -1)) != 0:
            raise RuntimeError(f"{label} replay origin audit is not clean")
        old = verify_old_result(spec)
        fresh_path = Path(spec["output_dir"]) / "RESULT.json"
        fresh = load_json(fresh_path)
        old_results[label] = old
        fresh_results[label] = fresh
        checked_hashes[label] = {
            "old": str(spec["old_sha256"]),
            "fresh": sha256_file(fresh_path),
        }
        replay_records.append(
            {
                "label": label,
                "source": output_record(Path(spec["source"])),
                "origin_receipt": output_record(
                    Path(spec["output_dir"]) / "SOURCE_ORIGINS.json"
                ),
                "result": output_record(fresh_path),
            }
        )

    stable = [
        stable_result_record(label, old_results[label], fresh_results[label])
        for label in ("E057", "E058", "E061")
    ]
    stable.extend(
        [
            verify_e059(old_results["E059"], fresh_results["E059"]),
            verify_e060(old_results["E060"], fresh_results["E060"]),
        ]
    )
    e062 = verify_e062(old_results["E062"], fresh_results["E062"])
    result = {
        "schema": "zmd_zero_condition_e065_source_stable_replay_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": "SOURCE_STABLE_REPLAY_SET_MATERIALIZED",
        "decision": "USE_E065_E062_RESULT_FOR_COMPLETE_FACE_E063",
        "checked_result_hashes": checked_hashes,
        "replay_records": replay_records,
        "stable_results": stable,
        "e062": e062,
        "truth_boundary": (
            "Fresh-cache source executions of the frozen E057-E062 research models. "
            "E057-E061 are compared after removing runtime-only fields; E062's "
            "physical/objective frontier is separated from arbitrary optimum-face "
            "representatives. The historical cause of E064's missing local artifacts "
            "is not established."
        ),
        "ledger_effect": "none",
    }
    dump_exclusive(RESULT_PATH, result)
    dump_exclusive(
        RECEIPT_PATH,
        {
            "schema": "zmd_zero_condition_e065_result_receipt_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "result_path": str(RESULT_PATH.relative_to(ROOT)),
            "result_sha256": sha256_file(RESULT_PATH),
            "runner_path": str(Path(__file__).resolve().relative_to(ROOT)),
            "runner_sha256": sha256_file(Path(__file__).resolve()),
            "fresh_results": checked_hashes,
            "ledger_effect": "none",
        },
    )
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument(
        "--label",
        choices=tuple(RUNNERS),
        help="materialize one source-stable replay",
    )
    value.add_argument(
        "--verify",
        action="store_true",
        help="compare all completed replays and write the terminal result",
    )
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if bool(args.label) == bool(args.verify):
        raise SystemExit("choose exactly one of --label or --verify")
    if args.label:
        record = run_label(str(args.label))
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))
        return 0
    result = verify_all()
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "stable": [row["label"] for row in result["stable_results"]],
                "e062_representative_differences": result["e062"][
                    "representative_difference_count"
                ],
                "result_path": str(RESULT_PATH),
                "result_sha256": sha256_file(RESULT_PATH),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
