from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.search.phase3b_active_guard_proto_shape_audit import (
    ACTIVE_GUARD_PROTO_SHAPE_AUDIT_SOURCE,
    audit_active_guard_bool_or_clauses,
    independent_active_guard_expected_counts,
    render_phase3b_active_guard_proto_shape_audit_markdown,
    render_phase3b_active_guard_proto_shape_audit_text,
)


class _Constraint:
    def __init__(self, literals: list[int]) -> None:
        self.bool_or = SimpleNamespace(literals=literals)

    def has_bool_or(self) -> bool:
        return True


class _LinearConstraint:
    bool_or = SimpleNamespace(literals=[])

    def has_bool_or(self) -> bool:
        return False


def _lit(index: int, *, negated: bool = False) -> int:
    return -int(index) - 1 if negated else int(index)


def _proto() -> SimpleNamespace:
    names = [
        "active__residual_optional::protocol_storage_box::slot::0",
        "cover_choice_block_selected__residual_optional::protocol_storage_box::slot::0__block::000",
        "cover_choice_local_selected__residual_optional::protocol_storage_box::slot::0__local::000",
        "active__residual_optional::power_pole::slot::0",
        "cover_choice_block_selected__group::manufacturing_3x3::crusher::1::slot::0__block::000",
        "cover_choice_local_selected__group::manufacturing_3x3::crusher::1::slot::0__local::000",
        "active__residual_optional::power_pole::slot::1",
        "cover_choice_local_selected__residual_optional::protocol_storage_box::slot::1__local::000",
    ]
    return SimpleNamespace(
        variables=[SimpleNamespace(name=name) for name in names],
        constraints=[
            _LinearConstraint(),
            _Constraint([_lit(0, negated=True), _lit(1, negated=True), _lit(2, negated=True), _lit(3)]),
            _Constraint([_lit(4, negated=True), _lit(5, negated=True), _lit(6)]),
        ],
    )


class _Slot:
    def __init__(self, *, template: str, active: object | None, key: str = "") -> None:
        self.template = template
        self.active = active
        self.key = key


class _Delegate:
    residual_optional_slots = {
        "power_pole": [
            _Slot(template="power_pole", active=object(), key="residual_optional::power_pole::slot::0"),
            _Slot(template="power_pole", active=object(), key="residual_optional::power_pole::slot::1"),
            _Slot(template="power_pole", active=object(), key="residual_optional::power_pole::slot::2"),
            _Slot(template="power_pole", active=object(), key="residual_optional::power_pole::slot::3"),
            _Slot(template="power_pole", active=object(), key="residual_optional::power_pole::slot::4"),
        ]
    }

    def _all_powered_slots(self) -> list[_Slot]:
        return [
            _Slot(
                template="protocol_storage_box",
                active=object(),
                key="residual_optional::protocol_storage_box::slot::0",
            ),
            _Slot(
                template="manufacturing_3x3",
                active=None,
                key="group::manufacturing_3x3::crusher::1::slot::0",
            ),
        ]

    def _use_block_element_power_coverage_for_template(self, template: str) -> bool:
        return True


class _FilteredDelegate(_Delegate):
    def _use_block_element_power_coverage_for_template(self, template: str) -> bool:
        return str(template) == "protocol_storage_box"


def test_active_guard_bool_or_shape_accepts_optional_and_mandatory_guards() -> None:
    result = audit_active_guard_bool_or_clauses(_proto(), expected_guard_count=2)

    assert result["total_bool_or_count"] == 2
    assert result["guard_clause_count"] == 2
    assert result["valid_guard_clause_count"] == 2
    assert result["invalid_guard_clause_count"] == 0
    assert result["matches_expected_guard_clause_count"] is True
    assert result["all_guard_clauses_valid"] is True
    assert result["optional_powered_guard_count"] == 1
    assert result["mandatory_powered_guard_count"] == 1
    assert result["literal_count_distribution"] == {"3": 1, "4": 1}
    assert result["template_counts"]["protocol_storage_box"] == 1
    assert result["template_counts"]["manufacturing_3x3"] == 1


def test_active_guard_bool_or_shape_validates_expected_signature_bijection() -> None:
    expected = {
        "residual_optional::protocol_storage_box::slot::0|block:000|local:000": (
            "residual_optional::power_pole::slot::0"
        ),
        "group::manufacturing_3x3::crusher::1::slot::0|block:000|local:000": (
            "residual_optional::power_pole::slot::1"
        ),
    }

    result = audit_active_guard_bool_or_clauses(
        _proto(),
        expected_guard_count=2,
        expected_signature_to_pole_key=expected,
    )

    assert result["expected_signature_bijection_valid"] is True
    assert result["expected_signature_count"] == 2
    assert result["actual_signature_count"] == 2
    assert result["expected_signature_match_count"] == 2
    assert result["missing_expected_signature_count"] == 0
    assert result["unexpected_signature_count"] == 0
    assert result["duplicate_signature_count"] == 0
    assert result["pole_key_mismatch_count"] == 0
    assert result["expected_signature_hash"] == result["actual_signature_hash"]


def test_active_guard_bool_or_shape_reports_expected_signature_gap() -> None:
    expected = {
        "residual_optional::protocol_storage_box::slot::0|block:000|local:000": (
            "residual_optional::power_pole::slot::99"
        ),
        "missing::powered|block:000|local:000": (
            "residual_optional::power_pole::slot::1"
        ),
    }

    result = audit_active_guard_bool_or_clauses(
        _proto(),
        expected_guard_count=2,
        expected_signature_to_pole_key=expected,
    )

    assert result["expected_signature_bijection_valid"] is False
    assert result["missing_expected_signature_count"] == 1
    assert result["unexpected_signature_count"] == 1
    assert result["pole_key_mismatch_count"] == 1
    assert result["expected_signature_mismatch_samples"]
    assert result["missing_expected_signature_samples"]


def test_active_guard_bool_or_shape_reports_invalid_mismatched_key() -> None:
    proto = _proto()
    proto.constraints.append(
        _Constraint([_lit(0, negated=True), _lit(1, negated=True), _lit(7, negated=True), _lit(3)])
    )

    result = audit_active_guard_bool_or_clauses(proto, expected_guard_count=3)

    assert result["guard_clause_count"] == 3
    assert result["valid_guard_clause_count"] == 2
    assert result["invalid_guard_clause_count"] == 1
    assert result["all_guard_clauses_valid"] is False
    assert result["invalid_samples"][0]["reason"] == "invalid_active_guard_clause"


def test_independent_expected_count_handles_padding_optional_and_mandatory() -> None:
    result = independent_active_guard_expected_counts(_Delegate(), block_size=4)

    assert result["status"] == "evaluated"
    assert result["pole_slot_count"] == 5
    assert result["powered_slot_count"] == 2
    assert result["padded_pole_position_count"] == 8
    assert result["padded_block_value_count"] == 3
    assert result["expected_guard_clause_count"] == 16
    assert result["optional_powered_guard_count"] == 8
    assert result["mandatory_powered_guard_count"] == 8
    assert result["template_counts"] == {
        "manufacturing_3x3": 8,
        "protocol_storage_box": 8,
    }
    assert result["expected_signature_count"] == 16
    assert result["expected_signature_hash"]
    assert result["expected_signature_samples"]


def test_independent_expected_count_respects_template_filter() -> None:
    result = independent_active_guard_expected_counts(_FilteredDelegate(), block_size=4)

    assert result["powered_slot_count"] == 1
    assert result["expected_guard_clause_count"] == 8
    assert result["optional_powered_guard_count"] == 8
    assert result["mandatory_powered_guard_count"] == 0
    assert result["template_counts"] == {"protocol_storage_box": 8}


def test_active_guard_proto_shape_renderers_and_script_surface() -> None:
    report = {
        "metadata": {
            "source": ACTIVE_GUARD_PROTO_SHAPE_AUDIT_SOURCE,
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "status": {
            "outcome": "active_guard_proto_shape_valid",
            "recommendation": "diagnostic only",
        },
        "active_guard_shape": audit_active_guard_bool_or_clauses(
            _proto(), expected_guard_count=2
        )
        | {
            "witness_matches_independent_expected": True,
            "witness_expected_guard_clause_count": 2,
            "optional_powered_guard_count_matches_independent_expected": True,
            "mandatory_powered_guard_count_matches_independent_expected": True,
            "template_counts_match_independent_expected": True,
            "expected_signature_bijection_valid": True,
            "expected_signature_hash_matches_independent": True,
            "actual_signature_count": 2,
            "expected_signature_count": 2,
            "missing_expected_signature_count": 0,
            "unexpected_signature_count": 0,
            "duplicate_signature_count": 0,
            "pole_key_mismatch_count": 0,
            "independent_expected": {
                "optional_powered_guard_count": 1,
                "mandatory_powered_guard_count": 1,
                "template_counts": {
                    "manufacturing_3x3": 1,
                    "protocol_storage_box": 1,
                },
            },
        },
        "checks": [
            {
                "check_id": "solver_not_invoked",
                "status": "pass",
                "detail": "solver_invoked=false",
            }
        ],
    }

    markdown = render_phase3b_active_guard_proto_shape_audit_markdown(report)
    text = render_phase3b_active_guard_proto_shape_audit_text(report)
    script_text = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "build_phase3b_active_guard_proto_shape_audit.py"
    ).read_text(encoding="utf-8")

    assert "ActiveGuard Proto Shape Audit" in markdown
    assert "candidate_elimination_claim: False" in markdown
    assert "guard_clause_count=2" in text
    assert "witness_matches_independent_expected=True" in text
    assert "template_counts_match_independent_expected=True" in text
    assert "expected_signature_bijection_valid=True" in text
    assert "Signature counts: actual=2 expected=2" in markdown
    assert "active_guard_proto_shape_audit.json" in script_text
    assert "solver_invoked" in script_text
