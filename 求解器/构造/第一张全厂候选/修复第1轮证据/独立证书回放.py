#!/usr/bin/env python3
"""不运行LP；对保存的独立矩阵逐列复算零流最优性证书。"""
import json, hashlib
from pathlib import Path
from fractions import Fraction as Q
HERE=Path(__file__).resolve().parent
matrix=json.loads((HERE/'独立LP矩阵.json').read_text())
report=json.loads((HERE/'独立LP.json').read_text())
raw=(HERE.parent/'生成/候选.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()==report['candidate_sha256']
rows={r['name']:r for r in matrix['rows']}
assert len(rows)==len(matrix['rows'])
contradictions=[]
for name,r in rows.items():
    if not r['terms'] and (Q(r['rhs'])!=0 if r['relation']=='eq' else Q(r['rhs'])<0):contradictions.append(name)
assert len(contradictions)==5
assert set(contradictions)=={v['name'] for v in report['exact_contradictions']}
relaxed={name:{**r,'relation':'le' if name.startswith('source:') else r['relation']} for name,r in rows.items() if not name.startswith('target:')}
assert all(Q(r['rhs'])==0 if r['relation']=='eq' else Q(r['rhs'])>=0 for r in relaxed.values())
certificate=report['source_relaxed_max_total_channel_flow']['certificate']
col=[Q() for _ in matrix['variables']];bound=Q();seen=set()
for term in certificate['multipliers']:
    name=term['row'];assert name not in seen;seen.add(name)
    r=relaxed[name];v=Q(term['value'])
    assert r['relation']=='eq' or v<=0
    bound+=v*Q(r['rhs'])
    for j,coef in r['terms']:col[j]+=v*Q(coef)
objective=[-1 if v[0]=='flow' else 0 for v in matrix['variables']]
assert all(a<=c for a,c in zip(col,objective))
assert bound==0 and certificate['bound']=='0'
out={'candidate_sha256':report['candidate_sha256'],'strict_infeasible_exact':True,'zero_rows':contradictions,
     'relaxed_zero_primal_exact':True,'relaxed_max_total_channel_flow':'0',
     'dual_columns_checked':len(col),'dual_nonzero_multipliers':len(seen),
     'scope':'固定当前布局、配方与物品支持；原模型由零行否证，零流证书仅属于供矿<=1且去掉成品目标的放宽模型。'}
(HERE/'独立证书回放.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
