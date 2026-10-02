#!/usr/bin/env python3
"""Local checks for the temporary rules; no source simulator files are edited.

Only directed belt/gate fixtures are used. Bridge rules are not simulated.
The optional reset diagnostic is labelled separately from adopted rule claims.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import importlib.util
import json
import random
from itertools import permutations, product
from pathlib import Path

HERE=Path(__file__).resolve().parent

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,HERE/filename)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod
    spec.loader.exec_module(mod)
    return mod

def temporary_world(sim):
    class TemporaryWorld(sim.World):
        def judge_component(self,u):
            if u.name in self.judged:
                return
            if not u.splitter and u.output_channels:
                assert len(u.output_channels)==1, 'directed-path fixtures only'
                channel=u.output_channels[0]
                item=u.ready_item(self)
                # Empty/immature items and immediate-return directions do not
                # trigger the receiver's grouped judgement under temporary #1.
                if item is None or item.previous==channel.dst.name:
                    self.judged.add(u.name)
                    u.judge(self)
                    return
                dst=channel.dst
                candidates={c for c in dst.input_channels
                    if c.src.component and not c.src.splitter and c.src.name not in self.judged}
                channels=dst.channels('input',self,candidates)
                for c in channels:
                    self.judged.add(c.src.name)
                for c in channels:
                    self.log(c.src,'judge',layer=self.layers[c.src.name],trigger=u.name)
                    self.transfer(c)
            else:
                self.judged.add(u.name)
                u.judge(self)
    return TemporaryWorld

def check_s06_s07():
    path=HERE/'s06_s07_verify.py'
    code=path.read_text().split("\nresult={'cases':",1)[0]
    ns={'__file__':str(path),'__name__':'temporary_s06_s07_definitions'}
    exec(compile(code,str(path),'exec'),ns)
    ns['sim'].World=temporary_world(ns['sim'])
    traces={}
    for case,count in [('s06',18),('s07',400)]:
        actual,events=ns['sim2_run'](case,count)
        expected=ns['table_run'](case,count)
        assert actual==expected
        traces[case]={'rows':actual,'events':events}
    cases=[0,0]
    for po in permutations(['KA','KB']):
        for no in permutations(['K','G']):
            a,_=ns['sim2_run']('s06',9,list(po),no)
            b=ns['table_run']('s06',9,list(po),no)
            assert a==b
            assert sum(len(r['machines']['K']['sent']) for r in a[:8])==1
            cases[0]+=1
    for po in permutations(['KG0','KG1','KG2']):
        for no in permutations(['C','A','B','K','G']):
            ports=['CA','CB','AC','BK']+list(po)
            a,_=ns['sim2_run']('s07',3,ports,no)
            b=ns['table_run']('s07',3,ports,no)
            assert a==b
            assert a[0]['machines']['K']['inputs']['plant']==49
            assert a[1]['machines']['K']['inputs']['plant']==50
            cases[1]+=1
    assert cases==[2*2,6*120]
    (HERE/'temporary_s06_s07_trace.json').write_text(json.dumps(traces,ensure_ascii=False,indent=2))
    return {'order_cases':cases,'two_encodings_agree':True,
            'S06_first_tick_total':1,'S07_input_steps_0_1':[49,50],
            'finite_plant_steps_compared':400,
            'scope':'Order sweeps are a superset of orders induced by construction; universal checks remain valid.'}

def check_s08():
    probe=load('temporary_s08_probe','s08_s09_probe.py')
    small=load('temporary_s08_small','s08_s09_independent.py')
    probe.m.World=temporary_world(probe.m)
    rng=random.Random(8099202)
    states=0
    for case in range(160):
        counts=[(rng.randrange(51),rng.randrange(51)) for _ in range(4)]
        ages=[[rng.choice([None,*range(9)])] for _ in range(4)]
        phase=[rng.choice([None,*range(1,9)]) for _ in range(4)]
        first=rng.choice(['A','B'])
        a=small.Small(counts,ages,phase,first)
        w,ms,rs=probe.build((1,1,1,1),counts,ages,phase,first)
        for step in range(160):
            a.step();w.step()
            b={'in':[len(x.slots[0]) for x in ms],'out':[len(x.output) for x in ms],
               'rem':[x.remaining for x in ms],'cache':[len(x.cache) for x in ms],
               'ages':[None if r.cells[0] is None else min(8,w.t-1-r.cells[0].entered)
                       for r in rs+[w.lookup['O1'],w.lookup['O2']]]}
            assert a.flat()==b
            assert a.phi()==probe.phi(ms,rs)
            if step==0:
                bound=min(a.phi()-.5,178)
            assert a.phi()>=bound
            states+=1
    return {'cases':160,'complete_states_compared':states,
            'two_encodings_agree':True,'scope':'No intervening offline reset; changed rule 31 is exercised.'}

def check_rebuild_robust_properties():
    probe=load('temporary_rebuild_probe','s08_s09_probe.py')
    small=load('temporary_rebuild_small','s08_s09_independent.py')
    probe.m.World=temporary_world(probe.m)
    rng=random.Random(9281002)
    compared=0; eligible=0; resets=0
    for case in range(80):
        counts=[(rng.randrange(51),rng.randrange(51)) for _ in range(4)]
        ages=[[rng.choice([None,*range(9)])] for _ in range(4)]
        phase=[rng.choice([None,*range(1,9)]) for _ in range(4)]
        a=small.Small(counts,ages,phase,'A')
        w,ms,rs=probe.build((1,1,1,1),counts,ages,phase,'A')
        initial_phi=None
        for step in range(160):
            if step and (case%3==0 or step%8==0 or rng.randrange(8)==0):
                first=rng.choice(['A','B'])
                # A genuine construction order: all nontransport units first,
                # then the named belts. Channel time=max(endpoint build times).
                belts=['CA','CB','AC','BK','O1','O2']
                if first=='B':
                    belts[:2]=['CB','CA']
                order=['C','A','B','K','sink']+belts
                rank={name:i for i,name in enumerate(order)}
                for u in w.nodes:
                    u.output_cursor=u.input_cursor=0
                    for c in u.output_channels:
                        c.connected=max(rank[c.src.name],rank[c.dst.name])
                        u.last_output[c]=-1
                comps=sorted((u for u in w.nodes if u.component),
                    key=lambda u:(w.layers[u.name],min(c.connected for c in u.output_channels)))
                nts=sorted((u for u in w.nodes if not u.component),
                    key=lambda u:min((c.connected for c in u.output_channels),default=999))
                w.order=comps+nts
                a.last=[[-1,-1],[-1],[-1],[-1,-1]]
                a.cursor=0;a.first=first
                resets+=1
            a.step();w.step()
            b={'in':[len(x.slots[0]) for x in ms],'out':[len(x.output) for x in ms],
               'rem':[x.remaining for x in ms],'cache':[len(x.cache) for x in ms],
               'ages':[None if r.cells[0] is None else min(8,w.t-1-r.cells[0].entered)
                       for r in rs+[w.lookup['O1'],w.lookup['O2']]]}
            assert a.flat()==b,(case,step,a.flat(),b)
            if step==0:
                initial_phi=a.phi()
                eligible+=initial_phi>=1
            if initial_phi>=1:
                assert a.phi()>=.5
            compared+=1
    waits={}
    for k in (1,2,3):
        maximum=0;cases=0
        # Initially every outlet empty is worst for the target: each other
        # outlet can take once, and residence forbids taking again in k<=3 steps.
        for orders in product(list(permutations(range(k))),repeat=k):
            occupied=set();target_step=None
            for step,order in enumerate(orders):
                j=next(x for x in order if x not in occupied)
                occupied.add(j)
                if j==0 and target_step is None:
                    target_step=step+1
            assert target_step is not None and target_step<=k
            maximum=max(maximum,target_step);cases+=1
        assert cases==len(list(permutations(range(k))))**k
        assert maximum==k
        waits[str(k)]={'priority_sequences':cases,'maximum_judgements':maximum,
                       'independent_pigeonhole_bound':k}
    # Critical, rule-reachable startup: only C has one plant, all paths empty.
    # C starts at step 0. At step 8 send the first seed to B; the other seed
    # must go to A at step 9 even if all success records are reset every step.
    w,ms,rs=probe.build((1,1,1,1),[(1,0),(0,0),(0,0),(0,0)],
                       [[None]]*4,None,'B')
    a=small.Small([(1,0),(0,0),(0,0),(0,0)],[[None]]*4,[None]*4,'B')
    critical=[]
    for step in range(11):
        rank={name:i for i,name in enumerate(['C','A','B','K','sink','CB','CA','AC','BK','O1','O2'])}
        for u in w.nodes:
            u.output_cursor=u.input_cursor=0
            for c in u.output_channels:
                c.connected=max(rank[c.src.name],rank[c.dst.name]);u.last_output[c]=-1
        w.order=sorted((u for u in w.nodes if u.component),key=lambda u:(w.layers[u.name],min(c.connected for c in u.output_channels)))+sorted((u for u in w.nodes if not u.component),key=lambda u:min((c.connected for c in u.output_channels),default=999))
        a.last=[[-1,-1],[-1],[-1],[-1,-1]];a.cursor=0;a.first='B'
        w.step();a.step()
        assert probe.phi(ms,rs)==a.phi()
        expected_phi=.5 if step==8 else 1
        assert a.phi()==expected_phi
        critical.append({'step':step,'phi':a.phi(),'C_output':len(ms[0].output),
                         'CA_head_full':rs[0].cells[0] is not None,
                         'CB_head_full':rs[2].cells[0] is not None})
    return {'conditional_reset_mode':True,'not_asserting_reset_is_required_by_temporary_rule_4':True,
            'plant_cases':80,'cases_with_initial_phi_at_least_one':eligible,
            'complete_states_compared':compared,'construction_derived_rebuilds':resets,
            'two_encodings_agree':True,'positive_inventory_violations':0,
            'S07_refill_independent_of_history':waits,
            'critical_half_unit_startup':critical,
            'critical_phi_at_steps_8_9':[critical[8]['phi'],critical[9]['phi']]}

def check_s10():
    mod=load('temporary_s10','s10_check.py')
    mod.sim.World=temporary_world(mod.sim)
    fixed=mod.wrong_slot_fixed_point()
    # New candidates use only belts. Verify every former belt-only loop case.
    count=0
    periods=set()
    for l1 in range(1,5):
        for l2 in range(1,5):
            for phase in range(1,9):
                for reverse in (False,True):
                    w,ms,paths=mod.make_world((l1,l2),('belt','belt'),phase,reverse)
                    other=mod.CountEngine((l1,l2),phase,reverse)
                    seen={}
                    for t in range(160):
                        w.step();other.step()
                        x=mod.sim_state(w,ms,paths)
                        assert x==other.state()
                        assert all(v[2] or v[3] for v in x[0])
                        if x in seen:
                            periods.add(t+1-seen[x]);break
                        seen[x]=t+1
                    else:
                        raise AssertionError('cycle not reached')
                    count+=1
    assert count==4*4*8*2
    return {'pure_belt_cases':count,'periods':sorted(periods),'two_encodings_agree':True,
            'original_counterexample':fixed}

def reset_diagnostic():
    # Rule #4 explicitly changes construction order. Whether it ALSO resets
    # last-success history is not stated. Demonstrate why the distinction matters.
    # With exact 8-step outlet service and only 1 item initially remaining,
    # retaining history selects B at step 8, whereas resetting selects A again.
    output=1
    entered=[None,None]
    last=[-1,-1]
    rows=[]
    for t in range(10):
        for j in range(2):
            if entered[j] is not None and t-entered[j]>=8:
                entered[j]=None
        if t==8:
            output+=2
            last=[-1,-1]
        chosen=None
        for j in sorted(range(2),key=lambda j:(last[j],j)):
            if output and entered[j] is None:
                chosen=j;output-=1;entered[j]=t;last[j]=t;break
        rows.append({'step':t,'sent':chosen,'output':output,'last_success':last[:]})
    assert [r['sent'] for r in rows if r['sent'] is not None]==[0,0,1]
    return {'conditional_on_reset':True,'not_a_claim_that_the_temporary_text_requires_reset':True,
            'successful_outlets':[0,0,1],'rows':rows}

def main():
    temp=HERE.parent/'临时规则.md'
    result={'temporary_rules_sha256':hashlib.sha256(temp.read_bytes()).hexdigest(),
            'S06_S07':check_s06_s07(),'S08':check_s08(),'S10':check_s10(),
            'rebuild_robust_properties':check_rebuild_robust_properties(),
            'history_reset_diagnostic':reset_diagnostic(),
            'admission_gate_loss':'No positive lower bound is simulated or assumed; final S10 excludes gates.'}
    (HERE/'temporary_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in {'S10','history_reset_diagnostic'}},ensure_ascii=False,indent=2))
    print(json.dumps({'S10_pure_belt_cases':result['S10']['pure_belt_cases'],
                      'S10_fixed_point_stable_from_step':result['S10']['original_counterexample']['stable_from_step']},ensure_ascii=False))

if __name__=='__main__':
    main()
