import random
def seg(s): return 1 + s//4
def run(k, offer, H):
    got=[]
    for s in range(1,H+1):
        if not offer(s): continue
        if got and s-got[-1] < 8: continue
        cur=seg(s)
        if sum(1 for t in got if cur-seg(t) <= 9) >= k: continue
        got.append(s)
    return got
def check(k, got, H):
    import bisect
    for a in range(1,H+1,7):
        for N in (1,5,37,40,41,80,123,400):
            b=a+N-1
            c=bisect.bisect_right(got,b)-bisect.bisect_left(got,a)
            assert c <= k*(-(-(N+3)//40)), (k,a,N,c)
H=4000
for k in range(6):
    g=run(k, lambda s: True, H)
    check(k,g,H)
    rnd=random.Random(k)
    for _ in range(30):
        p=rnd.random()
        g2=run(k, lambda s: rnd.random()<p, H); check(k,g2,H)
    print(k, len(g)/(H/8), k/5)
