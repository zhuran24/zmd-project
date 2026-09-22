"""Syntax/link QA only; never executes documented maintenance commands."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

OUT = Path(__file__).parent
PLAN = OUT.parents[1] / '代码体检方案.md'
REPORT = OUT.parent / '审查处理.md'
result = dict(bash=[],python=[],links=[],files={})
result_path = OUT/'document-check.json'
result_path.write_text('{}\n')
for path in [PLAN,REPORT]:
    text = path.read_text()
    result['files'][str(path)] = dict(lines=len(text.splitlines()),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    for i,block in enumerate(re.findall(r'```bash\n(.*?)\n```',text,re.S),1):
        proc = subprocess.run(['bash','-n'],input=block,text=True,capture_output=True)
        result['bash'].append(dict(file=str(path),block=i,returncode=proc.returncode,stderr=proc.stderr))
        for j,code in enumerate(re.findall(r"<<'PY'\n(.*?)\nPY",block,re.S),1):
            try: ast.parse(code); error=None
            except SyntaxError as exc: error=str(exc)
            result['python'].append(dict(file=str(path),block=i,heredoc=j,error=error))
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
        if '://' in target or target.startswith('#'): continue
        p = path.parent / target.split('#')[0]
        result['links'].append(dict(file=str(path),target=target,exists=p.exists()))
    assert text.count('```') % 2 == 0, path
ids=['H1','H2','H3','H4',*[f'M{i}' for i in range(1,9)],'L1/L2','L3','L4','L5','L6','L7/L8','L9']
result['review_groups']={x:bool(re.search(r'^### '+re.escape(x)+'：',REPORT.read_text(),re.M)) for x in ids}
result['pass']=all(x['returncode']==0 for x in result['bash']) and all(x['error'] is None for x in result['python']) and all(x['exists'] for x in result['links']) and all(result['review_groups'].values())
result['reader_review'] = dict(status='completed', checks=['standalone audience','final-state prose','status labels','no editing-process notes in plan','count scopes','meaningful names','cross-references'], runtime_validation='not executed')
result_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(pass_=result['pass'],bash_blocks=len(result['bash']),python_heredocs=len(result['python']),links=len(result['links']),groups=len(result['review_groups']),bad_links=[r for r in result['links'] if not r['exists']]),ensure_ascii=False,indent=2))
raise SystemExit(0 if result['pass'] else 1)
