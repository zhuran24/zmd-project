#!/usr/bin/env python3
"""独立复算原始匿名矿口流图的件数；结果只说明图结构。"""
import csv
import json
from collections import defaultdict
from pathlib import Path

OUT=Path(__file__).resolve().parent
RAW=Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4/channels.csv')
with RAW.open(encoding='utf-8',newline='') as stream:
    edges=list(csv.DictReader(stream))
graph=defaultdict(set)
reverse=defaultdict(set)
nodes=set()
parallel=defaultdict(list)
for row in edges:
    source,target=row['源机器id'],row['目标机器id']
    graph[source].add(target)
    reverse[target].add(source)
    nodes.update([source,target])
    parallel[(source,target)].append(row['通道id'])
visited=set()
order=[]
def visit(node):
    if node in visited:
        return
    visited.add(node)
    for target in sorted(graph[node]):
        visit(target)
    order.append(node)
for node in sorted(nodes):
    visit(node)
visited.clear()
components=[]
for node in reversed(order):
    if node in visited:
        continue
    stack=[node]
    component=[]
    while stack:
        current=stack.pop()
        if current in visited:
            continue
        visited.add(current)
        component.append(current)
        stack.extend(reverse[current]-visited)
    components.append(sorted(component))
result=dict(raw_nodes=len(nodes),logical_records=len(edges),simple_edges=sum(map(len,graph.values())),
    strongly_connected_components=len(components),nontrivial_components=sorted(part for part in components if len(part)>1),
    parallel_pairs=[dict(source=source,target=target,records=records) for (source,target),records in parallel.items() if len(records)>1],
    scope='矿石来源沿用原始CSV的单一匿名节点；有向环不构成运行活性检查范围。')
(OUT/'原始流图计数.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
