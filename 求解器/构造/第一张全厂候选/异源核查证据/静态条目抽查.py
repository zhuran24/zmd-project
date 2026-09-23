import json
from collections import Counter,defaultdict
exec(open('/home/zhuran24/zmd-research-fresh/求解器/构造/第一张全厂候选/异源核查证据/独立几何.py').read().split('# 核心/取货口附近')[0])
res={}
# 边带排布
left=sorted(o['y0'] for o in L['warehouse_outlets'] if o['Dout']==0)
bot=sorted(o['x0'] for o in L['warehouse_outlets'] if o['Dout']==1)
def gap(starts):
  cov=set();[cov.update(range(s,s+3)) for s in starts];return sorted(set(range(70))-cov)
res['left_gap']=gap(left);res['bottom_gap']=gap(bot)
facing=[]
for o in L['warehouse_outlets']:
  ec=edgecells(o,o['Dout'])[1];s=o['Dout'];n=(ec[0]+V[s][0],ec[1]+V[s][1])
  facing.append((o['id'],n,kind.get(occ.get(n))))
res['outlet_facing_not_transport']=[f for f in facing if f[2] not in TR]
res['outlet_items']=Counter(o['item'] for o in L['warehouse_outlets'])
res['core_items']=Counter(q['item'] for q in c['output_items'])
# 核心邻格：6个取货口对面格
cf=[]
for q in c['output_items']:
  e=edgecells(c,q['side'])[q['offset']];n=(e[0]+V[q['side']][0],e[1]+V[q['side']][1]);cf.append((q['side'],q['offset'],n,occ.get(n),kind.get(occ.get(n))))
res['core_out_facing']=cf
# 核心输入口相邻格
ci=[]
for s in (c['Din'],(c['Din']+2)%4):
  for i,e in enumerate(edgecells(c,s)):
    n=(e[0]+V[s][0],e[1]+V[s][1]);ci.append((s,i,n,occ.get(n),kind.get(occ.get(n))))
res['core_in_neighbors']=[x for x in ci if x[3]]
# 角区：矿石格与非运输单位的通道数
ore_cells=set(f[1] for f in facing)
cnt=0
for (a,b) in ch:
  for x,y in ((a,b),(b,a)):
    if kind[x[0]] in TR and kind[y[0]] not in TR and kind[y[0]]!='outlet':
      cell=units[x[0]][0]
      if cell in ore_cells:cnt+=1
res['ore_cell_nonT_channels_excl_outlet']=cnt
# 供电下限
poles=L['power_poles']
def band(p):
  xs={p['x0'],p['x1']};ys={p['y0'],p['y1']}
  return (1 in xs or 69 in xs) + (1 in ys or 69 in ys)
res['poles']=[(p['id'],p['x0'],p['y0'],band(p),sum(cov(p,m) for m in L['machines'])) for p in poles]
J=sum(1 for p in poles if band(p)>=1);P_=len(poles)
res['J']=J;res['9J<=23P-217']=(9*J,23*P_-217)
# 机器台数
res['models']=Counter(m['model'] for m in L['machines'])
res['recipes']=Counter(m['recipe_ids'][0] for m in L['machines'])
json.dump(res,open('/home/zhuran24/zmd-research-fresh/求解器/构造/第一张全厂候选/异源核查证据/静态条目抽查.json','w'),ensure_ascii=False,indent=1,default=str)
for k,v in res.items():print(k,v)
