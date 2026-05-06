from __future__ import annotations

from typing import Any

AI_CANDIDATE_RUN_SAMPLE_SCHEMA_ID = "phase3b_ai_candidate_run_sample_v0"
AI_FEATURE_DATASET_SUMMARY_SCHEMA_ID = "phase3b_ai_feature_dataset_summary_v0"


def build_candidate_run_feature_schema() -> dict[str, Any]:
    return {
        "schema": "phase3b_ai_feature_schema_v0",
        "sample_schema": AI_CANDIDATE_RUN_SAMPLE_SCHEMA_ID,
        "safety_contract": build_ai_dataset_safety_contract(),
        "required_top_level_fields": [
            "schema",
            "sample_id",
            "candidate_key",
            "run_id",
            "profile_id",
            "parallel_processes",
            "worker_profile",
            "selection_reason",
            "frontier_candidate_metrics",
            "precheck",
            "terminal",
            "solver_metrics",
            "resource_metrics",
            "labels",
        ],
        "field_notes": {
            "frontier_candidate_metrics": "Copied from exact telemetry; feature only, not proof.",
            "precheck": "Describes existing precheck telemetry; extractor does not run prechecks.",
            "terminal": "Observed terminal status/outcome from existing evidence replay.",
            "solver_metrics": "Copied from master_last_solve when present; null when absent.",
            "resource_metrics": "Run/window resource observations from existing benchmark evidence.",
            "labels": "Derived weak labels for future offline replay, not certified truth.",
        },
    }


def build_ai_dataset_safety_contract() -> dict[str, Any]:
    return {
        "shadow_only": True,
        "proof_source": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "model_trained": False,
        "checkpoint_written": False,
        "final_solution_written": False,
        "release_viewer_frontdoor_promoted": False,
    }

