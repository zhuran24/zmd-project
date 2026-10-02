"""Final report references, input fingerprints, results, and artifact hashes."""
from pathlib import Path
import hashlib
import json
import re
from datetime import datetime, timezone

OUT=Path(__file__).resolve().parent
REPORT=OUT.parent/'复核96G.md'


def main():
    report=REPORT.read_text()
    verification=json.loads((OUT/'verification.json').read_text())
    assert verification['status']=='PASS'
    assert verification['witnesses_checked']==2*(verification['base_cases']+verification['near_compatible'])+2*verification['base_cases']
    a=json.loads((OUT/'arithmetic_supports.json').read_text())
    b=json.loads((OUT/'arithmetic_vectors.json').read_text())
    assert all(a[k]==v for k,v in b.items())
    assert a['flows']['power_weight']==520
    assert a['integer_area_constant']==4638
    assert a['corner_area_upper']==4604
    assert a['power_minimum_at_least_11']==172
    assert a['two_extra_minimum']=='355/2'
    manifest=json.loads((OUT/'input_manifest.json').read_text())
    for filename,checksum in manifest.items():
        assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==checksum,filename
    targets=re.findall(r'\[[^\]]+\]\(([^)]+)\)',report)
    delivery=OUT/'delivery_validation.json'
    for target in targets:
        p=(REPORT.parent/target.split('#')[0]).resolve()
        assert p==delivery or p.is_file(),target
    assert '候选一「内带缺口」：未否证' in report
    assert '候选二「面积预算」：未否证' in report
    assert 'Y₀ 数同一周圈' in report
    assert '必要性未闭合' in report
    assert '单独对运输单位计数' in report
    assert '本次两条候选的证明不以 U=1110 为前提' in report
    for bad in ('TODO','TBD','待写','占位符'):
        assert bad not in report
    artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(OUT.iterdir()) if p.is_file() and p!=delivery}
    final=dict(status='完成',report_path=str(REPORT),verdicts=[
        dict(name='内带缺口',verdict='未否证',reason='近边补偿和角格取整通过；减1是否必需未证。',revised_text=''),
        dict(name='面积预算',verdict='未否证',reason='原X、Y面积式及其余结论均复核通过。',revised_text='')])
    result=dict(status='PASS',finished_utc=datetime.now(timezone.utc).isoformat(),
                report_path=str(REPORT),report_sha256=hashlib.sha256(REPORT.read_bytes()).hexdigest(),
                report_lines=len(report.splitlines()),resolved_links=len(targets),
                input_fingerprints_unchanged=True,independent_arithmetic_agrees=True,
                reader_review=dict(self_contained=True,scope_and_status_consistent=True,
                                   no_unproved_claim_that_original_inequality_is_false=True,
                                   remaining_corner_case_explicit=True,
                                   no_factory_claim_from_relaxed_witness=True,
                                   local_power_certificates_not_claimed_rerun=True,
                                   numeric_and_reference_pass=True),
                maximum_concurrent_compute_processes=2,solver_workers=1,
                artifact_sha256=artifacts,final_response=final)
    delivery.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    assert delivery.is_file()
    print(json.dumps({k:v for k,v in result.items() if k!='artifact_sha256'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
