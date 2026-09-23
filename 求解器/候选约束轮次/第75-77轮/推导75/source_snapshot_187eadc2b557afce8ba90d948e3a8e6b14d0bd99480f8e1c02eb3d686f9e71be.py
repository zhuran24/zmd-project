#!/usr/bin/env python3
"""Reproduce coordinate-only modifications and certify all three S levels."""
from pathlib import Path
import json,hashlib
import cp72,verify75
OUT=Path(__file__).resolve().parent;cp72.ROUNDS=OUT.parents[1]
def write(name,data):
    (OUT/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def replace_top(d,x):
    specs={tuple(b[k] for k in ('kind','x','y','w','h','axis')):b for b in cp72.domain()}
    for i,b in enumerate(d['chosen']):
        if b['kind']=='m' and b['x']==x and b['y']==65:
            d['chosen'][i]=specs['l',x,64,4,6,'h'];return
    raise AssertionError(('missing original top unit',x))
def main():
    base=json.loads((OUT/'fixed_bodies_S185_J1_best.json').read_text())
    changes=[{(38,37):(38,33)}, {(38,37):(38,33),(41,61):(39,61)},
             {(38,37):(38,33),(40,50):(38,49),(41,61):(39,61)},
             {(38,37):(38,34),(40,50):(38,49),(41,61):(39,61)},
             {(38,37):(38,35),(40,50):(38,49),(41,61):(39,61)}]
    records=[]
    for no,change in zip([0,4,5,6,7],changes):
        d=json.loads(json.dumps(base))
        for b in d['chosen']:
            if b['kind']=='p' and (b['x'],b['y']) in change:b['x'],b['y']=change[b['x'],b['y']]
        r=verify75.check(d);records.append(dict(variant=no,coordinate_changes=[[list(k),list(v)] for k,v in change.items()],upper=r['all_subset_upper']))
    write('coordinate_variation_reproduction',records)
    d=json.loads((OUT/'all_subsets_local.json').read_text())
    for S,x in [(185,None),(186,2),(187,9)]:
        if x is not None:replace_top(d,x)
        d['S']=S;d['scope']='M0 plus all 9 x 1024 original common-group capacity cuts; relaxation only'
        for k in ('stats','status','seconds','script_sha256','model_sha256','base','cluster_sizes','radius','workers','time_limit','build_seconds'):d.pop(k,None)
        d['construction']='S185 local flow witness; S186 replaces (2,65,5,5) by (2,64,4,6); S187 also replaces (9,65,5,5) by (9,64,4,6)'
        r=verify75.check(d);assert r['all_subset_upper']>=217
        name=f'complete_subsets_S{S}';write(name,d);write(name+'_audit',r)
        tr=verify75.transpose(d);rr=verify75.check(tr,True);assert rr['all_subset_upper']>=217
        write(name+'_transpose',tr);write(name+'_transpose_audit',rr)
        print(name,r['status'],r['line_gaps'],r['loss'],r['repeats'],r['all_subset_upper'],flush=True)
    tests=[]
    for label,mutate in [('false score',lambda z:z.update(S=z['S']-1)),('duplicate pole',lambda z:z['chosen'].append(next(b for b in z['chosen'] if b['kind']=='p'))),('outside base',lambda z:z['chosen'][0].update(x=70))]:
        z=json.loads(json.dumps(d));mutate(z)
        try:verify75.check(z)
        except AssertionError:tests.append(dict(case=label,rejected=True))
        else:raise AssertionError(('failed mutation check',label))
    old=json.loads((OUT.parents[1]/'第72-74轮/推导72/witness185.json').read_text())
    try:verify75.check(old)
    except AssertionError:tests.append(dict(case='old 185 violates M1',rejected=True))
    else:raise AssertionError('old witness should violate M1')
    write('checker_mutation_tests',dict(status='PASS',checks=tests,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
if __name__=='__main__':main()
