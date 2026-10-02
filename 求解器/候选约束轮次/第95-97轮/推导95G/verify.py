"""Cross-check local proof results and record the exact inputs used by 95G."""
import hashlib
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ga = json.loads((OUT/'geometry_a.json').read_text())
    gb = json.loads((OUT/'geometry_b.json').read_text())
    assert len(ga['baseline']) == len(gb['baseline']) == 135
    for x, y in zip(ga['baseline'], gb['baseline']):
        for key in ['key', 'bound', 'options']:
            assert x[key] == y[key], (key, x, y)
    assert ga['near'] == gb['near']
    assert ga['incompatible'] == gb['incompatible']
    assert ga['baseline_maximum'] == gb['baseline_maximum'] == 91
    assert ga['near_maximum'] == gb['near_maximum'] == 91
    assert len(ga['near']) == 15697 and len(ga['incompatible']) == 1042
    assert all(r[-1] <= 91 for r in ga['near'])
    aa = json.loads((OUT/'arithmetic_a.json').read_text())
    ab = json.loads((OUT/'arithmetic_b.json').read_text())
    assert aa == ab, [(k, aa[k], ab[k]) for k in aa if aa[k] != ab[k]]
    snapshot = OUT.parent/'前提快照'
    inputs = list(snapshot.glob('*.txt'))+[OUT.parent/'临时规则.md', ROOT/'候选约束.txt',
              OUT.parent.parent/'第92-94轮'/'推导92B.md',
              OUT.parent.parent/'第92-94轮'/'复核93B.md',
              OUT.parent.parent/'第92-94轮'/'复核94B.md',
              OUT.parent.parent/'第78-80轮'/'推导78B.md',
              OUT.parent.parent/'三审-第63-80轮'/'三审报告.md',
              OUT.parent.parent/'三审-第81轮'/'三审报告.md']
    manifest = {str(p): digest(p) for p in inputs}
    manifest_path = OUT/'input_manifest.json'
    if manifest_path.exists():
        assert json.loads(manifest_path.read_text()) == manifest, 'input changed since first check'
    else:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    summary = {'status': 'PASS', 'baseline_cases': len(ga['baseline']),
               'total_near_branches': len(ga['near'])+len(ga['incompatible']),
               'near_cases': len(ga['near']), 'impossible_fixed_body_cases': len(ga['incompatible']),
               'near_d_counts': dict(Counter(r[-2] for r in ga['near'])),
               'baseline_N_plus_w_histogram': dict(Counter(r['bound'] for r in ga['baseline'])),
               'near_N_plus_w_plus_d_histogram': dict(Counter(r[-1] for r in ga['near'])),
               'geometries': ['cell CP-SAT', 'exact interval scheduling'],
               'arithmetic_routes': ['support costs and dictionary DP', 'flow vectors and array convolution'],
               'arithmetic': {k: v for k, v in aa.items() if k != 'rounding_cases'},
               'seconds': {'geometry_a': ga['seconds'], 'geometry_b': gb['seconds']},
               'evidence_scope': 'necessary local bounds, no playable layout or counterexample'}
    (OUT/'verification.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
