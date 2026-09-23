#!/usr/bin/env python3
"""检查器 B：full-factory-static-v1 全厂静态闸门，输出绑定输入/源码 SHA。
起点为已复制的 seat-opus-3/check.py；原文存 legacy_check.py，仅用于旧样本回归。
无 git、内核或运行模拟依赖；stdout JSON；退出 0=静态通过，1=违反，2=未决/输入不合法。
"""
import os, sys
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
import argparse, hashlib, json, time, math
from pathlib import Path
from catalog import *
from schema import loads,validate,Invalid
from geometry import Checks,Geometry,structural,check_rectangle
from interfaces import check_interfaces
from flow import build,vector_from_witness,witness
from audit import static_audit,rectangle_audit,flow_audit,Audit
VERSION='checker-b-static-v1.1'
WRITE_ROOT=BASE.parent

def code_fingerprint():
 files=['check.py','catalog.py','schema.py','geometry.py','interfaces.py','flow.py','audit.py','constraint_catalog.json','constraint_catalog_71.json']
 return {n:hashlib.sha256((BASE/n).read_bytes()).hexdigest() for n in files}

def check_document(d,verify_sources=True,time_limit=120):
 c=Checks();a=Audit(c);report={'checker':VERSION,'checks':c.records,'flow':{'status':'BLOCKED'},'runtime_certified':False,'updates_L':False,
  'candidate_sha256':hashlib.sha256((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest(),
  'candidate_hash_basis':'UTF-8 JSON ensure_ascii=False indent=2 plus final newline; CLI replaces with exact file bytes',
  'checker_files_sha256':code_fingerprint(),
  'coverage':{'fixed':['输入候选的完整布局、设定、配方与物品支持；输入非法时仅核语法'],
              'open':['未固定的连续平均流与配方批率'],
              'quantifier':'仅本输入及其受限域的静态检查',
              'excluded_from_scope':['初态','调试','全部合法先后','可达循环态'],
              'failure_scope':'仅拒绝或暂不认证本输入；不排除其他布局，不降低 U 或提高 L。'}}
 try: validate(d,verify_sources)
 except (Invalid,OSError) as e:
  c.add('strict-schema',False,'格式 §1–9；正式文件指纹',str(e));report['status']='INVALID_INPUT';report['constraints']=a.finish();return report
 c.add('strict-schema',True,'格式 §1–9；正式文件指纹')
 a=Audit(c,d['source_fingerprints']['constraints'])
 report['source_profile']={'constraints_sha256':d['source_fingerprints']['constraints'],'constraint_count':len(a.catalog)}
 g=Geometry(d['layout'],c)
 if g.valid:
  structural(d,g,c);check_rectangle(d,g,c);interfaces_ok=check_interfaces(d,g,c)
  a=static_audit(d,g,c);rectangle_audit(d,g,a)
  report['geometry']={'occupied_cells':len(g.occ),'units':len(g.units),'channels':len(g.edges),'channel_graph_complete':not g.ambiguities,'transport_slots':len(g.slots),'empty_rectangle':g.rectangle,'powered':g.powered,'physical_channels_rebuilt':[{'from':unref(p),'to':unref(q)} for p,q in g.edges]}
  flow_ready=c.good('N5a','port-references','N4a','N4b','logical-feeds') and interfaces_ok
  if flow_ready and g.edges:
   lp=build(d,g);x=None
   if d['flow_witness'] is not None:
    try:
     x=vector_from_witness(d['flow_witness'],lp,d);bad=lp.exact(x,positive=True)
    except ValueError as e: bad=[str(e)]
    if bad: report['flow']={'status':'INVALID_WITNESS','violations':bad};x=None
    else: report['flow']={'status':'FEASIBLE_EXACT','source':'supplied witness','exact_rows':len(lp.rows),'delta':str(x[lp.index[('delta',)]])}
   else: report['flow'],x=lp.solve(time_limit)
   fs=report['flow']['status'];positive=x is not None
   if positive:
    report['flow_witness']=witness(lp,x,d);report['flow_summary']=flow_audit(d,g,lp,x,a)
   if fs=='NUMERICAL_UNRESOLVED': c.note('N5b','NUMERICAL_UNRESOLVED','格式 §9.2 N5b',report['flow'])
   else: c.add('N5b',positive,'格式 §9.2 N5b；规则·配方/滞留/传输；约束·物料流量',report['flow'])
   if d['design']['class']=='p2p':
    c.add('P3',positive,'共识 §1.3 P3；格式 §8.2 N5b')
    if positive:
     c.add('P2-rate',all(len({sum(x[j] for (i,it),j in lp.f.items() if i==ii) for ii in path})==1 for path in g.paths),'共识 §1.3 P2；格式 §8.4/9（同路径同速率）')
     c.add('P2',c.good('P2-paths','P2-rate'),'共识 §1.3 P2；格式 §8.2/8.4','单物品端到端路径及精确沿程流率联合核验')
     c.add('P4',c.good('P4'),'共识 §1.3 P4；格式 §8.2','桥使用轴两端结构完整且全部通道正流；不用轴无相向邻端口')
    else:
     c.note('P2','BLOCKED','共识 §1.3 P2；格式 §8.2','路径结构已单列；未取得精确正流，沿程流率未认证')
   a.test('存货误料停机与可用台数',c.good('wrong-material','outside-recipe'),'真实结构种类最小不动点核验',remaining='静态保守风险排除，不等于所有运行初态无误料。')
  else:
   c.note('N5b','BLOCKED','格式 §9 N5b','完整结构、接口或非空支持闸门未成立，不能核流。')
   if d['design']['class']=='p2p':
    c.note('P3','BLOCKED','格式 §8.2 P3','N5b 未核');c.note('P2','BLOCKED','格式 §8.2 P2','尚未核精确正流及沿程流率')
  report['coverage']={'fixed':['候选文件字节中的全部几何、设定、配方集、结构支持、allowed_items']+(['logical_feeds 的端点、路径和精确速率'] if 'logical_feeds' in d['design'] else []),'open':['未固定的连续分物品流与配方批率（附见证时核该见证）'],'quantifier':'一张固定布局的静态必要条件及指定受限类；存在一份严格正支持的连续平均流','excluded_from_scope':['运行初态','玩家调试办法','合法接通/判定次序','箱体传输相位','全部可达循环态'],'failure_scope':'仅本候选及记录的支持/限制；不排除其他几何或设定，不降低 U、不提高 L。','restrictions':d['design']['restrictions']}
 else: c.note('geometry-dependent-checks','BLOCKED','格式 §10','实体尺寸/占格无效，端口、LP 及依赖项未执行。')
 report['constraints']=a.finish()
 static_blockers=any(r['status'] in ['UNIMPLEMENTED','BLOCKED','NUMERICAL_UNRESOLVED'] for r in c.records)
 failed=any(r['status']=='FAIL' for r in c.records)
 # Formal runtime obligations are expected; missing static execution is a blocker.
 formal_blockers=any(p['status']=='BLOCKED' for r in report['constraints'] for p in r['checks'])
 report['status']='REJECTED' if failed else 'UNRESOLVED' if static_blockers or formal_blockers else 'STATIC_PASS'
 report['summary']={'checks':len(c.records),'failed':sum(r['status']=='FAIL' for r in c.records),'formal_constraints':len(report['constraints']),'formal_blocked':sum(any(p['status']=='BLOCKED' for p in r['checks']) for r in report['constraints']),'runtime_obligations':sum(any(p['status']=='RUNTIME_PENDING' for p in r['checks']) for r in report['constraints'])}
 return report

def safe_write(path,data):
 path=Path(path).resolve()
 if not path.is_relative_to(WRITE_ROOT): raise ValueError('输出仅允许位于 '+str(WRITE_ROOT))
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('candidate');ap.add_argument('--output');ap.add_argument('--witness-output');ap.add_argument('--time-limit',type=float,default=120)
 args=ap.parse_args()
 if not math.isfinite(args.time_limit) or args.time_limit<=0: ap.error('--time-limit 必须为有限正秒数')
 start=time.monotonic()
 try:
  raw=Path(args.candidate).read_bytes();d=loads(raw);r=check_document(d,time_limit=args.time_limit)
 except (OSError,Invalid) as e:
  raw=locals().get('raw',b'');r={'status':'INVALID_INPUT','error':str(e),'runtime_certified':False,'updates_L':False,'constraints':Audit(Checks()).finish(),
   'coverage':{'fixed':['指定输入文件字节；无法读取时无可核候选'], 'open':[],
               'quantifier':'文件可读性与严格 JSON 解析',
               'excluded_from_scope':['结构','平均流','运行初态','调试','全部合法先后'],
               'failure_scope':'仅本输入无法读取或解析；不作几何可行性与上下界判断。'}}
 r.update(checker=VERSION,candidate_sha256=hashlib.sha256(raw).hexdigest(),candidate_hash_basis='exact input file bytes',checker_files_sha256=code_fingerprint(),supported_source_fingerprints=HASHES,supported_constraint_profiles=CONSTRAINT_PROFILES,elapsed_seconds=round(time.monotonic()-start,6))
 if args.output: safe_write(args.output,r)
 else: print(json.dumps(r,ensure_ascii=False,indent=2))
 if args.witness_output and 'flow_witness' in r: safe_write(args.witness_output,r['flow_witness'])
 return 0 if r['status']=='STATIC_PASS' else 1 if r['status']=='REJECTED' else 2
if __name__=='__main__': raise SystemExit(main())
