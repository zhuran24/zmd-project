"""包一写入入口：守卫、原字节备份、数据写入；不运行测试或 Git。"""
from pathlib import Path
import json
from guard import OUT, ROOT, REPO, guard, save, digest, active_snapshot, difference

def write(relative, data):
    path = ROOT / relative
    assert path.resolve().is_relative_to(ROOT) and not any(p in path.parts for p in ['evidence','复核','target'])
    backup = OUT / 'before' / relative
    if path.exists() and not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(path.read_bytes())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)

def remove(relative):
    path = ROOT / relative
    write(relative, path.read_bytes())
    path.unlink()

def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2)+'\n'

def install():
    guard('install-before')
    for path in sorted((OUT/'staging').rglob('*')):
        if path.is_file():
            write(str(path.relative_to(OUT/'staging')), path.read_bytes())
    guard('install-after')

def audit():
    import importlib.util
    spec = importlib.util.spec_from_file_location('package3_audit', OUT / 'package3-audit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.audit()

if __name__ == '__main__':
    install()
