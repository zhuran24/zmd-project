"""独立建立 221 台专线骨架，带分数 tick 初始相位的有限运行检查。

不是布局证书；运输路径只有逻辑长度，没有假造 70x70 坐标。
"""
import os
os.sched_setaffinity(0,{2})
from pathlib import Path
from collections import Counter
import random,json,argparse
OUT=Path(__file__).resolve().parent

class Network:
    def __init__(self,rng,q):
        self.q=q; self.rng=rng;self.t=0;self.m=[];self.paths=[];self.groups=[];self.ore=[0,0];self.delivered=[0,0]
        def add(kind,inputs,output,amount=1,duration=1):
            n=len(self.m); self.m.append({'kind':kind,'recipe':inputs,'item':output,'batch':amount,'d':duration*q,'inv':{i:rng.randrange(11) for i in inputs},'out':rng.randrange(11),'cache':rng.choice([-1]+list(range(duration*q+1))),'ptr':0,'paths':[]});return n
        def wire(src,dst,item):
            n=len(self.paths); length=rng.randint(1,3)
            self.paths.append({'src':src,'dst':dst,'item':item,'cells':[None if rng.random()<.5 else rng.randrange(q+1) for _ in range(length)]})
            if src>=0:self.m[src]['paths'].append(n)
            return n
        self.add,self.wire=add,wire
        blue_furnace=[add('精炼炉',{'蓝铁矿':1},'蓝铁块') for _ in range(34)]
        blue_crush=[add('粉碎机',{'蓝铁块':1},'蓝铁粉末') for _ in range(34)]
        source_crush=[add('粉碎机',{'源矿':1},'源石粉末') for _ in range(18)]
        for f,c in zip(blue_furnace,blue_crush):wire(-1,f,'蓝铁矿');wire(f,c,'蓝铁块')
        for c in source_crush:wire(-1,c,'源矿')
        mills=[]
        for p,amount,dense,up in [('蓝铁粉末',17,'致密蓝铁粉末',blue_crush),('源石粉末',9,'致密源石粉末',source_crush)]:
            for j in range(amount):
                m=add('研磨机',{p:2,'砂叶粉末':1},dense);mills.append(m)
                wire(up[2*j],m,p);wire(up[2*j+1],m,p)
        flower_mills=[add('研磨机',{'荞花粉末':2,'砂叶粉末':1},'细磨荞花粉末') for _ in range(6)];mills+=flower_mills
        sand_sources=[]
        for plant,number,k in [('砂叶',11,3),('荞花',6,2)]:
            for j in range(number):
                C=add('采种机',{plant:1},plant+'种子',2); A=add('种植机',{plant+'种子':1},plant);B=add('种植机',{plant+'种子':1},plant);K=add('粉碎机',{plant:1},plant+'粉末',k)
                ca=wire(C,A,plant+'种子');ac=wire(A,C,plant);wire(C,B,plant+'种子');wire(B,K,plant)
                self.groups.append((C,A,B,K,ca,ac))
                if plant=='砂叶':sand_sources += [K]*(3 if j<10 else 2)
                else:wire(K,flower_mills[j],'荞花粉末');wire(K,flower_mills[j],'荞花粉末')
        rng.shuffle(sand_sources)
        for src,dst in zip(sand_sources,mills):wire(src,dst,'砂叶粉末')
        steel=[add('精炼炉',{'致密蓝铁粉末':1},'钢块') for _ in range(17)]
        for src,dst in zip(mills[:17],steel):wire(src,dst,'致密蓝铁粉末')
        parts=[add('配件机',{'钢块':1},'钢制零件') for _ in range(6)]
        for src,dst in zip(steel[:6],parts):wire(src,dst,'钢块')
        bottles=[add('塑形机',{'钢块':2},'钢质瓶') for _ in range(6)]
        for j in range(5):wire(steel[6+2*j],bottles[j],'钢块');wire(steel[7+2*j],bottles[j],'钢块')
        wire(steel[16],bottles[5],'钢块')
        for j in range(3):
            pack=add('封装机',{'钢制零件':10,'致密源石粉末':15},'高容谷地电池',1,5)
            for src in parts[2*j:2*j+2]:wire(src,pack,'钢制零件')
            for src in mills[17+3*j:20+3*j]:wire(src,pack,'致密源石粉末')
            wire(pack,-2,'高容谷地电池')
            fill=add('灌装机',{'钢质瓶':10,'细磨荞花粉末':10},'精选荞愈胶囊',1,5)
            for src in bottles[2*j:2*j+2]:wire(src,fill,'钢质瓶')
            for src in flower_mills[2*j:2*j+2]:wire(src,fill,'细磨荞花粉末')
            wire(fill,-2,'精选荞愈胶囊')
        assert len(self.m)==221 and len(self.paths)==317
        # 加入本线种子，保证闭合后的 Φ 足够；多加 1 件覆盖起态判定。
        for C,A,B,K,ca,ac in self.groups:
            target=2*(len(self.paths[ca]['cells'])+len(self.paths[ac]['cells']))+7
            while self.phi2((C,A,B,K,ca,ac))<target:
                i=next(iter(self.m[A]['inv']));self.m[A]['inv'][i]+=1;assert self.m[A]['inv'][i]<=50
        self.actions=[('machine',i) for i in range(len(self.m))]+[('path',j) for j in range(len(self.paths))]
        rng.shuffle(self.actions)

    def phi2(self,g):
        C,A,B,K,ca,ac=g; c,a=self.m[C],self.m[A]
        return 2*(sum(x is not None for x in self.paths[ca]['cells'])+sum(a['inv'].values())+int(a['cache']>=0)+a['out']+sum(x is not None for x in self.paths[ac]['cells'])+sum(c['inv'].values())+int(c['cache']>=0))+c['out']

    def settle(self,receive):
        changed=True
        while changed:
            changed=False
            for typ,j in self.actions:
                if typ=='machine':
                    m=self.m[j]
                    if 0<=m['cache']<=self.t and m['out']+m['batch']<=50:m['out']+=m['batch'];m['cache']=-1;changed=True
                    if m['cache']<0 and all(m['inv'][x]>=n for x,n in m['recipe'].items()):
                        for x,n in m['recipe'].items():m['inv'][x]-=n
                        m['cache']=self.t+m['d'];changed=True
                    pp=m['paths'];n=len(pp)
                    for z in range(n):
                        idx=(m['ptr']+z)%n; p=self.paths[pp[idx]]
                        if m['out'] and p['cells'][0] is None:
                            m['out']-=1;p['cells'][0]=self.t+self.q;m['ptr']=(idx+1)%n;changed=True;break
                else:
                    p=self.paths[j];cells=p['cells'];last=len(cells)-1
                    if cells[last] is not None and cells[last]<=self.t:
                        dst=p['dst']; item=p['item']
                        if dst>=0 and self.m[dst]['inv'][item]<50:
                            self.m[dst]['inv'][item]+=1;cells[last]=None;changed=True
                        elif dst==-2:
                            which=0 if item=='高容谷地电池' else 1
                            if receive[which]:self.delivered[which]+=1;cells[last]=None;changed=True
                    for i in reversed(range(last)):
                        if cells[i] is not None and cells[i]<=self.t and cells[i+1] is None:
                            cells[i+1]=self.t+self.q;cells[i]=None;changed=True
                    if p['src']==-1 and cells[0] is None:
                        cells[0]=self.t+self.q;self.ore[0 if p['item']=='蓝铁矿' else 1]+=1;changed=True

    def state(self):
        return (tuple((tuple(m['inv'].values()),m['out'],-1 if m['cache']<0 else max(0,m['cache']-self.t),m['ptr']) for m in self.m),tuple(tuple(-1 if t is None else max(0,t-self.t) for t in p['cells']) for p in self.paths))

def run(cases,q):
    results=[]
    for seed in range(82000,82000+cases):
        rng=random.Random(seed);n=Network(rng,q);seen={};row=None
        for t in range(3500*q):
            n.t=t
            if t<150*q:
                take=[bool(((t//(30*q))+seed+i)%3) for i in [0,1]]
                if t%(13*q)==0:
                    for m in n.m:m['ptr']=rng.randrange(len(m['paths']))
            else:take=[True,True]
            n.settle(take)
            if t>150*q:
                key=n.state()
                if key in seen:
                    old,deliv,ore=seen[key]; period=(t-old)/q
                    delta=[a-b for a,b in zip(n.delivered,deliv)]; minerals=[a-b for a,b in zip(n.ore,ore)]
                    row={'seed':seed,'period_ticks':period,'product_counts':delta,'ore_counts':minerals,'rates':[d/period for d in delta],'ore_rates':[d/period for d in minerals],'pass':delta[0]*20==12*period and delta[1]*20==11*period and minerals==[34*period,18*period]}
                    break
                seen[key]=(t,n.delivered[:],n.ore[:])
        if row is None:row={'seed':seed,'status':'NO_CYCLE_WITHIN_LIMIT','limit_ticks':3500}
        results.append(row);print(json.dumps(row),flush=True)
    result={'quantum':q,'cases':len(results),'machines':dict(Counter(m['kind'] for m in n.m)),'paths':len(n.paths),'results':results,'all_pass':all(x.get('pass',False) for x in results)}
    (OUT/f'skeleton_events_q{q}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cases',type=int,default=12);p.add_argument('--q',type=int,default=1);a=p.parse_args();run(a.cases,a.q)
