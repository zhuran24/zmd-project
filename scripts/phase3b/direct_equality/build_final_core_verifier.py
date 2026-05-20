from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b.coordinate_validation.field_channel_delta import (
    _force_fields_for_variant,
)
from src.search.phase3b.coordinate_validation.group_delta import (
    _build_delta_context,
    _compact_greedy,
    _compact_validation,
    _normalize_solver_profile,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the final-key subset from a direct equality core diagnostic."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--core-json", type=Path, required=True)
    parser.add_argument("--group-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument("--anchor-index", type=int, default=119)
    parser.add_argument("--field-variant", default="x_y_mode")
    parser.add_argument(
        "--master-search-profile",
        default=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    )
    parser.add_argument("--time-limit-seconds", type=float, default=10.0)
    parser.add_argument("--worker-count", type=int, default=1)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_direct_equality_core_final_verifier"),
    )
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    core_path = _resolve_input_path(project_root, args.core_json)
    core = json.loads(core_path.read_text(encoding="utf-8"))
    final_keys = _final_keys_from_core(core)
    started = time.perf_counter()
    cases = []

    cases.append(
        {
            "case": "final_all_keys",
            **_run_subset_case(
                project_root=project_root,
                candidate=str(args.candidate),
                anchor_idx=int(args.anchor_index),
                group_id=str(args.group_id),
                field_variant=str(args.field_variant),
                master_search_profile=str(args.master_search_profile),
                time_limit_seconds=float(args.time_limit_seconds),
                worker_count=int(args.worker_count),
                subset_keys=final_keys,
            ),
        }
    )
    for key in final_keys:
        subset = [candidate_key for candidate_key in final_keys if candidate_key != key]
        cases.append(
            {
                "case": "remove_one_final_key",
                "removed_key": key,
                **_run_subset_case(
                    project_root=project_root,
                    candidate=str(args.candidate),
                    anchor_idx=int(args.anchor_index),
                    group_id=str(args.group_id),
                    field_variant=str(args.field_variant),
                    master_search_profile=str(args.master_search_profile),
                    time_limit_seconds=float(args.time_limit_seconds),
                    worker_count=int(args.worker_count),
                    subset_keys=subset,
                ),
            }
        )
    for key in final_keys:
        cases.append(
            {
                "case": "single_final_key",
                **_run_subset_case(
                    project_root=project_root,
                    candidate=str(args.candidate),
                    anchor_idx=int(args.anchor_index),
                    group_id=str(args.group_id),
                    field_variant=str(args.field_variant),
                    master_search_profile=str(args.master_search_profile),
                    time_limit_seconds=float(args.time_limit_seconds),
                    worker_count=int(args.worker_count),
                    subset_keys=[key],
                ),
            }
        )

    report = {
        "metadata": {
            "source": "phase3b_direct_equality_final_core_verifier_v1",
            "generated_at": now_iso(),
            "diagnostic_semantics": "final_core_verification_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "source_core_json": str(core_path),
        },
        "candidate": {
            "key": str(args.candidate),
            "anchor_idx": int(args.anchor_index),
        },
        "profile": {
            "group_id": str(args.group_id),
            "field_variant": str(args.field_variant),
            "master_search_profile": str(args.master_search_profile),
            "time_limit_seconds": float(args.time_limit_seconds),
            "worker_count": int(args.worker_count),
        },
        "name": str(args.name),
        "final_keys": final_keys,
        "cases": cases,
        "summary": _summary_from_cases(cases),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = args.output_prefix or f"final_core_verifier_{args.name}_anchor{args.anchor_index}"
        json_path = output_dir / f"{prefix}.json"
        atomic_write_json(json_path, report)
        print(f"final_core_verifier_json={_display_path(project_root, json_path)}")
    return 0


def _run_subset_case(
    *,
    project_root: Path,
    candidate: str,
    anchor_idx: int,
    group_id: str,
    field_variant: str,
    master_search_profile: str,
    time_limit_seconds: float,
    worker_count: int,
    subset_keys: Sequence[str],
) -> dict[str, Any]:
    context = _build_delta_context(
        project_root,
        candidate=str(candidate),
        anchor_idx=int(anchor_idx),
        master_search_profile=str(master_search_profile),
    )
    group_by_id = {
        str(group.get("group_id", "")): group
        for group in context["ordered_groups"]
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
        "subset_key_count": int(len(subset_keys)),
        "subset_keys": list(str(key) for key in subset_keys),
        "greedy": _compact_greedy(greedy),
        "validation": validation,
    }


def _summary_from_cases(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    final_case = next((case for case in cases if case.get("case") == "final_all_keys"), {})
    remove_counts: dict[str, int] = {}
    single_counts: dict[str, int] = {}
    for case in cases:
        validation = case.get("validation")
        status = str(validation.get("status")) if isinstance(validation, Mapping) else "MISSING"
        if case.get("case") == "remove_one_final_key":
            remove_counts[status] = int(remove_counts.get(status, 0)) + 1
        elif case.get("case") == "single_final_key":
            single_counts[status] = int(single_counts.get(status, 0)) + 1
    final_validation = final_case.get("validation")
    final_status = (
        str(final_validation.get("status"))
        if isinstance(final_validation, Mapping)
        else "MISSING"
    )
    return {
        "final_all_status": final_status,
        "remove_one_status_counts": remove_counts,
        "single_key_status_counts": single_counts,
        "minimality_signal": (
            "strong_three_key_signal"
            if final_status == "INFEASIBLE"
            and remove_counts
            and set(remove_counts.keys()) == {"UNKNOWN"}
            else "inconclusive"
        ),
    }


def _final_keys_from_core(core: Mapping[str, Any]) -> list[str]:
    direct_core = core.get("direct_equality_core")
    if not isinstance(direct_core, Mapping):
        raise ValueError("core JSON missing direct_equality_core")
    keys = [str(key) for key in list(direct_core.get("final_keys", []))]
    if not keys:
        raise ValueError("core JSON does not contain final_keys")
    return keys


def _resolve_input_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _resolve_output_dir(project_root: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.is_absolute():
        return output_dir.resolve()
    return (project_root / output_dir).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _print_summary(report: Mapping[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    print("phase3b direct equality final core verifier")
    print(f"- name: {report.get('name')}")
    print(f"- final all status: {summary.get('final_all_status')}")
    print(f"- remove-one status counts: {summary.get('remove_one_status_counts')}")
    print(f"- single-key status counts: {summary.get('single_key_status_counts')}")
    print(f"- minimality signal: {summary.get('minimality_signal')}")


if __name__ == "__main__":
    raise SystemExit(main())
