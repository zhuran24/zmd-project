"""Public viewer compatibility assets must not mint exact certification."""

from __future__ import annotations

import json
from pathlib import Path

from src.render.industrial_planner_single_base_delivery_viewer import (
    build_single_base_delivery_viewer_bundle,
)


def test_public_viewer_legacy_payload_is_non_proof_bearing(tmp_path: Path) -> None:
    output_dir = tmp_path / "viewer"

    result = build_single_base_delivery_viewer_bundle(
        project_root=Path("."),
        output_dir=output_dir,
    )

    legacy_payload = json.loads((output_dir / "final_solution.json").read_text(encoding="utf-8"))
    viewer_manifest = json.loads(
        (output_dir / "release_viewer_manifest.json").read_text(encoding="utf-8")
    )

    assert result.exact_full_scale_certified_status == "open"
    assert viewer_manifest["exact_full_scale_certified"]["status"] == "open"
    assert viewer_manifest["viewer_bundle"]["asset_paths"]["final_solution"] == "final_solution.json"
    assert legacy_payload["search_status"] == "UNKNOWN"
    assert legacy_payload["search_stats"]["output_contract_source"] == "optimal_blueprint.json"
