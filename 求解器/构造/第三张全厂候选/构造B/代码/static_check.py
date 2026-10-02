#!/usr/bin/env python3
"""Independent cell/port reconstruction for this S2 candidate; never a dynamic certificate."""
import sys,json,hashlib
from pathlib import Path
from collections import Counter,defaultdict
from fractions import Fraction as F
BASE=Path(__file__).resolve().parents[1]
D=((1,0),(0,1),(-1,0),(0,-1))
REC={
 '粉碎-源矿':({'源矿':1},{'源石粉末':1},1),
 '粉碎-蓝铁块':({'蓝铁块':1},{'蓝铁粉末':1},1),
 '粉碎-砂叶':({'砂叶':1},{'砂叶粉末':3},1),
 '粉碎-荞花':({'荞花':1},{'荞花粉末':2},1),
 '精炼-蓝铁矿':({'蓝铁矿':1},{'蓝铁块':1},1),
 '精炼-致密蓝铁':({'致密蓝铁粉末':1},{'钢块':1},1),
 '研磨-致密蓝铁':({'蓝铁粉末':2,'砂叶粉末':1},{'致密蓝铁粉末':1},1),
 '研磨-致密源石':({'源石粉末':2,'砂叶粉末':1},{'致密源石粉末':1},1),
 '研磨-细磨荞花':({'荞花粉末':2,'砂叶粉末':1},{'细磨荞花粉末':1},1),
 '配件-钢制零件':({'钢块':1},{'钢制零件':1},1),
 '塑形-钢质瓶':({'钢块':2},{'钢质瓶':1},1),
 '种植-砂叶':({'砂叶种子':1},{'砂叶':1},1),
 '种植-荞花':({'荞花种子':1},{'荞花':1},1),
 '采种-砂叶':({'砂叶':1},{'砂叶种子':2},1),
 '采种-荞花':({'荞花':1},{'荞花种子':2},1),
 '封装-电池':({'钢制零件':10,'致密源石粉末':15},{'高容谷地电池':1},5),
 '灌装-胶囊':({'钢质瓶':10,'细磨荞花粉末':10},{'精选荞愈胶囊':1},5)}

def expected_edges():
 e=[]
 def add(s,t,it,q=1):e.append((s,t,it,str(F(q))))
 for k in range(1,35):
  add('OB'+str(k),'T'+str(k),'蓝铁矿');add('T'+str(k),'KB'+str(k),'蓝铁块');add('KB'+str(k),'B'+str((k+1)//2),'蓝铁粉末')
 for k in range(1,19):
  add('CORE' if k<7 else 'OO'+str(k),'U'+str(k),'源矿');add('U'+str(k),'O'+str((k+1)//2),'源石粉末')
 for k in range(1,18):
  add('B'+str(k),'R'+str(k),'致密蓝铁粉末');add('R'+str(k),'P'+str(k) if k<7 else 'H'+str((k-7)//2+1),'钢块')
 for k in range(1,10):add('O'+str(k),'E'+str((k-1)//3+1),'致密源石粉末')
 for k in range(1,7):
  add('P'+str(k),'E'+str((k-1)//2+1),'钢制零件')
  target='F'+str((k+1)//2 if k<5 else k-2)
  add('H'+str(k),target,'钢质瓶',F(1,2) if k==6 else 1);add('Q'+str(k),target,'细磨荞花粉末',F(1,2) if k==6 else 1)
 for k in range(1,4):add('E'+str(k),'CORE','高容谷地电池',F(1,5))
 for k,q in zip(range(1,5),[F(1,5),F(1,5),F(1,10),F(1,20)]):add('F'+str(k),'CORE','精选荞愈胶囊',q)
 groups=['B1 B2 O1','O2 O3','B3 B4 O4','O5 O6','B5 B6 O7','O8 O9','B7 B8 B9','B10 Q1 Q2','B11 B12 B13','B14 Q3 Q4','B15 B16 Q5','B17','Q6']
 for p,n in [('S',13),('Q',6)]:
  for k in range(1,n+1):
   item='砂叶' if p=='S' else '荞花';cr=p+str(k) if p=='S' else 'KQ'+str(k)
   targets=groups[k-1].split() if p=='S' else ['Q'+str(k)]*(1 if k==6 else 2)
   rate=sum(F(1,2) if t=='Q6' and p=='S' else F(1) for t in targets)/(3 if p=='S' else 2)
   add(p+'C'+str(k),p+'A'+str(k),item+'种子',rate);add(p+'C'+str(k),p+'B'+str(k),item+'种子',rate)
   add(p+'A'+str(k),p+'C'+str(k),item,rate);add(p+'B'+str(k),cr,item,rate)
   for t in targets:add(cr,t,item+'粉末',F(1,2) if p=='S' and t=='Q6' else 1)
 return e

def occupied_cells(u):
 if 'x' in u:return [(u['x'],u['y'])]
 return [(x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)]

def largest_rect(occ):
 # Histogram algorithm, independent of the brute-force column-interval checker.
 best=(0,0);out=None;heights=[0]*70
 for y in range(70):
  for x in range(70):heights[x]=0 if (x,y) in occ else heights[x]+1
  st=[]
  for x in range(71):
   h=heights[x] if x<70 else 0;start=x
   while st and st[-1][1]>h:
    a,hh=st.pop();w=x-a;start=a
    if w>=6 and hh>=6 and (w*hh,min(w,hh))>best:best=(w*hh,min(w,hh));out=dict(x0=a,y0=y-hh+1,x1=x-1,y1=y)
   if not st or st[-1][1]<h:st.append((start,h))
 return dict(area=best[0],short_side=best[1],rectangle=out)

def run(data,contract):
 l=data['layout'];checks=[];diagnostics={}
 def ck(name,ok,detail=None):checks.append(dict(name=name,pass_=bool(ok),detail=detail))
 ck('70x70',l['W']==l['H']==70)
 entities=[]
 for group in ['machines','warehouse_outlets','power_poles','storage_boxes','transport']:
  entities.extend((u,group) for u in l[group])
 entities.append((l['core'],'core'))
 ids=[u['id'] for u,g in entities];ck('unique_unit_ids',len(set(ids))==len(ids))
 units={u['id']:u for u,g in entities};kind={u['id']:g for u,g in entities};occ={};over=[];out=[]
 for u,g in entities:
  for xy in occupied_cells(u):
   if xy in occ:over.append([xy,occ[xy],u['id']])
   occ[xy]=u['id']
   if not all(isinstance(a,int) and 0<=a<70 for a in xy):out.append([u['id'],xy])
 ck('no_overlap',not over,over);ck('inside_base',not out,out)
 models=Counter(m['model'] for m in l['machines'])
 ck('230_machines',models==Counter({'粉碎机':71,'精炼炉':51,'研磨机':32,'种植机':38,'采种机':19,'配件机':6,'塑形机':6,'封装机':3,'灌装机':4}),dict(models))
 em={m['id']:m for m in contract['machines']};actual_m={m['id']:m for m in l['machines']}
 ck('machine_identity',set(em)==set(actual_m))
 shape=[];recipes=[]
 for u in l['machines']:
  sz=(3,3) if u['model'] in ['粉碎机','精炼炉','配件机','塑形机'] else (5,5) if u['model'] in ['种植机','采种机'] else (4,6) if u['Din']%2==0 else (6,4)
  if (u['x1']-u['x0']+1,u['y1']-u['y0']+1)!=sz:shape.append(u['id'])
  if u['id'] not in em or u['model']!=em[u['id']]['model'] or u['recipe_ids']!=[em[u['id']]['recipe_id']] or not u['settings']['manufacture_on']:recipes.append(u['id'])
 ck('machine_shapes_rotations',not shape,shape);ck('recipes_and_switches',not recipes,recipes)
 ck('forbidden_units_absent',not l['storage_boxes'] and not l['vin'] and not l['vout'] and all(t['type'] in ['belt','bridge'] for t in l['transport']))
 outletbad=[]
 for u in l['warehouse_outlets']:
  valid=(u['Dout']==0 and u['x0']==u['x1']==0 and u['y1']-u['y0']==2) or (u['Dout']==1 and u['y0']==u['y1']==0 and u['x1']-u['x0']==2)
  if not valid:outletbad.append(u['id'])
 ck('46_boundary_outlets',len(l['warehouse_outlets'])==46 and not outletbad,outletbad)
 ck('23_outlets_each_side',Counter(u['Dout'] for u in l['warehouse_outlets'])=={0:23,1:23})
 co=l['core'];ck('one_9x9_core',co['id']=='CORE' and co['x1']-co['x0']==co['y1']-co['y0']==8)
 cfg={(z['side'],z['offset']):z['item'] for z in co['output_items']}
 ck('core_6_ore_ports',len(co['output_items'])==6 and cfg=={(s,o):'源矿' for s in [(co['Din']+1)%4,(co['Din']+3)%4] for o in [1,4,7]})
 ck('ore_configurations',Counter([u['item'] for u in l['warehouse_outlets']]+list(cfg.values()))=={'蓝铁矿':34,'源矿':18})
 polebad=[];covered={}
 for p in l['power_poles']:
  if p['x1']-p['x0']!=1 or p['y1']-p['y0']!=1:polebad.append(p['id'])
 for u in l['machines']:
  covered[u['id']]=[p['id'] for p in l['power_poles'] if u['x0']<=p['x0']+6 and u['x1']>=p['x0']-5 and u['y0']<=p['y0']+6 and u['y1']>=p['y0']-5]
 ck('power_pole_shapes',not polebad,polebad);ck('all_machines_powered',all(covered.values()),[u for u,a in covered.items() if not a])
 # Physical ports are enumerated from rules, never from claimed channels.
 ports={};loc={}
 def port(u,d,o,mode):
  if 'x' in u:x,y=u['x'],u['y']
  elif d==0:x,y=u['x1'],u['y0']+o
  elif d==2:x,y=u['x0'],u['y0']+o
  elif d==1:x,y=u['x0']+o,u['y1']
  else:x,y=u['x0']+o,u['y0']
  r=(u['id'],d,o);ports[r]=((x,y),mode);loc[(x,y,d)]=r
 for u,g in entities:
  if g=='machines':
   for d,io in [(u['Din'],'in'),((u['Din']+2)%4,'out')]:
    n=u['y1']-u['y0']+1 if d%2==0 else u['x1']-u['x0']+1
    for o in range(n):port(u,d,o,io)
  elif g=='warehouse_outlets':port(u,u['Dout'],1,'out')
  elif g=='core':
   for d in [u['Din'],(u['Din']+2)%4]:
    for o in range(1,8):port(u,d,o,'in')
   for d,o in cfg:port(u,d,o,'out')
  elif g=='transport':
   if u['type']=='belt':
    ck('belt_distinct_sides.'+u['id'],u['in_side']!=u['out_side'])
    port(u,u['in_side'],0,'in');port(u,u['out_side'],0,'out')
   elif u['type']=='bridge':
    for d in range(4):port(u,d,0,'both')
 actual=set()
 for p,((x,y),io) in ports.items():
  if io not in ['out','both']:continue
  d=p[1];q=loc.get((x+D[d][0],y+D[d][1],(d+2)%4))
  if q and ports[q][1] in ['in','both'] and ('transport' in [kind[p[0]],kind[q[0]]]):actual.add((p,q))
 def ref(q):return(q['unit'],q['side'],q['offset'])
 claimed={(ref(e['from']),ref(e['to'])):e for e in data['design']['physical_channels']}
 ck('exact_automatic_channels',actual==set(claimed),dict(undeclared=list(actual-set(claimed)),nonexistent=list(set(claimed)-actual)))
 outs=defaultdict(list)
 for e in actual:outs[e[0]].append(e)
 used=set();found=[];route_errors=[]
 for lf in data['design'].get('logical_feeds',[]):
  ids_path=lf['path'];by_id={e['id']:e for e in data['design']['physical_channels']}
  seq=[]
  for cid in ids_path:
   if cid not in by_id:route_errors.append([lf['id'],'missing_channel',cid]);break
   e=by_id[cid];seq.append((ref(e['from']),ref(e['to'])))
  if not seq:continue
  cells=[];valid=seq[0][0]==ref(lf['from']) and seq[-1][1]==ref(lf['to']) and len(seq)>=2
  for i,(p,q) in enumerate(seq):
   valid &= (p,q) in actual and (p,q) not in used
   used.add((p,q))
   if i<len(seq)-1:
    r=seq[i+1][0];valid &= q[0]==r[0] and kind.get(q[0])=='transport'
    if q[0] in units:
     t=units[q[0]];cells.append((t.get('x'),t.get('y')))
     if t.get('type')=='bridge':valid &= r[1]==(q[1]+2)%4
     elif t.get('type')=='belt':valid &= q[1]==t['in_side'] and r[1]==t['out_side']
  valid &= len(cells)==len(set(cells))
  if not valid:route_errors.append([lf['id'],'non_path_or_shared_channel'])
  found.append((lf['from']['unit'],lf['to']['unit'],lf['item'],lf['rate']))
 ck('valid_nonrepeating_routes',not route_errors,route_errors)
 reverse_ids=set(data['design'].get('bridge_reverse_channels',[]))
 reverse_edges={(ref(e['from']),ref(e['to'])) for e in data['design']['physical_channels'] if e['id'] in reverse_ids}
 expected_reverse={(q,p) for p,q in used if units.get(p[0],{}).get('type')=='bridge' and units.get(q[0],{}).get('type')=='bridge'}
 ck('exact_bridge_reverse_channels',reverse_edges==expected_reverse and not reverse_edges&used,dict(declared=len(reverse_edges),expected=len(expected_reverse)))
 ck('all_channels_accounted_for',used|reverse_edges==actual,dict(unaccounted=list(actual-used-reverse_edges)))
 expected=Counter(expected_edges());in_contract=Counter((f['source'],f['target'],f['item'],f['rate']) for f in contract['feeds'])
 ck('independent_S2_contract',expected==in_contract and sum(expected.values())==325)
 missing=list((expected-Counter(found)).elements());extra=list((Counter(found)-expected).elements())
 ck('325_S2_routes',not missing and not extra,dict(missing=missing,extra=extra,completed=len(found)))
 paths=data['design'].get('logical_feeds',[]);lens={ (f['from']['unit'],f['to']['unit']):len(f['path'])-1 for f in paths}
 ck('H6_Q6_equal_lengths',('H6','F4') in lens and ('Q6','F4') in lens and lens['H6','F4']==lens['Q6','F4'],{str(k):v for k,v in lens.items() if k in [('H6','F4'),('Q6','F4')]})
 # Exact rational inventory balance for the actual declared routes.
 ins=defaultdict(Counter);outflow=defaultdict(Counter)
 for s,t,it,q in found:ins[t][it]+=F(q);outflow[s][it]+=F(q)
 unbalanced=[]
 for uid,m in em.items():
  a,b,tm=REC[m['recipe_id']];rate=F(m['batch_rate'])
  if ins[uid]!=Counter({it:rate*q for it,q in a.items()}) or outflow[uid]!=Counter({it:rate*q for it,q in b.items()}) or rate*tm>1:unbalanced.append(uid)
 ck('exact_average_machine_balance',not unbalanced,unbalanced)
 ck('exact_average_targets',ins['CORE']==Counter({'高容谷地电池':F(3,5),'精选荞愈胶囊':F(11,20)}),{k:str(v) for k,v in ins['CORE'].items()})
 bridges=[u for u in l['transport'] if u['type']=='bridge'];bridgeby={(u['x'],u['y']):u for u in bridges};adj=[];axes=[];axis_paths=defaultdict(list)
 for f in paths:
  for cid in f['path'][:-1]:
   e=next(e for e in data['design']['physical_channels'] if e['id']==cid);q=e['to'];u=units.get(q['unit'],{})
   if u.get('type')=='bridge':axis_paths[(u['id'],q['side']%2)].append(f['id'])
 for u in bridges:
  for d in [0,1]:
   v=bridgeby.get((u['x']+D[d][0],u['y']+D[d][1]))
   if v:adj.append([u['id'],v['id']])
  axes.append(dict(id=u['id'],x=u['x'],y=u['y'],H=axis_paths.get((u['id'],0),[]),V=axis_paths.get((u['id'],1),[])))
 ck('bridge_axes_separate_routes',all(len(a['H'])<=1 and len(a['V'])<=1 and not set(a['H'])&set(a['V']) for a in axes),axes)
 if data['schema']=='full-factory-static-v1':ck('v1_no_adjacent_bridges',not adj,adj)
 else:ck('s2b_extension_declared',data['schema']=='full-factory-static-s2b-v1' and data['design']['class']=='s2b_p2p',dict(adjacent_pairs=adj))
 axis_declarations=[]
 for u in bridges:
  want={0:None,1:None}
  for p,q in used:
   if q[0]==u['id']:want[q[1]%2]=q[1]
  if u['H_in']!=want[0] or u['V_in']!=want[1]:axis_declarations.append(u['id'])
 ck('bridge_axis_direction_declarations',not axis_declarations,axis_declarations)
 maximum=largest_rect(occ);r=data.get('empty_rectangle');area=0
 if r:
  cells=occupied_cells(r);area=len(cells);w=r['x1']-r['x0']+1;h=r['y1']-r['y0']+1
  valid=not any(xy in occ for xy in cells) and min(w,h)>=6 and (area,min(w,h))==(maximum['area'],maximum['short_side'])
 else:valid=False
 ck('maximum_empty_rectangle',valid,maximum)
 stats=dict(machines=len(l['machines']),machine_area=sum(len(occupied_cells(u)) for u in l['machines']),occupied_cells=len(occ),power_poles=len(l['power_poles']),transport=len(l['transport']),bridges=len(bridges),adjacent_bridge_pairs=len(adj),structural_channels=len(actual),reverse_bridge_channels=len(reverse_edges),completed_routes=len(found),missing_routes=len(missing),empty_rectangle=maximum)
 return dict(static_pass=all(c['pass_'] for c in checks),runtime_certified=False,stats=stats,checks=checks,bridge_structures=axes,power_coverage=covered)

if __name__=='__main__':
 path=Path(sys.argv[1]);data=json.loads(path.read_text());c=json.loads((BASE/'依据/S2接法.json').read_text())
 r=run(data,c);r['candidate_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();r['checker_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 out=Path(sys.argv[2]) if len(sys.argv)>2 else BASE/'静态检查结果.json';out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(static_pass=r['static_pass'],stats=r['stats'],failed_checks=[c['name'] for c in r['checks'] if not c['pass_']]),ensure_ascii=False))
