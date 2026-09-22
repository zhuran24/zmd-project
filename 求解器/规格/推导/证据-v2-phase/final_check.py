"""成稿引用、输出范围与输入保护检查；不改输入，不作整厂认证。"""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
DOC = HERE.parent / '三种相位不改产量-v2.md'
source_manifest = json.loads((HERE / 'sources.json').read_text())
source_hashes = source_manifest['files']
changed = [p for p, old in source_hashes.items()
           if hashlib.sha256(Path(p).read_bytes()).hexdigest() != old]
assert not changed, changed

missing = []
link_count = 0
for source in [DOC, HERE / 'audit.md', HERE / 'owner-quotes.md']:
    for href in re.findall(r'\]\(([^)]+)\)', source.read_text()):
        if '://' in href or href.startswith('#'):
            continue
        path = Path(href)
        path = path if path.is_absolute() else source.parent / path
        # 本脚本即将写出的检查结果也是审计记录的合法目标。
        if not path.exists() and path.resolve() != (HERE / 'final-check.json').resolve():
            missing.append(str(path))
        link_count += 1
assert not missing, missing

body = DOC.read_text()
sections = re.findall(r'^## §(\d+) ', body, re.M)
assert sections == ['0', '1', '2', '3', '4', '5'], sections
assert 'L=0、U=1113' in body
assert '第五星期位' not in body
assert '尚未经过第二版独立复核' in body
bad_extensions = [str(p) for p in HERE.rglob('*') if p.is_file()
                  and p.suffix not in {'.py', '.json', '.log', '.md'}]
assert not bad_extensions, bad_extensions

report = {
    'document': str(DOC), 'document_sha256': hashlib.sha256(DOC.read_bytes()).hexdigest(),
    'document_lines': len(body.splitlines()), 'sections': sections,
    'checked_local_links': link_count, 'missing_links': missing,
    'input_files_checked': len(source_hashes), 'changed_inputs': changed,
    'dialogue_initial_full_read': source_manifest['dialogue_initial_full_read'],
    'disallowed_evidence_file_types': bad_extensions,
    'author_full_read_audit': 'audit.md', 'independent_v2_review': False,
    'whole_layout_certified': False, 'kernel_run': False,
}
(HERE / 'final-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
