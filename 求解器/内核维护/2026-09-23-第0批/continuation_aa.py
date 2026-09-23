"""Fixed-path A/A capture with raw-token comparison and recursive reference validation.

All previous capture directories are renamed into seals, never deleted. The
historical R2 rows supply argv templates only; prerequisites are newly generated.
"""
import argparse, hashlib, json, os, re, shutil, sys
from pathlib import Path
from continuation_guard import RUN, REPO, command, check, sha, write
from continuation_runtime import verify as verify_runtime, audit_trace

def strict_loads(raw):
    def pairs(items):
        result={}
        for k,v in items:
            assert k not in result,'duplicate key'
            result[k]=v
        return result
    return json.loads(raw,object_pairs_hook=pairs)

TIMED = {'run-no-output','run-no-output-no-cache','run-no-output-zero','run-no-output-stop','run-no-output-out'}

def tokens(raw):
    text=raw.decode('utf-8'); dec=json.JSONDecoder(); spans={}
    def whitespace(i):
        while i<len(text) and text[i] in ' \t\r\n': i+=1
        return i
    def value(i,pointer):
        i=whitespace(i); start=i
        if text[i]=='{':
            obj={}; i=whitespace(i+1)
            if text[i]!='}':
                while True:
                    key,end=dec.raw_decode(text,i); assert isinstance(key,str) and key not in obj,'duplicate key'
                    i=whitespace(end); assert text[i]==':'
                    child=pointer+'/'+key.replace('~','~0').replace('/','~1')
                    obj[key],i=value(i+1,child);i=whitespace(i)
                    if text[i]=='}':break
                    assert text[i]==',';i=whitespace(i+1)
            result=obj;i+=1
        elif text[i]=='[':
            result=[];i=whitespace(i+1)
            if text[i]!=']':
                while True:
                    item,i=value(i,pointer+'/'+str(len(result)));result.append(item);i=whitespace(i)
                    if text[i]==']':break
                    assert text[i]==',';i=whitespace(i+1)
            i+=1
        else: result,i=dec.raw_decode(text,i)
        spans[pointer]=(len(text[:start].encode()),len(text[:i].encode()),result)
        return result,i
    result,end=value(0,'');assert whitespace(end)==len(text)
    return result,spans

def compare_bytes(a,b,timed=False):
    # Validate JSON structure even when equal; reject duplicate keys.
    if a.lstrip().startswith((b'{',b'[')):strict_loads(a)
    if b.lstrip().startswith((b'{',b'[')):strict_loads(b)
    mapping=[]
    if timed:
        _,sa=tokens(a);_,sb=tokens(b)
        aa=sa['/elapsed_ns'];bb=sb['/elapsed_ns']
        for item in (aa,bb):assert isinstance(item[2],str) and re.fullmatch('[0-9]+',item[2]),'measurement type'
        mapping.append(dict(pointer='/elapsed_ns',a=aa[2],b=bb[2],a_token=a[aa[0]:aa[1]].decode(),b_token=b[bb[0]:bb[1]].decode()))
        b=b[:bb[0]]+a[aa[0]:aa[1]]+b[bb[1]:]
    assert a==b,'unregistered byte difference'
    return mapping

def references(path,allowed,cache=None,stack=None):
    cache={} if cache is None else cache;stack=[] if stack is None else stack
    path=Path(path).resolve();assert any(path.is_relative_to(x) for x in allowed),('reference outside closure',str(path))
    if path in stack:raise AssertionError(('reference cycle',list(map(str,stack+[path]))))
    if path in cache:return cache[path]
    raw=path.read_bytes();edges=[]
    if path.suffix not in ('.json','.log') or not raw.lstrip().startswith((b'{',b'[')):cache[path]=edges;return edges
    data=strict_loads(raw)
    def walk(v,pointer):
        if isinstance(v,dict):
            if isinstance(v.get('path'),str) and isinstance(v.get('sha256'),str):
                base=path.parent
                if isinstance(data,dict) and data.get('schema')=='static-catalog-v2' and pointer.startswith('/sources/'):
                    base=base/data['source_root']
                if isinstance(data,dict) and data.get('schema') in ['kernel-output-v4','kernel-cycle-v3'] and pointer.startswith(('/parameter_assignment/','/input_history/')):
                    inputs=[x for x in data['fingerprints'] if x['role']=='input'];assert len(inputs)==1
                    base=(path.parent/inputs[0]['path']).resolve().parent
                target=(base/v['path']).resolve();assert target.is_file(),('missing reference',str(target))
                actual=sha(target);assert actual==v['sha256'],('bad reference hash',str(path),pointer,str(target),actual,v['sha256'])
                sub=references(target,allowed,cache,stack+[path]);edges.append(dict(pointer=pointer,target=str(target),sha256=actual,nested_edges=len(sub),mapping='identity; original target bytes verified'))
            for k,x in v.items():walk(x,pointer+'/'+k.replace('~','~0').replace('/','~1'))
        elif isinstance(v,list):
            for i,x in enumerate(v):walk(x,pointer+'/'+str(i))
    walk(data,'');cache[path]=edges;return edges

def selftest(out):
    cases=[]
    def reject(name,fn):
        try:fn()
        except (AssertionError,KeyError,ValueError,FileNotFoundError) as e:cases.append(dict(name=name,rejected=True,error=str(e)))
        else:raise AssertionError('negative accepted: '+name)
    a=b'{"elapsed_ns":"1","value":[1,2]}\n'
    assert compare_bytes(a,b'{"elapsed_ns":"23","value":[1,2]}\n',True)
    for name,b in [('missing',b'{"value":[1,2]}\n'),('type',b'{"elapsed_ns":2,"value":[1,2]}\n'),('array-order',b'{"elapsed_ns":"1","value":[2,1]}\n'),('key-order',b'{"value":[1,2],"elapsed_ns":"1"}\n'),('indent',b'{ "elapsed_ns":"1","value":[1,2]}\n'),('duplicate',b'{"elapsed_ns":"1","elapsed_ns":"1","value":[1,2]}\n'),('unregistered',b'{"elapsed_ns":"1","value":[1,3]}\n')]:reject(name,lambda b=b:compare_bytes(a,b,True))
    reject('wrong-source-mapping',lambda:compare_bytes(b'{"producer":{"path":"/a"}}',b'{"producer":{"path":"/b"}}'))
    sandbox=REPO/'target/health-capture/continuation-20260923/comparator-negative';sandbox.mkdir()
    target=sandbox/'target.json';target.write_text('{}\n')
    bad=sandbox/'bad.json';write(bad,dict(path='target.json',sha256='0'*64));reject('bad-reference-hash',lambda:references(bad,[sandbox]))
    missing=sandbox/'missing.json';write(missing,dict(path='absent.json',sha256='0'*64));reject('missing-reference',lambda:references(missing,[sandbox]))
    write(out,dict(passed=True,cases=cases,token_preserving_positive=True))

def prepare():
    f=json.loads((RUN/'continuation-freeze.json').read_text());S=Path(f['source_root']);art=json.loads((RUN/'continuation-production-a-artifacts.json').read_text())
    bins={a['target']['name']:dict(path=a['executable'],sha256=a['sha256'],source_root=str(S),profile=f['continuation_profile']) for a in art if a.get('executable')}
    base=REPO/'内核维护/2026-09-22d/R2-来源与计时';rows=json.loads((base/'aa/results.json').read_text())
    assert len(rows)==44
    capture=REPO/'target/health-capture/continuation-20260923-v2/cases';capture.mkdir(parents=True,exist_ok=True)
    cases=[]
    for row in rows:
        cid=row['name'];root=capture/cid;argv=[]
        for x in row['argv']:
            if x==row['argv'][0]:x=bins['topology' if cid.startswith('topology') else 'kernel']['path']
            else:x=x.replace(str(base/'aa/artifacts'),str(root/'artifacts')).replace(str(base/'aa/batch'),str(root/'batch')).replace(str(REPO),str(S)) if not x.startswith(str(base/'aa')) else x.replace(str(base/'aa/artifacts'),str(root/'artifacts')).replace(str(base/'aa/batch'),str(root/'batch'))
            argv.append(x)
        # The topology contract is generated from the frozen resource, never the R2 product.
        if cid=='topology-contract':argv[1]=str(root/'artifacts/contract.json')
        prerequisites=[];k=bins['kernel']['path'];cfg=str(S/'规格/内核配置-v1.json');input_=str(S/'数据/样例/生产循环环带.json')
        def generate(name,cmd):prerequisites.append(dict(id=name,argv=[k,*map(str,cmd),'--config',cfg],expected=0))
        if cid in ('verify-record-full','checkpoint-record'):generate('generate-full',['run',input_,'--ticks',12,'--out',root/'artifacts/run-full.json'])
        if cid=='verify-record-delta':generate('generate-delta',['run',input_,'--ticks',12,'--format','checkpoint_delta','--checkpoint-interval',3,'--out',root/'artifacts/run-delta.json'])
        if cid in ('verify-cycle','checkpoint-cycle'):generate('generate-cycle',['cycle',input_,'--max-ticks',20,'--search-checkpoint-interval',3,'--out',root/'batch/cycle.json'])
        if cid in ('verify-cycle-found','checkpoint-cycle-found'):generate('generate-cycle-found',['cycle',input_,'--max-ticks',50,'--search-checkpoint-interval',3,'--out',root/'batch/cycle-found.json'])
        if cid.startswith('verify-batch'):
            generate('generate-finite-record',['run',input_,'--ticks',12,'--out',root/'batch/finite-record.json'])
            generate('generate-cycle',['cycle',input_,'--max-ticks',20,'--search-checkpoint-interval',3,'--out',root/'batch/cycle.json'])
            if cid.endswith('with-cycle-found'):generate('generate-cycle-found',['cycle',input_,'--max-ticks',50,'--search-checkpoint-interval',3,'--out',root/'batch/cycle-found.json'])
        inputs={x:sha(x) for x in argv if Path(x).is_file() and Path(x).is_relative_to(S)}
        cases.append(dict(id=cid,role='R2 branch template with fresh prerequisites',argv=argv,cwd=str(S),environment={'KERNEL_BIN':k,'PYTHONDONTWRITEBYTECODE':'1'},input_hashes=inputs,prerequisites=prerequisites,expected=row['expected_exit'] if row['expected_exit'] is not None else row['exit_codes'][0],root=str(root),outputs='complete file tree including each prerequisite stdout/stderr, generated input, records and certificates'))
    fields=[dict(case_id=x,artifact='artifacts/run-no-output-out.json' if x=='run-no-output-out' else 'main.stdout.log',pointer='/elapsed_ns',contract='decimal nonnegative integer string',basis='plan 3.5 original five R2 fields') for x in sorted(TIMED)]
    write(RUN/'cases.json',cases);write(RUN/'binaries.json',bins);write(RUN/'comparison-fields.json',fields)
    return f,cases,bins,fields

def capture_case(case,label,f,bins):
    root=Path(case['root']);assert not root.exists();root.mkdir();(root/'artifacts').mkdir();(root/'batch').mkdir()
    (root/'.exclusive.json').write_text(json.dumps(dict(case_id=case['id'],root=str(root))))
    S=Path(f['source_root']);(root/'artifacts/bad-input.json').write_text('{}\n')
    if case['id']=='topology-contract':
        contract=json.loads((S/'数据/候选B/contract.json').read_text());(root/'artifacts/contract.json').write_text(json.dumps(contract,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    results=[]
    for step in [*case['prerequisites'],dict(id='main',argv=case['argv'],expected=case['expected'])]:
        for b in bins.values():assert sha(b['path'])==b['sha256']
        for x in f['files']:assert sha(Path(f['root'])/x['path'])==x['sha256']
        ident='continue-aa-'+case['id']+'-'+label+'-'+step['id']
        verify_runtime()
        trace=RUN/(ident+'.trace.log')
        result=command(ident,['strace','-f','-qq','-yy','-s','4096','-e','trace=openat,openat2,execve,chdir','-o',str(trace),*step['argv']],S,step['expected'],case['environment'])
        reads=audit_trace(trace,Path(f['root']),[root],executables=[x['path'] for x in bins.values()])
        write(RUN/(ident+'.reads.json'),reads)
        result['argv']=step['argv']
        for channel in ('stdout','stderr'):shutil.copyfile(RUN/(ident+'.'+channel+'.log'),root/(step['id']+'.'+channel+'.log'))
        results.append(dict(step=step['id'],returncode=result['returncode'],argv=result['argv']))
    edges={};cache={}
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name!='.exclusive.json':edges[str(p.relative_to(root))]=references(p,[Path(f['root']),root],cache)
    hashes={str(p.relative_to(root)):dict(sha256=sha(p),size=p.stat().st_size) for p in sorted(root.rglob('*')) if p.is_file()}
    seal=root.parent.parent/'sealed'/case['id']/label;seal.parent.mkdir(parents=True,exist_ok=True);assert not seal.exists()
    root.rename(seal)
    for p,v in hashes.items():assert sha(seal/p)==v['sha256']
    result=dict(case_id=case['id'],label=label,root=str(root),sealed=str(seal),files=hashes,steps=results,references=edges)
    write(RUN/('capture-'+case['id']+'-'+label+'.json'),result)
    return result

def compare_capture(a,b,fields):
    assert a['case_id']==b['case_id'] and a['files'].keys()==b['files'].keys()
    assert a['steps']==b['steps'];mappings=[]
    selected={x['artifact']:x for x in fields if x['case_id']==a['case_id']}
    for name in sorted(a['files']):
        raw_a=(Path(a['sealed'])/name).read_bytes();raw_b=(Path(b['sealed'])/name).read_bytes()
        assert hashlib.sha256(raw_a).hexdigest()==a['files'][name]['sha256'];assert hashlib.sha256(raw_b).hexdigest()==b['files'][name]['sha256']
        mapping=compare_bytes(raw_a,raw_b,name in selected)
        if mapping:mappings.append(dict(artifact=name,**mapping[0]))
    assert all(k in a['files'] for k in selected)
    return dict(case_id=a['case_id'],passed=True,files=len(a['files']),mappings=mappings,references='all original target hashes validated before sealing; fixed-path identity mapping')

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['aa','selftest']);args=p.parse_args()
    check('aa-start')
    if args.action=='selftest':selftest(RUN/'continuation-comparator-selftest.json');check('aa-selftest-after');return
    f,cases,bins,fields=prepare();results=[]
    completed={x['case_id'] for x in json.loads((RUN/'continuation-aa-results.json').read_text())} if (RUN/'continuation-aa-results.json').exists() else set()
    for case in cases:
        if case['id'] in completed:
            a=json.loads((RUN/('capture-'+case['id']+'-a.json')).read_text());b=json.loads((RUN/('capture-'+case['id']+'-b.json')).read_text())
            assert Path(a['root'])==Path(case['root']) and Path(b['root'])==Path(case['root'])
        else:
            a=capture_case(case,'a',f,bins);b=capture_case(case,'b',f,bins)
        results.append(compare_capture(a,b,fields));write(RUN/'continuation-aa-results.json',results);print('A/A passed',case['id'],flush=True)
    write(RUN/'continuation-aa-passed.json',dict(passed=True,cases=len(results),bindings='binaries.json',fields='comparison-fields.json',freeze='continuation-freeze.json'))
    check('aa-final')

if __name__=='__main__':main()
