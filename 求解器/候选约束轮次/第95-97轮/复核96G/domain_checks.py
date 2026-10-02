"""Two direct domain checks, plus small integer consequences of the budgets."""
from pathlib import Path
from itertools import product
from fractions import Fraction
import json

OUT=Path(__file__).resolve().parent


def explicit_check():
    data=[]
    band={(1,y) for y in range(1,70)}|{(x,1) for x in range(1,70)}
    for gl in range(0,70,3):
        for gb in range(0,70,3):
            if gl and gb:
                continue
            sources=set()
            tiles=set()
            for vertical,gap in ((True,gl),(False,gb)):
                t=0
                while t<70:
                    if t==gap:
                        t+=1
                        continue
                    for j in range(3):
                        tiles.add((0,t+j) if vertical else (t+j,0))
                    sources.add((1,t+1) if vertical else (t+1,1))
                    t+=3
            assert len(sources)==46 and len(tiles)==138
            q=({(0,y) for y in range(70)}|{(x,0) for x in range(70)})-tiles
            assert len(q)==1
            candidates=[]
            for w,h in ((3,3),(5,5),(6,4),(4,6),(9,9)):
                starts={(1,y) for y in range(1,71-h)}|{(x,1) for x in range(1,71-w)}
                for x,y in starts:
                    body={(i,j) for i in range(x,x+w) for j in range(y,y+h)}
                    if not body&sources:
                        candidates.append([x,y,w,h,len(body&band)])
            assert len(candidates)<=1
            assert all(c[2:]==[3,3,3] for c in candidates)
            max_post=0
            for x,y in ({(1,y) for y in range(1,69)}|{(x,1) for x in range(1,69)}):
                body={(x+i,y+j) for i in (0,1) for j in (0,1)}
                if not body&sources:
                    max_post=max(max_post,len(body&band))
            corridor={}
            for a in (2,3):
                legal=[]
                for b in range(2,65):
                    for h in range(6,71-b):
                        m=sum((1,y) in sources for y in range(b,b+h))
                        e=1 if b+h==70 else 2
                        if m<=e*(a-1) and (a,b)!=(2,2):
                            legal.append((b,h,e))
                corridor[a]=dict(max_height=max(h for b,h,e in legal),
                                 top_max=max([h for b,h,e in legal if e==1],default=0),
                                 maximum_area=(70-a)*max(h for b,h,e in legal))
            data.append(dict(gaps=[gl,gb],q=list(next(iter(q))),body=candidates,
                             max_post=max_post,corridor=corridor))
    return data


def interval_check():
    rows=[]
    for gl,gb in [(0,g) for g in range(0,70,3)]+[(g,0) for g in range(3,70,3)]:
        axis=lambda g:[3*k+1+int(3*k>=g) for k in range(23)]
        assert len(axis(gl))==len(axis(gb))==23
        # Run lengths between full-rate ore cells. Only a noncorner gap
        # creates a run of three interior cells in the band.
        machine=[]
        for vertical,gap in ((True,gl),(False,gb)):
            points=axis(gap)
            for lo,hi in zip([0]+points,points+[70]):
                if hi-lo-1>=3:
                    assert hi-lo-1==3
                    machine.append([1,lo+1,3,3,3] if vertical else [lo+1,1,3,3,3])
        corridor={}
        for width in (1,2):
            hmax=topmax=0
            for low,high in product(range(2,65),range(7,70)):
                h=high-low+1
                if h<6 or (width==1 and low==2):
                    continue
                m=sum(low<=v<=high for v in axis(gl))
                if m<=(1+(high!=69))*width:
                    hmax=max(hmax,h)
                    if high==69:
                        topmax=max(topmax,h)
            corridor[width+1]=dict(max_height=hmax,top_max=topmax,maximum_area=(69-width)*hmax)
        q=[0,gl] if gl else [gb,0]
        rows.append(dict(gaps=[gl,gb],q=q,body=machine,max_post=2,corridor=corridor))
    return rows


def consequences():
    # Every value below comes from integer inequality evaluation.
    arithmetic=json.loads((OUT/'arithmetic_supports.json').read_text())
    omega=Fraction(arithmetic['omega'])
    at1110=[]
    for p in range(1,350):
        for j in range(p+1):
            if 23*p-10*j<217 or 54*p-25*j<520:
                continue
            budget=4639-4*1110-16*p+2*j
            if budget>=0:
                at1110.append([p,j,budget])
    names={'crush':'粉碎机','refine':'精炼炉','fit':'配件机','box':'协议储存箱',
           'shape':'塑形机','grind':'研磨机','pack':'封装机','fill':'灌装机',
           'plant':'种植机','seed':'采种机'}
    extra_first={}
    for m,name in names.items():
        footprint=25 if m in ('plant','seed') else 24 if m in ('grind','pack','fill') else 9
        table=arithmetic['weight_tables_twice'].get(m)
        delta=0
        if table:
            n=arithmetic['flows']['counts'][m]
            delta=Fraction(table[str(n+1)]-table[str(n)],2)
        extra_first[name]=omega+4*footprint+delta
    eligible=[]
    for p in range(10,15):
        for j in range(p+1):
            if 23*p-10*j<217 or 54*p-25*j<520:
                continue
            budget=4751-4*1110-16*p+2*j
            for name,cost in extra_first.items():
                if cost<=budget:
                    eligible.append([p,j,name,int(budget-cost)])
    generic=Fraction(arithmetic['ordinary_direction'])
    no_box=generic+4*46-90-91
    ceiling=lambda q:-(-q.numerator//q.denominator)
    return dict(at_1110=at1110,single_extra_remaining=eligible,
                transport_bounds={
                    'general_four_fixed':ceiling(generic/4),
                    'no_box_four_fixed':ceiling(no_box/4),
                    'no_box_q_transport':ceiling((no_box+4)/4)})


def main():
    a,b=explicit_check(),interval_check()
    normalize=lambda rows:{tuple(x['gaps']):x for x in rows}
    assert normalize(a)==normalize(b)
    summary=dict(patterns=len(a),body_candidates=sum(len(r['body']) for r in a),
                 max_body_band_cells=max([c[-1] for r in a for c in r['body']]),
                 max_post_band_cells=max(r['max_post'] for r in a),
                 corridor_max={a0:max(r['corridor'][a0]['max_height'] for r in a) for a0 in (2,3)},
                 corridor_top_max={a0:max(r['corridor'][a0]['top_max'] for r in a) for a0 in (2,3)},
                 near_band_max_area=max(c['maximum_area'] for r in a for c in r['corridor'].values()),
                 independent_routes_agree=True)
    result=dict(summary=summary,patterns=a,consequences=consequences())
    (OUT/'domain_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(summary=summary,consequences=result['consequences']),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
