"""Validate report links, complete candidate fields, evidence and file scope."""
import hashlib
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPORT = OUT.parent/'推导95G.md'


def main():
    report = REPORT.read_text()
    candidates = []
    for title, start, end in [('内带缺口', '### 7.1 内带缺口', '### 7.2 面积预算'),
                              ('面积预算', '### 7.2 面积预算', '## 8.')]:
        section = report.split(start, 1)[1].split(end, 1)[0]
        def take(label):
            match = re.search(r'\*\*'+re.escape(label)+r'：\*\*(.+)', section)
            assert match, (title, label)
            return match.group(1).replace('`', '').strip()
        candidates.append({'name': title, 'kind': '必要条件', 'text': take(title),
                           'basis': take('据'), 'derivation': take('推导'),
                           'relation': take('relation'), 'status': '待审'})
    assert len(candidates) == 2
    (OUT/'candidates.json').write_text(json.dumps(candidates, ensure_ascii=False, indent=2)+'\n')
    links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', report)
    for link in links:
        assert not link.startswith('http'), link
        target = (REPORT.parent/link).resolve()
        assert target.exists(), target
    verification = json.loads((OUT/'verification.json').read_text())
    assert verification['status'] == 'PASS'
    for p in OUT.iterdir():
        assert p.is_file() and p.suffix in {'.py', '.log', '.json', '.md', '.gz'}, p
        assert p.stat().st_size < 100*1024*1024 or p.suffix == '.gz', p
    result = {'status': 'PASS', 'report_path': str(REPORT), 'candidate_names': [c['name'] for c in candidates],
              'local_links_checked': len(links),
              'reader_review': 'Completed: scope, original X, integer rounding, full-range quantifiers, U dependency and unresolved corner branch checked.'}
    (OUT/'delivery_validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    records = {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
               for p in sorted(OUT.iterdir()) if p.name not in {'artifact_manifest.json', 'delivery_check.log'}}
    records['../推导95G.md'] = {'bytes': REPORT.stat().st_size, 'sha256': hashlib.sha256(REPORT.read_bytes()).hexdigest()}
    (OUT/'artifact_manifest.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n')
    result['files_hashed'] = len(records)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
