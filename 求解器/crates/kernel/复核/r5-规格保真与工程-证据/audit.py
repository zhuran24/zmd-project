"""独立核对交付清单、约减重锁、契约字段与本席写入边界。"""
import copy
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EVIDENCE = ROOT/'crates/kernel/evidence/round6'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (HERE/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def main():
    manifest=read(EVIDENCE/'files.json')['files']
    rows=[]
    for name in manifest:
        p=Path(name)
        row={'path':name,'exists':p.exists()}
        if p.is_file():
            row.update(bytes=p.stat().st_size,sha256=sha(p))
            if p.suffix=='.json':
                data=read(p)
                row['json_type']=type(data).__name__
                if isinstance(data,dict):
                    row.update({k:data[k] for k in ('schema','status','record_mode') if k in data})
        rows.append(row)
    save('artifact-inventory.json',{'path_count':len(rows),'missing':[r['path'] for r in rows if not r['exists']],'files':rows})

    before=read(EVIDENCE/'before.json')['files']
    target=ROOT/'规格/复核/约减/等价类计数.json'
    lock=read(EVIDENCE/'reduction-lock.json')
    current=read(target)
    reconstructed=copy.deepcopy(current)
    for change in lock['changed_fingerprints']:
        row=next(r for r in reconstructed['sources'] if r['path']==change['path'])
        assert row['sha256']==change['after']
        row['sha256']=change['before']
    old_bytes=(json.dumps(reconstructed,ensure_ascii=False,indent=2)+'\n').encode()
    old_sha=hashlib.sha256(old_bytes).hexdigest()
    assert old_sha==lock['before_sha256']==before[str(target)]['sha256']
    assert sha(target)==lock['after_sha256']
    changed=[]
    unchanged=[]
    for name,info in before.items():
        if '/规格/复核/约减/' not in name:
            continue
        assert Path(name).is_file()
        (unchanged if sha(Path(name))==info['sha256'] else changed).append(name)
    assert changed==[str(target)]
    save('reduction-independent.json',{'status':'pass','before_hash_reconstructed':old_sha,
         'after_hash':sha(target),'changed_files':changed,'unchanged_count':len(unchanged),
         'changed_sha256_entries':len(lock['changed_fingerprints']),
         'non_source_content_equal':{k:v for k,v in reconstructed.items() if k!='sources'}=={k:v for k,v in current.items() if k!='sources'},
         'classes':lock['classes']})

    schema=read(ROOT/'规格/内核输出.schema.json')
    certificate=read(HERE/'none-7.json')
    assert set(schema['$defs']['CycleResult']['required'])==set(certificate)
    save('field-sets.json',{'top_level_fields':sorted(certificate),
         'count':len(certificate),'required_equal':True,
         'cycle_fields':sorted(certificate['cycle']),
         'input_reference_fields':sorted(certificate['replay_input_ref']),
         'domain_fields':sorted(certificate['domain_report'][0])})

    baseline=read(HERE/'baseline.json')
    changes=[]
    for name,old in baseline.items():
        p=Path(name)
        if not p.is_file():
            changes.append({'path':name,'change':'missing'})
        elif sha(p)!=old['sha256'] or p.stat().st_mtime_ns!=old['mtime_ns']:
            changes.append({'path':name,'change':'bytes_or_mtime'})
    save('write-boundary.json',{'baseline_files':len(baseline),'changed':changes,
         'evidence_extensions':sorted({p.suffix for p in HERE.rglob('*') if p.is_file()}),
         'evidence_bytes':sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file())})
    assert not changes,changes
    print(json.dumps({'inventory_paths':len(rows),'baseline_files':len(baseline),'baseline_unchanged':True},ensure_ascii=False))


if __name__=='__main__':
    main()
