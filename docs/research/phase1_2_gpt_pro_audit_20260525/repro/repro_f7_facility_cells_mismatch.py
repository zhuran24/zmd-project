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

from src.tests.cuts.test_family_power_hitting_set import _make_state, _make_cert, _make_cut
from src.cuts.families.power_hitting_set import validate_power_hitting_set
from src.cuts.lifecycle import evaluate_literal_multiset
from src.cuts.helpers.power_cover import compute_cover_set

state = _make_state(pose_anchor=(0,0), ghost_rect=(25,25,16,16))
state.groups["crusher_blue_iron"].selected_poses = ["p_3x3_a"]

actual = tuple(tuple(c) for c in state.candidate_placements["facility_pools"]["manufacturing_3x3"][0]["occupied_cells"])
free = frozenset((x,y) for x in range(70) for y in range(70)
               if (x,y) not in state.ghost_cells
               and (x,y) not in state.exterior_blocks
               and (x,y) not in state.cell_owner
               and (x,y) not in actual)
cover = compute_cover_set(actual, free, 5.0)

cert_payload = _make_cert(state)
cut = _make_cut(cert_payload, state)
vr = validate_power_hitting_set(cut, state, canonical_rules={})

print("actual cover size:", len(cover), "sample:", sorted(cover)[:5])
print("validator:", vr.kind, vr.detail)
print("evaluator:", evaluate_literal_multiset(cut, state))
print("actual_pose_cells_first_last:", actual[0], actual[-1])
