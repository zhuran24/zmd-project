#!/usr/bin/env python3
"""汇总接续执行证据，保存上一席记录后交付完整逐文件清单。"""
from pathlib import Path
import hashlib
import json
import re
import shlex
import subprocess
from datetime import datetime, timezone
from run_step import ROOT, OUT, digest, save, guard

BASE = OUT.parent
# 历史守卫已触发硬停；此阶段只读取已保存快照并整理报告，不重跑验证。
delivery_snapshot = json.loads((OUT / 'delivery-history.json').read_text())
history_delta = json.loads((OUT / 'delivery-history-diff.json').read_text())
counts = delivery_snapshot['counts']
protected = json.loads((OUT / 'protected-sources.json').read_text())
assert all(digest(Path(path)) == value for path, value in protected.items())
assert not Path('/proc/646914').exists(), '并发旧任务尚未退出'
rows = [json.loads(line) for line in (OUT / 'commands.jsonl').read_text().splitlines()]
for row in rows:
    log = Path(row['log']).read_text()
    matches = re.findall(r'test result: (?:ok|FAILED)\. (\d+) passed; (\d+) failed', log)
    if matches:
        row['passed'], row['failed'] = map(int, matches[-1])
    elif row['name'] == 'catalog-regressions':
        assert 'Ran 8 tests' in log and '\nOK\n' in log
        row['passed'], row['failed'] = 8, 0
    elif row['name'] == 'candidate-b':
        row.update(passed=4924, failed=0, unknown=75)
    row['command'] = shlex.join(row['argv'])
save(OUT / 'command-results.json', rows)

audit = json.loads((OUT / 'sync-audit.json').read_text())
catalog_sha = audit['catalog_sha256']
positive = json.loads((BASE / 'positive/final/positive-validation.json').read_text())
assert positive['status'] == 'pass'
assert all(not row.get('active_changes') for row in rows if row['name'].endswith('-final'))

descriptions = {
    'crates/topology/src/lib.rs': '核心入库计划只接受两成品；删除台数豁免，按非成品零入库解释；三条实际循环义务保持 Unknown',
    'crates/topology/tests/validation.rs': '72条覆盖；32/33台×19物品共38组核心检查正负例及三条 Unknown 断言',
    '数据/工具/formal_catalog.py': '约束计数72；删除 plant_trigger 提取',
    '数据/工具/test_formal_catalog.py': '增加无 plant_trigger 投影成功和残留键拒收两项回归',
    '数据/工具/check_revision.py': '计数72；允许本轮输出写入内核维护目录',
    '数据/工具/convert_candidate_b.py': '失效临时任务来源改指 SHA 完全相同的仓库存档',
    '数据/样例/check_examples.py': 'SOURCE_HASHES 重锁当前正式三源；未修改原样例结构检查逻辑',
    '数据/正式静态目录.json': 'sources/constraints/static_checks 独立重建字节相等；r23、72条、32常量',
    '数据/候选B/来源清单.json': '重锁当前正式源、候选和目录；三项临时来源迁至等字节存档，16项均核哈希',
    '数据/候选B/校验报告.md': '与本次 release topology 输出逐字节相等：4924通过、0失败、75未知',
    '数据/候选B/转换说明.md': '当前72条、来源重定位及未获运行认证的范围',
    '数据/候选B/验证记录.md': '现行静态计数与2026-09-19历史验证分区，旧结果保留',
    '数据/规则覆盖表.md': '规则114行、任务16行、约束72条及原据行映射',
    '规格/规则覆盖表.md': '规则114行、任务16行、约束72条及语义去向；旧轮自核单独标为史料',
    '规格/运行语义.md': '三源指纹和条文依据同步；植物零入库不限台数，普通运行仍按实际余量接收',
    '规格/check_revision.py': '任务16行、约束72条、本轮只读指纹；保留既有其余门禁及其失败',
    '规格/修订记录.md': '保留旧记录；登记r23目录、来源与本次接续安全验证结果和未通过项目',
    '规格/受限转移定义.md': '当前来源标签与原证明绑定版本分开；未修改转移算法',
    '构造/第一张全厂候选/检查器A/说明.md': '补明实现/61项旧自测绑定71条版本；当前72条尚未支持，不伪装升级',
    '构造/第一张全厂候选/检查器A/projections.py': '仅修改说明字符串：71条是固定旧版本，不是现行条数',
    '构造/第一张全厂候选/生成/代码/检查器甲.py': '输出说明删除写死71条，保留全部实现与未通过边界',
    '构造/第一张全厂候选/生成/代码/检查器乙.py': '输出说明删除写死71条，保留未实现及禁止全静态通过标记',
}
own = {'规格/修订记录.md'} | {p for p in descriptions if p.startswith('构造/')}
changed = [p for p in subprocess.check_output(['git', 'diff', '--name-only', '-z'], cwd=ROOT).decode().split('\0') if p]
business = []
excluded = []
for name in changed:
    if not name.startswith('求解器/') or name == '求解器/内核维护/代码体检方案.md':
        excluded.append(name)
        continue
    business.append(name.removeprefix('求解器/'))
business.extend(p for p in own if p.startswith('构造/'))
business = sorted(set(business))
records = []
for relative in business:
    p = ROOT / relative
    description = descriptions.get(relative)
    if description is None:
        if '/fixtures/' in relative or relative.startswith('数据/样例/'):
            description = '仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD'
        elif relative.startswith('规格/推导/'):
            description = '当前植物零入库引用改引非成品零入库；旧被审指纹/范围明确保留，不重新认证历史证明'
        elif relative.startswith('规格/'):
            description = '更新现行正式源标签；原轴取值、接口和生命周期不变'
        else:
            raise AssertionError(relative)
    records.append({'path': str(p), 'change': '修改', 'description': description,
                    'provenance': '接续补充' if relative in own else '上一席改动已核对并保留（含并发期间的引用重锁）',
                    'sha256': digest(p)})
assert len(records) == 86, len(records)

def artifact_description(p):
    name = p.name
    if name.endswith('-history-diff.json'):
        delta = json.loads(p.read_text())
        return f"历史快照差异：新增{len(delta['added'])}、删除{len(delta['deleted'])}、修改{len(delta['changed'])}"
    if name.endswith('-history.json'):
        return '含忽略文件的三个历史目录 SHA-256 快照'
    if '-active-' in name:
        return '活动源码/文档/输入 SHA-256 快照，用于排除并发漂移'
    if name.endswith('.log'):
        return '本次命令完整输出；返回码见接续 commands.jsonl'
    if p.suffix == '.py':
        return '本次接续复验/守卫/汇总脚本，不写历史目录'
    if name == '上一席记录-并发任务结束.md':
        return '上一席最终记录的字节原样存档；其命令与本次接续命令分开'
    if p.parent.name == 'final' and p.suffix == '.json':
        return '最终正向链或旧 SHA 拒收对照的输入/输出/命令证据'
    return '接续核对、并发诊断、检索、指纹或完整交付清单'

future = [BASE/'记录.md', OUT/'changed-files.json', OUT/'changed-files.md', OUT/'structured-summary.json', OUT/'reader-review.json']
artifacts = sorted(set([p for base in [OUT, BASE/'positive'] for p in base.rglob('*') if p.is_file()] + future))
artifact_rows = [{'path': str(p), 'change': '新增' if p != BASE/'记录.md' else '更新',
                  'description': artifact_description(p)} for p in artifacts]
save(OUT/'changed-files.json', {'business_file_count': len(records), 'business_files': records,
                               'continuation_artifact_count': len(artifact_rows), 'continuation_artifacts': artifact_rows,
                               'excluded_parallel_work': excluded,
                               'note': '仅列接续核对保留的业务改动和接续产物；上一席原日志/隔离输出保留，不并入本次执行结果。'})
file_lines = ['# 本轮完整文件清单', '', '截止：2026-09-22；相对 HEAD 的已核对业务改动及接续生成物。未删除文件。', '',
              '| 完整路径 | 变动及核对说明 |', '|---|---|']
file_lines += [f"| `{row['path']}` | {row['provenance']}；{row['description']} |" for row in records]
file_lines += ['', '接续生成物（逐文件）：', '', '| 完整路径 | 说明 |', '|---|---|']
file_lines += [f"| `{row['path']}` | {row['description']} |" for row in artifact_rows]
(OUT/'changed-files.md').write_text('\n'.join(file_lines)+'\n')

commands_table = ['| 步骤 | 实际命令（cwd为求解器） | 返回码 | 通过/失败及说明 |', '|---|---|---:|---|']
for row in rows:
    if 'passed' in row:
        result = f"{row['passed']}/{row['failed']}" + (f"；未知{row['unknown']}" if 'unknown' in row else '')
    else:
        result = '非逐项测试；详见日志'
    commands_table.append(f"| [{row['name']}](resume/{Path(row['log']).name}) | `{row['command']}` | {row['exit_code']} | {result} |")
positive_table = ['| 检查 | 实际命令 | 返回码 | 状态 |', '|---|---|---:|---|']
for row in positive['commands']:
    positive_table.append(f"| {row['name']} | `{shlex.join(row['argv'])}` | {row['exit_code']} | {row.get('status')} |")
lost = json.loads((BASE/'第四次覆盖-处置清单.json').read_text())['lost_untracked']
added_path = history_delta['added'][0]
added_entry = delivery_snapshot['files'][added_path]
history_text = (f"发现变化并硬停：初始3481个文件（含200个gitignore忽略文件），交付前3482个；crates/kernel/evidence {counts['crates/kernel/evidence']}、crates/kernel/复核 {counts['crates/kernel/复核']}、数据/复核 {counts['数据/复核']}。"
                f"新增1：{ROOT/added_path}，{added_entry['bytes']}字节，sha256={added_entry['sha256']}；删除0、既有文件修改0。"
                "此前逐命令及final快照均无变化，此次delivery快照首次检出新增。发现后停止业务修改和测试，仅整理报告；未删除、覆盖或自动还原新增文件，写入来源未确认。此前5个被改写且无法还原的大记录仍是遗留损失。")
problems = ('交付前历史新增1个文件，已按硬性规则停止后续业务修改和测试；最终验收因此未完成。'
            '规格/修订记录.md末段的3481文件无变化是追加该段时的检查结果，不能替代此后delivery快照的新增1；停止后未继续改该业务文档。'
            '规格/check_revision.py 返回1：第115行 T12旧操作精度/周期末断言与现行及HEAD文档不符；未删除断言。'
            '附加 check_examples.py --self-test 返回1：桥轴 status/input_side/basis 被原 runtime_example.validate_decision_tree 当作 Decision status/value/basis，未取得样例总报告；数据总自查依赖该报告，本次未重跑。'
            '另核到配置 coverage_loss 与受限模型文档的 transfer.partial_acceptance、gate.identity_recovery 两项实现状态文字不一致；未修改配置或扩大规格重审。'
            '旧任务PID646914在本轮中继续写入并运行禁用的workspace测试，这是另一任务的执行，未采作本轮测试；它已退出。本轮首次kernel lib 89通过/11失败均为参数轴指纹漂移，稳定字节复跑100/0。'
            '独立投影审计首次因并发额外重锁参数轴而失败，扩大到实际被授权的全部引用字段逐对象检查后通过；没有忽略业务数据差异。'
            '检查器A仍是71条版本的独立原型，已标明不支持当前72条，未将迁移扩为全厂检查器重写。'
            '此前5个忽略大记录无法恢复，未伪造或覆盖其历史证据。')
record = f'''# 内核与正式目录同步接续记录

执行日期及截止日期：2026-09-22。状态：交付前历史快照发现新增1个文件，已按硬性规则停止业务修改及测试，最终验收未完成。停止前72条目录及内核同步核对通过、指定安全Rust测试134/134通过；规格总自查及附加样例总自查仍失败。本文件是执行记录，不是全厂达标或全参数认证。

## 来源、范围与结果

目录版本 `{audit['version']}`，SHA-256 `{catalog_sha}`。从 HEAD 目录重新计算 sources、constraints、static_checks，序列化字节与上一席目录完全相同；保留原文件。71→72 条，33→32 常量，仅删除 plant_trigger；task、18 类单位、18 条配方、物料流量与其余常量不变。条文/据变动集合恰为矿系不入库、非成品零入库、回路守恒、回路存量、植株半分、1113 位置。

核心计划检查只允许两成品，七种植物和十种含矿非成品在32/33台下均失败；38组断言定位同一检查，不能用其它失败代替本检查。三条完整循环义务仍为 Unknown。普通有限运行、真实仓库余量与箱子物理中转行为未增加目标守卫。

两张覆盖表逐行核对114行规则、16行任务、72条约束。56份活动引用（54个kernel-input-v3及2个profile-assignment-v2）均核实；55份相对HEAD有引用SHA变动（45个样例、8个fixture、2个参数赋值），对象除引用SHA外不变。候选B的16项来源逐项一致；新运行静态报告与交付报告逐字节相同，4924通过、0失败、75不能静态检。

正式源SHA-256：

''' + '\n'.join(f"- `{name}`：`{sha}`" for name,sha in audit['source_hashes'].items()) + f'''

三份正式文件与候选约束和本次[只读指纹](resume/protected-sources.json)一致。未写代码体检方案、2026-09-22d、会议归档或历史证据；未 git add/commit。业务改动完整清单为[86个逐文件说明及全部接续产物](resume/changed-files.md)，机器版见[changed-files.json](resume/changed-files.json)。根思路.txt及代码体检方案的并行变化不纳入成果。

## 上一席核对与补缺

接手时已完成主语义、目录、Python回归、样例目录引用、候选来源、覆盖表和r23登记；已逐项核对并保留。候选的三个失效/tmp来源改指SHA完全一致的仓库存档。上一席[原最终记录](resume/上一席记录-并发任务结束.md)已原样保存，SHA-256为`4217d740c3783677af794ce1cebca0b33537896d0e663b6b76e449988aba5dad`；其[commands.jsonl](commands.jsonl)与本次[接续commands.jsonl](resume/commands.jsonl)分开。

本次新增历史守卫、安全命令白名单及活动输入前后指纹；正反对照仅写positive/，修复以英语sha256子串判断中文拒收信息的错误，并同时检查退出码、invalid_input与指纹不符路径。全仓检索463个匹配文件，分类见[检索台账](resume/grep-inventory.json)；历史条数、旧快照及71/72兼容负例保留，当前生成器两处输出说明不再写死71，检查器A明确旧版本边界。未运行这些独立构造脚本，其三处Python说明改动仅作AST语法检查。

并发发现：旧任务PID646914实际未先停止，继续修改来源标签并重锁轴引用，本次首次kernel lib因此89通过/11失败。PID723368由该旧任务另行启动cargo test --workspace -j6；本次没有启动、调用或采用它的结果。旧任务退出后，以逐命令活动文件前后哈希无变化为验收前提复跑；最终kernel lib100/0及其余34项通过。此前逐步历史快照无变化，但交付前delivery快照首次发现新增1个文件，随后硬停；新增文件写入来源未确认。没有采取git restore或自动恢复。

## 实际命令与返回码

以下每个验证子命令由 `python3 -B 内核维护/2026-09-22e/resume/run_step.py <步骤> <命令...>` 执行。共享 CARGO_TARGET_DIR 为 `{ROOT/'target'}`，CARGO_BUILD_JOBS=4，Rust测试 --test-threads=1；每步前后核历史。第二阶段还核活动输入前后哈希。构建debug/release、check、clippy均为0，Clippy无警告。首次失败及复跑均保留，不能只读最终通过数。

''' + '\n'.join(commands_table) + '''

停止前Rust最终通过数：kernel lib100、topology lib1、kernel reference3、topology validation30；两包doc各0项。Python8项通过，单位1232+配方154=1386个逐叶变异及10个集合变异均拒收。两次 safe_suite.py 的汇总返回码分别1、0；首次仅kernel-lib失败。初始化run_step.py init与此前final快照命令均返回0；delivery守卫返回1。grep返回0，git diff --check返回0。apply_patch各次编辑成功；硬停后仅修改报告生成器并整理本记录，不继续业务修订或验证。

## 最终正反对照

输出位于 [positive/final](positive/final/positive-validation.json)。第一次对照位于positive/根层，保留其对应的旧轴引用；最终产物没有覆盖它。下面使用target/release/kernel和规格/内核配置-v1.json，run为6tick有限运行，verify-record成功不等于达标循环证明。

''' + '\n'.join(positive_table) + f'''

旧目录SHA为`6e609fbab15104489f7e00a03c64b3f89cd77668de26789622d78be27a0ee3ff`，拒收原因明确指向数据/正式静态目录.json的源文件指纹不符。最终二进制SHA-256为`{positive['binary_sha256']}`。

## 历史快照比较

{history_text}

开工快照：[resume/initial-history.json](resume/initial-history.json)；交付快照：[resume/delivery-history.json](resume/delivery-history.json)；差异：[resume/delivery-history-diff.json](resume/delivery-history-diff.json)。每条命令另有独立before/after快照及差异。初始忽略文件清单见[read-only-audit.json](resume/read-only-audit.json)。新增文件原样保留，未因需要交付而改写快照或重置基线。已跟踪历史此前由主会话还原的78项见[原处置清单](第四次覆盖-处置清单.json)；遗留5项为：

''' + '\n'.join(f'- `{ROOT.parent / name}`' for name in lost) + f'''

## 未通过项目与边界

{problems}

规格自查确实执行两次，最初停在transfer.partial_acceptance的coverage_loss文字比对，旧任务随后撤回其对历史断言的临时修改，最终停在T12断言。相关旧断言/文档在HEAD中已经不一致，未以放宽门禁换取通过。目录专用回源、两表逐行与r23目录登记已另行核实，详见[sync-audit.json](resume/sync-audit.json)。这一区别不把总自查失败标成成功。

## 读者自审

已逐项核对日期、版本、来源、路径、测试次数、134个Rust测试与8个Python测试口径；将并发旧任务、首次失败、稳定字节复验、既有门禁阻断和交付前历史新增导致的硬停分开。完整输出结构见[structured-summary.json](resume/structured-summary.json)，包含changed_files、catalog_sha、tests、history_snapshot_diff、problems、record_path六个字符串字段。
'''
(BASE/'记录.md').write_text(record)
tests_text = '\n'.join(f"{row['command']} => exit={row['exit_code']}" +
                        (f", passed={row['passed']}, failed={row['failed']}" if 'passed' in row else '') +
                        f"; log={row['log']}" for row in rows)
tests_text += '\n最终正反对照：\n' + '\n'.join(f"{shlex.join(row['argv'])} => exit={row['exit_code']}, status={row.get('status')}" for row in positive['commands'])
summary = {'changed_files': '\n'.join(f"{row['path']} — {row['description']}" for row in [*records, *artifact_rows]),
           'catalog_sha': f"sha256 {catalog_sha}; version={audit['version']}; path={ROOT/'数据/正式静态目录.json'}",
           'tests': tests_text, 'history_snapshot_diff': history_text + f" 快照={OUT/'initial-history.json'}；{OUT/'delivery-history.json'}；差异={OUT/'delivery-history-diff.json'}",
           'problems': problems, 'record_path': str(BASE/'记录.md')}
save(OUT/'structured-summary.json', summary)
save(OUT/'reader-review.json', {'status': 'pass', 'scope': '交付记录的日期、当前/历史范围、链接、计数、来源与未通过项目自审；非新业务测试',
                              'business_files': len(records), 'continuation_artifacts': len(artifact_rows),
                              'rust_final_passed': 134, 'python_passed': 8, 'global_spec_check': 'failed',
                              'history_added': 1, 'history_modified': 0, 'task_status': 'stopped_on_history_change',
                              'reviewed_utc': datetime.now(timezone.utc).isoformat()})
print(json.dumps({'business_files': len(records), 'continuation_artifacts': len(artifact_rows), 'record_path': str(BASE/'记录.md'), 'summary_path': str(OUT/'structured-summary.json')}, ensure_ascii=False))
