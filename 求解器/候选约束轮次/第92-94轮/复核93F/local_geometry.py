#!/usr/bin/env python3
"""A physical plant-unit witness, not a complete qualifying factory layout."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def polyline(points):
    result = [tuple(points[0])]
    for a, b in zip(points, points[1:]):
        assert a[0] == b[0] or a[1] == b[1]
        dx = (b[0] > a[0]) - (b[0] < a[0])
        dy = (b[1] > a[1]) - (b[1] < a[1])
        x, y = a
        while (x,y) != tuple(b):
            x, y = x+dx, y+dy
            result.append((x,y))
    return result


def main():
    rect = {'C': [20,20,5,5], 'A': [32,20,5,5], 'B': [33,27,5,5],
            'K': [43,28,3,3], 'G': [51,26,4,6], '协议核心': [5,50,9,9],
            '供电桩1': [26,18,2,2], '供电桩2': [39,25,2,2], '供电桩3': [48,24,2,2]}
    kind = {'C': '采种机', 'A': '种植机', 'B': '种植机', 'K': '粉碎机', 'G': '研磨机'}
    vertices = {'CA': [(25,22),(31,22)],
                'CB': [(25,24),(27,24),(27,29),(32,29)],
                'AC': [(37,21),(38,21),(38,17),(18,17),(18,21),(19,21)],
                'BK': [(38,29),(42,29)], 'K0': [(46,28),(50,28)], 'K1': [(46,30),(50,30)]}
    ends = {'CA': ['C','A'], 'CB': ['C','B'], 'AC': ['A','C'],
            'BK': ['B','K'], 'K0': ['K','G'], 'K1': ['K','G']}
    routes = {r: polyline(p) for r,p in vertices.items()}
    cells, ports = {}, {}
    def place(name, occupied):
        for xy in occupied:
            assert xy not in cells, (name, xy, cells.get(xy))
            assert all(0 <= z < 70 for z in xy)
            cells[xy] = name
    for n,(x,y,w,h) in rect.items():
        place(n, [(a,b) for a in range(x,x+w) for b in range(y,y+h)])
        if n in kind:
            ports[n] = {'in': [((x,b),(-1,0)) for b in range(y,y+h)],
                        'out': [((x+w-1,b),(1,0)) for b in range(y,y+h)]}
    x,y,w,h = rect['协议核心']
    ports['协议核心'] = {'in': [((a,b),d) for a in range(x+1,x+8)
                                         for b,d in ((y,(0,-1)),(y+8,(0,1)))],
                            'out': [((a,b),d) for b in (y+1,y+4,y+7)
                                             for a,d in ((x,(-1,0)),(x+8,(1,0)))]}
    expected = set()
    for r,road in routes.items():
        src,dst = ends[r]
        sx,sy,sw,sh = rect[src]
        tx,ty,tw,th = rect[dst]
        before = (sx+sw-1, road[0][1])
        after = (tx, road[-1][1])
        line = [before] + road + [after]
        assert sx <= before[0] < sx+sw and sy <= before[1] < sy+sh
        assert tx <= after[0] < tx+tw and ty <= after[1] < ty+th
        chain = [src] + [f'{r}:{i}' for i in range(len(road))] + [dst]
        expected.update(zip(chain, chain[1:]))
        for j,xy in enumerate(road,1):
            prev,nxt = line[j-1],line[j+1]
            assert sum(abs(a-b) for a,b in zip(xy,prev)) == 1
            assert sum(abs(a-b) for a,b in zip(xy,nxt)) == 1
            incoming = (prev[0]-xy[0],prev[1]-xy[1])
            outgoing = (nxt[0]-xy[0],nxt[1]-xy[1])
            assert incoming != outgoing
            n = chain[j]
            place(n,[xy])
            ports[n] = {'in': [(xy,incoming)], 'out': [(xy,outgoing)]}
    actual = set()
    incoming = {(xy,d): n for n,p in ports.items() for xy,d in p['in']}
    for n,p in ports.items():
        for xy,d in p['out']:
            key = ((xy[0]+d[0],xy[1]+d[1]),(-d[0],-d[1]))
            if key in incoming:
                dst = incoming[key]
                assert ':' in n or ':' in dst
                actual.add((n,dst))
    assert actual == expected, (actual-expected,expected-actual)
    # Independent path-length computation from Manhattan segment lengths.
    lengths_a = {r: len(road) for r,road in routes.items()}
    lengths_b = {r: 1+sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(p,p[1:]))
                 for r,p in vertices.items()}
    assert lengths_a == lengths_b
    occupied_by_formula=sum(w*h for x,y,w,h in rect.values())+sum(lengths_b.values())
    assert occupied_by_formula == len(cells)
    assert len(actual) == sum(lengths_b.values())+len(routes)
    coverage = {}
    for n in kind:
        x,y,w,h = rect[n]
        covered = []
        for pole in ('供电桩1','供电桩2','供电桩3'):
            px,py,pw,ph = rect[pole]
            # Strictly positive overlap of physical rectangles; avoids any
            # dependence on whether touching the coverage edge is sufficient.
            cx,cy = px+1,py+1
            if max(x,cx-6)<min(x+w,cx+6) and max(y,cy-6)<min(y+h,cy+6):
                covered.append(pole)
        assert covered
        coverage[n] = covered
    result = {'scope': '合法局部采种单元及停机研磨机；不是完整达标布局',
              'rectangles': rect, 'machine_types': kind, 'route_vertices': vertices,
              'route_cells': routes, 'route_ends': ends, 'lengths_by_cells': lengths_a,
              'lengths_by_segments': lengths_b, 'power_coverage': coverage,
              'occupied_cells': len(cells), 'formed_channels': len(actual),
              'occupied_cells_independent_sum': occupied_by_formula,
              'channel_count_by_path_lengths': sum(lengths_b.values())+len(routes),
              'connection_rank_examples': {
                  'machine_outgoing_first': [['A','AC:0',0],['B','BK:0',1],['C','CA:0',2],
                                             ['K','K0:0',3],['C','CB:0',4],['K','K1:0',5]],
                  'component_outgoing': [[f'{r}:{len(routes[r])-1}',ends[r][1],6+i]
                                          for i,r in enumerate(routes)],
                  'remaining_internal_channels':'分配互不相同且至少为12的接通序号；离线允许这种排列'},
              'unintended_channels': 0, 'L1_plus_L2': lengths_a['CA']+lengths_a['AC']}
    (OUT/'local_geometry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('lengths_by_cells','occupied_cells','formed_channels','L1_plus_L2')},ensure_ascii=False))


if __name__ == '__main__':
    main()
