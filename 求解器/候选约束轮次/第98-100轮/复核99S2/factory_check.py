"""Independent dual-engine complete material-graph tests.
Run python3 -B factory_check.py --seed 9901 --maxlen 1 --history mixed.
The graph is unembedded; no geometric or power certificate is claimed.
"""
import argparse,json,random,hashlib,time
from pathlib import Path
from engine_time import TimestampWorld
from engine_age import AgeWorld
from model_spec import graph

def compare(a,b):
    x,y=a.signature(),b.signature()
    if x!=y:
        for j,(u,v) in enumerate(zip(x,y)):
            if u!=v:
                for k,(p,q) in enumerate(zip(u,v)):
                    if p!=q:raise AssertionError((a.t,"signature",j,k,p,q))
    assert a.sent==b.sent and a.received==b.received and a.refused==b.refused,(a.t,"route counters")
    assert a.started==b.started and a.delivered==b.delivered,(a.t,"manufacture/delivery")
    return x

def units(spec,sources,routes,lengths):
    return list(dict.fromkeys([*spec,*sources])),[(i,j) for i,l in enumerate(lengths) for j in range(l)]

def credits(t):
    battery="高容谷地电池";capsule="精选荞愈胶囊"
    if 300<=t<900:return {battery:0,capsule:100}
    if 900<=t<1700:return {battery:1 if t%17==0 else 0,capsule:1 if t%23==0 else 0}
    if 1700<=t<5000:return {battery:0,capsule:0}
    if 5000<=t<6000:return {battery:1,capsule:0}
    if 6000<=t<7000:return {battery:0,capsule:1}
    if 7000<=t<8000:return {battery:int(t%3==0),capsule:int(t%5==0)}
    return None

def run(seed,maxlen,history,steps=22000):
    start=time.monotonic();rng=random.Random(seed)
    spec,sources,routes=graph()
    lengths=[rng.randint(1,maxlen) for _ in routes]
    mineral=[i for i,(a,_,_) in enumerate(routes) if a!="核心" and a in sources]
    if maxlen==1:
        for i in mineral[:8]:lengths[i]+=1
    h=next(i for i,(a,b,_) in enumerate(routes) if a=="H6")
    q=next(i for i,(a,b,_) in enumerate(routes) if a=="Q6")
    lengths[q]=lengths[h]
    a=TimestampWorld(lengths);b=AgeWorld(lengths)
    physical,belts=units(spec,sources,routes,lengths)
    rng.shuffle(physical);rng.shuffle(belts);order=physical+belts
    a.rebuild(order,False);b.rebuild(order,False)
    samples={};closed=None;rebuilds=0
    for t in range(1,steps+1):
        if t<=8500 and (t%7==0 or t in (1,300,900,1700,5000,6000,7000,8000,8500)):
            order=physical+belts;rng.shuffle(order)
            clear=history=="clear" or (history=="mixed" and bool(rng.getrandbits(1)))
            a.rebuild(order,clear);b.rebuild(order,clear);rebuilds+=1
        cap=credits(t)
        a.step(None if cap is None else dict(cap));b.step(None if cap is None else dict(cap))
        sig=compare(a,b);a.check_contract()
        if t>10000 and t%480==0:
            if t-480 in samples and samples[t-480][0]==sig:
                previous=samples[t-480]
                delta={x:a.delivered[x]-previous[1].get(x,0) for x in a.delivered}
                ore=[a.sent[i]-previous[2][i] for i,(src,_,_) in enumerate(routes) if src in sources]
                assert len(ore)==52 and set(ore)=={60},ore
                assert delta=={"高容谷地电池":36,"精选荞愈胶囊":33},delta
                important=[i for i,(src,dst,_) in enumerate(routes) if src=="核心" or (src in spec and spec[src].kind=="粉碎机" and sum(x==src for x,_,_ in routes)>1)]
                refused=[a.refused[i]-previous[3][i] for i in important]
                assert not any(refused),(important,refused)
                closed={"start":t-480,"end":t,"period_steps":480,"deliveries":delta,
                        "ore_per_route":ore,"critical_route_count":len(important),"critical_refusals":sum(refused),
                        "per_machine_batches":{n:a.started[n]-previous[4].get(n,0) for n in spec},
                        "full_state_sha256":hashlib.sha256(repr(sig).encode()).hexdigest(),
                        "direct_tuple_equality":True}
                state_artifact={"seed":seed,"lengths":lengths,"step":t,
                                "before":previous[0],"after":sig,
                                "send_connection_rank":a.send_rank,"receive_connection_rank":a.receive_rank,
                                "nontransport_order":a.unit_order,
                                "last_success_offsets":[None if x is None else x-a.t for x in a.last_send],
                                "warehouse_mode":"continuously accepting both products"}
                Path(__file__).with_name(f"factory_state_{seed}.json").write_text(json.dumps(state_artifact,ensure_ascii=False,indent=2)+"\n")
                break
            samples[t]=(sig,dict(a.delivered),a.sent[:],a.refused[:],dict(a.started))
            if len(samples)>2:del samples[min(samples)]
    assert closed is not None,(seed,"no verified closure",t)
    result={"seed":seed,"maxlen":maxlen,"belt_cells":sum(lengths),"history":history,
            "steps_compared":t,"rebuilds":rebuilds,"lengths":lengths,"cycle":closed,
            "seconds":round(time.monotonic()-start,3),"violations":0,
            "state_note":"Exact tuple equality after replacing absolute success times by their per-source order; all future choices depend only on this order."}
    out=Path(__file__).with_name(f"factory_{seed}.json")
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("lengths","cycle")},ensure_ascii=False),flush=True)
    print(json.dumps({k:v for k,v in closed.items() if k not in ("per_machine_batches","ore_per_route")},ensure_ascii=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--seed",type=int,default=9901);p.add_argument("--maxlen",type=int,default=1)
    p.add_argument("--history",choices=["keep","clear","mixed"],default="mixed");p.add_argument("--steps",type=int,default=22000)
    a=p.parse_args();run(a.seed,a.maxlen,a.history,a.steps)
