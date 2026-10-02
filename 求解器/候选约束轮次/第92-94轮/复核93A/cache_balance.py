#!/usr/bin/env python3
"""Why item-count conservation must not silently include manufacturing caches."""
from pathlib import Path
from fractions import Fraction
import json
D=Path(__file__).resolve().parent
A=json.loads((D/'arithmetic_matrix.json').read_text())
B=json.loads((D/'arithmetic_batches.json').read_text())
# Encoding A: actual solved rates of the two seed-extraction recipes.
in_rate=sum(Fraction(r['rate'])*sum(r['inputs'].values()) for r in A['recipes'] if r['factory']=='采种机')
out_rate=sum(Fraction(r['rate'])*sum(r['outputs'].values()) for r in A['recipes'] if r['factory']=='采种机')
# Encoding B: integer batch balance in a 20-tick cycle.
batches=B['batches_per_20_ticks']['采种机']
in2=Fraction(batches,20);out2=Fraction(2*batches,20)
assert (in_rate,out_rate)==(in2,out2)==(16,32)
assert in_rate-out_rate==-16
assert in_rate+batches//20-out_rate==0
out={'status':'PASS','collection':'全部采种机的制造缓存格，仅用于说明为何须排除缓存格',
 'input_per_20_ticks':batches,'output_per_20_ticks':2*batches,
 'q_items_per_tick':str(in_rate),'b_items_per_tick':'0','Q_items_per_tick':str(out_rate),
 'unaccounted_creation_items_per_tick':'16','q_plus_b_minus_Q':'-16',
 'two_encodings_agree':True,'time_counting':'20 tick数量均由完整循环的平均率折算，不要求任意20 tick子窗口相同',
 'scope':'若将来源定序泛称的物品格集合解释为可包含缓存格，守恒式必须加配方转化项。此记录不是完整布局反例。'}
(D/'cache_balance.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False))
