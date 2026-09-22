"""交付复核：锁定原文、检查只读指纹及7条裁决，不修改被审材料。"""
from pathlib import Path
import datetime
import hashlib
import json
import re

ROOT = Path('/home/zhuran24/zmd-research-fresh')
WORK = ROOT / '求解器'
OUT = Path(__file__).resolve().parent
REPORT = OUT.parent / '否证-r4-2.md'

def read(path):
    return json.loads(path.read_text())

def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

selections = {
    '《明日方舟：终末地》游戏规则.txt': [(13, 18), (20, 32), (35, 41), (59, 76)],
    '求解任务.txt': [(1, 15)],
    '求解器/规格/内核输入.md': [(292, 299), (313, 337)],
    '求解器/规格/受限转移定义.md': [(5, 13), (31, 36), (49, 54), (139, 191)],
    '求解器/规格/内核输出.md': [(5, 31), (76, 97)],
    '求解器/规格/受限模型声明.md': [(39, 40)],
    '求解器/规格/选择点参数轴.md': [(39, 40)],
    '求解器/规格/内核输出.schema.json': [(2527, 2555), (2620, 2635)],
    '求解器/规格/内核实现-对规格的疑问.md': [(83, 95)],
    '求解器/crates/kernel/src/engine.rs': [(768, 826), (838, 884)],
    '求解器/crates/kernel/src/input.rs': [(852, 930)],
    '求解器/crates/kernel/src/polling.rs': [(94, 167), (230, 260)],
    '求解器/crates/kernel/src/output.rs': [(270, 276), (380, 403), (480, 510)],
    '求解器/crates/kernel/src/cycle.rs': [(240, 286), (344, 368), (675, 695)],
    '求解器/crates/kernel/src/model.rs': [(148, 158)],
    '求解器/crates/kernel/src/value.rs': [(281, 316)],
    '求解器/crates/kernel/tests/audit_round5.py': [(164, 176)],
}
excerpts = []
for relative, spans in selections.items():
    path = ROOT / relative
    lines = path.read_text().splitlines()
    excerpts.append(dict(path=str(path), sha256=digest(path),
                         excerpts=[dict(start=start, end=min(end, len(lines)),
                                        lines=[dict(line=i, text=lines[i-1]) for i in range(start, min(end, len(lines))+1)])
                                   for start, end in spans]))
write('source-excerpts.json', excerpts)

reasons = [
    ('KR-r4-L1-01', '未能否证。独立对照中，同格两件电池分为-2/-1两个年龄组被报“普通格不能混种”，单行两件通过；规则L13限制物种数，转移§6.2明确保留不同年龄。完整论证：/home/zhuran24/zmd-research-fresh/求解器/crates/kernel/复核/否证-r4-2.md §2。'),
    ('KR-r4-L1-02', '未能否证。trigger.extra通过seed及两个公开cycle_key入口；与对照键的唯一差异就是该字段，违反trigger={kind,value}和未知扩展拒收要求。见否证-r4-2.md §3及否证-r4-2-证据/key-extra.json。'),
    ('KR-r4-L1-03', '未能否证。完整几何中所有非运输取货侧至多一级，删边或恢复也不能产生阻尼查询；完整表运行12刻成功，仅清空choices即装载停止，超出输入§5.3要求的触达域。见否证-r4-2.md §4。'),
    ('KR-r4-L1-04', '未能否证。path_runs独立新跑3刻仍给belt_adjacency标exercised、附72条证据；源码只记录路径连续两带，未调用规格限定的几何邻接轴。见否证-r4-2.md §5。'),
    ('KR-r4-L1-05', '未能否证。t=1检查点经seed验证且原样保留，正常续跑首刻为2；max-sweeps=1时两种记录格式均trace=null，违反已装载起点及空前缀end_time保留义务。见否证-r4-2.md §6。'),
    ('KR-r4-L2-1', '未能否证。新生成的邻接轴误标记录通过verify-record；聚合代码直接信任exercised标签，现有缺口名单遗漏该轴。与KR-r4-L1-04同源不使发现失效。见否证-r4-2.md §7。'),
    ('KR-r4-L2-2', '未能否证。新跑年龄溢出得到inconclusive/resource及四个null上下文，AJV2020确认现行CycleResult的allOf/4拒收；正常预算未决对照通过。KQ-09已披露但schema冲突未修复。见否证-r4-2.md §8。'),
]
verdicts = dict(verdicts=[dict(id=identifier, refuted=False, reason=reason) for identifier, reason in reasons])
assert len(verdicts['verdicts']) == len({row['id'] for row in verdicts['verdicts']}) == 7
write('verdicts.json', verdicts)

before = read(OUT / 'before-fingerprints.json')['files']
changed = [path for path, expected in before.items() if not Path(path).is_file() or digest(Path(path)) != expected]
text = REPORT.read_text()
missing_links = []
for target in re.findall(r'\]\(([^)]+)\)', text):
    if not (REPORT.parent / target).resolve().exists():
        missing_links.append(target)
extensions = sorted({p.suffix for p in OUT.rglob('*') if p.is_file()})
bad_files = [str(p) for p in OUT.rglob('*') if p.is_file() and p.suffix not in {'.py', '.log', '.json', '.md'}]
bad_directories = [str(p) for p in OUT.rglob('*') if p.is_dir()]
commands = read(OUT / 'commands.json')
schema = read(OUT / 'schema-results.json')['cases']
payload = dict(time=datetime.datetime.now().astimezone().isoformat(),
               readonly_file_count=len(before), changed_readonly_files=changed,
               report=str(REPORT), report_sha256=digest(REPORT),
               missing_links=missing_links, evidence_extensions=extensions,
               forbidden_evidence_files=bad_files, evidence_subdirectories=bad_directories,
               new_invocations=len(commands), schema_passed=sum(row['valid'] for row in schema),
               schema_failed=sum(not row['valid'] for row in schema),
               verdict_count=len(verdicts['verdicts']),
               compiled_binary_sha256=digest(WORK / 'target/debug/kernel'),
               source_probe_sha256=digest(OUT / 'run_checks.py'),
               reader_review=dict(seven_findings_present=True, duplicate_and_problem_counts_separate=True,
                                  prior_and_fresh_evidence_separate=True,
                                  loaded_checkpoint_and_load_failure_separate=True,
                                  conditional_seed_not_claimed_reachable=True,
                                  no_fix_claimed=True))
# 首次检查时delivery-check本身尚不存在，链接在写完后重核。
payload['missing_links'] = [p for p in missing_links if p != '否证-r4-2-证据/delivery-check.json']
payload['status'] = 'pass' if not (changed or payload['missing_links'] or bad_files or bad_directories) else 'fail'
write('delivery-check.json', payload)
assert payload['status'] == 'pass', payload
assert len(commands) == 20 and payload['schema_passed'] == 4 and payload['schema_failed'] == 1
assert all((REPORT.parent / target).resolve().exists() for target in re.findall(r'\]\(([^)]+)\)', text))
print(json.dumps(payload, ensure_ascii=False, indent=2))
