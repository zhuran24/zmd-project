from __future__ import annotations

from types import SimpleNamespace

from src.search.phase3b.signature_region.equivalence_audit import (
    audit_mandatory_group_signature_region_equivalence,
    render_phase3b_signature_region_equivalence_audit_markdown,
    render_phase3b_signature_region_equivalence_audit_text,
)


def _fake_model_and_delegate(*, extra_region_tuple: bool = False, overlap: bool = False):
    group_id = "group::manufacturing_6x4::grinder_dense_blue_iron::14"
    model = SimpleNamespace(
        _mandatory_groups=[
            {
                "group_id": group_id,
                "facility_type": "grinder_dense_blue_iron",
                "operation_type": "manufacturing_6x4",
                "count": 10,
            }
        ]
    )
    regions_a = [SimpleNamespace(mode_id=0, x_min=0, x_max=1, y_min=0, y_max=0)]
    if extra_region_tuple:
        regions_a = [SimpleNamespace(mode_id=0, x_min=0, x_max=2, y_min=0, y_max=0)]
    regions_b = [SimpleNamespace(mode_id=1, x_min=5, x_max=5, y_min=7, y_max=7)]
    if overlap:
        regions_b = [SimpleNamespace(mode_id=0, x_min=1, x_max=1, y_min=0, y_max=0)]
    delegate = SimpleNamespace(
        _mandatory_group_bucket_pose_indices={
            group_id: {
                "sig_000": (0, 1),
                "sig_001": (2,),
            }
        },
        _mandatory_group_bucket_regions={
            group_id: {
                "sig_000": regions_a,
                "sig_001": regions_b,
            }
        },
        _mandatory_group_uses_signature_table={group_id: False},
        _mandatory_group_uses_domain_table={group_id: False},
        _template_pose_tuple_by_idx={
            "grinder_dense_blue_iron": {
                0: (0, 0, 0),
                1: (1, 0, 0),
                2: (5, 7, 1),
            }
        },
    )
    return model, delegate, group_id


def test_signature_region_equivalence_passes_for_matching_regions() -> None:
    model, delegate, group_id = _fake_model_and_delegate()

    report = audit_mandatory_group_signature_region_equivalence(
        model,
        delegate,
        group_id=group_id,
    )

    eq = report["equivalence"]
    assert eq["evaluated"] is True
    assert eq["outcome"] == "equivalent"
    assert eq["mismatched_bucket_count"] == 0
    assert eq["overlap_tuple_count"] == 0
    assert eq["exact_union_tuple_count"] == 3
    assert eq["region_union_tuple_count"] == 3


def test_signature_region_equivalence_reports_extra_tuple() -> None:
    model, delegate, group_id = _fake_model_and_delegate(extra_region_tuple=True)

    report = audit_mandatory_group_signature_region_equivalence(
        model,
        delegate,
        group_id=group_id,
    )

    eq = report["equivalence"]
    assert eq["outcome"] == "mismatch_detected"
    assert eq["mismatched_bucket_count"] == 1
    assert eq["union_extra_tuple_count"] == 1
    bucket = next(item for item in eq["buckets"] if item["bucket_id"] == "sig_000")
    assert bucket["extra_tuple_sample"] == [[2, 0, 0]]


def test_signature_region_equivalence_reports_overlap() -> None:
    model, delegate, group_id = _fake_model_and_delegate(overlap=True)

    report = audit_mandatory_group_signature_region_equivalence(
        model,
        delegate,
        group_id=group_id,
    )

    eq = report["equivalence"]
    assert eq["outcome"] == "mismatch_detected"
    assert eq["overlap_tuple_count"] == 1
    assert eq["overlap_tuple_sample"][0]["tuple"] == [1, 0, 0]


def test_signature_region_renderers_include_no_solve_semantics() -> None:
    model, delegate, group_id = _fake_model_and_delegate()
    audit = audit_mandatory_group_signature_region_equivalence(
        model,
        delegate,
        group_id=group_id,
    )
    report = {
        "candidate": {"key": "67x13"},
        "status": {"outcome": "equivalent", "recommendation": "ok"},
        "target_group": audit["target_group"],
        "equivalence": audit["equivalence"],
    }

    markdown = render_phase3b_signature_region_equivalence_audit_markdown(report)
    text = render_phase3b_signature_region_equivalence_audit_text(report)

    assert "Solver invoked: false" in markdown
    assert "no_solve_signature_region_equivalence_not_proof_source" in markdown
    assert "solver_invoked=false" in text
