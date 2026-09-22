#!/usr/bin/env python3
"""Read-only tracked-file guard and historical test accounting; writes only beside this script."""
import hashlib, json, os, re, subprocess, sys
from pathlib import Path
OUT = Path(__file__).resolve().parent
SOLVER = OUT.parents[2]
REPO = SOLVER.parent
def dump(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
def snapshot():
    paths = subprocess.check_output(['git','ls-files','-z'], cwd=REPO).decode().split('\0')
    result = {}
    for name in filter(None, paths):
        p = REPO/name
        if p.is_symlink():
            result[name] = {'symlink':os.readlink(p)}
        elif p.is_file():
            result[name] = {'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(), 'size':p.stat().st_size}
        else:
            result[name] = {'missing':True}
    return {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(), 'files':result}
if sys.argv[1] == 'before':
    value = snapshot(); dump('protected-before.json',value)
    print(json.dumps({'head':value['head'],'tracked_files':len(value['files'])}))
elif sys.argv[1] == 'after':
    before=json.loads((OUT/'protected-before.json').read_text()); after=snapshot()
    changes=[p for p in before['files'].keys()|after['files'].keys() if before['files'].get(p)!=after['files'].get(p)]
    result={'head_unchanged':before['head']==after['head'], 'tracked_files':len(after['files']), 'changed_tracked_files':sorted(changes), 'git_status':subprocess.check_output(['git','-c','core.quotePath=false','status','--short'],cwd=REPO,text=True)}
    dump('protected-after.json',result); print(json.dumps(result,ensure_ascii=False,indent=2))
    assert not changes and result['head_unchanged']
elif sys.argv[1] == 'counts':
    reports={}
    for date in ['2026-09-22','2026-09-22b','2026-09-22c']:
        p=SOLVER/'内核维护'/date/'test.log'; text=p.read_text(); suites=[]; active=None
        for n,line in enumerate(text.splitlines(),1):
            if 'Running ' in line or 'Doc-tests ' in line: active=line.strip()
            match=re.match(r'test result: .*? (\d+) passed; (\d+) failed;',line)
            if match: suites.append({'line':n,'suite':active,'passed':int(match[1]),'failed':int(match[2])})
        summary=re.search(r'passed (\d+) failed (\d+)',text)
        reports[date]={'path':str(p),'suites':suites,'passed':sum(x['passed'] for x in suites) if suites else int(summary[1]),'failed':sum(x['failed'] for x in suites) if suites else int(summary[2])}
    text=(SOLVER/'内核维护/2026-09-22/test.log').read_text()
    reports['excluded_cli']=[{'line':n,'name':m[1]} for n,line in enumerate(text.splitlines(),1) if (m:=re.match(r'test ((?:revision|round).*?) \.\.\. ok',line))]
    dump('test-counts.json',reports); print(json.dumps(reports,ensure_ascii=False,indent=2))
