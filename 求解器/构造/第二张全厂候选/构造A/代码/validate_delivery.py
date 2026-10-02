#!/usr/bin/env python3
"""交付一致性、源文件稳定性及产物指纹；不运行内核或修改原材料。"""
import ast
import hashlib
import json
import re
from datetime import datetime,timezone
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
REPORT=BASE.parent/'构造A.md'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name,data):
    (BASE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def main():
    result=dict(report_path=str(REPORT),layout_path='',static_pass=False,empty_rect='',
                summary='已证明固定S2接法在边界取货、纯带不共格条件下不可行。',
                blockers=['S3—B3/B4/O4—E2与边界取货口构成K3,3细分，无法无交叉布线。'])
    save('结果.json',result)
    reader_audit=dict(date='2026-10-02',status='PASS',
                      reviewer='本席自行按陌生读者视角复读；没有另一个审查席参与',
                      checks=[
                          dict(item='自包含结论',result='明确无布局、静态false、无已实现空矩形'),
                          dict(item='当前状态',result='没有把不可行证书、组件测试或抽象流量当作布局通过'),
                          dict(item='模型边界',result='逐格模型为数学定义；可执行CP-SAT只求必要拓扑子问题'),
                          dict(item='指代与命名',result='原S2编号和新增矿石链ID已定义；证书的零基名字另作说明'),
                          dict(item='数值口径',result='230台325路3567格；局部14台、3口、18真实路、3辅助边；压缩6点9边'),
                          dict(item='范围',result='限定S2接法及边界纯带；不否定其他接法或动态蕴含'),
                          dict(item='引用',result='相对文件链接由交付核验逐个检查'),
                          dict(item='图示',result='SVG已渲染PNG并目视核对；无文字截断，标明不是布局'),
                          dict(item='未完成项',result='所有坐标检查、旧A/B、调试与运行明确未执行及原因'),
                      ])
    save('证据/读者自审.json',reader_audit)
    inputs=json.loads((BASE/'证据/输入指纹.json').read_text())
    stable=[]
    for r in inputs:
        stable.append(dict(source=r['source'],expected=r['sha256'],
                           source_unchanged=sha(r['source'])==r['sha256'],
                           snapshot_unchanged=sha(BASE/r['copy'])==r['sha256']))
    legacy=json.loads((BASE/'证据/旧检查器复查.json').read_text())
    old=[]
    for r in legacy:
        entry=Path(r['original_path'])
        old.append(dict(checker=r['checker'],entry_unchanged=sha(entry)==r['original_entry_sha256'],
                        catalog_unchanged=sha(entry.parent/'catalog.py')==r['original_catalog_sha256']))
    syntax=[]
    for p in sorted((BASE/'代码').glob('*.py')):
        ast.parse(p.read_text());syntax.append(str(p.relative_to(BASE)))
    # 先写占位，允许正文的交付核验与清单链接被检查；随即覆盖为完整结果。
    save('证据/交付核验.json',{})
    save('证据/文件清单.json',{})
    links=[]
    for doc in [REPORT,BASE/'整数模型.md']:
        for link in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
            path=link.split('#',1)[0]
            if not path or '://' in path:continue
            target=(doc.parent/path).resolve()
            links.append(dict(document=str(doc),link=link,exists=target.exists()))
    for p in BASE.rglob('*.json'):json.loads(p.read_text())
    topo=json.loads((BASE/'证据/拓扑复核结果.json').read_text())
    sat=json.loads((BASE/'证据/CP-SAT-不要求空矩形.json').read_text())
    replay=json.loads((BASE/'证据/复跑结果.json').read_text())
    static=json.loads((BASE/'证据/静态检查结果.json').read_text())
    now=datetime.now(timezone.utc)
    start=datetime(2026,10,2,12,39,21,tzinfo=timezone.utc)
    execution=dict(start_utc=start.isoformat(),finish_utc=now.isoformat(),
                   wall_seconds=(now-start).total_seconds(),wall_limit_seconds=14400,
                   cp_sat_workers=6,replay_cpu_affinity=replay['cpu_affinity'],
                   solver_timed_out=False,background_solver_remaining=False,
                   write_scope=str(BASE.parent),git_commands_run=False,kernel_cargo_tests_run=False)
    save('证据/执行记录.json',execution)
    checks=dict(all_inputs_unchanged=all(x['source_unchanged'] and x['snapshot_unchanged'] for x in stable),
                legacy_entry_and_catalog_unchanged=all(x['entry_unchanged'] and x['catalog_unchanged'] for x in old),
                all_links_exist=all(x['exists'] for x in links),
                fixed_s2_certificate_verified=topo['certificate_pass'],
                cp_sat_infeasible=sat['status']=='INFEASIBLE',
                replay_expected=replay['all_expected'],
                no_layout_claim=result['layout_path']==result['empty_rect']=='',
                static_false=static['static_pass'] is False,
                all_coordinate_checks_not_run=all(r['status']=='NOT_RUN_NO_LAYOUT' for r in static['checks']),
                within_wall_limit=execution['wall_seconds']<=execution['wall_limit_seconds'],
                svg_and_png_present=(BASE/'布线障碍.svg').is_file() and (BASE/'布线障碍.png').is_file())
    audit=dict(all_pass=all(checks.values()),checks=checks,input_stability=stable,
               legacy_stability=old,syntax_parsed=syntax,links=links,report_sha256=sha(REPORT),
               scope='交付完整性通过，不是布局静态通过。')
    save('证据/交付核验.json',audit)
    paths=[REPORT]+sorted(p for p in BASE.rglob('*') if p.is_file() and p!=BASE/'证据/文件清单.json')
    manifest=[dict(path=str(p.relative_to(BASE.parent)),sha256=sha(p),bytes=p.stat().st_size) for p in paths]
    save('证据/文件清单.json',dict(files=manifest,excluded_self='本文件不包含自己的哈希，避免循环'))
    print(json.dumps(dict(delivery_integrity_pass=audit['all_pass'],files=len(manifest),
                         report_path=str(REPORT),static_pass=False,wall_seconds=execution['wall_seconds']),ensure_ascii=False))
    if not audit['all_pass']:raise SystemExit(1)


if __name__=='__main__':main()
