"""Parse official recipes and solve exact periodic balance, independently."""
from geometry77 import *
from fractions import Fraction as F
import re

def main():
    text=(ROOT/'《明日方舟：终末地》游戏规则.txt').read_text().split('\n配方\n',1)[1]
    recipes=[];kind=None
    def parse(side):return {name:int(n) for n,name in re.findall(r'(\d+)\s+([^\s＋]+)',side)}
    for line in text.splitlines():
        line=line.strip()
        if not line:continue
        if '→' not in line:kind=line;continue
        a,b=line.split('→');out,tick=b.rsplit('，',1)
        recipes.append(dict(kind=kind,ins=parse(a),outs=parse(out),tick=int(tick.split()[0])))
    assert len(recipes)==18
    items=sorted({x for r in recipes for side in ('ins','outs') for x in r[side]});assert len(items)==19
    # 18 recipe rates + two external mineral supplies, with no plant imports.
    eq=[]
    for item in items:
        row=[F(r['outs'].get(item,0)-r['ins'].get(item,0)) for r in recipes]
        row += [F(item=='蓝铁矿'),F(item=='源矿')]
        row += [F('0.6') if item=='高容谷地电池' else F('0.55') if item=='精选荞愈胶囊' else F(0)]
        eq.append(row)
    eq.append([F(r['kind']=='精炼炉') for r in recipes]+[F(0),F(0),F(51)])
    rank=0
    for col in range(20):
        pivot=next(i for i in range(rank,len(eq)) if eq[i][col])
        eq[rank],eq[pivot]=eq[pivot],eq[rank];d=eq[rank][col];eq[rank]=[v/d for v in eq[rank]]
        for i in range(len(eq)):
            if i!=rank and eq[i][col]:
                d=eq[i][col];eq[i]=[a-d*b for a,b in zip(eq[i],eq[rank])]
        rank+=1
    rates=[row[-1] for row in eq];assert all(r>=0 for r in rates)
    boundline=next(s for s in (ROOT/'求解约束.txt').read_text().splitlines() if s.startswith('机型下限：'))
    families_in_rules={r['kind'] for r in recipes}
    counts={k:int(v) for k,v in re.findall(r'([\u4e00-\u9fff]+)\s*≥(\d+)',boundline) if k in families_in_rules}
    families=[]
    for kind,n in counts.items():
        rs=[(r,rate) for r,rate in zip(recipes,rates) if r['kind']==kind]
        total=sum(v for r,v in rs);maximum=max(F(1,r['tick']) for r,v in rs)
        minimum=total-(n-1)*maximum;assert minimum>0
        families.append(dict(kind=kind,count=n,rates=[str(v) for r,v in rs],minimum=str(minimum)))
    assert sum(counts.values())==217
    assert sum(counts[k] for k in ['粉碎机','精炼炉','塑形机','配件机'])==131
    assert 131*9+48*25+38*24==3291
    branches=[dict(P=p,supply_budget=23*p-217,T_plus_F=277-4*p,area_cap=4639-4*1113,J_max=(23*p-217)//9) for p in (10,11,12)]
    out=dict(recipes=recipes,rates=[str(x) for x in rates],families=families,branches=branches,
      line_lengths=list(map(len,LINES)),physical_cells=len(WEIGHTS),double_counted=[p for p,n in WEIGHTS.items() if n==2])
    save('accounting.json',out);print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
