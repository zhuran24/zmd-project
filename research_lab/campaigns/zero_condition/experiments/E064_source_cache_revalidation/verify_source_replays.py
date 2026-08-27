#!/usr/bin/env python3
"""Verify source-isolated E057-E062 replays and freeze the E062 correction."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
LOCAL = ROOT / "research_lab/local/zero_condition/E064_source_cache_revalidation"
OUTPUT = LOCAL / "RESULT.json"
RECEIPT = LOCAL / "RESULT_RECEIPT.json"
DEFAULT_ORIGINS = LOCAL / "DEFAULT_ORIGINS.json"
FRESH_ORIGINS = LOCAL / "FRESH_ORIGINS.json"

RESULT_PAIRS: dict[str, tuple[Path, Path, str, str]] = {
    "E057": (
        ROOT
        / "research_lab/local/zero_condition/E057_qiaoyu_external_body_relation/"
        "run-004/RESULT.json",
        LOCAL / "e057-source/RESULT.json",
        "1cb96ea6785c0ded75f68f42f0d2d829e0a1c5bc6401b949710a9e524eb708c3",
        "b1bc0f99d479ecf4430374c7dacbc62227db832e017cf6469f3c22ef4027e763",
    ),
    "E058": (
        ROOT
        / "research_lab/local/zero_condition/"
        "E058_all6x4_terminal_signature_frontier/run-004/RESULT.json",
        LOCAL / "e058-source/RESULT.json",
        "d1295cd0988e751512968d1ad248f3e6da53ce912f52f6f28820f491c6fe27b4",
        "3f77839b71adaf3e183c9a857a1158e43726f6380db081082d6a8e470524917b",
    ),
    "E059": (
        ROOT
        / "research_lab/local/zero_condition/E059_two_zero_tradeoff_certificate/"
        "run-001/RESULT.json",
        LOCAL / "e059-source/RESULT.json",
        "c1404d1b41b5b6dd3069b9692387d35ab5962bfee0d0b3dfcc0d970915c7daff",
        "c3afb92e46c3ebad534fbda403b3c0c171362b7fae38844f43d5f75a3f743652",
    ),
    "E060": (
        ROOT
        / "research_lab/local/zero_condition/"
        "E060_generic_qiaoyu_sink_correction/run-001/RESULT.json",
        LOCAL / "e060-source/RESULT.json",
        "feb697f506cb2ca2422c1d0e96a02250cb33afcaa21fc86fda939f6ce79409b8",
        "6527eb4d78772458f5925c16b96b322fb360959cae165b0c8a2d41b6e59f8e7f",
    ),
    "E061": (
        ROOT
        / "research_lab/local/zero_condition/"
        "E061_all_one_object_signature_frontier/run-001/RESULT.json",
        LOCAL / "e061-source/RESULT.json",
        "0559401660d99c69127c7f65f287900a6ca205b9f6bfce64b9e607d1dda785b2",
        "f9b858659695fa3ccb822779dd947db15acbb306e1440865bd5416c325cb2a88",
    ),
    "E062": (
        ROOT
        / "research_lab/local/zero_condition/E062_one_object_tradeoff_atlas/"
        "run-001/RESULT.json",
        LOCAL / "e062-source/RESULT.json",
        "87141cbc5db98e45b69422d4b1b5e486d38c15a0dc6f677066b55b099108ff08",
        "cb4bc810696b1ffaa70fa0af5a3fc6554f8e86566cef465cbacf57a12530e055",
    ),
}

VOLATILE_KEYS = {
    "created_at_utc",
    "identity",
    "elapsed_seconds",
    "wall_time",
    "branches",
    "conflicts",
    "runner_sha256",
    "research_head",
    "tracked_status",
}


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


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    encoded = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


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


def verify_hash(path: Path, expected: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(f"frozen identity drift: {path}: {actual} != {expected}")
    return actual


def verify_origin_audits() -> dict[str, Any]:
    default = load(DEFAULT_ORIGINS)
    fresh = load(FRESH_ORIGINS)
    if int(default.get("foreign_function_count", 0)) <= 0:
        raise RuntimeError("default-cache origin audit did not reproduce contamination")
    if int(fresh.get("foreign_function_count", -1)) != 0:
        raise RuntimeError("fresh-cache origin audit still contains foreign functions")
    default_counts = {
        str(row["label"]): int(row["foreign_function_count"])
        for row in default["audits"]
    }
    fresh_counts = {
        str(row["label"]): int(row["foreign_function_count"])
        for row in fresh["audits"]
    }
    if set(default_counts) != set(RESULT_PAIRS) or set(fresh_counts) != set(
        RESULT_PAIRS
    ):
        raise RuntimeError("origin-audit runner coverage drift")
    if any(value != 0 for value in fresh_counts.values()):
        raise RuntimeError(f"fresh origin counts are nonzero: {fresh_counts}")
    return {
        "default_path": str(DEFAULT_ORIGINS.relative_to(ROOT)),
        "default_sha256": sha256_file(DEFAULT_ORIGINS),
        "default_foreign_function_count": int(default["foreign_function_count"]),
        "default_counts_by_runner": default_counts,
        "fresh_path": str(FRESH_ORIGINS.relative_to(ROOT)),
        "fresh_sha256": sha256_file(FRESH_ORIGINS),
        "fresh_foreign_function_count": int(fresh["foreign_function_count"]),
        "fresh_counts_by_runner": fresh_counts,
    }


def verify_stable_result(
    label: str,
    old: Mapping[str, Any],
    fresh: Mapping[str, Any],
) -> dict[str, Any]:
    old_projection = scientific_projection(old)
    fresh_projection = scientific_projection(fresh)
    if old_projection != fresh_projection:
        raise RuntimeError(f"{label} scientific projection changed under source replay")
    return {
        "label": label,
        "verdict": old.get("verdict"),
        "decision": old.get("decision"),
        "scientific_projection_digest": hashlib.sha256(
            json.dumps(
                old_projection,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "status": "SCIENTIFIC_FIELDS_IDENTICAL",
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


def presence(row: Mapping[str, Any]) -> dict[str, Any]:
    return dict(row["tradeoff"]["presence"])


def atlas_projection(atlas: Mapping[str, Any]) -> dict[str, Any]:
    projected = scientific_projection(atlas)
    projected.pop("strict_improvements", None)
    projected.pop("nonterminal_candidates", None)
    return projected


def verify_e062_correction(
    old: Mapping[str, Any],
    fresh: Mapping[str, Any]
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
        raise RuntimeError("E062 non6 atlas changed outside witness representatives")
    if atlas_projection(old["six4_atlas"]) != atlas_projection(
        fresh["six4_atlas"]
    ):
        raise RuntimeError("E062 6x4 atlas changed outside witness representatives")

    old_rows = sorted(old["strict_improvements"], key=improvement_identity)
    fresh_rows = sorted(fresh["strict_improvements"], key=improvement_identity)
    old_ids = [improvement_identity(row) for row in old_rows]
    fresh_ids = [improvement_identity(row) for row in fresh_rows]
    if old_ids != fresh_ids or len(old_ids) != 5:
        raise RuntimeError("E062 physical near-miss identities changed")

    corrections: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []
    for old_row, fresh_row in zip(old_rows, fresh_rows, strict=True):
        identity = improvement_identity(old_row)
        old_presence = presence(old_row)
        fresh_presence = presence(fresh_row)
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
            unchanged.append(record)
        else:
            corrections.append(record)

    if len(corrections) != 4 or len(unchanged) != 1:
        raise RuntimeError(
            "E062 representative correction cardinality drift: "
            f"corrected={len(corrections)} unchanged={len(unchanged)}"
        )
    for row in corrections:
        if row["facility_type"] != "power_pole":
            raise RuntimeError("E062 corrected representative is not a pole state")
        old_presence = row["old_presence"]
        fresh_presence = row["fresh_presence"]
        if (
            old_presence.get("source_only_components") != [1]
            or fresh_presence.get("source_only_components") != [4]
            or old_presence.get("sink_only_components") != []
            or fresh_presence.get("sink_only_components") != []
            or int(old_presence.get("qiaoyu_sink_component", -1)) != 15
            or int(fresh_presence.get("qiaoyu_sink_component", -1)) != 15
        ):
            raise RuntimeError(f"unexpected E062 pole correction: {row}")
    if unchanged[0]["facility_type"] != "manufacturing_6x4":
        raise RuntimeError("E062 unchanged near miss is not the 6x4 state")

    return {
        "label": "E062",
        "verdict": fresh.get("verdict"),
        "decision": fresh.get("decision"),
        "objective_distribution": fresh.get("total_objective_distribution"),
        "physical_near_miss_count": len(fresh_rows),
        "corrected_representative_count": len(corrections),
        "unchanged_representative_count": len(unchanged),
        "corrected_representatives": corrections,
        "unchanged_representatives": unchanged,
        "status": "NUMERIC_AND_PHYSICAL_RESULT_STABLE_REPRESENTATIVE_CORRECTED",
    }


def run() -> dict[str, Any]:
    origin_audit = verify_origin_audits()
    checked_hashes: dict[str, dict[str, str]] = {}
    old_results: dict[str, Mapping[str, Any]] = {}
    fresh_results: dict[str, Mapping[str, Any]] = {}
    for label, (old_path, fresh_path, old_hash, fresh_hash) in RESULT_PAIRS.items():
        checked_hashes[label] = {
            "old": verify_hash(old_path, old_hash),
            "fresh": verify_hash(fresh_path, fresh_hash),
        }
        old_results[label] = load(old_path)
        fresh_results[label] = load(fresh_path)

    stable = [
        verify_stable_result(label, old_results[label], fresh_results[label])
        for label in ("E057", "E058", "E059", "E060", "E061")
    ]
    e062 = verify_e062_correction(old_results["E062"], fresh_results["E062"])
    return {
        "schema": "zmd_zero_condition_e064_source_cache_revalidation_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": "SOURCE_REPLAY_PRESERVES_E057_E061_AND_CORRECTS_E062_PRESENCE",
        "decision": "USE_SOURCE_ISOLATED_IMPORTS_AND_FRESH_E062_PRESENCE",
        "origin_audit": origin_audit,
        "checked_result_hashes": checked_hashes,
        "stable_results": stable,
        "e062_correction": e062,
        "truth_boundary": (
            "Source-isolated reruns of the frozen E057-E062 research models. "
            "E057-E061 scientific fields are compared after removing only runtime "
            "counters, timestamps, identity envelopes, and evidence locators. E062 "
            "candidate identities and objective values are checked separately from "
            "the selected optimum-face presence witness."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if OUTPUT.exists():
        result = load(OUTPUT)
        if result.get("schema") != "zmd_zero_condition_e064_source_cache_revalidation_v1":
            raise RuntimeError("existing E064 result schema drift")
    else:
        result = run()
        dump_exclusive(OUTPUT, result)
    if not RECEIPT.exists():
        dump_exclusive(
            RECEIPT,
            {
                "schema": "zmd_zero_condition_e064_result_receipt_v1",
                "created_at_utc": utc_now(),
                "authority": "research_only_noncertified",
                "result_path": str(OUTPUT.relative_to(ROOT)),
                "result_sha256": sha256_file(OUTPUT),
                "default_origins_sha256": sha256_file(DEFAULT_ORIGINS),
                "fresh_origins_sha256": sha256_file(FRESH_ORIGINS),
                "ledger_effect": "none",
            },
        )
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "default_foreign": result["origin_audit"][
                    "default_foreign_function_count"
                ],
                "fresh_foreign": result["origin_audit"][
                    "fresh_foreign_function_count"
                ],
                "e062_corrected": result["e062_correction"][
                    "corrected_representative_count"
                ],
                "result_path": str(OUTPUT),
                "result_sha256": sha256_file(OUTPUT),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
