from pathlib import Path
from fractions import Fraction as F
from itertools import product
import hashlib, json, random
from independent_models import AgeModel, TimestampModel
HERE=Path(__file__).resolve().parent

def write(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def bridge_steps(mode, steps):
    # Actual ordered unit attempts for U belt, P bridge, Q bridge, D belt.
    entered=[-8]*4
    departures=[]
    trace=[]
    for t in range(steps):
        used=set()
        actions=[]
        def attempt(v):
            if v in used:
                return
            used.add(v)
            if entered[v] is None or t-entered[v]<8:
                return
            if v==3:
                entered[v]=None
                departures.append(t)
                actions.append('D->收货端')
            elif entered[v+1] is None:
                entered[v]=None
                entered[v+1]=t
                actions.append(['U->P','P->Q','Q->D'][v])
        attempt(3)
        if mode=='current':
            # Q's determination pulls P's other non-splitter upstream U.
            attempt(0)
        attempt(2);attempt(1);attempt(0)
        if entered[0] is None:
            entered[0]=t
            actions.append('源->U')
        if t<30:
            trace.append({'step':t,'actions':actions,'ages':[None if e is None else t-e for e in entered]})
    return departures,trace

def bridge_recurrence(mode,steps):
    # Independent FIFO event-time recurrence; cell initial tokens are mature.
    # With the current read, each vacancy of P misses U's determination.
    penalty=1 if mode=='current' else 0
    p_times=[0]
    while p_times[-1]+8+penalty<steps:
        p_times.append(p_times[-1]+8+penalty)
    # Initial D and Q tokens leave D at 0 and 8; each old P token
    # travels through Q and D, each residence taking another 8 steps.
    return [0,8]+[t+16 for t in p_times if t+16<steps]

def bridges():
    out={}
    for mode in ('current','proposed'):
        a,trace=bridge_steps(mode,12000)
        b=bridge_recurrence(mode,12000)
        assert a==b
        gaps=set(y-x for x,y in zip(a[2:],a[3:]))
        assert gaps==({9} if mode=='current' else {8})
        out[mode]={'delivered':len(a),'first_steps':a[:12],'steady_gaps':sorted(gaps),
                   'rate_per_tick':str(F(8,next(iter(gaps)))),'trace':trace,
                   'sha256_departure_steps':hashlib.sha256(json.dumps(a).encode()).hexdigest()}
    write('bridge_results.json',out)
    return {k:{q:v for q,v in d.items() if q!='trace'} for k,d in out.items()}

def chain_direct(ages,consumption):
    state=list(ages)
    stock=50
    outgoing=[[] for _ in ages]
    last=max(consumption)+8
    need=set(consumption)
    for t in range(1,last+1):
        for i,x in enumerate(state):
            if x>=0: state[i]=min(x+1,8)
        for i in reversed(range(len(state))):
            if state[i]<8: continue
            if i==len(state)-1:
                if stock>=50: continue
                stock+=1
            else:
                if state[i+1]>=0: continue
                state[i+1]=0
            state[i]=-1
            outgoing[i].append(t)
        if state[0]<0: state[0]=0
        if t in need: stock-=1
        assert stock>=49
    return [x[:len(consumption)] for x in outgoing]

def chain_event(ages,consumption):
    # First-principles recurrence in send number, not a step simulation.
    moved=[[] for _ in ages]
    for j,x in enumerate(consumption):
        for i in reversed(range(len(ages))):
            if j==0: mature=max(1,8-ages[i])
            else: mature=moved[max(i-1,0)][j-1]+8
            space=x+1 if i==len(ages)-1 else moved[i+1][j]
            moved[i].append(max(mature,space))
    return moved

def chains():
    count=0
    greatest=0
    digest=hashlib.sha256()
    for m in (1,2,3):
        for ages in product(range(9),repeat=m):
            for x1 in (1,4,8):
                for d1,d2 in product((8,9,17),repeat=2):
                    use=[x1,x1+d1,x1+d1+d2]
                    a=chain_direct(ages,use)
                    b=chain_event(ages,use)
                    assert a==b,(ages,use,a,b)
                    assert all(v<=x+8 for v,x in zip(a[-1],use))
                    greatest=max(greatest,max(v-x for v,x in zip(a[-1],use)))
                    digest.update(repr((ages,use,a)).encode())
                    count+=1
    rng=random.Random(9300403)
    for _ in range(1000):
        ages=[rng.randrange(9) for _ in range(rng.randrange(4,41))]
        use=[rng.randrange(1,9)]
        for j in range(11): use.append(use[-1]+rng.randrange(8,51))
        a=chain_direct(ages,use); b=chain_event(ages,use)
        assert a==b
        assert all(v<=x+8 for v,x in zip(a[-1],use))
        digest.update(repr((ages,use,a)).encode());count+=1
    result={'cases':count,'largest_observed_refill_delay_steps':greatest,
            'two_encodings_equal':True,'sha256':digest.hexdigest(),
            'coverage':'all ages for lengths 1..3 and selected demands; 1000 longer cases'}
    write('chain_results.json',result)
    return result

def boundary():
    rows=[]
    for q,rem in ((49,8),(49,7),(1,8),(1,7)):
        cfg={'k':2,'inputs':[50,50,0,0],'outputs':[q,50,0,0],
             'remaining':[rem,rem,-1,-1],
             'roads':[[0],[0],[-1],[-1],[-1],[-1]]}
        a,b=AgeModel(cfg),TimestampModel(cfg)
        p0=a.phi2(); snapshots=[]
        for t in range(1,25):
            a.step([True,True],list(range(6)))
            b.step([True,True],list(range(6)))
            assert a.state()==b.state() and a.phi2()==b.phi2()
            snapshots.append({'step':t,'phi2':a.phi2(),'state':a.state()})
        rows.append({'C_output':q,'initial_remaining':rem,'phi2_initial':p0,
                     'phi2_min':min(x['phi2'] for x in snapshots),
                     'old_bound_phi2':min(p0-1,356),
                     'normal_complete_step_compatible':rem<8,
                     'trace':snapshots})
    write('boundary_results.json',rows)
    return [{k:v for k,v in x.items() if k!='trace'} for x in rows]

def numbers():
    # Encoding A: direct weighted capacities and recipe equations.
    cap_a=sum([50,50,50,1,1,F(50,2)])
    empty_a=max(sum([0,50,50,0,1,F(50,2)]),sum([50,50,0,1,0,F(50,2)]))
    # Encoding B: independent enumeration over extremal corners for every slot.
    cap_b=F(0);empty_b=F(0)
    for ai,ao,ci,ac,cc,co in product((0,50),(0,50),(0,50),(0,1),(0,1),(0,50)):
        value=ai+ao+ci+ac+cc+F(co,2)
        cap_b=max(cap_b,value)
        if (ac==0 and ai==0) or (cc==0 and ci==0):
            empty_b=max(empty_b,value)
    assert cap_a==cap_b==177 and empty_a==empty_b==126
    source,biron=F(18),F(34)
    b_a=source/30;c_a=biron/40-source/60
    # Independent stoichiometric elimination: source -> powder -> concentrate
    # and iron -> steel, subtract battery parts, convert to bottles and capsules.
    concentrate=source/2
    b_b=concentrate/15
    steel=biron/2
    bottles=(steel-10*b_b)/2
    c_b=bottles/10
    assert b_a==b_b==F(3,5) and c_a==c_b==F(11,20)
    # Sum source-by-source versus destination-by-destination.
    links_by_origin=[52,34,34,18,68,44,17,17,6,9,6,6,6]
    links_by_destination=[34,34,18,34,18,68,44,17,17,15,12,6]
    assert sum(links_by_origin)==sum(links_by_destination)==317
    fleet=[69,51,32,6,6,34,17,3,3]
    fleet_groups=[52+17,34+17,17+9+6,5+1,6,17*2,11+6,3,3]
    assert sum(fleet)==sum(fleet_groups)==221
    result={'maximum_phi_offset':str(cap_a),'empty_cache_phi_offset':str(empty_a),
            'strict_high_threshold':str(empty_a+F(1,2)),
            'BB_conservative_offset':str(49+50+49+1+1),
            'BB_normal_step_offset':str(50+50+49+1+1+25),
            'battery_rate':str(b_a),'capsule_rate':str(c_a),
            'one_8_over_9_source_battery_bound':str((17+F(8,9))/30),
            'one_zero_source_battery_bound':str(F(17,30)),
            'machines':sum(fleet),'routes':sum(links_by_origin),
            'tick_to_steps':8,'two_encodings_equal':True}
    write('numbers.json',result)
    # Freeze evidence identities without reading any root-level homonyms.
    snapshot=HERE.parent/'前提快照'
    filenames=['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','求解充分条件.txt','不补的设定.txt']
    manifest={name:{'sha256':hashlib.sha256((snapshot/name).read_bytes()).hexdigest(),
                    'lines':len((snapshot/name).read_text().splitlines())} for name in filenames}
    write('premises.json',manifest)
    return result

if __name__=='__main__':
    print('bridge',bridges(),flush=True)
    print('chain',chains(),flush=True)
    print('boundary',boundary(),flush=True)
    print('numbers',numbers(),flush=True)
