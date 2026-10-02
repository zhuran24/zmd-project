#!/usr/bin/env python3
"""Independent arithmetic / geometry reconstructions, no dynamical sufficiency claim."""
import json,itertools,math
from pathlib import Path
OUT=Path(__file__).resolve().parent

def ports_a(g):return [3*k+1+(k>=g//3) for k in range(23)]
def ports_b(g):
 cells=[t for t in range(70) if t!=g]
 return [cells[i+1] for i in range(0,69,3)]
for g in range(0,70,3):assert ports_a(g)==ports_b(g)

def corridor_a(a):
 rows=[]
 for g in range(0,70,3):
  ps=ports_a(g)
  for b in range(2,65):
   for h in range(6,71-b):
    m=sum(b<=p<b+h for p in ps);e=1 if b+h==70 else 2
    if m<=e*(a-1):rows.append((g,b,h,m,e))
 return rows

def corridor_b(a):
 rows=[]
 for gap in range(24):
  ps=ports_b(gap*3);prefix=[0]
  for v in range(70):prefix.append(prefix[-1]+int(v in ps))
  for top in range(7,70):
   for bottom in range(2,top-4):
    count=prefix[top+1]-prefix[bottom];budget=(a-1)*(1+(top<69))
    if count<=budget:rows.append((gap*3,bottom,top-bottom+1,count,1+(top<69)))
 return rows
cuts={}
for a in (2,3,4):
 aa=corridor_a(a);bb=corridor_b(a);assert sorted(aa)==sorted(bb)
 cuts[str(a)]={'max_height':max(r[2] for r in aa),'max_top_attached':max([r[2] for r in aa if r[-1]==1],default=None),'cases':len(aa)}
assert [cuts[str(a)]['max_height'] for a in(2,3,4)]==[9,15,21]
assert cuts['2']['max_top_attached'] is None and cuts['3']['max_top_attached']==8

# Two generators for 47 common boundary gap patterns.
joints_a=[(g,h) for g in range(0,70,3) for h in range(0,70,3) if g==0 or h==0]
joints_b=[(0,0)]+[(3*k,0) for k in range(1,24)]+[(0,3*k) for k in range(1,24)]
assert sorted(joints_a)==sorted(joints_b)
def cap_a(g,h):
 src={(1,p) for p in ports_a(g)}|{(p,1) for p in ports_a(h)}
 total=0
 for x,y in src:
  cap=1
  for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
   if (x+dx,y+dy) in src:continue
   ok=False
   for k in range(3):
    bx=x+1 if dx==1 else x-3 if dx==-1 else x-k
    by=y+1 if dy==1 else y-3 if dy==-1 else y-k
    body={(a,b) for a in range(bx,bx+3) for b in range(by,by+3)}
    if bx>=1 and by>=1 and bx+2<=69 and by+2<=69 and not body&src:ok=True
   cap+=ok
  total+=cap
 return total

def cap_b(g,h):
 src=[(1,p) for p in ports_b(g)]+[(p,1) for p in ports_b(h)]
 possible={p:set() for p in src}
 # Only bodies near a source can supply a port adjacency.
 bodies=set()
 for x,y in src:
  for u in range(x-3,x+2):
   for v in range(y-3,y+2):
    if u<1 or v<1 or u>67 or v>67:continue
    if any(u<=a<u+3 and v<=b<v+3 for a,b in src):continue
    bodies.add((u,v))
 for u,v in bodies:
  for x,y in src:
   if v<=y<v+3 and x==u-1:possible[(x,y)].add('E')
   if v<=y<v+3 and x==u+3:possible[(x,y)].add('W')
   if u<=x<u+3 and y==v-1:possible[(x,y)].add('N')
   if u<=x<u+3 and y==v+3:possible[(x,y)].add('S')
 return 46+sum(len(v) for v in possible.values())
edge=[]
for g,h in joints_a:
 a=cap_a(g,h);b=cap_b(g,h);assert a==b,(g,h,a,b)
 edge.append({'gaps':[g,h],'cap':a})
assert max(r['cap'] for r in edge)==93

# Minimum directed adjacency counts along machine port sides, independent subset / bitmask forms.
def side_a(L):
 result=[]
 for k in range(1,L+1):
  vals=[]
  for pp in itertools.combinations(range(L),k):
   vals.append(sum(2 for p,q in zip(pp,pp[1:]) if q-p<=3))
  result.append(min(vals))
 return result

def side_b(L):
 ans=[999]*L
 for mask in range(1,2**L):
  count=mask.bit_count();last=None;v=0
  for p in range(L):
   if mask>>p&1:
    if last is not None and p-last<4:v+=2
    last=p
  ans[count-1]=min(ans[count-1],v)
 return ans
sides={L:side_a(L) for L in (3,5,6)}
for L in sides:assert sides[L]==side_b(L)
assert sides[3]==[0,2,4] and sides[6]==[0,0,2,6,8,10]

# The DP stores the required total intake/output and each machine's recipe bound.
def dp_a(n,d,L,rate_cap):
 dp={0:0}
 for i in range(n):
  nd={}
  for old,c in dp.items():
   for k in range(L+1):
    z=min(d,old+min(k,rate_cap));v=c+(sides[L][k-1] if k else 0)
    nd[z]=min(nd.get(z,10**9),v)
  dp=nd
 return dp[d]

def dp_b(n,d,L,rate_cap):
 # Unbounded knapsack in machine-count and throughput dimensions.
 table=[[10**8]*(d+1) for _ in range(n+1)];table[0][0]=0
 for used in range(1,n+1):
  for wanted in range(d+1):
   table[used][wanted]=min(table[used-1][max(0,wanted-min(k,rate_cap))]+(sides[L][k-1] if k else 0) for k in range(L+1))
 return table[n][d]
configs={'粉碎':(68,95,3,3),'研磨':(32,95,6,3),'塑形':(6,11,3,2),'封装':(3,15,6,5),'灌装':(3,11,6,4)}
tables={}
for name,(n,d,L,c) in configs.items():
 vals=[dp_a(n+q,d,L,c) for q in range(d+1)]
 vals2=[dp_b(n+q,d,L,c) for q in range(d+1)]
 assert vals==vals2,(name,vals[:5],vals2[:5])
 tables[name]={'initial':vals[0],'increments':[(vals[0]-v)/8 for v in vals[:8]],'max_decrease':vals[0]/8}
assert sum(t['initial'] for t in tables.values())==164
assert sum(t['max_decrease'] for t in tables.values())==20.5

# Arithmetic checked both expression-first and compartment sums.
arithmetic={'active_categories':[68+51+6+6,32+16,32+3+3], 'minimum_machines':sum([68,51,32,6,6,32,16,3,3]),'machine_area':131*9+48*25+38*24,'minimum_weight':131*2+(48+38)*3,'interfaces':52+305+260+2,'base_nonport':184-93+8,'inc':sum(t['initial'] for t in tables.values())}
assert arithmetic['active_categories']==[131,48,38]
assert arithmetic['minimum_machines']==217 and arithmetic['machine_area']==3291 and arithmetic['minimum_weight']==520
arithmetic.update(transport_general=math.ceil((619+99)/4),transport_five_min=math.ceil((619+99+164/2)/4),transport_four_min=math.ceil((619+98+109)/4),transport_no_box=math.ceil((619+184+8+109-91)/4),transport_no_box_q=math.ceil((619+184+8+109-91+4)/4),occupied=3291+81+138+40+208,no_bridge_occupied=3291+81+138+40+306,plant_transport=math.ceil((64+4)/2),plant_area=48*25+16*9+34)
assert [arithmetic[k] for k in ['transport_general','transport_five_min','transport_four_min','transport_no_box','transport_no_box_q','occupied','no_bridge_occupied','plant_transport','plant_area']]==[180,200,207,208,209,3758,3856,34,1378]
# An independent sum over the nine machine-type records.
records=[(68,9,2),(51,9,2),(32,24,3),(6,9,2),(6,9,2),(32,25,3),(16,25,3),(3,24,3),(3,24,3)]
assert sum(n*a for n,a,w in records)==arithmetic['machine_area']
assert sum(n*w for n,a,w in records)==arithmetic['minimum_weight']
# At most 3 turns cannot traverse opposite directions in a closed direction walk.
D=[(1,0),(0,1),(-1,0),(0,-1)]
for turns in range(4):
 for start in range(4):
  for signs in itertools.product((-1,1),repeat=turns):
   cur=start;seen=[cur]
   for v in signs:cur=(cur+v)%4;seen.append(cur)
   if cur!=start:continue
   assert all((d+2)%4 not in seen for d in seen)
   # A single direction or adjacent pair admits a positive potential through q x q units.
   possible=[v for v in D if all(v[0]*D[d][0]+v[1]*D[d][1]>0 for d in set(seen))]
   if not possible:
    possible=[(x,y) for x in(-1,1) for y in(-1,1) if all(x*D[d][0]+y*D[d][1]>0 for d in set(seen))]
   assert possible
result={'corridor':cuts,'joint_boundary_cases':len(joints_a),'edge_cap_max':max(v['cap'] for v in edge),'edge_caps':edge,'side_incidence':sides,'transport_drop_tables':tables,'arithmetic':arithmetic,'two_independent_encodings_equal':True}
(OUT/'geo_small_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['edge_caps']},ensure_ascii=False))
