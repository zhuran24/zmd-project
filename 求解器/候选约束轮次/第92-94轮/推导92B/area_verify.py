from fractions import Fraction as Q
from itertools import combinations,product
from pathlib import Path
import json,hashlib
D=Path(__file__).parent; ROOT=D.parents[3]
# A: support sets and bounded linear filling, then min-plus dynamic programming.
def edge_a(L,cap):
 out={}
 for d2 in range(2*cap+1):
  d=Q(d2,2); best=Q(999)
  for k in range(L+1):
   if k<d: continue
   for S in combinations(range(L),k):
    cs=[sum(1 for j in (i-1,i+1) if 0<=j<k and abs(S[j]-S[i])<=3) for i in range(k)]
    rem=d; val=Q(0)
    for c in sorted(cs):
     f=min(rem,1); val+=f*c; rem-=f
    if not rem: best=min(best,val)
  out[d2]=best
 return out
# B: no support variables: quarter-unit flow vectors and direct neighboring-positive-port weights.
def edge_b(L,cap):
 out={}
 for v in product(range(5),repeat=L):
  s=sum(v)
  if s>4*cap:continue
  indices=[j for j in range(L) if v[j]]
  w=sum(v[i]+v[j] for i,j in zip(indices,indices[1:]) if j-i<=3)
  out[s]=min(out.get(s,999),w)
 return {k:Q(v,4) for k,v in out.items()}
def fleet_a(table,n,total):
 dp={0:Q(0)}
 for _ in range(n):
  nxt={}
  for a,va in dp.items():
   for b,vb in table.items():
    if a+b<=total:nxt[a+b]=min(nxt.get(a+b,Q(9999)),va+vb)
  dp=nxt
 return dp[total]
def fleet_b(table,n,total):
 # Independent dense array of accumulated costs; values stored as integer quarter weights.
 inf=1000000; old=[0]+[inf]*total
 for machine in range(n):
  new=[inf]*(total+1)
  for t in range(total+1):
   for flow,cost in table.items():
    if t>=flow:new[t]=min(new[t],old[t-flow]+int(4*cost))
  old=new
 return Q(old[total],4)
spec={'研磨机':(6,3,Q(189,2),32,48,24),'塑形机':(3,2,Q(11),6,11,9),'封装机':(6,5,Q(15),3,8,24),'灌装机':(6,4,Q(11),3,6,24)}
claim={'研磨机':lambda n:max(Q(0),Q(379-8*n,2)),'塑形机':lambda n:Q(max(0,22-2*n)),'封装机':lambda n:Q({3:24,4:18,5:10,6:6,7:2}.get(n,0)),'灌装机':lambda n:Q({3:14,4:6,5:2}.get(n,0))}
res={'weights':{},'dimensions':{},'scalar':{},'band':{},'archived_infeasibility':{}}
for typ,(L,cap,total,nmin,nmax,area) in spec.items():
 a=edge_a(L,cap);b=edge_b(L,cap)
 assert all(a[t]==b[2*t] for t in a)
 vals={}
 for n in range(nmin,nmax+1):
  x=fleet_a(a,n,int(2*total)); y=fleet_b(b,n,int(4*total));z=claim[typ](n)
  assert x==y==z,(typ,n,x,y,z)
  vals[n]=str(x)
 res['weights'][typ]={'fleet':vals,'minimum_increment':str(min(4*area+claim[typ](n+1)-claim[typ](n) for n in range(nmin,nmax+1)))}
res['weights']['omega_min']=str(sum(claim[k](spec[k][3]) for k in spec))
# Rectangle areas: independent Cartesian enumeration and divisor computation.
for bound in (1044,1090,1107,1110,1113,1142):
 a=sorted((w*h,w,h) for w in range(6,69) for h in range(w,69) if w*h<=bound)
 b=[]
 for area in range(36,bound+1):
  for d in range(6,69):
   if area%d==0 and d<=area//d<=68:b.append((area,d,area//d))
 assert a==sorted(b)
 res['dimensions'][bound]={'maximum':a[-1][0],'shapes':[x[1:] for x in a if x[0]==a[-1][0]]}
res['scalar']['minimum_machine_area']=9*(68+51+6+6)+25*(32+16)+24*(32+3+3)
assert res['scalar']['minimum_machine_area']==3291
res['scalar']['base_fixed_area']=3291+81+46*3
res['scalar']['fourway_constant']=619-93+3*46
res['scalar']['no_box_inner_constant']=829+88+4
res['scalar']['general_inner_constant']=619+90+8+88+4
res['scalar']['general_area_rhs']=4*(4900-3291-81-138)-809
res['scalar']['extra_grind_seed_area']=9+25
res['scalar']['extra_grind_seed_4A_14P']=4*(4900-3291-81-138-9-25)-921
assert res['scalar']['extra_grind_seed_4A_14P']==4503
# Independently enumerate all 47 corner-compatible ways to place the unique band gap.
bands=[]
for l in range(0,70,3):
 for b in range(0,70,3):
  if l and b:continue
  # Port centers from 3-cell intervals on either side of gap.
  ports=lambda gap:[s+1 for s in range(0,gap,3)]+[s+1 for s in range(gap+1,70,3)]
  O={(1,y) for y in ports(l)}|{(x,1) for x in ports(b)}
  assert len(O)==46
  I={(1,y) for y in range(1,70)}|{(x,1) for x in range(2,70)}
  union=set(); pole=0
  for x in range(1,68):
   for y in range(1,68):
    if x>1 and y>1:continue
    body={(x+i,y+j) for i in range(3) for j in range(3)}
    if not(body&O):union|=body&I
  for x in range(1,69):
   for y in range(1,69):
    if x>1 and y>1:continue
    body={(x+i,y+j) for i in range(2) for j in range(2)}
    if not(body&O):pole=max(pole,len(body&I))
  bands.append({'gap_left':l,'gap_bottom':b,'nonore':len(I-O),'body_union':len(union),'pole':pole})
assert len(bands)==47 and max(r['body_union'] for r in bands)==3 and max(r['pole'] for r in bands)==2
res['band']={'arrangements':len(bands),'max_body_union':3,'max_pole':2,'all':bands}
# Scalar budget recomputed through both inequalities and explicit permissible J sets.
rows=[]
for P in range(10,19):
 allowed=[J for J in range(P+1) if 54*P-25*J>=520 and 23*P-10*J>=217]
 jmax=min(P,(54*P-520)//25,(23*P-217)//10)
 assert allowed==list(range(jmax+1))
 rows.append({'P':P,'J_max':jmax,'4E+Omega_max':4751-4440-16*P+2*jmax})
res['scalar']['A1110']=rows
assert max(r['4E+Omega_max'] for r in rows)==151
assert max(r['4E+Omega_max'] for r in rows if r['P']>=11)==139
# Archive status audit, not a new solver run.
hist=ROOT/'求解器/候选约束轮次/三审-第63-80轮/out'
for file in sorted(hist.glob('proj_b*_formal.json')):
 obj=json.loads(file.read_text());res['archived_infeasibility'][file.name]=obj
for fn in ('proj_b17_P10_J0-0_cap187.json','milp_b17_P10_J0-0_cap187_cpsat.json','milp_b17_P11_J0-4_cap187_cpsat.json'):
 file=hist/fn
 if file.exists():res['archived_infeasibility'][fn]=json.loads(file.read_text())
# A local legal idle body, not a complete layout/counterexample.
res['corner_scope_gap']={'unit':'粉碎机','body':[67,67,3,3],'switch':'关闭','corner':[69,69],'old_X_corner_charge':2,'direction_account_transport_or_empty_charge':0,'not_full_layout_counterexample':True}
(D/'area_verify.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
print(json.dumps({'weights':res['weights'],'dimensions':res['dimensions'],'scalar':res['scalar'],'band':{k:v for k,v in res['band'].items() if k!='all'},'archive_files':len(res['archived_infeasibility'])},ensure_ascii=False,indent=2))
