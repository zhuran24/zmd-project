#!/usr/bin/env python3
"""Independent audit B: integer counts in 20 ticks, direct event sets, brute period counts.
The constants are read from the snapshot by the reviewer, not from audit A.
"""
from pathlib import Path
import json
D=Path(__file__).resolve().parent
# Propagate exactly 12 batteries and 11 capsules through their recipes.
battery,capsule=12,11
parts,bottles=10*battery,10*capsule
dense_source,fine_buck=15*battery,10*capsule
steel=parts+2*bottles
dense_blue=steel
blue_powder,source_powder,buck_powder=2*dense_blue,2*dense_source,2*fine_buck
sand_powder=dense_blue+dense_source+fine_buck
assert buck_powder%2==0 and sand_powder%3==0
buck_crush,sand_crush=buck_powder//2,sand_powder//3
buck_seed_batches,sand_seed_batches=buck_crush,sand_crush
buck_plants,sand_plants=2*buck_crush,2*sand_crush
blue_blocks,source_ore=blue_powder,source_powder
blue_ore=blue_blocks
batch_counts=[blue_blocks+source_ore+buck_crush+sand_crush,blue_ore+steel,
              dense_blue+dense_source+fine_buck,bottles,parts,
              buck_plants+sand_plants,buck_seed_batches+sand_seed_batches,battery,capsule]
factory_names=['粉碎机','精炼炉','研磨机','塑形机','配件机','种植机','采种机','封装机','灌装机']
capacity=[20]*7+[4,4]
minimum=[]
for required,cap in zip(batch_counts,capacity):
    n=0
    while cap*n<required:n+=1
    minimum.append(n)
flows={'蓝铁矿':blue_ore,'源矿':source_ore,'蓝铁块':blue_blocks,'蓝铁粉末':blue_powder,
 '源石粉末':source_powder,'砂叶粉末':sand_powder,'砂叶':sand_plants,'砂叶种子':sand_plants,
 '荞花':buck_plants,'荞花种子':buck_plants,'荞花粉末':buck_powder,'致密蓝铁粉末':dense_blue,
 '钢块':steel,'致密源石粉末':dense_source,'细磨荞花粉末':fine_buck,'钢制零件':parts,
 '钢质瓶':bottles,'高容谷地电池':battery,'精选荞愈胶囊':capsule}
# Compare bounds through integer inequalities, without floats or fractions.
alt_bounds=[next(n for n in range(7) if 2*n>=a+b) for a,b in [(3,2),(3,1),(2,1),(2,2)]]
closed=max(len([t for t in range(41) if t%8==p]) for p in range(8))
next8=max(len([t for t in range(1,9) if t%8==p]) for p in range(8))
# Residence convolution of periodic births: count surviving units before death after 16 steps.
stocks=[]
for phase in range(8):
    born=[t for t in range(-64,65) if t%8==phase]
    stocks.append([sum(b<=t<b+16 for b in born) for t in range(32)])
assert all(all(x==2 for x in row) for row in stocks)
# Count the four-group words by a transfer matrix instead of four nested loops.
word_counts=[]
for k in range(1,7):
    v=[1]*(k+1)
    for _ in range(3):v=[sum(v[:k-b+1]) for b in range(k+1)]
    word_counts.append(sum(v))
family_count=sum(word_counts[k-1]*(1<<k)*(1<<4)*2 for k in range(1,7))

# Direct joint-state counting and independent modular-arithmetic prediction.
# For every single marked list position, equality implies equality for any material list.
formula_cases=0; records=[]
for L in range(1,61):
    for k in range(1,7):
        counts=[[0]*k for _ in range(L)]
        p=j=0; steps=0
        while True:
            counts[p][j]+=1;steps+=1
            p=(p+1)%L;j=(j+1)%k
            if p==0 and j==0:break
        # Euclidean reduction encoded here independently of the joint-state traversal.
        a,b=L,k
        while b:a,b=b,a%b
        h=a
        assert steps==L*k//h
        for p in range(L):
            for j in range(k):
                expected=int(p%h==j%h)
                assert counts[p][j]==expected,(L,k,p,j,counts[p][j],expected)
                # Normalized fraction of total F; cross multiplication avoids rounding.
                assert counts[p][j]*L*k==h*expected*steps
                formula_cases+=1
        records.append({'L':L,'k':k,'h':h,'joint_successes':steps})
result={'status':'PASS','encoding':'integer recipe back-propagation and direct joint-state traversal',
 'batches_per_20_ticks':dict(zip(factory_names,batch_counts)),
 'machine_minimum':dict(zip(factory_names,minimum)),'machine_count':sum(minimum),
 'machine_area':sum(n*a for n,a in zip(minimum,[9,9,24,9,9,25,25,24,24])),
 'material_counts_per_20_ticks':flows,'total_flow_numerator':sum(flows.values()),'total_flow_denominator':20,
 'mixed_channel_bounds':alt_bounds,'closed_5_tick_one_port_events':closed,'box_conservative_bound':3*closed,
 'next_8_steps_one_port_events':next8,'plant_stock_total_bound':32*min(min(r) for r in stocks),
 'mean_stock_bound_numerators_per_20_ticks':{'荞花':2*buck_plants,'砂叶':2*sand_plants},
 'wireless_period_steps':sum(1 for n in range(1,100) if n<=5*8),
 'four_group_word_counts':word_counts,'reported_polling_family_count':family_count,
 'formula_parameter_pairs':len(records),'formula_indicator_equalities':formula_cases,'formula_periods':records}
(D/'arithmetic_batches.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','machine_minimum','machine_area','total_flow_numerator','reported_polling_family_count','formula_indicator_equalities']},ensure_ascii=False))
# Comparison runs only AFTER both independent calculations have completed.
other=json.loads((D/'arithmetic_matrix.json').read_text())
for k in ['machine_minimum','machine_count','machine_area','mixed_channel_bounds','closed_5_tick_one_port_events','box_conservative_bound','next_8_steps_one_port_events','plant_stock_total_bound','wireless_period_steps','four_group_word_counts','reported_polling_family_count']:
    assert result[k]==other[k],k
print('Independent arithmetic agreement: PASS')
