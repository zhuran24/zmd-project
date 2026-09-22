"""复核收尾：仅重读指纹和证据类型，不清理或改写被审文件。"""
import hashlib
import json
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    before = json.loads((OUT / '开工指纹.json').read_text())
    changed = []
    review_changes = []
    for name, sha in before.items():
        path = Path(name) if name.startswith('/') else ROOT / name
        if not path.exists() or digest(path) != sha:
            (review_changes if '/复核/' in str(path) else changed).append(str(path))
    additions = []
    for base, directories, files in os.walk(ROOT):
        directories[:] = [name for name in directories if name not in ('target', '.cargo-home', '.git', '__pycache__')]
        for name in files:
            path = Path(base) / name
            relative = str(path.relative_to(ROOT))
            if relative not in before and '/复核/' not in str(path):
                additions.append(str(path))
    manifest = json.loads((ROOT / 'crates/kernel/evidence/revision-r3/交付清单.json').read_text())
    mismatches = []
    for row in manifest['changes']:
        path = Path(row['path'])
        if row['after'] is None:
            if path.exists():
                mismatches.append(str(path))
        elif not path.exists() or digest(path) != row['after']['sha256']:
            mismatches.append(str(path))
    protected = json.loads((ROOT / 'crates/kernel/evidence/revision-r3/范围审计.json').read_text())['protected_fingerprints']
    protected_changes = [r['path'] for r in protected if not Path(r['path']).exists() or digest(Path(r['path'])) != r['sha256']]
    forbidden, compiled, links, cargo = [], [], [], []
    for base in [ROOT / 'crates/kernel/evidence', ROOT / 'crates/kernel/复核']:
        for path in base.rglob('*'):
            if path.is_symlink():
                links.append(str(path))
            if path.is_dir() and path.name in ('target', '.cargo-home', 'registry', '.git'):
                forbidden.append(str(path))
            if path.is_file():
                with path.open('rb') as stream:
                    magic = stream.read(8)
                if magic.startswith((b'\x7fELF', b'!<arch>')):
                    compiled.append(str(path))
                if path.name in ('Cargo.toml', 'Cargo.lock'):
                    cargo.append(str(path))
    own_files = [p for p in OUT.rglob('*') if p.is_file()]
    invalid_types = [str(p) for p in own_files if p.suffix not in ('.py', '.rs', '.log', '.json', '.md')]
    result = dict(status='pass' if not any([changed, additions, mismatches, protected_changes, forbidden, compiled, cargo, invalid_types]) else 'review_required',
                  baseline_files=len(before), nonreview_changes=changed, concurrent_review_changes=review_changes,
                  nonreview_additions=additions,
                  original_manifest_rows=len(manifest['changes']), manifest_mismatches=mismatches,
                  original_protected_files=len(protected), original_protected_changes=protected_changes,
                  forbidden_directories=forbidden, compiled_files=compiled, cargo_manifests=cargo, symlinks=links,
                  own_evidence_invalid_types=invalid_types, own_evidence_file_count=len(own_files),
                  shared_target=str(ROOT / 'target'),
                  note='其它复核席并发写自己的复核目录，单列观测；本席未归因其修改。没有审计模拟器内容。')
    (OUT / '最终范围审计.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
