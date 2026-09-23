"""异源核查：不导入A/B或会议代码，按正式规则原文从零重建占格、端口、桥、通道、供电与最大空矩形。
只读候选，输出JSON到本目录。"""
import json,sys,hashlib
from collections import defaultdict,Counter
P='/home/zhuran24/zmd-research-fresh/求解器/构造/第一张全厂候选/生成/候选.json'
raw=open(P,'rb').read();D=json.loads(raw);L=D['layout']
V={0:(1,0),1:(0,1),2:(-1,0),3:(0,-1)}
err=[];occ={};units={};kind={}
def put(uid,k,cells):
  units[uid]=cells;kind[uid]=k
  for c in cells:
    if not(0<=c[0]<70 and 0<=c[1]<70):err.append(('bounds',uid,c))
    if c in occ:err.append(('overlap',uid,occ[c],c))
    occ[c]=uid
def box(u):return [(x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)]
SIZE={'粉碎机':3,'精炼炉':3,'配件机':3,'塑形机':3,'种植机':5,'采种机':5}
BIG={'研磨机','封装机','灌装机'}
# 端口表：(cell,side)->(uid,'in'/'out')  side=端口朝外方向
port={}
def edgecells(u,s):
  x0,y0,x1,y1=u['x0'],u['y0'],u['x1'],u['y1']
  if s==0:return [(x1,y) for y in range(y0,y1+1)]
  if s==2:return [(x0,y) for y in range(y0,y1+1)]
  if s==1:return [(x,y1) for x in range(x0,x1+1)]
  return [(x,y0) for x in range(x0,x1+1)]
def addp(uid,c,s,t,off):
  if (c,s) in port:err.append(('dupport',uid,c,s))
  port[(c,s)]=(uid,t,off)
for m in L['machines']:
  w=m['x1']-m['x0']+1;h=m['y1']-m['y0']+1
  if m['model'] in SIZE:
    if (w,h)!=(SIZE[m['model']],)*2:err.append(('shape',m['id'],w,h))
  else:
    # 长边为存货边：Din为E/W(0/2)时存货边竖直，长边须竖直 -> h=6,w=4
    exp=(4,6) if m['Din'] in (0,2) else (6,4)
    if (w,h)!=exp:err.append(('shape',m['id'],w,h,m['Din']))
  put(m['id'],'machine',box(m))
  for s,t in ((m['Din'],'in'),((m['Din']+2)%4,'out')):
    for i,c in enumerate(edgecells(m,s)):addp(m['id'],c,s,t,i)
outl=Counter()
for o in L['warehouse_outlets']:
  w=o['x1']-o['x0']+1;h=o['y1']-o['y0']+1
  if o['Dout']==0:
    ok=(w,h)==(1,3) and o['x0']==0;outl['left']+=1
  elif o['Dout']==1:
    ok=(w,h)==(3,1) and o['y0']==0;outl['bottom']+=1
  else: ok=False
  if not ok:err.append(('outlet',o['id']))
  put(o['id'],'outlet',box(o))
  ec=edgecells(o,o['Dout']);addp(o['id'],ec[1],o['Dout'],'out',1)
c=L['core'];put('CORE','core',box(c))
if (c['x1']-c['x0'],c['y1']-c['y0'])!=(8,8):err.append(('coreshape',))
for s in (c['Din'],(c['Din']+2)%4):
  for i,cc in enumerate(edgecells(c,s)):
    if 1<=i<=7:addp('CORE',cc,s,'in',i)
cop=set()
for q in c['output_items']:
  cop.add((q['side'],q['offset']))
  addp('CORE',edgecells(c,q['side'])[q['offset']],q['side'],'out',q['offset'])
if cop!={(s,o) for s in ((c['Din']+1)%4,(c['Din']+3)%4) for o in (1,4,7)}:err.append(('coreports',sorted(cop)))
for p in L['power_poles']:
  if (p['x1']-p['x0'],p['y1']-p['y0'])!=(1,1):err.append(('poleshape',p['id']))
  put(p['id'],'pole',box(p))
assert not L['storage_boxes']
bridges=[]
for t in L['transport']:
  put(t['id'],t['type'],[(t['x'],t['y'])])
  cc=(t['x'],t['y'])
  if t['type']=='belt':
    addp(t['id'],cc,t['in_side'],'in',0);addp(t['id'],cc,t['out_side'],'out',0)
  elif t['type']=='bridge':bridges.append(t)
  else:err.append(('unexpected_transport',t['id'],t['type']))
TR={'belt','bridge','splitter','merger','gate'}
# 桥：每轴两端看邻格朝向它的端口
bridgeinfo=[]
for t in bridges:
  cc=(t['x'],t['y'])
  for s in range(4):
    n=(cc[0]+V[s][0],cc[1]+V[s][1])
    if n in occ and kind[occ[n]]=='bridge':err.append(('adjbridge',t['id']))
  for ax,ends,key in (('H',(0,2),'H_in'),('V',(1,3),'V_in')):
    f={}
    for s in ends:
      n=(cc[0]+V[s][0],cc[1]+V[s][1]);q=port.get((n,(s+2)%4))
      if q:f[s]=q[1]
    der=None
    if len(f)==2:
      if set(f.values())=={'in','out'}:der=[s for s in ends if f[s]=='out'][0]
      else:err.append(('bridge_conflict',t['id'],ax,f))
    elif len(f)==1:
      s,ty=next(iter(f.items()));der=s if ty=='out' else (s+2)%4
      err.append(('bridge_single_end',t['id'],ax,f))
    if der!=t[key]:err.append(('bridge_decl',t['id'],ax,der,t[key]))
    bridgeinfo.append((t['id'],ax,f,der))
    if der is not None:
      addp(t['id'],cc,der,'in',0);addp(t['id'],cc,(der+2)%4,'out',0)
# 通道：一个out端口与朝向它的in端口相遇，且至少一端运输单位
ch=set()
for (cc,s),(uid,ty,off) in port.items():
  if ty!='out':continue
  n=(cc[0]+V[s][0],cc[1]+V[s][1]);q=port.get((n,(s+2)%4))
  if q and q[1]=='in' and (kind[uid] in TR or kind[q[0]] in TR):
    ch.add(((uid,s,off),(q[0],(s+2)%4,q[2])))
# 另查：同类端口相对（in对in、out对out）——不成通道，记录供参考
same=[]
for (cc,s),(uid,ty,off) in port.items():
  n=(cc[0]+V[s][0],cc[1]+V[s][1]);q=port.get((n,(s+2)%4))
  if q and q[1]==ty and uid<q[0]:same.append((uid,q[0],ty))
decl={((e['from']['unit'],e['from']['side'],e['from']['offset']),(e['to']['unit'],e['to']['side'],e['to']['offset'])) for e in D['design']['physical_channels']}
# 供电：桩中心为格点(x0+1,y0+1)，12x12范围为格 x0-5..x0+6
def cov(p,u):
  return any(p['x0']-5<=x<=p['x0']+6 and p['y0']-5<=y<=p['y0']+6 for (x,y) in units[u['id']])
unpow=[m['id'] for m in L['machines'] if not any(cov(p,m) for p in L['power_poles'])]
off=[m['id'] for m in L['machines'] if not m['settings']['manufacture_on']]
percov={p['id']:sum(cov(p,m) for m in L['machines']) for p in L['power_poles']}
# 最大空矩形：直方图+单调栈，列出全部最优
best=(0,0);opt=[]
hgt=[0]*70
for y in range(70):
  for x in range(70):hgt[x]=hgt[x]+1 if (x,y) not in occ else 0
  # 枚举所有(左,右)区间的最小高度 -> O(W^2)每行，简单可靠
  for a in range(70):
    mh=10**9
    for b in range(a,70):
      mh=min(mh,hgt[b])
      if mh==0:break
      w=b-a+1
      # 对该宽度，所有高度h<=mh都可；最优取h=mh，但短边约束需h>=6,w>=6
      if w>=6 and mh>=6:
        sc=(w*mh,min(w,mh))
        r=(a,y-mh+1,b,y)
        if sc>best:best=sc;opt=[r]
        elif sc==best:opt.append(r)
# 核心/取货口附近
out=dict(sha=hashlib.sha256(raw).hexdigest(),errors=[list(map(str,e)) for e in err],
 counts=dict(units=len(units),occupied=len(occ),channels=len(ch),declared=len(decl),missing=len(ch-decl),extra=len(decl-ch),
   outlets=dict(outl),bridges=len(bridges),machines=len(L['machines']),poles=len(L['power_poles'])),
 missing=[list(map(list,x)) for x in sorted(ch-decl)],extra=[list(map(list,x)) for x in sorted(decl-ch)],
 unpowered=unpow,off=off,max_per_pole=max(percov.values()),per_pole=percov,
 rect=dict(area=best[0],short=best[1],all_optimal=sorted(set(opt))),declared_rect=D['empty_rectangle'],
 same_type_facing=len(same),bridgeinfo=[[str(x) for x in b] for b in bridgeinfo])
json.dump(out,open('/home/zhuran24/zmd-research-fresh/求解器/构造/第一张全厂候选/异源核查证据/独立几何.json','w'),ensure_ascii=False,indent=1)
print({k:v for k,v in out.items() if k not in('missing','extra','per_pole','bridgeinfo')})
