"""Build viewer_report.json from canonical project artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.render.report_builder import build_viewer_report_from_project_root, write_viewer_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build viewer_report.json from project-root artifacts.")
    parser.add_argument("--project-root", default=".", help="Project root containing data/ and rules/.")
    parser.add_argument("--output", default="src/render/web_viewer/viewer_report.json", help="Output report path.")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    payload = build_viewer_report_from_project_root(project_root)
    write_viewer_report(Path(args.output), payload)
    print(f"viewer report written: {args.output}")


if __name__ == "__main__":
    main()
