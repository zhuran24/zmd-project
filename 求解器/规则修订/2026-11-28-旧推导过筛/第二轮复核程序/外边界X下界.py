# P=12、J=0、九机型恰下限无箱、A=1110 时正式 X 的下界（只用外边段，放宽：忽略两段机身互撞、角上邻接）
from functools import lru_cache
INF=10**9
def seg(n,sf,ef,core):
    # 长 n 的边段，格 0..n-1；sf/ef: 起/止端外侧是不能贴 M/C 的东西；core: 可用核心块数(0/1)
    # 块: M 长 3,4,5；C 长 9；M、C 两两不相邻；自由格费 1
    @lru_cache(None)
    def f(i,prevblock,c):
        if i==n: return 0 if not (prevblock and ef) else INF
        best=1+f(i+1,False,c)
        if not prevblock and not (i==0 and sf):
            for L in (3,4,5):
                if i+L<=n: best=min(best,f(i+L,True,c))
            if c and i+9<=n: best=min(best,f(i+9,True,c-1))
        return best
    return f(0,False,core)
res={}
for W,H in ((30,37),(37,30)):
  for a in range(4,70-W+1):
    for b in range(4,70-H+1):
      right=(a+W-1==69); top=(b+H-1==69)
      # 第 69 列 第 1..68 行的段
      cs=[]
      if right:
        cs.append((b-1, True, True))            # 行1..b-1：下端是取货口，上端贴 R
        if not top: cs.append((68-(b+H)+1, True, False))  # 行 b+H..68：下端贴 R，上端为角格
      else: cs.append((68,True,False))
      rs=[]
      if top:
        rs.append((a-1,True,True))
        if not right: rs.append((68-(a+W)+1,True,False))
      else: rs.append((68,True,False))
      segs=[s for s in cs+rs if s[0]>0]
      corner=0 if (right and top) else 2
      best=INF
      for ci in range(-1,len(segs)):
        tot=corner+sum(seg(n,sf,ef,1 if k==ci else 0) for k,(n,sf,ef) in enumerate(segs))
        best=min(best,tot)
      res[(W,H,a,b)]=best
m=min(res.values()); print('位置数',len(res),'min X =',m,[k for k,v in res.items() if v==m][:6])
