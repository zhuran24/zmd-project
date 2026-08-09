from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.ai_accel.schemas import (
    AI_CANDIDATE_RUN_SAMPLE_SCHEMA_ID,
    AI_FEATURE_DATASET_SUMMARY_SCHEMA_ID,
    build_ai_dataset_safety_contract,
    build_candidate_run_feature_schema,
)
from src.search.exact_campaign import now_iso


def extract_candidate_run_samples(
    acceptance_payload: Mapping[str, Any],
    *,
    scorecard_payload: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    profile_scores = _profile_scores(scorecard_payload)
    logical_cpu_count = _int_or_none(acceptance_payload.get("logical_cpu_count"))
    samples: list[dict[str, Any]] = []
    for record_index, record in enumerate(acceptance_payload.get("run_records", [])):
        if not isinstance(record, Mapping):
            continue
        if str(record.get("target", "")) != "production-campaign-run":
            continue
        profile_id = str(record.get("label") or _infer_profile_id(record))
        for wave in record.get("campaign_wave_summaries", []) or []:
            if not isinstance(wave, Mapping):
                continue
            for candidate_result in wave.get("candidate_results", []) or []:
                if not isinstance(candidate_result, Mapping):
                    continue
                samples.append(
                    _sample_from_candidate_result(
                        record=record,
                        wave=wave,
                        candidate_result=candidate_result,
                        record_index=record_index,
                        profile_id=profile_id,
                        profile_score=profile_scores.get(profile_id),
                        logical_cpu_count=logical_cpu_count,
                    )
                )
    return sorted(samples, key=_sample_sort_key)


def build_feature_dataset_summary(
    samples: Iterable[Mapping[str, Any]],
    *,
    acceptance_summary_path: Path,
    scorecard_path: Path,
) -> dict[str, Any]:
    sample_list = [dict(sample) for sample in samples]
    profile_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {
        "precheck_eliminated": 0,
        "unknown_risk": 0,
        "became_terminal_fast": 0,
        "high_prune_gain": 0,
    }
    for sample in sample_list:
        profile_id = str(sample.get("profile_id", ""))
        terminal = _mapping(sample.get("terminal"))
        labels = _mapping(sample.get("labels"))
        profile_counts[profile_id] = profile_counts.get(profile_id, 0) + 1
        status = str(terminal.get("status", ""))
        status_counts[status] = status_counts.get(status, 0) + 1
        for label_name in list(label_counts):
            if bool(labels.get(label_name, False)):
                label_counts[label_name] += 1
    return {
        "schema": AI_FEATURE_DATASET_SUMMARY_SCHEMA_ID,
        "generated_at": now_iso(),
        "sample_schema": AI_CANDIDATE_RUN_SAMPLE_SCHEMA_ID,
        "sample_count": len(sample_list),
        "profile_counts": dict(sorted(profile_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "label_counts": label_counts,
        "source_artifacts": {
            "acceptance_summary": str(Path(acceptance_summary_path)),
            "baseline_scorecard": str(Path(scorecard_path)),
        },
        "safety": build_ai_dataset_safety_contract(),
        "dataset_kind": "evidence_replay_shadow_dataset",
    }


def render_dataset_summary_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Phase3B AI Dataset V0 Shadow",
        "",
        f"- Dataset kind: `{summary.get('dataset_kind')}`",
        f"- Sample schema: `{summary.get('sample_schema')}`",
        f"- Sample count: `{summary.get('sample_count')}`",
        f"- Proof source: `{_mapping(summary.get('safety')).get('proof_source')}`",
        f"- Scheduler integration: `{_mapping(summary.get('safety')).get('scheduler_integration')}`",
        f"- Model trained: `{_mapping(summary.get('safety')).get('model_trained')}`",
        "",
        "## Profiles",
        "",
        "| Profile | Samples |",
        "| --- | ---: |",
    ]
    for profile_id, count in _mapping(summary.get("profile_counts")).items():
        lines.append(f"| {_markdown_cell(profile_id)} | {int(count)} |")
    lines.extend(["", "## Statuses", "", "| Status | Samples |", "| --- | ---: |"])
    for status, count in _mapping(summary.get("status_counts")).items():
        lines.append(f"| {_markdown_cell(status)} | {int(count)} |")
    return "\n".join(lines) + "\n"


def write_candidate_runs_jsonl(path: Path, samples: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [stable_json_dumps(dict(sample)) for sample in samples]
    Path(path).write_text("".join(line + "\n" for line in lines), encoding="utf-8")


def stable_json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_feature_schema() -> dict[str, Any]:
    return build_candidate_run_feature_schema()


def _sample_from_candidate_result(
    *,
    record: Mapping[str, Any],
    wave: Mapping[str, Any],
    candidate_result: Mapping[str, Any],
    record_index: int,
    profile_id: str,
    profile_score: Mapping[str, Any] | None,
    logical_cpu_count: int | None,
) -> dict[str, Any]:
    proof = _mapping(candidate_result.get("proof_status_summary"))
    precheck_payload = _mapping(proof.get("master_candidate_precheck"))
    master_last_solve = _mapping(proof.get("master_last_solve"))
    frontier_metrics = dict(_mapping(proof.get("frontier_candidate_metrics")))
    candidate_key = str(candidate_result.get("candidate_key", ""))
    wave_index = _int_or_none(wave.get("wave_index"))
    dispatch_seq = _int_or_none(candidate_result.get("dispatch_seq"))
    attempt_index = _int_or_none(candidate_result.get("attempt_index"))
    status = str(candidate_result.get("status", ""))
    outcome = str(candidate_result.get("outcome_category", ""))
    precheck_triggered = bool(precheck_payload.get("triggered", False))
    master_solve_skipped = bool(precheck_payload.get("master_solve_skipped", False))
    sample_id = _sample_id(
        profile_id=profile_id,
        record_index=record_index,
        wave_index=wave_index,
        dispatch_seq=dispatch_seq,
        candidate_key=candidate_key,
        attempt_index=attempt_index,
    )
    return {
        "schema": AI_CANDIDATE_RUN_SAMPLE_SCHEMA_ID,
        "sample_id": sample_id,
        "candidate_key": candidate_key,
        "run_id": _run_id(record, profile_id),
        "profile_id": profile_id,
        "source": {
            "evidence_kind": "existing_production_acceptance_replay",
            "record_index": int(record_index),
            "wave_index": wave_index,
            "dispatch_seq": dispatch_seq,
            "attempt_index": attempt_index,
            "target": str(record.get("target", "")),
        },
        "parallel_processes": _int_or_none(record.get("parallel_processes"))
        or _int_or_none(record.get("process_count")),
        "process_count": _int_or_none(record.get("process_count")),
        "worker_count_per_process": _int_or_none(record.get("worker_count_per_process")),
        "worker_profile": dict(_mapping(record.get("worker_profile"))),
        "profile_score": None if profile_score is None else dict(profile_score),
        "selection_reason": str(
            candidate_result.get("selection_reason")
            or proof.get("selection_reason")
            or ""
        ),
        "frontier_candidate_metrics": frontier_metrics,
        "precheck": {
            "triggered": precheck_triggered,
            "eliminated": bool(precheck_triggered and master_solve_skipped),
            "reason": precheck_payload.get("precheck_reason"),
            "master_solve_skipped": master_solve_skipped,
            "lookahead": proof.get("precheck_lookahead"),
            "screened_infeasible_anchor_count": _int_or_none(
                precheck_payload.get("screened_infeasible_anchor_count")
            ),
            "screen_pass_anchor_count": _int_or_none(
                precheck_payload.get("screen_pass_anchor_count")
            ),
        },
        "terminal": {
            "status": status,
            "outcome": outcome,
            "classification": _terminal_classification(
                status=status,
                outcome=outcome,
                precheck_triggered=precheck_triggered,
                master_solve_skipped=master_solve_skipped,
            ),
            "subtype": _terminal_subtype(
                status=status,
                precheck_payload=precheck_payload,
                proof=proof,
                master_last_solve=master_last_solve,
            ),
        },
        "solver_metrics": {
            "status": master_last_solve.get("status"),
            "wall_time": _number_or_none(master_last_solve.get("wall_time")),
            "user_time": _number_or_none(master_last_solve.get("user_time")),
            "deterministic_time": _number_or_none(master_last_solve.get("deterministic_time")),
            "branches": _int_or_none(master_last_solve.get("branches")),
            "conflicts": _int_or_none(master_last_solve.get("conflicts")),
            "binary_propagations": _int_or_none(master_last_solve.get("binary_propagations")),
            "integer_propagations": _int_or_none(master_last_solve.get("integer_propagations")),
            "hinted_literals": _int_or_none(master_last_solve.get("hinted_literals")),
            "search_profile": master_last_solve.get("search_profile"),
        },
        "resource_metrics": {
            "wave_elapsed_seconds": _number_or_none(wave.get("elapsed_seconds")),
            "rss_gib_at_window": _bytes_to_gib(
                _int_or_none(wave.get("peak_rss_bytes_external_total"))
                or _int_or_none(record.get("peak_rss_bytes_external_total"))
            ),
            "peak_rss_gib_record": _bytes_to_gib(_int_or_none(record.get("peak_rss_bytes_external_total"))),
            "avg_process_cpu_percent": _number_or_none(record.get("avg_process_cpu_pct")),
            "normalized_cpu_percent_avg": _normalized_cpu_percent(
                record.get("avg_process_cpu_pct"),
                logical_cpu_count,
            ),
        },
        "labels": {
            "became_terminal_fast": _became_terminal_fast(master_last_solve),
            "precheck_eliminated": bool(precheck_triggered and master_solve_skipped),
            "high_prune_gain": _high_prune_gain(frontier_metrics),
            "unknown_risk": status == "UNKNOWN" or outcome == "unknown",
        },
        "safety": build_ai_dataset_safety_contract(),
    }


def _profile_scores(scorecard_payload: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    if not isinstance(scorecard_payload, Mapping):
        return {}
    scores: dict[str, Mapping[str, Any]] = {}
    for profile in scorecard_payload.get("profiles", []) or []:
        if not isinstance(profile, Mapping):
            continue
        profile_id = str(profile.get("profile_id", ""))
        score = profile.get("baseline_normalized_score")
        if profile_id and isinstance(score, Mapping):
            scores[profile_id] = score
    return scores


def _sample_id(
    *,
    profile_id: str,
    record_index: int,
    wave_index: int | None,
    dispatch_seq: int | None,
    candidate_key: str,
    attempt_index: int | None,
) -> str:
    return (
        f"{profile_id}:r{record_index}:w{wave_index if wave_index is not None else 'na'}:"
        f"d{dispatch_seq if dispatch_seq is not None else 'na'}:"
        f"a{attempt_index if attempt_index is not None else 'na'}:{candidate_key}"
    )


def _run_id(record: Mapping[str, Any], profile_id: str) -> str:
    output_json = record.get("output_json")
    if output_json:
        return Path(str(output_json)).stem
    return f"{profile_id}_{record.get('target', 'run')}"


def _terminal_classification(
    *,
    status: str,
    outcome: str,
    precheck_triggered: bool,
    master_solve_skipped: bool,
) -> str:
    if precheck_triggered and master_solve_skipped:
        return "precheck_eliminated"
    if status == "UNKNOWN" or outcome == "unknown":
        return "master_unknown"
    if status == "INFEASIBLE":
        return "master_infeasible"
    if status == "CERTIFIED":
        return "certified"
    return "other"


def _terminal_subtype(
    *,
    status: str,
    precheck_payload: Mapping[str, Any],
    proof: Mapping[str, Any],
    master_last_solve: Mapping[str, Any],
) -> str | None:
    reason = precheck_payload.get("precheck_reason")
    if reason:
        return str(reason)
    if status == "UNKNOWN":
        branches = _int_or_none(master_last_solve.get("branches"))
        start_feasibility = _mapping(proof.get("master_start_feasibility"))
        hint_status = start_feasibility.get("ghost_anchor_hint_status")
        if branches == 0 and hint_status:
            return f"zero_branch_unknown:{hint_status}"
        if branches == 0:
            return "zero_branch_unknown"
        return "unknown"
    return None


def _became_terminal_fast(master_last_solve: Mapping[str, Any]) -> bool:
    wall_time = _number_or_none(master_last_solve.get("wall_time"))
    if wall_time is None:
        return False
    return wall_time <= 5.0


def _high_prune_gain(frontier_metrics: Mapping[str, Any]) -> bool:
    prune_gain = _int_or_none(frontier_metrics.get("certification_prune_gain"))
    anchor_count = _int_or_none(frontier_metrics.get("anchor_count"))
    if prune_gain is None:
        return False
    if anchor_count is None or anchor_count <= 0:
        return prune_gain > 0
    return (float(prune_gain) / float(anchor_count)) >= 10.0


def _sample_sort_key(sample: Mapping[str, Any]) -> tuple[Any, ...]:
    source = _mapping(sample.get("source"))
    return (
        str(sample.get("profile_id", "")),
        _int_or_none(source.get("record_index")) or 0,
        _int_or_none(source.get("wave_index")) or 0,
        _int_or_none(source.get("dispatch_seq")) or 0,
        str(sample.get("candidate_key", "")),
        _int_or_none(source.get("attempt_index")) or 0,
    )


def _infer_profile_id(record: Mapping[str, Any]) -> str:
    process_count = _int_or_none(record.get("process_count")) or _int_or_none(
        record.get("parallel_processes")
    ) or 0
    worker_count = _int_or_none(record.get("worker_count_per_process"))
    if worker_count is None:
        worker_count = _int_or_none(_mapping(record.get("worker_profile")).get("master")) or 0
    return f"prod_{process_count}x{worker_count}"


def _normalized_cpu_percent(value: Any, logical_cpu_count: int | None) -> float | None:
    number = _number_or_none(value)
    if number is None or logical_cpu_count is None or logical_cpu_count <= 0:
        return None
    return round(float(number) / float(logical_cpu_count), 6)


def _bytes_to_gib(value: int | None) -> float | None:
    if value is None:
        return None
    return round(float(value) / (1024 ** 3), 6)


def _number_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

