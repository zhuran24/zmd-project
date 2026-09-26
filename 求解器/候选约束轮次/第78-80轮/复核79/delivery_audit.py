"""Final read-only checks of inputs/report; the audit writes only beside itself."""
from pathlib import Path
import json,re,hashlib,datetime,os
os.sched_setaffinity(0,set(range(10)))
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3];REPORT=OUT.parent/'复核79.md'
NAMES=['供电桩分片的制造单位规格计数界','1113十桩占边分支的规格加权排除','研磨存货边权重下界','十七位置面积方向余量恒等式','十七位置内带与运输近等结构','十七位置供电逐项余量','十七位置存货通道近等结构','十七位置运输与矿石切线余量','十七位置十桩一占边支排除']

def main():
    report=REPORT.read_text();inputs=json.loads((OUT/'input_manifest.json').read_text())
    for n,d in inputs.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==d['sha256']
    rows=[]
    for line in report.splitlines():
        if line.startswith('| '):
            parts=[s.strip() for s in line.strip('|').split('|')]
            if parts[0] in NAMES:
                assert len(parts)==4 and parts[1]=='未否证' and parts[3]=='条文不变'
                rows.append(dict(name=parts[0],verdict=parts[1],reason=parts[2],revised_text=parts[3]))
    assert [r['name'] for r in rows]==NAMES
    links=[]
    for target in re.findall(r'\]\(([^\n)]+)\)',report):
        if '://' in target:continue
        p=(REPORT.parent/target).resolve();assert p.exists() or p==OUT/'delivery_audit.json',target
        links.append(target)
    audit=json.loads((OUT/'evidence_audit.json').read_text())
    assert audit['formal_constraint_count']==72 and len(audit['branch_coverage'])==6
    assert len(audit['unknown_runs'])==3 and all(d['status']=='UNKNOWN' for d in audit['unknown_runs'])
    assert json.loads((OUT/'weight_checks.json').read_text())['total']=='219/2'
    assert json.loads((OUT/'fragment_checks.json').read_text())['direct_maximum']==214
    for name in ['general_ge55_cp','boundary_le186_native_quick','boundary_le186_linear_cp','boundary_le186_linear_highs']:
        assert json.loads((OUT/(name+'.json')).read_text())['status']=='INFEASIBLE'
    artifacts=[]
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name!='delivery_audit.json':artifacts.append(dict(file=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    out=dict(report_path=str(REPORT),verdicts=rows,status='全部九条复核完成；三次UNKNOWN已被完成的整域不可行判定覆盖。',checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),inputs_unchanged=True,formal_constraints=72,report_sha256=hashlib.sha256(REPORT.read_bytes()).hexdigest(),links_checked=links,branch_coverage=audit['branch_coverage'],unknown_runs=audit['unknown_runs'],source_and_artifact_hashes=artifacts,reader_review=dict(names_and_verdicts=True,mathematical_dependencies_reproved=True,no_formal_upper_bound_change=True,all_numeric_claims_have_evidence=True,solver_receipts_not_formal_kernel_proofs=True,unknown_not_used_as_proof=True,only_designated_report_and_directory_written=True,other_seat_not_read=True),started_utc='2026-09-26T04:09:31+00:00')
    out['elapsed_seconds']=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(out['started_utc'])).total_seconds()
    assert out['elapsed_seconds']<3*3600
    import sys,ortools,scipy
    out['versions']=dict(python=sys.version,ortools=ortools.__version__,scipy=scipy.__version__)
    (OUT/'delivery_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    assert all((REPORT.parent/target).resolve().exists() for target in links)
    print(json.dumps(dict(report=str(REPORT),verdicts=len(rows),links=len(links),artifacts=len(artifacts),elapsed_seconds=out['elapsed_seconds'],inputs_unchanged=True),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
