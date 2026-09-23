#!/usr/bin/env python3
"""Round 68: independent integer reconstruction, no derivation-script imports.

Coordinates and dimensions come from the three formal text files. Proof JSON
is untrusted input: domains, projection options and DP frontiers are rebuilt.
All writes are confined to this script's directory. Standard library only.
"""
from pathlib import Path
from collections import defaultdict, Counter
from fractions import Fraction as F
from itertools import product
import hashlib
import json
import re
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SRC = OUT.parent / '推导66'
FORMAL = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']
PROOFS = ['power_certificates.json', 'edge_integer_certificate.json',
          'joint17_integer_certificate.json', 'joint17_j_certificate.json']

def digest(p):
    data = p.read_bytes()
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')

def meet(a, b):
    x,y,w,h = a; u,v,s,t = b
    return x < u+s and u < x+w and y < v+t and v < y+h

def cells(r):
    x,y,w,h = r
    return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}

def hole(b):
    return (49,b,21,53)

def available(x,y,b):
    return 1 <= x <= 69 and 1 <= y <= 69 and not (x >= 49 and b <= y < b+53)

def edge_pole(x,y):
    return x in (1,68) or y in (1,68)

def loss(b,x,y,cap):
    # Merge applicable bounds by maximum, never by summation.
    occupied = (x in (1,68)) + (y in (1,68))
    result = max(23-min(23,cap), (0,9,15)[occupied])
    gaps=[]
    if x+2 <= 49 and y-5 >= b and y+7 <= b+53:
        gaps.append(49-x-2)
    if y+2 <= b and x-5 >= 49 and x+7 <= 70:
        gaps.append(b-y-2)
    if y >= b+53 and x-5 >= 49 and x+7 <= 70:
        gaps.append(y-b-53)
    for g in gaps:
        if 0 <= g <= 6:
            result = max(result, (10,9,9,6,5,4,1)[g])
    return result

def verify_power():
    records = json.loads((SRC/PROOFS[0]).read_text())
    assert set(records)=={'9','17'}
    powers={}; summary={}; center_count=0
    for b in (9,17):
        domain={(x,y) for x in range(1,69) for y in range(1,69)
                if not meet((x,y,2,2),hole(b))}
        rows=records[str(b)]
        assert len(rows)==len(domain)==len({(r['x'],r['y']) for r in rows})
        assert {(r['x'],r['y']) for r in rows} == domain
        powers[b]={}
        for r in rows:
            p,q = r['x'],r['y']
            covered=set()
            for x,y,w,h in r['tiles']:
                assert all(type(n) is int for n in (x,y,w,h))
                assert 1 <= w <= 3 and 1 <= h <= 3
                covered.update(cells((x,y,w,h)))
            assert r['cap'] == min(23,len(r['tiles']))
            # Enumeration deliberately extends beyond every potentially
            # intersecting block; intersection is checked as occupied cells.
            power_cells=cells((p-5,q-5,12,12))
            centers=set()
            for x in range(max(2,p-8),min(68,p+9)+1):
                for y in range(max(2,q-8),min(68,q+9)+1):
                    block=(x-1,y-1,3,3)
                    if meet(block,hole(b)) or meet(block,(p,q,2,2)):
                        continue
                    if cells(block) & power_cells:
                        centers.add((x,y))
            assert centers <= covered, (b,p,q,centers-covered)
            center_count += len(centers)
            powers[b][p,q]=loss(b,p,q,r['cap'])
        summary[str(b)]={'poles':len(domain),'loss_histogram':dict(sorted(Counter(powers[b].values()).items()))}
    summary['center_checks']=center_count
    summary['strip_minimum_loss']={}
    for label, predicate in [('lower',lambda x,y: x>=49 and y+1<=8),
                             ('upper',lambda x,y: x>=49 and y>=62)]:
        group=[v for (x,y),v in powers[9].items() if predicate(x,y)]
        raw=[23-r['cap'] for r in records['9'] if predicate(r['x'],r['y'])]
        summary['strip_minimum_loss'][label]={'count':len(group),'minimum':min(group),'group_cover_only_minimum':min(raw)}
        assert min(group)==min(raw)==7
    summary['turning_poles']={str(p):powers[17][p] for p in [(47,68),(68,15)]}
    assert set(summary['turning_poles'].values())=={15}
    save('power.json',summary)
    return powers,summary

# Body: (x,y,w,h,kind,axis). axis=0: port faces left/right;
# axis=1: bottom/top. For core this is the output axis.
def ports(body):
    x,y,w,h,k,axis=body
    if k=='P': return []
    if axis==0:
        faces=[[(x-1,y+j) for j in range(h)],[(x+w,y+j) for j in range(h)]]
        other=[[(x+i,y-1) for i in range(w)],[(x+i,y+h) for i in range(w)]]
    else:
        faces=[[(x+i,y-1) for i in range(w)],[(x+i,y+h) for i in range(w)]]
        other=[[(x-1,y+j) for j in range(h)],[(x+w,y+j) for j in range(h)]]
    if k=='C':
        return [([s[i] for i in (1,4,7)],3) for s in faces] + [([p for s in other for p in s[1:8]],2)]
    return [(s,1) for s in faces]

def viable(body,b,obstacle=None):
    if obstacle is not None and meet(body[:4],obstacle): return False
    return all(sum(available(x,y,b) and (obstacle is None or (x,y) not in cells(obstacle))
                   for x,y in face)>=need for face,need in ports(body))

def bodies(b):
    result=[]
    types=[(3,3,'M',0),(3,3,'M',1),(5,5,'M',0),(5,5,'M',1),
           (6,4,'M',1),(4,6,'M',0),(9,9,'C',0),(9,9,'C',1),(2,2,'P',0)]
    for w,h,k,axis in types:
        for x in range(1,71-w):
            for y in range(1,71-h):
                body=(x,y,w,h,k,axis)
                if not meet(body[:4],hole(b)) and viable(body,b):
                    result.append(body)
    return result

# Line = (horizontal?, fixed coordinate, start, exclusive end).
def line_cells(line):
    horiz,fixed,start,end=line
    return [(t,fixed) if horiz else (fixed,t) for t in range(start,end)]

def project(body,line):
    x,y,w,h,k,axis=body; horiz,fixed,start,end=line
    lo,hi=(x,x+w) if horiz else (y,y+h)
    normal_low,normal_high=(y,y+h) if horiz else (x,x+w)
    if not normal_low <= fixed < normal_high or lo>=end or hi<=start: return None
    a,z=max(lo,start)-start,min(hi,end)-start
    return a,z,('Z' if lo<start or hi>end else k)

def strip_forbidden(body,branch):
    x,y,w,h,k,axis=body
    if branch=='no_lower_pole': return x>=49 and y+h<=9
    if branch=='no_upper_pole': return x>=49 and y>=62
    return False

def branch_bodies(b,all_bodies,power,branch):
    if branch=='all': return all_bodies
    pp=[(x-5,y-5,12,12) for (x,y),v in power.items()
        if v<=13 and not strip_forbidden((x,y,2,2,'P',0),branch)]
    return [body for body in all_bodies if
            (body[4]=='P' and not strip_forbidden(body,branch)) or
            (body[4]=='C') or
            (body[4]=='M' and any(meet(body[:4],area) for area in pp))]

def options_for(b,items,power,line,fixed=(),excluded=(),with_j=False):
    n=line[3]-line[2]
    options=[set() for _ in range(n)]
    gaps=[int(available(x,y,b)) for x,y in line_cells(line)]
    fixed_cells=set().union(*(cells(r) for r in fixed)) if fixed else set()
    for i,p in enumerate(line_cells(line)):
        if p in fixed_cells: gaps[i]=None
    for body in items:
        if body[:4] in excluded: continue
        pr=project(body,line)
        if pr is None: continue
        a,z,kind=pr
        if any(v is None for v in gaps[a:z]): continue
        x,y,w,h,k,axis=body
        c=int(k=='C'); p=int(k=='P'); l=power[x,y] if p else 0
        entry=(z,kind,c,p,l)+((-2*int(p and edge_pole(x,y)),) if with_j else ())
        options[a].add(entry)
    for rect in fixed:
        pr=project((*rect,'P',0),line)
        if pr is not None:
            a,z,_=pr
            options[a].add((z,'P',0,0,0)+((0,) if with_j else ()))
    return [sorted(s) for s in options],gaps

FORBIDDEN={('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}

def pareto(table):
    # Keep exact core and pole counts. Discard only greater loss with cost >=.
    groups=defaultdict(list)
    for (c,p,l),v in table.items(): groups[c,p].append((l,v))
    answer={}
    for (c,p),entries in groups.items():
        best=10**9
        for l,v in sorted(entries):
            if v<best:
                answer[c,p,l]=v; best=v
    return answer

def sequence_dp(opts,gaps):
    # No pruning at internal positions: full exact reachable state table.
    states=[{} for _ in range(len(opts)+1)]
    states[0][('',0,0,0)]=0
    for at in range(len(opts)):
        for (last,c,p,l),value in list(states[at].items()):
            if gaps[at] is not None:
                key=('',c,p,l); v=value+gaps[at]
                states[at+1][key]=min(states[at+1].get(key,10**9),v)
            for opt in opts[at]:
                end,kind,dc,dp,dl=opt[:5]
                if (last,kind) in FORBIDDEN: continue
                if c+dc>1 or p+dp>12 or l+dl>59: continue
                key=(kind,c+dc,p+dp,l+dl); v=value+(opt[5] if len(opt)==6 else 0)
                states[end][key]=min(states[end].get(key,10**9),v)
    table={}
    for (_,c,p,l),v in states[-1].items():
        key=(c,p,l);table[key]=min(table.get(key,10**9),v)
    return pareto(table)

def join(tables):
    current={(0,0,0):0}
    for table in tables:
        nxt={}
        for (c,p,l),v in current.items():
            for (d,q,m),w in table.items():
                if c+d<=1 and p+q<=12 and l+m<=59:
                    key=(c+d,p+q,l+m)
                    nxt[key]=min(nxt.get(key,10**9),v+w)
        current=pareto(nxt)
    return current

def minimum(table,P,spent_p=0,spent_loss=0):
    return min(v for (c,p,l),v in table.items() if p+spent_p<=P and l+spent_loss<=23*P-217)

def check_table(opts,gaps,entry):
    assert opts == entry['options'], ('options differ',next(((i,a,b) for i,(a,b) in enumerate(zip(opts,entry['options'])) if a!=b),None))
    assert gaps == entry['gaps']
    actual=sequence_dp(opts,gaps)
    expected={tuple(k):v for k,v in entry['frontier']}
    assert actual==expected, ('frontier differs',set(actual.items())-set(expected.items()),set(expected.items())-set(actual.items()))
    return actual

def check_adjacencies(b,items,lines):
    tested=0
    for line in lines:
        starts=defaultdict(list); ends=defaultdict(list)
        for body in items:
            pr=project(body,line)
            if pr is not None and pr[2]!='Z':
                a,z,k=pr; starts[a].append((k,body)); ends[z].append((k,body))
        for t,lefts in ends.items():
            for k,a in lefts:
                for k2,z in starts[t]:
                    if (k,k2) not in FORBIDDEN: continue
                    tested+=1
                    assert meet(a[:4],z[:4]) or not viable(a,b,z[:4]) or not viable(z,b,a[:4]), (line,a,z)
    return tested

def edges(powers,all_bodies):
    cert=json.loads((SRC/PROOFS[1]).read_text())
    expected_cases={(9,'all'),(17,'all'),(9,'no_lower_pole'),(9,'no_upper_pole')}
    assert len(cert)==len(expected_cases) and {(c['b'],c['branch']) for c in cert}==expected_cases
    result=[]; counters={'option_sets':0,'frontiers':0,'adjacency_pairs':0}
    tables_by_case={}
    for case in cert:
        b,branch=case['b'],case['branch']; power=powers[b]
        items=branch_bodies(b,all_bodies[b],power,branch)
        tables={}
        expected_lines={('E',True,False),('N',True,False),('W',False,False),('S',False,False)}
        if b==9: expected_lines.add(('N',False,False))
        if b==9 and branch=='all': expected_lines |= {('E',True,True),('N',True,True)}
        assert len(case['lines'])==len(expected_lines)
        assert {(v['side'],v['outer'],v['corner']) for v in case['lines']}==expected_lines
        for entry in case['lines']:
            side,outer,corner=entry['side'],entry['outer'],entry['corner']
            if outer:
                line=(side=='N',69,1,70)
            elif side=='W': line=(False,48,b,b+53)
            elif side=='S': line=(True,b-1,49,70)
            else: line=(True,b+53,49,70)
            fixed=((68,68,2,2),) if corner else ()
            excluded=((68,68,2,2),) if outer else ()
            opts,gaps=options_for(b,items,power,line,fixed,excluded)
            # Normalize tuple representation for exact certificate comparison.
            opts=[[list(v) for v in s] for s in opts]
            tables[side,outer,corner]=check_table(opts,gaps,entry)
            counters['option_sets']+=sum(map(len,opts)); counters['frontiers']+=1
        baseX=join([tables['E',True,False],tables['N',True,False]])
        Y=join([t for (s,o,c),t in tables.items() if not o])
        cornerX=None
        if ('E',True,True) in tables:
            cornerX=join([tables['E',True,True],tables['N',True,True]])
        for P in ((10,11,12) if branch=='all' else (10,)):
            X=minimum(baseX,P)
            if cornerX is not None and power[68,68]<=23*P-217:
                X=min(X,minimum(cornerX,P,1,power[68,68]))
            ymin=minimum(Y,P)
            allowance=187-16*P+2*((23*P-217)//9)
            result.append(dict(b=b,branch=branch,P=P,X=X,Y=ymin,allowance=allowance,excess=X+ymin-allowance))
        tables_by_case[b,branch]=tables
    for b in (9,17):
        lines=[(False,69,1,70),(True,69,1,70),(False,48,b,b+53),(True,b-1,49,70)]
        if b==9:lines.append((True,62,49,70))
        counters['adjacency_pairs']+=check_adjacencies(b,all_bodies[b],lines)
    # Verify independent-budget X and Y never count one body's resources twice.
    # The only X overlap at b=9 is explicitly handled by the corner flag.
    for b in (9,17):
        xlines=[(False,69,1,70),(True,69,1,70)]
        ylines=[(False,48,b,b+53),(True,b-1,49,70)]
        if b==9: ylines.append((True,62,49,70))
        mx={r[:4] for r in all_bodies[b] if sum(project(r,l) is not None for l in xlines)>1}
        my={r[:4] for r in all_bodies[b] if sum(project(r,l) is not None for l in ylines)>1}
        assert mx==({(68,68,2,2)} if b==9 else set())
        assert not my
    save('edge_results.json',{'results':result,**counters})
    return result,counters

def joint(powers,all_bodies):
    lines=[(False,69,1,17),(True,69,1,49),(False,48,17,70),(True,16,49,70)]
    turns=[(47,68,2,2),(68,15,2,2)]
    multi={body[:4] for body in all_bodies[17] if sum(project(body,l) is not None for l in lines)>1}
    assert multi==set(turns), multi
    out={}; counts=0
    for jflag,file in [(False,PROOFS[2]),(True,PROOFS[3])]:
        cert=json.loads((SRC/file).read_text())
        assert len(cert['cases'])==4 and {tuple(c['mask']) for c in cert['cases']}==set(product((0,1),repeat=2))
        expected_pairs={(P,mask) for P in (10,11,12) for mask in product((0,1),repeat=2)
                        if 15*sum(mask)<=23*P-217}
        assert len(cert['results'])==len(expected_pairs)
        assert {(r['P'],tuple(r['corner_mask'])) for r in cert['results']}==expected_pairs
        results=[]
        for case in cert['cases']:
            mask=case['mask']; fixed=tuple(r for r,v in zip(turns,mask) if v)
            spent_loss=sum(powers[17][r[0],r[1]] for r in fixed)
            assert spent_loss==case['corner_loss']
            tables=[]
            assert len(case['lines'])==len(lines)
            assert [r['line'] for r in case['lines']]==[
                ['E',False,69,1,17],['N',True,69,1,49],
                ['W',False,48,17,70],['S',True,16,49,70]]
            for line,entry in zip(lines,case['lines']):
                opts,gaps=options_for(17,all_bodies[17],powers[17],line,fixed,turns,jflag)
                opts=[[list(v) for v in s] for s in opts]
                tables.append(check_table(opts,gaps,entry)); counts+=1
            merged=join(tables)
            for P in (10,11,12):
                budget=23*P-217
                if spent_loss>budget:
                    results.append({'P':P,'mask':mask,'excluded_by_loss':spent_loss});continue
                if not jflag:
                    value=minimum(merged,P,len(fixed),spent_loss)
                else:
                    values=[]
                    for (c,p,l),v in merged.items():
                        if p+len(fixed)>P or l+spent_loss>budget:continue
                        # Omitted boundary poles: distinct from all counted poles.
                        omitted=min(P-p-len(fixed),(budget-l-spent_loss)//9)
                        values.append(16*P+v-2*len(fixed)-2*omitted)
                    value=min(values)
                results.append({'P':P,'mask':mask,'value':value})
                original=next(r for r in cert['results'] if r['P']==P and r['corner_mask']==mask)
                assert value==original['min_S' if jflag else 'XY']
        out['S' if jflag else 'XY']=results
    out['multi_line_bodies']=sorted(multi);out['checked_frontiers']=counts
    save('joint_results.json',out)
    return out

def accounting():
    raw=(ROOT/FORMAL[0]).read_text().split('配方\n',1)[1]
    rx=[];machine=None
    for line in raw.splitlines():
        line=line.strip()
        if not line:continue
        if '→' not in line:machine=line;continue
        ingredients,tail=line.split('→'); products,duration=tail.split('，')
        def parse(s):return {name:int(n) for n,name in re.findall(r'(\d+)\s+([^\s＋]+)',s.strip())}
        rx.append((machine,parse(ingredients),parse(products),int(re.search(r'\d+',duration).group())))
    kinds=sorted({k for _,a,z,t in rx for k in a|z});assert len(rx)==18 and len(kinds)==19
    K={'源矿','蓝铁矿','蓝铁块','蓝铁粉末','源石粉末'}
    record=[];caps=defaultdict(lambda:F(0))
    for m,a,z,t in rx:
        ki=sum(v for k,v in a.items() if k in K); ko=sum(v for k,v in z.items() if k in K)
        caps[m]=max(caps[m],F(ki,t))
        assert ko-ki == (-2 if m=='研磨机' and ('蓝铁粉末' in a or '源石粉末' in a) else 0)
        record.append({'machine':m,'input':a,'output':z,'ticks':t,'K_net':ko-ki})
    assert caps['粉碎机']==caps['精炼炉']==1 and caps['研磨机']==2
    assert all(v==0 for m,v in caps.items() if m not in ('粉碎机','精炼炉','研磨机'))
    # Solve all 19 balances from scratch, with refinery recycle zero and two
    # ore supplies as unknowns. Exact product delivery rates are formal facts.
    variables=len(rx)+2
    mat=[]
    for kind in kinds:
        row=[F(z.get(kind,0)-a.get(kind,0)) for m,a,z,t in rx]
        row += [F(kind=='源矿'),F(kind=='蓝铁矿')]
        row += [F(3,5) if kind=='高容谷地电池' else F(11,20) if kind=='精选荞愈胶囊' else F(0)]
        mat.append(row)
    recycle=next(i for i,(m,a,z,t) in enumerate(rx) if m=='精炼炉' and '蓝铁粉末' in a)
    mat.append([F(i==recycle) for i in range(variables)]+[F(0)])
    for col in range(variables):
        pivot=next(r for r in range(col,len(mat)) if mat[r][col])
        mat[col],mat[pivot]=mat[pivot],mat[col]
        div=mat[col][col]; mat[col]=[v/div for v in mat[col]]
        for r in range(len(mat)):
            if r!=col:
                factor=mat[r][col]
                mat[r]=[v-factor*u for v,u in zip(mat[r],mat[col])]
    rates=[mat[i][-1] for i in range(variables)]
    assert all(v>=0 for v in rates)
    work=defaultdict(lambda:F(0))
    for rate,(m,a,z,t) in zip(rates,rx):work[m]+=rate*t
    minimum={m:-(-w.numerator//w.denominator) for m,w in work.items()}
    assert sum(minimum.values())==217
    gaps=range(0,70,3)
    configurations=[(left,bottom) for left in gaps for bottom in gaps if left==0 or bottom==0]
    def sources(g):
        starts=list(range(0,g,3))+list(range(g+1,70,3))
        assert len(starts)==23
        return [s+1 for s in starts]
    assert len(configurations)==47
    assert {sum(s>=49 for s in sources(bottom)) for left,bottom in configurations}=={7}
    result={'recipes':record,'items':kinds,'rates':[str(v) for v in rates],
            'kappa':{m:str(v) for m,v in caps.items()},'minimum_machine_counts':minimum,
            'boundary_configurations':len(configurations),'sources_in_49_69':7,
            'cut_bounds':{str(b):{'H':b-1,'D_upper_constant':b-8,'U_upper_constant':(b-8)//2} for b in (6,7,9,17)}}
    save('accounting.json',result)
    return result

def cut_geometry():
    """Look for a legal body crossing a finite cut only partially in height.

    This domain deliberately omits power and port restrictions, so every legal
    manufacturing/core/pole placement is included. No boundary-source gap can
    fit any of these bodies (minimum width 2).
    """
    dimensions=[(3,3),(5,5),(6,4),(4,6),(9,9),(2,2)]
    summary=[]
    for b in (6,7,9,17):
        rects=[(x,y,w,h) for w,h in dimensions for x in range(1,71-w)
               for y in range(1,71-h) if not meet((x,y,w,h),hole(b))]
        segments=[(1,b)]
        if b==9: segments.append((62,70))
        for low,high in segments:
            anchors=range(49,70) if b in (9,17) else [49]
            for a in anchors:
                crossed=[]
                for r in rects:
                    x,y,w,h=r
                    if x<=a-1 and x+w>a and y<high and y+h>low:
                        assert low<=y and y+h<=high, (b,a,low,high,r)
                        crossed.append(r)
                summary.append({'b':b,'rows':[low,high-1],'a':a,'crossing_bodies':len(crossed)})
    # Adjacent 3x3 centers in any valid group overlap, including boundary offsets.
    differences=list(product(range(-2,3),repeat=2))
    assert all(meet((0,0,3,3),(dx,dy,3,3)) for dx,dy in differences)
    # Explicit finite partition for the P=10 case: lower absent, or lower
    # present and upper absent. Both present violates loss >=14 >13.
    truth=[]
    for lower,upper in product((False,True),repeat=2):
        if lower and upper: label='excluded: minimum loss 14 exceeds 13'
        elif not lower: label='lower absent'
        else: label='lower present, upper absent'
        truth.append({'lower':lower,'upper':upper,'case':label})
    result={'cuts':summary,'cut_count':len(summary),'all_material_cut_count':sum(r['b'] in (9,17) for r in summary),
            'partial_height_counterexamples':0,'center_difference_pairs':len(differences),'P10_partition':truth}
    assert result['all_material_cut_count']==63
    save('cut_geometry.json',result)
    return result

def main():
    started=time.monotonic()
    paths=[ROOT/n for n in FORMAL]+[SRC/n for n in PROOFS]
    before={str(p.relative_to(ROOT)):digest(p) for p in paths}
    powers,power_summary=verify_power();print('power PASS',power_summary['center_checks'],flush=True)
    all_bodies={b:bodies(b) for b in (9,17)}
    print('body domains', {b:len(v) for b,v in all_bodies.items()},flush=True)
    edge,counters=edges(powers,all_bodies);print('edges PASS',edge,flush=True)
    jj=joint(powers,all_bodies);print('joint PASS',jj['S'],flush=True)
    aa=accounting();print('accounting PASS',aa['rates'],flush=True)
    cuts=cut_geometry();print('cut geometry PASS',cuts['cut_count'],flush=True)
    after={str(p.relative_to(ROOT)):digest(p) for p in paths}
    assert before==after
    save('input_manifest.json',before)
    summary={'status':'PASS','seconds':time.monotonic()-started,'power':power_summary,
             'body_domains':{b:len(v) for b,v in all_bodies.items()},
             'edges':edge,'certificate_counts':counters,'joint':jj,
             'cut_geometry_summary':{k:v for k,v in cuts.items() if k!='cuts'},
             'formal_inputs_unchanged':True,'imports_derivation_scripts':False,'uses_solver':False}
    save('results.json',summary)
    print('PASS',round(summary['seconds'],3),flush=True)

if __name__=='__main__': main()
