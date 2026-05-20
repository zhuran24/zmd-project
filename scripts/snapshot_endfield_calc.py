"""Normalize endfield-calc snapshots into NeutralCatalog JSON and optional diff reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.endfield_calc.diff_report import (  # noqa: E402
    build_catalog_diff_report,
    render_catalog_diff_markdown,
)
from src.adapters.endfield_calc.semantic_mapping import (  # noqa: E402
    CURRENT_REPOSITORY_SEMANTIC_TARGET,
    available_semantic_targets,
    project_catalog_to_semantic_target,
)
from src.adapters.endfield_calc.snapshot_ingest import (  # noqa: E402
    ingest_snapshot_source,
    load_snapshot_source,
    write_snapshot_payload,
)
from src.interchange.normalized_catalog import build_catalog_from_rules_payload  # noqa: E402
from src.search.exact_campaign import atomic_write_json  # noqa: E402


SEMANTIC_TARGET_CHOICES = available_semantic_targets()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize a JSON snapshot, extracted endfield-calc repo, or endfield-calc zip archive into NeutralCatalog JSON."
    )
    parser.add_argument(
        "snapshot_dir",
        nargs="?",
        default="third_party_snapshots/endfield_calc/minimal_fixture",
        help="Path to a JSON snapshot directory, an extracted endfield-calc repository root, a flat TypeScript fixture directory, or a .zip archive containing the upstream repo.",
    )
    parser.add_argument(
        "--source-format",
        choices=("auto", "json", "typescript"),
        default="auto",
        help="Interpretation mode for the input directory.",
    )
    parser.add_argument(
        "--output",
        default="data/solutions/endfield_calc.normalized_catalog.json",
        help="Output JSON path for the raw normalized catalog.",
    )
    parser.add_argument(
        "--emit-snapshot-dir",
        default=None,
        help="Optional directory where the parsed raw snapshot JSON should be materialized. Useful for TypeScript source inputs.",
    )
    parser.add_argument(
        "--compare-rules",
        default=None,
        help="Optional rules/canonical_rules.json path used to build a reference normalized catalog for diff reporting.",
    )
    parser.add_argument(
        "--diff-output",
        default=None,
        help="Optional JSON path for a raw-catalog diff report.",
    )
    parser.add_argument(
        "--diff-markdown-output",
        default=None,
        help="Optional Markdown path for a human-readable raw-catalog diff report.",
    )
    parser.add_argument(
        "--semantic-target",
        choices=SEMANTIC_TARGET_CHOICES,
        default=None,
        help=(
            "Optional semantic-alignment target. "
            f"Use {CURRENT_REPOSITORY_SEMANTIC_TARGET!r} to project the verified overlapping slice into local canonical IDs."
        ),
    )
    parser.add_argument(
        "--semantic-output",
        default=None,
        help="Optional JSON path for the semantically aligned catalog.",
    )
    parser.add_argument(
        "--semantic-diff-output",
        default=None,
        help="Optional JSON path for a semantic-alignment diff report.",
    )
    parser.add_argument(
        "--semantic-diff-markdown-output",
        default=None,
        help="Optional Markdown path for a human-readable semantic-alignment diff report.",
    )
    args = parser.parse_args()

    snapshot_dir = Path(args.snapshot_dir)
    output_path = Path(args.output)

    normalized_catalog = ingest_snapshot_source(snapshot_dir, source_format=args.source_format)
    atomic_write_json(output_path, normalized_catalog)
    print(f"raw normalized catalog written: {output_path}")

    if args.emit_snapshot_dir:
        loaded = load_snapshot_source(snapshot_dir, source_format=args.source_format)
        write_snapshot_payload(Path(args.emit_snapshot_dir), loaded)
        print(f"raw snapshot materialized: {Path(args.emit_snapshot_dir)}")

    semantic_catalog: dict[str, object] | None = None
    if args.semantic_target:
        semantic_catalog = project_catalog_to_semantic_target(normalized_catalog, target=args.semantic_target)
        if args.semantic_output:
            semantic_output_path = Path(args.semantic_output)
            atomic_write_json(semantic_output_path, semantic_catalog)
            print(f"semantic catalog written: {semantic_output_path}")

    if args.compare_rules:
        rules_path = Path(args.compare_rules)
        rules_payload = json.loads(rules_path.read_text(encoding="utf-8"))
        reference_catalog = build_catalog_from_rules_payload(rules_payload)

        raw_diff_requested = args.diff_output or args.diff_markdown_output
        if raw_diff_requested:
            diff_report = build_catalog_diff_report(reference_catalog, normalized_catalog)
            if args.diff_output:
                atomic_write_json(Path(args.diff_output), diff_report)
                print(f"raw catalog diff written: {Path(args.diff_output)}")
            if args.diff_markdown_output:
                Path(args.diff_markdown_output).write_text(
                    render_catalog_diff_markdown(diff_report),
                    encoding="utf-8",
                )
                print(f"raw catalog diff markdown written: {Path(args.diff_markdown_output)}")

        semantic_diff_requested = args.semantic_diff_output or args.semantic_diff_markdown_output
        if semantic_diff_requested:
            if semantic_catalog is None:
                raise SystemExit("semantic diff requested but --semantic-target was not provided")
            semantic_diff_report = build_catalog_diff_report(reference_catalog, semantic_catalog)
            if args.semantic_diff_output:
                atomic_write_json(Path(args.semantic_diff_output), semantic_diff_report)
                print(f"semantic catalog diff written: {Path(args.semantic_diff_output)}")
            if args.semantic_diff_markdown_output:
                Path(args.semantic_diff_markdown_output).write_text(
                    render_catalog_diff_markdown(semantic_diff_report),
                    encoding="utf-8",
                )
                print(f"semantic catalog diff markdown written: {Path(args.semantic_diff_markdown_output)}")


if __name__ == "__main__":
    main()
