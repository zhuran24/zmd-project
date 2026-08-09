"""Tests for P1 #7 main — LBBDController.set_epsilon_stage tags new cuts."""

from __future__ import annotations

import pytest

from src.models.cut_manager import BendersCut


def test_set_epsilon_stage_none(monkeypatch):
    """set_epsilon_stage(None) → controller.epsilon_stage = None."""
    from src.search.benders_loop import LBBDController
    obj = type("Stub", (), {})()
    LBBDController.set_epsilon_stage(obj, None)
    assert obj.epsilon_stage is None


def test_set_epsilon_stage_float():
    from src.search.benders_loop import LBBDController
    obj = type("Stub", (), {})()
    LBBDController.set_epsilon_stage(obj, 0.05)
    assert obj.epsilon_stage == 0.05


def test_set_epsilon_stage_int_coerces_to_float():
    from src.search.benders_loop import LBBDController
    obj = type("Stub", (), {})()
    LBBDController.set_epsilon_stage(obj, 0)
    assert obj.epsilon_stage == 0.0
    assert isinstance(obj.epsilon_stage, float)


def test_persisted_nogood_tags_epsilon_stage():
    """_add_exact_persisted_nogood 构造的 BendersCut 应继承 self.epsilon_stage."""
    from src.search.benders_loop import LBBDController

    captured = []

    class FakeCutManager:
        def has_structured_cut(self, cut):
            return False

        def register_structured_cut(self, cut):
            captured.append(cut)
            return True

    class FakeMaster:
        def add_benders_cut(self, conflict_set, *, condition_lits=()):
            return True

    obj = type("Stub", (), {})()
    obj.cut_manager = FakeCutManager()
    obj.master = FakeMaster()
    obj.artifact_hashes = {}
    obj.generated_exact_safe_cuts = []
    obj.epsilon_stage = 0.01

    LBBDController._add_exact_persisted_nogood(
        obj,
        conflict_set={"inst_a": 0, "inst_b": 1},
        iteration=1,
        cut_type="binding_pose_domain_empty_nogood",
        proof_stage="binding",
        proof_summary={},
    )

    assert len(captured) == 1
    cut = captured[0]
    assert cut.epsilon_stage == 0.01
    # roundtrip survives serialization
    payload = cut.to_dict()
    assert payload["epsilon_stage"] == 0.01


def test_persisted_nogood_no_epsilon_stage_when_unset():
    from src.search.benders_loop import LBBDController

    captured = []

    class FakeCutManager:
        def has_structured_cut(self, cut):
            return False

        def register_structured_cut(self, cut):
            captured.append(cut)
            return True

    class FakeMaster:
        def add_benders_cut(self, conflict_set, *, condition_lits=()):
            return True

    obj = type("Stub", (), {})()
    obj.cut_manager = FakeCutManager()
    obj.master = FakeMaster()
    obj.artifact_hashes = {}
    obj.generated_exact_safe_cuts = []
    obj.epsilon_stage = None

    LBBDController._add_exact_persisted_nogood(
        obj,
        conflict_set={"inst_a": 0},
        iteration=1,
        cut_type="t",
        proof_stage="binding",
        proof_summary={},
    )

    assert captured[0].epsilon_stage is None
