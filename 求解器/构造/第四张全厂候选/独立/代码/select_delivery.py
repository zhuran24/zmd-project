#!/usr/bin/env python3
import json,hashlib,sys
from pathlib import Path
from export_layout import export
from check_static import run
BASE=Path(__file__).resolve().parents[1];allowed={'325条指定进路齐全','H6和Q6到F4等长','精确平均物料守恒','两种成品设计交付率','固定机位的运输格数必要条件','端口邻格数量必要条件'}
rows=[]
for p in (BASE/'迭代').rglob('*.json'):
 if not any(z in p.name for z in ['legal-','maxroutes','-best','current','final','接受','起点','snapshot']):continue
 try:
  d=json.loads(p.read_text())
  if 'units' not in d or 'paths' not in d or d.get('overlap',1)!=0:continue
  n=sum(bool(x['cells']) for x in d['paths']);rows.append((n,p))
 except (json.JSONDecodeError,KeyError,TypeError):continue
rows.sort(key=lambda a:(-a[0],str(a[1])));best=None;records=[]
for n,p in rows:
 if best and n<best[0][1]:break
 try:
  raw=json.loads(p.read_text());d=export(raw);r=run(d);bad=[c['name'] for c in r['checks'] if not c['pass'] and c['name'] not in allowed]
  record={'path':str(p),'routes':r['stats']['completed_routes'],'static_pass':r['static_pass'],'structural_errors':bad,'stats':r['stats']};records.append(record)
  if bad:continue
  st=r['stats'];equal=next(c['pass'] for c in r['checks'] if c['name']=='H6和Q6到F4等长')
  score=(r['static_pass'],st['completed_routes'],-st['fixed_geometry_obstructed'],equal,st['product_routes'],st['ore_routes'],-st['transport_length_lower_bound'],-st['occupied'])
  if best is None or score>best[0]:best=(score,p,d,r)
 except Exception as e:records.append({'path':str(p),'error':repr(e)})
assert best,'No structurally valid partial layout found'
score,p,d,r=best
(BASE/'布局.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');r['layout_sha256']=hashlib.sha256((BASE/'布局.json').read_bytes()).hexdigest();r['checker_sha256']=hashlib.sha256((BASE/'代码/check_static.py').read_bytes()).hexdigest()
(BASE/'静态检查结果.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');sel={'raw_source':str(p),'raw_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'layout_sha256':r['layout_sha256'],'score':score,'raw_candidates':len(rows),'checked_finalists':records}
(BASE/'结果/交付候选选择.json').write_text(json.dumps(sel,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'source':str(p),'stats':r['stats'],'static_pass':r['static_pass']},ensure_ascii=False))
