"""独立逐事件植物单元探测；时间格可细于 1 tick。

只读规则中的 1->2、1->1、1->k 配方，不导入推导席模型。
轨迹是局部反例/有限核验，不当作全厂布局或全称证明。
"""
import os
os.sched_setaffinity(0,{2})
from pathlib import Path
import random,json,argparse
OUT=Path(__file__).resolve().parent

class Cell:
    def __init__(self, lengths, quantum, k, rng, low=True, capacity=50):
        self.q=quantum; self.k=k; self.m=capacity; self.t=0
        self.ins=[0]*4; self.outs=[0]*4; self.cache=[-1]*4
        self.lines=[[None]*l for l in lengths]+[[None] for _ in range(k)]
        # A,C,B,K 索引 0,1,2,3。CA、AC、CB、BK、K 到下游。
        self.src=[1,0,1,2]+[3]*k
        self.dst=[0,1,2,3]+[-1]*k
        self.batch=[1,2,1,k]; self.ptr=[0]*4
        for j in range(4):
            self.ins[j]=rng.randrange(0,5 if low else capacity+1)
            self.outs[j]=rng.randrange(0,5 if low else capacity+1)
            if rng.random()<.6: self.cache[j]=rng.randrange(0,quantum+1)
        for line in self.lines:
            for i in range(len(line)):
                if rng.random()<.55: line[i]=rng.randrange(0,quantum+1)
        self.actions=[('start',j) for j in range(4)]+[('batch',j) for j in range(4)]+[('out',j) for j in range(4)]
        self.actions += [('move',li,i) for li,line in enumerate(self.lines) for i in reversed(range(len(line)))]
        rng.shuffle(self.actions)

    def phi2(self):
        return 2*(sum(x is not None for x in self.lines[0])+self.ins[0]+int(self.cache[0]>=0)+self.outs[0]+sum(x is not None for x in self.lines[1])+self.ins[1]+int(self.cache[1]>=0))+self.outs[1]

    def state(self):
        return {'time_step':self.t,'input':self.ins[:],'output':self.outs[:],
                'cache_remaining':[-1 if x<0 else max(0,x-self.t) for x in self.cache],
                'lines_remaining':[[None if x is None else max(0,x-self.t) for x in a] for a in self.lines],'phi2':self.phi2()}

    def key(self,period):
        s=self.state(); return (self.t%period,tuple(s['input']),tuple(s['output']),tuple(s['cache_remaining']),tuple(tuple(x) for x in s['lines_remaining']),tuple(self.ptr))

    def settle(self,accept):
        changed=True; sent=[0]*len(self.lines); source_sent=[0]*len(self.lines)
        while changed:
            changed=False
            for a in self.actions:
                if a[0]=='start':
                    j=a[1]
                    if self.cache[j]<0 and self.ins[j]:
                        self.ins[j]-=1; self.cache[j]=self.t+self.q; changed=True
                elif a[0]=='batch':
                    j=a[1]
                    if 0<=self.cache[j]<=self.t and self.outs[j]+self.batch[j]<=self.m:
                        self.outs[j]+=self.batch[j]; self.cache[j]=-1; changed=True
                elif a[0]=='out':
                    j=a[1]; ids=[i for i,s in enumerate(self.src) if s==j]
                    for off in range(len(ids)):
                        idx=(self.ptr[j]+off)%len(ids); li=ids[idx]
                        if self.outs[j] and self.lines[li][0] is None:
                            self.outs[j]-=1; self.lines[li][0]=self.t+self.q
                            self.ptr[j]=(idx+1)%len(ids); source_sent[li]+=1; changed=True
                            break
                else:
                    li,i=a[1:]; line=self.lines[li]
                    if line[i] is None or line[i]>self.t: continue
                    if i+1<len(line):
                        if line[i+1] is None: line[i+1]=self.t+self.q; line[i]=None; changed=True
                    elif self.dst[li]>=0:
                        j=self.dst[li]
                        if self.ins[j]<self.m: self.ins[j]+=1; line[i]=None; changed=True; sent[li]+=1
                    elif accept[li-4]:
                        line[i]=None; changed=True; sent[li]+=1
        return source_sent,sent

def run(seed,tries,quantum,settled=False):
    rng=random.Random(seed); failures=[]; cycles=0; checked=0
    for trial in range(tries):
        lengths=[rng.randint(1,4) for _ in range(4)]; k=rng.choice([2,3])
        c=Cell(lengths,quantum,k,rng,low=(trial%3!=0))
        if settled: c.settle([True]*k)
        initial=c.state(); initial_phi=c.phi2(); lower=min(initial_phi-1,2*(lengths[0]+lengths[1]+176))
        strong=initial_phi>=2*(lengths[0]+lengths[1])+5
        past=[]; seen={}; period=quantum*rng.randint(1,8); mask=[rng.random()<.7 for _ in range(period)]
        if not any(mask): mask[0]=True
        for step in range(int(settled),3000*quantum):
            c.t=step
            if step<30*quantum:
                accept=[rng.random()<.55 for _ in range(k)]
                if step%quantum==0 and rng.random()<.3: c.ptr[1]=rng.randrange(2)
            else: accept=[mask[step%period] for _ in range(k)]
            before=c.state(); c.settle(accept); state=c.state()
            if c.phi2()<lower:
                failures.append({'test':'D2 lower bound','trial':trial,'quantum':quantum,'lengths':lengths,'k':k,'initial':initial,'before':before,'after':state,'lower_phi2':lower,'actions':c.actions,'accept':accept,'tail':past[-20:]})
                break
            past.append(state)
            if step>=30*quantum:
                key=c.key(period)
                if key in seen:
                    start=seen[key]; orbit=past[start:]; cycles+=1
                    if strong:
                        checked+=1
                        bad=next((s for s in orbit if any(s['cache_remaining'][j]<0 for j in [1,2,3])),None)
                        if bad: failures.append({'test':'D3 cache nonempty','trial':trial,'quantum':quantum,'lengths':lengths,'k':k,'initial':initial,'cycle_length':len(orbit),'state':bad,'orbit':orbit,'actions':c.actions})
                    break
                seen[key]=len(past)-1
        if failures: break
    result={'seed':seed,'quantum':quantum,'settled_initial':settled,'trials_attempted':trial+1,'cycles':cycles,'strong_cycles':checked,'failures':failures}
    (OUT/f'plant_events_q{quantum}{"_settled" if settled else ""}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='failures'}|{'failure_count':len(failures),'failure_type':[f['test'] for f in failures]}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--tries',type=int,default=200);p.add_argument('--q',type=int,default=1);p.add_argument('--seed',type=int,default=82003);p.add_argument('--settled-init',action='store_true')
    a=p.parse_args();run(a.seed,a.tries,a.q,a.settled_init)
