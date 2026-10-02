from pathlib import Path
import json, random, hashlib, itertools, time
from independent_models import AgeModel, TimestampModel

HERE = Path(__file__).resolve().parent

def dump(name, value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def dense_config(rng, k, n):
    lengths=[rng.choice([1,2,3,5,9,17]) for _ in range(4)]+[1]*n
    return {'k':k,'inputs':[50]*4,'outputs':[50]*4,
            'remaining':[rng.randrange(9) for _ in range(4)],
            'roads':[[rng.randrange(9) for _ in range(m)] for m in lengths]}

def controls(rng, step, edges, n, scenario):
    # Every drain acts only on a mature head; deliberately more general than
    # any particular realizable downstream network.
    if scenario%5==0:
        drain=[True]*n
    elif scenario%5==1:
        drain=[step%(9+j*2)==0 for j in range(n)]
    elif scenario%5==2:
        drain=[step%211 not in range(25,181) for _ in range(n)]
    elif scenario%5==3:
        drain=[rng.random()<0.12 for _ in range(n)]
    else:
        drain=[step%(40+j*3) in (0,1) for j in range(n)]
    permutation=list(range(edges))
    rng.shuffle(permutation)
    order=list(range(4)); rng.shuffle(order)
    return drain,permutation,order

def verify_pair(a,b,drain,connection,power,order):
    ea=a.step(drain,connection,power,order)
    eb=b.step(drain,connection,power,order)
    assert ea==eb
    assert a.state()==b.state(), {'t':a.t,'a':a.state(),'b':b.state()}
    assert a.phi2()==b.phi2()
    assert a.events==b.events
    return ea

def dense_trials():
    rng=random.Random(9300401)
    stats={'cases':0,'paired_steps':0,'min_B_input':50,'min_K_input':50,
           'min_B_output':50,'min_K_output_by_k':{'2':50,'3':50},
           'max_outlet_wait_by_n':{},'failure':None,'complete_snapshot_hash':None}
    digest=hashlib.sha256()
    for k in (2,3):
        for n in range(k+1):
            for case in range(40):
                config=dense_config(rng,k,n)
                a,b=AgeModel(config),TimestampModel(config)
                deadline=[None]*n
                for step in range(1,1801):
                    drain,connection,order=controls(rng,step,len(config['roads']),n,case)
                    empty=verify_pair(a,b,drain,connection,(True,)*4,order)
                    assert all(r>=0 for r in a.r), (config,step,a.state())
                    assert a.i[2]>=49 and a.i[3]>=49
                    assert a.o[2]>=49 and a.o[3]>=50-k
                    assert not empty[2] or 2 in a.events
                    assert not empty[3] or 3 in a.events
                    for j in range(n):
                        if empty[j+4] and deadline[j] is None:
                            deadline[j]=step
                        if j+4 in a.events:
                            assert deadline[j] is not None
                            wait=step-deadline[j]
                            assert wait <= n-1
                            stats['max_outlet_wait_by_n'][str(n)]=max(wait,stats['max_outlet_wait_by_n'].get(str(n),0))
                            deadline[j]=None
                        if deadline[j] is not None:
                            assert step-deadline[j]<n-1
                    stats['min_B_input']=min(stats['min_B_input'],a.i[2])
                    stats['min_K_input']=min(stats['min_K_input'],a.i[3])
                    stats['min_B_output']=min(stats['min_B_output'],a.o[2])
                    stats['min_K_output_by_k'][str(k)]=min(stats['min_K_output_by_k'][str(k)],a.o[3])
                    digest.update(repr(a.state()).encode())
                    stats['paired_steps']+=1
                stats['cases']+=1
    stats['complete_snapshot_hash']=digest.hexdigest()
    stats['scope']='All conditions tested on an age/state superset; this is not a completeness certificate or a layout.'
    dump('dense_results.json',stats)
    return stats

def arbitrary_trials():
    rng=random.Random(9300402)
    stats={'cases':0,'paired_steps':0,'BB_events':0,'lowest_BB_excess_phi2':None,
           'candidate_violations':0,'original_176_violations_after_normalization':0,
           'min_2phi_loss':0}
    smallest=None
    for case in range(500):
        k=rng.choice([2,3]); n=rng.randrange(k+1)
        lengths=[rng.choice([1,2,4,7]) for _ in range(4)]+[1]*n
        dense=case%4==0
        config={'k':k,'inputs':[(50 if dense else rng.randrange(51)) for _ in range(4)],
                'outputs':[(50 if dense else rng.randrange(51)) for _ in range(4)],
                'remaining':[rng.randrange(-1,9) for _ in range(4)],
                'roads':[[rng.randrange(9) if dense else rng.randrange(-1,9) for _ in range(m)] for m in lengths]}
        a,b=AgeModel(config),TimestampModel(config)
        prev=None; initial=None; bound=None; oldbound=None
        for step in range(1,1601):
            drain,connection,order=controls(rng,step,len(lengths),n,case)
            power=(True,True,step%137<100,step%173<130) if case%3==0 else (True,)*4
            verify_pair(a,b,drain,connection,power,order)
            stats['paired_steps']+=1
            if step==16:
                initial=a.phi2()
                bound=min(initial-1,2*(lengths[0]+lengths[1]+150))
                oldbound=min(initial-1,2*(lengths[0]+lengths[1]+176))
                prev=None
            elif step>16:
                assert a.phi2()>=bound
                if a.phi2()<oldbound:
                    stats['original_176_violations_after_normalization']+=1
                stats['min_2phi_loss']=min(stats['min_2phi_loss'],a.phi2()-initial)
                for e in a.events:
                    if e in (0,2):
                        if prev==2 and e==2:
                            value=a.phi2()-2*(lengths[0]+lengths[1])
                            stats['BB_events']+=1
                            assert value>=300
                            if stats['lowest_BB_excess_phi2'] is None or value<stats['lowest_BB_excess_phi2']:
                                stats['lowest_BB_excess_phi2']=value
                                smallest={'config':config,'step':step,'state':a.state(),'excess_phi2':value}
                        prev=e
        stats['cases']+=1
    dump('arbitrary_results.json',stats)
    dump('smallest_BB.json',smallest)
    return stats

def low_cycle():
    # Reproduce the published scalar certificate from its explicit initial data,
    # with a legal manufacturing start at the first full step. No author code.
    cfg={'k':3,'inputs':[4,0,0,0],'outputs':[1,0,0,0],
         'remaining':[-1]*4,'roads':[[-1] for _ in range(7)]}
    a,b=AgeModel(cfg),TimestampModel(cfg)
    saved=[]
    for t in range(1,30019):
        # Each abstract downstream outlet removes a token after 9 steps.
        # At the preceding step a capped age of 8 means it is now eligible.
        verify_pair(a,b,[row[0]==8 for row in a.roads[4:]],list(range(7)),(True,)*4,(0,1,2,3))
        if t>=30000:
            state=a.state()
            state['relative_last']=[t-v for v in state.pop('last')]
            saved.append({'t':t,'phi2':a.phi2(),'state':state})
    # Compare all inventory/age/remaining/history values 9 steps apart;
    # counters must grow by one batch in each machine.
    check=[]
    for j in range(10):
        u,v=saved[j]['state'],saved[j+9]['state']
        assert all(u[key]==v[key] for key in ('inputs','outputs','remaining','roads','relative_last'))
        check.append([v['batches'][m]-u['batches'][m] for m in range(4)])
    assert all(delta==[1]*4 for delta in check)
    cycle=saved[1:10]
    result={'period_steps':9,'phi2_range':[min(x['phi2'] for x in cycle),max(x['phi2'] for x in cycle)],
            'empty_counts':[sum(x['state']['remaining'][m]<0 for x in cycle) for m in range(4)],
            'batches_per_period':check[0],'cycle':cycle,
            'status':'external 9-step removal is an abstract service, not a demonstrated legal layout'}
    # Read certificate DATA only, after independently deriving the cycle.
    original=json.loads((HERE.parent/'推导92D'/'plant_nine_certificate.json').read_text())
    def own_signature(x):
        st=x['state']
        return (st['inputs'],st['outputs'],st['remaining'],st['roads'][:4],
                [st['relative_last'][0],st['relative_last'][2]],x['phi2'])
    def original_signature(x):
        return (x['i'],x['o'],[(-1 if r==0 else 0 if r==-1 else r) for r in x['r']],
                [x['routes'][j] for j in (0,2,1,3)],
                [x['t']-v for v in x['last']],x['phi2'])
    orig=[original_signature(x) for x in original['cycle']]
    own=[own_signature(x) for x in cycle]
    shifts=[d for d in range(9) if all(orig[j]==own[(j+d)%9] for j in range(9))]
    assert len(shifts)==1, (orig,own)
    result['published_core_certificate_equal_after_cyclic_shift']=shifts[0]
    dump('independent_nine_cycle.json',result)
    return {k:v for k,v in result.items() if k!='cycle'}

if __name__=='__main__':
    start=time.monotonic()
    print('dense',dense_trials(),flush=True)
    print('arbitrary',arbitrary_trials(),flush=True)
    print('nine_cycle',low_cycle(),flush=True)
    print('seconds',time.monotonic()-start,flush=True)
