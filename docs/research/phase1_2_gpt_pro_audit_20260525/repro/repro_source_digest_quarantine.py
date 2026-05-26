from pathlib import Path
import sys


def _find_project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "PROJECT_LOCK.md").is_file() and (candidate / "src" / "cuts").is_dir():
            return candidate
    raise RuntimeError(
        "Could not locate project root: expected PROJECT_LOCK.md and src/cuts above "
        f"{start}"
    )


_PROJECT_ROOT = _find_project_root(Path(__file__).resolve().parent)
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import os
from src.tests.cuts.test_family_power_hitting_set import _make_state
from src.cuts.oracles.power_cover_oracle import generate_power_hitting_set_cuts
from src.cuts.lifecycle import compute_source_digest, step_6_attach_scope_check

os.environ["EXACT_F7_GENERATOR_ENABLED"] = "1"

state = _make_state()
state.source_digest = "stale-human-note-not-canonical-digest"

cuts = generate_power_hitting_set_cuts(
    state,
    target_poses=[("crusher_blue_iron", "p_3x3_a")],
    pole_radius=5.0,
    iter_index=0,
)
print("cuts", len(cuts))
cut = cuts[0]
print("cut_scope_digest", cut.scope.source_digest)
print("computed_digest_prefix", compute_source_digest(state)[:16])
print("scope_eq_computed", cut.scope.source_digest == compute_source_digest(state))
print("step6", step_6_attach_scope_check(cut, state))
