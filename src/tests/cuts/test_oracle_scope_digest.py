import os

from src.cuts.lifecycle import compute_source_digest
from src.cuts.oracles.power_cover_oracle import generate_power_hitting_set_cuts
from src.tests.cuts.test_family_power_hitting_set import _make_state


def test_oracle_scope_uses_computed_source_digest_even_if_state_field_is_stale() -> None:
    os.environ["EXACT_F7_GENERATOR_ENABLED"] = "1"
    try:
        state = _make_state()
        state.source_digest = "stale-human-note-not-canonical-digest"
        cuts = generate_power_hitting_set_cuts(
            state,
            target_poses=[("crusher_blue_iron", "p_3x3_a")],
            pole_radius=5.0,
            iter_index=0,
        )
        assert len(cuts) == 1
        assert cuts[0].scope.source_digest == compute_source_digest(state)
    finally:
        os.environ.pop("EXACT_F7_GENERATOR_ENABLED", None)
