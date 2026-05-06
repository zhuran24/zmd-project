"""Local web viewer launcher."""

from __future__ import annotations

import http.server
import os
from pathlib import Path
import shutil
import socketserver
from typing import Optional
import webbrowser

from src.render.report_builder import (
    VIEWER_REPORT_FILENAME,
    build_viewer_report_from_project_root,
    write_viewer_report,
)


def serve_viewer(
    port: int = 8070,
    project_root: Optional[Path] = None,
    *,
    viewer_dir: Optional[Path] = None,
) -> None:
    """Start a local HTTP server for the interactive viewer."""
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent.parent
    if viewer_dir is None:
        viewer_dir = Path(__file__).parent / "web_viewer"
    viewer_dir.mkdir(parents=True, exist_ok=True)

    solution_path = project_root / "data" / "solutions" / "final_solution.json"
    blueprint_path = project_root / "data" / "blueprints" / "optimal_blueprint.json"
    pools_path = project_root / "data" / "preprocessed" / "candidate_placements.json"

    if solution_path.exists():
        shutil.copy2(solution_path, viewer_dir / "final_solution.json")
    if blueprint_path.exists():
        shutil.copy2(blueprint_path, viewer_dir / "optimal_blueprint.json")
    if pools_path.exists():
        shutil.copy2(pools_path, viewer_dir / "candidate_placements.json")

    if blueprint_path.exists() and pools_path.exists():
        try:
            viewer_report = build_viewer_report_from_project_root(project_root)
            write_viewer_report(viewer_dir / VIEWER_REPORT_FILENAME, viewer_report)
        except Exception as exc:  # pragma: no cover - viewer report is best-effort.
            print(f"[VIS-04] viewer_report generation skipped: {exc}")

    print("\n[VIS-04] 启动交互式查看器")
    print(f"   打开浏览器: http://localhost:{port}")
    print("   按 Ctrl+C 停止\n")

    previous_cwd = Path.cwd()
    try:
        os.chdir(str(viewer_dir))
        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", port), handler) as httpd:
            webbrowser.open(f"http://localhost:{port}")
            httpd.serve_forever()
    finally:
        os.chdir(str(previous_cwd))


if __name__ == "__main__":
    serve_viewer()
