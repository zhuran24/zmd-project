"""Tests for P1 #7b prep — cut pool ε-stage bucketing on BendersCut."""

from __future__ import annotations

from src.models.cut_manager import BendersCut, CutManager


def _make_cut(epsilon_stage, cut_id="x") -> BendersCut:
    return BendersCut(
        cut_type="binding_pose_domain_empty_nogood",
        conflict_set={cut_id: "p0"},
        iteration=1,
        epsilon_stage=epsilon_stage,
        exact_safe=True,
    )


def test_to_dict_roundtrip_preserves_epsilon_stage():
    cut = _make_cut(epsilon_stage=0.05)
    payload = cut.to_dict()
    assert payload["epsilon_stage"] == 0.05
    restored = BendersCut.from_dict(payload)
    assert restored.epsilon_stage == 0.05


def test_to_dict_roundtrip_none_default():
    cut = _make_cut(epsilon_stage=None)
    payload = cut.to_dict()
    assert payload["epsilon_stage"] is None
    restored = BendersCut.from_dict(payload)
    assert restored.epsilon_stage is None


def test_legacy_payload_without_field_loads_as_none():
    """Backward compat: 旧 cut json 没 epsilon_stage 字段 → from_dict 默认 None."""
    payload = {
        "schema_version": 1,
        "cut_type": "any",
        "conflict_set": {"a": "1"},
        "iteration": 0,
        # epsilon_stage 故意不设
    }
    cut = BendersCut.from_dict(payload)
    assert cut.epsilon_stage is None


def test_cuts_for_stage_loose_to_tight(tmp_path):
    """0.05 stage 的 cut 在 0.01/0.0 阶段都可 reuse, 反向不行."""
    cm = CutManager(checkpoint_dir=tmp_path)
    cm.cuts.extend([
        _make_cut(epsilon_stage=0.05, cut_id="loose"),
        _make_cut(epsilon_stage=0.01, cut_id="mid"),
        _make_cut(epsilon_stage=0.0, cut_id="tight"),
        _make_cut(epsilon_stage=None, cut_id="legacy"),
    ])
    # target = 0.0 (最紧阶段) → 所有都可用 (0.05/0.01/0.0/legacy)
    keys_at_zero = sorted(next(iter(c.conflict_set)) for c in cm.cuts_for_stage(0.0))
    assert keys_at_zero == ["legacy", "loose", "mid", "tight"]

    # target = 0.01 → 0.05/0.01/legacy, 不含 0.0
    keys_at_01 = sorted(next(iter(c.conflict_set)) for c in cm.cuts_for_stage(0.01))
    assert keys_at_01 == ["legacy", "loose", "mid"]

    # target = 0.05 → 0.05/legacy, 不含 0.01/0.0
    keys_at_05 = sorted(next(iter(c.conflict_set)) for c in cm.cuts_for_stage(0.05))
    assert keys_at_05 == ["legacy", "loose"]


def test_cuts_for_stage_only_legacy(tmp_path):
    cm = CutManager(checkpoint_dir=tmp_path)
    cm.cuts.append(_make_cut(epsilon_stage=None, cut_id="only_legacy"))
    # legacy cut 在任何 ε 都用
    assert len(cm.cuts_for_stage(0.0)) == 1
    assert len(cm.cuts_for_stage(0.05)) == 1
    assert len(cm.cuts_for_stage(0.10)) == 1
