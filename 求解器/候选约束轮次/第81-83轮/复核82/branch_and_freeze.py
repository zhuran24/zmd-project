"""植物不分叉结构：精确图检查 / 独立 LP；冻结配方的两种计数。"""
import os
os.sched_setaffinity(0,{1})
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
from itertools import product
import json,warnings,re
import numpy as np
from scipy.optimize import linprog
OUT=Path(__file__).resolve().parent
cases=[]
for na,nz in product(range(1,4),repeat=2):
    for apos in product(range(nz),repeat=na):
        for zpos in product(range(na+1),repeat=nz):
            sink=na+nz
            successor=[na+j for j in apos]+[j if j<na else sink for j in zpos]+[sink]
            # 到粉碎出口的每条前向路径没有回路；逐次剥去无流入的结点。
            basin=[]
            for i in range(sink):
                visited=set();v=i
                while v!=sink and v not in visited:visited.add(v);v=successor[v]
                if v==sink:basin.append(i)
            remaining=set(basin)
            while remaining:
                leaves={i for i in remaining if not any(successor[j]==i for j in remaining)}
                assert leaves
                remaining-=leaves
            # 独立配方流量平衡：a_i=流入植株，z_j=流入种子。
            M=np.zeros((na+nz,na+nz))
            for i in range(na):
                M[i,i]=1
                for j,target in enumerate(zpos):
                    if target==i:M[i,na+j]-=1
            for j in range(nz):
                M[na+j,na+j]=1
                for i,target in enumerate(apos):
                    if target==j:M[na+j,i]-=2
            c=np.array([0]*na+[-int(t==na) for t in zpos])
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                r=linprog(c,A_eq=M,b_eq=np.zeros(na+nz),bounds=(0,1),method='highs',options={'threads':1})
            assert r.success and abs(r.fun)<1e-9
            cases.append({'采种':na,'种植':nz,'采种后继':apos,'种植后继':zpos,'图检查出口流量':0,'LP出口流量':float(-r.fun),'status':r.status})
formula=sum(z**a*(a+1)**z for a,z in product(range(1,4),repeat=2));assert len(cases)==formula==2176

lines=(OUT.parent/'前提快照/《明日方舟：终末地》游戏规则.txt').read_text().split('\n配方\n')[1].splitlines()
recipes=[];kind=None
for line in lines:
    if not line.strip():continue
    if '→' not in line:kind=line.strip();continue
    a,b=line.split('→');b=b.split('，')[0]
    def atoms(s):
        return {x.split()[1]:int(x.split()[0]) for x in s.strip().split('＋')}
    recipes.append({'kind':kind,'in':atoms(a),'out':atoms(b),'text':line.strip()})
families=[{x} for r in recipes for x in r['in']|r['out']]+[{'荞花','荞花种子'},{'砂叶','砂叶种子'}]
freeze={}
for wanted in [('高容谷地电池',),('精选荞愈胶囊',),('高容谷地电池','精选荞愈胶囊')]:
    stopped=set();steps=[]
    # 可接受的成品是仍存在的无限出口。拒收成品和非成品记入有限库存。
    while True:
        before=set(stopped)
        for family in families:
            if any(x in family and x not in wanted for x in ['高容谷地电池','精选荞愈胶囊']):continue
            net=[sum(r['out'].get(x,0)-r['in'].get(x,0) for x in family) for r in recipes]
            negative={i for i,d in enumerate(net) if d<0}
            if negative<=stopped:
                for i,d in enumerate(net):
                    if d>0 and i not in stopped:
                        stopped.add(i);steps.append({'recipe':i,'bounded_item_family':sorted(family),'already_finite_consumers':sorted(negative)})
        if stopped==before:break
    # 双拒收时，矿物研磨已经有限；原矿输入有限再使蓝铁矿精炼有限。
    if len(wanted)==2:
        idx=next(i for i,r in enumerate(recipes) if r['in']=={'蓝铁矿':1})
        stopped.add(idx);steps.append({'recipe':idx,'bounded_item_family':['蓝铁矿','蓝铁块','蓝铁粉末'],'reason':'这三类的净减少配方已有限；取蓝铁矿增加总数，故取矿有限；原矿本身只够有限批精炼。'})
    expected_outputs={'高容谷地电池':{'高容谷地电池','钢制零件','致密源石粉末','源石粉末'},'精选荞愈胶囊':{'精选荞愈胶囊','钢质瓶','细磨荞花粉末','荞花粉末','荞花','荞花种子'}}
    if len(wanted)==1:manual={i for i,r in enumerate(recipes) if set(r['out'])<=expected_outputs[wanted[0]]}
    else:manual={i for i,r in enumerate(recipes) if not (r['in']=={'蓝铁块':1} or r['in']=={'蓝铁粉末':1})}
    assert stopped==manual
    freeze['+'.join(wanted)]={'recipe_count':len(stopped),'recipes':[recipes[i]['text'] for i in sorted(stopped)],'finite_production_certificate':steps}
(OUT/'branch_cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
result={'branch_models':len(cases),'independent_count':formula,'all_graph_zero':True,'all_lp_zero':True,'freeze':freeze}
(OUT/'branch_and_freeze.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'models':len(cases),'freeze_counts':{k:v['recipe_count'] for k,v in freeze.items()}},ensure_ascii=False))
