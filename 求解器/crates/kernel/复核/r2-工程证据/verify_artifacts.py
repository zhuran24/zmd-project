#!/usr/bin/env python3
"""内核输出§1–§3：通读并复验记录、来源和覆盖报告篡改；仅在复核目录写证据。"""
import copy,hashlib,json,pathlib,re,sys
ROOT=pathlib.Path(__file__).resolve().parents[4]
OUT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'crates/kernel/tests'))
import verify_outputs as verifier

def digest(path):
    """内核输出§1：逐字节散列。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    """内核输出§1：正常记录先验收，再核独立单字段变异。"""
    reports=[]; mutations=[]
    for name in ['混做粉碎机两下游','分流器三路轮询']:
        data=verifier.checker.load_json(ROOT/f'数据/样例/{name}.json'); expected=verifier.run(data)
        for suffix in ['运行记录-kernel','运行记录-checkpoint_delta-kernel']:
            source=ROOT/f'数据/样例/{name}-{suffix}.json'
            reports.append(verifier.verify(source,data,expected)); record=verifier.checker.load_json(source)
            for case in ['coverage_fake_axis','coverage_fake_evidence','coverage_fake_transfer']:
                bad=copy.deepcopy(record)
                row=next(r for r in bad['uncovered_axes'] if r['axis']=='transfer.cooldown_scope')
                if case=='coverage_fake_axis': row['axis']='engineering.fabricated_axis'
                elif case=='coverage_fake_evidence':
                    row=next(r for r in bad['uncovered_axes'] if r['coverage_status']=='exercised' and r['axis']!='warehouse.acceptance'); row['evidence']=['not_registered_anywhere']
                else: row['coverage_status']='exercised'; row['evidence']=['J|999|0|999']
                path=OUT/f'{name}-{suffix}-{case}.json'; path.write_text(json.dumps(bad,ensure_ascii=False,indent=2)+'\n')
                try: verifier.verify(path,data,expected); accepted=True; error=None
                except Exception as e: accepted=False; error=str(e)
                mutations.append({'sample':name,'format':record['trace']['format'],'case':case,'accepted':accepted,'error':error,'path':str(path)})
    evidence=ROOT/'crates/kernel/evidence/revision-r1'
    manifest=json.loads((evidence/'deliverables.json').read_text())
    bad_files=[r['path'] for r in manifest['files'] if digest(pathlib.Path(r['path']))!=r['sha256']]
    old=json.loads((evidence/'baseline.json').read_text())
    changed=[p for p,h in old.items() if not pathlib.Path(p).is_file() or digest(pathlib.Path(p))!=h]
    original_logs={n:(evidence/n).read_text() for n in ['cargo-test.txt','clippy.txt','release-build.txt']}
    logs={n:(OUT/n).read_text() for n in ['cargo-test.txt','clippy.txt','release-build.txt']}
    funcs=[]; missing=[]; banned=[]
    for source in sorted((ROOT/'crates/kernel/src').glob('*.rs')):
        lines=source.read_text().splitlines()
        for i,line in enumerate(lines):
            if re.search(r'\bfn\s+\w+',line):
                funcs.append([str(source),i+1])
                if not any('///' in t and '§' in t for t in lines[max(0,i-8):i]): missing.append([str(source),i+1])
            if re.search(r'\b(?:f32|f64|HashMap|HashSet)\b|\bunsafe\s*\{',line): banned.append([str(source),i+1,line])
    tests=[(int(a),int(b)) for a,b in re.findall(r'test result: ok\. (\d+) passed; (\d+) failed',logs['cargo-test.txt'])]
    regression=json.loads((evidence/'regression-results.json').read_text())
    replay=json.loads((evidence/'review-probe-replay.json').read_text())
    result={'records':reports,'coverage_mutations':mutations,'r1_manifest_files':len(manifest['files']),'r1_manifest_mismatches':bad_files,'r1_baseline_files':len(old),'r1_baseline_changes':changed,'r1_test_counts':re.findall(r'test result: ok\. (\d+) passed; (\d+) failed',original_logs['cargo-test.txt']),'r1_regression_counts':{k:regression[k] for k in ['status','controls','metadata_negatives','cli_negatives']},'r1_probe_count':len(replay['cases']),'r2_tests_passed':sum(a for a,b in tests),'r2_tests_failed':sum(b for a,b in tests),'r2_cli_test_relocated':json.loads((OUT/'cli/regression-results.json').read_text())['status'],'rust_functions':len(funcs),'section_comments_missing':missing,'banned_constructs':banned,'r2_clippy':logs['clippy.txt'],'r2_build':logs['release-build.txt']}
    (OUT/'artifact-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['r1_baseline_changes','r2_clippy','r2_build']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
