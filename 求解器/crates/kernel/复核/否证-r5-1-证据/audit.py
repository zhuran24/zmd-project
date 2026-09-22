"""复核复现结果、保护文件及报告链接；只写本席最终校验结果。"""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    calls = read(HERE / 'commands.json')
    failures = {
        'ore-79999-check': 2, 'ore-80000-check': 2,
        'ore-79999-cycle': 2, 'ore-80000-cycle': 2,
        'relative-verify-record-root': 2, 'relative-verify-record-local': 2,
        'relative-checkpoint': 2, 'relative-batch': 2,
        'load-shell-checkpoint': 101,
    }
    for call in calls:
        assert call['exit_code'] == failures.get(call['name'], 0), call
    observations = {row['name']: row['result'] for row in calls}
    assert observations['load-shell-verify']['diagnostic_replayed']
    assert observations['load-shell-verify']['cycle_replayed'] is False
    assert observations['relative-verify-cycle']['cycle_replayed']
    assert all(row['valid'] for row in read(HERE / 'schema-results.json'))
    before = read(HERE / 'before.json')
    changed = []
    for name, old in before.items():
        path = Path(name)
        now = None if not path.exists() else dict(sha256=digest(path), size=path.stat().st_size,
                                                 mtime_ns=path.stat().st_mtime_ns)
        if now != old:
            changed.append(dict(path=name, before=old, after=now))
    report = HERE.parent / '否证-r5-1.md'
    links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', report.read_text())
    missing = [link for link in links if not (report.parent / link.split('#')[0]).exists()]
    # 这两份最终自审文件在本次交付检查完成时写入。
    expected_outputs = {'否证-r5-1-证据/verification-summary.json', '否证-r5-1-证据/reader-review.json'}
    missing = [link for link in missing if link not in expected_outputs]
    forbidden = [str(path) for path in HERE.rglob('*') if path.is_file()
                 and path.suffix not in {'.py', '.log', '.json', '.md'}]
    large = [str(path) for path in HERE.rglob('*') if path.is_file() and path.stat().st_size > 20_000_000]
    assert not changed, changed
    assert not missing, missing
    assert not forbidden, forbidden
    assert not large, large
    summary = dict(status='通过', scope='预期故障复现及交付边界检查，不是产品故障已修复',
        process_calls=len(calls), kernel_cli_calls=sum(Path(row['command'][0]).name == 'kernel' for row in calls),
        expected_failure_count=len(failures), schema_documents=5, existing_unit_tests_passed=3,
        protected_files=len(before), protected_sha256_size_mtime_unchanged=not changed,
        protected_changes=changed, report_links_checked=len(links), missing_links=missing,
        forbidden_evidence_files=forbidden, evidence_files_over_20MB=large,
        release_binary_sha256=digest(ROOT/'target/release/kernel'),
        constructor_binary_sha256=digest(ROOT/'target/r5_seat1_constructor_probe'),
        report_sha256=digest(report))
    (HERE/'verification-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
