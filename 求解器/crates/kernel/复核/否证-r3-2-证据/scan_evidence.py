"""只读核实遗留证据文件头、目录与快照清单，不复制或删除原件。"""
from pathlib import Path
import json
import hashlib

ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT = Path(__file__).resolve().parent
kernel = ROOT / 'crates/kernel'
binary = []
directories = []
for base in (kernel / 'evidence', kernel / '复核'):
    for path in sorted(base.rglob('*')):
        if path.is_dir() and path.name in ('target', '.cargo-home', 'registry', 'snapshot'):
            directories.append(dict(path=str(path), symlink=path.is_symlink(), resolved=str(path.resolve())))
        if not path.is_file():
            continue
        with path.open('rb') as stream:
            head = stream.read(8)
        if head.startswith(b'\x7fELF') or head == b'!<arch>\n':
            binary.append(dict(path=str(path), bytes=path.stat().st_size, magic=head.hex(),
                               sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
snapshot = kernel / '复核/r2-测试与证据/snapshot'
files = [dict(path=str(p.relative_to(snapshot)), bytes=p.stat().st_size)
         for p in sorted(snapshot.rglob('*')) if p.is_file()]
target = snapshot / '求解器/target'
result = dict(binary_count=len(binary), binary_bytes=sum(r['bytes'] for r in binary), binaries=binary,
              directories=directories, snapshot_files=files, snapshot_count=len(files),
              snapshot_bytes=sum(r['bytes'] for r in files),
              target=dict(exists=target.exists(), is_dir=target.is_dir(), is_symlink=target.is_symlink(),
                          entries=[p.name for p in target.iterdir()] if target.is_dir() else None),
              round5_binaries=[r for r in binary if '/evidence/round5/' in r['path']])
(OUT / 'evidence-scan.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('binaries','snapshot_files','directories')}, ensure_ascii=False))
