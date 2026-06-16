from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.checkpoint_free_evaluator import (
    ALLOWED_DURATIONS_SECONDS,
    ARTIFACT_ROOT,
    DEFAULT_MAX_TOTAL_PRIVATE_GIB,
    DEFAULT_MAX_TOTAL_RSS_GIB,
    DEFAULT_READINESS_PACKET,
    LOG_ROOT,
    run_checkpoint_free_evaluator,
    validate_checkpoint_free_request,
)


def _parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Run or plan a Phase3B checkpoint-free short-run evaluator."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true", help="Actually run one checkpoint-free wave.")
    mode.add_argument("--plan-only", action="store_true", help="Generate a plan without workers.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--readiness-packet", type=Path, default=DEFAULT_READINESS_PACKET)
    parser.add_argument("--candidate-id", default="B0_prod_4x4")
    parser.add_argument("--duration-seconds", type=int, default=300)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    parser.add_argument("--log-root", type=Path, default=LOG_ROOT)
    parser.add_argument("--max-wave-candidates", type=int, default=None)
    parser.add_argument(
        "--wave-candidate-key",
        action="append",
        default=[],
        help="Restrict this checkpoint-free diagnostic wave to an explicit current-frontier candidate key such as 42x32. Repeat for multiple keys.",
    )
    parser.add_argument(
        "--exclude-wave-candidate-key",
        action="append",
        default=[],
        help="Exclude a current-frontier candidate key from this checkpoint-free diagnostic wave. Repeat for multiple keys.",
    )
    parser.add_argument("--sample-interval-seconds", type=float, default=0.5)
    parser.add_argument("--max-total-private-gib", type=float, default=DEFAULT_MAX_TOTAL_PRIVATE_GIB)
    parser.add_argument("--max-total-rss-gib", type=float, default=DEFAULT_MAX_TOTAL_RSS_GIB)
    return parser.parse_known_args(argv)


def main(argv: list[str] | None = None) -> int:
    args, extra_tokens = _parse_args(argv)
    project_root = Path(args.project_root).resolve()
    artifact_root = _resolve_output_root(project_root, Path(args.artifact_root))
    log_root = _resolve_output_root(project_root, Path(args.log_root))
    guard = validate_checkpoint_free_request(
        duration_seconds=int(args.duration_seconds),
        artifact_root=artifact_root,
        log_root=log_root,
        extra_tokens=extra_tokens,
    )
    if not guard["allowed"]:
        print("phase3b checkpoint-free evaluator request rejected", file=sys.stderr)
        for reason in guard["reasons"]:
            print(f"- {reason}", file=sys.stderr)
        return 2
    if int(args.duration_seconds) not in set(ALLOWED_DURATIONS_SECONDS):
        print("unsupported duration", file=sys.stderr)
        return 2

    summary = run_checkpoint_free_evaluator(
        project_root=project_root,
        readiness_packet_path=Path(args.readiness_packet),
        candidate_id=str(args.candidate_id),
        duration_seconds=int(args.duration_seconds),
        execute=bool(args.execute),
        artifact_root=artifact_root,
        log_root=log_root,
        run_id=args.run_id,
        max_wave_candidates=args.max_wave_candidates,
        wave_candidate_keys=args.wave_candidate_key,
        exclude_wave_candidate_keys=args.exclude_wave_candidate_key,
        sample_interval_seconds=float(args.sample_interval_seconds),
        max_total_private_gib=args.max_total_private_gib,
        max_total_rss_gib=args.max_total_rss_gib,
    )
    print("phase3b checkpoint-free evaluator")
    print(f"candidate_id={summary['candidate_id']}")
    print(f"status={summary['status']}")
    print(f"execute={summary['execute']}")
    print(f"checkpoint_free={summary['checkpoint_free']}")
    print(f"main_py_executed={summary['main_py_executed']}")
    print(f"exact_campaign_used={summary['exact_campaign_used']}")
    print(f"checkpoint_written={summary['checkpoint_written']}")
    print(f"run_summary_json={_display_path(project_root, Path(summary['paths']['run_summary_json']))}")
    return 0 if summary["status"] in {"planned_only", "completed"} else 2


def _resolve_output_root(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(Path(path))


if __name__ == "__main__":
    raise SystemExit(main())
