"""只对四格环独立按条文手推20刻，不调用Rust或Python参考转移器。"""
import json,copy
from pathlib import Path
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');OUT=Path(__file__).resolve().parent
path=ROOT/'数据/样例/生产循环环带-周期证书-kernel.json';result=json.loads(path.read_text());cycle=result['cycle'];state=copy.deepcopy(cycle['start_state'])
def q(n):return {'value':str(n),'category':'算术推论'}
def tv(n):return {'kind':'rational','value':{'value':str(n),'category':'候选'}}
def physical(v):
 if isinstance(v,list):return [physical(x)for x in v]
 if isinstance(v,dict):return {k:physical(x)for k,x in v.items()if k not in ('category','basis')}
 return v
names='abcd';channels=[f'PC|{a}:east:0|{b}:south:0'for a,b in zip(names,names[1:]+names[:1])]
assert int(cycle['start_time']['value']['value'])==0 and cycle['period']['value']=='20'
assert [(r['slot'],r['contents'][0]['item'])for r in state['inventory']if r['contents']]==[('b:transport:0','高容谷地电池')]
assert state['progress'][0]['cooldowns'][0]['remaining']==tv(5)
position=1;entered=0;cooldown=5;rows=[]
for tick in range(1,21):
 # 生产代表化独立于玩家拿取；本例t=1只移走起点仓库的5胶囊。
 adjustment=[]
 for slot in state['warehouse']['slots']:
  if slot['item'] in ['高容谷地电池','精选荞愈胶囊']:
   adjustment.append({'item':slot['item'],'quantity':q(int(slot['quantity']['value'])),'reason':'production_representative'})
   slot['empty_identity']={'status':'specified','value':slot['item'],'basis':['手推：retain_history']};slot['item']=None;slot['quantity']=q(0)
 cooldown=max(cooldown-1,0);moves=[];events=[]
 for sweep in range(2):
  for index in range(4):
   event={'event':f'J|{tick}|{sweep}|{index}','operation':'move','target':channels[index]}
   if position!=index:event.update(outcome='failure',detail='source_empty')
   elif tick-entered<1:event.update(outcome='failure',detail='residence')
   else:
    event.update(outcome='success',detail='');position=(position+1)%4;entered=tick
    moves.append({'event':event['event'],'channel':channels[index],'item':'高容谷地电池','quantity':q(1)})
   events.append(event)
  event={'event':f'J|{tick}|{sweep}|4','operation':'transfer','target':'box'}
  if cooldown==0:event.update(outcome='success',detail='empty_box');cooldown=5
  else:event.update(outcome='guard_false',detail='cooldown')
  events.append(event)
 assert len(moves)==1
 for slot in state['inventory']:
  slot['contents']=([{'item':'高容谷地电池','quantity':q(1),'entered_at':tv(entered)}]if slot['slot']==names[position]+':transport:0'else[])
 state['environment']['time']=tv(tick);state['progress'][0]['cooldowns'][0]['remaining']=tv(cooldown)
 sc=state['semantic_context'];sc['judgment_context']['value']['instant']=tv(tick)
 source,dest=moves[0]['channel'].split('|')[1:]
 sc['tick_context']['value']={'window_start':tv(tick),'window_end':tv(tick+1),'movements':moves,'internal_passages':[],'port_usage':[{'port':p,'quantity':q(1)}for p in sorted([source,dest])]}
 observed=result['run_record']['trace']['ticks'][tick]
 assert physical(state)==physical(observed['state']),('state',tick)
 assert events==[{k:v for k,v in e.items()if k!='basis'}for e in observed['events']],('events',tick)
 assert observed['closure']['kind']=='no_success_state_repeat' and observed['closure']['scan_rounds']==2
 ledger=observed['warehouse_ledger']
 assert physical(ledger['representative_adjustment'])==physical(adjustment)
 assert all(ledger[k]==[]for k in ['core_inbound','wireless_inbound','port_outbound','external_supply','player_withdrawal'])
 assert all(r['actual_inbound']['value']=='0'for r in ledger['totals'])
 rows.append({'tick':tick,'move':channels[(position-1)%4],'position':names[position],'age':tick-entered,'cooldown':cooldown,'empty_transfer':tick%5==0,'representative_adjustment':adjustment,'state_values_match':True,'events_match':True})
assert position==1 and cooldown==5 and entered==20
assert physical(state)==physical(cycle['end_state'])
report={'status':'pass','certificate':str(path),'method':'由t=0的完整循环起点手推：单件四格环每刻移动1格，空箱每5刻尝试；未调用已有转移函数。20个完整StateSeed逐值比较，仅不比较basis/category文字，全部事件身份/操作/对象/结果/detail及闭包轮数另比较。','period':20,'start':0,'end':20,'rates':{'高容谷地电池':'0/20','精选荞愈胶囊':'0/20'},'rows':rows}
(OUT/'manual-cycle-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('20刻手推状态值、事件、台账及闭包均相等；P=lcm(4,5)=20')
