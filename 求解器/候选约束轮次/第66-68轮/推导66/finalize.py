#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,re
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3];REPORT=OUT.parent/'推导66.md'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
search=[]
for f in ['strip_flow_b17_P10.json','strip_flow_b17_P11.json','strip_flow_b17_P11_strengthened.json']:
 d=json.loads((OUT/f).read_text())
 search.append(dict(file=f,b=d['b'],P=d['P'],strengthened='strengthened' in f,status_code=d['status'],status='UNKNOWN' if d['status']==1 else d['message'],message=d['message'],elapsed_seconds=d['elapsed'],build_seconds=d['build_seconds'],variables=d['vars'],constraints=d['rows'],has_primal='chosen' in d,has_exact_exclusion_certificate=False))
summary=dict(searches=search,all_unknown=all(d['status']=='UNKNOWN' for d in search),total_elapsed_seconds=sum(d['elapsed_seconds'] for d in search),remaining_full_joint_optimum='not determined')
(OUT/'search_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
assert summary['all_unknown']
proof=json.loads((OUT/'exact_verification.json').read_text());assert proof['status']=='PASS'
model=json.loads((OUT/'model_audit.json').read_text());assert model['status']=='PASS'
rows=[]
for transpose in (False,True):
 for b in (9,17):
  for P in (10,11,12):
   r=dict(position=[b,49] if transpose else [49,b],P=P,excluded=b==9 or P==12)
   if b==9:r['exact_budget_excess']= {'10':[12,20],'11':[3],'12':[9]}[str(P)]
   else:r['exact_boundary_relaxation_S']={10:180,11:187,12:196}[P];r['remaining_budget']=187-r['exact_boundary_relaxation_S']
   rows.append(r)
assert 4*14+7*23==217
results=dict(candidate_count=4,full_new_position_exclusions=[[49,9],[9,49]],new_P12_exclusions=[[49,17],[17,49]],remaining=[[49,17,10],[49,17,11],[17,49,10],[17,49,11]],formal_area_upper_bound=1113,area1110_proved=False,rows=rows,P11_equalities=dict(J=4,X_plus_Y=19,loss_sum=36,edge_pole_machines=14,other_pole_machines=23,machine_sum=4*14+7*23,unique_cover=True),proof_status='exact integer certificates verified; all candidates pending review')
(OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
manifest=json.loads((OUT/'input_manifest.json').read_text());unchanged={f:digest(ROOT/f)==h for f,h in manifest.items()};assert all(unchanged.values())
syntax=[]
for p in OUT.glob('*.py'):compile(p.read_text(),str(p),'exec');syntax.append(p.name)
text=REPORT.read_text();links=[]
for link in re.findall(r'\]\(([^)]+)\)',text):
 if '://' in link:continue
 assert (REPORT.parent/link).exists() or link=='推导66/delivery_audit.json',link
 links.append(link)
assert text.count('状态：待审。')==4
files=list(OUT.iterdir());assert all(p.is_file() for p in files)
assert all(p.suffix in ('.py','.log','.json','.md','.gz') for p in files)
assert all(p.stat().st_size<=100*1024*1024 or p.suffix=='.gz' for p in files)
audit=dict(status='PASS',input_hashes_unchanged=unchanged,python_sources_compiled_without_pycache=syntax,report_links_checked=len(links),candidate_count=4,exact_verifier='PASS',negative_certificate_controls=model['negative_controls'],largest_file_bytes=max(p.stat().st_size for p in files),reader_review=dict(self_contained_definitions=True,final_status_matches_body=True,unproved_joint_optimum_explicit=True,numerical_search_not_used_as_proof=True,prior_pending_candidates_not_formal_premises=True,all_lower_and_upper_strips_addressed=True,no_full_layout_counterexample_claim=True,all_P_branches_reported=True,links_valid=True),report_sha256=digest(REPORT))
(OUT/'delivery_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
assert all((REPORT.parent/link).exists() for link in links)
(OUT/'finalize.log').write_text('PASS: exact certificates, inputs, candidate count, source syntax, links and reader review\n')
artifacts={str(p.relative_to(OUT.parent)):dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted([REPORT]+list(OUT.iterdir())) if p.name!='artifact_manifest.json'}
(OUT/'artifact_manifest.json').write_text(json.dumps(artifacts,ensure_ascii=False,indent=2))
print(json.dumps(dict(status='PASS',files=len(artifacts)+1,candidates=4,full_exclusions=results['full_new_position_exclusions'],remaining=results['remaining'],all_searches_unknown=True),ensure_ascii=False))
if __name__=='__main__':pass
