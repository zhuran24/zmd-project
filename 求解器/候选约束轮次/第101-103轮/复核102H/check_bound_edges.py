"""Targeted BB states, independent of the derivation's scripts and seeds."""
from itertools import product
from pathlib import Path
import json
from plant_models import Absolute,Countdown
from check_plants import step_pair

OUT=Path(__file__).resolve().parent

def main():
    cases=steps=bb=normal_bb=0
    least=10000; least_normal=10000
    witness=None
    for aq,cq,ar,cr,cb_age in product([49,50],[1,2,3,48,49,50],[0,1,7,8],[0,1,7,8],[None,6]):
        initial=dict(machines=[[50,cq,cr],[50,aq,ar],[0,0,None],[0,0,None]],
                     roads=[[8]*5,[8]*35,[cb_age]+[None]*10,[None]*5])
        a=Absolute(initial,2,0); b=Countdown(initial,2,0)
        phi0=a.phi2(); phi1=None
        trace=[]
        for t in range(1,25):
            setting=dict(offline=t in [4,11,12],clear=False,c_order=[1,0],k_order=[],
                         machine_order=[0,1,2,3],drain=[])
            phi=step_pair(a,b,t,setting)
            assert phi>=min(phi0-1,2*(40+150))
            if t==1: phi1=phi
            else: assert phi>=min(phi1-1,2*(40+176))
            trace.append(dict(step=t,phi2=phi,machines=a.canonical(t)[0],
                              events=[e for s,e in a.events if s==t]))
            if len(a.events)>=2 and a.events[-1][0]==t and a.events[-2][1]==a.events[-1][1]=='B':
                bb+=1
                delta=phi-2*40
                assert delta>=303
                if delta<least:
                    least=delta
                    witness=dict(initial=initial,trace=trace.copy(),phi0=phi0,offset2=delta)
                if a.events[-2][0]>=2:
                    normal_bb+=1
                    least_normal=min(least_normal,delta)
                    assert delta>=352
            steps+=1
        cases+=1
    assert least==303 and least_normal==352
    out=dict(cases=cases,compared_steps=steps,BB_events=bb,normal_BB_events=normal_bb,
             min_preparation_BB_offset2=least,min_normal_BB_offset2=least_normal,
             preparation_176_counterexample=witness)
    (OUT/'bound_edges.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='preparation_176_counterexample'}))

if __name__=='__main__': main()
