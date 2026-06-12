"""
Exact campaign state manager（精确战役状态管理器）.

职责：
1. 计算 certified exact（严格认证精确）输入工件哈希。
2. 管理最长 168 小时级 campaign state（战役状态）持久化。
3. 只有在 schema / mode / artifact hash / required fields 一致时才允许恢复。
4. 为每个候选空地保存 strictly valid evidence（严格有效证据）与 exact-safe cuts（精确安全 cuts）。
"""

from __future__ import annotations

import calendar
import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from src.models.cut_manager import BendersCut, _parse_ghost_anchor_condition_key
from src.models.master_model import (
    POSE_LEVEL_OPTIONAL_OPERATIONS,
    POSE_LEVEL_OPTIONAL_TEMPLATES,
    infer_certified_optional_lower_bounds,
)
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_OBJECTIVE,
    terminal_frontier_evidence_violation,
)

DEFAULT_CAMPAIGN_FILENAME = "exact_campaign_state.json"
CAMPAIGN_SCHEMA_VERSION = 5
MASTER_DOMAIN_CONTRACT_SCHEMA_VERSION = 1
PROOF_SUMMARY_SCHEMA_VERSION = 1
TERMINAL_FULL_FRONTIER_CERTIFIED_REASON = "search_exhausted_all_candidates"
VALID_CANDIDATE_STATUSES = {
    "RUNNING",
    "CERTIFIED",
    "INFEASIBLE",
    "UNKNOWN",
    "UNPROVEN",
    # P1 #7a prep: ε-Certified status. status="EPSILON_CERTIFIED" 表示 candidate
    # 求到 ε-bound 内但未 ε=0 完整 certified。bound_state.epsilon_target 记录
    # 是哪个 ε 阶段（0.05/0.01/0.0）。final_status 同样可以是 EPSILON_CERTIFIED。
    "EPSILON_CERTIFIED",
}

# A terminal public final_result is a projection of the certified candidate
# placement witness, not an extensible proof envelope.  Extra top-level fields can
# be copied into final_solution.json / optimal_blueprint.json by downstream
# serializers without being bound to the candidate-record solution digest.  Keep
# the public CERTIFIED surface fail-closed until such fields have a replayable
# proof contract.
TERMINAL_CERTIFIED_FINAL_RESULT_ALLOWED_FIELDS = frozenset(
    {
        "ghost_rect",
        "placement_solution",
        "search_status",
        "search_stats",
    }
)
TERMINAL_CERTIFIED_GHOST_RECT_ALLOWED_FIELDS = frozenset(
    {
        "w",
        "h",
        "area",
        "anchor_x",
        "anchor_y",
    }
)
TERMINAL_CERTIFIED_PLACEMENT_SOLUTION_ENTRY_ALLOWED_FIELDS = frozenset(
    {
        "facility_type",
        "pose_idx",
        "pose_id",
        "anchor",
        "orientation",
        "port_mode",
        "instance_id",
        "operation_type",
        "is_mandatory",
        "bound_type",
        "solve_mode",
    }
)
TERMINAL_CERTIFIED_LAST_STOP_REASON_ALLOWED_FIELDS = frozenset(
    {
        "reason",
        "status",
        "updated_at",
    }
)
TERMINAL_CERTIFIED_SEARCH_STATS_ALLOWED_FIELDS = frozenset(
    {
        "attempts",
        "explicit_candidate_solves",
        "solve_mode",
        "campaign_resumed",
        "frontier_peak_size",
        "derived_pruned_candidates",
        "frontier_selection_policy",
        "frontier_candidate_metrics",
        "solve_time_seconds",
        "benders_iterations",
    }
)
TERMINAL_CERTIFIED_FRONTIER_METRIC_ALLOWED_FIELDS = frozenset(
    {
        "selection_score_num",
        "selection_score_den",
        "certification_prune_gain",
        "infeasible_prune_gain",
        "anchor_count",
        "frontier_size",
        "potential_domain_size",
        "probe_candidate",
        "probe_prune_gain",
        "probe_resume_pending",
    }
)
REQUIRED_STATE_FIELDS = {
    "schema_version",
    "solve_mode",
    "campaign_hours",
    "created_at",
    "updated_at",
    "artifact_hashes",
    "master_domain_contract",
    "proof_summary_schema_version",
    "reset_reason",
    "final_result",
    "final_status",
    "last_stop_reason",
    "terminal_frontier_evidence",
    "declare_mode",
    "candidates",
}


def _default_master_domain_contract() -> Dict[str, Any]:
    """Certified exact campaign states are full ghost-anchor-domain proofs.

    The runtime may have experimental anchor slicing knobs for RAM probes, but a
    terminal campaign candidate is a whole-candidate claim.  Persist the domain
    contract explicitly so resume validation does not treat a domain-slice proof
    as release-authoritative evidence.
    """

    return {
        "schema_version": MASTER_DOMAIN_CONTRACT_SCHEMA_VERSION,
        "ghost_anchor_domain": "full_unfiltered",
        "ghost_anchor_filter": None,
    }


def _validate_master_domain_contract(state: Mapping[str, Any]) -> Optional[str]:
    contract = state.get("master_domain_contract")
    if not isinstance(contract, Mapping):
        return "master_domain_contract_invalid"
    try:
        schema_version = _strict_resume_int(
            contract.get("schema_version"),
            "master_domain_contract.schema_version",
        )
    except Exception:
        return "master_domain_contract_invalid"
    if schema_version != MASTER_DOMAIN_CONTRACT_SCHEMA_VERSION:
        return "master_domain_contract_invalid"
    if str(contract.get("ghost_anchor_domain")) != "full_unfiltered":
        return "master_domain_contract_invalid"
    if contract.get("ghost_anchor_filter") is not None:
        return "master_domain_contract_invalid"
    return None


REQUIRED_CANDIDATE_FIELDS = {
    "ghost_rect",
    "attempts",
    "started_at",
    "updated_at",
    "finished_at",
    "status",
    "proof_summary",
    "exact_safe_cuts",
    "loaded_exact_safe_cut_count",
    "generated_exact_safe_cut_count",
}

EXACT_HASH_FILES = {
    "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
    "candidate_placements": "data/preprocessed/candidate_placements.json",
    "canonical_rules": "rules/canonical_rules.json",
    "generic_io_requirements": "data/preprocessed/generic_io_requirements.json",
}
OPTIONAL_EXACT_HASH_FILES = {
    # Runtime preprocess profiles still consume utility/cycle-group declarations
    # from preprocess_plan.json.  Bind it to checkpoints when present so a plan
    # edit cannot ride on stale exact artifacts.
    "preprocess_plan": "rules/preprocess_plan.json",
}
MISSING_OPTIONAL_EXACT_ARTIFACT_HASH = "__MISSING_OPTIONAL_EXACT_ARTIFACT__"


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _loads_strict_json_object(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
    )


def now_ts() -> float:
    return time.time()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts()))


def iso_to_ts(iso_text: str) -> float:
    try:
        return float(calendar.timegm(time.strptime(iso_text, "%Y-%m-%dT%H:%M:%SZ")))
    except Exception:
        return now_ts()


def _path_has_symlink_component(path: Path) -> bool:
    candidate = Path(path)
    if not candidate.parts:
        return False
    current = Path(candidate.anchor) if candidate.is_absolute() else Path()
    parts = candidate.parts[1:] if candidate.is_absolute() else candidate.parts
    for part in parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return False
    return False


def sha256_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    if _path_has_symlink_component(path) or not path.is_file():
        raise ValueError(f"exact artifact must be a regular file with no symlink components: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def compute_exact_artifact_hashes(project_root: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for key, relative_path in EXACT_HASH_FILES.items():
        hashes[key] = sha256_file(project_root / relative_path)
    for key, relative_path in OPTIONAL_EXACT_HASH_FILES.items():
        artifact_path = project_root / relative_path
        if artifact_path.exists() or _path_has_symlink_component(artifact_path):
            hashes[key] = sha256_file(artifact_path)
        else:
            hashes[key] = MISSING_OPTIONAL_EXACT_ARTIFACT_HASH
    return hashes


def _strict_resume_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return int(value)


def _solution_without_ghost_marker(solution: Mapping[str, Any]) -> Dict[str, Any]:
    return {str(key): value for key, value in solution.items() if str(key) != "ghost_pick"}


def _terminal_certified_ghost_rect_unknown_field(ghost_rect: Mapping[str, Any]) -> Optional[str]:
    unknown_fields = sorted(
        str(field)
        for field in ghost_rect.keys()
        if str(field) not in TERMINAL_CERTIFIED_GHOST_RECT_ALLOWED_FIELDS
    )
    if unknown_fields:
        return f"terminal_certified_final_result_ghost_rect_unknown_field:{unknown_fields[0]}"
    return None


def _terminal_certified_last_stop_reason_violation(state: Mapping[str, Any]) -> Optional[str]:
    stop_record = state.get("last_stop_reason")
    if not isinstance(stop_record, Mapping):
        return "terminal_certified_last_stop_reason_invalid"
    unknown_fields = sorted(
        str(field)
        for field in stop_record.keys()
        if str(field) not in TERMINAL_CERTIFIED_LAST_STOP_REASON_ALLOWED_FIELDS
    )
    if unknown_fields:
        return f"terminal_certified_last_stop_reason_unknown_field:{unknown_fields[0]}"
    if str(stop_record.get("reason", "")) != TERMINAL_FULL_FRONTIER_CERTIFIED_REASON:
        return "terminal_certified_last_stop_reason_invalid"
    if str(stop_record.get("status", "")) != "CERTIFIED":
        return "terminal_certified_last_stop_reason_invalid"
    raw_updated_at = stop_record.get("updated_at")
    if raw_updated_at is not None and not isinstance(raw_updated_at, str):
        return "terminal_certified_last_stop_reason_invalid"
    return None


def _nonnegative_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and float(value) >= 0.0
        and float(value) != float("inf")
    )


def _terminal_certified_solution_entry_unknown_field(raw_entry: Mapping[str, Any]) -> Optional[str]:
    for key in raw_entry:
        field = str(key)
        if field not in TERMINAL_CERTIFIED_PLACEMENT_SOLUTION_ENTRY_ALLOWED_FIELDS:
            return field
    return None


def _terminal_certified_search_stats_violation(raw_search_stats: Any) -> Optional[str]:
    if raw_search_stats is None:
        return None
    if not isinstance(raw_search_stats, Mapping):
        return "terminal_certified_final_result_search_stats_invalid"
    unknown_fields = sorted(
        str(field)
        for field in raw_search_stats.keys()
        if str(field) not in TERMINAL_CERTIFIED_SEARCH_STATS_ALLOWED_FIELDS
    )
    if unknown_fields:
        return f"terminal_certified_final_result_search_stats_unknown_field:{unknown_fields[0]}"

    for field in (
        "attempts",
        "explicit_candidate_solves",
        "frontier_peak_size",
        "derived_pruned_candidates",
        "benders_iterations",
    ):
        if field in raw_search_stats:
            try:
                value = _strict_resume_int(raw_search_stats.get(field), f"final_result.search_stats.{field}")
            except Exception:
                return "terminal_certified_final_result_search_stats_invalid"
            if int(value) < 0:
                return "terminal_certified_final_result_search_stats_invalid"

    if "solve_time_seconds" in raw_search_stats and not _nonnegative_number(
        raw_search_stats.get("solve_time_seconds")
    ):
        return "terminal_certified_final_result_search_stats_invalid"
    if "solve_mode" in raw_search_stats and str(raw_search_stats.get("solve_mode")) != "certified_exact":
        return "terminal_certified_final_result_search_stats_invalid"
    if "campaign_resumed" in raw_search_stats and not isinstance(
        raw_search_stats.get("campaign_resumed"),
        bool,
    ):
        return "terminal_certified_final_result_search_stats_invalid"
    if "frontier_selection_policy" in raw_search_stats:
        try:
            _strict_nonempty_string(
                raw_search_stats.get("frontier_selection_policy"),
                "final_result.search_stats.frontier_selection_policy",
            )
        except Exception:
            return "terminal_certified_final_result_search_stats_invalid"

    raw_metrics = raw_search_stats.get("frontier_candidate_metrics")
    if raw_metrics is not None:
        if not isinstance(raw_metrics, Mapping):
            return "terminal_certified_final_result_search_stats_invalid"
        unknown_metric_fields = sorted(
            str(field)
            for field in raw_metrics.keys()
            if str(field) not in TERMINAL_CERTIFIED_FRONTIER_METRIC_ALLOWED_FIELDS
        )
        if unknown_metric_fields:
            return (
                "terminal_certified_final_result_search_stats_frontier_metric_unknown_field:"
                f"{unknown_metric_fields[0]}"
            )
        for field, raw_value in raw_metrics.items():
            try:
                value = _strict_resume_int(
                    raw_value,
                    f"final_result.search_stats.frontier_candidate_metrics.{field}",
                )
            except Exception:
                return "terminal_certified_final_result_search_stats_invalid"
            if int(value) < 0:
                return "terminal_certified_final_result_search_stats_invalid"
    return None


def _terminal_candidate_ghost_pick_binding_violation(
    state: Mapping[str, Any],
    *,
    final_result: Mapping[str, Any],
) -> Optional[str]:
    """Return a reason when terminal candidate evidence is not bound to its ghost anchor.

    The public final_result deliberately strips the synthetic ``ghost_pick`` marker
    from ``placement_solution``.  The terminal candidate record remains the
    authority that the master selected a concrete anchor, so project-bound
    validators must check that marker instead of accepting a hand-authored
    final_result anchor on its own.
    """

    ghost_rect = final_result.get("ghost_rect")
    if not isinstance(ghost_rect, Mapping):
        return "terminal_certified_final_result_ghost_rect_invalid"
    ghost_rect_unknown_field = _terminal_certified_ghost_rect_unknown_field(ghost_rect)
    if ghost_rect_unknown_field is not None:
        return ghost_rect_unknown_field
    try:
        ghost_w = _strict_resume_int(ghost_rect.get("w"), "final_result.ghost_rect.w")
        ghost_h = _strict_resume_int(ghost_rect.get("h"), "final_result.ghost_rect.h")
    except Exception:
        return "terminal_certified_final_result_ghost_rect_invalid"
    if "anchor_x" not in ghost_rect or "anchor_y" not in ghost_rect:
        return "terminal_certified_final_result_ghost_rect_anchor_missing"
    try:
        anchor_x = _strict_resume_int(
            ghost_rect.get("anchor_x"),
            "final_result.ghost_rect.anchor_x",
        )
        anchor_y = _strict_resume_int(
            ghost_rect.get("anchor_y"),
            "final_result.ghost_rect.anchor_y",
        )
    except Exception:
        return "terminal_certified_final_result_ghost_rect_anchor_invalid"

    candidates = state.get("candidates")
    if not isinstance(candidates, Mapping):
        return "terminal_certified_candidate_record_missing"
    record = candidates.get(candidate_key(ghost_w, ghost_h))
    if not isinstance(record, Mapping):
        return "terminal_certified_candidate_record_missing"
    record_solution = record.get("solution")
    if not isinstance(record_solution, Mapping):
        return "terminal_certified_candidate_solution_missing"
    if "ghost_pick" not in record_solution:
        return "terminal_certified_candidate_solution_ghost_pick_missing"
    ghost_pick = record_solution.get("ghost_pick")
    if not isinstance(ghost_pick, Mapping):
        return "terminal_certified_candidate_solution_ghost_pick_invalid"
    anchor = ghost_pick.get("anchor")
    if not isinstance(anchor, Mapping):
        return "terminal_certified_candidate_solution_ghost_pick_invalid"
    try:
        pick_anchor_x = _strict_resume_int(
            anchor.get("x"),
            "candidate.solution.ghost_pick.anchor.x",
        )
        pick_anchor_y = _strict_resume_int(
            anchor.get("y"),
            "candidate.solution.ghost_pick.anchor.y",
        )
    except Exception:
        return "terminal_certified_candidate_solution_ghost_pick_invalid"
    if int(pick_anchor_x) != int(anchor_x) or int(pick_anchor_y) != int(anchor_y):
        return "terminal_certified_candidate_solution_ghost_pick_mismatch"
    return None


def _load_exact_grid_dimensions(project_root: Optional[Path]) -> Optional[Tuple[int, int]]:
    if project_root is None:
        return None
    rules_path = project_root / EXACT_HASH_FILES["canonical_rules"]
    payload = _loads_strict_json_object(rules_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("canonical_rules must be a JSON object")
    globals_payload = payload.get("globals")
    if not isinstance(globals_payload, Mapping):
        raise ValueError("canonical_rules.globals must be a mapping")
    grid = globals_payload.get("grid")
    if not isinstance(grid, Mapping):
        raise ValueError("canonical_rules.globals.grid must be a mapping")
    grid_w = _strict_resume_int(grid.get("width"), "canonical_rules.globals.grid.width")
    grid_h = _strict_resume_int(grid.get("height"), "canonical_rules.globals.grid.height")
    if grid_w <= 0 or grid_h <= 0:
        raise ValueError("canonical_rules grid dimensions must be positive")
    return grid_w, grid_h




def _load_exact_min_side_admissibility(project_root: Optional[Path]) -> Optional[int]:
    if project_root is None:
        return None
    rules_path = project_root / EXACT_HASH_FILES["canonical_rules"]
    payload = _loads_strict_json_object(rules_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("canonical_rules must be a JSON object")
    globals_payload = payload.get("globals")
    if not isinstance(globals_payload, Mapping):
        raise ValueError("canonical_rules.globals must be a mapping")
    empty_rectangle = globals_payload.get("empty_rectangle")
    if not isinstance(empty_rectangle, Mapping):
        raise ValueError("canonical_rules.globals.empty_rectangle must be a mapping")
    if str(empty_rectangle.get("objective", "")) != TERMINAL_FRONTIER_OBJECTIVE:
        raise ValueError("canonical_rules.globals.empty_rectangle.objective invalid")
    min_side_admissibility = _strict_resume_int(
        empty_rectangle.get("min_side_admissibility"),
        "canonical_rules.globals.empty_rectangle.min_side_admissibility",
    )
    if min_side_admissibility <= 0:
        raise ValueError("canonical min_side_admissibility must be positive")
    return int(min_side_admissibility)


def _strict_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _validated_mandatory_exact_instances_payload(raw_instances: Any) -> list[Dict[str, Any]]:
    if not isinstance(raw_instances, list):
        raise ValueError("mandatory_exact_instances must be a JSON array")
    validated: list[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_instance in enumerate(raw_instances):
        field_prefix = f"mandatory_exact_instances[{index}]"
        if not isinstance(raw_instance, Mapping):
            raise ValueError(f"{field_prefix} must be a JSON object")
        instance = dict(raw_instance)
        instance_id = _strict_nonempty_string(instance.get("instance_id"), f"{field_prefix}.instance_id")
        if instance_id in seen_ids:
            raise ValueError(f"duplicate mandatory exact instance_id: {instance_id}")
        seen_ids.add(instance_id)
        _strict_nonempty_string(instance.get("facility_type"), f"{field_prefix}.facility_type")
        if instance.get("is_mandatory") is not True:
            raise ValueError(f"{field_prefix}.is_mandatory must be true")
        if str(instance.get("bound_type", "")) != "exact":
            raise ValueError(f"{field_prefix}.bound_type must be exact")
        validated.append(instance)
    return validated


def _load_validated_mandatory_exact_instances(project_root: Path) -> list[Dict[str, Any]]:
    instances_path = Path(project_root) / EXACT_HASH_FILES["mandatory_exact_instances"]
    raw_instances = _loads_strict_json_object(instances_path.read_text(encoding="utf-8"))
    return _validated_mandatory_exact_instances_payload(raw_instances)


def _load_exact_facility_pools(project_root: Path) -> Dict[str, list[Dict[str, Any]]]:
    placements_path = Path(project_root) / EXACT_HASH_FILES["candidate_placements"]
    payload = _loads_strict_json_object(placements_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("candidate_placements must be a JSON object")
    raw_pools = payload.get("facility_pools")
    if not isinstance(raw_pools, Mapping):
        raise ValueError("candidate_placements.facility_pools must be a JSON object")
    pools: Dict[str, list[Dict[str, Any]]] = {}
    for facility_type, raw_pool in raw_pools.items():
        if not isinstance(raw_pool, list):
            raise ValueError(f"facility pool {facility_type!r} must be a JSON array")
        pool: list[Dict[str, Any]] = []
        for index, raw_pose in enumerate(raw_pool):
            if not isinstance(raw_pose, Mapping):
                raise ValueError(f"facility pool {facility_type!r}[{index}] must be a JSON object")
            pool.append(dict(raw_pose))
        pools[str(facility_type)] = pool
    return pools


def _load_exact_facility_templates(project_root: Path) -> Dict[str, Dict[str, Any]]:
    rules_path = Path(project_root) / EXACT_HASH_FILES["canonical_rules"]
    payload = _loads_strict_json_object(rules_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("canonical_rules must be a JSON object")
    raw_templates = payload.get("facility_templates")
    if not isinstance(raw_templates, Mapping):
        raise ValueError("canonical_rules.facility_templates must be a JSON object")
    templates: Dict[str, Dict[str, Any]] = {}
    for facility_type, raw_template in raw_templates.items():
        if not isinstance(raw_template, Mapping):
            raise ValueError(f"facility template {facility_type!r} must be a JSON object")
        templates[str(facility_type)] = dict(raw_template)
    return templates


def _pose_occupied_cells(pose: Mapping[str, Any], *, field: str) -> list[tuple[int, int]]:
    raw_cells = pose.get("occupied_cells")
    if not isinstance(raw_cells, list):
        raise ValueError(f"{field}.occupied_cells must be a JSON array")
    cells: list[tuple[int, int]] = []
    for index, raw_cell in enumerate(raw_cells):
        if (
            isinstance(raw_cell, (str, bytes))
            or not isinstance(raw_cell, Sequence)
            or len(raw_cell) != 2
        ):
            raise ValueError(f"{field}.occupied_cells[{index}] must be [x,y]")
        x = _strict_resume_int(raw_cell[0], f"{field}.occupied_cells[{index}][0]")
        y = _strict_resume_int(raw_cell[1], f"{field}.occupied_cells[{index}][1]")
        cells.append((int(x), int(y)))
    return cells


def _pose_power_coverage_cells(pose: Mapping[str, Any], *, field: str) -> list[tuple[int, int]]:
    raw_cells = pose.get("power_coverage_cells")
    if raw_cells is None:
        return []
    if not isinstance(raw_cells, list):
        raise ValueError(f"{field}.power_coverage_cells must be a JSON array or null")
    cells: list[tuple[int, int]] = []
    for index, raw_cell in enumerate(raw_cells):
        if (
            isinstance(raw_cell, (str, bytes))
            or not isinstance(raw_cell, Sequence)
            or len(raw_cell) != 2
        ):
            raise ValueError(f"{field}.power_coverage_cells[{index}] must be [x,y]")
        x = _strict_resume_int(raw_cell[0], f"{field}.power_coverage_cells[{index}][0]")
        y = _strict_resume_int(raw_cell[1], f"{field}.power_coverage_cells[{index}][1]")
        cells.append((int(x), int(y)))
    return cells


def _is_authorized_exact_pose_optional_solution_entry(
    *,
    instance_id: str,
    entry: Mapping[str, Any],
    pose: Mapping[str, Any],
    facility_type: str,
) -> bool:
    parts = str(instance_id).split("::", 2)
    if len(parts) != 3 or parts[0] != "pose_optional":
        return False
    optional_facility_type = parts[1]
    pose_id = parts[2]
    if optional_facility_type != str(facility_type):
        return False
    if optional_facility_type not in POSE_LEVEL_OPTIONAL_TEMPLATES:
        return False
    if str(pose.get("pose_id", "")) != pose_id:
        return False
    raw_pose_id = entry.get("pose_id")
    if raw_pose_id is not None and str(raw_pose_id) != pose_id:
        return False
    raw_is_mandatory = entry.get("is_mandatory")
    if raw_is_mandatory is not None and raw_is_mandatory is not False:
        return False
    raw_bound_type = entry.get("bound_type")
    if raw_bound_type is not None and str(raw_bound_type) != "exact_pose_optional":
        return False
    raw_solve_mode = entry.get("solve_mode")
    if raw_solve_mode is not None and str(raw_solve_mode) != "certified_exact":
        return False
    return True


def _terminal_solution_entry_pose_metadata_violation(
    *,
    instance_id: str,
    entry: Mapping[str, Any],
    pose: Mapping[str, Any],
) -> Optional[str]:
    raw_pose_id = entry.get("pose_id")
    if raw_pose_id is not None and str(raw_pose_id) != str(pose.get("pose_id", "")):
        return "terminal_certified_final_result_solution_pose_metadata_mismatch"

    raw_anchor = entry.get("anchor")
    if raw_anchor is not None:
        pose_anchor = pose.get("anchor")
        if not isinstance(raw_anchor, Mapping) or not isinstance(pose_anchor, Mapping):
            return "terminal_certified_final_result_solution_pose_metadata_mismatch"
        try:
            raw_anchor_x = _strict_resume_int(
                raw_anchor.get("x"),
                f"final_result.placement_solution.{instance_id}.anchor.x",
            )
            raw_anchor_y = _strict_resume_int(
                raw_anchor.get("y"),
                f"final_result.placement_solution.{instance_id}.anchor.y",
            )
            pose_anchor_x = _strict_resume_int(
                pose_anchor.get("x"),
                f"candidate_placements.{instance_id}.anchor.x",
            )
            pose_anchor_y = _strict_resume_int(
                pose_anchor.get("y"),
                f"candidate_placements.{instance_id}.anchor.y",
            )
        except Exception:
            return "terminal_certified_final_result_solution_pose_metadata_mismatch"
        if int(raw_anchor_x) != int(pose_anchor_x) or int(raw_anchor_y) != int(pose_anchor_y):
            return "terminal_certified_final_result_solution_pose_metadata_mismatch"

    pose_params = pose.get("pose_params")
    raw_orientation = entry.get("orientation")
    if raw_orientation is not None:
        if not isinstance(pose_params, Mapping):
            return "terminal_certified_final_result_solution_pose_metadata_mismatch"
        try:
            raw_orientation_int = _strict_resume_int(
                raw_orientation,
                f"final_result.placement_solution.{instance_id}.orientation",
            )
            pose_orientation_int = _strict_resume_int(
                pose_params.get("orientation", 0),
                f"candidate_placements.{instance_id}.pose_params.orientation",
            )
        except Exception:
            return "terminal_certified_final_result_solution_pose_metadata_mismatch"
        if int(raw_orientation_int) != int(pose_orientation_int):
            return "terminal_certified_final_result_solution_pose_metadata_mismatch"

    raw_port_mode = entry.get("port_mode")
    if raw_port_mode is not None:
        expected_port_mode = (
            pose_params.get("port_mode", "default")
            if isinstance(pose_params, Mapping)
            else "default"
        )
        if str(raw_port_mode) != str(expected_port_mode):
            return "terminal_certified_final_result_solution_pose_metadata_mismatch"
    return None


def _pose_optional_solution_entry_metadata_violation(
    *,
    instance_id: str,
    entry: Mapping[str, Any],
    facility_type: str,
) -> Optional[str]:
    raw_instance_id = entry.get("instance_id")
    if raw_instance_id is not None and str(raw_instance_id) != str(instance_id):
        return "terminal_certified_final_result_solution_metadata_mismatch"

    raw_operation_type = entry.get("operation_type")
    expected_operation_type = POSE_LEVEL_OPTIONAL_OPERATIONS.get(str(facility_type))
    if raw_operation_type is not None and str(raw_operation_type) != str(expected_operation_type):
        return "terminal_certified_final_result_solution_metadata_mismatch"
    return None


def _mandatory_solution_entry_metadata_violation(
    *,
    instance_id: str,
    entry: Mapping[str, Any],
    expected_instance: Mapping[str, Any],
) -> Optional[str]:
    raw_instance_id = entry.get("instance_id")
    if raw_instance_id is not None and str(raw_instance_id) != str(instance_id):
        return "terminal_certified_final_result_solution_metadata_mismatch"
    raw_is_mandatory = entry.get("is_mandatory")
    if raw_is_mandatory is not None and raw_is_mandatory is not True:
        return "terminal_certified_final_result_solution_metadata_mismatch"
    raw_bound_type = entry.get("bound_type")
    if raw_bound_type is not None and str(raw_bound_type) != "exact":
        return "terminal_certified_final_result_solution_metadata_mismatch"
    raw_operation_type = entry.get("operation_type")
    if (
        raw_operation_type is not None
        and "operation_type" in expected_instance
        and str(raw_operation_type) != str(expected_instance.get("operation_type"))
    ):
        return "terminal_certified_final_result_solution_metadata_mismatch"
    raw_solve_mode = entry.get("solve_mode")
    if raw_solve_mode is not None and str(raw_solve_mode) != "certified_exact":
        return "terminal_certified_final_result_solution_metadata_mismatch"
    return None


def _validate_terminal_solution_against_project(
    *,
    final_result: Mapping[str, Any],
    project_root: Path,
    grid_dimensions: Tuple[int, int],
    min_side_admissibility: Optional[int] = None,
) -> Optional[str]:
    placement_solution = final_result.get("placement_solution")
    if not isinstance(placement_solution, Mapping):
        return "terminal_certified_final_result_solution_missing"
    try:
        mandatory_instances = _load_validated_mandatory_exact_instances(project_root)
        facility_pools = _load_exact_facility_pools(project_root)
        facility_templates = _load_exact_facility_templates(project_root)
        required_optional_lower_bounds = _load_exact_required_optional_lower_bounds(project_root)
    except Exception:
        return "terminal_certified_project_solution_authority_invalid"

    mandatory_by_id = {str(instance["instance_id"]): dict(instance) for instance in mandatory_instances}
    missing_mandatory = sorted(set(mandatory_by_id).difference(str(key) for key in placement_solution.keys()))
    if missing_mandatory:
        return "terminal_certified_final_result_solution_missing_mandatory_instance"

    grid_w, grid_h = int(grid_dimensions[0]), int(grid_dimensions[1])
    occupied_cells: set[tuple[int, int]] = set()
    optional_solution_counts: Dict[str, int] = {}
    selected_power_poles: list[tuple[str, set[tuple[int, int]]]] = []
    powered_solution_cells: list[tuple[str, set[tuple[int, int]]]] = []
    for instance_id, raw_entry in placement_solution.items():
        # The ghost_pick entry is the empty rectangle's own placement marker:
        # its cells are the claimed empty area, not facility occupancy.
        # Counting it as occupied would make the witness scan reject every
        # genuine terminal result (the witness would have to avoid itself).
        if str(instance_id) == "ghost_pick":
            return "terminal_certified_final_result_solution_contains_ghost_pick_marker"
        if not isinstance(raw_entry, Mapping):
            return "terminal_certified_final_result_solution_invalid"
        entry = dict(raw_entry)
        unknown_entry_field = _terminal_certified_solution_entry_unknown_field(entry)
        if unknown_entry_field is not None:
            return f"terminal_certified_final_result_solution_unknown_field:{instance_id}.{unknown_entry_field}"
        try:
            facility_type = _strict_nonempty_string(
                entry.get("facility_type"),
                f"final_result.placement_solution.{instance_id}.facility_type",
            )
            pose_idx = _strict_resume_int(
                entry.get("pose_idx"),
                f"final_result.placement_solution.{instance_id}.pose_idx",
            )
        except Exception:
            return "terminal_certified_final_result_solution_invalid"
        expected_instance = mandatory_by_id.get(str(instance_id))
        if expected_instance is not None and facility_type != str(expected_instance.get("facility_type")):
            return "terminal_certified_final_result_solution_facility_type_mismatch"
        pool = facility_pools.get(facility_type)
        if pool is None or pose_idx < 0 or pose_idx >= len(pool):
            return "terminal_certified_final_result_solution_pose_invalid"
        template = facility_templates.get(facility_type)
        if template is None:
            return "terminal_certified_project_solution_authority_invalid"
        pose = pool[int(pose_idx)]
        pose_metadata_reason = _terminal_solution_entry_pose_metadata_violation(
            instance_id=str(instance_id),
            entry=entry,
            pose=pose,
        )
        if pose_metadata_reason is not None:
            return pose_metadata_reason
        if expected_instance is not None:
            mandatory_metadata_reason = _mandatory_solution_entry_metadata_violation(
                instance_id=str(instance_id),
                entry=entry,
                expected_instance=expected_instance,
            )
            if mandatory_metadata_reason is not None:
                return mandatory_metadata_reason
        if expected_instance is None:
            if not _is_authorized_exact_pose_optional_solution_entry(
                instance_id=str(instance_id),
                entry=entry,
                pose=pose,
                facility_type=facility_type,
            ):
                return "terminal_certified_final_result_solution_unknown_instance"
            optional_metadata_reason = _pose_optional_solution_entry_metadata_violation(
                instance_id=str(instance_id),
                entry=entry,
                facility_type=facility_type,
            )
            if optional_metadata_reason is not None:
                return optional_metadata_reason
            optional_solution_counts[str(facility_type)] = (
                optional_solution_counts.get(str(facility_type), 0) + 1
            )
        try:
            cells = _pose_occupied_cells(
                pose,
                field=f"candidate_placements.{facility_type}[{int(pose_idx)}]",
            )
        except Exception:
            return "terminal_certified_final_result_solution_pose_invalid"
        for cell in cells:
            x, y = cell
            if x < 0 or y < 0 or x >= grid_w or y >= grid_h:
                return "terminal_certified_final_result_solution_geometry_invalid"
            if cell in occupied_cells:
                return "terminal_certified_final_result_solution_geometry_invalid"
            occupied_cells.add(cell)
        if facility_type == "power_pole":
            try:
                coverage_cells = _pose_power_coverage_cells(
                    pose,
                    field=f"candidate_placements.{facility_type}[{int(pose_idx)}]",
                )
            except Exception:
                return "terminal_certified_final_result_solution_pose_invalid"
            in_grid_coverage_cells: set[tuple[int, int]] = set()
            for cell in coverage_cells:
                x, y = cell
                if 0 <= x < grid_w and 0 <= y < grid_h:
                    in_grid_coverage_cells.add(cell)
            selected_power_poles.append((str(instance_id), in_grid_coverage_cells))
        elif bool(template.get("needs_power", False)):
            powered_solution_cells.append((str(instance_id), set(cells)))

    for facility_type, required_count in sorted(required_optional_lower_bounds.items()):
        if optional_solution_counts.get(str(facility_type), 0) < int(required_count):
            return "terminal_certified_final_result_solution_missing_required_optional_instance"

    # Protocol storage boxes are only justified on the public certified surface by
    # the replayable generic-input lower-bound contract.  Extra pose-optional boxes
    # are cheap blockers for the terminal empty-rectangle replay; routing/provenance
    # evidence for such surplus selections belongs in a future proof-carrying
    # certificate, so the current public validator fails closed.
    required_protocol_storage_boxes = int(
        required_optional_lower_bounds.get("protocol_storage_box", 0)
    )
    selected_protocol_storage_boxes = int(
        optional_solution_counts.get("protocol_storage_box", 0)
    )
    if selected_protocol_storage_boxes > required_protocol_storage_boxes:
        return "terminal_certified_final_result_solution_excess_protocol_storage_box_instance"

    power_coverers_by_instance: Dict[str, list[str]] = {}
    power_targets_by_pole: Dict[str, set[str]] = {
        pole_instance_id: set() for pole_instance_id, _coverage_cells in selected_power_poles
    }
    for powered_instance_id, cells in powered_solution_cells:
        coverers = [
            pole_instance_id
            for pole_instance_id, coverage_cells in selected_power_poles
            if any(cell in coverage_cells for cell in cells)
        ]
        if not coverers:
            return "terminal_certified_final_result_solution_power_coverage_missing"
        power_coverers_by_instance[str(powered_instance_id)] = list(coverers)
        for pole_instance_id in coverers:
            power_targets_by_pole.setdefault(str(pole_instance_id), set()).add(str(powered_instance_id))

    if len(selected_power_poles) > len(powered_solution_cells):
        return "terminal_certified_final_result_solution_unforced_power_pole_instance"
    for pole_instance_id, _coverage_cells in selected_power_poles:
        covered_powered_instances = power_targets_by_pole.get(str(pole_instance_id), set())
        if not covered_powered_instances:
            return "terminal_certified_final_result_solution_unforced_power_pole_instance"
        if not any(
            power_coverers_by_instance.get(str(powered_instance_id)) == [str(pole_instance_id)]
            for powered_instance_id in covered_powered_instances
        ):
            return "terminal_certified_final_result_solution_unforced_power_pole_instance"

    ghost_rect = final_result.get("ghost_rect")
    if not isinstance(ghost_rect, Mapping):
        return "terminal_certified_final_result_ghost_rect_invalid"
    try:
        ghost_w = _strict_resume_int(ghost_rect.get("w"), "final_result.ghost_rect.w")
        ghost_h = _strict_resume_int(ghost_rect.get("h"), "final_result.ghost_rect.h")
    except Exception:
        return "terminal_certified_final_result_ghost_rect_invalid"
    if ghost_w <= 0 or ghost_h <= 0 or ghost_w > grid_w or ghost_h > grid_h:
        return "terminal_certified_final_result_ghost_rect_invalid"

    occupancy_prefix = _build_occupancy_prefix(
        occupied_cells=occupied_cells,
        grid_w=grid_w,
        grid_h=grid_h,
    )
    if "anchor_x" not in ghost_rect or "anchor_y" not in ghost_rect:
        return "terminal_certified_final_result_ghost_rect_anchor_missing"
    try:
        anchor_x = _strict_resume_int(
            ghost_rect.get("anchor_x"),
            "final_result.ghost_rect.anchor_x",
        )
        anchor_y = _strict_resume_int(
            ghost_rect.get("anchor_y"),
            "final_result.ghost_rect.anchor_y",
        )
    except Exception:
        return "terminal_certified_final_result_ghost_rect_anchor_invalid"
    if (
        anchor_x < 0
        or anchor_y < 0
        or anchor_x > grid_w - int(ghost_w)
        or anchor_y > grid_h - int(ghost_h)
    ):
        return "terminal_certified_final_result_ghost_rect_anchor_invalid"
    if _occupied_count_in_rect(
        occupancy_prefix=occupancy_prefix,
        anchor_x=int(anchor_x),
        anchor_y=int(anchor_y),
        rect_w=int(ghost_w),
        rect_h=int(ghost_h),
    ) != 0:
        return "terminal_certified_final_result_ghost_rect_anchor_occupied"

    if not _empty_rect_exists(
        occupancy_prefix=occupancy_prefix,
        grid_w=grid_w,
        grid_h=grid_h,
        rect_w=int(ghost_w),
        rect_h=int(ghost_h),
    ):
        return "terminal_certified_final_result_empty_rect_not_witnessed"

    # The better-empty-rect optimality scan only has discriminating power when
    # mandatory facilities constrain the layout. With no mandatory instances,
    # every candidate is trivially feasible on the empty grid and any
    # non-full-grid claim would be "improvable" — that shape exists only in
    # synthetic test projects; the production mandatory set (266 instances) is
    # non-empty and pinned by the frozen-artifact hashes. The witness-existence
    # check above still applies unconditionally.
    if not mandatory_instances:
        return None
    try:
        admissible_min_side = 1 if min_side_admissibility is None else _strict_resume_int(
            min_side_admissibility,
            "project.min_side_admissibility",
        )
    except Exception:
        return "terminal_certified_final_result_solution_geometry_invalid"
    if admissible_min_side <= 0:
        return "terminal_certified_final_result_solution_geometry_invalid"
    best_empty_objective = _best_empty_rect_objective(
        occupancy_prefix=occupancy_prefix,
        grid_w=grid_w,
        grid_h=grid_h,
        min_side_admissibility=int(admissible_min_side),
    )
    claimed_objective = (int(ghost_w) * int(ghost_h), min(int(ghost_w), int(ghost_h)))
    if best_empty_objective > claimed_objective:
        return "terminal_certified_final_result_layout_has_better_empty_rect"
    return None


def _build_occupancy_prefix(
    *,
    occupied_cells: set[tuple[int, int]],
    grid_w: int,
    grid_h: int,
) -> list[list[int]]:
    prefix = [[0 for _ in range(int(grid_h) + 1)] for _ in range(int(grid_w) + 1)]
    for x in range(int(grid_w)):
        running = 0
        for y in range(int(grid_h)):
            running += 1 if (x, y) in occupied_cells else 0
            prefix[x + 1][y + 1] = prefix[x][y + 1] + running
    return prefix


def _occupied_count_in_rect(
    *,
    occupancy_prefix: Sequence[Sequence[int]],
    anchor_x: int,
    anchor_y: int,
    rect_w: int,
    rect_h: int,
) -> int:
    x0 = int(anchor_x)
    y0 = int(anchor_y)
    x1 = x0 + int(rect_w)
    y1 = y0 + int(rect_h)
    return int(
        occupancy_prefix[x1][y1]
        - occupancy_prefix[x0][y1]
        - occupancy_prefix[x1][y0]
        + occupancy_prefix[x0][y0]
    )


def _empty_rect_exists(
    *,
    occupancy_prefix: Sequence[Sequence[int]],
    grid_w: int,
    grid_h: int,
    rect_w: int,
    rect_h: int,
) -> bool:
    if rect_w <= 0 or rect_h <= 0 or rect_w > grid_w or rect_h > grid_h:
        return False
    for anchor_x in range(0, int(grid_w) - int(rect_w) + 1):
        for anchor_y in range(0, int(grid_h) - int(rect_h) + 1):
            if (
                _occupied_count_in_rect(
                    occupancy_prefix=occupancy_prefix,
                    anchor_x=anchor_x,
                    anchor_y=anchor_y,
                    rect_w=int(rect_w),
                    rect_h=int(rect_h),
                )
                == 0
            ):
                return True
    return False


def _best_empty_rect_objective(
    *,
    occupancy_prefix: Sequence[Sequence[int]],
    grid_w: int,
    grid_h: int,
    min_side_admissibility: int,
) -> Tuple[int, int]:
    best = (0, 0)
    min_side = int(min_side_admissibility)
    for rect_w in range(min_side, int(grid_w) + 1):
        for rect_h in range(min_side, int(grid_h) + 1):
            objective = (int(rect_w) * int(rect_h), min(int(rect_w), int(rect_h)))
            if objective <= best:
                continue
            if _empty_rect_exists(
                occupancy_prefix=occupancy_prefix,
                grid_w=int(grid_w),
                grid_h=int(grid_h),
                rect_w=int(rect_w),
                rect_h=int(rect_h),
            ):
                best = objective
    return best


def _load_exact_required_optional_lower_bounds(project_root: Path) -> Dict[str, int]:
    rules_path = project_root / EXACT_HASH_FILES["canonical_rules"]
    generic_path = project_root / EXACT_HASH_FILES["generic_io_requirements"]
    rules = _loads_strict_json_object(rules_path.read_text(encoding="utf-8"))
    generic_io_requirements = _loads_strict_json_object(
        generic_path.read_text(encoding="utf-8")
    )
    if not isinstance(rules, Mapping):
        raise ValueError("canonical_rules must be a JSON object")
    if not isinstance(generic_io_requirements, Mapping):
        raise ValueError("generic_io_requirements must be a JSON object")
    lower_bounds: Dict[str, int] = {}
    for facility_type, count in infer_certified_optional_lower_bounds(
        rules,
        generic_io_requirements,
    ).items():
        required_count = int(count)
        if required_count > 0:
            lower_bounds[str(facility_type)] = required_count
    return lower_bounds


def _load_exact_safe_area_upper_bound(project_root: Optional[Path]) -> Optional[int]:
    if project_root is None:
        return None
    rules_path = project_root / EXACT_HASH_FILES["canonical_rules"]
    generic_path = project_root / EXACT_HASH_FILES["generic_io_requirements"]
    rules = _loads_strict_json_object(rules_path.read_text(encoding="utf-8"))
    instances = _load_validated_mandatory_exact_instances(project_root)
    generic_io_requirements = _loads_strict_json_object(
        generic_path.read_text(encoding="utf-8")
    )
    if not isinstance(rules, Mapping):
        raise ValueError("canonical_rules must be a JSON object")
    if not isinstance(generic_io_requirements, Mapping):
        raise ValueError("generic_io_requirements must be a JSON object")
    grid_w, grid_h = _load_exact_grid_dimensions(project_root) or (0, 0)
    templates = dict(rules.get("facility_templates", {}))
    lower_bound = 0
    for instance in instances:
        facility_type = str(instance.get("facility_type"))
        template = templates[facility_type]
        dims = dict(template["dimensions"])
        lower_bound += int(dims["w"]) * int(dims["h"])
    for facility_type, count in infer_certified_optional_lower_bounds(
        rules,
        generic_io_requirements,
    ).items():
        template = dict(templates[str(facility_type)])
        dims = dict(template["dimensions"])
        lower_bound += int(count) * int(dims["w"]) * int(dims["h"])
    return max(0, int(grid_w) * int(grid_h) - int(lower_bound))


def _strict_candidate_ghost_rect(record: Mapping[str, Any]) -> Tuple[int, int]:
    ghost_rect = record.get("ghost_rect")
    if not isinstance(ghost_rect, Mapping):
        raise ValueError("candidate ghost_rect must be a mapping")
    ghost_w = _strict_resume_int(ghost_rect.get("w"), "candidate.ghost_rect.w")
    ghost_h = _strict_resume_int(ghost_rect.get("h"), "candidate.ghost_rect.h")
    area = _strict_resume_int(ghost_rect.get("area"), "candidate.ghost_rect.area")
    if ghost_w <= 0 or ghost_h <= 0 or area != ghost_w * ghost_h:
        raise ValueError("candidate ghost_rect dimensions must be positive and area-consistent")
    return ghost_w, ghost_h


def _expected_unfiltered_ghost_anchor_index(
    *,
    grid_w: int,
    grid_h: int,
    ghost_w: int,
    ghost_h: int,
    anchor_x: int,
    anchor_y: int,
) -> Optional[int]:
    if ghost_w <= 0 or ghost_h <= 0 or ghost_w > grid_w or ghost_h > grid_h:
        return None
    if anchor_x < 0 or anchor_y < 0:
        return None
    y_count = grid_h - ghost_h + 1
    if anchor_x > grid_w - ghost_w or anchor_y > grid_h - ghost_h:
        return None
    return int(anchor_x) * int(y_count) + int(anchor_y)


def _validate_cut_condition_domain(
    *,
    record: Mapping[str, Any],
    cut: BendersCut,
    grid_dimensions: Optional[Tuple[int, int]],
) -> None:
    if not cut.condition_set:
        return
    if grid_dimensions is None:
        raise ValueError("condition_set domain validation requires canonical grid dimensions")
    grid_w, grid_h = grid_dimensions
    ghost_w, ghost_h = _strict_candidate_ghost_rect(record)
    for key, rect_idx in cut.condition_set.items():
        parsed_anchor = _parse_ghost_anchor_condition_key(str(key))
        if parsed_anchor is None:
            raise ValueError(f"unsupported condition_set key: {key}")
        expected_rect_idx = _expected_unfiltered_ghost_anchor_index(
            grid_w=int(grid_w),
            grid_h=int(grid_h),
            ghost_w=int(ghost_w),
            ghost_h=int(ghost_h),
            anchor_x=int(parsed_anchor[0]),
            anchor_y=int(parsed_anchor[1]),
        )
        if expected_rect_idx is None:
            raise ValueError(f"condition_set ghost anchor is outside the candidate domain: {key}")
        if int(rect_idx) != expected_rect_idx:
            raise ValueError(
                "condition_set ghost anchor index does not match the current "
                f"candidate domain for key {key}"
            )


def candidate_key(ghost_w: int, ghost_h: int) -> str:
    return f"{ghost_w}x{ghost_h}"


def _candidate_objective_from_rect(ghost_w: int, ghost_h: int) -> Tuple[int, int]:
    return (int(ghost_w) * int(ghost_h), min(int(ghost_w), int(ghost_h)))


def _final_result_objective(result: Mapping[str, Any]) -> Tuple[int, int]:
    ghost_rect = result.get("ghost_rect")
    if not isinstance(ghost_rect, Mapping):
        return (0, 0)
    try:
        ghost_w = int(ghost_rect.get("w", 0))
        ghost_h = int(ghost_rect.get("h", 0))
    except Exception:
        return (0, 0)
    return _candidate_objective_from_rect(ghost_w, ghost_h)


def _has_certified_final_result(state: Mapping[str, Any]) -> bool:
    return isinstance(state.get("final_result"), Mapping)


def _fsync_directory(path: Path) -> None:
    try:
        dir_fd = os.open(str(path), os.O_RDONLY)
    except Exception:
        return
    try:
        os.fsync(dir_fd)
    except Exception:
        pass
    finally:
        os.close(dir_fd)


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-",
        suffix=".json",
        dir=str(path.parent),
    )
    tmp_path = Path(raw_tmp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp_path), str(path))
        _fsync_directory(path.parent)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def _bound_state_defaults() -> Dict[str, Any]:
    """P1 #7a prep: optional bound_state block per candidate.

    All fields default None. Filled in when master writes back lb/ub/gap
    after a wave (P1 #7 主体阶段集成). schema_version 不 bump — 这个 block
    是可选扩展, 旧 v3 reader 见到忽略, 新 reader 见缺失给默认。
    """
    return {
        "lb": None,            # int | None  : best dual lower bound
        "ub": None,            # int | None  : best primal incumbent
        "gap": None,           # float | None: (ub - lb) / max(|ub|, 1)
        "epsilon_target": None,  # float | None: 0.05/0.01/0.0 三阶段
        "prover": None,          # str | None: "master_cpsat" / "binding_lbbd" / etc.
        "observed_at": None,     # iso str | None
        "model_hash": None,      # str | None: 跨 wave 一致性校验
    }


def _candidate_defaults(ghost_w: int, ghost_h: int) -> Dict[str, Any]:
    return {
        "ghost_rect": {"w": int(ghost_w), "h": int(ghost_h), "area": int(ghost_w) * int(ghost_h)},
        "attempts": 0,
        "started_at": None,
        "updated_at": None,
        "finished_at": None,
        "status": "UNKNOWN",
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
        # P1 #7a prep: optional. 旧 v3 checkpoint 缺这个字段, reader 给默认。
        "bound_state": _bound_state_defaults(),
    }


def _build_initial_state(
    *,
    current_hashes: Mapping[str, str],
    campaign_hours: float,
    reset_reason: Optional[str],
) -> Dict[str, Any]:
    timestamp = now_iso()
    return {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "solve_mode": "certified_exact",
        "campaign_hours": float(campaign_hours),
        "created_at": timestamp,
        "updated_at": timestamp,
        "artifact_hashes": {str(k): str(v) for k, v in current_hashes.items()},
        "master_domain_contract": _default_master_domain_contract(),
        "proof_summary_schema_version": PROOF_SUMMARY_SCHEMA_VERSION,
        "reset_reason": reset_reason,
        "final_result": None,
        "final_status": None,
        "last_stop_reason": None,
        "terminal_frontier_evidence": None,
        # P2 #14 数据收集 audit: A 方案 (EXACT_OUTER_SKIP_UNKNOWN) 让 UNKNOWN
        # candidate 跳过 frontier → declare 出的 "最优" 可能漏 UNKNOWN 实际为
        # FEASIBLE, 违反 max_lex 严格证明. 此字段标记 campaign declare 严格度:
        #   "strict" (default) — declare 是真 max_lex 最优 (严格证明)
        #   "best_effort"      — historical/data-collection states only; resume/export
        #                         must not inherit terminal certified evidence from it.
        "declare_mode": "strict",
        "candidates": {},
    }


def _validate_candidate_record(
    record_key: str,
    record: Mapping[str, Any],
    *,
    grid_dimensions: Optional[Tuple[int, int]] = None,
    safe_area_upper_bound: Optional[int] = None,
) -> Optional[str]:
    missing = sorted(REQUIRED_CANDIDATE_FIELDS.difference(record.keys()))
    if missing:
        return f"candidate_missing_field:{record_key}:{missing[0]}"

    ghost_rect = record.get("ghost_rect")
    if not isinstance(ghost_rect, Mapping):
        return f"candidate_invalid_ghost_rect:{record_key}"
    for field in ("w", "h", "area"):
        if field not in ghost_rect:
            return f"candidate_missing_ghost_rect_field:{record_key}:{field}"
    try:
        ghost_w, ghost_h = _strict_candidate_ghost_rect(record)
    except Exception:
        return f"candidate_invalid_ghost_rect:{record_key}"
    if record_key != candidate_key(ghost_w, ghost_h):
        return f"candidate_key_ghost_rect_mismatch:{record_key}"

    try:
        _strict_resume_int(record.get("attempts", 0), f"candidate.{record_key}.attempts")
        _strict_resume_int(
            record.get("loaded_exact_safe_cut_count", 0),
            f"candidate.{record_key}.loaded_exact_safe_cut_count",
        )
        _strict_resume_int(
            record.get("generated_exact_safe_cut_count", 0),
            f"candidate.{record_key}.generated_exact_safe_cut_count",
        )
    except Exception:
        return f"candidate_invalid_count:{record_key}"

    status = str(record.get("status", ""))
    if status not in VALID_CANDIDATE_STATUSES:
        return f"candidate_invalid_status:{record_key}:{status}"
    if status == "CERTIFIED" and not isinstance(record.get("solution"), Mapping):
        return f"candidate_certified_solution_missing:{record_key}"

    if not isinstance(record.get("proof_summary"), Mapping):
        return f"candidate_invalid_proof_summary:{record_key}"
    exact_safe_cuts = record.get("exact_safe_cuts")
    if not isinstance(exact_safe_cuts, list):
        return f"candidate_invalid_exact_safe_cuts:{record_key}"
    for index, raw_cut in enumerate(exact_safe_cuts):
        if not isinstance(raw_cut, Mapping):
            return f"candidate_invalid_exact_safe_cut:{record_key}:{index}"
        try:
            cut = BendersCut.from_dict(raw_cut)
        except Exception:
            return f"candidate_invalid_exact_safe_cut:{record_key}:{index}"
        if cut.source_mode != "certified_exact" or cut.exact_safe is not True:
            return f"candidate_invalid_exact_safe_cut:{record_key}:{index}"
        try:
            _validate_cut_condition_domain(
                record=record,
                cut=cut,
                grid_dimensions=grid_dimensions,
            )
        except Exception:
            return f"candidate_invalid_exact_safe_cut:{record_key}:{index}"

    for field in ("started_at", "updated_at"):
        if record.get(field) is None:
            return f"candidate_missing_timestamp:{record_key}:{field}"
    if status == "RUNNING" and record.get("finished_at") is not None:
        return f"candidate_running_has_finished_at:{record_key}"
    if status != "RUNNING" and record.get("finished_at") is None:
        return f"candidate_terminal_missing_finished_at:{record_key}"
    return None


def _validate_resume_state(
    state: Mapping[str, Any],
    *,
    current_hashes: Mapping[str, str],
    project_root: Optional[Path] = None,
) -> Optional[str]:
    try:
        schema_version = _strict_resume_int(state.get("schema_version"), "schema_version")
    except Exception:
        return "schema_version_mismatch"
    if schema_version != CAMPAIGN_SCHEMA_VERSION:
        return "schema_version_mismatch"
    if str(state.get("solve_mode")) != "certified_exact":
        return "solve_mode_mismatch"
    missing = sorted(REQUIRED_STATE_FIELDS.difference(state.keys()))
    if missing:
        return f"missing_state_field:{missing[0]}"
    domain_contract_reason = _validate_master_domain_contract(state)
    if domain_contract_reason is not None:
        return domain_contract_reason
    try:
        proof_summary_schema_version = _strict_resume_int(
            state.get("proof_summary_schema_version"),
            "proof_summary_schema_version",
        )
    except Exception:
        return "proof_summary_schema_version_mismatch"
    if proof_summary_schema_version != PROOF_SUMMARY_SCHEMA_VERSION:
        return "proof_summary_schema_version_mismatch"
    if not isinstance(state.get("artifact_hashes"), Mapping):
        return "artifact_hashes_invalid"
    if dict(state.get("artifact_hashes", {})) != dict(current_hashes):
        return "artifact_hash_mismatch"
    if not isinstance(state.get("candidates"), Mapping):
        return "candidates_invalid"
    if state.get("last_stop_reason") is not None:
        stop_reason = state.get("last_stop_reason")
        if not isinstance(stop_reason, Mapping) or "reason" not in stop_reason:
            return "last_stop_reason_invalid"
    final_result = state.get("final_result")
    final_status = state.get("final_status")
    if final_result is not None and not isinstance(final_result, Mapping):
        return "final_result_invalid"
    if final_status is not None and not isinstance(final_status, str):
        return "final_status_invalid"
    if final_result is not None and final_status != "CERTIFIED":
        return "final_status_mismatch"
    declare_mode = state.get("declare_mode")
    if not isinstance(declare_mode, str) or declare_mode not in {"strict", "best_effort"}:
        return "declare_mode_invalid"
    if final_result is not None and declare_mode != "strict":
        return "final_result_declare_mode_not_strict"
    try:
        grid_dimensions = _load_exact_grid_dimensions(project_root)
        safe_area_upper_bound = _load_exact_safe_area_upper_bound(project_root)
    except Exception:
        return "canonical_grid_invalid"
    try:
        min_side_admissibility = (
            _load_exact_min_side_admissibility(project_root)
            if has_certified_export_surface(state)
            else None
        )
    except Exception:
        return "canonical_min_side_admissibility_invalid"

    terminal_violation = certified_terminal_evidence_violation(
        state,
        grid_dimensions=grid_dimensions,
        safe_area_upper_bound=safe_area_upper_bound,
        min_side_admissibility=min_side_admissibility,
    )
    if terminal_violation is not None:
        return terminal_violation

    for record_key, record in dict(state.get("candidates", {})).items():
        if not isinstance(record, Mapping):
            return f"candidate_invalid:{record_key}"
        reason = _validate_candidate_record(
            str(record_key),
            record,
            grid_dimensions=grid_dimensions,
        )
        if reason is not None:
            return reason
    if project_root is not None and has_terminal_full_frontier_certified_evidence(state):
        final_result_for_project = state.get("final_result")
        if isinstance(final_result_for_project, Mapping) and grid_dimensions is not None:
            solution_reason = _validate_terminal_solution_against_project(
                final_result=final_result_for_project,
                project_root=Path(project_root),
                grid_dimensions=grid_dimensions,
                min_side_admissibility=min_side_admissibility,
            )
            if solution_reason is not None:
                return solution_reason
            ghost_pick_reason = _terminal_candidate_ghost_pick_binding_violation(
                state,
                final_result=final_result_for_project,
            )
            if ghost_pick_reason is not None:
                return ghost_pick_reason
    return None


def validate_exact_campaign_resume_state(
    state: Mapping[str, Any],
    current_hashes: Mapping[str, str],
    *,
    project_root: Optional[Path] = None,
) -> Optional[str]:
    return _validate_resume_state(
        state,
        current_hashes=current_hashes,
        project_root=project_root,
    )


def has_certified_export_surface(state: Mapping[str, Any]) -> bool:
    """Return True when a state carries any terminal/certified-looking export claim."""

    if str(state.get("final_status")) == "CERTIFIED":
        return True
    if isinstance(state.get("final_result"), Mapping):
        return True
    stop_record = state.get("last_stop_reason")
    return isinstance(stop_record, Mapping) and str(stop_record.get("status")) == "CERTIFIED"


def has_terminal_full_frontier_certified_evidence(state: Mapping[str, Any]) -> bool:
    """Return True only for strict terminal full-frontier CERTIFIED evidence."""

    if str(state.get("declare_mode")) != "strict":
        return False
    if str(state.get("final_status")) != "CERTIFIED":
        return False
    if not isinstance(state.get("final_result"), Mapping):
        return False
    stop_record = state.get("last_stop_reason")
    if not isinstance(stop_record, Mapping):
        return False
    return (
        str(stop_record.get("status")) == "CERTIFIED"
        and str(stop_record.get("reason")) == TERMINAL_FULL_FRONTIER_CERTIFIED_REASON
    )


def terminal_certified_final_result_violation(
    state: Mapping[str, Any],
    *,
    grid_dimensions: Optional[Tuple[int, int]] = None,
    safe_area_upper_bound: Optional[int] = None,
    min_side_admissibility: Optional[int] = None,
) -> Optional[str]:
    """Return a fail-closed reason for malformed terminal CERTIFIED result evidence."""

    if not has_terminal_full_frontier_certified_evidence(state):
        return None
    stop_reason = _terminal_certified_last_stop_reason_violation(state)
    if stop_reason is not None:
        return stop_reason
    final_result = state.get("final_result")
    if not isinstance(final_result, Mapping):
        return "terminal_certified_final_result_invalid"
    unknown_final_result_fields = sorted(
        str(field)
        for field in final_result.keys()
        if str(field) not in TERMINAL_CERTIFIED_FINAL_RESULT_ALLOWED_FIELDS
    )
    if unknown_final_result_fields:
        return f"terminal_certified_final_result_unknown_field:{unknown_final_result_fields[0]}"
    if str(final_result.get("search_status", "")) != "CERTIFIED":
        return "terminal_certified_final_result_status_invalid"
    search_stats_reason = _terminal_certified_search_stats_violation(final_result.get("search_stats"))
    if search_stats_reason is not None:
        return search_stats_reason

    ghost_rect = final_result.get("ghost_rect")
    if not isinstance(ghost_rect, Mapping):
        return "terminal_certified_final_result_ghost_rect_invalid"
    ghost_rect_unknown_field = _terminal_certified_ghost_rect_unknown_field(ghost_rect)
    if ghost_rect_unknown_field is not None:
        return ghost_rect_unknown_field
    try:
        ghost_w = _strict_resume_int(ghost_rect.get("w"), "final_result.ghost_rect.w")
        ghost_h = _strict_resume_int(ghost_rect.get("h"), "final_result.ghost_rect.h")
        area = _strict_resume_int(ghost_rect.get("area"), "final_result.ghost_rect.area")
    except Exception:
        return "terminal_certified_final_result_ghost_rect_invalid"
    if ghost_w <= 0 or ghost_h <= 0 or area != ghost_w * ghost_h:
        return "terminal_certified_final_result_ghost_rect_invalid"
    if min_side_admissibility is not None and min(int(ghost_w), int(ghost_h)) < int(
        min_side_admissibility
    ):
        return "terminal_certified_final_result_below_admissibility"

    placement_solution = final_result.get("placement_solution")
    if not isinstance(placement_solution, Mapping):
        return "terminal_certified_final_result_solution_missing"

    candidates = state.get("candidates")
    if not isinstance(candidates, Mapping):
        return "terminal_certified_candidate_record_missing"
    key = candidate_key(ghost_w, ghost_h)
    record = candidates.get(key)
    if not isinstance(record, Mapping):
        return "terminal_certified_candidate_record_missing"
    try:
        record_w, record_h = _strict_candidate_ghost_rect(record)
    except Exception:
        return "terminal_certified_candidate_record_ghost_rect_invalid"
    if record_w != ghost_w or record_h != ghost_h:
        return "terminal_certified_candidate_record_ghost_rect_mismatch"
    if str(record.get("status", "")) != "CERTIFIED":
        return "terminal_certified_candidate_record_not_certified"
    record_solution = record.get("solution")
    if not isinstance(record_solution, Mapping):
        return "terminal_certified_candidate_solution_missing"
    if _solution_without_ghost_marker(record_solution) != _solution_without_ghost_marker(placement_solution):
        return "terminal_certified_final_result_solution_mismatch"

    final_objective = _candidate_objective_from_rect(ghost_w, ghost_h)
    for other_key, other_record in candidates.items():
        if not isinstance(other_record, Mapping):
            continue
        if str(other_record.get("status", "")) != "CERTIFIED":
            continue
        try:
            other_w, other_h = _strict_candidate_ghost_rect(other_record)
        except Exception:
            return "terminal_certified_candidate_record_ghost_rect_invalid"
        if _candidate_objective_from_rect(other_w, other_h) > final_objective:
            return "terminal_certified_final_result_not_best_candidate"

    frontier_reason = terminal_frontier_evidence_violation(
        evidence=state.get("terminal_frontier_evidence"),
        candidate_records=candidates,
        final_result=final_result,
        grid_dimensions=grid_dimensions,
        safe_area_upper_bound=safe_area_upper_bound,
        min_side_admissibility=min_side_admissibility,
    )
    if frontier_reason is not None:
        return frontier_reason
    return None


def has_valid_terminal_full_frontier_certified_evidence(state: Mapping[str, Any]) -> bool:
    """Return True only when terminal CERTIFIED state and candidate evidence agree."""

    return (
        has_terminal_full_frontier_certified_evidence(state)
        and terminal_certified_final_result_violation(state) is None
    )


def terminal_certified_final_result_violation_for_project(
    state: Mapping[str, Any],
    *,
    project_root: Path,
) -> Optional[str]:
    """Return a fail-closed terminal-evidence reason bound to the project domain."""

    try:
        resolved_project_root = Path(project_root)
        grid_dimensions = _load_exact_grid_dimensions(resolved_project_root)
        safe_area_upper_bound = _load_exact_safe_area_upper_bound(resolved_project_root)
    except Exception:
        return "canonical_grid_invalid"
    try:
        min_side_admissibility = _load_exact_min_side_admissibility(resolved_project_root)
    except Exception:
        return "canonical_min_side_admissibility_invalid"
    reason = terminal_certified_final_result_violation(
        state,
        grid_dimensions=grid_dimensions,
        safe_area_upper_bound=safe_area_upper_bound,
        min_side_admissibility=min_side_admissibility,
    )
    if reason is not None:
        return reason
    final_result = state.get("final_result")
    if isinstance(final_result, Mapping):
        solution_reason = _validate_terminal_solution_against_project(
            final_result=final_result,
            project_root=resolved_project_root,
            grid_dimensions=grid_dimensions,
            min_side_admissibility=min_side_admissibility,
        )
        if solution_reason is not None:
            return solution_reason
        return _terminal_candidate_ghost_pick_binding_violation(
            state,
            final_result=final_result,
        )
    return None


def has_valid_terminal_full_frontier_certified_evidence_for_project(
    state: Mapping[str, Any],
    *,
    project_root: Path,
) -> bool:
    """Return True only when terminal evidence is replayable on the current project domain."""

    if not has_terminal_full_frontier_certified_evidence(state):
        return False
    return (
        terminal_certified_final_result_violation_for_project(
            state,
            project_root=project_root,
        )
        is None
    )


def certified_terminal_evidence_violation(
    state: Mapping[str, Any],
    *,
    grid_dimensions: Optional[Tuple[int, int]] = None,
    safe_area_upper_bound: Optional[int] = None,
    min_side_admissibility: Optional[int] = None,
) -> Optional[str]:
    """Return a fail-closed reason for stale or contradictory certified export claims."""

    if has_certified_export_surface(state) and not has_terminal_full_frontier_certified_evidence(state):
        return "terminal_certified_frontier_evidence_invalid"
    return terminal_certified_final_result_violation(
        state,
        grid_dimensions=grid_dimensions,
        safe_area_upper_bound=safe_area_upper_bound,
        min_side_admissibility=min_side_admissibility,
    )


@dataclass
class ExactCampaign:
    project_root: Path
    path: Path
    state: Dict[str, Any]
    resumed: bool
    compatible_hashes: bool

    @classmethod
    def load_or_create(
        cls,
        project_root: Path,
        campaign_hours: float = 168.0,
        resume: bool = False,
        filename: str = DEFAULT_CAMPAIGN_FILENAME,
    ) -> "ExactCampaign":
        checkpoints_dir = project_root / "data" / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        path = checkpoints_dir / filename
        current_hashes = compute_exact_artifact_hashes(project_root)

        reset_reason: Optional[str] = None
        if resume and path.exists():
            try:
                loaded_state = _loads_strict_json_object(path.read_text(encoding="utf-8"))
            except Exception:
                reset_reason = "state_json_invalid"
            else:
                if isinstance(loaded_state, Mapping):
                    reset_reason = _validate_resume_state(
                        loaded_state,
                        current_hashes=current_hashes,
                        project_root=project_root,
                    )
                    if reset_reason is None:
                        state = dict(loaded_state)
                        state["updated_at"] = now_iso()
                        state["reset_reason"] = None
                        # Allow extending campaign budget on resume
                        if campaign_hours > float(state.get("campaign_hours", 0)):
                            state["campaign_hours"] = float(campaign_hours)
                        # Clear time-budget-exhausted stop so campaign can continue
                        stop = state.get("last_stop_reason")
                        if (
                            isinstance(stop, Mapping)
                            and stop.get("reason") == "campaign_time_budget_exhausted"
                        ):
                            state["last_stop_reason"] = None
                            state["final_status"] = None
                        return cls(
                            project_root=project_root,
                            path=path,
                            state=state,
                            resumed=True,
                            compatible_hashes=True,
                        )
                else:
                    reset_reason = "state_payload_invalid"

        state = _build_initial_state(
            current_hashes=current_hashes,
            campaign_hours=campaign_hours,
            reset_reason=reset_reason,
        )
        return cls(
            project_root=project_root,
            path=path,
            state=state,
            resumed=False,
            compatible_hashes=(reset_reason is None),
        )

    @property
    def artifact_hashes(self) -> Dict[str, str]:
        return dict(self.state.get("artifact_hashes", {}))

    @property
    def campaign_hours(self) -> float:
        return float(self.state.get("campaign_hours", 168.0))

    @property
    def reset_reason(self) -> Optional[str]:
        value = self.state.get("reset_reason")
        return None if value is None else str(value)

    def remaining_seconds(self) -> float:
        created_at = str(self.state.get("created_at", now_iso()))
        elapsed = max(0.0, now_ts() - iso_to_ts(created_at))
        return max(0.0, self.campaign_hours * 3600.0 - elapsed)

    def elapsed_seconds(self) -> float:
        """P1 #7 main: 给 outer_search 三阶段 ε 调度算当前 elapsed 用."""
        created_at = str(self.state.get("created_at", now_iso()))
        return max(0.0, now_ts() - iso_to_ts(created_at))

    def is_compatible_with_current_hashes(self) -> bool:
        return self.state.get("artifact_hashes") == compute_exact_artifact_hashes(self.project_root)

    def get_candidate_record(self, ghost_w: int, ghost_h: int) -> Optional[Dict[str, Any]]:
        record = self.state.get("candidates", {}).get(candidate_key(ghost_w, ghost_h))
        return dict(record) if isinstance(record, dict) else None

    def get_candidate_cuts(self, ghost_w: int, ghost_h: int) -> list[Dict[str, Any]]:
        record = self.get_candidate_record(ghost_w, ghost_h) or {}
        return list(record.get("exact_safe_cuts", []))

    # P1 #7a prep: bound_state read/write helpers (P1 #7d guard 也用这俩).
    def get_candidate_bound_state(
        self, ghost_w: int, ghost_h: int
    ) -> Dict[str, Any]:
        """Return current bound_state dict (default-filled if missing)."""
        record = self.get_candidate_record(ghost_w, ghost_h) or {}
        bound = record.get("bound_state")
        if isinstance(bound, Mapping):
            # Merge with defaults so新增字段也有 default
            merged = _bound_state_defaults()
            merged.update(dict(bound))
            return merged
        return _bound_state_defaults()

    def update_candidate_bound_state(
        self,
        ghost_w: int,
        ghost_h: int,
        *,
        lb: Optional[int] = None,
        ub: Optional[int] = None,
        gap: Optional[float] = None,
        epsilon_target: Optional[float] = None,
        prover: Optional[str] = None,
        model_hash: Optional[str] = None,
        regression_tolerance: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Update bound_state for the given candidate. None args 留旧值不变.

        P1 #7d guard: 如果 new_lb < old_lb - regression_tolerance 触发
        BOUND_REGRESSION audit event (append 到 state['audit_log']) 但不
        阻塞 — model_hash 可能合法变化, 需人审。

        Returns: 触发的 audit entry (dict) 或 None.
        """
        key = candidate_key(ghost_w, ghost_h)
        candidates = self.state.setdefault("candidates", {})
        record = candidates.get(key)
        if not isinstance(record, dict):
            record = _candidate_defaults(ghost_w, ghost_h)
            record["started_at"] = now_iso()
            record["updated_at"] = now_iso()
            candidates[key] = record
        bound = record.get("bound_state")
        if not isinstance(bound, dict):
            bound = _bound_state_defaults()

        old_lb = bound.get("lb")
        old_model_hash = bound.get("model_hash")

        if lb is not None:
            bound["lb"] = int(lb)
        if ub is not None:
            bound["ub"] = int(ub)
        if gap is not None:
            bound["gap"] = float(gap)
        if epsilon_target is not None:
            bound["epsilon_target"] = float(epsilon_target)
        if prover is not None:
            bound["prover"] = str(prover)
        if model_hash is not None:
            bound["model_hash"] = str(model_hash)
        bound["observed_at"] = now_iso()
        record["bound_state"] = bound
        record["updated_at"] = now_iso()
        self.state["updated_at"] = now_iso()

        # P1 #7d bound regression guard: 检测 lb 是否退化。
        audit_entry: Optional[Dict[str, Any]] = None
        if (
            lb is not None
            and isinstance(old_lb, int)
            and int(lb) < int(old_lb) - int(regression_tolerance)
        ):
            audit_entry = {
                "ts": now_iso(),
                "candidate_key": key,
                "event": "BOUND_REGRESSION",
                "old_lb": int(old_lb),
                "new_lb": int(lb),
                "tolerance": int(regression_tolerance),
                "model_hash_old": old_model_hash,
                "model_hash_new": bound.get("model_hash"),
                "prover": bound.get("prover"),
            }
            audit_log = self.state.setdefault("audit_log", [])
            if isinstance(audit_log, list):
                audit_log.append(audit_entry)
        return audit_entry

    def get_audit_log(self) -> list[Dict[str, Any]]:
        """P1 #7d: read accumulated audit events (BOUND_REGRESSION 等)."""
        log = self.state.get("audit_log", [])
        return list(log) if isinstance(log, list) else []

    def mark_candidate_started(self, ghost_w: int, ghost_h: int) -> None:
        key = candidate_key(ghost_w, ghost_h)
        candidates = self.state.setdefault("candidates", {})
        existing = candidates.get(key, {})
        record = _candidate_defaults(ghost_w, ghost_h)
        if isinstance(existing, Mapping):
            record.update(dict(existing))

        timestamp = now_iso()
        record["status"] = "RUNNING"
        record["attempts"] = int(record.get("attempts", 0)) + 1
        record["started_at"] = timestamp
        record["updated_at"] = timestamp
        record["finished_at"] = None

        candidates[key] = record
        self.state["last_stop_reason"] = None
        if self.state.get("final_result") is None:
            self.state["final_status"] = None
        self.state["updated_at"] = timestamp

    def mark_candidate_result(
        self,
        ghost_w: int,
        ghost_h: int,
        status: str,
        *,
        exact_safe_cuts: Optional[list[Mapping[str, Any]]] = None,
        solution: Optional[Mapping[str, Any]] = None,
        proof_summary: Optional[Mapping[str, Any]] = None,
        loaded_exact_safe_cut_count: Optional[int] = None,
        generated_exact_safe_cut_count: Optional[int] = None,
    ) -> None:
        key = candidate_key(ghost_w, ghost_h)
        candidates = self.state.setdefault("candidates", {})
        existing = candidates.get(key, {})
        record = _candidate_defaults(ghost_w, ghost_h)
        if isinstance(existing, Mapping):
            record.update(dict(existing))

        timestamp = now_iso()
        record["status"] = str(status)
        record["updated_at"] = timestamp
        record["finished_at"] = timestamp
        if record.get("started_at") is None:
            record["started_at"] = timestamp
        record["proof_summary"] = dict(proof_summary or {})

        if exact_safe_cuts is not None:
            record["exact_safe_cuts"] = [dict(cut) for cut in exact_safe_cuts]
        else:
            record["exact_safe_cuts"] = list(record.get("exact_safe_cuts", []))

        if loaded_exact_safe_cut_count is not None:
            record["loaded_exact_safe_cut_count"] = _strict_resume_int(
                loaded_exact_safe_cut_count,
                "loaded_exact_safe_cut_count",
            )
        else:
            record["loaded_exact_safe_cut_count"] = _strict_resume_int(
                record.get("loaded_exact_safe_cut_count", 0),
                "loaded_exact_safe_cut_count",
            )

        if generated_exact_safe_cut_count is not None:
            record["generated_exact_safe_cut_count"] = _strict_resume_int(
                generated_exact_safe_cut_count,
                "generated_exact_safe_cut_count",
            )
        else:
            record["generated_exact_safe_cut_count"] = _strict_resume_int(
                record.get("generated_exact_safe_cut_count", 0),
                "generated_exact_safe_cut_count",
            )

        if solution is not None and status == "CERTIFIED":
            # Candidate-level CERTIFIED evidence is only an incumbent until the
            # outer frontier has been exhausted.  Do not promote it to
            # state["final_result"] here: UNKNOWN/time-budget/worker-failure stops
            # must remain non-terminal and must not export best-effort evidence as
            # a full-frontier certificate.
            record["solution"] = dict(solution)
            if str(self.state.get("declare_mode")) != "strict":
                record["proof_summary"] = dict(record.get("proof_summary", {}))
                record["proof_summary"]["final_result_blocked_reason"] = (
                    "final_result_requires_strict_declare_mode"
                )
        elif status != "CERTIFIED":
            record.pop("solution", None)

        candidates[key] = record
        self.state["updated_at"] = timestamp

    def update_candidate_running_proof_summary(
        self,
        ghost_w: int,
        ghost_h: int,
        proof_summary: Mapping[str, Any],
    ) -> None:
        key = candidate_key(ghost_w, ghost_h)
        candidates = self.state.setdefault("candidates", {})
        existing = candidates.get(key, {})
        record = _candidate_defaults(ghost_w, ghost_h)
        if isinstance(existing, Mapping):
            record.update(dict(existing))

        if str(record.get("status")) != "RUNNING":
            return

        timestamp = now_iso()
        existing_summary = record.get("proof_summary")
        merged_summary = dict(existing_summary) if isinstance(existing_summary, Mapping) else {}
        merged_summary.update(dict(proof_summary or {}))
        record["proof_summary"] = merged_summary
        record["updated_at"] = timestamp
        candidates[key] = record
        self.state["updated_at"] = timestamp

    def mark_campaign_stopped(self, reason: str, status: Optional[str] = None) -> None:
        timestamp = now_iso()
        stop_record = {
            "reason": str(reason),
            "status": None if status is None else str(status),
            "updated_at": timestamp,
        }
        self.state["last_stop_reason"] = stop_record
        if status is not None:
            self.state["final_status"] = str(status)
        if (
            str(stop_record.get("status")) != "CERTIFIED"
            or str(stop_record.get("reason")) != TERMINAL_FULL_FRONTIER_CERTIFIED_REASON
        ):
            self.state["terminal_frontier_evidence"] = None
        self.state["updated_at"] = timestamp

    def best_certified_result(self) -> Optional[Dict[str, Any]]:
        if not has_valid_terminal_full_frontier_certified_evidence_for_project(
            self.state,
            project_root=self.project_root,
        ):
            return None
        result = self.state.get("final_result")
        if not isinstance(result, dict):
            return None
        result_copy = dict(result)
        result_copy["search_status"] = "CERTIFIED"
        return result_copy

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state["updated_at"] = now_iso()
        atomic_write_json(self.path, self.state)
