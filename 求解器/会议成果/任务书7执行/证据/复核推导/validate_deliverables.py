#!/usr/bin/env python3
"""检查交付完整性及指纹；不验证全游戏运行语义。"""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
index = json.loads((HERE/'裁定索引.json').read_text())
records = json.loads((HERE/'输入指纹.json').read_text())['files']
records += json.loads((HERE/'补充来源指纹.json').read_text())
input_checks = []
errors = []
for record in records:
    p = Path(record['path'])
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    same = actual == record['sha256']
    input_checks.append({'path':str(p),'sha256':actual,'unchanged':same})
    if not same:
        errors.append('input changed: '+str(p))

expected = {'L-E01','L-E02',*(f'L-U{i}' for i in range(1,8)),
            'P-E01','P-U05','G-U01','G-U02'}
actual_ids = {f['id'] for f in index['findings']}
if actual_ids != expected or len(actual_ids) != len(index['findings']):
    errors.append('finding index mismatch')
doc_texts = {path:Path(path).read_text() for path in index['files']}
for finding in index['findings']:
    for occurrence in finding['locations']:
        body = doc_texts[occurrence['file']]
        if finding['id'] not in body:
            errors.append('missing occurrence: '+finding['id']+' '+occurrence['file'])
        if finding['verdict'] not in body:
            errors.append('missing verdict: '+finding['id'])
negative_rows = []
for path,body in doc_texts.items():
    for lineno,line in enumerate(body.splitlines(),1):
        if line.startswith('|') and ('否证成立' in line or '无法判定' in line):
            ids = set(re.findall(r'\b(?:L-E\d+|L-U\d+|P-E\d+|P-U\d+|G-U\d+)\b',line))
            if ids:
                negative_rows.append({'file':path,'line':lineno,'ids':sorted(ids)})
                if not ids <= actual_ids:
                    errors.append('unindexed negative row: '+path+':'+str(lineno))

# 链接中包含本输出文件；检查之前先创建占位，最终立即写入完整结果。
report_path = HERE/'交付校验.json'
report_path.write_text('{}\n')
link_count = 0
for path,body in doc_texts.items():
    for match in re.finditer(r'\]\(([^)]+)\)',body):
        dest = match.group(1)
        if '://' not in dest and not dest.startswith('#'):
            link_count += 1
            target = (Path(path).parent/dest.split('#')[0]).resolve()
            if not target.exists():
                errors.append('missing link: '+path+' -> '+dest)

files = sorted(p for p in HERE.iterdir() if p.is_file())
for p in files:
    if p.suffix not in {'.py','.json','.log','.md'}:
        errors.append('unexpected evidence type: '+str(p))
artifact_hashes = [{'path':p,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest(),
                   'lines':len(doc_texts[p].splitlines())} for p in index['files']]
result = {
    'status':'pass' if not errors else 'fail',
    'input_checks':input_checks,
    'deliverables':artifact_hashes,
    'findings':{'unique':len(actual_ids),
        'refuted':sum(x['verdict']=='否证成立' for x in index['findings']),
        'unresolved':sum(x['verdict']=='无法判定' for x in index['findings'])},
    'indexed_negative_rows':negative_rows,
    'local_links_checked':link_count,
    'allowed_evidence_extensions':['.py','.json','.log','.md'],
    'errors':errors,
}
report_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':result['status'],'inputs':len(input_checks),
    'deliverables':len(artifact_hashes),'findings':result['findings'],
    'local_links_checked':link_count,'errors':errors},ensure_ascii=False,indent=2))
raise SystemExit(1 if errors else 0)
