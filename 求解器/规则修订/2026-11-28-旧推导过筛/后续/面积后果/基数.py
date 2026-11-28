from collections import Counter
from itertools import combinations
from math import ceil
machines=(68,51,32,6,6,32,16,3,3)
areas=(9,9,24,9,9,25,25,24,24)
body=sum(n*a for n,a in zip(machines,areas))
print('机身、固定占格、余格',body,body+81+46*3,4900-body-81-46*3)
def k_bound(g,swap):
    left,bottom=(0,g) if swap else (g,0)
    ore={(1,3*i+1+int(i>=left)) for i in range(23)}
    ore.update((3*i+1+int(i>=bottom),1) for i in range(23))
    squares={}
    for z in range(1,69):
        for x,y in ((1,z),(z,1)):
            cells={(x+a,y+b) for a in range(2) for b in range(2)}
            if not ore&cells:squares[x,y]=cells
    # Two strips can meet only among the three origins (1,1),(1,2),(2,1).
    near=[s for s in squares if max(s)<=2]
    best=0
    for n in range(len(near)+1):
        for pick in combinations(near,n):
            used=set().union(*(squares[s] for s in pick))
            if len(used)!=4*n:continue
            for axis in range(2):
                for z in range(3,69):
                    cells=squares.get((1,z) if axis==0 else (z,1),set())
                    if not cells&used:used.update(cells)
            best=max(best,sum(x==1 or y==1 for x,y in used))
    return best
results=Counter()
for g in range(24):
    for s in range(1 if g==0 else 2):
        h=9 if g in (0,23) else 2 if g in (1,22) else 0
        results[h,k_bound(g,s)]+=1
print('各(h,K上限)排布数',sorted(results.items()))
print('A+4P上界',1390-min(ceil((1002+h-k)/4) for h,k in results))
for name,d in [('下限无箱',0),('增塑形',34),('小机或箱',36),('两件增配',68),('粉碎+采种',136)]:
    top=(4558-160-d)//4
    sizes=[(w,h) for w in range(6,67) for h in range(w,67) if top-10<=w*h<=top]
    print(name,'纯标量',top,'尺寸',sorted(sizes,key=lambda s:-s[0]*s[1]))
for bound in (1036,1035,1034):
    print(bound,[(w,bound//w) for w in range(6,67) if bound%w==0 and w<=bound//w<=66])
