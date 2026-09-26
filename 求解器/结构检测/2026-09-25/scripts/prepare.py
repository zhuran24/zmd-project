#!/usr/bin/env python3
"""Semantic row classification and lossless full / restricted incidence inputs."""
import collections,json,sys,time
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix,save_npz
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parents[2]

GEOMETRY={23:('仓库取货口联合边带模式恰选一个',True),27:('仓库取货口邻格支撑',False),39:('制造单位两边端口邻格',False),40:('制造单位按尺寸的总台数',True),61:('协议核心取货端口邻格',False),62:('协议核心存货端口邻格',False),63:('协议核心与仓库取货口走廊兼容',False),64:('协议核心总数',True),74:('供电桩总数定义',True),75:('占边供电桩总数定义',True),77:('供电桩总数与占边数预算',True),78:('供电亏额总预算',True),85:('供电桩二维前缀和递推',False),90:('制造单位得电覆盖',False),94:('逐格结构占用定义',False),95:('结构、运输格及仓库取货口占用互斥',False),96:('运输格总数下限',True),101:('边带缺格条件下的运输格总数',True),111:('面积缺口总账',True),112:('供电桩总数面积预算',True)}
RELAX={**{l:v for l,v in GEOMETRY.items() if l<=75},76:GEOMETRY[77],77:GEOMETRY[78],84:GEOMETRY[85],89:GEOMETRY[90],93:GEOMETRY[94],94:GEOMETRY[95],95:GEOMETRY[96],100:GEOMETRY[101],109:GEOMETRY[111],110:GEOMETRY[112]}
FLOW={76:('桥接器与运输格状态兼容',False),77:('运输格与桥接器总数下限',True),97:('几何摆位与机型、存货边细分',False),101:('制造单位按机型的总台数',True),154:('相邻运输格流量起点支撑',False),155:('相邻运输格流量终点支撑',False),165:('制造单位或协议核心端口流量支撑',False),166:('端口流量的运输格支撑',False),163:('仓库取货口或协议核心满速取货',False),59:('逐运输格流量收支守恒',False),60:('逐运输格与桥接器容量',False),64:('桥接器单轴流量收支守恒',False),65:('桥接器单轴容量',False),185:('矿石合计收量与机型选择',False),186:('逐台矿石收量与存货端口对应',False),204:('粉碎机矿石总收量',True),205:('精炼炉矿石总收量',True),194:('逐台全体物品合计收量或出量定值',False),197:('逐台全体物品收出量下界',False),198:('逐台全体物品收出量上界',False),199:('逐台全体物品收出量与端口对应',False),208:('按机型汇总的全体物品收出量',True),210:('协议核心成品存货量下限',False)}
GLOBAL={23:('全制造单位全体物品总收量',True),24:('全制造单位全体物品总出量',True),25:('协议核心全体物品总存货量',True),27:('全体物品运输弧与运输格容量总账',True)}
CP72={64:('逐格结构占用定义',False),66:('保留单位端口邻格',False),68:('仓库取货口两边缺格允许表',True),71:('仓库取货口缺格选择编码',False),73:('仓库取货口强制邻格',False),78:('大制造单位双存货端口例外支撑',False),81:('大制造单位存货端口数',False),82:('双存货端口例外总数',True),85:('供电桩总数',True),88:('保留制造单位与协议核心总数上限',True),94:('保留制造单位得电覆盖',False),96:('保留制造单位重复供电计数',False),97:('重复供电与供电亏额总预算',True),103:('边段协议核心与供电桩计数',False),104:('边段供电亏额下界',False),105:('边段投影允许表',False),107:('边段实际缺口与投影下界',False),127:('面积缺口总账',True)}
RESIDUAL={31:('剩余3×3中心与已有结构互斥',False),33:('剩余3×3中心得电覆盖',False),36:('剩余格组与可用中心对应',False),37:('剩余格组与保留制造单位总数',True)}
MAP={'geometry.py':GEOMETRY,'solve_relaxation.py':RELAX,'flow_model.py':FLOW,'flow_model_global.py':GLOBAL,'cp72.py':CP72,'residual_model75.py':RESIDUAL}

def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def prep(model):
    p=OUT/'models'/model;z=np.load(p/'incidence.npz');off=z['offsets'];pins=z['pins'];src=z['source'];vs=json.loads((p/'variables.json').read_text());sources=json.loads((p/'constraint_sources.json').read_text());n=len(vs);m=len(off)-1
    labels=[];gm=[]
    for s in sources:
        label,g=MAP[Path(s['file']).name][s['line']];labels.append(label);gm.append(g)
        s.update(category=label,global_constraint=g)
    dump(p/'constraint_sources.json',sources)
    globalmask=np.array(gm,dtype=bool)[src];gids=np.flatnonzero(globalmask)
    rows=[]
    for i in gids:
        ids=pins[off[i]:off[i+1]];cs=collections.Counter(vs[v]['family'] for v in ids)
        xy=np.array([vs[v]['xy'] for v in ids if vs[v]['xy'] is not None])
        rows.append(dict(id=int(i),source=sources[src[i]],variables=len(ids),families=dict(cs),xy_bbox=[*xy.min(axis=0),*xy.max(axis=0)] if len(xy) else None,example_variables=[vs[v]['name'] for v in ids[:5]]))
    dump(p/'global_constraints.json',rows)
    A=csr_matrix((np.ones(len(pins),dtype=bool),pins,off),shape=(m,n))
    counts={}
    for mode in ('full','noglobal'):
        active=np.arange(m) if mode=='full' else np.flatnonzero(~globalmask)
        B=A[active];pairs=int(sum(int(x)*(int(x)-1)//2 for x in np.diff(B.indptr)))
        counts[mode]=dict(variables=n,constraints=len(active),pins=B.nnz,clique_pair_occurrences=pairs)
    for scope in ('whole','window'):
        if scope=='window':
            # Same 14x14 diagnostic window for the two flows and pure geometry.
            # Coordinate-free bookkeeping variables are retained.
            vids=np.array([v['id'] for v in vs if v['xy'] is None or (16<=v['xy'][0]<30 and 16<=v['xy'][1]<30)],dtype=np.int32)
            B=A[:,vids];rowids=np.flatnonzero(np.diff(B.indptr)>0);B=B[rowids]
        else:vids=np.arange(n,dtype=np.int32);B=A;rowids=np.arange(m,dtype=np.int32)
        dest=OUT/'raw'/f'{model}_{scope}';dest.mkdir(exist_ok=True)
        np.savez_compressed(dest/'input.npz',offsets=B.indptr,pins=B.indices,variable_ids=vids,constraint_ids=rowids,global_mask=globalmask[rowids],source=src[rowids])
        stats=dict(model=model,scope=scope,window=[16,16,30,30] if scope=='window' else None,variables=len(vids),constraints=len(rowids),pins=B.nnz,global_constraints=int(globalmask[rowids].sum()),original_variables=n,original_constraints=m,whole_graph_estimates=counts)
        dump(dest/'input.json',stats)
        print(json.dumps(stats),flush=True)
        if model=='residual75':break
    dump(p/'structure_summary.json',dict(global_constraints=len(gids),global_categories=dict(collections.Counter(x['source']['category'] for x in rows)),graph_estimates=counts))

if __name__=='__main__':
    for name in sys.argv[1:]:prep(name)
