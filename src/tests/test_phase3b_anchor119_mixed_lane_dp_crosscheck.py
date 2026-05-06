from __future__ import annotations

from src.search.phase3b_anchor119_mixed_lane_dp_crosscheck import (
    _check_p9_p10_tail,
    _dp_first_nine_slots,
    _interval_mask,
    _lowest_set_bit,
    render_phase3b_anchor119_mixed_lane_dp_crosscheck_markdown,
    render_phase3b_anchor119_mixed_lane_dp_crosscheck_text,
)


def _row(x: int, y: int, order: int, signature: int, mask: int) -> dict:
    return {
        "x": x,
        "y": y,
        "mode": 0,
        "pose_index": order,
        "order_key": order,
        "signature_id": signature,
        "mask": mask,
    }


def test_interval_mask_and_lowest_set_bit() -> None:
    assert _interval_mask(16, 5, 16, 31) == 0b11111
    assert _interval_mask(21, 5, 16, 31) == 0b11111 << 5
    assert _interval_mask(27, 5, 16, 31) is None
    assert _lowest_set_bit(0b1001000) == 3


def test_first_nine_dp_uses_leftmost_exact_cover_and_row_order() -> None:
    masks = [_interval_mask(16 + 5 * i, 5, 16, 61) for i in range(9)]
    assert all(mask is not None for mask in masks)
    choices_by_x = {
        0: [_row(0, 16 + 5 * i, i, 0, int(mask)) for i, mask in enumerate(masks[:3])],
        1: [
            _row(1, 16 + 5 * i, 10 + i, 0, int(mask))
            for i, mask in enumerate(masks[3:], start=3)
        ],
    }
    required_mask = 0
    for mask in masks:
        required_mask |= int(mask)

    result = _dp_first_nine_slots(
        choices_by_x=choices_by_x,
        protocol_mask=0,
        required_mask=required_mask,
        slot_count=9,
    )

    assert result["state_counts"] == [1] * 9
    assert result["pattern_state_count"] == 1
    assert len(result["final_states"]) == 1
    assert result["final_states"][0]["mask_x0"] == int(masks[0] | masks[1] | masks[2])


def test_p9_p10_tail_requires_x0_subset_and_monotone_order() -> None:
    x0_mask = int(_interval_mask(16, 10, 16, 40))
    p9_mask = int(_interval_mask(16, 5, 16, 40))
    p10_mask = int(_interval_mask(21, 5, 16, 40))
    outside_mask = int(_interval_mask(30, 5, 16, 40))
    final_states = [
        {
            "mask_x0": x0_mask,
            "last_order": 10,
            "last_signature": 1,
            "sequence": [],
        }
    ]
    rows = [
        _row(5, 16, 11, 1, p9_mask),
        _row(5, 21, 12, 1, p10_mask),
        _row(5, 30, 13, 1, outside_mask),
    ]

    result = _check_p9_p10_tail(final_states=final_states, x5_choices=rows)

    assert result["witness"] is not None
    assert result["witness"]["p9"]["y"] == 16
    assert result["witness"]["p10"]["y"] == 21


def test_renderers_keep_diagnostic_boundaries() -> None:
    report = {
        "metadata": {"solver_invoked": False, "proof_source": False},
        "candidate": {"ghost_rect": {"x": 2, "y": 3, "w": 67, "h": 13}},
        "status": {
            "outcome": "dp_crosscheck_exhaustive_no_witness",
            "runtime_promotion_ready": False,
            "recommendation": "diagnostic only",
        },
        "domains": {"protocol_row_count": 90, "lane_choice_counts": {"0": 45}},
        "crosscheck": {
            "entry_count": 45,
            "total_final_cover_states": 9,
            "total_p9_p10_pairs_checked": 0,
        },
        "provenance": {"domain_rows_sha256_matches_reference": True},
        "witness": None,
        "checks": [
            {"check_id": "solver_not_invoked", "status": "pass", "detail": "custom DP"}
        ],
    }

    markdown = render_phase3b_anchor119_mixed_lane_dp_crosscheck_markdown(report)
    text = render_phase3b_anchor119_mixed_lane_dp_crosscheck_text(report)

    assert "Solver invoked: false" in markdown
    assert "Proof source: false" in markdown
    assert "Runtime promotion ready: `False`" in markdown
    assert "solver_invoked=false" in text
    assert "proof_source=false" in text
    assert "domain_hash_match=True" in text

