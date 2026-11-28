"""第二轮：46 个矿石格的 92 个切向方向中，不能贴 3x3 子块（不压矿石格、在第 1..69 行列内）的个数，取 47 种排布最小值。"""
import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'corner_caps.py')).read().split('res = {}')[0])
mins=[]
for name,q,lm,bm in layouts():
    ore={(1,y) for y in lm}|{(x,1) for x in bm}
    def block_ok(x0,y0):
        return x0>=1 and y0>=1 and x0+2<=69 and y0+2<=69 and not any((x0+i,y0+j) in ore for i in range(3) for j in range(3))
    cov=lambda c:any(block_ok(c[0]-i,c[1]-j) for i in range(3) for j in range(3))
    bad=0
    for y in lm:
        for d in (1,-1): bad+= not cov((1,y+d))
    for x in bm:
        for d in (1,-1): bad+= not cov((x+d,1))
    mins.append((bad,name))
print(min(mins), sorted(set(b for b,_ in mins)))
