from fractions import Fraction as F
from math import ceil
from itertools import product

battery, capsule = F(18,30), F(33,60)
parts, bottles = 10*battery, 10*capsule
steel = parts + 2*bottles
grinds = (steel, 15*battery, 10*capsule)
grinding = sum(grinds)
flowers, leaves = grinds[2], grinding/3
plant = 2*(flowers+leaves)
crush = 2*(grinds[0]+grinds[1])+flowers+leaves
smelt = 3*steel
work = (crush, smelt, grinding, bottles, parts, plant, plant/2, 5*battery, 5*capsule)
print('work', *work, 'ceil', *(ceil(x) for x in work))
# 0 denotes sand leaf, 1 to 3 denote main ingredients, -1 denotes empty.
slots = [(-1,0)]+list(product(range(4),range(1,51)))
def locked(state):
    return all(k>0 for k,n in state) and state[0][0]!=state[1][0]
def put(state, i, kind, qty):
    out=list(state)
    out[i]=(kind,qty) if qty else (-1,0)
    return tuple(out)
count=enter=enter_by_start=start_locked=exit_lock=0
for s in product(slots,repeat=2):
    (k,a),(j,b)=s
    if k==j and k>=0:
        continue
    count+=1
    was=locked(s)
    for i, (kind,qty) in enumerate(s):
        for x in range(4):
            if kind not in (-1,x) or qty==50 or s[1-i][0]==x:
                continue
            is_locked=locked(put(s,i,x,qty+1))
            enter += is_locked and not was
            exit_lock += was and not is_locked
    for i,(kind,qty) in enumerate(s):
        if kind>0 and qty>=2 and s[1-i][0]==0:
            end=put(put(s,i,kind,qty-2),1-i,0,s[1-i][1]-1)
            start_locked += was
            enter_by_start += locked(end) and not was
            exit_lock += was and not locked(end)
print('states, entry receipts, entry starts, starts while locked, exits',count,enter,enter_by_start,start_locked,exit_lock)
