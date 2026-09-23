#!/usr/bin/env python3
"""闸门第1轮具体反例回归；部件测试不产生全厂通过证书。"""
import os, sys
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[k]='1'
sys.dont_write_bytecode=True
import copy, json, hashlib
from pathlib import Path
from catalog import HASHES, constraints, nb, opp
from check_full import Report, make_output
from geometry import Geometry
from design import check_design
from projections import geometry_checks
from selftest import empty, machine, belt, geo, status, normalize

BASE=Path(__file__).resolve().parent
EVIDENCE=BASE.parent/'闸门第1轮证据'
raw=(BASE.parent/'修复第1轮证据/候选-修复前.json').read_bytes()
d=json.loads(raw)
results=[]

def record(name, detail):
    results.append({'name':name,'pass':True,'detail':detail})

# D1: current entry must run the actual geometry and LP, without process monkeypatching.
out=make_output(raw,60)
(BASE/'gate1-original-candidate.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
cs={c['id']:c for c in out['checks']}
assert cs['fingerprints']['status']=='checked'
assert out['recomputed']['structural_channels']==424
assert out['recomputed']['maximum_empty_rectangle']['area']==48
assert out['flow']['status']=='violation'
assert cs['P2_structure']['status']=='checked' and cs['P2']['status']=='blocked'
assert 'B_feeds' not in cs
assert len(out['formal_constraints'])==72
assert [x['name'] for x in out['formal_constraints'][63:]]==[
    '1113 位置','面积预算','增机面积界','侧旁供电','矩形离带','回路转弯','矿石走廊','四通结点','内带缺口']
record('D1-current-version-and-D7-P2',{'channels':424,'area':48,'LP':'violation','P2':'blocked','ledger':72})
old=copy.deepcopy(d)
old['source_fingerprints']['constraints']='cf44821f07779490b9b1d913bfb87d7757ae8abfe784c912bb7891868780f7f3'
oldout=make_output(json.dumps(old,ensure_ascii=False).encode(),10)
assert oldout['status']=='rejected' and 'recomputed' not in oldout
record('D1-old-fingerprint-not-silently-accepted',{'status':oldout['status']})

# New #64 is independently exercised at each formally permitted position, plus wrong position/orientation.
g,_=geo(d)
legal=[(21,53,49,y) for y in (6,7,9,17)]+[(53,21,x,49) for x in (6,7,9,17)]
for W,H,x,y in legal+[(21,53,48,6),(53,21,6,48)]:
    g.maximum={'area':1113,'short_side':21,'bounds':dict(x0=x,y0=y,x1=x+W-1,y1=y+H-1)}
    r=Report();geometry_checks(g,r)
    assert status(r,'C64')==('checked' if (W,H,x,y) in legal else 'violation')
record('D1-1113-position-predicate',{'legal_cases':8,'illegal_cases':2,'scope':'只替换投影层矩形输入，不是合法全厂实例'})

# D3: provenance is not a demand to preserve the original 315 LF records.
a=copy.deepcopy(d);b=copy.deepcopy(d);b.pop('provenance')
ga,ra=geo(a);gb,rb=geo(b);check_design(ga,ra);check_design(gb,rb)
assert ga.channels==gb.channels and 'B_feeds' not in ra.checks and 'B_feeds' not in rb.checks
claim=copy.deepcopy(d['design']['restrictions'][0]);claim.update(id='candidate-b',statement='逐项保持候选B')
a['design']['restrictions'].append(claim)
ga,ra=geo(a);check_design(ga,ra)
assert status(ra,'B_feeds')=='violation'
record('D3-provenance-versus-preservation',{'channels_unchanged':424,'provenance_only':'no B_feeds obligation','explicit_preservation_without_LF':'violation'})

# D2: natural single-recipe models are not an extra restriction; actual subsets are.
for rid,needs in [('配件-钢制零件',False),('精炼-蓝铁矿',True)]:
    q=empty();q['layout']['machines']=[machine('M',3,3,rid)]
    gg,rr=geo(q);check_design(gg,rr)
    assert status(rr,'recipe_restriction_registration')==('violation' if needs else 'checked')
    if needs:
        rec=copy.deepcopy(claim);rec.update(id='recipe-subsets',statement='recipe_ids 限定本候选的配方集合；不把它当成游戏开关。')
        q['design']['restrictions']=[rec];gg,rr=geo(q);check_design(gg,rr)
        assert status(rr,'recipe_restriction_registration')=='checked' and status(rr,'recipe-subsets')=='checked'
        rec['statement']='任意改写不应被静默解释';gg,rr=geo(q);check_design(gg,rr)
        assert status(rr,'recipe-subsets')=='violation'
        rec.update(id='unknown-subset',statement='自由文本登记');gg,rr=geo(q);check_design(gg,rr)
        assert status(rr,'recipe_restriction_registration')=='unresolved'
record('D2-recipe-registration',{'natural_single_recipe':'no extra requirement','actual_subset':'requires registration','wrong_statement':'violation','unknown_registration':'unresolved'})

# Single-ended bridge: an existing physical connection remains even though N4a rejects its dead end.
counter=json.loads((EVIDENCE/'单端桥测例.json').read_text())
gg,rr=geo(counter)
expected={(('OUT_L00',0,1),('BR_TEST',2,0))}
assert set(gg.channels)==expected and status(rr,'N4a')=='violation' and status(rr,'N5a')=='violation'
for side in range(4):
    for neighbor_io in ('in','out'):
        q=empty();xy=nb((10,10),side)
        q['layout']['transport']=[{'id':'BR','x':10,'y':10,'type':'bridge','H_in':None,'V_in':None},
                                 belt('T',*xy,opp(side) if neighbor_io=='in' else side,side if neighbor_io=='in' else opp(side))]
        gg,rr=geo(q)
        edge=(('BR',side,0),('T',opp(side),0)) if neighbor_io=='in' else (('T',opp(side),0),('BR',side,0))
        assert set(gg.channels)=={edge} and status(rr,'N4a')=='violation' and status(rr,'N5a')=='violation'
record('single-ended-bridge-iff-reconstruction',{'gate_fixture_edges':1,'direction_and_io_cases':8,'N4a':'violation','omitted_declared_edge_N5a':'violation'})

# Compare the full real candidate's rebuilt channels to the frozen independent gate result, by endpoint.
old_b=json.loads((EVIDENCE/'B原始.json').read_text())
old_a=json.loads((EVIDENCE/'A适配诊断.json').read_text())
assert out['recomputed']['channels']==old_a['recomputed']['channels']
record('full-candidate-no-channel-regression',{'exact_endpoint_list_equal':True,'channels':424,'candidate_sha256':hashlib.sha256(raw).hexdigest()})
summary={'scope':'闸门第1轮检查器A修复回归；不认证全厂可行','total':len(results),'passed':len(results),'failed':0,'results':results}
(BASE/'gate1-regression.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
