"""Local web viewer launcher."""

from __future__ import annotations

import http.server
import hashlib
import os
from pathlib import Path
import shutil
import socketserver
import tempfile
from typing import Optional
import webbrowser

from src.search.exact_campaign import atomic_write_json
from src.io.serializer import load_candidate_placements, load_json_mapping
from src.render.report_builder import (
    VIEWER_REPORT_FILENAME,
    build_viewer_report_from_surface_snapshot,
)
from src.search.certified_surface import evaluate_certified_delivery_surface

VIEWER_CANDIDATE_PLACEMENTS_FILENAME = "candidate_placements.json"
VIEWER_GENERATION_MANIFEST_FILENAME = "viewer_generation_manifest.json"

_VIEWER_CERTIFIED_OUTPUTS = (
    VIEWER_GENERATION_MANIFEST_FILENAME,
    "final_solution.json",
    "optimal_blueprint.json",
    VIEWER_CANDIDATE_PLACEMENTS_FILENAME,
    VIEWER_REPORT_FILENAME,
)


def _remove_stale_viewer_outputs(viewer_dir: Path) -> None:
    cleanup_errors: list[str] = []
    for filename in _VIEWER_CERTIFIED_OUTPUTS:
        try:
            (viewer_dir / filename).unlink()
        except FileNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001 - cleanup must try every public viewer artifact.
            cleanup_errors.append(f"{filename}:{type(exc).__name__}:{exc}")
    if cleanup_errors:
        raise RuntimeError("certified viewer cleanup failed: " + ";".join(cleanup_errors))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_viewer_generation_manifest(staging_dir: Path) -> None:
    artifact_names = [
        name for name in _VIEWER_CERTIFIED_OUTPUTS if name != VIEWER_GENERATION_MANIFEST_FILENAME
    ]
    payload = {
        "metadata": {
            "schema": "certified_viewer_generation_manifest",
            "version": 1,
            "role": "postprocess_sidecar",
        },
        "artifacts": {
            name: {"sha256": _sha256_file(staging_dir / name)}
            for name in artifact_names
        },
    }
    atomic_write_json(staging_dir / VIEWER_GENERATION_MANIFEST_FILENAME, payload)


def _commit_viewer_generation(*, staging_dir: Path, viewer_dir: Path) -> None:
    try:
        for filename in _VIEWER_CERTIFIED_OUTPUTS:
            if filename == VIEWER_GENERATION_MANIFEST_FILENAME:
                continue
            (staging_dir / filename).replace(viewer_dir / filename)
        (staging_dir / VIEWER_GENERATION_MANIFEST_FILENAME).replace(
            viewer_dir / VIEWER_GENERATION_MANIFEST_FILENAME
        )
    except Exception:
        _remove_stale_viewer_outputs(viewer_dir)
        raise


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

    pools_path = project_root / "data" / "preprocessed" / "candidate_placements.json"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"

    surface = evaluate_certified_delivery_surface(
        project_root=project_root,
        campaign_state=None,
        campaign_path=campaign_path,
    )
    if not surface.publishable:
        _remove_stale_viewer_outputs(viewer_dir)
        raise RuntimeError(
            "certified viewer surface is not publishable: "
            f"{surface.blocked_reason or getattr(surface, 'reason', None) or 'unknown'}"
        )

    final_solution_payload = getattr(surface, "final_solution_payload", None)
    optimal_blueprint_payload = getattr(surface, "optimal_blueprint_payload", None)
    if final_solution_payload is None or optimal_blueprint_payload is None:
        _remove_stale_viewer_outputs(viewer_dir)
        raise RuntimeError("certified viewer surface snapshot is missing canonical payloads")

    if not pools_path.exists():
        _remove_stale_viewer_outputs(viewer_dir)
        raise RuntimeError("certified viewer generation requires candidate_placements.json")

    try:
        rules_path = project_root / "rules" / "canonical_rules.json"
        facility_pools = load_candidate_placements(pools_path)
        rules_payload = load_json_mapping(rules_path) if rules_path.exists() else {}
        viewer_report = build_viewer_report_from_surface_snapshot(
            surface=surface,
            facility_pools=facility_pools,
            rules_payload=rules_payload,
        )
        with tempfile.TemporaryDirectory(prefix=".viewer-generation-", dir=str(viewer_dir)) as tmp:
            staging_dir = Path(tmp)
            atomic_write_json(staging_dir / "final_solution.json", final_solution_payload)
            atomic_write_json(staging_dir / "optimal_blueprint.json", optimal_blueprint_payload)
            shutil.copy2(pools_path, staging_dir / VIEWER_CANDIDATE_PLACEMENTS_FILENAME)
            atomic_write_json(staging_dir / VIEWER_REPORT_FILENAME, viewer_report)
            _write_viewer_generation_manifest(staging_dir)
            _commit_viewer_generation(staging_dir=staging_dir, viewer_dir=viewer_dir)
    except Exception:
        _remove_stale_viewer_outputs(viewer_dir)
        raise

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
