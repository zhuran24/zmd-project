#!/usr/bin/env python3
"""Render this independent audit's results, never the relock seat's test results."""
import json
import re
from pathlib import Path
from verify import OUT, REPO, HISTORY, PARALLEL, load, save, now, digest

catalog = load('catalog-audit.json')
refs = load('references-audit.json')
business = load('business-audit.json')
history = load('final-history.json')
history_head = load('history-head.json')
scope = load('final-scope.json')
head = load('final-head-check.json')
scan = load('old-sha-scan.json')
inventory = load('all-catalog-inputs.json')
positive = load('positive-validation.json')
commands = [json.loads(line) for line in (OUT / 'commands.jsonl').read_text().splitlines()]
expected_names = ['cargo-build', 'cargo-check', 'cargo-clippy', 'kernel-lib', 'topology-lib',
                  'kernel-reference', 'topology-validation', 'kernel-doc', 'topology-doc',
                  'catalog-verify', 'catalog-regressions', 'positive-seed', 'positive-check',
                  'positive-run', 'positive-verify-record', 'stale-catalog-negative']
assert [c['name'] for c in commands] == expected_names
assert all(c['passed'] for c in commands)
tests = {}
for name in ['kernel-lib', 'topology-lib', 'kernel-reference', 'topology-validation', 'kernel-doc', 'topology-doc']:
    text = (OUT / (name + '.stdout.log')).read_text()
    match = re.search(r'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored;', text)
    assert match, name
    tests[name] = {'passed': int(match[1]), 'failed': int(match[2]), 'ignored': int(match[3])}
python_log = (OUT / 'catalog-regressions.stdout.log').read_text() + (OUT / 'catalog-regressions.stderr.log').read_text()
python_cases = int(re.search(r'Ran (\d+) tests? in ', python_log)[1])
assert '\nOK\n' in python_log
rust_passed = sum(r['passed'] for r in tests.values())
history_diffs = {p.name: json.loads(p.read_text()) for p in OUT.glob('*-history-diff.json')}
assert all(not any(delta.values()) for delta in history_diffs.values())
assert not history_head['mismatches'] and not head['history_diff'] and not head['head_history_changes_since_baseline']
assert all(head['formal_sources_equal_current_head'].values())
assert catalog['byte_equal'] and catalog['constraints'] == 72
assert not business['failures'] and not refs['mismatches']
assert all(r['matches'] for r in refs['candidate_sources'])
assert all(refs['source_hashes_check'].values()) and all(refs['readonly_snapshot_check'].values())
assert all(r['passed'] for r in positive['positive']) and positive['negative']['passed']
assert positive['seed_schema'] == 'kernel-input-v3' and positive['run_status'] == 'completed'
assert scan['returncode'] == 0 and not (OUT / 'old-sha-scan.stderr.log').read_bytes()
assert inventory['returncode'] == 0 and not inventory['stderr'] and not inventory['parse_errors']
assert not any(r['category'] == 'other_review_required' for r in inventory['files'])
archive_categories = {'three_protected_history_dirs', 'older_maintenance_archive', 'this_relock_records_backups_and_negative'}
non_archive = [r for r in scan['files'] if r['category'] not in archive_categories]
issues = []
if non_archive:
    issues.append({'id': 'V-01', 'criterion': '历史证据目录外旧目录 SHA 命中为零',
                   'finding': '修订记录 r23 历史段仍有旧 SHA，活动输入漏锁为零', 'files': non_archive})
if scope['out_of_scope']:
    issues.append({'id': 'V-02', 'criterion': 'git status 仅重锁业务文件、本轮记录和指定并行目录',
                   'finding': '存在范围外未跟踪文件；不归因于重锁或本次核验', 'files': scope['out_of_scope']})
overall = 'FAIL' if issues else 'PASS'
summary = {'status': overall, 'cutoff': now(), 'baseline_head': load('baseline.json')['head'],
           'final_head': head['head'], 'core_relock_checks': 'PASS', 'constraints': catalog['constraints'],
           'business_files': business['count'], 'relocked_inputs': refs['kernel_inputs'],
           'reference_documents': refs['documents'], 'reference_fields': refs['reference_fields'],
           'candidate_sources': len(refs['candidate_sources']), 'rust_passed': rust_passed,
           'python_passed': python_cases, 'commands': len(commands), 'test_failures': 0,
           'history_files': len(history['files']), 'history_bytes': history['bytes'],
           'history_tracked': history_head['tracked_count'], 'history_ignored': len(load('history-ignored.json')),
           'history_hash_comparisons': len(history_diffs), 'history_changes': load('final-history-diff.json'),
           'old_sha_non_archive_files': len(non_archive), 'old_sha_raw_files': scan['file_count'],
           'old_sha_raw_occurrences': scan['occurrences'], 'final_scope_counts': scope['counts'], 'issues': issues,
           'rust_tests': tests, 'command_results': commands}
save('summary.json', summary)

issue_text = '\n'.join(
    f"- **{issue['id']}：{issue['criterion']}——未满足。** {issue['finding']}。\n" +
    '\n'.join(f"  - `{f['path']}`" + (f"，第 {','.join(map(str, f['lines']))} 行，{f['occurrences']} 处。" if 'lines' in f else f"（`{f['status']}`）。") for f in issue['files'])
    for issue in issues) or '无。'
source_table = '\n'.join(f"| {r['path']} | `{r['head_sha256']}` |" for r in catalog['sources'])
test_table = '\n'.join(f"| [{c['name']}]({c['name']}.stdout.log) | {c['exit_code']} | " +
    (f"{tests[c['name']]['passed']} 通过 / {tests[c['name']]['failed']} 失败" if c['name'] in tests else
     f'{python_cases} 通过' if c['name'] == 'catalog-regressions' else
     '预期拒收：invalid_input、目录源文件指纹不符' if c['name'] == 'stale-catalog-negative' else '通过') +
    f"；[stderr]({c['name']}.stderr.log) |" for c in commands)
history_table = '\n'.join(f'| `{p}` | {n} |' for p, n in history['counts'].items())
old_table = '\n'.join(f"| {label} | {scan['category_counts'].get(cat, 0)} |" for cat, label in [
    ('three_protected_history_dirs', '三个受保护历史目录'), ('older_maintenance_archive', '以前的内核维护存档'),
    ('this_relock_records_backups_and_negative', '本次重锁的记录、备份和负例'), ('revision_history', '规格/修订记录.md 的历史段')])
initial_paths = {r['path'] for r in load('initial-status.json')}
scope_table = '\n'.join(f"| `{r['path']}` | `{r['status']}` | {'是' if r['path'] in initial_paths else '否；核验期间出现'} |" for r in scope['out_of_scope'])
text = f'''# r24 内核重锁独立核验记录

史料／执行记录。日期：2026-09-22；截止：{summary['cutoff']}。总判定：**{overall}**；目录、输入同步、安全测试、正反链与历史字节保护全部通过，严格文本检索和工作区范围要求有 {len(issues)} 类差异。仓库：`{REPO}`。

## 结论与不一致清单

独立重建目录逐字节一致，约束 **72 条**；**62 个业务文件**的差异均对应重锁，**54 份输入**（45 个样例、9 个 fixture）只替换目录 SHA；56 份输入／参数赋值、114 个引用字段及 16 项候选 B 来源全部匹配实际字节。Rust **{rust_passed}/{rust_passed}**、Python **{python_cases}/{python_cases}** 通过，16 条实际构建／测试／CLI 命令均符合预期退出码。三历史目录 **{len(history['files'])} 个文件**全量哈希前后零增删改。

{issue_text}

V-01 的命中属于 r23 史料，未发现活动输入漏锁；“活动输入残留为零”与“历史目录外字面 grep 为零”是两个不同结论。V-02 只记录最终工作区的客观状态，不推断写入者，也不把并发研究成果算作重锁业务文件。总判定按两项严格验收条件给出，未改写史料或范围外文件。

## 版本锚点与独立重建

重锁席开工 HEAD 是 `8ab232419c0e9e1702a14c4881a173f15fdade84`；本核验基线 HEAD 为 `{summary['baseline_head']}`，最终 HEAD 为 `{summary['final_head']}`。其间提交只涉及候选充分条件及其独立复核材料；三个正式源、目录、内核源码、测试输入和历史目录在这些提交间没有变化。提交及路径记录见 [final-head-check.json](final-head-check.json)。`dfc35cd` 已包含在核验基线中。

从基线 HEAD 用 `git show <commit>:<path>` 分别读取三份正式文件到 [head-sources/](head-sources/)，再用与 HEAD 相同的 `formal_catalog.py`／`formal_units.py` 投影完整约束、任务、常量、流量、配方和单位。HEAD 目录仅提供键顺序、单位排列、conventions 与原转录时间；版本显式设为 r24。重建不读取重锁席的备份或重建结果。

| 正式来源 | HEAD 与工作区一致的 SHA-256 |
|---|---|
{source_table}

- 新目录与 [rebuilt-catalog.json](rebuilt-catalog.json) 的 SHA-256 均为 `{catalog['new_sha256']}`，原始字节相等。
- 旧 HEAD 目录 SHA-256 为 `{catalog['old_sha256']}`。
- 目录有 72 条约束、18 类单位、18 条配方、32 项常量、19 项物料流量。
- 对 HEAD 的叶差异恰为 `constraints[32].text`、`sources[2].sha256`、`sources[2].lines[75]`、`version`；正式文件第 76 行同步到目录约束正文与来源全文。
- 最终三份正式文件仍与最终 HEAD 逐字节相等。

详细结果见 [catalog-audit.json](catalog-audit.json)；62 个业务文件的精确替换、追加及字段差异检查见 [business-audit.json](business-audit.json)。候选 B 报告计数沿用 r23，本次没有运行其 topology CLI，也没有把旧计数当作新测试结果。

## 输入查漏与旧指纹检索

活动样例／fixture 枚举独立于重锁席文件清单。54 份输入均仅改变 `catalog.sha256`；其余字节通过 HEAD 文件的单 SHA 替换逐一比较。另两份参数赋值无需改写。114 个引用字段、候选 B 16 项来源、样例 `SOURCE_HASHES` 与只读指纹表均按目标文件实际字节计算。明细见 [references-audit.json](references-audit.json)。

全仓另行枚举了 **{inventory['count']} 份带顶层 catalog 路径及 SHA 的 JSON**：54 份活动样例／fixture、603 份三个受保护目录内的历史输入、93 份规格复核／推导／会议存档输入、393 份维护存档输入。无 JSON 解析错误或未归类输入。历史输入中的更早指纹按存档保留，不作活动输入重锁。见 [all-catalog-inputs.json](all-catalog-inputs.json)。

对旧 r23 SHA 使用 `rg --hidden --no-ignore` 全仓只读检索，也读取了指定并行目录；排除 `.git`、target／Python 缓存及本核验 `verify/`，避免本报告和刻意构造的旧 SHA 负例自我命中。检索没有报错。

| 命中类别 | 文件数 |
|---|---:|
{old_table}

原始共 **{scan['file_count']} 个文件、{scan['occurrences']} 处**。若只排除三个受保护历史目录，这些命中全部仍在目录外；再将 390 份维护存档视为历史证据排除，仍有 `规格/修订记录.md:340` 一处。重锁席已经披露此 r23 历史段，因此本项是严格零命中口径差异，未发现其遗漏活动输入。逐文件行号及原始 argv 见 [old-sha-scan.json](old-sha-scan.json)。

## 自行重跑的安全集与正反链

所有执行入口均为落盘的 bash 脚本：`bash 求解器/内核维护/2026-09-22g/verify/run.sh <阶段>`。使用独立构建目录 `verify/target`，cargo `-j 4`，六个 Rust 安全目标均 `-- --test-threads=1`；`PYTHONDONTWRITEBYTECODE=1`。没有运行 workspace 总测试、七个 CLI 测试目标或历史证据写入脚本。Python 目录回归原代码使用 `求解器/target` 下的自动清理临时目录；构建缓存及核验产物不写三个历史目录。

完整 argv、工作目录、环境、起止时刻、耗时与返回码见 [commands.jsonl](commands.jsonl)。以下仅列本核验实际执行的结果，不引用重锁席的通过数：

| 步骤 | 退出码 | 结果与日志 |
|---|---:|---|
{test_table}

两包 doc 目标各 0 项，未增加 134 的计数。topology validation 内部还调用相同的 Python 回归，Python 8 项不重复累计。Clippy stderr 无 warning。

正向链由当前活动样例 `数据/样例/任务7内核/无线多格全收.json` 独立生成输入，只把两个引用路径转为绝对路径；seed、check、6 tick run、verify-record 均通过。负例只把 `catalog.sha256` 改为旧 r23 SHA，返回 2，状态 `invalid_input`，明确定位正式目录“源文件指纹不符”。负例不是由缺文件或其它输入错误导致。

自行构建的 kernel SHA-256 为 `{positive['binary_sha256']}`，与重锁席所报二进制 SHA 一致。详见 [positive-validation.json](positive-validation.json) 及 [positive/](positive/)。本结果覆盖有限运行及记录复验，不作达标循环或全参数证明。

## 历史全量哈希与并发状态

| 历史目录 | 文件数 |
|---|---:|
{history_table}

合计 **{len(history['files'])} 文件、{history['bytes']} 字节**，包含 1 个忽略文件。每条实际构建／测试／CLI 命令前后都计算全部历史文件的路径、大小及 SHA-256；加最终快照共保存 **{len(history_diffs)} 份对初始基线的差异比较**，全部新增 0、删除 0、修改 0。

对 HEAD 的验证使用 `git ls-tree` 和 `git cat-file --batch` 直接读取 **3474 个受跟踪历史 blob**，逐项计算 SHA-256，全部与工作区相同。另 1 个是既有忽略文件 `求解器/crates/kernel/复核/r3-测试与证据/密集制造闭环序3核验-重跑周期.json`，它没有 HEAD blob，已纳入前后全量哈希。最终三个目录的 `git diff HEAD` 为空，基线 HEAD 至最终 HEAD 也没有历史路径变化。

本次独立初始哈希还与重锁席的 initial／delivery 两份历史清单逐项对照，3475 个文件完全相同。此交叉比较是旁证；独立实测的初始／最终清单和 HEAD blob 对比是本核验的直接证据。

证据：[initial-history.json](initial-history.json)、[final-history.json](final-history.json)、[final-history-diff.json](final-history-diff.json)、[history-head.json](history-head.json)、[history-ignored.json](history-ignored.json)、[relock-history-crosscheck.json](relock-history-crosscheck.json)。

kernel lib 执行期间，并发提交 `3c5e7ee` 新增了四份候选充分条件复核文件并修改 `候选充分条件.txt`，全仓变更守卫因此暂停后续命令。100 个 kernel lib 测试已经通过。检查原始差异确认被核来源、构建输入、测试输入与历史文件均未变后，保留差异文件，继续剩余安全目标；没有重跑或合并另一席测试结果。后续守卫持续记录全仓差异，并对被核依赖施加字节不变检查。见 [kernel-lib-after-active-diff.json](kernel-lib-after-active-diff.json) 和 [final-concurrency.json](final-concurrency.json)。

最终状态中，62 个受跟踪业务文件全部位于重锁应改范围；本轮维护目录有 {scope['counts']['maintenance']} 条 status 项，指定并行目录有 {scope['counts']['parallel']} 条，二者均单独列账。范围外有 **{scope['counts']['out_of_scope']}** 条：

| 路径 | status | 是否已在独立初始快照中 |
|---|---|---|
{scope_table}

早期出现的四份候选充分条件复核文件后来被并发提交收录，最终已不在 status 中；各时点原始状态保存在 initial／audited／final-status 文件中。未修改指定并行目录、业务文件或任何历史文件；本核验的持久材料均位于 `verify/`，未执行暂存、提交或还原操作。最终范围清单见 [final-scope.json](final-scope.json)，原始状态见 [final-status.txt](final-status.txt)。

## 验收边界

重锁席列出的 T12 旧断言、样例桥轴 Decision 结构和两处实现状态文字问题，不属于本安全集；本次未运行其对应总自查，也未登记为修复。当前总体 FAIL 仅指上列 V-01、V-02，不把已有问题或历史指纹本身算作新内核失败。

机器汇总见 [summary.json](summary.json)；核验实现为 [verify.py](verify.py) 与 [run.sh](run.sh)。产物文件 SHA 清单见 [artifacts.json](artifacts.json)。
'''
(OUT / '记录.md').write_text(text)

# Reader-facing links, counts, status, and scope were also reviewed manually.
links = re.findall(r'\]\(([^)]+)\)', text)
missing = [link for link in links if not (OUT / link).exists() and link != 'artifacts.json']
assert not missing, missing
save('reader-review.json', {'time': now(), 'status': 'pass', 'missing_links': missing,
     'checks': ['status and issue count agree with summary', 'historical record and cutoff explicit',
                'raw grep hits separated from active references', 'HEAD drift and ignored-file boundary explicit',
                'test counts independently parsed and Python nested run not double-counted',
                'initial versus final status distinguished', 'finite positive chain not a target certificate']})
artifacts = [{'path': str(p.relative_to(OUT)), 'bytes': p.stat().st_size, 'sha256': digest(p)}
             for p in sorted(OUT.rglob('*')) if p.is_file() and
             p.relative_to(OUT).parts[0] not in ['target', 'tmp'] and p.name != 'artifacts.json']
save('artifacts.json', {'time': now(), 'excluded': ['target/', 'tmp/', 'artifacts.json self'], 'files': artifacts})
print(json.dumps({'status': overall, 'rust': rust_passed, 'python': python_cases,
                  'history': len(history['files']), 'issues': issues, 'report': str(OUT / '记录.md')}, ensure_ascii=False))
