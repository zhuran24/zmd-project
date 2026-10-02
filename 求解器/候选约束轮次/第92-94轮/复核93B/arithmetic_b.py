"""Independent review B: 20-tick integer backward demand; port-vector enumeration.
Does not import A or any derivation-seat code. Comparison happens only at the end.
"""
import itertools, json
from pathlib import Path
from fractions import Fraction

out=Path(__file__).resolve().parent
battery,capsule=12,11
parts=10*battery;dense_source=15*battery;bottles=10*capsule;fine_flower=10*capsule
steel=parts+2*bottles;dense_iron=steel;iron_powder=2*dense_iron;source_powder=2*dense_source
flower_powder=2*fine_flower;sand_powder=dense_iron+dense_source+fine_flower
flower_crush=flower_powder//2;sand_crush=sand_powder//3
assert flower_powder%2==sand_powder%3==0
recipe_batches=[source_powder,iron_powder,flower_crush,sand_crush,iron_powder,steel,0,dense_iron,dense_source,fine_flower,bottles,parts,2*flower_crush,2*sand_crush,flower_crush,sand_crush,battery,capsule]
flow_items=[iron_powder,source_powder,iron_powder,iron_powder,source_powder,sand_powder,2*sand_crush,2*sand_crush,2*flower_crush,2*flower_crush,flower_powder,dense_iron,steel,dense_source,fine_flower,parts,bottles,battery,capsule]
grouping={'粉碎机':range(4),'精炼炉':range(4,7),'研磨机':range(7,10),'塑形机':[10],'配件机':[11],'种植机':[12,13],'采种机':[14,15],'封装机':[16],'灌装机':[17]}
counts={m:(sum(recipe_batches[i]*(5 if i>=16 else 1) for i in ids)+19)//20 for m,ids in grouping.items()}
areas=[counts[m]*a for m,a in [('粉碎机',9),('精炼炉',9),('研磨机',24),('塑形机',9),('配件机',9),('种植机',25),('采种机',25),('封装机',24),('灌装机',24)]]
input_multipliers=[1,1,1,1,1,1,1,3,3,3,2,1,1,1,1,1,25,20]
output_multipliers=[1,1,2,3,1,1,1,1,1,1,1,1,1,1,2,2,1,1]
inputs=sum((sum(recipe_batches[i]*input_multipliers[i] for i in ids)+19)//20 for ids in grouping.values())
outputs=sum(max((sum(recipe_batches[i]*output_multipliers[i] for i in ids)+19)//20,3 if m in ('封装机','灌装机') else 0) for m,ids in grouping.items())

def vectors(width,cap):
    best=[100000]*(cap*2+1)
    for vector in itertools.product((0,1,2),repeat=width):
        load=sum(vector)
        if load>cap*2:continue
        present=[i for i,v in enumerate(vector) if v]
        cost=0
        for i in range(width):
            if not vector[i]:continue
            before=[j for j in present if j<i];after=[j for j in present if j>i]
            if before and i-before[-1]<=3:cost+=vector[i]
            if after and after[0]-i<=3:cost+=vector[i]
        best[load]=min(best[load],cost)
    return best

def knapsack(cost,need,last):
    state=[100000]*(need+1);state[0]=0;ans={}
    for n in range(1,last+1):
        nxt=[100000]*(need+1)
        for t in range(need+1):
            nxt[t]=min(state[t-q]+cost[q] for q in range(min(t,len(cost)-1)+1))
        state=nxt
        if state[need]<100000:ans[str(n)]=str(Fraction(state[need],2))
    return ans

specs={'研磨机':(6,3,189,48),'塑形机':(3,2,22,12),'封装机':(6,5,30,8),'灌装机':(6,4,22,6)}
single={m:vectors(w,c) for m,(w,c,_,_) in specs.items()}
tables={m:knapsack(single[m],need,n) for m,(_,_,need,n) in specs.items()}
pairs={str(t):sorted({(min(w,h),max(w,h)) for w in range(6,69) for h in range(6,69) if w*h==t}) for t in [1090,1107,1110,1111,1112]}
pj=[]
for p in range(10,70):
    maxj=min(p,(23*p-217)//10,(54*p-520)//25)
    for j in range(maxj+1):
        b=311-16*p+2*j
        if 2*b>=219:pj.append([p,j,b,199-16*p+2*j])
result={'method':'B: integer batches per 20 tick; direct port-flow vectors; array min-plus recurrence',
 'recipe_rates_r0':[str(Fraction(x,20)) for x in recipe_batches], 'machine_counts':counts,
 'manufacturing_area':sum(areas),'total_item_output':str(Fraction(sum(flow_items),20)),
 'machine_input_ports':inputs,'machine_output_ports_active_products':outputs,'interfaces':inputs+outputs+52+2,
 'single_costs_doubled':single,'weight_tables':tables,'factorizations':pairs,'pj_1110':pj}
result['extra_global_area_upper']=str(max(Fraction(4751-16*p+2*min(p,(23*p-217)//10,(54*p-520)//25),4)-Fraction(287,8) for p in range(10,348)))
(out/'arithmetic_b.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
a=json.loads((out/'arithmetic_a.json').read_text())
for key in ['recipe_rates_r0','machine_counts','manufacturing_area','total_item_output','machine_input_ports','machine_output_ports_active_products','interfaces','single_costs_doubled','weight_tables','pj_1110']:
    assert a[key]==result[key],(key,a[key],result[key])
assert a['factorizations']=={k:[list(p) for p in v] for k,v in pairs.items()}
print('A/B exact comparison PASS: recipe rates, counts, area, item flow, single costs, every group table, P/J, factorizations')
