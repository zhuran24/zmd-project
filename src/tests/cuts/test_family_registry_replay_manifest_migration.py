"""Replay is hard-coded production behavior; the manifest is an external gate."""

from __future__ import annotations

import ast
from pathlib import Path

from src.cuts.replay import LEGACY_DIAGNOSTIC_VALIDATORS, TYPED_REPLAY_FAMILIES
from src.tests.cuts.rule_cut_evolution.family_specs import (
    SHADOW_FAMILY_SPECS_V1,
    ReplayKind,
)


REPLAY_PATH = Path(__file__).resolve().parents[3] / "src/cuts/replay.py"


def test_hardcoded_typed_and_legacy_replay_sets_match_shadow_rows() -> None:
    expected_typed = {
        family
        for family, row in SHADOW_FAMILY_SPECS_V1.trust_specs.items()
        if row.replay.value is not None
        and row.replay.value.kind is ReplayKind.TYPED_SINGLE_ENTRY
    }
    expected_legacy = {
        family
        for family, row in SHADOW_FAMILY_SPECS_V1.trust_specs.items()
        if row.replay.value is not None
        and row.replay.value.kind is ReplayKind.LEGACY_DIAGNOSTIC
    }
    assert TYPED_REPLAY_FAMILIES == frozenset(expected_typed)
    assert frozenset(LEGACY_DIAGNOSTIC_VALIDATORS) == frozenset(expected_legacy)
    assert expected_typed.isdisjoint(expected_legacy)


def test_legacy_validator_identities_match_shadow_replay_identities() -> None:
    for family, validator in LEGACY_DIAGNOSTIC_VALIDATORS.items():
        replay = SHADOW_FAMILY_SPECS_V1.trust(family).replay.value
        assert replay is not None
        assert (validator.__module__, validator.__qualname__) == (
            replay.entrypoint.module,
            replay.entrypoint.qualname,
        )


def test_replay_has_no_shadow_or_manifest_import() -> None:
    tree = ast.parse(REPLAY_PATH.read_text(encoding="utf-8"), filename=str(REPLAY_PATH))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "src.cuts.family_specs" not in imported
    assert all(not module.startswith("src.tests.") for module in imported)
