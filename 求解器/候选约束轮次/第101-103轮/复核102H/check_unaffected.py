"""Selected unchanged candidates: 400-step stock, saturated phase/parity."""
from itertools import product,permutations
from pathlib import Path
from random import Random
import json
from plant_models import Absolute,Countdown
from check_plants import step_pair,settings

OUT=Path(__file__).resolve().parent

def main():
    rng=Random(2102931)
    cases=steps=0
    min_buffer=[50]*4
    for trial in range(32):
        k=2+trial%2
        lengths=[rng.randrange(1,10) for _ in range(4)]
        initial=dict(machines=[[50,50-y,rng.choice([None,0,1,8])] for y in [2,1,1,k]],
                     roads=[[8]*l for l in lengths])
        for mode in ['retain','clear']:
            a=Absolute(initial,k,k); b=Countdown(initial,k,k)
            for t in range(1,401):
                cfg=settings(rng,t,k,mode,frequency=1)
                step_pair(a,b,t,cfg)
                for i,y in enumerate([2,1,1,k]):
                    assert a.m[i][2] is not None
                    assert a.m[i][1]>=50-3*y
                    min_buffer[i]=min(min_buffer[i],a.m[i][1])
                steps+=1
            cases+=1
    phase_pairs=parity_cases=0
    for p,q in permutations(range(8),2):
        events=sorted([(p+8*j,0) for j in range(40)]+[(q+8*j,1) for j in range(40)])
        word=[ch for t,ch in events]
        assert all(word[j]!=word[j+1] for j in range(len(word)-1))
        phase_pairs+=1
        for batches in range(1,9):
            for species in product([0,1],repeat=batches):
                items=[a for a in species for _ in range(2)]
                counts=[[0,0],[0,0]]
                for j,a in enumerate(items): counts[word[j]][a]+=1
                expected=[species.count(a) for a in [0,1]]
                assert counts==[expected,expected]
                parity_cases+=1
    result=dict(C21=dict(cases=cases,compared_steps=steps,min_C_A_B_K_output=min_buffer,violations=0),
                E29_E31=dict(phase_pairs=phase_pairs,even_batch_species_cases=parity_cases))
    (OUT/'unaffected.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__': main()
