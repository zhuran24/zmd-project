#!/usr/bin/env python3
"""Round 71 independent reconstruction. Standard library; no author code imports.

All writes are confined to this script's directory. Input JSON is treated as
untrusted certificate data, never as the generator of the feasible domain.
Rectangles here use (x,y,width,height); axis 0 means left/right port sides.
"""
from pathlib import Path
from fractions import Fraction as Q
from collections import defaultdict, Counter
from itertools import product
import json, hashlib, time, sys, copy, re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
R69 = OUT.parent / '推导69'
R66 = OUT.parent.parent / '第66-68轮' / '推导66'
EMPTY = (49,17,21,53)
SPECS = [(3,3,0),(3,3,1),(5,5,0),(5,5,1),(6,4,1),(4,6,0)]
INPUTS = [ROOT/n for n in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']]
INPUTS += [OUT.parent/'推导69.md']
INPUTS += [OUT.parent.parent/'第66-68轮'/n for n in ['推导66.md','复核67.md','复核68.md']]
INPUTS += [R69/n for n in ['wall0_certificate.json','wall0_model.json','supply_strip_certificates.json','new_edge_certificate.json','new_edge_local_certificate.json','search_P10_edge.json','wall0_result.json']]
INPUTS += [R66/n for n in ['power_certificates.json','joint17_integer_certificate.json']]

def read(path): return json.loads(path.read_text())
def save(name,data): (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def manifest():
    return {str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in INPUTS}
def cells(r):
    x,y,w,h=r
    return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}
def hit(a,b):
    x,y,w,h=a; u,v,s,t=b
    return max(x,u)<min(x+w,u+s) and max(y,v)<min(y+h,v+t)
def sides(r,axis):
    x,y,w,h=r
    if axis==0: return [[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]]
    return [[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]]
def allowed(c):
    x,y=c
    return 1<=x<70 and 1<=y<70 and not (x>=49 and y>=17)

def local_model(walls, forbidden=None):
    """Enumerate ALL intersecting machines; only occupancy/one port per side."""
    post={(5,5),(5,6),(6,5),(6,6)}
    lo,hi,bot,top=walls
    def valid(c):
        x,y=c
        return lo<=x<hi and bot<=y<top and c not in post and (forbidden is None or not (forbidden[0]<=x<forbidden[2] and forbidden[1]<=y<forbidden[3]))
    bodies=[]
    for w,h,a in SPECS:
        for x in range(1-w,12):
            for y in range(1-h,12):
                r=(x,y,w,h)
                if not all(map(valid,cells(r))): continue
                ports=[[c for c in ss if valid(c)] for ss in sides(r,a)]
                if all(ports): bodies.append({'rect':list(r),'axis':a,'ports':ports})
    occupancy=defaultdict(dict)
    for i,b in enumerate(bodies):
        for c in cells(b['rect']): occupancy[c][i]=1
    rows=[]; rhs=[]; labels=[]
    for c in sorted(occupancy):
        rows.append(occupancy[c]); rhs.append(1); labels.append(['cell',*c])
    for i,b in enumerate(bodies):
        for k,port in enumerate(b['ports']):
            row=Counter({i:1})
            for c in port: row.update(occupancy.get(c,{}))
            rows.append(dict(row)); rhs.append(len(port)); labels.append(['port',i,k])
    return bodies,rows,rhs,labels

def dual(cert,model):
    bodies,rows,rhs,labels=model
    coeff=[Q(0)]*len(bodies); upper=Q(0)
    used=set()
    for row,num,den in cert['rows']:
        assert row not in used and 0<=row<len(rows); used.add(row)
        assert den>0 and num>=0
        weight=Q(num,den); upper+=weight*rhs[row]
        for col,val in rows[row].items(): coeff[col]+=weight*val
    used=set()
    for col,num,den in cert['bounds']:
        assert col not in used and 0<=col<len(bodies); used.add(col)
        assert den>0 and num>=0
        coeff[col]+=Q(num,den); upper+=Q(num,den)  # z_j <= 1
    assert min(coeff,default=Q(1))>=1, ('coefficient',min(coeff))
    assert upper==Q(*cert['upper']), ('upper',upper,cert['upper'])
    assert cert['integer_upper']==upper.numerator//upper.denominator
    return {'variables':len(bodies),'inequalities':len(rows),'nonzero_multipliers':len(cert['rows'])+len(cert['bounds']), 'upper':str(upper),'minimum_coefficient':str(min(coeff,default=Q(1))), 'cap':cert['integer_upper']}

def local_checks():
    model=local_model((-20,7,-20,32))
    wall=dual(read(R69/'wall0_certificate.json'),model)
    submitted=read(R69/'wall0_model.json')
    # Compare semantic rows, not dictionary iteration order.
    assert json.loads(json.dumps(model[0]))==submitted['bodies']
    assert model[1]==[dict(row) for row in submitted['rows']]
    assert model[2]==submitted['rhs'] and model[3]==submitted['labels']
    assert wall['variables']==550 and wall['inequalities']==1352
    assert wall['upper']=='1846/135' and wall['cap']==13
    witness=read(R69/'wall0_result.json')['witness']
    index={(tuple(b['rect']),b['axis']):i for i,b in enumerate(model[0])}
    chosen={index[tuple(b['rect']),b['axis']] for b in witness}
    assert len(chosen)==len(witness)==13
    assert all(sum(v for j,v in row.items() if j in chosen)<=rhs for row,rhs in zip(model[1],model[2]))
    wall['thirteen_body_relaxation_witness_checked']=True
    trials=[]
    for what in ['cap12','drop_multiplier']:
        bad=copy.deepcopy(read(R69/'wall0_certificate.json'))
        if what=='cap12': bad['integer_upper']=12
        else: bad['rows'].pop()
        try: dual(bad,model)
        except AssertionError: trials.append({'mutation':what,'rejected':True})
        else: raise AssertionError(('accepted mutation',what))
    positions={(p,q) for p in range(43,69) for q in range(1,17) if not hit((p,q,2,2),EMPTY)}
    certificates=read(R69/'supply_strip_certificates.json')
    found={}; details=[]
    for n,c in enumerate(certificates):
        assert c['positions']
        walls,forbidden=c['geom']
        m=local_model(walls,forbidden)
        assert c['n']==len(m[0])
        result=dual(c,m)
        for pp in c['positions']:
            p,q=pp; assert (p,q) in positions and (p,q) not in found
            # Outside [-6,18)^2 no body/port in this enumeration can occur.
            clip=lambda v:max(-6,min(18,v))
            actual=[list(map(clip,(6-p,75-p,6-q,75-q))),[max(-6,54-p),max(-6,22-q),18,18]]
            assert actual==c['geom'], (pp,actual,c['geom'])
            # Also rebuild un-clipped physical coordinates: there must be no missing option.
            physical=local_model((6-p,75-p,6-q,75-q),(54-p,22-q,75-p,75-q))
            assert physical[0]==m[0]
            found[p,q]=c['integer_upper']
        details.append({'positions':c['positions'],**result})
        if n%80==0: print('local certificates',n+1,flush=True)
    assert set(found)==positions and len(found)==395
    along=[found[68,q] for q in range(1,16)]
    assert along==[7,7,8,9,10,11,12,12,12,11,10,9,8,7,7]
    save('local_results.json',{'wall':wall,'strip_count':len(found),'right_edge':along,'certificates':details,'mutation_checks':trials})
    return found

def on_edge(p,q): return p in (1,68) or q in (1,68)
def formal_loss(p,q,edge_cost):
    n=int(p in (1,68))+int(q in (1,68))
    loss=15 if n==2 else edge_cost if n else 0
    # Only the west/south sides of this empty rectangle lie in the base.
    if p+2<=49 and q-5>=17 and q+7<=70:
        g=49-(p+2)
        if 0<=g<=6: loss=max(loss,[10,9,9,6,5,4,1][g])
    if q+2<=17 and p-5>=49 and p+7<=70:
        g=17-(q+2)
        if 0<=g<=6: loss=max(loss,[10,9,9,6,5,4,1][g])
    return loss

def group_checks():
    posts={(p,q) for p in range(1,69) for q in range(1,69) if not hit((p,q,2,2),EMPTY)}
    submitted=read(R66/'power_certificates.json')['17']
    assert len(submitted)==len(posts)==3511
    caps={}; total=0
    for c in submitted:
        p,q=c['x'],c['y']; assert (p,q) in posts and (p,q) not in caps
        domain={(x,y) for x in range(max(2,p-6),min(68,p+7)+1) for y in range(max(2,q-6),min(68,q+7)+1)
                if not hit((x-1,y-1,3,3),EMPTY) and not hit((x-1,y-1,3,3),(p,q,2,2))
                and hit((x-1,y-1,3,3),(p-5,q-5,12,12))}
        covered=set()
        for t in c['tiles']:
            assert all(type(x)==int for x in t) and 1<=t[2]<=3 and 1<=t[3]<=3
            covered.update(cells(t))
        assert domain<=covered
        assert c['cap']==min(23,len(c['tiles']))
        caps[p,q]=c['cap']; total+=len(domain)
    assert set(caps)==posts
    save('group_results.json',{'posts':len(posts),'centers':total,'corner_caps':[caps[47,68],caps[68,15]]})
    print('group certificates',len(posts),total,flush=True)
    return caps

LINES=[('E',False,69,1,17),('N',True,69,1,49),('W',False,48,17,70),('S',True,16,49,70)]
CORNERS=[(47,68,2,2),(68,15,2,2)]
BAD_PAIRS={('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}

def unit(r,kind,axis):
    if kind=='P': return {'r':r,'kind':kind,'axis':axis,'ports':[],'needs':[]}
    ss=sides(r,axis)
    if kind=='M': ports=ss; needs=[1,1]
    else:
        ports=[[side[k]] for side in ss for k in (1,4,7)]
        ports+=[[c for side in sides(r,1-axis) for c in side[1:8]]]
        needs=[1]*6+[2]
    ports=[[c for c in side if allowed(c)] for side in ports]
    return {'r':r,'kind':kind,'axis':axis,'ports':ports,'needs':needs}

def projection(u,line):
    _,horizontal,fixed,lo,hi=line
    x,y,w,h=u['r']
    if horizontal:
        if not y<=fixed<y+h: return None
        a,b=x,x+w
    else:
        if not x<=fixed<x+w: return None
        a,b=y,y+h
    start,end=max(a,lo),min(b,hi)
    if start>=end: return None
    return (start-lo,end-lo,u['kind'] if start==a and end==b else 'Z')

def enumerate_units():
    result=[]; total=0; mult=[]
    for kind,w,h,axis in [('M',w,h,a) for w,h,a in SPECS]+[('C',9,9,0),('C',9,9,1),('P',2,2,-1)]:
        for x in range(1,71-w):
            for y in range(1,71-h):
                r=(x,y,w,h)
                if hit(r,EMPTY): continue
                u=unit(r,kind,axis)
                if not all(len(g)>=need for g,need in zip(u['ports'],u['needs'])): continue
                total+=1
                projs=[projection(u,line) for line in LINES]
                if any(projs): result.append(u)
                if sum(p is not None for p in projs)>1: mult.append({'r':r,'kind':kind,'lines':[LINES[i][0] for i,p in enumerate(projs) if p]})
    assert {v['r'] for v in mult}==set(CORNERS) and len(mult)==2
    # Exhaust every forbidden adjacent pair of raw bodies, not merely length types.
    pairs=0
    for line in LINES:
        raw=[(u,projection(u,line)) for u in result if projection(u,line)]
        for a,pa in raw:
            for b,pb in raw:
                if pa[1]!=pb[0] or (pa[2],pb[2]) not in BAD_PAIRS: continue
                pairs+=1
                blocked=hit(a['r'],b['r'])
                if not blocked:
                    for source,target in [(a,b),(b,a)]:
                        obstruction=cells(target['r'])
                        if any(len(set(g)-obstruction)<need for g,need in zip(source['ports'],source['needs'])): blocked=True
                assert blocked,('unsafe adjacency rule',line,a,b)
    assert len(result)==652
    save('geometry_results.json',{'all_single_units':total,'touching_units':len(result),'multi_segment_units':mult,'forbidden_adjacent_pairs_checked':pairs})
    print('geometry',total,len(result),pairs,flush=True)
    return result

def frontier(table):
    """Only prune after whole segment / segment merge. Exact interior states."""
    kept={}; minima={}
    for (c,p,l),value in sorted(table.items()):
        if value<minima.get((c,p),10**9):
            kept[c,p,l]=value; minima[c,p]=value
    return kept

def minimize_line(options,gaps):
    n=len(options); states=[{} for _ in range(n+1)]
    states[0]['-',0,0,0]=0
    def put(d,key,value):
        if value<d.get(key,10**9): d[key]=value
    for i in range(n):
        for (prev,c,p,l),v in states[i].items():
            if gaps[i] is not None: put(states[i+1],('-',c,p,l),v+gaps[i])
            for end,kind,dc,dp,dl,cost in options[i]:
                if (prev,kind) in BAD_PAIRS or c+dc>1 or p+dp>12 or l+dl>59: continue
                put(states[end],(kind,c+dc,p+dp,l+dl),v+cost)
    table={}
    for (_,c,p,l),v in states[n].items(): put(table,(c,p,l),v)
    return frontier(table)

def merge_tables(a,b):
    table={}
    for (c,p,l),v in a.items():
        for (d,q,m),w in b.items():
            if c+d<=1 and p+q<=12 and l+m<=59:
                k=(c+d,p+q,l+m)
                table[k]=min(table.get(k,10**9),v+w)
    return frontier(table)

def reconstruct_options(units,line,mask,losses,include_j):
    n=line[4]-line[3]; opts=[set() for _ in range(n)]
    selected=[r for r,yes in zip(CORNERS,mask) if yes]
    for u in units:
        r=u['r']; kind=u['kind']; pr=projection(u,line)
        if pr is None: continue
        start,end,typ=pr
        if r in CORNERS and kind=='P':
            if r not in selected: continue
            option=(end,typ,0,0,0,0)
        else:
            if any(hit(r,fixed) for fixed in selected): continue
            c=int(kind=='C'); p=int(kind=='P')
            l=losses[r[0],r[1]] if p else 0
            cost=-2 if p and include_j and on_edge(r[0],r[1]) else 0
            option=(end,typ,c,p,l,cost)
        opts[start].add(option)
    return [sorted(s) for s in opts]

def edge_checks(local,group):
    units=enumerate_units()
    configs=[('old_XY',R66/'joint17_integer_certificate.json',9,False,False),
             ('new_S',R69/'new_edge_certificate.json',10,True,False),
             ('new_local_S',R69/'new_edge_local_certificate.json',10,True,True)]
    summary={}; mutation_done=False
    for name,path,edge_cost,include_j,use_local in configs:
        cert=read(path)
        losses={pos:max(23-cap,formal_loss(*pos,edge_cost),23-local.get(pos,23) if use_local else 0) for pos,cap in group.items()}
        cases={tuple(c['mask']):c for c in cert['cases']}
        assert set(cases)==set(product((0,1),repeat=2)) and len(cert['cases'])==4
        results={(tuple(r['corner_mask']),r['P']):r for r in cert['results']}
        assert len(results)==len(cert['results'])==9
        allrows=[]; count_opts=0; count_states=0
        for mask in product((0,1),repeat=2):
            fixed_count=sum(mask)
            fixed_loss=sum(losses[r[0],r[1]] for r,m in zip(CORNERS,mask) if m)
            case=cases[mask]; assert fixed_loss==case['corner_loss']
            assert [tuple(l['line']) for l in case['lines']]==LINES
            joint={(0,0,0):0}
            for line,submitted in zip(LINES,case['lines']):
                opts=reconstruct_options(units,line,mask,losses,include_j)
                expected=[[list(o if include_j else o[:-1]) for o in os] for os in opts]
                assert expected==submitted['options'], ('options mismatch',name,mask,line)
                gaps=[1]*len(opts)
                for r,yes in zip(CORNERS,mask):
                    pr=projection({'r':r,'kind':'P'},line)
                    if yes and pr:
                        for i in range(pr[0],pr[1]): gaps[i]=None
                assert submitted['gaps']==gaps
                if not mutation_done:
                    bad=copy.deepcopy(expected); bad[0].pop()
                    assert bad!=expected; mutation_done=True
                actual=minimize_line(opts,gaps)
                given={tuple(k):v for k,v in submitted['frontier']}
                assert actual==given, ('frontier mismatch',name,mask,line,actual,given)
                count_opts+=sum(map(len,opts)); count_states+=len(actual)
                joint=merge_tables(joint,actual)
            for P in (10,11,12):
                budget=23*P-217
                if fixed_loss>budget:
                    assert (mask,P) not in results
                    allrows.append({'mask':mask,'P':P,'fixed_loss':fixed_loss,'excluded_by_loss':True})
                    continue
                candidates=[]
                for (c,p,l),v in joint.items():
                    if p+fixed_count>P or l+fixed_loss>budget: continue
                    if include_j:
                        omitted=min(P-p-fixed_count,(budget-l-fixed_loss)//edge_cost)
                        value=16*P-2*fixed_count+v-2*omitted
                    else: omitted=0; value=v
                    candidates.append((value,(c,p,l),v,omitted))
                best=min(candidates)
                supplied=results[mask,P]['min_S' if include_j else 'XY']
                assert best[0]==supplied,('final mismatch',name,mask,P,best,supplied)
                allrows.append({'mask':mask,'P':P,'minimum':best[0],'resources':best[1],'segment_cost':best[2],'omitted_J':best[3],'fixed_loss':fixed_loss})
            print('edges',name,mask,'PASS',flush=True)
        summary[name]={'options':count_opts,'frontier_states':count_states,'branches':allrows}
    save('edge_results.json',summary)
    return summary

def accounting_checks():
    rules=(ROOT/'《明日方舟：终末地》游戏规则.txt').read_text()
    constraints=(ROOT/'求解约束.txt').read_text()
    named=[line.split('：')[0] for line in constraints.splitlines() if line and not line[0].isspace() and '：' in line and line.split('：',1)[1].strip()]
    assert len(named)==72
    recipes=[]; machine=None
    for line in rules.split('\n配方\n',1)[1].splitlines():
        line=line.strip()
        if not line: continue
        if '→' not in line: machine=line; continue
        left,right=line.split('→'); right,duration=right.split('，')
        def terms(text):
            return {name:int(n) for n,name in re.findall(r'(\d+)\s+([^＋]+?)(?=\s*＋|$)',text.strip())}
        ins,outs=terms(left),terms(right)
        assert ins and outs
        recipes.append((machine,ins,outs,int(duration.split()[0])))
    assert len(recipes)==18
    materials=sorted({k for _,i,o,_ in recipes for k in [*i,*o]})
    assert len(materials)==19
    # Unknowns: 18 recipe rates and two external ore supplies.
    matrix=[]
    for material in materials:
        row=[Q(o.get(material,0)-i.get(material,0)) for _,i,o,_ in recipes]
        row += [Q(material=='源矿'),Q(material=='蓝铁矿')]
        row += [Q(3,5) if material=='高容谷地电池' else Q(11,20) if material=='精选荞愈胶囊' else Q(0)]
        matrix.append(row)
    matrix.append([Q(machine=='精炼炉') for machine,_,_,_ in recipes]+[Q(0),Q(0),Q(51)])
    original=copy.deepcopy(matrix)
    pivot=0
    for col in range(20):
        i=next(i for i in range(pivot,len(matrix)) if matrix[i][col])
        matrix[pivot],matrix[i]=matrix[i],matrix[pivot]
        v=matrix[pivot][col]; matrix[pivot]=[x/v for x in matrix[pivot]]
        for j in range(len(matrix)):
            if j!=pivot:
                v=matrix[j][col]
                matrix[j]=[x-v*y for x,y in zip(matrix[j],matrix[pivot])]
        pivot+=1
    rates=[matrix[i][-1] for i in range(20)]
    assert all(x>=0 for x in rates)
    assert all(sum(x*y for x,y in zip(row[:-1],rates))==row[-1] for row in original)
    totals=defaultdict(Q)
    periods={}
    for (machine,_,_,duration),rate in zip(recipes,rates): totals[machine]+=rate; periods[machine]=duration
    minimum={m:-(-v.numerator*periods[m]//v.denominator) for m,v in totals.items()}
    per_machine={m:totals[m]-Q(minimum[m]-1,periods[m]) for m in minimum}
    assert sum(minimum.values())==217 and all(x>0 for x in per_machine.values())
    area=sum(n*(9 if m in ['粉碎机','精炼炉','配件机','塑形机'] else 25 if m in ['种植机','采种机'] else 24) for m,n in minimum.items())
    assert area==3291
    # Every one of the 24 boundary-hole positions and 47 joint arrangements.
    ports={}
    for gap in range(0,70,3):
        tiles=[tuple(range(a,a+3)) for a in list(range(0,gap,3))+list(range(gap+1,70,3))]
        assert len(tiles)==23 and {k for t in tiles for k in t}==set(range(70))-{gap}
        ports[gap]=[t[1] for t in tiles]
        # Neighbours along the boundary, when present, are warehouse short ends.
        assert all(any(n in (t[0],t[-1]) for t in tiles) for n in (gap-1,gap+1) if 0<=n<70)
    joint=[(g,h) for g in ports for h in ports if g==0 or h==0]
    assert len(joint)==47
    save('accounting_results.json',{'formal_constraints':len(named),'recipe_rates':[str(q) for q in rates[:18]],'ore_sources':list(map(str,rates[18:])), 'machine_counts':minimum,'manufacturing_area':area,'individual_rate_lower_bounds':{m:str(v) for m,v in per_machine.items()},'boundary_arrangements':len(joint),'area_remainder':4900-area-81-138-1113,'P_cases':[{'P':P,'loss_budget':23*P-217,'edge_J_max_old':(23*P-217)//9,'edge_J_max_new':(23*P-217)//10,'T_plus_F':277-4*P} for P in (10,11,12)]})
    print('accounting PASS',flush=True)

def point_checks(local,group):
    point=read(R69/'search_P10_edge.json')['chosen']
    occupied=set(); units=[]
    for b in point:
        kind='P' if b['kind']=='p' else 'C' if b['kind']=='c' else 'M'
        axis=0 if b['axis']=='h' else 1 if b['axis']=='v' else -1
        r=(b['x'],b['y'],b['w'],b['h']); cc=cells(r)
        assert all(map(allowed,cc)) and not cc&occupied
        if kind=='M': assert (r[2],r[3],axis) in SPECS
        if kind=='C': assert r[2:]==(9,9)
        if kind=='P': assert r[2:]==(2,2)
        occupied.update(cc); units.append(unit(r,kind,axis))
    for u in units:
        assert all(len(set(p)-occupied)>=need for p,need in zip(u['ports'],u['needs']))
    posts=[u['r'] for u in units if u['kind']=='P']
    machines=[u for u in units if u['kind']=='M']
    assert len(posts)==10 and len(machines)==22 and sum(u['kind']=='C' for u in units)==1
    k=[sum(hit(u['r'],(x-5,y-5,12,12)) for x,y,_,_ in posts) for u in machines]
    assert min(k)>=1
    loss=[max(23-group[x,y],formal_loss(x,y,10),23-local.get((x,y),23)) for x,y,_,_ in posts]
    assert loss==[b['loss'] for b in point if b['kind']=='p']
    repeated=sum(n-1 for n in k); gaps=[]
    for _,horizontal,fixed,lo,hi in LINES:
        gaps.append(sum((a,fixed) not in occupied if horizontal else (fixed,a) not in occupied for a in range(lo,hi)))
    J=sum(on_edge(x,y) for x,y,_,_ in posts); S=160-2*J+sum(gaps)
    assert (gaps,J,S,repeated,sum(loss))==([4,9,9,6],1,186,11,10)
    assert sum(k)==sum(sum(hit(u['r'],(x-5,y-5,12,12)) for u in machines) for x,y,_,_ in posts)
    save('point_results.json',{'source':'推导69/search_P10_edge.json','status':'necessary-condition relaxation only; no item sources or cycle constructed','machines':len(machines),'machine_sizes':dict(Counter(str(u['r'][2:]) for u in machines)),'posts':len(posts),'coverage_multiplicities':k,'gaps':gaps,'J':J,'S':S,'single_post_loss':sum(loss),'repeat_coverage':repeated,'total_fee':sum(loss)+repeated,'budget':13})
    print('point double count PASS',flush=True)

if __name__=='__main__':
    start=manifest()
    if (OUT/'input_manifest.json').exists(): assert read(OUT/'input_manifest.json')==start, 'input changed since first snapshot'
    else: save('input_manifest.json',start)
    t=time.monotonic()
    local=local_checks(); group=group_checks()
    edge_checks(local,group)
    accounting_checks(); point_checks(local,group)
    save('results.json',{'status':'PASS','elapsed_seconds':time.monotonic()-t,'inputs_unchanged':manifest()==start})
    assert manifest()==start
    print('PASS',flush=True)
