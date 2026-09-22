#!/usr/bin/env python3
from pathlib import Path
import ast, hashlib, json, re
E=Path(__file__).resolve().parent
B=E.parents[2]
report=B/'复核/否证-任务6.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
text=report.read_text()
data=read(E/'结构化结果.json')
assert len(data['findings'])==29
for f in data['findings']:
    assert text.count('### '+f['id']+' ')==1
    assert '### '+f['id']+' '+f['target'] in text
    assert '判定：**'+f['verdict']+'**。'+f['reason'] in text
assert [f['id'] for f in data['findings']]==['F'+str(i).zfill(2) for i in range(1,30)]
assert data['counts']=={'否证成立':0,'否证不成立':21,'无法判定':8}
for link in re.findall(r'\]\(([^)]+)\)',text):
    assert (report.parent/link).resolve().exists(),link
sealed=read(E/'审查输入指纹.json')['files']
for r in sealed:
    p=Path(r['path'])
    assert sha(p)==r['sha256'] and p.stat().st_mtime_ns==r['mtime_ns'],str(p)
author_inputs=read(B/'证据/相位认证/输入指纹.json')['files']
for r in author_inputs:
    p=Path(r['path'])
    assert sha(p)==r['sha256'] and p.stat().st_mtime_ns==r['mtime_ns'],str(p)
for p in E.rglob('*'):
    if not p.is_file():continue
    assert p.suffix in ['.md','.json','.log','.py'],str(p)
    if p.suffix=='.json':read(p)
    if p.suffix=='.py':ast.parse(p.read_text())
tool={'requested':'StructuredOutput','discovery':'ALL_TOOLS name/description regex StructuredOutput|structured.output',
      'available':False,'matches':[],'fallback':'结构化结果.json与最终JSON文本'}
(E/'工具可用性.json').write_text(json.dumps(tool,ensure_ascii=False,indent=2)+'\n')
files=[report]+sorted(p for p in E.rglob('*') if p.is_file() and p.name!='交付清单.json')
data['files']=list(map(str,files))
(E/'结构化结果.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
manifest={'schema':'task6-independent-review-delivery-v1','status':'done',
          'report_sha256':sha(report),'findings':data['counts'],
          'files':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in files],
          'self_hash':'omitted to avoid self-reference',
          'checks':{'report_json_findings_equal':29,'review_inputs_unchanged':len(sealed),
                    'author_inputs_unchanged':len(author_inputs),'links_exist':True,
                    'file_extensions_allowed':True,'reader_self_review':'读者自审.md'},
          'exit_status':0}
(E/'交付清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','findings':29,'verdicts':data['counts'],'review_inputs_unchanged':len(sealed),
                  'author_inputs_unchanged':len(author_inputs),'report_sha256':sha(report)},ensure_ascii=False))
