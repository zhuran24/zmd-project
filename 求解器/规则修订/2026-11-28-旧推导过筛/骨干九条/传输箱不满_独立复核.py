# 独立复核：0-1 BFS（填空代价1，取空最前非空格代价0），另用带件数的精确模拟验证下界与可达
from collections import deque
import itertools
def sym_min(K, S=6):
    start=(0,)*S; dist={start:0}; dq=deque([start])
    while dq:
        w=dq.popleft(); d=dist[w]
        if 0 not in w and len(set(w))<K: return d, w
        # erase
        f=next((i for i,x in enumerate(w) if x),None)
        if f is not None:
            n=w[:f]+(0,)+w[f+1:]
            if n not in dist or dist[n]>d: dist[n]=d; dq.appendleft(n)
        for k in range(1,K+1):
            i=next((i for i,x in enumerate(w) if x in (0,k)),None)
            if i is None or w[i]==k: continue
            n=w[:i]+(k,)+w[i+1:]
            if n not in dist: dist[n]=d+1; dq.append(n)
    return None,None
print({K:sym_min(K) for K in range(1,8)})
# 精确：带件数，进一件代价1，取一件（从最前非空格）代价0；件数上限 n_in 以内能否到达拒收
def exact_min(K, S=6, cap=50, limit=25):
    start=tuple(((0,0),)*S); dist={start:0}; dq=deque([start])
    while dq:
        w=dq.popleft(); d=dist[w]
        kinds=[c[0] for c in w]
        if all(c[1]>0 for c in w) and len(set(kinds))<K: return d
        if d>=limit: continue
        f=next((i for i,c in enumerate(w) if c[1]),None)
        if f is not None:
            c=w[f]; n=list(w); n[f]=(c[0] if c[1]>1 else 0, c[1]-1); n=tuple(n)
            if n not in dist or dist[n]>d: dist[n]=d; dq.appendleft(n)
        for k in range(1,K+1):
            i=next((i for i,c in enumerate(w) if c[1]==0 or (c[0]==k and c[1]<cap)),None)
            if i is None: continue
            n=list(w); n[i]=(k,w[i][1]+1); n=tuple(n)
            if n not in dist: dist[n]=d+1; dq.append(n)
    return None
print({K:exact_min(K) for K in (3,4,5,6,7)})
# 单口 40 步窗口、相邻成功进件至少相隔 8 步：最大件数
best=max(len(c) for r in range(0,8) for c in itertools.combinations(range(1,41),r) if all(b-a>=8 for a,b in zip(c,c[1:]))) if False else None
import functools
@functools.lru_cache(None)
def mx(j):  # 步 1..j 内
    return 0 if j<=0 else max(mx(j-1),1+mx(j-8))
print("单口40步", mx(40), "41步", mx(41))
