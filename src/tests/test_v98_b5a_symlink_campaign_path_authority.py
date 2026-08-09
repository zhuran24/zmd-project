from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.search.phase3b.b5a.b5_anchor_sprint import build_phase3b_b5_anchor_sprint_summary
from src.tests.certified_surface_fixtures import (
    ClonedCertifiedSurface,
    clone_surface_tree,  # noqa: F401 - imported fixture for pytest discovery.
    golden_publishable_surface,  # noqa: F401 - imported fixture dependency.
)


def test_v98_b5a_preserves_symlink_campaign_path_until_surface_verifier(
    tmp_path: Path,
    clone_surface_tree: Callable[[Path], ClonedCertifiedSurface],  # noqa: F811 - fixture shadows its import.
) -> None:
    surface = clone_surface_tree(tmp_path / "b5a_symlink_alias")
    project_root = surface.project_root
    alias_path = project_root / "data" / "checkpoints" / "alias_exact_campaign_state.json"
    alias_path.symlink_to(surface.campaign_path.name)

    summary = build_phase3b_b5_anchor_sprint_summary(
        project_root,
        campaign_state_path=alias_path,
    )

    assert summary["status"]["certified_surface_public"] is False
    assert summary["status"]["certified_surface_publishable"] is False
    assert summary["status"]["certified_surface_blocked_reason"] == "campaign_state_not_regular_file"
    assert summary["status"]["anchor_found"] is False
    assert summary["anchor"] is None
