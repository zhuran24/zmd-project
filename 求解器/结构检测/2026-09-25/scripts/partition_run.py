#!/usr/bin/env python3
"""Run partitioners only; never instantiate a CP-SAT or MIP solver."""
import argparse,json,os,resource,time
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from scipy.sparse import csr_matrix,load_npz,save_npz
OUT=Path(__file__).resolve().parents[1]
SEED=20260925
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('dataset');ap.add_argument('algorithm',choices=['kahypar','metis','manual']);ap.add_argument('mode',choices=['full','noglobal']);ap.add_argument('--ks',default='2,4,8');ap.add_argument('--config',default='km1_kKaHyPar_eco_sea20.ini');a=ap.parse_args()
    p=OUT/'raw'/a.dataset;z=np.load(p/'input.npz');n=len(z['variable_ids']);active=np.flatnonzero(~z['global_mask']) if a.mode=='noglobal' else np.arange(len(z['constraint_ids']));A=csr_matrix((np.ones(len(z['pins']),dtype=bool),z['pins'],z['offsets']),shape=(len(z['constraint_ids']),n));B=A[active]
    output=p/'partitions';output.mkdir(exist_ok=True)
    if a.algorithm=='metis':
        import pymetis
        cache=p/f'graph_{a.mode}.npz';t=time.monotonic()
        if cache.exists():G=load_npz(cache)
        else:
            G=(B.T@B).tocsr();G.setdiag(False);G.eliminate_zeros();G.sort_indices()
            assert (G!=G.T).nnz==0
            save_npz(cache,G)
        graph_seconds=time.monotonic()-t
        adj=pymetis.CSRAdjacency(np.asarray(G.indptr,dtype=pymetis.zero_copy_dtype()),np.asarray(G.indices,dtype=pymetis.zero_copy_dtype()))
        dump(p/f'graph_{a.mode}.json',dict(vertices=n,edges=G.nnz//2,clique_expansion='boolean B.T @ B, remove diagonal, simple undirected graph',construction_or_load_seconds=graph_seconds))
    if a.algorithm=='kahypar':
        import kahypar
        # Empty and singleton edges have zero cut cost for any partition.
        H=B[np.diff(B.indptr)>=2];offsets=H.indptr.tolist();pins=H.indices.tolist()
    if a.algorithm=='manual':
        variables=json.loads((OUT/'models'/a.dataset.rsplit('_',1)[0]/'variables.json').read_text())
    for k in map(int,a.ks.split(',')):
        file=output/f'{a.algorithm}_{a.mode}_k{k}.json'
        if file.exists():continue
        started=time.monotonic();extra={}
        print(json.dumps(dict(event='partition_start',dataset=a.dataset,algorithm=a.algorithm,mode=a.mode,k=k)),flush=True)
        if a.algorithm=='metis':
            result=pymetis.part_graph(k,adjacency=adj,recursive=False,options=pymetis.Options(seed=SEED,ufactor=30,ncuts=1,niter=10))
            part=list(result.vertex_part);extra['reported_edge_cut']=int(result.edge_cuts);extra['graph_edges']=G.nnz//2
        elif a.algorithm=='kahypar':
            h=kahypar.Hypergraph(n,H.shape[0],offsets,pins,k)
            ctx=kahypar.Context();ctx.loadINIconfiguration(str(OUT/'tools'/a.config));ctx.setK(k);ctx.setEpsilon(.03);ctx.setSeed(SEED);ctx.suppressOutput(True)
            kahypar.partition(h,ctx);part=[h.blockID(i) for i in range(n)]
            extra.update(objective='connectivity_minus_one',config=a.config,reported_km1=int(kahypar.connectivityMinusOne(h)),reported_cut=int(kahypar.cut(h)),partitioned_hyperedges=H.shape[0])
        else:
            assert k==4
            # A fixed four-quadrant geographic reference; no balancing step.
            # Coordinate-free bookkeeping variables go in the southwest group.
            part=[]
            split=23 if a.dataset.endswith('_window') else 35
            for i in z['variable_ids']:
                xy=variables[i]['xy']
                if xy is None:part.append(0)
                else:
                    x,y=xy;part.append(int(x>=split)+2*int(y>=split))
            extra['rule']=f'按变量代表点分四象限：x={split}、y={split}；无坐标变量归西南片。不做数量配平。'
        assert len(part)==n and all(0<=v<k for v in part)
        seconds=time.monotonic()-started
        record=dict(dataset=a.dataset,algorithm=a.algorithm,mode=a.mode,k=k,seed=SEED,epsilon=.03 if a.algorithm!='manual' else None,seconds=seconds,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,raw_block_sizes=np.bincount(part,minlength=k).tolist(),part=part,**extra)
        dump(file,record)
        print(json.dumps({key:v for key,v in record.items() if key!='part'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
