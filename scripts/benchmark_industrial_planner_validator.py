"""Benchmark harness for the pure-Python IndustrialPlanner blueprint validator."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.industrial_planner.blueprint_validator import validate_industrial_planner_blueprint


def _percentile(sorted_values: Sequence[float], quantile: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * float(quantile)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return float(sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction)


def run_validator_benchmark(
    blueprint_path: Path,
    *,
    iterations: int,
    warmup: int,
) -> dict[str, Any]:
    blueprint_path = Path(blueprint_path)
    payload = json.loads(blueprint_path.read_text(encoding="utf-8"))

    if iterations <= 0:
        raise ValueError("iterations must be > 0")
    if warmup < 0:
        raise ValueError("warmup must be >= 0")

    for _ in range(warmup):
        validate_industrial_planner_blueprint(payload)

    durations: list[float] = []
    reports: list[tuple[bool, bool, bool, int, int]] = []
    for _ in range(iterations):
        start = time.perf_counter()
        report = validate_industrial_planner_blueprint(payload)
        durations.append(time.perf_counter() - start)
        reports.append(
            (
                bool(report.is_import_compatible),
                bool(report.is_layout_healthy),
                bool(report.is_clean),
                len(report.port_warnings),
                len(report.port_mismatch_errors),
            )
        )

    sorted_durations = sorted(float(value) for value in durations)
    first_report = reports[0]
    if any(report != first_report for report in reports[1:]):
        raise RuntimeError("validator benchmark observed inconsistent validation outcomes across iterations")

    return {
        "benchmark_name": "industrial_planner_validator",
        "fixture_path": str(blueprint_path.as_posix()),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "iterations": int(iterations),
        "warmup": int(warmup),
        "device_count": int(len(payload.get("devices", []))) if isinstance(payload, dict) else 0,
        "base_id": str(payload.get("baseId", "")) if isinstance(payload, dict) else "",
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "validation_is_import_compatible": bool(first_report[0]),
        "validation_is_layout_healthy": bool(first_report[1]),
        "validation_is_clean": bool(first_report[2]),
        "validation_port_warning_count": int(first_report[3]),
        "validation_port_mismatch_count": int(first_report[4]),
        "min_seconds": float(min(sorted_durations)),
        "mean_seconds": float(statistics.fmean(sorted_durations)),
        "median_seconds": float(statistics.median(sorted_durations)),
        "p95_seconds": _percentile(sorted_durations, 0.95),
        "max_seconds": float(max(sorted_durations)),
        "raw_seconds": [float(value) for value in durations],
    }


def render_markdown_report(result: dict[str, Any], *, command: str) -> str:
    mean_seconds = float(result["mean_seconds"])
    if mean_seconds <= 2.0:
        conclusion = f"The reference run is comfortably within the 2-second class (mean {mean_seconds:.3f}s)."
    else:
        conclusion = f"The reference run is above the 2-second class target (mean {mean_seconds:.3f}s)."

    p95 = result.get("p95_seconds")
    p95_text = f"{float(p95):.6f}" if p95 is not None else "n/a"

    lines = [
        "# IndustrialPlanner Validator Benchmark (70×70)",
        "",
        "## Fixture",
        f"- Path: `{result['fixture_path']}`",
        f"- Base: `{result['base_id']}`",
        f"- User devices: {result['device_count']}",
        f"- Import compatible: {'yes' if result['validation_is_import_compatible'] else 'no'}",
        f"- Layout healthy: {'yes' if result['validation_is_layout_healthy'] else 'no'}",
        f"- Clean export: {'yes' if result['validation_is_clean'] else 'no'}",
        f"- Port warnings: {result['validation_port_warning_count']}",
        f"- Port mismatches: {result['validation_port_mismatch_count']}",
        "",
        "## Command",
        "```bash",
        command,
        "```",
        "",
        "## Environment",
        f"- Generated at (UTC): {result['generated_at_utc']}",
        f"- Python: {result['python_implementation']} {result['python_version']}",
        f"- Platform: {result['platform']}",
        f"- Warmup iterations: {result['warmup']}",
        f"- Measured iterations: {result['iterations']}",
        "",
        "## Results",
        "| Metric | Seconds |",
        "|---|---:|",
        f"| Min | {float(result['min_seconds']):.6f} |",
        f"| Mean | {float(result['mean_seconds']):.6f} |",
        f"| Median | {float(result['median_seconds']):.6f} |",
        f"| P95 | {p95_text} |",
        f"| Max | {float(result['max_seconds']):.6f} |",
        "",
        "## Conclusion",
        conclusion,
        "",
        "This benchmark is a deterministic synthetic 70×70 fixture meant to exercise import/layout-health validation at lot scale. It is not a throughput proof and does not simulate factory ticks.",
        "",
    ]
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprint_path", type=Path, help="Path to an IndustrialPlanner blueprint JSON file")
    parser.add_argument("--iterations", type=int, default=7, help="Measured benchmark iterations")
    parser.add_argument("--warmup", type=int, default=2, help="Warmup iterations before measuring")
    parser.add_argument("--json-output", type=Path, default=None, help="Optional path for benchmark JSON output")
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help="Optional path for a markdown benchmark report",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_validator_benchmark(
        args.blueprint_path,
        iterations=args.iterations,
        warmup=args.warmup,
    )
    command = " \\\n  ".join(
        [
            f"python scripts/{Path(__file__).name} {args.blueprint_path.as_posix()}",
            f"--warmup {args.warmup}",
            f"--iterations {args.iterations}",
            *(
                [f"--json-output {args.json_output.as_posix()}"]
                if args.json_output is not None
                else []
            ),
            *(
                [f"--markdown-output {args.markdown_output.as_posix()}"]
                if args.markdown_output is not None
                else []
            ),
        ]
    )
    markdown = render_markdown_report(result, command=command)

    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(markdown, encoding="utf-8")

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
