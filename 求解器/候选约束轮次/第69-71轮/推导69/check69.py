#!/usr/bin/env python3
"""Standard-library independent checker: reconstruct geometry, exact dual and DP.
No producer imports; no optimization software; all writes stay beside this file.
"""
from pathlib import Path
from fractions import Fraction as Q
from collections import defaultdict
import json,hashlib,time,sys,copy
OUT=Path(__file__).resolve().parent;OLD=OUT.parents[1]/'第66-68轮'/'推导66'
SHAPES=((3,3,0),(3,3,1),(5,5,0),(5,5,1),(6,4,1),(4,6,0))
def intersects(a,b):return a[0]<b[0]+b[2] and b[0]<a[0]+a[2] and a[1]<b[1]+b[3] and b[1]<a[1]+a[3]
def coords(r):return {(x,y) for x in range(r[0],r[0]+r[2]) for y in range(r[1],r[1]+r[3])}
def local_system(wall,hole=None):
 xmin,xmax,ymin,ymax=wall
 def legal(x,y):return xmin<=x<xmax and ymin<=y<ymax and not(5<=x<7 and 5<=y<7) and not(hole and x>=hole[0] and y>=hole[1])
 bodies=[];occupants=defaultdict(list)
 for w,h,ax in SHAPES:
  for x in range(1-w,12):
   for y in range(1-h,12):
    if not all(legal(i,j) for i,j in coords((x,y,w,h))):continue
    if ax==0:sides=[[(x-1,i) for i in range(y,y+h)],[(x+w,i) for i in range(y,y+h)]]
    else:sides=[[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]]
    sides=[[c for c in s if legal(*c)] for s in sides]
    if not all(sides):continue
    bodies.append((x,y,w,h,ax,sides))
    for c in coords((x,y,w,h)):occupants[c].append(len(bodies)-1)
 rows=[];rhs=[]
 for c in sorted(occupants):rows.append({j:1 for j in occupants[c]});rhs.append(1)
 for j,b in enumerate(bodies):
  for side in b[-1]:
   row=defaultdict(int);row[j]=1
   for c in side:
    for i in occupants.get(c,[]):row[i]+=1
   rows.append(row);rhs.append(len(side))
 return bodies,rows,rhs

def verify_dual(cert,wall,hole=None,weights=None,extra_rows=()):
 bodies,rows,rhs=local_system(wall,hole)
 for row,r in extra_rows:rows.append(row);rhs.append(r)
 n=len(bodies);co=[Q(0)]*n;value=Q(0)
 for i,a,b in cert['rows']:
  assert a>=0 and b>0 and 0<=i<len(rows)
  v=Q(a,b);value+=rhs[i]*v
  for j,k in rows[i].items():co[j]+=k*v
 for j,a,b in cert['bounds']:
  assert a>=0 and b>0 and 0<=j<n
  v=Q(a,b);co[j]+=v;value+=v
 if weights is None:weights=[1]*n
 assert all(c>=w for c,w in zip(co,weights))
 assert value==Q(*cert['upper'])
 assert value.numerator//value.denominator==cert['integer_upper']
 return dict(columns=n,rows=len(rows),upper=str(value),integer_upper=cert['integer_upper'])

def verify_groups():
 data=json.loads((OLD/'power_certificates.json').read_text())['17'];caps={};hole=(49,17,21,53)
 legal={(p,q) for p in range(1,69) for q in range(1,69) if not intersects((p,q,2,2),hole)}
 assert len(data)==len(legal)==3511
 for c in data:
  p,q=c['x'],c['y'];assert (p,q) in legal and (p,q) not in caps
  points={(x,y) for x in range(max(2,p-6),min(68,p+7)+1) for y in range(max(2,q-6),min(68,q+7)+1) if not intersects((x-1,y-1,3,3),hole) and not intersects((x-1,y-1,3,3),(p,q,2,2))}
  tiles=c['tiles'];assert all(1<=r[2]<=3 and 1<=r[3]<=3 for r in tiles)
  covered=set()
  for t in tiles:covered.update(coords(t))
  assert points<=covered and c['cap']==min(23,len(tiles))
  caps[p,q]=c['cap']
 return caps
LINES=[['E',False,69,1,17],['N',True,69,1,49],['W',False,48,17,70],['S',True,16,49,70]]
CORNERS=[(47,68,2,2),(68,15,2,2)]
def projection(rr,line):
 _,horizontal,k,lo,hi=line;x,y,w,h=rr
 if horizontal:
  if not y<=k<y+h:return None
  a,b=x,x+w
 else:
  if not x<=k<x+w:return None
  a,b=y,y+h
 if a>=hi or b<=lo:return None
 return max(a,lo),min(b,hi),a,b

def edge_bodies():
 ans=[];hole=(49,17,21,53)
 def available(c):return 1<=c[0]<70 and 1<=c[1]<70 and not(49<=c[0]<70 and 17<=c[1]<70)
 types=[('M',w,h,ax) for w,h,ax in SHAPES]+[('C',9,9,0),('C',9,9,1),('P',2,2,None)]
 for kind,w,h,ax in types:
  for x in range(1,71-w):
   for y in range(1,71-h):
    rr=(x,y,w,h)
    if intersects(rr,hole) or not any(projection(rr,l) for l in LINES):continue
    if kind=='M':
     ss=([[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]] if ax==0 else [[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]])
     if not all(any(available(c) for c in s) for s in ss):continue
    if kind=='C':
     if x<=3 and y<=3:continue
     take=([(i,y+k) for i in (x-1,x+9) for k in (1,4,7)] if ax==0 else [(x+k,j) for j in (y-1,y+9) for k in (1,4,7)])
     put=([(x+k,j) for k in range(1,8) for j in (y-1,y+9)] if ax==0 else [(i,y+k) for k in range(1,8) for i in (x-1,x+9)])
     if not all(available(c) for c in take) or sum(map(available,put))<2:continue
    ans.append((kind,rr,ax))
 return ans

def loss(rr,caps,new):
 p,q=rr[:2];count=int(p in (1,68))+int(q in (1,68));v=max(23-caps[p,q],(0,9,15)[count])
 costs=(10,9,9,6,5,4,1)
 if 22<=q<=63 and 0<=47-p<=6:v=max(v,costs[47-p])
 if 54<=p<=63 and 0<=15-q<=6:v=max(v,costs[15-q])
 if new and count:v=max(v,10)
 if new=='local':
  v=max(v,23-LOCAL.get((p,q),23))
 return v
LOCAL={}
for c in json.loads((OUT/'supply_strip_certificates.json').read_text()):
 for xy in c['positions']:LOCAL[tuple(xy)]=c['integer_upper']
BAD={('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}
def line_dp(opts,gaps):
 # Full resource table; no producer's Pareto pruning.
 d=[{} for _ in range(len(gaps)+1)];d[0][('G',0,0,0)]=0
 for x,gs in enumerate(gaps):
  for (tag,c,p,l),v in d[x].items():
   moves=[]
   if gs is not None:moves.append((x+1,'G',0,0,0,gs))
   for e,t,C,P,L,fee in opts[x]:
    if (tag,t) not in BAD:moves.append((e,t,C,P,L,fee))
   for e,t,C,P,L,fee in moves:
    if c+C>1 or p+P>12 or l+L>59:continue
    key=(t,c+C,p+P,l+L);d[e][key]=min(d[e].get(key,10000),v+fee)
 end={}
 for (tag,c,p,l),v in d[-1].items():end[c,p,l]=min(end.get((c,p,l),10000),v)
 return end

def verify_edges(caps,new=True):
 bodies=edge_bodies();stored=json.loads((OUT/('new_edge_local_certificate.json' if new=='local' else 'new_edge_certificate.json')).read_text() if new else (OLD/'joint17_j_certificate.json').read_text());results=[]
 assert len(stored['cases'])==4
 multi=[(k,r) for k,r,ax in bodies if sum(projection(r,l) is not None for l in LINES)>1]
 assert len(multi)==2 and {r for k,r in multi}==set(CORNERS) and all(k=='P' for k,r in multi)
 for case in stored['cases']:
  selected=[r for r,t in zip(CORNERS,case['mask']) if t];tabs=[]
  for line,c in zip(LINES,case['lines']):
   start,end=line[3:];opts=[set() for _ in range(end-start)];gaps=[1]*(end-start)
   for rr in selected:
    z=projection(rr,line)
    if z:
     for a in range(z[0],z[1]):gaps[a-start]=None
   for kind,rr,ax in bodies:
    z=projection(rr,line)
    if not z or rr in CORNERS and rr not in selected or any(intersects(rr,r) and rr!=r for r in selected):continue
    lo,hi,a,b=z;tag=kind if (lo,hi)==(a,b) else 'Z';C=int(kind=='C');P=int(kind=='P');L=loss(rr,caps,new) if P else 0;J=int(P and (rr[0] in (1,68) or rr[1] in (1,68)))
    if rr in selected:C=P=L=J=0
    opts[lo-start].add((hi-start,tag,C,P,L,-2*J))
   assert c['line']==line and c['gaps']==gaps and c['options']==[[list(v) for v in sorted(o)] for o in opts]
   tab=line_dp(opts,gaps)
   # Compare all certified frontier entries with unpruned DP.
   assert all(tab.get(tuple(k))==v for k,v in c['frontier'])
   tabs.append(tab)
  corner_loss=sum(loss(rr,caps,new) for rr in selected);J=len(selected);assert corner_loss==case['corner_loss']
  for P in (10,11,12):
   B=23*P-217-corner_loss
   if B<0:continue
   dp={(0,0,0):0}
   for tab in tabs:
    nd={}
    for (a,b,c),v in dp.items():
     for (d,e,f),w in tab.items():
      if a+d<=1 and b+e<=P-J and c+f<=B:
       k=(a+d,b+e,c+f);nd[k]=min(nd.get(k,10000),v+w)
    dp=nd
   best=min(16*P-2*J+v-2*min(P-J-p,(B-l)//(10 if new else 9)) for (c,p,l),v in dp.items())
   entry=next(r for r in stored['results'] if r['P']==P and r['corner_mask']==case['mask']);assert entry['min_S']==best
   results.append(dict(P=P,corner_mask=case['mask'],min_S=best))
 return dict(body_options=len(bodies),results=results)

def equality_bounds():
 a=json.loads((OLD/'joint17_integer_certificate.json').read_text())
 b=json.loads((OLD/'joint17_j_certificate.json').read_text())
 out=[]
 for case,checked in zip(a['cases'],b['cases']):
  assert case['mask']==checked['mask'] and case['corner_loss']==checked['corner_loss']
  tabs=[]
  for line,other in zip(case['lines'],checked['lines']):
   assert line['line']==other['line'] and line['gaps']==other['gaps']
   expected=[sorted({tuple(o[:5]) for o in os}) for os in other['options']]
   assert expected==[[tuple(o) for o in os] for os in line['options']]
   tabs.append(line_dp([[tuple(o)+(0,) for o in os] for os in line['options']],line['gaps']))
  P=11-sum(case['mask']);B=36-case['corner_loss'];dp={(0,0,0):0}
  for tab in tabs:
   nd={}
   for (a,b,c),v in dp.items():
    for (d,e,f),w in tab.items():
     if a+d<=1 and b+e<=P and c+f<=B:
      k=(a+d,b+e,c+f);nd[k]=min(nd.get(k,10000),v+w)
   dp=nd
  out.append(dict(mask=case['mask'],XY=min(dp.values())))
 assert all(r['XY']==19 for r in out)
 return out

def main():
 start=time.monotonic();cert=json.loads((OUT/'wall0_certificate.json').read_text())
 out={'wall0':verify_dual(cert,(-20,7,-20,32))}
 caps=verify_groups();out['old_power_positions']=len(caps)
 out['old_edges']=verify_edges(caps,False);out['new_edges']=verify_edges(caps,True)
 out['equality_XY']=equality_bounds()
 out['local_edges']=verify_edges(caps,'local')
 out['elapsed']=time.monotonic()-start
 (OUT/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
