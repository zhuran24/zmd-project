"""封存本线交付清单；读取实际交付记录验收，排除其它席位与构建缓存。"""
import hashlib
import json
import re
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parent
SPEC=BASE.parent
SOLVER=SPEC.parent
EXAMPLES=SOLVER/'数据/样例'
sys.path.insert(0,str(EXAMPLES))
import check_examples as checker
from check_golden_trace import INPUT, OUTPUT, GOLDEN
from runtime_record import validate_record, validate_checkpoint
from test_runtime_input import validate_schema


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks=checker.load_json(BASE/'自查结果.json')
    checker.require(checks['status']=='通过' and all(r['exit_code']==0 for r in checks['commands']), '有未通过命令')
    data=checker.load_json(INPUT);output=checker.load_json(OUTPUT)
    schema=checker.load_json(SPEC/'内核输出.schema.json')
    validate_schema(output,schema,schema)
    validate_record(output,data)
    validate_checkpoint(data,checker.load_json(BASE/'中途种子.json'),'J|2|0|1')
    before=checker.load_json(BASE/'本次修订前产物指纹.json')
    golden_paths=[GOLDEN,EXAMPLES/'混做粉碎机两下游-黄金轨迹.md']
    checker.require(all(digest(p)==before[str(p)] for p in golden_paths),'手工黄金被修改')
    protected=checker.load_json(BASE/'只读指纹.json')
    checker.require(all(digest(Path(p))==h for p,h in protected.items()),'保护文件发生变化')
    runtime=checker.load_json(BASE/'运行回归结果.json')
    checker.require(runtime['status']=='通过' and runtime['axis_count']==99 and len(runtime['tests'])==72,'运行回归统计变化')
    tests=(BASE/'cargo-test.log').read_text()
    checker.require(sum(map(int,re.findall(r'test result: ok\. (\d+) passed',tests)))==31,'Cargo通过数不符')
    report=(BASE/'候选B校验报告.md').read_text()
    checker.require(all(s in report for s in ('能检且通过（4925 项','能检且不通过（0 项','不能静态检（59 项')),'候选B统计不符')
    owned=[SPEC/name for name in ('内核输入.md','内核输出.md','内核输出.schema.json',
                                  '内核输入-修订记录.md','内核输入-对参数轴的修改请求.md')]
    owned += [p for p in EXAMPLES.iterdir() if p.is_file()]
    owned += [p for p in BASE.iterdir() if p.is_file()]
    for path in owned:
        if path.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
                checker.require((path.parent/target.split('#')[0]).exists(),'交付链接悬空: '+str(path)+': '+target)
    audit={'status':'通过','date':'2026-09-19','findings_revised':9,'axis_count':99,'runtime_regressions':72,
           'cargo_tests':31,'candidate_b':{'passed':4925,'failed':0,'not_static':59},
           'protected_files':len(protected),'protected_unchanged':True,'golden_original_bytes_unchanged':True,
           'stored_record_schema_and_complete_replay':'通过','checkpoint_roundtrip':'通过',
           'reader_review':{'history_and_current_separated':True,'versions_and_counts_consistent':True,
                            'current_scope_old_phrases_removed':True,'links_resolve':True,
                            'representation_not_claimed_as_general_execution':True},
           'shared_interface':'已读并核规格线第6轮§6答复；99轴及共享规格自查通过',
           'open_items':['per_instant通用运行与非周期函数/非有理求值',
                         '任意中途种子直接续跑和边界内部队列回放',
                         '实际混做、下游生产、离线和玩家动作、全历史族、全部解释及目标认证']}
    audit_path=BASE/'交付自审.json'
    audit_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    manifest_path=BASE/'交付清单.json'
    owned += [audit_path,manifest_path]
    modified=sorted({p for p in owned if p==manifest_path or (p.is_file() and digest(p)!=before.get(str(p)))})
    manifest={'schema':'kernel-input-delivery-v2','files':[str(p) for p in modified],
              'sha256':{str(p):digest(p) for p in modified if p!=manifest_path},
              'self_reference':'本清单列出自身路径，不含自身SHA以免循环；其它交付物均按实际字节锁定。',
              'baseline':str(BASE/'本次修订前产物指纹.json'),
              'excluded':'未变字节、target/.cargo-home构建缓存、其它席位修改的共享规格和复核文件不列为本席改动。',
              'summary':'9项处理落盘；3个样例、72项运行回归、黄金、规则覆盖、共享规格、31项Cargo及候选B校验通过。'}
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'通过','files':len(modified),'runtime_regressions':72,'manifest':str(manifest_path)},ensure_ascii=False))


if __name__=='__main__':main()
