from pathlib import Path
import hashlib,json
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[3];manifest=[]
for seat in ['A','B']:
 for name in ['catalog.py','geometry.py']:
  orig=ROOT/f'求解器/构造/第一张全厂候选/检查器{seat}/{name}'
  dst=BASE/f'旧检查器{seat}/{name}'
  dst.write_bytes(orig.read_bytes());manifest.append(dict(source=str(orig.relative_to(ROOT)),sha256=hashlib.sha256(orig.read_bytes()).hexdigest(),copy=str(dst.relative_to(BASE))))
 p=BASE/f'旧检查器{seat}/catalog.py';p.write_text(p.read_text().replace('parents[4]','parents[5]'))
p=BASE/'旧检查器A/geometry.py';s=p.read_text();a=s.index('  # All facing ports queried');b=s.index('  for p,(pt,c)in sorted',a)
s=s[:a]+'''  # S2B adaptation: inspect the two ends of each straight bridge run.
  for uid in bridges:
   u=self.units[uid];c=(u['x'],u['y'])
   for axis,ends,key in [('H',(0,2),'H_in'),('V',(1,3),'V_in')]:
    f={}
    for direction in ends:
     here=nb(c,direction);steps=0
     while self.occ.get(here) in bridges:
      here=nb(here,direction);steps+=1
      if steps>70:raise ValueError('nonfinite straight bridge run')
     endpoint=self.at.get((here,opp(direction)))
     if endpoint:f[direction]=endpoint[0]
    valid=not f or len(f)==2 and set(f.values())=={'in','out'}
    ins=next((d for d in ends if f.get(d)=='out'),None)
    self.axis[(uid,axis)]=ins
    self.check('N4a',valid and u[key]==ins,'临时规则按轴；S2B直桥串端点；保留逆向通道',{'bridge':uid,'axis':axis,'endpoints':f,'derived':ins,'declared':u[key]})
   for direction in range(4):self.port(u,direction,0,'both')
''' +s[b:]
s=s.replace("if pt!='out':continue","if pt not in ['out','both']:continue").replace("if v and v[0]=='in' and", "if v and v[0] in ['in','both'] and")
p.write_text(s)
p=BASE/'旧检查器B/geometry.py';s=p.read_text();a=s.index('  # Simultaneous derivation');b=s.index('  for p,(xy,io) in self.ports.items():',a)
s=s[:a]+'''  # S2B adaptation, independently encoded by scanning maximal row/column runs.
  bridge_at={(v['x'],v['y']):v for v in layout['transport'] if v['type']=='bridge'}
  for xy,u in bridge_at.items():
   uid=u['id']
   for ax,dirs,key in [(0,(2,0),'H_in'),(1,(3,1),'V_in')]:
    endpoints=[]
    for direction in dirs:
     px,py=xy;dx,dy=DX[direction]
     for step in range(71):
      px+=dx;py+=dy
      if (px,py) not in bridge_at:break
     ref_at_end=self.spatial.get(((px,py),opp(direction)))
     endpoints.append(None if ref_at_end is None else self.ports[ref_at_end][1])
    expected=dirs[endpoints.index('out')] if 'out' in endpoints else None
    valid=endpoints==[None,None] or sorted(x for x in endpoints if x is not None)==['in','out']
    checks.add('N4a',valid and u[key]==expected,'S2B同轴桥串两端检查；反向通道显式保留',{'unit':uid,'axis':ax,'endpoints':endpoints,'declared':u[key],'derived':expected})
    if expected is not None:self.axes[(uid,ax)]=expected
  for xy,u in bridge_at.items():
   for direction in range(4):self.port(u['id'],direction,0,xy,'both')
''' +s[b:]
s=s.replace("if io!='out': continue","if io not in ['out','both']: continue").replace("self.ports[q][1]=='in'", "self.ports[q][1] in ['in','both']")
p.write_text(s)
for row in manifest:row['adapted_sha256']=hashlib.sha256((BASE/row['copy']).read_bytes()).hexdigest()
(BASE/'证据/旧几何适配清单.json').write_text(json.dumps(dict(files=manifest,scope='只适配几何重建：A逐桥沿方向找端点，B沿行列扫描桥串；四个物理端口都保留，桥间双向通道均生成。未升级原CLI、77条约束台账或动态证明。'),ensure_ascii=False,indent=2))
