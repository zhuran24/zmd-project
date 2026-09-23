"""设计路径、逻辑来源及候选B固定内容核对；格式§8.3/8.4。"""
import json,hashlib
from collections import Counter,defaultdict
from fractions import Fraction as Q
from catalog import *
from geometry import pref

def check_design(g,r):
 d=g.d;de=d['design'];reg={x['id']:x for x in de['restrictions']};mandatory=NIDS+(PIDS if de['class']=='p2p'else[])
 r.check('restrictions',set(mandatory)<=set(reg),'格式§8.3；冻结共识§1.3',{'missing':sorted(set(mandatory)-set(reg))})
 # Free prose is not executable. Only explicitly implemented restriction names have semantics.
 known=set(NIDS+PIDS+['single-recipe','fixed-layout','fixed-recipes','fixed-logical-feeds','candidate-b','recipe-subsets'])
 for rid in sorted(set(reg)-known):r.unresolved('restriction:'+rid,'格式§8.3','额外限制为自由文本，未实现可执行解释；不静默放行')
 if 'recipe-subsets' in reg:r.check('recipe-subsets',reg['recipe-subsets']['statement']=='recipe_ids 限定本候选的配方集合；不把它当成游戏开关。','格式§5.1/8.3',{'definition':'固定JSON内的配方子集，仍需实际来料检查'})
 if 'single-recipe'in reg:r.check('single-recipe',all(len(u['recipe_ids'])==1 for u in g.lay['machines']),'格式§5.1/8.3',{'definition':'全部机器恰一配方'})
 # Register actual recipe subsets; a naturally single-recipe model adds no restriction.
 single_other=[u['id']for u in g.lay['machines']if not(de['class']=='p2p' and u['model']in('粉碎机','采种机')) and set(u['recipe_ids'])!={rid for rid,v in RECIPES.items()if v[0]==u['model']}]
 registered=bool(set(reg)&{'single-recipe','fixed-recipes','candidate-b','recipe-subsets'})
 if single_other and not registered and set(reg)-known:
  r.unresolved('recipe_restriction_registration','格式§8.2 P6/8.3',{'recipe_subset_machines':single_other,'detail':'存在额外登记但其可执行语义未实现；不能断言未登记，也不能认证已满足'})
 else:r.check('recipe_restriction_registration',not single_other or registered,'格式§8.2 P6 后段',{'recipe_subset_machines':single_other})
 for name in ['fixed-layout','fixed-recipes']:
  if name in reg:r.check(name,True,'格式§8.3',{'definition':'固定本候选字节中的全部单位占格/朝向/设置'if name=='fixed-layout'else'固定本候选字节中的全部 recipe_ids 集合'})
 bindings=de.get('source_bindings',[]);mapped={x['logical_source_id']:pref(x['port'])for x in bindings}
 for x in bindings:r.check('source_binding',pref(x['port'])in g.sources,'格式§8.4',x)
 if 'logical_feeds'in de:
  r.check('logical_rate_registration',bool(set(reg)&{'fixed-logical-feeds','candidate-b'}),'格式§8.3/8.4',{'definition':'附带逻辑路径速率全部作为精确等式'})
  byid={c['id']:(i,e)for i,(c,e)in enumerate(zip(g.cd,g.channels))if c};usage=[]
  for feed in de['logical_feeds']:
   valid=all(cid in byid for cid in feed['path']);r.check('logical_path',valid,'格式§8.4',{'feed':feed['id'],'unknown':[cid for cid in feed['path']if cid not in byid]})
   if not valid:continue
   es=[byid[cid][1]for cid in feed['path']];usage+=feed['path'];ok=pref(feed['from'])==es[0][0]and pref(feed['to'])==es[-1][1]and not g.is_t(es[0][0][0])and not g.is_t(es[-1][1][0])
   ok &= all(g.is_t(a[1][0])and g.slot(a[1])==g.slot(b[0])for a,b in zip(es,es[1:]))
   ok &= all(g.cd[byid[cid][0]]['allowed_items']==[feed['item']]for cid in feed['path'])
   r.check('logical_path',ok,'格式§8.4；共识 P2',{'feed':feed['id'],'path':feed['path']})
  r.check('logical_path_coverage',Counter(usage)==Counter(c['id']for c in g.cd if c),'格式§8.4',{'repeated':{k:v for k,v in Counter(usage).items()if v!=1},'uncovered':sorted({c['id']for c in g.cd if c}-set(usage))})
 bpath='求解器/数据/候选B/contract.json';isB='candidate-b'in reg
 if not isB:return
 raw=(ROOT/bpath).read_bytes();old=json.loads(raw);finger=hashlib.sha256(raw).hexdigest()
 r.check('B_provenance',any(p['path']==bpath and p['sha256']==finger for p in d.get('provenance',[])),'格式§8.4',{'contract_sha256':finger})
 r.check('B_sources',set(mapped)=={s['id']for s in old['sources']}and set(mapped.values())==set(g.sources),'格式§8.4',{'bindings':len(mapped),'physical_sources':len(g.sources)})
 for s in old['sources']:r.check('B_source_item',mapped.get(s['id'])in g.sources and g.sources.get(mapped.get(s['id']))==s['item'],'格式§8.4',{'logical_source':s['id']})
 machines={u['id']:u for u in g.lay['machines']};oldm={u['id']:u for u in old['machines']}
 r.check('B_machines',set(machines)==set(oldm),'格式§8.4',{'count':len(machines)})
 for uid,u in oldm.items():r.check('B_machine_recipe',uid in machines and machines[uid]['model']==u['kind']and set(machines[uid]['recipe_ids'])=={x['recipe']for x in u['recipes']},'格式§8.4',{'machine':uid})
 newf={v['id']:v for v in de.get('logical_feeds',[])};oldf={v['id']:v for v in old['logical_feeds']};logical_ports={};physical_ports={}
 r.check('B_feeds',set(newf)==set(oldf),'格式§8.4',{'count':len(newf)})
 for fid,v in oldf.items():
  if fid not in newf:continue
  cur=newf[fid];src=pref(cur['from']);dst=pref(cur['to']);expected_src=mapped.get(v['source'])if v['source']in mapped else None
  ok=(src==expected_src if expected_src else src[0]==v['source'])and dst[0]==v['target']and cur['item']==v['item']and Q(cur['rate'])==Q(v['planned_rate']['value'])
  r.check('B_feed_fixed',ok,'格式§8.4',{'feed':fid})
  for lp,pp in [(v['source_port'],src),(v['target_port'],dst)]:
   r.check('B_port_injection',(lp not in logical_ports or logical_ports[lp]==pp)and(pp not in physical_ports or physical_ports[pp]==lp),'格式§8.4；逻辑端口名不等于物理 offset',{'logical':lp,'physical':pp})
   logical_ports[lp]=pp;physical_ports[pp]=lp
