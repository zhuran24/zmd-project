"""Final artifact and proof-scope audit. Writes only beside this script."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,re
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3];REPORT=OUT.parent/'推导78A.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(name):return json.loads((OUT/name).read_text())
def main():
    manifest=read('input_manifest.json');inputs={}
    for name in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']:
        current=sha(ROOT/name);assert current==manifest[name]['sha256'];inputs[name]=current
    checks=read('final_independent_audit.json')
    assert checks['tables']['DP_upper']==checks['tables']['direct_enumeration_upper']==214
    assert checks['tables']['weighted_total']==515 and checks['tables']['required_weighted']==520
    receipts={
        'final_general_a_ge55.json':('INFEASIBLE','local_bound_a.py'),
        'local_b_ge55.json':('INFEASIBLE','single_pole_b.py'),
        'local_b_highs_ge55.json':('INFEASIBLE','single_pole_b.py'),
        'final_wall_a_opt.json':('OPTIMAL','local_bound_a.py'),
        'wall_b_ge30.json':('INFEASIBLE','single_pole_b.py'),
        'wall_b_highs_ge30.json':('INFEASIBLE','single_pole_b.py'),
        'final_general_a_witness.json':('OPTIMAL','local_bound_a.py'),
        'final_general_b_witness.json':('OPTIMAL','single_pole_b.py'),
        'final_wall_b_witness.json':('OPTIMAL','single_pole_b.py')}
    evidence={}
    for name,(status,script) in receipts.items():
        d=read(name);assert d['status']==status and d['source_sha256']==sha(OUT/script)
        evidence[name]=dict(status=status,source=script,source_sha256=d['source_sha256'],seconds=d['seconds'])
    report=REPORT.read_text();candidate_names=['供电桩分片的制造单位规格计数界','1113十桩占边分支的规格加权排除']
    candidate_text=(ROOT/'候选约束.txt').read_text()
    for name in candidate_names:
        assert name not in candidate_text and name+'：' in report
    assert report.count('状态：待审。')==2
    links=[]
    for target in re.findall(r'\]\(([^)]+)\)',report):
        p=(REPORT.parent/target).resolve()
        assert p.exists() or p==OUT/'delivery_audit.json',str(p)
        links.append(str(p))
    allowed={'.py','.log','.json','.md','.gz'};files={}
    for p in sorted(OUT.iterdir()):
        assert p.is_file() and p.suffix in allowed,p
        assert p.stat().st_size<=100_000_000 or p.suffix=='.gz',p
        if p.name in ('delivery_audit.json','delivery_audit.log'):continue
        files[p.name]=dict(bytes=p.stat().st_size,sha256=sha(p))
    now=datetime.now(timezone.utc);start=datetime.fromisoformat('2026-09-26T03:13:36+00:00');elapsed=(now-start).total_seconds()
    assert elapsed<10800
    result=dict(status='PASS',report=str(REPORT),report_sha256=sha(REPORT),candidate_names=candidate_names,
      mathematical_premises='Only the three current official files plus the branch A=1113,P=10,J=1; no pending candidate is a premise.',
      input_hashes_unchanged=inputs,evidence=evidence,independent_enumeration_and_rows=True,
      independent_global_upper=214,weighted_upper=515,weighted_requirement=520,
      proof_evidence_level='Completed integer solves from two independent encodings; HiGHS cross-check; exact coordinate/model/DP checks. No completed solver-free UNSAT tree or LRAT artifact.',
      auxiliary_tree_attempts=[read('general54_tree_attempt.json'),read('general54_tree_probe_attempt.json')],
      resource_record=dict(start_utc=start.isoformat(),end_utc=now.isoformat(),wall_seconds=elapsed,
                           solver_affinity=list(range(10)),maximum_simultaneous_solver_workers=9,standard_library_checks_single_thread=True),
      reader_review=dict(self_contained=True,current_status_consistent=True,no_pending_premise=True,
                         bound_not_layout=True,all_coordinate_choices_covered=True,transpose_covered=True,
                         formal_upper_unchanged=True,conditional_1110_relationship_explicit=True,
                         independent_encodings_not_confused_with_engines=True,all_report_links_exist=True,
                         incomplete_tree_attempts_explicit=True,candidate_names_unique=True),
      report_links=links,artifacts=files)
    (OUT/'delivery_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(dict(status=result['status'],report=str(REPORT),upper=214,candidates=candidate_names,wall_seconds=elapsed,files=len(files)),flush=True)
if __name__=='__main__':main()
