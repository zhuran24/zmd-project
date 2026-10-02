#!/usr/bin/env python3
"""对真实候选做定向损坏，确认相应静态项目会拒绝。基准可以缺路。"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,{6})
import json,sys,copy
from pathlib import Path
from static_check import audit,read,digest
B=Path(__file__).resolve().parents[1];src=Path(sys.argv[1]);base=read(src);contract=read(B/'逻辑接法.json')
result=[]
def run(name,change,wanted):
    d=copy.deepcopy(base);change(d);r=audit(d,contract,True)
    rejected=r['checks'].get(wanted,{}).get('status')=='FAIL'
    result.append(dict(case=name,expected_failed_check=wanted,rejected=rejected,observed=r['checks'].get(wanted)))
def belt_wrong(d):
    q=next(q for q in d['layout']['transport'] if q['type']=='belt');q['out_side']=q['in_side']
run('传送带存取边相同',belt_wrong,'belt_ports')
def bridge_wrong(d):
    q=next(q for q in d['layout']['transport'] if q['type']=='bridge');q['H_in']=(q['H_in']+2)%4
run('桥接器水平方向声明反转',bridge_wrong,'bridge_direction')
def reverse_missing(d):
    k=d['design']['bridge_reverse_channels'].pop();d['design']['physical_channels']=[q for q in d['design']['physical_channels'] if q['id']!=k]
if base['design']['bridge_reverse_channels']:run('漏报真实桥间逆向通道',reverse_missing,'all_automatic_channels')
def overlap(d):
    p=d['layout']['power_poles'][0];u=d['layout']['machines'][0]
    p.update(x0=u['x0'],y0=u['y0'],x1=u['x0']+1,y1=u['y0']+1)
run('供电桩压在机身上',overlap,'overlap')
def power_off(d):d['layout']['power_poles']=[]
run('删除全部供电桩',power_off,'power')
def fill_rect(d):
    r=d['empty_rectangle'];d['layout']['transport'].append(dict(id='MUTATION_BELT',x=r['x0'],y=r['y0'],type='belt',in_side=3,out_side=1))
run('占用声明空矩形',fill_rect,'maximum_empty_rectangle')
def cut_equal(d):
    ff=next(f for f in d['design']['logical_feeds'] if f['from']['unit']=='H6' and f['to']['unit']=='F4')
    p=next(p for p in d['design']['physical_channels'] if p['id']==ff['path'][0]);uid=p['to']['unit'];d['layout']['transport']=[t for t in d['layout']['transport'] if t['id']!=uid]
if any(f['from']['unit']=='H6' and f['to']['unit']=='F4' for f in base['design']['logical_feeds']):run('删掉H6末端进路，不能按空列表等长通过',cut_equal,'H6_Q6_equal_length')
out=dict(candidate_sha256=digest(src),all_expected_rejections=all(r['rejected'] for r in result),cases=result)
(B/'证据/拒绝性核验.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='cases'},ensure_ascii=False))
raise SystemExit(0 if out['all_expected_rejections'] else 1)
