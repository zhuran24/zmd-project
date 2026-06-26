from __future__ import annotations

from pathlib import Path

from src.search.phase3b.b5a.b5_anchor_sprint import build_phase3b_b5_anchor_sprint_summary
from src.tests.test_p1_2_open_gate_publish_block import _build_publishable_surface


def test_v98_b5a_preserves_symlink_campaign_path_until_surface_verifier(
    tmp_path: Path,
) -> None:
    project_root, campaign, _manifest = _build_publishable_surface(
        tmp_path / "b5a_symlink_alias"
    )
    alias_path = project_root / "data" / "checkpoints" / "alias_exact_campaign_state.json"
    alias_path.symlink_to(campaign.path.name)

    summary = build_phase3b_b5_anchor_sprint_summary(
        project_root,
        campaign_state_path=alias_path,
    )

    assert summary["status"]["certified_surface_public"] is False
    assert summary["status"]["certified_surface_publishable"] is False
    assert summary["status"]["certified_surface_blocked_reason"] == "campaign_state_not_regular_file"
    assert summary["status"]["anchor_found"] is False
    assert summary["anchor"] is None
