"""设计限制与候选 B 接口绑定；只读规范数据，不导入其他实现。"""
import hashlib, json
from collections import defaultdict
from catalog import *

EXTRA = {
 'recipe-subsets':'recipe_ids 限定本候选的配方集合；不把它当成游戏开关。',
 'fixed-layout':'本候选文件固定全部单位的位置、朝向与设定。',
 'fixed-channel-items':'physical_channels.allowed_items 固定设计物品支持。',
 'fixed-logical-feeds':'logical_feeds 固定端点、路径、物品与精确速率。',
 'candidate-b-preserved':'逐项保持候选 B 的机器、52 个来源与 315 条逻辑送料。',
}
def check_interfaces(d,g,c):
 z=d['design'];rs={r['id']:r for r in z['restrictions']};required=set(N_IDS + (P_IDS if z['class']=='p2p' else []))
 c.add('restrictions-required',required<=rs.keys(),'共识 §1.3；格式 §8.2/8.3',{'missing':sorted(required-rs.keys())})
 for k in sorted(rs.keys()-required):
  if k not in EXTRA: c.note('restriction:'+k,'UNIMPLEMENTED','格式 §8.3','未实现该额外限制的可执行解释；不能宣称覆盖。')
  else: c.add('restriction:'+k,rs[k]['statement']==EXTRA[k],'格式 §8.3；检查器B 说明·支持的额外限制',{'expected_statement':EXTRA[k]})
 extra_recipe=[]
 for u in g.l['machines']:
  if z['class']=='p2p' and u['model'] in ['粉碎机','采种机']: continue
  if set(u['recipe_ids'])!={r for r,x in RECIPES.items() if x[0]==u['model']}: extra_recipe.append(u['id'])
 c.add('recipe-restriction-register',not extra_recipe or 'recipe-subsets' in rs,'格式 §5.1/8.2 P6/8.3',extra_recipe)
 if 'logical_feeds' in z: c.add('logical-restriction-register','fixed-logical-feeds' in rs,'格式 §8.4（固定路径与数值速率须登记）')
 bindings=z.get('source_bindings',[])
 c.add('source-bindings',all(ref(b['port']) in g.source_items for b in bindings),'格式 §8.4 真实矿石物理身份')
 if 'logical_feeds' in z:
  channels={e['id']:e for e in z['physical_channels']};used=[];issues=[]
  for f in z['logical_feeds']:
   if any(e not in channels for e in f['path']): issues.append([f['id'],'missing channel']);continue
   path=[channels[e] for e in f['path']];used+=f['path']
   if path[0]['from']!=f['from'] or path[-1]['to']!=f['to']: issues.append([f['id'],'endpoint mismatch'])
   if ref(f['from']) not in g.ports or ref(f['to']) not in g.ports or g.transport(f['from']['unit']) or g.transport(f['to']['unit']): issues.append([f['id'],'endpoint must be nontransport'])
   if any(e['allowed_items']!=[f['item']] for e in path): issues.append([f['id'],'item mismatch'])
   for a,b in zip(path,path[1:]):
    p,q=ref(a['to']),ref(b['from'])
    if p not in g.ports or q not in g.ports or not g.transport(p[0]) or not g.transport(q[0]) or g.slot(p)!=g.slot(q): issues.append([f['id'],'broken transport slot or bridge axis'])
  if len(used)!=len(set(used)) or set(used)!=set(channels): issues.append(['coverage','each channel exactly once'])
  c.add('logical-feeds',not issues,'格式 §8.4；规则·桥接器/通道',issues)
 bpath='求解器/数据/候选B/contract.json'
 provenance=[v for v in d.get('provenance',[]) if v['path']==bpath]
 preserving='candidate-b-preserved' in rs
 if preserving:
  b=json.loads((ROOT/bpath).read_text());ok=bool(provenance) and provenance[0]['sha256']==hashlib.sha256((ROOT/bpath).read_bytes()).hexdigest()
  bm={u['id']:u for u in b['machines']};m={u['id']:u for u in g.l['machines']}
  ok &= set(bm)==set(m)
  for uid,u in m.items():
   if uid not in bm: continue
   ok &= u['model']==bm[uid]['kind'] and set(u['recipe_ids'])=={r['recipe'] for r in bm[uid]['recipes']}
  bindings={v['logical_source_id']:ref(v['port']) for v in bindings};bs={s['id']:s['item'] for s in b['sources']}
  ok &= set(bindings)==set(bs) and set(bindings.values())==set(g.source_items)
  for uid,p in bindings.items(): ok &= p in g.source_items and uid in bs and g.source_items.get(p)==bs.get(uid)
  fs={v['id']:v for v in z.get('logical_feeds',[])};bf={v['id']:v for v in b['logical_feeds']};ok &= fs.keys()==bf.keys()
  port_mapping=defaultdict(set)
  for fid,f in fs.items():
   if fid not in bf: continue
   old=bf[fid];ok &= f['item']==old['item'] and F(f['rate'])==F(old['planned_rate']['value'])
   a=ref(f['from']);q=ref(f['to'])
   ok &= (a==bindings.get(old['source']) if old['source'] in bs else a[0]==old['source']) and q[0]==old['target']
   port_mapping[old['source_port']].add(a);port_mapping[old['target_port']].add(q)
  ok &= all(len(ps)==1 for ps in port_mapping.values()) and len(set(next(iter(ps)) for ps in port_mapping.values()))==len(port_mapping)
  c.add('candidate-b-preserved',ok,'格式 §8.4；候选B/contract.json 逐项固定接口',{'machines':len(m),'sources':len(bindings),'feeds':len(fs)})
 elif provenance:
  c.note('candidate-b-provenance','INFO','格式 §8.3/8.4','记录了 B 来源但未声明逐项保持；仅检查当前完整候选，不认证历史固定指派。')
 return c.good('logical-feeds','source-bindings')
