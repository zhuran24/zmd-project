import os,json,time,sys,math
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
from ortools.sat.python import cp_model
BASE=Path(__file__).resolve().parents[1]; ROOT=BASE.parents[3]
B=json.loads((ROOT/'求解器/数据/候选B/contract.json').read_text())
model=cp_model.CpModel(); xs=[];ys=[]; rows=[]; allv=[]
# Half-cell enlargement only on the two full machine port sides: physical cells outside all ports remain free.
kind={'粉碎机':'小','精炼炉':'小','配件机':'小','塑形机':'小','种植机':'中','采种机':'中','研磨机':'大','封装机':'大','灌装机':'大'}
for mc in B['machines']:
 k=kind[mc['kind']];u=mc['id'];d=model.NewIntVar(0,3,u+'d');x=model.NewIntVar(1,66,u+'x');y=model.NewIntVar(1,66,u+'y')
 w=model.NewIntVar(3,6,'');h=model.NewIntVar(3,6,'');ex=model.NewIntVar(0,1,'');ey=model.NewIntVar(0,1,'')
 cases=[]
 for z in range(4):
  wh=(3,3) if k=='小' else (5,5) if k=='中' else (4,6) if z%2==0 else (6,4)
  cases.append([z,*wh,int(z%2==0),int(z%2==1)])
 model.AddAllowedAssignments([d,w,h,ex,ey],cases)
 ax=model.NewIntVar(1,138,'');ay=model.NewIntVar(1,138,'');sw=model.NewIntVar(6,14,'');sh=model.NewIntVar(6,14,'');xe=model.NewIntVar(1,140,'');ye=model.NewIntVar(1,140,'')
 model.Add(ax==2*x-ex);model.Add(ay==2*y-ey);model.Add(sw==2*w+2*ex);model.Add(sh==2*h+2*ey)
 # expansion totals 1 cell, i.e. doubled extent 2w+2, half on each side
 model.Add(xe==ax+sw);model.Add(ye==ay+sh)
 xs.append(model.NewIntervalVar(ax,sw,xe,''));ys.append(model.NewIntervalVar(ay,sh,ye,''))
 cx=model.NewIntVar(0,140,'');cy=model.NewIntVar(0,140,'');model.Add(cx==2*x+w);model.Add(cy==2*y+h)
 rows.append((mc,k,x,y,w,h,d,cx,cy));allv.extend([x,y,d])
def fix(x,y,w,h,margin=0):
 xs.append(model.NewFixedSizeIntervalVar(2*x-margin,2*w+2*margin,''));ys.append(model.NewFixedSizeIntervalVar(2*y-margin,2*h+2*margin,''))
core=(30,30);fix(*core,9,9,1)
# Reserve the true 46 transport cells in front of the outlets.
for j in range(23):fix(1,2+3*j,1,1);fix(2+3*j,1,1,1)
rect=(64,64,6,6);fix(*rect)
poles=[]
for x in (8,22,36,50,64):
 for y in (8,22,36,50,64):
  if not (x+1<30 or x>38 or y+1<30 or y>38):continue
  if not (x+1<64 or y+1<64):continue
  poles.append((x,y));fix(x,y,2,2)
model.AddNoOverlap2D(xs,ys)
by={r[0]['id']:r for r in rows};costs=[]
# B's relation used for distance guidance, without treating it as a proven geometric restriction.
for e in B['logical_feeds']:
 if e['source'] in by and e['target'] in by:
  a=by[e['source']];b=by[e['target']];dx=model.NewIntVar(0,140,'');dy=model.NewIntVar(0,140,'');model.AddAbsEquality(dx,a[7]-b[7]);model.AddAbsEquality(dy,a[8]-b[8]);costs.extend([dx,dy])
 elif e['source'].startswith('ORE'):
  b=by[e['target']];q=model.NewIntVar(0,140,'');model.AddMinEquality(q,[b[7],b[8]]);costs.append(3*q)
 elif e['target']=='CORE':
  a=by[e['source']];dx=model.NewIntVar(0,140,'');dy=model.NewIntVar(0,140,'');model.AddAbsEquality(dx,a[7]-69);model.AddAbsEquality(dy,a[8]-69);costs.extend([3*dx,3*dy])
model.Minimize(sum(costs));s=cp_model.CpSolver();s.parameters.num_workers=6;s.parameters.max_time_in_seconds=float(sys.argv[1]) if len(sys.argv)>1 else 300;s.parameters.random_seed=42
# Save every improving incumbent durably, even if the process is later interrupted.
class CB(cp_model.CpSolverSolutionCallback):
 def on_solution_callback(self):
  out={'objective':self.ObjectiveValue(),'wall':self.WallTime(),'core':core,'poles':poles,'reserved_rectangle':rect,'machines':[]}
  for mc,k,x,y,w,h,d,*_ in rows:
   xx,yy=self.Value(x),self.Value(y);out['machines'].append(dict(id=mc['id'],model=mc['kind'],kind=k,x0=xx,y0=yy,x1=xx+self.Value(w)-1,y1=yy+self.Value(h)-1,Din=self.Value(d),recipe_ids=[mc['recipes'][0]['recipe']],settings={'manufacture_on':True}))
  (BASE/'实验/摆放.json').write_text(json.dumps(out,ensure_ascii=False,indent=1))
  print('INCUMBENT',round(self.WallTime(),2),self.ObjectiveValue(),flush=True)
st=s.Solve(model,CB());print('FINAL',s.StatusName(st),s.WallTime(),s.ObjectiveValue(),s.BestObjectiveBound(),flush=True)
(BASE/'实验/摆放状态.json').write_text(json.dumps(dict(status=s.StatusName(st),wall=s.WallTime(),objective=s.ObjectiveValue(),bound=s.BestObjectiveBound()),indent=2))
