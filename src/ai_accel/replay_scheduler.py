from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.ai_accel.feature_extract import stable_json_dumps

RANKER_POLICIES = (
    "default_evidence_order",
    "prune_gain_first",
    "unknown_risk_avoidance_safe_proxy",
    "hybrid_v0",
)

RANK_FEATURE_WHITELIST = (
    "candidate_key",
    "profile_id",
    "sample_id",
    "source",
    "selection_reason",
    "frontier_candidate_metrics",
    "parallel_processes",
    "process_count",
    "worker_count_per_process",
    "worker_profile",
    "profile_score",
)

RANK_FEATURE_FORBIDDEN_FIELDS = (
    "terminal",
    "labels",
    "solver_metrics",
    "precheck",
    "resource_metrics",
)

USEFUL_TERMINAL_STATUSES = {"INFEASIBLE", "FEASIBLE", "OPTIMAL"}


def read_candidate_runs_jsonl(path: Path) -> list[dict[str, Any]]:
    if not Path(path).exists():
        return []
    samples: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if isinstance(payload, Mapping):
            samples.append(dict(payload))
    return sorted(samples, key=_default_sort_key)


def build_rank_features(sample: Mapping[str, Any]) -> dict[str, Any]:
    candidate_key = str(sample.get("candidate_key") or "")
    width, height = _candidate_dimensions(candidate_key)
    frontier = _mapping(sample.get("frontier_candidate_metrics"))
    selection_reason = str(sample.get("selection_reason") or "")
    worker_profile = _mapping(sample.get("worker_profile"))
    source = _mapping(sample.get("source"))
    return {
        "sample_id": str(sample.get("sample_id") or ""),
        "profile_id": str(sample.get("profile_id") or ""),
        "candidate_key": candidate_key,
        "candidate_width": width,
        "candidate_height": height,
        "candidate_area": None if width is None or height is None else width * height,
        "candidate_aspect_delta": None
        if width is None or height is None
        else abs(float(width) - float(height)),
        "selection_reason": selection_reason,
        "selection_reason_score": _selection_reason_score(selection_reason),
        "certification_prune_gain": _number_or_zero(frontier.get("certification_prune_gain")),
        "frontier_anchor_count": _number_or_zero(frontier.get("anchor_count")),
        "parallel_processes": _number_or_zero(sample.get("parallel_processes")),
        "process_count": _number_or_zero(sample.get("process_count")),
        "worker_count_per_process": _number_or_zero(sample.get("worker_count_per_process")),
        "worker_profile_stage_sum": sum(
            _number_or_zero(worker_profile.get(stage))
            for stage in ("master", "local_capacity", "binding", "routing")
        ),
        "source_order": _source_order_tuple(source),
    }


def rank_samples(
    samples: Sequence[Mapping[str, Any]],
    policy: str,
) -> list[dict[str, Any]]:
    if policy not in RANKER_POLICIES:
        raise ValueError(f"Unknown ranker policy: {policy}")
    ranked = sorted(samples, key=lambda sample: _rank_key(sample, policy))
    return [dict(sample) for sample in ranked]


def build_offline_replay_report(
    samples: Sequence[Mapping[str, Any]],
    *,
    source_artifacts: Mapping[str, Any] | None = None,
    readiness_payload: Mapping[str, Any] | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    sample_list = [dict(sample) for sample in samples]
    grouped = _samples_by_profile(sample_list)
    raw_policy_reports: dict[str, dict[str, Any]] = {}
    for policy in RANKER_POLICIES:
        profile_reports: dict[str, Any] = {}
        for profile_id, profile_samples in grouped.items():
            ranked = rank_samples(profile_samples, policy)
            profile_reports[profile_id] = evaluate_ranked_samples(ranked, top_k=top_k)
        raw_policy_reports[policy] = profile_reports
    policy_reports: dict[str, Any] = {}
    default_profile_reports = raw_policy_reports.get("default_evidence_order", {})
    for policy, profile_reports in raw_policy_reports.items():
        _attach_baseline_normalized_scores(profile_reports, default_profile_reports)
        policy_reports[policy] = {
            "policy": policy,
            "profile_reports": profile_reports,
            "aggregate": _aggregate_policy_report(profile_reports),
        }
    best_policy = _best_policy(policy_reports)
    return {
        "schema": "phase3b-ai-offline-replay-report-v0",
        "report_kind": "s9_offline_replay_v0",
        "artifact_timestamp_policy": "deterministic_input_replay_no_wall_clock",
        "source_fingerprint": candidate_universe_hash(sample_list),
        "source_artifacts": dict(source_artifacts or {}),
        "readiness_summary": _readiness_summary(readiness_payload),
        "rank_feature_contract": {
            "feature_whitelist": list(RANK_FEATURE_WHITELIST),
            "forbidden_as_rank_features": list(RANK_FEATURE_FORBIDDEN_FIELDS),
            "terminal_labels_solver_precheck_used_for_evaluation_only": True,
        },
        "ranker_policies": list(RANKER_POLICIES),
        "sample_count": len(sample_list),
        "profile_count": len(grouped),
        "candidate_universe_hash": candidate_universe_hash(sample_list),
        "policy_reports": policy_reports,
        "best_policy": best_policy,
        "recommendation": _replay_recommendation(policy_reports, best_policy, len(sample_list)),
        "safety": {
            "shadow_only": True,
            "offline_replay_only": True,
            "model_trained": False,
            "fresh_solver_run": False,
            "scheduler_integration": False,
            "candidate_order_changed": False,
            "candidate_universe_changed": False,
            "proof_source": False,
            "checkpoint_written": False,
            "checkpoint_imported_back": False,
            "runtime_elimination_enabled": False,
            "proof_source_mutated": False,
            "release_viewer_frontdoor_promoted": False,
        },
    }


def evaluate_ranked_samples(
    ranked_samples: Sequence[Mapping[str, Any]],
    *,
    top_k: int = 5,
) -> dict[str, Any]:
    sample_count = len(ranked_samples)
    effective_top_k = max(1, min(int(top_k), sample_count)) if sample_count else 0
    useful_flags = [_is_useful_replay_outcome(sample) for sample in ranked_samples]
    unknown_flags = [_terminal_status(sample) == "UNKNOWN" for sample in ranked_samples]
    first_useful_index = None
    for index, useful in enumerate(useful_flags, start=1):
        if useful:
            first_useful_index = index
            break
    top_samples = list(ranked_samples[:effective_top_k])
    top_useful = sum(1 for sample in top_samples if _is_useful_replay_outcome(sample))
    top_unknown = sum(1 for sample in top_samples if _terminal_status(sample) == "UNKNOWN")
    first_useful_score = 0.0 if first_useful_index is None else 1.0 / float(first_useful_index)
    top_k_useful_density = 0.0 if not effective_top_k else top_useful / float(effective_top_k)
    top_k_unknown_density = 0.0 if not effective_top_k else top_unknown / float(effective_top_k)
    unknown_density = 0.0 if not sample_count else sum(unknown_flags) / float(sample_count)
    replay_score = (
        0.45 * top_k_useful_density
        + 0.35 * first_useful_score
        + 0.20 * (1.0 - top_k_unknown_density)
    )
    return {
        "sample_count": sample_count,
        "top_k": effective_top_k,
        "first_useful_hit_index": first_useful_index,
        "top_k_useful_density": round(top_k_useful_density, 6),
        "unknown_density": round(unknown_density, 6),
        "top_k_unknown_density": round(top_k_unknown_density, 6),
        "useful_result_count": int(sum(useful_flags)),
        "unknown_result_count": int(sum(unknown_flags)),
        "replay_score": round(replay_score, 6),
        "baseline_normalized_replay_score": None,
        "ordered_sample_ids": [str(sample.get("sample_id") or "") for sample in ranked_samples],
        "ordered_candidate_keys": [str(sample.get("candidate_key") or "") for sample in ranked_samples],
    }


def build_order_shadow_suggestions(
    samples: Sequence[Mapping[str, Any]],
    replay_report: Mapping[str, Any],
    *,
    source_artifacts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    sample_list = [dict(sample) for sample in samples]
    selected_policy = str(_mapping(replay_report.get("best_policy")).get("policy") or "default_evidence_order")
    grouped = _samples_by_profile(sample_list)
    profiles: list[dict[str, Any]] = []
    output_entries: list[dict[str, str]] = []
    for profile_id, profile_samples in grouped.items():
        default_order = rank_samples(profile_samples, "default_evidence_order")
        suggested_order = rank_samples(profile_samples, selected_policy)
        default_positions = {
            str(sample.get("sample_id") or ""): index
            for index, sample in enumerate(default_order, start=1)
        }
        ordered_candidates = []
        for rank, sample in enumerate(suggested_order, start=1):
            sample_id = str(sample.get("sample_id") or "")
            entry = {
                "rank": rank,
                "sample_id": sample_id,
                "candidate_key": str(sample.get("candidate_key") or ""),
                "default_rank": default_positions.get(sample_id),
                "rank_delta": None
                if default_positions.get(sample_id) is None
                else int(default_positions[sample_id]) - int(rank),
                "ranker_policy": selected_policy,
            }
            ordered_candidates.append(entry)
            output_entries.append(
                {
                    "profile_id": str(profile_id),
                    "sample_id": sample_id,
                    "candidate_key": str(sample.get("candidate_key") or ""),
                }
            )
        profiles.append(
            {
                "profile_id": str(profile_id),
                "ordered_candidates": ordered_candidates,
            }
        )
    input_hash = candidate_universe_hash(sample_list)
    output_hash = _candidate_universe_hash_from_entries(output_entries)
    ab_gate = _shadow_ab_gate(replay_report)
    return {
        "schema": "phase3b-ai-order-shadow-suggestions-v0",
        "suggestion_kind": "s10_order_only_shadow_contract",
        "artifact_timestamp_policy": "deterministic_input_replay_no_wall_clock",
        "module_id": "candidate_ranker_baseline_v0",
        "lifecycle_state": "shadow",
        "selected_policy": selected_policy,
        "source_artifacts": dict(source_artifacts or {}),
        "candidate_universe": {
            "input_hash": input_hash,
            "output_hash": output_hash,
            "changed": input_hash != output_hash,
            "input_count": len(sample_list),
            "output_count": len(output_entries),
            "has_duplicate_output_entries": len(output_entries)
            != len({stable_json_dumps(entry) for entry in output_entries}),
        },
        "profiles": profiles,
        "ab_gate": ab_gate,
        "safety": {
            "shadow_only": True,
            "order_only": True,
            "scheduler_integration": False,
            "suggestion_file_consumed_by_scheduler": False,
            "candidate_order_changed": False,
            "candidate_universe_changed": input_hash != output_hash,
            "may_drop_candidates": False,
            "may_add_candidates": False,
            "may_create_cuts": False,
            "model_trained": False,
            "fresh_solver_run": False,
            "proof_source": False,
            "checkpoint_written": False,
            "checkpoint_imported_back": False,
            "runtime_elimination_enabled": False,
            "proof_source_mutated": False,
            "release_viewer_frontdoor_promoted": False,
        },
    }


def candidate_universe_hash(samples: Sequence[Mapping[str, Any]]) -> str:
    entries = [
        {
            "profile_id": str(sample.get("profile_id") or ""),
            "sample_id": str(sample.get("sample_id") or ""),
            "candidate_key": str(sample.get("candidate_key") or ""),
        }
        for sample in samples
    ]
    return _candidate_universe_hash_from_entries(entries)


def render_offline_replay_markdown(report: Mapping[str, Any]) -> str:
    best = _mapping(report.get("best_policy"))
    recommendation = _mapping(report.get("recommendation"))
    lines = [
        "# Phase3B S9 Offline Replay V0",
        "",
        f"- Report kind: `{report.get('report_kind')}`",
        f"- Sample count: `{report.get('sample_count')}`",
        f"- Candidate universe hash: `{report.get('candidate_universe_hash')}`",
        f"- Best policy: `{best.get('policy')}`",
        f"- A/B eligible: `{recommendation.get('order_only_ab_eligible')}`",
        f"- Proof source: `{_mapping(report.get('safety')).get('proof_source')}`",
        "",
        "| Policy | Mean Score | Mean Normalized | Profiles |",
        "| --- | ---: | ---: | ---: |",
    ]
    for policy, policy_report in _mapping(report.get("policy_reports")).items():
        aggregate = _mapping(_mapping(policy_report).get("aggregate"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(policy),
                    _markdown_cell(aggregate.get("mean_replay_score")),
                    _markdown_cell(aggregate.get("mean_baseline_normalized_replay_score")),
                    _markdown_cell(aggregate.get("profile_count")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def render_shadow_order_diff_markdown(suggestions: Mapping[str, Any]) -> str:
    universe = _mapping(suggestions.get("candidate_universe"))
    ab_gate = _mapping(suggestions.get("ab_gate"))
    lines = [
        "# Phase3B S10 Order-Only Shadow Diff",
        "",
        f"- Suggestion kind: `{suggestions.get('suggestion_kind')}`",
        f"- Selected policy: `{suggestions.get('selected_policy')}`",
        f"- Candidate universe changed: `{universe.get('changed')}`",
        f"- A/B gate status: `{ab_gate.get('status')}`",
        f"- Scheduler integration: `{_mapping(suggestions.get('safety')).get('scheduler_integration')}`",
        "",
        "| Profile | Candidate | Default Rank | Shadow Rank | Delta |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for profile in suggestions.get("profiles", []) or []:
        if not isinstance(profile, Mapping):
            continue
        profile_id = str(profile.get("profile_id") or "")
        for candidate in profile.get("ordered_candidates", []) or []:
            if not isinstance(candidate, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(profile_id),
                        _markdown_cell(candidate.get("candidate_key")),
                        _markdown_cell(candidate.get("default_rank")),
                        _markdown_cell(candidate.get("rank")),
                        _markdown_cell(candidate.get("rank_delta")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def _rank_key(sample: Mapping[str, Any], policy: str) -> tuple[Any, ...]:
    features = build_rank_features(sample)
    source_order = tuple(features["source_order"])
    tie = (
        str(features["profile_id"]),
        str(features["candidate_key"]),
        str(features["sample_id"]),
    )
    if policy == "default_evidence_order":
        return (*source_order, *tie)
    if policy == "prune_gain_first":
        return (
            -float(features["certification_prune_gain"]),
            -float(features["selection_reason_score"]),
            *source_order,
            *tie,
        )
    if policy == "unknown_risk_avoidance_safe_proxy":
        return (
            _none_last(features["candidate_area"]),
            _none_last(features["candidate_aspect_delta"]),
            -float(features["selection_reason_score"]),
            *source_order,
            *tie,
        )
    if policy == "hybrid_v0":
        return (
            -float(features["certification_prune_gain"]),
            _none_last(features["candidate_area"]),
            -float(features["selection_reason_score"]),
            _none_last(features["candidate_aspect_delta"]),
            *source_order,
            *tie,
        )
    raise ValueError(f"Unknown ranker policy: {policy}")


def _samples_by_profile(samples: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for sample in samples:
        profile_id = str(sample.get("profile_id") or "")
        grouped.setdefault(profile_id, []).append(dict(sample))
    return {key: grouped[key] for key in sorted(grouped)}


def _attach_baseline_normalized_scores(
    profile_reports: dict[str, Any],
    default_profile_reports: Mapping[str, Any],
) -> None:
    for profile_id, report in profile_reports.items():
        score = float(_mapping(report).get("replay_score") or 0.0)
        baseline = float(_mapping(_mapping(default_profile_reports).get(profile_id)).get("replay_score") or 0.0)
        report["baseline_normalized_replay_score"] = None if baseline <= 0 else round(score / baseline, 6)


def _aggregate_policy_report(profile_reports: Mapping[str, Any]) -> dict[str, Any]:
    reports = [_mapping(value) for value in profile_reports.values()]
    scores = [float(report.get("replay_score") or 0.0) for report in reports]
    normalized = [
        float(report.get("baseline_normalized_replay_score") or 0.0)
        for report in reports
        if report.get("baseline_normalized_replay_score") is not None
    ]
    return {
        "profile_count": len(reports),
        "mean_replay_score": round(sum(scores) / float(len(scores)), 6) if scores else None,
        "mean_baseline_normalized_replay_score": round(sum(normalized) / float(len(normalized)), 6)
        if normalized
        else None,
    }


def _best_policy(policy_reports: Mapping[str, Any]) -> dict[str, Any]:
    best_policy = "default_evidence_order"
    best_score = -1.0
    for policy, report in policy_reports.items():
        aggregate = _mapping(_mapping(report).get("aggregate"))
        score = float(aggregate.get("mean_replay_score") or 0.0)
        if score > best_score:
            best_policy = str(policy)
            best_score = score
    return {
        "policy": best_policy,
        "mean_replay_score": round(best_score, 6) if best_score >= 0 else None,
    }


def _replay_recommendation(
    policy_reports: Mapping[str, Any],
    best_policy: Mapping[str, Any],
    sample_count: int,
) -> dict[str, Any]:
    default_score = float(
        _mapping(_mapping(policy_reports.get("default_evidence_order")).get("aggregate")).get(
            "mean_replay_score"
        )
        or 0.0
    )
    best_score = float(best_policy.get("mean_replay_score") or 0.0)
    normalized = None if default_score <= 0 else best_score / default_score
    reasons: list[str] = []
    eligible = True
    if sample_count < 100:
        eligible = False
        reasons.append("sample_count_lt_100_shadow_only")
    if normalized is None or normalized < 1.10:
        eligible = False
        reasons.append("best_policy_replay_gain_below_10_percent")
    return {
        "best_policy_vs_default_normalized": None if normalized is None else round(normalized, 6),
        "order_only_ab_eligible": bool(eligible),
        "status": "shadow_diagnostic_only" if not eligible else "candidate_for_future_nonfinal_ab",
        "reasons": reasons,
    }


def _shadow_ab_gate(replay_report: Mapping[str, Any]) -> dict[str, Any]:
    recommendation = _mapping(replay_report.get("recommendation"))
    eligible = bool(recommendation.get("order_only_ab_eligible"))
    return {
        "eligible_for_nonfinal_ab": eligible,
        "status": "candidate_for_future_nonfinal_ab" if eligible else "blocked_diagnostic_only",
        "reasons": list(recommendation.get("reasons") or []),
    }


def _readiness_summary(readiness_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(readiness_payload, Mapping):
        return {"available": False}
    readiness = _mapping(readiness_payload.get("readiness"))
    coverage = _mapping(readiness_payload.get("coverage"))
    leakage = _mapping(readiness_payload.get("leakage_risk"))
    return {
        "available": True,
        "status": readiness.get("status"),
        "sample_count": coverage.get("sample_count"),
        "candidate_count": coverage.get("candidate_count"),
        "leakage_risk_level": leakage.get("risk_level"),
    }


def _is_useful_replay_outcome(sample: Mapping[str, Any]) -> bool:
    labels = _mapping(sample.get("labels"))
    if bool(labels.get("precheck_eliminated")) or bool(labels.get("high_prune_gain")):
        return True
    return _terminal_status(sample) in USEFUL_TERMINAL_STATUSES


def _terminal_status(sample: Mapping[str, Any]) -> str:
    return str(_mapping(sample.get("terminal")).get("status") or "")


def _candidate_dimensions(candidate_key: str) -> tuple[int | None, int | None]:
    parts = str(candidate_key).lower().split("x", 1)
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[0]), int(parts[1])
    except Exception:
        return None, None


def _source_order_tuple(source: Mapping[str, Any]) -> tuple[int, int, int, int]:
    return (
        _int_or_large(source.get("record_index")),
        _int_or_large(source.get("wave_index")),
        _int_or_large(source.get("dispatch_seq")),
        _int_or_large(source.get("attempt_index")),
    )


def _default_sort_key(sample: Mapping[str, Any]) -> tuple[Any, ...]:
    source = _mapping(sample.get("source"))
    return (
        str(sample.get("profile_id") or ""),
        *_source_order_tuple(source),
        str(sample.get("candidate_key") or ""),
        str(sample.get("sample_id") or ""),
    )


def _selection_reason_score(selection_reason: str) -> float:
    reason = str(selection_reason).lower()
    if "prune" in reason:
        return 3.0
    if "frontier" in reason:
        return 2.0
    if "baseline" in reason:
        return 1.0
    return 0.0


def _candidate_universe_hash_from_entries(entries: Sequence[Mapping[str, Any]]) -> str:
    normalized = sorted(
        [
            {
                "profile_id": str(entry.get("profile_id") or ""),
                "sample_id": str(entry.get("sample_id") or ""),
                "candidate_key": str(entry.get("candidate_key") or ""),
            }
            for entry in entries
        ],
        key=lambda item: (item["profile_id"], item["sample_id"], item["candidate_key"]),
    )
    return hashlib.sha256(stable_json_dumps({"entries": normalized}).encode("utf-8")).hexdigest()


def _none_last(value: Any) -> tuple[int, float]:
    if value is None:
        return (1, 0.0)
    try:
        return (0, float(value))
    except Exception:
        return (1, 0.0)


def _number_or_zero(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except Exception:
        return 0.0


def _int_or_large(value: Any) -> int:
    if value is None:
        return 10**9
    try:
        return int(value)
    except Exception:
        return 10**9


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
