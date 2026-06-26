"""No-drift audit for the checked-in IndustrialPlanner single-base delivery surface."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.render.industrial_planner_single_base_delivery_surface_alignment import (  # noqa: E402
    _DEFAULT_ENTRYPOINTS_JSON,
    _DEFAULT_ENTRYPOINTS_MARKDOWN,
    _DEFAULT_FRONTDOOR_MANIFEST_JSON,
    _DEFAULT_SURFACE_HEALTH_CONSOLE,
    _DEFAULT_SURFACE_HEALTH_JSON,
    _DEFAULT_SURFACE_HEALTH_MARKDOWN,
    _DEFAULT_OUTPUT_CONSOLE,
    _DEFAULT_OUTPUT_JSON,
    _DEFAULT_OUTPUT_MARKDOWN,
    SingleBaseDeliverySurfaceAlignmentError,
    build_single_base_delivery_surface_alignment_result,
    write_single_base_delivery_surface_alignment_outputs,
)



def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the checked-in IndustrialPlanner single-base repo-front frontdoor and aggregate active-entrypoints "
            "manifest for no-drift alignment."
        )
    )
    parser.add_argument(
        "--frontdoor-manifest-json",
        type=Path,
        default=_DEFAULT_FRONTDOOR_MANIFEST_JSON,
        help="Checked-in repo-front frontdoor manifest to audit.",
    )
    parser.add_argument(
        "--entrypoints-json",
        type=Path,
        default=_DEFAULT_ENTRYPOINTS_JSON,
        help="Checked-in aggregate active-entrypoints JSON manifest to audit.",
    )
    parser.add_argument(
        "--entrypoints-markdown",
        type=Path,
        default=_DEFAULT_ENTRYPOINTS_MARKDOWN,
        help="Checked-in aggregate active-entrypoints Markdown summary expected next to the JSON manifest.",
    )
    parser.add_argument(
        "--current-surface-health-json",
        type=Path,
        default=_DEFAULT_SURFACE_HEALTH_JSON,
        help="Checked-in compact current-surface-health JSON snapshot expected to align with the frontdoor/entrypoints surface.",
    )
    parser.add_argument(
        "--current-surface-health-markdown",
        type=Path,
        default=_DEFAULT_SURFACE_HEALTH_MARKDOWN,
        help="Checked-in compact current-surface-health Markdown snapshot expected next to the JSON snapshot.",
    )
    parser.add_argument(
        "--current-surface-health-console",
        type=Path,
        default=_DEFAULT_SURFACE_HEALTH_CONSOLE,
        help="Checked-in compact current-surface-health plain-text snapshot expected next to the JSON snapshot.",
    )
    parser.add_argument(
        "--require-surface-health-visibility",
        action="store_true",
        help="Fail closed unless the checked-in frontdoor and aggregate entrypoints visibly surface the current_surface_health JSON/Markdown/TXT trio.",
    )
    parser.add_argument(
        "--require-surface-alignment-visibility",
        action="store_true",
        help=(
            "Fail closed unless the surface-alignment JSON/Markdown/console summaries already exist as "
            "checked-in outputs. OFF by default: this audit GENERATES those summaries fresh each run "
            "(written to --json/--markdown/--console-output and uploaded as CI artifacts), so requiring "
            "its own not-yet-written output to pre-exist would be a self-contradiction. Pass this flag "
            "only in a separate verification context where the summaries are already committed."
        ),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=_DEFAULT_OUTPUT_JSON,
        help="Where to write the machine-readable audit summary JSON.",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=_DEFAULT_OUTPUT_MARKDOWN,
        help="Where to write the human-readable audit summary Markdown.",
    )
    parser.add_argument(
        "--console-output",
        type=Path,
        default=_DEFAULT_OUTPUT_CONSOLE,
        help="Where to write the plain-text console summary.",
    )
    return parser



def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        result = build_single_base_delivery_surface_alignment_result(
            project_root=PROJECT_ROOT,
            frontdoor_manifest_json_path=args.frontdoor_manifest_json,
            entrypoints_json_path=args.entrypoints_json,
            entrypoints_markdown_path=args.entrypoints_markdown,
            current_surface_health_json_path=args.current_surface_health_json,
            current_surface_health_markdown_path=args.current_surface_health_markdown,
            current_surface_health_console_path=args.current_surface_health_console,
            require_surface_health_visibility=args.require_surface_health_visibility,
            require_surface_alignment_visibility=args.require_surface_alignment_visibility,
        )
        outputs = write_single_base_delivery_surface_alignment_outputs(
            result,
            json_output_path=args.json_output,
            markdown_output_path=args.markdown_output,
            console_output_path=args.console_output,
        )
    except SingleBaseDeliverySurfaceAlignmentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    console_text = outputs.result.to_console_text()
    print(console_text)
    return 0 if outputs.result.is_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
