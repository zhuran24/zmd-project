"""任务8适用验收：局部机制、独立事务账、新证书及故意篡改拒收。"""
from run_command import ROOT,E,run
from pathlib import Path
import sys,json,copy,hashlib,os
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'crates/kernel/tests'))
from audit_task7 import audit_ledger,decode_trace,tm,n
from verify_all import schema_check
BIN=ROOT/'target/release/kernel';CFG=ROOT/'规格/内核配置-v1.json';S=ROOT/'数据/样例/任务7内核';O=E/'runs';N=E/'negative';O.mkdir(exist_ok=True);N.mkdir(exist_ok=True)
checks=[]
def read(p):return json.loads(p.read_text())
def write(p,v):p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def check(name,condition,detail=None):
 checks.append({'name':name,'passed':bool(condition),'detail':detail});write(E/'checks.json',checks)
 assert condition,(name,detail)
def runrec(name,ticks=1,extra=(),code=0,tag=None):
 dest=(O if code==0 else N)/((tag or name)+'.json')
 if '--format' not in extra:extra=['--format','checkpoint_delta','--checkpoint-interval','16',*extra]
 run('run-'+(tag or name),[BIN,'run',S/(name+'.json'),'--config',CFG,'--ticks',str(ticks),'--out',dest,*extra],expected=code)
 data=read(dest);schema_check([dest]);check('schema:'+dest.name,True)
 if code==0:
  run('verify-record-'+(tag or name),[BIN,'verify-record',dest,'--config',CFG])
  result=audit_ledger(data,read(S/(name+'.json')));check('独立逐事件账:'+dest.name,True,result)
 return data,dest

def tickstate(r,index=-1):return decode_trace(r['trace'])['ticks'][index]['state']
def stock(s,slot):return sum(n(c['quantity']) for r in s['inventory'] if r['slot']==slot for c in r['contents'])
def deliveries(r):
 totals={}
 for t in r['trace']['ticks']:
  for v in t['warehouse_ledger']['wireless_inbound']:totals[v['item']]=totals.get(v['item'],0)+n(v['quantity'])
 return totals

def main():
 for name in ['装载与普通制造','无线多格歧义']:
  p=run('check-'+name,[BIN,'check',S/(name+'.json'),'--config',CFG]);check('只装载:'+name,read_stdout(p)['status']=='input_checked',{'trajectory_executed':False})
 run('old-input-rejected',[BIN,'check',ROOT/'数据/样例/混做粉碎机两下游.json','--config',CFG],expected=2)
 r,_=runrec('装载与普通制造',4,extra=['--format','full_state_each_instant']);check('普通制造实际完成',n(r['validation_scope']['manufacturing_cycles_completed'])>0)
 for name,expected in [('无线部分接收',{'高容谷地电池':1}),('无线一满一可收',{'精选荞愈胶囊':3}),('无线多格全收',{'高容谷地电池':5}),('同刻双箱争余量',{'高容谷地电池':1})]:
  r,_=runrec(name,6 if name=='无线部分接收' else 1);check('实际无线量:'+name,deliveries(r)==expected,deliveries(r))
  if name=='无线部分接收':check('部分残留固定原格',stock(tickstate(r),'box:storage:0')==1 and stock(tickstate(r),'box:storage:1')==3)
 for name in ['无线空箱','无线全拒收']:
  r,_=runrec(name,6)
  attempts=[tm(t['time']) for t in r['trace']['ticks'] for ev in t['events'] if ev['operation']=='transfer' and ev['outcome'] in ['success','failure']]
  check('零发送尝试节拍:'+name,attempts==[0,5] and deliveries(r)=={},attempts)
 for name in ['身份断边恢复','身份实际切换','累计调低保留','累计调高资格','双门窗口恢复','阻尼恢复']:
  r,_=runrec(name,12 if name in ['双门窗口恢复','阻尼恢复'] else 6)
  if name.startswith('身份'):
   events=[json.loads(ev['detail']) for t in r['trace']['ticks'] for ev in t['events'] if ev['operation']=='gate_identity_maintenance']
   check('原几何恢复:'+name,any(e['restored_channels'] for e in events),events)
   if name=='身份实际切换':check('本次运行先断后恢复',any(e['removed_channels'] for e in events) and any(e['restored_channels'] for e in events))
  if name.startswith('累计'):
   g=tickstate(r)['logistics']['gate_counters'][0]
   check('累计真实数:'+name,n(g['total_received'])==(3 if name=='累计调低保留' else 5),g)
 r,_=runrec('成熟旧货重试',1);s=tickstate(r);check('旧件同刻再尝试而新件停留',stock(s,'a:transport:0')==0 and stock(s,'b:transport:0')==1 and stock(s,'c:transport:0')==1)
 bad,path=runrec('无线多格歧义',1,code=2);check('歧义停止无完成转移',bad['status']=='unsupported' and bad['trace']['ticks']==[] and '多个编号格' in str(bad['open_items']))
 # 两种记录编码和缓存开关均对实际轨迹比较。
 normal,p=runrec('身份实际切换',2,tag='cache-on')
 other,_=runrec('身份实际切换',2,extra=['--no-cache'],tag='cache-off');check('缓存开关全记录相同',normal==other)
 delta,_=runrec('身份实际切换',2,extra=['--format','full_state_each_instant'],tag='identity-full');check('增量完整重建',decode_trace(normal['trace'])==decode_trace(delta['trace']))
 # 从已验记录恢复后，固定参数保留，第一刻从t+1起。
 cp=N/'checkpoint-input.json';run('checkpoint',[BIN,'checkpoint',p,'--config',CFG,'--out',cp]);run('checkpoint-run',[BIN,'run',cp,'--config',CFG,'--ticks','1','--out',O/'checkpoint-record.json']);check('恢复第一刻',tm(read(O/'checkpoint-record.json')['trace']['ticks'][0]['time'])==2)
 for name,period,withrecord in [('生产环带',20,False),('静止成熟与暂停键',1,True),('累计审计与窗口周期',6,False),('累计调低保留',1,False)]:
  dest=O/(name+'-cycle.json');args=[BIN,'cycle',S/(name+'.json'),'--config',CFG,'--max-ticks','30','--out',dest]
  if not withrecord:args+=['--no-record']
  run('cycle-'+name,args);c=read(dest);schema_check([dest]);check('周期键与范围:'+name,c['status']=='diagnostic_cycle' and n(c['cycle']['period'])==period and c['cycle']['start_key']==c['cycle']['end_key'],{'status':c['status'],'period':c.get('cycle',{}).get('period')})
  run('verify-cycle-'+name,[BIN,'verify-cycle',dest,'--config',CFG])
  check('正式对应未冒领:'+name,c['environment_assumption']=='仓库收得下成品。' and c['cycle']['correspondence']['forward_projection']['status']=='unresolved' and c['cycle']['correspondence']['reverse_reconstruction']['status']=='not_claimed')
  if name=='累计审计与窗口周期':
   a=c['cycle']['start_state']['logistics']['gate_counters'][0];b=c['cycle']['end_state']['logistics']['gate_counters'][0];key=c['cycle']['start_key']['state']['logistics']['gate_counters'][0]
   check('累计删除而完整真值递增',n(b['total_received'])>n(a['total_received']) and key['total_received'] is None)
  if name=='静止成熟与暂停键':
   key=c['cycle']['start_key']['state'];check('成熟残余零且暂停deadline删审计',next(r for r in key['inventory'] if r['slot']=='belt:transport:0')['contents'][0]['entered_at']=={'residual':{'value':'0'}} and key['semantic_context']['pending_events']['value'][0]['trigger']['kind']=='remaining_work')
  if name=='累计调低保留':check('固定C键饱和',c['cycle']['start_key']['state']['logistics']['gate_counters'][0]['total_received']=={'value':'2'})
 # 可加载预算未决与源装载失败分开回放。
 dest=O/'budget-cycle.json';run('cycle-budget',[BIN,'cycle',S/'生产环带.json','--config',CFG,'--max-ticks','1','--no-record','--out',dest]);run('verify-budget',[BIN,'verify-cycle',dest,'--config',CFG]);check('预算未决',read(dest)['status']=='inconclusive' and read(dest)['budget']['completed_ticks']==1)
 dest=N/'load-stop-cycle.json';run('cycle-load-stop',[BIN,'cycle',ROOT/'数据/样例/生产循环环带.json','--config',CFG,'--max-ticks','1','--no-record','--out',dest],expected=2);schema_check([dest]);run('verify-load-stop',[BIN,'verify-cycle',dest,'--config',CFG]);check('装载失败未步进',read(dest)['budget']['completed_ticks']==0)
 # 输入生命周期及被删审计字段的资源/身份前件。
 for label,modify in [
  ('判定排序错组',lambda v:v['parameters']['fixedness_unproven'].update({'judgment.order':v['parameters']['fixed'].pop('judgment.order')})),
  ('制造日程过晚',lambda v:v['initial_state']['nonwarehouse']['value']['semantic_context']['pending_events']['value'][0].update(event='C|100|machine',trigger={'kind':'at_time','value':{'kind':'rational','value':{'value':'100','category':'候选'}}}))]:
  v=read(S/('静止成熟与暂停键.json' if label=='制造日程过晚' else '成熟旧货重试.json'));modify(v);p=N/(label+'-input.json');write(p,v)
  run('negative-'+label,[BIN,'cycle',p,'--config',CFG,'--max-ticks','1','--no-record','--out',N/(label+'-result.json')],expected=2);check(label,True)
 # 直接改真实同种年龄分组不改变物理键的物种总量。
 v=read(S/'静止成熟与暂停键.json');rows=v['initial_state']['nonwarehouse']['value']['inventory'];box=next(r for r in rows if r['slot']=='box:storage:0');base=copy.deepcopy(box['contents'][0]);base['quantity']['value']='1';second=copy.deepcopy(base);second['entered_at']['value']['value']='-50';box['contents']=[base,second]
 p=N/'同种年龄分组-input.json';write(p,v);dest=O/'同种年龄分组-cycle.json';run('cycle-同种年龄分组',[BIN,'cycle',p,'--config',CFG,'--max-ticks','3','--no-record','--out',dest]);run('verify-同种年龄分组',[BIN,'verify-cycle',dest,'--config',CFG]);key=read(dest)['cycle']['start_key'];check('非运输同种年龄分组合并',key==read(O/'静止成熟与暂停键-cycle.json')['cycle']['start_key'])
 # 篡改生成后的记录，必须被独立语义入口拒绝。
 for label,change in [
  ('篡改入库账',lambda x:x['trace']['ticks'][0]['warehouse_ledger']['totals'][0]['actual_inbound'].update(value='999')),
  ('篡改固定排序',lambda x:x['parameter_assignment']['fixed']['judgment.order']['value']['template_order'].reverse()),
  ('删除证据范围',lambda x:x.pop('evidence_scope'))]:
  v=copy.deepcopy(normal);change(v);p=N/(label+'.json');write(p,v);run('negative-'+label,[BIN,'verify-record',p,'--config',CFG],expected=2);check(label,True)
 original=read(O/'静止成熟与暂停键-cycle.json')
 for label,change in [
  ('伪造真实反例',lambda x:x.update(status='counterexample',level='concrete_full_cycle')),
  ('篡改周期长度',lambda x:x['cycle']['period'].update(value='2')),
  ('篡改证明指纹',lambda x:x['cycle']['normalization']['mapping_proof'].update(sha256='0'*64)),
  ('篡改引用指纹',lambda x:x['run_record_ref'].update(sha256='0'*64))]:
  v=copy.deepcopy(original);change(v);p=N/(label+'.json');write(p,v);run('negative-'+label,[BIN,'verify-cycle',p,'--config',CFG],expected=2);check(label,True)
 # 相对证书路径及证明引用路径。
 dest=E/'relative/cycle.json';v=copy.deepcopy(original)
 for row in v['fingerprints']:row['path']=os.path.relpath(row['path'],dest.parent)
 for key in ['replay_input_ref','run_record_ref']:
  v[key]['path']=os.path.relpath(v[key]['path'],dest.parent);v[key]['producer']['path']=os.path.relpath(v[key]['producer']['path'],dest.parent)
 def relative(node):
  if isinstance(node,dict):
   if set(node)=={'path','sha256'}:node['path']=os.path.relpath(node['path'],dest.parent)
   else:
    for val in node.values():relative(val)
  elif isinstance(node,list):
   for val in node:relative(val)
 relative(v['evidence_scope']);relative(v['cycle']['normalization']);relative(v['cycle']['reception_scope']);relative(v['cycle']['correspondence'])
 write(dest,v);run('verify-relative-cycle',[BIN,'verify-cycle',dest,'--config',CFG]);check('相对引用实际重放',True)
 run('batch-current',[BIN,'verify-batch',O,'--config',CFG]);check('批量当前版本',True)
 write(E/'checks.json',checks);print('PASS',len(checks),'checks')

def read_stdout(p):return json.loads(p.stdout)
if __name__=='__main__':main()
