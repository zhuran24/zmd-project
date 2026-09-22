"""批量验收的只读性：记录树与mtime/字节完全不变，结果日志只写本证据目录。"""
import hashlib
import json
from pathlib import Path
import subprocess

E = Path(__file__).resolve().parent
ROOT = E.parents[4]
BIN = ROOT / 'target/release/kernel'


def snapshot(directory):
    return {str(path): dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        bytes=path.stat().st_size, mtime_ns=path.stat().st_mtime_ns)
        for path in directory.rglob('*') if path.is_file()}


for name, directory in [('verify-batch', ROOT / '数据/样例'),
    ('verify-relative-batch', E / 'cli/package'), ('verify-reference-batch', E / 'cli/reference-package')]:
    before = snapshot(directory)
    checked = subprocess.run([str(BIN), 'verify-batch', str(directory)],
        capture_output=True, text=True, cwd=ROOT.parent)
    (E / (name + '.log')).write_text(checked.stderr)
    assert before == snapshot(directory), ('被核树变化', directory)
    assert checked.returncode == 0, (name, checked.stdout, checked.stderr)
    result = json.loads(checked.stdout)
    result.update(audited_tree_unchanged=True, checked_files=len(before),
        checked_bytes=sum(row['bytes'] for row in before.values()))
    (E / (name + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(name, len(result['records']), len(result['cycles']), flush=True)
