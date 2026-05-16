from __future__ import annotations

import itertools
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b.coordinate_validation.field_channel_delta import (
    _force_fields_for_variant,
)
from src.search.phase3b.coordinate_validation.group_delta import (
    _build_delta_context,
    _candidate_rect,
    _check,
    _compact_greedy,
    _compact_validation,
    _mapping,
    _normalize_solver_profile,
)

PHASE3B_DIRECT_EQUALITY_CORE_EXCHANGE_SOURCE = (
    "phase3b_direct_equality_core_exchange_v1"
)


def build_phase3b_direct_equality_core_exchange(
    project_root: Path,
    *,
    core_paths: Sequence[Path],
    group_id: str,
    candidate: str = "67x13",
    anchor_idx: int = 119,
    field_variant: str = "x_y_mode",
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    subset_size: int = 3,
    max_subsets: int = 16,
    time_limit_seconds: float = 2.0,
    worker_count: int = 1,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    normalized_core_paths = [_resolve_path(project_root, Path(path)) for path in core_paths]
    source_cores = [_source_core_payload(project_root, path) for path in normalized_core_paths]
    union_keys = sorted({key for core in source_cores for key in list(core["final_keys"])})
    subsets = _selected_subsets(
        union_keys,
        source_cores=source_cores,
        subset_size=int(subset_size),
        max_subsets=int(max_subsets),
    )

    try:
        artifact_hashes = compute_exact_artifact_hashes(project_root)
        artifact_hash_error = None
    except Exception as exc:
        artifact_hashes = {}
        artifact_hash_error = f"{type(exc).__name__}: {exc}"

    entries: list[Dict[str, Any]] = []
    context: Dict[str, Any] = {}
    greedy: Dict[str, Any] = {}
    model_error = None
    try:
        context = _build_delta_context(
            project_root,
            candidate=str(candidate),
            anchor_idx=int(anchor_idx),
            master_search_profile=str(master_search_profile),
        )
        group_by_id = {
            str(group.get("group_id", "")): group
            for group in list(context["ordered_groups"])
            if isinstance(group, Mapping)
        }
        group = group_by_id[str(group_id)]
        model = context["model"]
        greedy = model._run_mandatory_greedy_pass(
            ordered_groups=[group],
            candidates_by_group=context["candidates_by_group"],
            blocked_cells=set(),
            stop_on_first_failure=True,
        )
        solver_profile = _normalize_solver_profile(
            None,
            time_limit_seconds=float(time_limit_seconds),
            worker_count=int(worker_count),
        )
        for subset in subsets:
            entries.append(
                _evaluate_subset(
                    model=model,
                    greedy=greedy,
                    subset_keys=list(subset["subset_keys"]),
                    subset_id=str(subset["subset_id"]),
                    subset_origin=list(subset["subset_origin"]),
                    anchor_idx=int(anchor_idx),
                    field_variant=str(field_variant),
                    solver_profile=solver_profile,
                    time_limit_seconds=float(time_limit_seconds),
                )
            )
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    summary = _summary(entries, source_cores=source_cores, model_error=model_error)
    return {
        "metadata": {
            "source": PHASE3B_DIRECT_EQUALITY_CORE_EXCHANGE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "bounded_core_exchange_not_proof_source",
            "proof_source": False,
            "solver_invoked": True,
        },
        "paths": {
            "project_root": str(project_root),
            "core_paths": [str(path) for path in normalized_core_paths],
        },
        "candidate": {
            "key": str(candidate),
            "ghost_rect": _candidate_rect(str(candidate)),
            "anchor_idx": int(anchor_idx),
        },
        "profile": {
            "group_id": str(group_id),
            "field_variant": str(field_variant),
            "master_search_profile": str(master_search_profile),
            "subset_size": int(subset_size),
            "max_subsets": int(max_subsets),
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
        },
        "artifact_hashes": dict(artifact_hashes),
        "artifact_hash_error": artifact_hash_error,
        "source_cores": source_cores,
        "union_keys": union_keys,
        "greedy": _compact_greedy(greedy) if greedy else {},
        "entries": entries,
        "summary": summary,
        "status": _status(summary, model_error=model_error),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(entries, source_cores=source_cores, model_error=model_error),
    }


def render_phase3b_direct_equality_core_exchange_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    profile = _mapping(report.get("profile"))
    summary = _mapping(report.get("summary"))
    status = _mapping(report.get("status"))
    lines = [
        "# Phase 3B Direct-Equality Core Exchange",
        "",
        "- Diagnostic semantics: bounded_core_exchange_not_proof_source",
        "- Proof source: false",
        "- Solver invoked: true",
        f"- Candidate: `{candidate.get('key')}` / anchor `{candidate.get('anchor_idx')}`",
        f"- Group: `{profile.get('group_id')}`",
        f"- Union key count: `{summary.get('union_key_count')}`",
        f"- Evaluated subsets: `{summary.get('evaluated_subset_count')}`",
        f"- Status counts: `{summary.get('status_counts')}`",
        f"- Outcome: `{status.get('outcome')}`",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Subsets",
        "",
        "| Subset | Origin | Status | Reason | Keys | Wall | Branches | Conflicts |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for entry in list(report.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        validation = _mapping(entry.get("validation"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("subset_id")),
                    _markdown_cell(",".join(str(item) for item in list(entry.get("subset_origin", [])))),
                    _markdown_cell(validation.get("status")),
                    _markdown_cell(validation.get("reason")),
                    _markdown_cell("; ".join(str(key) for key in list(entry.get("subset_keys", [])))),
                    _markdown_cell(validation.get("wall_time")),
                    _markdown_cell(validation.get("branches")),
                    _markdown_cell(validation.get("conflicts")),
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
                        _markdown_cell(check.get("check_id")),
                        _markdown_cell(check.get("status")),
                        _markdown_cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_direct_equality_core_exchange_text(report: Mapping[str, Any]) -> str:
    summary = _mapping(report.get("summary"))
    status = _mapping(report.get("status"))
    lines = [
        "Phase 3B direct-equality core exchange",
        "diagnostic_semantics=bounded_core_exchange_not_proof_source",
        "proof_source=false",
        "solver_invoked=true",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"union_key_count={summary.get('union_key_count')}",
        f"evaluated_subset_count={summary.get('evaluated_subset_count')}",
        f"status_counts={summary.get('status_counts')}",
    ]
    for entry in list(report.get("entries", [])):
        if isinstance(entry, Mapping):
            validation = _mapping(entry.get("validation"))
            lines.append(
                "entry "
                f"subset={entry.get('subset_id')} "
                f"origin={entry.get('subset_origin')} "
                f"status={validation.get('status')} "
                f"reason={validation.get('reason')} "
                f"key_count={entry.get('subset_key_count')}"
            )
    return "\n".join(lines) + "\n"


def _evaluate_subset(
    *,
    model: Any,
    greedy: Mapping[str, Any],
    subset_keys: Sequence[str],
    subset_id: str,
    subset_origin: Sequence[str],
    anchor_idx: int,
    field_variant: str,
    solver_profile: Mapping[str, Any],
    time_limit_seconds: float,
) -> Dict[str, Any]:
    validation = _compact_validation(
        model._validate_coordinate_forced_hint(
            solution_hint=dict(greedy.get("solution_hint", {})),
            ghost_anchor_hint_idx=None,
            time_limit_seconds=float(time_limit_seconds),
            require_complete=False,
            solver_parameter_profile=solver_profile,
            force_fields=tuple(_force_fields_for_variant(str(field_variant))),
            force_equality_keys=set(str(key) for key in subset_keys),
            collect_force_equality_labels=False,
        )
    )
    return {
        "subset_id": str(subset_id),
        "subset_origin": [str(item) for item in subset_origin],
        "subset_key_count": int(len(subset_keys)),
        "subset_keys": [str(key) for key in subset_keys],
        "anchor_idx": int(anchor_idx),
        "validation": validation,
    }


def _source_core_payload(project_root: Path, path: Path) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    final_keys = _final_keys(payload)
    return {
        "name": str(payload.get("name") or Path(path).stem),
        "path": _display_path(project_root, path),
        "final_keys": final_keys,
        "final_key_count": int(len(final_keys)),
    }


def _final_keys(payload: Mapping[str, Any]) -> list[str]:
    if isinstance(payload.get("final_keys"), list):
        return [str(key) for key in list(payload.get("final_keys", []))]
    direct = _mapping(payload.get("direct_equality_core"))
    if isinstance(direct.get("final_keys"), list):
        return [str(key) for key in list(direct.get("final_keys", []))]
    raise ValueError("core payload does not expose final_keys")


def _selected_subsets(
    union_keys: Sequence[str],
    *,
    source_cores: Sequence[Mapping[str, Any]],
    subset_size: int,
    max_subsets: int,
) -> list[Dict[str, Any]]:
    if int(subset_size) <= 0:
        raise ValueError("subset_size must be positive")
    selected: list[Dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for core in source_cores:
        keys = tuple(sorted(str(key) for key in list(core.get("final_keys", []))))
        if len(keys) == int(subset_size) and keys not in seen:
            seen.add(keys)
            selected.append(
                {
                    "subset_id": f"source::{core.get('name')}",
                    "subset_origin": [f"source::{core.get('name')}"],
                    "subset_keys": list(keys),
                }
            )
    for keys in itertools.combinations(sorted(str(key) for key in union_keys), int(subset_size)):
        if keys in seen:
            continue
        if len(selected) >= int(max_subsets):
            break
        seen.add(keys)
        selected.append(
            {
                "subset_id": f"combo::{len(selected):03d}",
                "subset_origin": ["union_combination"],
                "subset_keys": list(keys),
            }
        )
    return selected


def _summary(
    entries: Sequence[Mapping[str, Any]],
    *,
    source_cores: Sequence[Mapping[str, Any]],
    model_error: str | None,
) -> Dict[str, Any]:
    status_counts = Counter()
    infeasible_subset_ids = []
    source_statuses: Dict[str, str] = {}
    for entry in entries:
        validation = _mapping(entry.get("validation"))
        status = str(validation.get("status", "MISSING"))
        status_counts[status] += 1
        if status == "INFEASIBLE":
            infeasible_subset_ids.append(str(entry.get("subset_id")))
        if any(str(origin).startswith("source::") for origin in list(entry.get("subset_origin", []))):
            source_statuses[str(entry.get("subset_id"))] = status
    union_key_count = len({key for core in source_cores for key in list(core.get("final_keys", []))})
    return {
        "union_key_count": int(union_key_count),
        "source_core_count": int(len(source_cores)),
        "evaluated_subset_count": int(len(entries)),
        "status_counts": dict(sorted(status_counts.items())),
        "infeasible_subset_ids": infeasible_subset_ids,
        "infeasible_subset_count": int(len(infeasible_subset_ids)),
        "source_subset_statuses": source_statuses,
        "model_error": model_error,
    }


def _status(summary: Mapping[str, Any], *, model_error: str | None) -> Dict[str, str]:
    if model_error is not None:
        return {
            "outcome": "model_error",
            "recommendation": "Fix the diagnostic setup before interpreting exchange results.",
        }
    infeasible_count = int(summary.get("infeasible_subset_count", 0))
    evaluated_count = int(summary.get("evaluated_subset_count", 0))
    if infeasible_count <= 0:
        return {
            "outcome": "no_exchange_subset_reproduced_infeasible",
            "recommendation": "Treat current 3-key cores as shrink-order specific until source cores are rechecked.",
        }
    if infeasible_count < evaluated_count:
        return {
            "outcome": "mixed_exchange_subsets",
            "recommendation": "Use the INFEASIBLE exchange subsets to identify the common slot-window and constraint family.",
        }
    return {
        "outcome": "all_exchange_subsets_infeasible",
        "recommendation": "The union appears highly saturated; narrow with targeted x-domain/no-overlap/family attribution.",
    }


def _checks(
    entries: Sequence[Mapping[str, Any]],
    *,
    source_cores: Sequence[Mapping[str, Any]],
    model_error: str | None,
) -> list[Dict[str, str]]:
    return [
        _check(
            "source_cores_present",
            "pass" if source_cores else "fail",
            f"source_core_count={len(source_cores)}",
        ),
        _check(
            "exchange_subsets_evaluated",
            "pass" if entries else "fail",
            f"evaluated_subset_count={len(entries)}",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            model_error or "no model error",
        ),
    ]


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
