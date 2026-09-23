import json,sys
from pathlib import Path
v=Path(__file__).resolve().parent;s=v.parents[2]
doc=json.loads((s/'crates/kernel/tests/fixtures/bridge.json').read_text())
print('FIXTURE KEYS',list(doc))
for k in ['layout','construction','timeline','settings']:
    print(k,json.dumps(doc[k],ensure_ascii=False,indent=2))
print('STATE',json.dumps({k:z for k,z in doc['initial_state']['nonwarehouse']['value'].items() if k!='semantic_context'},ensure_ascii=False,indent=2))
refs=json.loads((v/'bad-active-catalog-references.json').read_text())
counts={}
for r in refs: counts[r['path']]=counts.get(r['path'],0)+1
print('BAD-REF FILES',json.dumps(counts,ensure_ascii=False,indent=2))
print('STATUS OUTSIDE',json.dumps([r for r in json.loads((v/'before.json').read_text())['status'] if not r[3:].startswith('求解器/内核维护/2026-09-22h/')],ensure_ascii=False,indent=2))
