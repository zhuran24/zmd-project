"""Asynchronous manual-fill/start/stop audit. Never inserts into a cache."""
import argparse,json,random,time
from collections import Counter
from pathlib import Path
from model_spec import graph
from engine_time import TimestampWorld
from engine_age import AgeWorld
from factory_check import compare,units

WEIGHT={"源矿":1,"蓝铁矿":1,"砂叶种子":2,"荞花种子":2,"砂叶":3,"荞花":3,
        "蓝铁块":2,"蓝铁粉末":3,"源石粉末":2,"砂叶粉末":4,"荞花粉末":4,
        "致密蓝铁粉末":11,"致密源石粉末":9,"细磨荞花粉末":13,
        "钢块":12,"钢制零件":13,"钢质瓶":25}

def run(seed,maxlen):
    started=time.monotonic();rng=random.Random(seed);spec,sources,routes=graph()
    lengths=[rng.randint(1,maxlen) for _ in routes]
    i=next(i for i,(s,d,x) in enumerate(routes) if s=="H6")
    j=next(i for i,(s,d,x) in enumerate(routes) if s=="Q6")
    lengths[j]=lengths[i]
    a=TimestampWorld(lengths,prepared=False);b=AgeWorld(lengths,prepared=False)
    physical,belts=units(spec,sources,routes,lengths);order=physical+belts;rng.shuffle(order)
    a.rebuild(order,True);b.rebuild(order,True)
    backup=json.loads(Path(__file__).with_name("arithmetic_graph.json").read_text())["backup"]
    added=Counter();ops=0;lastweight=0;trace=[]
    upper=sum(50*sum(WEIGHT[x] for x,k in m.needs)+(50+m.amount)*WEIGHT[m.product] if m.duration==8 else 50*sum(WEIGHT[x] for x,k in m.needs) for m in spec.values())
    upper+=sum(lengths[e]*WEIGHT[x] for e,(_,d,x) in enumerate(routes) if d!="核心")
    def weight():
        total=0
        for n,m in spec.items():
            total+=sum(v*WEIGHT[x] for x,v in a.inputs[n].items())
            if m.duration==8:
                total+=a.output[n]*WEIGHT[m.product]
                if a.done[n] is not None:
                    total+=m.amount*WEIGHT[m.product] if a.done[n]<=a.t else sum(v*WEIGHT[x] for x,v in m.needs)
        for e,(_,d,x) in enumerate(routes):
            if d!="核心":total+=sum(v is not None for v in a.belts[e])*WEIGHT[x]
        return total
    def tick(n):
        nonlocal lastweight
        for _ in range(n):
            a.step();b.step();compare(a,b)
            w=weight();assert lastweight<=w<=upper,(a.t,w,lastweight,upper);lastweight=w
    def switch(on):
        for n,m in spec.items():a.on[n]=on and m.duration==8;b.on[b.name_id[n]]=a.on[n]
    def operation(item,count):
        nonlocal ops,lastweight
        added[item]+=count;ops+=1
        assert added[item]<=backup[item],(item,added[item],backup[item])
        w=weight();assert lastweight<=w<=upper;lastweight=w
        # Human operation intervals need not land on manufacturing boundaries.
        if ops%9==0:tick(rng.randint(3,41))
    switch(False);tick(37)
    for round_no in range(1,21):
        switch(False)
        for n,m in spec.items():
            for x,_ in m.needs:
                amount=50-a.inputs[n][x]
                a.inputs[n][x]+=amount
                b.stock[b.name_id[n]][list(dict(m.needs)).index(x)]+=amount
                operation(x,amount)
        for n,m in spec.items():
            if m.duration==8:
                amount=50-a.output[n];a.output[n]+=amount;b.goods[b.name_id[n]]+=amount;operation(m.product,amount)
        for e,(_,d,x) in enumerate(routes):
            if d=="核心":continue
            for k in range(lengths[e]-1,-1,-1):
                if a.belts[e][k] is None:
                    a.belts[e][k]=a.t;b.cells[b.start[e]+k]=0;operation(x,1)
        for n,m in spec.items():
            if m.duration==8:
                amount=50-a.output[n];a.output[n]+=amount;b.goods[b.name_id[n]]+=amount;operation(m.product,amount)
        compare(a,b)
        done=all(a.done[n] is not None and a.done[n]<=a.t for n,m in spec.items() if m.duration==8)
        trace.append({"round":round_no,"step":a.t,"weight":weight(),"all_nonfinal_caches_done":done})
        if done:break
        switch(True);tick(rng.randint(16,389));switch(False)
    else:raise AssertionError("startup not complete")
    tick(rng.randint(9,89))
    for n,m in spec.items():
        assert set(a.inputs[n].values())=={50}
        if m.duration==8:assert a.output[n]==50 and a.done[n] is not None and a.done[n]<=a.t
        else:assert a.output[n]==0 and a.done[n] is None
    for e,(_,d,x) in enumerate(routes):
        assert all(v is None for v in a.belts[e]) if d=="核心" else all(v is not None and a.t-v>=8 for v in a.belts[e])
    initial_end=a.t
    for n in spec:a.on[n]=True;b.on[b.name_id[n]]=True
    for _ in range(1000):a.step();b.step();compare(a,b);a.check_contract()
    result={"seed":seed,"maxlen":maxlen,"rounds":round_no,"trace":trace,"manual_operations":ops,
            "startup_steps":initial_end,"total_steps_compared":a.t,"manual_added":dict(added),
            "weight_upper":upper,"exact_prepared_state":True,"first_1000_steps_contract":True,
            "seconds":round(time.monotonic()-started,3)}
    Path(__file__).with_name(f"startup_{seed}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--seed",type=int,default=9951);p.add_argument("--maxlen",type=int,default=1)
    a=p.parse_args();run(a.seed,a.maxlen)
