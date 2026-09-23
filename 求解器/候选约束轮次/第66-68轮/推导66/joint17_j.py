#!/usr/bin/env python3
"""Joint integer boundary DP including the -2J term and omitted edge poles."""
import json
from itertools import product
from collections import defaultdict
from joint17 import BODIES,CORNERS,LINES,project,loss,overlap,OUT
from edge_dp import frontier
F={('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}
def solve(opts,gaps):
 n=len(gaps);dp=[{} for _ in range(n+1)];dp[0]['G',0,0,0]=0
 for pos in range(n):
  for (prev,c,p,l),v in dp[pos].items():
   if gaps[pos] is not None:
    key='G',c,p,l;dp[pos+1][key]=min(dp[pos+1].get(key,1000),v+gaps[pos])
   for end,tag,cc,pp,ll,fee in opts[pos]:
    if (prev,tag) in F or c+cc>1 or p+pp>12 or l+ll>59:continue
    key=tag,c+cc,p+pp,l+ll;dp[end][key]=min(dp[end].get(key,1000),v+fee)
 terminal={}
 for (prev,c,p,l),v in dp[n].items():terminal[c,p,l]=min(terminal.get((c,p,l),1000),v)
 return frontier(terminal)
def combine(tables,P,B):
 dp={(0,0,0):0}
 for tab in tables:
  nxt={}
  for (c,p,l),v in dp.items():
   for (cc,pp,ll),vv in tab.items():
    if c+cc>1 or p+pp>P or l+ll>B:continue
    key=c+cc,p+pp,l+ll;nxt[key]=min(nxt.get(key,1000),v+vv)
  dp=frontier(nxt)
 return dp

def run():
 cases=[];results=[]
 for mask in product((0,1),repeat=2):
  selected=[rr for flag,rr in zip(mask,CORNERS) if flag];certs=[];tables=[]
  for line in LINES:
   side,hor,fixed,start,end=line;opts=[set() for _ in range(end-start)];gaps=[1]*(end-start)
   for rr in selected:
    if (pr:=project(rr,line)):
     for u in range(pr[0],pr[1]):gaps[u-start]=None
   for kind,rr,axis,groups,needs in BODIES:
    pr=project(rr,line)
    if not pr or rr in CORNERS and rr not in selected:continue
    if any(overlap(rr,c) and rr!=c for c in selected):continue
    lo,hi,u,length=pr;tag=kind if lo==u and hi==u+length else 'Z'
    cc,pp,ll=int(kind=='C'),int(kind=='P'),loss(rr) if kind=='P' else 0
    j=int(kind=='P' and (rr[0] in (1,68) or rr[1] in (1,68)))
    if rr in selected:cc=pp=ll=j=0
    opts[lo-start].add((hi-start,tag,cc,pp,ll,-2*j))
   opts=[sorted(o) for o in opts];table=solve(opts,gaps);tables.append(table)
   certs.append(dict(line=line,options=opts,gaps=gaps,frontier=[[k,v] for k,v in sorted(table.items())]))
  L=sum(loss(rr) for rr in selected);J=len(selected)
  cases.append(dict(mask=mask,corner_loss=L,lines=certs))
  for P in (10,11,12):
   B=23*P-217
   if L>B:continue
   dp=combine(tables,P-J,B-L)
   best=min((v-2*min(P-J-p,(B-L-l)//9)+16*P-2*J,(c,p,l),v,min(P-J-p,(B-L-l)//9)) for (c,p,l),v in dp.items())
   row=dict(P=P,corner_mask=mask,min_S=best[0],resources=best[1],boundary_cost=best[2],omitted_J=best[3],deficit=best[0]-187)
   results.append(row);print(row,flush=True)
 data=dict(cases=cases,results=results)
 (OUT/'joint17_j_certificate.json').write_text(json.dumps(data,separators=(',',':')))
if __name__=='__main__':run()
