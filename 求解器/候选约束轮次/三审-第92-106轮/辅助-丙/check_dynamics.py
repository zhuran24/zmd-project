#!/usr/bin/env python3
"""独立的局部三阶段状态机；不使用 sim2/内核/任何席位的脚本。"""
from dataclasses import dataclass,field
from pathlib import Path
import random,json

OUT=Path(__file__).resolve().parent

@dataclass
class Machine:
    k:int
    raw:int=0
    out:int=0
    done:int|None=None
    starts:int=0
    sent:int=0

@dataclass
class Lane:
    src:str
    dst:str|None
    cells:list
    last:int=-100000

class Plant:
    def __init__(self,rng,k,lengths,n,strong=False):
        self.rng=rng;self.k=k
        self.m={x:Machine(q) for x,q in [('C',2),('A',1),('B',1),('K',k)]}
        pairs=[('C','A'),('C','B'),('A','C'),('B','K')]
        self.lanes=[Lane(a,b,[None]*l) for (a,b),l in zip(pairs,lengths)]
        self.lanes += [Lane('K',None,[None]*rng.randint(1,5)) for _ in range(n)]
        self.rank=list(range(len(self.lanes)));rng.shuffle(self.rank)
        self.order=list(self.m);rng.shuffle(self.order)
        for x,m in self.m.items():
            m.raw=50 if strong else rng.randrange(51)
            m.out=50 if strong else rng.randrange(51)
            m.done=rng.randrange(9) if strong else rng.choice([None]+list(range(9)))
        for index,lane in enumerate(self.lanes):
            lane.cells=[-rng.randrange(9) if strong or rng.randrange(2) else None for _ in lane.cells]
            lane.last=rng.randrange(-20,0)
        self.events=[];self.low_out={x:m.out for x,m in self.m.items()}

    def flush(self,x,t):
        m=self.m[x]
        if m.done is not None and m.done<=t and m.out+m.k<=50:
            m.out+=m.k;m.done=None

    def phi2(self):
        C,A=self.m['C'],self.m['A']
        return 2*(sum(v is not None for i in (0,2) for v in self.lanes[i].cells)+
                  A.raw+A.out+C.raw+(A.done is not None)+(C.done is not None))+C.out

    def reset(self,clear):
        self.rng.shuffle(self.rank);self.rng.shuffle(self.order)
        if clear:
            for l in self.lanes:l.last=-100000

    def step(self,t,drain=True):
        for x in self.m:self.flush(x,t)
        # 各条路独占格、末端对应唯一正确物品，路次序任意。
        ids=list(range(len(self.lanes)));self.rng.shuffle(ids)
        for idx in ids:
            l=self.lanes[idx]
            for j in range(len(l.cells)-1,-1,-1):
                birth=l.cells[j]
                if birth is None or t-birth<8:continue
                if j+1<len(l.cells):
                    if l.cells[j+1] is not None:continue
                    l.cells[j+1]=t
                elif l.dst is not None:
                    if self.m[l.dst].raw==50:continue
                    self.m[l.dst].raw+=1
                elif not drain or self.rng.randrange(4)==0:continue
                l.cells[j]=None
        event=None
        for x in self.order:
            m=self.m[x]
            candidates=[i for i,l in enumerate(self.lanes) if l.src==x]
            candidates.sort(key=lambda i:(self.lanes[i].last,self.rank.index(i)))
            if m.out:
                for i in candidates:
                    l=self.lanes[i]
                    if l.cells[0] is None:
                        l.cells[0]=t;l.last=t;m.out-=1;m.sent+=1
                        if x=='C':event='A' if i==0 else 'B'
                        self.low_out[x]=min(self.low_out[x],m.out)
                        self.flush(x,t)
                        break
        for x,m in self.m.items():
            self.flush(x,t)
            if m.done is None and m.raw:
                m.raw-=1;m.done=t+8;m.starts+=1
            self.low_out[x]=min(self.low_out[x],m.out)
        return event

def general_cases():
    rng=random.Random(10710922)
    checks=0;minphi=10000;clears=0
    for case in range(900):
        p=Plant(rng,2+case%2,[rng.randint(1,12) for _ in range(4)],2)
        normal=bool(case%2)
        t0=0
        if normal:p.step(0);t0=1
        start=p.phi2();L=len(p.lanes[0].cells)+len(p.lanes[2].cells)
        h=2*L+(352 if normal else 300);m=0
        for t in range(t0,t0+500):
            if rng.randrange(23)==0:
                clear=case%3!=0;p.reset(clear)
                if clear:m+=1;clears+=1
            p.step(t)
            phi=p.phi2()
            assert phi>=min(start-m-1,h-m),(case,t,phi,start,m,h)
            if start>=2:assert phi>=1
            minphi=min(minphi,phi);checks+=1
    return dict(cases=900,steps=checks,clear_events=clears,min_phi=minphi/2,violations=0)

def strong_cases():
    rng=random.Random(10710923);steps=0;mins=[50,50,50,50]
    for case in range(360):
        k=2+case%2;n=case%(k+1)
        p=Plant(rng,k,[rng.randint(1,20) for _ in range(4)],n,True)
        L=len(p.lanes[0].cells)+len(p.lanes[2].cells)
        assert p.phi2()==2*(L+177)
        for t in range(1600):
            if rng.randrange(11)==0:p.reset(case%3!=0)
            p.step(t,drain=not(300<=t%700<430))
            assert all(m.done is not None for m in p.m.values())
            C,A,B,K=[p.m[x] for x in ('C','A','B','K')]
            assert B.raw>=49 and K.raw>=49 and B.out>=49 and K.out>=50-k
            assert p.lanes[1].cells[0] is not None and p.lanes[3].cells[0] is not None
            mins=[min(a,b) for a,b in zip(mins,[B.raw,K.raw,B.out,K.out])]
            steps+=1
    return dict(cases=360,steps=steps,min_B_raw_K_raw_B_out_K_out=mins,violations=0)

def finite_stock():
    rng=random.Random(10710921);mins={1:50,2:50,3:50};cases=0;boundary=[]
    for k in (1,2,3):
        for initial_out in range(50-k,51):
            for done in [None]+list(range(9)):
                for pattern in range(5):
                    raw=50;q=initial_out;cache=done;birth=[-8]*k
                    firstempty=None
                    for t in range(420):
                        if cache is not None and cache<=t and q+k<=50:q+=k;cache=None
                        for i in range(k):
                            if birth[i] is not None and t-birth[i]>=8 and (pattern==0 or rng.randrange(pattern+1)==0):birth[i]=None
                        choices=[i for i in range(k) if birth[i] is None]
                        if q and choices:
                            i=rng.choice(choices);birth[i]=t;q-=1
                        if t<400:mins[k]=min(mins[k],q);assert q>=50-3*k
                        if cache is not None and cache<=t and q+k<=50:q+=k;cache=None
                        if cache is None and raw:raw-=1;cache=t+8
                        if cache is None and firstempty is None:firstempty=t
                        if t<400:assert cache is not None
                    if firstempty is not None:boundary.append(firstempty)
                    cases+=1
    assert min(boundary)==400
    return dict(cases=cases,minimum_output=mins,first_possible_empty=min(boundary),violations=0)

def normal_boundary_witness():
    rng=random.Random(1)
    p=Plant(rng,2,[3,4,4,3],2,True)
    for l in p.lanes:l.cells=[-8]*len(l.cells)
    p.m['C'].out=48;p.m['C'].done=8;p.m['A'].done=0
    # 保持CB路可请求，CA、AC构成满阻塞；B初料不取满，以便CB首格在1、9腾空。
    p.m['B'].raw=0;p.m['B'].out=0;p.m['B'].done=None
    p.m['K'].raw=0;p.m['K'].out=0;p.m['K'].done=None
    p.lanes[1].cells=[None]*4
    p.lanes[3].cells=[None]*3
    start=p.phi2();events=[]
    for t in range(1,11):
        event=p.step(t)
        events.append(dict(step=t,event=event,phi=p.phi2()/2))
    return dict(L=7,start=start/2,events=events,
                note='准备截面上的176只能作被否证的旧加强；150仍成立')

def low_inventory():
    rng=random.Random(221231);cases=[]
    for k in (2,3):
        for clear in (False,True):
            for lens in ([1,1,1,1],[7,8,31,4],[12,3,17,9]):
                p=Plant(rng,k,lens,k)
                for m in p.m.values():m.raw=0;m.out=0;m.done=None
                for l in p.lanes:l.cells=[None]*len(l.cells)
                p.m['C'].out=2
                assert p.phi2()==2
                minimum=2
                for t in range(4000):
                    if t%3==0:p.reset(clear)
                    p.step(t)
                    minimum=min(minimum,p.phi2())
                    assert p.phi2()>=1
                assert all(m.starts>0 for m in p.m.values())
                cases.append(dict(k=k,clear=clear,lengths=lens,min_phi=minimum/2,
                                  batches={x:m.starts for x,m in p.m.items()}))
    return dict(cases=cases,steps=48000,violations=0)

def origin_probe():
    # 输入路两带 P -> Q -> X。P中的正确矿石在调试反向通道 Q -> P 中进入，
    # 之后旋转两带成为最终正向路，未拆除物理单位；刚离开的单位仍为Q。
    state=dict(P=dict(item='源矿',previous='Q',age=8),Q=None,X_raw=0,X_cache=None)
    initial=json.loads(json.dumps(state))
    sent=0
    for _ in range(128):
        can_move=state['P'] is not None and state['P']['previous']!='Q' and state['Q'] is None
        if can_move:sent+=1
        assert not can_move
    return dict(initial=initial,steps=128,forward_moves=sent,final=state,
                status='literal-topology countermodel; applicability depends on whether dedicated-route wording constrains initial provenance')

def main():
    result=dict(general=general_cases(),strong=strong_cases(),finite=finite_stock(),
                prepared_176=normal_boundary_witness(),low_inventory=low_inventory(),origin_probe=origin_probe())
    (OUT/'dynamics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
