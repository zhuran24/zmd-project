import json,sys
from pathlib import Path
from pack_factory import C,BASE
p=Path(sys.argv[1]);d=json.loads(p.read_text());l=d['layout'];r=d['reserved_rectangle']
fixed=json.loads((BASE/'证据/loose-fixed.json').read_text())['layout'];fids={u['id'] for u in fixed['machines']}
nodes=l['machines']+l['warehouse_outlets']+[l['core']]+l['power_poles'];index={u['id']:i for i,u in enumerate(nodes)}
rows=[f'{len(nodes)} {len(C["feeds"])} {len(l["transport"])}']
for u in nodes:
 kind=0 if u.get('kind')=='小' else 1 if u.get('kind')=='中' else 2 if u.get('kind')=='大' else 4 if u['id']=='CORE' else 5 if u['id'].startswith('POWER') else 3
 mutable=int(kind<=2 and u['id'] not in fids)
 rows.append(f'{u["id"]} {kind} {mutable} {u["x0"]} {u["y0"]} {u.get("Din",u.get("Dout",0))}')
for f in C['feeds']:rows.append(f'{index[f["source"]]} {index[f["target"]]} {4 if f["item"] in ["源矿","蓝铁矿"] else 1}')
for t in l['transport']:rows.append(f'{t["x"]} {t["y"]} {t["in_side"]} {t["out_side"]}')
rows.append(f'{r["x0"]} {r["y0"]} {r["x1"]-r["x0"]+1} {r["y1"]-r["y0"]+1}')
(BASE/'证据/anneal-input.txt').write_text('\n'.join(rows)+'\n')

(BASE/'证据/anneal-base-layout.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
