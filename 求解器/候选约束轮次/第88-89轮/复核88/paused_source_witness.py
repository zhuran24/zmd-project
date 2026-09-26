"""A legal powered-but-switched-off source disproves the relay as written.

Also verifies a 70x70 embedding of this local witness. This witness is not a
factory meeting the global two-product targets and is not claimed to be one.
"""
from hashlib import sha256
from pathlib import Path
import json
import os

from exact_model import Model

HERE = Path(__file__).resolve().parent


def geometry():
    occupied = {}
    ports = {}
    def box(name, x, y, w, h):
        for xx in range(x, x+w):
            for yy in range(y, y+h):
                assert 0<=xx<70 and 0<=yy<70
                assert (xx, yy) not in occupied
                occupied[xx, yy] = name
    def port(x, y, dx, dy, role):
        assert (x, y) in occupied
        ports[x, y, dx, dy] = role
    box('core', 10, 10, 9, 9)
    for y in [11, 14, 17]:
        port(10, y, -1, 0, 'O')
        port(18, y, 1, 0, 'O')
    for x in range(11, 18):
        port(x, 10, 0, -1, 'I')
        port(x, 18, 0, 1, 'I')
    for name, x in [('Y', 20), ('X', 24)]:
        box(name, x, 10, 3, 3)
        for y in range(10, 13):
            port(x, y, -1, 0, 'I')
            port(x+2, y, 1, 0, 'O')
    box('power', 21, 15, 2, 2)
    paths = [[(19, 11)], [(23, 11)],
             [(27, y) for y in range(11, 21)]+[(x, 20) for x in range(26, 13, -1)]+[(14, 19)]]
    endpoints = [((18, 11), (20, 11)), ((22, 11), (24, 11)), ((26, 11), (14, 18))]
    expected = set()
    for j, path in enumerate(paths):
        full = [endpoints[j][0]]+path+[endpoints[j][1]]
        for i, (x, y) in enumerate(path, 1):
            name = f'belt{j}_{i}'
            box(name, x, y, 1, 1)
            prev, nxt = full[i-1], full[i+1]
            port(x, y, prev[0]-x, prev[1]-y, 'I')
            port(x, y, nxt[0]-x, nxt[1]-y, 'O')
        for a, b in zip(full, full[1:]):
            assert abs(a[0]-b[0])+abs(a[1]-b[1])==1
            expected.add((occupied[a], occupied[b]))
    actual = set()
    for (x, y, dx, dy), role in ports.items():
        if role=='O' and ports.get((x+dx, y+dy, -dx, -dy))=='I':
            actual.add((occupied[x, y], occupied[x+dx, y+dy]))
    assert actual==expected, (actual-expected, expected-actual)
    # Pole centre (22,16), coverage [16,28] x [10,22]. Both machines overlap it.
    assert all(max(x, 16)<min(x+3, 28) and max(10, 10)<min(13, 22) for x in [20, 24])
    return dict(core=[10, 10, 9, 9], Y=[20, 10, 3, 3], X=[24, 10, 3, 3],
                power=[21, 15, 2, 2], paths=paths, path_lengths=list(map(len, paths)),
                transport_count=sum(map(len, paths)), occupied_cells=len(occupied),
                channels=len(actual), no_unlisted_channels=True,
                both_machines_powered=True, source_switch_after_debug='off',
                source_recipe='1 蓝铁矿 → 1 蓝铁块，1 tick',
                recipient_recipe='1 蓝铁块 → 1 蓝铁粉末，1 tick')


def main():
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    geo = geometry()
    m = Model(q=10, seed=88088)
    y = m.machine('Y_refine_blue_ore')
    x = m.machine('X_crush_blue_block')
    ore = m.line(None, y, length=geo['path_lengths'][0], label='blue_ore')
    blue = m.line(y, x, length=geo['path_lengths'][1], label='blue_block')
    powder = m.line(x, None, length=geo['path_lengths'][2], label='blue_powder_to_core')
    m.prepare()
    m.close()
    signatures, counts, samples = {}, {}, []
    for t in range(1, 1101):
        m.t = t
        m.close()
        if t==105:
            assert m.machines[y].due==110
            m.pause_unfinished(y)
            m.close()
        if t in (105, 500, 900, 1000, 1010, 1100):
            sig = m.signature()
            signatures[t] = repr(sig)
            counts[t] = m.counters()
            samples.append(dict(tick=t/10, Y_stock=m.machines[y].stock[0],
                                Y_output=m.machines[y].output,
                                Y_cache_remaining=m.machines[y].paused_remaining/10,
                                Y_switch=m.machines[y].enabled,
                                X_stock=m.machines[x].stock[0], X_cache=m.machines[x].due,
                                X_output=m.machines[x].output,
                                YX_cells=m.lines[blue].cells,
                                warehouse_blue_powder=m.lines[powder].delivered))
    assert signatures[900]==signatures[1000]==signatures[1010]==signatures[1100]
    assert counts[900]==counts[1100]
    assert m.machines[y].due is not None and not m.machines[y].enabled
    assert m.machines[x].due is None and m.machines[x].enabled
    assert m.lines[blue].cells==[None]
    out = dict(geometry=geo, q=10, shutoff_tick='21/2', frozen_remaining_tick='1/2',
               steady_period_tick=1, witness_applies_to_indices=[11, 12, 13],
               samples=samples, equal_full_state=signatures[1000],
               state_sha256=sha256(signatures[1000].encode()).hexdigest(),
               no_events_in_steady_period=True,
               condition_check=dict(recipient_on_and_powered=True, d=1, a=1, c=1,
                    dc_ge_a=True, correct_inventory_output_and_single_batch=True,
                    source_cache_nonempty_at_every_real_time=True,
                    source_only_blue_ore_recipe=True, total_source_exits=1, output_batch_size=1,
                    exclusive_unrestricted_correct_line=True, recipient_cache_nonempty=False))
    (HERE/'paused_source_witness.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: out[k] for k in ['steady_period_tick', 'samples', 'state_sha256', 'condition_check']},
                     ensure_ascii=False))


if __name__=='__main__':
    main()
