#!/usr/bin/env python3
"""Integer clique covers for disjoint 3x3 subblocks of supplied machines."""
from pathlib import Path
import json,hashlib
from functools import lru_cache
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
def cells(x,y,w,h): return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}
def center_domain(p,q,b):
    # A 3x3 subblock has integer center. It must meet the half-open supply
    # square [p-5,p+7)x[q-5,q+7), and avoid pole, empty rectangle and row/col 0.
    ans=set()
    for x in range(max(2,p-6),min(68,p+7)+1):
      for y in range(max(2,q-6),min(68,q+7)+1):
        if x-1<70 and x+2>49 and y-1<b+53 and y+2>b: continue
        if x-1<p+2 and x+2>p and y-1<q+2 and y+2>q: continue
        ans.add((x,y))
    return ans

def cover(points):
    if not points:return []
    answers=[]
    for transpose in (False,True):
      pts={(y,x) if transpose else (x,y) for x,y in points}
      ymin=min(y for x,y in pts); ymax=max(y for x,y in pts)
      @lru_cache(None)
      def dp(y):
        if y>ymax:return ()
        best=None
        for h in range(1,4):
          xs=sorted({x for x,j in pts if y<=j<y+h})
          tiles=[]
          while xs:
            x=xs[0];tiles.append((x,y,3,h));xs=[j for j in xs if j>x+2]
          value=tuple(tiles)+dp(y+h)
          if best is None or len(value)<len(best):best=value
        return best
      tiles=dp(ymin)
      if transpose:tiles=tuple((y,x,h,w) for x,y,w,h in tiles)
      answers.append(tiles)
    return list(min(answers,key=len))

def bound(p,q,b):
    pts=center_domain(p,q,b); tiles=cover(pts)
    assert all(1<=w<=3 and 1<=h<=3 for x,y,w,h in tiles)
    assert pts<=set().union(*(cells(*t) for t in tiles)) if tiles else not pts
    return min(23,len(tiles)),tiles

def legal_poles(b):
    for p in range(1,69):
      for q in range(1,69):
        if p<70 and p+2>49 and q<b+53 and q+2>b:continue
        yield p,q

def main():
    manifest={}
    for f in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']:
      raw=(ROOT/f).read_bytes(); manifest[f]=hashlib.sha256(raw).hexdigest()
      (OUT/(f+'.md')).write_bytes(raw)
    (OUT/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    result={}
    for b in (9,17):
      rows=[]
      for p,q in legal_poles(b):
        cap,tiles=bound(p,q,b)
        rows.append(dict(x=p,y=q,cap=cap,tiles=tiles))
      result[str(b)]=rows
      hist={k:sum(v['cap']==k for v in rows) for k in sorted({v['cap'] for v in rows})}
      print(b,len(rows),hist,flush=True)
    (OUT/'power_certificates.json').write_text(json.dumps(result,separators=(',',':')))
if __name__=='__main__':main()
