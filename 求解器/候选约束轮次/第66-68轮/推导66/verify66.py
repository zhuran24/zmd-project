#!/usr/bin/env python3
"""Independent standard-library verifier: integer power covers and boundary DP.
Does not import power_bound.py, edge_dp.py, scipy, or the numerical model.
"""
from pathlib import Path
from collections import defaultdict
import json,hashlib,time
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3]
F={('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}
def cells(x,y,w,h):return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}
def overlap(a,b):
 x,y,w,h=a;u,v,W,H=b
 return max(x,u)<min(x+w,u+W) and max(y,v)<min(y+h,v+H)
def formal_loss(p,q,b):
 edge=(p in (1,68))+(q in (1,68));loss=[0,9,15][edge]
 if q-5>=b and q+7<=b+53:
  g=49-p-2
  if 0<=g<=6:loss=max(loss,[10,9,9,6,5,4,1][g])
 if p-5>=49 and p+7<=70:
  for g in (b-q-2,q-(b+53)):
   if 0<=g<=6:loss=max(loss,[10,9,9,6,5,4,1][g])
 return loss

def verify_power(data):
 result={};counts={};mins={}
 for b in (9,17):
  hole=(49,b,21,53)
  expected={(p,q) for p in range(1,69) for q in range(1,69) if not overlap((p,q,2,2),hole)}
  rows=data[str(b)];assert len(rows)==len(expected)
  assert {(r['x'],r['y']) for r in rows}==expected
  caps={}
  for r in rows:
   p,q=r['x'],r['y'];pole=(p,q,2,2);supply=(p-5,q-5,12,12)
   # Independent subblock intersection test; no shared center-domain helper.
   domain={(x,y) for x in range(max(2,p-7),min(68,p+8)+1) for y in range(max(2,q-7),min(68,q+8)+1)
           if overlap((x-1,y-1,3,3),supply) and not overlap((x-1,y-1,3,3),pole) and not overlap((x-1,y-1,3,3),hole)}
   seen=set()
   for tile in r['tiles']:
    x,y,w,h=tile;assert all(type(v)==int for v in tile)
    assert 1<=w<=3 and 1<=h<=3
    seen |= cells(*tile)
   assert domain<=seen
   assert r['cap']==min(23,len(r['tiles']))
   caps[p,q]=r['cap']
  result[b]=caps;counts[b]=len(caps)
  if b==9:
   mins={arm:min(23-cap for (p,q),cap in caps.items() if p>=49 and (q<9 if arm=='lower' else q>=62)) for arm in ('lower','upper')}
   assert mins=={'lower':7,'upper':7}
 return result,counts,mins

def all_bodies(b):
 hole=(49,b,21,53)
 def legal(c):return 1<=c[0]<=69 and 1<=c[1]<=69 and not(49<=c[0]<=69 and b<=c[1]<b+53)
 ans=[]
 for kind,w,h,axis in [('M',3,3,0),('M',3,3,1),('M',5,5,0),('M',5,5,1),('M',6,4,1),('M',4,6,0),('C',9,9,0),('C',9,9,1),('P',2,2,None)]:
  for x in range(1,71-w):
   for y in range(1,71-h):
    rr=(x,y,w,h)
    if overlap(rr,hole):continue
    if kind=='C' and x<=3 and y<=3:continue
    groups=[];needs=[]
    if axis==0:edges=[[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]]
    elif axis==1:edges=[[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]]
    if kind=='M':
     groups=[tuple(c for c in edge if legal(c)) for edge in edges];needs=[1,1]
    if kind=='C':
     take=[edge[k] for edge in edges for k in (1,4,7)]
     if not all(legal(c) for c in take):continue
     put=[(i,j) for i in range(x+1,x+8) for j in (y-1,y+9)] if axis==0 else [(i,j) for i in (x-1,x+9) for j in range(y+1,y+8)]
     groups=[(c,) for c in take]+[tuple(c for c in put if legal(c))];needs=[1]*6+[2]
    if any(len(e)<n for e,n in zip(groups,needs)):continue
    ans.append((kind,rr,axis,groups,needs))
 return ans

def frontier(table):
 # Pairwise dominance; implemented without the derivation's sorted loss scan.
 ans={}
 for k,v in table.items():
  c,p,l=k
  if not any(cc==c and pp==p and ll<l and vv<=v for (cc,pp,ll),vv in table.items()):ans[k]=v
 return ans

def solve_line(opts,gaps):
 N=len(gaps);states={(0,'G',0,0,0):0}
 # Explicit finite DAG; every transition increases position by at least 1.
 for pos in range(N):
  current=[(k,v) for k,v in states.items() if k[0]==pos]
  for (_,last,c,p,loss),value in current:
   moves=[]
   if gaps[pos] is not None:moves.append((pos+1,'G',0,0,0,gaps[pos]))
   moves += [(v[0],v[1],v[2],v[3],v[4],v[5] if len(v)==6 else 0) for v in opts[pos] if (last,v[1]) not in F]
   for end,tag,cc,pp,ll,fee in moves:
    if c+cc>1 or p+pp>12 or loss+ll>59:continue
    k=(end,tag,c+cc,p+pp,loss+ll)
    states[k]=min(states.get(k,10**9),value+fee)
  for k,v in current:del states[k]
 terminal={}
 for (pos,last,c,p,l),v in states.items():
  assert pos==N
  terminal[c,p,l]=min(terminal.get((c,p,l),10**9),v)
 return frontier(terminal)

def combine(tables,P,B):
 states={(0,0,0):0}
 for table in tables:
  nxt={}
  for (c,p,l),v in states.items():
   for (cc,pp,ll),vv in table.items():
    if c+cc<=1 and p+pp<=P and l+ll<=B:
     k=c+cc,p+pp,l+ll;nxt[k]=min(nxt.get(k,10**9),v+vv)
  states=frontier(nxt)
 return min(states.values(),default=1000)

def verify_dp(cases,caps):
 results=[];catalogs={b:all_bodies(b) for b in (9,17)};pairs_checked=0
 for case in cases:
  b=case['b'];branch=case['branch'];r=(49,b,21,53)
  def loss(p,q):return max(23-caps[b][p,q],formal_loss(p,q,b))
  def pole_allowed(p,q):return branch=='all' or not(p>=49 and (q<9 if branch=='no_lower_pole' else q>=62))
  eligible=[(p,q) for p,q in caps[b] if pole_allowed(p,q) and loss(p,q)<=13]
  tablemap={}
  for line in case['lines']:
   side,outer,corner=line['side'],line['outer'],line['corner'];horizontal=side in ('N','S')
   start,end=(1,70) if outer else (49,70) if horizontal else (b,b+53)
   fixed=69 if outer else 48 if side=='W' else b-1 if side=='S' else b+53
   opts=[set() for _ in range(end-start)];gaps=[];starts=defaultdict(list);ends=defaultdict(list)
   for u in range(start,end):
    x,y=(u,fixed) if horizontal else (fixed,u)
    gap=0 if outer and 49<=x<=69 and b<=y<b+53 else 1
    gaps.append(None if outer and corner and u>=68 else gap)
   for kind,rr,axis,groups,needs in catalogs[b]:
    x,y,w,h=rr
    if not ((y<=fixed<y+h and x<end and x+w>start) if horizontal else (x<=fixed<x+w and y<end and y+h>start)):continue
    if outer:
     if corner and overlap(rr,(68,68,2,2)) and rr!=(68,68,2,2):continue
     if not corner and rr==(68,68,2,2):continue
    if branch!='all':
     if kind=='P' and not pole_allowed(x,y):continue
     if kind=='M' and not any(x-6<=p<=x+w+4 and y-6<=q<=y+h+4 for p,q in eligible):continue
    u,length=(x,w) if horizontal else (y,h);lo=max(start,u);hi=min(end,u+length)
    full=lo==u and hi==u+length;tag=kind if full else 'Z'
    c,p,l=int(kind=='C'),int(kind=='P'),loss(x,y) if kind=='P' else 0
    if outer and corner and rr==(68,68,2,2):c=p=l=0
    opts[lo-start].add((hi-start,tag,c,p,l))
    if full:
     starts[lo,kind].append((rr,groups,needs));ends[hi,kind].append((rr,groups,needs))
   # Independently verify every geometrically enumerated forbidden adjacency.
   for (u,k),left in ends.items():
    for kk in ('M','C','P'):
     if (k,kk) not in F:continue
     for rr,gs,ns in left:
      a=cells(*rr)
      for rr2,gs2,ns2 in starts.get((u,kk),[]):
       d=cells(*rr2);pairs_checked+=1
       assert a&d or any(len(set(g)-d)<n for g,n in zip(gs,ns)) or any(len(set(g)-a)<n for g,n in zip(gs2,ns2))
   assert gaps==line['gaps']
   assert [[list(v) for v in sorted(o)] for o in opts]==line['options'],(b,branch,side,outer,corner,'options')
   got=solve_line(opts,gaps);saved={tuple(k):v for k,v in line['frontier']}
   assert got==saved,(b,branch,side,'DP')
   tablemap[side,outer,corner]=got
  for P in ((10,11,12) if branch=='all' else (10,)):
   B=23*P-217;J=B//9
   X=combine([tablemap[s,True,False] for s in ('E','N')],P,B)
   if b==9 and branch=='all':
    L=loss(68,68)
    if B>=L:X=min(X,combine([tablemap[s,True,True] for s in ('E','N')],P-1,B-L))
   Y=combine([tablemap[s,False,False] for s in ('W','S','N') if s!='N' or b==9],P,B)
   allowance=187-16*P+2*J
   results.append(dict(b=b,branch=branch,P=P,X=X,Y=Y,allowance=allowance,deficit=X+Y-allowance))
 return results,pairs_checked

def verify_joint(caps,weighted):
 name='joint17_j_certificate.json' if weighted else 'joint17_integer_certificate.json'
 data=json.loads((OUT/name).read_text());bodies=all_bodies(17)
 lines=[('E',False,69,1,17),('N',True,69,1,49),('W',False,48,17,70),('S',True,16,49,70)]
 corners=[(47,68,2,2),(68,15,2,2)]
 def loss(rr):return max(23-caps[17][rr[:2]],formal_loss(rr[0],rr[1],17))
 def projection(rr,line):
  _,hor,fixed,start,end=line;x,y,w,h=rr
  if hor:
   if not y<=fixed<y+h:return None
   u,length=x,w
  else:
   if not x<=fixed<x+w:return None
   u,length=y,h
  lo,hi=max(u,start),min(u+length,end)
  return (lo,hi,u,length) if lo<hi else None
 hits=[]
 for kind,rr,axis,groups,needs in bodies:
  touched=[line[0] for line in lines if projection(rr,line)]
  if len(touched)>1:
   assert kind=='P' and rr in corners
   hits.append({'body':list(rr),'lines':touched})
 assert len(hits)==2
 if not weighted:assert hits==data['multi_line_bodies']
 results=[]
 for case in data['cases']:
  chosen=[rr for rr,flag in zip(corners,case['mask']) if flag];L=sum(loss(rr) for rr in chosen)
  assert L==case['corner_loss'];tables=[]
  for line,saved in zip(lines,case['lines']):
   assert list(line)==saved['line'];side,hor,fixed,start,end=line
   opts=[set() for _ in range(end-start)];gaps=[1]*(end-start)
   for rr in chosen:
    if (p:=projection(rr,line)):
     for u in range(p[0],p[1]):gaps[u-start]=None
   for kind,rr,axis,groups,needs in bodies:
    p=projection(rr,line)
    if not p:continue
    if rr in corners and rr not in chosen:continue
    if any(overlap(rr,c) and rr!=c for c in chosen):continue
    lo,hi,u,length=p;tag=kind if lo==u and hi==u+length else 'Z'
    c,n,l=int(kind=='C'),int(kind=='P'),loss(rr) if kind=='P' else 0
    fee=-2 if kind=='P' and (rr[0] in (1,68) or rr[1] in (1,68)) else 0
    if rr in chosen:c=n=l=fee=0
    option=(hi-start,tag,c,n,l)+( (fee,) if weighted else ())
    opts[lo-start].add(option)
   assert gaps==saved['gaps']
   assert [[list(o) for o in sorted(v)] for v in opts]==saved['options']
   table=solve_line(opts,gaps)
   assert table=={tuple(k):v for k,v in saved['frontier']}
   tables.append(table)
  for P in (10,11,12):
   B=23*P-217
   if L>B:continue
   dp={(0,0,0):0}
   for table in tables:
    nxt={}
    for (c,p,l),v in dp.items():
     for (cc,pp,ll),vv in table.items():
      if c+cc>1 or p+pp>P-len(chosen) or l+ll>B-L:continue
      key=c+cc,p+pp,l+ll;nxt[key]=min(nxt.get(key,10**9),v+vv)
    dp=frontier(nxt)
   if weighted:
    best=min((v-2*min(P-len(chosen)-p,(B-L-l)//9)+16*P-2*len(chosen),(c,p,l),v,min(P-len(chosen)-p,(B-L-l)//9)) for (c,p,l),v in dp.items())
    row=dict(P=P,corner_mask=case['mask'],min_S=best[0],resources=list(best[1]),boundary_cost=best[2],omitted_J=best[3],deficit=best[0]-187)
   else:
    lower=min(dp.values());allowed=187-16*P+2*(B//9)
    row=dict(P=P,corner_mask=case['mask'],corner_loss=L,XY=lower,allowed=allowed,deficit=lower-allowed)
   results.append(row)
 assert results==data['results']
 if weighted:assert [min(r['min_S'] for r in results if r['P']==P) for P in (10,11,12)]==[180,187,196]
 return results

def main():
 t=time.monotonic();manifest=json.loads((OUT/'input_manifest.json').read_text())
 for name,h in manifest.items():
  assert hashlib.sha256((OUT/(name+'.md')).read_bytes()).hexdigest()==h
  assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h
 rules=(ROOT/'《明日方舟：终末地》游戏规则.txt').read_text();formal=(ROOT/'求解约束.txt').read_text()
 for s in ('大小3x3','大小5x5','大小6x4','大小9x9','供电桩：2x2','12x12'):assert s in rules
 for s in ('至多为 23 台循环态中有制造','9J ≤23P−217','4A+16P−2J+X+Y ≤4639'):assert s in formal
 caps,n,mins=verify_power(json.loads((OUT/'power_certificates.json').read_text()))
 results,pairs=verify_dp(json.loads((OUT/'edge_integer_certificate.json').read_text()),caps)
 joint=verify_joint(caps,False);joint_j=verify_joint(caps,True)
 expected=[-1,3,9,-9,-4,2,12,20]
 assert [r['deficit'] for r in results]==expected
 out=dict(joint17=joint,joint17_with_J=joint_j,status='PASS',power_poles=n,min_right_arm_loss=mins,independent_adjacency_checks=pairs,results=results,seconds=time.monotonic()-t,formal_inputs_unchanged=True,solver_used=False)
 (OUT/'exact_verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
