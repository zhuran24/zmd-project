from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import atomic_write_json, compute_exact_artifact_hashes, now_iso
from src.search.phase3b_forced_anchor_master import _check, _display_path, _mapping
from src.search.phase3b_mandatory_core_matrix import _build_mandatory_core_overlay

SIGNATURE_REGION_EQUIVALENCE_AUDIT_SOURCE = (
    "phase3b_signature_region_equivalence_audit_v1"
)
DEFAULT_CANDIDATE = "67x13"
DEFAULT_GROUP_ID = "group::manufacturing_6x4::grinder_dense_blue_iron::14"


def build_phase3b_signature_region_equivalence_audit(
    project_root: Path,
    *,
    candidate: str = DEFAULT_CANDIDATE,
    group_id: str = DEFAULT_GROUP_ID,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    enable_symmetry_breaking: bool = True,
    sample_limit: int = 8,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    candidate_key = str(candidate)
    started = time.perf_counter()
    report: Dict[str, Any] = {
        "metadata": {
            "source": SIGNATURE_REGION_EQUIVALENCE_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_signature_region_equivalence_not_proof_source",
            "solver_invoked": False,
            "proof_source": False,
        },
        "paths": {"project_root": str(project_root)},
        "candidate": {
            "key": candidate_key,
            "ghost_rect": _parse_candidate(candidate_key),
        },
        "profile": {
            "group_id": str(group_id),
            "master_search_profile": str(master_search_profile),
            "enable_symmetry_breaking": bool(enable_symmetry_breaking),
            "sample_limit": int(sample_limit),
        },
        "artifact_hashes": {},
        "artifact_hash_error": None,
        "status": {
            "completed": False,
            "outcome": "running",
            "recommendation": "Signature-region equivalence audit is running.",
        },
        "target_group": {},
        "equivalence": {},
        "timing": {},
        "model_error": None,
        "checks": [],
    }
    try:
        try:
            report["artifact_hashes"] = compute_exact_artifact_hashes(project_root)
        except Exception as exc:
            report["artifact_hash_error"] = f"{type(exc).__name__}: {exc}"

        ghost = _mapping(report["candidate"].get("ghost_rect"))
        model, _base_proto = _build_mandatory_core_overlay(
            project_root,
            ghost_rect=(int(ghost.get("w", 0)), int(ghost.get("h", 0))),
            master_search_profile=str(master_search_profile),
            enable_symmetry_breaking=bool(enable_symmetry_breaking),
        )
        delegate = getattr(model, "_coordinate_delegate", None)
        audit = audit_mandatory_group_signature_region_equivalence(
            model,
            delegate,
            group_id=str(group_id),
            sample_limit=int(sample_limit),
        )
        report["target_group"] = dict(audit.get("target_group", {}))
        report["equivalence"] = dict(audit.get("equivalence", {}))
        report["status"] = _status_from_equivalence(report["equivalence"])
    except Exception as exc:
        report["model_error"] = f"{type(exc).__name__}: {exc}"
        report["status"] = {
            "completed": True,
            "outcome": "diagnostic_error",
            "recommendation": "Signature-region equivalence audit failed; inspect model_error before using this evidence.",
        }
    report["timing"]["total_seconds"] = float(time.perf_counter() - started)
    report["checks"] = _checks(report)
    return report


def audit_mandatory_group_signature_region_equivalence(
    model: Any,
    delegate: Any,
    *,
    group_id: str,
    sample_limit: int = 8,
) -> Dict[str, Any]:
    if delegate is None:
        return {
            "target_group": {"group_id": str(group_id), "present": False},
            "equivalence": {
                "evaluated": False,
                "outcome": "coordinate_delegate_missing",
                "bucket_count": 0,
                "mismatched_bucket_count": 0,
                "overlap_tuple_count": 0,
            },
        }
    group = _find_group(model, group_id)
    if group is None:
        return {
            "target_group": {"group_id": str(group_id), "present": False},
            "equivalence": {
                "evaluated": False,
                "outcome": "target_group_missing",
                "bucket_count": 0,
                "mismatched_bucket_count": 0,
                "overlap_tuple_count": 0,
            },
        }
    group_map = _mapping(group)
    template = str(group_map.get("facility_type", ""))
    bucket_pose_indices = {
        str(bucket_id): tuple(int(value) for value in list(pose_indices))
        for bucket_id, pose_indices in dict(
            getattr(delegate, "_mandatory_group_bucket_pose_indices", {}).get(str(group_id), {})
        ).items()
    }
    bucket_regions = {
        str(bucket_id): list(regions)
        for bucket_id, regions in dict(
            getattr(delegate, "_mandatory_group_bucket_regions", {}).get(str(group_id), {})
        ).items()
    }
    pose_tuple_by_idx = dict(getattr(delegate, "_template_pose_tuple_by_idx", {}).get(template, {}))
    uses_signature_table = bool(
        getattr(delegate, "_mandatory_group_uses_signature_table", {}).get(str(group_id), False)
    )
    uses_domain_table = bool(
        getattr(delegate, "_mandatory_group_uses_domain_table", {}).get(str(group_id), False)
    )
    bucket_ids = sorted(set(bucket_pose_indices) | set(bucket_regions), key=str)
    tuple_owner: Dict[Tuple[int, int, int], list[str]] = {}
    bucket_entries: list[Dict[str, Any]] = []
    for bucket_id in bucket_ids:
        exact_tuples = {
            _normalize_tuple(pose_tuple_by_idx[int(pose_idx)])
            for pose_idx in bucket_pose_indices.get(bucket_id, ())
            if int(pose_idx) in pose_tuple_by_idx
        }
        region_tuples = _tuples_from_regions(bucket_regions.get(bucket_id, ()))
        for tuple_value in region_tuples:
            tuple_owner.setdefault(tuple_value, []).append(str(bucket_id))
        missing = sorted(exact_tuples - region_tuples)
        extra = sorted(region_tuples - exact_tuples)
        entry = {
            "bucket_id": str(bucket_id),
            "pose_index_count": int(len(bucket_pose_indices.get(bucket_id, ()))),
            "exact_tuple_count": int(len(exact_tuples)),
            "region_count": int(len(bucket_regions.get(bucket_id, ()))),
            "region_tuple_count": int(len(region_tuples)),
            "missing_tuple_count": int(len(missing)),
            "extra_tuple_count": int(len(extra)),
            "equivalent": not missing and not extra,
            "missing_tuple_sample": _sample_tuples(missing, sample_limit),
            "extra_tuple_sample": _sample_tuples(extra, sample_limit),
            "region_sample": [
                _region_payload(region)
                for region in list(bucket_regions.get(bucket_id, ()))[: max(0, int(sample_limit))]
            ],
        }
        bucket_entries.append(entry)
    overlaps = {
        tuple_value: sorted(bucket_ids)
        for tuple_value, bucket_ids in tuple_owner.items()
        if len(set(bucket_ids)) > 1
    }
    mismatches = [entry for entry in bucket_entries if not bool(entry.get("equivalent", False))]
    exact_union = set()
    region_union = set()
    for entry in bucket_entries:
        bucket_id = str(entry["bucket_id"])
        exact_union.update(
            _normalize_tuple(pose_tuple_by_idx[int(pose_idx)])
            for pose_idx in bucket_pose_indices.get(bucket_id, ())
            if int(pose_idx) in pose_tuple_by_idx
        )
        region_union.update(_tuples_from_regions(bucket_regions.get(bucket_id, ())))
    return {
        "target_group": {
            "group_id": str(group_id),
            "present": True,
            "facility_type": template,
            "operation_type": group_map.get("operation_type"),
            "required_count": int(group_map.get("count", 0)),
            "uses_signature_table": bool(uses_signature_table),
            "uses_domain_table": bool(uses_domain_table),
        },
        "equivalence": {
            "evaluated": True,
            "outcome": "equivalent" if not mismatches and not overlaps else "mismatch_detected",
            "bucket_count": int(len(bucket_entries)),
            "mismatched_bucket_count": int(len(mismatches)),
            "overlap_tuple_count": int(len(overlaps)),
            "exact_union_tuple_count": int(len(exact_union)),
            "region_union_tuple_count": int(len(region_union)),
            "union_missing_tuple_count": int(len(exact_union - region_union)),
            "union_extra_tuple_count": int(len(region_union - exact_union)),
            "overlap_tuple_sample": [
                {"tuple": list(tuple_value), "bucket_ids": owners}
                for tuple_value, owners in list(sorted(overlaps.items()))[: max(0, int(sample_limit))]
            ],
            "buckets": bucket_entries,
        },
    }


def render_phase3b_signature_region_equivalence_audit_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    candidate = _mapping(report.get("candidate"))
    target = _mapping(report.get("target_group"))
    eq = _mapping(report.get("equivalence"))
    lines = [
        "# Phase 3B Signature-Region Equivalence Audit",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Group: {target.get('group_id')}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "- Diagnostic semantics: no_solve_signature_region_equivalence_not_proof_source",
        "- Solver invoked: false",
        "",
        "| Bucket | Exact Tuples | Region Tuples | Missing | Extra | Equivalent |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for bucket in list(eq.get("buckets", [])):
        if not isinstance(bucket, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(bucket.get("bucket_id")),
                    str(int(bucket.get("exact_tuple_count", 0))),
                    str(int(bucket.get("region_tuple_count", 0))),
                    str(int(bucket.get("missing_tuple_count", 0))),
                    str(int(bucket.get("extra_tuple_count", 0))),
                    str(bool(bucket.get("equivalent", False))),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            f"- Mismatched buckets: {eq.get('mismatched_bucket_count')}",
            f"- Overlap tuple count: {eq.get('overlap_tuple_count')}",
            f"- Union missing tuple count: {eq.get('union_missing_tuple_count')}",
            f"- Union extra tuple count: {eq.get('union_extra_tuple_count')}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_phase3b_signature_region_equivalence_audit_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    candidate = _mapping(report.get("candidate"))
    target = _mapping(report.get("target_group"))
    eq = _mapping(report.get("equivalence"))
    lines = [
        "Phase 3B signature-region equivalence audit",
        f"candidate={candidate.get('key')}",
        f"group_id={target.get('group_id')}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        "diagnostic_semantics=no_solve_signature_region_equivalence_not_proof_source",
        "solver_invoked=false",
        f"bucket_count={eq.get('bucket_count')}",
        f"mismatched_bucket_count={eq.get('mismatched_bucket_count')}",
        f"overlap_tuple_count={eq.get('overlap_tuple_count')}",
        f"union_missing_tuple_count={eq.get('union_missing_tuple_count')}",
        f"union_extra_tuple_count={eq.get('union_extra_tuple_count')}",
    ]
    return "\n".join(lines) + "\n"


def write_phase3b_signature_region_equivalence_audit(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "signature_region_equivalence_audit",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    _atomic_write_text(md_path, render_phase3b_signature_region_equivalence_audit_markdown(report))
    _atomic_write_text(txt_path, render_phase3b_signature_region_equivalence_audit_text(report))
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _status_from_equivalence(equivalence: Mapping[str, Any]) -> Dict[str, Any]:
    if not bool(equivalence.get("evaluated", False)):
        outcome = str(equivalence.get("outcome", "not_evaluated"))
        return {
            "completed": True,
            "outcome": outcome,
            "recommendation": "Audit did not evaluate; inspect target_group and model setup.",
        }
    if str(equivalence.get("outcome")) == "equivalent":
        return {
            "completed": True,
            "outcome": "equivalent",
            "recommendation": "Compact signature-region tuples match filtered bucket pose tuples; next compare a default-off exact table-channel diagnostic if needed.",
        }
    return {
        "completed": True,
        "outcome": "mismatch_detected",
        "recommendation": "Compact signature-region tuples do not match filtered bucket pose tuples; inspect missing/extra/overlap samples before any runtime change.",
    }


def _checks(report: Mapping[str, Any]) -> list[Dict[str, Any]]:
    status = _mapping(report.get("status"))
    eq = _mapping(report.get("equivalence"))
    return [
        _check(
            "solver_not_invoked",
            "pass",
            "audit is no-solve and only compares derived tuple sets",
        ),
        _check(
            "audit_completed",
            "pass" if bool(status.get("completed", False)) else "fail",
            str(status.get("outcome")),
        ),
        _check(
            "signature_region_equivalence",
            "pass" if str(eq.get("outcome")) == "equivalent" else "fail",
            (
                f"mismatched_bucket_count={eq.get('mismatched_bucket_count')} "
                f"overlap_tuple_count={eq.get('overlap_tuple_count')}"
            ),
        ),
    ]


def _parse_candidate(candidate: str) -> Dict[str, int]:
    text = str(candidate).lower().strip()
    left, right = text.split("x", 1)
    w = int(left)
    h = int(right)
    return {"w": w, "h": h, "area": int(w * h)}


def _find_group(model: Any, group_id: str) -> Optional[Mapping[str, Any]]:
    for group in list(getattr(model, "_mandatory_groups", [])):
        if str(_mapping(group).get("group_id")) == str(group_id):
            return _mapping(group)
    return None


def _tuples_from_regions(regions: Iterable[Any]) -> set[Tuple[int, int, int]]:
    tuples: set[Tuple[int, int, int]] = set()
    for region in regions:
        mode_id = int(getattr(region, "mode_id"))
        for x_val in range(int(getattr(region, "x_min")), int(getattr(region, "x_max")) + 1):
            for y_val in range(int(getattr(region, "y_min")), int(getattr(region, "y_max")) + 1):
                tuples.add((int(x_val), int(y_val), int(mode_id)))
    return tuples


def _normalize_tuple(value: Any) -> Tuple[int, int, int]:
    x_val, y_val, mode_id = value
    return (int(x_val), int(y_val), int(mode_id))


def _sample_tuples(values: Sequence[Tuple[int, int, int]], limit: int) -> list[list[int]]:
    return [list(value) for value in list(values)[: max(0, int(limit))]]


def _region_payload(region: Any) -> Dict[str, int]:
    return {
        "mode_id": int(getattr(region, "mode_id")),
        "x_min": int(getattr(region, "x_min")),
        "x_max": int(getattr(region, "x_max")),
        "y_min": int(getattr(region, "y_min")),
        "y_max": int(getattr(region, "y_max")),
    }


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)
