import json,sys,codecs,re
from audit_guard import *
a=json.loads((IMPL/'isolation-accepted.json').read_text());S=Path(a['source_root'])
command('independent-metadata',['cargo','metadata','--locked','--offline','--no-deps','--format-version','1'],S)
d=json.loads((OUT/'independent-metadata.stdout.log').read_text())
expected={(p['manifest_path'],t['name'],tuple(t['kind'])) for p in d['packages'] for t in p['targets'] if t['test']}
actual={(h['manifest_path'],h['target']['name'],tuple(h['target']['kind'])) for h in a['harnesses']};assert len(actual)==len(a['harnesses']) and actual==expected
sys.path.insert(0,str(IMPL));from continuation_closure import words
counts=[]
for i,h in enumerate(a['harnesses']):
    binary=Path(h['executable']);assert sha(binary)==h['sha256'] and str(S).encode() in binary.read_bytes();dep=Path(h['dep_info']['path']);assert sha(dep)==h['dep_info']['sha256']
    rows=[]
    for line in dep.read_text().replace('\\\n','').splitlines():
        split=re.search(r'(?<!\\):(?:\s|$)',line)
        if split and str(binary) in words(line[:split.start()]):rows.append(words(line[split.end():]))
    assert len(rows)==1;paths=[str((S/x).resolve()) for x in rows[0]];assert len(paths)==len(set(paths)) and set(paths)==set(h['dep_info']['files'])
    assert all(sha(p)==h['dep_info']['files'][p] for p in paths)
    listing=(OUT/f'list-{i}.stdout.log').read_text();m=re.search(r'(\d+) tests?, (\d+) benchmarks?',listing);assert m
    counts.append(dict(name=h['target']['name'],kind=h['target']['kind'],count=int(m[1]),dep_info=str(dep)))
save('harness-binding-audit.json',dict(passed=True,metadata_targets=len(expected),harnesses=counts,total=sum(x['count'] for x in counts)))
# Successful write opens, including paths removed by the tests before the final hash scan.
writes=[];bad=[];read_bad=[];read_paths=set()
external=set(json.loads((IMPL/'continuation-runtime-dependencies.json').read_text())['files'])
executables={str(Path(x['executable']).resolve()) for x in a['harnesses']+a['binaries']}
def completed_lines(trace):
    pending={}
    for line in trace.read_text().splitlines():
        pid=line.split()[0]
        if '<unfinished ...>' in line:
            pending[pid]=line.split('<unfinished ...>')[0];continue
        if '<... ' in line and ' resumed>' in line:
            if pid in pending:line=pending.pop(pid)+line.split(' resumed>',1)[1]
        yield line
for trace in sorted(OUT.glob('guarded-*.trace.log')):
    for line in completed_lines(trace):
        m=re.search(r'= [0-9]+<([^>]+)>$',line)
        if not m:continue
        p=codecs.escape_decode(m[1].encode())[0].decode();path=Path(p.removesuffix(' (deleted)'))
        if not any(flag in line for flag in ['O_WRONLY','O_RDWR','O_CREAT','O_TRUNC','O_APPEND']):
            if path.is_dir():continue
            read_paths.add(str(path));resolved=str(path.resolve())
            allowed=path.is_relative_to(S.parent) or path.is_relative_to(OUT) or path.is_relative_to(REPO/'target/health-tests') or p.startswith(('/tmp/kernel-formal-catalog-','/dev/','/proc/','/sys/')) or resolved in external or resolved in executables
            if not allowed:read_bad.append(dict(trace=trace.name,path=p))
            continue
        allowed=path.is_relative_to(OUT) or path.is_relative_to(REPO/'target/health-tests') or p.startswith('/tmp/kernel-formal-catalog-') or p.startswith('/dev/')
        row=dict(trace=trace.name,path=p,allowed=allowed)
        writes.append(row)
        if not allowed:bad.append(row)
save('write-boundary-audit.json',dict(passed=not bad,successful_write_opens=len(writes),unique_paths=len({x['path'] for x in writes}),unexpected=bad,writes=writes));assert not bad
save('read-boundary-audit.json',dict(passed=not read_bad,unique_paths=len(read_paths),unexpected=read_bad,paths=sorted(read_paths),method='reassembled unfinished/resumed open calls, including vanished temporary files'));assert not read_bad
print('binding metadata',len(expected),'tests',sum(x['count'] for x in counts),'successful writes',len(writes),'unexpected',len(bad))
