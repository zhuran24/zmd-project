#!/usr/bin/env python3
"""Integer joint boundary DP for b=17; only two corner poles can meet two lines."""
import json
from itertools import product
from edge_dp import old_pole_loss
from power_bound import cells
from edge_dp import solve_line,combine
from power_bound import OUT
CAPS={(r['x'],r['y']):r['cap'] for r in json.loads((OUT/'power_certificates.json').read_text())['17']}

CORNERS=[(47,68,2,2),(68,15,2,2)]
LINES=[('E',False,69,1,17),('N',True,69,1,49),('W',False,48,17,70),('S',True,16,49,70)]
def overlap(a,b):
 x,y,w,h=a;u,v,W,H=b
 return x<u+W and u<x+w and y<v+H and v<y+h

def generate_bodies():
 # Enumerate anchors from the four measured lines, rather than the verifier's
 # independent full-base anchor enumeration.
 target=set()
 for _,hor,fixed,start,end in LINES:
  target.update((u,fixed) if hor else (fixed,u) for u in range(start,end))
 hole=cells(49,17,21,53)
 def legal(c):return 1<=c[0]<70 and 1<=c[1]<70 and c not in hole
 result=[]
 for kind,w,h,axis in [('M',3,3,0),('M',3,3,1),('M',5,5,0),('M',5,5,1),('M',6,4,1),('M',4,6,0),('C',9,9,0),('C',9,9,1),('P',2,2,None)]:
  anchors={(cx-dx,cy-dy) for cx,cy in target for dx in range(w) for dy in range(h)}
  for x,y in sorted(anchors):
   if not (1<=x<=70-w and 1<=y<=70-h) or cells(x,y,w,h)&hole:continue
   if kind=='C' and x<=3 and y<=3:continue
   if axis==0:sides=[[(x-1,y+j) for j in range(h)],[(x+w,y+j) for j in range(h)]]
   elif axis==1:sides=[[(x+j,y-1) for j in range(w)],[(x+j,y+h) for j in range(w)]]
   groups=[];needs=[]
   if kind=='M':groups=[tuple(c for c in side if legal(c)) for side in sides];needs=[1,1]
   elif kind=='C':
    takes=[side[k] for side in sides for k in (1,4,7)]
    if not all(legal(c) for c in takes):continue
    puts=([(x+j,y-1) for j in range(1,8)]+[(x+j,y+9) for j in range(1,8)] if axis==0 else [(x-1,y+j) for j in range(1,8)]+[(x+9,y+j) for j in range(1,8)])
    groups=[(c,) for c in takes]+[tuple(c for c in puts if legal(c))];needs=[1]*6+[2]
   if any(len(g)<n for g,n in zip(groups,needs)):continue
   result.append((kind,(x,y,w,h),axis,groups,needs))
 return result

BODIES=generate_bodies()
def loss(rr):return max(23-CAPS[rr[:2]],old_pole_loss(rr,(49,17,21,53)))
def project(rr,line):
 _,hor,fixed,start,end=line;x,y,w,h=rr
 if not ((y<=fixed<y+h and x<end and x+w>start) if hor else (x<=fixed<x+w and y<end and y+h>start)):return None
 u,length=(x,w) if hor else (y,h)
 return max(start,u),min(end,u+length),u,length

def run():
 multi=[]
 for kind,rr,axis,groups,needs in BODIES:
  hit=[l[0] for l in LINES if project(rr,l)]
  if len(hit)>1:
   assert kind=='P' and rr in CORNERS
   multi.append(dict(body=rr,lines=hit))
 cases=[];results=[]
 for mask in product((0,1),repeat=2):
  selected=[rr for flag,rr in zip(mask,CORNERS) if flag]
  linecert=[];tables=[]
  for line in LINES:
   side,hor,fixed,start,end=line;opts=[set() for _ in range(end-start)];gaps=[1]*(end-start)
   for rr in selected:
    proj=project(rr,line)
    if proj:
     lo,hi,_,_=proj
     for u in range(lo,hi):gaps[u-start]=None
   for kind,rr,axis,groups,needs in BODIES:
    proj=project(rr,line)
    if not proj:continue
    if rr in CORNERS and rr not in selected:continue
    if any(overlap(rr,c) and rr!=c for c in selected):continue
    lo,hi,u,length=proj;tag=kind if lo==u and hi==u+length else 'Z'
    cc,pp,ll=int(kind=='C'),int(kind=='P'),loss(rr) if kind=='P' else 0
    if rr in selected:cc=pp=ll=0
    opts[lo-start].add((hi-start,tag,cc,pp,ll))
   table=solve_line(tuple(tuple(sorted(o)) for o in opts),tuple(gaps));tables.append(table)
   linecert.append(dict(line=line,options=[sorted(o) for o in opts],gaps=gaps,frontier=[[k,v] for k,v in sorted(table.items())]))
  cornerloss=sum(loss(rr) for rr in selected)
  cases.append(dict(mask=mask,corner_loss=cornerloss,lines=linecert))
  for P in (10,11,12):
   B=23*P-217
   if cornerloss>B:continue
   lower=combine(tables,P-len(selected),B-cornerloss)
   row=dict(P=P,corner_mask=mask,corner_loss=cornerloss,XY=lower,allowed=187-16*P+2*(B//9),deficit=lower-(187-16*P+2*(B//9)))
   results.append(row);print(row,flush=True)
 cert=dict(multi_line_bodies=multi,cases=cases,results=results)
 (OUT/'joint17_integer_certificate.json').write_text(json.dumps(cert,separators=(',',':')))
if __name__=='__main__':run()
