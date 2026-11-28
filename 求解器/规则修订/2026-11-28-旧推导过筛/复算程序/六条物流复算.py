from fractions import Fraction as R
from math import ceil, gcd, lcm
from collections import Counter
from itertools import product

bat, cap = R(18,30), R(33,60)
parts, bottles, red, fine = 10*bat, 10*cap, 15*bat, 10*cap
steel = parts + 2*bottles
blue, ore = 2*steel, 2*red
sandpow, flowerpow = steel+red+fine, 2*fine
sand, flower = sandpow/3, flowerpow/2
plant = 2*(sand+flower)
mill = steel+red+fine
incoming = [ore+blue+sand+flower,blue+steel,3*mill,2*bottles,parts,plant,plant/2,25*bat,20*cap]
outgoing = [ore+blue+sandpow+flowerpow,blue+steel,mill,bottles,parts,plant,plant,bat,cap]
inports, outports = [list(map(ceil, values)) for values in (incoming,outgoing)]
sources = (70//3)*2 + 6
print(blue,ore,sources,inports,outports)
print(sum(inports),sum(outports),sum(outports[:-2])+ceil(5*bat)+ceil(5*cap)+sources,sum(inports)+ceil(bat+cap))
print('box',3*(40//8+1),3*ceil(40/8))
for i,o in ((1,1),(1,3),(3,1),(3,3)):
    degrees=[b-a for a in range(1,i+1) for b in range(1,o+1)]
    print((i,o),min(degrees),max(degrees))
order=list('ACB')
events=[]
for _ in range(9):
    channel=order.pop(0)
    events.append(channel)
    order.append(channel)
print(''.join(events))
for k in range(1,7):
    for L in range(1,9):
        h=gcd(k,L)
        for word in product('XY',repeat=L):
            counts=Counter((n%k,word[n%L]) for n in range(lcm(k,L)))
            for j in range(k):
                assert counts[j,'X']==word[j%h::h].count('X')
print('gcd cases',6*sum(2**L for L in range(1,9)))
for x,z,b in product(range(11), repeat=3):
    if x+b<=10 and x+z<=10:
        assert z>=max(0,x+z+b-10)
print('junction OK')
