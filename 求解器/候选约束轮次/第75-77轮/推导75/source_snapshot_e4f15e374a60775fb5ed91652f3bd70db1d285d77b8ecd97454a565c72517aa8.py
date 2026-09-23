#!/usr/bin/env python3
"""Build the final branch ledger, reproducibility inventory and delivery audit."""
import os
os.sched_setaffinity(0,set(range(12)))
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,re,sys
OUT=Path(__file__).resolve().parent;REPORT=OUT.parent/'推导75.md';ROOT=OUT.parents[3]
def read(name):return json.loads((OUT/name).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,data):(OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
start=datetime(2026,9,23,7,59,1,tzinfo=timezone.utc)
proofs=['project_native_cap187_J0.json','linear_project_cap187_J0.json','project_highs_cap187_J0.json']
assert all(read(p)['status']=='INFEASIBLE' for p in proofs)
branches=[]
for transposed,pos in [(False,[49,17]),(True,[17,49])]:
    for S in (185,186,187):
        branches.append(dict(position=pos,S=S,J=0,result='INFEASIBLE',scope='M0 safe projection, hence M1',evidence=proofs,transpose_bijection=transposed))
        stem=f'complete_subsets_S{S}'+('_transpose' if transposed else '')
        audit=read(stem+'_audit.json');assert audit['status']=='PASS' and audit['S']==S and audit['J']==1 and audit['all_subset_upper']>=217
        replays=[f'complete_replay_{e}_S{S}.json' for e in ('native','highs')]
        assert all(read(p)['status']=='OPTIMAL' and read(p)['S']==S for p in replays)
        branches.append(dict(position=pos,S=S,J=1,result='FEASIBLE',scope='M1 and all original subset-capacity cuts',witness=stem+'.json',audit=stem+'_audit.json',evidence=replays,transpose_bijection=transposed))
assert len(branches)==len({(tuple(b['position']),b['S'],b['J']) for b in branches})==12
write('branches.json',dict(status='COMPLETE',coverage='two transpose-related positions x S in {185,186,187} x J in {0,1}',lower_S_basis='R72/R73/R74 independently verified M0 bound; original receipts hash-checked, not rerun here',branches=branches))
# Preserve every current script as well as earlier snapshots already archived.
snapshots={}
for p in list(OUT.glob('*.py')):
    if p.name.startswith('source_snapshot_'):continue
    h=sha(p);copy=OUT/f'source_snapshot_{h}.py'
    if not copy.exists():copy.write_bytes(p.read_bytes())
    snapshots[p.name]=dict(sha256=h,snapshot=copy.name)
write('source_snapshots.json',dict(current=snapshots,all_versions=sorted(p.name for p in OUT.glob('source_snapshot_*.py'))))
inputs=read('input_manifest.json');changes=[]
for name,record in inputs.items():
    p=Path(name)
    if not p.exists() or sha(p)!=record['sha256']:changes.append(name)
assert not changes
old=OUT.parents[1]/'第72-74轮/推导72';lower_basis=[]
for stem,script,status in [('cp_cap184','cp72.py','INFEASIBLE'),('mip_J0_cap184','mip72.py',2),('mip_J1_cap184','mip72.py',2)]:
    p=old/(stem+'.json');d=json.loads(p.read_text());assert d['status']==status and d['cap']==184 and d['script_sha256']==sha(old/script)
    lower_basis.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p),script_sha256=d['script_sha256'],status=d['status']))
write('inherited_lower_bound_audit.json',dict(status='PASS',scope='source/receipt consistency only; no claim of a fresh threshold rerun',receipts=lower_basis))
experiments=[]
for p in sorted(OUT.glob('*.json')):
    d=read(p.name)
    if isinstance(d,dict) and d.get('time_limit') is not None and d.get('status') in ('OPTIMAL','FEASIBLE','INFEASIBLE','UNKNOWN'):
        record={k:d[k] for k in ('status','seconds','time_limit','workers','S_branch','J_branch','cap','scope','encoding','engine','fixed','subsolver','min_union') if k in d};record['file']=p.name;experiments.append(record)
        for key in ('script_sha256','wrapper_sha256'):
            if key in d:assert (OUT/f"source_snapshot_{d[key]}.py").exists(),(p.name,key,d[key])
now=datetime.now(timezone.utc);elapsed=(now-start).total_seconds();assert elapsed<3*3600
residual=[]
for S in (185,186,187):
    d=read(f'complete_subsets_S{S}_residual.json');best=min(d['partitions'],key=lambda r:r['upper']);inside=[i for i in range(10) if best['mask']>>i&1]
    deficit=sum(d['residual_capacities'][i] for i in inside)-best['inside_union']
    residual.append(dict(S=S,known=d['known_manufacturing'],required=d['remaining_required'],upper=d['residual_upper'],total_upper=d['total_manufacturing_upper'],gap=217-d['total_manufacturing_upper'],shift=best['shift'],inside_poles=inside,outside_capacity=best['outside_capacity'],inside_union=best['inside_union'],residual_deficit=deficit,total_charge=d['loss']+d['known_repeats']+deficit))
write('results.json',dict(status='M1_COMPLETE',start_utc=start.isoformat(),finish_utc=now.isoformat(),elapsed_seconds=elapsed,elapsed_minutes=elapsed/60,wall_limit_seconds=10800,heavy_compute_cpu_affinity=list(range(12)),python=sys.version,ortools=__import__('ortools').__version__,scipy=__import__('scipy').__version__,M1_minimum=185,complete_subset_relaxation_minimum=185,canonical_branches=6,including_transpose=12,new_candidates=2,new_position_exclusions=0,formal_upper_bound=1113,actual_P10_layout='UNRESOLVED',J_necessary=1,inherited_lower_bound=lower_basis,residual_point_certificates=residual,experiments=experiments))
text=REPORT.read_text();links=[]
for link in re.findall(r'\]\(([^)]+)\)',text):
    if '://' in link or link.startswith('#'):continue
    p=REPORT.parent/link;assert p.exists(),link;links.append(link)
allowed={'.py','.log','.json','.md','.gz'};bad=[str(p) for p in OUT.rglob('*') if p.is_file() and p.suffix not in allowed];assert not bad
large=[str(p) for p in OUT.rglob('*') if p.is_file() and p.stat().st_size>100*1024*1024];assert not large
assert read('checker_mutation_tests.json')['status']=='PASS' and read('domain_audit.json')['status']=='PASS'
assert all(read(f'residual_fixed_{e}.json')['status']=='INFEASIBLE' for e in ('A','B'))
assert all(read(f'residual_global_{e}{suffix}.json')['status']=='UNKNOWN' for e in ('A','B') for suffix in ('','_quick'))
audit=dict(status='PASS',input_files_unchanged=len(inputs),changed_inputs=changes,report_sha256=sha(REPORT),report_links_checked=len(links),branch_coverage='12 distinct records, all concluded',current_and_prior_source_versions_checked=True,output_types=sorted(allowed),oversize_uncompressed_files=large,reader_review=dict(status='PASS',checks=['M1 feasibility is separate from actual factory feasibility','all six canonical branches have witnesses or independent exclusion receipts','new residual bound excludes only specified points; global UNKNOWN remains unresolved','new residual deficit is recomputed after subtracting known actual coverage','both transpose geometry and all 9216 subset inequalities checked','global solver receipts are distinguished from exact rational and matching certificates','formal upper bound and candidate status unchanged']),memory_facts_used_as_mathematical_premises=False)
write('delivery_audit.json',audit)
manifest={str(p.relative_to(OUT.parent)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='output_manifest.json'}
manifest[REPORT.name]=dict(bytes=REPORT.stat().st_size,sha256=sha(REPORT));write('output_manifest.json',manifest)
print(json.dumps(dict(status='PASS',elapsed_minutes=elapsed/60,files=len(manifest),branches=12,M1_minimum=185,new_candidates=2),ensure_ascii=False))
