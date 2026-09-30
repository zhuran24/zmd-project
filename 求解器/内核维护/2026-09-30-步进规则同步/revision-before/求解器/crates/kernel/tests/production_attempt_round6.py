"""K6布局试作：L6六种满仓、仓外空；所有配方回源，实际尝试并保存精确卡点。"""
import sys
sys.dont_write_bytecode=True
import json,subprocess
from pathlib import Path
import build_fixtures as b
from generate_examples import unit
from runtime_example import quantity as q,time_value as t,decision
from migrate_round5 import migrate,save
ROOT=b.ROOT;BASE=ROOT/'数据/样例';E=ROOT/'crates/kernel/evidence/round6';BIN=ROOT/'target/release/kernel';CFG=ROOT/'规格/内核配置-v1.json'
def call(args,allow=False):
 p=subprocess.run([str(BIN),*map(str,args),'--config',str(CFG)],capture_output=True,text=True)
 assert allow or p.returncode==0,(args,p.stdout,p.stderr)
 return dict(exit_code=p.returncode,stdout=json.loads(p.stdout) if p.stdout.strip() else None,stderr=p.stderr)
def generate():
 kinds={r['id']:r for r in b.CATALOG['units']};recipes=[r for r in b.CATALOG['recipes'] if r['id']!='精炼-蓝铁粉末']
 for name in ('种植-荞花','种植-砂叶'):recipes.append(next(r for r in b.CATALOG['recipes'] if r['id']==name))
 # 19台配方覆盖链；上下游经真实仓库端口/无线入库连接，尚未满足达标必要口数。
 units=[];sources=[];placement=[];bottom=12;left=0
 for i,recipe in enumerate(recipes):
  kind=recipe['kind'];w=int(kinds[kind]['dimensions']['width']['value']);h=int(kinds[kind]['dimensions']['height']['value']);span=w+1
  if bottom+span<=70:origin=bottom;bottom+=span;side='bottom'
  else:origin=left;left+=span;side='left';assert left<=58,('左边界空间不足',left)
  def place(uid,kind,x,y):
   if side=='bottom':return unit(uid,kind,x,y)
   width=int(kinds[kind]['dimensions']['width']['value']);return unit(uid,kind,y,70-x-width,'r270')
  uid=f'm{i}';units.append(place(uid,kind,origin,2))
  for j,item in enumerate(recipe['inputs']):
   source=f'src{i}_{j}';units.append(place(source,'仓库取货口',origin+3*j,0));units.append(place(f'in{i}_{j}','传送带',origin+3*j+1,1));sources.append((source,item))
  output_count=min(3,max(int(v['value']) for v in recipe['outputs'].values()))
  units.append(place(f'box{i}','协议储存箱',origin,h+3))
  units.extend(place(f'out{i}_{j}','传送带',origin+j,h+2) for j in range(output_count))
  units.append(place(f'power{i}','供电桩',origin+1,h+6))
  placement.append(dict(unit=uid,recipe=recipe['id'],side=side,offset=origin))
 b.OUT=BASE;name='双成品满仓起动试作';d=b.generate(name,units);b.set_axis(d,'warehouse.external_supply',{'kind':'sufficient'})
 for switch in d['settings']['switches']:switch['enabled']=True
 seed=d['initial_state']['nonwarehouse']['value'];assert not any(r['contents'] for r in seed['inventory'])
 slots=seed['warehouse']['slots'];identities={r['item']:r['slot'] for r in slots if r['item']}
 for source,item in sources:
  if item not in identities:
   slot=f'W_stage_{len(identities)}';identities[item]=slot
   slots.append(dict(slot=slot,item=None,quantity=q(0),empty_identity=decision(item,'显式空仓格身份参数；数量为0，不注入物品；该身份选择的历史可达性未证')))
  d['settings']['warehouse_assignments'].append(dict(port=source+':north:1',slot=identities[item]))
 d['initial_state']['reachability']=decision({'kind':'conditional_state','document':str(E/'K6布局卡点.md'),'scope':'六类物品按L6各80000，其它仓内外数量为0；初始空格身份和已建成种子的历史可达性未证'},'K6条件布局实测，不从预置中间物料或成品开始')
 d['scenario']['assertions']=['全部真实配方来自正式静态目录；矿与植物仓口供料；19台制造，只用于找实现/布局卡点，未声称217台必要条件已满足。','仓库过站增加出库需求；这不是满足52矿口满速的达标布线。']
 path=BASE/(name+'.json');save(path,migrate(d));call(['seed',path,'--out',path]);return path,placement
if __name__=='__main__':
 path,placement=generate();static=call(['check',path,'--cycle-domain']);save(E/'K6-domain.json',static)
 run=call(['run',path,'--no-output','--ticks',512]);save(E/'K6-run.json',run)
 cert=BASE/'双成品满仓起动试作-周期证书-kernel.json';search=call(['cycle',path,'--no-record','--max-ticks',512,'--out',cert],True);save(E/'K6-search.json',search)
 result=json.loads(cert.read_text());verification=call(['verify-cycle',cert]);save(E/'K6-verify.json',verification)
 actual=run['stdout']['actual_inbound'];assert actual.get('高容谷地电池',0)>0 and actual.get('精选荞愈胶囊',0)>0,actual
 report=dict(status='attempt_completed_target_not_met',input=str(path),certificate=str(cert),placements=placement,units=len(json.loads(path.read_text())['layout']['units']),physical_channels=len(json.loads(path.read_text())['layout']['physical_channels']),initial_inventory='L6六种各80000，其它数量0；空格身份与已建种子历史仍条件化',finite_run=run['stdout'],cycle_status=result['status'],completed_ticks=result['budget']['completed_ticks'],rates=result['cycle']['rates'] if result['cycle'] else None,bottleneck_kind='layout',bottleneck='仅1封装、1灌装，每台5tick一件，故即使无限齐料也分别至多1/5，严格低于3/5及11/20；仓库中转还占用矿石所需的出库端口。本布局不能达到K6目标。D五项静态通过，512刻动态无D停止，台账真实记录两成品。',remaining='尚未构造同时满足目标率且仓库外/非成品仓库库存闭合的布局；不把预算未决或有限正交付称达标周期。')
 save(E/'K6-result.json',report);print(json.dumps({k:report[k] for k in ('status','units','physical_channels','cycle_status','completed_ticks')},ensure_ascii=False))
