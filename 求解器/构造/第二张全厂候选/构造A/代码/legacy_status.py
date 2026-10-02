#!/usr/bin/env python3
"""记录旧检查器未运行的实际原因，不制造缺失布局的伪检查。"""
import ast
import hashlib
import json
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
ROOT=BASE.parents[3]


def main():
    out=[]
    for seat,entry in [('A','check_full.py'),('B','check.py')]:
        source=ROOT/f'求解器/构造/第一张全厂候选/检查器{seat}'
        code=(source/'catalog.py').read_text()
        supported=None
        for node in ast.parse(code).body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HASHES' for t in node.targets):
                supported=ast.literal_eval(node.value)
        snapshot_hashes={k:hashlib.sha256((BASE/'依据快照'/f).read_bytes()).hexdigest() for k,f in [('rules','规则.txt'),('task','任务.txt'),('constraints','约束.txt')]}
        r=dict(checker=seat,status='NOT_RUN_NO_LAYOUT',static_pass=False,
               original_path=str(source/entry),
               original_entry_sha256=hashlib.sha256((source/entry).read_bytes()).hexdigest(),
               original_catalog_sha256=hashlib.sha256((source/'catalog.py').read_bytes()).hexdigest(),
               original_supported_fingerprints=supported,snapshot_fingerprints=snapshot_hashes,
               fingerprints_match=supported==snapshot_hashes,
               adapter_created=False,original_modified=False,
               reason='没有完整坐标候选可交给固定布局检查器。拓扑必要条件已经排除S2接法；未将逻辑图伪装成full-factory-static-v1布局。',
               scope='不是旧检查器A/B的通过或拒绝结果；未调用其候选检查入口。')
        p=BASE/f'检查器{seat}/复查状态.json';p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
        out.append(r)
    (BASE/'证据/旧检查器复查.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([dict(checker=r['checker'],status=r['status'],fingerprints_match=r['fingerprints_match']) for r in out],ensure_ascii=False))


if __name__=='__main__':main()
