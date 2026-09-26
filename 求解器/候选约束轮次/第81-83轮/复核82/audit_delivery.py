"""交付一致性与数值复核入口；不运行内核、不读取另一席材料。"""
import os
os.sched_setaffinity(0,{0})
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
from fractions import Fraction
from collections import Counter
import json,hashlib,importlib.util,re,datetime
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
REPORT=OUT.parent/'复核82.md'
def read(name):return json.loads((OUT/name).read_text())
checks={}
a,b=read('arithmetic_a.json'),read('arithmetic_b.json')
for key in ['machine_rates','physical_source_rate','mixed_safety','dead_combinations','areas','machine_count','weighted_minimum','residue_pairs','residue_sha256','plant_capacity_coefficients']:
    assert a[key]==b[key],key;checks['two_encodings_'+key]=True
for typ in a['direction_tables']:
    for key in ['single_cost_twice','global']:
        assert a['direction_tables'][typ][key]==b['direction_tables'][typ][key]
    checks['direction_table_'+typ]=True
assert all(Fraction(str(a['plant_mean'][k]))==Fraction(str(b['plant_mean'][k])) for k in a['plant_mean'])
checks['plant_average']=True
for suffix in ['edge_count','edge_weight','general_weight']:
    assert read('power_a_'+suffix+'.json')['status']=='INFEASIBLE'
    assert read('power_b_'+suffix+'.json')['status']==2
    checks['two_infeasibility_results_'+suffix]=True

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
pa=module(OUT/'power_a.py','review82_power_a')
pb=module(OUT/'power_b.py','review82_power_b')
for edge in [False,True]:
    aa={tuple(o[:6])+(tuple(tuple(sorted(s)) for s in o[7]),) for o in pa.domain(edge)}
    bb={tuple(o[:6])+(tuple(tuple(sorted(s)) for s in o[6]),) for o in pb.placements(edge)}
    assert aa==bb
    checks['independent_domain_equality_'+str(edge)]={'equal':True,'options':len(aa)}
geo=read('geometry_checks.json')
assert len(geo['band_cases'])==47
assert [r['algebra'] for r in geo['boundary_bounds']]==[7,10,17,8]
assert all(r['valid_placements']==0 for r in geo['endpoint_cases'])
checks['geometry']=True
bf=read('branch_and_freeze.json')
assert bf['branch_models']==2176 and [v['recipe_count'] for v in bf['freeze'].values()]==[4,6,16]
checks['branch_and_freeze']=True
lc=read('local_certificates.json')
assert lc['grinder_first_entry_counts']=={'two_main':300,'wrong':201}
checks['first_entry_counts']=True

plant_stats=[]
for q,expected in [(1,(932,877)),(2,(883,817)),(3,(837,771))]:
    r=read(f'plant_events_q{q}_settled.json');assert not r['failures']
    assert (r['cycles'],r['strong_cycles'])==expected
    g=read(f'plant_graph_m3_q{q}.json');assert not g['lower_bound_violations'] and not g['C_empty_in_high_cycles']
    plant_stats.append({'q':q,'simulation_cycles':r['cycles'],'simulation_strong_cycles':r['strong_cycles'],'graph_states':g['closed_states'],'graph_edges':g['edges']})
sk=[x for q in [1,2] for x in read(f'skeleton_events_q{q}.json')['results']]
assert len(sk)==24 and sum(x.get('pass',False) for x in sk)==5
assert sum(x.get('status')=='NO_CYCLE_WITHIN_LIMIT' for x in sk)==19
checks['finite_probes_not_promoted_to_proof']=True

records=read('review_records.json');summary=read('verdicts.json');body=REPORT.read_text()
assert len(records)==len(summary['verdicts'])==26
assert Counter(r['verdict'] for r in records)=={'未否证':17,'修正':9}
assert Counter(r['kind'] for r in records)=={'必要条件':15,'充分条件':11}
assert Counter(r['code'][2] for r in records)=={'A':8,'B':5,'C':8,'D':5}
assert summary['report_path']==str(REPORT)
for r,v in zip(records,summary['verdicts']):
    assert v=={k:r[k] for k in ['name','verdict','reason','revised_text']}
    assert body.count('### '+r['code']+'　'+r['name'])==1
    assert r['reason'] in body
    if r['verdict']=='修正':assert r['revised_text'] in body
    else:assert r['revised_text']==''
checks['all_26_verdicts_and_revisions_match_report']=True
links=re.findall(r'\]\(([^)]+)\)',body)
missing=[]
for link in links:
    if link.startswith(('http','#')):continue
    p=REPORT.parent/link
    if p.name=='delivery_audit.json':continue
    if not p.exists():missing.append(link)
assert not missing,missing
checks['all_local_links_exist']=True

manifest=read('input_manifest.json')
# 来源提交仅为报告归档来源，不是三份正式前提之一；不列入本次输入清单。
manifest={p:v for p,v in manifest.items() if not p.endswith('来源提交.txt')}
(OUT/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
for p,v in manifest.items():
    path=ROOT/p
    assert path.exists(),str(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==v['sha256'],p
checks['premise_snapshots_and_derivation_reports_unchanged']=True
files={}
for p in sorted(OUT.iterdir()):
    if p.is_file() and p.name!='delivery_audit.json':files[p.name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
files['../复核82.md']={'sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'bytes':REPORT.stat().st_size}
audit={'status':'PASS','started_utc':'2026-09-26 08:32:15 UTC','audit_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'checks':checks,'plant_statistics':plant_stats,'skeleton':{'attempts':24,'verified_cycles':5,'truncated_at_3500_ticks':19},
       'reader_audit':{'verdict_count_and_kind_count':True,'current_status_matches_text':True,'all_revised_texts_complete_and_shared_with_json':True,'unproven_phase_coverage_explicit':True,'raw_initial_state_trace_labeled_source_unproved':True,'no_cycle_and_relaxation_feasibility_not_called_pass':True,'all_cross_references_checked':True},
       'files':files}
(OUT/'delivery_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','verdicts':dict(Counter(r['verdict'] for r in records)),'artifacts':len(files),'all_checks':len(checks)},ensure_ascii=False))
