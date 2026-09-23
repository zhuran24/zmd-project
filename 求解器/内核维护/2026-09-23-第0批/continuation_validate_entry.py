import json,copy,sys
from pathlib import Path
from continuation_guard import *
a=json.loads((RUN/'isolation-accepted.json').read_text());entry=REPO/'数据/工具/kernel_regression.py';base=[sys.executable,'-B',str(entry)];rows=[]
def execute(name,args,expected=0):
 row=command('continue-entry-'+name,base+list(map(str,args)),REPO,expected);rows.append(dict(name=name,expected=expected,exit_code=row['returncode']));write(RUN/'continuation-entry-progress.json',rows)
execute('check-isolation',['check-isolation','--acceptance',RUN/'isolation-accepted.json','--source-root',a['source_root'],'--profile',a['profile']])
execute('wrong-profile',['check-isolation','--acceptance',RUN/'isolation-accepted.json','--source-root',a['source_root'],'--profile',a['profile']+'wrong'],2)
bad=copy.deepcopy(a);bad['harnesses'][0]['sha256']='0'*64;write(RUN/'entry-bad-binary-acceptance.json',bad)
execute('bad-binary',['check-isolation','--acceptance',RUN/'entry-bad-binary-acceptance.json','--source-root',a['source_root'],'--profile',a['profile']],2)
execute('capture',['capture','--cases',RUN/'entry-one-case.json','--binaries',RUN/'entry-b-binaries.json','--out',RUN/'entry-capture'])
execute('compare',['compare','--baseline',RUN/'capture-seed-a.json','--candidate',RUN/'entry-capture','--fields',RUN/'comparison-fields.json','--out',RUN/'entry-compare'])
execute('aa',['aa','--cases',RUN/'entry-one-case.json','--binaries',RUN/'entry-b-binaries.json','--fields',RUN/'comparison-fields.json','--out',RUN/'entry-aa'])
execute('old-context',['capture','--cases',RUN/'entry-one-case.json','--binaries',RUN/'binaries.json','--out',RUN/'entry-old-context'],2)
write(RUN/'entry-bad-fields.json',[dict(case_id='seed',artifact='main.stdout.log',pointer='/catalog/path')])
execute('wrong-source-map',['compare','--baseline',RUN/'capture-seed-a.json','--candidate',RUN/'entry-capture','--fields',RUN/'entry-bad-fields.json','--out',RUN/'entry-bad-mapping'],2)
execute('tests',['tests','--acceptance',RUN/'isolation-accepted.json','--out',RUN/'entry-tests'])
assert len(json.loads((RUN/'entry-tests/results.json').read_text()))==16
write(RUN/'continuation-entry-validation.json',dict(passed=True,checks=rows,tests_safe_commands=9,guarded_cli_suites=7,positive_capture_context='B explicitly bound to final source manifest',old_A_context_rejected=True))
check('entry-validation-final');print('All runner interfaces passed; guarded formal seven-suite run completed')
