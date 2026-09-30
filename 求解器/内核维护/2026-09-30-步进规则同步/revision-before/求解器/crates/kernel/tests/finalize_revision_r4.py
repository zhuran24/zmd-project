#!/usr/bin/env python3
"""第4轮交付：实测汇总、逐发现论证、只读范围指纹及非递归文件清单。"""
import hashlib
import json
import os
from pathlib import Path
import re
from cleanup_revision_r3 import scan

ROOT = Path(__file__).resolve().parents[3]
KERNEL = ROOT / 'crates/kernel'
OUT = KERNEL / 'evidence/revision-r4'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def inventory():
    paths = []
    for here, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ('target', '.cargo-home', '.git', '__pycache__')]
        paths += [Path(here) / name for name in names]
    paths += list(ROOT.parent.iterdir())
    return {str(p): dict(path=str(p), bytes=p.stat().st_size, sha256=sha(p))
            for p in paths if p.is_file() and not p.is_symlink()}


def main():
    test_log = (OUT / 'cargo-test.log').read_text()
    assert 'FAILED' not in test_log and 'error:' not in test_log
    tests = sum(map(int, re.findall(r'test result: ok\. (\d+) passed', test_log)))
    assert tests == 129, tests
    assert 'revision_r4_public_cli_regressions ... ok' in test_log
    assert 'Finished ' in (OUT / 'clippy.log').read_text()
    assert 'error:' not in (OUT / 'clippy.log').read_text()
    cli = read(OUT / 'cli/results.json')
    assert cli['status'] == 'pass_with_open_schema_gap'
    references = read(KERNEL / 'evidence/round5/record-validation.json')
    audit = read(KERNEL / 'evidence/round5/audit-results.json')
    assert references['status'] == '通过' and audit['status'] == 'pass'
    assert set(audit['required_unexercised']) == {'damping.belt_adjacency', 'transfer.resume_event', 'connection.bridge_first_contact'}
    bench = read(KERNEL / 'evidence/round5/benchmark-r4.json')
    write(OUT / 'benchmark-final.json', bench)
    requested = ['benchmark_brick_60', 'benchmark_candidate_b']
    metrics = {r['name']: r['ms_per_tick'] for r in bench['reports']}
    benchmark = {**bench, 'schema': 'kernel-benchmark-round5-v1', 'requested_cases': requested,
                 'requested_targets_met': all(r['target_met'] for r in bench['reports'] if r['name'] in requested),
                 'scope_report': str(OUT / '修订与验证.md')}
    write(KERNEL / 'evidence/benchmark.json', benchmark)
    write(KERNEL / 'evidence/round5/benchmark-final.json', bench)
    findings = [
        ('KR-r4-L1-01', '已修复', '普通格按物种集合判混种，同种跨年龄合法；容量、配方与扣料覆盖全部记录，入货保留真实新年龄。', '规则L13、输入§6、转移§4.1/4.2/6.2；年龄正例、混种/51件/跨格负例、满箱选下一格与跨组制造。'),
        ('KR-r4-L1-02', '已修复', '派生前严格核trigger恰含kind/value；公开生产键再次核封闭结构。', '输入§6、转移§6.2；run/seed/cycle和两个键入口拒绝extra，合法待办仍可装载。'),
        ('KR-r4-L1-03', '已修复', '必填表域从多级非运输取货侧沿完整几何求可查询分流器；非必填行可省，已填行仍严校。', '输入§5.3、转移§3.1/3.4；空表与全表12刻除参数点外逐字段相等，必填任一子集缺失仍unresolved。'),
        ('KR-r4-L1-04', '标签与聚合已修复；运行覆盖仍缺', '删除连续两带生成的伪邻接标记；path_runs下邻接轴统一not_exercised。', '参数轴§2、受限模型声明§2、输出§1；端到端记录、伪造标签拒收及独立缺口审计。'),
        ('KR-r4-L1-05', '已修复', '已装载引擎的空前缀保留完整起点、空ticks、种子end_time和验证范围；装载失败外壳仍可空。', '输出§1/§2；t=1检查点在t=2首刻max_sweeps=1停止，全态/增量均核字段并通过AJV。'),
        ('KR-r4-L2-1', '标签与聚合已修复；运行覆盖仍缺', '与L1-04同根因，独立保留ID；覆盖审计要求所有path_runs记录均未调用几何邻接轴。', '连续带样例仍实际执行belt_component_rule；未将此证据转记为belt_adjacency。'),
        ('KR-r4-L2-2', '未解决，已复现并续记KQ-09', '资源不足保持inconclusive/resource，装载失败不伪造状态；现行schema仍拒绝空上下文。', '输出§1/§5.1、转移§1；当前schema的AJV错误已存，K线无schema写权，S线请求见KQ-09。'),
    ]
    open_items = [
        'KR-r4-L2-2 / KQ-09：现行CycleResult schema仍拒绝装载资源未决的空上下文；待S线限定非空要求，K线没有schema写权。',
        'K6运行覆盖仍缺damping.belt_adjacency、connection.bridge_first_contact、transfer.resume_event；分别需要几何连通块、建造先接、暂停后恢复转移。',
        '密集制造闭环序2/5在1000 tick内未决；已核四份周期仅为条件低产反例，种子可达史、全局参数/读法族和一般动态约束未证。',
        '级二提升仍缺整批容量余量及非精确拿取族证明；本轮没有完成执行器/认证器的全称认证。',
    ]
    result = dict(status='revised_with_open_items', tests_passed=tests, clippy='pass',
                  cli_cases=len(cli['cases']), schema_passed=sum(r['valid'] for r in cli['schema_results']),
                  schema_failed=sum(not r['valid'] for r in cli['schema_results']),
                  reference_records=len(references['records']), audited_records=len(audit['records']),
                  cycle_results=len(audit['cycles']), ms_per_tick=metrics,
                  requested_targets_met=benchmark['requested_targets_met'],
                  findings=[dict(zip(('id', 'status', 'change', 'basis'), row)) for row in findings],
                  open_items=open_items)
    write(OUT / '交付结果.json', result)
    write(KERNEL / 'evidence/round5/交付结果.json', {**result, 'current_report': str(OUT / '修订与验证.md')})
    table = '\n'.join('| ' + ' | '.join(row) + ' |' for row in findings)
    report = f'''# 内核第4轮修订与验证

日期：2026-09-20。状态：7个发现ID逐项处理，6项在K线辖域完成修订，KR-r4-L2-2的schema兼容仍待S线。当前规格为S线第8轮；本报告只给受限实现及实际检查结果，不证明完整目标或全称认证。

## 逐发现处理

| 发现ID | 状态 | 修改 | 据与验证 |
|---|---|---|---|
{table}

新增Rust回归见[tests_revision_r4.rs](../../src/tests_revision_r4.rs)，公开入口、独立AJV及反向伪造测试见[revision_r4_cli.py](../../tests/revision_r4_cli.py)。原始输入、命令、退出码与输出路径见[CLI结果](cli/results.json)。三份正式文件、任务书5→1→2→3→4、当前输入/输出/schema/转移/参数轴/受限声明及[规格请求](../../../../规格/对内核的修改请求.md)作为本轮依据。

## 年龄分组与完整库存路径

规则L13限制的是物种数，记录行数还承载年龄。校验先逐行核正数量与入格时刻，再按物种集合核普通格单种，最后按单位/物种核跨普通格唯一性；箱体跨格和缓存例外保持。容量用全部年龄组之和。缓存批次、制造输入配方计数也按物种求和，不能让后行覆盖前行。整批扣料先核全量足够，再沿规范记录序扣减；数量不足不改库存。新入货只可合并同物种同入格时刻的记录，保留不同年龄。非运输格当前无年龄守卫，记录顺序为确定编码；运输格仍受容量1与滞留守卫，未添加新物种优先级。

新增年龄分组后，原Python参考器的单行累加也会丢失新年龄，首次全套因此在分流器逐字段差分失败，日志见[迁移前测试](pre-reference-migration-cargo-test.log)。参考器已按相同条款分别记新年龄、合计容量与配方、跨记录扣料，状态校验按物种集合核单种。黄金文件、原v2文件和[严格比较器](../../tests/reference.rs)保持原始字节。新v3记录通过现场Python独立重算及Rust逐字段比较，没有删除年龄、事件或状态字段，也未放宽断言。

## 分支表必填域与恢复

完整几何图是运行中删边/恢复图的母图；本支持域无新增几何。每个非运输单位的取货边按“直连汇流器逐边独立，其余合一级”分组。母图至多一级时，任何删边子图也至多一级，按转移§3.1永不发起阻尼查询，因此无需分支表。母图至少两级时，从其每条取货PC沿所有运输出路做可达搜索；遇非运输终点立即停止，桥接器仅沿到达轴。搜索不读取physical、当前门阻断或已选分支，因而保留当前失活但恢复后可查的分流器。有限PC去重使有向环也可完成静态域分析；运行中无终点仍按原停止语义处理。

上述可达分流器强制给全体非空几何出支子集。域外行允许省略，已填行仍核分流器身份、规范有序非空集合、所选成员及重复键，不能借此放过坏行。实际查表只读当前现存出边集合。12刻全表/空表对照只去除明确不同的参数点字段，其余完整状态、事件、时间、闭包和台账均相同；必填分流器的每一子集分别删除仍报unresolved，18刻切支/恢复正例通过。

## 输出、覆盖与KQ-09边界

trigger的封闭字段在种子派生之前检查，避免派生窗口日程覆盖未知扩展；键编码再次拒绝extra，防止公开Engine状态被调用方改写后把未定义字段带入生产键。

path_runs仅计路径连续带串，未调用geometric_components的几何邻接关系。覆盖生成器不再接受belt_adjacency标记，底层不再发出该标记，独立审计逐份确认未触发。连续带样例仍为belt_component_rule提供真实证据。K6保留三个具名缺口及原因，不能因参数有赋值或路径恰有两条带宣布邻接轴已覆盖。

run_record接收的Engine已经装载成功，空ticks不能推出装载失败；即使第一刻停止也保留start_state，end_time/from/through均为种子时刻，未闭包的半刻不提交。CLI实测从t=1检查点在t=2预算耗尽，两种编码均符合schema。与此不同，年龄溢出在装载阶段尚未形成合法引擎，cycle保持inconclusive/resource、completed_ticks=0及空上下文。AJV对该对象仍拒收seed/parameter_point/replay_input/run_record，错误及schema指纹见CLI结果；[KQ-09](../../../../规格/内核实现-对规格的疑问.md)已续记原精确请求。没有改schema、伪造种子或把资源不足降为invalid/stopped。

## 最终验证与性能

| 检查 | 实测结果 |
|---|---|
| cargo test --locked --offline | {tests}项通过，0失败；90项kernel库、3项完整参考、5项CLI集成、31项topology；[日志](cargo-test.log) |
| clippy --all-targets -- -D warnings | 通过；[日志](clippy.log) |
| 第4轮release公开CLI与AJV2020 | {len(cli['cases'])}次调用符合预期；{result['schema_passed']}份结果schema通过、1份KQ-09未通过；[日志](cli.log) |
| verify_outputs | 双参考×全态/增量共{len(references['records'])}份严格验收；[日志](verify-outputs.log) |
| 扩展及覆盖审计 | {len(audit['records'])}份运行、{len(audit['cycles'])}份循环结果；独立台账、字段键、周期率及完整重跑；[日志](coverage-audit.log)、[聚合结果](../round5/audit-results.json) |
| release性能 | 57单位/97PC：{metrics['benchmark_brick_60']:.6f} ms/tick；219制造台/315逻辑段/630PC：{metrics['benchmark_candidate_b']:.6f} ms/tick；额外81单位/100PC：{metrics['benchmark_brick']:.6f} ms/tick；[原始数据](benchmark-final.json) |

性能只计12次引擎推进，解析/构造/序列化不在ms/tick内，进程wall_ns另列。指定两档目标为≤1和≤20 ms/tick，本次达标标记为{str(benchmark['requested_targets_met']).lower()}；额外81单位档不冒称指定砖档。B档为关闭制造、有限预置货的合成物流压力布局，不证明候选B真实几何或长期满载性能。原缓存/直接路径逐字段差分已随全套通过。密集制造四份条件周期仍为190/190/105/395 tick，分流比为1/1/0/0，另外两序未决。

## 范围与未决

全部写入限K线授权路径，编译使用共享target，证据仅脚本、日志、JSON、Markdown；没有复制编译缓存、仓库快照或改动模拟器，没有commit/push。开工/收尾逐字节比较及读者自审见[范围审计](范围审计.json)，实际变更、新增及原始指纹见[交付清单](交付清单.json)。旧轮报告与旧生成器是历史记录，当前入口为finalize_revision_r4.py。

{chr(10).join('- ' + item for item in open_items)}
'''
    (OUT / '修订与验证.md').write_text(report)
    revision = KERNEL / '修订记录.md'
    text = revision.read_text()
    marker = '## 第4轮修订：年龄分组、阻尼查询域与停止记录'
    if marker in text:
        text = text[:text.index(marker)].rstrip() + '\n'
    text += f'''\n{marker}

日期：2026-09-20。性质：执行记录。当前论证与边界见[第4轮报告](evidence/revision-r4/修订与验证.md)。

| 发现ID | 状态 | 修改 | 据与验证 |
|---|---|---|---|
{table}

全工作区{tests}项通过、Clippy零警告，双参考{len(references['records'])}份、扩展{len(audit['records'])}份运行及{len(audit['cycles'])}份循环结果验收通过。第4轮release CLI共{len(cli['cases'])}次调用，独立AJV为{result['schema_passed']}通过、1个KQ-09未通过。指定砖档{metrics['benchmark_brick_60']:.6f} ms/tick、B档{metrics['benchmark_candidate_b']:.6f} ms/tick。黄金、v2及严格比较器未改；参考器按真实年龄修复并重生成v3，没有放宽差分。KQ-09待S线；K6三项缺口、两序预算未决及级二/全称义务如实保留。
'''
    revision.write_text(text)

    before = {r['path']: r for r in read(OUT / 'baseline.json')['files']}
    current = inventory()
    def authorized(path):
        p = Path(path)
        return p.is_relative_to(KERNEL) or p.is_relative_to(ROOT / '数据/样例') or p == ROOT / '规格/内核实现-对规格的疑问.md'
    violations = [p for p in before.keys() | current.keys() if not authorized(p)
                  and before.get(p, {}).get('sha256') != current.get(p, {}).get('sha256')]
    assert not violations, violations
    protected = [ROOT / 'crates/kernel/tests/reference.rs'] + [ROOT.parent / name for name in ('《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt')]
    for name in ('混做粉碎机两下游-黄金轨迹.json', '混做粉碎机两下游-黄金轨迹.md'):
        protected.append(ROOT / '数据/样例' / name)
    for p in protected:
        assert sha(p) == before[str(p)]['sha256'], p
    forbidden = [str(p) for p in OUT.rglob('*') if p.is_dir() and p.name in ('target', '.cargo-home', 'registry', 'snapshot')]
    unexpected = [str(p) for p in OUT.rglob('*') if p.is_file() and p.suffix not in ('.py', '.sh', '.rs', '.log', '.json', '.md')]
    assert not forbidden and not unexpected, (forbidden, unexpected)
    evidence_scan = scan()
    assert not any(evidence_scan.values()), evidence_scan
    docs = [KERNEL / 'README.md', revision, OUT / '修订与验证.md', KERNEL / 'evidence/round5/实施与验证.md',
            ROOT / '数据/样例/第五轮样例说明-kernel.md', ROOT / '规格/内核实现-对规格的疑问.md',
            KERNEL / '复核/证据维护说明.md', KERNEL / 'tests/legacy_probes/README.md']
    pending = {OUT / '范围审计.json', OUT / '交付清单.json'}
    broken = []
    for doc in docs:
        body = doc.read_text()
        assert re.search(r'20\d{2}-\d{2}-\d{2}', body[:512]), doc
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', body):
            if target.startswith(('http:', 'https:', '#')):
                continue
            path = (doc.parent / target.split('#')[0]).resolve()
            if not path.exists() and path not in pending:
                broken.append(dict(document=str(doc), target=target))
    assert not broken, broken
    scope = dict(status='pass', protected_files=sum(not authorized(p) for p in before), protected_changes=violations,
                 build_target=str(ROOT / 'target'), forbidden_evidence_directories=forbidden, unexpected_evidence_files=unexpected,
                 full_kernel_evidence_scan=evidence_scan,
                 unchanged_explicit_sources=[dict(path=str(p), sha256=sha(p)) for p in protected],
                 scope='比较仓库根普通文件与求解器普通文件；共享target/.cargo-home及__pycache__排除。模拟器未运行或改写。',
                 document_reader_review=dict(status='pass', documents=list(map(str, docs)), broken_links=broken,
                     checks=['7个ID逐项有据', '当前与历史分区', '库存年龄与计数路径完整', 'KQ-09与已装载空前缀区分',
                             '3个覆盖缺口有明确原因', '黄金及严格差分未放宽', '条件证书不升级全称', '数字与实测一致']))
    write(OUT / '范围审计.json', scope)
    current = inventory()
    excluded = {str(OUT / n) for n in ('交付清单.json', '最终回复.json', 'finalize.log')}
    changes = [dict(path=p, action='added' if p not in before else 'deleted' if p not in current else 'modified',
                    before=before.get(p), after=current.get(p)) for p in sorted(before.keys() | current.keys())
               if p not in excluded and before.get(p, {}).get('sha256') != current.get(p, {}).get('sha256')]
    write(OUT / '交付清单.json', dict(schema='kernel-revision-r4-files-v1', changes=changes, nonrecursive_files=sorted(excluded)))
    files = sorted({c['path'] for c in changes if c['after'] is not None} | excluded)
    summary = f'7个发现ID逐项处理，6项完成修订，KQ-09待S线。\n修复年龄分组及计数、trigger封闭校验、阻尼表查询域、覆盖误报和空续跑前缀。\n{tests}项测试与Clippy通过，4份严格参考、26份运行和10份循环结果验收通过。\n公开CLI 15次符合预期，AJV 11通过、1个既有schema冲突。\n砖档{metrics["benchmark_brick_60"]:.3f} ms/tick，B档{metrics["benchmark_candidate_b"]:.3f} ms/tick；K6保留三项缺口。\n论证、日志、来源及范围审计已落盘；正式文件和黄金未改，未commit/push。'
    write(OUT / '最终回复.json', dict(files=files, summary=summary, open_items=open_items))
    print(json.dumps(dict(status='pass', tests=tests, files=len(files), metrics=metrics, requested_targets_met=benchmark['requested_targets_met']), ensure_ascii=False))


if __name__ == '__main__':
    main()
