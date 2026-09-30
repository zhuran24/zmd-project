#!/usr/bin/env python3
"""第3轮历史生成器（仅配合该轮冻结结果；当前入口为finalize_revision_r4.py）。第3轮交付：从当前实测结果生成逐发现台账，不覆盖历史轮次的结论。"""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
KERNEL = ROOT / 'crates/kernel'
OUT = KERNEL / 'evidence/revision-r3'
ROUND5 = KERNEL / 'evidence/round5'


def read(path):
    return json.loads(path.read_text())


def main():
    tests = (OUT / 'cargo-test.log').read_text()
    assert 'FAILED' not in tests and 'error:' not in tests
    count = sum(map(int, re.findall(r'test result: ok\. (\d+) passed', tests)))
    assert count == 121, count
    clippy = (OUT / 'clippy.log').read_text()
    assert 'Finished' in clippy and 'error:' not in clippy
    audit = read(ROUND5 / 'audit-results.json')
    references = read(ROUND5 / 'record-validation.json')
    cli = read(OUT / 'cli/results.json')
    schema = read(OUT / 'cli-schema-audit.json')
    clean = read(OUT / 'cleanup.json')
    bench = read(ROUND5 / 'benchmark-final.json')
    assert audit['status'] == cli['status'] == clean['status'] == 'pass'
    assert references['status'] == '通过'
    assert set(audit['required_unexercised']) == {'transfer.resume_event','connection.bridge_first_contact'}
    metrics = {r['name']: r['ms_per_tick'] for r in bench['reports']}
    findings = [
        ('KR-r3-L1-01','已修复','仅before_boundary同步参数；after_closure校验并保留原参数。','输入§6.4、KQ-07；参数缺失/冲突/生命周期与合法续跑对照。'),
        ('KR-r3-L1-02','已修复','after_closure待窗口必须deadline>t，before_boundary允许deadline=t。','规则L64、转移§2.1；deadline<t/=t/>t及本刻到期维护正例。'),
        ('KR-r3-L1-03','已修复','verify-cycle共用独立完整前缀身份/时序检查，然后整份重算和P步重跑。','输出§2、§5.3.1；循环前缀重复事件、原延迟窗口证书均拒收。'),
        ('KR-r3-L1-04','已修复','sufficient在派生与装载阶段核两矿唯一正库存。','任务L7、输入§5.4；源矿/蓝铁矿历史空格均拒收，显式补矿回归保留。'),
        ('KR-r3-L2-01','已修复','覆盖缺失表、表内冲突、只改顶层相位、重复轴与生命周期错误。','与L1-01同源，独立保留ID；真实桥检查点状态和续跑五字段相等。'),
        ('KR-r3-L2-02','已修复','所有锚点单独解析历史相位Time并核整数0…5；允许合法历史值不同于当前冷却。','规则L36、输入§1.1/§5；-1/6/1/2/错误类型拒收，合法0/5对照通过。'),
        ('KR-r3-L2-03','标签与审计已修复；运行覆盖仍缺','桥搬运不计先接；含桥为input_checked，聚合独立核历史/方向/操作。','输出§1、第五轮K6；先接与恢复两轴逐条说明缺口，不虚构运行事件。'),
        ('KR-r3-L3-01','已修复','先核完整结构与目录格身份/重复/缺失及仓库引用，再改种子或建派生索引。','输入§2.3、转移§1；短格名/布尔种子及扩展矩阵在run/seed/cycle返回JSON和退出2。'),
        ('KR-r3-L3-02','分类已修复；schema待KQ-09','装载资源不足保留inconclusive和resource；无完整种子时仍留空上下文。','转移§1、输出§1/§5；年龄溢出run/cycle分类一致，但现行schema拒绝空未决外壳。'),
        ('KR-r3-L3-03','已清理','删除15个编译文件与193文件仓库式快照；4组源码探针移出证据树。','任务书5§0.2；cleanup.json保留原路径/字节/SHA-256，清理后无禁目录及ELF/ar。'),
    ]
    table='\n'.join('| '+' | '.join(row)+' |' for row in findings)
    open_items=[
        'KQ-09：现行CycleResult schema不允许装载资源未决的空上下文，与正文可空约定冲突。分类已修复，schema兼容性待S线处理；K线无schema写权。',
        'K6：connection.bridge_first_contact仅input_checked、transfer.resume_event未实际触发；固定已建成/开关/供电段不能生成对应运行事件。',
        '密集制造闭环序2/5在1000 tick内仍未决；4份条件周期不证明完整可达史、全局模板全序或一般动态约束。',
        '级二周期提升的整批容量与非精确拿取族义务、种子/参数/读法族认证及R线最终约减仍开放。',
    ]
    report=f'''# 内核第3轮修订与验证

日期：2026-09-20。状态：10条存活发现逐项处理；KQ-09的schema兼容性尚未解决，K6保留两项运行覆盖缺口。当前实现对齐规格第8轮，普通有限执行和生产部分周期的验证不构成完整基地或全称认证。

## 逐发现处理

| 发现ID | 状态 | 修改 | 据与回归 |
|---|---|---|---|
{table}

代码回归在[tests_revision_r3.rs](../../src/tests_revision_r3.rs)，公开入口回归在[revision_r3_cli.py](../../tests/revision_r3_cli.py)，落盘输入、输出、命令和退出码见[CLI结果](cli/results.json)。规格新冲突见[KQ-09](../../../../规格/内核实现-对规格的疑问.md)。

## 语义与错误边界

检查点恢复与新调度起点分开：先从未经改写的输入解析结构和锚点，只有before_boundary才同步当前参数及派生冗余上下文。after_closure没有修补路径；原参数、生命周期、记忆、成功账本和活动身份由严格装载校验。真实t=5桥检查点经seed保持完整StateSeed相等，续跑首刻t=6；time/state/events/warehouse_ledger/closure与原长轨迹逐字段相同。参数冲突不因重复执行派生而消失。

窗口使用真实5 tick截止，边界前deadline=t意味着本刻应办理，已闭包deadline=t则与“本刻维护已完成”冲突，必须拒收。制造完成的预计deadline仍只作审计，完成继续由remaining归零决定，本修复不把窗口规则外推给暂停制造。传输历史初相位虽与当前冷却分离，仍必须是本版可解的整数Time；1/2是明确unsupported(time.domain)，不是一般游戏禁止半tick的结论。

周期验收对解码后的完整前缀先建立事件注册与执行集合，检查单次消费、阶段和窗口实际执行时刻，再进行确定重算以及循环起点P步重跑。原tiny-expired-cycle在周期之前含延迟W|5|gate，现在verify-cycle和提取的verify-record都因同一待事件时序冲突拒收。新增前缀重复事件回归要求报具体身份错误，不能只靠整份重算不相等使测试通过。正常环带20 tick周期仍可重跑。

畸形结构先返回带位置Result：seed不对未经验证的布尔/数组对象做JSON可变索引；Engine先与目录核格身份与唯一集合、进度/门目标、仓库唯一身份和取货引用，再建索引并计算派生状态。sufficient通过相同装载路径核两矿正库存；explicit_ore_history保留边界显式补给语义，原补给、最后一件矿、容量和暂停回归未放宽。

资源不足与游戏停止分开。run/cycle装载年龄溢出均退出2、inconclusive；cycle.stop.kind=resource。现行schema的inconclusive条件却无条件要求seed/parameter_point/replay_input/run_record非空，正文允许装载前失败留空。不能在未构造成功时制造合法上下文，也不能改回stopped规避。此接口冲突登记KQ-09；[逐例schema审计](cli-schema-audit.json)明确保存{len(schema['passed'])}项通过与{len(schema['open_schema_gaps'])}项未通过，不宣称全部CLI输出schema通过。

## 验证结果

| 检查 | 实测结果与边界 |
|---|---|
| cargo test --locked --offline | {count}项通过、0失败；83项kernel库、3参考、4个CLI集成、31项topology，doc-tests为0；[日志](cargo-test.log) |
| cargo clippy --locked --offline --all-targets -- -D warnings | 通过，零警告；[日志](clippy.log) |
| release公开CLI | {len(cli['cases'])}次调用按预期返回；合法状态原样保留、非法值拒收、无panic；[日志](cli-release.log) |
| verify_outputs | 双参考×全态/增量共{len(references['records'])}份，黄金及完整tick差分通过；[日志](verify-outputs.log) |
| 扩展与覆盖审计 | {len(audit['records'])}份运行记录、{len(audit['cycles'])}份循环结果验收通过；独立台账/键/事件/重跑，保留两项覆盖缺口；[日志](coverage-audit.log)、[完整结果](../round5/audit-results.json) |
| 证据清理 | 15个ELF/ar与193文件快照删除，释放{clean['removed_bytes']}字节；4组探针源码迁出；[清单](cleanup.json) |

最初新增CLI测试将“unsupported相位”的cycle顶层也预期为unsupported，首次全套因此失败；按输出§5的stopped外壳、stop.kind=unsupported修正测试后，全套通过。初次失败日志[保留](initial-cargo-test.log)，未改内核停止语义迎合测试。后补到期检查点的3次CLI调用经release复核纳入59次调用，不额外计为3项Cargo测试。schema问题属于额外交叉验收发现，未作为通过项计数。

## 覆盖与性能

桥方向在输入时已resolved，先接历史发生在运行之前。独立[先接审计](../round5/bridge-first-contact-audit.json)直接核历史时间、方向锚点及实际操作集合；桥上搬运仍可证明bridge.*，不能证明connection.bridge_first_contact实际执行。后者需建造/定向转移；transfer.resume_event需暂停后的开关/供电恢复，二者不在固定已建成运行段。没有通过扩大已声明支持域或补造事件关闭K6。

release测量来自[benchmark-final.json](../round5/benchmark-final.json)，ms/tick为12次引擎推进时间，不含解析、构造或序列化；完整进程时间另存。57单位/97PC砖档为{metrics['benchmark_brick_60']:.6f} ms/tick，219制造台/315逻辑段/630PC档为{metrics['benchmark_candidate_b']:.6f} ms/tick；额外81单位/100PC对照为{metrics['benchmark_brick']:.6f} ms/tick。两档目标分别≤1/≤20；最终是否达标以JSON实测字段为准，额外对照不混入指定砖档。

这些是合成物流压力布局，B档关闭制造、预装有限货，不能当候选B真实可行几何、满载生产或任意长期性能保证。缓存/直接计算的原逐字段差分包含本次全套，未改黄金或放宽参考比较。

## 来源、规格请求与未决

修改请求KQ-01…08及R4-Q1已按当前规格核对；本轮重点落实KQ-07的历史参数保持，其余补矿两模式、v2分支切换、D.2容量前停止、I维护事件与读法锁定均由原回归和重新生成记录继续验收。KQ-09另列为新的规格接口问题，未修改S线schema。

写入限于crates/kernel、数据/样例及内核实现-对规格的疑问.md；编译只用共享target。删除和移动均限内核授权范围，旧报告及原始日志/JSON保留为历史证据，移动说明见[证据维护说明](../../复核/证据维护说明.md)。三份正式文件、候选约束与未授权求解器文件的字节审计见[范围审计](范围审计.json)；逐文件变更、新增和删除见[交付清单](交付清单.json)。未操作模拟器，未commit/push。

未决：KQ-09；两项K6运行覆盖；密集制造序2/5预算未决；条件种子完整可达史、全局模板全序、级二提升及种子/参数/读法族和一般动态约束认证。4份密集条件周期的0/1分流比证据和有限前缀不升级为全称结论。
'''
    (OUT / '修订与验证.md').write_text(report)
    revision = KERNEL / '修订记录.md'
    text = revision.read_text().replace('截止日期：2026-09-19。','截止日期：2026-09-20。')
    marker = '## 第3轮修订：第五轮内核的10条存活发现'
    if marker in text:
        text = text[:text.index(marker)].rstrip() + '\n'
    text += f'''\n{marker}

日期：2026-09-20。性质：修订执行记录。逐发现代码、条款、论证和验证边界见[第3轮报告](evidence/revision-r3/修订与验证.md)；下表保留所有发现ID，重复根因仍分别登记。

| 发现ID | 状态 | 修改 | 据与验证 |
|---|---|---|---|
{table}

全工作区{count}项通过、Clippy零警告，双参考{len(references['records'])}份、扩展{len(audit['records'])}份运行及{len(audit['cycles'])}份循环结果验收通过。release公开CLI {len(cli['cases'])}次调用符合预期；额外schema交叉验收{len(schema['passed'])}项通过、{len(schema['open_schema_gaps'])}项因KQ-09未通过。砖档{metrics['benchmark_brick_60']:.6f} ms/tick，B档{metrics['benchmark_candidate_b']:.6f} ms/tick，额外对照{metrics['benchmark_brick']:.6f} ms/tick。

KQ-09不在K线schema写权内，已登记明确修订请求。先接定向与传输恢复的运行覆盖仍缺，序2/5、级二和族全称认证仍未决；没有用停止或预算耗尽推无解。清理删除清单、最新原始日志与保护审计均在[revision-r3](evidence/revision-r3/)。
'''
    revision.write_text(text)
    result=dict(status='revised_with_open_items',tests_passed=count,clippy='pass',cli_cases=len(cli['cases']),
                cli_schema_passed=len(schema['passed']),cli_schema_open=len(schema['open_schema_gaps']),
                reference_records=len(references['records']),audited_records=len(audit['records']),
                cycle_results=len(audit['cycles']),ms_per_tick=metrics,findings=[dict(zip(['id','status','change','basis'],r)) for r in findings],
                open_items=open_items)
    (OUT / '交付结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('findings','open_items')},ensure_ascii=False))


if __name__ == '__main__':
    main()
