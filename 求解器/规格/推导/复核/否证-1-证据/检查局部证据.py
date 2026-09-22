from pathlib import Path
import json
p=Path(__file__).resolve().parent
d=json.loads((p/'逐tick反例.json').read_text())
g=d['geometry']
occupied={}
def occupy(name,cells):
    for xy in cells:
        xy=tuple(xy)
        assert 0<=xy[0]<70 and 0<=xy[1]<70,(name,xy)
        assert xy not in occupied,(name,occupied.get(xy),xy)
        occupied[xy]=name
for m in g['machines']:
    occupy(m['id'],[(x,y) for x in range(m['x'],m['x']+m['w']) for y in range(m['y'],m['y']+m['h'])])
occupy('D',[(g['splitter']['x'],g['splitter']['y'])])
occupy('G',[(g['gate']['x'],g['gate']['y'])])
occupy('seed_belts',g['seed_belts'])
occupy('crusher_belts',g['crusher_belts'])
def adjacent_chain(cells):
    for a,b in zip(cells,cells[1:]):
        assert abs(a[0]-b[0])+abs(a[1]-b[1])==1,(a,b)
adjacent_chain([[21,12],[22,12]]+g['seed_belts']+[[11,12]])
adjacent_chain([[16,12]]+g['crusher_belts']+[[16,8]])
adjacent_chain([[15,12],[16,12],[17,12]])
assert g['seed_belts'][0]==[23,12]
assert g['gate']['input']=='west' and g['gate']['output']=='east'
pole=next(m for m in g['machines'] if m['id']=='power')
cx,cy=pole['x']+1,pole['y']+1
for m in g['machines']:
    if m['id']=='power':
        continue
    assert max(m['x'],cx-6)<min(m['x']+m['w'],cx+6)
    assert max(m['y'],cy-6)<min(m['y']+m['h'],cy+6)
rows=d['rows']
intakes=[r['tick'] for r in rows if r['gate_seed_intake']]
assert intakes==[0,5]
for r in rows:
    t=r['tick']
    assert r['delta_plant_plus_seed_count']==r['S_completed_since_start']-r['C_completed_since_start']
    assert r['S_output_before_cache_flush']==50-sum(q['gate_seed_intake'] for q in rows if q['tick']<=t)
    assert r['S_old_cache_flushed']==(50-r['S_output_before_cache_flush']>=2)
    assert r['S_output_after_cache_flush']==r['S_output_before_cache_flush']+(2 if r['S_old_cache_flushed'] else 0)
assert rows[4]['delta_plant_plus_seed_count']==-4
assert rows[5]['delta_plant_plus_seed_count']==-5
assert rows[5]['S_new_manufacture_started']
assert 2*rows[-1]['C_completed_since_start']<=50
msg=('PASS: local footprints within 70x70; no overlap; indicated port-neighbor paths contiguous; '
     'three manufacturing units overlap power coverage; gate count and 5-tick spacing consistent; '
     'batch-release and inventory arithmetic consistent.\n'
     'SCOPE: hand-derived trace checks only. No kernel simulation; no proof of complete-base feasibility or final periodic yield.\n')
with (p/'局部检查.log').open('x') as f:
    f.write(msg)
print(msg,end='')
