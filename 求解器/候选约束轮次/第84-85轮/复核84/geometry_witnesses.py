#!/usr/bin/env python3
"""Validate the actual local geometry of the two new counterexamples."""
import json
import os
from pathlib import Path
from probes import merger_witness, quota_loop

HERE = Path(__file__).resolve().parent
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})


def line(a, b):
    x, y = a; u, v = b
    assert x == u or y == v
    n = abs(x-u) + abs(y-v)
    dx, dy = (0 if x == u else (1 if x < u else -1)), (0 if y == v else (1 if y < v else -1))
    return [(x+i*dx, y+i*dy) for i in range(n+1)]


def poly(*points):
    out = []
    for a, b in zip(points, points[1:]): out.extend(line(a,b)[:-1])
    return out + [points[-1]]


def check(bodies, paths, pillars):
    occupied = {}
    for name, (x,y,w,h) in bodies.items():
        for xx in range(x,x+w):
            for yy in range(y,y+h):
                assert (xx,yy) not in occupied
                occupied[xx,yy] = name
    for x,y,w,h in pillars:
        for xx in range(x,x+w):
            for yy in range(y,y+h):
                assert (xx,yy) not in occupied
                occupied[xx,yy] = 'pillar'
    transport = {}
    for name, path in paths.items():
        assert len(path) == len(set(path))
        for j, (x,y) in enumerate(path):
            assert 0 <= x < 70 and 0 <= y < 70 and (x,y) not in occupied, (name,x,y)
            if j: assert abs(x-path[j-1][0])+abs(y-path[j-1][1]) == 1
            transport.setdefault((x,y), []).append((name,j))
    crossings = []
    for cell, uses in transport.items():
        if len(uses) == 1: continue
        assert len(uses) == 2
        axes = []
        for name, j in uses:
            p = paths[name]
            assert 0 < j < len(p)-1
            before, after = p[j-1], p[j+1]
            assert before[0] == after[0] or before[1] == after[1]
            axes.append('v' if before[0] == after[0] else 'h')
        assert set(axes) == {'v','h'}
        crossings.append(cell)
    for name,(x,y,w,h) in bodies.items():
        if name.startswith('Z'): continue  # wireless is off
        assert any(max(x,px+1-6) < min(x+w,px+1+6) and max(y,py+1-6) < min(y+h,py+1+6)
                   for px,py,_,_ in pillars), name
    return {'bodies_nonoverlap': True, 'all_transport_inside_base': True,
            'transport_physical_cells': len(transport), 'bridge_crossings': crossings,
            'manufacturers_powered': True}


def main():
    q = quota_loop()['geometry']
    qcheck = check({'Y':q['Y_body'], 'X':q['X_body']},
                   {'gate':[tuple(q['gate'])], 'return':list(map(tuple,q['return_belts']))}, [q['power_pillar']])
    merge = merger_witness()['geometry']
    paths = {
        'CA':poly((25,21),(29,21)),
        'CB':poly((25,23),(26,23),(26,31),(29,31)),
        'AC':poly((35,22),(35,27),(18,27),(18,22),(19,22)),
        'BK':poly((35,32),(36,32),(36,8),(8,8),(8,11),(9,11)),
        'M_return':list(map(tuple,merge['return_belts'])),
        'Z_feed':[tuple(merge['feed_belt'])],
        'M':[tuple(merge['merger_M'])], 'D':[tuple(merge['splitter_D'])]}
    bodies = {'C':[20,20,5,5], 'A':[30,20,5,5], 'B':[30,30,5,5],
              'K':merge['K_body'], 'Z_box':merge['box_Z']}
    pillars = [[17,18,2,2],[28,17,2,2],[28,35,2,2],[6,13,2,2]]
    mcheck = check(bodies, paths, pillars)
    # All manufacturer inputs face west, outputs east; Z is the reverse.
    endpoints = [('CA','C','A'),('CB','C','B'),('AC','A','C'),('BK','B','K')]
    for pname, a, b in endpoints:
        p=paths[pname]; ax,ay,aw,ah=bodies[a]; bx,by,bw,bh=bodies[b]
        assert p[0][0] == ax+aw and ay <= p[0][1] < ay+ah
        assert p[-1][0] == bx-1 and by <= p[-1][1] < by+bh
    # Derive every automatic external port contact, including unused ports.
    ports = {}
    def port(cell, delta, mode): ports.setdefault((tuple(cell),tuple(delta)),set()).add(mode)
    for name,(x,y,w,h) in bodies.items():
        for yy in range(y,y+h):
            port((x,yy),(-1,0),'out' if name=='Z_box' else 'in')
            port((x+w-1,yy),(1,0),'in' if name=='Z_box' else 'out')
    endpoints_cells = {'CA':((24,21),(30,21)), 'CB':((24,23),(30,31)),
                       'AC':((34,22),(20,22)), 'BK':((34,32),(10,11)),
                       'M_return':((13,11),(17,12)), 'Z_feed':((15,12),(13,12))}
    expected = set()
    crossings = set(map(tuple,mcheck['bridge_crossings']))
    for name,(src,dst) in endpoints_cells.items():
        p = paths[name]; whole = [src]+p+[dst]
        for a,b in zip(whole,whole[1:]): expected.add((a,b))
        for j,c in enumerate(p,1):
            before,after=whole[j-1],whole[j+1]
            port(c,(before[0]-c[0],before[1]-c[1]),'in')
            port(c,(after[0]-c[0],after[1]-c[1]),'out')
            if c in crossings:
                port(c,(before[0]-c[0],before[1]-c[1]),'out')
                port(c,(after[0]-c[0],after[1]-c[1]),'in')
    for d in ((-1,0),(1,0),(0,1)): port((13,11),d,'in')
    port((13,11),(0,-1),'out')
    port((13,12),(1,0),'in')
    for d in ((-1,0),(0,1),(0,-1)): port((13,12),d,'out')
    expected.update({((12,11),(13,11)),((13,12),(13,11))})
    actual=set()
    for (c,d), modes in ports.items():
        neighbor=(c[0]+d[0],c[1]+d[1])
        if 'out' in modes and 'in' in ports.get((neighbor,(-d[0],-d[1])),set()):
            actual.add((c,neighbor))
    assert actual == expected, {'extra':list(actual-expected),'missing':list(expected-actual)}
    mcheck['all_automatic_port_contacts_match'] = True
    mcheck['external_directed_contacts'] = len(actual)
    ans = {'quota_geometry_validation':qcheck,
           'plant_merger_counterexample': {'bodies':bodies,'paths':paths,'pillars':pillars,'checks':mcheck,
                                            'L1':len(paths['CA']),'L2':len(paths['AC']),
                                            'full_frozen_phi':len(paths['CA'])+len(paths['AC'])+177}}
    cache_bodies={name:rect for name,rect in bodies.items() if name!='Z_box'}
    cache_bodies['Z_box']=[14,10,3,3]
    cache_paths={name:p for name,p in paths.items() if name in ('CA','CB','AC','BK')}
    cache_paths['K_export']=[(13,11)]
    ans['old_cache_counterexample']={'bodies':cache_bodies,'paths':cache_paths,'pillars':pillars,
                                     'checks':check(cache_bodies,cache_paths,pillars),
                                     'release_action':'Build K_export last; it fills from K and cannot leave until one tick later.'}
    (HERE/'geometry_witnesses.json').write_text(json.dumps(ans,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'quota':qcheck,'merger':mcheck,'L1':ans['plant_merger_counterexample']['L1'],
                      'L2':ans['plant_merger_counterexample']['L2']},ensure_ascii=False))


if __name__ == '__main__': main()
