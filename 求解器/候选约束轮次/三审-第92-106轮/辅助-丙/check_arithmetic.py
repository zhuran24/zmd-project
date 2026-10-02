#!/usr/bin/env python3
"""丙席独立复算；只依赖 Python 标准库，不读取其他席位的程序或结果。"""
from fractions import Fraction as F
from itertools import product, combinations, permutations
from functools import lru_cache
from pathlib import Path
import json

OUT = Path(__file__).resolve().parent

def ceil(q):
    return -(-q.numerator // q.denominator)

def area_numbers():
    # 先从 20 tick 的 12 电池、11 胶囊还原配方用量。
    parts, bottles, fine_buck, dense_ori = 120, 110, 110, 180
    steel = parts + 2*bottles
    dense_fe = steel
    fe_pow = 2*dense_fe
    ori_pow = 2*dense_ori
    buck_pow = 2*fine_buck
    sand_pow = dense_fe+dense_ori+fine_buck
    crushed_buck, crushed_sand = F(buck_pow,2), F(sand_pow,3)
    harvested = crushed_buck+crushed_sand
    planted = 2*harvested
    batches = [fe_pow+ori_pow+harvested, fe_pow+steel,
               dense_fe+dense_ori+fine_buck, bottles, parts, planted,
               harvested, 12, 11]
    durations = [1,1,1,1,1,1,1,5,5]
    sizes = [9,9,24,9,9,25,25,24,24]
    machines = [ceil(F(v)*d/20) for v,d in zip(batches,durations)]
    # 机型输入/输出总件数：各自按每端口 1/tick 向上取整。
    inputs = [batches[0],batches[1],3*batches[2],2*bottles,parts,
              planted,harvested,25*12,20*11]
    outputs = [fe_pow+ori_pow+buck_pow+sand_pow,batches[1],batches[2],
               bottles,parts,planted,2*harvested,12,11]
    ci = [ceil(F(x,20)) for x in inputs]
    co0 = [ceil(F(x,20)) for x in outputs]
    co = co0[:-2]+machines[-2:]
    assert machines == [68,51,32,6,6,32,16,3,3]
    assert sum(ci)==305 and sum(co)==260
    return dict(machines=machines,count=sum(machines),area=sum(a*b for a,b in zip(machines,sizes)),
                input_ports=ci,output_ports=co,old_output_sum=sum(co0),
                interfaces=sum(ci)+sum(co)+52+2,
                ore_per_tick=[str(F(fe_pow,20)),str(F(ori_pow,20))])

def weight_table(width,cap,demand2,max_n):
    # 单口 0,1/2,1；整数容量网络流在需求乘2后有整数最优点。
    best=[10**6]*(cap*2+1)
    for v in product(range(3),repeat=width):
        q=sum(v)
        if q>2*cap: continue
        support=[i for i,x in enumerate(v) if x]
        cost=sum(v[a]+v[b] for a,b in zip(support,support[1:]) if b-a<=3)
        best[q]=min(best[q],cost)
    dp=[0]+[10**6]*demand2
    result={}
    for n in range(1,max_n+1):
        nxt=[10**6]*(demand2+1)
        for total in range(demand2+1):
            nxt[total]=min((dp[total-x]+best[x] for x in range(min(total,2*cap)+1)),default=10**6)
        dp=nxt
        if dp[demand2]<10**6: result[n]=dp[demand2]
    return best,result

def area_weights():
    specs=[(6,3,189,49),(3,2,22,13),(6,5,30,10),(6,4,22,8)]
    tables=[]
    for spec in specs:
        _,tab=weight_table(*spec)
        tables.append(tab)
    assert [tables[i][n] for i,n in enumerate([32,6,3,3])]==[123,20,48,28]
    # 研磨闭式是安全下界，超过47台时按0而非负数。
    for n,cost in tables[0].items():
        target=379-8*n if n<=47 else 0
        assert cost>=target
    for n,cost in tables[1].items(): assert cost==2*max(0,22-2*n)
    for n,cost in tables[2].items(): assert cost==2*({3:24,4:18,5:10,6:6,7:2}.get(n,0))
    for n,cost in tables[3].items(): assert cost==2*({3:14,4:6,5:2}.get(n,0))
    increments=[min(8*size+tab[n+1]-tab[n] for n in tab if n+1 in tab)/2
                for size,tab in zip([24,9,24,24],tables)]
    assert increments==[92,34,88,88]
    pj=[(p,j) for p in range(1,100) for j in range(p+1)
        if 23*p-10*j>=217 and 54*p-25*j>=520]
    minpower=min(16*p-2*j for p,j in pj)
    bound=F(4751-minpower,4)-F(287,8)
    assert bound==F(8895,8)
    remaining=[(p,j,199-16*p+2*j) for p,j in pj if 16*p-2*j<=199]
    factors={a:[(w,h) for w in range(6,69) for h in range(w,69) if w*h==a]
             for a in range(1107,1113)}
    ext=[]
    for length,segments,t in [(71,2,1),(101,3,2),(138,2,2)]:
        ext.append(dict(length=length,no_extra=ceil(F(length-14-5*segments,6)),
                        one_extra=ceil(F(length-14-8*t-5*segments,6))))
    # 整数与偶数取整；比较 X_G=X_M+2chi 后的 G/M 阈值。
    thresholds=[]
    for chi in (0,1):
        rows=[]
        for z in range(4):
            proved=2*ceil(F(1843+2*z,4)) # z=X_M+Y
            g=2*ceil(F(921+z+chi,2))
            m=2*ceil(F(921+z,2))
            assert proved>=g>=m
            rows.append([z%2,g-m])
        thresholds.append(dict(chi=chi,G_minus_M_even_threshold=rows))
    return dict(double_weight_tables=tables,min_increments=increments,
                omega=109.5,direction_total=619+184+8+109.5+88+4-91,
                residual_area=4900-3291-81-138,min_power_term=minpower,
                extra_area_bound=str(bound),P_J_at_1110=remaining,factorizations=factors,
                outer_edge_bounds=ext,threshold_comparison=thresholds)

def prefix_check():
    # 独立枚举每个可达收料状态：先尽可能制造，检验公式余量与逐批减法相同。
    checked=0
    for a,b in [(2,1),(10,15),(10,10)]:
        for xa in range(51):
            for xb in range(51):
                states={(xa,xb,0,0)}
                for depth in range(8):
                    nxt=set()
                    for x,y,ia,ib in states:
                        xx,yy=x,y
                        while xx>=a and yy>=b: xx-=a; yy-=b
                        m=min((xa+ia)//a,(xb+ib)//b)
                        assert (xx,yy)==(xa+ia-a*m,xb+ib-b*m)
                        checked+=1
                        if xx<50:nxt.add((xx+1,yy,ia+1,ib))
                        if yy<50:nxt.add((xx,yy+1,ia,ib+1))
                    states=nxt
    return dict(states=checked,recipes=[[2,1],[10,15],[10,10]],depth=8,violations=0)

def blocks():
    result=[]
    for k in range(2,7):
        modes=leaves=0; latest=-1
        for occupied in range(k):
            for release in combinations(range(1,8),occupied):
                r=(0,)*(k-occupied)+release
                @lru_cache(None)
                def visit(t,mask):
                    if mask==(1<<k)-1:return (t-1,t-1,1)
                    choices=[i for i in range(k) if not(mask>>i&1) and r[i]<=t]
                    if not choices:return visit(t+1,mask)
                    children=[visit(t+1,mask|1<<i) for i in choices]
                    return min(x[0] for x in children),max(x[1] for x in children),sum(x[2] for x in children)
                lo,hi,count=visit(0,0)
                formula=max(x+k-1-i for i,x in enumerate(r))
                assert lo==hi==formula and hi<=7
                modes+=1;leaves+=count;latest=max(latest,hi)
        result.append(dict(k=k,release_modes=modes,service_orders=leaves,last_offset=latest))
    assert [x['release_modes'] for x in result]==[8,29,64,99,120]
    service=[]
    for k in (1,2,3):
        # 连续k步任意重排；所有首格起初都空，已收货首格8步内不能再次收。
        worst=0;cases=0
        for orders in product(list(permutations(range(k))),repeat=k):
            used=set()
            for t,order in enumerate(orders):
                j=next(j for j in order if j not in used)
                used.add(j)
                if j==0: worst=max(worst,t+1);break
            assert 0 in used
            cases+=1
        service.append(dict(k=k,order_schedules=cases,max_judgements=worst))
    return dict(blocks=result,refill_service=service)

def plant_arithmetic():
    checks=0
    for H2 in (300,352):
        for x2 in range(501):
            cur=x2
            for m in range(30):
                cur=min(cur-1,H2)
                assert cur==min(x2-m-1,H2-m)
                checks+=1
    # 满初态链递推，对任意长、相邻用料至少8步的序列逐格从后往前计算。
    import random
    rng=random.Random(20261002)
    chains=0
    for length in range(1,41):
        for _ in range(40):
            x=[];cur=0
            for j in range(40):cur+=rng.randint(8,30);x.append(cur)
            prev=[0]*length
            for j,demand in enumerate(x,1):
                now=[0]*length
                for i in range(length-1,-1,-1):
                    fresh=prev[max(0,i-1)]+8
                    space=now[i+1] if i+1<length else demand+1
                    now[i]=max(fresh,space)
                expected=max(8*j,demand+1)
                assert now==[expected]*length and expected<=demand+8
                prev=now
            chains+=1
    return dict(map_checks=checks,chain_cases=chains,
                general_bound=49+50+49+1+1,normal_BB_bound=50*3+2+F(49,2)-F(1,2),
                maximum=3*50+2+25,last_start=8*49,first_possible_empty=8*50,
                weak_output_bounds=[50-3*k for k in (1,2,3)],strong_output_bounds=[48,47])

def main():
    results=dict(area=area_numbers(),weights=area_weights(),prefix=prefix_check(),
                 polling=blocks(),plant=plant_arithmetic())
    (OUT/'arithmetic.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str)+'\n')
    print(json.dumps(dict(status='PASS',area=results['area'],plant=results['plant'],blocks=results['polling']['blocks']),ensure_ascii=False,default=str))

if __name__=='__main__':main()
