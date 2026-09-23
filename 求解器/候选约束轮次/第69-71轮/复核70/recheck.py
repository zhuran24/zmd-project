#!/usr/bin/env python3
"""Round 70 independent exact review. Reads data certificates, never producer code.
All output is confined to this script's directory. Run with python -B -S.
Rectangles in this implementation are (x, y, width, height), half open.
"""
from pathlib import Path
from fractions import Fraction
from collections import defaultdict, Counter
from itertools import product
from math import lcm
import json
import hashlib
import sys
import re

OUT = Path(__file__).resolve().parent
ROUND = OUT.parent
ROOT = ROUND.parents[2]
SRC = ROUND / '推导69'
PREV = ROUND.parent / '第66-68轮' / '推导66'
INPUTS = {}

def read(path):
    b = path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))] = {'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b)}
    return json.loads(b) if path.suffix == '.json' else b.decode()

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def overlap(a, b):
    x,y,w,h=a; X,Y,W,H=b
    return x<X+W and X<x+w and y<Y+H and Y<y+h

def cells(r):
    x,y,w,h=r
    return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}

def sides(r, axis):
    x,y,w,h=r
    if axis == 0:
        return [[(x-1,j) for j in range(y,y+h)], [(x+w,j) for j in range(y,y+h)]]
    return [[(i,y-1) for i in range(x,x+w)], [(i,y+h) for i in range(x,x+w)]]

TYPES = [(3,3,0),(3,3,1),(5,5,0),(5,5,1),(6,4,1),(4,6,0)]
EMPTY = (49,17,21,53)
POLE = (5,5,2,2)

def local_model(walls, hole=None):
    lo,hi,bot,top=walls
    def allowed(c):
        x,y=c
        return lo<=x<hi and bot<=y<top and c not in polecells and not (hole and hole[0]<=x<hole[2] and hole[1]<=y<hole[3])
    polecells=cells(POLE)
    bodies=[]
    for w,h,axis in TYPES:
        for x in range(1-w,12):
            for y in range(1-h,12):
                r=(x,y,w,h); occupied=cells(r)
                if not all(allowed(c) for c in occupied):
                    continue
                ports=[[c for c in side if allowed(c)] for side in sides(r,axis)]
                if all(ports):
                    bodies.append({'rect':list(r),'axis':axis,'ports':[[list(c) for c in side] for side in ports]})
    occupiers=defaultdict(list)
    for i,b in enumerate(bodies):
        for c in cells(b['rect']):occupiers[c].append(i)
    labels=[];rows=[];rhs=[]
    for c in sorted(occupiers):
        labels.append(['cell',*c]); rows.append({j:1 for j in occupiers[c]});rhs.append(1)
    for j,b in enumerate(bodies):
        for k,port in enumerate(b['ports']):
            coeff=Counter({j:1})
            for c in port:coeff.update(occupiers[tuple(c)])
            labels.append(['port',j,k]);rows.append(dict(coeff));rhs.append(len(port))
    return bodies,rows,rhs,labels

def dual_check(cert, model):
    bodies,rows,rhs,_=model
    terms=cert['rows'];bounds=cert['bounds']
    assert len({t[0] for t in terms})==len(terms)
    assert len({t[0] for t in bounds})==len(bounds)
    den=lcm(*(t[2] for t in terms+bounds))
    lhs=[0]*len(bodies);right=0
    for i,n,d in terms:
        assert 0<=i<len(rows) and n>=0 and d>0
        weight=n*(den//d);right+=weight*rhs[i]
        for j,a in rows[i].items():lhs[j]+=weight*a
    for j,n,d in bounds:
        assert 0<=j<len(bodies) and n>=0 and d>0
        weight=n*(den//d);lhs[j]+=weight;right+=weight
    assert min(lhs)>=den, ('uncovered column', min(lhs),den)
    assert Fraction(right,den)==Fraction(*cert['upper'])
    assert right//den==cert['integer_upper']
    return {'variables':len(bodies),'rows':len(rows),'terms':len(terms),'bound_terms':len(bounds),
            'upper':str(Fraction(right,den)), 'integer_upper':right//den,
            'minimum_column_coefficient':str(Fraction(min(lhs),den))}

def check_local():
    wall=read(SRC/'wall0_certificate.json')
    model=local_model((-20,7,-20,32))
    supplied=read(SRC/'wall0_model.json')
    assert model[0]==supplied['bodies'] and model[2]==supplied['rhs'] and model[3]==supplied['labels']
    assert all(a==dict(b) for a,b in zip(model[1],supplied['rows'])) and len(model[1])==len(supplied['rows'])
    summary={'wall':dual_check(wall,model)}
    # Deliberately damage an in-memory certificate: the checker must reject it.
    broken=dict(wall);broken['integer_upper']=12
    try:dual_check(broken,model)
    except AssertionError:pass
    else:raise AssertionError('bad integer bound accepted')
    broken=dict(wall);broken['rows']=wall['rows'][1:]
    try:dual_check(broken,model)
    except AssertionError:pass
    else:raise AssertionError('missing positive multiplier accepted')
    print('wall PASS',summary['wall'],flush=True)
    expected={(p,q) for p in range(43,69) for q in range(1,17) if not overlap((p,q,2,2),EMPTY)}
    caps={};results=[];total_columns=0;total_rows=0
    certs=read(SRC/'supply_strip_certificates.json')
    for e in certs:
        assert e['positions']
        walls,hole=e['geom']
        m=local_model(walls,hole)
        assert len(m[0])==e['n']
        result=dual_check(e,m)
        total_columns+=len(m[0]);total_rows+=len(m[1])
        for p,q in e['positions']:
            assert (p,q) in expected and (p,q) not in caps
            # The clipping constants enclose every possible body AND port cell.
            wantwalls=[max(-6,6-p),min(18,75-p),max(-6,6-q),min(18,75-q)]
            wanthole=[max(-6,54-p),max(-6,22-q),18,18]
            assert walls==wantwalls and hole==wanthole,(p,q,walls,hole)
            # Independent absolute-coordinate enumeration, with no clipped geometry.
            actual=[]
            for w,h,axis in TYPES:
                for x in range(max(1,p-4-w),min(70-w,p+6)+1):
                    for y in range(max(1,q-4-h),min(70-h,q+6)+1):
                        r=(x,y,w,h)
                        if overlap(r,EMPTY) or overlap(r,(p,q,2,2)):continue
                        def free(c):
                            i,j=c
                            return 1<=i<70 and 1<=j<70 and not (49<=i<70 and 17<=j<70) and not(p<=i<p+2 and q<=j<q+2)
                        ports=[[c for c in side if free(c)] for side in sides(r,axis)]
                        if not all(ports):continue
                        actual.append((x-p+5,y-q+5,w,h,axis))
            assert actual==[(*b['rect'],b['axis']) for b in m[0]],('absolute domain',p,q)
            caps[p,q]=e['integer_upper']
        results.append({'positions':e['positions'],**result})
        if len(results)%50==0:print('local certificates',len(results),flush=True)
    assert set(caps)==expected and len(expected)==395
    edge=[caps[68,q] for q in range(1,16)]
    assert edge==[7,7,8,9,10,11,12,12,12,11,10,9,8,7,7]
    summary.update({'positions':len(caps),'certificates':len(certs),'total_columns':total_columns,
                    'total_rows':total_rows,'right_edge_caps':edge,'certificates_checked':results,
                    'mutation_tests':['wrong floor rejected','missing multiplier rejected']})
    save('local_results.json',summary)
    print('local PASS',len(caps),'positions',total_columns,'columns',flush=True)
    return caps

def check_groups():
    certs=read(PREV/'power_certificates.json')['17']
    expected={(p,q) for p in range(1,69) for q in range(1,69) if not overlap((p,q,2,2),EMPTY)}
    caps={};count=0
    for e in certs:
        p,q=e['x'],e['y'];assert (p,q) in expected and (p,q) not in caps
        centers=[]
        for x in range(max(2,p-6),min(68,p+7)+1):
            for y in range(max(2,q-6),min(68,q+7)+1):
                b=(x-1,y-1,3,3)
                if not overlap(b,EMPTY) and not overlap(b,(p,q,2,2)):
                    assert overlap(b,(p-5,q-5,12,12));centers.append((x,y))
        covered=set()
        for a,b,w,h in e['tiles']:
            assert 1<=w<=3 and 1<=h<=3
            covered.update(cells((a,b,w,h)))
        assert set(centers)<=covered
        assert e['cap']==min(23,len(e['tiles']))
        caps[p,q]=e['cap'];count+=len(centers)
    assert set(caps)==expected and len(caps)==3511
    save('group_results.json',{'poles':len(caps),'centers':count,'cap_counts':dict(sorted(Counter(caps.values()).items()))})
    print('groups PASS',len(caps),count,flush=True)
    return caps

LINES=[('E',False,69,1,17),('N',True,69,1,49),('W',False,48,17,70),('S',True,16,49,70)]
CORNERS=[(47,68),(68,15)]

def effective(c):
    x,y=c
    return 1<=x<70 and 1<=y<70 and not(49<=x<70 and 17<=y<70)

def projection(r,line):
    _,horizontal,fixed,start,stop=line
    x,y,w,h=r
    perpendicular,extent,along,length=(y,h,x,w) if horizontal else (x,w,y,h)
    if not perpendicular<=fixed<perpendicular+extent:return None
    a=max(start,along);b=min(stop,along+length)
    return (a-start,b-start,a==along and b==along+length) if a<b else None

def boundary_bodies():
    out=[]
    specs=[('M',w,h,axis) for w,h,axis in TYPES]+[('C',9,9,0),('C',9,9,1),('P',2,2,None)]
    for kind,w,h,axis in specs:
        for x in range(1,71-w):
            for y in range(1,71-h):
                r=(x,y,w,h)
                if overlap(r,EMPTY):continue
                projs=[projection(r,line) for line in LINES]
                if not any(projs):continue
                if kind=='M':
                    ports=[[c for c in s if effective(c)] for s in sides(r,axis)]
                    if not all(ports):continue
                    required=[];inports=[]
                elif kind=='C':
                    required=[s[i] for s in sides(r,axis) for i in (1,4,7)]
                    if not all(map(effective,required)):continue
                    inports=[s[i] for s in sides(r,1-axis) for i in range(1,8) if effective(s[i])]
                    if len(inports)<2:continue
                    ports=[]
                else:ports=[];required=[];inports=[]
                out.append({'kind':kind,'rect':r,'axis':axis,'ports':ports,'required':required,
                            'inports':inports,'projections':projs})
    multi=[b for b in out if sum(p is not None for p in b['projections'])>1]
    assert {(b['kind'],b['rect']) for b in multi}=={('P',(*xy,2,2)) for xy in CORNERS}
    assert len(multi)==2
    return out

def pole_loss(p,q,groups,local,mode):
    nedge=int(p in (1,68))+int(q in (1,68))
    edge=0 if nedge==0 else (15 if nedge==2 else (9 if mode=='old' else 10))
    values=[0,23-groups[p,q],edge]
    sidebar=(10,9,9,6,5,4,1)
    g=47-p
    if 0<=g<=6 and q-5>=17 and q+7<=70:values.append(sidebar[g])
    g=15-q
    if 0<=g<=6 and p-5>=49 and p+7<=70:values.append(sidebar[g])
    if mode=='local' and (p,q) in local:values.append(23-local[p,q])
    return max(values)

def incompatible(a,b):
    return (a,b) in {('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}

def pair_check(bodies):
    checked=0
    def blocked(a,b):
        if overlap(a['rect'],b['rect']):return True
        occ=cells(b['rect'])
        if a['kind']=='M':return any(set(side)<=occ for side in a['ports'])
        if a['kind']=='C':return bool(set(a['required'])&occ) or len(set(a['inports'])-occ)<2
        return False
    for lineid in range(4):
        ending=defaultdict(list);starting=defaultdict(list)
        for b in bodies:
            p=b['projections'][lineid]
            if p and p[2]:starting[p[0]].append(b);ending[p[1]].append(b)
        for t in starting.keys()&ending.keys():
            for a in ending[t]:
                for b in starting[t]:
                    if incompatible(a['kind'],b['kind']):
                        assert blocked(a,b) or blocked(b,a),(lineid,a,b)
                        checked+=1
    return checked

def line_options(bodies,li,mask,groups,local,mode,score_j):
    line=LINES[li];n=line[4]-line[3]
    forced=[]
    for enabled,xy in zip(mask,CORNERS):
        if enabled:
            z=projection((*xy,2,2),line)
            if z:forced.append(z[:2])
    options=[set() for _ in range(n)];gaps=[1]*n
    for a,b in forced:
        for i in range(a,b):gaps[i]=None
    for body in bodies:
        proj=body['projections'][li]
        if proj is None:continue
        x,y,w,h=body['rect'];kind=body['kind']
        if kind=='P' and (x,y) in CORNERS:continue
        a,b,full=proj
        if any(a<d and c<b for c,d in forced):continue
        tag=kind if full else 'Z'
        core=int(kind=='C');pole=int(kind=='P');loss=pole_loss(x,y,groups,local,mode) if pole else 0
        value=-2 if score_j and pole and (x in (1,68) or y in (1,68)) else 0
        options[a].add((b,tag,core,pole,loss,value))
    for a,b in forced:options[a].add((b,'P',0,0,0,0))
    return [sorted(x) for x in options],gaps

def frontier(states):
    kept={};best={}
    for key,value in sorted(states.items()):
        c,p,l=key
        if value<best.get((c,p),10**6):
            best[c,p]=value;kept[key]=value
    return kept

def solve_line(options,gaps):
    n=len(options);dp=[{} for _ in range(n+1)]
    dp[0][('',0,0,0)]=0
    for i in range(n):
        for (prev,c,p,l),value in dp[i].items():
            if gaps[i] is not None:
                key=('',c,p,l);new=value+gaps[i]
                if new<dp[i+1].get(key,10**6):dp[i+1][key]=new
            for end,tag,dc,dpole,dl,add in options[i]:
                if incompatible(prev,tag):continue
                C,P,L=c+dc,p+dpole,l+dl
                if C>1 or P>12 or L>59:continue
                key=(tag,C,P,L);new=value+add
                if new<dp[end].get(key,10**6):dp[end][key]=new
    result={}
    for (_,c,p,l),value in dp[n].items():
        key=(c,p,l)
        result[key]=min(value,result.get(key,10**6))
    return result

def merge_tables(tables):
    current={(0,0,0):0}
    for tab in tables:
        nxt={}
        for (c,p,l),v in current.items():
            for (C,P,L),V in tab.items():
                key=(c+C,p+P,l+L)
                if key[0]>1 or key[1]>12 or key[2]>59:continue
                new=v+V
                if new<nxt.get(key,10**6):nxt[key]=new
        current=nxt
    return current

def check_edges(groups,local):
    bodies=boundary_bodies();assert len(bodies)==652,len(bodies)
    pairs=pair_check(bodies)
    print('boundary geometry PASS',len(bodies),'bodies',pairs,'forbidden pairs',flush=True)
    all_results=[];counts={'tables':0,'options':0,'frontier_entries':0,'bodies':len(bodies),'forbidden_adjacent_pairs':pairs}
    runs=[('old',False,PREV/'joint17_integer_certificate.json'),
          ('new',True,SRC/'new_edge_certificate.json'),
          ('local',True,SRC/'new_edge_local_certificate.json')]
    for mode,score_j,path in runs:
        cert=read(path)
        assert {tuple(c['mask']) for c in cert['cases']}==set(product((0,1),repeat=2)) and len(cert['cases'])==4
        recorded={(tuple(e['corner_mask']),e['P']):e for e in cert['results']}
        expected_results={(m,p) for m in product((0,1),repeat=2) for p in (10,11,12) if p!=10 or m==(0,0)}
        assert set(recorded)==expected_results and len(recorded)==len(cert['results'])
        for case in cert['cases']:
            mask=tuple(case['mask']);k=sum(mask)
            closs=sum(pole_loss(*xy,groups,local,mode) for xy,on in zip(CORNERS,mask) if on)
            assert case['corner_loss']==closs
            assert [tuple(x['line']) for x in case['lines']]==LINES
            tables=[]
            for li,submitted in enumerate(case['lines']):
                opts,gaps=line_options(bodies,li,mask,groups,local,mode,score_j)
                decoded=[[tuple(v) if score_j else (*v,0) for v in row] for row in submitted['options']]
                assert opts==decoded,('options',mode,mask,li)
                assert gaps==submitted['gaps']
                table=solve_line(opts,gaps)
                front=frontier(table)
                assert front=={tuple(k):v for k,v in submitted['frontier']},('frontier',mode,mask,li)
                tables.append(table)
                counts['tables']+=1;counts['options']+=sum(map(len,opts));counts['frontier_entries']+=len(front)
            combined=merge_tables(tables)
            for P in (10,11,12):
                budget=23*P-217
                if closs>budget:
                    assert (mask,P) not in recorded
                    all_results.append({'mode':mode,'mask':mask,'P':P,'corner_loss':closs,'minimum':None,'reason':'corner loss exceeds budget'})
                    continue
                choices=[]
                for (c,p,l),v in combined.items():
                    if p+k>P or l+closs>budget:continue
                    omitted=min(P-p-k,(budget-l-closs)//(9 if mode=='old' else 10))
                    score=16*P+v-2*k-2*omitted if score_j else v
                    choices.append((score,c,p,l,omitted,v))
                value=min(choices)[0]
                expected=recorded[mask,P]['min_S' if score_j else 'XY']
                assert value==expected,('minimum',mode,mask,P,value,expected)
                all_results.append({'mode':mode,'mask':mask,'P':P,'corner_loss':closs,'minimum':value,'one_resource_minimizer':min(choices)[1:]})
            print('edge PASS',mode,mask,flush=True)
    save('edge_results.json',{'counts':counts,'results':all_results})
    check_witness(groups,local)

def check_witness(groups,local):
    data=read(SRC/'search_P10_edge.json');chosen=data['chosen']
    occupied={};poles=[];machines=[];core=[]
    for i,b in enumerate(chosen):
        r=(b['x'],b['y'],b['w'],b['h'])
        assert all(map(effective,cells(r)))
        for c in cells(r):assert c not in occupied;occupied[c]=i
        if b['kind']=='p':poles.append((b['x'],b['y']))
        elif b['kind']=='c':core.append((i,b,r))
        else:machines.append((i,b,r))
    assert len(poles)==10 and len(core)==1
    for i,b,r in machines+core:
        axis=0 if b['axis']=='h' else 1
        if b['kind']=='c':
            req=[s[k] for s in sides(r,axis) for k in (1,4,7)]
            assert all(effective(c) and c not in occupied for c in req)
            ins=[s[k] for s in sides(r,1-axis) for k in range(1,8)]
            assert sum(effective(c) and c not in occupied for c in ins)>=2
        else:assert all(any(effective(c) and c not in occupied for c in s) for s in sides(r,axis))
    gaps=[]
    for _,horizontal,fixed,start,stop in LINES:
        gaps.append(sum(((t,fixed) if horizontal else (fixed,t)) not in occupied for t in range(start,stop)))
    j=sum(p in (1,68) or q in (1,68) for p,q in poles)
    losses=[pole_loss(p,q,groups,local,'local') for p,q in poles]
    multiplicities=[sum(overlap(r,(p-5,q-5,12,12)) for p,q in poles) for _,_,r in machines]
    assert all(k>=1 for k in multiplicities)
    repeats=sum(k-1 for k in multiplicities)
    S=160-2*j+sum(gaps)
    assert S==186 and sum(losses)==10 and repeats==11 and sum(losses)+repeats==21
    summary={'selected_kind_counts':dict(Counter(b['kind'] for b in chosen)), 'gaps':gaps,'J':j,'S':S,
             'pole_losses':losses,'machine_coverage_counts':multiplicities,'loss_total':sum(losses),'repeats':repeats,
             'total_charge':sum(losses)+repeats,'budget':13,'status':'relaxation point only; no material-source or cycle witness'}
    save('witness_results.json',summary)
    print('witness PASS',S,sum(losses),repeats,flush=True)

def check_accounting():
    rule=read(ROOT/'《明日方舟：终末地》游戏规则.txt')
    formal=read(ROOT/'求解约束.txt')
    recipes=[];machine=None
    def items(s):
        return {m.group(2):int(m.group(1)) for m in re.finditer(r'(\d+)\s+([^ ＋]+)',s.strip())}
    for line in rule.split('\n配方\n')[1].splitlines():
        line=line.strip()
        if not line:continue
        if '→' not in line:machine=line;continue
        left,right=line.split('→');right,tick=right.split('，')
        recipes.append((machine,items(left),items(right),int(re.search(r'\d+',tick).group())))
    names=sorted({i for _,a,b,_ in recipes for i in a.keys()|b.keys()})
    assert len(recipes)==18 and len(names)==19
    nr=len(recipes);mat=[]
    for item in names:
        rhs={'高容谷地电池':Fraction(3,5),'精选荞愈胶囊':Fraction(11,20)}.get(item,0)
        mat.append([Fraction(b.get(item,0)-a.get(item,0)) for _,a,b,_ in recipes]
                   +[Fraction(item=='源矿'),Fraction(item=='蓝铁矿'),Fraction(rhs)])
    # Under A=1113, all 51 refineries run continuously by formal 满载配置.
    mat.append([Fraction(kind=='精炼炉') for kind,_,_,_ in recipes]+[Fraction(0),Fraction(0),Fraction(51)])
    n=nr+2;assert len(mat)==n
    for col in range(n):
        pivot=next(i for i in range(col,n) if mat[i][col])
        mat[col],mat[pivot]=mat[pivot],mat[col]
        d=mat[col][col];mat[col]=[x/d for x in mat[col]]
        for i in range(n):
            if i!=col and mat[i][col]:
                d=mat[i][col];mat[i]=[a-d*b for a,b in zip(mat[i],mat[col])]
    solution=[row[-1] for row in mat];assert all(v>=0 for v in solution)
    lowerline=next(x for x in formal.splitlines() if x.startswith('机型下限：'))
    numbers={name:int(num) for name,num in re.findall(r'([\u4e00-\u9fff]+) ≥(\d+)',lowerline) if name in {r[0] for r in recipes}}
    assert len(numbers)==9
    counts={};rates={};active={};areas={}
    for kind in numbers:
        ids=[i for i,r in enumerate(recipes) if r[0]==kind]
        duration=recipes[ids[0]][3];assert all(recipes[i][3]==duration for i in ids)
        total=sum(solution[i] for i in ids)
        nmin=-(-(total*duration).numerator//(total*duration).denominator)
        assert nmin==numbers[kind]
        counts[kind]=nmin;rates[kind]=[str(solution[i]) for i in ids]
        active[kind]=str(total-Fraction(nmin-1,duration));assert Fraction(active[kind])>0
        areas[kind]=9 if kind in ('粉碎机','精炼炉','塑形机','配件机') else (25 if kind in ('种植机','采种机') else 24)
    total=sum(counts.values());area=sum(counts[k]*areas[k] for k in counts)
    assert total==217 and area==3291
    assert 4900-area-81-46*3-1113==277
    budgets=[{'P':p,'loss_budget':23*p-total,'old_J':(23*p-total)//9,'new_J':(23*p-total)//10,
              'transport_plus_outside_empty':277-4*p,'S_ceiling':4639-4*1113} for p in (10,11,12)]
    save('accounting_results.json',{'recipe_count':nr,'item_count':len(names),'recipe_rates':rates,
         'mining_rates':[str(x) for x in solution[-2:]],'counts':counts,'active_machine_rate_lower_bounds':active,
         'total_machines':total,'machine_area':area,'budgets':budgets})
    print('accounting PASS',total,area,flush=True)

def main():
    for name in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt']:
        read(ROOT/name)
    for name in ['候选约束.txt','求解器/候选约束轮次/第69-71轮/推导69.md',
                 '求解器/候选约束轮次/第66-68轮/推导66.md','求解器/候选约束轮次/第66-68轮/复核67.md',
                 '求解器/候选约束轮次/第66-68轮/复核68.md']:
        read(ROOT/name)
    check_accounting()
    local=check_local()
    groups=check_groups()
    if 'check_edges' in globals():check_edges(groups,local)
    for name,item in INPUTS.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==item['sha256']
    save('input_manifest.json',INPUTS)
    print('PASS: inputs unchanged',flush=True)

if __name__=='__main__':main()
