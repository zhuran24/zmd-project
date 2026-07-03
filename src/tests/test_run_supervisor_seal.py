"""Tests for the PR2 #7 production supervisor certify entrypoint
(scripts/run_supervisor_seal.py).

The entrypoint is a thin wiring layer: resume an already-committed
CANDIDATE_PROPOSED proposal and drive it through ExactCampaign.supervisor_seal()
(the real isolated L0 path). These tests exercise the *wiring* — a committed
proposal seals to a durable campaign CERTIFIED, the entrypoint never itself
publishes a delivery surface, an already-sealed campaign is not re-sealable, and
missing preconditions fail closed — not the L0 seal semantics (covered by
test_p1_2_supervisor_pr1 / test_pr2_l0_*).

Real seals here need the host's dependency floor (the repo-pinned floor manifest
is a deploy-pending placeholder that won't match this machine's stdlib/deps), so
sealing tests patch it exactly like test_p1_2_supervisor_pr1's autouse fixture.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.models.cut_manager import RUN_STATUS_CERTIFIED
from src.search import pr2_l0_micro_verifier_core as l0_module
from src.search.exact_campaign import (
    CANDIDATE_PROPOSED_STATUS,
    ExactCampaign,
    proposal_ready_marker_path_for_campaign,
)
from src.tests.test_exact_contract import _build_toy_exact_project
from src.tests.test_p1_2_supervisor_pr1 import _run_toy_candidate_proposal
from scripts import run_supervisor_seal
from scripts.generate_pr2_dependency_floor_manifest import build_manifest


@pytest.fixture(scope="session")
def _host_floor_bytes() -> tuple[bytes, int, str]:
    raw = (
        json.dumps(build_manifest(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    return raw, len(raw), hashlib.sha256(raw).hexdigest()


@pytest.fixture
def _host_floor_patched(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    _host_floor_bytes: tuple[bytes, int, str],
) -> None:
    raw, size_bytes, sha256 = _host_floor_bytes
    manifest_path = tmp_path / "host_floor_manifest.json"
    manifest_path.write_bytes(raw)
    monkeypatch.setattr(l0_module, "DEPENDENCY_FLOOR_MANIFEST_REL", str(manifest_path))
    monkeypatch.setattr(l0_module, "DEPENDENCY_FLOOR_MANIFEST_SIZE_BYTES", size_bytes)
    monkeypatch.setattr(l0_module, "DEPENDENCY_FLOOR_MANIFEST_SHA256", sha256)


def _campaign_checkpoint(project_root: Path) -> Path:
    return project_root / "data" / "checkpoints" / "exact_campaign_state.json"


def test_seals_proposal_and_second_run_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _host_floor_patched: None
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "seal_ok")
    _run_toy_candidate_proposal(project_root)

    pre = ExactCampaign.load_or_create(project_root, resume=True)
    assert pre.state["final_status"] == CANDIDATE_PROPOSED_STATUS

    # 通电≠发布: spy the central publisher so we assert the entrypoint itself never
    # publishes a delivery surface during the seal (file existence is a poor proxy —
    # the proposal stage legitimately writes a delivery manifest as evidence material).
    import src.search.certified_surface as certified_surface_module

    publish_calls: list[tuple] = []
    real_publish = certified_surface_module.publish_verified_certified_delivery_surface
    monkeypatch.setattr(
        certified_surface_module,
        "publish_verified_certified_delivery_surface",
        lambda *a, **k: publish_calls.append((a, k)) or real_publish(*a, **k),
    )

    assert run_supervisor_seal.main(["--project-root", str(project_root)]) == 0
    assert publish_calls == []  # the seal entrypoint must not publish

    sealed = ExactCampaign.load_or_create(project_root, resume=True)
    assert sealed.state["final_status"] == RUN_STATUS_CERTIFIED
    assert sealed.state["final_result"]["search_status"] == RUN_STATUS_CERTIFIED
    assert "supervisor_seal" in sealed.state
    # marker consumed on a successful seal
    assert not proposal_ready_marker_path_for_campaign(
        _campaign_checkpoint(project_root)
    ).exists()

    # already sealed → second run finds no CANDIDATE_PROPOSED proposal, fails closed
    assert run_supervisor_seal.main(["--project-root", str(project_root)]) == 2


def test_missing_checkpoint_fails_closed(tmp_path: Path) -> None:
    assert run_supervisor_seal.main(["--project-root", str(tmp_path)]) == 2


def test_missing_marker_fails_closed(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "no_marker")
    _run_toy_candidate_proposal(project_root)
    proposal_ready_marker_path_for_campaign(_campaign_checkpoint(project_root)).unlink()

    assert run_supervisor_seal.main(["--project-root", str(project_root)]) == 2
    # main returns before any resume, so the on-disk proposal is untouched — still
    # CANDIDATE_PROPOSED, never forged to CERTIFIED. (Read disk directly: a
    # resume() here would itself demote the marker-less proposal.)
    disk = json.loads(
        _campaign_checkpoint(project_root).read_text(encoding="utf-8")
    )
    assert disk["final_status"] == CANDIDATE_PROPOSED_STATUS
