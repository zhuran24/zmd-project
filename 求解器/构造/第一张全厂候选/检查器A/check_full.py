#!/usr/bin/env python3
"""全厂静态检查器 A。起点副本保存在 meeting_check_full.py。
入口无 example/legacy 宽松模式；通过不认证运行、不更新 L/U。
"""
import sys
sys.dont_write_bytecode=True
import json,hashlib,argparse,traceback
from pathlib import Path
from collections import Counter
from catalog import *
from schema import read_bytes,validate,Invalid
from geometry import Geometry
from design import check_design
from flow import Flow
from projections import geometry_checks,flow_checks
VERSION='checker-a-1.1-gate1'
DYNAMIC={1:'接通先后及离线后所有可达状态',2:'所有分叉分支',3:'全部无线传输相位',4:'所有固定判定次序',5:'N1 避开分级；解除限制需阻尼证明',6:'N2 避开密集结点；解除需分流比证明',7:'需要定序的运行前件及实际服务',15:'每个可达循环态、实际周期20倍数',16:'植物起动、可操作调试办法',20:'调试后的实际存货格无误料',22:'连续制造的逐tick/逐批性质',24:'每tick满速不是平均等式的充分结论',25:'50件库存、每事件前缀界',26:'每tick满速、暂存状态及运行实现',27:'每tick专机运行',28:'实际周期的混料顺序与上游箱体槽位',30:'满额窗口时刻与相位',33:'传输判定前仓库余量与箱内库存',35:'瞬时变化及实际周期',36:'实际周期的完成批次',38:'相邻异种批次逐批清空',39:'连续同产物批段长度',40:'实际库存瞬时/时间平均下界',41:'实际库存满足计算的下界',42:'每个可达循环态的分配',45:'编号格、18件上界、阻塞与相位',46:'轮询均分的全部动态前件',48:'反复物品清单及全部合法先后',52:'箱内最小编号滞货和前缀库存',53:'每事件后箱头库存界',69:'每个可达循环态均满足，而非仅存在本平均流'}
FLOW_NUMS={8,9,10,12,14,15,17,18,21,22,23,24,25,26,27,28,29,31,32,34,35,36,37,38,41,42,43,44,45,47,49,50,51,54,59,67,69,71}
PURE_DYNAMIC={1,2,3,4,7,16,30,33,39,40,46,48,52,53}
class Report:
 def __init__(self):self.checks={};self.formals={};self.flow=None;self.geometry_done=False
 def check(self,code,ok,basis,detail):
  v=self.checks.setdefault(code,{'id':code,'basis':basis,'status':'checked','checked_instances':0,'examples':[],'violations':[]})
  v['checked_instances']+=1
  if len(v['examples'])<3:v['examples'].append(detail)
  if not ok:v['status']='violation';v['violations'].append(detail)
 def unresolved(self,code,basis,detail):self.checks[code]={'id':code,'basis':basis,'status':'unresolved','detail':detail}
 def na(self,code,basis,detail):self.checks.setdefault(code,{'id':code,'basis':basis,'status':'antecedent_false','detail':detail})
 def alias(self,code,other,basis):
  v=self.checks.get(other,{'status':'checked'});self.checks[code]={'id':code,'basis':basis,'status':v['status'],'derived_from':other}
 def formal(self,num,ok,detail):self.check('C%02d'%num,ok,'求解约束#%d·%s'%(num,constraints()[num-1]['name']),detail)
 def formal_na(self,num,why):self.na('C%02d'%num,'求解约束#%d'%num,why)
 def has_fail(self):return any(v['status']in('violation','unresolved','blocked')for v in self.checks.values())
 def blocked(self,code,basis,detail):self.checks[code]={'id':code,'basis':basis,'status':'blocked','detail':detail}
 def ledger(self):
  rows=[]
  aliases={5:'N1',6:'N2',11:'N5a'}
  for c in constraints():
   num=c['number'];code='C%02d'%num;v=self.checks.get(code)
   if v is None and num in aliases:v=self.checks.get(aliases[num])
   if v is None:
    if num in PURE_DYNAMIC:v={'status':'runtime_pending'}
    elif num in FLOW_NUMS:v=({'status':'antecedent_false','detail':'精确流检查完成，相应条件前件未触发'}if self.flow and self.flow['status']=='checked'else{'status':'blocked','detail':'前置结构或精确流未通过，未执行依赖项'})
    else:v=({'status':'antecedent_false','detail':'相应条件式未触发'}if self.geometry_done else{'status':'blocked','detail':'输入/指纹前件失败，未进入几何阶段'})
   if num==20 and self.checks.get('wrong_material',{}).get('status')=='violation':v=self.checks['wrong_material']
   if num in FLOW_NUMS and (not self.flow or self.flow['status']!='checked')and v['status']=='checked':v={**v,'status':'partial_blocked','detail':'几何部分已核，平均流部分因前置条件未获精确见证而未完成'}
   rows.append({**c,'projection_status':v['status'],'check_id':code if code in self.checks else aliases.get(num),'antecedent_evidence':v.get('detail','布局/占格直接核，正流前件仅在精确流见证后取值；详见对应 check_id'),'remaining_obligation':DYNAMIC.get(num,'只证固定候选的静态/平均流必要条件；全部可达循环态的实现另证')})
  return rows

def implementation_hash():
 files=['check_full.py','catalog.py','schema.py','geometry.py','design.py','flow.py','projections.py'];base=Path(__file__).resolve().parent
 return {p:hashlib.sha256((base/p).read_bytes()).hexdigest()for p in files}

def check_candidate(d,time_limit=60):
 r=Report();g=None;x=None;f=None
 try:validate(d)
 except (Invalid,TypeError,KeyError,ValueError)as e:
  r.check('schema',False,'格式§2-9',str(e));return r,None
 r.check('schema',True,'格式§2-9',{})
 for k,path in FILES.items():
  actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest();r.check('fingerprints',d['source_fingerprints'][k]==actual==HASHES[k],'格式§1/10；正式文件版本固定',{'source':path,'actual':actual,'declared':d['source_fingerprints'][k],'supported':HASHES[k]})
 if r.has_fail():return r,None
 g=Geometry(d,r).build();geometry_checks(g,r);r.geometry_done=True;check_design(g,r)
 for cid in NIDS:
  if cid!='N5b':r.check(cid,True,'格式§8.2；共识§三.3',{'no_additional_trigger':True})
 # A structurally invalid instance cannot be certified by an LP built on an incomplete channel set.
 fatal={'bounds','overlap','machine_shape','unit_shape','outlet_boundary','N4a','N4b','N5a','logical_path','logical_path_coverage','source_binding'}
 if any(r.checks.get(k,{}).get('status')=='violation'for k in fatal):r.unresolved('N5b','格式§9','结构前件失败，未对不完整结构求流')
 else:
  f=Flow(g).build();fr,x=f.run(time_limit);r.flow=fr
  if fr['status']=='checked':r.check('N5b',True,'共识 N5b；格式§9',{'delta':fr['delta'],'exact_rows':fr['exact_rows']});flow_checks(g,f,x,r)
  elif fr['status']=='violation':r.check('N5b',False,'共识 N5b；格式§9',fr)
  else:r.unresolved('N5b','共识 N5b；格式§9',fr)
 if d['design']['class']=='p2p':
  r.alias('P3','N5b','共识 P3；全部结构通道正流')
  if r.checks.get('P2_structure',{}).get('status')=='violation':r.alias('P2','P2_structure','共识 P2；路径结构违反')
  elif r.flow and r.flow['status']=='checked':
   r.checks.pop('P2',None)
   vals=lambda i:sum((x[j] for (e,it),j in f.f.items() if e==i),Q())
   r.check('P2',all(all(vals(i)==vals(path[0]) for i in path) for path in g.path_decomposition),'共识 P2；精确流逐路径等速',{'paths':len(g.path_decomposition),'structure':'P2_structure','flow_status':r.flow['status']})
  else:r.blocked('P2','共识 P2；路径结构与等速须分别核验','路径结构见P2_structure；没有精确可行流，完整P2未完成')
 # Explicit no-object cases for runtime conditions; no box does not exempt C49-C51.
 if not g.lay['storage_boxes']:
  for num in [3,33,45,52,53]:r.formal_na(num,'没有协议储存箱')
 elif x is not None:r.formal(45,True,{'projection':'精确箱体逐物品平均守恒；编号格/18件/时序待运行'})
 if not any(u['type']=='gate'and u['k5']is not None for u in g.lay['transport']):r.formal_na(30,'没有设置每5tick上限的准入口')
 return r,g

def make_output(raw,time_limit=60):
 base={'checker':VERSION,'candidate_sha256':hashlib.sha256(raw).hexdigest(),'implementation_sha256':implementation_hash(),'runtime_certified':False,'L_updated':False,'failure_scope':{'fixed':'候选 SHA 对应的全部几何、端口设定、开关、配方集合、allowed_items、已声明逻辑路径速率及附带流见证','open':'未给流见证时其余分物品连续流与批率；不搜索其他布局、配方集合或支持','quantifier':'固定静态候选存在一个精确可核的平均流；非全部可达循环态','not_covered':'初态、调试、四个不得依赖量下运行；失败不降低 U，不推广为几何全域不可行'}}
 try:d=read_bytes(raw);r,g=check_candidate(d,time_limit)
 except (Invalid,ValueError,KeyError,TypeError)as e:
  r=Report();r.check('input',False,'格式§2 严格读取',str(e));g=None
 base['failure_types']=sorted({('dependency_blocked'if v['status']=='blocked'else'conservative_material_risk'if k in {'wrong_material','off_recipe','channel_possible_items','N3b'}else'numerical_or_unsupported_unresolved'if v['status']=='unresolved'else'fixed_candidate_static_violation')for k,v in r.checks.items()if v['status']in('violation','unresolved','blocked')})
 base['failure_scope']['flow_note']='后验投影拒绝某一LP见证时，只拒绝该见证；没有枚举其它连续流，不证明固定几何下不存在其它合格流。只有附带且精确核过的不可行/对偶证书覆盖其明确矩阵。'
 base.update({'status':'rejected'if any(v['status']=='violation'for v in r.checks.values())else'unresolved'if r.has_fail()else'static_pass','static_pass':not r.has_fail(),'checks':list(r.checks.values()),'formal_constraints':r.ledger(),'flow':r.flow})
 if g:
  base['recomputed']={'units':len(g.units),'occupied_cells':len(g.occ),'structural_channels':len(g.channels),'channels':[{'from':dict(zip(['unit','side','offset'],p)),'to':dict(zip(['unit','side','offset'],q))}for p,q in g.channels],'maximum_empty_rectangle':g.maximum,'power_coverage':g.power,'machine_counts':dict(Counter(u['model']for u in g.lay['machines'])),'p2p_paths':[[g.cd[i]['id']if g.cd[i]else i for i in path]for path in g.path_decomposition]}
 return base

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('candidate',type=Path);ap.add_argument('--out',type=Path);ap.add_argument('--time-limit',type=float,default=60);args=ap.parse_args()
 if not 0<args.time_limit<=3600:ap.error('time-limit 必须在 (0,3600]')
 if args.out and not args.out.resolve().is_relative_to(Path(__file__).resolve().parent.parent):ap.error('输出只允许在第一张全厂候选目录下')
 result=make_output(args.candidate.read_bytes(),args.time_limit);s=json.dumps(result,ensure_ascii=False,indent=2)
 if args.out:args.out.write_text(s+'\n',encoding='utf-8');print(json.dumps({'status':result['status'],'static_pass':result['static_pass'],'candidate_sha256':result['candidate_sha256'],'out':str(args.out.resolve())},ensure_ascii=False))
 else:print(s)
 return 0 if result['static_pass']else 1 if result['status']=='rejected'else 2
if __name__=='__main__':sys.exit(main())
