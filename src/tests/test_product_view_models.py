"""Tests for viewer-side report building and product view models."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from src.io.serializer import build_canonical_blueprint_payload
from src.render.report_builder import build_viewer_report_from_blueprint_payload
from src.render.serve import serve_viewer


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _sample_pools_payload() -> dict:
    return {
        "facility_pools": {
            "manufacturing_3x3": [
                {
                    "pose_id": "mfg_pose_0",
                    "anchor": {"x": 2, "y": 2},
                    "pose_params": {"orientation": 0, "port_mode": "left_right"},
                    "occupied_cells": [[2, 2], [3, 2], [4, 2], [2, 3], [3, 3], [4, 3], [2, 4], [3, 4], [4, 4]],
                    "input_port_cells": [{"x": 1, "y": 3, "dir": "W", "commodity": "raw_ore"}],
                    "output_port_cells": [{"x": 5, "y": 3, "dir": "E", "commodity": "iron_plate"}],
                    "power_coverage_cells": None,
                }
            ],
            "power_pole": [
                {
                    "pose_id": "pole_pose_0",
                    "anchor": {"x": 0, "y": 0},
                    "pose_params": {"orientation": 0, "port_mode": "omni"},
                    "occupied_cells": [[0, 0], [0, 1], [1, 0], [1, 1]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": [[0, 0], [0, 1], [1, 0], [1, 1]],
                }
            ],
        }
    }


def _sample_blueprint_payload() -> dict:
    pools = _sample_pools_payload()
    return build_canonical_blueprint_payload(
        placement_solution={
            "mfg_001": {
                "pose_idx": 0,
                "pose_id": "mfg_pose_0",
                "anchor": {"x": 2, "y": 2},
                "facility_type": "manufacturing_3x3",
            },
            "power_pole_001": {
                "pose_idx": 0,
                "pose_id": "pole_pose_0",
                "anchor": {"x": 0, "y": 0},
                "facility_type": "power_pole",
            },
        },
        routing_solution=[
            {"x": 5, "y": 3, "layer": 0, "component_type": "belt", "commodity": "iron_plate", "flow_in": ["W"], "flow_out": ["E"]},
            {"x": 6, "y": 3, "layer": 1, "component_type": "bridge", "commodity": "iron_plate", "flow_in": ["W"], "flow_out": ["E"]},
        ],
        ghost_rect={"w": 6, "h": 5, "area": 30, "anchor_x": 10, "anchor_y": 11},
        solve_time_seconds=7.5,
        benders_iterations=2,
        facility_pools=pools,
        export_timestamp="2026-03-25T00:00:00Z",
    )


def test_viewer_report_builds_cards_warnings_and_defaults() -> None:
    blueprint = _sample_blueprint_payload()
    pools = _sample_pools_payload()
    rules_payload = json.loads(Path("rules/canonical_rules.json").read_text(encoding="utf-8"))

    report = build_viewer_report_from_blueprint_payload(
        blueprint_payload=blueprint,
        facility_pools=pools,
        rules_payload=rules_payload,
        generated_at="2026-03-25T00:00:00Z",
    )

    assert report["metadata"]["version"] == "0.1.0"
    assert len(report["cards"]) == 5
    assert report["summary"]["routing"]["total_cells"] == 2
    assert report["summary"]["ports"]["total_active_ports"] == 2
    assert report["viewer_defaults"]["layers"]["routingGround"] is True


def test_serve_viewer_generates_viewer_report_when_blueprint_is_valid(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    viewer_dir = tmp_path / "viewer"
    viewer_dir.mkdir(parents=True, exist_ok=True)
    _write_json(project_root / "data" / "solutions" / "final_solution.json", {"legacy": True})
    _write_json(project_root / "data" / "blueprints" / "optimal_blueprint.json", _sample_blueprint_payload())
    _write_json(project_root / "data" / "preprocessed" / "candidate_placements.json", _sample_pools_payload())
    _write_json(project_root / "rules" / "canonical_rules.json", json.loads(Path("rules/canonical_rules.json").read_text(encoding="utf-8")))

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
            final_solution_payload={"legacy": True},
            optimal_blueprint_payload=_sample_blueprint_payload(),
        ),
    )
    monkeypatch.setattr(
        "src.render.report_builder.evaluate_certified_delivery_surface",
        lambda **_kwargs: SimpleNamespace(
            publishable=True,
            blocked_reason=None,
            optimal_blueprint_payload=_sample_blueprint_payload(),
        ),
    )

    serve_viewer(port=9998, project_root=project_root, viewer_dir=viewer_dir)

    assert (viewer_dir / "viewer_report.json").exists()
    viewer_report = json.loads((viewer_dir / "viewer_report.json").read_text(encoding="utf-8"))
    assert viewer_report["summary"]["routing"]["total_cells"] == 2
    assert opened_urls == ["http://localhost:9998"]
