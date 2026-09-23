#!/usr/bin/env python3
"""不调用求解器，不导入生成脚本；用Fraction核验完整分支覆盖及原始/对偶证书。"""
from fractions import Fraction as Q
from itertools import product
from pathlib import Path
import hashlib
import json
import re

P=Path(__file__).resolve().parent
model=json.loads((P/"b7_lp_model.json").read_text())
certs=json.loads((P/"b7_rational_certificates.json").read_text())
facts=json.loads((P/"enumeration.json").read_text())
source=json.loads((P/"input_manifest.json").read_text())
rules=(P/"游戏规则快照.md").read_text()
flat=lambda s:re.sub(r"\s+","",s)
for r in model["recipe_variables"]:
    fmt=lambda d:"＋".join(str(v)+k for k,v in d.items())
    line=fmt(r["inputs"])+"→"+fmt(r["outputs"])+"，"+str(r["ticks"])+"tick"
    assert line in flat(rules)

# 第二种边带算法：逐格游标跳过空格，重建23个中心。
centres={}
for gap in range(0,70,3):
    x=0; ps=[]
    while x<70:
        if x==gap:x+=1;continue
        assert gap not in [x,x+1,x+2]
        ps.append(x+1);x+=3
    assert x==70 and len(ps)==23
    assert len([p for p in ps if p>=49])==7
    centres[gap]=ps
expected=[]
for gap,ps in centres.items():
    starts=[x for x in range(49,65) if len([p for p in ps if x<=p<x+6])==1]
    if starts:expected.append((gap,starts))
assert expected==[(d["bottom_gap"],d["grinder_x"]) for d in facts["b7_survivors"]]
assert all(d["whole_grinder_count_in_singleton_domain"]==0 for d in facts["cases"] if d["b"]==6)

A=[[Q(x) for x in row] for row in model["A"]]
E=[[Q(x) for x in row] for row in model["E"]]
c=list(map(Q,model["objective"]))
u=[None if x is None else Q(x) for x in model["upper"]]
nv=len(c)
assert len(A)==43 and len(E)==5 and nv==38
assert model["kinds"]==["粉碎机","精炼炉","配件机","塑形机","种植机","采种机"]
assert model["eq_kinds"]==["粉碎机","精炼炉","配件机","种植机","采种机"]
assert u[:19]==list(map(Q,[18,34,"11/2","21/2",34,17,0,17,9,"11/2","11/2",6,11,21,"11/2","21/2",0,0,7]))
assert all(t is None for t in u[19:]) and c==[Q(0)]*19+[Q(1)]*19
g=[Q(0)]*nv;g[7:10]=[Q(1)]*3
k=[Q(0)]*nv;k[7:9]=[Q(-1)]*2
s=[Q(0)]*nv;s[10]=1
assert A[:5]==[g,[-v for v in g],k,s,[-v for v in s]]
assert list(map(Q,model["rhs"][:3]))==[Q(1),Q(-1,2),Q(-1,2)]
for row,kind in zip(E,model["eq_kinds"]):
    expected_row=[Q(int(r["kind"]==kind)) for r in model["recipe_variables"]]+[Q(0)]*20
    assert row==expected_row

# 直接按配方复建19种物料的正负净流量行，含7个原矿入口。
for j,item in enumerate(model["items"]):
    row=[Q(r["outputs"].get(item,0)-r["inputs"].get(item,0)) for r in model["recipe_variables"]]+[Q(0)]*(nv-18)
    constant=0
    if item=="蓝铁矿":row[18]=1
    elif item=="源矿":row[18]=-1;constant=7
    positive=row.copy();positive[19+j]=-1
    negative=[-x for x in row];negative[19+j]=-1
    assert A[5+2*j]==positive and A[6+2*j]==negative
    assert Q(model["rhs"][5+2*j])==-constant and Q(model["rhs"][6+2*j])==constant

# 以剩余宽度递减生成整数分支，与生成器的笛卡尔积过滤方法不同。
def domains(weights,budget,prefix=()):
    if not weights:
        yield prefix;return
    for v in range(budget//weights[0]+1):
        yield from domains(weights[1:],budget-v*weights[0],prefix+(v,))
want=set(domains([3,3,3,3,5,5],15))
got=[tuple(r["counts"]) for r in certs]
assert len(got)==len(set(got)) and set(got)==want
minimum=None
for r in certs:
    nd=dict(zip(model["kinds"],r["counts"]))
    b=list(map(Q,model["rhs"]));b[3]=Q(nd["塑形机"]);b[4]=Q(1,2)-nd["塑形机"]
    d=[Q(nd[k]) for k in model["eq_kinds"]]
    y,e,l,v,x=[list(map(Q,r[k])) for k in ["y","e","lower","upper","primal"]]
    assert len(y)==len(A) and len(e)==len(E) and len(l)==len(v)==len(x)==nv
    assert all(a<=0 for a in y+v) and all(a>=0 for a in l)
    for j in range(nv):
        assert c[j]==sum(A[i][j]*y[i] for i in range(len(A)))+sum(E[i][j]*e[i] for i in range(len(E)))+l[j]+v[j]
        assert u[j] is not None or v[j]==0
        assert x[j]>=0 and (u[j] is None or x[j]<=u[j])
    lower=sum(a*bb for a,bb in zip(y,b))+sum(a*dd for a,dd in zip(e,d))+sum(uu*vv for uu,vv in zip(u,v) if uu is not None)
    assert lower==Q(r["bound"]) and lower>=Q(19,3)
    assert all(sum(a*xx for a,xx in zip(row,x))<=bb for row,bb in zip(A,b))
    assert all(sum(a*xx for a,xx in zip(row,x))==dd for row,dd in zip(E,d))
    assert sum(a*xx for a,xx in zip(c,x))==lower
    minimum=lower if minimum is None else min(minimum,lower)
assert minimum==Q(19,3)
changed=[s["path"] for s in source["sources"] if hashlib.sha256(Path(s["path"]).read_bytes()).hexdigest()!=s["sha256"]]
assert not changed
out=dict(status="PASS",certificate_cases=len(certs),complete_integer_domain=True,
         exact_minimum=str(minimum),exact_deficit=str(minimum-6),
         solver_called=False,source_hashes_unchanged=True,
         checks=["19种物料矩阵按配方重建", "215个整数机型数组合无缺漏无重复", "所有对偶符号及驻点等式精确成立", "所有原始点满足约束且等于对偶值", "独立边带铺排得到同六种空格位置及十个研磨机起点"])
(P/"certificate_verification.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
final=dict(status="推导完成，候选待审；正式文件未改",
           report_path=str(P.parent/"B-切线容量-推导.md"),
           excluded_positions=[dict(position=p,P=[10,11,12],deficit=d) for p,d in [([49,6],"2"),([6,49],"2"),([49,7],"1/3"),([7,49],"1/3")]],
           remaining_positions=[[49,9],[9,49],[49,17],[17,49]],
           no_additional_P_exclusion_on_remaining=True,area_upper_bound=1113,
           b9_mineral_cut_margin="1+2G-D",b17_mineral_cut_margin="9+2G-D",
           remaining_note="未证明G、D的全布局最紧取值，未取得剩余位置或P分支的新排除；G=D=0时矿物切线分别余1、9件/tick。",
           certificate_verification=out)
(P/"results.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False,indent=2))
