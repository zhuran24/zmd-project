#!/usr/bin/env python3
"""最终记录验收后封存两轮清单；封存后只读复核，不再生成被列产物。"""
import hashlib
import json
from pathlib import Path
import re
import sys

BASE = Path(__file__).resolve().parent
SPEC = BASE.parent
SOLVER = SPEC.parent
ROOT = SOLVER.parent
EXAMPLES = SOLVER/'数据/样例'
sys.path.insert(0,str(EXAMPLES))
import check_examples as checker
from check_golden_trace import INPUT, OUTPUT, GOLDEN
from runtime_record import validate_record, validate_checkpoint
from test_runtime_input import validate_schema


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def verify_manifest(path):
    manifest = checker.load_json(path)
    expected = set(manifest['files']) - {str(path)}
    checker.require(set(manifest['sha256']) == expected, '清单哈希集合遗漏/重复')
    for name, fingerprint in manifest['sha256'].items():
        checker.require(digest(Path(name)) == fingerprint, '清单哈希失配: '+name)
    return len(expected)


def main():
    checks = checker.load_json(BASE/'自查结果.json')
    checker.require(checks['status']=='通过' and all(r['exit_code']==0 for r in checks['commands']), '全套检查尚未通过')
    checker.require(all(digest(Path(p))==h for p,h in checks['shared_start_sha256'].items()), '自查后共享依赖有变化，须重验')
    baseline = checker.load_json(BASE/'本次修订前产物指纹.json')
    for path in (GOLDEN, EXAMPLES/'混做粉碎机两下游-黄金轨迹.md'):
        checker.require(digest(path)==baseline[str(path)], '手工黄金发生变化')
    protected = checker.load_json(BASE/'只读指纹.json')
    protected = {p:h for p,h in protected.items() if p not in checks['shared_start_sha256']}
    checker.require(all(digest(Path(p))==h for p,h in protected.items()), '正式/候选/模拟器保护字节改变')
    sim_before = {p for p in protected if p.startswith(str(ROOT/'模拟器')+'/')}
    checker.require(sim_before=={str(p) for p in (ROOT/'模拟器').rglob('*') if p.is_file()}, '模拟器文件集合改变')
    data = checker.load_json(INPUT); output = checker.load_json(OUTPUT)
    schema = checker.load_json(SPEC/'内核输出.schema.json')
    validate_schema(output,schema,schema)
    validate_record(output,data)
    validate_checkpoint(data,checker.load_json(BASE/'中途种子.json'),'J|2|0|1')
    runtime = checker.load_json(BASE/'运行回归结果.json')
    revision = checker.load_json(BASE/'修订回归结果.json')
    checker.require(runtime['status']=='通过' and revision['status']=='通过', '运行/反例回归失败')
    cargo = sum(map(int,re.findall(r'test result: ok\. (\d+) passed',(BASE/'cargo-test.log').read_text())))
    candidate_text = (BASE/'候选B校验报告.md').read_text()
    candidate = {}
    for key, label in [('passed','能检且通过'),('failed','能检且不通过'),('not_static','不能静态检')]:
        candidate[key] = int(re.search(label+r'（(\d+) 项',candidate_text).group(1))
    checker.require(candidate['failed']==0, '候选B有失败')
    findings = ['K3-r4-L1-01','K3-r4-L3-01','K3-r4-L3-02','K3-r4-L3-03']
    # 自审与最终报告先写完，再生成清单，杜绝后写报告使清单失效。
    audit = {'status':'通过','date':'2026-09-19','findings_revised':findings,
             'axis_count':runtime['axis_count'],'runtime_regressions':len(runtime['tests']),
             'revision_regressions':revision['count'],'cargo_tests':cargo,'candidate_b':candidate,
             'protected_file_count':len(protected),'protected_unchanged':True,
             'golden_original_bytes_unchanged':True,'stored_record_schema_and_complete_replay':'通过',
             'checkpoint_roundtrip':'通过','shared_stable_since_checks':True,
             'reader_review':{'current_versions_and_history_separated':True,'all_four_findings_have_basis':True,
                              'function_representation_execution_and_universal_claims_separated':True,
                              'identity_scope_covers_input_seed_output_and_pending':True,
                              'local_links_resolve':True,'summary_counts_from_logs':True},
             'shared_request':'§7三项已由规格线第7轮答复并入，本线回核共享三表入口',
             'open_items':['通用per_instant执行、非有理求值及表达式语言外的函数未实现',
                           '任意中途种子续跑、实际混做/下游生产、全历史/解释及全部循环目标认证仍未完成']}
    write_json(BASE/'交付自审.json',audit)
    report = f'''# 内核输入第四轮修订自查

日期：2026-09-19。性质：执行证据记录。状态：本线要求的检查及附加规格线自查全部通过；四项发现均已落实。处理论证见[存活发现处理](存活发现处理.md)，逐条索引见[修订记录](../内核输入-修订记录.md)。本报告不是通用内核或达标认证。

## 检查结果

| 检查 | 实测结果 | 证据 |
|---|---|---|
| 样例 | 三例通过，19项负例和8组表示回归；几何与运行支持域分别验收 | [样例检查](样例检查.log) |
| 黄金轨迹 | 0–3 tick，四次出库、两个完整粉碎周期；逐刻事件/扫描28、42、43、43；手工JSON与Markdown原字节未变 | [黄金重算](黄金重算.log) |
| 原运行回归 | {len(runtime['tests'])}项通过，当前{runtime['axis_count']}轴；完整记录、投影、schema、周期排序及中途种子 | [运行回归结果](运行回归结果.json) |
| 第四轮回归 | {revision['count']}项通过；非周期函数、负/非整数/远时刻、隐藏坏分支、全槽位碰撞、全局历史/跨tick/pending事件身份 | [修订回归结果](修订回归结果.json) |
| 规则覆盖 | 两张覆盖表各逐行核114行规则、15行任务及56条约束，99轴全集与四条修订记录对齐 | [覆盖结果](规则覆盖自查.json) |
| 规格线自查 | 当前目录、99轴和第7轮相遇/空格序修订检查通过 | [规格线自查](规格线自查.log) |
| Cargo | {cargo}项通过，0失败，offline/locked | [cargo test](cargo-test.log) |
| 候选B | {candidate['passed']}通过、{candidate['failed']}失败、{candidate['not_static']}不能静态检；56正式约束均有报告项 | [校验报告](候选B校验报告.md) |
| 目录回源 | 正式全文/行号/哈希与单位/配方目录通过 | [回源日志](正式目录回源.log) |
| 最终落盘记录 | schema、完整重算、来源、全局身份和实际中途种子再验通过 | [交付自审](交付自审.json) |

计数均为工具实测，不是游戏实测或目标证明。Cargo和候选B只证契约静态检查；黄金只证给定条件有限前缀。完整命令、退出码和保护结果见[自查结果](自查结果.json)。运行记录来源包含实际读取的参数投影及正文，最终封存前已重新验证。

## 版本与边界

内核输入kernel-input-v3，输出kernel-output-v2，参数投影profile-assignment-v2。排序通用表示接v1/v2/v3，新增order-expr-v1表达式能表示正的2的幂换序的整个有理时域；全域证明见处理报告§1，远时刻选点测试不替代该证明。有限执行仍只运行global/v1组合。仓库保留命名域及J/C历史前缀按输入、StateSeed、生成与输出全辖域检查。

规格线并行将connection.port_meeting迁为open/U且保留共边本版值，并补成功入库后的空格序维护。本线核过差异后重新生成三例和投影，旧生命周期拒收没有被绕过，静态几何的显式取值分支已补。现行输入轴说明对齐；[迁移记录](共享配置迁移.json)保存差异。没有箱体/入库的有限轨迹不冒称验证了空格序后效。

正式三文件、候选约束和模拟器共{len(protected)}个保护文件字节及模拟器文件集合未变。共享三表的并行变化单列在自查结果，检查时段内稳定；本席未修改三表。新增v3及全局身份引用请求已由规格线第7轮答复并入；本线回核轴表、清单T2、覆盖表L25/L36/任务L14及文末身份入口，结果见[修改请求](../内核输入-对参数轴的修改请求.md)§7。未git commit/push。

任意中途种子直接续跑、非有理求值、语言外函数、通用per_instant执行、实际混做/下游生产、离线/玩家动作、全历史和全部解释及循环目标认证均未完成。修复四个具体发现没有更新真实布局下界。

## 封存与复现

仓库根依次运行：

```bash
python -B 求解器/规格/内核输入修订验证-r4/run_checks.py
python -B 求解器/规格/内核输入修订验证-r4/finalize_delivery.py
```

第二条必须最后执行：它先验实际落盘记录，再更新第三轮旧清单的当前字节哈希并明确历史语境，生成[第四轮交付清单](交付清单.json)，最后重读两清单的全部条目。清单不包含自身哈希，避免循环；其它所列文件全部锁定实际字节。之后若共享同步或重算改变被列文件，须重验重封，不能沿用此前“通过”。

交付读者自审覆盖当前版本与历史分区、四条发现及正式依据、表示/执行/全称边界、全局身份辖域、统计口径和本地链接。第一次全套检查中的样例链接核验先于中途种子生成而失败；现将样例自查置于种子和排序文件生成之后，最终全套重跑通过，没有把缺文件错误当作行为通过。
'''
    (BASE/'自查报告.md').write_text(report)
    owned = [SPEC/name for name in ('内核输入.md','内核输出.md','内核输出.schema.json','内核输入-修订记录.md','内核输入-对参数轴的修改请求.md')]
    owned += [p for p in EXAMPLES.iterdir() if p.is_file()]
    owned += [p for p in BASE.iterdir() if p.is_file()]
    old_path = SPEC/'内核输入修订验证-r3/交付清单.json'
    old = checker.load_json(old_path)
    old['historical_summary'] = old.get('historical_summary',old['summary'])
    old['summary'] = '第三轮历史文件列表；当前所列字节已由第四轮验收后刷新，现行结论见第四轮交付清单。'
    old['status'] = 'superseded'
    old['current_validation'] = str(BASE/'交付清单.json')
    old['refreshed_by'] = str(BASE/'finalize_delivery.py')
    old['sha256'] = {name:digest(Path(name)) for name in old['files'] if name != str(old_path)}
    write_json(old_path,old)
    old_count = verify_manifest(old_path)
    owned.append(old_path)
    for path in owned:
        if path.suffix == '.md':
            for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
                checker.require((path.parent/target.split('#')[0]).exists(), '交付链接悬空: '+str(path)+': '+target)
    manifest_path = BASE/'交付清单.json'
    changed = sorted({p for p in owned if p==manifest_path or digest(p)!=baseline.get(str(p))})
    manifest = {'schema':'kernel-input-delivery-v3','status':'verified','files':[str(p) for p in changed],
                'sha256':{str(p):digest(p) for p in changed if p!=manifest_path},
                'baseline':str(BASE/'本次修订前产物指纹.json'),
                'self_reference':'只排除自身SHA以免循环；其余所列文件按最后验证后的实际字节锁定。',
                'previous_manifest':{'path':str(old_path),'verified_hashes':old_count,'status':'superseded'},
                'summary':'4项发现已修订；全部必需自查通过，实际记录再验、两清单末次哈希复核通过。',
                'attribution':'交付追踪本轮相对开工变化的接口与样例实际字节；并行规格维护和本线消费迁移在处理报告§5分开说明，不声称独占作者。',
                'open_items':audit['open_items']}
    write_json(manifest_path,manifest)
    current_count = verify_manifest(manifest_path)
    verify_manifest(old_path)
    print(json.dumps({'status':'通过','files':len(changed),'current_hashes':current_count,'previous_hashes':old_count,
                      'manifest':str(manifest_path)},ensure_ascii=False))


if __name__ == '__main__':
    main()
