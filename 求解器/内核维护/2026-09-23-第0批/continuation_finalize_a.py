"""Reconstitute sealed captures at their original paths and persist full closure.

No file is deleted. All validators execute before the A source context changes.
"""
import json,shutil,sys
from pathlib import Path
from continuation_guard import *
from continuation_aa import references,strict_loads,compare_capture
from continuation_runtime import verify as verify_runtime,audit_trace

def main():
    assert json.loads((RUN/'continuation-aa-passed.json').read_text())['cases']==44
    f=json.loads((RUN/'continuation-freeze.json').read_text());F=Path(f['root']);S=Path(f['source_root']);bins=json.loads((RUN/'binaries.json').read_text());k=bins['kernel']['path'];cases=json.loads((RUN/'cases.json').read_text());receipts=json.loads((RUN/'continuation-a-validation-receipts.json').read_text()) if (RUN/'continuation-a-validation-receipts.json').exists() else []
    for x in f['files']:assert sha(F/x['path'])==x['sha256']
    for label in ['a','b']:
        check('restore-captures-'+label+'-before');captures=[];docs=[];roots=[];closure=[]
        for case in cases:
            cap=json.loads((RUN/('capture-'+case['id']+'-'+label+'.json')).read_text());root=Path(cap['root']);
            if not root.exists():shutil.copytree(cap['sealed'],root)
            assert {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}==set(cap['files'])
            roots.append(root);captures.append(cap)
            cache={}
            for rel,row in cap['files'].items():
                p=root/rel;assert sha(p)==row['sha256']
                if rel!='.exclusive.json':references(p,[F,root],cache)
                raw=p.read_bytes()
                if not raw.lstrip().startswith(b'{'):continue
                obj=strict_loads(raw)
                if obj.get('schema') in ['kernel-output-v4','kernel-cycle-v3']:
                    if obj['schema']=='kernel-output-v4':
                        producer=Path(obj['producer']['path']).resolve();assert producer.is_relative_to(S/'crates/kernel/src') and producer.is_file()
                    docs.append((case['id'],p,obj))
            closure.append(dict(case_id=case['id'],label=label,root=str(root),sealed=cap['sealed'],edges={str(p):v for p,v in cache.items()}))
        write(RUN/('continuation-reference-closure-'+label+'.json'),closure);check('restore-captures-'+label+'-after')
        schema_code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from verify_all import schema_check;schema_check([Path(x) for x in sys.argv[2:]])"
        def validate(tag,argv,expected=0):
            verify_runtime();trace=RUN/(tag+'.trace.log');row=command(tag,['strace','-f','-qq','-yy','-s','4096','-e','trace=openat,openat2,execve,chdir','-o',str(trace),*argv],S,expected,{'KERNEL_BIN':k})
            reads=audit_trace(trace,F,roots,executables=[x['path'] for x in bins.values()]);write(RUN/(tag+'.reads.json'),reads);verify_runtime();return row
        if not (RUN/('continue-schema-all-'+label+'.reads.json')).exists():validate('continue-schema-all-'+label,[sys.executable,'-B','-c',schema_code,str(S/'crates/kernel/tests'),*[str(p) for _,p,_ in docs]])
        covered=set()
        for _,p,obj in docs:
            if obj['schema']=='kernel-cycle-v3' and obj.get('run_record_ref'):covered.add((p.parent/obj['run_record_ref']['path']).resolve())
        for i,(cid,p,obj) in enumerate(docs):
            prior=[x for x in receipts if x['label']==label and x['path']==str(p)]
            if prior:
                assert len(prior)==1 and prior[0]['sha256']==sha(p)
                continue
            if p.resolve() in covered:
                receipts.append(dict(case_id=cid,label=label,path=str(p),sha256=sha(p),verification='covered by this capture cycle certificate'));continue
            mode='verify-cycle' if obj['schema']=='kernel-cycle-v3' else 'verify-record'
            # Standalone noncompleted records are explicitly rejected by verify-record.
            expected=2 if (mode=='verify-record' and obj['status']!='completed') else 0
            row=validate(f'continue-artifact-verify-{label}-{i}',[k,mode,str(p),'--config',str(S/'规格/内核配置-v1.json')],expected)
            receipts.append(dict(case_id=cid,label=label,path=str(p),sha256=sha(p),mode=mode,expected=expected,exit_code=row['returncode']))
            write(RUN/'continuation-a-validation-receipts.json',receipts)
        check('seal-validated-'+label+'-before')
        for cap,root in zip(captures,roots):
            for rel,row in cap['files'].items():assert sha(root/rel)==row['sha256']
            dest=root.parent.parent/'validated'/label/cap['case_id'];dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists();root.rename(dest)
        check('seal-validated-'+label+'-after')
    for x in f['files']:assert sha(F/x['path'])==x['sha256']
    fields=json.loads((RUN/'comparison-fields.json').read_text());results=json.loads((RUN/'continuation-aa-results.json').read_text())
    for row in fields:
        found=next(x for x in results if x['case_id']==row['case_id']);mapping=next(x for x in found['mappings'] if x['artifact']==row['artifact'])
        row.update(a=mapping['a'],b=mapping['b'],a_token=mapping['a_token'],b_token=mapping['b_token'],validator='continuation_aa.compare_bytes; raw JSON Pointer token replacement only')
    write(RUN/'comparison-fields.json',fields)
    write(RUN/'continuation-a-final.json',dict(passed=True,aa_pairs=44,closures=['continuation-reference-closure-a.json','continuation-reference-closure-b.json'],validation_receipts=len(receipts),source_manifest_sha256=sha(RUN/'continuation-freeze.json'),runtime_manifest_sha256=sha(RUN/'continuation-runtime-dependencies.json'),binary_manifest_sha256=sha(RUN/'binaries.json'),cases_sha256=sha(RUN/'cases.json'),fields_sha256=sha(RUN/'comparison-fields.json')))
    check('a-final-complete');print('A binding, original-reference closure and validation receipts complete')

if __name__=='__main__':main()
