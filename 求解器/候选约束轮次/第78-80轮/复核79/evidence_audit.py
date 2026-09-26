"""Exact, solver-free comparison of independent review results and submitted data."""
import os
os.sched_setaffinity(0,set(range(10)))
import json,hashlib,ast
from pathlib import Path
from fractions import Fraction as F
from collections import Counter

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3];A=OUT.parent/'推导78A';B=OUT.parent/'推导78B'
def read(p):return json.loads(p.read_text())

def canonical(d):
    if 'r' in d:x,y,w,h=d['r']
    else:x,y,w,h=(d[k] for k in ('x','y','w','h'))
    return d['kind'],x,y,w,h,d['axis']

def geometry(d):
    k,x,y,w,h,a=canonical(d)
    b={(x+i,y+j) for i in range(w) for j in range(h)}
    ps=[{(x-1,y+j) for j in range(h)},{(x+w,y+j) for j in range(h)}] if a==0 else [{(x+i,y-1) for i in range(w)},{(x+i,y+h) for i in range(w)}]
    return b,ps

def verify_point(chosen,wall,score):
    pole={(x,y) for x in (5,6) for y in (5,6)};reach={(x,y) for x in range(12) for y in range(12)}
    occupied=set(pole);geoms=[]
    for d in chosen:
        b,ps=geometry(d);assert not b&occupied and b&reach
        if wall:assert max(x for x,y in b)<=6
        occupied|=b;geoms.append((b,ps))
    for b,ps in geoms:
        for s in ps:assert any(c not in occupied and (not wall or c[0]<=6) for c in s)
    assert len(chosen)<=(14 if wall else 23)
    assert sum(2 if d['kind']=='s' else 3 for d in chosen)==score
    return dict(machines=len(chosen),counts=dict(Counter(d['kind'] for d in chosen)),weight=score)

def local_checks():
    out=[]
    for wall,prefix in [(False,'general_ge55'),(True,'wall_opt')]:
        ca=read(OUT/(prefix+'_cp_domain.json'));cb=read(OUT/(prefix+'_milp_domain.json'))
        aa={canonical(d):d for d in ca};bb={canonical(d):d for d in cb};assert aa.keys()==bb.keys()
        for key in aa:
            for sa,sb in zip(aa[key]['sides'],bb[key]['sides']):assert set(map(tuple,sa))==set(map(tuple,sb))
        submitted=read(A/('final_wall_model_a.json' if wall else 'final_general_model_a.json'))
        assert {canonical(d) for d in submitted['objects']}==aa.keys()
        out.append(dict(wall=wall,options=len(ca),review_encodings_equal=True,submitted_domain_equal=True))
    points=[]
    for path,wall,score,field in [(OUT/'general_ge54_cp.json',False,54,'witness'),(OUT/'wall_opt_cp.json',True,29,'witness'),(OUT/'wall_opt_milp.json',True,29,'witness'),(A/'final_general_a_witness.json',False,54,'chosen'),(A/'final_wall_a_opt.json',True,29,'chosen')]:
        points.append(dict(file=str(path.relative_to(OUT.parent)),**verify_point(read(path)[field],wall,score)))
    return dict(domains=out,witnesses=points)

def lp_certificates():
    checks=[]
    for cert in read(B/'weighted_account.json')['continuous_LP_certificates']:
        kind=cert['machine'];k=cert['low_regime_count'];x=list(map(F,cert['rates']));y=F(cert['dual_y']);lo_dual=list(map(F,cert['dual_lower']));hi_dual=list(map(F,cert['dual_upper']))
        if kind=='研磨机':n=32;total=F(189,2);bounds=[(F(3,2),F(2))]*k+[(F(2),F(3))]*(n-k);slope=[0]*k+[1]*(n-k);constant=-(n-k)
        elif kind=='塑形机':n=6;total=F(11);bounds=[(F(1),F(1))]*k+[(F(1),F(2))]*(n-k);slope=[0]*k+[1]*(n-k);constant=0
        else:n=3;total=F(11);bounds=[(F(3),F(3))]*k+[(F(3),F(4))]*(n-k);slope=[0]*k+[2]*(n-k);constant=2*k-2*(n-k)
        assert len(x)==n and sum(x)==total
        assert all(lo<=v<=hi for v,(lo,hi) in zip(x,bounds))
        assert all(v>=0 for v in lo_dual) and all(v<=0 for v in hi_dual)
        assert all(y+l+h==c for c,l,h in zip(slope,lo_dual,hi_dual))
        primal=constant+sum(c*v for c,v in zip(slope,x))
        dual=constant+y*total+sum(l*lo+h*hi for (lo,hi),l,h in zip(bounds,lo_dual,hi_dual))
        assert primal==dual==F(cert['minimum'])
        checks.append(dict(machine=kind,low_regime_count=k,minimum=str(primal),primal_and_dual_exact=True))
    return checks

def structural():
    ours=read(OUT/'structural_checks.json');submitted=read(B/'structural.json')
    a={tuple(d['gaps']):set(map(tuple,d['allowed_poles'])) for d in ours['patterns']}
    b={tuple(d['gaps']):{tuple(z['p']) for z in d['pole_positions']} for d in submitted['pole_patterns']}
    assert a==b
    assert set(map(tuple,ours['inner_poles']))==set(map(tuple,submitted['pole_union']))
    assert ours['ordinary_count']==submitted['nonedge_cap20_count']
    return dict(pole_pattern_count=len(a),all_pole_patterns_equal=True,ordinary_count=ours['ordinary_count'])

def main():
    output=dict(local=local_checks(),submitted_weight_certificates=lp_certificates(),structural=structural())
    ins=[68,51,95,11,6,32,16,15,11];outs=[95,51,32,6,6,32,32,3,3]
    output['interface_counts']=dict(machine_inputs=ins,machine_outputs=outs,input_total=sum(ins),output_total=sum(outs),C=52+sum(ins)+sum(outs)+2,mergers_min=(52+sum(outs)-sum(ins)-2+1)//2)
    assert output['interface_counts']['C']==619 and output['interface_counts']['mergers_min']==3
    output['power_slack']=dict(ordinary_baseline=9*23,edge_baseline=13,total_baseline=9*23+13,unused=9*23+13-217,edge_min=13-3,ordinary_min=23-3)
    domain=read(OUT/'boundary_le186_native_quick_domain.json')
    linear=read(OUT/'boundary_le186_linear_highs_domain.json')
    submitted_domain=read(B/'projected_domain.json')
    def key(d):return (*canonical(d),d['j'],d['loss'],tuple((tuple(map(tuple,ps)),n) for ps,n in d['ports']))
    assert {key(d) for d in domain}=={key(d) for d in linear}=={key(d) for d in submitted_domain}
    output['global_domain_compare']=dict(options=len(domain),all_ports_needs_j_loss_equal=True)
    forced=[(1,69),(69,1),(48,69),(69,16)]
    hits={str(c):sum(c in set(map(tuple,u['body'])) for u in domain if u['kind']!='p') for c in forced}
    assert not any(hits.values());output['four_forced_holes_body_options']=hits
    # Independent affine substitution for the cut identity: conservation gives
    # f_out = 7 + q_core - 2G - sum(a_i) + f_in.
    # Substituting into u_cut and then into its claimed RHS gives its LHS.
    u={'constant':16-7,'height':-1,'core':-1,'G':2,'a':1,'f_in':-2}
    right=Counter(u)
    for key,value in [('f_in',2),('kappa',1),('a',-1),('core',1)]:right[key]+=value
    right={k:v for k,v in right.items() if v}
    assert right=={'constant':9,'height':-1,'G':2,'kappa':1}
    output['cut_affine_identity']=right
    required=['general_ge55_cp.json','general_ge55_milp.json','wall_opt_cp.json','wall_opt_milp.json','boundary_le186_native_quick.json','boundary_le186_linear_cp.json','boundary_le186_linear_highs.json']
    output['receipts']=[dict(file=n,**{k:v for k,v in read(OUT/n).items() if k in ('status','message','seconds','wall_seconds','solver_seconds','weight','options','units','model_sha256')}) for n in required]
    output['unknown_runs']=[dict(file=n,status=read(OUT/n)['status'],seconds=read(OUT/n)['seconds']) for n in ['boundary_eq185_cp.json','boundary_eq186_cp.json','boundary_le186_cp.json'] if (OUT/n).exists()]
    for n in ['boundary_le186_native_quick.json','boundary_le186_linear_cp.json','boundary_le186_linear_highs.json']:assert read(OUT/n)['status']=='INFEASIBLE'
    inp=read(OUT/'input_manifest.json')
    for n,rec in inp.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==rec['sha256']
    producer_inputs=[]
    for src in (A,B):
        manifest=read(src/'input_manifest.json')
        for n in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt']:
            entry=manifest[n]
            expected=entry if isinstance(entry,str) else entry['sha256']
            assert expected==inp[n]['sha256']
        producer_inputs.append(dict(group=src.name,three_official_files_same=True))
    output['producer_inputs']=producer_inputs
    lines=(ROOT/'求解约束.txt').read_text().splitlines()
    output['formal_constraint_count']=sum(bool(line) and not line[0].isspace() and i+1<len(lines) and lines[i+1].strip().startswith('据：') for i,line in enumerate(lines))
    assert output['formal_constraint_count']==72
    output['branch_coverage']=[dict(position=list(pos),P=10,J=1,S=s,group_A='520>515',group_B='delta=0 < W-109 >= 1/2' if s==187 else 'S<=186 projection INFEASIBLE in both encodings') for pos in [(49,17),(17,49)] for s in [185,186,187]]
    imports={}
    for p in OUT.glob('*.py'):
        tree=ast.parse(p.read_text());imports[p.name]=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):imports[p.name].extend(a.name for a in n.names)
            if isinstance(n,ast.ImportFrom):imports[p.name].append(n.module)
    output['script_imports']=imports
    (OUT/'evidence_audit.json').write_text(json.dumps(output,ensure_ascii=False,indent=2));print('exact evidence audit passed',flush=True)

if __name__=='__main__':main()
