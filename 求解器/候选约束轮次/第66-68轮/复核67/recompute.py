#!/usr/bin/env python3
"""Round 67 independent audit. Only stdlib; no derivation Python is loaded.

Coordinates of bodies are half-open rectangles. Certificate JSON is untrusted
input: power covers are checked against reconstructed cells, and edge options
and integer tables are reconstructed before comparing to the submitted data.
All output is confined to this script's directory.
"""
from pathlib import Path
from collections import defaultdict, Counter
from fractions import Fraction as F
from itertools import product
import hashlib
import json
import re
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SUBMITTED = HERE.parent / '推导66'
INPUT_NAMES = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt']

def read_json(name):
    return json.loads((SUBMITTED / name).read_text())

def save(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def overlap(a, b):
    x,y,w,h = a; u,v,s,t = b
    return x < u+s and u < x+w and y < v+t and v < y+h

def contains(r, x, y):
    a,b,w,h = r
    return a <= x < a+w and b <= y < b+h

def hole(b):
    return (49,b,21,53)

def legal_body(r, b):
    x,y,w,h = r
    return x >= 1 and y >= 1 and x+w <= 70 and y+h <= 70 and not overlap(r,hole(b))

def transport_cell(x,y,b):
    # Row/column 0 contain warehouses; the isolated single gap has no periodic
    # throughput. No assumptions about the other bodies or mandatory ore cells.
    return 1 <= x <= 69 and 1 <= y <= 69 and not contains(hole(b),x,y)

def sides(r, axis, offsets=None):
    x,y,w,h = r
    if axis == 'x':
        offsets = range(h) if offsets is None else offsets
        return [[(x-1,y+i) for i in offsets], [(x+w,y+i) for i in offsets]]
    offsets = range(w) if offsets is None else offsets
    return [[(x+i,y-1) for i in offsets], [(x+i,y+h) for i in offsets]]

def ports_valid(r, kind, axis, b, blocked=()):
    def good(c):
        return transport_cell(*c,b) and not any(contains(z,*c) for z in blocked)
    if kind == 'P':
        return True
    if kind == 'M':
        return all(any(good(c) for c in side) for side in sides(r,axis))
    return (all(good(c) for side in sides(r,axis,[1,4,7]) for c in side)
            and sum(good(c) for side in sides(r,'y' if axis == 'x' else 'x',range(1,8)) for c in side) >= 2)

def edge_count(r):
    x,y,w,h = r
    return sum((x == 1, y == 1, x+w == 70, y+h == 70))

def power_range(p):
    return p[0]-5,p[1]-5,12,12

def side_loss(p,b):
    x,y,w,h=p; a,c,W,H=hole(b); px,py,pw,ph=power_range(p)
    gaps=[]
    if py >= c and py+ph <= c+H:
        if x+w <= a: gaps.append(a-x-w)
        if x >= a+W: gaps.append(x-a-W)
    if px >= a and px+pw <= a+W:
        if y+h <= c: gaps.append(c-y-h)
        if y >= c+H: gaps.append(y-c-H)
    losses=[10,9,9,6,5,4,1]
    return max([0]+[losses[g] for g in gaps if 0 <= g <= 6])

def verify_power():
    submitted=read_json('power_certificates.json')
    assert set(submitted)=={'9','17'}
    losses={}; summary={}; center_count=0
    for b in (9,17):
        expected={(x,y) for x in range(1,69) for y in range(1,69) if legal_body((x,y,2,2),b)}
        entries=submitted[str(b)]
        assert len(entries)==len(expected)
        assert {(v['x'],v['y']) for v in entries}==expected
        costs={}; counts=Counter(); centers_total=0
        for e in entries:
            p=(e['x'],e['y'],2,2); groups=e['tiles']; covered=set()
            for x,y,w,h in groups:
                assert all(type(z) is int for z in (x,y,w,h)) and 1 <= w <= 3 and 1 <= h <= 3
                covered.update(product(range(x,x+w),range(y,y+h)))
            # Enumerate all possible centers in the whole base, bounding only
            # one axis for speed; rectangle intersection, not stored domains.
            centers={(x,y) for x in range(2,69) for y in range(max(2,p[1]-7),min(68,p[1]+8)+1)
                     if not overlap((x-1,y-1,3,3),hole(b)) and not overlap((x-1,y-1,3,3),p)
                     and overlap((x-1,y-1,3,3),power_range(p))}
            assert centers <= covered, (b,p,centers-covered)
            cap=min(23,len(groups))
            assert e['cap']==cap
            n=edge_count(p)
            loss=max(23-cap,15 if n>=2 else 9 if n else 0,side_loss(p,b))
            costs[p[:2]]=loss
            counts[cap]+=1; centers_total+=len(centers)
        losses[b]=costs
        summary[str(b)]={'pole_count':len(costs),'center_count':centers_total,'cap_histogram':dict(sorted(counts.items()))}
        center_count+=centers_total
    for name,pred in [('lower',lambda x,y: x>=49 and y+2<=9),('upper',lambda x,y: x>=49 and y>=62)]:
        entries=[e for e in submitted['9'] if pred(e['x'],e['y'])]
        summary[name]={'count':len(entries),'min_group_loss':min(23-e['cap'] for e in entries),
                       'min_combined_loss':min(losses[9][e['x'],e['y']] for e in entries)}
    summary['b17_turn_poles']={str(k):losses[17][k] for k in [(47,68),(68,15)]}
    for k in [(47,68),(68,15)]:
        entry=next(e for e in submitted['17'] if (e['x'],e['y'])==k)
        assert len(entry['tiles'])==entry['cap']==8 and losses[17][k]==15
    summary['total_centers']=center_count
    save('power_audit.json',summary)
    print('POWER',summary,flush=True)
    return losses

def all_bodies(b, losses, branch='all'):
    # Body + M/C/P + port axis. Enumerating the whole base prevents guessing
    # which anchors can touch a particular boundary.
    specs=[(3,3,'M','x'),(3,3,'M','y'),(5,5,'M','x'),(5,5,'M','y'),
           (6,4,'M','y'),(4,6,'M','x'),(9,9,'C','x'),(9,9,'C','y'),(2,2,'P','')]
    def banned(r):
        x,y,w,h=r
        return x>=49 and ((branch=='no_lower_pole' and y+h<=b)
                          or (branch=='no_upper_pole' and y>=b+53))
    allowed_poles=[(x,y,2,2) for (x,y),L in losses.items() if L<=13 and not banned((x,y,2,2))]
    bodies=[]
    for w,h,k,axis in specs:
        for x in range(1,71-w):
            for y in range(1,71-h):
                r=(x,y,w,h)
                if not legal_body(r,b) or not ports_valid(r,k,axis,b): continue
                if k=='P' and banned(r): continue
                if k=='M' and branch!='all' and not any(not overlap(r,p) and overlap(r,power_range(p)) for p in allowed_poles): continue
                bodies.append((r,k,axis))
    return bodies

def line_cells(line):
    _,hor,c,start,end=line
    return [(t,c) if hor else (c,t) for t in range(start,end)]

def projection(r,line):
    _,hor,c,start,end=line
    x,y,w,h=r
    if not ((y<=c<y+h) if hor else (x<=c<x+w)): return None
    a,z=(x,x+w) if hor else (y,y+h)
    s,e=max(a,start),min(z,end)
    return (s-start,e-start,s==a and e==z) if s<e else None

FORBIDDEN={('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}

def options_for(b,bodies,line,losses,forced=(),absent=(),with_j=False):
    cells=line_cells(line); options=[set() for _ in cells]
    occupied={i for i,c in enumerate(cells) if any(contains(r,*c) for r in forced)}
    gaps=[None if i in occupied else 0 if contains(hole(b),*c) else 1 for i,c in enumerate(cells)]
    back=defaultdict(list)
    for r,k,axis in bodies:
        if r in absent or any(overlap(r,f) for f in forced): continue
        p=projection(r,line)
        if p is None: continue
        start,end,full=p
        typ=k if full else 'Z'
        option=(end,typ,int(k=='C'),int(k=='P'),losses[r[:2]] if k=='P' else 0)
        if with_j: option+=(-2 if k=='P' and edge_count(r) else 0,)
        options[start].add(option)
        back[start,option].append((r,k,axis))
    for f in forced:
        p=projection(f,line)
        if p is not None:
            s,e,full=p
            v=(e,'P' if full else 'Z',0,0,0)
            if with_j: v+=(0,)
            options[s].add(v)
    return [sorted(o) for o in options],gaps,back

def prune(table):
    # Dominance only at equal (core count, pole count). Keep each new strict
    # improvement as the loss budget increases. Exact integer costs throughout.
    out={}; best={}
    for (c,p,l),v in sorted(table.items()):
        if v < best.get((c,p),10**9):
            out[c,p,l]=v; best[c,p]=v
    return out

def solve_line(options,gaps):
    n=len(gaps); states=[{} for _ in range(n+1)]
    states[0][('',0,0,0)]=0
    def put(i,k,v):
        if v<states[i].get(k,10**9): states[i][k]=v
    for i in range(n):
        for (prev,c,p,l),v in list(states[i].items()):
            if gaps[i] is not None: put(i+1,('',c,p,l),v+gaps[i])
            for option in options[i]:
                end,kind,dc,dp,dl,*extra=option
                if (prev,kind) in FORBIDDEN: continue
                if c+dc<=1 and p+dp<=12 and l+dl<=59:
                    put(end,(kind,c+dc,p+dp,l+dl),v+(extra[0] if extra else 0))
    result={}
    for (_,c,p,l),v in states[n].items(): result[c,p,l]=min(v,result.get((c,p,l),10**9))
    return prune(result)

def merge(tables):
    joint={(0,0,0):0}
    for table in tables:
        nxt={}
        for (c,p,l),v in joint.items():
            for (d,q,m),w in table.items():
                k=c+d,p+q,l+m
                if k[0]<=1 and k[1]<=12 and k[2]<=59:
                    nxt[k]=min(v+w,nxt.get(k,10**9))
        joint=prune(nxt)
    return joint

def limited_min(table,P,offset_p=0,offset_l=0):
    a=[v for (c,p,l),v in table.items() if p+offset_p<=P and l+offset_l<=23*P-217]
    return min(a) if a else None

def compare_line(options,gaps,table,record,label):
    expected=[[tuple(v) for v in ls] for ls in record['options']]
    assert options==expected,(label,'options',[(i,a,z) for i,(a,z) in enumerate(zip(options,expected)) if a!=z][:3])
    assert gaps==record['gaps'],(label,'gaps')
    assert table=={tuple(k):v for k,v in record['frontier']},(label,'frontier',table,record['frontier'])

def outer_lines():
    return [('E',False,69,1,70),('N',True,69,1,70)]

def inner_lines(b):
    return [('W',False,48,b,b+53),('S',True,b-1,49,70)]+([('N',True,b+53,49,70)] if b+53<70 else [])

def verify_edges(losses):
    submitted=read_json('edge_integer_certificate.json'); results=[]; rebuilt=[]; checks=0
    assert len(submitted)==4
    assert {(r['b'],r['branch']) for r in submitted}=={(9,'all'),(17,'all'),(9,'no_lower_pole'),(9,'no_upper_pole')}
    geometry={}
    for record in submitted:
        b=record['b']; branch=record['branch']; bodies=all_bodies(b,losses[b],branch)
        required={(s,True,False) for s,*_ in outer_lines()}|{(s,False,False) for s,*_ in inner_lines(b)}
        if (b,branch)==(9,'all'):required|={(s,True,True) for s,*_ in outer_lines()}
        assert len(record['lines'])==len(required)
        assert {(e['side'],e['outer'],e['corner']) for e in record['lines']}==required
        geometry[b,branch]=bodies
        poles=[r for r,k,axis in bodies if k=='P']
        outsets={False:[],True:[]}; inners=[]; saved=[]
        for entry in record['lines']:
            line=next(z for z in (outer_lines() if entry['outer'] else inner_lines(b)) if z[0]==entry['side'])
            forced=((68,68,2,2),) if entry['corner'] else ()
            absent=((68,68,2,2),) if entry['outer'] and not entry['corner'] else ()
            opts,gaps,back=options_for(b,bodies,line,losses[b],forced,absent)
            table=solve_line(opts,gaps)
            compare_line(opts,gaps,table,entry,(b,branch,line,entry['corner']))
            if entry['outer']: outsets[entry['corner']].append(table)
            else: inners.append(table)
            saved.append({'line':line,'corner':entry['corner'],'options':opts,'gaps':gaps,'frontier':sorted(table.items())})
            # Check every represented adjacent full-body pair rejected by the
            # DP: either collision or loss of necessary ports on one body.
            bystart=defaultdict(list)
            for (s,v),anchors in back.items():
                if v[1]!='Z': bystart[s].extend((v[0],v[1],a) for a in anchors)
            for s,ls in bystart.items():
                for e,k,a in ls:
                    for _,j,z in bystart.get(e,[]):
                        if (k,j) not in FORBIDDEN: continue
                        ar,ak,aa=a; zr,zk,za=z
                        assert overlap(ar,zr) or not ports_valid(ar,ak,aa,b,(zr,)) or not ports_valid(zr,zk,za,b,(ar,)),(b,line,a,z)
                        checks+=1
        # No non-pole can touch both X segments. Nor can any body touch two
        # inner Y segments, so resources within each combined table are unique.
        for r,k,axis in bodies:
            xo=[z for z in outer_lines() if projection(r,z)]
            yi=[z for z in inner_lines(b) if projection(r,z)]
            assert len(xo)<2 or (k=='P' and r==(68,68,2,2))
            assert len(yi)<2
        X0=merge(outsets[False]); Y=merge(inners)
        X1=merge(outsets[True]) if outsets[True] else None
        for P in ((10,11,12) if branch=='all' else (10,)):
            X=limited_min(X0,P)
            if X1 is not None:
                xc=limited_min(X1,P,1,losses[b][68,68])
                if xc is not None: X=min(X,xc)
            y=limited_min(Y,P); allowed=187-16*P+2*((23*P-217)//9)
            results.append({'b':b,'branch':branch,'P':P,'X':X,'Y':y,'allowed':allowed,'excess':X+y-allowed})
        rebuilt.append({'b':b,'branch':branch,'body_count':len(bodies),'lines':saved})
    save('rebuilt_edge_tables.json',rebuilt)
    save('edge_results.json',{'results':results,'adjacent_anchor_checks':checks})
    print('EDGES',results,'adjacent checks',checks,flush=True)
    return geometry,results

def verify_joint(losses,geometry):
    b=17; bodies=geometry[17,'all']
    lines=[('E',False,69,1,17),('N',True,69,1,49),('W',False,48,17,70),('S',True,16,49,70)]
    shared=sorted({r for r,k,a in bodies if sum(projection(r,line) is not None for line in lines)>1})
    assert shared==[(47,68,2,2),(68,15,2,2)],shared
    recs=read_json('joint17_integer_certificate.json')['cases']; jrecs=read_json('joint17_j_certificate.json')['cases']
    assert {tuple(r['mask']) for r in recs}==set(product((0,1),repeat=2)) and len(recs)==4
    assert {tuple(r['mask']) for r in jrecs}==set(product((0,1),repeat=2)) and len(jrecs)==4
    results=[]; saved=[]
    for mask in product((0,1),repeat=2):
        forced=tuple(r for r,v in zip(shared,mask) if v); absent=tuple(r for r,v in zip(shared,mask) if not v)
        cp=sum(mask); cl=sum(losses[b][r[:2]] for r in forced)
        tables=[]
        for with_j,records in [(False,recs),(True,jrecs)]:
            record=next(v for v in records if tuple(v['mask'])==mask)
            assert record['corner_loss']==cl
            assert len(record['lines'])==4
            fs=[]; ls=[]
            for line,entry in zip(lines,record['lines']):
                assert list(line)==entry['line']
                opts,gaps,back=options_for(b,bodies,line,losses[b],forced,absent,with_j)
                tab=solve_line(opts,gaps)
                compare_line(opts,gaps,tab,entry,('joint',mask,with_j,line))
                fs.append(tab); ls.append({'line':line,'options':opts,'gaps':gaps,'frontier':sorted(tab.items())})
            tables.append(merge(fs)); saved.append({'mask':mask,'with_j':with_j,'lines':ls,'merged':sorted(tables[-1].items())})
        for P in (10,11,12):
            XY=limited_min(tables[0],P,cp,cl)
            candidates=[]
            for (c,p,l),v in tables[1].items():
                if p+cp>P or l+cl>23*P-217: continue
                omitted=min(P-p-cp,(23*P-217-l-cl)//9)
                candidates.append((16*P-2*cp+v-2*omitted,(c,p,l),omitted))
            best=min(candidates) if candidates else (None,None,None)
            results.append({'mask':mask,'P':P,'corner_loss':cl,'XY':XY,'S':best[0], 'resources':best[1],'omitted_J':best[2]})
    save('rebuilt_joint_tables.json',saved)
    save('joint_results.json',{'shared_bodies':shared,'results':results})
    print('JOINT',results,flush=True)
    return results

def verify_search_geometry(geometry):
    # Independently check the search's stated anchor counts; no numerical
    # feasibility/optimality claim is inferred from these domain counts.
    audits=[]
    for b in (9,17):
        strips=[(49,1,21,b-1)]+([(49,b+53,21,17-b)] if b<17 else [])
        def touches(r):
            return any(overlap(r,z) for z in strips)
        anchors=[v for v in geometry[b,'all'] if v[1]=='P' or touches(v[0])
                 or any(projection(v[0],line) for line in outer_lines()+inner_lines(b))]
        audits.append({'b':b,'all_anchors':len(anchors),
                       'strip_machine_anchors':sum(k=='M' and touches(r) for r,k,a in geometry[b,'all'])})
    assert audits==read_json('model_audit.json')['anchor_audits']
    save('search_geometry_audit.json',{'anchor_audits':audits,'not_a_feasibility_certificate':True})

def main():
    started=time.monotonic()
    manifest={n:digest(ROOT/n) for n in INPUT_NAMES}
    manifest.update({str(p.relative_to(ROOT)):digest(p) for p in SUBMITTED.glob('*certificate*.json')})
    manifest.update({str((SUBMITTED/n).relative_to(ROOT)):digest(SUBMITTED/n)
                     for n in ['model_audit.json','exact_verification.json']})
    save('input_manifest.json',manifest)
    losses=verify_power()
    geometry,edges=verify_edges(losses)
    joint=verify_joint(losses,geometry)
    verify_search_geometry(geometry)
    # Compare independently calculated aggregate values too, not just tables.
    submitted_results=read_json('exact_verification.json')
    expected={(r['b'],r['branch'],r['P']):(r['X'],r['Y']) for r in submitted_results['results']}
    assert {(r['b'],r['branch'],r['P']):(r['X'],r['Y']) for r in edges}==expected
    jm={(tuple(r['corner_mask']),r['P']):r['min_S'] for r in submitted_results['joint17_with_J']}
    assert {(tuple(r['mask']),r['P']):r['S'] for r in joint if r['S'] is not None}==jm
    jxy={(tuple(r['corner_mask']),r['P']):r['XY'] for r in submitted_results['joint17']}
    assert {(tuple(r['mask']),r['P']):r['XY'] for r in joint if r['XY'] is not None}==jxy
    for n in INPUT_NAMES: assert digest(ROOT/n)==manifest[n]
    save('results.json',{'status':'PASS','edge_results':edges,'joint_results':joint,'seconds':time.monotonic()-started,'input_hashes':manifest})
    print('PASS',time.monotonic()-started,flush=True)

if __name__=='__main__':
    main()
