"""Review arithmetic A: exact stoichiometric elimination and support-set costs."""
from fractions import Fraction as Q
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from math import ceil
import json

OUT=Path(__file__).resolve().parent
# name, machine, recipe time, inputs, output item, output quantity.
RECIPES=[
 ('crush_source','crush',1,{'ore_s':1},'pow_s',1),
 ('crush_blue','crush',1,{'ingot':1},'pow_b',1),
 ('crush_buck','crush',1,{'buck':1},'pow_k',2),
 ('crush_sand','crush',1,{'sand':1},'pow_l',3),
 ('refine_blue','refine',1,{'ore_b':1},'ingot',1),
 ('refine_steel','refine',1,{'dense_b':1},'steel',1),
 ('recycle','refine',1,{'pow_b':1},'ingot',1),
 ('grind_blue','grind',1,{'pow_b':2,'pow_l':1},'dense_b',1),
 ('grind_source','grind',1,{'pow_s':2,'pow_l':1},'dense_s',1),
 ('grind_buck','grind',1,{'pow_k':2,'pow_l':1},'fine_k',1),
 ('shape','shape',1,{'steel':2},'bottle',1),
 ('fit','fit',1,{'steel':1},'parts',1),
 ('plant_buck','plant',1,{'seed_k':1},'buck',1),
 ('plant_sand','plant',1,{'seed_l':1},'sand',1),
 ('seed_buck','seed',1,{'buck':1},'seed_k',2),
 ('seed_sand','seed',1,{'sand':1},'seed_l',2),
 ('pack','pack',5,{'parts':10,'dense_s':15},'battery',1),
 ('fill','fill',5,{'bottle':10,'fine_k':10},'capsule',1)]
AREA={'crush':9,'refine':9,'grind':24,'shape':9,'fit':9,'plant':25,'seed':25,'pack':24,'fill':24}


def solve_rates(recycling):
    products=sorted({r[4] for r in RECIPES})
    target={'battery':Q(3,5),'capsule':Q(11,20)}
    matrix=[]
    for p in products:
        row=[Q((r[5] if r[4]==p else 0)-r[3].get(p,0)) for r in RECIPES]
        matrix.append(row+[target.get(p,Q(0))])
    matrix.append([Q(int(r[0]=='recycle')) for r in RECIPES]+[Q(recycling)])
    n=len(RECIPES)
    assert len(matrix)==n
    for col in range(n):
        pivot=next(i for i in range(col,n) if matrix[i][col])
        matrix[col],matrix[pivot]=matrix[pivot],matrix[col]
        k=matrix[col][col]
        matrix[col]=[x/k for x in matrix[col]]
        for row in range(n):
            if row!=col:
                k=matrix[row][col]
                matrix[row]=[x-k*y for x,y in zip(matrix[row],matrix[col])]
    return [r[-1] for r in matrix]


def summarize(rates):
    load, incoming, outgoing, raw=defaultdict(Q),defaultdict(Q),defaultdict(Q),defaultdict(Q)
    for rate,r in zip(rates,RECIPES):
        load[r[1]]+=rate*r[2]
        incoming[r[1]]+=rate*sum(r[3].values())
        outgoing[r[1]]+=rate*r[5]
        for p,q in r[3].items():
            if p.startswith('ore_'):
                raw[p]+=rate*q
    counts={m:ceil(v) for m,v in load.items()}
    inc={m:ceil(v) for m,v in incoming.items()}
    out={m:ceil(v) for m,v in outgoing.items()}
    improved=dict(out)
    for m in ('pack','fill'):
        improved[m]=max(improved[m],counts[m])
    sizes={name:sum(counts[m] for m in counts if AREA[m]==area)
           for name,area in (('small',9),('medium',25),('large',24))}
    return dict(counts=counts,machines=sum(counts.values()),
                machines_by_size=sizes,power_weight=2*sizes['small']+3*(sizes['medium']+sizes['large']),
                manufacturing_area=sum(AREA[m]*v for m,v in counts.items()),
                input_channels=sum(inc.values()),input_by_machine=inc,
                output_channels_raw=sum(out.values()),output_channels=sum(improved.values()),
                output_by_machine=improved,ore={p:str(v) for p,v in raw.items()},
                interfaces=sum(inc.values())+sum(improved.values())+int(sum(raw.values()))+ceil(Q(3,5)+Q(11,20)))


def local_cost(length,cap):
    best=[10**6]*(2*cap+1)
    for mask in range(1<<length):
        ports=[j for j in range(length) if mask>>j&1]
        degrees={j:0 for j in ports}
        for a,b in zip(ports,ports[1:]):
            if b-a<=3:
                degrees[a]+=1
                degrees[b]+=1
        costs=sorted(degrees.values())
        for demand in range(min(2*cap,2*len(ports))+1):
            remain=demand
            value=0
            for c in costs:
                amount=min(2,remain)
                value+=amount*c
                remain-=amount
            best[demand]=min(best[demand],value)
    return best


def group_table(length,cap,total_twice,first,last):
    local=local_cost(length,cap)
    dp={0:0}
    table={}
    for n in range(1,last+1):
        nxt={}
        for s,value in dp.items():
            for q,cost in enumerate(local):
                if s+q<=total_twice:
                    nxt[s+q]=min(nxt.get(s+q,10**9),value+cost)
        dp=nxt
        if n>=first:
            table[n]=dp[total_twice]
    return table


def main():
    rates=solve_rates(0)
    flows=summarize(rates)
    tables={
      'grind':group_table(6,3,189,32,48),
      'shape':group_table(3,2,22,6,11),
      'pack':group_table(6,5,30,3,8),
      'fill':group_table(6,4,22,3,6)}
    weights={m:Q(tables[m][flows['counts'][m]],2) for m in tables}
    omega=sum(weights.values())
    mineral_cells=2*(70//3)
    inner_cells=2*69-1
    base_area=70**2-flows['manufacturing_area']-9**2-3*mineral_cells
    weighted_direction=flows['interfaces']+4*mineral_cells+8+omega+(inner_cells-mineral_cells-3)+4-91
    ordinary_direction=flows['interfaces']+(2*mineral_cells-2)+8+omega
    generic_inner_constant=flows['interfaces']+2*mineral_cells-2+8+(inner_cells-mineral_cells-3)+4
    generic_area_constant=4*base_area-generic_inner_constant
    extra_delta={}
    for m,area in AREA.items():
        if m in tables:
            keys=sorted(tables[m])
            drops=[Q(tables[m][a]-tables[m][a+1],2) for a in keys[:-1]]
            extra_delta[m]=str(4*area-max(drops))
        else:
            extra_delta[m]=str(4*area)
    extra_delta['box']='36'
    pj=[(p,j) for p in range(1,1226) for j in range(p+1)
        if 23*p-10*j>=flows['machines'] and 54*p-25*j>=flows['power_weight']]
    minpower=min(16*p-2*j for p,j in pj)
    first_extra=omega+min(Q(v) for v in extra_delta.values())
    area_extra=Q(generic_area_constant-minpower-first_extra,4)
    factor_pairs={a:[[w,a//w] for w in range(6,69) if a%w==0 and 6<=a//w<=68]
                  for a in (1107,1108,1109,1110,1111,1112)}
    edges=[]
    for L,k,t in ((71,2,1),(101,3,2),(138,2,2)):
        edges.append(dict(L=L,k=k,t=t,without_extra=ceil(Q(L-14-5*k,6)),
                          one_extra=ceil(Q(L-14-8*t-5*k,6))))
    rounding=[]
    for chi in (0,1):
        for s in range(2):
            strong=2*ceil((weighted_direction+s-2*chi)/2)
            candidate=2*ceil(Q(921+s-chi,2))
            original=2*ceil(Q(921+s,2))
            rounding.append(dict(chi=chi,xy_parity=s,strong=strong,candidate=candidate,original=original))
    result=dict(flows=flows,recipe_rates={r[0]:str(v) for r,v in zip(RECIPES,rates)},
                rates_at_r1={r[0]:str(v) for r,v in zip(RECIPES,solve_rates(1))},
                weight_tables_twice=tables,weights={m:str(v) for m,v in weights.items()},
                omega=str(omega),base_area=base_area,ordinary_direction=str(ordinary_direction),
                weighted_direction=str(weighted_direction),generic_inner_constant=generic_inner_constant,
                generic_area_constant=generic_area_constant,extra_delta=extra_delta,
                power_minimum=minpower,power_minimum_at_least_11=min(16*p-2*j for p,j in pj if p>=11),
                first_extra=str(first_extra),two_extra_minimum=str(omega+2*min(Q(v) for v in extra_delta.values())),
                integer_area_constant=4*base_area-ceil(weighted_direction),
                corner_area_upper=4*base_area-ceil(weighted_direction)+2-4*9,
                no_box_transport_direction=str(ordinary_direction+4*mineral_cells-(2*mineral_cells-2)-91),
                area_extra=str(area_extra),
                power_j_max={p:max(j for pp,j in pj if pp==p) for p in range(10,15)},
                factor_pairs=factor_pairs,edge_bounds=edges,rounding=rounding)
    (OUT/'arithmetic_supports.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
