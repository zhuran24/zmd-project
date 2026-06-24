"""Regression tests for blueprint-first render/output consumers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.io.serializer import (
    build_canonical_blueprint_payload,
    recover_legacy_render_payload_from_blueprint,
)
from src.render import ascii_renderer, image_renderer
from src.render import grid_visualizer
from src.render.report_builder import build_viewer_report_from_project_root
from src.render.serve import serve_viewer


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _sample_pools_payload() -> dict:
    return {
        "facility_pools": {
            "smelter": [
                {
                    "pose_id": "smelter_pose_0",
                    "anchor": {"x": 3, "y": 4},
                    "pose_params": {"orientation": 1, "port_mode": "left_right"},
                    "occupied_cells": [[3, 4], [4, 4]],
                    "input_port_cells": [{"x": 3, "y": 4, "dir": "W", "commodity": "ore"}],
                    "output_port_cells": [{"x": 4, "y": 4, "dir": "E", "commodity": "iron_plate"}],
                    "power_coverage_cells": None,
                }
            ],
            "power_pole": [
                {
                    "pose_id": "pole_pose_0",
                    "anchor": {"x": 0, "y": 0},
                    "pose_params": {"orientation": 0, "port_mode": "default"},
                    "occupied_cells": [[0, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": [[1, 0], [1, 1]],
                }
            ],
        }
    }


def _sample_blueprint_payload() -> dict:
    pools_payload = _sample_pools_payload()
    return build_canonical_blueprint_payload(
        placement_solution={
            "smelter_001": {
                "pose_idx": 0,
                "pose_id": "smelter_pose_0",
                "anchor": {"x": 3, "y": 4},
                "facility_type": "smelter",
            }
        },
        routing_solution=None,
        ghost_rect={"w": 5, "h": 4, "area": 20, "anchor_x": 8, "anchor_y": 9},
        solve_time_seconds=12.5,
        benders_iterations=3,
        facility_pools=pools_payload,
        export_timestamp="2026-03-23T00:00:00Z",
    )


def test_blueprint_recovery_uniquely_resolves_pose() -> None:
    legacy_payload = recover_legacy_render_payload_from_blueprint(
        blueprint_payload=_sample_blueprint_payload(),
        facility_pools=_sample_pools_payload(),
    )

    assert legacy_payload["placement_solution"]["smelter_001"]["pose_idx"] == 0
    assert legacy_payload["placement_solution"]["smelter_001"]["pose_id"] == "smelter_pose_0"
    assert legacy_payload["ghost_rect"]["anchor_x"] == 8
    assert legacy_payload["ghost_rect"]["anchor_y"] == 9
    assert legacy_payload["search_status"] == "UNKNOWN"


def test_blueprint_recovery_raises_on_missing_pose_match() -> None:
    blueprint_payload = _sample_blueprint_payload()
    broken_pools = _sample_pools_payload()
    broken_pools["facility_pools"]["smelter"][0]["pose_params"]["port_mode"] = "top_bottom"

    try:
        recover_legacy_render_payload_from_blueprint(
            blueprint_payload=blueprint_payload,
            facility_pools=broken_pools,
        )
    except ValueError as exc:
        assert "no pose match" in str(exc)
    else:
        raise AssertionError("expected missing pose match to raise ValueError")


def test_blueprint_recovery_raises_on_ambiguous_pose_match() -> None:
    blueprint_payload = _sample_blueprint_payload()
    ambiguous_pools = _sample_pools_payload()
    ambiguous_pools["facility_pools"]["smelter"].append(
        dict(ambiguous_pools["facility_pools"]["smelter"][0])
    )

    try:
        recover_legacy_render_payload_from_blueprint(
            blueprint_payload=blueprint_payload,
            facility_pools=ambiguous_pools,
        )
    except ValueError as exc:
        assert "ambiguous pose match" in str(exc)
    else:
        raise AssertionError("expected ambiguous pose match to raise ValueError")


def test_grid_visualizer_render_from_json_supports_blueprint_payload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    blueprint_path = tmp_path / "data" / "blueprints" / "optimal_blueprint.json"
    pools_path = tmp_path / "data" / "preprocessed" / "candidate_placements.json"
    _write_json(blueprint_path, _sample_blueprint_payload())
    _write_json(pools_path, _sample_pools_payload())

    captured = {}

    def fake_render(solution, pools, ghost_rect=None, ghost_pos=None, output_path=None, title=""):
        captured["solution"] = solution
        captured["pools"] = pools
        captured["ghost_rect"] = ghost_rect
        captured["ghost_pos"] = ghost_pos
        captured["output_path"] = output_path
        return output_path

    monkeypatch.setattr(grid_visualizer, "render_placement_heatmap", fake_render)

    output_path = tmp_path / "blueprint.png"
    result = grid_visualizer.render_from_json(blueprint_path, output_path=output_path)

    assert result == output_path
    assert captured["solution"]["smelter_001"]["pose_idx"] == 0
    assert "facility_pools" not in captured["pools"]
    assert captured["ghost_rect"]["w"] == 5
    assert captured["ghost_pos"] == (8, 9)


def test_grid_visualizer_render_from_json_supports_legacy_final_solution_payload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    final_solution_path = tmp_path / "data" / "solutions" / "final_solution.json"
    pools_path = tmp_path / "data" / "preprocessed" / "candidate_placements.json"
    _write_json(
        final_solution_path,
        {
            "ghost_rect": {"w": 5, "h": 4, "area": 20},
            "placement_solution": {
                "smelter_001": {
                    "pose_idx": 0,
                    "pose_id": "smelter_pose_0",
                    "anchor": {"x": 3, "y": 4},
                    "facility_type": "smelter",
                }
            },
            "search_status": "CERTIFIED",
            "search_stats": {},
        },
    )
    _write_json(pools_path, _sample_pools_payload())

    captured = {}

    def fake_render(solution, pools, ghost_rect=None, ghost_pos=None, output_path=None, title=""):
        captured["solution"] = solution
        captured["pools"] = pools
        captured["ghost_rect"] = ghost_rect
        captured["ghost_pos"] = ghost_pos
        return output_path

    monkeypatch.setattr(grid_visualizer, "render_placement_heatmap", fake_render)

    output_path = tmp_path / "legacy.png"
    result = grid_visualizer.render_from_json(final_solution_path, output_path=output_path)

    assert result == output_path
    assert captured["solution"]["smelter_001"]["pose_id"] == "smelter_pose_0"
    assert "facility_pools" not in captured["pools"]
    assert captured["ghost_pos"] is None


def test_serve_viewer_copies_blueprint_and_keeps_legacy_fallback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    viewer_dir = tmp_path / "viewer"
    viewer_dir.mkdir(parents=True, exist_ok=True)
    _write_json(project_root / "data" / "solutions" / "final_solution.json", {"legacy": True})
    _write_json(project_root / "data" / "blueprints" / "optimal_blueprint.json", {"blueprint": True})
    _write_json(project_root / "data" / "preprocessed" / "candidate_placements.json", _sample_pools_payload())

    opened_urls: list[str] = []

    class DummyServer:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def serve_forever(self) -> None:
            return None

    monkeypatch.setattr("src.render.serve.socketserver.TCPServer", DummyServer)
    monkeypatch.setattr("src.render.serve.webbrowser.open", lambda url: opened_urls.append(url))
    monkeypatch.setattr(
        "src.render.serve.evaluate_certified_delivery_surface",
        lambda **_kwargs: SimpleNamespace(
            publishable=True,
            blocked_reason=None,
            final_solution_payload={"snapshot": "final"},
            optimal_blueprint_payload={"snapshot": "blueprint"},
        ),
    )
    monkeypatch.setattr(
        "src.render.report_builder.evaluate_certified_delivery_surface",
        lambda **_kwargs: SimpleNamespace(
            publishable=True,
            blocked_reason=None,
            optimal_blueprint_payload={"snapshot": "blueprint"},
        ),
    )

    serve_viewer(port=9999, project_root=project_root, viewer_dir=viewer_dir)

    assert (viewer_dir / "final_solution.json").exists()
    assert (viewer_dir / "optimal_blueprint.json").exists()
    assert (viewer_dir / "candidate_placements.json").exists()
    assert json.loads((viewer_dir / "final_solution.json").read_text(encoding="utf-8")) == {
        "snapshot": "final"
    }
    assert json.loads((viewer_dir / "optimal_blueprint.json").read_text(encoding="utf-8")) == {
        "snapshot": "blueprint"
    }
    assert opened_urls == ["http://localhost:9999"]


def test_serve_viewer_removes_stale_report_when_report_generation_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    viewer_dir = tmp_path / "viewer"
    viewer_dir.mkdir(parents=True, exist_ok=True)
    _write_json(project_root / "data" / "preprocessed" / "candidate_placements.json", _sample_pools_payload())
    _write_json(viewer_dir / "viewer_report.json", {"stale": "viewer-report"})

    class DummyServer:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def serve_forever(self) -> None:
            return None

    monkeypatch.setattr("src.render.serve.socketserver.TCPServer", DummyServer)
    monkeypatch.setattr("src.render.serve.webbrowser.open", lambda _url: None)
    monkeypatch.setattr(
        "src.render.serve.evaluate_certified_delivery_surface",
        lambda **_kwargs: SimpleNamespace(
            publishable=True,
            blocked_reason=None,
            final_solution_payload={"snapshot": "final"},
            optimal_blueprint_payload={"snapshot": "blueprint"},
        ),
    )
    monkeypatch.setattr(
        "src.render.serve.build_viewer_report_from_project_root",
        lambda _project_root: (_ for _ in ()).throw(RuntimeError("report failed")),
    )

    serve_viewer(port=9999, project_root=project_root, viewer_dir=viewer_dir)

    assert json.loads((viewer_dir / "final_solution.json").read_text(encoding="utf-8")) == {
        "snapshot": "final"
    }
    assert json.loads((viewer_dir / "optimal_blueprint.json").read_text(encoding="utf-8")) == {
        "snapshot": "blueprint"
    }
    assert not (viewer_dir / "viewer_report.json").exists()


def test_serve_viewer_rejects_forged_canonical_outputs_and_removes_stale_viewer_copies(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    viewer_dir = tmp_path / "viewer"
    _write_json(project_root / "data" / "solutions" / "final_solution.json", {"search_status": "CERTIFIED"})
    _write_json(project_root / "data" / "blueprints" / "optimal_blueprint.json", {"schema": "forged"})
    _write_json(project_root / "data" / "preprocessed" / "candidate_placements.json", _sample_pools_payload())
    _write_json(viewer_dir / "final_solution.json", {"stale": "viewer-final"})
    _write_json(viewer_dir / "optimal_blueprint.json", {"stale": "viewer-blueprint"})
    _write_json(viewer_dir / "viewer_report.json", {"stale": "viewer-report"})

    with pytest.raises(RuntimeError, match=r"certified .* surface is not publishable"):
        serve_viewer(port=9999, project_root=project_root, viewer_dir=viewer_dir)

    assert not (viewer_dir / "final_solution.json").exists()
    assert not (viewer_dir / "optimal_blueprint.json").exists()
    assert not (viewer_dir / "viewer_report.json").exists()


def test_report_builder_rejects_forged_canonical_outputs_without_publishable_surface(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_json(project_root / "data" / "solutions" / "final_solution.json", {"search_status": "CERTIFIED"})
    _write_json(project_root / "data" / "blueprints" / "optimal_blueprint.json", _sample_blueprint_payload())
    _write_json(project_root / "data" / "preprocessed" / "candidate_placements.json", _sample_pools_payload())

    with pytest.raises(RuntimeError, match=r"certified .* surface is not publishable"):
        build_viewer_report_from_project_root(project_root)


def test_web_viewer_prefers_blueprint_with_legacy_fallback() -> None:
    html = (
        Path(__file__).resolve().parent.parent / "render" / "web_viewer" / "index.html"
    ).read_text(encoding="utf-8")

    assert "optimal_blueprint.json" in html
    assert "final_solution.json" in html
    assert "candidate_placements.json" in html
    assert "viewer_report.json" in html
    assert "release_viewer_manifest.json" in html
    assert "release-section" in html
    assert "downloads-section" in html
    assert "recoverLegacyDataFromBlueprint" in html
    assert "localStorage" in html
    assert "layer-routing-ground" in html
    assert "layer-active-ports" in html


def test_main_visualization_prefers_blueprint_with_legacy_fallback() -> None:
    source = (Path(__file__).resolve().parent.parent.parent / "main.py").read_text(encoding="utf-8")

    assert "optimal_blueprint.json" in source
    assert "final_solution.json" in source
    assert "recover_legacy_render_payload_from_blueprint" in source


def test_ascii_renderer_supports_legacy_payload(tmp_path: Path) -> None:
    final_solution_path = tmp_path / "data" / "solutions" / "final_solution.json"
    pools_path = tmp_path / "data" / "preprocessed" / "candidate_placements.json"
    _write_json(
        final_solution_path,
        {
            "ghost_rect": {"w": 5, "h": 4, "area": 20, "anchor_x": 8, "anchor_y": 9},
            "placement_solution": {
                "smelter_001": {
                    "pose_idx": 0,
                    "pose_id": "smelter_pose_0",
                    "anchor": {"x": 3, "y": 4},
                    "facility_type": "smelter",
                }
            },
            "search_status": "CERTIFIED",
            "search_stats": {},
        },
    )
    _write_json(pools_path, _sample_pools_payload())

    rendered = ascii_renderer.render_from_json(final_solution_path)

    assert "S" in rendered
    assert "#" in rendered
    assert "ghost_rect=5x4" in rendered


def test_ascii_renderer_supports_blueprint_payload(tmp_path: Path) -> None:
    blueprint_path = tmp_path / "data" / "blueprints" / "optimal_blueprint.json"
    pools_path = tmp_path / "data" / "preprocessed" / "candidate_placements.json"
    _write_json(blueprint_path, _sample_blueprint_payload())
    _write_json(pools_path, _sample_pools_payload())

    rendered = ascii_renderer.render_from_json(blueprint_path)

    assert "S" in rendered
    assert "ghost_rect=5x4" in rendered


def test_image_renderer_wraps_grid_visualizer(monkeypatch, tmp_path: Path) -> None:
    blueprint_path = tmp_path / "data" / "blueprints" / "optimal_blueprint.json"
    output_path = tmp_path / "wrapped.png"
    calls = {}

    def fake_render(json_path, output_path=None):
        calls["json_path"] = json_path
        calls["output_path"] = output_path
        return output_path

    monkeypatch.setattr(image_renderer, "render_heatmap_from_json", fake_render)

    result = image_renderer.render_from_json(blueprint_path, output_path=output_path)

    assert result == output_path
    assert calls["json_path"] == blueprint_path
    assert calls["output_path"] == output_path
