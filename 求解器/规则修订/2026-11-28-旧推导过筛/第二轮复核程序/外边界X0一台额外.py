# A=1110、P=10、J=0、恰多一台 3×3 单位（闲置机或箱，或在产塑形机）时 X0 的下界。
# 放宽：额外块长 3、可贴任何块（不施加端口阻挡），也可占右上角；忽略两段机身互撞。
from functools import lru_cache
INF=10**9
def seg(n,sf,ef,core,free):
    @lru_cache(None)
    def f(i,prev,c,fr):
        # prev: 0 自由格/段首, 1 在产块(M/C), 2 额外块
        if i==n: return 0 if not (prev==1 and ef) else INF
        best=1+f(i+1,0,c,fr)
        if prev!=1 and not (i==0 and sf):
            for L in (3,4,5):
                if i+L<=n: best=min(best,f(i+L,1,c,fr))
            if c and i+9<=n: best=min(best,f(i+9,1,c-1,fr))
        if fr and i+3<=n: best=min(best,f(i+3,2,c,fr-1))
        return best
    return f(0,0,core,free)
res={}
for W,H in ((30,37),(37,30)):
  for a in range(4,70-W+1):
    for b in range(4,70-H+1):
      right=(a+W-1==69); top=(b+H-1==69)
      opts=[]
      for cornerfree in ((False,True) if not (right and top) else (False,)):
        cs=[];rs=[]
        cend=68-(2 if cornerfree else 0)   # 额外块占右上角时盖住第 67、68 行/列
        if right:
          cs.append((b-1,True,True))
          if not top: cs.append((cend-(b+H)+1,True,False))
        else: cs.append((cend,True,False))
        if top:
          rs.append((a-1,True,True))
          if not right: rs.append((cend-(a+W)+1,True,False))
        else: rs.append((cend,True,False))
        segs=[s for s in cs+rs if s[0]>0]
        corner=0 if (right and top) or cornerfree else 2
        frees=0 if cornerfree else 1
        best=INF
        for ci in range(-1,len(segs)):
          for fi in range(-1,len(segs)):
            if fi>=0 and frees==0: continue
            tot=corner+sum(seg(n,sf,ef,1 if k==ci else 0,1 if k==fi else 0) for k,(n,sf,ef) in enumerate(segs))
            best=min(best,tot)
        opts.append(best)
      res[(W,H,a,b,right,top)]=min(opts)
m=min(res.values()); print('min X0 =',m)
for key in ('both','one','none'):
  sel=[v for k,v in res.items() if (k[4] and k[5])==(key=='both') and ((k[4]!=k[5])==(key=='one'))]
  print(key,min(sel))
