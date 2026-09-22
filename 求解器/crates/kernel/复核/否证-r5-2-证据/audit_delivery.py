"""交付终核：比较已有材料字节与mtime，核对链接、结论和证据文件类型。"""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent/'否证-r5-2.md'


def write(name, value):
    (HERE/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


baseline = json.loads((HERE/'baseline.json').read_text())
changed = []
for name, original in baseline.items():
    path = Path(name)
    if not path.is_file():
        changed.append({'path': name, 'reason': 'missing'})
        continue
    current = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
               'size': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns}
    if current != original:
        changed.append({'path': name, 'before': original, 'after': current})
write('write-boundary.json', {'checked_files': len(baseline), 'changed_files': changed,
    'unchanged': not changed, 'comparison': 'sha256/size/mtime_ns'})
assert not changed, changed

verdicts = json.loads((HERE/'verdicts.json').read_text())['verdicts']
expected = ['KR-r5-L2-01', 'KR-r5-L2-02', 'KR-r5-L2-03']
assert [row['id'] for row in verdicts] == expected
assert all(row['refuted'] is False and '未能否证' in row['reason'] for row in verdicts)
body = REPORT.read_text()
links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', body)
for link in links:
    assert (REPORT.parent/link).exists(), link
files = [path for path in HERE.rglob('*') if path.is_file()]
assert all(path.suffix in {'.py', '.rs', '.log', '.json', '.md'} for path in files)
assert not any(path.name in {'target', '.cargo-home', 'registry', '__pycache__'} for path in HERE.rglob('*'))
large = [str(path) for path in files if path.stat().st_size > 20*1024*1024]
assert not large, large
write('reader-review.json', {'status': 'pass', 'report': str(REPORT),
    'finding_ids': expected, 'links_checked': len(links),
    'manual_review': ['每条结论自包含且有独立试验、契约和实现依据',
                      '普通有限合法性与生产域准入区分，交叉坏记忆不作合法输入证据',
                      '路径归一化相等与原始字节摘要分别核验',
                      '诊断复现与状态恢复、周期重跑分别判定',
                      '未声称全量回归或一般规则证明，状态与当前实测一致'],
    'evidence_extensions': sorted({path.suffix for path in files}),
    'evidence_bytes_before_audit_result': sum(path.stat().st_size for path in files),
    'files_over_20MiB': large})
print(json.dumps({'status': 'pass', 'unchanged_files': len(baseline),
                  'links_checked': len(links), 'verdicts': len(verdicts)}, ensure_ascii=False))
