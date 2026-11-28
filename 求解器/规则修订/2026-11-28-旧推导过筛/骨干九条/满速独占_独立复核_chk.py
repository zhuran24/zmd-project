from fractions import Fraction as F
seg=lambda s: 1+s//4  # steps 1..3 ->1, then every 4
def run(k,o,n=200):
    got=[]
    for i in range(n):
        s=o+8*i
        c=sum(1 for t in got if seg(s)-9<=seg(t)<=seg(s))
        if c>=k: return i+1
        got.append(s)
    return None
for k in range(6): print(k,{run(k,o) for o in range(1,9)})
# window of arbitrary arrival pattern: max receipts in 40 consecutive steps for k=5
B,C=F(3,5),F(11,20)
steelpart=1; steelblk=1; dense_fe=1; fepow=2; feblk=2; feore=2
print('Fe ore',B*10*2+C*10*4,'Or ore',B*15*2)
sand=B*10+C*20  # dense Fe powder per tick? steel blocks
steel=B*10+C*10*2; densefe=steel; fepowder=2*densefe; denseor=B*15; finebw=C*10
sandpow=densefe+denseor+finebw; bwpow=2*finebw
crush=denseor*2+fepowder+sandpow/3+bwpow/2
refine=steel+fepowder  # ore->block = fepowder (34), dense->steel
plant=2*(sandpow/3)+2*(bwpow/2)
print('steel',steel,'crush',crush,'refine',refine,'fit',B*10,'plant',plant)
print('edge ports', (139)//3, 2*(70//3))
