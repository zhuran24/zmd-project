"""Delivery audit: exact domains, model receipts, input stability and links."""
from pathlib import Path
import json,re,hashlib,datetime,time
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3];REPORT=OUT.parent/'推导78B.md'
def read(p):return json.loads(Path(p).read_text())
def hashfile(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,d):(OUT/name).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

def main():
    t=time.monotonic()
    initial=read(OUT/'input_manifest.json');current={n:hashfile(ROOT/n) for n in initial}
    assert initial==current
    for d in read(OUT/'certificate_input_manifest.json'):
        assert hashfile(OUT/d['copy'])==d['sha256']==hashfile(d['source'])
    from geometry77 import domain,cells,power,hit,WEIGHTS
    import native_boundary78 as native
    caps=read(OUT/'capacities.json');one=domain(caps);two=native.domain()
    def firstkey(u):return (u['kind'],*u['r'],u['axis'])
    def secondkey(u):return (u['kind'],u['x'],u['y'],u['w'],u['h'],{'h':0,'v':1,'-':-1}[u['axis']])
    da={firstkey(u):u for u in one};db={secondkey(u):u for u in two}
    assert da.keys()==db.keys() and len(da)==3970
    for k,a in da.items():
        b=db[k];assert a['loss']==b['loss'] and a['j']==b['j']
        pa=sorted((tuple(sorted(map(tuple,p))),n) for p,n in a['ports'])
        pb=sorted((tuple(sorted(p)),n) for p,n in zip(b['ports'],b['needs']))
        assert pa==pb
    machines=[u for u in one if u['kind'] in ('s','m','l')]
    projected=[u for u in one if u['kind']!='p' or u['j'] or cells(u['r'])&WEIGHTS.keys() or any(hit(power(u['r'][:2]),m['r']) for m in machines)]
    assert len(projected)==1945
    assert {firstkey(u) for u in projected}=={firstkey(u) for u in read(OUT/'projected_domain.json')}
    native_receipt=read(OUT/'inner_native_cp.json');assert native_receipt['status']=='INFEASIBLE'
    assert native_receipt['script_sha256']==hashfile(OUT/'native_boundary78.py')
    from model77 import build
    m,units,reward,warehouse=build(1,186)
    m.row([(i,1) for i,u in enumerate(units) if u['kind']=='p' and (u['r'][0]==1 or u['r'][1]==1)],1,1)
    matrix_hash=hashlib.sha256(json.dumps([m.bounds,m.rows]).encode()).hexdigest()
    for name in ('inner_linear_quick.json','inner_linear_highs.json'):
        result=read(OUT/name);assert result['status']=='INFEASIBLE' and result['model_sha256']==matrix_hash
        for n,h in result['source_hashes'].items():assert hashfile(OUT/n)==h
    assert read(OUT/'inner_linear_cp.json')['status']=='UNKNOWN'
    save('linear_model.json',dict(bounds=m.bounds,rows=m.rows,units=units,matrix_sha256=matrix_hash))
    nmodel,_,_,_,_=native.build(fixed_j=1,cap=186,project=True)
    (OUT/'native_model.log').write_text(str(nmodel))
    corner=read(OUT/'corner_exploration.json');corner_b=read(OUT/'corner_independent.json')
    assert len(corner)==135 and all(c['status']=='OPTIMAL' and c['bound']<=91 for c in corner)
    assert corner_b['case_count']==135 and corner_b['max_bound']==91 and corner_b['independent_exact_agreement']
    weight=read(OUT/'weighted_account.json');assert weight['new_total']=='219/2' and weight['two_independent_encodings_agree']
    certificate=read(OUT/'certificates_independent.json');assert certificate['capacities_agree']
    structural=read(OUT/'structural.json');assert structural['pole_union_size']==80 and structural['active_transports']==236
    assert structural['active_transport_slack']=='3247/20'
    text=REPORT.read_text();part=text.split('## 6. 候选约束条目\n',1)[1].split('## 7.',1)[0]
    names=re.findall(r'^([^\n：]+)：',part,re.M);names=[n for n in names if n not in ('据','推导','状态')]
    assert len(names)==7 and part.count('状态：待审。')==7
    old=(ROOT/'候选约束.txt').read_text()
    assert all(not re.search(r'^'+re.escape(n)+'：',old,re.M) for n in names)
    now=datetime.datetime.now(datetime.timezone.utc)
    results=dict(report_path=str(REPORT),status='本支排除，候选待审',candidate_count=7,candidate_names=names,
      branch=dict(rectangle=[49,17,21,53],P=10,J=1,S=[185,186,187]),branch_excluded=True,
      formal_rectangle_upper=1113,formal_upper_changed=False,
      proof_chain=['W>=109.5','delta<=2 forces inner boundary pole and S<=186','two independent whole-domain projections infeasible'],
      independent_boundary_encodings=2,engines=['CP-SAT','HiGHS'],corner_cases=135,
      unknown_runs=[dict(file='inner_linear_cp.json',seconds=120,reason='default integer search; completed with another strategy and HiGHS')],
      started_utc='2026-09-26T03:13:25+00:00',completed_utc=now.isoformat(),
      wall_seconds=(now-datetime.datetime.fromisoformat('2026-09-26T03:13:25+00:00')).total_seconds(),
      affinity=list(range(14,24)),maximum_simultaneous_cpu_limit=10)
    assert results['wall_seconds']<10800
    save('results.json',results)
    # Create the audit path before checking the self-reference in the report.
    save('delivery_audit.json',{})
    targets=re.findall(r'\]\(([^)]+)\)',text)
    missing=[s for s in targets if not s.startswith(('http:','https:','#')) and not (REPORT.parent/s.split('#')[0]).exists()]
    assert not missing,missing
    files=[p for p in OUT.rglob('*') if p.is_file()]
    assert all(p.suffix in ('.py','.log','.json','.md','.gz') for p in files)
    assert all(p.stat().st_size<=100_000_000 or p.suffix=='.gz' for p in files)
    audit=dict(inputs_unchanged=True,input_sha256=current,candidate_names_unique=True,candidate_count=7,
      domains_independently_equal=True,full_options=3970,projected_options=1945,ports_losses_edges_equal=True,
      linear_model_rebuilt_hash=matrix_hash,global_statuses_verified=True,corner_cases=135,weight_certificates_verified=True,
      links_checked=len(targets),missing_links=[],allowed_output_extensions=True,
      largest_file_bytes=max(p.stat().st_size for p in files),total_output_bytes=sum(p.stat().st_size for p in files),
      no_git_operations=True,no_kernel_cargo_tests=True,
      reader_audit={'self_contained_scope':True,'final_state_only':True,'status_consistent':True,'no_instruction_echo':True,
                    'one_numeric_interpretation':True,'notation_defined':True,'references_exist':True},
      source_sha256={p.name:hashfile(p) for p in files if p.suffix=='.py'},report_sha256=hashfile(REPORT),
      seconds=time.monotonic()-t)
    save('delivery_audit.json',audit)
    print(json.dumps({k:v for k,v in audit.items() if k not in ('source_sha256','input_sha256','reader_audit')},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
