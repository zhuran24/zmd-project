"""只读运行被审自查，将其所有写出重定向到本复核目录。"""
from pathlib import Path
from contextlib import redirect_stdout
import hashlib
import io
import json
import sys
import traceback

here = Path(__file__).resolve().parent
spec = here.parent.parent
revision = spec / '第五轮规格修订'
original_write = Path.write_text
allowed = {revision / name for name in ['StateSeed字段清点.json', '提升容量卡点.json', '轮询均分局部推演.json', '自查结果.json']}
allowed.add(spec / '内核输出.schema.json')
captured = {}

def redirected_write(path, data, *args, **kwargs):
    path = path.resolve()
    if path not in allowed:
        raise AssertionError('非预期写入：' + str(path))
    captured[str(path)] = data
    return original_write(here / ('重跑-' + path.name), data, *args, **kwargs)

sys.path.insert(0, str(revision))
report = {}
for filename in [revision / 'build_schema.py', spec / 'check_revision.py', revision / 'check_round5.py']:
    output = io.StringIO()
    namespace = {'__name__': '__main__', '__file__': str(filename)}
    failure = None
    Path.write_text = redirected_write
    try:
        with redirect_stdout(output):
            exec(compile(filename.read_text(), str(filename), 'exec'), namespace)
    except Exception:
        failure = traceback.format_exc()
        output.write(failure)
    finally:
        Path.write_text = original_write
    (here / (filename.stem + '.log')).write_text(output.getvalue())
    report[filename.name] = {'status': 'PASS' if failure is None else 'STOPPED', 'log': filename.stem + '.log', 'completed_checks': namespace.get('results', []), 'error': failure}

for filename, content in captured.items():
    assert Path(filename).read_bytes() == content.encode('utf-8'), filename
report['regenerated_files'] = {'count': len(captured), 'byte_equal': True}
before = json.loads((here / '开工指纹.json').read_text())
changes = [row['path'] for row in before['files'] if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() != row['sha256']]
protected_changes = [name for name in changes if '/crates/kernel/' not in name and not name.endswith('/参数扫描约减.md')]
assert not protected_changes, protected_changes
report['read_only_fingerprints'] = {'count': len(before['files']), 'changed_external_files': changes, 'reviewed_S_files_and_formal_sources_unchanged': True}
(here / '重跑汇总.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({name: {key: value for key, value in item.items() if key not in ['completed_checks', 'error', 'changed_external_files']} for name, item in report.items()}, ensure_ascii=False))
