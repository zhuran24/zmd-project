"""Review arithmetic B: twenty-tick backward demand and explicit port vectors."""
from fractions import Fraction
from pathlib import Path
from itertools import product
import json

OUT=Path(__file__).resolve().parent


def ceil20(x):
    return (x+19)//20


def flow_inventory():
    battery,capsule=12,11
    parts,bottle,dense_source,fine_buck=10*battery,10*capsule,15*battery,10*capsule
    steel=parts+2*bottle
    dense_blue=steel
    blue_powder=2*dense_blue
    source_powder=2*dense_source
    buck_powder=2*fine_buck
    sand_powder=dense_blue+dense_source+fine_buck
    buck_crush=buck_powder//2
    sand_crush=sand_powder//3
    assert buck_crush*2==buck_powder and sand_crush*3==sand_powder
    loads={
       'crush':source_powder+blue_powder+buck_crush+sand_crush,
       'refine':blue_powder+steel,
       'grind':dense_blue+dense_source+fine_buck,
       'shape':bottle,'fit':parts,
       'plant':2*(buck_crush+sand_crush),'seed':buck_crush+sand_crush,
       'pack':5*battery,'fill':5*capsule}
    ins={
       'crush':loads['crush'],'refine':loads['refine'],
       'grind':3*loads['grind'],'shape':2*bottle,'fit':parts,
       'plant':loads['plant'],'seed':loads['seed'],'pack':25*battery,'fill':20*capsule}
    outs=dict(loads)
    outs.update(crush=source_powder+blue_powder+buck_powder+sand_powder,
                seed=2*loads['seed'],pack=battery,fill=capsule)
    counts={m:ceil20(q) for m,q in loads.items()}
    areas={m:(25 if m in ('plant','seed') else 24 if m in ('grind','pack','fill') else 9) for m in loads}
    in_channels={m:ceil20(q) for m,q in ins.items()}
    out_channels={m:ceil20(q) for m,q in outs.items()}
    raw=sum(out_channels.values())
    for m in ('pack','fill'):
        out_channels[m]=max(out_channels[m],counts[m])
    sizes={'small':counts['crush']+counts['refine']+counts['fit']+counts['shape'],
           'medium':counts['plant']+counts['seed'],
           'large':counts['grind']+counts['pack']+counts['fill']}
    return dict(counts=counts,machines=sum(counts.values()),
                machines_by_size=sizes,power_weight=sum(counts.values())*3-sizes['small'],
                manufacturing_area=sum(counts[m]*areas[m] for m in loads),
                input_channels=sum(in_channels.values()),input_by_machine=in_channels,
                output_channels_raw=raw,output_channels=sum(out_channels.values()),
                output_by_machine=out_channels,ore={'ore_b':str(blue_powder//20),'ore_s':str(source_powder//20)},
                interfaces=sum(in_channels.values())+sum(out_channels.values())+(blue_powder+source_powder)//20+ceil20(battery+capsule))


def minima(ports,per_machine,total,lo,hi):
    costs=[10**8]*(2*per_machine+1)
    for vector in product(range(3),repeat=ports):
        q=sum(vector)
        if q>2*per_machine:
            continue
        charge=0
        for i,flow in enumerate(vector):
            if not flow:
                continue
            charge+=flow*int(any(vector[j] for j in range(max(0,i-3),i)))
            charge+=flow*int(any(vector[j] for j in range(i+1,min(ports,i+4))))
        costs[q]=min(costs[q],charge)
    cumulative=[10**8]*(total+1)
    cumulative[0]=0
    result={}
    for count in range(1,hi+1):
        cumulative=[min((cumulative[d-q]+costs[q] for q in range(min(d,2*per_machine)+1)),default=10**8)
                    for d in range(total+1)]
        if count>=lo:
            result[count]=cumulative[total]
    return result


def main():
    flows=flow_inventory()
    tables={'grind':minima(6,3,189,32,48),'shape':minima(3,2,22,6,11),
            'pack':minima(6,5,30,3,8),'fill':minima(6,4,22,3,6)}
    weights={m:Fraction(tab[flows['counts'][m]],2) for m,tab in tables.items()}
    omega=sum(weights.values())
    power=[]
    for p in range(10,1226):
        for j in range(p+1):
            if flows['machines']+10*j<=23*p and flows['power_weight']+25*j<=54*p:
                power.append((p,j))
    area=4900-flows['manufacturing_area']-81-46*3
    ordinary=flows['interfaces']+90+8+omega
    weighted=ordinary+184-90-91+88+4
    generic=flows['interfaces']+90+8+88+4
    area_constant=area*4-generic
    extra={}
    for m in flows['counts']:
        footprint=25 if m in ('seed','plant') else 24 if m in ('grind','pack','fill') else 9
        values=tables.get(m)
        if values:
            extra[m]=str(min(Fraction(8*footprint+values[n+1]-values[n],2) for n in values if n+1 in values))
        else:
            extra[m]=str(4*footprint)
    extra['box']='36'
    first_extra=omega+min(Fraction(x) for x in extra.values())
    pmin=min(16*p-2*j for p,j in power)
    factors={a:[] for a in (1107,1108,1109,1110,1111,1112)}
    for w in range(6,69):
        for h in range(6,69):
            if w*h in factors:
                factors[w*h].append([w,h])
    edges=[]
    for length,segments,spare in ((138-30-37,2,1),(138-37,3,2),(138,2,2)):
        low0=next(x for x in range(139) if 6*x+14+5*segments>=length)
        low1=next(x for x in range(139) if 6*x+14+8*spare+5*segments>=length)
        edges.append(dict(L=length,k=segments,t=spare,without_extra=low0,one_extra=low1))
    rounding=[]
    for corner in (0,1):
        for parity in (0,1):
            candidates=range(900,950,2)
            strong=next(x for x in candidates if x>=weighted+parity-2*corner)
            proposed=next(x for x in candidates if x>=921+parity-corner)
            old=next(x for x in candidates if x>=921+parity)
            rounding.append(dict(chi=corner,xy_parity=parity,strong=strong,candidate=proposed,original=old))
    result=dict(flows=flows,weight_tables_twice=tables,weights={m:str(v) for m,v in weights.items()},
                omega=str(omega),base_area=area,ordinary_direction=str(ordinary),weighted_direction=str(weighted),
                generic_inner_constant=generic,generic_area_constant=area_constant,extra_delta=extra,
                power_minimum=pmin,power_minimum_at_least_11=min(16*p-2*j for p,j in power if p>=11),
                first_extra=str(first_extra),two_extra_minimum=str(omega+2*min(Fraction(x) for x in extra.values())),
                integer_area_constant=int(4*area-weighted),corner_area_upper=int(4*area-weighted)+2-36,
                no_box_transport_direction=str(flows['interfaces']+46*4+8+omega-91),
                area_extra=str((area_constant-pmin-first_extra)/4),
                power_j_max={p:max(j for pp,j in power if pp==p) for p in range(10,15)},
                factor_pairs=factors,edge_bounds=edges,rounding=rounding)
    (OUT/'arithmetic_vectors.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
