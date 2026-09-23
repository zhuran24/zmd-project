#!/usr/bin/env python3
"""Read-only independent audit; all output remains beside this script."""
import hashlib, json, os, subprocess, sys
from pathlib import Path

V = Path(__file__).resolve().parent
R = V.parents[3]
S = R / '求解器'
HISTORY = ['求解器/crates/kernel/evidence', '求解器/crates/kernel/复核', '求解器/数据/复核']
PROTECTED = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '游戏理解.txt', '候选约束.txt', '候选简化.txt', '候选充分条件.txt']
OLD = 'b573a299c5853dada4189f53b629733f826a535ca011c969c6d658256d9af74c'
def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args], cwd=R)
def dump(name, value):
    (V/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
def digest(data): return hashlib.sha256(data).hexdigest()
def inventory(base):
    return {str(p.relative_to(R)): {'size':p.stat().st_size,'sha256':digest(p.read_bytes())}
            for p in sorted(base.rglob('*')) if p.is_file()}
def status():
    return [r.decode() for r in git('status','--porcelain=v1','-z','--untracked-files=all').split(b'\0') if r]
def snapshot(label):
    histories = {h:inventory(R/h) for h in HISTORY}
    work = {}
    for root, dirs, files in os.walk(R):
        dirs[:] = [d for d in dirs if d not in ['.git', 'target', '__pycache__'] and Path(root,d) != V]
        if any(Path(root).is_relative_to(R/h) for h in HISTORY):
            dirs[:] = []; continue
        for f in files:
            p=Path(root,f)
            if p.is_file(): work[str(p.relative_to(R))]={'sha256':digest(p.read_bytes()),'size':p.stat().st_size}
    head = git('rev-parse','HEAD').decode().strip()
    head_history={}
    rows=git('ls-tree','-r','-z',head,'--',*HISTORY).split(b'\0')
    for row in rows:
        if not row: continue
        info, path = row.split(b'\t',1)
        mode, kind, oid=info.split()
        name=path.decode(); p=R/name
        actual=digest(p.read_bytes()) if p.is_file() else None
        expected=digest(git('cat-file','blob',oid.decode()))
        if expected!=actual: head_history[name]={'head':expected,'worktree':actual}
    data={'head':head,'history':histories,'work':work,'status':status(),
          'history_vs_head':head_history,'index_sha256':digest((R/'.git/index').read_bytes()),
          'protected_vs_head':{n:git('show',head+':'+n)==(R/n).read_bytes() for n in PROTECTED}}
    dump(label+'.json',data)
    print(json.dumps({'snapshot':label,'head':head,'history_files':{h:len(v) for h,v in histories.items()},'history_vs_head':head_history,'status_count':len(data['status']),'protected_vs_head':data['protected_vs_head']},ensure_ascii=False))
    if label=='after':
        b=json.loads((V/'before.json').read_text())
        changes={section:[k for k in sorted(set(b[section])|set(data[section])) if b[section].get(k)!=data[section].get(k)] for section in ['history','work']}
        changes['index_unchanged']=b['index_sha256']==data['index_sha256']
        changes['head_unchanged']=b['head']==head
        dump('preservation-result.json',changes); print(json.dumps(changes,ensure_ascii=False))
def catalog(label='before'):
    sys.path.insert(0,str(S/'数据/工具'))
    import formal_catalog as f
    head=json.loads((V/(label+'.json')).read_text())['head']
    out=V/'head-sources';out.mkdir(exist_ok=True)
    for n in f.SOURCE_NAMES: (out/n).write_bytes(git('show',head+':'+n))
    snap=f.source_snapshot(out); proj=f.formal_projection(snap); rules='\n'.join(snap[0]['lines'])
    values={'schema':'static-catalog-v2','source_root':'../..','version':'2026-09-22-r25-bridge-bidirectional','sources':snap,
            'recipes':f.recipe_projection(rules),'units':list(f.unit_projection(rules,proj['constraints'],f.quantity).values()),**proj}
    # Key order is serialization metadata, independently inherited from the previous HEAD catalog.
    old=json.loads(git('show',head+':求解器/数据/正式静态目录.json'))
    # These unchanged documentation/serialization fields are not projections of formal rules.
    values['conventions']=old['conventions']
    values['transcribed_at']=old['transcribed_at']
    unit_by_id={u['id']:u for u in values['units']}
    values['units']=[unit_by_id[u['id']] for u in old['units']]
    rebuilt={k:values[k] for k in old}
    assert rebuilt.keys()==values.keys()
    f.verify(rebuilt,out)
    encoded=(json.dumps(rebuilt,ensure_ascii=False,indent=2)+'\n').encode()
    (V/'rebuilt-catalog.json').write_bytes(encoded)
    actual=(S/'数据/正式静态目录.json').read_bytes()
    result_name='catalog-result.json' if label=='before' else 'catalog-final-result.json'
    dump(result_name,{'head':head,'equal':encoded==actual,'actual_sha256':digest(actual),'rebuilt_sha256':digest(encoded),'keys':list(rebuilt),'constraints':len(proj['constraints']),'units':len(rebuilt['units']),'recipes':len(rebuilt['recipes'])})
    print((V/result_name).read_text())
def scan():
    before=json.loads((V/'before.json').read_text())
    result=[]; refs=[]; bad=[]
    new=digest((S/'数据/正式静态目录.json').read_bytes())
    for n in before['work']:
        p=R/n; data=p.read_bytes()
        if OLD.encode() in data:
            for line,text in enumerate(data.decode(errors='replace').splitlines(),1):
                if OLD in text: result.append({'path':n,'line':line,'text':text[:1000]})
        if p.suffix!='.json': continue
        try: doc=json.loads(data)
        except (ValueError,UnicodeError): continue
        def walk(v,loc=()):
            if isinstance(v,dict):
                if 'sha256' in v and '正式静态目录.json' in str(v.get('path','')):
                    row={'path':n,'field':'.'.join(map(str,loc)),'reference':v}
                    refs.append(row)
                    if not n.startswith('求解器/内核维护/') and v['sha256']!=new:bad.append(row)
                for k,w in v.items():walk(w,loc+(k,))
            elif isinstance(v,list):
                for i,w in enumerate(v):walk(w,loc+(i,))
        walk(doc)
    dump('old-sha-outside-history.json',result);dump('catalog-references.json',refs);dump('bad-active-catalog-references.json',bad)
    print(json.dumps({'old_sha_occurrences':len(result),'old_sha_files':len(set(x['path'] for x in result)),'catalog_reference_fields':len(refs),'bad_active_references':len(bad)},ensure_ascii=False))
    print(json.dumps([r for r in result if not r['path'].startswith('求解器/内核维护/')],ensure_ascii=False,indent=2))
if __name__=='__main__':
    {'before':lambda:snapshot('before'),'after':lambda:snapshot('after'),'catalog':catalog,'catalog-final':lambda:catalog('after'),'scan':scan}[sys.argv[1]]()
