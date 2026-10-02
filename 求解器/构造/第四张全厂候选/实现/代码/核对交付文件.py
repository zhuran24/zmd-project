#!/usr/bin/env python3
"""核对交付入口、同一布局指纹和报告中的终态数字。"""
import os
os.sched_setaffinity(0, {6})
import ast
import datetime
import hashlib
import json
import re
from pathlib import Path

B = Path(__file__).resolve().parents[1]
report = B.parent / '实现.md'
layout = B / '布局.json'
read = lambda p: json.loads(p.read_text())
sha = hashlib.sha256(layout.read_bytes()).hexdigest()
s = read(B / '证据/静态检查结果.json')
r = read(B / '证据/逐路与端口核查.json')
summary = read(B / '证据/复核汇总.json')
assert all(d['candidate_sha256'] == sha for d in (s, r, summary))
assert summary['numeric_agreement']
assert r['expected_routes'] == 325 and r['built_routes'] == s['statistics']['routes']
body = report.read_text()
assert sha in body
assert f"{r['built_routes']}/325" in body
assert '搜索中' not in body
checks = []
for document in [report, B / '格式扩展.md']:
    for text, target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', document.read_text()):
        if re.match(r'^[a-z]+://', target):
            continue
        path = (document.parent / target.split('#')[0]).resolve()
        checks.append(dict(document=str(document.relative_to(B.parent)), label=text,
                           target=target, exists=path.exists()))
assert all(c['exists'] for c in checks)
code_files = sorted((B / '代码').glob('*.py'))
for p in code_files:
    ast.parse(p.read_text(), filename=str(p))
result = dict(time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              candidate_sha256=sha, report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
              static_pass=s['static_pass'], built_routes=r['built_routes'], missing_routes=r['missing_routes'],
              links=checks, python_files_parsed=len(code_files), all_checks_pass=True,
              scope='这些检查只验证交付文件一致性，不能把缺路候选改判为全厂通过。')
(B / '证据/交付文件一致性.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({k: v for k, v in result.items() if k != 'links'}, ensure_ascii=False))
