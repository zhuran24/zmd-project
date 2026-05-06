from __future__ import annotations

from types import SimpleNamespace

from src.search.phase3b_signature_monotonic_forced_label_audit import (
    audit_signature_monotonic_forced_labels,
    render_phase3b_signature_monotonic_forced_label_audit_markdown,
    render_phase3b_signature_monotonic_forced_label_audit_text,
)


def _fake_model_delegate():
    group_id = "group::alpha::op::0"
    model = SimpleNamespace(
        _mandatory_groups=[
            {
                "group_id": group_id,
                "facility_type": "alpha",
                "operation_type": "op",
                "count": 3,
            }
        ]
    )
    slot = SimpleNamespace(signature_id_to_bucket_id={0: "sig_000", 1: "sig_001", 2: "sig_002"})
    delegate = SimpleNamespace(
        mandatory_slots={group_id: [slot, slot, slot]},
        _mandatory_group_bucket_pose_indices={
            group_id: {
                "sig_000": (0,),
                "sig_001": (1,),
                "sig_002": (2,),
            }
        },
        _template_pose_tuple_by_idx={
            "alpha": {
                0: (0, 0, 0),
                1: (1, 0, 0),
                2: (2, 0, 0),
            }
        },
    )
    return model, delegate, group_id


def _fake_conjunctive_model_delegate():
    group_id = "group::alpha::op::0"
    model = SimpleNamespace(
        _mandatory_groups=[
            {
                "group_id": group_id,
                "facility_type": "alpha",
                "operation_type": "op",
                "count": 3,
            }
        ]
    )
    slot = SimpleNamespace(signature_id_to_bucket_id={0: "sig_000", 1: "sig_001", 2: "sig_002"})
    delegate = SimpleNamespace(
        mandatory_slots={group_id: [slot, slot, slot]},
        _mandatory_group_bucket_pose_indices={
            group_id: {
                "sig_000": (10, 11),
                "sig_001": (20,),
                "sig_002": (30,),
            }
        },
        _template_pose_tuple_by_idx={
            "alpha": {
                10: (0, 60, 1),
                11: (0, 10, 0),
                20: (1, 10, 1),
                30: (2, 60, 0),
            }
        },
    )
    return model, delegate, group_id


def test_signature_monotonic_audit_detects_inversion() -> None:
    model, delegate, group_id = _fake_model_delegate()
    labels = [
        {"group_id": group_id, "slot_index": 1, "field": "x", "forced_value": 2},
        {"group_id": group_id, "slot_index": 2, "field": "x", "forced_value": 1},
    ]

    report = audit_signature_monotonic_forced_labels(
        model,
        delegate,
        group_id=group_id,
        labels=labels,
    )

    mono = report["monotonicity"]
    assert mono["outcome"] == "monotonic_infeasible"
    assert mono["failure"]["slot_index"] == 2
    assert mono["failure"]["previous_possible_signature_ids"] == [2]
    assert mono["failure"]["current_allowed_signature_ids"] == [1]


def test_signature_monotonic_audit_conjoins_same_slot_fields() -> None:
    model, delegate, group_id = _fake_conjunctive_model_delegate()
    labels = [
        {"group_id": group_id, "slot_index": 0, "field": "y", "forced_value": 60},
        {"group_id": group_id, "slot_index": 0, "field": "mode", "forced_value": 0},
        {"group_id": group_id, "slot_index": 1, "field": "mode", "forced_value": 1},
    ]

    report = audit_signature_monotonic_forced_labels(
        model,
        delegate,
        group_id=group_id,
        labels=labels,
    )

    mono = report["monotonicity"]
    assert mono["outcome"] == "monotonic_infeasible"
    assert mono["constrained_slots"][:2] == [
        {"slot_index": 0, "allowed_signature_ids": [2]},
        {"slot_index": 1, "allowed_signature_ids": [0, 1]},
    ]
    assert mono["failure"] == {
        "slot_index": 1,
        "previous_possible_signature_ids": [2],
        "current_allowed_signature_ids": [0, 1],
    }


def test_signature_monotonic_audit_accepts_nondecreasing_labels() -> None:
    model, delegate, group_id = _fake_model_delegate()
    labels = [
        {"group_id": group_id, "slot_index": 1, "field": "x", "forced_value": 1},
        {"group_id": group_id, "slot_index": 2, "field": "x", "forced_value": 2},
    ]

    report = audit_signature_monotonic_forced_labels(
        model,
        delegate,
        group_id=group_id,
        labels=labels,
    )

    assert report["monotonicity"]["outcome"] == "monotonic_feasible"


def test_signature_monotonic_renderers_mark_no_solve() -> None:
    model, delegate, group_id = _fake_model_delegate()
    audit = audit_signature_monotonic_forced_labels(
        model,
        delegate,
        group_id=group_id,
        labels=[{"group_id": group_id, "slot_index": 1, "field": "x", "forced_value": 2}],
    )
    report = {
        "candidate": {"key": "67x13"},
        "target_group": audit["target_group"],
        "monotonicity": audit["monotonicity"],
        "status": {"outcome": "monotonic_feasible", "recommendation": "ok"},
    }

    markdown = render_phase3b_signature_monotonic_forced_label_audit_markdown(report)
    text = render_phase3b_signature_monotonic_forced_label_audit_text(report)

    assert "Solver invoked: false" in markdown
    assert "no_solve_signature_monotonic_forced_label_audit_not_proof_source" in markdown
    assert "solver_invoked=false" in text
