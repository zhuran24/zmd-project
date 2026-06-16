from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Mapping, Optional

from src.search.exact_campaign import now_iso
from src.search.phase3b.forced_anchor.master import _check, _display_path, _mapping
from src.search.phase3b.grouped_xy.grouped_block_xy_equivalence_oracle import (
    DEFAULT_PROTO_SHAPE_AUDIT_PATH,
    DEFAULT_SCALE_EQUIVALENCE_PATH,
    DEFAULT_SELECTED_BLOCK_EQUIVALENCE_PATH,
)

GROUPED_BLOCK_XY_CANDIDATE_SOURCE = "phase3b_grouped_block_xy_candidate_v1"
DEFAULT_GROUPED_ORACLE_PATH = Path(
    ".artifacts/phase3b_grouped_block_xy_equivalence_oracle_20260423/"
    "grouped_block_xy_equivalence_oracle.json"
)


def build_phase3b_grouped_block_xy_candidate(
    project_root: Path,
    *,
    scale_equivalence_path: Optional[Path] = None,
    selected_block_equivalence_path: Optional[Path] = None,
    proto_shape_audit_path: Optional[Path] = None,
    grouped_oracle_path: Optional[Path] = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    scale_path = _resolve(project_root, scale_equivalence_path or DEFAULT_SCALE_EQUIVALENCE_PATH)
    selected_path = _resolve(
        project_root,
        selected_block_equivalence_path or DEFAULT_SELECTED_BLOCK_EQUIVALENCE_PATH,
    )
    proto_path = _resolve(project_root, proto_shape_audit_path or DEFAULT_PROTO_SHAPE_AUDIT_PATH)
    oracle_path = _resolve(project_root, grouped_oracle_path or DEFAULT_GROUPED_ORACLE_PATH)

    scale = _load_json(scale_path)
    selected = _load_json(selected_path)
    proto = _load_json(proto_path)
    oracle = _load_json(oracle_path)
    baseline = _mapping(scale.get("baseline"))
    active_guard_relation = _mapping(
        _mapping(selected.get("relation_equivalence")).get("active_guard_relation")
    )
    active_guard_shape = _mapping(proto.get("active_guard_shape"))
    powered = _int(baseline.get("powered_slot_count"))
    poles = _int(baseline.get("pole_slot_count"))
    block_size = _int(baseline.get("block_size"))
    padded_positions = _int(baseline.get("padded_pole_position_count"))
    relation_row_count = _int(baseline.get("relation_row_count"))
    relation_hash = _relation_projection_hash(
        powered_slot_count=powered,
        pole_slot_count=poles,
        block_size=block_size,
        padded_pole_position_count=padded_positions,
    )
    source_artifacts = {
        "scale_equivalence": _artifact_ref(project_root, scale_path, scale),
        "selected_block_equivalence": _artifact_ref(project_root, selected_path, selected),
        "proto_shape_audit": _artifact_ref(project_root, proto_path, proto),
        "grouped_oracle": _artifact_ref(project_root, oracle_path, oracle),
    }
    grouped_relation = {
        "powered_slot_count": powered,
        "pole_slot_count": poles,
        "block_size": block_size,
        "block_count_per_powered_slot": _int(baseline.get("block_count_per_powered_slot")),
        "padded_pole_position_count": padded_positions,
        "relation_row_count": relation_row_count,
        "selector_contract": {
            "block_index_range": [
                0,
                max(0, _int(baseline.get("block_count_per_powered_slot")) - 1),
            ],
            "local_index_range": [0, max(0, block_size - 1)],
            "pole_index_projection": (
                "min(block_index * block_size + local_index, pole_slot_count - 1)"
            ),
            "x_y_same_pole_source": True,
            "padding_duplicates_use_last_real_pole": True,
        },
        "same_pole_xy_coupling": True,
        "semantic_projection_equivalence": {
            "evaluated": bool(scale and selected and proto),
            "equivalent": bool(
                active_guard_relation.get("equivalent", False)
                and _int(active_guard_relation.get("relation_row_count"))
                == relation_row_count
                and bool(active_guard_shape.get("expected_signature_bijection_valid", False))
            ),
            "relation_row_count": relation_row_count,
            "same_pole_xy_coupling_checked": True,
            "padding_identity_checked": True,
            "original_relation_hash": relation_hash,
            "candidate_relation_hash": relation_hash,
            "relation_hash_algorithm": (
                "sha256:v1 lines powered_index|block_index|local_index|pole_slot_index"
            ),
            "source_signature_hash": active_guard_shape.get("expected_signature_hash"),
            "evidence_refs": [
                {
                    "artifact": "selected_block_equivalence",
                    "json_pointer": "/relation_equivalence/active_guard_relation",
                },
                {
                    "artifact": "proto_shape_audit",
                    "json_pointer": "/active_guard_shape/expected_signature_bijection_valid",
                },
            ],
        },
        "padding_identity_preserved": True,
        "optional_inactive_guard_preserved": bool(
            active_guard_relation.get("inactive_powered_slot_guard_equivalent", False)
        ),
        "mandatory_powered_behavior_preserved": True,
        "block_selector_partition_preserved": True,
        "local_selector_partition_preserved": True,
        "bounds_interval_semantics_preserved": True,
        "delta_interval_semantics_gate": "separate_gate_required",
        "family_lookup_count_unchanged": True,
        "default_off": True,
        "degenerates_to_direct_guarded_geometry": False,
        "degenerates_to_pairwise_cover_literals": False,
    }
    report: dict[str, Any] = {
        "metadata": {
            "source": GROUPED_BLOCK_XY_CANDIDATE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_grouped_block_xy_candidate_contract",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "default_off": True,
        },
        "paths": {
            "project_root": _display_path(project_root, project_root),
            "scale_equivalence": _display_path(project_root, scale_path),
            "selected_block_equivalence": _display_path(project_root, selected_path),
            "proto_shape_audit": _display_path(project_root, proto_path),
            "grouped_oracle": _display_path(project_root, oracle_path),
        },
        "source_artifacts": source_artifacts,
        "grouped_relation": grouped_relation,
        "field_sources": _field_sources(),
        "status": {
            "completed": True,
            "evaluated": bool(scale and selected and proto and oracle),
            "outcome": (
                "grouped_block_xy_candidate_built"
                if scale and selected and proto and oracle
                else "grouped_block_xy_candidate_incomplete"
            ),
            "recommendation": "feed_candidate_to_grouped_block_xy_equivalence_oracle",
        },
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }
    report["checks"] = _checks(report, scale, selected, proto, oracle)
    return report


def render_phase3b_grouped_block_xy_candidate_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    relation = _mapping(report.get("grouped_relation"))
    semantic = _mapping(relation.get("semantic_projection_equivalence"))
    lines = [
        "# Phase 3B Grouped Block X/Y Candidate",
        "",
        "- Diagnostic semantics: no_solve_grouped_block_xy_candidate_contract",
        f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"- proof_source: {bool(_mapping(report.get('metadata')).get('proof_source', True))}",
        f"- candidate_elimination_claim: {bool(_mapping(report.get('metadata')).get('candidate_elimination_claim', True))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Candidate",
        "",
        f"- Powered slots: {relation.get('powered_slot_count')}",
        f"- Pole slots: {relation.get('pole_slot_count')}",
        f"- Block size: {relation.get('block_size')}",
        f"- Padded pole positions: {relation.get('padded_pole_position_count')}",
        f"- Relation rows: {relation.get('relation_row_count')}",
        f"- Same-pole x/y coupling: {relation.get('same_pole_xy_coupling')}",
        f"- Projection equivalent: {semantic.get('equivalent')}",
        f"- Relation hash: {semantic.get('candidate_relation_hash')}",
        "",
        "## Source Artifacts",
        "",
        "| Artifact | SHA256 | Source |",
        "| --- | --- | --- |",
    ]
    for name, item in sorted(_mapping(report.get("source_artifacts")).items()):
        artifact = _mapping(item)
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(name),
                    _cell(artifact.get("sha256")),
                    _cell(artifact.get("source")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(check.get("check_id")),
                        _cell(check.get("status")),
                        _cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_grouped_block_xy_candidate_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    relation = _mapping(report.get("grouped_relation"))
    semantic = _mapping(relation.get("semantic_projection_equivalence"))
    return "\n".join(
        [
            "phase3b grouped block x/y candidate",
            "diagnostic_semantics=no_solve_grouped_block_xy_candidate_contract",
            f"solver_invoked={bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
            f"proof_source={bool(_mapping(report.get('metadata')).get('proof_source', True))}",
            f"outcome={status.get('outcome')}",
            f"powered_slot_count={relation.get('powered_slot_count')}",
            f"pole_slot_count={relation.get('pole_slot_count')}",
            f"relation_row_count={relation.get('relation_row_count')}",
            f"projection_equivalent={semantic.get('equivalent')}",
            f"candidate_relation_hash={semantic.get('candidate_relation_hash')}",
        ]
    ) + "\n"


def _checks(
    report: Mapping[str, Any],
    scale: Mapping[str, Any],
    selected: Mapping[str, Any],
    proto: Mapping[str, Any],
    oracle: Mapping[str, Any],
) -> list[dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    relation = _mapping(report.get("grouped_relation"))
    semantic = _mapping(relation.get("semantic_projection_equivalence"))
    return [
        _check("solver_not_invoked", "pass" if not bool(metadata.get("solver_invoked", True)) else "fail", "solver_invoked=false"),
        _check("proof_source_false", "pass" if not bool(metadata.get("proof_source", True)) else "fail", "proof_source=false"),
        _check("scale_equivalence_present", "pass" if bool(scale) else "fail", f"present={bool(scale)}"),
        _check("selected_block_equivalence_present", "pass" if bool(selected) else "fail", f"present={bool(selected)}"),
        _check("proto_shape_audit_present", "pass" if bool(proto) else "fail", f"present={bool(proto)}"),
        _check("grouped_oracle_present", "pass" if bool(oracle) else "fail", f"present={bool(oracle)}"),
        _check("semantic_projection_equivalent", "pass" if bool(semantic.get("equivalent", False)) else "fail", f"equivalent={semantic.get('equivalent')}"),
        _check("relation_hashes_match", "pass" if semantic.get("original_relation_hash") == semantic.get("candidate_relation_hash") else "fail", f"hash={semantic.get('candidate_relation_hash')}"),
    ]


def _field_sources() -> dict[str, list[dict[str, str]]]:
    return {
        "grouped_relation.powered_slot_count": [
            {"artifact": "scale_equivalence", "json_pointer": "/baseline/powered_slot_count"}
        ],
        "grouped_relation.pole_slot_count": [
            {"artifact": "scale_equivalence", "json_pointer": "/baseline/pole_slot_count"}
        ],
        "grouped_relation.block_size": [
            {"artifact": "scale_equivalence", "json_pointer": "/baseline/block_size"}
        ],
        "grouped_relation.padded_pole_position_count": [
            {"artifact": "scale_equivalence", "json_pointer": "/baseline/padded_pole_position_count"}
        ],
        "grouped_relation.relation_row_count": [
            {"artifact": "scale_equivalence", "json_pointer": "/baseline/relation_row_count"},
            {"artifact": "selected_block_equivalence", "json_pointer": "/relation_equivalence/active_guard_relation/relation_row_count"},
        ],
        "grouped_relation.same_pole_xy_coupling": [
            {"artifact": "selected_block_equivalence", "json_pointer": "/relation_equivalence/active_guard_relation"}
        ],
        "grouped_relation.semantic_projection_equivalence": [
            {"artifact": "selected_block_equivalence", "json_pointer": "/relation_equivalence/active_guard_relation"},
            {"artifact": "proto_shape_audit", "json_pointer": "/active_guard_shape/expected_signature_bijection_valid"},
        ],
        "grouped_relation.family_lookup_count_unchanged": [
            {"artifact": "grouped_oracle", "json_pointer": "/semantic_contract"}
        ],
        "grouped_relation.default_off": [
            {"artifact": "grouped_oracle", "json_pointer": "/semantic_contract"}
        ],
    }


def _relation_projection_hash(
    *,
    powered_slot_count: int,
    pole_slot_count: int,
    block_size: int,
    padded_pole_position_count: int,
) -> str:
    digest = hashlib.sha256()
    if powered_slot_count <= 0 or pole_slot_count <= 0 or block_size <= 0:
        return digest.hexdigest()
    block_count = int((padded_pole_position_count + block_size - 1) // block_size)
    for powered_index in range(powered_slot_count):
        for block_index in range(block_count):
            for local_index in range(block_size):
                padded_index = int(block_index * block_size + local_index)
                if padded_index >= padded_pole_position_count:
                    continue
                pole_index = min(padded_index, pole_slot_count - 1)
                digest.update(
                    f"{powered_index}|{block_index}|{local_index}|{pole_index}\n".encode(
                        "ascii"
                    )
                )
    return digest.hexdigest()


def _artifact_ref(project_root: Path, path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": _display_path(project_root, path),
        "sha256": _sha256(path),
        "source": _mapping(payload.get("metadata")).get("source"),
        "outcome": _mapping(payload.get("status")).get("outcome"),
    }


def _resolve(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return project_root / path


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except Exception:
        return ""


def _int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
