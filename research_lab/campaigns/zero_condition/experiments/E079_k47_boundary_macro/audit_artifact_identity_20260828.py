#!/usr/bin/env python3
"""Audit the E079/E080 artifact-identity overwrite incident without rebinding.

This checker treats the original admitted byte identities as historical facts,
checks the current overwritten run directories by their current bytes, and
compares only a declared semantic projection to the independent blind/recheck
objects.  It does not promote the current bytes into the old evidence slots.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
BLIND_ROOT = Path("/home/zhuran24/zmd-blind")
OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E079_E080_identity_incident_20260828/AUDIT.json"
)

E079_DIR = (
    ROOT
    / "research_lab/local/zero_condition/E079_k47_boundary_macro/run-001"
)
E080_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E080_dependency_partition_seam_frontier/run-001"
)
RECHECK = ROOT / "research_lab/local/reviews/k47_recheck/recheck_result.json"
BLIND_PACKINGS = BLIND_ROOT / "blind_lab/local/u9/boundary_packings.json"
E079_RUNNER = Path(__file__).with_name("run_e079.py")
E080_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E080_dependency_partition_seam_frontier/run_e080.py"
)

ADMITTED = {
    "E079": {
        "RESULT.json": "9442e6568238edfe6aa7c37f1bddaf8a9f10c7017320c6af0cea092c80583662",
        "BOUNDARY_MACRO_V1.json": "f7f4cf3c70046e02bd434929570e6d177994198d7a588cbc02d24751b35c1810",
        "ENCODING_BENCHMARK.json": "43be1146c9e85904466e8349c4c686fcba1f77d639d6949b4e669366e2e83cb6",
        "RESULT_RECEIPT.json": "c1288f276eec2525d529a3dea177beaec761261a5c960a0c0953f2ddbbf0cd87",
    },
    "E080": {
        "RESULT.json": "47f497a3f8ee26351bdc1616c8061f80d03646089c266be66f979f7393080077",
        "PARTITION_FRONTIER.json": "96e4e84fb88c666aee38c7be2c421a59ca4fbe7e59d570eacee5f4391fe867b7",
        "SEAM_CONTRACT.json": "c44ee40995fcdd44a2ec9a8443245d1be75b51258ca9b347cd0fe1ae3563e6fc",
        "RESULT_RECEIPT.json": "92452d2d51e185f6f3958b0b35a541617a0ffd2126c3e14f6229f22c895d3a09",
    },
}

INTERMEDIATE_RECORD_CLAIMS = {
    "E079": {
        "RESULT.json": "06576856727f16eb1a52ced690a865f50453c39cf7a5a478c26e481777d5f718",
        "BOUNDARY_MACRO_V1.json": "4300cc3fbd4423e6f7ea21cf49e32c9264dc4177b97e1fb891bc4d6883087ef1",
        "ENCODING_BENCHMARK.json": "5ad9f09b8c73b23bb3f9ce377be2cf990721c54194f5b36b998f90154bcb96eb",
    },
    "E080": {
        "RESULT.json": "f79d27dfef7b7cfe073cb48abbd94018f42a32fdb2aa2217195e1fc8a6631321",
        "PARTITION_FRONTIER.json": "564ae324238c945de0cfe31c66065acf2992c5fd013e9f9d3c0175a31785089b",
        "SEAM_CONTRACT.json": "2b9e466e8d11c25d7e7a9da1ee12d000cff9ac8a8930c12e93b791b2a7d8c67",
    },
}

CURRENT = {
    "E079": {
        "RESULT.json": "3bf4ed2587e5efa51d83d0a82c12499f887a56cb100ebc5ddcbc2cc9db41d7af",
        "BOUNDARY_MACRO_V1.json": "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
        "ENCODING_BENCHMARK.json": "18dae7f06a56262e12db4276d45191d2cbd1604eb323915f119a16c1b21a9e1c",
        "RESULT_RECEIPT.json": "ec146b243040ba9bf45c52a4108a0dc090fbabca98af75a6074e22edef2bccb2",
    },
    "E080": {
        "RESULT.json": "c24ce2cdfb09e0bb72d10db8bd826adcf35b0b20d69ad0cb255f44efe038b21b",
        "PARTITION_FRONTIER.json": "6971f3ddc7e4a276703f65197477e9852733167d2cb4ace605acea3be2df8769",
        "SEAM_CONTRACT.json": "68dacce51deab725fd1e71a5e363ff1d7b9fed065cf5088b9d27acbc0bb5e5e6",
        "RESULT_RECEIPT.json": "65841dd05569a46a36b62c83a747eaa573dbdb5d796571fcfb3a5e49924a0042",
    },
}

EXPECTED_RUNNERS = {
    str(E079_RUNNER.relative_to(ROOT)): (
        "549bb2ae5858ad75e60d7dcf44a0064066c252c0d999182ed7080c4b0181da73"
    ),
    str(E080_RUNNER.relative_to(ROOT)): (
        "c3eab72325aefd39ca3719bc836ef137f0f3901415079095d5e120bd435df265"
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def file_records(directory: Path, expected: Mapping[str, str]) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for name, expected_hash in expected.items():
        path = directory / name
        require(path.is_file(), f"missing current artifact: {path}")
        observed = sha256_file(path)
        require(
            observed == expected_hash,
            f"current artifact drift: {path}: {observed} != {expected_hash}",
        )
        records[name] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }
    return records


def state_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "pose_indices": [int(value) for value in row["pose_indices"]],
        "left_anchors": [int(value) for value in row["left_anchors"]],
        "bottom_anchors": [int(value) for value in row["bottom_anchors"]],
        "omitted_allowed_l_cell": [
            int(value) for value in row["omitted_allowed_l_cell"]
        ],
    }


def blind_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "pose_indices": [int(value) for value in row["pose_indices"]],
        "left_anchors": [int(value) for value in row["left_anchors"]],
        "bottom_anchors": [int(value) for value in row["bottom_anchors"]],
        "omitted_allowed_l_cell": [
            int(value) for value in row["free_boundary_cell"]
        ],
    }


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def main() -> int:
    current_records = {
        "E079": file_records(E079_DIR, CURRENT["E079"]),
        "E080": file_records(E080_DIR, CURRENT["E080"]),
    }
    runner_records: dict[str, str] = {}
    for relative, expected_hash in EXPECTED_RUNNERS.items():
        path = ROOT / relative
        observed = sha256_file(path)
        require(
            observed == expected_hash,
            f"runner drift: {relative}: {observed} != {expected_hash}",
        )
        runner_records[relative] = observed

    macro = load_json(E079_DIR / "BOUNDARY_MACRO_V1.json")
    e079_result = load_json(E079_DIR / "RESULT.json")
    blind = load_json(BLIND_PACKINGS)
    recheck = load_json(RECHECK)
    states = list(macro["states"])
    packings = list(blind["packings"])
    require(int(macro["state_count"]) == 47 and len(states) == 47, "current K drift")
    require(len(packings) == 47, "blind packing count drift")
    current_projection = [state_projection(row) for row in states]
    blind_projection_rows = [blind_projection(row) for row in packings]
    require(
        current_projection == blind_projection_rows,
        "current E079 47-state projection differs from blind packings",
    )
    require(int(recheck["K"]) == 47, "R1 recheck K drift")
    require(
        bool(recheck["blind_packings_exact_equal"]),
        "R1 recheck no longer records exact blind equality",
    )
    require(int(e079_result["packing_count"]) == 47, "current E079 result K drift")
    require(e079_result["rank1_is_wlog"] is False, "rank-1 WLOG guard drift")

    e080_result = load_json(E080_DIR / "RESULT.json")
    frontier = load_json(E080_DIR / "PARTITION_FRONTIER.json")
    seam = load_json(E080_DIR / "SEAM_CONTRACT.json")
    require(int(e080_result["operation_type_count"]) == 17, "E080 operation count drift")
    require(
        int(e080_result["canonical_partition_count"]) == 65_535,
        "E080 canonical count drift",
    )
    require(int(e080_result["connected_partition_count"]) == 53, "E080 connected count drift")
    require(int(e080_result["pareto_frontier_count"]) == 6, "E080 Pareto count drift")
    selected = e080_result["selected_partition"]
    require(selected["partition_id"] == "partition_29914", "E080 selected partition drift")
    require(
        list(selected["seam"]["commodities"]) == ["sandleaf_powder", "steel_block"],
        "E080 selected seam drift",
    )
    require(
        frontier["selected_partition"]["partition_id"] == "partition_29914",
        "E080 frontier selected partition drift",
    )
    require(
        seam["selected_partition"]["partition_id"] == "partition_29914",
        "E080 seam selected partition drift",
    )
    macro_identity = e080_result["boundary_macro_identity"]
    require(int(macro_identity["state_count"]) == 47, "E080 macro count drift")
    require(
        macro_identity["sha256"] == CURRENT["E079"]["BOUNDARY_MACRO_V1.json"],
        "current E080 does not bind current overwritten E079 macro",
    )

    payload = {
        "schema": "zmd_e079_e080_artifact_identity_incident_audit_v1",
        "status": "PASS",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "research_head_at_audit": git_head(),
        "admitted_original_identities": ADMITTED,
        "intermediate_record_claims_not_present_on_disk": INTERMEDIATE_RECORD_CLAIMS,
        "current_overwritten_identities": current_records,
        "runner_identities_unchanged_from_original_commits": runner_records,
        "e079_semantic_replay": {
            "state_count": 47,
            "ordered_projection_exact_equal_to_blind": True,
            "projection_sha256": canonical_digest(current_projection),
            "blind_artifact": {
                "path": str(BLIND_PACKINGS),
                "sha256": sha256_file(BLIND_PACKINGS),
            },
            "r1_recheck": {
                "path": str(RECHECK.relative_to(ROOT)),
                "sha256": sha256_file(RECHECK),
                "blind_packings_exact_equal": True,
            },
        },
        "e080_load_bearing_replay": {
            "operation_type_count": 17,
            "canonical_partition_count": 65_535,
            "connected_partition_count": 53,
            "pareto_frontier_count": 6,
            "selected_partition_id": "partition_29914",
            "selected_seam_commodities": ["sandleaf_powder", "steel_block"],
            "current_rerun_binds_current_e079_macro": True,
        },
        "identity_judgment": {
            "original_bytes_restored_or_recovered": False,
            "current_bytes_promoted_into_original_slots": False,
            "semantic_object_reproduced": True,
            "rule": (
                "Keep the admitted original SHA records as the identity of the R1 result. "
                "Treat the current run-001 bytes as an unadmitted rerun and semantic "
                "corroboration only; never silently resolve an old pin to the current path."
            ),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "projection_sha256": payload["e079_semantic_replay"][
                    "projection_sha256"
                ],
                "output_path": str(OUT.relative_to(ROOT)),
                "output_sha256": sha256_file(OUT),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
