from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import preflight_gate
from src.search import exact_campaign as exact_campaign_module
from src.search.certified_artifact_contract import (
    LOCKED_EXACT_ARTIFACT_PATHS,
    LOCKED_EXACT_ARTIFACT_SHA256,
    LOCKED_EXACT_ARTIFACT_SIZE_BYTES,
    LockedExactArtifactContractError,
    certified_project_uses_locked_artifact_contract,
    locked_exact_artifact_contract_violation,
)
from src.search.exact_campaign import ExactCampaign
from src.search.outer_search import run_outer_search


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _write_weakened_exact_project(root: Path, *, locked: bool) -> None:
    if locked:
        (root / "PROJECT_LOCK.md").parent.mkdir(parents=True, exist_ok=True)
        (root / "PROJECT_LOCK.md").write_text("test lock marker\n", encoding="utf-8")
    _write_json(
        root / "rules" / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 70, "height": 70},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 6,
                },
            },
            "facility_templates": {},
        },
    )
    _write_json(root / "rules" / "preprocess_plan.json", {"utility_operations": {}})
    _write_json(root / "data" / "preprocessed" / "mandatory_exact_instances.json", [])
    _write_json(
        root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    _write_json(
        root / "data" / "preprocessed" / "candidate_placements.json",
        {"facility_pools": {}},
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_v102_locked_fresh_campaign_rejects_self_pinned_weakened_theorem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "locked_weakened_project"
    _write_weakened_exact_project(root, locked=True)
    monkeypatch.setattr(
        exact_campaign_module,
        "validate_locked_p1_2_close_kernel",
        lambda _project_root: None,
    )

    with pytest.raises(
        LockedExactArtifactContractError,
        match="locked_exact_artifact_hash_mismatch:mandatory_exact_instances",
    ):
        run_outer_search(
            project_root=root,
            solve_mode="certified_exact",
            campaign_hours=0.01,
            master_seconds=1.0,
            binding_seconds=1.0,
            routing_seconds=1.0,
            flow_seconds=1.0,
            benders_max_iter=1,
            max_attempts=1,
            min_side=6,
        )

    for relative_path in (
        "data/checkpoints/exact_campaign_state.json",
        "data/solutions/final_solution.json",
        "data/solutions/certified_delivery_manifest.json",
        "data/blueprints/optimal_blueprint.json",
    ):
        assert not (root / relative_path).exists()


@pytest.mark.parametrize("artifact_key", sorted(LOCKED_EXACT_ARTIFACT_SHA256))
def test_v102_locked_contract_rejects_every_frozen_hash_drift(
    tmp_path: Path,
    artifact_key: str,
) -> None:
    root = tmp_path / "locked_hash_drift"
    (root / "PROJECT_LOCK.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "PROJECT_LOCK.md").write_text("test lock marker\n", encoding="utf-8")
    hashes = dict(LOCKED_EXACT_ARTIFACT_SHA256)
    hashes[artifact_key] = "0" * 64

    assert locked_exact_artifact_contract_violation(
        project_root=root,
        artifact_hashes=hashes,
        artifact_sizes=LOCKED_EXACT_ARTIFACT_SIZE_BYTES,
    ) == f"locked_exact_artifact_hash_mismatch:{artifact_key}"


def test_v102_locked_contract_rejects_candidate_size_drift(tmp_path: Path) -> None:
    root = tmp_path / "locked_size_drift"
    (root / "PROJECT_LOCK.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "PROJECT_LOCK.md").write_text("test lock marker\n", encoding="utf-8")

    assert locked_exact_artifact_contract_violation(
        project_root=root,
        artifact_hashes=LOCKED_EXACT_ARTIFACT_SHA256,
        artifact_sizes={"candidate_placements": 1},
    ) == "locked_exact_artifact_size_mismatch:candidate_placements"


def test_v102_unlocked_toy_campaign_still_supports_model_regressions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "unlocked_toy_project"
    _write_weakened_exact_project(root, locked=False)
    monkeypatch.setattr(
        exact_campaign_module,
        "compute_certified_exact_source_digest",
        lambda: "test-source-digest",
    )

    campaign = ExactCampaign.load_or_create(root, campaign_hours=1.0, resume=False)

    assert campaign.state["solve_mode"] == "certified_exact"
    assert campaign.state["artifact_hashes"]["mandatory_exact_instances"] != (
        LOCKED_EXACT_ARTIFACT_SHA256["mandatory_exact_instances"]
    )


def test_v102_source_checkout_is_locked_without_relying_only_on_marker() -> None:
    source_root = Path(exact_campaign_module.__file__).resolve().parents[2]

    assert certified_project_uses_locked_artifact_contract(source_root)


def test_v102_runtime_frozen_hashes_match_preflight_contract() -> None:
    preflight_hashes = {
        "canonical_rules": preflight_gate.FROZEN_ARTIFACTS[
            LOCKED_EXACT_ARTIFACT_PATHS["canonical_rules"]
        ].lower(),
        "preprocess_plan": preflight_gate.FROZEN_ARTIFACTS[
            LOCKED_EXACT_ARTIFACT_PATHS["preprocess_plan"]
        ].lower(),
        "mandatory_exact_instances": preflight_gate.FROZEN_ARTIFACTS[
            LOCKED_EXACT_ARTIFACT_PATHS["mandatory_exact_instances"]
        ].lower(),
        "generic_io_requirements": preflight_gate.FROZEN_ARTIFACTS[
            LOCKED_EXACT_ARTIFACT_PATHS["generic_io_requirements"]
        ].lower(),
        "candidate_placements": preflight_gate.EXTERNAL_FROZEN_ARTIFACTS[
            LOCKED_EXACT_ARTIFACT_PATHS["candidate_placements"]
        ]["sha256"].lower(),
    }
    preflight_sizes = {
        "candidate_placements": preflight_gate.EXTERNAL_FROZEN_ARTIFACTS[
            LOCKED_EXACT_ARTIFACT_PATHS["candidate_placements"]
        ]["size_bytes"]
    }

    assert preflight_hashes == LOCKED_EXACT_ARTIFACT_SHA256
    assert preflight_sizes == LOCKED_EXACT_ARTIFACT_SIZE_BYTES


def test_v102_checked_in_frozen_inputs_match_runtime_contract() -> None:
    source_root = Path(exact_campaign_module.__file__).resolve().parents[2]

    for key, expected_hash in LOCKED_EXACT_ARTIFACT_SHA256.items():
        path = source_root / LOCKED_EXACT_ARTIFACT_PATHS[key]
        assert _sha256(path) == expected_hash
    for key, expected_size in LOCKED_EXACT_ARTIFACT_SIZE_BYTES.items():
        path = source_root / LOCKED_EXACT_ARTIFACT_PATHS[key]
        assert path.stat().st_size == expected_size


def test_v102_runtime_contract_module_is_source_digest_bound() -> None:
    assert (
        "src/search/certified_artifact_contract.py"
        in exact_campaign_module.CERTIFIED_EXACT_SOURCE_HASH_FILES
    )
