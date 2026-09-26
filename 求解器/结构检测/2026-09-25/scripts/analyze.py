#!/usr/bin/env python3
"""Convert cuts to a deterministic vertex separator and verify disconnection."""
import collections,json,math,os,sys,time
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
from scipy.sparse import csr_matrix,bmat,load_npz
from scipy.sparse.csgraph import connected_components
OUT=Path(__file__).resolve().parents[1]
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def entropy(counts):
    a=np.asarray(counts,dtype=float);a=a[a>0];a/=a.sum()
    return float(-np.sum(a*np.log(a))) if len(a) else 0.
def nmi(a,b):
    if not len(a):return 0.
    _,aa=np.unique(a,return_inverse=True);_,bb=np.unique(b,return_inverse=True)
    C=np.zeros((max(aa)+1,max(bb)+1),dtype=np.int64);np.add.at(C,(aa,bb),1)
    pa=C.sum(axis=1);pb=C.sum(axis=0);ii,jj=np.nonzero(C);N=len(a)
    mi=np.sum(C[ii,jj]/N*np.log(C[ii,jj]*N/(pa[ii]*pb[jj])))
    den=entropy(pa)+entropy(pb)
    return float(2*mi/den) if den else 0.
def ordered(counter):return dict(sorted(counter.items(),key=lambda q:(-q[1],str(q[0]))))
def family(v):
    return {'ore':'矿石子集层','all':'全体物品合计层','geometry':'几何及选择'}[v['layer']]+'／'+v['family']
def summarize(ids,variables,with_examples=True):
    by=collections.Counter();examples=collections.defaultdict(list);layers=collections.Counter();xy=[];regions=collections.Counter();detail={}
    for i in ids:
        v=variables[int(i)];f=family(v);by[f]+=1;layers[v['layer']]+=1
        fd=detail.setdefault(f,dict(regions=collections.Counter(),directions=collections.Counter(),input_sides=collections.Counter(),points=[]))
        if 'direction' in v:fd['directions'][['东','北','西','南'][v['direction']]]+=1
        vv=variables[v['parent_variable']] if 'parent_variable' in v else v
        if 'input_side' in vv:
            side=(['西','东'] if vv['axis']==0 else ['南','北'])[vv['input_side']]
            fd['input_sides'][side]+=1
        if len(examples[f])<3:examples[f].append(dict(id=v['id'],name=v['name'],xy=v['xy'],direction=v.get('direction'),kind=v.get('kind')))
        if v['xy'] is not None:
            x,y=v['xy'];xy.append((x,y));region=('东' if x>=35 else '西')+('北' if y>=35 else '南');regions[region]+=1;fd['regions'][region]+=1;fd['points'].append((x,y))
        else:regions['无空间代表点']+=1;fd['regions']['无空间代表点']+=1
    xy=np.asarray(xy)
    r=dict(count=len(ids),families=ordered(by),layers=ordered(layers),regions=ordered(regions),xy_bbox=([*xy.min(axis=0),*xy.max(axis=0)] if len(xy) else None))
    for f,fd in detail.items():
        ps=np.asarray(fd.pop('points'));fd['xy_bbox']=[*ps.min(axis=0),*ps.max(axis=0)] if len(ps) else None
        for key in ('regions','directions','input_sides'):fd[key]=ordered(fd[key])
    r['family_details']=detail
    if with_examples:r['examples']=dict(examples)
    return r
def spatial_signature(part,vids,variables,k,keep=None):
    if keep is None:keep=np.ones(len(part),dtype=bool)
    sel=np.flatnonzero(keep);withxy=[i for i in sel if variables[vids[i]]['xy'] is not None]
    points=np.array([variables[vids[i]]['xy'] for i in withxy]);parts=part[withxy]
    cells=(np.floor(points[:,0]).astype(int)*100+np.floor(points[:,1]).astype(int)) if len(points) else np.array([],dtype=int)
    coarse=(np.floor(points[:,0]/7).astype(int)*20+np.floor(points[:,1]/7).astype(int)) if len(points) else np.array([],dtype=int)
    if len(cells):
        _,inv=np.unique(cells,return_inverse=True);C=np.zeros((max(inv)+1,k),dtype=int);np.add.at(C,(inv,parts),1);agreement=float(C.max(axis=1).sum()/C.sum())
    else:agreement=None
    fams=np.array([family(variables[vids[i]]) for i in withxy]);layers=np.array([variables[vids[i]]['layer'] for i in withxy])
    fn=nmi(parts,fams);sn=nmi(parts,coarse);ln=nmi(parts,layers)
    # These are declared descriptive thresholds, not optimality scores.
    if len(np.unique(part[sel]))<2:label='只剩一个非空组，未形成多组分隔'
    elif agreement is not None and agreement<.8 and fn>sn and fn>=.2:label='非地域：变量类别或流量层分组明显'
    elif agreement is not None and agreement>=.85 and sn>fn:label='以地域为主'
    else:label='地域与变量类别混合，不能只凭分组称为按物品或生产链'
    return dict(label=label,same_cell_majority_agreement=agreement,nmi_with_7x7_regions=sn,nmi_with_families=fn,nmi_with_layers=ln,coordinate_variables=len(withxy))

def evaluate(dataset):
    root=OUT/'raw'/dataset;meta=json.loads((root/'input.json').read_text());model=meta['model'];z=np.load(root/'input.npz');vids=z['variable_ids'];cids=z['constraint_ids'];source=z['source'];off=z['offsets'];pins=z['pins'];gm=z['global_mask'];variables=json.loads((OUT/'models'/model/'variables.json').read_text());sources=json.loads((OUT/'models'/model/'constraint_sources.json').read_text());n=len(vids);m=len(cids)
    A=csr_matrix((np.ones(len(pins),dtype=np.int32),pins,off),shape=(m,n));sizes=np.diff(off)
    for file in sorted((root/'partitions').glob('*.json')):
        target=root/'analyses'/file.name
        if target.exists() and 'family_details' in json.loads(target.read_text())['separator_summary']:continue
        target.parent.mkdir(exist_ok=True)
        start=time.monotonic();p=json.loads(file.read_text());k=p['k'];part=np.array(p['part'],dtype=np.int32);active=~gm if p['mode']=='noglobal' else np.ones(m,dtype=bool)
        memberships=np.eye(k,dtype=np.int32)[part];counts=A@memberships;span=(counts>0).sum(axis=1);rawcut=(span>1)&active
        if p['algorithm']=='kahypar':
            assert int(rawcut.sum())==p['reported_cut']
            assert int(np.maximum(span[active]-1,0).sum())==p['reported_km1']
        # A constructive cover of all inter-part edges of the clique graph:
        # process cut hyperedges by descending original arity, then row ID;
        # retain the largest currently unselected block in each edge, put all
        # other incident vertices into S (ties choose smaller block ID).
        sep=np.zeros(n,dtype=bool);cutids=np.flatnonzero(rawcut)
        order=cutids[np.lexsort((cids[cutids],-sizes[cutids]))]
        for row in order:
            edge=pins[off[row]:off[row+1]];free=edge[~sep[edge]]
            if len(free)<2:continue
            cnt=np.bincount(part[free],minlength=k)
            if np.count_nonzero(cnt)<=1:continue
            stay=int(np.argmax(cnt));sep[free[part[free]!=stay]]=True
        free_memberships=memberships.copy();free_memberships[sep]=0
        left=A@free_memberships;leftspan=(left>0).sum(axis=1);sep_inc=A@sep.astype(np.int32)
        assert not np.any((leftspan>1)&active),'Uncovered crossing row'
        # L includes every row coupling S to a surviving group, plus every
        # explicitly lifted global row, including rows wholly in the master.
        links=((sep_inc>0)&(leftspan>0))|((leftspan>1)&~active)|(~active)
        masters=(sep_inc>0)&(leftspan==0)
        removed_spanning=(~active)&(leftspan>1)
        free=np.flatnonzero(~sep);C=A[active][:,free];C=C[np.diff(C.indptr)>0]
        incgraph=bmat([[None,C.T],[C,None]],format='csr',dtype=bool)
        _,cc=connected_components(incgraph,directed=False,return_labels=True)
        comp_ids,comp_sizes=np.unique(cc[:len(free)],return_counts=True)
        comps_by_block=[]
        for block in range(k):
            labs=cc[:len(free)][part[free]==block];_,cs=np.unique(labs,return_counts=True)
            comps_by_block.append(dict(count=len(cs),largest=int(max(cs)) if len(cs) else 0,smallest=int(min(cs)) if len(cs) else 0,singletons=int(np.sum(cs==1))))
        bylink=collections.Counter(sources[source[i]]['category'] for i in np.flatnonzero(links));bycut=collections.Counter(sources[source[i]]['category'] for i in cutids)
        examples={}
        for i in np.flatnonzero(links):
            s=sources[source[i]];key=s['category']
            if key not in examples:examples[key]=dict(constraint_id=int(cids[i]),file=s['file'],line=s['line'],global_constraint=s['global_constraint'])
        block_summaries=[]
        for block in range(k):
            local=np.flatnonzero((part==block)&~sep);s=summarize(vids[local],variables,False);s.update(block=block,raw_variables=int(np.sum(part==block)),components=comps_by_block[block]);block_summaries.append(s)
        graph_check=None
        if p['algorithm']=='metis':
            G=load_npz(root/f"graph_{p['mode']}.npz");twocut=0
            for first in range(0,n,2048):
                last=min(n,first+2048);lo=G.indptr[first];hi=G.indptr[last];leftparts=np.repeat(part[first:last],np.diff(G.indptr[first:last+1]));twocut+=int(np.sum(leftparts!=part[G.indices[lo:hi]]))
            assert twocut%2==0 and twocut//2==p['reported_edge_cut']
            graph_check=dict(edge_cut_recomputed=twocut//2,passed=True)
        result=dict(dataset=dataset,model=model,scope=meta['scope'],algorithm=p['algorithm'],mode=p['mode'],k=k,variables=n,constraints=m,active_constraints=int(active.sum()),global_constraints=int(gm.sum()),raw_block_sizes=p['raw_block_sizes'],separator_variables=int(sep.sum()),separator_variable_ids=vids[sep].tolist(),linking_constraints=int(links.sum()),linking_constraint_ids=cids[links].tolist(),raw_cut_constraints=int(rawcut.sum()),raw_cut_constraint_ids=cids[rawcut].tolist(),master_only_constraints=int(masters.sum()),removed_global_rows_still_spanning_blocks=int(removed_spanning.sum()),remaining_block_sizes=[b['count'] for b in block_summaries],remaining_max_block=max(b['count'] for b in block_summaries),remaining_min_block=min(b['count'] for b in block_summaries),actual_connected_components=len(comp_sizes),actual_largest_component=int(max(comp_sizes)) if len(comp_sizes) else 0,actual_smallest_component=int(min(comp_sizes)) if len(comp_sizes) else 0,actual_singleton_components=int(np.sum(comp_sizes==1)),component_size_histogram=ordered(collections.Counter(map(int,comp_sizes))),separator_summary=summarize(vids[sep],variables),linking_constraint_categories=ordered(bylink),cut_constraint_categories=ordered(bycut),linking_constraint_examples=examples,blocks=block_summaries,raw_partition_signature=spatial_signature(part,vids,variables,k),remaining_partition_signature=spatial_signature(part,vids,variables,k,~sep),verification=dict(active_rows_crossing_after_separator=0,connected_components_checked=True,graph_cut_check=graph_check,all_original_rows_independent_after_fixing_S=meta['scope']=='whole' and not np.any(leftspan>1)),partition_seconds=p['seconds'],analysis_seconds=time.monotonic()-start,separator_method='descending hyperedge arity, keep largest unremoved block, tie lowest block ID; constructive edge cover, not minimum')
        dump(target,result)
        print(json.dumps({key:result[key] for key in ['dataset','algorithm','mode','k','separator_variables','linking_constraints','remaining_block_sizes','actual_connected_components','raw_partition_signature','analysis_seconds']},ensure_ascii=False),flush=True)

if __name__=='__main__':
    for name in sys.argv[1:]:evaluate(name)
