from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.b5a.post_acceptance_blocker_summary import (
    DEFAULT_ACCEPTANCE_EXECUTION_GATE,
    DEFAULT_ACCEPTANCE_RESULT_VALIDATOR,
    DEFAULT_B5A_OPERATOR_SUMMARY,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PREFLIGHT_SUMMARY,
    DEFAULT_PRODUCTION_ACCEPTANCE_HANDOFF,
    SummaryPaths,
    build_post_acceptance_b5a_blocker_summary,
    render_post_acceptance_b5a_blocker_summary_markdown,
    write_post_acceptance_b5a_blocker_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Phase3B post-acceptance B5A blocker summary."
    )
    parser.add_argument(
        "--preflight-summary",
        type=Path,
        default=DEFAULT_PREFLIGHT_SUMMARY,
    )
    parser.add_argument(
        "--b5a-operator-summary",
        type=Path,
        default=DEFAULT_B5A_OPERATOR_SUMMARY,
    )
    parser.add_argument(
        "--acceptance-result-validator",
        type=Path,
        default=DEFAULT_ACCEPTANCE_RESULT_VALIDATOR,
    )
    parser.add_argument(
        "--acceptance-execution-gate",
        type=Path,
        default=DEFAULT_ACCEPTANCE_EXECUTION_GATE,
    )
    parser.add_argument(
        "--production-acceptance-handoff",
        type=Path,
        default=DEFAULT_PRODUCTION_ACCEPTANCE_HANDOFF,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    paths = SummaryPaths(
        preflight_summary=args.preflight_summary,
        b5a_operator_summary=args.b5a_operator_summary,
        acceptance_result_validator=args.acceptance_result_validator,
        acceptance_execution_gate=args.acceptance_execution_gate,
        production_acceptance_handoff=args.production_acceptance_handoff,
    )
    summary = build_post_acceptance_b5a_blocker_summary(paths)
    print(render_post_acceptance_b5a_blocker_summary_markdown(summary))

    if not args.no_write:
        written = write_post_acceptance_b5a_blocker_summary(
            summary, args.output_dir
        )
        print(f"Wrote JSON: {written['json']}")
        print(f"Wrote Markdown: {written['md']}")
        print(f"Wrote text: {written['txt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
