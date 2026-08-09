"""Small artifact and terminal-result proof core for the PR2 L0 verifier child."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from src.models.master_model import (
    POSE_LEVEL_OPTIONAL_OPERATIONS,
    POSE_LEVEL_OPTIONAL_TEMPLATES,
    infer_certified_optional_lower_bounds_for_instances,
    load_generic_io_requirements_artifact,
)
from src.search.certified_artifact_contract import (
    LOCKED_EXACT_ARTIFACT_SHA256,
    LOCKED_EXACT_ARTIFACT_PATHS,
    certified_project_uses_locked_artifact_contract,
    validate_locked_exact_artifact_contract,
    validate_locked_p1_2_close_kernel,
)
from src.search.pr2_l0_frontier_core import (
    TERMINAL_FRONTIER_OBJECTIVE,
    terminal_frontier_evidence_violation,
)

TERMINAL_FULL_FRONTIER_CERTIFIED_REASON = "search_exhausted_all_candidates"
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

EXACT_HASH_FILES = {
    key: LOCKED_EXACT_ARTIFACT_PATHS[key]
    for key in (
        "mandatory_exact_instances",
        "candidate_placements",
        "canonical_rules",
        "generic_io_requirements",
    )
}
OPTIONAL_EXACT_HASH_FILES = {
    # Runtime preprocess profiles still consume utility/cycle-group declarations
    # from preprocess_plan.json.  Bind it to checkpoints when present so a plan
    # edit cannot ride on stale exact artifacts.
    "preprocess_plan": LOCKED_EXACT_ARTIFACT_PATHS["preprocess_plan"],
    # The exact flow verifier reads this file directly when present.  Treat its
    # absence as an explicit artifact state and bind its bytes whenever present.
    "commodity_demands": "data/preprocessed/commodity_demands.json",
}
MISSING_OPTIONAL_EXACT_ARTIFACT_HASH = "__MISSING_OPTIONAL_EXACT_ARTIFACT__"
CERTIFIED_EXACT_SOURCE_DIGEST_KEY = "certified_exact_source_tree"

__all__ = (
    "CERTIFIED_EXACT_SOURCE_DIGEST_KEY",
    "CERTIFIED_EXACT_SOURCE_HASH_FILES",
    "EXACT_HASH_FILES",
    "MISSING_OPTIONAL_EXACT_ARTIFACT_HASH",
    "OPTIONAL_EXACT_HASH_FILES",
    "canonical_candidate_geometry_rederivation_violation",
    "TERMINAL_FULL_FRONTIER_CERTIFIED_REASON",
    "compute_certified_exact_source_digest",
    "compute_exact_artifact_hashes",
    "has_terminal_full_frontier_certified_evidence",
    "has_valid_terminal_full_frontier_certified_evidence",
    "sha256_file",
    "terminal_certified_final_result_project_precheck_violation",
    "terminal_certified_final_result_violation",
)


def _discover_certified_exact_source_hash_files() -> tuple[str, ...]:
    """Return the conservative production source surface bound to checkpoints.

    A hand-maintained import list is not a sound source authority: a proof-bearing
    sink can move behavior behind a newly imported module without changing the
    digest.  Bind every production Python module and script instead.  Tests are
    deliberately excluded because they do not execute on the certified runtime
    path.  Experiment descriptors are included when present so the no-close
    ablation identity is also checkpoint-bound without requiring intentionally
    removed close-kernel files.
    """

    source_root = Path(__file__).resolve().parent.parent.parent
    relative_paths: set[str] = {
        path.relative_to(source_root).as_posix()
        for path in source_root.glob("*.py")
        if path.is_file()
    }
    for path in (source_root / "src").rglob("*.py"):
        relative_path = path.relative_to(source_root).as_posix()
        if relative_path.startswith("src/tests/"):
            continue
        relative_paths.add(relative_path)
    scripts_root = source_root / "scripts"
    if scripts_root.exists():
        for path in scripts_root.rglob("*.py"):
            relative_paths.add(path.relative_to(source_root).as_posix())
    for relative_path in (
        "NO_CLOSE_KERNEL_EXPERIMENT.md",
        "NO_CLOSE_KERNEL_EXPERIMENT.json",
    ):
        if (source_root / relative_path).is_file():
            relative_paths.add(relative_path)
    return tuple(sorted(relative_paths))


# Every production source file that can be imported or invoked by the exact
# campaign is bound conservatively.  This closes transitive-import blind spots
# on public/release helpers and automatically covers future production modules.
CERTIFIED_EXACT_SOURCE_HASH_FILES = _discover_certified_exact_source_hash_files()


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


def compute_certified_exact_source_digest() -> str:
    """Digest the exact proof kernel source that gives candidate records meaning."""

    source_root = Path(__file__).resolve().parent.parent.parent
    digest = hashlib.sha256()
    for relative_path in CERTIFIED_EXACT_SOURCE_HASH_FILES:
        path = source_root / relative_path
        digest.update(str(relative_path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def compute_exact_artifact_hashes(project_root: Path) -> Dict[str, str]:
    project_root = Path(project_root)
    validate_locked_p1_2_close_kernel(project_root)
    hashes: Dict[str, str] = {}
    artifact_sizes: Dict[str, int] = {}
    for key, relative_path in EXACT_HASH_FILES.items():
        artifact_path = project_root / relative_path
        hashes[key] = sha256_file(artifact_path)
        artifact_sizes[key] = int(artifact_path.stat().st_size)
    for key, relative_path in OPTIONAL_EXACT_HASH_FILES.items():
        artifact_path = project_root / relative_path
        if artifact_path.exists() or _path_has_symlink_component(artifact_path):
            hashes[key] = sha256_file(artifact_path)
            artifact_sizes[key] = int(artifact_path.stat().st_size)
        else:
            hashes[key] = MISSING_OPTIONAL_EXACT_ARTIFACT_HASH
    # A campaign hash is a continuity check, not authority to choose the theorem
    # on first launch. Validate the frozen input contract before recording any
    # process-local source digest or creating checkpoint/export surfaces.
    validate_locked_exact_artifact_contract(
        project_root=project_root,
        artifact_hashes=hashes,
        artifact_sizes=artifact_sizes,
    )
    hashes[CERTIFIED_EXACT_SOURCE_DIGEST_KEY] = compute_certified_exact_source_digest()
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
    grid_dimensions: Optional[Tuple[int, int]] = None,
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
    if str(ghost_pick.get("facility_type", "")) != "ghost_rect":
        return "terminal_certified_candidate_solution_ghost_pick_invalid"
    try:
        pose_idx = _strict_resume_int(
            ghost_pick.get("pose_idx"),
            "candidate.solution.ghost_pick.pose_idx",
        )
    except Exception:
        return "terminal_certified_candidate_solution_ghost_pick_invalid"
    if int(pose_idx) < 0:
        return "terminal_certified_candidate_solution_ghost_pick_invalid"
    if grid_dimensions is not None:
        try:
            grid_w = _strict_resume_int(grid_dimensions[0], "project.grid.width")
            grid_h = _strict_resume_int(grid_dimensions[1], "project.grid.height")
        except Exception:
            return "terminal_certified_candidate_solution_ghost_pick_invalid"
        expected_pose_idx = _expected_unfiltered_ghost_anchor_index(
            grid_w=int(grid_w),
            grid_h=int(grid_h),
            ghost_w=int(ghost_w),
            ghost_h=int(ghost_h),
            anchor_x=int(anchor_x),
            anchor_y=int(anchor_y),
        )
        if expected_pose_idx is None or int(pose_idx) != int(expected_pose_idx):
            return "terminal_certified_candidate_solution_ghost_pick_mismatch"
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


def canonical_candidate_geometry_rederivation_violation(*, project_root: Path) -> Optional[str]:
    try:
        resolved_project_root = Path(project_root).resolve()
        if not certified_project_uses_locked_artifact_contract(resolved_project_root):
            return None
        rules_path = resolved_project_root / EXACT_HASH_FILES["canonical_rules"]
        payload = _loads_strict_json_object(rules_path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("canonical_rules must be a JSON object")
        raw_templates = payload.get("facility_templates")
        if not isinstance(raw_templates, Mapping):
            raise ValueError("canonical_rules.facility_templates must be a JSON object")
        facility_templates = dict(raw_templates)
        from src.placement.placement_generator import generate_all_pools

        pools = generate_all_pools(facility_templates)
        blob = json.dumps(
            {"facility_pools": pools},
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        sha256 = hashlib.sha256(blob).hexdigest()
        if sha256 != LOCKED_EXACT_ARTIFACT_SHA256["candidate_placements"]:
            return "canonical_candidate_geometry_rederivation_mismatch"
        return None
    except Exception:
        return "canonical_candidate_geometry_rederivation_invalid"


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


def _pose_pool_min_occupied_cell_count(
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    facility_type: str,
    *,
    grid_dimensions: Optional[Tuple[int, int]] = None,
) -> int:
    raw_pool = facility_pools.get(str(facility_type))
    if not isinstance(raw_pool, list) or not raw_pool:
        raise ValueError(f"candidate_placements.facility_pools.{facility_type} must be a non-empty array")

    best: Optional[int] = None
    for pose_idx, pose in enumerate(raw_pool):
        if not isinstance(pose, Mapping):
            raise ValueError(
                f"candidate_placements.{facility_type}[{pose_idx}] must be a JSON object"
            )
        cells = set(
            _pose_occupied_cells(
                pose,
                field=f"candidate_placements.{facility_type}[{pose_idx}]",
            )
        )
        if grid_dimensions is not None:
            grid_w, grid_h = grid_dimensions
            if any(
                x < 0 or y < 0 or x >= int(grid_w) or y >= int(grid_h)
                for x, y in cells
            ):
                raise ValueError(
                    f"candidate_placements.{facility_type}[{pose_idx}].occupied_cells out of grid"
                )
        pose_area = len(cells)
        if best is None or pose_area < best:
            best = pose_area

    if best is None:
        raise ValueError(f"candidate_placements.facility_pools.{facility_type} must be non-empty")
    return int(best)


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
        required_optional_lower_bounds = _load_exact_required_optional_lower_bounds(
            project_root
        )
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

    # Batch 5 dominance rule: the provider-aware arithmetic above is a lower bound,
    # never a selected-box upper bound.  Extra pose-optional protocol boxes can have
    # routing-space value, so rejecting selected > required would shrink the proof
    # domain.  This placement-only validator has no binding witness; the fresh fixed
    # witness verifier therefore enforces that every selected optional box binds at
    # least one physical generic-input sink and then proves the routed connection.

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

    # Recompute the layout-level optimum unconditionally.  Even an empty
    # mandatory set has a well-defined optimum (the full grid under the
    # admissibility floor), and accepting a smaller terminal witness would make
    # the public CERTIFIED surface depend on production-only assumptions.
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


def _load_exact_generic_input_slots_by_operation(
    *,
    project_root: Path,
    generic_io_requirements: Mapping[str, Any],
) -> Optional[Dict[str, int]]:
    """Load the shared Batch-5 box/core physical sink-capacity profile."""

    if not generic_io_requirements.get("required_generic_inputs", {}):
        return None
    from src.models.binding_subproblem import load_generic_input_slots_by_operation

    return load_generic_input_slots_by_operation(project_root=project_root)


def _load_exact_required_optional_lower_bounds(
    project_root: Path,
) -> Dict[str, int]:
    rules_path = project_root / EXACT_HASH_FILES["canonical_rules"]
    rules = _loads_strict_json_object(rules_path.read_text(encoding="utf-8"))
    generic_io_requirements = load_generic_io_requirements_artifact(project_root)
    instances = _load_validated_mandatory_exact_instances(project_root)
    if not isinstance(rules, Mapping):
        raise ValueError("canonical_rules must be a JSON object")
    if not isinstance(generic_io_requirements, Mapping):
        raise ValueError("generic_io_requirements must be a JSON object")
    generic_input_slots_by_operation = (
        _load_exact_generic_input_slots_by_operation(
            project_root=project_root,
            generic_io_requirements=generic_io_requirements,
        )
    )
    lower_bounds: Dict[str, int] = {}
    for facility_type, count in infer_certified_optional_lower_bounds_for_instances(
        instances,
        rules,
        generic_io_requirements,
        generic_input_slots_by_operation=generic_input_slots_by_operation,
    ).items():
        required_count = int(count)
        if required_count > 0:
            lower_bounds[str(facility_type)] = required_count
    return lower_bounds


def _load_exact_safe_area_upper_bound(
    project_root: Optional[Path],
) -> Optional[int]:
    if project_root is None:
        return None
    rules_path = project_root / EXACT_HASH_FILES["canonical_rules"]
    rules = _loads_strict_json_object(rules_path.read_text(encoding="utf-8"))
    instances = _load_validated_mandatory_exact_instances(project_root)
    facility_pools = _load_exact_facility_pools(project_root)
    generic_io_requirements = load_generic_io_requirements_artifact(project_root)
    if not isinstance(rules, Mapping):
        raise ValueError("canonical_rules must be a JSON object")
    if not isinstance(generic_io_requirements, Mapping):
        raise ValueError("generic_io_requirements must be a JSON object")
    grid_w, grid_h = _load_exact_grid_dimensions(project_root) or (0, 0)
    lower_bound = 0
    for instance in instances:
        facility_type = str(instance.get("facility_type"))
        lower_bound += _pose_pool_min_occupied_cell_count(
            facility_pools,
            facility_type,
            grid_dimensions=(int(grid_w), int(grid_h)),
        )
    generic_input_slots_by_operation = (
        _load_exact_generic_input_slots_by_operation(
            project_root=project_root,
            generic_io_requirements=generic_io_requirements,
        )
    )
    for facility_type, count in infer_certified_optional_lower_bounds_for_instances(
        instances,
        rules,
        generic_io_requirements,
        generic_input_slots_by_operation=generic_input_slots_by_operation,
    ).items():
        lower_bound += int(count) * _pose_pool_min_occupied_cell_count(
            facility_pools,
            str(facility_type),
            grid_dimensions=(int(grid_w), int(grid_h)),
        )
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


def candidate_key(ghost_w: int, ghost_h: int) -> str:
    return f"{ghost_w}x{ghost_h}"


def _candidate_objective_from_rect(ghost_w: int, ghost_h: int) -> Tuple[int, int]:
    return (int(ghost_w) * int(ghost_h), min(int(ghost_w), int(ghost_h)))


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
    candidate_records_override: Optional[Mapping[str, Any]] = None,
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

    candidates = (
        candidate_records_override
        if candidate_records_override is not None
        else state.get("candidates")
    )
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


def terminal_certified_final_result_project_precheck_violation(
    state: Mapping[str, Any],
    *,
    project_root: Path,
) -> Optional[str]:
    """Return local project/witness errors without granting proof authority.

    This precheck exists only to preserve precise fail-closed diagnostics before
    disk-currentness and isolated replay.  A ``None`` result is never sufficient
    for certification; every accepting caller must still execute the sink replay
    validator below.
    """

    try:
        resolved_project_root = Path(project_root).resolve()
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
            grid_dimensions=grid_dimensions,
        )
    return None
