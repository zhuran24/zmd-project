#!/usr/bin/env python3
"""独立从98S2既有图提取并复核K3,3细分；不导入本席接法生成器。"""
import hashlib
import itertools
import json
import os
from collections import Counter
from pathlib import Path

os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
BASE=Path(__file__).resolve().parents[1]


def save(name,obj):
    p=BASE/name
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')


def witness_paths(which):
    """原程序零基名字；S3/E2或S5/E3，仅三条矿路各取一支即可。"""
    if which==2: a,b,o,s,p=2,3,3,2,1
    elif which==3: a,b,o,s,p=4,5,6,4,2
    else: raise ValueError(which)
    left=['基地外部',f'砂叶粉碎{s}',f'封装{p}']
    right=[f'铁研磨{a}',f'铁研磨{b}',f'源研磨{o}']
    paths=[
        ['基地外部',f'仓库取货口{2*a}',f'矿精炼{2*a}',f'铁粉碎{2*a}',right[0]],
        ['基地外部',f'仓库取货口{2*b}',f'矿精炼{2*b}',f'铁粉碎{2*b}',right[1]],
        ['基地外部',f'仓库取货口{34+2*o}',f'源粉碎{2*o}',right[2]],
        [left[1],right[0]],[left[1],right[1]],[left[1],right[2]],
        [left[2],f'配件{a}',f'钢精炼{a}',right[0]],
        [left[2],f'配件{b}',f'钢精炼{b}',right[1]],
        [left[2],right[2]],
    ]
    return left,right,paths


def verify_paths(graph,left,right,paths):
    """纯Python逐边核：方向可忽略，但不能捏造原图进路或内部共用点。"""
    original={}
    for e in graph['routes']:
        original.setdefault(frozenset([e['from'],e['to']]),[]).append(e)
    terminals=set(left+right)
    source_names={r['from'] for r in graph['routes'] if r['from'].startswith('仓库取货口')}
    assert len(terminals)==6 and not set(left)&set(right)
    assert len(paths)==9
    pairs=set()
    interiors=set()
    actual_edges=[]
    virtual_edges=[]
    for p in paths:
        assert len(set(p))==len(p), ('单路径重复顶点',p)
        assert p[0] in left and p[-1] in right, ('错误分组',p)
        assert (p[0],p[-1]) not in pairs
        pairs.add((p[0],p[-1]))
        assert not (set(p[1:-1])&terminals), ('内部使用分支点',p)
        assert not (set(p[1:-1])&interiors), ('两条路径内部共用点',p)
        interiors.update(p[1:-1])
        for a,b in zip(p,p[1:]):
            if a=='基地外部':
                assert b in source_names, ('外部辅助边必须止于边界取货口',b)
                virtual_edges.append([a,b])
            else:
                assert frozenset([a,b]) in original, ('不存在的逻辑进路',a,b)
                choices=original[frozenset([a,b])]
                assert len(choices)==1, ('证书取边须有唯一原图记录',a,b)
                e=choices[0]
                actual_edges.append({k:e[k] for k in ['id','from','to','item']})
    assert pairs==set(itertools.product(left,right))
    assert len({e['id'] for e in actual_edges})==len(actual_edges)==18
    all_vertices=set().union(*(set(p) for p in paths))
    degree=Counter()
    for p in paths:
        for a,b in zip(p,p[1:]): degree[a]+=1;degree[b]+=1
    assert {n for n,d in degree.items() if d==3}==terminals
    assert all(degree[n]==2 for n in interiors)
    assert len(all_vertices)==18 and sum(degree.values())//2==21
    return dict(pass_certificate=True,branch_sets=[left,right],paths=paths,
                actual_routes=actual_edges,auxiliary_edges=virtual_edges,
                distinct_boundary_outlets=[p[1] for p in paths[:3]],
                subdivision_vertices=18,subdivision_edges=21,internal_vertices=sorted(interiors),
                reduced_vertices=6,reduced_edges=9,bipartite_planar_edge_upper_bound=8,
                contradiction='9 > 2×6−4 = 8',
                note='基地外部是平面性证明的辅助顶点，不是游戏单位、通道或仓库捷径。')


def rotations(left,right,omit=None):
    """枚举循环次序并由有向边置换数面；不用NetworkX或求解器。"""
    nodes=left+right
    neighbors={v:[] for v in nodes}
    for a,b in itertools.product(left,right):
        if omit is not None and {a,b}==set(omit): continue
        neighbors[a].append(b); neighbors[b].append(a)
    orders=[]
    for v in nodes:
        ns=neighbors[v]
        # 固定一个邻居作为循环起点，不去掉反射：所有有向平面嵌入都包含。
        orders.append([(ns[0],)+p for p in itertools.permutations(ns[1:])])
    entries=[]
    for choices in itertools.product(*(range(len(q)) for q in orders)):
        sigma={}
        for v,k,opts in zip(nodes,choices,orders):
            row=opts[k]
            for a,b in zip(row,row[1:]+row[:1]):sigma[(v,a)]=b
        darts={(a,b) for a in nodes for b in neighbors[a]}
        successor={(a,b):(b,sigma[b,a]) for a,b in darts}
        unseen=set(darts); faces=[]
        while unseen:
            first=min(unseen);walk=[];d=first
            while d in unseen:
                unseen.remove(d);walk.append(list(d));d=successor[d]
            assert d==first
            faces.append(walk)
        entries.append(dict(rotations=list(choices),face_count=len(faces),faces=faces))
    return entries


def main():
    path=BASE/'依据快照/既有逻辑图.json'
    graph=json.loads(path.read_text())
    certificates=[]
    for which in [2,3]:
        left,right,paths=witness_paths(which)
        cert=verify_paths(graph,left,right,paths)
        cert['id']=f'S{2*which-1}-E{which}'
        cert['source_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        save(f'证据/不可平面证书-{cert["id"]}.json',cert)
        certificates.append(cert)
    left,right,paths=witness_paths(2)
    table=rotations(left,right)
    assert len(table)==64
    histogram=dict(Counter(r['face_count'] for r in table))
    assert histogram=={3:40,1:24}
    save('证据/全部64种旋转系统.json',dict(vertices=left+right,edges=list(itertools.product(left,right)),
                                      planar_required_faces=5,face_histogram=histogram,rows=table))
    # 局部证书的反例检测：删一条关系后应恢复平面；删边不能仍被误报为此K3,3证书。
    controls=[]
    for e in itertools.product(left,right):
        rs=rotations(left,right,omit=e)
        euler_faces=2-6+8
        controls.append(dict(omitted_edge=e,rotation_count=len(rs),
                             has_planar_rotation=any(r['face_count']==euler_faces for r in rs)))
    assert all(c['has_planar_rotation'] for c in controls)
    tamper=[]
    for mode in ['删除一条真实进路','伪造内部共用点','把外部接到内陆机器']:
        gd=json.loads(json.dumps(graph));ps=json.loads(json.dumps(paths))
        if mode=='删除一条真实进路':
            gd['routes']=[r for r in gd['routes'] if not (r['from']=='砂叶粉碎2' and r['to']=='铁研磨2')]
        elif mode=='伪造内部共用点':ps[1][2]=ps[0][2]
        else:ps[0][1]='矿精炼4'
        caught=False
        try:verify_paths(gd,left,right,ps)
        except AssertionError:caught=True
        tamper.append(dict(case=mode,rejected=caught))
    assert all(t['rejected'] for t in tamper)

    import networkx as nx
    original=nx.Graph()
    def core(n):return '协议核心' if n.startswith('协议核心') else n
    for r in graph['routes']:original.add_edge(core(r['from']),core(r['to']))
    bare=nx.check_planarity(original)[0]
    augmented=original.copy()
    for n in list(original):
        if n.startswith('仓库取货口'):augmented.add_edge('基地外部',n)
    boundary=nx.check_planarity(augmented)[0]
    sub=nx.Graph()
    for p in paths:nx.add_path(sub,p)
    independent=dict(library='networkx',version=nx.__version__,
                     full_graph_without_boundary_apex_planar=bare,
                     full_graph_with_boundary_apex_planar=boundary,
                     selected_subdivision_planar=nx.check_planarity(sub)[0])
    assert bare is True and boundary is False and independent['selected_subdivision_planar'] is False
    # 方格图加外部点的有限模板：任何合法布局的选定实体/进路都给出其子图的收缩。
    grid=nx.grid_2d_graph(70,70)
    for x in range(70):
        grid.add_edge('基地外部',(x,0));grid.add_edge('基地外部',(x,69))
    for y in range(1,69):
        grid.add_edge('基地外部',(0,y));grid.add_edge('基地外部',(69,y))
    independent['grid_with_boundary_apex']=dict(vertices=len(grid),edges=grid.number_of_edges(),planar=nx.check_planarity(grid)[0])
    assert independent['grid_with_boundary_apex']['planar']
    result=dict(status='PROVED_INFEASIBLE_FOR_FIXED_S2',static_pass=False,
                certificates=[c['id'] for c in certificates],certificate_pass=True,
                exact_rotation_histogram=histogram,planar_required_faces=5,
                networkx=independent,edge_deletion_controls=controls,tamper_controls=tamper,
                scope='第98轮S2完整接法 + 所有仓库取货口在基地边界 + 纯带进路互不共格',
                not_claimed=['任意接法不可行','动态充分条件的蕴含为假','全局最优值','已实现空矩形'],
                layout_exists=False)
    save('证据/拓扑复核结果.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['edge_deletion_controls','tamper_controls']},ensure_ascii=False))


if __name__=='__main__':main()
