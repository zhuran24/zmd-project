"""Exact network witness for independent subset-layer relaxation.
This is an abstract network, not a factory layout or performance experiment.
"""
from pathlib import Path
import json

nodes=['sA','sB','p','q','tA','tB']
edges=[('sA','p'),('sB','p'),('p','q'),('q','tA'),('q','tB'),('sA','tB'),('sB','tA')]
capacity={e:1 for e in edges}

def check(flow,demand):
    balance={v:0 for v in nodes}
    for e,c in capacity.items():
        f=flow.get(e,0)
        assert isinstance(f,int) and 0<=f<=c
        balance[e[0]]-=f
        balance[e[1]]+=f
    assert all(balance[v]==demand.get(v,0) for v in nodes)

layers={
    'all':({('sA','tB'):1,('sB','tA'):1},{'sA':-1,'sB':-1,'tA':1,'tB':1}),
    'A':({('sA','p'):1,('p','q'):1,('q','tA'):1},{'sA':-1,'tA':1}),
    'B':({('sB','p'):1,('p','q'):1,('q','tB'):1},{'sB':-1,'tB':1}),
}
for flow,demand in layers.values():
    check(flow,demand)

def paths(start,end,path=()):
    if start==end:
        return [path]
    found=[]
    visited={e[0] for e in path}
    for edge in edges:
        if edge[0]==start and edge[1] not in visited:
            found+=paths(edge[1],end,path+(edge,))
    return found
pa,pb=paths('sA','tA'),paths('sB','tB')
assert len(pa)==len(pb)==1
assert ('p','q') in pa[0] and ('p','q') in pb[0]
assert layers['A'][0][('p','q')]+layers['B'][0][('p','q')]>capacity[('p','q')]
assert layers['all'][0].get(('p','q'),0)==0
# Shared capacity alone does not force a non-integral feasible polytope:
# x>=0,y>=0,x+y<=1 is the integral simplex with these three vertices.
shared_simplex_vertices=[(0,0),(1,0),(0,1)]
assert all(x>=0 and y>=0 and x+y<=1 for x,y in shared_simplex_vertices)
result={
    'scope':'abstract network counterexample to sufficiency; not a factory or performance claim',
    'independent_integer_layers_verified':list(layers),
    'A_paths':[list(p) for p in pa],
    'B_paths':[list(p) for p in pb],
    'joint_shared_capacity_feasible':False,
    'reason':'both unit demands have unique paths through p->q, whose capacity is 1',
    'all_layer_bottleneck_flow':0,
    'A_layer_bottleneck_flow':1,
    'B_layer_bottleneck_flow':1,
    'shared_capacity_integral_example_vertices':shared_simplex_vertices,
}
Path(__file__).with_name('subset-product-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
