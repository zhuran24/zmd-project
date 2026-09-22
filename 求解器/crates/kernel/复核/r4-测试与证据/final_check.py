#!/usr/bin/env python3
"""只读核对被审来源与本席交付物，并保存读者自审结果。"""
import ast
import hashlib
import json
import re
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
REPORT=OUT.parent/'复核-r4-测试与证据.md'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
baseline=read(OUT/'开工指纹.json')
changes=[p for p,r in baseline.items()if not Path(p).exists() or sha(Path(p))!=r['sha256']]
assert not changes,changes
inventory=read(OUT/'被审文件清单.json')
assert all(sha(Path(r['path']))==r['sha256']for r in inventory)
assert len(inventory)==74
summary=read(OUT/'结果.json')
assert len(summary['findings'])==2
assert [f['id']for f in summary['findings']]==['KR-r4-L2-1','KR-r4-L2-2']
assert all(f['severity'] in ['阻断','重要','次要']for f in summary['findings'])
log=(OUT/'cargo-test.log').read_text()
assert sum(map(int,re.findall(r'test result: ok\. (\d+) passed',log)))==120
assert 'FAILED' not in log
assert read(OUT/'redirected-rust-cli.json')['status']=='pass'
assert read(OUT/'manual-period-check.json')['differences']==[]
assert read(OUT/'d2-capacity-before-stop.json')['status']=='pass'
assert read(OUT/'supply-differential.json')['counts']['sufficient']['ore_out']==30
assert read(OUT/'independent-schema.json')['passed']==57 and read(OUT/'independent-schema.json')['failed']==1
assert len(read(OUT/'audit-results.json')['records'])==26
assert len(read(OUT/'audit-results.json')['cycles'])==10
assert len(read(OUT/'coverage-event-excerpts.json'))==31
assert all(r['all_within_target'] for r in read(OUT/'benchmark.json')['cases'][:2])
forbidden=[]
artifacts=[]
for p in sorted(OUT.rglob('*')):
    if p.is_symlink() or (p.is_dir()and p.name in ['target','.cargo-home','registry','snapshot','__pycache__']):forbidden.append(str(p))
    if p.is_file():
        if p.suffix not in ['.py','.sh','.log','.json','.md']:forbidden.append(str(p))
        with p.open('rb') as f:header=f.read(8)
        assert not header.startswith((b'\x7fELF',b'!<arch>\n'))
        if p.suffix=='.py':ast.parse(p.read_text())
        if p.suffix=='.json':read(p)
        if p.name!='交付自审.json':artifacts.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size))
assert not forbidden,forbidden
text=REPORT.read_text()
links=[]
for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
    p=(REPORT.parent/target.split('#')[0]).resolve()
    assert p.exists() or p==OUT/'交付自审.json',p
    links.append(str(p))
# GFM表中事件身份的竖线必须转义，避免断列。
for line in text.splitlines():
    if line.startswith('| `') and 'J' in line:
        assert len(re.split(r'(?<!\\)\|',line))==5,line
result=dict(status='pass',report=str(REPORT),report_sha256=sha(REPORT),protected_files=len(baseline),protected_changes=changes,
    reviewed_files=len(inventory),all_reviewed_bytes_unchanged=True,forbidden_files=forbidden,
    native_tests_passed=120,redirected_rust_cli_equivalent='4次调用和全部断言通过；原生单项因写权过滤',
    schema_passed=57,schema_failed=1,findings=2,links_checked=len(links),artifacts=artifacts,
    reader_review=dict(status='pass',checks=['状态与正文一致','发现区分新误报与既有未决','测试原生数和等价重跑分开',
        '性能保存全部三次和范围','31轴均有判读','20刻手推覆盖全周期并核前缀入库不重计',
        '局部证据未升级全称结论','交叉引用存在','表内事件竖线转义','代码语法和JSON可解析'],
        corrections=['覆盖表内事件ID竖线转义，避免Markdown断列','原行摘要表述改为所报状态与首条原始事件']))
(OUT/'交付自审.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items()if k not in ['artifacts','reader_review']},ensure_ascii=False))
