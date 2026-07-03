from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from typing import Any

import pytest

from src.io.delivery_manifest import delivery_manifest_output_path
from src.search.certified_surface import verify_certified_delivery_surface
from src.tests.test_p1_2_open_gate_publish_block import _build_publishable_surface


@dataclass(frozen=True)
class GoldenPublishableSurface:
    project_root: Path
    campaign_path: Path
    campaign_state: dict[str, Any]
    manifest_payload: dict[str, Any]


@dataclass(frozen=True)
class ClonedCertifiedSurface:
    project_root: Path
    campaign_path: Path
    campaign_state: dict[str, Any]
    manifest_payload: dict[str, Any]


@pytest.fixture(scope="session")
def golden_publishable_surface(
    tmp_path_factory: pytest.TempPathFactory,
) -> GoldenPublishableSurface:
    root = tmp_path_factory.mktemp("golden_publishable_surface")
    project_root, campaign, manifest = _build_publishable_surface(root)
    manifest_payload = dict(manifest or {})
    verdict = verify_certified_delivery_surface(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
        delivery_manifest=manifest_payload,
    )
    assert verdict.publishable, verdict.as_summary()
    return GoldenPublishableSurface(
        project_root=project_root,
        campaign_path=campaign.path,
        campaign_state=dict(campaign.state),
        manifest_payload=manifest_payload,
    )


@pytest.fixture
def clone_surface_tree(
    golden_publishable_surface: GoldenPublishableSurface,
) -> Callable[[Path], ClonedCertifiedSurface]:
    def clone(target_tmp: Path) -> ClonedCertifiedSurface:
        return _clone_surface_tree(golden_publishable_surface, target_tmp)

    return clone


def _clone_surface_tree(
    golden: GoldenPublishableSurface,
    target_tmp: Path,
) -> ClonedCertifiedSurface:
    target_root = Path(target_tmp)
    if target_root.exists() or target_root.is_symlink():
        if target_root.is_dir() and not target_root.is_symlink():
            shutil.rmtree(target_root)
        else:
            target_root.unlink()
    target_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(golden.project_root, target_root, symlinks=True)
    campaign_path = target_root / golden.campaign_path.relative_to(golden.project_root)
    campaign_state = json.loads(campaign_path.read_text(encoding="utf-8"))
    manifest_payload = json.loads(
        delivery_manifest_output_path(target_root).read_text(encoding="utf-8")
    )
    return ClonedCertifiedSurface(
        project_root=target_root,
        campaign_path=campaign_path,
        campaign_state=campaign_state,
        manifest_payload=manifest_payload,
    )
