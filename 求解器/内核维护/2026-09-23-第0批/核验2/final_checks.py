import ast,json,importlib.util,hashlib,re,os
from audit_files import *
R=ROOT/'求解器'
assert json.loads((OUT/'pipeline-passed.json').read_text())['passed']
# Compare exact canonical checker paths, without the implementation checker's basename mapping.
pos=json.loads((OUT/'own-closure-positive.json').read_text());caps=json.loads((OUT/'own-capture-index.json').read_text())
cap=next(x for x in caps if x['case_id']=='run-full' and x['label']=='a');record=json.loads((Path(cap['sealed'])/'artifacts/run-full.json').read_text());S=Path(json.loads((OUT/'own-freeze.json').read_text())['source_root'])
checker=[str(Path(x['path']).resolve()) for x in record['fingerprints'] if x['role']=='checker' and x['path'].endswith('.rs')];assert len(checker)==len(set(checker))==20
assert all(Path(p).is_relative_to(S/'crates/kernel/src') for p in checker)
for row in pos['artifacts']:
    if row['target']['name']=='kernel':
        expected=set(checker)-({str(S/'crates/kernel/src/main.rs')} if row['target']['kind']==['lib'] else set())
        assert {p for p in row['dependencies'] if p.endswith('.rs')}==expected
        assert all(sha(p)==h for p,h in row['dependencies'].items())
neg=json.loads((OUT/'own-closure-negative.json').read_text());assert neg['rejected'] and 'audit_unregistered.rs' in neg['reason'] and 'lib_missing' in neg['reason']
save('exact-checker-closure-audit.json',dict(passed=True,checker_count=len(checker),checker_paths=checker,negative_reason=neg['reason']))
# R3 output parity and exact early-rejection boundary from both independent runs.
ev=OUT/'内核维护/独立回归 中文/cargo-test-evidence';r3=[]
for f in sorted(ev.glob('revision_r3_cli-*/results.json')):
    d=json.loads(f.read_text());r3.append(dict(path=str(f),cases=[{k:r[k] for k in ['case','exit_code','status']} for r in d['cases']],expired=[{k:r.get(k) for k in ['case','exit_code','status','open_items']} for r in d['cases'] if 'expired-after-closure' in r['case'] or r['case']=='legacy-late-window-record']))
assert len(r3)==2 and all(len(x['cases'])==59 for x in r3) and r3[0]['cases']==r3[1]['cases']
assert all('源文件指纹不符' in str(case['open_items']) for x in r3 for case in x['expired'])
save('r3-runtime-boundary.json',dict(passed=True,cases_per_round=59,unchanged_case_exit_status=True,runs=r3,limitation='expired fixture is rejected for stale source fingerprint; does not demonstrate gate-state validation'))
# Generic guard behaviour on only new audit files. No removal operation is used.
spec=importlib.util.spec_from_file_location('tested_file_guard',R/'数据/工具/kernel_file_guard.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
root=OUT/'guard-probe';root.mkdir();(root/'empty').mkdir();(root/'file').write_text('old');(root/'link').symlink_to(root/'file');before=g.scan(root)
(root/'file').write_text('new');(root/'file').chmod(0o600);(root/'new-empty').mkdir();(root/'.ignored-file').write_text('bytes');after=g.scan(root);changes=g.changes(before,after)
assert {'file','new-empty','.ignored-file'}=={x['path'] for x in changes};assert after['entries']['empty']['kind']=='directory' and after['entries']['link']['kind']=='symlink'
(root/'file').rename(root/'moved');moved=g.scan(root);delta=g.changes(after,moved);assert {x['path'] for x in delta}=={'file','moved'}
save('file-guard-probes.json',dict(passed=True,modifications=changes,move=delta,empty_directory_and_symlink_preserved=True))
# Count every measured command; expected non-zero diagnostic results remain explicit.
commands=[json.loads(p.read_text()) for p in OUT.glob('*.command.json')];failed=[x for x in commands if x['returncode']!=x['expected'] or x['violation'] or x['average_cores']>6]
assert len(failed)==1 and failed[0]['label']=='suite-1-3-revision_cli'
save('resource-summary.json',dict(commands=len(commands),cpu_core_bound=4,max_average_cores=max(x['average_cores'] for x in commands),max_total_threads=max(x['max_total_threads'] for x in commands),max_runnable_threads=max(x['max_runnable_threads'] for x in commands),affinities=sorted({tuple(x['affinity']) for x in commands}),violations=[x['label'] for x in commands if x['violation'] or x['average_cores']>6],corrected_audit_setup_failures=[x['label'] for x in failed]))
print('Exact closure, R3 boundary, file guard and resource checks passed.')
