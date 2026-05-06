from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_WAVE_DIAGNOSIS = (
    ARTIFACT_ROOT / "11_wave_straggler_diagnosis" / "checkpoint_free_wave_diagnosis.json"
)
DEFAULT_SCOREBOARD = (
    ARTIFACT_ROOT / "09_checkpoint_free_scoreboard" / "checkpoint_free_eval_scoreboard.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "13_resource_hotspot_strategy"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_resource_hotspot_strategy(
        wave_diagnosis_path=_resolve_path(PROJECT_ROOT, args.wave_diagnosis),
        scoreboard_path=_resolve_path(PROJECT_ROOT, args.scoreboard),
    )
    print("phase3b checkpoint-free resource hotspot strategy")
    print(f"isolated_resource_stop_keys={','.join(strategy['hotspot_keys']['isolated_resource_stop_keys'])}")
    print(f"avoid_key_count={len(strategy['recommendation']['avoid_candidate_keys_for_wave_expansion'])}")
    if not args.no_write:
        paths = write_resource_hotspot_strategy(strategy, _resolve_path(PROJECT_ROOT, args.output_dir))
        print(f"strategy_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"strategy_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a read-only resource-hotspot strategy from checkpoint-free diagnostics."
    )
    parser.add_argument("--wave-diagnosis", type=Path, default=DEFAULT_WAVE_DIAGNOSIS)
    parser.add_argument("--scoreboard", type=Path, default=DEFAULT_SCOREBOARD)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_resource_hotspot_strategy(
    *,
    wave_diagnosis_path: Path,
    scoreboard_path: Path,
) -> dict[str, Any]:
    wave_diagnosis = _load_json(wave_diagnosis_path)
    scoreboard = _load_json(scoreboard_path)
    runs = [_mapping(run) for run in list(wave_diagnosis.get("runs", []) or []) if isinstance(run, Mapping)]
    isolated_resource_stop_keys = _isolated_resource_stop_keys(runs)
    straggler_keys = _keys_from_summary(wave_diagnosis, "straggler_candidate_keys")
    interrupted_keys = _keys_from_summary(wave_diagnosis, "interrupted_candidate_keys")
    completed_keys = _completed_non_resource_keys(runs)
    avoid_keys = sorted(set(isolated_resource_stop_keys) | set(interrupted_keys))
    retry_only_with_changed_strategy = sorted(set(isolated_resource_stop_keys) | set(straggler_keys))
    return {
        "schema": "phase3b-checkpoint-free-resource-hotspot-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "strategy_kind": "local_checkpoint_free_resource_hotspot_guidance",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "candidate_universe_changed": False,
        "scheduler_integration": False,
        "wave_diagnosis_path": str(wave_diagnosis_path),
        "scoreboard_path": str(scoreboard_path),
        "hotspot_keys": {
            "isolated_resource_stop_keys": isolated_resource_stop_keys,
            "straggler_keys": straggler_keys,
            "interrupted_keys": interrupted_keys,
            "completed_non_resource_keys": completed_keys,
        },
        "recommendation": {
            "action": "hold_full_wave_and_avoid_resource_hotspot_keys",
            "avoid_candidate_keys_for_wave_expansion": avoid_keys,
            "retry_only_with_changed_resource_strategy": retry_only_with_changed_strategy,
            "safe_to_use_as_completed_smoke_keys": completed_keys,
            "next_local_step": (
                "build a checkpoint-free reduced-frontier plan excluding hotspot keys, or "
                "change resource strategy before retrying hotspot keys"
            ),
            "blocked_actions": [
                "do_not_run_full_wave_matrix",
                "do_not_extend_hotspot_keys_to_600s",
                "do_not_promote_local_results_to_proof",
            ],
        },
        "candidate_summary": {
            "candidate_count": len(list(scoreboard.get("candidate_summaries", []) or [])),
            "any_sensitive_path_mutation": bool(
                _mapping(scoreboard.get("safety")).get("sensitive_path_mutation_detected")
            ),
            "resource_stop_run_count": int(
                _mapping(wave_diagnosis.get("summary")).get("resource_stop_run_count") or 0
            ),
            "timeout_run_count": int(
                _mapping(wave_diagnosis.get("summary")).get("timeout_run_count") or 0
            ),
        },
        "safety": {
            "main_py_executed": False,
            "exact_campaign_used": False,
            "proof_source": False,
            "checkpoint_written": False,
            "candidate_universe_changed": False,
            "production_profile_changed": False,
            "scheduler_integration": False,
        },
    }


def write_resource_hotspot_strategy(strategy: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "resource_hotspot_strategy.json"
    md_path = output_dir / "resource_hotspot_strategy.md"
    json_path.write_text(json.dumps(strategy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_resource_hotspot_strategy_markdown(strategy), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_resource_hotspot_strategy_markdown(strategy: Mapping[str, Any]) -> str:
    keys = _mapping(strategy.get("hotspot_keys"))
    recommendation = _mapping(strategy.get("recommendation"))
    summary = _mapping(strategy.get("candidate_summary"))
    lines = [
        "# Phase3B Checkpoint-Free Resource Hotspot Strategy",
        "",
        f"- Generated: `{strategy.get('generated_at')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "- Scheduler integration: `false`",
        f"- Resource-stop runs: `{summary.get('resource_stop_run_count')}`",
        f"- Timeout runs: `{summary.get('timeout_run_count')}`",
        "",
        "## Hotspot Keys",
        "",
        f"- Isolated resource-stop keys: `{', '.join(keys.get('isolated_resource_stop_keys', []))}`",
        f"- Straggler keys: `{', '.join(keys.get('straggler_keys', []))}`",
        f"- Interrupted keys: `{', '.join(keys.get('interrupted_keys', []))}`",
        f"- Completed smoke keys: `{', '.join(keys.get('completed_non_resource_keys', []))}`",
        "",
        "## Recommendation",
        "",
        f"- Avoid in wave expansion: `{', '.join(recommendation.get('avoid_candidate_keys_for_wave_expansion', []))}`",
        f"- Retry only after resource-strategy change: `{', '.join(recommendation.get('retry_only_with_changed_resource_strategy', []))}`",
        f"- Next local step: `{recommendation.get('next_local_step')}`",
        "",
        "This is local diagnostic guidance only. It does not alter scheduler order, proof semantics, production defaults, or canonical checkpoints.",
        "",
    ]
    return "\n".join(lines)


def _isolated_resource_stop_keys(runs: Sequence[Mapping[str, Any]]) -> list[str]:
    keys: set[str] = set()
    for run in runs:
        if not bool(run.get("resource_stop_triggered")):
            continue
        planned = [str(key) for key in list(run.get("planned_candidate_keys", []) or []) if str(key)]
        if int(run.get("wave_selected_count") or len(planned)) != 1:
            continue
        keys.update(planned)
    return sorted(keys)


def _completed_non_resource_keys(runs: Sequence[Mapping[str, Any]]) -> list[str]:
    keys: set[str] = set()
    for run in runs:
        if bool(run.get("resource_stop_triggered")) or bool(run.get("timed_out")):
            continue
        for key in list(run.get("completed_candidate_keys", []) or []):
            if str(key):
                keys.add(str(key))
    return sorted(keys)


def _keys_from_summary(payload: Mapping[str, Any], field: str) -> list[str]:
    return sorted(
        {
            str(key)
            for key in list(_mapping(payload.get("summary")).get(field, []) or [])
            if str(key)
        }
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _load_json(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _resolve_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
