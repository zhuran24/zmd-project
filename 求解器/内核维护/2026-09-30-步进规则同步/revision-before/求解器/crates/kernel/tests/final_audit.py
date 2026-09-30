#!/usr/bin/env python3
"""第四轮§4.7、内核输出§1：交付前的只读来源、说明链接、注释与文件指纹审计。"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KERNEL = ROOT / 'crates/kernel'


def digest(path):
    """内核输出§1：原始字节 SHA-256。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    """第四轮§4.7：严格核对已经落盘的结果，不刷新任何既有规格/黄金。"""
    baseline = json.loads((KERNEL / 'evidence/baseline.json').read_text())
    assert all(digest(Path(p)) == h for p, h in baseline.items())
    check = subprocess.run([str(ROOT / 'target/release/kernel'), 'check', str(ROOT / '数据/样例/桥接器双通路.json'), '--config', str(ROOT / '规格/内核配置-v1.json')], capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    periodic = subprocess.run([str(ROOT / 'target/release/kernel'), 'request', 'warehouse.periodic_lift', '--config', str(ROOT / '规格/内核配置-v1.json')], capture_output=True, text=True)
    assert periodic.returncode == 2
    stopped = json.loads(periodic.stdout)
    assert stopped['status'] == 'unsupported' and 'warehouse.periodic_lift' in stopped['open_items'][0]
    (KERNEL / 'evidence/periodic-stop.json').write_text(json.dumps(stopped, ensure_ascii=False, indent=2) + '\n')
    function_count = 0
    for source in (KERNEL / 'src').glob('*.rs'):
        lines = source.read_text().splitlines()
        assert not re.search(r'\b(?:f32|f64|HashMap)\b', '\n'.join(lines)), source
        for i, line in enumerate(lines):
            if re.search(r'\bfn\s+\w+', line):
                function_count += 1
                assert any('///' in s and '§' in s for s in lines[max(0, i-8):i]), (source, i+1)
    test_log = (KERNEL / 'evidence/cargo-test.txt').read_text()
    counts = [(int(a), int(b)) for a, b in re.findall(r'test result: ok\. (\d+) passed; (\d+) failed', test_log)]
    assert sum(a for a, _ in counts) == 79 and sum(b for _, b in counts) == 0
    docs = [KERNEL / 'README.md', KERNEL / 'evidence/实现验证.md', KERNEL / 'evidence/手推桥接轨迹.md', ROOT / '规格/内核实现-对规格的疑问.md']
    manifest_path = KERNEL / 'evidence/deliverables.json'
    manifest_path.write_text('{}\n')
    links = 0
    for doc in docs:
        for target in re.findall(r'\]\(([^)]+)\)', doc.read_text()):
            if target.startswith(('http:', 'https:', '#')):
                continue
            file = target.split('#')[0]
            assert (doc.parent / file).resolve().exists(), (doc, target)
            links += 1
    result = {'status': '通过', 'baseline_unchanged': len(baseline), 'workspace_tests_passed': 79, 'workspace_tests_failed': 0, 'rust_functions_with_section_comments': function_count, 'documentation_links_checked': links, 'bridge_static_cli': json.loads(check.stdout), 'periodic_lift_exit_code': periodic.returncode}
    (KERNEL / 'evidence/final-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    files = sorted([p for p in KERNEL.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p != manifest_path] + [ROOT / 'Cargo.toml', ROOT / 'Cargo.lock', ROOT / '规格/内核实现-对规格的疑问.md'] + list((ROOT / '数据/样例').glob('*-kernel.json')))
    manifest = {'scope': '本次源交付物及验证证据；不含target构建缓存和本清单自身', 'files': [{'path': str(p), 'sha256': digest(p), 'bytes': p.stat().st_size} for p in files]}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({**result, 'deliverable_files_including_manifest': len(files)+1}, ensure_ascii=False))


if __name__ == '__main__':
    main()
