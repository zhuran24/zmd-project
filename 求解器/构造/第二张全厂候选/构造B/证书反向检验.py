#!/usr/bin/env python3
"""核验证书检查器会拒绝断边、共用内部点及错误外点连接。

补充图论交叉检查：每份证书删去任意一条边后应当变成平面图。
这检验的是证书，不是合法布局或动态运行。
"""
import copy
import importlib.util
import json
from pathlib import Path

import networkx as nx

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('independent_static_check', BASE/'静态检查.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
d = checker.read(BASE/'S2接法.json')
cert = checker.read(BASE/'不可平面布线证书.json')
edges = {frozenset([f['source'],f['target']]) for f in d['feeds']}
boundary = {s['id'] for s in d['boundary_sources']}
results = []
for w in cert['witnesses']:
    intact = checker.verify_witness(w,edges,boundary)
    assert intact['status']=='PASS'
    used = {frozenset([a,b]) for p in w['paths'] for a,b in zip(p,p[1:])}
    real = [e for e in used if 'EXT' not in e]
    rejection = []
    for edge in sorted(real, key=lambda e:sorted(e)):
        modified = edges - {edge}
        outcome = checker.verify_witness(w,modified,boundary)
        rejection.append(outcome['status']=='FAIL')
    broken_paths = copy.deepcopy(w)
    broken_paths['paths'][-1] = broken_paths['paths'][-2]
    repeated_path_rejected = checker.verify_witness(broken_paths,edges,boundary)['status']=='FAIL'
    wrong_boundary = copy.deepcopy(w)
    wrong_boundary['paths'][0][1] = 'CORE'
    wrong_exterior_rejected = checker.verify_witness(wrong_boundary,edges,boundary)['status']=='FAIL'
    g = nx.Graph()
    g.add_edges_from(tuple(e) for e in used)
    deletions = []
    for a,b in list(g.edges()):
        reduced = g.copy()
        reduced.remove_edge(a,b)
        deletions.append(nx.check_planarity(reduced)[0])
    results.append(dict(id=w['id'],original_pass=True,real_edges_tested=len(real),
                        every_deleted_real_edge_rejected=all(rejection),
                        repeated_path_rejected=repeated_path_rejected,
                        interior_core_as_exterior_neighbor_rejected=wrong_exterior_rejected,
                        networkx_single_edge_deletions=len(deletions),
                        every_single_edge_deleted_graph_planar=all(deletions)))
success = all(r['every_deleted_real_edge_rejected'] and r['repeated_path_rejected']
              and r['interior_core_as_exterior_neighbor_rejected']
              and r['every_single_edge_deleted_graph_planar'] for r in results)
out = dict(all_pass=success,meaning='正证书有效；断边、重复路径、错误边界前件均被拒绝。',
           cases=results, independent_checker_sha256=checker.sha(BASE/'静态检查.py'),
           networkx_version=nx.__version__)
(BASE/'证书反向检验结果.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
raise SystemExit(0 if success else 1)
