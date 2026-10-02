#!/usr/bin/env python3
"""将搜索坐标与实际已布路径写成可核查的实体布局；不宣告通过。"""
import sys,json,hashlib,copy
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[3]
D=((1,0),(0,1),(-1,0),(0,-1))
def occu(u):
 if 'x' in u:return [(u['x'],u['y'])]
 return [(x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)]
def rectangle(used):
 h=[0]*70;best=(0,0);r=None
 for y in range(70):
  for x in range(70):h[x]=0 if (x,y) in used else h[x]+1
  stack=[]
  for x in range(71):
   z=h[x] if x<70 else 0;start=x
   while stack and stack[-1][1]>z:
    a,v=stack.pop();start=a;w=x-a
    if min(w,v)>=6 and (w*v,min(w,v))>best:best=(w*v,min(w,v));r=dict(x0=a,y0=y-v+1,x1=x-1,y1=y)
   if not stack or stack[-1][1]<z:stack.append((start,z))
 return r

def export(raw):
 c=json.loads((BASE/'逻辑接法.json').read_text());machines={m['id']:m for m in c['machines']}
 l={k:[] for k in ['machines','warehouse_outlets','power_poles','storage_boxes','transport','vin','vout']};l.update(W=70,H=70)
 for u in raw['units']:
  n=u['id'];v=dict(id=n,x0=u['x'],y0=u['y'],x1=u['x']+u['w']-1,y1=u['y']+u['h']-1)
  if n in machines:
   m=machines[n];v.update(model=m['model'],kind=m['kind'],Din=u['d'],recipe_ids=[m['recipe_id']],settings={'manufacture_on':True});l['machines'].append(v)
  elif n=='CORE':v.update(Din=u['d'],output_items=[dict(side=s,offset=o,item='源矿') for s in [(u['d']+1)%4,(u['d']+3)%4] for o in [1,4,7]]);l['core']=v
  elif u['type']==4:v.update(Dout=u['d'],item='蓝铁矿' if n.startswith('OB') else '源矿');l['warehouse_outlets'].append(v)
  else:v.update(orientation=0);l['power_poles'].append(v)
 usage={}
 for p in raw['paths']:
  for x,y,ins,outs in p['cells']:usage.setdefault((x,y),[]).append((p['r'],ins,outs))
 for (x,y),a in sorted(usage.items()):
  t=dict(id=f'X{x}_{y}',x=x,y=y)
  if len(a)==1:t.update(type='belt',in_side=a[0][1],out_side=a[0][2])
  else:
   assert len(a)==2 and all(o==(i+2)%4 for _,i,o in a) and a[0][1]%2!=a[1][1]%2,('conflicting routing is not exportable',x,y,a)
   by={i%2:i for _,i,o in a};t.update(type='bridge',H_in=by[0],V_in=by[1])
  l['transport'].append(t)
 channels=[];feeds=[]
 def channel(a,b,item):
  n=f'PC{len(channels):05d}';channels.append(dict(id=n,**{'from':a,'to':b},allowed_items=[item]));return n
 for p in raw['paths']:
  if not p['cells']:continue
  f=c['feeds'][p['r']];a=dict(unit=f['source'],side=p['source'][2],offset=p['source'][3]);b=dict(unit=f['target'],side=p['target'][2],offset=p['target'][3]);last=a;path=[]
  for x,y,ins,outs in p['cells']:
   path.append(channel(last,dict(unit=f'X{x}_{y}',side=ins,offset=0),f['item']));last=dict(unit=f'X{x}_{y}',side=outs,offset=0)
  path.append(channel(last,b,f['item']));feeds.append(dict(id=f['id'],**{'from':a,'to':b},item=f['item'],rate=f['rate'],path=path))
 bridges={u['id'] for u in l['transport'] if u['type']=='bridge'};reverse=[]
 for z in list(channels):
  if z['from']['unit'] in bridges and z['to']['unit'] in bridges:reverse.append(channel(z['to'],z['from'],z['allowed_items'][0]))
 # Cover remaining machines with free 2x2 footprints. This is recorded geometry, not a virtual power flag.
 used={c for group in ['machines','warehouse_outlets','power_poles','transport'] for u in l[group] for c in occu(u)}|set(occu(l['core']))|{(x,y) for x in range(64,70) for y in range(64,70)}
 def covers(u,p):return u['x0']<=p['x0']+6 and u['x1']>=p['x0']-5 and u['y0']<=p['y0']+6 and u['y1']>=p['y0']-5
 missing={u['id']:u for u in l['machines'] if not any(covers(u,p) for p in l['power_poles'])}
 while missing:
  best=None
  for x in range(1,69):
   for y in range(1,69):
    pp={(x,y),(x+1,y),(x,y+1),(x+1,y+1)}
    if used&pp:continue
    p=dict(id=f'POWERextra{len(l["power_poles"])}',x0=x,y0=y,x1=x+1,y1=y+1,orientation=0)
    cv=[n for n,u in missing.items() if covers(u,p)]
    if cv and (best is None or len(cv)>len(best[1])):best=p,cv,pp
  if best is None:break
  p,cv,pp=best;l['power_poles'].append(p);used|=pp
  for n in cv:missing.pop(n)
 used={c for group in ['machines','warehouse_outlets','power_poles','transport'] for u in l[group] for c in occu(u)}|set(occu(l['core']))
 fps={k:hashlib.sha256((BASE/'依据'/name).read_bytes()).hexdigest() for k,name in [('rules','《明日方舟：终末地》游戏规则.txt'),('task','求解任务.txt'),('constraints','求解约束.txt')]}
 restriction=dict(id='S2B-fixed',source=['dynamic','shape'],statement='实现第107轮第2节的固定230台及325路；桥接器允许相邻。',coverage_loss='只覆盖该接法。',release_obligations='改变接法后重新证明达标条件。',failure_scope='仅拒绝本候选；搜索失败不证明全类无解。')
 d=dict(schema='full-factory-static-s2b-v1' if reverse else 'full-factory-static-v1',candidate_id='fourth-independent',source_fingerprints=fps,provenance=[dict(path='求解器/候选约束轮次/第107-109轮/临时规则.md',sha256=hashlib.sha256((BASE/'依据/临时规则.md').read_bytes()).hexdigest()),dict(path='求解器/候选约束轮次/第107-109轮/推导107S2B.md',sha256=hashlib.sha256((BASE/'依据/推导107S2B.md').read_bytes()).hexdigest())],targets={'高容谷地电池':'3/5','精选荞愈胶囊':'11/20'},layout=l,empty_rectangle=rectangle(used),design={'class':'s2b_p2p' if reverse else 'p2p','restrictions':[restriction],'physical_channels':channels,'logical_feeds':feeds},flow_witness=None)
 if reverse:d['design']['bridge_reverse_channels']=reverse
 else:
  statements={'N1':'不使用汇流器。','N2':'不使用分流器。','N3a':'不使用物品准入口。','N3b':'不使用物品准入口。','N4a':'桥接器按轴使用，未用轴无通道。','N4b':'桥接器不相邻。','N5a':'列出全部自动通道。','N5b':'正向进路的设计流量为正；整厂是否满足流量条件另行核验。','P1':'不使用协议储存箱。','P2':'每路为单物品独立进路。','P3':'正流量条件由静态程序核验，声明不等于通过。','P4':'桥接器同轴不分叉。','P5':'桥接器不相邻。','P6':'粉碎机、采种机均按指定单配方接法。'}
  d['design']['restrictions'] += [dict(id=k,source=['dynamic','shape'],statement=v,coverage_loss='限定于所列点对点接法。',release_obligations='解除后重新核查几何和运行条件。',failure_scope='仅本候选。') for k,v in statements.items()]
 return d
if __name__=='__main__':
 p=Path(sys.argv[1]);raw=json.loads(p.read_text());d=export(raw);Path(sys.argv[2]).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print({'routes':len(d['design']['logical_feeds']),'transport':len(d['layout']['transport'])})
