import json
from collections import Counter,defaultdict
exec(open('/home/zhuran24/zmd-research-fresh/求解器/构造/第一张全厂候选/异源核查证据/独立几何.py').read().split('# 核心/取货口附近')[0])
model={m['id']:m['model'] for m in L['machines']}
S=R=E=0;inc=Counter();outc=Counter()
for a,b in ch:
  ta=kind[a[0]] in TR;tb=kind[b[0]] in TR
  if ta and tb:E+=1
  elif tb:S+=1;outc[a[0]]+=1
  else:R+=1;inc[b[0]]+=1
res={'S':S,'R':R,'E':E}
mi=Counter();mo=Counter()
for m in L['machines']:mi[m['model']]+=inc[m['id']];mo[m['model']]+=outc[m['id']]
res['in_by_model']=dict(mi);res['out_by_model']=dict(mo)
res['core_in']=inc['CORE'];res['outlet_out']=sum(outc[o['id']] for o in L['warehouse_outlets']);res['core_out']=outc['CORE']
res['fill_pack']={m['id']:(m['model'],inc[m['id']],outc[m['id']]) for m in L['machines'] if m['model'] in('封装机','灌装机')}
res['grinder_ge3']=sum(1 for m in L['machines'] if m['model']=='研磨机' and inc[m['id']]>=3)
res['shaper_ge2']=sum(1 for m in L['machines'] if m['model']=='塑形机' and inc[m['id']]>=2)
res['machines_no_in']=sum(1 for m in L['machines'] if inc[m['id']]==0)
res['machines_no_out']=sum(1 for m in L['machines'] if outc[m['id']]==0)
res['machines_isolated']=sum(1 for m in L['machines'] if inc[m['id']]==0 and outc[m['id']]==0)
# 设计物品 vs 两端机器配方一致性（路径起点产物/终点原料）
dmap={((e['from']['unit'],e['from']['side'],e['from']['offset']),(e['to']['unit'],e['to']['side'],e['to']['offset'])):e for e in D['design']['physical_channels']}
R_={'粉碎-源矿':({'源矿'},{'源石粉末'}),'粉碎-蓝铁块':({'蓝铁块'},{'蓝铁粉末'}),'粉碎-荞花':({'荞花'},{'荞花粉末'}),'粉碎-砂叶':({'砂叶'},{'砂叶粉末'}),'精炼-蓝铁矿':({'蓝铁矿'},{'蓝铁块'}),'精炼-致密蓝铁':({'致密蓝铁粉末'},{'钢块'}),'精炼-蓝铁粉末':({'蓝铁粉末'},{'蓝铁块'}),'研磨-致密蓝铁':({'蓝铁粉末','砂叶粉末'},{'致密蓝铁粉末'}),'研磨-致密源石':({'源石粉末','砂叶粉末'},{'致密源石粉末'}),'研磨-细磨荞花':({'荞花粉末','砂叶粉末'},{'细磨荞花粉末'}),'塑形-钢质瓶':({'钢块'},{'钢质瓶'}),'配件-钢制零件':({'钢块'},{'钢制零件'}),'种植-荞花':({'荞花种子'},{'荞花'}),'种植-砂叶':({'砂叶种子'},{'砂叶'}),'采种-荞花':({'荞花'},{'荞花种子'}),'采种-砂叶':({'砂叶'},{'砂叶种子'}),'封装-电池':({'钢制零件','致密源石粉末'},{'高容谷地电池'}),'灌装-胶囊':({'钢质瓶','细磨荞花粉末'},{'精选荞愈胶囊'})}
rec={m['id']:m['recipe_ids'][0] for m in L['machines']}
bad=[]
for (a,b),e in dmap.items():
  it=set(e['allowed_items'])
  if a[0] in rec and not it<=R_[rec[a[0]]][1]:bad.append(('src',e['id'],a[0],sorted(it)))
  if b[0] in rec and not it<=R_[rec[b[0]]][0]:bad.append(('dst',e['id'],b[0],sorted(it)))
  if b[0]=='CORE' and not it<={'高容谷地电池','精选荞愈胶囊'}:bad.append(('core',e['id'],sorted(it)))
res['label_mismatch']=bad
print(json.dumps(res,ensure_ascii=False,indent=0))
json.dump(res,open('/home/zhuran24/zmd-research-fresh/求解器/构造/第一张全厂候选/异源核查证据/通道计数.json','w'),ensure_ascii=False,indent=1)
