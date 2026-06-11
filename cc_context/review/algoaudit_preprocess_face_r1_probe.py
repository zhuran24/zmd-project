#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from pathlib import Path

from src.placement.placement_generator import GRID_W, GRID_H, load_templates, generate_all_pools

DIR = {'N': (0,1), 'S': (0,-1), 'E': (1,0), 'W': (-1,0)}

def front(p):
    dx, dy = DIR[p['dir']]
    return (p['x'] + dx, p['y'] + dy)

def in_grid(c):
    x,y=c
    return 0 <= x < GRID_W and 0 <= y < GRID_H

def main():
    pools = generate_all_pools(load_templates())
    print('pool_counts')
    for k in sorted(pools):
        print(f'  {k}: {len(pools[k])}')
    total=sum(len(v) for v in pools.values())
    print(f'total: {total}')

    geometry_errors=[]
    front_oog=[]
    protocol_ports=[]
    for tpl, poses in pools.items():
        for idx, pose in enumerate(poses):
            occ=[tuple(c) for c in pose.get('occupied_cells', [])]
            if len(occ) != len(set(occ)):
                geometry_errors.append((tpl, idx, pose['pose_id'], 'duplicate occupied'))
            for c in occ:
                if not in_grid(c):
                    geometry_errors.append((tpl, idx, pose['pose_id'], f'occupied out of grid {c}'))
            xs=[c[0] for c in occ]; ys=[c[1] for c in occ]
            if xs and ys:
                w=max(xs)-min(xs)+1; h=max(ys)-min(ys)+1
                if len(occ) != w*h:
                    geometry_errors.append((tpl, idx, pose['pose_id'], f'not full rectangle len={len(occ)} box={w}x{h}'))
            for side in ('input_port_cells','output_port_cells'):
                for p in pose.get(side, []) or []:
                    f=front(p)
                    if not in_grid(f):
                        front_oog.append((tpl, idx, pose['pose_id'], side, (p['x'],p['y'],p['dir']), f))
                    # Port must be adjacent outside bbox, direction away.
                    if occ:
                        x0,x1=min(xs),max(xs); y0,y1=min(ys),max(ys)
                        px,py,di=p['x'],p['y'],p['dir']
                        ok = ((di=='N' and py==y1+1 and x0<=px<=x1) or
                              (di=='S' and py==y0-1 and x0<=px<=x1) or
                              (di=='W' and px==x0-1 and y0<=py<=y1) or
                              (di=='E' and px==x1+1 and y0<=py<=y1))
                        if not ok:
                            geometry_errors.append((tpl, idx, pose['pose_id'], f'port not outward-adjacent: {side} {p} bbox={(x0,y0,x1,y1)}'))
            if tpl == 'protocol_storage_box':
                ins=pose.get('input_port_cells') or []
                outs=pose.get('output_port_cells') or []
                if ins or outs:
                    protocol_ports.append((tpl, idx, pose['pose_id'], len(ins), len(outs)))
    print(f'geometry_errors: {len(geometry_errors)}')
    for e in geometry_errors[:5]: print('  ', e)
    bytpl=Counter(x[0] for x in front_oog)
    print(f'front_oog_ports: {len(front_oog)}')
    for tpl,cnt in sorted(bytpl.items()): print(f'  {tpl}: {cnt}')
    for e in front_oog[:8]: print('  sample', e)
    print(f'protocol_storage_box_physical_port_poses: {len(protocol_ports)}')
    for e in protocol_ports[:4]: print('  sample', e)

    # Expected exact current generator external hash, compact format used by writer.
    text=json.dumps({'facility_pools': pools}, ensure_ascii=False, separators=(',', ':'))
    import hashlib
    print(f'candidate_compact_sha256: {hashlib.sha256(text.encode()).hexdigest()}')
    print(f'candidate_compact_bytes: {len(text.encode())}')

if __name__ == '__main__':
    main()
