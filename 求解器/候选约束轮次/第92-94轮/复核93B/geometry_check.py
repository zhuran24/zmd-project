"""Two independent finite calculations for source geometry and boundary budgets."""
import itertools,json,math
from pathlib import Path
out=Path(__file__).resolve().parent

def ports_a(g):
    cells=[x for x in range(70) if x!=g]
    return [cells[i+1] for i in range(0,69,3)]

def ports_b(g):
    k=g//3
    return [3*i+1 for i in range(k)]+[3*i+2 for i in range(k,23)]

allgeoms=[]
for gl in range(0,70,3):
    for gb in range(0,70,3):
        if gl and gb:continue
        l,b=ports_a(gl),ports_a(gb)
        assert l==ports_b(gl) and b==ports_b(gb)
        sources={(1,y) for y in l}|{(x,1) for x in b}
        I={(1,y) for y in range(1,70)}|{(x,1) for x in range(1,70)}
        cap=46
        for x,y in sources:
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                possible=False
                for off in range(3):
                    ax,ay=((x+1,y-off) if dx==1 else (x-3,y-off) if dx==-1 else (x-off,y+1) if dy==1 else (x-off,y-3))
                    if min(ax,ay)<1 or max(ax,ay)>67:continue
                    body={(ax+i,ay+j) for i in range(3) for j in range(3)}
                    if not body&sources:possible=True
                cap+=possible
        inner_cover=[]
        for x in range(1,68):
            for y in range(1,68):
                if x!=1 and y!=1:continue
                body={(x+i,y+j) for i in range(3) for j in range(3)}
                if not body&sources:inner_cover.append((x,y,len(body&I)))
        assert len(sources)==46 and len(I)==137 and len(I-sources)==91
        assert cap<=93 and len(inner_cover)<=1 and all(n==3 for _,_,n in inner_cover)
        # A 2x2 pole intersecting both arms is always excluded by source occupancy.
        assert {(1,1),(1,2),(2,1),(2,2)}&sources
        allgeoms.append({'left_gap':gl,'bottom_gap':gb,'source_count':46,'geometric_interface_cap':cap,'possible_inner_small_machines':inner_cover})

heights={2:[],3:[]}
for a in (2,3):
    for g in range(0,70,3):
        pp=ports_a(g)
        for b in range(2,65):
            for h in range(6,71-b):
                m=sum(b<=y<b+h for y in pp);ends=1 if b+h==70 else 2
                if m<=ends*(a-1):heights[a].append((h,b+h==70,g,b,m))
height_summary={str(a):{'max_height':max(t[0] for t in rows),'max_top_height':max([t[0] for t in rows if t[1]],default=0)} for a,rows in heights.items()}
assert height_summary=={'2':{'max_height':9,'max_top_height':0},'3':{'max_height':15,'max_top_height':8}}
heights_b={}
for a in (2,3):
    maxima=[0,0]
    for k in range(24):
        p=ports_b(3*k)
        prefix=[sum(t<j for t in p) for j in range(71)]
        for lo,hi in itertools.combinations(range(2,71),2):
            if hi-lo<6:continue
            top=int(hi==70)
            if prefix[hi]-prefix[lo]<=(2-top)*(a-1):maxima[top]=max(maxima[top],hi-lo)
    heights_b[str(a)]={'max_height':max(maxima),'max_top_height':maxima[1]}
assert heights_b==height_summary

core_intersections=set()
for start in range(-70,9):
    for length in range(6,71):
        interval=set(range(start,start+length))
        if interval&{1,4,7}:continue
        contact=tuple(sorted(interval&set(range(9))))
        core_intersections.add(contact)
assert core_intersections=={(),(0,),(8,)}
core_b=set()
for a,b in [(-70,0),(2,3),(5,6),(8,78)]:
    if b-a+1>=6:core_b.add(tuple(x for x in range(9) if a<=x<=b))
assert core_b=={(0,),(8,)}

edge_bounds=[]
for w,h in [(30,37),(37,30)]:
    for a in range(4,71-w):
        for b in range(4,71-h):
            top=b+h==70;right=a+w==70
            L=138-(w if top else 0)-(h if right else 0)
            k=2+int(top!=right)
            t=1 if top and right else 2
            xb=math.ceil((L-14-8*t-5*k)/6)
            xn=math.ceil((L-14-5*k)/6)
            edge_bounds.append({'rectangle':[a,b,w,h],'contact':int(top)+int(right),'L':L,'segments':k,'with_one_extra_X_min':xb,'no_extra_X_min':xn})
summary={str(contact):{'extra':min(r['with_one_extra_X_min'] for r in edge_bounds if r['contact']==contact),'no_extra':min(r['no_extra_X_min'] for r in edge_bounds if r['contact']==contact)} for contact in range(3)}
assert summary=={'0':{'extra':17,'no_extra':19},'1':{'extra':10,'no_extra':12},'2':{'extra':7,'no_extra':8}}
# Independent integer search solves L <= 6X+14c+8t+5k over allowed c,t.
summary_b={}
for contact,L,k,tmax in [(0,138,2,2),(1,101,3,2),(2,71,2,1)]:
    summary_b[str(contact)]={}
    for key,tmax0 in [('extra',tmax),('no_extra',0)]:
        summary_b[str(contact)][key]=next(x for x in range(139) if any(L<=6*x+14*c+8*t+5*k for c in range(2) for t in range(tmax0+1)))
assert summary_b==summary

scope_a=json.loads((out/'scope_a.json').read_text());scope_b=json.loads((out/'scope_b.json').read_text())
assert scope_a['cases']==scope_b['cases'] and scope_a['incompatible_fixed_machine']==scope_b['incompatible_fixed_machine']
assert scope_a['maximum']==scope_b['maximum']==91 and not scope_a['violations'] and not scope_b['violations']
result={'geometries':allgeoms,'core_contacts':[list(v) for v in sorted(core_intersections)],'corridor_heights':height_summary,'boundary_X_minima':summary,'boundary_cases':edge_bounds,
 'scope_agreement':{'cases':len(scope_a['cases']),'skipped_fixed_machine_overlap':scope_a['incompatible_fixed_machine'],'maximum_N_w_d':91,'a_b_identical':True}}
(out/'geometry_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('geometries','boundary_cases')},ensure_ascii=False))
