import ast,json,hashlib
from pathlib import Path
from audit_files import ROOT,OUT,IMPL,save,sha
names=['revision_cli','revision_r2_cli','revision_r3_cli','revision_r4_cli','revision_r5_cli','round5_cli','round6_cli']
paths={name:IMPL/name for name in ['isolation-accepted.json','test-harnesses.json','cases.json','binaries.json','comparison-fields.json']}
paths['kernel_regression.py']=ROOT/'求解器/数据/工具/kernel_regression.py'
missing=[{'name':n,'path':str(p),'exists':p.is_file()} for n,p in paths.items()]
meta=json.loads((OUT/'metadata-fixed.stdout.log').read_text());targets=[{'package':p['name'],'name':t['name'],'kind':t['kind'],'src_path':t['src_path'],'test':t['test']} for p in meta['packages'] for t in p['targets']]
threads=[]
for n in ['production-a-build.command.json','production-a-serial-build.command.json','production-a-observed-build.command.json']:
 d=json.loads((IMPL/n).read_text());peak=d.get('peak',[]);threads.append({'file':n,'reported':d['max_threads'],'recomputed_sum_of_saved_peak':sum(p['threads'] for p in peak),'exit_code':d['returncode'],'this_is_saved_evidence_not_new_measurement':True})
# Check exact structural move of round6 body, apart from the new allocator/global.
from read_objects import commit,obj
base=commit('aec2a30d945e21a492d4b05639d67a63abacb5b3')[2];p='求解器/crates/kernel/tests/round6_cli.py'
a=ast.parse(obj(base[p]['oid'])[1]);b=ast.parse((ROOT/p).read_text())
start=next(i for i,n in enumerate(a.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='cases' for t in n.targets))
main=next(n for n in b.body if isinstance(n,ast.FunctionDef) and n.name=='main')
same=ast.dump(ast.Module(body=a.body[start:],type_ignores=[]),include_attributes=False)==ast.dump(ast.Module(body=main.body[2:],type_ignores=[]),include_attributes=False)
fixtures=[]
p=ROOT/'求解器/crates/kernel/tests/revision_r3_cli.py';tree=ast.parse(p.read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
for n in main.body:
 if isinstance(n,ast.Assert) and 'required historical fixture mismatch' in ast.unparse(n):fixtures.append({'line':n.lineno,'assertion':ast.unparse(n)})
res={'required_artifacts':missing,'metadata_targets':targets,'declared_cli_names':names,'saved_thread_records_recalculated':threads,'round6_moved_body_ast_equal':same,'r3_required_checks':fixtures,'criteria':[{'id':'recovery','status':'FAIL','reason':'160+3 hashes match, seven originals removed and both versions locate; 13 lost originals lack six required directory markers'},{'id':'scope','status':'PASS','reason':'18 changed files plus one directory, all test/output infrastructure; production and runtime verifier bytes unchanged'},{'id':'protection','status':'PENDING_FINAL_SCAN','reason':'initial independent scan matches protected history'},{'id':'isolation','status':'FAIL','reason':'bounded helper probes pass; no accepted harness/source credential'},{'id':'two_safe_rounds','status':'FAIL','reason':'safe build rejected for actual thread budget; zero complete rounds'},{'id':'compilation_closure','status':'FAIL','reason':'no exact artifact dep-info comparison or new-module rejection'},{'id':'production_binary_equality','status':'FAIL','reason':'no same-path same-profile A/B binary pair'},{'id':'aa_reference_closure','status':'FAIL','reason':'runner/cases/field rules/reference closure acceptance missing'}]}
save('gates.json',res)
print(json.dumps({'required_artifacts_absent':sum(not r['exists'] for r in missing),'metadata_targets':len(targets),'round6_ast_equal':same,'thread_logs':threads},ensure_ascii=False))
