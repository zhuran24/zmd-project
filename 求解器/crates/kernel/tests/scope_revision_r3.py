#!/usr/bin/env python3
"""第3轮历史生成器（仅配合该轮冻结结果；当前入口为finalize_revision_r4.py）。第3轮范围及交付检查：基线逐字节核验、证据类型、读者链接与完整变更清单。"""
import hashlib
import json
import os
from pathlib import Path
import re
from cleanup_revision_r3 import scan

ROOT = Path(__file__).resolve().parents[4]
SOLVER = ROOT / '求解器'
KERNEL = SOLVER / 'crates/kernel'
OUT = KERNEL / 'evidence/revision-r3'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def authorized(path):
    return (path.is_relative_to(KERNEL) or path.is_relative_to(SOLVER / '数据/样例')
            or path == SOLVER / '规格/内核实现-对规格的疑问.md')


def main():
    before = {r['path']: r for r in json.loads((OUT / 'baseline.json').read_text())['files']}
    current = {}
    for base in [SOLVER, ROOT]:
        if base == ROOT:
            paths = [p for p in base.iterdir() if p.is_file()]
        else:
            paths = []
            for here, dirs, files in os.walk(base, followlinks=False):
                dirs[:] = [d for d in dirs if d not in ('target', '.cargo-home', '.git', '__pycache__')]
                paths.extend(Path(here) / f for f in files)
        for path in paths:
            if path.is_symlink() or not path.is_file():
                continue
            relative = str(path.relative_to(ROOT))
            current[relative] = dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))
    protected = []
    changes = []
    violations = []
    nonrecursive = {OUT / name for name in ('交付清单.json','scope.log','最终回复.json')}
    for relative in sorted(before.keys() | current.keys()):
        old, new = before.get(relative), current.get(relative)
        path = ROOT / relative
        if path in nonrecursive:
            continue
        if not authorized(path):
            if old is None or new is None or old['sha256'] != new['sha256']:
                violations.append(relative)
            elif path.is_file():
                protected.append(new)
        elif old is None or new is None or old['sha256'] != new['sha256']:
            changes.append(dict(path=str(path), action='added' if old is None else 'deleted' if new is None else 'modified',
                                before=old, after=new))
    assert not violations, violations
    evidence = scan()
    assert not any(evidence.values()), evidence
    unexpected = []
    for base in [KERNEL / 'evidence', KERNEL / '复核']:
        for path in base.rglob('*'):
            if path.is_file() and path.suffix not in ('.py','.rs','.sh','.log','.txt','.json','.md'):
                unexpected.append(str(path))
    assert not unexpected, unexpected
    docs = [KERNEL / 'README.md', KERNEL / '修订记录.md',OUT / '修订与验证.md',
            KERNEL / 'evidence/round5/实施与验证.md',KERNEL / '复核/证据维护说明.md',
            KERNEL / 'tests/legacy_probes/README.md',SOLVER / '数据/样例/第五轮样例说明-kernel.md',
            SOLVER / '规格/内核实现-对规格的疑问.md']
    pending = {OUT / '范围审计.json',OUT / '交付清单.json'}
    broken=[]
    for doc in docs:
        text=doc.read_text()
        assert re.search(r'20\d{2}-\d{2}-\d{2}',text[:512]),doc
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
            if target.startswith(('http:','https:','#')):
                continue
            path=(doc.parent / target.split('#')[0]).resolve()
            if not path.exists() and path not in pending:
                broken.append(dict(document=str(doc),target=target))
    assert not broken, broken
    result=json.loads((OUT / '交付结果.json').read_text())
    assert len(result['findings'])==len({r['id'] for r in result['findings']})==10
    assert result['cli_schema_open']==1 and any('KQ-09' in x for x in result['open_items'])
    unchanged_tests = ['crates/kernel/tests/reference.rs','数据/样例/混做粉碎机两下游-黄金轨迹.json',
                       '数据/样例/混做粉碎机两下游-黄金轨迹.md']
    for name in unchanged_tests:
        path=SOLVER / name
        assert sha(path)==before[str(path.relative_to(ROOT))]['sha256'],name
    scope=dict(status='pass',protected_files=len(protected),protected_changes=violations,
               protected_fingerprints=protected,build_target=str(SOLVER / 'target'),
               evidence_scan=evidence,unexpected_evidence_files=unexpected,
               evidence_types='源码脚本、文本日志（含历史.txt）、JSON、Markdown',
               reference_and_golden_unchanged=unchanged_tests,
               scope='基线包含仓库根文件及求解器普通文件；共享target/.cargo-home为编译缓存，不纳入内容保护。未对模拟器作运行或改写。',
               document_reader_review=dict(status='pass',documents=list(map(str,docs)),broken_links=broken,
                   checks=['现状与历史区分','发现10个ID逐项有据','KQ-09单列为schema未通过','59调用与121测试分开计数',
                           '条件周期与全称认证分开','性能三档各有范围','两个K6缺口有原因','链接存在']),
               unmodified_formal_files=[str(ROOT / name) for name in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']])
    write('范围审计.json',scope)
    for name in ('范围审计.json','交付结果.json','修订与验证.md'):
        path=OUT / name
        row=dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))
        changes=[c for c in changes if c['path']!=str(path)]
        changes.append(dict(path=str(path),action='added',before=None,after=row))
    changes.sort(key=lambda r:r['path'])
    write('交付清单.json',dict(schema='kernel-revision-r3-files-v1',changes=changes,
        nonrecursive_files=sorted(map(str,nonrecursive)),
        cleanup_manifest=str(OUT / 'cleanup.json'),counts={action:sum(c['action']==action for c in changes) for action in ['added','modified','deleted']}))
    print(json.dumps(dict(status='pass',protected=len(protected),changes=len(changes),
                          counts={action:sum(c['action']==action for c in changes) for action in ['added','modified','deleted']}),ensure_ascii=False))


if __name__ == '__main__':
    main()
