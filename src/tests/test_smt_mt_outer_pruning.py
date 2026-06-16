"""Tests for SMT-MT outer pruning Phase 1 engine + outer_search integration.

Covers:
- Env-gate semantics (truthy/falsy variants).
- OuterPruningEngine.build correctness (R-tree size + key mapping).
- notify_infeasible propagates to all (w', h') with w' >= w AND h' >= h.
- Geometric invariant: ghost_A subset ghost_B + ghost_A INFEASIBLE => ghost_B pruned.
- Module-level helpers no-op when engine is None.
- outer_search hook: env off => engine is None, env on => engine constructed.
- Telemetry write produces JSON snapshot with expected fields.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import pytest

from src.search import smt_mt_outer_pruning as smtmt


def _sample_candidates() -> List[Tuple[int, int, int]]:
    """Tiny set of (area, w, h) triples covering containment scenarios."""
    return [
        (36, 6, 6),
        (42, 7, 6),
        (49, 7, 7),
        (60, 10, 6),
        (100, 10, 10),
        (150, 15, 10),
        (400, 20, 20),
        (900, 30, 30),
    ]


class TestEnvGate:
    def test_env_off_default(self, monkeypatch):
        monkeypatch.delenv(smtmt.ENV_SMT_MT_OUTER_PRUNING, raising=False)
        assert smtmt.is_enabled() is False

    def test_env_truthy_variants(self, monkeypatch):
        for value in ("1", "true", "TRUE", "Yes", "on", " 1 "):
            monkeypatch.setenv(smtmt.ENV_SMT_MT_OUTER_PRUNING, value)
            assert smtmt.is_enabled() is True, f"value={value!r}"

    def test_env_falsy_variants(self, monkeypatch):
        for value in ("", "0", "false", "no", "off", "random"):
            monkeypatch.setenv(smtmt.ENV_SMT_MT_OUTER_PRUNING, value)
            assert smtmt.is_enabled() is False, f"value={value!r}"


class TestCandidateKey:
    def test_candidate_key_format(self):
        assert smtmt.candidate_key(6, 6) == "6x6"
        assert smtmt.candidate_key(70, 70) == "70x70"
        assert smtmt.candidate_key(15, 10) == "15x10"


class TestEngineBuild:
    def test_build_populates_metrics(self):
        engine = smtmt.OuterPruningEngine.build(_sample_candidates())
        snapshot = engine.metrics_snapshot()
        assert snapshot["candidate_count"] == len(_sample_candidates())
        assert snapshot["paradigm"] == "smt_mt_outer_pruning"
        assert snapshot["phase"] == "phase1"
        assert snapshot["infeasible_notifications"] == 0
        assert snapshot["total_pruned_unique"] == 0
        assert snapshot["real_prune_ratio"] == 0.0
        assert snapshot["rtree_build_seconds"] >= 0.0

    def test_build_empty_candidates(self):
        engine = smtmt.OuterPruningEngine.build([])
        assert engine.metrics_snapshot()["candidate_count"] == 0
        assert engine.pruned_candidate_keys() == set()


class TestMonotonePropagation:
    def test_notify_propagates_supersets(self):
        engine = smtmt.OuterPruningEngine.build(_sample_candidates())
        # ghost (10, 10) is INFEASIBLE => (15, 10), (20, 20), (30, 30) all pruned.
        # Also (10, 10) itself is in the upper set (>= containment).
        newly = engine.notify_infeasible(10, 10)
        keys = set(newly)
        assert "10x10" in keys
        assert "15x10" in keys
        assert "20x20" in keys
        assert "30x30" in keys
        # NOT pruned: smaller candidates
        assert "6x6" not in keys
        assert "7x6" not in keys
        assert "7x7" not in keys
        assert "10x6" not in keys

    def test_geometric_invariant_subset_implies_pruned(self):
        """ghost_A subset ghost_B + ghost_A INFEASIBLE => ghost_B pruned."""
        engine = smtmt.OuterPruningEngine.build(_sample_candidates())
        # ghost_A = (7, 6), ghost_B = (20, 20) — clearly subset
        engine.notify_infeasible(7, 6)
        assert engine.is_pruned(20, 20)
        assert engine.is_pruned(15, 10)
        assert engine.is_pruned(10, 10)
        # Self-pruned
        assert engine.is_pruned(7, 6)
        # Not pruned: incomparable (6, 6) — h is same but w smaller
        assert not engine.is_pruned(6, 6)

    def test_idempotent_notify(self):
        engine = smtmt.OuterPruningEngine.build(_sample_candidates())
        first = engine.notify_infeasible(10, 10)
        second = engine.notify_infeasible(10, 10)
        # Second notify finds the upper set already pruned — newly_pruned == []
        assert len(first) >= 4
        assert second == []
        # But the metrics record both notifications
        snapshot = engine.metrics_snapshot()
        assert snapshot["infeasible_notifications"] == 2
        assert snapshot["monotone_query_count"] == 2

    def test_cumulative_pruning_count(self):
        engine = smtmt.OuterPruningEngine.build(_sample_candidates())
        engine.notify_infeasible(20, 20)  # prunes 20x20, 30x30
        engine.notify_infeasible(10, 10)  # prunes 10x10, 15x10 (20x20+30x30 already)
        snapshot = engine.metrics_snapshot()
        # 4 unique candidates pruned: 10x10, 15x10, 20x20, 30x30
        assert snapshot["total_pruned_unique"] == 4

    def test_no_propagation_when_no_superset(self):
        engine = smtmt.OuterPruningEngine.build(_sample_candidates())
        # Mark the largest (30, 30) — only itself pruned.
        newly = engine.notify_infeasible(30, 30)
        assert newly == ["30x30"]


class TestModuleHelpers:
    def test_maybe_build_returns_none_when_env_off(self, monkeypatch):
        monkeypatch.delenv(smtmt.ENV_SMT_MT_OUTER_PRUNING, raising=False)
        engine = smtmt.maybe_build_engine(_sample_candidates())
        assert engine is None

    def test_maybe_build_returns_engine_when_env_on(self, monkeypatch):
        monkeypatch.setenv(smtmt.ENV_SMT_MT_OUTER_PRUNING, "1")
        engine = smtmt.maybe_build_engine(_sample_candidates())
        assert engine is not None
        assert isinstance(engine, smtmt.OuterPruningEngine)

    def test_maybe_notify_with_none_engine_returns_empty(self):
        result = smtmt.maybe_notify_infeasible(None, 10, 10)
        assert result == []

    def test_maybe_write_telemetry_with_none_engine_returns_none(self, tmp_path):
        result = smtmt.maybe_write_telemetry(None, tmp_path, wave_index=1)
        assert result is None


class TestTelemetryWrite:
    def test_write_telemetry_produces_json(self, tmp_path):
        engine = smtmt.OuterPruningEngine.build(_sample_candidates())
        engine.notify_infeasible(10, 10)
        output_path = tmp_path / "smt_mt_metrics.json"
        result_path = engine.write_telemetry(output_path)
        assert result_path == output_path
        assert output_path.exists()
        loaded = json.loads(output_path.read_text())
        assert loaded["paradigm"] == "smt_mt_outer_pruning"
        assert loaded["candidate_count"] == len(_sample_candidates())
        assert loaded["infeasible_notifications"] == 1
        assert loaded["total_pruned_unique"] >= 1
        assert "monotone_query_p95_ms" in loaded

    def test_maybe_write_telemetry_path_format(self, monkeypatch, tmp_path):
        monkeypatch.setenv(smtmt.ENV_SMT_MT_OUTER_PRUNING, "1")
        engine = smtmt.maybe_build_engine(_sample_candidates())
        assert engine is not None
        engine.notify_infeasible(10, 10)
        result = smtmt.maybe_write_telemetry(engine, tmp_path, wave_index=7)
        assert result is not None
        assert result.name == "phase1_metrics_wave_0007.json"
        assert result.parent.name == "smt_mt_outer_pruning"


class TestOuterSearchIntegrationSurface:
    """Verify the engine import + helper surface used by outer_search.py.

    We don't run a full outer_search invocation here (that requires the
    project data + venv ortools + minutes of solve time). Instead we
    verify:
    - the imports outer_search.py uses are exported
    - env-off behavior: outer_search.py constructs engine as None
    """

    def test_outer_search_imports_present(self):
        from src.search.outer_search import (
            OuterPruningEngine,
            maybe_build_engine,
            maybe_notify_infeasible,
            maybe_write_telemetry,
        )
        # Symbol identity sanity check
        assert OuterPruningEngine is smtmt.OuterPruningEngine
        assert maybe_build_engine is smtmt.maybe_build_engine
        assert maybe_notify_infeasible is smtmt.maybe_notify_infeasible
        assert maybe_write_telemetry is smtmt.maybe_write_telemetry

    def test_env_off_engine_none(self, monkeypatch):
        monkeypatch.delenv(smtmt.ENV_SMT_MT_OUTER_PRUNING, raising=False)
        # Simulate the outer_search build site
        engine = smtmt.maybe_build_engine(_sample_candidates())
        assert engine is None
        # All notify calls are no-ops
        assert smtmt.maybe_notify_infeasible(engine, 30, 30) == []


class TestDirectlyInfeasibleSet:
    def test_directly_infeasible_tracked_separately(self):
        engine = smtmt.OuterPruningEngine.build(_sample_candidates())
        engine.notify_infeasible(10, 10)
        engine.notify_infeasible(7, 7)
        direct = engine.directly_infeasible_keys()
        assert "10x10" in direct
        assert "7x7" in direct
        # 15x10 is pruned via propagation but not directly notified
        assert "15x10" not in direct
        assert engine.is_pruned(15, 10)
