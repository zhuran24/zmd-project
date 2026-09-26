"""Independent finite checks for the band, boundary arithmetic and two mandatory gaps."""
from pathlib import Path
from itertools import product
import json,math
OUT=Path(__file__).resolve().parent

def band_sources(g):
    covered=[];ports=[]
    for start in list(range(0,g,3))+list(range(g+1,70,3)):
        covered.extend(range(start,start+3));ports.append(start+1)
    assert len(covered)==69 and set(covered)==set(range(70))-{g}
    return ports

def band():
    cases=[]
    for gx,gy in product(range(0,70,3),repeat=2):
        if gx and gy:continue
        ores={(x,1) for x in band_sources(gx)}|{(1,y) for y in band_sources(gy)}
        assert len(ores)==46
        I={(1,y) for y in range(1,70)}|{(x,1) for x in range(1,70)}
        U=I-ores;possible=set()
        for x,y in product(range(1,68),repeat=2):
            if x>1 and y>1:continue
            b={(x+i,y+j) for i in range(3) for j in range(3)}
            if not b&ores:possible|=b&I
        assert len(U)==91 and len(possible)<=3
        for x,y in product(range(1,69),repeat=2):
            if x>1 and y>1:continue
            b={(x+i,y+j) for i in range(2) for j in range(2)}
            if not b&ores:assert len(b&I)<=2
        cases.append(dict(gap_x=gx,gap_y=gy,nonore=len(U),possible_large_unit_contact=len(possible)))
    assert len(cases)==47
    return cases

def local_at_point(w,h,point):
    rect={(x,y) for x in range(70-w,70) for y in range(70-h,70)}
    legal=[]
    for mw,mh,axis in ((3,3,0),(3,3,1),(5,5,0),(5,5,1),(6,4,1),(4,6,0)):
        for x in range(max(1,point[0]-mw+1),min(point[0],70-mw)+1):
            for y in range(max(1,point[1]-mh+1),min(point[1],70-mh)+1):
                body={(x+i,y+j) for i in range(mw) for j in range(mh)}
                if body&rect:continue
                if axis==0:sides=([(x-1,t) for t in range(y,y+mh)],[(x+mw,t) for t in range(y,y+mh)])
                else:sides=([(t,y-1) for t in range(x,x+mw)],[(t,y+mh) for t in range(x,x+mw)])
                if all(any(1<=a<=69 and 1<=b<=69 and (a,b) not in rect for a,b in s) for s in sides):
                    legal.append([x,y,mw,mh,axis])
    core=[]
    for x in range(max(1,point[0]-8),min(point[0],61)+1):
        for y in range(max(1,point[1]-8),min(point[1],61)+1):
            body={(x+i,y+j) for i in range(9) for j in range(9)}
            if body&rect:continue
            for axis in (0,1):
                ports=([(x-1,y+i) for i in (1,4,7)]+[(x+9,y+i) for i in (1,4,7)]) if axis==0 else ([(x+i,y-1) for i in (1,4,7)]+[(x+i,y+9) for i in (1,4,7)])
                if all(1<=a<=69 and 1<=b<=69 and (a,b) not in rect for a,b in ports):core.append([x,y,axis])
    return dict(point=point,active_manufacturing_options=legal,core_options=core)

def boundary():
    result=[]
    # Independent integer feasibility enumeration of m, c, t, X rather than ceil formula.
    for w,h in ((30,37),(37,30),(21,53),(53,21)):
        for right,top in product((False,True),repeat=2):
            L=138-(h if right else 0)-(w if top else 0)
            runs=2+int(right!=top)
            for extra in (0,1):
                tmax=extra*(1 if right and top else 2)
                minimum=None
                for gap in range(139):
                    if any(m<=gap+c+t+runs and 5*m+9*c+3*t+gap>=L
                        for c in range(2) for t in range(tmax+1) for m in range(47)):
                        minimum=gap;break
                result.append(dict(shape=[w,h],right=right,top=top,extra=extra,X_min=minimum))
    a=json.loads((OUT/'accounts_a.json').read_text())['budget']['boundary_bounds']
    lookup={(tuple(z['shape']),z['right'],z['top'],z['extra']):z['X_min'] for z in result}
    for z in a:assert lookup[tuple(z['shape']),z['right'],z['top'],z['exception']]==z['X_lower']
    return result

def power_domain():
    result=[]
    for typ in ('general_weight','edge_weight','edge_count'):
        a=json.loads((OUT/(typ+'_domain_a.json')).read_text());b=json.loads((OUT/(typ+'_domain_b.json')).read_text())
        def norm(xs):return {tuple(z['key']):(set(map(tuple,z['body'])),[set(map(tuple,s)) for s in z['sides']],z['weight']) for z in xs}
        assert norm(a)==norm(b)
        ra=json.loads((OUT/(typ+'_a.json')).read_text());rb=json.loads((OUT/(typ+'_b.json')).read_text())
        assert ra['status']=='INFEASIBLE' and rb['status']==2
        result.append(dict(model=typ,options=len(a),independent_domains_equal=True,both_infeasible=True,
            seconds_a=ra['seconds'],seconds_b=rb['seconds']))
    return result

def main():
    endpoints=[]
    for w,h in ((30,37),(37,30)):
        ps=[(69-w,69),(69,69-h)]
        checks=[local_at_point(w,h,p) for p in ps]
        assert all(not c['active_manufacturing_options'] and not c['core_options'] for c in checks)
        assert abs(ps[0][0]-ps[1][0])>=3 and abs(ps[0][1]-ps[1][1])>=3
        endpoints.append(dict(shape=[w,h],endpoints=checks,one_3x3_cannot_cover_both=True))
    data=dict(band=band(),boundary=boundary(),mandatory_gaps=endpoints,power=power_domain(),passes=True)
    (OUT/'geometry_check.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passes':True,'band_cases':len(data['band']),'boundary_cases':len(data['boundary']),
        'mandatory_gaps':endpoints,'power':data['power']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
