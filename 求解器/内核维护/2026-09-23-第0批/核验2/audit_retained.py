"""Recompute archived A/A bytes and recursive original reference hashes."""
import json,hashlib,re,sys
from audit_files import *
def load(raw):
    def pairs(items):
        d={}
        for k,v in items:
            assert k not in d,('duplicate key',k);d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs)
def elapsed_span(raw):
    s=raw.decode();dec=json.JSONDecoder();i=0
    def ws(n):
        while n<len(s) and s[n].isspace():n+=1
        return n
    i=ws(i);assert s[i]=='{';i=ws(i+1);found=[]
    while s[i]!='}':
        key,j=dec.raw_decode(s,i);j=ws(j);assert s[j]==':';j=ws(j+1);value,end=dec.raw_decode(s,j)
        if key=='elapsed_ns':found.append((len(s[:j].encode()),len(s[:end].encode()),value))
        i=ws(end)
        if s[i]=='}':break
        assert s[i]==',';i=ws(i+1)
    assert len(found)==1;begin,end,value=found[0];assert isinstance(value,str) and re.fullmatch('[0-9]+',value)
    return begin,end,value
def compare(rawa,rawb,timed):
    for raw in [rawa,rawb]:
        if raw.lstrip().startswith((b'{',b'[')):load(raw)
    mapping=None
    if timed:
        ia,ja,a=elapsed_span(rawa);ib,jb,b=elapsed_span(rawb);rawb=rawb[:ib]+rawa[ia:ja]+rawb[jb:];mapping=dict(a=a,b=b)
    assert rawa==rawb,'non-whitelisted raw byte difference'
    return mapping
def main(owner,prefix,casefile,fieldsfile,index=None):
    cases=json.loads(casefile.read_text());fields=json.loads(fieldsfile.read_text());timed={x['case_id']:x['artifact'] for x in fields}
    expected={'run-no-output','run-no-output-no-cache','run-no-output-zero','run-no-output-stop','run-no-output-out'}
    assert len(cases)==44 and len({c['id'] for c in cases})==44 and set(timed)==expected and len(fields)==5
    assert all(x['pointer']=='/elapsed_ns' and x['artifact']==('artifacts/run-no-output-out.json' if x['case_id']=='run-no-output-out' else 'main.stdout.log') for x in fields)
    F=Path(cases[0]['cwd']).parent;results=[];closures=[];total_files=0
    def capture(cid,label):
        return next(x for x in index if x['case_id']==cid and x['label']==label) if index else json.loads((owner/f'capture-{cid}-{label}.json').read_text())
    for case in cases:
        a=capture(case['id'],'a');b=capture(case['id'],'b');assert a['root']==b['root']==case['root'] and a['steps']==b['steps'];assert a['files'].keys()==b['files'].keys()
        mappings=[]
        for rel in a['files']:
            pa=Path(a['sealed'])/rel;pb=Path(b['sealed'])/rel;ra=pa.read_bytes();rb=pb.read_bytes()
            assert sha(pa)==a['files'][rel]['sha256'] and sha(pb)==b['files'][rel]['sha256'] and len(ra)==a['files'][rel]['size'] and len(rb)==b['files'][rel]['size']
            mapping=compare(ra,rb,rel==timed.get(case['id']))
            if mapping:mappings.append(dict(artifact=rel,pointer='/elapsed_ns',**mapping))
            total_files+=1
        results.append(dict(case_id=case['id'],passed=True,files=len(a['files']),mappings=mappings))
        for cap in [a,b]:
            root=Path(cap['root']);seal=Path(cap['sealed']);seen={};stack=[]
            def physical(p):return seal/p.relative_to(root) if p.is_relative_to(root) else p
            def visit(p):
                p=p.resolve();assert p.is_relative_to(F) or p.is_relative_to(root),('reference escape',p)
                assert p not in stack,('cycle',p)
                if p in seen:return
                raw=physical(p).read_bytes();edges=[];stack.append(p)
                if p.suffix in ['.json','.log'] and raw.lstrip().startswith((b'{',b'[')):
                    data=load(raw)
                    def walk(obj,pointer):
                        if isinstance(obj,dict):
                            if isinstance(obj.get('path'),str) and isinstance(obj.get('sha256'),str):
                                base=p.parent
                                if isinstance(data,dict) and data.get('schema')=='static-catalog-v2' and pointer.startswith('/sources/'):base=base/data['source_root']
                                if isinstance(data,dict) and data.get('schema') in ['kernel-output-v4','kernel-cycle-v3'] and pointer.startswith(('/parameter_assignment/','/input_history/')):
                                    inputs=[x for x in data['fingerprints'] if x['role']=='input'];assert len(inputs)==1;base=(p.parent/inputs[0]['path']).resolve().parent
                                target=(base/obj['path']).resolve();q=physical(target);actual=sha(q);assert actual==obj['sha256'],('reference hash mismatch',p,pointer,target)
                                edges.append(dict(pointer=pointer,target=str(target),physical=str(q),sha256=actual));visit(target)
                            for k,v in obj.items():walk(v,pointer+'/'+k.replace('~','~0').replace('/','~1'))
                        elif isinstance(obj,list):
                            for i,v in enumerate(obj):walk(v,pointer+'/'+str(i))
                    walk(data,'')
                stack.pop();seen[p]=edges
            for rel in cap['files']:
                if rel!='.exclusive.json':visit(root/rel)
            closures.append(dict(case_id=case['id'],label=cap['label'],edges={str(k):v for k,v in seen.items()}))
    save(prefix+'-aa.json',dict(passed=True,pairs=len(results),paired_files=total_files,measurements=sum(len(r['mappings']) for r in results),results=results))
    save(prefix+'-references.json',dict(passed=True,captures=len(closures),edges=sum(len(es) for r in closures for es in r['edges'].values()),closures=closures))
    print(prefix,'44 pairs',total_files,'paired files','five measurements; references verified')
if __name__=='__main__':
    if len(sys.argv)>1:
        main(OUT,'fresh-independent',OUT/'own-cases.json',OUT/'own-fields.json',json.loads((OUT/'own-capture-index.json').read_text()))
    else:main(IMPL,'retained-independent',IMPL/'cases.json',IMPL/'comparison-fields.json')
