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

from src.tests.cuts.test_family_power_grid_reach import _f5_fixture_state, _make_cert, _make_cut
from src.cuts.families.power_grid_reach import validate_power_grid_reach, evaluate_geometric_power_grid_reach, _build_full_free_mask, _protocol_core_cells
from src.cuts.helpers.power_cover import compute_cover_set, enumerate_valid_pole_anchors
from src.cuts.helpers.power_network import build_power_network, bfs_component

state = _f5_fixture_state(
    ghost_rect=(30,0,10,70),
    facility_anchor=(0,0),
    pc_anchor=(10,10),
    selected_poses=["p_3x3_a"],
)

actual_cells = tuple(tuple(c) for c in state.candidate_placements["facility_pools"]["manufacturing_3x3"][0]["occupied_cells"])
pc = (10,10)
free = _build_full_free_mask(state, actual_cells, pc)
cover = compute_cover_set(actual_cells, free, 5.0)
all_poles = enumerate_valid_pole_anchors(free)
graph = build_power_network(list(all_poles), 5.0, pc_cells=_protocol_core_cells(pc), ghost_rect=state.ghost_rect)
pc_comp = bfs_component(graph, pc)

print("actual cover size", len(cover), "reachable overlap", len(cover & pc_comp), "sample", sorted(cover & pc_comp)[:5])

cert_payload = _make_cert(state, facility_anchor=(60,60), protocol_core_cell=[10,10])
cut = _make_cut(cert_payload, state)
vr = validate_power_grid_reach(cut, state, {})
print("validator", vr.kind, vr.detail)
print("evaluator", evaluate_geometric_power_grid_reach(cut, state))
