#!/usr/bin/env python3
"""只读本轮落盘矩阵和有理证书，不调用求解器或A/B。"""
import json, hashlib
from pathlib import Path
from fractions import Fraction as Q
HERE=Path(__file__).resolve().parent
read=lambda n:json.loads((HERE/n).read_text())
m=read('独立LP矩阵.json'); r=read('独立LP.json')
assert hashlib.sha256((HERE/'候选只读快照.json').read_bytes()).hexdigest()==r['candidate_sha256']
rows={v['name']:v for v in m['rows']}
assert len(rows)==len(m['rows'])
bad=[v for v in m['rows'] if not v['terms'] and (Q(v['rhs'])!=0 if v['relation']=='eq' else Q(v['rhs'])<0)]
assert {v['name'] for v in bad}=={v['name'] for v in r['exact_contradictions']}
relaxed={n:{**v,'relation':'le' if n.startswith('source:') else v['relation']} for n,v in rows.items() if not n.startswith('target:')}
def verify(cert,objective,values):
    assert all(x>=0 for x in values)
    for row in relaxed.values():
        lhs=sum((Q(v)*values[j] for j,v in row['terms']),Q())
        assert lhs==Q(row['rhs']) if row['relation']=='eq' else lhs<=Q(row['rhs'])
    col=[Q() for _ in values]; bound=Q();seen=set()
    for t in cert['multipliers']:
        n=t['row'];assert n not in seen;seen.add(n)
        row=relaxed[n];y=Q(t['value'])
        assert row['relation']=='eq' or y<=0
        bound+=y*Q(row['rhs'])
        for j,v in row['terms']:col[j]+=y*Q(v)
    assert all(v<=objective[j] for j,v in enumerate(col))
    primal=sum((v*values[j] for j,v in enumerate(objective)),Q())
    assert primal==bound==Q(cert['bound'])
    return {'primal_dual_equal':True,'objective':str(bound),'columns_checked':len(col),'nonzero_dual_multipliers':len(seen)}
keys=m['variables']; idx={tuple(v):i for i,v in enumerate(keys)}
all_objective=[Q(-1) if k[0]=='flow' else Q() for k in keys]
total=verify(r['source_relaxed_max_total_channel_flow']['certificate'],all_objective,[Q() for _ in keys])
# All channel flows are nonnegative. A sum bounded by zero forces each to zero.
# Every batch has positive product coefficient in an output balance, forcing it to zero too.
batch_columns=[i for i,k in enumerate(keys) if k[0]=='batch']
for i in batch_columns:
    k=keys[i]
    assert any(n.startswith('machine:'+k[1]+':out:') and any(j==i and Q(v)<0 for j,v in row['terms']) and all((Q(v)<0 if keys[j][0]=='batch' else Q(v)>0) for j,v in row['terms']) for n,row in rows.items())
item_verifications={}
for it in r['per_item']:
    objective=[Q() for _ in keys]
    if it in ['源矿','蓝铁矿']:
        for n,row in rows.items():
            if n.startswith('source:'):
                for j,v in row['terms']:
                    if keys[j][0]=='flow' and keys[j][2]==it:objective[j]-=Q(v)
    else:
        for n,row in rows.items():
            if n.startswith('machine:') and n.endswith(':out:'+it):
                for j,v in row['terms']:
                    if keys[j][0]=='batch':objective[j]+=Q(v)
    w=read('独立LP-诊断见证-'+it+'.json');x=[Q() for _ in keys]
    for v in w['nonzero_values']:x[idx[tuple(v['key'])]]=Q(v['value'])
    item_verifications[it]=verify(w['solver']['certificate'],objective,x)
out={'candidate_sha256':r['candidate_sha256'],'strict_infeasible_exact':bool(bad),'zero_row_contradictions':bad,
     'relaxed_total_flow':total,'all_batches_forced_zero':True,'batch_columns_checked':len(batch_columns),
     'per_item':item_verifications,'solver_called':False,
     'scope':'固定快照、配方和物品支持；严格模型由矛盾行否证；最优值证书仅用于矿源<=1且去目标的放宽模型。'}
(HERE/'独立证书回放.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ['per_item','zero_row_contradictions']},ensure_ascii=False))
