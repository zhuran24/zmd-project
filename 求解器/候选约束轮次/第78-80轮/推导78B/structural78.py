"""Enumerate exact slack constants, source patterns, and necessary pole domains.
The coordinate lists are allowed domains, not layout constructions.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
import json,re
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3]
def square(x,y,w,h):return {(a,b) for a in range(x,x+w) for b in range(y,y+h)}
def tiling(g):
    a=[i for i in range(70) if i!=g]
    return [a[i+1] for i in range(0,69,3)]
def main():
    text=(ROOT/'求解约束.txt').read_text()
    line=next(l for l in text.splitlines() if l.startswith('机型下限：'))
    counts={k:int(v) for k,v in re.findall(r'(粉碎机|精炼炉|研磨机|塑形机|配件机|种植机|采种机|封装机|灌装机)\s*≥(\d+)',line)}
    area=sum(n*({'采种机':25,'种植机':25,'研磨机':24,'封装机':24,'灌装机':24}.get(k,9)) for k,n in counts.items())
    assert area==3291 and sum(counts.values())==217
    fixed={'source_ore_rates':[34,18],'input_channels':[68,51,95,11,6,32,16,15,11],
      'output_channels':[95,51,32,6,6,32,32,3,3]}
    assert sum(fixed['input_channels'])==305 and sum(fixed['output_channels'])==260
    distinct_fixed=area+9**2+2*23*3+10*2**2
    remainder=70**2-21*53-distinct_fixed
    weighted=json.loads((OUT/'weighted_account.json').read_text())
    assert remainder==weighted['exact_area']['transport_plus_empty']==237
    caps={tuple(v['p']):v['cap'] for v in json.loads((OUT/'capacities.json').read_text())}
    allowed=[];allp=set();sources=[]
    for g in range(0,70,3):
        for h in range(0,70,3):
            if min(g,h):continue
            la=[3*k+1+int(3*k>=g) for k in range(23)]
            ba=[3*k+1+int(3*k>=h) for k in range(23)]
            assert la==tiling(g) and ba==tiling(h)
            ore={(1,v) for v in la}|{(v,1) for v in ba}
            assert len(ore)==46
            source_count=sum(v>=49 for v in ba);assert source_count==7
            sources.append(dict(gaps=[g,h],ore=list(map(list,sorted(ore))),strip_sources=source_count))
            if not 0<max(g,h)<69:continue
            machine=square(1,g-1,3,3) if g else square(h-1,1,3,3)
            positions=[]
            for p,c in caps.items():
                if c<10 or not ((p[0]==1 and p[1] not in(1,68)) or (p[1]==1 and p[0] not in(1,68))):continue
                b=square(*p,2,2)
                if b&(ore|machine):continue
                positions.append(dict(p=list(p),cap=c));allp.add(p)
            allowed.append(dict(gaps=[g,h],small_machine_lower_left=[1,g-1] if g else [h-1,1],pole_positions=positions))
    byside={axis:sorted(p[1-axis] for p in allp if p[axis]==1) for axis in (0,1)}
    expected=[q for q in range(5,64) if q%3 in (0,2)]
    assert byside[0]==byside[1]==expected
    W=Counter([(69,y) for y in range(1,17)]+[(x,69) for x in range(1,49)]+[(48,y) for y in range(17,70)]+[(x,16) for x in range(49,70)])
    I={(1,y) for y in range(1,70)}|{(x,1) for x in range(2,70)}
    direction_domains=[]
    for pattern in sources:
        ore=set(map(tuple,pattern['ore']));U=I-ore;assert len(U)==91
        r=W.copy();r.update(U)
        assert max(r.values())==2
        assert sorted(c for c,k in r.items() if k==2)==[(1,69),(48,69),(69,1),(69,16)]
        direction_domains.append(dict(gaps=pattern['gaps'],inner_non_source_cells=len(U),max_charges_per_cell=max(r.values())))
    rates=[F(x) for x in (34,18,34,34,18)]+[F('31.5'),F(21),F(21),F(11),F(11),F(11),F(17),F(17),F(9),F('5.5'),F(6),F('5.5'),F('.6'),F('.55')]
    assert sum(rates)==F(6113,20)
    result=dict(machine_counts=counts,machine_area=area,total_machines=sum(counts.values()),transport_plus_empty=remainder,
      interface_baseline=52+sum(fixed['input_channels'])+sum(fixed['output_channels'])+2,
      input_output_counts=fixed,power_deficit_budget=23*10-sum(counts.values()),after_boundary_pole=13-10,
      source_patterns=sources,pole_patterns=allowed,pole_union=list(map(list,sorted(allp))),pole_union_size=len(allp),
      pole_range_by_side=byside,nonedge_cap20_count=sum(c>=20 and all(z not in (1,68) for z in p) for p,c in caps.items()),
      direction_domains=direction_domains,counted_edge_occurrences=sum(W.values()),counted_edge_cells=len(W),
      double_count_cells=[list(c) for c,k in W.items() if k==2],
      transport_flow_minimum=str(sum(rates)),active_transports=236,active_bridges_min=306-236,
      active_transport_slack=str(2*236-4-sum(rates)),cut_source_count=7,cut_height=16,cut_constant=16-7)
    (OUT/'structural.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in result.items() if k not in ('source_patterns','pole_patterns','direction_domains','pole_union')},flush=True)
if __name__=='__main__':main()
