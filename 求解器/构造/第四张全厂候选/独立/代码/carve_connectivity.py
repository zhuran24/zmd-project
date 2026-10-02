#!/usr/bin/env python3
"""为缺路预留明确的逐格通道，局部重摆后拆线重布；每次尝试持久化。"""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import sys,json,time,subprocess,copy,hashlib
from pathlib import Path
from collections import Counter
from ortools.sat.python import cp_model
from export_layout import export
from check_static import run as audit
BASE=Path(__file__).resolve().parents[1];CODE=BASE/'代码';WORK=BASE/'迭代'/(sys.argv[4] if len(sys.argv)>4 else '廊道搜索');WORK.mkdir(exist_ok=True)
contract=json.loads((BASE/'逻辑接法.json').read_text())
def freeze(d,p):
 p.with_suffix('.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 p.with_suffix('.pos').write_text(''.join(f'{u["x"]} {u["y"]} {u["d"]}\n' for u in d['units']))
 ps={p['r']:p for p in d['paths']}
 with p.with_suffix('.routes').open('w') as f:
  print(325,file=f)
  for r in range(325):
   q=ps.get(r,dict(cells=[],source=[0]*4,target=[0]*4));print(len(q['cells']),*q['source'],*q['target'],file=f)
   for z in q['cells']:print(*z,file=f)
def footprint(u):return {(x,y) for x in range(u['x'],u['x']+u['w']) for y in range(u['y'],u['y']+u['h'])}
def mask(z):return 1<<(z[2]%2) if z[3]==(z[2]+2)%4 else 3

def carve(raw,cut,radius,seconds,prefix,seed):
 m=cp_model.CpModel();u=raw['units'];n=len(u);xs=[];ys=[];ix=[];iy=[];cost=[];moves=[];movable=[];degrees=Counter()
 for p in raw['paths']:
  if p['cells']:
   f=contract['feeds'][p['r']];degrees[f['source']]+=1;degrees[f['target']]+=1
 f=contract['feeds'][cut['r']];ends={f['source'],f['target']}
 cx=[z[0] for z in cut['cells']];cy=[z[1] for z in cut['cells']];window=(max(1,min(cx)-radius-5),max(1,min(cy)-radius-5),min(69,max(cx)+radius+5),min(69,max(cy)+radius+5))
 poles=[z for z in u if z['type']==5]
 for k,a in enumerate(u):
  can=a['type']<3 and a['id'] not in ends and a['x']<=window[2] and a['x']+a['w']>window[0] and a['y']<=window[3] and a['y']+a['h']>window[1]
  lx=max(1,a['x']-radius) if can else a['x'];hx=min(70-a['w'],a['x']+radius) if can else a['x'];ly=max(1,a['y']-radius) if can else a['y'];hy=min(70-a['h'],a['y']+radius) if can else a['y']
  x=m.NewIntVar(lx,hx,f'x{k}');y=m.NewIntVar(ly,hy,f'y{k}');xs.append(x);ys.append(y);ix.append(m.NewFixedSizeIntervalVar(x,a['w'],f'ix{k}'));iy.append(m.NewFixedSizeIntervalVar(y,a['h'],f'iy{k}'))
  if can:
   movable.append(k);ch=m.NewBoolVar(f'move{k}');m.Add(x==a['x']).OnlyEnforceIf(ch.Not());m.Add(y==a['y']).OnlyEnforceIf(ch.Not());moves.append(ch)
   dx=m.NewIntVar(0,70,f'dx{k}');dy=m.NewIntVar(0,70,f'dy{k}');m.AddAbsEquality(dx,x-a['x']);m.AddAbsEquality(dy,y-a['y']);cost.extend([20*(1+degrees[a['id']])*ch,dx,dy])
   covers=[]
   for pi,po in enumerate(poles):
    if lx>po['x']+6 or hx+a['w']-1<po['x']-5 or ly>po['y']+6 or hy+a['h']-1<po['y']-5:continue
    cc=m.NewBoolVar(f'cov{k}_{pi}');covers.append(cc)
    m.Add(x<=po['x']+6).OnlyEnforceIf(cc);m.Add(x+a['w']-1>=po['x']-5).OnlyEnforceIf(cc);m.Add(y<=po['y']+6).OnlyEnforceIf(cc);m.Add(y+a['h']-1>=po['y']-5).OnlyEnforceIf(cc)
   m.AddBoolOr(covers)
  m.AddHint(x,a['x']);m.AddHint(y,a['y'])
 ix.append(m.NewFixedSizeIntervalVar(64,6,'emptyx'));iy.append(m.NewFixedSizeIntervalVar(64,6,'emptyy'))
 for j,(x,y,_,_) in enumerate(cut['cells']):ix.append(m.NewFixedSizeIntervalVar(x,1,f'cx{j}'));iy.append(m.NewFixedSizeIntervalVar(y,1,f'cy{j}'))
 m.AddNoOverlap2D(ix,iy);m.Minimize(sum(cost));solver=cp_model.CpSolver();solver.parameters.num_search_workers=1;solver.parameters.max_time_in_seconds=seconds;solver.parameters.random_seed=seed
 solver.parameters.log_search_progress=False
 class Save(cp_model.CpSolverSolutionCallback):
  def __init__(self):super().__init__();self.pose=None;self.obj=None;self.count=0
  def on_solution_callback(self):
   self.pose=[(self.Value(x),self.Value(y)) for x,y in zip(xs,ys)];self.obj=self.ObjectiveValue();self.count+=1
   prefix.with_suffix('.positions.json').write_text(json.dumps({'positions':self.pose,'objective':self.obj,'solution':self.count},ensure_ascii=False))
 cb=Save();start=time.monotonic();status=solver.Solve(m,cb)
 result={'status':solver.StatusName(status),'wall_seconds':time.monotonic()-start,'radius':radius,'movable':len(movable),'solutions':cb.count,'objective':cb.obj,'route':cut['r'],'window':window}
 prefix.with_suffix('.cp.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 if cb.pose is None:return None,result
 d=copy.deepcopy(raw);moved=set()
 for a,(x,y) in zip(d['units'],cb.pose):
  if (a['x'],a['y'])!=(x,y):moved.add(a['id'])
  a['x'],a['y']=x,y
 body=set().union(*(footprint(a) for a in d['units']));kept={}
 desired={(x,y):mask(z) for z in cut['cells'] for x,y in [z[:2]]}
 for p in d['paths']:
  f=contract['feeds'][p['r']]
  invalid=f['source'] in moved or f['target'] in moved or any((z[0],z[1]) in body or desired.get((z[0],z[1]),0)&mask(z) for z in p['cells'])
  kept[p['r']]=dict(p,cells=[] if invalid else p['cells'])
 kept[cut['r']]={k:cut[k] for k in ['r','source','target','cells']};d['paths']=[kept[r] for r in range(325)];d['overlap']=0;d['carve']={'cut':cut,'moved':sorted(moved),'cp':result}
 freeze(d,prefix);return d,result

def verified(raw,prefix):
 layout=export(raw);r=audit(layout);allowed={'325条指定进路齐全','H6和Q6到F4等长','精确平均物料守恒','两种成品设计交付率'}
 bad=[c['name'] for c in r['checks'] if not c['pass'] and c['name'] not in allowed]
 prefix.with_suffix('.layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2)+'\n');prefix.with_suffix('.check.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 st=r['stats'];merit=100*st['completed_routes']-35*st['fixed_geometry_obstructed']+50*st['product_routes']+10*st['ore_routes']
 return merit,r,bad

if __name__=='__main__':
 raw=json.loads(Path(sys.argv[1]).read_text());budget=float(sys.argv[2]);end=time.monotonic()+budget;seed=int(sys.argv[3]) if len(sys.argv)>3 else 901;current=WORK/'current';freeze(raw,current);score,check,bad=verified(raw,WORK/'start');assert not bad,bad
 log=(WORK/'记录.jsonl').open('a',buffering=1);roundno=0;attempt=0
 while time.monotonic()<end-20:
  baseline=WORK/f'基线{roundno:03d}';freeze(raw,baseline);cutfile=WORK/f'corridors-{roundno:03d}.json'
  subprocess.run([str(CODE/'make_disconnected_corridors'),str(BASE/'输入.txt'),str(current.with_suffix('.pos')),str(current.with_suffix('.routes')),str(seed+roundno),str(cutfile)],check=True)
  cuts=json.loads(cutfile.read_text());accepted=False
  for ci,cut in enumerate(cuts):
   if time.monotonic()>end-20:break
   attempt+=1;pre=WORK/f'尝试{attempt:04d}';pre.with_suffix('.input.json').write_text(json.dumps({'cut':cut,'baseline':str(baseline),'baseline_merit':score,'baseline_sha256':hashlib.sha256(current.with_suffix('.json').read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
   d,cp=carve(raw,cut,3+(attempt%3),min(12,end-time.monotonic()-6),pre,seed+attempt)
   rec={'attempt':attempt,'round':roundno,'cut':ci,'cp':cp,'accepted':False}
   if d is not None:
    out=WORK/f'重布{attempt:04d}'
    with out.with_suffix('.log').open('w') as f:
     subprocess.run([str(CODE/'search_incremental_locked'),str(BASE/'输入.txt'),str(seed+attempt),str(out),'3',str(pre.with_suffix('.pos')),'covered',str(pre.with_suffix('.routes')),str(cut['r'])],stdout=f,stderr=f,check=True,timeout=20)
    d=json.loads(Path(str(out)+'-final.json').read_text());val,ck,bad=verified(d,pre);rec.update(merit=val,stats=ck['stats'],errors=bad)
    if not bad and val>score+.01:
     raw=d;score=val;freeze(raw,current);freeze(raw,WORK/f'接受{attempt:04d}');accepted=True;rec['accepted']=True
   log.write(json.dumps(rec,ensure_ascii=False)+'\n');print(json.dumps({'attempt':attempt,'cp':cp['status'],'accepted':rec['accepted'],'stats':rec.get('stats')},ensure_ascii=False),flush=True)
   if accepted:break
  roundno+=1
  if not cuts:break
 freeze(raw,WORK/'final');print('finished',attempt,'attempts',score,flush=True)
