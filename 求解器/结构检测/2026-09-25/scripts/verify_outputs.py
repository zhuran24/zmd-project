#!/usr/bin/env python3
"""Independent protobuf incidence and separator audit; no solver calls."""
import collections,hashlib,json,sys,time
from pathlib import Path
import numpy as np
from ortools.sat import cp_model_pb2
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parents[2]
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def audit_model(name):
    p=OUT/'models'/name;proto=cp_model_pb2.CpModelProto();data=(p/'model.pb').read_bytes();proto.ParseFromString(data);meta=json.loads((p/'metadata.json').read_text());z=np.load(p/'incidence.npz');offsets=z['offsets'];pins=z['pins'];allrefs=[];enforced=negative=0
    for i,c in enumerate(proto.constraints):
        typ=c.WhichOneof('constraint');r=list(c.enforcement_literal);enforced+=bool(r)
        if typ=='linear':r+=list(c.linear.vars)
        elif typ in ('bool_or','bool_and','exactly_one','at_most_one','bool_xor'):r+=list(getattr(c,typ).literals)
        elif typ=='table':
            r+=list(c.table.vars)
            for e in c.table.exprs:r+=list(e.vars)
        else:raise AssertionError('Unexpected actual constraint type '+str(typ))
        negative+=sum(x<0 for x in r)
        refs=sorted({x if x>=0 else -x-1 for x in r});a,b=offsets[i:i+2]
        assert refs==pins[a:b].tolist(),(name,i,'incidence differs')
        allrefs.append(refs)
    assert hashlib.sha256(data).hexdigest()==meta['model_sha256']
    assert len(proto.variables)==meta['variables'] and len(proto.constraints)==meta['constraints']
    changed=[]
    for f in meta['sources']:
        path=ROOT/f['file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=f['sha256']:changed.append(f['file'])
    result=dict(model=name,variables=len(proto.variables),constraints=len(proto.constraints),all_constraint_incidence_equal=True,enforced_constraints=enforced,negative_references_checked=negative,source_files_changed_since_build=changed,model_sha256=meta['model_sha256'])
    if name=='residual75':
        old=json.loads((ROOT/'求解器/候选约束轮次/第75-77轮/推导75/residual_global_A.json').read_text())
        result['existing_build_metadata_match']={key:(meta[key]==old[key]) for key in ('variables','constraints')}
        result['existing_build_metadata_match']['centers']=meta['settings']['centers']==old['center_count']
        result['existing_build_metadata_match']['groups']=meta['settings']['groups']==old['group_count']
        assert all(result['existing_build_metadata_match'].values())
    return result,allrefs

def main():
    started=time.monotonic();models=[];runs=[];refs={}
    for name in ('flow_all','flow_ore','geometry','residual75'):
        r,rr=audit_model(name);models.append(r);refs[name]=rr
        print(json.dumps(dict(event='model_incidence_passed',model=name)),flush=True)
    for root in sorted((OUT/'raw').iterdir()):
        if not (root/'input.json').exists():continue
        meta=json.loads((root/'input.json').read_text());z=np.load(root/'input.npz');vids=z['variable_ids'];cids=z['constraint_ids'];pins=z['pins'];offsets=z['offsets'];globalmask=z['global_mask'];included=set(map(int,vids));origrefs=refs[meta['model']]
        for i,cid in enumerate(cids):
            expected=sorted(set(origrefs[cid])&included)
            got=sorted(map(int,vids[pins[offsets[i]:offsets[i+1]]]))
            assert expected==got,(root.name,int(cid),'restricted incidence differs')
        for file in sorted((root/'analyses').glob('*.json')):
            a=json.loads(file.read_text());p=json.loads((root/'partitions'/file.name).read_text());assignment=dict(zip(map(int,vids),p['part']));sep=set(a['separator_variable_ids']);activec=set(map(int,cids[~globalmask])) if a['mode']=='noglobal' else set(map(int,cids));left=[0]*a['k'];links=[];cross=[];bad=[];master=[];removedcross=[]
            for v,b in assignment.items():
                if v not in sep:left[b]+=1
            for cid in cids:
                r=set(origrefs[cid])&included
                rawparts={assignment[v] for v in r};parts={assignment[v] for v in r if v not in sep};hasS=bool(r&sep);active=cid in activec
                if active and len(rawparts)>1:cross.append(int(cid))
                if active and len(parts)>1:bad.append(int(cid))
                if (hasS and parts) or (not active):links.append(int(cid))
                if hasS and not parts:master.append(int(cid))
                if not active and len(parts)>1:removedcross.append(int(cid))
            assert not bad,(file,bad[:5])
            assert left==a['remaining_block_sizes']
            assert links==a['linking_constraint_ids']
            assert cross==a['raw_cut_constraint_ids']
            assert len(master)==a['master_only_constraints']
            assert len(removedcross)==a['removed_global_rows_still_spanning_blocks']
            assert len(sep)+sum(left)==a['variables']
            assert sum(a['separator_summary']['families'].values())==len(sep)
            assert sum(a['linking_constraint_categories'].values())==len(links)
            runs.append(dict(dataset=root.name,result=file.name,separator_count=len(sep),linking_constraint_count=len(links),active_crossing_constraints_after_fixing=0,passed=True))
        print(json.dumps(dict(event='dataset_passed',dataset=root.name,results_so_far=len(runs))),flush=True)
    result=dict(status='passed',models=models,results=runs,result_count=len(runs),seconds=time.monotonic()-started,checked='independent direct protobuf references, signed literals, restricted input incidence, every separator and linking-row set; no model solving')
    dump(OUT/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('results','models')},ensure_ascii=False))

if __name__=='__main__':main()
