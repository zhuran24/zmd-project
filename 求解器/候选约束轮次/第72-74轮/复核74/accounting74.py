"""Parse the formal recipes and solve the periodic balances over Q."""
from geometry74 import *
from fractions import Fraction as F
import re,hashlib

def main():
    text=(ROOT/'《明日方舟：终末地》游戏规则.txt').read_text().split('\n配方\n')[1]
    recipes=[];kind=None
    def term(s):
        n,name=s.strip().split(' ',1);return name.strip(),int(n)
    for line in text.splitlines():
        line=line.strip()
        if not line:continue
        if '→' not in line:kind=line;continue
        left,right=line.split('→');result,duration=right.rsplit('，',1)
        inputs=dict(term(s) for s in left.split('＋'));outputs=dict([term(result)])
        recipes.append((kind,inputs,outputs,int(duration.strip().split()[0])))
    items=sorted({s for _,a,b,_ in recipes for s in a.keys()|b.keys()})
    assert len(recipes)==18 and len(items)==19
    rows=[];n=len(recipes)+2;target={'高容谷地电池':F(3,5),'精选荞愈胶囊':F(11,20)}
    for item in items:
        row=[F(b.get(item,0)-a.get(item,0)) for _,a,b,_ in recipes]
        row += [F(item=='源矿'),F(item=='蓝铁矿'),target.get(item,F(0))]
        rows.append(row)
    rows.append([F(k=='精炼炉') for k,_,_,_ in recipes]+[F(0),F(0),F(51)])
    pivots=[];r=0
    for col in range(n):
        q=next((q for q in range(r,len(rows)) if rows[q][col]),None)
        if q is None:continue
        rows[r],rows[q]=rows[q],rows[r];factor=rows[r][col];rows[r]=[x/factor for x in rows[r]]
        for q in range(len(rows)):
            if q!=r and rows[q][col]:
                factor=rows[q][col];rows[q]=[x-factor*y for x,y in zip(rows[q],rows[r])]
        pivots.append(col);r+=1
    assert len(pivots)==n
    solution=[F(0)]*n
    for row,col in zip(rows,pivots):solution[col]=row[-1]
    assert all(x>=0 for x in solution)
    limits=dict(re.findall(r'(粉碎机|精炼炉|研磨机|塑形机|配件机|种植机|采种机|封装机|灌装机) ≥(\d+)',(ROOT/'求解约束.txt').read_text().split('机型下限：',1)[1].split('\n',1)[0]))
    limits={k:int(v) for k,v in limits.items()};assert len(limits)==9
    result=[]
    for k in limits:
        rates=[solution[i] for i,(kind,*_) in enumerate(recipes) if k==kind]
        duration=next(d for kind,a,b,d in recipes if kind==k)
        rate=sum(rates);minimum=rate-F(limits[k]-1,duration)
        assert minimum>0 and (rate*duration).__ceil__()==limits[k]
        result.append(dict(kind=k,rates=list(map(str,rates)),count=limits[k],per_machine_minimum=str(minimum)))
    small=sum(limits[k] for k in ('粉碎机','精炼炉','塑形机','配件机'))
    medium=sum(limits[k] for k in ('采种机','种植机'));large=sum(limits[k] for k in ('研磨机','封装机','灌装机'))
    area=9*small+25*medium+24*large
    assert (small,medium,large,area)==(131,48,38,3291)
    # Direct derivation of no extra machines from formal scalar inequalities.
    otherwise=[]
    for P in range(10,18):
        J=min(P,(23*P-217)//9);v=4*1113+16*P-2*J
        assert v>4608
        otherwise.append([P,J,v])
    extra_min=min(v for _,_,v in otherwise)+4*9
    assert extra_min>4639
    result_data=dict(recipes=18,materials=19,raw_rates=list(map(str,solution[-2:])),machines=result,
        size_counts=[small,medium,large],machine_area=area,total_machines=sum(limits.values()),
        S_cap=4639-4*1113,otherwise=otherwise,extra_machine_lower=extra_min,
        P_cases=[dict(P=P,power_budget=23*P-217,J_max=(23*P-217)//10,T_plus_F=4900-1113-area-81-138-4*P) for P in (10,11,12)])
    dump('accounting.json',result_data);print(result_data)

if __name__=='__main__':main()
