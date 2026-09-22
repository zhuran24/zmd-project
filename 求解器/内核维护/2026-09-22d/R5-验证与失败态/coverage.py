#!/usr/bin/env python3
"""Describe the immutable reference trajectories compared by reference.rs."""
import collections,json
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
coverage={}
for name in ['混做粉碎机两下游','分流器三路轮询']:
    record=json.loads((ROOT/f'数据/样例/{name}-参考运行记录.json').read_text())
    ticks=record['trace']['ticks']; events=[e for t in ticks for e in t['events']]
    coverage[name]={'ticks':len(ticks),'times':[t['time']['value']['value'] for t in ticks],
        'tick_fields':list(ticks[0]),'operations':dict(collections.Counter(e['operation'] for e in events)),
        'outcomes':dict(collections.Counter(e['outcome'] for e in events)),
        'details':dict(collections.Counter(str(e.get('detail')) for e in events)),
        'non_judgment_events':[{'time':t['time'],'events':[e for e in t['events'] if not e['event'].startswith('J|')]} for t in ticks if any(not e['event'].startswith('J|') for e in t['events'])]}
(OUT/'reference-coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(coverage,ensure_ascii=False,indent=2))
