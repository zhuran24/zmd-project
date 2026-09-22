"""任务8局部机制输入；原样例保持史料，显式迁移到本轮参数与源。"""
import sys,copy,json,hashlib
from pathlib import Path
sys.dont_write_bytecode=True
from run_command import ROOT,E,run
sys.path.insert(0,str(ROOT/'crates/kernel/tests'))
sys.path.insert(0,str(ROOT/'数据/样例'))
import build_fixtures as b
from generate_examples import unit
from runtime_example import quantity as q,time_value as t,decision
OUT=ROOT/'数据/样例/任务7内核';OUT.mkdir(exist_ok=True);b.OUT=OUT
CFG=ROOT/'规格/内核配置-v1.json';config=json.loads(CFG.read_text());BIN=ROOT/'target/release/kernel'
changes=[]
def read(p):return json.loads(p.read_text())
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def state(d):return d['initial_state']['nonwarehouse']['value']
def setaxis(d,k,v):
 for g in ['fixed','offline_mutable','fixedness_unproven']:
  if k in d['parameters'][g]:d['parameters'][g][k]['value']=v;return
 raise KeyError(k)
def migrate(d):
 p=d['parameters'];old={k:v for g in ['fixed','offline_mutable','fixedness_unproven'] for k,v in p[g].items()}
 for g in ['fixed','offline_mutable','fixedness_unproven']:p[g]={}
 for k,r in config['axes'].items():
  v=copy.deepcopy(old[k]);g='fixed' if r['lifetime'].startswith('F') else 'offline_mutable' if r['lifetime']=='O' else 'fixedness_unproven'
  if r['disposition']!='由输入全称量化':v['value']=copy.deepcopy(r['value'])
  v['basis']=['任务7内核显式迁移；现行配置 '+config['revision']+'；'+k]
  p[g][k]=v
 for ref,path in [(d['catalog'],ROOT/'数据/正式静态目录.json'),(p['axis_registry'],ROOT/'规格/选择点参数轴.md')]:ref.update(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 state(d)['semantic_context']['parameter_values']=[dict(axis=k,value=copy.deepcopy(v),lifetime=life) for g,life in [('fixed','F'),('offline_mutable','O'),('fixedness_unproven','U')] for k,v in p[g].items()]
 return d
def put(d,slot,item,n,age=-1):
 next(r for r in state(d)['inventory'] if r['slot']==slot)['contents']=[dict(item=item,quantity=q(n),entered_at=t(age))] if n else []
def warehouse(d,item,n):
 rows=state(d)['warehouse']['slots'];slot=next((r for r in rows if r['item']==item or r['empty_identity']['value']==item),None)
 if slot is None:slot={'slot':'test_'+item};rows.append(slot)
 slot.update(item=item if n else None,quantity=q(n),empty_identity=decision(item,'合成种子历史身份') if not n else decision(None,'非空格身份由item承载','not_applicable'))
def finish(name,d):
 d['scenario']['name']='任务7-'+name
 d['initial_state']['reachability']=decision({'kind':'conditional_state','document':str(ROOT/'crates/kernel/周期键读取审计.md'),'scope':'局部机制合成种子；任务8没有证明实际调试程序的全部可达后态'},'任务7工程局部验证')
 d=migrate(d);path=OUT/(name+'.json');write(path,d)
 seed=E/(name+'-seed.json');run('seed-'+name,[BIN,'seed',path,'--config',CFG,'--out',seed])
 write(path,read(seed));seed.unlink()
 changes.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'purpose':'synthetic_execution；单一明确参数点'})
 return path

def main():
 for name,old in [('装载与普通制造','混做粉碎机两下游'),('双门窗口恢复','分流器三路轮询'),('阻尼恢复','阻尼切支恢复核验'),('生产环带','生产循环环带')]:
  d=read(ROOT/'数据/样例'/(old+'.json'));finish(name,d)
 base=b.generate('无线模板',[unit('box','协议储存箱',10,10),unit('power','供电桩',14,10)])
 setaxis(base,'warehouse.external_supply',{'kind':'sufficient'})
 base['settings']['switches'][0]['enabled']=True
 for name,items,stocks in [
  ('无线部分接收',[('高容谷地电池',2),('精选荞愈胶囊',3)],{'高容谷地电池':79999,'精选荞愈胶囊':80000}),
  ('无线一满一可收',[('高容谷地电池',2),('精选荞愈胶囊',3)],{'高容谷地电池':80000,'精选荞愈胶囊':0}),
  ('无线空箱',[],{}),
  ('无线全拒收',[('高容谷地电池',2)],{'高容谷地电池':80000}),
  ('无线多格全收',[('高容谷地电池',2),('高容谷地电池',3)],{'高容谷地电池':0}),
  ('无线多格歧义',[('高容谷地电池',2),('高容谷地电池',3)],{'高容谷地电池':79998}),
 ]:
  d=copy.deepcopy(base)
  for i,(item,n) in enumerate(items):put(d,f'box:storage:{i}',item,n)
  for item,n in stocks.items():warehouse(d,item,n)
  finish(name,d)
 d=b.generate('恢复模板',[unit('source','协议储存箱',10,10),unit('gate','物品准入口',10,13),unit('belt','传送带',10,14),unit('sink','协议储存箱',10,15)])
 setaxis(d,'warehouse.external_supply',{'kind':'sufficient'})
 d['settings']['gates'][0].update(item='源矿',total_limit=None,window_limit=q(1))
 put(d,'source:storage:0','源矿',4)
 state(d)['logistics']['gate_counters'][0]['blocked_reasons']=['identity_mismatch']
 finish('身份断边恢复',d)
 for name,n,limit in [('累计调低保留',3,2),('累计调高资格',3,5)]:
  v=copy.deepcopy(d);v['settings']['gates'][0].update(total_limit=q(limit),window_limit=None)
  g=state(v)['logistics']['gate_counters'][0];g.update(total_received=q(n),blocked_reasons=['total_exhausted'] if n>=limit else [])
  finish(name,v)
 chain=b.generate('链模板',[unit('a','传送带',10,10),unit('b','传送带',10,11),unit('c','传送带',10,12)])
 setaxis(chain,'warehouse.external_supply',{'kind':'sufficient'})
 put(chain,'a:transport:0','高容谷地电池',1);put(chain,'b:transport:0','高容谷地电池',1)
 finish('成熟旧货重试',chain)
 actual=b.generate('身份切换模板',[unit('source','协议储存箱',10,10),unit('gate','物品准入口',10,13),unit('bypass','传送带',12,13),unit('sink','协议储存箱',10,14)])
 setaxis(actual,'warehouse.external_supply',{'kind':'sufficient'})
 actual['settings']['gates'][0].update(item='源矿',window_limit=q(1))
 put(actual,'source:storage:0','高容谷地电池',1);put(actual,'source:storage:1','源矿',3)
 finish('身份实际切换',actual)
 ring=b.generate('门环模板',[unit('a','传送带',10,10,'r90',1),unit('gate','物品准入口',10,11),unit('b','传送带',10,12,'r0',1),unit('c','传送带',11,12,'r270',1),unit('down','传送带',11,11,'r180'),unit('d','传送带',11,10,'r180',1)])
 setaxis(ring,'warehouse.external_supply',{'kind':'sufficient'})
 ring['settings']['gates'][0].update(item='高容谷地电池',window_limit=q(1))
 put(ring,'a:transport:0','高容谷地电池',1)
 finish('累计审计与窗口周期',ring)
 twin=b.generate('双箱模板',[unit('first','协议储存箱',10,10),unit('second','协议储存箱',20,10),unit('power1','供电桩',14,10),unit('power2','供电桩',24,10)])
 setaxis(twin,'warehouse.external_supply',{'kind':'sufficient'})
 for sw in twin['settings']['switches']:sw['enabled']=True
 put(twin,'first:storage:0','高容谷地电池',2);put(twin,'second:storage:0','高容谷地电池',2);warehouse(twin,'高容谷地电池',79999)
 finish('同刻双箱争余量',twin)
 # 静止成熟货、非运输旧年龄以及暂停制造的旧预计deadline都应允许物理键重复。
 d=b.generate('静止模板',[unit('belt','传送带',10,10),unit('box','协议储存箱',15,10),unit('machine','粉碎机',25,10)])
 setaxis(d,'warehouse.external_supply',{'kind':'sufficient'});put(d,'belt:transport:0','高容谷地电池',1,age=-100);put(d,'box:storage:0','精选荞愈胶囊',2,age=-100)
 put(d,'machine:buffer:0','源矿',1)
 pr=next(r for r in state(d)['progress'] if r['unit']=='machine');pr.update(phase='working',recipe='粉碎-源矿',locked_recipe='粉碎-源矿',candidate_recipes=['粉碎-源矿'],remaining=t(1))
 finish('静止成熟与暂停键',d)
 for n in ['无线模板','恢复模板','链模板','静止模板','身份切换模板','门环模板','双箱模板']:(OUT/(n+'.json')).unlink()
 write(E/'sample-manifest.json',changes)
 print('generated',len(changes))
if __name__=='__main__':main()
