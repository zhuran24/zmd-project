"""汇总逐ID结论，校验既有探针结果、来源字节和交付链接；不重跑内核。"""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT = Path(__file__).resolve().parent
REPORT = OUT.parent / '否证-r3-2.md'
(OUT / '交付核验.json').write_text('{"status":"checking"}\n')
prefix = str(REPORT)
items = [
    ('KR-r3-L1-01', '2.1', '当前seed先覆盖参数再校验；同一after_closure参数冲突输入直接run拒收，经seed后成功续跑，违反输入§6.4。'),
    ('KR-r3-L1-02', '2.2', '独立复现t=5、deadline=5被接受并在t=6执行窗口事件；该记录被verify-record以时序错误拒绝。'),
    ('KR-r3-L1-03', '2.3', '新生成P=1周期结果通过verify-cycle，但原样内嵌记录被verify-record拒绝；周期验收缺少规定的全前缀独立事件检查。'),
    ('KR-r3-L1-04', '2.4', '源矿、蓝铁矿分别清零并保留历史身份时，seed均成功，派生输入run均因缺矿拒收；正库存前提未纳入派生验收。'),
    ('KR-r3-L2-01', '2.5', '参数表清空、快照相位冲突、顶层相位冲突三例均为run拒收而seed覆盖后可续跑；合法对照完整状态保持相等。'),
    ('KR-r3-L2-02', '2.6', '同步参数镜像后，−1、6、1/2及not-a-Time均被run接受；非法字符串相位还通过P=20周期生成及verify-cycle，类型和值域校验确有遗漏。'),
    ('KR-r3-L2-03', '2.7', '新跑桥记录的32条先接覆盖证据全是已定向桥上的搬运；接通发生在记录之前。两轴物流成功不构成先接定向实际执行。'),
    ('KR-r3-L3-01', '2.8', '独立复现短槽位标签触发run越界panic、布尔种子触发seed索引panic；均退出101、stdout为空且无结果文件。'),
    ('KR-r3-L3-02', '2.9', '同源年龄溢出输入在run报告inconclusive，在cycle报告stopped且stop.kind=resource；装载外壳确实改变顶层资源分类。'),
    ('KR-r3-L3-03', '2.10', '实查仍有15个ELF/ar文件共219896964字节，以及193文件的历史快照和独立空target目录；属遗留证据违规，未归责第五轮新增复制。'),
]
verdicts = {'verdicts': [dict(id=key, refuted=False, reason=f'未能否证：{reason}详见{prefix} §{section}。')
                         for key, section, reason in items]}
(OUT / 'verdicts.json').write_text(json.dumps(verdicts, ensure_ascii=False, indent=2) + '\n')
baseline = json.loads((OUT / '开工指纹.json').read_text())
changed = [r['path'] for r in baseline if hashlib.sha256(Path(r['path']).read_bytes()).hexdigest() != r['sha256']]
sources = json.loads((OUT / 'source-fingerprints.json').read_text())
source_changed = [p for p, h in sources['sources'].items() if hashlib.sha256(Path(p).read_bytes()).hexdigest() != h]
reported = json.loads((OUT / 'reported-evidence-index.json').read_text())
reported_changed = [r['path'] for r in reported if hashlib.sha256(Path(r['path']).read_bytes()).hexdigest() != r['sha256']]
text = REPORT.read_text()
broken = []
for target in re.findall(r'\]\(([^)]+)\)', text):
    if not (REPORT.parent / target).resolve().exists():
        broken.append(target)
bad_files = [str(p) for p in OUT.rglob('*') if p.is_file() and p.suffix not in ('.py','.log','.json','.md')]
bad_dirs = [str(p) for p in OUT.rglob('*') if p.is_dir()]
binary = []
for path in OUT.iterdir():
    if path.is_file():
        with path.open('rb') as stream:
            magic = stream.read(8)
        if magic.startswith(b'\x7fELF') or magic == b'!<arch>\n':
            binary.append(str(path))
rows = json.loads((OUT / 'cli-results.json').read_text())
cases = {r['name']: r for r in rows}
assert len(cases) == len(rows) == 50
for name in ('slot-short', 'seed-bool'):
    assert cases[name]['exit_code'] == 101 and cases[name]['result_path'] is None and cases[name]['stdout'] == ''
assert cases['slot-unknown']['status'] == 'invalid_input'
assert cases['overflow-run']['status'] == 'inconclusive'
assert cases['overflow-cycle']['status'] == 'stopped' and cases['overflow-cycle']['stop']['kind'] == 'resource'
for name in ('negative','large','fraction','malformed'):
    assert cases['phase-' + name]['status'] == 'completed'
for name in ('phase-cycle-verify','expired-cycle-verify'):
    result = json.loads(Path(cases[name]['result_path']).read_text())
    assert result['cycle_replayed'] is True
for name in ('expired-embedded-verify','window-equal-verify'):
    assert cases[name]['status'] == 'invalid_input'
assert cases['window-future-verify']['status'] == 'input_checked'
assert cases['window-past']['status'] == 'invalid_input'
for ore in ('源矿','蓝铁矿'):
    assert cases['zero-' + ore + '-seed']['exit_code'] == 0
    assert cases['zero-' + ore + '-run']['status'] == 'invalid_input'
ids = [r['id'] for r in verdicts['verdicts']]
headings = re.findall(r'^### 2\.\d+ (KR-r3-L\d-\d+)', text, re.M)
assert len(ids) == len(set(ids)) == 10 and headings == ids
check = dict(status='pass' if not any((changed, source_changed, reported_changed, broken, bad_files, bad_dirs, binary)) else 'fail',
    baseline_files=len(baseline), changed=changed, source_changed=source_changed, reported_evidence_changed=reported_changed,
    broken_links=broken, disallowed_files=bad_files, evidence_subdirectories=bad_dirs, compiled_files=binary,
    verdict_count=len(ids), cli_calls=len(rows), reader_review='已逐条重读报告；依据、正负例、范围和归责与结果文件一致',
    report_sha256=hashlib.sha256(REPORT.read_bytes()).hexdigest(),
    binary_sha256=hashlib.sha256((ROOT/'target/release/kernel').read_bytes()).hexdigest())
(OUT/'交付核验.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(check,ensure_ascii=False,indent=2))
assert check['status'] == 'pass'
