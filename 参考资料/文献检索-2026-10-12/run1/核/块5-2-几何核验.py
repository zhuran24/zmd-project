"""Read-only geometric checks of local counterexamples; not a factory simulator."""
from pathlib import Path
import json
import hashlib

OUT = Path(__file__).resolve().parent
SOURCE = Path('/home/zhuran24/zmd-research-fresh/求解器/候选约束轮次/第78-80轮/推导78A/final_general_a_witness.json')

def cells(r):
    x, y, w, h = r
    return {(a, b) for a in range(x, x+w) for b in range(y, y+h)}

def ports(z):
    x, y, w, h = z['r']
    if z['axis'] == 0:
        return [[(x-1, b) for b in range(y, y+h)], [(x+w, b) for b in range(y, y+h)]]
    return [[(a, y-1) for a in range(x, x+w)], [(a, y+h) for a in range(x, x+w)]]

def check(chosen, pole, empty=None):
    base = cells([0, 0, 70, 70])
    pc = cells(pole)
    forbidden = cells(empty) if empty else set()
    coverage = cells([pole[0]-5, pole[1]-5, 12, 12])
    occupied = set(pc)
    bodies = []
    for z in chosen:
        b = cells(z['r'])
        assert b <= base and not b & forbidden and not b & occupied
        assert b & coverage, 'No positive-area power intersection'
        occupied |= b
        bodies.append(b)
    bridge_cells = set()
    port_choices = []
    for z in chosen:
        choices = []
        for side in ports(z):
            free = sorted(set(side) & base - occupied - forbidden)
            assert free, ('No free cell on a port edge', z)
            choices.append(list(free[0]))
            bridge_cells.add(free[0])
        port_choices.append(choices)
    return dict(pole=pole, empty=empty, chosen=chosen,
                count=len(chosen), score=sum(2 if z['kind']=='s' else 3 for z in chosen),
                checks=dict(in_base=True, nonoverlap=True, avoids_empty=True,
                            power_positive_area=True, transport_cell_on_each_port_edge=True),
                port_choices=port_choices, bridge_cells=sorted(bridge_cells),
                limitation='Local powered geometry and port adjacency only; no full-factory throughput or cyclic-state certificate.')

def shifted(objects, dx, dy):
    return [dict(z, r=[z['r'][0]+dx, z['r'][1]+dy, *z['r'][2:]]) for z in objects]

data = json.loads(SOURCE.read_text())
objects = data['chosen']
far_wall = check(shifted(objects, 53, 25), [58, 30, 2, 2])
far_wall['g'] = 70-(58+2)
far_wall['wall_touching_machines'] = [z for z in far_wall['chosen'] if z['r'][0]+z['r'][2] == 70]
far_wall['raw_loss'] = 54-far_wall['score']

# A finite rectangular hole excludes an intersection of two half-planes,
# unlike a pair of infinite walls, which excludes their union.
local_empty = cells([7, -31, 30, 37])
kept = [z for z in objects if not cells(z['r']) & local_empty]
# Discard bodies whose entire input/output edge faces the hole or a body.
# This independently enforces the necessary port adjacency after carving.
while True:
    occupied = cells([5, 5, 2, 2]) | set().union(*(cells(z['r']) for z in kept))
    filtered = [z for z in kept if all(set(side)-occupied-local_empty for side in ports(z))]
    if len(filtered) == len(kept):
        break
    kept = filtered
corner = check(shifted(kept, 24, 36), [29, 41, 2, 2], [31, 5, 30, 37])
corner['g_to_left_side'] = 0
corner['coverage_y'] = [36, 47]
corner['empty_y'] = [5, 41]
corner['halfplane_wall_cap_g0'] = 29
corner['score_exceeds_halfplane_cap'] = corner['score'] > 29

result = dict(source=str(SOURCE), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              far_wall=far_wall, finite_corner=corner)
path = OUT/'块5-2-几何核验.json'
path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({k: {a: v for a,v in z.items() if a not in ('chosen','port_choices','bridge_cells')}
                  for k,z in [('far_wall',far_wall), ('finite_corner',corner)]}, ensure_ascii=False, indent=2))
