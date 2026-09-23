from guard import ROOT, OUT
import json

def write(path, content):
    path = ROOT / path if isinstance(path, str) else path
    data = content.encode() if isinstance(content, str) else content
    if path.exists() and path.read_bytes() == data:
        return
    backup = OUT / 'before' / path.relative_to(ROOT)
    if path.exists() and not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(path.read_bytes())
    path.write_bytes(data)

def edit(path, pairs):
    text = (ROOT / path).read_text()
    for old, new in pairs:
        assert old in text, (path, old[:100])
        text = text.replace(old, new)
    write(path, text)

def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'
