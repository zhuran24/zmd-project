import json,shutil,tempfile
from audit_files import *
f=json.loads((IMPL/'continuation-freeze.json').read_text());oldroot=Path(f['root']);newroot=Path(tempfile.mkdtemp(prefix='kernel-audit2-'))
backup=ROOT/'求解器/target/health-capture/continuation-20260923/production-a-test-sources'
rows=[];mapping=[]
for row in f['files']:
    p=oldroot/row['path'];q=newroot/row['path']
    if sha(p)!=row['sha256']:
        p=backup/Path(row['path']).relative_to('求解器')
    assert sha(p)==row['sha256'],('A source unavailable',row['path'])
    q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);q.chmod(p.stat().st_mode&0o777)
    raw=q.read_bytes()
    if q.suffix=='.json' and str(oldroot).encode() in raw:
        rewritten=raw.replace(str(oldroot).encode(),str(newroot).encode());q.write_bytes(rewritten)
        mapping.append(dict(path=row['path'],before=row['sha256'],after=sha(q),from_root=str(oldroot),to_root=str(newroot),kind='physical copy path tokens only; both stages share this resource'))
    rows.append(dict(path=row['path'],sha256=sha(q),size=q.stat().st_size))
save('own-freeze.json',dict(root=str(newroot),source_root=str(newroot/'求解器'),files=rows,path_mappings=mapping,origin_manifest_sha256=sha(IMPL/'continuation-freeze.json')))
print('prepared',len(rows),'files',newroot,'path rewrites',len(mapping))
